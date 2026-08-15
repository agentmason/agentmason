import pytest
import tempfile
from pathlib import Path

from packages.documents import (
    ParserRegistry,
    ParseError,
    TextParser,
    MarkdownParser,
    CSVParser,
    JSONParser,
)
from packages.documents.chunking import ChunkingService, ChunkConfig


class TestParsers:
    """Test document parsers."""

    @pytest.mark.asyncio
    async def test_text_parser(self):
        """Test text file parsing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Hello World\nThis is a test file.")
            f.flush()
            path = f.name

        try:
            result = await TextParser.parse(path, "test.txt")
            assert "Hello World" in result.text
            assert result.metadata["file_name"] == "test.txt"
        finally:
            Path(path).unlink()

    @pytest.mark.asyncio
    async def test_markdown_parser(self):
        """Test markdown file parsing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Heading\n\nThis is markdown content.")
            f.flush()
            path = f.name

        try:
            result = await MarkdownParser.parse(path, "test.md")
            assert "# Heading" in result.text
            assert result.metadata["file_name"] == "test.md"
        finally:
            Path(path).unlink()

    @pytest.mark.asyncio
    async def test_csv_parser(self):
        """Test CSV file parsing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("Name,Age,City\nAlice,30,NYC\nBob,25,LA")
            f.flush()
            path = f.name

        try:
            result = await CSVParser.parse(path, "test.csv")
            assert "Alice" in result.text
            assert "Age" in result.metadata.get("columns", [])
        finally:
            Path(path).unlink()

    @pytest.mark.asyncio
    async def test_json_parser(self):
        """Test JSON file parsing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"key": "value", "number": 42}')
            f.flush()
            path = f.name

        try:
            result = await JSONParser.parse(path, "test.json")
            assert "value" in result.text
            assert result.metadata["format"] == "json"
        finally:
            Path(path).unlink()

    @pytest.mark.asyncio
    async def test_parser_registry(self):
        """Test parser registry."""
        registry = ParserRegistry()

        parser = registry.get_parser("text/plain")
        assert parser == TextParser

        parser = registry.get_parser("application/json")
        assert parser == JSONParser

    @pytest.mark.asyncio
    async def test_unsupported_mime_type(self):
        """Test error on unsupported MIME type."""
        registry = ParserRegistry()

        with pytest.raises(ParseError):
            registry.get_parser("application/unsupported")


class TestChunking:
    """Test document chunking."""

    def test_chunking_basic(self):
        """Test basic chunking."""
        text = "This is a test. " * 100
        service = ChunkingService()

        chunks = service.chunk(text)
        assert len(chunks) > 0
        assert all(chunk.index < len(chunks) for chunk in chunks)

    def test_chunking_preserves_metadata(self):
        """Test that chunking preserves metadata."""
        text = "Content " * 200
        metadata = {"document_id": "doc123", "source": "test"}

        service = ChunkingService()
        chunks = service.chunk(text, metadata)

        for chunk in chunks:
            assert "document_id" in chunk.metadata
            assert chunk.metadata["document_id"] == "doc123"
            assert "chunk_index" in chunk.metadata

    def test_token_estimation(self):
        """Test token count estimation."""
        text = "Hello world" * 100
        service = ChunkingService()

        token_count = service.estimate_tokens(text)
        assert token_count > 0
        # Rough check: ~4 chars per token
        assert 200 < token_count < 400

    def test_custom_chunk_config(self):
        """Test with custom chunk configuration."""
        text = "Word " * 500
        config = ChunkConfig(chunk_size=100, chunk_overlap=20)
        service = ChunkingService(config)

        chunks = service.chunk(text)
        # With smaller chunk size, should have more chunks
        assert len(chunks) > 3
