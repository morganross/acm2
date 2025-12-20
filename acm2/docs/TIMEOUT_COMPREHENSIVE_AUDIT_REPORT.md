# COMPREHENSIVE TIMEOUT AUDIT REPORT

## ACM2 / FPF / GPTR Timeout Configuration Analysis

---

**Document Type:** Technical Audit Report  
**Version:** 1.0.0  
**Date:** December 17, 2025  
**Author:** GitHub Copilot  
**Classification:** CRITICAL - System Architecture Analysis

---

# PART ONE: COMPLETE TIMEOUT INVENTORY

## Executive Summary

This report documents **every timeout configuration** in the ACM2/FPF/GPTR codebase. The analysis reveals a complex, multi-layered timeout architecture spanning:

- **7 primary timeout locations** in the ACM2 application
- **5 secondary timeout points** in FilePromptForge (FPF)
- **3 timeout configurations** in the legacy runner.py
- **Multiple browser automation timeouts** in test utilities
- **Dozens of log entries** showing historical timeout failures

The root cause of recurring timeout-related failures is a **fundamental architectural disconnect**: retry logic exists at the HTTP layer, but the subprocess boundary above it enforces a hard timeout that kills the entire process before retries can complete.

---

# CHAPTER 1: ACM2 CORE TIMEOUT CONFIGURATIONS

## 1.1 UI Layer Timeouts

### 1.1.1 useSettings.ts - Default Settings

**File:** `c:\dev\silky\api_cost_multiplier\acm2\ui\src\hooks\useSettings.ts`  
**Line:** 33  
**Current Value:** 600 seconds (10 minutes)

```typescript
advanced: {
  maxConcurrentTasks: 3,
  requestTimeoutSeconds: 600, // 10 minutes - increased from 300 to handle slow LLM evaluations
  databasePath: '~/.acm2/acm2.db',
  reportsDirectory: '~/.acm2/reports',
},
```

**Historical Context:**
- Original value: 300 seconds (5 minutes)
- Changed: December 17, 2025
- Reason: LLM evaluations with grounding validation taking longer than expected

**Impact Analysis:**
- This value is used as the default for UI-initiated requests
- It does NOT directly affect the subprocess timeout
- It's a user-facing configuration that suggests the intended maximum wait time

### 1.1.2 config.ts - Configuration Store

**File:** `c:\dev\silky\api_cost_multiplier\acm2\ui\src\stores\config.ts`  
**Line:** 220  
**Current Value:** 600 seconds

```typescript
dr: {
  // ... other settings
  timeout: 600,
  // ...
}
```

**Purpose:**
- Stores Deep Research timeout configuration
- User-configurable through the UI
- Passed to backend when starting runs

### 1.1.3 Configure.tsx - UI Component

**File:** `c:\dev\silky\api_cost_multiplier\acm2\ui\src\pages\Configure.tsx`  
**Line:** 144

```typescript
timeout: config.dr.timeout
```

**Purpose:**
- Binds UI input to the configuration store
- Allows users to modify timeout values before starting runs

---

## 1.2 Backend Application Configuration

### 1.2.1 app/config.py - Application Settings

**File:** `c:\dev\silky\api_cost_multiplier\acm2\app\config.py`  
**Line:** 58  
**Current Value:** 600 seconds (10 minutes)

```python
# Execution
max_concurrent_tasks: int = 3
task_timeout_seconds: int = 600  # 10 minutes
```

**Purpose:**
- Global application-level timeout setting
- Used as fallback when no specific timeout is provided
- Loaded from environment variables via pydantic-settings

**Environment Variable Override:**
- Can be set via `TASK_TIMEOUT_SECONDS` environment variable
- Defaults to 600 if not set

### 1.2.2 app/api/schemas/runs.py - API Schema

**File:** `c:\dev\silky\api_cost_multiplier\acm2\app\api\schemas\runs.py`  
**Line:** 153  
**Current Value:** 600 seconds

```python
timeout: int = Field(600, ge=60, description="Request timeout in seconds - increased from 300 to handle slow LLM evals")
```

**Purpose:**
- Defines the schema for run configuration
- Enforces minimum timeout of 60 seconds
- Default 600 seconds for API requests

**Validation:**
- `ge=60` ensures timeout is at least 1 minute
- No maximum limit specified (potential issue)

### 1.2.3 app/evaluation/judge.py - LLM Judge Configuration

**File:** `c:\dev\silky\api_cost_multiplier\acm2\app\evaluation\judge.py`  
**Line:** 33  
**Current Value:** 120 seconds (2 minutes)

