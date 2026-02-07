# Major Refactor: GPT-R Subprocess → Patched HTTP API

---

## FINAL PLAN

1. **Migrate from Windows to Linux** - Save hosting costs
2. **Refactor ACM to use GPT-R API instead of subprocesses** - Eliminates 500MB/user overhead
3. **Create a script to patch GPT-R for per-request provider keys** - Enables multi-tenant operation

*Direct import was considered but rejected in favor of HTTP API. The API overhead is negligible (~0.00003%) and we gain crash isolation + independent restarts.*

---

**Document Version**: 1.0  
**Date**: February 6, 2026  
**Status**: APPROVED  
**Estimated Effort**: 3-4 days  
**RAM Savings**: 500MB per concurrent user → 0MB additional per user

---

## Executive Summary

This refactor accomplishes two goals:
1. **Switch from subprocess to HTTP API** - Eliminates 500MB RAM overhead per concurrent job
2. **Patch GPT-R for per-request API keys** - Enables multi-tenant operation with user-provided API keys

### Architecture Change

```
BEFORE (Current):
User1 Request → ACM spawns subprocess → Python loads GPT-R → 500MB RAM
User2 Request → ACM spawns subprocess → Python loads GPT-R → 500MB RAM
User3 Request → ACM spawns subprocess → Python loads GPT-R → 500MB RAM
                                                    Total: 1.5GB for 3 users

AFTER (Target):
[Patched GPT-R Server: 500MB total, always running]
     ↑
User1 Request → ACM sends HTTP + API keys in headers → 0MB additional
User2 Request → ACM sends HTTP + API keys in headers → 0MB additional  
User3 Request → ACM sends HTTP + API keys in headers → 0MB additional
                                                    Total: 500MB for any # users
```

---

## Part 1: Pre-Work - Clone and Patch GPT-R

### 1.1 Why Patch?

Stock GPT-R reads API keys from environment variables at startup. All requests share one key.
For multi-tenant (per-user keys), we need keys passed per-request via headers.

**Good news**: The pattern already exists in GPT-R's codebase (retrievers check `headers.get("key_name")` first).

### 1.2 Clone GPT-R Locally

```bash
# In acm2 project root
mkdir -p vendor
cd vendor
git clone https://github.com/assafelovic/gpt-researcher.git
cd gpt-researcher
git checkout v3.4.0  # Pin to known stable version
```

### 1.3 Patch Files Overview

| File | Change | Lines |
|------|--------|-------|
| `gpt_researcher/utils/llm.py` | Add `api_keys` param to `create_chat_completion()` | ~15 |
| `gpt_researcher/utils/llm.py` | Inject key into `provider_kwargs` based on provider | ~10 |
| `gpt_researcher/skills/*.py` | Pass `api_keys=self.headers` through calls | ~20 |
| `gpt_researcher/actions/*.py` | Pass `api_keys` param through calls | ~15 |
| **Total** | | **~60 lines** |

### 1.4 Patch: utils/llm.py

```python
# BEFORE (line ~23)
async def create_chat_completion(
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = 0.4,
        max_tokens: int | None = 4000,
        llm_provider: str | None = None,
        stream: bool = False,
        websocket: Any | None = None,
        llm_kwargs: dict[str, Any] | None = None,
        cost_callback: callable = None,
        reasoning_effort: str | None = ReasoningEfforts.Medium.value,
        **kwargs
) -> str:

# AFTER
async def create_chat_completion(
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = 0.4,
        max_tokens: int | None = 4000,
        llm_provider: str | None = None,
        stream: bool = False,
        websocket: Any | None = None,
        llm_kwargs: dict[str, Any] | None = None,
        cost_callback: callable = None,
        reasoning_effort: str | None = ReasoningEfforts.Medium.value,
        api_keys: dict | None = None,  # NEW PARAMETER
        **kwargs
) -> str:
```

Then add key injection logic after `provider_kwargs = {'model': model}`:

```python
    provider_kwargs = {'model': model}
    
    # NEW: Inject API key from per-request headers if provided
    if api_keys and llm_provider:
        API_KEY_MAPPING = {
            "openai": ("openai_api_key", "openai_api_key"),
            "anthropic": ("anthropic_api_key", "anthropic_api_key"),
            "google_genai": ("google_api_key", "google_api_key"),
            "openrouter": ("openrouter_api_key", "openai_api_key"),
            "deepseek": ("deepseek_api_key", "openai_api_key"),
            "groq": ("groq_api_key", "groq_api_key"),
            "together": ("together_api_key", "together_api_key"),
            "mistralai": ("mistral_api_key", "mistral_api_key"),
        }
        if llm_provider in API_KEY_MAPPING:
            header_key, provider_key = API_KEY_MAPPING[llm_provider]
            if header_key in api_keys:
                provider_kwargs[provider_key] = api_keys[header_key]
```

