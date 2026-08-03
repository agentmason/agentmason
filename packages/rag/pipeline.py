from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class RAGDocument:
    id: str
    content: str
    metadata: dict[str, Any] | None = None


class RAGPipeline:
    def __init__(self) -> None:
        self.documents: list[RAGDocument] = []

    def ingest(self, document: RAGDocument) -> None:
        self.documents.append(document)

    def search(self, query: str) -> list[RAGDocument]:
        return [doc for doc in self.documents if query.lower() in doc.content.lower()][:5]

    def retrieve(self, query: str) -> list[dict[str, Any]]:
        results = self.search(query)
        return [{"id": doc.id, "content": doc.content, "metadata": doc.metadata or {}} for doc in results]
