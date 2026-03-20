"""create order submission ledger table

Revision ID: 20260319_03
Revises: 20260318_02
Create Date: 2026-03-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260319_03"
down_revision = "20260318_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "order_submission_ledger",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("principal_id", sa.String(length=255), nullable=False),
        sa.Column("endpoint", sa.String(length=255), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="processing"),
        sa.Column("result_order_id", sa.String(length=128), nullable=True),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "principal_id",
            "idempotency_key",
            name="uq_order_submission_principal_key",
        ),
    )
    op.create_index("ix_order_submission_ledger_id", "order_submission_ledger", ["id"], unique=False)
    op.create_index("ix_order_submission_ledger_principal_id", "order_submission_ledger", ["principal_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_order_submission_ledger_principal_id", table_name="order_submission_ledger")
    op.drop_index("ix_order_submission_ledger_id", table_name="order_submission_ledger")
    op.drop_table("order_submission_ledger")
