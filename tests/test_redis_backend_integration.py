import pytest
import asyncio
import fakeredis

from asgi_toolkit.rate_limiting import RedisBackend


@pytest.mark.parametrize(
    "scenario",
    [
        {
            "key": "test_client_1",
            "limit": 3,
            "window": 1,
            "expected_sequence": [
                (True, 2),  # First hit
                (True, 1),  # Second hit
                (True, 0),  # Third hit
                (False, 0),  # Fourth hit (denied)
            ],
        },
        {
            "key": "test_client_2",
            "limit": 2,
            "window": 1,
            "expected_sequence": [
                (True, 1),  # First hit
                (True, 0),  # Second hit
                (False, 0),  # Third hit (denied)
            ],
        },
    ],
)
@pytest.mark.asyncio
async def test_redis_backend_rate_limiting(scenario):
    """Parametrized integration test for RedisBackend using FakeAsyncRedis client."""
    redis_client = fakeredis.FakeAsyncRedis(decode_responses=True)

    try:
        await redis_client.flushdb()

        backend = RedisBackend(redis_client)

        key = scenario["key"]
        limit = scenario["limit"]
        window = scenario["window"]
        expected_sequence = scenario["expected_sequence"]

        for expected_allowed, expected_remaining in expected_sequence:
            result = await backend.hit(key, limit, window)

            assert result.allowed == expected_allowed, f"Unexpected allowed status for {key}"
            assert result.remaining == expected_remaining, f"Unexpected remaining hits for {key}"

            assert result.reset > 0, "Reset time should be a positive timestamp"

    finally:
        await redis_client.aclose()


@pytest.mark.parametrize(
    "concurrent_hits",
    [
        {"key": "concurrent_client_1", "limit": 3, "window": 1, "total_hits": 4},
        {"key": "concurrent_client_2", "limit": 2, "window": 1, "total_hits": 3},
    ],
)
@pytest.mark.asyncio
async def test_redis_backend_concurrent_hits(concurrent_hits):
    """Parametrized test for concurrent rate limiting with multiple clients."""
    redis_client = fakeredis.FakeAsyncRedis(decode_responses=True)

    try:
        await redis_client.flushdb()

        backend = RedisBackend(redis_client)
        key = concurrent_hits["key"]
        limit = concurrent_hits["limit"]
        window = concurrent_hits["window"]
        total_hits = concurrent_hits["total_hits"]

        async def hit_backend():
            return await backend.hit(key, limit, window)

        results = await asyncio.gather(*[hit_backend() for _ in range(total_hits)])

        allowed_hits = [result for result in results if result.allowed is True]
        assert len(allowed_hits) == limit, f"Expected {limit} allowed hits"

        last_result = results[-1]
        assert last_result.allowed is False, "Last hit should be denied"
        assert last_result.remaining == 0, "Remaining hits should be 0 when rate limit is exceeded"

    finally:
        await redis_client.aclose()
