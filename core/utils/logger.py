import logging
import logging.handlers
import re
from pathlib import Path


class SecretFilter(logging.Filter):
    def __init__(self, secrets: list[str] | None = None):
        super().__init__()
        self._secrets: list[str] = secrets or []

    def update_secrets(self, secrets: list[str]) -> None:
        self._secrets = [s for s in secrets if s and len(s) > 4]

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg  = self._redact(str(record.msg))
        record.args = tuple(self._redact(str(a)) for a in (record.args or ()))
        return True

    def _redact(self, text: str) -> str:
        for secret in self._secrets:
            text = text.replace(secret, "[REDACTED]")
        text = re.sub(r"(api[_-]?key=)[^\s&\"']+", r"\1[REDACTED]", text, flags=re.IGNORECASE)
        return text


_secret_filter = SecretFilter()


def setup_logger(name: str = "news_pipeline", log_level: str = "INFO", log_file: str = "pipeline.log") -> logging.Logger:
    Path("logs").mkdir(exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    console.addFilter(_secret_filter)
    logger.addHandler(console)

    file_handler = logging.handlers.RotatingFileHandler(
        f"logs/{log_file}",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    file_handler.addFilter(_secret_filter)
    logger.addHandler(file_handler)

    return logger


def update_secrets(secrets: list[str]) -> None:
    _secret_filter.update_secrets(secrets)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"news_pipeline.{name}")
