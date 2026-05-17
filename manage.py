#!/usr/bin/env python
"""
manage.py — Unified CLI entry point for the News Automation Pipeline.

Usage:
  python manage.py start        [--dev]              # ONE COMMAND: init db + pipeline + dashboard
  python manage.py discover     [--once | --stats]   # Stage 1+2: Discovery
  python manage.py verify       [--once | --stats]   # Stage 3:   Fact Verification
  python manage.py write        [--once | --stats]   # Stage 4:   AI Writing
  python manage.py dashboard    [--dev]              # Stage 5:   Editor Dashboard (FastAPI)
  python manage.py publish      [--once]             # Stage 6:   Auto-Publish
  python manage.py analytics    [--once]             # Stage 7:   Analytics Feedback
  python manage.py run-all                            # Run ALL pipelines on schedule
  python manage.py db-init                            # Initialise / migrate database
  python manage.py status                            # Print full pipeline status
"""
import argparse
import sys

from core.config.settings import get_settings
from core.utils.logger import setup_logger, update_secrets
from core.db.session import get_session_factory


def cmd_discover(args):
    settings = get_settings()
    setup_logger("news_pipeline", settings.log_level, "discovery.log")
    update_secrets(settings.secret_values)
    SessionFactory = get_session_factory(settings.database_url)

    if args.stats:
        from core.db.repository import StoryRepository
        with SessionFactory() as session:
            stats = StoryRepository(session).get_stats()
        print(f"Total stories : {stats['total']}")
        print(f"New           : {stats['new']}")
        print("By status:")
        for s, c in stats.get("by_status", {}).items():
            print(f"  {s}: {c}")
        print("By category:")
        for cat, c in stats.get("by_category", {}).items():
            print(f"  {cat}: {c}")
        return

    from discovery.pipeline import DiscoveryPipeline
    with SessionFactory() as session:
        summary = DiscoveryPipeline(session).run()
    print(summary)

    if not args.once:
        from scheduler.runner import start_discovery_scheduler
        start_discovery_scheduler(SessionFactory, settings)


def cmd_verify(args):
    settings = get_settings()
    setup_logger("news_pipeline", settings.log_level, "pipeline.log")
    update_secrets(settings.secret_values)
    SessionFactory = get_session_factory(settings.database_url)

    if args.stats:
        from core.db.repository import DraftRepository
        with SessionFactory() as session:
            stats = DraftRepository(session).get_stats()
        for k, v in stats.items():
            print(f"{k}: {v}")
        return

    from verification.pipeline import VerificationPipeline
    with SessionFactory() as session:
        summary = VerificationPipeline(session).run()
    print(summary)


def cmd_write(args):
    settings = get_settings()
    setup_logger("news_pipeline", settings.log_level, "pipeline.log")
    update_secrets(settings.secret_values)
    SessionFactory = get_session_factory(settings.database_url)

    if args.stats:
        from core.db.repository import DraftRepository
        with SessionFactory() as session:
            stats = DraftRepository(session).get_stats()
        for k, v in stats.items():
            print(f"{k}: {v}")
        return

    from writing.pipeline import WritingPipeline
    with SessionFactory() as session:
        summary = WritingPipeline(session).run()
    print(summary)


def cmd_dashboard(args):
    settings = get_settings()
    try:
        import uvicorn
    except ImportError:
        print("uvicorn not installed. Run: pip install uvicorn")
        sys.exit(1)

    uvicorn.run(
        "dashboard.app:app",
        host=settings.dashboard_host,
        port=settings.dashboard_port,
        reload=args.dev,
        log_level=settings.log_level.lower(),
    )


def cmd_publish(args):
    settings = get_settings()
    setup_logger("news_pipeline", settings.log_level, "pipeline.log")
    update_secrets(settings.secret_values)
    SessionFactory = get_session_factory(settings.database_url)

    from publisher.pipeline import PublishingPipeline
    with SessionFactory() as session:
        summary = PublishingPipeline(session).run()
    print(summary)


def cmd_analytics(args):
    settings = get_settings()
    setup_logger("news_pipeline", settings.log_level, "pipeline.log")
    update_secrets(settings.secret_values)
    SessionFactory = get_session_factory(settings.database_url)

    from analytics.collector import AnalyticsCollector
    from analytics.scorer import FeedbackScorer
    with SessionFactory() as session:
        collect_summary = AnalyticsCollector(session).collect()
        score_summary   = FeedbackScorer(session).update_priority_scores()
    print(collect_summary)
    print(score_summary)


def cmd_run_all(_args):
    settings = get_settings()
    setup_logger("news_pipeline", settings.log_level, "pipeline.log")
    update_secrets(settings.secret_values)
    SessionFactory = get_session_factory(settings.database_url)

    from scheduler.runner import start_all_pipelines
    start_all_pipelines(SessionFactory, settings)


