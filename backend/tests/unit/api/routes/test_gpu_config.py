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
from backend.models.gpu_config import GpuConfiguration, SystemSetting
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
        assert GpuAssignmentStrategy.BALANCED.value == "balanced"
