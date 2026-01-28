"""TensorRT Inference Backend for CLIP Vision Encoder.

Provides TensorRT-accelerated inference for CLIP image embeddings with the same
interface as the PyTorch backend, enabling 1.5-2x speedup for embedding extraction.

Usage:
    from tensorrt_inference import CLIPTensorRTInference

    # Load TensorRT engine
    backend = CLIPTensorRTInference(
        engine_path="/models/clip-vit-l/vision_encoder_fp16.engine",
    )

    # Run inference (same interface as PyTorch)
    embedding, inference_time_ms = backend.extract_embedding(image)

Environment Variables:
    CLIP_BACKEND: Backend selection ('pytorch' or 'tensorrt'). Default: 'pytorch'
    CLIP_ENGINE_PATH: Path to TensorRT engine file (required for tensorrt backend)
    CLIP_USE_TENSORRT: Alternative enable flag (true/false). Default: false
"""

import logging
import os
import time
from typing import Any

import numpy as np
import torch
from PIL import Image

logger = logging.getLogger(__name__)

# CLIP ViT-L specifications
CLIP_INPUT_SIZE = (224, 224)  # Standard CLIP input size
EMBEDDING_DIMENSION = 768  # CLIP ViT-L embedding dimension

# ImageNet normalization (used by CLIP)
IMAGENET_MEAN = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
IMAGENET_STD = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)


def get_clip_backend() -> str:
    """Get the configured CLIP inference backend.

    Checks multiple environment variables for flexibility:
    - CLIP_BACKEND: Primary selection ('pytorch' or 'tensorrt')
    - CLIP_USE_TENSORRT: Alternative flag (true/false)

    Returns:
        Backend type: 'pytorch' or 'tensorrt'.
    """
    # Check primary env var
    backend = os.environ.get("CLIP_BACKEND", "").lower()
    if backend in ("pytorch", "tensorrt"):
        return backend

    # Check alternative flag
    use_tensorrt = os.environ.get("CLIP_USE_TENSORRT", "false").lower()
    if use_tensorrt in ("true", "1", "yes"):
        return "tensorrt"

    # Default to PyTorch
    return "pytorch"


def is_tensorrt_available() -> bool:
    """Check if TensorRT is available for inference.

    Returns:
        True if TensorRT can be used.
    """
    try:
        import tensorrt

        return torch.cuda.is_available()
    except ImportError:
        return False


