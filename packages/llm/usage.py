from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from apps.api.app.models.llm_usage import LLMUsage


class LLMUsageTracker:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        execution_id: str,
        organization_id: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: Optional[int] = None,
    ) -> None:
        usage = LLMUsage(
            id=str(uuid4()),
            execution_id=execution_id,
            organization_id=organization_id,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens if total_tokens is not None else input_tokens + output_tokens,
            timestamp=datetime.now(timezone.utc),
        )
        self.db.add(usage)
        self.db.commit()
