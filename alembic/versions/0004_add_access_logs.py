"""Add access_logs table

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-14
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "access_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("practices.id"), nullable=True, index=True),
        sa.Column("actor_id", sa.String(100), nullable=False),
        sa.Column("actor_email", sa.String(200), nullable=True),
        sa.Column("actor_role", sa.String(50), nullable=False),
        sa.Column("resource", sa.String(200), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("http_method", sa.String(10), nullable=False),
        sa.Column("path", sa.String(500), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("access_logs")
