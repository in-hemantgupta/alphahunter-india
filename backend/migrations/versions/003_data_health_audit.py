"""create data_health_audit table

Revision ID: 003
Revises: 002
Create Date: 2026-07-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'data_health_audit',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('date', sa.DateTime(), nullable=False),
        sa.Column('field_name', sa.String(), nullable=False),
        sa.Column('coverage_pct', sa.Float()),
        sa.Column('source', sa.String()),
        sa.Column('status', sa.String()),
        sa.Column('failure_reason', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('data_health_audit')
