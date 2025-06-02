import pytest
import logging
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient as FastAPITestClient
from litestar import Litestar, get
from litestar.testing import TestClient as LitestarTestClient
from litestar.status_codes import HTTP_429_TOO_MANY_REQUESTS

from asgi_toolkit.rate_limiting import (
    RateLimitingMiddleware,
    RateLimitConfig,
    PolicyConfig,
    RateLimitingBackend,
    MetricsCollector,
    Counter,
    InMemoryBackend,
    RateLimitResult,
)
from asgi_toolkit.protocol import HTTPRequestScope


class MockRateLimitingBackend(RateLimitingBackend):
    def __init__(self, allowed=True, remaining=5, reset=100) -> None:
        self._allowed = allowed
        self._remaining = remaining
        self._reset = reset
        self.hits: list[RateLimitResult] = []
        self.last_key: str | None = None
        self.last_limit: int | None = None
        self.last_window: int | None = None

    async def hit(self, key: str, limit: int, window: int) -> RateLimitResult:
        result = RateLimitResult(allowed=self._allowed, remaining=self._remaining, reset=self._reset)
        self.hits.append(result)
        self.last_key = key
        self.last_limit = limit
        self.last_window = window
        return result


class MockIdentityExtractor:
    def __init__(self, identity="test_client") -> None:
        self._identity = identity

    async def __call__(self, scope: HTTPRequestScope) -> str:
        return self._identity


class MockCounter(Counter):
    def __init__(self) -> None:
        self.count = 0

    def inc(self) -> None:
        self.count += 1


class MockMetricsCollector(MetricsCollector):
    def __init__(self) -> None:
        self.counters: dict[str, MockCounter] = {}

    def counter(self, name: str, description: str) -> Counter:
        if name not in self.counters:
            self.counters[name] = MockCounter()
        return self.counters[name]


@pytest.fixture(params=["fastapi", "litestar"])
def client(request):
    mock_backend = MockRateLimitingBackend()
    mock_identity_extractor = MockIdentityExtractor()
    mock_logger = MagicMock(spec=logging.Logger)
    mock_metrics_collector = MockMetricsCollector()

    # Handle parametrized test cases that pass additional config
    if isinstance(request.param, tuple):
        framework, extra_config = request.param
        whitelist = extra_config.get("whitelist", set())
        policy_overrides = extra_config.get("policy_overrides", {})
    else:
        framework = request.param
        whitelist = set()
        policy_overrides = {}

    config = RateLimitConfig(
        activation_header="X-RateLimit-Activate",
        activation_query_param="ratelimit",
        whitelist=whitelist,
        policy_overrides=policy_overrides,
    )

    match framework:
        case "fastapi":
            app = FastAPI()

            @app.get("/")
            async def read_root():
                return {"message": "Hello, world!"}

            middleware = RateLimitingMiddleware(
                app=app,
                config=config,
                backend=mock_backend,
                identity_extractor=mock_identity_extractor,
                logger=mock_logger,
                metrics_collector=mock_metrics_collector,
            )
            test_client = FastAPITestClient(middleware)
            test_client.middleware = middleware
            test_client.mock_backend = mock_backend
            test_client.mock_identity_extractor = mock_identity_extractor
            test_client.mock_logger = mock_logger
            test_client.mock_metrics_collector = mock_metrics_collector
            return test_client
        case "litestar":

            @get("/")
            async def read_root() -> dict[str, str]:
                return {"message": "Hello, world!"}

            app = Litestar(route_handlers=[read_root])
            middleware = RateLimitingMiddleware(
                app=app,
                config=config,
                backend=mock_backend,
                identity_extractor=mock_identity_extractor,
                logger=mock_logger,
                metrics_collector=mock_metrics_collector,
            )
            test_client = LitestarTestClient(middleware)
            test_client.middleware = middleware
            test_client.mock_backend = mock_backend
            test_client.mock_identity_extractor = mock_identity_extractor
            test_client.mock_logger = mock_logger
            test_client.mock_metrics_collector = mock_metrics_collector
            return test_client


def assert_response_success(response, expected_data: dict):
    assert response.status_code == 200
    assert response.json() == expected_data


