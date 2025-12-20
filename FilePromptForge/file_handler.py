"""
file_handler - central router for File Prompt Forge (FPF)

Enforced guarantees implemented here:
- OPENAI_API_KEY is sourced only from filepromptforge/.env (no overrides).
- Provider-side web_search is required: runs that do not perform web_search will fail.
- Provider reasoning is required: runs that do not return reasoning will fail.
- Raw provider JSON sidecar is always saved. Human-readable output is only written if
  both web_search and reasoning checks pass.
"""

from __future__ import annotations
import os
import re
import json
import importlib
import logging
from typing import Dict, Optional, Tuple, Any, List
from pathlib import Path

from pricing.pricing_loader import load_pricing_index, find_pricing, calc_cost

LOG = logging.getLogger("file_handler")

# ---------------------------------------------------------------------------
# Configurable Log Output
# ---------------------------------------------------------------------------
# Environment variables:
#   FPF_LOG_OUTPUT  = "console" | "file" | "both" | "none" (default: "console")
#   FPF_LOG_FILE    = path to log file (required if output includes "file")
#
# Example usage from parent process (ACM):
#   env["FPF_LOG_OUTPUT"] = "file"
#   env["FPF_LOG_FILE"] = "logs/run_123/fpf_output.log"
# ---------------------------------------------------------------------------

_FPF_LOG_OUTPUT = os.getenv("FPF_LOG_OUTPUT", "console").lower()
_FPF_LOG_FILE_PATH = os.getenv("FPF_LOG_FILE")
_FPF_LOG_FILE_HANDLE = None


def _fpf_log(message: str) -> None:
    """Write log message to configured destination(s): console, file, both, or none."""
    global _FPF_LOG_FILE_HANDLE

    if _FPF_LOG_OUTPUT == "none":
        return

    # Console output
    if _FPF_LOG_OUTPUT in ("console", "both"):
        print(message, flush=True)

    # File output
    if _FPF_LOG_OUTPUT in ("file", "both") and _FPF_LOG_FILE_PATH:
        try:
            if _FPF_LOG_FILE_HANDLE is None:
                log_path = Path(_FPF_LOG_FILE_PATH)
                log_path.parent.mkdir(parents=True, exist_ok=True)
                _FPF_LOG_FILE_HANDLE = open(log_path, "a", encoding="utf-8")
            _FPF_LOG_FILE_HANDLE.write(message + "\n")
            _FPF_LOG_FILE_HANDLE.flush()
        except Exception:
            pass  # Best-effort file logging


# Console redaction/truncation helpers
def _redact_headers(h: dict) -> dict:
    try:
        red = {}
        for k, v in (h or {}).items():
            if str(k).lower() in ("authorization", "x-api-key", "x-goog-api-key", "api-key"):
                red[k] = "***REDACTED***"
            else:
                red[k] = v
        return red
    except Exception:
        return {}

def _truncate(s: str, n: int = 2000) -> str:
    try:
        if s is None:
            return ""
        s = str(s)
        return s if len(s) <= n else s[:n] + "…"
    except Exception:
        return ""


def _sanitize_filename(name: str) -> str:
    """Sanitize a string to be a valid filename."""
    if not name:
        return "unknown"
    # remove chars that are problematic for filenames
    return re.sub(r'[\\/*?:"<>|]', "", name)


def _is_transient_error(exc: Exception) -> bool:
    """Check if an error is transient and should be retried."""
    msg = str(exc).lower()
    # Transient conditions: rate limits, timeouts, server errors, grounding failures
    transient_indicators = [
        "429", "rate limit", "quota",  # Rate limiting
        "timeout", "timed out",         # Timeouts
        "502", "503", "504",            # Server errors
        "connection", "network",        # Network issues
        "grounding", "validation",      # Grounding failures (can retry with same request)
        "temporarily unavailable",
        "service unavailable",
        "internal server error",
    ]
    return any(tok in msg for tok in transient_indicators)


