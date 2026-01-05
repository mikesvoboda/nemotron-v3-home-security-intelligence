"""Unit tests for performance schemas."""

import pytest

from api.schemas.performance import (
    AiModelMetrics,
    ContainerMetrics,
    DatabaseMetrics,
    GpuMetrics,
    HostMetrics,
    InferenceMetrics,
    NemotronMetrics,
    PerformanceAlert,
    PerformanceUpdate,
    RedisMetrics,
    TimeRange,
)


class TestGpuMetrics:
    """Tests for GpuMetrics schema."""

    def test_valid_gpu_metrics(self):
        """Test creating valid GPU metrics."""
        metrics = GpuMetrics(
            name="NVIDIA RTX A5500",
            utilization=38.0,
            vram_used_gb=22.7,
            vram_total_gb=24.0,
            temperature=38,
            power_watts=31,
        )
        assert metrics.name == "NVIDIA RTX A5500"
        assert metrics.utilization == 38.0
        assert metrics.vram_used_gb == 22.7
        assert metrics.vram_total_gb == 24.0
        assert metrics.temperature == 38
        assert metrics.power_watts == 31

    def test_vram_percentage(self):
        """Test VRAM percentage calculation."""
        metrics = GpuMetrics(
            name="RTX",
            utilization=50,
            vram_used_gb=12.0,
            vram_total_gb=24.0,
            temperature=40,
            power_watts=100,
        )
        assert metrics.vram_percent == 50.0

    def test_vram_percentage_full(self):
        """Test VRAM percentage when fully utilized."""
        metrics = GpuMetrics(
            name="RTX",
            utilization=100,
            vram_used_gb=24.0,
            vram_total_gb=24.0,
            temperature=85,
            power_watts=350,
        )
        assert metrics.vram_percent == 100.0

    def test_utilization_validation_ge_zero(self):
        """Test utilization must be >= 0."""
        with pytest.raises(ValueError):
            GpuMetrics(
                name="RTX",
                utilization=-1.0,
                vram_used_gb=12.0,
                vram_total_gb=24.0,
                temperature=40,
                power_watts=100,
            )

    def test_utilization_validation_le_100(self):
        """Test utilization must be <= 100."""
        with pytest.raises(ValueError):
            GpuMetrics(
                name="RTX",
                utilization=101.0,
                vram_used_gb=12.0,
                vram_total_gb=24.0,
                temperature=40,
                power_watts=100,
            )


class TestAiModelMetrics:
    """Tests for AI model metrics schemas."""

    def test_rtdetr_metrics(self):
        """Test RT-DETRv2 metrics creation."""
        metrics = AiModelMetrics(
            status="healthy",
            vram_gb=0.17,
            model="rtdetr_r50vd_coco_o365",
            device="cuda:0",
        )
        assert metrics.status == "healthy"
        assert metrics.vram_gb == 0.17
        assert metrics.model == "rtdetr_r50vd_coco_o365"
        assert metrics.device == "cuda:0"

    def test_nemotron_metrics(self):
        """Test Nemotron metrics creation."""
        metrics = NemotronMetrics(
            status="healthy",
            slots_active=1,
            slots_total=2,
            context_size=4096,
        )
        assert metrics.status == "healthy"
        assert metrics.slots_active == 1
        assert metrics.slots_total == 2
        assert metrics.context_size == 4096

    def test_nemotron_metrics_all_slots_active(self):
        """Test Nemotron metrics with all slots active."""
        metrics = NemotronMetrics(
            status="healthy",
            slots_active=4,
            slots_total=4,
            context_size=8192,
        )
        assert metrics.slots_active == metrics.slots_total


class TestInferenceMetrics:
    """Tests for InferenceMetrics schema."""

    def test_inference_metrics_creation(self):
        """Test creating inference metrics."""
        metrics = InferenceMetrics(
            rtdetr_latency_ms={"avg": 45, "p95": 82, "p99": 120},
            nemotron_latency_ms={"avg": 2100, "p95": 4800, "p99": 8200},
            pipeline_latency_ms={"avg": 3200, "p95": 6100},
            throughput={"images_per_min": 12.4, "events_per_min": 2.1},
            queues={"detection": 0, "analysis": 0},
        )
        assert metrics.rtdetr_latency_ms["avg"] == 45
        assert metrics.nemotron_latency_ms["p95"] == 4800
        assert metrics.throughput["images_per_min"] == 12.4
        assert metrics.queues["detection"] == 0


class TestDatabaseMetrics:
    """Tests for DatabaseMetrics schema."""

    def test_postgresql_metrics(self):
        """Test PostgreSQL metrics creation."""
        metrics = DatabaseMetrics(
            status="healthy",
            connections_active=5,
            connections_max=30,
            cache_hit_ratio=98.2,
            transactions_per_min=1200,
        )
        assert metrics.status == "healthy"
        assert metrics.connections_active == 5
        assert metrics.connections_max == 30
        assert metrics.cache_hit_ratio == 98.2
        assert metrics.transactions_per_min == 1200

    def test_cache_hit_ratio_validation(self):
        """Test cache hit ratio must be between 0 and 100."""
        with pytest.raises(ValueError):
            DatabaseMetrics(
                status="healthy",
                connections_active=5,
                connections_max=30,
                cache_hit_ratio=101.0,
                transactions_per_min=1200,
            )


class TestRedisMetrics:
    """Tests for RedisMetrics schema."""

    def test_redis_metrics(self):
        """Test Redis metrics creation."""
        metrics = RedisMetrics(
            status="healthy",
            connected_clients=8,
            memory_mb=1.5,
            hit_ratio=99.5,
            blocked_clients=0,
        )
        assert metrics.status == "healthy"
        assert metrics.connected_clients == 8
        assert metrics.memory_mb == 1.5
        assert metrics.hit_ratio == 99.5
        assert metrics.blocked_clients == 0


