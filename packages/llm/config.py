from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ProviderConfig:
    provider: str
    model: str
    api_key: Optional[str] = None
    endpoint: Optional[str] = None
    temperature: float = 0.2
    max_tokens: int = 1024
    timeout: int = 60
