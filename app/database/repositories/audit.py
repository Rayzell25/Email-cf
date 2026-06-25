"""Audit log repository. Never stores secrets/tokens."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import AuditLog


async def log(
    session: AsyncSession,
    *,
    telegram_user_id: Optional[int],
    action: str,
    target: Optional[str] = None,
    status: Optional[str] = None,
    details: Optional[str] = None,
) -> None:
    session.add(
        AuditLog(
            telegram_user_id=telegram_user_id,
            action=action,
            target=target,
            status=status,
            details=details,
        )
    )
    await session.flush()
