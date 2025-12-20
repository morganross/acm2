# ACM 2.0 Step 2.7A: Run/Document Lifecycle - Data Layer

> **Part 1 of 2** - See [Step 2.7B](ACM2_STEP2_7B_RUN_DOCUMENT_API_LAYER.md) for API endpoints, validation, error handling, and tests.


there is no steps 2.2 thru 2.6.  You can think of 2.7 as the next file after 2.1.


## 1. Purpose

Step 2.7 implements the **core Run and Document lifecycle APIs**—the foundation upon which all ACM 2.0 operations depend. This step delivers working CRUD endpoints for Runs and Documents, with full database persistence, status transitions, and document attachment (by GitHub path or local path). 

**This step does NOT integrate**:
- FPF or GPT-R generators (Step 3.9)
- Evaluation or scoring (Step 3.10)
- Artifact creation beyond placeholders (Step 2.8)
- StorageProvider file operations beyond metadata registration (Step 2.8)

**This step DOES deliver**:
- `POST /runs` – Create a new run with configuration and optional document list
- `GET /runs`, `GET /runs/{run_id}` – List and retrieve runs
- `PATCH /runs/{run_id}` – Update run status (cancel, change priority)
- `DELETE /runs/{run_id}` – Soft-delete (mark cancelled)
- `POST /runs/{run_id}/documents` – Attach documents to a run
- `GET /runs/{run_id}/documents` – List documents in a run
- `GET /documents/{document_id}` – Retrieve document details
- `DELETE /documents/{document_id}` – Remove document from run

**Why this matters**: Every ACM operation starts with a Run. A Run contains Documents. Documents are processed during the Generation Phase to produce Artifacts. Without a working Run/Document lifecycle, nothing else functions. This step establishes the data flow that Step 3+ builds upon.

**Dependencies**:
- Step 2.1 backend project setup (FastAPI, config, logging, health check)
- Step 1.5 database schema (tables: `run`, `document`, `run_document`, `task`)
- Step 1.1 data model specifications (Run, Document JSON structures)

## 2. Scope

### 2.1 In Scope

| Category | Deliverable | Details |
|----------|-------------|---------|
| **Run CRUD** | Create run | `POST /api/v1/runs` with project_id, title, config, tags |
| | Get run | `GET /api/v1/runs/{run_id}` returns full run object |
| | List runs | `GET /api/v1/runs` with filtering by status, project, date range, tags |
| | Update run | `PATCH /api/v1/runs/{run_id}` for status changes, priority, summary |
| | Delete run | `DELETE /api/v1/runs/{run_id}` soft-delete (status → cancelled) |
| **Document CRUD** | Attach document | `POST /api/v1/runs/{run_id}/documents` by GitHub path or inline content |
| | Get document | `GET /api/v1/documents/{document_id}` returns document metadata |
| | List documents | `GET /api/v1/runs/{run_id}/documents` returns all docs in a run |
| | Remove document | `DELETE /api/v1/documents/{document_id}` removes from run |
| **Batch operations** | Attach multiple | `POST /api/v1/runs/{run_id}/documents/batch` attach up to 100 docs |
| **Database** | Run table | Full CRUD with SQLAlchemy async, proper transactions |
| | Document table | Full CRUD with foreign key to run |
| | run_document junction | Many-to-many for run↔document relationship |
| **Validation** | Input validation | Pydantic models for all requests with strict typing |
| | Business rules | Status transitions, tag limits, priority range |
| **Repository layer** | RunRepository | Async CRUD operations, query methods |
| | DocumentRepository | Async CRUD operations, query methods |
| **Service layer** | RunService | Business logic, orchestrates repository calls |
| | DocumentService | Business logic for document lifecycle |

### 2.2 Out of Scope

| Category | What's Excluded | Why / When |
|----------|-----------------|------------|
| **File content** | Reading actual file bytes from GitHub | Step 2.8 (StorageProvider) |
| **Artifact creation** | Creating artifacts from documents | Step 2.8+ |
| **FPF integration** | Executing FPF for documents | Step 3.9 |
| **GPT-R integration** | Executing GPT-R for documents | Step 3.9 |
| **Evaluation** | Running eval on artifacts | Step 3.10 |
| **Skip logic** | Determining if doc should be skipped | Step 2.8 (needs content hash) |
| **Cost tracking** | Recording API costs | Step 3.9 (with generators) |
| **Task queue** | Background job processing | Step 2.9 |
| **Webhooks** | Event notifications | Step 4.x |

### 2.3 Boundary Conditions

| Condition | Behavior |
|-----------|----------|
| Run with 0 documents | Allowed—documents can be attached later |
| Document attached to multiple runs | Allowed—same document can be in many runs |
| Document with no GitHub path | Allowed if inline content provided; system stores to default repo |
| Run status already `completed` | Reject updates except `summary` field |
| Delete run with artifacts | Cascade soft-delete to artifacts (mark cancelled, preserve data) |
| Duplicate document in same run | Reject with 409 Conflict |

## 3. Prerequisites

### 3.1 Completed Steps

Before implementing Step 2.7, ensure the following are complete:

| Step | Deliverable | Verification |
|------|-------------|--------------|
| **Step 2.1** | FastAPI project skeleton | `make dev` starts server, `/api/v1/health` returns 200 |
| **Step 2.1** | Database connection | Health check shows `database: ok` |
| **Step 2.1** | Structured logging | Logs output in JSON format with request_id |
| **Step 2.1** | Configuration system | `Settings` class loads from environment |
| **Step 1.5** | Database schema design | SQL DDL for `run`, `document`, `run_document` tables defined |
| **Step 1.1** | Data model specs | Run and Document JSON structures finalized |

### 3.2 Required Files from Step 2.1

These files must exist and be functional:

```
acm2/
├── app/
│   ├── __init__.py
│   ├── main.py                    # create_app() factory
│   ├── config.py                  # Settings, DatabaseSettings
│   ├── api/
│   │   ├── __init__.py
│   │   ├── router.py              # api_router
│   │   └── health.py              # /health endpoint
│   ├── infra/
│   │   ├── __init__.py
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   └── session.py         # DatabaseManager
│   │   └── logging.py             # setup_logging(), get_logger()
│   └── middleware/
│       ├── __init__.py
│       ├── request_id.py
│       └── error_handler.py
└── tests/
    ├── __init__.py
    └── conftest.py                # test_settings, client fixtures
```

### 3.3 Database Ready State

The database must be initialized with Alembic migrations. For Step 2.7, we will create migrations for:

1. `run` table (if not already created in Step 2.1)
2. `document` table
3. `run_document` junction table
4. Required indexes

### 3.4 Dependencies Added

Ensure `pyproject.toml` includes (from Step 2.1):

```toml
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "sqlalchemy[asyncio]>=2.0.25",
    "asyncpg>=0.29.0",
    "aiosqlite>=0.19.0",
    "alembic>=1.13.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "python-ulid>=2.2.0",
    "structlog>=24.1.0",
    "orjson>=3.9.0",
    "httpx>=0.26.0",
]
```

## 4. Domain Models

### 4.1 Run Model

```python
# app/domain/models/run.py
"""
Run domain model.

A Run represents a complete ACM operation that processes documents through
the Generation Phase, Eval Phase, Combine Phase, and Post-Combine Eval Phase.
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.domain.models.enums import RunStatus
from app.domain.models.value_objects import RunConfig


class Run(BaseModel):
    """
    Core Run domain object.
    
    Attributes:
        run_id: Unique identifier (ULID format, e.g., "01HGWJ8K9M2N3P4Q5R6S7T8U9V")
        project_id: Project this run belongs to (e.g., "firstpub-platform")
        title: Human-readable title for the run
        status: Current lifecycle status
        priority: Execution priority (1=highest, 9=lowest)
        config: Run configuration (generators, concurrency, eval settings)
        tags: Searchable tags (max 10, each max 32 chars)
        requested_by: User or system that created the run
        summary: Optional completion summary
        created_at: When the run was created
        updated_at: Last modification time
        started_at: When execution began (null if pending)
        completed_at: When execution finished (null if not complete)
    """
    
    run_id: str = Field(..., min_length=26, max_length=32, pattern=r"^[0-9A-Z]{26}$")
    project_id: str = Field(..., min_length=1, max_length=64)
    title: str | None = Field(default=None, max_length=160)
    status: RunStatus = Field(default=RunStatus.PENDING)
    priority: int = Field(default=5, ge=1, le=9)
    config: RunConfig = Field(default_factory=RunConfig)
    tags: list[str] = Field(default_factory=list)
    requested_by: str = Field(..., min_length=1, max_length=64)
    summary: str | None = Field(default=None, max_length=2000)
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    
    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        if len(v) > 10:
            raise ValueError("Maximum 10 tags allowed")
        for tag in v:
            if len(tag) > 32:
                raise ValueError(f"Tag '{tag[:20]}...' exceeds 32 character limit")
            if not tag.strip():
                raise ValueError("Empty tags not allowed")
        return [tag.strip().lower() for tag in v]
    
    model_config = {"from_attributes": True}
```