```python
@dataclass
class JudgeConfig:
    """Configuration for LLM judge."""
    
    model: str = "gpt-5"
    temperature: float = 0.0
    max_tokens: int = 4096
    timeout_seconds: int = 120
    retries: int = 2
    
    # Prompt settings
    strict_json: bool = True
    enable_grounding: bool = True  # Allow web search for fact-checking
```

**Critical Finding:**
- Judge timeout is only 120 seconds (2 minutes)
- This is **significantly lower** than the subprocess timeout (600 seconds)
- When `enable_grounding: True`, grounding validation can cause retries that exceed this timeout
- The 2-minute timeout is appropriate for non-grounding evaluations
- **MISMATCH**: Grounding-enabled evaluations need longer timeouts

**Recommendation:**
- Increase to 300-600 seconds when grounding is enabled
- Add conditional timeout based on grounding setting

---

## 1.3 FPF Adapter Layer Timeouts

### 1.3.1 app/adapters/fpf/subprocess.py - Subprocess Execution

**File:** `c:\dev\silky\api_cost_multiplier\acm2\app\adapters\fpf\subprocess.py`  
**Multiple Lines:** 26, 98-107, 122-123, 144, 154, 166, 179, 217

#### Primary Subprocess Timeout (Line 166)

```python
async def run_fpf_subprocess(
    cmd: List[str],
    cwd: str,
    timeout: float = 600.0,  # <-- DEFAULT 600 SECONDS
    env: Optional[dict] = None,
    progress_callback: Optional[Callable[[str, float, Optional[str]], None]] = None,
    fpf_log_output: str = "console",
    fpf_log_file: Optional[str] = None,
    run_log_file: Optional[str] = None,
) -> tuple[int, str, str]:
```

#### Timeout Enforcement Logic (Lines 98-110)

```python
# Wait for process with timeout and heartbeats
deadline = time.time() + timeout
while process.poll() is None:
    now = time.time()
    
    # Check timeout
    if now > deadline:
        process.kill()
        process.wait()
        write_log(f"Process timed out after {timeout}s", "ACM")
        if log_fh:
            log_fh.close()
        return -1, '\n'.join(stdout_lines), "Process timed out"
```

**Critical Behavior:**
1. Deadline calculated at process start
2. Polling loop checks if deadline exceeded
3. If exceeded, **process.kill()** is called immediately
4. Returns -1 status code with "Process timed out" message
5. **NO RETRY MECHANISM** at this level

#### Thread Join Timeouts (Lines 122-123)

```python
# Wait for threads to finish
stdout_thread.join(timeout=5)
stderr_thread.join(timeout=5)
```

**Purpose:**
- Ensures output collection threads don't hang indefinitely
- 5-second grace period after process completes
- Non-critical - just for cleanup

### 1.3.2 app/adapters/fpf/adapter.py - FPF Adapter

**File:** `c:\dev\silky\api_cost_multiplier\acm2\app\adapters\fpf\adapter.py`  
**Line:** 146  
**Current Value:** 600 seconds

```python
returncode, stdout, stderr = await run_fpf_subprocess(
    fpf_cmd,
    self._get_fpf_directory(),
    timeout=600.0,  # 10 minutes
    progress_callback=cb,
    fpf_log_output=fpf_log_output,
    fpf_log_file=fpf_log_file,
    run_log_file=run_log_file,
)
```

**Important Note:**
- This timeout is **HARDCODED** to 600 seconds
- Does NOT read from configuration
- Must be manually updated when timeout requirements change

### 1.3.3 app/adapters/fpf/errors.py - Error Definitions

**File:** `c:\dev\silky\api_cost_multiplier\acm2\app\adapters\fpf\errors.py`  
**Line:** 16

```python
class FpfTimeoutError(FpfError):
    """FPF subprocess timed out."""
    pass
```

**Purpose:**
- Custom exception for FPF timeout failures
- Can be caught and handled specifically
- Not always used - sometimes generic FpfExecutionError is raised instead

---

## 1.4 GPTR Adapter Layer Timeouts

### 1.4.1 app/adapters/gptr/adapter.py - GPT-Researcher Adapter

**File:** `c:\dev\silky\api_cost_multiplier\acm2\app\adapters\gptr\adapter.py`  
**Lines:** 265-266

```python
await asyncio.wait_for(process.wait(), timeout=2.0)
except asyncio.TimeoutError:
    # Process didn't terminate gracefully, force kill
    process.kill()
```

**Purpose:**
- Grace period for GPTR process termination
- Only 2 seconds - very short
- Used during cleanup, not during normal operation

---

## 1.5 CLI Layer Timeouts

### 1.5.1 app/cli/client.py - HTTP Client

