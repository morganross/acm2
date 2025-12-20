# ACM 2.0 – Step 2.8: Storage Provider Abstraction

**Status:** Draft  
**Author:** Development Team  
**Last Updated:** 2025-12-04

> **Platform:** Windows, Linux, macOS. Python + SQLite. No Docker.
> **Dependency:** This step builds on Step 2.7 (Run/Document Lifecycle) and Step 1.5 (Storage and Database).  
> **Document Type:** Implementation specification for the code writer. Code samples are illustrative, not copy-paste ready.

---

## Table of Contents

1. [Purpose](#1-purpose)
2. [Scope](#2-scope)
3. [Prerequisites](#3-prerequisites)
4. [Interface Definition](#4-interface-definition)
5. [GitHub Implementation](#5-github-implementation)
6. [Local Filesystem Implementation](#6-local-filesystem-implementation)
7. [Factory and Configuration](#7-factory-and-configuration)
8. [Integration with Run/Document APIs](#8-integration-with-rundocument-apis)
9. [Caching Strategy](#9-caching-strategy)
10. [Rate Limiting](#10-rate-limiting)
11. [Error Handling](#11-error-handling)
12. [Skip Logic Support](#12-skip-logic-support)
13. [Batch Operations](#13-batch-operations)
14. [Tests](#14-tests)
15. [Success Criteria](#15-success-criteria)
16. [File Structure](#16-file-structure)
17. [Next Steps](#17-next-steps)

---

## 1. Purpose

Step 2.8 introduces the **StorageProvider abstraction** that decouples ACM 2.0's file operations from any specific storage backend.

### Goals

| Goal | Description |
|------|-------------|
| **Backend Independence** | Switch between GitHub, local filesystem, or future providers (S3, Azure Blob) without changing application code |
| **Testability** | Use local filesystem or in-memory mocks for fast, offline testing |
| **Consistent API** | Single interface for read, write, delete, list, and hash operations |
| **Batch Efficiency** | Atomic multi-file commits to GitHub via Git Data API |
| **Skip Logic Support** | Content-addressable hashing for intelligent skip decisions |

### Deliverables

1. `StorageProvider` abstract base class with async methods
2. `GitHubStorageProvider` — Production implementation
3. `LocalStorageProvider` — Development/testing implementation
4. Factory function for provider instantiation
5. Integration with Run and Document services from Step 2.7

### Why This Matters

Without this abstraction, GitHub API calls would be scattered throughout the codebase. The StorageProvider centralizes file operations, enables testing without network calls, and allows future storage backends.

---

## 2. Scope

### 2.1 In Scope

| Item | Description |
|------|-------------|
| `StorageProvider` ABC | Abstract base class with all required methods |
| `GitHubStorageProvider` | GitHub implementation with Contents API and Git Data API |
| `LocalStorageProvider` | Windows filesystem implementation |
| Data classes | `StorageFile`, `StorageCommit`, `StorageError` |
| Factory function | `create_storage_provider(config)` |
| Caching layer | TTL cache for GitHub reads |
| Rate limiting | Respect GitHub API limits (5000/hour authenticated) |
| Retry logic | Exponential backoff for transient failures |
| Content hashing | SHA-256 and Git blob SHA |
| Batch writes | Multi-file atomic commits |

### 2.2 Out of Scope

| Item | Reason |
|------|--------|
| S3/Azure Blob providers | Future step |
| Git LFS support | Not needed for markdown/text |
| Webhook handlers | Separate concern |
| Branch management | All writes to configured branch |
| Pull request creation | Future feature |

### 2.3 Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Async-only interface | `async def` methods | Consistency with FastAPI |
| Path format | Forward slashes | Normalized internally |
| Hash algorithm | SHA-256 + Git blob SHA | Skip logic compatibility |
| Error hierarchy | Custom exceptions | Type-safe handling |

---

## 3. Prerequisites

### 3.1 Required Dependencies

Add to `pyproject.toml`:

| Package | Version | Purpose |
|---------|---------|---------|
| httpx | >=0.26.0 | Async HTTP client for GitHub API |
| cachetools | >=5.3.0 | TTL cache for reads |
| tenacity | >=8.2.0 | Retry logic |
| aiofiles | >=23.2.0 | Async file I/O |

### 3.2 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ACM2_GITHUB_TOKEN` | Yes (for GitHub) | Personal Access Token |
| `ACM2_STORAGE_PROVIDER` | No | `github` (default) or `local` |
| `ACM2_LOCAL_STORAGE_ROOT` | For local | Root path, e.g., `C:\acm2\storage` |

### 3.3 GitHub Token Scopes

For Personal Access Token (classic): `repo` scope

For Fine-Grained Token:
- Contents: Read and write
- Metadata: Read-only

---

## 4. Interface Definition

### 4.0 Path Normalization

All paths must be normalized to use forward slashes (`/`), regardless of the OS.

**Rules:**
- Input paths: Convert `\` to `/`.
- Storage paths: Always stored with `/`.
- Output paths: Always returned with `/`.

**Helper:**
```python
# app/core/paths.py
import os
from pathlib import Path

class PathUtils:
    @staticmethod
    def normalize(path: str | Path) -> str:
        """Convert path to POSIX style (forward slashes)."""
        return str(path).replace(os.sep, "/").replace("\\", "/")
```

**Action Required:** Use `PathUtils.normalize()` in all StorageProvider methods.

### 4.1 Data Classes

The code writer should create the following data classes in `app/infra/storage/types.py`:

#### StorageFile

Represents a file read from storage.

| Field | Type | Description |
|-------|------|-------------|
| `path` | str | Relative path (forward slashes) |
| `content` | bytes | File content |
| `sha` | str \| None | Content hash (Git blob SHA or SHA-256) |
| `size` | int \| None | Size in bytes |
| `encoding` | str | `utf-8` or `base64` |
| `last_modified` | datetime \| None | Modification time if available |

**Methods to implement:**
- `content_text` property: Decode content as UTF-8

#### StorageCommit

Represents result of a write operation.

| Field | Type | Description |
|-------|------|-------------|
| `sha` | str | Commit SHA or operation ID |
| `message` | str | Commit message |
| `author` | str | Author name |
| `timestamp` | datetime | When committed |
| `files` | list[str] | Affected file paths |

#### StorageFileInfo

Lightweight metadata (no content). Used for list operations.

| Field | Type | Description |
|-------|------|-------------|
| `path` | str | Relative path |
| `sha` | str \| None | Content hash |
| `size` | int | Size in bytes |
| `is_directory` | bool | True if directory |

#### StorageError

Exception class for storage errors.

| Field | Type | Description |
|-------|------|-------------|
| `code` | StorageErrorCode | Error type enum |
| `message` | str | Human-readable message |
| `path` | str \| None | File path if applicable |
| `details` | dict \| None | Extra error info |

**Error codes to define:**
- `NOT_FOUND` — File does not exist
- `ALREADY_EXISTS` — File exists (when overwrite=False)
- `PERMISSION_DENIED` — No access
- `RATE_LIMITED` — API rate limit hit
- `NETWORK_ERROR` — Connection failed
- `INVALID_PATH` — Bad path format
- `CONTENT_TOO_LARGE` — Exceeds size limit
- `CONFLICT` — SHA mismatch on update

### 4.2 StorageProvider Abstract Base Class

Create `app/infra/storage/provider.py` with an ABC defining these methods:

#### Read Operations

| Method | Signature | Description |
|--------|-----------|-------------|
| `read_file` | `async def read_file(path: str) -> StorageFile` | Read file content and metadata |
| `read_file_if_exists` | `async def read_file_if_exists(path: str) -> StorageFile \| None` | Read or return None |
| `file_exists` | `async def file_exists(path: str) -> bool` | Check existence |
| `get_file_info` | `async def get_file_info(path: str) -> StorageFileInfo` | Metadata without content |
| `get_file_hash` | `async def get_file_hash(path: str) -> str` | Get content hash |

**Behavior notes:**
- `read_file` raises `StorageError(NOT_FOUND)` if file missing
- `read_file_if_exists` catches NOT_FOUND and returns None
- `get_file_hash` returns prefixed hash: `git:abc123` or `sha256:abc123`

#### Write Operations

| Method | Signature | Description |
|--------|-----------|-------------|
| `write_file` | `async def write_file(path, content, message, *, overwrite=True, expected_sha=None) -> StorageCommit` | Write bytes |
| `write_file_text` | `async def write_file_text(path, content, message, *, encoding='utf-8', overwrite=True) -> StorageCommit` | Write string |
| `delete_file` | `async def delete_file(path, message) -> StorageCommit` | Delete file |

**Behavior notes:**
- `overwrite=False` raises `ALREADY_EXISTS` if file exists
- `expected_sha` enables optimistic locking: raises `CONFLICT` if SHA doesn't match
- `delete_file` raises `NOT_FOUND` if file missing

#### List Operations

| Method | Signature | Description |
|--------|-----------|-------------|
| `list_files` | `async def list_files(path_prefix='', *, recursive=False) -> list[StorageFileInfo]` | List directory |
| `list_files_glob` | `async def list_files_glob(pattern: str) -> list[StorageFileInfo]` | Glob pattern match |

**Behavior notes:**
- `list_files` returns empty list for non-existent directory
- `list_files_glob` supports `*`, `**`, `?` patterns
- Both return `StorageFileInfo` (not full content)

#### Batch Operations

| Method | Signature | Description |
|--------|-----------|-------------|
| `write_files_batch` | `async def write_files_batch(files: list[tuple[str, bytes]], message) -> StorageCommit` | Atomic multi-write |
| `delete_files_batch` | `async def delete_files_batch(paths: list[str], message) -> StorageCommit` | Atomic multi-delete |

**Behavior notes:**
- GitHub: Single commit with all files (truly atomic)
- Local: Best-effort (write all, not atomic)

#### Utility Operations

| Method | Signature | Description |
|--------|-----------|-------------|
| `compute_hash` | `async def compute_hash(content: bytes) -> str` | Hash without writing |
| `health_check` | `async def health_check() -> bool` | Verify connectivity |
| `close` | `async def close() -> None` | Clean up resources |

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `provider_name` | str | `"github"` or `"local"` |
| `capabilities` | StorageCapability | Feature flags |

**Capability flags to define:**
- `ATOMIC_BATCH_WRITE` — Batch writes are truly atomic
- `VERSIONING` — File history available
- `CONTENT_HASH_NATIVE` — Hash computed by storage
- `RATE_LIMITED` — Subject to rate limits

---

## 5. GitHub Implementation

Create `app/infra/storage/github_provider.py` implementing `StorageProvider`.

### 5.1 Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `repository` | str | required | `"owner/repo"` format |
| `base_path` | str | `""` | Path prefix, e.g., `"runs/"` |
| `branch` | str | `"main"` | Target branch |
| `token` | str \| None | None | GitHub PAT |
| `cache_ttl` | int | 300 | Cache TTL seconds |
| `cache_maxsize` | int | 1000 | Max cache entries |
| `timeout` | float | 30.0 | HTTP timeout |

### 5.2 Internal State

- HTTP client: Use `httpx.AsyncClient`, lazy-initialize, reuse for connection pooling
- Cache: Use `cachetools.TTLCache` with async lock
- Rate limit tracking: Store remaining count and reset time from response headers

### 5.3 GitHub API Endpoints

| Operation | API | Notes |
|-----------|-----|-------|
| Read file | `GET /repos/{owner}/{repo}/contents/{path}?ref={branch}` | Returns base64 content |
| Write file | `PUT /repos/{owner}/{repo}/contents/{path}` | Requires SHA for update |
| Delete file | `DELETE /repos/{owner}/{repo}/contents/{path}` | Requires SHA |
| List directory | `GET /repos/{owner}/{repo}/contents/{path}` | Returns array |
| Batch write | Git Data API (blobs + trees + commits) | See Section 13 |

### 5.4 Implementation Requirements

**Path handling:**
- Prepend `base_path` to all paths
- Normalize: strip leading `/`, convert `\` to `/`

**Authentication:**
- Send token in `Authorization: Bearer {token}` header
- Also set `X-GitHub-Api-Version: 2022-11-28`

**Content encoding:**
- GitHub returns base64-encoded content
- Decode on read, encode on write
- Detect binary vs text by attempting UTF-8 decode

**Rate limiting:**
- Read `X-RateLimit-Remaining` and `X-RateLimit-Reset` from response headers
- Before each request, check if limit exceeded
- If exceeded, raise `StorageError(RATE_LIMITED)` with reset time

**Caching:**
- Cache read results by `{path}:{branch}` key
- Invalidate on write/delete
- Use async lock for thread safety

**Retry logic:**
- Retry on `httpx.NetworkError` (connection issues)
- Use exponential backoff: 1s, 2s, 4s (max 3 attempts)
- Do NOT retry on 4xx errors (client errors)

**Error mapping:**

| HTTP Status | StorageError Code |
|-------------|-------------------|
| 404 | NOT_FOUND |
| 403 (rate limit) | RATE_LIMITED |
| 403 (other) | PERMISSION_DENIED |
| 409 | CONFLICT |
| 422 | INVALID_PATH |
| 5xx | NETWORK_ERROR |

### 5.5 Capabilities

Return: `ATOMIC_BATCH_WRITE | VERSIONING | CONTENT_HASH_NATIVE | RATE_LIMITED`

---

## 6. Local Filesystem Implementation

Create `app/infra/storage/local_provider.py` implementing `StorageProvider`.

### 6.1 Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `root_path` | str | required | Root directory, e.g., `C:\acm2\storage` |
| `create_root` | bool | True | Create root if missing |

### 6.2 Implementation Requirements

**Path handling:**
- All paths relative to `root_path`
- Convert forward slashes to OS path separator
- Reject paths with `..` (directory traversal)

**File operations:**
- Use `aiofiles` for async I/O
- Create parent directories automatically on write
- Use `pathlib.Path` for path manipulation

**Hash computation:**
- Compute SHA-256 of content
- Return as `sha256:{hex_digest}`

**Glob support:**
- Use `pathlib.Path.glob()` for pattern matching
- Convert glob pattern to Windows-compatible

**Commit simulation:**
- Generate ULID for commit SHA
- Return current timestamp
- Track affected files in commit

### 6.3 Error Mapping

| Condition | StorageError Code |
|-----------|-------------------|
| File not found | NOT_FOUND |
| Permission denied | PERMISSION_DENIED |
| Path traversal (`..`) | INVALID_PATH |
| Disk full | INTERNAL_ERROR |

### 6.4 Capabilities

Return: `SUPPORTS_GLOB` only (no atomic batch, no versioning)

---

## 7. Factory and Configuration

### 7.1 Settings Class

Add to `app/config.py` a `StorageSettings` class with:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `provider` | str | `"github"` | Provider type |
| `github_token` | str \| None | None | PAT for GitHub |
| `github_default_repo` | str \| None | None | Default repository |
| `github_default_branch` | str | `"main"` | Default branch |
| `local_root` | str | `"./storage"` | Root for local provider |

### 7.2 Factory Function

Create `app/infra/storage/factory.py` with function:

```
create_storage_provider(settings: StorageSettings) -> StorageProvider
```

Logic:
- If `settings.provider == "github"`: return `GitHubStorageProvider`
- If `settings.provider == "local"`: return `LocalStorageProvider`
- Otherwise: raise `ValueError`

### 7.3 Dependency Injection

Create FastAPI dependency `get_storage_provider()` that:
- Returns singleton provider for production
- Returns fresh provider for tests
- Handles cleanup on shutdown

---

## 8. Integration with Run/Document APIs

### 8.1 Document Registration

When a document is attached to a run (`POST /runs/{run_id}/documents`):

1. If source is GitHub path:
   - Call `StorageProvider.file_exists()` to verify file exists
   - Call `StorageProvider.get_file_hash()` to get content hash
   - Store hash in `document.content_hash` for skip logic

2. If source is inline content:
   - Call `StorageProvider.compute_hash()` on content
   - Call `StorageProvider.write_file()` to save to default repo
   - Update document with GitHub path

### 8.2 Document Content Retrieval

When content is needed (e.g., for generation):

1. Call `StorageProvider.read_file()` with GitHub path
2. Return content from `StorageFile.content`

### 8.3 Artifact Storage

When artifacts are created (Step 3+):

1. Call `StorageProvider.write_file()` to save to outputs repo
2. For batch: call `write_files_batch()` for atomic commit
3. Store GitHub path in artifact record

---

## 9. Caching Strategy

### 9.1 What to Cache

| Operation | Cache? | Reason |
|-----------|--------|--------|
| `read_file` | Yes | Files rarely change during a run |
| `file_exists` | No | Need fresh check |
| `get_file_info` | Yes | Metadata stable |
| `list_files` | No | Directory contents may change |

### 9.2 Cache Configuration

- Default TTL: 300 seconds (5 minutes)
- Max entries: 1000
- Key format: `read:{full_path}:{branch}`

### 9.3 Cache Invalidation

Invalidate on:
- `write_file` — Remove cached entry for that path
- `delete_file` — Remove cached entry
- `write_files_batch` — Remove all affected paths
- Manual `invalidate_cache(prefix)` call

---

## 10. Rate Limiting

### 10.1 GitHub Limits

| Authentication | Limit |
|----------------|-------|
| Authenticated (PAT) | 5,000/hour |
| Unauthenticated | 60/hour |
| With conditional requests (ETags) | Not counted |

### 10.2 Implementation

1. Track rate limit from response headers:
   - `X-RateLimit-Remaining`
   - `X-RateLimit-Reset` (Unix timestamp)

2. Before each request:
   - Check if remaining <= 0 and reset time is future
   - If so, raise `StorageError(RATE_LIMITED)` with details

3. Include reset time in error for caller to handle

### 10.3 Future Enhancement

Consider adding internal rate limiting (e.g., 10 requests/second) to avoid bursts. Use `asyncio.Semaphore` or similar.

---

## 11. Error Handling

### 11.1 Error Hierarchy

All storage errors should use `StorageError` exception with appropriate code.

### 11.2 Retry Policy

| Error Type | Retry? | Strategy |
|------------|--------|----------|
| Network error | Yes | Exponential backoff, max 3 |
| Rate limited | No | Caller decides |
| Not found | No | Permanent |
| Permission denied | No | Permanent |
| Conflict | No | Caller must handle |

### 11.3 Logging

Log all errors with:
- Error code
- Path (if applicable)
- Provider name
- Request ID (from context)

---

## 12. Skip Logic Support

### 12.1 Content Hash Format

- GitHub: `git:{blob_sha}` (40 hex chars)
- Local/computed: `sha256:{hash}` (64 hex chars)

### 12.2 Hash Comparison

Hashes from different providers are NOT directly comparable:
- Git blob SHA uses `blob {size}\0{content}` prefix
- SHA-256 is raw content

For skip logic, compare:
- Same provider: Direct comparison
- Cross-provider: Recompute hash using target algorithm

### 12.3 Integration Points

| Location | Action |
|----------|--------|
| Document attachment | Compute and store `content_hash` |
| Run start | Check if document hash matches existing artifacts |
| Artifact lookup | Query by `content_hash` for matching outputs |

---

## 13. Batch Operations

### 13.1 GitHub Git Data API

For atomic multi-file commits, use these endpoints in sequence:

1. **Get base commit**: `GET /repos/{owner}/{repo}/git/ref/heads/{branch}`
2. **Create blobs**: `POST /repos/{owner}/{repo}/git/blobs` (one per file)
3. **Create tree**: `POST /repos/{owner}/{repo}/git/trees` (with all blob SHAs)
4. **Create commit**: `POST /repos/{owner}/{repo}/git/commits`
5. **Update ref**: `PATCH /repos/{owner}/{repo}/git/refs/heads/{branch}`

### 13.2 Performance

| Method | Files | Estimated Time |
|--------|-------|----------------|
| Individual writes | 10 | ~20 seconds (10 commits) |
| Batch write | 10 | ~3 seconds (1 commit) |

Recommendation: Use batch for 3+ files.

### 13.3 Error Handling

If any step fails in batch:
- Blobs already created are orphaned (GitHub cleans up)
- Tree/commit not created
- Raise error with partial progress details

---

## 14. Tests

### 14.1 Unit Tests

Test with mock HTTP responses (httpx mock):

| Test | Description |
|------|-------------|
| `test_read_file_success` | Mock 200 response, verify content decoded |
| `test_read_file_not_found` | Mock 404, verify StorageError raised |
| `test_write_file_new` | Mock 201 response |
| `test_write_file_update` | Mock existing file, then 200 |
| `test_rate_limit_error` | Mock 403 with rate limit message |
| `test_cache_hit` | Read twice, verify one HTTP call |

### 14.2 Integration Tests

Test with real GitHub (use test repo):

| Test | Description |
|------|-------------|
| `test_roundtrip` | Write file, read back, verify content |
| `test_list_files` | Create files, list, verify all returned |
| `test_batch_write` | Write 5 files, verify single commit |

### 14.3 Local Provider Tests

| Test | Description |
|------|-------------|
| `test_read_write_local` | Basic roundtrip |
| `test_path_traversal_blocked` | Verify `..` rejected |
| `test_auto_create_directory` | Write to nested path |

---

## 15. Success Criteria

### 15.1 Functional Requirements

- [ ] `GitHubStorageProvider` passes all unit tests
- [ ] `LocalStorageProvider` passes all unit tests
- [ ] Factory creates correct provider based on config
- [ ] Integration tests pass with real GitHub
- [ ] Rate limiting prevents 429 errors
- [ ] Cache reduces redundant API calls by 50%+

### 15.2 Non-Functional Requirements

- [ ] Read operations complete in < 500ms (cached: < 5ms)
- [ ] Write operations complete in < 2s
- [ ] Batch write (10 files) completes in < 5s
- [ ] No resource leaks (HTTP clients closed)

### 15.3 Integration Requirements

- [ ] Document attachment uses provider for verification
- [ ] Content hash populated on document registration
- [ ] Provider injected via FastAPI dependency

---

## 16. File Structure

```
app/
├── infra/
│   └── storage/
│       ├── __init__.py              # Export public API
│       ├── types.py                 # StorageFile, StorageCommit, StorageError, enums
│       ├── provider.py              # StorageProvider ABC
│       ├── github_provider.py       # GitHubStorageProvider
│       ├── local_provider.py        # LocalStorageProvider
│       └── factory.py               # create_storage_provider()
tests/
├── unit/
│   └── storage/
│       ├── test_github_provider.py
│       └── test_local_provider.py
└── integration/
    └── test_storage_integration.py
```

---

## 17. Next Steps

After Step 2.8 is complete:

1. **Step 3.9 (FPF Adapter)**: Use StorageProvider to read documents and write artifacts
2. **Step 3.9 (GPT-R Adapter)**: Same pattern for GPT-Researcher integration
3. **Step 2.9 (Task Queue)**: Background jobs use provider for file operations
4. **Step 4 (Web GUI)**: Frontend calls API, which uses provider internally
