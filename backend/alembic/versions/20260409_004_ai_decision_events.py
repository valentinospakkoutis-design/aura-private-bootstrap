"""ai decision events + reason codes + counterfactuals (all append-only)

Revision ID: 004_decisions
Revises: 003_strategy
Create Date: 2026-04-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004_decisions"
down_revision: Union[str, None] = "003_strategy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Parent — append-only decision fact table
    op.execute("""
        CREATE TABLE IF NOT EXISTS ai_decision_events (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            symbol VARCHAR(20) NOT NULL,
            action VARCHAR(20) NOT NULL,
            confidence_score FLOAT,
            confidence_band VARCHAR(10),
            market_regime VARCHAR(20),
            narrative_summary TEXT,
            machine_summary TEXT,
            stop_loss_logic TEXT,
            take_profit_logic TEXT,
            expected_holding_profile TEXT,
            raw_signal_payload_json JSONB DEFAULT '{}',
            audit_metadata_json JSONB DEFAULT '{}',
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_ai_decision_user_ts ON ai_decision_events (user_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ai_decision_symbol_ts ON ai_decision_events (symbol, created_at DESC)")

    # Child — relational reason codes (NOT a JSON blob)
    op.execute("""
        CREATE TABLE IF NOT EXISTS ai_decision_reason_codes (
            id SERIAL PRIMARY KEY,
            decision_event_id INTEGER NOT NULL REFERENCES ai_decision_events(id),
            code VARCHAR(60) NOT NULL,
            category VARCHAR(20) NOT NULL,
            detail_text TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_ai_reason_code ON ai_decision_reason_codes (code)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ai_reason_event ON ai_decision_reason_codes (decision_event_id)")

    # Child — counterfactuals
    op.execute("""
        CREATE TABLE IF NOT EXISTS ai_decision_counterfactuals (
            id SERIAL PRIMARY KEY,
            decision_event_id INTEGER NOT NULL REFERENCES ai_decision_events(id),
            counterfactual_type VARCHAR(30) NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_ai_cf_event ON ai_decision_counterfactuals (decision_event_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ai_decision_counterfactuals")
    op.execute("DROP TABLE IF EXISTS ai_decision_reason_codes")
    op.execute("DROP TABLE IF EXISTS ai_decision_events")
