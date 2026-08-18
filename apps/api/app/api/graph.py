"""Business Graph API routes."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.core.database import get_db
from apps.api.app.models.graph import GraphEntity, GraphRelationship, EntityType, RelationshipType
from apps.api.app.models.membership import Membership
from apps.api.app.models.user import User
from apps.api.app.api.organizations import get_current_user
from packages.graph.service import GraphService

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Request/Response Schemas ---

class EntityCreateRequest(BaseModel):
    entity_type: str
    name: str
    description: Optional[str] = None
    properties: Optional[dict] = None


class EntityUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    properties: Optional[dict] = None


class RelationshipCreateRequest(BaseModel):
    source_entity_id: str
    target_entity_id: str
    relationship_type: str
    properties: Optional[dict] = None
    strength: float = Field(default=1.0, ge=0.0, le=1.0)


def _get_org_id(db: Session, user: User) -> str:
    membership = db.scalar(
        select(Membership).where(Membership.user_id == user.id).limit(1)
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No organization access")
    return str(membership.organization_id)


def _entity_to_dict(entity: GraphEntity) -> dict:
    return {
        "id": entity.id,
        "entity_type": entity.entity_type.value if isinstance(entity.entity_type, EntityType) else entity.entity_type,
        "name": entity.name,
        "description": entity.description,
        "properties": entity.properties,
        "created_by": entity.created_by,
        "created_at": entity.created_at.isoformat() if entity.created_at else None,
        "updated_at": entity.updated_at.isoformat() if entity.updated_at else None,
    }


def _relationship_to_dict(rel: GraphRelationship) -> dict:
    return {
        "id": rel.id,
        "source_entity_id": rel.source_entity_id,
        "target_entity_id": rel.target_entity_id,
        "relationship_type": rel.relationship_type.value if isinstance(rel.relationship_type, RelationshipType) else rel.relationship_type,
        "properties": rel.properties,
        "strength": rel.strength,
        "created_at": rel.created_at.isoformat() if rel.created_at else None,
    }


# --- Entity Endpoints ---

@router.get("/entities")
async def list_entities(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    q: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    """List business graph entities."""
    org_id = _get_org_id(db, current_user)
    service = GraphService(db)

    et = EntityType(entity_type) if entity_type else None
    results, total = service.search_entities(
        org_id, query=q, entity_type=et, limit=limit, offset=skip
    )

    return {
        "entities": [_entity_to_dict(e) for e in results],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.post("/entities", status_code=status.HTTP_201_CREATED)
async def create_entity(
    body: EntityCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Create a new graph entity."""
    org_id = _get_org_id(db, current_user)
    service = GraphService(db)

    try:
        et = EntityType(body.entity_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid entity_type: {body.entity_type}")

    entity = service.create_entity(
        org_id, et, body.name,
        description=body.description,
        properties=body.properties,
        created_by=current_user.id,
    )
    return _entity_to_dict(entity)


@router.get("/entities/{entity_id}")
async def get_entity(
    entity_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Get a specific entity with its details."""
    org_id = _get_org_id(db, current_user)
    service = GraphService(db)
    entity = service.get_entity(entity_id, org_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return _entity_to_dict(entity)


@router.patch("/entities/{entity_id}")
async def update_entity(
    entity_id: str,
    body: EntityUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Update an entity."""
    org_id = _get_org_id(db, current_user)
    service = GraphService(db)
    entity = service.update_entity(
        entity_id, org_id,
        name=body.name, description=body.description, properties=body.properties
    )
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return _entity_to_dict(entity)


@router.delete("/entities/{entity_id}")
async def delete_entity(
    entity_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Delete an entity and all its relationships."""
    org_id = _get_org_id(db, current_user)
    service = GraphService(db)
    success = service.delete_entity(entity_id, org_id)
    if not success:
        raise HTTPException(status_code=404, detail="Entity not found")
    return {"message": "Entity deleted successfully"}


@router.get("/entities/{entity_id}/relationships")
async def get_entity_relationships(
    entity_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    relationship_type: Optional[str] = Query(None),
    direction: str = Query("both", pattern="^(outgoing|incoming|both)$"),
) -> dict:
    """Get relationships for a specific entity."""
    org_id = _get_org_id(db, current_user)
    service = GraphService(db)

    # Verify entity exists
    entity = service.get_entity(entity_id, org_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    rt = RelationshipType(relationship_type) if relationship_type else None
    relationships = service.get_entity_relationships(
        entity_id, org_id, relationship_type=rt, direction=direction
    )

    return {
        "entity": _entity_to_dict(entity),
        "relationships": relationships,
    }


@router.get("/entities/{entity_id}/related")
async def get_related_entities(
    entity_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    depth: int = Query(1, ge=1, le=3),
) -> dict:
    """Get entities connected to a given entity (graph traversal)."""
    org_id = _get_org_id(db, current_user)
    service = GraphService(db)

    entity = service.get_entity(entity_id, org_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    related = service.get_related_entities(entity_id, org_id, depth=depth)
    return {
        "entity": _entity_to_dict(entity),
        "related": related,
    }


# --- Relationship Endpoints ---

@router.post("/relationships", status_code=status.HTTP_201_CREATED)
async def create_relationship(
    body: RelationshipCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Create a relationship between two entities."""
    org_id = _get_org_id(db, current_user)
    service = GraphService(db)

    try:
        rt = RelationshipType(body.relationship_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid relationship_type: {body.relationship_type}")

    rel = service.create_relationship(
        org_id,
        body.source_entity_id,
        body.target_entity_id,
        rt,
        properties=body.properties,
        strength=body.strength,
        created_by=current_user.id,
    )
    if not rel:
        raise HTTPException(status_code=404, detail="Source or target entity not found")
    return _relationship_to_dict(rel)


@router.delete("/relationships/{relationship_id}")
async def delete_relationship(
    relationship_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Delete a relationship."""
    org_id = _get_org_id(db, current_user)
    service = GraphService(db)
    success = service.delete_relationship(relationship_id, org_id)
    if not success:
        raise HTTPException(status_code=404, detail="Relationship not found")
    return {"message": "Relationship deleted successfully"}
