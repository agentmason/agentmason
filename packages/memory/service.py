"""Business Memory service - CRUD operations and lifecycle management."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import Session

from apps.api.app.models.memory import (
    BusinessMemory,
    MemoryCategory,
    MemorySource,
    MemoryStatus,
)

logger = logging.getLogger(__name__)


class MemoryConflict:
    """Represents a conflict between new and existing memory."""

    def __init__(self, existing: BusinessMemory, new_content: str, new_title: str):
        self.existing = existing
        self.new_content = new_content
        self.new_title = new_title


class MemoryService:
    """Service for managing business memories with lifecycle support."""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        organization_id: str,
        category: MemoryCategory,
        title: str,
        content: str,
        source: MemorySource,
        *,
        structured_data: Optional[dict] = None,
        source_reference: Optional[str] = None,
        confidence: float = 1.0,
        tags: Optional[list[str]] = None,
        created_by: Optional[str] = None,
    ) -> BusinessMemory:
        """Create a new business memory."""
        memory = BusinessMemory(
            id=str(uuid4()),
            organization_id=organization_id,
            category=category,
            title=title,
            content=content,
            structured_data=structured_data,
            status=MemoryStatus.ACTIVE,
            source=source,
            source_reference=source_reference,
            confidence=confidence,
            version=1,
            tags=tags,
            created_by=created_by,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(memory)
        self.db.commit()
        self.db.refresh(memory)
        logger.info(f"Created memory {memory.id} for org {organization_id}")
        return memory

    def get(self, memory_id: str, organization_id: str) -> Optional[BusinessMemory]:
        """Get a memory by ID, updating last_accessed_at."""
        memory = self.db.scalar(
            select(BusinessMemory).where(
                and_(
                    BusinessMemory.id == memory_id,
                    BusinessMemory.organization_id == organization_id,
                )
            )
        )
        if memory:
            memory.last_accessed_at = datetime.now(timezone.utc)
            self.db.commit()
        return memory

    def search(
        self,
        organization_id: str,
        *,
        query: Optional[str] = None,
        category: Optional[MemoryCategory] = None,
        status: Optional[MemoryStatus] = None,
        tags: Optional[list[str]] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[BusinessMemory], int]:
        """Search memories with filters. Returns (results, total_count)."""
        conditions = [BusinessMemory.organization_id == organization_id]

        if category:
            conditions.append(BusinessMemory.category == category)
        if status:
            conditions.append(BusinessMemory.status == status)
        else:
            # Default to active memories
            conditions.append(BusinessMemory.status == MemoryStatus.ACTIVE)

        if query:
            like_pattern = f"%{query}%"
            conditions.append(
                or_(
                    BusinessMemory.title.ilike(like_pattern),
                    BusinessMemory.content.ilike(like_pattern),
                )
            )

        base_query = select(BusinessMemory).where(and_(*conditions))
        total = self.db.scalar(
            select(func.count()).select_from(base_query.subquery())
        )

        results = self.db.scalars(
            base_query.order_by(BusinessMemory.updated_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()

        return list(results), total or 0

    def update(
        self,
        memory_id: str,
        organization_id: str,
        *,
        title: Optional[str] = None,
        content: Optional[str] = None,
        structured_data: Optional[dict] = None,
        status: Optional[MemoryStatus] = None,
        confidence: Optional[float] = None,
        tags: Optional[list[str]] = None,
        create_version: bool = False,
    ) -> Optional[BusinessMemory]:
        """Update a memory. Optionally create a new version."""
        memory = self.db.scalar(
            select(BusinessMemory).where(
                and_(
                    BusinessMemory.id == memory_id,
                    BusinessMemory.organization_id == organization_id,
                )
            )
        )
        if not memory:
            return None

        if create_version and (content or title):
            # Create new version, mark old as outdated
            new_memory = BusinessMemory(
                id=str(uuid4()),
                organization_id=organization_id,
                category=memory.category,
                title=title or memory.title,
                content=content or memory.content,
                structured_data=structured_data if structured_data is not None else memory.structured_data,
                status=MemoryStatus.ACTIVE,
                source=memory.source,
                source_reference=memory.source_reference,
                confidence=confidence if confidence is not None else memory.confidence,
                version=memory.version + 1,
                previous_version_id=memory.id,
                tags=tags if tags is not None else memory.tags,
                created_by=memory.created_by,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            memory.status = MemoryStatus.OUTDATED
            self.db.add(new_memory)
            self.db.commit()
            self.db.refresh(new_memory)
            return new_memory

        # In-place update
        if title:
            memory.title = title
        if content:
            memory.content = content
        if structured_data is not None:
            memory.structured_data = structured_data
        if status:
            memory.status = status
        if confidence is not None:
            memory.confidence = confidence
        if tags is not None:
            memory.tags = tags
        memory.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(memory)
        return memory

    def delete(self, memory_id: str, organization_id: str) -> bool:
        """Delete a memory (soft delete by marking inactive)."""
        memory = self.db.scalar(
            select(BusinessMemory).where(
                and_(
                    BusinessMemory.id == memory_id,
                    BusinessMemory.organization_id == organization_id,
                )
            )
        )
        if not memory:
            return False
        memory.status = MemoryStatus.INACTIVE
        memory.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        return True

    def hard_delete(self, memory_id: str, organization_id: str) -> bool:
        """Permanently delete a memory."""
        memory = self.db.scalar(
            select(BusinessMemory).where(
                and_(
                    BusinessMemory.id == memory_id,
                    BusinessMemory.organization_id == organization_id,
                )
            )
        )
        if not memory:
            return False
        self.db.delete(memory)
        self.db.commit()
        return True

    def find_conflicts(
        self,
        organization_id: str,
        category: MemoryCategory,
        title: str,
        content: str,
    ) -> list[BusinessMemory]:
        """Find existing memories that may conflict with new information."""
        like_pattern = f"%{title.split()[0] if title.split() else title}%"
        existing = self.db.scalars(
            select(BusinessMemory).where(
                and_(
                    BusinessMemory.organization_id == organization_id,
                    BusinessMemory.category == category,
                    BusinessMemory.status == MemoryStatus.ACTIVE,
                    or_(
                        BusinessMemory.title.ilike(like_pattern),
                        BusinessMemory.title.ilike(f"%{title}%"),
                    ),
                )
            )
        ).all()
        return list(existing)

    def get_relevant_memories(
        self,
        organization_id: str,
        query: str,
        *,
        categories: Optional[list[MemoryCategory]] = None,
        limit: int = 10,
    ) -> list[BusinessMemory]:
        """Get memories relevant to a query (text-based search for now)."""
        conditions = [
            BusinessMemory.organization_id == organization_id,
            BusinessMemory.status == MemoryStatus.ACTIVE,
        ]
        if categories:
            conditions.append(BusinessMemory.category.in_(categories))

        # Simple keyword search - could be enhanced with embeddings later
        words = [w for w in query.split() if len(w) > 3]
        if words:
            word_conditions = []
            for word in words[:5]:  # Limit to first 5 meaningful words
                pattern = f"%{word}%"
                word_conditions.append(
                    or_(
                        BusinessMemory.title.ilike(pattern),
                        BusinessMemory.content.ilike(pattern),
                    )
                )
            if word_conditions:
                conditions.append(or_(*word_conditions))

        results = self.db.scalars(
            select(BusinessMemory)
            .where(and_(*conditions))
            .order_by(BusinessMemory.confidence.desc(), BusinessMemory.updated_at.desc())
            .limit(limit)
        ).all()

        # Update last_accessed_at for retrieved memories
        for memory in results:
            memory.last_accessed_at = datetime.now(timezone.utc)
        if results:
            self.db.commit()

        return list(results)
