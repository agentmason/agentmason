from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ChunkConfig:
    """Configuration for document chunking."""
    chunk_size: int = 800
    chunk_overlap: int = 120
    separator: str = "\n\n"


@dataclass
class Chunk:
    """Represents a document chunk."""
    index: int
    content: str
    metadata: dict


class ChunkingService:
    """Service for splitting documents into chunks."""

    def __init__(self, config: Optional[ChunkConfig] = None) -> None:
        self.config = config or ChunkConfig()

    def chunk(
        self,
        text: str,
        metadata: Optional[dict] = None,
    ) -> list[Chunk]:
        """
        Split document text into chunks.
        
        Args:
            text: Document text to chunk
            metadata: Document metadata (page_number, section, etc.)
            
        Returns:
            List of Chunk objects
        """
        metadata = metadata or {}

        # Split by primary separator
        parts = text.split(self.config.separator)

        chunks_list = []
        current_chunk = ""
        chunk_index = 0

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # If adding this part would exceed chunk size, save current chunk and start new one
            if current_chunk and len(current_chunk) + len(part) > self.config.chunk_size:
                chunks_list.append(current_chunk)
                # Keep overlap with end of previous chunk
                current_chunk = self._get_overlap(current_chunk, part)

            current_chunk += (self.config.separator if current_chunk else "") + part

        # Add final chunk
        if current_chunk.strip():
            chunks_list.append(current_chunk.strip())

        # Convert to Chunk objects with metadata
        chunks = []
        for i, content in enumerate(chunks_list):
            chunk_metadata = metadata.copy()
            chunk_metadata.update({
                "chunk_index": i,
                "total_chunks": len(chunks_list),
            })
            chunks.append(Chunk(index=i, content=content, metadata=chunk_metadata))

        return chunks

    def _get_overlap(self, previous: str, current: str) -> str:
        """Create overlap between chunks to maintain context."""
        if self.config.chunk_overlap <= 0:
            return current

        # Get last N characters from previous chunk as overlap
        overlap = previous[-self.config.chunk_overlap:] if len(previous) > self.config.chunk_overlap else previous
        return overlap + self.config.separator + current

    def estimate_tokens(self, text: str) -> int:
        """
        Rough estimate of token count (for gpt-3.5/4).
        This is a simple approximation: ~4 chars per token.
        """
        return len(text) // 4
