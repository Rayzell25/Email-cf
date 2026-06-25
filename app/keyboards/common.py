"""Shared inline-keyboard button builder with optional premium emoji.

``btn`` decides how to attach an emoji:
  * if a premium ``icon_custom_emoji_id`` is configured for the key (and premium
    emoji are enabled) -> plain text label + ``icon_custom_emoji_id`` field
    (Bot API 9.4+, needs a 9.4+ Local Bot API server to render);
  * otherwise -> the plain unicode fallback is prefixed to the label.

Attaching ``icon_custom_emoji_id`` is wrapped in try/except so that any aiogram
version which rejects the extra field degrades gracefully to a unicode prefix
instead of crashing.
"""
from __future__ import annotations

from typing import Optional

from aiogram.types import InlineKeyboardButton

from app.utils.emoji import fallback, icon


def btn(
    label: str,
    callback_data: Optional[str] = None,
    *,
    emoji_key: Optional[str] = None,
    url: Optional[str] = None,
) -> InlineKeyboardButton:
    kwargs: dict = {"text": label}
    if callback_data is not None:
        kwargs["callback_data"] = callback_data
    if url is not None:
        kwargs["url"] = url

    icon_id = icon(emoji_key) if emoji_key else None
    if icon_id:
        try:
            return InlineKeyboardButton(**kwargs, icon_custom_emoji_id=icon_id)
        except Exception:
            pass  # fall back to unicode prefix below

    if emoji_key:
        prefix = fallback(emoji_key)
        if prefix:
            kwargs["text"] = f"{prefix} {label}"
    return InlineKeyboardButton(**kwargs)
