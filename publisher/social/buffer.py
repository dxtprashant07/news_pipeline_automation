"""
Buffer API v1 social distribution.
Posts approved articles to all configured Buffer profiles (Twitter/X, LinkedIn, Facebook).

Docs: https://buffer.com/developers/api
"""
import requests
from .base import SocialChannel
from core.config.settings import get_settings
from core.utils.rate_limiter import get_limiter

BUFFER_API = "https://api.bufferapp.com/1"


class BufferDistributor(SocialChannel):
    name = "buffer"

    def __init__(self) -> None:
        super().__init__()
        self.settings = get_settings()
        self.limiter  = get_limiter("buffer")

    def post(self, headline: str, post_url: str, category: str) -> list[str]:
        if not self.settings.buffer_access_token:
            self.logger.warning("BUFFER_ACCESS_TOKEN not set — skipping social distribution")
            return []
        profile_ids = self.settings.buffer_profile_id_list
        if not profile_ids:
            self.logger.warning("BUFFER_PROFILE_IDS not set — skipping social distribution")
            return []

        update_ids: list[str] = []
        text = f"{headline}\n\n{post_url} #{category}"

        for profile_id in profile_ids:
            try:
                self.limiter.acquire()
                resp = requests.post(
                    f"{BUFFER_API}/updates/create.json",
                    data={
                        "access_token": self.settings.buffer_access_token,
                        "profile_ids[]": profile_id,
                        "text": text,
                    },
                    timeout=15,
                )
                resp.raise_for_status()
                update_id = resp.json().get("updates", [{}])[0].get("id", "")
                if update_id:
                    update_ids.append(update_id)
                    self.logger.info(f"Queued to Buffer profile {profile_id}: {update_id}")
            except Exception as exc:
                self.logger.error(f"Buffer post failed for profile {profile_id}: {exc!r}")

        return update_ids
