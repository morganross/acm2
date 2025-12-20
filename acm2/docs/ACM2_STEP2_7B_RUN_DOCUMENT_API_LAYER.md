# ACM 2.0 Step 2.7B: Run/Document Lifecycle - API Layer

> **Part 2 of 2** - See [Step 2.7A](ACM2_STEP2_7A_RUN_DOCUMENT_DATA_LAYER.md) for domain models, database schema, repositories, and services.

---

## 8. API Endpoints

### 8.1 Run Endpoints

```python
# app/api/routes/runs.py
"""
Run API endpoints.
"""
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.domain.models.enums import RunStatus
from app.domain.models.run import Run
from app.domain.exceptions import (
    RunNotFoundError,
    InvalidStatusTransitionError,
    RunAlreadyTerminalError,
)
from app.services.dependencies import RunServiceDep
from app.api.schemas.runs import (
    RunCreateRequest,
    RunUpdateRequest,
    RunResponse,
    RunListResponse,
)

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def create_run(
    request: RunCreateRequest,
    run_service: RunServiceDep,
) -> RunResponse:
    """
    Create a new run.
    
    Creates a run with the specified configuration. Documents can be
    attached at creation time or added later via POST /runs/{run_id}/documents.
    """
    run = await run_service.create_run(
        project_id=request.project_id,
        requested_by=request.requested_by or "api",
        title=request.title,
        config=request.config.model_dump() if request.config else None,
        tags=request.tags,
        priority=request.priority,
    )
    return RunResponse.from_domain(run)


@router.get("", response_model=RunListResponse)
async def list_runs(
    run_service: RunServiceDep,
    project_id: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    tags: Annotated[list[str] | None, Query()] = None,
    created_after: Annotated[datetime | None, Query()] = None,
    created_before: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    order_by: Annotated[str, Query()] = "created_at_desc",
) -> RunListResponse:
    """
    List runs with optional filtering.
    
    Filters:
    - project_id: Filter by project
    - status: Filter by status (pending, running, completed, failed, cancelled)
    - tags: Filter by tags (any match)
    - created_after/before: Date range filter
    
    Pagination:
    - limit: Max results (default 50, max 100)
    - offset: Skip N results
    - order_by: created_at_desc (default), created_at_asc, priority_asc, updated_at_desc
    """
    status_enum = RunStatus(status) if status else None
    
    runs, total = await run_service.list_runs(
        project_id=project_id,
        status=status_enum,
        tags=tags,
        created_after=created_after,
        created_before=created_before,
        limit=limit,
        offset=offset,
        order_by=order_by,
    )
    
    return RunListResponse(
        runs=[RunResponse.from_domain(r) for r in runs],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: str,
    run_service: RunServiceDep,
) -> RunResponse:
    """Get a run by ID."""
    try:
        run = await run_service.get_run(run_id)
        return RunResponse.from_domain(run)
    except RunNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.patch("/{run_id}", response_model=RunResponse)
async def update_run(
    run_id: str,
    request: RunUpdateRequest,
    run_service: RunServiceDep,
) -> RunResponse:
    """
    Update run metadata.
    
    Can update: title, priority, tags, summary.
    Status updates use POST /runs/{run_id}/cancel or internal transitions.
    """
    try:
        run = await run_service.update_run(
            run_id,
            title=request.title,
            priority=request.priority,
            tags=request.tags,
            summary=request.summary,
        )
        return RunResponse.from_domain(run)
    except RunNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
    except RunAlreadyTerminalError as e:
        raise HTTPException(status_code=409, detail={"code": e.code, "message": e.message})


@router.post("/{run_id}/cancel", response_model=RunResponse)
async def cancel_run(
    run_id: str,
    run_service: RunServiceDep,
) -> RunResponse:
    """
    Cancel a run.
    
    Sets status to 'cancelled'. Cannot cancel already-completed runs.
    """
    try:
        run = await run_service.cancel_run(run_id)
        return RunResponse.from_domain(run)
    except RunNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
    except InvalidStatusTransitionError as e:
        raise HTTPException(status_code=409, detail={"code": e.code, "message": e.message})


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_run(
    run_id: str,
    run_service: RunServiceDep,
) -> None:
    """
    Delete a run (soft delete).
    
    Equivalent to cancelling. Data is preserved but run is marked cancelled.
    """
    try:
        await run_service.cancel_run(run_id)
    except RunNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
    except InvalidStatusTransitionError:
        pass  # Already terminal, that's fine for DELETE
```

