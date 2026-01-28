"""Base Class for TensorRT-Accelerated Model Inference.

This module provides an abstract base class for implementing AI models with
TensorRT optimization and automatic PyTorch fallback.

Key features:
- Unified interface for TensorRT and PyTorch inference
- Automatic backend selection based on availability
- Graceful fallback when TensorRT is unavailable
- Warmup support for optimal first-inference performance
- Consistent preprocessing/postprocessing hooks

Usage:
    from ai.common.tensorrt_inference import TensorRTInferenceBase
    from pathlib import Path
    import numpy as np

    class MyModel(TensorRTInferenceBase):
        def _init_pytorch(self):
            self.model = load_my_pytorch_model()

        def _init_tensorrt(self, onnx_path, precision):
            # Convert ONNX to TensorRT
            converter = TensorRTConverter(precision=precision)
            engine_path = converter.convert_onnx_to_trt(
                onnx_path=onnx_path,
                input_shapes={"input": (1, 3, 224, 224)},
            )
            self.trt_engine = TensorRTEngine(engine_path)

        def preprocess(self, inputs):
            # Normalize and prepare inputs
            return {"input": normalized_array}

        def postprocess(self, outputs):
            # Process model outputs
            return results

    # Usage
    model = MyModel(
        model_name="my_model",
        onnx_path=Path("model.onnx"),
        use_tensorrt=True,
    )
    result = model(input_image)

Environment Variables:
- TENSORRT_ENABLED: Global toggle for TensorRT (default: "true")
- TENSORRT_PRECISION: Default precision mode (default: "fp16")
"""

from __future__ import annotations

import logging
import os
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generic, TypeVar

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from .tensorrt_utils import TensorRTEngine

logger = logging.getLogger(__name__)

# Type variables for input/output types
InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")

# Environment configuration
TENSORRT_ENABLED_DEFAULT = os.environ.get("TENSORRT_ENABLED", "true").lower() == "true"
TENSORRT_PRECISION_DEFAULT = os.environ.get("TENSORRT_PRECISION", "fp16")


