"""SQLAlchemy models for home security intelligence system."""

from .alert import Alert, AlertRule, AlertSeverity, AlertStatus
from .area import Area, camera_areas
from .audit import AuditAction, AuditLog, AuditStatus
from .baseline import ActivityBaseline, ClassBaseline
from .camera import Base, Camera
from .camera_calibration import CameraCalibration
from .camera_zone import (
    CameraZone,
    CameraZoneShape,
    CameraZoneType,
    Zone,
    ZoneShape,
    ZoneType,
)
from .detection import Detection
from .enrichment import (
    ActionResult,
    DemographicsResult,
    PoseResult,
    ReIDEmbedding,
    ThreatDetection,
)
from .entity import Entity
from .enums import CameraStatus, EntityType, Severity, TrustStatus
from .event import Event
from .event_audit import EventAudit
from .event_detection import EventDetection, event_detections
from .event_feedback import EventFeedback, FeedbackType
from .experiment_result import ExperimentResult
from .export_job import ExportJob, ExportJobStatus, ExportType
from .gpu_stats import GPUStats
from .household import (
    HouseholdMember,
    MemberRole,
    PersonEmbedding,
    RegisteredVehicle,
    TrustLevel,
    VehicleType,
)
from .household_org import Household
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
from .prometheus_alert import PrometheusAlert, PrometheusAlertStatus
from .prompt_config import PromptConfig
from .property import Property
from .scene_change import SceneChange, SceneChangeType
from .summary import Summary, SummaryType
from .user_calibration import UserCalibration

__all__ = [
    "ActionResult",
    "ActivityBaseline",
    "Alert",
    "AlertRule",
    "AlertSeverity",
    "AlertStatus",
    "Area",
    "AuditAction",
    "AuditLog",
    "AuditStatus",
    "Base",
    "Camera",
    "CameraCalibration",
    "CameraNotificationSetting",
    "CameraStatus",
    "CameraZone",
    "CameraZoneShape",
    "CameraZoneType",
    "ClassBaseline",
    "DayOfWeek",
    "DemographicsResult",
    "Detection",
    "Entity",
    "EntityType",
    "Event",
    "EventAudit",
    "EventDetection",
    "EventFeedback",
    "ExperimentResult",
    "ExportJob",
    "ExportJobStatus",
    "ExportType",
    "FeedbackType",
    "GPUStats",
    "Household",
    "HouseholdMember",
    "Job",
    "JobAttempt",
    "JobAttemptStatus",
    "JobLog",
    "JobStatus",
    "JobTransition",
    "JobTransitionTrigger",
    "Log",
    "LogLevel",
    "MemberRole",
    "NotificationPreferences",
    "NotificationSound",
    "PersonEmbedding",
    "PoseResult",
    "PrometheusAlert",
    "PrometheusAlertStatus",
    "PromptConfig",
    "Property",
    "QuietHoursPeriod",
    "ReIDEmbedding",
    "RegisteredVehicle",
    "RiskLevel",
    "SceneChange",
    "SceneChangeType",
    "Severity",
    "Summary",
    "SummaryType",
    "ThreatDetection",
    "TrustLevel",
    "TrustStatus",
    "UserCalibration",
    "VehicleType",
    "Zone",
    "ZoneShape",
    "ZoneType",
    "camera_areas",
    "event_detections",
]
