"""
FPF (FilePromptForge) Adapter for ACM2.
"""
import asyncio
import json
import logging
import os
import subprocess
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from ..base import (
    BaseAdapter,
    GenerationConfig,
    GenerationResult,
    GeneratorType,
    ProgressCallback,
    TaskStatus,
)
from .errors import FpfExecutionError, FpfTimeoutError

logger = logging.getLogger(__name__)


class FpfAdapter(BaseAdapter):
    """
    Adapter for FilePromptForge (FPF).

    Uses the existing FilePromptForge CLI tool to run research queries
    and generate reports with web search and reasoning requirements.

    Example:
        adapter = FpfAdapter()
        config = GenerationConfig(provider="openai", model="gpt-5")
        result = await adapter.generate(
            query="What are the latest developments in quantum computing?",
            config=config,
        )
        print(result.content)
        print(f"Cost: ${result.cost_usd:.4f}")
    """

    def __init__(self):
        self._active_tasks: dict[str, asyncio.subprocess.Process] = {}

    @property
    def name(self) -> GeneratorType:
        return GeneratorType.FPF

    @property
    def display_name(self) -> str:
        return "FilePromptForge"

    async def generate(
        self,
        query: str,
        config: GenerationConfig,
        *,
        document_content: Optional[str] = None,
        progress_callback: Optional[ProgressCallback] = None,
        fpf_log_output: str = "console",
        fpf_log_file: Optional[str] = None,
        run_log_file: Optional[str] = None,
    ) -> GenerationResult:
        """
        Run FilePromptForge on a query.

        Args:
            query: The research question/instructions
            config: Generation configuration (model, provider, etc.)
            document_content: Optional document content for file_a
            progress_callback: Optional callback for progress updates
            fpf_log_output: FPF log destination ("console", "file", "both", "none")
            fpf_log_file: Path to FPF log file (required if fpf_log_output includes "file")
            run_log_file: Path to the run's log file for streaming FPF output

        Returns:
            GenerationResult with report, sources, and costs
        """
        extra = config.extra or {}
        missing = [key for key in ("task_id",) if key not in extra]
        if missing:
            raise ValueError(f"FPF config missing required fields: {', '.join(missing)}")

        task_id = str(extra["task_id"])
        started_at = datetime.utcnow()

        # Create temporary files for FPF
        # FPF compose_input expects: file_b (instructions) FIRST, then file_a (document)
        # So: file_a = document content, file_b = instructions/query
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # file_a = document content (appended after instructions in final prompt)
            file_a_path = tmp_path / "content.txt"
            file_a_content = document_content or ""
            file_a_path.write_text(file_a_content, encoding="utf-8")

            # file_b = instructions/query (placed first in final prompt)
            file_b_path = tmp_path / "instructions.txt"
            file_b_path.write_text(query, encoding="utf-8")

            output_path = tmp_path / "output.md"

            # Construct FPF log file path
            fpf_task_log = None
            if run_log_file:
                run_log_path = Path(run_log_file)
                safe_task_id = task_id.replace(":", "_").replace("/", "_").replace("\\", "_")
                logger.info(f"FPF adapter: task_id='{task_id}' safe_task_id='{safe_task_id}'")
                fpf_task_log = run_log_path.parent / f"fpf_{safe_task_id}.log"

            # Build FPF command
            fpf_cmd = self._build_fpf_command(
                file_a=str(file_a_path),
                file_b=str(file_b_path),
                output=str(output_path),
                config=config,
                extra=extra,
                log_file=str(fpf_task_log) if fpf_task_log else None,
            )
            timeout_val = extra.get("timeout")

            # Prepare environment - inherit current env to pass API keys
            env = os.environ.copy()
            
            proc = await asyncio.create_subprocess_exec(
                *fpf_cmd,
                cwd=self._get_fpf_directory(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            self._active_tasks[task_id] = proc

            try:
                if timeout_val:
                    stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout_val)
                else:
                    stdout_bytes, stderr_bytes = await proc.communicate()
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                raise FpfTimeoutError(f"FPF task {task_id} exceeded timeout {timeout_val}s")
            finally:
                self._active_tasks.pop(task_id, None)

            if proc.returncode != 0:
                stdout_str = (stdout_bytes or b"").decode("utf-8", errors="replace")
                stderr_str = (stderr_bytes or b"").decode("utf-8", errors="replace")
                error_msg = stderr_str or stdout_str or f"Return code {proc.returncode}"
                logger.error(f"FPF failed with return code {proc.returncode}: {error_msg}")
                raise FpfExecutionError(f"FPF execution failed: {error_msg}")

            # Parse results
            result_content = output_path.read_text(encoding="utf-8", errors="replace")

            completed_at = datetime.utcnow()
            duration = completed_at - started_at

            return GenerationResult(
                generator=GeneratorType.FPF,
                task_id=task_id,
                content=result_content,
                content_type="markdown",
                model=config.model,
                provider=config.provider,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration.total_seconds(),
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                cost_usd=0.0,
                sources=[],
                metadata={},
                status=TaskStatus.COMPLETED,
            )

    async def cancel(self, task_id: str) -> bool:
        """Cancel a running FPF subprocess."""
        proc = self._active_tasks.get(task_id)
        if not proc:
            return False
        try:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                proc.kill()
            return True
        except Exception as e:
            logger.error(f"Failed to cancel FPF task {task_id}: {e}")
            return False

    def _build_fpf_command(
        self,
        file_a: str,
        file_b: str,
        output: str,
        config: GenerationConfig,
        extra: dict,
        log_file: Optional[str] = None,
    ) -> list[str]:
        """Build the FPF command line arguments."""
        import sys
        
        model = config.model
        provider = config.provider
        
        if ":" in model:
            parts = model.split(":", 1)
            provider = parts[0]
            model = parts[1]
            logger.info(f"FPF adapter: parsed model string -> provider='{provider}', model='{model}'")

        fpf_dir = Path(self._get_fpf_directory())
        config_path = fpf_dir / "fpf_config.yaml"
        env_path = fpf_dir / ".env"

        cmd = [
            sys.executable,  # Use current Python interpreter
            "fpf_main.py",
            "--file-a", file_a,
            "--file-b", file_b,
            "--out", output,
            "--config", str(config_path),
            "--env", str(env_path),
            "--provider", provider,
            "--model", model,
            "--verbose",
        ]

        if extra.get("timeout"):
            cmd.extend(["--timeout", str(extra["timeout"])])

        if log_file:
            cmd.extend(["--log-file", log_file])

        if "reasoning_effort" in extra:
            cmd.extend(["--reasoning-effort", str(extra["reasoning_effort"])])
        if "max_completion_tokens" in extra:
            cmd.extend(["--max-completion-tokens", str(extra["max_completion_tokens"])])
        if extra.get("json_output"):
            cmd.append("--json")

        return cmd

    def _get_fpf_directory(self) -> str:
        """Get the FilePromptForge directory path."""
        # Path: adapter.py -> fpf -> adapters -> app -> acm2 (inner) -> FilePromptForge (sibling)
        current_dir = Path(__file__).resolve().parent
        fpf_dir = current_dir.parent.parent.parent.parent / "FilePromptForge"
        return str(fpf_dir)

    async def health_check(self) -> bool:
        """Check if FPF is available."""
        fpf_dir = self._get_fpf_directory()
        fpf_main = os.path.join(fpf_dir, "fpf_main.py")
        return os.path.exists(fpf_main)