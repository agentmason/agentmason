"""Workflow API routes — Phase 6: Autonomous Business Workflows."""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.core.database import get_db
from apps.api.app.models.membership import Membership
from apps.api.app.models.user import User
from apps.api.app.models.workflow import (
    Workflow, WorkflowExecution, WorkflowStepExecution,
    ApprovalRequest, WorkflowAuditLog,
    WorkflowStatus, ExecutionStatus, StepStatus,
    RiskLevel as RiskLevelEnum, ApprovalStatus, AuditAction,
)
from apps.api.app.api.organizations import get_current_user
from packages.llm.config import ProviderConfig
from packages.llm.factory import LLMProviderFactory
from packages.tools.registry import ToolRegistry
from packages.workflows.engine import WorkflowExecutionEngine
from packages.workflows.approval import ApprovalService, ApprovalError
from packages.workflows.audit import AuditService
from packages.workflows.risk import RiskClassifier, RiskPolicy
from packages.workflows.templates import WorkflowTemplateRegistry

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Request/Response Schemas ---

class WorkflowCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    trigger: Optional[str] = None
    steps: Optional[list[dict]] = None
    inputs: Optional[dict] = None
    conditions: Optional[dict] = None
    tools: Optional[list[str]] = None
    approval_policy: Optional[dict] = None
    retry_policy: Optional[dict] = None
    risk_policy: Optional[dict] = None
    cost_policy: Optional[dict] = None
    max_steps: int = 50
    max_iterations: int = 100
    timeout_seconds: int = 3600
    is_template: bool = False
    template_category: Optional[str] = None


class WorkflowUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger: Optional[str] = None
    status: Optional[str] = None
    steps: Optional[list[dict]] = None
    inputs: Optional[dict] = None
    conditions: Optional[dict] = None
    tools: Optional[list[str]] = None
    approval_policy: Optional[dict] = None
    retry_policy: Optional[dict] = None
    risk_policy: Optional[dict] = None
    cost_policy: Optional[dict] = None
    max_steps: Optional[int] = None
    max_iterations: Optional[int] = None
    timeout_seconds: Optional[int] = None


class WorkflowExecuteRequest(BaseModel):
    inputs: Optional[dict] = None
    objective: Optional[str] = None


class ApprovalDecisionRequest(BaseModel):
    decision_note: Optional[str] = None
    modified_parameters: Optional[dict] = None


class WorkflowFromTemplateRequest(BaseModel):
    template_name: str
    name: Optional[str] = None
    inputs: Optional[dict] = None


# --- Helpers ---

