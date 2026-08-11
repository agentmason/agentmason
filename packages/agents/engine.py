from __future__ import annotations

import asyncio
from enum import Enum
from typing import Any
from uuid import uuid4

from packages.agents.base import BaseAgent
from packages.tools.registry import ToolRegistry
from packages.tools.base import ToolPermission, ToolError
from packages.llm.providers import LLMProvider


class ExecutionStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    WAITING_FOR_TOOL = "waiting_for_tool"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentExecutionError(Exception):
    pass


class AgentExecutionEngine:
    def __init__(self, tool_registry: ToolRegistry, llm_provider: LLMProvider, max_tool_calls: int = 10) -> None:
        self.tool_registry = tool_registry
        self.llm_provider = llm_provider
        self.max_tool_calls = max_tool_calls

    async def run(self, agent: BaseAgent, user_input: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        execution_id = str(uuid4())
        input_messages = [
            {"role": "system", "content": agent.system_prompt},
            {"role": "user", "content": user_input},
        ]
        trace: list[dict[str, Any]] = []
        tool_calls = 0
        last_response: dict[str, Any] | None = None

        try:
            trace.append({"event": "execution_started", "execution_id": execution_id})
            while tool_calls < self.max_tool_calls:
                trace.append({"event": "llm_request", "execution_id": execution_id})
                llm_response = await self.llm_provider.generate(input_messages, model=agent.model, temperature=agent.temperature)
                output_text = llm_response.get("output", "")
                last_response = {"provider": llm_response.get("provider"), "model": llm_response.get("model"), "output": output_text}
                trace.append({"event": "llm_response", "output": output_text})

                if "tool:" in output_text.lower():
                    tool_calls += 1
                    trace.append({"event": "tool_selected", "execution_id": execution_id})
                    tool_name, args = self._parse_tool_call(output_text)
                    tool = self.tool_registry.get(tool_name)
                    if tool.requires_approval and tool.permission == ToolPermission.DESTRUCTIVE:
                        trace.append({"event": "waiting_for_approval", "tool": tool_name})
                        return {
                            "execution_id": execution_id,
                            "status": ExecutionStatus.WAITING_FOR_APPROVAL,
                            "trace": trace,
                            "tool": tool_name,
                            "tool_input": args,
                        }
                    trace.append({"event": "tool_started", "tool": tool_name})
                    tool_result = await tool.execute(args)
                    trace.append({"event": "tool_completed", "tool": tool_name, "result": tool_result})
                    input_messages.append({"role": "tool", "content": str(tool_result)})
                    continue
                break

            trace.append({"event": "execution_completed", "execution_id": execution_id})
            return {
                "execution_id": execution_id,
                "status": ExecutionStatus.COMPLETED,
                "output": last_response,
                "trace": trace,
            }
        except ToolError as exc:
            trace.append({"event": "tool_failed", "error": str(exc)})
            raise AgentExecutionError(str(exc)) from exc
        except Exception as exc:
            trace.append({"event": "execution_failed", "error": str(exc)})
            raise AgentExecutionError("Agent execution failed") from exc

    def _parse_tool_call(self, text: str) -> tuple[str, dict[str, Any]]:
        lower = text.lower()
        if "calculator" in lower:
            return "calculator", {"expression": text}
        if "current_datetime" in lower or "date" in lower or "time" in lower:
            return "current_datetime", {}
        if "text_analysis" in lower or "analyze" in lower:
            return "text_analysis", {"text": text}
        raise AgentExecutionError("No valid tool identified in LLM response")
