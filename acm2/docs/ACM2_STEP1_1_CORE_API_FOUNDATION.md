# ACM 2.0 – Phase 1.1 Core API Foundation

## 1. Purpose

Phase 1.1 establishes the **minimum viable API surface** for ACM 2.0 so that all subsequent development (generators, evaluation, UI) can depend on stable contracts. This phase does **not** integrate external engines; it focuses on data modeling, persistence, and HTTP/JSON endpoints that describe runs, documents, and artifacts.

## 2. Scope

- Define canonical representations for `Run`, `Document`, `Artifact`, `Task`, and `StorageProvider`.
- Stand up a FastAPI service with fully typed request/response schemas.
- Provide CRUD operations for runs and documents plus read-only access to artifacts (create placeholders only).
- Implement database persistence (PostgreSQL-preferred, SQLite fallback).
- Enforce Morgan's constraints: no legacy code reuse, files < 800 LOC, functions separated logically.
- Do **not** call FPF, GPT-R, or evaluation logic yet.

## 3. Success Criteria

| ID | Criterion | Verification Method |
|----|-----------|---------------------|
| SC-01 | API service boots with `uvicorn` and passes health check | `GET /health` returns 200 |
| SC-02 | Runs can be created, retrieved, listed, and cancelled | Automated integration tests |
| SC-03 | Documents can be registered by GitHub ref or raw content | Integration tests covering both storage modes |
| SC-04 | Artifacts table stores metadata even without physical files | DB inspection + API response |
| SC-05 | OpenAPI schema published at `/openapi.json` | Browser/CLI retrieval |
| SC-06 | Pylint/ruff, mypy `--strict`, pytest (80% coverage) all succeed in CI | CI pipeline logs |
| SC-07 | No source file exceeds 800 lines | CI check via `scripts/check_line_length.py` |

## 4. Architectural Overview

```
┌───────────────────────────────────────────────────────────────┐
│                       FastAPI Application                     │
├───────────────────────────────────────────────────────────────┤
│ Routers (app/api)                                             │
│   runs.py    ──▶ RunService ──▶ RunRepository ──▶ DB          │
│   documents.py ─▶ DocumentService ─▶ DocumentRepository ─▶ DB │
│   artifacts.py ─▶ ArtifactService ─▶ ArtifactRepository ─▶ DB │
│                                                               │
│ Domain (app/domain)                                           │
│   models.py (Pydantic + dataclasses)                          │
│   storage_provider.py                                         │
│                                                               │
│ Infrastructure (app/infra)                                    │
│   db/session.py (SQLAlchemy 2.0 async)                        │
│   repositories/*.py                                           │
│   migrations/ (Alembic)                                       │
└───────────────────────────────────────────────────────────────┘
```

- **Domain layer** is pure Python (no FastAPI). Business rules live here.
- **Service layer** coordinates repositories and applies validation.
- **API layer** performs input parsing/output serialization only.

## 5. Data Model Specifications

### 5.1 Run

```json
{
  "run_id": "run_20251203_143022_abc",
  "project_id": "acm2",
  "title": "Initial smoke test",
  "status": "pending",         // pending | queued | running | completed | failed | cancelled
  "created_at": "2025-12-03T14:30:22Z",
  "updated_at": "2025-12-03T14:30:22Z",
  "priority": 5,                // 1 (highest) – 9 (lowest)
  "config": {
    "concurrency": {"fpf": 2, "gptr": 2},
    "eval": {"auto_run": false}
  },
  "tags": ["phase1", "api"],
  "requested_by": "morgan",
  "summary": null
}
```

**Rules**
- `run_id` generated server-side as ULID for chronological sorting.
- `status` transitions enforced (cannot jump from `pending` to `completed`).
- `config` stored as JSONB (PostgreSQL) or TEXT (SQLite) with validation via Pydantic schema.
- `tags` limited to 10 per run; each tag max length 32 characters.

### 5.2 Document

```json
{
  "document_id": "doc_intro_001",
  "display_name": "Intro to ACM",
  "source": {
    "type": "github",          // github | inline
    "repository": "YOUR_USER/ACM-Docs",
    "ref": "main",
    "path": "docs/intro.md"
  },
  "content_hash": "sha256:...",
  "metadata": {
    "mime_type": "text/markdown",
    "size_bytes": 12845
  },
  "created_at": "2025-12-03T14:31:10Z",
  "updated_at": "2025-12-03T14:31:10Z"
}
```

**Rules**
- When `type=inline`, request must include `content` field; system computes hash and writes to default storage provider.
- Unique constraint on `(source.type, source.repository, source.ref, source.path)` to prevent duplicates.
- `display_name` optional; defaults to basename of path.

### 5.3 Artifact (placeholder state)

