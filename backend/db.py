import os
import psycopg2
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

import backend.env  # noqa: F401  loads repo-root .env

DATABASE_URL = os.getenv("DATABASE_URL")

engine = None
SessionLocal = None
Base = declarative_base()


def _require_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise ValueError(
            "DATABASE_URL is not set in .env. "
            "Start local Postgres with `docker compose up -d postgres` "
            "and use the URL from .env.example."
        )
    return url


def get_engine():
    global engine, SessionLocal
    if engine is None:
        engine = create_engine(_require_database_url())
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine


def get_session():
    get_engine()
    return SessionLocal()


def get_connection():
    """Raw psycopg2 connection for scripts that skip SQLAlchemy."""
    dsn = _require_database_url().replace("postgresql+psycopg2://", "postgresql://")
    return psycopg2.connect(dsn)
