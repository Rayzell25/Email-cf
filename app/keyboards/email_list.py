"""Keyboards for listing / viewing / deleting emails."""
from __future__ import annotations

from typing import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.keyboards.common import btn
from app.services.cloudflare import RoutingRule
from app.utils import callbacks as cb
from app.utils.pagination import Page


def email_list_kb(
    page: Page[RoutingRule], *, allow_create: bool = True
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for index, rule in enumerate(page.items):
        rows.append([btn(rule.email, cb.email_view(index))])

    rows.append(_nav_row(page))
    if allow_create:
        rows.append([btn("BUAT EMAIL DI DOMAIN INI", cb.CREATE_IN_DOMAIN, emoji_key="create")])
    rows.append([btn("MENU UTAMA", cb.MENU_HOME, emoji_key="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _nav_row(page: Page[RoutingRule]) -> list[InlineKeyboardButton]:
    prev_cb = cb.email_page(page.page - 1) if page.has_prev else cb.NOOP
    next_cb = cb.email_page(page.page + 1) if page.has_next else cb.NOOP
    return [
        btn("KEMBALI", prev_cb, emoji_key="back"),
        btn(page.label, cb.NOOP),
        InlineKeyboardButton(text="BERIKUTNYA \u25B6\ufe0f", callback_data=next_cb),
    ]


def email_detail_kb(index: int, *, can_delete: bool = True) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if can_delete:
        rows.append([btn("HAPUS EMAIL", cb.email_delete(index), emoji_key="delete")])
    rows.append([btn("KEMBALI KE LIST", cb.email_back_list(), emoji_key="back")])
    rows.append([btn("MENU UTAMA", cb.MENU_HOME, emoji_key="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def delete_confirm_kb(index: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn("YA, HAPUS", cb.email_delete_confirm(index), emoji_key="delete")],
            [btn("BATAL", cb.email_back_list(), emoji_key="fail")],
        ]
    )


def delete_result_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn("HAPUS EMAIL LAIN", cb.MENU_DELETE, emoji_key="delete")],
            [btn("KEMBALI KE LIST", cb.email_back_list(), emoji_key="list")],
            [btn("MENU UTAMA", cb.MENU_HOME, emoji_key="home")],
        ]
    )


def empty_domain_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn("BUAT EMAIL DI DOMAIN INI", cb.CREATE_IN_DOMAIN, emoji_key="create")],
            [btn("KEMBALI", cb.MENU_HOME, emoji_key="back")],
        ]
    )
