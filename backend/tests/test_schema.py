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
    UserAutopilotSettings, AutopilotModeChangeLog,
    AIDecisionEvent, AIDecisionReasonCode, AIDecisionCounterfactual,
    PersistentRiskEvent, PersistentFeedEvent, FeedEventRead,
    PortfolioStateSnapshot, PortfolioSymbolExposure, PortfolioClusterExposure,
    PersistentSimulationRun, SimulationResult, SimulationResultTimeseries,
    PersistentStrategyRegistry, StrategyHealthSnapshot, StrategyAllocation,
    AuditEvent,
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


def test_user_autopilot_settings_model():
    """UserAutopilotSettings should have mode, enabled, and overrides."""
    cols = {c.name for c in UserAutopilotSettings.__table__.columns}
    required = {"id", "user_id", "current_mode", "is_enabled",
                "config_overrides_json", "created_at", "updated_at"}
    assert required.issubset(cols), f"Missing: {required - cols}"
    print(f"PASS: UserAutopilotSettings | {len(cols)} columns")


def test_autopilot_mode_change_log_model():
    """AutopilotModeChangeLog should have previous/new mode, reason, changed_by."""
    cols = {c.name for c in AutopilotModeChangeLog.__table__.columns}
    required = {"id", "user_id", "previous_mode", "new_mode", "reason",
                "changed_by", "metadata_json", "created_at"}
    assert required.issubset(cols), f"Missing: {required - cols}"
    # Append-only: no updated_at
    assert "updated_at" not in cols, "Change log should be append-only (no updated_at)"
    print(f"PASS: AutopilotModeChangeLog | {len(cols)} columns (append-only)")


def test_ai_decision_event_model():
    """AIDecisionEvent should have core decision fields."""
    cols = {c.name for c in AIDecisionEvent.__table__.columns}
    required = {"id", "user_id", "symbol", "action", "confidence_score",
                "confidence_band", "market_regime", "narrative_summary",
                "machine_summary", "stop_loss_logic", "take_profit_logic",
                "expected_holding_profile", "raw_signal_payload_json",
                "audit_metadata_json", "created_at"}
    assert required.issubset(cols), f"Missing: {required - cols}"
    assert "updated_at" not in cols, "Events should be append-only"
    print(f"PASS: AIDecisionEvent | {len(cols)} columns (append-only)")


def test_ai_decision_reason_code_model():
    """AIDecisionReasonCode should have FK, code, category — relational, not JSON."""
    cols = {c.name for c in AIDecisionReasonCode.__table__.columns}
    required = {"id", "decision_event_id", "code", "category", "detail_text", "created_at"}
    assert required.issubset(cols), f"Missing: {required - cols}"
    assert "updated_at" not in cols, "Reason codes should be append-only"
    # Verify FK exists
    fks = {fk.column.table.name for col in AIDecisionReasonCode.__table__.columns for fk in col.foreign_keys}
    assert "ai_decision_events" in fks, "Should have FK to ai_decision_events"
    print(f"PASS: AIDecisionReasonCode | {len(cols)} columns, FK to ai_decision_events")


def test_ai_decision_counterfactual_model():
    """AIDecisionCounterfactual should have FK, type, content."""
    cols = {c.name for c in AIDecisionCounterfactual.__table__.columns}
    required = {"id", "decision_event_id", "counterfactual_type", "content", "created_at"}
    assert required.issubset(cols), f"Missing: {required - cols}"
    assert "updated_at" not in cols, "Counterfactuals should be append-only"
    fks = {fk.column.table.name for col in AIDecisionCounterfactual.__table__.columns for fk in col.foreign_keys}
    assert "ai_decision_events" in fks, "Should have FK to ai_decision_events"
    print(f"PASS: AIDecisionCounterfactual | {len(cols)} columns, FK to ai_decision_events")


def test_ai_decision_relationships():
    """AIDecisionEvent should have relationships to reason codes and counterfactuals."""
    rels = {r.key for r in AIDecisionEvent.__mapper__.relationships}
    assert "reason_codes_rel" in rels, "Missing reason_codes_rel relationship"
    assert "counterfactuals_rel" in rels, "Missing counterfactuals_rel relationship"
    print("PASS: AIDecisionEvent relationships defined")