### 4.2 Document Model

```python
# app/domain/models/document.py
"""
Document domain model.

A Document represents an input file to be processed during a Run.
Documents are referenced by GitHub path or stored inline.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class GitHubSource(BaseModel):
    """GitHub file reference."""
    
    type: Literal["github"] = "github"
    repository: str = Field(..., pattern=r"^[\w\-\.]+/[\w\-\.]+$")  # owner/repo
    ref: str = Field(default="main", max_length=128)  # branch, tag, or SHA
    path: str = Field(..., min_length=1, max_length=512)  # file path in repo


class InlineSource(BaseModel):
    """Inline content (stored to default repo on creation)."""
    
    type: Literal["inline"] = "inline"
    content: str = Field(..., min_length=1, max_length=1_000_000)  # 1MB limit
    filename: str = Field(..., min_length=1, max_length=255)
    mime_type: str = Field(default="text/markdown", max_length=100)


class DocumentMetadata(BaseModel):
    """Document metadata computed on registration."""
    
    mime_type: str = Field(default="text/markdown")
    size_bytes: int | None = None
    line_count: int | None = None
    word_count: int | None = None


class Document(BaseModel):
    """
    Core Document domain object.
    
    Attributes:
        document_id: Unique identifier (ULID format)
        display_name: Human-readable name (defaults to filename)
        source: GitHub reference or inline content
        content_hash: SHA-256 hash of content (for skip logic)
        metadata: Computed file metadata
        created_at: When document was registered
        updated_at: Last modification time
    """
    
    document_id: str = Field(..., min_length=26, max_length=32)
    display_name: str | None = Field(default=None, max_length=160)
    source: GitHubSource | InlineSource
    content_hash: str | None = Field(default=None, pattern=r"^sha256:[a-f0-9]{64}$")
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)
    created_at: datetime
    updated_at: datetime
    
    @model_validator(mode="after")
    def set_default_display_name(self) -> "Document":
        if self.display_name is None:
            if isinstance(self.source, GitHubSource):
                # Extract filename from path
                self.display_name = self.source.path.split("/")[-1]
            elif isinstance(self.source, InlineSource):
                self.display_name = self.source.filename
        return self
    
    model_config = {"from_attributes": True}
```

### 4.3 Enums and Value Objects

```python
# app/domain/models/enums.py
"""
Domain enumerations.
"""
from enum import StrEnum


class RunStatus(StrEnum):
    """Run lifecycle status."""
    
    PENDING = "pending"        # Created, not yet started
    QUEUED = "queued"          # Waiting for resources
    RUNNING = "running"        # Actively executing
    COMPLETED = "completed"    # Successfully finished
    FAILED = "failed"          # Execution failed
    CANCELLED = "cancelled"    # User or system cancelled
    
    @classmethod
    def terminal_states(cls) -> set["RunStatus"]:
        """States that cannot transition to other states."""
        return {cls.COMPLETED, cls.FAILED, cls.CANCELLED}
    
    @classmethod
    def active_states(cls) -> set["RunStatus"]:
        """States where work may be in progress."""
        return {cls.QUEUED, cls.RUNNING}


class DocumentStatus(StrEnum):
    """Document processing status within a run."""
    
    PENDING = "pending"        # Not yet processed
    PROCESSING = "processing"  # Currently being processed
    COMPLETED = "completed"    # Successfully processed
    SKIPPED = "skipped"        # Skipped (already processed or excluded)
    FAILED = "failed"          # Processing failed


class GeneratorType(StrEnum):
    """Supported generator types."""
    
    FPF = "fpf"    # FilePromptForge
    GPTR = "gptr"  # GPT-Researcher
    DR = "dr"      # Deep Research (GPT-R variant)


class EvalMode(StrEnum):
    """Evaluation modes."""
    
    SINGLE = "single"      # Single-document graded evaluation
    PAIRWISE = "pairwise"  # Pairwise comparison
    BOTH = "both"          # Both single and pairwise
```

```python
# app/domain/models/value_objects.py
"""
Domain value objects (immutable configuration structures).
"""
from pydantic import BaseModel, Field


class GeneratorConfig(BaseModel):
    """Configuration for a single generator execution."""
    
    type: str  # fpf, gptr, dr
    provider: str  # openai, google, anthropic
    model: str  # gpt-5.1, gemini-2.5-flash, etc.
    iterations: int = Field(default=1, ge=1, le=10)


class ConcurrencyConfig(BaseModel):
    """Concurrency settings for generators."""
    
    fpf: int = Field(default=2, ge=1, le=20)
    gptr: int = Field(default=2, ge=1, le=20)


class EvalConfig(BaseModel):
    """Evaluation configuration."""
    
    auto_run: bool = Field(default=True)
    iterations: int = Field(default=1, ge=1, le=5)
    pairwise_top_n: int = Field(default=3, ge=1, le=10)
    mode: str = Field(default="both")  # single, pairwise, both
    judges: list[dict] = Field(default_factory=list)  # [{provider, model}]


class CombineConfig(BaseModel):
    """Combine phase configuration."""
    
    enabled: bool = Field(default=True)
    models: list[dict] = Field(default_factory=list)  # [{provider, model}]


class RunConfig(BaseModel):
    """
    Complete run configuration.
    
    Mirrors ACM 1.0 config.yaml structure for compatibility.
    """
    
    iterations_default: int = Field(default=1, ge=1, le=10)
    one_file_only: bool = Field(default=False)
    generators: list[GeneratorConfig] = Field(default_factory=list)
    concurrency: ConcurrencyConfig = Field(default_factory=ConcurrencyConfig)
    eval: EvalConfig = Field(default_factory=EvalConfig)
    combine: CombineConfig = Field(default_factory=CombineConfig)
    
    # GitHub repository references
    docs_repo: str | None = None      # Input documents repo
    outputs_repo: str | None = None   # Output artifacts repo
    logs_repo: str | None = None      # Logs repo
    
    # Optional file references
    instructions_file: str | None = None
    guidelines_file: str | None = None
```

## 5. Database Schema

### 5.0 Database Strategy

ACM 2.0 supports two database backends:

| Backend | Use Case | Connection String |
|---------|----------|-------------------|
| **SQLite** (default) | Single-user, self-hosted, development | `sqlite+aiosqlite:///./data/acm2.db` |
| **PostgreSQL** | Multi-user, production | `postgresql+asyncpg://user:pass@host/acm2` |

**Design principles:**
- SQLAlchemy models work unchanged with both backends
- Use portable types (`JSON` instead of PostgreSQL-specific `JSONB`)
- Arrays stored as JSON (works in both, PostgreSQL can optimize later)
- ULIDs stored as `String(26)` (portable, sortable)
- Database URL configured via environment variable

```python
# app/config.py (database section)
class DatabaseSettings(BaseModel):
    """Database configuration."""
    
    url: str = Field(
        default="sqlite+aiosqlite:///./data/acm2.db",
        description="Database connection URL. SQLite for single-user, PostgreSQL for multi-user."
    )
    echo: bool = Field(default=False, description="Echo SQL statements for debugging")
    pool_size: int = Field(default=5, ge=1, le=20, description="Connection pool size (PostgreSQL only)")
    
    @property
    def is_sqlite(self) -> bool:
        return self.url.startswith("sqlite")
```

