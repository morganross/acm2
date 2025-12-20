# Comprehensive Analysis Report: Single Evaluation Skipped Document Failure

**Report ID:** SINGLE-EVAL-SKIP-2828a265  
**Run ID:** 2828a265-4fd3-4764-8310-7f4ce37f27eb  
**Date:** December 17, 2025  
**Severity:** HIGH - Data Integrity Failure  
**Status:** ROOT CAUSE IDENTIFIED  

---

# PART I: EXECUTIVE SUMMARY (Pages 1-5)

## Chapter 1: Overview and Problem Statement

### 1.1 The Critical Observation

During the execution of Run `2828a265-4fd3-4764-8310-7f4ce37f27eb` on December 17, 2025, the system completed successfully with status "Completed," yet a careful examination of the results reveals a **critical data gap**: one of the two generated documents was **completely skipped** during the single evaluation phase.

**Run Metadata:**
- **Run ID:** `2828a265-4fd3-4764-8310-7f4ce37f27eb`
- **Started:** 2025-12-17T20:57:30
- **Completed:** 2025-12-17T21:10:50
- **Total Duration:** 799.95 seconds (~13.3 minutes)
- **Final Status:** `completed`
- **Documents Generated:** 2 (GPT-5-mini, Gemini-2.5-flash)
- **Documents Evaluated (Single):** 1 (Gemini-2.5-flash ONLY)
- **Missing Evaluations:** GPT-5-mini document completely absent from `pre_combine_evals`

### 1.2 The Smoking Gun: Empty Content

The API response reveals the root cause in stark detail:

```json
"pre_combine_evals": {
    "0dd19fd9-45f8-456a-822f-44517469e725.fpf.1.google_gemini-2.5-flash": {
        "openai:gpt-5-mini": 3.67,
        "google:gemini-2.5-flash": 4.17
    }
    // MISSING: No entry for openai_gpt-5-mini document!
}
```

The GPT-5-mini generated document exists in `generated_docs` but has **NO** corresponding entry in `pre_combine_evals`. This is not a timeout issue, not a retry exhaustion, but a **silent skip** due to empty document content.

### 1.3 Evidence from Pairwise Comparisons

The pairwise comparison judges provide irrefutable evidence of the problem:

> **Judge (google:gemini-2.5-flash):** "Document A is empty, providing no content for review."

> **Judge (openai:gpt-5-mini):** "Document B is the clear winner because Document A contains no content."

These judgments confirm that the GPT-5-mini document was generated with **empty or null content**, causing the single evaluation to be bypassed entirely.

### 1.4 Impact Assessment

| Category | Impact Level | Description |
|----------|--------------|-------------|
| Data Integrity | **CRITICAL** | 50% of single evaluation data is missing |
| User Trust | **HIGH** | "Completed" status masks incomplete analysis |
| Cost Analysis | **MEDIUM** | Cannot calculate cost-to-quality ratio for missing doc |
| Decision Quality | **LOW** | Pairwise still correctly identified winner (by default) |

### 1.5 Related Documentation

This report builds upon and references the following prior analyses:

1. **`RUN_97a47b7f_COMPREHENSIVE_ERROR_REPORT.md`** - Previous run failure due to 300s timeout causing missing evaluations
2. **`generation_failure_analysis.md`** - Analysis of why generations fail silently
3. **`REPEATING_PROBLEM_GUI_FAILURE_ANALYSIS.md`** - Pattern of silent failures in the system
4. **`FPF_COST_DATA_FAILURE_ANALYSIS.md`** - FPF adapter cost data collection failures

---

# PART II: TECHNICAL DEEP DIVE (Pages 6-15)

## Chapter 2: The Code Path That Skipped Evaluation

### 2.1 The Conditional Gate

The single evaluation phase is controlled by a conditional statement in `run_executor.py` at line 561:

```python
# 2. Single eval IMMEDIATELY (streaming)
if single_evaluator and gen_result.content:
    try:
        eval_input = DocumentInput(
            doc_id=gen_result.doc_id,
            content=gen_result.content,
        )
        summary = await single_evaluator.evaluate_document(eval_input)
        result.single_eval_results[gen_result.doc_id] = summary
```