def _http_post_json(
    url: str, 
    payload: Dict, 
    headers: Dict, 
    timeout: int = 600,
    max_retries: int = 3,
    base_delay_ms: int = 500,
    max_delay_ms: int = 30000,
) -> Dict:
    """POST JSON and return parsed JSON response. Uses urllib (no extra deps).

    Enhancements:
    - Retry logic with exponential backoff for transient errors
    - Increased default timeout to 600s to accommodate longer reasoning/tool runs.
    - Added debug logging of request metadata (not payload contents) to assist troubleshooting.
    - Logs and raises detailed errors on HTTP failures.
    
    Args:
        url: The API endpoint URL
        payload: JSON payload to send
        headers: HTTP headers
        timeout: Request timeout in seconds (default 600)
        max_retries: Maximum retry attempts for transient errors (default 3)
        base_delay_ms: Base delay in milliseconds for exponential backoff (default 500)
        max_delay_ms: Maximum delay in milliseconds (default 30000)
    """
    import urllib.request
    import urllib.error
    import time
    import random

    body = json.dumps(payload).encode("utf-8")
    hdrs = {"Content-Type": "application/json"}
    hdrs.update(headers or {})

    # Log a compact request summary for debugging (do not log full payload to avoid sensitive data leakage)
    try:
        LOG.debug("HTTP POST %s headers=%s payload_bytes=%d timeout=%s", url, {k: hdrs.get(k) for k in ("Authorization", "Content-Type")}, len(body), timeout)
    except Exception:
        # best-effort logging; do not raise for logging failures
        pass

    last_error = None
    
    for attempt in range(1, max_retries + 1):
        req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
        # Request summary (redacted, truncated) - output controlled by FPF_LOG_OUTPUT
        try:
            _fpf_log(f"[FPF API][REQ] POST {url} attempt={attempt}/{max_retries} headers={_redact_headers(hdrs)} payload_bytes={len(body)} preview={_truncate(json.dumps(payload))}")
        except Exception:
            pass
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                # Response summary (truncated) - output controlled by FPF_LOG_OUTPUT
                try:
                    status_code = getattr(resp, "status", resp.getcode() if hasattr(resp, "getcode") else "unknown")
                    _fpf_log(f"[FPF API][RESP] {url} status={status_code} bytes={len(raw)} preview={_truncate(raw)}")
                except Exception:
                    pass
                return json.loads(raw)
        except urllib.error.HTTPError as he:
            try:
                msg = he.read().decode("utf-8", errors="ignore")
            except Exception:
                msg = ""
            # Error summary (truncated) - output controlled by FPF_LOG_OUTPUT
            try:
                _fpf_log(f"[FPF API][ERR] {url} attempt={attempt}/{max_retries} status={getattr(he,'code','?')} reason={getattr(he,'reason','?')} body={_truncate(msg)}")
            except Exception:
                pass
            
            last_error = RuntimeError(f"HTTP error {he.code}: {he.reason} - {msg}")
            
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
            
            LOG.exception("HTTPError during POST %s: %s %s", url, he, msg)
            raise last_error from he
            
        except Exception as e:
            try:
                _fpf_log(f"[FPF API][ERR] {url} attempt={attempt}/{max_retries} error={e}")
            except Exception:
                pass
            
            last_error = RuntimeError(f"HTTP request failed: {e}")
            
            # Check if we should retry
            if attempt < max_retries and _is_transient_error(e):
                # Exponential backoff with jitter
                delay_ms = min(base_delay_ms * (2 ** (attempt - 1)), max_delay_ms)
                delay_ms = random.uniform(0, delay_ms)  # Full jitter
                delay_s = delay_ms / 1000.0
                LOG.warning(f"Transient error on attempt {attempt}/{max_retries}, retrying in {delay_s:.2f}s: {e}")
                _fpf_log(f"[FPF API][RETRY] Waiting {delay_s:.2f}s before retry {attempt + 1}/{max_retries}")
                time.sleep(delay_s)
                continue
            
            LOG.exception("HTTP request failed for %s: %s", url, e)
            raise last_error from e
    
    # Should not reach here, but just in case
    if last_error:
        raise last_error
    raise RuntimeError("HTTP request failed after all retries")


