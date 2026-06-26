"""Keyboards for the create-email (random + method) flow."""
from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup

from app.keyboards.common import btn
from app.utils import callbacks as cb


def method_kb() -> InlineKeyboardMarkup:
    """Choose how to create after a domain is selected."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn("RANDOM", cb.CREATE_RANDOM, emoji_key="dice")],
            [btn("ENTER EMAIL", cb.CREATE_MANUAL, emoji_key="pencil")],
            [btn("BACK", cb.domain_page(1, "c"), emoji_key="back")],
        ]
    )


def count_kb() -> InlineKeyboardMarkup:
    # numbers 1..15 arranged in 2 columns (left & right), 2 per row
    rows: list[list] = []
    numbers = list(range(1, 16))
    for i in range(0, len(numbers), 2):
        rows.append([btn(str(n), cb.random_count(n)) for n in numbers[i:i + 2]])
    rows.append([btn("MANUAL INPUT", cb.CREATE_MANUAL, emoji_key="pencil")])
    rows.append([btn("BACK", cb.CREATE_BACK_METHOD, emoji_key="back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_kb(batch_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn("CREATE ALL", cb.random_confirm(batch_id), emoji_key="ok")],
            [btn("SHUFFLE", cb.random_reroll(batch_id), emoji_key="refresh")],
            [btn("MANUAL INPUT", cb.CREATE_MANUAL, emoji_key="pencil")],
            [btn("BACK", cb.CREATE_BACK_COUNT, emoji_key="back")],
        ]
    )


def processing_kb() -> InlineKeyboardMarkup:
    """No actionable buttons while processing (prevents double click)."""
    return InlineKeyboardMarkup(inline_keyboard=[])


def success_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn("VIEW EMAIL LIST", cb.MENU_LIST, emoji_key="list")],
            [btn("CREATE RANDOM AGAIN", cb.CREATE_RANDOM, emoji_key="dice")],
            [btn("CREATE MANUAL", cb.CREATE_MANUAL, emoji_key="pencil")],
            [btn("MAIN MENU", cb.MENU_HOME, emoji_key="home")],
        ]
    )


def partial_kb(batch_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn("REPLACE & RETRY", cb.random_retry_failed(batch_id), emoji_key="refresh")],
            [btn("VIEW EMAIL LIST", cb.MENU_LIST, emoji_key="list")],
            [btn("CREATE OTHER", cb.CREATE_RANDOM, emoji_key="dice")],
            [btn("MAIN MENU", cb.MENU_HOME, emoji_key="home")],
        ]
    )


# --- manual input keyboards (kept here with the rest of the create flow) -----
def manual_prompt_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn("USE RANDOM", cb.CREATE_RANDOM, emoji_key="dice")],
            [btn("BACK", cb.CREATE_BACK_METHOD, emoji_key="back")],
        ]
    )


def manual_confirm_kb(draft_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn("CREATE EMAIL", cb.manual_confirm(draft_id), emoji_key="ok")],
            [btn("CHANGE NAME", cb.manual_change(draft_id), emoji_key="pencil")],
            [btn("USE RANDOM", cb.CREATE_RANDOM, emoji_key="dice")],
            [btn("BACK", cb.CREATE_BACK_METHOD, emoji_key="back")],
        ]
    )
