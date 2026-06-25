"""List emails per domain + email detail view."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.models import EmailSource
from app.database.repositories import emails as emails_repo
from app.handlers import render
from app.keyboards.email_list import (
    email_detail_kb,
    email_list_kb,
    empty_domain_kb,
)
from app.keyboards.main_menu import error_retry_kb
from app.services.cloudflare import CloudflareClient, CloudflareError, RoutingRule
from app.utils import callbacks as cb
from app.utils.pagination import paginate

router = Router(name="email_list")

_ID_MONTHS = [
    "", "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
    "Agustus", "September", "Oktober", "November", "Desember",
]


def _fmt_wib(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    wib = dt.astimezone(timezone(timedelta(hours=7)))
    return f"{wib.day} {_ID_MONTHS[wib.month]} {wib.year}, {wib:%H:%M} WIB"


async def show_email_list(
    bot: Bot,
    session: AsyncSession,
    event: render.Event,
    state: FSMContext,
    cf: CloudflareClient,
    page_no: int = 1,
) -> None:
    data = await state.get_data()
    zone_id, domain = data.get("zone_id"), data.get("domain")
    if not zone_id or not domain:
        if isinstance(event, CallbackQuery):
            await render.ack(event, "Sesi kedaluwarsa. Tekan /start lagi.", True)
        return

    try:
        rules = await cf.list_routing_rules(zone_id)
    except CloudflareError as exc:
        await render.show(
            bot, session, event, render.cloudflare_error_text(exc.user_message),
            error_retry_kb(),
        )
        return

    if not rules:
        await render.show(
            bot, session, event, render.email_empty_text(domain), empty_domain_kb()
        )
        return

    settings = get_settings()
    page = paginate(rules, page_no, settings.email_page_size)
    await state.update_data(
        email_rules=[[r.id, r.email, r.destination or "", r.enabled] for r in page.items],
        email_page=page.page,
    )
    await render.show(
        bot, session, event, render.email_list_text(domain, page), email_list_kb(page)
    )


def _rule_from_state(rules_raw: Optional[list], index: int) -> Optional[RoutingRule]:
    if not rules_raw or index < 0 or index >= len(rules_raw):
        return None
    item = rules_raw[index]
    try:
        return RoutingRule(
            id=item[0], email=item[1], destination=item[2] or None, enabled=bool(item[3])
        )
    except (IndexError, TypeError):
        return None


@router.callback_query(F.data.startswith("e:pg:"))
async def on_page(
    callback: CallbackQuery,
    bot: Bot,
    session: AsyncSession,
    state: FSMContext,
    cf: CloudflareClient,
) -> None:
    await render.ack(callback)
    parts = cb.parse(callback.data)
    page_no = cb.safe_int(parts[2], 1) if len(parts) > 2 else 1
    await show_email_list(bot, session, callback, state, cf, page_no)


@router.callback_query(F.data == cb.email_back_list())
async def on_back_list(
    callback: CallbackQuery,
    bot: Bot,
    session: AsyncSession,
    state: FSMContext,
    cf: CloudflareClient,
) -> None:
    await render.ack(callback)
    page_no = (await state.get_data()).get("email_page", 1)
    await show_email_list(bot, session, callback, state, cf, page_no)


@router.callback_query(F.data.startswith("e:v:"))
async def on_view(
    callback: CallbackQuery,
    bot: Bot,
    session: AsyncSession,
    state: FSMContext,
    cf: CloudflareClient,
) -> None:
    await render.ack(callback)
    parts = cb.parse(callback.data)
    index = cb.safe_int(parts[2], -1) if len(parts) > 2 else -1
    data = await state.get_data()
    rule = _rule_from_state(data.get("email_rules"), index)
    domain = data.get("domain", "")
    if rule is None:
        await render.ack(callback, "Data lama, buka ulang list.", True)
        return

    await state.update_data(view_index=index)

    # delete-flow shortcut: go straight to delete confirmation
    if data.get("purpose") == "d":
        from app.handlers.email_delete import show_delete_confirm

        await show_delete_confirm(bot, session, callback, state, index)
        return

    # otherwise show full detail
    db_row = await emails_repo.get_for_rule(session, data.get("zone_id", ""), rule.id)
    created_via_bot = bool(
        db_row and db_row.source in (EmailSource.random.value, EmailSource.manual.value)
    )
    created_at = _fmt_wib(db_row.created_at) if db_row else None
    await render.show(
        bot, session, callback,
        render.email_detail_text(
            rule, domain, created_via_bot=created_via_bot, created_at=created_at
        ),
        email_detail_kb(index, can_delete=True),
    )
