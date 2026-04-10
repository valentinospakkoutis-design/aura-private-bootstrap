"""portfolio state snapshots + symbol/cluster exposures (all append-only)

Revision ID: 007_portfolio
Revises: 006_feed
Create Date: 2026-04-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007_portfolio"
down_revision: Union[str, None] = "006_feed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Parent — append-only snapshots
    op.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_state_snapshots (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            snapshot_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
            total_equity NUMERIC NOT NULL,
            available_cash NUMERIC NOT NULL,
            total_exposure NUMERIC NOT NULL,
            net_exposure NUMERIC NOT NULL,
            gross_exposure NUMERIC NOT NULL,
            drawdown_pct FLOAT,
            concentration_score FLOAT,
            diversification_score FLOAT,
            risk_score FLOAT,
            metadata_json JSONB DEFAULT '{}',
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_pstate_user_ts ON portfolio_state_snapshots (user_id, snapshot_timestamp DESC)")

    # Child — per-symbol exposure
    op.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_symbol_exposures (
            id SERIAL PRIMARY KEY,
            portfolio_snapshot_id INTEGER NOT NULL REFERENCES portfolio_state_snapshots(id),
            symbol VARCHAR(20) NOT NULL,
            asset_class VARCHAR(30),
            direction VARCHAR(10) NOT NULL DEFAULT 'long',
            quantity NUMERIC NOT NULL,
            market_value NUMERIC NOT NULL,
            exposure_pct FLOAT NOT NULL,
            unrealized_pnl NUMERIC,
            metadata_json JSONB DEFAULT '{}',
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_psymexp_snapshot ON portfolio_symbol_exposures (portfolio_snapshot_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_psymexp_symbol ON portfolio_symbol_exposures (symbol)")

    # Child — per-cluster exposure
    op.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_cluster_exposures (
            id SERIAL PRIMARY KEY,
            portfolio_snapshot_id INTEGER NOT NULL REFERENCES portfolio_state_snapshots(id),
            cluster_name VARCHAR(40) NOT NULL,
            gross_exposure NUMERIC NOT NULL,
            net_exposure NUMERIC NOT NULL,
            exposure_pct FLOAT NOT NULL,
            risk_weight FLOAT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_pclusexp_snapshot ON portfolio_cluster_exposures (portfolio_snapshot_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS portfolio_cluster_exposures")
    op.execute("DROP TABLE IF EXISTS portfolio_symbol_exposures")
    op.execute("DROP TABLE IF EXISTS portfolio_state_snapshots")