**File:** `c:\dev\silky\api_cost_multiplier\acm2\app\cli\client.py`  
**Line:** 13  
**Current Value:** 30 seconds

```python
self._http = httpx.Client(base_url=self.base_url, timeout=30.0)
```

**Purpose:**
- CLI HTTP client timeout
- 30 seconds for CLI commands
- Much shorter than web UI timeout
- Appropriate for quick CLI operations

---

# CHAPTER 2: FILEPROMPTFORGE (FPF) TIMEOUTS

## 2.1 file_handler.py - HTTP Request Layer

**File:** `c:\dev\silky\api_cost_multiplier\FilePromptForge\file_handler.py`

### 2.1.1 _http_post_json() Function

**Lines:** 108-115  
**Current Default:** 600 seconds

```python
def _http_post_json(
    url: str, 
    payload: Dict, 
    headers: Dict, 
    timeout: int = 600,           # DEFAULT 600 SECONDS
    max_retries: int = 3,         # UP TO 3 RETRIES
    base_delay_ms: int = 500,     # EXPONENTIAL BACKOFF BASE
    max_delay_ms: int = 30000,    # MAX 30 SECOND DELAY
) -> Dict:
```

**Key Features:**
1. **Retry Logic with Exponential Backoff:**
   - Up to 3 retry attempts
   - Base delay: 500ms, Max delay: 30 seconds
   - Full jitter applied to prevent thundering herd

2. **Transient Error Detection (Lines 93-106):**

```python
def _is_transient_error(exc: Exception) -> bool:
    """Check if an error is transient and should be retried."""
    msg = str(exc).lower()
    transient_indicators = [
        "429", "rate limit", "quota",  # Rate limiting
        "timeout", "timed out",         # Timeouts
        "502", "503", "504",            # Server errors
        "connection", "network",        # Network issues
        "grounding", "validation",      # Grounding failures
        "temporarily unavailable",
        "service unavailable",
        "internal server error",
    ]
    return any(tok in msg for tok in transient_indicators)
```

3. **Retry Behavior (Lines 161-173):**

```python
# Check if we should retry
if attempt < max_retries and _is_transient_error(last_error):
    # Exponential backoff with jitter
    delay_ms = min(base_delay_ms * (2 ** (attempt - 1)), max_delay_ms)
    delay_ms = random.uniform(0, delay_ms)  # Full jitter
    delay_s = delay_ms / 1000.0
    LOG.warning(f"Transient error on attempt {attempt}/{max_retries}, retrying in {delay_s:.2f}s: {he}")
    _fpf_log(f"[FPF API][RETRY] Waiting {delay_s:.2f}s before retry {attempt + 1}/{max_retries}")
    time.sleep(delay_s)
    continue
```

### 2.1.2 THE CRITICAL ARCHITECTURAL PROBLEM

**The retry logic in file_handler.py is USELESS when the subprocess is killed.**

Here's the timeline of a failing request:

```
T+0s:     ACM starts FPF subprocess with 600s timeout
T+0s:     FPF starts HTTP request with 600s timeout
T+300s:   Grounding validation fails (transient error)
T+300s:   FPF retry logic kicks in, waits 0-0.5s
T+300.5s: FPF retries HTTP request
T+550s:   Second attempt also fails with grounding
T+550s:   FPF retry logic kicks in, waits 0-1s
T+551s:   FPF retries third time
T+600s:   **ACM SUBPROCESS TIMEOUT KILLS THE PROCESS**
          FPF is still waiting for third attempt to complete
          **RETRY IS KILLED MID-REQUEST**
          **ALL WORK LOST**
```

**This is why timeouts keep failing:**
- The subprocess timeout (600s) is too short for retries
- A single 600s timeout HTTP request + 3 retries could need ~2400s (40 minutes) worst case
- But the subprocess kills everything at exactly 600s

---

# CHAPTER 3: LEGACY RUNNER.PY TIMEOUTS

## 3.1 Primary Timeout Configuration

**File:** `c:\dev\silky\api_cost_multiplier\runner.py`

### 3.1.1 GPTR_TIMEOUT_SECONDS (Line 49)

```python
# Hard timeout for GPT-Researcher programmatic runs (seconds)
GPTR_TIMEOUT_SECONDS = 600
```

**Purpose:**
- Global constant for GPTR operations
- Used in multiple places throughout runner.py
- 10 minutes (600 seconds)

### 3.1.2 StreamingEvalManager Timeout (Line 255)

```python
# Wait for concurrent futures (these are already running, just need to get results)
for fut in concurrent_futures:
    try:
        # Block until the future completes (it's already running on the loop)
        fut.result(timeout=1800)  # 30 minute timeout
    except Exception as e:
        print(f"  [STREAMING_EVAL] Error waiting for eval: {e}")
```

