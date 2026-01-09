"""Pydantic schemas for dead-letter queue (DLQ) API endpoints.

This module defines request/response schemas for the DLQ management API,
which provides visibility into and control over failed AI processing jobs.

The system has two dead-letter queues:
- `dlq:detection_queue` - Jobs that failed during RT-DETRv2 object detection
- `dlq:analysis_queue` - Jobs that failed during Nemotron risk analysis

Schema overview:
- DLQStatsResponse: Statistics for all DLQs (counts per queue)
- DLQJobResponse: Single failed job with enriched error context (NEM-1474)
- DLQJobsResponse: Paginated list of failed jobs
- DLQRequeueResponse: Result of requeue operations (single or bulk)
- DLQClearResponse: Result of clearing a DLQ
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DLQJobResponse(BaseModel):
    """Response schema for a single job in the dead-letter queue.

    Includes enriched error context (NEM-1474) for faster debugging:
    - error_type: Exception class name for categorization
    - stack_trace: Truncated stack trace for debugging
    - http_status: HTTP status code (for network errors)
    - response_body: Truncated AI service response (for debugging)
    - retry_delays: Delays applied between retry attempts
    - context: System state snapshot at failure time
    """

    original_job: dict = Field(
        ...,
        description="Original job payload that failed",
    )
    error: str = Field(
        ...,
        description="Error message from the last failure attempt",
    )
    attempt_count: int = Field(
        ...,
        description="Number of processing attempts made",
        ge=1,
    )
    first_failed_at: str = Field(
        ...,
        description="ISO timestamp of the first failure",
    )
    last_failed_at: str = Field(
        ...,
        description="ISO timestamp of the last failure",
    )
    queue_name: str = Field(
        ...,
        description="Name of the original queue where the job came from",
    )
    # Error context enrichment fields (NEM-1474)
    error_type: str | None = Field(
        None,
        description="Exception class name (e.g., 'ConnectionRefusedError')",
    )
    stack_trace: str | None = Field(
        None,
        description="Truncated stack trace (max 4KB) for debugging",
    )
    http_status: int | None = Field(
        None,
        description="HTTP status code if the error was from a network request",
    )
    response_body: str | None = Field(
        None,
        description="Truncated response body (max 2KB) from AI service",
    )
    retry_delays: list[float] | None = Field(
        None,
        description="Delays (in seconds) applied between retry attempts",
    )
    context: dict[str, Any] | None = Field(
        None,
        description="System state snapshot at failure time (queue depths, circuit breaker states)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
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
        }
    )


class DLQStatsResponse(BaseModel):
    """Response schema for DLQ statistics.

    Provides counts of failed jobs in each dead-letter queue, useful for
    monitoring the health of the AI processing pipeline and identifying
    when jobs are failing at a particular stage.
    """

    detection_queue_count: int = Field(
        ...,
        description="Number of jobs in the detection DLQ (dlq:detection_queue). "
        "These are jobs that failed during RT-DETRv2 object detection.",
        ge=0,
    )
    analysis_queue_count: int = Field(
        ...,
        description="Number of jobs in the analysis DLQ (dlq:analysis_queue). "
        "These are jobs that failed during Nemotron risk analysis.",
        ge=0,
    )
    total_count: int = Field(
        ...,
        description="Total number of failed jobs across all DLQs. "
        "High values may indicate systemic issues with AI services.",
        ge=0,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detection_queue_count": 2,
                "analysis_queue_count": 1,
                "total_count": 3,
            }
        }
    )


class DLQJobsResponse(BaseModel):
    """Response schema for listing jobs in a DLQ.

    Contains a paginated list of failed jobs with enriched error context
    for debugging and categorization.
    """

    queue_name: str = Field(
        ...,
        description="Name of the dead-letter queue (e.g., 'dlq:detection_queue')",
    )
    jobs: list[DLQJobResponse] = Field(
        ...,
        description="List of jobs in the queue with enriched error context",
    )
    count: int = Field(
        ...,
        description="Number of jobs returned in this response (may be less than total in queue due to pagination)",
        ge=0,
    )

    model_config = ConfigDict(
        json_schema_extra={
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
                        "stack_trace": 'Traceback (most recent call last):\n  File "/app/backend/services/detector_client.py", line 45, in detect\n    ...',
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
    )


class DLQRequeueResponse(BaseModel):
    """Response schema for requeuing job(s) from a DLQ.

    Used by both single-job requeue (`/requeue/{queue_name}`) and
    bulk requeue (`/requeue-all/{queue_name}`) endpoints.
    """

    success: bool = Field(
        ...,
        description="Whether the requeue operation succeeded. "
        "False if the DLQ was empty or the operation failed.",
    )
    message: str = Field(
        ...,
        description="Human-readable status message describing the result. "
        "Includes count of requeued jobs and target queue name.",
    )
    job: dict | None = Field(
        None,
        description="The requeued job data (if available). "
        "Note: Currently always None as job data is not preserved during the move operation.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Job requeued from dlq:detection_queue to detection_queue",
                "job": None,
            }
        }
    )


class DLQClearResponse(BaseModel):
    """Response schema for clearing a DLQ.

    WARNING: This is a destructive operation. Cleared jobs cannot be recovered.
    """

    success: bool = Field(
        ...,
        description="Whether the clear operation succeeded. "
        "True even if the queue was already empty.",
    )
    message: str = Field(
        ...,
        description="Human-readable status message including the count of deleted jobs. "
        "Format: 'Cleared N jobs from {queue_name}'.",
    )
    queue_name: str = Field(
        ...,
        description="Name of the cleared queue (e.g., 'dlq:detection_queue').",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Cleared 5 jobs from dlq:detection_queue",
                "queue_name": "dlq:detection_queue",
            }
        }
    )
