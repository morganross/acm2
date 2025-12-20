# ACM2 - API Cost Multiplier 2.0

## LLM Quick Reference Guide

This document is designed for LLM agents (like GitHub Copilot, Claude, GPT) to quickly understand and interact with the ACM2 codebase.

---

## 1. What is ACM2?

ACM2 (API Cost Multiplier 2.0) is a **research evaluation platform** that:
1. Takes input documents
2. Generates transformed/enhanced versions using multiple LLM models
3. Evaluates the quality of each generated document
4. Compares documents head-to-head (pairwise evaluation)
5. Optionally combines the best outputs into a final document
6. Tracks costs across all LLM API calls

### Core Use Case
Given a document and instructions, generate multiple versions using different models (GPT-4, Gemini, etc.), then evaluate which model produced the best output.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         ACM2 Stack                              │
├─────────────────────────────────────────────────────────────────┤
│  Frontend (React/Vite)                                          │
│    └── ui/                                                      │
│        └── src/                                                 │
│            ├── pages/           # Route components              │
│            ├── components/      # Reusable UI                   │
│            ├── stores/          # Zustand state                 │
│            └── api/             # API client                    │
├─────────────────────────────────────────────────────────────────┤
│  Backend (FastAPI/Uvicorn)                                      │
│    └── app/                                                     │
│        ├── api/                 # REST endpoints                │
│        │   ├── routes/          # Route handlers                │
│        │   ├── schemas/         # Pydantic models (API)         │
│        │   └── websockets.py    # WebSocket for live updates    │
│        ├── services/            # Business logic                │
│        │   └── run_executor.py  # Main execution pipeline       │
│        ├── adapters/            # External service integrations │
│        │   ├── fpf/             # FilePromptForge adapter       │
│        │   └── gptr/            # GPT-Researcher adapter        │
│        ├── evaluation/          # Evaluation logic              │
│        │   ├── single_doc.py    # Single document scoring       │
│        │   ├── pairwise.py      # Head-to-head comparison       │
│        │   └── judge.py         # LLM judge calls               │
│        ├── infra/               # Infrastructure                │
│        │   └── db/              # Database (SQLAlchemy)         │
│        │       ├── models/      # ORM models                    │
│        │       └── repositories/# Data access                   │
│        └── domain/              # Domain models                 │
├─────────────────────────────────────────────────────────────────┤
│  External Tools                                                 │
│    ├── FilePromptForge (FPF)    # CLI for LLM API calls         │
│    └── GPT-Researcher (GPTR)    # Research report generator     │
├─────────────────────────────────────────────────────────────────┤
│  Database: SQLite                                               │
│    Location: C:/Users/<user>/.acm2/acm2.db                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Key Concepts

### 3.1 Preset
A **saved configuration** that defines:
- Which documents to process
- Which models to use (e.g., `openai:gpt-4`, `google:gemini-2.5-pro`)
- Which generators to run (FPF, GPTR)
- Number of iterations
- Evaluation settings (single-doc, pairwise)
- Combine settings (optional)

**Database Table:** `presets`  
**API Route:** `/api/v1/presets`

### 3.2 Run
An **execution instance** of a preset. When you "execute" a preset, a Run is created that tracks:
- Status (pending, running, completed, failed, cancelled)
- Progress (tasks completed, total tasks)
- Cost (total USD spent on LLM calls)
- Results (generated documents, evaluation scores)

**Database Table:** `runs`  
**API Route:** `/api/v1/runs`

### 3.3 Document
Input documents that are processed by generators. Stored in the database with content.

**Database Table:** `documents`  
**API Route:** `/api/v1/documents`

### 3.4 Content
Reusable content items (instructions, prompts, evaluation criteria) stored in a "Content Library".

**Database Table:** `contents`  
**API Route:** `/api/v1/contents`

### 3.5 Generators
Tools that transform input documents:
- **FPF (FilePromptForge):** General-purpose LLM transformer. Takes input + instructions → output.
- **GPTR (GPT-Researcher):** Research-focused generator that searches the web and synthesizes reports.

### 3.6 Evaluation
Quality assessment of generated documents:
- **Single-Doc Evaluation:** Score a document on multiple criteria (1-10 scale)
- **Pairwise Evaluation:** Compare two documents head-to-head, determine winner
- **Judge Models:** LLMs used to evaluate (can be different from generation models)

---

## 4. Execution Pipeline

