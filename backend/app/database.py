from __future__ import annotations

import logging
import time
from collections.abc import Generator

from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models import Base, Product

logger = logging.getLogger(__name__)


def normalize_database_url(raw_url: str) -> str:
    if not raw_url:
        raise RuntimeError(
            "DATABASE_URL is missing. Copy .env.example to .env and add your rotated Aiven PostgreSQL URI."
        )
    if raw_url.startswith("postgres://"):
        raw_url = raw_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif raw_url.startswith("postgresql://"):
        raw_url = raw_url.replace("postgresql://", "postgresql+psycopg://", 1)
    elif raw_url.startswith("postgresql+psycopg2://"):
        raw_url = raw_url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)

    url = make_url(raw_url)
    if url.drivername.startswith("postgresql") and "sslmode" not in url.query:
        url = url.update_query_dict({"sslmode": "require"})
    return url.render_as_string(hide_password=False)


DATABASE_URL = normalize_database_url(settings.database_url)
_is_sqlite = DATABASE_URL.startswith("sqlite")
_engine_options = {"pool_pre_ping": True, "future": True}
if not _is_sqlite:
    _engine_options.update({"pool_size": 5, "max_overflow": 10, "pool_recycle": 1800})
else:
    _engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **_engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def wait_for_database(attempts: int = 30, delay: float = 2.0) -> None:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return
        except Exception as exc:  # pragma: no cover - depends on external service state
            last_error = exc
            logger.warning("Waiting for PostgreSQL (%s/%s): %s", attempt + 1, attempts, exc)
            time.sleep(delay)
    raise RuntimeError(f"PostgreSQL did not become available: {last_error}")


def initialize_database() -> None:
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
    from app.seed import seed_products

    seed_products()


def database_is_ready() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
