from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from uuid import uuid4

from sqlalchemy import DateTime, Enum as SQLEnum, Float, Integer, String, Text, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.app.models.base import Base


class MemoryCategory(str, Enum):
    """Category of business memory."""
    BUSINESS_FACT = "business_fact"
    PREFERENCE = "preference"
    GOAL = "goal"
    DECISION = "decision"
    PROCESS = "process"
    BUSINESS_RULE = "business_rule"


class MemoryStatus(str, Enum):
    """Status of a memory."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    OUTDATED = "outdated"
    CONFLICTED = "conflicted"


class MemorySource(str, Enum):
    """How the memory was created."""
    USER_INPUT = "user_input"
    CONVERSATION = "conversation"
    DOCUMENT = "document"
    INTEGRATION = "integration"
    AGENT_EXTRACTION = "agent_extraction"
    MANUAL = "manual"


class BusinessMemory(Base):
    """Model for persistent business memory."""
    __tablename__ = "business_memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    category: Mapped[MemoryCategory] = mapped_column(
        SQLEnum(MemoryCategory), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    structured_data: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[MemoryStatus] = mapped_column(
        SQLEnum(MemoryStatus), default=MemoryStatus.ACTIVE, nullable=False, index=True
    )
    source: Mapped[MemorySource] = mapped_column(
        SQLEnum(MemorySource), nullable=False
    )
    source_reference: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    previous_version_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    tags: Mapped[Optional[List]] = mapped_column(JSON, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    last_accessed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    def __repr__(self) -> str:
        return f"<BusinessMemory(id={self.id}, category={self.category}, title={self.title[:40]})>"