### 8.2 Document Endpoints

```python
# app/api/routes/documents.py
"""
Document API endpoints.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.domain.exceptions import (
    DocumentNotFoundError,
    DocumentAlreadyAttachedError,
    DocumentNotAttachedError,
    RunNotFoundError,
)
from app.services.dependencies import DocumentServiceDep
from app.api.schemas.documents import (
    DocumentAttachRequest,
    DocumentBatchAttachRequest,
    DocumentResponse,
    DocumentListResponse,
    DocumentWithStatusResponse,
)

router = APIRouter(tags=["documents"])


# ─────────────────────────────────────────────────────────────────
# DOCUMENT ATTACHMENT (under /runs/{run_id}/documents)
# ─────────────────────────────────────────────────────────────────

runs_documents_router = APIRouter(prefix="/runs/{run_id}/documents", tags=["documents"])


@runs_documents_router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def attach_document(
    run_id: str,
    request: DocumentAttachRequest,
    document_service: DocumentServiceDep,
) -> DocumentResponse:
    """
    Attach a document to a run.
    
    Document can be specified as:
    - GitHub path: {"repository": "owner/repo", "path": "docs/file.md", "ref": "main"}
    - Inline content: {"content": "...", "filename": "file.md"}
    - Existing document: {"document_id": "01HGWJ..."}
    """
    try:
        if request.document_id:
            # Attach existing document
            doc = await document_service.attach_to_run(run_id, request.document_id)
        elif request.repository and request.path:
            # Register and attach GitHub document
            doc = await document_service.attach_github_document_to_run(
                run_id,
                repository=request.repository,
                path=request.path,
                ref=request.ref or "main",
                display_name=request.display_name,
            )
        elif request.content and request.filename:
            # Register and attach inline document
            doc = await document_service.register_inline_document(
                content=request.content,
                filename=request.filename,
                mime_type=request.mime_type or "text/markdown",
                display_name=request.display_name,
            )
            doc = await document_service.attach_to_run(run_id, doc.document_id)
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "INVALID_DOCUMENT_SPEC",
                    "message": "Must provide document_id, repository+path, or content+filename",
                },
            )
        
        return DocumentResponse.from_domain(doc)
    
    except RunNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
    except DocumentNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
    except DocumentAlreadyAttachedError as e:
        raise HTTPException(status_code=409, detail={"code": e.code, "message": e.message})


@runs_documents_router.post("/batch", response_model=list[DocumentResponse], status_code=status.HTTP_201_CREATED)
async def attach_documents_batch(
    run_id: str,
    request: DocumentBatchAttachRequest,
    document_service: DocumentServiceDep,
) -> list[DocumentResponse]:
    """
    Attach multiple documents to a run in one request.
    
    Maximum 100 documents per batch.
    """
    if len(request.documents) > 100:
        raise HTTPException(
            status_code=400,
            detail={"code": "BATCH_TOO_LARGE", "message": "Maximum 100 documents per batch"},
        )
    
    try:
        docs = await document_service.attach_documents_batch(
            run_id,
            [d.model_dump(exclude_none=True) for d in request.documents],
        )
        return [DocumentResponse.from_domain(d) for d in docs]
    except RunNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@runs_documents_router.get("", response_model=DocumentListResponse)
async def list_documents_for_run(
    run_id: str,
    document_service: DocumentServiceDep,
    status: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DocumentListResponse:
    """
    List all documents attached to a run.
    
    Optionally filter by processing status (pending, processing, completed, skipped, failed).
    """
    docs, total = await document_service.list_documents_for_run(
        run_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return DocumentListResponse(
        documents=[DocumentResponse.from_domain(d) for d in docs],
        total=total,
        limit=limit,
        offset=offset,
    )


@runs_documents_router.get("/status", response_model=list[DocumentWithStatusResponse])
async def get_documents_with_status(
    run_id: str,
    document_service: DocumentServiceDep,
) -> list[DocumentWithStatusResponse]:
    """
    Get all documents with their per-run processing status.
    
    Returns document metadata plus status and error message if failed.
    """
    results = await document_service.get_documents_with_status(run_id)
    return [
        DocumentWithStatusResponse(
            document=DocumentResponse.from_domain(doc),
            status=status,
            error_message=error,
        )
        for doc, status, error in results
    ]


# ─────────────────────────────────────────────────────────────────
# DOCUMENT CRUD (under /documents)
# ─────────────────────────────────────────────────────────────────

@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    document_service: DocumentServiceDep,
) -> DocumentResponse:
    """Get a document by ID."""
    try:
        doc = await document_service.get_document(document_id)
        return DocumentResponse.from_domain(doc)
    except DocumentNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document_from_run(
    document_id: str,
    run_id: Annotated[str, Query(description="Run to detach document from")],
    document_service: DocumentServiceDep,
) -> None:
    """
    Remove a document from a run.
    
    Does not delete the document itself, only the attachment.
    """
    try:
        await document_service.detach_from_run(run_id, document_id)
    except DocumentNotAttachedError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
```

