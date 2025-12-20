"""
Utilities for loading pricing data and computing run costs.

Pricing data format:
- Stored as USD per 1,000,000 tokens (per-million) for input (prompt) and output (completion).
- Each record:
    {
      "provider": "openai",
      "model": "openai/gpt-4o-mini",
      "input_price_per_million_usd": 0.15,
      "output_price_per_million_usd": 0.60,
      "unit": "per_million_tokens",
      "last_updated": "YYYY-MM-DD",
      "source": "openrouter",
      "source_url": "https://openrouter.ai/api/v1/models",
      ...
    }
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_pricing_index(path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Load the pricing index JSON file.

    Args:
        path: Optional path to pricing_index.json. If not provided, caller should
              pass an absolute path.

    Returns:
        List of pricing records (possibly empty).
    """
    if not path:
        return []
    p = Path(path)
    if not p.exists():
        return []
    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        return []
    return []


def find_pricing(pricing_list: List[Dict[str, Any]], model_slug: str) -> Optional[Dict[str, Any]]:
    """
    Find a pricing record by exact model slug match.

    Args:
        pricing_list: List of pricing records loaded from pricing_index.json
        model_slug: Model identifier (e.g., 'openai/gpt-4o-mini', 'google/gemini-2.5-pro')

    Returns:
        The pricing record dict if found, else None.
    """
    if not model_slug:
        return None
    for rec in pricing_list:
        if isinstance(rec, dict) and rec.get("model") == model_slug:
            return rec
    return None


def _round6(x: float) -> float:
    try:
        return round(float(x), 6)
    except Exception:
        return 0.0


def calc_cost(tokens_in: int, tokens_out: int, record: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute cost in USD using per-million token pricing.

    Args:
        tokens_in: Number of input (prompt) tokens
        tokens_out: Number of output (completion) tokens
        record: Pricing record dict (or None if not found)

    Returns:
        Dict containing breakdown and total cost:
        {
          "input_price_per_million_usd": float | None,
          "output_price_per_million_usd": float | None,
          "input_tokens": int,
          "output_tokens": int,
          "input_cost_usd": float | None,
          "output_cost_usd": float | None,
          "total_cost_usd": float | None,
          "pricing_last_updated": str | None,
          "pricing_source": str | None,
          "pricing_source_url": str | None,
          "unit": "per_million_tokens" | None,
          "reason": str | None
        }
    """
    tokens_in = int(tokens_in or 0)
    tokens_out = int(tokens_out or 0)

    if not record or not isinstance(record, dict):
        return {
            "input_price_per_million_usd": None,
            "output_price_per_million_usd": None,
            "input_tokens": tokens_in,
            "output_tokens": tokens_out,
            "input_cost_usd": None,
            "output_cost_usd": None,
            "total_cost_usd": None,
            "pricing_last_updated": None,
            "pricing_source": None,
            "pricing_source_url": None,
            "unit": None,
            "reason": "pricing_not_found",
        }

    inp_price = record.get("input_price_per_million_usd")
    out_price = record.get("output_price_per_million_usd")

    # Treat missing price as 0, but keep None in the output fields to indicate missing
    input_cost = None
    output_cost = None
    total_cost = None

    if isinstance(inp_price, (int, float)):
        input_cost = (tokens_in / 1_000_000.0) * float(inp_price)
    if isinstance(out_price, (int, float)):
        output_cost = (tokens_out / 1_000_000.0) * float(out_price)

    if input_cost is not None or output_cost is not None:
        total_cost = (input_cost or 0.0) + (output_cost or 0.0)

    return {
        "input_price_per_million_usd": inp_price if isinstance(inp_price, (int, float)) else None,
        "output_price_per_million_usd": out_price if isinstance(out_price, (int, float)) else None,
        "input_tokens": tokens_in,
        "output_tokens": tokens_out,
        "input_cost_usd": _round6(input_cost) if input_cost is not None else None,
        "output_cost_usd": _round6(output_cost) if output_cost is not None else None,
        "total_cost_usd": _round6(total_cost) if total_cost is not None else None,
        "pricing_last_updated": record.get("last_updated"),
        "pricing_source": record.get("source"),
        "pricing_source_url": record.get("source_url"),
        "unit": record.get("unit"),
        "reason": None,
    }
