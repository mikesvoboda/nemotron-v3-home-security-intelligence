# ruff: noqa: ARG005
"""Unit tests for OSNet person re-identification loader.

Tests cover:
- PersonEmbeddingResult dataclass
- load_osnet_model function
- extract_person_embedding function
- extract_person_embeddings_batch function
- match_person_embeddings function
- format_person_reid_context function
"""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from backend.services.osnet_loader import (
    OSNET_EMBEDDING_DIM,
    PersonEmbeddingResult,
    extract_person_embedding,
    extract_person_embeddings_batch,
    format_person_reid_context,
    load_osnet_model,
    match_person_embeddings,
)


class TestPersonEmbeddingResult:
    """Tests for PersonEmbeddingResult dataclass."""

    def test_create_result_with_defaults(self) -> None:
        """Test creating PersonEmbeddingResult with default values."""
        embedding = np.random.rand(OSNET_EMBEDDING_DIM)
        result = PersonEmbeddingResult(embedding=embedding)

        assert result.embedding.shape == (OSNET_EMBEDDING_DIM,)
        assert result.detection_id is None
        assert result.confidence == 1.0

    def test_create_result_with_all_fields(self) -> None:
        """Test creating PersonEmbeddingResult with all fields."""
        embedding = np.random.rand(OSNET_EMBEDDING_DIM)
        result = PersonEmbeddingResult(embedding=embedding, detection_id="det-123", confidence=0.85)

        assert result.embedding.shape == (OSNET_EMBEDDING_DIM,)
        assert result.detection_id == "det-123"
        assert result.confidence == 0.85

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        embedding = np.ones(OSNET_EMBEDDING_DIM) * 0.5
        result = PersonEmbeddingResult(embedding=embedding, detection_id="det-456", confidence=0.9)

        d = result.to_dict()

        assert "embedding" in d
        assert "detection_id" in d
        assert "confidence" in d
        assert "embedding_dim" in d
        assert d["detection_id"] == "det-456"
        assert d["confidence"] == 0.9
        assert d["embedding_dim"] == OSNET_EMBEDDING_DIM
        assert len(d["embedding"]) == OSNET_EMBEDDING_DIM

    def test_cosine_similarity_identical(self) -> None:
        """Test cosine similarity with identical embeddings."""
        embedding = np.random.rand(OSNET_EMBEDDING_DIM)
        embedding = embedding / np.linalg.norm(embedding)  # Normalize

        result1 = PersonEmbeddingResult(embedding=embedding)
        result2 = PersonEmbeddingResult(embedding=embedding)

        similarity = result1.cosine_similarity(result2)

        assert 0.99 < similarity <= 1.0  # Should be very close to 1.0

    def test_cosine_similarity_orthogonal(self) -> None:
        """Test cosine similarity with orthogonal embeddings."""
        # Create two orthogonal vectors
        embedding1 = np.zeros(OSNET_EMBEDDING_DIM)
        embedding1[0] = 1.0

        embedding2 = np.zeros(OSNET_EMBEDDING_DIM)
        embedding2[1] = 1.0

        result1 = PersonEmbeddingResult(embedding=embedding1)
        result2 = PersonEmbeddingResult(embedding=embedding2)

        similarity = result1.cosine_similarity(result2)

        assert abs(similarity) < 0.01  # Should be close to 0

    def test_cosine_similarity_opposite(self) -> None:
        """Test cosine similarity with opposite embeddings."""
        embedding1 = np.ones(OSNET_EMBEDDING_DIM)
        embedding1 = embedding1 / np.linalg.norm(embedding1)

        embedding2 = -embedding1

        result1 = PersonEmbeddingResult(embedding=embedding1)
        result2 = PersonEmbeddingResult(embedding=embedding2)

        similarity = result1.cosine_similarity(result2)

        assert -1.0 <= similarity < -0.99  # Should be close to -1.0


