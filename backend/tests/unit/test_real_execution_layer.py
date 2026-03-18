from __future__ import annotations

from typing import Any, Dict, List

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from database.models import Base, ExecutionOrder
from services.execution.broker_client import BrokerClientError
from services.execution.engine import RealExecutionEngine
from services.execution.types import (
    BrokerOrderRequest,
    BrokerOrderResponse,
    ExecutionRequest,
    ExecutionStatus,
    ValidationContext,
)

pytestmark = pytest.mark.unit


class _FakeBrokerClient:
    def __init__(self):
        self.place_calls = 0
        self.cancel_calls = 0
        self.fail_place = False
        self.partial_fill = False
        self.latest_order_id = "BROKER-ORDER-001"
        self.status_payload = {
            "order_id": self.latest_order_id,
            "status": "SUBMITTED",
            "filled_quantity": 0.0,
        }

    def place_order(self, request: BrokerOrderRequest) -> BrokerOrderResponse:
        self.place_calls += 1
        if self.fail_place:
            raise BrokerClientError("broker down")
        if self.partial_fill:
            return BrokerOrderResponse(
                broker_order_id=self.latest_order_id,
                status=ExecutionStatus.PARTIALLY_FILLED,
                symbol=request.symbol,
                side=request.side,
                quantity=request.quantity,
                filled_quantity=request.quantity / 2,
                avg_fill_price=request.price,
                raw={"status": "PARTIALLY_FILLED", "filled_quantity": request.quantity / 2},
            )
        return BrokerOrderResponse(
            broker_order_id=self.latest_order_id,
            status=ExecutionStatus.SUBMITTED,
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            filled_quantity=0.0,
            avg_fill_price=None,
            raw={"status": "SUBMITTED", "filled_quantity": 0.0},
        )

    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        return dict(self.status_payload)

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        self.cancel_calls += 1
        return {"order_id": order_id, "status": "CANCELLED"}

    def get_positions(self) -> List[Dict[str, Any]]:
        return []

    def get_balance(self) -> Dict[str, Any]:
        return {"total_balance": 10000.0}


@pytest.fixture
def db_session_factory():
    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)
    try:
        yield SessionLocal
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _base_context(**overrides: Any) -> ValidationContext:
    data = {
        "user_roles": ["trader"],
        "allowed_symbols": ["BTCUSDT"],
        "portfolio_value": 10000.0,
        "max_position_size_percent": 10.0,
        "max_daily_loss_percent": 5.0,
        "current_daily_loss": 0.0,
        "stop_loss_required": False,
        "trading_mode": "live",
        "env_trading_mode": "live",
        "allow_live_trading": True,
        "kill_switch_active": False,
        "idempotency_reserved": True,
    }
    data.update(overrides)
    return ValidationContext(**data)


def _base_request(**overrides: Any) -> ExecutionRequest:
    data = {
        "broker": "binance",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "quantity": 0.2,
        "order_type": "MARKET",
        "price": 1000.0,
        "stop_loss_price": 990.0,
        "idempotency_key": "idem-001",
        "user_email": "trader@example.com",
    }
    data.update(overrides)
    return ExecutionRequest(**data)


def test_duplicate_idempotency_key_does_not_double_execute(db_session_factory) -> None:
    engine = RealExecutionEngine(session_factory=db_session_factory)
    broker = _FakeBrokerClient()

    first = engine.execute_order(
        request=_base_request(),
        context=_base_context(),
        broker_client=broker,
    )
    second = engine.execute_order(
        request=_base_request(),
        context=_base_context(),
        broker_client=broker,
    )

    assert first["replayed"] is False
    assert second["replayed"] is True
    assert broker.place_calls == 1


def test_idempotency_key_mismatch_hard_reject(db_session_factory) -> None:
    engine = RealExecutionEngine(session_factory=db_session_factory)
    broker = _FakeBrokerClient()

    engine.execute_order(
        request=_base_request(),
        context=_base_context(),
        broker_client=broker,
    )

    with pytest.raises(HTTPException) as exc:
        engine.execute_order(
            request=_base_request(quantity=0.5),
            context=_base_context(),
            broker_client=broker,
        )

    assert exc.value.status_code == 409
    assert exc.value.detail["error"] == "IDEMPOTENCY_KEY_REUSE_MISMATCH"


