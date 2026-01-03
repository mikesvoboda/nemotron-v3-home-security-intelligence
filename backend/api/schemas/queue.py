"""Pydantic schemas for queue message payload validation.

Security: These schemas validate all data entering the processing queues
to prevent malicious payloads from being processed by the AI pipeline.

This provides defense-in-depth against:
- Path traversal attacks via file_path
- Invalid camera_id injection
- Malformed batch data
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DetectionQueuePayload(BaseModel):
    """Validated payload for items in the detection queue.

    Security: All fields are validated to ensure:
    - camera_id contains only safe characters
    - file_path is an absolute path (not relative)
    - media_type is a known type
    - timestamp is valid ISO format
    """

    camera_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Camera identifier (alphanumeric, underscores, hyphens only)",
    )
    file_path: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="Absolute path to the media file",
    )
    timestamp: str = Field(
        ...,
        description="ISO format timestamp of when the file was detected",
    )
    media_type: Literal["image", "video"] = Field(
        default="image",
        description="Type of media file",
    )
    file_hash: str | None = Field(
        default=None,
        max_length=128,
        pattern=r"^[a-fA-F0-9]+$",
        description="Optional SHA256 hash of the file (hex encoded)",
    )
    pipeline_start_time: str | None = Field(
        default=None,
        description="ISO format timestamp of when the file was first detected (for total pipeline latency tracking)",
    )

    model_config = ConfigDict(
        extra="ignore",  # Ignore unexpected fields for forward compatibility
        json_schema_extra={
            "example": {
                "camera_id": "front_door",
                "file_path": "/export/foscam/front_door/image_001.jpg",
                "timestamp": "2025-12-23T10:30:00.000000",
                "media_type": "image",
            }
        },
    )

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        """Validate file path is absolute and doesn't contain path traversal.

        Security: Prevents directory traversal attacks like:
        - ../../../etc/passwd
        - /export/../etc/passwd
        """
        # Must be an absolute path
        if not v.startswith("/"):
            raise ValueError("file_path must be an absolute path starting with /")

        # Check for path traversal attempts
        if ".." in v:
            raise ValueError("file_path cannot contain '..' (path traversal)")

        # Check for null bytes (common injection technique)
        if "\x00" in v:
            raise ValueError("file_path cannot contain null bytes")

        return v

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        """Validate timestamp is valid ISO format."""
        try:
            # Try parsing as ISO format
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except (ValueError, AttributeError) as e:
            raise ValueError(f"timestamp must be valid ISO format: {e}") from e
        return v


class AnalysisQueuePayload(BaseModel):
    """Validated payload for items in the analysis queue.

    Security: All fields are validated to ensure:
    - batch_id is a valid UUID or identifier
    - camera_id contains only safe characters
    - detection_ids are positive integers
    """

    batch_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Unique batch identifier",
    )
    camera_id: str | None = Field(
        default=None,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Camera identifier (optional, can be derived from detections)",
    )
    detection_ids: list[int | str] | None = Field(
        default=None,
        description="List of detection IDs to analyze",
    )
    pipeline_start_time: str | None = Field(
        default=None,
        description="ISO format timestamp of when the first file in the batch was detected (for total pipeline latency tracking)",
    )

    model_config = ConfigDict(
        extra="ignore",  # Ignore unexpected fields for forward compatibility
        json_schema_extra={
            "example": {
                "batch_id": "550e8400-e29b-41d4-a716-446655440000",
                "camera_id": "front_door",
                "detection_ids": [1, 2, 3, 4, 5],
            }
        },
    )

    @field_validator("batch_id")
    @classmethod
    def validate_batch_id(cls, v: str) -> str:
        """Validate batch_id doesn't contain dangerous characters."""
        # Check for null bytes
        if "\x00" in v:
            raise ValueError("batch_id cannot contain null bytes")

        # Check for newlines (could affect logging)
        if "\n" in v or "\r" in v:
            raise ValueError("batch_id cannot contain newlines")

        return v

    @field_validator("detection_ids")
    @classmethod
    def validate_detection_ids(cls, v: list[int | str] | None) -> list[int | str] | None:
        """Validate detection_ids are positive integers or numeric strings."""
        if v is None:
            return v

        if not v:
            # Empty list is valid
            return v

        for detection_id in v:
            # Convert to int for validation
            try:
                id_val = int(detection_id)
            except (ValueError, TypeError) as e:
                raise ValueError(f"detection_ids must be integers or numeric strings: {e}") from e

            if id_val < 1:
                raise ValueError("detection_ids must be positive integers")

        # Prevent unreasonably large lists (DoS protection)
        if len(v) > 10000:
            raise ValueError("detection_ids list too large (max 10000)")

        return v


def validate_detection_payload(data: dict) -> DetectionQueuePayload:
    """Validate a detection queue payload.

    Args:
        data: Raw dictionary from queue

    Returns:
        Validated DetectionQueuePayload

    Raises:
        ValueError: If validation fails
    """
    try:
        return DetectionQueuePayload.model_validate(data)
    except Exception as e:
        raise ValueError(f"Invalid detection queue payload: {e}") from e


def validate_analysis_payload(data: dict) -> AnalysisQueuePayload:
    """Validate an analysis queue payload.

    Args:
        data: Raw dictionary from queue

    Returns:
        Validated AnalysisQueuePayload

    Raises:
        ValueError: If validation fails
    """
    try:
        return AnalysisQueuePayload.model_validate(data)
    except Exception as e:
        raise ValueError(f"Invalid analysis queue payload: {e}") from e
