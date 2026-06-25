"""Generation batch + batch item repository."""
from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    GenerationBatch,
    utcnow,
)


async def create_batch(
    session: AsyncSession,
    *,
    telegram_user_id: int,
    zone_id: str,
    domain: str,
    requested_count: int,
    status: BatchStatus = BatchStatus.draft,
) -> GenerationBatch:
    batch = GenerationBatch(
        telegram_user_id=telegram_user_id,
        zone_id=zone_id,
        domain=domain,
        requested_count=requested_count,
        status=status.value,
    )
    session.add(batch)
    await session.flush()
    return batch


async def get_batch(session: AsyncSession, batch_id: int) -> Optional[GenerationBatch]:
    result = await session.execute(
        select(GenerationBatch).where(GenerationBatch.id == batch_id)
    )
    return result.scalar_one_or_none()


async def set_batch_status(
    session: AsyncSession, batch: GenerationBatch, status: BatchStatus
) -> None:
    batch.status = status.value
    if status in (
        BatchStatus.completed,
        BatchStatus.partial,
        BatchStatus.failed,
        BatchStatus.cancelled,
        BatchStatus.expired,
    ):
        batch.completed_at = utcnow()
    await session.flush()


async def try_lock_for_processing(
    session: AsyncSession, batch_id: int
) -> Optional[GenerationBatch]:
    """Atomically move a batch into 'processing'. Returns None if it was already
    being processed / finished (double-click protection)."""
    batch = await get_batch(session, batch_id)
    if batch is None:
        return None
    if batch.status in (
        BatchStatus.processing.value,
        BatchStatus.completed.value,
        BatchStatus.cancelled.value,
        BatchStatus.expired.value,
    ):
        return None
    batch.status = BatchStatus.processing.value
    await session.flush()
    return batch


async def replace_items(
    session: AsyncSession, batch: GenerationBatch, emails: Sequence[str]
) -> list[BatchItem]:
    """Replace the batch's items with a fresh set of pending emails."""
    for item in list(batch.items):
        await session.delete(item)
    await session.flush()
    items: list[BatchItem] = []
    for email in emails:
        item = BatchItem(
            batch_id=batch.id,
            full_email=email,
            status=BatchItemStatus.pending.value,
        )
        session.add(item)
        items.append(item)
    await session.flush()
    return items


async def get_items(session: AsyncSession, batch_id: int) -> list[BatchItem]:
    result = await session.execute(
        select(BatchItem).where(BatchItem.batch_id == batch_id).order_by(BatchItem.id)
    )
    return list(result.scalars().all())
