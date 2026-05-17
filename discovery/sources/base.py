from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

from core.utils.logger import get_logger

logger = get_logger("utils.base")


@dataclass
class RawStory:
    """
    Raw, unprocessed story as returned by a source.
    Every source MUST produce RawStory objects — nothing else flows downstream.
    """
    title: str
    url: str
    source_name: str
    published_at: datetime | None = None
    summary: str = ""
    author: str = ""
    image_url: str = ""
    extra: dict = field(default_factory=dict)


class BaseSource(ABC):
    """Abstract base — every data source inherits from this."""

    name: str = "base"

    def __init__(self) -> None:
        self.logger = get_logger(f"sources.{self.name}")

    @abstractmethod
    def fetch(self) -> list[RawStory]:
        """
        Fetch stories from the source.
        Must return a list of RawStory objects (can be empty).
        Must NEVER raise — catch internally and return [].
        """
        ...

    def __repr__(self) -> str:
        return f"<Source: {self.name}>"
