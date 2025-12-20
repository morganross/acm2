# ACM 2.0 – Phase 1.4 Initial HTTP/JSON API

## 1. Purpose

Phase 1.4 delivers the **complete HTTP/JSON API specification** for ACM 2.0, including all endpoint contracts, request/response schemas, authentication, error handling, and versioning strategy. This document serves as the authoritative reference for frontend developers, integration engineers, and automated tooling.

## 2. Scope

- Full OpenAPI 3.1 specification for all Phase 1 endpoints.
- Authentication and authorization strategy.
- Request/response schema definitions with examples.
- Error taxonomy and standard error envelope.
- Pagination, filtering, and sorting conventions.
- Webhook support for async event notifications.
- Rate limiting and quota management.
- SDK generation strategy (Python, TypeScript).

## 3. API Design Principles

### 3.1 Core Principles

| Principle | Description |
|-----------|-------------|
| **REST-ful** | Resources identified by URIs, standard HTTP verbs, stateless interactions |
| **JSON-first** | All payloads are JSON; `Content-Type: application/json` required |
| **Versioned** | All endpoints prefixed with `/api/v1/` |
| **Predictable** | Consistent naming, pagination, error formats across all endpoints |
| **Secure by Default** | All endpoints require authentication unless explicitly marked public |
| **Idempotent** | POST operations support `Idempotency-Key` header |

### 3.2 Naming Conventions

```
Resources:     plural nouns (runs, documents, artifacts, tasks)
Actions:       POST to collection or sub-resource (POST /runs/{id}/cancel)
Query params:  snake_case (created_after, page_size)
JSON fields:   snake_case (run_id, created_at, content_hash)
Headers:       Title-Case-With-Dashes (X-Request-ID, Idempotency-Key)
```

## 4. Base URL & Versioning

### 4.1 URL Structure

```
Production:    https://api.acm2.example.com/api/v1/
Staging:       https://api-staging.acm2.example.com/api/v1/
Development:   http://localhost:8000/api/v1/
```

### 4.2 Version Policy

- **v1** is the current and only supported version.
- Breaking changes require a new major version (`v2`).
- Deprecation notice: 6 months before removal.
- Version in URL path (not header) for simplicity and cacheability.

## 5. Authentication & Authorization

### 5.1 Authentication Methods

| Method | Use Case | Header |
|--------|----------|--------|
| **API Key** | Server-to-server, scripts, CI/CD | `Authorization: Bearer <api_key>` |
| **JWT (OAuth 2.0)** | Web GUI, user sessions | `Authorization: Bearer <jwt_token>` |
| **GitHub App** | GitHub-integrated workflows | `X-GitHub-Token: <installation_token>` |

### 5.2 API Key Format

```
acm2_live_<32_random_alphanumeric>
acm2_test_<32_random_alphanumeric>
```

- Live keys have full permissions.
- Test keys are sandboxed to test project only.
- Keys can be scoped (read-only, write, admin).

### 5.3 Authorization Model

```yaml
Roles:
  viewer:
    - GET /runs
    - GET /runs/{id}
    - GET /documents
    - GET /artifacts
    
  operator:
    - all viewer permissions
    - POST /runs
    - PATCH /runs/{id}
    - POST /documents
    
  admin:
    - all operator permissions
    - DELETE /runs/{id}
    - DELETE /documents/{id}
    - POST /api-keys
    - DELETE /api-keys/{id}
```

### 5.4 Unauthenticated Endpoints

```
GET  /health              # Service health check
GET  /openapi.json        # OpenAPI specification
GET  /docs                # Swagger UI (development only)
```

## 6. Common Headers

### 6.1 Request Headers

| Header | Required | Description |
|--------|----------|-------------|
| `Authorization` | Yes* | Bearer token (API key or JWT) |
| `Content-Type` | Yes | Must be `application/json` for POST/PUT/PATCH |
| `Accept` | No | Default `application/json` |
| `X-Request-ID` | No | Client-provided correlation ID (UUID recommended) |
| `Idempotency-Key` | No | For POST requests; prevents duplicate creation |
| `X-GitHub-Token` | No | GitHub installation token for GitHub-sourced documents |

