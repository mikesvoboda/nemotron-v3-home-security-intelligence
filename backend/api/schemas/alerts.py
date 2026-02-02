"""Pydantic schemas for alerts API endpoints."""

import re
from datetime import datetime
from enum import StrEnum, auto
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from backend.api.schemas.pagination import PaginationMeta

# Pattern for valid dedup_key: alphanumeric, underscore, hyphen, colon only
# This prevents injection attacks via special characters (NEM-1107)
DEDUP_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9_:\-]+$")


def validate_dedup_key(value: str) -> str:
    """Validate dedup_key contains only safe characters.

    Args:
        value: The dedup_key value to validate

    Returns:
        The validated value

    Raises:
        ValueError: If the value contains invalid characters

    Security:
        Rejects SQL injection, command injection, path traversal,
        XSS vectors, and non-ASCII unicode characters.
    """
    if value and not DEDUP_KEY_PATTERN.match(value):
        raise ValueError(
            "dedup_key contains invalid characters. "
            "Only alphanumeric characters, underscores, hyphens, and colons are allowed."
        )
    return value


# Type alias for validated dedup_key fields
DedupKeyStr = Annotated[str, AfterValidator(validate_dedup_key)]


class AlertSeverity(StrEnum):
    """Alert severity levels."""

    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    CRITICAL = auto()


class AlertStatus(StrEnum):
    """Alert status values."""

    PENDING = auto()
    DELIVERED = auto()
    ACKNOWLEDGED = auto()
    DISMISSED = auto()


# =============================================================================
# AlertRule Schemas
# =============================================================================


# Valid days of the week for schedule validation
VALID_DAYS = frozenset(
    ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
)

# Valid pose classes for pose_types validation
# Based on PoseResult model CHECK constraint (ck_pose_results_pose_class)
VALID_POSE_CLASSES = frozenset(
    ["standing", "crouching", "bending_over", "arms_raised", "sitting", "lying_down", "unknown"]
)

# Valid threat types for threat_types validation
# Based on ThreatDetection model CHECK constraint (ck_threat_detections_threat_type)
VALID_THREAT_TYPES = frozenset(["gun", "knife", "grenade", "explosive", "weapon", "other"])

# Valid threat severity levels
# Based on ThreatDetection model CHECK constraint (ck_threat_detections_severity)
VALID_THREAT_SEVERITIES = frozenset(["critical", "high", "medium", "low"])


def validate_time_format(time_str: str) -> tuple[int, int]:
    """Validate time format and return hours and minutes.

    Args:
        time_str: Time string in HH:MM format

    Returns:
        Tuple of (hours, minutes)

    Raises:
        ValueError: If time format is invalid or values out of range
    """
    if not time_str or len(time_str) != 5 or time_str[2] != ":":
        raise ValueError(f"Invalid time format '{time_str}'. Expected HH:MM format.")

    try:
        hours = int(time_str[:2])
        minutes = int(time_str[3:])
    except ValueError as err:
        raise ValueError(
            f"Invalid time format '{time_str}'. Hours and minutes must be numeric."
        ) from err

    if hours < 0 or hours > 23:
        raise ValueError(f"Invalid hours '{hours}' in time '{time_str}'. Hours must be 00-23.")
    if minutes < 0 or minutes > 59:
        raise ValueError(
            f"Invalid minutes '{minutes}' in time '{time_str}'. Minutes must be 00-59."
        )

    return hours, minutes


