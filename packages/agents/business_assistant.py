from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from packages.agents.base import BaseAgent
from packages.tools.base import Tool


@dataclass
class BusinessAssistantAgent(BaseAgent):
    name: str = "business_assistant"
    description: str = "A general business assistant for reasoning and context-aware responses."
    system_prompt: str = "You are AgentMason, a business assistant that answers questions, reasons about business workflows, and uses tools when helpful."
    model: str = "gpt-4.1"
    temperature: float = 0.2
    tools: list[Tool] = field(default_factory=list)

    async def execute(self, input_text: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input": input_text,
            "status": "ready",
        }
