from sqlalchemy.orm import Session

from .writer import ArticleWriter
from .seo_optimizer import SEOOptimizer
from .image_generator import ImageGenerator
from verification.models import VerificationResult, VerificationStatus
from core.db.repository import StoryRepository, DraftRepository
from core.config.settings import get_settings
from core.utils.logger import get_logger

logger = get_logger("writing.pipeline")


class WritingPipeline:
    """
    Stage 4 pipeline — reads 'fact_checked' stories, writes articles,
    generates SEO metadata and featured images, saves drafts.

    Output: ArticleDraft rows with status='pending_review' (ready for Stage 5).
    """

    def __init__(self, session: Session) -> None:
        self.session    = session
        self.settings   = get_settings()
        self.story_repo = StoryRepository(session)
        self.draft_repo = DraftRepository(session)
        self.writer     = ArticleWriter()
        self.seo        = SEOOptimizer()
        self.image_gen  = ImageGenerator()

    def run(self) -> dict:
        logger.info("Writing pipeline started")

        stories = self.story_repo.fetch_fact_checked(
            limit=self.settings.max_stories_per_run,
            min_credibility=self.settings.credibility_threshold,
        )

        if not stories:
            logger.info("No fact-checked stories ready for writing")
            return {"fetched": 0, "written": 0, "failed": 0}

        written = 0
        failed  = 0

        for story in stories:
            try:
                written += self._write_article(story)
            except Exception as exc:
                logger.error(f"Writing failed for story {story.id}: {exc!r}")
                self.story_repo.update_status(story.id, "fact_checked")
                failed += 1

        stats = self.draft_repo.get_stats()
        logger.info(
            f"Writing complete — written={written}, failed={failed}, "
            f"pending_review={stats['pending_review']}"
        )
        return {"fetched": len(stories), "written": written, "failed": failed}

    def _write_article(self, story) -> int:
        verification = VerificationResult(
            story_id=story.id,
            status=VerificationStatus.VERIFIED,
            source_count=0,
        )

        self.story_repo.update_status(story.id, "writing")

        draft          = self.writer.write(story, verification)
        draft.seo      = self.seo.optimize(draft.headline, draft.category, draft.article_html)
        draft.image_url = self.image_gen.generate(draft.headline, draft.category)

        self.draft_repo.save_draft(draft)
        self.story_repo.update_status(story.id, "written")

        logger.info(
            f"  Written: story {story.id} — {draft.word_count} words, "
            f"keyword='{draft.seo.focus_keyword}'"
        )
        return 1
