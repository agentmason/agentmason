from __future__ import annotations

from typing import Any

from packages.integrations.base import OAuthTokenSet
from packages.integrations.services import GoogleDriveService
from packages.tools.base import Tool, ToolPermission, ToolError


class BusinessDriveToolBase(Tool):
    def __init__(self, organization_id: str, token_set: OAuthTokenSet) -> None:
        self.organization_id = organization_id
        self.token_set = token_set
        self.drive = GoogleDriveService()


class SearchBusinessFilesTool(BusinessDriveToolBase):
    name = "search_business_files"
    description = "Search the organization's connected Google Drive files."
    permission = ToolPermission.READ
    requires_approval = False

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        query = input_data.get("query")
        if not query:
            raise ToolError("Query parameter is required")
        files, token_set = await self.drive.search_files(self.token_set, query=query, limit=int(input_data.get("limit", 20)))
        self.token_set = token_set
        return {"results": [file.__dict__ for file in files], "provider": "google_drive"}


class ListBusinessFilesTool(BusinessDriveToolBase):
    name = "list_business_files"
    description = "List the organization's connected Google Drive files."
    permission = ToolPermission.READ
    requires_approval = False

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        files, token_set = await self.drive.list_files(self.token_set, page_size=int(input_data.get("limit", 20)))
        self.token_set = token_set
        return {"results": [file.__dict__ for file in files], "provider": "google_drive"}