### 8.3 Request/Response Schemas

```python
# app/api/schemas/runs.py
"""
Pydantic schemas for Run API requests and responses.
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.domain.models.enums import RunStatus
from app.domain.models.run import Run
from app.domain.models.value_objects import RunConfig


class RunConfigRequest(BaseModel):
    """Run configuration for create/update requests."""
    
    iterations_default: int = Field(default=1, ge=1, le=10)
    one_file_only: bool = False
    generators: list[dict[str, Any]] = Field(default_factory=list)
    concurrency: dict[str, int] = Field(default_factory=lambda: {"fpf": 2, "gptr": 2})
    eval: dict[str, Any] = Field(default_factory=dict)
    combine: dict[str, Any] = Field(default_factory=dict)
    docs_repo: str | None = None
    outputs_repo: str | None = None
    logs_repo: str | None = None
    instructions_file: str | None = None
    guidelines_file: str | None = None


class RunCreateRequest(BaseModel):
    """Request body for POST /runs."""
    
    project_id: str = Field(..., min_length=1, max_length=64)
    title: str | None = Field(default=None, max_length=160)
    config: RunConfigRequest | None = None
    tags: list[str] = Field(default_factory=list)
    priority: int = Field(default=5, ge=1, le=9)
    requested_by: str | None = Field(default=None, max_length=64)


class RunUpdateRequest(BaseModel):
    """Request body for PATCH /runs/{run_id}."""
    
    title: str | None = Field(default=None, max_length=160)
    priority: int | None = Field(default=None, ge=1, le=9)
    tags: list[str] | None = None
    summary: str | None = Field(default=None, max_length=2000)


class RunResponse(BaseModel):
    """Response body for run endpoints."""
    
    run_id: str
    project_id: str
    title: str | None
    status: str
    priority: int
    config: dict[str, Any]
    tags: list[str]
    requested_by: str
    summary: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    
    @classmethod
    def from_domain(cls, run: Run) -> "RunResponse":
        return cls(
            run_id=run.run_id,
            project_id=run.project_id,
            title=run.title,
            status=run.status.value,
            priority=run.priority,
            config=run.config.model_dump(),
            tags=run.tags,
            requested_by=run.requested_by,
            summary=run.summary,
            created_at=run.created_at,
            updated_at=run.updated_at,
            started_at=run.started_at,
            completed_at=run.completed_at,
        )


class RunListResponse(BaseModel):
    """Response body for GET /runs."""
    
    runs: list[RunResponse]
    total: int
    limit: int
    offset: int
```

