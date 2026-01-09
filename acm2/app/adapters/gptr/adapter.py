import asyncio
import json
import os
import subprocess
import sys
import logging
import threading
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
        self._active_tasks: Dict[str, subprocess.Popen] = {}
        self._cancel_events: Dict[str, threading.Event] = {}

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

    def _run_subprocess_sync(
        self,
        cmd: list[str],
        env: Dict[str, str],
        task_id: str,
        timeout_seconds: int,
        cancel_event: threading.Event,
    ) -> SubprocessResult:
        """
        Synchronous subprocess execution with timeout.
        Runs in a thread via asyncio.to_thread() to avoid event loop issues on Windows.
        """
        process = None
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=False,  # Binary mode for proper decoding
            )
            
            # Track for cancellation
            self._active_tasks[task_id] = process
            
            logger.info(f"GPT-R subprocess started (PID {process.pid}), timeout={timeout_seconds}s ({timeout_seconds // 60}min)")
            
            try:
                stdout_bytes, stderr_bytes = process.communicate(timeout=timeout_seconds)
                
                # Check if cancelled
                if cancel_event.is_set():
                    return SubprocessResult(
                        stdout="",
                        stderr="",
                        return_code=-1,
                        timed_out=False,
                        error="Cancelled"
                    )
                
                stdout_text = stdout_bytes.decode(errors='replace') if stdout_bytes else ""
                stderr_text = stderr_bytes.decode(errors='replace') if stderr_bytes else ""
                
                logger.info(f"GPT-R subprocess completed with return code: {process.returncode}")
                
                return SubprocessResult(
                    stdout=stdout_text,
                    stderr=stderr_text,
                    return_code=process.returncode,
                    timed_out=False
                )
                
            except subprocess.TimeoutExpired:
                logger.warning(f"GPT-R subprocess timed out after {timeout_seconds}s (PID {process.pid}), killing...")
                process.kill()
                stdout_bytes, stderr_bytes = process.communicate(timeout=5)
                stdout_text = stdout_bytes.decode(errors='replace') if stdout_bytes else ""
                stderr_text = stderr_bytes.decode(errors='replace') if stderr_bytes else ""
                
                return SubprocessResult(
                    stdout=stdout_text,
                    stderr=stderr_text,
                    return_code=-1,
                    timed_out=True,
                    error=f"Subprocess timed out after {timeout_seconds // 60} minutes"
                )
                
        except Exception as e:
            logger.exception(f"Error in subprocess execution: {e}")
            
            if process and process.poll() is None:
                try:
                    process.kill()
                    process.wait(timeout=2)
                except Exception:
                    pass
            
            return SubprocessResult(
                stdout="",
                stderr="",
                return_code=-1,
                timed_out=False,
                error=str(e)
            )

    async def _run_subprocess_with_timeout(
        self,
        cmd: list[str],
        env: Dict[str, str],
        task_id: str,
        timeout_seconds: int,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> SubprocessResult:
        """
        Run a subprocess with timeout using asyncio.to_thread().
        This avoids Windows event loop subprocess issues by running in a thread.
        
        Returns SubprocessResult with stdout, stderr, return_code, and timed_out flag.
        On timeout, kills the process and returns timed_out=True.
        """
        cancel_event = threading.Event()
        self._cancel_events[task_id] = cancel_event
        
        try:
            # Run the synchronous subprocess in a thread
            result = await asyncio.to_thread(
                self._run_subprocess_sync,
                cmd,
                env,
                task_id,
                timeout_seconds,
                cancel_event,
            )
            
            # Handle progress callback for stdout lines after completion
            if progress_callback and result.stdout:
                for line in result.stdout.split('\n'):
                    await self._handle_progress_line(line, progress_callback)
            
            return result
            
        except asyncio.CancelledError:
            # Signal the thread to stop
            cancel_event.set()
            raise
        except Exception as e:
            logger.exception(f"Error running subprocess via to_thread: {e}")
            return SubprocessResult(
                stdout="",
                stderr="",
                return_code=-1,
                timed_out=False,
                error=str(e)
            )
        finally:
            self._cancel_events.pop(task_id, None)
            self._active_tasks.pop(task_id, None)

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
        user_id: int,
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
        
        # Inject encrypted provider API keys for this user
        from app.security.key_injection import inject_provider_keys_for_user
        try:
            env = await inject_provider_keys_for_user(user_id, env)
            logger.debug(f"GPT-R: Injected encrypted API keys for user_id={user_id}")
        except Exception as e:
            logger.warning(f"GPT-R: Failed to inject provider keys for user {user_id}: {e}")
        
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
        
        cancelled = False
        for tid in task_ids_to_check:
            # Signal cancel via event
            cancel_event = self._cancel_events.get(tid)
            if cancel_event:
                cancel_event.set()
                cancelled = True
            
            # Kill the subprocess if tracked
            if tid in self._active_tasks:
                process = self._active_tasks[tid]
                try:
                    process.terminate()
                    try:
                        process.wait(timeout=2.0)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=1.0)
                    logger.info(f"Cancelled task {tid}")
                    cancelled = True
                except Exception as e:
                    logger.error(f"Failed to cancel task {tid}: {e}")
        
        return cancelled
