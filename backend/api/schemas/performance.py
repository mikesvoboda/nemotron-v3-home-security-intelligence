"""Pydantic schemas for system performance metrics.

These schemas are used for the System Performance Dashboard to collect and
broadcast real-time metrics from GPU, AI models, databases, and host system.
"""

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class TimeRange(str, Enum):
    """Time range options for historical data."""

    FIVE_MIN = "5m"
    FIFTEEN_MIN = "15m"
    SIXTY_MIN = "60m"


class GpuMetrics(BaseModel):
    """GPU metrics from nvidia-smi / pynvml."""

    name: str = Field(..., description="GPU device name (e.g., 'NVIDIA RTX A5500')")
    utilization: float = Field(..., ge=0, le=100, description="GPU utilization percentage (0-100)")
    vram_used_gb: float = Field(..., ge=0, description="VRAM used in GB")
    vram_total_gb: float = Field(..., gt=0, description="Total VRAM in GB")
    temperature: int = Field(..., ge=0, description="GPU temperature in Celsius")
    power_watts: int = Field(..., ge=0, description="GPU power usage in Watts")

    @property
    def vram_percent(self) -> float:
        """Calculate VRAM usage percentage."""
        return (self.vram_used_gb / self.vram_total_gb) * 100

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "NVIDIA RTX A5500",
                "utilization": 38.0,
                "vram_used_gb": 22.7,
                "vram_total_gb": 24.0,
                "temperature": 38,
                "power_watts": 31,
            }
        }
    )


class AiModelMetrics(BaseModel):
    """Metrics for RT-DETRv2 model."""

    status: str = Field(..., description="Health status: healthy, unhealthy, unreachable")
    vram_gb: float = Field(..., ge=0, description="VRAM used by the model in GB")
    model: str = Field(..., description="Model name")
    device: str = Field(..., description="Device (e.g., 'cuda:0')")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "vram_gb": 0.17,
                "model": "rtdetr_r50vd_coco_o365",
                "device": "cuda:0",
            }
        }
    )


class NemotronMetrics(BaseModel):
    """Metrics for Nemotron LLM."""

    status: str = Field(..., description="Health status: healthy, unhealthy, unreachable")
    slots_active: int = Field(..., ge=0, description="Number of active inference slots")
    slots_total: int = Field(..., ge=0, description="Total available inference slots")
    context_size: int = Field(..., ge=0, description="Context window size in tokens")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "slots_active": 1,
                "slots_total": 2,
                "context_size": 4096,
            }
        }
    )


class InferenceMetrics(BaseModel):
    """AI inference latency and throughput metrics."""

    rtdetr_latency_ms: dict[str, float] = Field(
        ..., description="RT-DETRv2 latency stats (avg, p95, p99)"
    )
    nemotron_latency_ms: dict[str, float] = Field(
        ..., description="Nemotron latency stats (avg, p95, p99)"
    )
    pipeline_latency_ms: dict[str, float] = Field(
        ..., description="Full pipeline latency stats (avg, p95)"
    )
    throughput: dict[str, float] = Field(
        ..., description="Throughput metrics (images_per_min, events_per_min)"
    )
    queues: dict[str, int] = Field(..., description="Queue depths (detection, analysis)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "rtdetr_latency_ms": {"avg": 45, "p95": 82, "p99": 120},
                "nemotron_latency_ms": {"avg": 2100, "p95": 4800, "p99": 8200},
                "pipeline_latency_ms": {"avg": 3200, "p95": 6100},
                "throughput": {"images_per_min": 12.4, "events_per_min": 2.1},
                "queues": {"detection": 0, "analysis": 0},
            }
        }
    )


class DatabaseMetrics(BaseModel):
    """PostgreSQL database metrics."""

    status: str = Field(..., description="Health status: healthy, unhealthy, unreachable")
    connections_active: int = Field(..., ge=0, description="Active connections")
    connections_max: int = Field(..., ge=0, description="Maximum allowed connections")
    cache_hit_ratio: float = Field(
        ..., ge=0, le=100, description="Buffer cache hit ratio percentage"
    )
    transactions_per_min: float = Field(..., ge=0, description="Transaction rate per minute")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "connections_active": 5,
                "connections_max": 30,
                "cache_hit_ratio": 98.2,
                "transactions_per_min": 1200,
            }
        }
    )


class RedisMetrics(BaseModel):
    """Redis cache metrics."""

    status: str = Field(..., description="Health status: healthy, unhealthy, unreachable")
    connected_clients: int = Field(..., ge=0, description="Number of connected clients")
    memory_mb: float = Field(..., ge=0, description="Memory used in MB")
    hit_ratio: float = Field(..., ge=0, le=100, description="Cache hit ratio percentage")
    blocked_clients: int = Field(..., ge=0, description="Number of blocked clients")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "connected_clients": 8,
                "memory_mb": 1.5,
                "hit_ratio": 99.5,
                "blocked_clients": 0,
            }
        }
    )


