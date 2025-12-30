"""FastAPI application entry point for home security intelligence system."""

import ssl
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
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
from backend.services.cleanup_service import CleanupService
from backend.services.event_broadcaster import get_broadcaster, stop_broadcaster
from backend.services.file_watcher import FileWatcher
from backend.services.gpu_monitor import GPUMonitor
from backend.services.health_monitor import ServiceHealthMonitor
from backend.services.pipeline_workers import get_pipeline_manager, stop_pipeline_manager
from backend.services.service_managers import ServiceConfig, ShellServiceManager
from backend.services.system_broadcaster import get_system_broadcaster


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

        # Initialize event broadcaster
        await get_broadcaster(redis_client)
        print("Event broadcaster initialized")

        # Initialize file watcher (monitors camera directories for new images)
        file_watcher = FileWatcher(redis_client=redis_client)
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
    service_health_monitor: ServiceHealthMonitor | None = None
    if redis_client is not None:
        service_configs = [
            ServiceConfig(
                name="rtdetr",
                health_url=f"{settings.rtdetr_url}/health",
                restart_cmd="scripts/start_rtdetr.sh",
                health_timeout=5.0,
                max_retries=3,
                backoff_base=5.0,
            ),
            ServiceConfig(
                name="nemotron",
                health_url=f"{settings.nemotron_url}/health",
                restart_cmd="scripts/start_nemotron.sh",
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
        print("Service health monitor initialized (RT-DETRv2, Nemotron)")

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
    await system_broadcaster.stop_broadcasting()
    print("System status broadcaster stopped")
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
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
    """Simple liveness health check endpoint.

    This endpoint indicates whether the process is running and able to
    respond to HTTP requests. It always returns 200 with status "alive"
    if the process is up.

    For detailed health information, use:
    - GET /api/system/health - Detailed health check with service status
    - GET /api/system/health/live - Kubernetes liveness probe
    - GET /api/system/health/ready - Kubernetes readiness probe

    This endpoint exists for backward compatibility with existing monitoring
    tools and Docker HEALTHCHECK configurations.

    Returns:
        Simple status indicating the server is alive.
    """
    return {"status": "alive", "message": "Use /api/system/health for detailed status"}


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
