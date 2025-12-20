# Pricing module (FilePromptForge)

Purpose:
- Centralize per-million token pricing (per 1,000,000 tokens) for supported LLM models/providers.
- Serve as a single source of truth for cost calculations across the project.

Planned flow:
1) Fetch pricing via the OpenRouter API (https://openrouter.ai/api/v1/models).
2) Store it locally under this folder (e.g., model_pricing.json).
3) Provide helper utilities to query pricing by provider/model and compute costs.
4) Integrate with cost calculation logic in the app/GUI.

Proposed data schema (JSON example):
- provider: string (e.g., openai, anthropic, google, openrouter)
- model: string (exact model id)
- input_price_per_million_usd: number (USD per 1,000,000 input tokens; stored as-is)
- output_price_per_million_usd: number (USD per 1,000,000 output tokens; stored as-is)
- unit: string ("per_million_tokens") to clarify normalization
- last_updated: ISO date string
- source: string ('openrouter'); source_url: string (https://openrouter.ai/api/v1/models)

Example record:
{
  "provider": "openai",
  "model": "openai/gpt-4o-mini",
  "input_price_per_million_usd": 0.15,
  "output_price_per_million_usd": 0.60,
  "unit": "per_million_tokens",
  "last_updated": "2025-09-19",
  "source": "openrouter",
  "source_url": "https://openrouter.ai/api/v1/models"
}

Files to be added next:
- __init__.py (make package importable)
- schema.json (JSON Schema for validation)
- pricing_index.json (fetched pricing data)
- fetch_pricing.py (script to call OpenRouter API and refresh pricing)
- pricing_loader.py (helpers to load/validate/query pricing)

Notes:
- Store all pricing as USD per 1,000,000 tokens to avoid unit ambiguity.
- Scope: Include only OpenAI and Google Gemini 2.5 models.
- Keep a last_refreshed timestamp and optionally a version/hash for provenance.
- Consider provider-specific nuances (rounded billing increments, context vs. output multipliers) as metadata if needed.
