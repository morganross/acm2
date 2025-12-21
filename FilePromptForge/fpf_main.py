"""
FPF top-level runner script.

Run this from the repository like:

  cd filepromptforge
  python fpf_main.py --help

Notes / guarantees implemented:
- Works when invoked from any working directory. The script resolves the package root
  (the directory containing this file) and inserts its parent into sys.path so that
  imports like `filepromptforge.file_handler` succeed regardless of cwd.
- Sets up logging to console and to a rotating log file located next to this script
  (fpf_run.log). All important steps are logged.
- Resolves relative paths against the repository package dir when the path is not
  found in the caller's cwd. This allows config or input files to be referenced
  relative to the package directory.
- Delegates the heavy work to filepromptforge.file_handler.run(...)
"""

from __future__ import annotations
import argparse
import logging
import logging.handlers
import sys
import os
from pathlib import Path
from typing import Optional

# Ensure imports find the package when called from other directories.
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR
# Add the parent of the package to sys.path so `import filepromptforge.*` works.
if str(PROJECT_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT.parent))

from file_handler import run as run_handler  # use local module in same directory

try:
    from .helpers import load_config, load_env_file
except ImportError:
    from helpers import load_config, load_env_file  # type: ignore

# Use PID in log filename to prevent contention on Windows during concurrent runs
LOG_FILENAME = SCRIPT_DIR / "logs" / f"fpf_run_{os.getpid()}.log"
# Ensure logs directory exists so the rotating file handler can write there
if not LOG_FILENAME.parent.exists():
    LOG_FILENAME.parent.mkdir(parents=True, exist_ok=True)


import yaml
import json


