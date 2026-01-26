"""Triton Inference Server Client for AI Model Inference.

This module provides a high-level client for interacting with NVIDIA Triton
Inference Server, supporting both gRPC and HTTP protocols.

The client supports:
- Object detection with YOLO26 and YOLO26 models
- Automatic batching for improved throughput
- Health checks and model status queries
- Graceful error handling with retry logic
- Async/await interface for non-blocking operation

Environment Variables:
    TRITON_URL: Triton server gRPC URL (default: localhost:8001)
    TRITON_HTTP_URL: Triton server HTTP URL (default: localhost:8000)
    TRITON_TIMEOUT: Request timeout in seconds (default: 60)
    TRITON_MODEL: Default model name (default: yolo26)
    TRITON_ENABLED: Enable Triton inference (default: false)
    TRITON_MAX_RETRIES: Maximum retry attempts (default: 3)

Usage:
    from ai.triton.client import TritonClient, TritonConfig

    config = TritonConfig.from_env()
    client = TritonClient(config)

    # Check server health
    if await client.is_healthy():
        # Run detection
        result = await client.detect(image_bytes)

References:
    - Triton Client: https://github.com/triton-inference-server/client
    - gRPC Python: https://grpc.io/docs/languages/python/
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)


# =============================================================================
# Exceptions
# =============================================================================


class TritonError(Exception):
    """Base exception for Triton-related errors."""

    pass


class TritonConnectionError(TritonError):
    """Raised when connection to Triton server fails."""

    pass


class TritonInferenceError(TritonError):
    """Raised when inference request fails."""

    pass


class TritonModelNotFoundError(TritonError):
    """Raised when requested model is not loaded in Triton."""

    pass


# =============================================================================
# Configuration
# =============================================================================


class TritonProtocol(str, Enum):
    """Triton client protocol options."""

    GRPC = "grpc"
    HTTP = "http"


@dataclass
class TritonConfig:
    """Configuration for Triton Inference Server client.

    Attributes:
        enabled: Whether Triton inference is enabled
        grpc_url: Triton gRPC endpoint URL
        http_url: Triton HTTP endpoint URL
        protocol: Preferred protocol (grpc or http)
        timeout: Request timeout in seconds
        default_model: Default model to use for inference
        max_retries: Maximum retry attempts for transient failures
        retry_delay: Base delay between retries (exponential backoff)
        verbose: Enable verbose logging
    """

    enabled: bool = False
    grpc_url: str = "localhost:8001"
    http_url: str = "localhost:8000"
    protocol: TritonProtocol = TritonProtocol.GRPC
    timeout: float = 60.0
    default_model: str = "yolo26"
    max_retries: int = 3
    retry_delay: float = 1.0
    verbose: bool = False
    # Model-specific settings
    confidence_threshold: float = 0.5
    # Connection pool settings
    max_connections: int = 10

    @classmethod
    def from_env(cls) -> TritonConfig:
        """Create TritonConfig from environment variables.

        Environment Variables:
            TRITON_ENABLED: Enable Triton (default: false)
            TRITON_URL: gRPC URL (default: localhost:8001)
            TRITON_HTTP_URL: HTTP URL (default: localhost:8000)
            TRITON_PROTOCOL: Protocol (grpc or http, default: grpc)
            TRITON_TIMEOUT: Timeout in seconds (default: 60)
            TRITON_MODEL: Default model (default: yolo26)
            TRITON_MAX_RETRIES: Max retries (default: 3)
            TRITON_VERBOSE: Verbose logging (default: false)
            TRITON_CONFIDENCE_THRESHOLD: Detection threshold (default: 0.5)

        Returns:
            TritonConfig instance
        """
        protocol_str = os.environ.get("TRITON_PROTOCOL", "grpc").lower()
        protocol = TritonProtocol.GRPC if protocol_str == "grpc" else TritonProtocol.HTTP

        return cls(
            enabled=os.environ.get("TRITON_ENABLED", "false").lower() == "true",
            grpc_url=os.environ.get("TRITON_URL", "localhost:8001"),
            http_url=os.environ.get("TRITON_HTTP_URL", "localhost:8000"),
            protocol=protocol,
            timeout=float(os.environ.get("TRITON_TIMEOUT", "60")),
            default_model=os.environ.get("TRITON_MODEL", "yolo26"),
            max_retries=int(os.environ.get("TRITON_MAX_RETRIES", "3")),
            verbose=os.environ.get("TRITON_VERBOSE", "false").lower() == "true",
            confidence_threshold=float(os.environ.get("TRITON_CONFIDENCE_THRESHOLD", "0.5")),
        )


# =============================================================================
# Detection Result Types
# =============================================================================


@dataclass
class BoundingBox:
    """Bounding box coordinates."""

    x: int
    y: int
    width: int
    height: int


@dataclass
class Detection:
    """Single object detection result."""

    class_name: str
    confidence: float
    bbox: BoundingBox


@dataclass
class DetectionResult:
    """Complete detection result from Triton inference."""

    detections: list[Detection] = field(default_factory=list)
    inference_time_ms: float = 0.0
    image_width: int = 0
    image_height: int = 0
    model_name: str = ""
    model_version: str = ""


# =============================================================================
# Triton Client
# =============================================================================


class TritonClient:
    """High-level client for Triton Inference Server.

    This client provides a simplified interface for running object detection
    inference using models deployed on Triton Inference Server.

    Features:
        - Automatic protocol selection (gRPC preferred for performance)
        - Request retry with exponential backoff
        - Health monitoring and model status checks
        - Async interface for non-blocking operation
        - Support for batch inference

    Usage:
        config = TritonConfig.from_env()
        client = TritonClient(config)

        # Health check
        if await client.is_healthy():
            # Run detection
            result = await client.detect(image_bytes)
            for detection in result.detections:
                print(f"{detection.class_name}: {detection.confidence:.2f}")

        # Cleanup
        await client.close()
    """

    # Security-relevant classes for filtering detections
    SECURITY_CLASSES: ClassVar[frozenset[str]] = frozenset(
        {"person", "car", "truck", "dog", "cat", "bird", "bicycle", "motorcycle", "bus"}
    )

    # COCO class ID to name mapping (for YOLO models)
    COCO_ID_TO_NAME: ClassVar[dict[int, str]] = {
        0: "person",
        1: "bicycle",
        2: "car",
        3: "motorcycle",
        5: "bus",
        7: "truck",
        14: "bird",
        15: "cat",
        16: "dog",
    }

    def __init__(self, config: TritonConfig | None = None) -> None:
        """Initialize Triton client.

        Args:
            config: Client configuration. If None, loads from environment.
        """
        self.config = config or TritonConfig.from_env()
        self._grpc_client: Any = None
        self._http_client: Any = None
        self._connected = False
        self._model_metadata: dict[str, dict[str, Any]] = {}

        logger.info(
            "TritonClient initialized",
            extra={
                "enabled": self.config.enabled,
                "protocol": self.config.protocol.value,
                "grpc_url": self.config.grpc_url,
                "http_url": self.config.http_url,
                "default_model": self.config.default_model,
            },
        )

    async def connect(self) -> None:
        """Establish connection to Triton server.

        Raises:
            TritonConnectionError: If connection fails
        """
        if not self.config.enabled:
            logger.warning("Triton is disabled, skipping connection")
            return

        try:
            if self.config.protocol == TritonProtocol.GRPC:
                await self._connect_grpc()
            else:
                await self._connect_http()

            self._connected = True
            logger.info(
                "Connected to Triton server",
                extra={"protocol": self.config.protocol.value},
            )
        except Exception as e:
            raise TritonConnectionError(f"Failed to connect to Triton: {e}") from e

    async def _connect_grpc(self) -> None:
        """Establish gRPC connection to Triton."""
        try:
            import tritonclient.grpc.aio as grpcclient
        except ImportError as e:
            raise TritonConnectionError(
                "tritonclient[grpc] not installed. Install with: pip install tritonclient[grpc]"
            ) from e

        self._grpc_client = grpcclient.InferenceServerClient(
            url=self.config.grpc_url,
            verbose=self.config.verbose,
        )

        # Verify connection by checking server liveness
        if not await self._grpc_client.is_server_live():
            raise TritonConnectionError(f"Triton server not live at {self.config.grpc_url}")

    async def _connect_http(self) -> None:
        """Establish HTTP connection to Triton."""
        try:
            import tritonclient.http.aio as httpclient
        except ImportError as e:
            raise TritonConnectionError(
                "tritonclient[http] not installed. Install with: pip install tritonclient[http]"
            ) from e

        self._http_client = httpclient.InferenceServerClient(
            url=self.config.http_url,
            verbose=self.config.verbose,
        )

        # Verify connection
        if not await self._http_client.is_server_live():
            raise TritonConnectionError(f"Triton server not live at {self.config.http_url}")

    async def close(self) -> None:
        """Close connection to Triton server."""
        if self._grpc_client is not None:
            await self._grpc_client.close()
            self._grpc_client = None

        if self._http_client is not None:
            await self._http_client.close()
            self._http_client = None

        self._connected = False
        logger.debug("Triton client connections closed")

    async def is_healthy(self) -> bool:
        """Check if Triton server is healthy.

        Returns:
            True if server is live and ready, False otherwise
        """
        if not self.config.enabled:
            return False

        try:
            if not self._connected:
                await self.connect()

            client = self._get_client()
            is_live: bool = await client.is_server_live()
            is_ready: bool = await client.is_server_ready()
            return is_live and is_ready
        except Exception as e:
            logger.warning(f"Triton health check failed: {e}")
            return False

    async def is_model_ready(self, model_name: str | None = None) -> bool:
        """Check if a specific model is loaded and ready.

        Args:
            model_name: Model to check (uses default if None)

        Returns:
            True if model is ready, False otherwise
        """
        if not self.config.enabled:
            return False

        model = model_name or self.config.default_model

        try:
            if not self._connected:
                await self.connect()

            client = self._get_client()
            result: bool = await client.is_model_ready(model)
            return result
        except Exception as e:
            logger.warning(f"Model ready check failed for {model}: {e}")
            return False

    def _get_client(self) -> Any:
        """Get the appropriate client based on protocol.

        Returns:
            gRPC or HTTP client instance

        Raises:
            TritonConnectionError: If no client is connected
        """
        if self.config.protocol == TritonProtocol.GRPC:
            if self._grpc_client is None:
                raise TritonConnectionError("gRPC client not connected")
            return self._grpc_client
        else:
            if self._http_client is None:
                raise TritonConnectionError("HTTP client not connected")
            return self._http_client

    async def get_model_metadata(self, model_name: str | None = None) -> dict[str, Any]:
        """Get metadata for a model.

        Args:
            model_name: Model to query (uses default if None)

        Returns:
            Model metadata dictionary

        Raises:
            TritonModelNotFoundError: If model not found
        """
        model = model_name or self.config.default_model

        # Check cache
        if model in self._model_metadata:
            return self._model_metadata[model]

        if not self._connected:
            await self.connect()

        try:
            client = self._get_client()
            metadata = await client.get_model_metadata(model)

            # Cache metadata
            self._model_metadata[model] = {
                "name": metadata.name if hasattr(metadata, "name") else model,
                "versions": (metadata.versions if hasattr(metadata, "versions") else ["1"]),
                "inputs": self._parse_tensor_metadata(
                    metadata.inputs if hasattr(metadata, "inputs") else []
                ),
                "outputs": self._parse_tensor_metadata(
                    metadata.outputs if hasattr(metadata, "outputs") else []
                ),
            }
            return self._model_metadata[model]
        except Exception as e:
            raise TritonModelNotFoundError(f"Model {model} not found: {e}") from e

    def _parse_tensor_metadata(self, tensors: list[Any]) -> list[dict[str, Any]]:
        """Parse tensor metadata from Triton response.

        Args:
            tensors: List of tensor metadata objects

        Returns:
            List of tensor info dictionaries
        """
        result = []
        for tensor in tensors:
            result.append(
                {
                    "name": tensor.name if hasattr(tensor, "name") else "",
                    "datatype": tensor.datatype if hasattr(tensor, "datatype") else "",
                    "shape": list(tensor.shape) if hasattr(tensor, "shape") else [],
                }
            )
        return result

    async def detect(
        self,
        image: bytes | NDArray[np.uint8],
        model_name: str | None = None,
        confidence_threshold: float | None = None,
    ) -> DetectionResult:
        """Run object detection on an image.

        Args:
            image: Image as bytes (JPEG/PNG) or numpy array (HWC RGB)
            model_name: Model to use (uses default if None)
            confidence_threshold: Filter threshold (uses config default if None)

        Returns:
            DetectionResult with detected objects

        Raises:
            TritonInferenceError: If inference fails
            TritonConnectionError: If not connected
        """
        model = model_name or self.config.default_model
        threshold = confidence_threshold or self.config.confidence_threshold

        # Ensure connected
        if not self._connected:
            await self.connect()

        # Preprocess image
        input_tensor, original_size = self._preprocess_image(image)

        # Run inference with retry
        start_time = time.perf_counter()

        for attempt in range(self.config.max_retries):
            try:
                raw_output = await self._infer(model, input_tensor)
                break
            except Exception as e:
                if attempt == self.config.max_retries - 1:
                    raise TritonInferenceError(
                        f"Inference failed after {self.config.max_retries} attempts: {e}"
                    ) from e
                delay = self.config.retry_delay * (2**attempt)
                logger.warning(f"Inference attempt {attempt + 1} failed, retrying in {delay}s: {e}")
                await asyncio.sleep(delay)

        inference_time_ms = (time.perf_counter() - start_time) * 1000

        # Postprocess based on model type
        if model == "yolo26":
            detections = self._postprocess_yolo(raw_output, original_size, threshold)
        else:  # yolo26
            detections = self._postprocess_yolo26(raw_output, original_size, threshold)

        return DetectionResult(
            detections=detections,
            inference_time_ms=inference_time_ms,
            image_width=original_size[0],
            image_height=original_size[1],
            model_name=model,
            model_version="1",
        )

    def _preprocess_image(
        self, image: bytes | NDArray[np.uint8]
    ) -> tuple[NDArray[np.float32], tuple[int, int]]:
        """Preprocess image for model input.

        Args:
            image: Image as bytes or numpy array

        Returns:
            Tuple of (preprocessed tensor, original size (width, height))
        """
        import io

        from PIL import Image as PILImage
        from PIL.Image import Image as PILImageType

        img: PILImageType
        if isinstance(image, bytes):
            img = PILImage.open(io.BytesIO(image))
        else:
            img = PILImage.fromarray(image)

        # Get original size
        original_size = img.size  # (width, height)

        # Convert to RGB if needed
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Resize to model input size (640x640)
        resized_img = img.resize((640, 640), PILImage.Resampling.BILINEAR)

        # Convert to numpy array
        img_array = np.array(resized_img, dtype=np.float32)

        # Normalize to [0, 1]
        img_array = img_array / 255.0

        # Convert HWC to CHW format
        img_array = img_array.transpose(2, 0, 1)

        # Add batch dimension
        img_array = np.expand_dims(img_array, axis=0)

        return img_array, original_size

    async def _infer(
        self, model_name: str, input_tensor: NDArray[np.float32]
    ) -> dict[str, NDArray[Any]]:
        """Run inference on Triton server.

        Args:
            model_name: Model to use
            input_tensor: Preprocessed input tensor

        Returns:
            Dictionary of output tensors
        """
        client = self._get_client()

        # Create inference input
        if self.config.protocol == TritonProtocol.GRPC:
            import tritonclient.grpc.aio as grpcclient

            inputs = [
                grpcclient.InferInput("images", input_tensor.shape, "FP32"),
            ]
            inputs[0].set_data_from_numpy(input_tensor)

            # Create output requests
            outputs = [
                grpcclient.InferRequestedOutput("labels"),
                grpcclient.InferRequestedOutput("boxes"),
                grpcclient.InferRequestedOutput("scores"),
            ]

            # For YOLO26, different output format
            if model_name == "yolo26":
                outputs = [grpcclient.InferRequestedOutput("output0")]

            # Run inference
            result = await client.infer(
                model_name=model_name,
                inputs=inputs,
                outputs=outputs,
                request_id="",
                timeout=self.config.timeout,
            )

            # Parse outputs
            if model_name == "yolo26":
                return {"output0": result.as_numpy("output0")}
            else:
                return {
                    "labels": result.as_numpy("labels"),
                    "boxes": result.as_numpy("boxes"),
                    "scores": result.as_numpy("scores"),
                }
        else:
            # HTTP client
            import tritonclient.http.aio as httpclient

            inputs = [
                httpclient.InferInput("images", list(input_tensor.shape), "FP32"),
            ]
            inputs[0].set_data_from_numpy(input_tensor)

            outputs = [
                httpclient.InferRequestedOutput("labels"),
                httpclient.InferRequestedOutput("boxes"),
                httpclient.InferRequestedOutput("scores"),
            ]

            if model_name == "yolo26":
                outputs = [httpclient.InferRequestedOutput("output0")]

            result = await client.infer(
                model_name=model_name,
                inputs=inputs,
                outputs=outputs,
                request_id="",
                timeout=self.config.timeout,
            )

            if model_name == "yolo26":
                return {"output0": result.as_numpy("output0")}
            else:
                return {
                    "labels": result.as_numpy("labels"),
                    "boxes": result.as_numpy("boxes"),
                    "scores": result.as_numpy("scores"),
                }

    def _postprocess_yolo26(
        self,
        outputs: dict[str, NDArray[Any]],
        original_size: tuple[int, int],
        threshold: float,
    ) -> list[Detection]:
        """Postprocess YOLO26 model outputs.

        Args:
            outputs: Raw model outputs
            original_size: Original image size (width, height)
            threshold: Confidence threshold

        Returns:
            List of Detection objects
        """
        labels = outputs["labels"][0]  # Remove batch dimension
        boxes = outputs["boxes"][0]
        scores = outputs["scores"][0]

        detections = []
        original_width, original_height = original_size

        for label, box, score in zip(labels, boxes, scores, strict=False):
            if score < threshold:
                continue

            # Get class name
            class_name = self._get_class_name_yolo26(int(label))
            if class_name not in self.SECURITY_CLASSES:
                continue

            # Scale box to original image size
            x1, y1, x2, y2 = box
            x1 = int(x1 * original_width / 640)
            y1 = int(y1 * original_height / 640)
            x2 = int(x2 * original_width / 640)
            y2 = int(y2 * original_height / 640)

            # Clamp to image bounds
            x1 = max(0, min(x1, original_width))
            y1 = max(0, min(y1, original_height))
            x2 = max(0, min(x2, original_width))
            y2 = max(0, min(y2, original_height))

            detections.append(
                Detection(
                    class_name=class_name,
                    confidence=float(score),
                    bbox=BoundingBox(
                        x=x1,
                        y=y1,
                        width=x2 - x1,
                        height=y2 - y1,
                    ),
                )
            )

        return detections

    def _postprocess_yolo(
        self,
        outputs: dict[str, NDArray[Any]],
        original_size: tuple[int, int],
        threshold: float,
    ) -> list[Detection]:
        """Postprocess YOLO26 model outputs.

        Args:
            outputs: Raw model outputs (output0: [batch, num_dets, 6])
            original_size: Original image size (width, height)
            threshold: Confidence threshold

        Returns:
            List of Detection objects
        """
        output = outputs["output0"][0]  # Remove batch dimension
        original_width, original_height = original_size

        detections = []

        for det in output:
            x1, y1, x2, y2, confidence, class_id = det

            if confidence < threshold:
                continue

            # Get class name from COCO ID
            class_name = self.COCO_ID_TO_NAME.get(int(class_id))
            if class_name is None or class_name not in self.SECURITY_CLASSES:
                continue

            # Scale box to original image size
            x1 = int(x1 * original_width / 640)
            y1 = int(y1 * original_height / 640)
            x2 = int(x2 * original_width / 640)
            y2 = int(y2 * original_height / 640)

            # Clamp to image bounds
            x1 = max(0, min(x1, original_width))
            y1 = max(0, min(y1, original_height))
            x2 = max(0, min(x2, original_width))
            y2 = max(0, min(y2, original_height))

            detections.append(
                Detection(
                    class_name=class_name,
                    confidence=float(confidence),
                    bbox=BoundingBox(
                        x=x1,
                        y=y1,
                        width=x2 - x1,
                        height=y2 - y1,
                    ),
                )
            )

        return detections

    def _get_class_name_yolo26(self, label_id: int) -> str:
        """Get class name from YOLO26 label ID.

        YOLO26 uses COCO class IDs. This mapping is the same as YOLO.

        Args:
            label_id: Model output label ID

        Returns:
            Class name string
        """
        return self.COCO_ID_TO_NAME.get(label_id, f"class_{label_id}")

    async def detect_batch(
        self,
        images: list[bytes | NDArray[np.uint8]],
        model_name: str | None = None,
        confidence_threshold: float | None = None,
    ) -> list[DetectionResult]:
        """Run batch detection on multiple images.

        This leverages Triton's dynamic batching for efficient inference.

        Args:
            images: List of images as bytes or numpy arrays
            model_name: Model to use (uses default if None)
            confidence_threshold: Filter threshold (uses config default if None)

        Returns:
            List of DetectionResult objects, one per image
        """
        model = model_name or self.config.default_model
        threshold = confidence_threshold or self.config.confidence_threshold

        if not images:
            return []

        # For now, process individually (Triton handles batching at server level)
        # Future optimization: batch preprocessing and single inference call
        results = []
        for image in images:
            result = await self.detect(image, model, threshold)
            results.append(result)

        return results

    async def get_server_statistics(self) -> dict[str, Any]:
        """Get server-wide statistics from Triton.

        Returns:
            Dictionary of server statistics
        """
        if not self._connected:
            await self.connect()

        try:
            client = self._get_client()
            # gRPC client has different method signature
            if self.config.protocol == TritonProtocol.GRPC:
                stats = await client.get_inference_statistics(model_name="")
            else:
                stats = await client.get_inference_statistics(model_name="")
            return {"statistics": stats}
        except Exception as e:
            logger.warning(f"Failed to get server statistics: {e}")
            return {}

    async def get_model_statistics(self, model_name: str | None = None) -> dict[str, Any]:
        """Get statistics for a specific model.

        Args:
            model_name: Model to query (uses default if None)

        Returns:
            Dictionary of model statistics
        """
        model = model_name or self.config.default_model

        if not self._connected:
            await self.connect()

        try:
            client = self._get_client()
            stats = await client.get_inference_statistics(model_name=model)
            return {"model": model, "statistics": stats}
        except Exception as e:
            logger.warning(f"Failed to get model statistics for {model}: {e}")
            return {}
