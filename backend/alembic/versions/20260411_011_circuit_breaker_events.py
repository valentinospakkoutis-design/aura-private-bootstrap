"""add circuit breaker events table

Revision ID: 011_circuit_breaker_events
Revises: 010_multi_user_isolation
Create Date: 2026-04-11
"""
from typing import Sequence, Union

from alembic import op

revision: str = "011_circuit_breaker_events"
down_revision: Union[str, None] = "010_multi_user_isolation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS circuit_breaker_events (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            rule_id VARCHAR NOT NULL,
            reason VARCHAR NOT NULL,
            tripped_at TIMESTAMP DEFAULT NOW(),
            resume_at TIMESTAMP NOT NULL,
            reset_manually BOOLEAN DEFAULT FALSE
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_circuit_breaker_events_user_id ON circuit_breaker_events (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_circuit_breaker_events_tripped_at ON circuit_breaker_events (tripped_at DESC)")


def downgrade() -> None:
    # Brownfield-safe downgrade: intentionally non-destructive.
    pass
