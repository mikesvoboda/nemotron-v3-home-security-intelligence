"""TensorRT Inference Backend for RT-DETR.

Provides TensorRT-accelerated inference with the same interface as the
PyTorch backend, enabling 2-3x speedup for object detection.

Usage:
    from tensorrt_inference import TensorRTInference

    # Load TensorRT engine
    backend = TensorRTInference(
        engine_path="/path/to/model.engine",
        confidence_threshold=0.5,
    )

    # Run detection (same interface as PyTorch)
    detections, inference_time_ms = backend.detect(image)

Environment Variables:
    RTDETR_BACKEND: Backend selection ('pytorch' or 'tensorrt'). Default: 'pytorch'
    RTDETR_ENGINE_PATH: Path to TensorRT engine file (required for tensorrt backend)
    RTDETR_CONFIDENCE: Detection confidence threshold (default: 0.5)
"""

import logging
import os
import time
from typing import Any

import numpy as np
import torch
from PIL import Image

logger = logging.getLogger(__name__)

# Security-relevant classes for home monitoring (same as PyTorch backend)
SECURITY_CLASSES = {"person", "car", "truck", "dog", "cat", "bird", "bicycle", "motorcycle", "bus"}

# COCO class labels (RT-DETR is trained on COCO)
COCO_LABELS = {
    0: "person",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    4: "airplane",
    5: "bus",
    6: "train",
    7: "truck",
    8: "boat",
    9: "traffic light",
    10: "fire hydrant",
    11: "stop sign",
    12: "parking meter",
    13: "bench",
    14: "bird",
    15: "cat",
    16: "dog",
    17: "horse",
    18: "sheep",
    19: "cow",
    20: "elephant",
    21: "bear",
    22: "zebra",
    23: "giraffe",
    24: "backpack",
    25: "umbrella",
    26: "handbag",
    27: "tie",
    28: "suitcase",
    29: "frisbee",
    30: "skis",
    31: "snowboard",
    32: "sports ball",
    33: "kite",
    34: "baseball bat",
    35: "baseball glove",
    36: "skateboard",
    37: "surfboard",
    38: "tennis racket",
    39: "bottle",
    40: "wine glass",
    41: "cup",
    42: "fork",
    43: "knife",
    44: "spoon",
    45: "bowl",
    46: "banana",
    47: "apple",
    48: "sandwich",
    49: "orange",
    50: "broccoli",
    51: "carrot",
    52: "hot dog",
    53: "pizza",
    54: "donut",
    55: "cake",
    56: "chair",
    57: "couch",
    58: "potted plant",
    59: "bed",
    60: "dining table",
    61: "toilet",
    62: "tv",
    63: "laptop",
    64: "mouse",
    65: "remote",
    66: "keyboard",
    67: "cell phone",
    68: "microwave",
    69: "oven",
    70: "toaster",
    71: "sink",
    72: "refrigerator",
    73: "book",
    74: "clock",
    75: "vase",
    76: "scissors",
    77: "teddy bear",
    78: "hair drier",
    79: "toothbrush",
}


def get_inference_backend() -> str:
    """Get the configured inference backend.

    Returns:
        Backend type: 'pytorch' or 'tensorrt'.
    """
    backend = os.environ.get("RTDETR_BACKEND", "pytorch").lower()
    if backend not in ("pytorch", "tensorrt"):
        logger.warning(f"Invalid RTDETR_BACKEND '{backend}', falling back to 'pytorch'")
        return "pytorch"
    return backend


