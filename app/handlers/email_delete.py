"""Delete email flow: confirm + perform deletion."""
from __future__ import annotations

from typing import Optional

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.handlers import render
from app.handlers.email_list import _rule_from_state
from app.keyboards.email_list import delete_confirm_kb, delete_result_kb
from app.keyboards.main_menu import error_retry_kb
from app.services import email_service
from app.services.cloudflare import CloudflareClient
from app.utils import callbacks as cb

router = Router(name="email_delete")


async def show_delete_confirm(
    bot: Bot,
    session: AsyncSession,
    callback: CallbackQuery,
    state: FSMContext,
    index: int,
) -> None:
    data = await state.get_data()
    rule = _rule_from_state(data.get("email_rules"), index)
    if rule is None:
        await render.ack(callback, "Stale data, reopen the list.", True)
        return
    await state.update_data(view_index=index)
    await render.show(
        bot, session, callback, render.delete_confirm_text(rule.email),
        delete_confirm_kb(index),
    )


@router.callback_query(F.data.startswith("e:del:"))
async def on_delete(
    callback: CallbackQuery, bot: Bot, session: AsyncSession, state: FSMContext
) -> None:
    await render.ack(callback)
    parts = cb.parse(callback.data)
    index = cb.safe_int(parts[2], -1) if len(parts) > 2 else -1
    await show_delete_confirm(bot, session, callback, state, index)


@router.callback_query(F.data.startswith("e:delok:"))
async def on_delete_confirm(
    callback: CallbackQuery,
    bot: Bot,
    session: AsyncSession,
    state: FSMContext,
    cf: CloudflareClient,
) -> None:
    await render.ack(callback, "Deleting...")
    parts = cb.parse(callback.data)
    index = cb.safe_int(parts[2], -1) if len(parts) > 2 else -1
    data = await state.get_data()
    zone_id = data.get("zone_id", "")
    rule = _rule_from_state(data.get("email_rules"), index)
    if rule is None or not zone_id:
        await render.ack(callback, "Stale data, reopen the list.", True)
        return

    result = await email_service.delete_one(
        session, cf,
        zone_id=zone_id, rule_id=rule.id, full_email=rule.email,
        owner_id=callback.from_user.id,
    )
    if result.ok:
        # invalidate cached list so BACK TO LIST shows fresh data
        await state.update_data(all_rules=None, all_rules_zone=None)
        await render.show(
            bot, session, callback, render.delete_success_text(rule.email),
            delete_result_kb(),
        )
    else:
        await render.show(
            bot, session, callback,
            render.cloudflare_error_text(result.error or "Gagal menghapus email."),
            error_retry_kb(),
        )
