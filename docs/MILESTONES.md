# ACM 2.0 Milestones & Progress Tracker

## Overview

This document tracks implementation progress through testable milestones. Each milestone has clear acceptance criteria that can be verified with automated tests or manual checks.

---

## Phase 1: Foundation (Steps 2.1)

### M1.1 — Project Skeleton ✅
**Status:** Complete

- [x] Directory structure created
- [x] All empty files created (~180 files)
- [x] `pyproject.toml` exists
- [x] `alembic.ini` exists

**Test:** `ls acm2/app` shows expected folders

---

### M1.2 — Dependencies & Virtual Environment
**Status:** Not Started

- [ ] `pyproject.toml` has all dependencies defined
- [ ] `pip install -e .` succeeds
- [ ] `python -c "import app"` works

**Test:**
```powershell
cd acm2
pip install -e ".[dev]"
python -c "from app import main; print('OK')"
```

---

### M1.3 — Configuration System
**Status:** Not Started

- [ ] `app/config.py` loads settings from environment
- [ ] `DatabaseSettings` class works
- [ ] `GitHubSettings` class works
- [ ] `LoggingSettings` class works
- [ ] Settings can be overridden via `.env`

**Test:**
```powershell
$env:ACM2_DB_USE_SQLITE = "true"
python -c "from app.config import get_settings; s = get_settings(); print(s.database.use_sqlite)"
# Should print: True
```

---

### M1.4 — FastAPI App Factory
**Status:** Not Started

- [ ] `app/main.py` has `create_app()` function
- [ ] App starts without errors
- [ ] CORS middleware configured
- [ ] Request ID middleware configured

**Test:**
```powershell
uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
# In another terminal:
curl http://127.0.0.1:8000/
```

---

### M1.5 — Health Check Endpoint
**Status:** Not Started

- [ ] `GET /api/v1/health` returns 200
- [ ] Response includes `status: "ok"`
- [ ] Response includes `database: "ok"` or `"error"`
- [ ] Response includes `version`

**Test:**
```powershell
curl http://127.0.0.1:8000/api/v1/health
# Expected: {"status": "ok", "database": "ok", "version": "0.1.0"}
```

---

### M1.6 — Database Connection (SQLite)
**Status:** Not Started

- [ ] `app/infra/db/session.py` has `DatabaseManager`
- [ ] SQLite file created on first run
- [ ] Async session works
- [ ] Connection pool configured

**Test:**
```powershell
python -c "
import asyncio
from app.infra.db.session import DatabaseManager
async def test():
    db = DatabaseManager()
    await db.connect()
    print('Connected!')
    await db.close()
asyncio.run(test())
"
```

---

### M1.7 — Structured Logging
**Status:** Not Started

- [ ] `app/infra/logging.py` configures structlog
- [ ] Logs output as JSON in production
- [ ] Logs output as pretty console in development
- [ ] Request ID included in all logs

**Test:**
```powershell
python -c "
from app.infra.logging import setup_logging, get_logger
setup_logging()
log = get_logger('test')
log.info('Hello', foo='bar')
"
# Should print JSON with timestamp, level, message, foo
```

---

### M1.8 — Alembic Migrations
**Status:** Not Started

- [ ] `alembic/env.py` configured for async
- [ ] Initial migration creates `run`, `document`, `run_document` tables
- [ ] `alembic upgrade head` succeeds
- [ ] `alembic downgrade -1` succeeds

**Test:**
```powershell
cd acm2
alembic upgrade head
alembic current
# Should show migration revision
```

---

## Phase 2: Run/Document Lifecycle (Steps 2.7A, 2.7B)

### M2.1 — Run Domain Model
**Status:** Not Started

- [ ] `Run` Pydantic model in `app/domain/models/run.py`
- [ ] `RunStatus` enum (pending, running, completed, failed, cancelled)
- [ ] `RunConfig` value object
- [ ] Tag validation (max 10 tags, 32 chars each)

**Test:**
```python
pytest tests/unit/domain/test_run_model.py -v
```

---

### M2.2 — Document Domain Model
**Status:** Not Started

- [ ] `Document` Pydantic model
- [ ] `GitHubSource` for GitHub files
- [ ] `InlineSource` for inline content
- [ ] `DocumentMetadata` for computed fields

**Test:**
```python
pytest tests/unit/domain/test_document_model.py -v
```

---

### M2.3 — Run Repository
**Status:** Not Started

- [ ] `RunRepository` with async CRUD
- [ ] `create()`, `get()`, `list()`, `update()`, `delete()`
- [ ] Filtering by status, project, tags
- [ ] Pagination support

**Test:**
```python
pytest tests/unit/repositories/test_run_repository.py -v
```

---

### M2.4 — Document Repository
**Status:** Not Started

