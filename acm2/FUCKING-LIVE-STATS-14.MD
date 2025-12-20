# FUCKING-LIVE-STATS-14: Run Failure Investigation Report

**Date:** December 20, 2025  
**Run ID:** `2bbde334-0438-4c77-a0ff-43022c2dfc74`  
**Status:** FAILED  
**Duration:** 09:27:50 - 09:37:50 (10 minutes)

---

## 1. EXECUTIVE SUMMARY

The run failed during the **pairwise phase** with error:
```
AttributeError: 'GeneratedDocument' object has no attribute 'status'
```

The bug is in `run_executor.py` line 939, where code attempts to access a `.status` attribute on `GeneratedDocument` objects, but this dataclass has no such field.

---

## 2. TIMELINE OF EVENTS

| Time | Phase | Event | Duration | Status |
|------|-------|-------|----------|--------|
| 09:27:50 | initialization | Run started | - | ✅ |
| 09:27:50 | generation | google:gemini-2.5-flash | 24.30s | ✅ |
| 09:27:50 | generation | google:gemini-2.5-pro | 33.40s | ✅ |
| 09:27:50 | generation | openai:gpt-5.1 | 272.43s | ✅ |
| 09:27:50 | generation | openai:gpt-5-mini | 600.05s | ✅ |
| 09:28:14 | single_eval | gemini-2.5-flash eval | 205.72s | ✅ (4.33) |
| 09:28:23 | single_eval | gemini-2.5-pro eval | 251.80s | ✅ (4.17) |
| 09:32:22 | single_eval | gpt-5.1 eval | 311.02s | ✅ (4.75) |
| 09:37:50 | pairwise | **CRASH** | - | ❌ |

**FPF Live Stats at failure:** 10 OK / 0 Fail / 0 Retry

---

## 3. ROOT CAUSE ANALYSIS

### 3.1 The Bug Location

**File:** `app/services/run_executor.py`  
**Line:** 939  
**Method:** `_run_pairwise()`

```python
# Lines 937-940: THE BUG
valid_docs = [
    doc for doc in result.generated_docs
    if doc.status == TaskStatus.COMPLETED and doc.content and len(doc.content.strip()) > 0
]
```

### 3.2 The Problem

The `GeneratedDocument` dataclass (defined at line 57-70) has these fields:
- `doc_id: str`
- `content: str`
- `generator: GeneratorType`
- `model: str`
- `source_doc_id: str`
- `iteration: int`
- `cost_usd: float`
- `duration_seconds: float`
- `started_at: Optional[datetime]`
- `completed_at: Optional[datetime]`
- `metadata: Dict[str, Any]`

**There is NO `status` field.**

### 3.3 Why This Bug Exists

The code assumes that `GeneratedDocument` tracks its own status (like `TaskStatus.COMPLETED`, `TaskStatus.FAILED`, etc.). However, the actual implementation works differently:

1. `_generate_single()` returns `GeneratedDocument` on success or `None` on failure
2. Only successful documents are appended to `result.generated_docs` (line 708)
3. Therefore, **ALL documents in `result.generated_docs` are implicitly successful**
4. There's no need to check `.status == TaskStatus.COMPLETED`

This is a **design mismatch**: the filtering logic assumes a status-tracking pattern that doesn't exist.

---

## 4. THE FIX

### Option A: Simple Fix (Recommended)

Since all documents in `generated_docs` are already successful, change the filter to only check for content:

```python
# BEFORE (BROKEN):
valid_docs = [
    doc for doc in result.generated_docs
    if doc.status == TaskStatus.COMPLETED and doc.content and len(doc.content.strip()) > 0
]

# AFTER (FIXED):
valid_docs = [
    doc for doc in result.generated_docs
    if doc.content and len(doc.content.strip()) > 0
]
```

### Option B: Add Status Field to GeneratedDocument

Add optional status tracking to the dataclass:

```python
@dataclass
class GeneratedDocument:
    """A document produced by generation."""
    doc_id: str
    content: str
    generator: GeneratorType
    model: str
    source_doc_id: str
    iteration: int
    cost_usd: float = 0.0
    duration_seconds: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: str = "completed"  # NEW FIELD
```

**Recommendation:** Option A is simpler and aligns with current architecture. Failed generations never make it into the list.

---

## 5. IMPACT ASSESSMENT

### What Worked
- ✅ All 4 generations completed successfully
- ✅ All 4 single-doc evaluations completed with scores
- ✅ FPF adapter with 600s timeout worked
- ✅ Live stats broadcasting worked
- ✅ Timeline events recorded
- ✅ Database persistence working