class TestLoadOSNetModel:
    """Tests for load_osnet_model function."""

    @pytest.mark.asyncio
    async def test_load_osnet_model_import_error(self, monkeypatch) -> None:
        """Test load_osnet_model handles ImportError when torch is not available."""
        import builtins
        import sys

        # Remove torch from imports if present
        modules_to_hide = ["torch", "torchvision"]
        hidden_modules = {}
        for mod in modules_to_hide:
            for key in list(sys.modules.keys()):
                if key == mod or key.startswith(f"{mod}."):
                    hidden_modules[key] = sys.modules.pop(key)

        # Mock import to raise ImportError
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "torch" or name.startswith("torch."):
                raise ImportError(f"No module named '{name}'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        try:
            with pytest.raises(ImportError, match="OSNet requires torch and torchvision"):
                await load_osnet_model("/fake/path")
        finally:
            sys.modules.update(hidden_modules)

    @pytest.mark.asyncio
    async def test_load_osnet_model_file_not_found(self, monkeypatch) -> None:
        """Test load_osnet_model handles FileNotFoundError when weights not found."""
        import sys
        from pathlib import Path

        # Create mock torch
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        # Create mock torchvision
        mock_torchvision = MagicMock()
        mock_transforms = MagicMock()
        mock_torchvision.transforms = mock_transforms

        # Create mock torchreid
        mock_torchreid = MagicMock()
        mock_build_model = MagicMock()
        mock_torchreid.models.build_model = mock_build_model
        mock_build_model.return_value = MagicMock()

        # Mock Path.glob to return empty list (no .pth files)
        mock_path = MagicMock(spec=Path)
        mock_path.glob.return_value = []
        mock_path.__truediv__ = lambda self, other: mock_path
        mock_path.exists.return_value = False

        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "torchvision", mock_torchvision)
        monkeypatch.setitem(sys.modules, "torchvision.transforms", mock_transforms)
        monkeypatch.setitem(sys.modules, "torchreid", mock_torchreid)
        monkeypatch.setitem(sys.modules, "torchreid.models", mock_torchreid.models)
        monkeypatch.setattr("backend.services.osnet_loader.Path", lambda x: mock_path)

        with pytest.raises(RuntimeError, match="Failed to load OSNet model"):
            await load_osnet_model("/fake/path")

    @pytest.mark.asyncio
    async def test_load_osnet_model_success_cpu(self, monkeypatch) -> None:
        """Test load_osnet_model success path with CPU (no CUDA)."""
        import sys
        from pathlib import Path

        # Create mock torch
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        mock_torch.load.return_value = {"conv1.weight": MagicMock()}

        # Create mock model
        mock_model = MagicMock()
        mock_model.eval.return_value = None
        mock_model.load_state_dict.return_value = None

        # Create mock torchreid
        mock_torchreid = MagicMock()
        mock_torchreid.models.build_model.return_value = mock_model

        # Create mock transforms
        mock_transforms = MagicMock()
        mock_compose = MagicMock()
        mock_transforms.Compose.return_value = mock_compose

        # Mock Path to return existing file
        mock_path = MagicMock(spec=Path)
        mock_weights_file = MagicMock()
        mock_weights_file.exists.return_value = True
        mock_path.__truediv__ = lambda self, other: mock_weights_file
        mock_path.glob.return_value = [mock_weights_file]

        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "torchreid", mock_torchreid)
        monkeypatch.setitem(sys.modules, "torchreid.models", mock_torchreid.models)
        monkeypatch.setitem(sys.modules, "torchvision", MagicMock())
        monkeypatch.setitem(sys.modules, "torchvision.transforms", mock_transforms)
        monkeypatch.setattr("backend.services.osnet_loader.Path", lambda x: mock_path)

        result = await load_osnet_model("/test/model")

        assert "model" in result
        assert "transform" in result
        mock_model.eval.assert_called_once()
        mock_model.cuda.assert_not_called()

    @pytest.mark.asyncio
    async def test_load_osnet_model_success_cuda(self, monkeypatch) -> None:
        """Test load_osnet_model success path with CUDA."""
        import sys
        from pathlib import Path

        # Create mock torch with CUDA
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        mock_torch.load.return_value = {"conv1.weight": MagicMock()}

        # Create mock model that supports cuda()
        mock_cuda_model = MagicMock()
        mock_cuda_model.eval.return_value = None

        mock_model = MagicMock()
        mock_model.cuda.return_value = mock_cuda_model
        mock_model.load_state_dict.return_value = None

        # Create mock torchreid
        mock_torchreid = MagicMock()
        mock_torchreid.models.build_model.return_value = mock_model

        # Create mock transforms
        mock_transforms = MagicMock()
        mock_compose = MagicMock()
        mock_transforms.Compose.return_value = mock_compose

        # Mock Path to return existing file
        mock_path = MagicMock(spec=Path)
        mock_weights_file = MagicMock()
        mock_weights_file.exists.return_value = True
        mock_path.__truediv__ = lambda self, other: mock_weights_file

        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "torchreid", mock_torchreid)
        monkeypatch.setitem(sys.modules, "torchreid.models", mock_torchreid.models)
        monkeypatch.setitem(sys.modules, "torchvision", MagicMock())
        monkeypatch.setitem(sys.modules, "torchvision.transforms", mock_transforms)
        monkeypatch.setattr("backend.services.osnet_loader.Path", lambda x: mock_path)

        result = await load_osnet_model("/test/model")

        assert "model" in result
        assert "transform" in result
        mock_model.cuda.assert_called_once()
        mock_cuda_model.eval.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_osnet_model_module_prefix_stripping(self, monkeypatch) -> None:
        """Test load_osnet_model strips 'module.' prefix from state dict keys."""
        import sys
        from pathlib import Path

        # Create state dict with 'module.' prefix (from DataParallel training)
        state_dict_with_prefix = {
            "module.conv1.weight": MagicMock(),
            "module.layer1.0.weight": MagicMock(),
        }

        # Create mock torch
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        mock_torch.load.return_value = state_dict_with_prefix

        # Create mock model
        mock_model = MagicMock()
        mock_model.eval.return_value = None

        # Capture the state dict passed to load_state_dict
        loaded_state_dict = None

        def capture_state_dict(sd, strict=True):
            nonlocal loaded_state_dict
            loaded_state_dict = sd

        mock_model.load_state_dict.side_effect = capture_state_dict

        # Create mock torchreid
        mock_torchreid = MagicMock()
        mock_torchreid.models.build_model.return_value = mock_model

        # Create mock transforms
        mock_transforms = MagicMock()
        mock_transforms.Compose.return_value = MagicMock()

        # Mock Path
        mock_path = MagicMock(spec=Path)
        mock_weights_file = MagicMock()
        mock_weights_file.exists.return_value = True
        mock_path.__truediv__ = lambda self, other: mock_weights_file

        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "torchreid", mock_torchreid)
        monkeypatch.setitem(sys.modules, "torchreid.models", mock_torchreid.models)
        monkeypatch.setitem(sys.modules, "torchvision", MagicMock())
        monkeypatch.setitem(sys.modules, "torchvision.transforms", mock_transforms)
        monkeypatch.setattr("backend.services.osnet_loader.Path", lambda x: mock_path)

        await load_osnet_model("/test/model")

        # Verify 'module.' prefix was stripped
        assert loaded_state_dict is not None
        assert "conv1.weight" in loaded_state_dict
        assert "layer1.0.weight" in loaded_state_dict
        assert "module.conv1.weight" not in loaded_state_dict

    @pytest.mark.asyncio
    async def test_load_osnet_model_classifier_keys_filtered(self, monkeypatch) -> None:
        """Test load_osnet_model filters out classifier keys to avoid shape mismatch."""
        import sys
        from pathlib import Path

        # Create state dict with classifier keys
        state_dict_with_classifier = {
            "conv1.weight": MagicMock(),
            "classifier.weight": MagicMock(),
            "classifier.bias": MagicMock(),
        }

        # Create mock torch
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        mock_torch.load.return_value = state_dict_with_classifier

        # Create mock model
        mock_model = MagicMock()
        mock_model.eval.return_value = None

        # Capture the state dict passed to load_state_dict
        loaded_state_dict = None

        def capture_state_dict(sd, strict=True):
            nonlocal loaded_state_dict
            loaded_state_dict = sd

        mock_model.load_state_dict.side_effect = capture_state_dict

        # Create mock torchreid
        mock_torchreid = MagicMock()
        mock_torchreid.models.build_model.return_value = mock_model

        # Create mock transforms
        mock_transforms = MagicMock()
        mock_transforms.Compose.return_value = MagicMock()

        # Mock Path
        mock_path = MagicMock(spec=Path)
        mock_weights_file = MagicMock()
        mock_weights_file.exists.return_value = True
        mock_path.__truediv__ = lambda self, other: mock_weights_file

        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "torchreid", mock_torchreid)
        monkeypatch.setitem(sys.modules, "torchreid.models", mock_torchreid.models)
        monkeypatch.setitem(sys.modules, "torchvision", MagicMock())
        monkeypatch.setitem(sys.modules, "torchvision.transforms", mock_transforms)
        monkeypatch.setattr("backend.services.osnet_loader.Path", lambda x: mock_path)

        await load_osnet_model("/test/model")

        # Verify classifier keys were filtered out
        assert loaded_state_dict is not None
        assert "conv1.weight" in loaded_state_dict
        assert "classifier.weight" not in loaded_state_dict
        assert "classifier.bias" not in loaded_state_dict

    @pytest.mark.asyncio
    async def test_load_osnet_model_fallback_torchscript(self, monkeypatch) -> None:
        """Test load_osnet_model fallback to TorchScript when torchreid unavailable."""
        import sys
        from pathlib import Path

        # Create mock torch
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        # Mock TorchScript model
        mock_ts_model = MagicMock()
        mock_ts_model.eval.return_value = None
        mock_torch.jit.load.return_value = mock_ts_model

        # Create mock transforms
        mock_transforms = MagicMock()
        mock_transforms.Compose.return_value = MagicMock()

        # Mock Path
        mock_path = MagicMock(spec=Path)
        mock_weights_file = MagicMock()
        mock_weights_file.exists.return_value = True
        mock_path.__truediv__ = lambda self, other: mock_weights_file

        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "torchvision", MagicMock())
        monkeypatch.setitem(sys.modules, "torchvision.transforms", mock_transforms)
        monkeypatch.setattr("backend.services.osnet_loader.Path", lambda x: mock_path)

        # Remove torchreid if present
        if "torchreid" in sys.modules:
            del sys.modules["torchreid"]

        result = await load_osnet_model("/test/model")

        assert "model" in result
        assert "transform" in result
        mock_torch.jit.load.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_osnet_model_no_torchreid_no_torchscript(self, monkeypatch) -> None:
        """Test load_osnet_model raises error when neither torchreid nor TorchScript available."""
        import sys
        from pathlib import Path

        # Create mock torch
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        mock_torch.jit.load.side_effect = RuntimeError("Not a TorchScript model")

        # Mock Path
        mock_path = MagicMock(spec=Path)
        mock_weights_file = MagicMock()
        mock_weights_file.exists.return_value = True
        mock_path.__truediv__ = lambda self, other: mock_weights_file

        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "torchvision", MagicMock())
        monkeypatch.setattr("backend.services.osnet_loader.Path", lambda x: mock_path)

        # Remove torchreid if present
        if "torchreid" in sys.modules:
            del sys.modules["torchreid"]

        with pytest.raises(
            RuntimeError, match="OSNet requires either torchreid package or TorchScript"
        ):
            await load_osnet_model("/test/model")


