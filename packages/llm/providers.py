from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from packages.llm.config import ProviderConfig
from packages.llm.exceptions import LLMProviderError


class LLMProvider(ABC):
    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    @abstractmethod
    async def generate(self, messages: list[Dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def stream(self, messages: list[Dict[str, str]], **kwargs: Any) -> Any:
        raise NotImplementedError


class BaseLLMProvider(LLMProvider):
    async def generate(self, messages: list[Dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        raise LLMProviderError("Provider does not implement generate")

    async def stream(self, messages: list[Dict[str, str]], **kwargs: Any) -> Any:
        raise LLMProviderError("Provider does not implement stream")