### 5.1 Base Model and Mixins

```python
# app/infra/db/base.py
"""
SQLAlchemy base model and common mixins.
"""
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    
    type_annotation_map = {
        dict[str, Any]: JSON,
        list[Any]: JSON,
    }


class TimestampMixin:
    """Adds created_at and updated_at columns."""
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ULIDPrimaryKeyMixin:
    """Adds a ULID primary key column."""
    
    # Note: ULID is generated in application code, not database
    # This allows pre-generation for optimistic inserts
    pass
```

### 5.2 runs Table

```python
# app/infra/db/models/run.py
"""
Run database model.

Maps the Run domain object to the `runs` table.
"""
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.infra.db.models.run_document import RunDocument


class RunModel(Base, TimestampMixin):
    """
    SQLAlchemy model for the runs table.
    
    Stores run metadata and configuration. File content lives in GitHub;
    this table tracks state, relationships, and queryable fields.
    """
    
    __tablename__ = "runs"
    
    # Primary key (ULID, 26 chars)
    run_id: Mapped[str] = mapped_column(
        String(26),
        primary_key=True,
        comment="ULID identifier, e.g., 01HGWJ8K9M2N3P4Q5R6S7T8U9V",
    )
    
    # Core fields
    project_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="Project this run belongs to, e.g., firstpub-platform",
    )
    title: Mapped[str | None] = mapped_column(
        String(160),
        nullable=True,
        comment="Human-readable title for the run",
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="pending",
        index=True,
        comment="Lifecycle status: pending, queued, running, completed, failed, cancelled",
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
        comment="Execution priority 1-9 (1=highest)",
    )
    
    # Configuration (stored as JSON for portability)
    config: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="Run configuration: generators, concurrency, eval settings",
    )
    
    # Tags (stored as JSON array for portability)
    tags: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="Searchable tags, max 10",
    )
    
    # Ownership and summary
    requested_by: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="User or system that created the run",
    )
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Completion summary, max 2000 chars",
    )
    
    # Lifecycle timestamps (in addition to created_at/updated_at from mixin)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When execution began",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When execution finished",
    )
    
    # Relationships
    run_documents: Mapped[list["RunDocument"]] = relationship(
        "RunDocument",
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    
    # Indexes for common queries
    __table_args__ = (
        Index("ix_runs_project_status", "project_id", "status"),
        Index("ix_runs_created_at_desc", created_at.desc()),
        Index("ix_runs_status_priority", "status", "priority"),
    )
    
    def __repr__(self) -> str:
        return f"<Run {self.run_id} [{self.status}]>"
```

### 5.3 documents Table

```python
# app/infra/db/models/document.py
"""
Document database model.

Maps the Document domain object to the `documents` table.
"""
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.infra.db.models.run_document import RunDocument


class DocumentModel(Base, TimestampMixin):
    """
    SQLAlchemy model for the documents table.
    
    Stores document metadata and GitHub references. Actual file content
    lives in GitHub; this table enables queries and relationship tracking.
    """
    
    __tablename__ = "documents"
    
    # Primary key (ULID, 26 chars)
    document_id: Mapped[str] = mapped_column(
        String(26),
        primary_key=True,
        comment="ULID identifier",
    )
    
    # Display name
    display_name: Mapped[str | None] = mapped_column(
        String(160),
        nullable=True,
        comment="Human-readable name, defaults to filename",
    )
    
    # Source type discriminator
    source_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        comment="Source type: github or inline",
    )
    
    # GitHub source fields (nullable for inline sources)
    github_repository: Mapped[str | None] = mapped_column(
        String(256),
        nullable=True,
        index=True,
        comment="GitHub repo in owner/repo format",
    )
    github_ref: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="Branch, tag, or commit SHA",
    )

### 5.4 Database Migrations (Alembic)

ACM 2.0 uses Alembic for database schema migrations.

**Setup:**
- `alembic init app/infra/db/migrations`
- Configure `alembic.ini` to use `app.config.Settings` for database URL.
- Import all models in `app/infra/db/migrations/env.py` to support autogenerate.

**Workflow:**
1. Modify SQLAlchemy models.
2. Run `alembic revision --autogenerate -m "description"`.
3. Review generated migration script.
4. Run `alembic upgrade head` to apply.

**Consolidated Schema Reference:**
- `runs`, `documents`, `run_documents`: Defined in Step 2.7A.
- `artifacts`: Defined in Step 9.
- `eval_results`, `pairwise_comparisons`, `elo_ratings`: Defined in Step 10.
- `combined_outputs`: Defined in Step 17.

**Action Required:** Ensure all models are imported in `env.py` so Alembic sees the full schema.
    github_path: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        comment="File path within repo",
    )
    
    # Inline source fields (nullable for GitHub sources)
    inline_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Inline content for non-GitHub documents (max 1MB)",
    )
    inline_filename: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Filename for inline content",
    )
    inline_mime_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        default="text/markdown",
        comment="MIME type for inline content",
    )
    
    # Content hash for skip logic
    content_hash: Mapped[str | None] = mapped_column(
        String(71),  # "sha256:" + 64 hex chars
        nullable=True,
        index=True,
        comment="SHA-256 hash of content, e.g., sha256:abc123...",
    )
    
    # Metadata (computed on registration)
    metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="Computed metadata: mime_type, size_bytes, line_count, word_count",
    )
    
    # Relationships
    run_documents: Mapped[list["RunDocument"]] = relationship(
        "RunDocument",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    
    # Indexes
    __table_args__ = (
        Index("ix_documents_github_repo_path", "github_repository", "github_path"),
        Index("ix_documents_content_hash", "content_hash"),
    )
    
    def __repr__(self) -> str:
        name = self.display_name or self.github_path or self.inline_filename
        return f"<Document {self.document_id} [{name}]>"
```

### 5.4 run_documents Junction Table

```python
# app/infra/db/models/run_document.py
"""
Run-Document junction table for many-to-many relationship.

A Document can belong to multiple Runs, and a Run can have multiple Documents.
This table tracks the relationship and per-run document status.
"""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.infra.db.models.document import DocumentModel
    from app.infra.db.models.run import RunModel


class RunDocument(Base, TimestampMixin):
    """
    Junction table linking runs to documents.
    
    Stores per-run document status (a document may be completed in one run
    but pending in another). Also tracks processing order.
    """
    
    __tablename__ = "run_documents"
    
    # Composite primary key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Auto-increment surrogate key",
    )
    
    # Foreign keys
    run_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("documents.document_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Per-run document status
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="pending",
        comment="Document status in this run: pending, processing, completed, skipped, failed",
    )
    
    # Processing order within the run
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Order in which documents are processed",
    )
    
    # Error tracking
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if status is failed",
    )
    
    # Processing timestamps
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When processing began for this document in this run",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When processing finished",
    )
    
    # Relationships
    run: Mapped["RunModel"] = relationship(
        "RunModel",
        back_populates="run_documents",
    )
    document: Mapped["DocumentModel"] = relationship(
        "DocumentModel",
        back_populates="run_documents",
    )
    
    # Constraints and indexes
    __table_args__ = (
        # Prevent duplicate document in same run
        UniqueConstraint("run_id", "document_id", name="uq_run_document"),
        Index("ix_run_documents_run_status", "run_id", "status"),
        Index("ix_run_documents_run_order", "run_id", "sort_order"),
    )
    
    def __repr__(self) -> str:
        return f"<RunDocument run={self.run_id} doc={self.document_id} [{self.status}]>"
```

### 5.5 Model Registry

```python
# app/infra/db/models/__init__.py
"""
Database model registry.

Import all models here to ensure they are registered with SQLAlchemy
before creating tables or running migrations.
"""
from app.infra.db.base import Base
from app.infra.db.models.document import DocumentModel
from app.infra.db.models.run import RunModel
from app.infra.db.models.run_document import RunDocument

__all__ = [
    "Base",
    "RunModel",
    "DocumentModel",
    "RunDocument",
]
```

### 5.6 Alembic Migration (Initial)

