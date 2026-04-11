"""add trade feedback table and model registry versioning

Revision ID: 013_trade_feedback_model_registry
Revises: 012_prediction_outcomes
Create Date: 2026-04-11
"""
from typing import Sequence, Union

from alembic import op

revision: str = "013_trade_feedback_model_registry"
down_revision: Union[str, None] = "012_prediction_outcomes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS trade_feedback (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR NOT NULL,
            action VARCHAR NOT NULL,
            confidence_at_entry FLOAT,
            entry_price FLOAT,
            exit_price FLOAT,
            pnl_pct FLOAT,
            outcome VARCHAR,
            features_snapshot JSONB,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_trade_feedback_symbol_created ON trade_feedback (symbol, created_at DESC)")

    op.execute("ALTER TABLE model_registry ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1")
    op.execute("ALTER TABLE model_registry ADD COLUMN IF NOT EXISTS improved_at TIMESTAMP")


def downgrade() -> None:
    # Brownfield-safe downgrade: intentionally non-destructive.
    pass
