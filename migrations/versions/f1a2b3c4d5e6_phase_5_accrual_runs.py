"""phase 5 accrual runs idempotency table

Revision ID: f1a2b3c4d5e6
Revises: b432e9ab0879
Create Date: 2026-11-13 16:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1a2b3c4d5e6'
down_revision = 'b432e9ab0879'
branch_labels = None
depends_on = None


def upgrade():
    # ### manually written (same gotcha as Phase 4 -- see b432e9ab0879): running
    # `flask db migrate` imports run.py, whose module-level db.create_all() races
    # ahead and creates this table on the dev DB before autogenerate inspects it,
    # so autogenerate reports "No changes detected". Written explicitly here
    # (transcribed from models.py / PRAGMA table_info on the dev DB) so the
    # migration history is correct for any database that has NOT yet booted
    # this app version. ###
    op.create_table(
        'accrual_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('policy_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('period_key', sa.String(length=20), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('run_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['policy_id'], ['accrual_policies.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('policy_id', 'user_id', 'period_key', name='uq_accrual_run_policy_user_period'),
    )
    # ### end manually-written commands ###


def downgrade():
    op.drop_table('accrual_runs')
