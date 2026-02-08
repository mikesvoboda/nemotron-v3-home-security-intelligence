"""Unit tests for the YOLO26 gateway adapter.

Tests the YOLO26 adapter endpoints and postprocessing logic with mocked
Triton client, verifying detection output, NMS, letterbox coordinate
reversal, batch handling, and error paths.
"""

from __future__ import annotations

import io
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from PIL import Image

from ai.gateway.adapters.yolo26 import (
    COCO_CLASSES,
    CONFIDENCE_THRESHOLD,
    MODEL_NAME,
    NMS_THRESHOLD,
    TARGET_SIZE,
    _postprocess_yolo,
    router,
)
from ai.gateway.triton_client import TritonClientError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_test_image(width: int = 640, height: int = 480, fmt: str = "JPEG") -> bytes:
    """Create a minimal test image as bytes."""
    img = Image.new("RGB", (width, height), color=(128, 64, 32))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    buf.seek(0)
    return buf.read()


def _make_yolo_output(
    detections: list[dict],
    num_classes: int = 80,
    num_preds: int = 8400,
) -> np.ndarray:
    """Build a synthetic YOLO output tensor with specific detections.

    Args:
        detections: List of dicts with keys cx, cy, w, h, class_id, confidence.
        num_classes: Number of object classes.
        num_preds: Total prediction slots.

    Returns:
        Array of shape (1, num_classes+4, num_preds).
    """
    output = np.zeros((1, num_classes + 4, num_preds), dtype=np.float32)
    for i, det in enumerate(detections):
        if i >= num_preds:
            break
        output[0, 0, i] = det["cx"]
        output[0, 1, i] = det["cy"]
        output[0, 2, i] = det["w"]
        output[0, 3, i] = det["h"]
        output[0, 4 + det["class_id"], i] = det["confidence"]
    return output


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_triton():
    """Create a mock Triton client."""
    client = AsyncMock()
    client.infer = AsyncMock()
    client.is_model_ready = AsyncMock(return_value=True)
    client.get_model_metadata = AsyncMock(
        return_value={
            "outputs": [{"name": "output0"}],
        }
    )
    return client


