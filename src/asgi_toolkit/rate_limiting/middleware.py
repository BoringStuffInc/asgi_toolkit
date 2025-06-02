"""Rate limiting middleware implementation."""

import time
from logging import Logger
from typing import cast

from asgi_toolkit.protocol import ASGIApp, HTTPRequestScope, Message, Receive, Scope, Send
from asgi_toolkit.protocol.http import HTTPResponseStartMessage

from asgi_toolkit.rate_limiting.config import RateLimitConfig
from asgi_toolkit.rate_limiting.protocols import Counter, IdentityExtractor, MetricsCollector, RateLimitingBackend
from asgi_toolkit.rate_limiting.utils import generate_rate_limit_key, get_rate_limit_policy, is_rate_limiting_activated


class RateLimitingMiddleware:
    """Rate limiting middleware for ASGI applications.

    Provides configurable rate limiting with support for:
    - Different backends (memory, Redis, etc.)
    - Per-route and per-method policies
    - Custom identity extraction
    - Metrics collection and logging
    - Whitelisting and activation controls
    """

    def __init__(
        self,
        app: ASGIApp,
        config: RateLimitConfig,
        backend: RateLimitingBackend,
        identity_extractor: IdentityExtractor,
        logger: Logger,
        metrics_collector: MetricsCollector | None = None,
    ) -> None:
        self.app = app
        self.config = config
        self.backend = backend
        self.identity_extractor = identity_extractor
        self.metrics_collector = metrics_collector
        self.logger = logger

        self.rate_limited_requests: Counter | None = None
        self.total_requests: Counter | None = None

        if self.metrics_collector:
            self.rate_limited_requests = self.metrics_collector.counter(
                "rate_limited_requests", "Number of requests denied by rate limiting"
            )
            self.total_requests = self.metrics_collector.counter(
                "total_requests", "Total number of requests processed by rate limiting middleware"
            )

    async def _send_rate_limit_response(
        self,
        scope: HTTPRequestScope,
        receive: Receive,
        send: Send,
        limit: int,
        remaining: int,
        reset: int,
    ) -> None:
        """Send a 429 Too Many Requests response."""
        headers = [
            (b"content-type", b"text/plain"),
            (b"content-length", b"17"),
            (b"x-ratelimit-limit", str(limit).encode()),
            (b"x-ratelimit-remaining", str(remaining).encode()),
            (b"x-ratelimit-reset", str(reset).encode()),
        ]

        if reset:
            retry_after = max(0, reset - int(time.time()))
            headers.append((b"retry-after", str(retry_after).encode()))

        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": headers,
            }
        )

        await send(
            {
                "type": "http.response.body",
                "body": b"Too Many Requests",
            }
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if not is_rate_limiting_activated(scope, self.config):
            await self.app(scope, receive, send)
            return

        if self.total_requests:
            self.total_requests.inc()

        client_id = await self.identity_extractor(scope)

        if client_id in self.config.whitelist:
            await self.app(scope, receive, send)
            return

        route = scope["path"]
        method = scope["method"]
        limit, window = get_rate_limit_policy(route, method, self.config)

        key = generate_rate_limit_key(client_id, route, method)
        rate_limit_result = await self.backend.hit(key, limit, window)

        if not rate_limit_result.allowed:
            self.logger.warning(
                "Rate limit exceeded for client %s on route %s %s. Limit: %d/%ds.",
                client_id,
                method,
                route,
                limit,
                window,
            )

            if self.rate_limited_requests:
                self.rate_limited_requests.inc()

            await self._send_rate_limit_response(
                scope, receive, send, limit, rate_limit_result.remaining, round(rate_limit_result.reset)
            )
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                message = cast(HTTPResponseStartMessage, message)

                headers = list(message.get("headers", []))
                headers.extend(
                    [
                        (b"x-ratelimit-limit", str(limit).encode()),
                        (b"x-ratelimit-remaining", str(rate_limit_result.remaining).encode()),
                        (b"x-ratelimit-reset", str(rate_limit_result.reset).encode()),
                    ]
                )
                message["headers"] = headers

            await send(message)

        await self.app(scope, receive, send_with_headers)
