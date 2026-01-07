"""
OpenRouter provider adapter for FPF.

OpenRouter is a unified gateway to 600+ LLM models. Unlike other FPF providers,
grounding (web search) is NOT enforced for OpenRouter because:
- Most OpenRouter models don't support native web search tools
- Web search capability is model-specific (only Perplexity Sonar has built-in search)
- OpenRouter passes through unsupported parameters silently

This provider sets REQUIRES_GROUNDING = False to skip grounding validation.
Reasoning validation still applies where the model supports it.
"""

from __future__ import annotations
from typing import Dict, Tuple, Optional, Any, List
import sys
import json
import logging
import random
import time
import urllib.request
import urllib.error

LOG = logging.getLogger("fpf_openrouter_main")

# Provider-level flags: Skip grounding and reasoning enforcement for OpenRouter
# Most OpenRouter models don't support native web search or explicit reasoning tokens
REQUIRES_GROUNDING = False
REQUIRES_REASONING = False

# OpenRouter uses OpenAI-compatible API
DEFAULT_API_BASE = "https://openrouter.ai/api/v1/chat/completions"

# Allow all models - OpenRouter handles validation
ALLOWED_PREFIXES = tuple()  # No restrictions


def _normalize_model(model: str) -> str:
    """
    Normalize model ID. OpenRouter models use 'provider/model' format.
    Strip any 'openrouter:' prefix if present.
    """
    raw = model or ""
    if raw.startswith("openrouter:"):
        raw = raw[len("openrouter:"):]
    return raw


def _translate_sampling(cfg: Dict) -> Dict[str, Any]:
    """Translate FPF sampling parameters to OpenAI-compatible format."""
    out: Dict[str, Any] = {}

    if cfg.get("max_completion_tokens") is not None:
        out["max_tokens"] = int(cfg["max_completion_tokens"])
    elif cfg.get("max_tokens") is not None:
        out["max_tokens"] = int(cfg["max_tokens"])
    else:
        out["max_tokens"] = 4096  # Reasonable default

    if cfg.get("temperature") is not None:
        out["temperature"] = float(cfg["temperature"])
    if cfg.get("top_p") is not None:
        out["top_p"] = float(cfg["top_p"])

    return out


def build_payload(prompt: str, cfg: Dict) -> Tuple[Dict, Optional[Dict]]:
    """
    Build an OpenAI-compatible chat completions payload for OpenRouter.
    
    OpenRouter supports:
    - Standard chat completions format
    - Model-specific parameters passed through
    - Optional reasoning_effort for supported models (o1/o3/DeepSeek R1)
    """
    model_cfg = cfg.get("model")
    if not model_cfg:
        raise RuntimeError("OpenRouter provider requires 'model' in config")
    model_to_use = _normalize_model(model_cfg)

    request_json = bool(cfg.get("json")) if cfg.get("json") is not None else False
    if request_json:
        json_instr = (
            "Return only a single valid JSON object. Do not include prose or fences. "
            "Output must be strictly valid JSON."
        )
        final_prompt = f"{json_instr}\n\n{prompt}"
    else:
        final_prompt = prompt

    sampling = _translate_sampling(cfg)

    messages: List[Dict[str, Any]] = []
    
    # Add system prompt if provided
    if cfg.get("system"):
        messages.append({"role": "system", "content": cfg["system"]})
    
    messages.append({"role": "user", "content": final_prompt})

    payload: Dict[str, Any] = {
        "model": model_to_use,
        "messages": messages,
        **sampling,
    }

    # Optional: Add reasoning_effort for models that support it (o1, o3, DeepSeek R1)
    reasoning_cfg = cfg.get("reasoning") or cfg.get("thinking") or {}
    if isinstance(reasoning_cfg, dict):
        effort = reasoning_cfg.get("effort") or reasoning_cfg.get("reasoning_effort")
        if effort:
            payload["reasoning_effort"] = effort

    # Perplexity-specific parameters for Sonar models
    if "perplexity/" in model_to_use:
        # search_mode: 'web' (default), 'academic', or 'sec'
        payload["search_mode"] = cfg.get("search_mode", "web")
        
        # web_search_options for search context size
        web_search_opts = cfg.get("web_search_options") or {}
        if web_search_opts:
            payload["web_search_options"] = web_search_opts
        elif "sonar-deep-research" in model_to_use:
            # Default to high search context for deep research
            payload["web_search_options"] = {"search_context_size": "high"}
        
        # reasoning_effort specifically for sonar-deep-research
        if "sonar-deep-research" in model_to_use and not payload.get("reasoning_effort"):
            # Default to medium if not specified
            payload["reasoning_effort"] = cfg.get("reasoning_effort", "medium")
        
        # Search domain filtering
        if cfg.get("search_domain_filter"):
            payload["search_domain_filter"] = cfg["search_domain_filter"]
        
        # Search recency filtering (e.g., 'day', 'week', 'month')
        if cfg.get("search_recency_filter"):
            payload["search_recency_filter"] = cfg["search_recency_filter"]
        
        # Optional: return related questions
        if cfg.get("return_related_questions"):
            payload["return_related_questions"] = True

    # Optional: response_format for JSON mode
    if request_json:
        payload["response_format"] = {"type": "json_object"}

    # OpenRouter-specific headers (optional but recommended)
    headers: Dict[str, str] = {}
    
    # HTTP-Referer and X-Title for app identification (helps with rate limits)
    if cfg.get("http_referer"):
        headers["HTTP-Referer"] = cfg["http_referer"]
    if cfg.get("x_title"):
        headers["X-Title"] = cfg["x_title"]

    return payload, headers if headers else None


