"""
Unified APScheduler runner — manages all pipeline job schedules.

Jobs:
  - Discovery (Stage 1+2)   : every DISCOVERY_INTERVAL_MINUTES (default 30)
  - Verification (Stage 3)  : every PIPELINE_INTERVAL_MINUTES (default 60)
  - Writing (Stage 4)       : every PIPELINE_INTERVAL_MINUTES (default 60)
  - Publishing (Stage 6)    : every 15 minutes after editorial approval
  - Analytics (Stage 7)     : daily at 6 AM

The dashboard (Stage 5) is a separate FastAPI process — not scheduled.
"""
import signal
import sys
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from core.utils.logger import get_logger

logger = get_logger("scheduler.runner")


def _run_discovery(SessionFactory):
    from discovery.pipeline import DiscoveryPipeline
    logger.info("Scheduler → Running discovery pipeline")
    try:
        with SessionFactory() as session:
            summary = DiscoveryPipeline(session).run()
        logger.info(f"Discovery done — saved {summary.get('saved', 0)} stories")
    except Exception as exc:
        logger.error(f"Discovery job failed: {exc!r}")


def _run_verification(SessionFactory):
    from verification.pipeline import VerificationPipeline
    logger.info("Scheduler → Running verification pipeline")
    try:
        with SessionFactory() as session:
            summary = VerificationPipeline(session).run()
        logger.info(f"Verification done — {summary.get('verified', 0)} verified")
    except Exception as exc:
        logger.error(f"Verification job failed: {exc!r}")


def _run_writing(SessionFactory):
    from writing.pipeline import WritingPipeline
    logger.info("Scheduler → Running writing pipeline")
    try:
        with SessionFactory() as session:
            summary = WritingPipeline(session).run()
        logger.info(f"Writing done — {summary.get('written', 0)} articles written")
    except Exception as exc:
        logger.error(f"Writing job failed: {exc!r}")


def _run_publishing(SessionFactory):
    from publisher.pipeline import PublishingPipeline
    logger.info("Scheduler → Running publishing pipeline")
    try:
        with SessionFactory() as session:
            summary = PublishingPipeline(session).run()
        logger.info(f"Publishing done — {summary.get('published', 0)} published")
    except Exception as exc:
        logger.error(f"Publishing job failed: {exc!r}")


def _run_analytics(SessionFactory):
    from analytics.collector import AnalyticsCollector
    from analytics.scorer import FeedbackScorer
    logger.info("Scheduler → Running analytics pipeline")
    try:
        with SessionFactory() as session:
            summary = AnalyticsCollector(session).collect()
            FeedbackScorer(session).update_priority_scores()
        logger.info(f"Analytics done — collected={summary.get('collected', 0)}")
    except Exception as exc:
        logger.error(f"Analytics job failed: {exc!r}")


def start_all_pipelines(SessionFactory, settings):
    """
    Start all pipeline jobs on their configured schedules.
    Blocks until Ctrl-C or SIGTERM.
    """
    scheduler = BlockingScheduler()

    scheduler.add_job(
        _run_discovery,
        trigger=IntervalTrigger(minutes=settings.discovery_interval_minutes),
        args=[SessionFactory],
        id="discovery",
        name="Discovery Pipeline (Stage 1+2)",
        replace_existing=True,
    )

    scheduler.add_job(
        _run_verification,
        trigger=IntervalTrigger(minutes=settings.pipeline_interval_minutes),
        args=[SessionFactory],
        id="verification",
        name="Verification Pipeline (Stage 3)",
        replace_existing=True,
    )

    scheduler.add_job(
        _run_writing,
        trigger=IntervalTrigger(minutes=settings.pipeline_interval_minutes),
        args=[SessionFactory],
        id="writing",
        name="Writing Pipeline (Stage 4)",
        replace_existing=True,
    )

    scheduler.add_job(
        _run_publishing,
        trigger=IntervalTrigger(minutes=15),
        args=[SessionFactory],
        id="publishing",
        name="Publishing Pipeline (Stage 6)",
        replace_existing=True,
    )

    scheduler.add_job(
        _run_analytics,
        trigger=CronTrigger(hour=6, minute=0),
        args=[SessionFactory],
        id="analytics",
        name="Analytics Feedback Loop (Stage 7)",
        replace_existing=True,
    )

    def _shutdown(signum, frame):
        logger.info("Shutdown signal received — stopping scheduler")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logger.info(
        f"Scheduler started — "
        f"discovery every {settings.discovery_interval_minutes}m, "
        f"pipeline every {settings.pipeline_interval_minutes}m, "
        f"publishing every 15m, analytics daily at 06:00"
    )
    scheduler.start()


def start_discovery_scheduler(SessionFactory, settings):
    """Lightweight scheduler — discovery only (used by python -m discovery)."""
    scheduler = BlockingScheduler()
    scheduler.add_job(
        _run_discovery,
        trigger=IntervalTrigger(minutes=settings.discovery_interval_minutes),
        args=[SessionFactory],
        id="discovery",
        replace_existing=True,
    )
    logger.info(f"Discovery scheduler started — every {settings.discovery_interval_minutes}m")
    scheduler.start()
