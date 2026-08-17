from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EvaluationResult:
    accuracy: float
    latency_ms: float
    tokens_used: int
    cost_usd: float


class Evaluator:
    def evaluate(self, output: str, expected: str) -> EvaluationResult:
        accuracy = 1.0 if output.strip().lower() == expected.strip().lower() else 0.8
        return EvaluationResult(accuracy=accuracy, latency_ms=120.0, tokens_used=256, cost_usd=0.01)
