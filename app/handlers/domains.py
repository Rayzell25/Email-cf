"""Domain listing + selection. Entry point for create / list / delete flows."""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.handlers import render, states
from app.keyboards.domains import domains_kb
from app.services.cloudflare import CloudflareClient, CloudflareError
from app.utils import callbacks as cb
from app.utils.pagination import paginate

router = Router(name="domains")

# menu callback -> purpose
_MENU_PURPOSE = {
    cb.MENU_CREATE: "c",
    cb.MENU_LIST: "l",
    cb.MENU_DELETE: "d",
    cb.MENU_DOMAINS: "v",
}


async def show_domains(
    bot: Bot,
    session: AsyncSession,
    event: render.Event,
    state: FSMContext,
    cf: CloudflareClient,
    purpose: str,
    page_no: int = 1,
) -> None:
    settings = get_settings()
    try:
        zones = await states.get_zones(state, cf)
    except CloudflareError as exc:
        from app.keyboards.main_menu import error_retry_kb

        await render.show(
            bot, session, event, render.cloudflare_error_text(exc.user_message),
            error_retry_kb(),
        )
        return

    page = paginate(zones, page_no, settings.domain_page_size)
    await states.set_page_zones(state, page.items)
    await state.update_data(purpose=purpose, domain_page=page.page)
    await render.show(
        bot, session, event, render.domains_text(purpose, page), domains_kb(page, purpose)
    )


@router.callback_query(F.data.in_(set(_MENU_PURPOSE.keys())))
async def on_menu_entry(
    callback: CallbackQuery,
    bot: Bot,
    session: AsyncSession,
    state: FSMContext,
    cf: CloudflareClient,
) -> None:
    await render.ack(callback)
    purpose = _MENU_PURPOSE[callback.data]
    await show_domains(bot, session, callback, state, cf, purpose, 1)


@router.callback_query(F.data.startswith("d:pg:"))
async def on_domain_page(
    callback: CallbackQuery,
    bot: Bot,
    session: AsyncSession,
    state: FSMContext,
    cf: CloudflareClient,
) -> None:
    await render.ack(callback)
    parts = cb.parse(callback.data)  # d:pg:purpose:page
    purpose = parts[2] if len(parts) > 2 else "v"
    page_no = cb.safe_int(parts[3], 1) if len(parts) > 3 else 1
    await show_domains(bot, session, callback, state, cf, purpose, page_no)


@router.callback_query(F.data.startswith("d:sel:"))
async def on_domain_select(
    callback: CallbackQuery,
    bot: Bot,
    session: AsyncSession,
    state: FSMContext,
    cf: CloudflareClient,
) -> None:
    await render.ack(callback)
    parts = cb.parse(callback.data)  # d:sel:purpose:index
    purpose = parts[2] if len(parts) > 2 else "v"
    index = cb.safe_int(parts[3], -1) if len(parts) > 3 else -1

    zone = await states.get_zone_by_index_on_page(state, index)
    if zone is None:
        await render.ack(callback, "Domain not found, reopen the menu.", True)
        return

    await state.update_data(zone_id=zone.id, domain=zone.name, purpose=purpose)

    if purpose == "c":
        await _start_create(bot, session, callback, state, cf, zone)
    else:
        # list / delete / view -> show the email list for this domain
        from app.handlers.email_list import show_email_list

        await show_email_list(bot, session, callback, state, cf, page_no=1)


async def _start_create(
    bot: Bot,
    session: AsyncSession,
    callback: CallbackQuery,
    state: FSMContext,
    cf: CloudflareClient,
    zone,
) -> None:
    from app.handlers.create_random import show_method

    # Only check the (free, cached) zone status. We intentionally do NOT call
    # get_email_routing_status here: it is an extra Cloudflare round-trip (slower)
    # and an extra permission surface. If Email Routing is disabled, the create
    # POST will report it clearly at confirm time.
    if zone.status and zone.status != "active":
        await render.show(
            bot, session, callback, render.domain_inactive_text(zone.name),
            _back_kb(),
        )
        return

    await show_method(bot, session, callback, state, zone.name)


def _back_kb():
    from aiogram.types import InlineKeyboardMarkup

    from app.keyboards.common import btn

    return InlineKeyboardMarkup(
        inline_keyboard=[[btn("MAIN MENU", cb.MENU_HOME, emoji_key="home")]]
    )
