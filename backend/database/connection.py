"""
Database connection management
PostgreSQL with SQLAlchemy (async and sync)
"""

import os
from typing import AsyncGenerator, Generator
from sqlalchemy import create_engine, MetaData
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
