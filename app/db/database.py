"""SQLite engine and session factory."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
SessionLocal: sessionmaker | None = None


def _ensure_dirs() -> None:
    settings = get_settings()
    Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.upload_dir, "samples").mkdir(parents=True, exist_ok=True)


def get_engine() -> Engine:
    global _engine, SessionLocal
    if _engine is None:
        _ensure_dirs()
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            connect_args={"check_same_thread": False},
            echo=False,
        )

        @event.listens_for(_engine, "connect")
        def _sqlite_pragma(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def reset_engine() -> None:
    """Test helper — drop the cached engine after env changes."""
    global _engine, SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    SessionLocal = None


def get_db() -> Generator[Session, None, None]:
    get_engine()
    assert SessionLocal is not None
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables and seed demo data if empty."""
    from app.db import models  # noqa: F401
    from app.db.seed import seed_if_empty

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    assert SessionLocal is not None
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()