def _is_transient_error(exc: Exception) -> bool:
    """Check if an error is transient and worth retrying."""
    msg = str(exc).lower()
    transient = [
        "429",
        "rate limit",
        "timeout",
        "timed out",
        "502",
        "503",
        "504",
        "connection",
        "network",
        "temporarily unavailable",
        "service unavailable",
        "overloaded",
    ]
    return any(tok in msg for tok in transient)


def extract_reasoning(raw_json: Dict) -> Optional[str]:
    """
    Extract reasoning/thinking from OpenRouter response.
    
    For models that support reasoning (o1/o3, DeepSeek R1, Gemini with thinking),
    the reasoning may appear in different places depending on the underlying model.
    """
    if not isinstance(raw_json, dict):
        return None

    # Check for explicit reasoning fields (DeepSeek R1 style)
    if raw_json.get("reasoning"):
        return raw_json["reasoning"]
    if raw_json.get("thinking"):
        return raw_json["thinking"]

    # Check choices for reasoning content
    choices = raw_json.get("choices") or []
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        
        message = choice.get("message") or {}
        
        # Some models put reasoning in a separate field
        if message.get("reasoning"):
            return message["reasoning"]
        if message.get("thinking"):
            return message["thinking"]
        
        # Check for reasoning in content blocks (Claude-style via OpenRouter)
        content = message.get("content")
        if isinstance(content, list):
            reasoning_parts = []
            for block in content:
                if isinstance(block, dict):
                    btype = block.get("type")
                    if btype in ("thinking", "reasoning"):
                        text = block.get("text") or block.get("thinking") or block.get("content")
                        if isinstance(text, str) and text.strip():
                            reasoning_parts.append(text.strip())
            if reasoning_parts:
                return "\n\n".join(reasoning_parts)

    return None


def parse_response(raw_json: Dict) -> str:
    """
    Parse the OpenRouter response to extract the main text content.
    Uses OpenAI-compatible format.
    """
    if not isinstance(raw_json, dict):
        return str(raw_json)

    choices = raw_json.get("choices") or []
    if choices:
        first_choice = choices[0]
        if isinstance(first_choice, dict):
            message = first_choice.get("message") or {}
            content = message.get("content")
            
            # Handle string content
            if isinstance(content, str):
                return content.strip()
            
            # Handle content blocks (Claude-style)
            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text")
                        if isinstance(text, str):
                            text_parts.append(text.strip())
                if text_parts:
                    return "\n\n".join(text_parts)

    # Fallback: return JSON representation
    try:
        return json.dumps(raw_json, indent=2, ensure_ascii=False)
    except Exception:
        return str(raw_json)