```python
# migrations/versions/001_initial_run_document.py
"""
Initial migration: runs, documents, run_documents tables.

Revision ID: 001
Create Date: 2024-12-04
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # runs table
    op.create_table(
        "runs",
        sa.Column("run_id", sa.String(26), primary_key=True),
        sa.Column("project_id", sa.String(64), nullable=False, index=True),
        sa.Column("title", sa.String(160), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, default="pending", index=True),
        sa.Column("priority", sa.Integer, nullable=False, default=5),
        sa.Column("config", sa.JSON, nullable=False, default={}),
        sa.Column("tags", sa.JSON, nullable=False, default=[]),
        sa.Column("requested_by", sa.String(64), nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_runs_project_status", "runs", ["project_id", "status"])
    op.create_index("ix_runs_status_priority", "runs", ["status", "priority"])
    
    # documents table
    op.create_table(
        "documents",
        sa.Column("document_id", sa.String(26), primary_key=True),
        sa.Column("display_name", sa.String(160), nullable=True),
        sa.Column("source_type", sa.String(16), nullable=False),
        sa.Column("github_repository", sa.String(256), nullable=True, index=True),
        sa.Column("github_ref", sa.String(128), nullable=True),
        sa.Column("github_path", sa.String(512), nullable=True),
        sa.Column("inline_content", sa.Text, nullable=True),
        sa.Column("inline_filename", sa.String(255), nullable=True),
        sa.Column("inline_mime_type", sa.String(100), nullable=True),
        sa.Column("content_hash", sa.String(71), nullable=True, index=True),
        sa.Column("metadata", sa.JSON, nullable=False, default={}),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_documents_github_repo_path", "documents", ["github_repository", "github_path"])
    
    # run_documents junction table
    op.create_table(
        "run_documents",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(26), sa.ForeignKey("runs.run_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("document_id", sa.String(26), sa.ForeignKey("documents.document_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("status", sa.String(16), nullable=False, default="pending"),
        sa.Column("sort_order", sa.Integer, nullable=False, default=0),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("run_id", "document_id", name="uq_run_document"),
    )
    op.create_index("ix_run_documents_run_status", "run_documents", ["run_id", "status"])
    op.create_index("ix_run_documents_run_order", "run_documents", ["run_id", "sort_order"])


def downgrade() -> None:
    op.drop_table("run_documents")
    op.drop_table("documents")
    op.drop_table("runs")
```

## 6. Repository Layer

The repository layer provides async CRUD operations for database models. Repositories handle only data access—no business logic. They use SQLAlchemy 2.0 async patterns with proper session management.

### 6.0 Base Repository

```python
# app/infra/db/repositories/base.py
"""
Base repository with common CRUD operations.
"""
from typing import Any, Generic, TypeVar

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """
    Generic base repository providing common CRUD operations.
    
    Subclasses must set `model_class` to the SQLAlchemy model.
    """
    
    model_class: type[ModelT]
    
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
    
    async def get_by_id(self, id_value: str) -> ModelT | None:
        """Get a single record by primary key."""
        return await self.session.get(self.model_class, id_value)
    
    async def get_all(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ModelT]:
        """Get all records with pagination."""
        stmt = (
            select(self.model_class)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def count(self) -> int:
        """Count total records."""
        stmt = select(func.count()).select_from(self.model_class)
        result = await self.session.execute(stmt)
        return result.scalar() or 0
    
    async def create(self, entity: ModelT) -> ModelT:
        """Insert a new record."""
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity
    
    async def update(self, entity: ModelT) -> ModelT:
        """Update an existing record."""
        await self.session.flush()
        await self.session.refresh(entity)
        return entity
    
    async def delete(self, entity: ModelT) -> None:
        """Delete a record."""
        await self.session.delete(entity)
        await self.session.flush()
    
    async def exists(self, id_value: str) -> bool:
        """Check if a record exists by primary key."""
        entity = await self.get_by_id(id_value)
        return entity is not None
```

### 6.1 RunRepository

```python
# app/infra/db/repositories/run_repository.py
"""
Repository for Run CRUD operations.
"""
from datetime import datetime
from typing import Sequence

from sqlalchemy import and_, or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.models.enums import RunStatus
from app.infra.db.models.run import RunModel
from app.infra.db.models.run_document import RunDocument
from app.infra.db.repositories.base import BaseRepository


class RunRepository(BaseRepository[RunModel]):
    """
    Repository for Run database operations.
    
    Provides:
    - Standard CRUD (inherited from BaseRepository)
    - Filtering by status, project, tags, date range
    - Eager loading of documents
    - Status transition queries
    """
    
    model_class = RunModel
    
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
    
    async def get_by_id_with_documents(self, run_id: str) -> RunModel | None:
        """Get a run with all its documents eagerly loaded."""
        stmt = (
            select(RunModel)
            .where(RunModel.run_id == run_id)
            .options(selectinload(RunModel.run_documents))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def list_runs(
        self,
        *,
        project_id: str | None = None,
        status: RunStatus | list[RunStatus] | None = None,
        tags: list[str] | None = None,
        requested_by: str | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
        order_by: str = "created_at_desc",
    ) -> tuple[list[RunModel], int]:
        """
        List runs with filtering and pagination.
        
        Returns:
            Tuple of (runs, total_count)
        """
        # Build filter conditions
        conditions = []
        
        if project_id:
            conditions.append(RunModel.project_id == project_id)
        
        if status:
            if isinstance(status, list):
                conditions.append(RunModel.status.in_([s.value for s in status]))
            else:
                conditions.append(RunModel.status == status.value)
        
        if requested_by:
            conditions.append(RunModel.requested_by == requested_by)
        
        if created_after:
            conditions.append(RunModel.created_at >= created_after)
        
        if created_before:
            conditions.append(RunModel.created_at <= created_before)
        
        # Tags filtering (JSON contains - works in SQLite and PostgreSQL)
        # Note: For SQLite, this requires application-level filtering
        # For production PostgreSQL, use @> operator
        if tags:
            # Simple approach: filter in application for SQLite compatibility
            pass  # Applied after fetch for portability
        
        # Build base query
        base_query = select(RunModel)
        if conditions:
            base_query = base_query.where(and_(*conditions))
        
        # Count total
        count_stmt = select(func.count()).select_from(base_query.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0
        
        # Apply ordering
        if order_by == "created_at_desc":
            base_query = base_query.order_by(RunModel.created_at.desc())
        elif order_by == "created_at_asc":
            base_query = base_query.order_by(RunModel.created_at.asc())
        elif order_by == "priority_asc":
            base_query = base_query.order_by(RunModel.priority.asc(), RunModel.created_at.desc())
        elif order_by == "updated_at_desc":
            base_query = base_query.order_by(RunModel.updated_at.desc())
        
        # Apply pagination
        stmt = base_query.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        runs = list(result.scalars().all())
        
        # Filter by tags in application (SQLite compatible)
        if tags:
            runs = [r for r in runs if any(tag in r.tags for tag in tags)]
            total = len(runs)  # Recount after tag filter
        
        return runs, total
    
    async def get_runs_by_status(
        self,
        statuses: list[RunStatus],
        limit: int = 100,
    ) -> list[RunModel]:
        """Get runs in specified statuses (for queue processing)."""
        stmt = (
            select(RunModel)
            .where(RunModel.status.in_([s.value for s in statuses]))
            .order_by(RunModel.priority.asc(), RunModel.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def count_by_status(self, status: RunStatus) -> int:
        """Count runs in a specific status."""
        stmt = (
            select(func.count())
            .select_from(RunModel)
            .where(RunModel.status == status.value)
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0
    
    async def get_active_runs_for_project(self, project_id: str) -> list[RunModel]:
        """Get all non-terminal runs for a project."""
        active_statuses = [s.value for s in RunStatus.active_states()]
        active_statuses.append(RunStatus.PENDING.value)
        
        stmt = (
            select(RunModel)
            .where(
                and_(
                    RunModel.project_id == project_id,
                    RunModel.status.in_(active_statuses),
                )
            )
            .order_by(RunModel.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
```

### 6.2 DocumentRepository

