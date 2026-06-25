"""Dashboard message repository (single active dashboard per user)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import DashboardMessage


async def get(session: AsyncSession, telegram_user_id: int) -> Optional[DashboardMessage]:
    result = await session.execute(
        select(DashboardMessage).where(
            DashboardMessage.telegram_user_id == telegram_user_id
        )
    )
    return result.scalar_one_or_none()


async def upsert(
    session: AsyncSession, telegram_user_id: int, chat_id: int, message_id: int
) -> DashboardMessage:
    """Create or replace the single dashboard record for a user."""
    dash = await get(session, telegram_user_id)
    if dash is None:
        dash = DashboardMessage(
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            message_id=message_id,
        )
        session.add(dash)
    else:
        dash.chat_id = chat_id
        dash.message_id = message_id
    await session.flush()
    return dash
