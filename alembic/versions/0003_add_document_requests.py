"""Add document_requests table

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-14
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_requests",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("case_id", sa.Integer, sa.ForeignKey("cases.id"), nullable=False, index=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("practices.id"), nullable=True, index=True),
        sa.Column("requested_by", sa.String(100), nullable=False),
        sa.Column("document_type", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fulfilled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("file_path", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("document_requests")
