"""Pydantic schemas for plate read API endpoints.

License plate recognition schemas for ALPR (Automatic License Plate
Recognition) functionality, supporting plate detection, OCR, and search.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BoundingBox(BaseModel):
    """Bounding box coordinates for plate detection.

    Coordinates are in pixel space relative to the source image.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "x1": 100.0,
                "y1": 200.0,
                "x2": 250.0,
                "y2": 240.0,
            }
        }
    )

    x1: float = Field(..., description="Left edge X coordinate")
    y1: float = Field(..., description="Top edge Y coordinate")
    x2: float = Field(..., description="Right edge X coordinate")
    y2: float = Field(..., description="Bottom edge Y coordinate")


class PlateReadBase(BaseModel):
    """Base schema for plate read data.

    Contains common fields for plate read creation and response.
    """

    camera_id: str = Field(..., description="Camera ID where plate was detected")
    timestamp: datetime = Field(..., description="Detection timestamp")
    plate_text: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Recognized plate text (alphanumeric only)",
    )
    raw_text: str = Field(..., max_length=50, description="Raw OCR output before filtering")
    detection_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Plate detection confidence (0-1)"
    )
    ocr_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Text recognition confidence (0-1)"
    )
    bbox: list[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Bounding box [x1, y1, x2, y2]",
    )
    image_quality_score: float = Field(
        ..., ge=0.0, le=1.0, description="Image quality assessment (0-1)"
    )
    is_enhanced: bool = Field(
        default=False, description="Whether low-light enhancement was applied"
    )
    is_blurry: bool = Field(default=False, description="Whether motion blur was detected")


class PlateReadCreate(PlateReadBase):
    """Schema for creating a new plate read record.

    Used when manually creating plate reads via the API (e.g., from
    external ALPR systems or manual entry).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "camera_id": "driveway",
                "timestamp": "2026-01-26T14:30:00Z",
                "plate_text": "ABC1234",
                "raw_text": "ABC-1234",
                "detection_confidence": 0.95,
                "ocr_confidence": 0.92,
                "bbox": [100.0, 200.0, 250.0, 240.0],
                "image_quality_score": 0.85,
                "is_enhanced": False,
                "is_blurry": False,
            }
        }
    )


class PlateReadResponse(PlateReadBase):
    """Response schema for a plate read record.

    Includes the database ID for reference and linking.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "camera_id": "driveway",
                "timestamp": "2026-01-26T14:30:00Z",
                "plate_text": "ABC1234",
                "raw_text": "ABC-1234",
                "detection_confidence": 0.95,
                "ocr_confidence": 0.92,
                "bbox": [100.0, 200.0, 250.0, 240.0],
                "image_quality_score": 0.85,
                "is_enhanced": False,
                "is_blurry": False,
                "created_at": "2026-01-26T14:30:05Z",
            }
        },
    )

    id: int = Field(..., description="Database record ID")
    created_at: datetime = Field(..., description="Record creation timestamp")


class PlateReadListResponse(BaseModel):
    """Paginated list of plate reads.

    Standard pagination envelope for plate read list endpoints.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "plate_reads": [
                    {
                        "id": 1,
                        "camera_id": "driveway",
                        "timestamp": "2026-01-26T14:30:00Z",
                        "plate_text": "ABC1234",
                        "raw_text": "ABC-1234",
                        "detection_confidence": 0.95,
                        "ocr_confidence": 0.92,
                        "bbox": [100.0, 200.0, 250.0, 240.0],
                        "image_quality_score": 0.85,
                        "is_enhanced": False,
                        "is_blurry": False,
                        "created_at": "2026-01-26T14:30:05Z",
                    }
                ],
                "total": 1,
                "page": 1,
                "page_size": 50,
            }
        }
    )

    plate_reads: list[PlateReadResponse] = Field(..., description="List of plate reads")
    total: int = Field(..., ge=0, description="Total number of plate reads matching query")
    page: int = Field(..., ge=1, description="Current page number (1-indexed)")
    page_size: int = Field(..., ge=1, le=1000, description="Number of items per page")


class PlateRecognizeRequest(BaseModel):
    """Request schema for plate recognition from image data.

    Used for the /recognize endpoint to extract plate text from
    uploaded images or base64-encoded image data.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "camera_id": "driveway",
                "image_base64": "data:image/jpeg;base64,/9j/4AAQSkZ...",
                "detection_bbox": [100.0, 200.0, 250.0, 240.0],
                "detection_confidence": 0.95,
            }
        }
    )

    camera_id: str = Field(..., description="Camera ID for the source image")
    image_base64: str = Field(..., description="Base64-encoded image data (JPEG or PNG)")
    detection_bbox: list[float] | None = Field(
        None,
        min_length=4,
        max_length=4,
        description="Optional bounding box for plate region [x1, y1, x2, y2]",
    )
    detection_confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Detection confidence from upstream detector",
    )


class PlateRecognizeResponse(BaseModel):
    """Response schema for plate recognition request.

    Returns the recognized plate text and confidence metrics
    without storing to database (for preview/testing).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "plate_text": "ABC1234",
                "raw_text": "ABC-1234",
                "ocr_confidence": 0.92,
                "image_quality_score": 0.85,
                "is_enhanced": False,
                "is_blurry": False,
                "stored": True,
                "plate_read_id": 123,
            }
        }
    )

    plate_text: str = Field(..., description="Recognized plate text (alphanumeric only)")
    raw_text: str = Field(..., description="Raw OCR output before filtering")
    ocr_confidence: float = Field(..., ge=0.0, le=1.0, description="OCR confidence (0-1)")
    image_quality_score: float = Field(..., ge=0.0, le=1.0, description="Image quality score (0-1)")
    is_enhanced: bool = Field(..., description="Whether low-light enhancement was applied")
    is_blurry: bool = Field(..., description="Whether motion blur was detected")
    stored: bool = Field(..., description="Whether the read was stored in database")
    plate_read_id: int | None = Field(
        None, description="Database ID if stored (null if not stored)"
    )


class PlateStatisticsResponse(BaseModel):
    """Statistics for plate recognition performance and activity.

    Aggregated metrics for monitoring ALPR system health and usage.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_reads": 1523,
                "unique_plates": 342,
                "avg_ocr_confidence": 0.89,
                "avg_quality_score": 0.82,
                "enhanced_count": 127,
                "blurry_count": 45,
                "reads_last_hour": 23,
                "reads_last_24h": 198,
            }
        }
    )

    total_reads: int = Field(..., ge=0, description="Total number of plate reads")
    unique_plates: int = Field(..., ge=0, description="Count of unique plate texts")
    avg_ocr_confidence: float = Field(..., ge=0.0, le=1.0, description="Average OCR confidence")
    avg_quality_score: float = Field(..., ge=0.0, le=1.0, description="Average image quality score")
    enhanced_count: int = Field(..., ge=0, description="Number of reads with low-light enhancement")
    blurry_count: int = Field(..., ge=0, description="Number of reads with motion blur")
    reads_last_hour: int = Field(..., ge=0, description="Reads in the last hour")
    reads_last_24h: int = Field(..., ge=0, description="Reads in the last 24 hours")
