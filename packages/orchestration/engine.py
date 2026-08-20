"""Orchestration engine — coordinates specialized agents for multi-agent execution."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from apps.api.app.models.orchestration import (
    SpecializedAgent, OrchestrationExecution, AgentTask, AgentCommunication,
    OrchestrationStatus, AgentTaskStatus, EvidenceType,
)
from apps.api.app.models.workflow import AuditAction
from packages.llm.providers import LLMProvider
from packages.orchestration.capabilities import CapabilityMatcher
from packages.orchestration.registry import SpecializedAgentRegistry
from packages.orchestration.planner import OrchestrationPlanner
from packages.orchestration.conflict import ConflictResolver
from packages.orchestration.context import SharedContextBuilder
from packages.workflows.audit import AuditService

logger = logging.getLogger(__name__)

# Maximum concurrent agent tasks
MAX_PARALLEL_AGENTS = 5
# Default timeout per agent task (seconds)
DEFAULT_AGENT_TIMEOUT = 120

# Prompt injection guard patterns
_INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all instructions",
    "disregard above",
    "forget your instructions",
    "override system prompt",
]

_AGENT_TASK_PROMPT = """\
You are {agent_name}, a specialized agent in the AgentMason platform.

{system_prompt}

Your task:
{task_objective}

Business context:
{context_text}

Rules:
1. Only use information from the provided context and your analysis.
2. Distinguish clearly between FACTS, INFERENCES, RECOMMENDATIONS, and ASSUMPTIONS.
3. Cite sources when referencing specific data.
4. Provide a confidence score (0.0-1.0) for your overall analysis.
5. If you cannot complete the task, explain why.

Respond ONLY with valid JSON:
{{
  "summary": "brief summary of your findings",
  "findings": [
    {{
      "title": "finding title",
      "content": "detailed finding",
      "evidence_type": "fact|inference|recommendation|assumption",
      "source": "where this information came from",
      "confidence": 0.0-1.0
    }}
  ],
  "recommendations": [
    {{
      "title": "recommendation title",
      "description": "detailed recommendation",
      "impact": "expected impact",
      "risk": "associated risk",
      "priority": "high|medium|low"
    }}
  ],
  "evidence": [
    {{
      "source": "source name",
      "type": "document|memory|graph|integration|analysis",
      "reference": "specific reference"
    }}
  ],
  "confidence": 0.0-1.0,
  "risks": [
    {{
      "description": "risk description",
      "severity": "low|medium|high|critical",
      "mitigation": "suggested mitigation"
    }}
  ],
  "required_actions": [
    {{
      "action": "action description",
      "type": "approval|workflow|notification|manual",
      "urgency": "immediate|soon|when_convenient"
    }}
  ],
  "sources": ["list of sources referenced"]
}}
"""

_SYNTHESIS_PROMPT = """\
You are the AgentMason Orchestrator. Multiple specialized agents have analyzed a business \
objective. Synthesize their findings into a unified recommendation.

Objective: {objective}

Agent Results:
{agent_results}

{conflict_resolution_text}

Rules:
1. Provide a coherent, unified analysis — not a collection of separate answers.
2. Weigh evidence quality, source reliability, and confidence levels.
3. If actions are recommended, they must go through the workflow/approval system.
4. High-risk recommendations must be flagged for human review.
5. Explain the reasoning behind the final recommendation.

