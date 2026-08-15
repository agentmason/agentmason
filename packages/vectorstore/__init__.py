from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Any

import logging

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Result from vector store search."""
    chunk_id: str
    score: float
    metadata: dict


class VectorStore(ABC):
    """Abstract base class for vector store implementations."""

    @abstractmethod
    async def upsert(
        self,
        chunk_id: str,
        embedding: list[float],
        metadata: dict,
        organization_id: str,
    ) -> None:
        """
        Upsert a chunk with its embedding and metadata.
        
        Args:
            chunk_id: Unique chunk ID
            embedding: Embedding vector
            metadata: Metadata dictionary
            organization_id: Organization ID for tenant isolation
        """
        pass

    @abstractmethod
    async def search(
        self,
        organization_id: str,
        query_embedding: list[float],
        top_k: int = 5,
        filters: Optional[dict] = None,
    ) -> list[SearchResult]:
        """
        Search for similar chunks.
        
        Args:
            organization_id: Organization ID for tenant isolation
            query_embedding: Query embedding vector
            top_k: Number of top results to return
            filters: Optional metadata filters
            
        Returns:
            List of SearchResult objects
        """
        pass

    @abstractmethod
    async def delete(
        self,
        chunk_id: str,
        organization_id: str,
    ) -> None:
        """
        Delete a chunk from the vector store.
        
        Args:
            chunk_id: Chunk ID to delete
            organization_id: Organization ID for tenant isolation
        """
        pass

    @abstractmethod
    async def delete_by_document(
        self,
        document_id: str,
        organization_id: str,
    ) -> None:
        """
        Delete all chunks for a document.
        
        Args:
            document_id: Document ID
            organization_id: Organization ID for tenant isolation
        """
        pass

    @abstractmethod
    async def exists(
        self,
        chunk_id: str,
        organization_id: str,
    ) -> bool:
        """Check if a chunk exists in the vector store."""
        pass


class PostgreSQLVectorStore(VectorStore):
    """Vector store implementation using PostgreSQL with pgvector extension."""

    def __init__(self, connection_string: str, table_name: str = "document_vectors") -> None:
        """
        Initialize PostgreSQL vector store.
        
        Args:
            connection_string: PostgreSQL connection string
            table_name: Table name for storing vectors
        """
        self.connection_string = connection_string
        self.table_name = table_name
        self._init_pool = None

    async def _get_connection_pool(self):
        """Get or create connection pool."""
        if self._init_pool is None:
            try:
                import asyncpg
                self._init_pool = await asyncpg.create_pool(
                    self.connection_string,
                    min_size=5,
                    max_size=20,
                )
            except ImportError:
                raise ImportError(
                    "asyncpg is required for PostgreSQL vector store. "
                    "Install with: pip install asyncpg"
                )
        return self._init_pool

    async def _ensure_table_exists(self) -> None:
        """Ensure pgvector table exists."""
        pool = await self._get_connection_pool()
        async with pool.acquire() as conn:
            # Enable pgvector extension
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

            # Create vectors table
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    id SERIAL PRIMARY KEY,
                    chunk_id VARCHAR(36) NOT NULL UNIQUE,
                    organization_id VARCHAR(36) NOT NULL,
                    document_id VARCHAR(36),
                    embedding vector(1536),
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX organization_idx (organization_id),
                    INDEX document_idx (document_id),
                    INDEX embedding_idx (embedding vector_cosine_ops)
                )
            """)

    async def upsert(
        self,
        chunk_id: str,
        embedding: list[float],
        metadata: dict,
        organization_id: str,
    ) -> None:
        """Upsert a chunk with embedding."""
        pool = await self._get_connection_pool()

        # Convert embedding list to pgvector format
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        async with pool.acquire() as conn:
            await conn.execute(f"""
                INSERT INTO {self.table_name} 
                (chunk_id, organization_id, document_id, embedding, metadata)
                VALUES ($1, $2, $3, $4::vector, $5)
                ON CONFLICT (chunk_id) DO UPDATE SET
                    embedding = EXCLUDED.embedding,
                    metadata = EXCLUDED.metadata
            """,
                chunk_id,
                organization_id,
                metadata.get("document_id"),
                embedding_str,
                metadata,
            )

    async def search(
        self,
        organization_id: str,
        query_embedding: list[float],
        top_k: int = 5,
        filters: Optional[dict] = None,
    ) -> list[SearchResult]:
        """Search for similar chunks."""
        pool = await self._get_connection_pool()

        # Convert embedding list to pgvector format
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        query = f"""
            SELECT chunk_id, 1 - (embedding <-> $1::vector) as score, metadata
            FROM {self.table_name}
            WHERE organization_id = $2
        """
        params = [embedding_str, organization_id]

        # Add filters if provided
        if filters:
            if "document_id" in filters:
                query += " AND metadata->>'document_id' = $3"
                params.append(filters["document_id"])

        query += f" ORDER BY embedding <-> $1::vector LIMIT {top_k}"

        results = []
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            for row in rows:
                results.append(SearchResult(
                    chunk_id=row["chunk_id"],
                    score=float(row["score"]),
                    metadata=row["metadata"],
                ))

        return results

    async def delete(
        self,
        chunk_id: str,
        organization_id: str,
    ) -> None:
        """Delete a chunk."""
        pool = await self._get_connection_pool()
        async with pool.acquire() as conn:
            await conn.execute(f"""
                DELETE FROM {self.table_name}
                WHERE chunk_id = $1 AND organization_id = $2
            """, chunk_id, organization_id)

    async def delete_by_document(
        self,
        document_id: str,
        organization_id: str,
    ) -> None:
        """Delete all chunks for a document."""
        pool = await self._get_connection_pool()
        async with pool.acquire() as conn:
            await conn.execute(f"""
                DELETE FROM {self.table_name}
                WHERE document_id = $1 AND organization_id = $2
            """, document_id, organization_id)

    async def exists(
        self,
        chunk_id: str,
        organization_id: str,
    ) -> bool:
        """Check if chunk exists."""
        pool = await self._get_connection_pool()
        async with pool.acquire() as conn:
            result = await conn.fetchval(f"""
                SELECT 1 FROM {self.table_name}
                WHERE chunk_id = $1 AND organization_id = $2
            """, chunk_id, organization_id)
            return result is not None
