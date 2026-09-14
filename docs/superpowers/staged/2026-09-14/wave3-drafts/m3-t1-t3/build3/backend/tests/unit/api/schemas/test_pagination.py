"""Tests for pagination schemas (NEM-3431)."""

from pydantic import BaseModel

from backend.api.schemas.pagination import (
    PaginatedResponse,
    PaginationInfo,
    PaginationMeta,
    create_paginated_response,
    create_pagination_meta,
)


class SampleItem(BaseModel):
    """Sample item for testing generic pagination."""

    id: int
    name: str


class TestPaginationInfo:
    """Tests for PaginationInfo schema."""

    def test_create_pagination_info(self):
        """Test creating a PaginationInfo instance."""
        info = PaginationInfo(
            total=100,
            limit=50,
            offset=0,
            has_more=True,
        )
        assert info.total == 100
        assert info.limit == 50
        assert info.offset == 0
        assert info.has_more is True

    def test_pagination_info_with_cursor(self):
        """Test PaginationInfo with cursor-based pagination."""
        info = PaginationInfo(
            total=100,
            limit=50,
            cursor="abc123",
            next_cursor="def456",
            has_more=True,
        )
        assert info.cursor == "abc123"
        assert info.next_cursor == "def456"


class TestPaginationMeta:
    """Tests for PaginationMeta schema."""

    def test_create_pagination_meta(self):
        """Test creating a PaginationMeta instance."""
        meta = PaginationMeta(
            total=150,
            limit=50,
            offset=0,
            has_more=True,
        )
        assert meta.total == 150
        assert meta.limit == 50
        assert meta.offset == 0
        assert meta.has_more is True


class TestCreatePaginationMeta:
    """Tests for create_pagination_meta helper function."""

    def test_has_more_with_next_cursor(self):
        """Test has_more is True when next_cursor is provided."""
        meta = create_pagination_meta(
            total=100,
            limit=50,
            next_cursor="cursor123",
        )
        assert meta.has_more is True

    def test_has_more_with_items_count_full_page(self):
        """Test has_more is True when full page of items returned."""
        meta = create_pagination_meta(
            total=100,
            limit=50,
            items_count=50,
        )
        assert meta.has_more is True

    def test_has_more_with_items_count_partial_page(self):
        """Test has_more is False when partial page of items returned."""
        meta = create_pagination_meta(
            total=100,
            limit=50,
            items_count=25,
        )
        assert meta.has_more is False

    def test_has_more_with_offset_more_items(self):
        """Test has_more is True when offset + limit < total."""
        meta = create_pagination_meta(
            total=100,
            limit=50,
            offset=0,
        )
        assert meta.has_more is True

    def test_has_more_with_offset_no_more_items(self):
        """Test has_more is False when offset + limit >= total."""
        meta = create_pagination_meta(
            total=100,
            limit=50,
            offset=50,
        )
        assert meta.has_more is False


class TestPaginatedResponse:
    """Tests for generic PaginatedResponse[T] model (NEM-3431)."""

    def test_create_paginated_response_first_page(self):
        """Test creating a paginated response for the first page."""
        items = [SampleItem(id=1, name="Item 1"), SampleItem(id=2, name="Item 2")]
        response = PaginatedResponse.create(
            items=items,
            total=100,
            page=1,
            page_size=50,
        )

        assert len(response.items) == 2
        assert response.total == 100
        assert response.page == 1
        assert response.page_size == 50
        assert response.has_prev is False
        assert response.has_next is True

    def test_create_paginated_response_middle_page(self):
        """Test creating a paginated response for a middle page."""
        items = [SampleItem(id=51, name="Item 51")]
        response = PaginatedResponse.create(
            items=items,
            total=150,
            page=2,
            page_size=50,
        )

        assert response.page == 2
        assert response.has_prev is True
        assert response.has_next is True

    def test_create_paginated_response_last_page(self):
        """Test creating a paginated response for the last page."""
        items = [SampleItem(id=91, name="Item 91")]
        response = PaginatedResponse.create(
            items=items,
            total=100,
            page=2,
            page_size=50,
        )

        assert response.page == 2
        assert response.has_prev is True
        assert response.has_next is False

    def test_create_paginated_response_single_page(self):
        """Test creating a paginated response when all items fit on one page."""
        items = [SampleItem(id=1, name="Item 1")]
        response = PaginatedResponse.create(
            items=items,
            total=1,
            page=1,
            page_size=50,
        )

        assert response.has_prev is False
        assert response.has_next is False

    def test_create_paginated_response_empty(self):
        """Test creating a paginated response with no items."""
        response = PaginatedResponse[SampleItem].create(
            items=[],
            total=0,
            page=1,
            page_size=50,
        )

        assert len(response.items) == 0
        assert response.total == 0
        assert response.has_prev is False
        assert response.has_next is False

    def test_create_paginated_response_helper_function(self):
        """Test the create_paginated_response helper function."""
        items = [SampleItem(id=1, name="Item 1")]
        response = create_paginated_response(
            items=items,
            total=100,
            page=1,
            page_size=50,
        )

        assert len(response.items) == 1
        assert response.total == 100
        assert response.page == 1
        assert response.page_size == 50

    def test_paginated_response_serialization(self):
        """Test that PaginatedResponse serializes correctly."""
        items = [SampleItem(id=1, name="Item 1")]
        response = PaginatedResponse.create(
            items=items,
            total=100,
            page=1,
            page_size=50,
        )

        data = response.model_dump()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "has_next" in data
        assert "has_prev" in data

    def test_paginated_response_json_schema(self):
        """Test that PaginatedResponse generates correct JSON schema."""
        schema = PaginatedResponse[SampleItem].model_json_schema()
        assert "properties" in schema
        assert "items" in schema["properties"]
        assert "total" in schema["properties"]
        assert "page" in schema["properties"]
        assert "page_size" in schema["properties"]
        assert "has_next" in schema["properties"]
        assert "has_prev" in schema["properties"]

    def test_paginated_response_exact_page_boundary(self):
        """Test pagination when total is exactly divisible by page_size."""
        items = [SampleItem(id=1, name="Item 1")]
        # 100 total, page_size 50 = 2 pages exactly
        response = PaginatedResponse.create(
            items=items,
            total=100,
            page=2,
            page_size=50,
        )

        assert response.has_prev is True
        assert response.has_next is False  # Page 2 is the last page
