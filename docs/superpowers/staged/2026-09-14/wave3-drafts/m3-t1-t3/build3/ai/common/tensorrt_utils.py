"""TensorRT Conversion and Engine Management Utilities.

This module provides utilities for converting ONNX models to TensorRT engines
and managing inference with optimized TensorRT runtimes.

Key features:
- ONNX to TensorRT engine conversion with precision control (FP32, FP16, INT8)
- GPU architecture-aware engine caching for cross-GPU compatibility
- Dynamic shape support for variable batch sizes
- INT8 calibration support for maximum inference speed

Environment Variables:
- TENSORRT_ENABLED: Enable/disable TensorRT optimization (default: "true")
- TENSORRT_PRECISION: Default precision mode (default: "fp16")
  Options: "fp32", "fp16", "int8"
- TENSORRT_CACHE_DIR: Directory for TensorRT engine cache (default: "models/tensorrt_cache")
- TENSORRT_MAX_WORKSPACE_SIZE: Maximum workspace size in bytes (default: 1GB)
- TENSORRT_VERBOSE: Enable verbose TensorRT logging (default: "false")

Usage:
    from ai.common.tensorrt_utils import TensorRTConverter, TensorRTEngine

    # Convert ONNX model to TensorRT
    converter = TensorRTConverter(precision="fp16")
    engine_path = converter.convert_onnx_to_trt(
        onnx_path=Path("model.onnx"),
        input_shapes={"input": (1, 3, 640, 640)},
    )

    # Load and use engine for inference
    engine = TensorRTEngine(engine_path)
    outputs = engine.infer({"input": input_tensor})

References:
- TensorRT Developer Guide: https://docs.nvidia.com/deeplearning/tensorrt/developer-guide/
- ONNX-TensorRT: https://github.com/onnx/onnx-tensorrt
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# Environment variable configuration
TENSORRT_ENABLED = os.environ.get("TENSORRT_ENABLED", "true").lower() == "true"
TENSORRT_PRECISION = os.environ.get("TENSORRT_PRECISION", "fp16")
TENSORRT_CACHE_DIR = Path(os.environ.get("TENSORRT_CACHE_DIR", "models/tensorrt_cache"))
TENSORRT_MAX_WORKSPACE_SIZE = int(
    os.environ.get("TENSORRT_MAX_WORKSPACE_SIZE", str(1 << 30))
)  # 1GB default
TENSORRT_VERBOSE = os.environ.get("TENSORRT_VERBOSE", "false").lower() == "true"


class TensorRTPrecision(str, Enum):
    """TensorRT precision modes.

    - FP32: Full precision (32-bit floating point) - highest accuracy, slowest
    - FP16: Half precision (16-bit floating point) - good accuracy/speed trade-off
    - INT8: Integer quantization (8-bit) - fastest, requires calibration
    """

    FP32 = "fp32"
    FP16 = "fp16"
    INT8 = "int8"


@dataclass
class TensorRTConfig:
    """Configuration for TensorRT engine building and inference.

    Attributes:
        enabled: Whether TensorRT optimization is enabled
        precision: Precision mode (fp32, fp16, int8)
        max_workspace_size: Maximum GPU workspace size in bytes
        cache_dir: Directory for caching built engines
        verbose: Enable verbose TensorRT logging
        dynamic_batch_size: Enable dynamic batch size support
        min_batch_size: Minimum batch size for dynamic batching
        max_batch_size: Maximum batch size for dynamic batching
        opt_batch_size: Optimal batch size for dynamic batching
    """

    enabled: bool = TENSORRT_ENABLED
    precision: TensorRTPrecision | str = TensorRTPrecision.FP16
    max_workspace_size: int = TENSORRT_MAX_WORKSPACE_SIZE
    cache_dir: Path = field(default_factory=lambda: TENSORRT_CACHE_DIR)
    verbose: bool = TENSORRT_VERBOSE
    dynamic_batch_size: bool = True
    min_batch_size: int = 1
    max_batch_size: int = 16
    opt_batch_size: int = 4

    @classmethod
    def from_env(cls) -> TensorRTConfig:
        """Create TensorRTConfig from environment variables.

        Reads:
        - TENSORRT_ENABLED: "true" or "false"
        - TENSORRT_PRECISION: precision string
        - TENSORRT_CACHE_DIR: cache directory path
        - TENSORRT_MAX_WORKSPACE_SIZE: workspace size in bytes
        - TENSORRT_VERBOSE: "true" or "false"
        """
        return cls(
            enabled=TENSORRT_ENABLED,
            precision=TENSORRT_PRECISION,
            max_workspace_size=TENSORRT_MAX_WORKSPACE_SIZE,
            cache_dir=TENSORRT_CACHE_DIR,
            verbose=TENSORRT_VERBOSE,
        )


def is_tensorrt_available() -> bool:
    """Check if TensorRT is available on the system.

    Returns:
        True if TensorRT is installed and importable, False otherwise.
    """
    try:
        import tensorrt as trt

        return True
    except ImportError:
        logger.debug("TensorRT not available: tensorrt package not installed")
        return False


def get_gpu_compute_capability() -> str | None:
    """Get the compute capability (SM version) of the current GPU.

    Returns:
        SM version string (e.g., "sm_86" for RTX 3090, "sm_89" for RTX 4090),
        or None if no GPU is available.
    """
    try:
        import torch

        if not torch.cuda.is_available():
            return None

        device_props = torch.cuda.get_device_properties(0)
        sm_version = f"sm_{device_props.major}{device_props.minor}"
        return sm_version
    except Exception as e:
        logger.debug(f"Failed to get GPU compute capability: {e}")
        return None


def get_gpu_name() -> str | None:
    """Get the name of the current GPU.

    Returns:
        GPU name string, or None if no GPU is available.
    """
    try:
        import torch

        if not torch.cuda.is_available():
            return None

        return torch.cuda.get_device_name(0)
    except Exception as e:
        logger.debug(f"Failed to get GPU name: {e}")
        return None


class TensorRTConverter:
    """Convert ONNX models to TensorRT engines with GPU-aware caching.

    This class handles the conversion of ONNX models to optimized TensorRT
    engines, with support for different precision modes and automatic
    engine caching based on GPU architecture.

    Attributes:
        config: TensorRT configuration
        logger: Logger instance for TensorRT builder
    """

    def __init__(
        self,
        precision: str = "fp16",
        max_workspace_size: int = 1 << 30,
        cache_dir: Path | str = Path("models/tensorrt_cache"),
        config: TensorRTConfig | None = None,
    ):
        """Initialize the TensorRT converter.

        Args:
            precision: Precision mode ("fp32", "fp16", or "int8")
            max_workspace_size: Maximum workspace memory in bytes (default: 1GB)
            cache_dir: Directory for engine cache (default: "models/tensorrt_cache")
            config: Full TensorRTConfig (overrides other arguments if provided)
        """
        if config is not None:
            self.config = config
        else:
            self.config = TensorRTConfig(
                precision=precision,
                max_workspace_size=max_workspace_size,
                cache_dir=Path(cache_dir),
            )

        # Validate TensorRT availability
        if not is_tensorrt_available():
            raise ImportError("TensorRT is not available. Please install tensorrt package.")

        # Initialize TensorRT components
        self._trt: Any = None  # Lazy import
        self._logger: Any = None
        self._builder: Any = None

    def _init_tensorrt(self) -> None:
        """Lazily initialize TensorRT components."""
        if self._trt is not None:
            return

        import tensorrt as trt

        self._trt = trt

        # Create TensorRT logger
        log_level = trt.Logger.VERBOSE if self.config.verbose else trt.Logger.WARNING
        self._logger = trt.Logger(log_level)

        # Create builder
        self._builder = trt.Builder(self._logger)

    def get_engine_path(
        self,
        onnx_path: Path,
        precision: str | None = None,
    ) -> Path:
        """Get the cached engine path for the current GPU architecture.

        The engine path includes:
        - ONNX model hash (for cache invalidation on model changes)
        - GPU SM version (engines are architecture-specific)
        - Precision mode

        Args:
            onnx_path: Path to the source ONNX model
            precision: Precision mode (uses config default if None)

        Returns:
            Path to the TensorRT engine file (may not exist yet)
        """
        # Use config precision if not specified
        prec = precision or (
            self.config.precision.value
            if isinstance(self.config.precision, TensorRTPrecision)
            else self.config.precision
        )

        # Get GPU compute capability for cache key
        sm_version = get_gpu_compute_capability() or "unknown"

        # Compute ONNX model hash for cache invalidation
        onnx_hash = self._compute_file_hash(onnx_path)

        # Construct engine filename
        model_name = onnx_path.stem
        engine_name = f"{model_name}_{sm_version}_{prec}_{onnx_hash[:8]}.engine"

        # Ensure cache directory exists
        self.config.cache_dir.mkdir(parents=True, exist_ok=True)

        return self.config.cache_dir / engine_name

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of a file.

        Args:
            file_path: Path to the file

        Returns:
            Hexadecimal hash string
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:  # nosemgrep: path-traversal-open
            # Read in chunks to handle large files
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    def convert_onnx_to_trt(
        self,
        onnx_path: Path,
        input_shapes: dict[str, tuple[int, ...]],
        dynamic_axes: dict[str, list[int]] | None = None,
        calibration_data: NDArray[np.float32] | None = None,
        force_rebuild: bool = False,
    ) -> Path:
        """Convert an ONNX model to a TensorRT engine.

        If a cached engine exists for the current GPU architecture, it will
        be reused unless force_rebuild is True.

        Args:
            onnx_path: Path to the ONNX model file
            input_shapes: Dictionary mapping input names to shapes
                Example: {"input": (1, 3, 640, 640)}
            dynamic_axes: Optional dictionary specifying dynamic axes
                Example: {"input": [0]} for dynamic batch dimension
            calibration_data: Calibration data for INT8 quantization
                Required when precision is "int8"
            force_rebuild: Force rebuild even if cached engine exists

        Returns:
            Path to the TensorRT engine file

        Raises:
            FileNotFoundError: If ONNX model file doesn't exist
            RuntimeError: If TensorRT engine building fails
        """
        if not onnx_path.exists():
            raise FileNotFoundError(f"ONNX model not found: {onnx_path}")

        # Get precision from config
        precision = (
            self.config.precision.value
            if isinstance(self.config.precision, TensorRTPrecision)
            else self.config.precision
        )

        # Check for INT8 calibration data requirement
        if precision == "int8" and calibration_data is None:
            raise ValueError("INT8 precision requires calibration_data for quantization")

        # Get engine path
        engine_path = self.get_engine_path(onnx_path)

        # Check cache
        if engine_path.exists() and not force_rebuild:
            logger.info(f"Using cached TensorRT engine: {engine_path}")
            return engine_path

        logger.info(
            f"Building TensorRT engine from {onnx_path} "
            f"(precision={precision}, workspace={self.config.max_workspace_size / (1 << 30):.1f}GB)"
        )

        # Initialize TensorRT
        self._init_tensorrt()
        trt = self._trt

        # Create network definition
        network_flags = 1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH)
        network = self._builder.create_network(network_flags)

        # Parse ONNX model
        parser = trt.OnnxParser(network, self._logger)
        with open(onnx_path, "rb") as f:  # nosemgrep: path-traversal-open
            if not parser.parse(f.read()):
                errors = [parser.get_error(i) for i in range(parser.num_errors)]
                raise RuntimeError(f"Failed to parse ONNX model: {errors}")

        # Create builder config
        builder_config = self._builder.create_builder_config()
        builder_config.set_memory_pool_limit(
            trt.MemoryPoolType.WORKSPACE, self.config.max_workspace_size
        )

        # Set precision flags
        if precision == "fp16":
            if self._builder.platform_has_fast_fp16:
                builder_config.set_flag(trt.BuilderFlag.FP16)
                logger.info("Enabled FP16 precision")
            else:
                logger.warning("GPU does not support fast FP16, using FP32")
        elif precision == "int8":
            if self._builder.platform_has_fast_int8:
                builder_config.set_flag(trt.BuilderFlag.INT8)
                # Set calibrator for INT8
                calibrator = self._create_calibrator(input_shapes, calibration_data, network)
                builder_config.int8_calibrator = calibrator
                logger.info("Enabled INT8 precision with calibration")
            else:
                logger.warning("GPU does not support fast INT8, using FP32")

        # Configure optimization profiles for dynamic shapes
        if dynamic_axes or self.config.dynamic_batch_size:
            profile = self._builder.create_optimization_profile()
            self._configure_dynamic_shapes(profile, network, input_shapes, dynamic_axes)
            builder_config.add_optimization_profile(profile)

        # Build engine
        logger.info("Building TensorRT engine (this may take several minutes)...")
        serialized_engine = self._builder.build_serialized_network(network, builder_config)

        if serialized_engine is None:
            raise RuntimeError("Failed to build TensorRT engine")

        # Save engine to file
        engine_path.parent.mkdir(parents=True, exist_ok=True)
        with open(engine_path, "wb") as f:  # nosemgrep: path-traversal-open
            f.write(serialized_engine)

        logger.info(f"TensorRT engine saved to: {engine_path}")
        return engine_path

    def _configure_dynamic_shapes(
        self,
        profile: Any,
        network: Any,
        input_shapes: dict[str, tuple[int, ...]],
        dynamic_axes: dict[str, list[int]] | None,
    ) -> None:
        """Configure optimization profile for dynamic shapes.

        Args:
            profile: TensorRT optimization profile
            network: TensorRT network definition
            input_shapes: Base input shapes
            dynamic_axes: Dictionary of dynamic axes per input
        """
        for i in range(network.num_inputs):
            input_tensor = network.get_input(i)
            name = input_tensor.name

            if name not in input_shapes:
                # Use shape from network
                base_shape = tuple(input_tensor.shape)
            else:
                base_shape = input_shapes[name]

            # Calculate min, opt, max shapes
            min_shape = list(base_shape)
            opt_shape = list(base_shape)
            max_shape = list(base_shape)

            # Handle dynamic axes
            axes = (dynamic_axes or {}).get(name, [])

            # Always treat batch dimension (axis 0) as dynamic if config allows
            if self.config.dynamic_batch_size and 0 not in axes:
                axes = [0, *axes]

            for axis in axes:
                if axis == 0:  # Batch dimension
                    min_shape[axis] = self.config.min_batch_size
                    opt_shape[axis] = self.config.opt_batch_size
                    max_shape[axis] = self.config.max_batch_size
                else:
                    # For other dynamic axes, use reasonable defaults
                    min_shape[axis] = max(1, base_shape[axis] // 2)
                    max_shape[axis] = base_shape[axis] * 2

            profile.set_shape(name, min_shape, opt_shape, max_shape)
            logger.debug(
                f"Dynamic shape for '{name}': min={min_shape}, opt={opt_shape}, max={max_shape}"
            )

    def _create_calibrator(
        self,
        _input_shapes: dict[str, tuple[int, ...]],
        calibration_data: NDArray[np.float32] | None,
        _network: Any,
    ) -> Any:
        """Create INT8 calibrator for quantization.

        Args:
            input_shapes: Input shapes dictionary (reserved for future use)
            calibration_data: Calibration dataset
            network: TensorRT network (reserved for future use)

        Returns:
            TensorRT calibrator instance
        """
        trt = self._trt

        class Int8Calibrator(trt.IInt8EntropyCalibrator2):  # type: ignore[name-defined]
            """INT8 calibrator using entropy calibration."""

            def __init__(
                self,
                data: NDArray[np.float32],
                cache_file: str = "calibration.cache",
            ):
                super().__init__()
                self.data = data
                self.cache_file = cache_file
                self.current_index = 0
                self.batch_size = data.shape[0] if data is not None else 1

                # Allocate device memory
                import torch

                self.device_input = torch.from_numpy(data).cuda().contiguous()

            def get_batch_size(self) -> int:
                return self.batch_size  # type: ignore[no-any-return]

            def get_batch(self, _names: list[str]) -> list[int] | None:
                if self.current_index >= len(self.data):
                    return None

                # Return pointer to device memory
                batch = [int(self.device_input.data_ptr())]
                self.current_index += self.batch_size
                return batch

            def read_calibration_cache(self) -> bytes | None:
                if os.path.exists(self.cache_file):
                    with open(self.cache_file, "rb") as f:  # nosemgrep: path-traversal-open
                        return f.read()
                return None

            def write_calibration_cache(self, cache: bytes) -> None:
                with open(self.cache_file, "wb") as f:  # nosemgrep: path-traversal-open
                    f.write(cache)

        if calibration_data is not None:
            return Int8Calibrator(calibration_data)
        return None


class TensorRTEngine:
    """Wrapper for TensorRT engine inference.

    This class provides a convenient interface for running inference with
    TensorRT engines, handling memory allocation and data transfer.

    Attributes:
        engine_path: Path to the TensorRT engine file
        engine: Loaded TensorRT engine
        context: Execution context for inference
    """

    def __init__(
        self,
        engine_path: Path | str,
        device: str = "cuda:0",
    ):
        """Initialize the TensorRT engine wrapper.

        Args:
            engine_path: Path to the TensorRT engine file
            device: CUDA device to use for inference

        Raises:
            FileNotFoundError: If engine file doesn't exist
            RuntimeError: If engine loading fails
        """
        self.engine_path = Path(engine_path)
        self.device = device

        if not self.engine_path.exists():
            raise FileNotFoundError(f"TensorRT engine not found: {self.engine_path}")

        if not is_tensorrt_available():
            raise ImportError("TensorRT is not available. Please install tensorrt package.")

        self._load_engine()

    def _load_engine(self) -> None:
        """Load the TensorRT engine from file."""
        import tensorrt as trt

        self._trt = trt

        # Create logger
        self._logger = trt.Logger(trt.Logger.WARNING)

        # Load engine from file
        with open(self.engine_path, "rb") as f:  # nosemgrep: path-traversal-open
            engine_data = f.read()

        runtime = trt.Runtime(self._logger)
        self.engine = runtime.deserialize_cuda_engine(engine_data)

        if self.engine is None:
            raise RuntimeError(f"Failed to load TensorRT engine: {self.engine_path}")

        # Create execution context
        self.context = self.engine.create_execution_context()

        # Get input/output tensor info
        self._io_info = self._get_io_info()

        logger.info(
            f"Loaded TensorRT engine: {self.engine_path.name} "
            f"(inputs: {list(self._io_info['inputs'].keys())}, "
            f"outputs: {list(self._io_info['outputs'].keys())})"
        )

    def _get_io_info(self) -> dict[str, Any]:
        """Get information about input/output tensors.

        Returns:
            Dictionary with 'inputs' and 'outputs' tensor information
        """
        trt = self._trt
        info: dict[str, dict[str, Any]] = {"inputs": {}, "outputs": {}}

        for i in range(self.engine.num_io_tensors):
            name = self.engine.get_tensor_name(i)
            mode = self.engine.get_tensor_mode(name)
            dtype = self.engine.get_tensor_dtype(name)
            shape = self.engine.get_tensor_shape(name)

            tensor_info = {
                "dtype": dtype,
                "shape": tuple(shape),
                "index": i,
            }

            if mode == trt.TensorIOMode.INPUT:
                info["inputs"][name] = tensor_info
            else:
                info["outputs"][name] = tensor_info

        return info

    def _get_numpy_dtype(self, trt_dtype: Any) -> np.dtype[Any]:
        """Convert TensorRT dtype to NumPy dtype.

        Args:
            trt_dtype: TensorRT data type

        Returns:
            Corresponding NumPy dtype
        """
        trt = self._trt
        dtype_map = {
            trt.float32: np.float32,
            trt.float16: np.float16,
            trt.int32: np.int32,
            trt.int8: np.int8,
            trt.bool: np.bool_,
        }
        return np.dtype(dtype_map.get(trt_dtype, np.float32))

    def infer(
        self,
        inputs: dict[str, NDArray[Any]],
    ) -> dict[str, NDArray[Any]]:
        """Run inference with named inputs/outputs.

        Args:
            inputs: Dictionary mapping input names to NumPy arrays

        Returns:
            Dictionary mapping output names to NumPy arrays

        Raises:
            ValueError: If required inputs are missing or shapes mismatch
        """
        import torch

        # Validate inputs
        for name in self._io_info["inputs"]:
            if name not in inputs:
                raise ValueError(f"Missing required input: {name}")

        # Set input shapes for dynamic dimensions
        for name, arr in inputs.items():
            if name in self._io_info["inputs"]:
                self.context.set_input_shape(name, arr.shape)

        # Allocate device memory for inputs and outputs
        device_inputs: dict[str, torch.Tensor] = {}
        device_outputs: dict[str, torch.Tensor] = {}

        # Copy inputs to device
        for name, arr in inputs.items():
            if name in self._io_info["inputs"]:
                tensor = torch.from_numpy(arr).to(self.device).contiguous()
                device_inputs[name] = tensor
                self.context.set_tensor_address(name, tensor.data_ptr())

        # Allocate outputs on device
        for name, info in self._io_info["outputs"].items():
            # Get actual output shape (may depend on input shapes)
            shape = self.context.get_tensor_shape(name)
            dtype = self._get_numpy_dtype(info["dtype"])

            # Convert to torch dtype
            torch_dtype = torch.from_numpy(np.array([], dtype=dtype)).dtype
            output_tensor = torch.empty(tuple(shape), dtype=torch_dtype, device=self.device)
            device_outputs[name] = output_tensor
            self.context.set_tensor_address(name, output_tensor.data_ptr())

        # Run inference
        if not self.context.execute_async_v3(torch.cuda.current_stream().cuda_stream):
            raise RuntimeError("TensorRT inference failed")

        # Synchronize
        torch.cuda.synchronize()

        # Copy outputs to host
        outputs: dict[str, NDArray[Any]] = {}
        for name, tensor in device_outputs.items():
            outputs[name] = tensor.cpu().numpy()

        return outputs

    def infer_batch(
        self,
        inputs_list: list[dict[str, NDArray[Any]]],
    ) -> list[dict[str, NDArray[Any]]]:
        """Run batched inference on multiple input sets.

        This method processes multiple input dictionaries by stacking them
        into a single batch for efficient GPU inference.

        Args:
            inputs_list: List of input dictionaries

        Returns:
            List of output dictionaries, one per input

        Note:
            All inputs must have compatible shapes for batching.
        """
        if not inputs_list:
            return []

        if len(inputs_list) == 1:
            return [self.infer(inputs_list[0])]

        # Stack inputs into batched arrays
        batched_inputs: dict[str, NDArray[Any]] = {}
        for name in inputs_list[0]:
            arrays = [inp[name] for inp in inputs_list]
            batched_inputs[name] = np.stack(arrays, axis=0)

        # Run batched inference
        batched_outputs = self.infer(batched_inputs)

        # Split outputs back into individual results
        results: list[dict[str, NDArray[Any]]] = []
        batch_size = len(inputs_list)

        for i in range(batch_size):
            result: dict[str, NDArray[Any]] = {}
            for name, arr in batched_outputs.items():
                result[name] = arr[i]
            results.append(result)

        return results

    def get_input_names(self) -> list[str]:
        """Get names of all input tensors.

        Returns:
            List of input tensor names
        """
        return list(self._io_info["inputs"].keys())

    def get_output_names(self) -> list[str]:
        """Get names of all output tensors.

        Returns:
            List of output tensor names
        """
        return list(self._io_info["outputs"].keys())

    def get_input_shape(self, name: str) -> tuple[int, ...]:
        """Get the shape of an input tensor.

        Args:
            name: Input tensor name

        Returns:
            Input tensor shape

        Raises:
            KeyError: If input name not found
        """
        if name not in self._io_info["inputs"]:
            raise KeyError(f"Unknown input tensor: {name}")
        shape: tuple[int, ...] = self._io_info["inputs"][name]["shape"]
        return shape

    def get_output_shape(self, name: str) -> tuple[int, ...]:
        """Get the shape of an output tensor.

        Args:
            name: Output tensor name

        Returns:
            Output tensor shape

        Raises:
            KeyError: If output name not found
        """
        if name not in self._io_info["outputs"]:
            raise KeyError(f"Unknown output tensor: {name}")
        shape: tuple[int, ...] = self._io_info["outputs"][name]["shape"]
        return shape

    def __del__(self) -> None:
        """Clean up TensorRT resources."""
        if hasattr(self, "context") and self.context is not None:
            del self.context
        if hasattr(self, "engine") and self.engine is not None:
            del self.engine
