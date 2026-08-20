"""Orchestration API routes — Phase 7: Multi-Agent Orchestration."""

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
from apps.api.app.models.orchestration import (
    SpecializedAgent, OrchestrationExecution, AgentTask,
    AgentStatus, AgentRiskLevel, OrchestrationStatus, AgentTaskStatus,
)
from apps.api.app.api.organizations import get_current_user
from packages.llm.config import ProviderConfig
from packages.llm.factory import LLMProviderFactory
from packages.orchestration.registry import SpecializedAgentRegistry
from packages.orchestration.engine import OrchestrationEngine
from packages.orchestration.context import SharedContextBuilder
from packages.orchestration.conflict import ConflictResolver
from packages.orchestration.planner import OrchestrationPlanner
from packages.orchestration.capabilities import CapabilityMatcher
from packages.orchestration.evaluation import AgentEvaluator
from packages.workflows.audit import AuditService

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Request/Response Schemas ---

class AgentCreateRequest(BaseModel):
    name: str
    agent_type: str
    description: Optional[str] = None
    capabilities: Optional[list[str]] = None
    allowed_tools: Optional[list[str]] = None
    allowed_data_sources: Optional[list[str]] = None
    permissions: Optional[list[dict]] = None
    supported_tasks: Optional[list[str]] = None
    model_config_data: Optional[dict] = None
    system_prompt: Optional[str] = None
    risk_level: str = "medium"
    version: str = "1.0.0"


class AgentUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    capabilities: Optional[list[str]] = None
    allowed_tools: Optional[list[str]] = None
    allowed_data_sources: Optional[list[str]] = None
    permissions: Optional[list[dict]] = None
    supported_tasks: Optional[list[str]] = None
    model_config_data: Optional[dict] = None
    system_prompt: Optional[str] = None
    risk_level: Optional[str] = None
    status: Optional[str] = None
    version: Optional[str] = None


class OrchestrationPlanRequest(BaseModel):
    objective: str
    context: Optional[dict] = None


class OrchestrationExecuteRequest(BaseModel):
    objective: str
    plan: Optional[dict] = None
    context: Optional[dict] = None


# --- Helpers ---

