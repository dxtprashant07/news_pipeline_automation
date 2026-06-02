from datetime import datetime, timezone

from .base import BaseSource, RawStory
from core.config.settings import get_settings
from discovery.config.categories import TWITTER_NEWS_ACCOUNTS
from core.utils.rate_limiter import get_limiter
from core.utils.retry import with_retry


class TwitterSource(BaseSource):
    name = "twitter"

    def __init__(self) -> None:
        super().__init__()
        self.settings = get_settings()
        self.limiter = get_limiter("twitter")

    def fetch(self) -> list[RawStory]:
        if not self.settings.twitter_bearer_token:
            self.logger.warning("TWITTER_BEARER_TOKEN not set -- skipping Twitter source.")
            return []
        try:
            import tweepy
            self._client = tweepy.Client(
                bearer_token=self.settings.twitter_bearer_token,
                wait_on_rate_limit=False,
            )
            return self._fetch_tweets()
        except ImportError:
            self.logger.error("tweepy not installed. Run: pip install tweepy")
            return []
        except Exception as exc:
            self.logger.error(f"Twitter fetch failed: {exc}")
            return []

    @with_retry(max_attempts=2, base_delay=5.0, circuit_name="twitter")
    def _fetch_tweets(self) -> list[RawStory]:
        stories: list[RawStory] = []

        all_accounts = list(dict.fromkeys(
            acc for accs in TWITTER_NEWS_ACCOUNTS.values() for acc in accs
        ))

        for handle in all_accounts[:12]:
            try:
                self.limiter.acquire()
                user_resp = self._client.get_user(
                    username=handle,
                    user_fields=["id", "name"],
                )
                if not user_resp.data:
                    continue

                user_id   = user_resp.data.id
                user_name = user_resp.data.name

                tweets_resp = self._client.get_users_tweets(
                    id=user_id,
                    max_results=10,
                    tweet_fields=["created_at", "entities", "public_metrics"],
                    expansions=["attachments.media_keys"],
                    exclude=["retweets", "replies"],
                )
                if not tweets_resp.data:
                    continue

                for tweet in tweets_resp.data:
                    url = self._extract_url(tweet)
                    if not url:
                        url = f"https://x.com/{handle}/status/{tweet.id}"

                    metrics = tweet.public_metrics or {}
                    stories.append(RawStory(
                        title=tweet.text[:280].replace("\n", " ").strip(),
                        url=url,
                        source_name=f"twitter/@{handle}",
                        published_at=tweet.created_at or datetime.now(tz=timezone.utc),
                        summary=tweet.text,
                        extra={
                            "tweet_id":      str(tweet.id),
                            "twitter_handle": handle,
                            "display_name":  user_name,
                            "likes":         metrics.get("like_count", 0),
                            "retweets":      metrics.get("retweet_count", 0),
                            "tweet_url":     f"https://x.com/{handle}/status/{tweet.id}",
                        },
                    ))

            except Exception as exc:
                self.logger.warning(f"Twitter @{handle} failed: {exc}")
                continue

        self.logger.info(f"Twitter: fetched {len(stories)} tweets")
        return stories

    def _extract_url(self, tweet) -> str:
        """Return the first expanded external URL from a tweet's entities."""
        try:
            urls = (tweet.entities or {}).get("urls", [])
            for u in urls:
                expanded = u.get("expanded_url", "")
                if expanded and "t.co" not in expanded and "x.com" not in expanded and "twitter.com" not in expanded:
                    return expanded
        except Exception:
            pass
        return ""
