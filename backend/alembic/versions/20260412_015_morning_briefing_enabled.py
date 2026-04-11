"""add morning_briefing_enabled to user_profiles

Revision ID: 015_morning_briefing_enabled
Revises: 014_dca_orders
Create Date: 2026-04-12
"""
from typing import Sequence, Union

from alembic import op

revision: str = "015_morning_briefing_enabled"
down_revision: Union[str, None] = "014_dca_orders"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS morning_briefing_enabled BOOLEAN DEFAULT TRUE"
    )


def downgrade() -> None:
    # Brownfield-safe downgrade: intentionally non-destructive.
    pass
