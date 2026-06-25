"""Async database engine / session factory + schema initialisation."""
from __future__ import annotations

import os
from typing import AsyncIterator
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings
from app.database.models import Base
from app.utils.logger import get_logger

logger = get_logger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _ensure_sqlite_dir(database_url: str) -> None:
    """Make sure the directory for a sqlite file exists."""
    if "sqlite" not in database_url:
        return
    # forms: sqlite+aiosqlite:///data/bot.db  or  ...////abs/path
    path_part = database_url.split(":///", 1)[-1]
    if not path_part or path_part == ":memory:":
        return
    directory = os.path.dirname(path_part)
    if directory:
        os.makedirs(directory, exist_ok=True)


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        url = get_settings().database_url
        _ensure_sqlite_dir(url)
        _engine = create_async_engine(url, echo=False, pool_pre_ping=True)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(), expire_on_commit=False, class_=AsyncSession
        )
    return _session_factory


async def init_db() -> None:
    """Create tables if they do not exist yet."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialised (%s)", _safe_db_label())


async def dispose_db() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


def _safe_db_label() -> str:
    try:
        parsed = urlparse(get_settings().database_url)
        return f"{parsed.scheme}:{parsed.path}"
    except Exception:
        return "database"


async def get_session() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        yield session
