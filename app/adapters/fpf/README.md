# FPF (FilePromptForge) Adapter

This adapter integrates FilePromptForge into ACM2, enabling document-based research generation with web search and reasoning capabilities.

## Overview

The FPF adapter wraps the FilePromptForge CLI tool to provide:
- Standardized interface matching other generators (GPTR, etc.)
- Automatic model mapping for provider whitelists
- Cost tracking and token counting
- Progress callbacks for UI updates
- Cancellation support

## Configuration

### FPF-Specific Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `reasoning_effort` | string | `"medium"` | Reasoning intensity: `"low"`, `"medium"`, `"high"` |
| `max_completion_tokens` | int | `50000` | Maximum tokens for completion |
| `document_content` | string | `None` | Document content for FPF's file_a input |

### Model Mapping

The adapter automatically maps common model names to FPF-whitelisted equivalents:

| Requested Model | Mapped To |
|-----------------|-----------|
| `gpt-4o` | `o3` |
| `gpt-4o-mini` | `o3-mini` |
| `gpt-4-turbo` | `o3` |
| `gpt-4` | `o3` |
| `gpt-3.5-turbo` | `o3-mini` |

This mapping is defined in `FPF_MODEL_MAP` in `adapter.py` and can be extended as needed.

## Usage

### Via API

```python
import requests

response = requests.post(
    "http://localhost:8001/api/v1/generation/generate",
    json={
        "query": "Research question here",
        "generator": "fpf",
        "provider": "openai",
        "model": "gpt-4o",  # Will be mapped to o3
        "document_content": "Source document content",
        "reasoning_effort": "medium",
        "max_completion_tokens": 10000,
    }
)

task_id = response.json()["task_id"]

# Poll for completion
status = requests.get(f"http://localhost:8001/api/v1/generation/status/{task_id}")
```

### Via Adapter Directly

```python
from app.adapters import FpfAdapter, GenerationConfig

adapter = FpfAdapter()

config = GenerationConfig(
    provider="openai",
    model="gpt-4o",
    extra={
        "reasoning_effort": "high",
        "max_completion_tokens": 32000,
    }
)

result = await adapter.generate(
    query="Your research question",
    config=config,
    document_content="Optional source document",
)

print(result.content)
print(f"Cost: ${result.cost_usd:.4f}")
```

## Requirements

### FilePromptForge Setup

The FPF adapter expects FilePromptForge to be located at:
```
api_cost_multiplier/FilePromptForge/
```

Required files:
- `fpf_main.py` - Main entry point
- `.env` - Environment configuration with API keys

### Environment Variables

FilePromptForge's `.env` should contain:
```env
OPENAI_API_KEY=sk-...
# Other provider keys as needed
```

## Health Check

The adapter provides a health check that verifies:
1. FilePromptForge directory exists
2. `fpf_main.py` is present
3. `.env` file is configured

```python
adapter = FpfAdapter()
is_healthy = await adapter.health_check()
```

## Error Handling

The adapter handles common errors:

| Error | Cause | Resolution |
|-------|-------|------------|
| `FpfExecutionError` | FPF CLI failed | Check FPF logs, verify API keys |
| `FpfTimeoutError` | Execution timeout | Increase timeout or reduce complexity |
| `FpfConfigError` | Invalid configuration | Check config options |

## Testing

Run unit tests:
```bash
cd acm2
python -m pytest tests/unit/adapters/fpf/ -v
```

Run integration test (requires running server):
```bash
python test_fpf_standalone.py
```

## Architecture

```
app/adapters/fpf/
├── __init__.py      # Package exports
├── adapter.py       # Main FpfAdapter implementation
├── config.py        # FpfConfig dataclass
├── errors.py        # Custom exceptions
├── result.py        # FpfExecutionResult dataclass
└── subprocess.py    # Subprocess execution utilities
```

## Extending Model Mappings

To add new model mappings, edit `FPF_MODEL_MAP` in `adapter.py`:

```python
FPF_MODEL_MAP: dict[str, str] = {
    "gpt-4o": "o3",
    "your-model": "mapped-model",
    # Add more mappings here
}
```
