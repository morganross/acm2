# OpenRouter Provider Implementation Plan

## Overview

Add OpenRouter as a new provider to FilePromptForge (FPF). OpenRouter provides a unified API gateway to hundreds of AI models through a single endpoint, using an OpenAI-compatible API format.

---

## 1. OpenRouter API Summary

### Endpoint
```
https://openrouter.ai/api/v1/chat/completions
```

### Authentication
```python
headers = {
    "Authorization": "Bearer <OPENROUTER_API_KEY>",
    "HTTP-Referer": "<YOUR_SITE_URL>",  # Optional, for rankings
    "X-Title": "<YOUR_SITE_NAME>",       # Optional, for rankings
    "Content-Type": "application/json"
}
```

### Request Format (OpenAI-Compatible)
```python
{
    "model": "openai/gpt-4o",           # provider/model format
    "messages": [
        {"role": "system", "content": "..."},
        {"role": "user", "content": "..."}
    ],
    "max_tokens": 4096,                  # Optional
    "temperature": 1.0,                  # Optional, 0.0-2.0
    "top_p": 1.0,                        # Optional, 0.0-1.0
    "stream": false,                     # Optional
    "response_format": {"type": "json_object"},  # Optional, for JSON mode
    "stop": ["..."],                     # Optional
    "tools": [...],                      # Optional, for tool calling
}
```

### Response Format
```python
{
    "id": "gen-xxxxxxxxxxxxxx",
    "choices": [
        {
            "finish_reason": "stop",
            "message": {
                "role": "assistant",
                "content": "Hello there!"
            }
        }
    ],
    "usage": {
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150
    },
    "model": "openai/gpt-4o"
}
```

### Supported Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `temperature` | float | 1.0 | Range: 0.0-2.0 |
| `max_tokens` | int | - | Max output tokens |
| `top_p` | float | 1.0 | Range: 0.0-1.0 |
| `top_k` | int | 0 | Not for OpenAI models |
| `frequency_penalty` | float | 0.0 | Range: -2.0 to 2.0 |
| `presence_penalty` | float | 0.0 | Range: -2.0 to 2.0 |
| `repetition_penalty` | float | 1.0 | Range: 0.0-2.0 |
| `stop` | array | - | Stop sequences |
| `response_format` | object | - | JSON mode |

---

## 2. Implementation Tasks

### Task 1: Create Provider Directory Structure
```
acm2/FilePromptForge/providers/openrouter/
├── __init__.py
├── fpf_openrouter_main.py    # Main provider adapter
└── fpf_openrouter_config.yaml # Provider config (if needed)
```

### Task 2: Implement `fpf_openrouter_main.py`

Required functions (matching other providers):

```python
def build_payload(prompt: str, cfg: dict) -> Tuple[dict, Optional[dict]]:
    """
    Build OpenRouter API payload.
    
    Args:
        prompt: The composed prompt text
        cfg: Configuration dict containing model, temperature, max_tokens, etc.
    
    Returns:
        Tuple of (payload_body, optional_headers)
    """
    pass

def parse_response(raw: dict) -> str:
    """
    Extract the text content from OpenRouter response.
    
    Args:
        raw: The raw JSON response from OpenRouter API
    
    Returns:
        The assistant's response text
    """
    pass

def extract_reasoning(raw: dict) -> Optional[str]:
    """
    Extract reasoning/thinking content if present.
    
    Args:
        raw: The raw JSON response
    
    Returns:
        Reasoning text or None
    """
    pass

def validate_model(model_id: str) -> bool:
    """
    Validate if model is supported by OpenRouter.
    
    Args:
        model_id: The model identifier (e.g., "openai/gpt-4o")
    
    Returns:
        True if valid, False otherwise
    """
    pass
```

### Task 3: Update Provider Registry

**File:** `acm2/FilePromptForge/providers/__init__.py`
```python
__all__ = ["openai", "google", "openaidp", "anthropic", "openrouter"]
```

### Task 4: Add API Key Support

**File:** `acm2/FilePromptForge/.env` (template)
```
OPENROUTER_API_KEY=sk-or-v1-...
```

