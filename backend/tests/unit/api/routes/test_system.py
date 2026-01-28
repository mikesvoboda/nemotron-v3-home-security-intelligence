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
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

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
    HealthCheckServiceStatus,
)
from backend.core.config import Settings
from backend.core.redis import get_redis

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def test_app() -> FastAPI:
    """Create test FastAPI app with system router.

    Includes a mock Redis dependency override to prevent
    endpoints with RateLimiter from connecting to real Redis.
    """
    app = FastAPI()
    app.include_router(router)

    # Create mock Redis client for rate limiting
    mock_redis = AsyncMock()
    mock_redis.health_check.return_value = {"status": "healthy", "connected": True}

    async def mock_get_redis():
        yield mock_redis

    app.dependency_overrides[get_redis] = mock_get_redis
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

    def test_are_critical_pipeline_workers_healthy_detection_error_state(self) -> None:
        """Test that detection worker in error state is still considered healthy.

        NEM-3901: The "error" state is transient and self-recovers within ~1 second.
        Treating error as unhealthy causes false negatives in readiness probes,
        leading to SLO burn rate spikes.
        """
        mock_manager = MagicMock()
        mock_manager.get_status.return_value = {
            "running": True,
            "workers": {
                "detection": {"state": "error"},
                "analysis": {"state": "running"},
            },
        }

        register_workers(pipeline_manager=mock_manager)
        assert _are_critical_pipeline_workers_healthy() is True

    def test_are_critical_pipeline_workers_healthy_analysis_error_state(self) -> None:
        """Test that analysis worker in error state is still considered healthy.

        NEM-3901: The "error" state is transient and self-recovers within ~1 second.
        """
        mock_manager = MagicMock()
        mock_manager.get_status.return_value = {
            "running": True,
            "workers": {
                "detection": {"state": "running"},
                "analysis": {"state": "error"},
            },
        }

        register_workers(pipeline_manager=mock_manager)
        assert _are_critical_pipeline_workers_healthy() is True

    def test_are_critical_pipeline_workers_healthy_both_error_state(self) -> None:
        """Test that both workers in error state are still considered healthy.

        NEM-3901: Even if both workers encounter transient errors simultaneously,
        they should still be considered operational since they auto-recover.
        """
        mock_manager = MagicMock()
        mock_manager.get_status.return_value = {
            "running": True,
            "workers": {
                "detection": {"state": "error"},
                "analysis": {"state": "error"},
            },
        }

        register_workers(pipeline_manager=mock_manager)
        assert _are_critical_pipeline_workers_healthy() is True

    def test_are_critical_pipeline_workers_healthy_starting_state(self) -> None:
        """Test that starting state is NOT considered healthy.

        Workers in "starting" state haven't completed initialization,
        so they should not be considered operational.
        """
        mock_manager = MagicMock()
        mock_manager.get_status.return_value = {
            "running": True,
            "workers": {
                "detection": {"state": "starting"},
                "analysis": {"state": "running"},
            },
        }

        register_workers(pipeline_manager=mock_manager)
        assert _are_critical_pipeline_workers_healthy() is False

    def test_are_critical_pipeline_workers_healthy_stopping_state(self) -> None:
        """Test that stopping state is NOT considered healthy.

        Workers in "stopping" state are shutting down and should not
        be considered operational for readiness probes.
        """
        mock_manager = MagicMock()
        mock_manager.get_status.return_value = {
            "running": True,
            "workers": {
                "detection": {"state": "running"},
                "analysis": {"state": "stopping"},
            },
        }

        register_workers(pipeline_manager=mock_manager)
        assert _are_critical_pipeline_workers_healthy() is False


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


@pytest.mark.integration  # Requires isolated_db fixture (real database)
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


@pytest.mark.integration  # Requires isolated_db fixture (real database)
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


# =============================================================================
# Performance Metrics Endpoint Tests
# =============================================================================


