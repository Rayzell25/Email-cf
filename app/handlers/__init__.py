"""Handler routers aggregation."""
from __future__ import annotations

from aiogram import Router


def get_routers() -> list[Router]:
    from app.handlers import (
        create_manual,
        create_random,
        domains,
        email_delete,
        email_list,
        menu,
        start,
    )

    return [
        start.router,
        menu.router,
        domains.router,
        create_random.router,
        create_manual.router,
        email_list.router,
        email_delete.router,
    ]
