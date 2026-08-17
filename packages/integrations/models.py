from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class BusinessEmail:
    id: str
    thread_id: str
    sender: str
    recipients: list[str]
    subject: str
    body: str
    timestamp: datetime
    labels: list[str] = field(default_factory=list)
    attachments: list[dict[str, Any]] = field(default_factory=list)
    source: str = "gmail"


@dataclass
class BusinessCalendarEvent:
    id: str
    title: str
    description: str
    start: datetime
    end: datetime
    attendees: list[str] = field(default_factory=list)
    location: Optional[str] = None
    source: str = "google_calendar"


@dataclass
class BusinessFile:
    id: str
    name: str
    mime_type: str
    modified_time: datetime
    web_view_link: Optional[str] = None
    checksum: Optional[str] = None
    content: Optional[str] = None
    source: str = "google_drive"