### 6.2 Response Headers

| Header | Description |
|--------|-------------|
| `X-Request-ID` | Echoed from request or server-generated UUID |
| `X-RateLimit-Limit` | Requests allowed per window |
| `X-RateLimit-Remaining` | Requests remaining in current window |
| `X-RateLimit-Reset` | Unix timestamp when window resets |
| `Link` | Pagination links (RFC 5988) |

## 7. Endpoint Reference

### 7.1 Health & Meta

#### GET /health

```http
GET /api/v1/health
```

Response (200):
```json
{
  "status": "healthy",
  "service": "acm2-api",
  "version": "1.0.0",
  "timestamp": "2025-12-03T15:00:00Z",
  "checks": {
    "database": "ok",
    "storage": "ok",
    "redis": "ok"
  }
}
```

Response (503) when degraded:
```json
{
  "status": "degraded",
  "service": "acm2-api",
  "version": "1.0.0",
  "timestamp": "2025-12-03T15:00:00Z",
  "checks": {
    "database": "ok",
    "storage": "error",
    "redis": "ok"
  }
}
```

---

### 7.2 Runs

#### POST /runs

Create a new run.

```http
POST /api/v1/runs
Content-Type: application/json
Authorization: Bearer acm2_live_xxx
Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000
```

Request Body:
```json
{
  "project_id": "firstpub-platform",
  "title": "December evaluation batch",
  "config": {
    "generators": {
      "fpf": {
        "enabled": true,
        "iterations": 3,
        "models": [
          {"provider": "openai", "model": "gpt-4o"},
          {"provider": "anthropic", "model": "claude-3-5-sonnet"}
        ]
      },
      "gptr": {
        "enabled": true,
        "iterations": 2,
        "report_type": "research_report"
      }
    },
    "evaluation": {
      "auto_run": true,
      "single_doc": true,
      "pairwise": true,
      "playoffs": false
    },
    "concurrency": {
      "max_parallel_generators": 4,
      "max_parallel_evals": 2
    }
  },
  "documents": [
    "doc_intro_001",
    "doc_chapter1_002"
  ],
  "tags": ["december-batch", "evaluation"],
  "priority": 3,
  "requested_by": "morgan",
  "webhook_url": "https://hooks.example.com/acm/runs"
}
```

Response (201 Created):
```json
{
  "run_id": "run_01HGWJ8K9M2N3P4Q5R6S7T8U9V",
  "project_id": "firstpub-platform",
  "title": "December evaluation batch",
  "status": "pending",
  "config": { ... },
  "documents": ["doc_intro_001", "doc_chapter1_002"],
  "tags": ["december-batch", "evaluation"],
  "priority": 3,
  "requested_by": "morgan",
  "webhook_url": "https://hooks.example.com/acm/runs",
  "created_at": "2025-12-03T15:30:00Z",
  "updated_at": "2025-12-03T15:30:00Z",
  "links": {
    "self": "/api/v1/runs/run_01HGWJ8K9M2N3P4Q5R6S7T8U9V",
    "tasks": "/api/v1/runs/run_01HGWJ8K9M2N3P4Q5R6S7T8U9V/tasks",
    "artifacts": "/api/v1/runs/run_01HGWJ8K9M2N3P4Q5R6S7T8U9V/artifacts"
  }
}
```

#### GET /runs/{run_id}

Retrieve run details.

```http
GET /api/v1/runs/run_01HGWJ8K9M2N3P4Q5R6S7T8U9V
Authorization: Bearer acm2_live_xxx
```

Response (200):
```json
{
  "run_id": "run_01HGWJ8K9M2N3P4Q5R6S7T8U9V",
  "project_id": "firstpub-platform",
  "title": "December evaluation batch",
  "status": "running",
  "progress": {
    "total_tasks": 12,
    "completed_tasks": 5,
    "failed_tasks": 0,
    "pending_tasks": 7,
    "percent_complete": 41.67
  },
  "config": { ... },
  "documents": ["doc_intro_001", "doc_chapter1_002"],
  "tags": ["december-batch", "evaluation"],
  "priority": 3,
  "requested_by": "morgan",
  "started_at": "2025-12-03T15:30:05Z",
  "created_at": "2025-12-03T15:30:00Z",
  "updated_at": "2025-12-03T15:35:00Z",
  "links": { ... }
}
```

