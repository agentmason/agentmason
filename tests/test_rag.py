import pytest

from packages.embeddings.provider import (
    MockEmbeddingProvider,
    OpenAIEmbeddingProvider,
)
from packages.rag.retrieval import RetrievalService, RetrievedChunk
from packages.rag.context import ContextBuilder
from packages.vectorstore import PostgreSQLVectorStore


class TestEmbeddingProviders:
    """Test embedding providers."""

    @pytest.mark.asyncio
    async def test_mock_embedding_provider(self):
        """Test mock embedding provider."""
        provider = MockEmbeddingProvider(dimension=512)

        embedding = await provider.embed_text("Hello world")
        assert len(embedding) == 512
        assert all(-1 <= x <= 1 for x in embedding)

    @pytest.mark.asyncio
    async def test_mock_batch_embedding(self):
        """Test mock batch embedding."""
        provider = MockEmbeddingProvider(dimension=512)

        embeddings = await provider.embed_documents(["Text 1", "Text 2", "Text 3"])
        assert len(embeddings) == 3
        assert all(len(e) == 512 for e in embeddings)

    def test_embedding_dimension(self):
        """Test embedding dimension."""
        provider = MockEmbeddingProvider(dimension=256)
        assert provider.get_embedding_dimension() == 256


class TestContextBuilder:
    """Test RAG context builder."""

    def test_build_context_empty(self):
        """Test building context with empty chunks."""
        context = ContextBuilder.build_context([])
        assert context == ""

    def test_build_context_single_chunk(self):
        """Test building context with single chunk."""
        chunk = RetrievedChunk(
            chunk_id="chunk1",
            content="This is test content",
            score=0.95,
            metadata={
                "document_id": "doc1",
                "document_name": "Test Document.pdf",
                "page_number": 1,
            }
        )

        context = ContextBuilder.build_context([chunk])
        assert "Test Document.pdf" in context
        assert "This is test content" in context

    def test_extract_citations(self):
        """Test citation extraction."""
        chunks = [
            RetrievedChunk(
                chunk_id="chunk1",
                content="Content 1",
                score=0.95,
                metadata={"document_id": "doc1", "document_name": "Doc1.pdf"}
            ),
            RetrievedChunk(
                chunk_id="chunk2",
                content="Content 2",
                score=0.85,
                metadata={"document_id": "doc2", "document_name": "Doc2.pdf"}
            ),
        ]

        citations = ContextBuilder.extract_citations(chunks)
        assert len(citations) == 2
        assert citations[0]["citation_number"] == 1
        assert citations[0]["document_name"] == "Doc1.pdf"
        assert citations[1]["score"] == 0.85

    def test_build_prompt_with_context(self):
        """Test prompt building."""
        chunk = RetrievedChunk(
            chunk_id="chunk1",
            content="Test content",
            score=0.9,
            metadata={"document_id": "doc1", "document_name": "Doc.pdf"}
        )

        context = ContextBuilder.build_context([chunk])
        prompt = ContextBuilder.build_prompt_with_context(
            "What is this about?",
            context
        )

        assert "What is this about?" in prompt
        assert "Test content" in prompt


class TestRetrievalService:
    """Test retrieval service."""

    @pytest.mark.asyncio
    async def test_retrieved_chunk_properties(self):
        """Test RetrievedChunk properties."""
        metadata = {
            "document_id": "doc123",
            "document_name": "Employee Handbook.pdf",
            "page_number": 17,
            "content": "PTO policy details"
        }

        chunk = RetrievedChunk(
            chunk_id="chunk1",
            content="PTO details",
            score=0.92,
            metadata=metadata
        )

        assert chunk.document_id == "doc123"
        assert chunk.document_name == "Employee Handbook.pdf"
        assert chunk.page_number == 17
        assert chunk.score == 0.92

    @pytest.mark.asyncio
    async def test_retrieved_chunk_to_dict(self):
        """Test RetrievedChunk serialization."""
        chunk = RetrievedChunk(
            chunk_id="chunk1",
            content="Test content",
            score=0.88,
            metadata={"document_id": "doc1", "document_name": "Doc.pdf"}
        )

        chunk_dict = chunk.to_dict()
        assert chunk_dict["chunk_id"] == "chunk1"
        assert chunk_dict["score"] == 0.88
        assert chunk_dict["document_name"] == "Doc.pdf"
