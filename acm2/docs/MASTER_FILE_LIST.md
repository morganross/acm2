# ACM 2.0 Master File List

This document lists all files and folders required for the ACM 2.0 software, extracted from the implementation specification documents.

---

## Root Directory (`acm2/`)
- `pyproject.toml` — Package definition, dependencies, tools
- `alembic.ini` — Database migrations config
- `Makefile` — Task runner (cross-platform via make)
- `.env.example` — Environment variable template
- `.gitignore`
- `README.md`

---

## App Directory (`app/`)

### Core Files
- `app/__init__.py`
- `app/main.py` — FastAPI app factory
- `app/config.py` — Pydantic settings (Settings, DatabaseSettings, GitHubSettings, LoggingSettings)

### Core Utilities (`app/core/`)
- `app/core/__init__.py`
- `app/core/paths.py` — PathUtils for path normalization

### API Layer (`app/api/`)
- `app/api/__init__.py`
- `app/api/router.py` — Main router aggregating all routes
- `app/api/exception_handlers.py` — Domain → HTTP error mapping
- `app/api/health.py` — Health check endpoint
- `app/api/routes/__init__.py`
- `app/api/routes/runs.py` — Run endpoints
- `app/api/routes/documents.py` — Document endpoints
- `app/api/routes/generation.py` — Generation endpoints (FPF/GPTR trigger)
- `app/api/routes/artifacts.py` — Artifact endpoints
- `app/api/routes/evaluation.py` — Evaluation endpoints
- `app/api/routes/reports.py` — Report endpoints
- `app/api/routes/combine.py` — Combine endpoints
- `app/api/schemas/__init__.py`
- `app/api/schemas/runs.py` — Run request/response schemas
- `app/api/schemas/documents.py` — Document request/response schemas

### Domain Layer (`app/domain/`)
- `app/domain/__init__.py`
- `app/domain/exceptions.py` — Domain exceptions (RunNotFoundError, etc.)
- `app/domain/models/__init__.py`
- `app/domain/models/enums.py` — RunStatus, DocumentStatus, etc.
- `app/domain/models/run.py` — Run domain model
- `app/domain/models/document.py` — Document domain model
- `app/domain/models/artifact.py` — Artifact domain model
- `app/domain/models/value_objects.py` — RunConfig, GeneratorConfig, etc.

### Services Layer (`app/services/`)
- `app/services/__init__.py`
- `app/services/dependencies.py` — FastAPI dependency injection
- `app/services/health_service.py` — Health check service
- `app/services/run_service.py` — Run business logic
- `app/services/document_service.py` — Document business logic
- `app/services/generation_service.py` — Orchestrates generation
- `app/services/generation_task.py` — Background task management

### Infrastructure Layer (`app/infra/`)
- `app/infra/__init__.py`
- `app/infra/logging.py` — Structured logging setup
- `app/infra/telemetry.py` — OpenTelemetry (optional)

#### Database (`app/infra/db/`)
- `app/infra/db/__init__.py`
- `app/infra/db/base.py` — SQLAlchemy Base, mixins
- `app/infra/db/session.py` — DatabaseManager, get_session
- `app/infra/db/models/__init__.py` — Model registry
- `app/infra/db/models/run.py` — RunModel
- `app/infra/db/models/document.py` — DocumentModel
- `app/infra/db/models/run_document.py` — RunDocument junction
- `app/infra/db/models/artifact.py` — ArtifactModel
- `app/infra/db/repositories/__init__.py` — Repository registry
- `app/infra/db/repositories/base.py` — BaseRepository
- `app/infra/db/repositories/run_repository.py`
- `app/infra/db/repositories/document_repository.py`
- `app/infra/db/repositories/run_document_repository.py`
- `app/infra/db/repositories/artifact_repository.py`

#### Storage (`app/infra/storage/`)
- `app/infra/storage/__init__.py` — Export public API
- `app/infra/storage/types.py` — StorageFile, StorageCommit, StorageError, enums
- `app/infra/storage/provider.py` — StorageProvider ABC
- `app/infra/storage/github_provider.py` — GitHubStorageProvider
- `app/infra/storage/local_provider.py` — LocalStorageProvider
- `app/infra/storage/factory.py` — create_storage_provider()

