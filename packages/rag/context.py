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

    @staticmethod
    def build_memory_context(memories: list) -> str:
        """
        Build context from business memories for inclusion in prompts.
        
        Args:
            memories: List of BusinessMemory objects
            
        Returns:
            Formatted memory context string
        """
        if not memories:
            return ""

        parts = ["# Relevant Business Memory\n"]
        for i, memory in enumerate(memories, 1):
            category = memory.category.value if hasattr(memory.category, 'value') else memory.category
            parts.append(f"\n[{category.replace('_', ' ').title()}] {memory.title}")
            parts.append(f"  {memory.content}")
            if memory.source_reference:
                parts.append(f"  Source: {memory.source_reference}")
            parts.append("")

        parts.append("=" * 40)
        parts.append("End of Business Memory\n")
        return "\n".join(parts)

    @staticmethod
    def build_combined_context(
        user_query: str,
        chunks: list[RetrievedChunk] = None,
        memories: list = None,
        graph_context: list[dict] = None,
        system_instructions: str = "",
    ) -> str:
        """
        Build a combined prompt with RAG chunks, business memory, and graph context.
        """
        prompt_parts = []

        if system_instructions:
            prompt_parts.append(system_instructions)
            prompt_parts.append("\n" + "=" * 40 + "\n")

        if memories:
            prompt_parts.append(ContextBuilder.build_memory_context(memories))

        if chunks:
            prompt_parts.append(ContextBuilder.build_context(chunks))

        if graph_context:
            prompt_parts.append("\n# Relevant Business Relationships\n")
            for item in graph_context:
                prompt_parts.append(f"- {item.get('name', 'Unknown')} ({item.get('entity_type', '')}) "
                                   f"[via: {item.get('via_relationship', 'related')}]")
            prompt_parts.append("\n" + "=" * 40 + "\n")

        if not chunks and not memories and not graph_context:
            prompt_parts.append("Note: No additional business context available for this query.")

        prompt_parts.append("\nUser Query:")
        prompt_parts.append(user_query)

        return "\n".join(prompt_parts)