def test_persistent_risk_event_model():
    """PersistentRiskEvent should have full risk intervention fields."""
    cols = {c.name for c in PersistentRiskEvent.__table__.columns}
    required = {"id", "user_id", "symbol", "related_decision_event_id",
                "event_type", "severity", "reason_code", "summary",
                "details_json", "original_requested_notional", "adjusted_notional",
                "original_requested_quantity", "adjusted_quantity",
                "portfolio_risk_score", "created_at"}
    assert required.issubset(cols), f"Missing: {required - cols}"
    assert "updated_at" not in cols, "Risk events should be append-only"
    # Verify FK to ai_decision_events
    fks = {fk.column.table.name for col in PersistentRiskEvent.__table__.columns for fk in col.foreign_keys}
    assert "ai_decision_events" in fks, "Should have FK to ai_decision_events"
    print(f"PASS: PersistentRiskEvent | {len(cols)} columns, FK to ai_decision_events (append-only)")


def test_persistent_feed_event_model():
    """PersistentFeedEvent should have full feed fields with dedupe and expiry."""
    cols = {c.name for c in PersistentFeedEvent.__table__.columns}
    required = {"id", "user_id", "source_type", "event_type", "priority",
                "title", "short_summary", "full_explanation",
                "related_symbol", "confidence_score", "risk_level",
                "action_suggestion", "source_reference_type", "source_reference_id",
                "dedupe_key", "expires_at", "created_at"}
    assert required.issubset(cols), f"Missing: {required - cols}"
    assert "updated_at" not in cols, "Feed events should be append-only"
    print(f"PASS: PersistentFeedEvent | {len(cols)} columns (append-only)")


def test_feed_event_read_model():
    """FeedEventRead should have FK, user_id, read_at with unique constraint."""
    cols = {c.name for c in FeedEventRead.__table__.columns}
    required = {"id", "feed_event_id", "user_id", "read_at"}
    assert required.issubset(cols), f"Missing: {required - cols}"
    assert "updated_at" not in cols, "Read receipts should be append-only"
    # Verify FK
    fks = {fk.column.table.name for col in FeedEventRead.__table__.columns for fk in col.foreign_keys}
    assert "persistent_feed_events" in fks, "Should have FK to persistent_feed_events"
    # Verify unique constraint
    constraints = {c.name for c in FeedEventRead.__table__.constraints if hasattr(c, 'name') and c.name}
    assert "uq_feed_read_event_user" in constraints, "Should have unique constraint on (feed_event_id, user_id)"
    print(f"PASS: FeedEventRead | {len(cols)} columns, FK + unique constraint")


def test_feed_event_relationships():
    """PersistentFeedEvent should have relationship to reads."""
    rels = {r.key for r in PersistentFeedEvent.__mapper__.relationships}
    assert "reads" in rels, "Missing reads relationship"
    print("PASS: PersistentFeedEvent.reads relationship defined")


def test_portfolio_state_snapshot_model():
    """PortfolioStateSnapshot should have equity, exposure, and risk fields."""
    cols = {c.name for c in PortfolioStateSnapshot.__table__.columns}
    required = {"id", "user_id", "snapshot_timestamp", "total_equity",
                "available_cash", "total_exposure", "net_exposure",
                "gross_exposure", "drawdown_pct", "concentration_score",
                "diversification_score", "risk_score", "metadata_json", "created_at"}
    assert required.issubset(cols), f"Missing: {required - cols}"
    assert "updated_at" not in cols, "Snapshots should be append-only"
    print(f"PASS: PortfolioStateSnapshot | {len(cols)} columns (append-only)")


def test_portfolio_symbol_exposure_model():
    """PortfolioSymbolExposure should have FK, symbol, direction, value."""
    cols = {c.name for c in PortfolioSymbolExposure.__table__.columns}
    required = {"id", "portfolio_snapshot_id", "symbol", "asset_class",
                "direction", "quantity", "market_value", "exposure_pct",
                "unrealized_pnl", "metadata_json", "created_at"}
    assert required.issubset(cols), f"Missing: {required - cols}"
    assert "updated_at" not in cols
    fks = {fk.column.table.name for col in PortfolioSymbolExposure.__table__.columns for fk in col.foreign_keys}
    assert "portfolio_state_snapshots" in fks
    print(f"PASS: PortfolioSymbolExposure | {len(cols)} columns, FK to snapshots")


