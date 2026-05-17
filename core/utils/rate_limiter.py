import time
import threading
from dataclasses import dataclass, field

from .logger import get_logger

logger = get_logger("rate_limiter")


@dataclass
class RateLimiter:
    """Token-bucket rate limiter — thread-safe."""
    calls: int
    period: float

    _tokens: float = field(init=False)
    _last_refill: float = field(init=False)
    _lock: threading.Lock = field(init=False)

    def __post_init__(self) -> None:
        self._tokens = float(self.calls)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        added = elapsed * (self.calls / self.period)
        self._tokens = min(float(self.calls), self._tokens + added)
        self._last_refill = now

    def acquire(self, timeout: float = 60.0) -> None:
        deadline = time.monotonic() + timeout
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
            wait = 1 / (self.calls / self.period)
            if time.monotonic() + wait > deadline:
                raise TimeoutError("Rate limiter timed out waiting for a token.")
            logger.debug(f"Rate limit reached — waiting {wait:.2f}s")
            time.sleep(wait)


LIMITERS: dict[str, RateLimiter] = {
    "newsapi":       RateLimiter(calls=100, period=3600),
    "google_trends": RateLimiter(calls=10,  period=60),
    "reddit":        RateLimiter(calls=60,  period=60),
    "rss":           RateLimiter(calls=30,  period=60),
    "bing_search":   RateLimiter(calls=100, period=60),
    "wordpress":     RateLimiter(calls=60,  period=60),
    "buffer":        RateLimiter(calls=100, period=3600),
}


def get_limiter(name: str) -> RateLimiter:
    if name not in LIMITERS:
        LIMITERS[name] = RateLimiter(calls=30, period=60)
    return LIMITERS[name]
