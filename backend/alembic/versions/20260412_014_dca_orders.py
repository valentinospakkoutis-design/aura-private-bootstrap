"""add dca orders table

Revision ID: 014_dca_orders
Revises: 013_trade_feedback_model_registry
Create Date: 2026-04-12
"""
from typing import Sequence, Union

from alembic import op

revision: str = "014_dca_orders"
down_revision: Union[str, None] = "013_trade_feedback_model_registry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS dca_orders (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            symbol VARCHAR NOT NULL,
            target_price FLOAT NOT NULL,
            size_usd FLOAT NOT NULL,
            status VARCHAR DEFAULT 'pending',
            executed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_dca_orders_user_status ON dca_orders (user_id, status, created_at DESC)")


def downgrade() -> None:
    # Brownfield-safe downgrade: intentionally non-destructive.
    pass
