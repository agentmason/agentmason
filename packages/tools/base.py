from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ToolPermission(str):
    READ = "read"
    WRITE = "write"
    DESTRUCTIVE = "destructive"


class ToolError(Exception):
    pass


class Tool(ABC):
    name: str
    description: str
    permission: ToolPermission
    requires_approval: bool

    @abstractmethod
    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
