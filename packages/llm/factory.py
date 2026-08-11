from __future__ import annotations

from packages.llm.config import ProviderConfig
from packages.llm.exceptions import LLMProviderError
from packages.llm.local_provider import LocalLLMProvider
from packages.llm.openai_provider import OpenAIProvider
from packages.llm.anthropic_provider import AnthropicProvider
from packages.llm.providers import LLMProvider


class LLMProviderFactory:
    @staticmethod
    def create(provider: str, config: ProviderConfig) -> LLMProvider:
        provider_lower = provider.lower()
        if provider_lower == "openai":
            return OpenAIProvider(config)
        if provider_lower == "anthropic":
            return AnthropicProvider(config)
        if provider_lower == "local":
            return LocalLLMProvider(config)
        raise LLMProviderError(f"Unsupported LLM provider: {provider}")
