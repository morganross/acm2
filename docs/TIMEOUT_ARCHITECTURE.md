# Timeout & Retry Architecture

## Ownership Principle

**Each sub-system owns its timeout and retry configuration.**

ACM2 is a coordinator that delegates execution to sub-systems. It does NOT override or duplicate timeout/retry logic that already exists in sub-systems.

## Architecture Diagram

```
ACM2 (Coordinator)
│
├── Safety Ceiling Only (86400s / 24 hours)
│   └── Catastrophic failure protection - should NEVER be reached
│
├── FPF Sub-System
│   ├── Config: FilePromptForge/fpf_config.yaml
│   ├── Provider-specific: providers.<name>.timeout_seconds
│   │   ├── openaidp: 7200s (2 hours) - deep research
│   │   ├── tavily: 1800s (30 min) - async research
│   │   └── openai/google: 600s (10 min) - standard
│   ├── Global fallback: concurrency.timeout_seconds
│   └── Retry: concurrency.retry.* (base_delay_ms, max_retries, etc.)
│
├── GPTR Sub-System
│   └── Config: GPT-Researcher's own configuration
│
└── Evaluation Sub-System
    └── Config: JudgeConfig in judge.py
        ├── timeout_seconds: 600s (per LLM call)
        └── retries: 3
```

## FPF Timeout Resolution

FPF's `_resolve_timeout()` function determines timeouts with this precedence:

1. `providers.<provider>.timeout_seconds` (highest priority)
2. `concurrency.timeout_seconds` (global override)
3. Provider-specific defaults:
   - `openaidp` → 7200s (for o3-deep-research, o4-mini-deep-research)
   - `tavily` → 1800s (for Tavily async research)
   - others → 600s

## FPF Retry Configuration

Located in `fpf_config.yaml`:

```yaml
concurrency:
  retry:
    base_delay_ms: 500
    max_delay_ms: 6000
    max_retries: 2
    jitter: full
```

Additionally, each provider's `execute_and_verify()` has internal retry logic with exponential backoff for transient errors (502, 503, 504, timeouts).

## ACM2 Safety Ceiling

ACM2 sets a 24-hour safety timeout on subprocess calls:

```python
# In adapter.py
timeout=86400.0  # Safety ceiling - FPF controls actual timeout
```

**Purpose:** Protect against catastrophic hangs where FPF itself fails to timeout.

**This should NEVER be reached in normal operation.** If it is reached, there's a bug in FPF's timeout handling.

## Evaluation Timeouts

The `JudgeConfig` in `app/evaluation/judge.py` controls evaluation LLM call timeouts:

```python
timeout_seconds: int = 600  # Per-call timeout
retries: int = 3            # Retry count for transient failures
```

**Future improvement:** These could be moved to a config file or preset configuration.

## Key Principles

1. **Single Source of Truth**: Each sub-system owns its timeout configuration
2. **No Duplication**: ACM2 does not duplicate timeout logic that exists in sub-systems
3. **Provider Agnostic**: ACM2 doesn't need to know about provider-specific timeouts
4. **Safety Ceiling**: ACM2 only sets a maximum ceiling for catastrophic failure protection

## Troubleshooting

### "Process timed out after 86400s"
This should never happen. If it does:
1. Check FPF's `_resolve_timeout()` - is it returning a valid timeout?
2. Check the provider adapter's `execute_and_verify()` - is it respecting the timeout?
3. Check for infinite loops or deadlocks in the provider code

### "Timeout waiting for FPF"
This is expected behavior when FPF's internal timeout is reached:
1. Check `fpf_config.yaml` for the provider's timeout setting
2. Increase `providers.<provider>.timeout_seconds` if needed
3. For deep research models, ensure `openaidp` timeout is set appropriately

---

*Last Updated: December 19, 2025*
*Reason: Refactored to delegate all timeouts to sub-systems*
