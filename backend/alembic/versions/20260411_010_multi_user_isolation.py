"""multi-user isolation for brokers and paper trading profile state

Revision ID: 010_multi_user_isolation
Revises: 009_audit
Create Date: 2026-04-11
"""
from typing import Sequence, Union

from alembic import op

revision: str = "010_multi_user_isolation"
down_revision: Union[str, None] = "009_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Broker credentials -> per user (keep legacy NULL user_id rows for seed user fallback)
    op.execute("ALTER TABLE broker_credentials ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)")

    # Remove legacy uniqueness on broker_name and replace with per-user uniqueness.
    op.execute("ALTER TABLE broker_credentials DROP CONSTRAINT IF EXISTS broker_credentials_broker_name_key")
    op.execute("DROP INDEX IF EXISTS ix_broker_credentials_broker_name")
    op.execute("CREATE INDEX IF NOT EXISTS ix_broker_credentials_broker_name ON broker_credentials (broker_name)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_broker_credentials_user_id ON broker_credentials (user_id)")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_broker_credentials_user_broker "
        "ON broker_credentials (user_id, broker_name)"
    )

    # Paper trading profile state -> per user
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS paper_balance FLOAT DEFAULT 10000.0")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS paper_positions JSONB DEFAULT '[]'")


def downgrade() -> None:
    # Brownfield-safe downgrade: intentionally non-destructive.
    pass