def execute_and_verify(
    provider_url: str,
    payload: Dict,
    headers: Optional[Dict],
    verify_helpers,
    timeout: Optional[int] = None,
    max_retries: int = 3,
    retry_delay: float = 1.0,
) -> Dict:
    """
    Execute the OpenRouter request and run validation.
    
    Note: Grounding validation is skipped for OpenRouter (REQUIRES_GROUNDING = False).
    Reasoning validation may still apply.
    """
    data = json.dumps(payload).encode("utf-8")
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)

    base_delay_ms = retry_delay * 1000
    max_delay_ms = max(base_delay_ms * 4, 120000)
    last_error: Optional[Exception] = None

    for attempt in range(1, max_retries + 1):
        req = urllib.request.Request(provider_url, data=data, headers=hdrs, method="POST")
        try:
            LOG.debug("OpenRouter request attempt %d/%d to %s", attempt, max_retries, provider_url)
            if timeout is None:
                resp_ctx = urllib.request.urlopen(req)
            else:
                resp_ctx = urllib.request.urlopen(req, timeout=timeout)
            with resp_ctx as resp:
                raw = resp.read().decode("utf-8")
                raw_json = json.loads(raw)
                
                # Pass this module for provider-level flag checking
                provider_mod = sys.modules.get(__name__) or __import__(__name__)
                verify_helpers.assert_grounding_and_reasoning(raw_json, provider=provider_mod)
                return raw_json
                
        except urllib.error.HTTPError as he:
            try:
                msg = he.read().decode("utf-8", errors="ignore")
            except Exception:
                msg = ""
            last_error = RuntimeError(f"HTTP error {getattr(he, 'code', '?')}: {getattr(he, 'reason', '?')} - {msg}")

            if attempt < max_retries and _is_transient_error(last_error):
                delay_ms = min(base_delay_ms * (2 ** (attempt - 1)), max_delay_ms)
                delay_ms = random.uniform(0, delay_ms)
                time.sleep(delay_ms / 1000.0)
                continue
            raise last_error from he
        except Exception as e:
            last_error = RuntimeError(f"HTTP request failed: {e}")
            if attempt < max_retries and _is_transient_error(e):
                delay_ms = min(base_delay_ms * (2 ** (attempt - 1)), max_delay_ms)
                delay_ms = random.uniform(0, delay_ms)
                time.sleep(delay_ms / 1000.0)
                continue
            raise last_error from e

    if last_error:
        raise last_error
    raise RuntimeError("HTTP request failed after all retries")


def list_available_models(api_key: str, api_base: str = "https://openrouter.ai/api/v1") -> List[str]:
    """
    List available models from OpenRouter.
    
    OpenRouter provides a /models endpoint that returns all available models.
    """
    url = api_base.rstrip("/") + "/models"
    hdrs = {
        "Authorization": f"Bearer {api_key}",
    }
    req = urllib.request.Request(url, headers=hdrs, method="GET")
    with urllib.request.urlopen(req) as resp:
        raw = resp.read().decode("utf-8")
        data = json.loads(raw)
    
    models = []
    for m in data.get("data", []):
        if isinstance(m, dict) and m.get("id"):
            models.append(m["id"])
    return sorted(models)


if __name__ == "__main__":
    import argparse
    import os

    parser = argparse.ArgumentParser(description="OpenRouter provider utilities for FPF")
    parser.add_argument("--list-models", action="store_true", help="List available models using OPENROUTER_API_KEY")
    parser.add_argument("--api-base", default="https://openrouter.ai/api/v1", help="Override API base URL")

    args = parser.parse_args()

    if args.list_models:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise SystemExit("OPENROUTER_API_KEY not set in environment")
        try:
            models = list_available_models(api_key, api_base=args.api_base)
            print(json.dumps(models, indent=2))
        except Exception as exc:
            raise SystemExit(f"Failed to list models: {exc}")
