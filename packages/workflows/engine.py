"""Workflow execution engine — orchestrates plan execution with approval gates,
cost controls, failure handling, and recovery."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from apps.api.app.models.workflow import (
    Workflow, WorkflowExecution, WorkflowStepExecution,
    ApprovalRequest, ExecutionStatus, StepStatus, RiskLevel as RiskLevelEnum, AuditAction,
    WorkflowStatus, ApprovalStatus,
)
from packages.tools.registry import ToolRegistry
from packages.tools.base import ToolError
from packages.llm.providers import LLMProvider
from packages.workflows.states import WorkflowState, WorkflowTransitions, InvalidTransitionError
from packages.workflows.risk import RiskClassifier, RiskPolicy
from packages.workflows.approval import ApprovalService
from packages.workflows.audit import AuditService
from packages.workflows.conditions import ConditionEvaluator
from packages.workflows.cost import CostController, CostPolicy, CostLimitExceeded
from packages.workflows.planner import WorkflowPlanner

logger = logging.getLogger(__name__)

# Content-filtering keywords for prompt injection protection
_INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all instructions",
    "disregard above",
    "forget your instructions",
    "override system prompt",
    "new instructions:",
    "you are now",
    "act as if",
    "pretend you are",
    "system: ",
]


class WorkflowExecutionEngine:
    """Orchestrates the execution of workflow plans with full lifecycle management."""

    def __init__(
        self,
        db: Session,
        tool_registry: ToolRegistry,
        llm_provider: LLMProvider,
        risk_classifier: RiskClassifier | None = None,
    ) -> None:
        self.db = db
        self.tools = tool_registry
        self.llm = llm_provider
        self.risk_classifier = risk_classifier or RiskClassifier()
        self.approval_service = ApprovalService(db)
        self.audit_service = AuditService(db)
        self.condition_evaluator = ConditionEvaluator()
        self.planner = WorkflowPlanner(llm_provider, tool_registry, self.risk_classifier)

    # ------------------------------------------------------------------
    # Workflow CRUD
    # ------------------------------------------------------------------

    def create_workflow(
        self,
        organization_id: str,
        name: str,
        user_id: str,
        description: str | None = None,
        trigger: str | None = None,
        steps: list[dict] | None = None,
        inputs: dict | None = None,
        conditions: dict | None = None,
        tools: list[str] | None = None,
        approval_policy: dict | None = None,
        retry_policy: dict | None = None,
        risk_policy: dict | None = None,
        cost_policy: dict | None = None,
        max_steps: int = 50,
        max_iterations: int = 100,
        timeout_seconds: int = 3600,
        is_template: bool = False,
        template_category: str | None = None,
    ) -> Workflow:
        """Create a new workflow definition."""
        # Validate tool references
        if tools:
            available = {t.name for t in self.tools.list()}
            invalid = [t for t in tools if t not in available]
            if invalid:
                raise ValueError(f"Unknown tools: {invalid}")

        workflow = Workflow(
            id=str(uuid4()),
            organization_id=organization_id,
            name=name,
            description=description,
            trigger=trigger,
            status=WorkflowStatus.DRAFT,
            steps=steps,
            inputs=inputs,
            conditions=conditions,
            tools=tools,
            approval_policy=approval_policy,
            retry_policy=retry_policy,
            risk_policy=risk_policy,
            cost_policy=cost_policy,
            max_steps=max_steps,
            max_iterations=max_iterations,
            timeout_seconds=timeout_seconds,
            is_template=is_template,
            template_category=template_category,
            created_by=user_id,
        )
        self.db.add(workflow)
        self.db.commit()
        self.db.refresh(workflow)

        self.audit_service.log(
            organization_id=organization_id,
            action=AuditAction.WORKFLOW_CREATED,
            user_id=user_id,
            workflow_id=workflow.id,
        )
        return workflow

    def get_workflow(self, workflow_id: str, organization_id: str) -> Workflow | None:
        return self.db.scalar(
            select(Workflow).where(
                and_(Workflow.id == workflow_id, Workflow.organization_id == organization_id)
            )
        )

    def list_workflows(
        self,
        organization_id: str,
        status: str | None = None,
        is_template: bool | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Workflow], int]:
        conditions = [Workflow.organization_id == organization_id]
        if status:
            conditions.append(Workflow.status == WorkflowStatus(status))
        if is_template is not None:
            conditions.append(Workflow.is_template == is_template)

        count_stmt = select(Workflow).where(and_(*conditions))
        total = len(list(self.db.scalars(count_stmt).all()))

        stmt = (
            select(Workflow)
            .where(and_(*conditions))
            .order_by(Workflow.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all()), total

    def update_workflow(
        self, workflow_id: str, organization_id: str, user_id: str, **updates: Any
    ) -> Workflow | None:
        workflow = self.get_workflow(workflow_id, organization_id)
        if not workflow:
            return None

        allowed = {
            "name", "description", "trigger", "status", "steps", "inputs",
            "conditions", "tools", "approval_policy", "retry_policy", "risk_policy",
            "cost_policy", "max_steps", "max_iterations", "timeout_seconds",
            "is_template", "template_category",
        }
        for key, value in updates.items():
            if key in allowed and value is not None:
                if key == "status":
                    value = WorkflowStatus(value)
                setattr(workflow, key, value)

        self.db.commit()
        self.db.refresh(workflow)

        self.audit_service.log(
            organization_id=organization_id,
            action=AuditAction.WORKFLOW_UPDATED,
            user_id=user_id,
            workflow_id=workflow.id,
        )
        return workflow

    def delete_workflow(self, workflow_id: str, organization_id: str, user_id: str) -> bool:
        workflow = self.get_workflow(workflow_id, organization_id)
        if not workflow:
            return False

        self.audit_service.log(
            organization_id=organization_id,
            action=AuditAction.WORKFLOW_DELETED,
            user_id=user_id,
            workflow_id=workflow.id,
        )
        self.db.delete(workflow)
        self.db.commit()
        return True

    # ------------------------------------------------------------------
    # Execution lifecycle
    # ------------------------------------------------------------------

    async def execute_workflow(
        self,
        workflow_id: str,
        organization_id: str,
        user_id: str,
        inputs: dict[str, Any] | None = None,
        objective: str | None = None,
    ) -> WorkflowExecution:
        """Start a new workflow execution.

        If ``objective`` is provided, the planner generates steps dynamically.
        Otherwise, the workflow's predefined steps are used.
        """
        workflow = self.get_workflow(workflow_id, organization_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")
        if workflow.status not in (WorkflowStatus.ACTIVE, WorkflowStatus.DRAFT):
            raise ValueError(f"Workflow is {workflow.status.value}, cannot execute")

        # Build or use predefined plan
        if objective:
            # AI planner mode — generate steps from objective
            business_context = await self._gather_business_context(organization_id, objective)
            plan = await self.planner.create_plan(objective, business_context=business_context)
            steps = plan.get("steps", [])
        else:
            steps = workflow.steps or []
            plan = {"plan_name": workflow.name, "steps": steps}

        # Resolve input templates
        resolved_inputs = inputs or {}
        steps = self._resolve_step_templates(steps, resolved_inputs)

        # Create execution record
        execution = WorkflowExecution(
            id=str(uuid4()),
            workflow_id=workflow_id,
            organization_id=organization_id,
            user_id=user_id,
            status=ExecutionStatus.PLANNED,
            plan=plan,
            inputs=resolved_inputs,
            objective=objective,
            total_steps=len(steps),
            current_step_index=0,
            completed_steps=0,
            context={},
        )
        self.db.add(execution)

        # Create step execution records
        for step_def in steps:
            step_exec = WorkflowStepExecution(
                id=str(uuid4()),
                execution_id=execution.id,
                organization_id=organization_id,
                step_index=step_def.get("index", 0),
                step_name=step_def.get("name", "unnamed_step"),
                step_type=step_def.get("type", "action"),
                status=StepStatus.PENDING,
                tool_name=step_def.get("tool"),
                tool_input=step_def.get("tool_input"),
                risk_level=RiskLevelEnum(step_def.get("risk_level", "low")),
                requires_approval=step_def.get("requires_approval", False),
                max_retries=self._get_max_retries(workflow),
                reasoning=step_def.get("description"),
            )
            self.db.add(step_exec)

        self.db.commit()
        self.db.refresh(execution)

        self.audit_service.log(
            organization_id=organization_id,
            action=AuditAction.EXECUTION_STARTED,
            user_id=user_id,
            workflow_id=workflow_id,
            execution_id=execution.id,
        )

        # Begin execution
        return await self._run_execution(execution, workflow)

    async def resume_execution(
        self,
        execution_id: str,
        organization_id: str,
        user_id: str,
    ) -> WorkflowExecution:
        """Resume a paused/failed/waiting execution from its current step."""
        execution = self._get_execution(execution_id, organization_id)
        if not execution:
            raise ValueError(f"Execution {execution_id} not found")

        current_state = WorkflowState(execution.status.value)
        if not WorkflowTransitions.is_resumable(current_state):
            raise ValueError(f"Execution is {execution.status.value}, cannot resume")

        # If waiting for approval, check if approvals have been resolved
        if current_state == WorkflowState.WAITING_FOR_APPROVAL:
            pending = self.approval_service.get_pending(organization_id, execution_id)
            if pending:
                raise ValueError(f"Cannot resume: {len(pending)} approval(s) still pending")

        workflow = self.get_workflow(execution.workflow_id, organization_id)
        if not workflow:
            raise ValueError("Associated workflow not found")

        self._transition(execution, WorkflowState.RUNNING)

        self.audit_service.log(
            organization_id=organization_id,
            action=AuditAction.EXECUTION_RESUMED,
            user_id=user_id,
            workflow_id=execution.workflow_id,
            execution_id=execution_id,
        )

        return await self._run_execution(execution, workflow)

    def pause_execution(self, execution_id: str, organization_id: str, user_id: str) -> WorkflowExecution:
        execution = self._get_execution(execution_id, organization_id)
        if not execution:
            raise ValueError(f"Execution {execution_id} not found")
        self._transition(execution, WorkflowState.PAUSED)
        self.audit_service.log(
            organization_id=organization_id,
            action=AuditAction.EXECUTION_PAUSED,
            user_id=user_id,
            execution_id=execution_id,
            workflow_id=execution.workflow_id,
        )
        return execution

    def cancel_execution(self, execution_id: str, organization_id: str, user_id: str) -> WorkflowExecution:
        execution = self._get_execution(execution_id, organization_id)
        if not execution:
            raise ValueError(f"Execution {execution_id} not found")
        self._transition(execution, WorkflowState.CANCELLED)
        execution.completed_at = datetime.now(timezone.utc)

        # Cancel pending steps
        for step in execution.step_executions:
            if step.status in (StepStatus.PENDING, StepStatus.RUNNING, StepStatus.WAITING_FOR_APPROVAL):
                step.status = StepStatus.CANCELLED

        # Cancel pending approvals
        for req in execution.approval_requests:
            if req.status == ApprovalStatus.PENDING:
                req.status = ApprovalStatus.CANCELLED

        self.db.commit()
        self.audit_service.log(
            organization_id=organization_id,
            action=AuditAction.EXECUTION_CANCELLED,
            user_id=user_id,
            execution_id=execution_id,
            workflow_id=execution.workflow_id,
        )
        return execution

    def get_execution(self, execution_id: str, organization_id: str) -> WorkflowExecution | None:
        return self._get_execution(execution_id, organization_id)

    def list_executions(
        self,
        organization_id: str,
        workflow_id: str | None = None,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[WorkflowExecution], int]:
        conditions = [WorkflowExecution.organization_id == organization_id]
        if workflow_id:
            conditions.append(WorkflowExecution.workflow_id == workflow_id)
        if status:
            conditions.append(WorkflowExecution.status == ExecutionStatus(status))

        count_stmt = select(WorkflowExecution).where(and_(*conditions))
        total = len(list(self.db.scalars(count_stmt).all()))

        stmt = (
            select(WorkflowExecution)
            .where(and_(*conditions))
            .order_by(WorkflowExecution.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all()), total

    # ------------------------------------------------------------------
    # Internal execution loop
    # ------------------------------------------------------------------

    async def _run_execution(self, execution: WorkflowExecution, workflow: Workflow) -> WorkflowExecution:
        """Run the execution from its current step index."""
        cost_policy = CostPolicy.from_dict(workflow.cost_policy or {})
        cost_ctrl = CostController(cost_policy)
        cost_ctrl.tracker.tool_calls = execution.total_tool_calls
        cost_ctrl.tracker.llm_calls = execution.total_llm_calls
        cost_ctrl.tracker.token_usage = execution.total_token_usage
        cost_ctrl.tracker.steps_executed = execution.completed_steps

        self._transition(execution, WorkflowState.RUNNING)
        execution.started_at = execution.started_at or datetime.now(timezone.utc)
        self.db.commit()

        start_time = time.monotonic()
        step_execs = sorted(execution.step_executions, key=lambda s: s.step_index)

        try:
            idx = execution.current_step_index
            while idx < len(step_execs):
                step_exec = step_execs[idx]

                # Skip already completed/skipped steps (recovery)
                if step_exec.status in (StepStatus.COMPLETED, StepStatus.SKIPPED):
                    idx += 1
                    execution.current_step_index = idx
                    self.db.commit()
                    continue

                # Check cost limits
                elapsed = time.monotonic() - start_time
                cost_ctrl.update_elapsed(elapsed)
                try:
                    cost_ctrl.check_limits()
                except CostLimitExceeded as cle:
                    self._transition(execution, WorkflowState.PAUSED)
                    execution.error = str(cle)
                    self._sync_cost_tracking(execution, cost_ctrl)
                    self.db.commit()
                    self.audit_service.log(
                        organization_id=execution.organization_id,
                        action=AuditAction.COST_LIMIT_REACHED,
                        execution_id=execution.id,
                        workflow_id=workflow.id,
                        error_info=str(cle),
                    )
                    return execution

                # Execute the step
                result = await self._execute_step(step_exec, execution, workflow, cost_ctrl)

                if result == "waiting_for_approval":
                    self._transition(execution, WorkflowState.WAITING_FOR_APPROVAL)
                    self._sync_cost_tracking(execution, cost_ctrl)
                    self.db.commit()
                    return execution

                if result == "failed":
                    # Check retry
                    if step_exec.retry_count < step_exec.max_retries:
                        step_exec.retry_count += 1
                        step_exec.status = StepStatus.PENDING
                        self.db.commit()
                        self.audit_service.log(
                            organization_id=execution.organization_id,
                            action=AuditAction.STEP_RETRIED,
                            execution_id=execution.id,
                            step_execution_id=step_exec.id,
                            workflow_id=workflow.id,
                        )
                        # Exponential backoff
                        backoff = self._get_backoff(workflow, step_exec.retry_count)
                        await asyncio.sleep(min(backoff, 5))  # cap actual sleep for responsiveness
                        continue
                    else:
                        # Exhausted retries — fail execution
                        self._transition(execution, WorkflowState.FAILED)
                        execution.error = f"Step '{step_exec.step_name}' failed after {step_exec.retry_count} retries: {step_exec.error}"
                        execution.completed_at = datetime.now(timezone.utc)
                        self._sync_cost_tracking(execution, cost_ctrl)
                        self.db.commit()
                        self.audit_service.log(
                            organization_id=execution.organization_id,
                            action=AuditAction.EXECUTION_FAILED,
                            execution_id=execution.id,
                            workflow_id=workflow.id,
                            error_info=execution.error,
                        )
                        return execution

                if result == "skipped":
                    pass  # move to next

                # Advance
                idx += 1
                execution.current_step_index = idx
                self.db.commit()

            # All steps completed
            self._transition(execution, WorkflowState.COMPLETED)
            execution.completed_at = datetime.now(timezone.utc)
            execution.outputs = self._build_outputs(execution)
            self._sync_cost_tracking(execution, cost_ctrl)
            self.db.commit()

            self.audit_service.log(
                organization_id=execution.organization_id,
                action=AuditAction.EXECUTION_COMPLETED,
                execution_id=execution.id,
                workflow_id=workflow.id,
                output_summary=execution.outputs,
            )

        except Exception as exc:
            logger.exception("Workflow execution failed: %s", exc)
            self._transition(execution, WorkflowState.FAILED)
            execution.error = str(exc)
            execution.completed_at = datetime.now(timezone.utc)
            self._sync_cost_tracking(execution, cost_ctrl)
            self.db.commit()
            self.audit_service.log(
                organization_id=execution.organization_id,
                action=AuditAction.EXECUTION_FAILED,
                execution_id=execution.id,
                workflow_id=workflow.id,
                error_info=str(exc),
            )

        return execution

    async def _execute_step(
        self,
        step: WorkflowStepExecution,
        execution: WorkflowExecution,
        workflow: Workflow,
        cost_ctrl: CostController,
    ) -> str:
        """Execute a single step. Returns 'completed', 'failed', 'skipped', or 'waiting_for_approval'."""
        step.status = StepStatus.RUNNING
        step.started_at = datetime.now(timezone.utc)
        self.db.commit()

        self.audit_service.log(
            organization_id=execution.organization_id,
            action=AuditAction.STEP_STARTED,
            execution_id=execution.id,
            step_execution_id=step.id,
            workflow_id=workflow.id,
            tool_name=step.tool_name,
        )

        try:
            # Handle different step types
            if step.step_type == "condition":
                return await self._execute_condition_step(step, execution)

            if step.step_type == "approval" or (step.requires_approval and not self._has_approval(step)):
                return await self._execute_approval_step(step, execution, workflow)

            if step.step_type == "loop":
                return await self._execute_loop_step(step, execution, workflow, cost_ctrl)

            # Regular action step
            if not step.tool_name:
                # No tool — mark as completed (manual/informational step)
                step.status = StepStatus.COMPLETED
                step.completed_at = datetime.now(timezone.utc)
                execution.completed_steps += 1
                cost_ctrl.record_step()
                self.db.commit()
                return "completed"

            # Check approval requirement based on risk
            tool = self.tools.get(step.tool_name)
            if not tool:
                step.status = StepStatus.FAILED
                step.error = f"Tool '{step.tool_name}' not available"
                step.completed_at = datetime.now(timezone.utc)
                self.db.commit()
                return "failed"

            risk_assessment = self.risk_classifier.assess_tool(
                tool_name=tool.name,
                tool_permission=tool.permission,
                tool_requires_approval=tool.requires_approval,
                input_data=step.tool_input,
            )

            if risk_assessment.requires_approval and not self._has_approval(step):
                return await self._execute_approval_step(step, execution, workflow)

            # Sanitize tool input for prompt injection
            sanitized_input = self._sanitize_input(step.tool_input or {})

            # Execute tool
            cost_ctrl.record_tool_call()
            tool_result = await tool.execute(sanitized_input)

            step.tool_output = tool_result
            step.status = StepStatus.COMPLETED
            step.completed_at = datetime.now(timezone.utc)
            execution.completed_steps += 1
            cost_ctrl.record_step()

            # Store output in execution context for downstream steps
            ctx = execution.context or {}
            ctx[f"step_output_{step.step_name}"] = tool_result
            execution.context = ctx

            self.db.commit()

            self.audit_service.log(
                organization_id=execution.organization_id,
                action=AuditAction.TOOL_EXECUTED,
                execution_id=execution.id,
                step_execution_id=step.id,
                workflow_id=workflow.id,
                tool_name=step.tool_name,
                risk_level=risk_assessment.level,
                input_summary=sanitized_input,
                output_summary=tool_result if isinstance(tool_result, dict) else {"result": str(tool_result)},
            )
            return "completed"

        except ToolError as te:
            step.status = StepStatus.FAILED
            step.error = str(te)
            step.completed_at = datetime.now(timezone.utc)
            self.db.commit()
            self.audit_service.log(
                organization_id=execution.organization_id,
                action=AuditAction.TOOL_FAILED,
                execution_id=execution.id,
                step_execution_id=step.id,
                workflow_id=workflow.id,
                tool_name=step.tool_name,
                error_info=str(te),
            )
            return "failed"

        except Exception as exc:
            step.status = StepStatus.FAILED
            step.error = str(exc)
            step.completed_at = datetime.now(timezone.utc)
            self.db.commit()
            self.audit_service.log(
                organization_id=execution.organization_id,
                action=AuditAction.STEP_FAILED,
                execution_id=execution.id,
                step_execution_id=step.id,
                workflow_id=workflow.id,
                error_info=str(exc),
            )
            return "failed"

    async def _execute_condition_step(
        self, step: WorkflowStepExecution, execution: WorkflowExecution
    ) -> str:
        """Evaluate a condition step."""
        condition = (step.metadata_payload or {}).get("condition") or (step.tool_input or {})
        ctx = {
            "context": execution.context or {},
            "inputs": execution.inputs or {},
            "step_output": execution.context or {},
        }
        result = self.condition_evaluator.evaluate(condition, ctx)
        step.tool_output = {"condition_result": result}
        step.status = StepStatus.COMPLETED
        step.completed_at = datetime.now(timezone.utc)
        execution.completed_steps += 1
        self.db.commit()
        return "completed"

    async def _execute_approval_step(
        self, step: WorkflowStepExecution, execution: WorkflowExecution, workflow: Workflow
    ) -> str:
        """Create an approval request and pause."""
        approval = self.approval_service.create_request(
            execution_id=execution.id,
            organization_id=execution.organization_id,
            action_type=step.tool_name or step.step_name,
            action_description=step.reasoning or f"Approval required for: {step.step_name}",
            risk_level=step.risk_level.value if step.risk_level else "medium",
            step_execution_id=step.id,
            action_parameters=step.tool_input,
            reason=f"Workflow '{workflow.name}' requires approval for this action",
            target_system=step.tool_name,
            expected_outcome=step.reasoning,
        )
        step.approval_id = approval.id
        self.db.commit()

        self.audit_service.log(
            organization_id=execution.organization_id,
            action=AuditAction.APPROVAL_REQUESTED,
            execution_id=execution.id,
            step_execution_id=step.id,
            workflow_id=workflow.id,
            tool_name=step.tool_name,
            risk_level=step.risk_level.value if step.risk_level else None,
        )
        return "waiting_for_approval"

    async def _execute_loop_step(
        self,
        step: WorkflowStepExecution,
        execution: WorkflowExecution,
        workflow: Workflow,
        cost_ctrl: CostController,
    ) -> str:
        """Execute a loop step (batch processing)."""
        loop_config = (step.metadata_payload or {}).get("loop_config") or (step.tool_input or {}).get("loop_config")
        if not loop_config:
            step.status = StepStatus.COMPLETED
            step.completed_at = datetime.now(timezone.utc)
            execution.completed_steps += 1
            self.db.commit()
            return "completed"

        max_iterations = min(loop_config.get("max_iterations", 50), 100)
        # Resolve collection to iterate over
        items_path = loop_config.get("over", "")
        items = self._resolve_context_value(items_path, execution.context or {})
        if not isinstance(items, list):
            items = []

        results = []
        iteration = 0
        for item in items[:max_iterations]:
            iteration += 1
            cost_ctrl.record_iteration()
            try:
                cost_ctrl.check_limits()
            except CostLimitExceeded:
                break
            results.append({"iteration": iteration, "item": str(item)[:200], "status": "processed"})

        step.tool_output = {"iterations": iteration, "results": results}
        step.status = StepStatus.COMPLETED
        step.completed_at = datetime.now(timezone.utc)
        execution.completed_steps += 1
        self.db.commit()
        return "completed"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_execution(self, execution_id: str, organization_id: str) -> WorkflowExecution | None:
        return self.db.scalar(
            select(WorkflowExecution).where(
                and_(
                    WorkflowExecution.id == execution_id,
                    WorkflowExecution.organization_id == organization_id,
                )
            )
        )

    def _transition(self, execution: WorkflowExecution, target: WorkflowState) -> None:
        current = WorkflowState(execution.status.value)
        WorkflowTransitions.validate_transition(current, target)
        execution.status = ExecutionStatus(target.value)
        self.db.commit()

    def _has_approval(self, step: WorkflowStepExecution) -> bool:
        """Check if the step already has a granted approval."""
        if not step.approval_id:
            return False
        approval = self.db.scalar(
            select(ApprovalRequest).where(ApprovalRequest.id == step.approval_id)
        )
        return approval is not None and approval.status == ApprovalStatus.APPROVED

    def _get_max_retries(self, workflow: Workflow) -> int:
        policy = workflow.retry_policy or {}
        return policy.get("max_retries", 3)

    def _get_backoff(self, workflow: Workflow, retry_count: int) -> float:
        policy = workflow.retry_policy or {}
        base = policy.get("backoff_seconds", 5)
        return min(base * (2 ** (retry_count - 1)), 300)

    def _sync_cost_tracking(self, execution: WorkflowExecution, cost_ctrl: CostController) -> None:
        execution.total_token_usage = cost_ctrl.tracker.token_usage
        execution.total_tool_calls = cost_ctrl.tracker.tool_calls
        execution.total_llm_calls = cost_ctrl.tracker.llm_calls

    def _resolve_step_templates(self, steps: list[dict], inputs: dict[str, Any]) -> list[dict]:
        """Replace {variable} placeholders in step definitions with input values."""
        import json as _json
        raw = _json.dumps(steps)
        for key, value in inputs.items():
            raw = raw.replace(f"{{{key}}}", str(value))
        return _json.loads(raw)

    def _resolve_context_value(self, path: str, context: dict[str, Any]) -> Any:
        """Resolve a dot-path value from execution context."""
        parts = path.split(".")
        current: Any = context
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current

    def _build_outputs(self, execution: WorkflowExecution) -> dict[str, Any]:
        """Build a summary output from completed steps."""
        step_results = []
        for step in sorted(execution.step_executions, key=lambda s: s.step_index):
            step_results.append({
                "step": step.step_name,
                "status": step.status.value,
                "output": step.tool_output,
            })
        return {
            "steps_completed": execution.completed_steps,
            "total_steps": execution.total_steps,
            "step_results": step_results,
        }

    def _sanitize_input(self, data: dict[str, Any]) -> dict[str, Any]:
        """Protect against prompt injection in tool inputs originating from external data."""
        sanitized = {}
        for key, value in data.items():
            if isinstance(value, str):
                sanitized[key] = self._check_injection(value)
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_input(value)
            else:
                sanitized[key] = value
        return sanitized

    def _check_injection(self, text: str) -> str:
        """Flag but do not remove potential injection content — treat as data, not instructions."""
        lower = text.lower()
        for pattern in _INJECTION_PATTERNS:
            if pattern in lower:
                logger.warning("Potential prompt injection detected in workflow input: '%s...'", text[:100])
                # Wrap in data delimiter to prevent LLM interpretation as instruction
                return f"[DATA]{text}[/DATA]"
        return text

    async def _gather_business_context(self, organization_id: str, objective: str) -> str:
        """Gather business context from memory, graph, and RAG for the planner."""
        context_parts: list[str] = []

        # Search business memory
        try:
            from packages.memory.service import MemoryService
            memory_svc = MemoryService(self.db)
            memories, _ = memory_svc.search(organization_id, query=objective, limit=5)
            if memories:
                context_parts.append("## Relevant Business Memories")
                for m in memories:
                    context_parts.append(f"- [{m.category.value}] {m.title}: {m.content[:200]}")
        except Exception as e:
            logger.debug("Could not gather memory context: %s", e)

        # Search business graph
        try:
            from packages.graph.service import GraphService
            graph_svc = GraphService(self.db)
            entities = graph_svc.search(organization_id, query=objective, limit=5)
            if entities:
                context_parts.append("\n## Relevant Business Entities")
                for ent in entities:
                    context_parts.append(f"- [{ent.entity_type.value}] {ent.name}")
        except Exception as e:
            logger.debug("Could not gather graph context: %s", e)

        return "\n".join(context_parts) if context_parts else ""
