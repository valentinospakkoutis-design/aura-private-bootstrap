"""add user_achievements table

Revision ID: 016_user_achievements
Revises: 015_morning_briefing_enabled
Create Date: 2026-04-12
"""
from typing import Sequence, Union

from alembic import op

revision: str = "016_user_achievements"
down_revision: Union[str, None] = "015_morning_briefing_enabled"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS user_achievements (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            achievement_id VARCHAR NOT NULL,
            earned_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(user_id, achievement_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_user_achievements_user_id ON user_achievements (user_id, earned_at DESC)"
    )


def downgrade() -> None:
    # Brownfield-safe downgrade: intentionally non-destructive.
    pass
