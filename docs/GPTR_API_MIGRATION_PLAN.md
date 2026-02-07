# GPT-Researcher Migration Plan: Subprocess → HTTP API

**Document Version**: 1.0  
**Date**: February 6, 2026  
**Status**: PLANNING  
**Estimated Effort**: 2-3 days  

---

## Executive Summary

This document outlines the plan to migrate ACM2's GPT-Researcher integration from a subprocess-based approach to using GPT-Researcher's native HTTP API (FastAPI server).

**Current State**: 665 lines of subprocess management code  
**Target State**: ~50 lines of HTTP client code + separate GPTR service  
**RAM Savings**: ~500 MB per concurrent job → 500 MB total (shared)

---

## Part 1: Why We Chose Subprocess (And Why It Was Right)

### 1.1 The Original Problem

When GPT-Researcher was first integrated into ACM2, there were legitimate technical challenges:

| Challenge | Why Subprocess Solved It |
|-----------|-------------------------|
| **Windows Event Loop Conflicts** | asyncio on Windows + subprocess I/O has quirks. Running GPTR in a separate process avoids event loop pollution. |
| **Timeout Enforcement** | Python's `asyncio.wait_for()` doesn't guarantee cancellation. `process.kill()` is absolute. |
| **Crash Isolation** | If GPTR crashes, hangs, or runs out of memory, the subprocess dies but ACM2 survives. |
| **Memory Cleanup** | When a subprocess exits, the OS reclaims ALL its memory. No leaks accumulate. |
| **Environment Isolation** | Each job gets a clean `os.environ` without polluting the main process. |
| **Dependency Conflicts** | GPTR's 200+ dependencies could conflict with ACM2's. Subprocess isolation prevents this. |

### 1.2 What Subprocess Cost Us

| Cost | Impact |
|------|--------|
| **~500 MB RAM per job** | New Python interpreter loads all GPTR dependencies |
| **3-10 second startup** | Process spawn + Python init + import time |
| **665 lines of code** | Subprocess management, JSON parsing, retry logic, timeout threading |
| **Complex debugging** | Errors come as JSON strings, stack traces in stdout |
| **JSON protocol** | Had to build our own communication layer |

### 1.3 The Verdict

**Subprocess was the right choice at the time.** It provided stability and isolation when we didn't know if GPTR would play nicely with our event loop. But now that GPTR has a mature HTTP API, we can get the same isolation with far less complexity.

---

## Part 2: Why HTTP API Is Better Now

### 2.1 What GPTR's HTTP API Provides

GPT-Researcher ships with a full FastAPI server (`main.py`):

```bash
# From their repo
python -m uvicorn main:app --reload
# Runs on localhost:8000
```

This gives us:
- `/research` endpoint for running queries
- Built-in request/response handling
- Their team maintains it
- Clean HTTP interface

### 2.2 Comparison

| Aspect | Subprocess (Current) | HTTP API (Target) |
|--------|----------------------|-------------------|
| Lines of code in ACM2 | 665 | ~50 |
| RAM per job | +500 MB | +0 (shared service) |
| Isolation | ✅ Full | ✅ Full (separate process) |
| Timeout control | ✅ `process.kill()` | ✅ HTTP timeout + service restart |
| Startup time | 3-10 seconds | 0 (service already running) |
| Crash recovery | Manual retry | Service auto-restart (systemd) |
| Debugging | Parse JSON from stdout | HTTP errors, service logs |
| Maintenance | We maintain wrapper | They maintain API |

---

## Part 3: Implementation Plan

### Phase 1: Preparation (Day 1 Morning)

#### 1.1 Set Up GPTR as Standalone Service

Create a systemd unit file for GPTR:

