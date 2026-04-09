"""
Tests for the next-gen database schema models.
Validates all new models are importable and have correct structure.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.models import (
    Base, User, DecisionAudit, AutopilotConfig,
    PortfolioSnapshot, SimulationRun, StrategyHealth, RiskEvent,
)


def test_decision_audit_model():
    """DecisionAudit should have all explainability fields."""
    cols = {c.name for c in DecisionAudit.__table__.columns}
    required = {"id", "user_id", "symbol", "action", "confidence_score",
                "confidence_band", "market_regime", "reason_codes",
                "blocked_by", "sizing_adjustments", "improvement_triggers",
                "narrative_summary", "machine_summary", "smart_score",
                "trend_score", "using_ml_model", "risk_profile",
                "sizing_decision", "sizing_notional", "portfolio_risk_score",
                "source", "created_at"}
    assert required.issubset(cols), f"Missing: {required - cols}"
    print(f"PASS: DecisionAudit | {len(cols)} columns")


def test_autopilot_config_model():
    """AutopilotConfig should have mode and thresholds."""
    cols = {c.name for c in AutopilotConfig.__table__.columns}
    required = {"id", "user_id", "mode", "confidence_threshold",
                "smart_score_threshold", "max_positions", "stop_loss_pct",
                "take_profit_pct", "is_enabled"}
    assert required.issubset(cols)
    print(f"PASS: AutopilotConfig | {len(cols)} columns")


def test_portfolio_snapshot_model():
    """PortfolioSnapshot should have exposure and risk fields."""
    cols = {c.name for c in PortfolioSnapshot.__table__.columns}
    required = {"id", "user_id", "total_value_usd", "exposure_by_class",
                "exposure_by_symbol", "portfolio_risk_score", "snapshot_at"}
    assert required.issubset(cols)
    print(f"PASS: PortfolioSnapshot | {len(cols)} columns")


def test_simulation_run_model():
    """SimulationRun should have strategy, PnL, and reproducibility fields."""
    cols = {c.name for c in SimulationRun.__table__.columns}
    required = {"id", "user_id", "strategy", "symbols", "initial_capital",
                "final_capital", "pnl", "sharpe_ratio", "config_json",
                "trades_json", "created_at"}
    assert required.issubset(cols)
    print(f"PASS: SimulationRun | {len(cols)} columns")


def test_strategy_health_model():
    """StrategyHealth should track per-strategy performance."""
    cols = {c.name for c in StrategyHealth.__table__.columns}
    required = {"id", "strategy_name", "symbol", "score",
                "signal_action", "signal_confidence", "recorded_at"}
    assert required.issubset(cols)
    print(f"PASS: StrategyHealth | {len(cols)} columns")


def test_risk_event_model():
    """RiskEvent should log blocks, reductions, alerts."""
    cols = {c.name for c in RiskEvent.__table__.columns}
    required = {"id", "user_id", "symbol", "event_type", "reason_codes",
                "explanation", "source", "severity", "created_at"}
    assert required.issubset(cols)
    print(f"PASS: RiskEvent | {len(cols)} columns")


def test_all_tables_in_metadata():
    """All new tables should be in SQLAlchemy metadata."""
    table_names = set(Base.metadata.tables.keys())
    new_tables = {"decision_audit", "autopilot_configs", "portfolio_snapshots",
                  "simulation_runs", "strategy_health", "risk_events"}
    assert new_tables.issubset(table_names), f"Missing: {new_tables - table_names}"
    print(f"PASS: all {len(new_tables)} new tables in metadata | total: {len(table_names)} tables")


def test_indexes_defined():
    """Key indexes should be defined."""
    da_indexes = {idx.name for idx in DecisionAudit.__table__.indexes}
    assert "ix_decision_audit_symbol_ts" in da_indexes
    assert "ix_decision_audit_user" in da_indexes

    ps_indexes = {idx.name for idx in PortfolioSnapshot.__table__.indexes}
    assert "ix_portfolio_snap_user_ts" in ps_indexes

    sr_indexes = {idx.name for idx in SimulationRun.__table__.indexes}
    assert "ix_sim_run_user_ts" in sr_indexes

    sh_indexes = {idx.name for idx in StrategyHealth.__table__.indexes}
    assert "ix_strat_health_name_ts" in sh_indexes

    re_indexes = {idx.name for idx in RiskEvent.__table__.indexes}
    assert "ix_risk_event_symbol_ts" in re_indexes
    print("PASS: all composite indexes defined")


def test_append_only_tables_have_no_updated_at():
    """Append-only tables should NOT have updated_at (immutable logs)."""
    for model in [DecisionAudit, PortfolioSnapshot, SimulationRun, StrategyHealth, RiskEvent]:
        cols = {c.name for c in model.__table__.columns}
        assert "updated_at" not in cols, f"{model.__tablename__} should be append-only (no updated_at)"
    print("PASS: append-only tables confirmed (no updated_at)")


def test_mutable_tables_have_updated_at():
    """Mutable config tables should have updated_at."""
    for model in [AutopilotConfig]:
        cols = {c.name for c in model.__table__.columns}
        assert "updated_at" in cols, f"{model.__tablename__} should have updated_at"
    print("PASS: mutable tables have updated_at")


if __name__ == "__main__":
    test_decision_audit_model()
    test_autopilot_config_model()
    test_portfolio_snapshot_model()
    test_simulation_run_model()
    test_strategy_health_model()
    test_risk_event_model()
    test_all_tables_in_metadata()
    test_indexes_defined()
    test_append_only_tables_have_no_updated_at()
    test_mutable_tables_have_updated_at()
    print(f"\nAll 10 tests passed!")
