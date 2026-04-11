"""add prediction outcomes table

Revision ID: 012_prediction_outcomes
Revises: 011_circuit_breaker_events
Create Date: 2026-04-11
"""
from typing import Sequence, Union

from alembic import op

revision: str = "012_prediction_outcomes"
down_revision: Union[str, None] = "011_circuit_breaker_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS prediction_outcomes (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR NOT NULL,
            action VARCHAR NOT NULL,
            confidence FLOAT NOT NULL,
            price_at_prediction FLOAT NOT NULL,
            price_7d_later FLOAT,
            price_30d_later FLOAT,
            was_correct_7d BOOLEAN,
            was_correct_30d BOOLEAN,
            pnl_7d_pct FLOAT,
            created_at TIMESTAMP DEFAULT NOW(),
            evaluated_at TIMESTAMP
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_prediction_outcomes_symbol ON prediction_outcomes (symbol)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_prediction_outcomes_created_at ON prediction_outcomes (created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_prediction_outcomes_eval_7d ON prediction_outcomes (was_correct_7d, created_at)")


def downgrade() -> None:
    # Brownfield-safe downgrade: intentionally non-destructive.
    pass
