# ACM 2.0 – Step 9: FPF Adapter Integration

**Status:** Draft  
**Author:** Development Team  
**Last Updated:** 2025-12-04

> **Platform:** Windows, Linux, macOS. Python + SQLite. No Docker.
> **Dependency:** This step builds on Step 7 (Run/Document Lifecycle) and Step 8 (StorageProvider).  
> **Document Type:** Implementation specification for the code writer. Code samples are illustrative, not copy-paste ready.

---

## Table of Contents

1. [Purpose](#1-purpose)
2. [Scope](#2-scope)
3. [Prerequisites](#3-prerequisites)
4. [FPF Adapter Interface](#4-fpf-adapter-interface)
5. [FPF Configuration](#5-fpf-configuration)
6. [Execution Flow](#6-execution-flow)
7. [Background Job Integration](#7-background-job-integration)
8. [Result Handling](#8-result-handling)
9. [Artifact Storage](#9-artifact-storage)
10. [Database Integration](#10-database-integration)
11. [Skip Logic](#11-skip-logic)
12. [Error Handling](#12-error-handling)
13. [Retry Logic](#13-retry-logic)
14. [Concurrency Control](#14-concurrency-control)
15. [Logging Integration](#15-logging-integration)
16. [API Endpoints](#16-api-endpoints)
17. [Tests](#17-tests)
18. [Success Criteria](#18-success-criteria)
19. [File Structure](#19-file-structure)
20. [Next Steps](#20-next-steps)

---

## 1. Purpose

Step 9 integrates **FilePromptForge (FPF)** as the primary document generation adapter in ACM 2.0.

### Why an Adapter?

FPF is an external tool that ACM 2.0 invokes to generate reports from source documents. The adapter pattern provides:

| Benefit | Description |
|---------|-------------|
| **Isolation** | FPF subprocess management, environment, and output parsing contained in one module |
| **Testability** | Mock the adapter for fast unit tests without invoking real LLM calls |
| **Replaceability** | Same interface for FPF and GPT-R adapters (Step 16) |
| **Error Boundaries** | FPF failures don't crash the API server |
| **Configuration** | Centralized model/provider settings per generator |

### What FPF Does

FPF takes a source document (markdown) and generates a processed report using LLM providers:

```
Input:  Source document (e.g., executive order text)
        + Instructions file (how to process)
        + Guidelines file (style rules)
        
Output: Generated report (markdown)
        + Metadata (model used, tokens, duration)
```

### Deliverables

1. `FpfAdapter` class with async `generate()` method
2. `FpfConfig` data class for adapter configuration
3. `FpfResult` data class for generation results
4. Integration with Run/Document lifecycle (Step 7)
5. Artifact storage via StorageProvider (Step 8)
6. API endpoint to trigger FPF generation
7. Background execution with progress tracking

---

## 2. Scope

### 2.1 In Scope

| Item | Description |
|------|-------------|
| FPF adapter class | Wraps FPF invocation with clean async interface |
| Subprocess management | Start, monitor, terminate FPF processes |
| Output parsing | Extract generated content and metadata from FPF output |
| Configuration | Model, provider, iterations, temperature settings |
| Result storage | Save artifacts via StorageProvider |
| Database records | Create `Artifact` records linked to Run/Document |
| Skip logic check | Query existing artifacts before generation |
| Error handling | Catch FPF failures, report to caller |
| Retry logic | Retry transient failures (rate limits, network) |
| Concurrency limits | Max simultaneous FPF processes |
| Progress reporting | Status updates during generation |
| API endpoints | Trigger and monitor FPF generation |

### 2.2 Out of Scope

| Item | Reason |
|------|--------|
| FPF internal changes | FPF is external; adapter only wraps it |
| GPT-R adapter | Covered in Step 16 |
| Evaluation | Covered in Steps 18-20 |
| Combine phase | Covered in Step 17 |
| Web GUI changes | GUI calls API; no direct adapter access |

### 2.3 Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Invocation method | **Subprocess** | FPF is a separate Python process with its own dependencies |
| Communication | **Stdout/file output** | FPF writes results to files; adapter reads them |
| Async model | **asyncio subprocess** | Non-blocking; integrates with FastAPI |
| Result format | **Markdown + JSON metadata** | Consistent with ACM 1.0 artifacts |
| Concurrency | **Semaphore-limited** | Prevent resource exhaustion |

---

## 3. Prerequisites

### 3.1 Required Dependencies

Already in `pyproject.toml` from previous steps:

| Package | Version | Purpose |
|---------|---------|---------|
| `asyncio` | stdlib | Subprocess management |
| `structlog` | >=23.2.0 | Structured logging |
| `tenacity` | >=8.2.0 | Retry logic |
| `pydantic` | >=2.0.0 | Configuration validation |

### 3.2 FPF Installation

FPF must be installed and accessible. The adapter needs:

| Requirement | Description |
|-------------|-------------|
| FPF location | Path to FPF installation (e.g., `C:\dev\silky\api_cost_multiplier\FilePromptForge`) |
| **FPF Version** | **Pinned Commit Hash** (e.g., `git checkout <hash>`) to prevent config drift |
| Python environment | FPF's venv or the shared ACM venv |
| Environment variables | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc. |
| Instructions file | Default instructions template |
| Guidelines file | Default style guidelines |

**Action Required:** Add a startup check in `FpfAdapter.__init__` to verify FPF version/commit matches expected value.

### 3.3 Completed Steps

| Step | Provides | Used By FPF Adapter |
|------|----------|---------------------|
| **Step 7** | `Run`, `Document`, `RunDocument` models | Adapter reads document info, updates status |
| **Step 8** | `StorageProvider` | Adapter reads source docs, writes artifacts |

### 3.4 Configuration Requirements

The code writer should ensure these settings are available in `app/config.py`:

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `fpf_path` | str | Required | Path to FPF installation |
| `fpf_python` | str | `python` | Python executable for FPF |
| `fpf_timeout` | int | 600 | Max seconds per document |
| `fpf_max_concurrent` | int | 2 | Max parallel FPF processes |
| `fpf_default_provider` | str | `openai` | Default LLM provider |
| `fpf_default_model` | str | `gpt-4o` | Default model |
| `fpf_instructions_file` | str | None | Path to instructions template |
| `fpf_guidelines_file` | str | None | Path to guidelines file |

---

## 4. FPF Adapter Interface

### 4.1 Base Generator Adapter

The code writer should create an abstract base class that both FPF and GPT-R adapters will implement:

**File:** `app/adapters/base.py`

| Method | Signature | Description |
|--------|-----------|-------------|
| `generate` | `async def generate(document: Document, config: GeneratorConfig) -> GeneratorResult` | Generate artifact from document |
| `validate_config` | `def validate_config(config: GeneratorConfig) -> None` | Raise if config invalid |
| `health_check` | `async def health_check() -> bool` | Verify adapter is operational |

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `name` | str | Adapter identifier (e.g., `"fpf"`, `"gptr"`) |
| `supports_iterations` | bool | Whether adapter supports multiple iterations |
| `max_concurrent` | int | Concurrent execution limit |

### 4.2 FpfAdapter Class

**File:** `app/adapters/fpf/adapter.py`

The `FpfAdapter` class implements the base interface:

| Method | Description |
|--------|-------------|
| `__init__(settings: FpfSettings)` | Initialize with FPF path, timeout, concurrency settings |
| `generate(document, config)` | Main entry point — returns `FpfResult` |
| `_build_command(document, config)` | Construct FPF CLI command |
| `_run_subprocess(command)` | Execute FPF and capture output |
| `_parse_output(stdout, stderr, output_path)` | Extract result from FPF output |
| `_cleanup(temp_files)` | Remove temporary files |

**Concurrency:** The adapter should maintain an `asyncio.Semaphore` initialized to `max_concurrent` (default 2). Each `generate()` call acquires the semaphore before spawning a subprocess.

### 4.3 FpfResult Data Class

**File:** `app/adapters/fpf/result.py`

The result object returned by `generate()`:

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether generation succeeded |
| `content` | str \| None | Generated markdown content |
| `content_hash` | str \| None | SHA-256 of content |
| `error` | str \| None | Error message if failed |
| `error_code` | str \| None | Error classification (e.g., `TIMEOUT`, `RATE_LIMITED`) |
| `metadata` | FpfMetadata | Execution metadata |

**FpfMetadata fields:**

| Field | Type | Description |
|-------|------|-------------|
| `provider` | str | LLM provider used |
| `model` | str | Model used |
| `iteration` | int | Which iteration (1-based) |
| `input_tokens` | int \| None | Tokens in prompt |
| `output_tokens` | int \| None | Tokens in response |
| `duration_seconds` | float | Execution time |
| `fpf_version` | str \| None | FPF version string |
| `timestamp` | datetime | When generation completed |

### 4.4 Error Types

The adapter should define specific error types for different failure modes:

| Error Class | When Raised |
|-------------|-------------|
| `FpfTimeoutError` | Process exceeded timeout |
| `FpfProcessError` | Non-zero exit code |
| `FpfOutputError` | Could not parse output |
| `FpfRateLimitError` | LLM rate limit hit |
| `FpfAuthError` | API key invalid/missing |
| `FpfConfigError` | Invalid configuration |

---

## 5. FPF Configuration

### 5.1 FpfSettings (Application-Level)

**File:** `app/adapters/fpf/config.py`

Settings from environment/config file — apply to all FPF invocations:

| Setting | Type | Env Var | Description |
|---------|------|---------|-------------|
| `fpf_path` | Path | `ACM2_FPF_PATH` | FPF installation directory |
| `fpf_python` | str | `ACM2_FPF_PYTHON` | Python executable (default: `python`) |
| `fpf_timeout` | int | `ACM2_FPF_TIMEOUT` | Max seconds per document (default: 600) |
| `fpf_max_concurrent` | int | `ACM2_FPF_MAX_CONCURRENT` | Parallel limit (default: 2) |
| `fpf_output_dir` | Path | `ACM2_FPF_OUTPUT_DIR` | Temp output location |

### 5.2 FpfGeneratorConfig (Per-Invocation)

Configuration passed to `generate()` — can vary per run or per document:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `provider` | str | `"openai"` | LLM provider |
| `model` | str | `"gpt-4o"` | Model identifier |
| `iteration` | int | 1 | Which iteration (1-N) |
| `temperature` | float | 0.7 | LLM temperature |
| `max_tokens` | int \| None | None | Max output tokens |
| `instructions_file` | str \| None | None | Override instructions |
| `guidelines_file` | str \| None | None | Override guidelines |
| `extra_args` | dict | {} | Additional FPF CLI args |

### 5.3 Configuration Hierarchy

Configuration merges from multiple sources (later overrides earlier):

```
1. Application defaults (FpfSettings)
       ↓
2. Run-level config (run.config.generators[])
       ↓
3. Document-level override (if specified)
       ↓
4. Final FpfGeneratorConfig
```

**Example:** A run might specify `model: "gpt-4o-mini"` for all documents, but one document could override to `model: "gpt-4o"` for higher quality.

### 5.4 Config Hash

For skip logic, the adapter should compute a deterministic hash of the configuration:

| Included in Hash | Excluded from Hash |
|------------------|-------------------|
| provider | timeout |
| model | max_concurrent |
| iteration | output_dir |
| temperature | |
| instructions_file content hash | |
| guidelines_file content hash | |

**Format:** `config_hash = sha256(canonical_json(config_fields))`

The config hash is stored with artifacts to enable skip logic: same document + same config = skip.

---

## 6. Execution Flow

### 6.1 High-Level Sequence

```
API Request (POST /runs/{id}/generate)
    │
    ▼
┌─────────────────────────────────────────────────┐
│ 1. Validate run exists and is in valid state    │
│ 2. Get documents attached to run                │
│ 3. For each document (with concurrency limit):  │
│    a. Check skip logic                          │
│    b. If skip: mark as skipped, continue        │
│    c. Acquire semaphore                         │
│    d. Call FpfAdapter.generate()                │
│    e. Store artifact via StorageProvider        │
│    f. Update database records                   │
│    g. Release semaphore                         │
│ 4. Update run status (completed/failed/partial) │
└─────────────────────────────────────────────────┘
    │
    ▼
API Response (generation task ID or results)
```

### 6.2 Detailed Steps

#### Step 1: Pre-Generation Validation

Before starting generation, validate:

| Check | Action if Failed |
|-------|------------------|
| Run exists | Return 404 |
| Run status is `pending` or `running` | Return 409 (conflict) |
| Run has attached documents | Return 400 (no documents) |
| FPF adapter is healthy | Return 503 (service unavailable) |

#### Step 2: Document Retrieval

For each document in the run:

1. Get document metadata from database
2. Fetch document content via `StorageProvider.read_file()`
3. Compute content hash if not already set
4. Update document record with content hash

#### Step 3: Skip Logic Check

Before generating, check if artifact already exists:

```
Query: SELECT * FROM artifacts 
       WHERE document_id = ? 
       AND content_hash = ? 
       AND config_hash = ?
       AND generator = 'fpf'
```

| Result | Action |
|--------|--------|
| Matching artifact exists | Mark document as `skipped`, reuse artifact |
| No match | Proceed with generation |
| Force flag set | Proceed regardless |

#### Step 4: FPF Subprocess Execution

The adapter builds and executes an FPF command:

**Command construction:**

```
{python} -m fpf generate \
    --input {temp_input_file} \
    --output {temp_output_file} \
    --provider {provider} \
    --model {model} \
    --instructions {instructions_file} \
    --guidelines {guidelines_file} \
    [--temperature {temp}] \
    [--max-tokens {max}]
```

**Execution:**

1. Write document content to temp input file
2. Start subprocess with `asyncio.create_subprocess_exec()`
3. Set timeout alarm
4. Capture stdout/stderr
5. Wait for completion or timeout
6. Read output file if process succeeded

#### Step 5: Output Processing

After subprocess completes:

| Exit Code | Action |
|-----------|--------|
| 0 | Parse output file, extract content and metadata |
| Non-zero | Parse stderr for error classification |
| Timeout | Kill process, return `FpfTimeoutError` |

**Output file format** (FPF writes JSON):

```json
{
  "content": "# Generated Report\n\n...",
  "metadata": {
    "provider": "openai",
    "model": "gpt-4o",
    "input_tokens": 1234,
    "output_tokens": 5678,
    "duration_ms": 12345
  }
}
```

#### Step 6: Artifact Storage

On successful generation:

1. Compute content hash: `sha256(content.encode('utf-8'))`
2. Determine artifact path: `{outputs_repo}/runs/{run_id}/artifacts/{document_id}/{generator}_{iteration}.md`
3. Write via `StorageProvider.write_file()`
4. Create `Artifact` database record

#### Step 7: Status Updates

After each document:

| Outcome | Document Status | Run Status |
|---------|-----------------|------------|
| Success | `completed` | stays `running` |
| Skipped | `skipped` | stays `running` |
| Failed (retryable) | `pending` (retry) | stays `running` |
| Failed (permanent) | `failed` | stays `running` |
| All done, all success | — | `completed` |
| All done, any failed | — | `partial_failure` |
| All failed | — | `failed` |

### 6.3 Concurrency Model

Documents are processed with bounded concurrency:

```python
# Pseudocode
semaphore = asyncio.Semaphore(max_concurrent)  # e.g., 2

async def process_document(doc):
    async with semaphore:
        result = await fpf_adapter.generate(doc, config)
        await store_artifact(result)
        
# Process all documents concurrently (limited by semaphore)
await asyncio.gather(*[process_document(d) for d in documents])
```

This allows 2 FPF subprocesses to run simultaneously while others wait.

---

## 7. Background Job Integration

### 7.1 Synchronous vs Asynchronous Execution

Generation can run in two modes:

| Mode | When Used | Behavior |
|------|-----------|----------|
| **Synchronous** | Single document, short timeout | API waits, returns result directly |
| **Asynchronous** | Multiple documents, long runs | API returns task ID, client polls for status |

**Recommendation:** Default to asynchronous for runs with >1 document or any document expected to take >30 seconds.

### 7.2 In-Process Async Model

Since ACM 2.0 is single-user, use in-process async rather than external task queue:

```
POST /runs/{id}/generate
    │
    ▼
┌─────────────────────────────────────┐
│ Create GenerationTask record        │
│ Start asyncio.create_task()         │
│ Return task_id immediately          │
└─────────────────────────────────────┘
    │
    ▼ (background)
┌─────────────────────────────────────┐
│ Process documents with semaphore    │
│ Update task progress in database    │
│ Handle errors/retries               │
│ Mark task complete when done        │
└─────────────────────────────────────┘
```

### 7.3 Task Tracking

**GenerationTask record fields:**

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | ULID | Unique task identifier |
| `run_id` | ULID | Associated run |
| `status` | enum | `pending`, `running`, `completed`, `failed`, `cancelled` |
| `progress` | int | 0-100 percentage |
| `current_document` | str \| None | Document being processed |
| `documents_total` | int | Total documents to process |
| `documents_completed` | int | Successfully processed |
| `documents_skipped` | int | Skipped via skip logic |
| `documents_failed` | int | Failed to process |
| `started_at` | datetime | When task started |
| `completed_at` | datetime \| None | When task finished |
| `error` | str \| None | Error message if failed |

### 7.4 Progress Callbacks

The adapter should accept a progress callback:

```python
# Pseudocode
async def on_progress(event: ProgressEvent):
    """Called by adapter during generation."""
    await update_task_progress(task_id, event)
    
result = await fpf_adapter.generate(
    document=doc,
    config=config,
    on_progress=on_progress
)
```

**ProgressEvent types:**

| Event | Description |
|-------|-------------|
| `STARTED` | Document generation started |
| `LLM_CALL_START` | Making LLM API call |
| `LLM_CALL_COMPLETE` | LLM returned response |
| `WRITING_OUTPUT` | Writing artifact to storage |
| `COMPLETED` | Document finished successfully |
| `FAILED` | Document failed |
| `SKIPPED` | Document skipped via skip logic |

### 7.5 Cancellation Support

Cancellation uses cooperative checking:

1. Client calls `POST /runs/{id}/generate/cancel`
2. Server sets `task.status = 'cancelling'` and `cancellation_event.set()`
3. Adapter checks `cancellation_event` between documents
4. If set: stop processing, mark remaining as `cancelled`
5. Running subprocess: send SIGTERM, wait briefly, then SIGKILL

**Cancellation behavior:**

| State | Action |
|-------|--------|
| Document in progress | Let it finish, don't start next |
| Subprocess running | Terminate subprocess |
| Between documents | Stop immediately |

---

## 8. Result Handling

### 8.1 Success Results

When FPF completes successfully, `FpfResult` contains:

| Field | Value |
|-------|-------|
| `success` | `True` |
| `content` | Generated markdown string |
| `content_hash` | SHA-256 of content |
| `error` | `None` |
| `metadata` | Populated FpfMetadata |

### 8.2 Failure Results

When FPF fails, `FpfResult` contains:

| Field | Value |
|-------|-------|
| `success` | `False` |
| `content` | `None` (or partial if available) |
| `content_hash` | `None` |
| `error` | Human-readable error message |
| `error_code` | Classification (see Section 12) |
| `metadata` | Partial metadata if available |

### 8.3 Partial Results

On timeout or interrupt, attempt to salvage partial output:

| Scenario | Behavior |
|----------|----------|
| Timeout with output file | Read partial content, mark as `partial` |
| Timeout, no output | Return failure with timeout error |
| Process killed | Check for output, salvage if present |

### 8.4 Metadata Extraction

FPF output includes metadata that should be captured:

| Source | Extracted Fields |
|--------|------------------|
| FPF JSON output | `input_tokens`, `output_tokens`, `duration_ms` |
| Process timing | `duration_seconds` (wall clock) |
| Config used | `provider`, `model`, `temperature` |
| System info | `fpf_version`, `timestamp` |

---

## 9. Artifact Storage

### 9.1 Storage Location

Artifacts are stored via StorageProvider to the outputs repository:

**Path pattern:**
```
{outputs_repo}/runs/{run_id}/artifacts/{document_slug}/{generator}_{iteration}.md
```

**Example:**
```
myorg/acm-outputs/runs/01HGWJ.../artifacts/eo-2024-001/fpf_1.md
myorg/acm-outputs/runs/01HGWJ.../artifacts/eo-2024-001/fpf_2.md
myorg/acm-outputs/runs/01HGWJ.../artifacts/eo-2024-001/gptr_1.md
```

### 9.2 Document Slug

Generate URL-safe slug from document:

| Input | Slug |
|-------|------|
| `Executive Order 2024-001.md` | `executive-order-2024-001` |
| `docs/policy/eo_2024_001.md` | `eo-2024-001` |
| ULID fallback | `01HGWJ...` (first 12 chars) |

### 9.3 Artifact Metadata File

Alongside the artifact, store a metadata JSON:

**Path:** `{artifact_path}.meta.json`

```json
{
  "artifact_id": "01HGWJ...",
  "document_id": "01HGXYZ...",
  "run_id": "01HGABC...",
  "generator": "fpf",
  "iteration": 1,
  "content_hash": "sha256:abc123...",
  "config_hash": "sha256:def456...",
  "created_at": "2025-12-04T12:00:00Z",
  "metadata": {
    "provider": "openai",
    "model": "gpt-4o",
    "input_tokens": 1234,
    "output_tokens": 5678,
    "duration_seconds": 45.2
  }
}
```

### 9.4 StorageProvider Usage

```python
# Pseudocode for artifact storage
async def store_artifact(result: FpfResult, run_id: str, doc: Document):
    artifact_path = f"runs/{run_id}/artifacts/{doc.slug}/fpf_{result.metadata.iteration}.md"
    meta_path = f"{artifact_path}.meta.json"
    
    # Write content
    await storage_provider.write_file(
        path=artifact_path,
        content=result.content.encode('utf-8'),
        message=f"Add FPF artifact for {doc.display_name}"
    )
    
    # Write metadata
    await storage_provider.write_file(
        path=meta_path,
        content=json.dumps(metadata).encode('utf-8'),
        message=f"Add metadata for {doc.display_name}"
    )
```

---

## 10. Database Integration

### 10.1 Artifact Table Schema

**Table:** `artifacts`

| Column | Type | Description |
|--------|------|-------------|
| `artifact_id` | TEXT PK | ULID |
| `tenant_id` | TEXT | Multi-tenant support |
| `run_id` | TEXT FK | References runs |
| `document_id` | TEXT FK | References documents |
| `generator` | TEXT | `fpf`, `gptr`, `combine` |
| `iteration` | INTEGER | 1-N |
| `storage_path` | TEXT | Path in StorageProvider |
| `content_hash` | TEXT | SHA-256 of content |
| `config_hash` | TEXT | Hash of generation config |
| `status` | TEXT | `pending`, `completed`, `failed` |
| `metadata` | TEXT | JSON blob |
| `created_at` | TEXT | ISO timestamp |
| `updated_at` | TEXT | ISO timestamp |

**Indexes:**
- `(run_id, document_id, generator, iteration)` — unique constraint
- `(document_id, content_hash, config_hash)` — skip logic lookup
- `(run_id, status)` — listing artifacts by run

### 10.2 Artifact Repository

**File:** `app/infra/db/repositories/artifact_repository.py`

| Method | Description |
|--------|-------------|
| `create(artifact: Artifact)` | Insert new artifact |
| `get_by_id(artifact_id)` | Fetch by ID |
| `get_for_run(run_id)` | List all artifacts for a run |
| `get_for_document(document_id)` | List artifacts for a document |
| `find_existing(document_id, content_hash, config_hash, generator)` | Skip logic query |
| `update_status(artifact_id, status)` | Update status |

### 10.3 Status Updates During Generation

The generation service should update database records at each stage:

| Event | Database Update |
|-------|-----------------|
| Generation starts | `run.status = 'running'`, `run.started_at = now()` |
| Document starts | `run_documents.status = 'processing'` |
| Document completes | `run_documents.status = 'completed'`, create artifact record |
| Document skipped | `run_documents.status = 'skipped'` |
| Document fails | `run_documents.status = 'failed'`, `run_documents.error = msg` |
| All done | `run.status = final_status`, `run.completed_at = now()` |

---

## 11. Skip Logic

### 11.1 Skip Logic Purpose

Avoid redundant LLM calls when:
- Same document content
- Same generation configuration
- Artifact already exists

**Cost savings:** Skip logic can reduce API costs by 50-90% on re-runs.

### 11.2 Skip Conditions

Generation is skipped when ALL of these match:

| Field | Must Match |
|-------|------------|
| `document_id` | Same document |
| `content_hash` | Document content unchanged |
| `config_hash` | Generation config unchanged |
| `generator` | Same generator (fpf) |
| `iteration` | Same iteration number |

### 11.3 Content Hash Computation

Computed when document is first read:

```python
content_hash = "sha256:" + hashlib.sha256(content.encode('utf-8')).hexdigest()
```

### 11.4 Config Hash Computation

Computed from generation-affecting settings only:

```python
config_for_hash = {
    "provider": config.provider,
    "model": config.model,
    "temperature": config.temperature,
    "instructions_hash": hash_file(config.instructions_file),
    "guidelines_hash": hash_file(config.guidelines_file),
}
# Sort keys for determinism
config_hash = "sha256:" + hashlib.sha256(
    json.dumps(config_for_hash, sort_keys=True).encode()
).hexdigest()
```

### 11.5 Force Regeneration

Override skip logic when explicitly requested:

```http
POST /runs/{id}/generate?force=true
```

Or per-document:
```json
{
  "documents": ["01HGWJ..."],
  "force": true
}
```

### 11.6 Skip Logic Query

```python
# Pseudocode
async def should_skip(doc: Document, config: FpfGeneratorConfig) -> Artifact | None:
    existing = await artifact_repo.find_existing(
        document_id=doc.document_id,
        content_hash=doc.content_hash,
        config_hash=compute_config_hash(config),
        generator="fpf"
    )
    return existing  # None if should generate, Artifact if should skip
```

---

## 12. Error Handling

### 12.1 Error Classification

| Error Code | Description | Retryable |
|------------|-------------|-----------|
| `TIMEOUT` | Process exceeded timeout | Yes (once) |
| `RATE_LIMITED` | LLM API rate limit | Yes |
| `NETWORK_ERROR` | Connection failed | Yes |
| `AUTH_ERROR` | Invalid API key | No |
| `INVALID_CONFIG` | Bad configuration | No |
| `INVALID_OUTPUT` | Could not parse FPF output | No |
| `PROCESS_ERROR` | FPF crashed | Maybe |
| `CANCELLED` | User cancelled | No |
| `UNKNOWN` | Unclassified error | No |

### 12.2 Error Detection

Parse FPF stderr and exit code to classify errors:

| Signal | Error Code |
|--------|------------|
| Exit code 1 + "rate limit" in stderr | `RATE_LIMITED` |
| Exit code 1 + "401" or "unauthorized" | `AUTH_ERROR` |
| Exit code 1 + "timeout" | `TIMEOUT` |
| Exit code 1 + "connection" | `NETWORK_ERROR` |
| Process killed by timeout | `TIMEOUT` |
| Exit code != 0, unrecognized | `PROCESS_ERROR` |
| Output file missing or unparseable | `INVALID_OUTPUT` |

### 12.3 Error Response Format

Errors are captured in `FpfResult` and propagated to API:

```json
{
  "success": false,
  "error": "Rate limit exceeded for model gpt-4o",
  "error_code": "RATE_LIMITED",
  "retryable": true,
  "retry_after_seconds": 60
}
```

### 12.4 Error Logging

All errors logged with context:

```python
log.error(
    "fpf_generation_failed",
    run_id=run_id,
    document_id=doc.document_id,
    error_code=result.error_code,
    error=result.error,
    duration_seconds=result.metadata.duration_seconds,
)
```

---

## 13. Retry Logic

### 13.1 Retry Policy

| Error Code | Max Retries | Backoff |
|------------|-------------|---------|
| `RATE_LIMITED` | 3 | Exponential: 60s, 120s, 240s |
| `NETWORK_ERROR` | 3 | Exponential: 5s, 15s, 45s |
| `TIMEOUT` | 1 | No backoff |
| `PROCESS_ERROR` | 1 | 10s delay |
| Others | 0 | Not retried |

### 13.2 Backoff Strategy

Use `tenacity` library for retry logic:

```python
# Pseudocode
@retry(
    retry=retry_if_exception_type(RetryableError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=5, max=300),
    before_sleep=log_retry_attempt,
)
async def generate_with_retry(doc, config):
    result = await fpf_adapter.generate(doc, config)
    if not result.success and result.retryable:
        raise RetryableError(result.error_code, result.error)
    return result
```

### 13.3 Retry State Tracking

Track retries in task metadata:

| Field | Description |
|-------|-------------|
| `retry_count` | Current retry attempt (0-based) |
| `max_retries` | Maximum allowed |
| `last_error` | Most recent error |
| `next_retry_at` | When next retry will occur |

### 13.4 Circuit Breaker

If many documents fail with same error, stop early:

| Condition | Action |
|-----------|--------|
| 3+ consecutive `AUTH_ERROR` | Abort run, likely bad API key |
| 5+ consecutive `RATE_LIMITED` | Pause 5 minutes, then resume |
| 50% failure rate after 10 docs | Mark run as `failed` |

---

## 14. Concurrency Control

### 14.1 Why Limit Concurrency?

| Reason | Concern |
|--------|---------|
| **Resource usage** | Each FPF subprocess uses memory and CPU |
| **API rate limits** | LLM providers limit requests per minute |
| **Cost control** | Prevent runaway API spend |
| **System stability** | Too many processes can crash Windows |

### 14.2 Semaphore-Based Limiting

```python
# In FpfAdapter.__init__
self._semaphore = asyncio.Semaphore(settings.fpf_max_concurrent)

# In FpfAdapter.generate
async def generate(self, doc, config):
    async with self._semaphore:
        return await self._do_generate(doc, config)
```

### 14.3 Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `fpf_max_concurrent` | 2 | Max simultaneous FPF processes |
| `gptr_max_concurrent` | 2 | Max simultaneous GPT-R processes |
| `global_max_concurrent` | 4 | Total across all generators |

### 14.4 Queue Behavior

When semaphore is full:

| Behavior | Description |
|----------|-------------|
| Wait | New requests wait until slot available |
| FIFO | First-come, first-served ordering |
| Timeout | Optional timeout to prevent indefinite wait |
| Cancellation | Waiting tasks can be cancelled |

### 14.5 Per-Provider Limits

Optional: limit by LLM provider to respect their rate limits:

```python
# Pseudocode
provider_semaphores = {
    "openai": asyncio.Semaphore(3),
    "anthropic": asyncio.Semaphore(2),
    "google": asyncio.Semaphore(2),
}

async def generate(self, doc, config):
    async with self._semaphore:  # Global limit
        async with provider_semaphores[config.provider]:  # Per-provider
            return await self._do_generate(doc, config)
```

---

## 15. Logging Integration

### 15.1 Structured Log Fields

All FPF adapter logs should include:

| Field | Description |
|-------|-------------|
| `run_id` | Associated run |
| `document_id` | Document being processed |
| `generator` | Always `"fpf"` |
| `iteration` | Iteration number |
| `task_id` | Generation task ID |

### 15.2 Log Events

| Event | Level | When |
|-------|-------|------|
| `fpf_generation_started` | INFO | Document generation begins |
| `fpf_subprocess_started` | DEBUG | FPF process spawned |
| `fpf_subprocess_output` | DEBUG | Stdout/stderr lines (if verbose) |
| `fpf_generation_completed` | INFO | Success with duration, tokens |
| `fpf_generation_skipped` | INFO | Skip logic triggered |
| `fpf_generation_failed` | ERROR | Failure with error details |
| `fpf_generation_retrying` | WARN | Retry attempt starting |
| `fpf_generation_cancelled` | WARN | User cancelled |

### 15.3 Example Log Output

```json
{
  "event": "fpf_generation_completed",
  "level": "info",
  "timestamp": "2025-12-04T12:00:00Z",
  "run_id": "01HGWJ...",
  "document_id": "01HGXYZ...",
  "generator": "fpf",
  "iteration": 1,
  "task_id": "01HGABC...",
  "provider": "openai",
  "model": "gpt-4o",
  "input_tokens": 1234,
  "output_tokens": 5678,
  "duration_seconds": 45.2,
  "artifact_id": "01HGDEF..."
}
```

### 15.4 FPF Stdout/Stderr Capture

Capture subprocess output for debugging:

| Output | Handling |
|--------|----------|
| stdout | Log at DEBUG level, parse for progress |
| stderr | Log at DEBUG level, scan for errors |
| Combined | Store in task record for inspection |

**Truncation:** If output exceeds 10KB, truncate and note in log.

### 15.5 Correlation

All logs for a single generation task share:
- `task_id` — unique per generation request
- `run_id` — links to run
- `request_id` — from original API request (if available)

---

## 16. API Endpoints

### 16.1 Trigger Generation

**Endpoint:** `POST /api/v1/runs/{run_id}/generate`

**Request Body:**
```json
{
  "generator": "fpf",
  "config": {
    "provider": "openai",
    "model": "gpt-4o",
    "iterations": 2
  },
  "documents": ["01HGWJ...", "01HGXYZ..."],
  "force": false
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `generator` | str | Required | `"fpf"` or `"gptr"` |
| `config` | object | Run config | Override generation config |
| `documents` | list | All | Specific documents to generate |
| `force` | bool | false | Skip skip-logic |

**Response (202 Accepted):**
```json
{
  "task_id": "01HGABC...",
  "status": "pending",
  "documents_total": 5,
  "message": "Generation started"
}
```

### 16.2 Check Progress

**Endpoint:** `GET /api/v1/runs/{run_id}/generate/status`

**Response:**
```json
{
  "task_id": "01HGABC...",
  "status": "running",
  "progress": 40,
  "current_document": "Executive Order 2024-001",
  "documents_total": 5,
  "documents_completed": 2,
  "documents_skipped": 0,
  "documents_failed": 0,
  "started_at": "2025-12-04T12:00:00Z",
  "estimated_completion": "2025-12-04T12:05:00Z"
}
```

**Status values:**
- `pending` — Queued, not started
- `running` — In progress
- `completed` — All documents processed
- `failed` — Generation failed
- `cancelled` — User cancelled
- `partial_failure` — Some documents failed

### 16.3 Cancel Generation

**Endpoint:** `POST /api/v1/runs/{run_id}/generate/cancel`

**Response (200 OK):**
```json
{
  "task_id": "01HGABC...",
  "status": "cancelling",
  "message": "Cancellation requested"
}
```

**Note:** Cancellation is asynchronous. Poll status to confirm `cancelled`.

### 16.4 List Artifacts

**Endpoint:** `GET /api/v1/runs/{run_id}/artifacts`

**Query Parameters:**
- `generator` — Filter by generator (fpf, gptr)
- `document_id` — Filter by document
- `status` — Filter by status

**Response:**
```json
{
  "artifacts": [
    {
      "artifact_id": "01HGDEF...",
      "document_id": "01HGWJ...",
      "generator": "fpf",
      "iteration": 1,
      "status": "completed",
      "storage_path": "runs/01HGABC.../artifacts/eo-2024-001/fpf_1.md",
      "content_hash": "sha256:abc123...",
      "created_at": "2025-12-04T12:00:00Z",
      "metadata": {
        "provider": "openai",
        "model": "gpt-4o",
        "input_tokens": 1234,
        "output_tokens": 5678
      }
    }
  ],
  "total": 1
}
```

### 16.5 Get Artifact Content

**Endpoint:** `GET /api/v1/artifacts/{artifact_id}/content`

**Response:** Raw markdown content with appropriate Content-Type header.

---

## 17. Tests

### 17.1 Unit Tests

**File:** `tests/unit/adapters/fpf/test_adapter.py`

| Test | Description |
|------|-------------|
| `test_generate_success` | Mock subprocess returns valid output |
| `test_generate_timeout` | Process exceeds timeout, verify cleanup |
| `test_generate_rate_limited` | Mock rate limit error, verify retry |
| `test_generate_auth_error` | Invalid API key, verify no retry |
| `test_config_hash_deterministic` | Same config → same hash |
| `test_skip_logic_match` | Existing artifact found → skip |
| `test_skip_logic_force` | Force flag bypasses skip |
| `test_concurrency_limit` | Semaphore blocks excess requests |
| `test_cancellation` | Cancel mid-generation |

### 17.2 Integration Tests

**File:** `tests/integration/test_fpf_adapter.py`

| Test | Description |
|------|-------------|
| `test_end_to_end_generation` | Real FPF call (use cheap model) |
| `test_artifact_stored` | Verify artifact in StorageProvider |
| `test_database_records` | Verify artifact and status in DB |
| `test_multiple_documents` | Process 3 docs concurrently |
| `test_skip_on_rerun` | Second run skips unchanged docs |

### 17.3 Mock FPF

For unit tests, create a mock FPF script:

**File:** `tests/fixtures/mock_fpf.py`

```python
# Pseudocode
# Simulates FPF behavior for testing

if args.fail:
    print("Error: simulated failure", file=sys.stderr)
    sys.exit(1)
    
if args.slow:
    time.sleep(args.delay)
    
output = {
    "content": "# Mock Generated Report\n\nThis is mock content.",
    "metadata": {"provider": "mock", "model": "mock-1", ...}
}
write_json(args.output, output)
```

### 17.4 Test Fixtures

**File:** `tests/conftest.py`

| Fixture | Description |
|---------|-------------|
| `fpf_adapter` | Configured FpfAdapter instance |
| `mock_storage` | In-memory StorageProvider |
| `sample_document` | Document with test content |
| `sample_config` | FpfGeneratorConfig with test values |

---

## 18. Success Criteria

### 18.1 Functional Requirements

- [ ] `FpfAdapter.generate()` produces valid `FpfResult`
- [ ] Artifacts stored via StorageProvider to correct path
- [ ] Artifact database records created with correct metadata
- [ ] Skip logic prevents redundant generation
- [ ] Force flag bypasses skip logic
- [ ] Multiple iterations generate separate artifacts
- [ ] Concurrency limited by semaphore
- [ ] Cancellation stops in-flight generation
- [ ] Errors classified and reported correctly
- [ ] Retries work for transient failures

### 18.2 API Requirements

- [ ] `POST /runs/{id}/generate` returns 202 with task_id
- [ ] `GET /runs/{id}/generate/status` returns accurate progress
- [ ] `POST /runs/{id}/generate/cancel` initiates cancellation
- [ ] `GET /runs/{id}/artifacts` lists generated artifacts
- [ ] `GET /artifacts/{id}/content` returns artifact content

### 18.3 Quality Requirements

- [ ] Unit test coverage ≥80% for adapter code
- [ ] Integration tests pass with real FPF (CI environment)
- [ ] No subprocess leaks (all processes cleaned up)
- [ ] Structured logs for all operations
- [ ] Error messages are actionable

### 18.4 Performance Requirements

- [ ] Single document generation: <10s overhead beyond LLM time
- [ ] Skip logic check: <50ms
- [ ] Concurrent generation respects limits
- [ ] No memory leaks on long runs

---

## 19. File Structure

After completing Step 9:

```
app/
├── adapters/
│   ├── __init__.py                 # Export adapters
│   ├── base.py                     # GeneratorAdapter ABC
│   └── fpf/
│       ├── __init__.py             # Export FpfAdapter
│       ├── adapter.py              # FpfAdapter class
│       ├── config.py               # FpfSettings, FpfGeneratorConfig
│       ├── result.py               # FpfResult, FpfMetadata
│       ├── errors.py               # FpfError subclasses
│       └── subprocess.py           # Process management helpers
│
├── services/
│   ├── generation_service.py       # Orchestrates generation
│   └── generation_task.py          # Background task management
│
├── api/
│   └── routes/
│       ├── generation.py           # Generation endpoints
│       └── artifacts.py            # Artifact endpoints
│
└── infra/
    └── db/
        ├── models/
        │   └── artifact.py         # ArtifactModel
        └── repositories/
            └── artifact_repository.py

tests/
├── unit/
│   └── adapters/
│       └── fpf/
│           ├── test_adapter.py
│           ├── test_config.py
│           └── test_skip_logic.py
├── integration/
│   └── test_fpf_adapter.py
└── fixtures/
    └── mock_fpf.py
```

---

## 20. Next Steps

After Step 9 is complete:

1. **Step 10 (Evaluation)**: Wire up evaluation and reporting
   - Evaluate generated artifacts
   - Store eval results as artifacts
   - HTML report generation

2. **Step 16 (GPT-R Adapter)**: Same pattern for GPT-Researcher
   - `GptrAdapter` implementing same interface
   - Deep Research mode support
   - Different subprocess/API handling

3. **Step 17 (Combine)**: Combine Phase adapter
   - Takes winner artifacts from evaluation
   - Produces combined output
   - Uses same artifact storage pattern
