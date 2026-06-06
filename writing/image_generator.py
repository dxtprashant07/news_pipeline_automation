"""
Image sourcing for articles (Stage 4).

Priority order:
  1. Source image captured from the original RSS / news feed (free, no API)
  2. Pollinations.ai AI generation (free, no API key required)
  3. DALL-E 3 generation (only if IMAGE_GENERATION_ENABLED=true and OPENAI_API_KEY set)
  4. Empty string (article published without featured image)
"""
import urllib.parse
import requests
from core.config.settings import get_settings
from core.utils.logger import get_logger

logger = get_logger("writing.image_generator")

# Minimum image dimensions we'll accept from the source feed (px)
_MIN_IMAGE_BYTES = 5_000   # reject tiny placeholder images (<5 KB)


def _is_usable_url(url: str) -> bool:
    """Quick validation — must be http(s) and not a known placeholder pattern."""
    if not url or not url.startswith(("http://", "https://")):
        return False
    bad_patterns = ("placeholder", "default", "blank", "no-image", "noimage", "1x1", "pixel")
    lower = url.lower()
    return not any(p in lower for p in bad_patterns)


def _probe_image(url: str) -> bool:
    """
    HEAD-request the URL to verify it's a real image and not tiny.
    Returns True if the image looks usable.
    """
    try:
        r = requests.head(url, timeout=5, allow_redirects=True)
        if r.status_code != 200:
            return False
        content_type = r.headers.get("content-type", "")
        if "image" not in content_type:
            return False
        content_length = int(r.headers.get("content-length", 0))
        if content_length and content_length < _MIN_IMAGE_BYTES:
            return False
        return True
    except Exception:
        return False


class ImageGenerator:
    def __init__(self) -> None:
        self.settings = get_settings()

    def generate(self, headline: str, category: str, source_image_url: str = "") -> str:
        """
        Return a usable image URL for the article.

        Args:
            headline:          Article headline (used for DALL-E prompt).
            category:          Article category.
            source_image_url:  Image URL captured from the original news source (RSS thumbnail).
                               Used first — no API cost.
        """
        # ── Priority 1: source image from RSS feed ────────────────────────────
        if _is_usable_url(source_image_url):
            if _probe_image(source_image_url):
                logger.debug(f"Using source image for '{headline[:50]}'")
                return source_image_url
            logger.debug(f"Source image failed probe: {source_image_url[:80]}")

        # ── Priority 2: Pollinations.ai (free, no API key) ───────────────────
        try:
            return self._call_pollinations(headline, category)
        except Exception as exc:
            logger.warning(f"Pollinations image failed for '{headline[:50]}': {exc!r}")

        # ── Priority 3: DALL-E generation ─────────────────────────────────────
        if self.settings.image_generation_enabled:
            if not self.settings.openai_api_key:
                logger.warning("IMAGE_GENERATION_ENABLED=true but OPENAI_API_KEY not set — skipping")
            else:
                try:
                    return self._call_dalle(headline, category)
                except Exception as exc:
                    logger.error(f"DALL-E generation failed for '{headline[:50]}': {exc!r}")

        return ""

    def _call_pollinations(self, headline: str, category: str) -> str:
        prompt = (
            f"professional editorial news photo, {headline}, "
            f"{category} news, photojournalistic style, "
            "no text, no watermarks, high quality"
        )
        encoded = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=1200&height=630&nologo=true&model=flux"

        r = requests.head(url, timeout=20, allow_redirects=True)
        if r.status_code == 200 and "image" in r.headers.get("content-type", ""):
            logger.info(f"Pollinations image ready for '{headline[:50]}'")
            return url

        raise ValueError(f"Pollinations returned status {r.status_code}")

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

        image_url = response.data[0].url or ""
        if image_url:
            logger.info(f"DALL-E image generated for '{headline[:50]}'")
        return image_url
