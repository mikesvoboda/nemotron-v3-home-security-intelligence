"""Unit tests for Triton Inference Server client.

These tests verify the Triton client wrapper functionality using mocks.
For integration tests that require a running Triton server, see test_integration.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from ai.triton.client import (
    BoundingBox,
    Detection,
    DetectionResult,
    TritonClient,
    TritonConfig,
    TritonConnectionError,
    TritonInferenceError,
    TritonProtocol,
)


class TestTritonConfig:
    """Tests for TritonConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = TritonConfig()
        assert config.enabled is False
        assert config.grpc_url == "localhost:8001"
        assert config.http_url == "localhost:8000"
        assert config.protocol == TritonProtocol.GRPC
        assert config.timeout == 60.0
        assert config.default_model == "rtdetr"
        assert config.max_retries == 3
        assert config.confidence_threshold == 0.5

    def test_from_env_defaults(self) -> None:
        """Test configuration from environment with defaults."""
        with patch.dict("os.environ", {}, clear=True):
            config = TritonConfig.from_env()
            assert config.enabled is False
            assert config.grpc_url == "localhost:8001"
            assert config.protocol == TritonProtocol.GRPC

    def test_from_env_custom_values(self) -> None:
        """Test configuration from custom environment variables."""
        env_vars = {
            "TRITON_ENABLED": "true",
            "TRITON_URL": "triton-server:8001",
            "TRITON_HTTP_URL": "triton-server:8000",
            "TRITON_PROTOCOL": "http",
            "TRITON_TIMEOUT": "120",
            "TRITON_MODEL": "yolo26",
            "TRITON_MAX_RETRIES": "5",
            "TRITON_CONFIDENCE_THRESHOLD": "0.7",
            "TRITON_VERBOSE": "true",
        }
        with patch.dict("os.environ", env_vars, clear=True):
            config = TritonConfig.from_env()
            assert config.enabled is True
            assert config.grpc_url == "triton-server:8001"
            assert config.http_url == "triton-server:8000"
            assert config.protocol == TritonProtocol.HTTP
            assert config.timeout == 120.0
            assert config.default_model == "yolo26"
            assert config.max_retries == 5
            assert config.confidence_threshold == 0.7
            assert config.verbose is True


class TestTritonClientInit:
    """Tests for TritonClient initialization."""

    def test_init_with_config(self, triton_config: TritonConfig) -> None:
        """Test client initialization with provided config."""
        client = TritonClient(triton_config)
        assert client.config == triton_config
        assert client._connected is False

    def test_init_without_config(self) -> None:
        """Test client initialization with default config from env."""
        with patch.dict("os.environ", {}, clear=True):
            client = TritonClient()
            assert client.config.enabled is False

    def test_security_classes_defined(self) -> None:
        """Test that security classes are properly defined."""
        assert "person" in TritonClient.SECURITY_CLASSES
        assert "car" in TritonClient.SECURITY_CLASSES
        assert "truck" in TritonClient.SECURITY_CLASSES
        assert "dog" in TritonClient.SECURITY_CLASSES
        assert "cat" in TritonClient.SECURITY_CLASSES

    def test_coco_id_to_name_mapping(self) -> None:
        """Test COCO class ID to name mapping."""
        assert TritonClient.COCO_ID_TO_NAME[0] == "person"
        assert TritonClient.COCO_ID_TO_NAME[2] == "car"
        assert TritonClient.COCO_ID_TO_NAME[16] == "dog"


class TestTritonClientHealth:
    """Tests for health check functionality."""

    @pytest.mark.asyncio
    async def test_is_healthy_when_disabled(self, triton_config_disabled: TritonConfig) -> None:
        """Test health check returns False when Triton is disabled."""
        client = TritonClient(triton_config_disabled)
        result = await client.is_healthy()
        assert result is False

    @pytest.mark.asyncio
    async def test_is_healthy_connection_error(self, triton_config: TritonConfig) -> None:
        """Test health check returns False on connection error."""
        client = TritonClient(triton_config)
        with patch.object(
            client, "connect", side_effect=TritonConnectionError("Connection failed")
        ):
            result = await client.is_healthy()
            assert result is False

    @pytest.mark.asyncio
    async def test_is_model_ready_when_disabled(self, triton_config_disabled: TritonConfig) -> None:
        """Test model ready check returns False when disabled."""
        client = TritonClient(triton_config_disabled)
        result = await client.is_model_ready("rtdetr")
        assert result is False