```ini
# /etc/systemd/system/gptr.service
[Unit]
Description=GPT-Researcher API Server
After=network.target

[Service]
Type=simple
User=acm2
WorkingDirectory=/opt/gptr
ExecStart=/opt/gptr/venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8001
Environment="OPENAI_API_KEY=..."
Environment="TAVILY_API_KEY=..."
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

#### 1.2 Create Configuration

Add to ACM2's `.env`:

```dotenv
GPTR_API_URL=http://127.0.0.1:8001
GPTR_TIMEOUT_SECONDS=1200  # 20 minutes
```

Add to `app/config.py`:

```python
# GPT-Researcher API Configuration
gptr_api_url: str = "http://127.0.0.1:8001"
gptr_timeout_seconds: int = 1200
```

### Phase 2: New Adapter Implementation (Day 1 Afternoon)

#### 2.1 Create New HTTP-Based Adapter

Create `app/adapters/gptr/adapter_http.py`:

```python
"""
GPT-Researcher HTTP API Adapter.

Calls the standalone GPTR FastAPI service instead of spawning subprocesses.
"""
import httpx
import logging
from datetime import datetime
from typing import Optional

from app.adapters.base import (
    BaseAdapter, GenerationConfig, GenerationResult, 
    GeneratorType, TaskStatus, ProgressCallback
)
from app.config import get_settings

logger = logging.getLogger(__name__)


