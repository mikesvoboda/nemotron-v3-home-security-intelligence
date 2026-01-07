"""Pydantic schemas for dead-letter queue (DLQ) API endpoints."""

from pydantic import BaseModel, ConfigDict, Field


class DLQJobResponse(BaseModel):
    """Response schema for a single job in the dead-letter queue."""

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
            }
        }
    )


class DLQStatsResponse(BaseModel):
    """Response schema for DLQ statistics."""

    detection_queue_count: int = Field(
        ...,
        description="Number of jobs in the detection DLQ",
        ge=0,
    )
    analysis_queue_count: int = Field(
        ...,
        description="Number of jobs in the analysis DLQ",
        ge=0,
    )
    total_count: int = Field(
        ...,
        description="Total number of jobs across all DLQs",
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
    """Response schema for listing jobs in a DLQ."""

    queue_name: str = Field(
        ...,
        description="Name of the dead-letter queue",
    )
    jobs: list[DLQJobResponse] = Field(
        ...,
        description="List of jobs in the queue",
    )
    count: int = Field(
        ...,
        description="Number of jobs returned",
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
                        "error": "Connection refused",
                        "attempt_count": 3,
                        "first_failed_at": "2025-12-23T10:30:05.000000",
                        "last_failed_at": "2025-12-23T10:30:15.000000",
                        "queue_name": "detection_queue",
                    }
                ],
                "count": 1,
            }
        }
    )


class DLQRequeueResponse(BaseModel):
    """Response schema for requeuing a job from DLQ."""

    success: bool = Field(
        ...,
        description="Whether the requeue operation succeeded",
    )
    message: str = Field(
        ...,
        description="Status message",
    )
    job: dict | None = Field(
        None,
        description="The requeued job data (if successful)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Job requeued from dlq:detection_queue to detection_queue",
                "job": {
                    "camera_id": "front_door",
                    "file_path": "/export/foscam/front_door/image_001.jpg",
                    "timestamp": "2025-12-23T10:30:00.000000",
                },
            }
        }
    )


class DLQClearResponse(BaseModel):
    """Response schema for clearing a DLQ."""

    success: bool = Field(
        ...,
        description="Whether the clear operation succeeded",
    )
    message: str = Field(
        ...,
        description="Status message",
    )
    queue_name: str = Field(
        ...,
        description="Name of the cleared queue",
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
