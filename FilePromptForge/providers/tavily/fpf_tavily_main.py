import os
import json
import time
import urllib.request
import urllib.error
import sys
import random
import logging

LOG = logging.getLogger("fpf_tavily_main")

ALLOWED_MODELS = {"mini", "pro", "auto"}


def _is_transient_error(exc: Exception) -> bool:
    """Check if an error is transient and should be retried."""
    msg = str(exc).lower()
    transient_indicators = [
        "429", "rate limit", "quota",  # Rate limiting
        "timeout", "timed out",         # Timeouts
        "502", "503", "504",            # Server errors
        "connection", "network",        # Network issues
        "temporarily unavailable",
        "service unavailable",
        "internal server error",
    ]
    return any(tok in msg for tok in transient_indicators)


def _normalize_model(model_id: str) -> str:
    raw = str(model_id) if model_id is not None else ""
    base = raw.split(":", 1)[0]
    if base.startswith("tvly-"):
        base = base[len("tvly-"):]
    return base or "auto"


def validate_model(model_id: str) -> bool:
    normalized = _normalize_model(model_id)
    return normalized in ALLOWED_MODELS


def build_payload(prompt: str, cfg: dict):
    model = cfg.get("model") or "auto"
    normalized_model = _normalize_model(model)
    if not validate_model(model):
        allowed = ", ".join(sorted(ALLOWED_MODELS))
        raise RuntimeError(f"model '{model}' is not allowed for Tavily provider; allowed: {allowed}")
    stream = bool(cfg.get("stream", False))
    citation_format = cfg.get("citation_format", "numbered")
    output_schema = cfg.get("output_schema")

    payload = {
        "input": prompt,
        "model": normalized_model,
        "stream": stream,
        "citation_format": citation_format,
    }
    if output_schema is not None:
        payload["output_schema"] = output_schema

    # API key is handled by file_handler.py which reads from .env and sets Authorization header
    # Do NOT read from os.environ here - follow the same pattern as Google/OpenAI providers
    headers = {
        "Content-Type": "application/json",
    }

    return payload, headers


def _http_get_json(url: str, headers: dict, timeout: int = 60) -> dict:
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw)