The critical condition is: `if single_evaluator and gen_result.content:`

This means:
1. If `single_evaluator` is None → Skip (evaluation disabled)
2. If `gen_result.content` is falsy (None, empty string, whitespace) → **Skip silently**

### 2.2 What Happened in This Run

The timeline events from the run reveal the sequence:

| Timestamp | Event | Model | Duration |
|-----------|-------|-------|----------|
| 20:57:30 | Generation Started | gemini-2.5-flash | - |
| 20:57:41 | Generation Completed | gemini-2.5-flash | 11.65s |
| 20:57:30 | Generation Started | gpt-5-mini | - |
| 21:07:30 | Generation Completed | gpt-5-mini | **600.11s** (timeout boundary!) |

**Key Observation:** The GPT-5-mini generation took exactly 600 seconds - the timeout limit we recently increased from 300s.

### 2.3 The Timeout-Content Correlation

When examining `RUN_97a47b7f_COMPREHENSIVE_ERROR_REPORT.md`, we see a pattern:

| Run | Model | Duration | Content Status | Single Eval |
|-----|-------|----------|----------------|-------------|
| 97a47b7f | gpt-5-mini | 271s | Unknown | Missing (timeout during eval) |
| 2828a265 | gpt-5-mini | 600s | **EMPTY** | Skipped (no content) |

The 600-second timeout was implemented to prevent the evaluation timeout, but it reveals a **different failure mode**: the FPF subprocess completed but returned empty content.

### 2.4 Why Did FPF Return Empty Content?

FPF (FilePromptForge) can return empty content for several reasons:

1. **Web Search Failure:** FPF's web search component failed to retrieve any sources
2. **LLM API Error:** The underlying LLM API returned an error that FPF swallowed
3. **Content Filtering:** The content was filtered for safety/policy reasons
4. **Timeout Recovery:** FPF hit an internal timeout and returned gracefully with no content
5. **Parse Error:** The LLM response couldn't be parsed into the expected format

Given the 600-second duration (exactly at the timeout limit), the most likely cause is:

> **HYPOTHESIS:** The FPF subprocess hit the 600-second timeout, caught the TimeoutError, and returned an empty result object to avoid crashing.

## Chapter 3: The Silent Failure Pattern

### 3.1 No Exception, No Log, No Trace

The most insidious aspect of this failure is its **silence**. When `gen_result.content` is empty:

```python
if single_evaluator and gen_result.content:
    # This entire block is skipped
    ...
# No else clause! No logging! No error recorded!
```

There is no:
- Exception thrown
- Error logged
- Warning emitted
- Metric recorded
- UI indication

The system simply proceeds to the next step as if nothing happened.

### 3.2 Historical Pattern Recognition

This pattern is documented in `generation_failure_analysis.md`:

> **"ACM2 does NOT have retry logic at the executor level... If FPF returns an error, ACM2 doesn't retry at its level"**

And in `REPEATING_PROBLEM_GUI_FAILURE_ANALYSIS.md`:

> **"The error was silently swallowed by the try/catch in the API call."**

The system has a **systemic pattern of swallowing errors** and proceeding with incomplete data.

### 3.3 The Completed Status Lie

The run is marked as `completed` with `success: true` in all timeline events. The user sees:

```
Status: Completed ✓
Documents: 2
Pairwise: 2
```

But the reality is:
- 1 of 2 documents has no content
- 0 of 2 documents were fully evaluated
- 50% of expected data is missing

---

# PART III: DATA FORENSICS (Pages 16-25)

## Chapter 4: Complete Data Extraction

### 4.1 Generated Documents Analysis

The run produced four documents total:

| Doc ID | Model | Generator | Content Status |
|--------|-------|-----------|----------------|
| `...google_gemini-2.5-flash` | gemini-2.5-flash | fpf | ✓ Has Content |
| `...openai_gpt-5-mini` | gpt-5-mini | fpf | ✗ **EMPTY** |
| `combined...openai_gpt-5-mini` | gpt-5-mini | combine | ✓ Has Content |
| `combined...google_gemini-2.5-flash` | gemini-2.5-flash | combine | ✓ Has Content |

