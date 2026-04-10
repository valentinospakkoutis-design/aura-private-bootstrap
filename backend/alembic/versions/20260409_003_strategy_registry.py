"""strategy registry (mutable) + health snapshots + allocations (append-only)

Revision ID: 003_strategy
Revises: 002_autopilot
Create Date: 2026-04-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003_strategy"
down_revision: Union[str, None] = "002_autopilot"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Parent table — mutable registry
    op.execute("""
        CREATE TABLE IF NOT EXISTS persistent_strategy_registry (
            id SERIAL PRIMARY KEY,
            strategy_key VARCHAR(40) UNIQUE NOT NULL,
            display_name VARCHAR(100) NOT NULL,
            description TEXT,
            asset_scope VARCHAR(30),
            holding_style VARCHAR(30),
            risk_class VARCHAR(20),
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            version VARCHAR(20) DEFAULT '1.0',
            config_schema_json JSONB DEFAULT '{}',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_strategy_registry_key ON persistent_strategy_registry (strategy_key)")

    # Child — append-only health snapshots
    op.execute("""
        CREATE TABLE IF NOT EXISTS strategy_health_snapshots (
            id SERIAL PRIMARY KEY,
            strategy_id INTEGER NOT NULL REFERENCES persistent_strategy_registry(id),
            snapshot_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
            health_score FLOAT NOT NULL,
            recent_return_pct FLOAT,
            recent_drawdown_pct FLOAT,
            win_rate_pct FLOAT,
            volatility_score FLOAT,
            stability_score FLOAT,
            metadata_json JSONB DEFAULT '{}',
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_strathsnap_strat_ts ON strategy_health_snapshots (strategy_id, snapshot_timestamp DESC)")

    # Child — append-only allocations
    op.execute("""
        CREATE TABLE IF NOT EXISTS strategy_allocations (
            id SERIAL PRIMARY KEY,
            strategy_id INTEGER NOT NULL REFERENCES persistent_strategy_registry(id),
            user_id INTEGER,
            allocation_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
            target_allocation_pct FLOAT NOT NULL,
            actual_allocation_pct FLOAT,
            reason_summary TEXT,
            metadata_json JSONB DEFAULT '{}',
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_stratalloc_strat_ts ON strategy_allocations (strategy_id, allocation_timestamp DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_stratalloc_user_ts ON strategy_allocations (user_id, allocation_timestamp DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS strategy_allocations")
    op.execute("DROP TABLE IF EXISTS strategy_health_snapshots")
    op.execute("DROP TABLE IF EXISTS persistent_strategy_registry")
