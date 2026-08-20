"""Business configuration model — tenant-level business setup.

Stores configurable business profile so the platform is never hard-coded
to a single company.  Swap the seed data to onboard a different customer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import DateTime, JSON, String, Text, Boolean, Float
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.app.models.base import Base


# ── Business Config ─────────────────────────────────────────────────────

class BusinessConfig(Base):
    """Tenant-level business configuration."""

    __tablename__ = "business_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, unique=True)

    # Company identity
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    business_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tagline: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Structured lists (JSON)
    departments: Mapped[Optional[List]] = mapped_column(JSON, nullable=True)          # ["Executive", "Sales", ...]
    business_activities: Mapped[Optional[List]] = mapped_column(JSON, nullable=True)  # ["Software development", ...]
    goals: Mapped[Optional[List[Dict]]] = mapped_column(JSON, nullable=True)          # [{name, description, category}]
    kpis: Mapped[Optional[List[Dict]]] = mapped_column(JSON, nullable=True)           # [{name, unit, target, category}]

    # Demo mode
    demo_mode: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


# ── KPI Records ─────────────────────────────────────────────────────────

class BusinessKPI(Base):
    """Individual KPI data point, time-series friendly."""

    __tablename__ = "business_kpis"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)   # revenue, sales, operations, ...
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)        # $, %, count, hours, ...
    target: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    trend: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # up, down, flat
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    period: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)  # 2026-08, Q3-2026, etc.

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )


# ── Business Inbox ──────────────────────────────────────────────────────

class BusinessInboxItem(Base):
    """Central inbox for AgentMason-generated business events."""

    __tablename__ = "business_inbox"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    category: Mapped[str] = mapped_column(String(50), nullable=False)  # needs_attention, needs_approval, opportunity, risk, completed, information
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")  # critical, high, medium, low
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommended_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    why_it_matters: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    agent_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    workflow_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    data_sources: Mapped[Optional[List]] = mapped_column(JSON, nullable=True)

    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open")  # open, acknowledged, resolved, dismissed
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


# ── Agent Activity Log ──────────────────────────────────────────────────

class AgentActivity(Base):
    """Log of agent actions for the 'What AgentMason Did' view."""

    __tablename__ = "agent_activities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(500), nullable=False)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    workflow_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    data_sources: Mapped[Optional[List]] = mapped_column(JSON, nullable=True)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )


# ── Business Metrics (value/impact) ─────────────────────────────────────

class BusinessMetric(Base):
    """AgentMason impact / value-generated metrics."""

    __tablename__ = "business_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    metric_name: Mapped[str] = mapped_column(String(255), nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    metric_unit: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False, default="estimated")  # actual, estimated, potential
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )
