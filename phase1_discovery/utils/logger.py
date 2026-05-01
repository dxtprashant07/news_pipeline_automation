import logging
import logging.handlers
import re
from pathlib import Path


class SecretFilter(logging.Filter):
    """Replaces known secret values with [REDACTED] in every log record."""

    def __init__(self, secrets: list[str] | None = None):
        super().__init__()
        self._secrets: list[str] = secrets or []

    def update_secrets(self, secrets: list[str]) -> None:
        self._secrets = [s for s in secrets if s and len(s) > 4]

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self._redact(str(record.msg))
        record.args = tuple(self._redact(str(a)) for a in (record.args or ()))
        return True

    def _redact(self, text: str) -> str:
        for secret in self._secrets:
            text = text.replace(secret, "[REDACTED]")
        # Also catch apiKey=<anything> and apikey=<anything> in URLs
        text = re.sub(r"(api[_-]?key=)[^\s&\"']+", r"\1[REDACTED]", text, flags=re.IGNORECASE)
        return text


# Module-level filter instance so secrets can be updated after settings load
_secret_filter = SecretFilter()


def setup_logger(name: str = "news_pipeline", log_level: str = "INFO") -> logging.Logger:
    """
    Returns a configured logger that writes to both console and a rotating file.
    Call update_secrets() after settings are loaded to enable redaction.
    """
    Path("logs").mkdir(exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    if logger.handlers:
        return logger  # Already configured

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    console.addFilter(_secret_filter)
    logger.addHandler(console)

    # Rotating file — 5 MB × 3 files
    file_handler = logging.handlers.RotatingFileHandler(
        "logs/discovery.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    file_handler.addFilter(_secret_filter)
    logger.addHandler(file_handler)

    return logger


def update_secrets(secrets: list[str]) -> None:
    """Call this once settings are loaded to enable key redaction in logs."""
    _secret_filter.update_secrets(secrets)


def get_logger(name: str) -> logging.Logger:
    """Get a child logger under the main pipeline namespace."""
    return logging.getLogger(f"news_pipeline.{name}")