class TestExtractPersonEmbedding:
    """Tests for extract_person_embedding function."""

    @pytest.mark.asyncio
    async def test_extract_person_embedding_success(self, monkeypatch) -> None:
        """Test extract_person_embedding success path."""
        import sys

        # Create mock torch
        mock_torch = MagicMock()
        mock_torch.inference_mode.return_value.__enter__ = MagicMock()
        mock_torch.inference_mode.return_value.__exit__ = MagicMock()

        # Create mock tensor
        mock_tensor = MagicMock()
        mock_tensor.unsqueeze.return_value = mock_tensor
        mock_tensor.to.return_value = mock_tensor

        # Create mock model output
        mock_output = MagicMock()
        mock_output.squeeze.return_value = MagicMock()
        mock_output.squeeze.return_value.cpu.return_value = MagicMock()
        mock_output.squeeze.return_value.cpu.return_value.numpy.return_value = np.random.rand(
            OSNET_EMBEDDING_DIM
        )

        # Create mock model
        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([MagicMock(device="cpu")])
        mock_model.return_value = mock_output

        # Create mock transform
        mock_transform = MagicMock()
        mock_transform.return_value = mock_tensor

        model_dict = {"model": mock_model, "transform": mock_transform}

        # Create mock image
        mock_image = MagicMock()
        mock_image.mode = "RGB"
        mock_image.size = (128, 256)

        monkeypatch.setitem(sys.modules, "torch", mock_torch)

        result = await extract_person_embedding(model_dict, mock_image)

        assert isinstance(result, PersonEmbeddingResult)
        assert result.embedding.shape == (OSNET_EMBEDDING_DIM,)
        assert result.confidence == 1.0  # Good size image

    @pytest.mark.asyncio
    async def test_extract_person_embedding_small_crop_low_confidence(self, monkeypatch) -> None:
        """Test extract_person_embedding with small crop returns low confidence."""
        import sys

        # Create mock torch
        mock_torch = MagicMock()
        mock_torch.inference_mode.return_value.__enter__ = MagicMock()
        mock_torch.inference_mode.return_value.__exit__ = MagicMock()

        # Create mock tensor and output
        mock_tensor = MagicMock()
        mock_tensor.unsqueeze.return_value = mock_tensor
        mock_tensor.to.return_value = mock_tensor

        mock_output = MagicMock()
        mock_output.squeeze.return_value = MagicMock()
        mock_output.squeeze.return_value.cpu.return_value = MagicMock()
        mock_output.squeeze.return_value.cpu.return_value.numpy.return_value = np.random.rand(
            OSNET_EMBEDDING_DIM
        )

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([MagicMock(device="cpu")])
        mock_model.return_value = mock_output

        mock_transform = MagicMock()
        mock_transform.return_value = mock_tensor

        model_dict = {"model": mock_model, "transform": mock_transform}

        # Create small image (< 32x64)
        mock_image = MagicMock()
        mock_image.mode = "RGB"
        mock_image.size = (20, 40)  # Very small

        monkeypatch.setitem(sys.modules, "torch", mock_torch)

        result = await extract_person_embedding(model_dict, mock_image)

        assert isinstance(result, PersonEmbeddingResult)
        assert result.confidence == 0.5  # Low confidence for small crop

    @pytest.mark.asyncio
    async def test_extract_person_embedding_medium_crop_medium_confidence(
        self, monkeypatch
    ) -> None:
        """Test extract_person_embedding with medium crop returns medium confidence."""
        import sys

        # Create mock torch
        mock_torch = MagicMock()
        mock_torch.inference_mode.return_value.__enter__ = MagicMock()
        mock_torch.inference_mode.return_value.__exit__ = MagicMock()

        mock_tensor = MagicMock()
        mock_tensor.unsqueeze.return_value = mock_tensor
        mock_tensor.to.return_value = mock_tensor

        mock_output = MagicMock()
        mock_output.squeeze.return_value = MagicMock()
        mock_output.squeeze.return_value.cpu.return_value = MagicMock()
        mock_output.squeeze.return_value.cpu.return_value.numpy.return_value = np.random.rand(
            OSNET_EMBEDDING_DIM
        )

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([MagicMock(device="cpu")])
        mock_model.return_value = mock_output

        mock_transform = MagicMock()
        mock_transform.return_value = mock_tensor

        model_dict = {"model": mock_model, "transform": mock_transform}

        # Create medium image (< 64x128)
        mock_image = MagicMock()
        mock_image.mode = "RGB"
        mock_image.size = (50, 100)

        monkeypatch.setitem(sys.modules, "torch", mock_torch)

        result = await extract_person_embedding(model_dict, mock_image)

        assert isinstance(result, PersonEmbeddingResult)
        assert result.confidence == 0.8  # Medium confidence

    @pytest.mark.asyncio
    async def test_extract_person_embedding_non_rgb_converted(self, monkeypatch) -> None:
        """Test extract_person_embedding converts non-RGB images to RGB."""
        import sys

        # Create mock torch
        mock_torch = MagicMock()
        mock_torch.inference_mode.return_value.__enter__ = MagicMock()
        mock_torch.inference_mode.return_value.__exit__ = MagicMock()

        mock_tensor = MagicMock()
        mock_tensor.unsqueeze.return_value = mock_tensor
        mock_tensor.to.return_value = mock_tensor

        mock_output = MagicMock()
        mock_output.squeeze.return_value = MagicMock()
        mock_output.squeeze.return_value.cpu.return_value = MagicMock()
        mock_output.squeeze.return_value.cpu.return_value.numpy.return_value = np.random.rand(
            OSNET_EMBEDDING_DIM
        )

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([MagicMock(device="cpu")])
        mock_model.return_value = mock_output

        mock_transform = MagicMock()
        mock_transform.return_value = mock_tensor

        model_dict = {"model": mock_model, "transform": mock_transform}

        # Create RGBA image (not RGB)
        mock_rgb_image = MagicMock()
        mock_rgb_image.size = (128, 256)

        mock_image = MagicMock()
        mock_image.mode = "RGBA"
        mock_image.convert.return_value = mock_rgb_image

        monkeypatch.setitem(sys.modules, "torch", mock_torch)

        result = await extract_person_embedding(model_dict, mock_image)

        assert isinstance(result, PersonEmbeddingResult)
        mock_image.convert.assert_called_once_with("RGB")

    @pytest.mark.asyncio
    async def test_extract_person_embedding_with_detection_id(self, monkeypatch) -> None:
        """Test extract_person_embedding includes detection_id when provided."""
        import sys

        mock_torch = MagicMock()
        mock_torch.inference_mode.return_value.__enter__ = MagicMock()
        mock_torch.inference_mode.return_value.__exit__ = MagicMock()

        mock_tensor = MagicMock()
        mock_tensor.unsqueeze.return_value = mock_tensor
        mock_tensor.to.return_value = mock_tensor

        mock_output = MagicMock()
        mock_output.squeeze.return_value = MagicMock()
        mock_output.squeeze.return_value.cpu.return_value = MagicMock()
        mock_output.squeeze.return_value.cpu.return_value.numpy.return_value = np.random.rand(
            OSNET_EMBEDDING_DIM
        )

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([MagicMock(device="cpu")])
        mock_model.return_value = mock_output

        mock_transform = MagicMock()
        mock_transform.return_value = mock_tensor

        model_dict = {"model": mock_model, "transform": mock_transform}

        mock_image = MagicMock()
        mock_image.mode = "RGB"
        mock_image.size = (128, 256)

        monkeypatch.setitem(sys.modules, "torch", mock_torch)

        result = await extract_person_embedding(model_dict, mock_image, detection_id="test-det-123")

        assert result.detection_id == "test-det-123"

    @pytest.mark.asyncio
    async def test_extract_person_embedding_error_handling(self, monkeypatch) -> None:
        """Test extract_person_embedding handles errors."""
        import sys

        mock_torch = MagicMock()

        mock_model = MagicMock()
        mock_model.parameters.side_effect = RuntimeError("Model error")

        model_dict = {"model": mock_model, "transform": MagicMock()}

        mock_image = MagicMock()
        mock_image.mode = "RGB"

        monkeypatch.setitem(sys.modules, "torch", mock_torch)

        with pytest.raises(RuntimeError, match="Person embedding extraction failed"):
            await extract_person_embedding(model_dict, mock_image)


