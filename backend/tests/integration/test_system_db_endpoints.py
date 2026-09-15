"""Integration tests for the DB-backed /api/system endpoints.

M3 Task 3 (audit 1.3): these classes lived in
`backend/tests/unit/api/routes/test_system.py` behind class-level
`@pytest.mark.integration` decorators. The root-conftest
`pytest_collection_modifyitems` hook skips ANY /unit/ item carrying the
integration marker unconditionally (conftest.py:438-441), so all 10 tests here
had never executed. Moved to the tier that actually runs them.

Fixture notes:
- `isolated_db` is re-aliased to integration/conftest.py's `session` below
  (without the alias it would still resolve to the ROOT fixture, which yields
  None and would fight the integration client's engine for DATABASE_URL).
- `async_client` is rebuilt here on top of the integration `client` fixture
  (integration/conftest.py:1438: full app + integration_db + mock_redis +
  X-API-Key), replacing the source file's app-with-router mock client — the
  endpoints below reach full-app dependency paths (get_redis in the
  rate-limiter/readiness chain) the mock router never wired.
- `mock_settings` is copied verbatim from the source file.
- TestSeverityThresholds carries here ONLY its DB-backed sibling; the
  pure-logic sibling stayed in the unit file.
"""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.system import register_workers
from backend.api.schemas.system import HealthCheckServiceStatus
from backend.core.config import Settings


@pytest.fixture
def async_client(client: AsyncClient) -> AsyncClient:
    """Expose the integration `client` under the name the moved tests use."""
    return client


@pytest.fixture(autouse=True)
def _clear_health_caches() -> Generator[None]:
    """Clear the module-level health/readiness caches before and after each
    test. The shipped endpoints memoize verdicts for HEALTH_CACHE_TTL_SECONDS
    (~10s, NEM-3892 caches in system._health_cache/_readiness_cache), so a
    preceding test's cached verdict answers within the window — the exact
    ledger R-T7-HEALTH class; see test_health_checks.py:178 and the
    test_system_api.py cache-reset precedent. Un-skipped by M3 Task 3, these
    tests now actually run, so they must defuse the cache the way their
    already-green siblings do."""
    from backend.api.routes.system import clear_health_cache

    clear_health_cache()
    yield
    clear_health_cache()


@pytest.fixture
async def isolated_db(session: AsyncSession) -> AsyncSession:
    """Alias the unit tier's `isolated_db` name onto the integration `session`.

    The moved tests request `isolated_db` (the root fixture they were written
    against). Reusing integration/conftest.py's worker-isolated session keeps
    endpoint and test on ONE engine against the worker DB — the root fixture's
    close_db()/init_db() churn would fight the integration client's engine.
    """
    yield session


@pytest.fixture
def mock_settings() -> Settings:
    """Patch system-route settings reads (copied from the source unit file)."""
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


@pytest.mark.integration  # M3 Task 3: full app stack via the integration `client`
class TestSeverityThresholds:
    """DB-backed tests for severity threshold configuration.

    M3 Task 3: split out from backend/tests/unit/api/routes/test_system.py
    (the pure-logic sibling stayed in the unit file).
    """

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


@pytest.mark.integration  # M3 Task 3: full app stack via the integration `client`
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


@pytest.mark.integration  # M3 Task 3: full app stack via the integration `client`
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


@pytest.mark.integration  # M3 Task 3: full app stack via the integration `client`
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


@pytest.mark.integration  # M3 Task 3: full app stack via the integration `client`
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


@pytest.mark.integration  # M3 Task 3: full app stack via the integration `client`
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
