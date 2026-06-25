"""Dependency-injection middleware.

Opens a fresh async DB session per update and injects it (plus the shared
Cloudflare client) into the handler's data dict as ``session`` and ``cf``.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.services.cloudflare import CloudflareClient


class DependenciesMiddleware(BaseMiddleware):
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        cf: CloudflareClient,
    ) -> None:
        self.session_factory = session_factory
        self.cf = cf

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with self.session_factory() as session:
            data["session"] = session
            data["cf"] = self.cf
            try:
                return await handler(event, data)
            except Exception:
                await session.rollback()
                raise
