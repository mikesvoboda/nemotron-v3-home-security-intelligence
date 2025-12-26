"""Dead-letter queue (DLQ) inspection and management API endpoints.

This module provides endpoints to:
- View DLQ statistics
- List jobs in each DLQ
- Requeue jobs from DLQ back to processing
- Clear DLQ contents
"""

from enum import Enum

from fastapi import APIRouter, Depends, Query

from backend.api.schemas.dlq import (
    DLQClearResponse,
    DLQJobsResponse,
    DLQRequeueResponse,
    DLQStatsResponse,
)
from backend.core.logging import get_logger
from backend.core.redis import RedisClient, get_redis
from backend.services.retry_handler import get_retry_handler

logger = get_logger(__name__)

router = APIRouter(prefix="/api/dlq", tags=["dlq"])


class DLQName(str, Enum):
    """Available dead-letter queue names."""

    DETECTION = "dlq:detection_queue"
    ANALYSIS = "dlq:analysis_queue"


def _get_target_queue(dlq_name: DLQName) -> str:
    """Get the target queue name for requeuing from a DLQ.

    Args:
        dlq_name: DLQ name enum

    Returns:
        Target queue name
    """
    if dlq_name == DLQName.DETECTION:
        return "detection_queue"
    return "analysis_queue"


@router.get("/stats", response_model=DLQStatsResponse)
async def get_dlq_stats(
    redis: RedisClient = Depends(get_redis),
) -> DLQStatsResponse:
    """Get dead-letter queue statistics.

    Returns the number of jobs in each DLQ and the total count.

    Returns:
        DLQStatsResponse with queue counts
    """
    handler = get_retry_handler(redis)
    stats = await handler.get_dlq_stats()

    return DLQStatsResponse(
        detection_queue_count=stats.detection_queue_count,
        analysis_queue_count=stats.analysis_queue_count,
        total_count=stats.total_count,
    )


@router.get("/jobs/{queue_name}", response_model=DLQJobsResponse)
async def get_dlq_jobs(
    queue_name: DLQName,
    start: int = Query(0, ge=0, description="Start index (0-based)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of jobs to return"),
    redis: RedisClient = Depends(get_redis),
) -> DLQJobsResponse:
    """List jobs in a specific dead-letter queue.

    Returns jobs in the specified DLQ without removing them.
    Use pagination parameters to control the result set.

    Args:
        queue_name: Name of the DLQ (detection or analysis)
        start: Start index for pagination
        limit: Maximum number of jobs to return
        redis: Redis client

    Returns:
        DLQJobsResponse with list of jobs
    """
    handler = get_retry_handler(redis)
    end = start + limit - 1 if limit > 0 else -1

    jobs = await handler.get_dlq_jobs(queue_name.value, start, end)

    return DLQJobsResponse(
        queue_name=queue_name.value,
        jobs=[
            {
                "original_job": job.original_job,
                "error": job.error,
                "attempt_count": job.attempt_count,
                "first_failed_at": job.first_failed_at,
                "last_failed_at": job.last_failed_at,
                "queue_name": job.queue_name,
            }
            for job in jobs
        ],
        count=len(jobs),
    )


@router.post("/requeue/{queue_name}", response_model=DLQRequeueResponse)
async def requeue_dlq_job(
    queue_name: DLQName,
    redis: RedisClient = Depends(get_redis),
) -> DLQRequeueResponse:
    """Requeue the oldest job from a DLQ back to its original processing queue.

    Removes the oldest job from the specified DLQ and adds it back to the
    original processing queue for retry.

    Args:
        queue_name: Name of the DLQ (detection or analysis)
        redis: Redis client

    Returns:
        DLQRequeueResponse with operation result
    """
    handler = get_retry_handler(redis)
    target_queue = _get_target_queue(queue_name)

    # Move job from DLQ to target queue
    success = await handler.move_dlq_job_to_queue(queue_name.value, target_queue)

    if success:
        logger.info(
            f"Requeued job from {queue_name.value} to {target_queue}",
            extra={
                "dlq_name": queue_name.value,
                "target_queue": target_queue,
            },
        )
        return DLQRequeueResponse(
            success=True,
            message=f"Job requeued from {queue_name.value} to {target_queue}",
            job=None,  # We don't have the job data after move
        )

    return DLQRequeueResponse(
        success=False,
        message=f"No jobs to requeue from {queue_name.value}",
        job=None,
    )


@router.post("/requeue-all/{queue_name}", response_model=DLQRequeueResponse)
async def requeue_all_dlq_jobs(
    queue_name: DLQName,
    redis: RedisClient = Depends(get_redis),
) -> DLQRequeueResponse:
    """Requeue all jobs from a DLQ back to their original processing queue.

    Removes all jobs from the specified DLQ and adds them back to the
    original processing queue for retry.

    Args:
        queue_name: Name of the DLQ (detection or analysis)
        redis: Redis client

    Returns:
        DLQRequeueResponse with operation result and count
    """
    handler = get_retry_handler(redis)
    target_queue = _get_target_queue(queue_name)

    requeued_count = 0
    while True:
        success = await handler.move_dlq_job_to_queue(queue_name.value, target_queue)
        if not success:
            break
        requeued_count += 1

    if requeued_count > 0:
        logger.info(
            f"Requeued {requeued_count} jobs from {queue_name.value} to {target_queue}",
            extra={
                "dlq_name": queue_name.value,
                "target_queue": target_queue,
                "count": requeued_count,
            },
        )
        return DLQRequeueResponse(
            success=True,
            message=f"Requeued {requeued_count} jobs from {queue_name.value} to {target_queue}",
            job=None,
        )

    return DLQRequeueResponse(
        success=False,
        message=f"No jobs to requeue from {queue_name.value}",
        job=None,
    )


@router.delete("/{queue_name}", response_model=DLQClearResponse)
async def clear_dlq(
    queue_name: DLQName,
    redis: RedisClient = Depends(get_redis),
) -> DLQClearResponse:
    """Clear all jobs from a dead-letter queue.

    WARNING: This permanently removes all jobs from the specified DLQ.
    Use with caution.

    Args:
        queue_name: Name of the DLQ to clear
        redis: Redis client

    Returns:
        DLQClearResponse with operation result
    """
    handler = get_retry_handler(redis)

    # Get count before clearing
    if queue_name == DLQName.DETECTION:
        count = await redis.get_queue_length(queue_name.value)
    else:
        count = await redis.get_queue_length(queue_name.value)

    success = await handler.clear_dlq(queue_name.value)

    if success:
        logger.info(
            f"Cleared {count} jobs from {queue_name.value}",
            extra={
                "queue_name": queue_name.value,
                "count": count,
            },
        )
        return DLQClearResponse(
            success=True,
            message=f"Cleared {count} jobs from {queue_name.value}",
            queue_name=queue_name.value,
        )

    return DLQClearResponse(
        success=False,
        message=f"Failed to clear {queue_name.value}",
        queue_name=queue_name.value,
    )
