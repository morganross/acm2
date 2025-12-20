# ACM 2.0 Development Steps

This document is about **how to proceed with development of ACM 2.0**, not listing features or low-level code details.

> **VOCABULARY NOTE**: See `docs/VOCABULARY.md` for official terminology. The word "phase" is reserved for pipeline stages (Generation Phase, Eval Phase, Combine Phase, Post-Combine Eval Phase). Development milestones use "Step".

## Step 0 – Clarify goals and boundaries

1. **Write a short ACM 2.0 one-pager**  
   - Summarize what ACM 2.0 is for (runs, documents, artifacts, reports).  
   - Explicitly state: API-first, web GUI, GitHub-backed storage, FPF/GPT‑R as adapters.

2. **List what must be preserved from the current system**  
   - File-based skip logic, robustness of FPF, HTML reporting, ability to re-execute single docs.  
   - Note cases where the current behavior is fragile and should *not* be carried over ("recent files" heuristics, over-coupled paths, etc.).

## Step 1 – Define the core data model and API

3. **Define core domain objects on paper**  
   - `Run`, `Document`, `Artifact`, `StorageLocation`, `FpfRunResult`, `EvalRunResult`.  
   - Sketch their key fields and relationships, ignoring implementation details.

4. **Design the initial HTTP/JSON API**  
   - List endpoints like `/runs`, `/documents`, `/artifacts`, `/evals`.  
   - For each, specify inputs, outputs, and how they reference each other (ids, paths, GitHub refs).

5. **Decide on storage and database choices**  
   - Choose a simple database for ACM state (e.g. SQLite first).  
   - Confirm GitHub as the first `StorageProvider` for documents and artifacts (with room for others later).

## Step 2 – Build the minimal backend (API-first)

6. **Set up the ACM 2.0 backend project**  
   - Create a new Python service (e.g. FastAPI) under `acm2/`.  
   - Add basic wiring: configuration, logging, database connection, health check endpoint.

7. **Implement the minimal run/document lifecycle**  
   - Implement APIs to: create a run, attach documents (by GitHub path or local path), and list runs/documents.  
   - Store run and document metadata in the database; do *not* integrate LLMs or FPF yet.

8. **Introduce the `StorageProvider` abstraction**  
   - Define an interface for reading/writing documents and artifacts (initial implementation: GitHub and local filesystem).  
   - Make all file operations in the backend go through this abstraction.

## Step 3 – Integrate FPF and evaluation

9. **Integrate the FPF adapter**  
   - Use the FPF adapter (see `FPF_DEVELOPMENT_STEPS.md`) as the only way ACM 2.0 calls FPF.  
   - Add API operations to execute FPF for a run/doc and record `FpfRunResult` in the database.

10. **Wire up evaluation and reporting**  
    - Decide how eval results are represented as artifacts (DBs, CSVs, HTML).  
    - Add endpoints to trigger evaluations and to list/download eval artifacts for a run.

## Step 4 – Web GUI and UX

11. **Build a simple web GUI on top of the API**  
    - **Status: COMPLETE**
    - Implement a minimal frontend that can: list runs, show documents, display status, and link to HTML reports.  
    - Ensure the GUI only talks to the backend API, never to files directly.
    - Built with React + Vite + Tailwind CSS.
    - Served by FastAPI backend at `/` (SPA fallback) and `/api/v1` (API).

The new web GUI in ACM 2.0 has exactly the same functionality as the desktop GUI. Every single part of it.

## Step 5 – CLI and Deployment

12. **Implement the `acm2` CLI**
    - **Status: COMPLETE**
    - Create command-line interface: `acm2 serve`, `acm2 runs create`, `acm2 runs list`, etc.
    - CLI calls the same API endpoints as the web GUI.
    - Support both interactive use and scripting/automation.
    - Quick usage: `acm2 serve --port 8002` (SPA at `/`, API at `/api/v1`); `acm2 runs list`; `acm2 runs create --name demo --documents doc1 --models gpt-4o`; `acm2 runs start <id>`; `acm2 presets list`; `acm2 presets execute <preset_id>`.

