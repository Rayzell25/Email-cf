"""Application entry point."""
from __future__ import annotations

import asyncio

from aiogram.types import BotCommand

from app.bot import build_bot, build_dispatcher, build_storage
from app.config import get_settings
from app.database.session import dispose_db, get_session_factory, init_db
from app.middlewares.dependencies import DependenciesMiddleware
from app.middlewares.error_handler import register_error_handler
from app.middlewares.owner_only import OwnerOnlyMiddleware
from app.services.cloudflare import CloudflareClient
from app.utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


async def _set_commands(bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Buka dashboard"),
            BotCommand(command="menu", description="Menu utama"),
        ]
    )


async def run() -> None:
    setup_logging()
    settings = get_settings()

    problems = settings.validate_required()
    if problems:
        for problem in problems:
            logger.error("Konfigurasi: %s", problem)
        raise SystemExit("Konfigurasi tidak lengkap. Lihat .env / .env.example.")

    await init_db()

    bot = build_bot(settings)
    storage = build_storage(settings)
    dp = build_dispatcher(storage)

    cf = CloudflareClient(
        api_token=settings.cloudflare_api_token,
        account_id=settings.cloudflare_account_id,
    )
    session_factory = get_session_factory()

    # --- middlewares (order matters: owner check first) ---
    owner_mw = OwnerOnlyMiddleware(settings.telegram_owner_id)
    deps_mw = DependenciesMiddleware(session_factory, cf)
    for observer in (dp.message, dp.callback_query):
        observer.outer_middleware(owner_mw)
        observer.outer_middleware(deps_mw)

    register_error_handler(dp, bot)

    # --- routers ---
    from app.handlers import get_routers

    for router in get_routers():
        dp.include_router(router)

    try:
        await _set_commands(bot)
    except Exception as exc:  # non-fatal
        logger.warning("set_my_commands failed: %s", exc)

    logger.info("Bot starting (polling)...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        logger.info("Shutting down...")
        await cf.close()
        await bot.session.close()
        await dispose_db()


def main() -> None:
    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
