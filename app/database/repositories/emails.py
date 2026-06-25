"""Routing-email repository (local mirror of Cloudflare routing rules)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import EmailSource, EmailStatus, RoutingEmail, utcnow


async def get_by_full_email(
    session: AsyncSession, full_email: str
) -> Optional[RoutingEmail]:
    result = await session.execute(
        select(RoutingEmail).where(RoutingEmail.full_email == full_email.lower())
    )
    return result.scalar_one_or_none()


async def exists_active(session: AsyncSession, full_email: str) -> bool:
    row = await get_by_full_email(session, full_email)
    return row is not None and row.status == EmailStatus.active.value


async def record_created(
    session: AsyncSession,
    *,
    zone_id: str,
    domain: str,
    local_part: str,
    normalized_local_part: str,
    full_email: str,
    rule_id: Optional[str],
    destination_email: Optional[str],
    source: EmailSource,
) -> RoutingEmail:
    row = await get_by_full_email(session, full_email)
    if row is None:
        row = RoutingEmail(
            zone_id=zone_id,
            domain=domain,
            local_part=local_part,
            normalized_local_part=normalized_local_part,
            full_email=full_email.lower(),
        )
        session.add(row)
    row.zone_id = zone_id
    row.domain = domain
    row.local_part = local_part
    row.normalized_local_part = normalized_local_part
    row.cloudflare_rule_id = rule_id
    row.destination_email = destination_email
    row.source = source.value
    row.status = EmailStatus.active.value
    row.deleted_at = None
    await session.flush()
    return row


async def record_deleted(session: AsyncSession, full_email: str) -> None:
    row = await get_by_full_email(session, full_email)
    if row is not None:
        row.status = EmailStatus.deleted.value
        row.deleted_at = utcnow()
        await session.flush()


async def get_for_rule(
    session: AsyncSession, zone_id: str, rule_id: str
) -> Optional[RoutingEmail]:
    result = await session.execute(
        select(RoutingEmail).where(
            RoutingEmail.zone_id == zone_id,
            RoutingEmail.cloudflare_rule_id == rule_id,
        )
    )
    return result.scalar_one_or_none()


async def count_active(session: AsyncSession) -> int:
    from sqlalchemy import func

    result = await session.execute(
        select(func.count())
        .select_from(RoutingEmail)
        .where(RoutingEmail.status == EmailStatus.active.value)
    )
    return int(result.scalar() or 0)


async def get_active_for_zone(
    session: AsyncSession, zone_id: str
) -> list[RoutingEmail]:
    result = await session.execute(
        select(RoutingEmail).where(
            RoutingEmail.zone_id == zone_id,
            RoutingEmail.status == EmailStatus.active.value,
        )
    )
    return list(result.scalars().all())
