"""Conditional evaluation for workflow step conditions."""

from __future__ import annotations

import operator
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Safe operators for condition evaluation — no exec/eval
_OPERATORS: dict[str, Any] = {
    "eq": operator.eq,
    "ne": operator.ne,
    "gt": operator.gt,
    "gte": operator.ge,
    "lt": operator.lt,
    "lte": operator.le,
    "in": lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
    "contains": lambda a, b: b in a if isinstance(a, (str, list)) else False,
    "starts_with": lambda a, b: a.startswith(b) if isinstance(a, str) else False,
    "ends_with": lambda a, b: a.endswith(b) if isinstance(a, str) else False,
    "is_empty": lambda a, _: not a,
    "is_not_empty": lambda a, _: bool(a),
    "is_true": lambda a, _: a is True,
    "is_false": lambda a, _: a is False,
}


class ConditionEvaluator:
    """Evaluates workflow step conditions safely without exec/eval.

    Condition format:
    {
        "field": "invoice_amount",
        "operator": "gt",
        "value": 10000,
        "source": "step_output"    # step_output | input | context | memory
    }

    Compound conditions:
    {
        "all": [<condition>, <condition>]    # AND
    }
    {
        "any": [<condition>, <condition>]    # OR
    }
    """

    def evaluate(self, condition: dict[str, Any], context: dict[str, Any]) -> bool:
        """Evaluate a condition or compound condition against the execution context."""
        if not condition:
            return True

        # Compound: AND
        if "all" in condition:
            return all(self.evaluate(c, context) for c in condition["all"])

        # Compound: OR
        if "any" in condition:
            return any(self.evaluate(c, context) for c in condition["any"])

        # Compound: NOT
        if "not" in condition:
            return not self.evaluate(condition["not"], context)

        # Simple condition
        return self._evaluate_simple(condition, context)

    def _evaluate_simple(self, condition: dict[str, Any], context: dict[str, Any]) -> bool:
        """Evaluate a single condition."""
        field = condition.get("field", "")
        op_name = condition.get("operator", "eq")
        expected = condition.get("value")
        source = condition.get("source", "context")

        # Resolve the actual value from context
        actual = self._resolve_value(field, source, context)

        op_fn = _OPERATORS.get(op_name)
        if op_fn is None:
            logger.warning("Unknown operator '%s' in condition, defaulting to False", op_name)
            return False

        try:
            return bool(op_fn(actual, expected))
        except (TypeError, ValueError) as e:
            logger.warning("Condition evaluation error for field '%s': %s", field, e)
            return False

    def _resolve_value(self, field: str, source: str, context: dict[str, Any]) -> Any:
        """Resolve a dotted field path from the appropriate context source."""
        source_data = context.get(source, context)
        if isinstance(source_data, dict):
            return _get_nested(source_data, field)
        return None


def _get_nested(data: dict[str, Any], path: str) -> Any:
    """Resolve a dot-separated path in a nested dict."""
    keys = path.split(".")
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        elif isinstance(current, list):
            try:
                current = current[int(key)]
            except (IndexError, ValueError):
                return None
        else:
            return None
    return current
