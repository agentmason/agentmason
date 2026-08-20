"""Shared context builder — assembles minimal, permission-aware context for agents."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from apps.api.app.models.orchestration import SpecializedAgent

logger = logging.getLogger(__name__)


class SharedContextBuilder:
    """Builds scoped context for agent tasks based on agent permissions and data sources."""

    def __init__(
        self,
        db: Session,
        memory_service: Any | None = None,
        graph_service: Any | None = None,
        rag_retrieval: Any | None = None,
    ) -> None:
        self.db = db
        self.memory_service = memory_service
        self.graph_service = graph_service
        self.rag_retrieval = rag_retrieval

    async def build_context(
        self,
        agent: SpecializedAgent,
        organization_id: str,
        objective: str,
        additional_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build minimal, permission-aware context for an agent task.

        Only includes data sources the agent is allowed to access.
        """
        context: dict[str, Any] = {
            "objective": objective,
            "agent_type": agent.agent_type,
            "agent_permissions": agent.permissions or [],
        }

        allowed_sources = set(agent.allowed_data_sources or [])

        # Memory context
        if "memory" in allowed_sources and self.memory_service:
            try:
                memories = await self._fetch_relevant_memories(
                    organization_id, objective
                )
                context["business_memory"] = memories
            except Exception as exc:
                logger.warning("Failed to fetch memory context for %s: %s", agent.name, exc)
                context["business_memory"] = []

        # Graph context
        if "graph" in allowed_sources and self.graph_service:
            try:
                graph_data = await self._fetch_relevant_graph(
                    organization_id, objective
                )
                context["business_graph"] = graph_data
            except Exception as exc:
                logger.warning("Failed to fetch graph context for %s: %s", agent.name, exc)
                context["business_graph"] = []

        # Document/RAG context
        if "documents" in allowed_sources and self.rag_retrieval:
            try:
                docs = await self._fetch_relevant_documents(
                    organization_id, objective
                )
                context["documents"] = docs
            except Exception as exc:
                logger.warning("Failed to fetch document context for %s: %s", agent.name, exc)
                context["documents"] = []

        # Additional context passed in from orchestrator or previous agents
        if additional_context:
            context["additional"] = additional_context

        return context

    async def _fetch_relevant_memories(
        self, organization_id: str, query: str
    ) -> list[dict[str, Any]]:
        """Fetch relevant business memories."""
        if not self.memory_service:
            return []
        memories = self.memory_service.search(
            organization_id=organization_id, query=query, limit=10
        )
        return [
            {
                "title": m.title,
                "content": m.content,
                "category": m.category.value if hasattr(m.category, "value") else str(m.category),
                "confidence": m.confidence,
                "source": m.source.value if hasattr(m.source, "value") else str(m.source),
            }
            for m in memories
        ]

    async def _fetch_relevant_graph(
        self, organization_id: str, query: str
    ) -> list[dict[str, Any]]:
        """Fetch relevant graph entities."""
        if not self.graph_service:
            return []
        entities = self.graph_service.search_entities(
            organization_id=organization_id, query=query, limit=10
        )
        return [
            {
                "name": e.name,
                "type": e.entity_type.value if hasattr(e.entity_type, "value") else str(e.entity_type),
                "description": e.description,
                "properties": e.properties,
            }
            for e in entities
        ]

    async def _fetch_relevant_documents(
        self, organization_id: str, query: str
    ) -> list[dict[str, Any]]:
        """Fetch relevant document chunks via RAG."""
        if not self.rag_retrieval:
            return []
        chunks = await self.rag_retrieval.retrieve(
            organization_id=organization_id, query=query, top_k=5
        )
        return [
            {
                "content": c.content,
                "score": c.score,
                "metadata": c.metadata,
            }
            for c in chunks
        ]