```json
{
  "artifact_id": "art_01HFYV2M7N3C8",
  "run_id": "run_20251203_143022_abc",
  "document_id": "doc_intro_001",
  "kind": "placeholder",      // placeholder until generators integrated
  "generator": "none",
  "storage_uri": null,
  "metadata": {
    "notes": "Reserved slot for future FPF output"
  },
  "created_at": "2025-12-03T14:35:42Z"
}
```

**Rules**
- Phase 1.1 only allows creation of placeholder artifacts (used to reserve IDs).
- `storage_uri` stays null until Phase 2+ populate actual files.
- Composite index on `(run_id, document_id)` for quick lookup.

### 5.4 Task (future-proofing)

- Task records are optional in Phase 1.1 but schema must exist.
- Allow creation of `Task` objects linked to runs with `status=pending`.

## 6. Database Schema

Use Alembic migrations with naming convention `YYYYMMDD_HHMM_description`.

```sql
CREATE TABLE run (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(26) UNIQUE NOT NULL,
    project_id VARCHAR(64) NOT NULL,
    title VARCHAR(160),
    status VARCHAR(16) NOT NULL,
    priority SMALLINT DEFAULT 5 CHECK (priority BETWEEN 1 AND 9),
    config JSONB NOT NULL,
    tags TEXT[] DEFAULT '{}',
    requested_by VARCHAR(64) NOT NULL,
    summary TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE document (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(32) UNIQUE NOT NULL,
    display_name VARCHAR(160),
    source JSONB NOT NULL,
    content_hash VARCHAR(71) NOT NULL,
    metadata JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE artifact (
    id SERIAL PRIMARY KEY,
    artifact_id VARCHAR(32) UNIQUE NOT NULL,
    run_id VARCHAR(26) REFERENCES run(run_id) ON DELETE CASCADE,
    document_id VARCHAR(32) REFERENCES document(document_id) ON DELETE CASCADE,
    kind VARCHAR(32) NOT NULL,
    generator VARCHAR(32) NOT NULL,
    storage_uri TEXT,
    metadata JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE task (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(32) UNIQUE NOT NULL,
    run_id VARCHAR(26) REFERENCES run(run_id) ON DELETE CASCADE,
    task_type VARCHAR(32) NOT NULL,
    status VARCHAR(16) NOT NULL,
    retry_count SMALLINT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

SQLite fallback should replace JSONB with TEXT but maintain Pydantic validation before persistence.

## 7. API Endpoints

### 7.1 Health

- `GET /health`
  - Response: `{ "status": "ok", "service": "acm2-core", "timestamp": "ISO-8601" }`
  - Must include DB connectivity check (< 100ms).

### 7.2 Runs

| Method | Path | Description |
|--------|------|-------------|
| POST | `/runs` | Create new run |
| GET | `/runs/{run_id}` | Retrieve run details |
| GET | `/runs` | List runs with filtering |
| PATCH | `/runs/{run_id}` | Update status (cancel, change priority) |
| DELETE | `/runs/{run_id}` | Soft-delete (mark as cancelled) |

#### 7.2.1 POST /runs

Request:
```json
{
  "project_id": "acm2",
  "title": "Phase 1.1 demo",
  "config": {
    "concurrency": {"gptr": 1},
    "eval": {"auto_run": false}
  },
  "documents": ["doc_intro_001"],
  "tags": ["phase1"],
  "priority": 4,
  "requested_by": "morgan"
}
```

Validation:
- `documents` may reference existing document IDs or inline document specs.
- If inline document spec provided, create document transactionally.
- `priority` default 5; enforce integer.

Response (201): includes generated `run_id` and normalized config.

#### 7.2.2 GET /runs

Query parameters:
- `status` (multi-select)
- `project_id`
- `tag`
- `created_before`, `created_after`
- `limit` (1-100, default 20)
- `cursor` (opaque pagination token based on ULID)

Response includes `next_cursor` when more pages remain.

#### 7.2.3 PATCH /runs/{run_id}

Allowed operations (JSON Patch-style but simplified):
```json
{
  "status": "cancelled",
  "summary": "Cancelled via API by morgan",
  "priority": 3
}
```

Rules:
- Only allow status transitions: `pending|queued|running -> cancelled`.
- `completed` runs cannot be modified except `summary` field.

### 7.3 Documents

| Method | Path |
|--------|------|
| POST | `/documents` |
| GET | `/documents/{document_id}` |
| GET | `/documents` |
| PUT | `/documents/{document_id}` | (Update metadata only) |

`POST /documents` accepts either GitHub reference or inline content:

```json
{
  "display_name": "Intro",
  "source": {
    "type": "github",
    "repository": "YOUR_USER/ACM-Docs",
    "ref": "main",
    "path": "docs/intro.md"
  }
}
```

Inline example:

```json
{
  "display_name": "Draft",
  "source": {
    "type": "inline",
    "content": "# Draft document\n...",
    "mime_type": "text/markdown"
  }
}
```

Response includes computed `content_hash` and document ID.

### 7.4 Artifacts (Placeholder)

| Method | Path |
|--------|------|
| POST | `/artifacts` |
| GET | `/artifacts/{artifact_id}` |
| GET | `/runs/{run_id}/artifacts` |

`POST /artifacts` sample payload:
```json
{
  "run_id": "run_20251203_143022_abc",
  "document_id": "doc_intro_001",
  "kind": "placeholder",
  "metadata": {"notes": "reserved"}
}
```

Business rules ensure placeholder artifacts cannot be duplicated for the same `(run, document, kind)` combination.

## 8. Validation & Error Handling

- Standard error envelope:
```json
{
  "error": {
    "code": "RUN_NOT_FOUND",
    "message": "Run run_20251203_000000_xyz does not exist",
    "details": null
  }
}
```
- HTTP status mapping
  - 400 for validation errors (include field path `source.type` etc.).
  - 404 for missing resources.
  - 409 for conflicts (duplicate document, illegal status transition).
  - 500 reserved for unexpected failures (captured by Sentry/OTel).

## 9. Observability

- Integrate OpenTelemetry exporter (`app/infra/telemetry.py`).
- Emit structured logs per request with correlation ID `X-Request-ID`.
- Metrics to expose via `/metrics` (Prometheus):
  - `acm2_requests_total{path,method,status}`
  - `acm2_run_status_total{status}`
  - `acm2_db_query_duration_seconds`

## 10. Testing Strategy

| Layer | Tooling | Coverage |
|-------|---------|----------|
| Unit | pytest + pytest-asyncio | Domain models, services |
| Integration | httpx.AsyncClient + test DB | API routers |
| Contract | schemathesis (OpenAPI-based) | Edge cases & fuzz |
| Static Analysis | mypy --strict, ruff | CI gating |

Additional scripts:
- `scripts/run_tests.ps1` (Windows) / `scripts/run_tests.sh` (Unix)
- `scripts/check_line_length.py` ensures `< 800` lines rule.

## 11. Deliverables Checklist

- [ ] FastAPI app scaffold with routers, services, repositories.
- [ ] Pydantic models in `app/domain/models.py` with strict validation.
- [ ] Alembic migrations committed.
- [ ] CI pipeline (.github/workflows/api.yml) invoking tests and linters.
- [ ] Postman/OpenAPI collection for manual testing.
- [ ] ADR: `docs/adr/0001-core-api-foundation.md` (records decisions on FastAPI, SQLAlchemy).
- [ ] Developer setup guide (`docs/setup.md`) describing environment, env vars, run commands.

## 12. Timeline (Target)

| Week | Milestone |
|------|-----------|
| 1 | Project scaffold, CI pipeline, health endpoint |
| 2 | Run entity (model, API, tests) |
| 3 | Document entity + GitHub reference validation |
| 4 | Artifact placeholder endpoints, observability, cleanup |

## 13. Open Questions


2. document_id is configuarable, with varibles like "file_uuid" and "global uuid"
we retain all files possible. forever. everything ever genreated or logged must exist forever.
4.
5. Will inline documents eventually sync back to GitHub automatically? yes



## 14. Proposed Improvements & Refinements

Based on further review, the following refinements should be incorporated into the Phase 1.1 implementation plan:

### 14.1 Idempotency & Safety
- **Idempotency Keys**: Implement `Idempotency-Key` header support for `POST /runs` and `POST /documents` to prevent duplicate resource creation on network retries.
- **Rate Limiting**: Although internal-facing initially, add basic rate limiting (e.g., `slowapi`) to prevent accidental DoS from runaway scripts.

### 14.2 API Standards
- **Versioning**: Prefix all endpoints with `/api/v1` to allow for future breaking changes without disrupting existing clients.
- **Pagination**: Standardize `cursor` format (e.g., base64-encoded ULID) across all list endpoints.
- **CORS**: Configure CORS middleware to allow requests from `localhost` (for development) and the future Web GUI domain.

### 14.3 Configuration & Validation
- **Strict Config Validation**: Even though the DB stores `config` as JSONB, the application layer MUST validate it against a strict Pydantic model before persistence.
- **Environment Management**: Use `pydantic-settings` to manage configuration via `.env` files and environment variables, ensuring secrets (DB credentials, GitHub tokens) are never hardcoded.

### 14.4 Architecture
- **Dependency Injection**: Use `fastapi.Depends` for dependency injection of services and repositories. This is critical for swapping implementations during testing (e.g., using an in-memory DB or mock GitHub adapter).
- **Soft Deletion**: Clarify that "soft delete" means setting `status=cancelled` for runs. For documents, consider adding an `is_active` boolean flag rather than deleting rows, to preserve historical run integrity.

### 14.5 Developer Experience
- **Makefile / Justfile**: Provide a task runner file to standardize common commands (`make test`, `make lint`, `make run`).
- **Pre-commit Hooks**: Setup `pre-commit` to run linters and formatters automatically before commit.

