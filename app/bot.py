"""Bot / Dispatcher / storage factories.

Supports a self-hosted Local Bot API server (``BOT_API_ROOT``) for low latency
and access to the newest Bot API features (e.g. premium emoji on buttons via
``icon_custom_emoji_id``). Falls back to the official Telegram cloud API when
``BOT_API_ROOT`` is empty.
"""
from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import Settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


def build_bot(settings: Settings) -> Bot:
    session = None
    base = settings.normalized_bot_api_root
    if base:
        api_server = TelegramAPIServer.from_base(base, is_local=True)
        session = AiohttpSession(api=api_server)
        logger.info("Using Local Bot API server at %s", base)
    else:
        logger.info("Using official Telegram Bot API (cloud)")

    return Bot(
        token=settings.telegram_bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def build_storage(settings: Settings) -> BaseStorage:
    if settings.redis_url:
        try:
            from aiogram.fsm.storage.redis import RedisStorage

            storage = RedisStorage.from_url(settings.redis_url)
            logger.info("Using Redis FSM storage")
            return storage
        except Exception as exc:  # pragma: no cover - depends on runtime env
            logger.warning("Redis unavailable (%s); using in-memory storage", exc)
    return MemoryStorage()


def build_dispatcher(storage: BaseStorage) -> Dispatcher:
    return Dispatcher(storage=storage)
