"""/start and /menu commands."""
from __future__ import annotations

from aiogram import Bot, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories import users as users_repo
from app.handlers.menu import render_main_menu
from app.services.cloudflare import CloudflareClient

router = Router(name="start")


@router.message(CommandStart())
async def on_start(
    message: Message,
    bot: Bot,
    session: AsyncSession,
    state: FSMContext,
    cf: CloudflareClient,
) -> None:
    await users_repo.get_or_create(session, message.from_user.id)
    await session.commit()
    await state.clear()
    # /start always creates one fresh dashboard message (and refreshes zones).
    await render_main_menu(bot, session, state, message, cf, fresh=True, force=True)
    # remove the user's /start command message so only the dashboard remains
    try:
        await message.delete()
    except Exception:
        pass


@router.message(Command("menu"))
async def on_menu(
    message: Message,
    bot: Bot,
    session: AsyncSession,
    state: FSMContext,
    cf: CloudflareClient,
) -> None:
    await render_main_menu(bot, session, state, message, cf, fresh=True)
    try:
        await message.delete()
    except Exception:
        pass
