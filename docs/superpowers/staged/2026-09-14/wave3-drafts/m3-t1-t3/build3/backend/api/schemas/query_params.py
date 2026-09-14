"""Reusable query parameter models for API routes.

This module provides Pydantic models for common query parameters that can be
used with FastAPI's Depends() for consistent validation across endpoints.

NEM-3345: Implement Query Parameter Models for reusable validation.

Usage:
    from backend.api.schemas.query_params import (
        PaginationParams,
        DateRangeParams,
        FilterParams,
        SortParams,
        CommonQueryParams,
    )

    @router.get("/events")
    async def list_events(
        pagination: PaginationParams = Depends(),
        date_range: DateRangeParams = Depends(),
        filters: FilterParams = Depends(),
        sort: SortParams = Depends(),
        db: AsyncSession = Depends(get_db),
    ) -> EventListResponse:
        # Use pagination.limit, pagination.offset, pagination.cursor
        # Use date_range.start_date, date_range.end_date
        # Use filters.camera_id, filters.detection_type, filters.risk_level
        # Use sort.sort_by, sort.sort_order
        ...
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Any

from fastapi import HTTPException, Query, status
from pydantic import BaseModel, model_validator


class SortOrder(str, Enum):
    """Sort order enumeration."""

    ASC = "asc"
    DESC = "desc"


class RiskLevel(str, Enum):
    """Risk level enumeration for event filtering."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PaginationParams(BaseModel):
    """Pagination query parameters.

    Supports both cursor-based (recommended) and offset-based (deprecated) pagination.
    Cursor-based pagination offers better performance for large datasets.

    Attributes:
        limit: Maximum number of results to return (1-1000, default 50)
        offset: Number of results to skip (deprecated, use cursor instead)
        cursor: Pagination cursor from previous response's next_cursor field

    Example:
        @router.get("/items")
        async def list_items(pagination: PaginationParams = Depends()):
            query = query.limit(pagination.limit)
            if pagination.cursor:
                cursor_data = decode_cursor(pagination.cursor)
                query = query.where(Item.id < cursor_data.id)
            elif pagination.offset:
                query = query.offset(pagination.offset)
    """

    limit: Annotated[
        int,
        Query(
            default=50,
            ge=1,
            le=1000,
            description="Maximum number of results to return (1-1000, default 50)",
        ),
    ]
    offset: Annotated[
        int,
        Query(
            default=0,
            ge=0,
            description="Number of results to skip (deprecated, use cursor instead)",
        ),
    ]
    cursor: Annotated[
        str | None,
        Query(
            default=None,
            description="Pagination cursor from previous response's next_cursor field",
        ),
    ]

    model_config = {"frozen": True}

    @model_validator(mode="after")
    def validate_pagination_method(self) -> PaginationParams:
        """Validate that cursor and non-zero offset are not used together."""
        if self.cursor is not None and self.offset > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot use both 'offset' and 'cursor' pagination. Choose one.",
            )
        return self

    @property
    def is_cursor_based(self) -> bool:
        """Check if cursor-based pagination is being used."""
        return self.cursor is not None

    @property
    def is_offset_deprecated(self) -> bool:
        """Check if deprecated offset pagination is being used."""
        return self.cursor is None and self.offset > 0

    def get_deprecation_warning(self) -> str | None:
        """Get deprecation warning if using offset without cursor."""
        if self.is_offset_deprecated:
            return (
                "Offset pagination is deprecated and will be removed in a future version. "
                "Please use cursor-based pagination instead by using the 'cursor' parameter "
                "with the 'next_cursor' value from the response."
            )
        return None


