"""FastAPI application entry point for home security intelligence system."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.middleware import AuthMiddleware
from backend.api.middleware.request_id import RequestIDMiddleware
from backend.api.routes import cameras, detections, dlq, events, media, metrics, system, websocket
from backend.api.routes.logs import router as logs_router
from backend.core import close_db, get_settings, init_db
from backend.core.logging import setup_logging
from backend.core.redis import close_redis, init_redis
from backend.services.cleanup_service import CleanupService
from backend.services.event_broadcaster import get_broadcaster, stop_broadcaster
from backend.services.file_watcher import FileWatcher
from backend.services.gpu_monitor import GPUMonitor
from backend.services.pipeline_workers import get_pipeline_manager, stop_pipeline_manager
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

    yield

    # Shutdown
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
app.include_router(cameras.router)
app.include_router(detections.router)
app.include_router(dlq.router)
app.include_router(events.router)
app.include_router(logs_router)
app.include_router(media.router)
app.include_router(metrics.router)
app.include_router(system.router)
app.include_router(websocket.router)


@app.get("/")
async def root() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "message": "Home Security Intelligence API"}


@app.get("/health")
async def health() -> dict[str, Any]:
    """Detailed health check endpoint."""
    # Check database
    db_status = "operational"
    try:
        from backend.core import get_engine

        engine = get_engine()
        if engine:
            db_status = "operational"
    except RuntimeError:
        db_status = "not_initialized"

    # Check Redis
    redis_status = "not_initialized"
    redis_details = {}
    try:
        from backend.core.redis import _redis_client

        if _redis_client:
            redis_health = await _redis_client.health_check()
            redis_status = redis_health.get("status", "unknown")
            redis_details = redis_health
    except Exception as e:
        redis_status = "error"
        redis_details = {"error": str(e)}

    overall_status = "healthy"
    if db_status != "operational" or redis_status not in ["healthy", "not_initialized"]:
        overall_status = "degraded"

    return {
        "status": overall_status,
        "api": "operational",
        "database": db_status,
        "redis": redis_status,
        "redis_details": redis_details,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)  # noqa: S104
