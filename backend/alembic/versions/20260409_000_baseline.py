"""baseline — represents the pre-Alembic database state

This is a NO-OP migration. It exists so that production databases
created by init_db() / create_all() can be stamped to a known
revision without executing any DDL.

BROWNFIELD BOOTSTRAP PROCEDURE:
  1. On production (tables already exist):
     $ alembic stamp 000_baseline
     This records "000_baseline" in alembic_version without running DDL.

  2. Then apply new migrations:
     $ alembic upgrade head
     This runs 001 through 009, all of which use IF NOT EXISTS guards.

  3. On a fresh database (no tables):
     $ alembic upgrade head
     This runs 000 (no-op) then 001-009 (creates everything).

Revision ID: 000_baseline
Revises: None
Create Date: 2026-04-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "000_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No-op: this revision represents the pre-Alembic state.
    # Tables were created by init_db() / Base.metadata.create_all().
    pass


def downgrade() -> None:
    # No-op: cannot undo "the database existed before Alembic"
    pass
