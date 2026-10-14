"""Add extended claim fields to cases table.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-14
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("cases") as batch_op:
        batch_op.add_column(sa.Column("claim_number", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("modifier", sa.String(10), nullable=True))
        batch_op.add_column(sa.Column("rendering_provider_npi", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("billing_provider_tin", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("clinical_notes", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("carc_codes", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("cases") as batch_op:
        batch_op.drop_column("carc_codes")
        batch_op.drop_column("clinical_notes")
        batch_op.drop_column("billing_provider_tin")
        batch_op.drop_column("rendering_provider_npi")
        batch_op.drop_column("modifier")
        batch_op.drop_column("claim_number")
