"""Workflow state machine and transitions."""

from __future__ import annotations

from enum import Enum
from typing import Set


class WorkflowState(str, Enum):
    """Mirrors ExecutionStatus from models for state machine logic."""
    DRAFT = "draft"
    PLANNED = "planned"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_FOR_INPUT = "waiting_for_input"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Legal state transitions
_TRANSITIONS: dict[WorkflowState, Set[WorkflowState]] = {
    WorkflowState.DRAFT: {WorkflowState.PLANNED, WorkflowState.CANCELLED},
    WorkflowState.PLANNED: {WorkflowState.RUNNING, WorkflowState.CANCELLED},
    WorkflowState.RUNNING: {
        WorkflowState.WAITING_FOR_APPROVAL,
        WorkflowState.WAITING_FOR_INPUT,
        WorkflowState.PAUSED,
        WorkflowState.COMPLETED,
        WorkflowState.FAILED,
        WorkflowState.CANCELLED,
    },
    WorkflowState.WAITING_FOR_APPROVAL: {
        WorkflowState.RUNNING,
        WorkflowState.CANCELLED,
        WorkflowState.FAILED,
    },
    WorkflowState.WAITING_FOR_INPUT: {
        WorkflowState.RUNNING,
        WorkflowState.CANCELLED,
    },
    WorkflowState.PAUSED: {
        WorkflowState.RUNNING,
        WorkflowState.CANCELLED,
    },
    WorkflowState.COMPLETED: set(),
    WorkflowState.FAILED: {WorkflowState.RUNNING},   # resume from failure
    WorkflowState.CANCELLED: set(),
}

# Terminal states — no further transitions allowed (except FAILED → RUNNING for recovery)
TERMINAL_STATES = {WorkflowState.COMPLETED, WorkflowState.CANCELLED}
RESUMABLE_STATES = {
    WorkflowState.PAUSED,
    WorkflowState.WAITING_FOR_APPROVAL,
    WorkflowState.WAITING_FOR_INPUT,
    WorkflowState.FAILED,
}


class WorkflowTransitions:
    """Validates and enforces legal state transitions."""

    @staticmethod
    def can_transition(current: WorkflowState, target: WorkflowState) -> bool:
        if current == target:
            return True  # Idempotent — already in target state
        allowed = _TRANSITIONS.get(current, set())
        return target in allowed

    @staticmethod
    def validate_transition(current: WorkflowState, target: WorkflowState) -> None:
        if not WorkflowTransitions.can_transition(current, target):
            raise InvalidTransitionError(
                f"Cannot transition from {current.value} to {target.value}"
            )

    @staticmethod
    def is_terminal(state: WorkflowState) -> bool:
        return state in TERMINAL_STATES

    @staticmethod
    def is_resumable(state: WorkflowState) -> bool:
        return state in RESUMABLE_STATES

    @staticmethod
    def allowed_transitions(state: WorkflowState) -> Set[WorkflowState]:
        return _TRANSITIONS.get(state, set()).copy()


class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass
