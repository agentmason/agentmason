from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from packages.llm.config import ProviderConfig
from packages.llm.providers import LLMProvider


class LocalLLMProvider(LLMProvider):
    async def generate(self, messages: list[Dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        content = self._build_response(messages)
        return {
            "provider": "local",
            "model": self.config.model,
            "output": content,
            "usage": {"input_tokens": 0, "output_tokens": len(content.split()), "total_tokens": len(content.split())},
        }

    async def stream(self, messages: list[Dict[str, str]], **kwargs: Any) -> Any:
        content = self._build_response(messages)
        for chunk in self._chunk_text(content):
            yield {"type": "token", "text": chunk}
            await asyncio.sleep(0)
        yield {"type": "done"}

    def _build_response(self, messages: list[Dict[str, str]]) -> str:
        last_user = next((msg["content"] for msg in reversed(messages) if msg["role"] == "user"), "")
        return f"[Local Assistant] I received your request and would normally use a model to respond. Original prompt: {last_user}"

    def _chunk_text(self, text: str) -> List[str]:
        return [part + " " for part in text.split(" ")]
