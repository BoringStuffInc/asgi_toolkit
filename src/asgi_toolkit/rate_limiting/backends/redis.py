import time
from typing import Protocol

from asgi_toolkit.rate_limiting.protocols import RateLimitingBackend, RateLimitResult


class RedisClientProtocol(Protocol):
    """Protocol for a Redis client with necessary rate limiting methods.

    Defines the minimum interface required by the RedisBackend.
    """

    async def incr(self, key: str) -> int:
        """Increments the number stored at key by one."""

    async def expire(self, key: str, seconds: int) -> bool:
        """Set a timeout on key."""

    async def ttl(self, key: str) -> int:
        """Get the time to live for a key."""


class RedisBackend(RateLimitingBackend):
    __slots__ = ("_redis_client",)

    def __init__(self, redis_client: RedisClientProtocol) -> None:
        """Initializes the Redis rate limiting backend.

        Args:
            redis_client: The Redis client to use.
        """
        self._redis_client = redis_client

    async def hit(self, key: str, limit: int, window: int) -> RateLimitResult:
        current_time = int(time.time())
        redis_key = f"rate_limit:{key}:{window}"

        count = await self._redis_client.incr(redis_key)

        if count == 1:
            await self._redis_client.expire(redis_key, window)

        ttl = await self._redis_client.ttl(redis_key)
        # If ttl is -1, the key has no expiry. If ttl is -2, the key does not exist.
        # In a rate limiting context, a key without expiry or a non-existent key
        # after incr and expire would be unexpected if the logic is correct.
        # However, to be safe, handle cases where ttl might be non-positive.
        if ttl <= 0:
            reset = current_time + window
        else:
            reset = current_time + ttl

        allowed = count <= limit
        remaining = max(0, limit - count)

        return RateLimitResult(allowed=allowed, remaining=remaining, reset=reset)
