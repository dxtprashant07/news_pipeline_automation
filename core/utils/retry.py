import time
import functools
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Any, Type

from .logger import get_logger

logger = get_logger("retry")


class CircuitState(Enum):
    CLOSED    = "closed"
    OPEN      = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    name: str
    failure_threshold: int = 3
    reset_timeout: int = 300

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _last_failure_time: datetime | None = field(default=None, init=False)

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if self._last_failure_time and \
               datetime.now() - self._last_failure_time > timedelta(seconds=self.reset_timeout):
                self._state = CircuitState.HALF_OPEN
                logger.info(f"Circuit [{self.name}] → HALF_OPEN")
        return self._state

    def record_success(self) -> None:
        self._failure_count = 0
        self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = datetime.now()
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(f"Circuit [{self.name}] → OPEN after {self._failure_count} failures")

    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN


_breakers: dict[str, CircuitBreaker] = {}


def get_breaker(name: str) -> CircuitBreaker:
    if name not in _breakers:
        _breakers[name] = CircuitBreaker(name=name)
    return _breakers[name]


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
    circuit_name: str | None = None,
):
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            breaker = get_breaker(circuit_name or func.__name__)
            if breaker.is_open():
                raise RuntimeError(f"Circuit [{breaker.name}] is OPEN — skipping call")

            last_exc: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    result = func(*args, **kwargs)
                    breaker.record_success()
                    return result
                except exceptions as exc:
                    last_exc = exc
                    breaker.record_failure()
                    if attempt < max_attempts:
                        delay = base_delay * (backoff_factor ** (attempt - 1))
                        logger.warning(
                            f"[{func.__name__}] attempt {attempt}/{max_attempts} failed: "
                            f"{exc}. Retrying in {delay:.1f}s…"
                        )
                        time.sleep(delay)
                    else:
                        logger.error(f"[{func.__name__}] all {max_attempts} attempts failed.")

            raise last_exc  # type: ignore[misc]

        return wrapper
    return decorator
