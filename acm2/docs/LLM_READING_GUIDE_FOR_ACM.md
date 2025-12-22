# LLM Reading Guide for ACM / Eval Code

This document is written **for an LLM** that is trying to understand what our current ACM + evaluation stack does and what we want from the software.

The goal: if you (LLM) read the right files in the right order, you will:
- Learn what ACM does end‑to‑end today.
- See how generation, FPF, evaluation, and HTML reporting fit together.
- Understand which behaviors we care about preserving in ACM 2.0.

You do **not** need to understand every helper or edge case; focus on the big flows and how data moves.

---

## 1. Understand the current orchestration (ACM today)

Next, scan the main orchestration logic in the legacy system. This shows how runs work today.

1. `api_cost_multiplier/runner.py`  
   - This is the central script that orchestrates: generation, evaluation, combining results, playoffs, and HTML export.  
   - Look for:  
     - How it discovers input documents.  
     - How it decides whether to skip work based on existing files.  
     - How it calls generation, evaluation, and playoffs scripts.  
     - How it finds winners and final reports.

2. `api_cost_multiplier/generate.py` (or similar generation script)  
   - Handles turning input documents into model outputs (prompts → completions).  
   - Look for:  
     - How it loops over documents.  
     - How it names output files.  
     - How it decides to skip if an output already exists.

3. `api_cost_multiplier/evaluate.py`  
   - Orchestrates evaluation runs (probably calling into `llm-doc-eval` or similar).  
   - Look for:  
     - How it reads model outputs.  
     - What evaluation artifacts it creates (SQLite DBs, CSVs, HTML).  
     - How it handles winners / playoffs / combined reports.

As you read, construct a **conceptual flow** like:

> Documents in → generation outputs → evaluation DBs/HTML → combined/winner outputs.

Capture the key inputs/outputs for each phase and the filenames/directories they use.

---

## 3. See how FPF is integrated

FPF (FilePromptForge) is a major building block. You should learn how the current code calls it.

1. `api_cost_multiplier/api_cost_multiplier/FilePromptForge/` and `api_cost_multiplier/api_cost_multiplier/functions/`  
   - Look for modules with names like `fpf_*.py` or anything that:
     - Builds FPF configs.  
     - Launches FPF runs.  
     - Reads FPF outputs.

2. Inside those files, focus on:
   - How a single FPF run is configured (input files, model, parameters).  
   - Where outputs are written and how they are named.  
   - Any retry, validation, or logging logic.

Your goal is not to rewrite FPF, but to understand:
- What inputs ACM gives FPF.  
- What outputs ACM expects back.  
- How tightly coupled ACM is to FPF’s internal structure.

---

## 4. Understand evaluation internals

Evaluation often lives partly in `evaluate.py` and partly in a separate eval package.

1. `api_cost_multiplier/llm-doc-eval/` (or similarly named folder)  
   - Look for the main entrypoint used by `evaluate.py`.  
   - Identify how it reads model outputs and writes DB/HTML/CSV.

2. Any configuration or presets under `api_cost_multiplier/api_cost_multiplier/presets.yaml` or `config.yaml`  
   - These files define how runs and evals are parameterized.  
   - Note how different presets map to different models, cost settings, or evaluation modes.

Focus on:
- How evaluation jobs are defined (per doc, per model, etc.).  
- How we identify winners or best models.  
- How the eval artifacts are organized on disk.

---

## 5. Logging, skip logic, and heuristics

A key part of ACM’s behavior is how it **avoids re‑doing work** and how it logs what happened.

1. In `runner.py`, `generate.py`, and `evaluate.py`:  
   - Search for words like `skip`, `existing`, `recent`, `latest`, `winners`, `exports`.  
   - Pay attention to any logic that scans directories to find the “most recent” or “matching” files.

2. Note the problems we want to fix in ACM 2.0:
   - Heuristics based on "recent files" or "most recent export dir".  
   - Tight coupling to specific folder layouts and implicit global state.

From this, build an internal checklist of **behaviors to preserve** (e.g., don’t re‑run work if the exact artifact exists) versus **mechanisms to replace** (e.g., timestamp‑based guessing of which files belong together).

---

## 6. Summarize the current system in your own words

After you read the files above, you (LLM) should produce a short internal summary (for us or for yourself) that answers:

1. What are the main phases of a run, and how do they connect?  
2. How are documents, models, FPF, and evaluation wired together today?  
3. Where are the strongest, battle‑tested parts (things we should wrap and reuse)?  
4. Where are the fragile parts (things that rely on directory scans, magic names, or global state)?  
5. What information do we need in ACM 2.0’s database/API to avoid relying on fragile heuristics?

If you can answer those questions clearly, you have learned what we need you to know about the current ACM + eval code, and you’re ready to help design or implement ACM 2.0 behavior that respects the existing strengths while fixing the current pain points.

In addition to the extremely detailed and thorough report, also:

Explain what this ACM + eval software does in:
1. One short sentence.
2. Ten detailed sentences that walk through the main phases and data flow.
3. A short paragraph describing why someone would use this software instead of doing the same work manually.