#### GET /runs

List runs with filtering and pagination.

```http
GET /api/v1/runs?status=running&status=pending&project_id=firstpub-platform&limit=20&cursor=xxx
Authorization: Bearer acm2_live_xxx
```

Query Parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string[] | Filter by status (multi-select) |
| `project_id` | string | Filter by project |
| `tag` | string | Filter by tag |
| `requested_by` | string | Filter by requester |
| `created_after` | ISO8601 | Created after timestamp |
| `created_before` | ISO8601 | Created before timestamp |
| `limit` | int | Page size (1-100, default 20) |
| `cursor` | string | Pagination cursor |
| `sort` | string | Sort field (created_at, updated_at, priority) |
| `order` | string | Sort order (asc, desc; default desc) |

Response (200):
```json
{
  "data": [
    { "run_id": "run_01HGWJ8K9M2N3P4Q5R6S7T8U9V", ... },
    { "run_id": "run_01HGWJ7K8L1M2N3P4Q5R6S7T8", ... }
  ],
  "pagination": {
    "total_count": 47,
    "page_size": 20,
    "has_more": true,
    "next_cursor": "eyJydW5faWQiOiJydW5fMDFIR1dKN0s4TDFNMk4zUDRRNVI2UzdUOCJ9"
  }
}
```

#### PATCH /runs/{run_id}

Update run (cancel, change priority, add summary).

```http
PATCH /api/v1/runs/run_01HGWJ8K9M2N3P4Q5R6S7T8U9V
Content-Type: application/json
Authorization: Bearer acm2_live_xxx
```

Request Body:
```json
{
  "status": "cancelled",
  "summary": "Cancelled due to config error",
  "priority": 9
}
```

Response (200): Updated run object.

#### POST /runs/{run_id}/cancel

Cancel a running or pending run.

```http
POST /api/v1/runs/run_01HGWJ8K9M2N3P4Q5R6S7T8U9V/cancel
Authorization: Bearer acm2_live_xxx
```

Request Body (optional):
```json
{
  "reason": "User requested cancellation"
}
```

Response (200):
```json
{
  "run_id": "run_01HGWJ8K9M2N3P4Q5R6S7T8U9V",
  "status": "cancelled",
  "cancelled_at": "2025-12-03T15:40:00Z",
  "cancelled_by": "morgan",
  "cancellation_reason": "User requested cancellation"
}
```

#### POST /runs/{run_id}/retry

Retry a failed run.

```http
POST /api/v1/runs/run_01HGWJ8K9M2N3P4Q5R6S7T8U9V/retry
Authorization: Bearer acm2_live_xxx
```

Request Body (optional):
```json
{
  "retry_failed_tasks_only": true
}
```

Response (201): New run object with reference to original run.

---

### 7.3 Documents

#### POST /documents

Register a document.

```http
POST /api/v1/documents
Content-Type: application/json
Authorization: Bearer acm2_live_xxx
```

**GitHub Source:**
```json
{
  "display_name": "Introduction",
  "source": {
    "type": "github",
    "repository": "YOUR_USER/firstpub-Platform",
    "ref": "main",
    "path": "docs/intro.md"
  },
  "tags": ["intro", "overview"]
}
```

**Inline Source:**
```json
{
  "display_name": "Draft Document",
  "source": {
    "type": "inline",
    "content": "# Draft\n\nThis is a draft document for testing...",
    "mime_type": "text/markdown"
  },
  "tags": ["draft"]
}
```

**Local File Source:**
```json
{
  "display_name": "Local Test",
  "source": {
    "type": "local",
    "path": "/data/documents/test.md"
  },
  "tags": ["local"]
}
```

