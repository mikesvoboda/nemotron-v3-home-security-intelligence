"""Unit tests for PerformanceCollector service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.performance_collector import PerformanceCollector


@pytest.fixture
def collector():
    """Create a PerformanceCollector instance with mocked pynvml."""
    with patch("services.performance_collector.PerformanceCollector._init_pynvml"):
        collector = PerformanceCollector()
        collector._pynvml_available = False
        return collector


class TestGpuMetrics:
    """Tests for GPU metrics collection."""

    @pytest.mark.asyncio
    async def test_collect_gpu_metrics_with_pynvml(self, collector):
        """Test GPU metrics collection via pynvml."""
        with patch.object(collector, "_collect_gpu_pynvml") as mock_gpu:
            mock_gpu.return_value = {
                "name": "NVIDIA RTX A5500",
                "utilization": 38.0,
                "vram_used_gb": 22.7,
                "vram_total_gb": 24.0,
                "temperature": 38,
                "power_watts": 31,
            }
            metrics = await collector.collect_gpu_metrics()
            assert metrics is not None
            assert metrics.name == "NVIDIA RTX A5500"
            assert metrics.utilization == 38.0

    @pytest.mark.asyncio
    async def test_collect_gpu_metrics_fallback(self, collector):
        """Test GPU metrics fallback when pynvml unavailable."""
        with (
            patch.object(collector, "_collect_gpu_pynvml", return_value=None),
            patch.object(collector, "_collect_gpu_fallback") as mock_fallback,
        ):
            mock_fallback.return_value = {
                "name": "Unknown GPU",
                "utilization": 0,
                "vram_used_gb": 0,
                "vram_total_gb": 24.0,
                "temperature": 0,
                "power_watts": 0,
            }
            metrics = await collector.collect_gpu_metrics()
            assert metrics is not None
            mock_fallback.assert_called_once()

    @pytest.mark.asyncio
    async def test_collect_gpu_metrics_returns_none_on_failure(self, collector):
        """Test GPU metrics returns None when all collection methods fail."""
        with (
            patch.object(collector, "_collect_gpu_pynvml", return_value=None),
            patch.object(collector, "_collect_gpu_fallback", return_value=None),
        ):
            metrics = await collector.collect_gpu_metrics()
            assert metrics is None


class TestAiModelMetrics:
    """Tests for AI model metrics collection."""

    @pytest.mark.asyncio
    async def test_collect_rtdetr_metrics_healthy(self, collector):
        """Test RT-DETRv2 metrics collection when healthy."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "healthy",
            "vram_used_gb": 0.17,
            "model_name": "rtdetr_r50vd_coco_o365",
            "device": "cuda:0",
        }

        with patch.object(collector, "_get_http_client") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client.return_value = mock_client_instance

            metrics = await collector.collect_rtdetr_metrics()
            assert metrics is not None
            assert metrics.status == "healthy"

    @pytest.mark.asyncio
    async def test_collect_rtdetr_metrics_unreachable(self, collector):
        """Test RT-DETRv2 metrics when service is unreachable."""
        with patch.object(collector, "_get_http_client") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.side_effect = Exception("Connection refused")
            mock_client.return_value = mock_client_instance

            metrics = await collector.collect_rtdetr_metrics()
            assert metrics is not None
            assert metrics.status == "unreachable"

    @pytest.mark.asyncio
    async def test_collect_nemotron_metrics_healthy(self, collector):
        """Test Nemotron metrics collection when healthy."""
        mock_slots = [
            {"state": 0, "n_ctx": 4096},
            {"state": 1, "n_ctx": 4096},
        ]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_slots

        with patch.object(collector, "_get_http_client") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client.return_value = mock_client_instance

            metrics = await collector.collect_nemotron_metrics()
            assert metrics is not None
            assert metrics.status == "healthy"
            assert metrics.slots_total == 2
            assert metrics.context_size == 4096

    @pytest.mark.asyncio
    async def test_collect_nemotron_metrics_all_slots_active(self, collector):
        """Test Nemotron metrics when all slots are active."""
        mock_slots = [
            {"state": 1, "n_ctx": 8192},
            {"state": 1, "n_ctx": 8192},
            {"state": 1, "n_ctx": 8192},
        ]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_slots

        with patch.object(collector, "_get_http_client") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client.return_value = mock_client_instance

            metrics = await collector.collect_nemotron_metrics()
            assert metrics.slots_active == 3
            assert metrics.slots_total == 3


