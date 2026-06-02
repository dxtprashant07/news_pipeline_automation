"""Pipeline control endpoints -- trigger pipeline stages from the dashboard."""
import threading
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from dashboard.auth import require_api_key
from core.utils.logger import get_logger

logger = get_logger("dashboard.pipeline")
router = APIRouter(prefix="/pipeline", tags=["pipeline"], dependencies=[Depends(require_api_key)])

_status = {
    "running": False,
    "last_run": None,
    "last_result": None,
    "last_config": None,
    "stage_log": [],
}
_auto = {"enabled": False, "timer": None}


class RunConfig(BaseModel):
    article_count:   int            = Field(default=10,  ge=1, le=100)
    category:        Optional[str]  = Field(default=None)          # None = all
    word_count:      int            = Field(default=700, ge=200, le=3000)
    min_credibility: int            = Field(default=40,  ge=0,  le=100)
    run_discovery:   bool           = True
    run_verification: bool          = True
    run_writing:     bool           = True
    ai_model:        Optional[str]  = Field(default=None)          # None = use settings default


def _run_once(config: RunConfig):
    _status["running"]     = True
    _status["last_run"]    = datetime.now(timezone.utc).isoformat()
    _status["last_config"] = config.model_dump()
    _status["stage_log"]   = []

    def log_stage(stage: str, msg: str):
        _status["stage_log"].append({"stage": stage, "msg": msg, "ts": datetime.now(timezone.utc).isoformat()})
        logger.info(f"[{stage}] {msg}")

    try:
        from core.config.settings import get_settings
        from core.db.session import get_session_factory
        settings = get_settings()
        SessionFactory = get_session_factory(settings.database_url)

        if config.run_discovery:
            log_stage("discovery", "Starting discovery stage...")
            from discovery.pipeline import DiscoveryPipeline
            with SessionFactory() as session:
                result = DiscoveryPipeline(session).run(
                    category=config.category if config.category and config.category != "all" else None,
                    max_stories=config.article_count * 5,
                )
            log_stage("discovery", f"Done — {result.get('saved', 0)} new stories saved")

        if config.run_verification:
            log_stage("verification", "Starting verification stage...")
            from verification.pipeline import VerificationPipeline
            with SessionFactory() as session:
                result = VerificationPipeline(session).run()
            log_stage("verification", f"Done — {result.get('verified', 0)} stories verified")

        if config.run_writing:
            log_stage("writing", f"Writing up to {config.article_count} articles ({config.word_count} words each)...")
            from writing.pipeline import WritingPipeline
            with SessionFactory() as session:
                result = WritingPipeline(session).run(
                    article_count=config.article_count,
                    category=config.category if config.category and config.category != "all" else None,
                    word_count=config.word_count,
                    min_credibility=config.min_credibility,
                    ai_model=config.ai_model,
                )
            log_stage("writing", f"Done — {result.get('written', 0)} articles written, {result.get('failed', 0)} failed")

        _status["last_result"] = "success"
        logger.info("Pipeline run completed successfully")

    except Exception as exc:
        _status["last_result"] = f"error: {exc}"
        _status["stage_log"].append({"stage": "error", "msg": str(exc), "ts": datetime.now(timezone.utc).isoformat()})
        logger.exception("Pipeline run failed")
    finally:
        _status["running"] = False
        if _auto["enabled"]:
            _schedule_auto()


def _schedule_auto():
    if not _auto["enabled"]:
        return
    t = threading.Timer(1800, _auto_run)
    t.daemon = True
    t.name = "auto-pipeline-timer"
    _auto["timer"] = t
    t.start()


def _auto_run():
    if not _auto["enabled"] or _status["running"]:
        if _auto["enabled"]:
            _schedule_auto()
        return
    thread = threading.Thread(target=_run_once, args=(RunConfig(),), daemon=True, name="auto-pipeline-run")
    thread.start()


@router.get("/status")
def pipeline_status():
    return {
        "running":     _status["running"],
        "last_run":    _status["last_run"],
        "last_result": _status["last_result"],
        "last_config": _status["last_config"],
        "stage_log":   _status["stage_log"],
        "auto_mode":   _auto["enabled"],
    }


@router.post("/run")
def run_pipeline(config: RunConfig = RunConfig()):
    if _status["running"]:
        return {"status": "already_running"}
    thread = threading.Thread(target=_run_once, args=(config,), daemon=True, name="manual-pipeline-run")
    thread.start()
    return {"status": "started", "config": config.model_dump()}


@router.post("/auto")
def set_auto_mode(enabled: bool):
    _auto["enabled"] = enabled
    if enabled:
        _schedule_auto()
    else:
        if _auto["timer"]:
            _auto["timer"].cancel()
            _auto["timer"] = None
    return {"auto_mode": enabled}
