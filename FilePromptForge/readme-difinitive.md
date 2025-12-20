# File Prompt Forge (FPF) — Definitive README

Generated: 2025-09-15

This README is the canonical, comprehensive reference for the File Prompt Forge (FPF) repository. It covers purpose, architecture, configuration, runtime behavior, enforcement policies, developer workflows, troubleshooting, and where to find important artifacts.

## Brief overview
- Purpose: FPF composes prompts from two input files and sends a single non-streaming Responses API request to a configured provider. It is designed to enforce provider-side web-search grounding and to require explicit model reasoning for production runs.
- Scope: OpenAI Responses API only (current code includes an OpenAI provider adapter). Archive examples are retained under `ARCHIVE/` for reference only and are not executed by runtime paths.
- Key policy decisions:
  - Web-search (provider-side grounding) is always enabled for allowed models.
  - Reasoning is always required for allowed models; runs that do not return reasoning or do not invoke web_search will fail and will not produce a human-readable output file.
  - The OpenAI API key is canonical and must live in `filepromptforge/.env`.

## Project layout (important files & directories)
- filepromptforge/
  - fpf_main.py — top-level CLI runner (cwd-independent; canonical run entry).
  - file_handler.py — central router that composes payload, calls provider, saves sidecars, and enforces web_search+reasoning.
  - fpf_config.yaml — runtime configuration (model, provider_url, include fields, web_search tuning).
  - providers/ — provider adapters
    - openai/fpf_openai_main.py — OpenAI Responses adapter (payload builder, parse_response, extract_reasoning, model whitelist & mapping).
  - fpf/ — small helper module (compose_input, load_config, load_env_file) used to avoid circular imports.
  - test/ — sample test inputs & templates used by canonical runs.
  - .env (repo-filepromptforge/.env) — canonical location for OPENAI_API_KEY (must be present).
  - fpf_run.log — rotating run log produced by runner.
  - *.md — audit and capability reports added during refactor:
    - openai_model_capabilities.md
    - websearch_reasoning_audit.md
    - websearch_report.md
    - openai_key_report.md
    - fallback_report.md

## Quick start (local)
1. Ensure Python 3.11+ and a working network connection.
2. Put your OPENAI API key into `filepromptforge/.env` as:
   OPENAI_API_KEY=sk-...
   - This repository enforces using this file as the canonical secret source. Do not set other .env files for production.
3. Edit `filepromptforge/fpf_config.yaml` if needed. For local testing the repository has test paths under `test/`.
4. Run:
   - cd filepromptforge
   - python fpf_main.py --verbose
   The CLI prints the path to the human-readable response on success.

