"""Integration tests for the AI model loaders R8 slice S2b left standing.

S2b retired the enrichment tier and 19 of the 22 model loaders with it, so this
file — which used to drive the CLIP, Florence, pet-classifier, violence, age,
gender and threat-detection loaders through the registry — shrank to what
survived: the ModelZoo/ModelManager contract (registry shape, VRAM budgets,
reference counting, error propagation) and the OSNet person re-ID loader.

HTTP calls to external AI services are mocked to isolate the tests. We're
testing the model loader infrastructure, not actual AI inference.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.model_zoo import (
    _LOADER_MAP,
    get_model_zoo,
    reset_model_manager,
    reset_model_zoo,
)
from backend.services.osnet_loader import load_osnet_model

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_transformers(monkeypatch):
    """Mock torch/transformers so loaders never touch real weights or a GPU.

    Kept under its original name: TestOSNetLoaderIntegration (whose loader
    survives S2b) uses it, and test_osnet_loader.py re-exports it for the
    check-integration-tests hook. The cuda.is_available=True setup is retained
    for OSNet only — the fail-fast CUDA guards that motivated it lived in the
    retired clip/violence/pet/gender/age loaders.
    """
    import sys

    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = True
    mock_torch.cuda.empty_cache = MagicMock()

    monkeypatch.setitem(sys.modules, "torch", mock_torch)

    return {"torch": mock_torch}


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset all singleton state before and after each test."""
    reset_model_zoo()
    reset_model_manager()
    yield
    reset_model_zoo()
    reset_model_manager()


def _stub_load(model_name: str, result: object):
    """Patch a zoo row's load_fn to return `result`.

    The pre-S2b version of this module drove real loaders through the manager;
    those modules are gone. The manager contract is loader-agnostic, so the
    manager tests stub the row's own load_fn and assert the manager behaviour
    they are actually about.
    """
    return patch.object(get_model_zoo()[model_name], "load_fn", AsyncMock(return_value=result))


# =============================================================================
# Test Model Zoo Integration
# =============================================================================


class TestModelZooIntegration:
    """Integration tests for Model Zoo model registry."""

    def test_get_model_zoo_returns_registry(self):
        """Test get_model_zoo returns model configurations.

        The rows asserted here before S2b (siglip2-base-patch16-224,
        florence-2-large, pet-classifier) were retired with their loaders;
        these are rows models.yml still ships to the backend.
        """
        zoo = get_model_zoo()

        assert isinstance(zoo, dict)
        assert "osnet-ain-x1-0" in zoo
        assert "yolo11-license-plate" in zoo
        assert "face-recognizer" in zoo

    def test_registry_is_a_subset_of_the_loader_map(self):
        """A row only reaches the registry if it has a loader, and the loader
        map points at no row the retired yaml rows left behind."""
        zoo = get_model_zoo()

        assert set(zoo) <= set(_LOADER_MAP)

    def test_model_configs_have_required_fields(self):
        """Test all model configs have required fields."""
        zoo = get_model_zoo()

        for name, config in zoo.items():
            assert config.name == name
            assert isinstance(config.vram_mb, int)
            assert config.vram_mb >= 0
            assert config.category in [
                "detection",
                "ocr",
                "embedding",
                "pose",
                # fast-alpr (models.yml: category alpr) — categories flow
                # verbatim from models.yml into ModelConfig (3396d3ef unified
                # registry). The other categories this list carried
                # (vision-language, depth-estimation, classification,
                # segmentation, action-recognition, quality-assessment,
                # preprocessing) belonged to rows S2b retired.
                "alpr",
            ]
            assert callable(config.load_fn)
            assert isinstance(config.enabled, bool)

    def test_model_configs_vram_budgets_reasonable(self):
        """Test model VRAM budgets are within reasonable limits."""
        zoo = get_model_zoo()

        # No single model should exceed 3GB VRAM budget
        for name, config in zoo.items():
            assert config.vram_mb <= 3000, f"{name} VRAM budget too high: {config.vram_mb}MB"

    def test_osnet_model_in_zoo(self):
        """Test the re-ID row is registered correctly.

        Replaces test_clip_model_in_zoo (the CLIP row and its loader were
        retired by S2b). This is the surviving row whose load_fn identity is
        pinned — and it is pinned *through* the sha256 partial, because
        models.yml binds the F12 hash into the loader rather than storing the
        bare function.
        """
        import functools

        zoo = get_model_zoo()
        config = zoo["osnet-ain-x1-0"]

        assert config.name == "osnet-ain-x1-0"
        assert config.category == "embedding"
        assert config.enabled is True
        assert isinstance(config.load_fn, functools.partial)
        assert config.load_fn.func is load_osnet_model


