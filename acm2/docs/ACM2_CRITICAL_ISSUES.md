# ACM 2.0 — Critical Issues & Gaps

**Status:** All Issues Resolved in Documentation  
**Last Updated:** 2025-12-05

This document tracks critical omissions, inconsistencies, and "holes" identified in the ACM 2.0 specification.

---

## 1. Inconsistencies in "Combine" Phase (RESOLVED)

**Location:** `ACM2_STEP17_COMBINE_INTEGRATION.md` vs `ACM2_STEP10_EVALUATION.md`

**Resolution:**
- Updated `ACM2_STEP17_COMBINE_INTEGRATION.md` to use `TEXT PRIMARY KEY` (ULID) for `combined_outputs`.
- Updated `ACM2_STEP10_EVALUATION.md` to include `combined_output_id` in `eval_results`, `pairwise_comparisons`, and `elo_ratings`.

---

## 2. The "Task Queue" Ghost (Startup Recovery) (RESOLVED)

**Location:** `ACM2_PHASE2_1_BACKEND_PROJECT_SETUP.md`

**Resolution:**
- Added **Startup Recovery** logic to `lifespan` handler in `app/main.py` (Step 6).
- Logic resets `running` tasks to `failed` on boot.

---

## 3. Missing "Project" or Grouping Concept (RESOLVED)

**Location:** `ACM2_STEP11_WEB_GUI.md`

**Resolution:**
- Added `tags` filter to Run List view in GUI spec.
- Added `tags` input to Create Run Wizard in GUI spec.

---

## 4. GPT-R Adapter vs. Rate Limiting (RESOLVED)

**Location:** `ACM2_STEP16_GPTR_ADAPTER.md`

**Resolution:**
- Updated Step 16 to explicitly state that GPT-R is "unmanaged" for MVP.
- Recommended low internal concurrency (1-2) and global concurrency limits.

---

## 5. FPF Adapter Configuration Drift (RESOLVED)

**Location:** `ACM2_STEP9_FPF_ADAPTER.md`

**Resolution:**
- Added requirement to pin FPF commit hash/version in Prerequisites.
- Added startup check requirement.

---

## 6. Evaluation "Judge" Prompts (RESOLVED)

**Location:** `ACM2_STEP10_EVALUATION.md`

**Resolution:**
- Added "Judge Prompts" section (5.5).
- Specified storage in `acm2/evaluation/prompts/` and override mechanism.

---

## 7. Web GUI Missing "Combine" Interface (RESOLVED)

**Location:** `ACM2_STEP11_WEB_GUI.md`

**Resolution:**
- Added "Combine Interface" section (5.6).
- Detailed the UI for selecting artifacts and strategy.

---

## 8. Database Migration Strategy (RESOLVED)

**Location:** `ACM2_STEP2_7A_RUN_DOCUMENT_DATA_LAYER.md`

**Resolution:**
- Added "Database Migrations (Alembic)" section (5.4).
- Listed consolidated schema references.

---

## 9. Windows Path Handling (RESOLVED)

**Location:** `ACM2_STEP2_8_STORAGE_PROVIDER.md`

**Resolution:**
- Added "Path Normalization" section (4.0).
- Defined `PathUtils.normalize()` helper to enforce forward slashes.
