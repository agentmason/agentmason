from __future__ import annotations

from collections import Counter
from typing import Any

from packages.tools.base import Tool, ToolPermission


class TextAnalysisTool(Tool):
    name = "text_analysis"
    description = "Analyze text and return word counts, character counts, and key phrases."
    permission = ToolPermission.READ
    requires_approval = False

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        text = input_data.get("text")
        if not isinstance(text, str):
            raise ValueError("text_analysis tool requires a text string")
        words = [word.strip(".,!?\"'()").lower() for word in text.split() if word.strip(".,!?\"'()")] 
        counts = Counter(words)
        top_phrases = [word for word, _ in counts.most_common(5)]
        return {
            "character_count": len(text),
            "word_count": len(words),
            "top_phrases": top_phrases,
        }
