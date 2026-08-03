from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    USER = "user"
    ADMIN = "admin"
    AUDITOR = "auditor"


class AuthorizationService:
    def __init__(self) -> None:
        self._roles: dict[str, set[Role]] = {}

    def assign_role(self, subject_id: str, role: Role) -> None:
        self._roles.setdefault(subject_id, set()).add(role)

    def has_role(self, subject_id: str, role: Role) -> bool:
        return role in self._roles.get(subject_id, set())
