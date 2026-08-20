"""Orchestration planner — analyzes objectives and creates multi-agent execution plans."""

from __future__ import annotations

import json
import logging
from typing import Any

from packages.llm.providers import LLMProvider
from packages.orchestration.capabilities import CapabilityMatcher
from packages.orchestration.registry import SpecializedAgentRegistry

logger = logging.getLogger(__name__)

# Prompt injection patterns to reject
_INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all instructions",
    "disregard above",
    "forget your instructions",
    "override system prompt",
    "new instructions:",
    "you are now",
    "pretend you are",
]

_PLANNER_SYSTEM_PROMPT = """\
You are the AgentMason Orchestration Planner. Your role is to analyze a user's business \
objective and determine the optimal plan for using specialized agents.

Available agents and their capabilities:
{agent_catalog}

Rules:
1. Use the MINIMUM number of agents necessary to accomplish the objective.
2. If only one agent is needed, plan a single-agent execution.
3. Mark tasks that can run in parallel with the same execution_order number.
4. Tasks that depend on previous results must have a higher execution_order.
5. For each task, specify the required capabilities and expected output type.
6. Consider agent risk levels — high-risk actions may require approval.
7. Be precise about what each agent should do.

Respond ONLY with valid JSON in this exact format:
{{
  "plan_name": "short name for the plan",
  "plan_description": "brief description of the overall approach",
  "requires_multiple_agents": true/false,
  "estimated_risk": "low|medium|high|critical",
  "show_plan_to_user": true/false,
  "tasks": [
    {{
      "agent_type": "agent type name",
      "objective": "what this agent should do",
      "capabilities_required": ["list of capabilities needed"],
      "expected_output_type": "analysis|recommendation|review|assessment",
      "execution_order": 0,
      "depends_on": [],
      "reasoning": "why this agent is needed"
    }}
  ],
  "execution_strategy": "parallel|sequential|mixed",
  "warnings": ["any concerns about the plan"]
}}
"""


class OrchestrationPlanner:
    """Creates execution plans by matching objectives to agent capabilities."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        agent_registry: SpecializedAgentRegistry,
        capability_matcher: CapabilityMatcher | None = None,
    ) -> None:
        self.llm = llm_provider
        self.registry = agent_registry
        self.capability_matcher = capability_matcher or CapabilityMatcher()

    async def create_plan(
        self,
        objective: str,
        organization_id: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Analyze the objective and create an execution plan.

        Uses keyword matching for fast capability identification, then LLM
        for intelligent agent selection and task decomposition.
        """
        # Guard against prompt injection
        lower_obj = objective.lower()
        for pattern in _INJECTION_PATTERNS:
            if pattern in lower_obj:
                raise ValueError("Objective contains disallowed content")

        # Step 1: Fast keyword-based capability identification
        required_capabilities = self.capability_matcher.get_required_capabilities(objective)

        # Step 2: Find agents matching those capabilities
        matching_agents = self.registry.find_by_capabilities(
            organization_id, required_capabilities
        )

        if not matching_agents:
            # Fallback: use all active agents and let LLM decide
            matching_agents, _ = self.registry.list_agents(
                organization_id, status="active", limit=100
            )

        if not matching_agents:
            return self._single_agent_fallback(objective)

        # Step 3: Build agent catalog for LLM
        agent_catalog = self._build_agent_catalog(matching_agents)

        # Step 4: LLM-based planning
        system_prompt = _PLANNER_SYSTEM_PROMPT.format(agent_catalog=agent_catalog)

        user_message = f"Objective: {objective}"
        if context:
            user_message += f"\n\nAdditional context: {json.dumps(context, default=str)}"

        try:
            response = await self.llm.generate(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.1,
            )

            output = response.get("output", "")
            plan = self._parse_plan(output)

            # Validate that planned agents actually exist
            plan = self._validate_plan(plan, organization_id)
            plan["required_capabilities"] = required_capabilities

            return plan

        except Exception as exc:
            logger.exception("LLM planning failed: %s", exc)
            # Fallback to capability-based plan without LLM
            return self._capability_based_plan(
                objective, required_capabilities, matching_agents
            )

    def _build_agent_catalog(self, agents: list) -> str:
        """Build a text catalog of available agents for the LLM."""
        lines: list[str] = []
        for agent in agents:
            caps = ", ".join(agent.capabilities or [])
            lines.append(
                f"- {agent.agent_type} ({agent.name}): "
                f"capabilities=[{caps}], risk_level={agent.risk_level.value}"
            )
        return "\n".join(lines)

    def _parse_plan(self, output: str) -> dict[str, Any]:
        """Parse LLM output into a structured plan."""
        # Extract JSON from response
        text = output.strip()
        # Handle markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        try:
            plan = json.loads(text)
        except json.JSONDecodeError:
            raise ValueError("Failed to parse orchestration plan from LLM response")

        # Validate required fields
        if "tasks" not in plan or not isinstance(plan["tasks"], list):
            raise ValueError("Plan must contain a 'tasks' list")

        return plan

    def _validate_plan(self, plan: dict[str, Any], organization_id: str) -> dict[str, Any]:
        """Validate that all agents in the plan exist and are active."""
        valid_tasks: list[dict] = []
        for task in plan.get("tasks", []):
            agent_type = task.get("agent_type")
            if agent_type:
                agent = self.registry.get_by_type(organization_id, agent_type)
                if agent and agent.status.value == "active":
                    task["agent_id"] = agent.id
                    valid_tasks.append(task)
                else:
                    logger.warning("Agent type %s not found/active, skipping", agent_type)

        plan["tasks"] = valid_tasks
        return plan

    def _capability_based_plan(
        self,
        objective: str,
        capabilities: list[str],
        agents: list,
    ) -> dict[str, Any]:
        """Create a simple plan based on capability matching alone."""
        tasks: list[dict] = []
        seen_types: set[str] = set()

        for agent in agents:
            if agent.agent_type in seen_types:
                continue
            agent_caps = set(agent.capabilities or [])
            matched = agent_caps & set(capabilities)
            if matched:
                tasks.append({
                    "agent_type": agent.agent_type,
                    "agent_id": agent.id,
                    "objective": f"Analyze the following objective using your {', '.join(matched)} capabilities: {objective}",
                    "capabilities_required": list(matched),
                    "expected_output_type": "analysis",
                    "execution_order": 0,  # All parallel by default
                    "depends_on": [],
                    "reasoning": f"Agent has matching capabilities: {', '.join(matched)}",
                })
                seen_types.add(agent.agent_type)

        return {
            "plan_name": "capability_based_plan",
            "plan_description": f"Automated plan for: {objective[:100]}",
            "requires_multiple_agents": len(tasks) > 1,
            "estimated_risk": "medium",
            "show_plan_to_user": len(tasks) > 2,
            "tasks": tasks,
            "execution_strategy": "parallel" if len(tasks) > 1 else "sequential",
            "warnings": ["Plan generated without LLM — may be less optimized"],
            "required_capabilities": capabilities,
        }

    def _single_agent_fallback(self, objective: str) -> dict[str, Any]:
        """Fallback plan when no agents are available."""
        return {
            "plan_name": "fallback_plan",
            "plan_description": "No matching agents found",
            "requires_multiple_agents": False,
            "estimated_risk": "low",
            "show_plan_to_user": False,
            "tasks": [],
            "execution_strategy": "sequential",
            "warnings": ["No specialized agents available for this objective"],
            "required_capabilities": [],
        }
