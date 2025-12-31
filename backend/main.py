"""FastAPI application entry point for home security intelligence system."""

import ssl
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from backend.api.middleware import AuthMiddleware
from backend.api.middleware.request_id import RequestIDMiddleware
from backend.api.routes import (
    admin,
    alerts,
    audit,
    cameras,
    detections,
    dlq,
    events,
    media,
    metrics,
    notification,
    system,
    websocket,
    zones,
)
from backend.api.routes.logs import router as logs_router
from backend.api.routes.system import register_workers
from backend.core import close_db, get_settings, init_db
from backend.core.logging import setup_logging
from backend.core.redis import close_redis, init_redis
from backend.models.camera import Camera
from backend.services.cleanup_service import CleanupService
from backend.services.event_broadcaster import get_broadcaster, stop_broadcaster
from backend.services.file_watcher import FileWatcher
from backend.services.gpu_monitor import GPUMonitor
from backend.services.health_monitor import ServiceHealthMonitor
from backend.services.performance_collector import PerformanceCollector
from backend.services.pipeline_workers import get_pipeline_manager, stop_pipeline_manager
from backend.services.service_managers import ServiceConfig, ShellServiceManager
from backend.services.system_broadcaster import get_system_broadcaster, stop_system_broadcaster


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


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Manage application lifecycle - startup and shutdown events."""
    # Initialize logging first (before any other initialization)
    setup_logging()

    # Startup
    settings = get_settings()
    await init_db()
    print(f"Database initialized: {settings.database_url}")

    # Track whether Redis-dependent services were initialized
    redis_client = None
    file_watcher = None
    pipeline_manager = None

    try:
        redis_client = await init_redis()
        print(f"Redis initialized: {settings.redis_url}")

        # Initialize and start event broadcaster for WebSocket real-time events
        # Note: get_broadcaster() both creates AND starts the broadcaster
        # (subscribes to Redis pub/sub channel)
        event_broadcaster = await get_broadcaster(redis_client)
        channel = event_broadcaster.channel_name
        print(f"Event broadcaster started, listening on channel: {channel}")

        # Initialize file watcher (monitors camera directories for new images)
        # Pass camera_creator callback to enable auto-creation of camera records
        file_watcher = FileWatcher(
            redis_client=redis_client,
            camera_creator=create_camera_callback,
        )
        await file_watcher.start()
        print(f"File watcher started: {settings.foscam_base_path}")

        # Initialize pipeline workers (detection queue, analysis queue, batch timeout)
        pipeline_manager = await get_pipeline_manager(redis_client)
        await pipeline_manager.start()
        print("Pipeline workers started (detection, analysis, batch timeout, metrics)")

    except Exception as e:
        print(f"Redis connection failed: {e}")
        print("Continuing without Redis - some features may be unavailable")

    # Initialize system broadcaster (runs independently of Redis, but uses it when available)
    # Pass the Redis client if it was successfully initialized
    system_broadcaster = get_system_broadcaster(redis_client=redis_client)
    await system_broadcaster.start_broadcasting(interval=5.0)
    print("System status broadcaster initialized (5s interval)")

    # Initialize performance collector and attach to system broadcaster
    # This enables detailed performance metrics broadcasting alongside system status
    performance_collector = PerformanceCollector()
    system_broadcaster.set_performance_collector(performance_collector)
    print("Performance collector initialized and attached to system broadcaster")

    # Initialize GPU monitor
    # Note: broadcaster=None to avoid duplicate GPU stats broadcasts
    # (system_broadcaster already handles GPU stats in periodic status updates)
    gpu_monitor = GPUMonitor(broadcaster=None)
    await gpu_monitor.start()
    print("GPU monitor initialized")

    # Initialize cleanup service
    cleanup_service = CleanupService()
    await cleanup_service.start()
    print("Cleanup service initialized")

    # Initialize service health monitor for auto-recovery of AI services
    # Note: This monitors RT-DETRv2 and Nemotron services for health and can trigger restarts
    # Redis is excluded since the application handles Redis failures gracefully already
    # Restart capability can be disabled via AI_RESTART_ENABLED=false for containerized deployments
    # where the restart scripts are not available inside the backend container
    service_health_monitor: ServiceHealthMonitor | None = None
    if redis_client is not None:
        # Set restart_cmd based on ai_restart_enabled setting
        # When disabled (e.g., in containers), health monitoring still works but no restart attempts
        rtdetr_restart_cmd = "ai/start_detector.sh" if settings.ai_restart_enabled else None
        nemotron_restart_cmd = "ai/start_llm.sh" if settings.ai_restart_enabled else None

        service_configs = [
            ServiceConfig(
                name="rtdetr",
                health_url=f"{settings.rtdetr_url}/health",
                restart_cmd=rtdetr_restart_cmd,
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
        print(
            f"Service health monitor initialized (RT-DETRv2, Nemotron) - restart: {restart_status}"
        )

    # Register workers with system routes for readiness checks
    register_workers(
        gpu_monitor=gpu_monitor,
        cleanup_service=cleanup_service,
        system_broadcaster=system_broadcaster,
        file_watcher=file_watcher,
        pipeline_manager=pipeline_manager,
    )
    print("Workers registered for readiness monitoring")

    yield

    # Shutdown
    # Stop service health monitor first (before stopping services it monitors)
    if service_health_monitor is not None:
        await service_health_monitor.stop()
        print("Service health monitor stopped")

    await cleanup_service.stop()
    print("Cleanup service stopped")
    await gpu_monitor.stop()
    print("GPU monitor stopped")

    # Stop pipeline workers (before file watcher to allow queue draining)
    await stop_pipeline_manager()
    print("Pipeline workers stopped")

    # Stop file watcher
    if file_watcher:
        await file_watcher.stop()
        print("File watcher stopped")

    await stop_broadcaster()
    print("Event broadcaster stopped")
    await stop_system_broadcaster()
    print("System status broadcaster stopped")
    # Close performance collector (cleanup HTTP client and pynvml)
    await performance_collector.close()
    print("Performance collector closed")
    await close_db()
    print("Database connections closed")
    await close_redis()
    print("Redis connection closed")


app = FastAPI(
    title="Home Security Intelligence API",
    description="AI-powered home security monitoring system",
    version="0.1.0",
    lifespan=lifespan,
)

# Add authentication middleware (if enabled in settings)
app.add_middleware(AuthMiddleware)

# Add request ID middleware for log correlation
app.add_middleware(RequestIDMiddleware)

# Security: Restrict CORS methods to only what's needed
# Using explicit methods instead of wildcard "*" to follow least-privilege principle
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Register routers
app.include_router(admin.router)
app.include_router(alerts.router)
app.include_router(audit.router)
app.include_router(cameras.router)
app.include_router(detections.router)
app.include_router(dlq.router)
app.include_router(events.router)
app.include_router(logs_router)
app.include_router(media.router)
app.include_router(metrics.router)
app.include_router(notification.router)
app.include_router(system.router)
app.include_router(websocket.router)
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
        Simple status indicating the server is alive.
    """
    return {"status": "alive"}


