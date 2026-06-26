"""Dashboard service: enforce the "one active bot message" rule.

All menu navigation edits the SAME message. If the stored dashboard message can
no longer be edited (deleted / too old), exactly one new dashboard is created
and the stored id is replaced. We never keep more than one active dashboard.
"""
from __future__ import annotations

from typing import Optional

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories import dashboard as dashboard_repo
from app.utils.logger import get_logger
from app.utils.ui import safe_edit, safe_send

logger = get_logger(__name__)


async def render(
    bot: Bot,
    session: AsyncSession,
    *,
    user_id: int,
    chat_id: int,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: str = "HTML",
) -> None:
    """Show ``text`` on the user's single dashboard message.

    Edits the existing dashboard when possible; otherwise creates a new one and
    stores its id (replacing the old record).
    """
    record = await dashboard_repo.get(session, user_id)

    if record is not None:
        edited = await safe_edit(
            bot,
            record.chat_id,
            record.message_id,
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
        if edited:
            await session.commit()
            return
        # old dashboard gone -> fall through to create a fresh one

    message = await safe_send(
        bot, chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode
    )
    if message is not None:
        await dashboard_repo.upsert(
            session, telegram_user_id=user_id, chat_id=chat_id, message_id=message.message_id
        )
        await session.commit()
    else:
        logger.warning("Failed to render dashboard for user %s", user_id)


async def create_fresh(
    bot: Bot,
    session: AsyncSession,
    *,
    user_id: int,
    chat_id: int,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: str = "HTML",
) -> None:
    """Force-create a new dashboard message (used by /start and /menu).

    The previously tracked dashboard message is DELETED first, so the chat keeps
    exactly one bot message: the new dashboard appears at the bottom and the old
    menu disappears.
    """
    old = await dashboard_repo.get(session, user_id)
    if old is not None:
        try:
            await bot.delete_message(old.chat_id, old.message_id)
        except Exception:
            # already gone / too old to delete -> ignore
            pass

    message = await safe_send(
        bot, chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode
    )
    if message is not None:
        await dashboard_repo.upsert(
            session, telegram_user_id=user_id, chat_id=chat_id, message_id=message.message_id
        )
        await session.commit()