- [ ] `DocumentRepository` with async CRUD
- [ ] `RunDocumentRepository` for junction table
- [ ] Attach/detach documents to runs
- [ ] List documents by run

**Test:**
```python
pytest tests/unit/repositories/test_document_repository.py -v
```

---

### M2.5 — Run Service
**Status:** Not Started

- [ ] `RunService` business logic layer
- [ ] Status transition validation
- [ ] Create run with documents
- [ ] Cancel run (soft delete)

**Test:**
```python
pytest tests/unit/services/test_run_service.py -v
```

---

### M2.6 — Run API Endpoints
**Status:** Not Started

- [ ] `POST /api/v1/runs` — create run
- [ ] `GET /api/v1/runs` — list runs with filters
- [ ] `GET /api/v1/runs/{run_id}` — get run
- [ ] `PATCH /api/v1/runs/{run_id}` — update run
- [ ] `POST /api/v1/runs/{run_id}/cancel` — cancel run
- [ ] `DELETE /api/v1/runs/{run_id}` — soft delete

**Test:**
```python
pytest tests/integration/api/test_runs_api.py -v
```

---

### M2.7 — Document API Endpoints
**Status:** Not Started

- [ ] `POST /api/v1/runs/{run_id}/documents` — attach document
- [ ] `POST /api/v1/runs/{run_id}/documents/batch` — batch attach
- [ ] `GET /api/v1/runs/{run_id}/documents` — list documents
- [ ] `GET /api/v1/documents/{document_id}` — get document
- [ ] `DELETE /api/v1/documents/{document_id}` — detach

**Test:**
```python
pytest tests/integration/api/test_documents_api.py -v
```

---

## Phase 3: Storage Provider (Step 2.8)

### M3.1 — StorageProvider Interface
**Status:** Not Started

- [ ] `StorageProvider` ABC defined
- [ ] `StorageFile`, `StorageCommit`, `StorageError` data classes
- [ ] All method signatures documented

**Test:** Code review / type checking

---

### M3.2 — LocalStorageProvider
**Status:** Not Started

- [ ] Read/write files to local filesystem
- [ ] Path normalization (Windows paths)
- [ ] Directory auto-creation
- [ ] Content hash computation (SHA-256)

**Test:**
```python
pytest tests/unit/storage/test_local_provider.py -v
```

---

### M3.3 — GitHubStorageProvider
**Status:** Not Started

- [ ] Read files via Contents API
- [ ] Write files via Contents API
- [ ] Batch write via Git Data API
- [ ] Rate limit header parsing
- [ ] TTL cache for reads

**Test:**
```python
pytest tests/unit/storage/test_github_provider.py -v
pytest tests/integration/test_storage_integration.py -v  # requires GitHub token
```

---

## Phase 4: FPF Adapter (Step 9)

### M4.1 — FPF Adapter Interface
**Status:** Not Started

- [ ] `GeneratorAdapter` ABC
- [ ] `FpfAdapter` class
- [ ] `FpfResult`, `FpfMetadata` data classes
- [ ] Error types defined

**Test:**
```python
pytest tests/unit/adapters/fpf/test_adapter.py -v
```

---

### M4.2 — FPF Subprocess Management
**Status:** Not Started

- [ ] Build FPF CLI command
- [ ] Execute subprocess with timeout
- [ ] Parse stdout/stderr
- [ ] Cleanup temp files

**Test:**
```python
pytest tests/unit/adapters/fpf/test_subprocess.py -v
```

---

### M4.3 — Skip Logic
**Status:** Not Started

- [ ] Compute config hash
- [ ] Check existing artifacts
- [ ] Skip if hash matches
- [ ] Force flag bypasses skip

**Test:**
```python
pytest tests/unit/adapters/fpf/test_skip_logic.py -v
```

---

### M4.4 — Generation API
**Status:** Not Started

- [ ] `POST /api/v1/runs/{run_id}/generate` — start generation
- [ ] `GET /api/v1/runs/{run_id}/generate/status` — check progress
- [ ] `POST /api/v1/runs/{run_id}/generate/cancel` — cancel
- [ ] Artifacts created and stored

**Test:**
```python
pytest tests/integration/test_fpf_adapter.py -v
```

---

## Phase 5: Evaluation (Step 10)

### M5.1 — Single-Doc Evaluator
**Status:** Not Started

- [ ] `SingleDocEvaluator` class
- [ ] Judge configuration
- [ ] Criteria scoring (1-10)
- [ ] Multiple iterations

**Test:**
```python
pytest tests/evaluation/test_single_doc_evaluator.py -v
```

---

### M5.2 — Pairwise Evaluator
**Status:** Not Started

- [ ] `PairwiseEvaluator` class
- [ ] Head-to-head comparison
- [ ] Winner determination
- [ ] Confidence scoring

**Test:**
```python
pytest tests/evaluation/test_pairwise_evaluator.py -v
```

---