### 1.5 Patch: Skill and Action Call Sites

Every call to `create_chat_completion()` needs `api_keys=self.headers` added.

Example from `gpt_researcher/skills/researcher.py`:
```python
# BEFORE
response = await create_chat_completion(
    messages=messages,
    model=self.cfg.smart_llm_model,
    llm_provider=self.cfg.smart_llm_provider,
    cost_callback=self.cost_callback,
)

# AFTER
response = await create_chat_completion(
    messages=messages,
    model=self.cfg.smart_llm_model,
    llm_provider=self.cfg.smart_llm_provider,
    cost_callback=self.cost_callback,
    api_keys=self.headers,  # ADD THIS
)
```

**Call sites to patch** (grep for `create_chat_completion`):
- `actions/agent_creator.py` (1 call)
- `actions/query_processing.py` (3 calls)
- `actions/report_generation.py` (5+ calls)
- `skills/researcher.py` (2-3 calls)
- `skills/writer.py` (2-3 calls)
- `skills/context_manager.py` (1-2 calls)

### 1.6 Create Patch File

After making changes:

```bash
cd vendor/gpt-researcher
git diff > ../../patches/gpt-researcher-multitenancy.patch
```

### 1.7 Install Script

Create `scripts/install_gptr.sh`:

```bash
#!/bin/bash
set -e

GPTR_VERSION="v3.4.0"
PATCH_FILE="patches/gpt-researcher-multitenancy.patch"

echo "Installing GPT-Researcher with multi-tenancy patch..."

# Clone if not exists
if [ ! -d "vendor/gpt-researcher" ]; then
    mkdir -p vendor
    git clone https://github.com/assafelovic/gpt-researcher.git vendor/gpt-researcher
fi

cd vendor/gpt-researcher
git fetch --tags
git checkout $GPTR_VERSION

# Apply patch
git apply ../../$PATCH_FILE

# Install in editable mode
pip install -e .

echo "GPT-Researcher $GPTR_VERSION installed with multi-tenancy patch"
```

---

## Part 2: GPT-R HTTP Server Setup

### 2.1 GPT-R Already Has a FastAPI Server

Located at `gpt_researcher/server/` or run via their docs example.

```bash
# From vendor/gpt-researcher
uvicorn gpt_researcher.server.main:app --host 0.0.0.0 --port 8001
```

### 2.2 Systemd Service (Linux Production)

Create `/etc/systemd/system/gptr.service`:

```ini
[Unit]
Description=GPT-Researcher API Server
After=network.target

[Service]
Type=simple
User=acm2
WorkingDirectory=/opt/acm2/vendor/gpt-researcher
Environment="TAVILY_API_KEY=tvly-xxx"
ExecStart=/opt/acm2/.venv/bin/uvicorn gpt_researcher.server.main:app --host 127.0.0.1 --port 8001
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable gptr
sudo systemctl start gptr
```

### 2.3 Windows Development (PowerShell)

Create `scripts/start_gptr_server.ps1`:

```powershell
$env:TAVILY_API_KEY = "tvly-xxx"
cd vendor/gpt-researcher
python -m uvicorn gpt_researcher.server.main:app --host 127.0.0.1 --port 8001 --reload
```

---

## Part 3: ACM2 HTTP Client Implementation

### 3.1 New Client Module

Create `acm2/app/adapters/gptr/http_client.py`:

```python
"""
GPT-Researcher HTTP Client

Replaces subprocess-based adapter with HTTP calls to GPT-R server.
Supports per-request API keys via headers for multi-tenant operation.
"""

import httpx
from typing import Optional
import asyncio


class GPTRClient:
    """HTTP client for GPT-Researcher server."""
    
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8001",
        timeout: float = 1200.0,  # 20 minutes for long research
    ):
        self.base_url = base_url
        self.timeout = timeout
    
    async def research(
        self,
        query: str,
        report_type: str = "research_report",
        tone: str = "Objective",
        source_urls: list[str] | None = None,
        api_keys: dict | None = None,
    ) -> dict:
        """
        Execute a research request.
        
        Args:
            query: Research query/prompt
            report_type: Type of report (research_report, detailed_report, etc.)
            tone: Report tone
            source_urls: Optional list of URLs to research
            api_keys: Dict of provider API keys for multi-tenant operation
                     e.g. {"openai_api_key": "sk-...", "anthropic_api_key": "..."}
        
        Returns:
            dict with keys: content, context, costs, visited_urls
        """
        payload = {
            "query": query,
            "report_type": report_type,
            "tone": tone,
        }
        if source_urls:
            payload["source_urls"] = source_urls
        
        headers = {"Content-Type": "application/json"}
        
        # Inject per-request API keys as headers
        if api_keys:
            for key, value in api_keys.items():
                # Header format: X-OpenAI-API-Key, X-Anthropic-API-Key, etc.
                header_name = f"X-{key.replace('_', '-').title()}"
                headers[header_name] = value
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/research",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            return response.json()
    
    async def health_check(self) -> bool:
        """Check if GPT-R server is running."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            return False


# Module-level singleton
_client: GPTRClient | None = None


def get_gptr_client(base_url: str = "http://127.0.0.1:8001") -> GPTRClient:
    """Get or create GPT-R client singleton."""
    global _client
    if _client is None:
        _client = GPTRClient(base_url=base_url)
    return _client
```

### 3.2 Update Adapter

Replace `acm2/app/adapters/gptr/adapter.py`:

```python
"""
GPT-Researcher Adapter - HTTP API Version

This replaces the subprocess-based adapter. RAM usage drops from
~500MB per concurrent job to 0MB additional (shared server).
"""

from .http_client import get_gptr_client, GPTRClient
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class GPTRAdapter:
    """Adapter for GPT-Researcher HTTP API."""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8001"):
        self.client = get_gptr_client(base_url)
    
    async def run_research(
        self,
        prompt: str,
        report_type: str = "research_report",
        tone: str = "Objective",
        source_urls: list[str] | None = None,
        user_api_keys: dict | None = None,
    ) -> dict:
        """
        Run GPT-R research task.
        
        Args:
            prompt: Research query
            report_type: Type of report
            tone: Report tone
            source_urls: Optional source URLs
            user_api_keys: Per-user API keys for multi-tenant operation
        
        Returns:
            dict: {status, content, context, costs, visited_urls}
        """
        try:
            result = await self.client.research(
                query=prompt,
                report_type=report_type,
                tone=tone,
                source_urls=source_urls,
                api_keys=user_api_keys,
            )
            return {
                "status": "success",
                "content": result.get("content", ""),
                "context": result.get("context", ""),
                "costs": result.get("costs", 0.0),
                "visited_urls": result.get("visited_urls", []),
            }
        except Exception as e:
            logger.exception("GPT-R research failed")
            return {
                "status": "failed",
                "error": str(e),
            }
    
    async def health_check(self) -> bool:
        """Check GPT-R server health."""
        return await self.client.health_check()
```

### 3.3 Delete Old Subprocess Code

After migration is complete and tested:

```bash
# Files to remove (665 lines of subprocess management)
rm acm2/app/adapters/gptr/entrypoint.py
rm acm2/app/adapters/gptr/subprocess_runner.py  # if exists
# Update __init__.py to export new adapter
```

---

## Part 4: Patch GPT-R Server for Header-Based Keys

The stock GPT-R server needs to read API keys from request headers and pass them to `GPTResearcher(headers=...)`.

### 4.1 Patch Server Route

Patch `gpt_researcher/server/main.py` (or wherever their `/research` endpoint is):

```python
# BEFORE
@app.post("/research")
async def research(request: ResearchRequest):
    researcher = GPTResearcher(
        query=request.query,
        report_type=request.report_type,
        ...
    )

# AFTER  
@app.post("/research")
async def research(request: ResearchRequest, req: Request):
    # Extract API keys from request headers
    api_keys = {}
    for header, value in req.headers.items():
        header_lower = header.lower()
        if header_lower.startswith("x-") and "api-key" in header_lower:
            # Convert X-OpenAI-API-Key → openai_api_key
            key_name = header_lower[2:].replace("-", "_")
            api_keys[key_name] = value
    
    researcher = GPTResearcher(
        query=request.query,
        report_type=request.report_type,
        headers=api_keys,  # Pass keys via headers dict
        ...
    )
```

---

## Part 5: Migration Checklist

### Phase 1: Setup (Day 1)
- [ ] Clone GPT-R to `vendor/gpt-researcher`
- [ ] Pin to version v3.4.0
- [ ] Create patch for `utils/llm.py` (add `api_keys` param)
- [ ] Patch all `create_chat_completion()` call sites
- [ ] Patch server route to extract headers
- [ ] Generate `patches/gpt-researcher-multitenancy.patch`
- [ ] Create `scripts/install_gptr.sh`
- [ ] Test patch applies cleanly

