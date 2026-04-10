"""
Post-migration schema verification for AURA.
Run after 'alembic upgrade head' or 'alembic stamp' to verify
the database matches expectations.

Usage:
    DATABASE_URL=postgresql://... python scripts/verify_schema.py

Checks:
  1. alembic_version table exists and has a revision
  2. All 19 Alembic-managed tables exist
  3. Required columns exist on each table
  4. Required indexes exist
  5. FK constraints are in place
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine, text, inspect


def verify():
    database_url = os.getenv("DATABASE_URL", "")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    if not database_url:
        print("SKIP: DATABASE_URL not set — cannot verify live schema")
        return True

    engine = create_engine(database_url)
    inspector = inspect(engine)
    errors = []
    warnings = []

    # ── 1. Alembic version check ──
    with engine.connect() as conn:
        try:
            result = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
            row = result.fetchone()
            if row:
                print(f"  alembic_version: {row[0]}")
            else:
                errors.append("alembic_version table exists but is EMPTY — run 'alembic stamp <revision>'")
        except Exception:
            errors.append("alembic_version table does NOT exist — run 'alembic stamp 000_baseline' first")

    # ── 2. Table existence ──
    existing_tables = set(inspector.get_table_names())

    REQUIRED_TABLES = {
        "user_profiles",
        "user_autopilot_settings",
        "autopilot_mode_change_log",
        "persistent_strategy_registry",
        "strategy_health_snapshots",
        "strategy_allocations",
        "ai_decision_events",
        "ai_decision_reason_codes",
        "ai_decision_counterfactuals",
        "persistent_risk_events",
        "persistent_feed_events",
        "feed_event_reads",
        "portfolio_state_snapshots",
        "portfolio_symbol_exposures",
        "portfolio_cluster_exposures",
        "persistent_simulation_runs",
        "simulation_results",
        "simulation_result_timeseries",
        "audit_events",
    }

    missing_tables = REQUIRED_TABLES - existing_tables
    if missing_tables:
        errors.append(f"Missing tables: {sorted(missing_tables)}")
    else:
        print(f"  Tables: all {len(REQUIRED_TABLES)} present")

    # ── 3. Key column checks ──
    COLUMN_CHECKS = {
        "user_profiles": ["user_id", "risk_profile", "investment_objective", "preferred_mode", "notes_json"],
        "ai_decision_events": ["user_id", "symbol", "action", "confidence_score", "narrative_summary"],
        "ai_decision_reason_codes": ["decision_event_id", "code", "category"],
        "persistent_risk_events": ["related_decision_event_id", "event_type", "severity", "reason_code"],
        "persistent_feed_events": ["user_id", "source_type", "event_type", "dedupe_key", "expires_at"],
        "feed_event_reads": ["feed_event_id", "user_id", "read_at"],
        "audit_events": ["event_domain", "event_name", "entity_type", "entity_id", "severity"],
    }

    for table, required_cols in COLUMN_CHECKS.items():
        if table not in existing_tables:
            continue
        actual_cols = {c["name"] for c in inspector.get_columns(table)}
        missing_cols = set(required_cols) - actual_cols
        if missing_cols:
            errors.append(f"{table}: missing columns {sorted(missing_cols)}")

    if not any("missing columns" in e for e in errors):
        print(f"  Columns: spot-checked {sum(len(v) for v in COLUMN_CHECKS.values())} across {len(COLUMN_CHECKS)} tables")

    # ── 4. Index checks ──
    REQUIRED_INDEXES = {
        "ai_decision_events": ["ix_ai_decision_user_ts", "ix_ai_decision_symbol_ts"],
        "ai_decision_reason_codes": ["ix_ai_reason_code"],
        "persistent_risk_events": ["ix_prisk_user_ts", "ix_prisk_event_type"],
        "persistent_feed_events": ["ix_pfeed_user_ts", "ix_pfeed_dedupe"],
        "audit_events": ["ix_audit_user_ts", "ix_audit_domain_ts", "ix_audit_entity", "ix_audit_severity_ts"],
        "portfolio_state_snapshots": ["ix_pstate_user_ts"],
    }

    for table, required_idxs in REQUIRED_INDEXES.items():
        if table not in existing_tables:
            continue
        actual_idxs = {idx["name"] for idx in inspector.get_indexes(table)}
        missing_idxs = set(required_idxs) - actual_idxs
        if missing_idxs:
            warnings.append(f"{table}: missing indexes {sorted(missing_idxs)}")

    if not any("missing indexes" in w for w in warnings):
        print(f"  Indexes: spot-checked {sum(len(v) for v in REQUIRED_INDEXES.values())} across {len(REQUIRED_INDEXES)} tables")

    # ── 5. FK checks ──
    FK_CHECKS = {
        "ai_decision_reason_codes": "ai_decision_events",
        "ai_decision_counterfactuals": "ai_decision_events",
        "feed_event_reads": "persistent_feed_events",
        "portfolio_symbol_exposures": "portfolio_state_snapshots",
        "portfolio_cluster_exposures": "portfolio_state_snapshots",
        "simulation_results": "persistent_simulation_runs",
        "simulation_result_timeseries": "persistent_simulation_runs",
        "strategy_health_snapshots": "persistent_strategy_registry",
        "strategy_allocations": "persistent_strategy_registry",
    }

    for child, expected_parent in FK_CHECKS.items():
        if child not in existing_tables:
            continue
        fks = inspector.get_foreign_keys(child)
        fk_targets = {fk["referred_table"] for fk in fks}
        if expected_parent not in fk_targets:
            warnings.append(f"{child}: FK to {expected_parent} not found (found: {fk_targets or 'none'})")

    if not any("FK to" in w for w in warnings):
        print(f"  FKs: verified {len(FK_CHECKS)} parent-child relationships")

    # ── Report ──
    print()
    if errors:
        print(f"ERRORS ({len(errors)}):")
        for e in errors:
            print(f"  [ERROR] {e}")
    if warnings:
        print(f"WARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"  [WARN]  {w}")
    if not errors and not warnings:
        print("RESULT: ALL CHECKS PASSED")
        return True
    elif not errors:
        print("RESULT: PASSED with warnings")
        return True
    else:
        print("RESULT: FAILED — fix errors before proceeding")
        return False


if __name__ == "__main__":
    print("AURA Schema Verification")
    print("=" * 40)
    success = verify()
    sys.exit(0 if success else 1)
