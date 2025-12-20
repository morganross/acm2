# ACM 2.0 – Phase 0 One‑Pager

## Purpose

ACM 2.0 is the next generation of our analysis and evaluation pipeline. The goal is to move from a path-and-script–centric toolchain to a **run‑centered, API‑first system** that can be safely used by multiple tools, multiple users, and automation.

It should keep the parts of the current stack that work very well (FPF, evaluation logic, HTML reports, robust logging) but remove brittle coupling and heuristics ("recent files", magic directory scanning, hard‑coded paths) that block multi‑file concurrency, retries, and a clean web experience.

## Non‑Goals

- Not a full re‑write of prompts, LLM logic, or evaluation methodology.
- Not a replacement for GitHub or other storage systems; ACM 2.0 is an **app on top of them**.
- Not a single desktop GUI only; the core must be usable **without** a local GUI.

## High‑Level Shape

- **API‑first backend** (Python service, e.g. FastAPI) exposing runs, documents, and artifacts over HTTP/JSON.
- **GitHub‑backed storage** as the first‑class way to store and version documents and outputs (with the option to plug in other storage providers later).
- **Adapters for engines** like FPF and GPT‑R so ACM 2.0 calls them through small, stable interfaces instead of reaching into their internals.
- **Web GUI** that talks only to the API, plus HTML reports that can be viewed directly in a browser.

## What We Must Preserve

- **File‑based skip logic**: being able to detect that a particular document + config already has outputs based on filenames/patterns, *not* timestamps.
- **FPF reliability and logging**: FPF is battle‑tested; ACM 2.0 should leverage it via an adapter, not re‑implement its behavior.
- **Single‑document workflows**: the ability to run or re‑run a single document (or small subset) without re‑processing everything.
- **HTML reports and exports**: clear, linkable outputs (HTML/CSV/DB) that humans can inspect and share.
- **Strong, structured logging**: enough detail to debug failures and reconstruct what happened for a run.

## What We Should Change or Drop

- **"Recent files" and "most recent export dir" heuristics**: replace them with explicit run IDs and stable artifact references.
- **Direct filesystem coupling between phases**: generation, eval, combine, and playoffs should talk via **artifacts and run metadata**, not opportunistic directory scans.
- **GUI fields that require full paths**: move to run/document selection by ID or logical name; paths become an implementation detail.
- **Vendored GPT‑R and tangled FPF calls**: replace with thin adapters (CLI or library) that encapsulate versioning, arguments, and outputs.

## Phase 0 Deliverables

By the end of Phase 0 we should have:

1. This one‑pager agreed upon and updated with any extra hard requirements you care about.
2. A short, explicit list of behaviors that **must** match current ACM vs. behaviors we are willing to change.
3. A rough drawing (even on paper) of the core objects: `Run`, `Document`, `Artifact`, and how they relate to GitHub, FPF, and evaluation.
4. Agreement that new work targets ACM 2.0 APIs and adapters, not new features in the legacy runner except for emergency fixes.

---

## Deliverable 1: One-Pager Finalization & Hard Requirements

### 1.1 Purpose

This document serves as the authoritative reference for ACM 2.0's scope, goals, and constraints. Before proceeding to Phase 1, all stakeholders must review, comment, and sign off.

### 1.2 Hard Requirements Checklist

The following requirements are **non-negotiable** for ACM 2.0:

| ID | Requirement | Rationale |
|----|-------------|-----------|
| HR-01 | **Deterministic Skip Logic** | Must detect existing outputs by filename pattern `{base_name}.*` across eval_output, winners, and gen_output directories. No timestamp-based logic. |
| HR-02 | **Run Isolation** | Each run must be fully isolated with its own run_id, artifacts, and logs. No shared mutable state between concurrent runs. |
| HR-03 | **Backward-Compatible FPF Integration** | FPF calling conventions (stdin JSON batch protocol, exit codes 0-5, 4-layer retry) must be preserved or adapted without loss of functionality. |
| HR-04 | **Evaluation DB Compatibility** | SQLite schema for `single_doc_results`, `pairwise_results`, and `elo_ratings` must remain compatible or have documented migration path. |
| HR-05 | **HTML Report Generation** | Timeline JSON → HTML report pipeline must produce equivalent output viewable in browser. |
| HR-06 | **Winner Persistence** | Winning documents must be saved to a designated winners directory with stable naming. |
| HR-07 | **Structured Logging** | All operations must emit structured logs with timestamps, run IDs, and operation types parseable by timeline tools. |
| HR-08 | **Single-Document Re-run** | Users must be able to re-run generation or evaluation for a single document without re-processing the entire batch. |

