"""Entry point: python -m discovery [--once | --stats]"""
import argparse
from core.config.settings import get_settings
from core.utils.logger import setup_logger, update_secrets
from core.db.session import get_session_factory


def main():
    parser = argparse.ArgumentParser(description="News Discovery Pipeline (Stage 1+2)")
    parser.add_argument("--once",  action="store_true", help="Run pipeline once and exit")
    parser.add_argument("--stats", action="store_true", help="Print DB stats and exit")
    args = parser.parse_args()

    settings = get_settings()
    setup_logger("news_pipeline", settings.log_level, "discovery.log")
    update_secrets(settings.secret_values)

    SessionFactory = get_session_factory(settings.database_url)

    if args.stats:
        from core.db.repository import StoryRepository
        from sqlalchemy import select, func
        with SessionFactory() as session:
            repo  = StoryRepository(session)
            stats = repo.get_stats()
        print(f"Total stories : {stats['total']}")
        print(f"New (unprocessed): {stats['new']}")
        print("By status:")
        for status, count in stats.get("by_status", {}).items():
            print(f"  {status}: {count}")
        print("By category:")
        for cat, count in stats.get("by_category", {}).items():
            print(f"  {cat}: {count}")
        return

    if args.once:
        from .pipeline import DiscoveryPipeline
        with SessionFactory() as session:
            pipeline = DiscoveryPipeline(session)
            summary  = pipeline.run()
        print(summary)
        return

    # Default: start APScheduler
    from scheduler.runner import start_discovery_scheduler
    start_discovery_scheduler(SessionFactory, settings)


if __name__ == "__main__":
    main()