**File:** `acm2/FilePromptForge/file_handler.py`
- The existing `_read_key_from_env_file()` already handles `{PROVIDER}_API_KEY` pattern
- No changes needed - `OPENROUTER_API_KEY` will be auto-detected

### Task 5: Add Provider URL

**File:** Update default provider URLs or config
```python
provider_urls = {
    "openai": "https://api.openai.com/v1/responses",
    "google": "https://generativelanguage.googleapis.com/...",
    "anthropic": "https://api.anthropic.com/v1/messages",
    "openrouter": "https://openrouter.ai/api/v1/chat/completions"  # NEW
}
```

### Task 6: Add to ACM2 App Config

**File:** `acm2/acm2/app/config.py`
```python
class Settings(BaseSettings):
    # ... existing keys ...
    openrouter_api_key: Optional[str] = None  # NEW
```

### Task 7: Add to UI Settings Page

**File:** `acm2/acm2/ui/src/pages/Settings.tsx`
- Add input field for `OPENROUTER_API_KEY`
- Display alongside existing API key fields

### Task 8: Add Models to models.yaml

**File:** `acm2/acm2/app/models.yaml`
```yaml
openrouter:
  # OpenAI models via OpenRouter
  - id: openrouter:openai/gpt-4o
    name: GPT-4o (via OpenRouter)
    context_window: 128000
    max_output_tokens: 16384
  
  # Anthropic models via OpenRouter  
  - id: openrouter:anthropic/claude-3.5-sonnet
    name: Claude 3.5 Sonnet (via OpenRouter)
    context_window: 200000
    max_output_tokens: 8192
  
  # Meta models via OpenRouter
  - id: openrouter:meta-llama/llama-3.1-405b-instruct
    name: Llama 3.1 405B (via OpenRouter)
    context_window: 131072
    max_output_tokens: 4096
  
  # Mistral models via OpenRouter
  - id: openrouter:mistralai/mistral-large
    name: Mistral Large (via OpenRouter)
    context_window: 128000
    max_output_tokens: 8192
```

---

## 3. Provider Adapter Code Skeleton

