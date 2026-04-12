"""add leaderboard snapshots and referrals

Revision ID: 020_social_features
Revises: 019_onchain_history
Create Date: 2026-04-12
"""
from typing import Sequence, Union

from alembic import op

revision: str = "020_social_features"
down_revision: Union[str, None] = "019_onchain_history"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS leaderboard_snapshots (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            display_name VARCHAR NOT NULL,
            paper_pnl_pct FLOAT DEFAULT 0,
            paper_trades INTEGER DEFAULT 0,
            win_rate FLOAT DEFAULT 0,
            period VARCHAR NOT NULL,
            snapshot_date DATE DEFAULT CURRENT_DATE,
            UNIQUE(user_id, period, snapshot_date)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS referrals (
            id SERIAL PRIMARY KEY,
            referrer_id INTEGER REFERENCES users(id),
            referred_id INTEGER REFERENCES users(id),
            referral_code VARCHAR UNIQUE NOT NULL,
            reward_given BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """
    )

    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_code VARCHAR UNIQUE")

    op.execute(
        """
        UPDATE users
        SET referral_code = UPPER(SUBSTRING(MD5(id::text), 1, 8))
        WHERE referral_code IS NULL
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_leaderboard_period_date
        ON leaderboard_snapshots (period, snapshot_date DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_referrals_referrer
        ON referrals (referrer_id, created_at DESC)
        """
    )


def downgrade() -> None:
    # Brownfield-safe downgrade: intentionally non-destructive.
    pass