Response (201 Created):
```json
{
  "document_id": "doc_01HGWK2M3N4P5Q6R7S8T9U0V1W",
  "display_name": "Introduction",
  "source": {
    "type": "github",
    "repository": "YOUR_USER/firstpub-Platform",
    "ref": "main",
    "path": "docs/intro.md"
  },
  "content_hash": "sha256:a1b2c3d4e5f6...",
  "metadata": {
    "mime_type": "text/markdown",
    "size_bytes": 4523,
    "line_count": 142
  },
  "tags": ["intro", "overview"],
  "created_at": "2025-12-03T15:45:00Z",
  "updated_at": "2025-12-03T15:45:00Z",
  "links": {
    "self": "/api/v1/documents/doc_01HGWK2M3N4P5Q6R7S8T9U0V1W",
    "content": "/api/v1/documents/doc_01HGWK2M3N4P5Q6R7S8T9U0V1W/content",
    "artifacts": "/api/v1/documents/doc_01HGWK2M3N4P5Q6R7S8T9U0V1W/artifacts"
  }
}
```

#### GET /documents/{document_id}

Retrieve document metadata.

```http
GET /api/v1/documents/doc_01HGWK2M3N4P5Q6R7S8T9U0V1W
Authorization: Bearer acm2_live_xxx
```

Response (200): Document object as shown above.

#### GET /documents/{document_id}/content

Retrieve raw document content.

```http
GET /api/v1/documents/doc_01HGWK2M3N4P5Q6R7S8T9U0V1W/content
Authorization: Bearer acm2_live_xxx
Accept: text/markdown
```

Response (200):
```
Content-Type: text/markdown
Content-Length: 4523

# Introduction

This document provides an overview of...
```

#### GET /documents

List documents with filtering.

Query Parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| `source_type` | string | Filter by source type (github, inline, local) |
| `repository` | string | Filter by GitHub repository |
| `tag` | string | Filter by tag |
| `content_hash` | string | Find by exact content hash |
| `limit` | int | Page size (1-100, default 20) |
| `cursor` | string | Pagination cursor |

#### PUT /documents/{document_id}

Update document metadata (not content).

```http
PUT /api/v1/documents/doc_01HGWK2M3N4P5Q6R7S8T9U0V1W
Content-Type: application/json
Authorization: Bearer acm2_live_xxx
```

Request Body:
```json
{
  "display_name": "Updated Introduction",
  "tags": ["intro", "overview", "updated"]
}
```

#### POST /documents/{document_id}/refresh

Refresh content from source (GitHub or local).

```http
POST /api/v1/documents/doc_01HGWK2M3N4P5Q6R7S8T9U0V1W/refresh
Authorization: Bearer acm2_live_xxx
```

Response (200):
```json
{
  "document_id": "doc_01HGWK2M3N4P5Q6R7S8T9U0V1W",
  "previous_hash": "sha256:a1b2c3d4e5f6...",
  "current_hash": "sha256:f6e5d4c3b2a1...",
  "changed": true,
  "refreshed_at": "2025-12-03T16:00:00Z"
}
```

---

### 7.4 Artifacts

#### GET /artifacts/{artifact_id}

Retrieve artifact metadata.

```http
GET /api/v1/artifacts/art_01HGWL3N4P5Q6R7S8T9U0V1W2X
Authorization: Bearer acm2_live_xxx
```

Response (200):
```json
{
  "artifact_id": "art_01HGWL3N4P5Q6R7S8T9U0V1W2X",
  "run_id": "run_01HGWJ8K9M2N3P4Q5R6S7T8U9V",
  "document_id": "doc_01HGWK2M3N4P5Q6R7S8T9U0V1W",
  "kind": "generated_report",
  "generator": "fpf",
  "status": "completed",
  "storage_uri": "gs://acm2-artifacts/runs/run_01.../intro.fpf.1.gpt-4o.abc.md",
  "metadata": {
    "model": "gpt-4o",
    "provider": "openai",
    "iteration": 1,
    "token_count": 2847,
    "generation_time_ms": 12340
  },
  "created_at": "2025-12-03T15:32:00Z",
  "links": {
    "self": "/api/v1/artifacts/art_01HGWL3N4P5Q6R7S8T9U0V1W2X",
    "content": "/api/v1/artifacts/art_01HGWL3N4P5Q6R7S8T9U0V1W2X/content",
    "run": "/api/v1/runs/run_01HGWJ8K9M2N3P4Q5R6S7T8U9V",
    "document": "/api/v1/documents/doc_01HGWK2M3N4P5Q6R7S8T9U0V1W"
  }
}
```

