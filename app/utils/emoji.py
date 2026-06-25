"""Premium / custom emoji helpers (aiogram 3) + safe fallback.

Two different places, two different mechanisms (do NOT mix them up):

  1. INLINE BUTTON label  -> field ``icon_custom_emoji_id`` (Bot API 9.4+).
     Button text stays PLAIN; the custom emoji id goes in its own field.
  2. MESSAGE TEXT / caption -> tag ``<tg-emoji emoji-id="...">FALLBACK</tg-emoji>``
     with ``parse_mode=HTML``.

Requirements for premium emoji to actually render:
  * bot OWNER has Telegram Premium, AND
  * the Bot API server supports it (a self-hosted Local Bot API server must be
    version 9.4+ -- an outdated server silently drops custom emoji).

If premium emoji are disabled or unavailable, everything degrades gracefully to
plain unicode emoji (see :func:`strip_premium` and the ``safe_*`` send helpers
in :mod:`app.utils.ui`).

How to fill in real ids: send the premium emoji to your bot, then read
``message.entities[].custom_emoji_id`` (a ~19 digit string). Put it below.
"""
from __future__ import annotations

import re
from typing import Dict, Optional, Tuple

from app.config import get_settings

# key -> (fallback_unicode, custom_emoji_id | None)
# Fill the second value with your own custom_emoji_id (as a string) to enable a
# premium/animated emoji for that slot. Leave None to always use unicode.
EMOJI: Dict[str, Tuple[str, Optional[str]]] = {
    "cloud": ("\u2601\ufe0f", None),       # ☁️
    "create": ("\u2795", None),            # ➕
    "list": ("\U0001F4CB", None),          # 📋
    "delete": ("\U0001F5D1", None),        # 🗑
    "domain": ("\U0001F310", None),        # 🌐
    "refresh": ("\U0001F504", None),       # 🔄
    "back": ("\u25C0\ufe0f", None),        # ◀️
    "next": ("\u25B6\ufe0f", None),        # ▶️
    "home": ("\U0001F3E0", None),          # 🏠
    "dice": ("\U0001F3B2", None),          # 🎲
    "pencil": ("\u270F\ufe0f", None),      # ✏️
    "ok": ("\u2705", None),                # ✅
    "fail": ("\u274C", None),              # ❌
    "wait": ("\u23F3", None),              # ⏳
    "warn": ("\u26A0\ufe0f", None),        # ⚠️
    "mailbox": ("\U0001F4ED", None),       # 📭
    "mail": ("\U0001F4E7", None),          # 📧
    "green": ("\U0001F7E2", None),         # 🟢
    "stop": ("\u26D4", None),              # ⛔
}

_TG_EMOJI_RE = re.compile(r"<tg-emoji[^>]*>([\s\S]*?)</tg-emoji>", re.IGNORECASE)


def _premium_enabled() -> bool:
    return bool(get_settings().use_premium_emoji)


def fallback(key: str) -> str:
    """Return only the plain unicode fallback for a key."""
    item = EMOJI.get(key)
    return item[0] if item else ""


def pe(key: str) -> str:
    """Render an emoji for use inside MESSAGE TEXT.

    Returns a ``<tg-emoji>`` tag when premium emoji are enabled and an id is
    configured; otherwise the plain unicode fallback.
    """
    item = EMOJI.get(key)
    if not item:
        return ""
    unicode_fallback, custom_id = item
    if _premium_enabled() and custom_id:
        return f'<tg-emoji emoji-id="{custom_id}">{unicode_fallback}</tg-emoji>'
    return unicode_fallback


def icon(key: str) -> Optional[str]:
    """Return the ``icon_custom_emoji_id`` value for a BUTTON, or None.

    None means "do not attach an icon field" -- the button keeps its plain
    unicode emoji in the text instead.
    """
    item = EMOJI.get(key)
    if not item:
        return None
    _, custom_id = item
    if _premium_enabled() and custom_id:
        return custom_id
    return None


def has_premium(text: str) -> bool:
    return bool(_TG_EMOJI_RE.search(text or ""))


def strip_premium(text: str) -> str:
    """Remove ``<tg-emoji>`` tags, leaving the unicode fallback content."""
    return _TG_EMOJI_RE.sub(lambda m: m.group(1), text or "")