### Phase 2: HTTP Client (Day 2)
- [ ] Create `http_client.py` with `GPTRClient`
- [ ] Create new `adapter.py` (HTTP version)
- [ ] Update config for `GPTR_BASE_URL`
- [ ] Test client against local server

### Phase 3: Integration (Day 3)
- [ ] Update ACM2 to use new adapter
- [ ] Add health check on startup
- [ ] Handle server connection errors gracefully
- [ ] Test with single-user (env keys)
- [ ] Test with per-user keys via headers

### Phase 4: Cleanup (Day 4)
- [ ] Remove old subprocess code (665 lines)
- [ ] Update documentation
- [ ] Update `FOREVER-README-INSTALL.MD`
- [ ] Add GPT-R server to docker-compose (if applicable)
- [ ] Memory test: confirm 0MB overhead per request

---

## Part 6: Maintenance Plan

### On GPT-R Updates

1. Check release notes for breaking changes to:
   - `create_chat_completion()` signature
   - `GPTResearcher.__init__()` params
   - Server route structure

2. If compatible:
   ```bash
   cd vendor/gpt-researcher
   git fetch --tags
   git checkout vX.Y.Z
   git apply ../../patches/gpt-researcher-multitenancy.patch
   # If conflicts, resolve and regenerate patch
   ```

3. Re-run tests

### Expected Frequency
- GPT-R releases ~1x/month
- Breaking changes: ~1x/year (based on 15+ months stability observed)
- Patch maintenance: ~30 min/quarter

---

## Appendix: File Inventory

### Files to Create
| Path | Purpose |
|------|---------|
| `vendor/gpt-researcher/` | Cloned + patched GPT-R |
| `patches/gpt-researcher-multitenancy.patch` | Git patch file |
| `scripts/install_gptr.sh` | Automated patch + install |
| `scripts/start_gptr_server.ps1` | Windows dev server |
| `acm2/app/adapters/gptr/http_client.py` | HTTP client |

### Files to Modify
| Path | Change |
|------|--------|
| `acm2/app/adapters/gptr/adapter.py` | Replace subprocess with HTTP |
| `acm2/app/adapters/gptr/__init__.py` | Export new adapter |
| `acm2/app/core/config.py` | Add `GPTR_BASE_URL` setting |

### Files to Delete
| Path | Lines Saved |
|------|-------------|
| `acm2/app/adapters/gptr/entrypoint.py` | ~92 lines |
| Subprocess management code | ~573 lines |
| **Total** | **~665 lines** |

---

## Summary

| Metric | Before | After |
|--------|--------|-------|
| RAM per concurrent user | 500MB | 0MB |
| Lines of subprocess code | 665 | 0 |
| Lines of HTTP client code | 0 | ~100 |
| Per-user API keys | ✅ (via env per subprocess) | ✅ (via headers) |
| Startup time per request | 3-10 sec | 0 sec |
| Crash isolation | ✅ | ✅ (separate server) |
| Maintenance burden | None | Low (~30 min/quarter) |

---

## Phased Implementation Strategy

**Rationale**: Isolate HTTP integration issues from key injection issues.

### Phase 1: HTTP API with System-Wide Keys

1. Start GPT-R server with API keys in its `.env` file (system-wide, shared)
2. Replace ACM subprocess adapter with HTTP client
3. Test all edge cases:
   - Timeouts
   - Error handling
   - Streaming responses
   - Cancellation
   - Concurrent requests
4. Iron out issues without per-request key complexity

**Goal**: Validate HTTP integration works correctly before adding key injection.

### Phase 2: Per-Request API Keys

1. Patch GPT-R to accept `X-*-API-Key` headers (as detailed in Part 1)
2. Modify ACM HTTP client to:
   - Decrypt user keys via `ProviderKeyManager`
   - Send keys in request headers
3. Remove keys from GPT-R's `.env` file
4. Test multi-tenant key isolation

**Goal**: Enable per-user API keys for multi-tenant operation.

### Why This Order?

- If something breaks in Phase 1 ? it's the HTTP integration
- If something breaks in Phase 2 ? it's the key injection
- Easier debugging with isolated concerns

---

## ?? Evolution of Thinking (Appended Later)

**Note**: The content above was written earlier in the planning process. Our understanding has evolved through further discussion. The sections below capture additional ideas, context, and considerations that emerged later. They may contradict, refine, or expand on earlier sections. Read the whole document to get the full picture.

