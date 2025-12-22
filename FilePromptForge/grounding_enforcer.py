"""
grounding_enforcer
- Centralized verification utilities to enforce that provider responses include:
  1) Grounding (provider-side web search / citations / tools)
  2) Reasoning (model-produced rationale/thinking, provider-specific shapes)

EXTREME LOGGING MODE:
- Every validation check is logged with full details
- Per-run validation log files created in logs/validation/
- All API request/response data persisted
- Field-by-field inspection results logged
- Respects Python logging levels (DEBUG/INFO/WARNING/ERROR)
"""

from __future__ import annotations
from typing import Any, Dict, Optional, List
import logging
import json
import os
import threading
from pathlib import Path
from datetime import datetime

LOG = logging.getLogger("grounding_enforcer")


def _serialize_for_json(obj: Any) -> Any:
    """Recursively convert objects to JSON-serializable types."""
    if isinstance(obj, Path):
        return str(obj)
    elif isinstance(obj, dict):
        return {k: _serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_serialize_for_json(item) for item in obj]
    else:
        return obj


class ValidationError(RuntimeError):
    """Custom exception for validation failures with detailed classification."""
    
    def __init__(self, message: str, missing_grounding: bool = False, missing_reasoning: bool = False):
        super().__init__(message)
        self.missing_grounding = missing_grounding
        self.missing_reasoning = missing_reasoning
        self.category = self._classify()
    
    def _classify(self) -> str:
        """Classify validation error for intelligent retry."""
        if self.missing_grounding and self.missing_reasoning:
            return "validation_both"
        elif self.missing_grounding:
            return "validation_grounding"
        elif self.missing_reasoning:
            return "validation_reasoning"
        return "validation_unknown"

# Global state for current run context (set by file_handler before validation).
# Use thread-local storage so each worker thread has its own context,
# avoiding cross-run contamination under high concurrency.
_CURRENT_RUN_CONTEXT = threading.local()


def set_run_context(run_id: str, provider: str, model: str, log_dir: Optional[Path] = None) -> None:
    """Set context for the current run to enable per-run logging.

    This is called by file_handler for each run, typically once per thread.
    Thread-local storage ensures that concurrent runs do not overwrite each
    other's context or validation logs.
    """
    actual_log_dir = log_dir or Path(__file__).parent / "logs" / "validation"
    actual_log_dir.mkdir(parents=True, exist_ok=True)

    _CURRENT_RUN_CONTEXT.run_id = run_id
    _CURRENT_RUN_CONTEXT.provider = provider
    _CURRENT_RUN_CONTEXT.model = model
    _CURRENT_RUN_CONTEXT.log_dir = str(actual_log_dir)
    _CURRENT_RUN_CONTEXT.timestamp = datetime.utcnow().isoformat()


def _get_context_as_dict() -> Dict[str, Any]:
    """Return the current thread-local run context as a plain dict.

    If no context has been set in this thread, an empty dict is returned.
    """
    if not hasattr(_CURRENT_RUN_CONTEXT, "run_id"):
        return {}

    return {
        "run_id": getattr(_CURRENT_RUN_CONTEXT, "run_id", "unknown"),
        "provider": getattr(_CURRENT_RUN_CONTEXT, "provider", "unknown"),
        "model": getattr(_CURRENT_RUN_CONTEXT, "model", "unknown"),
        "log_dir": getattr(_CURRENT_RUN_CONTEXT, "log_dir", None),
        "timestamp": getattr(_CURRENT_RUN_CONTEXT, "timestamp", None),
    }