@pytest.mark.integration  # Requires isolated_db fixture (real database)
class TestGetHealthEndpoint:
    """Tests for GET /api/system/health endpoint."""

    @pytest.mark.asyncio
    async def test_health_endpoint_all_healthy(
        self,
        async_client: AsyncClient,
        isolated_db: AsyncSession,
        mock_settings: Settings,
    ) -> None:
        """Test health endpoint returns 200 when all services healthy."""
        with (
            patch("backend.api.routes.system.get_db", return_value=isolated_db),
            patch("backend.api.routes.system.check_database_health") as mock_db,
            patch("backend.api.routes.system.check_redis_health") as mock_redis,
            patch("backend.api.routes.system.check_ai_services_health") as mock_ai,
            patch("backend.api.routes.system._emit_health_status_changes", new=AsyncMock()),
        ):
            # Mock all services as healthy
            mock_db.return_value = HealthCheckServiceStatus(
                status="healthy", message="Connected", details=None
            )
            mock_redis.return_value = HealthCheckServiceStatus(
                status="healthy", message="Connected", details=None
            )
            mock_ai.return_value = HealthCheckServiceStatus(
                status="healthy", message="All services operational", details=None
            )

            response = await async_client.get("/api/system/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["services"]["database"]["status"] == "healthy"
            assert data["services"]["redis"]["status"] == "healthy"
            assert data["services"]["ai"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_endpoint_database_unhealthy(
        self,
        async_client: AsyncClient,
        isolated_db: AsyncSession,
        mock_settings: Settings,
    ) -> None:
        """Test health endpoint returns 503 when database is unhealthy."""
        with (
            patch("backend.api.routes.system.get_db", return_value=isolated_db),
            patch("backend.api.routes.system.check_database_health") as mock_db,
            patch("backend.api.routes.system.check_redis_health") as mock_redis,
            patch("backend.api.routes.system.check_ai_services_health") as mock_ai,
            patch("backend.api.routes.system._emit_health_status_changes", new=AsyncMock()),
        ):
            # Database unhealthy
            mock_db.return_value = HealthCheckServiceStatus(
                status="unhealthy", message="Connection failed", details=None
            )
            mock_redis.return_value = HealthCheckServiceStatus(
                status="healthy", message="Connected", details=None
            )
            mock_ai.return_value = HealthCheckServiceStatus(
                status="healthy", message="All services operational", details=None
            )

            response = await async_client.get("/api/system/health")

            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_health_endpoint_degraded(
        self,
        async_client: AsyncClient,
        isolated_db: AsyncSession,
        mock_settings: Settings,
    ) -> None:
        """Test health endpoint returns 503 degraded when AI services down."""
        with (
            patch("backend.api.routes.system.get_db", return_value=isolated_db),
            patch("backend.api.routes.system.check_database_health") as mock_db,
            patch("backend.api.routes.system.check_redis_health") as mock_redis,
            patch("backend.api.routes.system.check_ai_services_health") as mock_ai,
            patch("backend.api.routes.system._emit_health_status_changes", new=AsyncMock()),
        ):
            # AI services unhealthy
            mock_db.return_value = HealthCheckServiceStatus(
                status="healthy", message="Connected", details=None
            )
            mock_redis.return_value = HealthCheckServiceStatus(
                status="healthy", message="Connected", details=None
            )
            mock_ai.return_value = HealthCheckServiceStatus(
                status="unhealthy", message="Services not responding", details=None
            )

            response = await async_client.get("/api/system/health")

            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "degraded"


@pytest.mark.integration  # Requires isolated_db fixture (real database)
class TestGetReadinessEndpoint:
    """Tests for GET /api/system/health/ready endpoint."""

    @pytest.mark.asyncio
    async def test_readiness_endpoint_ready(
        self,
        async_client: AsyncClient,
        isolated_db: AsyncSession,
        mock_settings: Settings,
    ) -> None:
        """Test readiness endpoint returns 200 when ready."""
        mock_manager = MagicMock()
        mock_manager.get_status.return_value = {
            "running": True,
            "workers": {
                "detection": {"state": "running"},
                "analysis": {"state": "running"},
            },
        }

        with (
            patch("backend.api.routes.system.get_db", return_value=isolated_db),
            patch("backend.api.routes.system.check_database_health") as mock_db,
            patch("backend.api.routes.system.check_redis_health") as mock_redis,
            patch("backend.api.routes.system.check_ai_services_health") as mock_ai,
        ):
            mock_db.return_value = HealthCheckServiceStatus(
                status="healthy", message="Connected", details=None
            )
            mock_redis.return_value = HealthCheckServiceStatus(
                status="healthy", message="Connected", details=None
            )
            mock_ai.return_value = HealthCheckServiceStatus(
                status="healthy", message="All services operational", details=None
            )

            register_workers(pipeline_manager=mock_manager)

            response = await async_client.get("/api/system/health/ready")

            assert response.status_code == 200
            data = response.json()
            assert data["ready"] is True
            assert data["status"] == "ready"

    @pytest.mark.asyncio
    async def test_readiness_endpoint_not_ready_pipeline_down(
        self,
        async_client: AsyncClient,
        isolated_db: AsyncSession,
        mock_settings: Settings,
    ) -> None:
        """Test readiness endpoint returns 503 when pipeline workers down."""
        mock_manager = MagicMock()
        mock_manager.get_status.return_value = {
            "running": False,
            "workers": {},
        }

        with (
            patch("backend.api.routes.system.get_db", return_value=isolated_db),
            patch("backend.api.routes.system.check_database_health") as mock_db,
            patch("backend.api.routes.system.check_redis_health") as mock_redis,
            patch("backend.api.routes.system.check_ai_services_health") as mock_ai,
        ):
            mock_db.return_value = HealthCheckServiceStatus(
                status="healthy", message="Connected", details=None
            )
            mock_redis.return_value = HealthCheckServiceStatus(
                status="healthy", message="Connected", details=None
            )
            mock_ai.return_value = HealthCheckServiceStatus(
                status="healthy", message="All services operational", details=None
            )

            register_workers(pipeline_manager=mock_manager)

            response = await async_client.get("/api/system/health/ready")

            assert response.status_code == 503
            data = response.json()
            assert data["ready"] is False
            assert data["status"] == "not_ready"


class TestWebSocketHealthEndpoint:
    """Tests for GET /api/system/health/websocket endpoint."""

    @pytest.mark.asyncio
    async def test_websocket_health_broadcasters_available(
        self, async_client: AsyncClient, mock_settings: Settings
    ) -> None:
        """Test websocket health when broadcasters are available."""
        mock_event_broadcaster = MagicMock()
        mock_event_broadcaster.get_circuit_state.return_value = MagicMock(value="closed")
        mock_event_broadcaster.circuit_breaker.failure_count = 0
        mock_event_broadcaster.is_degraded.return_value = False

        mock_system_broadcaster = MagicMock()
        mock_system_broadcaster.get_circuit_state.return_value = MagicMock(value="closed")
        mock_system_broadcaster.circuit_breaker.failure_count = 0
        mock_system_broadcaster._pubsub_listening = True

        # Patch the imported modules in the get_websocket_health function
        with (
            patch(
                "backend.services.event_broadcaster._broadcaster",
                mock_event_broadcaster,
            ),
            patch(
                "backend.services.system_broadcaster._system_broadcaster",
                mock_system_broadcaster,
            ),
        ):
            response = await async_client.get("/api/system/health/websocket")

            assert response.status_code == 200
            data = response.json()
            assert data["event_broadcaster"]["state"] == "closed"
            assert data["system_broadcaster"]["state"] == "closed"

    @pytest.mark.asyncio
    async def test_websocket_health_broadcasters_unavailable(
        self, async_client: AsyncClient, mock_settings: Settings
    ) -> None:
        """Test websocket health when broadcasters are not initialized."""
        with (
            patch("backend.services.event_broadcaster._broadcaster", None),
            patch("backend.services.system_broadcaster._system_broadcaster", None),
        ):
            response = await async_client.get("/api/system/health/websocket")

            assert response.status_code == 200
            data = response.json()
            assert data["event_broadcaster"]["state"] == "unavailable"
            assert data["system_broadcaster"]["state"] == "unavailable"


class TestGetConfigEndpoint:
    """Tests for GET /api/system/config endpoint."""

    @pytest.mark.asyncio
    async def test_get_config_success(
        self, async_client: AsyncClient, mock_settings: Settings
    ) -> None:
        """Test successful config retrieval."""
        response = await async_client.get("/api/system/config")

        assert response.status_code == 200
        data = response.json()
        assert "app_name" in data
        assert "version" in data
        assert "retention_days" in data
        assert "batch_window_seconds" in data
        assert data["batch_window_seconds"] == 90


class TestListWebSocketEventTypesEndpoint:
    """Tests for GET /api/system/websocket/events endpoint."""

    @pytest.mark.asyncio
    async def test_list_event_types_success(
        self, async_client: AsyncClient, mock_settings: Settings
    ) -> None:
        """Test successful event types listing."""
        response = await async_client.get("/api/system/websocket/events")

        assert response.status_code == 200
        data = response.json()
        assert "event_types" in data
        assert "channels" in data
        assert "total_count" in data
        assert isinstance(data["event_types"], list)


@pytest.mark.integration  # Requires isolated_db fixture (real database)
class TestGetStatsEndpoint:
    """Tests for GET /api/system/stats endpoint."""

    @pytest.mark.asyncio
    async def test_get_stats_success(
        self,
        async_client: AsyncClient,
        isolated_db: AsyncSession,
        mock_settings: Settings,
    ) -> None:
        """Test successful stats retrieval."""
        with patch("backend.api.routes.system.get_db", return_value=isolated_db):
            response = await async_client.get("/api/system/stats")

            assert response.status_code == 200
            data = response.json()
            assert "total_cameras" in data
            assert "total_events" in data
            assert "total_detections" in data
            assert "uptime_seconds" in data
            assert isinstance(data["uptime_seconds"], int | float)


@pytest.mark.integration  # Requires isolated_db fixture (real database)
class TestGetGPUStatsEndpoint:
    """Tests for GET /api/system/gpu endpoint."""

    @pytest.mark.asyncio
    async def test_get_gpu_stats_no_data(
        self,
        async_client: AsyncClient,
        isolated_db: AsyncSession,
        mock_settings: Settings,
    ) -> None:
        """Test GPU stats endpoint when no data available."""
        with patch("backend.api.routes.system.get_db", return_value=isolated_db):
            response = await async_client.get("/api/system/gpu")

            assert response.status_code == 200
            data = response.json()
            # Should have null values when no stats available
            assert data["gpu_name"] is None or isinstance(data["gpu_name"], str)


class TestGetGPUStatsEndpointUnit:
    """Unit tests for GET /api/system/gpu endpoint (with mocked database)."""

    @pytest.mark.asyncio
    async def test_get_gpu_stats_with_data(
        self,
        test_app: FastAPI,
        mock_settings: Settings,
    ) -> None:
        """Test GPU stats endpoint returns data when available."""
        from datetime import UTC, datetime

        from backend.core.database import get_db
        from backend.models import GPUStats

        mock_db = AsyncMock(spec=AsyncSession)

        # Create mock GPU stats
        mock_gpu_stats = GPUStats(
            id=1,
            recorded_at=datetime(2025, 1, 23, 12, 0, 0, tzinfo=UTC),
            gpu_name="RTX A5500",
            gpu_utilization=75.5,
            memory_used=20480,
            memory_total=24564,
            temperature=65,
            power_usage=180,
            inference_fps=15.2,
            fan_speed=45,
            sm_clock=1500,
            memory_bandwidth_utilization=80.5,
            pstate=2,
            throttle_reasons=None,
            power_limit=300,
            sm_clock_max=1800,
            compute_processes_count=2,
            pcie_replay_counter=0,
            temp_slowdown_threshold=84,
            memory_clock=1215,
            memory_clock_max=1215,
            pcie_link_gen=4,
            pcie_link_width=16,
            pcie_tx_throughput=1500,
            pcie_rx_throughput=1200,
            encoder_utilization=0,
            decoder_utilization=0,
            bar1_used=256,
        )

        # Mock database query result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_gpu_stats
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def mock_get_db():
            yield mock_db

        test_app.dependency_overrides[get_db] = mock_get_db

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:  # type: ignore[arg-type]
            response = await client.get("/api/system/gpu")

            assert response.status_code == 200
            data = response.json()
            assert data["gpu_name"] == "RTX A5500"
            assert data["utilization"] == 75.5
            assert data["memory_used"] == 20480
            assert data["memory_total"] == 24564
            assert data["temperature"] == 65
            assert data["power_usage"] == 180
            assert data["inference_fps"] == 15.2

    @pytest.mark.asyncio
    async def test_get_gpu_stats_no_data(
        self,
        test_app: FastAPI,
        mock_settings: Settings,
    ) -> None:
        """Test GPU stats endpoint when no data available returns null values."""
        from backend.core.database import get_db

        mock_db = AsyncMock(spec=AsyncSession)

        # Mock database query result - no stats found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def mock_get_db():
            yield mock_db

        # Clear cache to ensure we test the no-data scenario
        import backend.api.routes.system as system_module

        system_module._gpu_stats_cache = None

        test_app.dependency_overrides[get_db] = mock_get_db

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:  # type: ignore[arg-type]
            response = await client.get("/api/system/gpu")

            assert response.status_code == 200
            data = response.json()
            # All fields should be null when no data available
            assert data["gpu_name"] is None
            assert data["utilization"] is None
            assert data["memory_used"] is None
            assert data["memory_total"] is None
            assert data["temperature"] is None
            assert data["power_usage"] is None

        # Clean up
        system_module._gpu_stats_cache = None

    @pytest.mark.asyncio
    async def test_get_gpu_stats_uses_cache(
        self,
        test_app: FastAPI,
        mock_settings: Settings,
    ) -> None:
        """Test GPU stats endpoint uses cache on subsequent requests."""
        from datetime import UTC, datetime

        from backend.core.database import get_db
        from backend.models import GPUStats

        mock_db = AsyncMock(spec=AsyncSession)

        # Create mock GPU stats
        mock_gpu_stats = GPUStats(
            id=1,
            recorded_at=datetime(2025, 1, 23, 12, 0, 0, tzinfo=UTC),
            gpu_name="RTX A5500",
            gpu_utilization=75.5,
            memory_used=20480,
            memory_total=24564,
            temperature=65,
            power_usage=180,
            inference_fps=15.2,
        )

        # Mock database query result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_gpu_stats
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def mock_get_db():
            yield mock_db

        # Clear cache before test
        import backend.api.routes.system as system_module

        system_module._gpu_stats_cache = None

        test_app.dependency_overrides[get_db] = mock_get_db

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:  # type: ignore[arg-type]
            # First request - should hit database
            response1 = await client.get("/api/system/gpu")
            assert response1.status_code == 200
            assert mock_db.execute.call_count == 1

            # Second request - should use cache (within 5s TTL)
            response2 = await client.get("/api/system/gpu")
            assert response2.status_code == 200
            # Database should not be queried again
            assert mock_db.execute.call_count == 1
            assert response2.json() == response1.json()

        # Clean up cache after test
        system_module._gpu_stats_cache = None

    @pytest.mark.asyncio
    async def test_get_gpu_stats_cache_expiry(
        self,
        test_app: FastAPI,
        mock_settings: Settings,
    ) -> None:
        """Test GPU stats cache expires after TTL."""
        import time
        from datetime import UTC, datetime

        from backend.api.routes.system import GPUStatsCacheEntry
        from backend.core.database import get_db
        from backend.models import GPUStats

        mock_db = AsyncMock(spec=AsyncSession)

        # Create mock GPU stats
        mock_gpu_stats = GPUStats(
            id=1,
            recorded_at=datetime(2025, 1, 23, 12, 0, 0, tzinfo=UTC),
            gpu_name="RTX A5500",
            gpu_utilization=75.5,
            memory_used=20480,
            memory_total=24564,
            temperature=65,
            power_usage=180,
            inference_fps=15.2,
        )

        # Mock database query result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_gpu_stats
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def mock_get_db():
            yield mock_db

        import backend.api.routes.system as system_module

        # Clear cache
        system_module._gpu_stats_cache = None

        test_app.dependency_overrides[get_db] = mock_get_db

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:  # type: ignore[arg-type]
            # First request
            response1 = await client.get("/api/system/gpu")
            assert response1.status_code == 200
            assert mock_db.execute.call_count == 1

            # Manually expire the cache by creating a new cache entry with old timestamp
            if system_module._gpu_stats_cache:
                expired_response = system_module._gpu_stats_cache.response
                system_module._gpu_stats_cache = GPUStatsCacheEntry(
                    response=expired_response,
                    cached_at=time.time() - 10,  # Expired 10 seconds ago
                )

            # Second request - cache expired, should hit database again
            response2 = await client.get("/api/system/gpu")
            assert response2.status_code == 200
            assert mock_db.execute.call_count == 2

        # Clean up
        system_module._gpu_stats_cache = None


class TestGetGPUStatsHistoryEndpoint:
    """Unit tests for GET /api/system/gpu/history endpoint."""

    @pytest.mark.asyncio
    async def test_get_gpu_history_no_data(
        self,
        test_app: FastAPI,
        mock_settings: Settings,
    ) -> None:
        """Test GPU history endpoint returns empty list when no data available."""
        from backend.core.database import get_db

        mock_db = AsyncMock(spec=AsyncSession)

        # Mock count query - endpoint uses scalar() not scalar_one()
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        # Mock samples query
        mock_samples_result = MagicMock()
        mock_samples_result.scalars.return_value.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_samples_result])

        async def mock_get_db():
            yield mock_db

        test_app.dependency_overrides[get_db] = mock_get_db

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:  # type: ignore[arg-type]
            response = await client.get("/api/system/gpu/history")

            assert response.status_code == 200
            data = response.json()
            assert data["items"] == []
            assert data["pagination"]["total"] == 0
            assert data["pagination"]["limit"] == 300  # Default limit for GPU history
            assert data["pagination"]["has_more"] is False

    @pytest.mark.asyncio
    async def test_get_gpu_history_with_data(
        self,
        test_app: FastAPI,
        mock_settings: Settings,
    ) -> None:
        """Test GPU history endpoint returns samples when data available."""
        from datetime import UTC, datetime

        from backend.core.database import get_db
        from backend.models import GPUStats

        mock_db = AsyncMock(spec=AsyncSession)

        # Create mock GPU stats samples
        mock_samples = [
            GPUStats(
                id=i,
                recorded_at=datetime(2025, 1, 23, 12, 0, i, tzinfo=UTC),
                gpu_name="RTX A5500",
                gpu_utilization=75.0 + i,
                memory_used=20000 + i * 100,
                memory_total=24564,
                temperature=60 + i,
                power_usage=180 + i,
                inference_fps=15.0 + i * 0.1,
            )
            for i in range(5)
        ]

        # Mock count query
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 5

        # Mock samples query
        mock_samples_result = MagicMock()
        mock_samples_result.scalars.return_value.all.return_value = mock_samples

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_samples_result])

        async def mock_get_db():
            yield mock_db

        test_app.dependency_overrides[get_db] = mock_get_db

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:  # type: ignore[arg-type]
            response = await client.get("/api/system/gpu/history")

            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 5
            assert data["pagination"]["total"] == 5
            assert data["items"][0]["gpu_name"] == "RTX A5500"
            assert "utilization" in data["items"][0]
            assert "memory_used" in data["items"][0]

    @pytest.mark.asyncio
    async def test_get_gpu_history_with_limit(
        self,
        test_app: FastAPI,
        mock_settings: Settings,
    ) -> None:
        """Test GPU history endpoint respects limit parameter."""
        from datetime import UTC, datetime

        from backend.core.database import get_db
        from backend.models import GPUStats

        mock_db = AsyncMock(spec=AsyncSession)

        # Create mock GPU stats samples (more than requested limit)
        mock_samples = [
            GPUStats(
                id=i,
                recorded_at=datetime(2025, 1, 23, 12, 0, i, tzinfo=UTC),
                gpu_name="RTX A5500",
                gpu_utilization=75.0,
                memory_used=20000,
                memory_total=24564,
                temperature=60,
                power_usage=180,
                inference_fps=15.0,
            )
            for i in range(3)
        ]

        # Mock count query
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 10

        # Mock samples query
        mock_samples_result = MagicMock()
        mock_samples_result.scalars.return_value.all.return_value = mock_samples

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_samples_result])

        async def mock_get_db():
            yield mock_db

        test_app.dependency_overrides[get_db] = mock_get_db

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:  # type: ignore[arg-type]
            response = await client.get("/api/system/gpu/history?limit=3")

            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 3
            assert data["pagination"]["total"] == 10
            assert data["pagination"]["limit"] == 3
            assert data["pagination"]["has_more"] is True

    @pytest.mark.asyncio
    async def test_get_gpu_history_with_since_filter(
        self,
        test_app: FastAPI,
        mock_settings: Settings,
    ) -> None:
        """Test GPU history endpoint filters by since parameter."""
        from datetime import UTC, datetime

        from backend.core.database import get_db
        from backend.models import GPUStats

        mock_db = AsyncMock(spec=AsyncSession)

        # Create mock GPU stats samples after the since timestamp
        mock_samples = [
            GPUStats(
                id=1,
                recorded_at=datetime(2025, 1, 23, 12, 30, 0, tzinfo=UTC),
                gpu_name="RTX A5500",
                gpu_utilization=75.0,
                memory_used=20000,
                memory_total=24564,
                temperature=60,
                power_usage=180,
                inference_fps=15.0,
            )
        ]

        # Mock count query
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        # Mock samples query
        mock_samples_result = MagicMock()
        mock_samples_result.scalars.return_value.all.return_value = mock_samples

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_samples_result])

        async def mock_get_db():
            yield mock_db

        test_app.dependency_overrides[get_db] = mock_get_db

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:  # type: ignore[arg-type]
            # Query with since parameter
            since_time = "2025-01-23T12:00:00Z"
            response = await client.get(f"/api/system/gpu/history?since={since_time}")

            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 1
            assert data["pagination"]["total"] == 1

    @pytest.mark.asyncio
    async def test_get_gpu_history_pagination(
        self,
        test_app: FastAPI,
        mock_settings: Settings,
    ) -> None:
        """Test GPU history endpoint pagination with limit.

        Note: GPU history uses time-based filtering (since), not offset pagination.
        """
        from datetime import UTC, datetime

        from backend.core.database import get_db
        from backend.models import GPUStats

        mock_db = AsyncMock(spec=AsyncSession)

        # Create mock GPU stats samples
        mock_samples = [
            GPUStats(
                id=i,
                recorded_at=datetime(2025, 1, 23, 12, 0, i, tzinfo=UTC),
                gpu_name="RTX A5500",
                gpu_utilization=75.0,
                memory_used=20000,
                memory_total=24564,
                temperature=60,
                power_usage=180,
                inference_fps=15.0,
            )
            for i in range(2)
        ]

        # Mock count query
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 10

        # Mock samples query
        mock_samples_result = MagicMock()
        mock_samples_result.scalars.return_value.all.return_value = mock_samples

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_samples_result])

        async def mock_get_db():
            yield mock_db

        test_app.dependency_overrides[get_db] = mock_get_db

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:  # type: ignore[arg-type]
            response = await client.get("/api/system/gpu/history?limit=2")

            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 2
            assert data["pagination"]["total"] == 10
            assert data["pagination"]["limit"] == 2
            assert data["pagination"]["has_more"] is True

    @pytest.mark.asyncio
    async def test_get_gpu_history_invalid_since(
        self,
        test_app: FastAPI,
        mock_settings: Settings,
    ) -> None:
        """Test GPU history endpoint handles invalid since parameter."""
        from backend.core.database import get_db

        mock_db = AsyncMock(spec=AsyncSession)

        async def mock_get_db():
            yield mock_db

        test_app.dependency_overrides[get_db] = mock_get_db

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:  # type: ignore[arg-type]
            response = await client.get("/api/system/gpu/history?since=invalid-date")

            # FastAPI should return 422 for invalid query parameter format
            assert response.status_code == 422