When a preset is executed, the `RunExecutor` orchestrates this pipeline:

```
┌──────────────────────────────────────────────────────────────┐
│ PHASE 1: GENERATION                                          │
│ For each (document × model × iteration):                     │
│   1. Generate document via FPF/GPTR                          │
│   2. Immediately run single-doc evaluation (streaming)       │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│ PHASE 2: PAIRWISE EVALUATION (optional)                      │
│   1. Collect all single-eval scores                          │
│   2. Filter to Top-N (optional)                              │
│   3. Run pairwise tournament                                 │
│   4. Calculate Elo rankings                                  │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│ PHASE 3: COMBINE (optional)                                  │
│   1. Take top outputs                                        │
│   2. Synthesize into combined document                       │
│   3. Optionally evaluate combined output                     │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    [Final Results + Cost Summary]
```

---

## 5. API Reference

### Base URL
```
http://localhost:8002/api/v1
```

### Health Check
```http
GET /api/v1/health
Response: {"status": "ok", "version": "2.0.0"}
```

### Presets

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/presets` | List all presets |
| POST | `/presets` | Create new preset |
| GET | `/presets/{id}` | Get preset details |
| PUT | `/presets/{id}` | Update preset |
| DELETE | `/presets/{id}` | Delete preset |
| POST | `/presets/{id}/duplicate` | Clone preset |
| POST | `/presets/{id}/execute` | Execute preset (creates Run) |

### Runs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/runs` | List all runs |
| POST | `/runs` | Create new run |
| GET | `/runs/{id}` | Get run details |
| DELETE | `/runs/{id}` | Delete run |
| POST | `/runs/{id}/start` | Start pending run |
| POST | `/runs/{id}/pause` | Pause running run |
| POST | `/runs/{id}/resume` | Resume paused run |
| POST | `/runs/{id}/cancel` | Cancel run |
| GET | `/runs/{id}/report` | Get evaluation report |
| GET | `/runs/{id}/logs` | Get run logs |
| GET | `/runs/{id}/generated/{doc_id}` | Get generated document |

### Documents

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/documents` | List documents |
| POST | `/documents` | Create document |
| POST | `/documents/upload` | Upload file as document |
| GET | `/documents/{id}` | Get document metadata |
| GET | `/documents/{id}/content` | Get document content |
| PATCH | `/documents/{id}` | Update document |
| DELETE | `/documents/{id}` | Delete document |

### Contents (Content Library)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/contents` | List contents |
| GET | `/contents/counts` | Get counts by type |
| POST | `/contents` | Create content |
| GET | `/contents/{id}` | Get content |
| PUT | `/contents/{id}` | Update content |
| DELETE | `/contents/{id}` | Delete content |
| POST | `/contents/{id}/resolve` | Resolve content references |
| POST | `/contents/{id}/duplicate` | Clone content |

### Evaluation (Direct API)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/evaluation/single` | Single-doc evaluation |
| POST | `/evaluation/pairwise` | Pairwise comparison |
| POST | `/evaluation/full` | Full evaluation pipeline |
| POST | `/evaluation/full/async` | Async full evaluation |
| GET | `/evaluation/jobs/{id}` | Get async job status |
| GET | `/evaluation/criteria` | List evaluation criteria |

### Generation (Direct API)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/generation/generate` | Generate document |
| GET | `/generation/status/{id}` | Get task status |
| POST | `/generation/cancel/{id}` | Cancel generation |
| GET | `/generation/tasks` | List active tasks |

### WebSocket

```
ws://localhost:8002/api/v1/runs/ws/run/{run_id}
```

Broadcasts live updates during run execution:
- `fpf_stats_update`: Live FPF call statistics
- `progress_update`: Task progress updates
- `status_update`: Run status changes

---

## 6. Database Schema

### Key Tables

#### `presets`
```sql
id              VARCHAR(36) PRIMARY KEY
name            VARCHAR(255) NOT NULL
description     TEXT
documents       JSON        -- List of document IDs
models          JSON        -- List of {provider, model, ...}
generators      JSON        -- ['fpf', 'gptr']
iterations      INTEGER DEFAULT 1
evaluation_enabled BOOLEAN DEFAULT TRUE
pairwise_enabled   BOOLEAN DEFAULT FALSE
fpf_config      JSON        -- FPF-specific config
gptr_config     JSON        -- GPTR-specific config
log_level       VARCHAR(20) DEFAULT 'INFO'
created_at      DATETIME
updated_at      DATETIME
```