def test_portfolio_cluster_exposure_model():
    """PortfolioClusterExposure should have FK, cluster_name, exposures."""
    cols = {c.name for c in PortfolioClusterExposure.__table__.columns}
    required = {"id", "portfolio_snapshot_id", "cluster_name",
                "gross_exposure", "net_exposure", "exposure_pct",
                "risk_weight", "created_at"}
    assert required.issubset(cols), f"Missing: {required - cols}"
    assert "updated_at" not in cols
    fks = {fk.column.table.name for col in PortfolioClusterExposure.__table__.columns for fk in col.foreign_keys}
    assert "portfolio_state_snapshots" in fks
    print(f"PASS: PortfolioClusterExposure | {len(cols)} columns, FK to snapshots")


def test_portfolio_state_relationships():
    """PortfolioStateSnapshot should have relationships to symbol and cluster exposures."""
    rels = {r.key for r in PortfolioStateSnapshot.__mapper__.relationships}
    assert "symbol_exposures" in rels, "Missing symbol_exposures relationship"
    assert "cluster_exposures" in rels, "Missing cluster_exposures relationship"
    print("PASS: PortfolioStateSnapshot relationships defined")


def test_persistent_simulation_run_model():
    """PersistentSimulationRun should have config, status, and reproducibility fields."""
    cols = {c.name for c in PersistentSimulationRun.__table__.columns}
    required = {"id", "user_id", "strategy_id", "run_type", "symbol_universe_json",
                "timeframe_start", "timeframe_end", "initial_capital",
                "config_json", "assumptions_json", "disclaimer_text",
                "status", "started_at", "completed_at", "created_at"}
    assert required.issubset(cols), f"Missing: {required - cols}"
    assert "updated_at" not in cols
    print(f"PASS: PersistentSimulationRun | {len(cols)} columns (append-only)")


def test_simulation_result_model():
    """SimulationResult should have FK and all metric fields."""
    cols = {c.name for c in SimulationResult.__table__.columns}
    required = {"id", "simulation_run_id", "total_return_pct", "annualized_return_pct",
                "max_drawdown_pct", "sharpe_ratio", "win_rate_pct", "total_trades",
                "avg_trade_return_pct", "pnl_value", "risk_metrics_json",
                "summary_text", "created_at"}
    assert required.issubset(cols), f"Missing: {required - cols}"
    assert "updated_at" not in cols
    fks = {fk.column.table.name for col in SimulationResult.__table__.columns for fk in col.foreign_keys}
    assert "persistent_simulation_runs" in fks
    print(f"PASS: SimulationResult | {len(cols)} columns, FK to runs")


def test_simulation_result_timeseries_model():
    """SimulationResultTimeseries should have FK, timestamp, equity."""
    cols = {c.name for c in SimulationResultTimeseries.__table__.columns}
    required = {"id", "simulation_run_id", "point_timestamp", "equity_value",
                "drawdown_pct", "exposure_pct", "created_at"}
    assert required.issubset(cols), f"Missing: {required - cols}"
    assert "updated_at" not in cols
    fks = {fk.column.table.name for col in SimulationResultTimeseries.__table__.columns for fk in col.foreign_keys}
    assert "persistent_simulation_runs" in fks
    print(f"PASS: SimulationResultTimeseries | {len(cols)} columns, FK to runs")


def test_simulation_relationships():
    """PersistentSimulationRun should have relationships to results and timeseries."""
    rels = {r.key for r in PersistentSimulationRun.__mapper__.relationships}
    assert "results" in rels, "Missing results relationship"
    assert "timeseries" in rels, "Missing timeseries relationship"
    print("PASS: PersistentSimulationRun relationships defined")


def test_persistent_strategy_registry_model():
    """PersistentStrategyRegistry should have key, scope, risk_class, and updated_at (mutable)."""
    cols = {c.name for c in PersistentStrategyRegistry.__table__.columns}
    required = {"id", "strategy_key", "display_name", "description",
                "asset_scope", "holding_style", "risk_class", "is_active",
                "version", "config_schema_json", "created_at", "updated_at"}
    assert required.issubset(cols), f"Missing: {required - cols}"
    assert "updated_at" in cols, "Registry is mutable — should have updated_at"
    print(f"PASS: PersistentStrategyRegistry | {len(cols)} columns (mutable)")


