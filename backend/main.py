"""FastAPI application entry point for home security intelligence system.

This module provides:
- FastAPI application configuration with middleware and routes
- Application lifespan management (startup/shutdown)
- Signal handling for graceful shutdown (SIGTERM/SIGINT)
- Health check endpoints for container orchestration
"""

import asyncio
import pathlib
import signal
import ssl
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Any

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.routing import APIRoute

from backend.api.exception_handlers import register_exception_handlers
from backend.api.middleware import (
    AuthMiddleware,
    BaggageMiddleware,
    BodySizeLimitMiddleware,
    ContentTypeValidationMiddleware,
    DeprecationConfig,
    DeprecationLoggerMiddleware,
    DeprecationMiddleware,
    IdempotencyMiddleware,
    RequestLoggingMiddleware,
    RequestRecorderMiddleware,
    RequestTimingMiddleware,
    SecurityHeadersMiddleware,
)
from backend.api.middleware.request_id import RequestIDMiddleware
from backend.api.routes import (
    admin,
    ai_audit,
    alertmanager,
    alerts,
    analytics,
    audit,
    calibration,
    cameras,
    debug,
    detections,
    dlq,
    entities,
    events,
    exports,
    feedback,
    gpu_config,
    health_ai_services,
    hierarchy,
    household,
    jobs,
    logs,
    media,
    metrics,
    notification,
    notification_preferences,
    outbound_webhooks,
    prompt_management,
    queues,
    rum,
    scheduled_reports,
    services,
    settings_api,
    summaries,
    system,
    system_settings,
    tracks,
    webhooks,
    websocket,
    zone_anomalies,
    zone_household,
    zones,
)
from backend.api.routes.system import register_workers
from backend.core import close_db, get_container, get_settings, init_db, wire_services
from backend.core.config_validation import log_config_summary, validate_config
from backend.core.database import warm_connection_pool
from backend.core.docker_client import DockerClient
from backend.core.free_threading import get_threading_mode, verify_free_threading
from backend.core.logging import enable_deferred_db_logging, redact_url, setup_logging
from backend.core.redis import close_redis, init_redis
from backend.core.telemetry import init_profiling, setup_telemetry, shutdown_telemetry
from backend.jobs.summary_job import (
    SummaryJobScheduler,
    get_summary_job_scheduler,
    reset_summary_job_scheduler,
)
from backend.models.camera import Camera
from backend.models.enums import CameraStatus
from backend.services.background_evaluator import BackgroundEvaluator
from backend.services.circuit_breaker import CircuitBreakerConfig, get_circuit_breaker
from backend.services.cleanup_service import CleanupService
from backend.services.container_orchestrator import ContainerOrchestrator
from backend.services.evaluation_queue import get_evaluation_queue
from backend.services.event_broadcaster import get_broadcaster, stop_broadcaster
from backend.services.file_watcher import FileWatcher
from backend.services.gpu_monitor import GPUMonitor
from backend.services.health_monitor import ServiceHealthMonitor
from backend.services.job_tracker import init_job_tracker_websocket
from backend.services.performance_collector import PerformanceCollector
from backend.services.pipeline_quality_audit_service import get_audit_service
from backend.services.pipeline_workers import (
    create_analysis_worker,
    create_detection_worker,
    create_metrics_worker,
    create_timeout_worker,
    drain_queues,
    get_pipeline_manager,
    stop_pipeline_manager,
)
from backend.services.service_managers import ServiceConfig, ShellServiceManager
from backend.services.system_broadcaster import get_system_broadcaster, stop_system_broadcaster
from backend.services.worker_supervisor import (
    SupervisorConfig,
    get_worker_supervisor,
    reset_worker_supervisor,
)

# Graceful shutdown event - set when SIGTERM/SIGINT is received
# This allows the lifespan context to coordinate shutdown with signal handlers
_shutdown_event: asyncio.Event | None = None

# Track whether signal handlers have been installed (prevents double-installation)
_signal_handlers_installed: bool = False


def get_shutdown_event() -> asyncio.Event:
    """Get the global shutdown event, creating it if necessary.

    The shutdown event is used to coordinate graceful shutdown between
    signal handlers and the FastAPI lifespan context. When a signal is
    received, the event is set, allowing async code to detect the shutdown
    request and clean up appropriately.

    Returns:
        asyncio.Event that is set when shutdown is requested
    """
    global _shutdown_event  # noqa: PLW0603
    if _shutdown_event is None:
        _shutdown_event = asyncio.Event()
    return _shutdown_event


def install_signal_handlers() -> None:
    """Install signal handlers for graceful shutdown.

    Registers handlers for SIGTERM and SIGINT that:
    1. Log the received signal
    2. Set the shutdown event for coordination

    This function is idempotent - calling it multiple times is safe.
    Signal handlers are only installed when running in the main thread
    and when the event loop supports add_signal_handler (not on Windows).

    Note: Uvicorn already handles signals and triggers lifespan shutdown,
    so our handlers primarily add logging and coordination capabilities.
    """
    global _signal_handlers_installed  # noqa: PLW0603

    if _signal_handlers_installed:
        return

    from backend.core.logging import get_logger

    logger = get_logger(__name__)

    try:
        loop = asyncio.get_running_loop()
        shutdown_event = get_shutdown_event()

        def create_signal_handler(sig: signal.Signals) -> None:
            def handler() -> None:
                logger.info(
                    f"Received {sig.name}, initiating graceful shutdown...",
                    extra={"signal": sig.name, "signal_number": sig.value},
                )
                shutdown_event.set()

            loop.add_signal_handler(sig, handler)

        # Register handlers for common termination signals
        create_signal_handler(signal.SIGTERM)
        create_signal_handler(signal.SIGINT)

        _signal_handlers_installed = True
        logger.info(
            "Signal handlers installed for SIGTERM and SIGINT",
            extra={"handlers": ["SIGTERM", "SIGINT"]},
        )

    except NotImplementedError:
        # Signal handlers not supported on Windows with ProactorEventLoop
        logger.debug("Signal handlers not supported on this platform")
    except RuntimeError as e:
        # Not running in the main thread or no event loop
        logger.debug(f"Could not install signal handlers: {e}")


