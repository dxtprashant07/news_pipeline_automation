"""
Stage 6 — Auto-Publish & Distribute Pipeline.

Reads 'approved' drafts → publishes to WordPress → posts to social → triggers newsletter.
Everything runs in under 60 seconds per article (as per the proposal).
"""
from sqlalchemy.orm import Session

from .wordpress import WordPressPublisher
from .social.buffer import BufferDistributor
from .newsletter.mailchimp import MailchimpNewsletter
from core.db.repository import PublisherRepository, DraftRepository, StoryRepository
from core.config.settings import get_settings
from core.utils.logger import get_logger

logger = get_logger("publisher.pipeline")


class PublishingPipeline:
    """
    Reads approved drafts from the editorial queue and:
    1. Publishes to WordPress (REST API)
    2. Queues social posts via Buffer
    3. Triggers newsletter via Mailchimp
    4. Records the PublishedArticle row in the database
    """

    def __init__(self, session: Session) -> None:
        self.session      = session
        self.settings     = get_settings()
        self.pub_repo     = PublisherRepository(session)
        self.draft_repo   = DraftRepository(session)
        self.story_repo   = StoryRepository(session)
        self.wp           = WordPressPublisher()
        self.social       = BufferDistributor()
        self.newsletter   = MailchimpNewsletter()

    def run(self) -> dict:
        logger.info("Publishing pipeline started")

        drafts = self.pub_repo.get_unpublished_approved(limit=20)
        if not drafts:
            logger.info("No approved drafts ready for publishing")
            return {"published": 0, "failed": 0}

        published = 0
        failed    = 0

        for draft in drafts:
            try:
                published += self._publish_draft(draft)
            except Exception as exc:
                logger.error(f"Publishing failed for draft {draft.id}: {exc!r}")
                failed += 1

        logger.info(f"Publishing complete — published={published}, failed={failed}")
        return {"published": published, "failed": failed}

    def _publish_draft(self, draft) -> int:
        # 1. WordPress
        wp_post_id, wp_url = self.wp.publish(draft)

        # 2. Record in DB immediately (so social/newsletter failures don't block)
        pub_record = self.pub_repo.save_published(draft.id, wp_post_id, wp_url)

        # 3. Social distribution
        try:
            update_ids = self.social.post(draft.headline, wp_url, draft.category)
            pub_record.buffer_sent       = bool(update_ids)
            pub_record.buffer_update_ids = update_ids
            self.session.commit()
        except Exception as exc:
            logger.warning(f"Social post failed for draft {draft.id}: {exc!r}")

        # 4. Newsletter
        try:
            campaign_id = self.newsletter.send(draft.headline, wp_url, draft.article_html)
            if campaign_id:
                pub_record.newsletter_sent       = True
                pub_record.newsletter_campaign_id = campaign_id
                self.session.commit()
        except Exception as exc:
            logger.warning(f"Newsletter failed for draft {draft.id}: {exc!r}")

        # 5. Update story status to 'published'
        self.story_repo.update_status(draft.story_id, "published")

        logger.info(f"Published draft {draft.id} → {wp_url}")
        return 1
