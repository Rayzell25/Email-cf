"""Domain list keyboard (paginated, 20 per page)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.keyboards.common import btn, pagination_row
from app.services.cloudflare import Zone
from app.utils import callbacks as cb
from app.utils.pagination import Page


def domains_kb(page: Page[Zone], purpose: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for index, zone in enumerate(page.items):
        rows.append([btn(zone.name, cb.domain_select(index, purpose))])

    nav = pagination_row(
        page,
        cb.domain_page(page.page - 1, purpose),
        cb.domain_page(page.page + 1, purpose),
    )
    if nav:
        rows.append(nav)
    rows.append([btn("MAIN MENU", cb.MENU_HOME, emoji_key="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