#### GET /artifacts/{artifact_id}/content

Download artifact content.

```http
GET /api/v1/artifacts/art_01HGWL3N4P5Q6R7S8T9U0V1W2X/content
Authorization: Bearer acm2_live_xxx
```

Response (200):
```
Content-Type: text/markdown
Content-Disposition: attachment; filename="intro.fpf.1.gpt-4o.abc.md"
Content-Length: 12845

# Generated Report

...
```

#### GET /runs/{run_id}/artifacts

List artifacts for a run.

```http
GET /api/v1/runs/run_01HGWJ8K9M2N3P4Q5R6S7T8U9V/artifacts?kind=generated_report&generator=fpf
Authorization: Bearer acm2_live_xxx
```

Query Parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| `kind` | string | Filter by artifact kind |
| `generator` | string | Filter by generator (fpf, gptr, eval) |
| `document_id` | string | Filter by source document |
| `status` | string | Filter by status |
| `limit` | int | Page size |
| `cursor` | string | Pagination cursor |

Response (200):
```json
{
  "data": [
    { "artifact_id": "art_01HGWL3N4P5Q6R7S8T9U0V1W2X", ... },
    { "artifact_id": "art_01HGWL4P5Q6R7S8T9U0V1W2X3Y", ... }
  ],
  "pagination": { ... }
}
```

#### GET /documents/{document_id}/artifacts

List all artifacts generated from a document (across all runs).

---

### 7.5 Tasks

#### GET /runs/{run_id}/tasks

List tasks for a run.

```http
GET /api/v1/runs/run_01HGWJ8K9M2N3P4Q5R6S7T8U9V/tasks
Authorization: Bearer acm2_live_xxx
```

Response (200):
```json
{
  "data": [
    {
      "task_id": "task_01HGWM4P5Q6R7S8T9U0V1W2X3Y",
      "run_id": "run_01HGWJ8K9M2N3P4Q5R6S7T8U9V",
      "task_type": "generate_fpf",
      "status": "completed",
      "document_id": "doc_01HGWK2M3N4P5Q6R7S8T9U0V1W",
      "config": {
        "provider": "openai",
        "model": "gpt-4o",
        "iteration": 1
      },
      "retry_count": 0,
      "started_at": "2025-12-03T15:30:10Z",
      "completed_at": "2025-12-03T15:30:45Z",
      "duration_ms": 35000,
      "artifacts": ["art_01HGWL3N4P5Q6R7S8T9U0V1W2X"]
    }
  ],
  "pagination": { ... }
}
```

#### GET /tasks/{task_id}

Retrieve task details including logs.

```http
GET /api/v1/tasks/task_01HGWM4P5Q6R7S8T9U0V1W2X3Y?include=logs
Authorization: Bearer acm2_live_xxx
```

Response (200):
```json
{
  "task_id": "task_01HGWM4P5Q6R7S8T9U0V1W2X3Y",
  "run_id": "run_01HGWJ8K9M2N3P4Q5R6S7T8U9V",
  "task_type": "generate_fpf",
  "status": "completed",
  "logs": [
    {"timestamp": "2025-12-03T15:30:10Z", "level": "INFO", "message": "Starting FPF generation..."},
    {"timestamp": "2025-12-03T15:30:45Z", "level": "INFO", "message": "Generation completed successfully"}
  ],
  ...
}
```

#### POST /tasks/{task_id}/retry

Retry a failed task.

```http
POST /api/v1/tasks/task_01HGWM4P5Q6R7S8T9U0V1W2X3Y/retry
Authorization: Bearer acm2_live_xxx
```

---

### 7.6 Evaluations

#### GET /runs/{run_id}/evaluation

