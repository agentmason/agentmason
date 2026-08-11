from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class ToolDefinition(Protocol):
    name: str
    description: str

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]: ...


@dataclass
class BaseAgent:
    name: str
    description: str
    system_prompt: str
    model: str
    temperature: float = 0.2
    tools: list[ToolDefinition] = field(default_factory=list)
    memory: dict[str, Any] = field(default_factory=dict)

    async def execute(self, input_text: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "agent": self.name,
            "input": input_text,
            "status": "ready",
            "tools": [tool.name for tool in self.tools],
            "metadata": kwargs,
        }
