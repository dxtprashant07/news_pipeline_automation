from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from .models import Base
from ..utils.logger import get_logger

logger = get_logger("storage.database")


def _get_engine(database_url: str):
    """Create SQLAlchemy engine with sane defaults."""
    connect_args = {}

    if database_url.startswith("sqlite"):
        # SQLite: enforce foreign keys + WAL mode for concurrency
        connect_args = {"check_same_thread": False}
        Path("data").mkdir(exist_ok=True)

    engine = create_engine(
        database_url,
        connect_args=connect_args,
        pool_pre_ping=True,   # Detect stale connections
        echo=False,           # Set True to log every SQL statement
    )

    if database_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, _):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def init_db(database_url: str):
    """
    Create all tables if they don't exist.
    Call once at application startup.
    """
    engine = _get_engine(database_url)
    Base.metadata.create_all(engine)
    logger.info(f"Database initialised at: {database_url}")
    return engine


def get_session_factory(database_url: str) -> sessionmaker:
    engine = _get_engine(database_url)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)
