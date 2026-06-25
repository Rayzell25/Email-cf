"""Main menu handlers + the shared main-menu renderer."""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories import emails as emails_repo
from app.handlers import render
from app.handlers import states
from app.keyboards.main_menu import main_menu_kb
from app.services.cloudflare import CloudflareClient, CloudflareError
from app.utils import callbacks as cb

router = Router(name="menu")


async def render_main_menu(
    bot: Bot,
    session: AsyncSession,
    state: FSMContext,
    event: render.Event,
    cf: CloudflareClient,
    *,
    fresh: bool = False,
) -> None:
    """Build + show the main menu (also refreshes the zones cache)."""
    await state.set_state(None)

    connected = True
    zones = []
    try:
        zones = await states.get_zones(state, cf, force=True)
    except CloudflareError:
        connected = False

    total_emails = await emails_repo.count_active(session)
    text = render.menu_text(len(zones), total_emails, connected=connected)
    await render.show(bot, session, event, text, main_menu_kb(), fresh=fresh)


@router.callback_query(F.data == cb.MENU_HOME)
async def on_home(
    callback: CallbackQuery,
    bot: Bot,
    session: AsyncSession,
    state: FSMContext,
    cf: CloudflareClient,
) -> None:
    await render.ack(callback)
    await render_main_menu(bot, session, state, callback, cf)


@router.callback_query(F.data == cb.MENU_REFRESH)
async def on_refresh(
    callback: CallbackQuery,
    bot: Bot,
    session: AsyncSession,
    state: FSMContext,
    cf: CloudflareClient,
) -> None:
    await render.ack(callback, "Memuat ulang...")
    await render_main_menu(bot, session, state, callback, cf)


@router.callback_query(F.data == cb.NOOP)
async def on_noop(callback: CallbackQuery) -> None:
    # inert button (e.g. the page indicator) -- just clear the spinner
    await render.ack(callback)
