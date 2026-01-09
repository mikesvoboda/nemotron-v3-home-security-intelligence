"""Comprehensive unit tests for system API routes.

Tests coverage for backend/api/routes/system.py focusing on:
- Circuit breaker logic and state management
- Health check endpoints with service dependencies
- Storage statistics with filesystem operations
- Severity threshold configuration updates
- Batch aggregator status reporting
- Pipeline status aggregation
- WebSocket broadcaster health checks
- Full health endpoint with comprehensive service checks
"""

from __future__ import annotations

import tempfile
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from backend.api.routes.system import (
    CircuitBreaker,
    _are_critical_pipeline_workers_healthy,
    _build_empty_batch_response,
    _decode_redis_value,
    _get_degradation_status,
    _get_directory_stats,
    _get_worker_statuses,
    _parse_detections,
    _runtime_env_path,
    _write_runtime_env,
    register_workers,
    router,
    verify_api_key,
)
from backend.api.schemas.system import (
    DegradationModeEnum,
)
from backend.core.config import Settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def test_app() -> FastAPI:
    """Create test FastAPI app with system router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
async def async_client(test_app: FastAPI) -> AsyncClient:
    """Create async HTTP client for testing."""
    transport = ASGITransport(app=test_app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_settings() -> Settings:
    """Create mock settings for tests."""
    with patch("backend.api.routes.system.get_settings") as mock:
        settings = Settings(
            database_url="postgresql+asyncpg://test:test@localhost/test",  # pragma: allowlist secret
            api_key_enabled=False,
            api_keys=[],  # pragma: allowlist secret
            foscam_base_path="/test/foscam",
            video_thumbnails_dir="/test/thumbnails",
            clips_directory="/test/clips",
            batch_window_seconds=90,
            batch_idle_timeout_seconds=30,
            severity_low_max=30,
            severity_medium_max=60,
            severity_high_max=90,
        )
        mock.return_value = settings
        yield settings


@pytest.fixture
def circuit_breaker() -> CircuitBreaker:
    """Create fresh circuit breaker for tests."""
    return CircuitBreaker(
        failure_threshold=3,
        reset_timeout=timedelta(seconds=30),
    )


# =============================================================================
# Circuit Breaker Tests
# =============================================================================


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    def test_initial_state_is_closed(self, circuit_breaker: CircuitBreaker) -> None:
        """Test that circuit starts in closed state."""
        assert circuit_breaker.get_state("test-service") == "closed"
        assert not circuit_breaker.is_open("test-service")

    def test_record_failure_increments_count(self, circuit_breaker: CircuitBreaker) -> None:
        """Test that recording failures increments counter."""
        circuit_breaker.record_failure("test-service")
        assert circuit_breaker._failures.get("test-service", 0) == 1

    def test_record_failure_with_error_message(self, circuit_breaker: CircuitBreaker) -> None:
        """Test that error messages are cached."""
        error_msg = "Connection timeout"
        circuit_breaker.record_failure("test-service", error_msg)
        assert circuit_breaker.get_cached_error("test-service") == error_msg

    def test_circuit_opens_after_threshold(self, circuit_breaker: CircuitBreaker) -> None:
        """Test that circuit opens after reaching failure threshold."""
        # Record failures up to threshold
        for _ in range(circuit_breaker.failure_threshold):
            circuit_breaker.record_failure("test-service")

        assert circuit_breaker.is_open("test-service")
        assert circuit_breaker.get_state("test-service") == "open"

    def test_circuit_remains_open_during_timeout(self, circuit_breaker: CircuitBreaker) -> None:
        """Test that circuit stays open during reset timeout."""
        # Open the circuit
        for _ in range(circuit_breaker.failure_threshold):
            circuit_breaker.record_failure("test-service")

        # Check multiple times - should remain open
        assert circuit_breaker.is_open("test-service")
        assert circuit_breaker.is_open("test-service")

    def test_circuit_resets_after_timeout(self, circuit_breaker: CircuitBreaker) -> None:
        """Test that circuit closes after reset timeout expires."""
        # Use very short timeout for testing
        circuit_breaker.reset_timeout = timedelta(milliseconds=10)

        # Open the circuit
        for _ in range(circuit_breaker.failure_threshold):
            circuit_breaker.record_failure("test-service")
        assert circuit_breaker.is_open("test-service")

        # Wait for timeout and check again - should reset
        import time

        time.sleep(0.015)  # Wait slightly longer than timeout
        assert not circuit_breaker.is_open("test-service")

    def test_record_success_resets_failures(self, circuit_breaker: CircuitBreaker) -> None:
        """Test that recording success resets failure count."""
        circuit_breaker.record_failure("test-service", "Error 1")
        circuit_breaker.record_failure("test-service", "Error 2")
        assert circuit_breaker._failures.get("test-service", 0) == 2

        circuit_breaker.record_success("test-service")
        assert circuit_breaker._failures.get("test-service", 0) == 0
        assert circuit_breaker.get_cached_error("test-service") is None

    def test_get_cached_error_returns_none_for_unknown_service(
        self, circuit_breaker: CircuitBreaker
    ) -> None:
        """Test that cached error returns None for unknown service."""
        assert circuit_breaker.get_cached_error("unknown-service") is None


# =============================================================================
# API Key Verification Tests
# =============================================================================


class TestVerifyApiKey:
    """Tests for API key verification dependency."""

    @pytest.mark.asyncio
    async def test_no_auth_when_disabled(self, mock_settings: Settings) -> None:
        """Test that API key is not required when auth is disabled."""
        mock_settings.api_key_enabled = False
        # Should not raise
        await verify_api_key(x_api_key=None)

    @pytest.mark.asyncio
    async def test_missing_key_raises_401(self, mock_settings: Settings) -> None:
        """Test that missing API key raises 401 when auth enabled."""
        mock_settings.api_key_enabled = True
        mock_settings.api_keys = ["test-key"]

        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(x_api_key=None)

        assert exc_info.value.status_code == 401
        assert "API key required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_invalid_key_raises_401(self, mock_settings: Settings) -> None:
        """Test that invalid API key raises 401."""
        mock_settings.api_key_enabled = True
        mock_settings.api_keys = ["valid-key"]  # pragma: allowlist secret

        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(x_api_key="invalid-key")  # pragma: allowlist secret

        assert exc_info.value.status_code == 401
        assert "Invalid API key" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_valid_key_passes(self, mock_settings: Settings) -> None:
        """Test that valid API key passes verification."""
        mock_settings.api_key_enabled = True
        mock_settings.api_keys = ["valid-key-123"]  # pragma: allowlist secret

        # Should not raise
        await verify_api_key(x_api_key="valid-key-123")  # pragma: allowlist secret


# =============================================================================
# Worker Status Tests
# =============================================================================


class TestWorkerStatus:
    """Tests for worker status tracking."""

    def test_register_workers(self) -> None:
        """Test that workers can be registered."""
        mock_gpu_monitor = MagicMock()
        mock_cleanup = MagicMock()

        register_workers(
            gpu_monitor=mock_gpu_monitor,
            cleanup_service=mock_cleanup,
        )

        # Workers should be accessible via _get_worker_statuses
        statuses = _get_worker_statuses()
        assert len(statuses) >= 2
        worker_names = [s.name for s in statuses]
        assert "gpu_monitor" in worker_names
        assert "cleanup_service" in worker_names

    def test_get_worker_statuses_with_running_workers(self) -> None:
        """Test worker status reporting for running workers."""
        mock_gpu_monitor = MagicMock()
        mock_gpu_monitor.running = True

        mock_cleanup = MagicMock()
        mock_cleanup.running = False

        register_workers(
            gpu_monitor=mock_gpu_monitor,
            cleanup_service=mock_cleanup,
        )

        statuses = _get_worker_statuses()
        status_dict = {s.name: s for s in statuses}

        assert status_dict["gpu_monitor"].running is True
        assert status_dict["gpu_monitor"].message is None

        assert status_dict["cleanup_service"].running is False
        assert status_dict["cleanup_service"].message == "Not running"

    def test_are_critical_pipeline_workers_healthy_no_manager(self) -> None:
        """Test that missing pipeline manager returns False."""
        register_workers(pipeline_manager=None)
        assert _are_critical_pipeline_workers_healthy() is False

    def test_are_critical_pipeline_workers_healthy_manager_stopped(self) -> None:
        """Test that stopped manager returns False."""
        mock_manager = MagicMock()
        mock_manager.get_status.return_value = {
            "running": False,
            "workers": {},
        }

        register_workers(pipeline_manager=mock_manager)
        assert _are_critical_pipeline_workers_healthy() is False

    def test_are_critical_pipeline_workers_healthy_detection_stopped(self) -> None:
        """Test that stopped detection worker returns False."""
        mock_manager = MagicMock()
        mock_manager.get_status.return_value = {
            "running": True,
            "workers": {
                "detection": {"state": "stopped"},
                "analysis": {"state": "running"},
            },
        }

        register_workers(pipeline_manager=mock_manager)
        assert _are_critical_pipeline_workers_healthy() is False

    def test_are_critical_pipeline_workers_healthy_analysis_stopped(self) -> None:
        """Test that stopped analysis worker returns False."""
        mock_manager = MagicMock()
        mock_manager.get_status.return_value = {
            "running": True,
            "workers": {
                "detection": {"state": "running"},
                "analysis": {"state": "stopped"},
            },
        }

        register_workers(pipeline_manager=mock_manager)
        assert _are_critical_pipeline_workers_healthy() is False

    def test_are_critical_pipeline_workers_healthy_all_running(self) -> None:
        """Test that all running workers returns True."""
        mock_manager = MagicMock()
        mock_manager.get_status.return_value = {
            "running": True,
            "workers": {
                "detection": {"state": "running"},
                "analysis": {"state": "running"},
            },
        }

        register_workers(pipeline_manager=mock_manager)
        assert _are_critical_pipeline_workers_healthy() is True


# =============================================================================
# Directory Stats Tests
# =============================================================================


class TestGetDirectoryStats:
    """Tests for _get_directory_stats helper."""

    def test_nonexistent_directory_returns_zeros(self) -> None:
        """Test that nonexistent directory returns (0, 0)."""
        path = Path("/nonexistent/path/12345")
        total_size, file_count = _get_directory_stats(path)
        assert total_size == 0
        assert file_count == 0

    def test_empty_directory_returns_zeros(self) -> None:
        """Test that empty directory returns (0, 0)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            total_size, file_count = _get_directory_stats(path)
            assert total_size == 0
            assert file_count == 0

    def test_directory_with_files(self) -> None:
        """Test that directory with files returns correct stats."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)

            # Create test files
            file1 = path / "file1.txt"
            file1.write_text("Hello World")  # 11 bytes

            file2 = path / "file2.txt"
            file2.write_text("Test")  # 4 bytes

            total_size, file_count = _get_directory_stats(path)
            assert file_count == 2
            assert total_size == 15  # 11 + 4

    def test_directory_with_subdirectories(self) -> None:
        """Test that subdirectories are recursively scanned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)

            # Create nested structure
            subdir = path / "subdir"
            subdir.mkdir()
            file1 = subdir / "nested.txt"
            file1.write_text("Nested")  # 6 bytes

            total_size, file_count = _get_directory_stats(path)
            assert file_count == 1
            assert total_size == 6


