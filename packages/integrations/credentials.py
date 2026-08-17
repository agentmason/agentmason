from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Optional

from cryptography.fernet import Fernet


def _key_from_env() -> bytes:
    raw = os.getenv("OAUTH_ENCRYPTION_KEY", "")
    if raw:
        return raw.encode("utf-8")
    return base64.urlsafe_b64encode(sha256(b"agentmason-dev-key").digest())


@dataclass
class CredentialRecord:
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    scopes: tuple[str, ...]


class CredentialStore:
    def __init__(self, key: bytes | None = None) -> None:
        self._fernet = Fernet(key or _key_from_env())
        self._store: dict[str, str] = {}

    def encrypt_payload(self, payload: dict[str, object]) -> str:
        return self._fernet.encrypt(json.dumps(payload).encode("utf-8")).decode("utf-8")

    def decrypt_payload(self, token: str) -> dict[str, object]:
        return json.loads(self._fernet.decrypt(token.encode("utf-8")).decode("utf-8"))

    async def save(self, integration_id: str, record: CredentialRecord) -> None:
        payload = {
            "access_token": record.access_token,
            "refresh_token": record.refresh_token,
            "expires_at": record.expires_at.isoformat() if record.expires_at else None,
            "scopes": list(record.scopes),
        }
        self._store[integration_id] = self.encrypt_payload(payload)

    async def get(self, integration_id: str) -> Optional[CredentialRecord]:
        token = self._store.get(integration_id)
        if not token:
            return None
        payload = self.decrypt_payload(token)
        return CredentialRecord(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token"),
            expires_at=datetime.fromisoformat(payload["expires_at"]) if payload.get("expires_at") else None,
            scopes=tuple(payload.get("scopes") or ()),
        )

    async def delete(self, integration_id: str) -> None:
        self._store.pop(integration_id, None)
