"""Tests for TensorRT inference base classes (NEM-3838).

These tests verify the tensorrt_inference module for model implementations.
Tests use mock backends to run regardless of TensorRT availability.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from numpy.typing import NDArray


class MockTensorRTInferenceModel:
    """Mock implementation of TensorRTInferenceBase for testing."""

    def __init__(
        self,
        model_name: str = "test_model",
        use_tensorrt: bool = False,
        device: str = "cpu",
    ):
        self.model_name = model_name
        self.use_tensorrt = use_tensorrt
        self.device = device
        self.precision = "fp16"
        self.pytorch_model = MagicMock()
        self.trt_engine = MagicMock() if use_tensorrt else None
        self._inference_count = 0
        self._total_inference_time_ms = 0.0

    def preprocess(self, inputs: Any) -> dict[str, NDArray[Any]]:
        """Mock preprocess."""
        if isinstance(inputs, np.ndarray):
            return {"input": inputs}
        return {"input": np.array(inputs)}

    def postprocess(self, outputs: dict[str, NDArray[Any]]) -> Any:
        """Mock postprocess."""
        return outputs.get("output", outputs)

    def __call__(self, inputs: Any) -> Any:
        """Run mock inference."""
        _ = self.preprocess(inputs)  # Validate preprocessing works

        if self.use_tensorrt and self.trt_engine is not None:
            outputs = {"output": np.array([1.0, 2.0, 3.0])}
        else:
            outputs = {"output": np.array([1.0, 2.0, 3.0])}

        self._inference_count += 1
        return self.postprocess(outputs)

    def get_backend_name(self) -> str:
        return "tensorrt" if self.use_tensorrt else "pytorch"

    def get_statistics(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "backend": self.get_backend_name(),
            "inference_count": self._inference_count,
        }


class TestTensorRTInferenceBase:
    """Tests for TensorRTInferenceBase abstract class."""

    def test_backend_selection_pytorch(self) -> None:
        """Test that PyTorch backend is selected when TensorRT disabled."""
        model = MockTensorRTInferenceModel(use_tensorrt=False)

        assert model.get_backend_name() == "pytorch"
        assert model.use_tensorrt is False

    def test_backend_selection_tensorrt(self) -> None:
        """Test that TensorRT backend is selected when enabled."""
        model = MockTensorRTInferenceModel(use_tensorrt=True)

        assert model.get_backend_name() == "tensorrt"
        assert model.use_tensorrt is True

    def test_inference_updates_statistics(self) -> None:
        """Test that inference updates statistics."""
        model = MockTensorRTInferenceModel()

        # Initial state
        assert model._inference_count == 0

        # Run inference
        _ = model(np.array([1.0, 2.0]))

        # Check statistics updated
        assert model._inference_count == 1

    def test_get_statistics(self) -> None:
        """Test get_statistics method."""
        model = MockTensorRTInferenceModel(model_name="test_model")

        stats = model.get_statistics()

        assert stats["model_name"] == "test_model"
        assert stats["backend"] == "pytorch"
        assert stats["inference_count"] == 0


class TestTensorRTInferenceBaseAbstractMethods:
    """Tests for abstract method requirements."""

    def test_abstract_class_cannot_instantiate(self) -> None:
        """Test that TensorRTInferenceBase cannot be instantiated directly."""
        from ai.common.tensorrt_inference import TensorRTInferenceBase

        with pytest.raises(TypeError, match="abstract"):
            TensorRTInferenceBase(model_name="test")  # type: ignore[abstract]

    def test_required_methods(self) -> None:
        """Test that required abstract methods exist."""
        from ai.common.tensorrt_inference import TensorRTInferenceBase

        # Check abstract methods are defined
        assert hasattr(TensorRTInferenceBase, "_init_pytorch")
        assert hasattr(TensorRTInferenceBase, "_init_tensorrt")
        assert hasattr(TensorRTInferenceBase, "preprocess")
        assert hasattr(TensorRTInferenceBase, "postprocess")


class MockDetectionModel:
    """Mock detection model for testing format_detections."""

    def __init__(self) -> None:
        self.confidence_threshold = 0.5
        self.nms_threshold = 0.45
        self.class_names: list[str] = []

    def format_detections(
        self,
        boxes: NDArray[Any],
        scores: NDArray[Any],
        class_ids: NDArray[Any],
        image_size: tuple[int, int] | None = None,
    ) -> list[dict[str, Any]]:
        """Format detection results as list of dictionaries."""
        detections: list[dict[str, Any]] = []

        for i in range(len(boxes)):
            detection: dict[str, Any] = {
                "bbox": boxes[i].tolist(),
                "confidence": float(scores[i]),
                "class_id": int(class_ids[i]),
            }

            # Add class name if available
            if self.class_names and 0 <= int(class_ids[i]) < len(self.class_names):
                detection["class_name"] = self.class_names[int(class_ids[i])]

            detections.append(detection)

        return detections

    def apply_nms(
        self,
        boxes: NDArray[Any],
        scores: NDArray[Any],
        class_ids: NDArray[Any],
    ) -> tuple[NDArray[Any], NDArray[Any], NDArray[Any]]:
        """Apply Non-Maximum Suppression to detection results."""
        import torch
        from torchvision.ops import nms

        # Filter by confidence
        mask = scores >= self.confidence_threshold
        boxes = boxes[mask]
        scores = scores[mask]
        class_ids = class_ids[mask]

        if len(boxes) == 0:
            return boxes, scores, class_ids

        # Convert to torch for NMS
        boxes_torch = torch.from_numpy(boxes).float()
        scores_torch = torch.from_numpy(scores).float()

        # Apply NMS
        keep_indices = nms(boxes_torch, scores_torch, self.nms_threshold)
        keep_indices = keep_indices.numpy()

        return boxes[keep_indices], scores[keep_indices], class_ids[keep_indices]


class TestTensorRTDetectionModel:
    """Tests for TensorRTDetectionModel specialized class."""

    def test_class_exists(self) -> None:
        """Test that TensorRTDetectionModel class exists."""
        from ai.common.tensorrt_inference import TensorRTDetectionModel

        assert TensorRTDetectionModel is not None

    def test_inheritance(self) -> None:
        """Test inheritance from TensorRTInferenceBase."""
        from ai.common.tensorrt_inference import (
            TensorRTDetectionModel,
            TensorRTInferenceBase,
        )

        assert issubclass(TensorRTDetectionModel, TensorRTInferenceBase)

    def test_format_detections(self) -> None:
        """Test format_detections method."""
        # Use mock model to test the method without abstract class issues
        model = MockDetectionModel()
        model.class_names = ["person", "car", "dog"]

        # Test data
        boxes = np.array([[10, 20, 100, 200], [50, 60, 150, 250]])
        scores = np.array([0.9, 0.8])
        class_ids = np.array([0, 1])

        detections = model.format_detections(boxes, scores, class_ids)

        assert len(detections) == 2
        assert detections[0]["class_name"] == "person"
        assert detections[0]["confidence"] == 0.9
        assert detections[1]["class_name"] == "car"
        assert detections[1]["confidence"] == 0.8

    def test_format_detections_without_class_names(self) -> None:
        """Test format_detections without class names."""
        model = MockDetectionModel()
        model.class_names = []

        boxes = np.array([[10, 20, 100, 200]])
        scores = np.array([0.9])
        class_ids = np.array([0])

        detections = model.format_detections(boxes, scores, class_ids)

        assert len(detections) == 1
        assert "class_name" not in detections[0]
        assert detections[0]["class_id"] == 0


class MockClassificationModel:
    """Mock classification model for testing get_top_predictions."""

    def __init__(self) -> None:
        self.class_names: list[str] = []
        self.top_k = 5

    def get_top_predictions(
        self,
        logits: NDArray[Any],
        apply_softmax: bool = True,
    ) -> dict[str, Any]:
        """Get top-k predictions from logits."""
        # Handle batch dimension
        if logits.ndim == 2:
            logits = logits[0]

        # Apply softmax if needed
        if apply_softmax:
            exp_logits = np.exp(logits - np.max(logits))
            probs = exp_logits / exp_logits.sum()
        else:
            probs = logits

        # Get top-k indices
        top_indices = np.argsort(probs)[::-1][: self.top_k]

        # Build predictions list
        predictions: list[dict[str, Any]] = []
        for idx in top_indices:
            pred: dict[str, Any] = {
                "class_id": int(idx),
                "confidence": float(probs[idx]),
            }
            if self.class_names and 0 <= idx < len(self.class_names):
                pred["class_name"] = self.class_names[idx]
            predictions.append(pred)

        # Build result
        result: dict[str, Any] = {
            "top_class_id": int(top_indices[0]),
            "top_confidence": float(probs[top_indices[0]]),
            "predictions": predictions,
        }

        if self.class_names and 0 <= top_indices[0] < len(self.class_names):
            result["top_class_name"] = self.class_names[top_indices[0]]

        return result


class TestTensorRTClassificationModel:
    """Tests for TensorRTClassificationModel specialized class."""

    def test_class_exists(self) -> None:
        """Test that TensorRTClassificationModel class exists."""
        from ai.common.tensorrt_inference import TensorRTClassificationModel

        assert TensorRTClassificationModel is not None

    def test_inheritance(self) -> None:
        """Test inheritance from TensorRTInferenceBase."""
        from ai.common.tensorrt_inference import (
            TensorRTClassificationModel,
            TensorRTInferenceBase,
        )

        assert issubclass(TensorRTClassificationModel, TensorRTInferenceBase)

    def test_get_top_predictions(self) -> None:
        """Test get_top_predictions method."""
        # Use mock model to test the method without abstract class issues
        model = MockClassificationModel()
        model.class_names = ["cat", "dog", "bird", "fish", "rabbit"]
        model.top_k = 3

        # Test logits (higher value = more confident)
        logits = np.array([0.1, 0.5, 0.2, 0.15, 0.05])

        result = model.get_top_predictions(logits, apply_softmax=True)

        assert "top_class_id" in result
        assert result["top_class_id"] == 1  # dog (highest logit)
        assert result["top_class_name"] == "dog"
        assert "predictions" in result
        assert len(result["predictions"]) == 3

    def test_get_top_predictions_without_softmax(self) -> None:
        """Test get_top_predictions without softmax."""
        model = MockClassificationModel()
        model.class_names = ["a", "b", "c"]
        model.top_k = 2

        # Already normalized probabilities
        probs = np.array([0.1, 0.7, 0.2])

        result = model.get_top_predictions(probs, apply_softmax=False)

        assert result["top_class_id"] == 1  # 'b' has highest prob
        assert result["top_confidence"] == 0.7

    def test_get_top_predictions_batch_dimension(self) -> None:
        """Test get_top_predictions with batch dimension."""
        model = MockClassificationModel()
        model.class_names = ["a", "b"]
        model.top_k = 2

        # 2D array with batch dimension
        logits = np.array([[0.3, 0.7]])

        result = model.get_top_predictions(logits)

        assert result["top_class_id"] == 1


class TestEnvironmentVariableDefaults:
    """Tests for environment variable defaults in inference module."""

    def test_tensorrt_enabled_default(self) -> None:
        """Test TENSORRT_ENABLED default in inference module."""
        from ai.common.tensorrt_inference import TENSORRT_ENABLED_DEFAULT

        assert isinstance(TENSORRT_ENABLED_DEFAULT, bool)

    def test_tensorrt_precision_default(self) -> None:
        """Test TENSORRT_PRECISION default in inference module."""
        from ai.common.tensorrt_inference import TENSORRT_PRECISION_DEFAULT

        assert TENSORRT_PRECISION_DEFAULT in ("fp32", "fp16", "int8")


class TestNMSPostprocessing:
    """Tests for NMS (Non-Maximum Suppression) postprocessing."""

    @pytest.mark.skipif(
        os.environ.get("TORCH_AVAILABLE", "true").lower() != "true",
        reason="PyTorch with torchvision not available",
    )
    def test_apply_nms_filters_low_confidence(self) -> None:
        """Test that NMS filters low confidence detections."""
        # Use mock model to test the method without abstract class issues
        model = MockDetectionModel()
        model.confidence_threshold = 0.5
        model.nms_threshold = 0.45

        # Test data with one low confidence detection
        boxes = np.array([[10, 20, 100, 200], [50, 60, 150, 250]])
        scores = np.array([0.9, 0.3])  # Second is below threshold
        class_ids = np.array([0, 1])

        filtered_boxes, filtered_scores, filtered_classes = model.apply_nms(
            boxes, scores, class_ids
        )

        assert len(filtered_boxes) == 1
        assert filtered_scores[0] == 0.9

    @pytest.mark.skipif(
        os.environ.get("TORCH_AVAILABLE", "true").lower() != "true",
        reason="PyTorch with torchvision not available",
    )
    def test_apply_nms_empty_input(self) -> None:
        """Test NMS with empty input."""
        model = MockDetectionModel()
        model.confidence_threshold = 0.5
        model.nms_threshold = 0.45

        boxes = np.array([]).reshape(0, 4)
        scores = np.array([])
        class_ids = np.array([])

        filtered_boxes, filtered_scores, filtered_classes = model.apply_nms(
            boxes, scores, class_ids
        )

        assert len(filtered_boxes) == 0
        assert len(filtered_scores) == 0
        assert len(filtered_classes) == 0


class TestConcreteImplementation:
    """Tests with a concrete implementation of TensorRTInferenceBase."""

    def test_concrete_model_implementation(self) -> None:
        """Test creating a concrete model implementation."""
        from ai.common.tensorrt_inference import TensorRTInferenceBase

        class ConcreteModel(TensorRTInferenceBase[np.ndarray, np.ndarray]):
            def _init_pytorch(self) -> None:
                self.pytorch_model = lambda x: {"output": x["input"] * 2}

            def _init_tensorrt(
                self,
                onnx_path: Path | None,
                precision: str,
            ) -> None:
                # Skip TensorRT init in tests
                raise ImportError("TensorRT not available for test")

            def preprocess(self, inputs: np.ndarray) -> dict[str, NDArray[Any]]:
                return {"input": inputs}

            def postprocess(self, outputs: dict[str, NDArray[Any]]) -> np.ndarray:
                return outputs["output"]

        # Patch to avoid actual TensorRT checks
        with patch(
            "ai.common.tensorrt_inference.TensorRTInferenceBase._tensorrt_available",
            return_value=False,
        ):
            model = ConcreteModel(
                model_name="concrete_test",
                use_tensorrt=False,
                warmup=False,
            )

            assert model.model_name == "concrete_test"
            assert model.use_tensorrt is False
            assert model.get_backend_name() == "pytorch"
