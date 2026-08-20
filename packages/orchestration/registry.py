"""Specialized agent registry — discovers and manages agents for orchestration."""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from apps.api.app.models.orchestration import (
    SpecializedAgent, AgentStatus, AgentRiskLevel,
)

logger = logging.getLogger(__name__)


# Default agent definitions used to seed the registry
DEFAULT_AGENTS: list[dict[str, Any]] = [
    {
        "agent_type": "research",
        "name": "Research Agent",
        "description": "Researches business information, analyzes documents, searches connected sources, gathers evidence, and summarizes findings.",
        "capabilities": [
            "document_research", "market_research", "vendor_research",
        ],
        "allowed_tools": [
            "text_analysis", "business_memory", "business_graph",
        ],
        "allowed_data_sources": ["documents", "memory", "graph", "integrations"],
        "permissions": [
            {"action": "read", "resource": "documents"},
            {"action": "read", "resource": "memory"},
            {"action": "read", "resource": "graph"},
            {"action": "read", "resource": "integrations"},
        ],
        "supported_tasks": [
            "research_topic", "analyze_document", "summarize_findings",
            "gather_evidence", "vendor_assessment",
        ],
        "risk_level": AgentRiskLevel.LOW,
        "system_prompt": (
            "You are the Research Agent for AgentMason. Your role is to research business "
            "information, analyze documents, search connected sources, and provide well-sourced "
            "findings. Always cite your sources. Prioritize trusted business sources. "
            "Distinguish clearly between facts, inferences, and assumptions."
        ),
    },
    {
        "agent_type": "finance",
        "name": "Finance Agent",
        "description": "Analyzes financial information, invoices, expenses, identifies cost-saving opportunities, calculates financial impact, and provides financial recommendations.",
        "capabilities": [
            "financial_analysis", "expense_analysis", "invoice_analysis",
            "financial_forecasting",
        ],
        "allowed_tools": [
            "calculator", "text_analysis", "business_memory", "business_graph",
        ],
        "allowed_data_sources": ["documents", "memory", "graph"],
        "permissions": [
            {"action": "read", "resource": "financial_data"},
            {"action": "read", "resource": "documents"},
            {"action": "read", "resource": "memory"},
            {"action": "create", "resource": "financial_analysis"},
        ],
        "supported_tasks": [
            "expense_analysis", "invoice_analysis", "cost_optimization",
            "financial_impact", "budget_review", "vendor_cost_analysis",
        ],
        "risk_level": AgentRiskLevel.HIGH,
        "system_prompt": (
            "You are the Finance Agent for AgentMason. Your role is to analyze financial data, "
            "invoices, expenses, and provide financial recommendations. You must NOT independently "
            "execute financial transactions. All calculations must be precise and verifiable. "
            "Always cite the source of financial figures. Distinguish between confirmed data "
            "and projections."
        ),
    },
    {
        "agent_type": "sales",
        "name": "Sales Agent",
        "description": "Analyzes leads, customers, sales opportunities, researches prospects, recommends follow-ups, and identifies pipeline opportunities.",
        "capabilities": [
            "customer_analysis", "sales_analysis", "pipeline_analysis",
            "lead_analysis",
        ],
        "allowed_tools": [
            "text_analysis", "business_memory", "business_graph",
        ],
        "allowed_data_sources": ["documents", "memory", "graph", "integrations"],
        "permissions": [
            {"action": "read", "resource": "crm_data"},
            {"action": "read", "resource": "documents"},
            {"action": "read", "resource": "memory"},
            {"action": "create", "resource": "drafts"},
        ],
        "supported_tasks": [
            "lead_analysis", "customer_risk_analysis", "pipeline_review",
            "prospect_research", "follow_up_recommendations",
        ],
        "risk_level": AgentRiskLevel.MEDIUM,
        "system_prompt": (
            "You are the Sales Agent for AgentMason. Your role is to analyze leads, customers, "
            "sales opportunities, and pipeline data. Provide actionable recommendations for "
            "sales follow-ups and customer engagement. Communications can only be sent through "
            "the approval system."
        ),
    },
    {
        "agent_type": "operations",
        "name": "Operations Agent",
        "description": "Analyzes business processes, identifies bottlenecks, analyzes operational metrics, and recommends process improvements.",
        "capabilities": [
            "business_process_analysis", "operational_metrics",
            "process_optimization",
        ],
        "allowed_tools": [
            "text_analysis", "business_memory", "business_graph",
        ],
        "allowed_data_sources": ["documents", "memory", "graph"],
        "permissions": [
            {"action": "read", "resource": "operational_data"},
            {"action": "read", "resource": "documents"},
            {"action": "read", "resource": "memory"},
            {"action": "read", "resource": "graph"},
        ],
        "supported_tasks": [
            "process_analysis", "bottleneck_identification",
            "metrics_analysis", "process_improvement",
            "dependency_analysis",
        ],
        "risk_level": AgentRiskLevel.MEDIUM,
        "system_prompt": (
            "You are the Operations Agent for AgentMason. Your role is to analyze business "
            "processes, identify bottlenecks, review operational metrics, and recommend process "
            "improvements. Focus on actionable, measurable improvements. Consider dependencies "
            "between processes."
        ),
    },
    {
        "agent_type": "compliance",
        "name": "Compliance Agent",
        "description": "Analyzes business policies, contracts, checks workflow compliance, identifies policy conflicts and regulatory risks, and flags actions requiring human review.",
        "capabilities": [
            "contract_analysis", "compliance_review", "policy_analysis",
            "risk_assessment",
        ],
        "allowed_tools": [
            "text_analysis", "business_memory", "business_graph",
        ],
        "allowed_data_sources": ["documents", "memory", "graph"],
        "permissions": [
            {"action": "read", "resource": "contracts"},
            {"action": "read", "resource": "policies"},
            {"action": "read", "resource": "documents"},
            {"action": "read", "resource": "memory"},
        ],
        "supported_tasks": [
            "contract_review", "policy_compliance_check",
            "regulatory_risk_assessment", "conflict_identification",
            "approval_requirements",
        ],
        "risk_level": AgentRiskLevel.HIGH,
        "system_prompt": (
            "You are the Compliance Agent for AgentMason. Your role is advisory — analyze "
            "business policies, contracts, and compliance requirements. Identify policy conflicts "
            "and regulatory risks. Flag actions requiring human review. You must NOT make "
            "authoritative legal conclusions. Always indicate uncertainty clearly."
        ),
    },
]


