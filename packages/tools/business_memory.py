"""Agent tool for searching and managing business memory."""

from __future__ import annotations

from typing import Any

from packages.tools.base import Tool, ToolPermission
from packages.memory.service import MemoryService
from apps.api.app.models.memory import MemoryCategory


class SearchBusinessMemoryTool(Tool):
    """Search business memories relevant to a query."""

    name = "search_business_memory"
    description = (
        "Search the business's long-term memory for relevant facts, rules, decisions, "
        "preferences, goals, and processes. Use when you need context about the business "
        "that may have been learned from previous conversations or documents."
    )
    permission = ToolPermission.READ
    requires_approval = False

    def __init__(self, db_session_factory):
        self.db_session_factory = db_session_factory

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        query = input_data.get("query", "")
        organization_id = input_data.get("organization_id")
        category = input_data.get("category")
        limit = input_data.get("limit", 10)

        if not query or not organization_id:
            return {"error": "query and organization_id are required"}

        db = self.db_session_factory()
        try:
            service = MemoryService(db)
            categories = None
            if category:
                try:
                    categories = [MemoryCategory(category)]
                except ValueError:
                    pass

            memories = service.get_relevant_memories(
                organization_id, query, categories=categories, limit=limit
            )

            results = []
            for m in memories:
                results.append({
                    "id": m.id,
                    "category": m.category.value,
                    "title": m.title,
                    "content": m.content,
                    "confidence": m.confidence,
                    "source": m.source.value,
                    "source_reference": m.source_reference,
                    "tags": m.tags,
                })

            return {
                "results": results,
                "count": len(results),
                "message": f"Found {len(results)} relevant business memory(ies).",
            }
        finally:
            db.close()


class CreateBusinessMemoryTool(Tool):
    """Create a new business memory from a conversation or task."""

    name = "create_business_memory"
    description = (
        "Store a new business memory (fact, rule, decision, preference, goal, or process). "
        "Use when the user shares important business information that should be remembered."
    )
    permission = ToolPermission.WRITE
    requires_approval = False

    def __init__(self, db_session_factory):
        self.db_session_factory = db_session_factory

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        organization_id = input_data.get("organization_id")
        category = input_data.get("category")
        title = input_data.get("title")
        content = input_data.get("content")

        if not all([organization_id, category, title, content]):
            return {"error": "organization_id, category, title, and content are required"}

        from apps.api.app.models.memory import MemorySource
        db = self.db_session_factory()
        try:
            service = MemoryService(db)
            try:
                cat = MemoryCategory(category)
            except ValueError:
                return {"error": f"Invalid category: {category}"}

            memory = service.create(
                organization_id,
                cat,
                title,
                content,
                MemorySource.AGENT_EXTRACTION,
                confidence=input_data.get("confidence", 0.8),
                tags=input_data.get("tags", ["agent-created"]),
            )
            return {
                "id": memory.id,
                "title": memory.title,
                "message": "Business memory created successfully.",
            }
        finally:
            db.close()
