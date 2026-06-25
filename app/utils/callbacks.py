"""Callback data builders / parsers.

Telegram limits callback_data to 64 bytes. We therefore use short prefixes and
small integer indexes / database ids only. We NEVER put full emails, full zone
ids, API tokens or other sensitive / long data into callback_data.

Context that does not fit (zone ids, rule ids, the current page of items) is
kept in the per-user FSM state instead and referenced here by index.
"""
from __future__ import annotations

from typing import Optional

SEP = ":"

# ---- Menu --------------------------------------------------------------------
MENU_HOME = "m:home"
MENU_CREATE = "m:create"
MENU_LIST = "m:list"
MENU_DELETE = "m:delete"
MENU_DOMAINS = "m:domains"
MENU_REFRESH = "m:refresh"
NOOP = "noop"  # inert button (e.g. the "1/3" page indicator)


def _join(*parts: object) -> str:
    return SEP.join(str(p) for p in parts)


# ---- Domain listing / selection ---------------------------------------------
# purpose tells the handler what to do after a domain is picked.
#   c = create, l = list email, d = delete email
def domain_page(page: int, purpose: str) -> str:
    return _join("d", "pg", purpose, page)


def domain_select(index: int, purpose: str) -> str:
    """index = position of the domain on the current (cached) page."""
    return _join("d", "sel", purpose, index)


# ---- Create flow -------------------------------------------------------------
CREATE_RANDOM = "c:rand"
CREATE_MANUAL = "c:man"
CREATE_BACK_METHOD = "c:bmeth"   # back to the "random vs manual" chooser
CREATE_BACK_COUNT = "c:bcount"   # back to the "how many" chooser


def random_count(n: int) -> str:
    return _join("r", "cnt", n)


def random_reroll(batch_id: int) -> str:
    return _join("r", "re", batch_id)


def random_confirm(batch_id: int) -> str:
    return _join("r", "ok", batch_id)


def random_retry_failed(batch_id: int) -> str:
    return _join("r", "rf", batch_id)


MANUAL_START = "man:start"
MANUAL_USE_RANDOM = "man:rand"


def manual_confirm(draft_id: int) -> str:
    return _join("man", "ok", draft_id)


def manual_change(draft_id: int) -> str:
    return _join("man", "ch", draft_id)


# ---- Email list / detail / delete -------------------------------------------
def email_page(page: int) -> str:
    return _join("e", "pg", page)


def email_view(index: int) -> str:
    """index = position of the email on the current cached page."""
    return _join("e", "v", index)


def email_delete(index: int) -> str:
    return _join("e", "del", index)


def email_delete_confirm(index: int) -> str:
    return _join("e", "delok", index)


def email_back_list() -> str:
    return _join("e", "back")


CREATE_IN_DOMAIN = "e:create_here"


# ---- Parsing -----------------------------------------------------------------
def parse(data: str) -> list[str]:
    return data.split(SEP)


def safe_int(value: str, default: Optional[int] = None) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