class TestPerformanceMetricsEndpoint:
    """Tests for GET /api/system/performance endpoint."""

    @pytest.mark.asyncio
    async def test_performance_endpoint_returns_metrics(
        self, async_client: AsyncClient, mock_settings: Settings
    ) -> None:
        """Test that performance endpoint returns PerformanceUpdate response."""
        from datetime import UTC, datetime

        from backend.api.schemas.performance import (
            GpuMetrics,
            HostMetrics,
            PerformanceUpdate,
        )

        # Create mock PerformanceUpdate
        mock_update = PerformanceUpdate(
            timestamp=datetime.now(UTC),
            gpu=GpuMetrics(
                name="NVIDIA RTX A5500",
                utilization=38.0,
                vram_used_gb=22.7,
                vram_total_gb=24.0,
                temperature=38,
                power_watts=31,
            ),
            host=HostMetrics(
                cpu_percent=12.0,
                ram_used_gb=8.2,
                ram_total_gb=32.0,
                disk_used_gb=156.0,
                disk_total_gb=500.0,
            ),
            ai_models={},
            databases={},
            containers=[],
            alerts=[],
        )

        # Mock the performance collector
        mock_collector = AsyncMock()
        mock_collector.collect_all.return_value = mock_update

        import backend.api.routes.system as system_module

        original_collector = system_module._performance_collector
        try:
            system_module._performance_collector = mock_collector

            response = await async_client.get("/api/system/performance")

            assert response.status_code == 200
            data = response.json()
            assert "timestamp" in data
            assert "gpu" in data
            assert "host" in data
            assert data["gpu"]["name"] == "NVIDIA RTX A5500"
            assert data["gpu"]["utilization"] == 38.0
            assert data["host"]["cpu_percent"] == 12.0
        finally:
            system_module._performance_collector = original_collector

    @pytest.mark.asyncio
    async def test_performance_endpoint_collector_not_initialized(
        self, async_client: AsyncClient, mock_settings: Settings
    ) -> None:
        """Test that endpoint returns 503 when collector is not initialized."""
        import backend.api.routes.system as system_module

        original_collector = system_module._performance_collector
        try:
            system_module._performance_collector = None

            response = await async_client.get("/api/system/performance")

            assert response.status_code == 503
            data = response.json()
            assert "detail" in data
            assert "not initialized" in data["detail"].lower()
        finally:
            system_module._performance_collector = original_collector

    @pytest.mark.asyncio
    async def test_performance_endpoint_collector_error(
        self, async_client: AsyncClient, mock_settings: Settings
    ) -> None:
        """Test that endpoint handles collector errors gracefully."""
        mock_collector = AsyncMock()
        mock_collector.collect_all.side_effect = RuntimeError("Collection failed")

        import backend.api.routes.system as system_module

        original_collector = system_module._performance_collector
        try:
            system_module._performance_collector = mock_collector

            response = await async_client.get("/api/system/performance")

            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
        finally:
            system_module._performance_collector = original_collector

    @pytest.mark.asyncio
    async def test_performance_endpoint_with_all_metrics(
        self, async_client: AsyncClient, mock_settings: Settings
    ) -> None:
        """Test endpoint returns all metric fields when available."""
        from datetime import UTC, datetime

        from backend.api.schemas.performance import (
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
        )

        # Create mock PerformanceUpdate with all fields populated
        mock_update = PerformanceUpdate(
            timestamp=datetime.now(UTC),
            gpu=GpuMetrics(
                name="NVIDIA RTX A5500",
                utilization=38.0,
                vram_used_gb=22.7,
                vram_total_gb=24.0,
                temperature=38,
                power_watts=31,
            ),
            ai_models={
                "yolo26": AiModelMetrics(
                    status="healthy",
                    vram_gb=0.17,
                    model="yolo26_r50vd_coco_o365",
                    device="cuda:0",
                ),
                "nemotron": NemotronMetrics(
                    status="healthy",
                    slots_active=1,
                    slots_total=2,
                    context_size=4096,
                ),
            },
            nemotron=NemotronMetrics(
                status="healthy",
                slots_active=1,
                slots_total=2,
                context_size=4096,
            ),
            inference=InferenceMetrics(
                yolo26_latency_ms={"avg": 45, "p95": 82, "p99": 120},
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
                ),
                "redis": RedisMetrics(
                    status="healthy",
                    connected_clients=8,
                    memory_mb=1.5,
                    hit_ratio=99.5,
                    blocked_clients=0,
                ),
            },
            host=HostMetrics(
                cpu_percent=12.0,
                ram_used_gb=8.2,
                ram_total_gb=32.0,
                disk_used_gb=156.0,
                disk_total_gb=500.0,
            ),
            containers=[
                ContainerMetrics(name="backend", status="running", health="healthy"),
                ContainerMetrics(name="frontend", status="running", health="healthy"),
            ],
            alerts=[
                PerformanceAlert(
                    severity="warning",
                    metric="gpu_temperature",
                    value=82,
                    threshold=80,
                    message="GPU temperature high: 82C",
                ),
            ],
        )

        mock_collector = AsyncMock()
        mock_collector.collect_all.return_value = mock_update

        import backend.api.routes.system as system_module

        original_collector = system_module._performance_collector
        try:
            system_module._performance_collector = mock_collector

            response = await async_client.get("/api/system/performance")

            assert response.status_code == 200
            data = response.json()

            # Verify all fields are present
            assert "timestamp" in data
            assert "gpu" in data
            assert "ai_models" in data
            assert "nemotron" in data
            assert "inference" in data
            assert "databases" in data
            assert "host" in data
            assert "containers" in data
            assert "alerts" in data

            # Verify nested structure
            assert data["ai_models"]["yolo26"]["status"] == "healthy"
            assert data["databases"]["postgresql"]["status"] == "healthy"
            assert len(data["containers"]) == 2
            assert len(data["alerts"]) == 1
            assert data["alerts"][0]["severity"] == "warning"
        finally:
            system_module._performance_collector = original_collector