def assert_rate_limited_response(response, expected_remaining: int = 0):
    assert response.status_code == HTTP_429_TOO_MANY_REQUESTS
    assert response.text == "Too Many Requests"
    assert "x-ratelimit-limit" in response.headers
    assert "x-ratelimit-remaining" in response.headers
    assert response.headers["x-ratelimit-remaining"] == str(expected_remaining)
    assert "x-ratelimit-reset" in response.headers


def assert_backend_hits(mock_backend, expected_count: int):
    assert len(mock_backend.hits) == expected_count


def assert_metrics_count(mock_metrics_collector, metric_name: str, expected_count: int):
    assert mock_metrics_collector.counters[metric_name].count == expected_count


class TestRateLimitingMiddleware:
    def test_request_allowed(self, client):
        client.mock_backend._allowed = True
        response = client.get("/", headers={"X-RateLimit-Activate": "true"})

        assert_response_success(response, {"message": "Hello, world!"})
        assert_backend_hits(client.mock_backend, 1)
        assert client.mock_backend.hits[0].allowed is True
        assert client.mock_backend.last_key.startswith("ratelimit:test_client")

    def test_request_denied(self, client):
        client.mock_backend._allowed = False
        client.mock_backend._remaining = 0
        client.mock_backend._reset = 200

        response = client.get("/", headers={"X-RateLimit-Activate": "true"})
        assert_rate_limited_response(response)
        assert_metrics_count(client.mock_metrics_collector, "rate_limited_requests", 1)

    @pytest.mark.parametrize(
        "activation_method,activation_value",
        [
            ("header", {"X-RateLimit-Activate": "true"}),
            ("query", "/?ratelimit=true"),
        ],
    )
    def test_activation_methods(
        self,
        client,
        activation_method,
        activation_value,
    ):
        if activation_method == "header":
            client.get("/", headers=activation_value)
        else:
            client.get(activation_value)

        assert_backend_hits(client.mock_backend, 1)

    def test_not_activated_by_default(self, client):
        client.get("/")

        assert_backend_hits(client.mock_backend, 0)

    @pytest.mark.parametrize(
        "deactivation_method,deactivation_value",
        [
            ("header", {"X-RateLimit-Activate": "off"}),
            ("query", "/?ratelimit=off"),
        ],
    )
    def test_deactivation_methods(
        self,
        client,
        deactivation_method,
        deactivation_value,
    ):
        if deactivation_method == "header":
            client.get("/", headers=deactivation_value)
        else:
            client.get(deactivation_value)

        assert_backend_hits(client.mock_backend, 0)

    @pytest.mark.parametrize(
        "client",
        [
            pytest.param(("fastapi", {"whitelist": {"whitelisted_user"}}), id="fastapi"),
            pytest.param(("litestar", {"whitelist": {"whitelisted_user"}}), id="litestar"),
        ],
        indirect=True,
    )
    def test_whitelisted_client(self, client):
        client.mock_identity_extractor._identity = "whitelisted_user"

        response = client.get("/", headers={"X-RateLimit-Activate": "true"})
        assert response.status_code == 200
        assert_backend_hits(client.mock_backend, 0)

    def test_default_policy(self, client):
        client.get("/", headers={"X-RateLimit-Activate": "true"})

        assert client.mock_backend.last_limit == 100
        assert client.mock_backend.last_window == 60

    @pytest.mark.parametrize(
        "client",
        [
            pytest.param(("fastapi", {"policy_overrides": {"/": PolicyConfig(limit=10, window=50)}}), id="fastapi"),
            pytest.param(("litestar", {"policy_overrides": {"/": PolicyConfig(limit=10, window=50)}}), id="litestar"),
        ],
        indirect=True,
    )
    def test_route_override_policy(self, client):
        client.get("/", headers={"X-RateLimit-Activate": "true"})
        assert client.mock_backend.last_limit == 10
        assert client.mock_backend.last_window == 50

    @pytest.mark.parametrize(
        "client",
        [
            pytest.param(
                ("fastapi", {"policy_overrides": {"/": {"GET": PolicyConfig(limit=5, window=30)}}}), id="fastapi"
            ),
            pytest.param(
                ("litestar", {"policy_overrides": {"/": {"GET": PolicyConfig(limit=5, window=30)}}}), id="litestar"
            ),
        ],
        indirect=True,
    )
    def test_method_override_policy(self, client):
        client.get("/", headers={"X-RateLimit-Activate": "true"})
        assert client.mock_backend.last_limit == 5
        assert client.mock_backend.last_window == 30

    def test_metrics_incremented(self, client):
        client.get("/", headers={"X-RateLimit-Activate": "true"})
        assert_metrics_count(client.mock_metrics_collector, "total_requests", 1)
        assert_metrics_count(client.mock_metrics_collector, "rate_limited_requests", 0)

        original_hit = client.mock_backend.hit

        async def mock_hit_denied(key, limit, window) -> RateLimitResult:
            client.mock_backend.hit = original_hit
            return RateLimitResult(allowed=False, remaining=0, reset=200)

        client.mock_backend.hit = mock_hit_denied

        client.get("/", headers={"X-RateLimit-Activate": "true"})
        assert_metrics_count(client.mock_metrics_collector, "total_requests", 2)
        assert_metrics_count(client.mock_metrics_collector, "rate_limited_requests", 1)

    @pytest.mark.asyncio
    async def test_websocket_scope_skipped(self):
        mock_backend = MockRateLimitingBackend()
        mock_identity_extractor = MockIdentityExtractor()
        mock_logger = MagicMock(spec=logging.Logger)
        mock_metrics_collector = MockMetricsCollector()

        app = FastAPI()

        @app.get("/")
        async def read_root():
            return {"message": "Hello, world!"}

        config = RateLimitConfig(activation_header="X-RateLimit-Activate", activation_query_param="ratelimit")
        middleware = RateLimitingMiddleware(
            app=app,
            config=config,
            backend=mock_backend,
            identity_extractor=mock_identity_extractor,
            logger=mock_logger,
            metrics_collector=mock_metrics_collector,
        )

        async def mock_receive():
            pass

        async def mock_send(message):
            pass

        websocket_scope = {"type": "websocket", "path": "/ws", "method": "GET"}

        await middleware(websocket_scope, mock_receive, mock_send)

        assert_backend_hits(mock_backend, 0)


