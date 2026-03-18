from __future__ import annotations

import os
import types

import pytest

from services.execution.broker_client import (
    BrokerClientError,
    ExecutionConfigurationError,
    build_broker_client,
    validate_execution_provider_or_raise,
)
from services.live_trading import LiveTradingService

pytestmark = pytest.mark.unit


def test_live_mode_with_stub_provider_hard_fails() -> None:
    with pytest.raises(ExecutionConfigurationError):
        validate_execution_provider_or_raise(
            provider="stub",
            trading_mode="live",
            allow_live_trading=True,
        )


def test_paper_mode_with_stub_provider_allowed() -> None:
    validate_execution_provider_or_raise(
        provider="stub",
        trading_mode="paper",
        allow_live_trading=False,
    )


def test_no_fallback_to_stub_when_binance_missing_credentials() -> None:
    with pytest.raises(BrokerClientError):
        build_broker_client(
            provider="binance",
            broker_name="binance",
            adapter=types.SimpleNamespace(api_key=None, api_secret=None, testnet=True),
            trading_mode="live",
            allow_live_trading=True,
        )


def test_live_execution_path_initializes_real_binance_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    service = LiveTradingService()
    service.set_trading_mode("live")

    monkeypatch.setenv("EXECUTION_PROVIDER", "binance")
    monkeypatch.setenv("ALLOW_LIVE_TRADING", "true")
    monkeypatch.setenv("TRADING_MODE", "live")

    adapter = types.SimpleNamespace(api_key="key", api_secret="secret", testnet=True, get_supported_symbols=lambda: ["BTCUSDT"])

    from services.execution.binance_adapter import BinanceBrokerClient

    monkeypatch.setattr(
        BinanceBrokerClient,
        "get_balance",
        lambda self: {"total_balance": 10000.0, "available_balance": 9000.0},
        raising=True,
    )
    monkeypatch.setattr(
        BinanceBrokerClient,
        "place_order",
        lambda self, request: type("Resp", (), {
            "broker_order_id": "abc123",
            "status": type("Status", (), {"value": "SUBMITTED"})(),
            "filled_quantity": 0.0,
            "avg_fill_price": None,
            "raw": {"status": "NEW"},
        })(),
        raising=True,
    )
    monkeypatch.setattr(
        service.execution_engine,
        "execute_order",
        lambda request, context, broker_client: {
            "internal_order_id": "AURA-TEST-1",
            "idempotency_key": request.idempotency_key,
            "broker": request.broker,
            "broker_order_id": "abc123",
            "symbol": request.symbol,
            "side": request.side,
            "quantity": request.quantity,
            "price": request.price,
            "status": "SUBMITTED",
            "error_reason": None,
            "replayed": False,
            "created_at": "2026-03-18T00:00:00",
            "updated_at": "2026-03-18T00:00:00",
        },
        raising=True,
    )

    result = service.execute_live_order(
        broker="binance",
        symbol="BTCUSDT",
        side="BUY",
        quantity=0.1,
        order_type="MARKET",
        validation_result={"valid": True, "errors": []},
        idempotency_key="idem-live-1",
        user_email="trader@example.com",
        user_roles=["trader"],
        broker_adapter=adapter,
        price=1000.0,
        stop_loss_price=990.0,
        idempotency_reserved=True,
    )

    assert "error" not in result
    assert result["status"] == "SUBMITTED"


def test_production_profile_startup_lockout(monkeypatch: pytest.MonkeyPatch) -> None:
    service = LiveTradingService()
    service.set_trading_mode("live")

    monkeypatch.setenv("AURA_ENV", "production")
    monkeypatch.setenv("EXECUTION_PROVIDER", "stub")
    monkeypatch.setenv("ALLOW_LIVE_TRADING", "true")

    with pytest.raises(ExecutionConfigurationError):
        service.validate_execution_configuration()

    monkeypatch.delenv("AURA_ENV", raising=False)
    monkeypatch.delenv("EXECUTION_PROVIDER", raising=False)
    monkeypatch.delenv("ALLOW_LIVE_TRADING", raising=False)
    monkeypatch.delenv("TRADING_MODE", raising=False)
