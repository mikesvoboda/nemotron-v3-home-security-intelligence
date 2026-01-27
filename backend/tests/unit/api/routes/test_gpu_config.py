"""Unit tests for GPU configuration API routes.

This test file provides comprehensive coverage for all 7 GPU configuration
endpoints in backend/api/routes/gpu_config.py:

1. GET /api/system/gpus - List detected GPUs
2. GET /api/system/gpu-config - Get current GPU configuration
3. PUT /api/system/gpu-config - Update GPU configuration
4. POST /api/system/gpu-config/apply - Apply configuration and restart services
5. GET /api/system/gpu-config/status - Get apply operation status
6. POST /api/system/gpu-config/detect - Re-detect GPUs and update DB
7. GET /api/system/gpu-config/preview - Preview auto-assignment strategy

Target: ~30-40 test cases covering all success and error scenarios.

Related Issues:
    - NEM-3321: Add backend API route tests for GPU configuration
    - NEM-3318: Implement GPU configuration API routes
    - NEM-3292: Multi-GPU Support Epic

Design Document:
    See docs/plans/2025-01-23-multi-gpu-support-design.md
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
    ServiceStatus,
)
from backend.core.database import get_db
from backend.models.gpu_config import GpuConfiguration, SystemSetting
from backend.services.gpu_detection_service import GpuDevice as GpuDeviceDataclass

# =============================================================================
# Fixtures
# =============================================================================


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
    # Reset global fallback state before each test to ensure isolation
    from backend.api.routes import gpu_config

    gpu_config._apply_state_fallback = {
        "in_progress": False,
        "operation_id": None,
        "services_pending": [],
        "services_completed": [],
        "service_statuses": [],
        "last_updated": None,
    }

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


@pytest.fixture(autouse=True)
def reset_apply_state():
    """Reset the global _apply_state before each test."""
    from backend.api.routes import gpu_config

    gpu_config._apply_state = {
        "in_progress": False,
        "services_pending": [],
        "services_completed": [],
        "service_statuses": [],
        "last_updated": None,
    }
    yield


# =============================================================================
# GET /api/system/gpus Tests
# =============================================================================


class TestListGpus:
    """Tests for GET /api/system/gpus endpoint."""

    @patch("backend.api.routes.gpu_config.get_gpu_detection_service")
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

    @patch("backend.api.routes.gpu_config.get_gpu_detection_service")
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

        # Validate first GPU
        gpu0 = data["gpus"][0]
        assert gpu0["index"] == 0
        assert gpu0["name"] == "RTX A5500"
        assert gpu0["vram_total_mb"] == 24564
        assert gpu0["vram_used_mb"] == 19304
        assert gpu0["compute_capability"] == "8.6"

        # Validate second GPU
        gpu1 = data["gpus"][1]
        assert gpu1["index"] == 1
        assert gpu1["name"] == "RTX A400"
        assert gpu1["vram_total_mb"] == 4094
        assert gpu1["vram_used_mb"] == 329
        assert gpu1["compute_capability"] == "8.6"

    @patch("backend.api.routes.gpu_config.get_gpu_detection_service")
    def test_list_gpus_handles_detection_service_errors(
        self, mock_get_service: MagicMock, client: TestClient
    ) -> None:
        """Test that detection service errors return 500 with error detail."""
        mock_service = AsyncMock()
        mock_service.detect_gpus = AsyncMock(side_effect=Exception("NVML init failed"))
        mock_get_service.return_value = mock_service

        response = client.get("/api/system/gpus")

        assert response.status_code == 500
        assert "GPU detection failed" in response.json()["detail"]
        assert "NVML init failed" in response.json()["detail"]

    @patch("backend.api.routes.gpu_config.get_gpu_detection_service")
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


# =============================================================================
# GET /api/system/gpu-config Tests
# =============================================================================


class TestGetGpuConfig:
    """Tests for GET /api/system/gpu-config endpoint."""

    def test_get_gpu_config_returns_default_when_none_exists(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that default config is returned when no config exists in DB."""
        # Mock empty results for strategy and assignments
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
        assert data["strategy"] == "manual"  # Default strategy
        assert "assignments" in data
        assert isinstance(data["assignments"], list)
        # Should have default assignments for all services
        assert len(data["assignments"]) >= 3  # ai-llm, ai-yolo26, ai-enrichment
        assert data["updated_at"] is None

    def test_get_gpu_config_returns_saved_config(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that saved config is returned from database."""
        # Mock strategy setting
        mock_strategy_setting = SystemSetting(
            key="gpu_assignment_strategy",
            value={"strategy": "vram_based"},
        )
        mock_strategy_result = MagicMock()
        mock_strategy_result.scalar_one_or_none.return_value = mock_strategy_setting

        # Mock GPU configurations
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

        # Mock updated_at timestamp
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


# =============================================================================
# PUT /api/system/gpu-config Tests
# =============================================================================


class TestUpdateGpuConfig:
    """Tests for PUT /api/system/gpu-config endpoint."""

    @patch("backend.api.routes.gpu_config.get_gpu_detection_service")
    def test_update_gpu_config_validates_required_fields(
        self, mock_get_service: MagicMock, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that update validates required fields (though request body is optional)."""
        # Empty request body is valid - should keep current config
        mock_strategy_result = MagicMock()
        mock_strategy_result.scalar_one_or_none.return_value = None

        mock_assignments_result = MagicMock()
        mock_assignments_result.scalars.return_value.all.return_value = []

        mock_existing_configs_result = MagicMock()
        mock_existing_configs_result.scalars.return_value.all.return_value = []

        # update_gpu_config flow:
        # 1. Get current strategy (line 583-585)
        # 2. Get current assignments (line 587-590)
        # 3. Detect GPUs for validation (mocked via get_gpu_detection_service)
        # 4. Set current strategy (line 599) - calls db.execute in _set_current_strategy
        # 5. Save assignments (line 602) - calls db.execute in _save_assignments_to_db
        mock_db_session.execute.side_effect = [
            mock_strategy_result,  # Get current strategy
            mock_assignments_result,  # Get current assignments
            mock_strategy_result,  # Set current strategy - check if exists
            mock_existing_configs_result,  # Save assignments - get existing configs
        ]

        mock_service = AsyncMock()
        mock_service.detect_gpus = AsyncMock(return_value=[])
        mock_get_service.return_value = mock_service

        response = client.put("/api/system/gpu-config", json={})

        # Should succeed with empty request
        assert response.status_code == 200
        assert response.json()["success"] is True

    @patch("backend.api.routes.gpu_config.get_gpu_detection_service")
    def test_update_gpu_config_rejects_invalid_gpu_indices(
        self, mock_get_service: MagicMock, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that invalid GPU indices are flagged in warnings."""
        mock_service = AsyncMock()
        mock_service.detect_gpus = AsyncMock(
            return_value=[
                GpuDeviceDataclass(
                    index=0,
                    name="GPU 0",
                    vram_total_mb=8000,
                    vram_used_mb=0,
                    uuid="GPU-00000000-0000-0000-0000-000000000000",
                    compute_capability="8.6",
                )
            ]
        )
        mock_get_service.return_value = mock_service

        mock_strategy_result = MagicMock()
        mock_strategy_result.scalar_one_or_none.return_value = None

        mock_assignments_result = MagicMock()
        mock_assignments_result.scalars.return_value.all.return_value = []

        mock_existing_configs_result = MagicMock()
        mock_existing_configs_result.scalars.return_value.all.return_value = []

        mock_db_session.execute.side_effect = [
            mock_strategy_result,
            mock_assignments_result,
            mock_strategy_result,
            mock_existing_configs_result,
        ]

        # Assign to non-existent GPU 2
        request_data = {
            "strategy": "manual",
            "assignments": [{"service": "ai-llm", "gpu_index": 2, "vram_budget_override": None}],
        }

        response = client.put("/api/system/gpu-config", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["warnings"]) > 0
        assert any("non-existent GPU 2" in w for w in data["warnings"])

    @patch("backend.api.routes.gpu_config.get_gpu_detection_service")
    def test_update_gpu_config_returns_vram_warnings_when_over_budget(
        self,
        mock_get_service: MagicMock,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_gpus: list[GpuDeviceDataclass],
    ) -> None:
        """Test that VRAM warnings are returned when assignments exceed GPU capacity."""
        mock_service = AsyncMock()
        mock_service.detect_gpus = AsyncMock(return_value=sample_gpus)
        mock_get_service.return_value = mock_service

        mock_strategy_result = MagicMock()
        mock_strategy_result.scalar_one_or_none.return_value = None

        mock_assignments_result = MagicMock()
        mock_assignments_result.scalars.return_value.all.return_value = []

        mock_existing_configs_result = MagicMock()
        mock_existing_configs_result.scalars.return_value.all.return_value = []

        mock_db_session.execute.side_effect = [
            mock_strategy_result,
            mock_assignments_result,
            mock_strategy_result,
            mock_existing_configs_result,
        ]

        # Assign more VRAM than GPU 1 has (4094 MB)
        request_data = {
            "strategy": "manual",
            "assignments": [
                {"service": "ai-llm", "gpu_index": 1, "vram_budget_override": 10.0},  # 10GB > 4GB
            ],
        }

        response = client.put("/api/system/gpu-config", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["warnings"]) > 0
        assert any("over budget" in w.lower() for w in data["warnings"])
        assert any("GPU 1" in w for w in data["warnings"])

    @patch("backend.api.routes.gpu_config.get_gpu_detection_service")
    def test_update_gpu_config_saves_to_database_correctly(
        self, mock_get_service: MagicMock, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that configuration is saved to database correctly."""
        mock_service = AsyncMock()
        mock_service.detect_gpus = AsyncMock(return_value=[])
        mock_get_service.return_value = mock_service

        mock_strategy_result = MagicMock()
        mock_strategy_result.scalar_one_or_none.return_value = None

        mock_assignments_result = MagicMock()
        mock_assignments_result.scalars.return_value.all.return_value = []

        mock_existing_configs_result = MagicMock()
        mock_existing_configs_result.scalars.return_value.all.return_value = []

        mock_db_session.execute.side_effect = [
            mock_strategy_result,
            mock_assignments_result,
            mock_strategy_result,
            mock_existing_configs_result,
        ]

        request_data = {
            "strategy": "vram_based",
            "assignments": [
                {"service": "ai-llm", "gpu_index": 0, "vram_budget_override": None},
            ],
        }

        response = client.put("/api/system/gpu-config", json=request_data)

        assert response.status_code == 200
        assert response.json()["success"] is True
        # Verify commit was called
        mock_db_session.commit.assert_called_once()

    @patch("backend.api.routes.gpu_config.get_gpu_detection_service")
    def test_update_gpu_config_handles_database_errors(
        self, mock_get_service: MagicMock, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that database errors are handled with rollback."""
        mock_service = AsyncMock()
        mock_service.detect_gpus = AsyncMock(return_value=[])
        mock_get_service.return_value = mock_service

        mock_db_session.execute.side_effect = Exception("Database error")

        request_data = {"strategy": "manual"}

        response = client.put("/api/system/gpu-config", json=request_data)

        assert response.status_code == 500
        assert "Failed to save GPU configuration" in response.json()["detail"]
        mock_db_session.rollback.assert_called_once()


# =============================================================================
# POST /api/system/gpu-config/apply Tests
# =============================================================================


class TestApplyGpuConfig:
    """Tests for POST /api/system/gpu-config/apply endpoint."""

    @patch("backend.api.routes.gpu_config.GpuConfigService")
    def test_apply_gpu_config_returns_success_response(
        self, mock_config_service_class: MagicMock, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that apply returns success response with service statuses."""
        # Mock config service
        mock_config_service = AsyncMock()
        mock_config_service.write_config_files = AsyncMock()
        mock_config_service_class.return_value = mock_config_service

        # Mock strategy and assignments
        mock_strategy_result = MagicMock()
        mock_strategy_result.scalar_one_or_none.return_value = None

        mock_config1 = GpuConfiguration(
            service_name="ai-llm", gpu_index=0, strategy="manual", enabled=True
        )
        mock_assignments_result = MagicMock()
        mock_assignments_result.scalars.return_value.all.return_value = [mock_config1]

        mock_db_session.execute.side_effect = [
            mock_strategy_result,
            mock_assignments_result,
        ]

        response = client.post("/api/system/gpu-config/apply")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "restarted_services" in data
        assert "service_statuses" in data
        assert "warnings" in data
        assert len(data["restarted_services"]) >= 1

    @patch("backend.api.routes.gpu_config.GpuConfigService")
    def test_apply_gpu_config_handles_restart_failures(
        self, mock_config_service_class: MagicMock, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that restart failures are handled gracefully."""
        # Mock config service to raise error
        mock_config_service = AsyncMock()
        mock_config_service.write_config_files = AsyncMock(
            side_effect=Exception("Docker restart failed")
        )
        mock_config_service_class.return_value = mock_config_service

        mock_strategy_result = MagicMock()
        mock_strategy_result.scalar_one_or_none.return_value = None

        mock_config = GpuConfiguration(
            service_name="ai-llm", gpu_index=0, strategy="manual", enabled=True
        )
        mock_assignments_result = MagicMock()
        mock_assignments_result.scalars.return_value.all.return_value = [mock_config]

        mock_db_session.execute.side_effect = [
            mock_strategy_result,
            mock_assignments_result,
        ]

        response = client.post("/api/system/gpu-config/apply")

        assert response.status_code == 500
        assert "Failed to apply GPU configuration" in response.json()["detail"]

    @patch("backend.api.routes.gpu_config.GpuConfigService")
    def test_apply_gpu_config_rejects_concurrent_applies(
        self, mock_config_service_class: MagicMock, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that concurrent apply operations are rejected with 409."""
        from backend.api.routes import gpu_config
        from backend.services.gpu_config_service import ApplyResult, RestartStatus

        # Set apply state to in-progress using the fallback state
        # Note: The endpoint now uses Redis when available, but falls back to
        # _apply_state_fallback for in-memory tracking without Redis (NEM-3547)
        gpu_config._apply_state_fallback["in_progress"] = True
        gpu_config._apply_state_fallback["operation_id"] = "test-operation-id"

        # Mock the config service to return an incomplete operation
        mock_service = AsyncMock()
        mock_config_service_class.return_value = mock_service
        mock_service.get_operation_status.return_value = ApplyResult(
            success=False,
            operation_id="test-operation-id",
            started_at=datetime.now(UTC),
            changed_services=["ai-llm"],
            service_statuses={"ai-llm": MagicMock(status=RestartStatus.PENDING)},
            completed_at=None,  # Operation not completed - still in progress
        )

        response = client.post("/api/system/gpu-config/apply")

        # Clean up state for other tests
        gpu_config._apply_state_fallback["in_progress"] = False
        gpu_config._apply_state_fallback["operation_id"] = None

        assert response.status_code == 409
        assert "already in progress" in response.json()["detail"]


# =============================================================================
# GET /api/system/gpu-config/status Tests
# =============================================================================


class TestGetGpuConfigStatus:
    """Tests for GET /api/system/gpu-config/status endpoint."""

    def test_get_gpu_config_status_returns_status_correctly(self, client: TestClient) -> None:
        """Test that status endpoint returns current apply status."""
        from backend.api.routes import gpu_config

        # Set up status using the fallback state
        # Note: The endpoint now uses Redis when available, but falls back to
        # _apply_state_fallback for in-memory tracking without Redis (NEM-3547)
        gpu_config._apply_state_fallback = {
            "in_progress": True,
            "operation_id": None,  # No Redis operation, so this uses fallback state
            "services_pending": ["ai-llm", "ai-yolo26"],
            "services_completed": ["ai-enrichment"],
            "service_statuses": [
                ServiceStatus(service="ai-llm", status="starting", message=None),
                ServiceStatus(service="ai-yolo26", status="pending", message=None),
                ServiceStatus(service="ai-enrichment", status="running", message=None),
            ],
            "last_updated": datetime.now(UTC),
        }

        response = client.get("/api/system/gpu-config/status")

        # Clean up state for other tests
        gpu_config._apply_state_fallback = {
            "in_progress": False,
            "operation_id": None,
            "services_pending": [],
            "services_completed": [],
            "service_statuses": [],
            "last_updated": None,
        }

        assert response.status_code == 200
        data = response.json()
        assert data["in_progress"] is True
        assert len(data["services_pending"]) == 2
        assert len(data["services_completed"]) == 1
        assert len(data["service_statuses"]) == 3
        assert data["services_pending"][0] == "ai-llm"
        assert data["services_completed"][0] == "ai-enrichment"

    def test_get_gpu_config_status_when_not_in_progress(self, client: TestClient) -> None:
        """Test status when no apply operation is running."""
        response = client.get("/api/system/gpu-config/status")

        assert response.status_code == 200
        data = response.json()
        assert data["in_progress"] is False
        assert data["services_pending"] == []
        assert data["services_completed"] == []


# =============================================================================
# POST /api/system/gpu-config/detect Tests
# =============================================================================


class TestDetectGpus:
    """Tests for POST /api/system/gpu-config/detect endpoint."""

    @patch("backend.api.routes.gpu_config.get_gpu_detection_service")
    def test_detect_gpus_triggers_gpu_rescan(
        self,
        mock_get_service: MagicMock,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_gpus: list[GpuDeviceDataclass],
    ) -> None:
        """Test that detect endpoint triggers GPU re-scan."""
        mock_service = AsyncMock()
        mock_service.detect_gpus = AsyncMock(return_value=sample_gpus)
        mock_get_service.return_value = mock_service

        # Mock existing devices query
        mock_existing_devices_result = MagicMock()
        mock_existing_devices_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_existing_devices_result

        response = client.post("/api/system/gpu-config/detect")

        assert response.status_code == 200
        data = response.json()
        assert "gpus" in data
        assert len(data["gpus"]) == 2
        # Verify detection service was called
        mock_service.detect_gpus.assert_called_once()

    @patch("backend.api.routes.gpu_config.get_gpu_detection_service")
    def test_detect_gpus_updates_database(
        self,
        mock_get_service: MagicMock,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_gpus: list[GpuDeviceDataclass],
    ) -> None:
        """Test that detect endpoint updates database with detected GPUs."""
        mock_service = AsyncMock()
        mock_service.detect_gpus = AsyncMock(return_value=sample_gpus)
        mock_get_service.return_value = mock_service

        mock_existing_devices_result = MagicMock()
        mock_existing_devices_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_existing_devices_result

        response = client.post("/api/system/gpu-config/detect")

        assert response.status_code == 200
        # Verify database commit was called
        mock_db_session.commit.assert_called_once()

    @patch("backend.api.routes.gpu_config.get_gpu_detection_service")
    def test_detect_gpus_handles_detection_failures(
        self, mock_get_service: MagicMock, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that detection failures are handled with 500 and rollback."""
        mock_service = AsyncMock()
        mock_service.detect_gpus = AsyncMock(side_effect=Exception("NVML initialization failed"))
        mock_get_service.return_value = mock_service

        response = client.post("/api/system/gpu-config/detect")

        assert response.status_code == 500
        assert "GPU detection failed" in response.json()["detail"]
        mock_db_session.rollback.assert_called_once()


# =============================================================================
# GET /api/system/gpu-config/preview Tests
# =============================================================================


class TestPreviewGpuConfig:
    """Tests for GET /api/system/gpu-config/preview endpoint."""

    @patch("backend.api.routes.gpu_config.get_gpu_detection_service")
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
        assert len(data["proposed_assignments"]) >= 3  # At least 3 AI services

    @patch("backend.api.routes.gpu_config.get_gpu_detection_service")
    def test_preview_gpu_config_validates_strategy_parameter(
        self, mock_get_service: MagicMock, client: TestClient
    ) -> None:
        """Test that invalid strategy parameter is rejected."""
        # Missing required strategy parameter
        response = client.get("/api/system/gpu-config/preview")

        assert response.status_code == 422  # Validation error
        assert "Field required" in response.text or "required" in response.text.lower()

    @patch("backend.api.routes.gpu_config.get_gpu_detection_service")
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
            assert len(data["proposed_assignments"]) >= 3

    @patch("backend.api.routes.gpu_config.get_gpu_detection_service")
    def test_preview_gpu_config_returns_warnings_when_appropriate(
        self, mock_get_service: MagicMock, client: TestClient
    ) -> None:
        """Test that preview returns warnings when strategy constraints aren't met."""
        # Single GPU scenario - isolation_first should warn
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

    @patch("backend.api.routes.gpu_config.get_gpu_detection_service")
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


# =============================================================================
# Schema Validation Tests
# =============================================================================


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

        # With override
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

    def test_service_status_schema(self):
        """Test ServiceStatus schema."""
        status = ServiceStatus(
            service="ai-llm",
            status="running",
            message="Configuration applied",
        )

        data = status.model_dump()
        assert data["service"] == "ai-llm"
        assert data["status"] == "running"
        assert data["message"] == "Configuration applied"

    def test_gpu_assignment_strategy_enum_values(self):
        """Test GpuAssignmentStrategy enum has all expected values."""
        assert GpuAssignmentStrategy.MANUAL.value == "manual"
        assert GpuAssignmentStrategy.VRAM_BASED.value == "vram_based"
        assert GpuAssignmentStrategy.LATENCY_OPTIMIZED.value == "latency_optimized"
        assert GpuAssignmentStrategy.ISOLATION_FIRST.value == "isolation_first"
        assert GpuAssignmentStrategy.BALANCED.value == "balanced"
