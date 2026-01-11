"""SQLAlchemy models for home security intelligence system."""

from .alert import Alert, AlertRule, AlertSeverity, AlertStatus
from .api_key import APIKey
from .audit import AuditAction, AuditLog, AuditStatus
from .baseline import ActivityBaseline, ClassBaseline
from .camera import Base, Camera
from .detection import Detection
from .entity import Entity, EntityType
from .enums import CameraStatus, Severity
from .event import Event
from .event_audit import EventAudit
from .event_detection import EventDetection, event_detections
from .event_feedback import EventFeedback, FeedbackType
from .gpu_stats import GPUStats
from .log import Log
from .notification_preferences import (
    CameraNotificationSetting,
    DayOfWeek,
    NotificationPreferences,
    NotificationSound,
    QuietHoursPeriod,
    RiskLevel,
)
from .prompt_config import PromptConfig
from .scene_change import SceneChange, SceneChangeType
from .user_calibration import UserCalibration
from .zone import Zone, ZoneShape, ZoneType

__all__ = [
    "APIKey",
    "ActivityBaseline",
    "Alert",
    "AlertRule",
    "AlertSeverity",
    "AlertStatus",
    "AuditAction",
    "AuditLog",
    "AuditStatus",
    "Base",
    "Camera",
    "CameraNotificationSetting",
    "CameraStatus",
    "ClassBaseline",
    "DayOfWeek",
    "Detection",
    "Entity",
    "EntityType",
    "Event",
    "EventAudit",
    "EventDetection",
    "EventFeedback",
    "FeedbackType",
    "GPUStats",
    "Log",
    "NotificationPreferences",
    "NotificationSound",
    "PromptConfig",
    "QuietHoursPeriod",
    "RiskLevel",
    "SceneChange",
    "SceneChangeType",
    "Severity",
    "UserCalibration",
    "Zone",
    "ZoneShape",
    "ZoneType",
    "event_detections",
]
