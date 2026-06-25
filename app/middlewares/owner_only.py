"""Owner-only access control.

The bot is private: only ``TELEGRAM_OWNER_ID`` may use it. Everyone else gets a
short "access denied" reply and never sees any Cloudflare menu/data.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, User

from app.utils.logger import get_logger

logger = get_logger(__name__)

DENIED_TEXT = "\u26D4 AKSES DITOLAK\n\nBot ini bersifat pribadi."


class OwnerOnlyMiddleware(BaseMiddleware):
    def __init__(self, owner_id: int) -> None:
        self.owner_id = int(owner_id)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        if user is None or user.id != self.owner_id:
            await self._deny(event, user)
            return None  # stop processing
        return await handler(event, data)

    async def _deny(self, event: TelegramObject, user: User | None) -> None:
        uid = user.id if user else "unknown"
        logger.warning("Access denied for user %s", uid)
        try:
            if isinstance(event, CallbackQuery):
                await event.answer("Akses ditolak. Bot ini pribadi.", show_alert=True)
            elif isinstance(event, Message):
                await event.answer(DENIED_TEXT)
        except Exception:  # pragma: no cover - best effort
            pass