def test_strategy_health_snapshot_model():
    """StrategyHealthSnapshot should have FK, scores, and no updated_at."""
    cols = {c.name for c in StrategyHealthSnapshot.__table__.columns}
    required = {"id", "strategy_id", "snapshot_timestamp", "health_score",
                "recent_return_pct", "recent_drawdown_pct", "win_rate_pct",
                "volatility_score", "stability_score", "metadata_json", "created_at"}
    assert required.issubset(cols), f"Missing: {required - cols}"
    assert "updated_at" not in cols, "Health snapshots should be append-only"
    fks = {fk.column.table.name for col in StrategyHealthSnapshot.__table__.columns for fk in col.foreign_keys}
    assert "persistent_strategy_registry" in fks
    print(f"PASS: StrategyHealthSnapshot | {len(cols)} columns, FK to registry (append-only)")


def test_strategy_allocation_model():
    """StrategyAllocation should have FK, user_id, target/actual pct."""
    cols = {c.name for c in StrategyAllocation.__table__.columns}
    required = {"id", "strategy_id", "user_id", "allocation_timestamp",
                "target_allocation_pct", "actual_allocation_pct",
                "reason_summary", "metadata_json", "created_at"}
    assert required.issubset(cols), f"Missing: {required - cols}"
    assert "updated_at" not in cols, "Allocations should be append-only"
    fks = {fk.column.table.name for col in StrategyAllocation.__table__.columns for fk in col.foreign_keys}
    assert "persistent_strategy_registry" in fks
    print(f"PASS: StrategyAllocation | {len(cols)} columns, FK to registry (append-only)")


def test_strategy_registry_relationships():
    """PersistentStrategyRegistry should have relationships to health and allocations."""
    rels = {r.key for r in PersistentStrategyRegistry.__mapper__.relationships}
    assert "health_snapshots" in rels
    assert "allocations" in rels
    print("PASS: PersistentStrategyRegistry relationships defined")


def test_strategy_key_unique():
    """strategy_key should have a unique constraint."""
    cols_with_unique = {c.name for c in PersistentStrategyRegistry.__table__.columns if c.unique}
    assert "strategy_key" in cols_with_unique, "strategy_key should be unique"
    print("PASS: strategy_key unique constraint")


def test_audit_event_model():
    """AuditEvent should have domain, severity, entity reference, and no updated_at."""
    cols = {c.name for c in AuditEvent.__table__.columns}
    required = {"id", "user_id", "event_domain", "event_name",
                "entity_type", "entity_id", "severity", "summary",
                "payload_json", "created_at"}
    assert required.issubset(cols), f"Missing: {required - cols}"
    assert "updated_at" not in cols, "Audit events should be append-only"
    print(f"PASS: AuditEvent | {len(cols)} columns (append-only)")


def test_audit_event_indexes():
    """AuditEvent should have 4 composite indexes."""
    indexes = {idx.name for idx in AuditEvent.__table__.indexes}
    assert "ix_audit_user_ts" in indexes
    assert "ix_audit_domain_ts" in indexes
    assert "ix_audit_entity" in indexes
    assert "ix_audit_severity_ts" in indexes
    print("PASS: AuditEvent indexes defined (4 composite)")