def reset_signal_handlers() -> None:
    """Reset signal handler state for testing.

    This function is NOT thread-safe and should only be used in test
    fixtures to ensure clean state between tests.

    Warning: Only use this in test teardown, never in production code.
    """
    global _shutdown_event, _signal_handlers_installed  # noqa: PLW0603
    _shutdown_event = None
    _signal_handlers_installed = False


async def create_camera_callback(camera: Camera) -> None:
    """Callback to create a camera in the database (used by FileWatcher auto-create).

    This callback is invoked when FileWatcher detects a new camera directory
    and needs to create a corresponding Camera record in the database.
    Uses get_or_create semantics to avoid duplicate camera errors.

    Args:
        camera: Camera instance to create (with id, name, folder_path populated)
    """
    from sqlalchemy import select

    from backend.core.database import get_session
    from backend.core.logging import get_logger

    logger = get_logger(__name__)

    async with get_session() as session:
        # Check if camera already exists (by id or folder_path)
        result = await session.execute(
            select(Camera).where(
                (Camera.id == camera.id) | (Camera.folder_path == camera.folder_path)
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            logger.debug(f"Camera already exists: {existing.id} (folder: {existing.folder_path})")
            return

        # Create new camera
        session.add(camera)
        await session.commit()
        logger.info(
            f"Auto-created camera: {camera.id} ({camera.name})",
            extra={"camera_id": camera.id, "folder_path": camera.folder_path},
        )


def init_circuit_breakers() -> list[str]:
    """Pre-register circuit breakers for known external services.

    This function initializes circuit breakers at startup for all known
    external services that the application depends on. This ensures the
    circuit breakers appear in the monitoring UI even before they are first used.

    Pre-registered circuit breakers:
    - yolo26: YOLO26 object detection service
    - nemotron: Nemotron LLM risk analysis service
    - postgresql: Database connection pool
    - redis: Redis cache and queue service

    Returns:
        List of circuit breaker names that were pre-registered
    """
    # Configuration for AI services - more aggressive (quick failure detection)
    ai_service_config = CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=30.0,
        half_open_max_calls=3,
        success_threshold=2,
    )

    # Configuration for infrastructure services - more tolerant
    infrastructure_config = CircuitBreakerConfig(
        failure_threshold=10,
        recovery_timeout=60.0,
        half_open_max_calls=5,
        success_threshold=3,
    )

    # Pre-register circuit breakers
    breaker_names = []

    # AI services
    get_circuit_breaker("yolo26", ai_service_config)
    breaker_names.append("yolo26")

    get_circuit_breaker("nemotron", ai_service_config)
    breaker_names.append("nemotron")

    # Infrastructure services
    get_circuit_breaker("postgresql", infrastructure_config)
    breaker_names.append("postgresql")

    get_circuit_breaker("redis", infrastructure_config)
    breaker_names.append("redis")

    return breaker_names


def _directory_has_images(folder: pathlib.Path) -> bool:
    """Check if a directory contains any image files (recursively).

    This is used to filter out empty camera directories during seeding.
    Only cameras with actual image data should be seeded.

    Args:
        folder: Path to the camera directory

    Returns:
        True if directory contains at least one image file
    """
    # Supported image extensions (case-insensitive via glob)
    # Use rglob for recursive search (cameras may have date subdirectories)
    image_patterns = ["*.jpg", "*.JPG", "*.jpeg", "*.JPEG", "*.png", "*.PNG"]
    return any(any(folder.rglob(pattern)) for pattern in image_patterns)


async def seed_cameras_if_empty() -> int:
    """Seed cameras from filesystem if database is empty.

    This function runs on startup to auto-discover and seed camera records
    from the configured foscam_base_path. Only seeds if no cameras exist
    in the database (safe for restarts).

    Only cameras with actual image data are seeded - empty directories are skipped.

    Returns:
        Number of cameras created (0 if database already had cameras)
    """
    from pathlib import Path

    from sqlalchemy import func, select

    from backend.core.database import get_session
    from backend.core.logging import get_logger
    from backend.models.camera import normalize_camera_id

    logger = get_logger(__name__)
    settings = get_settings()

    async with get_session() as session:
        # Check if cameras table is empty
        result = await session.execute(select(func.count(Camera.id)))
        count = result.scalar() or 0

        if count > 0:
            logger.debug(f"Database already has {count} cameras, skipping seed")
            return 0

        # Discover cameras from filesystem
        base_path = Path(settings.foscam_base_path)
        if not base_path.exists():
            logger.warning(f"Camera base path does not exist: {base_path}")
            return 0

        created = 0
        skipped = 0
        for folder in sorted(base_path.iterdir()):
            if folder.is_dir() and not folder.name.startswith("."):
                # Only seed cameras that have actual image data
                if not _directory_has_images(folder):
                    logger.debug(
                        f"Skipping empty camera directory: {folder.name}",
                        extra={"folder_path": str(folder)},
                    )
                    skipped += 1
                    continue

                camera_id = normalize_camera_id(folder.name)
                display_name = folder.name.replace("_", " ").title()

                camera = Camera(
                    id=camera_id,
                    name=display_name,
                    folder_path=str(folder),
                    status=CameraStatus.ONLINE.value,
                )
                session.add(camera)
                created += 1
                logger.info(
                    f"Seeded camera: {camera_id} ({display_name})",
                    extra={"camera_id": camera_id, "folder_path": str(folder)},
                )

        if created > 0:
            await session.commit()
            logger.info(
                f"Auto-seeded {created} cameras from {base_path} (skipped {skipped} empty directories)"
            )

        return created


async def validate_camera_paths_on_startup() -> tuple[int, int]:
    """Validate camera paths on startup and log any issues.

    This function checks all cameras in the database to ensure their folder_path
    is under the configured foscam_base_path. This catches configuration mismatches
    early (e.g., when FOSCAM_BASE_PATH changes between environments).

    Issues are logged once at startup rather than on every snapshot request,
    reducing log noise while still alerting administrators to problems.

    Returns:
        Tuple of (valid_count, invalid_count)
    """
    from pathlib import Path

    from sqlalchemy import select

    from backend.core.database import get_session
    from backend.core.logging import get_logger

    logger = get_logger(__name__)
    settings = get_settings()
    base_root = Path(settings.foscam_base_path).resolve()

    async with get_session() as session:
        result = await session.execute(select(Camera))
        cameras = result.scalars().all()

        if not cameras:
            return (0, 0)

        valid_count = 0
        invalid_cameras: list[tuple[str, str, str]] = []

        for camera in cameras:
            try:
                camera_dir = Path(camera.folder_path).resolve()
                camera_dir.relative_to(base_root)
                valid_count += 1
            except ValueError:
                invalid_cameras.append((camera.id, camera.name, camera.folder_path))

        invalid_count = len(invalid_cameras)

        if invalid_cameras:
            # Log a summary warning once at startup
            logger.warning(
                f"Found {invalid_count} camera(s) with folder_path outside "
                f"FOSCAM_BASE_PATH ({settings.foscam_base_path}). "
                f"Snapshots will be unavailable for these cameras. "
                f"Use GET /api/cameras/validation/paths for details.",
                extra={
                    "invalid_count": invalid_count,
                    "valid_count": valid_count,
                    "base_path": str(base_root),
                },
            )
            # Log each invalid camera at debug level for troubleshooting
            for cam_id, cam_name, cam_path in invalid_cameras:
                logger.debug(
                    f"Camera path mismatch: {cam_name} ({cam_id}) -> {cam_path}",
                    extra={"camera_id": cam_id, "folder_path": cam_path},
                )

        return (valid_count, invalid_count)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Manage application lifecycle - startup and shutdown events.

    This lifespan context manager handles:
    1. Startup: Initialize all services (database, Redis, workers, etc.)
    2. Signal handling: Install SIGTERM/SIGINT handlers for graceful shutdown
    3. Shutdown: Stop all services in proper order, clean up resources

    Signal Handling:
        SIGTERM and SIGINT handlers are installed during startup. When a signal
        is received, the handler logs the event and sets a shutdown event.
        Uvicorn will then trigger the lifespan shutdown sequence.

    Container Orchestration:
        - Docker/Podman: SIGTERM sent on `docker stop` (30s default grace period)
        - Kubernetes: SIGTERM sent on pod termination (30s default grace period)
        - The application should complete shutdown within the grace period
    """
    from backend.core.logging import get_logger

    # Initialize logging first (before any other initialization)
    setup_logging()
    lifespan_logger = get_logger(__name__)

    # Verify free-threaded Python is active (Python 3.14t with PYTHON_GIL=0)
    # This should fail fast if the container is misconfigured
    try:
        verify_free_threading()
        lifespan_logger.info(f"Python runtime: {get_threading_mode()}")
    except RuntimeError as e:
        lifespan_logger.warning(f"Free-threading verification: {e}")
        lifespan_logger.warning(
            "Continuing with GIL enabled - concurrent performance may be reduced"
        )

    # Install signal handlers for graceful shutdown (SIGTERM/SIGINT)
    # This must be done early, after the event loop is running
    install_signal_handlers()

    # Initialize Pyroscope continuous profiling (NEM-3103)
    # Must be done early to capture profiling data from the entire startup
    init_profiling()

    # Startup
    settings = get_settings()

    # Validate configuration and log summary (NEM-2026)
    # This provides visibility into configuration status at startup
    config_result = validate_config(settings)
    log_config_summary(config_result)
    if not config_result.valid:
        # Log critical errors but don't fail startup - let individual services fail gracefully
        lifespan_logger.warning(
            f"Configuration validation found {len(config_result.errors)} error(s). "
            "Check logs for details."
        )

    # Initialize OpenTelemetry tracing (NEM-1629)
    # Must be done early, before other services are initialized
    otel_initialized = setup_telemetry(_app, settings)
    if otel_initialized:
        lifespan_logger.info(
            f"OpenTelemetry tracing enabled: {settings.otel_service_name} -> "
            f"{settings.otel_exporter_otlp_endpoint}"
        )

    # Pre-register circuit breakers for known services
    # This ensures they appear in monitoring UI even before first use
    breaker_names = init_circuit_breakers()
    lifespan_logger.info(f"Circuit breakers initialized: {', '.join(breaker_names)}")

    await init_db()
    lifespan_logger.info(f"Database initialized: {redact_url(settings.database_url)}")

    # Warm connection pool to reduce cold-start latency (NEM-3757)
    # Pre-establishes database connections so first requests don't wait for TCP/TLS handshakes
    if settings.database_pool_warming_enabled:
        warming_result = await warm_connection_pool()
        if warming_result["success"]:
            lifespan_logger.info(
                f"Connection pool warmed: {warming_result['connections_warmed']} connections "
                f"in {warming_result['duration_ms']}ms"
            )
        elif warming_result["connections_warmed"] > 0:
            lifespan_logger.warning(
                f"Connection pool partially warmed: {warming_result['connections_warmed']}/"
                f"{warming_result['target_connections']} connections ({warming_result['error']})"
            )
        else:
            lifespan_logger.warning(f"Connection pool warming failed: {warming_result['error']}")

    # Re-enable database logging now that tables exist (NEM-2442)
    # This handles the case where logging was deferred because the logs table
    # didn't exist when setup_logging() was called on a fresh database
    enable_deferred_db_logging()

    # Auto-seed cameras from filesystem if database is empty
    seeded = await seed_cameras_if_empty()
    if seeded > 0:
        lifespan_logger.info(f"Auto-seeded {seeded} cameras from {settings.foscam_base_path}")

    # Validate camera paths against configured base path
    # This logs warnings once at startup for cameras with mismatched paths
    valid_count, invalid_count = await validate_camera_paths_on_startup()
    if invalid_count > 0:
        lifespan_logger.warning(
            f"Camera path validation: {valid_count} valid, {invalid_count} invalid "
            f"(see logs or GET /api/cameras/validation/paths)"
        )

    # Track whether Redis-dependent services were initialized
    redis_client = None
    file_watcher = None
    pipeline_manager = None

    try:
        redis_client = await init_redis()
        lifespan_logger.info(f"Redis initialized: {redact_url(settings.redis_url)}")

        # Wire up DI container with all application services (NEM-2003)
        # This must happen after Redis is initialized since some services depend on it
        container = get_container()
        await wire_services(container)
        lifespan_logger.info("DI container services wired")

        # Initialize and start event broadcaster for WebSocket real-time events
        # Note: get_broadcaster() both creates AND starts the broadcaster
        # (subscribes to Redis pub/sub channel)
        event_broadcaster = await get_broadcaster(redis_client)
        channel = event_broadcaster.channel_name
        lifespan_logger.info(f"Event broadcaster started, listening on channel: {channel}")

        # Initialize file watcher (monitors camera directories for new images)
        # Pass camera_creator callback to enable auto-creation of camera records
        file_watcher = FileWatcher(
            redis_client=redis_client,
            camera_creator=create_camera_callback,
        )
        await file_watcher.start()
        lifespan_logger.info(f"File watcher started: {settings.foscam_base_path}")

        # Initialize pipeline workers (detection queue, analysis queue, batch timeout)
        pipeline_manager = await get_pipeline_manager(redis_client)
        await pipeline_manager.start()
        lifespan_logger.info(
            "Pipeline workers started (detection, analysis, batch timeout, metrics)"
        )

        # Initialize WorkerSupervisor for automatic crash recovery (NEM-2460)
        # The supervisor monitors pipeline workers and restarts them if they crash
        async def on_worker_restart(name: str, attempt: int, error: str | None) -> None:
            """Log worker restart events."""
            lifespan_logger.warning(
                f"Worker '{name}' restarting (attempt {attempt}): {error or 'unknown error'}"
            )

        async def on_worker_failure(name: str, error: str | None) -> None:
            """Log worker failure events after max restarts exceeded."""
            lifespan_logger.error(
                f"Worker '{name}' FAILED - exceeded max restarts: {error or 'unknown error'}"
            )

        supervisor_config = SupervisorConfig(
            check_interval=settings.worker_supervisor_check_interval,
            default_max_restarts=settings.worker_supervisor_max_restarts,
        )
        worker_supervisor = get_worker_supervisor(
            config=supervisor_config,
            broadcaster=event_broadcaster,
            on_restart=on_worker_restart,
            on_failure=on_worker_failure,
        )

        # Register workers with the supervisor
        # Note: Workers are already managed by PipelineManager, but supervisor
        # provides additional monitoring and restart callbacks
        await worker_supervisor.register_worker(
            "detection",
            create_detection_worker(redis_client),
            max_restarts=settings.worker_supervisor_max_restarts,
        )
        await worker_supervisor.register_worker(
            "analysis",
            create_analysis_worker(redis_client),
            max_restarts=settings.worker_supervisor_max_restarts,
        )
        await worker_supervisor.register_worker(
            "batch_timeout",
            create_timeout_worker(redis_client),
            max_restarts=settings.worker_supervisor_max_restarts,
        )
        await worker_supervisor.register_worker(
            "metrics",
            create_metrics_worker(redis_client),
            max_restarts=settings.worker_supervisor_max_restarts,
        )

        await worker_supervisor.start()
        lifespan_logger.info(
            f"WorkerSupervisor started with {worker_supervisor.worker_count} workers"
        )

    except Exception as e:
        lifespan_logger.error(f"Redis connection failed: {e}")
        lifespan_logger.warning("Continuing without Redis - some features may be unavailable")

    # Initialize system broadcaster (runs independently of Redis, but uses it when available)
    # Pass the Redis client if it was successfully initialized
    system_broadcaster = get_system_broadcaster(redis_client=redis_client)
    await system_broadcaster.start_broadcasting(interval=5.0)
    lifespan_logger.info("System status broadcaster initialized (5s interval)")

    # Initialize job tracker with WebSocket broadcasting (NEM-2261)
    # This enables export progress updates to be sent to connected clients
    await init_job_tracker_websocket(redis_client=redis_client)
    lifespan_logger.info("Job tracker initialized with WebSocket broadcasting")

    # Initialize performance collector and attach to system broadcaster
    # This enables detailed performance metrics broadcasting alongside system status
    performance_collector = PerformanceCollector()
    system_broadcaster.set_performance_collector(performance_collector)
    lifespan_logger.info("Performance collector initialized and attached to system broadcaster")

    # Initialize GPU monitor
    # Note: broadcaster=None to avoid duplicate GPU stats broadcasts
    # (system_broadcaster already handles GPU stats in periodic status updates)
    gpu_monitor = GPUMonitor(broadcaster=None)
    await gpu_monitor.start()
    lifespan_logger.info("GPU monitor initialized")

    # Initialize cleanup service
    cleanup_service = CleanupService()
    await cleanup_service.start()
    lifespan_logger.info("Cleanup service initialized")

    # Initialize background evaluator for AI audit evaluation when GPU is idle
    # This processes pending evaluations automatically instead of requiring manual clicks
    background_evaluator: BackgroundEvaluator | None = None
    if redis_client is not None and settings.background_evaluation_enabled:
        evaluation_queue = get_evaluation_queue(redis_client)
        audit_service = get_audit_service()
        background_evaluator = BackgroundEvaluator(
            redis_client=redis_client,
            gpu_monitor=gpu_monitor,
            evaluation_queue=evaluation_queue,
            audit_service=audit_service,
            gpu_idle_threshold=settings.background_evaluation_gpu_idle_threshold,
            idle_duration_required=settings.background_evaluation_idle_duration,
            poll_interval=settings.background_evaluation_poll_interval,
            enabled=settings.background_evaluation_enabled,
        )
        await background_evaluator.start()
        lifespan_logger.info(
            f"Background evaluator initialized "
            f"(idle threshold: {settings.background_evaluation_gpu_idle_threshold}%, "
            f"idle duration: {settings.background_evaluation_idle_duration}s)"
        )

    # Initialize summary job scheduler for automatic dashboard summary generation (NEM-2891)
    # Generates hourly and daily summaries of high/critical events every 5 minutes
    # Uses DEFAULT_TIMEOUT_SECONDS (180s) to accommodate Nemotron LLM inference time
    summary_job_scheduler: SummaryJobScheduler | None = None
    if redis_client is not None:
        event_broadcaster = await get_broadcaster(redis_client)
        summary_job_scheduler = get_summary_job_scheduler(
            interval_minutes=5,
            redis_client=redis_client,
            broadcaster=event_broadcaster,
        )
        await summary_job_scheduler.start()
        lifespan_logger.info("Summary job scheduler started (5-minute interval)")

    # Initialize service health monitor for auto-recovery of AI services
    # Note: This monitors YOLO26 and Nemotron services for health and can trigger restarts
    # Redis is excluded since the application handles Redis failures gracefully already
    # Restart capability can be disabled via AI_RESTART_ENABLED=false for containerized deployments
    # where the restart scripts are not available inside the backend container
    service_health_monitor: ServiceHealthMonitor | None = None
    if redis_client is not None:
        # Set restart_cmd based on ai_restart_enabled setting
        # When disabled (e.g., in containers), health monitoring still works but no restart attempts
        yolo26_restart_cmd = "ai/start_detector.sh" if settings.ai_restart_enabled else None
        nemotron_restart_cmd = "ai/start_llm.sh" if settings.ai_restart_enabled else None

        service_configs = [
            ServiceConfig(
                name="yolo26",
                health_url=f"{settings.yolo26_url}/health",
                restart_cmd=yolo26_restart_cmd,
                health_timeout=5.0,
                max_retries=3,
                backoff_base=5.0,
            ),
            ServiceConfig(
                name="nemotron",
                health_url=f"{settings.nemotron_url}/health",
                restart_cmd=nemotron_restart_cmd,
                health_timeout=5.0,
                max_retries=3,
                backoff_base=5.0,
            ),
        ]
        service_manager = ShellServiceManager(subprocess_timeout=60.0)
        # Get event broadcaster for WebSocket status updates
        event_broadcaster = await get_broadcaster(redis_client)
        service_health_monitor = ServiceHealthMonitor(
            manager=service_manager,
            services=service_configs,
            broadcaster=event_broadcaster,
            check_interval=15.0,
        )
        await service_health_monitor.start()
        restart_status = (
            "enabled" if settings.ai_restart_enabled else "disabled (AI_RESTART_ENABLED=false)"
        )
        lifespan_logger.info(
            f"Service health monitor initialized (YOLO26, Nemotron) - restart: {restart_status}"
        )

    # Initialize container orchestrator (if enabled)
    # This provides health monitoring and self-healing for Docker/Podman containers
    container_orchestrator: ContainerOrchestrator | None = None
    docker_client: DockerClient | None = None

    if settings.orchestrator.enabled and redis_client:
        try:
            docker_client = DockerClient(settings.orchestrator.docker_host)

            # Get event broadcaster for WebSocket updates
            event_broadcaster = await get_broadcaster(redis_client)

            container_orchestrator = ContainerOrchestrator(
                docker_client=docker_client,
                redis_client=redis_client,
                settings=settings.orchestrator,
                broadcast_fn=event_broadcaster.broadcast_service_status,
            )

            # Store in app.state for route access
            _app.state.orchestrator = container_orchestrator

            await container_orchestrator.start()
            lifespan_logger.info("Container orchestrator started")
        except Exception as e:
            lifespan_logger.error(f"Container orchestrator initialization failed: {e}")
            lifespan_logger.warning("Continuing without orchestrator")

    # Register workers with health service registry (NEM-2611: dependency injection)
    # Get the registry from the DI container instead of using globals
    health_registry = container.get("health_service_registry")
    health_registry.register_gpu_monitor(gpu_monitor)
    health_registry.register_cleanup_service(cleanup_service)
    health_registry.register_system_broadcaster(system_broadcaster)
    if file_watcher is not None:
        health_registry.register_file_watcher(file_watcher)
    if pipeline_manager is not None:
        health_registry.register_pipeline_manager(pipeline_manager)
    if service_health_monitor is not None:
        health_registry.register_service_health_monitor(service_health_monitor)
    health_registry.register_performance_collector(performance_collector)

    # Also register with the legacy register_workers for backward compatibility
    # This will be removed once all routes are migrated to use the registry
    register_workers(
        gpu_monitor=gpu_monitor,
        cleanup_service=cleanup_service,
        system_broadcaster=system_broadcaster,
        file_watcher=file_watcher,
        pipeline_manager=pipeline_manager,
        service_health_monitor=service_health_monitor,
        performance_collector=performance_collector,
        worker_supervisor=get_worker_supervisor(),
    )
    lifespan_logger.info("Workers registered for readiness monitoring (DI + legacy)")

    yield

    # Shutdown
    # Stop container orchestrator first (before stopping docker client)
    if container_orchestrator is not None:
        await container_orchestrator.stop()
        lifespan_logger.info("Container orchestrator stopped")
    if docker_client is not None:
        await docker_client.close()
        lifespan_logger.info("Docker client closed")

    # Stop service health monitor (before stopping services it monitors)
    if service_health_monitor is not None:
        await service_health_monitor.stop()
        lifespan_logger.info("Service health monitor stopped")

    # Stop background evaluator (before GPU monitor since it depends on it)
    if background_evaluator is not None:
        await background_evaluator.stop()
        lifespan_logger.info("Background evaluator stopped")

    # Stop summary job scheduler
    if summary_job_scheduler is not None:
        await summary_job_scheduler.stop()
        lifespan_logger.info("Summary job scheduler stopped")
        reset_summary_job_scheduler()

    await cleanup_service.stop()
    lifespan_logger.info("Cleanup service stopped")
    await gpu_monitor.stop()
    lifespan_logger.info("GPU monitor stopped")

    # Stop WorkerSupervisor first to prevent restart attempts during shutdown (NEM-2460)
    worker_supervisor = get_worker_supervisor()
    await worker_supervisor.stop()
    lifespan_logger.info("WorkerSupervisor stopped")
    reset_worker_supervisor()

    # Drain queues gracefully before stopping workers (NEM-2006)
    # This ensures in-flight tasks complete and logs any tasks that couldn't finish
    remaining_tasks = await drain_queues(timeout=30.0)
    if remaining_tasks > 0:
        lifespan_logger.warning(f"Queue drain timeout: {remaining_tasks} tasks remaining")
    else:
        lifespan_logger.info("Queue drain completed successfully")

    # Stop pipeline workers (after queue draining)
    await stop_pipeline_manager()
    lifespan_logger.info("Pipeline workers stopped")

    # Stop file watcher
    if file_watcher:
        await file_watcher.stop()
        lifespan_logger.info("File watcher stopped")

    await stop_broadcaster()
    lifespan_logger.info("Event broadcaster stopped")
    await stop_system_broadcaster()
    lifespan_logger.info("System status broadcaster stopped")
    # Close performance collector (cleanup HTTP client and pynvml)
    await performance_collector.close()
    lifespan_logger.info("Performance collector closed")

    # Unload AI models from GPU memory (NEM-1996)
    # This prevents GPU memory leaks on shutdown and ensures clean restarts
    try:
        from backend.services.model_zoo import get_model_manager

        model_manager = get_model_manager()
        await model_manager.unload_all()
        lifespan_logger.info("AI models unloaded from GPU")
    except Exception as e:
        lifespan_logger.warning(f"Error unloading models: {e}")

    # Clear CUDA cache after model unload (NEM-2022)
    # Separated from model unloading for better error isolation
    # This ensures CUDA cleanup errors don't affect other shutdown steps
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.synchronize()  # Wait for all GPU operations to complete
            torch.cuda.empty_cache()  # Release cached memory back to GPU
            lifespan_logger.info("CUDA cache cleared")
        else:
            lifespan_logger.debug("CUDA not available, skipping cache clear")
    except ImportError:
        lifespan_logger.debug("torch not installed, skipping CUDA cleanup")
    except Exception as e:
        # Log but don't prevent shutdown - CUDA cleanup is best-effort
        lifespan_logger.warning(f"Error clearing CUDA cache: {e}")

    # Shutdown DI container services (NEM-2003)
    # This gracefully closes all services that have close() or disconnect() methods
    try:
        di_container = get_container()
        await di_container.shutdown()
        lifespan_logger.info("DI container services shut down")
    except Exception as e:
        lifespan_logger.warning(f"Error shutting down DI container: {e}")

    await close_db()
    lifespan_logger.info("Database connections closed")
    await close_redis()
    lifespan_logger.info("Redis connection closed")

    # Shutdown OpenTelemetry (flushes pending traces)
    shutdown_telemetry()
    lifespan_logger.info("OpenTelemetry tracing shut down")


def _get_openapi_servers() -> list[dict[str, str]]:
    """Get OpenAPI server URLs from environment variable.

    The OPENAPI_SERVER_URL environment variable allows configuring the server URL
    for OpenAPI spec generation. This is required for ZAP security scanning in
    different environments (CI, staging, production).

    If not set, defaults to http://localhost:8000 for local development.

    Returns:
        List of server dictionaries for FastAPI's servers parameter.
    """
    import os

    server_url = os.environ.get("OPENAPI_SERVER_URL", "http://localhost:8000")
    return [{"url": server_url, "description": "API server"}]


def _get_deprecation_config() -> DeprecationConfig:
    """Get deprecation configuration for RFC 8594 headers (NEM-2089).

    This function returns a DeprecationConfig that registers all deprecated API
    endpoints. The middleware will add Deprecation, Sunset, and Link headers
    to responses from these endpoints per RFC 8594.

    Returns:
        DeprecationConfig with registered deprecated endpoints.

    Example:
        To deprecate an endpoint, import DeprecatedEndpoint and datetime,
        then add to this function::

            from datetime import UTC, datetime
            from backend.api.middleware import DeprecatedEndpoint

            config.register(
                DeprecatedEndpoint(
                    path="/api/v1/cameras",
                    sunset_date=datetime(2026, 6, 1, tzinfo=UTC),
                    deprecated_at=datetime(2026, 1, 1, tzinfo=UTC),
                    replacement="/api/v2/cameras",
                    link="https://docs.example.com/migration/v2-cameras",
                )
            )

    Note:
        DeprecatedEndpoint fields:
        - path: The URL path (supports wildcards like /api/v1/*)
        - sunset_date: When the endpoint will be removed
        - deprecated_at: When deprecation was announced (optional)
        - replacement: Replacement endpoint path (optional)
        - link: Documentation URL for migration guide (optional)
    """
    config = DeprecationConfig()

    # Currently no deprecated endpoints are registered.
    # When deprecating an endpoint, add config.register() calls here.

    return config


def custom_generate_unique_id(route: APIRoute) -> str:
    """Generate custom operation IDs for OpenAPI schema (NEM-3347).

    Creates more readable operation IDs by combining the route's tag with its
    function name. This improves the developer experience when using API clients
    generated from the OpenAPI spec.

    Args:
        route: FastAPI route to generate an operation ID for

    Returns:
        Operation ID in format "tag_function_name" or just "function_name" if no tags

    Example:
        A route with tags=["cameras"] and name="get_camera" returns "cameras_get_camera"
    """
    if route.tags:
        return f"{route.tags[0]}_{route.name}"
    return route.name


app = FastAPI(
    title="Home Security Intelligence API",
    description="AI-powered home security monitoring system",
    version="0.1.0",
    lifespan=lifespan,
    # Server URLs for OpenAPI spec - required for ZAP security scanning
    # Configurable via OPENAPI_SERVER_URL environment variable
    servers=_get_openapi_servers(),
    # Custom operation ID generator for more readable API client code (NEM-3347)
    generate_unique_id_function=custom_generate_unique_id,
)


# Save reference to original openapi method before overriding (NEM-3347)
_original_openapi = app.openapi


@lru_cache
def get_cached_openapi_schema() -> dict[str, Any]:
    """Get cached OpenAPI schema for improved performance (NEM-3347).

    Caches the OpenAPI schema generation using lru_cache to avoid regenerating
    the schema on every /openapi.json request. This significantly improves
    response time for documentation endpoints in production.

    Returns:
        OpenAPI schema dictionary (cached after first call)
    """
    return _original_openapi()


# Override the default openapi method with cached version (NEM-3347)
app.openapi = get_cached_openapi_schema  # type: ignore[method-assign]


# Add authentication middleware (if enabled in settings)
app.add_middleware(AuthMiddleware)

# Add Content-Type validation middleware for request body validation (NEM-1617)
# Validates that POST/PUT/PATCH requests have acceptable Content-Type headers
app.add_middleware(ContentTypeValidationMiddleware)

# Add request ID middleware for log correlation
app.add_middleware(RequestIDMiddleware)

# Add OpenTelemetry Baggage middleware for cross-service context propagation (NEM-3796)
# Extracts incoming baggage from W3C Baggage headers and sets application-specific context
# (camera.id, event.priority, request.source) for propagation through the detection pipeline
app.add_middleware(BaggageMiddleware)

# Add request timing middleware for API latency tracking (NEM-1469)
# Added early so it measures the full request lifecycle including other middleware
app.add_middleware(RequestTimingMiddleware)

# Add request logging middleware for structured observability (NEM-1963)
# Logs HTTP requests with timing, status codes, and correlation IDs
# Added after RequestTimingMiddleware so logging happens after timing starts
# Excludes health/metrics endpoints to reduce noise
if get_settings().request_logging_enabled:
    app.add_middleware(RequestLoggingMiddleware)

# Add request recording middleware for debugging production issues (NEM-1964)
# Records HTTP requests for replay debugging based on:
# - Always on error (status >= 500)
# - Sample % of successful requests (configurable via request_recording_sample_rate)
# - When X-Debug-Record header is present
# Disabled by default for production (request_recording_enabled=False)
if get_settings().request_recording_enabled:
    app.add_middleware(RequestRecorderMiddleware)

# Add RFC 8594 deprecation headers middleware (NEM-2089)
# Adds Deprecation, Sunset, and Link headers to deprecated endpoints
app.add_middleware(DeprecationMiddleware, config=_get_deprecation_config())

# Add deprecation logger middleware for tracking deprecated endpoint usage (NEM-2090)
# Logs deprecated calls, increments Prometheus metrics, and adds Warning header
# Note: Must be added AFTER DeprecationMiddleware so it can see the Deprecation header
app.add_middleware(DeprecationLoggerMiddleware)

# Security: Restrict CORS methods to only what's needed
# Using explicit methods instead of wildcard "*" to follow least-privilege principle
# Note: When allow_credentials=True, allow_origins cannot be ["*"]
# If "*" is in origins, we disable credentials to allow any origin
_cors_origins = get_settings().cors_origins
_allow_credentials = "*" not in _cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Add security headers middleware for defense-in-depth
# HSTS preload can be enabled via HSTS_PRELOAD env var for public deployments
app.add_middleware(SecurityHeadersMiddleware, hsts_preload=get_settings().hsts_preload)

# Add body size limit middleware to prevent DoS attacks (NEM-1614)
# Default: 10MB limit for request bodies
app.add_middleware(BodySizeLimitMiddleware, max_body_size=10 * 1024 * 1024)

# Add GZip compression middleware for response compression (NEM-3741)
# Compresses responses larger than 1KB with compression level 5
# Provides 70-90% bandwidth reduction for large JSON responses
app.add_middleware(
    GZipMiddleware,
    minimum_size=1000,  # Only compress responses > 1KB
    compresslevel=5,  # Balance between CPU and compression ratio
)

# Add idempotency middleware for mutation endpoints (NEM-1999)
# Caches responses by Idempotency-Key header to prevent duplicate operations
# Must be after body limit (to validate body first) and before auth (to cache auth'd responses)
if get_settings().idempotency_enabled:
    app.add_middleware(IdempotencyMiddleware)

# Register global exception handlers for consistent error responses
register_exception_handlers(app)

# Register routers
app.include_router(admin.router)
app.include_router(ai_audit.router)
app.include_router(alertmanager.router)
app.include_router(alerts.router)
app.include_router(alerts.alerts_instance_router)
app.include_router(analytics.router)
app.include_router(audit.router)
app.include_router(calibration.router)
app.include_router(cameras.router)
app.include_router(debug.router)
app.include_router(detections.router)
app.include_router(dlq.router)
app.include_router(entities.router)
app.include_router(events.router)
app.include_router(exports.router)
app.include_router(feedback.router)
app.include_router(gpu_config.router)
app.include_router(health_ai_services.router)
app.include_router(hierarchy.router)
app.include_router(hierarchy.property_router)
app.include_router(hierarchy.area_router)
app.include_router(household.router)
app.include_router(jobs.router)
app.include_router(logs.router)
app.include_router(media.router)
app.include_router(metrics.router)
app.include_router(notification.router)
app.include_router(notification_preferences.router)
app.include_router(outbound_webhooks.router)
app.include_router(prompt_management.router)
app.include_router(queues.router)
app.include_router(rum.router)
app.include_router(scheduled_reports.router)
app.include_router(services.router)
app.include_router(settings_api.router)
app.include_router(summaries.router)
app.include_router(system.router)
app.include_router(system_settings.router)
app.include_router(tracks.router)
app.include_router(webhooks.router)
app.include_router(websocket.router)
app.include_router(zone_anomalies.router)
app.include_router(zone_household.router)
app.include_router(zones.router)


@app.get("/")
async def root() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "message": "Home Security Intelligence API"}


@app.get("/health")
async def health() -> dict[str, str]:
    """Simple liveness health check endpoint (canonical liveness probe).

    This endpoint indicates whether the process is running and able to
    respond to HTTP requests. It always returns 200 with status "alive"
    if the process is up.

    This is the canonical liveness probe endpoint. Use this for:
    - Docker HEALTHCHECK liveness checks
    - Kubernetes liveness probes
    - Simple "is the server up?" monitoring

    For detailed health information, use:
    - GET /api/system/health - Detailed health check with service status
    - GET /ready - Readiness probe (checks dependencies)

    Returns:
        LivenessResponse with status "alive".
    """
    from backend.api.schemas.health import LivenessResponse

    return LivenessResponse().model_dump()


@app.get("/ready")
async def ready() -> Response:
    """Simple readiness health check endpoint (canonical readiness probe).

    This endpoint indicates whether the application is ready to receive
    traffic and process requests. It checks critical dependencies:
    - Database connectivity
    - Redis connectivity
    - Critical pipeline workers

    This is the canonical readiness probe endpoint. Use this for:
    - Docker HEALTHCHECK readiness checks
    - Kubernetes readiness probes
    - Load balancer health checks

    For detailed readiness information with service breakdown, use:
    - GET /api/system/health/ready - Full readiness response with details

    Returns:
        SimpleReadinessResponse with ready bool and status. HTTP 200 if ready, 503 if not.
    """
    from starlette.responses import JSONResponse

    from backend.api.routes.system import (
        _are_critical_pipeline_workers_healthy,
        check_database_health,
        check_redis_health,
    )
    from backend.api.schemas.health import SimpleReadinessResponse
    from backend.core import get_db
    from backend.core.redis import get_redis_optional

    # Get database session
    db_status = None
    async for db in get_db():
        db_status = await check_database_health(db)
        break

    if db_status is None:
        return JSONResponse(
            content=SimpleReadinessResponse(ready=False, status="not_ready").model_dump(),
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    # Get Redis client (optional - it's a generator that returns None if unavailable)
    redis = None
    async for redis_client in get_redis_optional():
        redis = redis_client
        break
    redis_status = await check_redis_health(redis)

    # Check pipeline workers
    pipeline_workers_healthy = _are_critical_pipeline_workers_healthy()

    db_healthy = db_status.status == "healthy"
    redis_healthy = redis_status.status == "healthy"

    if db_healthy and redis_healthy and pipeline_workers_healthy:
        return JSONResponse(
            content=SimpleReadinessResponse(ready=True, status="ready").model_dump(),
            status_code=status.HTTP_200_OK,
        )
    else:
        return JSONResponse(
            content=SimpleReadinessResponse(ready=False, status="not_ready").model_dump(),
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


def get_ssl_context() -> ssl.SSLContext | None:
    """Get SSL context for HTTPS if TLS is enabled.

    Returns:
        ssl.SSLContext if TLS is enabled, None otherwise.
    """
    from backend.core.tls import (
        TLSConfig,
        TLSMode,
        create_ssl_context,
        generate_self_signed_certificate,
        get_tls_config,
    )

    config = get_tls_config()

    # Type guard: TLSConfig uses new mode API, dict is legacy
    if isinstance(config, dict):
        # Legacy dict config - no TLSConfig features
        return None

    if not config.is_enabled:
        return None

    # Auto-generate self-signed certificate if needed
    if config.mode == TLSMode.SELF_SIGNED:
        import os
        from pathlib import Path

        # Use default paths if not specified
        cert_path = config.cert_path or "data/certs/cert.pem"
        key_path = config.key_path or "data/certs/key.pem"

        # Generate certificate if it doesn't exist
        if not Path(cert_path).exists() or not Path(key_path).exists():
            from backend.core.logging import get_logger

            ssl_logger = get_logger(__name__)
            ssl_logger.info(f"Generating self-signed certificate: {cert_path}")
            hostname = os.environ.get("TLS_HOSTNAME", "localhost")
            san_hosts_str = os.environ.get("TLS_SAN_HOSTS", "127.0.0.1,::1")
            san_hosts = [h.strip() for h in san_hosts_str.split(",") if h.strip()]

            generate_self_signed_certificate(
                cert_path=cert_path,
                key_path=key_path,
                hostname=hostname,
                san_hosts=san_hosts,
            )

        # Update config paths for self-signed mode
        config = TLSConfig(
            mode=config.mode,
            cert_path=cert_path,
            key_path=key_path,
            ca_path=config.ca_path,
            verify_client=config.verify_client,
            min_version=config.min_version,
        )

    return create_ssl_context(config)


if __name__ == "__main__":
    import uvicorn

    from backend.core.logging import get_logger

    main_logger = get_logger(__name__)
    settings = get_settings()
    ssl_context = get_ssl_context()

    if ssl_context:
        main_logger.info(f"Starting HTTPS server on {settings.api_host}:{settings.api_port}")
        uvicorn.run(
            app,
            host=settings.api_host,
            port=settings.api_port,
            ssl_keyfile=settings.tls_key_path,
            ssl_certfile=settings.tls_cert_path,
        )
    else:
        main_logger.info(f"Starting HTTP server on {settings.api_host}:{settings.api_port}")
        uvicorn.run(app, host=settings.api_host, port=settings.api_port)
