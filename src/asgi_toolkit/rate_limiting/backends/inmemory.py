import time

from asgi_toolkit.rate_limiting.protocols import RateLimitingBackend, RateLimitResult


class InMemoryBackend(RateLimitingBackend):
    __slots__ = ("_counters",)

    def __init__(self) -> None:
        self._counters: dict[tuple[str, int], dict[str, int]] = {}

    async def hit(self, key: str, limit: int, window: int) -> RateLimitResult:
        current_time = int(time.time())
        window_key = (key, window)

        self._cleanup_expired_entries(current_time)

        if window_key in self._counters:
            window_start_time = self._counters[window_key]["window_start_time"]
            if current_time >= window_start_time + window:
                del self._counters[window_key]

        if window_key not in self._counters:
            self._counters[window_key] = {"count": 0, "window_start_time": current_time}

        self._counters[window_key]["count"] += 1

        count = self._counters[window_key]["count"]
        window_start_time = self._counters[window_key]["window_start_time"]

        allowed = count <= limit
        remaining = max(0, limit - count)
        reset = window_start_time + window

        return RateLimitResult(allowed=allowed, remaining=remaining, reset=reset)

    def _cleanup_expired_entries(self, current_time: int) -> None:
        expired_keys = [
            window_key
            for window_key, data in self._counters.items()
            if current_time >= data["window_start_time"] + window_key[1]
        ]
        for key in expired_keys:
            del self._counters[key]