class TestHostMetrics:
    """Tests for host system metrics."""

    @pytest.mark.asyncio
    async def test_collect_host_metrics(self, collector):
        """Test host metrics collection via psutil."""
        with patch("services.performance_collector.psutil") as mock_psutil:
            mock_psutil.cpu_percent.return_value = 12.5

            mock_mem = MagicMock()
            mock_mem.used = 8_800_000_000  # ~8.2 GB
            mock_mem.total = 34_359_738_368  # 32 GB
            mock_psutil.virtual_memory.return_value = mock_mem

            mock_disk = MagicMock()
            mock_disk.used = 167_503_724_544  # ~156 GB
            mock_disk.total = 536_870_912_000  # 500 GB
            mock_psutil.disk_usage.return_value = mock_disk

            metrics = await collector.collect_host_metrics()
            assert metrics is not None
            assert metrics.cpu_percent == 12.5
            assert metrics.ram_total_gb == pytest.approx(32.0, rel=0.1)

    @pytest.mark.asyncio
    async def test_collect_host_metrics_failure(self, collector):
        """Test host metrics returns None on failure."""
        with patch("services.performance_collector.psutil") as mock_psutil:
            mock_psutil.cpu_percent.side_effect = Exception("psutil error")

            metrics = await collector.collect_host_metrics()
            assert metrics is None


