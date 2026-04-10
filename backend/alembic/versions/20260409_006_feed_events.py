"""persistent feed events + read receipts (both append-only)

Revision ID: 006_feed
Revises: 005_risk
Create Date: 2026-04-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006_feed"
down_revision: Union[str, None] = "005_risk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Parent — append-only feed events
    op.execute("""
        CREATE TABLE IF NOT EXISTS persistent_feed_events (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            source_type VARCHAR(30) NOT NULL,
            event_type VARCHAR(30) NOT NULL,
            priority VARCHAR(10) NOT NULL DEFAULT 'medium',
            title TEXT NOT NULL,
            short_summary TEXT NOT NULL,
            full_explanation TEXT,
            related_symbol VARCHAR(20),
            confidence_score FLOAT,
            risk_level VARCHAR(10),
            action_suggestion TEXT,
            source_reference_type VARCHAR(30),
            source_reference_id INTEGER,
            dedupe_key VARCHAR(64) UNIQUE,
            expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_pfeed_user_ts ON persistent_feed_events (user_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_pfeed_user_type_ts ON persistent_feed_events (user_id, event_type, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_pfeed_dedupe ON persistent_feed_events (dedupe_key)")

    # Child — append-only read receipts
    op.execute("""
        CREATE TABLE IF NOT EXISTS feed_event_reads (
            id SERIAL PRIMARY KEY,
            feed_event_id INTEGER NOT NULL REFERENCES persistent_feed_events(id),
            user_id INTEGER NOT NULL,
            read_at TIMESTAMP DEFAULT NOW(),
            UNIQUE (feed_event_id, user_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_feed_read_user_ts ON feed_event_reads (user_id, read_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS feed_event_reads")
    op.execute("DROP TABLE IF EXISTS persistent_feed_events")
