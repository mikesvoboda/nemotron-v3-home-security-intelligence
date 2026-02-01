"""Integration tests for Model Zoo Management API endpoints (NEM-4783).

These tests verify the Model Zoo Management API endpoints work correctly
with mocked enrichment services. The backend acts as an aggregation layer
that combines static model metadata from the registry with runtime state
from enrichment services.

Tests cover:
1. Happy path - list models, load/unload, VRAM summary
2. Error handling - nonexistent model, disabled model, service unavailable

Endpoints tested:
- GET /api/system/models - List all models with registry + runtime state
- GET /api/system/models/{name}/status - Detailed status for specific model
- POST /api/system/models/{name}/load - Load model via enrichment service
- POST /api/system/models/{name}/unload - Unload model via enrichment service
- POST /api/system/models/{name}/reload - Unload + load
- POST /api/system/models/unload-all - Unload all models on both services
- GET /api/system/models/vram-summary - Per-GPU VRAM breakdown

Uses shared fixtures from conftest.py:
- integration_db: Clean PostgreSQL test database
- client: httpx AsyncClient with test app
- mock_redis: Mock Redis client

Note: This is TDD RED phase - tests are expected to FAIL until
the API implementation is complete.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import AsyncClient

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


# =============================================================================
# Mock Enrichment Service Responses
# =============================================================================


def create_enrichment_status_response(
    loaded_models: list[str],
    vram_used_mb: int = 2100,
    vram_budget_mb: int = 6800,
) -> dict:
    """Create a mock response from enrichment service /models/status endpoint.

    Args:
        loaded_models: List of model names that are currently loaded
        vram_used_mb: Total VRAM used in MB
        vram_budget_mb: Total VRAM budget in MB

    Returns:
        Mock response dictionary matching enrichment service format
    """
    return {
        "loaded_models": {
            model: {
                "actual_vram_mb": 500,
                "last_used": "2025-01-31T10:30:00Z",
                "load_count": 5,
            }
            for model in loaded_models
        },
        "vram_used_mb": vram_used_mb,
        "vram_budget_mb": vram_budget_mb,
    }


def create_load_response(
    model_name: str,
    load_time_ms: float = 1250.0,
    vram_mb: int = 500,
) -> dict:
    """Create a mock response from enrichment service /models/preload endpoint.

    Args:
        model_name: Name of the loaded model
        load_time_ms: Time taken to load in milliseconds
        vram_mb: VRAM usage in MB

    Returns:
        Mock response dictionary matching enrichment service format
    """
    return {
        "success": True,
        "model_name": model_name,
        "load_time_ms": load_time_ms,
        "vram_mb": vram_mb,
    }


def create_unload_response(model_name: str, freed_vram_mb: int = 500) -> dict:
    """Create a mock response from enrichment service /models/{name}/unload endpoint.

    Args:
        model_name: Name of the unloaded model
        freed_vram_mb: VRAM freed in MB

    Returns:
        Mock response dictionary matching enrichment service format
    """
    return {
        "success": True,
        "model_name": model_name,
        "freed_vram_mb": freed_vram_mb,
    }


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_enrichment_responses():
    """Fixture providing mock HTTP responses for enrichment services.

    Returns a context manager that patches httpx.AsyncClient to return
    mock responses for enrichment service endpoints.
    """

    async def mock_get(url: str, *args, **kwargs) -> httpx.Response:
        """Mock GET requests to enrichment services."""
        if "/models/status" in url:
            # Heavy enrichment service (GPU 0)
            if "8094" in url or "ai-enrichment:" in url:
                return httpx.Response(
                    200,
                    json=create_enrichment_status_response(
                        loaded_models=["fashion-clip", "vehicle-segment-classification"],
                        vram_used_mb=2100,
                        vram_budget_mb=6800,
                    ),
                )
            # Light enrichment service (GPU 1)
            if "8096" in url or "ai-enrichment-light" in url:
                return httpx.Response(
                    200,
                    json=create_enrichment_status_response(
                        loaded_models=["threat-detection-yolov8n", "osnet-x0-25"],
                        vram_used_mb=450,
                        vram_budget_mb=1200,
                    ),
                )
        raise httpx.HTTPStatusError(
            "Not Found",
            request=httpx.Request("GET", url),
            response=httpx.Response(404),
        )

    async def mock_post(url: str, *args, **kwargs) -> httpx.Response:
        """Mock POST requests to enrichment services."""
        # Preload (load) model
        if "/models/preload" in url:
            model_name = kwargs.get("params", {}).get("model_name", "unknown")
            return httpx.Response(
                200,
                json=create_load_response(model_name),
            )
        # Unload model
        if "/models/" in url and "/unload" in url:
            # Extract model name from URL path
            parts = url.split("/models/")[-1].split("/unload")[0]
            model_name = parts
            return httpx.Response(
                200,
                json=create_unload_response(model_name),
            )
        raise httpx.HTTPStatusError(
            "Not Found",
            request=httpx.Request("POST", url),
            response=httpx.Response(404),
        )

    return {"get": mock_get, "post": mock_post}


# =============================================================================
# Happy Path Tests
# =============================================================================


class TestListModelsIntegration:
    """Integration tests for GET /api/system/models endpoint."""

    @pytest.mark.asyncio
    async def test_list_models_returns_real_enrichment_state(
        self,
        client: AsyncClient,
        mock_enrichment_responses: dict,
    ) -> None:
        """Test that list models aggregates state from both enrichment services.

        Verifies:
        - Response includes models from the registry
        - Runtime state is populated from enrichment services
        - Service status shows both services as healthy
        - Models show correct GPU assignment
        """
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=mock_enrichment_responses["get"])
        mock_http.post = AsyncMock(side_effect=mock_enrichment_responses["post"])

        with patch("backend.api.routes.model_management.get_http_client", return_value=mock_http):
            response = await client.get("/api/system/models")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "models" in data
        assert "service_status" in data

        # Verify models list is populated
        models = data["models"]
        assert len(models) > 0

        # Find a model that should be loaded (from mock responses)
        fashion_clip = next((m for m in models if m["name"] == "fashion-clip"), None)
        assert fashion_clip is not None
        assert fashion_clip["runtime"]["loaded"] is True
        assert fashion_clip["gpu_id"] == 0
        assert fashion_clip["service"] == "ai-enrichment"

        # Find a model from the light service
        threat_model = next((m for m in models if m["name"] == "threat-detection-yolov8n"), None)
        assert threat_model is not None
        assert threat_model["runtime"]["loaded"] is True
        assert threat_model["gpu_id"] == 1
        assert threat_model["service"] == "ai-enrichment-light"

        # Verify service status
        service_status = data["service_status"]
        assert service_status["ai-enrichment"] == "healthy"
        assert service_status["ai-enrichment-light"] == "healthy"

    @pytest.mark.asyncio
    async def test_list_models_includes_unloaded_models(
        self,
        client: AsyncClient,
        mock_enrichment_responses: dict,
    ) -> None:
        """Test that list includes models that are not currently loaded.

        Verifies:
        - Unloaded models have runtime.loaded = False
        - Unloaded models still show estimated VRAM and category
        """
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=mock_enrichment_responses["get"])

        with patch("backend.api.routes.model_management.get_http_client", return_value=mock_http):
            response = await client.get("/api/system/models")

        assert response.status_code == 200
        data = response.json()

        # Find a model that should NOT be loaded (not in mock responses)
        yolo_world = next((m for m in data["models"] if m["name"] == "yolo-world-s"), None)
        if yolo_world:  # Model exists in registry
            assert yolo_world["runtime"]["loaded"] is False
            assert yolo_world["runtime"]["actual_vram_mb"] is None
            assert yolo_world["estimated_vram_mb"] > 0
            assert yolo_world["category"] is not None


class TestLoadModelIntegration:
    """Integration tests for POST /api/system/models/{name}/load endpoint."""

    @pytest.mark.asyncio
    async def test_load_model_actually_loads_in_enrichment(
        self,
        client: AsyncClient,
        mock_enrichment_responses: dict,
    ) -> None:
        """Test that load model proxies to the correct enrichment service.

        Verifies:
        - Request is routed to correct enrichment service based on model
        - Response includes load time and VRAM usage
        - Response includes GPU and service info
        """
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=mock_enrichment_responses["get"])
        mock_http.post = AsyncMock(side_effect=mock_enrichment_responses["post"])

        with patch("backend.api.routes.model_management.get_http_client", return_value=mock_http):
            response = await client.post("/api/system/models/threat-detection-yolov8n/load")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["success"] is True
        assert data["model_name"] == "threat-detection-yolov8n"
        assert data["service"] == "ai-enrichment-light"
        assert data["gpu_id"] == 1
        assert "load_time_ms" in data
        assert "vram_mb" in data

        # Verify the enrichment service was called
        mock_http.post.assert_called()
        call_args = mock_http.post.call_args
        assert "8096" in str(call_args) or "ai-enrichment-light" in str(call_args)


class TestUnloadModelIntegration:
    """Integration tests for POST /api/system/models/{name}/unload endpoint."""

    @pytest.mark.asyncio
    async def test_unload_model_actually_unloads_in_enrichment(
        self,
        client: AsyncClient,
        mock_enrichment_responses: dict,
    ) -> None:
        """Test that unload model proxies to the correct enrichment service.

        Verifies:
        - Request is routed to correct enrichment service
        - Response includes freed VRAM info
        """
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=mock_enrichment_responses["get"])
        mock_http.post = AsyncMock(side_effect=mock_enrichment_responses["post"])

        with patch("backend.api.routes.model_management.get_http_client", return_value=mock_http):
            response = await client.post("/api/system/models/fashion-clip/unload")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["success"] is True
        assert data["model_name"] == "fashion-clip"
        assert "freed_vram_mb" in data

        # Verify the enrichment service was called with unload
        mock_http.post.assert_called()


class TestVRAMSummaryIntegration:
    """Integration tests for GET /api/system/models/vram-summary endpoint."""

    @pytest.mark.asyncio
    async def test_vram_summary_reflects_actual_gpu_usage(
        self,
        client: AsyncClient,
        mock_enrichment_responses: dict,
    ) -> None:
        """Test that VRAM summary returns per-GPU breakdown from enrichment services.

        Verifies:
        - Response includes per-GPU VRAM info
        - Each GPU shows service, budget, used, available
        - Totals are correctly calculated
        """
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=mock_enrichment_responses["get"])

        with patch("backend.api.routes.model_management.get_http_client", return_value=mock_http):
            response = await client.get("/api/system/models/vram-summary")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "gpus" in data
        assert "totals" in data

        gpus = data["gpus"]
        assert len(gpus) == 2  # Heavy and light services

        # Verify GPU 0 (heavy service)
        gpu0 = next((g for g in gpus if g["gpu_id"] == 0), None)
        assert gpu0 is not None
        assert gpu0["service"] == "ai-enrichment"
        assert gpu0["budget_mb"] == 6800
        assert gpu0["used_mb"] == 2100
        assert gpu0["available_mb"] == 4700
        assert "utilization_percent" in gpu0
        assert "loaded_models" in gpu0
        assert "fashion-clip" in gpu0["loaded_models"]

        # Verify GPU 1 (light service)
        gpu1 = next((g for g in gpus if g["gpu_id"] == 1), None)
        assert gpu1 is not None
        assert gpu1["service"] == "ai-enrichment-light"
        assert gpu1["budget_mb"] == 1200
        assert gpu1["used_mb"] == 450
        assert "threat-detection-yolov8n" in gpu1["loaded_models"]

        # Verify totals
        totals = data["totals"]
        assert totals["budget_mb"] == 8000  # 6800 + 1200
        assert totals["used_mb"] == 2550  # 2100 + 450
        assert totals["available_mb"] == 5450  # 8000 - 2550
        assert totals["model_count"] == 4  # 2 from each service


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestModelNotFoundErrors:
    """Integration tests for model not found error handling."""

    @pytest.mark.asyncio
    async def test_load_nonexistent_model_returns_error(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that loading a nonexistent model returns 404.

        Verifies:
        - Response status is 404
        - Error message indicates model not found
        """
        response = await client.post("/api/system/models/nonexistent-model-xyz/load")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower() or "nonexistent" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_unload_nonexistent_model_returns_error(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that unloading a nonexistent model returns 404.

        Verifies:
        - Response status is 404
        - Error message indicates model not found
        """
        response = await client.post("/api/system/models/nonexistent-model-xyz/unload")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower() or "nonexistent" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_status_nonexistent_model_returns_error(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that getting status for nonexistent model returns 404.

        Verifies:
        - Response status is 404
        - Error message indicates model not found
        """
        response = await client.get("/api/system/models/nonexistent-model-xyz/status")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data


class TestDisabledModelErrors:
    """Integration tests for disabled model error handling."""

    @pytest.mark.asyncio
    async def test_load_disabled_model_returns_error(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that loading a disabled model returns 400.

        The model 'yolo26-general' is disabled in the registry.

        Verifies:
        - Response status is 400
        - Error message indicates model is disabled
        """
        # yolo26-general is disabled in the model zoo registry
        response = await client.post("/api/system/models/yolo26-general/load")

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "disabled" in data["detail"].lower()


class TestServiceUnavailableErrors:
    """Integration tests for enrichment service unavailable handling."""

    @pytest.mark.asyncio
    async def test_graceful_degradation_when_enrichment_down(
        self,
        client: AsyncClient,
    ) -> None:
        """Test graceful degradation when enrichment services are unavailable.

        Verifies:
        - List models still returns static registry data
        - Service status shows services as unhealthy
        - Runtime state shows services as unavailable
        """

        async def mock_get_fail(url: str, *args, **kwargs) -> httpx.Response:
            """Mock GET that simulates service unavailable."""
            raise httpx.ConnectError("Connection refused")

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=mock_get_fail)

        with patch("backend.api.routes.model_management.get_http_client", return_value=mock_http):
            response = await client.get("/api/system/models")

        # Should still return 200 with degraded data
        assert response.status_code == 200
        data = response.json()

        # Verify response structure is maintained
        assert "models" in data
        assert "service_status" in data

        # Models should still be present (from registry)
        models = data["models"]
        assert len(models) > 0

        # Service status should show unhealthy
        service_status = data["service_status"]
        assert service_status["ai-enrichment"] in ("unhealthy", "unavailable")
        assert service_status["ai-enrichment-light"] in ("unhealthy", "unavailable")

        # Runtime state should be empty/unavailable for all models
        for model in models:
            assert model["runtime"]["loaded"] is False
            assert model["runtime"]["actual_vram_mb"] is None

    @pytest.mark.asyncio
    async def test_load_model_when_enrichment_down_returns_503(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that load returns 503 when enrichment service is unavailable.

        Verifies:
        - Response status is 503
        - Error message indicates service unavailable
        """

        async def mock_post_fail(url: str, *args, **kwargs) -> httpx.Response:
            """Mock POST that simulates service unavailable."""
            raise httpx.ConnectError("Connection refused")

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=mock_post_fail)

        with patch("backend.api.routes.model_management.get_http_client", return_value=mock_http):
            response = await client.post("/api/system/models/threat-detection-yolov8n/load")

        assert response.status_code == 503
        data = response.json()
        assert "detail" in data
        assert "unavailable" in data["detail"].lower() or "enrichment" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_vram_summary_with_partial_service_failure(
        self,
        client: AsyncClient,
        mock_enrichment_responses: dict,
    ) -> None:
        """Test VRAM summary handles partial service failure gracefully.

        When one enrichment service is down but the other is up:
        - Should still return data for the healthy service
        - Should indicate the unhealthy service status
        """

        async def mock_get_partial(url: str, *args, **kwargs) -> httpx.Response:
            """Mock GET where only light service responds."""
            # Heavy service fails
            if "8094" in url or ("ai-enrichment:" in url and "light" not in url):
                raise httpx.ConnectError("Connection refused")
            # Light service responds
            if "8096" in url or "ai-enrichment-light" in url:
                return httpx.Response(
                    200,
                    json=create_enrichment_status_response(
                        loaded_models=["threat-detection-yolov8n"],
                        vram_used_mb=300,
                        vram_budget_mb=1200,
                    ),
                )
            raise httpx.ConnectError("Unknown URL")

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=mock_get_partial)

        with patch("backend.api.routes.model_management.get_http_client", return_value=mock_http):
            response = await client.get("/api/system/models/vram-summary")

        assert response.status_code == 200
        data = response.json()

        # Should have data for at least the working service
        assert "gpus" in data
        gpus = data["gpus"]

        # Light service (GPU 1) should have data
        gpu1 = next((g for g in gpus if g["gpu_id"] == 1), None)
        assert gpu1 is not None
        assert gpu1["used_mb"] == 300


