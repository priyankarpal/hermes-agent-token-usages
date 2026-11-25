"""Tests for pagination logic."""

import pytest
from token_usage.paging import paginate, PaginationInfo


class TestPaginate:
    """Tests for the paginate function."""

    def test_empty_list(self) -> None:
        """Empty list returns empty page and correct pagination info."""
        items: list[int] = []
        page_items, info = paginate(items, page=1, page_size=10)

        assert page_items == []
        assert info.page == 1
        assert info.page_size == 10
        assert info.total_pages == 0
        assert info.total_items == 0
        assert info.start_row == 0
        assert info.end_row == 0
        assert info.has_next is False

    def test_exact_multiple(self) -> None:
        """List with exact multiple of page size."""
        items = list(range(20))  # 20 items
        page_items, info = paginate(items, page=1, page_size=10)

        assert page_items == list(range(10))
        assert info.page == 1
        assert info.page_size == 10
        assert info.total_pages == 2
        assert info.total_items == 20
        assert info.start_row == 1
        assert info.end_row == 10
        assert info.has_next is True

        # Page 2
        page_items, info = paginate(items, page=2, page_size=10)
        assert page_items == list(range(10, 20))
        assert info.page == 2
        assert info.start_row == 11
        assert info.end_row == 20
        assert info.has_next is False

    def test_partial_last_page(self) -> None:
        """Last page has fewer items than page size."""
        items = list(range(25))  # 25 items, page_size=10 -> 3 pages
        page_items, info = paginate(items, page=3, page_size=10)

        assert page_items == list(range(20, 25))
        assert info.page == 3
        assert info.page_size == 10
        assert info.total_pages == 3
        assert info.total_items == 25
        assert info.start_row == 21
        assert info.end_row == 25
        assert info.has_next is False

    def test_out_of_range_page_raises(self) -> None:
        """Page number > total_pages raises ValueError."""
        items = list(range(5))

        with pytest.raises(ValueError, match="page out of range"):
            paginate(items, page=2, page_size=10)

        with pytest.raises(ValueError, match="page out of range"):
            paginate(items, page=0, page_size=10)

        with pytest.raises(ValueError, match="page out of range"):
            paginate(items, page=-1, page_size=10)

    def test_invalid_page_size_raises(self) -> None:
        """Page size < 1 raises ValueError."""
        items = list(range(5))

        with pytest.raises(ValueError, match="page_size must be >= 1"):
            paginate(items, page=1, page_size=0)

        with pytest.raises(ValueError, match="page_size must be >= 1"):
            paginate(items, page=1, page_size=-1)

    def test_page_size_one(self) -> None:
        """Page size of 1 works correctly."""
        items = list(range(3))
        page_items, info = paginate(items, page=2, page_size=1)

        assert page_items == [1]
        assert info.total_pages == 3
        assert info.start_row == 2
        assert info.end_row == 2

    def test_large_page_size(self) -> None:
        """Page size larger than list returns all items on page 1."""
        items = list(range(5))
        page_items, info = paginate(items, page=1, page_size=100)

        assert page_items == list(range(5))
        assert info.total_pages == 1
        assert info.start_row == 1
        assert info.end_row == 5
        assert info.has_next is False


class TestPaginationInfo:
    """Tests for PaginationInfo dataclass."""

    def test_pagination_info_fields(self) -> None:
        """PaginationInfo has all required fields."""
        info = PaginationInfo(
            page=1,
            page_size=10,
            total_pages=3,
            total_items=25,
            start_row=1,
            end_row=10,
            has_next=True,
        )
        assert info.page == 1
        assert info.page_size == 10
        assert info.total_pages == 3
        assert info.total_items == 25
        assert info.start_row == 1
        assert info.end_row == 10
        assert info.has_next is True