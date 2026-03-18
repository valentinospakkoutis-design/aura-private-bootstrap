from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, Optional
from uuid import uuid4

from fastapi import HTTPException, status

from database.connection import SessionLocal
from database.models import ExecutionOrder, ExecutionOrderAudit
from ops.observability import runtime_monitor
from services.execution.broker_client import BrokerClient, BrokerClientError
from services.execution.types import (
    BrokerOrderRequest,
    ExecutionRequest,
    ExecutionStatus,
    ValidationContext,
)

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {
    ExecutionStatus.FILLED.value,
    ExecutionStatus.FAILED.value,
    ExecutionStatus.CANCELLED.value,
}

OPEN_STATUSES = {
    ExecutionStatus.PENDING.value,
    ExecutionStatus.SUBMITTED.value,
    ExecutionStatus.PARTIALLY_FILLED.value,
}


class RealExecutionEngine:
    """Deterministic execution engine for live broker-backed orders."""

    def __init__(self, session_factory: Callable[[], Any] = SessionLocal):
        self._session_factory = session_factory

    @staticmethod
    def _fingerprint(request: ExecutionRequest) -> str:
        payload = {
            "broker": request.broker.lower(),
            "symbol": request.symbol.upper(),
            "side": request.side.upper(),
            "quantity": float(request.quantity),
            "order_type": request.order_type.upper(),
            "price": float(request.price),
            "stop_loss_price": float(request.stop_loss_price) if request.stop_loss_price is not None else None,
            "user_email": request.user_email.lower(),
        }
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def _ensure(condition: bool, code: str, message: str, http_status: int = status.HTTP_400_BAD_REQUEST) -> None:
        if not condition:
            raise HTTPException(status_code=http_status, detail={"error": code, "message": message})

    def validate_order(self, request: ExecutionRequest, context: ValidationContext) -> Dict[str, Any]:
        self._ensure(context.trading_mode.lower() == "live", "LIVE_MODE_REQUIRED", "Trading mode must be live")
        self._ensure(context.env_trading_mode.lower() == "live", "LIVE_MODE_ENV_REQUIRED", "TRADING_MODE must be live")
        self._ensure(context.allow_live_trading, "LIVE_TRADING_DISABLED", "ALLOW_LIVE_TRADING must be true")
        self._ensure(not context.kill_switch_active, "KILL_SWITCH_ACTIVE", "Kill switch is active")
        self._ensure(context.idempotency_reserved, "IDEMPOTENCY_NOT_RESERVED", "Idempotency reservation is required")

        roles = {r.strip().lower() for r in context.user_roles if r.strip()}
        self._ensure(
            bool(roles.intersection({"trader", "admin"})),
            "EXECUTION_FORBIDDEN",
            "Trader or admin role required for live execution",
            http_status=status.HTTP_403_FORBIDDEN,
        )

        symbol = request.symbol.upper().strip()
        allowed_symbols = {s.strip().upper() for s in context.allowed_symbols if s.strip()}
        self._ensure(bool(symbol), "INVALID_SYMBOL", "Symbol is required")
        if allowed_symbols:
            self._ensure(symbol in allowed_symbols, "SYMBOL_NOT_ALLOWED", f"Symbol {symbol} is not allowed")

        self._ensure(request.side.upper() in {"BUY", "SELL"}, "INVALID_SIDE", "Side must be BUY or SELL")
        self._ensure(request.quantity > 0, "INVALID_QUANTITY", "Quantity must be > 0")
        self._ensure(request.price > 0, "INVALID_PRICE", "Price must be > 0")

        order_value = float(request.quantity) * float(request.price)
        self._ensure(context.portfolio_value > 0, "INVALID_PORTFOLIO_VALUE", "Portfolio value must be > 0")
        position_size_percent = (order_value / context.portfolio_value) * 100.0
        self._ensure(
            position_size_percent <= context.max_position_size_percent,
            "POSITION_SIZE_EXCEEDED",
            "Position size exceeds configured cap",
        )

        max_daily_loss = abs(context.max_daily_loss_percent * context.portfolio_value / 100.0)
        self._ensure(
            abs(context.current_daily_loss) <= max_daily_loss,
            "DAILY_LOSS_LIMIT_REACHED",
            "Daily loss cap reached",
        )

        if context.stop_loss_required and request.stop_loss_price is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "STOP_LOSS_REQUIRED", "message": "Stop loss is required for live execution"},
            )

        return {
            "valid": True,
            "symbol": symbol,
            "order_value": order_value,
            "position_size_percent": position_size_percent,
            "validated_at": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def _to_result(order: ExecutionOrder, replayed: bool = False) -> Dict[str, Any]:
        return {
            "internal_order_id": order.internal_order_id,
            "idempotency_key": order.idempotency_key,
            "broker": order.broker,
            "broker_order_id": order.broker_order_id,
            "symbol": order.symbol,
            "side": order.side,
            "quantity": float(order.quantity),
            "price": float(order.price),
            "status": order.status,
            "error_reason": order.error_reason,
            "replayed": replayed,
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "updated_at": order.updated_at.isoformat() if order.updated_at else None,
        }

    @staticmethod
    def _audit(
        session: Any,
        internal_order_id: str,
        event_type: str,
        payload: Dict[str, Any],
    ) -> None:
        session.add(
            ExecutionOrderAudit(
                internal_order_id=internal_order_id,
                event_type=event_type,
                payload=payload,
                created_at=datetime.utcnow(),
            )
        )

    def execute_order(
        self,
        *,
        request: ExecutionRequest,
        context: ValidationContext,
        broker_client: BrokerClient,
    ) -> Dict[str, Any]:
        validation = self.validate_order(request, context)
        request_hash = self._fingerprint(request)

        session = self._session_factory()
        order: Optional[ExecutionOrder] = None
        internal_order_id = f"AURA-{uuid4().hex[:24].upper()}"

        try:
            existing = (
                session.query(ExecutionOrder)
                .filter(ExecutionOrder.idempotency_key == request.idempotency_key)
                .first()
            )
            if existing is not None:
                if existing.request_fingerprint != request_hash:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail={
                            "error": "IDEMPOTENCY_KEY_REUSE_MISMATCH",
                            "message": "Idempotency key already used with different payload",
                        },
                    )
                runtime_monitor.record_idempotency_replay()
                return self._to_result(existing, replayed=True)

            order = ExecutionOrder(
                internal_order_id=internal_order_id,
                idempotency_key=request.idempotency_key,
                request_fingerprint=request_hash,
                broker=request.broker.lower(),
                broker_order_id=None,
                symbol=request.symbol.upper(),
                side=request.side.upper(),
                quantity=float(request.quantity),
                price=float(request.price),
                status=ExecutionStatus.PENDING.value,
                error_reason=None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(order)
            self._audit(session, internal_order_id, "DECISION_INPUT", request.__dict__)
            self._audit(session, internal_order_id, "VALIDATED_ORDER", validation)
            session.commit()

            broker_request = BrokerOrderRequest(
                symbol=request.symbol.upper(),
                side=request.side.upper(),
                quantity=float(request.quantity),
                order_type=request.order_type.upper(),
                price=float(request.price),
                client_order_id=request.idempotency_key,
            )
            self._audit(session, internal_order_id, "BROKER_REQUEST", broker_request.__dict__)
            session.commit()

            try:
                broker_response = broker_client.place_order(broker_request)
            except BrokerClientError as exc:
                order.status = ExecutionStatus.FAILED.value
                order.error_reason = f"BROKER_CALL_FAILED: {exc}"
                order.updated_at = datetime.utcnow()
                runtime_monitor.record_order_failed(symbol=request.symbol.upper(), error_type="BROKER_CALL_FAILED", latency_ms=0.0)
                self._audit(
                    session,
                    internal_order_id,
                    "BROKER_FAILURE",
                    {"error": str(exc)},
                )
                session.commit()
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail={"error": "BROKER_CALL_FAILED", "message": str(exc)},
                )

            order.broker_order_id = broker_response.broker_order_id
            order.status = broker_response.status.value
            order.filled_quantity = float(broker_response.filled_quantity)
            order.avg_fill_price = broker_response.avg_fill_price
            order.updated_at = datetime.utcnow()

            self._audit(session, internal_order_id, "BROKER_RESPONSE", broker_response.raw)
            self._audit(session, internal_order_id, "FINAL_STATE", {"status": order.status})
            try:
                session.commit()
            except Exception as persist_error:
                session.rollback()
                try:
                    if broker_response.broker_order_id:
                        broker_client.cancel_order(broker_response.broker_order_id)
                except Exception:
                    logger.exception("Broker cancel failed after persistence error")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={
                        "error": "DB_PERSIST_FAILED_AFTER_SUBMISSION",
                        "message": f"Order submitted to broker but persistence failed: {persist_error}",
                    },
                )

            return self._to_result(order, replayed=False)

        except HTTPException:
            session.rollback()
            raise
        except Exception as exc:
            session.rollback()
            if order is None or (order.broker_order_id is None and order.status == ExecutionStatus.PENDING.value):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={
                        "error": "ORDER_PERSISTENCE_FAILED",
                        "message": f"Unable to persist order before execution: {exc}",
                    },
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "EXECUTION_ENGINE_ERROR",
                    "message": f"Execution engine failed unexpectedly: {exc}",
                },
            )
        finally:
            session.close()

    def reconcile_once(
        self,
        *,
        broker_client_resolver: Callable[[str], Optional[BrokerClient]],
        limit: int = 100,
    ) -> Dict[str, Any]:
        session = self._session_factory()
        updated = 0
        flagged = 0
        checked = 0

        try:
            open_orders: Iterable[ExecutionOrder] = (
                session.query(ExecutionOrder)
                .filter(ExecutionOrder.status.in_(OPEN_STATUSES))
                .limit(limit)
                .all()
            )
            for order in open_orders:
                checked += 1
                if not order.broker_order_id:
                    continue
                broker_client = broker_client_resolver(order.broker)
                if broker_client is None:
                    flagged += 1
                    self._audit(
                        session,
                        order.internal_order_id,
                        "RECONCILIATION_MISMATCH",
                        {"reason": "broker_client_missing", "broker": order.broker},
                    )
                    continue

                try:
                    broker_status_payload = broker_client.get_order_status(order.broker_order_id)
                except Exception as exc:
                    flagged += 1
                    self._audit(
                        session,
                        order.internal_order_id,
                        "RECONCILIATION_MISMATCH",
                        {"reason": "status_fetch_failed", "error": str(exc)},
                    )
                    continue

                broker_status = str(broker_status_payload.get("status") or "").upper()
                normalized = {
                    "NEW": ExecutionStatus.SUBMITTED.value,
                    "ACK": ExecutionStatus.SUBMITTED.value,
                    "SUBMITTED": ExecutionStatus.SUBMITTED.value,
                    "FILLED": ExecutionStatus.FILLED.value,
                    "PARTIALLY_FILLED": ExecutionStatus.PARTIALLY_FILLED.value,
                    "PARTIAL": ExecutionStatus.PARTIALLY_FILLED.value,
                    "FAILED": ExecutionStatus.FAILED.value,
                    "REJECTED": ExecutionStatus.FAILED.value,
                    "CANCELED": ExecutionStatus.CANCELLED.value,
                    "CANCELLED": ExecutionStatus.CANCELLED.value,
                    "PENDING": ExecutionStatus.PENDING.value,
                }.get(broker_status, order.status)

                if normalized != order.status:
                    flagged += 1
                    self._audit(
                        session,
                        order.internal_order_id,
                        "RECONCILIATION_MISMATCH",
                        {
                            "local_status": order.status,
                            "broker_status": normalized,
                            "raw": broker_status_payload,
                        },
                    )

                new_filled = float(broker_status_payload.get("filled_quantity") or order.filled_quantity or 0.0)
                new_avg_price_raw = broker_status_payload.get("avg_fill_price")
                new_avg_price = float(new_avg_price_raw) if new_avg_price_raw is not None else order.avg_fill_price

                if (
                    order.status != normalized
                    or float(order.filled_quantity or 0.0) != new_filled
                    or order.avg_fill_price != new_avg_price
                ):
                    order.status = normalized
                    order.filled_quantity = new_filled
                    order.avg_fill_price = new_avg_price
                    order.updated_at = datetime.utcnow()
                    self._audit(
                        session,
                        order.internal_order_id,
                        "RECONCILIATION_UPDATE",
                        {
                            "status": normalized,
                            "filled_quantity": new_filled,
                            "avg_fill_price": new_avg_price,
                        },
                    )
                    updated += 1

            session.commit()
            return {
                "checked": checked,
                "updated": updated,
                "flagged": flagged,
                "timestamp": datetime.utcnow().isoformat(),
            }
        finally:
            session.close()
