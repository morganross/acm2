"""API key auth and simple in-memory per-key rate limiting middleware."""
from __future__ import annotations

import time
from typing import Callable, Awaitable, Dict, Tuple, Optional

from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.responses import JSONResponse


class ApiKeyMiddleware:
    """Enforces a static API key via Authorization: Bearer <key> for /api routes."""

    def __init__(self, app: ASGIApp, api_key: Optional[str]):
        self.app = app
        self.api_key = api_key

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http" or not scope.get("path", "").startswith("/api"):
            await self.app(scope, receive, send)
            return

        # Allow OPTIONS requests (CORS preflight)
        if scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return

        # Skip enforcement if no key configured
        if not self.api_key:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        auth_header = headers.get(b"authorization")

        if not auth_header:
            await self._reject(send, status_code=401, detail="Missing Authorization header")
            return

        try:
            scheme, token = auth_header.decode().split(" ", 1)
        except ValueError:
            await self._reject(send, status_code=401, detail="Invalid Authorization header format")
            return

        if scheme.lower() != "bearer" or token != self.api_key:
            await self._reject(send, status_code=403, detail="Invalid API key")
            return

        await self.app(scope, receive, send)

    async def _reject(self, send: Send, status_code: int, detail: str) -> None:
        response = JSONResponse({"detail": detail}, status_code=status_code)
        await response(None, send)


class RateLimitMiddleware:
    """Simple fixed-window rate limiter keyed by API key.

    Applies only to /api routes when an API key is configured. Not suitable for
    multi-instance clustering without shared state.
    """

    def __init__(
        self,
        app: ASGIApp,
        api_key: Optional[str],
        max_requests: int,
        window_seconds: int,
    ) -> None:
        self.app = app
        self.api_key = api_key
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: Dict[str, Tuple[float, int]] = {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http" or not scope.get("path", "").startswith("/api"):
            await self.app(scope, receive, send)
            return

        # Allow OPTIONS requests (CORS preflight)
        if scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return

        if not self.api_key or self.max_requests <= 0 or self.window_seconds <= 0:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        auth_header = headers.get(b"authorization")
        token = None
        if auth_header:
            try:
                scheme, token_val = auth_header.decode().split(" ", 1)
                if scheme.lower() == "bearer":
                    token = token_val
            except ValueError:
                pass

        # If no token or wrong token, ApiKeyMiddleware will handle; we only rate-limit when token matches
        if token != self.api_key:
            await self.app(scope, receive, send)
            return

        now = time.time()
        window_start, count = self._buckets.get(token, (now, 0))

        if now - window_start >= self.window_seconds:
            window_start, count = now, 0

        if count >= self.max_requests:
            response = JSONResponse(
                {
                    "detail": "Rate limit exceeded",
                    "limit": self.max_requests,
                    "window_seconds": self.window_seconds,
                },
                status_code=429,
            )
            await response(scope, send)
            return

        self._buckets[token] = (window_start, count + 1)
        await self.app(scope, receive, send)

