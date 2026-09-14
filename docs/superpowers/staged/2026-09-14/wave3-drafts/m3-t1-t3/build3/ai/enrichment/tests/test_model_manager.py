"""Unit tests for OnDemandModelManager.

Tests cover:
- Model registration and configuration
- On-demand model loading
- LRU eviction with priority-based ordering
- VRAM budget enforcement
- Thread safety with concurrent access
- Status reporting and monitoring
- Idle model cleanup
- Prometheus metrics for VRAM monitoring (NEM-3149)
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from ai.enrichment.model_manager import (
    ENRICHMENT_MODEL_EVICTIONS_TOTAL,
    ENRICHMENT_MODEL_LOAD_TIME_SECONDS,
    ENRICHMENT_MODELS_LOADED,
    ENRICHMENT_VRAM_BUDGET_BYTES,
    ENRICHMENT_VRAM_USAGE_BYTES,
    ENRICHMENT_VRAM_UTILIZATION_PERCENT,
    ModelConfig,
    ModelInfo,
    ModelPriority,
    OnDemandModelManager,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def manager() -> OnDemandModelManager:
    """Create a model manager with 1GB budget for testing."""
    return OnDemandModelManager(vram_budget_gb=1.0)


@pytest.fixture
def small_manager() -> OnDemandModelManager:
    """Create a model manager with small budget (500MB) for eviction tests."""
    return OnDemandModelManager(vram_budget_gb=0.5)


def create_mock_model(name: str = "mock") -> MagicMock:
    """Create a mock model instance."""
    mock = MagicMock()
    mock.name = name
    return mock


def create_model_config(
    name: str,
    vram_mb: int,
    priority: ModelPriority = ModelPriority.MEDIUM,
    load_delay: float = 0.0,
) -> ModelConfig:
    """Create a model config with mock loader/unloader.

    Args:
        name: Model name
        vram_mb: VRAM usage in MB
        priority: Model priority for eviction
        load_delay: Simulated load time in seconds

    Returns:
        ModelConfig with mock functions
    """
    model = create_mock_model(name)

    def loader() -> MagicMock:
        if load_delay > 0:
            import time

            time.sleep(load_delay)
        return model

    def unloader(m: MagicMock) -> None:
        pass

    return ModelConfig(
        name=name,
        vram_mb=vram_mb,
        priority=priority,
        loader_fn=loader,
        unloader_fn=unloader,
    )


# =============================================================================
# ModelPriority Tests
# =============================================================================


class TestModelPriority:
    """Tests for ModelPriority enum."""

    def test_priority_ordering(self) -> None:
        """CRITICAL < HIGH < MEDIUM < LOW in terms of eviction priority."""
        assert ModelPriority.CRITICAL < ModelPriority.HIGH
        assert ModelPriority.HIGH < ModelPriority.MEDIUM
        assert ModelPriority.MEDIUM < ModelPriority.LOW

    def test_priority_values(self) -> None:
        """Priority values are integers as expected."""
        assert ModelPriority.CRITICAL == 0
        assert ModelPriority.HIGH == 1
        assert ModelPriority.MEDIUM == 2
        assert ModelPriority.LOW == 3

    def test_priority_comparison(self) -> None:
        """Priority can be compared numerically."""
        assert ModelPriority.LOW > ModelPriority.CRITICAL
        assert ModelPriority.MEDIUM >= ModelPriority.HIGH


# =============================================================================
# ModelInfo Tests
# =============================================================================


class TestModelInfo:
    """Tests for ModelInfo dataclass."""

    def test_create_model_info(self) -> None:
        """ModelInfo stores model metadata correctly."""
        model = create_mock_model()
        now = datetime.now()

        info = ModelInfo(
            model=model,
            vram_mb=500,
            priority=ModelPriority.HIGH,
            last_used=now,
        )

        assert info.model is model
        assert info.vram_mb == 500
        assert info.priority == ModelPriority.HIGH
        assert info.last_used == now


# =============================================================================
# ModelConfig Tests
# =============================================================================


class TestModelConfig:
    """Tests for ModelConfig dataclass."""

    def test_create_model_config(self) -> None:
        """ModelConfig stores configuration correctly."""

        def loader() -> str:
            return "model"

        def unloader(m: str) -> None:
            pass

        config = ModelConfig(
            name="test-model",
            vram_mb=1000,
            priority=ModelPriority.CRITICAL,
            loader_fn=loader,
            unloader_fn=unloader,
        )

        assert config.name == "test-model"
        assert config.vram_mb == 1000
        assert config.priority == ModelPriority.CRITICAL
        assert config.loader_fn() == "model"


# =============================================================================
# OnDemandModelManager Initialization Tests
# =============================================================================


class TestModelManagerInit:
    """Tests for OnDemandModelManager initialization."""

    def test_default_budget(self) -> None:
        """Default VRAM budget is 6.8GB."""
        manager = OnDemandModelManager()
        assert manager.vram_budget == 6.8 * 1024  # 6963.2 MB

    def test_custom_budget(self) -> None:
        """Custom VRAM budget is converted to MB."""
        manager = OnDemandModelManager(vram_budget_gb=2.0)
        assert manager.vram_budget == 2048  # 2GB = 2048MB

    def test_initial_state(self) -> None:
        """Manager starts with empty model collections."""
        manager = OnDemandModelManager()
        assert len(manager.loaded_models) == 0
        assert len(manager.model_registry) == 0
        assert len(manager.pending_loads) == 0


# =============================================================================
# Model Registration Tests
# =============================================================================


class TestModelRegistration:
    """Tests for model registration."""

    def test_register_model(self, manager: OnDemandModelManager) -> None:
        """Model can be registered."""
        config = create_model_config("test-model", 500)
        manager.register_model(config)

        assert "test-model" in manager.model_registry
        assert manager.model_registry["test-model"] is config

    def test_register_duplicate_raises(self, manager: OnDemandModelManager) -> None:
        """Registering duplicate model name raises ValueError."""
        config = create_model_config("test-model", 500)
        manager.register_model(config)

        with pytest.raises(ValueError, match="already registered"):
            manager.register_model(config)

    def test_unregister_model(self, manager: OnDemandModelManager) -> None:
        """Model can be unregistered."""
        config = create_model_config("test-model", 500)
        manager.register_model(config)
        manager.unregister_model("test-model")

        assert "test-model" not in manager.model_registry

    def test_unregister_nonexistent_is_safe(self, manager: OnDemandModelManager) -> None:
        """Unregistering nonexistent model is a no-op."""
        manager.unregister_model("nonexistent")  # Should not raise


# =============================================================================
# Model Loading Tests
# =============================================================================


class TestModelLoading:
    """Tests for on-demand model loading."""

    @pytest.mark.asyncio
    async def test_get_model_loads_on_demand(self, manager: OnDemandModelManager) -> None:
        """get_model loads model on first access."""
        config = create_model_config("test-model", 500)
        manager.register_model(config)

        assert not manager.is_loaded("test-model")

        model = await manager.get_model("test-model")

        assert manager.is_loaded("test-model")
        assert model is not None

    @pytest.mark.asyncio
    async def test_get_model_returns_cached(self, manager: OnDemandModelManager) -> None:
        """get_model returns cached model on subsequent calls."""
        config = create_model_config("test-model", 500)
        manager.register_model(config)

        model1 = await manager.get_model("test-model")
        model2 = await manager.get_model("test-model")

        assert model1 is model2

    @pytest.mark.asyncio
    async def test_get_unknown_model_raises(self, manager: OnDemandModelManager) -> None:
        """get_model raises ValueError for unregistered model."""
        with pytest.raises(ValueError, match="Unknown model"):
            await manager.get_model("nonexistent")

    @pytest.mark.asyncio
    async def test_get_model_updates_last_used(self, manager: OnDemandModelManager) -> None:
        """get_model updates last_used timestamp."""
        config = create_model_config("test-model", 500)
        manager.register_model(config)

        await manager.get_model("test-model")
        first_access = manager.loaded_models["test-model"].last_used

        await asyncio.sleep(0.01)  # Small delay
        await manager.get_model("test-model")
        second_access = manager.loaded_models["test-model"].last_used

        assert second_access > first_access

    @pytest.mark.asyncio
    async def test_vram_tracking(self, manager: OnDemandModelManager) -> None:
        """VRAM usage is tracked correctly."""
        config1 = create_model_config("model1", 300)
        config2 = create_model_config("model2", 200)
        manager.register_model(config1)
        manager.register_model(config2)

        assert manager._current_vram_usage() == 0

        await manager.get_model("model1")
        assert manager._current_vram_usage() == 300

        await manager.get_model("model2")
        assert manager._current_vram_usage() == 500


# =============================================================================
# Model Unloading Tests
# =============================================================================


class TestModelUnloading:
    """Tests for model unloading."""

    @pytest.mark.asyncio
    async def test_unload_model(self, manager: OnDemandModelManager) -> None:
        """unload_model removes model from memory."""
        config = create_model_config("test-model", 500)
        manager.register_model(config)

        await manager.get_model("test-model")
        assert manager.is_loaded("test-model")

        await manager.unload_model("test-model")
        assert not manager.is_loaded("test-model")

    @pytest.mark.asyncio
    async def test_unload_nonexistent_is_safe(self, manager: OnDemandModelManager) -> None:
        """Unloading nonexistent model is a no-op."""
        await manager.unload_model("nonexistent")  # Should not raise

    @pytest.mark.asyncio
    async def test_unload_all(self, manager: OnDemandModelManager) -> None:
        """unload_all removes all loaded models."""
        config1 = create_model_config("model1", 300)
        config2 = create_model_config("model2", 200)
        manager.register_model(config1)
        manager.register_model(config2)

        await manager.get_model("model1")
        await manager.get_model("model2")
        assert len(manager.loaded_models) == 2

        await manager.unload_all()
        assert len(manager.loaded_models) == 0

    @pytest.mark.asyncio
    async def test_unload_calls_unloader(self, manager: OnDemandModelManager) -> None:
        """Unloading calls the unloader function."""
        unloader_called = []

        def unloader(m: MagicMock) -> None:
            unloader_called.append(m)

        config = ModelConfig(
            name="test-model",
            vram_mb=500,
            priority=ModelPriority.MEDIUM,
            loader_fn=create_mock_model,
            unloader_fn=unloader,
        )
        manager.register_model(config)

        await manager.get_model("test-model")
        await manager.unload_model("test-model")

        assert len(unloader_called) == 1


# =============================================================================
# LRU Eviction Tests
# =============================================================================


class TestLRUEviction:
    """Tests for LRU eviction logic."""

    @pytest.mark.asyncio
    async def test_eviction_when_over_budget(self, small_manager: OnDemandModelManager) -> None:
        """Models are evicted when VRAM budget is exceeded."""
        # Budget is 500MB
        config1 = create_model_config("model1", 300, ModelPriority.MEDIUM)
        config2 = create_model_config("model2", 300, ModelPriority.MEDIUM)
        small_manager.register_model(config1)
        small_manager.register_model(config2)

        await small_manager.get_model("model1")
        assert small_manager.is_loaded("model1")

        # Loading model2 should evict model1 (300 + 300 = 600 > 500)
        await small_manager.get_model("model2")

        assert not small_manager.is_loaded("model1")  # Evicted
        assert small_manager.is_loaded("model2")  # Loaded

    @pytest.mark.asyncio
    async def test_lru_eviction_order(self, small_manager: OnDemandModelManager) -> None:
        """Least recently used model is evicted first (same priority)."""
        # Budget is 500MB
        config1 = create_model_config("model1", 200, ModelPriority.MEDIUM)
        config2 = create_model_config("model2", 200, ModelPriority.MEDIUM)
        config3 = create_model_config("model3", 200, ModelPriority.MEDIUM)
        small_manager.register_model(config1)
        small_manager.register_model(config2)
        small_manager.register_model(config3)

        # Load model1 and model2 (400MB used)
        await small_manager.get_model("model1")
        await asyncio.sleep(0.01)
        await small_manager.get_model("model2")

        # Access model1 again to make it more recent
        await asyncio.sleep(0.01)
        await small_manager.get_model("model1")

        # Loading model3 should evict model2 (LRU among same priority)
        await small_manager.get_model("model3")

        assert small_manager.is_loaded("model1")  # Recently used, kept
        assert not small_manager.is_loaded("model2")  # Oldest, evicted
        assert small_manager.is_loaded("model3")  # Just loaded

    @pytest.mark.asyncio
    async def test_priority_based_eviction(self, small_manager: OnDemandModelManager) -> None:
        """Lower priority models are evicted before higher priority."""
        # Budget is 500MB
        config_critical = create_model_config("critical", 200, ModelPriority.CRITICAL)
        config_low = create_model_config("low", 200, ModelPriority.LOW)
        config_new = create_model_config("new", 200, ModelPriority.MEDIUM)
        small_manager.register_model(config_critical)
        small_manager.register_model(config_low)
        small_manager.register_model(config_new)

        # Load critical and low (400MB used)
        await small_manager.get_model("low")  # Loaded first
        await asyncio.sleep(0.01)
        await small_manager.get_model("critical")  # Loaded second but higher priority

        # Loading new should evict low (lower priority) even though critical was more recent
        await small_manager.get_model("new")

        assert small_manager.is_loaded("critical")  # High priority, kept
        assert not small_manager.is_loaded("low")  # Low priority, evicted
        assert small_manager.is_loaded("new")  # Just loaded

    @pytest.mark.asyncio
    async def test_cannot_load_model_larger_than_budget(
        self, small_manager: OnDemandModelManager
    ) -> None:
        """RuntimeError raised when model is larger than entire budget."""
        config = create_model_config("huge", 1000)  # 1000MB > 500MB budget
        small_manager.register_model(config)

        with pytest.raises(RuntimeError, match="insufficient VRAM"):
            await small_manager.get_model("huge")


# =============================================================================
# Concurrent Access Tests
# =============================================================================


class TestConcurrentAccess:
    """Tests for thread safety and concurrent access."""

    @pytest.mark.asyncio
    async def test_concurrent_loads_same_model(self, manager: OnDemandModelManager) -> None:
        """Concurrent loads of same model don't cause issues."""
        config = create_model_config("test-model", 500, load_delay=0.05)
        manager.register_model(config)

        # Start multiple concurrent loads
        tasks = [manager.get_model("test-model") for _ in range(5)]
        results = await asyncio.gather(*tasks)

        # All should return the same model instance
        assert all(r is results[0] for r in results)
        assert manager.is_loaded("test-model")

    @pytest.mark.asyncio
    async def test_concurrent_loads_different_models(self, manager: OnDemandModelManager) -> None:
        """Concurrent loads of different models work correctly."""
        config1 = create_model_config("model1", 200)
        config2 = create_model_config("model2", 200)
        config3 = create_model_config("model3", 200)
        manager.register_model(config1)
        manager.register_model(config2)
        manager.register_model(config3)

        tasks = [
            manager.get_model("model1"),
            manager.get_model("model2"),
            manager.get_model("model3"),
        ]
        await asyncio.gather(*tasks)

        assert manager.is_loaded("model1")
        assert manager.is_loaded("model2")
        assert manager.is_loaded("model3")