13. **Deployment and packaging**
    - **Status: COMPLETE**
    - Runs on Windows, Linux, macOS. No Docker.
    - Installation: `pip install acm2` (Python package only).
    - Run `acm2 serve` to start the web app (serves SPA at `/`, API at `/api/v1`).

## Step 6 – Authentication and API Access

14. **API key management**
    - **Status: COMPLETE**
    - Single API key stored in `.env` file (`~/.acm2/.env` or `./acm2.env`).
    - Backend checks `Authorization: Bearer <key>` header.
    - No database, no scopes, no revocation endpoints.
    - Configure rate limits via `RATE_LIMIT_MAX_REQUESTS` / `RATE_LIMIT_WINDOW_SECONDS`; defaults: 120 req/60s.

15. **Rate limiting**
    - **Status: COMPLETE**
    - Add per-key rate limits to prevent abuse.
    - Generous limits for single-user self-hosted mode.
    - Configurable for future SaaS deployment.

## Step 7 – Generator Adapters

16. **GPT-R adapter**
    - **Status: COMPLETE**
    - Wrap GPT-Researcher as a clean adapter (like FPF adapter).
    - Isolate subprocess management, environment variables, output parsing.
    - Support both standard GPT-R and Deep Research modes.

17. **Combine integration**
    - **Status: COMPLETE**
    - Implement the Combine Phase as an adapter.
    - Takes winner artifacts, produces combined output.
    - Configurable model selection for combine step.

## Step 8 – Evaluation Integration

**IMPORTANT: Evaluation Flow Timing**

The evaluation pipeline has specific timing requirements:

```
┌─────────────────────────────────────────────────────────────────────┐
│  GENERATION PHASE                                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                          │
│  │ Doc 1    │  │ Doc 2    │  │ Doc 3    │  ... (parallel gen)      │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                          │
│       │             │             │                                  │
│       ▼             ▼             ▼                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                          │
│  │Single    │  │Single    │  │Single    │  ← STREAMING: Each doc   │
│  │Eval 1    │  │Eval 2    │  │Eval 3    │    evaluated immediately │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘    after generation      │
│       │             │             │                                  │
└───────┴─────────────┴─────────────┴──────────────────────────────────┘
                      │
                      ▼  (wait for ALL single evals to complete)
┌─────────────────────────────────────────────────────────────────────┐
│  PAIRWISE PHASE (batch, after all single evals)                     │
│                                                                      │
│  1. Collect all single-eval scores                                  │
│  2. Filter to Top-N by avg score (efficiency optimization)          │
│  3. Run pairwise tournament: A vs B, A vs C, B vs C, ...           │
│  4. Calculate Elo ratings from pairwise results                     │
│  5. Determine final winner                                          │
└─────────────────────────────────────────────────────────────────────┘
```

- **Single-doc eval** = STREAMING (per-document, immediately after gen)
- **Pairwise eval** = BATCH (after all single evals complete)

18. **Single-doc evaluation**
    - **Status: COMPLETE**
    - Runs immediately after each document generation completes.
    - Endpoint to trigger single-document graded evaluation.
    - Store results in evaluation database.
    - Support multiple judges and iterations.
    - Returns scores per criterion (1-5 scale).

19. **Pairwise evaluation**
    - **Status: COMPLETE**
    - Runs ONLY after all single-doc evaluations are complete.
    - Endpoint to trigger pairwise comparison between artifacts.
    - Uses single-eval scores for Top-N filtering (efficiency).
    - Elo rating calculation and persistence.
    - Returns final rankings.

20. **Post-Combine evaluation**
    - **Status: COMPLETE**
    - Evaluate combined artifacts after Combine Phase.
    - Same evaluation logic, different input artifacts.
    - Combined docs enter pairwise directly (skip single eval or run it).


MOST IMPORTANT - MORGAN'S NOTES (I'M MORGAN)

Do not re-use old code from ACM 1.0. Think about industry standard best practices and use that.

No single file may be over 800 lines. We want functions in their own files when applicable.

**ACM 2.0 does NOT use MA (Multi-Agent)**. ACM 1.0 used MA, but we are removing it entirely from ACM 2.0. The only generators in ACM 2.0 are FPF and GPT-R.

**Platform:** Windows, Linux, macOS. Python + SQLite. No Docker.

