# FPF Grounding Threshold Investigation Report

**Date:** 2025-12-17
**Status:** Completed
**Investigator:** GitHub Copilot

## Executive Summary

After an exhaustive search of the entire codebase (including `FilePromptForge` core, providers, `acm2` evaluation logic, configuration files, and logs), **no code was found that implements a "66%" (or "0.66") grounding threshold.**

The investigation confirms that "grounding" in this system is implemented as a **boolean check** (presence/absence of metadata), not a percentage-based score.

The "66%" figure likely originates from **log artifacts** (timestamps or elapsed time) that were misinterpreted as a threshold score.

## Detailed Findings

### 1. Codebase Search for "66%" / "0.66"

We performed a global search for `0.66`, `66%`, and `grounding_threshold`.

| Location | Finding | Relevance |
| :--- | :--- | :--- |
| **Code Logic** | **NONE** | N/A |
| **Config Files** | **NONE** | N/A |
| `logs/fpf_run.log` | `elapsed=40.66s`, `elapsed=80.66s` | **High** (Likely source of confusion) |
| `logs/fpf_run.log` | `total_cost_usd': 0.669371` | **Medium** (Possible source) |
| `logs/...` | Timestamps ending in `.66...` | Low |
| `National Debt.md` | "between 66% and 100% of GDP" | Irrelevant (Content) |

### 2. Grounding Logic Implementation

We audited the code responsible for grounding and validation. All logic is **boolean**.

#### A. `FilePromptForge/grounding_enforcer.py`
- **Function:** `detect_grounding(response)`
- **Logic:** Returns `True` if `groundingMetadata` or `tool_calls` are present. Returns `False` otherwise.
- **Thresholds:** None.

#### B. `FilePromptForge/providers/google/fpf_google_main.py`
- **Logic:** Checks `if candidate.get("groundingMetadata")`.
- **Thresholds:** None.

#### C. `acm2/app/evaluation/judge.py`
- **Config:** `enable_grounding: bool = True`
- **Logic:** Toggles whether the judge is allowed to use web search.
- **Thresholds:** None.

### 3. Other Thresholds Found (Unrelated)

To ensure completeness, here are *all* thresholds found in the system:

| File | Variable | Value | Purpose |
| :--- | :--- | :--- | :--- |
| `acm2/app/evaluation/elo.py` | `high_rating_threshold` | `1200.0` | ELO rating classification |
| `acm2/app/evaluation/criteria.py` | `weight` | `1.5`, `1.2`, etc. | Scoring weights |
| `FilePromptForge/fpf_config.yaml` | `timeout_seconds` | `600` | Execution timeout |
| `FilePromptForge/fpf_config.yaml` | `qps` | `0.9` | Rate limiting |

## Conclusion

The "grounding threshold" of 66% does not exist in the codebase. The timeouts are likely caused by:
1.  **Provider Latency:** Google/OpenAI taking longer than `timeout_seconds` (600s) to return a response with grounding.
2.  **Strict Boolean Checks:** If a provider fails to return *any* grounding metadata (due to API issues), FPF treats it as a failure (0% success), not a low score.

**Recommendation:**
- Ignore the "66%" figure.
- Focus debugging on why `groundingMetadata` is missing from provider responses or why latency exceeds 600s.
