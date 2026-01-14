"""SQLAlchemy models for home security intelligence system."""

from .alert import Alert, AlertRule, AlertSeverity, AlertStatus
from .audit import AuditAction, AuditLog, AuditStatus
from .baseline import ActivityBaseline, ClassBaseline
from .camera import Base, Camera
from .detection import Detection
from .entity import Entity
from .enums import CameraStatus, EntityType, Severity
from .event import Event
from .event_audit import EventAudit
from .event_detection import EventDetection, event_detections
from .event_feedback import EventFeedback, FeedbackType
from .export_job import ExportJob, ExportJobStatus, ExportType
from .gpu_stats import GPUStats
from .job import Job, JobStatus
from .job_attempt import JobAttempt, JobAttemptStatus
from .job_log import JobLog, LogLevel
from .job_transition import JobTransition, JobTransitionTrigger
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
    "ExportJob",
    "ExportJobStatus",
    "ExportType",
    "FeedbackType",
    "GPUStats",
    "Job",
    "JobAttempt",
    "JobAttemptStatus",
    "JobLog",
    "JobStatus",
    "JobTransition",
    "JobTransitionTrigger",
    "Log",
    "LogLevel",
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
