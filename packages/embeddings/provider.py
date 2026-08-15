from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """
        Embed a single text string.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding
        """
        pass

    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """
        Embed multiple texts in batch.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embeddings (each embedding is a list of floats)
        """
        pass

    @abstractmethod
    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings from this provider."""
        pass


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embedding provider using text-embedding-3-small."""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small") -> None:
        """
        Initialize OpenAI embedding provider.
        
        Args:
            api_key: OpenAI API key
            model: Model to use (default: text-embedding-3-small)
        """
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError("openai is required for OpenAI embeddings. Install with: pip install openai")

        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self._embedding_dimension = 1536  # text-embedding-3-small dimension

    async def embed_text(self, text: str) -> list[float]:
        """Embed a single text string."""
        embeddings = await self.embed_documents([text])
        return embeddings[0]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in batch."""
        if not texts:
            return []

        try:
            # Clean and truncate texts if needed
            cleaned_texts = [
                text.replace("\n", " ").strip()[:8000]  # Max 8000 chars per OpenAI limits
                for text in texts
            ]

            response = await self.client.embeddings.create(
                model=self.model,
                input=cleaned_texts,
            )

            # Sort by index to maintain order
            embeddings = sorted(response.data, key=lambda x: x.index)
            return [embedding.embedding for embedding in embeddings]
        except Exception as e:
            logger.error(f"Failed to embed documents with OpenAI: {str(e)}")
            raise

    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings from OpenAI."""
        return self._embedding_dimension


class MockEmbeddingProvider(EmbeddingProvider):
    """Mock embedding provider for testing (returns random vectors)."""

    def __init__(self, dimension: int = 1536) -> None:
        """
        Initialize mock embedding provider.
        
        Args:
            dimension: Dimension of embeddings to generate
        """
        self._embedding_dimension = dimension

    async def embed_text(self, text: str) -> list[float]:
        """Generate mock embedding for single text."""
        import hashlib
        # Use hash to generate deterministic but varied embeddings
        hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
        import random
        random.seed(hash_val)
        return [random.uniform(-1, 1) for _ in range(self._embedding_dimension)]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate mock embeddings for multiple texts."""
        embeddings = []
        for text in texts:
            embeddings.append(await self.embed_text(text))
        return embeddings

    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings."""
        return self._embedding_dimension
