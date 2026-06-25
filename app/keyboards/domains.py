"""Domain list keyboard (paginated, 20 per page)."""
from __future__ import annotations

from typing import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.keyboards.common import btn
from app.services.cloudflare import Zone
from app.utils import callbacks as cb
from app.utils.pagination import Page


def domains_kb(page: Page[Zone], purpose: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for index, zone in enumerate(page.items):
        rows.append([btn(zone.name, cb.domain_select(index, purpose))])

    rows.append(_nav_row(page, purpose))
    rows.append([btn("MENU UTAMA", cb.MENU_HOME, emoji_key="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _nav_row(page: Page[Zone], purpose: str) -> list[InlineKeyboardButton]:
    prev_cb = cb.domain_page(page.page - 1, purpose) if page.has_prev else cb.NOOP
    next_cb = cb.domain_page(page.page + 1, purpose) if page.has_next else cb.NOOP
    return [
        btn("KEMBALI", prev_cb, emoji_key="back"),
        btn(page.label, cb.NOOP),
        InlineKeyboardButton(text="BERIKUTNYA \u25B6\ufe0f", callback_data=next_cb),
    ]
