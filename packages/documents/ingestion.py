from __future__ import annotations

import hashlib
import logging
import tempfile
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.models.document import Document, DocumentChunk, DocumentStatus
from packages.documents import ParserRegistry, ParseError
from packages.documents.chunking import ChunkingService, ChunkConfig
from packages.embeddings.provider import EmbeddingProvider
from packages.storage import FileStorage
from packages.vectorstore import VectorStore

logger = logging.getLogger(__name__)


class IngestionService:
    """Service for ingesting and processing documents."""

    def __init__(
        self,
        file_storage: FileStorage,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        chunk_config: Optional[ChunkConfig] = None,
    ) -> None:
        """
        Initialize ingestion service.
        
        Args:
            file_storage: File storage implementation
            embedding_provider: Embedding provider
            vector_store: Vector store implementation
            chunk_config: Chunking configuration
        """
        self.file_storage = file_storage
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.parser_registry = ParserRegistry()
        self.chunking_service = ChunkingService(chunk_config or ChunkConfig())

    async def ingest_document(
        self,
        db: Session,
        document_id: str,
        organization_id: str,
    ) -> bool:
        """
        Ingest a document: parse, chunk, embed, and store.
        
        Args:
            db: Database session
            document_id: Document ID
            organization_id: Organization ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get document
            document = db.scalar(
                select(Document).where(Document.id == document_id)
            )

            if not document:
                logger.error(f"Document not found: {document_id}")
                return False

            logger.info(f"Starting ingestion of document {document_id}")

            # Update status
            document.status = DocumentStatus.PROCESSING
            db.commit()

            # Retrieve file from storage
            file_content = await self.file_storage.get(document.storage_location)

            # Create temporary file for parsing
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(document.file_name).suffix) as tmp:
                tmp.write(file_content)
                tmp_path = tmp.name

            try:
                # Parse document
                logger.info(f"Parsing document: {document.file_name}")
                parse_result = await self.parser_registry.parse(
                    tmp_path,
                    document.file_name,
                    document.mime_type,
                )

                # Update document metadata
                document.metadata_payload = parse_result.metadata

                # Chunk document
                logger.info(f"Chunking document: {document_id}")
                metadata = {
                    "document_id": document_id,
                    "document_name": document.name,
                    "source_type": document.source_type.value,
                }
                if parse_result.pages:
                    metadata["total_pages"] = parse_result.pages

                chunks = self.chunking_service.chunk(parse_result.text, metadata)
                logger.info(f"Created {len(chunks)} chunks from document {document_id}")

                # Embed and store chunks
                chunk_objects = []
                embeddings_to_create = []

                for chunk in chunks:
                    # Create chunk object
                    chunk_obj = DocumentChunk(
                        id=f"{document_id}_chunk_{chunk.index}",
                        organization_id=organization_id,
                        document_id=document_id,
                        chunk_index=chunk.index,
                        content=chunk.content,
                        token_count=self.chunking_service.estimate_tokens(chunk.content),
                        metadata_payload=chunk.metadata,
                    )
                    chunk_objects.append(chunk_obj)
                    embeddings_to_create.append(chunk.content)

                # Embed chunks in batch
                logger.info(f"Embedding {len(embeddings_to_create)} chunks")
                embeddings = await self.embedding_provider.embed_documents(embeddings_to_create)

                # Store chunks and embeddings
                for chunk_obj, embedding in zip(chunk_objects, embeddings):
                    chunk_obj.embedding = self._embedding_to_bytes(embedding)
                    chunk_obj.embedding_model = "text-embedding-3-small"

                    # Add to database
                    db.add(chunk_obj)

                    # Add to vector store
                    await self.vector_store.upsert(
                        chunk_id=chunk_obj.id,
                        embedding=embedding,
                        metadata={
                            "document_id": chunk_obj.document_id,
                            "document_name": document.name,
                            "chunk_index": chunk_obj.chunk_index,
                            "content": chunk_obj.content,
                            "page_number": chunk_obj.metadata_payload.get("page_number"),
                            "total_pages": chunk_obj.metadata_payload.get("total_pages"),
                        },
                        organization_id=organization_id,
                    )

                # Update document status
                document.status = DocumentStatus.INDEXED
                document.error_message = None

                db.commit()
                logger.info(f"Document {document_id} ingested successfully")
                return True

            finally:
                # Clean up temporary file
                Path(tmp_path).unlink(missing_ok=True)

        except ParseError as e:
            logger.error(f"Parse error for document {document_id}: {str(e)}")
            document.status = DocumentStatus.FAILED
            document.error_message = f"Parse error: {str(e)}"
            db.commit()
            return False

        except Exception as e:
            logger.error(f"Ingestion failed for document {document_id}: {str(e)}")
            document.status = DocumentStatus.FAILED
            document.error_message = f"Ingestion error: {str(e)}"
            db.commit()
            return False

    async def delete_document_vectors(
        self,
        organization_id: str,
        document_id: str,
    ) -> None:
        """
        Delete all vectors for a document from vector store.
        
        Args:
            organization_id: Organization ID
            document_id: Document ID
        """
        try:
            await self.vector_store.delete_by_document(document_id, organization_id)
            logger.info(f"Deleted vectors for document {document_id}")
        except Exception as e:
            logger.error(f"Failed to delete vectors for document {document_id}: {str(e)}")
            raise

    @staticmethod
    def _embedding_to_bytes(embedding: list[float]) -> bytes:
        """Convert embedding vector to bytes for storage."""
        import struct
        # Pack as doubles (8 bytes each)
        return struct.pack(f"{len(embedding)}d", *embedding)

    @staticmethod
    def _bytes_to_embedding(data: bytes) -> list[float]:
        """Convert bytes back to embedding vector."""
        import struct
        # Unpack doubles
        return list(struct.unpack(f"{len(data) // 8}d", data))
