# ACM2 Backend Log Locations

| Location | Creator | Purpose |
|----------|---------|---------|
| `c:\devlop\acm2\server.log` | `restart.ps1` | uvicorn server stdout/stderr |
| `data/user_{id}/runs/{run_id}/logs/run.log` | `get_run_logger()` in `logging_utils.py` | Per-run orchestration logs |
| `data/user_{id}/runs/{run_id}/logs/fpf_output.log` | `get_fpf_log_path()` in `paths.py` | FPF subprocess output |
| `FilePromptForge/logs/{run_id}/fpf_{doc_id}.fpf.1.{provider}_{model}.log` | FPF subprocess | Per-model call logs with full API payloads |
| `FilePromptForge/logs/{timestamp}-{short_run_id}.json` | FPF subprocess | Consolidated request/response JSON |
| `FilePromptForge/logs/validation/` | `grounding_enforcer.py` | Grounding/reasoning validation results |
| `FilePromptForge/logs/failure-{ts}-google-grounding.json` | `fpf_google_main.py` | Google grounding failure artifacts |
| `FilePromptForge/logs/diag_*.txt` | `memory_dumper.py` | Diagnostic memory dumps |
| `FilePromptForge/logs/heap_*.txt` | `memory_dumper.py` | Heap dumps |
| `FilePromptForge/logs/stack_*.txt` | `memory_dumper.py` | Stack traces |
| `FilePromptForge/logs/calls_{pid}.log` | `memory_dumper.py` | FPF call history |
| `FilePromptForge/logs/fpf_run_{pid}.log` | `fpf_main.py` | FPF process log |
| `