@app.get("/ready", response_model=None)
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
        Simple status indicating readiness. HTTP 200 if ready, 503 if not.
    """
    from starlette.responses import JSONResponse

    from backend.api.routes.system import (
        _are_critical_pipeline_workers_healthy,
        check_database_health,
        check_redis_health,
    )
    from backend.core import get_db
    from backend.core.redis import get_redis_optional

    # Get database session
    db_status = None
    async for db in get_db():
        db_status = await check_database_health(db)
        break

    if db_status is None:
        return JSONResponse(
            content={"ready": False, "status": "not_ready"},
            status_code=503,
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
            content={"ready": True, "status": "ready"},
            status_code=200,
        )
    else:
        return JSONResponse(
            content={"ready": False, "status": "not_ready"},
            status_code=503,
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
            print(f"Generating self-signed certificate: {cert_path}")
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

    settings = get_settings()
    ssl_context = get_ssl_context()

    if ssl_context:
        print(f"Starting HTTPS server on {settings.api_host}:{settings.api_port}")
        uvicorn.run(
            app,
            host=settings.api_host,
            port=settings.api_port,
            ssl_keyfile=settings.tls_key_path,
            ssl_certfile=settings.tls_cert_path,
        )
    else:
        print(f"Starting HTTP server on {settings.api_host}:{settings.api_port}")
        uvicorn.run(app, host=settings.api_host, port=settings.api_port)
