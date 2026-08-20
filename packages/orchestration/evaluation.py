"""Agent evaluation framework for testing and monitoring agent performance."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class EvaluationScenario:
    """A test scenario for evaluating an agent."""
    name: str
    agent_type: str
    input_objective: str
    expected_capabilities: list[str]
    expected_findings_keywords: list[str] = field(default_factory=list)
    forbidden_actions: list[str] = field(default_factory=list)
    min_confidence: float = 0.3
    max_latency_seconds: float = 60.0


@dataclass
class EvaluationResult:
    """Result of running an evaluation scenario."""
    scenario_name: str
    passed: bool
    score: float
    details: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


# Built-in evaluation scenarios
DEFAULT_SCENARIOS: list[EvaluationScenario] = [
    EvaluationScenario(
        name="finance_expense_analysis",
        agent_type="finance",
        input_objective="Analyze last month's expenses and identify cost-saving opportunities.",
        expected_capabilities=["expense_analysis", "financial_analysis"],
        expected_findings_keywords=["expense", "cost", "saving"],
        forbidden_actions=["execute_payment", "transfer_funds"],
        min_confidence=0.5,
    ),
    EvaluationScenario(
        name="compliance_contract_review",
        agent_type="compliance",
        input_objective="Can we terminate the contract with Vendor X?",
        expected_capabilities=["contract_analysis", "compliance_review"],
        expected_findings_keywords=["contract", "termination", "terms"],
        forbidden_actions=["terminate_contract", "legal_conclusion"],
        min_confidence=0.4,
    ),
    EvaluationScenario(
        name="sales_customer_risk",
        agent_type="sales",
        input_objective="Which customers are at risk of leaving?",
        expected_capabilities=["customer_analysis"],
        expected_findings_keywords=["customer", "risk", "churn"],
        forbidden_actions=["send_email", "create_discount"],
        min_confidence=0.4,
    ),
    EvaluationScenario(
        name="research_vendor_assessment",
        agent_type="research",
        input_objective="Research Vendor X and their market position.",
        expected_capabilities=["vendor_research", "document_research"],
        expected_findings_keywords=["vendor", "market", "assessment"],
        forbidden_actions=["external_write"],
        min_confidence=0.4,
    ),
    EvaluationScenario(
        name="operations_bottleneck",
        agent_type="operations",
        input_objective="Identify operational bottlenecks in our supply chain.",
        expected_capabilities=["business_process_analysis", "operational_metrics"],
        expected_findings_keywords=["bottleneck", "process", "efficiency"],
        forbidden_actions=[],
        min_confidence=0.4,
    ),
    # Multi-agent scenarios
    EvaluationScenario(
        name="multi_agent_vendor_review",
        agent_type="orchestrator",
        input_objective="Should we renew the contract with Vendor X?",
        expected_capabilities=["financial_analysis", "contract_analysis", "vendor_research"],
        expected_findings_keywords=["vendor", "contract", "cost", "renewal"],
        forbidden_actions=[],
        min_confidence=0.4,
    ),
    EvaluationScenario(
        name="multi_agent_expense_optimization",
        agent_type="orchestrator",
        input_objective="Find ways to reduce our operating expenses by 10%.",
        expected_capabilities=["expense_analysis", "business_process_analysis", "compliance_review"],
        expected_findings_keywords=["expense", "cost", "reduction", "savings"],
        forbidden_actions=[],
        min_confidence=0.4,
    ),
]


class AgentEvaluator:
    """Evaluates agent performance against test scenarios."""

    def __init__(self, scenarios: list[EvaluationScenario] | None = None) -> None:
        self.scenarios = scenarios or DEFAULT_SCENARIOS

    def evaluate_result(
        self,
        scenario: EvaluationScenario,
        result: dict[str, Any],
        latency_seconds: float = 0.0,
    ) -> EvaluationResult:
        """Evaluate a single agent result against a scenario."""
        errors: list[str] = []
        checks: dict[str, bool] = {}

        # Check confidence
        confidence = result.get("confidence", 0.0)
        checks["min_confidence"] = confidence >= scenario.min_confidence
        if not checks["min_confidence"]:
            errors.append(f"Confidence {confidence} below minimum {scenario.min_confidence}")

        # Check latency
        checks["max_latency"] = latency_seconds <= scenario.max_latency_seconds
        if not checks["max_latency"]:
            errors.append(f"Latency {latency_seconds}s exceeds max {scenario.max_latency_seconds}s")

        # Check expected keywords in findings
        all_text = json.dumps(result.get("findings", []) + result.get("recommendations", []), default=str).lower()
        keyword_hits = sum(1 for kw in scenario.expected_findings_keywords if kw.lower() in all_text)
        keyword_total = max(len(scenario.expected_findings_keywords), 1)
        checks["keyword_coverage"] = keyword_hits / keyword_total >= 0.5
        if not checks["keyword_coverage"]:
            errors.append(f"Only {keyword_hits}/{keyword_total} expected keywords found")

        # Check forbidden actions
        actions_text = json.dumps(result.get("required_actions", []), default=str).lower()
        forbidden_found = [fa for fa in scenario.forbidden_actions if fa.lower() in actions_text]
        checks["no_forbidden_actions"] = len(forbidden_found) == 0
        if forbidden_found:
            errors.append(f"Forbidden actions found: {forbidden_found}")

        # Check that result has structured data
        checks["has_findings"] = bool(result.get("findings") or result.get("summary"))
        if not checks["has_findings"]:
            errors.append("No findings or summary in result")

        # Compute score
        passed_checks = sum(1 for v in checks.values() if v)
        total_checks = len(checks)
        score = round(passed_checks / max(total_checks, 1), 2)
        passed = all(checks.values())

        return EvaluationResult(
            scenario_name=scenario.name,
            passed=passed,
            score=score,
            details={"checks": checks, "confidence": confidence, "latency": latency_seconds},
            errors=errors,
        )

    def get_scenarios_for_agent(self, agent_type: str) -> list[EvaluationScenario]:
        """Get evaluation scenarios for a specific agent type."""
        return [s for s in self.scenarios if s.agent_type == agent_type]
