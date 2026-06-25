"""Create-email flow: method chooser + random generation/confirm/create."""
from __future__ import annotations

from typing import Optional

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    BatchItemStatus,
    BatchStatus,
    EmailSource,
)
from app.database.repositories import batches as batches_repo
from app.handlers import render
from app.keyboards import random_email as kb
from app.keyboards.main_menu import main_menu_kb
from app.services import email_service, reservation_service
from app.services.cloudflare import CloudflareClient
from app.utils import callbacks as cb
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = Router(name="create_random")


# ---------------------------------------------------------------------------
# Method chooser
# ---------------------------------------------------------------------------
async def show_method(
    bot: Bot,
    session: AsyncSession,
    event: render.Event,
    state: FSMContext,
    domain: str,
) -> None:
    await render.show(bot, session, event, render.method_text(domain), kb.method_kb())


@router.callback_query(F.data == cb.CREATE_BACK_METHOD)
async def on_back_method(
    callback: CallbackQuery, bot: Bot, session: AsyncSession, state: FSMContext
) -> None:
    await render.ack(callback)
    domain = (await state.get_data()).get("domain")
    if not domain:
        await _need_restart(callback)
        return
    await show_method(bot, session, callback, state, domain)


@router.callback_query(F.data == cb.CREATE_IN_DOMAIN)
async def on_create_in_domain(
    callback: CallbackQuery, bot: Bot, session: AsyncSession, state: FSMContext
) -> None:
    """'BUAT EMAIL DI DOMAIN INI' from the email list."""
    await render.ack(callback)
    domain = (await state.get_data()).get("domain")
    if not domain:
        await _need_restart(callback)
        return
    await show_method(bot, session, callback, state, domain)


# ---------------------------------------------------------------------------
# Random: choose count
# ---------------------------------------------------------------------------
@router.callback_query(F.data == cb.CREATE_RANDOM)
async def on_random(
    callback: CallbackQuery, bot: Bot, session: AsyncSession, state: FSMContext
) -> None:
    await render.ack(callback)
    domain = (await state.get_data()).get("domain")
    if not domain:
        await _need_restart(callback)
        return
    await render.show(bot, session, callback, render.random_count_text(domain), kb.count_kb())


@router.callback_query(F.data == cb.CREATE_BACK_COUNT)
async def on_back_count(
    callback: CallbackQuery, bot: Bot, session: AsyncSession, state: FSMContext
) -> None:
    await render.ack(callback)
    domain = (await state.get_data()).get("domain")
    if not domain:
        await _need_restart(callback)
        return
    await render.show(bot, session, callback, render.random_count_text(domain), kb.count_kb())


@router.callback_query(F.data.startswith("r:cnt:"))
async def on_count(
    callback: CallbackQuery,
    bot: Bot,
    session: AsyncSession,
    state: FSMContext,
    cf: CloudflareClient,
) -> None:
    await render.ack(callback, "Membuat nama...")
    parts = cb.parse(callback.data)
    count = cb.safe_int(parts[2], 0) if len(parts) > 2 else 0
    if count < 1 or count > 10:
        await render.ack(callback, "Jumlah tidak valid.", True)
        return

    data = await state.get_data()
    zone_id, domain = data.get("zone_id"), data.get("domain")
    if not zone_id or not domain:
        await _need_restart(callback)
        return

    await _generate_into_batch(
        bot, session, callback, state, cf, zone_id, domain, count, new_batch=True
    )


@router.callback_query(F.data.startswith("r:re:"))
async def on_reroll(
    callback: CallbackQuery,
    bot: Bot,
    session: AsyncSession,
    state: FSMContext,
    cf: CloudflareClient,
) -> None:
    await render.ack(callback, "Mengacak ulang...")
    data = await state.get_data()
    zone_id, domain = data.get("zone_id"), data.get("domain")
    batch_id = data.get("batch_id")
    old_token = data.get("rsv_token")
    if not zone_id or not domain or not batch_id:
        await _need_restart(callback)
        return

    batch = await batches_repo.get_batch(session, batch_id)
    if batch is None or batch.status not in (
        BatchStatus.draft.value,
        BatchStatus.reserved.value,
    ):
        await _need_restart(callback)
        return

    if old_token:
        await reservation_service.release(session, old_token)

    await _generate_into_batch(
        bot,
        session,
        callback,
        state,
        cf,
        zone_id,
        domain,
        batch.requested_count,
        new_batch=False,
        batch=batch,
    )


async def _generate_into_batch(
    bot: Bot,
    session: AsyncSession,
    callback: CallbackQuery,
    state: FSMContext,
    cf: CloudflareClient,
    zone_id: str,
    domain: str,
    count: int,
    *,
    new_batch: bool,
    batch=None,
) -> None:
    token = reservation_service.new_token()
    reserved = await reservation_service.generate_and_reserve(
        session, cf, zone_id=zone_id, domain=domain, count=count, token=token
    )
    if not reserved:
        await reservation_service.release(session, token)
        await render.show(
            bot, session, callback,
            render.cloudflare_error_text("Gagal menghasilkan nama unik. Coba lagi."),
            main_menu_kb(),
        )
        return

    emails = [r.full_email for r in reserved]

    if new_batch or batch is None:
        batch = await batches_repo.create_batch(
            session,
            telegram_user_id=callback.from_user.id,
            zone_id=zone_id,
            domain=domain,
            requested_count=count,
            status=BatchStatus.reserved,
        )
    else:
        await batches_repo.set_batch_status(session, batch, BatchStatus.reserved)
    await batches_repo.replace_items(session, batch, emails)
    await session.commit()

    await state.update_data(batch_id=batch.id, rsv_token=token)
    await render.show(
        bot, session, callback,
        render.random_confirm_text(domain, emails),
        kb.confirm_kb(batch.id),
    )


