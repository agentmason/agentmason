"""Memory extraction - automatically identify useful memories from conversations."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from apps.api.app.models.memory import MemoryCategory, MemorySource

logger = logging.getLogger(__name__)


@dataclass
class ExtractedMemory:
    """A potential memory extracted from text."""
    category: MemoryCategory
    title: str
    content: str
    confidence: float
    tags: list[str]


# Patterns that indicate business rules or decisions
RULE_PATTERNS = [
    r"(?:all|every|any)\s+.+\s+(?:must|should|need to|require|requires)\s+",
    r"(?:above|over|more than|exceeds?)\s+\$?[\d,]+",
    r"(?:policy|rule|requirement|guideline|procedure)\s+(?:is|states?|requires?)",
    r"(?:always|never|must always|must never)\s+",
    r"(?:before|after|prior to)\s+(?:payment|approval|signing|sending)",
]

PREFERENCE_PATTERNS = [
    r"(?:prefer|we prefer|i prefer|use|we use|we always use)\s+",
    r"(?:our (?:preferred|default|standard))\s+",
    r"(?:instead of|rather than|not .+, use)\s+",
]

FACT_PATTERNS = [
    r"(?:our company|we are|the company|our business)\s+(?:is|has|does|provides|offers)",
    r"(?:we have|there are)\s+\d+\s+(?:employees?|locations?|departments?|products?)",
    r"(?:our (?:address|location|headquarters|office))\s+(?:is|are)\s+",
    r"(?:founded|established|started)\s+(?:in|on)\s+",
]

GOAL_PATTERNS = [
    r"(?:our goal|we want to|we aim to|we plan to|objective is to)\s+",
    r"(?:increase|decrease|improve|reduce|grow|expand|launch)\s+",
    r"(?:by (?:end of|next|Q[1-4]|january|february|march|april|may|june|july|august|september|october|november|december))",
]

DECISION_PATTERNS = [
    r"(?:we decided|decision is|we chose|we went with|approved)\s+",
    r"(?:going forward|from now on|effective immediately)\s+",
]

PROCESS_PATTERNS = [
    r"(?:step \d|first .+ then|the process is|workflow is)\s+",
    r"(?:when .+ happens?, .+ should)\s+",
    r"(?:escalat(?:e|ion)|handoff|handover|transfer to)\s+",
]


class MemoryExtractionService:
    """Extracts potential business memories from text."""

    def extract(self, text: str, source: MemorySource = MemorySource.CONVERSATION) -> list[ExtractedMemory]:
        """Extract potential memories from text. Returns candidates for review."""
        if not text or len(text.strip()) < 20:
            return []

        extracted: list[ExtractedMemory] = []
        sentences = self._split_sentences(text)

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 15:
                continue

            memory = self._classify_sentence(sentence)
            if memory:
                extracted.append(memory)

        # Deduplicate by title similarity
        return self._deduplicate(extracted)

    def _classify_sentence(self, sentence: str) -> Optional[ExtractedMemory]:
        """Classify a sentence into a memory category."""
        lower = sentence.lower()

        # Check business rules first (highest value)
        for pattern in RULE_PATTERNS:
            if re.search(pattern, lower):
                return ExtractedMemory(
                    category=MemoryCategory.BUSINESS_RULE,
                    title=self._make_title(sentence),
                    content=sentence,
                    confidence=0.8,
                    tags=["auto-extracted"],
                )

        for pattern in DECISION_PATTERNS:
            if re.search(pattern, lower):
                return ExtractedMemory(
                    category=MemoryCategory.DECISION,
                    title=self._make_title(sentence),
                    content=sentence,
                    confidence=0.75,
                    tags=["auto-extracted"],
                )

        for pattern in PROCESS_PATTERNS:
            if re.search(pattern, lower):
                return ExtractedMemory(
                    category=MemoryCategory.PROCESS,
                    title=self._make_title(sentence),
                    content=sentence,
                    confidence=0.7,
                    tags=["auto-extracted"],
                )

        for pattern in GOAL_PATTERNS:
            if re.search(pattern, lower):
                return ExtractedMemory(
                    category=MemoryCategory.GOAL,
                    title=self._make_title(sentence),
                    content=sentence,
                    confidence=0.7,
                    tags=["auto-extracted"],
                )

        for pattern in PREFERENCE_PATTERNS:
            if re.search(pattern, lower):
                return ExtractedMemory(
                    category=MemoryCategory.PREFERENCE,
                    title=self._make_title(sentence),
                    content=sentence,
                    confidence=0.65,
                    tags=["auto-extracted"],
                )

        for pattern in FACT_PATTERNS:
            if re.search(pattern, lower):
                return ExtractedMemory(
                    category=MemoryCategory.BUSINESS_FACT,
                    title=self._make_title(sentence),
                    content=sentence,
                    confidence=0.6,
                    tags=["auto-extracted"],
                )

        return None

    def _make_title(self, sentence: str) -> str:
        """Create a short title from a sentence."""
        # Take first 80 chars, cut at word boundary
        if len(sentence) <= 80:
            return sentence.rstrip(".")
        truncated = sentence[:80]
        last_space = truncated.rfind(" ")
        if last_space > 40:
            truncated = truncated[:last_space]
        return truncated.rstrip(".") + "..."

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        # Simple sentence splitting
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s for s in sentences if s.strip()]

    def _deduplicate(self, memories: list[ExtractedMemory]) -> list[ExtractedMemory]:
        """Remove near-duplicate extractions."""
        seen_titles: set[str] = set()
        unique: list[ExtractedMemory] = []
        for m in memories:
            key = m.title.lower()[:50]
            if key not in seen_titles:
                seen_titles.add(key)
                unique.append(m)
        return unique
