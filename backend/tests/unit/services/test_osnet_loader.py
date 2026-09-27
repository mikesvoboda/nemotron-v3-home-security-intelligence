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

import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

import backend.services.osnet_loader as ol
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
        # The loader probes BOTH torchreid spellings (0.2.5 nests under
        # torchreid.reid.models), and this file's real-weights proof caches the
        # real nested module process-wide — the mock must shadow both, or a
        # randomized run lets the real build_model answer this test.
        monkeypatch.setitem(sys.modules, "torchreid.reid.models", mock_torchreid.models)
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
        # NEM-4521: load_state_dict returns (missing_keys, unexpected_keys) tuple
        mock_model.load_state_dict.return_value = ([], [])

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

        # Mock security validation
        monkeypatch.setattr(
            "backend.core.security.validate_model_path",
            lambda *args, **kwargs: Path("/test/model"),
        )

        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "torchreid", mock_torchreid)
        monkeypatch.setitem(sys.modules, "torchreid.models", mock_torchreid.models)
        # The loader probes BOTH torchreid spellings (0.2.5 nests under
        # torchreid.reid.models), and this file's real-weights proof caches the
        # real nested module process-wide — the mock must shadow both, or a
        # randomized run lets the real build_model answer this test.
        monkeypatch.setitem(sys.modules, "torchreid.reid.models", mock_torchreid.models)
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
        # NEM-4521: load_state_dict returns (missing_keys, unexpected_keys) tuple
        mock_model.load_state_dict.return_value = ([], [])

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

        # Mock security validation
        monkeypatch.setattr(
            "backend.core.security.validate_model_path",
            lambda *args, **kwargs: Path("/test/model"),
        )

        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "torchreid", mock_torchreid)
        monkeypatch.setitem(sys.modules, "torchreid.models", mock_torchreid.models)
        # The loader probes BOTH torchreid spellings (0.2.5 nests under
        # torchreid.reid.models), and this file's real-weights proof caches the
        # real nested module process-wide — the mock must shadow both, or a
        # randomized run lets the real build_model answer this test.
        monkeypatch.setitem(sys.modules, "torchreid.reid.models", mock_torchreid.models)
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
            # NEM-4521: load_state_dict returns (missing_keys, unexpected_keys) tuple
            return ([], [])

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

        # Mock security validation
        monkeypatch.setattr(
            "backend.core.security.validate_model_path",
            lambda *args, **kwargs: Path("/test/model"),
        )

        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "torchreid", mock_torchreid)
        monkeypatch.setitem(sys.modules, "torchreid.models", mock_torchreid.models)
        # The loader probes BOTH torchreid spellings (0.2.5 nests under
        # torchreid.reid.models), and this file's real-weights proof caches the
        # real nested module process-wide — the mock must shadow both, or a
        # randomized run lets the real build_model answer this test.
        monkeypatch.setitem(sys.modules, "torchreid.reid.models", mock_torchreid.models)
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
            # NEM-4521: load_state_dict returns (missing_keys, unexpected_keys) tuple
            return ([], [])

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

        # Mock security validation
        monkeypatch.setattr(
            "backend.core.security.validate_model_path",
            lambda *args, **kwargs: Path("/test/model"),
        )

        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "torchreid", mock_torchreid)
        monkeypatch.setitem(sys.modules, "torchreid.models", mock_torchreid.models)
        # The loader probes BOTH torchreid spellings (0.2.5 nests under
        # torchreid.reid.models), and this file's real-weights proof caches the
        # real nested module process-wide — the mock must shadow both, or a
        # randomized run lets the real build_model answer this test.
        monkeypatch.setitem(sys.modules, "torchreid.reid.models", mock_torchreid.models)
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

        # Simulate torchreid being uninstalled. Deleting sys.modules keys is
        # NOT enough (importlib re-imports an on-disk package), and it never
        # was: the shipped `from torchreid.models import` raised even on a
        # fresh import in envs like this one. Patch the loader's probe to
        # raise ImportError — exactly what "not installed" looks like to it.
        def _no_torchreid() -> None:
            raise ImportError("torchreid not installed (simulated)")

        monkeypatch.setattr(ol, "_import_build_model", _no_torchreid)

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

        # Simulate torchreid being uninstalled (see the TorchScript test:
        # patch the probe; sys.modules deletion can't hide an on-disk package).
        def _no_torchreid() -> None:
            raise ImportError("torchreid not installed (simulated)")

        monkeypatch.setattr(ol, "_import_build_model", _no_torchreid)

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
    async def test_extract_person_embedding_too_short_raises(self, monkeypatch) -> None:
        """D-5 (ledger item 20): short features RAISE — the retired padding
        turned a wrong checkpoint into a plausible 512-vector with no trail."""
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

        with pytest.raises(RuntimeError, match=f"{OSNET_EMBEDDING_DIM}"):
            await extract_person_embedding(model_dict, mock_image)


