"""Unit tests for kept GPU configuration API routes (F-176, F-178, F-182).

R2a row 36 retired F-177 (POST /gpu-config/detect), F-179 (PUT /gpu-config),
F-180 (GET /gpu-config/services), F-181 (POST /gpu-config/apply, GET /gpu-config/status),
and F-183 (POST /gpu-config/import, POST /gpu-config/rollback).
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes.gpu_config import router
from backend.api.schemas.gpu_config import (
    GpuAssignment,
    GpuAssignmentStrategy,
    GpuConfigResponse,
    GpuDeviceResponse,
    GpuDevicesResponse,
)
from backend.core.database import get_db
from backend.models.gpu_config import GpuConfiguration, GpuConfigurationVersion, SystemSetting
from backend.services.gpu_detection_service import GpuDevice as GpuDeviceDataclass


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def client(mock_db_session: AsyncMock) -> TestClient:
    """Create a test client with mocked dependencies."""
    app = FastAPI()
    app.include_router(router)

    async def override_get_db():
        yield mock_db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_gpus() -> list[GpuDeviceDataclass]:
    """Create sample GPU devices for testing."""
    return [
        GpuDeviceDataclass(
            index=0,
            name="RTX A5500",
            vram_total_mb=24564,
            vram_used_mb=19304,
            uuid="GPU-12345678-1234-1234-1234-123456789012",
            compute_capability="8.6",
        ),
        GpuDeviceDataclass(
            index=1,
            name="RTX A400",
            vram_total_mb=4094,
            vram_used_mb=329,
            uuid="GPU-87654321-4321-4321-4321-210987654321",
            compute_capability="8.6",
        ),
    ]


@pytest.fixture
def sample_assignments() -> list[GpuAssignment]:
    """Create sample GPU assignments for testing."""
    return [
        GpuAssignment(service="ai-llm", gpu_index=0, vram_budget_override=None),
        GpuAssignment(service="ai-yolo26", gpu_index=0, vram_budget_override=None),
        GpuAssignment(service="ai-enrichment", gpu_index=1, vram_budget_override=3.5),
    ]


class TestMountedGpuRoutes:
    """Tests that only the kept F-176, F-178, and F-182 GET routes remain on router."""

    def test_only_kept_gpu_routes_are_mounted(self) -> None:
        """R2a row 36 retired detect, update, apply, status, services, import, and rollback."""
        mounted = sorted((m, r.path) for r in router.routes for m in getattr(r, "methods", ()))
        assert mounted == [
            ("GET", "/api/system/ai-services"),
            ("GET", "/api/system/gpu-config"),
            ("GET", "/api/system/gpu-config/export"),
            ("GET", "/api/system/gpu-config/history"),
            ("GET", "/api/system/gpu-config/history/diff"),
            ("GET", "/api/system/gpu-config/history/{version_id}"),
            ("GET", "/api/system/gpu-config/preview"),
            ("GET", "/api/system/gpus"),
        ]


class TestListGpus:
    """Tests for GET /api/system/gpus endpoint."""

    @patch("backend.api.routes.gpu_config.get_gpu_detection_service", autospec=True)
    def test_list_gpus_returns_empty_list_when_no_gpus(
        self, mock_get_service: MagicMock, client: TestClient
    ) -> None:
        """Test that listing GPUs returns empty list when no GPUs detected."""
        mock_service = AsyncMock()
        mock_service.detect_gpus = AsyncMock(return_value=[])
        mock_get_service.return_value = mock_service

        response = client.get("/api/system/gpus")

        assert response.status_code == 200
        data = response.json()
        assert "gpus" in data
        assert isinstance(data["gpus"], list)
        assert len(data["gpus"]) == 0

    @patch("backend.api.routes.gpu_config.get_gpu_detection_service", autospec=True)
    def test_list_gpus_returns_detected_gpus(
        self, mock_get_service: MagicMock, client: TestClient, sample_gpus: list[GpuDeviceDataclass]
    ) -> None:
        """Test that listing GPUs returns all detected GPUs with correct schema."""
        mock_service = AsyncMock()
        mock_service.detect_gpus = AsyncMock(return_value=sample_gpus)
        mock_get_service.return_value = mock_service

        response = client.get("/api/system/gpus")

        assert response.status_code == 200
        data = response.json()
        assert len(data["gpus"]) == 2

        gpu0 = data["gpus"][0]
        assert gpu0["index"] == 0
        assert gpu0["name"] == "RTX A5500"
        assert gpu0["vram_total_mb"] == 24564
        assert gpu0["vram_used_mb"] == 19304
        assert gpu0["compute_capability"] == "8.6"

        gpu1 = data["gpus"][1]
        assert gpu1["index"] == 1
        assert gpu1["name"] == "RTX A400"
        assert gpu1["vram_total_mb"] == 4094
        assert gpu1["vram_used_mb"] == 329
        assert gpu1["compute_capability"] == "8.6"

    @patch("backend.api.routes.gpu_config.get_gpu_detection_service", autospec=True)
    def test_list_gpus_handles_detection_service_errors(
        self, mock_get_service: MagicMock, client: TestClient
    ) -> None:
        """Test that detection service errors return empty list gracefully."""
        mock_service = AsyncMock()
        mock_service.detect_gpus = AsyncMock(side_effect=Exception("NVML init failed"))
        mock_get_service.return_value = mock_service

        response = client.get("/api/system/gpus")

        assert response.status_code == 200
        assert response.json()["gpus"] == []

    @patch("backend.api.routes.gpu_config.get_gpu_detection_service", autospec=True)
    def test_list_gpus_validates_response_schema(
        self, mock_get_service: MagicMock, client: TestClient, sample_gpus: list[GpuDeviceDataclass]
    ) -> None:
        """Test that response matches GpuDevicesResponse schema."""
        mock_service = AsyncMock()
        mock_service.detect_gpus = AsyncMock(return_value=sample_gpus)
        mock_get_service.return_value = mock_service

        response = client.get("/api/system/gpus")

        assert response.status_code == 200
        validated = GpuDevicesResponse(**response.json())
        assert len(validated.gpus) == 2
        assert validated.gpus[0].index == 0
        assert validated.gpus[1].index == 1


class TestGetGpuConfig:
    """Tests for GET /api/system/gpu-config endpoint."""

    def test_get_gpu_config_returns_default_when_none_exists(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that default config is returned when no config exists in DB."""
        mock_strategy_result = MagicMock()
        mock_strategy_result.scalar_one_or_none.return_value = None

        mock_assignments_result = MagicMock()
        mock_assignments_result.scalars.return_value.all.return_value = []

        mock_updated_at_result = MagicMock()
        mock_updated_at_result.scalar_one_or_none.return_value = None

        mock_db_session.execute.side_effect = [
            mock_strategy_result,
            mock_assignments_result,
            mock_updated_at_result,
        ]

        response = client.get("/api/system/gpu-config")

        assert response.status_code == 200
        data = response.json()
        assert data["strategy"] == "manual"
        assert "assignments" in data
        assert isinstance(data["assignments"], list)
        assert len(data["assignments"]) >= 1
        assert data["updated_at"] is None

    def test_get_gpu_config_returns_saved_config(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that saved config is returned from database."""
        mock_strategy_setting = SystemSetting(
            key="gpu_assignment_strategy",
            value={"strategy": "vram_based"},
        )
        mock_strategy_result = MagicMock()
        mock_strategy_result.scalar_one_or_none.return_value = mock_strategy_setting

        mock_config1 = GpuConfiguration(
            service_name="ai-llm",
            gpu_index=0,
            strategy="vram_based",
            enabled=True,
        )
        mock_config2 = GpuConfiguration(
            service_name="ai-yolo26",
            gpu_index=1,
            strategy="vram_based",
            enabled=True,
            vram_budget_override=4.5,
        )
        mock_assignments_result = MagicMock()
        mock_assignments_result.scalars.return_value.all.return_value = [
            mock_config1,
            mock_config2,
        ]

        updated_at = datetime(2026, 1, 23, 10, 30, 0, tzinfo=UTC)
        mock_updated_at_result = MagicMock()
        mock_updated_at_result.scalar_one_or_none.return_value = updated_at

        mock_db_session.execute.side_effect = [
            mock_strategy_result,
            mock_assignments_result,
            mock_updated_at_result,
        ]

        response = client.get("/api/system/gpu-config")

        assert response.status_code == 200
        data = response.json()
        assert data["strategy"] == "vram_based"
        assert len(data["assignments"]) == 2
        assert data["assignments"][0]["service"] == "ai-llm"
        assert data["assignments"][0]["gpu_index"] == 0
        assert data["assignments"][1]["service"] == "ai-yolo26"
        assert data["assignments"][1]["gpu_index"] == 1
        assert data["assignments"][1]["vram_budget_override"] == 4.5
        assert data["updated_at"] is not None

    def test_get_gpu_config_includes_all_assignment_fields(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that all assignment fields are included in response."""
        mock_strategy_result = MagicMock()
        mock_strategy_result.scalar_one_or_none.return_value = None

        mock_config = GpuConfiguration(
            service_name="ai-enrichment",
            gpu_index=1,
            strategy="manual",
            vram_budget_override=3.5,
            enabled=True,
        )
        mock_assignments_result = MagicMock()
        mock_assignments_result.scalars.return_value.all.return_value = [mock_config]

        mock_updated_at_result = MagicMock()
        mock_updated_at_result.scalar_one_or_none.return_value = None

        mock_db_session.execute.side_effect = [
            mock_strategy_result,
            mock_assignments_result,
            mock_updated_at_result,
        ]

        response = client.get("/api/system/gpu-config")

        assert response.status_code == 200
        data = response.json()
        assignment = data["assignments"][0]
        assert "service" in assignment
        assert "gpu_index" in assignment
        assert "vram_budget_override" in assignment
        assert assignment["service"] == "ai-enrichment"
        assert assignment["gpu_index"] == 1
        assert assignment["vram_budget_override"] == 3.5

    def test_get_gpu_config_handles_database_errors(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that database errors return 500."""
        mock_db_session.execute.side_effect = Exception("Database connection failed")

        response = client.get("/api/system/gpu-config")

        assert response.status_code == 500
        assert "Failed to load GPU configuration" in response.json()["detail"]


class TestPreviewGpuConfig:
    """Tests for GET /api/system/gpu-config/preview endpoint."""

    @patch("backend.api.routes.gpu_config.get_gpu_detection_service", autospec=True)
    def test_preview_gpu_config_returns_preview_for_strategy(
        self, mock_get_service: MagicMock, client: TestClient, sample_gpus: list[GpuDeviceDataclass]
    ) -> None:
        """Test that preview returns proposed assignments for strategy."""
        mock_service = AsyncMock()
        mock_service.detect_gpus = AsyncMock(return_value=sample_gpus)
        mock_get_service.return_value = mock_service

        response = client.get("/api/system/gpu-config/preview?strategy=vram_based")

        assert response.status_code == 200
        data = response.json()
        assert data["strategy"] == "vram_based"
        assert "proposed_assignments" in data
        assert "warnings" in data
        assert isinstance(data["proposed_assignments"], list)
        assert len(data["proposed_assignments"]) >= 1

    @patch("backend.api.routes.gpu_config.get_gpu_detection_service", autospec=True)
    def test_preview_gpu_config_validates_strategy_parameter(
        self, mock_get_service: MagicMock, client: TestClient
    ) -> None:
        """Test that invalid strategy parameter is rejected."""
        response = client.get("/api/system/gpu-config/preview")

        assert response.status_code == 422
        assert "Field required" in response.text or "required" in response.text.lower()

    @patch("backend.api.routes.gpu_config.get_gpu_detection_service", autospec=True)
    def test_preview_gpu_config_for_each_strategy(
        self, mock_get_service: MagicMock, client: TestClient, sample_gpus: list[GpuDeviceDataclass]
    ) -> None:
        """Test that preview works for each assignment strategy."""
        mock_service = AsyncMock()
        mock_service.detect_gpus = AsyncMock(return_value=sample_gpus)
        mock_get_service.return_value = mock_service

        strategies = [
            "manual",
            "vram_based",
            "latency_optimized",
            "isolation_first",
            "balanced",
        ]

        for strategy in strategies:
            response = client.get(f"/api/system/gpu-config/preview?strategy={strategy}")

            assert response.status_code == 200, f"Strategy {strategy} failed"
            data = response.json()
            assert data["strategy"] == strategy
            assert len(data["proposed_assignments"]) >= 1

    @patch("backend.api.routes.gpu_config.get_gpu_detection_service", autospec=True)
    def test_preview_gpu_config_returns_warnings_when_appropriate(
        self, mock_get_service: MagicMock, client: TestClient
    ) -> None:
        """Test that preview returns warnings when strategy constraints aren't met."""
        single_gpu = [
            GpuDeviceDataclass(
                index=0,
                name="GPU 0",
                vram_total_mb=8000,
                vram_used_mb=0,
                uuid="GPU-00000000-0000-0000-0000-000000000000",
                compute_capability="8.6",
            )
        ]

        mock_service = AsyncMock()
        mock_service.detect_gpus = AsyncMock(return_value=single_gpu)
        mock_get_service.return_value = mock_service

        response = client.get("/api/system/gpu-config/preview?strategy=isolation_first")

        assert response.status_code == 200
        data = response.json()
        assert len(data["warnings"]) > 0
        assert any("isolation" in w.lower() for w in data["warnings"])

    @patch("backend.api.routes.gpu_config.get_gpu_detection_service", autospec=True)
    def test_preview_gpu_config_handles_no_gpus_detected(
        self, mock_get_service: MagicMock, client: TestClient
    ) -> None:
        """Test preview behavior when no GPUs are detected."""
        mock_service = AsyncMock()
        mock_service.detect_gpus = AsyncMock(return_value=[])
        mock_get_service.return_value = mock_service

        response = client.get("/api/system/gpu-config/preview?strategy=manual")

        assert response.status_code == 200
        data = response.json()
        assert data["strategy"] == "manual"
        assert len(data["warnings"]) > 0
        assert any("No GPUs detected" in w for w in data["warnings"])


class TestGpuConfigSchemas:
    """Tests for GPU configuration schemas."""

    def test_gpu_device_response_schema(self):
        """Test GpuDeviceResponse schema validation."""
        device = GpuDeviceResponse(
            index=0,
            name="RTX A5500",
            vram_total_mb=24564,
            vram_used_mb=19304,
            compute_capability="8.6",
        )

        data = device.model_dump()
        assert data["index"] == 0
        assert data["name"] == "RTX A5500"
        assert data["vram_total_mb"] == 24564
        assert data["vram_used_mb"] == 19304
        assert data["compute_capability"] == "8.6"

    def test_gpu_assignment_schema_with_optional_fields(self):
        """Test GpuAssignment schema with optional fields."""
        assignment = GpuAssignment(
            service="ai-llm",
            gpu_index=0,
            vram_budget_override=None,
        )

        data = assignment.model_dump()
        assert data["service"] == "ai-llm"
        assert data["gpu_index"] == 0
        assert data["vram_budget_override"] is None

        assignment2 = GpuAssignment(
            service="ai-enrichment",
            gpu_index=1,
            vram_budget_override=3.5,
        )
        data2 = assignment2.model_dump()
        assert data2["vram_budget_override"] == 3.5

    def test_gpu_config_response_schema(self):
        """Test GpuConfigResponse schema."""
        response = GpuConfigResponse(
            strategy=GpuAssignmentStrategy.MANUAL,
            assignments=[GpuAssignment(service="ai-llm", gpu_index=0, vram_budget_override=None)],
            updated_at=datetime(2026, 1, 23, 10, 30, 0, tzinfo=UTC),
        )

        data = response.model_dump()
        assert data["strategy"] == "manual"
        assert len(data["assignments"]) == 1
        assert data["updated_at"] is not None

    def test_gpu_assignment_strategy_enum_values(self):
        """Test GpuAssignmentStrategy enum has all expected values."""
        assert GpuAssignmentStrategy.MANUAL.value == "manual"
        assert GpuAssignmentStrategy.VRAM_BASED.value == "vram_based"
        assert GpuAssignmentStrategy.LATENCY_OPTIMIZED.value == "latency_optimized"
        assert GpuAssignmentStrategy.ISOLATION_FIRST.value == "isolation_first"


class TestDiffRouteNotShadowed:
    """[r285] F-182's Compare: history/diff must reach the diff handler, not {version_id}.

    Ruling 285: the diff route is registered after
    ``GET /gpu-config/history/{version_id}``, so Starlette matches the literal ``diff``
    as a version id and the handler queries ``WHERE id == 'diff'`` — asyncpg rejects the
    literal and the request answers 500. The fix registers ``diff`` first. Both tests call
    the diff route through the MOUNTED router, as the package block requires.
    """

    def _two_versions(self) -> list[MagicMock]:
        """Two configuration versions, 1 and 2, differing in strategy and assignments."""
        v1 = MagicMock(spec=GpuConfigurationVersion)
        v1.id = "version-1-uuid"
        v1.version_number = 1
        v1.strategy = "vram_based"
        v1.description = "initial"
        v1.created_at = datetime(2026, 10, 20, 12, 0, 0, tzinfo=UTC)
        v1.created_by = "test"
        v1.assignments = [
            {"service": "ai-llm", "gpu_index": 0, "vram_budget_override": None},
        ]
        v2 = MagicMock(spec=GpuConfigurationVersion)
        v2.id = "version-2-uuid"
        v2.version_number = 2
        v2.strategy = "manual"
        v2.description = "rebalance"
        v2.created_at = datetime(2026, 10, 20, 13, 0, 0, tzinfo=UTC)
        v2.created_by = "test"
        v2.assignments = [
            {"service": "ai-llm", "gpu_index": 1, "vram_budget_override": 2.5},
        ]
        return [v1, v2]

    def test_diff_route_reaches_the_diff_handler_through_the_mounted_router(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """GET history/diff?from_version=1&to_version=2 must answer the diff, not 500.

        Red at the ready head: the request is matched by the ``{version_id}`` route, so
        ``get_config_version`` runs its id-equality query and the mock session's scalar
        is not the diff payload the handler returns.
        """
        versions = self._two_versions()
        result = MagicMock()
        result.scalars.return_value.all.return_value = versions
        # The shadowed route (get_config_version) calls scalar_one_or_none(); None makes
        # it answer its own 404 "Configuration version diff not found" — the readable red.
        result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = result

        response = client.get("/api/system/gpu-config/history/diff?from_version=1&to_version=2")

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["from_version"] == 1
        assert data["to_version"] == 2
        assert data["strategy_changed"] is True
        assert data["old_strategy"] == "vram_based"
        assert data["new_strategy"] == "manual"
        assert data["assignment_changes"] == [
            {
                "service": "ai-llm",
                "change_type": "modified",
                "old_gpu_index": 0,
                "new_gpu_index": 1,
                "old_vram_override": None,
                "new_vram_override": 2.5,
            }
        ]

    def test_diff_route_filters_by_version_number_not_the_string_diff(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """The first statement the route executes filters version_number, never id == 'diff'.

        Pins the handler identity from the SQL side: with the shadowing order the mounted
        request reaches ``get_config_version``, whose statement filters
        ``GpuConfigurationVersion.id == 'diff'`` — the literal asyncpg rejects.
        """
        versions = self._two_versions()
        result = MagicMock()
        result.scalars.return_value.all.return_value = versions
        mock_db_session.execute.return_value = result

        client.get("/api/system/gpu-config/history/diff?from_version=1&to_version=2")

        statement = mock_db_session.execute.await_args_list[0].args[0]
        compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
        assert "version_number IN" in compiled, compiled
        assert "'diff'" not in compiled, compiled
        assert GpuAssignmentStrategy.BALANCED.value == "balanced"