```python
# app/api/schemas/documents.py
"""
Pydantic schemas for Document API requests and responses.
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.domain.models.document import Document, GitHubSource, InlineSource


class DocumentAttachRequest(BaseModel):
    """
    Request body for POST /runs/{run_id}/documents.
    
    One of three forms:
    1. Existing document: document_id
    2. GitHub document: repository + path + ref
    3. Inline document: content + filename
    """
    
    # Existing document
    document_id: str | None = None
    
    # GitHub document
    repository: str | None = Field(default=None, pattern=r"^[\w\-\.]+/[\w\-\.]+$")
    path: str | None = Field(default=None, max_length=512)
    ref: str | None = Field(default="main", max_length=128)
    
    # Inline document
    content: str | None = Field(default=None, max_length=1_000_000)
    filename: str | None = Field(default=None, max_length=255)
    mime_type: str | None = Field(default="text/markdown", max_length=100)
    
    # Common
    display_name: str | None = Field(default=None, max_length=160)


class DocumentBatchAttachRequest(BaseModel):
    """Request body for POST /runs/{run_id}/documents/batch."""
    
    documents: list[DocumentAttachRequest] = Field(..., min_length=1, max_length=100)


class DocumentSourceResponse(BaseModel):
    """Document source (GitHub or inline)."""
    
    type: str  # "github" or "inline"
    repository: str | None = None
    ref: str | None = None
    path: str | None = None
    filename: str | None = None
    mime_type: str | None = None


class DocumentMetadataResponse(BaseModel):
    """Document metadata."""
    
    mime_type: str
    size_bytes: int | None = None
    line_count: int | None = None
    word_count: int | None = None


class DocumentResponse(BaseModel):
    """Response body for document endpoints."""
    
    document_id: str
    display_name: str | None
    source: DocumentSourceResponse
    content_hash: str | None
    metadata: DocumentMetadataResponse
    created_at: datetime
    updated_at: datetime
    
    @classmethod
    def from_domain(cls, doc: Document) -> "DocumentResponse":
        if isinstance(doc.source, GitHubSource):
            source = DocumentSourceResponse(
                type="github",
                repository=doc.source.repository,
                ref=doc.source.ref,
                path=doc.source.path,
            )
        else:
            source = DocumentSourceResponse(
                type="inline",
                filename=doc.source.filename,
                mime_type=doc.source.mime_type,
            )
        
        return cls(
            document_id=doc.document_id,
            display_name=doc.display_name,
            source=source,
            content_hash=doc.content_hash,
            metadata=DocumentMetadataResponse(
                mime_type=doc.metadata.mime_type,
                size_bytes=doc.metadata.size_bytes,
                line_count=doc.metadata.line_count,
                word_count=doc.metadata.word_count,
            ),
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )


class DocumentListResponse(BaseModel):
    """Response body for GET /runs/{run_id}/documents."""
    
    documents: list[DocumentResponse]
    total: int
    limit: int
    offset: int


class DocumentWithStatusResponse(BaseModel):
    """Document with per-run processing status."""
    
    document: DocumentResponse
    status: str  # pending, processing, completed, skipped, failed
    error_message: str | None = None
```

### 8.4 Router Registration

```python
# app/api/router.py
"""
API router registration.
"""
from fastapi import APIRouter

from app.api.routes import health, runs, documents

api_router = APIRouter(prefix="/api/v1")

# Health check
api_router.include_router(health.router)

# Core resources
api_router.include_router(runs.router)
api_router.include_router(documents.router)
api_router.include_router(documents.runs_documents_router)
```

## 9. Document Attachment

### 9.1 Attaching by GitHub Path

Documents can be attached to a run by specifying a GitHub repository and path:

```http
POST /api/v1/runs/01HGWJ.../documents
Content-Type: application/json

{
  "repository": "myorg/docs",
  "path": "executive-orders/eo-2024-001.md",
  "ref": "main",
  "display_name": "EO 2024-001"
}
```

**Behavior:**
1. System checks if document with same repo/path/ref already exists
2. If exists: reuses existing document record
3. If not: creates new document record
4. Attaches document to run via `run_documents` junction table
5. Returns document metadata (content not fetched until Generation Phase)

**Content Hash:**
- Not computed at attachment time (requires reading file content)
- Computed lazily during Generation Phase when StorageProvider reads the file
- Used for skip logic once populated

### 9.2 Attaching by Local Path

For local development and testing, documents can reference local files:

```http
POST /api/v1/runs/01HGWJ.../documents
Content-Type: application/json

{
  "content": "# Executive Order 2024-001\n\nThis executive order...",
  "filename": "eo-2024-001.md",
  "mime_type": "text/markdown",
  "display_name": "EO 2024-001"
}
```

