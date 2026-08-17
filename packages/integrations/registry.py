from __future__ import annotations

from typing import Dict, Iterable

from packages.integrations.base import Integration


class IntegrationRegistry:
    def __init__(self) -> None:
        self._integrations: Dict[str, Integration] = {}

    def register(self, integration: Integration) -> None:
        self._integrations[integration.provider] = integration

    def get(self, provider: str) -> Integration:
        integration = self._integrations.get(provider)
        if integration is None:
            raise KeyError(f"Integration not found: {provider}")
        return integration

    def list(self) -> list[Integration]:
        return list(self._integrations.values())