class CLIPTensorRTInference:
    """TensorRT inference backend for CLIP vision encoder.

    Provides the same interface as the PyTorch CLIPEmbeddingModel class for
    seamless backend switching. Only supports vision encoding (image -> embedding).

    Attributes:
        engine_path: Path to the TensorRT engine file.
        device: CUDA device to use (e.g., 'cuda:0').
        engine: Loaded TensorRT engine.
        context: TensorRT execution context.
    """

    def __init__(
        self,
        engine_path: str,
        device: str = "cuda:0",
    ):
        """Initialize TensorRT inference backend.

        Args:
            engine_path: Path to TensorRT engine file.
            device: CUDA device (e.g., 'cuda:0'). Default: 'cuda:0'.

        Raises:
            FileNotFoundError: If engine file doesn't exist.
            ImportError: If TensorRT is not installed.
            RuntimeError: If engine loading fails.
        """
        self.engine_path = engine_path
        self.device = device

        # TensorRT objects (initialized in _load_engine)
        self.engine: Any = None
        self.context: Any = None
        self.stream: Any = None

        # Binding info (populated in _setup_bindings)
        self._input_binding: dict[str, Any] = {}
        self._output_binding: dict[str, Any] = {}

        # Load engine
        self._load_engine()

        # Warmup
        self._warmup()

        logger.info("CLIP TensorRT backend initialized:")
        logger.info(f"  Engine: {self.engine_path}")
        logger.info(f"  Device: {self.device}")
        logger.info(f"  Embedding dimension: {EMBEDDING_DIMENSION}")

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
            import tensorrt as trt
        except ImportError as e:
            raise ImportError(
                "TensorRT is not installed. Install with: pip install tensorrt"
            ) from e

        logger.info(f"Loading TensorRT engine: {self.engine_path}")

        # Create runtime and deserialize engine
        trt_logger = trt.Logger(trt.Logger.WARNING)
        runtime = trt.Runtime(trt_logger)

        with open(self.engine_path, "rb") as f:  # nosemgrep: path-traversal-open
            engine_data = f.read()

        self.engine = runtime.deserialize_cuda_engine(engine_data)
        if self.engine is None:
            raise RuntimeError("Failed to deserialize TensorRT engine")

        # Create execution context
        self.context = self.engine.create_execution_context()

        # Create CUDA stream
        self.stream = torch.cuda.Stream(device=self.device)

        # Set up bindings
        self._setup_bindings()

        logger.info("TensorRT engine loaded successfully")

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
                self._output_binding = binding_info
                logger.debug(f"Output: {name}, shape={shape}, dtype={np_dtype}")

    def _preprocess(self, image: Image.Image) -> np.ndarray:
        """Preprocess image for TensorRT inference.

        Applies the same preprocessing as the PyTorch CLIP model:
        - Resize to 224x224
        - Convert to RGB
        - Normalize with ImageNet mean/std (CLIP-specific values)

        Args:
            image: PIL Image to preprocess.

        Returns:
            Preprocessed numpy array [1, 3, 224, 224].
        """
        # Convert to RGB if needed
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Resize to CLIP input size using bicubic interpolation (CLIP default)
        image = image.resize(CLIP_INPUT_SIZE, Image.Resampling.BICUBIC)

        # Convert to numpy and normalize to [0, 1]
        img_array = np.array(image, dtype=np.float32) / 255.0

        # Normalize with CLIP-specific ImageNet values
        img_array = (img_array - IMAGENET_MEAN) / IMAGENET_STD

        # Transpose from HWC to CHW format
        img_array = img_array.transpose(2, 0, 1)

        # Add batch dimension [1, 3, 224, 224]
        img_array = np.expand_dims(img_array, axis=0)

        return img_array.astype(np.float32)

    def _run_inference(self, input_data: np.ndarray) -> np.ndarray:
        """Run TensorRT inference.

        Args:
            input_data: Preprocessed input array [batch, 3, 224, 224].

        Returns:
            Output embeddings [batch, 768].
        """
        batch_size = input_data.shape[0]

        # Allocate input tensor on GPU
        input_tensor = torch.from_numpy(input_data).to(self.device)

        # Set input shape for dynamic batch
        input_name = self._input_binding["name"]
        input_shape = (batch_size, *self._input_binding["shape"][1:])
        self.context.set_input_shape(input_name, input_shape)

        # Allocate output tensor
        output_name = self._output_binding["name"]
        output_shape = (batch_size, EMBEDDING_DIMENSION)
        output_tensor = torch.empty(output_shape, dtype=torch.float32, device=self.device)

        # Set tensor addresses
        self.context.set_tensor_address(input_name, input_tensor.data_ptr())
        self.context.set_tensor_address(output_name, output_tensor.data_ptr())

        # Run inference
        self.context.execute_async_v3(stream_handle=self.stream.cuda_stream)
        self.stream.synchronize()

        # Convert to numpy
        return output_tensor.cpu().numpy()

    def _warmup(self, num_iterations: int = 3) -> None:
        """Warmup the engine with dummy inputs.

        Args:
            num_iterations: Number of warmup iterations.
        """
        logger.info(f"Warming up TensorRT engine with {num_iterations} iterations...")

        # Create dummy image
        dummy_image = Image.new("RGB", CLIP_INPUT_SIZE, color=(128, 128, 128))

        for i in range(num_iterations):
            try:
                input_data = self._preprocess(dummy_image)
                self._run_inference(input_data)
                logger.info(f"Warmup iteration {i + 1}/{num_iterations} complete")
            except Exception as e:
                logger.warning(f"Warmup iteration {i + 1} failed: {e}")

        logger.info("Warmup complete")

    def extract_embedding(self, image: Image.Image) -> tuple[list[float], float]:
        """Generate a 768-dimensional embedding from an image.

        Matches the interface of CLIPEmbeddingModel.extract_embedding().

        Args:
            image: PIL Image to process.

        Returns:
            Tuple of (embedding list, inference_time_ms).
        """
        start_time = time.perf_counter()

        # Preprocess image
        input_data = self._preprocess(image)

        # Run inference
        embeddings = self._run_inference(input_data)

        # Normalize embedding (L2 normalization, matching PyTorch behavior)
        embedding = embeddings[0]
        epsilon = 1e-8
        norm = np.linalg.norm(embedding) + epsilon
        embedding = embedding / norm

        inference_time_ms = (time.perf_counter() - start_time) * 1000

        return embedding.tolist(), inference_time_ms

    def extract_embedding_batch(self, images: list[Image.Image]) -> tuple[list[list[float]], float]:
        """Generate embeddings for a batch of images.

        Args:
            images: List of PIL Images to process.

        Returns:
            Tuple of (list of embedding lists, inference_time_ms).
        """
        if not images:
            return [], 0.0

        start_time = time.perf_counter()

        # Preprocess all images
        input_batches = [self._preprocess(img) for img in images]
        input_data = np.concatenate(input_batches, axis=0)

        # Run inference
        embeddings = self._run_inference(input_data)

        # Normalize embeddings (L2 normalization)
        epsilon = 1e-8
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True) + epsilon
        embeddings = embeddings / norms

        inference_time_ms = (time.perf_counter() - start_time) * 1000

        return embeddings.tolist(), inference_time_ms

    def compute_anomaly_score(
        self, image: Image.Image, baseline_embedding: list[float]
    ) -> tuple[float, float, float]:
        """Compute anomaly score by comparing image embedding to baseline.

        Matches the interface of CLIPEmbeddingModel.compute_anomaly_score().

        Args:
            image: PIL Image to analyze.
            baseline_embedding: 768-dimensional baseline embedding.

        Returns:
            Tuple of (anomaly_score, similarity, inference_time_ms).
        """
        start_time = time.perf_counter()

        # Extract embedding for current image
        current_embedding, _ = self.extract_embedding(image)

        # Convert to numpy for computation
        current_array = np.array(current_embedding, dtype=np.float32)
        baseline_array = np.array(baseline_embedding, dtype=np.float32)

        # Ensure normalized (they should be from extract_embedding)
        epsilon = 1e-8
        current_norm = current_array / (np.linalg.norm(current_array) + epsilon)
        baseline_norm = baseline_array / (np.linalg.norm(baseline_array) + epsilon)

        # Compute cosine similarity (dot product of normalized vectors)
        similarity = float(np.dot(current_norm, baseline_norm))

        # Compute anomaly score: 1 - similarity, clamped to [0, 1]
        anomaly_score = max(0.0, min(1.0, 1.0 - similarity))

        inference_time_ms = (time.perf_counter() - start_time) * 1000

        return anomaly_score, similarity, inference_time_ms

    def get_health_info(self) -> dict[str, Any]:
        """Get health information for the backend.

        Returns:
            Dictionary with health status information.
        """
        return {
            "backend": "tensorrt",
            "engine_path": self.engine_path,
            "device": self.device,
            "embedding_dimension": EMBEDDING_DIMENSION,
            "engine_loaded": self.engine is not None,
        }