**Behavior:**
1. System computes SHA-256 hash of content
2. Checks if document with same hash already exists (deduplication)
3. If exists: reuses existing document record
4. If not: creates new document with inline content stored in database
5. Attaches document to run

**Note:** Inline content is stored in the `documents.inline_content` column. For large files, prefer GitHub storage.

### 9.3 Batch Attachment

Attach multiple documents in a single request:

```http
POST /api/v1/runs/01HGWJ.../documents/batch
Content-Type: application/json

{
  "documents": [
    {"repository": "myorg/docs", "path": "eo-2024-001.md"},
    {"repository": "myorg/docs", "path": "eo-2024-002.md"},
    {"document_id": "01HGXYZ..."},
    {"content": "# Quick test\n\nTest content.", "filename": "test.md"}
  ]
}
```

**Behavior:**
- Processes documents in order, assigns `sort_order` based on position
- Skips duplicates (documents already attached to run)
- Returns list of successfully attached documents
- Maximum 100 documents per batch

## 10. Status Transitions

### 10.1 Run Status State Machine

```
                         ┌─────────────────────────────────┐
                         │                                 │
                         ▼                                 │
    ┌─────────┐     ┌─────────┐     ┌───────────┐         │
    │ PENDING │────▶│ QUEUED  │────▶│  RUNNING  │─────────┤
    └────┬────┘     └────┬────┘     └─────┬─────┘         │
         │               │                 │               │
         │               │                 ├──────────────▶│ COMPLETED
         │               │                 │               │
         │               │                 ├──────────────▶│ FAILED
         │               │                 │               │
         └───────────────┴─────────────────┴──────────────▶│ CANCELLED
                                                           │
                                                           ▼
                                              (Terminal - no transitions out)
```

**Allowed Transitions:**

| From | To | Trigger |
|------|----|---------|
| `pending` | `queued` | Run submitted to execution queue |
| `pending` | `cancelled` | User cancels before execution |
| `queued` | `running` | Execution engine picks up run |
| `queued` | `cancelled` | User cancels while queued |
| `running` | `completed` | All documents processed successfully |
| `running` | `failed` | Unrecoverable error during execution |
| `running` | `cancelled` | User cancels during execution |

**Terminal States:** `completed`, `failed`, `cancelled` — no further transitions allowed.

### 10.2 Document Status State Machine

Per-run document status (stored in `run_documents` junction table):

```
    ┌─────────┐     ┌────────────┐     ┌───────────┐
    │ PENDING │────▶│ PROCESSING │────▶│ COMPLETED │
    └────┬────┘     └─────┬──────┘     └───────────┘
         │                │
         │                └───────────▶ FAILED
         │
         └───────────────────────────▶ SKIPPED
```

**Allowed Transitions:**

| From | To | Trigger |
|------|----|---------|
| `pending` | `processing` | Document picked up for generation |
| `pending` | `skipped` | Skip logic determines no work needed |
| `processing` | `completed` | Generation finished successfully |
| `processing` | `failed` | Generation error |

## 11. Skip Logic Integration

Skip logic is **not implemented in Step 2.7** but the data structures support it:

**How skip logic will work (Step 2.8+):**

1. Document registered with `content_hash = null`
2. During Generation Phase, StorageProvider reads file content
3. Content hash computed: `sha256:abc123...`
4. Skip check: query artifacts table for matching `document_id` + `content_hash`
5. If match found with same generator config: status → `skipped`
6. If no match: proceed with generation

**Fields supporting skip logic:**

| Table | Column | Purpose |
|-------|--------|---------|
| `documents` | `content_hash` | SHA-256 of file content |
| `run_documents` | `status` | `skipped` if skip logic triggers |
| `artifacts` | `document_id` | Link artifact to source document |
| `artifacts` | `content_hash` | Hash at generation time |
| `artifacts` | `generator` | fpf, gptr, dr |
| `artifacts` | `metadata.model` | Model used for generation |

## 12. Validation Rules

### 12.1 Run Validation

