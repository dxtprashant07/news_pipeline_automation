from sqlalchemy.orm import Session

from .fact_checker import FactChecker
from .models import VerificationStatus
from core.db.repository import StoryRepository, DraftRepository
from core.config.settings import get_settings
from core.utils.logger import get_logger

logger = get_logger("verification.pipeline")


class VerificationPipeline:
    """
    Stage 3 pipeline — reads 'new' stories, fact-checks each one, updates status.

    Verified stories move to 'fact_checked' and are ready for the writing pipeline.
    Rejected stories move to 'rejected' and are logged for weekly review.
    """

    def __init__(self, session: Session) -> None:
        self.session      = session
        self.settings     = get_settings()
        self.story_repo   = StoryRepository(session)
        self.draft_repo   = DraftRepository(session)
        self.fact_checker = FactChecker()

    def run(self) -> dict:
        logger.info("Verification pipeline started")

        stories = self.story_repo.fetch_new(
            limit=self.settings.max_stories_per_run,
            min_credibility=self.settings.min_credibility_score,
        )

        if not stories:
            logger.info("No new stories to verify")
            return {"fetched": 0, "verified": 0, "rejected": 0}

        verified = 0
        rejected = 0

        for story in stories:
            try:
                self.story_repo.update_status(story.id, "fact_checking")
                result = self.fact_checker.check(story)
                self.draft_repo.save_fact_check(result)

                if result.status == VerificationStatus.VERIFIED:
                    self.story_repo.update_status(story.id, "fact_checked")
                    verified += 1
                else:
                    self.story_repo.update_status(story.id, "rejected")
                    rejected += 1
                    logger.info(f"  Rejected story {story.id}: {result.rejection_reason}")
            except Exception:
                logger.exception(f"  Error processing story {story.id} — skipping")
                self.story_repo.update_status(story.id, "new")  # reset so it retries next run

        logger.info(f"Verification complete — {verified} verified, {rejected} rejected")
        return {"fetched": len(stories), "verified": verified, "rejected": rejected}