def _get_validation_log_path() -> Optional[Path]:
    """Get the path for the current run's validation log file."""
    if not hasattr(_CURRENT_RUN_CONTEXT, "run_id"):
        return None
    run_id = getattr(_CURRENT_RUN_CONTEXT, "run_id", "unknown")
    log_dir_str = getattr(_CURRENT_RUN_CONTEXT, "log_dir", None)
    log_dir = Path(log_dir_str) if log_dir_str else None
    # Prefer the stored timestamp if present to keep filenames stable per run.
    ts_str = getattr(_CURRENT_RUN_CONTEXT, "timestamp", "")
    try:
        if ts_str:
            dt = datetime.fromisoformat(ts_str)
            timestamp = dt.strftime("%Y%m%dT%H%M%S")
        else:
            timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    except ValueError:
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    return log_dir / f"{timestamp}-{run_id}-validation.json"


def _log_validation_detail(category: str, check: str, result: Any, details: Dict[str, Any]) -> None:
    """
    Log a single validation check with full details to both Python logger and per-run file.
    
    Args:
        category: 'grounding' or 'reasoning'
        check: Name of the specific check being performed
        result: Boolean or extracted value
        details: Additional context (field values, structure info, etc.)
    """
    # Safe serialization for logging
    try:
        safe_details = _serialize_for_json(details)
    except Exception:
        safe_details = {"error": "Failed to serialize details"}

    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "category": category,
        "check": check,
        "result": result,
        "details": safe_details,
    }
    
    # Log to Python logger at DEBUG level
    try:
        details_str = json.dumps(safe_details, ensure_ascii=False, default=str)[:500]
    except Exception:
        details_str = "<unserializable>"

    LOG.debug("[VALIDATION] %s.%s = %s | %s", category, check, result, details_str)
    
    # Also log to console for extreme visibility (ASCII-safe to avoid Windows encoding issues)
    try:
        console_details = json.dumps(safe_details, ensure_ascii=True, default=str)[:200]
        print(f"[VALIDATION] {category}.{check} = {result} | details={console_details}", flush=True)
    except Exception:
        # If even ASCII-safe print fails, just skip console output
        pass
    
    # Append to per-run validation log file
    log_path = _get_validation_log_path()
    if log_path:
        try:
            # Load existing log if present
            if log_path.exists():
                with open(log_path, "r", encoding="utf-8") as f:
                    log_data = json.load(f)
                # Ensure loaded data is also serialized (in case it contains Path objects)
                log_data = _serialize_for_json(log_data)
            else:
                # Convert Path objects and other non-serializable types to strings
                log_data = {
                    "run_context": _serialize_for_json(_get_context_as_dict()),
                    "checks": []
                }
            
            # Append this check
            log_data["checks"].append(log_entry)
            
            # Write back
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            LOG.error("Failed to write validation log to %s: %s", log_path, e)


def _save_full_response(raw_json: Dict[str, Any], stage: str) -> None:
    """Save the complete raw response at a given validation stage."""
    log_path = _get_validation_log_path()
    if not log_path:
        return
    
    try:
        response_path = log_path.parent / f"{log_path.stem}-{stage}-response.json"
        with open(response_path, "w", encoding="utf-8") as f:
            json.dump(raw_json, f, indent=2, ensure_ascii=False)
        LOG.info("Saved full %s response to %s", stage, response_path)
    except Exception as e:
        LOG.error("Failed to save %s response: %s", stage, e)


def _json_safe_get(d: Any, key: str, default=None):
    try:
        if isinstance(d, dict):
            return d.get(key, default)
    except Exception:
        pass
    return default


