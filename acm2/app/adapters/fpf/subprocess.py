"""
Subprocess utilities for FPF execution with real-time output streaming.
"""
import asyncio
import logging
import os
import json
import subprocess
import sys
import threading
import time
import contextvars
from pathlib import Path
from typing import List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Thread pool for running subprocesses on Windows
_executor = ThreadPoolExecutor(max_workers=4)


def _run_subprocess_streaming(
    cmd: List[str],
    cwd: str,
    env: dict,
    timeout: float,
    log_file: Optional[str] = None,
    heartbeat_interval: float = 30.0,
    idle_no_output_kill: Optional[float] = 180.0,
) -> tuple[int, str, str]:
    """
    Synchronous subprocess execution with real-time output streaming.
    
    Streams stdout/stderr to the logger and optionally to a log file.
    Logs heartbeats every heartbeat_interval seconds while waiting.
    """
    stdout_lines = []
    stderr_lines = []
    start_time = time.time()
    last_heartbeat = start_time
    last_output = start_time
    
    # Open log file if specified
    log_fh = None
    if log_file:
        try:
            log_fh = open(log_file, 'a', encoding='utf-8')
        except Exception as e:
            logger.warning(f"Could not open FPF log file {log_file}: {e}")
    
    def write_log(line: str, prefix: str = "FPF", update_idle: bool = True):
        """Write to both logger and log file."""
        log_line = f"[{prefix}] {line}"
        logger.info(log_line)
        if log_fh:
            try:
                log_fh.write(f"{log_line}\n")
                log_fh.flush()
            except Exception:
                pass
        # Track last time we saw output for idle detection
        if update_idle:
            nonlocal last_output
            last_output = time.time()
    
    try:
        # Use Popen for real-time streaming
        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf-8',
            errors='replace',
            bufsize=1,  # Line buffered
        )
        
        # Capture current context to propagate to threads
        ctx = contextvars.copy_context()
        ctx_stdout = ctx.copy()
        ctx_stderr = ctx.copy()

        # Read stdout and stderr in separate threads
        def read_stdout():
            ctx_stdout.run(_read_stdout_impl)

        def _read_stdout_impl():
            nonlocal last_heartbeat
            try:
                for line in iter(process.stdout.readline, ''):
                    if line:
                        line = line.rstrip('\n\r')
                        stdout_lines.append(line)
                        write_log(line, "FPF")
                        last_heartbeat = time.time()
            except Exception as e:
                write_log(f"Error reading stdout: {e}", "ACM ERR")
            finally:
                try:
                    process.stdout.close()
                except Exception:
                    pass
        
        def read_stderr():
            ctx_stderr.run(_read_stderr_impl)

        def _read_stderr_impl():
            nonlocal last_heartbeat
            try:
                for line in iter(process.stderr.readline, ''):
                    if line:
                        line = line.rstrip('\n\r')
                        stderr_lines.append(line)
                        write_log(line, "FPF ERR")
                        last_heartbeat = time.time()
            except Exception as e:
                write_log(f"Error reading stderr: {e}", "ACM ERR")
            finally:
                try:
                    process.stderr.close()
                except Exception:
                    pass
        
        stdout_thread = threading.Thread(target=read_stdout, daemon=True)
        stderr_thread = threading.Thread(target=read_stderr, daemon=True)
        stdout_thread.start()
        stderr_thread.start()
        
        # Wait for process with timeout and heartbeats
        deadline = time.time() + timeout
        write_log(f"Subprocess started. PID: {process.pid}, Timeout: {timeout}s, Deadline: {deadline}", "ACM")

        while process.poll() is None:
            now = time.time()
            
            # Check timeout
            if now > deadline:
                write_log(f"TIMEOUT REACHED. Killing process {process.pid}...", "ACM")
                process.kill()
                process.wait()
                write_log(f"Process {process.pid} killed due to timeout.", "ACM")
                if log_fh:
                    log_fh.close()
                return -1, '\n'.join(stdout_lines), "Process timed out"

            # Kill if no stdout/stderr seen for an extended period (prevents heartbeat-only hangs)
            if idle_no_output_kill and (now - last_output) >= idle_no_output_kill:
                write_log(f"IDLE TIMEOUT. No output for {int(idle_no_output_kill)}s. Killing process {process.pid}...", "ACM")
                process.kill()
                process.wait()
                write_log(
                    f"Terminated due to no output for {int(idle_no_output_kill)}s",
                    "ACM",
                )
                if log_fh:
                    log_fh.close()
                return -2, '\n'.join(stdout_lines), f"No output for {int(idle_no_output_kill)}s"
            
            # Log heartbeat if needed
            if now - last_heartbeat >= heartbeat_interval:
                elapsed = int(now - start_time)
                write_log(f"Heartbeat: FPF subprocess {process.pid} running for {elapsed}s... (start={start_time} now={now})", "ACM", update_idle=False)
                last_heartbeat = now
            
            # Sleep briefly to avoid busy waiting
            time.sleep(0.1)
        
        write_log(f"Process {process.pid} exited naturally. Return code: {process.returncode}", "ACM")

        # Wait for threads to finish
        stdout_thread.join(timeout=5)
        stderr_thread.join(timeout=5)
        
        elapsed = int(time.time() - start_time)
        write_log(f"FPF subprocess completed in {elapsed}s with return code {process.returncode}", "ACM")
        
        if log_fh:
            log_fh.close()
        
        return process.returncode, '\n'.join(stdout_lines), '\n'.join(stderr_lines)
        
    except Exception as e:
        # Include stdout/stderr snippets for diagnostics
        try:
            stdout_snip = '\n'.join(stdout_lines[-200:])
            stderr_snip = '\n'.join(stderr_lines[-200:])
        except Exception:
            stdout_snip = ''
            stderr_snip = ''
        logger.exception(f"Subprocess error: {e}\nSTDOUT_SNIPPET:\n{stdout_snip}\nSTDERR_SNIPPET:\n{stderr_snip}")
        if log_fh:
            try:
                log_fh.close()
            except Exception:
                logger.debug("Failed to close FPF log file handle", exc_info=True)
        return -1, '\n'.join(stdout_lines), str(e)


