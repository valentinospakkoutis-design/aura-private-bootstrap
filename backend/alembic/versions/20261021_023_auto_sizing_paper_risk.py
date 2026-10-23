"""Server-owned paper sizing history; existing accounts intentionally unseeded."""
from alembic import op
import sqlalchemy as sa
revision = '023_auto_sizing_paper_risk'
down_revision = '022_paper_snapshot_created_at'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('auto_sizing_paper_risk',
        sa.Column('user_id', sa.Integer(), primary_key=True),
        sa.Column('initial_equity_usd', sa.Float(), nullable=False),
        sa.Column('peak_equity_usd', sa.Float(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('last_observed_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_table('auto_sizing_paper_risk')