class HostMetrics(BaseModel):
    """Host system metrics from psutil."""

    cpu_percent: float = Field(..., ge=0, le=100, description="CPU utilization percentage")
    ram_used_gb: float = Field(..., ge=0, description="RAM used in GB")
    ram_total_gb: float = Field(..., gt=0, description="Total RAM in GB")
    disk_used_gb: float = Field(..., ge=0, description="Disk used in GB")
    disk_total_gb: float = Field(..., gt=0, description="Total disk in GB")

    @property
    def ram_percent(self) -> float:
        """Calculate RAM usage percentage."""
        return (self.ram_used_gb / self.ram_total_gb) * 100

    @property
    def disk_percent(self) -> float:
        """Calculate disk usage percentage."""
        return (self.disk_used_gb / self.disk_total_gb) * 100

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cpu_percent": 12,
                "ram_used_gb": 8.2,
                "ram_total_gb": 32,
                "disk_used_gb": 156,
                "disk_total_gb": 500,
            }
        }
    )


class ContainerMetrics(BaseModel):
    """Container health status."""

    name: str = Field(..., description="Container name")
    status: str = Field(..., description="Container status (running, stopped, restarting, etc.)")
    health: str = Field(..., description="Health status (healthy, unhealthy, starting)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "backend",
                "status": "running",
                "health": "healthy",
            }
        }
    )


class PerformanceAlert(BaseModel):
    """Alert when metric exceeds threshold."""

    severity: str = Field(..., description="Alert severity: warning or critical")
    metric: str = Field(..., description="Metric name that triggered the alert")
    value: float = Field(..., description="Current metric value")
    threshold: float = Field(..., description="Threshold that was exceeded")
    message: str = Field(..., description="Human-readable alert message")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "severity": "warning",
                "metric": "gpu_temperature",
                "value": 82,
                "threshold": 80,
                "message": "GPU temperature high: 82C",
            }
        }
    )


class PerformanceUpdate(BaseModel):
    """Complete performance update sent via WebSocket.

    This is the main payload broadcast to frontend clients every 5 seconds.
    All fields are optional to allow partial updates.
    """

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When this update was generated (UTC)",
    )
    gpu: GpuMetrics | None = Field(None, description="GPU metrics")
    ai_models: dict[str, AiModelMetrics | NemotronMetrics] = Field(
        default_factory=dict, description="AI model metrics keyed by model name"
    )
    nemotron: NemotronMetrics | None = Field(None, description="Nemotron-specific metrics")
    inference: InferenceMetrics | None = Field(
        None, description="AI inference latency and throughput"
    )
    databases: dict[str, DatabaseMetrics | RedisMetrics] = Field(
        default_factory=dict, description="Database metrics keyed by name"
    )
    host: HostMetrics | None = Field(None, description="Host system metrics")
    containers: list[ContainerMetrics] = Field(
        default_factory=list, description="Container health statuses"
    )
    alerts: list[PerformanceAlert] = Field(
        default_factory=list, description="Active performance alerts"
    )

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()},
        json_schema_extra={
            "example": {
                "timestamp": "2025-12-31T10:30:00Z",
                "gpu": {
                    "name": "NVIDIA RTX A5500",
                    "utilization": 38.0,
                    "vram_used_gb": 22.7,
                    "vram_total_gb": 24.0,
                    "temperature": 38,
                    "power_watts": 31,
                },
                "ai_models": {
                    "rtdetr": {
                        "status": "healthy",
                        "vram_gb": 0.17,
                        "model": "rtdetr",
                        "device": "cuda:0",
                    }
                },
                "host": {
                    "cpu_percent": 12,
                    "ram_used_gb": 8.2,
                    "ram_total_gb": 32,
                    "disk_used_gb": 156,
                    "disk_total_gb": 500,
                },
                "alerts": [],
            }
        },
    )


class PerformanceHistoryResponse(BaseModel):
    """Response containing historical performance data.

    Used by GET /api/system/performance/history endpoint.
    """

    snapshots: list[PerformanceUpdate] = Field(
        ..., description="List of performance snapshots ordered chronologically"
    )
    time_range: TimeRange = Field(..., description="Time range of the history")
    count: int = Field(..., ge=0, description="Number of snapshots returned")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "snapshots": [],
                "time_range": "5m",
                "count": 0,
            }
        }
    )
