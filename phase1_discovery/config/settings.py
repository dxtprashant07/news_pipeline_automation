from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── News Sources ───────────────────────────────────────
    newsapi_key: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "NewsPipeline/1.0"

    # ── Database ───────────────────────────────────────────
    database_url: str = "sqlite:///./data/news_discovery.db"

    # ── Pipeline ───────────────────────────────────────────
    scheduler_interval_minutes: int = 30
    max_stories_per_run: int = 100
    min_credibility_score: int = 40

    # ── Geographic Focus ───────────────────────────────────
    geo_focus: str = "IN"

    # ── Logging ────────────────────────────────────────────
    log_level: str = "INFO"

    @field_validator("geo_focus")
    @classmethod
    def validate_geo(cls, v: str) -> str:
        allowed = {"IN", "US", "GB", "GLOBAL"}
        if v.upper() not in allowed:
            raise ValueError(f"geo_focus must be one of {allowed}")
        return v.upper()

    @property
    def secret_values(self) -> list[str]:
        """Returns all secret strings so the logger can redact them."""
        return [
            v for v in [
                self.newsapi_key,
                self.reddit_client_id,
                self.reddit_client_secret,
            ]
            if v and len(v) > 4
        ]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached singleton — raises clearly on missing/invalid values."""
    return Settings()