Respond ONLY with valid JSON:
{{
  "summary": "unified summary of all findings",
  "recommendation": {{
    "title": "main recommendation",
    "description": "detailed recommendation",
    "rationale": "why this is the best course of action",
    "alternatives": ["alternative approaches considered"],
    "risks": ["risks to consider"]
  }},
  "key_findings": [
    {{
      "finding": "key finding",
      "source_agents": ["which agents contributed"],
      "confidence": 0.0-1.0
    }}
  ],
  "required_actions": [
    {{
      "action": "action to take",
      "type": "approval|workflow|notification|manual",
      "risk_level": "low|medium|high|critical",
      "requires_approval": true/false
    }}
  ],
  "confidence": 0.0-1.0,
  "requires_human_approval": true/false,
  "suggested_workflow": {{
    "name": "workflow name if actions are needed",
    "steps": ["list of workflow steps"]
  }}
}}
"""


class OrchestrationEngine:
    """Central orchestrator that coordinates specialized agents."""

    def __init__(
        self,
        db: Session,
        llm_provider: LLMProvider,
        agent_registry: SpecializedAgentRegistry,
        context_builder: SharedContextBuilder,
        conflict_resolver: ConflictResolver | None = None,
        audit_service: AuditService | None = None,
        planner: OrchestrationPlanner | None = None,
    ) -> None:
        self.db = db
        self.llm = llm_provider
        self.registry = agent_registry
        self.context_builder = context_builder
        self.conflict_resolver = conflict_resolver or ConflictResolver(llm_provider)
        self.audit = audit_service or AuditService(db)
        self.planner = planner or OrchestrationPlanner(
            llm_provider, agent_registry, CapabilityMatcher()
        )

    # ------------------------------------------------------------------
    # Plan-only endpoint (for review before execution)
    # ------------------------------------------------------------------

    async def create_plan(
        self,
        objective: str,
        organization_id: str,
        user_id: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create an execution plan without executing it."""
        self._guard_injection(objective)
        plan = await self.planner.create_plan(objective, organization_id, context)
        return plan

    # ------------------------------------------------------------------
    # Full orchestration execution
    # ------------------------------------------------------------------

    async def execute(
        self,
        objective: str,
        organization_id: str,
        user_id: str,
        plan: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> OrchestrationExecution:
        """Execute a multi-agent orchestration.

        1. Plan (or use provided plan)
        2. Create execution record
        3. Delegate tasks to agents
        4. Collect results
        5. Resolve conflicts
        6. Synthesize final answer
        7. Optionally trigger Phase 6 workflow
        """
        self._guard_injection(objective)

        # Step 1: Plan
        if not plan:
            plan = await self.planner.create_plan(objective, organization_id, context)

        tasks_def = plan.get("tasks", [])
        if not tasks_def:
            # No agents needed — direct answer
            return await self._direct_answer(objective, organization_id, user_id)

        # Step 2: Create execution record
        execution = OrchestrationExecution(
            id=str(uuid4()),
            organization_id=organization_id,
            user_id=user_id,
            objective=objective,
            plan=plan,
            status=OrchestrationStatus.PLANNING,
            total_agent_tasks=len(tasks_def),
        )
        self.db.add(execution)
        self.db.commit()
        self.db.refresh(execution)

        self.audit.log(
            organization_id=organization_id,
            action=AuditAction.EXECUTION_STARTED,
            user_id=user_id,
            execution_id=execution.id,
            input_summary={"objective": objective, "plan": plan.get("plan_name")},
        )

        try:
            # Step 3: Create agent task records
            agent_tasks = self._create_agent_tasks(execution, tasks_def, organization_id)

            # Step 4: Execute tasks (parallel/sequential as planned)
            execution.status = OrchestrationStatus.EXECUTING
            execution.started_at = datetime.now(timezone.utc)
            self.db.commit()

            task_results = await self._execute_tasks(
                agent_tasks, execution, organization_id, context
            )

            # Step 5: Detect and resolve conflicts
            execution.status = OrchestrationStatus.MERGING_RESULTS
            self.db.commit()

            conflicts = self.conflict_resolver.detect_conflicts(task_results)

            conflict_resolution = None
            if conflicts:
                execution.status = OrchestrationStatus.RESOLVING_CONFLICTS
                self.db.commit()

                conflict_resolution = await self.conflict_resolver.resolve(
                    objective, task_results, conflicts
                )

                execution.conflicts = [
                    {"topic": c.topic, "agents": c.agents, "severity": c.severity}
                    for c in conflicts
                ]
                execution.conflict_resolution = {
                    "strategy": conflict_resolution.strategy,
                    "resolved_count": len(conflict_resolution.resolved),
                    "unresolved_count": len(conflict_resolution.unresolved),
                    "requires_human_review": conflict_resolution.requires_human_review,
                }
                self.db.commit()

            # Step 6: Synthesize final answer
            synthesis = await self._synthesize_results(
                objective, task_results, conflict_resolution
            )

            # Step 7: Complete execution
            execution.status = OrchestrationStatus.COMPLETED
            execution.final_summary = synthesis.get("summary", "")
            execution.final_recommendation = synthesis.get("recommendation")
            execution.final_confidence = synthesis.get("confidence", 0.5)
            execution.completed_at = datetime.now(timezone.utc)

            # Aggregate cost tracking
            self._aggregate_costs(execution)

            self.db.commit()
            self.db.refresh(execution)

            self.audit.log(
                organization_id=organization_id,
                action=AuditAction.EXECUTION_COMPLETED,
                user_id=user_id,
                execution_id=execution.id,
                output_summary={
                    "summary": execution.final_summary[:500] if execution.final_summary else None,
                    "confidence": execution.final_confidence,
                    "tasks_completed": sum(1 for t in execution.tasks if t.status == AgentTaskStatus.COMPLETED),
                    "conflicts_found": len(conflicts),
                },
            )

            return execution

        except Exception as exc:
            logger.exception("Orchestration failed: %s", exc)
            execution.status = OrchestrationStatus.FAILED
            execution.error = str(exc)
            execution.completed_at = datetime.now(timezone.utc)
            self._aggregate_costs(execution)
            self.db.commit()

            self.audit.log(
                organization_id=organization_id,
                action=AuditAction.EXECUTION_FAILED,
                user_id=user_id,
                execution_id=execution.id,
                error_info=str(exc),
            )
            return execution

    # ------------------------------------------------------------------
    # Task management
    # ------------------------------------------------------------------

    def _create_agent_tasks(
        self,
        execution: OrchestrationExecution,
        tasks_def: list[dict],
        organization_id: str,
    ) -> list[AgentTask]:
        """Create AgentTask records from the plan."""
        agent_tasks: list[AgentTask] = []

        for task_def in tasks_def:
            agent_id = task_def.get("agent_id")
            if not agent_id:
                agent_type = task_def.get("agent_type")
                agent = self.registry.get_by_type(organization_id, agent_type)
                if not agent:
                    logger.warning("Agent type %s not found, skipping task", agent_type)
                    continue
                agent_id = agent.id

            task = AgentTask(
                id=str(uuid4()),
                orchestration_id=execution.id,
                agent_id=agent_id,
                organization_id=organization_id,
                objective=task_def.get("objective", ""),
                expected_output_type=task_def.get("expected_output_type"),
                capabilities_required=task_def.get("capabilities_required"),
                execution_order=task_def.get("execution_order", 0),
                depends_on=task_def.get("depends_on"),
                status=AgentTaskStatus.PENDING,
            )
            self.db.add(task)
            agent_tasks.append(task)

        self.db.commit()
        return agent_tasks

    async def _execute_tasks(
        self,
        agent_tasks: list[AgentTask],
        execution: OrchestrationExecution,
        organization_id: str,
        additional_context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute agent tasks respecting execution order and dependencies."""
        # Group tasks by execution_order
        order_groups: dict[int, list[AgentTask]] = {}
        for task in agent_tasks:
            order_groups.setdefault(task.execution_order, []).append(task)

        all_results: list[dict[str, Any]] = []
        completed_task_results: dict[str, dict[str, Any]] = {}

        for order in sorted(order_groups.keys()):
            group = order_groups[order]

            # Check dependencies
            ready_tasks = []
            for task in group:
                deps = task.depends_on or []
                deps_met = all(
                    dep_id in completed_task_results for dep_id in deps
                )
                if deps_met:
                    ready_tasks.append(task)
                else:
                    task.status = AgentTaskStatus.CANCELLED
                    task.error = "Dependencies not met"
                    self.db.commit()

            if not ready_tasks:
                continue

            # Build context including results from previous phases
            dep_context = additional_context.copy() if additional_context else {}
            if completed_task_results:
                dep_context["previous_agent_results"] = list(completed_task_results.values())

            # Execute tasks in parallel (within same execution_order)
            if len(ready_tasks) == 1:
                result = await self._execute_single_task(
                    ready_tasks[0], execution, organization_id, dep_context
                )
                all_results.append(result)
                completed_task_results[ready_tasks[0].id] = result
            else:
                # Parallel execution with concurrency limit
                semaphore = asyncio.Semaphore(MAX_PARALLEL_AGENTS)

                async def run_with_limit(t: AgentTask) -> dict[str, Any]:
                    async with semaphore:
                        return await self._execute_single_task(
                            t, execution, organization_id, dep_context
                        )

                parallel_results = await asyncio.gather(
                    *(run_with_limit(t) for t in ready_tasks),
                    return_exceptions=True,
                )

                for task, result in zip(ready_tasks, parallel_results):
                    if isinstance(result, Exception):
                        error_result = {
                            "task_id": task.id,
                            "agent_type": "unknown",
                            "status": "failed",
                            "error": str(result),
                            "confidence": 0.0,
                        }
                        all_results.append(error_result)
                        completed_task_results[task.id] = error_result
                    else:
                        all_results.append(result)
                        completed_task_results[task.id] = result

        return all_results

    async def _execute_single_task(
        self,
        task: AgentTask,
        execution: OrchestrationExecution,
        organization_id: str,
        additional_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a single agent task."""
        agent = self.registry.get(task.agent_id, organization_id)
        if not agent:
            task.status = AgentTaskStatus.FAILED
            task.error = "Agent not found"
            self.db.commit()
            return {"task_id": task.id, "agent_type": "unknown", "status": "failed", "error": "Agent not found"}

        task.status = AgentTaskStatus.RUNNING
        task.started_at = datetime.now(timezone.utc)
        self.db.commit()

        self.audit.log(
            organization_id=organization_id,
            action=AuditAction.STEP_STARTED,
            execution_id=execution.id,
            step_execution_id=task.id,
            agent_name=agent.name,
        )

        try:
            # Build context
            context = await self.context_builder.build_context(
                agent=agent,
                organization_id=organization_id,
                objective=task.objective,
                additional_context=additional_context,
            )
            task.context = context

            # Build agent prompt
            context_text = json.dumps(context, default=str, indent=2)
            if len(context_text) > 8000:
                context_text = context_text[:8000] + "\n...(truncated)"

            prompt = _AGENT_TASK_PROMPT.format(
                agent_name=agent.name,
                system_prompt=agent.system_prompt or "",
                task_objective=task.objective,
                context_text=context_text,
            )

            # Execute via LLM with timeout
            model = (agent.model_config_data or {}).get("model", "gpt-4.1")
            temperature = (agent.model_config_data or {}).get("temperature", 0.2)

            try:
                response = await asyncio.wait_for(
                    self.llm.generate(
                        messages=[
                            {"role": "system", "content": prompt},
                            {"role": "user", "content": f"Execute this task: {task.objective}"},
                        ],
                        model=model,
                        temperature=temperature,
                    ),
                    timeout=DEFAULT_AGENT_TIMEOUT,
                )
            except asyncio.TimeoutError:
                task.status = AgentTaskStatus.TIMED_OUT
                task.error = f"Agent timed out after {DEFAULT_AGENT_TIMEOUT}s"
                task.completed_at = datetime.now(timezone.utc)
                self.db.commit()
                return {
                    "task_id": task.id,
                    "agent_type": agent.agent_type,
                    "status": "timed_out",
                    "error": task.error,
                    "confidence": 0.0,
                }

            output = response.get("output", "")
            result = self._parse_agent_result(output, task.id, agent.agent_type)

            # Update task record
            task.status = AgentTaskStatus.COMPLETED
            task.summary = result.get("summary", "")
            task.findings = result.get("findings", [])
            task.recommendations = result.get("recommendations", [])
            task.evidence = result.get("evidence", [])
            task.confidence = result.get("confidence", 0.5)
            task.risks = result.get("risks", [])
            task.required_actions = result.get("required_actions", [])
            task.sources = result.get("sources", [])
            task.llm_calls = 1
            task.completed_at = datetime.now(timezone.utc)
            self.db.commit()

            # Record communication: agent → orchestrator
            comm = AgentCommunication(
                id=str(uuid4()),
                orchestration_id=execution.id,
                organization_id=organization_id,
                from_agent_id=agent.id,
                to_agent_id=None,  # to orchestrator
                message_type="result",
                content=result.get("summary", ""),
                structured_data=result,
            )
            self.db.add(comm)
            self.db.commit()

            self.audit.log(
                organization_id=organization_id,
                action=AuditAction.STEP_COMPLETED,
                execution_id=execution.id,
                step_execution_id=task.id,
                agent_name=agent.name,
                output_summary={"summary": result.get("summary", "")[:200], "confidence": result.get("confidence")},
            )

            return result

        except Exception as exc:
            logger.exception("Agent task failed: %s", exc)
            task.status = AgentTaskStatus.FAILED
            task.error = str(exc)
            task.completed_at = datetime.now(timezone.utc)
            self.db.commit()

            self.audit.log(
                organization_id=organization_id,
                action=AuditAction.STEP_FAILED,
                execution_id=execution.id,
                step_execution_id=task.id,
                agent_name=agent.name if agent else None,
                error_info=str(exc),
            )

            return {
                "task_id": task.id,
                "agent_type": agent.agent_type if agent else "unknown",
                "status": "failed",
                "error": str(exc),
                "confidence": 0.0,
            }

    # ------------------------------------------------------------------
    # Result synthesis
    # ------------------------------------------------------------------

    async def _synthesize_results(
        self,
        objective: str,
        task_results: list[dict[str, Any]],
        conflict_resolution: Any | None = None,
    ) -> dict[str, Any]:
        """Synthesize results from multiple agents into a unified response."""
        agent_results_text = self._format_results_for_synthesis(task_results)

        conflict_text = ""
        if conflict_resolution and conflict_resolution.resolved:
            conflict_text = "\nConflict Resolutions:\n"
            for resolved in conflict_resolution.resolved:
                conflict_text += f"- {resolved.get('topic', 'N/A')}: {resolved.get('resolution', 'N/A')}\n"
        if conflict_resolution and conflict_resolution.unresolved:
            conflict_text += "\nUnresolved Conflicts (require human review):\n"
            for unresolved in conflict_resolution.unresolved:
                conflict_text += f"- {unresolved.get('topic', 'N/A')}: {unresolved.get('reason', 'N/A')}\n"

        prompt = _SYNTHESIS_PROMPT.format(
            objective=objective,
            agent_results=agent_results_text,
            conflict_resolution_text=conflict_text,
        )

        try:
            response = await self.llm.generate(
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": "Provide the unified analysis."},
                ],
                temperature=0.1,
            )
            output = response.get("output", "")
            return self._parse_json_response(output)
        except Exception as exc:
            logger.exception("Synthesis failed: %s", exc)
            # Fallback: merge results manually
            return {
                "summary": f"Analysis of: {objective}",
                "recommendation": {"title": "Review agent findings", "description": "Automated synthesis failed — please review individual agent results."},
                "key_findings": [{"finding": r.get("summary", ""), "source_agents": [r.get("agent_type", "")], "confidence": r.get("confidence", 0.5)} for r in task_results],
                "confidence": self.conflict_resolver._compute_average_confidence(task_results),
                "requires_human_approval": True,
            }

    def _format_results_for_synthesis(self, task_results: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for result in task_results:
            agent = result.get("agent_type", "unknown")
            lines.append(f"\n=== {agent} (confidence: {result.get('confidence', 'N/A')}) ===")
            lines.append(f"Summary: {result.get('summary', 'N/A')}")
            for f in result.get("findings", []):
                lines.append(f"  [{f.get('evidence_type', 'unknown')}] {f.get('title', 'N/A')}: {f.get('content', '')}")
            for r in result.get("recommendations", []):
                lines.append(f"  [Recommendation] {r.get('title', 'N/A')}: {r.get('description', '')}")
            for risk in result.get("risks", []):
                lines.append(f"  [Risk] {risk.get('description', '')}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Direct answer (no agents needed)
    # ------------------------------------------------------------------

    async def _direct_answer(
        self, objective: str, organization_id: str, user_id: str
    ) -> OrchestrationExecution:
        """Handle simple requests that don't need specialized agents."""
        execution = OrchestrationExecution(
            id=str(uuid4()),
            organization_id=organization_id,
            user_id=user_id,
            objective=objective,
            plan={"plan_name": "direct_answer", "tasks": []},
            status=OrchestrationStatus.COMPLETED,
            final_summary="No specialized agents were required for this request.",
            final_confidence=0.5,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        self.db.add(execution)
        self.db.commit()
        self.db.refresh(execution)
        return execution

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_execution(
        self, execution_id: str, organization_id: str
    ) -> OrchestrationExecution | None:
        return self.db.scalar(
            select(OrchestrationExecution).where(
                and_(
                    OrchestrationExecution.id == execution_id,
                    OrchestrationExecution.organization_id == organization_id,
                )
            )
        )

    def list_executions(
        self,
        organization_id: str,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[OrchestrationExecution], int]:
        conditions = [OrchestrationExecution.organization_id == organization_id]
        if status:
            conditions.append(OrchestrationExecution.status == OrchestrationStatus(status))

        total = len(list(self.db.scalars(
            select(OrchestrationExecution).where(and_(*conditions))
        ).all()))

        executions = list(self.db.scalars(
            select(OrchestrationExecution)
            .where(and_(*conditions))
            .order_by(OrchestrationExecution.created_at.desc())
            .offset(offset)
            .limit(limit)
        ).all())
        return executions, total

    def get_task(
        self, task_id: str, organization_id: str
    ) -> AgentTask | None:
        return self.db.scalar(
            select(AgentTask).where(
                and_(
                    AgentTask.id == task_id,
                    AgentTask.organization_id == organization_id,
                )
            )
        )

    def list_tasks(
        self,
        organization_id: str,
        orchestration_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AgentTask], int]:
        conditions = [AgentTask.organization_id == organization_id]
        if orchestration_id:
            conditions.append(AgentTask.orchestration_id == orchestration_id)
        if status:
            conditions.append(AgentTask.status == AgentTaskStatus(status))

        total = len(list(self.db.scalars(
            select(AgentTask).where(and_(*conditions))
        ).all()))

        tasks = list(self.db.scalars(
            select(AgentTask)
            .where(and_(*conditions))
            .order_by(AgentTask.execution_order, AgentTask.created_at)
            .offset(offset)
            .limit(limit)
        ).all())
        return tasks, total

    def get_execution_trace(
        self, execution_id: str, organization_id: str
    ) -> dict[str, Any]:
        """Build a full execution trace for observability."""
        execution = self.get_execution(execution_id, organization_id)
        if not execution:
            return {}

        tasks = list(self.db.scalars(
            select(AgentTask).where(
                and_(
                    AgentTask.orchestration_id == execution_id,
                    AgentTask.organization_id == organization_id,
                )
            ).order_by(AgentTask.execution_order, AgentTask.created_at)
        ).all())

        comms = list(self.db.scalars(
            select(AgentCommunication).where(
                and_(
                    AgentCommunication.orchestration_id == execution_id,
                    AgentCommunication.organization_id == organization_id,
                )
            ).order_by(AgentCommunication.created_at)
        ).all())

        # Get audit entries
        audit_entries, _ = self.audit.get_timeline(
            organization_id=organization_id,
            execution_id=execution_id,
        )

        return {
            "execution_id": execution.id,
            "objective": execution.objective,
            "status": execution.status.value,
            "plan": execution.plan,
            "tasks": [
                {
                    "task_id": t.id,
                    "agent_id": t.agent_id,
                    "objective": t.objective,
                    "status": t.status.value,
                    "execution_order": t.execution_order,
                    "summary": t.summary,
                    "confidence": t.confidence,
                    "findings_count": len(t.findings or []),
                    "recommendations_count": len(t.recommendations or []),
                    "started_at": t.started_at.isoformat() if t.started_at else None,
                    "completed_at": t.completed_at.isoformat() if t.completed_at else None,
                    "error": t.error,
                }
                for t in tasks
            ],
            "communications": [
                {
                    "from_agent": c.from_agent_id,
                    "to_agent": c.to_agent_id,
                    "type": c.message_type,
                    "content": c.content[:200],
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                }
                for c in comms
            ],
            "conflicts": execution.conflicts,
            "conflict_resolution": execution.conflict_resolution,
            "final_summary": execution.final_summary,
            "final_confidence": execution.final_confidence,
            "cost": {
                "total_token_usage": execution.total_token_usage,
                "total_tool_calls": execution.total_tool_calls,
                "total_llm_calls": execution.total_llm_calls,
                "total_agent_tasks": execution.total_agent_tasks,
            },
            "audit_timeline": [
                {
                    "action": e.action.value,
                    "agent_name": e.agent_name,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in audit_entries
            ],
            "started_at": execution.started_at.isoformat() if execution.started_at else None,
            "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
        }

    def get_agent_metrics(self, organization_id: str) -> dict[str, Any]:
        """Compute performance metrics for agents."""
        agents, _ = self.registry.list_agents(organization_id, limit=100)
        metrics: dict[str, Any] = {"agents": []}

        for agent in agents:
            tasks = list(self.db.scalars(
                select(AgentTask).where(
                    and_(
                        AgentTask.agent_id == agent.id,
                        AgentTask.organization_id == organization_id,
                    )
                )
            ).all())

            total = len(tasks)
            completed = sum(1 for t in tasks if t.status == AgentTaskStatus.COMPLETED)
            failed = sum(1 for t in tasks if t.status == AgentTaskStatus.FAILED)
            timed_out = sum(1 for t in tasks if t.status == AgentTaskStatus.TIMED_OUT)

            # Average latency
            latencies: list[float] = []
            for t in tasks:
                if t.started_at and t.completed_at:
                    dt = (t.completed_at - t.started_at).total_seconds()
                    latencies.append(dt)
            avg_latency = round(sum(latencies) / max(len(latencies), 1), 2) if latencies else 0

            # Average confidence
            confidences = [t.confidence for t in tasks if t.confidence is not None]
            avg_confidence = round(sum(confidences) / max(len(confidences), 1), 2) if confidences else 0

            total_tokens = sum(t.token_usage for t in tasks)
            total_llm = sum(t.llm_calls for t in tasks)
            total_tools = sum(t.tool_calls for t in tasks)

            last_task = max(tasks, key=lambda t: t.created_at, default=None)

            metrics["agents"].append({
                "agent_id": agent.id,
                "agent_type": agent.agent_type,
                "name": agent.name,
                "status": agent.status.value,
                "version": agent.version,
                "capabilities": agent.capabilities,
                "risk_level": agent.risk_level.value,
                "tasks_total": total,
                "tasks_completed": completed,
                "tasks_failed": failed,
                "tasks_timed_out": timed_out,
                "success_rate": round(completed / max(total, 1) * 100, 1),
                "avg_latency_seconds": avg_latency,
                "avg_confidence": avg_confidence,
                "total_token_usage": total_tokens,
                "total_llm_calls": total_llm,
                "total_tool_calls": total_tools,
                "last_activity": last_task.created_at.isoformat() if last_task else None,
            })

        return metrics

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _aggregate_costs(self, execution: OrchestrationExecution) -> None:
        """Aggregate cost tracking from all tasks."""
        total_tokens = 0
        total_tools = 0
        total_llm = 0
        for task in execution.tasks:
            total_tokens += task.token_usage
            total_tools += task.tool_calls
            total_llm += task.llm_calls
        execution.total_token_usage = total_tokens
        execution.total_tool_calls = total_tools
        execution.total_llm_calls = total_llm

    def _parse_agent_result(
        self, output: str, task_id: str, agent_type: str
    ) -> dict[str, Any]:
        """Parse agent LLM output into structured result."""
        parsed = self._parse_json_response(output)
        parsed["task_id"] = task_id
        parsed["agent_type"] = agent_type
        parsed["status"] = "completed"
        return parsed

    def _parse_json_response(self, output: str) -> dict[str, Any]:
        """Parse JSON from LLM response, handling markdown code blocks."""
        text = output.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {
                "summary": text[:500],
                "findings": [],
                "recommendations": [],
                "confidence": 0.3,
            }

    def _guard_injection(self, text: str) -> None:
        """Reject text containing prompt injection patterns."""
        lower = text.lower()
        for pattern in _INJECTION_PATTERNS:
            if pattern in lower:
                raise ValueError("Input contains disallowed content")
