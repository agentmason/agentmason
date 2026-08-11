from __future__ import annotations

import ast
import operator
from typing import Any

from packages.tools.base import Tool, ToolError, ToolPermission


SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.Mod: operator.mod,
}


class CalculatorTool(Tool):
    name = "calculator"
    description = "Perform safe arithmetic calculations."
    permission = ToolPermission.READ
    requires_approval = False

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        expression = input_data.get("expression")
        if not expression or not isinstance(expression, str):
            raise ToolError("Calculator requires an expression string")
        result = self._evaluate(expression)
        return {"expression": expression, "result": result}

    def _evaluate(self, expression: str) -> float:
        node = ast.parse(expression, mode="eval")
        return self._evaluate_node(node.body)

    def _evaluate_node(self, node: ast.AST) -> float:
        if isinstance(node, ast.BinOp):
            left = self._evaluate_node(node.left)
            right = self._evaluate_node(node.right)
            op_type = type(node.op)
            if op_type in SAFE_OPERATORS:
                return SAFE_OPERATORS[op_type](left, right)
            raise ToolError("Unsupported operator")
        if isinstance(node, ast.UnaryOp):
            operand = self._evaluate_node(node.operand)
            op_type = type(node.op)
            if op_type in SAFE_OPERATORS:
                return SAFE_OPERATORS[op_type](operand)
            raise ToolError("Unsupported unary operator")
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        raise ToolError("Invalid expression")