---

## Appendix A: Why Subprocess Exists (Historical Context)

### The Real Reasons for Subprocess (Not Just RAM)

After deeper investigation, we found the subprocess approach was NOT arbitrary. Two key reasons:

#### 1. Per-User API Key Isolation (THE BIG ONE)

GPT-R reads API keys from `os.environ` which is **process-wide, shared by ALL requests**.

`python
# Problem with direct import + concurrent users:

# Thread 1 (User A)
os.environ["OPENAI_API_KEY"] = "user_a_key"
researcher1 = GPTResearcher(...)  # Uses user_a_key... maybe

# Thread 2 (User B) runs at same time
os.environ["OPENAI_API_KEY"] = "user_b_key"  # OVERWRITES!
researcher2 = GPTResearcher(...)  # Uses user_b_key

# Thread 1's researcher now sees user_b_key! WRONG USER BILLED!
`

**Subprocess solves this**: Each subprocess gets its OWN copy of environment variables. No cross-contamination possible.

This is in `adapter.py` lines 270-275:
`python
from app.security.key_injection import inject_provider_keys_for_user_auto
env = await inject_provider_keys_for_user_auto(user_uuid, env)
`

#### 2. Windows Event Loop Issues

Windows has quirky asyncio behavior with subprocesses when using `ProactorEventLoop`. The adapter works around this by running subprocess calls in threads (`asyncio.to_thread()`).

---

## Appendix B: Alternative Approaches (Ideas to Consider)

### Option: Direct Import (Simplest, But Has Caveats)

If we patch GPT-R to read keys from headers instead of os.environ, we could just do:

`python
from gpt_researcher import GPTResearcher

async def run_research(query: str, user_headers: dict):
    researcher = GPTResearcher(query=query, headers=user_headers)
    await researcher.conduct_research()
    return await researcher.write_report()
`

~10 lines replaces 556 lines of subprocess code.

### Tradeoffs Comparison

| Approach | RAM | Complexity | Crash isolation | Restart flexibility |
|----------|-----|------------|-----------------|---------------------|
| Subprocess | 500MB/user | High | ? | ? |
| HTTP API | 500MB fixed | Medium | ? | ? |
| Direct import | 500MB fixed | **Low** | ? | ? |

### What is an "Instance" vs "Process"?

For future reference, clarifying terminology:

- **Process**: A full OS-level execution unit. Loads Python interpreter, all libraries, everything. ~500MB for GPT-R.
- **Instance**: A Python object (e.g., `researcher = GPTResearcher(...)`). Uses ~1-5MB for just its data. Shares already-loaded libraries.

`
SUBPROCESS MODEL:
+---------------------------------+
� Python Process 1 (500MB)        � ? User A
�  - Python interpreter           �
�  - gpt_researcher + deps        �
+---------------------------------+
+---------------------------------+
� Python Process 2 (500MB)        � ? User B
�  - Python interpreter (AGAIN)   �
�  - gpt_researcher + deps (AGAIN)�
+---------------------------------+
Total: 1GB for 2 users

INSTANCE MODEL (HTTP or Direct Import):
+---------------------------------------------+
� Single Python Process (500MB total)         �
�  - Python interpreter (once)                �
�  - gpt_researcher + deps (once)             �
�                                             �
�  +--------------+  +--------------+         �
�  � Instance A   �  � Instance B   �         �
�  � ~2MB         �  � ~2MB         �         �
�  +--------------+  +--------------+         �
+---------------------------------------------+
Total: ~504MB for any number of users
`

---

## Appendix C: Why We Can't Just Use Direct Import Today

Without patching GPT-R, you **cannot** do per-user API keys with direct import because:

1. Stock GPT-R reads keys from `os.environ` (process-wide)
2. Concurrent requests would overwrite each other's keys
3. Wrong users would get billed

**The subprocess was the ONLY way to do per-user keys with stock GPT-R.**

The HTTP API + patch approach lets us:
1. Keep per-user key support
2. Eliminate the 500MB/user overhead
3. Get crash isolation (separate server process)

Direct import would be even simpler but loses crash isolation.

---

## Appendix D: Lazy Start Ideas

Ideas for not running GPT-R 24/7 if usage is low:

1. **systemd socket activation** - systemd listens on port, auto-starts GPT-R on first request
2. **Check-and-start from ACM** - Ping health endpoint, start if down (adds ~3-5 sec cold start)
3. **Always-on** - Just keep it running, 500MB is cheap

For low-traffic apps, socket activation is nice. For frequent usage, just keep it running.

