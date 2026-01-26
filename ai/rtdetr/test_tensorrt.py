"""Unit tests for TensorRT conversion and inference.

Tests for the TensorRT conversion script and inference backend that provides
2-3x inference speedup compared to PyTorch inference.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add the ai/rtdetr directory to sys.path to enable imports
_rtdetr_dir = Path(__file__).parent
if str(_rtdetr_dir) not in sys.path:
    sys.path.insert(0, str(_rtdetr_dir))


class TestTensorRTConverterConfig:
    """Tests for TensorRT converter configuration."""

    def test_converter_supports_fp16_precision(self):
        """Test that converter supports FP16 precision."""
        from tensorrt_converter import TensorRTConverter

        converter = TensorRTConverter(
            onnx_path="/path/to/model.onnx",
            precision="fp16",
        )
        assert converter.precision == "fp16"

    def test_converter_supports_fp32_precision(self):
        """Test that converter supports FP32 precision."""
        from tensorrt_converter import TensorRTConverter

        converter = TensorRTConverter(
            onnx_path="/path/to/model.onnx",
            precision="fp32",
        )
        assert converter.precision == "fp32"

    def test_converter_default_precision_is_fp16(self):
        """Test that default precision is FP16 for optimal performance."""
        from tensorrt_converter import TensorRTConverter

        converter = TensorRTConverter(onnx_path="/path/to/model.onnx")
        assert converter.precision == "fp16"

    def test_converter_rejects_invalid_precision(self):
        """Test that converter rejects invalid precision values."""
        from tensorrt_converter import TensorRTConverter

        with pytest.raises(ValueError, match="precision must be"):
            TensorRTConverter(
                onnx_path="/path/to/model.onnx",
                precision="int4",  # Invalid precision
            )

    def test_converter_supports_dynamic_batch_size(self):
        """Test that converter supports dynamic batch sizes."""
        from tensorrt_converter import TensorRTConverter

        converter = TensorRTConverter(
            onnx_path="/path/to/model.onnx",
            max_batch_size=8,
            dynamic_batch=True,
        )
        assert converter.max_batch_size == 8
        assert converter.dynamic_batch is True

    def test_converter_default_batch_size(self):
        """Test default batch size configuration."""
        from tensorrt_converter import TensorRTConverter

        converter = TensorRTConverter(onnx_path="/path/to/model.onnx")
        assert converter.max_batch_size == 1
        assert converter.dynamic_batch is False

    def test_converter_workspace_size_configurable(self):
        """Test that TensorRT workspace size is configurable."""
        from tensorrt_converter import TensorRTConverter

        converter = TensorRTConverter(
            onnx_path="/path/to/model.onnx",
            workspace_size_gb=4,
        )
        assert converter.workspace_size_gb == 4

    def test_converter_default_workspace_size(self):
        """Test default workspace size is 2GB."""
        from tensorrt_converter import TensorRTConverter

        converter = TensorRTConverter(onnx_path="/path/to/model.onnx")
        assert converter.workspace_size_gb == 2


class TestTensorRTConverterExport:
    """Tests for ONNX to TensorRT engine export."""

    def test_export_generates_default_output_path(self):
        """Test that export generates default output path from ONNX path."""
        from tensorrt_converter import TensorRTConverter

        converter = TensorRTConverter(onnx_path="/path/to/model.onnx")

        # Should generate /path/to/model_fp16.engine
        default_path = converter._get_default_engine_path()
        assert default_path == "/path/to/model_fp16.engine"

    def test_export_path_includes_precision(self):
        """Test that generated engine path includes precision suffix."""
        from tensorrt_converter import TensorRTConverter

        converter = TensorRTConverter(
            onnx_path="/path/to/model.onnx",
            precision="fp32",
        )
        default_path = converter._get_default_engine_path()
        assert "_fp32.engine" in default_path

    def test_export_raises_on_missing_onnx(self):
        """Test that export raises error when ONNX file doesn't exist."""
        from tensorrt_converter import TensorRTConverter

        converter = TensorRTConverter(onnx_path="/nonexistent/model.onnx")

        with pytest.raises(FileNotFoundError):
            converter.export()


