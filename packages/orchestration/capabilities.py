"""Capability system for matching user requests to agent capabilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Capability(str, Enum):
    """Standard agent capabilities."""
    FINANCIAL_ANALYSIS = "financial_analysis"
    EXPENSE_ANALYSIS = "expense_analysis"
    INVOICE_ANALYSIS = "invoice_analysis"
    FINANCIAL_FORECASTING = "financial_forecasting"
    DOCUMENT_RESEARCH = "document_research"
    MARKET_RESEARCH = "market_research"
    VENDOR_RESEARCH = "vendor_research"
    CUSTOMER_ANALYSIS = "customer_analysis"
    SALES_ANALYSIS = "sales_analysis"
    PIPELINE_ANALYSIS = "pipeline_analysis"
    LEAD_ANALYSIS = "lead_analysis"
    CONTRACT_ANALYSIS = "contract_analysis"
    COMPLIANCE_REVIEW = "compliance_review"
    POLICY_ANALYSIS = "policy_analysis"
    RISK_ASSESSMENT = "risk_assessment"
    BUSINESS_PROCESS_ANALYSIS = "business_process_analysis"
    OPERATIONAL_METRICS = "operational_metrics"
    PROCESS_OPTIMIZATION = "process_optimization"
    WORKFLOW_EXECUTION = "workflow_execution"


# Maps capability keywords found in user requests to capabilities
_CAPABILITY_KEYWORDS: dict[str, list[str]] = {
    Capability.FINANCIAL_ANALYSIS: [
        "financial", "finance", "revenue", "profit", "loss", "budget",
        "cost", "spending", "money", "fiscal", "accounting",
    ],
    Capability.EXPENSE_ANALYSIS: [
        "expense", "expenses", "cost reduction", "cost saving",
        "operating cost", "overhead", "spend",
    ],
    Capability.INVOICE_ANALYSIS: [
        "invoice", "invoices", "billing", "payment", "accounts payable",
        "accounts receivable",
    ],
    Capability.FINANCIAL_FORECASTING: [
        "forecast", "projection", "predict", "trend", "growth",
    ],
    Capability.DOCUMENT_RESEARCH: [
        "research", "investigate", "find information", "look up",
        "search", "analyze document", "review document",
    ],
    Capability.MARKET_RESEARCH: [
        "market", "competitor", "industry", "benchmark",
    ],
    Capability.VENDOR_RESEARCH: [
        "vendor", "supplier", "provider", "contractor",
    ],
    Capability.CUSTOMER_ANALYSIS: [
        "customer", "client", "account", "retention", "churn",
        "customer risk", "leaving",
    ],
    Capability.SALES_ANALYSIS: [
        "sales", "revenue growth", "deal", "quota",
    ],
    Capability.PIPELINE_ANALYSIS: [
        "pipeline", "funnel", "lead", "prospect", "opportunity",
    ],
    Capability.LEAD_ANALYSIS: [
        "lead", "leads", "prospect", "prospects",
    ],
    Capability.CONTRACT_ANALYSIS: [
        "contract", "agreement", "terms", "renewal", "termination",
        "SLA", "service level",
    ],
    Capability.COMPLIANCE_REVIEW: [
        "compliance", "compliant", "regulation", "regulatory",
        "audit", "policy compliance",
    ],
    Capability.POLICY_ANALYSIS: [
        "policy", "policies", "rule", "rules", "guideline",
        "governance",
    ],
    Capability.RISK_ASSESSMENT: [
        "risk", "risks", "threat", "vulnerability", "exposure",
    ],
    Capability.BUSINESS_PROCESS_ANALYSIS: [
        "process", "workflow", "procedure", "bottleneck",
        "efficiency", "optimization",
    ],
    Capability.OPERATIONAL_METRICS: [
        "operational", "operations", "operating", "metrics", "KPI", "performance",
        "productivity",
    ],
    Capability.PROCESS_OPTIMIZATION: [
        "optimize", "improve", "streamline", "automate",
        "reduce waste",
    ],
    Capability.WORKFLOW_EXECUTION: [
        "execute", "action", "do", "perform", "implement",
        "carry out",
    ],
}


@dataclass
class CapabilityMatch:
    """A matched capability with relevance score."""
    capability: str
    score: float
    matched_keywords: list[str] = field(default_factory=list)


class CapabilityMatcher:
    """Matches user requests to capabilities using keyword and LLM analysis."""

    def __init__(self, keyword_map: dict[str, list[str]] | None = None) -> None:
        self._keyword_map = keyword_map or _CAPABILITY_KEYWORDS

    def match_keywords(self, text: str) -> list[CapabilityMatch]:
        """Fast keyword-based capability matching."""
        lower = text.lower()
        matches: list[CapabilityMatch] = []

        for capability, keywords in self._keyword_map.items():
            matched = [kw for kw in keywords if kw.lower() in lower]
            if matched:
                # Score based on number of keyword matches relative to total keywords
                score = min(len(matched) / max(len(keywords) * 0.3, 1), 1.0)
                cap_value = capability.value if isinstance(capability, Capability) else capability
                matches.append(CapabilityMatch(
                    capability=cap_value,
                    score=round(score, 2),
                    matched_keywords=matched,
                ))

        # Sort by score descending
        matches.sort(key=lambda m: m.score, reverse=True)
        return matches

    def get_required_capabilities(self, text: str, threshold: float = 0.1) -> list[str]:
        """Return capabilities above the relevance threshold."""
        matches = self.match_keywords(text)
        return [m.capability for m in matches if m.score >= threshold]
