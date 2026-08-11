from __future__ import annotations

from packages.common.errors import AgentMasonError


class LLMProviderError(AgentMasonError):
    pass


class LLMAuthenticationError(LLMProviderError):
    pass


class LLMRateLimitError(LLMProviderError):
    pass


class LLMTimeoutError(LLMProviderError):
    pass


class LLMInvalidRequestError(LLMProviderError):
    pass