## Configuration (fpf_config.yaml)
- `provider_url` — URL used for the provider (e.g., https://api.openai.com/v1/responses).
- `model` — model ID. This project enforces a model whitelist inside the OpenAI adapter. Confirm model is allowed in `openai_model_capabilities.md`.
- `test.file_a` / `test.file_b` — default input files for canonical runs.
- `prompt_template` — optional path or inline template using `{{file_a}}` and `{{file_b}}`.
- `web_search` (tuning-only) — max_results, search_prompt, etc. Note: the `enable` flag is ignored in production; web_search is enforced in code.
- `include` — fields to request from provider (e.g., `["web_search_call.action.sources"]`).

## Secrets & environment
- OPENAI_API_KEY must be in `filepromptforge/.env`.
- The runner reads only that file for the API key by default (explicit `--env` overrides are intentionally removed in production mode).
- The loader will parse KEY=VALUE lines and explicitly set the process env from the repo .env for determinism.

## How the runtime works (high level)
1. Compose prompt from file_a and file_b using `compose_input`.
2. Provider adapter (`providers/openai/fpf_openai_main.py`) builds the payload:
   - Always attaches a minimal `tools=[{"type":"web_search"}]` block.
   - Performs a per-model mapping to the correct reasoning parameter shape (e.g., `reasoning.effort` for GPT‑5 / O-series).
   - If the configured model is not in the adapter whitelist, the adapter raises an error (fail-fast).
3. `file_handler` sends the single POST and immediately saves a raw JSON sidecar `<out>.fpf.response.txt.raw.json`.
4. Enforcement checks:
   - Validate that provider performed web_search (detect `web_search_call` / `tools` usage).
   - Extract reasoning via `extract_reasoning` and ensure it is present and non-empty.
   - If checks pass: write `<out>.fpf.response.txt.reasoning.txt` and the human-readable response `<out>.fpf.response.txt`.
   - If checks fail: save raw sidecar, log error, and raise runtime error (no human-readable output).
5. Logs and important debug artifacts are written to `fpf_run.log` and `last_payload.json`.

## Confirming reasoning & web_search were used
- The handler already performs checks and writes sidecars. To programmatically confirm:
  - Check raw sidecar for:
    - `reasoning` top-level field or output items with `"type":"reasoning"`.
    - `tools` array includes a `{"type":"web_search"}` entry OR output items of `"type":"web_search_call"`.
    - `usage.output_tokens_details.reasoning_tokens` > 0 (optional metric).
  - The handler writes a `.reasoning.txt` sidecar and logs `"Run validated: web_search used and reasoning present."` on success.

## Developer/maintenance notes
- Provider adapter design:
  - Per-model capability mapping is implemented in `providers/openai/fpf_openai_main.py` — it will map reasoning parameter shapes and enforce the whitelist.
  - Keep the `tools` block minimal by default; add provider-specific fields only via per-model mapping to avoid unknown-parameter errors.
- Logging:
  - The handler saves outbound payload to `last_payload.json` (debug use).
  - HTTP timeout is increased to 120 seconds to accommodate deep reasoning + tool calls.
- Tests:
  - Canonical run: `python fpf_main.py --verbose` (uses test files when `--file-a`/`--file-b` not supplied).
  - After a run, verify `fpf_run.log`, `<out>.raw.json`, and `<out>.reasoning.txt`.

## Troubleshooting (common errors & fixes)
- HTTP 400 unknown parameter (e.g., `tools[0].max_results` or `reasoning.explain`):
  - Cause: provider rejected unsupported field.
  - Fix: remove unknown tool/param or use per-model mapping. The adapter was updated to keep `tools` minimal and perform per-model reasoning mapping.
- Timeout:
  - Deep reasoning + tool workflows can take long. We increased the default timeout to 120s. If runs still time out, check network/proxy, API availability, or reduce reasoning depth.
- No reasoning or web_search present in raw:
  - Provider did not perform tool calls or generate reasoning. Confirm model is reasoning-capable (see `openai_model_capabilities.md`) and that your provider/account supports the web_search tool (provider-side connector may be required).
- API key missing:
  - Ensure `filepromptforge/.env` contains OPENAI_API_KEY; file_handler will refuse to proceed otherwise.

## Security & cost notes
- Reasoning-enabled runs can consume large numbers of tokens. Configure `max_output_tokens` or `tokens` for tests to limit cost.
- Raw sidecars may contain PII from web search or content; handle them per your data governance policy.

## Developer workflow & contribution
- Make small, focused commits. Every change that affects runtime behavior must include:
  - A brief PR description: what changed, why, and the observable effect (logs/artifacts).
  - Run the canonical test locally and attach `fpf_run.log`, the human-readable output, the `.raw.json`, and the `.reasoning.txt` in PR checks.
- For provider updates:
  - Update `providers/openai/fpf_openai_main.py` per-model mapping carefully, and add tests demonstrating the payload shape and handling.

## File index (quick)
- fpf_main.py — CLI runner
- file_handler.py — runtime orchestration & enforcement
- providers/openai/fpf_openai_main.py — provider adapter (payload/parse/extract)
- fpf/fpf_main.py — helpers (compose_input, load_config, load_env_file)
- fpf_config.yaml — runtime config
- .env (filepromptforge/.env) — must contain OPENAI_API_KEY
- test/ — sample inputs
- fpf_run.log — rotating log file
- last_payload.json — last outbound payload (debug)
- *.md — audits & capability reports (openai_model_capabilities.md, websearch_reasoning_audit.md, etc.)

## Next recommended improvements
- Add CI check that runs canonical test with a low-cost reasoning-capable model (or a mock) and verifies presence of `web_search` and `reasoning`.
- Provide an option for a cheaper "test mode" that composes the payload and writes it to disk without performing a network call.
- Add structured verification output (`<out>.verification.json`) summarizing: reasoning_present, reasoning_tokens, web_search_used, run_duration.

If you want, I will:
- Add the verification script `tools/verify_run.py` and a small CI stub.
- Or open the significant files (last_payload.json, raw JSON sidecar, reasoning sidecar) here to review specific content.