class AlertRuleSchedule(BaseModel):
    """Schema for alert rule schedule (time-based conditions).

    If start_time > end_time, the schedule spans midnight (e.g., 22:00-06:00).
    Empty days array means all days. No schedule = always active (vacation mode).

    Validation:
    - Days must be valid day names (monday-sunday)
    - Times must be valid HH:MM format with hours 00-23, minutes 00-59
    - Start and end times are validated but can span midnight
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
                "start_time": "22:00",
                "end_time": "06:00",
                "timezone": "America/New_York",
            }
        }
    )

    days: list[str] | None = Field(
        None,
        description="Days of week when rule is active (empty = all days). "
        "Values: monday, tuesday, wednesday, thursday, friday, saturday, sunday",
    )
    start_time: str | None = Field(
        None,
        pattern=r"^\d{2}:\d{2}$",
        description="Start time in HH:MM format (00:00-23:59)",
    )
    end_time: str | None = Field(
        None,
        pattern=r"^\d{2}:\d{2}$",
        description="End time in HH:MM format (00:00-23:59)",
    )
    timezone: str = Field("UTC", description="Timezone for time evaluation")

    @field_validator("days")
    @classmethod
    def validate_days(cls, v: list[str] | None) -> list[str] | None:
        """Validate that days are valid day names.

        Args:
            v: List of day names or None

        Returns:
            Validated list or None

        Raises:
            ValueError: If any day is invalid
        """
        if v is None:
            return v

        invalid_days = [day for day in v if day.lower() not in VALID_DAYS]
        if invalid_days:
            raise ValueError(
                f"Invalid day(s): {', '.join(invalid_days)}. "
                f"Valid days are: {', '.join(sorted(VALID_DAYS))}"
            )

        # Normalize to lowercase
        return [day.lower() for day in v]

    @field_validator("start_time")
    @classmethod
    def validate_start_time(cls, v: str | None) -> str | None:
        """Validate start time format and values.

        Args:
            v: Time string or None

        Returns:
            Validated time string or None

        Raises:
            ValueError: If time format is invalid
        """
        if v is None:
            return v
        validate_time_format(v)
        return v

    @field_validator("end_time")
    @classmethod
    def validate_end_time(cls, v: str | None) -> str | None:
        """Validate end time format and values.

        Args:
            v: Time string or None

        Returns:
            Validated time string or None

        Raises:
            ValueError: If time format is invalid
        """
        if v is None:
            return v
        validate_time_format(v)
        return v


class AlertRuleConditions(BaseModel):
    """Schema for legacy alert rule conditions (backward compatibility).

    New rules should use explicit fields on AlertRuleCreate/AlertRuleUpdate.
    This schema is kept for backward compatibility with existing rules.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "risk_threshold": 70,
                "object_types": ["person", "vehicle"],
                "camera_ids": ["front_door", "backyard"],
                "time_ranges": [{"start": "22:00", "end": "06:00"}],
            }
        }
    )

    risk_threshold: int | None = Field(
        None, ge=0, le=100, description="Minimum risk score to trigger alert"
    )
    object_types: list[str] | None = Field(
        None, description="Object types that trigger alerts (e.g., person, vehicle)"
    )
    camera_ids: list[str] | None = Field(
        None, description="Specific camera IDs that trigger alerts"
    )
    time_ranges: list[dict] | None = Field(
        None, description="Time ranges when alerts are active (start/end in HH:MM format)"
    )