def _get_org_id(db: Session, user: User) -> str:
    membership = db.scalar(
        select(Membership).where(Membership.user_id == user.id).limit(1)
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No organization access")
    return str(membership.organization_id)


def _build_orchestration_engine(db: Session) -> OrchestrationEngine:
    """Create an OrchestrationEngine with default configuration."""
    config = ProviderConfig(provider="local", model="local", api_key="not-needed")
    llm_provider = LLMProviderFactory.create("local", config)

    agent_registry = SpecializedAgentRegistry(db)
    context_builder = SharedContextBuilder(db)
    conflict_resolver = ConflictResolver(llm_provider)
    audit_service = AuditService(db)
    capability_matcher = CapabilityMatcher()
    planner = OrchestrationPlanner(llm_provider, agent_registry, capability_matcher)

    return OrchestrationEngine(
        db=db,
        llm_provider=llm_provider,
        agent_registry=agent_registry,
        context_builder=context_builder,
        conflict_resolver=conflict_resolver,
        audit_service=audit_service,
        planner=planner,
    )


def _agent_to_dict(agent: SpecializedAgent) -> dict:
    return {
        "id": agent.id,
        "organization_id": agent.organization_id,
        "name": agent.name,
        "description": agent.description,
        "agent_type": agent.agent_type,
        "capabilities": agent.capabilities,
        "allowed_tools": agent.allowed_tools,
        "allowed_data_sources": agent.allowed_data_sources,
        "permissions": agent.permissions,
        "supported_tasks": agent.supported_tasks,
        "model_config": agent.model_config_data,
        "system_prompt": agent.system_prompt,
        "risk_level": agent.risk_level.value if isinstance(agent.risk_level, AgentRiskLevel) else agent.risk_level,
        "status": agent.status.value if isinstance(agent.status, AgentStatus) else agent.status,
        "version": agent.version,
        "created_by": agent.created_by,
        "created_at": agent.created_at.isoformat() if agent.created_at else None,
        "updated_at": agent.updated_at.isoformat() if agent.updated_at else None,
    }


def _orchestration_to_dict(ex: OrchestrationExecution) -> dict:
    return {
        "id": ex.id,
        "organization_id": ex.organization_id,
        "user_id": ex.user_id,
        "objective": ex.objective,
        "plan": ex.plan,
        "status": ex.status.value if isinstance(ex.status, OrchestrationStatus) else ex.status,
        "final_summary": ex.final_summary,
        "final_recommendation": ex.final_recommendation,
        "final_confidence": ex.final_confidence,
        "conflicts": ex.conflicts,
        "conflict_resolution": ex.conflict_resolution,
        "workflow_execution_id": ex.workflow_execution_id,
        "total_token_usage": ex.total_token_usage,
        "total_tool_calls": ex.total_tool_calls,
        "total_llm_calls": ex.total_llm_calls,
        "total_agent_tasks": ex.total_agent_tasks,
        "error": ex.error,
        "tasks": [_task_to_dict(t) for t in (ex.tasks or [])],
        "started_at": ex.started_at.isoformat() if ex.started_at else None,
        "completed_at": ex.completed_at.isoformat() if ex.completed_at else None,
        "created_at": ex.created_at.isoformat() if ex.created_at else None,
    }


def _task_to_dict(task: AgentTask) -> dict:
    return {
        "id": task.id,
        "orchestration_id": task.orchestration_id,
        "agent_id": task.agent_id,
        "objective": task.objective,
        "expected_output_type": task.expected_output_type,
        "capabilities_required": task.capabilities_required,
        "execution_order": task.execution_order,
        "depends_on": task.depends_on,
        "status": task.status.value if isinstance(task.status, AgentTaskStatus) else task.status,
        "summary": task.summary,
        "findings": task.findings,
        "recommendations": task.recommendations,
        "evidence": task.evidence,
        "confidence": task.confidence,
        "risks": task.risks,
        "required_actions": task.required_actions,
        "sources": task.sources,
        "token_usage": task.token_usage,
        "tool_calls": task.tool_calls,
        "llm_calls": task.llm_calls,
        "error": task.error,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


# ============================================================
# Agent CRUD endpoints
# ============================================================

@router.get("/agents")
def list_agents(
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List specialized agents for the organization."""
    org_id = _get_org_id(db, user)
    registry = SpecializedAgentRegistry(db)
    agents, total = registry.list_agents(org_id, status=status, limit=limit, offset=skip)
    return {
        "agents": [_agent_to_dict(a) for a in agents],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.post("/agents", status_code=status.HTTP_201_CREATED)
def create_agent(
    body: AgentCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Register a new specialized agent."""
    org_id = _get_org_id(db, user)
    registry = SpecializedAgentRegistry(db)
    agent = registry.register(
        organization_id=org_id,
        user_id=str(user.id),
        agent_type=body.agent_type,
        name=body.name,
        description=body.description,
        capabilities=body.capabilities,
        allowed_tools=body.allowed_tools,
        allowed_data_sources=body.allowed_data_sources,
        permissions=body.permissions,
        supported_tasks=body.supported_tasks,
        model_config_data=body.model_config_data,
        system_prompt=body.system_prompt,
        risk_level=AgentRiskLevel(body.risk_level),
        version=body.version,
    )
    return _agent_to_dict(agent)


@router.get("/agents/{agent_id}")
def get_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a specialized agent by ID."""
    org_id = _get_org_id(db, user)
    registry = SpecializedAgentRegistry(db)
    agent = registry.get(agent_id, org_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return _agent_to_dict(agent)


@router.patch("/agents/{agent_id}")
def update_agent(
    agent_id: str,
    body: AgentUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update a specialized agent."""
    org_id = _get_org_id(db, user)
    registry = SpecializedAgentRegistry(db)
    updates = body.model_dump(exclude_none=True)
    agent = registry.update(agent_id, org_id, **updates)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return _agent_to_dict(agent)


@router.post("/agents/seed")
def seed_agents(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Seed default specialized agents for the organization."""
    org_id = _get_org_id(db, user)
    registry = SpecializedAgentRegistry(db)
    created = registry.seed_defaults(org_id, str(user.id))
    return {
        "seeded": len(created),
        "agents": [_agent_to_dict(a) for a in created],
    }


# ============================================================
# Orchestration endpoints
# ============================================================

@router.post("/orchestrator/plan")
async def create_plan(
    body: OrchestrationPlanRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create an orchestration plan without executing it."""
    org_id = _get_org_id(db, user)
    engine = _build_orchestration_engine(db)
    plan = await engine.create_plan(
        objective=body.objective,
        organization_id=org_id,
        user_id=str(user.id),
        context=body.context,
    )
    return plan


@router.post("/orchestrator/execute")
async def execute_orchestration(
    body: OrchestrationExecuteRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Execute a multi-agent orchestration."""
    org_id = _get_org_id(db, user)
    engine = _build_orchestration_engine(db)
    execution = await engine.execute(
        objective=body.objective,
        organization_id=org_id,
        user_id=str(user.id),
        plan=body.plan,
        context=body.context,
    )
    return _orchestration_to_dict(execution)


# ============================================================
# Execution queries
# ============================================================

@router.get("/executions")
def list_orchestration_executions(
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List orchestration executions."""
    org_id = _get_org_id(db, user)
    engine = _build_orchestration_engine(db)
    executions, total = engine.list_executions(org_id, status=status, limit=limit, offset=skip)
    return {
        "executions": [_orchestration_to_dict(e) for e in executions],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/executions/{execution_id}")
def get_orchestration_execution(
    execution_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a specific orchestration execution."""
    org_id = _get_org_id(db, user)
    engine = _build_orchestration_engine(db)
    execution = engine.get_execution(execution_id, org_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return _orchestration_to_dict(execution)


@router.get("/executions/{execution_id}/trace")
def get_execution_trace(
    execution_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get full execution trace for observability."""
    org_id = _get_org_id(db, user)
    engine = _build_orchestration_engine(db)
    trace = engine.get_execution_trace(execution_id, org_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Execution not found")
    return trace


# ============================================================
# Task queries
# ============================================================

@router.get("/tasks")
def list_agent_tasks(
    orchestration_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List agent tasks."""
    org_id = _get_org_id(db, user)
    engine = _build_orchestration_engine(db)
    tasks, total = engine.list_tasks(
        org_id, orchestration_id=orchestration_id, status=status,
        limit=limit, offset=skip,
    )
    return {
        "tasks": [_task_to_dict(t) for t in tasks],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/tasks/{task_id}")
def get_agent_task(
    task_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a specific agent task."""
    org_id = _get_org_id(db, user)
    engine = _build_orchestration_engine(db)
    task = engine.get_task(task_id, org_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return _task_to_dict(task)


# ============================================================
# Metrics & evaluation
# ============================================================

@router.get("/metrics")
def get_agent_metrics(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get agent performance metrics."""
    org_id = _get_org_id(db, user)
    engine = _build_orchestration_engine(db)
    return engine.get_agent_metrics(org_id)


@router.get("/evaluation/scenarios")
def list_evaluation_scenarios(
    agent_type: Optional[str] = Query(None),
):
    """List available evaluation scenarios."""
    evaluator = AgentEvaluator()
    if agent_type:
        scenarios = evaluator.get_scenarios_for_agent(agent_type)
    else:
        scenarios = evaluator.scenarios
    return {
        "scenarios": [
            {
                "name": s.name,
                "agent_type": s.agent_type,
                "input_objective": s.input_objective,
                "expected_capabilities": s.expected_capabilities,
                "min_confidence": s.min_confidence,
            }
            for s in scenarios
        ]
    }
