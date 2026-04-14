"""adopt raw SQL legacy tables into SQLAlchemy management

Revision ID: 021_raw_sql_to_sqlalchemy
Revises: 020_social_features
Create Date: 2026-04-14
"""
from typing import Sequence, Union

from alembic import op

revision: str = "021_raw_sql_to_sqlalchemy"
down_revision: Union[str, None] = "020_social_features"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE auth_audit_logs ADD COLUMN IF NOT EXISTS user_id INTEGER")
    op.execute("ALTER TABLE auth_audit_logs ADD COLUMN IF NOT EXISTS event_type TEXT NOT NULL DEFAULT 'UNKNOWN'")
    op.execute("ALTER TABLE auth_audit_logs ADD COLUMN IF NOT EXISTS event_status TEXT NOT NULL DEFAULT 'UNKNOWN'")
    op.execute("ALTER TABLE auth_audit_logs ADD COLUMN IF NOT EXISTS ip_address TEXT")
    op.execute("ALTER TABLE auth_audit_logs ADD COLUMN IF NOT EXISTS user_agent TEXT")
    op.execute("ALTER TABLE auth_audit_logs ADD COLUMN IF NOT EXISTS metadata JSONB")
    op.execute("ALTER TABLE auth_audit_logs ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()")

    op.execute("ALTER TABLE user_2fa_settings ADD COLUMN IF NOT EXISTS user_id INTEGER")
    op.execute("ALTER TABLE user_2fa_settings ADD COLUMN IF NOT EXISTS secret_encrypted TEXT")
    op.execute("ALTER TABLE user_2fa_settings ADD COLUMN IF NOT EXISTS is_enabled BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE user_2fa_settings ADD COLUMN IF NOT EXISTS recovery_codes_json JSONB")
    op.execute("ALTER TABLE user_2fa_settings ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()")
    op.execute("ALTER TABLE user_2fa_settings ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()")

    op.execute("ALTER TABLE live_order_audit_logs ADD COLUMN IF NOT EXISTS user_id INTEGER")
    op.execute("ALTER TABLE live_order_audit_logs ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'unknown'")
    op.execute("ALTER TABLE live_order_audit_logs ADD COLUMN IF NOT EXISTS symbol TEXT NOT NULL DEFAULT 'UNKNOWN'")
    op.execute("ALTER TABLE live_order_audit_logs ADD COLUMN IF NOT EXISTS side TEXT NOT NULL DEFAULT 'UNKNOWN'")
    op.execute("ALTER TABLE live_order_audit_logs ADD COLUMN IF NOT EXISTS quantity NUMERIC NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE live_order_audit_logs ADD COLUMN IF NOT EXISTS price NUMERIC")
    op.execute("ALTER TABLE live_order_audit_logs ADD COLUMN IF NOT EXISTS trading_mode TEXT NOT NULL DEFAULT 'paper'")
    op.execute("ALTER TABLE live_order_audit_logs ADD COLUMN IF NOT EXISTS client_order_id TEXT")
    op.execute("ALTER TABLE live_order_audit_logs ADD COLUMN IF NOT EXISTS broker TEXT NOT NULL DEFAULT 'unknown'")
    op.execute("ALTER TABLE live_order_audit_logs ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'unknown'")
    op.execute("ALTER TABLE live_order_audit_logs ADD COLUMN IF NOT EXISTS broker_order_id TEXT")
    op.execute("ALTER TABLE live_order_audit_logs ADD COLUMN IF NOT EXISTS response_summary JSONB")
    op.execute("ALTER TABLE live_order_audit_logs ADD COLUMN IF NOT EXISTS error_message TEXT")
    op.execute("ALTER TABLE live_order_audit_logs ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()")

    op.execute("ALTER TABLE push_tokens ADD COLUMN IF NOT EXISTS user_id INTEGER")
    op.execute("ALTER TABLE push_tokens ADD COLUMN IF NOT EXISTS token TEXT")
    op.execute("ALTER TABLE push_tokens ADD COLUMN IF NOT EXISTS platform TEXT DEFAULT 'android'")
    op.execute("ALTER TABLE push_tokens ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE")
    op.execute("ALTER TABLE push_tokens ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()")
    op.execute("ALTER TABLE push_tokens ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()")

    op.execute("ALTER TABLE feed_events ADD COLUMN IF NOT EXISTS event_type TEXT NOT NULL DEFAULT 'system'")
    op.execute("ALTER TABLE feed_events ADD COLUMN IF NOT EXISTS symbol TEXT")
    op.execute("ALTER TABLE feed_events ADD COLUMN IF NOT EXISTS title TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE feed_events ADD COLUMN IF NOT EXISTS body TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE feed_events ADD COLUMN IF NOT EXISTS severity TEXT DEFAULT 'info'")
    op.execute("ALTER TABLE feed_events ADD COLUMN IF NOT EXISTS reason_codes TEXT[]")
    op.execute("ALTER TABLE feed_events ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb")
    op.execute("ALTER TABLE feed_events ADD COLUMN IF NOT EXISTS dedup_key TEXT")
    op.execute("ALTER TABLE feed_events ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()")


def downgrade() -> None:
    pass
