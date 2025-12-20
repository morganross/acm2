# ACM Technical Deep Dive

## Document Purpose

This document provides a **code-level** understanding of how the Advanced Comparison Manager (ACM) currently works. It includes pseudo-code for all major flows, documents edge cases, error handling patterns, and internal state management.

**Target Audience**: LLMs and developers implementing ACM 2.0.

---

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [Entry Point & Initialization](#2-entry-point--initialization)
3. [Skip Logic (Phase 1)](#3-skip-logic-phase-1)
4. [Generation Phase](#4-generation-phase)
   - 4.1 [FPF Batch Processing](#41-fpf-batch-processing)
   - 4.2 [GPT-Researcher Subprocess](#42-gpt-researcher-subprocess)
   - 4.3 [Multi-Agent Runner](#43-multi-agent-runner)
5. [Output Management](#5-output-management)
6. [Evaluation Phase](#6-evaluation-phase)
   - 6.1 [Streaming Single-Doc Eval](#61-streaming-single-doc-eval)
   - 6.2 [Single-Doc Evaluation](#62-single-doc-evaluation)
   - 6.3 [Pairwise (Elo) Evaluation](#63-pairwise-elo-evaluation)
7. [Combination Phase (Playoffs)](#7-combination-phase-playoffs)
8. [Concurrency Control](#8-concurrency-control)
9. [Edge Cases & Error Handling](#9-edge-cases--error-handling)
10. [Data Structures & State](#10-data-structures--state)
11. [File Naming Conventions](#11-file-naming-conventions)
12. [Key Constants & Configuration](#12-key-constants--configuration)

---

## 1. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           runner.py :: main()                                │
│                                                                              │
│  ┌──────────────┐    ┌──────────────────────┐    ┌─────────────────────┐   │
│  │ SKIP CHECK   │───▶│  GENERATION PHASE    │───▶│  EVALUATION PHASE   │   │
│  │ (per file)   │    │  (FPF/GPTR/DR/MA)    │    │  (single + pairwise)│   │
│  └──────────────┘    └──────────────────────┘    └─────────────────────┘   │
│         │                      │                            │               │
│         ▼                      ▼                            ▼               │
│  ┌──────────────┐    ┌──────────────────────┐    ┌─────────────────────┐   │
│  │ Check 3 dirs:│    │ StreamingEvalManager │    │ trigger_evaluation_ │   │
│  │ - eval_out   │    │ spawns eval as files │    │ for_all_files()     │   │
│  │ - winners    │    │ complete             │    │                     │   │
│  │ - gen_output │    └──────────────────────┘    └─────────────────────┘   │
│  └──────────────┘                                          │               │
│                                                            ▼               │
│                                               ┌─────────────────────────┐  │
│                                               │ Optional: Playoffs      │  │
│                                               │ (combiner.py + re-eval) │  │
│                                               └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Entry Point & Initialization

### File: `runner.py :: main()`

```pseudo
FUNCTION main():
    # Parse CLI arguments
    args = parse_args()
    config_path = args.config OR "config.yaml"
    
    # Load configuration
    config = load_yaml(config_path)
    
    # Initialize logging
    setup_logging(config)
    
    # Record batch start time (used for file discovery)
    batch_start_ts = time.time()
    
    # Initialize heartbeat thread
    hb_thread = start_heartbeat_thread(batch_start_ts)
    
    # Initialize StreamingEvalManager if enabled
    IF config.eval.auto_run AND config.eval.streaming_single_eval:
        STREAMING_EVAL_MANAGER = StreamingEvalManager(
            db_path = generate_unique_db_path(),
            config_path = eval_config_path,
            iterations = config.eval.iterations
        )
    
    # Find all markdown files in input folder
    markdown_files = file_manager.find_markdown_files(input_folder)
    
    # Process each file
    FOR md_file IN markdown_files:
        IF skip_check(md_file):
            CONTINUE  # Skip this file
        
        # Split runs by type
        fpf_runs, gptr_runs, dr_runs, ma_runs = categorize_runs(config.runs)
        
        # Execute generation (details in Section 4)
        generated_files = await execute_generation(md_file, fpf_runs, gptr_runs, dr_runs, ma_runs)
        
        # Wait for streaming evals (if enabled)
        IF STREAMING_EVAL_MANAGER:
            await STREAMING_EVAL_MANAGER.wait_all()
    
    # Trigger batch evaluation
    await trigger_evaluation_for_all_files(output_folder, config, ...)
    
    # Generate timeline and HTML report
    generate_timeline_json(subproc_log_path)
    open_master_html_report()
```

### Initialization Edge Cases

| Edge Case | Handling |
|-----------|----------|
| Missing config.yaml | Exit with error message |
| Invalid YAML syntax | Python exception, graceful exit |
| Missing input_folder | Exit with error message |
| Empty markdown_files list | Warn and exit (no work to do) |
| StreamingEvalManager init fails | Set to None, continue without streaming |

---

## 3. Skip Logic (Phase 1)

**Critical**: Skip check happens **BEFORE** generation, not after.

### File: `runner.py` (lines ~2040-2090)

```pseudo
FUNCTION skip_check(md_file) -> bool:
    base_name = get_basename_without_extension(md_file)
    
    # CHECK 1: Eval Output Directory
    IF config.eval.auto_run:
        eval_out_dir = resolve_path(config.eval.output_directory)
        FOR file IN recursive_walk(eval_out_dir):
            IF file.startswith(base_name + "."):
                LOG "Skipping {md_file} (found eval output: {file})"
                RETURN True  # SKIP
    
    # CHECK 2: Winners Directory
    winners_dir = join(parent_of(output_folder), "winners", relative_dir_of(md_file))
    IF exists(winners_dir):
        existing_winners = [f for f in listdir(winners_dir) 
                           if f.startswith(base_name + ".") 
                           and f.endswith((".md", ".txt"))]
        IF existing_winners:
            LOG "Skipping {md_file} (found existing winner: {existing_winners[0]})"
            RETURN True  # SKIP
    
    # CHECK 3: Generation Output Directory
    output_dir_for_file = mirror_input_structure(md_file, output_folder)
    IF exists(output_dir_for_file):
        existing = [f for f in listdir(output_dir_for_file)
                   if f.startswith(base_name + ".")
                   and f.endswith((".md", ".json", ".txt", ".docx", ".pdf"))]
        IF existing:
            LOG "Skipping {md_file} (found {len(existing)} existing outputs)"
            RETURN True  # SKIP
    
    RETURN False  # DO NOT SKIP
```

### Skip Logic Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| Pattern `base_name.*` matches unrelated file | False positive skip (known limitation) |
| Partial/corrupt output files exist | Still triggers skip (no content validation) |
| Multiple files with same base_name in different dirs | Each checked independently |
| Eval output in subdirectory | Recursive walk finds it |
| Permission error on directory | Warning logged, check continues |

---

## 4. Generation Phase

### 4.1 FPF Batch Processing

**File**: `runner.py :: process_file_fpf_batch()` and `functions/fpf_runner.py`

#### Batch Architecture

```pseudo
FUNCTION process_file_fpf_batch(md_file, config, fpf_entries, iterations):
    # Group entries by provider for execution order
    openaidp_entries = [e for e in fpf_entries if e.provider == "openaidp"]
    rest_entries = [e for e in fpf_entries if e.provider != "openaidp"]
    
    # Create inflight tracker for watermark gating
    tracker = FpfInflightTracker({
        "rest": len(rest_entries) * iterations,
        "deep": len(openaidp_entries) * iterations
    })
    
    # Execute OpenAI DP entries first (T1 quota), then rest
    await run_fpf_batch("rest", rest_entries, tracker)
    await run_fpf_batch("deep", openaidp_entries, tracker)
```

#### FPF Subprocess Protocol

**File**: `functions/fpf_runner.py :: run_filepromptforge_batch()`

```pseudo
FUNCTION run_filepromptforge_batch(file_a, file_b, runs_list, options) -> list[(path, model)]:
    """
    runs_list format: [
        {"provider": "openai", "model": "gpt-4o", "iterations": 3, "kind": "fpf"},
        ...
    ]
    """
    
    # Build command with stdin JSON protocol
    cmd = [python, "-u", fpf_main_path, "--config", config, "--stdin-json"]
    
    # Prepare runs JSON for stdin
    runs_json = {
        "runs": runs_list,
        "file_a": file_a,
        "file_b": file_b,
        "output_dir": output_dir
    }
    
    # Spawn subprocess
    proc = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    proc.stdin.write(json.dumps(runs_json))
    proc.stdin.close()
    
    # Parse results from stdout
    results = []
    FOR line IN proc.stdout:
        IF line.startswith("{"):
            event = json.loads(line)
            IF event.type == "run_complete" AND event.data.ok:
                results.append((event.data.path, event.data.model))
            
            # Trigger streaming eval callback
            IF on_event:
                on_event(event)
    
    RETURN results
```

#### FPF 4-Layer Retry System

```pseudo
FUNCTION run_fpf_with_retry(file_a, file_b, run_index, options) -> (path, model):
    """
    4-Layer validation retry system for Google provider grounding issues.
    """
    
    # LAYER 1: Initial run with enhanced preamble (if Google)
    IF is_google_provider(options):
        file_a = ensure_enhanced_instructions(file_a, "initial")
    
    result = run_fpf_subprocess(file_a, file_b, options)
    exit_code = result.returncode
    
    # Exit codes: 0=success, 1=missing_grounding, 2=missing_reasoning, 3=both, 4=unknown
    IF exit_code == 0:
        # LAYER 2: Fallback detection - check for FAILURE-REPORT.json
        recent_failures = scan_validation_log_dir(last_5_seconds=True)
        IF recent_failures:
            exit_code = determine_exit_code_from_failure_report(recent_failures[0])
    
    IF exit_code != 0:
        # LAYER 3: Determine failure type
        failure_type = map_exit_code_to_failure_type(exit_code)
        # 1 -> "grounding", 2 -> "reasoning", 3 -> "both", 4 -> "both"
        
        # LAYER 4: Retry with validation-enhanced instructions
        FOR attempt IN [1, 2, 3]:
            enhanced_file_a = ensure_enhanced_instructions_validation(
                file_a, failure_type, attempt
            )
            result = run_fpf_subprocess(enhanced_file_a, file_b, options)
            IF result.returncode == 0:
                BREAK
    
    RETURN (result.path, result.model)
```

### 4.2 GPT-Researcher Subprocess

**File**: `runner.py :: process_file_run()` (rtype="gptr"/"dr")

```pseudo
FUNCTION run_gptr_subprocess(query_prompt, report_type, target_model) -> (path, model):
    """
    Spawns gptr_subprocess.py with model override via environment variables.
    """
    
    # Write prompt to temp file (race condition workaround)
    tmp_prompt_path = write_temp_file(query_prompt)
    
    # Build command
    cmd = [python, "-u", "functions/gptr_subprocess.py",
           "--prompt-file", tmp_prompt_path,
           "--report-type", report_type]
    
    # Set environment for model override
    env = os.environ.copy()
    env["SMART_LLM"] = target_model
    env["STRATEGIC_LLM"] = target_model
    env["FAST_LLM"] = target_model
    env["PYTHONIOENCODING"] = "utf-8"
    
    # Spawn with streaming output
    proc = Popen(cmd, stdout=PIPE, stderr=PIPE, env=env)
    
    # Stream stdout/stderr to console (reader threads)
    t_out = Thread(target=stream_reader, args=(proc.stdout, "OUT"))
    t_err = Thread(target=stream_reader, args=(proc.stderr, "ERR"))
    
    # Wait for completion
    await asyncio.run_in_executor(None, proc.wait)
    
    # Parse JSON result from last stdout line
    IF proc.returncode == 0:
        last_json_line = find_last_json_line(stdout_lines)
        data = json.loads(last_json_line)
        RETURN (data["path"], data["model"])
    ELSE:
        # Retry once if "Prompt file not found" error
        IF "Prompt file not found" IN stderr_lines:
            rewrite_temp_file(tmp_prompt_path, query_prompt)
            fsync(tmp_prompt_path)
            result = retry_subprocess(cmd, env)
            IF result.success:
                RETURN (result.path, result.model)
        
        RAISE RuntimeError(f"GPTR subprocess failed: rc={proc.returncode}")
```

### 4.3 Multi-Agent Runner

**File**: `functions/MA_runner.py`

```pseudo
FUNCTION run_multi_agent_once(query_text, output_folder, run_index, task_config) -> list[str]:
    """
    Runs MA_CLI/Multi_Agent_CLI.py as subprocess.
    Returns list of artifact paths (markdown, docx, pdf).
    """
    
    # Write query to temp file
    tmp_query_file = write_temp_file(query_text)
    
    # Write task_config.json (strict file-based config)
    task_cfg_path = join(output_folder, "task_config.json")
    write_json(task_cfg_path, task_config)
    
    # Build command
    cmd = [python, "-u", MA_CLI_PATH,
           "--query-file", tmp_query_file,
           "--output-folder", output_folder,
           "--output-filename", f"ma_report_{run_index}_{uuid}.json",
           "--publish-markdown",
           "--task-config", task_cfg_path]
    
    # Environment setup
    env = os.environ.copy()
    env["GPTR_DISABLE_STREAMING"] = "true"  # Avoid streaming permission errors
    env["PYTHONPATH"] = prepend_local_gpt_researcher(env["PYTHONPATH"])
    
    # Record start time for artifact discovery
    start_ts = time.time()
    
    # Spawn with timeout
    proc = Popen(cmd, stdout=PIPE, stderr=PIPE, stdin=DEVNULL, cwd=local_multi_agents)
    
    TRY:
        proc.wait(timeout=TIMEOUT_SECONDS)  # 600 seconds
    EXCEPT TimeoutExpired:
        proc.kill()
        RETURN [write_failed_artifact(output_folder, "MA_CLI subprocess timed out")]
    
    IF proc.returncode != 0:
        RETURN [write_failed_artifact(output_folder, f"exit_code={proc.returncode}")]
    
    # Discover artifacts written after start_ts
    artifacts = []
    search_roots = [join(popen_cwd, "outputs"), output_folder]
    FOR root IN search_roots:
        FOR file IN recursive_walk(root):
            IF file.ext IN [".md", ".docx", ".pdf"]:
                IF file.mtime >= (start_ts - 1.0):
                    artifacts.append(file.path)
    
    IF NOT artifacts:
        RETURN [write_failed_artifact(output_folder, "No artifacts discovered")]
    
    RETURN artifacts
```

---

## 5. Output Management

### File: `functions/output_manager.py :: save_generated_reports()`

```pseudo
FUNCTION save_generated_reports(input_md_path, input_base_dir, output_base_dir, generated_paths, on_file_saved=None):
    """
    Copies generated reports to output directory, mirroring input structure.
    Triggers streaming eval callback for each saved file.
    """
    
    base_name = get_basename_without_extension(input_md_path)
    output_dir = mirror_input_structure(input_md_path, output_base_dir)
    makedirs(output_dir)
    
    saved = []
    seen_src = set()  # Deduplication
    
    # MA: Apply one_file_only policy (prefer .md > .docx > .pdf)
    ma_items = select_preferred_ma_artifact(generated_paths["ma"])
    
    FOR kind IN ["ma", "gptr", "dr", "fpf"]:
        FOR idx, (src_path, model) IN enumerate(generated_paths[kind]):
            IF src_path IN seen_src:
                CONTINUE  # Skip duplicates
            
            # Generate unique destination filename
            model_label = sanitize_model_for_filename(model)
            dest = generate_unique_dest(output_dir, base_name, kind, idx, model_label, extension)
            
            # Copy file
            shutil.copy2(src_path, dest)
            saved.append(dest)
            seen_src.add(src_path)
            
            # Notify callback (triggers streaming eval)
            IF on_file_saved:
                on_file_saved(dest)
            ELIF STREAMING_EVAL_MANAGER:
                STREAMING_EVAL_MANAGER.spawn_eval(dest)
    
    RETURN saved
```

### Unique Filename Generation

```pseudo
FUNCTION generate_unique_dest(output_dir, base_name, kind, idx, model_label, ext) -> str:
    """
    Pattern: {base_name}.{kind}.{idx}.{model_label}.{uid3}.{ext}
    Example: intro.fpf.1.gpt-4o.abc.md
    """
    
    FOR _ IN range(10):
        uid = generate_uid3()  # 3-char alphanumeric
        candidate = join(output_dir, f"{base_name}.{kind}.{idx}.{model_label}.{uid}.{ext}")
        IF NOT exists(candidate):
            RETURN candidate
    
    # Fallback with counter (extremely unlikely)
    counter = 1
    WHILE True:
        uid = generate_uid3()
        candidate = join(output_dir, f"{base_name}.{kind}.{idx}.{model_label}.{uid}-{counter}.{ext}")
        IF NOT exists(candidate):
            RETURN candidate
        counter += 1
```

---

## 6. Evaluation Phase

### 6.1 Streaming Single-Doc Eval

**File**: `runner.py :: StreamingEvalManager`

```pseudo
CLASS StreamingEvalManager:
    """
    Spawns evaluate.py --single-file subprocess as each generation file completes.
    Allows eval to run concurrently with remaining generations.
    """
    
    def __init__(self, db_path, config_path, iterations):
        self.db_path = db_path
        self.config_path = config_path
        self.iterations = iterations
        self.tasks = []
        self.results = []
        self._spawned_files = set()  # Deduplication
        self._lock = asyncio.Lock()
        self._loop = None
    
    def spawn_eval(self, file_path):
        """Spawn single-file eval. Thread-safe via run_coroutine_threadsafe."""
        
        async with self._lock:
            IF file_path IN self._spawned_files:
                RETURN  # Already spawned
            self._spawned_files.add(file_path)
        
        # Build subprocess command
        cmd = [python, "-u", "evaluate.py",
               "--single-file", file_path,
               "--db-path", self.db_path,
               "--config", self.config_path,
               "--iterations", str(self.iterations),
               "--skip-pairwise"]
        
        # Schedule async task
        IF self._loop:
            # Thread-safe scheduling from FPF callback
            future = asyncio.run_coroutine_threadsafe(
                self._run_eval_subprocess(file_path, cmd),
                self._loop
            )
            self.tasks.append(future)
        ELSE:
            task = asyncio.create_task(self._run_eval_subprocess(file_path, cmd))
            self.tasks.append(task)
    
    async def _run_eval_subprocess(self, file_path, cmd):
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        output, _ = await proc.communicate()
        
        result = {
            "file": file_path,
            "returncode": proc.returncode,
            "output": output.decode()
        }
        
        async with self._lock:
            self.results.append(result)
        
        RETURN result
    
    async def wait_all(self):
        """Wait for all spawned evals to complete."""
        
        # Separate asyncio.Task from concurrent.futures.Future
        async_tasks = [t for t in self.tasks if isinstance(t, asyncio.Task)]
        futures = [t for t in self.tasks if not isinstance(t, asyncio.Task)]
        
        IF async_tasks:
            await asyncio.gather(*async_tasks, return_exceptions=True)
        
        FOR fut IN futures:
            fut.result(timeout=1800)  # 30 min timeout
        
        RETURN self.results
```

### 6.2 Single-Doc Evaluation

**File**: `llm-doc-eval/llm_doc_eval/api.py :: run_single_evaluation()`

```pseudo
FUNCTION run_single_evaluation(
    doc_paths: list[str],
    reference_file: str,
    output_db: str,
    iterations: int = 1,
    rubric_path: str = None
) -> str:
    """
    Grades each document against a rubric (single-doc scoring).
    Returns path to SQLite database with results.
    """
    
    # Load rubric (dimensions with 1-5 scoring criteria)
    rubric = load_rubric(rubric_path)
    
    # Prepare FPF batch runs
    runs = []
    FOR doc_path IN doc_paths:
        FOR dimension IN rubric.dimensions:
            FOR i IN range(iterations):
                runs.append({
                    "doc_id": extract_doc_id(doc_path),
                    "dimension": dimension.name,
                    "prompt": build_grading_prompt(doc_path, dimension),
                    "iteration": i
                })
    
    # Execute via FPF batch
    results = fpf_runner.run_filepromptforge_batch(
        file_a = rubric_as_instructions,
        file_b = doc_content,
        runs = runs
    )
    
    # Parse scores from responses
    FOR result IN results:
        score = parse_score_from_response(result.response)
        insert_into_db(output_db, "single_doc_results", {
            "doc_id": result.doc_id,
            "dimension": result.dimension,
            "score": score,
            "iteration": result.iteration
        })
    
    RETURN output_db
```

### 6.3 Pairwise (Elo) Evaluation

**File**: `llm-doc-eval/llm_doc_eval/api.py :: run_pairwise_evaluation()`

```pseudo
FUNCTION run_pairwise_evaluation(
    doc_paths: list[str],
    reference_file: str,
    output_db: str,
    iterations: int = 1,
    top_n: int = None,
    source_db: str = None,
    new_docs_only: list[str] = None
) -> str:
    """
    Compares documents pairwise using Elo rating system.
    Optionally narrows pool to top_n based on single-doc scores.
    """
    
    # Optimization: Narrow to top N by single-doc scores
    IF top_n AND source_db:
        doc_paths = _get_top_n_docs(source_db, doc_paths, top_n)
    
    # Optimization: Copy existing single scores for unchanged docs
    IF source_db AND new_docs_only:
        _copy_single_scores_from_source_db(source_db, output_db, 
            [d for d in doc_paths if d not in new_docs_only])
    
    # Generate all pairs
    pairs = generate_pairs(doc_paths)
    
    # Optimization: If new_docs_only, only evaluate pairs containing new docs
    IF new_docs_only:
        pairs = [p for p in pairs if p[0] in new_docs_only or p[1] in new_docs_only]
    
    # Execute pairwise comparisons
    FOR (doc_a, doc_b) IN pairs:
        FOR i IN range(iterations):
            result = compare_documents(doc_a, doc_b, reference_file)
            insert_into_db(output_db, "pairwise_results", {
                "doc_a": doc_a,
                "doc_b": doc_b,
                "winner": result.winner,  # "A", "B", or "tie"
                "iteration": i
            })
    
    # Compute Elo ratings
    compute_elo_ratings(output_db)
    
    RETURN output_db

FUNCTION _get_top_n_docs(source_db, doc_paths, n) -> list[str]:
    """Select top N documents by average single-doc score."""
    
    query = """
        SELECT doc_id, AVG(score) as avg_score
        FROM single_doc_results
        WHERE doc_id IN ({placeholders})
        GROUP BY doc_id
        ORDER BY avg_score DESC
        LIMIT ?
    """
    return execute_query(source_db, query, doc_paths, n)
```

---

## 7. Combination Phase (Playoffs)

**File**: `combiner.py :: ReportCombiner`

```pseudo
CLASS ReportCombiner:
    
    def __init__(self, db_path):
        self.db_path = db_path
    
    def get_top_reports(self, n=2, metric="avg_score") -> list[str]:
        """
        Returns top N report paths from evaluation database.
        Uses AVG(score) from single_doc_results or Elo from pairwise.
        """
        
        IF metric == "avg_score":
            query = """
                SELECT doc_id, AVG(score) as avg_score
                FROM single_doc_results
                GROUP BY doc_id
                ORDER BY avg_score DESC
                LIMIT ?
            """
        ELIF metric == "elo":
            query = """
                SELECT doc_id, elo_rating
                FROM elo_ratings
                ORDER BY elo_rating DESC
                LIMIT ?
            """
        
        results = execute_query(self.db_path, query, [n])
        RETURN [row["doc_id"] for row in results]
    
    def combine(self, report_a_path, report_b_path, original_instructions_path, combine_instructions_path) -> str:
        """
        Combines two reports into a "Gold Standard" candidate using FPF.
        """
        
        # Build combined prompt
        prompt = f"""
{read_file(combine_instructions_path)}

=== ORIGINAL TASK ===
{read_file(original_instructions_path)}

=== REPORT A ===
{read_file(report_a_path)}

=== REPORT B ===
{read_file(report_b_path)}

=== YOUR TASK ===
Combine the best elements from Report A and Report B to create an improved report.
"""
        
        # Call FPF
        result = fpf_runner.run_filepromptforge_once(
            file_a = combine_instructions_path,
            file_b = temp_file_with_prompt,
            options = {"provider": "openai", "model": "gpt-4o"}
        )
        
        RETURN result.path
```

### Playoffs Flow

```pseudo
FUNCTION run_playoffs(initial_eval_db, output_folder, config):
    """
    1. Get top 2 reports from initial eval
    2. Combine them
    3. Re-evaluate combined vs top 2
    4. Select winner
    """
    
    combiner = ReportCombiner(initial_eval_db)
    
    # Get top 2
    top_2 = combiner.get_top_reports(n=2)
    IF len(top_2) < 2:
        RETURN top_2[0] if top_2 else None
    
    # Combine
    combined_path = combiner.combine(
        top_2[0], top_2[1],
        config.instructions_file,
        config.combine_instructions_file
    )
    
    # Re-evaluate with combined doc added
    all_docs = top_2 + [combined_path]
    new_db = await run_evaluation(
        all_docs,
        new_docs_only=[combined_path],
        source_db=initial_eval_db,
        skip_single_for_existing=True
    )
    
    # Get winner
    winner = get_best_report(new_db)
    
    # Save winner to winners directory
    save_winner(winner, winners_dir)
    
    RETURN winner
```

---

## 8. Concurrency Control

### GPT-Researcher Concurrency

**File**: `runner.py :: _resolve_gptr_concurrency()`

```pseudo
FUNCTION _resolve_gptr_concurrency(config) -> (enabled, max_concurrent, delay):
    """
    Resolves GPTR concurrency with optional policy override.
    
    Config path: concurrency.gpt_researcher.{enabled, max_concurrent_reports, launch_delay_seconds}
    Policy path: policies.concurrency.gpt_researcher.{enforce, max_concurrent_reports_cap, launch_delay_seconds_min}
    """
    
    # Local config
    local = config.concurrency.gpt_researcher OR {}
    local_enabled = local.get("enabled", False)
    local_max = local.get("max_concurrent_reports", 1)
    local_delay = local.get("launch_delay_seconds", 0.0)
    
    # Policy overlay (if enforce=True)
    policy = config.policies.concurrency.gpt_researcher OR {}
    IF policy.get("enforce"):
        cap = policy.get("max_concurrent_reports_cap")
        IF cap:
            local_max = min(local_max, cap)
        
        min_delay = policy.get("launch_delay_seconds_min")
        IF min_delay:
            local_delay = max(local_delay, min_delay)
    
    RETURN (local_enabled, max(1, local_max), max(0.0, local_delay))
```

### MA Concurrency

```pseudo
FUNCTION run_multi_agent_runs_concurrent(query, num_runs, model, max_concurrent):
    """Uses asyncio.Semaphore for concurrency limiting."""
    
    sem = asyncio.Semaphore(max_concurrent OR num_runs)
    
    async def _run_one(i):
        async with sem:  # Acquire semaphore
            return await run_multi_agent_once(query, temp_dir, i, task_config)
    
    tasks = [_run_one(i) for i in range(1, num_runs + 1)]
    await asyncio.gather(*tasks, return_exceptions=True)
```

### FPF Inflight Tracker

```pseudo
CLASS FpfInflightTracker:
    """
    Watermark-based gating for FPF batch execution.
    Ensures "rest" bucket completes before "deep" bucket starts.
    """
    
    def __init__(self, totals: dict):
        self.totals = totals  # {"rest": 10, "deep": 5}
        self.completed = {"rest": 0, "deep": 0}
        self.events = {"rest": asyncio.Event(), "deep": asyncio.Event()}
    
    def update(self, event):
        IF event.type == "run_complete":
            bucket = event.data.bucket
            self.completed[bucket] += 1
            IF self.completed[bucket] >= self.totals[bucket]:
                self.events[bucket].set()
    
    async def wait_for(self, bucket):
        await self.events[bucket].wait()
```

---

## 9. Edge Cases & Error Handling

### File Discovery Edge Cases

| Scenario | Handling |
|----------|----------|
| File modified during batch | `batch_start_ts` threshold filters old files |
| Duplicate source files | `seen_src` set prevents double-processing |
| Missing file extension | Falls back to ".md" or ".json" |
| Unicode filename | UTF-8 encoding enforced throughout |
| Symlinks | Resolved to absolute paths |

### Subprocess Edge Cases

| Scenario | Handling |
|----------|----------|
| Prompt file race condition | 5x retry with 0.2s delay, fsync after write |
| UTF-8 encoding on Windows | `PYTHONIOENCODING=utf-8`, `PYTHONUTF8=1` |
| Subprocess timeout | Kill process, write `.failed.json` artifact |
| Exit code non-zero | Parse stderr, attempt retry if applicable |
| Missing output file | Warning logged, empty result returned |

### FPF Validation Edge Cases

| Exit Code | Meaning | Retry Behavior |
|-----------|---------|----------------|
| 0 | Success | Check for FAILURE-REPORT.json (Layer 2) |
| 1 | Missing grounding | Retry with grounding-enhanced preamble |
| 2 | Missing reasoning | Retry with reasoning-enhanced preamble |
| 3 | Both missing | Retry with combined preamble |
| 4 | Unknown validation failure | Retry with both |
| 5 | Other error | No retry |

### Evaluation Edge Cases

| Scenario | Handling |
|----------|----------|
| Single doc fails eval | Results stored with NULL score |
| DB locked during write | SQLite WAL mode, retry logic |
| Insufficient docs for pairwise | Skip pairwise, use single scores |
| Top N filtering fails | Fall back to all docs |
| Streaming eval spawned twice | `_spawned_files` set prevents duplicates |

---

## 10. Data Structures & State

### Global State Variables

```python
# runner.py module-level globals
STREAMING_EVAL_MANAGER: StreamingEvalManager | None = None
SUBPROC_LOGGER: logging.Logger | None = None  # Dedicated subprocess log
GPTR_TIMEOUT_SECONDS: int = 1200  # 20 minutes
MA_TIMEOUT_SECONDS: int = 600    # 10 minutes
```

### Config Structure (config.yaml)

```yaml
input_folder: "./inputs"
output_folder: "./outputs"
instructions_file: "./prompts/instructions.txt"
one_file_only: false
iterations_default: 3

runs:
  - type: fpf
    provider: openai
    model: gpt-4o
  - type: gptr
    provider: openai
    model: gpt-4o
  - type: ma
    model: gpt-4o

concurrency:
  gpt_researcher:
    enabled: true
    max_concurrent_reports: 3
    launch_delay_seconds: 1.0
  multi_agent:
    enabled: true
    max_concurrent_runs: 2

eval:
  auto_run: true
  streaming_single_eval: true
  output_directory: "./gptr-eval-process/final_reports"
  config_path: "./llm-doc-eval/llm_doc_eval/config.yaml"
  iterations: 1
  playoffs:
    enabled: true
    top_n: 3
```

### Database Schema (eval results)

```sql
-- single_doc_results table
CREATE TABLE single_doc_results (
    id INTEGER PRIMARY KEY,
    doc_id TEXT NOT NULL,
    dimension TEXT NOT NULL,
    score REAL,
    iteration INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- pairwise_results table
CREATE TABLE pairwise_results (
    id INTEGER PRIMARY KEY,
    doc_a TEXT NOT NULL,
    doc_b TEXT NOT NULL,
    winner TEXT CHECK(winner IN ('A', 'B', 'tie')),
    iteration INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- elo_ratings table
CREATE TABLE elo_ratings (
    doc_id TEXT PRIMARY KEY,
    elo_rating REAL DEFAULT 1500.0,
    games_played INTEGER DEFAULT 0
);
```

---

## 11. File Naming Conventions

### Generated Files

```
{base_name}.{generator_type}.{index}.{model_label}.{uid3}.{extension}

Examples:
  intro.fpf.1.gpt-4o.abc.md
  intro.gptr.2.gemini-1.5-pro.xyz.md
  intro.ma.1.claude-3-opus.def.md
  intro.dr.1.gpt-4o.ghi.md
  intro.fpf.3.gpt-4o.jkl.failed.json
```

### Evaluation Files

```
streaming_eval_{timestamp}.db     # Streaming eval SQLite DB
eval_{timestamp}.db               # Batch eval SQLite DB
timeline_data.json                # Timeline JSON for HTML report
acm_session.log                   # Main ACM log
acm_subproc_{uid}.log             # Per-batch subprocess log
```

### Winner Files

```
{winners_dir}/{relative_path}/{base_name}.winner.md
```

---

## 12. Key Constants & Configuration

### Timeouts

| Operation | Default Timeout |
|-----------|----------------|
| GPTR subprocess | 1200s (20 min) |
| MA subprocess | 600s (10 min) |
| FPF batch | 1800s (30 min) |
| Streaming eval wait | 1800s (30 min) |
| Timeline generation | 120s (2 min) |

### Retry Limits

| Operation | Max Retries |
|-----------|-------------|
| GPTR prompt file missing | 1 retry |
| FPF validation failure | 3 retries |
| File copy collision | 10 random UIDs |

### Concurrency Defaults

| Operation | Default Max Concurrent |
|-----------|----------------------|
| GPTR reports | 1 (disabled by default) |
| MA runs | 1 (disabled by default) |
| FPF batch | Unlimited within batch |
| Streaming eval | Unlimited |

---

## Summary

This document covers the complete technical implementation of ACM v1. Key architectural patterns:

1. **Subprocess Isolation**: All generators (FPF, GPTR, MA) run as subprocesses with JSON IPC
2. **File-Based Skip Logic**: Pattern matching on `{base_name}.*` in three directories
3. **Streaming Evaluation**: Single-doc evals spawn as files complete, parallel with generation
4. **4-Layer FPF Retry**: Sophisticated validation failure detection and retry with enhanced prompts
5. **Concurrency Control**: Semaphore-gated parallelism with configurable limits
6. **State Persistence**: SQLite for eval results, JSON for timeline/events

For ACM 2.0, these patterns should be preserved where appropriate, with the addition of proper API endpoints and data models.
