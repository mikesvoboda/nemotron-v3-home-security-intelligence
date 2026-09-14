"""Queue status monitoring API endpoints.

This module provides endpoints to monitor job queue health including:
- Queue depth and processing metrics
- Worker status and throughput
- Health status based on configurable thresholds
"""

from fastapi import APIRouter, Depends

from backend.api.schemas.queue_status import QueuesStatusResponse
from backend.core.logging import get_logger
from backend.core.redis import RedisClient, get_redis
from backend.services.queue_status_service import (
    QueueStatusService,
    get_queue_status_service,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/queues", tags=["queues"])


async def get_queue_service(
    redis: RedisClient = Depends(get_redis),
) -> QueueStatusService:
    """FastAPI dependency for queue status service.

    Args:
        redis: Redis client dependency

    Returns:
        QueueStatusService instance
    """
    return get_queue_status_service(redis)


@router.get(
    "/status",
    response_model=QueuesStatusResponse,
    responses={
        200: {
            "description": "Queue status retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "queues": [
                            {
                                "name": "ai_analysis",
                                "status": "healthy",
                                "depth": 15,
                                "running": 2,
                                "workers": 4,
                                "throughput": {
                                    "jobs_per_minute": 12.5,
                                    "avg_processing_seconds": 4.8,
                                },
                                "oldest_job": {
                                    "id": "job_12345",
                                    "queued_at": "2025-12-23T10:30:00.000000",
                                    "wait_seconds": 45.2,
                                },
                            }
                        ],
                        "summary": {
                            "total_queued": 15,
                            "total_running": 2,
                            "total_workers": 4,
                            "overall_status": "healthy",
                        },
                    }
                }
            },
        },
        500: {"description": "Internal server error"},
    },
    summary="Get queue status",
    description="""
Get the status of all job queues including depth, processing rate, and health.

**Queues Monitored:**
- `detection`: Object detection jobs from camera uploads
- `ai_analysis`: LLM risk analysis jobs for batched detections
- `dlq`: Dead-letter queue for failed jobs

**Health Status:**
- `healthy`: Queue depth below warning threshold, wait times acceptable
- `warning`: Queue depth approaching limits or wait times elevated
- `critical`: Queue depth exceeds limits or oldest job waiting too long

**Thresholds:**
Each queue has configurable thresholds:
- `depth_warning`: Queue depth that triggers warning status
- `depth_critical`: Queue depth that triggers critical status
- `max_wait_seconds`: Maximum acceptable wait time for oldest job
""",
)
async def get_queues_status(
    service: QueueStatusService = Depends(get_queue_service),
) -> QueuesStatusResponse:
    """Get the status of all job queues.

    Returns queue depth, processing rate, worker counts, and health status
    for each monitored queue. The response includes:

    - **queues**: List of individual queue statuses with metrics
    - **summary**: Aggregated statistics across all queues

    The health status is computed based on:
    1. Queue depth relative to warning/critical thresholds
    2. Wait time of the oldest job relative to max_wait_seconds

    Returns:
        QueuesStatusResponse with all queue statuses and summary
    """
    return await service.get_queues_status_response()
