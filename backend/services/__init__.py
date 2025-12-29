"""Business logic and background services."""

from .alert_dedup import AlertDeduplicationService, DedupResult, build_dedup_key
from .alert_engine import AlertRuleEngine, EvaluationResult, TriggeredRule, get_alert_engine
from .audit import AuditService, audit_service
from .baseline import BaselineService, get_baseline_service, reset_baseline_service
from .batch_aggregator import BatchAggregator
from .cleanup_service import CleanupService, CleanupStats
from .clip_generator import (
    ClipGenerationError,
    ClipGenerator,
    get_clip_generator,
    reset_clip_generator,
)
from .dedupe import DedupeService, compute_file_hash, get_dedupe_service, reset_dedupe_service
from .detector_client import DetectorClient
from .event_broadcaster import EventBroadcaster, get_broadcaster, stop_broadcaster
from .file_watcher import FileWatcher, is_image_file, is_valid_image
from .gpu_monitor import GPUMonitor
from .nemotron_analyzer import NemotronAnalyzer
from .notification import (
    DeliveryResult,
    NotificationChannel,
    NotificationDelivery,
    NotificationService,
    get_notification_service,
    reset_notification_service,
)
from .retry_handler import (
    DLQStats,
    JobFailure,
    RetryConfig,
    RetryHandler,
    RetryResult,
    get_retry_handler,
    reset_retry_handler,
)
from .search import (
    SearchFilters,
    SearchResponse,
    SearchResult,
    refresh_event_search_vector,
    search_events,
    update_event_object_types,
)
from .severity import (
    SEVERITY_COLORS,
    SEVERITY_PRIORITY,
    SeverityDefinition,
    SeverityService,
    get_severity_color,
    get_severity_priority,
    get_severity_service,
    reset_severity_service,
    severity_from_string,
    severity_gt,
    severity_gte,
    severity_lt,
    severity_lte,
)
from .thumbnail_generator import ThumbnailGenerator
from .zone_service import (
    bbox_center,
    detection_in_zone,
    get_highest_priority_zone,
    get_zones_for_detection,
    point_in_zone,
    zones_to_context,
)

__all__ = [
    "SEVERITY_COLORS",
    "SEVERITY_PRIORITY",
    "AlertDeduplicationService",
    "AlertRuleEngine",
    "AuditService",
    "BaselineService",
    "BatchAggregator",
    "CleanupService",
    "CleanupStats",
    "ClipGenerationError",
    "ClipGenerator",
    "DLQStats",
    "DedupResult",
    "DedupeService",
    "DeliveryResult",
    "DetectorClient",
    "EvaluationResult",
    "EventBroadcaster",
    "FileWatcher",
    "GPUMonitor",
    "JobFailure",
    "NemotronAnalyzer",
    "NotificationChannel",
    "NotificationDelivery",
    "NotificationService",
    "RetryConfig",
    "RetryHandler",
    "RetryResult",
    "SearchFilters",
    "SearchResponse",
    "SearchResult",
    "SeverityDefinition",
    "SeverityService",
    "ThumbnailGenerator",
    "TriggeredRule",
    "audit_service",
    "bbox_center",
    "build_dedup_key",
    "compute_file_hash",
    "detection_in_zone",
    "get_alert_engine",
    "get_baseline_service",
    "get_broadcaster",
    "get_clip_generator",
    "get_dedupe_service",
    "get_highest_priority_zone",
    "get_notification_service",
    "get_retry_handler",
    "get_severity_color",
    "get_severity_priority",
    "get_severity_service",
    "get_zones_for_detection",
    "is_image_file",
    "is_valid_image",
    "point_in_zone",
    "refresh_event_search_vector",
    "reset_baseline_service",
    "reset_clip_generator",
    "reset_dedupe_service",
    "reset_notification_service",
    "reset_retry_handler",
    "reset_severity_service",
    "search_events",
    "severity_from_string",
    "severity_gt",
    "severity_gte",
    "severity_lt",
    "severity_lte",
    "stop_broadcaster",
    "update_event_object_types",
    "zones_to_context",
]
