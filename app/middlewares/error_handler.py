"""Global error handler.

Catches unhandled exceptions so the bot never crashes on a single bad update.
It logs a redacted message (the logger filter strips secrets) and shows the user
a short, safe message -- never a stack trace or raw API response.
"""
from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.types import ErrorEvent

from app.services.cloudflare import CloudflareError
from app.utils.logger import get_logger

logger = get_logger(__name__)

GENERIC_TEXT = "\u26A0\ufe0f Something went wrong. Please try again."


def register_error_handler(dp: Dispatcher, bot: Bot) -> None:
    @dp.errors()
    async def _on_error(event: ErrorEvent) -> bool:
        exc = event.exception
        logger.exception("Unhandled error: %s", type(exc).__name__)

        # pick a user-safe message
        if isinstance(exc, CloudflareError):
            text = f"\u274C {exc.user_message}"
        else:
            text = GENERIC_TEXT

        update = event.update
        try:
            if update.callback_query is not None:
                await update.callback_query.answer(text[:190], show_alert=True)
            elif update.message is not None:
                await update.message.answer(text)
        except Exception:  # pragma: no cover - best effort
            pass
        return True  # mark as handled
