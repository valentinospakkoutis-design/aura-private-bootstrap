"""simulation runs + results + timeseries (all append-only)

Revision ID: 008_simulation
Revises: 007_portfolio
Create Date: 2026-04-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "008_simulation"
down_revision: Union[str, None] = "007_portfolio"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Parent — append-only simulation runs
    op.execute("""
        CREATE TABLE IF NOT EXISTS persistent_simulation_runs (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            strategy_id VARCHAR(30),
            run_type VARCHAR(20) NOT NULL DEFAULT 'backtest',
            symbol_universe_json JSONB NOT NULL,
            timeframe_start TIMESTAMP,
            timeframe_end TIMESTAMP,
            initial_capital NUMERIC NOT NULL,
            config_json JSONB NOT NULL,
            assumptions_json JSONB DEFAULT '{}',
            disclaimer_text TEXT NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'queued',
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_psim_user_ts ON persistent_simulation_runs (user_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_psim_status ON persistent_simulation_runs (status)")

    # Child — results summary
    op.execute("""
        CREATE TABLE IF NOT EXISTS simulation_results (
            id SERIAL PRIMARY KEY,
            simulation_run_id INTEGER NOT NULL REFERENCES persistent_simulation_runs(id),
            total_return_pct FLOAT,
            annualized_return_pct FLOAT,
            max_drawdown_pct FLOAT,
            sharpe_ratio FLOAT,
            win_rate_pct FLOAT,
            total_trades INTEGER,
            avg_trade_return_pct FLOAT,
            pnl_value NUMERIC,
            risk_metrics_json JSONB DEFAULT '{}',
            summary_text TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_simresult_run ON simulation_results (simulation_run_id)")

    # Child — equity curve timeseries
    op.execute("""
        CREATE TABLE IF NOT EXISTS simulation_result_timeseries (
            id SERIAL PRIMARY KEY,
            simulation_run_id INTEGER NOT NULL REFERENCES persistent_simulation_runs(id),
            point_timestamp TIMESTAMP NOT NULL,
            equity_value NUMERIC NOT NULL,
            drawdown_pct FLOAT,
            exposure_pct FLOAT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_simts_run_ts ON simulation_result_timeseries (simulation_run_id, point_timestamp)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS simulation_result_timeseries")
    op.execute("DROP TABLE IF EXISTS simulation_results")
    op.execute("DROP TABLE IF EXISTS persistent_simulation_runs")