| Field | Rule | Error Code |
|-------|------|------------|
| `project_id` | Required, 1-64 chars | `VALIDATION_ERROR` |
| `title` | Optional, max 160 chars | `VALIDATION_ERROR` |
| `priority` | 1-9 (default 5) | `VALIDATION_ERROR` |
| `tags` | Max 10 tags, each max 32 chars | `VALIDATION_ERROR` |
| `config` | Must match RunConfig schema | `VALIDATION_ERROR` |
| `status` transition | Must follow state machine | `INVALID_STATUS_TRANSITION` |
| Update terminal run | Only `summary` allowed | `RUN_ALREADY_TERMINAL` |

### 12.2 Document Validation

| Field | Rule | Error Code |
|-------|------|------------|
| `repository` | Format: `owner/repo` | `VALIDATION_ERROR` |
| `path` | Required for GitHub, max 512 chars | `VALIDATION_ERROR` |
| `ref` | Max 128 chars (default "main") | `VALIDATION_ERROR` |
| `content` | Max 1MB for inline | `VALIDATION_ERROR` |
| `filename` | Required for inline, max 255 chars | `VALIDATION_ERROR` |
| Duplicate in run | Document already attached | `DOCUMENT_ALREADY_ATTACHED` |

### 12.3 Batch Validation

| Rule | Error Code |
|------|------------|
| Max 100 documents per batch | `BATCH_TOO_LARGE` |
| At least 1 document | `VALIDATION_ERROR` |

## 13. Error Handling

### 13.1 Error Response Format

All errors return JSON with consistent structure:

```json
{
  "detail": {
    "code": "RUN_NOT_FOUND",
    "message": "Run not found: 01HGWJ..."
  }
}
```

### 13.2 HTTP Status Codes

| Status | Meaning | Example |
|--------|---------|---------|
| `400` | Validation error | Invalid request body |
| `404` | Not found | Run or document doesn't exist |
| `409` | Conflict | Duplicate document, invalid transition |
| `422` | Unprocessable entity | Pydantic validation failed |
| `500` | Internal error | Unexpected server error |

### 13.3 Domain Exception Mapping

```python
# app/api/exception_handlers.py
"""
Map domain exceptions to HTTP responses.
"""
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

from app.domain.exceptions import (
    DomainError,
    RunNotFoundError,
    DocumentNotFoundError,
    InvalidStatusTransitionError,
    RunAlreadyTerminalError,
    DocumentAlreadyAttachedError,
    DocumentNotAttachedError,
)

EXCEPTION_STATUS_CODES = {
    RunNotFoundError: 404,
    DocumentNotFoundError: 404,
    DocumentNotAttachedError: 404,
    InvalidStatusTransitionError: 409,
    RunAlreadyTerminalError: 409,
    DocumentAlreadyAttachedError: 409,
}


async def domain_exception_handler(request: Request, exc: DomainError) -> JSONResponse:
    """Handle domain exceptions with appropriate HTTP status."""
    status_code = EXCEPTION_STATUS_CODES.get(type(exc), 400)
    return JSONResponse(
        status_code=status_code,
        content={"detail": {"code": exc.code, "message": exc.message}},
    )
```

## 14. Tests

### 14.1 Unit Tests

```python
# tests/unit/services/test_run_service.py
"""
Unit tests for RunService.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from app.services.run_service import RunService
from app.domain.models.enums import RunStatus
from app.domain.exceptions import RunNotFoundError, InvalidStatusTransitionError


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def run_service(mock_session):
    return RunService(mock_session)


class TestCreateRun:
    async def test_creates_run_with_defaults(self, run_service, mock_session):
        """Test creating a run with minimal required fields."""
        run = await run_service.create_run(
            project_id="test-project",
            requested_by="test-user",
        )
        
        assert run.project_id == "test-project"
        assert run.status == RunStatus.PENDING
        assert run.priority == 5
        assert run.tags == []
        mock_session.commit.assert_called_once()
    
    async def test_creates_run_with_config(self, run_service, mock_session):
        """Test creating a run with custom configuration."""
        config = {
            "generators": [{"type": "fpf", "provider": "openai", "model": "gpt-4o"}],
            "iterations_default": 2,
        }
        run = await run_service.create_run(
            project_id="test-project",
            requested_by="test-user",
            config=config,
        )
        
        assert run.config.iterations_default == 2
        assert len(run.config.generators) == 1


class TestStatusTransitions:
    async def test_valid_transition_pending_to_cancelled(self, run_service):
        """Test valid transition from pending to cancelled."""
        # Setup mock to return pending run
        ...
    
    async def test_invalid_transition_completed_to_running(self, run_service):
        """Test that completed runs cannot transition to running."""
        with pytest.raises(InvalidStatusTransitionError):
            ...
```