class TestTritonClientPreprocess:
    """Tests for image preprocessing."""

    def test_preprocess_image_bytes(
        self, triton_config: TritonConfig, sample_image_bytes: bytes
    ) -> None:
        """Test preprocessing image from bytes."""
        client = TritonClient(triton_config)
        tensor, original_size = client._preprocess_image(sample_image_bytes)

        # Check tensor shape: [batch, channels, height, width]
        assert tensor.shape == (1, 3, 640, 640)
        assert tensor.dtype == np.float32

        # Check values are normalized to [0, 1]
        assert tensor.min() >= 0.0
        assert tensor.max() <= 1.0

        # Check original size
        assert original_size == (640, 480)  # width, height

    def test_preprocess_image_array(
        self, triton_config: TritonConfig, sample_image_array: np.ndarray
    ) -> None:
        """Test preprocessing image from numpy array."""
        client = TritonClient(triton_config)
        tensor, original_size = client._preprocess_image(sample_image_array)

        assert tensor.shape == (1, 3, 640, 640)
        assert tensor.dtype == np.float32
        assert original_size == (640, 480)


class TestTritonClientPostprocess:
    """Tests for detection postprocessing."""

    def test_postprocess_rtdetr(
        self,
        triton_config: TritonConfig,
        mock_rtdetr_outputs: dict[str, np.ndarray],
    ) -> None:
        """Test RT-DETR output postprocessing."""
        client = TritonClient(triton_config)
        original_size = (1280, 720)  # width, height

        detections = client._postprocess_rtdetr(mock_rtdetr_outputs, original_size, threshold=0.5)

        # Should have 3 detections above threshold (person, car, dog)
        assert len(detections) == 3

        # Check first detection (person)
        assert detections[0].class_name == "person"
        assert detections[0].confidence == pytest.approx(0.95)
        assert isinstance(detections[0].bbox, BoundingBox)

        # Check second detection (car)
        assert detections[1].class_name == "car"
        assert detections[1].confidence == pytest.approx(0.87)

        # Check third detection (dog)
        assert detections[2].class_name == "dog"
        assert detections[2].confidence == pytest.approx(0.72)

    def test_postprocess_rtdetr_filters_low_confidence(
        self,
        triton_config: TritonConfig,
    ) -> None:
        """Test that low confidence detections are filtered."""
        client = TritonClient(triton_config)

        # Create outputs with low confidence
        outputs = {
            "labels": np.array([[0]]),
            "boxes": np.array([[[100, 100, 200, 200]]], dtype=np.float32),
            "scores": np.array([[0.3]], dtype=np.float32),  # Below 0.5 threshold
        }

        detections = client._postprocess_rtdetr(outputs, (640, 480), threshold=0.5)
        assert len(detections) == 0

    def test_postprocess_rtdetr_filters_non_security_classes(
        self,
        triton_config: TritonConfig,
    ) -> None:
        """Test that non-security classes are filtered."""
        client = TritonClient(triton_config)

        # Class 10 is not in SECURITY_CLASSES
        outputs = {
            "labels": np.array([[10]]),
            "boxes": np.array([[[100, 100, 200, 200]]], dtype=np.float32),
            "scores": np.array([[0.95]], dtype=np.float32),
        }

        detections = client._postprocess_rtdetr(outputs, (640, 480), threshold=0.5)
        assert len(detections) == 0

    def test_postprocess_yolo(
        self,
        triton_config: TritonConfig,
        mock_yolo_outputs: dict[str, np.ndarray],
    ) -> None:
        """Test YOLO26 output postprocessing."""
        client = TritonClient(triton_config)
        original_size = (1280, 720)

        detections = client._postprocess_yolo(mock_yolo_outputs, original_size, threshold=0.5)

        # Should have 3 detections above threshold
        assert len(detections) == 3

        # Verify detection classes
        class_names = [d.class_name for d in detections]
        assert "person" in class_names
        assert "car" in class_names
        assert "dog" in class_names

    def test_postprocess_yolo_filters_low_confidence(
        self,
        triton_config: TritonConfig,
    ) -> None:
        """Test YOLO filtering of low confidence detections."""
        client = TritonClient(triton_config)

        outputs = {
            "output0": np.array(
                [
                    [[100, 100, 200, 200, 0.3, 0]]  # Low confidence person
                ],
                dtype=np.float32,
            ),
        }

        detections = client._postprocess_yolo(outputs, (640, 480), threshold=0.5)
        assert len(detections) == 0


