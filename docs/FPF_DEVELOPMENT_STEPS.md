# FPF Development Steps (for ACM 2.0)

This document is about **how to evolve FPF so it works cleanly with ACM 2.0**, not about FPF’s feature requirements.

## Phase 1 – Wrap existing FPF in a clean adapter

1. **Inventory current entrypoints**  
   - List all current ways FPF is invoked (CLI scripts, Python functions, config files).  
   - Note where ACM currently calls into FPF and what arguments/paths it passes.

2. **Define a minimal adapter API**  
   - On paper, define one or two Python functions that *should* be the only way ACM 2.0 talks to FPF (e.g. `run_fpf_for_document`).  
   - Decide input parameters (document reference, instructions reference, config object) and a single return type (`FpfRunResult`).

3. **Introduce config and result models**  
   - Create `FpfConfig` and `FpfRunResult` dataclasses/Pydantic models with just the fields ACM needs.  
   - Keep them small and stable; mark any optional/experimental fields clearly.

4. **Implement the adapter around existing FPF code**  
   - Implement the adapter functions by *calling into* the current FPF logic (no behavioral changes yet).  
   - Ensure the adapter is responsible for: choosing output directory, capturing output file paths, and mapping errors into `FpfRunResult`.

5. **Switch ACM (current version) to use the adapter**  
   - Replace direct calls into FPF internals with calls to the new adapter API.  
   - Keep filenames and folders the same so behavior stays identical.

## Phase 2 – Stabilize contracts and logging

6. **Standardize filename and directory patterns**  
   - Write down the intended naming scheme for FPF outputs (how doc id, model, mode, run index appear in filenames).  
   - Make the adapter enforce or normalize to that naming scheme.

7. **Align FPF logging with ACM logging**  
   - Route FPF logs through a shared logger (e.g. `acm.fpf`) rather than ad-hoc prints.  
   - Ensure the adapter can tag logs with `run_id` and `document_id` when called from ACM.

8. **Normalize error handling and retry hints**  
   - In the adapter, categorize common failure modes (rate limit, JSON/grounding issues, validation problems).  
   - Encode these as structured fields in `FpfRunResult` so ACM can make retry decisions without scraping logs.

9. **Add basic tests around the adapter behavior**  
   - Write a few small tests that call the adapter with simple inputs and assert on:  
     - Returned status and output file paths.  
     - Behavior when outputs already exist (skip vs regenerate, depending on policy).  
   - Use these tests to lock in the adapter contract.

## Phase 3 – Internal cleanup (optional, incremental)

10. **Refactor FPF internals behind the adapter boundary**  
    - Gradually clean up FPF internals (prompt assembly, LLM calls, file writing) without changing the adapter API.  
    - Split large functions into smaller units and reduce global state, but only after adapter tests are in place.

11. **Evaluate whether a separate FPF CLI should be retained**  
    - If a standalone CLI is useful, re-implement it as a thin layer on top of the adapter API.  
    - Ensure CLI options map directly onto `FpfConfig` so there is a single source of truth.

12. **Document adapter usage for other tools**  
    - Write short usage examples showing how *other* applications (beyond ACM) should call FPF via the adapter.  
    - Encourage all new integrations to depend on the adapter rather than FPF internals.
