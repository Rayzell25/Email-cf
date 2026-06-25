"""Safe Telegram send/edit helpers.

These wrappers:
  * ignore the harmless "message is not modified" error,
  * fall back to plain unicode emoji if the server rejects custom emoji,
  * never raise on transient edit failures (so a stale button never crashes
    the bot).
"""
from __future__ import annotations

from typing import Any, Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, Message

from app.utils.emoji import has_premium, strip_premium
from app.utils.logger import get_logger

logger = get_logger(__name__)

_NOT_MODIFIED = "message is not modified"


def _is_emoji_error(message: str) -> bool:
    msg = message.lower()
    return (
        "custom emoji" in msg
        or "emoji" in msg
        or "can't parse entities" in msg
        or "entity" in msg
    )


async def safe_send(
    bot: Bot,
    chat_id: int,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    **kwargs: Any,
) -> Optional[Message]:
    try:
        return await bot.send_message(
            chat_id, text, reply_markup=reply_markup, **kwargs
        )
    except TelegramBadRequest as exc:
        if has_premium(text) and _is_emoji_error(str(exc)):
            return await bot.send_message(
                chat_id, strip_premium(text), reply_markup=reply_markup, **kwargs
            )
        logger.warning("safe_send failed: %s", exc)
        return None


async def safe_edit(
    bot: Bot,
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    **kwargs: Any,
) -> bool:
    """Edit a message text. Returns True on success (or harmless no-op)."""
    try:
        await bot.edit_message_text(
            text=text,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=reply_markup,
            **kwargs,
        )
        return True
    except TelegramBadRequest as exc:
        err = str(exc)
        if _NOT_MODIFIED in err.lower():
            # Content identical -> nothing to do. Not an error.
            return True
        if has_premium(text) and _is_emoji_error(err):
            try:
                await bot.edit_message_text(
                    text=strip_premium(text),
                    chat_id=chat_id,
                    message_id=message_id,
                    reply_markup=reply_markup,
                    **kwargs,
                )
                return True
            except TelegramBadRequest as exc2:
                if _NOT_MODIFIED in str(exc2).lower():
                    return True
                logger.warning("safe_edit fallback failed: %s", exc2)
                return False
        # Message can't be edited (deleted / too old / not found)
        logger.info("safe_edit could not edit message: %s", err)
        return False
