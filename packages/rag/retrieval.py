from __future__ import annotations

import logging
from typing import Optional

from packages.embeddings.provider import EmbeddingProvider
from packages.vectorstore import VectorStore, SearchResult

logger = logging.getLogger(__name__)


class RetrievalService:
    """Service for retrieving relevant documents using semantic search."""

    def __init__(
        self,
        vector_store: VectorStore,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        """
        Initialize retrieval service.
        
        Args:
            vector_store: Vector store implementation
            embedding_provider: Embedding provider implementation
        """
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider

    async def retrieve(
        self,
        organization_id: str,
        query: str,
        top_k: int = 5,
        filters: Optional[dict] = None,
    ) -> list[RetrievedChunk]:
        """
        Retrieve relevant chunks for a query.
        
        Args:
            organization_id: Organization ID
            query: Search query
            top_k: Number of top results
            filters: Optional metadata filters
            
        Returns:
            List of RetrievedChunk objects
        """
        try:
            # Generate query embedding
            logger.info(f"Generating embedding for query: {query[:100]}")
            query_embedding = await self.embedding_provider.embed_text(query)

            # Search vector store
            logger.info(f"Searching vector store for organization {organization_id}")
            search_results = await self.vector_store.search(
                organization_id=organization_id,
                query_embedding=query_embedding,
                top_k=top_k,
                filters=filters,
            )

            # Convert to RetrievedChunk objects
            chunks = []
            for result in search_results:
                chunk = RetrievedChunk(
                    chunk_id=result.chunk_id,
                    content=result.metadata.get("content", ""),
                    score=result.score,
                    metadata=result.metadata,
                )
                chunks.append(chunk)

            logger.info(f"Retrieved {len(chunks)} chunks")
            return chunks

        except Exception as e:
            logger.error(f"Retrieval failed: {str(e)}")
            raise


class RetrievedChunk:
    """Represents a chunk retrieved from the vector store."""

    def __init__(
        self,
        chunk_id: str,
        content: str,
        score: float,
        metadata: dict,
    ) -> None:
        self.chunk_id = chunk_id
        self.content = content
        self.score = score
        self.metadata = metadata

    @property
    def document_id(self) -> Optional[str]:
        """Get document ID from metadata."""
        return self.metadata.get("document_id")

    @property
    def document_name(self) -> Optional[str]:
        """Get document name from metadata."""
        return self.metadata.get("document_name")

    @property
    def page_number(self) -> Optional[int]:
        """Get page number from metadata."""
        return self.metadata.get("page_number")

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "score": self.score,
            "document_id": self.document_id,
            "document_name": self.document_name,
            "page_number": self.page_number,
            "metadata": self.metadata,
        }
