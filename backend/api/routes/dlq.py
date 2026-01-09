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
from backend.core.constants import (
    ANALYSIS_QUEUE,
    DETECTION_QUEUE,
    DLQ_ANALYSIS_QUEUE,
    DLQ_DETECTION_QUEUE,
)
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
    """Available dead-letter queue names.

    The system has two dead-letter queues corresponding to the two stages
    of the AI processing pipeline:

    - DETECTION: Jobs that failed during RT-DETRv2 object detection
      (e.g., detector service unavailable, image processing errors)
    - ANALYSIS: Jobs that failed during Nemotron risk analysis
      (e.g., LLM service unavailable, response parsing errors)

    Each DLQ stores failed jobs with enriched error context for debugging.
    """

    DETECTION = DLQ_DETECTION_QUEUE
    """Dead-letter queue for failed detection jobs (dlq:detection_queue)."""

    ANALYSIS = DLQ_ANALYSIS_QUEUE
    """Dead-letter queue for failed analysis jobs (dlq:analysis_queue)."""

    @property
    def target_queue(self) -> str:
        """Get the target queue name for requeuing from this DLQ.

        When jobs are requeued from a DLQ, they are moved to their original
        processing queue:
        - dlq:detection_queue -> detection_queue
        - dlq:analysis_queue -> analysis_queue

        Returns:
            Target queue name for requeuing
        """
        return {
            DLQName.DETECTION: DETECTION_QUEUE,
            DLQName.ANALYSIS: ANALYSIS_QUEUE,
        }[self]


@router.get(
    "/stats",
    response_model=DLQStatsResponse,
    summary="Get DLQ statistics",
    description="""
Retrieve statistics for all dead-letter queues in the system.

Returns the count of failed jobs in each DLQ (detection and analysis)
along with a total count. Use this endpoint to monitor the health of
the AI processing pipeline and identify when jobs are failing.

**No authentication required** for this read-only endpoint.
    """,
    operation_id="get_dlq_stats",
    responses={
        200: {
            "description": "Successfully retrieved DLQ statistics",
            "content": {
                "application/json": {
                    "example": {
                        "detection_queue_count": 2,
                        "analysis_queue_count": 1,
                        "total_count": 3,
                    }
                }
            },
        },
        500: {"description": "Internal server error - Redis connection failed"},
    },
)
async def get_dlq_stats(
    redis: RedisClient = Depends(get_redis),
) -> DLQStatsResponse:
    """Get dead-letter queue statistics.

    Returns the number of jobs in each DLQ and the total count.
    This is useful for monitoring the health of the AI pipeline
    and identifying when processing jobs are failing.

    Args:
        redis: Redis client (injected dependency)

    Returns:
        DLQStatsResponse with queue counts for detection and analysis DLQs
    """
    handler = get_retry_handler(redis)
    stats = await handler.get_dlq_stats()

    return DLQStatsResponse(
        detection_queue_count=stats.detection_queue_count,
        analysis_queue_count=stats.analysis_queue_count,
        total_count=stats.total_count,
    )