class TestOSNetConstants:
    """Tests for OSNet constants."""

    def test_osnet_embedding_dim_constant(self) -> None:
        """Test OSNET_EMBEDDING_DIM is set correctly."""
        assert OSNET_EMBEDDING_DIM == 512


# =============================================================================
# Provenance + pinning (ledger item 20: the full swap — F11 belt, F12 hash)
# =============================================================================

OSNET_SHA256 = (
    "8a07e8da38946f7cee37f4561617bf8b6d2fe8f3a4027852893ea092e46d919f"  # pragma: allowlist secret
)
OSNET_ID = "osnet-ain-x1-0@osnet_ain_x1_0_msmt17@8a07e8da3894"


def _yaml_catalog() -> dict:
    from pathlib import Path

    import yaml

    models_yml = Path(__file__).resolve().parents[4] / "models.yml"
    entries = yaml.safe_load(models_yml.read_text())["models"]
    return {e["name"]: e for e in entries}


class TestModelsYmlOsnetRow:
    """The zoo row is the SINGLE source of the OSNet identity: weights file
    name + SHA-256 pin. Every producer's belt derives from it, so a weights
    swap changes every stored model_id at once — or the pin below fails."""

    def test_row_pins_weights_by_sha256(self) -> None:
        row = _yaml_catalog()["osnet-ain-x1-0"]
        assert row["sha256"] == OSNET_SHA256

    def test_row_names_the_weights_file(self) -> None:
        row = _yaml_catalog()["osnet-ain-x1-0"]
        assert row["runtime_file"] == "osnet_ain_x1_0_msmt17.pth"

    def test_description_carries_the_honest_benchmark(self) -> None:
        """The retired wording ("MSMT17 Rank-1 73.3%") conflated the
        multi-source (MS+D+C->Market) number with single-source MSMT17;
        single-source MSMT17->Market is 70.1 (14-specialist-model-research)."""
        row = _yaml_catalog()["osnet-ain-x1-0"]
        assert "73.3" not in row["description"]
        assert "70.1" in row["description"]


class TestOsnetModelId:
    """osnet_model_id() is the ONE belt string every person-vector producer
    labels with (B5b) — backend handle, unified.reid_embedding, safe-extract
    payloads all read it, so "one space" is mechanical, not aspirational."""

    def test_value_is_row_derived_never_a_literal(self) -> None:
        row = _yaml_catalog()["osnet-ain-x1-0"]
        stem = row["runtime_file"].removesuffix(".pth")
        assert ol.osnet_model_id() == f"osnet-ain-x1-0@{stem}@{row['sha256'][:12]}"
        assert ol.osnet_model_id() == OSNET_ID

    def test_same_value_for_every_caller(self) -> None:
        assert ol.osnet_model_id() == ol.osnet_model_id()


