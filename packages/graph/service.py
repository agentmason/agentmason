"""Business Graph service - entity and relationship CRUD + traversal."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import Session

from apps.api.app.models.graph import (
    GraphEntity,
    GraphRelationship,
    EntityType,
    RelationshipType,
)

logger = logging.getLogger(__name__)


class GraphService:
    """Service for managing the business knowledge graph."""

    def __init__(self, db: Session):
        self.db = db

    # --- Entity CRUD ---

    def create_entity(
        self,
        organization_id: str,
        entity_type: EntityType,
        name: str,
        *,
        description: Optional[str] = None,
        properties: Optional[dict] = None,
        created_by: Optional[str] = None,
    ) -> GraphEntity:
        """Create a new graph entity."""
        entity = GraphEntity(
            id=str(uuid4()),
            organization_id=organization_id,
            entity_type=entity_type,
            name=name,
            description=description,
            properties=properties,
            created_by=created_by,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def get_entity(self, entity_id: str, organization_id: str) -> Optional[GraphEntity]:
        """Get an entity by ID."""
        return self.db.scalar(
            select(GraphEntity).where(
                and_(
                    GraphEntity.id == entity_id,
                    GraphEntity.organization_id == organization_id,
                )
            )
        )

    def search_entities(
        self,
        organization_id: str,
        *,
        query: Optional[str] = None,
        entity_type: Optional[EntityType] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[GraphEntity], int]:
        """Search entities with filters."""
        conditions = [GraphEntity.organization_id == organization_id]

        if entity_type:
            conditions.append(GraphEntity.entity_type == entity_type)
        if query:
            pattern = f"%{query}%"
            conditions.append(
                or_(
                    GraphEntity.name.ilike(pattern),
                    GraphEntity.description.ilike(pattern),
                )
            )

        base = select(GraphEntity).where(and_(*conditions))
        total = self.db.scalar(select(func.count()).select_from(base.subquery()))
        results = self.db.scalars(
            base.order_by(GraphEntity.name).offset(offset).limit(limit)
        ).all()

        return list(results), total or 0

    def update_entity(
        self,
        entity_id: str,
        organization_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        properties: Optional[dict] = None,
    ) -> Optional[GraphEntity]:
        """Update an entity."""
        entity = self.get_entity(entity_id, organization_id)
        if not entity:
            return None
        if name:
            entity.name = name
        if description is not None:
            entity.description = description
        if properties is not None:
            entity.properties = properties
        entity.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def delete_entity(self, entity_id: str, organization_id: str) -> bool:
        """Delete an entity and its relationships."""
        entity = self.get_entity(entity_id, organization_id)
        if not entity:
            return False
        # Delete related relationships
        self.db.execute(
            select(GraphRelationship).where(
                and_(
                    GraphRelationship.organization_id == organization_id,
                    or_(
                        GraphRelationship.source_entity_id == entity_id,
                        GraphRelationship.target_entity_id == entity_id,
                    ),
                )
            )
        )
        # Actually delete relationships
        rels = self.db.scalars(
            select(GraphRelationship).where(
                and_(
                    GraphRelationship.organization_id == organization_id,
                    or_(
                        GraphRelationship.source_entity_id == entity_id,
                        GraphRelationship.target_entity_id == entity_id,
                    ),
                )
            )
        ).all()
        for rel in rels:
            self.db.delete(rel)
        self.db.delete(entity)
        self.db.commit()
        return True

    # --- Relationship CRUD ---

    def create_relationship(
        self,
        organization_id: str,
        source_entity_id: str,
        target_entity_id: str,
        relationship_type: RelationshipType,
        *,
        properties: Optional[dict] = None,
        strength: float = 1.0,
        created_by: Optional[str] = None,
    ) -> Optional[GraphRelationship]:
        """Create a relationship between two entities."""
        # Verify both entities exist and belong to the same org
        source = self.get_entity(source_entity_id, organization_id)
        target = self.get_entity(target_entity_id, organization_id)
        if not source or not target:
            return None

        rel = GraphRelationship(
            id=str(uuid4()),
            organization_id=organization_id,
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            relationship_type=relationship_type,
            properties=properties,
            strength=strength,
            created_by=created_by,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(rel)
        self.db.commit()
        self.db.refresh(rel)
        return rel

    def get_entity_relationships(
        self,
        entity_id: str,
        organization_id: str,
        *,
        relationship_type: Optional[RelationshipType] = None,
        direction: str = "both",  # "outgoing", "incoming", "both"
    ) -> list[dict]:
        """Get relationships for an entity with connected entity info."""
        conditions = [GraphRelationship.organization_id == organization_id]

        if direction == "outgoing":
            conditions.append(GraphRelationship.source_entity_id == entity_id)
        elif direction == "incoming":
            conditions.append(GraphRelationship.target_entity_id == entity_id)
        else:
            conditions.append(
                or_(
                    GraphRelationship.source_entity_id == entity_id,
                    GraphRelationship.target_entity_id == entity_id,
                )
            )

        if relationship_type:
            conditions.append(GraphRelationship.relationship_type == relationship_type)

        rels = self.db.scalars(
            select(GraphRelationship).where(and_(*conditions))
        ).all()

        results = []
        for rel in rels:
            # Get the connected entity
            connected_id = (
                rel.target_entity_id if rel.source_entity_id == entity_id
                else rel.source_entity_id
            )
            connected = self.get_entity(connected_id, organization_id)
            results.append({
                "relationship_id": rel.id,
                "relationship_type": rel.relationship_type.value,
                "direction": "outgoing" if rel.source_entity_id == entity_id else "incoming",
                "connected_entity": {
                    "id": connected.id,
                    "name": connected.name,
                    "entity_type": connected.entity_type.value,
                } if connected else None,
                "properties": rel.properties,
                "strength": rel.strength,
            })

        return results

    def delete_relationship(self, relationship_id: str, organization_id: str) -> bool:
        """Delete a relationship."""
        rel = self.db.scalar(
            select(GraphRelationship).where(
                and_(
                    GraphRelationship.id == relationship_id,
                    GraphRelationship.organization_id == organization_id,
                )
            )
        )
        if not rel:
            return False
        self.db.delete(rel)
        self.db.commit()
        return True

    def get_related_entities(
        self,
        entity_id: str,
        organization_id: str,
        *,
        depth: int = 1,
    ) -> list[dict]:
        """Get entities connected to a given entity (BFS traversal)."""
        visited: set[str] = {entity_id}
        results: list[dict] = []
        current_level = [entity_id]

        for level in range(depth):
            next_level: list[str] = []
            for eid in current_level:
                rels = self.get_entity_relationships(eid, organization_id)
                for rel in rels:
                    connected = rel.get("connected_entity")
                    if connected and connected["id"] not in visited:
                        visited.add(connected["id"])
                        next_level.append(connected["id"])
                        results.append({
                            **connected,
                            "distance": level + 1,
                            "via_relationship": rel["relationship_type"],
                        })
            current_level = next_level
            if not current_level:
                break

        return results