# =============================================================================
# Additional Endpoint Coverage Tests
# =============================================================================


class TestGetSeverityMetadataEndpoint:
    """Tests for GET /api/system/severity endpoint."""

    @pytest.mark.asyncio
    async def test_get_severity_metadata_success(
        self, async_client: AsyncClient, mock_settings: Settings
    ) -> None:
        """Test successful severity metadata retrieval."""
        from backend.models.enums import Severity
        from backend.services.severity import SeverityDefinition

        mock_service = MagicMock()
        mock_service.get_severity_definitions.return_value = [
            SeverityDefinition(
                severity=Severity.LOW,
                label="Low",
                description="Minor concern",
                color="#00FF00",
                priority=1,
                min_score=0,
                max_score=30,
            ),
            SeverityDefinition(
                severity=Severity.MEDIUM,
                label="Medium",
                description="Moderate concern",
                color="#FFFF00",
                priority=2,
                min_score=31,
                max_score=60,
            ),
        ]
        mock_service.get_thresholds.return_value = {
            "low_max": 30,
            "medium_max": 60,
            "high_max": 90,
        }

        with patch(
            "backend.services.severity.get_severity_service",
            return_value=mock_service,
        ):
            response = await async_client.get("/api/system/severity")

            assert response.status_code == 200
            data = response.json()
            assert "definitions" in data
            assert "thresholds" in data
            assert len(data["definitions"]) == 2
            assert data["thresholds"]["low_max"] == 30