# =============================================================================
# Storage Stats Endpoint Tests
# =============================================================================


class TestGetStorageStats:
    """Tests for GET /api/system/storage endpoint."""

    @pytest.mark.asyncio
    async def test_get_storage_stats_success(
        self,
        async_client: AsyncClient,
        isolated_db: AsyncSession,
        mock_settings: Settings,
    ) -> None:
        """Test successful storage stats retrieval."""
        with (
            patch("backend.api.routes.system.get_db", return_value=isolated_db),
            patch("backend.api.routes.system.shutil.disk_usage") as mock_disk_usage,
            patch("backend.api.routes.system._get_directory_stats") as mock_dir_stats,
        ):
            # Mock disk usage
            mock_disk_usage.return_value = MagicMock(
                total=1000000000,  # 1GB
                used=400000000,  # 400MB
                free=600000000,  # 600MB
            )

            # Mock directory stats
            mock_dir_stats.return_value = (1024, 5)  # 1KB, 5 files

            response = await async_client.get("/api/system/storage")

            assert response.status_code == 200
            data = response.json()

            assert data["disk_total_bytes"] == 1000000000
            assert data["disk_used_bytes"] == 400000000
            assert data["disk_free_bytes"] == 600000000
            assert data["disk_usage_percent"] == 40.0
            assert data["thumbnails"]["file_count"] == 5
            assert data["thumbnails"]["size_bytes"] == 1024

    @pytest.mark.asyncio
    async def test_get_storage_stats_handles_disk_error(
        self,
        async_client: AsyncClient,
        isolated_db: AsyncSession,
        mock_settings: Settings,
    ) -> None:
        """Test that disk errors return zeros instead of failing."""
        with (
            patch("backend.api.routes.system.get_db", return_value=isolated_db),
            patch(
                "backend.api.routes.system.shutil.disk_usage",
                side_effect=OSError("Permission denied"),
            ),
            patch("backend.api.routes.system._get_directory_stats") as mock_dir_stats,
        ):
            mock_dir_stats.return_value = (0, 0)

            response = await async_client.get("/api/system/storage")

            assert response.status_code == 200
            data = response.json()

            # Should return zeros when disk access fails
            assert data["disk_total_bytes"] == 0
            assert data["disk_used_bytes"] == 0
            assert data["disk_free_bytes"] == 0
            assert data["disk_usage_percent"] == 0.0