# =============================================================================
# Additional Endpoint Tests
# =============================================================================


class TestModelStatusEndpoint:
    """Integration tests for GET /api/system/models/{name}/status endpoint."""

    @pytest.mark.asyncio
    async def test_get_model_status_returns_detailed_info(
        self,
        client: AsyncClient,
        mock_enrichment_responses: dict,
    ) -> None:
        """Test that model status endpoint returns detailed model info.

        Verifies:
        - Response includes all model fields
        - Runtime state is populated from enrichment service
        """
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=mock_enrichment_responses["get"])

        with patch("backend.api.routes.model_management.get_http_client", return_value=mock_http):
            response = await client.get("/api/system/models/fashion-clip/status")

        assert response.status_code == 200
        data = response.json()

        # Verify all expected fields are present
        assert data["name"] == "fashion-clip"
        assert "category" in data
        assert "estimated_vram_mb" in data
        assert "enabled" in data
        assert "service" in data
        assert "gpu_id" in data
        assert "runtime" in data

        # Verify runtime state
        runtime = data["runtime"]
        assert runtime["loaded"] is True
        assert "actual_vram_mb" in runtime
        assert "last_used" in runtime
        assert "load_count" in runtime


class TestReloadModelEndpoint:
    """Integration tests for POST /api/system/models/{name}/reload endpoint."""

    @pytest.mark.asyncio
    async def test_reload_model_unloads_and_loads(
        self,
        client: AsyncClient,
        mock_enrichment_responses: dict,
    ) -> None:
        """Test that reload performs unload then load.

        Verifies:
        - Both unload and load are called
        - Response indicates success with load info
        """
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=mock_enrichment_responses["get"])
        mock_http.post = AsyncMock(side_effect=mock_enrichment_responses["post"])

        with patch("backend.api.routes.model_management.get_http_client", return_value=mock_http):
            response = await client.post("/api/system/models/fashion-clip/reload")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["model_name"] == "fashion-clip"

        # Verify both calls were made (unload then load)
        # Note: The exact assertion depends on implementation
        assert mock_http.post.call_count >= 2


class TestUnloadAllEndpoint:
    """Integration tests for POST /api/system/models/unload-all endpoint."""

    @pytest.mark.asyncio
    async def test_unload_all_clears_both_services(
        self,
        client: AsyncClient,
        mock_enrichment_responses: dict,
    ) -> None:
        """Test that unload-all calls both enrichment services.

        Verifies:
        - Both services are called to unload
        - Response indicates success for both services
        """
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=mock_enrichment_responses["get"])
        mock_http.post = AsyncMock(side_effect=mock_enrichment_responses["post"])

        with patch("backend.api.routes.model_management.get_http_client", return_value=mock_http):
            response = await client.post("/api/system/models/unload-all")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "services" in data

        # Both services should report success
        services = data["services"]
        assert "ai-enrichment" in services
        assert "ai-enrichment-light" in services
