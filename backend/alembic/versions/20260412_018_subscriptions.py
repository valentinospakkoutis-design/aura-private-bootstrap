"""add subscriptions and prediction usage

Revision ID: 018_subscriptions
Revises: 017_weekly_reports
Create Date: 2026-04-12
"""
from typing import Sequence, Union

from alembic import op

revision: str = "018_subscriptions"
down_revision: Union[str, None] = "017_weekly_reports"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS subscriptions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER UNIQUE NOT NULL REFERENCES users(id),
            tier VARCHAR(20) NOT NULL DEFAULT 'free',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            started_at TIMESTAMP DEFAULT NOW(),
            expires_at TIMESTAMP,
            payment_provider VARCHAR(40),
            provider_subscription_id VARCHAR(120),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_subscriptions_user_id ON subscriptions (user_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS prediction_usage (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            usage_date DATE NOT NULL,
            predictions_requested INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(user_id, usage_date)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_prediction_usage_user_date ON prediction_usage (user_id, usage_date DESC)"
    )

    op.execute(
        """
        INSERT INTO subscriptions (user_id, tier, is_active)
        SELECT id, 'free', TRUE FROM users
        ON CONFLICT (user_id) DO NOTHING
        """
    )


def downgrade() -> None:
    # Brownfield-safe downgrade: intentionally non-destructive.
    pass