### 1.3 Soft Requirements (Negotiable)

| ID | Requirement | Current Status | Proposed Change |
|----|-------------|----------------|-----------------|
| SR-01 | Directory structure mirroring | Input folder structure mirrored to output | Consider flat structure with metadata |
| SR-02 | Model override via env vars | SMART_LLM, FAST_LLM, STRATEGIC_LLM | Move to explicit run config |
| SR-03 | One-file-only mode | Config flag limits to first file | Replace with explicit file selection |
| SR-04 | Heartbeat thread | 30-second console heartbeat | Move to API health endpoint |

### 1.4 Sign-Off Criteria

- [ ] Product owner reviewed and approved scope
- [ ] Technical lead reviewed architecture alignment
- [ ] No open blockers in hard requirements
- [ ] All soft requirements dispositioned (keep/modify/drop)

---

## Deliverable 2: Behavior Compatibility Matrix

### 2.1 Purpose

Explicitly document which current ACM behaviors must be preserved exactly, which can be modified, and which should be dropped entirely.

### 2.2 Skip Logic ( Behavioral Compatibility)

#### 2.2.1 Skip Logic Behavior

```
CURRENT BEHAVIOR:
  FOR each markdown file in input_folder:
    base_name = filename without extension
    
    CHECK 1: eval_output/{any_subdir}/{base_name}.*
      → If match found: SKIP (logged as "found eval output")
    
    CHECK 2: {output_parent}/winners/{relative_path}/{base_name}.*
      → If match found: SKIP (logged as "found existing winner")
    
    CHECK 3: output_folder/{relative_path}/{base_name}.*
      → If match found: SKIP (logged as "found N existing outputs")

ACM 2.0 may:
  - May use differnt system.
  - Use same pattern matching: startswith(base_name + ".")
  - Support same file extensions: .md, .json, .txt, .docx, .pdf
  - Log skip decisions with same detail level
```

#### 2.2.2 FPF Exit Code Handling

```
EXIT CODES (must be preserved):
  0 = Success
  1 = Missing grounding (triggers grounding-enhanced retry)
  2 = Missing reasoning (triggers reasoning-enhanced retry)
  3 = Both missing (triggers combined retry)
  4 = Unknown validation failure (triggers combined retry)
  5 = Other error (no retry)

LAYER 2 FALLBACK (must be preserved):
  Even if exit code = 0, scan logs/validation/*-FAILURE-REPORT.json
  for files modified in last 5 seconds. If found, override exit code.
```

#### 2.2.3 Filename Generation

```
PATTERN: {base_name}.{kind}.{index}.{model_label}.{uid3}.{ext}

EXAMPLES:
  intro.fpf.1.gpt-4o.abc.md
  intro.gptr.2.gemini-1-5-pro.xyz.md
  intro.dr.1.gpt-4o.ghi.md
  


#### 2.2.4 Evaluation Database Schema

```sql
-- These tables  exist with these columns (additional columns OK)