class AlertRuleCreate(BaseModel):
    """Schema for creating an alert rule.

    All conditions use AND logic - all specified conditions must match for the rule to trigger.
    Leave a condition as null/empty to not filter on that criterion.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Night Intruder Alert",
                "description": "High-priority alert for person detection at night",
                "enabled": True,
                "severity": "critical",
                "risk_threshold": 70,
                "object_types": ["person"],
                "camera_ids": ["front_door", "backyard"],
                "min_confidence": 0.8,
                "schedule": {
                    "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
                    "start_time": "22:00",
                    "end_time": "06:00",
                    "timezone": "America/New_York",
                },
                "dedup_key_template": "{camera_id}:{rule_id}",
                "cooldown_seconds": 300,
                "channels": ["pushover", "webhook"],
                "dwell_time_enabled": False,
            }
        }
    )

    name: str = Field(..., min_length=1, max_length=255, description="Rule name")
    description: str | None = Field(None, description="Rule description")
    enabled: bool = Field(True, description="Whether the rule is active")
    severity: AlertSeverity = Field(
        AlertSeverity.MEDIUM, description="Severity level for triggered alerts"
    )

    # Explicit condition fields (preferred over legacy conditions)
    risk_threshold: int | None = Field(
        None, ge=0, le=100, description="Alert when risk_score >= threshold"
    )
    object_types: list[str] | None = Field(
        None, description="Object types to match (e.g., ['person', 'vehicle'])"
    )
    camera_ids: list[str] | None = Field(
        None, description="Camera IDs to apply rule to (empty = all cameras)"
    )
    zone_ids: list[str] | None = Field(None, description="Zone IDs to match (empty = any zone)")
    min_confidence: float | None = Field(
        None, ge=0.0, le=1.0, description="Minimum detection confidence (0.0-1.0)"
    )
    schedule: AlertRuleSchedule | None = Field(
        None, description="Time-based conditions (null = always active)"
    )

    # Legacy conditions field (for backward compatibility)
    conditions: AlertRuleConditions | None = Field(
        None, description="Legacy conditions (use explicit fields instead)"
    )

    # =========================================================================
    # New Alert Condition Types (NEM-5085)
    # =========================================================================

    # Dwell time condition: Alert when dwell exceeds threshold in a zone
    dwell_threshold_seconds: int | None = Field(
        None, ge=0, description="Dwell time threshold in seconds (alert when exceeded)"
    )
    exclude_household_members: bool = Field(
        False, description="Whether to exclude household members from dwell time alerts"
    )

    # Pose condition: Alert on specific poses
    pose_types: list[str] | None = Field(
        None,
        description="Pose types to alert on (e.g., ['crouching', 'lying_down']). "
        "Valid: standing, crouching, bending_over, arms_raised, sitting, lying_down, unknown",
    )
    pose_confidence_threshold: float | None = Field(
        None, ge=0.0, le=1.0, description="Minimum pose confidence (0.0-1.0)"
    )

    # Action condition: Alert on X-CLIP recognized actions
    action_types: list[str] | None = Field(
        None,
        description="Action types to alert on (e.g., ['loitering', 'peering_through_window']). "
        "Actions are recognized by X-CLIP model.",
    )
    action_confidence_threshold: float | None = Field(
        None, ge=0.0, le=1.0, description="Minimum action confidence (0.0-1.0)"
    )

    # Threat condition: Alert on weapon detection
    threat_detection_enabled: bool = Field(
        False, description="Enable alert on threat/weapon detection"
    )
    threat_types: list[str] | None = Field(
        None,
        description="Threat types to alert on (e.g., ['gun', 'knife']). "
        "Valid: gun, knife, grenade, explosive, weapon, other",
    )
    threat_min_severity: str | None = Field(
        None, description="Minimum threat severity (critical, high, medium, low)"
    )
    threat_confidence_threshold: float | None = Field(
        None, ge=0.0, le=1.0, description="Minimum threat detection confidence (0.0-1.0)"
    )

    # Smoke/fire condition: Alert on smoke or fire detection
    smoke_fire_detection_enabled: bool = Field(
        False, description="Enable alert on smoke/fire detection"
    )
    smoke_fire_consecutive_required: int = Field(
        2,
        ge=1,
        description="Number of consecutive smoke/fire detections required (reduces false positives)",
    )
    smoke_fire_confidence_threshold: float | None = Field(
        None, ge=0.0, le=1.0, description="Minimum smoke/fire confidence (0.0-1.0)"
    )

    # Deduplication settings
    dedup_key_template: str = Field(
        "{camera_id}:{rule_id}",
        max_length=255,
        description="Template for dedup key. Variables: {camera_id}, {rule_id}, {object_type}",
    )
    cooldown_seconds: int = Field(300, ge=0, description="Minimum seconds between duplicate alerts")
    channels: list[str] = Field(
        default_factory=list, description="Notification channels for this rule"
    )
    dwell_time_enabled: bool = Field(
        default=False,
        description="Enable dwell time / loitering detection. "
        "Uses the zone's loitering_threshold_seconds to trigger alerts.",
    )

    @field_validator("pose_types")
    @classmethod
    def validate_pose_types(cls, v: list[str] | None) -> list[str] | None:
        """Validate that pose_types contains valid pose classes."""
        if v is None or len(v) == 0:
            return v

        invalid_poses = [pose for pose in v if pose not in VALID_POSE_CLASSES]
        if invalid_poses:
            raise ValueError(
                f"Invalid pose type(s): {', '.join(invalid_poses)}. "
                f"Valid pose types are: {', '.join(sorted(VALID_POSE_CLASSES))}"
            )
        return v

    @field_validator("threat_types")
    @classmethod
    def validate_threat_types(cls, v: list[str] | None) -> list[str] | None:
        """Validate that threat_types contains valid threat types."""
        if v is None or len(v) == 0:
            return v

        # Threat types are validated but we allow them even when disabled
        # This permits configuring the filter before enabling
        invalid_threats = [threat for threat in v if threat not in VALID_THREAT_TYPES]
        if invalid_threats:
            raise ValueError(
                f"Invalid threat type(s): {', '.join(invalid_threats)}. "
                f"Valid threat types are: {', '.join(sorted(VALID_THREAT_TYPES))}"
            )
        return v

    @field_validator("threat_min_severity")
    @classmethod
    def validate_threat_min_severity(cls, v: str | None) -> str | None:
        """Validate that threat_min_severity is a valid severity level."""
        if v is None:
            return v

        if v not in VALID_THREAT_SEVERITIES:
            raise ValueError(
                f"Invalid threat severity: {v}. "
                f"Valid severities are: {', '.join(sorted(VALID_THREAT_SEVERITIES))}"
            )
        return v


class AlertRuleUpdate(BaseModel):
    """Schema for updating an alert rule (PATCH).

    Only provided fields will be updated. Null values clear the field.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "enabled": False,
                "risk_threshold": 80,
                "cooldown_seconds": 600,
                "dwell_time_enabled": True,
            }
        }
    )

    name: str | None = Field(None, min_length=1, max_length=255, description="Rule name")
    description: str | None = Field(None, description="Rule description")
    enabled: bool | None = Field(None, description="Whether the rule is active")
    severity: AlertSeverity | None = Field(None, description="Severity level")

    # Explicit condition fields
    risk_threshold: int | None = Field(
        None, ge=0, le=100, description="Alert when risk_score >= threshold"
    )
    object_types: list[str] | None = Field(None, description="Object types to match")
    camera_ids: list[str] | None = Field(None, description="Camera IDs to apply rule to")
    zone_ids: list[str] | None = Field(None, description="Zone IDs to match")
    min_confidence: float | None = Field(
        None, ge=0.0, le=1.0, description="Minimum detection confidence"
    )
    schedule: AlertRuleSchedule | None = Field(None, description="Time-based conditions")

    # Legacy conditions
    conditions: AlertRuleConditions | None = Field(None, description="Legacy conditions")

    # =========================================================================
    # New Alert Condition Types (NEM-5085)
    # =========================================================================

    # Dwell time condition
    dwell_threshold_seconds: int | None = Field(
        None, ge=0, description="Dwell time threshold in seconds"
    )
    exclude_household_members: bool | None = Field(
        None, description="Whether to exclude household members from dwell time alerts"
    )

    # Pose condition
    pose_types: list[str] | None = Field(None, description="Pose types to alert on")
    pose_confidence_threshold: float | None = Field(
        None, ge=0.0, le=1.0, description="Minimum pose confidence"
    )

    # Action condition
    action_types: list[str] | None = Field(None, description="Action types to alert on")
    action_confidence_threshold: float | None = Field(
        None, ge=0.0, le=1.0, description="Minimum action confidence"
    )

    # Threat condition
    threat_detection_enabled: bool | None = Field(
        None, description="Enable alert on threat detection"
    )
    threat_types: list[str] | None = Field(None, description="Threat types to alert on")
    threat_min_severity: str | None = Field(None, description="Minimum threat severity")
    threat_confidence_threshold: float | None = Field(
        None, ge=0.0, le=1.0, description="Minimum threat confidence"
    )

    # Smoke/fire condition
    smoke_fire_detection_enabled: bool | None = Field(
        None, description="Enable alert on smoke/fire detection"
    )
    smoke_fire_consecutive_required: int | None = Field(
        None, ge=1, description="Consecutive detections required"
    )
    smoke_fire_confidence_threshold: float | None = Field(
        None, ge=0.0, le=1.0, description="Minimum smoke/fire confidence"
    )

    # Deduplication settings
    dedup_key_template: str | None = Field(
        None, max_length=255, description="Template for dedup key"
    )
    cooldown_seconds: int | None = Field(
        None, ge=0, description="Minimum seconds between duplicate alerts"
    )
    channels: list[str] | None = Field(None, description="Notification channels for this rule")
    dwell_time_enabled: bool | None = Field(
        None,
        description="Enable dwell time / loitering detection. "
        "Uses the zone's loitering_threshold_seconds to trigger alerts.",
    )

    @field_validator("pose_types")
    @classmethod
    def validate_pose_types(cls, v: list[str] | None) -> list[str] | None:
        """Validate that pose_types contains valid pose classes."""
        if v is None or len(v) == 0:
            return v

        invalid_poses = [pose for pose in v if pose not in VALID_POSE_CLASSES]
        if invalid_poses:
            raise ValueError(
                f"Invalid pose type(s): {', '.join(invalid_poses)}. "
                f"Valid pose types are: {', '.join(sorted(VALID_POSE_CLASSES))}"
            )
        return v

    @field_validator("threat_types")
    @classmethod
    def validate_threat_types(cls, v: list[str] | None) -> list[str] | None:
        """Validate that threat_types contains valid threat types."""
        if v is None or len(v) == 0:
            return v

        invalid_threats = [threat for threat in v if threat not in VALID_THREAT_TYPES]
        if invalid_threats:
            raise ValueError(
                f"Invalid threat type(s): {', '.join(invalid_threats)}. "
                f"Valid threat types are: {', '.join(sorted(VALID_THREAT_TYPES))}"
            )
        return v

    @field_validator("threat_min_severity")
    @classmethod
    def validate_threat_min_severity(cls, v: str | None) -> str | None:
        """Validate that threat_min_severity is a valid severity level."""
        if v is None:
            return v

        if v not in VALID_THREAT_SEVERITIES:
            raise ValueError(
                f"Invalid threat severity: {v}. "
                f"Valid severities are: {', '.join(sorted(VALID_THREAT_SEVERITIES))}"
            )
        return v


