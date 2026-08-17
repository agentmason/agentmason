from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.app.models.base import Base


class IntegrationStatus(str, Enum):
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    ERROR = "ERROR"
    REAUTH_REQUIRED = "REAUTH_REQUIRED"
    SYNCING = "SYNCING"


class OAuthCredential(Base):
    __tablename__ = "oauth_credentials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    integration_id: Mapped[str] = mapped_column(String(36), ForeignKey("integrations.id"), nullable=False, index=True)
    encrypted_access_token: Mapped[str] = mapped_column(String(4096), nullable=False)
    encrypted_refresh_token: Mapped[Optional[str]] = mapped_column(String(4096), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    scopes: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    integration = relationship("Integration", back_populates="credential")


class Integration(Base):
    __tablename__ = "integrations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    integration_type: Mapped[str] = mapped_column(String(255), nullable=False, default="business")
    status: Mapped[IntegrationStatus] = mapped_column(String(50), nullable=False, default=IntegrationStatus.DISCONNECTED)
    account_identifier: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    metadata_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    organization = relationship("Organization", back_populates="integrations")
    credential = relationship("OAuthCredential", back_populates="integration", cascade="all, delete-orphan", uselist=False)