class TestGetReidHandle:
    """Membership read of the resident models — NEVER a load trigger (the
    face get_face_leg_handles pattern)."""

    def test_absent_model_answers_none(self, monkeypatch) -> None:
        fake_manager = MagicMock()
        fake_manager._loaded_models = {}
        monkeypatch.setattr("backend.services.model_zoo.get_model_manager", lambda: fake_manager)
        assert ol.get_reid_handle() is None

    def test_resident_model_is_returned_unchanged(self, monkeypatch) -> None:
        handle = {"model": MagicMock(), "model_id": OSNET_ID}
        fake_manager = MagicMock()
        fake_manager._loaded_models = {"osnet-ain-x1-0": handle}
        monkeypatch.setattr("backend.services.model_zoo.get_model_manager", lambda: fake_manager)
        assert ol.get_reid_handle() is handle

    def test_read_never_triggers_a_load(self, monkeypatch) -> None:
        fake_manager = MagicMock()
        fake_manager._loaded_models = {}
        monkeypatch.setattr("backend.services.model_zoo.get_model_manager", lambda: fake_manager)
        ol.get_reid_handle()
        assert fake_manager.load.call_count == 0
        assert fake_manager.preload.call_count == 0


class TestOsnetShaPinEnforcedBeforeLoad:
    """F12 shape, person-vector twin: wrong bytes are the same answer as no
    bytes — UNAVAILABLE, and the file is never torch.load'ed."""

    @pytest.mark.asyncio
    async def test_hash_miss_raises_and_torch_load_never_runs(self, tmp_path, monkeypatch) -> None:
        weights = tmp_path / "osnet_ain_x1_0_msmt17.pth"
        weights.write_bytes(b"not-the-pinned-bytes")

        mock_torch = MagicMock()
        monkeypatch.setitem(sys.modules, "torch", mock_torch)

        with pytest.raises(RuntimeError, match="sha256"):
            await load_osnet_model(str(tmp_path), expected_sha256=OSNET_SHA256)
        assert mock_torch.load.call_count == 0
        assert mock_torch.jit.load.call_count == 0

    @pytest.mark.asyncio
    async def test_load_result_carries_the_belt(self, tmp_path, monkeypatch) -> None:
        import hashlib

        content = b"pinned-enough-for-this-harness"
        weights = tmp_path / "osnet_ain_x1_0_msmt17.pth"
        weights.write_bytes(content)
        sha = hashlib.sha256(content).hexdigest()

        # Fake the whole torch/torchreid stack; the pin check is real.
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        fake_model = MagicMock()
        fake_model.load_state_dict.return_value = (
            type("R", (), {"missing_keys": [], "unexpected_keys": []})(),
        )
        mock_build = MagicMock(return_value=fake_model)
        fake_models_mod = MagicMock(build_model=mock_build)
        fake_torchreid = MagicMock()
        fake_torchreid.reid.models = fake_models_mod
        mock_tv = MagicMock()
        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "torchvision", mock_tv)
        monkeypatch.setitem(sys.modules, "torchvision.transforms", mock_tv.transforms)
        monkeypatch.setitem(sys.modules, "torchreid", fake_torchreid)
        monkeypatch.setitem(sys.modules, "torchreid.reid", fake_torchreid.reid)
        monkeypatch.setitem(sys.modules, "torchreid.reid.models", fake_models_mod)

        # Belt grammar is computed from the ACTUAL loaded file, same helper.
        result = await load_osnet_model(str(tmp_path), expected_sha256=sha)
        assert result["model_id"] == f"osnet-ain-x1-0@osnet_ain_x1_0_msmt17@{sha[:12]}"

    @pytest.mark.asyncio
    async def test_directory_mode_finds_the_named_weights_file(self, tmp_path, monkeypatch) -> None:
        """Directory deploy (no runtime_file passed): the loader finds
        osnet_ain_x1_0_msmt17.pth and the belt names its file."""
        import hashlib

        weights = tmp_path / "osnet_ain_x1_0_msmt17.pth"
        weights.write_bytes(b"dir-mode-bytes")
        sha = hashlib.sha256(weights.read_bytes()).hexdigest()

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        fake_model = MagicMock()
        fake_model.load_state_dict.return_value = (
            type("R", (), {"missing_keys": [], "unexpected_keys": []})(),
        )
        mock_build = MagicMock(return_value=fake_model)
        fake_models_mod = MagicMock(build_model=mock_build)
        fake_torchreid = MagicMock()
        fake_torchreid.reid.models = fake_models_mod
        mock_tv = MagicMock()
        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "torchvision", mock_tv)
        monkeypatch.setitem(sys.modules, "torchvision.transforms", mock_tv.transforms)
        monkeypatch.setitem(sys.modules, "torchreid", fake_torchreid)
        monkeypatch.setitem(sys.modules, "torchreid.reid", fake_torchreid.reid)
        monkeypatch.setitem(sys.modules, "torchreid.reid.models", fake_models_mod)

        result = await load_osnet_model(str(tmp_path), expected_sha256=sha)
        assert result["model"] is fake_model
        assert result["model_id"] == f"osnet-ain-x1-0@osnet_ain_x1_0_msmt17@{sha[:12]}"


