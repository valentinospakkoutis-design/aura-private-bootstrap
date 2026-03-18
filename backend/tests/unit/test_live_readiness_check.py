from __future__ import annotations

import json

import pytest

from services.live_readiness import (
    FAIL,
    GO,
    LIMITED_GO,
    NO_GO,
    PASS,
    ReadinessCheck,
    WARNING,
    LiveReadinessChecker,
    exit_code_for_verdict,
)
from tools.live_readiness_check import main as readiness_main

pytestmark = pytest.mark.unit


@pytest.fixture
def checker() -> LiveReadinessChecker:
    return LiveReadinessChecker()


def _set_live_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRADING_MODE", "live")
    monkeypatch.setenv("ALLOW_LIVE_TRADING", "true")
    monkeypatch.setenv("AURA_ENV", "production")


def test_live_mode_with_stub_provider_is_no_go(checker: LiveReadinessChecker, monkeypatch: pytest.MonkeyPatch) -> None:
    _set_live_env(monkeypatch)
    monkeypatch.setenv("EXECUTION_PROVIDER", "stub")

    result = checker.check_execution_provider_safety()

    assert result.status == FAIL
    assert "Stub execution provider" in result.details


def test_missing_broker_secret_is_no_go(checker: LiveReadinessChecker, monkeypatch: pytest.MonkeyPatch) -> None:
    _set_live_env(monkeypatch)
    monkeypatch.setenv("EXECUTION_PROVIDER", "binance")
    monkeypatch.delenv("BINANCE_API_KEY", raising=False)
    monkeypatch.delenv("BINANCE_API_SECRET", raising=False)

    result = checker.check_broker_credentials()

    assert result.status == FAIL
    assert "validation failed" in result.details


def test_db_unavailable_is_no_go(checker: LiveReadinessChecker, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("services.live_readiness.check_db_connection", lambda: False, raising=True)

    result = checker.check_database_readiness()

    assert result.status == FAIL
    assert "not reachable" in result.details


def test_migrations_not_current_is_no_go(checker: LiveReadinessChecker, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("services.live_readiness.check_db_connection", lambda: True, raising=True)
    monkeypatch.setattr(
        checker,
        "_migration_state",
        lambda: (False, "Migrations not current"),
        raising=True,
    )

    class _FakeInspector:
        @staticmethod
        def get_table_names() -> list[str]:
            return [
                "execution_orders",
                "execution_order_audit",
                "order_submission_ledger",
                "pnl_snapshots",
                "drawdown_events",
                "risk_shutdown_events",
                "alembic_version",
            ]

    class _FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class _FakeEngine:
        @staticmethod
        def connect():
            return _FakeConn()

    monkeypatch.setattr("services.live_readiness.sync_engine", _FakeEngine(), raising=True)
    monkeypatch.setattr("services.live_readiness.inspect", lambda conn: _FakeInspector(), raising=True)

    result = checker.check_database_readiness()

    assert result.status == FAIL
    assert "Migrations not current" in result.details


def test_kill_switch_active_yields_limited_go(checker: LiveReadinessChecker, monkeypatch: pytest.MonkeyPatch) -> None:
    verdict = checker._compute_verdict(
        [
            ReadinessCheck(name="execution_provider", status=PASS, details="ok", critical=True),
            ReadinessCheck(name="database_readiness", status=PASS, details="ok", critical=True),
            ReadinessCheck(name="kill_switch", status=WARNING, details="global active", critical=False),
        ]
    )

    assert verdict == LIMITED_GO


def test_all_critical_pass_returns_go(checker: LiveReadinessChecker, monkeypatch: pytest.MonkeyPatch) -> None:
    ok = ReadinessCheck(name="any", status=PASS, details="ok", critical=True)
    ok_non_critical = ReadinessCheck(name="any_optional", status=PASS, details="ok", critical=False)

    monkeypatch.setattr(checker, "check_test_status", lambda: ok_non_critical, raising=True)
    monkeypatch.setattr(checker, "check_execution_provider_safety", lambda: ok, raising=True)
    monkeypatch.setattr(checker, "check_broker_credentials", lambda: ok, raising=True)
    monkeypatch.setattr(checker, "check_database_readiness", lambda: ok, raising=True)
    monkeypatch.setattr(checker, "check_kill_switch_status", lambda: ok_non_critical, raising=True)
    monkeypatch.setattr(checker, "check_risk_governor_readiness", lambda: ok, raising=True)
    monkeypatch.setattr(checker, "check_startup_live_guards", lambda: ok, raising=True)
    monkeypatch.setattr(checker, "check_observability_alerting", lambda: ok_non_critical, raising=True)
    monkeypatch.setattr(checker, "check_operator_limits", lambda: ok_non_critical, raising=True)

    report = checker.run()

    assert report.verdict == GO


def test_json_mode_output_valid(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(
        "tools.live_readiness_check.LiveReadinessChecker.run",
        lambda self: type(
            "R",
            (),
            {
                "to_dict": lambda _self: {
                    "verdict": LIMITED_GO,
                    "checks": [{"name": "kill_switch", "status": WARNING, "details": "active"}],
                },
                "verdict": LIMITED_GO,
            },
        )(),
        raising=True,
    )

    code = readiness_main(["--json"])
    out = capsys.readouterr().out
    payload = json.loads(out)

    assert code == 1
    assert payload["verdict"] == LIMITED_GO
    assert payload["checks"][0]["name"] == "kill_switch"


def test_exit_codes_correct() -> None:
    assert exit_code_for_verdict(GO) == 0
    assert exit_code_for_verdict(LIMITED_GO) == 1
    assert exit_code_for_verdict(NO_GO) == 2
