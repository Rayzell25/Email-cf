"""Main menu keyboard."""
from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup

from app.keyboards.common import btn
from app.utils import callbacks as cb


def main_menu_kb() -> InlineKeyboardMarkup:
    # 2 columns, equal width; the last button is full width on its own row.
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                btn("CREATE EMAIL", cb.MENU_CREATE, emoji_key="create"),
                btn("LIST EMAIL", cb.MENU_LIST, emoji_key="list"),
            ],
            [
                btn("DELETE EMAIL", cb.MENU_DELETE, emoji_key="delete"),
                btn("LIST DOMAIN", cb.MENU_DOMAINS, emoji_key="domain"),
            ],
            [btn("REFRESH", cb.MENU_REFRESH, emoji_key="refresh")],
        ]
    )


def error_retry_kb(retry_callback: str = cb.MENU_REFRESH) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn("TRY AGAIN", retry_callback, emoji_key="refresh")],
            [btn("MAIN MENU", cb.MENU_HOME, emoji_key="home")],
        ]
    )
