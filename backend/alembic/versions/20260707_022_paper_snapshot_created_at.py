"""add created_at (+ backing indexes) to paper_strategy_snapshots

The table is provisioned by Base.metadata.create_all, which never alters an
existing table. Deployments whose table predates the created_at column drifted:
the A/B recorder's INSERT names created_at (model has a Python-side
default=datetime.utcnow) and fails with "column created_at does not exist".

This backfills the drifted schema. Every statement is IF NOT EXISTS, so columns
that already exist are left untouched — created_at and its two composite indexes
are the only pieces actually missing on the affected deployments.

Revision ID: 022_paper_snapshot_created_at
Revises: 021_raw_sql_to_sqlalchemy
Create Date: 2026-07-07
"""
from typing import Sequence, Union

from alembic import op

revision: str = "022_paper_snapshot_created_at"
down_revision: Union[str, None] = "021_raw_sql_to_sqlalchemy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The column that is actually missing on drifted deployments.
    op.execute(
        "ALTER TABLE paper_strategy_snapshots "
        "ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()"
    )

    # Defensive: ensure the rest of the recorder's insert columns exist too.
    # No-ops where already present (matches migration 021's idempotent style).
    op.execute("ALTER TABLE paper_strategy_snapshots ADD COLUMN IF NOT EXISTS user_id INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE paper_strategy_snapshots ADD COLUMN IF NOT EXISTS threshold DOUBLE PRECISION")
    op.execute("ALTER TABLE paper_strategy_snapshots ADD COLUMN IF NOT EXISTS equity DOUBLE PRECISION NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE paper_strategy_snapshots ADD COLUMN IF NOT EXISTS cash DOUBLE PRECISION NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE paper_strategy_snapshots ADD COLUMN IF NOT EXISTS floating_pnl DOUBLE PRECISION NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE paper_strategy_snapshots ADD COLUMN IF NOT EXISTS realized_pnl DOUBLE PRECISION NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE paper_strategy_snapshots ADD COLUMN IF NOT EXISTS total_pnl DOUBLE PRECISION NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE paper_strategy_snapshots ADD COLUMN IF NOT EXISTS n_open INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE paper_strategy_snapshots ADD COLUMN IF NOT EXISTS n_closed INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE paper_strategy_snapshots ADD COLUMN IF NOT EXISTS wins INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE paper_strategy_snapshots ADD COLUMN IF NOT EXISTS losses INTEGER NOT NULL DEFAULT 0")

    # Composite indexes the model declares; both reference created_at, so they
    # could not have been created on the drifted table either.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_paper_snap_user_ts "
        "ON paper_strategy_snapshots (user_id, created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_paper_snap_threshold_ts "
        "ON paper_strategy_snapshots (threshold, created_at)"
    )


def downgrade() -> None:
    pass