def _get_org_id(db: Session, user: User) -> str:
    membership = db.scalar(
        select(Membership).where(Membership.user_id == user.id).limit(1)
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No organization access")
    return str(membership.organization_id)


def _build_engine(db: Session) -> WorkflowExecutionEngine:
    """Create a WorkflowExecutionEngine with default tool registry and LLM."""
    from packages.tools.calculator import CalculatorTool
    from packages.tools.datetime_tool import DateTimeTool
    from packages.tools.text_analysis import TextAnalysisTool

    tool_registry = ToolRegistry()
    tool_registry.register(CalculatorTool())
    tool_registry.register(DateTimeTool())
    tool_registry.register(TextAnalysisTool())

    # Register business tools if available
    try:
        from packages.tools.business_memory import SearchBusinessMemoryTool, CreateBusinessMemoryTool
        from packages.tools.business_graph import SearchBusinessGraphTool, GetRelatedEntitiesTool
        from packages.tools.business_knowledge import SearchBusinessKnowledgeTool

        def db_factory():
            return db

        tool_registry.register(SearchBusinessMemoryTool(db_factory))
        tool_registry.register(CreateBusinessMemoryTool(db_factory))
        tool_registry.register(SearchBusinessGraphTool(db_factory))
        tool_registry.register(GetRelatedEntitiesTool(db_factory))
        tool_registry.register(SearchBusinessKnowledgeTool(db_factory))
    except ImportError:
        logger.debug("Business tools not available")

    # Register integration tools if available
    try:
        from packages.tools.business_email import SearchBusinessEmailTool, CreateEmailDraftTool, SendEmailTool
        from packages.tools.business_drive import SearchBusinessFilesTool, ListBusinessFilesTool
        from packages.tools.business_calendar import SearchCalendarTool, CreateCalendarEventTool, UpdateCalendarEventTool

        tool_registry.register(SearchBusinessEmailTool(None))
        tool_registry.register(CreateEmailDraftTool(None))
        tool_registry.register(SendEmailTool(None))
        tool_registry.register(SearchBusinessFilesTool(None))
        tool_registry.register(ListBusinessFilesTool(None))
        tool_registry.register(SearchCalendarTool(None))
        tool_registry.register(CreateCalendarEventTool(None))
        tool_registry.register(UpdateCalendarEventTool(None))
    except ImportError:
        logger.debug("Integration tools not available")

    config = ProviderConfig(provider="local", model="local", api_key="not-needed")
    llm_provider = LLMProviderFactory.create("local", config)

    return WorkflowExecutionEngine(
        db=db,
        tool_registry=tool_registry,
        llm_provider=llm_provider,
    )


def _workflow_to_dict(wf: Workflow) -> dict:
    return {
        "id": wf.id,
        "organization_id": wf.organization_id,
        "name": wf.name,
        "description": wf.description,
        "trigger": wf.trigger,
        "status": wf.status.value if isinstance(wf.status, WorkflowStatus) else wf.status,
        "steps": wf.steps,
        "inputs": wf.inputs,
        "conditions": wf.conditions,
        "tools": wf.tools,
        "approval_policy": wf.approval_policy,
        "retry_policy": wf.retry_policy,
        "risk_policy": wf.risk_policy,
        "cost_policy": wf.cost_policy,
        "max_steps": wf.max_steps,
        "max_iterations": wf.max_iterations,
        "timeout_seconds": wf.timeout_seconds,
        "is_template": wf.is_template,
        "template_category": wf.template_category,
        "created_by": wf.created_by,
        "created_at": wf.created_at.isoformat() if wf.created_at else None,
        "updated_at": wf.updated_at.isoformat() if wf.updated_at else None,
    }


def _execution_to_dict(ex: WorkflowExecution) -> dict:
    return {
        "id": ex.id,
        "workflow_id": ex.workflow_id,
        "organization_id": ex.organization_id,
        "user_id": ex.user_id,
        "status": ex.status.value if isinstance(ex.status, ExecutionStatus) else ex.status,
        "plan": ex.plan,
        "inputs": ex.inputs,
        "outputs": ex.outputs,
        "objective": ex.objective,
        "error": ex.error,
        "current_step_index": ex.current_step_index,
        "total_steps": ex.total_steps,
        "completed_steps": ex.completed_steps,
        "progress": round((ex.completed_steps / ex.total_steps * 100) if ex.total_steps > 0 else 0, 1),
        "total_token_usage": ex.total_token_usage,
        "total_tool_calls": ex.total_tool_calls,
        "total_llm_calls": ex.total_llm_calls,
        "started_at": ex.started_at.isoformat() if ex.started_at else None,
        "completed_at": ex.completed_at.isoformat() if ex.completed_at else None,
        "created_at": ex.created_at.isoformat() if ex.created_at else None,
        "updated_at": ex.updated_at.isoformat() if ex.updated_at else None,
        "steps": [_step_to_dict(s) for s in sorted(ex.step_executions, key=lambda s: s.step_index)],
        "approvals": [_approval_to_dict(a) for a in ex.approval_requests],
    }


def _step_to_dict(step: WorkflowStepExecution) -> dict:
    return {
        "id": step.id,
        "step_index": step.step_index,
        "step_name": step.step_name,
        "step_type": step.step_type,
        "status": step.status.value if isinstance(step.status, StepStatus) else step.status,
        "tool_name": step.tool_name,
        "tool_input": step.tool_input,
        "tool_output": step.tool_output,
        "risk_level": step.risk_level.value if isinstance(step.risk_level, RiskLevelEnum) else step.risk_level,
        "requires_approval": step.requires_approval,
        "approval_id": step.approval_id,
        "retry_count": step.retry_count,
        "max_retries": step.max_retries,
        "error": step.error,
        "reasoning": step.reasoning,
        "started_at": step.started_at.isoformat() if step.started_at else None,
        "completed_at": step.completed_at.isoformat() if step.completed_at else None,
    }


def _approval_to_dict(a: ApprovalRequest) -> dict:
    return {
        "id": a.id,
        "execution_id": a.execution_id,
        "step_execution_id": a.step_execution_id,
        "status": a.status.value if isinstance(a.status, ApprovalStatus) else a.status,
        "action_type": a.action_type,
        "action_description": a.action_description,
        "action_parameters": a.action_parameters,
        "risk_level": a.risk_level.value if isinstance(a.risk_level, RiskLevelEnum) else a.risk_level,
        "reason": a.reason,
        "data_summary": a.data_summary,
        "target_system": a.target_system,
        "expected_outcome": a.expected_outcome,
        "decided_by": a.decided_by,
        "decided_at": a.decided_at.isoformat() if a.decided_at else None,
        "decision_note": a.decision_note,
        "modified_parameters": a.modified_parameters,
        "expires_at": a.expires_at.isoformat() if a.expires_at else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def _audit_to_dict(entry: WorkflowAuditLog) -> dict:
    return {
        "id": entry.id,
        "action": entry.action.value if isinstance(entry.action, AuditAction) else entry.action,
        "user_id": entry.user_id,
        "workflow_id": entry.workflow_id,
        "execution_id": entry.execution_id,
        "step_execution_id": entry.step_execution_id,
        "agent_name": entry.agent_name,
        "tool_name": entry.tool_name,
        "risk_level": entry.risk_level.value if isinstance(entry.risk_level, RiskLevelEnum) else entry.risk_level,
        "approval_status": entry.approval_status.value if isinstance(entry.approval_status, ApprovalStatus) else entry.approval_status,
        "input_summary": entry.input_summary,
        "output_summary": entry.output_summary,
        "error_info": entry.error_info,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


# =====================================================================
# Workflow CRUD Endpoints
# =====================================================================

@router.get("")
async def list_workflows(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    status_filter: Optional[str] = Query(None, alias="status"),
    is_template: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    """List workflow definitions."""
    org_id = _get_org_id(db, current_user)
    engine = _build_engine(db)
    workflows, total = engine.list_workflows(
        org_id, status=status_filter, is_template=is_template, limit=limit, offset=skip
    )
    return {
        "workflows": [_workflow_to_dict(w) for w in workflows],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_workflow(
    body: WorkflowCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Create a new workflow definition."""
    org_id = _get_org_id(db, current_user)
    engine = _build_engine(db)

    try:
        workflow = engine.create_workflow(
            organization_id=org_id,
            name=body.name,
            user_id=current_user.id,
            description=body.description,
            trigger=body.trigger,
            steps=body.steps,
            inputs=body.inputs,
            conditions=body.conditions,
            tools=body.tools,
            approval_policy=body.approval_policy,
            retry_policy=body.retry_policy,
            risk_policy=body.risk_policy,
            cost_policy=body.cost_policy,
            max_steps=body.max_steps,
            max_iterations=body.max_iterations,
            timeout_seconds=body.timeout_seconds,
            is_template=body.is_template,
            template_category=body.template_category,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _workflow_to_dict(workflow)


@router.get("/templates")
async def list_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """List available workflow templates."""
    registry = WorkflowTemplateRegistry()
    templates = registry.list()
    return {"templates": templates, "total": len(templates)}


@router.post("/from-template", status_code=status.HTTP_201_CREATED)
async def create_from_template(
    body: WorkflowFromTemplateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Create a workflow from a built-in template."""
    org_id = _get_org_id(db, current_user)
    registry = WorkflowTemplateRegistry()
    template = registry.get(body.template_name)
    if not template:
        raise HTTPException(status_code=404, detail=f"Template '{body.template_name}' not found")

    engine = _build_engine(db)
    workflow = engine.create_workflow(
        organization_id=org_id,
        name=body.name or template["name"],
        user_id=current_user.id,
        description=template.get("description"),
        trigger=template.get("trigger"),
        steps=template.get("steps"),
        inputs=template.get("inputs"),
        approval_policy=template.get("approval_policy"),
        retry_policy=template.get("retry_policy"),
        cost_policy=template.get("cost_policy"),
        is_template=False,
        template_category=template.get("template_category"),
    )
    return _workflow_to_dict(workflow)


@router.get("/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Get a specific workflow definition."""
    org_id = _get_org_id(db, current_user)
    engine = _build_engine(db)
    workflow = engine.get_workflow(workflow_id, org_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return _workflow_to_dict(workflow)


@router.patch("/{workflow_id}")
async def update_workflow(
    workflow_id: str,
    body: WorkflowUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Update a workflow definition."""
    org_id = _get_org_id(db, current_user)
    engine = _build_engine(db)
    updates = body.model_dump(exclude_none=True)
    workflow = engine.update_workflow(workflow_id, org_id, current_user.id, **updates)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return _workflow_to_dict(workflow)


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Delete a workflow definition."""
    org_id = _get_org_id(db, current_user)
    engine = _build_engine(db)
    if not engine.delete_workflow(workflow_id, org_id, current_user.id):
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"deleted": True}


# =====================================================================
# Execution Endpoints
# =====================================================================

@router.post("/{workflow_id}/execute", status_code=status.HTTP_201_CREATED)
async def execute_workflow(
    workflow_id: str,
    body: WorkflowExecuteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Start executing a workflow."""
    org_id = _get_org_id(db, current_user)
    engine = _build_engine(db)

    try:
        execution = await engine.execute_workflow(
            workflow_id=workflow_id,
            organization_id=org_id,
            user_id=current_user.id,
            inputs=body.inputs,
            objective=body.objective,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Workflow execution error")
        raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")

    return _execution_to_dict(execution)


@router.post("/{workflow_id}/pause")
async def pause_workflow_execution(
    workflow_id: str,
    execution_id: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Pause a running workflow execution."""
    org_id = _get_org_id(db, current_user)
    engine = _build_engine(db)
    try:
        execution = engine.pause_execution(execution_id, org_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _execution_to_dict(execution)


@router.post("/{workflow_id}/resume")
async def resume_workflow_execution(
    workflow_id: str,
    execution_id: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Resume a paused or waiting workflow execution."""
    org_id = _get_org_id(db, current_user)
    engine = _build_engine(db)
    try:
        execution = await engine.resume_execution(execution_id, org_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _execution_to_dict(execution)


@router.post("/{workflow_id}/cancel")
async def cancel_workflow_execution(
    workflow_id: str,
    execution_id: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Cancel a workflow execution."""
    org_id = _get_org_id(db, current_user)
    engine = _build_engine(db)
    try:
        execution = engine.cancel_execution(execution_id, org_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _execution_to_dict(execution)


# =====================================================================
# Execution List / Detail
# =====================================================================

@router.get("/executions/list")
async def list_executions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workflow_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    """List workflow executions."""
    org_id = _get_org_id(db, current_user)
    engine = _build_engine(db)
    executions, total = engine.list_executions(
        org_id, workflow_id=workflow_id, status=status_filter, limit=limit, offset=skip
    )
    return {
        "executions": [_execution_to_dict(e) for e in executions],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/executions/{execution_id}")
async def get_execution(
    execution_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Get a specific workflow execution with steps and approvals."""
    org_id = _get_org_id(db, current_user)
    engine = _build_engine(db)
    execution = engine.get_execution(execution_id, org_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return _execution_to_dict(execution)


# =====================================================================
# Approval Endpoints
# =====================================================================

@router.post("/executions/{execution_id}/approve")
async def approve_execution(
    execution_id: str,
    approval_id: str = Query(...),
    body: ApprovalDecisionRequest = ApprovalDecisionRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Approve a pending approval request."""
    org_id = _get_org_id(db, current_user)
    approval_svc = ApprovalService(db)
    try:
        approval = approval_svc.approve(
            approval_id=approval_id,
            organization_id=org_id,
            user_id=current_user.id,
            decision_note=body.decision_note,
            modified_parameters=body.modified_parameters,
        )
    except ApprovalError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Log approval
    audit_svc = AuditService(db)
    audit_svc.log(
        organization_id=org_id,
        action=AuditAction.APPROVAL_GRANTED,
        user_id=current_user.id,
        execution_id=execution_id,
        approval_status="approved",
    )

    return _approval_to_dict(approval)


@router.post("/executions/{execution_id}/reject")
async def reject_execution(
    execution_id: str,
    approval_id: str = Query(...),
    body: ApprovalDecisionRequest = ApprovalDecisionRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Reject a pending approval request."""
    org_id = _get_org_id(db, current_user)
    approval_svc = ApprovalService(db)
    try:
        approval = approval_svc.reject(
            approval_id=approval_id,
            organization_id=org_id,
            user_id=current_user.id,
            decision_note=body.decision_note,
        )
    except ApprovalError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Log rejection
    audit_svc = AuditService(db)
    audit_svc.log(
        organization_id=org_id,
        action=AuditAction.APPROVAL_REJECTED,
        user_id=current_user.id,
        execution_id=execution_id,
        approval_status="rejected",
    )

    return _approval_to_dict(approval)


@router.get("/executions/{execution_id}/approvals")
async def list_approvals(
    execution_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """List approval requests for an execution."""
    org_id = _get_org_id(db, current_user)
    approval_svc = ApprovalService(db)
    pending = approval_svc.get_pending(org_id, execution_id)
    return {"approvals": [_approval_to_dict(a) for a in pending]}


# =====================================================================
# Audit / Timeline / Metrics
# =====================================================================

@router.get("/executions/{execution_id}/timeline")
async def get_execution_timeline(
    execution_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    """Get the execution timeline (audit trail)."""
    org_id = _get_org_id(db, current_user)
    audit_svc = AuditService(db)
    entries, total = audit_svc.get_timeline(
        org_id, execution_id=execution_id, limit=limit, offset=skip
    )
    return {
        "timeline": [_audit_to_dict(e) for e in entries],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/metrics/overview")
async def get_workflow_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Get workflow observability metrics."""
    org_id = _get_org_id(db, current_user)
    audit_svc = AuditService(db)
    return audit_svc.get_metrics(org_id)