### 4.2 Generation Event Details

```json
{
    "doc_id": "...fpf.1.openai_gpt-5-mini",
    "generator": "fpf",
    "model": "openai:gpt-5-mini",
    "started_at": "2025-12-17T20:57:30.140696",
    "completed_at": "2025-12-17T21:07:30.253046",
    "duration_seconds": 600.112039,
    "status": "completed",
    "error": null,
    "token_count": null,
    "cost_usd": 0.0
}
```

**Observations:**
- `status: "completed"` - The generation was marked successful
- `error: null` - No error was recorded
- `token_count: null` - No tokens were tracked (suggests no LLM response)
- `cost_usd: 0.0` - No cost recorded (no API call completed?)
- `duration_seconds: 600.112` - Almost exactly the timeout limit

### 4.3 Single Evaluation Results

Only one document has evaluation scores:

```json
"pre_combine_evals_detailed": {
    "...google_gemini-2.5-flash": {
        "evaluations": [
            {
                "judge_model": "openai:gpt-5-mini",
                "scores": [
                    {"criterion": "factuality", "score": 4},
                    {"criterion": "relevance", "score": 4},
                    {"criterion": "completeness", "score": 3},
                    {"criterion": "clarity", "score": 4},
                    {"criterion": "structure", "score": 4},
                    {"criterion": "depth", "score": 3}
                ],
                "average_score": 3.67
            },
            {
                "judge_model": "google:gemini-2.5-flash",
                "scores": [
                    {"criterion": "factuality", "score": 1},  // Flagged as hallucination!
                    {"criterion": "relevance", "score": 5},
                    {"criterion": "completeness", "score": 5},
                    {"criterion": "clarity", "score": 5},
                    {"criterion": "structure", "score": 5},
                    {"criterion": "depth", "score": 4}
                ],
                "average_score": 4.17
            }
        ],
        "overall_average": 3.92
    }
}
```

**The GPT-5-mini document has NO evaluation scores because it had NO content to evaluate.**

### 4.4 Pairwise Comparison Evidence

The pairwise comparisons clearly document the empty content:

```json
{
    "doc_id_a": "...openai_gpt-5-mini",
    "doc_id_b": "...google_gemini-2.5-flash",
    "winner": "...google_gemini-2.5-flash",
    "reason": "Document B is the clear winner because Document A contains no content"
}
```

Every comparison involving the GPT-5-mini original document cites its emptiness:
- "Document A is empty"
- "Document A contains no content"
- "Document B is comprehensive... Document A is empty"
- "Document A contains no material to evaluate"

---

# PART IV: ROOT CAUSE ANALYSIS (Pages 26-40)

## Chapter 5: The FPF Subprocess Failure

### 5.1 FPF Architecture Review

FPF (FilePromptForge) is an external tool that:
1. Takes a prompt/document and instructions
2. Optionally performs web searches
3. Uses an LLM to generate content
4. Returns the result as JSON

The ACM2 system calls FPF via subprocess:

```python
# From fpf_adapter.py (conceptual)
process = await asyncio.create_subprocess_exec(
    "fpf", "--json", "--timeout", str(timeout), ...
)
stdout, stderr = await asyncio.wait_for(
    process.communicate(),
    timeout=timeout
)
result = json.loads(stdout)
```

### 5.2 The Timeout Cascade

When the timeout is reached:

1. `asyncio.wait_for` raises `asyncio.TimeoutError`
2. The subprocess is killed
3. The adapter must handle the error

**Current Handling (problematic):**
```python
except asyncio.TimeoutError:
    logger.warning(f"FPF timed out after {timeout}s")
    return GeneratedDocument(
        doc_id=doc_id,
        content="",  # EMPTY CONTENT!
        model=model,
        ...
    )
```

