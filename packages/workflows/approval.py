"""Approval service for human-in-the-loop workflow control."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from apps.api.app.models.workflow import (
    ApprovalRequest, ApprovalStatus, RiskLevel as RiskLevelEnum,
    WorkflowExecution, WorkflowStepExecution, StepStatus,
    ExecutionStatus,
)

logger = logging.getLogger(__name__)

# Default approval expiration
DEFAULT_APPROVAL_TTL_HOURS = 24


class ApprovalError(Exception):
    pass


class ApprovalService:
    """Manages approval requests for workflow actions."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_request(
        self,
        execution_id: str,
        organization_id: str,
        action_type: str,
        action_description: str,
        risk_level: str,
        step_execution_id: str | None = None,
        action_parameters: dict[str, Any] | None = None,
        reason: str | None = None,
        data_summary: dict[str, Any] | None = None,
        target_system: str | None = None,
        expected_outcome: str | None = None,
        ttl_hours: int = DEFAULT_APPROVAL_TTL_HOURS,
    ) -> ApprovalRequest:
        """Create a new approval request and pause the execution."""
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)

        approval = ApprovalRequest(
            id=str(uuid4()),
            execution_id=execution_id,
            organization_id=organization_id,
            step_execution_id=step_execution_id,
            status=ApprovalStatus.PENDING,
            action_type=action_type,
            action_description=action_description,
            action_parameters=action_parameters,
            risk_level=RiskLevelEnum(risk_level),
            reason=reason,
            data_summary=data_summary,
            target_system=target_system,
            expected_outcome=expected_outcome,
            expires_at=expires_at,
        )
        self.db.add(approval)

        # Update the step status if provided
        if step_execution_id:
            step = self.db.get(WorkflowStepExecution, step_execution_id)
            if step:
                step.status = StepStatus.WAITING_FOR_APPROVAL
                step.approval_id = approval.id

        # Update execution status
        execution = self.db.get(WorkflowExecution, execution_id)
        if execution:
            execution.status = ExecutionStatus.WAITING_FOR_APPROVAL

        self.db.commit()
        self.db.refresh(approval)
        logger.info("Approval request created: %s for execution %s", approval.id, execution_id)
        return approval

    def approve(
        self,
        approval_id: str,
        organization_id: str,
        user_id: str,
        decision_note: str | None = None,
        modified_parameters: dict[str, Any] | None = None,
    ) -> ApprovalRequest:
        """Approve a pending request."""
        approval = self._get_and_validate(approval_id, organization_id)

        if approval.status != ApprovalStatus.PENDING:
            raise ApprovalError(f"Approval {approval_id} is not pending (status={approval.status.value})")

        # Check expiration — handle both naive and aware datetimes (SQLite stores naive)
        if approval.expires_at:
            now = datetime.now(timezone.utc)
            expires = approval.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if now > expires:
                approval.status = ApprovalStatus.EXPIRED
                self.db.commit()
                raise ApprovalError(f"Approval {approval_id} has expired")

        # Validate that modified_parameters don't change critical fields
        if modified_parameters and approval.action_parameters:
            self._validate_parameter_modification(approval.action_parameters, modified_parameters)

        approval.status = ApprovalStatus.APPROVED
        approval.decided_by = user_id
        approval.decided_at = datetime.now(timezone.utc)
        approval.decision_note = decision_note
        if modified_parameters:
            approval.modified_parameters = modified_parameters

        self.db.commit()
        self.db.refresh(approval)
        logger.info("Approval %s granted by user %s", approval_id, user_id)
        return approval

    def reject(
        self,
        approval_id: str,
        organization_id: str,
        user_id: str,
        decision_note: str | None = None,
    ) -> ApprovalRequest:
        """Reject a pending request."""
        approval = self._get_and_validate(approval_id, organization_id)

        if approval.status != ApprovalStatus.PENDING:
            raise ApprovalError(f"Approval {approval_id} is not pending (status={approval.status.value})")

        approval.status = ApprovalStatus.REJECTED
        approval.decided_by = user_id
        approval.decided_at = datetime.now(timezone.utc)
        approval.decision_note = decision_note

        # Fail the associated step
        if approval.step_execution_id:
            step = self.db.get(WorkflowStepExecution, approval.step_execution_id)
            if step:
                step.status = StepStatus.FAILED
                step.error = f"Approval rejected: {decision_note or 'No reason given'}"

        self.db.commit()
        self.db.refresh(approval)
        logger.info("Approval %s rejected by user %s", approval_id, user_id)
        return approval

    def get_pending(self, organization_id: str, execution_id: str | None = None) -> list[ApprovalRequest]:
        """Get all pending approval requests."""
        stmt = select(ApprovalRequest).where(
            and_(
                ApprovalRequest.organization_id == organization_id,
                ApprovalRequest.status == ApprovalStatus.PENDING,
            )
        )
        if execution_id:
            stmt = stmt.where(ApprovalRequest.execution_id == execution_id)
        stmt = stmt.order_by(ApprovalRequest.created_at.desc())
        return list(self.db.scalars(stmt).all())

    def get_by_id(self, approval_id: str, organization_id: str) -> ApprovalRequest | None:
        """Get an approval request by ID within an organization."""
        return self.db.scalar(
            select(ApprovalRequest).where(
                and_(
                    ApprovalRequest.id == approval_id,
                    ApprovalRequest.organization_id == organization_id,
                )
            )
        )

    def expire_stale(self, organization_id: str) -> int:
        """Expire all overdue pending approvals. Returns count expired."""
        now = datetime.now(timezone.utc)  # Note: SQLite may store naive datetimes
        stmt = select(ApprovalRequest).where(
            and_(
                ApprovalRequest.organization_id == organization_id,
                ApprovalRequest.status == ApprovalStatus.PENDING,
                ApprovalRequest.expires_at <= now,
            )
        )
        expired = list(self.db.scalars(stmt).all())
        for req in expired:
            req.status = ApprovalStatus.EXPIRED
        if expired:
            self.db.commit()
        return len(expired)

    def _get_and_validate(self, approval_id: str, organization_id: str) -> ApprovalRequest:
        """Fetch approval with tenant isolation."""
        approval = self.db.scalar(
            select(ApprovalRequest).where(
                and_(
                    ApprovalRequest.id == approval_id,
                    ApprovalRequest.organization_id == organization_id,
                )
            )
        )
        if not approval:
            raise ApprovalError(f"Approval request {approval_id} not found")
        return approval

    def _validate_parameter_modification(
        self, original: dict[str, Any], modified: dict[str, Any]
    ) -> None:
        """Ensure modified parameters don't introduce new keys or change protected fields."""
        protected_keys = {"recipient", "target", "account", "destination"}
        for key in modified:
            if key not in original:
                raise ApprovalError(
                    f"Cannot add new parameter '{key}' during approval modification"
                )
            if key in protected_keys and modified[key] != original.get(key):
                raise ApprovalError(
                    f"Cannot modify protected parameter '{key}' during approval"
                )
