"""Pydantic schemas for settings API endpoints.

These schemas define the response structure for the /api/v1/settings endpoint,
exposing user-configurable settings grouped by category.

Phase 2.1: GET endpoint schemas (NEM-3119)
Phase 2.2: PATCH endpoint schemas (NEM-3120)
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "BatchSettings",
    "BatchSettingsUpdate",
    "DetectionSettings",
    "DetectionSettingsUpdate",
    "FeatureSettings",
    "FeatureSettingsUpdate",
    "QueueSettings",
    "QueueSettingsUpdate",
    "RateLimitingSettings",
    "RateLimitingSettingsUpdate",
    "RetentionSettings",
    "RetentionSettingsUpdate",
    "SettingsResponse",
    "SettingsUpdate",
    "SeveritySettings",
    "SeveritySettingsUpdate",
]


class DetectionSettings(BaseModel):
    """Detection-related settings for object detection thresholds.

    Controls the confidence thresholds used by YOLO26 for object detection
    and fast-path processing for high-priority alerts.
    """

    confidence_threshold: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for object detections (0.0-1.0)",
    )
    fast_path_threshold: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence threshold for fast-path high-priority analysis (0.0-1.0)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "confidence_threshold": 0.5,
                "fast_path_threshold": 0.9,
            }
        }
    )


class BatchSettings(BaseModel):
    """Batch processing settings for detection grouping.

    Controls how detections are batched together before being sent to
    the Nemotron LLM for risk analysis.
    """

    window_seconds: int = Field(
        ...,
        gt=0,
        description="Time window in seconds for batch processing detections",
    )
    idle_timeout_seconds: int = Field(
        ...,
        gt=0,
        description="Idle timeout in seconds before processing incomplete batch",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "window_seconds": 90,
                "idle_timeout_seconds": 30,
            }
        }
    )


class SeveritySettings(BaseModel):
    """Severity threshold settings for risk score categorization.

    Defines the maximum risk score values for each severity level.
    Risk scores are 0-100, and severity is determined by:
    - LOW: 0 to low_max
    - MEDIUM: low_max+1 to medium_max
    - HIGH: medium_max+1 to high_max
    - CRITICAL: above high_max
    """

    low_max: int = Field(
        ...,
        ge=0,
        le=100,
        description="Maximum risk score for LOW severity (0 to this value = LOW)",
    )
    medium_max: int = Field(
        ...,
        ge=0,
        le=100,
        description="Maximum risk score for MEDIUM severity",
    )
    high_max: int = Field(
        ...,
        ge=0,
        le=100,
        description="Maximum risk score for HIGH severity (above = CRITICAL)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "low_max": 29,
                "medium_max": 59,
                "high_max": 84,
            }
        }
    )


class FeatureSettings(BaseModel):
    """Feature toggle settings for enabling/disabling AI pipeline components.

    Controls which AI processing features are active in the detection pipeline.
    """

    vision_extraction_enabled: bool = Field(
        ...,
        description="Enable Florence-2 vision extraction for vehicle/person attributes",
    )
    reid_enabled: bool = Field(
        ...,
        description="Enable CLIP re-identification for tracking entities across cameras",
    )
    scene_change_enabled: bool = Field(
        ...,
        description="Enable SSIM-based scene change detection",
    )
    clip_generation_enabled: bool = Field(
        ...,
        description="Enable automatic clip generation for events",
    )
    image_quality_enabled: bool = Field(
        ...,
        description="Enable BRISQUE image quality assessment (CPU-based)",
    )
    background_eval_enabled: bool = Field(
        ...,
        description="Enable automatic background AI audit evaluation when GPU is idle",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "vision_extraction_enabled": True,
                "reid_enabled": True,
                "scene_change_enabled": True,
                "clip_generation_enabled": True,
                "image_quality_enabled": True,
                "background_eval_enabled": True,
            }
        }
    )


class RateLimitingSettings(BaseModel):
    """Rate limiting settings for API protection.

    Controls request rate limits to prevent abuse and ensure fair resource usage.
    """

    enabled: bool = Field(
        ...,
        description="Enable rate limiting for API endpoints",
    )
    requests_per_minute: int = Field(
        ...,
        ge=1,
        description="Maximum requests per minute per client IP",
    )
    burst_size: int = Field(
        ...,
        ge=1,
        description="Additional burst allowance for short request spikes",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "enabled": True,
                "requests_per_minute": 60,
                "burst_size": 10,
            }
        }
    )


class QueueSettings(BaseModel):
    """Queue settings for Redis-based processing queues.

    Controls queue size limits and backpressure thresholds for the detection
    and analysis processing queues.
    """

    max_size: int = Field(
        ...,
        ge=100,
        description="Maximum size of Redis queues",
    )
    backpressure_threshold: float = Field(
        ...,
        ge=0.5,
        le=1.0,
        description="Queue fill ratio (0.0-1.0) at which to start backpressure warnings",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "max_size": 10000,
                "backpressure_threshold": 0.8,
            }
        }
    )


class RetentionSettings(BaseModel):
    """Data retention settings for events and logs.

    Controls how long events, detections, and logs are retained before cleanup.
    """

    days: int = Field(
        ...,
        gt=0,
        description="Number of days to retain events and detections",
    )
    log_days: int = Field(
        ...,
        gt=0,
        description="Number of days to retain logs",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "days": 30,
                "log_days": 7,
            }
        }
    )


class SettingsResponse(BaseModel):
    """Complete settings response with all configurable settings grouped by category.

    This is the response schema for GET /api/v1/settings, containing all
    user-configurable settings organized into logical groups.
    """

    detection: DetectionSettings = Field(
        ...,
        description="Detection confidence threshold settings",
    )
    batch: BatchSettings = Field(
        ...,
        description="Batch processing settings",
    )
    severity: SeveritySettings = Field(
        ...,
        description="Severity threshold settings for risk categorization",
    )
    features: FeatureSettings = Field(
        ...,
        description="Feature toggle settings",
    )
    rate_limiting: RateLimitingSettings = Field(
        ...,
        description="Rate limiting settings",
    )
    queue: QueueSettings = Field(
        ...,
        description="Queue settings",
    )
    retention: RetentionSettings = Field(
        ...,
        description="Data retention settings",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detection": {
                    "confidence_threshold": 0.5,
                    "fast_path_threshold": 0.9,
                },
                "batch": {
                    "window_seconds": 90,
                    "idle_timeout_seconds": 30,
                },
                "severity": {
                    "low_max": 29,
                    "medium_max": 59,
                    "high_max": 84,
                },
                "features": {
                    "vision_extraction_enabled": True,
                    "reid_enabled": True,
                    "scene_change_enabled": True,
                    "clip_generation_enabled": True,
                    "image_quality_enabled": True,
                    "background_eval_enabled": True,
                },
                "rate_limiting": {
                    "enabled": True,
                    "requests_per_minute": 60,
                    "burst_size": 10,
                },
                "queue": {
                    "max_size": 10000,
                    "backpressure_threshold": 0.8,
                },
                "retention": {
                    "days": 30,
                    "log_days": 7,
                },
            }
        }
    )


# =============================================================================
# Update Schemas (all fields optional for partial updates)
# =============================================================================


class DetectionSettingsUpdate(BaseModel):
    """Detection settings update schema (all fields optional).

    Used for PATCH /api/v1/settings to partially update detection settings.
    """

    confidence_threshold: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for object detections (0.0-1.0)",
    )
    fast_path_threshold: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Confidence threshold for fast-path high-priority analysis (0.0-1.0)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "confidence_threshold": 0.6,
            }
        }
    )


class BatchSettingsUpdate(BaseModel):
    """Batch settings update schema (all fields optional).

    Used for PATCH /api/v1/settings to partially update batch processing settings.
    Validates that idle_timeout_seconds < window_seconds when both are provided.
    """

    window_seconds: int | None = Field(
        None,
        gt=0,
        le=600,
        description="Time window in seconds for batch processing detections (max 600)",
    )
    idle_timeout_seconds: int | None = Field(
        None,
        gt=0,
        le=300,
        description="Idle timeout in seconds before processing incomplete batch (max 300)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "window_seconds": 120,
            }
        }
    )

    @model_validator(mode="after")
    def validate_timeout_relationship(self) -> BatchSettingsUpdate:
        """Validate that idle_timeout_seconds is less than window_seconds when both provided."""
        # Only validate when both fields are provided together
        if self.window_seconds is not None and self.idle_timeout_seconds is not None:
            if self.idle_timeout_seconds >= self.window_seconds:
                raise ValueError(
                    "idle_timeout_seconds must be less than window_seconds for optimal batch processing"
                )

        return self


class SeveritySettingsUpdate(BaseModel):
    """Severity settings update schema (all fields optional).

    Used for PATCH /api/v1/settings to partially update severity thresholds.
    Validates that severity thresholds maintain proper ordering (low < medium < high).
    """

    low_max: int | None = Field(
        None,
        ge=0,
        le=100,
        description="Maximum risk score for LOW severity (0 to this value = LOW)",
    )
    medium_max: int | None = Field(
        None,
        ge=0,
        le=100,
        description="Maximum risk score for MEDIUM severity",
    )
    high_max: int | None = Field(
        None,
        ge=0,
        le=100,
        description="Maximum risk score for HIGH severity (above = CRITICAL)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "low_max": 25,
            }
        }
    )

    @model_validator(mode="after")
    def validate_severity_ordering(self) -> SeveritySettingsUpdate:
        """Validate that severity thresholds are properly ordered when multiple are provided."""
        # Only validate when multiple thresholds are provided together
        provided = [
            ("low_max", self.low_max),
            ("medium_max", self.medium_max),
            ("high_max", self.high_max),
        ]
        provided_values = [(name, val) for name, val in provided if val is not None]

        if len(provided_values) >= 2:
            # Check ordering of provided values
            if (
                self.low_max is not None
                and self.medium_max is not None
                and self.low_max >= self.medium_max
            ):
                raise ValueError("low_max must be less than medium_max")
            if (
                self.medium_max is not None
                and self.high_max is not None
                and self.medium_max >= self.high_max
            ):
                raise ValueError("medium_max must be less than high_max")
            if (
                self.low_max is not None
                and self.high_max is not None
                and self.low_max >= self.high_max
            ):
                raise ValueError("low_max must be less than high_max")

        return self


class FeatureSettingsUpdate(BaseModel):
    """Feature settings update schema (all fields optional).

    Used for PATCH /api/v1/settings to partially update feature toggles.
    """

    vision_extraction_enabled: bool | None = Field(
        None,
        description="Enable Florence-2 vision extraction for vehicle/person attributes",
    )
    reid_enabled: bool | None = Field(
        None,
        description="Enable CLIP re-identification for tracking entities across cameras",
    )
    scene_change_enabled: bool | None = Field(
        None,
        description="Enable SSIM-based scene change detection",
    )
    clip_generation_enabled: bool | None = Field(
        None,
        description="Enable automatic clip generation for events",
    )
    image_quality_enabled: bool | None = Field(
        None,
        description="Enable BRISQUE image quality assessment (CPU-based)",
    )
    background_eval_enabled: bool | None = Field(
        None,
        description="Enable automatic background AI audit evaluation when GPU is idle",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "reid_enabled": False,
            }
        }
    )


class RateLimitingSettingsUpdate(BaseModel):
    """Rate limiting settings update schema (all fields optional).

    Used for PATCH /api/v1/settings to partially update rate limiting.
    """

    enabled: bool | None = Field(
        None,
        description="Enable rate limiting for API endpoints",
    )
    requests_per_minute: int | None = Field(
        None,
        ge=1,
        le=10000,
        description="Maximum requests per minute per client IP",
    )
    burst_size: int | None = Field(
        None,
        ge=1,
        le=100,
        description="Additional burst allowance for short request spikes",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "requests_per_minute": 120,
            }
        }
    )


class QueueSettingsUpdate(BaseModel):
    """Queue settings update schema (all fields optional).

    Used for PATCH /api/v1/settings to partially update queue configuration.
    """

    max_size: int | None = Field(
        None,
        ge=100,
        le=100000,
        description="Maximum size of Redis queues",
    )
    backpressure_threshold: float | None = Field(
        None,
        ge=0.5,
        le=1.0,
        description="Queue fill ratio (0.0-1.0) at which to start backpressure warnings",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "max_size": 15000,
            }
        }
    )


class RetentionSettingsUpdate(BaseModel):
    """Retention settings update schema (all fields optional).

    Used for PATCH /api/v1/settings to partially update retention policies.
    """

    days: int | None = Field(
        None,
        ge=1,
        le=365,
        description="Number of days to retain events and detections (1-365)",
    )
    log_days: int | None = Field(
        None,
        ge=1,
        le=365,
        description="Number of days to retain logs (1-365)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "days": 60,
            }
        }
    )


class SettingsUpdate(BaseModel):
    """Schema for updating runtime settings via PATCH.

    All fields are optional to support partial updates. Only provided
    fields will be updated. Changes are written to data/runtime.env
    and take effect immediately without server restart.
    """

    detection: DetectionSettingsUpdate | None = Field(
        None,
        description="Detection confidence threshold settings",
    )
    batch: BatchSettingsUpdate | None = Field(
        None,
        description="Batch processing settings",
    )
    severity: SeveritySettingsUpdate | None = Field(
        None,
        description="Severity threshold settings for risk categorization",
    )
    features: FeatureSettingsUpdate | None = Field(
        None,
        description="Feature toggle settings",
    )
    rate_limiting: RateLimitingSettingsUpdate | None = Field(
        None,
        description="Rate limiting settings",
    )
    queue: QueueSettingsUpdate | None = Field(
        None,
        description="Queue settings",
    )
    retention: RetentionSettingsUpdate | None = Field(
        None,
        description="Data retention settings",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detection": {
                    "confidence_threshold": 0.6,
                },
                "features": {
                    "reid_enabled": False,
                },
            }
        }
    )
