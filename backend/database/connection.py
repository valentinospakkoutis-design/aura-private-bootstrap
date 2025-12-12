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

# Database URL from environment or default
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/aura_db"
)

# Async database URL (replace postgresql:// with postgresql+asyncpg://)
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
    poolclass=NullPool,  # Use NullPool for async
    echo=os.getenv("DB_ECHO", "false").lower() == "true"
)

# Session makers
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for getting sync database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting async database session
    """
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
    """
    Initialize database - create all tables
    """
    from .models import Base
    Base.metadata.create_all(bind=sync_engine)
    print("[+] Database tables created")


async def init_async_db():
    """
    Initialize database asynchronously
    """
    from .models import Base
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[+] Database tables created (async)")


def close_db():
    """
    Close database connections
    """
    sync_engine.dispose()
    print("[+] Database connections closed")


async def close_async_db():
    """
    Close async database connections
    """
    await async_engine.dispose()
    print("[+] Async database connections closed")


# Health check
def check_db_connection() -> bool:
    """
    Check if database connection is working
    """
    try:
        from sqlalchemy import text
        with sync_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"[-] Database connection error: {e}")
        return False

