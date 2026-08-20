"""Dogfood API — Run My Business on AgentMason.

Endpoints for the Executive Command Center, Business Inbox, Approval
Center, Agent Activity, Demo Scenarios, KPIs, Briefing, and Impact Dashboard.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session

from apps.api.app.core.database import get_db
from apps.api.app.models.membership import Membership
from apps.api.app.models.user import User
from apps.api.app.api.organizations import get_current_user
from packages.dogfood.models import (
    BusinessConfig, BusinessKPI, BusinessInboxItem,
    AgentActivity, BusinessMetric,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Helpers ─────────────────────────────────────────────────────────────

def _get_org_id(db: Session, user: User) -> str:
    membership = db.scalar(
        select(Membership).where(Membership.user_id == user.id).limit(1)
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No organization access")
    return str(membership.organization_id)


# ╭──────────────────────────────────────────────────────────────────────╮
# │                     BUSINESS CONFIG                                 │
# ╰──────────────────────────────────────────────────────────────────────╯

class BusinessConfigResponse(BaseModel):
    id: str
    company_name: str
    product_name: Optional[str] = None
    business_type: Optional[str] = None
    tagline: Optional[str] = None
    departments: Optional[list] = None
    business_activities: Optional[list] = None
    goals: Optional[list] = None
    kpis: Optional[list] = None
    demo_mode: bool = True


@router.get("/config")
def get_business_config(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    org_id = _get_org_id(db, user)
    config = db.query(BusinessConfig).filter_by(organization_id=org_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Business not configured. Run seed first.")
    return {
        "id": config.id,
        "company_name": config.company_name,
        "product_name": config.product_name,
        "business_type": config.business_type,
        "tagline": config.tagline,
        "departments": config.departments,
        "business_activities": config.business_activities,
        "goals": config.goals,
        "kpis": config.kpis,
        "demo_mode": config.demo_mode,
    }


# ╭──────────────────────────────────────────────────────────────────────╮
# │                           SEED                                      │
# ╰──────────────────────────────────────────────────────────────────────╯

class SeedRequest(BaseModel):
    force: bool = False


@router.post("/seed")
def seed_business_workspace(
    body: SeedRequest = SeedRequest(),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    from packages.dogfood.seed import seed_business
    org_id = _get_org_id(db, user)
    summary = seed_business(db, org_id, str(user.id), force=body.force)
    return {"status": "ok", "summary": summary}


# ╭──────────────────────────────────────────────────────────────────────╮
# │                     EXECUTIVE DASHBOARD                             │
# ╰──────────────────────────────────────────────────────────────────────╯

@router.get("/dashboard")
def get_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Executive Command Center — 'What is happening in my business right now?'"""
    org_id = _get_org_id(db, user)

    # Config
    config = db.query(BusinessConfig).filter_by(organization_id=org_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Business not configured. Run seed first.")

    # KPIs
    kpis = db.query(BusinessKPI).filter_by(organization_id=org_id).order_by(BusinessKPI.recorded_at.desc()).all()
    kpi_list = []
    seen_kpis: set = set()
    for k in kpis:
        if k.name not in seen_kpis:
            seen_kpis.add(k.name)
            kpi_list.append({
                "name": k.name, "category": k.category, "value": k.value,
                "unit": k.unit, "target": k.target, "trend": k.trend,
                "is_demo_data": k.is_demo_data,
            })

    # Inbox summary
    inbox_items = db.query(BusinessInboxItem).filter_by(
        organization_id=org_id
    ).filter(
        BusinessInboxItem.status.in_(["open", "acknowledged"])
    ).order_by(
        desc(BusinessInboxItem.created_at)
    ).all()

    attention_items = []
    for item in inbox_items:
        attention_items.append({
            "id": item.id,
            "category": item.category,
            "priority": item.priority,
            "title": item.title,
            "description": item.description,
            "agent_name": item.agent_name,
            "requires_approval": item.requires_approval,
            "is_demo_data": item.is_demo_data,
        })

    # Health summary from KPIs
    revenue_kpi = next((k for k in kpi_list if k["name"] == "Monthly Recurring Revenue"), None)
    customers_kpi = next((k for k in kpi_list if k["name"] == "Active Customers"), None)
    pipeline_kpi = next((k for k in kpi_list if k["name"] == "Pipeline Value"), None)
    expenses_kpi = next((k for k in kpi_list if k["name"] == "Monthly Expenses"), None)
    margin_kpi = next((k for k in kpi_list if k["name"] == "Operating Margin"), None)

    health = {
        "revenue": revenue_kpi,
        "customers": customers_kpi,
        "pipeline": pipeline_kpi,
        "expenses": expenses_kpi,
        "operating_margin": margin_kpi,
    }

    # Recent activities
    activities = db.query(AgentActivity).filter_by(
        organization_id=org_id
    ).order_by(desc(AgentActivity.created_at)).limit(5).all()

    recent_activities = [{
        "id": a.id, "agent_name": a.agent_name, "action": a.action,
        "result": a.result, "created_at": a.created_at.isoformat() if a.created_at else None,
        "is_demo_data": a.is_demo_data,
    } for a in activities]

    return {
        "company_name": config.company_name,
        "product_name": config.product_name,
        "demo_mode": config.demo_mode,
        "health": health,
        "kpis": kpi_list,
        "attention_items": attention_items,
        "recent_activities": recent_activities,
        "summary": {
            "total_kpis": len(kpi_list),
            "open_attention_items": len([i for i in attention_items if i["category"] == "needs_attention"]),
            "pending_approvals": len([i for i in attention_items if i["requires_approval"]]),
            "opportunities": len([i for i in attention_items if i["category"] == "opportunity"]),
            "risks": len([i for i in attention_items if i["category"] == "risk"]),
        },
    }


# ╭──────────────────────────────────────────────────────────────────────╮
# │                       EXECUTIVE BRIEFING                            │
# ╰──────────────────────────────────────────────────────────────────────╯

@router.get("/briefing")
def get_executive_briefing(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """AI-generated executive briefing from available data."""
    org_id = _get_org_id(db, user)

    config = db.query(BusinessConfig).filter_by(organization_id=org_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Business not configured.")

    # Gather data for briefing
    kpis = db.query(BusinessKPI).filter_by(organization_id=org_id).all()
    inbox = db.query(BusinessInboxItem).filter_by(organization_id=org_id).filter(
        BusinessInboxItem.status.in_(["open", "acknowledged"])
    ).all()
    activities = db.query(AgentActivity).filter_by(organization_id=org_id).order_by(
        desc(AgentActivity.created_at)
    ).limit(20).all()

    # Build briefing sections from real data
    priorities = [
        {"title": i.title, "priority": i.priority, "category": i.category,
         "why": i.why_it_matters, "action": i.recommended_action}
        for i in inbox if i.category in ("needs_attention", "needs_approval") and i.priority in ("critical", "high")
    ]

    risks = [
        {"title": i.title, "description": i.description, "evidence": i.evidence, "risk": i.risk}
        for i in inbox if i.category == "risk"
    ]

    opportunities = [
        {"title": i.title, "description": i.description, "evidence": i.evidence, "action": i.recommended_action}
        for i in inbox if i.category == "opportunity"
    ]

    approvals_needed = [
        {"id": i.id, "title": i.title, "description": i.description,
         "agent_name": i.agent_name, "risk": i.risk}
        for i in inbox if i.requires_approval and i.status == "open"
    ]

    completed = [
        {"agent_name": a.agent_name, "action": a.action, "result": a.result}
        for a in activities
    ]

    # KPI highlights
    kpi_highlights = []
    for k in kpis:
        if k.target and k.value:
            pct = (k.value / k.target * 100) if k.target != 0 else 0
            status_str = "on_track" if pct >= 80 else ("at_risk" if pct >= 50 else "behind")
            kpi_highlights.append({
                "name": k.name, "value": k.value, "target": k.target,
                "unit": k.unit, "progress_pct": round(pct, 1),
                "status": status_str, "trend": k.trend, "is_demo_data": k.is_demo_data,
            })

    return {
        "company_name": config.company_name,
        "demo_mode": config.demo_mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "greeting": f"Here's what needs your attention today at {config.company_name}.",
        "top_priorities": priorities,
        "risks": risks,
        "opportunities": opportunities,
        "recommended_actions": [p["action"] for p in priorities if p.get("action")],
        "completed_recently": completed[:10],
        "waiting_for_approval": approvals_needed,
        "kpi_highlights": kpi_highlights,
    }


# ╭──────────────────────────────────────────────────────────────────────╮
# │                       BUSINESS INBOX                                │
# ╰──────────────────────────────────────────────────────────────────────╯

@router.get("/inbox")
def get_inbox(
    category: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    org_id = _get_org_id(db, user)
    q = db.query(BusinessInboxItem).filter_by(organization_id=org_id)
    if category:
        q = q.filter_by(category=category)
    if status_filter:
        q = q.filter_by(status=status_filter)
    else:
        q = q.filter(BusinessInboxItem.status.in_(["open", "acknowledged"]))

    total = q.count()
    items = q.order_by(desc(BusinessInboxItem.created_at)).offset(offset).limit(limit).all()

    return {
        "items": [{
            "id": i.id, "category": i.category, "priority": i.priority,
            "title": i.title, "description": i.description,
            "evidence": i.evidence, "recommended_action": i.recommended_action,
            "risk": i.risk, "why_it_matters": i.why_it_matters,
            "agent_name": i.agent_name, "data_sources": i.data_sources,
            "status": i.status, "requires_approval": i.requires_approval,
            "is_demo_data": i.is_demo_data,
            "created_at": i.created_at.isoformat() if i.created_at else None,
        } for i in items],
        "total": total,
    }


@router.patch("/inbox/{item_id}")
def update_inbox_item(
    item_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    action: str = Query(..., description="acknowledge, resolve, or dismiss"),
) -> dict:
    org_id = _get_org_id(db, user)
    item = db.query(BusinessInboxItem).filter_by(id=item_id, organization_id=org_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inbox item not found")

    if action == "acknowledge":
        item.status = "acknowledged"
    elif action == "resolve":
        item.status = "resolved"
        item.resolved_at = datetime.now(timezone.utc)
    elif action == "dismiss":
        item.status = "dismissed"
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Use: acknowledge, resolve, dismiss")

    db.commit()
    return {"status": "ok", "item_id": item_id, "new_status": item.status}


# ╭──────────────────────────────────────────────────────────────────────╮
# │                      APPROVAL CENTER                                │
# ╰──────────────────────────────────────────────────────────────────────╯

@router.get("/approvals")
def get_pending_approvals(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Centralized 'Needs My Approval' view."""
    org_id = _get_org_id(db, user)

    # Inbox items requiring approval
    inbox_approvals = db.query(BusinessInboxItem).filter_by(
        organization_id=org_id, requires_approval=True, status="open",
    ).order_by(desc(BusinessInboxItem.created_at)).all()

    items = [{
        "id": i.id, "source": "inbox",
        "title": i.title, "description": i.description,
        "reason": i.why_it_matters, "risk": i.risk,
        "agent_name": i.agent_name, "data_sources": i.data_sources,
        "recommended_action": i.recommended_action,
        "evidence": i.evidence,
        "is_demo_data": i.is_demo_data,
        "created_at": i.created_at.isoformat() if i.created_at else None,
    } for i in inbox_approvals]

    # Also include workflow approval requests (from existing system)
    from apps.api.app.models.workflow import ApprovalRequest, ApprovalStatus
    wf_approvals = db.query(ApprovalRequest).filter(
        ApprovalRequest.status == ApprovalStatus.PENDING.value,
    ).order_by(desc(ApprovalRequest.created_at)).all()

    for a in wf_approvals:
        items.append({
            "id": a.id, "source": "workflow",
            "title": a.action_type or "Workflow Action",
            "description": a.action_description,
            "reason": a.reason, "risk": a.risk_level,
            "agent_name": None, "data_sources": [],
            "recommended_action": a.expected_outcome,
            "evidence": a.data_summary,
            "is_demo_data": False,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        })

    return {"approvals": items, "total": len(items)}


class ApprovalDecision(BaseModel):
    decision: str = Field(..., description="approve, reject, or edit")
    note: Optional[str] = None


@router.post("/approvals/{item_id}/decide")
def decide_approval(
    item_id: str,
    body: ApprovalDecision,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    org_id = _get_org_id(db, user)

    # Check inbox items first
    item = db.query(BusinessInboxItem).filter_by(id=item_id, organization_id=org_id).first()
    if item:
        if body.decision == "approve":
            item.status = "resolved"
            item.resolved_at = datetime.now(timezone.utc)
            # Log the approval as an activity
            db.add(AgentActivity(
                organization_id=org_id,
                agent_name=item.agent_name or "System",
                action=f"Approved: {item.title}",
                detail=f"Decision: approved. Note: {body.note or 'N/A'}",
                result="Action approved and queued for execution.",
                is_demo_data=item.is_demo_data,
            ))
        elif body.decision == "reject":
            item.status = "dismissed"
        elif body.decision == "edit":
            item.status = "acknowledged"
        db.commit()
        return {"status": "ok", "item_id": item_id, "decision": body.decision}

    raise HTTPException(status_code=404, detail="Approval item not found")


# ╭──────────────────────────────────────────────────────────────────────╮
# │                     AGENT ACTIVITY                                  │
# ╰──────────────────────────────────────────────────────────────────────╯

@router.get("/activities")
def get_agent_activities(
    agent_name: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    org_id = _get_org_id(db, user)
    q = db.query(AgentActivity).filter_by(organization_id=org_id)
    if agent_name:
        q = q.filter_by(agent_name=agent_name)
    total = q.count()
    activities = q.order_by(desc(AgentActivity.created_at)).offset(offset).limit(limit).all()
    return {
        "activities": [{
            "id": a.id, "agent_name": a.agent_name, "action": a.action,
            "detail": a.detail, "result": a.result,
            "workflow_id": a.workflow_id, "data_sources": a.data_sources,
            "is_demo_data": a.is_demo_data,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        } for a in activities],
        "total": total,
    }


# ╭──────────────────────────────────────────────────────────────────────╮
# │                         KPIs                                        │
# ╰──────────────────────────────────────────────────────────────────────╯

@router.get("/kpis")
def get_kpis(
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    org_id = _get_org_id(db, user)
    q = db.query(BusinessKPI).filter_by(organization_id=org_id)
    if category:
        q = q.filter_by(category=category)
    kpis = q.order_by(desc(BusinessKPI.recorded_at)).all()

    # Deduplicate — latest per name
    seen: set = set()
    result = []
    for k in kpis:
        if k.name not in seen:
            seen.add(k.name)
            result.append({
                "id": k.id, "name": k.name, "category": k.category,
                "value": k.value, "unit": k.unit, "target": k.target,
                "trend": k.trend, "is_demo_data": k.is_demo_data,
                "period": k.period,
                "progress_pct": round(k.value / k.target * 100, 1) if k.target else None,
            })
    return {"kpis": result, "total": len(result)}


# ╭──────────────────────────────────────────────────────────────────────╮
# │                    IMPACT / VALUE DASHBOARD                         │
# ╰──────────────────────────────────────────────────────────────────────╯

@router.get("/impact")
def get_impact_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    org_id = _get_org_id(db, user)
    metrics = db.query(BusinessMetric).filter_by(organization_id=org_id).order_by(
        desc(BusinessMetric.recorded_at)
    ).all()

    return {
        "metrics": [{
            "id": m.id, "metric_name": m.metric_name,
            "metric_value": m.metric_value, "metric_unit": m.metric_unit,
            "confidence": m.confidence, "description": m.description,
            "is_demo_data": m.is_demo_data,
        } for m in metrics],
        "total": len(metrics),
    }


# ╭──────────────────────────────────────────────────────────────────────╮
# │                    DEMO SCENARIOS                                   │
# ╰──────────────────────────────────────────────────────────────────────╯

DEMO_SCENARIOS = [
    {
        "id": "business-review",
        "name": "Run My Business Review",
        "description": "AgentMason analyzes the business and produces an executive briefing.",
        "icon": "📊",
        "objective": "Perform a comprehensive business review. Analyze all KPIs, review customer activity, check lead pipeline, review outstanding invoices, identify risks and opportunities, and generate an executive briefing with prioritized recommendations.",
    },
    {
        "id": "find-customers",
        "name": "Find New Customers",
        "description": "Agents research and prioritize leads.",
        "icon": "🔍",
        "objective": "Research and qualify all open leads in the pipeline. For each lead, determine company fit, score the opportunity, identify likely needs for AgentMason, and create personalized outreach recommendations ranked by priority.",
    },
    {
        "id": "handle-invoices",
        "name": "Handle Overdue Invoices",
        "description": "Finance Agent identifies invoices and Sales Agent prepares follow-ups.",
        "icon": "💰",
        "objective": "Identify all overdue invoices and prepare appropriate follow-up actions. For each overdue invoice, assess the customer relationship, determine appropriate follow-up timing and tone, and draft communications. All communications require approval.",
    },
    {
        "id": "government-opportunities",
        "name": "Find Government Opportunities",
        "description": "Government Contracts Agent analyzes opportunities and creates bid/no-bid recommendations.",
        "icon": "🏛️",
        "objective": "Analyze all tracked government contract opportunities. For each opportunity, evaluate alignment with company capabilities, identify requirement gaps, create compliance checklists, estimate response effort, and recommend bid or no-bid with detailed justification.",
    },
    {
        "id": "find-savings",
        "name": "Find Cost Savings",
        "description": "Finance + Operations + Research agents collaborate.",
        "icon": "💵",
        "objective": "Analyze all recurring expenses, vendor contracts, and operational processes to identify cost reduction opportunities. Quantify potential savings, assess implementation risk, and prioritize recommendations by impact and ease of implementation.",
    },
    {
        "id": "prepare-day",
        "name": "Prepare My Day",
        "description": "AgentMason creates a prioritized list of actions.",
        "icon": "☀️",
        "objective": "Create a prioritized action plan for today. Review all pending items, upcoming deadlines, customer situations, open leads, and business metrics. Produce a focused list of the top 5-7 actions I should take today, ranked by business impact and urgency.",
    },
]


@router.get("/scenarios")
def list_scenarios() -> dict:
    return {"scenarios": DEMO_SCENARIOS}


class ScenarioRunRequest(BaseModel):
    scenario_id: str


@router.post("/scenarios/run")
def run_scenario(
    body: ScenarioRunRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Run a demo scenario through the orchestration engine."""
    org_id = _get_org_id(db, user)

    scenario = next((s for s in DEMO_SCENARIOS if s["id"] == body.scenario_id), None)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    # Use the existing orchestration engine
    try:
        from packages.llm.config import ProviderConfig
        from packages.llm.factory import LLMProviderFactory
        from packages.orchestration.engine import OrchestrationEngine
        from packages.orchestration.registry import SpecializedAgentRegistry
        from packages.orchestration.context import SharedContextBuilder
        from packages.orchestration.conflict import ConflictResolver
        from packages.orchestration.planner import OrchestrationPlanner
        from packages.orchestration.capabilities import CapabilityMatcher

        provider_config = ProviderConfig()
        llm_provider = LLMProviderFactory.create(provider_config)
        agent_registry = SpecializedAgentRegistry(db)
        context_builder = SharedContextBuilder(db)
        conflict_resolver = ConflictResolver()
        planner = OrchestrationPlanner(llm_provider)
        capability_matcher = CapabilityMatcher()

        engine = OrchestrationEngine(
            db=db,
            llm_provider=llm_provider,
            agent_registry=agent_registry,
            context_builder=context_builder,
            conflict_resolver=conflict_resolver,
            planner=planner,
        )

        import asyncio
        result = asyncio.run(engine.execute(
            objective=scenario["objective"],
            organization_id=org_id,
            user_id=str(user.id),
            context={"scenario": scenario["id"], "demo_mode": True},
        ))

        # Log the scenario run
        db.add(AgentActivity(
            organization_id=org_id,
            agent_name="Orchestrator",
            action=f"Ran scenario: {scenario['name']}",
            detail=scenario["objective"],
            result=result.get("final_summary", "Completed"),
            is_demo_data=True,
        ))
        db.commit()

        return {
            "status": "ok",
            "scenario": scenario["name"],
            "execution_id": result.get("id"),
            "summary": result.get("final_summary"),
            "recommendation": result.get("final_recommendation"),
            "confidence": result.get("final_confidence"),
        }
    except Exception as e:
        logger.exception("Scenario execution failed: %s", e)
        # Return a useful result even without LLM
        return {
            "status": "demo_fallback",
            "scenario": scenario["name"],
            "message": f"Scenario '{scenario['name']}' requires a configured LLM provider. The orchestration engine would execute: {scenario['objective']}",
            "note": "Configure OPENAI_API_KEY or another LLM provider to run live orchestration.",
        }