class TensorRTInferenceBase(ABC, Generic[InputT, OutputT]):
    """Abstract base class for TensorRT-accelerated model inference.

    This class provides a unified interface for AI models that can use
    either TensorRT or PyTorch for inference. It handles automatic
    backend selection, initialization, and fallback logic.

    Subclasses must implement:
    - _init_pytorch(): Initialize PyTorch model (fallback path)
    - _init_tensorrt(): Initialize TensorRT engine
    - preprocess(): Convert raw inputs to model input format
    - postprocess(): Convert model outputs to final format

    Attributes:
        model_name: Human-readable name for logging
        use_tensorrt: Whether TensorRT backend is active
        precision: TensorRT precision mode (fp32, fp16, int8)
        device: CUDA device string
        trt_engine: TensorRT engine (if TensorRT backend)
        pytorch_model: PyTorch model (if PyTorch backend)
    """

    def __init__(
        self,
        model_name: str,
        onnx_path: Path | str | None = None,
        pytorch_model_path: Path | str | None = None,
        use_tensorrt: bool = True,
        precision: str = TENSORRT_PRECISION_DEFAULT,
        device: str = "cuda:0",
        warmup: bool = True,
        warmup_iterations: int = 3,
    ):
        """Initialize the inference model.

        Args:
            model_name: Human-readable name for logging
            onnx_path: Path to ONNX model for TensorRT conversion
            pytorch_model_path: Path to PyTorch model weights
            use_tensorrt: Whether to attempt TensorRT optimization
            precision: TensorRT precision ("fp32", "fp16", or "int8")
            device: CUDA device to use (e.g., "cuda:0")
            warmup: Whether to run warmup inference on initialization
            warmup_iterations: Number of warmup iterations to run
        """
        self.model_name = model_name
        self.onnx_path = Path(onnx_path) if onnx_path else None
        self.pytorch_model_path = Path(pytorch_model_path) if pytorch_model_path else None
        self.precision = precision
        self.device = device
        self._warmup = warmup
        self._warmup_iterations = warmup_iterations

        # Backend state
        self.use_tensorrt = False
        self.trt_engine: TensorRTEngine | None = None
        self.pytorch_model: Any = None

        # Statistics
        self._inference_count = 0
        self._total_inference_time_ms = 0.0

        # Determine backend
        requested_tensorrt = use_tensorrt and TENSORRT_ENABLED_DEFAULT

        if requested_tensorrt and self._tensorrt_available():
            self._try_init_tensorrt()
        else:
            self._init_pytorch_backend()

    def _tensorrt_available(self) -> bool:
        """Check if TensorRT is available and GPU supports it.

        Returns:
            True if TensorRT can be used, False otherwise.
        """
        # Check if TensorRT is installed
        if not self._check_tensorrt_installed():
            return False

        # Check CUDA availability
        if not self._check_cuda_available():
            return False

        # Check ONNX model availability
        return self._check_onnx_model_available()

    def _check_tensorrt_installed(self) -> bool:
        """Check if TensorRT package is installed."""
        try:
            from .tensorrt_utils import is_tensorrt_available

            if not is_tensorrt_available():
                logger.debug(f"[{self.model_name}] TensorRT package not available")
                return False
            return True
        except ImportError:
            logger.debug(f"[{self.model_name}] Could not import tensorrt_utils")
            return False

    def _check_cuda_available(self) -> bool:
        """Check if CUDA is available for TensorRT."""
        try:
            import torch

            if not torch.cuda.is_available():
                logger.debug(f"[{self.model_name}] CUDA not available for TensorRT")
                return False
            return True
        except ImportError:
            logger.debug(f"[{self.model_name}] PyTorch not available")
            return False

    def _check_onnx_model_available(self) -> bool:
        """Check if ONNX model path is valid."""
        if self.onnx_path is None:
            logger.debug(f"[{self.model_name}] No ONNX model path provided for TensorRT")
            return False
        if not self.onnx_path.exists():
            logger.debug(f"[{self.model_name}] ONNX model not found: {self.onnx_path}")
            return False
        return True

    def _try_init_tensorrt(self) -> None:
        """Attempt TensorRT initialization with fallback to PyTorch."""
        try:
            logger.info(
                f"[{self.model_name}] Initializing TensorRT backend (precision={self.precision})"
            )
            self._init_tensorrt(self.onnx_path, self.precision)
            self.use_tensorrt = True
            logger.info(f"[{self.model_name}] TensorRT backend initialized successfully")

            # Run warmup
            if self._warmup:
                self._run_warmup()

        except Exception as e:
            logger.warning(
                f"[{self.model_name}] TensorRT initialization failed: {e}. Falling back to PyTorch."
            )
            self._init_pytorch_backend()

    def _init_pytorch_backend(self) -> None:
        """Initialize PyTorch backend."""
        try:
            logger.info(f"[{self.model_name}] Initializing PyTorch backend")
            self._init_pytorch()
            self.use_tensorrt = False
            logger.info(f"[{self.model_name}] PyTorch backend initialized successfully")

            # Run warmup
            if self._warmup:
                self._run_warmup()

        except Exception as e:
            logger.error(f"[{self.model_name}] PyTorch initialization failed: {e}")
            raise

    def _run_warmup(self) -> None:
        """Run warmup inference iterations.

        Warmup helps trigger JIT compilation (for torch.compile) and
        ensures first real inference has optimal performance.
        """
        try:
            sample_input = self._get_warmup_input()
            if sample_input is None:
                logger.debug(f"[{self.model_name}] No warmup input provided, skipping warmup")
                return

            logger.debug(f"[{self.model_name}] Running {self._warmup_iterations} warmup iterations")

            for i in range(self._warmup_iterations):
                _ = self(sample_input)
                logger.debug(
                    f"[{self.model_name}] Warmup iteration {i + 1}/{self._warmup_iterations}"
                )

            logger.debug(f"[{self.model_name}] Warmup complete")

        except Exception as e:
            logger.warning(f"[{self.model_name}] Warmup failed: {e}")

    def _get_warmup_input(self) -> InputT | None:
        """Get sample input for warmup.

        Override this method to provide a sample input for warmup inference.
        Return None to skip warmup.

        Returns:
            Sample input for warmup, or None to skip
        """
        return None

    @abstractmethod
    def _init_pytorch(self) -> None:
        """Initialize the PyTorch model (fallback backend).

        This method is called when TensorRT is unavailable or fails.
        Implementations should:
        - Load model weights from self.pytorch_model_path
        - Move model to self.device
        - Set model to eval mode
        - Store model in self.pytorch_model

        Raises:
            Exception: If PyTorch model initialization fails
        """
        raise NotImplementedError

    @abstractmethod
    def _init_tensorrt(
        self,
        onnx_path: Path | None,
        precision: str,
    ) -> None:
        """Initialize the TensorRT engine.

        This method is called when TensorRT is requested and available.
        Implementations should:
        - Create TensorRTConverter with appropriate settings
        - Convert ONNX model to TensorRT engine
        - Store engine in self.trt_engine

        Args:
            onnx_path: Path to the ONNX model file
            precision: TensorRT precision mode ("fp32", "fp16", "int8")

        Raises:
            Exception: If TensorRT engine building fails
        """
        raise NotImplementedError

    @abstractmethod
    def preprocess(self, inputs: InputT) -> dict[str, NDArray[Any]]:
        """Preprocess inputs for model inference.

        Convert raw inputs (e.g., PIL Images, file paths) to NumPy arrays
        suitable for model inference.

        Args:
            inputs: Raw input data (type depends on model)

        Returns:
            Dictionary mapping input tensor names to NumPy arrays
        """
        raise NotImplementedError

    @abstractmethod
    def postprocess(self, outputs: dict[str, NDArray[Any]]) -> OutputT:
        """Postprocess model outputs.

        Convert raw model outputs to the final result format.

        Args:
            outputs: Dictionary mapping output tensor names to NumPy arrays

        Returns:
            Processed output (type depends on model)
        """
        raise NotImplementedError

    def _infer_tensorrt(
        self,
        preprocessed: dict[str, NDArray[Any]],
    ) -> dict[str, NDArray[Any]]:
        """Run inference with TensorRT engine.

        Args:
            preprocessed: Preprocessed input arrays

        Returns:
            Model output arrays
        """
        if self.trt_engine is None:
            raise RuntimeError("TensorRT engine not initialized")

        return self.trt_engine.infer(preprocessed)

    def _infer_pytorch(
        self,
        preprocessed: dict[str, NDArray[Any]],
    ) -> dict[str, NDArray[Any]]:
        """Run inference with PyTorch model.

        Args:
            preprocessed: Preprocessed input arrays

        Returns:
            Model output arrays
        """
        import torch

        if self.pytorch_model is None:
            raise RuntimeError("PyTorch model not initialized")

        # Convert inputs to PyTorch tensors
        inputs_torch = {
            name: torch.from_numpy(arr).to(self.device) for name, arr in preprocessed.items()
        }

        # Run inference
        with torch.no_grad():
            outputs_torch = self.pytorch_model(**inputs_torch)

        # Convert outputs to NumPy
        if isinstance(outputs_torch, torch.Tensor):
            outputs_torch = {"output": outputs_torch}
        elif not isinstance(outputs_torch, dict):
            # Handle tuple/list outputs
            outputs_torch = {f"output_{i}": out for i, out in enumerate(outputs_torch)}

        outputs_np: dict[str, NDArray[Any]] = {}
        for name, tensor in outputs_torch.items():
            if isinstance(tensor, torch.Tensor):
                outputs_np[name] = tensor.cpu().numpy()
            else:
                outputs_np[name] = tensor

        return outputs_np

    def __call__(self, inputs: InputT) -> OutputT:
        """Run inference with automatic backend selection.

        This is the main entry point for inference. It handles:
        1. Preprocessing raw inputs
        2. Running inference (TensorRT or PyTorch)
        3. Postprocessing outputs
        4. Timing and statistics

        Args:
            inputs: Raw input data

        Returns:
            Processed output
        """
        start_time = time.perf_counter()

        # Preprocess
        preprocessed = self.preprocess(inputs)

        # Run inference with appropriate backend
        if self.use_tensorrt:
            outputs = self._infer_tensorrt(preprocessed)
        else:
            outputs = self._infer_pytorch(preprocessed)

        # Postprocess
        result = self.postprocess(outputs)

        # Update statistics
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        self._inference_count += 1
        self._total_inference_time_ms += elapsed_ms

        return result

    def infer_batch(self, inputs_list: list[InputT]) -> list[OutputT]:
        """Run batched inference on multiple inputs.

        Args:
            inputs_list: List of raw inputs

        Returns:
            List of processed outputs
        """
        if not inputs_list:
            return []

        # Simple sequential processing for now
        # Subclasses can override for true batch processing
        return [self(inp) for inp in inputs_list]

    def get_backend_name(self) -> str:
        """Get the name of the active inference backend.

        Returns:
            "tensorrt" or "pytorch"
        """
        return "tensorrt" if self.use_tensorrt else "pytorch"

    def get_statistics(self) -> dict[str, Any]:
        """Get inference statistics.

        Returns:
            Dictionary with inference statistics
        """
        avg_time_ms = (
            self._total_inference_time_ms / self._inference_count
            if self._inference_count > 0
            else 0.0
        )

        return {
            "model_name": self.model_name,
            "backend": self.get_backend_name(),
            "precision": self.precision if self.use_tensorrt else "fp32",
            "device": self.device,
            "inference_count": self._inference_count,
            "total_inference_time_ms": self._total_inference_time_ms,
            "avg_inference_time_ms": avg_time_ms,
        }

    def reset_statistics(self) -> None:
        """Reset inference statistics."""
        self._inference_count = 0
        self._total_inference_time_ms = 0.0