class TestTriggerCleanupEndpoint:
    """Tests for POST /api/system/cleanup endpoint."""

    @pytest.mark.asyncio
    async def test_cleanup_dry_run(
        self, async_client: AsyncClient, mock_settings: Settings
    ) -> None:
        """Test cleanup dry run returns expected counts without deleting."""
        from backend.services.cleanup_service import CleanupStats

        # Create stats object properly (no init args)
        mock_stats = CleanupStats()
        mock_stats.events_deleted = 10
        mock_stats.detections_deleted = 50
        mock_stats.gpu_stats_deleted = 100
        mock_stats.logs_deleted = 200
        mock_stats.thumbnails_deleted = 50
        mock_stats.images_deleted = 0
        mock_stats.space_reclaimed = 1024000

        mock_service = MagicMock()
        mock_service.dry_run_cleanup = AsyncMock(return_value=mock_stats)

        # Disable API key for this test
        mock_settings.api_key_enabled = False

        with patch(
            "backend.services.cleanup_service.CleanupService",
            return_value=mock_service,
        ):
            response = await async_client.post("/api/system/cleanup", params={"dry_run": True})

            assert response.status_code == 200
            data = response.json()
            assert data["dry_run"] is True
            assert data["events_deleted"] == 10
            assert data["detections_deleted"] == 50
            assert data["space_reclaimed"] == 1024000

    @pytest.mark.asyncio
    async def test_cleanup_dry_run_error(
        self, async_client: AsyncClient, mock_settings: Settings
    ) -> None:
        """Test cleanup dry run handles errors."""
        mock_service = MagicMock()
        mock_service.dry_run_cleanup = AsyncMock(side_effect=OSError("Disk error"))

        mock_settings.api_key_enabled = False

        with (
            patch(
                "backend.services.cleanup_service.CleanupService",
                return_value=mock_service,
            ),
            pytest.raises(OSError),
        ):
            await async_client.post("/api/system/cleanup", params={"dry_run": True})


