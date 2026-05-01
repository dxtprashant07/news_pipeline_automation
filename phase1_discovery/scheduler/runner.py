from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, JobExecutionEvent

from ..config.settings import get_settings
from ..storage.database import get_session_factory
from ..pipeline import DiscoveryPipeline
from ..utils.logger import get_logger

logger = get_logger("scheduler")


def _run_pipeline() -> None:
    """Single pipeline execution — called by the scheduler."""
    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)

    with SessionFactory() as session:
        pipeline = DiscoveryPipeline(session)
        summary = pipeline.run()

    logger.info(
        f"[Scheduler] Run complete — "
        f"saved {summary['saved']} | "
        f"db_total={summary['db_total']} | "
        f"new={summary['db_new']}"
    )


def _on_job_event(event: JobExecutionEvent) -> None:
    if event.exception:
        logger.error(f"[Scheduler] Job FAILED: {event.exception}")
    else:
        logger.debug("[Scheduler] Job succeeded")


def start_scheduler() -> None:
    settings = get_settings()
    interval = settings.scheduler_interval_minutes

    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        _run_pipeline,
        trigger=IntervalTrigger(minutes=interval),
        id="discovery_pipeline",
        name="News Discovery",
        max_instances=1,        # Never run overlapping instances
        misfire_grace_time=120, # If a run was missed, allow 2 min grace
        replace_existing=True,
    )
    scheduler.add_listener(_on_job_event, EVENT_JOB_ERROR | EVENT_JOB_EXECUTED)

    logger.info(f"Scheduler starting — pipeline runs every {interval} minutes")
    logger.info("Press Ctrl+C to stop.\n")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user.")
        scheduler.shutdown(wait=False)