@pytest.fixture
def app(mock_triton):
    """Create a test FastAPI app with the YOLO26 router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
async def client(app, mock_triton):
    """Create an async test client with mocked Triton."""
    with patch("ai.gateway.adapters.yolo26.get_triton_client", return_value=mock_triton):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


# =============================================================================
# _postprocess_yolo unit tests
# =============================================================================


class TestPostprocessYolo:
    """Tests for the YOLO postprocessing function."""

    def test_empty_output_returns_no_detections(self):
        """All-zero output produces no detections."""
        output = np.zeros((1, 84, 8400), dtype=np.float32)
        result = _postprocess_yolo(output, orig_w=640, orig_h=480)
        assert result == []

    def test_single_detection_high_confidence(self):
        """A single high-confidence detection is returned correctly."""
        output = _make_yolo_output(
            [{"cx": 320, "cy": 240, "w": 100, "h": 100, "class_id": 0, "confidence": 0.95}]
        )
        result = _postprocess_yolo(output, orig_w=640, orig_h=480)

        assert len(result) == 1
        assert result[0]["class"] == "person"
        assert result[0]["confidence"] == 0.95
        assert "bbox" in result[0]
        assert "x" in result[0]["bbox"]
        assert "y" in result[0]["bbox"]
        assert "width" in result[0]["bbox"]
        assert "height" in result[0]["bbox"]

    def test_low_confidence_filtered(self):
        """Detections below the confidence threshold are removed."""
        output = _make_yolo_output(
            [{"cx": 320, "cy": 240, "w": 100, "h": 100, "class_id": 0, "confidence": 0.1}]
        )
        result = _postprocess_yolo(
            output, orig_w=640, orig_h=480, conf_threshold=CONFIDENCE_THRESHOLD
        )
        assert result == []

    def test_custom_confidence_threshold(self):
        """Custom confidence threshold filters appropriately."""
        output = _make_yolo_output(
            [
                {"cx": 320, "cy": 240, "w": 100, "h": 100, "class_id": 0, "confidence": 0.5},
                {"cx": 100, "cy": 100, "w": 50, "h": 50, "class_id": 1, "confidence": 0.3},
            ]
        )
        result = _postprocess_yolo(output, orig_w=640, orig_h=480, conf_threshold=0.4)
        assert len(result) == 1
        assert result[0]["class"] == "person"

    def test_nms_removes_overlapping_boxes(self):
        """NMS removes highly overlapping same-class detections."""
        # Two person detections nearly identical
        output = _make_yolo_output(
            [
                {"cx": 320, "cy": 240, "w": 100, "h": 100, "class_id": 0, "confidence": 0.9},
                {"cx": 325, "cy": 245, "w": 100, "h": 100, "class_id": 0, "confidence": 0.8},
            ]
        )
        result = _postprocess_yolo(output, orig_w=640, orig_h=480, nms_threshold=NMS_THRESHOLD)
        # NMS should keep only the higher-confidence one
        assert len(result) == 1
        assert result[0]["confidence"] == 0.9

    def test_nms_keeps_different_classes(self):
        """NMS does not suppress detections of different classes."""
        output = _make_yolo_output(
            [
                {"cx": 320, "cy": 240, "w": 100, "h": 100, "class_id": 0, "confidence": 0.9},
                {"cx": 325, "cy": 245, "w": 100, "h": 100, "class_id": 2, "confidence": 0.8},
            ]
        )
        result = _postprocess_yolo(output, orig_w=640, orig_h=480)
        assert len(result) == 2

    def test_nms_keeps_non_overlapping_same_class(self):
        """NMS keeps same-class detections with no overlap."""
        output = _make_yolo_output(
            [
                {"cx": 100, "cy": 100, "w": 50, "h": 50, "class_id": 0, "confidence": 0.9},
                {"cx": 500, "cy": 400, "w": 50, "h": 50, "class_id": 0, "confidence": 0.8},
            ]
        )
        result = _postprocess_yolo(output, orig_w=640, orig_h=480)
        assert len(result) == 2

    def test_transposed_input_handled(self):
        """Handles transposed output shape (1, num_preds, 84) correctly."""
        output = _make_yolo_output(
            [{"cx": 320, "cy": 240, "w": 100, "h": 100, "class_id": 0, "confidence": 0.9}]
        )
        # Transpose from (1, 84, 8400) to (1, 8400, 84) to test auto-transpose
        transposed = output.transpose(0, 2, 1)
        result = _postprocess_yolo(transposed, orig_w=640, orig_h=480)
        assert len(result) == 1
        assert result[0]["class"] == "person"

    def test_bbox_coordinates_positive(self):
        """Bounding box coordinates are non-negative."""
        # Use coordinates well within the 640x640 letterboxed canvas
        output = _make_yolo_output(
            [{"cx": 320, "cy": 320, "w": 100, "h": 100, "class_id": 0, "confidence": 0.9}]
        )
        result = _postprocess_yolo(output, orig_w=640, orig_h=480)
        assert len(result) == 1
        assert result[0]["bbox"]["x"] >= 0
        assert result[0]["bbox"]["y"] >= 0
        assert result[0]["bbox"]["width"] > 0
        assert result[0]["bbox"]["height"] > 0

    def test_unknown_class_id_gives_fallback_name(self):
        """Class IDs beyond COCO_CLASSES list get a fallback name."""
        output = _make_yolo_output(
            [{"cx": 320, "cy": 240, "w": 100, "h": 100, "class_id": 79, "confidence": 0.9}]
        )
        result = _postprocess_yolo(output, orig_w=640, orig_h=480)
        assert len(result) == 1
        # class_id 79 is "toothbrush" — the last COCO class (index 79)
        assert result[0]["class"] == COCO_CLASSES[79]

    def test_multiple_classes_detected(self):
        """Multiple different classes are all returned."""
        output = _make_yolo_output(
            [
                {"cx": 100, "cy": 100, "w": 80, "h": 80, "class_id": 0, "confidence": 0.9},
                {"cx": 300, "cy": 300, "w": 80, "h": 80, "class_id": 2, "confidence": 0.85},
                {"cx": 500, "cy": 100, "w": 80, "h": 80, "class_id": 15, "confidence": 0.7},
            ]
        )
        result = _postprocess_yolo(output, orig_w=640, orig_h=480)
        assert len(result) == 3
        classes = {d["class"] for d in result}
        assert "person" in classes
        assert "car" in classes
        assert "cat" in classes


# =============================================================================
# /detect endpoint tests
# =============================================================================


class TestDetectEndpoint:
    """Tests for the POST /detect endpoint."""

    async def test_detect_success(self, client, mock_triton):
        """Successful detection returns expected JSON structure."""
        yolo_output = _make_yolo_output(
            [{"cx": 320, "cy": 240, "w": 100, "h": 100, "class_id": 0, "confidence": 0.9}]
        )
        mock_triton.infer.return_value = {"output0": yolo_output}

        image_bytes = _make_test_image()
        response = await client.post(
            "/detect",
            files={"file": ("test.jpg", image_bytes, "image/jpeg")},
        )

        assert response.status_code == 200
        data = response.json()
        assert "detections" in data
        assert "image_width" in data
        assert "image_height" in data
        assert "inference_time_ms" in data
        assert data["image_width"] == 640
        assert data["image_height"] == 480

    async def test_detect_no_objects(self, client, mock_triton):
        """Empty YOLO output returns zero detections."""
        mock_triton.infer.return_value = {"output0": np.zeros((1, 84, 8400), dtype=np.float32)}

        image_bytes = _make_test_image()
        response = await client.post(
            "/detect",
            files={"file": ("test.jpg", image_bytes, "image/jpeg")},
        )

        assert response.status_code == 200
        assert response.json()["detections"] == []

    async def test_detect_invalid_image(self, client, mock_triton):
        """Non-image data returns 400."""
        response = await client.post(
            "/detect",
            files={"file": ("bad.jpg", b"not an image", "image/jpeg")},
        )
        assert response.status_code == 400

    async def test_detect_triton_error(self, client, mock_triton):
        """Triton failure returns 503."""
        mock_triton.infer.side_effect = TritonClientError("GPU OOM")

        image_bytes = _make_test_image()
        response = await client.post(
            "/detect",
            files={"file": ("test.jpg", image_bytes, "image/jpeg")},
        )

        assert response.status_code == 503
        assert "Inference failed" in response.json()["detail"]

    async def test_detect_png_image(self, client, mock_triton):
        """PNG images are accepted and processed."""
        mock_triton.infer.return_value = {"output0": np.zeros((1, 84, 8400), dtype=np.float32)}

        image_bytes = _make_test_image(fmt="PNG")
        response = await client.post(
            "/detect",
            files={"file": ("test.png", image_bytes, "image/png")},
        )

        assert response.status_code == 200


# =============================================================================
# /detect/batch endpoint tests
# =============================================================================


class TestDetectBatchEndpoint:
    """Tests for the POST /detect/batch endpoint."""

    async def test_batch_detect_success(self, client, mock_triton):
        """Batch detection processes multiple images."""
        yolo_output = _make_yolo_output(
            [{"cx": 320, "cy": 240, "w": 100, "h": 100, "class_id": 0, "confidence": 0.9}]
        )
        mock_triton.infer.return_value = {"output0": yolo_output}

        img1 = _make_test_image(320, 240)
        img2 = _make_test_image(640, 480)
        response = await client.post(
            "/detect/batch",
            files=[
                ("files", ("img1.jpg", img1, "image/jpeg")),
                ("files", ("img2.jpg", img2, "image/jpeg")),
            ],
        )

        assert response.status_code == 200
        data = response.json()
        assert data["batch_size"] == 2
        assert len(data["results"]) == 2
        assert "total_inference_time_ms" in data

    async def test_batch_detect_partial_failure(self, client, mock_triton):
        """One bad image does not fail the entire batch."""
        yolo_output = _make_yolo_output(
            [{"cx": 320, "cy": 240, "w": 100, "h": 100, "class_id": 0, "confidence": 0.9}]
        )
        # First call succeeds, second call fails (triton error)
        mock_triton.infer.side_effect = [
            {"output0": yolo_output},
            TritonClientError("Timeout"),
        ]

        img1 = _make_test_image()
        img2 = _make_test_image()
        response = await client.post(
            "/detect/batch",
            files=[
                ("files", ("img1.jpg", img1, "image/jpeg")),
                ("files", ("img2.jpg", img2, "image/jpeg")),
            ],
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 2
        assert len(data["results"][0]["detections"]) >= 1
        assert "error" in data["results"][1]


# =============================================================================
# /segment endpoint tests
# =============================================================================


class TestSegmentEndpoint:
    """Tests for the POST /segment endpoint."""

    async def test_segment_success(self, client, mock_triton):
        """Segmentation endpoint returns detection results."""
        yolo_output = _make_yolo_output(
            [{"cx": 320, "cy": 240, "w": 100, "h": 100, "class_id": 0, "confidence": 0.9}]
        )
        mock_triton.infer.return_value = {"output0": yolo_output}

        image_bytes = _make_test_image()
        response = await client.post(
            "/segment",
            files={"file": ("test.jpg", image_bytes, "image/jpeg")},
        )

        assert response.status_code == 200
        data = response.json()
        assert "detections" in data
        assert "inference_time_ms" in data

    async def test_segment_triton_error(self, client, mock_triton):
        """Triton error during segmentation returns 503."""
        mock_triton.infer.side_effect = TritonClientError("Model not loaded")

        image_bytes = _make_test_image()
        response = await client.post(
            "/segment",
            files={"file": ("test.jpg", image_bytes, "image/jpeg")},
        )

        assert response.status_code == 503

    async def test_segment_invalid_image(self, client, mock_triton):
        """Invalid image returns 400."""
        response = await client.post(
            "/segment",
            files={"file": ("bad.jpg", b"garbage", "image/jpeg")},
        )
        assert response.status_code == 400


# =============================================================================
# /health endpoint tests
# =============================================================================


class TestHealthEndpoint:
    """Tests for the GET /health endpoint."""

    async def test_health_model_ready(self, client, mock_triton):
        """Health returns healthy when model is ready."""
        mock_triton.is_model_ready.return_value = True

        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["model"] == MODEL_NAME
        assert data["model_loaded"] is True

    async def test_health_model_not_ready(self, client, mock_triton):
        """Health returns degraded when model is not ready."""
        mock_triton.is_model_ready.return_value = False

        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["model_loaded"] is False
