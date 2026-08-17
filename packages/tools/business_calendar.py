from __future__ import annotations

from typing import Any

from packages.integrations.base import OAuthTokenSet
from packages.integrations.models import BusinessCalendarEvent
from packages.integrations.services import GoogleCalendarService
from packages.tools.base import Tool, ToolPermission, ToolError


class BusinessCalendarToolBase(Tool):
    def __init__(self, organization_id: str, token_set: OAuthTokenSet) -> None:
        self.organization_id = organization_id
        self.token_set = token_set
        self.calendar = GoogleCalendarService()


class SearchCalendarTool(BusinessCalendarToolBase):
    name = "search_calendar"
    description = "Search the organization's connected Google Calendar events."
    permission = ToolPermission.READ
    requires_approval = False

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        query = input_data.get("query", "")
        events, token_set = await self.calendar.search_events(self.token_set, query=query)
        self.token_set = token_set
        return {"results": [event.__dict__ for event in events], "provider": "google_calendar"}


class GetCalendarEventTool(BusinessCalendarToolBase):
    name = "get_calendar_event"
    description = "Get a Google Calendar event."
    permission = ToolPermission.READ
    requires_approval = False

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        event_id = input_data.get("event_id")
        if not event_id:
            raise ToolError("event_id is required")
        event, token_set = await self.calendar.get_event(self.token_set, event_id=event_id)
        self.token_set = token_set
        return {"event": event.__dict__, "provider": "google_calendar"}


class CreateCalendarEventTool(BusinessCalendarToolBase):
    name = "create_calendar_event"
    description = "Create a Google Calendar event."
    permission = ToolPermission.WRITE
    requires_approval = True

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        event = BusinessCalendarEvent(
            id="",
            title=input_data.get("title", ""),
            description=input_data.get("description", ""),
            start=input_data["start"],
            end=input_data["end"],
            attendees=input_data.get("attendees", []),
            location=input_data.get("location"),
        )
        created, token_set = await self.calendar.create_event(self.token_set, event)
        self.token_set = token_set
        return {"event": created.__dict__, "provider": "google_calendar"}


class UpdateCalendarEventTool(BusinessCalendarToolBase):
    name = "update_calendar_event"
    description = "Update a Google Calendar event."
    permission = ToolPermission.WRITE
    requires_approval = True

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        event_id = input_data.get("event_id")
        if not event_id:
            raise ToolError("event_id is required")
        event = BusinessCalendarEvent(
            id=event_id,
            title=input_data.get("title", ""),
            description=input_data.get("description", ""),
            start=input_data["start"],
            end=input_data["end"],
            attendees=input_data.get("attendees", []),
            location=input_data.get("location"),
        )
        updated, token_set = await self.calendar.update_event(self.token_set, event_id=event_id, event=event)
        self.token_set = token_set
        return {"event": updated.__dict__, "provider": "google_calendar"}