#### Rate Limiting (`app/infra/rate_limiting/`)
- `app/infra/rate_limiting/__init__.py`
- `app/infra/rate_limiting/bucket.py` — RateLimitBucket, RateLimitKey, RateLimitPermit
- `app/infra/rate_limiting/limiter.py` — RateLimiter class
- `app/infra/rate_limiting/header_parsers.py` — Provider-specific header parsers
- `app/infra/rate_limiting/config.py` — RateLimitConfig, default limits

### Middleware (`app/middleware/`)
- `app/middleware/__init__.py`
- `app/middleware/request_id.py` — X-Request-ID injection
- `app/middleware/error_handler.py` — Global exception handling

### Adapters (`app/adapters/`)
- `app/adapters/__init__.py` — Export adapters
- `app/adapters/base.py` — GeneratorAdapter ABC

#### FPF Adapter (`app/adapters/fpf/`)
- `app/adapters/fpf/__init__.py` — Export FpfAdapter
- `app/adapters/fpf/adapter.py` — FpfAdapter class
- `app/adapters/fpf/config.py` — FpfSettings, FpfGeneratorConfig
- `app/adapters/fpf/result.py` — FpfResult, FpfMetadata
- `app/adapters/fpf/errors.py` — FpfError subclasses
- `app/adapters/fpf/subprocess.py` — Process management helpers

#### GPT-R Adapter (`app/adapters/gptr/`)
- `app/adapters/gptr/__init__.py`
- `app/adapters/gptr/adapter.py` — GptrAdapter class
- `app/adapters/gptr/config.py` — GptrConfig, GptrSettings

### Evaluation (`app/evaluation/`)
- `app/evaluation/__init__.py` — Public exports
- `app/evaluation/models.py` — EvalResult, PairwiseResult, CriterionScore
- `app/evaluation/single_doc.py` — SingleDocEvaluator class
- `app/evaluation/pairwise.py` — PairwiseEvaluator class
- `app/evaluation/elo.py` — EloCalculator class
- `app/evaluation/orchestrator.py` — EvalOrchestrator class
- `app/evaluation/aggregator.py` — ResultAggregator class
- `app/evaluation/mock.py` — MockSingleEvaluator, MockPairwiseEvaluator

#### Evaluation Prompts (`app/evaluation/prompts/`)
- `app/evaluation/prompts/single_doc.txt` — Prompt template for single-doc eval
- `app/evaluation/prompts/pairwise.txt` — Prompt template for pairwise comparison

#### Evaluation Reports (`app/evaluation/reports/`)
- `app/evaluation/reports/__init__.py`
- `app/evaluation/reports/generator.py` — HtmlReportGenerator class
- `app/evaluation/reports/templates/base.html` — Base Jinja2 template
- `app/evaluation/reports/templates/eval_report.html` — Full evaluation report
- `app/evaluation/reports/templates/partials/scores_table.html`
- `app/evaluation/reports/templates/partials/rankings.html`
- `app/evaluation/reports/templates/partials/comparisons.html`

### Combine (`app/combine/`)
- `app/combine/__init__.py`
- `app/combine/service.py` — CombinerService
- `app/combine/strategies/__init__.py`
- `app/combine/strategies/concatenate.py` — ConcatenateCombiner
- `app/combine/strategies/best_of_n.py` — BestOfNCombiner
- `app/combine/strategies/section_assembly.py` — SectionAssemblyCombiner
- `app/combine/strategies/intelligent_merge.py` — IntelligentMergeCombiner
- `app/combine/source_handler.py` — SourceHandler for GPT-R sources

### Schemas (`app/schemas/`)
- `app/schemas/__init__.py`
- `app/schemas/combine.py` — CombineConfig, CombineResult, CombineStrategy
- `app/schemas/gptr.py` — GptrConfig, GptrRunResult, GptrSource

---