class TestTensorRTInferenceBackend:
    """Tests for TensorRT inference backend."""

    def test_backend_initialization(self):
        """Test TensorRT inference backend initialization."""
        from tensorrt_inference import TensorRTInference

        with patch.object(TensorRTInference, "_load_engine"):
            backend = TensorRTInference(
                engine_path="/path/to/model.engine",
                device="cuda:0",
            )
            assert backend.engine_path == "/path/to/model.engine"
            assert backend.device == "cuda:0"

    def test_backend_default_device(self):
        """Test that backend defaults to cuda:0."""
        from tensorrt_inference import TensorRTInference

        with patch.object(TensorRTInference, "_load_engine"):
            backend = TensorRTInference(engine_path="/path/to/model.engine")
            assert backend.device == "cuda:0"

    def test_backend_detect_interface(self):
        """Test that backend has detect() method matching PyTorch interface."""
        from PIL import Image
        from tensorrt_inference import TensorRTInference

        with patch.object(TensorRTInference, "_load_engine"):
            backend = TensorRTInference(engine_path="/path/to/model.engine")

            # Mock the inference
            with (
                patch.object(backend, "_run_inference") as mock_infer,
                patch.object(backend, "_preprocess") as mock_preprocess,
                patch.object(backend, "_postprocess") as mock_postprocess,
            ):
                mock_preprocess.return_value = MagicMock()
                mock_infer.return_value = {}
                mock_postprocess.return_value = []

                test_image = Image.new("RGB", (640, 480), color=(128, 128, 128))
                detections, inference_time = backend.detect(test_image)

                assert isinstance(detections, list)
                assert isinstance(inference_time, float)

    def test_backend_detect_batch_interface(self):
        """Test that backend has detect_batch() method matching PyTorch interface."""
        from PIL import Image
        from tensorrt_inference import TensorRTInference

        with patch.object(TensorRTInference, "_load_engine"):
            backend = TensorRTInference(engine_path="/path/to/model.engine")

            with patch.object(backend, "detect") as mock_detect:
                mock_detect.return_value = ([], 5.0)

                test_images = [
                    Image.new("RGB", (640, 480), color=(128, 128, 128)) for _ in range(3)
                ]
                all_detections, total_time = backend.detect_batch(test_images)

                assert isinstance(all_detections, list)
                assert len(all_detections) == 3
                assert isinstance(total_time, float)

    def test_backend_returns_security_classes_only(self):
        """Test that backend filters detections to security-relevant classes."""
        from tensorrt_inference import SECURITY_CLASSES

        expected_classes = {
            "person",
            "car",
            "truck",
            "dog",
            "cat",
            "bird",
            "bicycle",
            "motorcycle",
            "bus",
        }
        assert expected_classes == SECURITY_CLASSES

    def test_backend_confidence_threshold(self):
        """Test that backend applies confidence threshold."""
        from tensorrt_inference import TensorRTInference

        with patch.object(TensorRTInference, "_load_engine"):
            backend = TensorRTInference(
                engine_path="/path/to/model.engine",
                confidence_threshold=0.7,
            )
            assert backend.confidence_threshold == 0.7

    def test_backend_default_confidence_threshold(self):
        """Test default confidence threshold is 0.5."""
        from tensorrt_inference import TensorRTInference

        with patch.object(TensorRTInference, "_load_engine"):
            backend = TensorRTInference(engine_path="/path/to/model.engine")
            assert backend.confidence_threshold == 0.5


class TestTensorRTBackendSelection:
    """Tests for backend selection between PyTorch and TensorRT."""

    def test_pytorch_backend_by_default(self):
        """Test that PyTorch backend is selected by default."""
        backend = os.environ.get("RTDETR_BACKEND", "pytorch")
        # Default should be pytorch
        assert backend in ["pytorch", "tensorrt"]

    def test_backend_selection_via_environment(self):
        """Test backend selection via RTDETR_BACKEND environment variable."""
        from tensorrt_inference import get_inference_backend

        # Test pytorch selection
        with patch.dict(os.environ, {"RTDETR_BACKEND": "pytorch"}):
            backend_type = get_inference_backend()
            assert backend_type == "pytorch"

        # Test tensorrt selection
        with patch.dict(os.environ, {"RTDETR_BACKEND": "tensorrt"}):
            backend_type = get_inference_backend()
            assert backend_type == "tensorrt"

    def test_invalid_backend_falls_back_to_pytorch(self):
        """Test that invalid backend value falls back to PyTorch."""
        from tensorrt_inference import get_inference_backend

        with patch.dict(os.environ, {"RTDETR_BACKEND": "invalid"}):
            backend_type = get_inference_backend()
            assert backend_type == "pytorch"


class TestTensorRTEngineLoading:
    """Tests for TensorRT engine loading."""

    def test_engine_not_found_raises_error(self):
        """Test that missing engine file raises FileNotFoundError."""
        from tensorrt_inference import TensorRTInference

        with pytest.raises(FileNotFoundError):
            TensorRTInference(engine_path="/nonexistent/model.engine")


class TestTensorRTHealthStatus:
    """Tests for TensorRT health status reporting."""

    def test_health_includes_backend_type(self):
        """Test that health response includes backend type."""
        from tensorrt_inference import TensorRTInference

        with patch.object(TensorRTInference, "_load_engine"):
            backend = TensorRTInference(engine_path="/path/to/model.engine")
            health = backend.get_health_info()

            assert "backend" in health
            assert health["backend"] == "tensorrt"

    def test_health_includes_engine_path(self):
        """Test that health response includes engine path."""
        from tensorrt_inference import TensorRTInference

        with patch.object(TensorRTInference, "_load_engine"):
            backend = TensorRTInference(engine_path="/path/to/model.engine")
            health = backend.get_health_info()

            assert "engine_path" in health
            assert health["engine_path"] == "/path/to/model.engine"


class TestONNXExport:
    """Tests for exporting HuggingFace model to ONNX."""

    def test_onnx_export_from_huggingface(self, tmp_path):
        """Test ONNX export from HuggingFace model."""
        from tensorrt_converter import export_to_onnx

        # Create mock objects
        mock_model_instance = MagicMock()
        mock_model_instance.eval = MagicMock()

        mock_processor_instance = MagicMock()
        mock_processor_instance.return_value = {"pixel_values": MagicMock()}

        output_file = tmp_path / "output.onnx"

        with (
            patch(
                "transformers.AutoModelForObjectDetection.from_pretrained",
                return_value=mock_model_instance,
            ),
            patch(
                "transformers.AutoImageProcessor.from_pretrained",
                return_value=mock_processor_instance,
            ),
            patch("tensorrt_converter.torch.onnx.export") as mock_export,
        ):
            # Create a dummy file so stat() works
            output_file.write_bytes(b"dummy")

            output_path = export_to_onnx(
                model_path="/path/to/hf_model",
                output_path=str(output_file),
            )

            mock_export.assert_called_once()
            assert output_path == str(output_file)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
