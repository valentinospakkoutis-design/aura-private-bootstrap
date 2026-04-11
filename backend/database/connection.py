"""
Database connection management
PostgreSQL with SQLAlchemy (async and sync)
"""

import os
from typing import AsyncGenerator, Generator
from sqlalchemy import create_engine, MetaData, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from contextlib import asynccontextmanager, contextmanager

# Database URL from environment (no default — skip DB if not configured)
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Railway gives postgres:// but SQLAlchemy requires postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Only create engines if DATABASE_URL is configured
if DATABASE_URL:
    # Async database URL
    ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

    # Sync engine
    sync_engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        echo=os.getenv("DB_ECHO", "false").lower() == "true"
    )

    # Async engine
    async_engine = create_async_engine(
        ASYNC_DATABASE_URL,
        pool_pre_ping=True,
        poolclass=NullPool,
        echo=os.getenv("DB_ECHO", "false").lower() == "true"
    )

    # Session makers
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)
    AsyncSessionLocal = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
else:
    ASYNC_DATABASE_URL = ""
    sync_engine = None
    async_engine = None
    SessionLocal = None
    AsyncSessionLocal = None
    print("[!] DATABASE_URL not set — running without database")


def get_db() -> Generator[Session, None, None]:
    """Dependency for getting sync database session"""
    if not SessionLocal:
        raise RuntimeError("Database not configured (DATABASE_URL not set)")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database session"""
    if not AsyncSessionLocal:
        raise RuntimeError("Database not configured (DATABASE_URL not set)")
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def _alembic_manages_schema() -> bool:
    """Check if Alembic is managing the schema (alembic_version table exists with a revision)."""
    if not sync_engine:
        return False
    try:
        with sync_engine.connect() as conn:
            result = conn.execute(text(
                "SELECT version_num FROM alembic_version LIMIT 1"
            ))
            row = result.fetchone()
            if row:
                print(f"[+] Alembic is managing schema (revision: {row[0]})")
                return True
    except Exception:
        pass  # Table doesn't exist — Alembic not yet bootstrapped
    return False


def init_db():
    """Initialize database - create all tables.

    If Alembic is managing the schema (alembic_version table exists),
    skip raw SQL table creation for Alembic-managed tables and only
    run legacy ALTER TABLE statements for pre-Alembic tables.
    Use 'alembic upgrade head' for schema changes going forward.
    """
    if not sync_engine:
        print("[!] Skipping DB init — no DATABASE_URL")
        return

    alembic_active = _alembic_manages_schema()

    from .models import Base
    Base.metadata.create_all(bind=sync_engine)
    # Add columns if missing (for existing rl_models tables)
    with sync_engine.connect() as conn:
        try:
            conn.execute(text(
                "ALTER TABLE rl_models ADD COLUMN IF NOT EXISTS model_data BYTEA"
            ))
            conn.execute(text(
                "ALTER TABLE rl_models ADD COLUMN IF NOT EXISTS metadata JSONB"
            ))
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 0"
            ))
            # Extend user_profiles with new personalization columns
            conn.execute(text(
                "ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS investment_objective TEXT DEFAULT 'balanced_growth'"
            ))
            conn.execute(text(
                "ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS preferred_mode TEXT DEFAULT 'manual_assist'"
            ))
            conn.execute(text(
                "ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS max_portfolio_exposure_override NUMERIC"
            ))
            conn.execute(text(
                "ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS max_position_size_override NUMERIC"
            ))
            conn.execute(text(
                "ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS notes_json JSONB DEFAULT '{}'"
            ))
            conn.execute(text(
                "ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS paper_balance FLOAT DEFAULT 10000.0"
            ))
            conn.execute(text(
                "ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS paper_positions JSONB DEFAULT '[]'"
            ))
            conn.execute(text(
                "ALTER TABLE broker_credentials ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)"
            ))
            conn.execute(text(
                "ALTER TABLE broker_credentials DROP CONSTRAINT IF EXISTS broker_credentials_broker_name_key"
            ))
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_broker_credentials_user_broker ON broker_credentials (user_id, broker_name)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_broker_credentials_user_id ON broker_credentials (user_id)"
            ))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS auth_audit_logs (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER,
                    event_type TEXT NOT NULL,
                    event_status TEXT NOT NULL,
                    ip_address TEXT,
                    user_agent TEXT,
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS user_2fa_settings (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER UNIQUE NOT NULL,
                    secret_encrypted TEXT NOT NULL,
                    is_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                    recovery_codes_json JSONB,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS live_order_audit_logs (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER,
                    source TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity NUMERIC NOT NULL,
                    price NUMERIC,
                    trading_mode TEXT NOT NULL,
                    client_order_id TEXT,
                    broker TEXT NOT NULL,
                    status TEXT NOT NULL,
                    broker_order_id TEXT,
                    response_summary JSONB,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS push_tokens (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER,
                    token TEXT UNIQUE NOT NULL,
                    platform TEXT DEFAULT 'android',
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS circuit_breaker_events (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    rule_id VARCHAR NOT NULL,
                    reason VARCHAR NOT NULL,
                    tripped_at TIMESTAMP DEFAULT NOW(),
                    resume_at TIMESTAMP NOT NULL,
                    reset_manually BOOLEAN DEFAULT FALSE
                )
            """))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_circuit_breaker_events_user_id ON circuit_breaker_events (user_id)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_circuit_breaker_events_tripped_at ON circuit_breaker_events (tripped_at DESC)"
            ))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS prediction_outcomes (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR NOT NULL,
                    action VARCHAR NOT NULL,
                    confidence FLOAT NOT NULL,
                    price_at_prediction FLOAT NOT NULL,
                    price_7d_later FLOAT,
                    price_30d_later FLOAT,
                    was_correct_7d BOOLEAN,
                    was_correct_30d BOOLEAN,
                    pnl_7d_pct FLOAT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    evaluated_at TIMESTAMP
                )
            """))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_prediction_outcomes_symbol ON prediction_outcomes (symbol)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_prediction_outcomes_created_at ON prediction_outcomes (created_at DESC)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_prediction_outcomes_eval_7d ON prediction_outcomes (was_correct_7d, created_at)"
            ))
            # ── Alembic-managed tables ──
            # When Alembic is active (alembic_version table has a revision),
            # skip raw SQL table creation — Alembic owns these tables.
            # Use 'alembic upgrade head' for schema changes going forward.
            if alembic_active:
                conn.commit()
                print("[+] Alembic manages schema — skipped raw SQL for 19 managed tables")
                print("[+] Database tables created (legacy only)")
                return

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER UNIQUE NOT NULL,
                    risk_profile TEXT NOT NULL DEFAULT 'moderate',
                    objective TEXT DEFAULT 'growth',
                    confidence_threshold_override NUMERIC,
                    max_position_override NUMERIC,
                    behavior_flags JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS user_autopilot_settings (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER UNIQUE NOT NULL,
                    current_mode TEXT NOT NULL DEFAULT 'balanced',
                    is_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                    config_overrides_json JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS autopilot_mode_change_log (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    previous_mode TEXT,
                    new_mode TEXT NOT NULL,
                    reason TEXT,
                    changed_by TEXT NOT NULL DEFAULT 'user',
                    metadata_json JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_autopilot_settings_user ON user_autopilot_settings (user_id)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_autopilot_change_user_ts ON autopilot_mode_change_log (user_id, created_at DESC)"
            ))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS feed_events (
                    id SERIAL PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    symbol TEXT,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    severity TEXT DEFAULT 'info',
                    reason_codes TEXT[],
                    metadata JSONB DEFAULT '{}',
                    dedup_key TEXT UNIQUE,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_feed_events_created ON feed_events (created_at DESC)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_feed_events_type ON feed_events (event_type)"
            ))
            # AI decision explainability tables
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS ai_decision_events (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER,
                    symbol TEXT NOT NULL,
                    action TEXT NOT NULL,
                    confidence_score NUMERIC,
                    confidence_band TEXT,
                    market_regime TEXT,
                    narrative_summary TEXT,
                    machine_summary TEXT,
                    stop_loss_logic TEXT,
                    take_profit_logic TEXT,
                    expected_holding_profile TEXT,
                    raw_signal_payload_json JSONB DEFAULT '{}',
                    audit_metadata_json JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS ai_decision_reason_codes (
                    id SERIAL PRIMARY KEY,
                    decision_event_id INTEGER NOT NULL REFERENCES ai_decision_events(id),
                    code TEXT NOT NULL,
                    category TEXT NOT NULL,
                    detail_text TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS ai_decision_counterfactuals (
                    id SERIAL PRIMARY KEY,
                    decision_event_id INTEGER NOT NULL REFERENCES ai_decision_events(id),
                    counterfactual_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_ai_decision_user_ts ON ai_decision_events (user_id, created_at DESC)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_ai_decision_symbol_ts ON ai_decision_events (symbol, created_at DESC)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_ai_reason_code ON ai_decision_reason_codes (code)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_ai_reason_event ON ai_decision_reason_codes (decision_event_id)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_ai_cf_event ON ai_decision_counterfactuals (decision_event_id)"
            ))
            # Persistent risk events table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS persistent_risk_events (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER,
                    symbol TEXT,
                    related_decision_event_id INTEGER REFERENCES ai_decision_events(id),
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL DEFAULT 'warning',
                    reason_code TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    details_json JSONB DEFAULT '{}',
                    original_requested_notional NUMERIC,
                    adjusted_notional NUMERIC,
                    original_requested_quantity NUMERIC,
                    adjusted_quantity NUMERIC,
                    portfolio_risk_score NUMERIC,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_prisk_user_ts ON persistent_risk_events (user_id, created_at DESC)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_prisk_symbol_ts ON persistent_risk_events (symbol, created_at DESC)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_prisk_event_type ON persistent_risk_events (event_type)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_prisk_decision_event ON persistent_risk_events (related_decision_event_id)"
            ))
            # Persistent feed events (user-facing AI feed / timeline)
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS persistent_feed_events (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER,
                    source_type TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    priority TEXT NOT NULL DEFAULT 'medium',
                    title TEXT NOT NULL,
                    short_summary TEXT NOT NULL,
                    full_explanation TEXT,
                    related_symbol TEXT,
                    confidence_score NUMERIC,
                    risk_level TEXT,
                    action_suggestion TEXT,
                    source_reference_type TEXT,
                    source_reference_id INTEGER,
                    dedupe_key TEXT UNIQUE,
                    expires_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS feed_event_reads (
                    id SERIAL PRIMARY KEY,
                    feed_event_id INTEGER NOT NULL REFERENCES persistent_feed_events(id),
                    user_id INTEGER NOT NULL,
                    read_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE (feed_event_id, user_id)
                )
            """))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_pfeed_user_ts ON persistent_feed_events (user_id, created_at DESC)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_pfeed_user_type_ts ON persistent_feed_events (user_id, event_type, created_at DESC)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_pfeed_dedupe ON persistent_feed_events (dedupe_key)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_feed_read_user_ts ON feed_event_reads (user_id, read_at DESC)"
            ))
            # Portfolio state & exposure history tables
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS portfolio_state_snapshots (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    snapshot_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
                    total_equity NUMERIC NOT NULL,
                    available_cash NUMERIC NOT NULL,
                    total_exposure NUMERIC NOT NULL,
                    net_exposure NUMERIC NOT NULL,
                    gross_exposure NUMERIC NOT NULL,
                    drawdown_pct NUMERIC,
                    concentration_score NUMERIC,
                    diversification_score NUMERIC,
                    risk_score NUMERIC,
                    metadata_json JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS portfolio_symbol_exposures (
                    id SERIAL PRIMARY KEY,
                    portfolio_snapshot_id INTEGER NOT NULL REFERENCES portfolio_state_snapshots(id),
                    symbol TEXT NOT NULL,
                    asset_class TEXT,
                    direction TEXT NOT NULL DEFAULT 'long',
                    quantity NUMERIC NOT NULL,
                    market_value NUMERIC NOT NULL,
                    exposure_pct NUMERIC NOT NULL,
                    unrealized_pnl NUMERIC,
                    metadata_json JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS portfolio_cluster_exposures (
                    id SERIAL PRIMARY KEY,
                    portfolio_snapshot_id INTEGER NOT NULL REFERENCES portfolio_state_snapshots(id),
                    cluster_name TEXT NOT NULL,
                    gross_exposure NUMERIC NOT NULL,
                    net_exposure NUMERIC NOT NULL,
                    exposure_pct NUMERIC NOT NULL,
                    risk_weight NUMERIC,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_pstate_user_ts ON portfolio_state_snapshots (user_id, snapshot_timestamp DESC)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_psymexp_snapshot ON portfolio_symbol_exposures (portfolio_snapshot_id)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_psymexp_symbol ON portfolio_symbol_exposures (symbol)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_pclusexp_snapshot ON portfolio_cluster_exposures (portfolio_snapshot_id)"
            ))
            # Simulation & backtesting persistence tables
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS persistent_simulation_runs (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    strategy_id TEXT,
                    run_type TEXT NOT NULL DEFAULT 'backtest',
                    symbol_universe_json JSONB NOT NULL,
                    timeframe_start TIMESTAMP,
                    timeframe_end TIMESTAMP,
                    initial_capital NUMERIC NOT NULL,
                    config_json JSONB NOT NULL,
                    assumptions_json JSONB DEFAULT '{}',
                    disclaimer_text TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS simulation_results (
                    id SERIAL PRIMARY KEY,
                    simulation_run_id INTEGER NOT NULL REFERENCES persistent_simulation_runs(id),
                    total_return_pct NUMERIC,
                    annualized_return_pct NUMERIC,
                    max_drawdown_pct NUMERIC,
                    sharpe_ratio NUMERIC,
                    win_rate_pct NUMERIC,
                    total_trades INTEGER,
                    avg_trade_return_pct NUMERIC,
                    pnl_value NUMERIC,
                    risk_metrics_json JSONB DEFAULT '{}',
                    summary_text TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS simulation_result_timeseries (
                    id SERIAL PRIMARY KEY,
                    simulation_run_id INTEGER NOT NULL REFERENCES persistent_simulation_runs(id),
                    point_timestamp TIMESTAMP NOT NULL,
                    equity_value NUMERIC NOT NULL,
                    drawdown_pct NUMERIC,
                    exposure_pct NUMERIC,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_psim_user_ts ON persistent_simulation_runs (user_id, created_at DESC)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_psim_status ON persistent_simulation_runs (status)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_simresult_run ON simulation_results (simulation_run_id)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_simts_run_ts ON simulation_result_timeseries (simulation_run_id, point_timestamp)"
            ))
            # Strategy platform tables
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS persistent_strategy_registry (
                    id SERIAL PRIMARY KEY,
                    strategy_key TEXT UNIQUE NOT NULL,
                    display_name TEXT NOT NULL,
                    description TEXT,
                    asset_scope TEXT,
                    holding_style TEXT,
                    risk_class TEXT,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    version TEXT DEFAULT '1.0',
                    config_schema_json JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS strategy_health_snapshots (
                    id SERIAL PRIMARY KEY,
                    strategy_id INTEGER NOT NULL REFERENCES persistent_strategy_registry(id),
                    snapshot_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
                    health_score NUMERIC NOT NULL,
                    recent_return_pct NUMERIC,
                    recent_drawdown_pct NUMERIC,
                    win_rate_pct NUMERIC,
                    volatility_score NUMERIC,
                    stability_score NUMERIC,
                    metadata_json JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS strategy_allocations (
                    id SERIAL PRIMARY KEY,
                    strategy_id INTEGER NOT NULL REFERENCES persistent_strategy_registry(id),
                    user_id INTEGER,
                    allocation_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
                    target_allocation_pct NUMERIC NOT NULL,
                    actual_allocation_pct NUMERIC,
                    reason_summary TEXT,
                    metadata_json JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_strathsnap_strat_ts ON strategy_health_snapshots (strategy_id, snapshot_timestamp DESC)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_stratalloc_strat_ts ON strategy_allocations (strategy_id, allocation_timestamp DESC)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_stratalloc_user_ts ON strategy_allocations (user_id, allocation_timestamp DESC)"
            ))
            # Unified audit trail
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS audit_events (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER,
                    event_domain TEXT NOT NULL,
                    event_name TEXT NOT NULL,
                    entity_type TEXT,
                    entity_id INTEGER,
                    severity TEXT NOT NULL DEFAULT 'info',
                    summary TEXT NOT NULL,
                    payload_json JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_audit_user_ts ON audit_events (user_id, created_at DESC)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_audit_domain_ts ON audit_events (event_domain, created_at DESC)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_events (entity_type, entity_id)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_audit_severity_ts ON audit_events (severity, created_at DESC)"
            ))
            conn.commit()
        except Exception as e:
            print(f"[!] Could not add columns (may already exist): {e}")
    print("[+] Database tables created")


async def init_async_db():
    """Initialize database asynchronously"""
    if not async_engine:
        print("[!] Skipping async DB init — no DATABASE_URL")
        return
    from .models import Base
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[+] Database tables created (async)")


def close_db():
    """Close database connections"""
    if sync_engine:
        sync_engine.dispose()
        print("[+] Database connections closed")


async def close_async_db():
    """Close async database connections"""
    if async_engine:
        await async_engine.dispose()
        print("[+] Async database connections closed")


def check_db_connection() -> bool:
    """Check if database connection is working"""
    if not sync_engine:
        print("[!] No DATABASE_URL configured — skipping DB check")
        return False
    try:
        from sqlalchemy import text
        with sync_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"[-] Database connection error: {e}")
        return False