# ---------------------------------------------------------------------------
# Confirm + create
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("r:ok:"))
async def on_confirm(
    callback: CallbackQuery,
    bot: Bot,
    session: AsyncSession,
    state: FSMContext,
    cf: CloudflareClient,
) -> None:
    parts = cb.parse(callback.data)
    batch_id = cb.safe_int(parts[2], 0) if len(parts) > 2 else 0

    # double-click protection: atomically move into 'processing'
    batch = await batches_repo.try_lock_for_processing(session, batch_id)
    if batch is None:
        await render.ack(callback, "\u23F3 Proses sedang berjalan / sudah selesai.", True)
        return
    await session.commit()
    await render.ack(callback)

    data = await state.get_data()
    domain = data.get("domain", batch.domain)
    items = await batches_repo.get_items(session, batch_id)
    to_attempt = [it for it in items if it.status == BatchItemStatus.pending.value]

    results = await _process_items(
        bot, session, callback, cf, batch.zone_id, domain, items, to_attempt
    )
    await _finish(bot, session, callback, batch, domain, results)


@router.callback_query(F.data.startswith("r:rf:"))
async def on_retry_failed(
    callback: CallbackQuery,
    bot: Bot,
    session: AsyncSession,
    state: FSMContext,
    cf: CloudflareClient,
) -> None:
    await render.ack(callback, "Mengganti nama yang gagal...")
    parts = cb.parse(callback.data)
    batch_id = cb.safe_int(parts[2], 0) if len(parts) > 2 else 0

    batch = await batches_repo.get_batch(session, batch_id)
    if batch is None:
        await _need_restart(callback)
        return

    items = await batches_repo.get_items(session, batch_id)
    failed = [it for it in items if it.status == BatchItemStatus.failed.value]
    if not failed:
        await render.ack(callback, "Tidak ada email yang gagal.", True)
        return

    # generate replacements for the failed slots
    token = reservation_service.new_token()
    reserved = await reservation_service.generate_and_reserve(
        session, cf, zone_id=batch.zone_id, domain=batch.domain,
        count=len(failed), token=token,
    )
    await state.update_data(rsv_token=token)

    for item, repl in zip(failed, reserved):
        item.full_email = repl.full_email
        item.status = BatchItemStatus.pending.value
        item.error_message = None
        item.cloudflare_rule_id = None
    await batches_repo.set_batch_status(session, batch, BatchStatus.processing)
    await session.commit()

    refreshed = await batches_repo.get_items(session, batch_id)
    to_attempt = [it for it in refreshed if it.status == BatchItemStatus.pending.value]
    results = await _process_items(
        bot, session, callback, cf, batch.zone_id, batch.domain, refreshed, to_attempt
    )
    await _finish(bot, session, callback, batch, batch.domain, results)


async def _process_items(
    bot: Bot,
    session: AsyncSession,
    callback: CallbackQuery,
    cf: CloudflareClient,
    zone_id: str,
    domain: str,
    all_items: list,
    to_attempt: list,
) -> list[tuple[bool, str, Optional[str]]]:
    total = len(to_attempt)
    done = 0
    for item in to_attempt:
        done += 1
        await render.show(
            bot, session, callback, render.processing_text(domain, done, total),
            kb.processing_kb(),
        )
        result = await email_service.create_one(
            session, cf,
            zone_id=zone_id, domain=domain, full_email=item.full_email,
            source=EmailSource.random, owner_id=callback.from_user.id,
        )
        if result.ok:
            item.status = BatchItemStatus.created.value
            item.cloudflare_rule_id = result.rule_id
            item.error_message = None
        else:
            item.status = BatchItemStatus.failed.value
            item.error_message = result.error
        await session.commit()

    # build ordered results for ALL items (so successes from prior runs show too)
    results: list[tuple[bool, str, Optional[str]]] = []
    for item in all_items:
        ok = item.status == BatchItemStatus.created.value
        results.append((ok, item.full_email, item.error_message))
    return results


async def _finish(
    bot: Bot,
    session: AsyncSession,
    callback: CallbackQuery,
    batch,
    domain: str,
    results: list[tuple[bool, str, Optional[str]]],
) -> None:
    success = [r for r in results if r[0]]
    failed = [r for r in results if not r[0]]

    if not failed:
        await batches_repo.set_batch_status(session, batch, BatchStatus.completed)
        await session.commit()
        await render.show(
            bot, session, callback,
            render.success_text(domain, [e for _, e, _ in success]),
            kb.success_kb(),
        )
    else:
        status = BatchStatus.partial if success else BatchStatus.failed
        await batches_repo.set_batch_status(session, batch, status)
        await session.commit()
        await render.show(
            bot, session, callback,
            render.partial_text(domain, results),
            kb.partial_kb(batch.id),
        )


async def _need_restart(callback: CallbackQuery) -> None:
    await render.ack(callback, "Sesi kedaluwarsa. Tekan /start lagi.", True)
