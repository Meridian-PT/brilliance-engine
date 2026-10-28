"""phase 3 benefits enrollment windows accrual policies announcements

Revision ID: 77c70b136359
Revises: 653884608251
Create Date: 2026-10-28 20:22:35.193424

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '77c70b136359'
down_revision = '653884608251'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands manually written (see Phase 2 learnings: these tables were
    # already created on this dev DB by db.create_all() via a live reloader
    # process before this migration was generated, so `flask db migrate`
    # autogenerate reported "No changes detected" and produced an empty
    # upgrade(). Written explicitly here so the migration history is correct
    # for any database that has NOT yet booted this app version (e.g. a
    # deployed Postgres instance) — on such a DB, db.create_all() would also
    # create these tables on next boot, but this migration keeps Alembic's
    # history consistent regardless of boot order. ###
    op.create_table(
        'benefit_plans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('plan_type', sa.String(length=30), nullable=False),
        sa.Column('provider', sa.String(length=150), nullable=True),
        sa.Column('tier', sa.String(length=50), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'benefit_enrollments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('plan_id', sa.Integer(), nullable=False),
        sa.Column('coverage_level', sa.String(length=30), nullable=True),
        sa.Column('dependents_count', sa.Integer(), nullable=True),
        sa.Column('effective_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['plan_id'], ['benefit_plans.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'open_enrollment_windows',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'accrual_policies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('leave_type', sa.String(length=30), nullable=False),
        sa.Column('rate_per_period', sa.Float(), nullable=False),
        sa.Column('period', sa.String(length=20), nullable=True),
        sa.Column('annual_cap', sa.Float(), nullable=True),
        sa.Column('carryover_max', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'announcements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('audience', sa.String(length=100), nullable=True),
        sa.Column('author_id', sa.Integer(), nullable=True),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('is_pinned', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['author_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    # ### end manually-written commands ###


def downgrade():
    op.drop_table('announcements')
    op.drop_table('accrual_policies')
    op.drop_table('open_enrollment_windows')
    op.drop_table('benefit_enrollments')
    op.drop_table('benefit_plans')
