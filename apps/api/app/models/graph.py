from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional
from uuid import uuid4

from sqlalchemy import DateTime, Enum as SQLEnum, Float, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.app.models.base import Base


class EntityType(str, Enum):
    """Types of business entities."""
    COMPANY = "company"
    PERSON = "person"
    EMPLOYEE = "employee"
    CUSTOMER = "customer"
    VENDOR = "vendor"
    PRODUCT = "product"
    SERVICE = "service"
    DEPARTMENT = "department"
    LOCATION = "location"
    PROJECT = "project"
    CONTRACT = "contract"
    ORDER = "order"
    INVOICE = "invoice"
    DOCUMENT = "document"
    PROCESS = "process"
    GOAL = "goal"
    DECISION = "decision"
    BUSINESS_RULE = "business_rule"


class RelationshipType(str, Enum):
    """Types of relationships between entities."""
    OWNS = "owns"
    WORKS_FOR = "works_for"
    MANAGES = "manages"
    SERVES = "serves"
    PURCHASES = "purchases"
    PROVIDES = "provides"
    USES = "uses"
    LOCATED_AT = "located_at"
    RELATED_TO = "related_to"
    DEPENDS_ON = "depends_on"
    PART_OF = "part_of"
    CREATED_BY = "created_by"
    APPROVED_BY = "approved_by"
    GOVERNED_BY = "governed_by"
    ACHIEVES = "achieves"
    REPLACES = "replaces"


class GraphEntity(Base):
    """A node in the business graph."""
    __tablename__ = "graph_entities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    entity_type: Mapped[EntityType] = mapped_column(
        SQLEnum(EntityType), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    properties: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
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
        return f"<GraphEntity(id={self.id}, type={self.entity_type}, name={self.name})>"


class GraphRelationship(Base):
    """An edge in the business graph."""
    __tablename__ = "graph_relationships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    source_entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    target_entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    relationship_type: Mapped[RelationshipType] = mapped_column(
        SQLEnum(RelationshipType), nullable=False, index=True
    )
    properties: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    strength: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    def __repr__(self) -> str:
        return f"<GraphRelationship(id={self.id}, type={self.relationship_type})>"
