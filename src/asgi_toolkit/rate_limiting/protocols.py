from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from asgi_toolkit.protocol import HTTPRequestScope


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    """
    Represents the result of a rate limit check.

    Attributes:
        allowed (bool): Whether the request is allowed.
        remaining (int): Number of remaining requests in the current window.
        reset (float): Timestamp when the rate limit window resets.
    """

    allowed: bool
    remaining: int
    reset: float

    def __post_init__(self) -> None:
        """
        Validate the result attributes.
        """
        if not isinstance(self.allowed, bool):
            raise TypeError("'allowed' must be a boolean")
        if not isinstance(self.remaining, int):
            raise TypeError("'remaining' must be an integer")
        if self.remaining < 0:
            raise ValueError("'remaining' must be non-negative")
        if not isinstance(self.reset, (int, float)):
            raise TypeError("'reset' must be a number")


class RateLimitingBackend(Protocol):
    async def hit(self, key: str, limit: int, window: int) -> RateLimitResult:
        """
        Registers a hit for the given key and checks if the limit is exceeded within the window.

        Args:
            key: The unique key for the client/route combination. Must not be empty.
            limit: The maximum number of requests allowed. Must be positive.
            window: The time window in seconds. Must be positive.

        Returns:
            A RateLimitResult containing:
            - allowed: True if the request is allowed, False otherwise.
            - remaining: The number of remaining requests allowed (always >= 0).
            - reset: The timestamp (in seconds) when the rate limit resets.
        """


class Counter(Protocol):
    def inc(self) -> None:
        """Increment the counter."""


class MetricsCollector(Protocol):
    def counter(self, name: str, description: str) -> Counter:
        """Create a counter metric."""


IdentityExtractor = Callable[[HTTPRequestScope], Awaitable[str]]