def detect_grounding(raw_json: Dict[str, Any]) -> bool:
    """
    Heuristics to detect that provider-side grounding/search was used.
    EXTREME LOGGING: Every check is logged with field-by-field inspection.
    """
    LOG.info("=== GROUNDING DETECTION START ===")
    _save_full_response(raw_json, "grounding_check")
    ctx_provider = _get_context_as_dict().get("provider", "").lower()
    
    if not isinstance(raw_json, dict):
        _log_validation_detail("grounding", "type_check", False, {"type": str(type(raw_json)), "reason": "not a dict"})
        LOG.info("=== GROUNDING DETECTION END: FALSE (not dict) ===")
        return False
    
    # Log top-level keys for structure visibility
    top_keys = list(raw_json.keys())
    _log_validation_detail("grounding", "structure", None, {"top_level_keys": top_keys, "key_count": len(top_keys)})

    # Check 0: Anthropic/Claude content blocks for tool_use or server_tool_use
    try:
        content_blocks = raw_json.get("content")
        _log_validation_detail(
            "grounding",
            "content_blocks",
            isinstance(content_blocks, list),
            {"type": type(content_blocks).__name__, "length": len(content_blocks) if isinstance(content_blocks, list) else 0},
        )

        if isinstance(content_blocks, list):
            for idx, block in enumerate(content_blocks):
                if not isinstance(block, dict):
                    _log_validation_detail("grounding", f"content[{idx}]", None, {"type": type(block).__name__, "skipped": True})
                    continue
                btype = block.get("type")
                name = block.get("name") or block.get("tool_name")
                has_tool = btype in ("tool_use", "server_tool_use", "web_search_tool_result")
                has_web_name = isinstance(name, str) and "web_search" in name.lower()
                has_result = isinstance(block.get("results"), list) or isinstance(block.get("search_results"), list)
                _log_validation_detail(
                    "grounding",
                    f"content[{idx}].tool",
                    has_tool or has_web_name or has_result,
                    {
                        "type": btype,
                        "name": name,
                        "keys": list(block.keys()),
                        "has_results": has_result,
                    },
                )
                if has_tool or has_web_name or has_result:
                    LOG.info("=== GROUNDING DETECTION END: TRUE (Anthropic content tool) ===")
                    return True
    except Exception as e:
        _log_validation_detail("grounding", "content_blocks", False, {"error": str(e)})
    
    # Check 1: Direct tool call evidence
    try:
        tc = raw_json.get("tool_calls")
        tc_type = type(tc).__name__
        tc_len = len(tc) if isinstance(tc, list) else 0
        tc_present = isinstance(tc, list) and len(tc) > 0
        
        _log_validation_detail("grounding", "tool_calls", tc_present, {
            "type": tc_type,
            "length": tc_len,
            "value_preview": str(tc)[:200] if tc else None
        })
        
        if tc_present:
            LOG.info("=== GROUNDING DETECTION END: TRUE (tool_calls found) ===")
            return True
    except Exception as e:
        _log_validation_detail("grounding", "tool_calls", False, {"error": str(e)})
    
    # Check 2: Tools field
    try:
        tls = raw_json.get("tools")
        tls_type = type(tls).__name__
        tls_len = len(tls) if isinstance(tls, list) else 0
        tls_present = isinstance(tls, list) and len(tls) > 0
        
        _log_validation_detail("grounding", "tools", tls_present, {
            "type": tls_type,
            "length": tls_len,
            "value_preview": str(tls)[:200] if tls else None
        })
        
        if tls_present:
            LOG.info("=== GROUNDING DETECTION END: TRUE (tools found) ===")
            return True
    except Exception as e:
        _log_validation_detail("grounding", "tools", False, {"error": str(e)})

    # Check 3: Scan output blocks for URLs/citations
    try:
        output = raw_json.get("output") or raw_json.get("outputs")
        output_type = type(output).__name__
        output_len = len(output) if isinstance(output, list) else 0
        
        _log_validation_detail("grounding", "output_blocks", None, {
            "type": output_type,
            "length": output_len,
            "present": output is not None
        })
        
        if isinstance(output, list):
            for idx, item in enumerate(output):
                if not isinstance(item, dict):
                    _log_validation_detail("grounding", f"output[{idx}]", None, {"type": type(item).__name__, "skipped": True})
                    continue
                
                item_keys = list(item.keys())
                _log_validation_detail("grounding", f"output[{idx}].keys", None, {"keys": item_keys})
                
                content = item.get("content") or item.get("contents")
                content_type = type(content).__name__
                content_len = len(content) if isinstance(content, list) else 0
                
                if isinstance(content, list):
                    for cidx, c in enumerate(content):
                        if isinstance(c, dict):
                            c_keys = list(c.keys())
                            has_link_fields = any(k in c for k in ("source", "url", "link", "href"))
                            
                            _log_validation_detail("grounding", f"output[{idx}].content[{cidx}]", has_link_fields, {
                                "type": "dict",
                                "keys": c_keys,
                                "has_link_fields": has_link_fields,
                                "link_field_types": {k: type(c.get(k)).__name__ for k in ("source", "url", "link", "href") if k in c}
                            })
                            
                            if has_link_fields:
                                LOG.info("=== GROUNDING DETECTION END: TRUE (link fields in output content) ===")
                                return True
                            
                            t = c.get("text")
                            if isinstance(t, str):
                                has_url = "http://" in t or "https://" in t
                                has_citation = "Citation:" in t or "[source]" in t
                                
                                _log_validation_detail("grounding", f"output[{idx}].content[{cidx}].text", has_url or has_citation, {
                                    "length": len(t),
                                    "has_url": has_url,
                                    "has_citation": has_citation,
                                    "preview": t[:200]
                                })
                                
                                if has_url or has_citation:
                                    LOG.info("=== GROUNDING DETECTION END: TRUE (URLs/citations in text) ===")
                                    return True
                        elif isinstance(c, str):
                            has_url = "http://" in c or "https://" in c
                            has_citation = "Citation:" in c
                            
                            _log_validation_detail("grounding", f"output[{idx}].content[{cidx}]", has_url or has_citation, {
                                "type": "str",
                                "length": len(c),
                                "has_url": has_url,
                                "has_citation": has_citation,
                                "preview": c[:200]
                            })
                            
                            if has_url or has_citation:
                                LOG.info("=== GROUNDING DETECTION END: TRUE (URLs/citations in string content) ===")
                                return True
    except Exception as e:
        _log_validation_detail("grounding", "output_scan", False, {"error": str(e)})

    # Check 4: String search in full JSON
    try:
        s = json.dumps(raw_json, ensure_ascii=False)
        has_web_search = "web_search" in s
        has_tool_call = "tool_call" in s or "tool_calls" in s
        
        _log_validation_detail("grounding", "json_string_search", has_web_search or has_tool_call, {
            "json_length": len(s),
            "has_web_search": has_web_search,
            "has_tool_call": has_tool_call,
            "json_preview": s[:500]
        })
        
        if has_web_search or has_tool_call:
            LOG.info("=== GROUNDING DETECTION END: TRUE (string search match) ===")
            return True
    except Exception as e:
        _log_validation_detail("grounding", "json_string_search", False, {"error": str(e)})

    # Check 5: Gemini-specific checks
    try:
        cands = raw_json.get("candidates")
        cands_type = type(cands).__name__
        cands_len = len(cands) if isinstance(cands, list) else 0
        
        _log_validation_detail("grounding", "candidates", None, {
            "type": cands_type,
            "length": cands_len,
            "present": cands is not None
        })
        
        if isinstance(cands, list):
            for cidx, cand in enumerate(cands):
                cand_keys = list(cand.keys()) if isinstance(cand, dict) else []
                _log_validation_detail("grounding", f"candidates[{cidx}].keys", None, {"keys": cand_keys})
                
                # Check groundingMetadata
                gm = _json_safe_get(cand, "groundingMetadata")
                gm_type = type(gm).__name__
                gm_keys = list(gm.keys()) if isinstance(gm, dict) else []
                gm_len = len(gm) if isinstance(gm, dict) else 0
                
                _log_validation_detail("grounding", f"candidates[{cidx}].groundingMetadata", None, {
                    "type": gm_type,
                    "keys": gm_keys,
                    "length": gm_len,
                    "present": gm is not None
                })
                
                if isinstance(gm, dict) and len(gm) > 0:
                    wsq = gm.get("webSearchQueries")
                    gs = gm.get("groundingSupports")
                    cs = gm.get("confidenceScores")
                    sep = gm.get("searchEntryPoint")
                    
                    _log_validation_detail("grounding", f"candidates[{cidx}].groundingMetadata.fields", None, {
                        "webSearchQueries": {"type": type(wsq).__name__, "length": len(wsq) if isinstance(wsq, list) else 0, "present": wsq is not None, "value": wsq},
                        "groundingSupports": {"type": type(gs).__name__, "length": len(gs) if isinstance(gs, list) else 0, "present": gs is not None},
                        "confidenceScores": {"type": type(cs).__name__, "present": cs is not None, "value": cs},
                        "searchEntryPoint": {"type": type(sep).__name__, "present": sep is not None, "value": sep}
                    })
                    
                    if wsq or gs or cs or sep:
                        LOG.info("=== GROUNDING DETECTION END: TRUE (Gemini groundingMetadata fields) ===")
                        return True
                    
                    # Any non-empty groundingMetadata counts
                    LOG.info("=== GROUNDING DETECTION END: TRUE (non-empty groundingMetadata) ===")
                    return True
                
                # Check citations
                cit = _json_safe_get(cand, "citations")
                cit_type = type(cit).__name__
                cit_len = len(cit) if isinstance(cit, list) else 0
                
                _log_validation_detail("grounding", f"candidates[{cidx}].citations", cit_len > 0, {
                    "type": cit_type,
                    "length": cit_len,
                    "value_preview": str(cit)[:200] if cit else None
                })
                
                if isinstance(cit, list) and len(cit) > 0:
                    LOG.info("=== GROUNDING DETECTION END: TRUE (citations present) ===")
                    return True
                
                # Check citationMetadata
                citm = _json_safe_get(cand, "citationMetadata")
                citm_type = type(citm).__name__
                citm_len = len(citm) if isinstance(citm, dict) else 0
                
                _log_validation_detail("grounding", f"candidates[{cidx}].citationMetadata", citm_len > 0, {
                    "type": citm_type,
                    "length": citm_len,
                    "value_preview": str(citm)[:200] if citm else None
                })
                
                if isinstance(citm, dict) and len(citm) > 0:
                    LOG.info("=== GROUNDING DETECTION END: TRUE (citationMetadata present) ===")
                    return True
                
                # Check content.parts
                content = _json_safe_get(cand, "content") or {}
                parts = _json_safe_get(content, "parts")
                parts_type = type(parts).__name__
                parts_len = len(parts) if isinstance(parts, list) else 0
                
                _log_validation_detail("grounding", f"candidates[{cidx}].content.parts", None, {
                    "type": parts_type,
                    "length": parts_len
                })
                
                if isinstance(parts, list):
                    for pidx, p in enumerate(parts):
                        if isinstance(p, dict):
                            p_keys = list(p.keys())
                            cm = _json_safe_get(p, "citationMetadata")
                            cm_type = type(cm).__name__
                            cm_len = len(cm) if isinstance(cm, dict) else 0
                            
                            _log_validation_detail("grounding", f"candidates[{cidx}].content.parts[{pidx}].citationMetadata", cm_len > 0, {
                                "part_keys": p_keys,
                                "type": cm_type,
                                "length": cm_len,
                                "value": cm
                            })
                            
                            if isinstance(cm, dict) and len(cm) > 0:
                                LOG.info("=== GROUNDING DETECTION END: TRUE (part citationMetadata) ===")
                                return True
                            
                            # Check for URI fields
                            uri_fields = {}
                            for k in ("uri", "url", "link", "href"):
                                v = p.get(k)
                                if isinstance(v, str) and v.strip():
                                    uri_fields[k] = v
                            
                            _log_validation_detail("grounding", f"candidates[{cidx}].content.parts[{pidx}].uri_fields", len(uri_fields) > 0, {
                                "fields_found": uri_fields
                            })
                            
                            if uri_fields:
                                LOG.info("=== GROUNDING DETECTION END: TRUE (URI fields in parts) ===")
                                return True
    except Exception as e:
        _log_validation_detail("grounding", "gemini_checks", False, {"error": str(e)})

    # Check 6: Tavily-specific checks (only if provider is tavily)
    try:
        if ctx_provider == "tavily":
            # Top-level sources list with URLs/titles counts as grounding evidence
            sources = raw_json.get("sources")
            src_present = isinstance(sources, list) and any(
                isinstance(s, dict) and (s.get("url") or s.get("title")) for s in sources or []
            )
            _log_validation_detail("grounding", "tavily.sources", src_present, {
                "type": type(sources).__name__,
                "length": len(sources) if isinstance(sources, list) else 0,
                "sample": sources[:2] if isinstance(sources, list) else None
            })
            if src_present:
                LOG.info("=== GROUNDING DETECTION END: TRUE (tavily sources) ===")
                return True

            # Scan top-level content/report/answer for URLs or embedded citations
            content = raw_json.get("content") or raw_json.get("report") or raw_json.get("answer")
            if isinstance(content, str):
                has_url = "http://" in content or "https://" in content
                has_citation = "Citation:" in content
                _log_validation_detail("grounding", "tavily.content_str", has_url or has_citation, {
                    "length": len(content),
                    "has_url": has_url,
                    "has_citation": has_citation,
                    "preview": content[:200]
                })
                if has_url or has_citation:
                    LOG.info("=== GROUNDING DETECTION END: TRUE (tavily content URLs) ===")
                    return True
            elif isinstance(content, (dict, list)):
                # Walk shallowly for url/link/href fields
                def _contains_uri(obj: Any) -> bool:
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            if k in ("url", "link", "href") and isinstance(v, str) and v.strip():
                                return True
                            if isinstance(v, (dict, list)) and _contains_uri(v):
                                return True
                    elif isinstance(obj, list):
                        for item in obj:
                            if _contains_uri(item):
                                return True
                    return False

                has_uri = _contains_uri(content)
                _log_validation_detail("grounding", "tavily.content_nested", has_uri, {
                    "type": type(content).__name__
                })
                if has_uri:
                    LOG.info("=== GROUNDING DETECTION END: TRUE (tavily nested URLs) ===")
                    return True
    except Exception as e:
        _log_validation_detail("grounding", "tavily_checks", False, {"error": str(e)})

    LOG.info("=== GROUNDING DETECTION END: FALSE (no matches) ===")
    return False


