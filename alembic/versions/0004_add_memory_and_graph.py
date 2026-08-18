"""Add business memory and graph models.

Revision ID: 0004_add_memory_and_graph
Revises: 0003_add_integrations_and_oauth_credentials
Create Date: 2026-08-18 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_add_memory_and_graph"
down_revision = "0003_add_integrations_and_oauth_credentials"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Business Memories table
    op.create_table(
        "business_memories",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("structured_data", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="active"),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("source_reference", sa.String(length=512), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("previous_version_id", sa.String(length=36), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_business_memories_organization_id", "organization_id"),
        sa.Index("ix_business_memories_category", "category"),
        sa.Index("ix_business_memories_status", "status"),
        sa.Index("ix_business_memories_created_at", "created_at"),
        sa.Index("ix_business_memories_previous_version_id", "previous_version_id"),
        sa.Index("ix_business_memories_org_category", "organization_id", "category"),
        sa.Index("ix_business_memories_org_status", "organization_id", "status"),
    )

    # Graph Entities table
    op.create_table(
        "graph_entities",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("properties", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_graph_entities_organization_id", "organization_id"),
        sa.Index("ix_graph_entities_entity_type", "entity_type"),
        sa.Index("ix_graph_entities_created_at", "created_at"),
        sa.Index("ix_graph_entities_org_type", "organization_id", "entity_type"),
    )

    # Graph Relationships table
    op.create_table(
        "graph_relationships",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("source_entity_id", sa.String(length=36), nullable=False),
        sa.Column("target_entity_id", sa.String(length=36), nullable=False),
        sa.Column("relationship_type", sa.String(length=50), nullable=False),
        sa.Column("properties", sa.JSON(), nullable=True),
        sa.Column("strength", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["source_entity_id"], ["graph_entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_entity_id"], ["graph_entities.id"], ondelete="CASCADE"),
        sa.Index("ix_graph_relationships_organization_id", "organization_id"),
        sa.Index("ix_graph_relationships_source_entity_id", "source_entity_id"),
        sa.Index("ix_graph_relationships_target_entity_id", "target_entity_id"),
        sa.Index("ix_graph_relationships_relationship_type", "relationship_type"),
        sa.Index("ix_graph_relationships_org_type", "organization_id", "relationship_type"),
    )


def downgrade() -> None:
    op.drop_table("graph_relationships")
    op.drop_table("graph_entities")
    op.drop_table("business_memories")
