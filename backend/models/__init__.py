"""SQLAlchemy models for home security intelligence system."""

from .alert import Alert, AlertRule, AlertSeverity, AlertStatus
from .analytics_zone import LineZone, PolygonZone
from .area import Area, camera_areas
from .audit import AuditAction, AuditLog, AuditStatus
from .backup_job import BackupJob, BackupJobStatus, RestoreJob, RestoreJobStatus
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
from .dwell_time import DwellTimeRecord
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
from .gpu_config import (
    GpuAssignmentStrategy,
    GpuConfiguration,
    GpuDevice,
    SystemSetting,
)
from .gpu_stats import GPUStats
from .heatmap import HeatmapData, HeatmapResolution
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
from .outbound_webhook import (
    IntegrationType,
    OutboundWebhook,
    WebhookDelivery,
    WebhookDeliveryStatus,
    WebhookEventType,
)
from .prometheus_alert import PrometheusAlert, PrometheusAlertStatus
from .prompt_config import PromptConfig
from .property import Property
from .scene_change import SceneChange, SceneChangeType
from .scheduled_report import ReportFormat, ReportFrequency, ScheduledReport
from .summary import Summary, SummaryType
from .track import Track
from .user_calibration import UserCalibration
from .zone_anomaly import AnomalySeverity, AnomalyType, ZoneAnomaly
from .zone_baseline import ZoneActivityBaseline
from .zone_household_config import ZoneHouseholdConfig

__all__ = [
    "ActionResult",
    "ActivityBaseline",
    "Alert",
    "AlertRule",
    "AlertSeverity",
    "AlertStatus",
    "AnomalySeverity",
    "AnomalyType",
    "Area",
    "AuditAction",
    "AuditLog",
    "AuditStatus",
    "BackupJob",
    "BackupJobStatus",
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
    "DwellTimeRecord",
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
    "GpuAssignmentStrategy",
    "GpuConfiguration",
    "GpuDevice",
    "HeatmapData",
    "HeatmapResolution",
    "Household",
    "HouseholdMember",
    "IntegrationType",
    "Job",
    "JobAttempt",
    "JobAttemptStatus",
    "JobLog",
    "JobStatus",
    "JobTransition",
    "JobTransitionTrigger",
    "LineZone",
    "Log",
    "LogLevel",
    "MemberRole",
    "NotificationPreferences",
    "NotificationSound",
    "OutboundWebhook",
    "PersonEmbedding",
    "PolygonZone",
    "PoseResult",
    "PrometheusAlert",
    "PrometheusAlertStatus",
    "PromptConfig",
    "Property",
    "QuietHoursPeriod",
    "ReIDEmbedding",
    "RegisteredVehicle",
    "ReportFormat",
    "ReportFrequency",
    "RestoreJob",
    "RestoreJobStatus",
    "RiskLevel",
    "SceneChange",
    "SceneChangeType",
    "ScheduledReport",
    "Severity",
    "Summary",
    "SummaryType",
    "SystemSetting",
    "ThreatDetection",
    "Track",
    "TrustLevel",
    "TrustStatus",
    "UserCalibration",
    "VehicleType",
    "WebhookDelivery",
    "WebhookDeliveryStatus",
    "WebhookEventType",
    "Zone",
    "ZoneActivityBaseline",
    "ZoneAnomaly",
    "ZoneHouseholdConfig",
    "ZoneShape",
    "ZoneType",
    "camera_areas",
    "event_detections",
]