#### `runs`
```sql
id              VARCHAR(36) PRIMARY KEY
title           VARCHAR(255) NOT NULL
description     TEXT
preset_id       VARCHAR(36) FK -> presets.id
status          VARCHAR(20) -- pending/running/completed/failed/cancelled
error_message   TEXT
started_at      DATETIME
completed_at    DATETIME
config          JSON        -- Snapshot of preset config
total_tasks     INTEGER DEFAULT 0
completed_tasks INTEGER DEFAULT 0
failed_tasks    INTEGER DEFAULT 0
current_task    VARCHAR(255)
total_cost_usd  FLOAT DEFAULT 0.0
total_tokens    INTEGER DEFAULT 0
results_summary JSON        -- Final results
created_at      DATETIME
updated_at      DATETIME
```

#### `documents`
```sql
id              VARCHAR(36) PRIMARY KEY
name            VARCHAR(255) NOT NULL
path            VARCHAR(1024)
content         TEXT
file_type       VARCHAR(50)
size_bytes      INTEGER
created_at      DATETIME
updated_at      DATETIME
```

#### `contents`
```sql
id              VARCHAR(36) PRIMARY KEY
name            VARCHAR(255) NOT NULL
content_type    VARCHAR(50) -- instructions/criteria/prompt/etc
content         TEXT
description     TEXT
tags            JSON
created_at      DATETIME
updated_at      DATETIME
```

---

## 7. Key Files & Locations

### Backend Entry Point
- `app/main.py` - FastAPI app factory

### API Routes
- `app/api/routes/runs.py` - Run endpoints (1319 lines)
- `app/api/routes/presets.py` - Preset endpoints (655 lines)
- `app/api/routes/documents.py` - Document endpoints
- `app/api/routes/contents.py` - Content Library endpoints
- `app/api/routes/evaluation.py` - Evaluation endpoints

### Core Services
- `app/services/run_executor.py` - Main execution pipeline (1247 lines)

### Adapters
- `app/adapters/fpf/adapter.py` - FilePromptForge integration (408 lines)
- `app/adapters/fpf/subprocess.py` - FPF subprocess management (240 lines)
- `app/adapters/gptr/adapter.py` - GPT-Researcher integration

### Evaluation
- `app/evaluation/single_doc.py` - Single document evaluator
- `app/evaluation/pairwise.py` - Pairwise evaluator
- `app/evaluation/judge.py` - LLM judge implementation
- `app/evaluation/criteria.py` - Evaluation criteria definitions

### Database
- `app/infra/db/models/` - SQLAlchemy ORM models
- `app/infra/db/repositories/` - Data access layer
- `app/infra/db/session.py` - Database session management

### Schemas (API)
- `app/schemas/runs.py` - Run-related Pydantic models
- `app/api/schemas/presets.py` - Preset-related Pydantic models

### WebSocket
- `app/api/websockets.py` - WebSocket connection manager

### Frontend
- `ui/src/` - React application source
- `ui/src/pages/` - Route components
- `ui/src/stores/` - Zustand state stores
- `ui/src/api/` - API client

---

## 8. Common Operations

### Start the Server
```powershell
# From acm2 directory
Start-Process -FilePath "python" -ArgumentList "-m", "uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8002" -WorkingDirectory "c:\dev\silky\api_cost_multiplier\acm2" -WindowStyle Hidden
```

### Verify Server Running
```powershell
netstat -ano | Select-String ":8002.*LISTENING"
```

### Query Database
```powershell
python -c "import sqlite3; c=sqlite3.connect('C:/Users/kjhgf/.acm2/acm2.db'); r=c.execute('SELECT id, status FROM runs LIMIT 5'); print(r.fetchall())"
```

### Check Run Status
```powershell
curl http://localhost:8002/api/v1/runs/{run_id}
```

### List Presets
```powershell
curl http://localhost:8002/api/v1/presets
```

### Execute a Preset
```powershell
curl -X POST http://localhost:8002/api/v1/presets/{preset_id}/execute
```

---

## 9. Model String Format

Models are specified as `provider:model_name`:
- `openai:gpt-4`
- `openai:gpt-4o`
- `openai:gpt-5`
- `openai:gpt-5-mini`
- `openai:gpt-5.1`
- `google:gemini-2.5-pro`
- `google:gemini-2.5-flash`
- `anthropic:claude-3-opus`
- `anthropic:claude-3-sonnet`

