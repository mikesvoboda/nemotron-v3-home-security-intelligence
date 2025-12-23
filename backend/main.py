"""FastAPI application entry point for home security intelligence system."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import cameras, media, system
from backend.core import close_db, get_settings, init_db
from backend.core.redis import close_redis, init_redis


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle - startup and shutdown events."""
    # Startup
    settings = get_settings()
    await init_db()
    print(f"Database initialized: {settings.database_url}")

    try:
        await init_redis()
        print(f"Redis initialized: {settings.redis_url}")
    except Exception as e:
        print(f"Redis connection failed: {e}")
        print("Continuing without Redis - some features may be unavailable")

    yield

    # Shutdown
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(cameras.router)
app.include_router(media.router)
app.include_router(system.router)


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
