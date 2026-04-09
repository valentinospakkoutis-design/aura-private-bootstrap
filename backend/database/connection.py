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


def init_db():
    """Initialize database - create all tables"""
    if not sync_engine:
        print("[!] Skipping DB init — no DATABASE_URL")
        return
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
