"""Bulk operation schemas for events and detections APIs.

This module provides schemas for bulk create, update, and delete operations
on events and detections. These schemas support partial success handling
with per-item results using HTTP 207 Multi-Status responses.

See NEM-1433 for implementation details.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BulkOperationStatus(str, Enum):
    """Status of individual items in a bulk operation."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class BulkItemResult(BaseModel):
    """Result for a single item in a bulk operation.

    Attributes:
        index: Zero-based index of the item in the request array
        status: Operation status (success, failed, skipped)
        id: ID of the created/updated resource (for successful operations)
        error: Error message (for failed operations)
    """

    model_config = ConfigDict(from_attributes=True)

    index: int = Field(..., ge=0, description="Zero-based index of the item in the request")
    status: BulkOperationStatus = Field(..., description="Operation status")
    id: int | None = Field(None, description="ID of the created/updated resource")
    error: str | None = Field(None, description="Error message for failed operations")


class BulkOperationResponse(BaseModel):
    """Base response for bulk operations with partial success support.

    Uses HTTP 207 Multi-Status when some operations succeed and others fail.

    Attributes:
        total: Total number of items in the request
        succeeded: Number of successful operations
        failed: Number of failed operations
        skipped: Number of skipped operations
        results: Per-item results with status and error details
    """

    model_config = ConfigDict(from_attributes=True)

    total: int = Field(..., ge=0, description="Total number of items in the request")
    succeeded: int = Field(..., ge=0, description="Number of successful operations")
    failed: int = Field(..., ge=0, description="Number of failed operations")
    skipped: int = Field(0, ge=0, description="Number of skipped operations")
    results: list[BulkItemResult] = Field(default_factory=list, description="Per-item results")


# =============================================================================
# Event Bulk Schemas
# =============================================================================


class EventBulkCreateItem(BaseModel):
    """Schema for a single event in a bulk create request.

    Attributes:
        batch_id: Batch ID that generated this event (tracks detection grouping)
        camera_id: Camera ID that generated this event
        started_at: Event start timestamp
        ended_at: Optional event end timestamp
        risk_score: Risk score from 0-100
        risk_level: Risk level (low, medium, high, critical)
        summary: Brief event summary
        reasoning: Detailed reasoning from LLM analysis
        detection_ids: List of detection IDs associated with this event
    """

    model_config = ConfigDict(from_attributes=True)

    batch_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Batch ID that generated this event",
    )
    camera_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Camera ID",
        pattern=r"^[a-zA-Z0-9_-]+$",
    )
    started_at: datetime = Field(..., description="Event start timestamp")
    ended_at: datetime | None = Field(None, description="Event end timestamp")
    risk_score: int = Field(..., ge=0, le=100, description="Risk score (0-100)")
    risk_level: str = Field(
        ...,
        description="Risk level",
        pattern=r"^(low|medium|high|critical)$",
    )
    summary: str = Field(..., min_length=1, max_length=1000, description="Event summary")
    reasoning: str | None = Field(None, max_length=5000, description="LLM reasoning")
    detection_ids: list[int] = Field(default_factory=list, description="Associated detection IDs")


class EventBulkCreateRequest(BaseModel):
    """Request schema for bulk event creation.

    Attributes:
        events: List of events to create (max 100 per request)
    """

    model_config = ConfigDict(from_attributes=True)

    events: list[EventBulkCreateItem] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Events to create (max 100)",
    )


class EventBulkCreateResponse(BulkOperationResponse):
    """Response schema for bulk event creation.

    Extends BulkOperationResponse with created event IDs.
    """

    pass


class EventBulkUpdateItem(BaseModel):
    """Schema for a single event update in a bulk update request.

    Attributes:
        id: Event ID to update
        reviewed: Mark event as reviewed/dismissed
        notes: Optional notes for the event
    """

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., gt=0, description="Event ID to update")
    reviewed: bool | None = Field(None, description="Mark as reviewed")
    notes: str | None = Field(None, max_length=2000, description="Notes")


