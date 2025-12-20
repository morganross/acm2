"""
Google Gemini provider adapter for FPF.

This adapter enforces provider-side web_search for every outgoing payload.

- build_payload(prompt: str, cfg: dict) -> (dict, dict|None)
- parse_response(raw: dict) -> str
- extract_reasoning(raw: dict) -> Optional[str]
- validate_model(model_id: str) -> bool
"""

from __future__ import annotations
from typing import Dict, Tuple, Optional, Any, List
import logging
import random
import time

LOG = logging.getLogger("fpf_google_main")

ALLOWED_MODELS = {
    "gemini-pro-latest",
    "gemini-3-pro-preview",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
}


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


def _normalize_model(model: str) -> str:
    if not model:
        return ""
    return model.split(":")[0]


def validate_model(model_id: str) -> bool:
    m = _normalize_model(model_id or "")
    if m in ALLOWED_MODELS:
        return True
    for allowed in ALLOWED_MODELS:
        if m.startswith(allowed):
            return True
    return False


def build_payload(prompt: str, cfg: Dict) -> Tuple[Dict, Optional[Dict]]:
    """
    Build a Gemini API payload that enforces web_search.
    """
    model = cfg.get("model") or "gemini-2.5-pro"
    model_to_use = _normalize_model(model)

    if not validate_model(model_to_use):
        raise RuntimeError(f"Model '{model_to_use}' is not allowed by the Google provider whitelist. Allowed models: {sorted(ALLOWED_MODELS)}")

    # For JSON requests, prepend a JSON-only instruction; otherwise use prompt as-is
    try:
        request_json = bool(cfg.get("json"))
    except Exception:
        request_json = False

    if request_json:
        json_instr = "Return only a single valid JSON object. Do not include any prose or Markdown fences. Output must be strictly valid JSON."
        final_prompt = f"{json_instr}\n\n{prompt}"
    else:
        # Use the prompt exactly as provided - no additional prefixes
        final_prompt = prompt

    payload: Dict[str, Any] = {
        "contents": [
            {
                "parts": [
                    {"text": final_prompt}
                ]
            }
        ],
        "tools": [
            {
                "google_search": {}
            }
        ]
    }
    
    # Note: toolConfig.functionCallingConfig is for custom function_declarations only,
    # NOT for built-in tools like google_search. The model will use google_search
    # when it deems appropriate based on the prompt.
    generation_config = {}
    if "max_completion_tokens" in cfg and cfg["max_completion_tokens"] is not None:
        generation_config["maxOutputTokens"] = int(cfg["max_completion_tokens"])
    
    if "temperature" in cfg and cfg["temperature"] is not None:
        generation_config["temperature"] = float(cfg["temperature"])

    if "top_p" in cfg and cfg["top_p"] is not None:
        generation_config["topP"] = float(cfg["top_p"])

    # Apply reasoning config based on model version
    if model_to_use.startswith("gemini-3"):
        # Gemini 3: Use thinkingLevel (cannot use thinkingBudget)
        # Default to high reasoning if not specified, and ensure thoughts are included.
        tc = generation_config.get("thinkingConfig", {})
        
        # Respect configured effort if present (low/high), default to high
        configured_effort = (cfg.get("reasoning") or {}).get("effort")
        if configured_effort and str(configured_effort).lower() in ("low", "high"):
            tc["thinkingLevel"] = str(configured_effort).lower()
        else:
            tc["thinkingLevel"] = "high"
            
        tc["includeThoughts"] = True
        generation_config["thinkingConfig"] = tc
    elif model_to_use.startswith("gemini-2.5"):
        # Gemini 2.5: Use thinkingBudget (legacy style)
        # Only apply if we want to enforce reasoning defaults for 2.5 as well.
        # Given the user's context implies a migration from an existing setup, 
        # we'll add a safe default budget to match the "program that uses gemini 2.5-pro with reasoning" description.
        tc = generation_config.get("thinkingConfig", {})
        if "thinkingBudget" not in tc:
            tc["thinkingBudget"] = 8000
        tc["includeThoughts"] = True
        generation_config["thinkingConfig"] = tc

    # Never set JSON responseMimeType or responseJsonSchema for Google; JSON is prompt-only when cfg["json"] is True.

    if generation_config:
        payload["generationConfig"] = generation_config

    return payload, None


