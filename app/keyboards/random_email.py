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
            [btn("MASUKKAN EMAIL", cb.CREATE_MANUAL, emoji_key="pencil")],
            [btn("KEMBALI", cb.domain_page(1, "c"), emoji_key="back")],
        ]
    )


def count_kb() -> InlineKeyboardMarkup:
    row1 = [btn(str(n), cb.random_count(n)) for n in range(1, 6)]
    row2 = [btn(str(n), cb.random_count(n)) for n in range(6, 11)]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            row1,
            row2,
            [btn("INPUT MANUAL", cb.CREATE_MANUAL, emoji_key="pencil")],
            [btn("KEMBALI", cb.CREATE_BACK_METHOD, emoji_key="back")],
        ]
    )


def confirm_kb(batch_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn("BUAT SEMUA", cb.random_confirm(batch_id), emoji_key="ok")],
            [btn("ACAK ULANG", cb.random_reroll(batch_id), emoji_key="refresh")],
            [btn("INPUT MANUAL", cb.CREATE_MANUAL, emoji_key="pencil")],
            [btn("KEMBALI", cb.CREATE_BACK_COUNT, emoji_key="back")],
        ]
    )


def processing_kb() -> InlineKeyboardMarkup:
    """No actionable buttons while processing (prevents double click)."""
    return InlineKeyboardMarkup(inline_keyboard=[])


def success_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn("LIHAT LIST EMAIL", cb.MENU_LIST, emoji_key="list")],
            [btn("BUAT RANDOM LAGI", cb.CREATE_RANDOM, emoji_key="dice")],
            [btn("BUAT MANUAL", cb.CREATE_MANUAL, emoji_key="pencil")],
            [btn("MENU UTAMA", cb.MENU_HOME, emoji_key="home")],
        ]
    )


def partial_kb(batch_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn("GANTI DAN COBA LAGI", cb.random_retry_failed(batch_id), emoji_key="refresh")],
            [btn("LIHAT LIST EMAIL", cb.MENU_LIST, emoji_key="list")],
            [btn("BUAT EMAIL LAIN", cb.CREATE_RANDOM, emoji_key="dice")],
            [btn("MENU UTAMA", cb.MENU_HOME, emoji_key="home")],
        ]
    )



# --- manual input keyboards (kept here with the rest of the create flow) -----
def manual_prompt_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn("GUNAKAN RANDOM", cb.CREATE_RANDOM, emoji_key="dice")],
            [btn("KEMBALI", cb.CREATE_BACK_METHOD, emoji_key="back")],
        ]
    )


def manual_confirm_kb(draft_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn("BUAT EMAIL", cb.manual_confirm(draft_id), emoji_key="ok")],
            [btn("GANTI NAMA", cb.manual_change(draft_id), emoji_key="pencil")],
            [btn("GUNAKAN RANDOM", cb.CREATE_RANDOM, emoji_key="dice")],
            [btn("KEMBALI", cb.CREATE_BACK_METHOD, emoji_key="back")],
        ]
    )
