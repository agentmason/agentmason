from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4

from apps.api.app.core.config import settings
from packages.integrations.base import OAuthTokenSet
from packages.integrations.models import BusinessCalendarEvent, BusinessEmail, BusinessFile


class IntegrationAuthError(Exception):
    pass


class BaseGoogleService:
    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _token_expired(self, expires_at: Optional[datetime]) -> bool:
        return expires_at is not None and expires_at <= self._now()

    def _refresh_token(self, token_set: OAuthTokenSet) -> OAuthTokenSet:
        if not token_set.refresh_token:
            raise IntegrationAuthError("CONNECTION_REAUTH_REQUIRED")
        refreshed_access = hashlib.sha256(f"{token_set.refresh_token}:{self._now().isoformat()}".encode()).hexdigest()
        return OAuthTokenSet(
            access_token=refreshed_access,
            refresh_token=token_set.refresh_token,
            expires_at=self._now() + timedelta(hours=1),
            scopes=token_set.scopes,
        )


class GmailService(BaseGoogleService):
    async def search_emails(self, token_set: OAuthTokenSet, query: str, limit: int = 20) -> tuple[list[BusinessEmail], OAuthTokenSet]:
        token_set = self._refresh_token(token_set) if self._token_expired(token_set.expires_at) else token_set
        results = [
            BusinessEmail(
                id=f"msg-{uuid4().hex}",
                thread_id=f"thread-{uuid4().hex}",
                sender="customer@example.com",
                recipients=["user@example.com"],
                subject=f"Match for {query}",
                body=f"Simulated Gmail search result for query: {query}",
                timestamp=self._now(),
                labels=["INBOX"],
            )
        ]
        return results[:limit], token_set

    async def get_email(self, token_set: OAuthTokenSet, message_id: str) -> tuple[BusinessEmail, OAuthTokenSet]:
        token_set = self._refresh_token(token_set) if self._token_expired(token_set.expires_at) else token_set
        return (
            BusinessEmail(
                id=message_id,
                thread_id=f"thread-{message_id}",
                sender="customer@example.com",
                recipients=["user@example.com"],
                subject="Simulated email",
                body="This is a simulated Gmail message body.",
                timestamp=self._now(),
                labels=["INBOX"],
            ),
            token_set,
        )

    async def get_thread(self, token_set: OAuthTokenSet, thread_id: str) -> tuple[list[BusinessEmail], OAuthTokenSet]:
        email, token_set = await self.get_email(token_set, message_id=f"{thread_id}-1")
        return [email], token_set

    async def create_draft(self, token_set: OAuthTokenSet, to: list[str], subject: str, body: str) -> tuple[dict[str, Any], OAuthTokenSet]:
        token_set = self._refresh_token(token_set) if self._token_expired(token_set.expires_at) else token_set
        return (
            {"draft_id": f"draft-{uuid4().hex}", "to": to, "subject": subject, "body": body},
            token_set,
        )

    async def send_email(self, token_set: OAuthTokenSet, to: list[str], subject: str, body: str) -> tuple[dict[str, Any], OAuthTokenSet]:
        token_set = self._refresh_token(token_set) if self._token_expired(token_set.expires_at) else token_set
        return (
            {"message_id": f"sent-{uuid4().hex}", "to": to, "subject": subject, "body": body, "status": "sent"},
            token_set,
        )


class GoogleDriveService(BaseGoogleService):
    SUPPORTED_MIME_TYPES = {
        "application/pdf": ".pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "application/msword": ".docx",
        "text/plain": ".txt",
        "text/markdown": ".md",
        "text/x-markdown": ".md",
        "text/csv": ".csv",
        "application/csv": ".csv",
        "application/json": ".json",
    }

    async def search_files(self, token_set: OAuthTokenSet, query: str, limit: int = 20) -> tuple[list[BusinessFile], OAuthTokenSet]:
        token_set = self._refresh_token(token_set) if self._token_expired(token_set.expires_at) else token_set
        return (
            [
                BusinessFile(
                    id=f"file-{uuid4().hex}",
                    name=f"{query}.md",
                    mime_type="text/markdown",
                    modified_time=self._now(),
                    web_view_link="https://drive.google.com/file/d/example",
                    checksum=hashlib.sha256(query.encode()).hexdigest(),
                )
            ][:limit],
            token_set,
        )

    async def list_files(self, token_set: OAuthTokenSet, page_size: int = 100) -> tuple[list[BusinessFile], OAuthTokenSet]:
        token_set = self._refresh_token(token_set) if self._token_expired(token_set.expires_at) else token_set
        return await self.search_files(token_set, query="business", limit=page_size)

    async def get_file(self, token_set: OAuthTokenSet, file_id: str) -> tuple[BusinessFile, OAuthTokenSet]:
        token_set = self._refresh_token(token_set) if self._token_expired(token_set.expires_at) else token_set
        return (
            BusinessFile(
                id=file_id,
                name=f"{file_id}.txt",
                mime_type="text/plain",
                modified_time=self._now(),
                content="Simulated file contents.",
                web_view_link="https://drive.google.com/file/d/example",
                checksum=hashlib.sha256(file_id.encode()).hexdigest(),
            ),
            token_set,
        )

    async def download_file(self, token_set: OAuthTokenSet, file_id: str) -> tuple[bytes, BusinessFile, OAuthTokenSet]:
        file_obj, token_set = await self.get_file(token_set, file_id)
        return file_obj.content.encode("utf-8") if file_obj.content else b"", file_obj, token_set


class GoogleCalendarService(BaseGoogleService):
    async def list_events(self, token_set: OAuthTokenSet, time_min: datetime | None = None, time_max: datetime | None = None) -> tuple[list[BusinessCalendarEvent], OAuthTokenSet]:
        token_set = self._refresh_token(token_set) if self._token_expired(token_set.expires_at) else token_set
        now = self._now()
        return (
            [
                BusinessCalendarEvent(
                    id=f"event-{uuid4().hex}",
                    title="Simulated meeting",
                    description="Simulated Google Calendar event.",
                    start=now,
                    end=now + timedelta(hours=1),
                    attendees=["user@example.com"],
                    location="Conference Room A",
                )
            ],
            token_set,
        )

    async def get_event(self, token_set: OAuthTokenSet, event_id: str) -> tuple[BusinessCalendarEvent, OAuthTokenSet]:
        events, token_set = await self.list_events(token_set)
        return replace(events[0], id=event_id), token_set

    async def search_events(self, token_set: OAuthTokenSet, query: str) -> tuple[list[BusinessCalendarEvent], OAuthTokenSet]:
        return await self.list_events(token_set)

    async def create_event(self, token_set: OAuthTokenSet, event: BusinessCalendarEvent) -> tuple[BusinessCalendarEvent, OAuthTokenSet]:
        token_set = self._refresh_token(token_set) if self._token_expired(token_set.expires_at) else token_set
        return replace(event, id=f"event-{uuid4().hex}"), token_set

    async def update_event(self, token_set: OAuthTokenSet, event_id: str, event: BusinessCalendarEvent) -> tuple[BusinessCalendarEvent, OAuthTokenSet]:
        created, token_set = await self.create_event(token_set, event)
        return replace(created, id=event_id), token_set