def test_broker_failure_marks_failed_without_state_corruption(db_session_factory) -> None:
    engine = RealExecutionEngine(session_factory=db_session_factory)
    broker = _FakeBrokerClient()
    broker.fail_place = True

    with pytest.raises(HTTPException) as exc:
        engine.execute_order(
            request=_base_request(),
            context=_base_context(),
            broker_client=broker,
        )

    assert exc.value.status_code == 502

    db = db_session_factory()
    try:
        stored = db.query(ExecutionOrder).filter(ExecutionOrder.idempotency_key == "idem-001").first()
        assert stored is not None
        assert stored.status == "FAILED"
        assert stored.broker_order_id is None
    finally:
        db.close()


def test_validation_failure_blocks_execution_before_broker_call(db_session_factory) -> None:
    engine = RealExecutionEngine(session_factory=db_session_factory)
    broker = _FakeBrokerClient()

    with pytest.raises(HTTPException) as exc:
        engine.execute_order(
            request=_base_request(),
            context=_base_context(kill_switch_active=True),
            broker_client=broker,
        )

    assert exc.value.detail["error"] == "KILL_SWITCH_ACTIVE"
    assert broker.place_calls == 0


def test_partial_fill_state_is_persisted(db_session_factory) -> None:
    engine = RealExecutionEngine(session_factory=db_session_factory)
    broker = _FakeBrokerClient()
    broker.partial_fill = True

    result = engine.execute_order(
        request=_base_request(),
        context=_base_context(),
        broker_client=broker,
    )

    assert result["status"] == "PARTIALLY_FILLED"


def test_reconciliation_updates_state_from_broker(db_session_factory) -> None:
    engine = RealExecutionEngine(session_factory=db_session_factory)
    broker = _FakeBrokerClient()

    result = engine.execute_order(
        request=_base_request(),
        context=_base_context(),
        broker_client=broker,
    )
    assert result["status"] == "SUBMITTED"

    broker.status_payload = {
        "order_id": broker.latest_order_id,
        "status": "FILLED",
        "filled_quantity": 0.2,
        "avg_fill_price": 1002.0,
    }

    summary = engine.reconcile_once(
        broker_client_resolver=lambda _: broker,
    )

    assert summary["updated"] >= 1

    db = db_session_factory()
    try:
        stored = db.query(ExecutionOrder).filter(ExecutionOrder.idempotency_key == "idem-001").first()
        assert stored is not None
        assert stored.status == "FILLED"
        assert float(stored.filled_quantity) == pytest.approx(0.2)
    finally:
        db.close()


def test_live_mode_required(db_session_factory) -> None:
    engine = RealExecutionEngine(session_factory=db_session_factory)
    broker = _FakeBrokerClient()

    with pytest.raises(HTTPException) as exc:
        engine.execute_order(
            request=_base_request(),
            context=_base_context(trading_mode="paper"),
            broker_client=broker,
        )

    assert exc.value.detail["error"] == "LIVE_MODE_REQUIRED"


def test_crash_before_persistence_never_calls_broker(db_session_factory) -> None:
    engine = RealExecutionEngine(session_factory=db_session_factory)
    broker = _FakeBrokerClient()

    def _raise_before_insert(mapper, connection, target):
        raise RuntimeError("db write failed")

    event.listen(ExecutionOrder, "before_insert", _raise_before_insert)
    try:
        with pytest.raises(HTTPException) as exc:
            engine.execute_order(
                request=_base_request(),
                context=_base_context(),
                broker_client=broker,
            )
        assert exc.value.detail["error"] == "ORDER_PERSISTENCE_FAILED"
        assert broker.place_calls == 0
    finally:
        event.remove(ExecutionOrder, "before_insert", _raise_before_insert)


class _FailingFinalCommitSession(Session):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._commit_count = 0

    def commit(self):
        self._commit_count += 1
        if self._commit_count == 3:
            raise RuntimeError("commit failed after broker submission")
        return super().commit()


def test_crash_after_submission_triggers_cancel(db_session_factory) -> None:
    bind = db_session_factory.kw["bind"]
    FailingSessionLocal = sessionmaker(
        bind=bind,
        autocommit=False,
        autoflush=False,
        class_=_FailingFinalCommitSession,
    )
    engine = RealExecutionEngine(session_factory=FailingSessionLocal)
    broker = _FakeBrokerClient()

    with pytest.raises(HTTPException) as exc:
        engine.execute_order(
            request=_base_request(),
            context=_base_context(),
            broker_client=broker,
        )

    assert exc.value.status_code == 503
    assert exc.value.detail["error"] == "DB_PERSIST_FAILED_AFTER_SUBMISSION"
    assert broker.cancel_calls == 1
