"""
FPF (FilePromptForge) Adapter for ACM2.
"""
import asyncio
import json
import logging
import os
import subprocess
import tempfile
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

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
        self._active_tasks: Dict[str, subprocess.Popen] = {}
        self._cancel_events: Dict[str, threading.Event] = {}

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
            
            # Set FPF log environment variables so FPF writes structured JSON logs
            run_id = extra.get("run_id")
            if run_id:
                env["FPF_RUN_GROUP_ID"] = run_id
                # Point FPF logs to ACM2's logs directory  
                logs_dir = Path("logs") / run_id
                logs_dir.mkdir(parents=True, exist_ok=True)
                env["FPF_LOG_DIR"] = str(logs_dir.resolve())
            
            fpf_cwd = self._get_fpf_directory()
            actual_timeout = timeout_val if timeout_val else 1200  # 20 min default
            
            # Create cancel event for this task
            cancel_event = threading.Event()
            self._cancel_events[task_id] = cancel_event
            
            try:
                # Run subprocess in thread to avoid Windows event loop issues
                result = await asyncio.to_thread(
                    self._run_subprocess_sync,
                    fpf_cmd,
                    env,
                    fpf_cwd,
                    task_id,
                    actual_timeout,
                    cancel_event,
                )
            finally:
                self._cancel_events.pop(task_id, None)
                self._active_tasks.pop(task_id, None)
            
            if result.get("cancelled"):
                raise FpfExecutionError(f"FPF task {task_id} was cancelled")
            
            if result.get("timed_out"):
                raise FpfTimeoutError(f"FPF task {task_id} exceeded timeout {actual_timeout}s")
            
            if result["return_code"] != 0:
                error_msg = result["stderr"] or result["stdout"] or f"Return code {result['return_code']}"
                logger.error(f"FPF failed with return code {result['return_code']}: {error_msg}")
                raise FpfExecutionError(f"FPF execution failed: {error_msg}")

            # Parse results
            result_content = output_path.read_text(encoding="utf-8", errors="replace")

            completed_at = datetime.utcnow()
            duration = completed_at - started_at
            
            # Try to extract cost and token info from FPF's JSON log
            input_tokens = 0
            output_tokens = 0
            total_tokens = 0
            cost_usd = 0.0
            
            if run_id:
                cost_info = self._parse_fpf_cost_log(run_id)
                if cost_info:
                    input_tokens = cost_info.get("input_tokens", 0)
                    output_tokens = cost_info.get("output_tokens", 0)
                    total_tokens = cost_info.get("total_tokens", 0)
                    cost_usd = cost_info.get("cost_usd", 0.0)
                    logger.info(f"FPF cost for {task_id}: ${cost_usd:.6f} ({total_tokens} tokens)")

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
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost_usd=cost_usd,
                sources=[],
                metadata={},
                status=TaskStatus.COMPLETED,
            )

    async def cancel(self, task_id: str) -> bool:
        """Cancel a running FPF subprocess."""
        # Signal cancel via event
        cancel_event = self._cancel_events.get(task_id)
        if cancel_event:
            cancel_event.set()
        
        # Kill the subprocess if tracked
        proc = self._active_tasks.get(task_id)
        if proc:
            try:
                proc.terminate()
                # Give it a moment to terminate
                try:
                    proc.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=1.0)
                logger.info(f"Cancelled FPF task {task_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to cancel FPF task {task_id}: {e}")
                return False
        
        # If we only had the cancel event, that's still a success
        return cancel_event is not None
    
    def _run_subprocess_sync(
        self,
        cmd: list[str],
        env: Dict[str, str],
        cwd: str,
        task_id: str,
        timeout_seconds: int,
        cancel_event: threading.Event,
    ) -> Dict[str, Any]:
        """
        Synchronous subprocess execution with timeout.
        Runs in a thread via asyncio.to_thread() to avoid event loop issues on Windows.
        """
        process = None
        try:
            process = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=False,
            )
            
            # Track for cancellation
            self._active_tasks[task_id] = process
            
            logger.info(f"FPF subprocess started (PID {process.pid}), timeout={timeout_seconds}s ({timeout_seconds // 60}min)")
            
            try:
                stdout_bytes, stderr_bytes = process.communicate(timeout=timeout_seconds)
                
                if cancel_event.is_set():
                    return {"cancelled": True, "stdout": "", "stderr": "", "return_code": -1}
                
                stdout_text = stdout_bytes.decode(errors='replace') if stdout_bytes else ""
                stderr_text = stderr_bytes.decode(errors='replace') if stderr_bytes else ""
                
                logger.info(f"FPF subprocess completed with return code: {process.returncode}")
                
                return {
                    "stdout": stdout_text,
                    "stderr": stderr_text,
                    "return_code": process.returncode,
                    "timed_out": False,
                    "cancelled": False,
                }
                
            except subprocess.TimeoutExpired:
                logger.warning(f"FPF subprocess timed out after {timeout_seconds}s (PID {process.pid}), killing...")
                process.kill()
                stdout_bytes, stderr_bytes = process.communicate(timeout=5)
                stdout_text = stdout_bytes.decode(errors='replace') if stdout_bytes else ""
                stderr_text = stderr_bytes.decode(errors='replace') if stderr_bytes else ""
                
                return {
                    "stdout": stdout_text,
                    "stderr": stderr_text,
                    "return_code": -1,
                    "timed_out": True,
                    "cancelled": False,
                }
                
        except Exception as e:
            logger.exception(f"Error in FPF subprocess execution: {e}")
            
            if process and process.poll() is None:
                try:
                    process.kill()
                    process.wait(timeout=2)
                except Exception:
                    pass
            
            return {
                "stdout": "",
                "stderr": "",
                "return_code": -1,
                "timed_out": False,
                "cancelled": False,
                "error": str(e),
            }

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
        
        # Only parse provider:model format if provider is not already set
        # This avoids double-parsing models like "meta-llama/llama-3.1-405b:free"
        # which have a colon for the :free suffix, not provider:model format
        if not provider and ":" in model:
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
        
        # FPF retry settings
        if "fpf_max_retries" in extra:
            cmd.extend(["--fpf-max-retries", str(extra["fpf_max_retries"])])
        if "fpf_retry_delay" in extra:
            cmd.extend(["--fpf-retry-delay", str(extra["fpf_retry_delay"])])

        return cmd

    def _parse_fpf_cost_log(self, run_id: str) -> dict | None:
        """Parse FPF's JSON log file to extract cost and token usage.
        
        FPF writes logs to logs/{run_group_id}/YYYYMMDDTHHMMSS-{run_id}.json
        with fields: total_cost_usd, usage.prompt_tokens, usage.completion_tokens
        """
        import json
        import glob
        
        try:
            logs_dir = Path("logs") / run_id
            if not logs_dir.exists():
                logger.debug(f"FPF logs dir not found: {logs_dir}")
                return None
            
            # Find the most recent JSON log file
            log_files = list(logs_dir.glob("*.json"))
            if not log_files:
                logger.debug(f"No JSON logs found in {logs_dir}")
                return None
            
            # Sort by modification time, get newest
            log_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            newest_log = log_files[0]
            
            logger.debug(f"Parsing FPF cost log: {newest_log}")
            
            with open(newest_log, "r", encoding="utf-8") as f:
                log_data = json.load(f)
            
            # Extract cost and token info
            cost_usd = log_data.get("total_cost_usd", 0.0)
            usage = log_data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            total_tokens = input_tokens + output_tokens
            
            return {
                "cost_usd": cost_usd,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
            }
            
        except Exception as e:
            logger.warning(f"Failed to parse FPF cost log for run {run_id}: {e}")
            return None

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