class TestInMemoryBackend:
    @pytest.fixture
    def in_memory_backend(self):
        return InMemoryBackend()

    @patch("time.time", return_value=100)
    async def test_hit_allowed(self, mock_time, in_memory_backend):
        result = await in_memory_backend.hit("key1", 5, 60)
        allowed = result.allowed
        remaining = result.remaining
        reset = result.reset

        assert allowed is True
        assert remaining == 4
        assert reset == 160
        assert in_memory_backend._counters == {("key1", 60): {"count": 1, "window_start_time": 100}}

    @patch("time.time", return_value=100)
    async def test_hit_denied(self, mock_time, in_memory_backend):
        for _ in range(6):
            result = await in_memory_backend.hit("key1", 5, 60)
            allowed = result.allowed
            remaining = result.remaining
            reset = result.reset

        assert allowed is False
        assert remaining == 0
        assert reset == 160
        assert in_memory_backend._counters == {("key1", 60): {"count": 6, "window_start_time": 100}}

    @patch("time.time")
    async def test_window_reset(self, mock_time, in_memory_backend):
        mock_time.return_value = 100
        await in_memory_backend.hit("key1", 5, 60)
        assert in_memory_backend._counters[("key1", 60)]["count"] == 1

        mock_time.return_value = 159
        await in_memory_backend.hit("key1", 5, 60)
        assert in_memory_backend._counters[("key1", 60)]["count"] == 2

        mock_time.return_value = 160
        await in_memory_backend.hit("key1", 5, 60)
        assert in_memory_backend._counters[("key1", 60)]["count"] == 1
        assert in_memory_backend._counters[("key1", 60)]["window_start_time"] == 160

    @patch("time.time", return_value=100)
    async def test_cleanup_expired_entries(self, mock_time, in_memory_backend):
        await in_memory_backend.hit("key1", 5, 60)
        await in_memory_backend.hit("key2", 3, 30)

        assert ("key1", 60) in in_memory_backend._counters
        assert ("key2", 30) in in_memory_backend._counters

        mock_time.return_value = 131
        await in_memory_backend.hit("key3", 10, 10)

        assert ("key1", 60) in in_memory_backend._counters
        assert ("key2", 30) not in in_memory_backend._counters
        assert ("key3", 10) in in_memory_backend._counters