### 14.2 Integration Tests

```python
# tests/integration/api/test_runs_api.py
"""
Integration tests for Run API endpoints.
"""
import pytest
from httpx import AsyncClient

from app.main import create_app


@pytest.fixture
async def client():
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


class TestCreateRun:
    async def test_create_run_success(self, client):
        """Test POST /api/v1/runs creates a run."""
        response = await client.post(
            "/api/v1/runs",
            json={
                "project_id": "test-project",
                "title": "Test Run",
                "tags": ["test", "integration"],
            },
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["project_id"] == "test-project"
        assert data["status"] == "pending"
        assert "run_id" in data
    
    async def test_create_run_validation_error(self, client):
        """Test POST /api/v1/runs with invalid data."""
        response = await client.post(
            "/api/v1/runs",
            json={"title": "Missing project_id"},
        )
        
        assert response.status_code == 422


class TestListRuns:
    async def test_list_runs_empty(self, client):
        """Test GET /api/v1/runs with no runs."""
        response = await client.get("/api/v1/runs")
        
        assert response.status_code == 200
        data = response.json()
        assert data["runs"] == []
        assert data["total"] == 0
    
    async def test_list_runs_with_filter(self, client):
        """Test GET /api/v1/runs with status filter."""
        # Create a run first
        await client.post("/api/v1/runs", json={"project_id": "test"})
        
        response = await client.get("/api/v1/runs?status=pending")
        
        assert response.status_code == 200
        data = response.json()
        assert all(r["status"] == "pending" for r in data["runs"])
```

### 14.3 Test Fixtures

```python
# tests/conftest.py
"""
Shared test fixtures.
"""
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.infra.db.base import Base
from app.config import Settings


@pytest.fixture
def test_settings():
    """Test configuration using in-memory SQLite."""
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        dev_mode=True,
    )


@pytest.fixture
async def db_session(test_settings):
    """Create test database session."""
    engine = create_async_engine(test_settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    
    await engine.dispose()


@pytest.fixture
def sample_run_data():
    """Sample run creation data."""
    return {
        "project_id": "test-project",
        "title": "Test Run",
        "config": {
            "generators": [
                {"type": "fpf", "provider": "openai", "model": "gpt-4o", "iterations": 1},
            ],
        },
        "tags": ["test"],
        "priority": 5,
    }


@pytest.fixture
def sample_document_data():
    """Sample document attachment data."""
    return {
        "repository": "testorg/docs",
        "path": "test-doc.md",
        "ref": "main",
        "display_name": "Test Document",
    }
```

## 15. Success Criteria

### 15.1 Functional Criteria

| Criteria | Verification |
|----------|--------------|
| Create run | `POST /api/v1/runs` returns 201 with valid run_id |
| List runs | `GET /api/v1/runs` returns paginated list |
| Filter runs | Status, project, tags filters work correctly |
| Get run | `GET /api/v1/runs/{id}` returns run details |
| Update run | `PATCH /api/v1/runs/{id}` updates allowed fields |
| Cancel run | `POST /api/v1/runs/{id}/cancel` sets status to cancelled |
| Delete run | `DELETE /api/v1/runs/{id}` soft-deletes |
| Attach document | `POST /api/v1/runs/{id}/documents` attaches document |
| Batch attach | `POST /api/v1/runs/{id}/documents/batch` attaches multiple |
| List documents | `GET /api/v1/runs/{id}/documents` returns documents |
| Get document | `GET /api/v1/documents/{id}` returns document details |
| Detach document | `DELETE /api/v1/documents/{id}?run_id=...` removes from run |

### 15.2 Quality Criteria

