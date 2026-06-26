"""Email service: the safe create / delete orchestration around Cloudflare.

Implements the PRD re-check-before-create rules and timeout verification so a
create or delete is never silently duplicated.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.models import EmailSource, NameStatus
from app.database.repositories import audit as audit_repo
from app.database.repositories import emails as emails_repo
from app.database.repositories import names as names_repo
from app.services.cloudflare import (
    CloudflareClient,
    CloudflareError,
    CloudflareUnknownResult,
)
from app.utils.logger import get_logger
from app.utils.validators import normalize_name

logger = get_logger(__name__)


@dataclass
class CreateResult:
    ok: bool
    full_email: str
    rule_id: Optional[str] = None
    error: Optional[str] = None


@dataclass
class DeleteResult:
    ok: bool
    full_email: str
    error: Optional[str] = None


async def create_one(
    session: AsyncSession,
    cf: CloudflareClient,
    *,
    zone_id: str,
    domain: str,
    full_email: str,
    source: EmailSource,
    owner_id: Optional[int] = None,
) -> CreateResult:
    """Create one routing rule with full pre-checks. Idempotent on retry."""
    settings = get_settings()
    full_email = full_email.lower()
    local_part = full_email.split("@", 1)[0]
    normalized = normalize_name(local_part)
    destination = settings.default_destination_email

    if not destination:
        return CreateResult(False, full_email, error="Destination email is not set.")

    # --- re-check: already exists locally? ---
    if await emails_repo.exists_active(session, full_email):
        return CreateResult(False, full_email, error="Address already in use.")

    # --- re-check: already exists on Cloudflare? ---
    try:
        existing = await cf.find_rule_by_email(zone_id, full_email)
    except CloudflareError as exc:
        return CreateResult(False, full_email, error=exc.user_message)
    if existing is not None:
        # mirror into DB so future checks are correct, but report as collision
        await emails_repo.record_created(
            session,
            zone_id=zone_id,
            domain=domain,
            local_part=local_part,
            normalized_local_part=normalized,
            full_email=full_email,
            rule_id=existing.id,
            destination_email=existing.destination,
            source=EmailSource.external,
        )
        await session.commit()
        return CreateResult(False, full_email, error="Address already in use.")

    # --- create ---
    try:
        rule = await cf.create_routing_rule(zone_id, full_email, destination)
        rule_id = rule.id
    except CloudflareUnknownResult:
        # status unknown -> verify before deciding (avoid duplicate create)
        verified = await _verify_created(cf, zone_id, full_email)
        if verified is None:
            await _safe_mark_failed(session, normalized)
            await session.commit()
            return CreateResult(
                False, full_email, error="Status unknown, please try again."
            )
        rule_id = verified.id
    except CloudflareError as exc:
        await _safe_mark_failed(session, normalized)
        await session.commit()
        return CreateResult(False, full_email, error=exc.user_message)

    # --- persist success ---
    await emails_repo.record_created(
        session,
        zone_id=zone_id,
        domain=domain,
        local_part=local_part,
        normalized_local_part=normalized,
        full_email=full_email,
        rule_id=rule_id,
        destination_email=destination,
        source=source,
    )
    if normalized:
        await names_repo.set_status(session, normalized, NameStatus.created)
    await audit_repo.log(
        session,
        telegram_user_id=owner_id,
        action="create_email",
        target=full_email,
        status="ok",
    )
    await session.commit()
    return CreateResult(True, full_email, rule_id=rule_id)


async def _verify_created(cf: CloudflareClient, zone_id: str, full_email: str):
    try:
        return await cf.find_rule_by_email(zone_id, full_email)
    except CloudflareError:
        return None


async def _safe_mark_failed(session: AsyncSession, normalized: str) -> None:
    if normalized:
        try:
            await names_repo.set_status(session, normalized, NameStatus.failed)
        except Exception:  # pragma: no cover - best effort
            logger.warning("could not mark name failed: %s", normalized)


async def delete_one(
    session: AsyncSession,
    cf: CloudflareClient,
    *,
    zone_id: str,
    rule_id: str,
    full_email: str,
    owner_id: Optional[int] = None,
) -> DeleteResult:
    full_email = full_email.lower()
    normalized = normalize_name(full_email.split("@", 1)[0])

    try:
        await cf.delete_routing_rule(zone_id, rule_id)
    except CloudflareUnknownResult:
        # verify it is actually gone
        try:
            still = await cf.find_rule_by_email(zone_id, full_email)
        except CloudflareError as exc:
            return DeleteResult(False, full_email, error=exc.user_message)
        if still is not None:
            return DeleteResult(
                False, full_email, error="Status unknown, please try again."
            )
    except CloudflareError as exc:
        # maybe it was already deleted (e.g. double click) -> verify
        try:
            still = await cf.find_rule_by_email(zone_id, full_email)
        except CloudflareError:
            return DeleteResult(False, full_email, error=exc.user_message)
        if still is not None:
            return DeleteResult(False, full_email, error=exc.user_message)
        # already gone -> treat as success

    await emails_repo.record_deleted(session, full_email)
    # the random name stays permanently reserved (deleted) and never reused
    if normalized:
        existing = await names_repo.get_by_normalized(session, normalized)
        if existing is not None:
            await names_repo.set_status(session, normalized, NameStatus.deleted)
    await audit_repo.log(
        session,
        telegram_user_id=owner_id,
        action="delete_email",
        target=full_email,
        status="ok",
    )
    await session.commit()
    return DeleteResult(True, full_email)
