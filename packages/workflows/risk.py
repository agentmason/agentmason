"""Risk classification system for workflow actions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from packages.tools.base import ToolPermission


class RiskLevel:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Ordered severity for comparison
_SEVERITY = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2, RiskLevel.CRITICAL: 3}


@dataclass
class RiskAssessment:
    """Result of a risk evaluation for a single action."""
    level: str
    requires_approval: bool
    reason: str
    tool_name: str | None = None
    reversible: bool = True
    auto_approve: bool = False


@dataclass
class RiskPolicy:
    """Configurable risk policy for an organization or workflow."""
    # Default thresholds
    auto_approve_levels: list[str] = field(default_factory=lambda: [RiskLevel.LOW])
    require_approval_levels: list[str] = field(default_factory=lambda: [RiskLevel.HIGH, RiskLevel.CRITICAL])

    # Tool-specific overrides
    tool_risk_overrides: dict[str, str] = field(default_factory=dict)
    tool_approval_overrides: dict[str, bool] = field(default_factory=dict)

    # Action-pattern rules (e.g. send_email → MEDIUM)
    action_risk_map: dict[str, str] = field(default_factory=lambda: {
        "search": RiskLevel.LOW,
        "read": RiskLevel.LOW,
        "list": RiskLevel.LOW,
        "get": RiskLevel.LOW,
        "create_draft": RiskLevel.LOW,
        "create_task": RiskLevel.LOW,
        "update": RiskLevel.MEDIUM,
        "create": RiskLevel.MEDIUM,
        "send_email": RiskLevel.MEDIUM,
        "send": RiskLevel.MEDIUM,
        "delete": RiskLevel.HIGH,
        "payment": RiskLevel.HIGH,
        "transfer": RiskLevel.HIGH,
        "contract": RiskLevel.HIGH,
        "submit": RiskLevel.HIGH,
    })

    # Financial thresholds
    financial_approval_threshold: float = 10000.0

    @staticmethod
    def from_dict(data: dict[str, Any]) -> RiskPolicy:
        return RiskPolicy(
            auto_approve_levels=data.get("auto_approve_levels", [RiskLevel.LOW]),
            require_approval_levels=data.get("require_approval_levels", [RiskLevel.HIGH, RiskLevel.CRITICAL]),
            tool_risk_overrides=data.get("tool_risk_overrides", {}),
            tool_approval_overrides=data.get("tool_approval_overrides", {}),
            action_risk_map=data.get("action_risk_map", RiskPolicy().action_risk_map),
            financial_approval_threshold=data.get("financial_approval_threshold", 10000.0),
        )


class RiskClassifier:
    """Classifies actions by risk level and determines approval requirements."""

    def __init__(self, policy: RiskPolicy | None = None) -> None:
        self.policy = policy or RiskPolicy()

    def assess_tool(
        self,
        tool_name: str,
        tool_permission: str,
        tool_requires_approval: bool,
        input_data: dict[str, Any] | None = None,
    ) -> RiskAssessment:
        """Classify risk for a tool execution."""
        # 1. Check tool-specific override
        if tool_name in self.policy.tool_risk_overrides:
            level = self.policy.tool_risk_overrides[tool_name]
        # 2. Map by permission type
        elif tool_permission == ToolPermission.DESTRUCTIVE:
            level = RiskLevel.HIGH
        elif tool_permission == ToolPermission.WRITE:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.LOW

        # 3. Check action-pattern rules
        for pattern, pattern_level in self.policy.action_risk_map.items():
            if pattern in tool_name.lower():
                if _SEVERITY.get(pattern_level, 0) > _SEVERITY.get(level, 0):
                    level = pattern_level
                break

        # 4. Check financial thresholds in input
        if input_data:
            amount = _extract_financial_amount(input_data)
            if amount is not None and amount > self.policy.financial_approval_threshold:
                level = RiskLevel.HIGH

        # 5. Determine approval requirement
        if tool_name in self.policy.tool_approval_overrides:
            requires_approval = self.policy.tool_approval_overrides[tool_name]
        elif tool_requires_approval:
            requires_approval = True
        elif level in self.policy.require_approval_levels:
            requires_approval = True
        else:
            requires_approval = False

        auto_approve = level in self.policy.auto_approve_levels and not requires_approval
        reversible = tool_permission != ToolPermission.DESTRUCTIVE

        return RiskAssessment(
            level=level,
            requires_approval=requires_approval,
            reason=f"Tool '{tool_name}' classified as {level} risk (permission={tool_permission})",
            tool_name=tool_name,
            reversible=reversible,
            auto_approve=auto_approve,
        )

    def assess_action(
        self,
        action_name: str,
        description: str = "",
        input_data: dict[str, Any] | None = None,
    ) -> RiskAssessment:
        """Classify risk for a generic action (used by planner before tool selection)."""
        level = RiskLevel.MEDIUM  # default
        for pattern, pattern_level in self.policy.action_risk_map.items():
            if pattern in action_name.lower() or pattern in description.lower():
                level = pattern_level
                break

        if input_data:
            amount = _extract_financial_amount(input_data)
            if amount is not None and amount > self.policy.financial_approval_threshold:
                level = RiskLevel.HIGH

        requires_approval = level in self.policy.require_approval_levels
        return RiskAssessment(
            level=level,
            requires_approval=requires_approval,
            reason=f"Action '{action_name}' classified as {level} risk",
            reversible=True,
        )


def _extract_financial_amount(data: dict[str, Any]) -> float | None:
    """Try to extract a monetary amount from action input data."""
    for key in ("amount", "total", "price", "cost", "value", "payment_amount", "invoice_amount"):
        if key in data:
            try:
                return float(data[key])
            except (TypeError, ValueError):
                continue
    return None