## CLI Directory (`app/cli/`)
- `app/cli/__init__.py` — Package exports
- `app/cli/main.py` — Entry point, Typer app, global options
- `app/cli/client.py` — ApiClient, AsyncApiClient
- `app/cli/config.py` — ConfigManager, get_config_path
- `app/cli/output.py` — Formatting utilities
- `app/cli/progress.py` — Progress bars and spinners
- `app/cli/errors.py` — Error handling, exit codes
- `app/cli/completion.py` — Dynamic completion helpers
- `app/cli/interactive.py` — Interactive REPL mode (optional)
- `app/cli/commands/__init__.py`
- `app/cli/commands/serve.py` — acm2 serve command
- `app/cli/commands/runs.py` — acm2 runs subcommands
- `app/cli/commands/docs.py` — acm2 docs subcommands
- `app/cli/commands/eval.py` — acm2 eval subcommands
- `app/cli/commands/reports.py` — acm2 reports subcommands
- `app/cli/commands/config.py` — acm2 config subcommands

---

## Migrations Directory (`alembic/`)
- `alembic/env.py` — Alembic configuration
- `alembic/script.py.mako`
- `alembic/versions/` — Migration scripts folder
- `alembic/versions/001_initial_run_document.py` — Initial migration

### Database Migrations (by feature)
- `migrations/versions/010_eval_tables.sql` — Eval schema migration (if SQL-based)

---

## Tests Directory (`tests/`)
- `tests/__init__.py`
- `tests/conftest.py` — Shared fixtures
- `tests/factories.py` — Test factories (ArtifactFactory, etc.)

### Unit Tests (`tests/unit/`)
- `tests/unit/__init__.py`
- `tests/unit/services/test_run_service.py`
- `tests/unit/services/test_document_service.py`
- `tests/unit/repositories/test_run_repository.py`
- `tests/unit/adapters/__init__.py`
- `tests/unit/adapters/fpf/__init__.py`
- `tests/unit/adapters/fpf/test_adapter.py`
- `tests/unit/adapters/fpf/test_config.py`
- `tests/unit/adapters/fpf/test_skip_logic.py`
- `tests/unit/storage/test_github_provider.py`
- `tests/unit/storage/test_local_provider.py`

### Integration Tests (`tests/integration/`)
- `tests/integration/__init__.py`
- `tests/integration/api/test_runs_api.py`
- `tests/integration/api/test_documents_api.py`
- `tests/integration/test_fpf_adapter.py`
- `tests/integration/test_storage_integration.py`

### Evaluation Tests (`tests/evaluation/`)
- `tests/evaluation/__init__.py`
- `tests/evaluation/test_single_doc_evaluator.py`
- `tests/evaluation/test_pairwise_evaluator.py`
- `tests/evaluation/test_elo_calculator.py`
- `tests/evaluation/test_eval_orchestrator.py`
- `tests/evaluation/test_result_aggregator.py`
- `tests/evaluation/test_html_report_generator.py`
- `tests/evaluation/test_evaluation_integration.py`

### CLI Tests (`tests/cli/`)
- `tests/cli/__init__.py`
- `tests/cli/conftest.py` — Test fixtures
- `tests/cli/test_main.py`
- `tests/cli/test_runs.py`
- `tests/cli/test_docs.py`
- `tests/cli/test_eval.py`
- `tests/cli/test_reports.py`
- `tests/cli/test_config.py`
- `tests/cli/test_client.py`
- `tests/cli/test_output.py`
- `tests/cli/test_errors.py`

### Test Fixtures (`tests/fixtures/`)
- `tests/fixtures/mock_fpf.py` — Mock FPF script for testing

---

## Scripts Directory (`scripts/`)
- `scripts/__init__.py`
- `scripts/check_line_length.py` — Enforce <800 lines rule
- `scripts/run_dev.py` — Development server launcher

---

## UI Directory (`ui/`)

### Root Config
- `ui/package.json`
- `ui/tailwind.config.js`
- `ui/tsconfig.json`
- `ui/vite.config.ts`
- `ui/components.json` — shadcn/ui config
- `ui/index.html` — HTML entry point

### Source (`ui/src/`)
- `ui/src/main.tsx` — React entry point
- `ui/src/App.tsx` — App root with routing
- `ui/src/index.css` — Global styles (Tailwind imports)