def _extract_reasoning_generic(raw_json: Dict[str, Any]) -> Optional[str]:
    """
    Provider-agnostic best-effort extraction of reasoning-like content.
    EXTREME LOGGING: All extraction attempts logged.
    """
    LOG.debug("Starting generic reasoning extraction")
    
    if not isinstance(raw_json, dict):
        _log_validation_detail("reasoning", "generic.type_check", False, {"type": str(type(raw_json))})
        return None

    # Check top-level reasoning
    r = raw_json.get("reasoning")
    r_type = type(r).__name__
    
    if isinstance(r, str) and r.strip():
        _log_validation_detail("reasoning", "generic.top_level_str", True, {
            "type": r_type,
            "length": len(r),
            "preview": r[:200]
        })
        return r.strip()
    
    if isinstance(r, dict):
        parts: List[str] = []
        for k, v in r.items():
            if isinstance(v, str) and v.strip():
                parts.append(v.strip())
        
        _log_validation_detail("reasoning", "generic.top_level_dict", len(parts) > 0, {
            "type": r_type,
            "keys": list(r.keys()),
            "string_parts_found": len(parts)
        })
        
        if parts:
            return "\n\n".join(parts)

    # Check outputs
    output = raw_json.get("output") or raw_json.get("outputs")
    output_type = type(output).__name__
    
    _log_validation_detail("reasoning", "generic.output", None, {
        "type": output_type,
        "length": len(output) if isinstance(output, list) else 0
    })
    
    if isinstance(output, list):
        for idx, item in enumerate(output):
            if not isinstance(item, dict):
                continue
            
            # Check reasoning field
            ri = item.get("reasoning")
            if isinstance(ri, str) and ri.strip():
                _log_validation_detail("reasoning", f"generic.output[{idx}].reasoning", True, {
                    "type": "str",
                    "length": len(ri),
                    "preview": ri[:200]
                })
                return ri.strip()
            
            if isinstance(ri, dict):
                parts = []
                for v in ri.values():
                    if isinstance(v, str) and v.strip():
                        parts.append(v.strip())
                
                _log_validation_detail("reasoning", f"generic.output[{idx}].reasoning", len(parts) > 0, {
                    "type": "dict",
                    "keys": list(ri.keys()),
                    "string_parts": len(parts)
                })
                
                if parts:
                    return "\n\n".join(parts)
            
            # Check content blocks
            content = item.get("content") or item.get("contents")
            if isinstance(content, list):
                for cidx, c in enumerate(content):
                    if isinstance(c, dict):
                        t = c.get("type")
                        text = c.get("text")
                        
                        is_reasoning_type = t in {"reasoning", "analysis", "explanation"}
                        has_text = isinstance(text, str) and text.strip()
                        
                        _log_validation_detail("reasoning", f"generic.output[{idx}].content[{cidx}]", is_reasoning_type and has_text, {
                            "type": t,
                            "has_text": has_text,
                            "text_length": len(text) if isinstance(text, str) else 0
                        })
                        
                        if is_reasoning_type and has_text:
                            return text.strip()

    _log_validation_detail("reasoning", "generic.final", False, {"reason": "no reasoning content found"})
    return None


