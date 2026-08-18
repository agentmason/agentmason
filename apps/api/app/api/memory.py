"""Business Memory API routes."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.core.database import get_db
from apps.api.app.models.memory import BusinessMemory, MemoryCategory, MemorySource, MemoryStatus
from apps.api.app.models.membership import Membership
from apps.api.app.models.user import User
from apps.api.app.api.organizations import get_current_user
from packages.memory.service import MemoryService

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Request/Response Schemas ---

class MemoryCreateRequest(BaseModel):
    category: str
    title: str
    content: str
    source: str = "manual"
    structured_data: Optional[dict] = None
    source_reference: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    tags: Optional[list[str]] = None


class MemoryUpdateRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    structured_data: Optional[dict] = None
    status: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    tags: Optional[list[str]] = None
    create_version: bool = False


def _get_org_id(db: Session, user: User) -> str:
    membership = db.scalar(
        select(Membership).where(Membership.user_id == user.id).limit(1)
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No organization access")
    return str(membership.organization_id)


def _memory_to_dict(memory: BusinessMemory) -> dict:
    return {
        "id": memory.id,
        "category": memory.category.value if isinstance(memory.category, MemoryCategory) else memory.category,
        "title": memory.title,
        "content": memory.content,
        "structured_data": memory.structured_data,
        "status": memory.status.value if isinstance(memory.status, MemoryStatus) else memory.status,
        "source": memory.source.value if isinstance(memory.source, MemorySource) else memory.source,
        "source_reference": memory.source_reference,
        "confidence": memory.confidence,
        "version": memory.version,
        "previous_version_id": memory.previous_version_id,
        "tags": memory.tags,
        "created_by": memory.created_by,
        "last_accessed_at": memory.last_accessed_at.isoformat() if memory.last_accessed_at else None,
        "created_at": memory.created_at.isoformat() if memory.created_at else None,
        "updated_at": memory.updated_at.isoformat() if memory.updated_at else None,
    }


# --- Endpoints ---

@router.get("")
async def list_memories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    q: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    """List business memories with optional filters."""
    org_id = _get_org_id(db, current_user)
    service = MemoryService(db)

    cat = MemoryCategory(category) if category else None
    st = MemoryStatus(status_filter) if status_filter else None

    results, total = service.search(
        org_id, query=q, category=cat, status=st, limit=limit, offset=skip
    )

    return {
        "memories": [_memory_to_dict(m) for m in results],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_memory(
    body: MemoryCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Create a new business memory."""
    org_id = _get_org_id(db, current_user)
    service = MemoryService(db)

    try:
        cat = MemoryCategory(body.category)
        src = MemorySource(body.source)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid enum value: {e}")

    # Check for conflicts
    conflicts = service.find_conflicts(org_id, cat, body.title, body.content)
    conflict_info = None
    if conflicts:
        conflict_info = [
            {"id": c.id, "title": c.title, "content": c.content[:200]}
            for c in conflicts[:3]
        ]

    memory = service.create(
        org_id,
        cat,
        body.title,
        body.content,
        src,
        structured_data=body.structured_data,
        source_reference=body.source_reference,
        confidence=body.confidence,
        tags=body.tags,
        created_by=current_user.id,
    )

    result = _memory_to_dict(memory)
    if conflict_info:
        result["potential_conflicts"] = conflict_info
    return result


@router.get("/{memory_id}")
async def get_memory(
    memory_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Get a specific business memory."""
    org_id = _get_org_id(db, current_user)
    service = MemoryService(db)
    memory = service.get(memory_id, org_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    return _memory_to_dict(memory)


@router.patch("/{memory_id}")
async def update_memory(
    memory_id: str,
    body: MemoryUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Update a business memory."""
    org_id = _get_org_id(db, current_user)
    service = MemoryService(db)

    st = MemoryStatus(body.status) if body.status else None

    memory = service.update(
        memory_id,
        org_id,
        title=body.title,
        content=body.content,
        structured_data=body.structured_data,
        status=st,
        confidence=body.confidence,
        tags=body.tags,
        create_version=body.create_version,
    )
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    return _memory_to_dict(memory)


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Delete (deactivate) a business memory."""
    org_id = _get_org_id(db, current_user)
    service = MemoryService(db)
    success = service.delete(memory_id, org_id)
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"message": "Memory deleted successfully"}
