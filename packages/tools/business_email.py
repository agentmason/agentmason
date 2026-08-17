from __future__ import annotations

from typing import Any, Optional

from packages.integrations.base import OAuthTokenSet
from packages.integrations.services import GmailService
from packages.tools.base import Tool, ToolPermission, ToolError


class BusinessEmailToolBase(Tool):
    def __init__(self, organization_id: str, token_set: OAuthTokenSet) -> None:
        self.organization_id = organization_id
        self.token_set = token_set
        self.gmail = GmailService()


class SearchBusinessEmailTool(BusinessEmailToolBase):
    name = "search_business_email"
    description = "Search the organization's connected Gmail account."
    permission = ToolPermission.READ
    requires_approval = False

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        query = input_data.get("query")
        if not query:
            raise ToolError("Query parameter is required")
        emails, token_set = await self.gmail.search_emails(self.token_set, query=query, limit=int(input_data.get("limit", 20)))
        self.token_set = token_set
        return {"results": [email.__dict__ for email in emails], "provider": "gmail"}


class CreateEmailDraftTool(BusinessEmailToolBase):
    name = "create_email_draft"
    description = "Create a Gmail draft for the organization."
    permission = ToolPermission.WRITE
    requires_approval = False

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        to = input_data.get("to") or []
        subject = input_data.get("subject")
        body = input_data.get("body")
        if not subject or not body:
            raise ToolError("subject and body are required")
        draft, token_set = await self.gmail.create_draft(self.token_set, to=to, subject=subject, body=body)
        self.token_set = token_set
        return {"draft": draft, "provider": "gmail"}


class SendEmailTool(BusinessEmailToolBase):
    name = "send_email"
    description = "Send an email using the organization's connected Gmail account."
    permission = ToolPermission.DESTRUCTIVE
    requires_approval = True

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        to = input_data.get("to") or []
        subject = input_data.get("subject")
        body = input_data.get("body")
        if not subject or not body:
            raise ToolError("subject and body are required")
        sent, token_set = await self.gmail.send_email(self.token_set, to=to, subject=subject, body=body)
        self.token_set = token_set
        return {"message": sent, "provider": "gmail"}
