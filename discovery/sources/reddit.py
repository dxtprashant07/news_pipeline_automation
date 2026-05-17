from datetime import datetime, timezone

from .base import BaseSource, RawStory
from core.config.settings import get_settings
from discovery.config.categories import REDDIT_SUBREDDITS
from core.utils.rate_limiter import get_limiter
from core.utils.retry import with_retry


class RedditSource(BaseSource):
    name = "reddit"

    def __init__(self) -> None:
        super().__init__()
        self.settings = get_settings()
        self.limiter = get_limiter("reddit")

    def fetch(self) -> list[RawStory]:
        if not self.settings.reddit_client_id or not self.settings.reddit_client_secret:
            self.logger.warning("Reddit credentials not set — skipping Reddit source.")
            return []
        try:
            import praw
            self._reddit = praw.Reddit(
                client_id=self.settings.reddit_client_id,
                client_secret=self.settings.reddit_client_secret,
                user_agent=self.settings.reddit_user_agent,
            )
            return self._fetch_posts()
        except ImportError:
            self.logger.error("praw not installed. Run: pip install praw")
            return []
        except Exception as exc:
            self.logger.error(f"Reddit fetch failed: {exc}")
            return []

    @with_retry(max_attempts=2, base_delay=3.0, circuit_name="reddit")
    def _fetch_posts(self) -> list[RawStory]:
        stories: list[RawStory] = []
        all_subs    = [s for subs in REDDIT_SUBREDDITS.values() for s in subs]
        unique_subs = list(dict.fromkeys(all_subs))

        for sub_name in unique_subs[:8]:
            try:
                self.limiter.acquire()
                subreddit = self._reddit.subreddit(sub_name)
                for post in subreddit.hot(limit=10):
                    if post.is_self or not post.url:
                        continue
                    stories.append(RawStory(
                        title=post.title.strip(),
                        url=post.url,
                        source_name=f"reddit/r/{sub_name}",
                        published_at=datetime.fromtimestamp(post.created_utc, tz=timezone.utc),
                        summary=post.selftext[:300] if post.selftext else "",
                        image_url=post.thumbnail if post.thumbnail.startswith("http") else "",
                        extra={
                            "score":        post.score,
                            "num_comments": post.num_comments,
                            "subreddit":    sub_name,
                            "reddit_url":   f"https://reddit.com{post.permalink}",
                        },
                    ))
            except Exception as exc:
                self.logger.warning(f"Reddit r/{sub_name} failed: {exc}")
                continue

        self.logger.info(f"Reddit: fetched {len(stories)} posts")
        return stories