# =============================================================================
# Test Model Manager Integration
# =============================================================================


class TestModelManagerIntegration:
    """Integration tests for ModelManager on-demand loading."""

    @pytest.mark.asyncio
    async def test_model_manager_load_context_manager(self):
        """Test ModelManager load using async context manager."""
        from backend.services.model_zoo import get_model_manager

        manager = get_model_manager()
        sentinel = {"model": MagicMock(), "processor": MagicMock()}

        with _stub_load("yolo11-license-plate", sentinel):
            async with manager.load("yolo11-license-plate") as model:
                assert model is sentinel

            # Model should be unloaded after context exit
            status = manager.get_status()
            assert "yolo11-license-plate" not in status["loaded_models"]

    @pytest.mark.asyncio
    async def test_model_manager_reference_counting(self):
        """Test ModelManager tracks reference counts correctly."""
        from backend.services.model_zoo import get_model_manager

        manager = get_model_manager()
        sentinel = MagicMock()

        with _stub_load("yolo11-license-plate", sentinel):
            # Load model twice (simulating concurrent use)
            async with manager.load("yolo11-license-plate") as model1:
                assert model1 is sentinel

                async with manager.load("yolo11-license-plate") as model2:
                    # Should return same model instance
                    assert model2 is model1

                    status = manager.get_status()
                    assert "yolo11-license-plate" in status["loaded_models"]
                    # Reference count should be 2
                    assert status["load_counts"]["yolo11-license-plate"] == 2

                # After first release, ref count should be 1
                status = manager.get_status()
                assert status["load_counts"]["yolo11-license-plate"] == 1

            # After all releases, model should be unloaded
            status = manager.get_status()
            assert "yolo11-license-plate" not in status["loaded_models"]

    @pytest.mark.asyncio
    async def test_model_manager_vram_tracking(self):
        """Test ModelManager tracks total VRAM usage."""
        from backend.services.model_zoo import get_model_manager

        manager = get_model_manager()
        plate_vram = get_model_zoo()["yolo11-license-plate"].vram_mb

        with _stub_load("yolo11-license-plate", MagicMock()):
            async with manager.load("yolo11-license-plate"):
                status = manager.get_status()
                assert status["total_loaded_vram_mb"] == plate_vram  # the row's own budget

    @pytest.mark.asyncio
    async def test_model_manager_concurrent_loads_different_models(self):
        """Test ModelManager handles concurrent loads of different models."""
        from backend.services.model_zoo import get_model_manager

        zoo = get_model_zoo()
        manager = get_model_manager()

        with (
            _stub_load("yolo11-license-plate", MagicMock()),
            _stub_load("yolo11-face", MagicMock()),
        ):
            async with manager.load("yolo11-license-plate") as plate_model:
                assert plate_model is not None

                async with manager.load("yolo11-face") as face_model:
                    assert face_model is not None

                    status = manager.get_status()
                    # Both models should be loaded
                    assert "yolo11-license-plate" in status["loaded_models"]
                    assert "yolo11-face" in status["loaded_models"]
                    # Total VRAM should be sum of both
                    assert status["total_loaded_vram_mb"] == (
                        zoo["yolo11-license-plate"].vram_mb + zoo["yolo11-face"].vram_mb
                    )

    @pytest.mark.asyncio
    async def test_model_manager_handles_load_error(self):
        """Test ModelManager handles model loading errors gracefully."""
        from backend.services.model_zoo import get_model_manager

        manager = get_model_manager()

        failing = MagicMock(side_effect=RuntimeError("Simulated loader failure"))
        with patch.object(get_model_zoo()["yolo11-license-plate"], "load_fn", failing):
            with pytest.raises(RuntimeError, match="Simulated loader failure"):
                async with manager.load("yolo11-license-plate"):
                    pass

        # Manager should remain in consistent state
        status = manager.get_status()
        assert "yolo11-license-plate" not in status["loaded_models"]

    @pytest.mark.asyncio
    async def test_model_manager_status_returns_correct_structure(self):
        """Test get_status returns properly structured data."""
        from backend.services.model_zoo import get_model_manager

        manager = get_model_manager()

        with _stub_load("yolo11-license-plate", MagicMock()):
            async with manager.load("yolo11-license-plate"):
                status = manager.get_status()

                assert "loaded_models" in status
                assert "total_loaded_vram_mb" in status
                assert "load_counts" in status
                assert isinstance(status["loaded_models"], list)
                assert isinstance(status["total_loaded_vram_mb"], int)
                assert isinstance(status["load_counts"], dict)


