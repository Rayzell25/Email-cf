"""Shared rendering helpers + dashboard text builders.

All bot text is built here so the single-message dashboard stays consistent.
Message text uses :func:`app.utils.emoji.pe` so premium emoji are used when
enabled and gracefully fall back to unicode otherwise.
"""
from __future__ import annotations

from typing import Optional, Union

from aiogram import Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import dashboard as dashboard_service
from app.services.cloudflare import RoutingRule
from app.utils.emoji import pe
from app.utils.pagination import Page

Event = Union[Message, CallbackQuery]


def _ids(event: Event) -> tuple[int, int]:
    """Return (user_id, chat_id) for a Message or CallbackQuery."""
    user_id = event.from_user.id
    if isinstance(event, CallbackQuery):
        chat_id = event.message.chat.id if event.message else user_id
    else:
        chat_id = event.chat.id
    return user_id, chat_id


async def show(
    bot: Bot,
    session: AsyncSession,
    event: Event,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    *,
    fresh: bool = False,
) -> None:
    """Render text on the user's single dashboard message.

    ``fresh=True`` forces a brand new dashboard message (used by /start).
    """
    user_id, chat_id = _ids(event)
    if fresh:
        await dashboard_service.create_fresh(
            bot,
            session,
            user_id=user_id,
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
        )
        return
    await dashboard_service.render(
        bot,
        session,
        user_id=user_id,
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
    )


async def ack(event: CallbackQuery, text: str = "", show_alert: bool = False) -> None:
    """Answer a callback query (clears the button spinner). Best-effort."""
    try:
        await event.answer(text or None, show_alert=show_alert)
    except Exception:
        pass


# ----------------------------------------------------------------------------
# Text builders
# ----------------------------------------------------------------------------
def menu_text(total_domains: int, total_emails: int, connected: bool) -> str:
    status = (
        f"{pe('green')} Cloudflare API: Terhubung"
        if connected
        else f"{pe('fail')} Cloudflare API: Tidak terhubung"
    )
    return (
        f"{pe('cloud')} <b>CLOUDFLARE EMAIL MANAGER</b>\n\n"
        "Kelola email Cloudflare langsung dari Telegram.\n\n"
        f"{pe('domain')} Total domain: <b>{total_domains}</b>\n"
        f"{pe('mail')} Email tercatat: <b>{total_emails}</b>\n"
        f"{status}\n\n"
        "Pilih menu:"
    )


_PURPOSE_TITLE = {
    "c": ("create", "BUAT EMAIL"),
    "l": ("list", "LIST EMAIL"),
    "d": ("delete", "HAPUS EMAIL"),
}


def domains_text(purpose: str, page: Page) -> str:
    emoji_key, title = _PURPOSE_TITLE.get(purpose, ("domain", "LIST DOMAIN"))
    if page.total_items == 0:
        return (
            f"{pe('domain')} <b>LIST DOMAIN</b>\n\n"
            "Belum ada domain pada akun Cloudflare ini."
        )
    return (
        f"{pe(emoji_key)} <b>{title}</b>\n\n"
        f"Total domain: <b>{page.total_items}</b>\n"
        f"Halaman: <b>{page.page} dari {page.total_pages}</b>\n\n"
        "Pilih domain:"
    )


def method_text(domain: str) -> str:
    return (
        f"{pe('create')} <b>BUAT EMAIL</b>\n\n"
        f"Domain dipilih:\n{pe('domain')} <b>{domain}</b>\n\n"
        "Silakan pilih cara membuat email."
    )


def random_count_text(domain: str) -> str:
    return (
        f"{pe('dice')} <b>BUAT EMAIL RANDOM</b>\n\n"
        f"Domain:\n{pe('domain')} <b>{domain}</b>\n\n"
        "Pilih jumlah email yang ingin dibuat (1-10):"
    )


def random_confirm_text(domain: str, emails: list[str]) -> str:
    lines = "\n".join(f"{i}. {e}" for i, e in enumerate(emails, start=1))
    return (
        f"{pe('dice')} <b>KONFIRMASI EMAIL RANDOM</b>\n\n"
        f"Domain:\n{pe('domain')} <b>{domain}</b>\n\n"
        f"Jumlah:\n<b>{len(emails)} email</b>\n\n"
        "Email yang akan dibuat:\n"
        f"{lines}\n\n"
        "Lanjutkan pembuatan?"
    )


def processing_text(domain: str, current: int, total: int) -> str:
    return (
        f"{pe('wait')} <b>MEMBUAT EMAIL</b>\n\n"
        f"Domain:\n{pe('domain')} <b>{domain}</b>\n\n"
        f"Proses:\n<b>{current} dari {total}</b>"
    )


def success_text(domain: str, emails: list[str]) -> str:
    lines = "\n".join(f"{pe('ok')} {e}" for e in emails)
    return (
        f"{pe('ok')} <b>EMAIL BERHASIL DIBUAT</b>\n\n"
        f"Domain:\n{pe('domain')} <b>{domain}</b>\n\n"
        f"Berhasil:\n<b>{len(emails)} email</b>\n\n"
        f"{lines}"
    )