class TestTensorboardImportHazard:
    """torchreid's package chain imports torch.utils.tensorboard, which needs
    the tensorboard package — absent from this venv, and SummaryWriter is
    trainer-only (never inference). The loader pre-registers a bounded stub
    so the REAL build_model branch works; without it, every env without
    tensorboard silently degrades to the TorchScript fallback and the whole
    store answers 'unavailable' in the field."""

    def test_stub_installed_when_tensorboard_missing(self, monkeypatch) -> None:
        import builtins
        import sys as _sys

        real_import = builtins.__import__

        def no_tensorboard(name, *a, **k):
            if name == "tensorboard" or name.startswith("tensorboard."):
                raise ImportError("No module named 'tensorboard'")
            return real_import(name, *a, **k)

        saved = _sys.modules.pop("torch.utils.tensorboard", None)
        try:
            monkeypatch.setattr(builtins, "__import__", no_tensorboard)
            ol._ensure_tensorboard_importable()
            stub = _sys.modules.get("torch.utils.tensorboard")
            assert stub is not None
            assert hasattr(stub, "SummaryWriter")
            assert stub.SummaryWriter("x") is not None  # inert, not a raise
        finally:
            _sys.modules.pop("torch.utils.tensorboard", None)
            if saved is not None:
                _sys.modules["torch.utils.tensorboard"] = saved

    def test_real_module_wins_when_importable(self) -> None:
        import importlib

        try:
            importlib.import_module("torch.utils.tensorboard")
            real = sys.modules["torch.utils.tensorboard"]
        except ImportError:
            pytest.skip("torch.utils.tensorboard not importable in this env")
        ol._ensure_tensorboard_importable()
        assert sys.modules["torch.utils.tensorboard"] is real


class TestRealWeightsProof:
    """The swap's acceptance line (plan Slice B2): build_model
    ('osnet_ain_x1_0') must ACTUALLY import and run in this venv — the
    tier mocks everything else, so without this pin a silent
    tensorboard/torchreid failure ships a store that only answers
    'unavailable'. Gated: skips when the pinned weights or torchreid are
    absent (CI); runs the real thing wherever they exist."""

    @staticmethod
    def _weights() -> Path | None:
        import os

        base = os.environ.get("AGENT_GPU_DIR") or ""
        candidate = Path(base) / "models/model-zoo/osnet-ain-x1-0/osnet_ain_x1_0_msmt17.pth"
        return candidate if candidate.is_file() else None

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)  # real torchreid build + inference; the 5s tier
    # default flakes under xdist load (weights present => not a skip path)
    async def test_pinned_weights_load_end_to_end(self, monkeypatch) -> None:
        weights = self._weights()
        if weights is None:
            pytest.skip("pinned OSNet weights not present (AGENT_GPU_DIR unset)")
        try:
            import torch  # noqa: F401

            # torchreid's chain needs the tensorboard hazard handled FIRST
            # (bare `import torchreid` fails in a venv without tensorboard —
            # the loader applies the same shim; doing it here is what makes
            # this proof test the loader's REAL path, not a false skip).
            ol._ensure_tensorboard_importable()
            import torchreid  # noqa: F401
        except ImportError:
            pytest.skip("torch/torchreid not installed")

        # The weights live under $AGENT_GPU_DIR (dev box), outside the
        # deploy-time allowed dirs (/models/...); allow this one dir so the
        # proof runs the real load through the real path validation.
        import backend.core.security as sec

        monkeypatch.setattr(
            sec,
            "DEFAULT_ALLOWED_MODEL_DIRECTORIES",
            (*sec.DEFAULT_ALLOWED_MODEL_DIRECTORIES, str(weights.parent.parent.parent)),
        )

        result = await load_osnet_model(str(weights.parent), expected_sha256=OSNET_SHA256)
        assert result["model_id"] == OSNET_ID
        assert result["embedding_dim"] == 512

        # Real crop -> real 512-d unit vector (no padding, no truncation).
        from PIL import Image

        crop = Image.new("RGB", (64, 128), color=(90, 120, 150))
        emb = await extract_person_embedding(result, crop)
        assert isinstance(emb, PersonEmbeddingResult)
        assert emb.embedding.shape == (512,)
        assert abs(float(np.linalg.norm(emb.embedding)) - 1.0) < 1e-4
        assert emb.model_id == OSNET_ID
        assert np.isfinite(emb.embedding).all()