@router.get(
    "/jobs/{queue_name}",
    response_model=DLQJobsResponse,
    summary="List jobs in a DLQ",
    description="""
List failed jobs in a specific dead-letter queue with enriched error context.

Returns jobs in the specified DLQ without removing them. Use pagination
parameters to efficiently browse through large numbers of failed jobs.

**Available queues:**
- `dlq:detection_queue` - Jobs that failed during RT-DETRv2 object detection
- `dlq:analysis_queue` - Jobs that failed during Nemotron risk analysis

**Enriched error context (NEM-1474):**
Each job includes detailed debugging information:
- `error_type`: Exception class name (e.g., 'ConnectionRefusedError') for categorization
- `stack_trace`: Truncated stack trace (max 4KB) for debugging
- `http_status`: HTTP status code if the error was from a network request
- `response_body`: Truncated AI service response (max 2KB)
- `retry_delays`: List of delays (seconds) applied between retry attempts
- `context`: System state snapshot at failure time (queue depths, circuit breaker states)

**No authentication required** for this read-only endpoint.
    """,
    operation_id="get_dlq_jobs",
    responses={
        200: {
            "description": "Successfully retrieved jobs from the DLQ",
            "content": {
                "application/json": {
                    "example": {
                        "queue_name": "dlq:detection_queue",
                        "jobs": [
                            {
                                "original_job": {
                                    "camera_id": "front_door",
                                    "file_path": "/export/foscam/front_door/image_001.jpg",
                                    "timestamp": "2025-12-23T10:30:00.000000",
                                },
                                "error": "Connection refused: detector service unavailable",
                                "attempt_count": 3,
                                "first_failed_at": "2025-12-23T10:30:05.000000",
                                "last_failed_at": "2025-12-23T10:30:15.000000",
                                "queue_name": "detection_queue",
                                "error_type": "ConnectionRefusedError",
                                "stack_trace": "Traceback (most recent call last):\n  ...",
                                "http_status": None,
                                "response_body": None,
                                "retry_delays": [1.0, 2.0],
                                "context": {
                                    "detection_queue_depth": 150,
                                    "analysis_queue_depth": 25,
                                    "dlq_circuit_breaker_state": "closed",
                                },
                            }
                        ],
                        "count": 1,
                    }
                }
            },
        },
        422: {
            "description": "Validation error - invalid queue name or pagination parameters",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "type": "enum",
                                "loc": ["path", "queue_name"],
                                "msg": "Input should be 'dlq:detection_queue' or 'dlq:analysis_queue'",
                            }
                        ]
                    }
                }
            },
        },
        500: {"description": "Internal server error - Redis connection failed"},
    },
)
async def get_dlq_jobs(
    queue_name: DLQName,
    start: int = Query(
        0,
        ge=0,
        description="Start index for pagination (0-based). Use with `limit` to page through results.",
    ),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
        description="Maximum number of jobs to return (1-1000). Default is 100.",
    ),
    redis: RedisClient = Depends(get_redis),
) -> DLQJobsResponse:
    """List jobs in a specific dead-letter queue with enriched error context.

    Returns jobs in the specified DLQ without removing them.
    Use pagination parameters to control the result set.

    Each job includes enriched error context (NEM-1474):
    - error_type: Exception class name for categorization
    - stack_trace: Truncated stack trace for debugging
    - http_status: HTTP status code (for network errors)
    - response_body: Truncated AI service response
    - retry_delays: Delays applied between retry attempts
    - context: System state snapshot at failure time

    Args:
        queue_name: Name of the DLQ (detection or analysis)
        start: Start index for pagination (0-based)
        limit: Maximum number of jobs to return (1-1000)
        redis: Redis client (injected dependency)

    Returns:
        DLQJobsResponse with list of jobs including error context
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
                # Error context enrichment (NEM-1474)
                "error_type": job.error_type,
                "stack_trace": job.stack_trace,
                "http_status": job.http_status,
                "response_body": job.response_body,
                "retry_delays": job.retry_delays,
                "context": job.context,
            }
            for job in jobs
        ],
        count=len(jobs),
    )


@router.post(
    "/requeue/{queue_name}",
    response_model=DLQRequeueResponse,
    summary="Requeue oldest job from DLQ",
    description="""
Requeue the oldest (first) job from a dead-letter queue back to its original processing queue.

This operation:
1. Removes the oldest job from the specified DLQ (FIFO order)
2. Adds it back to the original processing queue for retry
3. Returns success/failure status

**Queue mapping:**
- `dlq:detection_queue` -> `detection_queue` (RT-DETRv2 processing)
- `dlq:analysis_queue` -> `analysis_queue` (Nemotron risk analysis)

**Use cases:**
- Retry a single job after fixing a transient issue (e.g., AI service restart)
- Gradually reprocess failed jobs one at a time
- Test if the processing pipeline is working before requeuing all jobs