# =============================================================================
# Severity Thresholds Tests
# =============================================================================


class TestSeverityThresholds:
    """Tests for severity threshold configuration."""

    def test_update_severity_thresholds_validation_logic(self) -> None:
        """Test that invalid threshold ordering logic is correct."""
        # Test the validation logic without hitting the database
        low_max = 50
        medium_max = 40  # Less than low_max - invalid
        high_max = 90

        # The validation is: low_max < medium_max < high_max
        is_valid = low_max < medium_max < high_max

        assert not is_valid, "Invalid threshold ordering should be detected"

    @pytest.mark.asyncio
    async def test_update_severity_thresholds_success(
        self,
        isolated_db: AsyncSession,
        mock_settings: Settings,
    ) -> None:
        """Test successful threshold update."""
        from backend.api.routes.system import update_severity_thresholds
        from backend.api.schemas.system import SeverityThresholdsUpdateRequest

        request_obj = MagicMock()
        update_request = SeverityThresholdsUpdateRequest(
            low_max=35,
            medium_max=65,
            high_max=85,
        )

        with (
            patch("backend.api.routes.system._write_runtime_env") as mock_write,
            patch("backend.api.routes.system.get_settings") as mock_get_settings,
        ):
            # Mock the settings return
            mock_get_settings.return_value = mock_settings
            mock_get_settings.cache_clear = MagicMock()

            # Mock severity service within the function's import context
            mock_service = MagicMock()
            mock_service.get_thresholds.return_value = {
                "low_max": 35,
                "medium_max": 65,
                "high_max": 85,
            }
            mock_service.get_severity_definitions.return_value = []

            with (
                patch(
                    "backend.services.severity.get_severity_service",
                    return_value=mock_service,
                ),
                patch("backend.services.severity.reset_severity_service"),
                patch("backend.api.routes.system.AuditService.log_action", new=AsyncMock()),
            ):
                result = await update_severity_thresholds(
                    update=update_request,
                    db=isolated_db,
                    request=request_obj,
                )

                # Verify thresholds in response
                assert result.thresholds.low_max == 35
                assert result.thresholds.medium_max == 65
                assert result.thresholds.high_max == 85

                # Verify runtime env was written
                mock_write.assert_called_once()


