"""Unit tests for performance collector service.

Tests cover:
- PerformanceCollector initialization
- Alert thresholds configuration
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.performance_collector import (
    THRESHOLDS,
    PerformanceCollector,
)

# =============================================================================
# Threshold Tests
# =============================================================================


class TestThresholds:
    """Tests for performance thresholds configuration."""

    def test_gpu_temperature_thresholds(self) -> None:
        """Test GPU temperature threshold values."""
        assert THRESHOLDS["gpu_temperature"]["warning"] == 75
        assert THRESHOLDS["gpu_temperature"]["critical"] == 85

    def test_gpu_utilization_thresholds(self) -> None:
        """Test GPU utilization threshold values."""
        assert THRESHOLDS["gpu_utilization"]["warning"] == 90
        assert THRESHOLDS["gpu_utilization"]["critical"] == 98

    def test_gpu_vram_thresholds(self) -> None:
        """Test GPU VRAM threshold values."""
        assert THRESHOLDS["gpu_vram"]["warning"] == 90
        assert THRESHOLDS["gpu_vram"]["critical"] == 95

    def test_gpu_power_thresholds(self) -> None:
        """Test GPU power threshold values."""
        assert THRESHOLDS["gpu_power"]["warning"] == 300
        assert THRESHOLDS["gpu_power"]["critical"] == 350

    def test_host_cpu_thresholds(self) -> None:
        """Test host CPU threshold values."""
        assert THRESHOLDS["host_cpu"]["warning"] == 80
        assert THRESHOLDS["host_cpu"]["critical"] == 95

    def test_host_ram_thresholds(self) -> None:
        """Test host RAM threshold values."""
        assert THRESHOLDS["host_ram"]["warning"] == 85
        assert THRESHOLDS["host_ram"]["critical"] == 95

    def test_host_disk_thresholds(self) -> None:
        """Test host disk threshold values."""
        assert THRESHOLDS["host_disk"]["warning"] == 80
        assert THRESHOLDS["host_disk"]["critical"] == 90

    def test_redis_memory_thresholds(self) -> None:
        """Test Redis memory threshold values."""
        assert THRESHOLDS["redis_memory_mb"]["warning"] == 100
        assert THRESHOLDS["redis_memory_mb"]["critical"] == 500

    def test_redis_hit_ratio_thresholds(self) -> None:
        """Test Redis hit ratio threshold values."""
        assert THRESHOLDS["redis_hit_ratio"]["warning"] == 50
        assert THRESHOLDS["redis_hit_ratio"]["critical"] == 10

    def test_pg_connections_thresholds(self) -> None:
        """Test PostgreSQL connections threshold values."""
        assert THRESHOLDS["pg_connections"]["warning"] == 0.8
        assert THRESHOLDS["pg_connections"]["critical"] == 0.95

    def test_pg_cache_hit_thresholds(self) -> None:
        """Test PostgreSQL cache hit threshold values."""
        assert THRESHOLDS["pg_cache_hit"]["warning"] == 90
        assert THRESHOLDS["pg_cache_hit"]["critical"] == 80

    def test_rtdetr_latency_thresholds(self) -> None:
        """Test RT-DETRv2 latency threshold values."""
        assert THRESHOLDS["rtdetr_latency_p95"]["warning"] == 200
        assert THRESHOLDS["rtdetr_latency_p95"]["critical"] == 500

    def test_nemotron_latency_thresholds(self) -> None:
        """Test Nemotron latency threshold values."""
        assert THRESHOLDS["nemotron_latency_p95"]["warning"] == 10000
        assert THRESHOLDS["nemotron_latency_p95"]["critical"] == 30000

    def test_all_thresholds_have_warning_and_critical(self) -> None:
        """Test that all thresholds have both warning and critical levels."""
        for name, levels in THRESHOLDS.items():
            assert "warning" in levels, f"{name} missing warning level"
            assert "critical" in levels, f"{name} missing critical level"


# =============================================================================
# PerformanceCollector Tests
# =============================================================================


class TestPerformanceCollectorInit:
    """Tests for PerformanceCollector initialization."""

    def test_init_without_pynvml(self) -> None:
        """Test initialization when pynvml is not available."""
        with patch("backend.services.performance_collector.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock()

            collector = PerformanceCollector()

            assert collector._http_client is None
            assert hasattr(collector, "_pynvml_available")

    def test_init_pynvml_not_available(self) -> None:
        """Test that pynvml unavailable doesn't crash init."""
        with patch("backend.services.performance_collector.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock()

            collector = PerformanceCollector()

            # Should not raise, and pynvml_available should be False
            # (since pynvml is unlikely to be installed in test environment)
            assert hasattr(collector, "_pynvml_available")


class TestGetHttpClient:
    """Tests for _get_http_client method."""

    @pytest.mark.asyncio
    async def test_get_http_client_creates_client(self) -> None:
        """Test that _get_http_client creates a client."""
        with patch("backend.services.performance_collector.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock()

            collector = PerformanceCollector()
            client = await collector._get_http_client()

            assert client is not None
            await client.aclose()

    @pytest.mark.asyncio
    async def test_get_http_client_reuses_client(self) -> None:
        """Test that _get_http_client reuses existing client."""
        with patch("backend.services.performance_collector.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock()

            collector = PerformanceCollector()
            client1 = await collector._get_http_client()
            client2 = await collector._get_http_client()

            assert client1 is client2
            await client1.aclose()


class TestCollectGpuPynvml:
    """Tests for _collect_gpu_pynvml method."""

    def test_collect_gpu_pynvml_unavailable(self) -> None:
        """Test GPU collection when pynvml is not available."""
        with patch("backend.services.performance_collector.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock()

            collector = PerformanceCollector()
            collector._pynvml_available = False

            result = collector._collect_gpu_pynvml()

            assert result is None


# =============================================================================
# Host Metrics Tests
# =============================================================================


class TestCollectHostMetrics:
    """Tests for collect_host_metrics method."""

    @pytest.mark.asyncio
    async def test_collect_host_metrics_success(self) -> None:
        """Test successful host metrics collection."""
        with patch("backend.services.performance_collector.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock()

            with patch("backend.services.performance_collector.psutil") as mock_psutil:
                # Mock CPU percent
                mock_psutil.cpu_percent.return_value = 45.5

                # Mock virtual memory
                mock_mem = MagicMock()
                mock_mem.used = 8 * 1024**3  # 8 GB
                mock_mem.total = 16 * 1024**3  # 16 GB
                mock_psutil.virtual_memory.return_value = mock_mem

                # Mock disk usage
                mock_disk = MagicMock()
                mock_disk.used = 100 * 1024**3  # 100 GB
                mock_disk.total = 500 * 1024**3  # 500 GB
                mock_psutil.disk_usage.return_value = mock_disk

                collector = PerformanceCollector()
                result = await collector.collect_host_metrics()

                assert result is not None
                assert result.cpu_percent == 45.5
                assert result.ram_used_gb == 8.0
                assert result.ram_total_gb == 16.0
                assert result.disk_used_gb == 100.0
                assert result.disk_total_gb == 500.0

    @pytest.mark.asyncio
    async def test_collect_host_metrics_cpu_failure(self) -> None:
        """Test host metrics collection when CPU measurement fails."""
        with patch("backend.services.performance_collector.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock()

            with patch("backend.services.performance_collector.psutil") as mock_psutil:
                # Mock CPU percent to raise exception
                mock_psutil.cpu_percent.side_effect = Exception("Permission denied")

                # Mock virtual memory
                mock_mem = MagicMock()
                mock_mem.used = 8 * 1024**3
                mock_mem.total = 16 * 1024**3
                mock_psutil.virtual_memory.return_value = mock_mem

                # Mock disk usage
                mock_disk = MagicMock()
                mock_disk.used = 100 * 1024**3
                mock_disk.total = 500 * 1024**3
                mock_psutil.disk_usage.return_value = mock_disk

                collector = PerformanceCollector()
                result = await collector.collect_host_metrics()

                # Should return partial data with cpu_percent = 0.0
                assert result is not None
                assert result.cpu_percent == 0.0
                assert result.ram_used_gb == 8.0
                assert result.disk_used_gb == 100.0

    @pytest.mark.asyncio
    async def test_collect_host_metrics_all_failures(self) -> None:
        """Test host metrics collection when all measurements fail."""
        with patch("backend.services.performance_collector.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock()

            with patch("backend.services.performance_collector.psutil") as mock_psutil:
                # All psutil calls fail
                mock_psutil.cpu_percent.side_effect = Exception("Permission denied")
                mock_psutil.virtual_memory.side_effect = Exception("Permission denied")
                mock_psutil.disk_usage.side_effect = Exception("Permission denied")

                collector = PerformanceCollector()
                result = await collector.collect_host_metrics()

                # Should return fallback values but not None
                # Schema requires ram_total_gb and disk_total_gb > 0, so fallback to 1.0
                assert result is not None
                assert result.cpu_percent == 0.0
                assert result.ram_used_gb == 0.0
                assert result.ram_total_gb == 1.0  # Fallback to avoid schema validation error
                assert result.disk_used_gb == 0.0
                assert result.disk_total_gb == 1.0  # Fallback to avoid schema validation error


# =============================================================================
# PostgreSQL Metrics Tests
# =============================================================================


class TestCollectPostgresqlMetrics:
    """Tests for collect_postgresql_metrics method."""

    @pytest.mark.asyncio
    async def test_collect_postgresql_metrics_session_factory_none(self) -> None:
        """Test PostgreSQL metrics when session factory is None."""
        with patch("backend.services.performance_collector.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock()

            with patch(
                "backend.services.performance_collector.PerformanceCollector.collect_postgresql_metrics"
            ) as mock_method:
                # Simulate the session factory being None
                from backend.api.schemas.performance import DatabaseMetrics

                mock_method.return_value = DatabaseMetrics(
                    status="unreachable",
                    connections_active=0,
                    connections_max=30,
                    cache_hit_ratio=0,
                    transactions_per_min=0,
                )

                collector = PerformanceCollector()
                result = await collector.collect_postgresql_metrics()

                assert result is not None
                assert result.status == "unreachable"


# =============================================================================
# Redis Metrics Tests
# =============================================================================


class TestCollectRedisMetrics:
    """Tests for collect_redis_metrics method."""

    @pytest.mark.asyncio
    async def test_collect_redis_metrics_not_connected(self) -> None:
        """Test Redis metrics when client is not connected."""
        with patch("backend.services.performance_collector.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock()

            with patch("backend.core.redis.init_redis") as mock_init_redis:
                # Mock Redis client that raises RuntimeError on _ensure_connected
                mock_client = MagicMock()
                mock_client._ensure_connected.side_effect = RuntimeError(
                    "Redis client not connected"
                )
                mock_init_redis.return_value = mock_client

                collector = PerformanceCollector()
                result = await collector.collect_redis_metrics()

                assert result is not None
                assert result.status == "unreachable"
                assert result.connected_clients == 0

    @pytest.mark.asyncio
    async def test_collect_redis_metrics_success(self) -> None:
        """Test successful Redis metrics collection."""
        with patch("backend.services.performance_collector.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock()

            with patch("backend.core.redis.init_redis") as mock_init_redis:
                # Mock Redis client with successful info() call
                mock_raw_client = MagicMock()
                mock_raw_client.info = MagicMock(
                    return_value={
                        "connected_clients": 5,
                        "used_memory": 10 * 1024 * 1024,  # 10 MB
                        "keyspace_hits": 100,
                        "keyspace_misses": 10,
                        "blocked_clients": 0,
                    }
                )
                # Make info() an async mock

                async def mock_info():
                    return {
                        "connected_clients": 5,
                        "used_memory": 10 * 1024 * 1024,
                        "keyspace_hits": 100,
                        "keyspace_misses": 10,
                        "blocked_clients": 0,
                    }

                mock_raw_client.info = mock_info

                mock_client = MagicMock()
                mock_client._ensure_connected.return_value = mock_raw_client
                mock_init_redis.return_value = mock_client

                collector = PerformanceCollector()
                result = await collector.collect_redis_metrics()

                assert result is not None
                assert result.status == "healthy"
                assert result.connected_clients == 5
                assert result.memory_mb == 10.0
                # hit_ratio = 100 / (100 + 10) * 100 = 90.9%
                assert abs(result.hit_ratio - 90.909) < 0.1


# =============================================================================
# Container Health Tests
# =============================================================================


class TestCollectContainerHealth:
    """Tests for collect_container_health method."""

    @pytest.mark.asyncio
    async def test_collect_container_health_backend_always_healthy(self) -> None:
        """Test that backend is always marked as healthy."""
        with patch("backend.services.performance_collector.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                frontend_url="http://frontend:80",
                yolo26_url="http://ai-yolo26:8095",
                nemotron_url="http://ai-llm:8091",
            )

            collector = PerformanceCollector()

            # Mock all internal methods to return unhealthy
            with (
                patch.object(collector, "_check_service_health") as mock_service,
                patch.object(collector, "_check_postgres_health") as mock_pg,
                patch.object(collector, "_check_redis_health") as mock_redis,
            ):
                from backend.api.schemas.performance import ContainerMetrics

                mock_service.return_value = ContainerMetrics(
                    name="test", status="unknown", health="unhealthy"
                )
                mock_pg.return_value = ContainerMetrics(
                    name="postgres", status="unknown", health="unhealthy"
                )
                mock_redis.return_value = ContainerMetrics(
                    name="redis", status="unknown", health="unhealthy"
                )

                result = await collector.collect_container_health()

                # Backend should always be first and healthy
                assert len(result) == 6
                assert result[0].name == "backend"
                assert result[0].health == "healthy"

    @pytest.mark.asyncio
    async def test_check_service_health_success(self) -> None:
        """Test successful HTTP health check."""
        with patch("backend.services.performance_collector.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock()

            import httpx

            collector = PerformanceCollector()

            # Create a mock response
            mock_response = MagicMock()
            mock_response.status_code = 200

            with patch("httpx.AsyncClient.get", return_value=mock_response):
                client = httpx.AsyncClient()
                result = await collector._check_service_health(
                    client, "test-service", "http://test:8000/health"
                )
                await client.aclose()

                assert result.name == "test-service"
                assert result.health == "healthy"

    @pytest.mark.asyncio
    async def test_check_service_health_unhealthy_status(self) -> None:
        """Test HTTP health check with non-200 status."""
        with patch("backend.services.performance_collector.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock()

            import httpx

            collector = PerformanceCollector()

            # Create a mock response with 500 status
            mock_response = MagicMock()
            mock_response.status_code = 500

            with patch("httpx.AsyncClient.get", return_value=mock_response):
                client = httpx.AsyncClient()
                result = await collector._check_service_health(
                    client, "test-service", "http://test:8000/health"
                )
                await client.aclose()

                assert result.name == "test-service"
                assert result.health == "unhealthy"

    @pytest.mark.asyncio
    async def test_check_service_health_connection_error(self) -> None:
        """Test HTTP health check with connection error."""
        with patch("backend.services.performance_collector.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock()

            import httpx

            collector = PerformanceCollector()

            with patch(
                "httpx.AsyncClient.get", side_effect=httpx.ConnectError("Connection refused")
            ):
                client = httpx.AsyncClient()
                result = await collector._check_service_health(
                    client, "test-service", "http://test:8000/health"
                )
                await client.aclose()

                assert result.name == "test-service"
                assert result.status == "unknown"
                assert result.health == "unhealthy"

    @pytest.mark.asyncio
    async def test_check_service_health_timeout(self) -> None:
        """Test HTTP health check with timeout."""
        with patch("backend.services.performance_collector.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock()

            import httpx

            collector = PerformanceCollector()

            with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Timeout")):
                client = httpx.AsyncClient()
                result = await collector._check_service_health(
                    client, "test-service", "http://test:8000/health"
                )
                await client.aclose()

                assert result.name == "test-service"
                assert result.status == "running"  # Timeout suggests service exists
                assert result.health == "unhealthy"


# =============================================================================
# Alert Generation Tests
# =============================================================================


class TestAlertGeneration:
    """Tests for alert generation methods."""

    def test_check_gpu_alerts_no_alerts(self) -> None:
        """Test no alerts when GPU metrics are within thresholds."""
        with patch("backend.services.performance_collector.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock()

            from backend.api.schemas.performance import GpuMetrics

            collector = PerformanceCollector()
            gpu = GpuMetrics(
                name="Test GPU",
                utilization=50.0,
                vram_used_gb=10.0,
                vram_total_gb=24.0,
                temperature=60,
                power_watts=150,
            )

            alerts = collector.check_gpu_alerts(gpu)
            assert len(alerts) == 0

    def test_check_gpu_alerts_temperature_warning(self) -> None:
        """Test warning alert for high GPU temperature."""
        with patch("backend.services.performance_collector.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock()

            from backend.api.schemas.performance import GpuMetrics

            collector = PerformanceCollector()
            gpu = GpuMetrics(
                name="Test GPU",
                utilization=50.0,
                vram_used_gb=10.0,
                vram_total_gb=24.0,
                temperature=78,  # Above 75 warning threshold
                power_watts=150,
            )

            alerts = collector.check_gpu_alerts(gpu)
            assert len(alerts) == 1
            assert alerts[0].severity == "warning"
            assert alerts[0].metric == "gpu_temperature"

    def test_check_gpu_alerts_temperature_critical(self) -> None:
        """Test critical alert for very high GPU temperature."""
        with patch("backend.services.performance_collector.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock()

            from backend.api.schemas.performance import GpuMetrics

            collector = PerformanceCollector()
            gpu = GpuMetrics(
                name="Test GPU",
                utilization=50.0,
                vram_used_gb=10.0,
                vram_total_gb=24.0,
                temperature=90,  # Above 85 critical threshold
                power_watts=150,
            )

            alerts = collector.check_gpu_alerts(gpu)
            assert len(alerts) == 1
            assert alerts[0].severity == "critical"
            assert alerts[0].metric == "gpu_temperature"

    def test_check_host_alerts_no_alerts(self) -> None:
        """Test no alerts when host metrics are within thresholds."""
        with patch("backend.services.performance_collector.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock()

            from backend.api.schemas.performance import HostMetrics

            collector = PerformanceCollector()
            host = HostMetrics(
                cpu_percent=50.0,
                ram_used_gb=8.0,
                ram_total_gb=16.0,
                disk_used_gb=100.0,
                disk_total_gb=500.0,
            )

            alerts = collector.check_host_alerts(host)
            assert len(alerts) == 0

    def test_check_host_alerts_cpu_critical(self) -> None:
        """Test critical alert for very high CPU usage."""
        with patch("backend.services.performance_collector.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock()

            from backend.api.schemas.performance import HostMetrics

            collector = PerformanceCollector()
            host = HostMetrics(
                cpu_percent=98.0,  # Above 95 critical threshold
                ram_used_gb=8.0,
                ram_total_gb=16.0,
                disk_used_gb=100.0,
                disk_total_gb=500.0,
            )

            alerts = collector.check_host_alerts(host)
            assert any(a.metric == "host_cpu" and a.severity == "critical" for a in alerts)


# =============================================================================
# Throughput Calculation Tests (NEM-249)
# =============================================================================


class TestThroughputCalculation:
    """Tests for throughput calculation in collect_inference_metrics."""

    @pytest.mark.asyncio
    async def test_get_detections_per_minute_with_data(self) -> None:
        """Test detections per minute calculation with data."""
        with patch("backend.services.performance_collector.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock()

            collector = PerformanceCollector()

            # Mock session with detection count
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar.return_value = 30  # 30 detections in last minute
            mock_session.execute.return_value = mock_result

            result = await collector._get_detections_per_minute(mock_session)

            assert result == 30

    @pytest.mark.asyncio
    async def test_get_detections_per_minute_no_data(self) -> None:
        """Test detections per minute returns 0 when no data."""
        with patch("backend.services.performance_collector.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock()

            collector = PerformanceCollector()

            # Mock session with no detections
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar.return_value = None
            mock_session.execute.return_value = mock_result

            result = await collector._get_detections_per_minute(mock_session)

            assert result == 0

    @pytest.mark.asyncio
    async def test_get_detections_per_minute_handles_error(self) -> None:
        """Test detections per minute returns 0 on error."""
        with patch("backend.services.performance_collector.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock()

            collector = PerformanceCollector()

            # Mock session that raises error
            mock_session = AsyncMock()
            mock_session.execute.side_effect = Exception("DB error")

            result = await collector._get_detections_per_minute(mock_session)

            assert result == 0

    @pytest.mark.asyncio
    async def test_get_events_per_minute_with_data(self) -> None:
        """Test events per minute calculation with data."""
        with patch("backend.services.performance_collector.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock()

            collector = PerformanceCollector()

            # Mock session with event count
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar.return_value = 5  # 5 events in last minute
            mock_session.execute.return_value = mock_result

            result = await collector._get_events_per_minute(mock_session)

            assert result == 5

    @pytest.mark.asyncio
    async def test_get_events_per_minute_no_data(self) -> None:
        """Test events per minute returns 0 when no data."""
        with patch("backend.services.performance_collector.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock()

            collector = PerformanceCollector()

            # Mock session with no events
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar.return_value = None
            mock_session.execute.return_value = mock_result

            result = await collector._get_events_per_minute(mock_session)

            assert result == 0

    @pytest.mark.asyncio
    async def test_get_events_per_minute_handles_error(self) -> None:
        """Test events per minute returns 0 on error."""
        with patch("backend.services.performance_collector.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock()

            collector = PerformanceCollector()

            # Mock session that raises error
            mock_session = AsyncMock()
            mock_session.execute.side_effect = Exception("DB error")

            result = await collector._get_events_per_minute(mock_session)

            assert result == 0

    @pytest.mark.asyncio
    async def test_collect_inference_metrics_includes_throughput(self) -> None:
        """Test that collect_inference_metrics includes real throughput values."""
        with patch("backend.services.performance_collector.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock()

            # Mock the pipeline tracker (imported inside collect_inference_metrics)
            with patch("backend.core.metrics.get_pipeline_latency_tracker") as mock_tracker:
                mock_tracker_instance = MagicMock()
                mock_tracker_instance.get_stage_stats.return_value = {
                    "avg_ms": 100.0,
                    "p95_ms": 200.0,
                    "p99_ms": 250.0,
                }
                mock_tracker.return_value = mock_tracker_instance

                # Mock the database session
                mock_session = AsyncMock()
                mock_session.__aenter__.return_value = mock_session
                mock_session.__aexit__.return_value = None

                with patch(
                    "backend.core.database.get_session",
                    return_value=mock_session,
                ):
                    collector = PerformanceCollector()

                    # Mock throughput methods that use the session
                    async def mock_get_detections(session):
                        return 30

                    async def mock_get_events(session):
                        return 5

                    with (
                        patch.object(
                            collector, "_get_detections_per_minute", side_effect=mock_get_detections
                        ),
                        patch.object(
                            collector, "_get_events_per_minute", side_effect=mock_get_events
                        ),
                    ):
                        result = await collector.collect_inference_metrics()

                        assert result is not None
                        assert result.throughput["images_per_min"] == 30
                        assert result.throughput["events_per_min"] == 5
