from __future__ import annotations

from typing import Any

import anthropic
from anthropic import AnthropicError
from packages.llm.config import ProviderConfig
from packages.llm.exceptions import LLMAuthenticationError, LLMInvalidRequestError, LLMProviderError, LLMRateLimitError, LLMTimeoutError
from packages.llm.providers import LLMProvider


class AnthropicProvider(LLMProvider):
    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self.client = anthropic.AsyncAnthropic(api_key=config.api_key)

    async def generate(self, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        prompt = self._build_prompt(messages)
        try:
            response = await self.client.completions.create(
                model=self.config.model,
                prompt=prompt,
                temperature=kwargs.get("temperature", self.config.temperature),
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
                timeout=kwargs.get("timeout", self.config.timeout),
            )
            return {
                "provider": "anthropic",
                "model": self.config.model,
                "output": response["completion"],
                "raw": response,
            }
        except anthropic.AuthenticationError as exc:
            raise LLMAuthenticationError("Anthropic authentication failed") from exc
        except anthropic.RateLimitError as exc:
            raise LLMRateLimitError("Anthropic rate limit exceeded") from exc
        except anthropic.Timeout as exc:
            raise LLMTimeoutError("Anthropic request timed out") from exc
        except anthropic.BadRequestError as exc:
            raise LLMInvalidRequestError("Anthropic invalid request") from exc
        except AnthropicError as exc:
            raise LLMProviderError("Anthropic provider error") from exc

    async def stream(self, messages: list[dict[str, str]], **kwargs: Any) -> Any:
        prompt = self._build_prompt(messages)
        try:
            async for event in self.client.completions.stream(
                model=self.config.model,
                prompt=prompt,
                temperature=kwargs.get("temperature", self.config.temperature),
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
                timeout=kwargs.get("timeout", self.config.timeout),
            ):
                yield {"type": "token", "text": event["completion"]}
            yield {"type": "done"}
        except anthropic.AuthenticationError as exc:
            raise LLMAuthenticationError("Anthropic authentication failed") from exc
        except anthropic.RateLimitError as exc:
            raise LLMRateLimitError("Anthropic rate limit exceeded") from exc
        except anthropic.Timeout as exc:
            raise LLMTimeoutError("Anthropic request timed out") from exc
        except anthropic.BadRequestError as exc:
            raise LLMInvalidRequestError("Anthropic invalid request") from exc
        except AnthropicError as exc:
            raise LLMProviderError("Anthropic provider error") from exc

    def _build_prompt(self, messages: list[dict[str, str]]) -> str:
        prompt_parts: list[str] = []
        for message in messages:
            role = message.get("role")
            content = message.get("content", "")
            prompt_parts.append(f"{role.upper()}: {content}")
        prompt_parts.append("AI:")
        return "\n\n".join(prompt_parts)