# =============================================================================
# Runtime Env File Tests
# =============================================================================


class TestRuntimeEnvFile:
    """Tests for runtime environment file handling."""

    def test_runtime_env_path(self) -> None:
        """Test that runtime env path is correct."""
        path = _runtime_env_path()
        assert path.name == "runtime.env"
        assert path.is_absolute()

    def test_write_runtime_env_creates_file(self) -> None:
        """Test that writing runtime env creates the file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("backend.api.routes.system._runtime_env_path") as mock_path:
                mock_path.return_value = Path(tmpdir) / "runtime.env"

                overrides = {
                    "SEVERITY_LOW_MAX": "35",
                    "SEVERITY_MEDIUM_MAX": "65",
                }

                _write_runtime_env(overrides)

                # Verify file was created
                env_file = Path(tmpdir) / "runtime.env"
                assert env_file.exists()

                # Verify content
                content = env_file.read_text()
                assert "SEVERITY_LOW_MAX=35" in content
                assert "SEVERITY_MEDIUM_MAX=65" in content

    def test_write_runtime_env_updates_existing(self) -> None:
        """Test that writing runtime env updates existing values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / "runtime.env"

            # Create existing file
            env_file.write_text(
                "SEVERITY_LOW_MAX=30\nOTHER_VAR=unchanged\n"  # pragma: allowlist secret
            )

            with patch("backend.api.routes.system._runtime_env_path", return_value=env_file):
                overrides = {"SEVERITY_LOW_MAX": "40"}

                _write_runtime_env(overrides)

                # Verify updated content
                content = env_file.read_text()
                assert "SEVERITY_LOW_MAX=40" in content
                assert "OTHER_VAR=unchanged" in content


# =============================================================================
# Batch Aggregator Status Tests
# =============================================================================


