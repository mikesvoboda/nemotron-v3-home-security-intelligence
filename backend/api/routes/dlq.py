"""Dead-letter queue (DLQ) inspection and management API endpoints.

This module provides endpoints to:
- View DLQ statistics
- List jobs in each DLQ
- Requeue jobs from DLQ back to processing
- Clear DLQ contents

Destructive operations (requeue, clear) require API key authentication
when api_key_enabled is set to True in settings.
"""

import hashlib
from enum import Enum

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from backend.api.schemas.dlq import (
    DLQClearResponse,
    DLQJobsResponse,
    DLQRequeueResponse,
    DLQStatsResponse,
)
from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.core.redis import RedisClient, get_redis
from backend.services.retry_handler import get_retry_handler

logger = get_logger(__name__)

router = APIRouter(prefix="/api/dlq", tags=["dlq"])


async def verify_api_key(
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    api_key: str | None = None,
) -> None:
    """Verify API key for destructive DLQ operations.

    This dependency validates the API key when api_key_enabled is True.
    When authentication is disabled, all requests are allowed.

    Accepts API key via:
    - X-API-Key header (preferred)
    - api_key query parameter (fallback)

    Args:
        x_api_key: API key provided via X-API-Key header
        api_key: API key from query parameter

    Raises:
        HTTPException: 401 if API key is missing or invalid when auth is enabled
    """
    settings = get_settings()

    # Skip authentication if disabled
    if not settings.api_key_enabled:
        return

    # Use header first, fall back to query param
    key = x_api_key or api_key

    # Require API key when authentication is enabled
    if not key:
        raise HTTPException(
            status_code=401,
            detail="API key required. Provide via X-API-Key header or api_key query parameter.",
        )

    # Hash the provided key and compare against valid keys
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    valid_hashes = {hashlib.sha256(k.encode()).hexdigest() for k in settings.api_keys}

    if key_hash not in valid_hashes:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
        )


class DLQName(str, Enum):
    """Available dead-letter queue names."""

    DETECTION = "dlq:detection_queue"
    ANALYSIS = "dlq:analysis_queue"

    @property
    def target_queue(self) -> str:
        """Get the target queue name for requeuing from this DLQ.

        Returns:
            Target queue name
        """
        return {
            DLQName.DETECTION: "detection_queue",
            DLQName.ANALYSIS: "analysis_queue",
        }[self]


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
    _auth: None = Depends(verify_api_key),
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
    target_queue = queue_name.target_queue

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
    _auth: None = Depends(verify_api_key),
) -> DLQRequeueResponse:
    """Requeue all jobs from a DLQ back to their original processing queue.

    Removes all jobs from the specified DLQ and adds them back to the
    original processing queue for retry. Limited to settings.max_requeue_iterations
    to prevent resource exhaustion.

    Args:
        queue_name: Name of the DLQ (detection or analysis)
        redis: Redis client

    Returns:
        DLQRequeueResponse with operation result and count
    """
    settings = get_settings()
    max_iterations = settings.max_requeue_iterations

    handler = get_retry_handler(redis)
    target_queue = queue_name.target_queue

    # Check queue size before starting - return early if empty
    queue_length = await redis.get_queue_length(queue_name.value)
    if queue_length == 0:
        return DLQRequeueResponse(
            success=False,
            message=f"No jobs to requeue from {queue_name.value}",
            job=None,
        )

    requeued_count = 0
    for _ in range(max_iterations):
        success = await handler.move_dlq_job_to_queue(queue_name.value, target_queue)
        if not success:
            break
        requeued_count += 1

    if requeued_count > 0:
        # Check if we hit the limit
        hit_limit = requeued_count >= max_iterations
        message = f"Requeued {requeued_count} jobs from {queue_name.value} to {target_queue}"
        if hit_limit:
            message += f" (hit limit of {max_iterations})"

        logger.info(
            f"Requeued {requeued_count} jobs from {queue_name.value} to {target_queue}",
            extra={
                "dlq_name": queue_name.value,
                "target_queue": target_queue,
                "count": requeued_count,
                "hit_limit": hit_limit,
            },
        )
        return DLQRequeueResponse(
            success=True,
            message=message,
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
    _auth: None = Depends(verify_api_key),
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
