"""Agent tool for querying the business graph."""

from __future__ import annotations

from typing import Any

from packages.tools.base import Tool, ToolPermission
from packages.graph.service import GraphService
from apps.api.app.models.graph import EntityType, RelationshipType


class SearchBusinessGraphTool(Tool):
    """Search business entities in the knowledge graph."""

    name = "search_business_graph"
    description = (
        "Search the business graph for entities like people, companies, departments, "
        "products, vendors, contracts, and their relationships. Use when you need to "
        "understand business structure or find related entities."
    )
    permission = ToolPermission.READ
    requires_approval = False

    def __init__(self, db_session_factory):
        self.db_session_factory = db_session_factory

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        query = input_data.get("query", "")
        organization_id = input_data.get("organization_id")
        entity_type = input_data.get("entity_type")

        if not organization_id:
            return {"error": "organization_id is required"}

        db = self.db_session_factory()
        try:
            service = GraphService(db)
            et = None
            if entity_type:
                try:
                    et = EntityType(entity_type)
                except ValueError:
                    pass

            entities, total = service.search_entities(
                organization_id, query=query, entity_type=et, limit=20
            )

            results = []
            for e in entities:
                results.append({
                    "id": e.id,
                    "entity_type": e.entity_type.value,
                    "name": e.name,
                    "description": e.description,
                    "properties": e.properties,
                })

            return {
                "results": results,
                "total": total,
                "message": f"Found {len(results)} business entities.",
            }
        finally:
            db.close()


class GetRelatedEntitiesTool(Tool):
    """Get entities related to a specific entity in the business graph."""

    name = "get_related_entities"
    description = (
        "Get entities related to a specific entity through the business graph. "
        "Useful for understanding organizational hierarchy, dependencies, and connections."
    )
    permission = ToolPermission.READ
    requires_approval = False

    def __init__(self, db_session_factory):
        self.db_session_factory = db_session_factory

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        entity_id = input_data.get("entity_id")
        organization_id = input_data.get("organization_id")
        depth = input_data.get("depth", 1)

        if not entity_id or not organization_id:
            return {"error": "entity_id and organization_id are required"}

        db = self.db_session_factory()
        try:
            service = GraphService(db)
            entity = service.get_entity(entity_id, organization_id)
            if not entity:
                return {"error": "Entity not found"}

            related = service.get_related_entities(entity_id, organization_id, depth=min(depth, 3))
            relationships = service.get_entity_relationships(entity_id, organization_id)

            return {
                "entity": {
                    "id": entity.id,
                    "name": entity.name,
                    "entity_type": entity.entity_type.value,
                },
                "relationships": relationships,
                "related_entities": related,
                "message": f"Found {len(related)} related entities.",
            }
        finally:
            db.close()
