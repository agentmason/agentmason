from __future__ import annotations

import logging
from typing import Any, Optional

from packages.tools.base import Tool, ToolPermission, ToolError
from packages.rag.retrieval import RetrievalService, RetrievedChunk
from packages.rag.context import ContextBuilder

logger = logging.getLogger(__name__)


class SearchBusinessKnowledgeTool(Tool):
    """Tool for searching business knowledge using RAG."""

    name = "search_business_knowledge"
    description = "Search the organization's connected business knowledge for relevant information."
    permission = ToolPermission.READ
    requires_approval = False

    def __init__(self, retrieval_service: RetrievalService) -> None:
        """
        Initialize the search tool.
        
        Args:
            retrieval_service: RetrievalService instance for searching
        """
        self.retrieval_service = retrieval_service

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """
        Execute the search tool.
        
        Args:
            input_data: Dictionary containing:
                - query: Search query string
                - organization_id: Organization ID
                - top_k: Number of top results (optional, default 5)
                - filters: Metadata filters (optional)
                
        Returns:
            Dictionary containing:
                - results: List of retrieved chunks
                - citations: Citation information
                - context: Formatted context for LLM
        """
        try:
            query = input_data.get("query")
            organization_id = input_data.get("organization_id")
            top_k = input_data.get("top_k", 5)
            filters = input_data.get("filters")

            if not query:
                raise ToolError("Query parameter is required")

            if not organization_id:
                raise ToolError("Organization ID is required")

            # Retrieve relevant chunks
            logger.info(f"Searching business knowledge for: {query[:100]}")
            chunks: list[RetrievedChunk] = await self.retrieval_service.retrieve(
                organization_id=organization_id,
                query=query,
                top_k=top_k,
                filters=filters,
            )

            if not chunks:
                return {
                    "results": [],
                    "citations": [],
                    "context": "",
                    "message": "No relevant documents found in business knowledge.",
                }

            # Build context
            context = ContextBuilder.build_context(chunks)

            # Extract citations
            citations = ContextBuilder.extract_citations(chunks)

            return {
                "results": [chunk.to_dict() for chunk in chunks],
                "citations": citations,
                "context": context,
                "message": f"Found {len(chunks)} relevant document(s).",
            }

        except ToolError:
            raise
        except Exception as e:
            logger.error(f"Search tool failed: {str(e)}")
            raise ToolError(f"Failed to search business knowledge: {str(e)}") from e
