from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from packages.integrations.base import Integration, IntegrationMetadata


@dataclass
class OAuthConfig:
    authorization_url: str
    scopes: tuple[str, ...]


class GoogleIntegration(Integration):
    provider = "google"
    name = "Google"

    def __init__(self, scopes: tuple[str, ...]) -> None:
        self.scopes = scopes

    async def connect(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"provider": self.provider, "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth", "scopes": self.scopes}

    async def disconnect(self, *args: Any, **kwargs: Any) -> None:
        return None

    async def health_check(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"status": "CONNECTED", "checked_at": datetime.now(timezone.utc).isoformat()}

    async def get_metadata(self, *args: Any, **kwargs: Any) -> IntegrationMetadata:
        return IntegrationMetadata(scopes=self.scopes)


class GmailIntegration(GoogleIntegration):
    provider = "gmail"
    name = "Gmail"


class GoogleDriveIntegration(GoogleIntegration):
    provider = "google_drive"
    name = "Google Drive"


class GoogleCalendarIntegration(GoogleIntegration):
    provider = "google_calendar"
    name = "Google Calendar"
