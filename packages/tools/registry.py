from __future__ import annotations

from typing import Dict, Iterable

from packages.tools.base import Tool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"Tool not found: {name}")
        return tool

    def list(self) -> list[Tool]:
        return list(self._tools.values())

    def available_for_permission(self, permission: str) -> list[Tool]:
        return [tool for tool in self._tools.values() if tool.permission == permission]
