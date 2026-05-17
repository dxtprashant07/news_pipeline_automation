"""
Mailchimp newsletter trigger — sends a campaign to the subscriber list
when an article is published.

Uses Mailchimp Marketing API v3.
Docs: https://mailchimp.com/developer/marketing/api/campaigns/
"""
import requests
from core.config.settings import get_settings
from core.utils.logger import get_logger

logger = get_logger("publisher.newsletter.mailchimp")


class MailchimpNewsletter:
    def __init__(self) -> None:
        self.settings = get_settings()

    def send(self, headline: str, post_url: str, article_html: str) -> str:
        """
        Create and send a Mailchimp campaign for the article.
        Returns campaign_id on success, "" on failure or if not configured.
        """
        if not self.settings.mailchimp_api_key or not self.settings.mailchimp_list_id:
            logger.info("Mailchimp not configured — skipping newsletter send")
            return ""

        try:
            return self._create_and_send(headline, post_url, article_html)
        except Exception as exc:
            logger.error(f"Mailchimp send failed: {exc!r}")
            return ""

    def _create_and_send(self, headline: str, post_url: str, article_html: str) -> str:
        key    = self.settings.mailchimp_api_key
        dc     = key.split("-")[-1]
        base   = f"https://{dc}.api.mailchimp.com/3.0"
        headers = {"Authorization": f"apikey {key}", "Content-Type": "application/json"}

        # 1. Create campaign
        campaign_resp = requests.post(
            f"{base}/campaigns",
            headers=headers,
            json={
                "type": "regular",
                "recipients": {"list_id": self.settings.mailchimp_list_id},
                "settings": {
                    "subject_line": headline,
                    "from_name":    "News Pipeline",
                    "reply_to":     "noreply@yoursite.com",
                },
            },
            timeout=15,
        )
        campaign_resp.raise_for_status()
        campaign_id = campaign_resp.json()["id"]

        # 2. Set content
        requests.put(
            f"{base}/campaigns/{campaign_id}/content",
            headers=headers,
            json={"html": f"<h1>{headline}</h1>{article_html}<p><a href='{post_url}'>Read full article</a></p>"},
            timeout=15,
        ).raise_for_status()

        # 3. Send
        requests.post(f"{base}/campaigns/{campaign_id}/actions/send",
                      headers=headers, timeout=15).raise_for_status()

        logger.info(f"Mailchimp campaign sent: {campaign_id}")
        return campaign_id
