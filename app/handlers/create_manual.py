"""Manual email input flow.

The only place the bot waits for a typed message. After reading the name, the
user's message is deleted so the chat keeps a single dashboard message.
"""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import EmailSource
from app.database.repositories import emails as emails_repo
from app.handlers import render
from app.handlers.states import Flow
from app.keyboards.common import btn
from app.keyboards.main_menu import main_menu_kb
from app.keyboards.random_email import manual_confirm_kb, manual_prompt_kb
from app.services import email_service, reservation_service
from app.services.cloudflare import CloudflareClient, CloudflareError
from app.utils import callbacks as cb
from app.utils.validators import validate_local_part

router = Router(name="create_manual")


@router.callback_query(F.data == cb.CREATE_MANUAL)
async def on_manual(
    callback: CallbackQuery, bot: Bot, session: AsyncSession, state: FSMContext
) -> None:
    await render.ack(callback)
    domain = (await state.get_data()).get("domain")
    if not domain:
        await render.ack(callback, "Sesi kedaluwarsa. Tekan /start lagi.", True)
        return
    await state.set_state(Flow.manual_input)
    await render.show(
        bot, session, callback, render.manual_prompt_text(domain), manual_prompt_kb()
    )


@router.callback_query(F.data.startswith("man:ch:"))
async def on_change(
    callback: CallbackQuery, bot: Bot, session: AsyncSession, state: FSMContext
) -> None:
    await render.ack(callback)
    data = await state.get_data()
    domain = data.get("domain")
    draft = data.get("manual_draft")
    if not domain:
        await render.ack(callback, "Sesi kedaluwarsa. Tekan /start lagi.", True)
        return
    # release the previously reserved name before asking for a new one
    if draft and len(draft) >= 3 and draft[2]:
        await reservation_service.release(session, draft[2])
    await state.update_data(manual_draft=None)
    await state.set_state(Flow.manual_input)
    await render.show(
        bot, session, callback, render.manual_prompt_text(domain), manual_prompt_kb()
    )


@router.message(Flow.manual_input)
async def on_manual_text(
    message: Message,
    bot: Bot,
    session: AsyncSession,
    state: FSMContext,
    cf: CloudflareClient,
) -> None:
    text = (message.text or "").strip()
    # delete the user's message immediately (keep single dashboard)
    try:
        await message.delete()
    except Exception:
        pass

    data = await state.get_data()
    zone_id, domain = data.get("zone_id"), data.get("domain")
    if not zone_id or not domain:
        await render.show(bot, session, message, render.menu_text(0, 0, True), main_menu_kb())
        return

    result = validate_local_part(text)
    if not result.ok:
        await render.show(
            bot, session, message, render.manual_invalid_text(domain, result.error),
            manual_prompt_kb(),
        )
        return

    local = result.value
    full_email = f"{local}@{domain.lower()}"

    # existing checks: DB + Cloudflare
    if await emails_repo.exists_active(session, full_email):
        await render.show(
            bot, session, message,
            render.manual_invalid_text(domain, f"{full_email} sudah terdaftar."),
            manual_prompt_kb(),
        )
        return
    try:
        if await cf.find_rule_by_email(zone_id, full_email) is not None:
            await render.show(
                bot, session, message,
                render.manual_invalid_text(domain, f"{full_email} sudah terdaftar."),
                manual_prompt_kb(),
            )
            return
    except CloudflareError as exc:
        await render.show(
            bot, session, message, render.cloudflare_error_text(exc.user_message),
            main_menu_kb(),
        )
        return

    # reserve this specific name
    token = reservation_service.new_token()
    reserved = await reservation_service.reserve_specific(
        session, display_name=local, domain=domain, token=token
    )
    if reserved is None:
        await render.show(
            bot, session, message,
            render.manual_invalid_text(domain, "Nama ini sudah pernah dipakai. Coba nama lain."),
            manual_prompt_kb(),
        )
        return

    await state.update_data(
        manual_draft=[local, full_email, token, reserved.generated_name_id]
    )
    await state.set_state(None)  # stop capturing text
    await render.show(
        bot, session, message,
        render.manual_confirm_text(domain, full_email),
        manual_confirm_kb(reserved.generated_name_id),
    )


@router.callback_query(F.data.startswith("man:ok:"))
async def on_confirm(
    callback: CallbackQuery,
    bot: Bot,
    session: AsyncSession,
    state: FSMContext,
    cf: CloudflareClient,
) -> None:
    await render.ack(callback, "Membuat email...")
    data = await state.get_data()
    zone_id, domain = data.get("zone_id"), data.get("domain")
    draft = data.get("manual_draft")
    if not zone_id or not domain or not draft:
        await render.ack(callback, "Sesi kedaluwarsa. Tekan /start lagi.", True)
        return

    full_email = draft[1]
    result = await email_service.create_one(
        session, cf,
        zone_id=zone_id, domain=domain, full_email=full_email,
        source=EmailSource.manual, owner_id=callback.from_user.id,
    )
    await state.update_data(manual_draft=None)

    if result.ok:
        await render.show(
            bot, session, callback, render.success_text(domain, [full_email]),
            _manual_done_kb(),
        )
    else:
        await render.show(
            bot, session, callback,
            render.manual_invalid_text(domain, result.error or "Gagal membuat email."),
            manual_prompt_kb(),
        )
        await state.set_state(Flow.manual_input)


def _manual_done_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn("LIHAT LIST EMAIL", cb.MENU_LIST, emoji_key="list")],
            [btn("BUAT MANUAL LAGI", cb.CREATE_MANUAL, emoji_key="pencil")],
            [btn("MENU UTAMA", cb.MENU_HOME, emoji_key="home")],
        ]
    )
