"""
Pricing module for FilePromptForge.

This package will store and expose per-token pricing data for supported LLM
models/providers. It is intended to be the single source of truth for cost
calculations across the project.

Files expected in this package:
- pricing_index.json: The fetched/normalized pricing data (per-token, USD).
- schema.json: JSON Schema for validating pricing_index.json.
- README.md: Overview and maintenance notes.

Modules:
- fetch_pricing.py: Utilities to call OpenRouter API and refresh pricing.
- pricing_loader.py (planned): Load/validate/query pricing utilities.
"""

__version__ = "0.0.1"

# Filenames used within this package
PRICING_FILENAME = "pricing_index.json"
SCHEMA_FILENAME = "schema.json"

__all__ = ["PRICING_FILENAME", "SCHEMA_FILENAME", "__version__"]