Get evaluation results for a run.

```http
GET /api/v1/runs/run_01HGWJ8K9M2N3P4Q5R6S7T8U9V/evaluation
Authorization: Bearer acm2_live_xxx
```

Response (200):
```json
{
  "run_id": "run_01HGWJ8K9M2N3P4Q5R6S7T8U9V",
  "evaluation_status": "completed",
  "single_doc_results": {
    "artifact_count": 6,
    "dimensions_evaluated": ["accuracy", "completeness", "clarity", "relevance"],
    "average_scores": {
      "accuracy": 4.2,
      "completeness": 3.8,
      "clarity": 4.5,
      "relevance": 4.1
    }
  },
  "pairwise_results": {
    "comparisons_made": 15,
    "elo_rankings": [
      {"artifact_id": "art_01...", "elo_rating": 1623, "rank": 1},
      {"artifact_id": "art_02...", "elo_rating": 1578, "rank": 2},
      {"artifact_id": "art_03...", "elo_rating": 1512, "rank": 3}
    ]
  },
  "winner": {
    "artifact_id": "art_01HGWL3N4P5Q6R7S8T9U0V1W2X",
    "selection_method": "elo_ranking",
    "elo_rating": 1623
  },
  "links": {
    "report_html": "/api/v1/runs/run_01.../evaluation/report",
    "report_csv": "/api/v1/runs/run_01.../evaluation/export?format=csv",
    "database": "/api/v1/runs/run_01.../evaluation/export?format=sqlite"
  }
}
```

#### GET /runs/{run_id}/evaluation/report

Get HTML evaluation report.

```http
GET /api/v1/runs/run_01HGWJ8K9M2N3P4Q5R6S7T8U9V/evaluation/report
Authorization: Bearer acm2_live_xxx
Accept: text/html
```

#### GET /runs/{run_id}/evaluation/export

Export evaluation data.

```http
GET /api/v1/runs/run_01HGWJ8K9M2N3P4Q5R6S7T8U9V/evaluation/export?format=csv
Authorization: Bearer acm2_live_xxx
```

Query Parameters:
- `format`: csv, sqlite, json

---

## 8. Error Handling

### 8.1 Standard Error Envelope

All errors return a consistent JSON structure:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      {
        "field": "config.generators.fpf.iterations",
        "message": "Must be between 1 and 10",
        "value": 15
      }
    ],
    "request_id": "req_01HGWN5Q6R7S8T9U0V1W2X3Y4Z",
    "timestamp": "2025-12-03T16:00:00Z",
    "documentation_url": "https://docs.acm2.example.com/errors/VALIDATION_ERROR"
  }
}
```

### 8.2 Error Codes

| HTTP Status | Error Code | Description |
|-------------|------------|-------------|
| 400 | `VALIDATION_ERROR` | Request body or parameters invalid |
| 400 | `INVALID_CONFIG` | Run configuration invalid |
| 401 | `UNAUTHORIZED` | Missing or invalid authentication |
| 403 | `FORBIDDEN` | Insufficient permissions |
| 404 | `NOT_FOUND` | Resource does not exist |
| 404 | `RUN_NOT_FOUND` | Specific run not found |
| 404 | `DOCUMENT_NOT_FOUND` | Specific document not found |
| 404 | `ARTIFACT_NOT_FOUND` | Specific artifact not found |
| 409 | `CONFLICT` | Resource conflict (duplicate, illegal state transition) |
| 409 | `DUPLICATE_DOCUMENT` | Document with same source already exists |
| 409 | `INVALID_STATUS_TRANSITION` | Cannot transition run/task to requested status |
| 422 | `UNPROCESSABLE_ENTITY` | Request understood but cannot be processed |
| 429 | `RATE_LIMITED` | Too many requests |
| 500 | `INTERNAL_ERROR` | Unexpected server error |
| 502 | `UPSTREAM_ERROR` | Error from GitHub API or generator |
| 503 | `SERVICE_UNAVAILABLE` | Service temporarily unavailable |

### 8.3 Retry Guidance

Response headers indicate retry behavior:

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 30
X-RateLimit-Reset: 1701619200
```

