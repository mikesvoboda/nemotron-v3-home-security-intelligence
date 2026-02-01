"""Unit tests for Model Management API routes.

TDD RED phase tests for backend/api/routes/model_management.py endpoints.
These tests define expected behavior for Model Zoo Management API endpoints
before implementation.

Related Issues:
    - NEM-4780: Model Zoo Management Epic
    - NEM-4782: Backend API endpoint unit tests (TDD RED phase)

Design Document:
    See docs/plans/2025-01-31-model-zoo-management-design.md

Endpoints Tested:
    - GET  /api/system/models           - List all models with runtime state
    - GET  /api/system/models/{name}/status - Get detailed model status
    - POST /api/system/models/{name}/load   - Load a model
    - POST /api/system/models/{name}/unload - Unload a model
    - POST /api/system/models/{name}/reload - Reload a model (unload + load)
    - POST /api/system/models/unload-all    - Unload all models
    - GET  /api/system/models/vram-summary  - Get VRAM usage summary
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.schemas.model_management import (
    LoadModelResponse,
    ModelDetailResponse,
    ModelListResponse,
    UnloadAllResponse,
    UnloadModelResponse,
    VramSummaryResponse,
)
from backend.services.model_zoo import ModelConfig

# =============================================================================
# Test Constants
# =============================================================================

# Heavy models assigned to GPU 0 (ai-enrichment service)
HEAVY_MODELS = frozenset(
    {
        "vehicle-segment-classification",
        "fashion-clip",
        "xclip-base",
        "segformer-b2-clothes",
        "yolo-world-s",
        "vitpose-small",
        "vehicle-damage-detection",
        "violence-detection",
    }
)

# Light models assigned to GPU 1 (ai-enrichment-light service)
LIGHT_MODELS = frozenset(
    {
        "threat-detection-yolov8n",
        "osnet-x0-25",
        "depth-anything-v2-small",
        "pet-classifier",
        "vit-age-classifier",
        "vit-gender-classifier",
        "yolov8n-pose",
        "weather-classification",
        "brisque-quality",
    }
)

ENRICHMENT_URL = "http://ai-enrichment:8094"
ENRICHMENT_LIGHT_URL = "http://ai-enrichment-light:8096"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_enrichment_client() -> AsyncMock:
    """Create a mock enrichment HTTP client."""
    client = AsyncMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    return client


@pytest.fixture
def sample_model_configs() -> dict[str, ModelConfig]:
    """Create sample model configs from the model zoo."""
    return {
        "threat-detection-yolov8n": ModelConfig(
            name="threat-detection-yolov8n",
            path="/models/model-zoo/threat-detection-yolov8n",
            category="detection",
            vram_mb=300,
            load_fn=AsyncMock(),
            enabled=True,
            available=False,
        ),
        "vehicle-segment-classification": ModelConfig(
            name="vehicle-segment-classification",
            path="/models/model-zoo/vehicle-segment-classification",
            category="classification",
            vram_mb=1500,
            load_fn=AsyncMock(),
            enabled=True,
            available=False,
        ),
        "osnet-x0-25": ModelConfig(
            name="osnet-x0-25",
            path="/models/model-zoo/osnet-x0-25",
            category="embedding",
            vram_mb=100,
            load_fn=AsyncMock(),
            enabled=True,
            available=False,
        ),
        "fashion-clip": ModelConfig(
            name="fashion-clip",
            path="/models/model-zoo/fashion-siglip",
            category="classification",
            vram_mb=500,
            load_fn=AsyncMock(),
            enabled=True,
            available=False,
        ),
        "florence-2-large": ModelConfig(
            name="florence-2-large",
            path="/models/model-zoo/florence-2-large",
            category="vision-language",
            vram_mb=1200,
            load_fn=AsyncMock(),
            enabled=False,  # Disabled model
            available=False,
        ),
    }


@pytest.fixture
def sample_enrichment_status_response() -> dict:
    """Mock response from enrichment service /models/status endpoint."""
    return {
        "loaded_models": ["threat-detection-yolov8n", "osnet-x0-25"],
        "total_vram_mb": 400,
        "models": {
            "threat-detection-yolov8n": {
                "vram_mb": 287,
                "last_used": "2025-01-31T10:30:00Z",
                "load_count": 5,
            },
            "osnet-x0-25": {
                "vram_mb": 95,
                "last_used": "2025-01-31T10:25:00Z",
                "load_count": 3,
            },
        },
    }


@pytest.fixture
def sample_heavy_enrichment_status_response() -> dict:
    """Mock response from heavy enrichment service /models/status endpoint."""
    return {
        "loaded_models": ["fashion-clip", "vehicle-segment-classification"],
        "total_vram_mb": 2000,
        "models": {
            "fashion-clip": {
                "vram_mb": 480,
                "last_used": "2025-01-31T10:20:00Z",
                "load_count": 2,
            },
            "vehicle-segment-classification": {
                "vram_mb": 1450,
                "last_used": "2025-01-31T10:15:00Z",
                "load_count": 1,
            },
        },
    }


@pytest.fixture
def mock_http_response() -> MagicMock:
    """Create a mock HTTP response."""
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status = MagicMock()
    return response


# =============================================================================
# GET /api/system/models Tests
# =============================================================================


class TestListModels:
    """Tests for GET /api/system/models endpoint."""

    @patch("backend.api.routes.model_management.get_model_zoo")
    @patch("backend.api.routes.model_management.get_http_client")
    async def test_list_models_returns_registry_with_runtime_state(
        self,
        mock_get_http_client: MagicMock,
        mock_get_model_zoo: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
        sample_enrichment_status_response: dict,
        sample_heavy_enrichment_status_response: dict,
        mock_enrichment_client: AsyncMock,
    ) -> None:
        """List models should return registry models merged with runtime state."""
        # Setup mocks
        mock_get_model_zoo.return_value = sample_model_configs

        # Mock light enrichment service response
        light_response = MagicMock()
        light_response.status_code = 200
        light_response.json.return_value = sample_enrichment_status_response

        # Mock heavy enrichment service response
        heavy_response = MagicMock()
        heavy_response.status_code = 200
        heavy_response.json.return_value = sample_heavy_enrichment_status_response

        async def mock_get(url: str, **kwargs):
            if "ai-enrichment-light" in url:
                return light_response
            return heavy_response

        mock_enrichment_client.get = mock_get
        mock_get_http_client.return_value = mock_enrichment_client

        # Import and call the route (will fail until implemented)
        from backend.api.routes.model_management import list_models

        response = await list_models(http_client=mock_enrichment_client)

        # Validate response
        assert isinstance(response, ModelListResponse)
        assert len(response.models) == 5  # All models from registry

        # Find loaded model and verify runtime state
        threat_model = next(m for m in response.models if m.name == "threat-detection-yolov8n")
        assert threat_model.runtime.loaded is True
        assert threat_model.runtime.actual_vram_mb == 287
        assert threat_model.runtime.load_count == 5

        # Find unloaded model and verify runtime state
        florence_model = next(m for m in response.models if m.name == "florence-2-large")
        assert florence_model.runtime.loaded is False
        assert florence_model.runtime.actual_vram_mb is None

        # Verify service status
        assert response.service_status["ai-enrichment"] == "healthy"
        assert response.service_status["ai-enrichment-light"] == "healthy"

    @patch("backend.api.routes.model_management.get_model_zoo")
    @patch("backend.api.routes.model_management.get_http_client")
    async def test_list_models_handles_enrichment_service_down(
        self,
        mock_get_http_client: MagicMock,
        mock_get_model_zoo: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
        mock_enrichment_client: AsyncMock,
    ) -> None:
        """List models should handle enrichment service being down gracefully."""
        mock_get_model_zoo.return_value = sample_model_configs

        # Simulate both services being down
        import httpx

        mock_enrichment_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_get_http_client.return_value = mock_enrichment_client

        from backend.api.routes.model_management import list_models

        response = await list_models(http_client=mock_enrichment_client)

        # Should still return models from registry
        assert isinstance(response, ModelListResponse)
        assert len(response.models) == 5

        # All models should show as not loaded when service is down
        for model in response.models:
            assert model.runtime.loaded is False
            assert model.runtime.actual_vram_mb is None

        # Service status should reflect unhealthy state
        assert response.service_status["ai-enrichment"] == "unhealthy"
        assert response.service_status["ai-enrichment-light"] == "unhealthy"


# =============================================================================
# GET /api/system/models/{name}/status Tests
# =============================================================================


class TestGetModelStatus:
    """Tests for GET /api/system/models/{name}/status endpoint."""

    @patch("backend.api.routes.model_management.get_model_config")
    @patch("backend.api.routes.model_management.get_http_client")
    async def test_get_model_status_returns_detailed_info(
        self,
        mock_get_http_client: MagicMock,
        mock_get_model_config: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
        sample_enrichment_status_response: dict,
        mock_enrichment_client: AsyncMock,
    ) -> None:
        """Get model status should return detailed model information."""
        model_name = "threat-detection-yolov8n"
        mock_get_model_config.return_value = sample_model_configs[model_name]

        # Mock enrichment response
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = sample_enrichment_status_response
        mock_enrichment_client.get = AsyncMock(return_value=response)
        mock_get_http_client.return_value = mock_enrichment_client

        from backend.api.routes.model_management import get_model_status

        result = await get_model_status(
            model_name=model_name,
            http_client=mock_enrichment_client,
        )

        assert isinstance(result, ModelDetailResponse)
        assert result.name == model_name
        assert result.category == "detection"
        assert result.path == "/models/model-zoo/threat-detection-yolov8n"
        assert result.estimated_vram_mb == 300
        assert result.enabled is True
        assert result.service == "ai-enrichment-light"
        assert result.gpu_id == 1
        assert result.runtime.loaded is True
        assert result.runtime.actual_vram_mb == 287

    @patch("backend.api.routes.model_management.get_model_config")
    async def test_get_model_status_unknown_model_returns_404(
        self,
        mock_get_model_config: MagicMock,
    ) -> None:
        """Get model status should return 404 for unknown models."""
        mock_get_model_config.return_value = None

        from fastapi import HTTPException

        from backend.api.routes.model_management import get_model_status

        with pytest.raises(HTTPException) as exc_info:
            await get_model_status(
                model_name="nonexistent-model",
                http_client=AsyncMock(),
            )

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()


# =============================================================================
# POST /api/system/models/{name}/load Tests
# =============================================================================


class TestLoadModel:
    """Tests for POST /api/system/models/{name}/load endpoint."""

    @patch("backend.api.routes.model_management.get_model_config")
    @patch("backend.api.routes.model_management.get_http_client")
    async def test_load_model_proxies_to_correct_service(
        self,
        mock_get_http_client: MagicMock,
        mock_get_model_config: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
        mock_enrichment_client: AsyncMock,
    ) -> None:
        """Load model should proxy request to the correct enrichment service."""
        model_name = "threat-detection-yolov8n"
        mock_get_model_config.return_value = sample_model_configs[model_name]

        # Mock successful load response
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "success": True,
            "model_name": model_name,
            "load_time_ms": 1250.0,
            "vram_mb": 287,
        }
        mock_enrichment_client.post = AsyncMock(return_value=response)
        mock_get_http_client.return_value = mock_enrichment_client

        from backend.api.routes.model_management import load_model

        result = await load_model(
            model_name=model_name,
            http_client=mock_enrichment_client,
        )

        assert isinstance(result, LoadModelResponse)
        assert result.success is True
        assert result.model_name == model_name
        assert result.load_time_ms == 1250.0
        assert result.vram_mb == 287

        # Verify correct service was called (light service for this model)
        mock_enrichment_client.post.assert_called_once()
        call_url = mock_enrichment_client.post.call_args[0][0]
        assert "ai-enrichment-light" in call_url

    @patch("backend.api.routes.model_management.get_model_config")
    @patch("backend.api.routes.model_management.get_http_client")
    async def test_load_model_heavy_routes_to_gpu0(
        self,
        mock_get_http_client: MagicMock,
        mock_get_model_config: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
        mock_enrichment_client: AsyncMock,
    ) -> None:
        """Heavy models should be loaded via ai-enrichment service (GPU 0)."""
        model_name = "vehicle-segment-classification"
        mock_get_model_config.return_value = sample_model_configs[model_name]

        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "success": True,
            "model_name": model_name,
            "load_time_ms": 2500.0,
            "vram_mb": 1450,
        }
        mock_enrichment_client.post = AsyncMock(return_value=response)
        mock_get_http_client.return_value = mock_enrichment_client

        from backend.api.routes.model_management import load_model

        result = await load_model(
            model_name=model_name,
            http_client=mock_enrichment_client,
        )

        assert result.success is True
        assert result.gpu_id == 0
        assert result.service == "ai-enrichment"

        # Verify heavy enrichment service was called
        call_url = mock_enrichment_client.post.call_args[0][0]
        assert "ai-enrichment:8094" in call_url or "ai-enrichment" in call_url
        assert "ai-enrichment-light" not in call_url

    @patch("backend.api.routes.model_management.get_model_config")
    @patch("backend.api.routes.model_management.get_http_client")
    async def test_load_model_light_routes_to_gpu1(
        self,
        mock_get_http_client: MagicMock,
        mock_get_model_config: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
        mock_enrichment_client: AsyncMock,
    ) -> None:
        """Light models should be loaded via ai-enrichment-light service (GPU 1)."""
        model_name = "osnet-x0-25"
        mock_get_model_config.return_value = sample_model_configs[model_name]

        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "success": True,
            "model_name": model_name,
            "load_time_ms": 500.0,
            "vram_mb": 95,
        }
        mock_enrichment_client.post = AsyncMock(return_value=response)
        mock_get_http_client.return_value = mock_enrichment_client

        from backend.api.routes.model_management import load_model

        result = await load_model(
            model_name=model_name,
            http_client=mock_enrichment_client,
        )

        assert result.success is True
        assert result.gpu_id == 1
        assert result.service == "ai-enrichment-light"

        # Verify light enrichment service was called
        call_url = mock_enrichment_client.post.call_args[0][0]
        assert "ai-enrichment-light" in call_url


# =============================================================================
# POST /api/system/models/{name}/unload Tests
# =============================================================================


class TestUnloadModel:
    """Tests for POST /api/system/models/{name}/unload endpoint."""

    @patch("backend.api.routes.model_management.get_model_config")
    @patch("backend.api.routes.model_management.get_http_client")
    async def test_unload_model_proxies_to_correct_service(
        self,
        mock_get_http_client: MagicMock,
        mock_get_model_config: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
        mock_enrichment_client: AsyncMock,
    ) -> None:
        """Unload model should proxy request to the correct enrichment service."""
        model_name = "threat-detection-yolov8n"
        mock_get_model_config.return_value = sample_model_configs[model_name]

        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "success": True,
            "model_name": model_name,
            "freed_vram_mb": 287,
        }
        mock_enrichment_client.post = AsyncMock(return_value=response)
        mock_get_http_client.return_value = mock_enrichment_client

        from backend.api.routes.model_management import unload_model

        result = await unload_model(
            model_name=model_name,
            http_client=mock_enrichment_client,
        )

        assert isinstance(result, UnloadModelResponse)
        assert result.success is True
        assert result.model_name == model_name
        assert result.freed_vram_mb == 287

        # Verify correct service was called
        mock_enrichment_client.post.assert_called_once()
        call_url = mock_enrichment_client.post.call_args[0][0]
        assert "ai-enrichment-light" in call_url
        assert "unload" in call_url


# =============================================================================
# POST /api/system/models/{name}/reload Tests
# =============================================================================


class TestReloadModel:
    """Tests for POST /api/system/models/{name}/reload endpoint."""

    @patch("backend.api.routes.model_management.get_model_config")
    @patch("backend.api.routes.model_management.get_http_client")
    async def test_reload_model_unloads_then_loads(
        self,
        mock_get_http_client: MagicMock,
        mock_get_model_config: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
        mock_enrichment_client: AsyncMock,
    ) -> None:
        """Reload model should call unload then load sequentially."""
        model_name = "threat-detection-yolov8n"
        mock_get_model_config.return_value = sample_model_configs[model_name]

        unload_response = MagicMock()
        unload_response.status_code = 200
        unload_response.json.return_value = {
            "success": True,
            "model_name": model_name,
            "freed_vram_mb": 287,
        }

        load_response = MagicMock()
        load_response.status_code = 200
        load_response.json.return_value = {
            "success": True,
            "model_name": model_name,
            "load_time_ms": 1300.0,
            "vram_mb": 290,
        }

        call_count = 0

        async def mock_post(url: str, **kwargs):
            nonlocal call_count
            call_count += 1
            if "unload" in url:
                return unload_response
            return load_response

        mock_enrichment_client.post = mock_post
        mock_get_http_client.return_value = mock_enrichment_client

        from backend.api.routes.model_management import reload_model

        result = await reload_model(
            model_name=model_name,
            http_client=mock_enrichment_client,
        )

        # Should return load response
        assert isinstance(result, LoadModelResponse)
        assert result.success is True
        assert result.model_name == model_name

        # Should have called both unload and load
        assert call_count == 2


# =============================================================================
# POST /api/system/models/unload-all Tests
# =============================================================================


class TestUnloadAllModels:
    """Tests for POST /api/system/models/unload-all endpoint."""

    @patch("backend.api.routes.model_management.get_http_client")
    async def test_unload_all_calls_both_services(
        self,
        mock_get_http_client: MagicMock,
        mock_enrichment_client: AsyncMock,
    ) -> None:
        """Unload all should call unload on both enrichment services."""
        heavy_response = MagicMock()
        heavy_response.status_code = 200
        heavy_response.json.return_value = {
            "success": True,
            "unloaded_count": 2,
            "freed_vram_mb": 2000,
        }

        light_response = MagicMock()
        light_response.status_code = 200
        light_response.json.return_value = {
            "success": True,
            "unloaded_count": 2,
            "freed_vram_mb": 400,
        }

        services_called = []

        async def mock_post(url: str, **kwargs):
            if "ai-enrichment-light" in url:
                services_called.append("ai-enrichment-light")
                return light_response
            services_called.append("ai-enrichment")
            return heavy_response

        mock_enrichment_client.post = mock_post
        mock_get_http_client.return_value = mock_enrichment_client

        from backend.api.routes.model_management import unload_all_models

        result = await unload_all_models(http_client=mock_enrichment_client)

        assert isinstance(result, UnloadAllResponse)
        assert result.success is True
        assert result.unloaded_count == 4  # 2 + 2
        assert result.freed_vram_mb == 2400  # 2000 + 400
        assert result.services["ai-enrichment"] == 2
        assert result.services["ai-enrichment-light"] == 2

        # Both services should have been called
        assert "ai-enrichment" in services_called
        assert "ai-enrichment-light" in services_called


# =============================================================================
# GET /api/system/models/vram-summary Tests
# =============================================================================


class TestVramSummary:
    """Tests for GET /api/system/models/vram-summary endpoint."""

    @patch("backend.api.routes.model_management.get_http_client")
    async def test_vram_summary_aggregates_both_gpus(
        self,
        mock_get_http_client: MagicMock,
        mock_enrichment_client: AsyncMock,
    ) -> None:
        """VRAM summary should aggregate data from both enrichment services."""
        # Mock heavy enrichment service response
        heavy_response = MagicMock()
        heavy_response.status_code = 200
        heavy_response.json.return_value = {
            "budget_mb": 6800,
            "used_mb": 2000,
            "loaded_models": ["fashion-clip", "vehicle-segment-classification"],
        }

        # Mock light enrichment service response
        light_response = MagicMock()
        light_response.status_code = 200
        light_response.json.return_value = {
            "budget_mb": 1200,
            "used_mb": 400,
            "loaded_models": ["threat-detection-yolov8n", "osnet-x0-25"],
        }

        async def mock_get(url: str, **kwargs):
            if "ai-enrichment-light" in url:
                return light_response
            return heavy_response

        mock_enrichment_client.get = mock_get
        mock_get_http_client.return_value = mock_enrichment_client

        from backend.api.routes.model_management import get_vram_summary

        result = await get_vram_summary(http_client=mock_enrichment_client)

        assert isinstance(result, VramSummaryResponse)

        # Verify per-GPU info
        assert len(result.gpus) == 2

        gpu0 = next(g for g in result.gpus if g.gpu_id == 0)
        assert gpu0.service == "ai-enrichment"
        assert gpu0.budget_mb == 6800
        assert gpu0.used_mb == 2000
        assert gpu0.available_mb == 4800
        assert len(gpu0.loaded_models) == 2

        gpu1 = next(g for g in result.gpus if g.gpu_id == 1)
        assert gpu1.service == "ai-enrichment-light"
        assert gpu1.budget_mb == 1200
        assert gpu1.used_mb == 400
        assert gpu1.available_mb == 800
        assert len(gpu1.loaded_models) == 2

        # Verify totals
        assert result.totals.budget_mb == 8000
        assert result.totals.used_mb == 2400
        assert result.totals.available_mb == 5600
        assert result.totals.model_count == 4


# =============================================================================
# Service Routing Tests
# =============================================================================


class TestServiceRouting:
    """Tests for model-to-service routing logic."""

    def test_heavy_model_routes_to_enrichment(self) -> None:
        """Heavy models should route to ai-enrichment service."""
        from backend.api.routes.model_management import get_service_for_model

        for model_name in HEAVY_MODELS:
            service = get_service_for_model(model_name)
            assert service == ENRICHMENT_URL, f"{model_name} should route to ai-enrichment"

    def test_light_model_routes_to_enrichment_light(self) -> None:
        """Light models should route to ai-enrichment-light service."""
        from backend.api.routes.model_management import get_service_for_model

        for model_name in LIGHT_MODELS:
            service = get_service_for_model(model_name)
            assert service == ENRICHMENT_LIGHT_URL, (
                f"{model_name} should route to ai-enrichment-light"
            )

    def test_get_gpu_id_for_model(self) -> None:
        """Models should be assigned to correct GPU based on service routing."""
        from backend.api.routes.model_management import get_gpu_id_for_model

        # Heavy models -> GPU 0
        for model_name in HEAVY_MODELS:
            gpu_id = get_gpu_id_for_model(model_name)
            assert gpu_id == 0, f"{model_name} should be on GPU 0"

        # Light models -> GPU 1
        for model_name in LIGHT_MODELS:
            gpu_id = get_gpu_id_for_model(model_name)
            assert gpu_id == 1, f"{model_name} should be on GPU 1"


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling in model management routes."""

    @patch("backend.api.routes.model_management.get_model_config")
    async def test_load_disabled_model_returns_400(
        self,
        mock_get_model_config: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
    ) -> None:
        """Loading a disabled model should return 400 error."""
        # Florence is disabled in our sample configs
        model_name = "florence-2-large"
        mock_get_model_config.return_value = sample_model_configs[model_name]

        from fastapi import HTTPException

        from backend.api.routes.model_management import load_model

        with pytest.raises(HTTPException) as exc_info:
            await load_model(
                model_name=model_name,
                http_client=AsyncMock(),
            )

        assert exc_info.value.status_code == 400
        assert "disabled" in exc_info.value.detail.lower()

    @patch("backend.api.routes.model_management.get_model_config")
    @patch("backend.api.routes.model_management.get_http_client")
    async def test_load_model_service_error_returns_502(
        self,
        mock_get_http_client: MagicMock,
        mock_get_model_config: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
        mock_enrichment_client: AsyncMock,
    ) -> None:
        """Service errors during load should return 502 Bad Gateway."""
        model_name = "threat-detection-yolov8n"
        mock_get_model_config.return_value = sample_model_configs[model_name]

        response = MagicMock()
        response.status_code = 500
        response.json.return_value = {"error": "Out of memory"}
        mock_enrichment_client.post = AsyncMock(return_value=response)
        mock_get_http_client.return_value = mock_enrichment_client

        from fastapi import HTTPException

        from backend.api.routes.model_management import load_model

        with pytest.raises(HTTPException) as exc_info:
            await load_model(
                model_name=model_name,
                http_client=mock_enrichment_client,
            )

        assert exc_info.value.status_code == 502

    @patch("backend.api.routes.model_management.get_model_config")
    async def test_unload_unknown_model_returns_404(
        self,
        mock_get_model_config: MagicMock,
    ) -> None:
        """Unloading an unknown model should return 404."""
        mock_get_model_config.return_value = None

        from fastapi import HTTPException

        from backend.api.routes.model_management import unload_model

        with pytest.raises(HTTPException) as exc_info:
            await unload_model(
                model_name="nonexistent-model",
                http_client=AsyncMock(),
            )

        assert exc_info.value.status_code == 404


