"""AI workflow planner — converts natural-language objectives into executable plans."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional
from uuid import uuid4

from packages.llm.providers import LLMProvider
from packages.tools.registry import ToolRegistry
from packages.workflows.risk import RiskClassifier

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = """You are a workflow planning assistant for a business automation system.

Your job is to convert a user's business objective into a structured execution plan.

## Available Tools
{available_tools}

## Business Context
{business_context}

## Rules
1. ONLY use tools from the Available Tools list above. Never invent tools.
2. Each step must have a clear action, a tool name (from available tools), and expected input/output.
3. Mark steps that involve sending external communications, financial transactions, deleting data, or any irreversible action as requiring approval.
4. For batch operations, include a loop step with clear iteration bounds.
5. Include validation and verification steps.
6. If you cannot accomplish the objective with available tools, say so.

## Output Format
Respond with ONLY a valid JSON object (no markdown, no explanation):
{{
  "plan_name": "Human-readable name for this plan",
  "plan_description": "Brief description of what this plan does",
  "estimated_steps": <number>,
  "steps": [
    {{
      "index": 0,
      "name": "step_name",
      "description": "What this step does",
      "type": "action|condition|loop|approval",
      "tool": "tool_name or null",
      "tool_input": {{}},
      "requires_approval": false,
      "risk_level": "low|medium|high",
      "condition": null,
      "loop_config": null,
      "depends_on": []
    }}
  ],
  "inputs_needed": ["list of inputs the user must provide if any"],
  "warnings": ["any concerns about the plan"]
}}
"""


class PlanValidationError(Exception):
    pass


class WorkflowPlanner:
    """Uses an LLM to convert natural-language objectives into executable workflow plans."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        tool_registry: ToolRegistry,
        risk_classifier: RiskClassifier | None = None,
    ) -> None:
        self.llm = llm_provider
        self.tools = tool_registry
        self.risk_classifier = risk_classifier or RiskClassifier()

    async def create_plan(
        self,
        objective: str,
        business_context: str = "",
        model: str = "gpt-4.1",
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        """Generate an execution plan from a natural-language objective."""
        available_tools = self._format_available_tools()

        system_prompt = PLANNER_SYSTEM_PROMPT.format(
            available_tools=available_tools,
            business_context=business_context or "No additional business context provided.",
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Create an execution plan for: {objective}"},
        ]

        response = await self.llm.generate(messages, model=model, temperature=temperature)
        output = response.get("output", "")

        plan = self._parse_plan(output)
        plan = self._validate_plan(plan)
        plan = self._enrich_risk_assessment(plan)
        plan["plan_id"] = str(uuid4())
        plan["objective"] = objective

        return plan

    def _format_available_tools(self) -> str:
        """Format available tools for the planner prompt."""
        tools = self.tools.list()
        if not tools:
            return "No tools available."
        lines = []
        for tool in tools:
            approval = " [REQUIRES APPROVAL]" if tool.requires_approval else ""
            lines.append(f"- {tool.name}: {tool.description} (permission: {tool.permission}){approval}")
        return "\n".join(lines)

    def _parse_plan(self, raw_output: str) -> dict[str, Any]:
        """Parse the LLM output into a structured plan."""
        # Strip markdown fences if present
        text = raw_output.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = lines[1:]  # remove opening fence
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        try:
            plan = json.loads(text)
        except json.JSONDecodeError as e:
            raise PlanValidationError(f"LLM returned invalid JSON: {e}")

        if not isinstance(plan, dict):
            raise PlanValidationError("Plan must be a JSON object")
        if "steps" not in plan or not isinstance(plan["steps"], list):
            raise PlanValidationError("Plan must contain a 'steps' array")

        return plan

    def _validate_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Validate that the plan only references available tools."""
        available = {t.name for t in self.tools.list()}
        validated_steps = []

        for step in plan["steps"]:
            tool_name = step.get("tool")
            if tool_name and tool_name not in available:
                logger.warning("Plan references unavailable tool '%s', removing step", tool_name)
                step["tool"] = None
                step["description"] = f"[UNAVAILABLE TOOL: {tool_name}] {step.get('description', '')}"
                step["type"] = "manual"

            # Ensure required fields
            step.setdefault("index", len(validated_steps))
            step.setdefault("name", f"step_{step['index']}")
            step.setdefault("description", "")
            step.setdefault("type", "action")
            step.setdefault("requires_approval", False)
            step.setdefault("risk_level", "low")
            step.setdefault("condition", None)
            step.setdefault("loop_config", None)
            step.setdefault("depends_on", [])
            step.setdefault("tool_input", {})

            validated_steps.append(step)

        plan["steps"] = validated_steps
        plan["estimated_steps"] = len(validated_steps)
        return plan

    def _enrich_risk_assessment(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Apply risk classifier to each step."""
        for step in plan["steps"]:
            tool_name = step.get("tool")
            if tool_name:
                tool = self.tools.get(tool_name)
                if tool:
                    assessment = self.risk_classifier.assess_tool(
                        tool_name=tool.name,
                        tool_permission=tool.permission,
                        tool_requires_approval=tool.requires_approval,
                        input_data=step.get("tool_input"),
                    )
                    step["risk_level"] = assessment.level
                    step["requires_approval"] = assessment.requires_approval
            else:
                assessment = self.risk_classifier.assess_action(
                    step.get("name", ""),
                    step.get("description", ""),
                )
                step["risk_level"] = assessment.level
                step["requires_approval"] = assessment.requires_approval

        return plan
