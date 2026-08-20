"""Cost control and budget enforcement for workflow executions."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CostPolicy:
    """Configurable cost limits for a workflow execution."""
    max_token_usage: int = 100_000
    max_llm_calls: int = 50
    max_tool_calls: int = 100
    max_duration_seconds: int = 3600
    max_steps: int = 50
    max_iterations: int = 100

    @staticmethod
    def from_dict(data: dict[str, Any]) -> CostPolicy:
        return CostPolicy(
            max_token_usage=data.get("max_token_usage", 100_000),
            max_llm_calls=data.get("max_llm_calls", 50),
            max_tool_calls=data.get("max_tool_calls", 100),
            max_duration_seconds=data.get("max_duration_seconds", 3600),
            max_steps=data.get("max_steps", 50),
            max_iterations=data.get("max_iterations", 100),
        )


@dataclass
class CostTracker:
    """Tracks running costs during workflow execution."""
    token_usage: int = 0
    llm_calls: int = 0
    tool_calls: int = 0
    steps_executed: int = 0
    iterations: int = 0
    elapsed_seconds: float = 0.0


class CostLimitExceeded(Exception):
    """Raised when a cost limit is exceeded."""
    def __init__(self, limit_type: str, current: int | float, maximum: int | float) -> None:
        self.limit_type = limit_type
        self.current = current
        self.maximum = maximum
        super().__init__(f"Cost limit exceeded: {limit_type} ({current}/{maximum})")


class CostController:
    """Enforces cost limits during workflow execution."""

    def __init__(self, policy: CostPolicy | None = None) -> None:
        self.policy = policy or CostPolicy()
        self.tracker = CostTracker()

    def record_tokens(self, count: int) -> None:
        self.tracker.token_usage += count

    def record_llm_call(self) -> None:
        self.tracker.llm_calls += 1

    def record_tool_call(self) -> None:
        self.tracker.tool_calls += 1

    def record_step(self) -> None:
        self.tracker.steps_executed += 1

    def record_iteration(self) -> None:
        self.tracker.iterations += 1

    def update_elapsed(self, seconds: float) -> None:
        self.tracker.elapsed_seconds = seconds

    def check_limits(self) -> None:
        """Check all limits. Raises CostLimitExceeded if any exceeded."""
        if self.tracker.token_usage > self.policy.max_token_usage:
            raise CostLimitExceeded("token_usage", self.tracker.token_usage, self.policy.max_token_usage)
        if self.tracker.llm_calls > self.policy.max_llm_calls:
            raise CostLimitExceeded("llm_calls", self.tracker.llm_calls, self.policy.max_llm_calls)
        if self.tracker.tool_calls > self.policy.max_tool_calls:
            raise CostLimitExceeded("tool_calls", self.tracker.tool_calls, self.policy.max_tool_calls)
        if self.tracker.steps_executed > self.policy.max_steps:
            raise CostLimitExceeded("steps", self.tracker.steps_executed, self.policy.max_steps)
        if self.tracker.iterations > self.policy.max_iterations:
            raise CostLimitExceeded("iterations", self.tracker.iterations, self.policy.max_iterations)
        if self.tracker.elapsed_seconds > self.policy.max_duration_seconds:
            raise CostLimitExceeded("duration_seconds", self.tracker.elapsed_seconds, self.policy.max_duration_seconds)

    def get_usage(self) -> dict[str, Any]:
        """Return current usage vs limits."""
        return {
            "token_usage": {"current": self.tracker.token_usage, "limit": self.policy.max_token_usage},
            "llm_calls": {"current": self.tracker.llm_calls, "limit": self.policy.max_llm_calls},
            "tool_calls": {"current": self.tracker.tool_calls, "limit": self.policy.max_tool_calls},
            "steps": {"current": self.tracker.steps_executed, "limit": self.policy.max_steps},
            "iterations": {"current": self.tracker.iterations, "limit": self.policy.max_iterations},
            "duration_seconds": {"current": self.tracker.elapsed_seconds, "limit": self.policy.max_duration_seconds},
        }
