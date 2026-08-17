from __future__ import annotations

import hashlib
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.core.config import settings
from apps.api.app.models.document import Document, DocumentSourceType, DocumentStatus
from apps.api.app.models.integration import Integration, IntegrationStatus
from packages.documents import ParseError, ParserRegistry
from packages.documents.ingestion import IngestionService
from packages.integrations.base import OAuthTokenSet
from packages.integrations.models import BusinessFile
from packages.integrations.services import GoogleDriveService
from packages.storage import LocalFileStorage
from packages.embeddings.provider import MockEmbeddingProvider, OpenAIEmbeddingProvider
from packages.vectorstore import PostgreSQLVectorStore, VectorStore


@dataclass
class DriveSyncResult:
    scanned: int
    ingested: int
    skipped: int


class GoogleDriveSyncService:
    def __init__(self) -> None:
        self.drive_service = GoogleDriveService()

    def _existing_checksum(self, db: Session, organization_id: str, drive_file_id: str) -> Optional[str]:
        docs = db.scalars(
            select(Document).where(
                Document.organization_id == organization_id,
                Document.source_type == DocumentSourceType.GOOGLE_DRIVE,
            )
        ).all()
        for doc in docs:
            metadata = doc.metadata_payload or {}
            if metadata.get("drive_file_id") == drive_file_id:
                return doc.checksum
        return None

    def _embedding_provider(self):
        if settings.openai_api_key:
            return OpenAIEmbeddingProvider(api_key=settings.openai_api_key, model=settings.openai_embedding_model)
        return MockEmbeddingProvider()

    def _vector_store(self) -> VectorStore:
        if settings.database_url.startswith("sqlite"):
            return _NoopVectorStore()
        return PostgreSQLVectorStore(settings.database_url)

    async def sync(self, db: Session, organization_id: str, token_set: OAuthTokenSet) -> DriveSyncResult:
        files, token_set = await self.drive_service.list_files(token_set)
        ingested = 0
        skipped = 0
        for file in files:
            checksum = file.checksum or hashlib.sha256(file.id.encode()).hexdigest()
            existing_checksum = self._existing_checksum(db, organization_id, file.id)
            if existing_checksum == checksum:
                skipped += 1
                continue
            await self._ingest_file(db, organization_id, file, checksum)
            ingested += 1
        return DriveSyncResult(scanned=len(files), ingested=ingested, skipped=skipped)

    async def _ingest_file(self, db: Session, organization_id: str, file: BusinessFile, checksum: str) -> None:
        storage = LocalFileStorage(settings.local_storage_path)
        file_bytes = (file.content or "").encode("utf-8")
        storage_location = await storage.save(file.id, file_bytes, organization_id)
        document = Document(
            organization_id=organization_id,
            name=file.name,
            file_name=file.name,
            mime_type=file.mime_type,
            file_size=len(file_bytes),
            storage_location=storage_location,
            checksum=checksum,
            status=DocumentStatus.UPLOADED,
            source_type=DocumentSourceType.GOOGLE_DRIVE,
            metadata_payload={
                "source_type": "google_drive",
                "source_id": file.id,
                "drive_file_id": file.id,
                "drive_url": file.web_view_link,
                "file_name": file.name,
                "modified_time": file.modified_time.isoformat(),
            },
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        ingestion = IngestionService(
            file_storage=storage,
            embedding_provider=self._embedding_provider(),
            vector_store=self._vector_store(),
        )
        await ingestion.ingest_document(db=db, document_id=document.id, organization_id=organization_id)


class _NoopVectorStore(VectorStore):
    async def upsert(self, chunk_id: str, embedding: list[float], metadata: dict, organization_id: str) -> None:
        return None

    async def search(self, organization_id: str, query_embedding: list[float], top_k: int = 5, filters: Optional[dict] = None):
        return []

    async def delete(self, chunk_id: str, organization_id: str) -> None:
        return None

    async def delete_by_document(self, document_id: str, organization_id: str) -> None:
        return None

    async def exists(self, chunk_id: str, organization_id: str) -> bool:
        return False