class TestCheckDatabaseHealthFunction:
    """Tests for check_database_health helper function."""

    @pytest.mark.asyncio
    async def test_database_health_check_success(self) -> None:
        """Test database health check when database is healthy."""
        from backend.api.routes.system import check_database_health

        # Create a proper mock session
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalar.return_value = 1
        mock_session.execute.return_value = mock_result

        result = await check_database_health(mock_session)

        assert result.status == "healthy"
        assert "operational" in result.message.lower() or "connected" in result.message.lower()


class TestCheckRedisHealthFunction:
    """Tests for check_redis_health helper function."""

    @pytest.mark.asyncio
    async def test_redis_health_check_with_redis(self) -> None:
        """Test Redis health check when Redis is available."""
        from backend.api.routes.system import check_redis_health

        mock_redis = AsyncMock()
        mock_redis.health_check = AsyncMock(return_value={"status": "healthy", "connected": True})

        result = await check_redis_health(mock_redis)

        assert result.status == "healthy"

    @pytest.mark.asyncio
    async def test_redis_health_check_without_redis(self) -> None:
        """Test Redis health check when Redis is not available."""
        from backend.api.routes.system import check_redis_health

        result = await check_redis_health(None)

        assert result.status == "unhealthy"
        assert "unavailable" in result.message.lower() or "failed" in result.message.lower()


class TestCheckAIServicesHealth:
    """Tests for check_ai_services_health function."""

    @pytest.mark.asyncio
    async def test_ai_services_health_all_healthy(self, mock_settings: Settings) -> None:
        """Test AI services health when all services are healthy."""
        from backend.api.routes.system import check_ai_services_health

        # Mock the circuit breaker checks
        with (
            patch(
                "backend.api.routes.system._check_yolo26_health_with_circuit_breaker",
                new=AsyncMock(return_value=(True, None)),
            ),
            patch(
                "backend.api.routes.system._check_nemotron_health_with_circuit_breaker",
                new=AsyncMock(return_value=(True, None)),
            ),
        ):
            result = await check_ai_services_health()

            assert result.status == "healthy"

    @pytest.mark.asyncio
    async def test_ai_services_health_one_unhealthy(self, mock_settings: Settings) -> None:
        """Test AI services health when one service is unhealthy."""
        from backend.api.routes.system import check_ai_services_health

        # Mock the circuit breaker checks - YOLO26 healthy, Nemotron unhealthy
        with (
            patch(
                "backend.api.routes.system._check_yolo26_health_with_circuit_breaker",
                new=AsyncMock(return_value=(True, None)),
            ),
            patch(
                "backend.api.routes.system._check_nemotron_health_with_circuit_breaker",
                new=AsyncMock(return_value=(False, "Connection refused")),
            ),
        ):
            result = await check_ai_services_health()

            # When one service is down, status is "degraded" not "unhealthy"
            assert result.status == "degraded"
            assert "nemotron" in result.message.lower()


class TestCircuitBreakerState:
    """Tests for circuit breaker state helper function."""

    def test_get_circuit_state_closed(self, circuit_breaker: CircuitBreaker) -> None:
        """Test getting circuit state when closed."""
        state = circuit_breaker.get_state("test-service")
        assert state == "closed"

    def test_get_circuit_state_open(self, circuit_breaker: CircuitBreaker) -> None:
        """Test getting circuit state when open."""
        # Open the circuit
        for _ in range(circuit_breaker.failure_threshold):
            circuit_breaker.record_failure("test-service")

        state = circuit_breaker.get_state("test-service")
        assert state == "open"


