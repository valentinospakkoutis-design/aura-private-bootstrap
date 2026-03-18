from __future__ import annotations

from typing import Any, Dict, List

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, DrawdownEvent, PnLSnapshot, RiskShutdownEvent
from ops.kill_switch import kill_switch_manager
from ops.observability import runtime_monitor
from services.risk_governor import RiskGovernorConfig, RiskGovernorService

pytestmark = pytest.mark.unit


@pytest.fixture
def risk_service() -> RiskGovernorService:
    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    config = RiskGovernorConfig(
        caution_drawdown_pct=2.0,
        defense_drawdown_pct=4.0,
        preservation_drawdown_pct=6.0,
        hard_shutdown_drawdown_pct=10.0,
        daily_loss_limit_pct=50.0,
        session_loss_limit_pct=50.0,
        auto_shutdown_activates_kill_switch=True,
        auto_shutdown_cancel_open_orders=False,
        preservation_blocks_new_trades=True,
        session_bucket_hours=24,
    )
    service = RiskGovernorService(session_factory=SessionLocal, config=config)

    kill_switch_manager.global_active = False
    kill_switch_manager.emergency_mode = False
    kill_switch_manager.cancel_open_orders = False
    kill_switch_manager.blocked_symbols.clear()
    kill_switch_manager.blocked_strategies.clear()
    kill_switch_manager.audit_events.clear()

    yield service

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_pnl_updates_after_wins_and_losses(risk_service: RiskGovernorService) -> None:
    first = risk_service.update_pnl(mode="paper", equity=10000.0, realized_delta=100.0, unrealized_pnl=50.0, source="test")
    second = risk_service.update_pnl(mode="paper", equity=9800.0, realized_delta=-80.0, unrealized_pnl=-120.0, source="test")

    assert first["realized_pnl"] == pytest.approx(100.0)
    assert second["realized_pnl"] == pytest.approx(20.0)
    assert second["daily_pnl"] == pytest.approx(-200.0)


def test_drawdown_state_machine_transitions(risk_service: RiskGovernorService) -> None:
    risk_service.update_pnl(mode="paper", equity=10000.0, source="test")
    caution = risk_service.update_pnl(mode="paper", equity=9700.0, source="test")
    defense = risk_service.update_pnl(mode="paper", equity=9500.0, source="test")
    preservation = risk_service.update_pnl(mode="paper", equity=9300.0, source="test")

    assert caution["risk_state"] == "CAUTION"
    assert defense["risk_state"] == "DEFENSE"
    assert preservation["risk_state"] == "PRESERVATION"


def test_preservation_blocks_new_execution(risk_service: RiskGovernorService) -> None:
    risk_service.update_pnl(mode="live", equity=10000.0, source="test")
    risk_service.update_pnl(mode="live", equity=9300.0, source="test")

    can_execute, reason = risk_service.can_execute(mode="live", symbol="BTCUSDT")
    assert can_execute is False
    assert reason == "RISK_PRESERVATION_ACTIVE"


def test_hard_shutdown_activates_kill_switch(risk_service: RiskGovernorService) -> None:
    risk_service.update_pnl(mode="live", equity=10000.0, source="test")
    result = risk_service.update_pnl(mode="live", equity=8500.0, source="test")

    assert result["risk_state"] == "SHUTDOWN"
    assert result["shutdown_active"] is True

    status = kill_switch_manager.status()
    assert status["global_active"] is True


def test_restart_safe_persistence_restores_state(risk_service: RiskGovernorService) -> None:
    risk_service.update_pnl(mode="live", equity=10000.0, source="test")
    risk_service.update_pnl(mode="live", equity=9200.0, source="test")

    restarted = RiskGovernorService(session_factory=risk_service._session_factory, config=risk_service.config)
    status = restarted.get_status(mode="live")

    assert status["current_equity"] == pytest.approx(9200.0)
    assert status["risk_state"] in {"PRESERVATION", "DEFENSE", "CAUTION"}


def test_daily_loss_limit_triggers_shutdown(risk_service: RiskGovernorService) -> None:
    strict = RiskGovernorService(
        session_factory=risk_service._session_factory,
        config=RiskGovernorConfig(
            caution_drawdown_pct=50.0,
            defense_drawdown_pct=60.0,
            preservation_drawdown_pct=70.0,
            hard_shutdown_drawdown_pct=80.0,
            daily_loss_limit_pct=2.0,
            session_loss_limit_pct=3.0,
            auto_shutdown_activates_kill_switch=False,
            preservation_blocks_new_trades=True,
            session_bucket_hours=24,
        ),
    )

    strict.update_pnl(mode="paper", equity=10000.0, source="test")
    result = strict.update_pnl(mode="paper", equity=9600.0, source="test")

    assert result["risk_state"] == "SHUTDOWN"
    assert result["trigger_reason"] in {"daily_loss_limit", "session_loss_limit"}


def test_alerts_emitted_on_shutdown_events(risk_service: RiskGovernorService, monkeypatch: pytest.MonkeyPatch) -> None:
    emitted: List[Dict[str, Any]] = []

    def _capture(event):
        emitted.append({"kind": event.kind, "level": event.level})

    monkeypatch.setattr(runtime_monitor.alerts, "send", _capture, raising=True)

    risk_service.update_pnl(mode="live", equity=10000.0, source="test")
    risk_service.update_pnl(mode="live", equity=8500.0, source="test")

    kinds = {item["kind"] for item in emitted}
    assert "risk_shutdown_triggered" in kinds
    assert "drawdown_threshold_breached" in kinds


def test_risk_governor_persists_events(risk_service: RiskGovernorService) -> None:
    risk_service.update_pnl(mode="live", equity=10000.0, source="test")
    risk_service.update_pnl(mode="live", equity=9300.0, source="test")

    db = risk_service._session_factory()
    try:
        assert db.query(PnLSnapshot).count() >= 2
        assert db.query(DrawdownEvent).count() >= 1
        assert db.query(RiskShutdownEvent).count() >= 1
    finally:
        db.close()