class TestHostMetrics:
    """Tests for HostMetrics schema."""

    def test_host_metrics(self):
        """Test host metrics creation."""
        metrics = HostMetrics(
            cpu_percent=12,
            ram_used_gb=8.2,
            ram_total_gb=32,
            disk_used_gb=156,
            disk_total_gb=500,
        )
        assert metrics.cpu_percent == 12
        assert metrics.ram_used_gb == 8.2
        assert metrics.ram_total_gb == 32
        assert metrics.disk_used_gb == 156
        assert metrics.disk_total_gb == 500

    def test_ram_percent(self):
        """Test RAM percentage calculation."""
        metrics = HostMetrics(
            cpu_percent=12,
            ram_used_gb=16.0,
            ram_total_gb=32.0,
            disk_used_gb=156,
            disk_total_gb=500,
        )
        assert metrics.ram_percent == 50.0

    def test_disk_percent(self):
        """Test disk percentage calculation."""
        metrics = HostMetrics(
            cpu_percent=12,
            ram_used_gb=8.2,
            ram_total_gb=32,
            disk_used_gb=250.0,
            disk_total_gb=500.0,
        )
        assert metrics.disk_percent == 50.0


class TestContainerMetrics:
    """Tests for ContainerMetrics schema."""

    def test_healthy_container(self):
        """Test healthy container metrics."""
        metrics = ContainerMetrics(name="backend", status="running", health="healthy")
        assert metrics.name == "backend"
        assert metrics.status == "running"
        assert metrics.health == "healthy"

    def test_unhealthy_container(self):
        """Test unhealthy container metrics."""
        metrics = ContainerMetrics(name="ai-llm", status="running", health="unhealthy")
        assert metrics.health == "unhealthy"


class TestPerformanceAlert:
    """Tests for alert schema."""

    def test_warning_alert(self):
        """Test creating a warning alert."""
        alert = PerformanceAlert(
            severity="warning",
            metric="gpu_temperature",
            value=82,
            threshold=80,
            message="GPU temperature high: 82C",
        )
        assert alert.severity == "warning"
        assert alert.metric == "gpu_temperature"
        assert alert.value == 82
        assert alert.threshold == 80
        assert "82C" in alert.message

    def test_critical_alert(self):
        """Test creating a critical alert."""
        alert = PerformanceAlert(
            severity="critical",
            metric="vram_usage",
            value=96,
            threshold=95,
            message="VRAM critically high",
        )
        assert alert.severity == "critical"
        assert alert.metric == "vram_usage"
        assert alert.value == 96


class TestPerformanceUpdate:
    """Tests for complete performance update."""

    def test_full_update(self):
        """Test creating a full performance update."""
        update = PerformanceUpdate(
            gpu=GpuMetrics(
                name="RTX",
                utilization=50,
                vram_used_gb=12,
                vram_total_gb=24,
                temperature=40,
                power_watts=100,
            ),
            ai_models={
                "rtdetr": AiModelMetrics(
                    status="healthy", vram_gb=0.17, model="rtdetr", device="cuda:0"
                )
            },
            inference=InferenceMetrics(
                rtdetr_latency_ms={"avg": 45, "p95": 82, "p99": 120},
                nemotron_latency_ms={"avg": 2100, "p95": 4800, "p99": 8200},
                pipeline_latency_ms={"avg": 3200, "p95": 6100},
                throughput={"images_per_min": 12.4, "events_per_min": 2.1},
                queues={"detection": 0, "analysis": 0},
            ),
            databases={
                "postgresql": DatabaseMetrics(
                    status="healthy",
                    connections_active=5,
                    connections_max=30,
                    cache_hit_ratio=98.2,
                    transactions_per_min=1200,
                )
            },
            host=HostMetrics(
                cpu_percent=12,
                ram_used_gb=8.2,
                ram_total_gb=32,
                disk_used_gb=156,
                disk_total_gb=500,
            ),
            containers=[ContainerMetrics(name="backend", status="running", health="healthy")],
            alerts=[],
        )
        assert update.gpu.utilization == 50
        assert update.timestamp is not None
        assert "rtdetr" in update.ai_models
        assert len(update.containers) == 1

    def test_minimal_update(self):
        """Test creating a minimal update with optional fields."""
        update = PerformanceUpdate()
        assert update.gpu is None
        assert update.host is None
        assert update.alerts == []
        assert update.timestamp is not None

    def test_update_with_alerts(self):
        """Test update containing alerts."""
        update = PerformanceUpdate(
            alerts=[
                PerformanceAlert(
                    severity="warning",
                    metric="cpu",
                    value=85,
                    threshold=80,
                    message="CPU high",
                ),
                PerformanceAlert(
                    severity="critical",
                    metric="ram",
                    value=96,
                    threshold=95,
                    message="RAM critical",
                ),
            ]
        )
        assert len(update.alerts) == 2
        assert update.alerts[0].severity == "warning"
        assert update.alerts[1].severity == "critical"


class TestTimeRange:
    """Tests for time range enum."""

    def test_time_ranges(self):
        """Test time range enum values."""
        assert TimeRange.FIVE_MIN.value == "5m"
        assert TimeRange.FIFTEEN_MIN.value == "15m"
        assert TimeRange.SIXTY_MIN.value == "60m"

    def test_time_range_is_string_enum(self):
        """Test time range is a string enum."""
        assert isinstance(TimeRange.FIVE_MIN, str)
        assert TimeRange.FIVE_MIN == "5m"