def execute_and_verify(provider_url: str, payload: dict, headers: dict, verify_helpers, timeout: int = 300, max_retries: int = 3, verbose: bool = None) -> dict:
    """
    Tavily is asynchronous: POST returns {status: pending, request_id}. We must poll
    GET /research/{request_id} until status == "completed" (or timeout) and then
    return the final JSON for grounding/reasoning validation.
    
    Includes retry logic with exponential backoff for transient errors.
    
    Args:
        timeout: Polling deadline in seconds (default 300s for long research tasks)
        verbose: If True, emit status updates to stdout for ACM subprocess capture.
                 If None (default), auto-detect from FPF_LOG_OUTPUT env var.
    """
    import sys
    import os
    body = json.dumps(payload).encode("utf-8")
    hdrs = dict(headers or {})
    base_delay_ms = 500
    max_delay_ms = 30000
    
    # Auto-detect verbose mode from FPF_LOG_OUTPUT if not explicitly set
    if verbose is None:
        fpf_log_output = os.getenv("FPF_LOG_OUTPUT", "console").lower()
        verbose = fpf_log_output in ("console", "both")
    
    # Import this module directly rather than using sys.modules which fails in subprocess context
    import providers.tavily.fpf_tavily_main as provider_module
    
    def _emit_status(msg: str):
        """Emit status update to stdout for ACM subprocess reader when verbose enabled."""
        if verbose:
            print(f"[TAVILY_STATUS] {msg}", flush=True)
            sys.stdout.flush()
    
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            _emit_status(f"Attempt {attempt}/{max_retries}: Initiating Tavily research request...")
            LOG.debug("Tavily request attempt %d/%d to %s", attempt, max_retries, provider_url)
            req = urllib.request.Request(provider_url, data=body, headers=hdrs, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                first_json = json.loads(raw)

            request_id = first_json.get("request_id")
            status = first_json.get("status")
            _emit_status(f"Received request_id={request_id}, initial status={status}")

            # If already completed (unlikely), validate directly
            if status == "completed" and request_id:
                _emit_status("Research completed immediately!")
                verify_helpers.assert_grounding_and_reasoning(first_json, provider=provider_module)
                return first_json

            if not request_id:
                raise RuntimeError("Tavily did not return request_id; cannot poll for completion")

            poll_interval = 3
            deadline = time.time() + timeout
            final_json = first_json
            poll_count = 0
            while time.time() < deadline:
                time.sleep(poll_interval)
                poll_count += 1
                elapsed = int(time.time() - (deadline - timeout))
                remaining = int(deadline - time.time())
                poll_url = provider_url.rstrip("/") + f"/{request_id}"
                final_json = _http_get_json(poll_url, hdrs, timeout=timeout)
                status = final_json.get("status")
                _emit_status(f"Poll #{poll_count}: status={status}, elapsed={elapsed}s, remaining={remaining}s")
                if status == "completed":
                    _emit_status(f"Research completed after {elapsed}s!")
                    break
                if status in ("failed", "error"):
                    raise RuntimeError(f"Tavily research failed with status={status}")

            if final_json.get("status") != "completed":
                raise RuntimeError("Tavily research did not complete before timeout")

            verify_helpers.assert_grounding_and_reasoning(final_json, provider=provider_module)
            return final_json
            
        except urllib.error.HTTPError as he:
            try:
                msg = he.read().decode("utf-8", errors="ignore")
            except Exception:
                msg = ""
            last_error = RuntimeError(f"HTTP error {getattr(he, 'code', '?')}: {getattr(he, 'reason', '?')} - {msg}")
            
            if attempt < max_retries and _is_transient_error(last_error):
                delay_ms = min(base_delay_ms * (2 ** (attempt - 1)), max_delay_ms)
                delay_ms = random.uniform(0, delay_ms)
                delay_s = delay_ms / 1000.0
                LOG.warning("Transient error on attempt %d/%d, retrying in %.2fs: %s", attempt, max_retries, delay_s, he)
                time.sleep(delay_s)
                continue
            raise last_error from he
            
        except Exception as e:
            last_error = RuntimeError(f"Tavily request failed: {e}")
            
            if attempt < max_retries and _is_transient_error(e):
                delay_ms = min(base_delay_ms * (2 ** (attempt - 1)), max_delay_ms)
                delay_ms = random.uniform(0, delay_ms)
                delay_s = delay_ms / 1000.0
                LOG.warning("Transient error on attempt %d/%d, retrying in %.2fs: %s", attempt, max_retries, delay_s, e)
                time.sleep(delay_s)
                continue
            raise last_error from e
    
    if last_error:
        raise last_error
    raise RuntimeError("Tavily request failed after all retries")


def parse_response(raw_json: dict) -> str:
    if not isinstance(raw_json, dict):
        return json.dumps(raw_json)

    if raw_json.get("content"):
        return str(raw_json["content"])
    if raw_json.get("answer"):
        return str(raw_json["answer"])
    if raw_json.get("report"):
        return str(raw_json["report"])

    sources = raw_json.get("sources")
    if sources and isinstance(sources, list):
        parts = []
        for s in sources[:3]:
            title = s.get("title") if isinstance(s, dict) else None
            url = s.get("url") if isinstance(s, dict) else None
            if title and url:
                parts.append(f"{title} <{url}>")
            elif url:
                parts.append(url)
            elif title:
                parts.append(title)
        if parts:
            return "\n".join(parts)

    return json.dumps(raw_json)


def extract_reasoning(raw_json: dict):
    """Tavily-specific reasoning extractor.

    Priority:
    1) explicit reasoning field if present
    2) top-level content/report as rationale text
    3) fallback: join source titles/urls
    """
    if not isinstance(raw_json, dict):
        return None

    reasoning = raw_json.get("reasoning")
    if reasoning:
        return str(reasoning)

    # content/report as fallback rationale
    for key in ("content", "report"):
        val = raw_json.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    # sources fallback
    sources = raw_json.get("sources")
    if sources and isinstance(sources, list):
        parts = []
        for s in sources[:5]:
            if not isinstance(s, dict):
                continue
            title = s.get("title")
            url = s.get("url")
            if url and title:
                parts.append(f"{title} — {url}")
            elif url:
                parts.append(url)
            elif title:
                parts.append(title)
        if parts:
            return "; ".join(parts)

    return None

