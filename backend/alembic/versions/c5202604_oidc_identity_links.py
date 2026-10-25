"""Explicit external OIDC identity associations.

Revision ID: c5202604
Revises: c5202603
"""
from alembic import op
import sqlalchemy as sa
revision = "c5202604"
down_revision = "c5202603"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "oidc_identity_links",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("issuer", sa.String(512), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("issuer", "subject", name="uq_oidc_identity_issuer_subject"),
    )
    op.create_index("ix_oidc_identity_links_user_id", "oidc_identity_links", ["user_id"])

def downgrade():
    op.drop_index("ix_oidc_identity_links_user_id", table_name="oidc_identity_links")
    op.drop_table("oidc_identity_links")