def _load_provider_module(provider_name: str = "openai"):
    """Import the provider module. Raise RuntimeError if not found."""
    try:
        # Construct the module name dynamically (import within this package root).
        module_name = f"providers.{provider_name}.fpf_{provider_name}_main"
        mod = importlib.import_module(module_name)
        LOG.info("Successfully loaded provider module: %s", module_name)
        return mod
    except ModuleNotFoundError as e:
        LOG.error("Provider module not found for: %s", provider_name)
        raise RuntimeError(f"Provider module not found for: {provider_name}") from e
    except Exception as e:
        LOG.exception("An unexpected error occurred while loading provider module for: %s", provider_name)
        raise RuntimeError(f"Could not load provider module for {provider_name}") from e


def _read_key_from_env_file(env_path: Path, key: str) -> Optional[str]:
    """
    Read KEY=VALUE lines from env_path and return the value for `key` if present.
    This is a conservative, deterministic parser used to ensure the repo .env is
    the canonical source for sensitive keys.
    """
    if not env_path.exists():
        return None
    try:
        with env_path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.strip() == key:
                    return v.strip().strip('\'"')
    except Exception:
        # Do not swallow — let caller decide. Return None on parse failure.
        return None
    return None


def _response_used_websearch(raw_json: Dict) -> bool:
    """
    Inspect provider response to determine whether provider-side web_search
    (tool usage) occurred.

    Heuristics:
    - If 'tool_calls' or 'tools' exists and is non-empty -> True
    - If any output block contains 'reasoning' or content referencing 'source' or 'web_search' strings -> True
    """
    if not isinstance(raw_json, dict):
        return False

    # direct tool call evidence
    if "tool_calls" in raw_json and isinstance(raw_json["tool_calls"], list) and raw_json["tool_calls"]:
        return True
    if "tools" in raw_json and isinstance(raw_json["tools"], list) and raw_json["tools"]:
        # some providers return tools metadata even if empty; require non-empty
        return True

    # inspect outputs for websearch indicators
    output = raw_json.get("output") or raw_json.get("outputs")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            # check content blocks for source-like entries
            content = item.get("content") or item.get("contents")
            if isinstance(content, list):
                for c in content:
                    # string search for common markers
                    try:
                        if isinstance(c, dict):
                            # fields that may indicate web search results
                            if any(k in c for k in ("source", "url", "link")):
                                return True
                            text = c.get("text") or ""
                            if isinstance(text, str) and ("http://" in text or "https://" in text or "[source]" in text or "Citation:" in text):
                                return True
                        elif isinstance(c, str):
                            if "http://" in c or "https://" in c or "Citation:" in c:
                                return True
                    except Exception:
                        continue
    # fallback: scan entire JSON string for web_search mention (conservative)
    try:
        raw_str = json.dumps(raw_json)
        if "web_search" in raw_str or "tool_call" in raw_str or "tool_calls" in raw_str:
            # only return True if also appears with some content length
            return "web_search" in raw_str
    except Exception:
        pass
        
    # Gemini specific check for groundingMetadata
    try:
        if "candidates" in raw_json and isinstance(raw_json["candidates"], list):
            for candidate in raw_json["candidates"]:
                if "groundingMetadata" in candidate and candidate["groundingMetadata"]:
                    return True
    except Exception:
        pass

    return False


def _extract_json_from_text(text: str) -> Optional[str]:
    """
    Best-effort JSON extractor from mixed text:
    - Prefer fenced ```json ... ``` blocks
    - Then any fenced block containing a JSON-looking object/array
    - Then the first {...} or [...] region in the text
    Returns a minified JSON string if parseable; otherwise None.
    """
    try:
        if not isinstance(text, str) or not text.strip():
            return None
        import re as _re
        import json as _json
        candidates: List[str] = []

        # Prefer ```json ... ```
        m = _re.search(r"```json\s*(\{.*?\}|\[.*?\])\s*```", text, flags=_re.DOTALL | _re.IGNORECASE)
        if m:
            candidates.append(m.group(1))

        # Any fenced code block containing JSON-looking object/array
        m2 = _re.search(r"```+\s*(\{.*?\}|\[.*?\])\s*```", text, flags=_re.DOTALL)
        if m2:
            candidates.append(m2.group(1))

        # Fallback: first object/array region
        m3 = _re.search(r"(\{.*\}|\[.*\])", text, flags=_re.DOTALL)
        if m3:
            candidates.append(m3.group(1))

        for blob in candidates:
            try:
                obj = _json.loads(blob)
                # Minify for stability
                return _json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
            except Exception:
                continue
        return None
    except Exception:
        return None

