from abc import ABC, abstractmethod
from core.utils.logger import get_logger


class SocialChannel(ABC):
    """Abstract base for all social distribution channels."""

    name: str = "base"

    def __init__(self) -> None:
        self.logger = get_logger(f"publisher.social.{self.name}")

    @abstractmethod
    def post(self, headline: str, post_url: str, category: str) -> list[str]:
        """
        Post an approved article to this channel.
        Returns list of update/post IDs created.
        Must never raise — return [] on failure.
        """
        ...