```http
HTTP/1.1 503 Service Unavailable
Retry-After: 60
```

## 9. Rate Limiting

### 9.1 Default Limits

| Tier | Requests/minute | Requests/hour | Concurrent runs |
|------|-----------------|---------------|-----------------|
| Free | 60 | 1,000 | 2 |
| Standard | 300 | 10,000 | 10 |
| Enterprise | 1,000 | 50,000 | 50 |

### 9.2 Rate Limit Headers

```http
X-RateLimit-Limit: 300
X-RateLimit-Remaining: 247
X-RateLimit-Reset: 1701619200
```

### 9.3 Endpoint-Specific Limits

| Endpoint | Additional Limit |
|----------|------------------|
| `POST /runs` | 10/minute (prevents queue flooding) |
| `POST /documents` | 50/minute |
| `GET /artifacts/{id}/content` | 100/minute (bandwidth protection) |

## 10. Webhooks

### 10.1 Webhook Events

| Event | Trigger |
|-------|---------|
| `run.created` | New run created |
| `run.started` | Run execution started |
| `run.completed` | Run finished successfully |
| `run.failed` | Run failed |
| `run.cancelled` | Run was cancelled |
| `task.completed` | Individual task completed |
| `task.failed` | Individual task failed |
| `artifact.created` | New artifact generated |
| `evaluation.completed` | Evaluation finished |

### 10.2 Webhook Payload

```json
{
  "event": "run.completed",
  "timestamp": "2025-12-03T16:30:00Z",
  "data": {
    "run_id": "run_01HGWJ8K9M2N3P4Q5R6S7T8U9V",
    "status": "completed",
    "artifacts_count": 12,
    "winner_artifact_id": "art_01HGWL3N4P5Q6R7S8T9U0V1W2X"
  },
  "links": {
    "run": "https://api.acm2.example.com/api/v1/runs/run_01HGWJ8K9M2N3P4Q5R6S7T8U9V"
  }
}
```

### 10.3 Webhook Security

- Webhooks include `X-ACM2-Signature` header (HMAC-SHA256).
- Webhook secret configured per project.
- Retry policy: 3 attempts with exponential backoff (1s, 5s, 30s).

## 11. SDK Generation

### 11.1 Generated SDKs

| Language | Generator | Package Name |
|----------|-----------|--------------|
| Python | openapi-python-client | `acm2-client` |
| TypeScript | openapi-typescript-codegen | `@acm2/client` |

### 11.2 SDK Features

- Full type hints / TypeScript types.
- Automatic retry with exponential backoff.
- Pagination helpers (async iterators).
- Webhook signature verification utilities.

### 11.3 Python SDK Example

```python
from acm2_client import ACM2Client, RunConfig

client = ACM2Client(api_key="acm2_live_xxx")

# Create a run
run = await client.runs.create(
    project_id="firstpub-platform",
    title="API test",
    documents=["doc_intro_001"],
    config=RunConfig(
        generators={"fpf": {"enabled": True, "iterations": 2}}
    )
)

# Wait for completion
run = await client.runs.wait_for_completion(run.run_id, timeout=3600)

# Get winner
evaluation = await client.runs.get_evaluation(run.run_id)
print(f"Winner: {evaluation.winner.artifact_id}")
```

## 12. OpenAPI Specification Location

Full OpenAPI 3.1 specification available at:

- **Runtime**: `GET /openapi.json`
- **Repository**: `acm2/openapi/acm2-api-v1.yaml`
- **Documentation**: `GET /docs` (Swagger UI, development only)
- **ReDoc**: `GET /redoc` (alternative documentation UI)

## 13. Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-12-03 | Initial API specification |

## 14. Open Questions

1. Should artifact content be streamed for large files, or always served via signed URLs?
2. Do we need a bulk document registration endpoint (`POST /documents/batch`)?
3. Should webhook delivery be configurable per event type?
4. What's the maximum inline document size before requiring GitHub/local source?
5. Do we need real-time progress via WebSocket in addition to polling and webhooks?
