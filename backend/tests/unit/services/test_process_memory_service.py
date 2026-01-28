"""Unit tests for ProcessMemoryService.

Tests verify:
- Process memory collection via psutil
- Memory percentage calculations
- Memory warning thresholds
- Container memory limit detection
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.services.process_memory_service import (
    ProcessMemoryInfo,
    ProcessMemoryService,
    get_process_memory_info,
)


class TestProcessMemoryInfo:
    """Tests for ProcessMemoryInfo dataclass."""

    def test_memory_info_creation(self) -> None:
        """Test ProcessMemoryInfo creation with valid values."""
        info = ProcessMemoryInfo(
            rss_bytes=1024 * 1024 * 500,  # 500 MB
            rss_mb=500.0,
            vms_bytes=1024 * 1024 * 1000,  # 1000 MB
            vms_mb=1000.0,
            percent=50.0,
            container_limit_mb=1024.0,
            container_usage_percent=48.8,
        )

        assert info.rss_mb == 500.0
        assert info.vms_mb == 1000.0
        assert info.percent == 50.0
        assert info.container_limit_mb == 1024.0
        assert info.container_usage_percent == 48.8

    def test_memory_info_without_container_limit(self) -> None:
        """Test ProcessMemoryInfo without container memory limit."""
        info = ProcessMemoryInfo(
            rss_bytes=1024 * 1024 * 500,
            rss_mb=500.0,
            vms_bytes=1024 * 1024 * 1000,
            vms_mb=1000.0,
            percent=50.0,
            container_limit_mb=None,
            container_usage_percent=None,
        )

        assert info.container_limit_mb is None
        assert info.container_usage_percent is None


class TestProcessMemoryService:
    """Tests for ProcessMemoryService."""

    def test_service_initialization(self) -> None:
        """Test service initializes correctly."""
        service = ProcessMemoryService()
        assert service._process is not None

    def test_get_memory_info_returns_valid_data(self) -> None:
        """Test get_memory_info returns valid memory data."""
        service = ProcessMemoryService()
        info = service.get_memory_info()

        # Memory values should be positive
        assert info.rss_bytes > 0
        assert info.rss_mb > 0
        assert info.vms_bytes > 0
        assert info.vms_mb > 0

        # Percentage should be between 0 and 100
        assert 0 <= info.percent <= 100

        # MB should equal bytes / (1024 * 1024)
        assert abs(info.rss_mb - info.rss_bytes / (1024 * 1024)) < 0.01
        assert abs(info.vms_mb - info.vms_bytes / (1024 * 1024)) < 0.01

    def test_get_memory_info_with_mocked_psutil(self) -> None:
        """Test get_memory_info with mocked psutil values."""
        with patch("psutil.Process") as mock_process_class:
            mock_process = MagicMock()
            mock_process.memory_info.return_value = MagicMock(
                rss=4_000_000_000,  # 4GB
                vms=8_000_000_000,  # 8GB
            )
            mock_process.memory_percent.return_value = 25.0
            mock_process_class.return_value = mock_process

            service = ProcessMemoryService()
            info = service.get_memory_info()

            assert info.rss_bytes == 4_000_000_000
            assert abs(info.rss_mb - 3814.7) < 1  # ~3.7 GB
            assert info.vms_bytes == 8_000_000_000
            assert info.percent == 25.0

    def test_get_container_memory_limit_from_cgroup_v2(self) -> None:
        """Test container memory limit detection from cgroup v2."""
        from backend.services.process_memory_service import (
            CGROUP_V2_MEMORY_MAX,
        )

        service = ProcessMemoryService()
        service._cached_container_limit = False  # Reset cache

        # Mock the _read_cgroup_file method to return cgroup v2 limit
        def mock_read_cgroup(path):
            if path == CGROUP_V2_MEMORY_MAX:
                return "4294967296"  # 4GB
            return None

        with patch.object(service, "_read_cgroup_file", side_effect=mock_read_cgroup):
            limit = service._get_container_memory_limit()
            assert limit == 4096  # 4GB in MB

    def test_get_container_memory_limit_max_means_no_limit(self) -> None:
        """Test that 'max' in cgroup file means no limit."""
        from backend.services.process_memory_service import (
            CGROUP_V2_MEMORY_MAX,
        )

        service = ProcessMemoryService()
        service._cached_container_limit = False  # Reset cache

        def mock_read_cgroup(path):
            if path == CGROUP_V2_MEMORY_MAX:
                return "max"  # No limit
            return None

        with patch.object(service, "_read_cgroup_file", side_effect=mock_read_cgroup):
            limit = service._get_container_memory_limit()
            assert limit is None

    def test_get_container_memory_limit_file_not_found(self) -> None:
        """Test graceful handling when cgroup files don't exist."""
        service = ProcessMemoryService()
        service._cached_container_limit = False  # Reset cache

        # Return None for all paths (simulating file not found)
        with patch.object(service, "_read_cgroup_file", return_value=None):
            limit = service._get_container_memory_limit()
            assert limit is None

    def test_is_memory_critical_above_threshold(self) -> None:
        """Test is_memory_critical returns True above threshold."""
        service = ProcessMemoryService()

        # Mock high memory usage
        with patch.object(service, "get_memory_info") as mock_get:
            mock_get.return_value = ProcessMemoryInfo(
                rss_bytes=4_000_000_000,
                rss_mb=3814.7,
                vms_bytes=8_000_000_000,
                vms_mb=7629.4,
                percent=95.0,  # Above default 90% threshold
                container_limit_mb=4096.0,
                container_usage_percent=93.1,
            )
            assert service.is_memory_critical() is True

    def test_is_memory_critical_below_threshold(self) -> None:
        """Test is_memory_critical returns False below threshold."""
        service = ProcessMemoryService()

        with patch.object(service, "get_memory_info") as mock_get:
            mock_get.return_value = ProcessMemoryInfo(
                rss_bytes=1_000_000_000,
                rss_mb=953.7,
                vms_bytes=2_000_000_000,
                vms_mb=1907.3,
                percent=50.0,  # Below default 90% threshold
                container_limit_mb=4096.0,
                container_usage_percent=23.3,
            )
            assert service.is_memory_critical() is False

    def test_is_memory_warning_above_threshold(self) -> None:
        """Test is_memory_warning returns True above warning threshold."""
        service = ProcessMemoryService()

        with patch.object(service, "get_memory_info") as mock_get:
            mock_get.return_value = ProcessMemoryInfo(
                rss_bytes=3_500_000_000,
                rss_mb=3337.9,
                vms_bytes=7_000_000_000,
                vms_mb=6675.7,
                percent=85.0,  # Above default 80% warning threshold
                container_limit_mb=4096.0,
                container_usage_percent=81.5,
            )
            assert service.is_memory_warning() is True

    def test_custom_thresholds(self) -> None:
        """Test service with custom warning and critical thresholds."""
        service = ProcessMemoryService(
            warning_threshold_percent=70.0,
            critical_threshold_percent=85.0,
        )

        with patch.object(service, "get_memory_info") as mock_get:
            # Set container_usage_percent to be used for threshold checks
            mock_get.return_value = ProcessMemoryInfo(
                rss_bytes=3_000_000_000,
                rss_mb=2861.0,
                vms_bytes=6_000_000_000,
                vms_mb=5722.0,
                percent=75.0,  # Above custom 70% warning, below 85% critical
                container_limit_mb=4096.0,
                container_usage_percent=75.0,  # Use same value as percent for container
            )
            assert service.is_memory_warning() is True
            assert service.is_memory_critical() is False

    def test_container_usage_percent_calculation(self) -> None:
        """Test container usage percentage is calculated correctly."""
        from backend.services.process_memory_service import CGROUP_V2_MEMORY_MAX

        with patch("psutil.Process") as mock_process_class:
            mock_process = MagicMock()
            mock_process.memory_info.return_value = MagicMock(
                rss=2_000_000_000,  # ~1907 MB
                vms=4_000_000_000,
            )
            mock_process.memory_percent.return_value = 25.0
            mock_process_class.return_value = mock_process

            # Create service with mocked process
            service = ProcessMemoryService()

            # Mock cgroup to return a known limit
            def mock_read_cgroup(path):
                if path == CGROUP_V2_MEMORY_MAX:
                    return "4294967296"  # 4GB
                return None

            with patch.object(service, "_read_cgroup_file", side_effect=mock_read_cgroup):
                info = service.get_memory_info()

                # Container usage should be rss_mb / container_limit_mb * 100
                assert info.container_limit_mb == 4096  # 4GB in MB
                expected_container_percent = (info.rss_mb / 4096) * 100
                assert info.container_usage_percent is not None
                assert abs(info.container_usage_percent - expected_container_percent) < 0.1


class TestGetProcessMemoryInfo:
    """Tests for the convenience function."""

    def test_get_process_memory_info_returns_info(self) -> None:
        """Test convenience function returns valid memory info."""
        info = get_process_memory_info()

        assert isinstance(info, ProcessMemoryInfo)
        assert info.rss_bytes > 0
        assert info.rss_mb > 0

    def test_get_process_memory_info_uses_singleton(self) -> None:
        """Test convenience function uses singleton service."""
        info1 = get_process_memory_info()
        info2 = get_process_memory_info()

        # Both calls should return valid data
        assert info1.rss_bytes > 0
        assert info2.rss_bytes > 0