def test_all_tables_in_metadata():
    """All new tables should be in SQLAlchemy metadata."""
    table_names = set(Base.metadata.tables.keys())
    new_tables = {"decision_audit", "autopilot_configs", "portfolio_snapshots",
                  "simulation_runs", "strategy_health", "risk_events",
                  "user_autopilot_settings", "autopilot_mode_change_log",
                  "ai_decision_events", "ai_decision_reason_codes",
                  "ai_decision_counterfactuals", "persistent_risk_events",
                  "persistent_feed_events", "feed_event_reads",
                  "portfolio_state_snapshots", "portfolio_symbol_exposures",
                  "portfolio_cluster_exposures",
                  "persistent_simulation_runs", "simulation_results",
                  "simulation_result_timeseries",
                  "persistent_strategy_registry", "strategy_health_snapshots",
                  "strategy_allocations", "audit_events"}
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

    mcl_indexes = {idx.name for idx in AutopilotModeChangeLog.__table__.indexes}
    assert "ix_autopilot_change_user_ts" in mcl_indexes

    ade_indexes = {idx.name for idx in AIDecisionEvent.__table__.indexes}
    assert "ix_ai_decision_user_ts" in ade_indexes
    assert "ix_ai_decision_symbol_ts" in ade_indexes

    arc_indexes = {idx.name for idx in AIDecisionReasonCode.__table__.indexes}
    assert "ix_ai_reason_code" in arc_indexes

    pre_indexes = {idx.name for idx in PersistentRiskEvent.__table__.indexes}
    assert "ix_prisk_user_ts" in pre_indexes
    assert "ix_prisk_symbol_ts" in pre_indexes
    assert "ix_prisk_event_type" in pre_indexes
    assert "ix_prisk_decision_event" in pre_indexes

    pfe_indexes = {idx.name for idx in PersistentFeedEvent.__table__.indexes}
    assert "ix_pfeed_user_ts" in pfe_indexes
    assert "ix_pfeed_user_type_ts" in pfe_indexes
    assert "ix_pfeed_dedupe" in pfe_indexes

    fer_indexes = {idx.name for idx in FeedEventRead.__table__.indexes}
    assert "ix_feed_read_user_ts" in fer_indexes

    pss_indexes = {idx.name for idx in PortfolioStateSnapshot.__table__.indexes}
    assert "ix_pstate_user_ts" in pss_indexes

    pse_indexes = {idx.name for idx in PortfolioSymbolExposure.__table__.indexes}
    assert "ix_psymexp_snapshot" in pse_indexes
    assert "ix_psymexp_symbol" in pse_indexes

    pce_indexes = {idx.name for idx in PortfolioClusterExposure.__table__.indexes}
    assert "ix_pclusexp_snapshot" in pce_indexes

    psr_indexes = {idx.name for idx in PersistentSimulationRun.__table__.indexes}
    assert "ix_psim_user_ts" in psr_indexes
    assert "ix_psim_status" in psr_indexes

    sres_indexes = {idx.name for idx in SimulationResult.__table__.indexes}
    assert "ix_simresult_run" in sres_indexes

    sts_indexes = {idx.name for idx in SimulationResultTimeseries.__table__.indexes}
    assert "ix_simts_run_ts" in sts_indexes

    shs_indexes = {idx.name for idx in StrategyHealthSnapshot.__table__.indexes}
    assert "ix_strathsnap_strat_ts" in shs_indexes

    sa_indexes = {idx.name for idx in StrategyAllocation.__table__.indexes}
    assert "ix_stratalloc_strat_ts" in sa_indexes
    assert "ix_stratalloc_user_ts" in sa_indexes
    print("PASS: all composite indexes defined")


def test_append_only_tables_have_no_updated_at():
    """Append-only tables should NOT have updated_at (immutable logs)."""
    for model in [DecisionAudit, PortfolioSnapshot, SimulationRun, StrategyHealth, RiskEvent,
                   AutopilotModeChangeLog, AIDecisionEvent, AIDecisionReasonCode, AIDecisionCounterfactual,
                   PersistentRiskEvent, PersistentFeedEvent, FeedEventRead,
                   PortfolioStateSnapshot, PortfolioSymbolExposure, PortfolioClusterExposure,
                   PersistentSimulationRun, SimulationResult, SimulationResultTimeseries,
                   StrategyHealthSnapshot, StrategyAllocation, AuditEvent]:
        cols = {c.name for c in model.__table__.columns}
        assert "updated_at" not in cols, f"{model.__tablename__} should be append-only (no updated_at)"
    print("PASS: append-only tables confirmed (no updated_at)")


def test_mutable_tables_have_updated_at():
    """Mutable config tables should have updated_at."""
    for model in [AutopilotConfig, UserAutopilotSettings, PersistentStrategyRegistry]:
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
    test_ai_decision_event_model()
    test_ai_decision_reason_code_model()
    test_ai_decision_counterfactual_model()
    test_ai_decision_relationships()
    test_persistent_risk_event_model()
    test_persistent_feed_event_model()
    test_feed_event_read_model()
    test_feed_event_relationships()
    test_portfolio_state_snapshot_model()
    test_portfolio_symbol_exposure_model()
    test_portfolio_cluster_exposure_model()
    test_portfolio_state_relationships()
    test_persistent_simulation_run_model()
    test_simulation_result_model()
    test_simulation_result_timeseries_model()
    test_simulation_relationships()
    test_persistent_strategy_registry_model()
    test_strategy_health_snapshot_model()
    test_strategy_allocation_model()
    test_strategy_registry_relationships()
    test_strategy_key_unique()
    test_audit_event_model()
    test_audit_event_indexes()
    test_all_tables_in_metadata()
    test_user_autopilot_settings_model()
    test_autopilot_mode_change_log_model()
    test_indexes_defined()
    test_append_only_tables_have_no_updated_at()
    test_mutable_tables_have_updated_at()
    print(f"\nAll 35 tests passed!")