class AlertRuleResponse(BaseModel):
    """Schema for alert rule response."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Night Intruder Alert",
                "description": "High-priority alert for person detection at night",
                "enabled": True,
                "severity": "critical",
                "risk_threshold": 70,
                "object_types": ["person"],
                "camera_ids": ["front_door", "backyard"],
                "zone_ids": None,
                "min_confidence": 0.8,
                "schedule": {
                    "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
                    "start_time": "22:00",
                    "end_time": "06:00",
                    "timezone": "America/New_York",
                },
                "conditions": None,
                "dedup_key_template": "{camera_id}:{rule_id}",
                "cooldown_seconds": 300,
                "channels": ["pushover", "webhook"],
                "dwell_time_enabled": False,
                "created_at": "2025-12-28T12:00:00Z",
                "updated_at": "2025-12-28T12:00:00Z",
            }
        },
    )

    id: str = Field(..., description="Alert rule UUID")
    name: str = Field(..., description="Rule name")
    description: str | None = Field(None, description="Rule description")
    enabled: bool = Field(..., description="Whether the rule is active")
    severity: AlertSeverity = Field(..., description="Severity level")

    # Explicit condition fields
    risk_threshold: int | None = Field(None, description="Risk score threshold")
    object_types: list[str] | None = Field(None, description="Object types to match")
    camera_ids: list[str] | None = Field(None, description="Camera IDs to apply to")
    zone_ids: list[str] | None = Field(None, description="Zone IDs to match")
    min_confidence: float | None = Field(None, description="Minimum confidence")
    schedule: AlertRuleSchedule | None = Field(None, description="Time-based conditions")

    # Legacy conditions
    conditions: AlertRuleConditions | None = Field(None, description="Legacy conditions")

    # =========================================================================
    # New Alert Condition Types (NEM-5085)
    # =========================================================================

    # Dwell time condition
    dwell_threshold_seconds: int | None = Field(None, description="Dwell time threshold in seconds")
    exclude_household_members: bool = Field(
        False, description="Exclude household members from dwell time alerts"
    )

    # Pose condition
    pose_types: list[str] | None = Field(None, description="Pose types to alert on")
    pose_confidence_threshold: float | None = Field(None, description="Minimum pose confidence")

    # Action condition
    action_types: list[str] | None = Field(None, description="Action types to alert on")
    action_confidence_threshold: float | None = Field(None, description="Minimum action confidence")

    # Threat condition
    threat_detection_enabled: bool = Field(False, description="Enable threat detection alerts")
    threat_types: list[str] | None = Field(None, description="Threat types to alert on")
    threat_min_severity: str | None = Field(None, description="Minimum threat severity")
    threat_confidence_threshold: float | None = Field(None, description="Minimum threat confidence")

    # Smoke/fire condition
    smoke_fire_detection_enabled: bool = Field(False, description="Enable smoke/fire alerts")
    smoke_fire_consecutive_required: int = Field(2, description="Consecutive detections required")
    smoke_fire_confidence_threshold: float | None = Field(
        None, description="Minimum smoke/fire confidence"
    )

    # Deduplication settings
    dedup_key_template: str = Field(..., description="Template for dedup key")
    cooldown_seconds: int = Field(..., description="Minimum seconds between duplicate alerts")
    channels: list[str] = Field(default_factory=list, description="Notification channels")
    dwell_time_enabled: bool = Field(
        default=False,
        description="Enable dwell time / loitering detection. "
        "Uses the zone's loitering_threshold_seconds to trigger alerts.",
    )

    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class AlertRuleListResponse(BaseModel):
    """Schema for alert rule list response with pagination."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "name": "High Risk Alert",
                        "enabled": True,
                        "conditions": {"risk_threshold": 70},
                        "cooldown_seconds": 300,
                        "channels": ["pushover"],
                        "created_at": "2025-12-28T12:00:00Z",
                        "updated_at": "2025-12-28T12:00:00Z",
                    }
                ],
                "pagination": {
                    "total": 1,
                    "limit": 50,
                    "offset": 0,
                    "cursor": None,
                    "next_cursor": None,
                    "has_more": False,
                },
            }
        }
    )

    items: list[AlertRuleResponse] = Field(..., description="List of alert rules")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")


