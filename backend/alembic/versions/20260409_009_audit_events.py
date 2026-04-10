"""unified audit events (append-only, cross-domain)

Revision ID: 009_audit
Revises: 008_simulation
Create Date: 2026-04-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "009_audit"
down_revision: Union[str, None] = "008_simulation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS audit_events (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            event_domain VARCHAR(20) NOT NULL,
            event_name VARCHAR(60) NOT NULL,
            entity_type VARCHAR(40),
            entity_id INTEGER,
            severity VARCHAR(10) NOT NULL DEFAULT 'info',
            summary TEXT NOT NULL,
            payload_json JSONB DEFAULT '{}',
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_user_ts ON audit_events (user_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_domain_ts ON audit_events (event_domain, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_entity ON audit_events (entity_type, entity_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_severity_ts ON audit_events (severity, created_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS audit_events")
