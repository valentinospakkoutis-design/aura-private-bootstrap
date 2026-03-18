from __future__ import annotations

import importlib

import pytest

from ops.secret_loader import SecretConfigurationError, SecretLoader
from services.execution.broker_client import BrokerClientError
from services.execution.reliability import BrokerExecutionGuard, GuardConfig
from services.execution.startup_checks import ExecutionStartupChecker, StartupSafetyError

pytestmark = pytest.mark.unit


def test_secret_loader_missing_secret_raises_without_leaking_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MISSING_SECRET", raising=False)
    loader = SecretLoader()

    with pytest.raises(SecretConfigurationError) as exc:
        loader.get_secret("MISSING_SECRET")

    assert "MISSING_SECRET" in str(exc.value)
    assert "super-secret-value" not in str(exc.value)


def test_live_startup_checker_fails_when_db_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    checker = ExecutionStartupChecker()
    monkeypatch.setenv("TRADING_MODE", "live")
    monkeypatch.setenv("ALLOW_LIVE_TRADING", "true")

    module = importlib.import_module("services.execution.startup_checks")
    monkeypatch.setattr(module, "check_db_connection", lambda: False, raising=True)

    with pytest.raises(StartupSafetyError):
        checker.validate_live_requirements(provider="binance")


def test_broker_guard_retries_retryable_errors_then_succeeds() -> None:
    guard = BrokerExecutionGuard(
        provider="binance",
        config=GuardConfig(max_retries=3, backoff_base_seconds=0.001, call_timeout_seconds=1.0),
    )

    calls = {"count": 0}

    def _flaky():
        calls["count"] += 1
        if calls["count"] < 3:
            raise RuntimeError("network timeout")
        return {"ok": True}

    result = guard.execute(operation="POST /api/v3/order", symbol="BTCUSDT", fn=_flaky)

    assert result == {"ok": True}
    assert calls["count"] == 3


def test_broker_guard_does_not_retry_non_retryable_errors() -> None:
    guard = BrokerExecutionGuard(
        provider="binance",
        config=GuardConfig(max_retries=3, backoff_base_seconds=0.001, call_timeout_seconds=1.0),
    )

    calls = {"count": 0}

    def _invalid_order():
        calls["count"] += 1
        raise RuntimeError("invalid quantity")

    with pytest.raises(BrokerClientError):
        guard.execute(operation="POST /api/v3/order", symbol="BTCUSDT", fn=_invalid_order)

    assert calls["count"] == 1


def test_live_startup_checker_blocks_when_migrations_not_current(monkeypatch: pytest.MonkeyPatch) -> None:
    checker = ExecutionStartupChecker()
    monkeypatch.setenv("TRADING_MODE", "live")
    monkeypatch.setenv("ALLOW_LIVE_TRADING", "true")
    monkeypatch.setenv("BINANCE_API_KEY", "x" * 24)
    monkeypatch.setenv("BINANCE_API_SECRET", "y" * 48)

    module = importlib.import_module("services.execution.startup_checks")
    monkeypatch.setattr(module, "check_db_connection", lambda: True, raising=True)

    def _raise_migration_error() -> None:
        raise StartupSafetyError("migrations outdated")

    monkeypatch.setattr(
        ExecutionStartupChecker,
        "_assert_migrations_up_to_date",
        staticmethod(_raise_migration_error),
        raising=True,
    )

    with pytest.raises(StartupSafetyError):
        checker.validate_live_requirements(provider="binance")
