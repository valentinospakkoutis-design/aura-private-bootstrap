"""create execution tables

Revision ID: 20260318_01
Revises:
Create Date: 2026-03-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260318_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("internal_order_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("broker", sa.String(length=64), nullable=False),
        sa.Column("broker_order_id", sa.String(length=128), nullable=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("filled_quantity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_fill_price", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("internal_order_id", name="uq_execution_orders_internal_order_id"),
        sa.UniqueConstraint("idempotency_key", name="uq_execution_orders_idempotency_key"),
    )
    op.create_index("ix_execution_orders_internal_order_id", "execution_orders", ["internal_order_id"], unique=False)
    op.create_index("ix_execution_orders_idempotency_key", "execution_orders", ["idempotency_key"], unique=False)
    op.create_index("ix_execution_orders_broker_order_id", "execution_orders", ["broker_order_id"], unique=False)
    op.create_index("ix_execution_orders_symbol", "execution_orders", ["symbol"], unique=False)
    op.create_index("ix_execution_orders_broker", "execution_orders", ["broker"], unique=False)
    op.create_index("ix_execution_orders_status", "execution_orders", ["status"], unique=False)

    op.create_table(
        "execution_order_audit",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("internal_order_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["internal_order_id"],
            ["execution_orders.internal_order_id"],
            name="fk_execution_order_audit_internal_order_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_execution_order_audit_internal_order_id", "execution_order_audit", ["internal_order_id"], unique=False)
    op.create_index("ix_execution_order_audit_event_type", "execution_order_audit", ["event_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_execution_order_audit_event_type", table_name="execution_order_audit")
    op.drop_index("ix_execution_order_audit_internal_order_id", table_name="execution_order_audit")
    op.drop_table("execution_order_audit")

    op.drop_index("ix_execution_orders_status", table_name="execution_orders")
    op.drop_index("ix_execution_orders_broker", table_name="execution_orders")
    op.drop_index("ix_execution_orders_symbol", table_name="execution_orders")
    op.drop_index("ix_execution_orders_broker_order_id", table_name="execution_orders")
    op.drop_index("ix_execution_orders_idempotency_key", table_name="execution_orders")
    op.drop_index("ix_execution_orders_internal_order_id", table_name="execution_orders")
    op.drop_table("execution_orders")