class TestTritonClientDetection:
    """Tests for the detect method."""

    @pytest.mark.asyncio
    async def test_detect_not_connected(
        self, triton_config: TritonConfig, sample_image_bytes: bytes
    ) -> None:
        """Test that detect auto-connects when not connected."""
        client = TritonClient(triton_config)

        # Mock connect and _infer
        client.connect = AsyncMock()
        client._connected = True

        # Mock the _infer method directly instead of the grpc client
        mock_outputs = {
            "labels": np.array([[0]]),
            "boxes": np.array([[[100, 100, 200, 200]]], dtype=np.float32),
            "scores": np.array([[0.95]], dtype=np.float32),
        }
        client._infer = AsyncMock(return_value=mock_outputs)

        result = await client.detect(sample_image_bytes)

        assert isinstance(result, DetectionResult)
        assert result.model_name == "rtdetr"

    @pytest.mark.asyncio
    async def test_detect_retry_on_failure(
        self, triton_config: TritonConfig, sample_image_bytes: bytes
    ) -> None:
        """Test that detect retries on transient failures."""
        triton_config.max_retries = 3
        triton_config.retry_delay = 0.01  # Fast retry for test

        client = TritonClient(triton_config)
        client._connected = True

        # First two calls fail, third succeeds
        call_count = 0

        async def mock_infer(*_args: object, **_kwargs: object) -> dict[str, np.ndarray]:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Transient error")

            return {
                "labels": np.array([[0]]),
                "boxes": np.array([[[100, 100, 200, 200]]], dtype=np.float32),
                "scores": np.array([[0.95]], dtype=np.float32),
            }

        client._infer = mock_infer

        result = await client.detect(sample_image_bytes)

        assert call_count == 3
        assert len(result.detections) == 1

    @pytest.mark.asyncio
    async def test_detect_raises_after_max_retries(
        self, triton_config: TritonConfig, sample_image_bytes: bytes
    ) -> None:
        """Test that detect raises error after max retries exhausted."""
        triton_config.max_retries = 2
        triton_config.retry_delay = 0.01

        client = TritonClient(triton_config)
        client._connected = True
        client._infer = AsyncMock(side_effect=Exception("Persistent error"))

        with pytest.raises(TritonInferenceError) as exc_info:
            await client.detect(sample_image_bytes)

        assert "2 attempts" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_detect_uses_custom_threshold(
        self, triton_config: TritonConfig, sample_image_bytes: bytes
    ) -> None:
        """Test that detect respects custom confidence threshold."""
        client = TritonClient(triton_config)
        client._connected = True

        # Mock inference result with confidence 0.6
        mock_outputs = {
            "labels": np.array([[0]]),
            "boxes": np.array([[[100, 100, 200, 200]]], dtype=np.float32),
            "scores": np.array([[0.6]], dtype=np.float32),
        }
        client._infer = AsyncMock(return_value=mock_outputs)

        # With high threshold (0.8), should filter out
        result = await client.detect(sample_image_bytes, confidence_threshold=0.8)
        assert len(result.detections) == 0

        # With lower threshold (0.5), should include
        result = await client.detect(sample_image_bytes, confidence_threshold=0.5)
        assert len(result.detections) == 1