# =============================================================================
# Status Reporting Tests
# =============================================================================


class TestStatusReporting:
    """Tests for status and monitoring."""

    def test_is_loaded(self, manager: OnDemandModelManager) -> None:
        """is_loaded returns correct state."""
        config = create_model_config("test-model", 500)
        manager.register_model(config)

        assert not manager.is_loaded("test-model")
        assert not manager.is_loaded("nonexistent")

    @pytest.mark.asyncio
    async def test_get_loaded_models(self, manager: OnDemandModelManager) -> None:
        """get_loaded_models returns list of loaded model names."""
        config1 = create_model_config("model1", 200)
        config2 = create_model_config("model2", 200)
        manager.register_model(config1)
        manager.register_model(config2)

        assert manager.get_loaded_models() == []

        await manager.get_model("model1")
        assert manager.get_loaded_models() == ["model1"]

        await manager.get_model("model2")
        assert set(manager.get_loaded_models()) == {"model1", "model2"}

    @pytest.mark.asyncio
    async def test_get_status(self, manager: OnDemandModelManager) -> None:
        """get_status returns comprehensive status info."""
        config = create_model_config("test-model", 500, ModelPriority.HIGH)
        manager.register_model(config)
        await manager.get_model("test-model")

        status = manager.get_status()

        assert status["vram_budget_mb"] == 1024  # 1GB
        assert status["vram_used_mb"] == 500
        assert status["vram_available_mb"] == 524
        assert "vram_utilization_percent" in status
        assert len(status["loaded_models"]) == 1
        assert status["loaded_models"][0]["name"] == "test-model"
        assert status["loaded_models"][0]["vram_mb"] == 500
        assert status["loaded_models"][0]["priority"] == "HIGH"
        assert len(status["registered_models"]) == 1
        assert status["pending_loads"] == []


