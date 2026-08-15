"""Add Document and DocumentChunk models for RAG.

Revision ID: 0002_add_rag_models
Revises: 0001_initial
Create Date: 2026-08-12 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0002_add_rag_models'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create documents table
    op.create_table(
        'documents',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('organization_id', sa.String(36), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('file_name', sa.String(255), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('storage_location', sa.String(512), nullable=False),
        sa.Column('checksum', sa.String(64), nullable=False),
        sa.Column('status', sa.Enum('uploaded', 'processing', 'indexed', 'failed', 'deleted', name='documentstatus'), nullable=False),
        sa.Column('source_type', sa.Enum('uploaded', 'google_drive', 'gmail', 'onedrive', 'sharepoint', 'notion', 'slack', 'crm', 'api', name='documentsourcetype'), nullable=False),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_documents_organization_id', 'organization_id'),
        sa.Index('ix_documents_checksum', 'checksum'),
        sa.Index('ix_documents_status', 'status'),
        sa.Index('ix_documents_created_at', 'created_at'),
    )

    # Create document_chunks table
    op.create_table(
        'document_chunks',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('organization_id', sa.String(36), nullable=False),
        sa.Column('document_id', sa.String(36), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('token_count', sa.Integer(), nullable=True),
        sa.Column('embedding', sa.LargeBinary(), nullable=True),
        sa.Column('embedding_model', sa.String(100), nullable=True),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('similarity_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_document_chunks_organization_id', 'organization_id'),
        sa.Index('ix_document_chunks_document_id', 'document_id'),
        sa.Index('ix_document_chunks_created_at', 'created_at'),
    )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('document_chunks')
    op.drop_table('documents')
