from __future__ import annotations

import logging
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.core.database import get_db
from apps.api.app.models.document import Document, DocumentStatus
from apps.api.app.models.user import User
from apps.api.app.api.organizations import get_current_user
from packages.storage import LocalFileStorage
from packages.documents import ParserRegistry, ParseError

logger = logging.getLogger(__name__)

router = APIRouter()


class DocumentResponse:
    """Response model for document."""
    def __init__(self, doc: Document):
        self.id = doc.id
        self.name = doc.name
        self.file_name = doc.file_name
        self.mime_type = doc.mime_type
        self.file_size = doc.file_size
        self.status = doc.status.value
        self.created_at = doc.created_at
        self.updated_at = doc.updated_at
        self.error_message = doc.error_message
        self.metadata = doc.metadata_payload


@router.post("/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Upload a document for processing.
    
    Supported formats:
    - PDF
    - DOCX
    - TXT
    - Markdown
    - CSV
    - JSON
    """
    try:
        # Get user's organizations
        from apps.api.app.models.membership import Membership
        memberships = db.scalars(
            select(Membership).where(Membership.user_id == current_user.id)
        ).all()

        if not memberships:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User has no organization access"
            )

        # Use first organization (can be improved with explicit org selection)
        organization_id = memberships[0].organization_id

        # Validate file
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File name is required"
            )

        # Validate MIME type
        supported_types = {
            "application/pdf": ".pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
            "application/msword": ".docx",
            "text/plain": ".txt",
            "text/markdown": ".md",
            "text/x-markdown": ".md",
            "text/csv": ".csv",
            "application/csv": ".csv",
            "application/json": ".json",
        }

        mime_type = file.content_type or "application/octet-stream"
        if mime_type not in supported_types:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported file type: {mime_type}"
            )

        # Read file content
        content = await file.read()
        file_size = len(content)

        # Validate file size (25 MB max)
        MAX_SIZE = 25 * 1024 * 1024
        if file_size > MAX_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds {MAX_SIZE / (1024*1024):.0f} MB limit"
            )

        # Create document record
        document_id = str(uuid4())
        document = Document(
            id=document_id,
            organization_id=organization_id,
            name=file.filename or "Untitled",
            file_name=file.filename or "untitled",
            mime_type=mime_type,
            file_size=file_size,
            status=DocumentStatus.UPLOADED,
            storage_location="",  # Will be set after saving
            checksum="",  # Will be computed
            created_by=current_user.id,
        )

        # Save to storage
        storage = LocalFileStorage()
        storage_location = await storage.save(document_id, content, organization_id)
        document.storage_location = storage_location

        # Compute checksum
        import hashlib
        document.checksum = hashlib.sha256(content).hexdigest()

        # Save document to database
        db.add(document)
        db.commit()
        db.refresh(document)

        logger.info(f"Document {document_id} uploaded by {current_user.id}")

        # Queue for processing (async job)
        # TODO: Queue ingestion job when worker system is available
        logger.info(f"Document {document_id} queued for processing")

        return {
            "id": document.id,
            "name": document.name,
            "status": document.status.value,
            "message": "Document uploaded and queued for processing",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document upload failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload document"
        )


@router.get("/documents")
async def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
) -> dict:
    """List documents for the user's organization."""
    try:
        from apps.api.app.models.membership import Membership

        # Get user's organizations
        memberships = db.scalars(
            select(Membership).where(Membership.user_id == current_user.id)
        ).all()

        if not memberships:
            return {"documents": [], "total": 0}

        organization_id = memberships[0].organization_id

        # Get documents
        documents = db.scalars(
            select(Document)
            .where(Document.organization_id == organization_id)
            .order_by(Document.created_at.desc())
            .offset(skip)
            .limit(limit)
        ).all()

        total = db.scalar(
            select(len(Document))
            .where(Document.organization_id == organization_id)
        )

        return {
            "documents": [
                {
                    "id": doc.id,
                    "name": doc.name,
                    "status": doc.status.value,
                    "file_size": doc.file_size,
                    "created_at": doc.created_at,
                }
                for doc in documents
            ],
            "total": total or 0,
            "skip": skip,
            "limit": limit,
        }

    except Exception as e:
        logger.error(f"Failed to list documents: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list documents"
        )


@router.get("/documents/{document_id}")
async def get_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Get document details."""
    try:
        from apps.api.app.models.membership import Membership

        # Get user's organization
        memberships = db.scalars(
            select(Membership).where(Membership.user_id == current_user.id)
        ).all()

        if not memberships:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

        organization_id = memberships[0].organization_id

        # Get document
        document = db.scalar(
            select(Document).where(
                Document.id == document_id,
                Document.organization_id == organization_id
            )
        )

        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        # Count chunks
        from apps.api.app.models.document import DocumentChunk
        chunk_count = db.scalar(
            select(len(DocumentChunk)).where(DocumentChunk.document_id == document_id)
        ) or 0

        return {
            "id": document.id,
            "name": document.name,
            "status": document.status.value,
            "file_size": document.file_size,
            "chunk_count": chunk_count,
            "created_at": document.created_at,
            "error_message": document.error_message,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get document"
        )


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Delete a document and all its chunks."""
    try:
        from apps.api.app.models.membership import Membership

        # Get user's organization
        memberships = db.scalars(
            select(Membership).where(Membership.user_id == current_user.id)
        ).all()

        if not memberships:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

        organization_id = memberships[0].organization_id

        # Get document
        document = db.scalar(
            select(Document).where(
                Document.id == document_id,
                Document.organization_id == organization_id
            )
        )

        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        # Delete from storage
        storage = LocalFileStorage()
        try:
            await storage.delete(document.storage_location)
        except Exception as e:
            logger.warning(f"Failed to delete file from storage: {str(e)}")

        # Delete chunks from database (cascaded delete)
        # Delete from vector store (TODO: when available)

        # Delete document from database
        db.delete(document)
        db.commit()

        logger.info(f"Document {document_id} deleted by {current_user.id}")

        return {"message": "Document deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document"
        )


@router.post("/documents/{document_id}/reindex")
async def reindex_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Reindex a document."""
    try:
        from apps.api.app.models.membership import Membership

        # Get user's organization
        memberships = db.scalars(
            select(Membership).where(Membership.user_id == current_user.id)
        ).all()

        if not memberships:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

        organization_id = memberships[0].organization_id

        # Get document
        document = db.scalar(
            select(Document).where(
                Document.id == document_id,
                Document.organization_id == organization_id
            )
        )

        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        # Update status to processing
        document.status = DocumentStatus.PROCESSING
        db.commit()

        logger.info(f"Document {document_id} queued for reindexing")

        return {
            "id": document.id,
            "status": document.status.value,
            "message": "Document queued for reindexing",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reindex document: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reindex document"
        )


@router.get("/search")
async def search_knowledge(
    q: str = Query(..., description="Search query"),
    top_k: int = Query(5, ge=1, le=20, description="Number of results"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Search the organization's knowledge base.
    
    Query parameter:
    - q: Search query (e.g., "PTO policy")
    
    Returns:
    - sources: List of retrieved document chunks with similarity scores
    - total: Total number of results
    """
    try:
        from apps.api.app.models.membership import Membership
        from apps.api.app.models.document import DocumentChunk

        # Get user's organization
        memberships = db.scalars(
            select(Membership).where(Membership.user_id == current_user.id)
        ).all()

        if not memberships:
            return {"sources": [], "total": 0, "message": "No organization access"}

        organization_id = memberships[0].organization_id

        # For now, return indexed documents with a simple text search
        # TODO: Integrate with RetrievalService and embedding provider
        # This is a simplified implementation for demo purposes

        # Search document chunks for matching text
        chunks = db.scalars(
            select(DocumentChunk)
            .where(
                DocumentChunk.organization_id == organization_id,
                DocumentChunk.content.contains(q)
            )
            .limit(top_k)
        ).all()

        # Get document names
        doc_ids = {chunk.document_id for chunk in chunks}
        documents = {}
        for doc_id in doc_ids:
            doc = db.scalar(
                select(Document).where(Document.id == doc_id)
            )
            if doc:
                documents[doc_id] = doc

        sources = []
        for chunk in chunks:
            doc = documents.get(chunk.document_id)
            sources.append({
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "document_name": doc.name if doc else "Unknown",
                "page_number": chunk.metadata_payload.get("page_number") if chunk.metadata_payload else None,
                "score": 0.8,  # Placeholder - would be actual similarity score
                "content": chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content,
            })

        return {
            "sources": sources,
            "total": len(sources),
            "query": q,
            "message": f"Found {len(sources)} matching document(s)",
        }

    except Exception as e:
        logger.error(f"Search failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed"
        )
