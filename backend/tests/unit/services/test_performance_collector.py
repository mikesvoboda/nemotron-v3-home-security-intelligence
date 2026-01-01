"""Unit tests for performance collector service.

Tests cover:
- PerformanceCollector initialization
- Alert thresholds configuration
"""

from unittest.mock import MagicMock, patch

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