class TensorRTDetectionModel(TensorRTInferenceBase[Any, list[dict[str, Any]]]):
    """Specialized base class for object detection models.

    This class extends TensorRTInferenceBase with detection-specific
    functionality like NMS postprocessing and bounding box scaling.

    Attributes:
        confidence_threshold: Minimum confidence for detections
        nms_threshold: NMS IoU threshold
        class_names: List of class names for label mapping
    """

    def __init__(
        self,
        model_name: str,
        confidence_threshold: float = 0.5,
        nms_threshold: float = 0.45,
        class_names: list[str] | None = None,
        **kwargs: Any,
    ):
        """Initialize detection model.

        Args:
            model_name: Human-readable model name
            confidence_threshold: Minimum confidence threshold
            nms_threshold: NMS IoU threshold
            class_names: List of class names
            **kwargs: Additional arguments for TensorRTInferenceBase
        """
        self.confidence_threshold = confidence_threshold
        self.nms_threshold = nms_threshold
        self.class_names = class_names or []

        super().__init__(model_name=model_name, **kwargs)

    def apply_nms(
        self,
        boxes: NDArray[Any],
        scores: NDArray[Any],
        class_ids: NDArray[Any],
    ) -> tuple[NDArray[Any], NDArray[Any], NDArray[Any]]:
        """Apply Non-Maximum Suppression to detection results.

        Args:
            boxes: Bounding boxes array (N, 4) in xyxy format
            scores: Confidence scores array (N,)
            class_ids: Class ID array (N,)

        Returns:
            Tuple of (filtered_boxes, filtered_scores, filtered_class_ids)
        """
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

    def format_detections(
        self,
        boxes: NDArray[Any],
        scores: NDArray[Any],
        class_ids: NDArray[Any],
        image_size: tuple[int, int] | None = None,
    ) -> list[dict[str, Any]]:
        """Format detection results as list of dictionaries.

        Args:
            boxes: Bounding boxes (N, 4) in xyxy format
            scores: Confidence scores (N,)
            class_ids: Class IDs (N,)
            image_size: Original image size (width, height) for scaling (reserved)

        Returns:
            List of detection dictionaries with keys:
            - bbox: [x1, y1, x2, y2]
            - confidence: float
            - class_id: int
            - class_name: str (if class_names available)
        """
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