class TestDatabaseMetrics:
    """Tests for database metrics."""

    @pytest.mark.asyncio
    async def test_collect_postgresql_metrics(self, collector):
        """Test PostgreSQL metrics collection."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.side_effect = [5, 98.2, 1200]  # active, cache_hit, txns
        mock_session.execute.return_value = mock_result

        mock_session_factory = MagicMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        with patch("core.database.get_session_factory", return_value=mock_session_factory):
            metrics = await collector.collect_postgresql_metrics()
            assert metrics is not None
            assert metrics.status == "healthy"
            assert metrics.connections_active == 5

    @pytest.mark.asyncio
    async def test_collect_postgresql_metrics_failure(self, collector):
        """Test PostgreSQL metrics returns unreachable on failure."""
        with patch(
            "core.database.get_session_factory", side_effect=RuntimeError("DB not initialized")
        ):
            metrics = await collector.collect_postgresql_metrics()
            assert metrics is not None
            assert metrics.status == "unreachable"

    @pytest.mark.asyncio
    async def test_collect_redis_metrics(self, collector):
        """Test Redis metrics collection."""
        mock_info = {
            "connected_clients": 8,
            "used_memory": 1_509_949,
            "keyspace_hits": 9900,
            "keyspace_misses": 100,
            "blocked_clients": 2,
        }

        mock_redis = AsyncMock()
        mock_redis.info = AsyncMock(return_value=mock_info)

        with patch(
            "core.redis.get_redis_optional", new_callable=AsyncMock, return_value=mock_redis
        ):
            metrics = await collector.collect_redis_metrics()
            assert metrics is not None
            assert metrics.status == "healthy"
            assert metrics.connected_clients == 8
            assert metrics.hit_ratio == pytest.approx(99.0, rel=0.1)

    @pytest.mark.asyncio
    async def test_collect_redis_metrics_failure(self, collector):
        """Test Redis metrics returns unreachable on failure."""
        mock_redis = AsyncMock()
        mock_redis.info = AsyncMock(side_effect=Exception("Redis error"))

        with patch(
            "core.redis.get_redis_optional", new_callable=AsyncMock, return_value=mock_redis
        ):
            metrics = await collector.collect_redis_metrics()
            assert metrics is not None
            assert metrics.status == "unreachable"

    @pytest.mark.asyncio
    async def test_collect_redis_metrics_no_client(self, collector):
        """Test Redis metrics returns unreachable when client unavailable."""
        with patch("core.redis.get_redis_optional", new_callable=AsyncMock, return_value=None):
            metrics = await collector.collect_redis_metrics()
            assert metrics is not None
            assert metrics.status == "unreachable"


class TestAlertGeneration:
    """Tests for alert threshold checking."""

    def test_gpu_temperature_warning(self, collector):
        """Test GPU temperature warning alert."""
        from api.schemas.performance import GpuMetrics

        gpu = GpuMetrics(
            name="RTX",
            utilization=50,
            vram_used_gb=12,
            vram_total_gb=24,
            temperature=78,
            power_watts=200,
        )
        alerts = collector.check_gpu_alerts(gpu)
        assert len(alerts) == 1
        assert alerts[0].severity == "warning"
        assert "temperature" in alerts[0].metric

    def test_gpu_temperature_critical(self, collector):
        """Test GPU temperature critical alert."""
        from api.schemas.performance import GpuMetrics

        gpu = GpuMetrics(
            name="RTX",
            utilization=50,
            vram_used_gb=12,
            vram_total_gb=24,
            temperature=88,
            power_watts=200,
        )
        alerts = collector.check_gpu_alerts(gpu)
        assert len(alerts) == 1
        assert alerts[0].severity == "critical"

    def test_gpu_vram_warning(self, collector):
        """Test GPU VRAM warning alert."""
        from api.schemas.performance import GpuMetrics

        gpu = GpuMetrics(
            name="RTX",
            utilization=50,
            vram_used_gb=22.0,  # 91.7%
            vram_total_gb=24,
            temperature=40,
            power_watts=200,
        )
        alerts = collector.check_gpu_alerts(gpu)
        assert len(alerts) == 1
        assert alerts[0].severity == "warning"
        assert "vram" in alerts[0].metric

    def test_no_alerts_when_healthy(self, collector):
        """Test no alerts when metrics are healthy."""
        from api.schemas.performance import GpuMetrics

        gpu = GpuMetrics(
            name="RTX",
            utilization=50,
            vram_used_gb=12,
            vram_total_gb=24,
            temperature=40,
            power_watts=100,
        )
        alerts = collector.check_gpu_alerts(gpu)
        assert len(alerts) == 0

    def test_host_cpu_warning(self, collector):
        """Test host CPU warning alert."""
        from api.schemas.performance import HostMetrics

        host = HostMetrics(
            cpu_percent=82,
            ram_used_gb=8,
            ram_total_gb=32,
            disk_used_gb=100,
            disk_total_gb=500,
        )
        alerts = collector.check_host_alerts(host)
        assert len(alerts) == 1
        assert alerts[0].severity == "warning"
        assert "cpu" in alerts[0].metric

    def test_host_ram_critical(self, collector):
        """Test host RAM critical alert."""
        from api.schemas.performance import HostMetrics

        host = HostMetrics(
            cpu_percent=50,
            ram_used_gb=31,  # 96.9%
            ram_total_gb=32,
            disk_used_gb=100,
            disk_total_gb=500,
        )
        alerts = collector.check_host_alerts(host)
        assert len(alerts) == 1
        assert alerts[0].severity == "critical"
        assert "ram" in alerts[0].metric


class TestFullCollection:
    """Tests for full metrics collection."""

    @pytest.mark.asyncio
    async def test_collect_all(self, collector):
        """Test collecting all metrics."""
        with patch.object(collector, "collect_gpu_metrics", new_callable=AsyncMock) as mock_gpu:
            mock_gpu.return_value = None

            with patch.object(
                collector, "collect_rtdetr_metrics", new_callable=AsyncMock
            ) as mock_rtdetr:
                mock_rtdetr.return_value = None

                with patch.object(
                    collector, "collect_nemotron_metrics", new_callable=AsyncMock
                ) as mock_nemotron:
                    mock_nemotron.return_value = None

                    with patch.object(
                        collector, "collect_host_metrics", new_callable=AsyncMock
                    ) as mock_host:
                        mock_host.return_value = None

                        with patch.object(
                            collector,
                            "collect_postgresql_metrics",
                            new_callable=AsyncMock,
                        ) as mock_pg:
                            mock_pg.return_value = None

                            with patch.object(
                                collector,
                                "collect_redis_metrics",
                                new_callable=AsyncMock,
                            ) as mock_redis:
                                mock_redis.return_value = None

                                with patch.object(
                                    collector,
                                    "collect_container_health",
                                    new_callable=AsyncMock,
                                ) as mock_containers:
                                    mock_containers.return_value = []

                                    with patch.object(
                                        collector,
                                        "collect_inference_metrics",
                                        new_callable=AsyncMock,
                                    ) as mock_inference:
                                        mock_inference.return_value = None

                                        update = await collector.collect_all()
                                        assert update is not None
                                        assert update.timestamp is not None

    @pytest.mark.asyncio
    async def test_collect_all_with_metrics(self, collector):
        """Test collecting all metrics with real data."""
        from api.schemas.performance import (
            AiModelMetrics,
            ContainerMetrics,
            DatabaseMetrics,
            GpuMetrics,
            HostMetrics,
            NemotronMetrics,
            RedisMetrics,
        )

        gpu = GpuMetrics(
            name="RTX",
            utilization=50,
            vram_used_gb=12,
            vram_total_gb=24,
            temperature=78,  # Will trigger warning
            power_watts=100,
        )

        with (
            patch.object(
                collector, "collect_gpu_metrics", new_callable=AsyncMock, return_value=gpu
            ),
            patch.object(
                collector,
                "collect_rtdetr_metrics",
                new_callable=AsyncMock,
                return_value=AiModelMetrics(
                    status="healthy", vram_gb=0.17, model="rtdetr", device="cuda:0"
                ),
            ),
            patch.object(
                collector,
                "collect_nemotron_metrics",
                new_callable=AsyncMock,
                return_value=NemotronMetrics(
                    status="healthy",
                    slots_active=1,
                    slots_total=2,
                    context_size=4096,
                ),
            ),
            patch.object(
                collector,
                "collect_host_metrics",
                new_callable=AsyncMock,
                return_value=HostMetrics(
                    cpu_percent=12,
                    ram_used_gb=8,
                    ram_total_gb=32,
                    disk_used_gb=100,
                    disk_total_gb=500,
                ),
            ),
            patch.object(
                collector,
                "collect_postgresql_metrics",
                new_callable=AsyncMock,
                return_value=DatabaseMetrics(
                    status="healthy",
                    connections_active=5,
                    connections_max=30,
                    cache_hit_ratio=98.2,
                    transactions_per_min=1200,
                ),
            ),
            patch.object(
                collector,
                "collect_redis_metrics",
                new_callable=AsyncMock,
                return_value=RedisMetrics(
                    status="healthy",
                    connected_clients=8,
                    memory_mb=1.5,
                    hit_ratio=99.0,
                    blocked_clients=0,
                ),
            ),
            patch.object(
                collector,
                "collect_container_health",
                new_callable=AsyncMock,
                return_value=[
                    ContainerMetrics(
                        name="backend",
                        status="running",
                        health="healthy",
                    )
                ],
            ),
            patch.object(
                collector,
                "collect_inference_metrics",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            update = await collector.collect_all()
            assert update.gpu is not None
            assert update.gpu.utilization == 50
            assert "rtdetr" in update.ai_models
            assert "nemotron" in update.ai_models
            assert "postgresql" in update.databases
            assert "redis" in update.databases
            assert len(update.containers) == 1
            # GPU temp is 78, should trigger warning
            assert len(update.alerts) == 1
            assert update.alerts[0].severity == "warning"


class TestResourceCleanup:
    """Tests for resource cleanup."""

    @pytest.mark.asyncio
    async def test_close_resources(self, collector):
        """Test closing HTTP client."""
        mock_client = AsyncMock()
        mock_client.is_closed = False
        collector._http_client = mock_client

        await collector.close()

        mock_client.aclose.assert_awaited_once()
