"""Reservation service: generate unique random names and reserve them.

Uniqueness is enforced against ALL of:
  1. duplicates inside the current batch,
  2. the generated_names history table (global, case-insensitive),
  3. existing routing_emails in the local DB,
  4. live Cloudflare routing rules for the target domain,
  5. names currently reserved by another in-flight process.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.models import NameStatus, utcnow
from app.database.repositories import emails as emails_repo
from app.database.repositories import names as names_repo
from app.services import name_generator
from app.services.cloudflare import CloudflareClient, CloudflareError
from app.utils.logger import get_logger
from app.utils.validators import normalize_name

logger = get_logger(__name__)


@dataclass
class ReservedName:
    display_name: str
    normalized: str
    local_part: str
    full_email: str
    generated_name_id: int


def new_token() -> str:
    return secrets.token_hex(8)


async def _cloudflare_local_parts(
    cf: CloudflareClient, zone_id: str, domain: str
) -> set[str]:
    """Normalized local-parts already present on Cloudflare for this domain."""
    taken: set[str] = set()
    try:
        rules = await cf.list_routing_rules(zone_id)
    except CloudflareError:
        # If we cannot read Cloudflare we proceed with DB-only checks; the
        # final pre-create re-check will catch any collision.
        return taken
    suffix = "@" + domain.lower()
    for rule in rules:
        if rule.email.endswith(suffix):
            local = rule.email[: -len(suffix)]
            taken.add(normalize_name(local))
    return taken


async def generate_and_reserve(
    session: AsyncSession,
    cf: CloudflareClient,
    *,
    zone_id: str,
    domain: str,
    count: int,
    token: str,
) -> List[ReservedName]:
    """Generate ``count`` unique names and reserve them under ``token``."""
    settings = get_settings()
    reserved_until = utcnow() + timedelta(minutes=settings.name_reservation_minutes)
    max_attempts = max(settings.max_generation_attempts, count * 20)

    cf_locals = await _cloudflare_local_parts(cf, zone_id, domain)

    reserved: List[ReservedName] = []
    used_norms: set[str] = set()
    attempts = 0

    while len(reserved) < count and attempts < max_attempts:
        attempts += 1
        display = name_generator.generate_one()
        normalized = normalize_name(display)
        if not normalized or len(normalized) < 4:
            continue
        if normalized in used_norms or normalized in cf_locals:
            continue

        full_email = f"{normalized}@{domain.lower()}"

        # DB history + existing email checks
        if await names_repo.is_taken(session, normalized):
            continue
        if await emails_repo.exists_active(session, full_email):
            continue

        # reserve (relies on UNIQUE constraint for concurrency safety)
        row = await names_repo.reserve(
            session,
            display_name=display,
            normalized=normalized,
            token=token,
            reserved_until=reserved_until,
        )
        if row is None:
            continue  # lost a race; try another name

        used_norms.add(normalized)
        reserved.append(
            ReservedName(
                display_name=display,
                normalized=normalized,
                local_part=normalized,
                full_email=full_email,
                generated_name_id=row.id,
            )
        )

    await session.commit()
    return reserved


async def release(session: AsyncSession, token: str) -> None:
    await names_repo.release_by_token(session, token)
    await session.commit()


async def reserve_specific(
    session: AsyncSession,
    *,
    display_name: str,
    domain: str,
    token: str,
) -> Optional[ReservedName]:
    """Reserve one specific (manual) name. Returns None if it is already taken."""
    settings = get_settings()
    reserved_until = utcnow() + timedelta(minutes=settings.name_reservation_minutes)
    normalized = normalize_name(display_name)
    if not normalized:
        return None
    row = await names_repo.reserve(
        session,
        display_name=display_name,
        normalized=normalized,
        token=token,
        reserved_until=reserved_until,
    )
    if row is None:
        return None
    await session.commit()
    return ReservedName(
        display_name=display_name,
        normalized=normalized,
        local_part=normalized,
        full_email=f"{normalized}@{domain.lower()}",
        generated_name_id=row.id,
    )


async def mark_created(session: AsyncSession, normalized: str) -> None:
    await names_repo.set_status(session, normalized, NameStatus.created)


async def mark_failed(session: AsyncSession, normalized: str) -> None:
    await names_repo.set_status(session, normalized, NameStatus.failed)
