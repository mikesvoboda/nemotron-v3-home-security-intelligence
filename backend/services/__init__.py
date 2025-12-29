"""Business logic and background services."""

from .batch_aggregator import BatchAggregator
from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerRegistry,
    CircuitState,
    get_circuit_breaker,
    reset_circuit_breaker_registry,
)
from .cleanup_service import CleanupService, CleanupStats
from .dedupe import DedupeService, compute_file_hash, get_dedupe_service, reset_dedupe_service
from .degradation_manager import (
    DegradationManager,
    DegradationMode,
    QueuedJob,
    ServiceHealth,
    ServiceStatus,
    get_degradation_manager,
    reset_degradation_manager,
)
from .detector_client import DetectorClient, DetectorUnavailableError
from .event_broadcaster import EventBroadcaster, get_broadcaster, stop_broadcaster
from .file_watcher import FileWatcher, is_image_file, is_valid_image
from .gpu_monitor import GPUMonitor
from .nemotron_analyzer import NemotronAnalyzer
from .retry_handler import (
    DLQStats,
    JobFailure,
    RetryConfig,
    RetryHandler,
    RetryResult,
    get_retry_handler,
    reset_retry_handler,
)
from .thumbnail_generator import ThumbnailGenerator

__all__ = [
    "BatchAggregator",
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerError",
    "CircuitBreakerRegistry",
    "CircuitState",
    "CleanupService",
    "CleanupStats",
    "DLQStats",
    "DedupeService",
    "DegradationManager",
    "DegradationMode",
    "DetectorClient",
    "DetectorUnavailableError",
    "EventBroadcaster",
    "FileWatcher",
    "GPUMonitor",
    "JobFailure",
    "NemotronAnalyzer",
    "QueuedJob",
    "RetryConfig",
    "RetryHandler",
    "RetryResult",
    "ServiceHealth",
    "ServiceStatus",
    "ThumbnailGenerator",
    "compute_file_hash",
    "get_broadcaster",
    "get_circuit_breaker",
    "get_dedupe_service",
    "get_degradation_manager",
    "get_retry_handler",
    "is_image_file",
    "is_valid_image",
    "reset_circuit_breaker_registry",
    "reset_dedupe_service",
    "reset_degradation_manager",
    "reset_retry_handler",
    "stop_broadcaster",
]