def setup_logging(level: int = logging.INFO) -> None:
    logger = logging.getLogger()
    logger.setLevel(level)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch_formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    ch.setFormatter(ch_formatter)

    # File handler (rotating)
    fh = logging.handlers.RotatingFileHandler(
        filename=str(LOG_FILENAME),
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    fh.setLevel(level)
    fh_formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    fh.setFormatter(fh_formatter)

    # Avoid duplicate handlers if setup_logging called multiple times
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        logger.addHandler(ch)
    if not any(isinstance(h, logging.handlers.RotatingFileHandler) for h in logger.handlers):
        logger.addHandler(fh)

def resolve_path_candidate(candidate: Optional[str]) -> Optional[str]:
    """
    Resolve a possibly relative path.

    Order:
    1. If candidate is None -> return None
    2. If absolute -> return if exists, else still return absolute (let downstream error)
    3. If relative and exists relative to cwd -> return that
    4. If relative and exists relative to PROJECT_ROOT -> return PROJECT_ROOT / candidate
    5. Otherwise return candidate unchanged (downstream will error)
    """
    if not candidate:
        return None
    p = Path(candidate)
    if p.is_absolute():
        return str(p)
    # exists relative to cwd
    cwd_try = Path.cwd() / candidate
    if cwd_try.exists():
        return str(cwd_try)
    pkg_try = PROJECT_ROOT / candidate
    if pkg_try.exists():
        return str(pkg_try)
    # fallback - not found in cwd or package. Log and return None so caller can fail fast.
    import logging
    logging.getLogger("fpf_main").error("Path not found in cwd or package: %s", candidate)
    return None

def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def main(argv: Optional[list[str]] = None) -> int:
    setup_logging(logging.INFO)
    log = logging.getLogger("fpf_main")
    parser = argparse.ArgumentParser(prog="fpf_main", description="File Prompt Forge runner")
    parser.add_argument("--file-a", help="First input file (left side).", dest="file_a")
    parser.add_argument("--file-b", help="Second input file (right side).", dest="file_b")
    parser.add_argument("--out", help="Output path for human-readable response", dest="out")
    parser.add_argument("--config", help="Path to fpf_config.yaml", dest="config")
    parser.add_argument("--env", help="Path to .env (optional). Defaults to package .env", dest="env")
    parser.add_argument("--provider", help="Override provider", dest="provider")
    parser.add_argument("--model", help="Override model id", dest="model")
    parser.add_argument("--reasoning-effort", help="Override reasoning effort", dest="reasoning_effort")
    parser.add_argument("--max-completion-tokens", help="Override max completion tokens", dest="max_completion_tokens", type=int)
    parser.add_argument("--timeout", help="Override request timeout in seconds", dest="timeout", type=int)
    parser.add_argument("--max-concurrency", help="Override global max concurrency for batch mode", dest="max_concurrency", type=int)
    parser.add_argument("--runs-stdin", action="store_true", help="Read JSON array of runs from stdin and execute as a batch")
    parser.add_argument("--batch-output", choices=["lines", "json"], default="lines", help="Batch output format: 'lines' (one path per success) or 'json' (results array)")
    parser.add_argument("--json", action="store_true", help="Enable JSON output mode (bypasses minimum content size check)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    args = parser.parse_args(argv)
    try:
        # Early stderr debug to ensure visibility even if logging handlers are odd
        print(f"[FPF DEBUG] argv parsed: runs_stdin={getattr(args, 'runs_stdin', False)} batch_output={getattr(args, 'batch_output', 'lines')} config={args.config} env={args.env}", file=sys.stderr, flush=True)
    except Exception:
        pass

    if args.verbose:
        setup_logging(logging.DEBUG)
        log.setLevel(logging.DEBUG)
        log.debug("Verbose logging enabled")

    log.info("Starting FPF runner")
    log.debug("Script dir: %s", SCRIPT_DIR)
    
    config_path = resolve_path_candidate(args.config) or str(PROJECT_ROOT / "fpf_config.yaml")
    cfg = load_config(config_path)

    # stdin batch mode: if --runs-stdin is set, read a JSON array of runs from stdin and schedule via scheduler
    if getattr(args, "runs_stdin", False):
        # Determine env path (prefer CLI, then default to package .env)
        env = resolve_path_candidate(args.env) or str(PROJECT_ROOT / ".env")
        # Concurrency config (optional)
        conc_cfg = (cfg or {}).get("concurrency") or {}
        try:
            if getattr(args, "max_concurrency", None) is not None:
                conc_cfg["max_concurrency"] = int(args.max_concurrency)
        except Exception:
            pass
        # Read stdin JSON
        try:
            print("[FPF DEBUG] runs-stdin: reading stdin...", file=sys.stderr, flush=True)
            data = sys.stdin.read()
            print(f"[FPF DEBUG] runs-stdin: read {len(data or '')} bytes", file=sys.stderr, flush=True)
            runs_from_stdin = json.loads(data) if data and data.strip() else []
            if not isinstance(runs_from_stdin, list):
                raise ValueError("runs-stdin JSON must be an array")
            print(f"[FPF DEBUG] runs-stdin: parsed {len(runs_from_stdin)} run(s)", file=sys.stderr, flush=True)
        except Exception as exc:
            print(f"FPF batch stdin parse failed: {exc}", file=sys.stderr)
            return 2
        # Import scheduler and execute
        try:
            from .scheduler import run_many as scheduler_run_many  # type: ignore
        except Exception:
            from scheduler import run_many as scheduler_run_many  # type: ignore
        print("[FPF DEBUG] runs-stdin: scheduling runs...", file=sys.stderr, flush=True)
        try:
            os.environ["FPF_SCHEDULER"] = "1"
        except Exception:
            pass
        results = scheduler_run_many(runs_from_stdin, config_path=config_path, env_path=env, concurrency_cfg=conc_cfg)
        print(f"[FPF DEBUG] runs-stdin: scheduler returned {len(results)} result(s)", file=sys.stderr, flush=True)
        successes = [r for r in results if r.get("path")]
        failures = [r for r in results if not r.get("path")]
        # Output format
        if getattr(args, "batch_output", "lines") == "json":
            try:
                print(json.dumps(results, ensure_ascii=False))
            except Exception:
                # Fallback to minimal JSON if unexpected types appear
                safe = []
                for r in results:
                    safe.append({
                        "id": r.get("id"),
                        "provider": r.get("provider"),
                        "model": r.get("model"),
                        "path": r.get("path"),
                        "error": r.get("error"),
                    })
                print(json.dumps(safe, ensure_ascii=False))
        else:
            for r in successes:
                try:
                    print(r.get("path"))
                except Exception:
                    pass
        # Log a brief summary (goes to rotating log)
        log.info("Batch (stdin) complete: %s succeeded, %s failed", len(successes), len(failures))
        print(f"[FPF DEBUG] runs-stdin: finished, successes={len(successes)} failures={len(failures)}", file=sys.stderr, flush=True)
        # Exit: success if at least one run succeeded, else non-zero
        return 0 if successes else 2

    # Batch mode: if runs present and concurrency.enabled, schedule via scheduler
    try:
        runs_cfg = (cfg or {}).get("runs")
        conc_cfg = (cfg or {}).get("concurrency") or {}
    except Exception:
        runs_cfg = None
        conc_cfg = {}
    if runs_cfg and conc_cfg.get("enabled"):
        # Determine env path (prefer CLI, then default to package .env)
        env = resolve_path_candidate(args.env) or str(PROJECT_ROOT / ".env")
        # Optional override from CLI
        try:
            if getattr(args, "max_concurrency", None) is not None:
                conc_cfg["max_concurrency"] = int(args.max_concurrency)
        except Exception:
            pass
        # Import scheduler and execute
        try:
            from .scheduler import run_many as scheduler_run_many  # type: ignore
        except Exception:
            from scheduler import run_many as scheduler_run_many  # type: ignore
        try:
            os.environ["FPF_SCHEDULER"] = "1"
        except Exception:
            pass
        results = scheduler_run_many(runs_cfg, config_path=config_path, env_path=env, concurrency_cfg=conc_cfg)
        successes = [r for r in results if r.get("path")]
        failures = [r for r in results if not r.get("path")]
        # Print each successful output path one per line (CLI contract)
        for r in successes:
            try:
                print(r.get("path"))
            except Exception:
                pass
        # Log a brief summary
        log.info("Batch complete: %s succeeded, %s failed", len(successes), len(failures))
        # Exit: success if at least one run succeeded, else non-zero
        return 0 if successes else 2

    file_a_path = args.file_a or cfg.get("test", {}).get("file_a")
    file_b_path = args.file_b or cfg.get("test", {}).get("file_b")
    out_path = args.out or cfg.get("test", {}).get("out")

    file_a = resolve_path_candidate(file_a_path)
    if not file_a:
        raise FileNotFoundError(f"Input file not found: {file_a_path}")
    file_b = resolve_path_candidate(file_b_path)
    if not file_b:
        raise FileNotFoundError(f"Input file not found: {file_b_path}")

    config = config_path
    env = resolve_path_candidate(args.env) or str(PROJECT_ROOT / ".env")

    # Resolve output path: if not absolute, make it relative to the project root.
    if out_path and not Path(out_path).is_absolute():
        out = str(PROJECT_ROOT / out_path)
    else:
        out = out_path

    model = args.model
    reasoning_effort = args.reasoning_effort
    max_completion_tokens = args.max_completion_tokens
    timeout = args.timeout
    provider = args.provider
    request_json = args.json

    log.debug("Resolved paths - file_a=%s, file_b=%s, config=%s, env=%s, out=%s, provider=%s, model=%s, json=%s, timeout=%s",
              file_a, file_b, config, env, out, provider, model, request_json, timeout)

    try:
        result_path = run_handler(
            file_a=file_a,
            file_b=file_b,
            out_path=out,
            config_path=config,
            env_path=env,
            provider=provider,
            model=model,
            reasoning_effort=reasoning_effort,
            max_completion_tokens=max_completion_tokens,
            timeout=timeout,
            request_json=request_json,
        )
        log.info("Run completed. Output written to %s", result_path)
        print(result_path)
        return 0
    except Exception as exc:
        log.exception("FPF run failed: %s", exc)
        # Emit a uniform RUN_COMPLETE failure record for single-run mode
        try:
            prov = (args.provider or cfg.get("provider") or "na")
            model = (args.model or cfg.get("model") or "na")
            _prov_norm = str(prov).strip().lower()
            _model_norm = str(model).strip().lower()
            kind = "deep" if (_prov_norm == "openaidp" or ("deep-research" in _model_norm)) else "rest"
            # id is unknown at this layer; elapsed/status may be unknown; include out if resolved
            log.info(
                "[FPF RUN_COMPLETE] id=%s kind=%s provider=%s model=%s ok=false elapsed=%s status=%s path=%s error=%s",
                "na", kind, prov, model, "na", "na", (out or "na"), str(exc)
            )
        except Exception:
            pass
        print(f"FPF run failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
