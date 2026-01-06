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
        # Support both old format (detail) and new standardized format (error.message)
        if "error" in data:
            assert "not found" in data["error"]["message"].lower()
        else:
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


class TestModelZooStatusEndpoint:
    """Tests for GET /api/system/model-zoo/status endpoint."""

    @pytest.mark.asyncio
    async def test_get_model_zoo_status_returns_all_models(self) -> None:
        """Test that GET /api/system/model-zoo/status returns status for all models."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/system/model-zoo/status")

        assert response.status_code == 200
        data = response.json()

        # Verify top-level response structure
        assert "models" in data
        assert "total_models" in data
        assert "loaded_count" in data
        assert "disabled_count" in data
        assert "vram_budget_mb" in data
        assert "vram_used_mb" in data
        assert "timestamp" in data

        # Should have multiple models
        assert len(data["models"]) > 0
        assert data["total_models"] == len(data["models"])

    @pytest.mark.asyncio
    async def test_model_zoo_status_item_structure(self) -> None:
        """Test that each model status item has required fields."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/system/model-zoo/status")

        assert response.status_code == 200
        data = response.json()

        # Check first model has required fields
        model = data["models"][0]
        required_fields = [
            "name",
            "display_name",
            "category",
            "status",
            "vram_mb",
            "last_used_at",
            "enabled",
        ]
        for field in required_fields:
            assert field in model, f"Missing required field: {field}"

    @pytest.mark.asyncio
    async def test_model_zoo_status_shows_loaded_models(self) -> None:
        """Test that loaded models show 'loaded' status in compact view."""
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
                response = await client.get("/api/system/model-zoo/status")

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
        assert data["loaded_count"] == 1

    @pytest.mark.asyncio
    async def test_model_zoo_status_shows_disabled_models(self) -> None:
        """Test that disabled models show 'disabled' status."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/system/model-zoo/status")

        assert response.status_code == 200
        data = response.json()

        # Find a disabled model (yolo26-general is disabled by default)
        disabled_model = None
        for model in data["models"]:
            if model["name"] == "yolo26-general":
                disabled_model = model
                break

        assert disabled_model is not None
        assert disabled_model["status"] == "disabled"
        assert disabled_model["enabled"] is False

    @pytest.mark.asyncio
    async def test_model_zoo_status_models_sorted_correctly(self) -> None:
        """Test that models are sorted with enabled first, then disabled."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/system/model-zoo/status")

        assert response.status_code == 200
        data = response.json()

        # Check that all enabled models come before disabled models
        found_disabled = False
        for model in data["models"]:
            if not model["enabled"]:
                found_disabled = True
            elif found_disabled:
                # Found enabled model after disabled - wrong order
                pytest.fail("Enabled models should appear before disabled models")


