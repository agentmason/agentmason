"""Add integrations and oauth credentials.

Revision ID: 0003_add_integrations_and_oauth_credentials
Revises: 0002_add_rag_models
Create Date: 2026-08-15 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_add_integrations_and_oauth_credentials"
down_revision = "0002_add_rag_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("integrations", sa.Column("provider", sa.String(length=255), nullable=False, server_default=""))
    op.add_column("integrations", sa.Column("integration_type", sa.String(length=255), nullable=False, server_default="business"))
    op.add_column("integrations", sa.Column("status", sa.String(length=50), nullable=False, server_default="DISCONNECTED"))
    op.add_column("integrations", sa.Column("account_identifier", sa.String(length=255), nullable=True))
    op.add_column("integrations", sa.Column("display_name", sa.String(length=255), nullable=True))
    op.add_column("integrations", sa.Column("metadata", sa.JSON(), nullable=True))
    op.add_column("integrations", sa.Column("created_by", sa.String(length=36), nullable=True))
    op.add_column("integrations", sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("integrations", sa.Column("name", sa.String(length=255), nullable=False, server_default=""))

    op.create_table(
        "oauth_credentials",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("integration_id", sa.String(length=36), nullable=False),
        sa.Column("encrypted_access_token", sa.String(length=4096), nullable=False),
        sa.Column("encrypted_refresh_token", sa.String(length=4096), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scopes", sa.String(length=2048), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["integration_id"], ["integrations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_oauth_credentials_integration_id", "integration_id"),
    )

    op.alter_column("integrations", "provider", server_default=None)
    op.alter_column("integrations", "integration_type", server_default=None)
    op.alter_column("integrations", "status", server_default=None)
    op.alter_column("integrations", "name", server_default=None)


def downgrade() -> None:
    op.drop_table("oauth_credentials")
    op.drop_column("integrations", "last_sync_at")
    op.drop_column("integrations", "created_by")
    op.drop_column("integrations", "metadata")
    op.drop_column("integrations", "display_name")
    op.drop_column("integrations", "account_identifier")
    op.drop_column("integrations", "status")
    op.drop_column("integrations", "integration_type")
    op.drop_column("integrations", "provider")
    op.drop_column("integrations", "name")