# =============================================================================
# Alert Schemas
# =============================================================================


class AlertCreate(BaseModel):
    """Schema for creating an alert."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_id": 123,
                "rule_id": "550e8400-e29b-41d4-a716-446655440000",
                "severity": "high",
                "dedup_key": "front_door:person:entry_zone",
                "channels": ["pushover"],
                "metadata": {"camera_name": "Front Door"},
            }
        }
    )

    event_id: int = Field(..., description="Event ID that triggered this alert")
    rule_id: str | None = Field(None, description="Alert rule UUID that matched (optional)")
    severity: AlertSeverity = Field(AlertSeverity.MEDIUM, description="Alert severity level")
    dedup_key: DedupKeyStr = Field(
        ...,
        max_length=255,
        description="Deduplication key for alert grouping. "
        "Only alphanumeric, underscore, hyphen, and colon characters allowed.",
    )
    channels: list[str] = Field(
        default_factory=list, description="Notification channels to deliver to"
    )
    metadata: dict | None = Field(None, description="Additional context for the alert")


class AlertUpdate(BaseModel):
    """Schema for updating an alert (PATCH)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "acknowledged",
            }
        }
    )

    status: AlertStatus | None = Field(None, description="Alert status")
    delivered_at: datetime | None = Field(None, description="Delivery timestamp")
    channels: list[str] | None = Field(
        None, description="Notification channels that received this alert"
    )
    metadata: dict | None = Field(None, description="Additional context for the alert")