**Authentication required:** This destructive operation requires an API key when `api_key_enabled=True`.
Provide the key via `X-API-Key` header or `api_key` query parameter.
    """,
    operation_id="requeue_dlq_job",
    responses={
        200: {
            "description": "Job successfully requeued or no jobs available",
            "content": {
                "application/json": {
                    "examples": {
                        "success": {
                            "summary": "Job requeued successfully",
                            "value": {
                                "success": True,
                                "message": "Job requeued from dlq:detection_queue to detection_queue",
                                "job": None,
                            },
                        },
                        "empty_queue": {
                            "summary": "No jobs in DLQ",
                            "value": {
                                "success": False,
                                "message": "No jobs to requeue from dlq:detection_queue",
                                "job": None,
                            },
                        },
                    }
                }
            },
        },
        401: {
            "description": "Unauthorized - API key required or invalid",
            "content": {
                "application/json": {
                    "examples": {
                        "missing_key": {
                            "summary": "API key not provided",
                            "value": {
                                "detail": "API key required. Provide via X-API-Key header or api_key query parameter."
                            },
                        },
                        "invalid_key": {
                            "summary": "Invalid API key",
                            "value": {"detail": "Invalid API key"},
                        },
                    }
                }
            },
        },
        422: {
            "description": "Validation error - invalid queue name",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "type": "enum",
                                "loc": ["path", "queue_name"],
                                "msg": "Input should be 'dlq:detection_queue' or 'dlq:analysis_queue'",
                            }
                        ]
                    }
                }
            },
        },
        500: {"description": "Internal server error - Redis connection failed"},
    },
)
async def requeue_dlq_job(
    queue_name: DLQName,
    redis: RedisClient = Depends(get_redis),
    _auth: None = Depends(verify_api_key),
) -> DLQRequeueResponse:
    """Requeue the oldest job from a DLQ back to its original processing queue.

    Removes the oldest job from the specified DLQ and adds it back to the
    original processing queue for retry. This is a destructive operation
    that requires API key authentication when enabled.

    Args:
        queue_name: Name of the DLQ (detection or analysis)
        redis: Redis client (injected dependency)
        _auth: API key verification (injected dependency)

    Returns:
        DLQRequeueResponse with operation result (success=True if job was requeued)
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


@router.post(
    "/requeue-all/{queue_name}",
    response_model=DLQRequeueResponse,
    summary="Requeue all jobs from DLQ",
    description="""
Requeue all jobs from a dead-letter queue back to their original processing queue.

This bulk operation:
1. Removes all jobs from the specified DLQ
2. Adds them back to the original processing queue for retry
3. Returns the count of requeued jobs

**Queue mapping:**
- `dlq:detection_queue` -> `detection_queue` (RT-DETRv2 processing)
- `dlq:analysis_queue` -> `analysis_queue` (Nemotron risk analysis)

**Safety limits:**
This operation is limited to `max_requeue_iterations` (configurable in settings)
to prevent resource exhaustion. If the DLQ contains more jobs than the limit,
a partial requeue will occur and the response will indicate the limit was hit.

**Use cases:**
- Bulk retry after fixing a systemic issue (e.g., AI service configuration)
- Clear DLQ after investigating and resolving root cause
- Recovery after a prolonged outage

**Authentication required:** This destructive operation requires an API key when `api_key_enabled=True`.
Provide the key via `X-API-Key` header or `api_key` query parameter.
    """,
    operation_id="requeue_all_dlq_jobs",
    responses={
        200: {
            "description": "Jobs requeued (fully or partially) or no jobs available",
            "content": {
                "application/json": {
                    "examples": {
                        "success": {
                            "summary": "All jobs requeued successfully",
                            "value": {
                                "success": True,
                                "message": "Requeued 15 jobs from dlq:detection_queue to detection_queue",
                                "job": None,
                            },
                        },
                        "partial": {
                            "summary": "Partial requeue (hit limit)",
                            "value": {
                                "success": True,
                                "message": "Requeued 1000 jobs from dlq:detection_queue to detection_queue (hit limit of 1000)",
                                "job": None,
                            },
                        },
                        "empty_queue": {
                            "summary": "No jobs in DLQ",
                            "value": {
                                "success": False,
                                "message": "No jobs to requeue from dlq:detection_queue",
                                "job": None,
                            },
                        },
                    }
                }
            },
        },
        401: {
            "description": "Unauthorized - API key required or invalid",
            "content": {
                "application/json": {
                    "examples": {
                        "missing_key": {
                            "summary": "API key not provided",
                            "value": {
                                "detail": "API key required. Provide via X-API-Key header or api_key query parameter."
                            },
                        },
                        "invalid_key": {
                            "summary": "Invalid API key",
                            "value": {"detail": "Invalid API key"},
                        },
                    }
                }
            },
        },
        422: {
            "description": "Validation error - invalid queue name",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "type": "enum",
                                "loc": ["path", "queue_name"],
                                "msg": "Input should be 'dlq:detection_queue' or 'dlq:analysis_queue'",
                            }
                        ]
                    }
                }
            },
        },
        500: {"description": "Internal server error - Redis connection failed"},
    },
)
async def requeue_all_dlq_jobs(
    queue_name: DLQName,
    redis: RedisClient = Depends(get_redis),
    _auth: None = Depends(verify_api_key),
) -> DLQRequeueResponse:
    """Requeue all jobs from a DLQ back to their original processing queue.

    Removes all jobs from the specified DLQ and adds them back to the
    original processing queue for retry. Limited to settings.max_requeue_iterations
    to prevent resource exhaustion.

    This is a destructive bulk operation that requires API key authentication
    when enabled.

    Args:
        queue_name: Name of the DLQ (detection or analysis)
        redis: Redis client (injected dependency)
        _auth: API key verification (injected dependency)

    Returns:
        DLQRequeueResponse with operation result and count of requeued jobs
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


@router.delete(
    "/{queue_name}",
    response_model=DLQClearResponse,
    summary="Clear all jobs from DLQ",
    description="""