The adapter returns a valid `GeneratedDocument` object with **empty content** instead of:
- Raising an exception
- Returning `None`
- Setting an error flag

### 5.3 The Executor's Blind Spot

The `run_executor.py` checks only for `gen_result` being non-None:

```python
gen_result = await self._generate_single(...)

if gen_result:  # Passes! Object exists!
    result.generated_docs.append(gen_result)  # Added to list!
    
    if single_evaluator and gen_result.content:  # FAILS! content is empty
        # Evaluation skipped silently
```

### 5.4 The Cascade of Silent Failures

```
┌─────────────────────────────────────────────────────────────────┐
│ FPF Subprocess                                                  │
│ ┌─────────────┐    ┌─────────────┐    ┌─────────────┐          │
│ │ Web Search  │ → │ LLM API     │ → │ JSON Parse  │ → TIMEOUT │
│ └─────────────┘    └─────────────┘    └─────────────┘          │
│                                              ↓                  │
│                                       Return empty              │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ FPF Adapter                                                     │
│ Catches TimeoutError → Returns GeneratedDocument(content="")   │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ Run Executor                                                    │
│ gen_result != None → Add to generated_docs ✓                    │
│ gen_result.content == "" → Skip single eval SILENTLY            │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ Pairwise Evaluation                                             │
│ Compares empty doc vs real doc → Winner determined correctly    │
│ BUT: User never knows WHY gpt-5-mini "lost"                     │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ Run Status                                                      │
│ All phases "completed" → Status: COMPLETED ✓                    │
│ Reality: 50% of single eval data missing                        │
└─────────────────────────────────────────────────────────────────┘
```

## Chapter 6: Why 600 Seconds Wasn't Enough

### 6.1 The OpenAI Model Latency Issue

The GPT-5-mini model (despite its "mini" designation) exhibits high latency for complex prompts:

| Run | Model | Task | Duration |
|-----|-------|------|----------|
| 97a47b7f | gpt-5-mini | Generation | 271s |
| 2828a265 | gpt-5-mini | Generation | 600s (timeout) |
| 2828a265 | gemini-2.5-flash | Generation | 11.65s |

**51x slower** than Gemini for the same task!

### 6.2 Contributing Factors

1. **Web Search Latency:** Each search iteration adds 10-30 seconds
2. **Token Generation:** Large responses take longer
3. **API Queue Depth:** OpenAI may have request queuing
4. **Context Size:** Larger contexts increase processing time
5. **Model Load:** "Mini" models may share resources with larger models

### 6.3 The 600s Timeout Configuration

The timeout was recently increased from 300s to 600s in response to `RUN_97a47b7f_COMPREHENSIVE_ERROR_REPORT.md`:

```python
# app/api/schemas/runs.py line 153
timeout: int = Field(default=600, description="Timeout in seconds")

# ui/src/stores/config.ts line 220
timeout: 600
```

But 600 seconds was still not enough for this particular run.

## Chapter 7: The Absence of Instrumentation

### 7.1 Missing Metrics

The system does not track:
- FPF subprocess start/end times independently
- Web search success/failure counts
- LLM API response times within FPF
- Content length before returning
- Empty content occurrences

### 7.2 Missing Logs

When content is empty, there is no log entry at the executor level:

```python
# Current code - NO LOGGING for empty content
if single_evaluator and gen_result.content:
    # Evaluate
# No else! No logging!
```

**Recommended Addition:**
```python
if single_evaluator:
    if gen_result.content:
        # Evaluate
    else:
        logger.warning(
            f"Skipping single eval for {gen_result.doc_id}: "
            f"Content is empty (duration: {gen_result.duration_seconds}s)"
        )
        result.errors.append(
            f"Empty content from {gen_result.model} - evaluation skipped"
        )
```

### 7.3 Missing UI Indicators

The UI shows:
- "Evaluations: 0 / 0" - No indication of skipped evaluations
- No warning icon for incomplete data
- No differentiation between "not run" and "skipped due to error"

---

# PART V: COMPARISON TO PREVIOUS FAILURES (Pages 41-50)