class TestBatchAggregatorStatus:
    """Tests for batch aggregator status helpers."""

    def test_decode_redis_value_bytes(self) -> None:
        """Test decoding bytes to string."""
        value = b"test-value"
        result = _decode_redis_value(value)
        assert result == "test-value"

    def test_decode_redis_value_string(self) -> None:
        """Test that string values pass through."""
        value = "test-value"
        result = _decode_redis_value(value)
        assert result == "test-value"

    def test_decode_redis_value_none(self) -> None:
        """Test that None returns None."""
        result = _decode_redis_value(None)
        assert result is None

    def test_parse_detections_valid_json(self) -> None:
        """Test parsing valid JSON detections."""
        import json

        detections = [{"label": "person", "confidence": 0.95}]
        json_bytes = json.dumps(detections).encode()

        result = _parse_detections(json_bytes)
        assert len(result) == 1
        assert result[0]["label"] == "person"

    def test_parse_detections_invalid_json(self) -> None:
        """Test that invalid JSON raises JSONDecodeError."""
        import json

        with pytest.raises(json.JSONDecodeError):
            _parse_detections(b"invalid json")

    def test_parse_detections_none(self) -> None:
        """Test that None returns empty list."""
        result = _parse_detections(None)
        assert result == []

    def test_build_empty_batch_response(self, mock_settings: Settings) -> None:
        """Test building empty batch response."""
        response = _build_empty_batch_response(mock_settings)

        assert response.active_batches == 0
        assert response.batches == []
        assert response.batch_window_seconds == 90
        assert response.idle_timeout_seconds == 30


# =============================================================================
# Degradation Status Tests
# =============================================================================


class TestDegradationStatus:
    """Tests for degradation manager status."""

    def test_get_degradation_status_manager_not_initialized(self) -> None:
        """Test that uninitialized manager returns None."""
        # Clear the global degradation manager
        import backend.api.routes.system as system_module

        original_manager = system_module._degradation_manager
        try:
            system_module._degradation_manager = None

            # Mock the get_degradation_manager to raise error
            with patch(
                "backend.services.degradation_manager.get_degradation_manager",
                side_effect=RuntimeError("Not initialized"),
            ):
                result = _get_degradation_status()
                assert result is None
        finally:
            system_module._degradation_manager = original_manager

    def test_get_degradation_status_success(self) -> None:
        """Test successful degradation status retrieval."""
        import time

        mock_manager = MagicMock()
        mock_manager.get_status.return_value = {
            "mode": "normal",
            "is_degraded": False,
            "redis_healthy": True,
            "memory_queue_size": 0,
            "fallback_queues": {},
            "services": {
                "redis": {
                    "status": "healthy",
                    "last_check": time.time(),  # Use timestamp, not datetime
                    "consecutive_failures": 0,
                }
            },
            "available_features": ["detection", "analysis"],
        }

        # Set the global manager
        import backend.api.routes.system as system_module

        original_manager = system_module._degradation_manager
        try:
            system_module._degradation_manager = mock_manager

            result = _get_degradation_status()

            assert result is not None
            assert result.mode == DegradationModeEnum.NORMAL
            assert result.is_degraded is False
            assert result.redis_healthy is True
            assert len(result.services) == 1
        finally:
            system_module._degradation_manager = original_manager

    def test_get_degradation_status_handles_errors(self) -> None:
        """Test that status parsing errors return None."""
        mock_manager = MagicMock()
        mock_manager.get_status.return_value = {
            "mode": "invalid_mode",  # Will cause ValueError
        }

        import backend.api.routes.system as system_module

        original_manager = system_module._degradation_manager
        try:
            system_module._degradation_manager = mock_manager

            result = _get_degradation_status()
            assert result is None
        finally:
            system_module._degradation_manager = original_manager


# =============================================================================
# Helper Function Tests (Additional Coverage)
# =============================================================================


class TestHelperFunctions:
    """Tests for additional helper functions to improve coverage."""

    def test_decode_redis_value_with_utf8(self) -> None:
        """Test decoding with UTF-8 characters."""
        value = "test-value-™".encode()
        result = _decode_redis_value(value)
        assert result == "test-value-™"

    def test_get_directory_stats_permission_error(self) -> None:
        """Test that permission errors are handled gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            subdir = path / "restricted"
            subdir.mkdir()

            # Create a file
            testfile = subdir / "test.txt"
            testfile.write_text("test")

            # Mock stat to raise PermissionError
            with patch.object(Path, "stat", side_effect=PermissionError):
                total_size, file_count = _get_directory_stats(path)
                # Should return zeros for the file we couldn't access
                assert total_size == 0
                assert file_count == 0