def create_clip_backend(
    model_path: str | None = None,
    engine_path: str | None = None,
    device: str = "cuda:0",
) -> Any:
    """Factory function to create the appropriate CLIP inference backend.

    Automatically selects between PyTorch and TensorRT based on configuration
    and availability. Falls back to PyTorch if TensorRT is unavailable.

    Args:
        model_path: Path to HuggingFace model (for PyTorch backend).
        engine_path: Path to TensorRT engine (for TensorRT backend).
        device: CUDA device to use.

    Returns:
        Inference backend instance (CLIPEmbeddingModel or CLIPTensorRTInference).

    Raises:
        ValueError: If required paths are not provided for the selected backend.
    """
    backend_type = get_clip_backend()

    if backend_type == "tensorrt":
        # Check if TensorRT is available
        if not is_tensorrt_available():
            logger.warning("TensorRT requested but not available, falling back to PyTorch")
            backend_type = "pytorch"
        else:
            # Get engine path from env if not provided
            if engine_path is None:
                engine_path = os.environ.get("CLIP_ENGINE_PATH")

            if engine_path is None:
                logger.warning(
                    "TensorRT requested but CLIP_ENGINE_PATH not set, falling back to PyTorch"
                )
                backend_type = "pytorch"
            elif not os.path.exists(engine_path):
                logger.warning(
                    f"TensorRT engine not found at {engine_path}, falling back to PyTorch"
                )
                backend_type = "pytorch"

    if backend_type == "tensorrt":
        logger.info("Creating CLIP TensorRT backend")
        return CLIPTensorRTInference(
            engine_path=engine_path,  # type: ignore[arg-type]
            device=device,
        )
    else:
        logger.info("Creating CLIP PyTorch backend")
        # Import PyTorch backend (avoid circular import at module load)
        # Note: The actual CLIPEmbeddingModel is defined in model.py
        # This function should be called from model.py where CLIPEmbeddingModel is defined
        if model_path is None:
            model_path = os.environ.get("CLIP_MODEL_PATH", "/models/clip-vit-l")

        # Return None to indicate PyTorch backend should be used
        # The caller (model.py) will instantiate CLIPEmbeddingModel
        return None


