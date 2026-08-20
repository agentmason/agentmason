"""Workflow models for Phase 6: Autonomous Business Workflows."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import DateTime, Enum as SQLEnum, Float, Integer, String, Text, Boolean, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.app.models.base import Base


# --- Enums ---

class WorkflowStatus(str, Enum):
    """Status of a workflow definition."""
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class ExecutionStatus(str, Enum):
    """Status of a workflow execution."""
    DRAFT = "draft"
    PLANNED = "planned"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_FOR_INPUT = "waiting_for_input"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    """Status of a workflow step execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    WAITING_FOR_INPUT = "waiting_for_input"
    CANCELLED = "cancelled"


class RiskLevel(str, Enum):
    """Risk classification for actions."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ApprovalStatus(str, Enum):
    """Status of an approval request."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class AuditAction(str, Enum):
    """Types of auditable actions."""
    WORKFLOW_CREATED = "workflow_created"
    WORKFLOW_UPDATED = "workflow_updated"
    WORKFLOW_DELETED = "workflow_deleted"
    EXECUTION_STARTED = "execution_started"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"
    EXECUTION_CANCELLED = "execution_cancelled"
    EXECUTION_PAUSED = "execution_paused"
    EXECUTION_RESUMED = "execution_resumed"
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    STEP_SKIPPED = "step_skipped"
    STEP_RETRIED = "step_retried"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_REJECTED = "approval_rejected"
    APPROVAL_EXPIRED = "approval_expired"
    TOOL_EXECUTED = "tool_executed"
    TOOL_FAILED = "tool_failed"
    COST_LIMIT_REACHED = "cost_limit_reached"
    HUMAN_INTERVENTION = "human_intervention"


# --- Models ---

class Workflow(Base):
    """A reusable workflow definition."""
    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trigger: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[WorkflowStatus] = mapped_column(
        SQLEnum(WorkflowStatus), default=WorkflowStatus.DRAFT, nullable=False, index=True
    )

    # Workflow definition
    steps: Mapped[Optional[List]] = mapped_column(JSON, nullable=True)
    inputs: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    conditions: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    tools: Mapped[Optional[List]] = mapped_column(JSON, nullable=True)

    # Policies
    required_permissions: Mapped[Optional[List]] = mapped_column(JSON, nullable=True)
    approval_policy: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    retry_policy: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    risk_policy: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    cost_policy: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)

    # Limits
    max_steps: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    max_iterations: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=3600, nullable=False)

    # Template metadata
    is_template: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    template_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Metadata
    created_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    metadata_payload: Mapped[Optional[Dict]] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    executions: Mapped[list["WorkflowExecution"]] = relationship(
        "WorkflowExecution", back_populates="workflow", cascade="all, delete-orphan"
    )


class WorkflowExecution(Base):
    """A single execution instance of a workflow."""
    __tablename__ = "workflow_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workflow_id: Mapped[str] = mapped_column(String(36), ForeignKey("workflows.id"), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    status: Mapped[ExecutionStatus] = mapped_column(
        SQLEnum(ExecutionStatus), default=ExecutionStatus.PLANNED, nullable=False, index=True
    )

    # Plan and execution state
    plan: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    inputs: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    outputs: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    context: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Progress tracking
    current_step_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_steps: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_steps: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Cost tracking
    total_token_usage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tool_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_llm_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Natural language objective (for AI-planned workflows)
    objective: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Metadata
    metadata_payload: Mapped[Optional[Dict]] = mapped_column("metadata", JSON, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="executions")
    step_executions: Mapped[list["WorkflowStepExecution"]] = relationship(
        "WorkflowStepExecution", back_populates="execution", cascade="all, delete-orphan",
        order_by="WorkflowStepExecution.step_index"
    )
    approval_requests: Mapped[list["ApprovalRequest"]] = relationship(
        "ApprovalRequest", back_populates="execution", cascade="all, delete-orphan"
    )


class WorkflowStepExecution(Base):
    """Execution record for an individual workflow step."""
    __tablename__ = "workflow_step_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    execution_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflow_executions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    step_name: Mapped[str] = mapped_column(String(255), nullable=False)
    step_type: Mapped[str] = mapped_column(String(50), default="action", nullable=False)  # action, condition, loop, approval

    status: Mapped[StepStatus] = mapped_column(
        SQLEnum(StepStatus), default=StepStatus.PENDING, nullable=False, index=True
    )

    # Tool execution
    tool_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tool_input: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    tool_output: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)

    # Risk and approval
    risk_level: Mapped[Optional[RiskLevel]] = mapped_column(SQLEnum(RiskLevel), nullable=True)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approval_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # Retry tracking
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    # Error info
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # LLM reasoning for this step
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Metadata
    metadata_payload: Mapped[Optional[Dict]] = mapped_column("metadata", JSON, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    execution: Mapped["WorkflowExecution"] = relationship("WorkflowExecution", back_populates="step_executions")


class ApprovalRequest(Base):
    """An approval request for a workflow action."""
    __tablename__ = "approval_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    execution_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflow_executions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    step_execution_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    status: Mapped[ApprovalStatus] = mapped_column(
        SQLEnum(ApprovalStatus), default=ApprovalStatus.PENDING, nullable=False, index=True
    )

    # What is being approved
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    action_description: Mapped[str] = mapped_column(Text, nullable=False)
    action_parameters: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    risk_level: Mapped[RiskLevel] = mapped_column(SQLEnum(RiskLevel), default=RiskLevel.MEDIUM, nullable=False)

    # Why
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    data_summary: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    target_system: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    expected_outcome: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Approval decision
    decided_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    modified_parameters: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)

    # Expiration
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    execution: Mapped["WorkflowExecution"] = relationship("WorkflowExecution", back_populates="approval_requests")


class WorkflowAuditLog(Base):
    """Immutable audit log for all workflow-related actions."""
    __tablename__ = "workflow_audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    workflow_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    execution_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    step_execution_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    action: Mapped[AuditAction] = mapped_column(SQLEnum(AuditAction), nullable=False, index=True)

    # Details
    agent_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tool_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    risk_level: Mapped[Optional[RiskLevel]] = mapped_column(SQLEnum(RiskLevel), nullable=True)
    approval_status: Mapped[Optional[ApprovalStatus]] = mapped_column(SQLEnum(ApprovalStatus), nullable=True)

    input_summary: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    output_summary: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    error_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamp — immutable
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )
