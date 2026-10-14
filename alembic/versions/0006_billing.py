"""Add billing: fee config on practices, verification on outcomes, statements table

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-14
"""

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Practice fee config
    op.add_column("practices", sa.Column("fee_rate_standard", sa.Numeric(5, 4), nullable=False, server_default="0.2200"))
    op.add_column("practices", sa.Column("fee_rate_aged", sa.Numeric(5, 4), nullable=False, server_default="0.3200"))
    op.add_column("practices", sa.Column("aged_threshold_days", sa.Integer, nullable=False, server_default="180"))

    # Outcome verification
    op.add_column("outcomes", sa.Column("verified", sa.Boolean, nullable=False, server_default="0"))
    op.add_column("outcomes", sa.Column("verification_method", sa.String(50), nullable=True))
    op.add_column("outcomes", sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("outcomes", sa.Column("verified_by", sa.String(100), nullable=True))
    op.add_column("outcomes", sa.Column("billable_amount", sa.Numeric(10, 2), nullable=True))

    # Statements
    op.create_table(
        "statements",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("practice_id", sa.Integer, sa.ForeignKey("practices.id"), nullable=False, index=True),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("total_recovered", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("fee_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("line_items", sa.Text, nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stripe_invoice_id", sa.String(100), nullable=True),
        sa.Column("pdf_path", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("statements")
    for col in ["verified", "verification_method", "verified_at", "verified_by", "billable_amount"]:
        op.drop_column("outcomes", col)
    for col in ["fee_rate_standard", "fee_rate_aged", "aged_threshold_days"]:
        op.drop_column("practices", col)