class TensorRTInference:
    """TensorRT inference backend for RT-DETR.

    Provides the same interface as the PyTorch RTDETRv2Model class for
    seamless backend switching.

    Attributes:
        engine_path: Path to the TensorRT engine file.
        device: CUDA device to use (e.g., 'cuda:0').
        confidence_threshold: Minimum confidence for detections.
        engine: Loaded TensorRT engine.
        context: TensorRT execution context.
    """

    def __init__(
        self,
        engine_path: str,
        device: str = "cuda:0",
        confidence_threshold: float = 0.5,
    ):
        """Initialize TensorRT inference backend.

        Args:
            engine_path: Path to TensorRT engine file.
            device: CUDA device (e.g., 'cuda:0'). Default: 'cuda:0'.
            confidence_threshold: Min confidence threshold. Default: 0.5.

        Raises:
            FileNotFoundError: If engine file doesn't exist.
            RuntimeError: If engine loading fails.
        """
        self.engine_path = engine_path
        self.device = device
        self.confidence_threshold = confidence_threshold

        # TensorRT objects
        self.engine: Any = None
        self.context: Any = None
        self.stream: Any = None

        # Binding info
        self._input_binding: dict[str, Any] = {}
        self._output_bindings: dict[str, Any] = {}

        # Load engine
        self._load_engine()

        logger.info("TensorRT backend initialized:")
        logger.info(f"  Engine: {self.engine_path}")
        logger.info(f"  Device: {self.device}")
        logger.info(f"  Confidence threshold: {self.confidence_threshold}")

    def _load_engine(self) -> None:
        """Load TensorRT engine from file.

        Raises:
            FileNotFoundError: If engine file doesn't exist.
            ImportError: If TensorRT is not installed.
            RuntimeError: If engine loading fails.
        """
        if not os.path.exists(self.engine_path):
            raise FileNotFoundError(f"TensorRT engine not found: {self.engine_path}")

        try:
            import importlib.util

            if importlib.util.find_spec("tensorrt") is None:
                raise ImportError("tensorrt module not found")
        except ImportError as e:
            raise ImportError(
                "TensorRT is not installed. Install with: pip install tensorrt"
            ) from e

        logger.info(f"Loading TensorRT engine: {self.engine_path}")

        # Create runtime and deserialize engine
        self.engine = self._deserialize_engine()

        # Create execution context
        self.context = self.engine.create_execution_context()

        # Create CUDA stream
        self.stream = torch.cuda.Stream(device=self.device)

        # Set up bindings
        self._setup_bindings()

        logger.info("TensorRT engine loaded successfully")

    def _deserialize_engine(self) -> Any:
        """Deserialize TensorRT engine from file.

        Returns:
            Deserialized TensorRT engine.
        """
        import tensorrt as trt

        trt_logger = trt.Logger(trt.Logger.WARNING)
        runtime = trt.Runtime(trt_logger)

        with open(self.engine_path, "rb") as f:  # nosemgrep: path-traversal-open
            engine_data = f.read()

        engine = runtime.deserialize_cuda_engine(engine_data)
        if engine is None:
            raise RuntimeError("Failed to deserialize TensorRT engine")

        return engine

    def _setup_bindings(self) -> None:
        """Set up input/output bindings for the engine."""
        import tensorrt as trt

        for i in range(self.engine.num_io_tensors):
            name = self.engine.get_tensor_name(i)
            dtype = self.engine.get_tensor_dtype(name)
            shape = self.engine.get_tensor_shape(name)
            mode = self.engine.get_tensor_mode(name)

            # Convert TensorRT dtype to numpy dtype
            np_dtype = trt.nptype(dtype)

            binding_info = {
                "name": name,
                "shape": tuple(shape),
                "dtype": np_dtype,
            }

            if mode == trt.TensorIOMode.INPUT:
                self._input_binding = binding_info
                logger.debug(f"Input: {name}, shape={shape}, dtype={np_dtype}")
            else:
                self._output_bindings[name] = binding_info
                logger.debug(f"Output: {name}, shape={shape}, dtype={np_dtype}")

    def _preprocess(self, image: Image.Image) -> np.ndarray:
        """Preprocess image for TensorRT inference.

        Args:
            image: PIL Image to preprocess.

        Returns:
            Preprocessed numpy array ready for inference.
        """
        # Convert to RGB if needed
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Resize to expected input size (from binding shape)
        # Input shape is typically [batch, channels, height, width]
        input_shape = self._input_binding["shape"]
        target_h, target_w = input_shape[2], input_shape[3]
        image = image.resize((target_w, target_h), Image.BILINEAR)

        # Convert to numpy and normalize
        img_array = np.array(image, dtype=np.float32) / 255.0

        # Normalize with ImageNet mean/std
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        img_array = (img_array - mean) / std

        # Transpose to CHW format and add batch dimension
        img_array = img_array.transpose(2, 0, 1)
        img_array = np.expand_dims(img_array, axis=0)

        return img_array.astype(np.float32)

    def _run_inference(self, input_data: np.ndarray) -> dict[str, np.ndarray]:
        """Run TensorRT inference.

        Args:
            input_data: Preprocessed input array.

        Returns:
            Dictionary of output name to output array.
        """
        # Allocate input tensor
        input_tensor = torch.from_numpy(input_data).to(self.device)

        # Allocate output tensors
        outputs = {}
        for name, binding in self._output_bindings.items():
            shape = binding["shape"]
            # Handle dynamic shapes
            shape = tuple(max(1, s) for s in shape)
            outputs[name] = torch.empty(shape, dtype=torch.float32, device=self.device)

        # Set tensor addresses
        self.context.set_tensor_address(
            self._input_binding["name"],
            input_tensor.data_ptr(),
        )
        for name, tensor in outputs.items():
            self.context.set_tensor_address(name, tensor.data_ptr())

        # Run inference
        self.context.execute_async_v3(stream_handle=self.stream.cuda_stream)
        self.stream.synchronize()

        # Convert to numpy
        return {name: tensor.cpu().numpy() for name, tensor in outputs.items()}

    def _postprocess(
        self,
        outputs: dict[str, np.ndarray],
        original_size: tuple[int, int],
    ) -> list[dict[str, Any]]:
        """Postprocess TensorRT outputs to detection format.

        Args:
            outputs: Raw model outputs (logits, pred_boxes).
            original_size: Original image size (width, height).

        Returns:
            List of detection dictionaries.
        """
        # Get logits and boxes
        logits = outputs.get("logits", next(iter(outputs.values())))
        pred_boxes = outputs.get("pred_boxes")

        if pred_boxes is None:
            # Try to find boxes output by name pattern
            for name, value in outputs.items():
                if "box" in name.lower():
                    pred_boxes = value
                    break

        if pred_boxes is None:
            logger.warning("No bounding box output found")
            return []

        # Apply softmax to logits to get probabilities
        probs = self._softmax(logits[0])  # Remove batch dimension

        # Get max probability and class for each detection
        max_probs = np.max(probs, axis=-1)
        class_ids = np.argmax(probs, axis=-1)

        detections = []
        original_w, original_h = original_size

        for i, (prob, class_id) in enumerate(zip(max_probs, class_ids, strict=False)):
            if prob < self.confidence_threshold:
                continue

            # Get class name
            class_name = COCO_LABELS.get(class_id, f"class_{class_id}")

            # Filter to security-relevant classes
            if class_name not in SECURITY_CLASSES:
                continue

            # Get bounding box (format: cx, cy, w, h normalized)
            cx, cy, w, h = pred_boxes[0, i]

            # Convert to x1, y1, x2, y2 pixel coordinates
            x1 = int((cx - w / 2) * original_w)
            y1 = int((cy - h / 2) * original_h)
            x2 = int((cx + w / 2) * original_w)
            y2 = int((cy + h / 2) * original_h)

            # Clamp to image bounds
            x1 = max(0, min(x1, original_w))
            y1 = max(0, min(y1, original_h))
            x2 = max(0, min(x2, original_w))
            y2 = max(0, min(y2, original_h))

            detections.append(
                {
                    "class": class_name,
                    "confidence": float(prob),
                    "bbox": {
                        "x": x1,
                        "y": y1,
                        "width": x2 - x1,
                        "height": y2 - y1,
                    },
                }
            )

        return detections

    @staticmethod
    def _softmax(x: np.ndarray) -> np.ndarray:
        """Compute softmax along last axis."""
        exp_x = np.exp(x - np.max(x, axis=-1, keepdims=True))
        return exp_x / np.sum(exp_x, axis=-1, keepdims=True)

    def detect(self, image: Image.Image) -> tuple[list[dict[str, Any]], float]:
        """Run object detection on an image.

        Args:
            image: PIL Image to detect objects in.

        Returns:
            Tuple of (detections list, inference_time_ms).
        """
        start_time = time.perf_counter()

        # Store original size
        original_size = image.size  # (width, height)

        # Preprocess
        input_data = self._preprocess(image)

        # Run inference
        outputs = self._run_inference(input_data)

        # Postprocess
        detections = self._postprocess(outputs, original_size)

        inference_time_ms = (time.perf_counter() - start_time) * 1000

        return detections, inference_time_ms

    def detect_batch(
        self,
        images: list[Image.Image],
    ) -> tuple[list[list[dict[str, Any]]], float]:
        """Run batch object detection on multiple images.

        Args:
            images: List of PIL Images.

        Returns:
            Tuple of (list of detections per image, total_inference_time_ms).
        """
        start_time = time.perf_counter()
        all_detections = []

        # Process each image (sequential for now, batch support requires dynamic shapes)
        for image in images:
            detections, _ = self.detect(image)
            all_detections.append(detections)

        total_time_ms = (time.perf_counter() - start_time) * 1000

        return all_detections, total_time_ms

    def _warmup(self, num_iterations: int = 3) -> None:
        """Warmup the engine with dummy inputs.

        Args:
            num_iterations: Number of warmup iterations.
        """
        logger.info(f"Warming up TensorRT engine with {num_iterations} iterations...")

        # Create dummy image matching input shape
        input_shape = self._input_binding["shape"]
        dummy_h, dummy_w = input_shape[2], input_shape[3]
        dummy_image = Image.new("RGB", (dummy_w, dummy_h), color=(128, 128, 128))

        for i in range(num_iterations):
            try:
                self._run_inference(self._preprocess(dummy_image))
                logger.info(f"Warmup iteration {i + 1}/{num_iterations} complete")
            except Exception as e:
                logger.warning(f"Warmup iteration {i + 1} failed: {e}")

        logger.info("Warmup complete")

    def get_health_info(self) -> dict[str, Any]:
        """Get health information for the backend.

        Returns:
            Dictionary with health status information.
        """
        return {
            "backend": "tensorrt",
            "engine_path": self.engine_path,
            "device": self.device,
            "confidence_threshold": self.confidence_threshold,
            "engine_loaded": self.engine is not None,
        }


