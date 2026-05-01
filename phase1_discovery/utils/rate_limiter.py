import time
import threading
from dataclasses import dataclass, field

from .logger import get_logger

logger = get_logger("rate_limiter")


@dataclass
class RateLimiter:
    """
    Token-bucket rate limiter — thread-safe.

    Example:
        limiter = RateLimiter(calls=10, period=60)  # 10 calls per minute
        limiter.acquire()  # blocks if limit is hit
    """
    calls: int          # Max calls allowed per period
    period: float       # Period in seconds

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
        """Block until a token is available or timeout is reached."""
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


# Pre-built limiters for each external API (tune as needed)
LIMITERS: dict[str, RateLimiter] = {
    "newsapi":       RateLimiter(calls=100, period=3600),   # 100/hr free tier
    "google_trends": RateLimiter(calls=10,  period=60),     # unofficial, be gentle
    "reddit":        RateLimiter(calls=60,  period=60),     # 60/min OAuth
    "rss":           RateLimiter(calls=30,  period=60),
}


def get_limiter(name: str) -> RateLimiter:
    if name not in LIMITERS:
        # Default: 30 calls per minute
        LIMITERS[name] = RateLimiter(calls=30, period=60)
    return LIMITERS[name]
