from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class ToolDefinition(Protocol):
    name: str
    description: str

    async def run(self, *args: Any, **kwargs: Any) -> Any: ...


@dataclass(slots=True)
class BaseAgent:
    name: str
    description: str
    tools: list[ToolDefinition] = field(default_factory=list)
    memory: dict[str, Any] = field(default_factory=dict)

    async def execute(self, input_text: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "agent": self.name,
            "input": input_text,
            "status": "completed",
            "tools": [tool.name for tool in self.tools],
            "metadata": kwargs,
        }


@dataclass(slots=True)
class AgentExecutionEngine:
    agents: dict[str, BaseAgent] = field(default_factory=dict)

    def register(self, agent: BaseAgent) -> None:
        self.agents[agent.name] = agent

    async def run(self, agent_name: str, input_text: str, **kwargs: Any) -> dict[str, Any]:
        agent = self.agents.get(agent_name)
        if not agent:
            raise KeyError(f"Unknown agent: {agent_name}")
        return await agent.execute(input_text, **kwargs)