CREATE TABLE single_doc_results (
    id INTEGER PRIMARY KEY,
    doc_id TEXT NOT NULL,          -- Full path or stable identifier
    dimension TEXT NOT NULL,        -- Rubric dimension name
    score REAL,                     -- 1.0-5.0 or NULL on failure
    iteration INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE pairwise_results (
    id INTEGER PRIMARY KEY,
    doc_a TEXT NOT NULL,
    doc_b TEXT NOT NULL,
    winner TEXT CHECK(winner IN ('A', 'B', 'tie')),
    iteration INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE elo_ratings (
    doc_id TEXT PRIMARY KEY,
    elo_rating REAL DEFAULT 1500.0,
    games_played INTEGER DEFAULT 0
);
```

### 2.3 MAY CHANGE (Behavior Modifications Allowed)

#### 2.3.1 Configuration Format

```
CURRENT: config.yaml with nested structure
  - runs: list of {type, provider, model}
  - concurrency.gpt_researcher.{enabled, max_concurrent_reports, ...}
  - eval.{auto_run, streaming_single_eval, ...}

ACM 2.0 MAY:
  - Use different config format (JSON, TOML)
  - Flatten or restructure keys
  - Add new required fields
  - MUST provide migration tool or documentation
```

#### 2.3.2 Log Format

```
CURRENT: 
  - Text-based with timestamp prefix
  - Special markers: [FPF RUN_START], [GPTR_END], [STREAMING_EVAL], etc.
  - Parsed by tools/timeline_from_logs.py

ACM 2.0 MAY:
  - Switch to structured JSON logging
  - Change marker format
  - MUST update timeline parser OR replace with new visualization
```

#### 2.3.3 Subprocess Communication

```
CURRENT:
  - FPF: stdin JSON, stdout events, exit codes
  - GPTR: env vars for model, stdout JSON line for result
  - MA: --task-config file, artifact discovery by mtime

ACM 2.0 MAY:
  - Unify to single protocol (e.g., all stdin JSON)
  - Add message queuing
  - MUST preserve equivalent functionality
```

### 2.4 SHOULD DROP (Deprecated Behaviors)

| Behavior | Reason to Drop |
|----------|----------------|
| `batch_start_ts` file filtering | Replace with explicit artifact registration |
| Environment variable model override | Move to explicit run config |
| `SUBPROC_LOGGER` global | Replace with dependency injection |
| `forward_subprocess_output` toggle | Always log, control verbosity via log level |
| Heartbeat thread with console print | Replace with API status endpoint |
| `one_file_only` config flag | Replace with explicit file selection in request |
| `seen_src` deduplication set | Use database-backed artifact tracking |

---

## Deliverable 3: Core Object Model Diagram

### 3.1 Entity Definitions

#### 3.1.1 Run

```yaml
Run:
  description: |
    A single invocation of the ACM pipeline for one or more source documents.
    Immutable after creation (append-only state transitions).
  
  attributes:
    run_id: string           # UUID, e.g., "run_20251203_143022_abc"
    created_at: timestamp
    status: enum             # pending | running | completed | failed | cancelled
    config: RunConfig        # Snapshot of configuration at run start
    source_documents: list[DocumentRef]
    
  relationships:
    - has_many: Artifact     # Generated reports, eval DBs, logs
    - has_many: Task         # Individual generation/eval tasks
    - belongs_to: Project    # Logical grouping (optional)
```

#### 3.1.2 Document

```yaml
Document:
  description: |
    A source markdown file that serves as input to generation.
    May be stored in GitHub, local filesystem, or other storage.
  
  attributes:
    doc_id: string           # Stable identifier, e.g., "intro" or "docs/chapter1"
    storage_ref: string      # GitHub: "owner/repo/path", Local: "/abs/path"
    content_hash: string     # SHA-256 of content for change detection
    
  relationships:
    - has_many: Artifact     # Generated outputs for this document
    - referenced_by: Run     # Runs that include this document
```

#### 3.1.3 Artifact

```yaml
Artifact:
  description: |
    Any file produced by ACM: generated reports, evaluation databases,
    logs, HTML reports, winner copies.
  
  attributes:
    artifact_id: string      # UUID
    artifact_type: enum      # report | eval_db | log | html_report | winner
    generator: enum          # fpf | gptr | dr | ma | eval | combine
    storage_ref: string      # Where artifact is stored
    metadata: dict           # Generator-specific: model, iteration, scores, etc.
    
  relationships:
    - belongs_to: Run
    - belongs_to: Document   # Source document (for reports)
    - derived_from: list[Artifact]  # For combined/winner artifacts
```

#### 3.1.4 Task

```yaml
Task:
  description: |
    A unit of work within a Run: one FPF call, one GPTR report, one eval, etc.
  
  attributes:
    task_id: string
    task_type: enum          # generate_fpf | generate_gptr | generate_ma | 
                             # eval_single | eval_pairwise | combine
    status: enum             # pending | running | completed | failed | skipped
    started_at: timestamp
    completed_at: timestamp
    error_message: string    # If failed
    retry_count: int
    
  relationships:
    - belongs_to: Run
    - produces: list[Artifact]
    - depends_on: list[Task]  # For DAG ordering
```

### 3.2 Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              ACM 2.0 OBJECT MODEL                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐         ┌─────────────┐         ┌─────────────┐           │
│  │   Project   │ 1───N   │     Run     │ 1───N   │    Task     │           │
│  │             │◄────────│             │◄────────│             │           │
│  │ project_id  │         │ run_id      │         │ task_id     │           │
│  │ name        │         │ status      │         │ task_type   │           │
│  │ github_repo │         │ config      │         │ status      │           │
│  └─────────────┘         │ created_at  │         │ retry_count │           │
│                          └──────┬──────┘         └──────┬──────┘           │
│                                 │                       │                   │
│                                 │ 1                     │ 1                 │
│                                 │                       │                   │
│                                 ▼ N                     ▼ N                 │
│  ┌─────────────┐         ┌─────────────┐         ┌─────────────┐           │
│  │  Document   │ N───M   │  Artifact   │◄────────│  Artifact   │           │
│  │             │◄───────▶│             │ derived │  (winner)   │           │
│  │ doc_id      │         │ artifact_id │ from    │             │           │
│  │ storage_ref │         │ type        │         │             │           │
│  │ content_hash│         │ generator   │         │             │           │
│  └─────────────┘         │ storage_ref │         └─────────────┘           │
│                          │ metadata    │                                    │
│                          └─────────────┘                                    │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  STORAGE ADAPTERS                                                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                         │
│  │   GitHub    │  │ Local FS    │  │   S3/Blob   │                         │
│  │   Adapter   │  │   Adapter   │  │   Adapter   │                         │
│  └─────────────┘  └─────────────┘  └─────────────┘                         │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  GENERATOR ADAPTERS                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │     FPF     │  │    GPTR     │  │     MA      │  │    Eval     │        │
│  │   Adapter   │  │   Adapter   │  │   Adapter   │  │   Adapter   │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 State Transitions

#### 3.3.1 Run State Machine

```
                    ┌──────────────────────────────────────────┐
                    │                                          │
                    ▼                                          │
┌─────────┐    ┌─────────┐    ┌─────────────┐    ┌─────────┐  │
│ PENDING │───▶│ RUNNING │───▶│  COMPLETED  │    │ FAILED  │  │
└─────────┘    └────┬────┘    └─────────────┘    └────▲────┘  │
                    │                                  │       │
                    │         ┌───────────┐           │       │
                    └────────▶│ CANCELLED │───────────┼───────┘
                              └───────────┘           │
                                                      │
     (any state except COMPLETED can transition to FAILED)
```

#### 3.3.2 Task State Machine

```
┌─────────┐    ┌─────────┐    ┌─────────────┐
│ PENDING │───▶│ RUNNING │───▶│  COMPLETED  │
└────┬────┘    └────┬────┘    └─────────────┘
     │              │
     │              │         ┌─────────┐
     │              └────────▶│ FAILED  │──┐
     │                        └─────────┘  │ retry_count < max
     │                              │      │
     │              ┌───────────────┘      │
     │              ▼                      │
     │         ┌─────────┐                 │
     └────────▶│ SKIPPED │◄────────────────┘ retry_count >= max
               └─────────┘
```

### 3.4 GitHub Integration

```yaml
GitHubStorageAdapter:
  operations:
    list_documents:
      input: {repo, path_prefix, branch}
      output: list[Document]
      
    read_document:
      input: {repo, path, ref}
      output: {content, sha}
      
    write_artifact:
      input: {repo, path, content, message, branch}
      output: {sha, url}
      
    create_run_branch:
      input: {repo, run_id, base_branch}
      output: {branch_name}
      
    list_artifacts:
      input: {repo, run_id}
      output: list[Artifact]

  configuration:
    auth: GitHub App or PAT
    default_branch: main
    artifact_branch_pattern: "acm/runs/{run_id}"
    artifact_path_pattern: "acm-outputs/{run_id}/{artifact_type}/{filename}"
```

---

## Deliverable 4: Development Focus Agreement

### 4.1 Purpose

Establish explicit agreement that new feature development targets ACM 2.0, with legacy runner receiving only critical maintenance.

### 4.2 Legacy Runner (runner.py) Policy

#### 4.2.1 Allowed Changes

| Category | Description | Example |
|----------|-------------|---------|
| **Critical Bug Fixes** | Fixes for issues blocking production use | Subprocess deadlock, data corruption |
| **Security Patches** | Addressing CVEs in dependencies | Updating vulnerable library |
| **Documentation** | Improving comments, docstrings | Adding edge case documentation |
| **Logging Improvements** | Better error messages for debugging | More context in failure logs |

#### 4.2.2 Prohibited Changes

| Category | Description | Redirect To |
|----------|-------------|-------------|
| **New Features** | Any new functionality | ACM 2.0 API |
| **Refactoring** | Structural changes | ACM 2.0 implementation |
| **New Integrations** | Additional generators,
| **UI/UX Changes** | GUI modifications | ACM 2.0 web GUI |

### 4.3 ACM 2.0 Development Priorities

#### 4.3.1 Phase 1 Priorities (Post Phase 0)

```
PRIORITY 1: Core API Foundation
├── Run management endpoints (create, status, cancel)
├── Document registration
├── Artifact storage abstraction
└── SQLite → PostgreSQL migration path

PRIORITY 2: Generator Adapters
├── FPF adapter (preserving 4-layer retry)
├── GPTR adapter (subprocess isolation)
└── Adapter interface contract

PRIORITY 3: Evaluation Integration
├── Single-doc eval endpoint
├── Pairwise eval endpoint
├── Streaming eval support
└── Results aggregation

PRIORITY 4: Storage Backends
├── Local filesystem adapter
├── GitHub adapter (read)
├── GitHub adapter (write artifacts)
└── Storage abstraction layer
```

#### 4.3.2 Development Guidelines

```yaml
code_style:
  language: Python 3.11+
  framework: FastAPI
  async: Required for all I/O operations
  typing: Strict (mypy --strict)
  
testing:
  unit_coverage: 80% minimum
  integration_tests: Required for all adapters
  e2e_tests: Required for all API endpoints
  
documentation:
  api: OpenAPI/Swagger auto-generated
  code: Docstrings with examples
  architecture: ADRs for major decisions
  
ci_cd:
  linting: ruff, black
  type_checking: mypy
  security: bandit, safety
  tests: pytest with coverage
```



## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **ACM** | Advanced Comparison Manager - the overall system |
| **FPF** | FilePromptForge - LLM generation tool |
| **GPTR** | GPT-Researcher - research report generator |
| **MA** | Multi-Agent - multi-agent research system |
| **DR** | Deep Research - extended GPTR mode |
| **Run** | Single pipeline execution instance |
| **Artifact** | Any file produced by ACM |
| **Task** | Unit of work within a run |
| **Adapter** | Interface layer for external tools/storage |
| **Skip Logic** | Check for existing outputs before processing |

## Appendix B: Reference Documents

| Document | Location | Purpose |
|----------|----------|---------|
| ACM Technical Deep Dive | `acm2/ACM_TECHNICAL_DEEP_DIVE.md` | Current implementation details |
| LLM Understanding Report | `acm2/LLM_ACM_UNDERSTANDING_REPORT.md` | High-level architecture overview |
| ACM2 Development Steps | `acm2/ACM2_DEVELOPMENT_STEPS.md` | Phase-by-phase implementation plan |
| FPF Development Steps | `acm2/FPF_DEVELOPMENT_STEPS.md` | FPF adapter requirements |
| LLM Reading Guide | `acm2/LLM_READING_GUIDE_FOR_ACM.md` | Guide for LLMs analyzing ACM |

