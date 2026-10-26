"""Backfill stale min_filled_qty values to the safe full-fill default.

Background
----------
Reservations created with the v8/v9/v10 formula may have min_filled_qty set to
a value strictly less than reserved_qty when qty_step is a factor of reserved_qty
(integer ratio).  For example:

    reserved_qty=34, qty_step=1
    v8:  min = max(floor(0.97×34/1)×1, 34−1) = max(32, 33) = 33   ← stale
    v9:  three-way clamp → 33                                        ← stale
    v10: floor(34/1)×1 = 34                                         ← correct

With v12's settle_reservation() logic, a stored min_filled_qty=33 still allows
fill=33 to close as 'filled', bypassing the strict remainder < step rule.

This migration fixes active (non-terminal) reservations by setting min_filled_qty
to reserved_qty (the safe full-fill default) wherever the stored value is less than
reserved_qty.

    UPDATE execution_reservations
       SET min_filled_qty = quantity
     WHERE status NOT IN ('filled','rejected','cancelled','cancelled_partial')
       AND min_filled_qty IS NOT NULL
       AND min_filled_qty < quantity;

Note: the column holding the reserved amount is named `quantity` in the
execution_reservations table (not `reserved_qty`, which is a Python-side alias).

Terminal rows (filled/rejected/cancelled/cancelled_partial) are left untouched:
they are already settled and their threshold is historically accurate.

NULL rows are also left untouched: the v12 settle_reservation() code already
handles NULL by requiring full fill.

Revision ID: 026_backfill_min_qty   (22 chars ≤ VARCHAR(32))
Revises:     025_reservation_capacity
Create Date: 2026-10-26
"""
import sqlalchemy as sa
from alembic import op

# ── revision identifiers ─────────────────────────────────────────────────────
revision      = '026_backfill_min_qty'      # 22 chars — within VARCHAR(32)
down_revision = '025_reservation_capacity'
branch_labels = None
depends_on    = None

# Terminal statuses — settled rows must not be touched.
_TERMINAL = ('filled', 'rejected', 'cancelled', 'cancelled_partial')


def upgrade() -> None:
    """Set min_filled_qty = quantity for active rows with stale (< qty) threshold."""
    conn = op.get_bind()

    # Inline the terminal status literals — SQLite does not support NOT IN with
    # a named tuple binding; PostgreSQL does but for maximum portability we use
    # literal strings.  _TERMINAL values are hard-coded constants, never user data.
    _terminal_clause = "('filled','rejected','cancelled','cancelled_partial')"

    # Count affected rows before update (for logging / audit trail).
    result = conn.execute(sa.text(
        f"""
        SELECT COUNT(*)
          FROM execution_reservations
         WHERE status NOT IN {_terminal_clause}
           AND min_filled_qty IS NOT NULL
           AND min_filled_qty < quantity
        """
    ))
    affected = result.scalar()

    if affected:
        conn.execute(sa.text(
            f"""
            UPDATE execution_reservations
               SET min_filled_qty = quantity
             WHERE status NOT IN {_terminal_clause}
               AND min_filled_qty IS NOT NULL
               AND min_filled_qty < quantity
            """
        ))

    # Log to alembic output (visible in alembic upgrade output).
    print(f'\n  [026] Backfilled min_filled_qty → quantity for {affected} active row(s).')


def downgrade() -> None:
    """No safe downgrade: we cannot recover the original stale values.

    The downgrade is intentionally a no-op.  Reverting to migration 025
    does not restore the stale thresholds — those were incorrect and should
    not be restored.  If a true rollback is needed, restore from a DB
    snapshot taken before running this migration.
    """
    pass