class SpecializedAgentRegistry:
    """Registry for discovering and managing specialized agents."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def seed_defaults(self, organization_id: str, user_id: str) -> list[SpecializedAgent]:
        """Seed default agents for an organization if they don't exist."""
        created: list[SpecializedAgent] = []
        for defn in DEFAULT_AGENTS:
            existing = self.get_by_type(organization_id, defn["agent_type"])
            if existing:
                continue
            agent = self.register(
                organization_id=organization_id,
                user_id=user_id,
                **defn,
            )
            created.append(agent)
        return created

    def register(
        self,
        organization_id: str,
        user_id: str,
        agent_type: str,
        name: str,
        description: str | None = None,
        capabilities: list[str] | None = None,
        allowed_tools: list[str] | None = None,
        allowed_data_sources: list[str] | None = None,
        permissions: list[dict] | None = None,
        supported_tasks: list[str] | None = None,
        model_config_data: dict | None = None,
        system_prompt: str | None = None,
        risk_level: AgentRiskLevel = AgentRiskLevel.MEDIUM,
        version: str = "1.0.0",
    ) -> SpecializedAgent:
        """Register a new specialized agent."""
        agent = SpecializedAgent(
            id=str(uuid4()),
            organization_id=organization_id,
            name=name,
            description=description,
            agent_type=agent_type,
            capabilities=capabilities,
            allowed_tools=allowed_tools,
            allowed_data_sources=allowed_data_sources,
            permissions=permissions,
            supported_tasks=supported_tasks,
            model_config_data=model_config_data,
            system_prompt=system_prompt,
            risk_level=risk_level,
            status=AgentStatus.ACTIVE,
            version=version,
            created_by=user_id,
        )
        self.db.add(agent)
        self.db.commit()
        self.db.refresh(agent)
        logger.info("Registered agent %s (%s) for org %s", name, agent_type, organization_id)
        return agent

    def get(self, agent_id: str, organization_id: str) -> SpecializedAgent | None:
        return self.db.scalar(
            select(SpecializedAgent).where(
                and_(
                    SpecializedAgent.id == agent_id,
                    SpecializedAgent.organization_id == organization_id,
                )
            )
        )

    def get_by_type(self, organization_id: str, agent_type: str) -> SpecializedAgent | None:
        return self.db.scalar(
            select(SpecializedAgent).where(
                and_(
                    SpecializedAgent.organization_id == organization_id,
                    SpecializedAgent.agent_type == agent_type,
                    SpecializedAgent.status == AgentStatus.ACTIVE,
                )
            )
        )

    def list_agents(
        self,
        organization_id: str,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[SpecializedAgent], int]:
        conditions = [SpecializedAgent.organization_id == organization_id]
        if status:
            conditions.append(SpecializedAgent.status == AgentStatus(status))

        total = len(list(self.db.scalars(
            select(SpecializedAgent).where(and_(*conditions))
        ).all()))

        agents = list(self.db.scalars(
            select(SpecializedAgent)
            .where(and_(*conditions))
            .order_by(SpecializedAgent.name)
            .offset(offset)
            .limit(limit)
        ).all())
        return agents, total

    def update(
        self, agent_id: str, organization_id: str, **updates: Any
    ) -> SpecializedAgent | None:
        agent = self.get(agent_id, organization_id)
        if not agent:
            return None

        allowed = {
            "name", "description", "capabilities", "allowed_tools",
            "allowed_data_sources", "permissions", "supported_tasks",
            "model_config_data", "system_prompt", "risk_level", "status", "version",
        }
        for key, value in updates.items():
            if key in allowed and value is not None:
                if key == "status":
                    value = AgentStatus(value)
                if key == "risk_level":
                    value = AgentRiskLevel(value)
                setattr(agent, key, value)

        self.db.commit()
        self.db.refresh(agent)
        return agent

    def find_by_capabilities(
        self, organization_id: str, capabilities: list[str]
    ) -> list[SpecializedAgent]:
        """Find active agents that have any of the requested capabilities."""
        all_agents, _ = self.list_agents(organization_id, status="active", limit=100)
        matched: list[SpecializedAgent] = []
        cap_set = set(capabilities)
        for agent in all_agents:
            agent_caps = set(agent.capabilities or [])
            if agent_caps & cap_set:
                matched.append(agent)
        return matched

    def get_agent_capabilities(self, organization_id: str) -> dict[str, list[str]]:
        """Return a map of agent_type → capabilities for all active agents."""
        agents, _ = self.list_agents(organization_id, status="active", limit=100)
        return {a.agent_type: (a.capabilities or []) for a in agents}