def detect_reasoning(raw_json: Dict[str, Any], provider: Optional[Any] = None) -> bool:
    """
    Detect that provider returned reasoning.
    EXTREME LOGGING: All checks logged.
    """
    LOG.info("=== REASONING DETECTION START ===")
    _save_full_response(raw_json, "reasoning_check")
    
    provider_name = provider.__name__ if provider and hasattr(provider, '__name__') else str(type(provider))
    _log_validation_detail("reasoning", "provider", None, {"provider": provider_name, "has_extract_reasoning": hasattr(provider, "extract_reasoning") if provider else False})
    
    # Try provider-specific extraction
    try:
        if provider is not None and hasattr(provider, "extract_reasoning"):
            r = provider.extract_reasoning(raw_json)
            r_type = type(r).__name__
            r_len = len(r) if isinstance(r, str) else 0
            has_reasoning = isinstance(r, str) and r.strip()
            
            _log_validation_detail("reasoning", "provider.extract_reasoning", has_reasoning, {
                "type": r_type,
                "length": r_len,
                "preview": r[:200] if isinstance(r, str) else None
            })
            
            if has_reasoning:
                LOG.info("=== REASONING DETECTION END: TRUE (provider extractor) ===")
                return True
    except Exception as e:
        _log_validation_detail("reasoning", "provider.extract_reasoning", False, {"error": str(e)})

    # Gemini-specific heuristics
    try:
        cands = raw_json.get("candidates")
        if isinstance(cands, list) and cands:
            gm = cands[0].get("groundingMetadata")
            
            if isinstance(gm, dict):
                wsq = gm.get("webSearchQueries")
                gs = gm.get("groundingSupports")
                sc = gm.get("supportingContent")
                cs = gm.get("confidenceScores")
                
                has_signals = bool(wsq or gs or sc or cs)
                
                _log_validation_detail("reasoning", "gemini.groundingMetadata_as_reasoning", has_signals, {
                    "has_webSearchQueries": bool(wsq),
                    "has_groundingSupports": bool(gs),
                    "has_supportingContent": bool(sc),
                    "has_confidenceScores": bool(cs),
                    "webSearchQueries": wsq,
                    "groundingSupports_count": len(gs) if isinstance(gs, list) else 0,
                    "confidenceScores": cs
                })
                
                if has_signals:
                    LOG.info("=== REASONING DETECTION END: TRUE (Gemini groundingMetadata as reasoning) ===")
                    return True
            
            # Check content parts
            content = cands[0].get("content") or {}
            parts = content.get("parts")
            
            if isinstance(parts, list):
                for pidx, p in enumerate(parts):
                    if isinstance(p, dict):
                        t = p.get("text")
                        has_text = isinstance(t, str) and t.strip()
                        
                        _log_validation_detail("reasoning", f"gemini.content.parts[{pidx}].text", has_text, {
                            "type": type(t).__name__,
                            "length": len(t) if isinstance(t, str) else 0,
                            "preview": t[:200] if isinstance(t, str) else None
                        })
                        
                        if has_text:
                            LOG.info("=== REASONING DETECTION END: TRUE (Gemini content text) ===")
                            return True
    except Exception as e:
        _log_validation_detail("reasoning", "gemini.heuristics", False, {"error": str(e)})

    # Generic extraction
    generic = _extract_reasoning_generic(raw_json)
    has_generic = isinstance(generic, str) and generic.strip() != ""
    
    _log_validation_detail("reasoning", "generic", has_generic, {
        "type": type(generic).__name__,
        "length": len(generic) if isinstance(generic, str) else 0,
        "preview": generic[:200] if isinstance(generic, str) else None
    })
    
    if has_generic:
        LOG.info("=== REASONING DETECTION END: TRUE (generic extraction) ===")
    else:
        LOG.info("=== REASONING DETECTION END: FALSE (no matches) ===")
    
    return has_generic