class TensorRTClassificationModel(TensorRTInferenceBase[Any, dict[str, Any]]):
    """Specialized base class for classification models.

    This class extends TensorRTInferenceBase with classification-specific
    functionality like softmax and top-k predictions.

    Attributes:
        class_names: List of class names for label mapping
        top_k: Number of top predictions to return
    """

    def __init__(
        self,
        model_name: str,
        class_names: list[str] | None = None,
        top_k: int = 5,
        **kwargs: Any,
    ):
        """Initialize classification model.

        Args:
            model_name: Human-readable model name
            class_names: List of class names
            top_k: Number of top predictions to return
            **kwargs: Additional arguments for TensorRTInferenceBase
        """
        self.class_names = class_names or []
        self.top_k = top_k

        super().__init__(model_name=model_name, **kwargs)

    def get_top_predictions(
        self,
        logits: NDArray[Any],
        apply_softmax: bool = True,
    ) -> dict[str, Any]:
        """Get top-k predictions from logits.

        Args:
            logits: Model output logits (num_classes,) or (batch, num_classes)
            apply_softmax: Whether to apply softmax to logits

        Returns:
            Dictionary with:
            - top_class_id: ID of top prediction
            - top_class_name: Name of top prediction (if available)
            - top_confidence: Confidence of top prediction
            - predictions: List of top-k (class_id, class_name, confidence)
        """
        import numpy as np

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