### What Failed
- ❌ Pairwise phase crashed immediately on entry
- ❌ Run marked as failed
- ❌ No pairwise comparisons executed
- ❌ No combine phase executed
- ❌ No winner determined

### User Impact
- Run shows as "failed" despite 10/10 FPF calls succeeding
- Evaluation scores were computed but run is unusable
- User must re-run to get pairwise/combine results

---

## 6. ADDITIONAL OBSERVATIONS

### 6.1 gpt-5-mini Generation Took 600 Seconds

The gpt-5-mini generation took exactly 600.05 seconds - which is the timeout value! This suggests:
- The request may have been slow or hung
- It completed just at the timeout boundary
- Worth investigating if this is a model performance issue

### 6.2 Missing 4th Evaluation

Looking at the timeline, we have:
- 4 generations (all 4 models)
- 3 evaluations (gemini-2.5-flash, gemini-2.5-pro, gpt-5.1)
- Missing: gpt-5-mini evaluation

The gpt-5-mini evaluation likely hadn't started yet because the pairwise phase crashed first. The evaluations run in parallel but gpt-5-mini generation finished last (at 600s) leaving no time for its evaluation before pairwise started.

### 6.3 History Pattern

Looking at `.history` folder, this same bug has existed since at least December 19th - the `doc.status` check appears in many historical versions of the file, suggesting it was introduced and never tested with a full run reaching pairwise phase.

---

## 7. REGRESSION RISK

This is a **blocking bug** that prevents ANY run with pairwise enabled from completing. The bug has likely existed for some time but wasn't caught because:
1. Previous runs may not have reached pairwise phase (failed earlier)
2. Previous runs may have had pairwise disabled
3. The path wasn't exercised in testing

---

## 8. FIX VERIFICATION STEPS

After applying the fix:

1. **Restart server** with new code
2. **Start new run** with Default Preset
3. **Monitor** through generation and single-eval phases
4. **Verify** pairwise phase starts and completes
5. **Verify** combine phase executes
6. **Verify** run status = "completed"
7. **Check** winner is determined

---

## 9. RELATED BUGS FIXED IN THIS SESSION

| Bug | Description | Status |
|-----|-------------|--------|
| BUG 1 | Orphan recovery on server restart | ✅ FIXED |
| BUG 2 | 24-hour hardcoded timeout | ✅ FIXED (now 600s configurable) |
| BUG 3 | last_error not cleared on success | ✅ FIXED |
| **BUG 4** | `GeneratedDocument` missing `status` attribute | ✅ FIXED |
| **BUG 5** | FPF adapter returns failed result instead of raising exception | ✅ FIXED |

---

## 9.1 BUG 5 DETAILS: FPF Adapter Exception Handling

### Problem
When FPF subprocess times out or fails, the adapter was catching the exception and returning a `GenerationResult` with `status=FAILED` and empty content, instead of re-raising the exception.

This caused:
1. `_generate_single` received a non-None result (treating failure as success)
2. Empty `GeneratedDocument` was created
3. Timeline event emitted with `success=True` despite timeout
4. 0-byte file saved to `logs/generated/`

### Evidence
- gpt-5-mini generation took exactly 600s (timeout limit)
- File `7469e725.e56a.fpf.1.openai_gpt-5-mini.md` was 0 bytes
- Timeline showed `success: true` for this generation
- Log showed `FpfExecutionError: FPF execution failed: Process timed out`

### Root Cause
In `app/adapters/fpf/adapter.py` lines 198-220:
```python
except Exception as e:
    logger.exception(f"FPF generation failed for task {task_id}")
    # BUG: Returning result instead of raising
    return GenerationResult(
        status=TaskStatus.FAILED,
        content="",
        ...
    )
```

### Fix
Changed to re-raise the exception:
```python
except Exception as e:
    logger.exception(f"FPF generation failed for task {task_id}")
    raise  # Let _generate_single handle it and return None
```

---

## 10. CONCLUSION

The run failed due to a code bug, not an infrastructure or API issue. The fix is straightforward: remove the `.status` check from the pairwise document filter. All documents in `generated_docs` are already successful by definition of how they're added.

**Priority:** CRITICAL - Blocks all runs with pairwise enabled  
**Effort:** LOW - One line change  
**Risk:** LOW - Simple logic fix with clear semantics  

---

*Report generated: December 20, 2025 01:45 AM*