def extract_reasoning(raw_json: Dict) -> Optional[str]:
    """
    Extract reasoning content from a Gemini API response object if present.

    Accepted indicators (in order of preference):
    - candidates[*].groundingMetadata.webSearchQueries (joined as newline string)
    - candidates[*].groundingMetadata.groundingSupports / confidenceScores (summarized)
    - candidates[*].content.parts[*].text (first 1-2 non-empty text parts joined)
    """
    if not isinstance(raw_json, dict):
        return None

    # 1) Grounding metadata: webSearchQueries (strongest signal)
    try:
        cands = raw_json.get("candidates")
        if isinstance(cands, list) and cands:
            gm = cands[0].get("groundingMetadata")
            if isinstance(gm, dict):
                queries = gm.get("webSearchQueries")
                if isinstance(queries, list) and queries:
                    return "\n".join([str(q) for q in queries if isinstance(q, str) and q.strip()])
    except Exception:
        pass

    # 2) Grounding metadata: supports / confidence (treat as reasoning summary)
    try:
        cands = raw_json.get("candidates")
        if isinstance(cands, list) and cands:
            gm = cands[0].get("groundingMetadata")
            if isinstance(gm, dict):
                supports = gm.get("groundingSupports") or gm.get("supportingContent") or []
                confs = gm.get("confidenceScores") or []
                if (isinstance(supports, list) and len(supports) > 0) or (isinstance(confs, list) and len(confs) > 0):
                    sup_n = len(supports) if isinstance(supports, list) else 0
                    conf_n = len(confs) if isinstance(confs, list) else 0
                    return f"Gemini grounding metadata present (supports={sup_n}, confidence_scores={conf_n})."
    except Exception:
        pass

    # 3) Content parts text (fallback summary)
    try:
        cands = raw_json.get("candidates")
        if isinstance(cands, list) and cands:
            content = cands[0].get("content") or {}
            parts = content.get("parts")
            if isinstance(parts, list):
                texts: List[str] = []
                for p in parts:
                    if isinstance(p, dict):
                        t = p.get("text")
                        if isinstance(t, str) and t.strip():
                            texts.append(t.strip())
                if texts:
                    # If we have multiple parts, the earlier ones are likely reasoning/thoughts
                    if len(texts) > 1:
                        return "\n\n".join(texts[:-1])
                    # If only one part, it's likely just the response, so no reasoning extracted here
                    return None
    except Exception:
        pass

    return None


def parse_response(raw_json: Dict) -> str:
    """
    Extract readable text from a Gemini API response object.
    """
    if not isinstance(raw_json, dict):
        return str(raw_json)
        
    try:
        parts = raw_json["candidates"][0]["content"]["parts"]
        # Filter for parts that have text
        text_parts = [p for p in parts if "text" in p]
        
        if not text_parts:
            return ""

        # If multiple text parts exist, the last one is the final response.
        # The earlier ones are likely thoughts/reasoning when includeThoughts=True.
        return text_parts[-1]["text"]
    except (IndexError, KeyError, TypeError):
        import json
        return json.dumps(raw_json, indent=2)

