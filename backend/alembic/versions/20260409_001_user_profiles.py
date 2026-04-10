"""user_profiles — per-user personalization settings (mutable)

Revision ID: 001_user_profiles
Revises: None
Create Date: 2026-04-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_user_profiles"
down_revision: Union[str, None] = "000_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_profiles (
            id SERIAL PRIMARY KEY,
            user_id INTEGER UNIQUE NOT NULL,
            risk_profile VARCHAR(20) NOT NULL DEFAULT 'moderate',
            investment_objective VARCHAR(30) DEFAULT 'balanced_growth',
            preferred_mode VARCHAR(20) DEFAULT 'manual_assist',
            confidence_threshold_override FLOAT,
            max_portfolio_exposure_override FLOAT,
            max_position_size_override FLOAT,
            behavior_flags_json JSONB DEFAULT '{}',
            notes_json JSONB DEFAULT '{}',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_profiles_user_id ON user_profiles (user_id)")

    # Backward-compatible column additions for existing tables
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS investment_objective VARCHAR(30) DEFAULT 'balanced_growth'")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS preferred_mode VARCHAR(20) DEFAULT 'manual_assist'")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS max_portfolio_exposure_override FLOAT")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS max_position_size_override FLOAT")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS notes_json JSONB DEFAULT '{}'")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_profiles")