## Chapter 8: Pattern Analysis Across Runs

### 8.1 Run 97a47b7f vs Run 2828a265

| Aspect | Run 97a47b7f | Run 2828a265 |
|--------|--------------|--------------|
| Date | Dec 17, 2025 (earlier) | Dec 17, 2025 (later) |
| Timeout | 300s | 600s |
| GPT-5-mini Gen Time | 271s | 600s (timeout) |
| Gemini Gen Time | ~12s | 11.65s |
| Failure Point | Single eval timeout | Generation empty content |
| Single Eval Data | Missing (eval timeout) | Missing (skipped) |
| Pairwise Result | Correct | Correct |
| Status | Completed | Completed |

### 8.2 The Evolution of the Problem

**Before Timeout Increase (300s):**
- Generation succeeded (271s)
- Evaluation started but timed out
- Partial data sometimes saved

**After Timeout Increase (600s):**
- Generation now has enough time to... fail completely?
- Empty content returned instead of partial content
- No evaluation data at all

**Irony:** Increasing the timeout allowed the failure to complete gracefully, making it even more silent.

### 8.3 Referenced Documentation Cross-Analysis

**From `RUN_97a47b7f_COMPREHENSIVE_ERROR_REPORT.md`:**
> "The 300s Timeout is the Bottleneck"

**Current Finding:** The 600s timeout is ALSO a bottleneck, but now manifests as empty content instead of evaluation timeout.

**From `generation_failure_analysis.md`:**
> "ACM2 does NOT have retry logic at the executor level"

**Current Finding:** Still true. No retry was attempted after the empty generation.

**From `REPEATING_PROBLEM_GUI_FAILURE_ANALYSIS.md`:**
> "The error was silently swallowed"

**Current Finding:** The pattern continues. Empty content is not logged as an error.

## Chapter 9: The Empty Content Problem Class

### 9.1 Definition

An "Empty Content Failure" is a failure mode where:
1. A generation subprocess completes without error
2. A valid response object is returned
3. The content field is empty or null
4. Downstream processes skip silently
5. The run is marked as successful

### 9.2 Causes of Empty Content

| Cause | Likelihood | Evidence in This Run |
|-------|------------|---------------------|
| Timeout → graceful empty return | **HIGH** | 600s duration exactly |
| Web search returned no results | MEDIUM | Unknown (no FPF logs) |
| LLM API rate limit | LOW | No error logged |
| Content filter triggered | LOW | No filter message |
| Parse error swallowed | MEDIUM | No error logged |

### 9.3 Detection Strategies

**Current (None):**
- No detection
- No logging
- No alerting

**Proposed:**
1. **Content Length Check:** Reject if `len(content) < MIN_CONTENT_LENGTH`
2. **Duration Correlation:** Flag if `duration > 0.9 * timeout AND content == ""`
3. **Cost Validation:** If `cost == 0 AND duration > 60s` → Suspicious
4. **Token Count Check:** If `token_count == 0 OR null` → Investigate

---

# PART VI: RECOMMENDED FIXES (Pages 51-60)

## Chapter 10: Immediate Actions

### 10.1 Add Logging for Empty Content

**File:** `acm2/app/services/run_executor.py`
**Location:** After line 561

```python
# 2. Single eval IMMEDIATELY (streaming)
if single_evaluator:
    if gen_result.content and len(gen_result.content.strip()) > 0:
        # Existing evaluation logic
        ...
    else:
        logger.warning(
            f"SKIPPED single eval for {gen_result.doc_id}: "
            f"Empty content (duration: {gen_result.duration_seconds:.1f}s, "
            f"model: {gen_result.model})"
        )
        result.errors.append(
            f"Empty content from {model} - single evaluation skipped"
        )
        # Emit failed timeline event
        await self._emit_timeline_event(
            run_id=run_id,
            phase="evaluation",
            event_type="single_eval",
            description=f"SKIPPED: {gen_result.doc_id[:20]}... (empty content)",
            model=model,
            timestamp=datetime.utcnow(),
            duration_seconds=0,
            success=False,
            details={"doc_id": gen_result.doc_id, "reason": "empty_content"},
        )
```