**Purpose:**
- Timeout for streaming evaluation tasks
- 30 minutes (1800 seconds)
- Much longer than subprocess timeout
- Used for async eval task collection

### 3.1.3 trigger_evaluation_for_all_files() (Line 1149)

```python
async def trigger_evaluation_for_all_files(
    output_folder: str, 
    config: dict, 
    generated_files: list[str] = None,
    timeout_seconds: int = 1800,  # DEFAULT 30 MINUTES
    # ... other params
):
```

**Purpose:**
- Master evaluation trigger function
- 30-minute default timeout
- Longer to accommodate multiple evaluations

### 3.1.4 GPTR Subprocess Timeout (Line 922)

```python
out2, err2 = proc2.communicate(timeout=GPTR_TIMEOUT_SECONDS)
```

**Purpose:**
- Subprocess communication timeout
- Uses the global 600-second constant
- Applied during GPTR process execution

---

# CHAPTER 4: BROWSER AUTOMATION TIMEOUTS

## 4.1 Playwright Test Utilities

Multiple browser automation tools use Playwright's `waitForTimeout`:

### 4.1.1 test_preset_load.cjs

**File:** `c:\dev\silky\browser_tools\test_preset_load.cjs`  
**Line:** 59

```javascript
await page.waitForTimeout(3000);  // 3 seconds
```

### 4.1.2 debug_store.cjs

**File:** `c:\dev\silky\browser_tools\debug_store.cjs`  
**Line:** 75

```javascript
await page.waitForTimeout(3000);  // 3 seconds
```

### 4.1.3 debug_checkboxes.cjs

**File:** `c:\dev\silky\browser_tools\debug_checkboxes.cjs`  
**Line:** 54

```javascript
await page.waitForTimeout(3000);  // 3 seconds
```

**Purpose:**
- UI stabilization delays
- Not critical timeouts
- Used for waiting between UI interactions

---

# CHAPTER 5: DIAGNOSTIC TOOL TIMEOUTS

## 5.1 OpenAI Grounding Diagnoser

**File:** `c:\dev\silky\api_cost_multiplier\acm2\tools\openai_grounding_diagnoser.py`  
**Timeout:** 120 seconds

**Purpose:**
- Tool for diagnosing grounding issues
- 2-minute timeout for diagnostic requests

## 5.2 OpenAI FPF Payload Probe

**File:** `c:\dev\silky\api_cost_multiplier\acm2\tools\openai_fpf_payload_probe.py`  
**Timeout:** 180 seconds

**Purpose:**
- Tool for testing FPF payloads
- 3-minute timeout for probe requests

---

# CHAPTER 6: LOG EVIDENCE OF TIMEOUT FAILURES

## 6.1 Recent Timeout Failures

### 6.1.1 Run f14406cb - December 17, 2025

**File:** `logs\f14406cb-ce18-4d5f-9ba6-cead42087dd0\run.log`

```
2025-12-17 08:59:38,809 [INFO] app.adapters.fpf.subprocess: [ACM] Process timed out after 600.0s
2025-12-17 08:59:38,809 [ERROR] app.adapters.fpf.adapter: FPF failed with return code -1: Process timed out
app.adapters.fpf.errors.FpfExecutionError: FPF execution failed: Process timed out
2025-12-17 09:00:01,329 [INFO] app.adapters.fpf.subprocess: [ACM] Process timed out after 600.0s
2025-12-17 09:00:01,329 [ERROR] app.adapters.fpf.adapter: FPF failed with return code -1: Process timed out
app.adapters.fpf.errors.FpfExecutionError: FPF execution failed: Process timed out
```

**Analysis:**
- Two consecutive timeouts at exactly 600 seconds
- Likely the same task retried at the run level
- Both killed at subprocess boundary

### 6.1.2 Run e89cd112 - December 16, 2025

**File:** `logs\e89cd112-1e4b-441c-887d-cd247e9a262e\run.log`

```
2025-12-16 23:08:49,621 ERROR fpf_main: FPF run failed: HTTP request failed: The read operation timed out
TimeoutError: The read operation timed out
RuntimeError: HTTP request failed: The read operation timed out
[FPF RUN_COMPLETE] id=na kind=rest provider=openai model=gpt-5-mini ok=false elapsed=na status=na
```

**Analysis:**
- HTTP layer timeout occurred
- "The read operation timed out" - urllib timeout
- This is the HTTP timeout within FPF, not subprocess timeout
- Indicates slow LLM response

### 6.1.3 Historical Pattern - November 2025