| Criteria | Target |
|----------|--------|
| Unit test coverage | ≥80% for services |
| Integration test coverage | All endpoints tested |
| Response time | <100ms for single resource operations |
| Documentation | OpenAPI spec auto-generated and accurate |
| Error messages | All errors include code and human-readable message |

### 15.3 Verification Commands

```powershell
# Start server
acm2 serve --dev

# Health check
curl http://localhost:8000/api/v1/health

# Create run
curl -X POST http://localhost:8000/api/v1/runs -H "Content-Type: application/json" -d '{"project_id": "test"}'

# List runs
curl http://localhost:8000/api/v1/runs

# Run tests
pytest tests/ -v --cov=app --cov-report=term-missing
```

## 16. File Structure

After implementing Step 2.7, the project structure should be:

```
acm2/
├── app/
│   ├── __init__.py
│   ├── main.py                         # create_app() factory
│   ├── config.py                       # Settings, DatabaseSettings
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── router.py                   # api_router registration
│   │   ├── exception_handlers.py       # Domain → HTTP error mapping
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── health.py               # GET /health
│   │   │   ├── runs.py                 # Run endpoints
│   │   │   └── documents.py            # Document endpoints
│   │   └── schemas/
│   │       ├── __init__.py
│   │       ├── runs.py                 # Run request/response schemas
│   │       └── documents.py            # Document request/response schemas
│   │
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── exceptions.py               # Domain exceptions
│   │   └── models/
│   │       ├── __init__.py
│   │       ├── enums.py                # RunStatus, DocumentStatus, etc.
│   │       ├── run.py                  # Run domain model
│   │       ├── document.py             # Document domain model
│   │       └── value_objects.py        # RunConfig, GeneratorConfig, etc.
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── dependencies.py             # FastAPI dependency injection
│   │   ├── run_service.py              # Run business logic
│   │   └── document_service.py         # Document business logic
│   │
│   ├── infra/
│   │   ├── __init__.py
│   │   ├── logging.py                  # Structured logging setup
│   │   └── db/
│   │       ├── __init__.py
│   │       ├── base.py                 # SQLAlchemy Base, mixins
│   │       ├── session.py              # DatabaseManager, get_session
│   │       ├── models/
│   │       │   ├── __init__.py         # Model registry
│   │       │   ├── run.py              # RunModel
│   │       │   ├── document.py         # DocumentModel
│   │       │   └── run_document.py     # RunDocument junction
│   │       └── repositories/
│   │           ├── __init__.py         # Repository registry
│   │           ├── base.py             # BaseRepository
│   │           ├── run_repository.py
│   │           ├── document_repository.py
│   │           └── run_document_repository.py
│   │
│   └── middleware/
│       ├── __init__.py
│       ├── request_id.py               # Request ID injection
│       └── error_handler.py            # Global error handling
│
├── migrations/
│   ├── env.py                          # Alembic configuration
│   └── versions/
│       └── 001_initial_run_document.py # Initial migration
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                     # Shared fixtures
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── services/
│   │   │   ├── test_run_service.py
│   │   │   └── test_document_service.py
│   │   └── repositories/
│   │       └── test_run_repository.py
│   └── integration/
│       ├── __init__.py
│       └── api/
│           ├── test_runs_api.py
│           └── test_documents_api.py
│
├── pyproject.toml
├── Makefile                            # dev, test, lint commands
└── README.md
```

## 17. Next Steps

After completing Step 2.7, proceed to:

### Step 2.8: StorageProvider Abstraction

- Define `StorageProvider` interface for reading/writing files
- Implement `GitHubStorageProvider` for GitHub repos
- Implement `LocalStorageProvider` for local filesystem (Windows paths)
- Integrate with DocumentService for content hash computation
- Add artifact storage/retrieval

### Step 3.9: FPF and GPT-R Integration

- Create FPF adapter (subprocess management, retry logic)
- Create GPT-R adapter (Deep Research mode support)
- Add generation endpoints
- Record artifacts in database

### Step 3.10: Evaluation Integration

- Single-doc and pairwise evaluation endpoints
- Evaluation database (compatible with ACM 1.0 schema)
- Elo rating calculation
- Result aggregation and ranking