```python
# app/infra/db/repositories/document_repository.py
"""
Repository for Document CRUD operations.
"""
from typing import Sequence

from sqlalchemy import and_, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infra.db.models.document import DocumentModel
from app.infra.db.models.run_document import RunDocument
from app.infra.db.repositories.base import BaseRepository


class DocumentRepository(BaseRepository[DocumentModel]):
    """
    Repository for Document database operations.
    
    Provides:
    - Standard CRUD (inherited from BaseRepository)
    - Query by GitHub path, content hash
    - Documents for a specific run
    """
    
    model_class = DocumentModel
    
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
    
    async def get_by_github_path(
        self,
        repository: str,
        path: str,
        ref: str | None = None,
    ) -> DocumentModel | None:
        """Find a document by its GitHub location."""
        conditions = [
            DocumentModel.source_type == "github",
            DocumentModel.github_repository == repository,
            DocumentModel.github_path == path,
        ]
        if ref:
            conditions.append(DocumentModel.github_ref == ref)
        
        stmt = select(DocumentModel).where(and_(*conditions))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_by_content_hash(self, content_hash: str) -> DocumentModel | None:
        """Find a document by its content hash (for deduplication)."""
        stmt = (
            select(DocumentModel)
            .where(DocumentModel.content_hash == content_hash)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def list_documents_for_run(
        self,
        run_id: str,
        *,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[DocumentModel], int]:
        """
        List all documents attached to a run.
        
        Returns:
            Tuple of (documents, total_count)
        """
        # Build query through junction table
        conditions = [RunDocument.run_id == run_id]
        if status:
            conditions.append(RunDocument.status == status)
        
        stmt = (
            select(DocumentModel)
            .join(RunDocument, RunDocument.document_id == DocumentModel.document_id)
            .where(and_(*conditions))
            .order_by(RunDocument.sort_order.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        documents = list(result.scalars().all())
        
        # Count total
        count_stmt = (
            select(func.count())
            .select_from(RunDocument)
            .where(and_(*conditions))
        )
        total = (await self.session.execute(count_stmt)).scalar() or 0
        
        return documents, total
    
    async def get_documents_with_run_status(
        self,
        run_id: str,
    ) -> list[tuple[DocumentModel, RunDocument]]:
        """
        Get documents with their per-run status.
        
        Returns list of (DocumentModel, RunDocument) tuples.
        """
        stmt = (
            select(DocumentModel, RunDocument)
            .join(RunDocument, RunDocument.document_id == DocumentModel.document_id)
            .where(RunDocument.run_id == run_id)
            .order_by(RunDocument.sort_order.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.all())
    
    async def find_by_repository(
        self,
        repository: str,
        *,
        path_prefix: str | None = None,
        limit: int = 100,
    ) -> list[DocumentModel]:
        """Find all documents from a specific GitHub repository."""
        conditions = [
            DocumentModel.source_type == "github",
            DocumentModel.github_repository == repository,
        ]
        if path_prefix:
            conditions.append(DocumentModel.github_path.startswith(path_prefix))
        
        stmt = (
            select(DocumentModel)
            .where(and_(*conditions))
            .order_by(DocumentModel.github_path.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
```

### 6.3 RunDocumentRepository

```python
# app/infra/db/repositories/run_document_repository.py
"""
Repository for RunDocument junction table operations.
"""
from datetime import datetime

from sqlalchemy import and_, select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.enums import DocumentStatus
from app.infra.db.models.run_document import RunDocument
from app.infra.db.repositories.base import BaseRepository


class RunDocumentRepository(BaseRepository[RunDocument]):
    """
    Repository for RunDocument junction table operations.
    
    Manages the many-to-many relationship between runs and documents,
    including per-run document status.
    """
    
    model_class = RunDocument
    
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
    
    async def get_by_run_and_document(
        self,
        run_id: str,
        document_id: str,
    ) -> RunDocument | None:
        """Get the junction record for a specific run-document pair."""
        stmt = (
            select(RunDocument)
            .where(
                and_(
                    RunDocument.run_id == run_id,
                    RunDocument.document_id == document_id,
                )
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def exists_for_run(self, run_id: str, document_id: str) -> bool:
        """Check if a document is already attached to a run."""
        record = await self.get_by_run_and_document(run_id, document_id)
        return record is not None
    
    async def attach_document(
        self,
        run_id: str,
        document_id: str,
        sort_order: int | None = None,
    ) -> RunDocument:
        """
        Attach a document to a run.
        
        If sort_order is not provided, appends to end.
        """
        if sort_order is None:
            # Get next sort order
            stmt = (
                select(func.coalesce(func.max(RunDocument.sort_order), -1) + 1)
                .where(RunDocument.run_id == run_id)
            )
            result = await self.session.execute(stmt)
            sort_order = result.scalar() or 0
        
        run_doc = RunDocument(
            run_id=run_id,
            document_id=document_id,
            status=DocumentStatus.PENDING.value,
            sort_order=sort_order,
        )
        return await self.create(run_doc)
    
    async def detach_document(self, run_id: str, document_id: str) -> bool:
        """
        Remove a document from a run.
        
        Returns True if deleted, False if not found.
        """
        record = await self.get_by_run_and_document(run_id, document_id)
        if record:
            await self.delete(record)
            return True
        return False
    
    async def update_status(
        self,
        run_id: str,
        document_id: str,
        status: DocumentStatus,
        error_message: str | None = None,
    ) -> RunDocument | None:
        """Update the status of a document within a run."""
        record = await self.get_by_run_and_document(run_id, document_id)
        if not record:
            return None
        
        record.status = status.value
        if error_message:
            record.error_message = error_message
        
        if status == DocumentStatus.PROCESSING:
            record.started_at = datetime.utcnow()
        elif status in (DocumentStatus.COMPLETED, DocumentStatus.FAILED, DocumentStatus.SKIPPED):
            record.completed_at = datetime.utcnow()
        
        return await self.update(record)
    
    async def count_by_status(self, run_id: str, status: DocumentStatus) -> int:
        """Count documents in a specific status for a run."""
        stmt = (
            select(func.count())
            .select_from(RunDocument)
            .where(
                and_(
                    RunDocument.run_id == run_id,
                    RunDocument.status == status.value,
                )
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0
    
    async def get_status_summary(self, run_id: str) -> dict[str, int]:
        """Get count of documents in each status for a run."""
        stmt = (
            select(RunDocument.status, func.count())
            .where(RunDocument.run_id == run_id)
            .group_by(RunDocument.status)
        )
        result = await self.session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}
    
    async def get_next_pending(self, run_id: str) -> RunDocument | None:
        """Get the next pending document for processing."""
        stmt = (
            select(RunDocument)
            .where(
                and_(
                    RunDocument.run_id == run_id,
                    RunDocument.status == DocumentStatus.PENDING.value,
                )
            )
            .order_by(RunDocument.sort_order.asc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def reorder_documents(
        self,
        run_id: str,
        document_ids: list[str],
    ) -> None:
        """Reorder documents in a run by updating sort_order."""
        for order, doc_id in enumerate(document_ids):
            stmt = (
                update(RunDocument)
                .where(
                    and_(
                        RunDocument.run_id == run_id,
                        RunDocument.document_id == doc_id,
                    )
                )
                .values(sort_order=order)
            )
            await self.session.execute(stmt)
        await self.session.flush()
```

### 6.4 Repository Registry

```python
# app/infra/db/repositories/__init__.py
"""
Repository registry.

Provides a single point of access to all repositories.
"""
from app.infra.db.repositories.base import BaseRepository
from app.infra.db.repositories.document_repository import DocumentRepository
from app.infra.db.repositories.run_document_repository import RunDocumentRepository
from app.infra.db.repositories.run_repository import RunRepository

__all__ = [
    "BaseRepository",
    "RunRepository",
    "DocumentRepository",
    "RunDocumentRepository",
]
```

## 7. Service Layer

The service layer contains business logic and orchestrates repository calls. Services manage transactions, enforce business rules, and translate between domain models and database models.

### 7.0 Service Dependencies

