from __future__ import annotations

from typing import Dict, Iterable

from packages.agents.base import BaseAgent


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: Dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.name] = agent

    def get(self, name: str) -> BaseAgent:
        agent = self._agents.get(name)
        if agent is None:
            raise KeyError(f"Agent not found: {name}")
        return agent

    def list(self) -> list[BaseAgent]:
        return list(self._agents.values())