class TestExtractPersonEmbeddingsBatch:
    """Tests for extract_person_embeddings_batch function."""

    @pytest.mark.asyncio
    async def test_extract_batch_empty_list(self) -> None:
        """Test extract_person_embeddings_batch with empty image list."""
        model_dict = {"model": MagicMock(), "transform": MagicMock()}

        result = await extract_person_embeddings_batch(model_dict, [])

        assert result == []

    @pytest.mark.asyncio
    async def test_extract_batch_multiple_images(self, monkeypatch) -> None:
        """Test extract_person_embeddings_batch with multiple images."""
        import sys

        # Create mock torch
        mock_torch = MagicMock()
        mock_torch.inference_mode.return_value.__enter__ = MagicMock()
        mock_torch.inference_mode.return_value.__exit__ = MagicMock()

        # Mock stack
        mock_stacked = MagicMock()
        mock_stacked.to.return_value = mock_stacked
        mock_torch.stack.return_value = mock_stacked

        # Create mock model output (batch of 2)
        mock_output = MagicMock()
        mock_output.cpu.return_value = MagicMock()
        mock_output.cpu.return_value.numpy.return_value = np.random.rand(2, OSNET_EMBEDDING_DIM)

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([MagicMock(device="cpu")])
        mock_model.return_value = mock_output

        mock_tensor = MagicMock()
        mock_transform = MagicMock()
        mock_transform.return_value = mock_tensor

        model_dict = {"model": mock_model, "transform": mock_transform}

        # Create two mock images
        mock_image1 = MagicMock()
        mock_image1.mode = "RGB"
        mock_image1.size = (128, 256)

        mock_image2 = MagicMock()
        mock_image2.mode = "RGB"
        mock_image2.size = (64, 128)

        monkeypatch.setitem(sys.modules, "torch", mock_torch)

        results = await extract_person_embeddings_batch(model_dict, [mock_image1, mock_image2])

        assert len(results) == 2
        assert all(isinstance(r, PersonEmbeddingResult) for r in results)
        assert results[0].confidence == 1.0  # Good size
        assert results[1].confidence == 1.0  # Medium size -> 1.0 (>= 64x128)

    @pytest.mark.asyncio
    async def test_extract_batch_with_detection_ids(self, monkeypatch) -> None:
        """Test extract_person_embeddings_batch with detection IDs."""
        import sys

        mock_torch = MagicMock()
        mock_torch.inference_mode.return_value.__enter__ = MagicMock()
        mock_torch.inference_mode.return_value.__exit__ = MagicMock()

        mock_stacked = MagicMock()
        mock_stacked.to.return_value = mock_stacked
        mock_torch.stack.return_value = mock_stacked

        mock_output = MagicMock()
        mock_output.cpu.return_value = MagicMock()
        mock_output.cpu.return_value.numpy.return_value = np.random.rand(2, OSNET_EMBEDDING_DIM)

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([MagicMock(device="cpu")])
        mock_model.return_value = mock_output

        mock_tensor = MagicMock()
        mock_transform = MagicMock()
        mock_transform.return_value = mock_tensor

        model_dict = {"model": mock_model, "transform": mock_transform}

        mock_image1 = MagicMock()
        mock_image1.mode = "RGB"
        mock_image1.size = (128, 256)

        mock_image2 = MagicMock()
        mock_image2.mode = "RGB"
        mock_image2.size = (128, 256)

        monkeypatch.setitem(sys.modules, "torch", mock_torch)

        results = await extract_person_embeddings_batch(
            model_dict, [mock_image1, mock_image2], detection_ids=["det1", "det2"]
        )

        assert len(results) == 2
        assert results[0].detection_id == "det1"
        assert results[1].detection_id == "det2"