class GptrHttpAdapter(BaseAdapter):
    """
    Adapter that calls GPT-Researcher's HTTP API.
    
    Requires GPTR to be running as a separate service.
    """
    
    def __init__(self):
        settings = get_settings()
        self._base_url = settings.gptr_api_url
        self._timeout = settings.gptr_timeout_seconds

    @property
    def name(self) -> GeneratorType:
        return GeneratorType.GPTR

    @property
    def display_name(self) -> str:
        return "GPT-Researcher"

    async def health_check(self) -> bool:
        """Check if GPTR service is running."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._base_url}/")
                return response.status_code == 200
        except Exception:
            return False

    async def generate(
        self, 
        query: str,
        config: GenerationConfig, 
        *,
        user_uuid: str,
        document_content: Optional[str] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> GenerationResult:
        """Run GPT-Researcher via HTTP API."""
        started_at = datetime.utcnow()
        task_id = config.extra.get("task_id", "unknown")
        
        # Build request payload
        payload = {
            "task": query,
            "report_type": config.extra.get("report_type", "research_report"),
            "agent": config.extra.get("agent", "auto"),
        }
        
        # Add optional parameters
        if config.extra.get("tone"):
            payload["tone"] = config.extra["tone"]
        if config.extra.get("source_urls"):
            payload["source_urls"] = config.extra["source_urls"]
        
        # Inject API keys as headers (GPTR service must be configured to accept these)
        # Or: configure GPTR service with keys in its environment
        headers = {
            "Content-Type": "application/json",
        }
        
        try:
            if progress_callback:
                await progress_callback("starting", 0.0, "Sending request to GPTR service...")
            
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/research",
                    json=payload,
                    headers=headers,
                )
                
                if response.status_code != 200:
                    return GenerationResult(
                        generator=GeneratorType.GPTR,
                        task_id=task_id,
                        content="",
                        cost_usd=0.0,
                        status=TaskStatus.FAILED,
                        error_message=f"GPTR API error: {response.status_code} - {response.text[:500]}",
                        started_at=started_at,
                        completed_at=datetime.utcnow(),
                    )
                
                data = response.json()
                
                if progress_callback:
                    await progress_callback("completed", 1.0, "Research complete")
                
                return GenerationResult(
                    generator=GeneratorType.GPTR,
                    task_id=task_id,
                    content=data.get("report", data.get("output", "")),
                    cost_usd=float(data.get("costs", 0.0) or 0.0),
                    metadata={
                        "sources": data.get("sources", []),
                        "research_context": data.get("context", ""),
                    },
                    status=TaskStatus.COMPLETED,
                    started_at=started_at,
                    completed_at=datetime.utcnow(),
                )
                
        except httpx.TimeoutException:
            return GenerationResult(
                generator=GeneratorType.GPTR,
                task_id=task_id,
                content="",
                cost_usd=0.0,
                status=TaskStatus.FAILED,
                error_message=f"GPTR request timed out after {self._timeout} seconds",
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )
        except Exception as e:
            logger.exception(f"GPTR HTTP request failed: {e}")
            return GenerationResult(
                generator=GeneratorType.GPTR,
                task_id=task_id,
                content="",
                cost_usd=0.0,
                status=TaskStatus.FAILED,
                error_message=f"GPTR request failed: {str(e)}",
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

    async def cancel(self, task_id: str) -> bool:
        """Cancel is not directly supported via HTTP API."""
        # GPTR's HTTP API may not support cancellation
        # For now, return False
        logger.warning(f"Cancel requested for {task_id} but HTTP API doesn't support cancellation")
        return False
```

**Total: ~120 lines** (vs 665 lines currently)

### Phase 3: Integration (Day 2)

#### 3.1 Update RunExecutor to Use New Adapter

In `app/services/run_executor.py`:

```python
# Change import
# OLD:
from ..adapters.gptr.adapter import GptrAdapter

# NEW:
from ..adapters.gptr.adapter_http import GptrHttpAdapter as GptrAdapter
```

#### 3.2 Add Feature Flag for Gradual Rollout

```python
# In config.py
use_gptr_http_api: bool = True  # Toggle between subprocess and HTTP

# In run_executor.py
if settings.use_gptr_http_api:
    from ..adapters.gptr.adapter_http import GptrHttpAdapter as GptrAdapter
else:
    from ..adapters.gptr.adapter import GptrAdapter
```

#### 3.3 Update Health Check Endpoint

Ensure `/api/v1/health` checks GPTR service availability:

```python
# In health.py
gptr_healthy = await gptr_adapter.health_check()
```

### Phase 4: Testing (Day 2-3)

#### 4.1 Test Matrix

| Test | Expected Result |
|------|-----------------|
| GPTR service not running | health_check returns False, generate returns error |
| Normal research query | Returns report content |
| Long-running query | Completes before timeout |
| Query exceeds timeout | Returns timeout error |
| GPTR service crashes mid-request | Returns connection error |
| Multiple concurrent requests | All succeed (service handles queue) |

#### 4.2 Test Commands

```bash
# Start GPTR service
cd /opt/gptr && ./venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8001

# Test health
curl http://127.0.0.1:8001/

# Test research endpoint
curl -X POST http://127.0.0.1:8001/research \
  -H "Content-Type: application/json" \
  -d '{"task": "What is quantum computing?", "report_type": "research_report"}'
```

### Phase 5: Deployment (Day 3)

#### 5.1 Deployment Steps

1. Deploy GPTR as standalone service
2. Verify GPTR service is healthy
3. Deploy ACM2 with new adapter (feature flag ON)
4. Monitor for errors
5. If stable, remove old subprocess adapter
6. Remove feature flag

#### 5.2 Rollback Plan

If issues occur:
1. Set `use_gptr_http_api = False` in config
2. Restart ACM2
3. Investigate GPTR service logs

---

## Part 4: Preventing Common Issues

### 4.1 Service Availability

**Issue**: GPTR service not running when ACM2 starts.

**Prevention**:
- Use systemd `After=gptr.service` in ACM2's unit file
- Add retry logic in health_check endpoint
- Display clear error in UI: "Research service unavailable"

```python
async def health_check(self) -> bool:
    """Check GPTR service with retry."""
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._base_url}/")
                if response.status_code == 200:
                    return True
        except Exception:
            await asyncio.sleep(1)
    return False
```

### 4.2 Timeout Handling

**Issue**: HTTP timeout doesn't kill the GPTR job - it keeps running.

**Prevention**:
- Set GPTR's internal timeout lower than HTTP timeout
- Monitor GPTR service for runaway jobs
- Add watchdog to restart GPTR if RAM exceeds threshold

```ini
# In gptr.service
MemoryMax=2G
TimeoutStopSec=30
```

### 4.3 API Key Injection

**Issue**: Per-user API keys need to reach GPTR service.

**Solutions** (pick one):
1. **Header-based**: Send keys in request headers, modify GPTR to read them
2. **Service-level**: Configure GPTR with shared keys, track usage per-user in ACM2
3. **Request body**: Add keys to request payload if GPTR API supports it

**Recommended**: Option 2 (Service-level keys) - simplest, GPTR already works this way.

```python
# Track usage attribution in ACM2, not in GPTR
result = await gptr_adapter.generate(query, config, user_uuid=user_uuid)
await usage_tracker.record(user_uuid, result.cost_usd)
```

### 4.4 Crash Recovery

**Issue**: GPTR service crashes and doesn't restart.

**Prevention**:
```ini
# systemd handles this
Restart=always
RestartSec=5
```

**Monitoring**:
```bash
# Alert if GPTR restarts too often
journalctl -u gptr.service --since "1 hour ago" | grep "Started GPT-Researcher" | wc -l
```

### 4.5 Request Queuing

**Issue**: Multiple concurrent requests overwhelm GPTR.

**Prevention**:
- GPTR's uvicorn handles concurrent requests
- Add semaphore in ACM2 to limit concurrent GPTR calls:

```python
_gptr_semaphore = asyncio.Semaphore(3)  # Max 3 concurrent

async def generate(self, ...):
    async with _gptr_semaphore:
        # Make HTTP request
```

### 4.6 Network Errors

**Issue**: Localhost connection fails.

**Prevention**:
- Use `127.0.0.1` not `localhost` (avoids DNS issues)
- Check firewall rules
- Log connection errors clearly:

```python
except httpx.ConnectError as e:
    logger.error(f"Cannot connect to GPTR at {self._base_url}: {e}")
    return GenerationResult(
        status=TaskStatus.FAILED,
        error_message="Research service unavailable. Please try again later.",
    )
```

### 4.7 Response Format Changes

**Issue**: GPTR updates their API, response format changes.

**Prevention**:
- Pin GPTR version in requirements
- Parse response defensively:

```python
content = data.get("report") or data.get("output") or data.get("result") or ""
```

- Add API version check:

```python
async def health_check(self) -> bool:
    response = await client.get(f"{self._base_url}/")
    data = response.json()
    version = data.get("version", "unknown")
    if version < "3.0.0":
        logger.warning(f"GPTR version {version} may have incompatible API")
    return True
```

---

## Part 5: Verification Checklist

### Before Migration

- [ ] GPTR service runs standalone
- [ ] GPTR responds to `/research` endpoint
- [ ] API keys configured in GPTR environment
- [ ] Timeout settings configured

### After Migration

- [ ] ACM2 health endpoint shows GPTR healthy
- [ ] Research query from UI completes successfully
- [ ] Multiple concurrent queries work
- [ ] Timeout error displays correctly
- [ ] GPTR crash triggers clear error message
- [ ] RAM usage reduced (check with `htop`)

### Cleanup

- [ ] Remove `app/adapters/gptr/adapter.py` (old subprocess version)
- [ ] Remove `app/adapters/gptr/entrypoint.py`
- [ ] Remove subprocess-related config from `GptrConfig`
- [ ] Update documentation
- [ ] Remove feature flag

---

## Part 6: Files Changed

| File | Action |
|------|--------|
| `app/adapters/gptr/adapter_http.py` | CREATE - New HTTP adapter |
| `app/adapters/gptr/adapter.py` | DELETE (after migration) |
| `app/adapters/gptr/entrypoint.py` | DELETE (after migration) |
| `app/adapters/gptr/config.py` | MODIFY - Remove subprocess settings |
| `app/config.py` | MODIFY - Add GPTR API URL/timeout |
| `app/services/run_executor.py` | MODIFY - Import new adapter |
| `.env` | MODIFY - Add GPTR_API_URL |

---

## Summary

| Metric | Before | After |
|--------|--------|-------|
| Lines of GPTR adapter code | 665 | ~120 |
| RAM per concurrent job | +500 MB | +0 MB |
| Total GPTR RAM | N × 500 MB | 500 MB (fixed) |
| Job startup time | 3-10 seconds | 0 seconds |
| Files | 3 | 1 |
| Maintenance burden | High (we maintain) | Low (they maintain API) |

**Estimated Effort**: 2-3 days for careful implementation and testing.

---

*End of Migration Plan*