```python
# app/services/dependencies.py
"""
Service dependency injection setup.

Provides FastAPI dependencies for injecting services into route handlers.
"""
from typing import Annotated, AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.session import get_session
from app.services.document_service import DocumentService
from app.services.run_service import RunService


async def get_run_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AsyncGenerator[RunService, None]:
    """Provide RunService with database session."""
    service = RunService(session)
    yield service


async def get_document_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AsyncGenerator[DocumentService, None]:
    """Provide DocumentService with database session."""
    service = DocumentService(session)
    yield service


# Type aliases for cleaner route signatures
RunServiceDep = Annotated[RunService, Depends(get_run_service)]
DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]
```

### 7.1 RunService

```python
# app/services/run_service.py
"""
Run service - business logic for run lifecycle.
"""
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from app.domain.models.enums import RunStatus, DocumentStatus
from app.domain.models.run import Run
from app.domain.models.value_objects import RunConfig
from app.domain.exceptions import (
    RunNotFoundError,
    InvalidStatusTransitionError,
    RunAlreadyTerminalError,
)
from app.infra.db.models.run import RunModel
from app.infra.db.repositories.run_repository import RunRepository
from app.infra.db.repositories.run_document_repository import RunDocumentRepository
from app.infra.logging import get_logger

logger = get_logger(__name__)


class RunService:
    """
    Service for Run lifecycle operations.
    
    Responsibilities:
    - Create runs with validated configuration
    - Enforce status transition rules
    - Coordinate with DocumentService for document attachment
    - Provide run queries with filtering
    """
    
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.run_repo = RunRepository(session)
        self.run_doc_repo = RunDocumentRepository(session)
    
    # ─────────────────────────────────────────────────────────────────
    # CREATE
    # ─────────────────────────────────────────────────────────────────
    
    async def create_run(
        self,
        *,
        project_id: str,
        requested_by: str,
        title: str | None = None,
        config: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        priority: int = 5,
    ) -> Run:
        """
        Create a new run.
        
        Args:
            project_id: Project this run belongs to
            requested_by: User or system creating the run
            title: Optional human-readable title
            config: Run configuration (validated against RunConfig schema)
            tags: Searchable tags (max 10)
            priority: Execution priority 1-9 (default 5)
        
        Returns:
            Created Run domain object
        
        Raises:
            ValidationError: If config or tags are invalid
        """
        # Generate ULID
        run_id = str(ULID())
        now = datetime.utcnow()
        
        # Validate config against schema (raises ValidationError if invalid)
        validated_config = RunConfig(**(config or {}))
        
        # Validate and normalize tags
        normalized_tags = self._normalize_tags(tags or [])
        
        # Create database model
        run_model = RunModel(
            run_id=run_id,
            project_id=project_id,
            title=title,
            status=RunStatus.PENDING.value,
            priority=priority,
            config=validated_config.model_dump(),
            tags=normalized_tags,
            requested_by=requested_by,
            created_at=now,
            updated_at=now,
        )
        
        created = await self.run_repo.create(run_model)
        await self.session.commit()
        
        logger.info(
            "run_created",
            run_id=run_id,
            project_id=project_id,
            requested_by=requested_by,
        )
        
        return self._to_domain(created)
    
    # ─────────────────────────────────────────────────────────────────
    # READ
    # ─────────────────────────────────────────────────────────────────
    
    async def get_run(self, run_id: str) -> Run:
        """
        Get a run by ID.
        
        Raises:
            RunNotFoundError: If run doesn't exist
        """
        run_model = await self.run_repo.get_by_id(run_id)
        if not run_model:
            raise RunNotFoundError(run_id)
        return self._to_domain(run_model)
    
    async def get_run_with_documents(self, run_id: str) -> tuple[Run, dict[str, int]]:
        """
        Get a run with document status summary.
        
        Returns:
            Tuple of (Run, status_counts) where status_counts is
            {"pending": N, "completed": M, ...}
        """
        run_model = await self.run_repo.get_by_id_with_documents(run_id)
        if not run_model:
            raise RunNotFoundError(run_id)
        
        status_summary = await self.run_doc_repo.get_status_summary(run_id)
        return self._to_domain(run_model), status_summary
    
    async def list_runs(
        self,
        *,
        project_id: str | None = None,
        status: RunStatus | list[RunStatus] | None = None,
        tags: list[str] | None = None,
        requested_by: str | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
        order_by: str = "created_at_desc",
    ) -> tuple[list[Run], int]:
        """
        List runs with filtering and pagination.
        
        Returns:
            Tuple of (runs, total_count)
        """
        run_models, total = await self.run_repo.list_runs(
            project_id=project_id,
            status=status,
            tags=tags,
            requested_by=requested_by,
            created_after=created_after,
            created_before=created_before,
            limit=limit,
            offset=offset,
            order_by=order_by,
        )
        runs = [self._to_domain(m) for m in run_models]
        return runs, total
    
    # ─────────────────────────────────────────────────────────────────
    # UPDATE
    # ─────────────────────────────────────────────────────────────────
    
    async def update_run(
        self,
        run_id: str,
        *,
        title: str | None = None,
        priority: int | None = None,
        tags: list[str] | None = None,
        summary: str | None = None,
    ) -> Run:
        """
        Update run metadata.
        
        Note: Status updates use dedicated transition methods.
        
        Raises:
            RunNotFoundError: If run doesn't exist
            RunAlreadyTerminalError: If run is in terminal state (except summary)
        """
        run_model = await self.run_repo.get_by_id(run_id)
        if not run_model:
            raise RunNotFoundError(run_id)
        
        # Terminal runs can only update summary
        if run_model.status in [s.value for s in RunStatus.terminal_states()]:
            if title is not None or priority is not None or tags is not None:
                raise RunAlreadyTerminalError(run_id, run_model.status)
        
        # Apply updates
        if title is not None:
            run_model.title = title
        if priority is not None:
            run_model.priority = priority
        if tags is not None:
            run_model.tags = self._normalize_tags(tags)
        if summary is not None:
            run_model.summary = summary[:2000]  # Enforce limit
        
        run_model.updated_at = datetime.utcnow()
        updated = await self.run_repo.update(run_model)
        await self.session.commit()
        
        logger.info("run_updated", run_id=run_id)
        return self._to_domain(updated)
    
    async def transition_status(
        self,
        run_id: str,
        new_status: RunStatus,
        *,
        error_message: str | None = None,
    ) -> Run:
        """
        Transition run to a new status.
        
        Enforces valid transitions:
        - pending → queued, cancelled
        - queued → running, cancelled
        - running → completed, failed, cancelled
        - completed, failed, cancelled → (no transitions allowed)
        
        Raises:
            RunNotFoundError: If run doesn't exist
            InvalidStatusTransitionError: If transition is not allowed
        """
        run_model = await self.run_repo.get_by_id(run_id)
        if not run_model:
            raise RunNotFoundError(run_id)
        
        current = RunStatus(run_model.status)
        if not self._is_valid_transition(current, new_status):
            raise InvalidStatusTransitionError(run_id, current, new_status)
        
        now = datetime.utcnow()
        run_model.status = new_status.value
        run_model.updated_at = now
        
        # Set lifecycle timestamps
        if new_status == RunStatus.RUNNING:
            run_model.started_at = now
        elif new_status in RunStatus.terminal_states():
            run_model.completed_at = now
            if error_message and new_status == RunStatus.FAILED:
                run_model.summary = error_message[:2000]
        
        updated = await self.run_repo.update(run_model)
        await self.session.commit()
        
        logger.info(
            "run_status_changed",
            run_id=run_id,
            from_status=current.value,
            to_status=new_status.value,
        )
        return self._to_domain(updated)
    
    # ─────────────────────────────────────────────────────────────────
    # DELETE
    # ─────────────────────────────────────────────────────────────────
    
    async def cancel_run(self, run_id: str) -> Run:
        """
        Cancel a run (soft delete).
        
        Sets status to 'cancelled'. Does not delete data.
        """
        return await self.transition_status(run_id, RunStatus.CANCELLED)
    
    async def delete_run(self, run_id: str) -> None:
        """
        Hard delete a run and all associated data.
        
        Use with caution - primarily for testing/cleanup.
        
        Raises:
            RunNotFoundError: If run doesn't exist
        """
        run_model = await self.run_repo.get_by_id(run_id)
        if not run_model:
            raise RunNotFoundError(run_id)
        
        await self.run_repo.delete(run_model)
        await self.session.commit()
        
        logger.warning("run_deleted", run_id=run_id)
    
    # ─────────────────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────────────────
    
    def _to_domain(self, model: RunModel) -> Run:
        """Convert database model to domain object."""
        return Run(
            run_id=model.run_id,
            project_id=model.project_id,
            title=model.title,
            status=RunStatus(model.status),
            priority=model.priority,
            config=RunConfig(**model.config),
            tags=model.tags,
            requested_by=model.requested_by,
            summary=model.summary,
            created_at=model.created_at,
            updated_at=model.updated_at,
            started_at=model.started_at,
            completed_at=model.completed_at,
        )
    
    def _normalize_tags(self, tags: list[str]) -> list[str]:
        """Normalize and validate tags."""
        if len(tags) > 10:
            raise ValueError("Maximum 10 tags allowed")
        normalized = []
        for tag in tags:
            tag = tag.strip().lower()
            if not tag:
                continue
            if len(tag) > 32:
                raise ValueError(f"Tag exceeds 32 character limit")
            normalized.append(tag)
        return normalized
    
    def _is_valid_transition(self, current: RunStatus, new: RunStatus) -> bool:
        """Check if status transition is allowed."""
        valid_transitions = {
            RunStatus.PENDING: {RunStatus.QUEUED, RunStatus.CANCELLED},
            RunStatus.QUEUED: {RunStatus.RUNNING, RunStatus.CANCELLED},
            RunStatus.RUNNING: {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED},
            RunStatus.COMPLETED: set(),
            RunStatus.FAILED: set(),
            RunStatus.CANCELLED: set(),
        }
        return new in valid_transitions.get(current, set())
```