# =============================================================================
# Idle Cleanup Tests
# =============================================================================


class TestIdleCleanup:
    """Tests for idle model cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_idle_models(self, manager: OnDemandModelManager) -> None:
        """cleanup_idle_models unloads models not used recently."""
        config = create_model_config("test-model", 500)
        manager.register_model(config)

        await manager.get_model("test-model")

        # Manually set last_used to past
        manager.loaded_models["test-model"].last_used = datetime.now() - timedelta(seconds=600)

        # Cleanup with 300s threshold should unload the model
        unloaded = await manager.cleanup_idle_models(idle_seconds=300)

        assert "test-model" in unloaded
        assert not manager.is_loaded("test-model")

    @pytest.mark.asyncio
    async def test_cleanup_keeps_recent_models(self, manager: OnDemandModelManager) -> None:
        """cleanup_idle_models keeps recently used models."""
        config = create_model_config("test-model", 500)
        manager.register_model(config)

        await manager.get_model("test-model")

        # Model was just accessed, should not be cleaned up
        unloaded = await manager.cleanup_idle_models(idle_seconds=300)

        assert unloaded == []
        assert manager.is_loaded("test-model")

    @pytest.mark.asyncio
    async def test_cleanup_selective(self, manager: OnDemandModelManager) -> None:
        """cleanup_idle_models only unloads idle models."""
        config1 = create_model_config("old-model", 200)
        config2 = create_model_config("new-model", 200)
        manager.register_model(config1)
        manager.register_model(config2)

        await manager.get_model("old-model")
        await manager.get_model("new-model")

        # Make old-model idle
        manager.loaded_models["old-model"].last_used = datetime.now() - timedelta(seconds=600)

        unloaded = await manager.cleanup_idle_models(idle_seconds=300)

        assert "old-model" in unloaded
        assert "new-model" not in unloaded
        assert not manager.is_loaded("old-model")
        assert manager.is_loaded("new-model")


# =============================================================================
# CUDA Integration Tests
# =============================================================================


class TestCUDAIntegration:
    """Tests for CUDA/torch integration."""

    @pytest.mark.asyncio
    async def test_unload_clears_cuda_cache(self, manager: OnDemandModelManager) -> None:
        """Unloading model clears CUDA cache."""
        config = create_model_config("test-model", 500)
        manager.register_model(config)

        await manager.get_model("test-model")

        with (
            patch("torch.cuda.is_available", return_value=True),
            patch("torch.cuda.empty_cache") as mock_empty_cache,
        ):
            await manager.unload_model("test-model")
            mock_empty_cache.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_cuda_available(self, manager: OnDemandModelManager) -> None:
        """Works correctly when CUDA is not available."""
        config = create_model_config("test-model", 500)
        manager.register_model(config)

        await manager.get_model("test-model")

        with (
            patch("torch.cuda.is_available", return_value=False),
            patch("torch.cuda.empty_cache") as mock_empty_cache,
        ):
            await manager.unload_model("test-model")
            mock_empty_cache.assert_not_called()


# =============================================================================
# Prometheus Metrics Tests (NEM-3149)
# =============================================================================


class TestPrometheusMetrics:
    """Tests for Prometheus metrics tracking VRAM usage and model evictions."""

    def test_budget_metric_set_on_init(self) -> None:
        """VRAM budget metric is set when manager is initialized."""
        # Create manager - triggers budget metric to be set (side effect)
        _manager = OnDemandModelManager(vram_budget_gb=2.0)

        # 2GB = 2 * 1024 * 1024 * 1024 bytes = 2147483648 bytes
        expected_budget_bytes = 2.0 * 1024 * 1024 * 1024
        assert ENRICHMENT_VRAM_BUDGET_BYTES._value.get() == expected_budget_bytes

        # Cleanup - create new manager with different budget to reset
        _ = OnDemandModelManager(vram_budget_gb=6.8)

    @pytest.mark.asyncio
    async def test_vram_usage_metric_updated_on_load(self) -> None:
        """VRAM usage metrics are updated when models are loaded."""
        manager = OnDemandModelManager(vram_budget_gb=1.0)
        config = create_model_config("metrics-test-load", 500)
        manager.register_model(config)

        # Initially no models loaded
        initial_usage = ENRICHMENT_VRAM_USAGE_BYTES._value.get()
        initial_loaded = ENRICHMENT_MODELS_LOADED._value.get()

        await manager.get_model("metrics-test-load")

        # After loading, usage should increase by 500MB
        # 500 MB = 500 * 1024 * 1024 bytes = 524288000 bytes
        new_usage = ENRICHMENT_VRAM_USAGE_BYTES._value.get()
        new_loaded = ENRICHMENT_MODELS_LOADED._value.get()

        # The difference should be 500MB in bytes
        assert new_usage == initial_usage + (500 * 1024 * 1024)
        assert new_loaded == initial_loaded + 1

        # Cleanup
        await manager.unload_all()

    @pytest.mark.asyncio
    async def test_vram_utilization_metric(self) -> None:
        """VRAM utilization percentage is correctly calculated."""
        manager = OnDemandModelManager(vram_budget_gb=1.0)  # 1GB = 1024 MB budget
        config = create_model_config("metrics-test-util", 512)  # 512 MB = 50%
        manager.register_model(config)

        await manager.get_model("metrics-test-util")

        utilization = ENRICHMENT_VRAM_UTILIZATION_PERCENT._value.get()
        # 512 / 1024 * 100 = 50%
        assert utilization == 50.0

        # Cleanup
        await manager.unload_all()

    @pytest.mark.asyncio
    async def test_vram_usage_metric_updated_on_unload(self) -> None:
        """VRAM usage metrics are updated when models are unloaded."""
        manager = OnDemandModelManager(vram_budget_gb=1.0)
        config = create_model_config("metrics-test-unload", 300)
        manager.register_model(config)

        await manager.get_model("metrics-test-unload")
        usage_after_load = ENRICHMENT_VRAM_USAGE_BYTES._value.get()
        loaded_after_load = ENRICHMENT_MODELS_LOADED._value.get()

        await manager.unload_model("metrics-test-unload")
        usage_after_unload = ENRICHMENT_VRAM_USAGE_BYTES._value.get()
        loaded_after_unload = ENRICHMENT_MODELS_LOADED._value.get()

        # Usage should decrease by 300MB
        assert usage_after_unload == usage_after_load - (300 * 1024 * 1024)
        assert loaded_after_unload == loaded_after_load - 1

    @pytest.mark.asyncio
    async def test_eviction_counter_incremented(self) -> None:
        """Eviction counter is incremented when models are evicted."""
        # Use small budget to force eviction
        manager = OnDemandModelManager(vram_budget_gb=0.5)  # 512 MB budget

        config1 = create_model_config("evict-test-1", 300, ModelPriority.LOW)
        config2 = create_model_config("evict-test-2", 300, ModelPriority.MEDIUM)
        manager.register_model(config1)
        manager.register_model(config2)

        # Get initial eviction count for model1
        initial_evictions = ENRICHMENT_MODEL_EVICTIONS_TOTAL.labels(
            model_name="evict-test-1",
            priority="LOW",
        )._value.get()

        # Load model1
        await manager.get_model("evict-test-1")
        assert manager.is_loaded("evict-test-1")

        # Loading model2 should evict model1 (300 + 300 = 600 > 512)
        await manager.get_model("evict-test-2")

        # Model1 should be evicted
        assert not manager.is_loaded("evict-test-1")

        # Eviction counter for model1 should be incremented
        new_evictions = ENRICHMENT_MODEL_EVICTIONS_TOTAL.labels(
            model_name="evict-test-1",
            priority="LOW",
        )._value.get()
        assert new_evictions == initial_evictions + 1

        # Cleanup
        await manager.unload_all()

    @pytest.mark.asyncio
    async def test_load_time_histogram_recorded(self) -> None:
        """Model load time is recorded in histogram."""
        manager = OnDemandModelManager(vram_budget_gb=1.0)

        # Create config with small delay to ensure measurable load time
        config = create_model_config("load-time-test", 200, load_delay=0.05)
        manager.register_model(config)

        # Get initial histogram sum for this model (histogram _sum is a float, not a Value)
        histogram = ENRICHMENT_MODEL_LOAD_TIME_SECONDS.labels(model_name="load-time-test")
        initial_sum = histogram._sum.get()

        await manager.get_model("load-time-test")

        # Histogram sum should have increased
        new_sum = histogram._sum.get()
        assert new_sum > initial_sum
        # The load time should be at least the delay we added
        assert new_sum >= initial_sum + 0.05

        # Cleanup
        await manager.unload_all()

    @pytest.mark.asyncio
    async def test_models_loaded_gauge_accuracy(self) -> None:
        """Models loaded gauge accurately reflects loaded model count."""
        manager = OnDemandModelManager(vram_budget_gb=2.0)  # Large budget

        config1 = create_model_config("gauge-test-1", 100)
        config2 = create_model_config("gauge-test-2", 100)
        config3 = create_model_config("gauge-test-3", 100)
        manager.register_model(config1)
        manager.register_model(config2)
        manager.register_model(config3)

        # Load models one by one and check gauge
        initial = ENRICHMENT_MODELS_LOADED._value.get()

        await manager.get_model("gauge-test-1")
        assert ENRICHMENT_MODELS_LOADED._value.get() == initial + 1

        await manager.get_model("gauge-test-2")
        assert ENRICHMENT_MODELS_LOADED._value.get() == initial + 2

        await manager.get_model("gauge-test-3")
        assert ENRICHMENT_MODELS_LOADED._value.get() == initial + 3

        # Unload all
        await manager.unload_all()
        # Gauge should be back to initial
        assert ENRICHMENT_MODELS_LOADED._value.get() == initial