class TestDimensionGuardRaises:
    """D-5: a wrong checkpoint must never become a plausible vector. The
    retired pad/truncate-to-512 made any dim a 512-vector with no trail;
    the guard now refuses the vector."""

    @pytest.mark.asyncio
    async def test_short_features_raise_not_pad(self, monkeypatch) -> None:
        import sys

        mock_torch = MagicMock()
        mock_tensor = MagicMock()
        mock_output = MagicMock()
        short = np.random.rand(OSNET_EMBEDDING_DIM - 100).astype("float32")
        mock_output.squeeze.return_value.cpu.return_value.numpy.return_value = short
        mock_tensor.__getitem__ = lambda self, k: mock_output
        mock_torch.stack.return_value = mock_tensor
        mock_torch.inference_mode.return_value = MagicMock(
            __enter__=lambda s: None, __exit__=lambda *a: False
        )

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([MagicMock(device="cpu")])
        mock_model.return_value = mock_output
        mock_transform = MagicMock(return_value=mock_tensor)

        monkeypatch.setitem(sys.modules, "torch", mock_torch)

        image = MagicMock()
        image.mode = "RGB"
        image.size = (128, 256)

        with pytest.raises(RuntimeError, match="512"):
            await extract_person_embedding(
                {"model": mock_model, "transform": mock_transform, "model_id": OSNET_ID},
                image,
            )

    @pytest.mark.asyncio
    async def test_long_features_raise_not_truncate(self, monkeypatch) -> None:
        import sys

        mock_torch = MagicMock()
        mock_tensor = MagicMock()
        mock_output = MagicMock()
        long = np.random.rand(OSNET_EMBEDDING_DIM + 64).astype("float32")
        mock_output.squeeze.return_value.cpu.return_value.numpy.return_value = long
        mock_torch.inference_mode.return_value = MagicMock(
            __enter__=lambda s: None, __exit__=lambda *a: False
        )

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([MagicMock(device="cpu")])
        mock_model.return_value = mock_output
        mock_transform = MagicMock(return_value=mock_tensor)

        monkeypatch.setitem(sys.modules, "torch", mock_torch)

        image = MagicMock()
        image.mode = "RGB"
        image.size = (128, 256)

        with pytest.raises(RuntimeError, match="512"):
            await extract_person_embedding(
                {"model": mock_model, "transform": mock_transform, "model_id": OSNET_ID},
                image,
            )

    def test_person_embedding_result_carries_the_belt(self) -> None:
        r = PersonEmbeddingResult(embedding=np.ones(OSNET_EMBEDDING_DIM), model_id=OSNET_ID)
        assert r.model_id == OSNET_ID
        assert r.to_dict()["model_id"] == OSNET_ID

    def test_belt_defaults_none_not_a_claim(self) -> None:
        r = PersonEmbeddingResult(embedding=np.ones(OSNET_EMBEDDING_DIM))
        assert r.model_id is None
