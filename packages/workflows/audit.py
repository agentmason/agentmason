"""Audit trail service for workflow actions."""

from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import select, and_, desc
from sqlalchemy.orm import Session

from apps.api.app.models.workflow import (
    WorkflowAuditLog, AuditAction, RiskLevel as RiskLevelEnum,
    ApprovalStatus as ApprovalStatusEnum,
)

logger = logging.getLogger(__name__)


class AuditService:
    """Records immutable audit entries for all workflow-related actions."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def log(
        self,
        organization_id: str,
        action: AuditAction,
        user_id: str | None = None,
        workflow_id: str | None = None,
        execution_id: str | None = None,
        step_execution_id: str | None = None,
        agent_name: str | None = None,
        tool_name: str | None = None,
        risk_level: str | None = None,
        approval_status: str | None = None,
        input_summary: dict[str, Any] | None = None,
        output_summary: dict[str, Any] | None = None,
        error_info: str | None = None,
    ) -> WorkflowAuditLog:
        """Create an immutable audit log entry."""
        # Sanitize input/output — strip sensitive fields
        safe_input = _sanitize_summary(input_summary) if input_summary else None
        safe_output = _sanitize_summary(output_summary) if output_summary else None

        entry = WorkflowAuditLog(
            id=str(uuid4()),
            organization_id=organization_id,
            user_id=user_id,
            workflow_id=workflow_id,
            execution_id=execution_id,
            step_execution_id=step_execution_id,
            action=action,
            agent_name=agent_name,
            tool_name=tool_name,
            risk_level=RiskLevelEnum(risk_level) if risk_level else None,
            approval_status=ApprovalStatusEnum(approval_status) if approval_status else None,
            input_summary=safe_input,
            output_summary=safe_output,
            error_info=error_info,
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def get_timeline(
        self,
        organization_id: str,
        execution_id: str | None = None,
        workflow_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[WorkflowAuditLog], int]:
        """Retrieve audit log entries as a timeline."""
        conditions = [WorkflowAuditLog.organization_id == organization_id]
        if execution_id:
            conditions.append(WorkflowAuditLog.execution_id == execution_id)
        if workflow_id:
            conditions.append(WorkflowAuditLog.workflow_id == workflow_id)

        count_stmt = select(WorkflowAuditLog).where(and_(*conditions))
        total = len(list(self.db.scalars(count_stmt).all()))

        stmt = (
            select(WorkflowAuditLog)
            .where(and_(*conditions))
            .order_by(WorkflowAuditLog.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        entries = list(self.db.scalars(stmt).all())
        return entries, total

    def get_metrics(self, organization_id: str) -> dict[str, Any]:
        """Compute observability metrics from audit data."""
        all_entries = list(self.db.scalars(
            select(WorkflowAuditLog).where(
                WorkflowAuditLog.organization_id == organization_id
            )
        ).all())

        started = sum(1 for e in all_entries if e.action == AuditAction.EXECUTION_STARTED)
        completed = sum(1 for e in all_entries if e.action == AuditAction.EXECUTION_COMPLETED)
        failed = sum(1 for e in all_entries if e.action == AuditAction.EXECUTION_FAILED)
        approvals_requested = sum(1 for e in all_entries if e.action == AuditAction.APPROVAL_REQUESTED)
        approvals_granted = sum(1 for e in all_entries if e.action == AuditAction.APPROVAL_GRANTED)
        approvals_rejected = sum(1 for e in all_entries if e.action == AuditAction.APPROVAL_REJECTED)
        tools_executed = sum(1 for e in all_entries if e.action == AuditAction.TOOL_EXECUTED)
        tool_failures = sum(1 for e in all_entries if e.action == AuditAction.TOOL_FAILED)
        retries = sum(1 for e in all_entries if e.action == AuditAction.STEP_RETRIED)
        cost_limits = sum(1 for e in all_entries if e.action == AuditAction.COST_LIMIT_REACHED)

        return {
            "total_executions_started": started,
            "total_executions_completed": completed,
            "total_executions_failed": failed,
            "success_rate": (completed / started * 100) if started > 0 else 0.0,
            "failure_rate": (failed / started * 100) if started > 0 else 0.0,
            "approvals_requested": approvals_requested,
            "approvals_granted": approvals_granted,
            "approvals_rejected": approvals_rejected,
            "approval_rate": (approvals_granted / approvals_requested * 100) if approvals_requested > 0 else 0.0,
            "tools_executed": tools_executed,
            "tool_failures": tool_failures,
            "tool_failure_rate": (tool_failures / tools_executed * 100) if tools_executed > 0 else 0.0,
            "retries": retries,
            "cost_limit_hits": cost_limits,
        }


# Sensitive keys that should be redacted in audit logs
_SENSITIVE_KEYS = frozenset({
    "password", "secret", "token", "api_key", "access_token", "refresh_token",
    "authorization", "credential", "ssn", "credit_card", "card_number",
})


def _sanitize_summary(data: dict[str, Any]) -> dict[str, Any]:
    """Redact sensitive fields from audit summaries."""
    sanitized = {}
    for key, value in data.items():
        if key.lower() in _SENSITIVE_KEYS:
            sanitized[key] = "***REDACTED***"
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_summary(value)
        elif isinstance(value, str) and len(value) > 500:
            sanitized[key] = value[:500] + "...(truncated)"
        else:
            sanitized[key] = value
    return sanitized