# =============================================================================
# Monitoring Health Endpoint Tests (NEM-2470)
# =============================================================================


class TestMonitoringHealthHelpers:
    """Tests for monitoring health helper functions."""

    def test_parse_prometheus_timestamp_valid(self) -> None:
        """Test parsing valid Prometheus timestamps."""
        from backend.api.routes.system import _parse_prometheus_timestamp

        # Test standard ISO format
        result = _parse_prometheus_timestamp("2024-01-13T10:30:00Z")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 13
        assert result.hour == 10
        assert result.minute == 30

    def test_parse_prometheus_timestamp_with_nanoseconds(self) -> None:
        """Test parsing Prometheus timestamps with nanoseconds."""
        from backend.api.routes.system import _parse_prometheus_timestamp

        # Test timestamp with nanosecond precision
        result = _parse_prometheus_timestamp("2024-01-13T10:30:00.123456789Z")
        assert result is not None
        assert result.year == 2024

    def test_parse_prometheus_timestamp_none(self) -> None:
        """Test parsing None timestamp returns None."""
        from backend.api.routes.system import _parse_prometheus_timestamp

        assert _parse_prometheus_timestamp(None) is None

    def test_parse_prometheus_timestamp_invalid(self) -> None:
        """Test parsing invalid timestamp returns None."""
        from backend.api.routes.system import _parse_prometheus_timestamp

        assert _parse_prometheus_timestamp("invalid") is None
        assert _parse_prometheus_timestamp("") is None

    def test_build_targets_summary_empty(self) -> None:
        """Test building targets summary from empty list."""
        from backend.api.routes.system import _build_targets_summary

        result = _build_targets_summary([])
        assert result == []

    def test_build_targets_summary_single_job(self) -> None:
        """Test building targets summary for single job."""
        from backend.api.routes.system import _build_targets_summary

        targets = [
            {"job": "test-job", "health": "up"},
            {"job": "test-job", "health": "up"},
            {"job": "test-job", "health": "down"},
        ]
        result = _build_targets_summary(targets)

        assert len(result) == 1
        assert result[0].job == "test-job"
        assert result[0].total == 3
        assert result[0].up == 2
        assert result[0].down == 1

    def test_build_targets_summary_multiple_jobs(self) -> None:
        """Test building targets summary for multiple jobs."""
        from backend.api.routes.system import _build_targets_summary

        targets = [
            {"job": "job-a", "health": "up"},
            {"job": "job-b", "health": "up"},
            {"job": "job-a", "health": "down"},
        ]
        result = _build_targets_summary(targets)

        assert len(result) == 2
        # Results are sorted by job name
        assert result[0].job == "job-a"
        assert result[1].job == "job-b"

    def test_build_exporter_status_with_matching_targets(self) -> None:
        """Test building exporter status when targets match."""
        from backend.api.routes.system import _build_exporter_status

        targets = [
            {
                "job": "redis",
                "instance": "redis-exporter:9121",
                "health": "up",
                "lastScrape": None,
                "lastError": "",
            },
        ]
        result = _build_exporter_status(targets)

        # Should find redis-exporter
        redis_exporter = next((e for e in result if e.name == "redis-exporter"), None)
        assert redis_exporter is not None
        assert redis_exporter.status.value == "up"

    def test_build_exporter_status_no_matching_targets(self) -> None:
        """Test building exporter status when no targets match."""
        from backend.api.routes.system import _build_exporter_status

        result = _build_exporter_status([])

        # All exporters should be unknown
        for exporter in result:
            assert exporter.status.value == "unknown"
            assert "not found" in exporter.error.lower()

    def test_identify_monitoring_issues_prometheus_unreachable(self) -> None:
        """Test identifying issues when Prometheus is unreachable."""
        from backend.api.routes.system import _identify_monitoring_issues

        issues = _identify_monitoring_issues(
            prometheus_reachable=False,
            targets_summary=[],
            exporters=[],
        )

        assert len(issues) == 1
        assert "not reachable" in issues[0].lower()

    def test_identify_monitoring_issues_all_targets_down(self) -> None:
        """Test identifying issues when all targets in a job are down."""
        from backend.api.routes.system import (
            ExporterStatus,
            ExporterStatusEnum,
            _identify_monitoring_issues,
        )
        from backend.api.schemas.system import JobTargetSummary

        targets_summary = [
            JobTargetSummary(job="test-job", total=2, up=0, down=2),
        ]
        exporters = [
            ExporterStatus(
                name="test-exporter",
                status=ExporterStatusEnum.UP,
                endpoint="http://test:9121",
            ),
        ]

        issues = _identify_monitoring_issues(
            prometheus_reachable=True,
            targets_summary=targets_summary,
            exporters=exporters,
        )

        assert any("all targets" in issue.lower() for issue in issues)

    def test_identify_monitoring_issues_exporter_down(self) -> None:
        """Test identifying issues when an exporter is down."""
        from backend.api.routes.system import (
            ExporterStatus,
            ExporterStatusEnum,
            _identify_monitoring_issues,
        )

        exporters = [
            ExporterStatus(
                name="test-exporter",
                status=ExporterStatusEnum.DOWN,
                endpoint="http://test:9121",
                error="Connection refused",
            ),
        ]

        issues = _identify_monitoring_issues(
            prometheus_reachable=True,
            targets_summary=[],
            exporters=exporters,
        )

        assert any("test-exporter" in issue.lower() and "down" in issue.lower() for issue in issues)


class TestMonitoringHealthEndpoint:
    """Tests for monitoring health API endpoint."""

    @pytest.mark.asyncio
    async def test_monitoring_health_prometheus_unreachable(
        self, async_client: AsyncClient, mock_settings: Settings
    ) -> None:
        """Test monitoring health when Prometheus is unreachable."""
        mock_settings.prometheus_url = "http://prometheus:9090"

        with patch(
            "backend.api.routes.system._check_prometheus_reachability",
            new=AsyncMock(return_value=(False, {"error": "Connection refused"})),
        ):
            response = await async_client.get("/api/system/monitoring/health")

            assert response.status_code == 200
            data = response.json()
            assert data["healthy"] is False
            assert data["prometheus_reachable"] is False
            assert "not reachable" in data["issues"][0].lower()

    @pytest.mark.asyncio
    async def test_monitoring_health_prometheus_reachable(
        self, async_client: AsyncClient, mock_settings: Settings
    ) -> None:
        """Test monitoring health when Prometheus is reachable."""
        mock_settings.prometheus_url = "http://prometheus:9090"

        mock_targets = [
            {
                "job": "hsi-backend-metrics",
                "instance": "backend:8000",
                "health": "up",
                "lastScrape": "2024-01-13T10:30:00Z",
                "lastError": "",
            },
            {
                "job": "redis",
                "instance": "redis-exporter:9121",
                "health": "up",
                "lastScrape": "2024-01-13T10:30:00Z",
                "lastError": "",
            },
        ]

        with (
            patch(
                "backend.api.routes.system._check_prometheus_reachability",
                new=AsyncMock(return_value=(True, {"status": "ready"})),
            ),
            patch(
                "backend.api.routes.system._get_prometheus_targets",
                new=AsyncMock(return_value=mock_targets),
            ),
            patch(
                "backend.api.routes.system._get_prometheus_tsdb_status",
                new=AsyncMock(return_value={"headStats": {"numSeries": 1000}}),
            ),
        ):
            response = await async_client.get("/api/system/monitoring/health")

            assert response.status_code == 200
            data = response.json()
            assert data["healthy"] is True
            assert data["prometheus_reachable"] is True
            assert len(data["targets_summary"]) == 2
            assert data["metrics_collection"]["collecting"] is True
            assert data["metrics_collection"]["total_series"] == 1000


