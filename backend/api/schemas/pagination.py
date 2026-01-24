"""Standard pagination schemas for API responses.

This module provides standardized pagination types that should be used
by all list endpoints to ensure consistent API response structure.

NEM-2075: Standardize pagination response envelope.
NEM-3431: Generic PaginatedResponse[T] for type-safe list endpoints.
"""

from collections.abc import Sequence
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

# Generic type variable for paginated items
T = TypeVar("T")


class PaginationInfo(BaseModel):
    """Pagination metadata for list responses (NEM-2075).

    Standard pagination envelope used by entities and other list endpoints.
    Supports both cursor-based pagination (recommended) and offset pagination.
    """

    total: int = Field(..., ge=0, description="Total count matching filters")
    limit: int = Field(..., ge=1, le=1000, description="Page size (1-1000)")
    offset: int | None = Field(
        None, ge=0, description="Page offset (0-based, for offset pagination)"
    )
    cursor: str | None = Field(None, description="Current cursor position")
    next_cursor: str | None = Field(None, description="Cursor for next page")
    has_more: bool = Field(False, description="Whether more results are available")


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses.

    Contains information about the current page and total results.
    Supports both offset-based and cursor-based pagination.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total": 150,
                "limit": 50,
                "offset": 0,
                "cursor": None,
                "next_cursor": "eyJpZCI6IDUwfQ",  # pragma: allowlist secret
                "has_more": True,
            }
        }
    )

    total: int = Field(
        ...,
        ge=0,
        description="Total number of items matching the query",
    )
    limit: int = Field(
        ...,
        ge=1,
        le=10000,
        description="Maximum number of items returned per page",
    )
    offset: int | None = Field(
        default=None,
        ge=0,
        description="Number of items skipped (offset-based pagination)",
    )
    cursor: str | None = Field(
        default=None,
        description="Current cursor position (cursor-based pagination)",
    )
    next_cursor: str | None = Field(
        default=None,
        description="Cursor for the next page of results",
    )
    has_more: bool = Field(
        ...,
        description="Whether more items are available beyond this page",
    )


def create_pagination_meta(
    *,
    total: int,
    limit: int,
    offset: int | None = None,
    cursor: str | None = None,
    next_cursor: str | None = None,
    items_count: int | None = None,
) -> PaginationMeta:
    """Create pagination metadata with computed has_more field.

    Args:
        total: Total number of items matching the query
        limit: Maximum items per page
        offset: Number of items skipped (for offset pagination)
        cursor: Current cursor position (for cursor pagination)
        next_cursor: Cursor for next page (for cursor pagination)
        items_count: Number of items actually returned (for computing has_more)

    Returns:
        PaginationMeta instance with has_more computed
    """
    # Compute has_more based on available information
    if next_cursor is not None:
        # If there's a next_cursor, there are more items
        has_more = True
    elif items_count is not None:
        # If we returned a full page, there might be more
        has_more = items_count >= limit
    elif offset is not None:
        # Offset-based: check if we've seen all items
        has_more = (offset + limit) < total
    else:
        # Default: assume no more if we can't determine
        has_more = False

    return PaginationMeta(
        total=total,
        limit=limit,
        offset=offset,
        cursor=cursor,
        next_cursor=next_cursor,
        has_more=has_more,
    )


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response model for list endpoints (NEM-3431).

    This generic model provides a type-safe, reusable pagination envelope
    that can be parameterized with any item type.

    Example usage:
        >>> from backend.api.schemas.pagination import PaginatedResponse
        >>> from backend.api.schemas.camera import CameraResponse
        >>>
        >>> # As type annotation
        >>> def list_cameras() -> PaginatedResponse[CameraResponse]:
        >>>     ...
        >>>
        >>> # Creating a response
        >>> response = PaginatedResponse[CameraResponse](
        ...     items=[camera1, camera2],
        ...     total=100,
        ...     page=1,
        ...     page_size=50,
        ... )

    Attributes:
        items: List of items for the current page
        total: Total number of items matching the query
        page: Current page number (1-indexed)
        page_size: Number of items per page
        has_next: Whether there are more pages after this one
        has_prev: Whether there are pages before this one
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [],
                "total": 100,
                "page": 1,
                "page_size": 50,
                "has_next": True,
                "has_prev": False,
            }
        }
    )

    items: Sequence[T] = Field(..., description="List of items for the current page")
    total: int = Field(..., ge=0, description="Total number of items matching the query")
    page: int = Field(..., ge=1, description="Current page number (1-indexed)")
    page_size: int = Field(..., ge=1, le=10000, description="Number of items per page")
    has_next: bool = Field(..., description="Whether there are more pages after this one")
    has_prev: bool = Field(..., description="Whether there are pages before this one")

    @classmethod
    def create(
        cls,
        items: Sequence[T],
        total: int,
        page: int = 1,
        page_size: int = 50,
    ) -> PaginatedResponse[T]:
        """Create a paginated response with computed navigation flags.

        This factory method automatically calculates has_next and has_prev
        based on the total count, current page, and page size.

        Args:
            items: List of items for the current page
            total: Total number of items matching the query
            page: Current page number (1-indexed, default 1)
            page_size: Number of items per page (default 50)

        Returns:
            PaginatedResponse instance with computed navigation flags

        Example:
            >>> cameras = [cam1, cam2, cam3]
            >>> response = PaginatedResponse.create(
            ...     items=cameras,
            ...     total=150,
            ...     page=2,
            ...     page_size=50,
            ... )
            >>> response.has_prev  # True (page 2 has a page 1)
            >>> response.has_next  # True (50*2=100 < 150)
        """
        # Calculate total pages
        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

        # Compute navigation flags
        has_prev = page > 1
        has_next = page < total_pages

        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_next=has_next,
            has_prev=has_prev,
        )


def create_paginated_response(
    items: Sequence[T],
    total: int,
    page: int = 1,
    page_size: int = 50,
) -> PaginatedResponse[T]:
    """Create a paginated response with computed navigation flags (NEM-3431).

    Convenience function for creating PaginatedResponse instances.
    Automatically calculates has_next and has_prev based on pagination parameters.

    Args:
        items: List of items for the current page
        total: Total number of items matching the query
        page: Current page number (1-indexed, default 1)
        page_size: Number of items per page (default 50)

    Returns:
        PaginatedResponse instance with computed navigation flags

    Example:
        >>> from backend.api.schemas.pagination import create_paginated_response
        >>> from backend.api.schemas.camera import CameraResponse
        >>>
        >>> cameras: list[CameraResponse] = await fetch_cameras(page=2, limit=50)
        >>> total_count = await count_cameras()
        >>>
        >>> response = create_paginated_response(
        ...     items=cameras,
        ...     total=total_count,
        ...     page=2,
        ...     page_size=50,
        ... )
    """
    return PaginatedResponse.create(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
