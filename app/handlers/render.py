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
# Text builders (English UI)
# ----------------------------------------------------------------------------
def menu_text(total_domains: int, total_emails: int, connected: bool) -> str:
    status = (
        f"{pe('green')} Cloudflare API: Connected"
        if connected
        else f"{pe('fail')} Cloudflare API: Not connected"
    )
    return (
        f"{pe('cloud')} <b>CLOUDFLARE EMAIL MANAGER</b>\n\n"
        "Manage your Cloudflare email routing from Telegram.\n\n"
        f"{pe('domain')} Total domains: <b>{total_domains}</b>\n"
        f"{pe('mail')} Saved emails: <b>{total_emails}</b>\n"
        f"{status}\n\n"
        "Choose a menu:"
    )


_PURPOSE_TITLE = {
    "c": ("create", "CREATE EMAIL"),
    "l": ("list", "LIST EMAIL"),
    "d": ("delete", "DELETE EMAIL"),
}


def domains_text(purpose: str, page: Page) -> str:
    emoji_key, title = _PURPOSE_TITLE.get(purpose, ("domain", "LIST DOMAIN"))
    if page.total_items == 0:
        return (
            f"{pe('domain')} <b>LIST DOMAIN</b>\n\n"
            "No domains found on this Cloudflare account."
        )
    return (
        f"{pe(emoji_key)} <b>{title}</b>\n\n"
        f"Total domains: <b>{page.total_items}</b>\n"
        f"Page: <b>{page.page} of {page.total_pages}</b>\n\n"
        "Select a domain:"
    )


def method_text(domain: str) -> str:
    return (
        f"{pe('create')} <b>CREATE EMAIL</b>\n\n"
        f"Selected domain:\n{pe('domain')} <b>{domain}</b>\n\n"
        "Choose how to create the email."
    )


def random_count_text(domain: str) -> str:
    return (
        f"{pe('dice')} <b>RANDOM EMAIL</b>\n\n"
        f"Domain:\n{pe('domain')} <b>{domain}</b>\n\n"
        "Choose how many emails to create (1-10):"
    )


def random_confirm_text(domain: str, emails: list[str]) -> str:
    lines = "\n".join(f"{i}. {e}" for i, e in enumerate(emails, start=1))
    return (
        f"{pe('dice')} <b>CONFIRM RANDOM EMAIL</b>\n\n"
        f"Domain:\n{pe('domain')} <b>{domain}</b>\n\n"
        f"Count:\n<b>{len(emails)} emails</b>\n\n"
        "Emails to create:\n"
        f"{lines}\n\n"
        "Proceed?"
    )


def processing_text(domain: str, current: int, total: int) -> str:
    return (
        f"{pe('wait')} <b>CREATING EMAIL</b>\n\n"
        f"Domain:\n{pe('domain')} <b>{domain}</b>\n\n"
        f"Progress:\n<b>{current} of {total}</b>"
    )


def success_text(domain: str, emails: list[str]) -> str:
    lines = "\n".join(f"{pe('ok')} {e}" for e in emails)
    return (
        f"{pe('ok')} <b>EMAILS CREATED</b>\n\n"
        f"Domain:\n{pe('domain')} <b>{domain}</b>\n\n"
        f"Created:\n<b>{len(emails)} emails</b>\n\n"
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
        f"{pe('warn')} <b>CREATION FINISHED</b>\n\n"
        f"Domain:\n{pe('domain')} <b>{domain}</b>\n\n"
        f"Success: <b>{len(success)}</b>   Failed: <b>{len(failed)}</b>\n\n"
        f"{body}"
    )


def manual_prompt_text(domain: str) -> str:
    return (
        f"{pe('pencil')} <b>MANUAL EMAIL INPUT</b>\n\n"
        f"Domain:\n{pe('domain')} <b>{domain}</b>\n\n"
        "Type the email name.\n\n"
        "Example:\nsupport\nadmin.store\norder-2026\n\n"
        f"No need to type @{domain}."
    )


def manual_invalid_text(domain: str, error: str) -> str:
    return (
        f"{pe('warn')} <b>INVALID INPUT</b>\n\n"
        f"{error}\n\n"
        f"Domain:\n{pe('domain')} <b>{domain}</b>\n\n"
        "Please type the email name again."
    )


def manual_confirm_text(domain: str, full_email: str) -> str:
    return (
        f"{pe('pencil')} <b>CONFIRM EMAIL</b>\n\n"
        "Address to create:\n"
        f"{pe('mail')} <b>{full_email}</b>\n\n"
        f"Domain:\n{pe('domain')} <b>{domain}</b>\n\n"
        "Proceed?"
    )


def email_list_text(domain: str, page: Page[RoutingRule]) -> str:
    return (
        f"{pe('list')} <b>LIST EMAIL</b>\n\n"
        f"Domain:\n{pe('domain')} <b>{domain}</b>\n\n"
        f"Total emails: <b>{page.total_items}</b>\n"
        f"Page: <b>{page.page} of {page.total_pages}</b>\n\n"
        "Select an email to view details:"
    )


def email_empty_text(domain: str) -> str:
    return (
        f"{pe('mailbox')} <b>NO EMAILS YET</b>\n\n"
        f"Domain:\n{pe('domain')} <b>{domain}</b>\n\n"
        "There are no email addresses on this domain."
    )


def email_detail_text(
    rule: RoutingRule,
    domain: str,
    *,
    created_via_bot: bool,
    created_at: Optional[str],
) -> str:
    status = f"{pe('green')} Active" if rule.enabled else f"{pe('fail')} Inactive"
    via = "Yes" if created_via_bot else "No"
    when = created_at if created_at else "Unknown"
    return (
        f"{pe('mail')} <b>EMAIL DETAILS</b>\n\n"
        f"Address:\n<b>{rule.email}</b>\n\n"
        f"Domain:\n{domain}\n\n"
        f"Destination:\n{rule.destination or '-'}\n\n"
        f"Status:\n{status}\n\n"
        f"Created via bot:\n{via}\n\n"
        f"Created at:\n{when}"
    )


def delete_confirm_text(full_email: str) -> str:
    return (
        f"{pe('warn')} <b>DELETE EMAIL</b>\n\n"
        "You are about to delete:\n"
        f"{pe('mail')} <b>{full_email}</b>\n\n"
        "After deletion, this address will no longer receive "
        "or forward email.\n\n"
        "Are you sure?"
    )


def delete_success_text(full_email: str) -> str:
    return (
        f"{pe('ok')} <b>EMAIL DELETED</b>\n\n"
        f"{pe('mail')} <b>{full_email}</b>\n\n"
        "The address has been removed from Cloudflare Email Routing."
    )


def cloudflare_error_text(message: str) -> str:
    return (
        f"{pe('fail')} <b>CLOUDFLARE API ERROR</b>\n\n"
        f"{message}\n\n"
        "Possible causes:\n"
        "- Wrong API token\n"
        "- Missing token permissions\n"
        "- Cloudflare outage"
    )


def domain_inactive_text(domain: str) -> str:
    return (
        f"{pe('warn')} <b>DOMAIN NOT ACTIVE</b>\n\n"
        f"Domain:\n{domain}\n\n"
        "The Cloudflare domain is not active, or Email Routing is not enabled."
    )
