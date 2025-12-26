import asyncio
import json
import os
import sys
import logging
from typing import AsyncGenerator, Optional, Dict, Any
from pathlib import Path
from datetime import datetime

from dotenv import dotenv_values

from app.adapters.base import BaseAdapter, GenerationConfig, GenerationResult, GeneratorType, TaskStatus, ProgressCallback
from app.adapters.gptr.config import GptrConfig

# Path to FilePromptForge .env file containing API keys
FPF_ENV_PATH = Path(__file__).parent.parent.parent.parent.parent / "FilePromptForge" / ".env"

logger = logging.getLogger(__name__)

# Map ACM provider names to GPT-Researcher provider names
GPTR_PROVIDER_MAP = {
    "google": "google_genai",
    "anthropic": "anthropic",
    "openai": "openai",
    "openrouter": "openrouter",
}

def _map_model_for_gptr(model_str: str) -> str:
    """Convert ACM model string (provider:model) to GPT-Researcher format."""
    if ":" not in model_str:
        return model_str
    provider, model = model_str.split(":", 1)
    gptr_provider = GPTR_PROVIDER_MAP.get(provider, provider)
    return f"{gptr_provider}:{model}"

class GptrAdapter(BaseAdapter):
    """
    Adapter for GPT-Researcher (gptr).
    Runs gpt-researcher in a subprocess to ensure isolation and stability.
    """

    def __init__(self):
        self._entrypoint = Path(__file__).parent / "entrypoint.py"
        self._active_tasks: Dict[str, asyncio.subprocess.Process] = {}

    @property
    def name(self) -> GeneratorType:
        return GeneratorType.GPTR

    @property
    def display_name(self) -> str:
        return "GPT-Researcher"

    async def health_check(self) -> bool:
        """Check if gpt-researcher is installed and entrypoint exists."""
        if not self._entrypoint.exists():
            return False
        try:
            # Quick check if we can import it in current env (optional, but good signal)
            import gpt_researcher
            return True
        except ImportError:
            return False

    async def generate(
        self, 
        query: str,
        config: GenerationConfig, 
        *,
        document_content: Optional[str] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> GenerationResult:
        """
        Run GPT-Researcher generation.
        """
        task_id = str(config.extra.get("task_id")) if getattr(config, 'extra', None) and "task_id" in config.extra else ("gptr-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
        started_at = datetime.utcnow()

        # 1. Prepare Configuration
        # config.extra might contain the dict for GptrConfig
        gptr_config = GptrConfig(**(config.extra or {}))
        
        # 2. Prepare Environment
        env = os.environ.copy()
        
        # Load API keys from FilePromptForge .env file (same source FPF uses)
        if FPF_ENV_PATH.exists():
            fpf_env = dotenv_values(FPF_ENV_PATH)
            env.update(fpf_env)
            logger.debug(f"GPT-R: Loaded {len(fpf_env)} environment variables from {FPF_ENV_PATH}")
        else:
            logger.warning(f"GPT-R: FilePromptForge .env not found at {FPF_ENV_PATH}")
        
        # Handle Model Selection
        # GPT-R relies heavily on env vars for model selection
        # We map our standardized model name to what GPT-R expects
        
        # Build full model string from provider and model
        full_model = f"{config.provider}:{config.model}" if config.provider and config.model else config.model
        logger.info(f"GPT-R config: provider={config.provider!r}, model={config.model!r}, full_model={full_model!r}")
        model_str = _map_model_for_gptr(full_model)
        logger.info(f"GPT-R model after mapping: {model_str!r}")
        
        # For now, we pass the model directly to SMART_LLM/FAST_LLM
        # This overrides config.py in GPT-R if set
        env["SMART_LLM"] = model_str
        env["FAST_LLM"] = model_str
        env["STRATEGIC_LLM"] = model_str
        
        # Pass run parameters via env vars to entrypoint
        env["GPTR_PROMPT"] = query
        env["GPTR_REPORT_TYPE"] = gptr_config.report_type
        if gptr_config.tone:
            env["GPTR_TONE"] = gptr_config.tone
        if gptr_config.retriever:
            env["RETRIEVER"] = gptr_config.retriever # GPT-R uses RETRIEVER env var
            env["GPTR_RETRIEVER"] = gptr_config.retriever # For our entrypoint explicit arg
        
        if gptr_config.source_urls:
            env["GPTR_SOURCE_URLS"] = json.dumps(gptr_config.source_urls)

        # Apply explicit env overrides from config
        env.update(gptr_config.env_overrides)

        # 3. Run Subprocess
        cmd = [sys.executable, str(self._entrypoint)]
        
        if progress_callback:
            if asyncio.iscoroutinefunction(progress_callback):
                await progress_callback("starting", 0.0, "Launching GPT-Researcher subprocess...")
            else:
                progress_callback("starting", 0.0, "Launching GPT-Researcher subprocess...")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            self._active_tasks[task_id] = process

            # Stream stdout line-by-line and call progress_callback for JSON progress messages
            stdout_lines = []
            stderr_lines = []

            async def _read_stdout():
                while True:
                    line = await process.stdout.readline()
                    if not line:
                        break
                    decoded = line.decode(errors='replace').rstrip('\n')
                    stdout_lines.append(decoded)
                    # attempt to parse JSON progress
                    stripped = decoded.strip()
                    if stripped.startswith('{') and progress_callback:
                        try:
                            data = json.loads(stripped)
                            # if contains explicit progress keys
                            if 'progress' in data or 'stage' in data or 'status' in data:
                                progress_val = float(data.get('progress', 0.0) or 0.0)
                                stage = data.get('stage') or data.get('status') or 'running'
                                message = data.get('message') or None
                                if asyncio.iscoroutinefunction(progress_callback):
                                    await progress_callback(stage, progress_val, message)
                                else:
                                    progress_callback(stage, progress_val, message)
                        except Exception:
                            # Not a progress JSON or parse failed
                            pass

            async def _read_stderr():
                while True:
                    line = await process.stderr.readline()
                    if not line:
                        break
                    decoded = line.decode(errors='replace').rstrip('\n')
                    stderr_lines.append(decoded)

            stdout_task = asyncio.create_task(_read_stdout())
            stderr_task = asyncio.create_task(_read_stderr())

            # Wait for process to exit and for read tasks to complete
            logger.info(f"GPT-R subprocess started, waiting for completion...")
            await process.wait()
            await stdout_task
            await stderr_task
            
            logger.info(f"GPT-R subprocess completed with return code: {process.returncode}")

            stdout = '\n'.join(stdout_lines)
            stderr = '\n'.join(stderr_lines)
            
            stdout_str = stdout.strip()
            stderr_str = stderr.strip()
            
            # Log output regardless of return code for debugging
            logger.info(f"GPT-R stdout ({len(stdout_lines)} lines, first 1500 chars): {stdout_str[:1500]}")
            if stderr_str:
                logger.warning(f"GPT-R stderr: {stderr_str[:1500]}")

            if process.returncode != 0:
                if progress_callback:
                    if asyncio.iscoroutinefunction(progress_callback):
                        await progress_callback("completed", 1.0, "Completed")
                    else:
                        progress_callback("completed", 1.0, "Completed")

                return GenerationResult(
                    generator=GeneratorType.GPTR,
                    task_id=task_id,
                    content="",
                    cost_usd=0.0,
                    metadata={"error": stderr_str, "stdout": stdout_str},
                    status=TaskStatus.FAILED,
                    error_message=f"Subprocess exited with code {process.returncode}: {stderr_str}",
                    started_at=started_at,
                    completed_at=datetime.utcnow()
                )

            # 4. Parse Output
            # We expect the last line of stdout to be the JSON result
            try:
                # Find the last line that looks like JSON
                lines = stdout.split('\n')
                logger.info(f"GPT-R stdout lines count: {len(lines)}")
                logger.info(f"GPT-R stdout (first 1000 chars): {stdout[:1000]}")
                logger.info(f"GPT-R stderr (first 1000 chars): {stderr_str[:1000] if stderr_str else '(empty)'}")
                json_line = ""
                for line in reversed(lines):
                    if line.strip().startswith("{"):
                        json_line = line
                        break
                
                if not json_line:
                     # Fallback: sometimes GPT-R prints logs after JSON?
                     # Or maybe it failed silently but printed something else
                     logger.error(f"No JSON in GPT-R output. Full stdout: {stdout}")
                     raise ValueError("No JSON output found in subprocess stdout")

                data = json.loads(json_line)
                
                if data.get("status") == "failed":
                    return GenerationResult(
                        generator=GeneratorType.GPTR,
                        task_id=task_id,
                        content="",
                        cost_usd=0.0,
                        metadata={"traceback": data.get("traceback")},
                        status=TaskStatus.FAILED,
                        error_message=data.get("error", "Unknown error in GPT-R"),
                        started_at=started_at,
                        completed_at=datetime.utcnow()
                    )

                return GenerationResult(
                    generator=GeneratorType.GPTR,
                    task_id=task_id,
                    content=data.get("content", ""),
                    cost_usd=float(data.get("costs", 0.0) or 0.0),
                    metadata={
                        "context": data.get("context"),
                        "visited_urls": data.get("visited_urls"),
                        "report_type": gptr_config.report_type
                    },
                    status=TaskStatus.COMPLETED,
                    started_at=started_at,
                    completed_at=datetime.utcnow()
                )

            except json.JSONDecodeError:
                return GenerationResult(
                    generator=GeneratorType.GPTR,
                    task_id=task_id,
                    content="",
                    cost_usd=0.0,
                    metadata={"stdout": stdout_str, "stderr": stderr_str},
                    status=TaskStatus.FAILED,
                    error_message="Failed to parse GPT-R JSON output",
                    started_at=started_at,
                    completed_at=datetime.utcnow()
                )

        except Exception as e:
            logger.exception("GPT-R Adapter execution error")
            return GenerationResult(
                generator=GeneratorType.GPTR,
                task_id=task_id,
                content="",
                cost_usd=0.0,
                metadata={},
                status=TaskStatus.FAILED,
                error_message=f"Adapter execution error: {str(e)}",
                started_at=started_at,
                completed_at=datetime.utcnow()
            )
        finally:
            if task_id in self._active_tasks:
                del self._active_tasks[task_id]

    async def cancel(self, task_id: str) -> bool:
        """Cancel a running task."""
        if task_id in self._active_tasks:
            process = self._active_tasks[task_id]
            try:
                process.terminate()
                # Give it a moment to terminate gracefully
                try:
                    await asyncio.wait_for(process.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    process.kill()
                return True
            except Exception as e:
                logger.error(f"Failed to cancel task {task_id}: {e}")
                return False
        return False