# =============================================================================
# Test Model Loader Error Handling
# =============================================================================


class TestModelLoaderErrorHandling:
    """Test error handling for the surviving loaders."""

    @pytest.mark.asyncio
    async def test_osnet_rejects_path_outside_the_allowlist(self) -> None:
        """NEM-4501: a path outside the allowed roots is refused before any
        stat or read, wrapped as the loader's RuntimeError."""
        with pytest.raises(RuntimeError, match="Invalid model path"):
            await load_osnet_model("/etc/shadow")

    @pytest.mark.asyncio
    async def test_osnet_missing_weights_error(self) -> None:
        """An allowed directory with no weights raises, not silently degrades."""
        with pytest.raises(RuntimeError, match="No model weights found"):
            await load_osnet_model("/tmp/osnet-absent-weights-dir")  # noqa: S108


# =============================================================================
# Test OSNet Loader Integration
# =============================================================================


class TestOSNetLoaderIntegration:
    """Integration tests for OSNet person re-ID model loader (functional API)."""

    @pytest.mark.asyncio
    async def test_osnet_load_success_with_torchreid(self, mock_transformers, monkeypatch):
        """Test OSNet model loads successfully with torchreid."""
        import sys

        # Mock torchvision
        mock_torchvision = MagicMock()
        mock_transforms = MagicMock()
        mock_torchvision.transforms = mock_transforms
        monkeypatch.setitem(sys.modules, "torchvision", mock_torchvision)
        monkeypatch.setitem(sys.modules, "torchvision.transforms", mock_transforms)

        # Mock torchreid
        mock_torchreid = MagicMock()
        mock_model = MagicMock()
        mock_model.parameters = MagicMock(return_value=iter([MagicMock()]))
        mock_model.eval = MagicMock(return_value=mock_model)
        # load_state_dict returns (missing_keys, unexpected_keys)
        mock_model.load_state_dict = MagicMock(return_value=([], []))
        mock_torchreid.models.build_model.return_value = mock_model

        monkeypatch.setitem(sys.modules, "torchreid", mock_torchreid)
        monkeypatch.setitem(sys.modules, "torchreid.models", mock_torchreid.models)

        # Mock Path.glob to return a weights file and torch.load
        # Use /tmp which is in allowed directories for security validation
        from unittest.mock import patch

        mock_weights = {"state_dict": {"conv1.weight": MagicMock()}}
        with (
            patch("pathlib.Path.exists", return_value=True, autospec=True),
            patch("pathlib.Path.glob", return_value=[MagicMock()], autospec=True),
            # No autospec: the mock_transformers fixture has already replaced
            # sys.modules["torch"] with a MagicMock, so the patch target's
            # parent IS a Mock -- create_autospec refuses (InvalidSpecError)
            # and there is no real signature to enforce anyway.
            patch("torch.load", return_value=mock_weights),
        ):
            result = await load_osnet_model("/tmp/osnet_model")  # noqa: S108

        assert result is not None
        assert "model" in result
        assert "transform" in result

    @pytest.mark.asyncio
    async def test_osnet_missing_weights_error(self, mock_transformers, monkeypatch):
        """Test OSNet loader raises error for missing weights."""
        import sys

        # Mock torchvision
        mock_torchvision = MagicMock()
        mock_transforms = MagicMock()
        mock_torchvision.transforms = mock_transforms
        monkeypatch.setitem(sys.modules, "torchvision", mock_torchvision)
        monkeypatch.setitem(sys.modules, "torchvision.transforms", mock_transforms)

        # Mock torchreid
        mock_torchreid = MagicMock()
        monkeypatch.setitem(sys.modules, "torchreid", mock_torchreid)
        monkeypatch.setitem(sys.modules, "torchreid.models", mock_torchreid.models)

        # Mock Path.glob to return no files and exists to return False
        from unittest.mock import patch

        with patch("pathlib.Path.exists", return_value=False, autospec=True):
            with patch("pathlib.Path.glob", return_value=[], autospec=True):
                with pytest.raises(RuntimeError, match="Failed to load OSNet"):
                    await load_osnet_model("/nonexistent/path")
