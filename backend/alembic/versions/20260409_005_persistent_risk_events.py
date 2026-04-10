"""persistent risk events (append-only, nullable FK to ai_decision_events)

Revision ID: 005_risk
Revises: 004_decisions
Create Date: 2026-04-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005_risk"
down_revision: Union[str, None] = "004_decisions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS persistent_risk_events (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            symbol VARCHAR(20),
            related_decision_event_id INTEGER REFERENCES ai_decision_events(id),
            event_type VARCHAR(30) NOT NULL,
            severity VARCHAR(10) NOT NULL DEFAULT 'warning',
            reason_code VARCHAR(60) NOT NULL,
            summary TEXT NOT NULL,
            details_json JSONB DEFAULT '{}',
            original_requested_notional NUMERIC,
            adjusted_notional NUMERIC,
            original_requested_quantity NUMERIC,
            adjusted_quantity NUMERIC,
            portfolio_risk_score FLOAT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_prisk_user_ts ON persistent_risk_events (user_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_prisk_symbol_ts ON persistent_risk_events (symbol, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_prisk_event_type ON persistent_risk_events (event_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_prisk_decision_event ON persistent_risk_events (related_decision_event_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS persistent_risk_events")
