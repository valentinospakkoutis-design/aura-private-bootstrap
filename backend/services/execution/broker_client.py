from __future__ import annotations

import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from services.execution.types import BrokerOrderRequest, BrokerOrderResponse, ExecutionStatus


class BrokerClientError(Exception):
    """Raised when broker interaction fails."""


class ExecutionConfigurationError(BrokerClientError):
    """Raised when execution provider configuration is unsafe or invalid."""


class BrokerClient(ABC):
    """Strict broker abstraction used by the execution engine only."""

    @abstractmethod
    def place_order(self, request: BrokerOrderRequest) -> BrokerOrderResponse:
        raise NotImplementedError

    @abstractmethod
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_positions(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def get_balance(self) -> Dict[str, Any]:
        raise NotImplementedError


def _is_truthy(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def execution_profile() -> str:
    for env_var in ("AURA_ENV", "ENVIRONMENT", "APP_ENV"):
        value = os.getenv(env_var)
        if value and value.strip():
            return value.strip().lower()
    return "development"


def _live_like_context(trading_mode: str, allow_live_trading: bool) -> bool:
    profile = execution_profile()
    profile_live = profile in {"prod", "production", "staging", "live"}
    mode_live = str(trading_mode).strip().lower() == "live"
    return profile_live or mode_live or allow_live_trading


class StubBrokerClient(BrokerClient):
    """Deterministic local stub for development and test workflows."""

    def __init__(self, broker_name: str):
        self.broker_name = broker_name.lower()
        self._stub_orders: Dict[str, Dict[str, Any]] = {}

    def place_order(self, request: BrokerOrderRequest) -> BrokerOrderResponse:
        broker_order_id = f"{self.broker_name.upper()}-{uuid4().hex[:20]}"
        stub = {
            "order_id": broker_order_id,
            "status": "SUBMITTED",
            "symbol": request.symbol,
            "side": request.side,
            "quantity": request.quantity,
            "filled_quantity": 0.0,
            "avg_fill_price": None,
            "acknowledged_at": datetime.utcnow().isoformat(),
            "stub_mode": True,
        }
        self._stub_orders[broker_order_id] = stub
        return BrokerOrderResponse(
            broker_order_id=broker_order_id,
            status=ExecutionStatus.SUBMITTED,
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            filled_quantity=0.0,
            avg_fill_price=None,
            raw=stub,
        )

    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        return self._stub_orders.get(
            order_id,
            {
                "order_id": order_id,
                "status": "FAILED",
                "error": "ORDER_NOT_FOUND",
                "stub_mode": True,
            },
        )

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        if order_id in self._stub_orders:
            self._stub_orders[order_id]["status"] = "CANCELLED"
        return {
            "order_id": order_id,
            "status": "CANCELLED",
            "stub_mode": True,
        }

    def get_positions(self) -> List[Dict[str, Any]]:
        return []

    def get_balance(self) -> Dict[str, Any]:
        return {
            "broker": self.broker_name,
            "total_balance": 0.0,
            "available_balance": 0.0,
            "stub_mode": True,
        }


class RealBrokerClient(BrokerClient):
    """
    Structured adapter for real broker APIs.

    The adapter can be replaced with true REST/WebSocket integration without touching
    the execution engine. Stub mode is explicit and controlled by env flag.
    """

    def __init__(self, broker_name: str, adapter: Any):
        self.broker_name = broker_name.lower()
        self.adapter = adapter
        self.stub_mode = os.getenv("REAL_BROKER_STUB_MODE", "false").lower() == "true"

    @staticmethod
    def _map_status(raw_status: str) -> ExecutionStatus:
        status = (raw_status or "").upper()
        mapping = {
            "NEW": ExecutionStatus.SUBMITTED,
            "ACK": ExecutionStatus.SUBMITTED,
            "SUBMITTED": ExecutionStatus.SUBMITTED,
            "FILLED": ExecutionStatus.FILLED,
            "PARTIALLY_FILLED": ExecutionStatus.PARTIALLY_FILLED,
            "PARTIAL": ExecutionStatus.PARTIALLY_FILLED,
            "REJECTED": ExecutionStatus.FAILED,
            "FAILED": ExecutionStatus.FAILED,
            "CANCELED": ExecutionStatus.CANCELLED,
            "CANCELLED": ExecutionStatus.CANCELLED,
            "PENDING": ExecutionStatus.PENDING,
        }
        return mapping.get(status, ExecutionStatus.SUBMITTED)

    def place_order(self, request: BrokerOrderRequest) -> BrokerOrderResponse:
        if hasattr(self.adapter, "place_order"):
            raw = self.adapter.place_order(
                {
                    "symbol": request.symbol,
                    "side": request.side,
                    "quantity": request.quantity,
                    "order_type": request.order_type,
                    "price": request.price,
                    "client_order_id": request.client_order_id,
                }
            )
            if not isinstance(raw, dict):
                raise BrokerClientError("Broker returned invalid response payload")
            if raw.get("error"):
                raise BrokerClientError(str(raw["error"]))

            broker_order_id = str(raw.get("order_id") or raw.get("id") or uuid4())
            status = self._map_status(str(raw.get("status") or "SUBMITTED"))
            filled_quantity = float(raw.get("filled_quantity") or raw.get("executed_qty") or 0.0)
            avg_price = raw.get("avg_fill_price") or raw.get("price")
            avg_fill_price = float(avg_price) if avg_price is not None else None

            return BrokerOrderResponse(
                broker_order_id=broker_order_id,
                status=status,
                symbol=request.symbol,
                side=request.side,
                quantity=request.quantity,
                filled_quantity=filled_quantity,
                avg_fill_price=avg_fill_price,
                raw=raw,
            )

        raise BrokerClientError(
            "Broker adapter does not implement place_order"
        )

    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        if hasattr(self.adapter, "get_order_status"):
            response = self.adapter.get_order_status(order_id)
            if not isinstance(response, dict):
                raise BrokerClientError("Broker returned invalid order status payload")
            return response

        raise BrokerClientError(
            "Broker adapter does not implement get_order_status"
        )

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        if hasattr(self.adapter, "cancel_order"):
            response = self.adapter.cancel_order(order_id)
            if not isinstance(response, dict):
                raise BrokerClientError("Broker returned invalid cancel payload")
            return response

        raise BrokerClientError(
            "Broker adapter does not implement cancel_order"
        )

    def get_positions(self) -> List[Dict[str, Any]]:
        if hasattr(self.adapter, "get_positions"):
            positions = self.adapter.get_positions()
            if isinstance(positions, list):
                return positions
            raise BrokerClientError("Broker returned invalid positions payload")

        raise BrokerClientError(
            "Broker adapter does not implement get_positions"
        )

    def get_balance(self) -> Dict[str, Any]:
        if hasattr(self.adapter, "get_balance"):
            balance = self.adapter.get_balance()
            if isinstance(balance, dict):
                return balance
            raise BrokerClientError("Broker returned invalid balance payload")

        if hasattr(self.adapter, "get_account_balance"):
            balance = self.adapter.get_account_balance()
            if isinstance(balance, dict):
                return balance
            raise BrokerClientError("Broker returned invalid account balance payload")

        raise BrokerClientError(
            "Broker adapter does not implement get_balance"
        )


def validate_execution_provider_or_raise(*, provider: str, trading_mode: str, allow_live_trading: bool) -> None:
    normalized_provider = (provider or "stub").strip().lower()
    if normalized_provider == "stub" and _live_like_context(trading_mode, allow_live_trading):
        raise ExecutionConfigurationError(
            "Stub execution provider is forbidden when live trading or production profile is enabled"
        )


def build_broker_client(
    *,
    provider: str,
    broker_name: str,
    adapter: Any,
    trading_mode: str,
    allow_live_trading: bool,
) -> BrokerClient:
    normalized_provider = (provider or "stub").strip().lower()
    validate_execution_provider_or_raise(
        provider=normalized_provider,
        trading_mode=trading_mode,
        allow_live_trading=allow_live_trading,
    )

    if normalized_provider == "stub":
        return StubBrokerClient(broker_name=broker_name)

    if normalized_provider == "binance":
        from services.execution.binance_adapter import BinanceBrokerClient

        return BinanceBrokerClient.from_adapter(adapter)

    if normalized_provider == "auto":
        if broker_name.strip().lower() == "binance":
            from services.execution.binance_adapter import BinanceBrokerClient

            return BinanceBrokerClient.from_adapter(adapter)
        return RealBrokerClient(broker_name=broker_name, adapter=adapter)

    raise ExecutionConfigurationError(
        f"Unsupported EXECUTION_PROVIDER '{provider}'. Supported values: stub, binance, auto"
    )