class TestModelZooLatencyHistoryEndpoint:
    """Tests for GET /api/system/model-zoo/latency/history endpoint."""

    @pytest.mark.asyncio
    async def test_get_latency_history_requires_model_param(self) -> None:
        """Test that model parameter is required."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/system/model-zoo/latency/history")

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_get_latency_history_for_valid_model(self) -> None:
        """Test that valid model returns latency history."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/system/model-zoo/latency/history",
                params={"model": "yolo11-license-plate"},
            )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["model_name"] == "yolo11-license-plate"
        assert "display_name" in data
        assert "snapshots" in data
        assert "window_minutes" in data
        assert "bucket_seconds" in data
        assert "has_data" in data
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_get_latency_history_not_found_for_invalid_model(self) -> None:
        """Test that invalid model returns 404."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/system/model-zoo/latency/history",
                params={"model": "nonexistent-model"},
            )

        assert response.status_code == 404
        data = response.json()
        # Support both old format (detail) and new standardized format (error.message)
        if "error" in data:
            assert "not found" in data["error"]["message"].lower()
        else:
            assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_latency_history_respects_since_param(self) -> None:
        """Test that since parameter controls window size."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/system/model-zoo/latency/history",
                params={"model": "yolo11-license-plate", "since": 30},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["window_minutes"] == 30

    @pytest.mark.asyncio
    async def test_get_latency_history_respects_bucket_seconds_param(self) -> None:
        """Test that bucket_seconds parameter controls bucket size."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/system/model-zoo/latency/history",
                params={"model": "yolo11-license-plate", "bucket_seconds": 120},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["bucket_seconds"] == 120

    @pytest.mark.asyncio
    async def test_get_latency_history_with_data(self) -> None:
        """Test that latency history with data returns proper snapshots."""
        from backend.core.metrics import ModelLatencyTracker

        # Create a tracker with some data
        mock_tracker = ModelLatencyTracker(max_samples=100)
        mock_tracker.record_model_latency("yolo11-license-plate", 45.0)
        mock_tracker.record_model_latency("yolo11-license-plate", 50.0)
        mock_tracker.record_model_latency("yolo11-license-plate", 55.0)

        with patch(
            "backend.core.metrics.get_model_latency_tracker",
            return_value=mock_tracker,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    "/api/system/model-zoo/latency/history",
                    params={"model": "yolo11-license-plate"},
                )

        assert response.status_code == 200
        data = response.json()

        assert data["has_data"] is True
        assert len(data["snapshots"]) > 0

        # Find a snapshot with data
        snapshot_with_data = None
        for snapshot in data["snapshots"]:
            if snapshot["stats"] is not None:
                snapshot_with_data = snapshot
                break

        assert snapshot_with_data is not None
        stats = snapshot_with_data["stats"]
        assert "avg_ms" in stats
        assert "p50_ms" in stats
        assert "p95_ms" in stats
        assert "sample_count" in stats

    @pytest.mark.asyncio
    async def test_get_latency_history_no_data_shows_empty(self) -> None:
        """Test that model with no data returns has_data=False."""
        from backend.core.metrics import ModelLatencyTracker

        # Create an empty tracker
        mock_tracker = ModelLatencyTracker(max_samples=100)

        with patch(
            "backend.core.metrics.get_model_latency_tracker",
            return_value=mock_tracker,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    "/api/system/model-zoo/latency/history",
                    params={"model": "yolo11-license-plate"},
                )

        assert response.status_code == 200
        data = response.json()

        assert data["has_data"] is False


class TestModelLatencyTracker:
    """Tests for ModelLatencyTracker class."""

    def test_record_and_get_model_stats(self) -> None:
        """Test recording latency and retrieving stats."""
        from backend.core.metrics import ModelLatencyTracker

        tracker = ModelLatencyTracker(max_samples=100)
        tracker.record_model_latency("test-model", 100.0)
        tracker.record_model_latency("test-model", 200.0)
        tracker.record_model_latency("test-model", 300.0)

        stats = tracker.get_model_stats("test-model", window_minutes=60)

        assert stats["sample_count"] == 3
        assert stats["avg_ms"] == 200.0
        assert stats["p50_ms"] is not None
        assert stats["p95_ms"] is not None

    def test_get_stats_for_unknown_model(self) -> None:
        """Test that unknown model returns empty stats."""
        from backend.core.metrics import ModelLatencyTracker

        tracker = ModelLatencyTracker(max_samples=100)
        stats = tracker.get_model_stats("unknown-model", window_minutes=60)

        assert stats["sample_count"] == 0
        assert stats["avg_ms"] is None
        assert stats["p50_ms"] is None
        assert stats["p95_ms"] is None

    def test_get_model_latency_history_buckets(self) -> None:
        """Test that latency history returns bucketed data."""
        from backend.core.metrics import ModelLatencyTracker

        tracker = ModelLatencyTracker(max_samples=100)
        tracker.record_model_latency("test-model", 50.0)

        history = tracker.get_model_latency_history(
            "test-model",
            window_minutes=5,
            bucket_seconds=60,
        )

        # Should have 5 buckets (5 minutes * 60 seconds / 60 seconds per bucket)
        assert len(history) == 5

        # Each bucket should have timestamp and stats (can be None)
        for snapshot in history:
            assert "timestamp" in snapshot
            assert "stats" in snapshot

    def test_circular_buffer_limits_samples(self) -> None:
        """Test that circular buffer limits sample storage."""
        from backend.core.metrics import ModelLatencyTracker

        tracker = ModelLatencyTracker(max_samples=10)

        # Record more than max samples
        for i in range(20):
            tracker.record_model_latency("test-model", float(i))

        stats = tracker.get_model_stats("test-model", window_minutes=60)

        # Should only have max_samples
        assert stats["sample_count"] == 10
