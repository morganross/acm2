"""
Documents API Routes.

Endpoints for managing source documents.
Uses database repository - no mock data.
"""
import hashlib
import logging
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any

from app.infra.db.session import get_user_db
from app.infra.db.repositories import DocumentRepository
from app.infra.db.models.document import Document
from app.auth.middleware import get_current_user
from ..schemas.documents import (
    DocumentCreate,
    DocumentUpdate,
    DocumentSummary,
    DocumentDetail,
    DocumentList,
    DocumentContent,
    DocumentType,
    DocumentStatus,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])


# ============================================================================
# Helper Functions
# ============================================================================

def _get_document_type(file_type: str) -> DocumentType:
    """Convert database file_type to API DocumentType."""
    type_map = {
        "markdown": DocumentType.MARKDOWN,
        "html": DocumentType.HTML,
        "text": DocumentType.TEXT,
        "pdf": DocumentType.PDF,
    }
    return type_map.get(file_type.lower(), DocumentType.TEXT)


def _get_file_type(doc_type: DocumentType) -> str:
    """Convert API DocumentType to database file_type."""
    type_map = {
        DocumentType.MARKDOWN: "markdown",
        DocumentType.HTML: "html",
        DocumentType.TEXT: "text",
        DocumentType.PDF: "pdf",
    }
    return type_map.get(doc_type, "text")


def _to_summary(doc: Document) -> DocumentSummary:
    """Convert Document model to summary response."""
    return DocumentSummary(
        id=doc.id,
        name=doc.name,
        document_type=_get_document_type(doc.file_type),
        status=DocumentStatus.READY,  # Always ready in DB
        size_bytes=doc.size_bytes or 0,
        word_count=doc.word_count or 0,
        char_count=len(doc.content) if doc.content else 0,
        tags=doc.tags.split(",") if doc.tags else [],
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


def _to_detail(doc: Document, include_content: bool = False) -> DocumentDetail:
    """Convert Document model to detail response."""
    content = doc.content or ""
    return DocumentDetail(
        id=doc.id,
        name=doc.name,
        document_type=_get_document_type(doc.file_type),
        status=DocumentStatus.READY,
        content=content if include_content else None,
        content_preview=content[:500] if content else "",
        size_bytes=doc.size_bytes or 0,
        word_count=doc.word_count or 0,
        char_count=len(content),
        file_path=doc.path,
        original_url=None,
        tags=doc.tags.split(",") if doc.tags else [],
        metadata={},
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        run_count=0,
    )


# ============================================================================
# Endpoints
# ============================================================================

@router.post("", response_model=DocumentSummary)
async def create_document(
    data: DocumentCreate,
    user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_user_db),
) -> DocumentSummary:
    """
    Create a new document.
    
    Provide content directly, a file_path to read from, or a url to fetch.
    """
    repo = DocumentRepository(db, user_id=user['uuid'])
    
    # Get content from one of the sources
    content = ""
    if data.content:
        content = data.content
    elif data.file_path:
        try:
            with open(data.file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Could not read file: {e}")
    elif data.url:
        raise HTTPException(status_code=501, detail="URL fetching not yet implemented")
    else:
        raise HTTPException(
            status_code=400, 
            detail="Must provide content, file_path, or url"
        )
    
    # Calculate metadata
    content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
    size_bytes = len(content.encode('utf-8'))
    word_count = len(content.split())
    
    # Create document model
    doc = Document(
        id=str(uuid4()),
        name=data.name,
        path=data.file_path or f"inline/{data.name}",
        content=content,
        content_hash=content_hash,
        size_bytes=size_bytes,
        word_count=word_count,
        file_type=_get_file_type(data.document_type),
        tags=",".join(data.tags) if data.tags else None,
    )
    
    created_doc = await repo.create(doc)
    return _to_summary(created_doc)


@router.post("/upload", response_model=DocumentSummary)
async def upload_document(
    file: UploadFile = File(...),
    tags: str = Query("", description="Comma-separated tags"),
    user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_user_db),
) -> DocumentSummary:
    """
    Upload a document file.
    """
    repo = DocumentRepository(db, user_id=user['uuid'])
    
    # Read file content
    content = await file.read()
    try:
        content_str = content.decode('utf-8')
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded text")
    
    # Determine type from extension
    filename = file.filename or "uploaded.txt"
    if filename.endswith('.md'):
        file_type = "markdown"
    elif filename.endswith('.html'):
        file_type = "html"
    else:
        file_type = "text"
    
    # Calculate metadata
    content_hash = hashlib.sha256(content_str.encode('utf-8')).hexdigest()
    size_bytes = len(content_str.encode('utf-8'))
    word_count = len(content_str.split())
    
    # Create document
    doc = Document(
        id=str(uuid4()),
        name=filename,
        path=f"uploads/{filename}",
        content=content_str,
        content_hash=content_hash,
        size_bytes=size_bytes,
        word_count=word_count,
        file_type=file_type,
        tags=tags if tags else None,
    )
    
    created_doc = await repo.create(doc)
    return _to_summary(created_doc)


@router.get("", response_model=DocumentList)
async def list_documents(
    tags: Optional[str] = Query(None, description="Comma-separated tags to filter by"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_user_db),
) -> DocumentList:
    """
    List all documents with pagination.
    """
    repo = DocumentRepository(db, user_id=user['uuid'])
    offset = (page - 1) * page_size
    
    # Get documents from DB
    all_docs = await repo.get_active(limit=page_size, offset=offset)
    
    # For total count, we need a separate query
    # For now, estimate based on returned items
    items = [_to_summary(d) for d in all_docs]
    
    # If we got a full page, there might be more
    total = offset + len(items)
    if len(items) == page_size:
        total += 1  # Indicate there might be more
    
    pages = (total + page_size - 1) // page_size
    
    return DocumentList(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{doc_id}", response_model=DocumentDetail)
async def get_document(
    doc_id: str,
    include_content: bool = Query(False, description="Include full content"),
    user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_user_db),
) -> DocumentDetail:
    """
    Get detailed information about a document.
    """
    repo = DocumentRepository(db, user_id=user['uuid'])
    doc = await repo.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return _to_detail(doc, include_content)


@router.get("/{doc_id}/content", response_model=DocumentContent)
async def get_document_content(
    doc_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_user_db),
) -> DocumentContent:
    """
    Get the full content of a document.
    """
    repo = DocumentRepository(db, user_id=user['uuid'])
    doc = await repo.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return DocumentContent(
        id=doc.id,
        name=doc.name,
        content=doc.content or "",
        document_type=_get_document_type(doc.file_type),
    )


@router.patch("/{doc_id}", response_model=DocumentDetail)
async def update_document(
    doc_id: str,
    data: DocumentUpdate,
    user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_user_db),
) -> DocumentDetail:
    """
    Update document metadata.
    """
    repo = DocumentRepository(db, user_id=user['uuid'])
    doc = await repo.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Update fields
    if data.name is not None:
        doc.name = data.name
    if data.tags is not None:
        doc.tags = ",".join(data.tags)
    
    await db.commit()
    await db.refresh(doc)
    return _to_detail(doc)


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_user_db),
) -> dict:
    """
    Delete a document permanently.
    """
    repo = DocumentRepository(db, user_id=user['uuid'])
    deleted = await repo.delete(doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"status": "deleted", "doc_id": doc_id}
