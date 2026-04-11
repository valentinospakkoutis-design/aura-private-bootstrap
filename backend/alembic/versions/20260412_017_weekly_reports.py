"""add weekly_reports table

Revision ID: 017_weekly_reports
Revises: 016_user_achievements
Create Date: 2026-04-12
"""
from typing import Sequence, Union

from alembic import op

revision: str = "017_weekly_reports"
down_revision: Union[str, None] = "016_user_achievements"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS weekly_reports (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            week_start DATE NOT NULL,
            pnl_pct FLOAT,
            total_trades INTEGER,
            win_rate FLOAT,
            best_trade VARCHAR,
            worst_trade VARCHAR,
            ai_accuracy FLOAT,
            report_text TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_weekly_reports_user_week ON weekly_reports (user_id, week_start DESC)"
    )


def downgrade() -> None:
    # Brownfield-safe downgrade: intentionally non-destructive.
    pass
