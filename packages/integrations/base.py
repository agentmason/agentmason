from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


@dataclass
class IntegrationMetadata:
    account_identifier: Optional[str] = None
    display_name: Optional[str] = None
    scopes: tuple[str, ...] = ()
    extra: dict[str, Any] | None = None


class Integration(ABC):
    name: str
    provider: str

    @abstractmethod
    async def connect(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def disconnect(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError

    @abstractmethod
    async def health_check(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_metadata(self, *args: Any, **kwargs: Any) -> IntegrationMetadata:
        raise NotImplementedError


@dataclass
class OAuthTokenSet:
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    scopes: tuple[str, ...]