### M5.3 — Elo Calculator
**Status:** Not Started

- [ ] `EloCalculator` class
- [ ] K-factor = 32
- [ ] Initial rating = 1500
- [ ] Rating history tracking

**Test:**
```python
pytest tests/evaluation/test_elo_calculator.py -v
```

---

### M5.4 — Evaluation Orchestrator
**Status:** Not Started

- [ ] `EvalOrchestrator` coordinates full pipeline
- [ ] Single-doc → Pairwise → Elo
- [ ] Top-N selection
- [ ] Result aggregation

**Test:**
```python
pytest tests/evaluation/test_eval_orchestrator.py -v
```

---

### M5.5 — HTML Report Generator
**Status:** Not Started

- [ ] Jinja2 templates
- [ ] Scores table
- [ ] Rankings view
- [ ] Pairwise comparisons

**Test:**
```python
pytest tests/evaluation/test_html_report_generator.py -v
```

---

## Phase 6: Combine (Step 17)

### M6.1 — Concatenate Strategy
**Status:** Not Started

- [ ] Simple artifact concatenation
- [ ] Custom separator
- [ ] Table of contents generation

**Test:**
```python
pytest tests/combine/test_concatenate.py -v
```

---

### M6.2 — Best-of-N Strategy
**Status:** Not Started

- [ ] Select highest-scored artifact
- [ ] Configurable metric
- [ ] Tie-breaking logic

**Test:**
```python
pytest tests/combine/test_best_of_n.py -v
```

---

### M6.3 — Intelligent Merge Strategy
**Status:** Not Started

- [ ] LLM-assisted merging
- [ ] Deduplication
- [ ] Citation preservation

**Test:**
```python
pytest tests/combine/test_intelligent_merge.py -v
```

---

## Phase 7: CLI (Step 12)

### M7.1 — CLI Framework
**Status:** Not Started

- [ ] Typer app setup
- [ ] Global options (--api-url, --format, --verbose)
- [ ] Entry point `acm2` command

**Test:**
```powershell
acm2 --help
acm2 --version
```

---

### M7.2 — Server Commands
**Status:** Not Started

- [ ] `acm2 serve` starts server
- [ ] `--port`, `--host` options
- [ ] `--open` opens browser

**Test:**
```powershell
acm2 serve --port 9000 &
curl http://127.0.0.1:9000/api/v1/health
```

---

### M7.3 — Run Commands
**Status:** Not Started

- [ ] `acm2 runs list`
- [ ] `acm2 runs create`
- [ ] `acm2 runs get <id>`
- [ ] `acm2 runs start <id>`
- [ ] `acm2 runs cancel <id>`

**Test:**
```python
pytest tests/cli/test_runs.py -v
```

---

## Phase 8: Web GUI (Step 11)

### M8.1 — UI Build Setup
**Status:** Complete

- [x] React + Vite configured
- [x] Tailwind CSS configured
- [x] `npm run dev` works
- [x] `npm run build` produces dist/

**Test:**
```powershell
cd acm2/ui
npm install
npm run build
```

---

### M8.2 — Run List Page
**Status:** Complete

- [x] Lists runs with status badges
- [x] Filtering by status
- [x] Pagination
- [x] "New Run" button

**Test:** Manual browser test

---

### M8.3 — Run Detail Page
**Status:** Complete

- [x] Shows run configuration
- [x] Document list with status
- [x] Progress tracking
- [x] Action buttons (Start, Cancel)

**Test:** Manual browser test

---

### M8.4 — Static File Serving
**Status:** Complete

- [x] FastAPI serves built UI
- [x] SPA fallback to index.html
- [x] Single `acm2 serve` command

**Test:**
```powershell
acm2 serve
# Open http://localhost:8000 in browser
```

---

## Summary

| Phase | Milestones | Complete | In Progress | Not Started |
|-------|------------|----------|-------------|-------------|
| 1. Foundation | 8 | 1 | 0 | 7 |
| 2. Run/Document | 7 | 0 | 0 | 7 |
| 3. Storage | 3 | 0 | 0 | 3 |
| 4. FPF Adapter | 4 | 0 | 0 | 4 |
| 5. Evaluation | 5 | 0 | 0 | 5 |
| 6. Combine | 3 | 0 | 0 | 3 |
| 7. CLI | 3 | 0 | 0 | 3 |
| 8. Web GUI | 4 | 0 | 0 | 4 |
| **Total** | **37** | **1** | **0** | **36** |

---

## Quick Test Commands

Run all unit tests:
```powershell
cd acm2
pytest tests/unit -v
```

Run all integration tests:
```powershell
pytest tests/integration -v
```

Run full test suite with coverage:
```powershell
pytest tests/ -v --cov=app --cov-report=term-missing
```

Type checking:
```powershell
mypy app/
```

Linting:
```powershell
ruff check app/
```