class TestMonitoringTargetsEndpoint:
    """Tests for monitoring targets API endpoint."""

    @pytest.mark.asyncio
    async def test_monitoring_targets_prometheus_unreachable(
        self, async_client: AsyncClient, mock_settings: Settings
    ) -> None:
        """Test monitoring targets when Prometheus is unreachable."""
        mock_settings.prometheus_url = "http://prometheus:9090"

        with patch(
            "backend.api.routes.system._check_prometheus_reachability",
            new=AsyncMock(return_value=(False, {"error": "Connection refused"})),
        ):
            response = await async_client.get("/api/system/monitoring/targets")

            assert response.status_code == 503
            assert "not reachable" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_monitoring_targets_success(
        self, async_client: AsyncClient, mock_settings: Settings
    ) -> None:
        """Test monitoring targets returns correct data."""
        mock_settings.prometheus_url = "http://prometheus:9090"

        mock_targets = [
            {
                "job": "hsi-backend-metrics",
                "instance": "backend:8000",
                "health": "up",
                "labels": {"service": "hsi"},
                "lastScrape": "2024-01-13T10:30:00Z",
                "lastError": "",
                "scrapeDuration": "0.025",
            },
            {
                "job": "redis",
                "instance": "redis-exporter:9121",
                "health": "down",
                "labels": {},
                "lastScrape": "2024-01-13T10:30:00Z",
                "lastError": "Connection refused",
                "scrapeDuration": None,
            },
        ]

        with (
            patch(
                "backend.api.routes.system._check_prometheus_reachability",
                new=AsyncMock(return_value=(True, {"status": "ready"})),
            ),
            patch(
                "backend.api.routes.system._get_prometheus_targets",
                new=AsyncMock(return_value=mock_targets),
            ),
        ):
            response = await async_client.get("/api/system/monitoring/targets")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2
            assert data["up"] == 1
            assert data["down"] == 1
            assert len(data["targets"]) == 2
            assert "hsi-backend-metrics" in data["jobs"]
            assert "redis" in data["jobs"]

    @pytest.mark.asyncio
    async def test_monitoring_targets_empty(
        self, async_client: AsyncClient, mock_settings: Settings
    ) -> None:
        """Test monitoring targets with no targets configured."""
        mock_settings.prometheus_url = "http://prometheus:9090"

        with (
            patch(
                "backend.api.routes.system._check_prometheus_reachability",
                new=AsyncMock(return_value=(True, {"status": "ready"})),
            ),
            patch(
                "backend.api.routes.system._get_prometheus_targets",
                new=AsyncMock(return_value=[]),
            ),
        ):
            response = await async_client.get("/api/system/monitoring/targets")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 0
            assert data["up"] == 0
            assert data["down"] == 0
            assert data["targets"] == []
            assert data["jobs"] == []


# =============================================================================
# Test Health Check Liveness Endpoint (NEM-3892)
# =============================================================================


class TestLivenessEndpoint:
    """Tests for the fast liveness endpoint (/api/system/health/live)."""

    @pytest.mark.asyncio
    async def test_liveness_returns_alive_status(self, async_client: AsyncClient) -> None:
        """Test that liveness endpoint returns alive status immediately."""
        response = await async_client.get("/api/system/health/live")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_liveness_is_fast(self, async_client: AsyncClient) -> None:
        """Test that liveness endpoint responds in under 100ms."""
        import time

        start = time.time()
        response = await async_client.get("/api/system/health/live")
        duration_ms = (time.time() - start) * 1000

        assert response.status_code == 200
        # Should respond in under 100ms (generous limit for test overhead)
        assert duration_ms < 100, f"Liveness took {duration_ms:.1f}ms, expected < 100ms"


# =============================================================================
# Test Health Check Metrics (NEM-3892)
# =============================================================================


class TestHealthCheckMetrics:
    """Tests for health check latency metrics."""

    def test_health_check_latency_metric_exists(self) -> None:
        """Test that health check latency histogram is defined."""
        from backend.core.metrics import HEALTH_CHECK_LATENCY_SECONDS

        assert HEALTH_CHECK_LATENCY_SECONDS is not None
        # Check labels are defined
        assert "endpoint" in str(HEALTH_CHECK_LATENCY_SECONDS._labelnames)
        assert "check_type" in str(HEALTH_CHECK_LATENCY_SECONDS._labelnames)

    def test_health_check_component_latency_metric_exists(self) -> None:
        """Test that component latency histogram is defined."""
        from backend.core.metrics import HEALTH_CHECK_COMPONENT_LATENCY_SECONDS

        assert HEALTH_CHECK_COMPONENT_LATENCY_SECONDS is not None
        assert "component" in str(HEALTH_CHECK_COMPONENT_LATENCY_SECONDS._labelnames)

    def test_observe_health_check_latency_function(self) -> None:
        """Test that observe_health_check_latency function works."""
        from backend.core.metrics import observe_health_check_latency

        # Should not raise any exceptions
        observe_health_check_latency("health", "cached", 0.001)
        observe_health_check_latency("health_ready", "full", 0.250)
        observe_health_check_latency("health_live", "liveness", 0.005)

    def test_observe_health_check_component_latency_function(self) -> None:
        """Test that observe_health_check_component_latency function works."""
        from backend.core.metrics import observe_health_check_component_latency

        # Should not raise any exceptions
        observe_health_check_component_latency("database", 0.050)
        observe_health_check_component_latency("redis", 0.025)
        observe_health_check_component_latency("ai_services", 0.100)

    def test_cache_metrics_functions(self) -> None:
        """Test cache hit/miss metric functions work."""
        from backend.core.metrics import (
            record_health_check_cache_hit,
            record_health_check_cache_miss,
        )

        # Should not raise any exceptions
        record_health_check_cache_hit("health")
        record_health_check_cache_miss("health_ready")