**WARNING:** Permanently delete all jobs from a dead-letter queue.

This destructive operation:
1. Counts jobs in the specified DLQ
2. Deletes all jobs permanently (they cannot be recovered)
3. Returns the count of deleted jobs

**Available queues:**
- `dlq:detection_queue` - Failed RT-DETRv2 object detection jobs
- `dlq:analysis_queue` - Failed Nemotron risk analysis jobs

**Use cases:**
- Clear stale jobs that are no longer relevant (e.g., images already deleted)
- Reset after testing or debugging
- Clean up after resolving issues and selectively requeuing important jobs

**Caution:** Unlike requeue operations, cleared jobs cannot be recovered.
Consider using `/jobs/{queue_name}` to inspect jobs before clearing.

**Authentication required:** This destructive operation requires an API key when `api_key_enabled=True`.
Provide the key via `X-API-Key` header or `api_key` query parameter.
    """,
    operation_id="clear_dlq",
    responses={
        200: {
            "description": "DLQ cleared successfully or operation failed",
            "content": {
                "application/json": {
                    "examples": {
                        "success": {
                            "summary": "DLQ cleared successfully",
                            "value": {
                                "success": True,
                                "message": "Cleared 5 jobs from dlq:detection_queue",
                                "queue_name": "dlq:detection_queue",
                            },
                        },
                        "empty_queue": {
                            "summary": "DLQ was already empty",
                            "value": {
                                "success": True,
                                "message": "Cleared 0 jobs from dlq:detection_queue",
                                "queue_name": "dlq:detection_queue",
                            },
                        },
                        "failure": {
                            "summary": "Clear operation failed",
                            "value": {
                                "success": False,
                                "message": "Failed to clear dlq:detection_queue",
                                "queue_name": "dlq:detection_queue",
                            },
                        },
                    }
                }
            },
        },
        401: {
            "description": "Unauthorized - API key required or invalid",
            "content": {
                "application/json": {
                    "examples": {
                        "missing_key": {
                            "summary": "API key not provided",
                            "value": {
                                "detail": "API key required. Provide via X-API-Key header or api_key query parameter."
                            },
                        },
                        "invalid_key": {
                            "summary": "Invalid API key",
                            "value": {"detail": "Invalid API key"},
                        },
                    }
                }
            },
        },
        422: {
            "description": "Validation error - invalid queue name",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "type": "enum",
                                "loc": ["path", "queue_name"],
                                "msg": "Input should be 'dlq:detection_queue' or 'dlq:analysis_queue'",
                            }
                        ]
                    }
                }
            },
        },
        500: {"description": "Internal server error - Redis connection failed"},
    },
)
async def clear_dlq(
    queue_name: DLQName,
    redis: RedisClient = Depends(get_redis),
    _auth: None = Depends(verify_api_key),
) -> DLQClearResponse:
    """Clear all jobs from a dead-letter queue.

    WARNING: This permanently removes all jobs from the specified DLQ.
    Jobs cannot be recovered after this operation. Use with caution.

    This is a destructive operation that requires API key authentication
    when enabled.

    Args:
        queue_name: Name of the DLQ to clear
        redis: Redis client (injected dependency)
        _auth: API key verification (injected dependency)

    Returns:
        DLQClearResponse with operation result and count of deleted jobs
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