def cmd_start(args):
    """One command to rule them all — init DB, start pipeline scheduler, start dashboard."""
    import threading

    settings = get_settings()
    setup_logger("news_pipeline", settings.log_level, "pipeline.log")
    update_secrets(settings.secret_values)

    # Step 1 — init/migrate DB
    print("Initialising database...")
    cmd_db_init(args)

    # Step 2 — run one immediate pipeline pass so articles appear straight away
    print("\nRunning initial pipeline pass (discover → verify → write)...")
    SessionFactory = get_session_factory(settings.database_url)
    try:
        from discovery.pipeline import DiscoveryPipeline
        from verification.pipeline import VerificationPipeline
        from writing.pipeline import WritingPipeline
        with SessionFactory() as session:
            print("  Discovering stories...")
            DiscoveryPipeline(session).run()
        with SessionFactory() as session:
            print("  Verifying stories...")
            VerificationPipeline(session).run()
        with SessionFactory() as session:
            print("  Writing articles...")
            WritingPipeline(session).run()
    except Exception as exc:
        print(f"  Initial pipeline pass failed: {exc} — continuing anyway")

    # Step 3 — start the scheduler in a background thread
    print("\nStarting pipeline scheduler (runs every 30-60 min in background)...")
    def _run_scheduler():
        from scheduler.runner import start_all_pipelines
        start_all_pipelines(get_session_factory(settings.database_url), settings)

    scheduler_thread = threading.Thread(target=_run_scheduler, daemon=True, name="pipeline-scheduler")
    scheduler_thread.start()

    # Step 4 — start the dashboard (blocks here — Ctrl+C to stop everything)
    print(f"\nDashboard starting at http://{settings.dashboard_host}:{settings.dashboard_port}")
    print("Press Ctrl+C to stop.\n")
    try:
        import uvicorn
    except ImportError:
        print("uvicorn not installed. Run: pip install uvicorn")
        sys.exit(1)

    uvicorn.run(
        "dashboard.app:app",
        host=settings.dashboard_host,
        port=settings.dashboard_port,
        reload=args.dev,
        log_level=settings.log_level.lower(),
    )


def cmd_db_init(_args):
    settings = get_settings()
    from core.db.session import init_db
    import sqlite3, re
    from core.db.models import Base
    from sqlalchemy import create_engine, inspect, text

    init_db(settings.database_url)

    # Add any columns present in the ORM models but missing from the live DB
    if settings.database_url.startswith("sqlite"):
        db_path = re.sub(r"^sqlite:///", "", settings.database_url)
        engine = create_engine(settings.database_url)
        inspector = inspect(engine)
        added = []
        for table in Base.metadata.sorted_tables:
            existing = {col["name"] for col in inspector.get_columns(table.name)}
            for col in table.columns:
                if col.name not in existing:
                    col_type = col.type.compile(engine.dialect)
                    default = ""
                    if col.default is not None and col.default.is_scalar:
                        val = col.default.arg
                        default = f" DEFAULT '{val}'" if isinstance(val, str) else f" DEFAULT {val}"
                    with engine.connect() as conn:
                        conn.execute(text(f'ALTER TABLE {table.name} ADD COLUMN "{col.name}" {col_type}{default}'))
                        conn.commit()
                    added.append(f"{table.name}.{col.name}")
        if added:
            print(f"Migrated columns: {', '.join(added)}")

    print(f"Database initialised at: {settings.database_url}")


def cmd_status(_args):
    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)

    from core.db.repository import StoryRepository, DraftRepository

    with SessionFactory() as session:
        story_stats = StoryRepository(session).get_stats()
        draft_stats = DraftRepository(session).get_stats()

    print("=" * 50)
    print("NEWS PIPELINE STATUS")
    print("=" * 50)
    print(f"Total stories discovered : {story_stats['total']}")
    print("Story status breakdown:")
    for status, count in story_stats.get("by_status", {}).items():
        print(f"  {status:<20} {count}")
    print()
    print(f"Total fact checks        : {draft_stats['total_fact_checks']}")
    print(f"  Verified               : {draft_stats['verified']}")
    print(f"  Rejected               : {draft_stats['rejected']}")
    print()
    print(f"Total article drafts     : {draft_stats['total_drafts']}")
    print(f"  Pending review         : {draft_stats['pending_review']}")
    print(f"  Approved               : {draft_stats['approved']}")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="News Automation Pipeline CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # start (all-in-one)
    p_start = sub.add_parser("start", help="Init DB + run pipeline + start dashboard (one command)")
    p_start.add_argument("--dev", action="store_true", help="Enable hot-reload (development only)")

    # discover
    p_disc = sub.add_parser("discover", help="Run discovery pipeline (Stage 1+2)")
    p_disc.add_argument("--once",  action="store_true", help="Run once and exit (don't start scheduler)")
    p_disc.add_argument("--stats", action="store_true", help="Print stats and exit")

    # verify
    p_ver = sub.add_parser("verify", help="Run verification pipeline (Stage 3)")
    p_ver.add_argument("--once",  action="store_true")
    p_ver.add_argument("--stats", action="store_true")

    # write
    p_wri = sub.add_parser("write", help="Run writing pipeline (Stage 4)")
    p_wri.add_argument("--once",  action="store_true")
    p_wri.add_argument("--stats", action="store_true")

    # dashboard
    p_dash = sub.add_parser("dashboard", help="Start editor review dashboard (Stage 5)")
    p_dash.add_argument("--dev", action="store_true", help="Enable hot-reload (development only)")

    # publish
    p_pub = sub.add_parser("publish", help="Run publishing pipeline (Stage 6)")
    p_pub.add_argument("--once", action="store_true")

    # analytics
    p_ana = sub.add_parser("analytics", help="Run analytics feedback loop (Stage 7)")
    p_ana.add_argument("--once", action="store_true")

    # run-all
    sub.add_parser("run-all", help="Start all pipelines on schedule")

    # db-init
    sub.add_parser("db-init", help="Initialise or migrate the database")

    # status
    sub.add_parser("status", help="Print full pipeline status")

    args = parser.parse_args()

    commands = {
        "start":     cmd_start,
        "discover":  cmd_discover,
        "verify":    cmd_verify,
        "write":     cmd_write,
        "dashboard": cmd_dashboard,
        "publish":   cmd_publish,
        "analytics": cmd_analytics,
        "run-all":   cmd_run_all,
        "db-init":   cmd_db_init,
        "status":    cmd_status,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