```python
"""
OpenRouter provider adapter for FPF.

OpenRouter provides a unified API to hundreds of AI models through a single
OpenAI-compatible endpoint. This adapter handles:
- build_payload(prompt, cfg) -> (dict, dict|None)
- parse_response(raw) -> str
- extract_reasoning(raw) -> Optional[str]
- validate_model(model_id) -> bool
"""

from __future__ import annotations
from typing import Dict, Tuple, Optional, Any

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


def _normalize_model(model: str) -> str:
    """
    Normalize model string.
    Expected format: openrouter:provider/model or provider/model
    Returns: provider/model format for OpenRouter API
    """
    if not model:
        raise RuntimeError("OpenRouter provider requires 'model'")
    # Strip openrouter: prefix if present
    if model.startswith("openrouter:"):
        model = model[len("openrouter:"):]
    return model


def _translate_sampling(cfg: Dict) -> Dict:
    """Extract sampling parameters from config."""
    out: Dict[str, Any] = {}
    
    if cfg.get("max_output_tokens"):
        out["max_tokens"] = int(cfg["max_output_tokens"])
    elif cfg.get("max_tokens"):
        out["max_tokens"] = int(cfg["max_tokens"])
    
    if cfg.get("temperature") is not None:
        out["temperature"] = float(cfg["temperature"])
    
    if cfg.get("top_p") is not None:
        out["top_p"] = float(cfg["top_p"])
    
    return out


def build_payload(prompt: str, cfg: Dict) -> Tuple[Dict, Optional[Dict]]:
    """
    Build OpenRouter chat completions payload.
    
    Returns (payload, optional_provider_headers)
    """
    if "model" not in cfg or not cfg.get("model"):
        raise RuntimeError("OpenRouter provider requires 'model' in config")
    
    model = _normalize_model(cfg["model"])
    
    # Build messages array
    messages = []
    
    # System message if present
    system_prompt = cfg.get("system_prompt")
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    
    # User message with the composed prompt
    messages.append({"role": "user", "content": prompt})
    
    # Build payload
    payload = {
        "model": model,
        "messages": messages,
    }
    
    # Add sampling parameters
    sampling = _translate_sampling(cfg)
    payload.update(sampling)
    
    # Optional: JSON mode
    if cfg.get("json_mode"):
        payload["response_format"] = {"type": "json_object"}
    
    # Optional headers for OpenRouter rankings
    headers = {
        "HTTP-Referer": cfg.get("site_url", "https://github.com/acm2"),
        "X-Title": cfg.get("site_title", "ACM2 Content Evaluation"),
    }
    
    return payload, headers


def parse_response(raw: Dict) -> str:
    """Extract text content from OpenRouter response."""
    if not isinstance(raw, dict):
        raise RuntimeError(f"Expected dict response, got {type(raw)}")
    
    # Check for error
    if "error" in raw:
        err = raw["error"]
        msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        raise RuntimeError(f"OpenRouter API error: {msg}")
    
    # Extract from choices
    choices = raw.get("choices", [])
    if not choices:
        raise RuntimeError("No choices in OpenRouter response")
    
    first_choice = choices[0]
    
    # Handle streaming vs non-streaming
    if "message" in first_choice:
        content = first_choice["message"].get("content", "")
    elif "delta" in first_choice:
        content = first_choice["delta"].get("content", "")
    else:
        content = ""
    
    return content or ""


def extract_reasoning(raw: Dict) -> Optional[str]:
    """
    Extract reasoning/thinking content if model supports it.
    Some models via OpenRouter may include reasoning in tool calls
    or special response fields.
    """
    if not isinstance(raw, dict):
        return None
    
    # Check for reasoning in choices
    choices = raw.get("choices", [])
    if choices and "message" in choices[0]:
        msg = choices[0]["message"]
        # Some models put reasoning in a separate field
        if "reasoning" in msg:
            return msg["reasoning"]
        # Check tool calls for reasoning
        if "tool_calls" in msg:
            for tc in msg.get("tool_calls", []):
                if tc.get("type") == "reasoning":
                    return tc.get("reasoning", {}).get("content")
    
    return None


def validate_model(model_id: str) -> bool:
    """
    Validate model format. OpenRouter accepts provider/model format.
    We don't maintain a whitelist - OpenRouter handles model validation.
    """
    if not model_id:
        return False
    normalized = _normalize_model(model_id)
    # Must have provider/model format
    return "/" in normalized
```

---

## 4. Testing Plan

### Unit Tests
1. Test `build_payload()` with various config combinations
2. Test `parse_response()` with sample responses
3. Test `_normalize_model()` with different formats
4. Test error handling for malformed responses

### Integration Tests
1. Make actual API call to OpenRouter with test model
2. Verify response parsing
3. Test streaming (if implemented)
4. Test with different model providers (OpenAI, Anthropic, Meta via OpenRouter)

### Manual Testing
1. Add OpenRouter model to preset via GUI
2. Execute preset
3. Verify generation works
4. Check logs for proper API interaction

---

## 5. Configuration Notes

### Model Naming Convention
Models should be prefixed with `openrouter:` in the ACM2 database:
- `openrouter:openai/gpt-4o`
- `openrouter:anthropic/claude-3.5-sonnet`
- `openrouter:meta-llama/llama-3.1-405b-instruct`

The adapter strips the `openrouter:` prefix before sending to the API.

### Rate Limiting
OpenRouter has its own rate limits per model. Consider:
- Adding OpenRouter to the rate limiter in `acm2/app/services/rate_limiter.py`
- Starting with conservative limits (e.g., 5 concurrent requests)

### Cost Tracking
OpenRouter charges per token based on underlying model costs. 
The response includes usage data that can be used for cost tracking.

---

## 6. Implementation Order

1. **Create provider directory and files**
2. **Implement `fpf_openrouter_main.py`**
3. **Update `providers/__init__.py`**
4. **Test with direct API call**
5. **Add models to `models.yaml`**
6. **Add UI support for API key**
7. **End-to-end test with preset execution**

---

## 7. Advantages of OpenRouter

1. **Single API key** for hundreds of models
2. **Automatic fallbacks** if a model is unavailable
3. **Cost optimization** - OpenRouter finds cheapest available provider
4. **OpenAI-compatible** - minimal adapter changes needed
5. **Access to models not directly available** (Llama, Mistral, etc.)
