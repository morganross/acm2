# ACM 2.0 – Global Rate Limiting Plan

**Status:** Draft  
**Author:** Development Team  
**Last Updated:** 2025-12-04

> **Platform:** Windows, Linux, macOS. Python + SQLite. No Docker.
> **Goal:** Proactive rate limiting that minimizes 429 errors by knowing limits upfront and scheduling requests accordingly.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Rate Limit Data Model](#2-rate-limit-data-model)
3. [Provider Rate Limit Headers](#3-provider-rate-limit-headers)
4. [Token Bucket Implementation](#4-token-bucket-implementation)
5. [Concurrency Semaphores](#5-concurrency-semaphores)
6. [Token Estimation](#6-token-estimation)
7. [Configuration](#7-configuration)
8. [Integration Points](#8-integration-points)
9. [Monitoring and Observability](#9-monitoring-and-observability)
10. [Error Handling and Fallback](#10-error-handling-and-fallback)
11. [File Structure](#11-file-structure)

---

## 1. Overview

### The Problem with Reactive Rate Limiting

ACM 1.0 uses reactive rate limiting:
1. Fire requests at the API
2. Hit rate limit (429 error)
3. Backoff and retry
4. Waste time on failed requests

### Proactive Rate Limiting (ACM 2.0)

**Know your limits upfront, schedule accordingly.**

| Approach | How It Works | Result |
|----------|--------------|--------|
| **Reactive** | Send request → get 429 → backoff → retry | Unpredictable, wastes time |
| **Proactive** | Check bucket → wait if needed → send request | Near-zero 429s, predictable throughput |

### Key Insight

Providers return rate limit info in response headers. After the first request, we know exactly:
- How many requests remain in current window
- How many tokens remain in current window
- When the window resets

We use this to **never exceed limits**.

---

## 2. Rate Limit Data Model

### 2.1 RateLimitBucket

Each provider/model combination has its own bucket.

```python
@dataclass
class RateLimitBucket:
    """Tracks rate limit state for a provider/model."""
    
    provider: str              # "openai", "anthropic", "google", "azure"
    model: str                 # "gpt-4o", "claude-sonnet-4-20250514", etc.
    
    # Configured limits (from defaults or API response)
    rpm_limit: int             # Requests per minute
    tpm_limit: int             # Tokens per minute
    rpd_limit: int | None      # Requests per day (some providers)
    tpd_limit: int | None      # Tokens per day (some providers)
    
    # Current state
    rpm_remaining: int         # Requests remaining in current window
    tpm_remaining: int         # Tokens remaining in current window
    rpd_remaining: int | None  # Daily requests remaining
    tpd_remaining: int | None  # Daily tokens remaining
    
    # Window timing
    rpm_resets_at: datetime    # When minute window resets
    tpd_resets_at: datetime | None  # When daily window resets
    
    # Tracking
    last_updated: datetime
    last_request_at: datetime | None
```

### 2.2 RateLimitKey

```python
@dataclass(frozen=True)
class RateLimitKey:
    """Unique identifier for a rate limit bucket."""
    provider: str
    model: str
    
    def __str__(self) -> str:
        return f"{self.provider}/{self.model}"
```

### 2.3 RateLimitPermit

```python
@dataclass
class RateLimitPermit:
    """Permit to make a request, must be released after completion."""
    key: RateLimitKey
    acquired_at: datetime
    estimated_tokens: int
    permit_id: str  # UUID for tracking
```

---

## 3. Provider Rate Limit Headers

### 3.1 OpenAI

```
x-ratelimit-limit-requests: 500
x-ratelimit-limit-tokens: 150000
x-ratelimit-remaining-requests: 499
x-ratelimit-remaining-tokens: 149800
x-ratelimit-reset-requests: 120ms
x-ratelimit-reset-tokens: 1s
```

**Parser:**
```python
def parse_openai_headers(headers: dict) -> RateLimitUpdate:
    return RateLimitUpdate(
        rpm_limit=int(headers.get("x-ratelimit-limit-requests", 0)),
        tpm_limit=int(headers.get("x-ratelimit-limit-tokens", 0)),
        rpm_remaining=int(headers.get("x-ratelimit-remaining-requests", 0)),
        tpm_remaining=int(headers.get("x-ratelimit-remaining-tokens", 0)),
        rpm_reset_ms=parse_duration(headers.get("x-ratelimit-reset-requests", "0ms")),
        tpm_reset_ms=parse_duration(headers.get("x-ratelimit-reset-tokens", "0ms")),
    )
```

### 3.2 Anthropic

```
anthropic-ratelimit-requests-limit: 50
anthropic-ratelimit-requests-remaining: 49
anthropic-ratelimit-requests-reset: 2025-12-04T12:00:00Z
anthropic-ratelimit-tokens-limit: 40000
anthropic-ratelimit-tokens-remaining: 39500
anthropic-ratelimit-tokens-reset: 2025-12-04T12:00:00Z
```

**Parser:**
```python
def parse_anthropic_headers(headers: dict) -> RateLimitUpdate:
    return RateLimitUpdate(
        rpm_limit=int(headers.get("anthropic-ratelimit-requests-limit", 0)),
        tpm_limit=int(headers.get("anthropic-ratelimit-tokens-limit", 0)),
        rpm_remaining=int(headers.get("anthropic-ratelimit-requests-remaining", 0)),
        tpm_remaining=int(headers.get("anthropic-ratelimit-tokens-remaining", 0)),
        rpm_reset_at=parse_iso_datetime(headers.get("anthropic-ratelimit-requests-reset")),
        tpm_reset_at=parse_iso_datetime(headers.get("anthropic-ratelimit-tokens-reset")),
    )
```

### 3.3 Google (Gemini)

Google uses quota-based limiting. Headers are less standardized.

```
x-ratelimit-limit: 60
x-ratelimit-remaining: 59
x-ratelimit-reset: 1701696000
```

**Note:** Google quotas are typically per-project, configured in Cloud Console. Consider querying the Quota API for accurate limits.

### 3.4 Azure OpenAI

Similar to OpenAI but with Azure-specific headers:

```
x-ratelimit-remaining-requests: 119
x-ratelimit-remaining-tokens: 119900
x-ms-region: eastus
```

**Azure has deployment-level limits** — each deployment (model instance) has its own TPM allocation.

### 3.5 Groq

```
x-ratelimit-limit-requests: 30
x-ratelimit-limit-tokens: 6000
x-ratelimit-remaining-requests: 29
x-ratelimit-remaining-tokens: 5800
x-ratelimit-reset-requests: 2s
x-ratelimit-reset-tokens: 10s
```

### 3.6 Header Parser Registry

```python
HEADER_PARSERS: dict[str, Callable[[dict], RateLimitUpdate]] = {
    "openai": parse_openai_headers,
    "anthropic": parse_anthropic_headers,
    "google": parse_google_headers,
    "azure": parse_azure_headers,
    "groq": parse_groq_headers,
}

def parse_rate_limit_headers(provider: str, headers: dict) -> RateLimitUpdate | None:
    parser = HEADER_PARSERS.get(provider)
    if parser:
        try:
            return parser(headers)
        except Exception as e:
            logger.warning(f"Failed to parse rate limit headers for {provider}: {e}")
    return None
```

---

## 4. Token Bucket Implementation

### 4.1 RateLimiter Class

```python
class RateLimiter:
    """Global rate limiter for all LLM API calls."""
    
    def __init__(self, config: RateLimitConfig):
        self._config = config
        self._buckets: dict[RateLimitKey, RateLimitBucket] = {}
        self._locks: dict[RateLimitKey, asyncio.Lock] = {}
        self._waiters: dict[RateLimitKey, int] = {}  # Count of waiting requests
    
    def _get_or_create_bucket(self, key: RateLimitKey) -> RateLimitBucket:
        """Get existing bucket or create from defaults."""
        if key not in self._buckets:
            defaults = self._config.get_defaults(key.provider, key.model)
            self._buckets[key] = RateLimitBucket(
                provider=key.provider,
                model=key.model,
                rpm_limit=defaults.rpm,
                tpm_limit=defaults.tpm,
                rpm_remaining=defaults.rpm,
                tpm_remaining=defaults.tpm,
                rpm_resets_at=datetime.now() + timedelta(minutes=1),
                last_updated=datetime.now(),
            )
            self._locks[key] = asyncio.Lock()
        return self._buckets[key]
    
    async def acquire(
        self,
        provider: str,
        model: str,
        estimated_tokens: int,
        timeout: float | None = None
    ) -> RateLimitPermit:
        """
        Acquire a permit to make a request.
        
        Blocks until rate limit capacity is available.
        Returns a permit that MUST be released after the request completes.
        
        Args:
            provider: API provider (openai, anthropic, etc.)
            model: Model name (gpt-4o, claude-sonnet-4-20250514, etc.)
            estimated_tokens: Estimated total tokens (input + output)
            timeout: Max seconds to wait (None = wait forever)
        
        Raises:
            RateLimitTimeoutError: If timeout exceeded while waiting
        """
        key = RateLimitKey(provider, model)
        bucket = self._get_or_create_bucket(key)
        
        start_time = datetime.now()
        
        async with self._locks[key]:
            while True:
                # Refill bucket if window has reset
                self._maybe_refill(bucket)
                
                # Check if we have capacity
                if bucket.rpm_remaining >= 1 and bucket.tpm_remaining >= estimated_tokens:
                    # Acquire
                    bucket.rpm_remaining -= 1
                    bucket.tpm_remaining -= estimated_tokens
                    bucket.last_request_at = datetime.now()
                    
                    return RateLimitPermit(
                        key=key,
                        acquired_at=datetime.now(),
                        estimated_tokens=estimated_tokens,
                        permit_id=str(uuid.uuid4())
                    )
                
                # Calculate wait time
                wait_seconds = self._calculate_wait(bucket, estimated_tokens)
                
                # Check timeout
                if timeout is not None:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    if elapsed + wait_seconds > timeout:
                        raise RateLimitTimeoutError(
                            f"Timeout waiting for rate limit capacity: {key}"
                        )
                
                # Log waiting
                logger.info(
                    f"Rate limit: waiting {wait_seconds:.1f}s for {key} "
                    f"(rpm_remaining={bucket.rpm_remaining}, tpm_remaining={bucket.tpm_remaining})"
                )
                
                # Wait and retry
                await asyncio.sleep(min(wait_seconds, 1.0))  # Check every second max
    
    def release(
        self,
        permit: RateLimitPermit,
        actual_tokens: int | None = None,
        response_headers: dict | None = None
    ) -> None:
        """
        Release a permit after request completion.
        
        Updates bucket state from response headers if available.
        Corrects token count if actual differs from estimate.
        """
        bucket = self._buckets.get(permit.key)
        if not bucket:
            return
        
        # Update from headers (authoritative)
        if response_headers:
            update = parse_rate_limit_headers(permit.key.provider, response_headers)
            if update:
                self._apply_update(bucket, update)
        
        # Correct token estimate if needed
        if actual_tokens is not None and actual_tokens != permit.estimated_tokens:
            token_diff = permit.estimated_tokens - actual_tokens
            bucket.tpm_remaining += token_diff  # Give back over-estimated tokens
        
        bucket.last_updated = datetime.now()
    
    def _maybe_refill(self, bucket: RateLimitBucket) -> None:
        """Refill bucket if window has reset."""
        now = datetime.now()
        
        if now >= bucket.rpm_resets_at:
            bucket.rpm_remaining = bucket.rpm_limit
            bucket.tpm_remaining = bucket.tpm_limit
            bucket.rpm_resets_at = now + timedelta(minutes=1)
    
    def _calculate_wait(self, bucket: RateLimitBucket, tokens_needed: int) -> float:
        """Calculate seconds to wait for capacity."""
        now = datetime.now()
        
        # If RPM exhausted, wait for reset
        if bucket.rpm_remaining < 1:
            return (bucket.rpm_resets_at - now).total_seconds()
        
        # If TPM exhausted, wait for reset
        if bucket.tpm_remaining < tokens_needed:
            return (bucket.rpm_resets_at - now).total_seconds()
        
        return 0.0
    
    def _apply_update(self, bucket: RateLimitBucket, update: RateLimitUpdate) -> None:
        """Apply authoritative update from response headers."""
        if update.rpm_limit:
            bucket.rpm_limit = update.rpm_limit
        if update.tpm_limit:
            bucket.tpm_limit = update.tpm_limit
        if update.rpm_remaining is not None:
            bucket.rpm_remaining = update.rpm_remaining
        if update.tpm_remaining is not None:
            bucket.tpm_remaining = update.tpm_remaining
        if update.rpm_reset_at:
            bucket.rpm_resets_at = update.rpm_reset_at
```

### 4.2 Context Manager Usage

```python
class RateLimitContext:
    """Context manager for rate-limited requests."""
    
    def __init__(
        self,
        limiter: RateLimiter,
        provider: str,
        model: str,
        estimated_tokens: int
    ):
        self._limiter = limiter
        self._provider = provider
        self._model = model
        self._estimated_tokens = estimated_tokens
        self._permit: RateLimitPermit | None = None
        self._response_headers: dict | None = None
        self._actual_tokens: int | None = None
    
    async def __aenter__(self) -> "RateLimitContext":
        self._permit = await self._limiter.acquire(
            self._provider,
            self._model,
            self._estimated_tokens
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._permit:
            self._limiter.release(
                self._permit,
                actual_tokens=self._actual_tokens,
                response_headers=self._response_headers
            )
    
    def set_response(self, headers: dict, actual_tokens: int) -> None:
        """Call after receiving response to update rate limit state."""
        self._response_headers = headers
        self._actual_tokens = actual_tokens


# Usage:
async with rate_limiter.context("openai", "gpt-4o", estimated_tokens=5000) as ctx:
    response = await client.chat.completions.create(...)
    ctx.set_response(response.headers, response.usage.total_tokens)
```

---

## 5. Concurrency Semaphores

Even with token bucket, limit concurrent requests per provider as a safety net.

### 5.1 Semaphore Layer

```python
class ConcurrencyLimiter:
    """Limits concurrent requests per provider."""
    
    def __init__(self, config: ConcurrencyConfig):
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._config = config
    
    def _get_semaphore(self, provider: str) -> asyncio.Semaphore:
        if provider not in self._semaphores:
            limit = self._config.get_concurrency_limit(provider)
            self._semaphores[provider] = asyncio.Semaphore(limit)
        return self._semaphores[provider]
    
    @asynccontextmanager
    async def acquire(self, provider: str):
        """Acquire concurrency permit for provider."""
        semaphore = self._get_semaphore(provider)
        async with semaphore:
            yield
```

### 5.2 Default Concurrency Limits

```yaml
# rate_limits.yaml
concurrency:
  openai: 10        # 10 concurrent requests
  anthropic: 5      # Anthropic has stricter limits
  google: 10
  azure: 10
  groq: 5
  default: 3        # Unknown providers
```

### 5.3 Combined Rate + Concurrency Limiter

```python
class GlobalLimiter:
    """Combines rate limiting and concurrency limiting."""
    
    def __init__(self, rate_config: RateLimitConfig, concurrency_config: ConcurrencyConfig):
        self._rate_limiter = RateLimiter(rate_config)
        self._concurrency_limiter = ConcurrencyLimiter(concurrency_config)
    
    @asynccontextmanager
    async def acquire(
        self,
        provider: str,
        model: str,
        estimated_tokens: int
    ) -> AsyncIterator[RateLimitContext]:
        """
        Acquire both rate limit and concurrency permits.
        
        Usage:
            async with limiter.acquire("openai", "gpt-4o", 5000) as ctx:
                response = await make_request()
                ctx.set_response(response.headers, response.usage.total_tokens)
        """
        # First acquire concurrency (fast, just a semaphore)
        async with self._concurrency_limiter.acquire(provider):
            # Then acquire rate limit (may wait for bucket capacity)
            async with self._rate_limiter.context(provider, model, estimated_tokens) as ctx:
                yield ctx
```

---

## 6. Token Estimation

### 6.1 Why Estimate?

For proactive TPM limiting, we must know token count **before** sending the request.

### 6.2 Estimation Strategies

| Strategy | Accuracy | Speed | Use Case |
|----------|----------|-------|----------|
| **tiktoken** | High (exact for OpenAI) | Medium | OpenAI models |
| **Anthropic tokenizer** | High | Medium | Claude models |
| **Character ratio** | Low (~80%) | Fast | Fallback, unknown models |

### 6.3 TokenEstimator Class

```python
class TokenEstimator:
    """Estimates token count for different providers/models."""
    
    def __init__(self):
        self._tiktoken_encodings: dict[str, tiktoken.Encoding] = {}
    
    def estimate(
        self,
        provider: str,
        model: str,
        messages: list[dict],
        max_output_tokens: int = 4096
    ) -> int:
        """
        Estimate total tokens (input + output) for a request.
        
        Args:
            provider: API provider
            model: Model name
            messages: Chat messages
            max_output_tokens: Expected max output tokens
        
        Returns:
            Estimated total tokens
        """
        input_tokens = self._estimate_input(provider, model, messages)
        
        # Add buffer for output (use max_output_tokens or default)
        output_estimate = min(max_output_tokens, 4096)
        
        return input_tokens + output_estimate
    
    def _estimate_input(self, provider: str, model: str, messages: list[dict]) -> int:
        """Estimate input tokens."""
        
        if provider == "openai" or provider == "azure":
            return self._tiktoken_estimate(model, messages)
        
        elif provider == "anthropic":
            return self._anthropic_estimate(messages)
        
        else:
            return self._character_estimate(messages)
    
    def _tiktoken_estimate(self, model: str, messages: list[dict]) -> int:
        """Use tiktoken for accurate OpenAI token count."""
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")  # Default for GPT-4
        
        # Count tokens per message (simplified)
        total = 0
        for msg in messages:
            total += 4  # Message overhead
            total += len(encoding.encode(msg.get("content", "")))
            total += len(encoding.encode(msg.get("role", "")))
        total += 2  # Reply priming
        
        return total
    
    def _anthropic_estimate(self, messages: list[dict]) -> int:
        """Estimate for Anthropic (use character ratio, ~4 chars/token)."""
        total_chars = sum(len(msg.get("content", "")) for msg in messages)
        return int(total_chars / 3.5)  # Anthropic tokenizer is slightly different
    
    def _character_estimate(self, messages: list[dict]) -> int:
        """Fallback: ~4 characters per token."""
        total_chars = sum(len(msg.get("content", "")) for msg in messages)
        return int(total_chars / 4) + 100  # Add buffer
```

### 6.4 Estimation Accuracy

After each request, compare estimate to actual:

```python
def track_estimation_accuracy(
    provider: str,
    model: str,
    estimated: int,
    actual: int
) -> None:
    """Track estimation accuracy for tuning."""
    ratio = actual / estimated if estimated > 0 else 1.0
    
    logger.debug(
        f"Token estimation: {provider}/{model} - "
        f"estimated={estimated}, actual={actual}, ratio={ratio:.2f}"
    )
    
    # Could store in DB for analysis and auto-tuning
```

---

## 7. Configuration

### 7.1 Default Rate Limits

```yaml
# config/rate_limits.yaml

# Default limits per provider/model (conservative estimates)
# These are updated from response headers after first request

defaults:
  openai:
    gpt-4o:
      rpm: 500
      tpm: 150000
    gpt-4o-mini:
      rpm: 500
      tpm: 200000
    gpt-4-turbo:
      rpm: 500
      tpm: 150000
    default:  # Fallback for unknown OpenAI models
      rpm: 100
      tpm: 40000
  
  anthropic:
    claude-sonnet-4-20250514:
      rpm: 50
      tpm: 40000
    claude-3-5-sonnet-20241022:
      rpm: 50
      tpm: 40000
    claude-3-5-haiku-20241022:
      rpm: 50
      tpm: 50000
    default:
      rpm: 50
      tpm: 40000
  
  google:
    gemini-1.5-pro:
      rpm: 60
      tpm: 120000
    gemini-1.5-flash:
      rpm: 60
      tpm: 120000
    default:
      rpm: 60
      tpm: 100000
  
  azure:
    # Azure limits are per-deployment, configured in Azure portal
    default:
      rpm: 100
      tpm: 80000
  
  groq:
    llama-3.1-70b-versatile:
      rpm: 30
      tpm: 6000
    default:
      rpm: 30
      tpm: 6000
  
  # Catch-all for unknown providers
  default:
    rpm: 10
    tpm: 10000

# Concurrency limits (max simultaneous requests)
concurrency:
  openai: 10
  anthropic: 5
  google: 10
  azure: 10
  groq: 5
  default: 3

# Behavior settings
settings:
  # How long to wait for rate limit capacity before timeout (seconds)
  acquire_timeout: 300  # 5 minutes
  
  # Buffer ratio for token estimation (1.1 = 10% buffer)
  token_estimate_buffer: 1.1
  
  # Minimum wait between requests to same provider (milliseconds)
  min_request_interval_ms: 50
  
  # Whether to update limits from response headers
  update_from_headers: true
```

### 7.2 Configuration Loading

```python
@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    
    defaults: dict[str, dict[str, ProviderLimits]]
    concurrency: dict[str, int]
    settings: RateLimitSettings
    
    @classmethod
    def load(cls, path: Path | None = None) -> "RateLimitConfig":
        """Load config from YAML file or use built-in defaults."""
        if path and path.exists():
            with open(path) as f:
                data = yaml.safe_load(f)
        else:
            data = DEFAULT_RATE_LIMITS  # Built-in defaults
        
        return cls(
            defaults=data.get("defaults", {}),
            concurrency=data.get("concurrency", {}),
            settings=RateLimitSettings(**data.get("settings", {}))
        )
    
    def get_defaults(self, provider: str, model: str) -> ProviderLimits:
        """Get default limits for provider/model."""
        provider_defaults = self.defaults.get(provider, self.defaults.get("default", {}))
        
        if isinstance(provider_defaults, dict):
            model_limits = provider_defaults.get(model, provider_defaults.get("default", {}))
            return ProviderLimits(**model_limits)
        
        return ProviderLimits(rpm=10, tpm=10000)  # Ultra-conservative fallback
    
    def get_concurrency_limit(self, provider: str) -> int:
        """Get concurrency limit for provider."""
        return self.concurrency.get(provider, self.concurrency.get("default", 3))
```

---

## 8. Integration Points

### 8.1 Where Rate Limiting Plugs In

```
┌─────────────────────────────────────────────────────────────┐
│                      ACM 2.0 Pipeline                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  FPF Adapter ──────┐                                        │
│                    │                                        │
│  GPT-R Adapter ────┼───► GlobalLimiter ───► LLM APIs       │
│                    │          │                             │
│  Eval System ──────┘          │                             │
│                               ▼                             │
│                        ┌─────────────┐                      │
│                        │ Rate Bucket │                      │
│                        │ Concurrency │                      │
│                        │ Semaphore   │                      │
│                        └─────────────┘                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 8.2 ModelClient Wrapper

All LLM calls go through a rate-limited client:

```python
class RateLimitedModelClient:
    """Model client with built-in rate limiting."""
    
    def __init__(
        self,
        provider: str,
        client: Any,  # OpenAI, Anthropic, etc.
        limiter: GlobalLimiter,
        token_estimator: TokenEstimator
    ):
        self._provider = provider
        self._client = client
        self._limiter = limiter
        self._estimator = token_estimator
    
    async def chat_completion(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int = 4096,
        **kwargs
    ) -> Any:
        """Rate-limited chat completion."""
        
        # Estimate tokens
        estimated = self._estimator.estimate(
            self._provider,
            model,
            messages,
            max_output_tokens=max_tokens
        )
        
        # Apply buffer
        estimated = int(estimated * 1.1)
        
        # Acquire permits and make request
        async with self._limiter.acquire(self._provider, model, estimated) as ctx:
            response = await self._client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                **kwargs
            )
            
            # Update rate limit state from response
            ctx.set_response(
                headers=dict(response.headers) if hasattr(response, 'headers') else {},
                actual_tokens=response.usage.total_tokens if response.usage else estimated
            )
            
            return response
```

### 8.3 FPF Adapter Integration

```python
# In FPF adapter
class FpfAdapter:
    def __init__(self, limiter: GlobalLimiter, ...):
        self._model_client = RateLimitedModelClient(
            provider="openai",  # or from config
            client=openai_client,
            limiter=limiter,
            token_estimator=TokenEstimator()
        )
    
    async def generate(self, doc: Document) -> Artifact:
        # All LLM calls automatically rate-limited
        response = await self._model_client.chat_completion(
            model=self._config.model,
            messages=self._build_messages(doc),
            max_tokens=4096
        )
        ...
```

### 8.4 Eval System Integration

```python
# In evaluation system
class SingleDocEvaluator:
    def __init__(self, limiter: GlobalLimiter, ...):
        self._model_client = RateLimitedModelClient(
            provider=self._config.judge_provider,
            client=self._build_client(),
            limiter=limiter,
            token_estimator=TokenEstimator()
        )
    
    async def evaluate(self, artifact: str, criteria: list) -> EvalResult:
        # Rate-limited judge call
        response = await self._model_client.chat_completion(
            model=self._config.judge_model,
            messages=self._build_judge_prompt(artifact, criteria)
        )
        ...
```

---

## 9. Monitoring and Observability

### 9.1 Metrics to Track

| Metric | Description | Use |
|--------|-------------|-----|
| `rate_limit_wait_seconds` | Time spent waiting for capacity | Identify bottlenecks |
| `rate_limit_remaining_rpm` | Remaining requests in window | Dashboard |
| `rate_limit_remaining_tpm` | Remaining tokens in window | Dashboard |
| `rate_limit_429_count` | Number of 429 errors (should be ~0) | Alert if > 0 |
| `token_estimation_ratio` | Actual/estimated token ratio | Tune estimator |
| `concurrent_requests` | Current concurrent requests per provider | Dashboard |

### 9.2 Logging

```python
# Log format for rate limit events
logger.info(
    "rate_limit.acquire",
    extra={
        "provider": "openai",
        "model": "gpt-4o",
        "estimated_tokens": 5000,
        "wait_seconds": 2.5,
        "rpm_remaining": 10,
        "tpm_remaining": 15000
    }
)

logger.info(
    "rate_limit.release",
    extra={
        "provider": "openai",
        "model": "gpt-4o",
        "actual_tokens": 4800,
        "estimation_ratio": 0.96
    }
)

logger.warning(
    "rate_limit.429_error",  # Should rarely happen
    extra={
        "provider": "openai",
        "model": "gpt-4o",
        "retry_after": 30
    }
)
```

### 9.3 Status API

```python
# API endpoint to check rate limit status
@router.get("/api/v1/rate-limits/status")
async def get_rate_limit_status(limiter: GlobalLimiter = Depends()):
    """Get current rate limit status for all providers."""
    return {
        provider: {
            "model": model,
            "rpm_limit": bucket.rpm_limit,
            "rpm_remaining": bucket.rpm_remaining,
            "tpm_limit": bucket.tpm_limit,
            "tpm_remaining": bucket.tpm_remaining,
            "resets_at": bucket.rpm_resets_at.isoformat(),
            "concurrent_requests": limiter.get_concurrent_count(provider)
        }
        for (provider, model), bucket in limiter.get_all_buckets()
    }
```

---

## 10. Error Handling and Fallback

### 10.1 When Proactive Limiting Fails

Despite proactive limiting, 429s can still occur:
- Shared org-wide limits (another process consumed quota)
- Limits changed server-side
- Clock skew on reset times

### 10.2 Fallback Strategy

```python
async def request_with_fallback(
    client: RateLimitedModelClient,
    model: str,
    messages: list[dict],
    max_retries: int = 3
) -> Any:
    """Make request with fallback retry on 429."""
    
    for attempt in range(max_retries):
        try:
            return await client.chat_completion(model, messages)
        
        except RateLimitError as e:
            # Log unexpected 429
            logger.warning(f"Unexpected 429 on attempt {attempt + 1}: {e}")
            
            # Extract retry-after from error
            retry_after = extract_retry_after(e) or (2 ** attempt)
            
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_after)
            else:
                raise
```

### 10.3 Circuit Breaker (Optional)

For persistent failures, implement circuit breaker:

```python
class CircuitBreaker:
    """Temporarily disable requests to failing provider."""
    
    def __init__(self, failure_threshold: int = 5, reset_timeout: float = 60.0):
        self._failure_count: dict[str, int] = {}
        self._open_until: dict[str, datetime] = {}
        self._threshold = failure_threshold
        self._reset_timeout = reset_timeout
    
    def record_failure(self, provider: str) -> None:
        self._failure_count[provider] = self._failure_count.get(provider, 0) + 1
        
        if self._failure_count[provider] >= self._threshold:
            self._open_until[provider] = datetime.now() + timedelta(seconds=self._reset_timeout)
            logger.warning(f"Circuit breaker OPEN for {provider}")
    
    def record_success(self, provider: str) -> None:
        self._failure_count[provider] = 0
    
    def is_open(self, provider: str) -> bool:
        if provider in self._open_until:
            if datetime.now() < self._open_until[provider]:
                return True
            else:
                # Half-open: allow one request
                del self._open_until[provider]
        return False
```

---

## 11. File Structure

```
acm2/
├── rate_limiting/
│   ├── __init__.py              # Public exports
│   ├── models.py                # RateLimitBucket, RateLimitKey, RateLimitPermit
│   ├── bucket.py                # RateLimiter class
│   ├── concurrency.py           # ConcurrencyLimiter class
│   ├── global_limiter.py        # GlobalLimiter (combines rate + concurrency)
│   ├── token_estimator.py       # TokenEstimator class
│   ├── header_parsers.py        # Per-provider header parsing
│   ├── config.py                # RateLimitConfig loading
│   ├── client_wrapper.py        # RateLimitedModelClient
│   └── circuit_breaker.py       # CircuitBreaker (optional)
├── config/
│   └── rate_limits.yaml         # Default rate limit configuration
└── tests/
    └── rate_limiting/
        ├── test_bucket.py
        ├── test_concurrency.py
        ├── test_token_estimator.py
        ├── test_header_parsers.py
        └── test_integration.py
```

---

## Summary

| Component | Purpose |
|-----------|---------|
| **Token Bucket** | Track RPM/TPM per provider/model, block until capacity available |
| **Header Parsers** | Extract rate limit info from each provider's response headers |
| **Concurrency Limiter** | Safety net limiting concurrent requests |
| **Token Estimator** | Estimate tokens before sending for proactive TPM limiting |
| **GlobalLimiter** | Combines rate + concurrency limiting in one interface |
| **RateLimitedModelClient** | Drop-in wrapper for LLM clients with automatic limiting |

**Result:** Near-zero 429 errors, predictable throughput, ability to calculate ETAs for runs.

---

**End of Rate Limiting Plan**
