from __future__ import annotations

import logging
from typing import Optional

from packages.rag.retrieval import RetrievedChunk

logger = logging.getLogger(__name__)


class ContextBuilder:
    """Builder for creating RAG context from retrieved chunks."""

    @staticmethod
    def build_context(
        chunks: list[RetrievedChunk],
        include_scores: bool = False,
    ) -> str:
        """
        Build a formatted context from retrieved chunks.
        
        Args:
            chunks: List of retrieved chunks
            include_scores: Whether to include similarity scores
            
        Returns:
            Formatted context string for the LLM
        """
        if not chunks:
            return ""

        context_parts = []
        context_parts.append("# Retrieved Information from Business Knowledge\n")

        for i, chunk in enumerate(chunks, 1):
            document_name = chunk.document_name or "Unknown Document"
            page = f" — Page {chunk.page_number}" if chunk.page_number else ""

            # Build source header
            source_header = f"Source {i}: {document_name}{page}"
            if include_scores:
                source_header += f" (Relevance: {chunk.score:.2%})"

            context_parts.append(f"\n{source_header}\n")
            context_parts.append("-" * 40)
            context_parts.append(chunk.content)
            context_parts.append("")

        context_parts.append("\n" + "=" * 40)
        context_parts.append("End of Retrieved Information\n")

        return "\n".join(context_parts)

    @staticmethod
    def build_prompt_with_context(
        user_query: str,
        context: str,
        system_instructions: str = "",
    ) -> str:
        """
        Build a complete prompt with context for the LLM.
        
        Args:
            user_query: Original user query
            context: Built context from chunks
            system_instructions: System-level instructions
            
        Returns:
            Formatted prompt for the LLM
        """
        prompt_parts = []

        if system_instructions:
            prompt_parts.append(system_instructions)
            prompt_parts.append("\n" + "=" * 40 + "\n")

        if context:
            prompt_parts.append(context)
            prompt_parts.append("\n" + "=" * 40)
            prompt_parts.append("\nUser Query:")
        else:
            prompt_parts.append("Note: No business knowledge available for this query.")
            prompt_parts.append("\nUser Query:")

        prompt_parts.append(user_query)

        return "\n".join(prompt_parts)

    @staticmethod
    def extract_citations(chunks: list[RetrievedChunk]) -> list[dict]:
        """
        Extract citation information from retrieved chunks.
        
        Args:
            chunks: List of retrieved chunks
            
        Returns:
            List of citation dictionaries
        """
        citations = []
        for i, chunk in enumerate(chunks, 1):
            citation = {
                "citation_number": i,
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "document_name": chunk.document_name,
                "page": chunk.page_number,
                "score": round(chunk.score, 4),
            }
            citations.append(citation)
        return citations