def execute_and_verify(provider_url: str, payload: Dict, headers: Optional[Dict], verify_helpers, timeout: int = 600, max_retries: int = 3) -> Dict:
    """
    Execute the Google Gemini request and verify both grounding and reasoning are present.
    Enforces mandatory grounding (google_search) and reasoning at the lowest level.
    
    Includes retry logic with exponential backoff for transient errors (502, 503, 504, etc.)
    """
    import urllib.request
    import urllib.error
    import json as _json

    data = _json.dumps(payload).encode("utf-8")
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)

    base_delay_ms = 500
    max_delay_ms = 30000
    last_error = None
    
    for attempt in range(1, max_retries + 1):
        req = urllib.request.Request(provider_url, data=data, headers=hdrs, method="POST")
        try:
            LOG.debug("Google request attempt %d/%d to %s", attempt, max_retries, provider_url)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                raw_json = _json.loads(raw)
                
                # Enforce grounding + reasoning using shared helpers; pass this module for provider-specific extraction
                try:
                    verify_helpers.assert_grounding_and_reasoning(raw_json, provider=__import__(__name__))
                except verify_helpers.ValidationError as ve:
                    # LAYER 1: Exit with specific code based on validation failure type
                    import sys
                    print(f"[VALIDATION FAILED] {ve}", file=sys.stderr, flush=True)
                    
                    # Minimal failure artifact to speed debugging
                    try:
                        import os, datetime as _dt, json as _json2
                        logs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "logs"))
                        os.makedirs(logs_dir, exist_ok=True)
                        ts = _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
                        artifact_path = os.path.join(logs_dir, f"failure-{ts}-google-grounding.json")
                        # Shallow summary to avoid huge dumps
                        cands = raw_json.get("candidates")
                        gm_present = False
                        if isinstance(cands, list) and cands:
                            gm = cands[0].get("groundingMetadata")
                            gm_present = isinstance(gm, dict) and len(gm) > 0
                        artifact = {
                            "provider": "google",
                            "provider_url": provider_url,
                            "timestamp_utc": ts,
                            "error": str(ve),
                            "validation_category": ve.category,
                            "missing_grounding": ve.missing_grounding,
                            "missing_reasoning": ve.missing_reasoning,
                            "summary": {
                                "has_candidates": isinstance(cands, list) and len(cands) > 0,
                                "has_groundingMetadata": gm_present
                            }
                        }
                        with open(artifact_path, "w", encoding="utf-8") as fh:
                            _json2.dump(artifact, fh, ensure_ascii=False, indent=2)
                    except Exception:
                        pass
                    
                    # Exit with specific code based on what's missing
                    if ve.missing_grounding and ve.missing_reasoning:
                        sys.exit(3)  # Both missing
                    elif ve.missing_grounding:
                        sys.exit(1)  # Grounding only
                    elif ve.missing_reasoning:
                        sys.exit(2)  # Reasoning only
                    else:
                        sys.exit(4)  # Unknown validation error
                except Exception as e:
                    # Non-validation errors: exit with code 5
                    import sys
                    print(f"[FPF ERROR] {e}", file=sys.stderr, flush=True)
                    sys.exit(5)
                return raw_json
                
        except urllib.error.HTTPError as he:
            try:
                msg = he.read().decode("utf-8", errors="ignore")
            except Exception:
                msg = ""
            last_error = RuntimeError(f"HTTP error {getattr(he, 'code', '?')}: {getattr(he, 'reason', '?')} - {msg}")
            
            # Check if we should retry
            if attempt < max_retries and _is_transient_error(last_error):
                delay_ms = min(base_delay_ms * (2 ** (attempt - 1)), max_delay_ms)
                delay_ms = random.uniform(0, delay_ms)  # Full jitter
                delay_s = delay_ms / 1000.0
                LOG.warning("Transient error on attempt %d/%d, retrying in %.2fs: %s", attempt, max_retries, delay_s, he)
                time.sleep(delay_s)
                continue
            
            raise last_error from he
            
        except Exception as e:
            last_error = RuntimeError(f"HTTP request failed: {e}")
            
            # Check if we should retry
            if attempt < max_retries and _is_transient_error(e):
                delay_ms = min(base_delay_ms * (2 ** (attempt - 1)), max_delay_ms)
                delay_ms = random.uniform(0, delay_ms)  # Full jitter
                delay_s = delay_ms / 1000.0
                LOG.warning("Transient error on attempt %d/%d, retrying in %.2fs: %s", attempt, max_retries, delay_s, e)
                time.sleep(delay_s)
                continue
            
            raise last_error from e
    
    # Should not reach here, but just in case
    if last_error:
        raise last_error
    raise RuntimeError("HTTP request failed after all retries")
