"""Unit tests for /api/system/models endpoints.

Tests the model zoo status API endpoints that expose model registry,
VRAM usage, and individual model status information.
"""

from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app


class TestGetModelsEndpoint:
    """Tests for GET /api/system/models endpoint."""

    @pytest.mark.asyncio
    async def test_get_models_returns_registry(self) -> None:
        """Test that GET /api/system/models returns model registry."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/system/models")

        assert response.status_code == 200
        data = response.json()

        # Verify top-level response structure
        assert "vram_budget_mb" in data
        assert "vram_used_mb" in data
        assert "vram_available_mb" in data
        assert "models" in data
        assert "loading_strategy" in data
        assert "max_concurrent_models" in data

        # Verify VRAM values are reasonable
        assert data["vram_budget_mb"] == 1650
        assert data["vram_available_mb"] == data["vram_budget_mb"] - data["vram_used_mb"]

    @pytest.mark.asyncio
    async def test_get_models_returns_model_list(self) -> None:
        """Test that models list contains expected model information."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/system/models")

        assert response.status_code == 200
        data = response.json()

        # Should have models
        assert isinstance(data["models"], list)
        assert len(data["models"]) > 0

        # Check first model has required fields
        model = data["models"][0]
        assert "name" in model
        assert "display_name" in model
        assert "vram_mb" in model
        assert "status" in model
        assert "category" in model
        assert "enabled" in model

    @pytest.mark.asyncio
    async def test_get_models_shows_loaded_status(self) -> None:
        """Test that loaded models show 'loaded' status."""
        # Mock ModelManager with a loaded model
        mock_manager = MagicMock()
        mock_manager.loaded_models = ["yolo11-license-plate"]
        mock_manager.total_loaded_vram = 300
        mock_manager._load_counts = {"yolo11-license-plate": 1}

        with patch(
            "backend.api.routes.system.get_model_manager",
            return_value=mock_manager,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/system/models")

        assert response.status_code == 200
        data = response.json()

        # Find the loaded model
        loaded_model = None
        for model in data["models"]:
            if model["name"] == "yolo11-license-plate":
                loaded_model = model
                break

        assert loaded_model is not None
        assert loaded_model["status"] == "loaded"

    @pytest.mark.asyncio
    async def test_get_models_shows_unloaded_status(self) -> None:
        """Test that unloaded models show 'unloaded' status."""
        # Mock ModelManager with no loaded models
        mock_manager = MagicMock()
        mock_manager.loaded_models = []
        mock_manager.total_loaded_vram = 0
        mock_manager._load_counts = {}

        with patch(
            "backend.api.routes.system.get_model_manager",
            return_value=mock_manager,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/system/models")

        assert response.status_code == 200
        data = response.json()

        # All enabled models should be unloaded
        for model in data["models"]:
            if model["enabled"]:
                assert model["status"] == "unloaded"


class TestGetModelByNameEndpoint:
    """Tests for GET /api/system/models/{model_name} endpoint."""

    @pytest.mark.asyncio
    async def test_get_model_returns_details(self) -> None:
        """Test that GET /api/system/models/{name} returns model details."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/system/models/yolo11-license-plate")

        assert response.status_code == 200
        data = response.json()

        # Verify model details
        assert data["name"] == "yolo11-license-plate"
        assert "display_name" in data
        assert data["vram_mb"] == 300
        assert data["category"] == "detection"
        assert data["enabled"] is True

    @pytest.mark.asyncio
    async def test_get_model_not_found(self) -> None:
        """Test that non-existent model returns 404."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/system/models/nonexistent-model")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_model_shows_load_stats(self) -> None:
        """Test that model details include load statistics."""
        # Mock ModelManager with a loaded model
        mock_manager = MagicMock()
        mock_manager.loaded_models = ["yolo11-license-plate"]
        mock_manager.total_loaded_vram = 300
        mock_manager._load_counts = {"yolo11-license-plate": 1}

        with patch(
            "backend.api.routes.system.get_model_manager",
            return_value=mock_manager,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/system/models/yolo11-license-plate")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "loaded"
        assert "load_count" in data

    @pytest.mark.asyncio
    async def test_get_disabled_model(self) -> None:
        """Test that disabled models return status='disabled'."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            # yolo26-general is disabled by default
            response = await client.get("/api/system/models/yolo26-general")

        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "yolo26-general"
        assert data["enabled"] is False
        assert data["status"] == "disabled"


class TestModelStatusSchema:
    """Tests for model status response schema validation."""

    @pytest.mark.asyncio
    async def test_model_status_response_has_all_fields(self) -> None:
        """Test that model status response contains all required fields."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/system/models/yolo11-face")

        assert response.status_code == 200
        data = response.json()

        # Required fields for individual model status
        required_fields = [
            "name",
            "display_name",
            "vram_mb",
            "status",
            "category",
            "enabled",
            "available",
            "path",
        ]

        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

    @pytest.mark.asyncio
    async def test_models_registry_response_has_all_fields(self) -> None:
        """Test that models registry response contains all required fields."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/system/models")

        assert response.status_code == 200
        data = response.json()

        # Required fields for registry response
        required_fields = [
            "vram_budget_mb",
            "vram_used_mb",
            "vram_available_mb",
            "models",
            "loading_strategy",
            "max_concurrent_models",
        ]

        for field in required_fields:
            assert field in data, f"Missing required field: {field}"


class TestVRAMStats:
    """Tests for VRAM statistics in model registry."""

    @pytest.mark.asyncio
    async def test_vram_used_reflects_loaded_models(self) -> None:
        """Test that vram_used_mb reflects currently loaded models."""
        # Mock ModelManager with loaded models
        mock_manager = MagicMock()
        mock_manager.loaded_models = ["yolo11-license-plate", "yolo11-face"]
        mock_manager.total_loaded_vram = 500  # 300 + 200
        mock_manager._load_counts = {
            "yolo11-license-plate": 1,
            "yolo11-face": 1,
        }

        with patch(
            "backend.api.routes.system.get_model_manager",
            return_value=mock_manager,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/system/models")

        assert response.status_code == 200
        data = response.json()

        assert data["vram_used_mb"] == 500
        assert data["vram_available_mb"] == data["vram_budget_mb"] - 500

    @pytest.mark.asyncio
    async def test_vram_zero_when_no_models_loaded(self) -> None:
        """Test that vram_used_mb is 0 when no models are loaded."""
        mock_manager = MagicMock()
        mock_manager.loaded_models = []
        mock_manager.total_loaded_vram = 0
        mock_manager._load_counts = {}

        with patch(
            "backend.api.routes.system.get_model_manager",
            return_value=mock_manager,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/system/models")

        assert response.status_code == 200
        data = response.json()

        assert data["vram_used_mb"] == 0
        assert data["vram_available_mb"] == data["vram_budget_mb"]