#### Pages (`ui/src/pages/`)
- `ui/src/pages/Layout.tsx` — App shell with nav
- `ui/src/pages/Dashboard.tsx` — Dashboard / home
- `ui/src/pages/Configure.tsx` — ACM 1.0-style config page (main)
- `ui/src/pages/RunList.tsx` — Run list
- `ui/src/pages/RunNew.tsx` — Create run wizard
- `ui/src/pages/RunDetail.tsx` — Run detail
- `ui/src/pages/RunCombine.tsx` — Combine artifacts
- `ui/src/pages/Documents.tsx` — Document browser
- `ui/src/pages/Settings.tsx` — Settings page

#### API Client (`ui/src/api/`)
- `ui/src/api/client.ts` — API client with fetch wrapper
- `ui/src/api/runs.ts` — Run API functions
- `ui/src/api/documents.ts` — Document API functions
- `ui/src/api/execution.ts` — Generate/Evaluate API functions

#### Components (`ui/src/components/`)
- `ui/src/components/RunCard.tsx` — Run card for list view
- `ui/src/components/RunStatusBadge.tsx` — Status badge component
- `ui/src/components/DocumentPicker.tsx` — Document selection (recent + GitHub)
- `ui/src/components/GeneratorConfig.tsx` — Generator configuration (legacy)
- `ui/src/components/EvalConfig.tsx` — Evaluation configuration (legacy)

#### Config Components (`ui/src/components/config/`) — ACM 1.0 Parity
- `ui/src/components/config/ProvidersPanel.tsx` — FPF/GPTR/DR/MA model checkboxes
- `ui/src/components/config/ModelCheckboxList.tsx` — Reusable multi-select checkboxes
- `ui/src/components/config/PathsEvalPanel.tsx` — Paths + evaluation settings
- `ui/src/components/config/GptrParamsPanel.tsx` — All 20+ sliders
- `ui/src/components/config/CombinePanel.tsx` — Combine & revise settings
- `ui/src/components/config/RuntimeMetrics.tsx` — Progress metrics bar
- `ui/src/components/config/ActionButtons.tsx` — Bottom action buttons
- `ui/src/components/config/PresetSelector.tsx` — Preset dropdown

#### Hooks (`ui/src/hooks/`)
- `ui/src/hooks/useConfig.ts` — Config state hook
- `ui/src/hooks/usePresets.ts` — Presets hook

#### Stores (`ui/src/stores/`)
- `ui/src/stores/config.ts` — RunConfig store (all settings)
- `ui/src/stores/presets.ts` — Presets store (load/save/apply)
- `ui/src/stores/modelCatalog.ts` — Available models per generator
- `ui/src/stores/run.ts` — Current run state/progress
- `ui/src/stores/settings.ts` — User settings store

#### Types (`ui/src/types/`)
- `ui/src/types/run.ts` — Run type definitions
- `ui/src/types/config.ts` — Config type definitions (RunConfig, etc.)
- `ui/src/types/document.ts` — Document type definitions

#### Lib (`ui/src/lib/`)
- `ui/src/lib/utils.ts` — Utility functions

#### Static (`ui/public/`)
- `ui/public/favicon.png`

---

## Docs Directory (`docs/`)
- `docs/setup.md` — Developer setup guide
- `docs/adr/0001-project-structure.md` — Architecture Decision Record

---

## Summary Statistics

| Category | File Count |
|----------|------------|
| Root Config | 6 |
| App Core | 3 |
| API Layer | 14 |
| Domain Layer | 8 |
| Services Layer | 7 |
| Infrastructure (DB) | 15 |
| Infrastructure (Storage) | 6 |
| Infrastructure (Rate Limiting) | 5 |
| Middleware | 3 |
| Adapters | 12 |
| Evaluation | 17 |
| Combine | 7 |
| Schemas | 3 |
| CLI | 17 |
| Migrations | 3 |
| Tests | 35 |
| Scripts | 3 |
| UI | 33 |
| Docs | 2 |
| **TOTAL** | **~199** |

### UI File Breakdown

| UI Category | File Count |
|-------------|------------|
| Root Config | 6 |
| Source Core | 3 |
| Pages | 9 |
| API Client | 4 |
| Components | 5 |
| Config Components | 8 |
| Hooks | 2 |
| Stores | 5 |
| Types | 3 |
| Lib | 1 |
| Static | 1 |
| **UI Total** | **47** |
| UI | 24 |
| Docs | 2 |
| **Total** | **~180 files** |
