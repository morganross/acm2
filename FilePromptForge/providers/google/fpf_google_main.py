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
import sys
import os

LOG = logging.getLogger("fpf_google_main")

# --- EXTREME LOGGING: TRACE HELPER ---
TRACE_LEVEL_NUM = 5
def trace(msg: str, *args):
    if LOG.isEnabledFor(TRACE_LEVEL_NUM):
        ts = time.time()
        LOG.log(TRACE_LEVEL_NUM, f"[{ts:.4f}] {msg}", *args)

def _dump_bits(label: str, data: bytes):
    """Log every single byte and bit as requested."""
    try:
        ts = time.time()
        pid = os.getpid()
        # Create a separate dump file for this specific event
        # We use a random suffix to ensure no collisions even with fast loops
        rnd = random.randint(0, 999999)
        filename = f"logs/dump_{pid}_{int(ts*1000000)}_{rnd}_{label}.txt"
        os.makedirs("logs", exist_ok=True)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"Label: {label}\n")
            f.write(f"Timestamp: {ts}\n")
            f.write(f"Size: {len(data)} bytes\n")
            f.write("-" * 40 + "\n")
            # Hex and Binary dump
            # We will log every byte as requested
            for i, byte in enumerate(data):
                binary = f"{byte:08b}"
                hex_val = f"{byte:02x}"
                char = chr(byte) if 32 <= byte <= 126 else "."
                f.write(f"Byte {i:08d}: Hex={hex_val} | Bin={binary} | Char={char}\n")
        trace(f"Dumped {len(data)} bytes to {filename}")
    except Exception as e:
        print(f"Failed to dump bits: {e}", file=sys.stderr)

def _log_response_details(data: dict):
    """Log detailed structure of the response."""
    try:
        trace("--- RESPONSE DETAILS ---")
        if not isinstance(data, dict):
            trace("Response is not a dict: %s", type(data))
            return

        # Usage Metadata
        usage = data.get("usageMetadata", {})
        trace("Usage: prompt=%s, candidates=%s, total=%s", 
              usage.get("promptTokenCount"), 
              usage.get("candidatesTokenCount"), 
              usage.get("totalTokenCount"))

        # Candidates
        candidates = data.get("candidates", [])
        trace("Candidate Count: %d", len(candidates))
        
        for i, cand in enumerate(candidates):
            trace("Candidate %d:", i)
            trace("  Finish Reason: %s", cand.get("finishReason"))
            trace("  Safety Ratings: %s", len(cand.get("safetyRatings", [])))
            
            # Content
            content = cand.get("content", {})
            parts = content.get("parts", [])
            trace("  Content Parts: %d", len(parts))
            for j, part in enumerate(parts):
                txt = part.get("text", "")
                trace("    Part %d Text Length: %d", j, len(txt))
                if len(txt) < 100:
                    trace("    Part %d Text Preview: %s", j, txt)
            
            # Grounding
            gm = cand.get("groundingMetadata", {})
            if gm:
                trace("  Grounding Metadata Present")
                trace("    Web Search Queries: %s", gm.get("webSearchQueries"))
                trace("    Search Entry Point: %s", gm.get("searchEntryPoint"))
                trace("    Retrieval Queries: %s", gm.get("retrievalQueries"))
            else:
                trace("  NO Grounding Metadata")
                
            # Citation
            cm = cand.get("citationMetadata", {})
            if cm:
                trace("  Citation Metadata Present: %d sources", len(cm.get("citationSources", [])))

        # Prompt Feedback
        pf = data.get("promptFeedback", {})
        if pf:
            trace("Prompt Feedback: %s", pf)
            
        trace("------------------------")
    except Exception as e:
        trace("Error logging response details: %s", e)
# -------------------------------------


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