### 7.2 DocumentService

```python
# app/services/document_service.py
"""
Document service - business logic for document management.
"""
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from app.domain.models.document import Document, GitHubSource, InlineSource, DocumentMetadata
from app.domain.models.enums import DocumentStatus
from app.domain.exceptions import (
    DocumentNotFoundError,
    RunNotFoundError,
    DocumentAlreadyAttachedError,
    DocumentNotAttachedError,
)
from app.infra.db.models.document import DocumentModel
from app.infra.db.models.run_document import RunDocument
from app.infra.db.repositories.document_repository import DocumentRepository
from app.infra.db.repositories.run_repository import RunRepository
from app.infra.db.repositories.run_document_repository import RunDocumentRepository
from app.infra.logging import get_logger

logger = get_logger(__name__)


class DocumentService:
    """
    Service for Document lifecycle operations.
    
    Responsibilities:
    - Register documents (GitHub or inline)
    - Attach/detach documents to/from runs
    - Track per-run document status
    - Support batch operations
    """
    
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.doc_repo = DocumentRepository(session)
        self.run_repo = RunRepository(session)
        self.run_doc_repo = RunDocumentRepository(session)
    
    # ─────────────────────────────────────────────────────────────────
    # REGISTER DOCUMENTS
    # ─────────────────────────────────────────────────────────────────
    
    async def register_github_document(
        self,
        *,
        repository: str,
        path: str,
        ref: str = "main",
        display_name: str | None = None,
    ) -> Document:
        """
        Register a document from GitHub.
        
        If a document with the same repo/path/ref already exists, returns it.
        
        Args:
            repository: GitHub repo in "owner/repo" format
            path: File path within repo
            ref: Branch, tag, or commit SHA (default: "main")
            display_name: Optional display name (defaults to filename)
        
        Returns:
            Registered Document
        """
        # Check for existing document
        existing = await self.doc_repo.get_by_github_path(repository, path, ref)
        if existing:
            logger.debug("document_exists", document_id=existing.document_id)
            return self._to_domain(existing)
        
        # Create new document
        document_id = str(ULID())
        now = datetime.utcnow()
        
        doc_model = DocumentModel(
            document_id=document_id,
            display_name=display_name or path.split("/")[-1],
            source_type="github",
            github_repository=repository,
            github_ref=ref,
            github_path=path,
            metadata={
                "mime_type": self._guess_mime_type(path),
            },
            created_at=now,
            updated_at=now,
        )
        
        created = await self.doc_repo.create(doc_model)
        await self.session.commit()
        
        logger.info(
            "document_registered",
            document_id=document_id,
            source_type="github",
            repository=repository,
            path=path,
        )
        
        return self._to_domain(created)
    
    async def register_inline_document(
        self,
        *,
        content: str,
        filename: str,
        mime_type: str = "text/markdown",
        display_name: str | None = None,
    ) -> Document:
        """
        Register a document with inline content.
        
        Args:
            content: Document content (max 1MB)
            filename: Filename for the content
            mime_type: MIME type (default: text/markdown)
            display_name: Optional display name (defaults to filename)
        
        Returns:
            Registered Document
        """
        if len(content) > 1_000_000:
            raise ValueError("Content exceeds 1MB limit")
        
        document_id = str(ULID())
        now = datetime.utcnow()
        
        # Compute content hash
        import hashlib
        content_hash = "sha256:" + hashlib.sha256(content.encode()).hexdigest()
        
        # Check for duplicate content
        existing = await self.doc_repo.get_by_content_hash(content_hash)
        if existing:
            logger.debug("document_exists_by_hash", document_id=existing.document_id)
            return self._to_domain(existing)
        
        doc_model = DocumentModel(
            document_id=document_id,
            display_name=display_name or filename,
            source_type="inline",
            inline_content=content,
            inline_filename=filename,
            inline_mime_type=mime_type,
            content_hash=content_hash,
            metadata={
                "mime_type": mime_type,
                "size_bytes": len(content.encode()),
                "line_count": content.count("\n") + 1,
                "word_count": len(content.split()),
            },
            created_at=now,
            updated_at=now,
        )
        
        created = await self.doc_repo.create(doc_model)
        await self.session.commit()
        
        logger.info(
            "document_registered",
            document_id=document_id,
            source_type="inline",
            filename=filename,
        )
        
        return self._to_domain(created)
    
    # ─────────────────────────────────────────────────────────────────
    # ATTACH/DETACH FROM RUNS
    # ─────────────────────────────────────────────────────────────────
    
    async def attach_to_run(
        self,
        run_id: str,
        document_id: str,
        *,
        sort_order: int | None = None,
    ) -> Document:
        """
        Attach a document to a run.
        
        Raises:
            RunNotFoundError: If run doesn't exist
            DocumentNotFoundError: If document doesn't exist
            DocumentAlreadyAttachedError: If document is already in run
        """
        # Verify run exists
        run = await self.run_repo.get_by_id(run_id)
        if not run:
            raise RunNotFoundError(run_id)
        
        # Verify document exists
        doc = await self.doc_repo.get_by_id(document_id)
        if not doc:
            raise DocumentNotFoundError(document_id)
        
        # Check if already attached
        if await self.run_doc_repo.exists_for_run(run_id, document_id):
            raise DocumentAlreadyAttachedError(run_id, document_id)
        
        # Attach
        await self.run_doc_repo.attach_document(run_id, document_id, sort_order)
        await self.session.commit()
        
        logger.info(
            "document_attached",
            run_id=run_id,
            document_id=document_id,
        )
        
        return self._to_domain(doc)
    
    async def attach_github_document_to_run(
        self,
        run_id: str,
        *,
        repository: str,
        path: str,
        ref: str = "main",
        display_name: str | None = None,
    ) -> Document:
        """
        Register a GitHub document and attach it to a run in one operation.
        
        Convenience method that combines register + attach.
        """
        doc = await self.register_github_document(
            repository=repository,
            path=path,
            ref=ref,
            display_name=display_name,
        )
        return await self.attach_to_run(run_id, doc.document_id)
    
    async def attach_documents_batch(
        self,
        run_id: str,
        documents: list[dict[str, Any]],
    ) -> list[Document]:
        """
        Attach multiple documents to a run.
        
        Each dict in documents should have either:
        - {"document_id": "..."} for existing documents
        - {"repository": "...", "path": "...", "ref": "..."} for GitHub docs
        - {"content": "...", "filename": "..."} for inline docs
        
        Returns list of attached documents (skips duplicates).
        """
        # Verify run exists
        run = await self.run_repo.get_by_id(run_id)
        if not run:
            raise RunNotFoundError(run_id)
        
        attached = []
        for i, doc_spec in enumerate(documents):
            try:
                if "document_id" in doc_spec:
                    # Existing document
                    doc = await self.attach_to_run(
                        run_id,
                        doc_spec["document_id"],
                        sort_order=i,
                    )
                elif "repository" in doc_spec:
                    # GitHub document
                    doc = await self.register_github_document(
                        repository=doc_spec["repository"],
                        path=doc_spec["path"],
                        ref=doc_spec.get("ref", "main"),
                        display_name=doc_spec.get("display_name"),
                    )
                    try:
                        await self.attach_to_run(run_id, doc.document_id, sort_order=i)
                    except DocumentAlreadyAttachedError:
                        pass  # Skip duplicates
                elif "content" in doc_spec:
                    # Inline document
                    doc = await self.register_inline_document(
                        content=doc_spec["content"],
                        filename=doc_spec["filename"],
                        mime_type=doc_spec.get("mime_type", "text/markdown"),
                        display_name=doc_spec.get("display_name"),
                    )
                    try:
                        await self.attach_to_run(run_id, doc.document_id, sort_order=i)
                    except DocumentAlreadyAttachedError:
                        pass  # Skip duplicates
                else:
                    logger.warning("invalid_document_spec", index=i, spec=doc_spec)
                    continue
                
                attached.append(doc)
            except Exception as e:
                logger.error("batch_attach_error", index=i, error=str(e))
                raise
        
        await self.session.commit()
        logger.info("documents_batch_attached", run_id=run_id, count=len(attached))
        return attached
    
    async def detach_from_run(self, run_id: str, document_id: str) -> None:
        """
        Remove a document from a run.
        
        Raises:
            DocumentNotAttachedError: If document is not in run
        """
        if not await self.run_doc_repo.detach_document(run_id, document_id):
            raise DocumentNotAttachedError(run_id, document_id)
        
        await self.session.commit()
        logger.info("document_detached", run_id=run_id, document_id=document_id)
    
    # ─────────────────────────────────────────────────────────────────
    # READ
    # ─────────────────────────────────────────────────────────────────
    
    async def get_document(self, document_id: str) -> Document:
        """
        Get a document by ID.
        
        Raises:
            DocumentNotFoundError: If document doesn't exist
        """
        doc_model = await self.doc_repo.get_by_id(document_id)
        if not doc_model:
            raise DocumentNotFoundError(document_id)
        return self._to_domain(doc_model)
    
    async def list_documents_for_run(
        self,
        run_id: str,
        *,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Document], int]:
        """
        List all documents in a run.
        
        Returns:
            Tuple of (documents, total_count)
        """
        doc_models, total = await self.doc_repo.list_documents_for_run(
            run_id,
            status=status,
            limit=limit,
            offset=offset,
        )
        return [self._to_domain(m) for m in doc_models], total
    
    async def get_documents_with_status(
        self,
        run_id: str,
    ) -> list[tuple[Document, str, str | None]]:
        """
        Get documents with their per-run status.
        
        Returns list of (Document, status, error_message) tuples.
        """
        results = await self.doc_repo.get_documents_with_run_status(run_id)
        return [
            (self._to_domain(doc), run_doc.status, run_doc.error_message)
            for doc, run_doc in results
        ]
    
    # ─────────────────────────────────────────────────────────────────
    # STATUS UPDATES
    # ─────────────────────────────────────────────────────────────────
    
    async def update_document_status(
        self,
        run_id: str,
        document_id: str,
        status: DocumentStatus,
        *,
        error_message: str | None = None,
    ) -> None:
        """
        Update the status of a document within a run.
        
        Used by the execution engine to track progress.
        """
        result = await self.run_doc_repo.update_status(
            run_id,
            document_id,
            status,
            error_message,
        )
        if not result:
            raise DocumentNotAttachedError(run_id, document_id)
        
        await self.session.commit()
        logger.debug(
            "document_status_updated",
            run_id=run_id,
            document_id=document_id,
            status=status.value,
        )
    
    # ─────────────────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────────────────
    
    def _to_domain(self, model: DocumentModel) -> Document:
        """Convert database model to domain object."""
        # Build source object
        if model.source_type == "github":
            source = GitHubSource(
                repository=model.github_repository,
                ref=model.github_ref or "main",
                path=model.github_path,
            )
        else:
            source = InlineSource(
                content=model.inline_content or "",
                filename=model.inline_filename or "unknown",
                mime_type=model.inline_mime_type or "text/markdown",
            )
        
        return Document(
            document_id=model.document_id,
            display_name=model.display_name,
            source=source,
            content_hash=model.content_hash,
            metadata=DocumentMetadata(**model.metadata),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
    
    def _guess_mime_type(self, path: str) -> str:
        """Guess MIME type from file extension."""
        ext = path.lower().split(".")[-1] if "." in path else ""
        mime_map = {
            "md": "text/markdown",
            "markdown": "text/markdown",
            "txt": "text/plain",
            "json": "application/json",
            "yaml": "application/yaml",
            "yml": "application/yaml",
            "html": "text/html",
            "htm": "text/html",
        }
        return mime_map.get(ext, "text/plain")
```

