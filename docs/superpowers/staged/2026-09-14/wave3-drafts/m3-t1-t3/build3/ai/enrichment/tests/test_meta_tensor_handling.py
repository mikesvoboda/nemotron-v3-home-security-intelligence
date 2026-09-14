"""Unit tests for meta tensor handling in enrichment models.

Tests cover:
- _has_meta_tensors helper function
- _materialize_meta_tensors helper function
- ClothingClassifier meta tensor handling
- ActionRecognizer meta tensor handling

These tests verify that models with meta tensors (lazy-loaded weights)
are properly detected and materialized to avoid "Cannot copy out of meta tensor" errors.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add ai/enrichment to path for imports
enrichment_dir = Path(__file__).parent.parent
sys.path.insert(0, str(enrichment_dir))


class TestMetaTensorHelpers:
    """Tests for meta tensor detection and materialization helpers in model.py."""

    def test_has_meta_tensors_returns_true_for_meta_device(self) -> None:
        """Test that _has_meta_tensors detects meta tensors."""
        from model import _has_meta_tensors

        # Create a mock parameter on meta device
        mock_param = MagicMock()
        mock_device = MagicMock()
        mock_device.type = "meta"
        mock_param.device = mock_device

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([mock_param])

        assert _has_meta_tensors(mock_model) is True

    def test_has_meta_tensors_returns_false_for_cpu_device(self) -> None:
        """Test that _has_meta_tensors returns False for CPU tensors."""
        from model import _has_meta_tensors

        mock_param = MagicMock()
        mock_device = MagicMock()
        mock_device.type = "cpu"
        mock_param.device = mock_device

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([mock_param])

        assert _has_meta_tensors(mock_model) is False

    def test_has_meta_tensors_returns_false_for_cuda_device(self) -> None:
        """Test that _has_meta_tensors returns False for CUDA tensors."""
        from model import _has_meta_tensors

        mock_param = MagicMock()
        mock_device = MagicMock()
        mock_device.type = "cuda"
        mock_param.device = mock_device

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([mock_param])

        assert _has_meta_tensors(mock_model) is False

    def test_has_meta_tensors_returns_false_for_empty_model(self) -> None:
        """Test that _has_meta_tensors returns False for models with no parameters."""
        from model import _has_meta_tensors

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([])

        assert _has_meta_tensors(mock_model) is False

    def test_has_meta_tensors_handles_exception(self) -> None:
        """Test that _has_meta_tensors returns False on exception."""
        from model import _has_meta_tensors

        mock_model = MagicMock()
        mock_model.parameters.side_effect = RuntimeError("Test error")

        assert _has_meta_tensors(mock_model) is False

    def test_materialize_meta_tensors_calls_to_empty_and_load_state_dict(self) -> None:
        """Test that _materialize_meta_tensors uses to_empty() + load_state_dict()."""
        from model import _materialize_meta_tensors

        mock_model = MagicMock()
        mock_state_dict = {"weight": MagicMock()}
        mock_model.state_dict.return_value = mock_state_dict
        mock_model.to_empty.return_value = mock_model

        with patch("torch.device") as mock_torch_device:
            mock_torch_device.return_value = "cpu"

            result = _materialize_meta_tensors(mock_model, "cpu")

            mock_model.state_dict.assert_called_once()
            mock_model.to_empty.assert_called_once()
            mock_model.load_state_dict.assert_called_once_with(mock_state_dict, assign=True)
            assert result == mock_model


class TestClothingClassifierMetaTensors:
    """Tests for ClothingClassifier meta tensor handling."""

    def test_load_model_detects_meta_tensors(self) -> None:
        """Test that ClothingClassifier detects models with meta tensors."""
        from model import ClothingClassifier

        # Create mock parameter on meta device
        mock_meta_param = MagicMock()
        mock_meta_device = MagicMock()
        mock_meta_device.type = "meta"
        mock_meta_param.device = mock_meta_device

        # Create mock model with meta tensors
        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([mock_meta_param])
        mock_model.state_dict.return_value = {"weight": MagicMock()}
        mock_model.to_empty.return_value = mock_model
        mock_model.eval.return_value = None

        mock_preprocess = MagicMock()
        mock_tokenizer = MagicMock()

        with patch("model.validate_model_path") as mock_validate:
            mock_validate.return_value = "/models/fashion-siglip"
            with patch("model.create_model_from_pretrained") as mock_create:
                mock_create.return_value = (mock_model, mock_preprocess)
                with patch("model.get_tokenizer") as mock_get_tokenizer:
                    mock_get_tokenizer.return_value = mock_tokenizer
                    with (
                        patch("torch.cuda.is_available", return_value=False),
                        patch("torch.device") as mock_torch_device,
                    ):
                        mock_torch_device.return_value = "cpu"

                        classifier = ClothingClassifier("/models/fashion-siglip", device="cpu")
                        classifier.load_model()

                        # Verify meta tensor handling was triggered
                        mock_model.to_empty.assert_called_once()
                        mock_model.load_state_dict.assert_called_once()

    def test_load_model_no_meta_tensors(self) -> None:
        """Test that ClothingClassifier handles models without meta tensors."""
        from model import ClothingClassifier

        # Create mock parameter on CPU device (no meta tensors)
        mock_cpu_param = MagicMock()
        mock_cpu_device = MagicMock()
        mock_cpu_device.type = "cpu"
        mock_cpu_param.device = mock_cpu_device

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([mock_cpu_param])
        mock_model.eval.return_value = None

        mock_preprocess = MagicMock()
        mock_tokenizer = MagicMock()

        with patch("model.validate_model_path") as mock_validate:
            mock_validate.return_value = "/models/fashion-siglip"
            with patch("model.create_model_from_pretrained") as mock_create:
                mock_create.return_value = (mock_model, mock_preprocess)
                with patch("model.get_tokenizer") as mock_get_tokenizer:
                    mock_get_tokenizer.return_value = mock_tokenizer
                    with patch("torch.cuda.is_available", return_value=False):
                        classifier = ClothingClassifier("/models/fashion-siglip", device="cpu")
                        classifier.load_model()

                        # Verify model was loaded but no meta tensor handling
                        assert classifier.model is not None
                        # to_empty should not have been called
                        assert not mock_model.to_empty.called

    def test_load_model_handles_materialization_error(self) -> None:
        """Test that ClothingClassifier handles materialization errors gracefully."""
        from model import ClothingClassifier

        # Create mock parameter on meta device
        mock_meta_param = MagicMock()
        mock_meta_device = MagicMock()
        mock_meta_device.type = "meta"
        mock_meta_param.device = mock_meta_device

        # Create mock model that fails on materialization
        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([mock_meta_param])
        mock_model.state_dict.return_value = {"weight": MagicMock()}
        mock_model.to_empty.side_effect = RuntimeError("Materialization failed")

        mock_preprocess = MagicMock()
        mock_tokenizer = MagicMock()

        with patch("model.validate_model_path") as mock_validate:
            mock_validate.return_value = "/models/fashion-siglip"
            with patch("model.create_model_from_pretrained") as mock_create:
                mock_create.return_value = (mock_model, mock_preprocess)
                with patch("model.get_tokenizer") as mock_get_tokenizer:
                    mock_get_tokenizer.return_value = mock_tokenizer
                    with patch("torch.cuda.is_available", return_value=False):
                        classifier = ClothingClassifier("/models/fashion-siglip", device="cpu")

                        # Should raise RuntimeError on materialization failure
                        with pytest.raises(RuntimeError) as exc_info:
                            classifier.load_model()

                        assert "Failed to materialize meta tensors" in str(exc_info.value)


class TestActionRecognizerMetaTensors:
    """Tests for ActionRecognizer meta tensor handling."""

    def test_load_model_detects_meta_tensors(self) -> None:
        """Test that ActionRecognizer detects models with meta tensors."""
        from models.action_recognizer import ActionRecognizer

        # Create mock parameter on meta device
        mock_meta_param = MagicMock()
        mock_meta_device = MagicMock()
        mock_meta_device.type = "meta"
        mock_meta_param.device = mock_meta_device

        # Create mock model with meta tensors
        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([mock_meta_param])
        mock_model.state_dict.return_value = {"weight": MagicMock()}
        mock_model.to_empty.return_value = mock_model
        mock_model.eval.return_value = None

        mock_processor = MagicMock()

        with patch(
            "models.action_recognizer.XCLIPProcessor.from_pretrained"
        ) as mock_processor_load:
            mock_processor_load.return_value = mock_processor
            with patch("models.action_recognizer.XCLIPModel.from_pretrained") as mock_model_load:
                mock_model_load.return_value = mock_model
                with (
                    patch("torch.cuda.is_available", return_value=False),
                    patch("torch.device") as mock_torch_device,
                ):
                    mock_torch_device.return_value = "cpu"

                    recognizer = ActionRecognizer("/models/xclip", device="cpu")
                    recognizer.load_model()

                    # Verify meta tensor handling was triggered
                    mock_model.to_empty.assert_called_once()
                    mock_model.load_state_dict.assert_called_once()

    def test_load_model_no_meta_tensors(self) -> None:
        """Test that ActionRecognizer handles models without meta tensors."""
        from models.action_recognizer import ActionRecognizer

        # Create mock parameter on CPU device (no meta tensors)
        mock_cpu_param = MagicMock()
        mock_cpu_device = MagicMock()
        mock_cpu_device.type = "cpu"
        mock_cpu_param.device = mock_cpu_device

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([mock_cpu_param])
        mock_model.to.return_value = mock_model
        mock_model.eval.return_value = None

        mock_processor = MagicMock()

        with patch(
            "models.action_recognizer.XCLIPProcessor.from_pretrained"
        ) as mock_processor_load:
            mock_processor_load.return_value = mock_processor
            with patch("models.action_recognizer.XCLIPModel.from_pretrained") as mock_model_load:
                mock_model_load.return_value = mock_model
                with patch("torch.cuda.is_available", return_value=False):
                    recognizer = ActionRecognizer("/models/xclip", device="cpu")
                    recognizer.load_model()

                    # Verify model was loaded but no meta tensor handling
                    assert recognizer.model is not None
                    # to_empty should not have been called
                    assert not mock_model.to_empty.called

    def test_load_model_handles_materialization_error(self) -> None:
        """Test that ActionRecognizer handles materialization errors gracefully."""
        from models.action_recognizer import ActionRecognizer

        # Create mock parameter on meta device
        mock_meta_param = MagicMock()
        mock_meta_device = MagicMock()
        mock_meta_device.type = "meta"
        mock_meta_param.device = mock_meta_device

        # Create mock model that fails on materialization
        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([mock_meta_param])
        mock_model.state_dict.return_value = {"weight": MagicMock()}
        mock_model.to_empty.side_effect = RuntimeError("Materialization failed")

        mock_processor = MagicMock()

        with patch(
            "models.action_recognizer.XCLIPProcessor.from_pretrained"
        ) as mock_processor_load:
            mock_processor_load.return_value = mock_processor
            with patch("models.action_recognizer.XCLIPModel.from_pretrained") as mock_model_load:
                mock_model_load.return_value = mock_model
                with patch("torch.cuda.is_available", return_value=False):
                    recognizer = ActionRecognizer("/models/xclip", device="cpu")

                    # Should raise RuntimeError on materialization failure
                    with pytest.raises(RuntimeError) as exc_info:
                        recognizer.load_model()

                    assert "Failed to materialize meta tensors" in str(exc_info.value)

    def test_load_model_with_sdpa_and_meta_tensors(self) -> None:
        """Test that SDPA loading works with meta tensor handling."""
        from models.action_recognizer import ActionRecognizer

        # Create mock parameter on meta device
        mock_meta_param = MagicMock()
        mock_meta_device = MagicMock()
        mock_meta_device.type = "meta"
        mock_meta_param.device = mock_meta_device

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([mock_meta_param])
        mock_model.state_dict.return_value = {"weight": MagicMock()}
        mock_model.to_empty.return_value = mock_model
        mock_model.eval.return_value = None

        mock_processor = MagicMock()

        with patch(
            "models.action_recognizer.XCLIPProcessor.from_pretrained"
        ) as mock_processor_load:
            mock_processor_load.return_value = mock_processor
            with patch("models.action_recognizer.XCLIPModel.from_pretrained") as mock_model_load:
                # SDPA loading should succeed
                mock_model_load.return_value = mock_model
                with (
                    patch("torch.cuda.is_available", return_value=False),
                    patch("torch.device") as mock_torch_device,
                ):
                    mock_torch_device.return_value = "cpu"

                    recognizer = ActionRecognizer("/models/xclip", device="cpu")
                    recognizer.load_model()

                    # Verify SDPA was attempted
                    assert mock_model_load.call_count == 1
                    call_kwargs = mock_model_load.call_args[1]
                    assert "attn_implementation" in call_kwargs
                    assert call_kwargs["attn_implementation"] == "sdpa"

                    # Verify meta tensor handling was triggered
                    mock_model.to_empty.assert_called_once()
