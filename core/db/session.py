from pathlib import Path
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from .models import Base
from ..utils.logger import get_logger

logger = get_logger("db.session")


def _make_engine(database_url: str):
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        Path("data").mkdir(exist_ok=True)

    engine = create_engine(
        database_url,
        connect_args=connect_args,
        pool_pre_ping=True,
        echo=False,
    )

    if database_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, _):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def _migrate(engine) -> None:
    """Add new columns to existing tables without dropping data."""
    migrations = [
        "ALTER TABLE article_drafts ADD COLUMN seo_score INTEGER DEFAULT 0",
        "ALTER TABLE article_drafts ADD COLUMN seo_breakdown JSON DEFAULT '{}'",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass  # column already exists -- safe to ignore


def init_db(database_url: str):
    engine = _make_engine(database_url)
    Base.metadata.create_all(engine)
    _migrate(engine)
    logger.info(f"Database initialised: {database_url}")
    return engine


def get_session_factory(database_url: str) -> sessionmaker:
    engine = _make_engine(database_url)
    Base.metadata.create_all(engine)
    _migrate(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)
