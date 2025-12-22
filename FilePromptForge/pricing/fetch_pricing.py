"""
Fetch and normalize model pricing from the OpenRouter API.

This script retrieves model metadata (including pricing) from:
  https://openrouter.ai/api/v1/models

It stores prices as USD per 1,000,000 tokens (per-million) for both input (prompt)
and output (completion), without converting to per-token. If only per-1k pricing
is provided, it is scaled by 1,000 to produce per-million.

Scope filtering:
- Only include OpenAI models (provider == "openai")
- Only include Google Gemini 2.5 models (provider == "google" and model id startswith "google/gemini-2.5")

Writes the result to pricing_index.json in this package.

Environment variables:
- OPENROUTER_API_KEY (optional): If set, sent as Authorization: Bearer <key>.
- PRICING_OUTPUT_PATH (optional): If set, path where pricing_index.json will be written.

Usage:
- As a module:
    python -m API_Cost_Multiplier.filepromptforge.pricing.fetch_pricing

- As a script:
    python API_Cost_Multiplier/filepromptforge/pricing/fetch_pricing.py
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


def fetch_openrouter_models(api_key: Optional[str] = None, timeout: Optional[int] = None) -> Dict[str, Any]:
    headers: Dict[str, str] = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    resp = requests.get(OPENROUTER_MODELS_URL, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _to_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return None


def _include_model(provider: str, model_id: str) -> bool:
    if provider == "openai":
        return True
    if provider == "google" and model_id.startswith("google/gemini-2.5"):
        return True
    return False


def normalize_model_entry(entry: Dict[str, Any], as_of: str) -> Optional[Dict[str, Any]]:
    # Identify model id and provider
    model_id = entry.get("id") or entry.get("name") or entry.get("model")
    if not model_id:
        return None

    provider = model_id.split("/")[0] if "/" in model_id else "openrouter"

    if not _include_model(provider, model_id):
        return None

    pricing = entry.get("pricing") or {}

    # Per OpenRouter common fields: 'prompt' and 'completion' are USD per 1M tokens
    input_per_million = _to_float(pricing.get("prompt"))
    if input_per_million is not None:
        # OpenRouter 'prompt' is USD per token; convert to per 1M tokens
        input_per_million = input_per_million * 1_000_000.0
    output_per_million = _to_float(pricing.get("completion"))
    if output_per_million is not None:
        # OpenRouter 'completion' is USD per token; convert to per 1M tokens
        output_per_million = output_per_million * 1_000_000.0

    # Fallbacks: some providers expose per-1k token fields; scale to per-million
    if input_per_million is None and pricing.get("input_per_1k") is not None:
        v = _to_float(pricing.get("input_per_1k"))
        input_per_million = v * 1000.0 if v is not None else None
    if output_per_million is None and pricing.get("output_per_1k") is not None:
        v = _to_float(pricing.get("output_per_1k"))
        output_per_million = v * 1000.0 if v is not None else None

    # If no pricing is available, skip entry
    if input_per_million is None and output_per_million is None:
        return None

    # Best-effort context length discovery from various possible fields
    context_length = (
        entry.get("context_length")
        or (entry.get("top_provider") or {}).get("context_length")
        or (entry.get("architecture") or {}).get("context_length")
    )

    return {
        "provider": provider,
        "model": model_id,
        "input_price_per_million_usd": input_per_million,
        "output_price_per_million_usd": output_per_million,
        "unit": "per_million_tokens",
        "last_updated": as_of,
        "source": "openrouter",
        "source_url": OPENROUTER_MODELS_URL,
        "metadata": {
            "context_length": context_length,
            "raw_pricing": pricing,
        },
    }


def normalize_openrouter_response(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    # OpenRouter often returns {"data": [ ...models... ]}
    models = data.get("data") if isinstance(data, dict) else None
    if models is None:
        # Try alternative keys or assume the data is the list
        models = data.get("models") if isinstance(data, dict) else data

    if isinstance(models, dict):
        models = models.get("data")  # nested 'data'

    if not isinstance(models, list):
        return []

    as_of = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d")
    out: List[Dict[str, Any]] = []
    for entry in models:
        norm = normalize_model_entry(entry, as_of)
        if norm:
            out.append(norm)
    return out


def write_pricing_index(
    pricing: List[Dict[str, Any]], output_path: Optional[Path] = None
) -> Path:
    if output_path is None:
        output_path = Path(__file__).parent / "pricing_index.json"
    tmp = output_path.with_suffix(".json.tmp")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tmp.open("w", encoding="utf-8") as f:
        json.dump(pricing, f, indent=2)

    tmp.replace(output_path)
    return output_path


def refresh_pricing(
    api_key: Optional[str] = None, timeout: int = 30, output_path: Optional[str] = None
) -> Path:
    data = fetch_openrouter_models(api_key=api_key, timeout=timeout)
    normalized = normalize_openrouter_response(data)
    path = write_pricing_index(normalized, Path(output_path) if output_path else None)
    return path


def main() -> None:
    api_key = os.getenv("OPENROUTER_API_KEY")
    out = os.getenv("PRICING_OUTPUT_PATH")  # optional override

    try:
        path = refresh_pricing(api_key=api_key, output_path=out)
        print(f"Wrote pricing_index.json to {path}")
    except requests.HTTPError as e:
        # Bubble up for calling process to handle, but print for convenience
        print(f"HTTP error fetching OpenRouter models: {e}", flush=True)
        raise
    except Exception as e:
        print(f"Unexpected error: {e}", flush=True)
        raise


if __name__ == "__main__":
    main()