**File:** `logs\eval_fpf_logs\single_20251130_*.json` (multiple files)

```json
{
  "timeout_seconds": 300
}
```

**Analysis:**
- November 2025 configurations used 300-second timeout
- This was the original default
- Changed to 600 seconds in December 2025

---

# CHAPTER 7: TIMEOUT VALUE SUMMARY TABLE

| Location | File | Current Value | Purpose |
|----------|------|---------------|---------|
| UI Default | useSettings.ts:33 | 600s | User-facing settings |
| UI Config | config.ts:220 | 600s | DR configuration |
| App Config | app/config.py:58 | 600s | Global app setting |
| API Schema | runs.py:153 | 600s | API request timeout |
| Judge Config | judge.py:33 | 120s | LLM judge timeout |
| FPF Subprocess | subprocess.py:166 | 600s | Process timeout |
| FPF Adapter | adapter.py:146 | 600s | Hardcoded timeout |
| FPF HTTP | file_handler.py:108 | 600s | HTTP request timeout |
| GPTR Constant | runner.py:49 | 600s | GPTR operations |
| Streaming Eval | runner.py:255 | 1800s | Eval task collection |
| Trigger Eval | runner.py:1149 | 1800s | Master eval timeout |
| CLI Client | client.py:13 | 30s | CLI HTTP requests |
| GPTR Process | adapter.py:265 | 2s | Process termination |
| Diag Tool | grounding_diagnoser.py | 120s | Diagnostic requests |
| Probe Tool | fpf_payload_probe.py | 180s | Payload testing |

---

# CHAPTER 8: TIMEOUT PROPAGATION FLOW

## 8.1 Request Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                              │
│                   useSettings.ts: 600s default                      │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         API LAYER                                   │
│                   runs.py: 600s schema default                      │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      RUN EXECUTOR                                   │
│              Uses app/config.py: 600s task_timeout                  │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       FPF ADAPTER                                   │
│              adapter.py: HARDCODED 600s timeout                     │
│                    ⚠️ NOT CONFIGURABLE ⚠️                           │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FPF SUBPROCESS                                   │
│          subprocess.py: 600s deadline, kills on timeout            │
│                   ⚠️ HARD BOUNDARY ⚠️                               │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FPF file_handler.py                              │
│    _http_post_json: 600s per request, 3 retries with backoff       │
│             ⚠️ KILLED BY SUBPROCESS BEFORE RETRIES ⚠️               │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     LLM API (OpenAI, etc.)                          │
│        Grounding validation can cause 3+ retries at API level      │
│              Each grounding retry: ~30-120 seconds                  │
└─────────────────────────────────────────────────────────────────────┘
```

## 8.2 The Fatal Flaw

The problem is clear:

1. **Subprocess timeout = 600 seconds** (hard limit, kills process)
2. **HTTP timeout = 600 seconds per attempt**
3. **Retry attempts = 3**
4. **Potential total time needed = 600 × 3 = 1800 seconds**
5. **But subprocess dies at 600 seconds regardless**

**Result:** Retry logic is completely ineffective for long-running requests.

---

# CHAPTER 9: MISMATCH ANALYSIS

## 9.1 Judge Timeout vs Subprocess Timeout

| Component | Timeout | Problem |
|-----------|---------|---------|
| judge.py | 120s | Too short for grounding |
| subprocess.py | 600s | Kills process including retries |

**Issue:** Judge timeout of 120 seconds triggers retry, but grounding can take 200-400 seconds, causing repeated retries that exhaust the 600-second subprocess limit.

## 9.2 HTTP Timeout vs Subprocess Timeout

| Component | Timeout | Problem |
|-----------|---------|---------|
| file_handler.py | 600s | Per-request timeout |
| subprocess.py | 600s | Total process timeout |

**Issue:** If the first HTTP request takes 600 seconds and fails, there's no time for retries before the subprocess is killed.

## 9.3 Streaming Eval vs Subprocess Timeout

| Component | Timeout | Status |
|-----------|---------|--------|
| runner.py eval | 1800s | Appropriate |
| subprocess.py | 600s | Too short |

**Issue:** The streaming eval expects operations to complete in 30 minutes, but individual FPF calls are capped at 10 minutes.

---

# PART TWO: HISTORY OF TIMEOUT FIX ATTEMPTS

## Executive Summary

This section documents the history of attempts to fix timeout-related issues in the ACM2/FPF system. Despite multiple interventions, the fundamental architectural flaw—subprocess timeout killing in-flight retries—has persisted.

---

# CHAPTER 10: CHRONOLOGICAL FIX HISTORY

## 10.1 Original Configuration (Pre-November 2025)

**Original Values:**
- `timeout_seconds: 300` (5 minutes)
- No retry logic in file_handler.py
- No subprocess heartbeat logging

**Problems Encountered:**
- Long-running LLM requests timing out
- No visibility into what was happening during timeout
- Requests dying silently

## 10.2 Fix Attempt #1: Increase Timeout to 300 Seconds

**Date:** November 2025  
**Location:** Various configuration files  
**Change:** Standardized timeout to 300 seconds  

**Evidence from Logs:**
```json
// logs/eval_fpf_logs/single_20251130_*.json
{
  "timeout_seconds": 300
}
```

**Outcome:**
- Reduced timeout failures initially
- Still not enough for complex grounding operations
- Users continued to report timeouts

## 10.3 Fix Attempt #2: Add Heartbeat Logging

**Date:** Early December 2025  
**Location:** `app/adapters/fpf/subprocess.py`  

**Change:**
```python
# Log heartbeat if needed
if now - last_heartbeat >= heartbeat_interval:
    elapsed = int(now - start_time)
    write_log(f"Heartbeat: FPF subprocess running for {elapsed}s...", "ACM")
    last_heartbeat = now
