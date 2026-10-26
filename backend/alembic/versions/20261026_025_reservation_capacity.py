"""Add worst_case_total_usd, worst_case_notional_usd, min_filled_qty to execution_reservations.

F21-active: worst_case_total_usd and worst_case_notional_usd store per-reservation
worst-case cost at reservation time so the active-reservation SQL aggregation uses
worst-case figures rather than raw notional+fee.

F22-persist: min_filled_qty persists the step-aligned completeness threshold across
sessions so settle_reservation() can load it from DB instead of relying on a
transient Python attribute (_min_filled_qty) that was lost on session reload.

Revision ID: 025_reservation_capacity
Revises:     024_execution_reservations
Create Date: 2026-10-26

NOTE: revision ID shortened to 24 chars (≤ Alembic's default VARCHAR(32) version_num
column).  The previous draft used '025_reservation_worst_case_and_min_qty' (38 chars)
which would truncate or error on PostgreSQL with the default alembic_version schema.
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision      = '025_reservation_capacity'
down_revision = '024_execution_reservations'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    with op.batch_alter_table('execution_reservations') as batch:
        # F21-active: worst-case cash cost (notional × 1.05 + fee on that notional).
        batch.add_column(sa.Column(
            'worst_case_total_usd',
            sa.Numeric(20, 8),
            nullable=True,
        ))
        # F21-active: worst-case notional only (no fee), used for symbol/portfolio
        # exposure checks which do not include fees.
        batch.add_column(sa.Column(
            'worst_case_notional_usd',
            sa.Numeric(20, 8),
            nullable=True,
        ))
        # F22-persist: step-aligned 97 % completeness threshold.
        batch.add_column(sa.Column(
            'min_filled_qty',
            sa.Numeric(20, 8),
            nullable=True,
        ))


def downgrade() -> None:
    with op.batch_alter_table('execution_reservations') as batch:
        batch.drop_column('min_filled_qty')
        batch.drop_column('worst_case_notional_usd')
        batch.drop_column('worst_case_total_usd')
