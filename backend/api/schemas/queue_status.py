"""Pydantic schemas for queue status API endpoints.

This module provides schemas for monitoring job queue health including:
- Queue depth and processing metrics
- Worker status and throughput
- Health status based on configurable thresholds
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class QueueHealthStatus(str, Enum):
    """Health status for a queue based on depth and wait time."""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"


class ThroughputMetrics(BaseModel):
    """Throughput metrics for a queue."""

    jobs_per_minute: float = Field(
        ...,
        ge=0,
        description="Average number of jobs processed per minute",
    )
    avg_processing_seconds: float = Field(
        ...,
        ge=0,
        description="Average time to process a job in seconds",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "jobs_per_minute": 12.5,
                "avg_processing_seconds": 4.8,
            }
        }
    )


class OldestJobInfo(BaseModel):
    """Information about the oldest job in a queue."""

    id: str | None = Field(
        None,
        description="Job identifier (if available)",
    )
    queued_at: datetime | None = Field(
        None,
        description="Timestamp when the job was queued",
    )
    wait_seconds: float = Field(
        ...,
        ge=0,
        description="How long the oldest job has been waiting in seconds",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "job_12345",
                "queued_at": "2025-12-23T10:30:00.000000",
                "wait_seconds": 45.2,
            }
        }
    )


class QueueStatus(BaseModel):
    """Status of a single job queue."""

    name: str = Field(
        ...,
        description="Queue name",
    )
    status: QueueHealthStatus = Field(
        ...,
        description="Health status of the queue",
    )
    depth: int = Field(
        ...,
        ge=0,
        description="Number of jobs waiting in the queue",
    )
    running: int = Field(
        ...,
        ge=0,
        description="Number of jobs currently being processed",
    )
    workers: int = Field(
        ...,
        ge=0,
        description="Number of workers available for this queue",
    )
    throughput: ThroughputMetrics = Field(
        ...,
        description="Throughput metrics for the queue",
    )
    oldest_job: OldestJobInfo | None = Field(
        None,
        description="Information about the oldest job waiting (if any)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
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
        }
    )


class QueueStatusSummary(BaseModel):
    """Summary statistics across all queues."""

    total_queued: int = Field(
        ...,
        ge=0,
        description="Total number of jobs waiting across all queues",
    )
    total_running: int = Field(
        ...,
        ge=0,
        description="Total number of jobs currently being processed",
    )
    total_workers: int = Field(
        ...,
        ge=0,
        description="Total number of workers across all queues",
    )
    overall_status: QueueHealthStatus = Field(
        ...,
        description="Overall health status (worst status across all queues)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_queued": 45,
                "total_running": 8,
                "total_workers": 12,
                "overall_status": "healthy",
            }
        }
    )


class QueuesStatusResponse(BaseModel):
    """Response schema for GET /api/queues/status endpoint."""

    queues: list[QueueStatus] = Field(
        ...,
        description="Status of each queue",
    )
    summary: QueueStatusSummary = Field(
        ...,
        description="Summary statistics across all queues",
    )

    model_config = ConfigDict(
        json_schema_extra={
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
                    },
                    {
                        "name": "detection",
                        "status": "warning",
                        "depth": 55,
                        "running": 3,
                        "workers": 4,
                        "throughput": {
                            "jobs_per_minute": 8.2,
                            "avg_processing_seconds": 7.3,
                        },
                        "oldest_job": None,
                    },
                ],
                "summary": {
                    "total_queued": 70,
                    "total_running": 5,
                    "total_workers": 8,
                    "overall_status": "warning",
                },
            }
        }
    )
