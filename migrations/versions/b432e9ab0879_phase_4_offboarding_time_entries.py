"""phase 4 offboarding time entries

Revision ID: b432e9ab0879
Revises: 77c70b136359
Create Date: 2026-10-28 20:37:11.921114

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b432e9ab0879'
down_revision = '77c70b136359'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands manually written (see Phase 3 learnings: a live
    # python3 run.py reloader process was running against this dev DB, so
    # db.create_all() created these tables the moment models.py was saved —
    # before `flask db migrate` ever ran. Autogenerate would therefore report
    # "No changes detected". Written explicitly here (transcribed from
    # PRAGMA table_info on the live dev DB) so the migration history is
    # correct for any database that has NOT yet booted this app version
    # (e.g. a deployed Postgres instance lacking a live create_all race). ###
    op.create_table(
        'offboarding_cases',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('initiated_by', sa.Integer(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('last_day', sa.Date(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['initiated_by'], ['users.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'offboarding_tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('assigned_to', sa.String(length=20), nullable=True),
        sa.Column('due_offset_days', sa.Integer(), nullable=True),
        sa.Column('completed', sa.Boolean(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['offboarding_cases.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'time_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('work_date', sa.Date(), nullable=False),
        sa.Column('hours', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('project_or_task', sa.String(length=200), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('source', sa.String(length=20), nullable=True),
        sa.Column('approved_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    # ### end manually-written commands ###


def downgrade():
    op.drop_table('time_entries')
    op.drop_table('offboarding_tasks')
    op.drop_table('offboarding_cases')
