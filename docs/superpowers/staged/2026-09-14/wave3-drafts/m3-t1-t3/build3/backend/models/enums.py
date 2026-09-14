"""Enumeration types for home security intelligence system."""

from enum import Enum


class CameraStatus(str, Enum):
    """Camera status values.

    Indicates the operational state of a camera:
    - ONLINE: Camera is active and receiving images
    - OFFLINE: Camera is not currently active (e.g., disconnected)
    - ERROR: Camera is experiencing an error condition
    - UNKNOWN: Camera status cannot be determined
    """

    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    UNKNOWN = "unknown"

    def __str__(self) -> str:
        """Return string representation of camera status."""
        return self.value


class EntityType(str, Enum):
    """Entity types for re-identification tracking.

    Categorizes tracked entities for person/object re-identification:
    - PERSON: Human individuals tracked across cameras
    - VEHICLE: Cars, trucks, motorcycles, bicycles
    - ANIMAL: Pets and wildlife
    - PACKAGE: Delivered packages or parcels
    - OTHER: Unclassified tracked objects
    """

    PERSON = "person"
    VEHICLE = "vehicle"
    ANIMAL = "animal"
    PACKAGE = "package"
    OTHER = "other"

    def __str__(self) -> str:
        """Return string representation of entity type."""
        return self.value


class TrustStatus(str, Enum):
    """Trust status for tracked entities.

    Indicates the trust level of a tracked entity:
    - TRUSTED: Known/recognized entity (e.g., household member, family vehicle)
    - UNTRUSTED: Explicitly flagged as suspicious/unwanted entity
    - UNKNOWN: Entity has not been classified (default)
    """

    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"
    UNKNOWN = "unknown"

    def __str__(self) -> str:
        """Return string representation of trust status."""
        return self.value


class Severity(str, Enum):
    """Severity levels for security events.

    Severity is determined by mapping risk scores (0-100) to these levels:
    - LOW: Routine activity, no concern (default: 0-29)
    - MEDIUM: Notable activity, worth reviewing (default: 30-59)
    - HIGH: Concerning activity, review soon (default: 60-84)
    - CRITICAL: Immediate attention required (default: 85-100)

    The thresholds are configurable via settings:
    - SEVERITY_LOW_MAX (default: 29)
    - SEVERITY_MEDIUM_MAX (default: 59)
    - SEVERITY_HIGH_MAX (default: 84)
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    def __str__(self) -> str:
        """Return string representation of severity."""
        return self.value


class IngestionMode(str, Enum):
    """Camera ingestion mode - how images are acquired.

    NEM-4191: Defines the method used to acquire images from cameras:
    - FTP: Traditional FTP-based image uploads from cameras
    - RTSP: Real-Time Streaming Protocol for live video streams
    - ONVIF: Open Network Video Interface Forum standard for IP cameras
    """

    FTP = "ftp"
    RTSP = "rtsp"
    ONVIF = "onvif"

    def __str__(self) -> str:
        """Return string representation of ingestion mode."""
        return self.value


class StreamProfile(str, Enum):
    """Camera stream profile for RTSP/ONVIF cameras.

    NEM-4191: Defines which video stream profile to use:
    - MAIN: High resolution, primary stream (typically 1080p or higher)
    - SUB: Lower resolution, secondary stream for preview/thumbnails
    - BOTH: Use both main and sub streams
    """

    MAIN = "main"
    SUB = "sub"
    BOTH = "both"

    def __str__(self) -> str:
        """Return string representation of stream profile."""
        return self.value
