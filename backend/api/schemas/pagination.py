"""Standard pagination schemas for API responses.

This module provides standardized pagination types that should be used
by all list endpoints to ensure consistent API response structure.

NEM-2075: Standardize pagination response envelope.
"""

from pydantic import BaseModel, ConfigDict, Field


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
        le=1000,
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
