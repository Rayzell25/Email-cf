"""Generic pagination helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, List, Sequence, TypeVar

T = TypeVar("T")


@dataclass
class Page(Generic[T]):
    items: List[T]
    page: int  # 1-based current page
    total_pages: int
    total_items: int
    page_size: int

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def label(self) -> str:
        return f"{self.page}/{self.total_pages}"


def paginate(items: Sequence[T], page: int, page_size: int) -> Page[T]:
    total_items = len(items)
    if page_size < 1:
        page_size = 1
    total_pages = max(1, (total_items + page_size - 1) // page_size)
    # clamp page into the valid range
    page = max(1, min(page, total_pages))
    start = (page - 1) * page_size
    end = start + page_size
    return Page(
        items=list(items[start:end]),
        page=page,
        total_pages=total_pages,
        total_items=total_items,
        page_size=page_size,
    )
