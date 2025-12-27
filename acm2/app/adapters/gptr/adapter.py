import asyncio
import json
import os
import sys
import logging
from typing import AsyncGenerator, Optional, Dict, Any, Tuple
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass

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


@dataclass
class SubprocessResult:
    """Result from running a subprocess with timeout."""
    stdout: str
    stderr: str
    return_code: int
    timed_out: bool = False
    error: Optional[str] = None


class GptrAdapter(BaseAdapter):
    """
    Adapter for GPT-Researcher (gptr).
    Runs gpt-researcher in a subprocess to ensure isolation and stability.
    Supports configurable timeout and retry on timeout.
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

    async def _run_subprocess_with_timeout(
        self,
        cmd: list[str],
        env: Dict[str, str],
        task_id: str,
        timeout_seconds: int,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> SubprocessResult:
        """
        Run a subprocess with timeout, streaming stdout/stderr.
        
        Returns SubprocessResult with stdout, stderr, return_code, and timed_out flag.
        On timeout, kills the process and returns timed_out=True.
        """
        process = None
        stdout_lines = []
        stderr_lines = []
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            self._active_tasks[task_id] = process
            
            async def _read_stdout():
                """Read stdout in chunks to avoid LimitOverrunError on very long lines."""
                buffer = ""
                CHUNK_SIZE = 262144  # 256 KB per read
                while True:
                    try:
                        chunk = await process.stdout.read(CHUNK_SIZE)
                    except Exception:
                        break
                    if not chunk:
                        # Flush remaining buffer
                        if buffer:
                            stdout_lines.append(buffer)
                            await self._handle_progress_line(buffer, progress_callback)
                        break

                    decoded = chunk.decode(errors='replace')
                    buffer += decoded

                    # Split complete lines and keep remainder in buffer
                    *lines, buffer = buffer.split('\n')
                    for decoded_line in lines:
                        stdout_lines.append(decoded_line)
                        await self._handle_progress_line(decoded_line, progress_callback)

            async def _read_stderr():
                """Read stderr line by line."""
                while True:
                    try:
                        line = await process.stderr.readline()
                    except Exception:
                        break
                    if not line:
                        break
                    decoded = line.decode(errors='replace').rstrip('\n')
                    stderr_lines.append(decoded)

            # Create tasks for reading stdout/stderr
            stdout_task = asyncio.create_task(_read_stdout())
            stderr_task = asyncio.create_task(_read_stderr())

            logger.info(f"GPT-R subprocess started (PID {process.pid}), timeout={timeout_seconds}s ({timeout_seconds // 60}min)")
            
            try:
                # Wait for process with timeout
                await asyncio.wait_for(process.wait(), timeout=timeout_seconds)
                
                # Process completed within timeout, wait for read tasks
                await asyncio.wait_for(stdout_task, timeout=5.0)
                await asyncio.wait_for(stderr_task, timeout=5.0)
                
                logger.info(f"GPT-R subprocess completed with return code: {process.returncode}")
                
                return SubprocessResult(
                    stdout='\n'.join(stdout_lines),
                    stderr='\n'.join(stderr_lines),
                    return_code=process.returncode,
                    timed_out=False
                )
                
            except asyncio.TimeoutError:
                # Process timed out - kill it
                logger.warning(f"GPT-R subprocess timed out after {timeout_seconds}s (PID {process.pid}), killing...")
                
                # Cancel read tasks
                stdout_task.cancel()
                stderr_task.cancel()
                
                # Try graceful termination first
                try:
                    process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), timeout=5.0)
                    except asyncio.TimeoutError:
                        # Force kill if termination doesn't work
                        logger.warning(f"GPT-R subprocess did not terminate gracefully, force killing (PID {process.pid})")
                        process.kill()
                        await asyncio.wait_for(process.wait(), timeout=2.0)
                except Exception as kill_err:
                    logger.error(f"Error killing subprocess: {kill_err}")
                
                return SubprocessResult(
                    stdout='\n'.join(stdout_lines),
                    stderr='\n'.join(stderr_lines),
                    return_code=-1,
                    timed_out=True,
                    error=f"Subprocess timed out after {timeout_seconds // 60} minutes"
                )
                
        except Exception as e:
            logger.exception(f"Error in subprocess execution: {e}")
            
            # Attempt to kill process if it exists
            if process and process.returncode is None:
                try:
                    process.kill()
                    await asyncio.wait_for(process.wait(), timeout=2.0)
                except Exception:
                    pass
            
            return SubprocessResult(
                stdout='\n'.join(stdout_lines),
                stderr='\n'.join(stderr_lines),
                return_code=-1,
                timed_out=False,
                error=str(e)
            )
        finally:
            if task_id in self._active_tasks:
                del self._active_tasks[task_id]

    async def _handle_progress_line(self, line: str, progress_callback: Optional[ProgressCallback]) -> None:
        """Parse a line for progress JSON and call progress_callback if applicable."""
        if not progress_callback:
            return
        
        stripped = line.strip()
        if not stripped.startswith('{'):
            return
        
        try:
            data = json.loads(stripped)
            if 'progress' in data or 'stage' in data or 'status' in data:
                progress_val = float(data.get('progress', 0.0) or 0.0)
                stage = data.get('stage') or data.get('status') or 'running'
                message = data.get('message') or None
                if asyncio.iscoroutinefunction(progress_callback):
                    await progress_callback(stage, progress_val, message)
                else:
                    progress_callback(stage, progress_val, message)
        except Exception:
            pass

    async def generate(
        self, 
        query: str,
        config: GenerationConfig, 
        *,
        document_content: Optional[str] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> GenerationResult:
        """
        Run GPT-Researcher generation with timeout and retry support.
        """
        task_id = str(config.extra.get("task_id")) if getattr(config, 'extra', None) and "task_id" in config.extra else ("gptr-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
        started_at = datetime.utcnow()

        # 1. Prepare Configuration
        gptr_config = GptrConfig(**(config.extra or {}))
        
        # Get timeout and retry settings
        timeout_minutes = gptr_config.subprocess_timeout_minutes
        max_retries = gptr_config.subprocess_retries
        timeout_seconds = timeout_minutes * 60
        
        logger.info(f"GPT-R generation starting: task_id={task_id}, timeout={timeout_minutes}min, retries={max_retries}")
        
        # 2. Prepare Environment
        env = os.environ.copy()
        
        # Load API keys from FilePromptForge .env file
        if FPF_ENV_PATH.exists():
            fpf_env = dotenv_values(FPF_ENV_PATH)
            env.update(fpf_env)
            logger.debug(f"GPT-R: Loaded {len(fpf_env)} environment variables from {FPF_ENV_PATH}")
        else:
            logger.warning(f"GPT-R: FilePromptForge .env not found at {FPF_ENV_PATH}")
        
        # Handle Model Selection
        full_model = f"{config.provider}:{config.model}" if config.provider and config.model else config.model
        logger.info(f"GPT-R config: provider={config.provider!r}, model={config.model!r}, full_model={full_model!r}")
        model_str = _map_model_for_gptr(full_model)
        logger.info(f"GPT-R model after mapping: {model_str!r}")
        
        # Set model env vars
        env["SMART_LLM"] = model_str
        env["FAST_LLM"] = model_str
        env["STRATEGIC_LLM"] = model_str

        # Token caps per model to avoid provider max_tokens errors
        MODEL_OUTPUT_LIMITS = {
            "openai:gpt-4.1-mini": 4096,
            "openai:gpt-4-turbo": 4096,
            "openai:gpt-4o": 4096,
            "openai:gpt-5": 8192,
            "openai:gpt-5.1": 8192,
        }
        safe_max_tokens = int(config.max_tokens or 4000)
        provider_limit = MODEL_OUTPUT_LIMITS.get(model_str, 4096)
        max_tokens = min(safe_max_tokens, provider_limit)
        
        env["SMART_LLM_TOKEN_LIMIT"] = str(max_tokens)
        env["FAST_LLM_TOKEN_LIMIT"] = str(max_tokens)
        env["STRATEGIC_LLM_TOKEN_LIMIT"] = str(max_tokens)
        env["SUMMARY_TOKEN_LIMIT"] = str(max(512, min(2048, max_tokens)))
        env["GPTR_TEMPERATURE"] = str(config.temperature)
        
        # Pass run parameters via env vars
        env["GPTR_PROMPT"] = query
        env["GPTR_REPORT_TYPE"] = gptr_config.report_type
        if gptr_config.tone:
            env["GPTR_TONE"] = gptr_config.tone
        if gptr_config.retriever:
            env["RETRIEVER"] = gptr_config.retriever
            env["GPTR_RETRIEVER"] = gptr_config.retriever
        
        if gptr_config.source_urls:
            env["GPTR_SOURCE_URLS"] = json.dumps(gptr_config.source_urls)

        env.update(gptr_config.env_overrides)

        # 3. Run Subprocess with Retry
        cmd = [sys.executable, str(self._entrypoint)]
        
        last_result: Optional[SubprocessResult] = None
        attempt = 0
        
        while attempt <= max_retries:
            attempt += 1
            attempt_task_id = f"{task_id}-attempt{attempt}"
            
            if progress_callback:
                msg = f"Launching GPT-Researcher subprocess (attempt {attempt}/{max_retries + 1})..."
                if asyncio.iscoroutinefunction(progress_callback):
                    await progress_callback("starting", 0.0, msg)
                else:
                    progress_callback("starting", 0.0, msg)
            
            logger.info(f"GPT-R attempt {attempt}/{max_retries + 1} for task {task_id}")
            
            result = await self._run_subprocess_with_timeout(
                cmd=cmd,
                env=env,
                task_id=attempt_task_id,
                timeout_seconds=timeout_seconds,
                progress_callback=progress_callback,
            )
            
            last_result = result
            
            # If timed out and we have retries left, try again
            if result.timed_out and attempt <= max_retries:
                logger.warning(f"GPT-R attempt {attempt} timed out, retrying ({max_retries - attempt + 1} retries left)...")
                if progress_callback:
                    msg = f"Attempt {attempt} timed out, retrying..."
                    if asyncio.iscoroutinefunction(progress_callback):
                        await progress_callback("retrying", 0.0, msg)
                    else:
                        progress_callback("retrying", 0.0, msg)
                continue
            
            # If not timed out (success or error), break out
            if not result.timed_out:
                break
            
            # Final timeout - no more retries
            if result.timed_out:
                logger.error(f"GPT-R all {max_retries + 1} attempts timed out for task {task_id}")
                break
        
        # 4. Process Result
        if last_result is None:
            return GenerationResult(
                generator=GeneratorType.GPTR,
                task_id=task_id,
                content="",
                cost_usd=0.0,
                metadata={},
                status=TaskStatus.FAILED,
                error_message="No subprocess result (unexpected error)",
                started_at=started_at,
                completed_at=datetime.utcnow()
            )
        
        # Handle timeout failure
        if last_result.timed_out:
            if progress_callback:
                if asyncio.iscoroutinefunction(progress_callback):
                    await progress_callback("failed", 1.0, f"Timed out after {timeout_minutes} minutes")
                else:
                    progress_callback("failed", 1.0, f"Timed out after {timeout_minutes} minutes")
            
            return GenerationResult(
                generator=GeneratorType.GPTR,
                task_id=task_id,
                content="",
                cost_usd=0.0,
                metadata={
                    "timeout_minutes": timeout_minutes,
                    "attempts": attempt,
                    "stdout_preview": last_result.stdout[:2000] if last_result.stdout else "",
                    "stderr_preview": last_result.stderr[:2000] if last_result.stderr else "",
                },
                status=TaskStatus.FAILED,
                error_message=f"Subprocess timed out after {timeout_minutes} minutes ({attempt} attempt(s))",
                started_at=started_at,
                completed_at=datetime.utcnow()
            )
        
        # Handle subprocess execution error
        if last_result.error:
            return GenerationResult(
                generator=GeneratorType.GPTR,
                task_id=task_id,
                content="",
                cost_usd=0.0,
                metadata={"error": last_result.error},
                status=TaskStatus.FAILED,
                error_message=f"Subprocess error: {last_result.error}",
                started_at=started_at,
                completed_at=datetime.utcnow()
            )
        
        stdout_str = last_result.stdout.strip()
        stderr_str = last_result.stderr.strip()
        
        # Log output for debugging
        logger.info(f"GPT-R stdout (first 1500 chars): {stdout_str[:1500]}")
        if stderr_str:
            logger.warning(f"GPT-R stderr (first 1500 chars): {stderr_str[:1500]}")
        
        # Handle non-zero exit code
        if last_result.return_code != 0:
            if progress_callback:
                if asyncio.iscoroutinefunction(progress_callback):
                    await progress_callback("failed", 1.0, f"Exit code {last_result.return_code}")
                else:
                    progress_callback("failed", 1.0, f"Exit code {last_result.return_code}")

            return GenerationResult(
                generator=GeneratorType.GPTR,
                task_id=task_id,
                content="",
                cost_usd=0.0,
                metadata={"error": stderr_str, "stdout": stdout_str},
                status=TaskStatus.FAILED,
                error_message=f"Subprocess exited with code {last_result.return_code}: {stderr_str[:500]}",
                started_at=started_at,
                completed_at=datetime.utcnow()
            )

        # 5. Parse JSON Output
        try:
            lines = last_result.stdout.split('\n')
            json_line = ""
            for line in reversed(lines):
                if line.strip().startswith("{"):
                    json_line = line
                    break
            
            if not json_line:
                logger.error(f"No JSON in GPT-R output. Full stdout: {stdout_str}")
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

            if progress_callback:
                if asyncio.iscoroutinefunction(progress_callback):
                    await progress_callback("completed", 1.0, "Research complete")
                else:
                    progress_callback("completed", 1.0, "Research complete")

            return GenerationResult(
                generator=GeneratorType.GPTR,
                task_id=task_id,
                content=data.get("content", ""),
                cost_usd=float(data.get("costs", 0.0) or 0.0),
                metadata={
                    "context": data.get("context"),
                    "visited_urls": data.get("visited_urls"),
                    "report_type": gptr_config.report_type,
                    "attempts": attempt,
                },
                status=TaskStatus.COMPLETED,
                started_at=started_at,
                completed_at=datetime.utcnow()
            )

        except json.JSONDecodeError as e:
            return GenerationResult(
                generator=GeneratorType.GPTR,
                task_id=task_id,
                content="",
                cost_usd=0.0,
                metadata={"stdout": stdout_str, "stderr": stderr_str},
                status=TaskStatus.FAILED,
                error_message=f"Failed to parse GPT-R JSON output: {e}",
                started_at=started_at,
                completed_at=datetime.utcnow()
            )
        except Exception as e:
            logger.exception("GPT-R output parsing error")
            return GenerationResult(
                generator=GeneratorType.GPTR,
                task_id=task_id,
                content="",
                cost_usd=0.0,
                metadata={"stdout": stdout_str, "stderr": stderr_str},
                status=TaskStatus.FAILED,
                error_message=f"Output parsing error: {str(e)}",
                started_at=started_at,
                completed_at=datetime.utcnow()
            )

    async def cancel(self, task_id: str) -> bool:
        """Cancel a running task."""
        # Check for both direct task_id and attempt variants
        task_ids_to_check = [task_id] + [f"{task_id}-attempt{i}" for i in range(1, 5)]
        
        for tid in task_ids_to_check:
            if tid in self._active_tasks:
                process = self._active_tasks[tid]
                try:
                    process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), timeout=2.0)
                    except asyncio.TimeoutError:
                        process.kill()
                    logger.info(f"Cancelled task {tid}")
                    return True
                except Exception as e:
                    logger.error(f"Failed to cancel task {tid}: {e}")
                    return False
        return False
