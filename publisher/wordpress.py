"""
Stage 6 — WordPress REST API client.

Publishes approved article drafts to WordPress using Application Passwords.
No plugins required — uses the built-in WP REST API.

Docs: https://developer.wordpress.org/rest-api/reference/posts/
"""
import base64
import requests
from core.config.settings import get_settings
from core.utils.logger import get_logger
from core.utils.rate_limiter import get_limiter

logger = get_logger("publisher.wordpress")


class WordPressPublisher:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.limiter  = get_limiter("wordpress")

    @property
    def _auth_header(self) -> dict:
        credentials = f"{self.settings.wordpress_username}:{self.settings.wordpress_app_password}"
        token = base64.b64encode(credentials.encode()).decode()
        return {"Authorization": f"Basic {token}"}

    def publish(self, draft) -> tuple[int, str]:
        """
        Publish an approved ArticleDraft to WordPress.

        Returns (wp_post_id, wp_post_url).
        Raises on failure — caller handles exception.
        """
        if not self.settings.wordpress_url:
            raise ValueError("WORDPRESS_URL not set in .env")
        if not self.settings.wordpress_username or not self.settings.wordpress_app_password:
            raise ValueError("WORDPRESS_USERNAME and WORDPRESS_APP_PASSWORD must be set in .env")

        self.limiter.acquire()

        endpoint = f"{self.settings.wordpress_url.rstrip('/')}/wp-json/wp/v2/posts"

        payload = {
            "title":        draft.headline,
            "content":      draft.article_html,
            "status":       "publish",
            "categories":   self._resolve_category(draft.category),
            "tags":         draft.secondary_keywords or [],
            "meta": {
                "_yoast_wpseo_title":          draft.meta_title,
                "_yoast_wpseo_metadesc":       draft.meta_description,
                "_yoast_wpseo_focuskw":        draft.focus_keyword,
            },
            "excerpt": draft.meta_description,
        }

        if draft.image_url:
            media_id = self._upload_image(draft.image_url, draft.headline)
            if media_id:
                payload["featured_media"] = media_id

        resp = requests.post(
            endpoint,
            headers={**self._auth_header, "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        post_id  = data["id"]
        post_url = data["link"]
        logger.info(f"Published to WordPress: post_id={post_id} url={post_url}")
        return post_id, post_url

    def _resolve_category(self, category_name: str) -> list[int]:
        """Look up or create a WordPress category by name. Returns [category_id]."""
        endpoint = f"{self.settings.wordpress_url.rstrip('/')}/wp-json/wp/v2/categories"
        try:
            resp = requests.get(
                endpoint,
                headers=self._auth_header,
                params={"search": category_name, "per_page": 5},
                timeout=10,
            )
            resp.raise_for_status()
            cats = resp.json()
            if cats:
                return [cats[0]["id"]]

            # Create it
            create_resp = requests.post(
                endpoint,
                headers={**self._auth_header, "Content-Type": "application/json"},
                json={"name": category_name},
                timeout=10,
            )
            create_resp.raise_for_status()
            return [create_resp.json()["id"]]
        except Exception as exc:
            logger.warning(f"Category lookup/create failed for '{category_name}': {exc}")
            return []

    def _upload_image(self, image_url: str, title: str) -> int | None:
        """Download an image URL and upload it to WordPress media library."""
        try:
            img_data = requests.get(image_url, timeout=15).content
            endpoint = f"{self.settings.wordpress_url.rstrip('/')}/wp-json/wp/v2/media"
            resp = requests.post(
                endpoint,
                headers={
                    **self._auth_header,
                    "Content-Disposition": f'attachment; filename="{title[:50]}.png"',
                    "Content-Type": "image/png",
                },
                data=img_data,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()["id"]
        except Exception as exc:
            logger.warning(f"Image upload failed: {exc}")
            return None