class DateRangeParams(BaseModel):
    """Date range query parameters.

    Provides consistent date filtering across endpoints with validation
    to ensure start_date is before end_date.

    Attributes:
        start_date: Filter results from this date/time (inclusive)
        end_date: Filter results until this date/time (inclusive)

    Example:
        @router.get("/events")
        async def list_events(date_range: DateRangeParams = Depends()):
            if date_range.start_date:
                query = query.where(Event.started_at >= date_range.start_date)
            if date_range.end_date:
                query = query.where(Event.started_at <= date_range.end_date)
    """

    start_date: Annotated[
        datetime | None,
        Query(
            default=None,
            description="Filter results from this date/time (inclusive, ISO 8601 format)",
        ),
    ]
    end_date: Annotated[
        datetime | None,
        Query(
            default=None,
            description="Filter results until this date/time (inclusive, ISO 8601 format)",
        ),
    ]

    model_config = {"frozen": True}

    @model_validator(mode="after")
    def validate_date_range(self) -> DateRangeParams:
        """Validate that start_date is before end_date."""
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.start_date > self.end_date
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_date must be before or equal to end_date",
            )
        return self

    def get_normalized_end_date(self) -> datetime | None:
        """Get end_date normalized to end of day if at midnight.

        This ensures date-only filters like "2026-01-15" include all
        results from that day.

        Returns:
            Normalized end_date or None if not set
        """
        if self.end_date is None:
            return None

        # If the end_date is at exactly midnight (00:00:00), extend to end of day
        if (
            self.end_date.hour == 0
            and self.end_date.minute == 0
            and self.end_date.second == 0
            and self.end_date.microsecond == 0
        ):
            return self.end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        return self.end_date


class FilterParams(BaseModel):
    """Common filter query parameters for detections and events.

    Provides reusable filter parameters for the most common filtering needs
    across detection and event endpoints.

    Attributes:
        camera_id: Filter by camera ID
        detection_type: Filter by object detection type (person, car, etc.)
        object_type: Alias for detection_type (for backward compatibility)
        risk_level: Filter by risk level (low, medium, high, critical)
        min_confidence: Minimum confidence score (0.0-1.0)
        reviewed: Filter by reviewed status (True/False)

    Example:
        @router.get("/detections")
        async def list_detections(filters: FilterParams = Depends()):
            if filters.camera_id:
                query = query.where(Detection.camera_id == filters.camera_id)
            if filters.object_type:
                query = query.where(Detection.object_type == filters.object_type)
    """

    camera_id: Annotated[
        str | None,
        Query(default=None, description="Filter by camera ID"),
    ]
    detection_type: Annotated[
        str | None,
        Query(
            default=None,
            alias="object_type",
            description="Filter by object type (person, car, etc.)",
        ),
    ]
    risk_level: Annotated[
        RiskLevel | None,
        Query(default=None, description="Filter by risk level (low, medium, high, critical)"),
    ]
    min_confidence: Annotated[
        float | None,
        Query(default=None, ge=0.0, le=1.0, description="Minimum confidence score (0.0-1.0)"),
    ]
    reviewed: Annotated[
        bool | None,
        Query(default=None, description="Filter by reviewed status"),
    ]

    model_config = {"frozen": True, "populate_by_name": True}

    @property
    def object_type(self) -> str | None:
        """Alias for detection_type for backward compatibility."""
        return self.detection_type


class SortParams(BaseModel):
    """Sort query parameters.

    Provides consistent sorting across endpoints with configurable
    sort field and order.

    Attributes:
        sort_by: Field to sort by (varies by endpoint)
        sort_order: Sort order (asc or desc, default desc)

    Example:
        @router.get("/events")
        async def list_events(sort: SortParams = Depends()):
            order_func = desc if sort.sort_order == SortOrder.DESC else asc
            if sort.sort_by == "started_at":
                query = query.order_by(order_func(Event.started_at))
    """

    sort_by: Annotated[
        str | None,
        Query(default=None, description="Field to sort by (endpoint-specific)"),
    ]
    sort_order: Annotated[
        SortOrder,
        Query(default=SortOrder.DESC, description="Sort order (asc or desc)"),
    ]

    model_config = {"frozen": True}

    def get_order_function(self) -> Any:
        """Get SQLAlchemy order function based on sort_order.

        Returns:
            sqlalchemy.desc or sqlalchemy.asc function
        """
        from sqlalchemy import asc, desc

        return desc if self.sort_order == SortOrder.DESC else asc