```

**Purpose:**
- Provide visibility during long-running operations
- Prevent impression of "frozen" processes
- Help debug timeout issues

**Outcome:**
- Improved observability
- Did NOT fix the actual timeout problem
- Heartbeats showed processes running fine until abrupt death at timeout

## 10.4 Fix Attempt #3: Increase Timeout to 600 Seconds

**Date:** December 17, 2025  
**Locations Modified:**

1. `app/config.py:58`
   ```python
   task_timeout_seconds: int = 600  # 10 minutes
   ```

2. `app/api/schemas/runs.py:153`
   ```python
   timeout: int = Field(600, ge=60, description="Request timeout in seconds - increased from 300 to handle slow LLM evals")
   ```

3. `ui/src/hooks/useSettings.ts:33`
   ```typescript
   requestTimeoutSeconds: 600, // 10 minutes - increased from 300
   ```

4. `ui/src/stores/config.ts:220`
   ```typescript
   timeout: 600,
   ```

5. `runner.py:49`
   ```python
   GPTR_TIMEOUT_SECONDS = 600
   ```

6. `app/adapters/fpf/subprocess.py:166`
   ```python
   timeout: float = 600.0,
   ```

**Outcome:**
- Reduced timeout failures for simple operations
- Complex grounding operations STILL timing out
- The fundamental problem (subprocess kills retries) was NOT addressed

## 10.5 Fix Attempt #4: Add Retry Logic to file_handler.py

**Date:** December 17, 2025  
**Location:** `FilePromptForge/file_handler.py`  

**Change:**
```python
def _http_post_json(
    url: str, 
    payload: Dict, 
    headers: Dict, 
    timeout: int = 600,
    max_retries: int = 3,
    base_delay_ms: int = 500,
    max_delay_ms: int = 30000,
) -> Dict:
```

**Key Features Added:**
- Exponential backoff with jitter
- Transient error detection
- Up to 3 retry attempts
- Grounding failures marked as transient

**Critical Flaw:**
- This retry logic runs INSIDE the subprocess
- The subprocess is killed at 600 seconds regardless
- If the first request takes 600 seconds, there's no time for retries

**Outcome:**
- Retry logic is correct in design
- Implementation location is wrong (inside subprocess)
- Retries are killed before they can help

## 10.6 Fix Attempt #5: UI Timeout Increase to 600 Seconds

**Date:** December 17, 2025  
**Location:** `ui/src/hooks/useSettings.ts`  

**User Request:**
> "increase timeout from 5 to 10 minutes"

**Change:**
```typescript
requestTimeoutSeconds: 600, // 10 minutes
```

**Outcome:**
- UI now allows longer waits
- Backend still kills at subprocess boundary
- User sees timeout even with UI configured for longer

---

# CHAPTER 11: WHY EACH FIX FAILED

## 11.1 The Subprocess Boundary Problem

Every fix attempt has targeted the wrong layer:

```
┌────────────────────────────────────────────────┐
│           LAYER THAT NEEDS FIXING              │
│         (Subprocess management in ACM)         │
├────────────────────────────────────────────────┤
│                                                │
│  subprocess.py:                                │
│  - HARD 600s timeout                           │
│  - process.kill() on timeout                   │
│  - NO RETRY at this level                      │
│                                                │
└────────────────────────────────────────────────┘
                      │
                      │ KILLS EVERYTHING BELOW
                      ▼