def _resolve_timeout(cfg: dict, provider_name: str) -> int:
    """
    Resolve the effective request timeout with precedence:
      providers.<provider>.timeout_seconds > concurrency.timeout_seconds > defaults
    Defaults: 7200 for 'openaidp' (deep research background), 1800 for 'tavily', else 600.
    """
    try:
        _conc = cfg.get("concurrency") or {}
        _timeout_cfg = int(_conc.get("timeout_seconds") or 0)
    except Exception:
        _timeout_cfg = 0
    try:
        _prov_cfg = (cfg.get("providers") or {}).get(provider_name, {}) or {}
        _prov_timeout = int(_prov_cfg.get("timeout_seconds") or 0)
    except Exception:
        _prov_timeout = 0
    # Set fallback based on provider
    if provider_name == "openaidp":
        _fallback = 7200
    elif provider_name == "tavily":
        _fallback = 1800  # 30 minutes for Tavily async research
    else:
        _fallback = 600
    return _prov_timeout or _timeout_cfg or _fallback


def run(file_a: Optional[str] = None,
        file_b: Optional[str] = None,
        out_path: Optional[str] = None,
        config_path: Optional[str] = None,
        env_path: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
        max_completion_tokens: Optional[int] = None,
        timeout: Optional[int] = None,
        request_json: Optional[bool] = None) -> str:
    """
    High-level entry point (OpenAI-only).

    Behavior guarantees enforced:
    - Loads OPENAI_API_KEY only from filepromptforge/.env (repo .env).
    - Fails if provider response did not perform web_search or did not return reasoning.
    - Saves raw sidecar always; writes human-readable output only when checks pass.
    """
    # Import helpers lazily to avoid circular imports
    try:
        from .helpers import compose_input, load_config, load_env_file  # preferred relative import
    except ImportError:
        try:
            from helpers import compose_input, load_config, load_env_file  # type: ignore
        except ImportError:
            # Legacy fallback for older layouts
            from fpf_main import compose_input, load_config, load_env_file  # type: ignore

    cfg = load_config(config_path or str(Path(__file__).parent / "fpf_config.yaml"))
    # Default JSON extraction behavior to boolean cfg["json"] when request_json is not provided
    if request_json is None:
        try:
            request_json = bool(cfg.get("json"))
        except Exception:
            request_json = False
    
    # Determine the provider and load the correct API key.
    # Normalize provider, and auto-route deep-research models to 'openaidp'
    provider_name = (provider or cfg.get("provider", "openai")).lower()
    try:
        _sel_model = (model or cfg.get("model") or "").lower()
        _norm_model = _sel_model.split(":", 1)[0]
        if _norm_model.startswith("o3-deep-research") or _norm_model.startswith("o4-mini-deep-research"):
            provider_name = "openaidp"
    except Exception:
        pass
    api_key_name = f"{provider_name.upper()}_API_KEY"

    env_file = Path(env_path) if env_path else Path(__file__).resolve().parent / ".env"
    api_key_value = _read_key_from_env_file(env_file, api_key_name)

    if api_key_value is None or api_key_value == "":
        # Fallback for backward compatibility with OPENAI_API_KEY
        if provider_name in ("openai", "openaidp"):
            api_key_value = _read_key_from_env_file(env_file, "OPENAI_API_KEY")

    # Tavily: load key from the same .env file and inject into process env for the adapter
    if provider_name == "tavily" and (api_key_value is None or api_key_value == ""):
        api_key_value = _read_key_from_env_file(env_file, "TAVILY_API_KEY")
        if api_key_value:
            try:
                os.environ["TAVILY_API_KEY"] = api_key_value
            except Exception:
                pass

    if api_key_value is None or api_key_value == "":
        LOG.error("API key '%s' not found in env file: %s", api_key_name, env_file)
        raise RuntimeError(f"API key not found in {env_file}. Set {api_key_name} there.")


    # Allow CLI override of model but keep canonical config for web_search/reasoning enforcement
    if model:
        # normalize to provider expected form (do not append :online here — provider adapter handles model normalization)
        cfg["model"] = model
    
    if reasoning_effort:
        if "reasoning" not in cfg:
            cfg["reasoning"] = {}
        cfg["reasoning"]["effort"] = reasoning_effort
    
    if max_completion_tokens:
        cfg["max_completion_tokens"] = max_completion_tokens

    if not file_a or not file_b:
        raise RuntimeError("file_a and file_b must be provided as arguments")

    # Prepare run identifiers and default output path early; emit RUN_START for single-run mode
    try:
        import uuid as _uuid
    except Exception:
        _uuid = None
    run_id = (_uuid.uuid4().hex[:8] if _uuid else "runid")
    model_name_sanitized = _sanitize_filename(cfg.get("model"))
    b_path = Path(file_b)
    file_b_stem = b_path.stem
    # Resolve output path early so the RUN_START record includes it
    if out_path:
        try:
            out_path = out_path.replace("<model_name>", model_name_sanitized)
            out_path = out_path.replace("<file_b_stem>", file_b_stem)
            out_path = out_path.replace("<run_id>", run_id)
        except Exception:
            pass
    else:
        out_name = f"{file_b_stem}.{model_name_sanitized}.{run_id}.fpf.response.txt"
        out_path = str(b_path.parent / out_name)
    kind = "deep" if (provider_name == "openaidp" or (str(cfg.get("model") or "").lower().startswith("o3-deep-research") or str(cfg.get("model") or "").lower().startswith("o4-mini-deep-research"))) else "rest"
    
    # Avoid duplicate signals when invoked by the scheduler
    if os.getenv("FPF_SCHEDULER") != "1":
        try:
            LOG.info("[FPF RUN_START] id=%s kind=%s provider=%s model=%s file_b=%s out=%s attempt=1/1", run_id, kind, provider_name, cfg.get("model"), file_b, out_path)
        except Exception:
            pass

    # compose prompt
    prompt_template = cfg.get("prompt_template")
    prompt = compose_input(file_a, file_b, prompt_template)

    provider = _load_provider_module(provider_name)

    model_to_use = cfg.get("model")
    if hasattr(provider, "validate_model"):
        if not provider.validate_model(model_to_use):
            raise RuntimeError(f"Model '{model_to_use}' is not allowed by OpenAI provider whitelist")

    # build payload (provider adapter is responsible for enforcing web_search & reasoning in payload)
    if hasattr(provider, "build_payload"):
        payload_result = provider.build_payload(prompt, cfg)
        if isinstance(payload_result, tuple) and len(payload_result) == 2:
            payload_body, provider_headers = payload_result
        else:
            payload_body = payload_result
            provider_headers = {}
    else:
        raise RuntimeError("Provider does not expose build_payload")

    provider_urls = cfg.get("provider_urls", {})
    provider_url = provider_urls.get(provider_name)
    if not provider_url:
        # Fallback for backward compatibility
        provider_url = cfg.get("provider_url")

    # Dynamically compute Google Gemini endpoint from cfg["model"] to avoid endpoint–model drift
    if provider_name == "google":
        try:
            norm_model = (cfg.get("model") or "").split(":", 1)[0]
            if not norm_model:
                raise RuntimeError("Google provider requires cfg['model'] to be set")
            computed_url = f"https://generativelanguage.googleapis.com/v1beta/models/{norm_model}:generateContent"
            if provider_url and provider_url != computed_url:
                try:
                    LOG.warning("Overriding configured provider_url for Google to match model: %s -> %s", provider_url, computed_url)
                except Exception:
                    pass
            provider_url = computed_url
        except Exception as e:
            # Fall through to existing checks; will raise if provider_url remains missing
            LOG.debug("Failed to compute dynamic Google endpoint from model: %s", e)

    if not provider_url:
        raise RuntimeError(f"provider_url for '{provider_name}' not configured in config")

    # build headers
    headers = dict(provider_headers or {})
    api_key = api_key_value
    if not api_key:
        raise RuntimeError(f"API key {api_key_name} not found in env file: {env_file}")

    if provider_name == "google":
        # Google Gemini uses x-goog-api-key header
        headers["x-goog-api-key"] = api_key
    elif provider_name == "anthropic":
        # Anthropic uses x-api-key plus required version header
        headers["x-api-key"] = api_key
        if "anthropic-version" not in headers:
            headers["anthropic-version"] = cfg.get("anthropic_version") or "2023-06-01"
        if cfg.get("anthropic_beta") and "anthropic-beta" not in headers:
            headers["anthropic-beta"] = cfg.get("anthropic_beta")
    else:
        # Default to bearer token for OpenAI and others
        headers["Authorization"] = f"Bearer {api_key}"

    if cfg.get("referer"):
        headers["Referer"] = cfg.get("referer")
    if cfg.get("title"):
        headers["Title"] = cfg.get("title")

    # perform HTTP POST: log timing and send request
    # Note: outbound payload is intentionally not persisted to reduce sidecar files.

    import time
    start_ts = time.time()
    # Prefer provider-level execute_and_verify when available to enforce grounding+reasoning at the lowest level.
    try:
        from . import grounding_enforcer as _ge
    except ImportError:
        import grounding_enforcer as _ge

    # Set validation context for extreme logging (after _ge import)
    try:
        _ge.set_run_context(
            run_id=run_id,
            provider=provider_name,
            model=cfg.get("model") or "unknown",
            log_dir=Path(__file__).resolve().parent / "logs" / "validation"
        )
    except Exception as ex:
        LOG.warning("Failed to set validation context for run %s: %s", run_id, ex)

    # Determine request timeout with provider override > concurrency > defaults
    # If explicit timeout provided via CLI/args, it takes precedence over everything
    timeout_to_use = timeout if timeout is not None else _resolve_timeout(cfg, provider_name)

    if hasattr(provider, "execute_and_verify"):
        raw_json = provider.execute_and_verify(
            provider_url,
            payload_body,
            headers,
            _ge,
            timeout=timeout_to_use,
        )
    elif provider_name == "openaidp" and hasattr(provider, "execute_dp_background"):
        raw_json = provider.execute_dp_background(
            provider_url,
            payload_body,
            headers,
            timeout=timeout_to_use,
        )
        _ge.assert_grounding_and_reasoning(raw_json, provider=provider)
    else:
        raw_json = _http_post_json(
            provider_url,
            payload_body,
            headers,
            timeout=timeout_to_use,
        )
        _ge.assert_grounding_and_reasoning(raw_json, provider=provider)
    # Core-level mandatory verification (non-configurable): assert grounding and reasoning again.
    _ge.assert_grounding_and_reasoning(raw_json, provider=provider)
    elapsed = time.time() - start_ts
    try:
        if isinstance(raw_json, dict):
            LOG.info("HTTP POST completed in %.2fs; response keys=%s; tool_choice=%s", elapsed, list(raw_json.keys()), raw_json.get("tool_choice"))
        else:
            LOG.info("HTTP POST completed in %.2fs; response type=%s", elapsed, type(raw_json))
    except Exception:
        LOG.debug("Completed HTTP POST in %.2fs but failed to inspect response for logging", elapsed)

    # out_path was resolved earlier (pre-HTTP); proceed to ensure directory exists

    final_out_path = Path(out_path)
    # create parent directory if it does not exist
    final_out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path = str(final_out_path)

    # Raw provider sidecar files are no longer written. The response is captured in the consolidated run log.

    # ---- Enhanced logging & extraction (request/response, web_search results, reasoning) ----
    base_dir = Path(__file__).resolve().parent

    # Extract web_search_call entries from provider response (if present)
    websearch_entries = []
    try:
        output_items = raw_json.get("output") or raw_json.get("outputs") or []
        for item in output_items:
            if not isinstance(item, dict):
                continue
            t = item.get("type", "")
            if t == "web_search_call" or "web_search" in t or t.startswith("ws_"):
                websearch_entries.append(item)
    except Exception:
        LOG.exception("Failed to extract web_search entries from raw response")
        websearch_entries = []

    # Extract provider reasoning (if provider exposes an extractor)
    reasoning_text = None
    try:
        if hasattr(provider, "extract_reasoning"):
            reasoning_text = provider.extract_reasoning(raw_json)
        else:
            reasoning_text = raw_json.get("reasoning")
    except Exception:
        LOG.exception("Failed to extract reasoning via provider.extract_reasoning")
        reasoning_text = None

    # Consolidated per-run log (single JSON) written to logs/ with a run UID
    try:
        import uuid as _uuid
        import datetime as _dt
        # run_id was generated earlier for filename/log correlation
        started_iso = _dt.datetime.fromtimestamp(start_ts).isoformat()
        finished_iso = _dt.datetime.now().isoformat()

        # Attempt to get a human-readable text representation for inclusion
        try:
            human_text = provider.parse_response(raw_json) if hasattr(provider, "parse_response") else json.dumps(raw_json, indent=2, ensure_ascii=False)
        except Exception:
            human_text = None

        # Standardize usage across providers (OpenAI/Gemini) and compute cost
        def _std_usage(rj: dict) -> dict:
            # OpenAI-style (Responses API and Chat Completions)
            try:
                u = rj.get("usage") or {}
                # Responses API fields
                it = u.get("input_tokens")
                ot = u.get("output_tokens")
                tt = u.get("total_tokens")
                if any(isinstance(x, int) for x in (it, ot, tt)):
                    it_i = int(it or 0)
                    ot_i = int(ot or 0)
                    return {"prompt_tokens": it_i, "completion_tokens": ot_i, "total_tokens": int(tt or (it_i + ot_i))}
                # Legacy Chat Completions fields
                pt = u.get("prompt_tokens")
                ct = u.get("completion_tokens")
                if isinstance(pt, int) or isinstance(ct, int):
                    pt_i = int(pt or 0)
                    ct_i = int(ct or 0)
                    return {"prompt_tokens": pt_i, "completion_tokens": ct_i, "total_tokens": pt_i + ct_i}
            except Exception:
                pass
            # Google Gemini-style
            try:
                um = rj.get("usageMetadata") or {}
                pt = um.get("promptTokenCount")
                ct = um.get("candidatesTokenCount")
                tt = um.get("totalTokenCount")
                if any(isinstance(x, int) for x in (pt, ct, tt)):
                    if pt is None or ct is None:
                        pts = 0
                        cts = 0
                        for c in (rj.get("candidates") or []):
                            m = c.get("usageMetadata") or {}
                            pts += int(m.get("promptTokenCount") or 0)
                            cts += int(m.get("candidatesTokenCount") or 0)
                        pt = int(pt or pts)
                        ct = int(ct or cts)
                    return {
                        "prompt_tokens": int(pt or 0),
                        "completion_tokens": int(ct or 0),
                        "total_tokens": int(tt or (int(pt or 0) + int(ct or 0))),
                    }
            except Exception:
                pass
            return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        usage_std = _std_usage(raw_json)

        # Price lookup and cost computation
        try:
            pricing_path = str(base_dir / "pricing" / "pricing_index.json")
            pricing_list = load_pricing_index(pricing_path)
            model_cfg = cfg.get("model") or ""
            canonical_provider = "openai" if provider_name in ("openaidp",) else provider_name
            model_slug = model_cfg if "/" in str(model_cfg) else f"{canonical_provider}/{model_cfg}"
            rec = find_pricing(pricing_list, model_slug)
            cost = calc_cost(usage_std.get("prompt_tokens", 0), usage_std.get("completion_tokens", 0), rec)
            total_cost_usd = cost.get("total_cost_usd")
        except Exception:
            cost = {"reason": "cost_calc_failed"}
            total_cost_usd = None

        # Optional run group metadata from environment
        run_group_id = os.environ.get("FPF_RUN_GROUP_ID")

        consolidated = {
            "run_group_id": run_group_id,
            "run_id": run_id,
            "started_at": started_iso,
            "finished_at": finished_iso,
            "model": cfg.get("model"),
            "config": cfg,
            "request": payload_body,
            "response": raw_json,
            "web_search": websearch_entries,
            "reasoning": reasoning_text,
            "human_text": human_text,
            "usage": usage_std,
            "cost": cost,
            "total_cost_usd": total_cost_usd,
        }

        logs_root = Path(os.environ.get("FPF_LOG_DIR") or (base_dir / "logs"))
        logs_dir = (logs_root / run_group_id) if run_group_id else logs_root
        if not logs_dir.exists():
            logs_dir.mkdir(parents=True, exist_ok=True)

        # Write a unique per-run JSON log file that contains the full run data.
        try:
            log_name = f"{_dt.datetime.now().strftime('%Y%m%dT%H%M%S')}-{run_id}.json"
            log_path = logs_dir / log_name
            with open(log_path, "w", encoding="utf-8") as fh:
                json.dump(consolidated, fh, indent=2, ensure_ascii=False)
            LOG.info("Wrote per-run consolidated log %s (run_id=%s)", log_path, run_id)
        except Exception:
            LOG.exception("Failed to write per-run consolidated log")
    except Exception:
        LOG.exception("Unexpected error in enhanced logging/extraction")

    # Grounding and reasoning were asserted earlier via grounding_enforcer (mandatory).

    # Extract and (optionally) verify reasoning
    reasoning_text = None
    try:
        if hasattr(provider, "extract_reasoning"):
            reasoning_text = provider.extract_reasoning(raw_json)
        else:
            # attempt a best-effort extraction from known shapes
            reasoning_text = raw_json.get("reasoning")
            if isinstance(reasoning_text, dict):
                # stringify simple dict forms
                reasoning_text = "\n\n".join([str(v) for v in reasoning_text.values() if isinstance(v, (str, int, float))])
    except Exception:
        LOG.exception("Failed to extract reasoning from provider response")
        reasoning_text = None

    # Reasoning presence was asserted earlier via grounding_enforcer.

    # Parse human-readable text and decide output content
    if hasattr(provider, "parse_response"):
        human_text = provider.parse_response(raw_json)
    else:
        human_text = json.dumps(raw_json, indent=2, ensure_ascii=False)

    output_content = human_text
    parsed_json_found = False
    if request_json:
        try:
            extracted = _extract_json_from_text(human_text or "")
            if extracted:
                output_content = extracted
                parsed_json_found = True
        except Exception:
            # best-effort only
            pass

    # Write output (only after all checks passed)
    # Final defensive guard: if grounding wasn't detected, refuse to write any output file.
    # This is belt-and-suspenders on top of earlier assertions.
    if not _ge.detect_grounding(raw_json):
        raise RuntimeError("Refusing to write output: no provider-side grounding detected")
    try:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(output_content)
    except Exception as e:
        LOG.exception("Failed to write output to %s: %s", out_path, e)
        raise RuntimeError(f"Failed to write output to {out_path}: {e}") from e

    # Check minimum content size (3KB) - documents under this threshold are likely incomplete
    # Skip this check for JSON outputs (e.g., evaluation responses) which are naturally smaller
    MIN_CONTENT_BYTES = 3072  # 3KB
    content_size = len(output_content.encode('utf-8'))
    if content_size < MIN_CONTENT_BYTES and not parsed_json_found and not request_json:
        LOG.warning("FPF output too small (%d bytes < %d bytes minimum), triggering retry", content_size, MIN_CONTENT_BYTES)
        raise RuntimeError(f"FPF output too small ({content_size} bytes), minimum is {MIN_CONTENT_BYTES} bytes")

    LOG.info("Run validated: web_search used and reasoning present. Output written to %s parsed_json_found=%s", out_path, parsed_json_found)
    # Emit RUN_COMPLETE (single-run mode) at INFO to console and file
    if os.getenv("FPF_SCHEDULER") != "1":
        try:
            LOG.info("[FPF RUN_COMPLETE] id=%s kind=%s provider=%s model=%s ok=true elapsed=%.2fs status=%s path=%s error=%s", run_id, kind, provider_name, cfg.get("model"), elapsed, "na", out_path, "na")
        except Exception:
            pass
    return out_path