class TestMatchPersonEmbeddings:
    """Tests for match_person_embeddings function."""

    def test_match_person_embeddings_high_similarity(self) -> None:
        """Test match_person_embeddings finds high similarity matches."""
        # Create similar embeddings
        embedding1 = np.random.rand(OSNET_EMBEDDING_DIM)
        embedding1 = embedding1 / np.linalg.norm(embedding1)

        embedding2 = embedding1 + np.random.rand(OSNET_EMBEDDING_DIM) * 0.01
        embedding2 = embedding2 / np.linalg.norm(embedding2)

        query = PersonEmbeddingResult(embedding=embedding1, detection_id="query")
        gallery = [PersonEmbeddingResult(embedding=embedding2, detection_id="match1")]

        matches = match_person_embeddings(query, gallery, threshold=0.7)

        assert len(matches) == 1
        assert matches[0][0].detection_id == "match1"
        assert matches[0][1] > 0.9  # Very high similarity

    def test_match_person_embeddings_below_threshold(self) -> None:
        """Test match_person_embeddings filters out low similarity."""
        # Create orthogonal embeddings
        embedding1 = np.zeros(OSNET_EMBEDDING_DIM)
        embedding1[0] = 1.0

        embedding2 = np.zeros(OSNET_EMBEDDING_DIM)
        embedding2[1] = 1.0

        query = PersonEmbeddingResult(embedding=embedding1, detection_id="query")
        gallery = [PersonEmbeddingResult(embedding=embedding2, detection_id="no-match")]

        matches = match_person_embeddings(query, gallery, threshold=0.7)

        assert len(matches) == 0  # Similarity too low

    def test_match_person_embeddings_sorted_by_similarity(self) -> None:
        """Test match_person_embeddings returns matches sorted by similarity."""
        base_embedding = np.random.rand(OSNET_EMBEDDING_DIM)
        base_embedding = base_embedding / np.linalg.norm(base_embedding)

        # Create embeddings with varying similarity
        high_sim = base_embedding + np.random.rand(OSNET_EMBEDDING_DIM) * 0.01
        high_sim = high_sim / np.linalg.norm(high_sim)

        med_sim = base_embedding + np.random.rand(OSNET_EMBEDDING_DIM) * 0.1
        med_sim = med_sim / np.linalg.norm(med_sim)

        query = PersonEmbeddingResult(embedding=base_embedding)
        gallery = [
            PersonEmbeddingResult(embedding=med_sim, detection_id="med"),
            PersonEmbeddingResult(embedding=high_sim, detection_id="high"),
        ]

        matches = match_person_embeddings(query, gallery, threshold=0.5)

        # Should be sorted with highest similarity first
        assert len(matches) == 2
        assert matches[0][0].detection_id == "high"
        assert matches[1][0].detection_id == "med"
        assert matches[0][1] > matches[1][1]

    def test_match_person_embeddings_empty_gallery(self) -> None:
        """Test match_person_embeddings with empty gallery."""
        embedding = np.random.rand(OSNET_EMBEDDING_DIM)
        query = PersonEmbeddingResult(embedding=embedding)

        matches = match_person_embeddings(query, [], threshold=0.7)

        assert matches == []