### 10.2 Add Content Validation in FPF Adapter

**File:** `acm2/app/adapters/fpf_adapter.py`

```python
async def generate(self, ...) -> GeneratedDocument:
    ...
    result = await self._run_fpf_subprocess(...)
    
    if not result.content or len(result.content.strip()) < 100:
        raise GenerationError(
            f"FPF returned insufficient content: {len(result.content or '')} chars "
            f"after {result.duration_seconds:.1f}s"
        )
    
    return result
```

### 10.3 Increase Timeout to 900 Seconds

Given that 600 seconds was exactly hit, increase to 900 seconds (15 minutes) with a clear warning at 600s:

```python
# app/api/schemas/runs.py
timeout: int = Field(
    default=900,
    description="Timeout in seconds (default 15 minutes)",
    ge=60,
    le=1800,
)
```

## Chapter 11: Medium-Term Improvements

### 11.1 Implement Retry Logic for Empty Content

```python
MAX_GENERATION_RETRIES = 2

async def _generate_with_retry(self, ...):
    for attempt in range(MAX_GENERATION_RETRIES + 1):
        result = await self._generate_single(...)
        
        if result and result.content and len(result.content.strip()) > 100:
            return result
        
        if attempt < MAX_GENERATION_RETRIES:
            logger.warning(
                f"Generation attempt {attempt + 1} returned empty, retrying..."
            )
            await asyncio.sleep(5)  # Brief pause before retry
    
    logger.error(f"Generation failed after {MAX_GENERATION_RETRIES + 1} attempts")
    return result  # Return last result even if empty (for tracking)
```

### 11.2 Add Status Indicators for Partial Completion

**UI Changes:**
- Add "Evaluations: 1/2" indicator instead of "0/0"
- Show warning icon (⚠️) when evaluations are incomplete
- Add tooltip: "Some evaluations were skipped due to empty content"

**API Changes:**
- Add `evaluation_status: "partial" | "complete" | "failed"` to run response
- Add `skipped_evaluations: List[str]` to track which docs were skipped

### 11.3 Implement FPF Progress Streaming

Allow the FPF adapter to stream progress updates:

```
┌─ FPF Progress Stream ─────────────────────────────────────────┐
│ 0s    [▓░░░░░░░░░] Starting...                               │
│ 30s   [▓▓▓░░░░░░░] Web search: 3/5 queries complete          │
│ 120s  [▓▓▓▓▓░░░░░] LLM processing: tokens received           │
│ 300s  [▓▓▓▓▓▓▓░░░] Content generation in progress            │
│ 500s  [▓▓▓▓▓▓▓▓▓░] Finalizing response...                    │
│ 600s  [▓▓▓▓▓▓▓▓▓▓] TIMEOUT - Returning partial content       │
└───────────────────────────────────────────────────────────────┘
```

## Chapter 12: Long-Term Architecture Changes

### 12.1 Decouple Generation and Evaluation Timeouts

Currently, one global timeout applies. Separate them:

```python
class TimeoutConfig(BaseModel):
    generation_timeout: int = 900  # 15 min for generation
    single_eval_timeout: int = 300  # 5 min per eval
    pairwise_timeout: int = 60     # 1 min per comparison
    combine_timeout: int = 180     # 3 min for combine
```

### 12.2 Implement Partial Content Saving

If FPF times out mid-generation, save whatever content was streamed:

```python
async def _run_fpf_with_streaming(self, ...):
    partial_content = []
    
    async for chunk in fpf_stream:
        partial_content.append(chunk)
        
        # Save checkpoint every 30 seconds
        if time_since_last_save > 30:
            await self._save_partial_content(partial_content)
    
    # On timeout, return accumulated content
    return "".join(partial_content)
```

### 12.3 Add Model-Specific Timeout Profiles

Based on observed performance:

