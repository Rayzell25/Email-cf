"""Generated-name repository: global uniqueness + reservation bookkeeping."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import GeneratedName, NameStatus, utcnow


async def get_by_normalized(
    session: AsyncSession, normalized: str
) -> Optional[GeneratedName]:
    result = await session.execute(
        select(GeneratedName).where(GeneratedName.normalized_name == normalized)
    )
    return result.scalar_one_or_none()


async def is_taken(session: AsyncSession, normalized: str, now: datetime | None = None) -> bool:
    """A name is considered taken if it exists and is NOT releasable.

    Releasable means an expired reservation. ``created`` and ``deleted`` names
    are permanently taken (never reused). An active (not yet expired)
    ``reserved`` name is also taken.
    """
    now = now or utcnow()
    row = await get_by_normalized(session, normalized)
    if row is None:
        return False
    if row.status in (NameStatus.created.value, NameStatus.deleted.value, NameStatus.failed.value):
        return True
    if row.status == NameStatus.reserved.value:
        if row.reserved_until is not None and _aware(row.reserved_until) <= now:
            return False  # reservation expired -> free to reuse
        return True
    return False


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        from datetime import timezone

        return dt.replace(tzinfo=timezone.utc)
    return dt


async def reserve(
    session: AsyncSession,
    display_name: str,
    normalized: str,
    token: str,
    reserved_until: datetime,
) -> Optional[GeneratedName]:
    """Reserve a name. Returns the row, or None if it is already taken.

    Relies on the UNIQUE constraint on ``normalized_name`` for concurrency
    safety: if two processes race, only one INSERT succeeds.
    """
    existing = await get_by_normalized(session, normalized)
    if existing is not None:
        if await is_taken(session, normalized):
            return None
        # expired reservation -> repurpose the row
        existing.display_name = display_name
        existing.status = NameStatus.reserved.value
        existing.reservation_token = token
        existing.reserved_until = reserved_until
        existing.deleted_at = None
        await session.flush()
        return existing

    row = GeneratedName(
        display_name=display_name,
        normalized_name=normalized,
        status=NameStatus.reserved.value,
        reservation_token=token,
        reserved_until=reserved_until,
    )
    session.add(row)
    await session.flush()
    return row


async def release_by_token(session: AsyncSession, token: str) -> int:
    """Release (mark expired) all reserved names for a reservation token."""
    result = await session.execute(
        update(GeneratedName)
        .where(
            GeneratedName.reservation_token == token,
            GeneratedName.status == NameStatus.reserved.value,
        )
        .values(status=NameStatus.expired.value, reservation_token=None)
    )
    return result.rowcount or 0


async def set_status(
    session: AsyncSession, normalized: str, status: NameStatus
) -> None:
    values: dict = {"status": status.value}
    if status == NameStatus.deleted:
        values["deleted_at"] = utcnow()
    if status in (NameStatus.created, NameStatus.failed):
        values["reservation_token"] = None
    await session.execute(
        update(GeneratedName)
        .where(GeneratedName.normalized_name == normalized)
        .values(**values)
    )


async def expire_stale(session: AsyncSession, now: datetime | None = None) -> int:
    now = now or utcnow()
    result = await session.execute(
        update(GeneratedName)
        .where(
            GeneratedName.status == NameStatus.reserved.value,
            GeneratedName.reserved_until.is_not(None),
            GeneratedName.reserved_until <= now,
        )
        .values(status=NameStatus.expired.value, reservation_token=None)
    )
    return result.rowcount or 0


async def filter_taken(
    session: AsyncSession, normalized_names: Sequence[str]
) -> set[str]:
    """Return the subset of given normalized names that are already taken."""
    if not normalized_names:
        return set()
    result = await session.execute(
        select(GeneratedName).where(
            GeneratedName.normalized_name.in_(list(normalized_names))
        )
    )
    taken: set[str] = set()
    now = utcnow()
    for row in result.scalars().all():
        if row.status in (
            NameStatus.created.value,
            NameStatus.deleted.value,
            NameStatus.failed.value,
        ):
            taken.add(row.normalized_name)
        elif row.status == NameStatus.reserved.value:
            if row.reserved_until is None or _aware(row.reserved_until) > now:
                taken.add(row.normalized_name)
    return taken
