from __future__ import annotations

import asyncio
from typing import Any

import openai
from openai import OpenAIError

try:
    from openai import AuthenticationError, RateLimitError, APITimeoutError, BadRequestError
    InvalidRequestError = BadRequestError
    Timeout = APITimeoutError
except ImportError:
    try:
        from openai import AuthenticationError, InvalidRequestError, RateLimitError, Timeout
    except ImportError:
        AuthenticationError = OpenAIError
        InvalidRequestError = OpenAIError
        RateLimitError = OpenAIError
        Timeout = OpenAIError

from packages.llm.config import ProviderConfig
from packages.llm.exceptions import LLMAuthenticationError, LLMInvalidRequestError, LLMProviderError, LLMRateLimitError, LLMTimeoutError
from packages.llm.providers import LLMProvider


class OpenAIProvider(LLMProvider):
    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self.client = openai.OpenAI(api_key=config.api_key)

    async def generate(self, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        try:
            response = await self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=kwargs.get("temperature", self.config.temperature),
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
                timeout=kwargs.get("timeout", self.config.timeout),
                **kwargs,
            )
            choice = response.choices[0]
            return {
                "provider": "openai",
                "model": self.config.model,
                "output": choice.message["content"],
                "raw": response,
            }
        except AuthenticationError as exc:
            raise LLMAuthenticationError("OpenAI authentication failed") from exc
        except RateLimitError as exc:
            raise LLMRateLimitError("OpenAI rate limit exceeded") from exc
        except Timeout as exc:
            raise LLMTimeoutError("OpenAI request timed out") from exc
        except InvalidRequestError as exc:
            raise LLMInvalidRequestError("OpenAI invalid request") from exc
        except OpenAIError as exc:
            raise LLMProviderError("OpenAI provider error") from exc

    async def stream(self, messages: list[dict[str, str]], **kwargs: Any) -> Any:
        try:
            stream = await self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=kwargs.get("temperature", self.config.temperature),
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
                timeout=kwargs.get("timeout", self.config.timeout),
                stream=True,
                **kwargs,
            )
            async for event in stream:
                if event.type == "response.delta":
                    yield {"type": "token", "text": event.delta.get("content", "")}
            yield {"type": "done"}
        except AuthenticationError as exc:
            raise LLMAuthenticationError("OpenAI authentication failed") from exc
        except RateLimitError as exc:
            raise LLMRateLimitError("OpenAI rate limit exceeded") from exc
        except Timeout as exc:
            raise LLMTimeoutError("OpenAI request timed out") from exc
        except InvalidRequestError as exc:
            raise LLMInvalidRequestError("OpenAI invalid request") from exc
        except OpenAIError as exc:
            raise LLMProviderError("OpenAI provider error") from exc