---

## 10. Run Status Lifecycle

```
PENDING ──start──> RUNNING ──success──> COMPLETED
    │                 │
    │                 ├──fail──> FAILED
    │                 │
    │                 └──cancel──> CANCELLED
    │
    └──fail──> FAILED (validation error)
```

---

## 11. Known Issues / Gotchas

### 1. Orphaned Runs
If the server restarts during a run, the run stays in `running` status forever. Check for orphaned runs on startup.

### 2. WebSocket Connection
WebSocket endpoint is at `/api/v1/runs/ws/run/{run_id}` (note the path structure).

### 3. FPF Subprocess Timeout
The FPF subprocess has a 24-hour safety timeout. If FPF hangs internally, it won't be killed for 24 hours.

### 4. Python Environment
Use the virtual environment at `c:\dev\silky\.venv` for all Python commands.

### 5. Database Location
Default SQLite database is at `C:/Users/<username>/.acm2/acm2.db`.

---

## 12. Environment Variables

Key environment variables (set in `.env`):
```
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...
ANTHROPIC_API_KEY=...
ACM2_DATABASE_URL=sqlite+aiosqlite:///C:/Users/kjhgf/.acm2/acm2.db
```

---

## 13. Testing

```powershell
# Run all tests
cd c:\dev\silky\api_cost_multiplier\acm2
pytest

# Run specific test file
pytest tests/test_api.py

# Run with coverage
pytest --cov=app
```

---

## 14. Debugging Tips

### View Run Logs
```powershell
Get-Content "c:\dev\silky\api_cost_multiplier\acm2\logs\{run_id}\run.log" -Tail 100
```

### Check FPF Subprocess Output
Logs are written to the run's log directory during execution.

### Enable Debug Logging
Set `log_level: "DEBUG"` in preset configuration.

### Query Recent Runs
```sql
SELECT id, title, status, created_at, total_cost_usd 
FROM runs 
ORDER BY created_at DESC 
LIMIT 10;
```

---

## 15. Key Dataclasses

### RunConfig (app/services/run_executor.py)
```python
@dataclass
class RunConfig:
    document_ids: List[str]
    document_contents: Dict[str, str]
    generators: List[GeneratorType]
    models: List[str]
    instructions: str = ""
    iterations: int = 1
    enable_single_eval: bool = True
    enable_pairwise: bool = True
    eval_iterations: int = 1
    eval_judge_models: List[str] = field(default_factory=list)
    pairwise_top_n: Optional[int] = None
    enable_combine: bool = False
    combine_strategy: str = ""
    combine_models: List[str] = field(default_factory=list)
    combine_instructions: Optional[str] = None
    generation_concurrency: int = 3
    eval_concurrency: int = 3
    request_timeout: int = 1800
    max_retries: int = 3
    retry_delay: float = 2.0
    log_level: str = "INFO"
```

### RunResult (app/services/run_executor.py)
```python
@dataclass
class RunResult:
    run_id: str
    status: RunPhase
    generated_docs: List[GeneratedDocument]
    single_eval_results: Optional[Dict[str, SingleEvalSummary]]
    pairwise_results: Optional[PairwiseSummary]
    winner_doc_id: Optional[str]
    combined_content: Optional[str]
    combined_docs: List[GeneratedDocument]
    post_combine_eval_results: Optional[PairwiseSummary]
    total_cost_usd: float
    duration_seconds: float
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    fpf_stats: Optional[Dict[str, Any]]
    errors: List[str]
```

---

## 16. Summary

ACM2 is a research evaluation platform that:
1. **Stores** presets (configurations) and documents in SQLite
2. **Executes** runs via the RunExecutor service
3. **Generates** documents using FPF or GPTR adapters
4. **Evaluates** documents using LLM judges (single-doc and pairwise)
5. **Tracks** costs across all API calls
6. **Broadcasts** live progress via WebSocket
7. **Exposes** a REST API for frontend and programmatic access

**Key URLs:**
- API: `http://localhost:8002/api/v1/`
- WebSocket: `ws://localhost:8002/api/v1/runs/ws/run/{run_id}`

**Key Files:**
- Entry: `app/main.py`
- Executor: `app/services/run_executor.py`
- Routes: `app/api/routes/*.py`
- Models: `app/infra/db/models/*.py`

---

*Last Updated: December 20, 2025*
