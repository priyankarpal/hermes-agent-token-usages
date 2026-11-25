"""Pagination logic for token usage reports.

Pure functions for splitting lists into pages with metadata.
"""

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class PaginationInfo:
    """Metadata about a paginated result."""

    page: int
    page_size: int
    total_pages: int
    total_items: int
    start_row: int
    end_row: int
    has_next: bool


def paginate(items: list[T], page: int, page_size: int) -> tuple[list[T], PaginationInfo]:
    """Split a list into pages and return the requested page with pagination info.

    Args:
        items: List of items to paginate.
        page: 1-based page number to return.
        page_size: Number of items per page (must be >= 1).

    Returns:
        Tuple of (page_items, pagination_info).

    Raises:
        ValueError: If page < 1, page > total_pages, or page_size < 1.
    """
    if page_size < 1:
        raise ValueError("page_size must be >= 1")

    total_items = len(items)
    total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 0

    if page < 1 or (total_pages > 0 and page > total_pages):
        raise ValueError("page out of range")

    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, total_items)

    page_items = items[start_idx:end_idx]

    start_row = start_idx + 1 if total_items > 0 else 0
    end_row = end_idx if total_items > 0 else 0
    has_next = page < total_pages

    info = PaginationInfo(
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        total_items=total_items,
        start_row=start_row,
        end_row=end_row,
        has_next=has_next,
    )

    return page_items, info