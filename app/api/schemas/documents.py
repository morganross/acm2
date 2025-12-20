"""
API Schemas for Documents.
"""
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    """Type of document."""
    MARKDOWN = "markdown"
    TEXT = "text"
    PDF = "pdf"
    HTML = "html"


class DocumentStatus(str, Enum):
    """Processing status of a document."""
    PENDING = "pending"
    READY = "ready"
    ERROR = "error"


# ============================================================================
# Request Models
# ============================================================================

class DocumentCreate(BaseModel):
    """Request to create/upload a document."""
    name: str = Field(..., min_length=1, max_length=500)
    content: Optional[str] = Field(None, description="Raw content (for text/markdown)")
    file_path: Optional[str] = Field(None, description="Path to file on disk")
    url: Optional[str] = Field(None, description="URL to fetch document from")
    document_type: DocumentType = Field(DocumentType.MARKDOWN)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class DocumentUpdate(BaseModel):
    """Request to update document metadata."""
    name: Optional[str] = Field(None, min_length=1, max_length=500)
    tags: Optional[list[str]] = None
    metadata: Optional[dict[str, str]] = None


# ============================================================================
# Response Models
# ============================================================================

class DocumentSummary(BaseModel):
    """Summary view of a document (for lists)."""
    id: str
    name: str
    document_type: DocumentType
    status: DocumentStatus
    size_bytes: int
    word_count: int
    char_count: int
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class DocumentDetail(BaseModel):
    """Detailed view of a document."""
    id: str
    name: str
    document_type: DocumentType
    status: DocumentStatus
    
    # Content info
    content: Optional[str] = Field(None, description="Full content if requested")
    content_preview: str = Field("", description="First 500 chars")
    size_bytes: int
    word_count: int
    char_count: int
    
    # Source
    file_path: Optional[str] = None
    original_url: Optional[str] = None
    
    # Organization
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    
    # Timestamps
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Usage stats
    run_count: int = Field(0, description="Number of runs using this document")
    
    class Config:
        from_attributes = True


class DocumentList(BaseModel):
    """Paginated list of documents."""
    items: list[DocumentSummary]
    total: int
    page: int
    page_size: int
    pages: int


class DocumentContent(BaseModel):
    """Just the document content (for download)."""
    id: str
    name: str
    content: str
    document_type: DocumentType