class AlertResponse(BaseModel):
    """Schema for alert response."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440001",
                "event_id": 123,
                "rule_id": "550e8400-e29b-41d4-a716-446655440000",
                "severity": "high",
                "status": "delivered",
                "created_at": "2025-12-28T12:00:00Z",
                "updated_at": "2025-12-28T12:01:00Z",
                "delivered_at": "2025-12-28T12:00:30Z",
                "channels": ["pushover"],
                "dedup_key": "front_door:person:entry_zone",
                "metadata": {"camera_name": "Front Door"},
            }
        },
    )

    id: str = Field(..., description="Alert UUID")
    event_id: int = Field(..., description="Event ID that triggered this alert")
    rule_id: str | None = Field(None, description="Alert rule UUID that matched")
    severity: AlertSeverity = Field(..., description="Alert severity level")
    status: AlertStatus = Field(..., description="Alert status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    delivered_at: datetime | None = Field(None, description="Delivery timestamp")
    channels: list[str] = Field(default_factory=list, description="Notification channels")
    dedup_key: str = Field(..., description="Deduplication key")
    # Maps from model's alert_metadata attribute to API's metadata field
    metadata: dict | None = Field(
        None,
        description="Additional context",
        validation_alias="alert_metadata",
    )


class AlertListResponse(BaseModel):
    """Schema for alert list response with pagination."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440001",
                        "event_id": 123,
                        "rule_id": "550e8400-e29b-41d4-a716-446655440000",
                        "severity": "high",
                        "status": "delivered",
                        "created_at": "2025-12-28T12:00:00Z",
                        "updated_at": "2025-12-28T12:01:00Z",
                        "delivered_at": "2025-12-28T12:00:30Z",
                        "channels": ["pushover"],
                        "dedup_key": "front_door:person:entry_zone",
                        "metadata": {},
                    }
                ],
                "pagination": {
                    "total": 1,
                    "limit": 50,
                    "offset": 0,
                    "cursor": None,
                    "next_cursor": None,
                    "has_more": False,
                },
            }
        }
    )

    items: list[AlertResponse] = Field(..., description="List of alerts")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")