def assert_grounding_and_reasoning(raw_json: Dict[str, Any], provider: Optional[Any] = None) -> None:
    """
    Assert both grounding and reasoning are present; raise RuntimeError if either is missing.
    EXTREME LOGGING: Full validation summary saved before raising.
    """
    LOG.info("=" * 80)
    LOG.info("VALIDATION CHECKPOINT: assert_grounding_and_reasoning")
    LOG.info("=" * 80)
    
    g = detect_grounding(raw_json)
    r = detect_reasoning(raw_json, provider=provider)
    
    # Log final summary
    validation_summary = {
        "timestamp": datetime.utcnow().isoformat(),
        "run_context": _serialize_for_json(_get_context_as_dict()),
        "grounding_detected": g,
        "reasoning_detected": r,
        "validation_passed": g and r
    }
    
    _log_validation_detail("summary", "final", g and r, validation_summary)
    
    LOG.info("VALIDATION SUMMARY: grounding=%s reasoning=%s PASSED=%s", g, r, g and r)
    print(f"\n{'='*80}\n[VALIDATION SUMMARY] grounding={g} reasoning={r} PASSED={g and r}\n{'='*80}\n", flush=True)
    
    missing = []
    if not g:
        missing.append("grounding (web_search/citations)")
    if not r:
        missing.append("reasoning (thinking/rationale)")
    
    if missing:
        error_msg = "Provider response failed mandatory checks: missing " + " and ".join(missing) + ". Enforcement is strict; no report may be written. See logs for details."
        
        # Save detailed failure report
        log_path = _get_validation_log_path()
        if log_path:
            failure_report_path = log_path.parent / f"{log_path.stem}-FAILURE-REPORT.json"
            try:
                with open(failure_report_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "run_context": _serialize_for_json(_get_context_as_dict()),
                        "validation_summary": validation_summary,
                        "error": error_msg,
                        "missing": missing,
                        "raw_response": raw_json
                    }, f, indent=2, ensure_ascii=False)
                LOG.error("VALIDATION FAILED - Full failure report saved to: %s", failure_report_path)
                print(f"\n[VALIDATION FAILED] Full failure report: {failure_report_path}\n", flush=True)
            except Exception as e:
                LOG.error("Failed to save failure report: %s", e)
        
        LOG.error("VALIDATION FAILED: %s", error_msg)
        # Raise ValidationError with classification info for intelligent retry
        raise ValidationError(error_msg, missing_grounding=not g, missing_reasoning=not r)
    
    LOG.info("VALIDATION PASSED: Both grounding and reasoning detected")
    LOG.info("=" * 80)
