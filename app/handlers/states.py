"""FSM states + shared state-data helpers.

Most navigation is stateless (callbacks). We only need a real FSM *state* for
the manual-name text input, so the plain message handler only fires while the
user is actually being asked to type a name.

State *data* (a plain dict) caches per-user context that is too large or too
sensitive for callback_data:
    zones        -> list[[id, name, status]] (sorted) for domain index lookup
    purpose      -> 'c' | 'l' | 'd' (what picking a domain should do)
    zone_id      -> selected zone id
    domain       -> selected domain name
    batch_id     -> current random batch id
    email_rules  -> list[[rule_id, email, destination, enabled]] of current page
    email_page   -> current email page number
    view_index   -> index of the email being viewed
    manual_draft -> [local_part, full_email, token, generated_name_id]
"""
from __future__ import annotations

from typing import Optional

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.services.cloudflare import CloudflareClient, Zone


class Flow(StatesGroup):
    manual_input = State()


# --- zones cache --------------------------------------------------------------
async def set_zones(state: FSMContext, zones: list[Zone]) -> None:
    await state.update_data(zones=[[z.id, z.name, z.status] for z in zones])


def _to_zones(raw: Optional[list]) -> list[Zone]:
    zones: list[Zone] = []
    for item in raw or []:
        try:
            zones.append(Zone(id=item[0], name=item[1], status=item[2]))
        except (IndexError, TypeError):
            continue
    return zones


async def get_zones(
    state: FSMContext, cf: CloudflareClient, *, force: bool = False
) -> list[Zone]:
    data = await state.get_data()
    if not force:
        cached = _to_zones(data.get("zones"))
        if cached:
            return cached
    zones = await cf.list_zones()
    await set_zones(state, zones)
    return zones


async def get_zone_by_index_on_page(
    state: FSMContext, index: int
) -> Optional[Zone]:
    """Resolve a domain button index to a Zone using the cached current page."""
    data = await state.get_data()
    page_zones = _to_zones(data.get("page_zones"))
    if 0 <= index < len(page_zones):
        return page_zones[index]
    return None


async def set_page_zones(state: FSMContext, zones: list[Zone]) -> None:
    """Cache the zones shown on the current domain-list page (for index lookup)."""
    await state.update_data(page_zones=[[z.id, z.name, z.status] for z in zones])
