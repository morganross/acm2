# Analysis: Why Did One Generation Fail?

## 1. What Happened
- The run requested 2 models: `openai:gpt-5-mini` and `google:gemini-2.5-flash`
- Only `google:gemini-2.5-flash` succeeded (9.78s, generated document)
- `openai:gpt-5-mini` appears to have failed silently

## 2. Why Didn't Retry Logic Kick In?

**ACM2 does NOT have retry logic at the executor level:**
- Looking at `run_executor.py`, the `_generate_single()` method catches exceptions and logs them, but does NOT retry:
```python
except Exception as e:
    logger.error(f"Generation failed for {provider}:{model}: {e}")
    return None  # Just returns None, no retry
```

**FPF Adapter has retry logic, but only for specific errors:**
- The FPF adapter (`fpf_adapter.py`) has `max_retries=3` configured
- But this is passed to the FPF library, which handles retries internally
- If FPF returns an error, ACM2 doesn't retry at its level

## 3. Does FPF Retry?
- Yes, FPF has internal retry logic (configurable via `max_retries`)
- The preset shows `fpf_config.max_retries: 3`
- However, if FPF exhausts retries and still fails, ACM2 doesn't have a fallback

## 4. Internet Searching Instructions
Looking at the preset configuration:
- `fpf_config.enable_web_search: true` ✅
- `fpf_config.search_iterations: 3` ✅
- But there are **NO explicit instructions** in the `system_instructions` or `custom_instructions` fields to enforce web searching

The FPF config enables web search, but doesn't include instructions like:
> "You MUST use web search to find current information..."

## 5. What Instructions Were Included?
From the preset:
```json
"fpf_config": {
  "system_instructions": "",  // EMPTY!
  "custom_instructions": "",  // EMPTY!
  "enable_web_search": true,
  "search_iterations": 3
}
```

The instructions are **empty** - no explicit guidance was given to the model.

---

## Recommendations

### A. Add Retry Logic to ACM2 Executor
```python
# In run_executor.py
async def _generate_single(self, ..., max_retries=3):
    for attempt in range(max_retries):
        try:
            result = await adapter.generate(...)
            if result:
                return result
        except Exception as e:
            logger.warning(f"Attempt {attempt+1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
    return None
```

### B. Add Web Search Instructions to Preset
```json
"fpf_config": {
  "system_instructions": "You are a research assistant. You MUST use web search to gather current, factual information before writing your response.",
  "enable_web_search": true
}
```

### C. Log Failed Generations More Explicitly
Currently failures are silent. We should:
1. Track failed generations in `generation_events`
2. Show them in the UI with error messages
3. Store error details in the database

---

*Generated: December 14, 2025*
