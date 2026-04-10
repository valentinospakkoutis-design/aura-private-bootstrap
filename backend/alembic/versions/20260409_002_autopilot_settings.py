"""autopilot settings (mutable) + mode change log (append-only)

Revision ID: 002_autopilot
Revises: 001_user_profiles
Create Date: 2026-04-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_autopilot"
down_revision: Union[str, None] = "001_user_profiles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_autopilot_settings (
            id SERIAL PRIMARY KEY,
            user_id INTEGER UNIQUE NOT NULL,
            current_mode VARCHAR(20) NOT NULL DEFAULT 'balanced',
            is_enabled BOOLEAN NOT NULL DEFAULT FALSE,
            config_overrides_json JSONB DEFAULT '{}',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_autopilot_settings_user ON user_autopilot_settings (user_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS autopilot_mode_change_log (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            previous_mode VARCHAR(20),
            new_mode VARCHAR(20) NOT NULL,
            reason TEXT,
            changed_by VARCHAR(20) NOT NULL DEFAULT 'user',
            metadata_json JSONB DEFAULT '{}',
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_autopilot_change_user_ts ON autopilot_mode_change_log (user_id, created_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS autopilot_mode_change_log")
    op.execute("DROP TABLE IF EXISTS user_autopilot_settings")
