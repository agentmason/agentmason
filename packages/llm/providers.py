from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ProviderConfig:
    provider: str
    model: str
    api_key: str | None = None
    endpoint: str | None = None


class LLMProvider:
    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    async def complete(self, prompt: str, **kwargs: Any) -> str:
        return f"[{self.config.provider}:{self.config.model}] {prompt}"
