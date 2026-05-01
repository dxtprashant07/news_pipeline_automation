"""
Phase 1 — News Discovery Pipeline
Entry point. Run with:

    python main.py           # Start the scheduler (runs every 30 min)
    python main.py --once    # Run the pipeline once and exit
    python main.py --stats   # Print DB stats and exit
"""
import argparse
import sys

# ── Setup logging & secrets FIRST — before any other imports ───────────────
from .utils.logger import setup_logger, update_secrets

logger = setup_logger()

# ── Validate settings at startup (fail-fast) ───────────────────────────────
try:
    from .config.settings import get_settings
    settings = get_settings()
    update_secrets(settings.secret_values)
    logger.info("Settings loaded and validated.")
except Exception as exc:
    logger.critical(f"Configuration error: {exc}")
    sys.exit(1)

# ── Rest of imports (after settings are confirmed valid) ───────────────────
from .storage.database import get_session_factory, init_db
from .pipeline import DiscoveryPipeline
from .scheduler.runner import start_scheduler


def run_once() -> None:
    """Execute the pipeline a single time — useful for testing."""
    logger.info("Running pipeline once…")
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        pipeline = DiscoveryPipeline(session)
        summary = pipeline.run()

    print("\n── Pipeline Summary ─────────────────────────────")
    print(f"  Raw fetched    : {summary['raw_fetched']}")
    print(f"  Filtered out   : {summary['filtered_out']}  (below min credibility)")
    print(f"  Saved (new)    : {summary['saved']}")
    print(f"  DB total       : {summary['db_total']}")
    print(f"  DB new (queue) : {summary['db_new']}")
    print(f"\n  By category:")
    for cat, count in sorted(summary["by_category"].items(), key=lambda x: -x[1]):
        print(f"    {cat:<18} {count}")
    print("─────────────────────────────────────────────────\n")


def print_stats() -> None:
    """Print DB stats without running the pipeline."""
    from .storage.repository import StoryRepository
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        repo = StoryRepository(session)
        stats = repo.get_stats()

    print("\n── Database Stats ───────────────────────────────")
    print(f"  Total stories  : {stats['total']}")
    print(f"  In queue (new) : {stats['new']}")
    print(f"\n  By category:")
    for cat, count in sorted(stats["by_category"].items(), key=lambda x: -x[1]):
        print(f"    {cat:<18} {count}")
    print("─────────────────────────────────────────────────\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="News Discovery Pipeline — Phase 1")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--once",  action="store_true", help="Run pipeline once and exit")
    group.add_argument("--stats", action="store_true", help="Show DB stats and exit")
    args = parser.parse_args()

    # Ensure DB and tables exist
    init_db(settings.database_url)

    if args.once:
        run_once()
    elif args.stats:
        print_stats()
    else:
        # Default: start the scheduler (blocking)
        start_scheduler()


if __name__ == "__main__":
    main()