def _run_subprocess_sync(
    cmd: List[str],
    cwd: str,
    env: dict,
    timeout: float,
) -> tuple[int, str, str]:
    """Legacy synchronous subprocess execution for Windows compatibility."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Process timed out"
    except Exception as e:
        return -1, "", str(e)


async def run_fpf_subprocess(
    cmd: List[str],
    cwd: str,
    timeout: float,  # REQUIRED - no default, caller must specify (FPF controls actual timeout)
    env: Optional[dict] = None,
    progress_callback: Optional[Callable[[str, float, Optional[str]], None]] = None,
    fpf_log_output: str = "console",
    fpf_log_file: Optional[str] = None,
    run_log_file: Optional[str] = None,
    idle_no_output_kill: Optional[float] = 180.0,
) -> tuple[int, str, str]:
    """
    Run FPF as a subprocess with real-time output streaming.

    Args:
        cmd: Command to run
        cwd: Working directory
        timeout: Safety ceiling timeout in seconds (FPF handles actual timeout internally)
        env: Environment variables
        fpf_log_output: FPF log output mode ("console", "file", "both", "none")
        fpf_log_file: Path to FPF log file (required if fpf_log_output includes "file")
        run_log_file: Path to the run's log file for real-time output

    Returns:
        Tuple of (returncode, stdout, stderr)
    """
    # Set up environment
    process_env = os.environ.copy()
    if env:
        process_env.update(env)

    # Configure FPF logging via environment variables
    process_env["FPF_LOG_OUTPUT"] = fpf_log_output
    if fpf_log_file:
        process_env["FPF_LOG_FILE"] = fpf_log_file
    
    # Force unbuffered output from Python subprocesses
    process_env["PYTHONUNBUFFERED"] = "1"

    # Ensure FPF can find its .env file
    fpf_env_path = Path(cwd) / ".env"
    if fpf_env_path.exists():
        process_env["FPF_ENV_FILE"] = str(fpf_env_path)

    logger.info(f"Running FPF command: {' '.join(cmd)}")
    logger.info(f"FPF working directory: {cwd}")
    logger.debug(f"FPF run params: timeout={timeout} fpf_log_output={fpf_log_output} fpf_log_file={fpf_log_file} run_log_file={run_log_file}")

    # Log presence of common provider secrets (redacted) for diagnostics
    try:
        openai_present = bool(process_env.get('OPENAI_API_KEY') or process_env.get('OPENAI_KEY'))
        google_present = bool(process_env.get('GOOGLE_API_KEY') or process_env.get('GOOGLE_API_KEY_JSON'))
        logger.debug(f"FPF env secrets present: OPENAI={openai_present} GOOGLE={google_present}")
    except Exception:
        logger.debug("Failed to inspect FPF env for secret presence", exc_info=True)

    # Use streaming subprocess for real-time output
    loop = asyncio.get_event_loop()
    returncode, stdout, stderr = await loop.run_in_executor(
        _executor,
        _run_subprocess_streaming,
        cmd,
        cwd,
        process_env,
        timeout,
        run_log_file,
        30.0,  # heartbeat interval
        idle_no_output_kill,
    )
    return returncode, stdout, stderr