"""
Image Generation Agent (Stage 4) — generates featured images using DALL-E 3.
Only runs when IMAGE_GENERATION_ENABLED=true in .env.
"""
import requests
from core.config.settings import get_settings
from core.utils.logger import get_logger

logger = get_logger("writing.image_generator")


class ImageGenerator:
    def __init__(self) -> None:
        self.settings = get_settings()

    def generate(self, headline: str, category: str) -> str:
        """
        Generate a featured image for the article.
        Returns a URL string (empty string if disabled or failed).
        """
        if not self.settings.image_generation_enabled:
            return ""
        if not self.settings.openai_api_key:
            logger.warning("IMAGE_GENERATION_ENABLED=true but OPENAI_API_KEY not set — skipping")
            return ""

        try:
            return self._call_dalle(headline, category)
        except Exception as exc:
            logger.error(f"Image generation failed for '{headline[:60]}': {exc!r}")
            return ""

    def _call_dalle(self, headline: str, category: str) -> str:
        import openai
        client = openai.OpenAI(api_key=self.settings.openai_api_key)

        prompt = (
            f"A professional, photojournalistic featured image for a news article. "
            f"Topic: {headline}. Category: {category}. "
            "Clean, editorial style. No text or watermarks."
        )

        response = client.images.generate(
            model=self.settings.dalle_model,
            prompt=prompt,
            n=1,
            size="1792x1024",
            quality="standard",
        )

        image_url = response.data[0].url
        logger.info(f"Image generated for '{headline[:50]}'")
        return image_url or ""