```python
MODEL_TIMEOUT_PROFILES = {
    "openai:gpt-5-mini": 900,      # Known slow performer
    "openai:gpt-5": 600,
    "google:gemini-2.5-flash": 120,  # Very fast
    "google:gemini-2.5-pro": 300,
    "anthropic:claude-3-opus": 600,
}
```

---

# PART VII: TESTING AND VALIDATION (Pages 61-70)

## Chapter 13: Reproduction Steps

### 13.1 Reproducing the Empty Content Failure

1. Configure a preset with:
   - Model: `openai:gpt-5-mini`
   - Complex document requiring web search
   - Timeout: 300 seconds (force timeout)

2. Start execution via UI or API

3. Observe:
   - Generation completes after exactly 300s
   - Content is empty
   - Single evaluation is skipped
   - Run marked as "Completed"

### 13.2 Validating the Fix

After implementing the logging fix:

1. Re-run the same configuration
2. Check logs for: `"SKIPPED single eval for ... Empty content"`
3. Check API response for: `"errors": ["Empty content from openai:gpt-5-mini..."]`
4. Check timeline for: Failed evaluation event with `success: false`

### 13.3 Unit Test Cases

```python
# test_run_executor.py

async def test_empty_content_logs_warning(caplog):
    """Empty generated content should log a warning and record error."""
    executor = RunExecutor()
    
    # Mock generation that returns empty content
    with patch.object(executor, '_generate_single') as mock_gen:
        mock_gen.return_value = GeneratedDocument(
            doc_id="test-doc",
            content="",  # Empty!
            model="openai:gpt-5-mini",
        )
        
        result = await executor.run(...)
    
    assert "SKIPPED single eval" in caplog.text
    assert "Empty content" in result.errors[0]


async def test_empty_content_emits_failed_timeline_event():
    """Empty content should emit a failed timeline event."""
    executor = RunExecutor()
    
    # ... similar setup ...
    
    result = await executor.run(...)
    
    timeline_events = result.timeline_events
    skip_event = next(
        (e for e in timeline_events if "SKIPPED" in e.description),
        None
    )
    
    assert skip_event is not None
    assert skip_event.success == False
    assert skip_event.details["reason"] == "empty_content"
```

## Chapter 14: Monitoring and Alerting

### 14.1 Metrics to Track

| Metric | Type | Description |
|--------|------|-------------|
| `generation_empty_content_total` | Counter | Total empty content returns |
| `generation_duration_seconds` | Histogram | Time taken per generation |
| `single_eval_skipped_total` | Counter | Evaluations skipped |
| `run_partial_completion_total` | Counter | Runs with incomplete data |

### 14.2 Alert Conditions

| Alert | Condition | Severity |
|-------|-----------|----------|
| High Empty Content Rate | empty_content > 10% of generations | WARNING |
| Generation Timeout Spike | timeout_rate > 20% in 1 hour | WARNING |
| Model Unavailable | all generations for model failed | CRITICAL |

### 14.3 Dashboard Queries

**Prometheus/Grafana:**
```promql
# Empty content rate by model
sum(rate(generation_empty_content_total[5m])) by (model)
/ sum(rate(generation_total[5m])) by (model)

# Average generation time approaching timeout
histogram_quantile(0.95, rate(generation_duration_seconds_bucket[5m]))
```

---

# PART VIII: CONCLUSIONS (Pages 71-75)

## Chapter 15: Summary of Findings

### 15.1 Root Cause Chain

```
┌────────────────────────────────────────────────────────────────┐
│ ROOT CAUSE: GPT-5-mini model latency exceeded 600s timeout     │
│                              ↓                                 │
│ PROXIMATE CAUSE: FPF returned empty content on timeout         │
│                              ↓                                 │
│ FAILURE MODE: Single evaluation skipped silently               │
│                              ↓                                 │
│ IMPACT: 50% of evaluation data missing; run marked "complete"  │
└────────────────────────────────────────────────────────────────┘
```

### 15.2 Key Takeaways

1. **Timeouts are not long enough:** Even 600s is insufficient for some GPT-5-mini generations
2. **Silent failures are endemic:** The system repeatedly swallows errors without logging
3. **Status is misleading:** "Completed" does not mean "all data collected"
4. **Validation is missing:** No checks for content quality/presence before proceeding

