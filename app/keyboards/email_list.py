"""Keyboards for listing / viewing / deleting emails."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.keyboards.common import btn, pagination_row
from app.services.cloudflare import RoutingRule
from app.utils import callbacks as cb
from app.utils.pagination import Page


def email_list_kb(
    page: Page[RoutingRule], *, allow_create: bool = True
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for index, rule in enumerate(page.items):
        rows.append([btn(rule.email, cb.email_view(index))])

    nav = pagination_row(page, cb.email_page(page.page - 1), cb.email_page(page.page + 1))
    if nav:
        rows.append(nav)
    if allow_create:
        rows.append([btn("CREATE EMAIL IN THIS DOMAIN", cb.CREATE_IN_DOMAIN, emoji_key="create")])
    rows.append([btn("MAIN MENU", cb.MENU_HOME, emoji_key="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def email_detail_kb(index: int, *, can_delete: bool = True) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if can_delete:
        rows.append([btn("DELETE EMAIL", cb.email_delete(index), emoji_key="delete")])
    rows.append([btn("BACK TO LIST", cb.email_back_list(), emoji_key="back")])
    rows.append([btn("MAIN MENU", cb.MENU_HOME, emoji_key="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def delete_confirm_kb(index: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn("YES, DELETE", cb.email_delete_confirm(index), emoji_key="delete")],
            [btn("CANCEL", cb.email_back_list(), emoji_key="fail")],
        ]
    )


def delete_result_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn("DELETE ANOTHER", cb.MENU_DELETE, emoji_key="delete")],
            [btn("BACK TO LIST", cb.email_back_list(), emoji_key="list")],
            [btn("MAIN MENU", cb.MENU_HOME, emoji_key="home")],
        ]
    )


def empty_domain_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn("CREATE EMAIL IN THIS DOMAIN", cb.CREATE_IN_DOMAIN, emoji_key="create")],
            [btn("BACK", cb.MENU_HOME, emoji_key="back")],
        ]
    )
