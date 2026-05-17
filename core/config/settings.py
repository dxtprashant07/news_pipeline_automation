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

    # ── Database ───────────────────────────────────────────
    database_url: str = "sqlite:///./news.db"

    # ── Logging ────────────────────────────────────────────
    log_level: str = "INFO"

    # ── Geographic Focus ───────────────────────────────────
    geo_focus: str = "IN"

    # ── News Sources (Stage 1) ─────────────────────────────
    newsapi_key: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "NewsPipeline/1.0"

    # ── Discovery Scheduler ────────────────────────────────
    discovery_interval_minutes: int = 30
    max_stories_per_run: int = 100
    min_credibility_score: int = 40

    # ── AI Providers (Stage 3 + 4) ─────────────────────────
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""

    # Model routing — provider inferred from model name prefix:
    #   claude-*  → Anthropic   |  gpt-* / o1-* → OpenAI   |  gemini-* → Google
    article_model: str = "claude-sonnet-4-6"
    seo_model: str = ""          # falls back to article_model if empty

    # ── Fact Verification (Stage 3) ────────────────────────
    bing_search_api_key: str = ""
    min_verification_sources: int = 3
    credibility_threshold: int = 75
    verification_timeout_seconds: int = 10

    # ── Article Writing (Stage 4) ──────────────────────────
    article_word_count: int = 700
    article_max_tokens: int = 2048

    # ── Image Generation (Stage 4) ─────────────────────────
    image_generation_enabled: bool = False
    dalle_model: str = "dall-e-3"

    # ── Verification + Writing Scheduler ──────────────────
    pipeline_interval_minutes: int = 60

    # ── Dashboard (Stage 5) ────────────────────────────────
    dashboard_host: str = "127.0.0.1"
    dashboard_port: int = 8000
    dashboard_secret_key: str = ""
    dashboard_api_key: str = ""       # Set in production to protect the dashboard
    cors_origins: str = "http://localhost:8000,http://127.0.0.1:8000"

    # ── WordPress Publisher (Stage 6) ──────────────────────
    wordpress_url: str = ""          # e.g. https://yoursite.com
    wordpress_username: str = ""
    wordpress_app_password: str = "" # Application Password from WP settings

    # ── Social Distribution (Stage 6) ─────────────────────
    buffer_access_token: str = ""
    buffer_profile_ids: list[str] = []

    # ── Newsletter (Stage 6) ───────────────────────────────
    mailchimp_api_key: str = ""
    mailchimp_list_id: str = ""

    # ── Analytics (Stage 7) ────────────────────────────────
    ga4_property_id: str = ""
    google_service_account_json: str = ""  # path to service account key file

    @field_validator("geo_focus")
    @classmethod
    def validate_geo(cls, v: str) -> str:
        allowed = {"IN", "US", "GB", "GLOBAL"}
        if v.upper() not in allowed:
            raise ValueError(f"geo_focus must be one of {allowed}")
        return v.upper()

    @field_validator("dashboard_secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        bad = {"change-me-in-production", "secret", "password", ""}
        if v.lower() in bad:
            import warnings
            warnings.warn(
                "DASHBOARD_SECRET_KEY is not set or uses an insecure default. "
                "Set a strong random value in your .env file.",
                stacklevel=2,
            )
        return v

    @property
    def resolved_seo_model(self) -> str:
        return self.seo_model or self.article_model

    @property
    def secret_values(self) -> list[str]:
        return [
            v for v in [
                self.newsapi_key,
                self.reddit_client_id,
                self.reddit_client_secret,
                self.anthropic_api_key,
                self.openai_api_key,
                self.gemini_api_key,
                self.bing_search_api_key,
                self.wordpress_app_password,
                self.buffer_access_token,
                self.mailchimp_api_key,
                self.dashboard_secret_key,
            ]
            if v and len(v) > 4
        ]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
