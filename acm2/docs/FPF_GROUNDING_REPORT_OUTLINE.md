# FPF Grounding & Threshold Investigation Report - Outline

## Executive Summary
- **Objective**: Investigate the existence, origin, and impact of the "grounding threshold" (allegedly 66%) in FilePromptForge.
- **Findings**: 
    - No explicit percentage-based threshold (e.g., `0.66`) exists in the FPF codebase (`grounding_enforcer.py`, `file_handler.py`, providers).
    - A **boolean** grounding check exists in `grounding_enforcer.py` (`detect_grounding`), which enforces the presence of citations/web search results.
    - The "40.00% >= 66.00%" log message likely originates from an external dependency (e.g., `gpt-researcher` internal scoring) or a specific provider response field (e.g., Gemini `confidenceScores`), but FPF itself does not enforce this specific number.
    - Grounding failures *are* occurring and triggering retries, causing timeouts.

## Part 1: The "Grounding Threshold" Investigation
### 1.1 The Myth of the 66%
- Analysis of `grounding_enforcer.py`:
    - Logic is boolean (`True`/`False`), not scalar.
    - Checks for: `tool_calls`, `citations`, `groundingMetadata` (Gemini), `web_search` strings.
    - No numerical comparison logic found.
- Analysis of Providers:
    - OpenAI, Google, Tavily adapters do not contain threshold logic.
- Hypothesis on the "40% >= 66%" Log:
    - Likely a `confidenceScore` returned by Gemini and logged by FPF, but not used for *enforcement* in FPF code (FPF only checks for *presence* of metadata).
    - Alternatively, a `gpt-researcher` internal metric (if used).

### 1.2 The Real Grounding Enforcer
- **Mechanism**: `grounding_enforcer.py` -> `detect_grounding()`
- **Enforcement**: `assert_grounding_and_reasoning()` raises `ValidationError` if `detect_grounding()` returns `False`.
- **Impact**: `file_handler.py` catches `ValidationError` (as a transient error) and retries.
- **The Loop**: 
    - Request -> Provider -> Response (No Grounding) -> `ValidationError` -> Retry -> ... -> Timeout.

## Part 2: System Architecture & Failure Points
### 2.1 The Retry Loop of Death
- **ACM2 Timeout**: 600s (Hard process kill).
- **FPF Retry Logic**: 3 retries with exponential backoff.
- **Conflict**: If grounding fails repeatedly (e.g., model refuses to search), FPF retries until ACM2 kills it.

### 2.2 Provider Specifics
- **Gemini**: Returns `groundingMetadata`. FPF checks for its *presence*.
- **OpenAI**: Returns `tool_calls`. FPF checks for `web_search` tool call.
- **Tavily**: Returns direct search results.

## Part 3: Recommendations & Fixes
### 3.1 Immediate Fixes
- **Disable Strict Enforcement**: Allow "soft" failures for grounding (log warning instead of error).
- **Increase Timeouts**: Align ACM2 timeout with FPF retry potential (e.g., 1200s).
- **Fix the Model**: Ensure the prompt *forces* the model to use the search tool (prompt engineering).

### 3.2 Long-Term Architectural Changes
- **Decouple Validation**: Move grounding check to a post-processing step that doesn't block the response.
- **Visibility**: Expose the actual grounding score (if available) to the user in the UI.

## Part 4: Comprehensive Code Audit (Appendix)
- Full listing of `grounding_enforcer.py`.
- Full listing of `file_handler.py` retry logic.
- Log analysis of failure cases.