class TestTritonClientBatch:
    """Tests for batch detection."""

    @pytest.mark.asyncio
    async def test_detect_batch_empty(self, triton_config: TritonConfig) -> None:
        """Test batch detection with empty list."""
        client = TritonClient(triton_config)
        results = await client.detect_batch([])
        assert results == []

    @pytest.mark.asyncio
    async def test_detect_batch_single_image(
        self, triton_config: TritonConfig, sample_image_bytes: bytes
    ) -> None:
        """Test batch detection with single image."""
        client = TritonClient(triton_config)
        client._connected = True

        # Mock _infer directly
        mock_outputs = {
            "labels": np.array([[0]]),
            "boxes": np.array([[[100, 100, 200, 200]]], dtype=np.float32),
            "scores": np.array([[0.95]], dtype=np.float32),
        }
        client._infer = AsyncMock(return_value=mock_outputs)

        results = await client.detect_batch([sample_image_bytes])

        assert len(results) == 1
        assert isinstance(results[0], DetectionResult)

    @pytest.mark.asyncio
    async def test_detect_batch_multiple_images(
        self, triton_config: TritonConfig, sample_image_bytes: bytes
    ) -> None:
        """Test batch detection with multiple images."""
        client = TritonClient(triton_config)
        client._connected = True

        # Mock _infer directly
        mock_outputs = {
            "labels": np.array([[0]]),
            "boxes": np.array([[[100, 100, 200, 200]]], dtype=np.float32),
            "scores": np.array([[0.95]], dtype=np.float32),
        }
        client._infer = AsyncMock(return_value=mock_outputs)

        images = [sample_image_bytes, sample_image_bytes, sample_image_bytes]
        results = await client.detect_batch(images)

        assert len(results) == 3
        for result in results:
            assert isinstance(result, DetectionResult)


class TestTritonClientClose:
    """Tests for client cleanup."""

    @pytest.mark.asyncio
    async def test_close_grpc_client(self, triton_config: TritonConfig) -> None:
        """Test closing gRPC client."""
        client = TritonClient(triton_config)
        mock_grpc = MagicMock()
        mock_grpc.close = AsyncMock()
        client._grpc_client = mock_grpc
        client._connected = True

        await client.close()

        # Check mock was called before client set it to None
        mock_grpc.close.assert_called_once()
        assert client._grpc_client is None
        assert client._connected is False

    @pytest.mark.asyncio
    async def test_close_http_client(self, triton_config: TritonConfig) -> None:
        """Test closing HTTP client."""
        triton_config.protocol = TritonProtocol.HTTP
        client = TritonClient(triton_config)
        mock_http = MagicMock()
        mock_http.close = AsyncMock()
        client._http_client = mock_http
        client._connected = True

        await client.close()

        # Check mock was called before client set it to None
        mock_http.close.assert_called_once()
        assert client._http_client is None
        assert client._connected is False


class TestDetectionDataClasses:
    """Tests for Detection and BoundingBox dataclasses."""

    def test_bounding_box_creation(self) -> None:
        """Test BoundingBox creation."""
        bbox = BoundingBox(x=100, y=50, width=200, height=150)
        assert bbox.x == 100
        assert bbox.y == 50
        assert bbox.width == 200
        assert bbox.height == 150

    def test_detection_creation(self) -> None:
        """Test Detection creation."""
        bbox = BoundingBox(x=100, y=50, width=200, height=150)
        detection = Detection(class_name="person", confidence=0.95, bbox=bbox)
        assert detection.class_name == "person"
        assert detection.confidence == 0.95
        assert detection.bbox == bbox

    def test_detection_result_creation(self) -> None:
        """Test DetectionResult creation."""
        result = DetectionResult(
            detections=[],
            inference_time_ms=25.5,
            image_width=1920,
            image_height=1080,
            model_name="rtdetr",
            model_version="1",
        )
        assert result.inference_time_ms == 25.5
        assert result.image_width == 1920
        assert result.image_height == 1080
        assert result.model_name == "rtdetr"
        assert result.model_version == "1"

    def test_detection_result_defaults(self) -> None:
        """Test DetectionResult default values."""
        result = DetectionResult()
        assert result.detections == []
        assert result.inference_time_ms == 0.0
        assert result.image_width == 0
        assert result.image_height == 0
        assert result.model_name == ""
        assert result.model_version == ""
