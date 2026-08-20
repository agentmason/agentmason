"""Conflict resolution for multi-agent orchestration."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from packages.llm.providers import LLMProvider
from apps.api.app.models.orchestration import ConflictResolutionStrategy

logger = logging.getLogger(__name__)

_CONFLICT_RESOLUTION_PROMPT = """\
You are the AgentMason Conflict Resolver. Multiple specialized agents have provided \
findings about a business objective, and some findings conflict with each other.

Objective: {objective}

Agent Findings:
{findings_text}

Identified Conflicts:
{conflicts_text}

Rules:
1. Consider the evidence, source reliability, agent expertise, confidence level, and risk.
2. Do NOT arbitrarily select one answer over another.
3. If the conflict cannot be safely resolved, recommend human review.
4. Provide a clear explanation of the resolution rationale.
5. Policy and compliance constraints override cost optimization suggestions.

Respond ONLY with valid JSON:
{{
  "resolution_strategy": "evidence_weight|confidence_rank|expertise_priority|human_review|policy_override",
  "resolved_findings": [
    {{
      "topic": "what the conflict is about",
      "resolution": "the resolved conclusion",
      "rationale": "why this resolution was chosen",
      "contributing_agents": ["agent types that informed this"],
      "confidence": 0.0-1.0,
      "requires_human_review": true/false
    }}
  ],
  "unresolved_conflicts": [
    {{
      "topic": "conflict that cannot be resolved",
      "reason": "why it requires human review",
      "agent_positions": {{"agent_type": "their position"}}
    }}
  ],
  "overall_confidence": 0.0-1.0
}}
"""


@dataclass
class Conflict:
    """A detected conflict between agent findings."""
    topic: str
    agents: list[str]
    positions: dict[str, str]
    severity: str = "medium"  # low, medium, high


@dataclass
class ConflictResolution:
    """Result of conflict resolution."""
    strategy: str
    resolved: list[dict[str, Any]] = field(default_factory=list)
    unresolved: list[dict[str, Any]] = field(default_factory=list)
    overall_confidence: float = 0.0
    requires_human_review: bool = False


class ConflictResolver:
    """Detects and resolves conflicts between agent results."""

    def __init__(self, llm_provider: LLMProvider) -> None:
        self.llm = llm_provider

    def detect_conflicts(
        self, task_results: list[dict[str, Any]]
    ) -> list[Conflict]:
        """Detect conflicts between agent task results.

        Looks for contradictory recommendations, conflicting facts,
        and incompatible required actions.
        """
        conflicts: list[Conflict] = []

        # Group findings by topic keywords
        findings_by_topic: dict[str, list[tuple[str, dict]]] = {}
        for result in task_results:
            agent_type = result.get("agent_type", "unknown")
            for finding in result.get("findings", []):
                topic = finding.get("topic", finding.get("title", "general"))
                key = topic.lower().strip()
                findings_by_topic.setdefault(key, []).append((agent_type, finding))

            for rec in result.get("recommendations", []):
                topic = rec.get("topic", rec.get("title", "general"))
                key = topic.lower().strip()
                findings_by_topic.setdefault(key, []).append((agent_type, rec))

        # Check for conflicting positions on the same topic
        for topic, entries in findings_by_topic.items():
            if len(entries) < 2:
                continue

            agents = [e[0] for e in entries]
            if len(set(agents)) < 2:
                continue

            # Different agents have opinions on same topic — check for contradictions
            positions = {}
            for agent_type, entry in entries:
                position = entry.get("recommendation", entry.get("conclusion", entry.get("content", "")))
                positions[agent_type] = str(position)

            # Simple contradiction detection: look for opposing sentiment keywords
            has_conflict = self._detect_opposition(list(positions.values()))
            if has_conflict:
                conflicts.append(Conflict(
                    topic=topic,
                    agents=list(positions.keys()),
                    positions=positions,
                    severity="medium",
                ))

        # Check for conflicting required_actions
        all_actions: dict[str, list[tuple[str, str]]] = {}
        for result in task_results:
            agent_type = result.get("agent_type", "unknown")
            for action in result.get("required_actions", []):
                action_type = action.get("type", action.get("action", "unknown"))
                all_actions.setdefault(action_type, []).append(
                    (agent_type, action.get("description", ""))
                )

        for action_type, entries in all_actions.items():
            if len(entries) >= 2 and len(set(e[0] for e in entries)) >= 2:
                positions = {e[0]: e[1] for e in entries}
                if self._detect_opposition(list(positions.values())):
                    conflicts.append(Conflict(
                        topic=f"action:{action_type}",
                        agents=list(positions.keys()),
                        positions=positions,
                        severity="high",
                    ))

        return conflicts

    def _detect_opposition(self, statements: list[str]) -> bool:
        """Heuristic check for opposing statements."""
        # Multi-word negative phrases checked first
        negative_phrases = ["should not", "do not", "don't"]
        # Single-word negative indicators
        negative_words = {"replace", "terminate", "stop", "reduce", "remove", "cancel", "eliminate", "discontinue"}
        # Single-word positive indicators
        positive_words = {"should", "recommend", "approve", "renew", "continue", "increase", "keep", "maintain"}

        sentiments: list[str] = []
        for stmt in statements:
            lower = stmt.lower()
            # Check negative phrases first
            has_neg_phrase = any(neg in lower for neg in negative_phrases)
            has_neg_word = any(word in lower.split() for word in negative_words)
            has_neg = has_neg_phrase or has_neg_word
            has_pos = any(word in lower.split() for word in positive_words)
            if has_neg and not has_pos:
                sentiments.append("negative")
            elif has_neg and has_pos:
                # Negative phrase trumps positive word (e.g. "should replace")
                sentiments.append("negative")
            elif has_pos:
                sentiments.append("positive")
            else:
                sentiments.append("neutral")

        unique = set(sentiments) - {"neutral"}
        return len(unique) > 1

    async def resolve(
        self,
        objective: str,
        task_results: list[dict[str, Any]],
        conflicts: list[Conflict],
    ) -> ConflictResolution:
        """Resolve detected conflicts using LLM analysis."""
        if not conflicts:
            return ConflictResolution(
                strategy=ConflictResolutionStrategy.EVIDENCE_WEIGHT.value,
                overall_confidence=self._compute_average_confidence(task_results),
            )

        # Build prompts
        findings_text = self._format_findings(task_results)
        conflicts_text = self._format_conflicts(conflicts)

        prompt = _CONFLICT_RESOLUTION_PROMPT.format(
            objective=objective,
            findings_text=findings_text,
            conflicts_text=conflicts_text,
        )

        try:
            response = await self.llm.generate(
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": "Resolve the conflicts above."},
                ],
                temperature=0.1,
            )

            output = response.get("output", "")
            parsed = self._parse_resolution(output)

            requires_human = bool(parsed.get("unresolved_conflicts"))
            for resolved in parsed.get("resolved_findings", []):
                if resolved.get("requires_human_review"):
                    requires_human = True

            return ConflictResolution(
                strategy=parsed.get("resolution_strategy", ConflictResolutionStrategy.EVIDENCE_WEIGHT.value),
                resolved=parsed.get("resolved_findings", []),
                unresolved=parsed.get("unresolved_conflicts", []),
                overall_confidence=parsed.get("overall_confidence", 0.5),
                requires_human_review=requires_human,
            )

        except Exception as exc:
            logger.exception("Conflict resolution failed: %s", exc)
            return ConflictResolution(
                strategy=ConflictResolutionStrategy.HUMAN_REVIEW.value,
                unresolved=[
                    {
                        "topic": c.topic,
                        "reason": "Automated resolution failed",
                        "agent_positions": c.positions,
                    }
                    for c in conflicts
                ],
                requires_human_review=True,
                overall_confidence=0.3,
            )

    def _format_findings(self, task_results: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for result in task_results:
            agent = result.get("agent_type", "unknown")
            lines.append(f"\n--- {agent} (confidence: {result.get('confidence', 'N/A')}) ---")
            lines.append(f"Summary: {result.get('summary', 'N/A')}")
            for f in result.get("findings", []):
                lines.append(f"  Finding: {json.dumps(f, default=str)}")
            for r in result.get("recommendations", []):
                lines.append(f"  Recommendation: {json.dumps(r, default=str)}")
        return "\n".join(lines)

    def _format_conflicts(self, conflicts: list[Conflict]) -> str:
        lines: list[str] = []
        for c in conflicts:
            lines.append(f"\nConflict on '{c.topic}' (severity: {c.severity}):")
            for agent, position in c.positions.items():
                lines.append(f"  {agent}: {position}")
        return "\n".join(lines)

    def _parse_resolution(self, output: str) -> dict[str, Any]:
        text = output.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"resolution_strategy": "human_review", "unresolved_conflicts": [], "overall_confidence": 0.3}

    def _compute_average_confidence(self, task_results: list[dict[str, Any]]) -> float:
        confidences = [r.get("confidence", 0.5) for r in task_results if r.get("confidence") is not None]
        return round(sum(confidences) / max(len(confidences), 1), 2)
