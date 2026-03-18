from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

pytestmark = pytest.mark.unit


@pytest.fixture
def sqlite_db_url(tmp_path: Path) -> str:
    db_file = tmp_path / "exec_migration_test.db"
    return f"sqlite:///{db_file.as_posix()}"


def _alembic_config(database_url: str) -> Config:
    backend_root = Path(__file__).resolve().parents[2]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_migration_creates_execution_tables(sqlite_db_url: str) -> None:
    config = _alembic_config(sqlite_db_url)
    command.upgrade(config, "head")

    engine = create_engine(sqlite_db_url)
    inspector = inspect(engine)
    try:
        tables = set(inspector.get_table_names())
        assert "execution_orders" in tables
        assert "execution_order_audit" in tables
        assert "pnl_snapshots" in tables
        assert "drawdown_events" in tables
        assert "risk_shutdown_events" in tables

        order_columns = {column["name"] for column in inspector.get_columns("execution_orders")}
        for required in {
            "internal_order_id",
            "idempotency_key",
            "broker_order_id",
            "symbol",
            "side",
            "quantity",
            "price",
            "status",
            "request_fingerprint",
            "created_at",
            "updated_at",
            "error_reason",
        }:
            assert required in order_columns

        pnl_columns = {column["name"] for column in inspector.get_columns("pnl_snapshots")}
        for required in {
            "timestamp",
            "mode",
            "equity",
            "realized_pnl",
            "unrealized_pnl",
            "drawdown_pct",
            "risk_state",
            "shutdown_active",
        }:
            assert required in pnl_columns
    finally:
        engine.dispose()


def test_migration_enforces_idempotency_uniqueness(sqlite_db_url: str) -> None:
    config = _alembic_config(sqlite_db_url)
    command.upgrade(config, "head")

    engine = create_engine(sqlite_db_url)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO execution_orders (
                        internal_order_id, idempotency_key, request_fingerprint, broker, broker_order_id,
                        symbol, side, quantity, price, filled_quantity, avg_fill_price, status,
                        error_reason, created_at, updated_at
                    ) VALUES (
                        'AURA-1', 'dup-key', 'fp1', 'binance', 'b1',
                        'BTCUSDT', 'BUY', 0.1, 1000.0, 0.0, NULL, 'PENDING',
                        NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    """
                )
            )

            with pytest.raises(Exception):
                conn.execute(
                    text(
                        """
                        INSERT INTO execution_orders (
                            internal_order_id, idempotency_key, request_fingerprint, broker, broker_order_id,
                            symbol, side, quantity, price, filled_quantity, avg_fill_price, status,
                            error_reason, created_at, updated_at
                        ) VALUES (
                            'AURA-2', 'dup-key', 'fp2', 'binance', 'b2',
                            'BTCUSDT', 'BUY', 0.1, 1000.0, 0.0, NULL, 'PENDING',
                            NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                        )
                        """
                    )
                )
    finally:
        engine.dispose()