class FieldSelectionParams(BaseModel):
    """Sparse fieldsets query parameters.

    Enables clients to request only specific fields in the response,
    reducing payload size for large responses.

    NEM-1434: Sparse fieldsets support.

    Attributes:
        fields: Comma-separated list of fields to include in response

    Example:
        @router.get("/cameras")
        async def list_cameras(field_selection: FieldSelectionParams = Depends()):
            requested_fields = field_selection.parse_fields()
            # Validate against allowed fields for this endpoint
            valid_fields = validate_fields(requested_fields, VALID_CAMERA_FIELDS)
    """

    fields: Annotated[
        str | None,
        Query(
            default=None,
            description="Comma-separated list of fields to include in response (sparse fieldsets)",
        ),
    ]

    model_config = {"frozen": True}

    def parse_fields(self) -> set[str] | None:
        """Parse the fields parameter into a set of field names.

        Returns:
            Set of field names, or None if no fields specified
        """
        if not self.fields:
            return None
        return {f.strip() for f in self.fields.split(",") if f.strip()}


class CommonQueryParams(BaseModel):
    """Combined common query parameters for convenience.

    Groups all common query parameters into a single dependency for
    endpoints that need pagination, date range, filters, and sorting.

    Example:
        @router.get("/events")
        async def list_events(params: CommonQueryParams = Depends()):
            # Access all parameters through a single object
            # params.pagination.limit
            # params.date_range.start_date
            # params.filters.camera_id
            # params.sort.sort_order
    """

    # Pagination params
    limit: Annotated[int, Query(default=50, ge=1, le=1000)]
    offset: Annotated[int, Query(default=0, ge=0)]
    cursor: Annotated[str | None, Query(default=None)]

    # Date range params
    start_date: Annotated[datetime | None, Query(default=None)]
    end_date: Annotated[datetime | None, Query(default=None)]

    # Filter params
    camera_id: Annotated[str | None, Query(default=None)]
    object_type: Annotated[str | None, Query(default=None)]
    risk_level: Annotated[RiskLevel | None, Query(default=None)]
    min_confidence: Annotated[float | None, Query(default=None, ge=0.0, le=1.0)]
    reviewed: Annotated[bool | None, Query(default=None)]

    # Sort params
    sort_by: Annotated[str | None, Query(default=None)]
    sort_order: Annotated[SortOrder, Query(default=SortOrder.DESC)]

    # Field selection
    fields: Annotated[str | None, Query(default=None)]

    model_config = {"frozen": True}

    @model_validator(mode="after")
    def validate_params(self) -> CommonQueryParams:
        """Validate combined parameters."""
        # Validate pagination
        if self.cursor is not None and self.offset > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot use both 'offset' and 'cursor' pagination. Choose one.",
            )
        # Validate date range
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.start_date > self.end_date
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_date must be before or equal to end_date",
            )
        return self

    @property
    def pagination(self) -> PaginationParams:
        """Get pagination parameters as a PaginationParams object."""
        return PaginationParams(
            limit=self.limit,
            offset=self.offset,
            cursor=self.cursor,
        )

    @property
    def date_range(self) -> DateRangeParams:
        """Get date range parameters as a DateRangeParams object."""
        return DateRangeParams(
            start_date=self.start_date,
            end_date=self.end_date,
        )

    @property
    def filters(self) -> FilterParams:
        """Get filter parameters as a FilterParams object."""
        return FilterParams(
            camera_id=self.camera_id,
            detection_type=self.object_type,
            risk_level=self.risk_level,
            min_confidence=self.min_confidence,
            reviewed=self.reviewed,
        )

    @property
    def sort(self) -> SortParams:
        """Get sort parameters as a SortParams object."""
        return SortParams(
            sort_by=self.sort_by,
            sort_order=self.sort_order,
        )

    @property
    def field_selection(self) -> FieldSelectionParams:
        """Get field selection parameters as a FieldSelectionParams object."""
        return FieldSelectionParams(fields=self.fields)


# Type aliases for use with Annotated in route definitions
PaginationParamsDep = Annotated[PaginationParams, Query()]
DateRangeParamsDep = Annotated[DateRangeParams, Query()]
FilterParamsDep = Annotated[FilterParams, Query()]
SortParamsDep = Annotated[SortParams, Query()]