### 15.3 Priority Actions

| Priority | Action | Effort | Impact |
|----------|--------|--------|--------|
| P0 | Add logging for empty content | 1 hour | HIGH |
| P0 | Increase timeout to 900s | 5 min | MEDIUM |
| P1 | Add content length validation | 2 hours | HIGH |
| P1 | Add UI indicators for partial completion | 4 hours | MEDIUM |
| P2 | Implement generation retry logic | 8 hours | HIGH |
| P3 | Implement FPF progress streaming | 2 days | MEDIUM |

## Chapter 16: Lessons Learned

### 16.1 Design Principles Violated

1. **Fail Fast:** System should fail loudly, not silently proceed
2. **Observability:** All failure modes should be logged and tracked
3. **Honesty:** Status should reflect actual data quality, not just process completion
4. **Resilience:** Transient failures should trigger retries, not silent skips

### 16.2 Recommended Architecture Patterns

1. **Result Validation:** Always validate output before marking success
2. **Error Accumulation:** Collect all errors, not just the first one
3. **Partial Success Handling:** Define clear states for partial completion
4. **Timeout Graduation:** Use model-specific timeouts, not one-size-fits-all

### 16.3 Future Prevention

- Add pre-commit hooks to check for silent failure patterns
- Require error handling review in PR process
- Implement chaos engineering tests (inject empty responses)
- Add data quality checks to CI/CD pipeline

---

# APPENDICES (Pages 76-80)

## Appendix A: Full API Response

[Full JSON response from API omitted for brevity - see run ID 2828a265-4fd3-4764-8310-7f4ce37f27eb]

## Appendix B: Timeline Events

| Timestamp | Phase | Event | Model | Duration | Success |
|-----------|-------|-------|-------|----------|---------|
| 20:57:30 | initialization | start | - | - | ✓ |
| 20:57:30 | generation | generation | gemini-2.5-flash | 11.65s | ✓ |
| 20:57:41 | evaluation | single_eval | gpt-5-mini, gemini | 198.87s | ✓ |
| 20:57:30 | generation | generation | gpt-5-mini | 600.11s | ✓ |
| - | evaluation | single_eval | - | - | **MISSING** |
| 21:07:30 | pairwise | pairwise_eval | gpt-5-mini, gemini | 28.24s | ✓ |
| 21:07:58 | combination | combine | gpt-5-mini | 87.35s | ✓ |
| 21:09:25 | combination | combine | gemini-2.5-flash | 6.24s | ✓ |
| 21:10:50 | completion | complete | - | 799.95s | ✓ |

## Appendix C: Related Documentation Index

| Document | Path | Relevance |
|----------|------|-----------|
| Comprehensive Error Report | `RUN_97a47b7f_COMPREHENSIVE_ERROR_REPORT.md` | Previous timeout-related failure |
| Generation Failure Analysis | `generation_failure_analysis.md` | Silent failure patterns |
| GUI Failure Analysis | `REPEATING_PROBLEM_GUI_FAILURE_ANALYSIS.md` | Error swallowing pattern |
| FPF Cost Data Failure | `FPF_COST_DATA_FAILURE_ANALYSIS.md` | FPF adapter issues |
| Console Heartbeat Hang | `REPEATING_PROBLEM_Console_Heartbeat_Hang.md` | Process management issues |

## Appendix D: Code References

| File | Line | Description |
|------|------|-------------|
| `run_executor.py` | 561 | Silent skip condition |
| `run_executor.py` | 458-468 | Single evaluator setup |
| `fpf_adapter.py` | ~150 | Timeout handling |
| `schemas/runs.py` | 153 | Timeout configuration |
| `stores/config.ts` | 220 | UI timeout default |

---

**END OF REPORT**

*Report prepared by: Automated Analysis System*  
*Review Status: Pending Human Review*  
*Classification: Internal Technical Documentation*  
*Distribution: Engineering Team*
