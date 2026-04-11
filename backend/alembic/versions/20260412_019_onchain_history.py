"""add onchain history persistence and weekly report metadata

Revision ID: 019_onchain_history
Revises: 018_subscriptions
Create Date: 2026-04-12
"""
from typing import Sequence, Union

from alembic import op

revision: str = "019_onchain_history"
down_revision: Union[str, None] = "018_subscriptions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS onchain_signal_history (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(20) NOT NULL,
            futures_symbol VARCHAR(20) NOT NULL,
            onchain_score FLOAT NOT NULL,
            onchain_sentiment VARCHAR(12) NOT NULL,
            funding_rate FLOAT,
            open_interest FLOAT,
            long_short_ratio FLOAT,
            fear_greed INTEGER,
            funding_bearish BOOLEAN DEFAULT FALSE,
            extreme_fear BOOLEAN DEFAULT FALSE,
            extreme_greed BOOLEAN DEFAULT FALSE,
            overleveraged_longs BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_onchain_history_symbol_ts ON onchain_signal_history (symbol, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_onchain_history_sentiment_ts ON onchain_signal_history (onchain_sentiment, created_at DESC)"
    )
    op.execute(
        "ALTER TABLE weekly_reports ADD COLUMN IF NOT EXISTS onchain_summary_json JSONB"
    )


def downgrade() -> None:
    # Brownfield-safe downgrade: intentionally non-destructive.
    pass