def create_inference_backend(
    model_path: str | None = None,
    engine_path: str | None = None,
    confidence_threshold: float = 0.5,
    device: str = "cuda:0",
) -> Any:
    """Factory function to create the appropriate inference backend.

    Args:
        model_path: Path to HuggingFace model (for PyTorch backend).
        engine_path: Path to TensorRT engine (for TensorRT backend).
        confidence_threshold: Detection confidence threshold.
        device: CUDA device to use.

    Returns:
        Inference backend instance (RTDETRv2Model or TensorRTInference).

    Raises:
        ValueError: If required paths are not provided for the selected backend.
    """
    backend_type = get_inference_backend()

    if backend_type == "tensorrt":
        if engine_path is None:
            engine_path = os.environ.get("RTDETR_ENGINE_PATH")
        if engine_path is None:
            raise ValueError("TensorRT backend requires engine_path or RTDETR_ENGINE_PATH env var")

        return TensorRTInference(
            engine_path=engine_path,
            device=device,
            confidence_threshold=confidence_threshold,
        )
    else:
        # Import PyTorch backend
        from model import RTDETRv2Model

        if model_path is None:
            model_path = os.environ.get(
                "RTDETR_MODEL_PATH",
                "/export/ai_models/rt-detrv2/rtdetr_v2_r101vd",
            )

        backend = RTDETRv2Model(
            model_path=model_path,
            device=device,
            confidence_threshold=confidence_threshold,
        )
        backend.load_model()
        return backend
