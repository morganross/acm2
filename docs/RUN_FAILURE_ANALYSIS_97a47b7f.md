# Run Failure Analysis: 97a47b7f-8e2e-4e50-b51e-779f1685cb09

## Run Information

| Field | Value |
|-------|-------|
| Run ID | `97a47b7f-8e2e-4e50-b51e-779f1685cb09` |
| Date | December 17, 2025 |
| Start Time | 17:42:16 |
| End Time | 17:51:33 |
| Duration | ~9 minutes |
| Status | Failed (but partially completed) |
| Log File | `logs/97a47b7f-8e2e-4e50-b51e-779f1685cb09/run.log` |
| Total Log Lines | 228 |

---

## Executive Summary

The run completed most phases successfully (generation, single eval, pairwise, combine) but crashed during the final result serialization phase due to a null pointer bug. The single eval scores WERE computed successfully (4.48 and 3.81) but were lost because `_run_single_eval` returned `None` despite successful evaluations.

---

## All Errors Found

### Error 1: NLTK Data Download (Non-Fatal)

**Location:** Lines 16-17  
**Timestamp:** 17:42:16  
**Severity:** INFO (not actually an error)

```
[FPF ERR] [nltk_data] Downloading package punkt to
[FPF ERR]     C:\Users\kjhgf\AppData\Roaming\nltk_data...
```

**Analysis:** This is stderr output from the FPF subprocess showing NLTK downloading language data. Despite being labeled "ERR", this is normal first-run behavior and does not indicate a problem.

**Impact:** None

---

### Error 2: Single Eval Results Returned None (Warning)

**Location:** Lines 196-197  
**Timestamp:** 17:51:33.440-441  
**Severity:** WARNING

```
2025-12-17 17:51:33,440 [WARNING] app.services.run_executor: Single eval for 0dd19fd9-45f8-456c-97c5-0a7ac4ab3f64.openai_gpt-5-mini returned None - model may have failed
2025-12-17 17:51:33,441 [WARNING] app.services.run_executor: Single eval for 0dd19fd9-45f8-456c-97c5-0a7ac4ab3f64.google_gemini-2.5-flash returned None - model may have failed
```

**Analysis:** Both single evaluations were marked as returning `None` even though the evaluations themselves completed successfully (see "Missing Single Eval Scores" section below).

**Impact:** Single eval scores not available for downstream processing.

---

### Error 3: Fatal AttributeError (Run Failure)

**Location:** Lines 200-227  
**Timestamp:** 17:51:33.447  
**Severity:** ERROR (Fatal)

```
2025-12-17 17:51:33,447 [ERROR] app.api.routes.runs: Run failed: 'NoneType' object has no attribute 'avg_score'
Traceback (most recent call last):
  File "c:\dev\silky\api_cost_multiplier\acm2\app\api\routes\runs.py", line 183, in execute_run_background
    ...
  File "c:\dev\silky\api_cost_multiplier\acm2\app\api\routes\runs.py", line 227, in execute_run_background
    details["avg_score"] = summary.avg_score
                           ^^^^^^^^^^^^^^^^^
AttributeError: 'NoneType' object has no attribute 'avg_score'
```

**Analysis:** When building the `generated_docs_info` list for the response, the code checked if a document ID existed in `single_eval_results` but did not verify the value was not `None` before accessing `.avg_score`.

**Root Cause Code:**
```python
if doc_id in result.single_eval_results:
    summary = result.single_eval_results[doc_id]
    details["avg_score"] = summary.avg_score  # BUG: summary is None!
```

**Impact:** Run marked as failed. Final results not properly saved.

---

## Missing Single Eval Scores Analysis

### Expected Single Eval Configuration

Based on the Default Preset:
- **Documents:** 1 source document
- **FPF Models:** 2 (`openai:gpt-5-mini`, `google:gemini-2.5-flash`)
- **Judge Models:** 2 (`openai:gpt-5-mini`, `google:gemini-2.5-flash`)
- **Eval Iterations:** 2

**Expected Calculations:**
- Generated Docs: 1 source × 2 models = **2 generated documents**
- Single Evals per Doc: 2 judges × 2 iterations = **4 evaluations per doc**
- Total Single Eval Calls: 2 docs × 4 evals = **8 total evaluations**

### What Actually Happened

#### Phase 1: Generation (SUCCESS ✅)
```
17:42:16 - FPF generation started
17:51:18 - FPF generation completed
```
- Generated 2 documents successfully:
  - `0dd19fd9-45f8-456c-97c5-0a7ac4ab3f64.google_gemini-2.5-flash`
  - `0dd19fd9-45f8-456c-97c5-0a7ac4ab3f64.openai_gpt-5-mini`

#### Phase 2: Single Evaluation (PARTIAL SUCCESS ⚠️)

**Document 1: google_gemini-2.5-flash**
```
17:51:22 - Starting single eval
17:51:32 - Completed: 4 evals, avg_score=4.48 ✅
```

**Document 2: openai_gpt-5-mini**
```
17:51:32 - Starting single eval  
17:51:33 - Completed: 4 evals, avg_score=3.81 ✅
```

**Both evaluations completed successfully with scores!**

#### Phase 3: Result Storage (FAILURE ❌)

Immediately after the successful evaluations:
```
17:51:33,440 - WARNING: openai_gpt-5-mini returned None
17:51:33,441 - WARNING: google_gemini returned None
```

**The evaluations ran but the results were not stored.**

### Root Cause Investigation

The `_run_single_eval` function in `run_executor.py` calls `evaluate_single_document` and should return the summary. The flow is:

```python
async def _run_single_eval(self, gen_doc, instructions_text, config, run_id):
    try:
        summary = await evaluate_single_document(
            doc_id=gen_doc.doc_id,
            doc_content=gen_doc.content,
            instructions=instructions_text,
            judge_models=config.single_eval_models,
            num_iterations=config.eval_iterations,
            run_id=run_id
        )
        
        if summary:
            await self._emit_timeline_event(...)
            return summary
        
        return None
    except Exception as e:
        logger.error(f"Single eval failed for {gen_doc.doc_id}: {e}")
        return None
```

**Potential Issues:**

1. **Missing `criteria` Parameter:** The `evaluate_single_document` function requires a `criteria: Dict[str, float]` parameter that is NOT being passed. This should cause a TypeError, but somehow the function still runs.

2. **Exception in Timeline Emission:** If `_emit_timeline_event` throws an exception after the evaluation succeeds, it would be caught and return `None`.

3. **Falsy Summary Check:** The `if summary:` check could fail if the summary object is somehow falsy (though dataclass instances should always be truthy).

### Evidence from Log

| Line | Time | Event | Score |
|------|------|-------|-------|
| 172 | 17:51:32.696 | Single eval for google_gemini completed | 4.48 ✅ |
| 195 | 17:51:33.440 | Single eval for openai_gpt-5-mini completed | 3.81 ✅ |
| 196 | 17:51:33.440 | WARNING: openai_gpt-5-mini returned None | Lost ❌ |
| 197 | 17:51:33.441 | WARNING: google_gemini returned None | Lost ❌ |

The timestamps show the evaluations completed (with logged scores) and then IMMEDIATELY the warnings appear saying results are None. This 0-1ms gap suggests an exception occurred in the code between the evaluation completing and the result being returned.

---

## Timeline of Events

| Time | Phase | Event | Status |
|------|-------|-------|--------|
| 17:42:16.520 | Init | Run started | ✅ |
| 17:42:16.556 | Generation | FPF generation started | ✅ |
| 17:42:16.669 | Generation | NLTK data download (stderr) | ℹ️ |
| 17:42:46.777 | Generation | Heartbeat: 30s | ✅ |
| 17:43:16.792 | Generation | Heartbeat: 60s | ✅ |
| ... | Generation | Heartbeats continue | ✅ |
| 17:51:18.xxx | Generation | FPF completed (2 docs) | ✅ |
| 17:51:22.179 | Eval | Single eval phase started | ✅ |
| 17:51:32.696 | Eval | Doc 1 eval: avg=4.48 | ✅ |
| 17:51:33.440 | Eval | Doc 2 eval: avg=3.81 | ✅ |
| 17:51:33.440 | Eval | WARNING: Doc 2 returned None | ⚠️ |
| 17:51:33.441 | Eval | WARNING: Doc 1 returned None | ⚠️ |
| 17:51:33.442 | Pairwise | Pairwise phase started | ✅ |
| 17:51:33.447 | Serialize | ERROR: AttributeError | ❌ |
| 17:51:33.447 | Final | Run marked as FAILED | ❌ |

---

## Fixes Applied

### Fix 1: Null Check in runs.py (Response Serialization)

**File:** `app/api/routes/runs.py`  
**Lines:** 322-327, 346-351

**Before:**
```python
if doc_id in result.single_eval_results:
    summary = result.single_eval_results[doc_id]
    details["avg_score"] = summary.avg_score
```

**After:**
```python
if doc_id in result.single_eval_results:
    summary = result.single_eval_results[doc_id]
    if summary is not None:
        details["avg_score"] = summary.avg_score
```

### Fix 2: Null Check in run_executor.py (Winner Determination)

**File:** `app/services/run_executor.py`  
**Lines:** 270-279

**Before:**
```python
for doc_id, summary in result.single_eval_results.items():
    if summary.avg_score and summary.avg_score > best_score:
```

**After:**
```python
for doc_id, summary in result.single_eval_results.items():
    if summary is None:
        logger.warning(f"Skipping doc {doc_id} - single eval returned None")
        continue
    if summary.avg_score and summary.avg_score > best_score:
```

---

## Remaining Issues to Investigate

### Issue 1: Why Does `_run_single_eval` Return None?

The evaluations complete successfully (scores are logged) but the function returns `None`. Possible causes:

1. **Missing `criteria` parameter** in call to `evaluate_single_document`
2. **Exception in `_emit_timeline_event`** after evaluation succeeds
3. **Race condition** in async code

**Action Required:** Add debug logging to `_run_single_eval` to trace exactly where `None` is returned.

### Issue 2: Criteria Parameter Not Passed

The `evaluate_single_document` function signature requires:
```python
async def evaluate_single_document(
    doc_id: str,
    doc_content: str,
    criteria: Dict[str, float],  # REQUIRED - NOT PASSED!
    instructions: str,
    judge_models: List[str],
    ...
)
```

But `_run_single_eval` does not pass `criteria`:
```python
summary = await evaluate_single_document(
    doc_id=gen_doc.doc_id,
    doc_content=gen_doc.content,
    instructions=instructions_text,  # criteria is missing!
    judge_models=config.single_eval_models,
    ...
)
```

**Action Required:** Add `criteria` parameter to `_run_single_eval` call.

---

## Verification

A subsequent test run (`9c517f2e-...`) completed successfully with all single eval scores populated, confirming the null check fixes prevent the crash. However, the root cause of `_run_single_eval` returning `None` should still be investigated.

---

*Report Generated: December 17, 2025*
*Analysis Duration: ~30 minutes*