# =============================================================================
# Deduplication Schemas
# =============================================================================


class DedupCheckRequest(BaseModel):
    """Schema for checking alert deduplication."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "dedup_key": "front_door:person:entry_zone",
                "cooldown_seconds": 300,
            }
        }
    )

    dedup_key: DedupKeyStr = Field(
        ...,
        max_length=255,
        description="Deduplication key to check. "
        "Only alphanumeric, underscore, hyphen, and colon characters allowed.",
    )
    cooldown_seconds: int = Field(300, ge=0, description="Cooldown window in seconds")


class DedupCheckResponse(BaseModel):
    """Schema for deduplication check response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "is_duplicate": True,
                "existing_alert_id": "550e8400-e29b-41d4-a716-446655440001",
                "seconds_until_cooldown_expires": 180,
            }
        }
    )

    is_duplicate: bool = Field(..., description="Whether a duplicate exists")
    existing_alert_id: str | None = Field(None, description="ID of existing alert if duplicate")
    seconds_until_cooldown_expires: int | None = Field(
        None, description="Seconds until cooldown expires (if duplicate)"
    )


# =============================================================================
# Rule Testing Schemas
# =============================================================================


class RuleTestRequest(BaseModel):
    """Schema for testing a rule against historical events."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_ids": [1, 2, 3, 4, 5],
                "test_time": "2025-12-28T22:30:00Z",
            }
        }
    )

    event_ids: list[int] | None = Field(
        None,
        description="Specific event IDs to test against. If not provided, tests against recent events.",
    )
    limit: int = Field(
        10,
        ge=1,
        le=100,
        description="Maximum number of recent events to test (if event_ids not provided)",
    )
    test_time: datetime | None = Field(
        None,
        description="Override current time for schedule testing (ISO format)",
    )


class RuleTestEventResult(BaseModel):
    """Schema for a single event's test result."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_id": 123,
                "camera_id": "front_door",
                "risk_score": 75,
                "object_types": ["person"],
                "matches": True,
                "matched_conditions": ["risk_score >= 70", "object_type in ['person']"],
                "started_at": "2025-12-28T22:15:00Z",
            }
        }
    )

    event_id: int = Field(..., description="Event ID")
    camera_id: str = Field(..., description="Camera ID")
    risk_score: int | None = Field(None, description="Event risk score")
    object_types: list[str] = Field(default_factory=list, description="Detected object types")
    matches: bool = Field(..., description="Whether the rule matched this event")
    matched_conditions: list[str] = Field(
        default_factory=list, description="List of conditions that matched"
    )
    started_at: str | None = Field(None, description="Event start timestamp")


class RuleTestResponse(BaseModel):
    """Schema for rule test response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "rule_id": "550e8400-e29b-41d4-a716-446655440000",
                "rule_name": "Night Intruder Alert",
                "events_tested": 10,
                "events_matched": 3,
                "match_rate": 0.3,
                "results": [
                    {
                        "event_id": 123,
                        "camera_id": "front_door",
                        "risk_score": 75,
                        "object_types": ["person"],
                        "matches": True,
                        "matched_conditions": ["risk_score >= 70", "object_type in ['person']"],
                        "started_at": "2025-12-28T22:15:00Z",
                    }
                ],
            }
        }
    )

    rule_id: str = Field(..., description="Rule ID that was tested")
    rule_name: str = Field(..., description="Rule name")
    events_tested: int = Field(..., description="Number of events tested")
    events_matched: int = Field(..., description="Number of events that matched the rule")
    match_rate: float = Field(..., description="Proportion of events that matched (0.0-1.0)")
    results: list[RuleTestEventResult] = Field(..., description="Per-event test results")