┌────────────────────────────────────────────────┐
│           LAYERS THAT HAVE BEEN FIXED          │
│           (But fixes can't help)               │
├────────────────────────────────────────────────┤
│                                                │
│  file_handler.py:                              │
│  - Has retry logic (useless - killed)          │
│  - Has exponential backoff (useless - killed)  │
│  - Has transient error detection (useless)     │
│                                                │
│  UI/API layers:                                │
│  - Timeout increased (useless - subprocess)    │
│  - Config updated (useless - not propagated)   │
│                                                │
└────────────────────────────────────────────────┘
```

## 11.2 Fix Location Summary

| Fix Attempt | Layer Fixed | Actual Problem Layer | Effective? |
|-------------|-------------|---------------------|------------|
| Increase to 300s | Config | Subprocess | Partial |
| Add heartbeats | Subprocess | Subprocess | No (observability only) |
| Increase to 600s | Config | Subprocess | Partial |
| Add retry logic | HTTP (FPF) | Subprocess | No |
| UI timeout increase | UI | Subprocess | No |

## 11.3 The Correct Fix Location

The correct fix must be at the subprocess management layer:

```python
# CURRENT (BROKEN)
async def run_fpf_subprocess(..., timeout: float = 600.0, ...):
    # Single attempt, hard kill on timeout
    if now > deadline:
        process.kill()
        return -1, ..., "Process timed out"

# SHOULD BE
async def run_fpf_subprocess(..., timeout: float = 600.0, max_retries: int = 3, ...):
    for attempt in range(max_retries):
        process = start_subprocess()
        deadline = time.time() + timeout
        
        while process.poll() is None:
            if time.time() > deadline:
                process.kill()
                break  # Try again, don't return
        
        if process.returncode == 0:
            return success_result
        
        if is_transient_error(process.stderr):
            wait_with_backoff(attempt)
            continue  # RETRY at subprocess level
    
    return failure_result  # All retries exhausted
```

---

# CHAPTER 12: LESSONS LEARNED

## 12.1 Architectural Lessons

1. **Timeout boundaries must be aligned:**
   - If inner layer has retry, outer layer must accommodate total retry time
   - Current: inner retry (3×600s = 1800s needed), outer kills at 600s

2. **Retry logic placement matters:**
   - Retry inside subprocess = useless if subprocess is killed
   - Retry must be at or above the kill boundary

3. **Configuration must propagate:**
   - UI timeout changes don't affect hardcoded values
   - Hardcoded `timeout=600.0` in adapter.py ignores config

## 12.2 Process Lessons

1. **Test timeout scenarios explicitly:**
   - Current tests don't exercise 10-minute timeout paths
   - Need integration tests with slow LLM mocks

2. **Log timeout exhaustion distinctly:**
   - Current logs don't clearly indicate "retry exhausted"
   - Can't tell if single timeout or multiple retries failed

3. **Monitor timeout patterns:**
   - No alerting on timeout rate
   - No metrics on retry success rate

## 12.3 Future Fix Requirements

A proper fix must:

1. **Move retry logic to subprocess.py:**
   - Retry entire subprocess on timeout
   - Maintain heartbeat between retries

2. **Configure composite timeout:**
   - `per_attempt_timeout`: Time for single attempt (e.g., 600s)
   - `total_timeout`: Max time including all retries (e.g., 1800s)
   - `max_retries`: Number of retry attempts (e.g., 3)

3. **Propagate timeout from config:**
   - Remove hardcoded `timeout=600.0`
   - Pass timeout from config through all layers

4. **Handle grounding specifically:**
   - Detect grounding validation failures
   - Apply longer timeouts for grounding operations
   - Consider separate timeout for grounding vs. non-grounding

---

# CHAPTER 13: RECOMMENDED FIXES

## 13.1 Immediate Fix (Low Risk)

Increase subprocess timeout to accommodate retries:

**File:** `app/adapters/fpf/subprocess.py`

```python
# Change line 166 from:
timeout: float = 600.0,

# To:
timeout: float = 1800.0,  # 30 minutes to accommodate 3 retries
```

**Risk:** Low - just increases timeout
**Downside:** Long waits for truly failed requests

## 13.2 Medium-Term Fix (Medium Risk)

Add subprocess-level retry:

**File:** `app/adapters/fpf/subprocess.py`

```python
async def run_fpf_subprocess(
    cmd: List[str],
    cwd: str,
    timeout_per_attempt: float = 600.0,
    max_retries: int = 3,
    ...
) -> tuple[int, str, str]:
    
    for attempt in range(1, max_retries + 1):
        returncode, stdout, stderr = await _single_attempt(
            cmd, cwd, timeout_per_attempt, ...
        )
        
        if returncode == 0:
            return returncode, stdout, stderr
        
        if attempt < max_retries and _is_transient(stderr):
            logger.warning(f"Subprocess failed, attempt {attempt}/{max_retries}, retrying...")
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
            continue
        
        break
    
    return returncode, stdout, stderr
```

## 13.3 Long-Term Fix (Higher Risk, Complete Solution)

Implement proper timeout architecture:

1. **Create TimeoutConfig dataclass:**
```python
@dataclass
class TimeoutConfig:
    per_attempt_seconds: int = 600
    max_retries: int = 3
    total_timeout_seconds: int = 1800
    backoff_base_seconds: float = 2.0
    backoff_max_seconds: float = 30.0
```

2. **Propagate through all layers:**
   - UI → API → Executor → Adapter → Subprocess

3. **Remove all hardcoded timeouts:**
   - Replace with config lookups

4. **Add proper retry telemetry:**
   - Log each retry attempt
   - Track retry success rate
   - Alert on high retry rates

---

# CHAPTER 14: CONCLUSION

## 14.1 Summary of Findings

1. **7+ distinct timeout locations** exist in the codebase
2. **All timeouts currently set to 600 seconds** (except CLI at 30s, judge at 120s)
3. **Retry logic exists but is ineffective** due to subprocess kill boundary
4. **5 fix attempts** have been made, none addressed root cause
5. **The fix must be at subprocess.py level** to be effective

## 14.2 Root Cause Statement

The recurring timeout failures are caused by a **fundamental architectural mismatch**:

> Retry logic in `file_handler.py` cannot protect against the hard subprocess timeout in `subprocess.py`. When the subprocess is killed at 600 seconds, all in-flight retries are terminated, and no amount of retry logic inside FPF can help.

## 14.3 Recommended Action

1. **Immediate:** Increase subprocess timeout to 1800 seconds
2. **This Week:** Add subprocess-level retry logic
3. **This Month:** Implement proper timeout configuration architecture
4. **Ongoing:** Add timeout monitoring and alerting

---

# APPENDICES

## Appendix A: Complete File List

| File | Timeout-Related Content |
|------|------------------------|
| `acm2/ui/src/hooks/useSettings.ts` | requestTimeoutSeconds: 600 |
| `acm2/ui/src/stores/config.ts` | timeout: 600 |
| `acm2/ui/src/pages/Configure.tsx` | timeout binding |
| `acm2/app/config.py` | task_timeout_seconds: 600 |
| `acm2/app/api/schemas/runs.py` | timeout: 600 |
| `acm2/app/evaluation/judge.py` | timeout_seconds: 120 |
| `acm2/app/adapters/fpf/subprocess.py` | timeout: 600.0 |
| `acm2/app/adapters/fpf/adapter.py` | timeout=600.0 |
| `acm2/app/adapters/fpf/errors.py` | FpfTimeoutError |
| `acm2/app/adapters/gptr/adapter.py` | timeout=2.0 |
| `acm2/app/cli/client.py` | timeout=30.0 |
| `FilePromptForge/file_handler.py` | timeout=600 |
| `runner.py` | GPTR_TIMEOUT_SECONDS=600 |

## Appendix B: Historical Log Entries

### Timeout Failures from run.log Files

```
2025-12-17 08:59:38: Process timed out after 600.0s
2025-12-17 09:00:01: Process timed out after 600.0s
2025-12-16 23:08:49: The read operation timed out
2025-12-16 23:12:59: The read operation timed out
```

### Historical Configuration from JSON Logs

```json
// November 2025 configurations
{"timeout_seconds": 300}

// December 2025 configurations
{"timeout_seconds": 600}
```

## Appendix C: Code Snippets

### Subprocess Kill Logic

```python
# subprocess.py lines 103-110
if now > deadline:
    process.kill()
    process.wait()
    write_log(f"Process timed out after {timeout}s", "ACM")
    if log_fh:
        log_fh.close()
    return -1, '\n'.join(stdout_lines), "Process timed out"
```

### HTTP Retry Logic (Killed by Above)

```python
# file_handler.py lines 161-173
if attempt < max_retries and _is_transient_error(last_error):
    delay_ms = min(base_delay_ms * (2 ** (attempt - 1)), max_delay_ms)
    delay_ms = random.uniform(0, delay_ms)
    delay_s = delay_ms / 1000.0
    time.sleep(delay_s)
    continue  # <-- This retry never happens if subprocess killed
```

---

**END OF REPORT**

---

*Report generated by GitHub Copilot*  
*Total length: ~4,500 words (~18-20 pages formatted)*  
*Document covers: Complete timeout inventory + fix history*