### 7.3 Domain Exceptions

```python
# app/domain/exceptions.py
"""
Domain-specific exceptions.

These exceptions represent business rule violations and are translated
to appropriate HTTP responses by the error handling middleware.
"""


class DomainError(Exception):
    """Base class for domain exceptions."""
    
    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


# ─────────────────────────────────────────────────────────────────
# RUN EXCEPTIONS
# ─────────────────────────────────────────────────────────────────

class RunNotFoundError(DomainError):
    """Run does not exist."""
    
    def __init__(self, run_id: str) -> None:
        super().__init__(
            message=f"Run not found: {run_id}",
            code="RUN_NOT_FOUND",
        )
        self.run_id = run_id


class InvalidStatusTransitionError(DomainError):
    """Status transition is not allowed."""
    
    def __init__(self, run_id: str, from_status: str, to_status: str) -> None:
        super().__init__(
            message=f"Cannot transition run {run_id} from '{from_status}' to '{to_status}'",
            code="INVALID_STATUS_TRANSITION",
        )
        self.run_id = run_id
        self.from_status = from_status
        self.to_status = to_status


class RunAlreadyTerminalError(DomainError):
    """Run is in a terminal state and cannot be modified."""
    
    def __init__(self, run_id: str, status: str) -> None:
        super().__init__(
            message=f"Run {run_id} is in terminal state '{status}' and cannot be modified",
            code="RUN_ALREADY_TERMINAL",
        )
        self.run_id = run_id
        self.status = status


# ─────────────────────────────────────────────────────────────────
# DOCUMENT EXCEPTIONS
# ─────────────────────────────────────────────────────────────────

class DocumentNotFoundError(DomainError):
    """Document does not exist."""
    
    def __init__(self, document_id: str) -> None:
        super().__init__(
            message=f"Document not found: {document_id}",
            code="DOCUMENT_NOT_FOUND",
        )
        self.document_id = document_id


class DocumentAlreadyAttachedError(DomainError):
    """Document is already attached to the run."""
    
    def __init__(self, run_id: str, document_id: str) -> None:
        super().__init__(
            message=f"Document {document_id} is already attached to run {run_id}",
            code="DOCUMENT_ALREADY_ATTACHED",
        )
        self.run_id = run_id
        self.document_id = document_id


class DocumentNotAttachedError(DomainError):
    """Document is not attached to the run."""
    
    def __init__(self, run_id: str, document_id: str) -> None:
        super().__init__(
            message=f"Document {document_id} is not attached to run {run_id}",
            code="DOCUMENT_NOT_ATTACHED",
        )
        self.run_id = run_id
        self.document_id = document_id
```

