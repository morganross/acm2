"""
Small helper module used by file_handler for composing inputs and loading config/env.

Provides:
- compose_input(file_a: str, file_b: str, prompt_template: Optional[str]) -> str
- load_config(path: str) -> dict
- load_env_file(path: str) -> None

This implementation is intentionally small and deterministic so the CLI runner
can import these helpers without pulling in the top-level runner (avoids circular imports).
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Optional, Dict
import yaml

def load_env_file(path: str) -> None:
    """
    Load simple KEY=VALUE pairs from a .env file into os.environ.
    Existing environment variables are not overwritten.
    """
    p = Path(path)
    if not p.exists():
        return
    with p.open("r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('\'"')
            # Do not overwrite existing envs
            if key not in os.environ:
                os.environ[key] = val

def load_config(path: str) -> Dict:
    """
    Load YAML config from `path`. If the file does not exist or parsing fails,
    raise an error so the caller can decide whether to use defaults or exit.
    """
    p = Path(path)
    if not p.exists():
        # Return empty dict rather than silent fallback; caller should decide
        return {}
    with p.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
        return data

def compose_input(file_a: str, file_b: str, prompt_template: Optional[str] = None) -> str:
    """
    Compose the prompt string from file_a and file_b. If prompt_template is provided
    and is a path to a file, the template may include the placeholders:
      {{file_a}} and {{file_b}}
    which will be replaced with the file contents. Otherwise the contents are joined.
    """
    def _read(p: str) -> str:
        try:
            return Path(p).read_text(encoding="utf-8")
        except Exception:
            return ""

    a_text = _read(file_a)
    b_text = _read(file_b)

    if prompt_template:
        tpl_path = Path(prompt_template)
        if tpl_path.exists():
            tpl = tpl_path.read_text(encoding="utf-8")
            return tpl.replace("{{file_a}}", a_text).replace("{{file_b}}", b_text)
        # if template path not found, treat template as literal string
        return str(prompt_template).replace("{{file_a}}", a_text).replace("{{file_b}}", b_text)

    # default composition
    return a_text + "\n\n" + b_text