class EventBulkUpdateRequest(BaseModel):
    """Request schema for bulk event updates.

    Attributes:
        events: List of event updates (max 100 per request)
    """

    model_config = ConfigDict(from_attributes=True)

    events: list[EventBulkUpdateItem] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Event updates (max 100)",
    )


class EventBulkDeleteRequest(BaseModel):
    """Request schema for bulk event deletion.

    Attributes:
        event_ids: List of event IDs to delete (max 100 per request)
        soft_delete: If true, mark as deleted instead of removing
    """

    model_config = ConfigDict(from_attributes=True)

    event_ids: list[int] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Event IDs to delete (max 100)",
    )
    soft_delete: bool = Field(True, description="Soft delete (default) vs hard delete")


# =============================================================================
# Detection Bulk Schemas
# =============================================================================


class DetectionBulkCreateItem(BaseModel):
    """Schema for a single detection in a bulk create request.

    Attributes:
        camera_id: Camera ID that captured this detection
        object_type: Type of detected object (person, vehicle, etc.)
        confidence: Detection confidence score (0.0-1.0)
        detected_at: Detection timestamp
        file_path: Path to the detection image
        bbox_x: Bounding box X coordinate
        bbox_y: Bounding box Y coordinate
        bbox_width: Bounding box width
        bbox_height: Bounding box height
        enrichment_data: Optional enrichment pipeline results
    """

    model_config = ConfigDict(from_attributes=True)

    camera_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Camera ID",
        pattern=r"^[a-zA-Z0-9_-]+$",
    )
    object_type: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Object type (person, vehicle, etc.)",
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0-1.0)")
    detected_at: datetime = Field(..., description="Detection timestamp")
    file_path: str = Field(..., min_length=1, max_length=1000, description="Image file path")
    bbox_x: int = Field(..., ge=0, description="Bounding box X coordinate")
    bbox_y: int = Field(..., ge=0, description="Bounding box Y coordinate")
    bbox_width: int = Field(..., gt=0, description="Bounding box width")
    bbox_height: int = Field(..., gt=0, description="Bounding box height")
    enrichment_data: dict[str, Any] | None = Field(None, description="Enrichment pipeline results")


class DetectionBulkCreateRequest(BaseModel):
    """Request schema for bulk detection creation.

    Attributes:
        detections: List of detections to create (max 100 per request)
    """

    model_config = ConfigDict(from_attributes=True)

    detections: list[DetectionBulkCreateItem] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Detections to create (max 100)",
    )


class DetectionBulkCreateResponse(BulkOperationResponse):
    """Response schema for bulk detection creation.

    Extends BulkOperationResponse with created detection IDs.
    """

    pass


class DetectionBulkUpdateItem(BaseModel):
    """Schema for a single detection update in a bulk update request.

    Attributes:
        id: Detection ID to update
        object_type: Updated object type
        confidence: Updated confidence score
        enrichment_data: Updated enrichment data
    """

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., gt=0, description="Detection ID to update")
    object_type: str | None = Field(None, min_length=1, max_length=100, description="Object type")
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="Confidence score")
    enrichment_data: dict[str, Any] | None = Field(None, description="Enrichment pipeline results")


class DetectionBulkUpdateRequest(BaseModel):
    """Request schema for bulk detection updates.

    Attributes:
        detections: List of detection updates (max 100 per request)
    """

    model_config = ConfigDict(from_attributes=True)

    detections: list[DetectionBulkUpdateItem] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Detection updates (max 100)",
    )


class DetectionBulkDeleteRequest(BaseModel):
    """Request schema for bulk detection deletion.

    Note: Detection deletion is always hard delete as detections
    are raw data and soft-delete is not supported.

    Attributes:
        detection_ids: List of detection IDs to delete (max 100 per request)
    """

    model_config = ConfigDict(from_attributes=True)

    detection_ids: list[int] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Detection IDs to delete (max 100)",
    )