def validate_tensorrt_output(
    pytorch_model: Any,
    tensorrt_backend: CLIPTensorRTInference,
    num_samples: int = 10,
    threshold: float = 0.99,
) -> tuple[bool, float]:
    """Validate TensorRT output matches PyTorch output.

    Compares embeddings between backends using cosine similarity.

    Args:
        pytorch_model: PyTorch CLIPEmbeddingModel instance.
        tensorrt_backend: TensorRT CLIPTensorRTInference instance.
        num_samples: Number of random test images to use.
        threshold: Minimum cosine similarity threshold.

    Returns:
        Tuple of (passed, average_similarity).
    """
    import random

    logger.info(f"Validating TensorRT output with {num_samples} samples...")
    logger.info(f"  Threshold: {threshold}")

    similarities = []

    for i in range(num_samples):
        # Create random test image (non-security: random colors for testing)
        r = random.randint(0, 255)  # noqa: S311 # nosemgrep: insecure-random
        g = random.randint(0, 255)  # noqa: S311 # nosemgrep: insecure-random
        b = random.randint(0, 255)  # noqa: S311 # nosemgrep: insecure-random
        test_image = Image.new("RGB", CLIP_INPUT_SIZE, color=(r, g, b))

        # Get PyTorch embedding
        pytorch_embedding, _ = pytorch_model.extract_embedding(test_image)
        pytorch_array = np.array(pytorch_embedding, dtype=np.float32)

        # Get TensorRT embedding
        tensorrt_embedding, _ = tensorrt_backend.extract_embedding(test_image)
        tensorrt_array = np.array(tensorrt_embedding, dtype=np.float32)

        # Compute cosine similarity
        similarity = float(np.dot(pytorch_array, tensorrt_array))
        similarities.append(similarity)

        logger.debug(f"  Sample {i + 1}: similarity = {similarity:.6f}")

    avg_similarity = sum(similarities) / len(similarities)
    min_similarity = min(similarities)
    passed = min_similarity >= threshold

    logger.info(f"Validation {'PASSED' if passed else 'FAILED'}:")
    logger.info(f"  Average similarity: {avg_similarity:.6f}")
    logger.info(f"  Minimum similarity: {min_similarity:.6f}")
    logger.info(f"  Threshold: {threshold}")

    return passed, avg_similarity