class TestFormatPersonReidContext:
    """Tests for format_person_reid_context function."""

    def test_format_person_reid_context_no_matches(self) -> None:
        """Test format_person_reid_context with no matches."""
        result = format_person_reid_context([], "det-123")

        assert "det-123" in result
        assert "No prior matches" in result
        assert "new individual" in result

    def test_format_person_reid_context_high_confidence_match(self) -> None:
        """Test format_person_reid_context with high confidence match."""
        embedding = np.random.rand(OSNET_EMBEDDING_DIM)
        match_result = PersonEmbeddingResult(embedding=embedding, detection_id="known-person")

        matches = [(match_result, 0.95)]

        result = format_person_reid_context(matches, "det-123")

        assert "det-123" in result
        assert "HIGH CONFIDENCE" in result
        assert "known-person" in result
        assert "95%" in result

    def test_format_person_reid_context_medium_confidence_match(self) -> None:
        """Test format_person_reid_context with medium confidence match."""
        embedding = np.random.rand(OSNET_EMBEDDING_DIM)
        match_result = PersonEmbeddingResult(embedding=embedding, detection_id="maybe-person")

        matches = [(match_result, 0.85)]

        result = format_person_reid_context(matches, "det-456")

        assert "det-456" in result
        assert "Likely same person" in result
        assert "maybe-person" in result
        assert "85%" in result

    def test_format_person_reid_context_low_confidence_match(self) -> None:
        """Test format_person_reid_context with low confidence match."""
        embedding = np.random.rand(OSNET_EMBEDDING_DIM)
        match_result = PersonEmbeddingResult(embedding=embedding, detection_id="possible-person")

        matches = [(match_result, 0.75)]

        result = format_person_reid_context(matches, "det-789")

        assert "det-789" in result
        assert "Possible match" in result
        assert "possible-person" in result
        assert "75%" in result

    def test_format_person_reid_context_multiple_matches(self) -> None:
        """Test format_person_reid_context with multiple matches (top 3 shown)."""
        embedding = np.random.rand(OSNET_EMBEDDING_DIM)

        matches = [
            (PersonEmbeddingResult(embedding=embedding, detection_id="match1"), 0.95),
            (PersonEmbeddingResult(embedding=embedding, detection_id="match2"), 0.85),
            (PersonEmbeddingResult(embedding=embedding, detection_id="match3"), 0.75),
            (PersonEmbeddingResult(embedding=embedding, detection_id="match4"), 0.65),
        ]

        result = format_person_reid_context(matches, "det-multi")

        # Should only show top 3
        assert "match1" in result
        assert "match2" in result
        assert "match3" in result
        assert "match4" not in result

    @pytest.mark.asyncio
    async def test_extract_person_embedding_tuple_output(self, monkeypatch) -> None:
        """Test extract_person_embedding handles tuple model output."""
        import sys

        mock_torch = MagicMock()
        mock_torch.inference_mode.return_value.__enter__ = MagicMock()
        mock_torch.inference_mode.return_value.__exit__ = MagicMock()

        mock_tensor = MagicMock()
        mock_tensor.unsqueeze.return_value = mock_tensor
        mock_tensor.to.return_value = mock_tensor

        # Model returns tuple (features, logits)
        mock_features = MagicMock()
        mock_features.squeeze.return_value = MagicMock()
        mock_features.squeeze.return_value.cpu.return_value = MagicMock()
        mock_features.squeeze.return_value.cpu.return_value.numpy.return_value = np.random.rand(
            OSNET_EMBEDDING_DIM
        )
        mock_logits = MagicMock()

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([MagicMock(device="cpu")])
        mock_model.return_value = (mock_features, mock_logits)  # Tuple output

        mock_transform = MagicMock()
        mock_transform.return_value = mock_tensor

        model_dict = {"model": mock_model, "transform": mock_transform}

        mock_image = MagicMock()
        mock_image.mode = "RGB"
        mock_image.size = (128, 256)

        monkeypatch.setitem(sys.modules, "torch", mock_torch)

        result = await extract_person_embedding(model_dict, mock_image)

        assert isinstance(result, PersonEmbeddingResult)
        assert result.embedding.shape == (OSNET_EMBEDDING_DIM,)

    @pytest.mark.asyncio
    async def test_extract_person_embedding_wrong_dimension_flatten(self, monkeypatch) -> None:
        """Test extract_person_embedding handles wrong-sized embeddings (needs flattening)."""
        import sys

        mock_torch = MagicMock()
        mock_torch.inference_mode.return_value.__enter__ = MagicMock()
        mock_torch.inference_mode.return_value.__exit__ = MagicMock()

        mock_tensor = MagicMock()
        mock_tensor.unsqueeze.return_value = mock_tensor
        mock_tensor.to.return_value = mock_tensor

        # Return 2D array that needs flattening
        wrong_shape = np.random.rand(2, OSNET_EMBEDDING_DIM // 2)
        mock_output = MagicMock()
        mock_output.squeeze.return_value = MagicMock()
        mock_output.squeeze.return_value.cpu.return_value = MagicMock()
        mock_output.squeeze.return_value.cpu.return_value.numpy.return_value = wrong_shape

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([MagicMock(device="cpu")])
        mock_model.return_value = mock_output

        mock_transform = MagicMock()
        mock_transform.return_value = mock_tensor

        model_dict = {"model": mock_model, "transform": mock_transform}

        mock_image = MagicMock()
        mock_image.mode = "RGB"
        mock_image.size = (128, 256)

        monkeypatch.setitem(sys.modules, "torch", mock_torch)

        result = await extract_person_embedding(model_dict, mock_image)

        assert isinstance(result, PersonEmbeddingResult)
        # Should be truncated/padded to correct dimension
        assert result.embedding.shape == (OSNET_EMBEDDING_DIM,)

    @pytest.mark.asyncio
    async def test_extract_person_embedding_too_short_padding(self, monkeypatch) -> None:
        """Test extract_person_embedding pads short embeddings."""
        import sys

        mock_torch = MagicMock()
        mock_torch.inference_mode.return_value.__enter__ = MagicMock()
        mock_torch.inference_mode.return_value.__exit__ = MagicMock()

        mock_tensor = MagicMock()
        mock_tensor.unsqueeze.return_value = mock_tensor
        mock_tensor.to.return_value = mock_tensor

        # Return embedding that's too short
        short_embedding = np.random.rand(OSNET_EMBEDDING_DIM - 100)
        mock_output = MagicMock()
        mock_output.squeeze.return_value = MagicMock()
        mock_output.squeeze.return_value.cpu.return_value = MagicMock()
        mock_output.squeeze.return_value.cpu.return_value.numpy.return_value = short_embedding

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([MagicMock(device="cpu")])
        mock_model.return_value = mock_output

        mock_transform = MagicMock()
        mock_transform.return_value = mock_tensor

        model_dict = {"model": mock_model, "transform": mock_transform}

        mock_image = MagicMock()
        mock_image.mode = "RGB"
        mock_image.size = (128, 256)

        monkeypatch.setitem(sys.modules, "torch", mock_torch)

        result = await extract_person_embedding(model_dict, mock_image)

        assert isinstance(result, PersonEmbeddingResult)
        # Should be padded to correct dimension
        assert result.embedding.shape == (OSNET_EMBEDDING_DIM,)


class TestOSNetConstants:
    """Tests for OSNet constants."""

    def test_osnet_embedding_dim_constant(self) -> None:
        """Test OSNET_EMBEDDING_DIM is set correctly."""
        assert OSNET_EMBEDDING_DIM == 512
