"""create pnl and risk governor tables

Revision ID: 20260318_02
Revises: 20260318_01
Create Date: 2026-03-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260318_02"
down_revision = "20260318_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pnl_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("equity", sa.Float(), nullable=False),
        sa.Column("realized_pnl", sa.Float(), nullable=False, server_default="0"),
        sa.Column("unrealized_pnl", sa.Float(), nullable=False, server_default="0"),
        sa.Column("daily_pnl", sa.Float(), nullable=False, server_default="0"),
        sa.Column("session_pnl", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rolling_7d_pnl", sa.Float(), nullable=False, server_default="0"),
        sa.Column("peak_equity", sa.Float(), nullable=False),
        sa.Column("drawdown_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("max_drawdown_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("risk_state", sa.String(length=32), nullable=False),
        sa.Column("shutdown_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("win_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("loss_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="unknown"),
        sa.Column("trading_day", sa.String(length=10), nullable=False),
        sa.Column("session_id", sa.String(length=32), nullable=False),
    )
    op.create_index("ix_pnl_snapshots_timestamp", "pnl_snapshots", ["timestamp"], unique=False)
    op.create_index("ix_pnl_snapshots_mode", "pnl_snapshots", ["mode"], unique=False)
    op.create_index("ix_pnl_snapshots_trading_day", "pnl_snapshots", ["trading_day"], unique=False)
    op.create_index("ix_pnl_snapshots_session_id", "pnl_snapshots", ["session_id"], unique=False)
    op.create_index("ix_pnl_snapshots_risk_state", "pnl_snapshots", ["risk_state"], unique=False)

    op.create_table(
        "drawdown_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("previous_state", sa.String(length=32), nullable=False),
        sa.Column("new_state", sa.String(length=32), nullable=False),
        sa.Column("drawdown_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("trigger_reason", sa.String(length=128), nullable=False),
        sa.Column("daily_pnl", sa.Float(), nullable=False, server_default="0"),
        sa.Column("session_pnl", sa.Float(), nullable=False, server_default="0"),
    )
    op.create_index("ix_drawdown_events_timestamp", "drawdown_events", ["timestamp"], unique=False)
    op.create_index("ix_drawdown_events_mode", "drawdown_events", ["mode"], unique=False)
    op.create_index("ix_drawdown_events_new_state", "drawdown_events", ["new_state"], unique=False)

    op.create_table(
        "risk_shutdown_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("trigger_reason", sa.String(length=128), nullable=False),
        sa.Column("drawdown_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("daily_pnl", sa.Float(), nullable=False, server_default="0"),
        sa.Column("session_pnl", sa.Float(), nullable=False, server_default="0"),
        sa.Column("symbol", sa.String(length=32), nullable=True),
        sa.Column("strategy", sa.String(length=64), nullable=True),
        sa.Column("kill_switch_activated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("cancel_open_orders", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_risk_shutdown_events_timestamp", "risk_shutdown_events", ["timestamp"], unique=False)
    op.create_index("ix_risk_shutdown_events_mode", "risk_shutdown_events", ["mode"], unique=False)
    op.create_index("ix_risk_shutdown_events_state", "risk_shutdown_events", ["state"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_risk_shutdown_events_state", table_name="risk_shutdown_events")
    op.drop_index("ix_risk_shutdown_events_mode", table_name="risk_shutdown_events")
    op.drop_index("ix_risk_shutdown_events_timestamp", table_name="risk_shutdown_events")
    op.drop_table("risk_shutdown_events")

    op.drop_index("ix_drawdown_events_new_state", table_name="drawdown_events")
    op.drop_index("ix_drawdown_events_mode", table_name="drawdown_events")
    op.drop_index("ix_drawdown_events_timestamp", table_name="drawdown_events")
    op.drop_table("drawdown_events")

    op.drop_index("ix_pnl_snapshots_risk_state", table_name="pnl_snapshots")
    op.drop_index("ix_pnl_snapshots_session_id", table_name="pnl_snapshots")
    op.drop_index("ix_pnl_snapshots_trading_day", table_name="pnl_snapshots")
    op.drop_index("ix_pnl_snapshots_mode", table_name="pnl_snapshots")
    op.drop_index("ix_pnl_snapshots_timestamp", table_name="pnl_snapshots")
    op.drop_table("pnl_snapshots")