def build_payload(prompt: str, cfg: Dict) -> Tuple[Dict, Optional[Dict]]:
    """
    Build a Gemini API payload that enforces web_search.
    """
    model = cfg.get("model")
    if not model:
        raise RuntimeError("Google provider requires 'model' in config - no fallback defaults allowed")
    model_to_use = _normalize_model(model)

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
    # --- EXTREME LOGGING: REASONING EXTRACTION ---
    try:
        import json
        print(f"[FPF GOOGLE DEBUG] extract_reasoning input keys: {list(raw_json.keys()) if isinstance(raw_json, dict) else 'not_dict'}", file=sys.stderr, flush=True)
    except Exception:
        pass
    # ---------------------------------------------

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
    except Exception as e:
        print(f"[FPF GOOGLE DEBUG] extract_reasoning step 1 failed: {e}", file=sys.stderr, flush=True)
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
    except Exception as e:
        print(f"[FPF GOOGLE DEBUG] extract_reasoning step 2 failed: {e}", file=sys.stderr, flush=True)
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
    except Exception as e:
        print(f"[FPF GOOGLE DEBUG] extract_reasoning step 3 failed: {e}", file=sys.stderr, flush=True)
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
    import threading
    from memory_dumper import dump_stack_traces, dump_heap_stats, ExtremeLogger, dump_system_diagnostics, log_call

    trace("ENTER execute_and_verify timeout=%s", timeout)
    trace("Preparing payload serialization...")
    
    # Dump initial memory state and system diagnostics
    trace("Dumping initial memory state and diagnostics...")
    dump_system_diagnostics("pre_run")
    dump_stack_traces("pre_serialize")
    dump_heap_stats("pre_serialize")
    
    try:
        data = _json.dumps(payload).encode("utf-8")
    except Exception as e:
        trace("Serialization failed: %s", e)
        raise

    trace("Payload serialized. Size: %d bytes", len(data))
    _dump_bits("request_payload", data)

    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    
    trace("Headers prepared: %s", list(hdrs.keys()))
    
    # Check for API Key in headers
    if "x-goog-api-key" in hdrs:
        key_val = hdrs["x-goog-api-key"]
        masked_key = f"{key_val[:4]}...{key_val[-4:]}" if key_val and len(key_val) > 8 else "INVALID"
        trace("API Key found in headers: x-goog-api-key=%s (Length: %d)", masked_key, len(key_val) if key_val else 0)
    else:
        trace("CRITICAL: x-goog-api-key NOT found in headers!")
        LOG.error("x-goog-api-key missing from Google request headers")

    base_delay_ms = 500
    max_delay_ms = 30000
    last_error = None
    
    for attempt in range(1, max_retries + 1):
        trace("Starting attempt %d/%d", attempt, max_retries)
        
        req = urllib.request.Request(provider_url, data=data, headers=hdrs, method="POST")
        trace("Request object created: %s", req)
        trace("Request method: %s", req.get_method())
        trace("Request full url: %s", req.get_full_url())
        
        # Start Extreme Logger for this attempt
        extreme_logger = ExtremeLogger(interval=1.0) # 1 log per second + stack dumps
        extreme_logger.start()
        
        try:
            LOG.debug("Google request attempt %d/%d to %s", attempt, max_retries, provider_url)
            trace("Attempt %d: Calling urlopen with timeout=%s", attempt, timeout)
            
            start_time = time.time()
            
            # Wrap urlopen in a logged function for call tracing
            @log_call
            def logged_urlopen(r, t):
                return urllib.request.urlopen(r, timeout=t)

            with logged_urlopen(req, timeout) as resp:
                elapsed = time.time() - start_time
                trace("Attempt %d: urlopen returned after %.4fs", attempt, elapsed)
                trace("Response code: %s", resp.getcode())
                trace("Response headers: %s", resp.info())
                
                trace("Reading response body...")
                raw_bytes = resp.read()
                trace("Read %d bytes from response", len(raw_bytes))
                _dump_bits(f"response_body_attempt_{attempt}", raw_bytes)
                
                trace("Decoding response...")
                raw = raw_bytes.decode("utf-8")
                trace("Response decoded. Length: %d chars", len(raw))
                
                trace("Parsing JSON...")
                raw_json = _json.loads(raw)
                trace("JSON parsed successfully. Keys: %s", list(raw_json.keys()) if isinstance(raw_json, dict) else "not_dict")
                
                _log_response_details(raw_json)
                
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
                    print(f"[FPF GOOGLE DEBUG] Exiting 3 (Both missing)", file=sys.stderr, flush=True)
                    sys.exit(3)  # Both missing
                elif ve.missing_grounding:
                    print(f"[FPF GOOGLE DEBUG] Exiting 1 (Grounding missing)", file=sys.stderr, flush=True)
                    sys.exit(1)  # Grounding only
                elif ve.missing_reasoning:
                    print(f"[FPF GOOGLE DEBUG] Exiting 2 (Reasoning missing)", file=sys.stderr, flush=True)
                    sys.exit(2)  # Reasoning only
                else:
                    print(f"[FPF GOOGLE DEBUG] Exiting 4 (Unknown validation error)", file=sys.stderr, flush=True)
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
                
                trace("TRANSIENT ERROR DETECTED: %s", last_error)
                trace("Retry Decision: YES (Attempt %d < %d)", attempt, max_retries)
                trace("Backoff Strategy: Exponential with Full Jitter")
                trace("Base Delay: %dms, Max Delay: %dms", base_delay_ms, max_delay_ms)
                trace("Calculated Delay: %.4fs", delay_s)
                
                LOG.warning("Transient error on attempt %d/%d, retrying in %.2fs: %s", attempt, max_retries, delay_s, he)
                
                trace("Sleeping for %.4fs...", delay_s)
                time.sleep(delay_s)
                trace("Woke up from sleep. Proceeding to next attempt.")
                continue
            
            trace("FATAL ERROR or MAX RETRIES REACHED")
            trace("Is Transient: %s", _is_transient_error(last_error))
            trace("Attempts Exhausted: %s", attempt >= max_retries)
            raise last_error from he
            
        except Exception as e:
            # --- EXTREME LOGGING: EXCEPTION DEBUG ---
            print(f"[FPF GOOGLE DEBUG] Exception on attempt {attempt}: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
            trace("EXCEPTION CAUGHT: %s: %s", type(e).__name__, e)
            # ----------------------------------------
            last_error = RuntimeError(f"HTTP request failed: {e}")
            
            # Check if we should retry
            if attempt < max_retries and _is_transient_error(e):
                delay_ms = min(base_delay_ms * (2 ** (attempt - 1)), max_delay_ms)
                delay_ms = random.uniform(0, delay_ms)  # Full jitter
                delay_s = delay_ms / 1000.0
                
                trace("TRANSIENT EXCEPTION DETECTED: %s", e)
                trace("Retry Decision: YES (Attempt %d < %d)", attempt, max_retries)
                trace("Calculated Delay: %.4fs", delay_s)
                
                LOG.warning("Transient error on attempt %d/%d, retrying in %.2fs: %s", attempt, max_retries, delay_s, e)
                
                trace("Sleeping for %.4fs...", delay_s)
                time.sleep(delay_s)
                trace("Woke up from sleep. Proceeding to next attempt.")
                continue
            
            trace("FATAL EXCEPTION or MAX RETRIES REACHED")
            raise last_error from e
        finally:
            extreme_logger.stop()
            extreme_logger.join()
            dump_stack_traces(f"post_attempt_{attempt}")
            dump_heap_stats(f"post_attempt_{attempt}")
    
    # Should not reach here, but just in case
    if last_error:
        trace("Loop finished with error: %s", last_error)
        raise last_error
    trace("Loop finished without explicit error but no return. Raising generic RuntimeError.")
    raise RuntimeError("HTTP request failed after all retries")
