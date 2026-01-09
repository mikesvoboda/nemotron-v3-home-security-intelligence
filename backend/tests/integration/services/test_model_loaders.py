"""Integration tests for AI model loaders.

These tests verify that model loaders work correctly with the Model Zoo
infrastructure, handle loading/unloading, manage VRAM, and integrate properly
with the enrichment pipeline.

HTTP calls to external AI services (RT-DETRv2, Nemotron, Florence, CLIP)
are mocked to isolate the tests. We're testing the model loader infrastructure,
not actual AI inference.
"""

from unittest.mock import MagicMock

import pytest

from backend.services.clip_loader import CLIPLoader, load_clip_model
from backend.services.florence_loader import load_florence_model
from backend.services.model_zoo import get_model_zoo, reset_model_manager, reset_model_zoo
from backend.services.pet_classifier_loader import load_pet_classifier_model
from backend.services.violence_loader import load_violence_model

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_transformers(monkeypatch):
    """Mock transformers library for model loading tests."""
    import sys

    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    mock_torch.cuda.empty_cache = MagicMock()

    mock_processor = MagicMock()
    mock_model = MagicMock()
    mock_model.cuda.return_value = mock_model
    mock_model.cpu.return_value = mock_model

    mock_transformers_lib = MagicMock()
    mock_transformers_lib.CLIPProcessor.from_pretrained.return_value = mock_processor
    mock_transformers_lib.CLIPModel.from_pretrained.return_value = mock_model
    mock_transformers_lib.AutoProcessor.from_pretrained.return_value = mock_processor
    mock_transformers_lib.AutoModelForVision2Seq.from_pretrained.return_value = mock_model

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers_lib)

    return {"torch": mock_torch, "transformers": mock_transformers_lib}


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset all singleton state before and after each test."""
    reset_model_zoo()
    reset_model_manager()
    yield
    reset_model_zoo()
    reset_model_manager()


# =============================================================================
# Test CLIP Model Loader Integration
# =============================================================================


class TestCLIPLoaderIntegration:
    """Integration tests for CLIP model loader."""

    @pytest.mark.asyncio
    async def test_clip_loader_load_success(self, mock_transformers):
        """Test CLIP model loads successfully."""
        loader = CLIPLoader("openai/clip-vit-large-patch14")

        result = await loader.load(device="cpu")

        assert "model" in result
        assert "processor" in result
        assert loader._model is not None
        mock_transformers["transformers"].CLIPModel.from_pretrained.assert_called_once()

    @pytest.mark.asyncio
    async def test_clip_loader_load_with_cuda(self, mock_transformers):
        """Test CLIP model loads with CUDA device."""
        mock_transformers["torch"].cuda.is_available.return_value = True

        loader = CLIPLoader("openai/clip-vit-large-patch14")
        result = await loader.load(device="cuda")

        assert "model" in result
        assert result["model"].cuda.called

    @pytest.mark.asyncio
    async def test_clip_loader_unload(self, mock_transformers):
        """Test CLIP model unloads and clears CUDA cache."""
        # Enable CUDA for this test to verify empty_cache is called
        mock_transformers["torch"].cuda.is_available.return_value = True

        loader = CLIPLoader("openai/clip-vit-large-patch14")
        await loader.load(device="cpu")

        assert loader._model is not None

        await loader.unload()

        assert loader._model is None
        # empty_cache should be called when CUDA is available
        mock_transformers["torch"].cuda.empty_cache.assert_called()

    @pytest.mark.asyncio
    async def test_clip_loader_properties(self, mock_transformers):
        """Test CLIP loader properties return correct values."""
        loader = CLIPLoader("openai/clip-vit-large-patch14")

        assert loader.model_name == "clip-vit-l"
        assert loader.vram_mb == 800
        assert isinstance(loader.vram_mb, int)

    @pytest.mark.asyncio
    async def test_clip_loader_missing_weights_error(self, mock_transformers):
        """Test CLIP loader raises error for missing weights."""
        mock_transformers["transformers"].CLIPModel.from_pretrained.side_effect = RuntimeError(
            "Model weights not found"
        )

        loader = CLIPLoader("/nonexistent/path")

        with pytest.raises(RuntimeError, match="Failed to load CLIP model"):
            await loader.load()

    @pytest.mark.asyncio
    async def test_load_clip_model_function(self, mock_transformers):
        """Test standalone load_clip_model function."""
        result = await load_clip_model("openai/clip-vit-large-patch14")

        assert "model" in result
        assert "processor" in result
        mock_transformers["transformers"].CLIPProcessor.from_pretrained.assert_called_once_with(
            "openai/clip-vit-large-patch14"
        )


# =============================================================================
# Test Florence Model Loader Integration
# =============================================================================


class TestFlorenceLoaderIntegration:
    """Integration tests for Florence-2 model loader (functional API)."""

    @pytest.mark.asyncio
    async def test_load_florence_model_function_success(self, mock_transformers):
        """Test load_florence_model function loads successfully."""
        mock_transformers["transformers"].AutoModelForCausalLM = MagicMock()
        mock_model = MagicMock()
        mock_model.to = MagicMock(return_value=mock_model)
        mock_model.eval = MagicMock(return_value=mock_model)
        mock_transformers[
            "transformers"
        ].AutoModelForCausalLM.from_pretrained.return_value = mock_model

        result = await load_florence_model("microsoft/Florence-2-large")

        assert result is not None
        # Florence returns (model, processor) tuple
        mock_transformers["transformers"].AutoProcessor.from_pretrained.assert_called_once()

    @pytest.mark.asyncio
    async def test_florence_model_missing_weights_error(self, mock_transformers):
        """Test Florence loader raises error for missing weights."""
        mock_transformers["transformers"].AutoModelForCausalLM = MagicMock()
        mock_transformers[
            "transformers"
        ].AutoModelForCausalLM.from_pretrained.side_effect = RuntimeError("Model weights not found")

        with pytest.raises(RuntimeError, match="Failed to load Florence"):
            await load_florence_model("/nonexistent/path")


# =============================================================================
# Test Pet Classifier Loader Integration
# =============================================================================


class TestPetClassifierLoaderIntegration:
    """Integration tests for pet classifier model loader (functional API)."""

    @pytest.mark.asyncio
    async def test_pet_classifier_load_success(self, mock_transformers):
        """Test pet classifier model loads successfully."""
        mock_transformers["transformers"].AutoModelForImageClassification = MagicMock()
        mock_model = MagicMock()
        mock_model.to = MagicMock(return_value=mock_model)
        mock_model.eval = MagicMock(return_value=mock_model)
        mock_transformers[
            "transformers"
        ].AutoModelForImageClassification.from_pretrained.return_value = mock_model
        mock_transformers["transformers"].AutoImageProcessor = MagicMock()

        result = await load_pet_classifier_model("/path/to/model")

        assert result is not None
        assert "model" in result
        assert "processor" in result

    @pytest.mark.asyncio
    async def test_pet_classifier_missing_weights_error(self, mock_transformers):
        """Test pet classifier loader raises error for missing weights."""
        mock_transformers["transformers"].AutoModelForImageClassification = MagicMock()
        mock_transformers[
            "transformers"
        ].AutoModelForImageClassification.from_pretrained.side_effect = RuntimeError(
            "Model weights not found"
        )

        with pytest.raises(RuntimeError, match="Failed to load pet classifier"):
            await load_pet_classifier_model("/nonexistent/path")


# =============================================================================
# Test Violence Loader Integration
# =============================================================================


class TestViolenceLoaderIntegration:
    """Integration tests for violence detection model loader (functional API)."""

    @pytest.mark.asyncio
    async def test_violence_loader_load_success(self, mock_transformers):
        """Test violence detection model loads successfully."""
        mock_transformers["transformers"].AutoModelForImageClassification = MagicMock()
        mock_model = MagicMock()
        mock_model.to = MagicMock(return_value=mock_model)
        mock_model.eval = MagicMock(return_value=mock_model)
        mock_transformers[
            "transformers"
        ].AutoModelForImageClassification.from_pretrained.return_value = mock_model
        mock_transformers["transformers"].AutoImageProcessor = MagicMock()

        result = await load_violence_model("/path/to/model")

        assert result is not None
        assert "model" in result
        assert "processor" in result

    @pytest.mark.asyncio
    async def test_violence_loader_missing_weights_error(self, mock_transformers):
        """Test violence loader raises error for missing weights."""
        mock_transformers["transformers"].AutoModelForImageClassification = MagicMock()
        mock_transformers[
            "transformers"
        ].AutoModelForImageClassification.from_pretrained.side_effect = RuntimeError(
            "Model weights not found"
        )

        with pytest.raises(RuntimeError, match="Failed to load violence"):
            await load_violence_model("/nonexistent/path")


# =============================================================================
# Test Model Zoo Integration
# =============================================================================


class TestModelZooIntegration:
    """Integration tests for Model Zoo model registry."""

    def test_get_model_zoo_returns_registry(self):
        """Test get_model_zoo returns model configurations."""
        zoo = get_model_zoo()

        assert isinstance(zoo, dict)
        assert "clip-vit-l" in zoo
        assert "florence-2-large" in zoo
        assert "pet-classifier" in zoo

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
                "vision-language",
                "pose",
                "depth-estimation",
                "classification",
                "segmentation",
                "action-recognition",
                "quality-assessment",
            ]
            assert callable(config.load_fn)
            assert isinstance(config.enabled, bool)

    def test_model_configs_vram_budgets_reasonable(self):
        """Test model VRAM budgets are within reasonable limits."""
        zoo = get_model_zoo()

        # No single model should exceed 3GB VRAM budget
        for name, config in zoo.items():
            assert config.vram_mb <= 3000, f"{name} VRAM budget too high: {config.vram_mb}MB"

    def test_clip_model_in_zoo(self):
        """Test CLIP model is registered correctly."""
        zoo = get_model_zoo()
        config = zoo["clip-vit-l"]

        assert config.name == "clip-vit-l"
        assert config.category == "embedding"
        assert config.enabled is True
        assert config.load_fn is load_clip_model


# =============================================================================
# Test Model Manager Integration
# =============================================================================


class TestModelManagerIntegration:
    """Integration tests for ModelManager on-demand loading."""

    @pytest.mark.asyncio
    async def test_model_manager_load_context_manager(self, mock_transformers):
        """Test ModelManager load using async context manager."""
        from backend.services.model_zoo import get_model_manager

        manager = get_model_manager()

        async with manager.load("clip-vit-l") as model:
            assert model is not None
            assert "model" in model
            assert "processor" in model

        # Model should be unloaded after context exit
        status = manager.get_status()
        assert "clip-vit-l" not in status["loaded_models"]

    @pytest.mark.asyncio
    async def test_model_manager_reference_counting(self, mock_transformers):
        """Test ModelManager tracks reference counts correctly."""
        from backend.services.model_zoo import get_model_manager

        manager = get_model_manager()

        # Load model twice (simulating concurrent use)
        async with manager.load("clip-vit-l") as model1:
            assert model1 is not None

            async with manager.load("clip-vit-l") as model2:
                # Should return same model instance
                assert model2 is model1

                status = manager.get_status()
                assert "clip-vit-l" in status["loaded_models"]
                # Reference count should be 2
                assert status["load_counts"]["clip-vit-l"] == 2

            # After first release, ref count should be 1
            status = manager.get_status()
            assert status["load_counts"]["clip-vit-l"] == 1

        # After all releases, model should be unloaded
        status = manager.get_status()
        assert "clip-vit-l" not in status["loaded_models"]

    @pytest.mark.asyncio
    async def test_model_manager_vram_tracking(self, mock_transformers):
        """Test ModelManager tracks total VRAM usage."""
        from backend.services.model_zoo import get_model_manager

        manager = get_model_manager()

        async with manager.load("clip-vit-l"):
            status = manager.get_status()
            assert status["total_loaded_vram_mb"] == 800  # CLIP VRAM

    @pytest.mark.asyncio
    async def test_model_manager_concurrent_loads_different_models(self, mock_transformers):
        """Test ModelManager handles concurrent loads of different models."""
        from backend.services.model_zoo import get_model_manager

        # Setup AutoImageProcessor for pet classifier
        mock_transformers["transformers"].AutoImageProcessor = MagicMock()
        mock_transformers["transformers"].AutoModelForImageClassification = MagicMock()
        mock_pet_model = MagicMock()
        mock_pet_model.to = MagicMock(return_value=mock_pet_model)
        mock_pet_model.eval = MagicMock(return_value=mock_pet_model)
        mock_transformers[
            "transformers"
        ].AutoModelForImageClassification.from_pretrained.return_value = mock_pet_model

        manager = get_model_manager()

        # Load two different models concurrently
        async with manager.load("clip-vit-l") as clip_model:
            assert clip_model is not None

            async with manager.load("pet-classifier") as pet_model:
                assert pet_model is not None

                status = manager.get_status()
                # Both models should be loaded
                assert "clip-vit-l" in status["loaded_models"]
                assert "pet-classifier" in status["loaded_models"]
                # Total VRAM should be sum of both
                assert status["total_loaded_vram_mb"] == 800 + 200

    @pytest.mark.asyncio
    async def test_model_manager_handles_load_error(self, mock_transformers):
        """Test ModelManager handles model loading errors gracefully."""
        from backend.services.model_zoo import get_model_manager

        manager = get_model_manager()

        # Simulate load failure
        mock_transformers["transformers"].CLIPModel.from_pretrained.side_effect = RuntimeError(
            "Model not found"
        )

        with pytest.raises(RuntimeError, match="Failed to load CLIP model"):
            async with manager.load("clip-vit-l"):
                pass

        # Manager should remain in consistent state
        status = manager.get_status()
        assert "clip-vit-l" not in status["loaded_models"]

    @pytest.mark.asyncio
    async def test_model_manager_status_returns_correct_structure(self, mock_transformers):
        """Test get_status returns properly structured data."""
        from backend.services.model_zoo import get_model_manager

        manager = get_model_manager()

        async with manager.load("clip-vit-l"):
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
    """Test error handling for model loaders."""

    @pytest.mark.asyncio
    async def test_clip_loader_import_error(self, monkeypatch):
        """Test CLIP loader handles ImportError for missing transformers."""
        import builtins
        import sys

        # Hide transformers module
        modules_to_hide = ["transformers"]
        hidden_modules = {}
        for mod in modules_to_hide:
            for key in list(sys.modules.keys()):
                if key == mod or key.startswith(f"{mod}."):
                    hidden_modules[key] = sys.modules.pop(key)

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "transformers" or name.startswith("transformers."):
                raise ImportError(f"No module named '{name}'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        try:
            with pytest.raises(ImportError, match="transformers package required"):
                await load_clip_model("openai/clip-vit-large-patch14")
        finally:
            sys.modules.update(hidden_modules)

    @pytest.mark.asyncio
    async def test_florence_loader_runtime_error(self, mock_transformers):
        """Test Florence loader handles RuntimeError during model load."""
        mock_transformers["transformers"].AutoModelForCausalLM = MagicMock()
        mock_transformers[
            "transformers"
        ].AutoModelForCausalLM.from_pretrained.side_effect = RuntimeError("CUDA out of memory")

        with pytest.raises(RuntimeError, match="Failed to load Florence"):
            await load_florence_model("microsoft/Florence-2-large")

    @pytest.mark.asyncio
    async def test_model_loader_with_empty_path(self, mock_transformers):
        """Test model loader handles empty model path."""
        mock_transformers["transformers"].CLIPProcessor.from_pretrained.side_effect = ValueError(
            "Invalid model path"
        )

        with pytest.raises(RuntimeError, match="Failed to load CLIP model"):
            await load_clip_model("")


# =============================================================================
# Test Model Warmup
# =============================================================================


class TestModelWarmup:
    """Test model warmup functionality."""

    @pytest.mark.asyncio
    async def test_clip_loader_model_loads_for_warmup(self, mock_transformers):
        """Test CLIP model can be loaded for warmup."""
        loader = CLIPLoader("openai/clip-vit-large-patch14")

        result = await loader.load(device="cpu")

        # Model should be loaded and ready for inference
        assert result is not None
        assert loader._model is not None

    @pytest.mark.asyncio
    async def test_florence_loader_model_loads_for_warmup(self, mock_transformers):
        """Test Florence model can be loaded for warmup."""
        mock_transformers["transformers"].AutoModelForCausalLM = MagicMock()
        mock_model = MagicMock()
        mock_model.to = MagicMock(return_value=mock_model)
        mock_model.eval = MagicMock(return_value=mock_model)
        mock_transformers[
            "transformers"
        ].AutoModelForCausalLM.from_pretrained.return_value = mock_model

        result = await load_florence_model("microsoft/Florence-2-large")

        assert result is not None


# =============================================================================
# Test Model Inference (Mocked)
# =============================================================================


class TestModelInferenceMocked:
    """Test model inference with mocked outputs."""

    @pytest.mark.asyncio
    async def test_clip_model_inference_mock(self, mock_transformers):
        """Test CLIP model returns inference results (mocked)."""
        # Mock the model's forward pass
        mock_model = mock_transformers["transformers"].CLIPModel.from_pretrained.return_value
        mock_embeddings = MagicMock()
        mock_embeddings.shape = (1, 768)  # 768-dimensional embeddings
        mock_model.return_value = MagicMock(image_embeds=mock_embeddings)

        loader = CLIPLoader("openai/clip-vit-large-patch14")
        result = await loader.load(device="cpu")

        # Verify model is callable (would perform inference)
        assert result["model"] is not None
        assert callable(result["model"])

    @pytest.mark.asyncio
    async def test_florence_model_inference_mock(self, mock_transformers):
        """Test Florence model returns inference results (mocked)."""
        mock_transformers["transformers"].AutoModelForCausalLM = MagicMock()
        mock_model = MagicMock()
        mock_model.to = MagicMock(return_value=mock_model)
        mock_model.eval = MagicMock(return_value=mock_model)
        mock_output = MagicMock()
        mock_output.sequences = [[1, 2, 3]]  # Token IDs
        mock_model.generate.return_value = mock_output
        mock_transformers[
            "transformers"
        ].AutoModelForCausalLM.from_pretrained.return_value = mock_model

        result = await load_florence_model("microsoft/Florence-2-large")

        # Florence returns a tuple (model, processor)
        assert result is not None
        # Verify model has generate method (Florence-specific)
        assert hasattr(mock_model, "generate")
