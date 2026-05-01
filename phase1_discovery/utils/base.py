from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

from .logger import get_logger

logger = get_logger("utils.base")


@dataclass
class RawStory:
    """
    Raw, unprocessed story as returned by a source.
    Every source MUST produce RawStory objects — nothing else flows downstream.
    """
    title: str
    url: str
    source_name: str                    # e.g. "NewsAPI", "Reddit", "GoogleTrends"
    published_at: datetime | None = None
    summary: str = ""
    author: str = ""
    image_url: str = ""
    extra: dict = field(default_factory=dict)  # source-specific metadata


class BaseSource(ABC):
    """
    Every data source inherits from this.
    Guarantees a consistent interface for the pipeline.
    """

    name: str = "base"  # Override in each subclass

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