# =============================================================================
# FastAPI TestClient Integration Tests
# =============================================================================


class TestModelManagementRouterIntegration:
    """Integration tests using FastAPI TestClient.

    These tests verify the router is correctly wired and endpoints
    respond with expected HTTP status codes and response formats.
    """

    @pytest.fixture
    def mock_http_client_dependency(self) -> AsyncMock:
        """Create a mock HTTP client for dependency injection."""
        client = AsyncMock()
        # Mock GET to return empty status
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "loaded_models": {},
            "vram_used_mb": 0,
            "vram_budget_mb": 6800,
        }
        client.get = AsyncMock(return_value=response)
        # Mock POST to return success
        post_response = MagicMock()
        post_response.status_code = 200
        post_response.json.return_value = {
            "success": True,
            "unloaded_count": 0,
            "freed_vram_mb": 0,
        }
        client.post = AsyncMock(return_value=post_response)
        return client

    @pytest.fixture
    def app(self, mock_http_client_dependency: AsyncMock) -> FastAPI:
        """Create a FastAPI app with model management router."""
        from backend.api.routes.model_management import get_http_client, router

        app = FastAPI()
        app.include_router(router)

        # Override the dependency to use our mock
        async def mock_get_http_client():
            return mock_http_client_dependency

        app.dependency_overrides[get_http_client] = mock_get_http_client
        return app

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        """Create a test client for the FastAPI app."""
        with TestClient(app) as test_client:
            yield test_client

    def test_list_models_endpoint_exists(self, client: TestClient) -> None:
        """GET /api/system/models endpoint should exist."""
        response = client.get("/api/system/models")
        # Should not be 404
        assert response.status_code != 404

    def test_get_model_status_endpoint_exists(self, client: TestClient) -> None:
        """GET /api/system/models/{name}/status endpoint should exist."""
        response = client.get("/api/system/models/test-model/status")
        # Should be 404 since test-model doesn't exist in registry
        assert response.status_code == 404

    def test_load_model_endpoint_exists(self, client: TestClient) -> None:
        """POST /api/system/models/{name}/load endpoint should exist."""
        response = client.post("/api/system/models/test-model/load")
        assert response.status_code != 405  # Method Not Allowed

    def test_unload_model_endpoint_exists(self, client: TestClient) -> None:
        """POST /api/system/models/{name}/unload endpoint should exist."""
        response = client.post("/api/system/models/test-model/unload")
        assert response.status_code != 405

    def test_reload_model_endpoint_exists(self, client: TestClient) -> None:
        """POST /api/system/models/{name}/reload endpoint should exist."""
        response = client.post("/api/system/models/test-model/reload")
        assert response.status_code != 405

    def test_unload_all_endpoint_exists(self, client: TestClient) -> None:
        """POST /api/system/models/unload-all endpoint should exist."""
        response = client.post("/api/system/models/unload-all")
        assert response.status_code != 405

    def test_vram_summary_endpoint_exists(self, client: TestClient) -> None:
        """GET /api/system/models/vram-summary endpoint should exist."""
        response = client.get("/api/system/models/vram-summary")
        assert response.status_code != 404
