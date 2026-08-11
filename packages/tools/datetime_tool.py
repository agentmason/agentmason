from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from packages.tools.base import Tool, ToolPermission


class DateTimeTool(Tool):
    name = "current_datetime"
    description = "Return the current UTC date and time."
    permission = ToolPermission.READ
    requires_approval = False

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return {"timestamp": datetime.now(timezone.utc).isoformat()}