def partial_text(
    domain: str, results: list[tuple[bool, str, Optional[str]]]
) -> str:
    success = [r for r in results if r[0]]
    failed = [r for r in results if not r[0]]
    lines = []
    for ok, email, err in results:
        if ok:
            lines.append(f"{pe('ok')} {email}")
        else:
            lines.append(f"{pe('fail')} {email}")
            if err:
                lines.append(f"   {err}")
    body = "\n".join(lines)
    return (
        f"{pe('warn')} <b>PEMBUATAN SELESAI</b>\n\n"
        f"Domain:\n{pe('domain')} <b>{domain}</b>\n\n"
        f"Berhasil: <b>{len(success)}</b>   Gagal: <b>{len(failed)}</b>\n\n"
        f"{body}"
    )


def manual_prompt_text(domain: str) -> str:
    return (
        f"{pe('pencil')} <b>INPUT EMAIL MANUAL</b>\n\n"
        f"Domain:\n{pe('domain')} <b>{domain}</b>\n\n"
        "Silakan ketik nama email.\n\n"
        "Contoh:\nsupport\nadmin.store\norder-2026\n\n"
        f"Tidak perlu menulis @{domain}."
    )


def manual_invalid_text(domain: str, error: str) -> str:
    return (
        f"{pe('warn')} <b>INPUT TIDAK VALID</b>\n\n"
        f"{error}\n\n"
        f"Domain:\n{pe('domain')} <b>{domain}</b>\n\n"
        "Silakan ketik nama email lagi."
    )


def manual_confirm_text(domain: str, full_email: str) -> str:
    return (
        f"{pe('pencil')} <b>KONFIRMASI EMAIL</b>\n\n"
        "Alamat yang akan dibuat:\n"
        f"{pe('mail')} <b>{full_email}</b>\n\n"
        f"Domain:\n{pe('domain')} <b>{domain}</b>\n\n"
        "Lanjutkan?"
    )


def email_list_text(domain: str, page: Page[RoutingRule]) -> str:
    return (
        f"{pe('list')} <b>LIST EMAIL</b>\n\n"
        f"Domain:\n{pe('domain')} <b>{domain}</b>\n\n"
        f"Total email: <b>{page.total_items}</b>\n"
        f"Halaman: <b>{page.page} dari {page.total_pages}</b>\n\n"
        "Pilih email untuk melihat detail:"
    )


def email_empty_text(domain: str) -> str:
    return (
        f"{pe('mailbox')} <b>BELUM ADA EMAIL</b>\n\n"
        f"Domain:\n{pe('domain')} <b>{domain}</b>\n\n"
        "Belum ada alamat email pada domain ini."
    )


def email_detail_text(
    rule: RoutingRule,
    domain: str,
    *,
    created_via_bot: bool,
    created_at: Optional[str],
) -> str:
    status = f"{pe('green')} Aktif" if rule.enabled else f"{pe('fail')} Nonaktif"
    via = "Ya" if created_via_bot else "Tidak"
    when = created_at if created_at else "Tidak diketahui"
    return (
        f"{pe('mail')} <b>DETAIL EMAIL</b>\n\n"
        f"Alamat:\n<b>{rule.email}</b>\n\n"
        f"Domain:\n{domain}\n\n"
        f"Tujuan:\n{rule.destination or '-'}\n\n"
        f"Status:\n{status}\n\n"
        f"Dibuat melalui bot:\n{via}\n\n"
        f"Tanggal dibuat:\n{when}"
    )


def delete_confirm_text(full_email: str) -> str:
    return (
        f"{pe('warn')} <b>HAPUS EMAIL</b>\n\n"
        "Anda akan menghapus:\n"
        f"{pe('mail')} <b>{full_email}</b>\n\n"
        "Setelah dihapus, alamat ini tidak lagi menerima "
        "atau meneruskan email.\n\n"
        "Yakin ingin menghapusnya?"
    )


def delete_success_text(full_email: str) -> str:
    return (
        f"{pe('ok')} <b>EMAIL BERHASIL DIHAPUS</b>\n\n"
        f"{pe('mail')} <b>{full_email}</b>\n\n"
        "Alamat sudah dihapus dari Cloudflare Email Routing."
    )


def cloudflare_error_text(message: str) -> str:
    return (
        f"{pe('fail')} <b>CLOUDFLARE API ERROR</b>\n\n"
        f"{message}\n\n"
        "Kemungkinan:\n"
        "- API Token salah\n"
        "- Permission token kurang\n"
        "- Cloudflare sedang gangguan"
    )


def domain_inactive_text(domain: str) -> str:
    return (
        f"{pe('warn')} <b>DOMAIN TIDAK AKTIF</b>\n\n"
        f"Domain:\n{domain}\n\n"
        "Status domain Cloudflare tidak aktif, atau Email Routing belum aktif."
    )
