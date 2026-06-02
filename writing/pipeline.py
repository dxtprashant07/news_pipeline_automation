from sqlalchemy.orm import Session

from .writer import ArticleWriter
from .seo_optimizer import SEOOptimizer
from .seo_scorer import SEOScorer
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
        self.seo_scorer = SEOScorer()
        self.image_gen  = ImageGenerator()

    def run(
        self,
        article_count: int | None = None,
        category: str | None = None,
        word_count: int | None = None,
        min_credibility: int | None = None,
        ai_model: str | None = None,
        max_age_hours: int = 48,
    ) -> dict:
        limit    = article_count   if article_count   is not None else self.settings.max_stories_per_run
        min_cred = min_credibility if min_credibility is not None else self.settings.credibility_threshold
        wc       = word_count      if word_count      is not None else self.settings.article_word_count
        model    = ai_model        if ai_model        is not None else self.settings.article_model

        logger.info(
            f"Writing pipeline started — limit={limit}, category={category or 'all'}, "
            f"words={wc}, model={model}, min_cred={min_cred}"
        )

        stories = self.story_repo.fetch_fact_checked(
            limit=limit,
            min_credibility=min_cred,
            category=category,
            max_age_hours=max_age_hours,
        )

        if not stories:
            logger.info("No fact-checked stories ready for writing")
            return {"fetched": 0, "written": 0, "failed": 0}

        written = 0
        failed  = 0

        for story in stories:
            try:
                written += self._write_article(story, word_count=wc, ai_model=model)
            except Exception as exc:
                logger.error(f"Writing failed for story {story.id}: {exc!r}")
                self.story_repo.update_status(story.id, "fact_checked")
                failed += 1

        stats = self.draft_repo.get_stats()
        logger.info(
            f"Writing complete -- written={written}, failed={failed}, "
            f"pending_review={stats['pending_review']}"
        )
        return {"fetched": len(stories), "written": written, "failed": failed}

    def _write_article(self, story, word_count: int | None = None, ai_model: str | None = None) -> int:
        verification = VerificationResult(
            story_id=story.id,
            status=VerificationStatus.VERIFIED,
            source_count=0,
        )

        # Pre-compute focus keyword BEFORE writing so it can be woven into the article.
        focus_keyword, secondary_keywords = self.seo.get_keywords(
            headline=story.title,
            category=story.category,
            summary=story.summary or "",
        )

        self.story_repo.update_status(story.id, "writing")

        draft = self.writer.write(
            story, verification,
            word_count=word_count,
            ai_model=ai_model,
            focus_keyword=focus_keyword,
            secondary_keywords=secondary_keywords,
        )
        # Full SEO pass now that the complete article exists (keyword already woven in).
        draft.seo = self.seo.optimize(draft.headline, draft.category, draft.article_html)
        # Image: use RSS thumbnail first (free), fall back to DALL-E if enabled.
        draft.image_url = self.image_gen.generate(
            draft.headline,
            draft.category,
            source_image_url=story.image_url or "",
        )

        seo_result = self.seo_scorer.score(
            headline=draft.headline,
            meta_title=draft.seo.meta_title,
            meta_description=draft.seo.meta_description,
            focus_keyword=draft.seo.focus_keyword,
            secondary_keywords=draft.seo.secondary_keywords,
            article_html=draft.article_html,
            word_count=draft.word_count,
        )
        draft.seo_score    = seo_result.total
        draft.seo_breakdown = seo_result.to_dict()

        self.draft_repo.save_draft(draft)
        self.story_repo.update_status(story.id, "written")

        logger.info(
            f"  Written: story {story.id} — {draft.word_count} words, "
            f"keyword='{draft.seo.focus_keyword}', SEO={draft.seo_score}/100 ({seo_result.grade})"
        )
        return 1
