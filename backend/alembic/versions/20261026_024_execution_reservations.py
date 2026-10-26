"""Atomic execution reservations for paper mode.

Revision:     024_execution_reservations
Down revision: 023_prior_schema

Changes
───────
1. auto_sizing_paper_risk.initial_equity_usd / peak_equity_usd  Float → NUMERIC(20,8)
2. user_profiles.paper_balance  Float → NUMERIC(20,8)  (guarded; skipped if already NUMERIC)
3. execution_reservations table — one row per in-flight paper order
4. reservation_fill_events table — one row per fill event, UNIQUE on (reservation_id, fill_id)

Operational constraints unchanged
──────────────────────────────────
- No account resets, no real orders, no migrations on external DB.
- ALLOW_LIVE_TRADING unchanged.
- DCA safeguards and kill switch preserved.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision      = '024_execution_reservations'
down_revision = '022_paper_snapshot_created_at'
branch_labels = None
depends_on    = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    # ── 1. auto_sizing_paper_risk: Float → NUMERIC ─────────────────────────
    with op.batch_alter_table('auto_sizing_paper_risk') as batch:
        batch.alter_column('initial_equity_usd',
                           existing_type=sa.Float(),
                           type_=sa.Numeric(20, 8),
                           existing_nullable=False)
        batch.alter_column('peak_equity_usd',
                           existing_type=sa.Float(),
                           type_=sa.Numeric(20, 8),
                           existing_nullable=False)

    # ── 2. user_profiles.paper_balance: Float → NUMERIC ────────────────────
    up_cols = {c['name']: c for c in inspector.get_columns('user_profiles')}
    if 'paper_balance' in up_cols:
        existing_type = up_cols['paper_balance']['type']
        type_name = type(existing_type).__name__.upper()
        if 'NUMERIC' not in type_name and 'DECIMAL' not in type_name:
            with op.batch_alter_table('user_profiles') as batch:
                batch.alter_column('paper_balance',
                                   existing_type=sa.Float(),
                                   type_=sa.Numeric(20, 8),
                                   existing_nullable=True)

    # ── 3. execution_reservations ───────────────────────────────────────────
    op.create_table(
        'execution_reservations',
        sa.Column('id',               sa.Integer(),    primary_key=True, autoincrement=True),
        sa.Column('idempotency_key',  sa.String(64),   nullable=False, unique=True),
        sa.Column('user_id',          sa.Integer(),    nullable=False, index=True),
        sa.Column('account_mode',     sa.String(16),   nullable=False),
        sa.Column('symbol',           sa.String(32),   nullable=False),
        sa.Column('side',             sa.String(8),    nullable=False),
        sa.Column('order_type',       sa.String(16),   nullable=False),
        sa.Column('quantity',         sa.Numeric(20, 8), nullable=False),
        sa.Column('notional_usd',     sa.Numeric(20, 8), nullable=False),
        sa.Column('fee_estimate_usd', sa.Numeric(20, 8), nullable=False),
        sa.Column('status',           sa.String(24),   nullable=False, server_default='reserved'),
        sa.Column('created_at',       sa.DateTime(),   nullable=False),
        sa.Column('expires_at',       sa.DateTime(),   nullable=False),
        sa.Column('claimed_at',       sa.DateTime(),   nullable=True),
        sa.Column('released_at',      sa.DateTime(),   nullable=True),
        sa.Column('filled_quantity',  sa.Numeric(20, 8), nullable=True),
        sa.Column('filled_notional',  sa.Numeric(20, 8), nullable=True),
        sa.Column('actual_fee_usd',   sa.Numeric(20, 8), nullable=True),
        sa.Column('broker_order_id',  sa.String(128),  nullable=True),
        sa.CheckConstraint("account_mode = 'paper'",     name='ck_er_paper_only'),
        sa.CheckConstraint("side IN ('BUY','SELL')",     name='ck_er_side'),
        sa.CheckConstraint(
            "status IN ('reserved','claiming','partial','filled',"
            "'rejected','unknown','cancelled_partial')",
            name='ck_er_status'),
    )
    op.create_index('ix_er_user_status', 'execution_reservations',
                    ['user_id', 'status'])

    # ── 4. reservation_fill_events ──────────────────────────────────────────
    op.create_table(
        'reservation_fill_events',
        sa.Column('id',            sa.Integer(),    primary_key=True, autoincrement=True),
        sa.Column('reservation_id', sa.Integer(),   nullable=False),
        sa.Column('fill_id',       sa.String(128),  nullable=False),
        sa.Column('filled_quantity', sa.Numeric(20, 8), nullable=False),
        sa.Column('filled_notional', sa.Numeric(20, 8), nullable=False),
        sa.Column('actual_fee_usd',  sa.Numeric(20, 8), nullable=False),
        sa.Column('recorded_at',   sa.DateTime(),   nullable=False),
        sa.UniqueConstraint('reservation_id', 'fill_id', name='uq_fill_event'),
        sa.ForeignKeyConstraint(['reservation_id'], ['execution_reservations.id'],
                                name='fk_rfe_reservation'),
    )


def downgrade():
    op.drop_table('reservation_fill_events')
    op.drop_index('ix_er_user_status', 'execution_reservations')
    op.drop_table('execution_reservations')
    with op.batch_alter_table('auto_sizing_paper_risk') as batch:
        batch.alter_column('initial_equity_usd',
                           existing_type=sa.Numeric(20, 8),
                           type_=sa.Float(), existing_nullable=False)
        batch.alter_column('peak_equity_usd',
                           existing_type=sa.Numeric(20, 8),
                           type_=sa.Float(), existing_nullable=False)
