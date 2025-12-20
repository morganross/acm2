"""
FPF (FilePromptForge) Adapter for ACM2.

This adapter wraps the FilePromptForge CLI tool to provide:
- Standardized interface matching other generators
- Cost tracking and token counting
- Progress callbacks for UI updates
- Cancellation support
"""
import asyncio
import json
import logging
import os
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
from .subprocess import run_fpf_subprocess

logger = logging.getLogger(__name__)

# Model mapping for FPF provider whitelists.
# Maps commonly-requested models to their whitelisted equivalents.
# Adapter-level fallback so we don't have to modify FilePromptForge itself.
# NOTE: o3/o3-mini require special API access - do NOT map standard models to them.
# Most users should pass models directly without remapping.
FPF_MODEL_MAP: dict[str, str] = {
    # Only add mappings if FPF has strict model whitelists
    # For now, pass through all models as-is
}


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
        self._active_tasks: dict[str, Any] = {}  # task_id -> subprocess
        self._cancelled: set[str] = set()

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
        task_id = str(config.extra.get("task_id")) if config.extra and "task_id" in config.extra else str(uuid.uuid4())
        started_at = datetime.utcnow()
        start_time = time.time()

        try:
            # Create temporary files for FPF
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)

                # Create file_a (instructions/prompt) - use query as instructions
                file_a_path = tmp_path / "instructions.txt"
                file_a_path.write_text(query, encoding="utf-8")

                # Create file_b (content) - use document_content if provided, otherwise empty
                file_b_path = tmp_path / "content.txt"
                file_b_content = document_content or ""
                file_b_path.write_text(file_b_content, encoding="utf-8")

                # Set up output path
                output_path = tmp_path / "output.md"

                if progress_callback:
                    await self._safe_callback(progress_callback, "preparing", 0.0, "Setting up FPF execution...")

                # Build FPF command
                fpf_cmd = self._build_fpf_command(
                    file_a=str(file_a_path),
                    file_b=str(file_b_path),
                    output=str(output_path),
                    config=config,
                )

                if progress_callback:
                    await self._safe_callback(progress_callback, "running", 0.1, "Executing FPF research...")

                # Run FPF using subprocess utility
                # Build progress callback wrapper which ensures safe invocation
                cb = None
                if progress_callback:
                    async def cb(stage: str, progress: float, message: Optional[str]):
                        await self._safe_callback(progress_callback, stage, progress, message)

                returncode, stdout, stderr = await run_fpf_subprocess(
                    fpf_cmd,
                    self._get_fpf_directory(),
                    timeout=float(config.extra.get("timeout", 600)) if config.extra else 600.0,  # Use timeout from config, no fallback to 24hr
                    progress_callback=cb,
                    fpf_log_output=fpf_log_output,
                    fpf_log_file=fpf_log_file,
                    run_log_file=run_log_file,
                )

                # Check return code
                if returncode != 0:
                    error_msg = stderr or stdout or "Unknown error"
                    logger.error(f"FPF failed with return code {returncode}: {error_msg}")
                    raise FpfExecutionError(f"FPF execution failed: {error_msg}")

                if progress_callback:
                    await self._safe_callback(progress_callback, "parsing", 0.9, "Parsing FPF results...")

                # Parse results
                result_content = ""
                if output_path.exists():
                    result_content = output_path.read_text(encoding="utf-8", errors="replace")

                # Try to find and parse the raw JSON for cost/metadata
                cost_usd, metadata = self._parse_fpf_costs(tmp_path)

                # Extract sources from content (FPF includes citations)
                sources = self._extract_sources_from_content(result_content)

                completed_at = datetime.utcnow()
                duration = completed_at - started_at

                if progress_callback:
                    await self._safe_callback(progress_callback, "completed", 1.0, "FPF research completed")

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
                    input_tokens=0,  # FPF doesn't provide token counts
                    output_tokens=0,
                    total_tokens=0,
                    cost_usd=cost_usd,
                    sources=sources,
                    metadata=metadata,
                    status=TaskStatus.COMPLETED,
                )

        except Exception as e:
            # Re-raise the exception so _generate_single can handle it properly
            # and return None (marking the generation as failed)
            logger.exception(f"FPF generation failed for task {task_id}")
            raise

    def cancel(self, task_id: str) -> bool:
        """Cancel a running FPF task."""
        if task_id in self._active_tasks:
            process = self._active_tasks[task_id]
            if process.returncode is None:
                process.terminate()
                self._cancelled.add(task_id)
                return True
        return False

    def _build_fpf_command(
        self,
        file_a: str,
        file_b: str,
        output: str,
        config: GenerationConfig,
    ) -> list[str]:
        """Build the FPF command line arguments."""
        # Parse model string which may include provider prefix (e.g., "google:gemini-2.5-flash")
        model = config.model
        provider = config.provider
        
        # Check if model string contains provider prefix (e.g., "openai:gpt-5" or "google:gemini-2.5-flash")
        if ":" in model:
            parts = model.split(":", 1)
            provider = parts[0]
            model = parts[1]
            logger.info(f"FPF adapter: parsed model string -> provider='{provider}', model='{model}'")
        
        # Map model to FPF-whitelisted equivalent if needed
        if model in FPF_MODEL_MAP:
            mapped_model = FPF_MODEL_MAP[model]
            logger.info(f"FPF adapter: mapping model '{model}' -> '{mapped_model}'")
            model = mapped_model

        cmd = [
            "python",
            "fpf_main.py",
            "--file-a", file_a,
            "--file-b", file_b,
            "--out", output,
            "--provider", provider,
            "--model", model,
        ]

        # Add extra config options
        extra = config.extra or {}

        if "reasoning_effort" in extra:
            cmd.extend(["--reasoning-effort", str(extra["reasoning_effort"])])

        if "max_completion_tokens" in extra:
            cmd.extend(["--max-completion-tokens", str(extra["max_completion_tokens"])])

        if "timeout" in extra:
            cmd.extend(["--timeout", str(extra["timeout"])])

        # Add JSON output flag (for evaluations that return small JSON responses)
        if extra.get("json_output"):
            cmd.append("--json")

        # Add verbose logging
        cmd.append("--verbose")

        return cmd

    def _get_fpf_directory(self) -> str:
        """Get the FilePromptForge directory path."""
        # Navigate from acm2/app/adapters/fpf/ to FilePromptForge/
        # acm2/ is at api_cost_multiplier/acm2/, FilePromptForge is at api_cost_multiplier/FilePromptForge/
        current_dir = Path(__file__).resolve().parent
        fpf_dir = current_dir.parent.parent.parent.parent / "FilePromptForge"
        return str(fpf_dir)

    def _parse_fpf_costs(self, tmp_dir: Path) -> tuple[float, dict[str, Any]]:
        """Parse FPF cost data from raw JSON files."""
        cost_usd = 0.0
        metadata = {}

        try:
            # Look for .raw.json files in the temp directory
            for json_file in tmp_dir.glob("*.raw.json"):
                with open(json_file, 'r', encoding='utf-8') as f:
                    raw_data = json.load(f)

                # Extract cost information (FPF doesn't provide structured cost data)
                # We'll estimate based on model and approximate usage
                if "usage" in raw_data:
                    usage = raw_data["usage"]
                    # FPF uses OpenAI-style pricing, estimate costs
                    cost_usd += self._estimate_cost(raw_data.get("model", ""), usage)

                metadata["raw_response"] = raw_data

        except Exception as e:
            logger.warning(f"Failed to parse FPF costs: {e}")

        return cost_usd, metadata

    def _estimate_cost(self, model: str, usage: dict) -> float:
        """Estimate cost based on model and usage."""
        # Simple cost estimation - in production, use actual pricing data
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)

        # Rough pricing per 1K tokens (update with actual rates)
        pricing = {
            "gpt-5": {"input": 0.005, "output": 0.015},
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
        }

        model_key = model.lower().replace("-turbo", "").replace("-preview", "")
        rates = pricing.get(model_key, pricing["gpt-5"])

        cost = (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1000
        return cost

    def _extract_sources_from_content(self, content: str) -> list[dict[str, Any]]:
        """Extract sources/citations from FPF content."""
        sources = []

        # FPF typically includes citations in the content
        # Look for common citation patterns
        import re

        # Find URLs
        url_pattern = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
        urls = re.findall(url_pattern, content)

        for url in urls:
            sources.append({
                "url": url,
                "title": f"Source from {url[:50]}...",
                "snippet": "",
            })

        return sources

    async def _safe_callback(
        self, 
        callback: ProgressCallback, 
        stage: str, 
        progress: float, 
        message: Optional[str]
    ) -> None:
        """Safely invoke progress callback."""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(stage, progress, message)
            else:
                callback(stage, progress, message)
        except Exception as e:
            logger.warning(f"Progress callback failed: {e}")

    async def health_check(self) -> bool:
        """
        Check if FPF is properly configured and available.
        
        Returns:
            True if FPF can be used
        """
        try:
            # Check if FPF directory exists
            fpf_dir = self._get_fpf_directory()
            if not os.path.exists(fpf_dir):
                logger.warning(f"FPF directory not found: {fpf_dir}")
                return False
            
            # Check if fpf_main.py exists
            fpf_main = os.path.join(fpf_dir, "fpf_main.py")
            if not os.path.exists(fpf_main):
                logger.warning(f"FPF main script not found: {fpf_main}")
                return False
            
            # Check if .env file exists
            env_file = os.path.join(fpf_dir, ".env")
            if not os.path.exists(env_file):
                logger.warning(f"FPF .env file not found: {env_file}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"FPF health check failed: {e}")
            return False