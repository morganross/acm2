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
        pass

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
        task_id = str(config.extra["task_id"]) if config.extra else str(uuid.uuid4())
        started_at = datetime.utcnow()

        # Create temporary files for FPF
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            file_a_path = tmp_path / "instructions.txt"
            file_a_path.write_text(query, encoding="utf-8")

            file_b_path = tmp_path / "content.txt"
            file_b_content = document_content or ""
            file_b_path.write_text(file_b_content, encoding="utf-8")

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
                log_file=str(fpf_task_log) if fpf_task_log else None
            )

            timeout_val = config.extra["timeout"]

            # Run FPF using subprocess.run - simple and direct
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(
                    fpf_cmd,
                    cwd=self._get_fpf_directory(),
                    timeout=timeout_val,
                    capture_output=True,
                    text=True
                )
            )

            # Check return code
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or f"Return code {result.returncode}"
                logger.error(f"FPF failed with return code {result.returncode}: {error_msg}")
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

    def cancel(self, task_id: str) -> bool:
        """Cancel not supported in simplified version."""
        return False

    def _build_fpf_command(
        self,
        file_a: str,
        file_b: str,
        output: str,
        config: GenerationConfig,
        log_file: Optional[str] = None,
    ) -> list[str]:
        """Build the FPF command line arguments."""
        model = config.model
        provider = config.provider
        
        if ":" in model:
            parts = model.split(":", 1)
            provider = parts[0]
            model = parts[1]
            logger.info(f"FPF adapter: parsed model string -> provider='{provider}', model='{model}'")

        cmd = [
            "python",
            "fpf_main.py",
            "--file-a", file_a,
            "--file-b", file_b,
            "--out", output,
            "--provider", provider,
            "--model", model,
            "--timeout", str(config.extra["timeout"]),
            "--verbose",
        ]

        if log_file:
            cmd.extend(["--log-file", log_file])

        extra = config.extra
        if "reasoning_effort" in extra:
            cmd.extend(["--reasoning-effort", str(extra["reasoning_effort"])])
        if "max_completion_tokens" in extra:
            cmd.extend(["--max-completion-tokens", str(extra["max_completion_tokens"])])
        if extra.get("json_output"):
            cmd.append("--json")

        return cmd

    def _get_fpf_directory(self) -> str:
        """Get the FilePromptForge directory path."""
        current_dir = Path(__file__).resolve().parent
        fpf_dir = current_dir.parent.parent.parent.parent / "FilePromptForge"
        return str(fpf_dir)

    async def health_check(self) -> bool:
        """Check if FPF is available."""
        fpf_dir = self._get_fpf_directory()
        fpf_main = os.path.join(fpf_dir, "fpf_main.py")
        return os.path.exists(fpf_main)