"""Unit tests for the Florence-2 gateway adapter.

Tests the Florence-2 adapter endpoints (extract, batch-extract, ocr,
ocr-with-regions, detect, dense-caption, describe-region, phrase-grounding,
detect_security_objects, analyze-scene, health) with mocked Triton client.
"""

from __future__ import annotations

import base64
import io
import json
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from PIL import Image

from ai.gateway.adapters.florence import (
    MODEL_NAME,
    SECURITY_OBJECTS,
    _florence_infer,
    _parse_json_output,
    router,
)
from ai.gateway.triton_client import TritonClientError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_b64_image(width: int = 224, height: int = 224) -> str:
    """Create a small test image encoded as base64."""
    img = Image.new("RGB", (width, height), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _make_triton_text_output(text: str) -> dict[str, np.ndarray]:
    """Create a mock Triton output dict with text encoded as bytes."""
    arr = np.array([text.encode("utf-8")], dtype=object)
    return {"result": arr}


def _make_triton_json_output(data: dict | list) -> dict[str, np.ndarray]:
    """Create a mock Triton output dict with JSON-encoded data."""
    return _make_triton_text_output(json.dumps(data))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_triton():
    """Create a mock Triton client."""
    client = AsyncMock()
    client.infer = AsyncMock()
    client.is_model_ready = AsyncMock(return_value=True)
    return client


@pytest.fixture
def app():
    """Create a test FastAPI app with the Florence router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
async def client(app, mock_triton):
    """Create an async test client with mocked Triton."""
    with patch("ai.gateway.adapters.florence.get_triton_client", return_value=mock_triton):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


# =============================================================================
# _parse_json_output unit tests
# =============================================================================


class TestParseJsonOutput:
    """Tests for the JSON output parser."""

    def test_valid_json_dict(self):
        """Parses a valid JSON dict string."""
        result = _parse_json_output('{"key": "value"}')
        assert result == {"key": "value"}

    def test_valid_json_list(self):
        """Parses a valid JSON list string."""
        result = _parse_json_output("[1, 2, 3]")
        assert result == [1, 2, 3]

    def test_plain_text_fallback(self):
        """Returns raw text when not valid JSON."""
        result = _parse_json_output("A cat sitting on a mat")
        assert result == "A cat sitting on a mat"

    def test_empty_string(self):
        """Returns empty string for empty input."""
        result = _parse_json_output("")
        assert result == ""


# =============================================================================
# /extract endpoint tests
# =============================================================================


class TestExtractEndpoint:
    """Tests for the POST /extract endpoint."""

    async def test_extract_success(self, client, mock_triton):
        """Successful extraction returns result text."""
        mock_triton.infer.return_value = _make_triton_text_output("A sunny garden")

        response = await client.post(
            "/extract",
            json={"image": _make_b64_image(), "prompt": "<CAPTION>"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["result"] == "A sunny garden"
        assert data["prompt_used"] == "<CAPTION>"
        assert "inference_time_ms" in data

    async def test_extract_default_prompt(self, client, mock_triton):
        """Uses default <CAPTION> prompt when not specified."""
        mock_triton.infer.return_value = _make_triton_text_output("A house")

        response = await client.post(
            "/extract",
            json={"image": _make_b64_image()},
        )

        assert response.status_code == 200
        assert response.json()["prompt_used"] == "<CAPTION>"

    async def test_extract_invalid_image(self, client, mock_triton):
        """Invalid base64 image returns 400."""
        response = await client.post(
            "/extract",
            json={"image": "!!!invalid!!!", "prompt": "<CAPTION>"},
        )
        assert response.status_code == 400

    async def test_extract_triton_error(self, client, mock_triton):
        """Triton failure returns 503."""
        mock_triton.infer.side_effect = TritonClientError("Backend error")

        response = await client.post(
            "/extract",
            json={"image": _make_b64_image(), "prompt": "<CAPTION>"},
        )
        assert response.status_code == 503


# =============================================================================
# /batch-extract endpoint tests
# =============================================================================


class TestBatchExtractEndpoint:
    """Tests for the POST /batch-extract endpoint."""

    async def test_batch_extract_success(self, client, mock_triton):
        """Batch extraction processes all items."""
        mock_triton.infer.return_value = _make_triton_text_output("Result text")

        response = await client.post(
            "/batch-extract",
            json={
                "items": [
                    {"image": _make_b64_image(), "prompt": "<CAPTION>"},
                    {"image": _make_b64_image(), "prompt": "<OCR>"},
                ]
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["batch_size"] == 2
        assert len(data["results"]) == 2
        assert all(r["result"] == "Result text" for r in data["results"])

    async def test_batch_extract_partial_failure(self, client, mock_triton):
        """One failing item does not fail the entire batch."""
        mock_triton.infer.side_effect = [
            _make_triton_text_output("Good result"),
            TritonClientError("Model OOM"),
        ]

        response = await client.post(
            "/batch-extract",
            json={
                "items": [
                    {"image": _make_b64_image(), "prompt": "<CAPTION>"},
                    {"image": _make_b64_image(), "prompt": "<OCR>"},
                ]
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["results"][0]["result"] == "Good result"
        assert data["results"][1]["error"] is not None


# =============================================================================
# /ocr endpoint tests
# =============================================================================


class TestOcrEndpoint:
    """Tests for the POST /ocr endpoint."""

    async def test_ocr_success(self, client, mock_triton):
        """OCR returns extracted text."""
        mock_triton.infer.return_value = _make_triton_text_output("STOP AHEAD")

        response = await client.post(
            "/ocr",
            json={"image": _make_b64_image()},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["text"] == "STOP AHEAD"
        assert "inference_time_ms" in data


# =============================================================================
# /ocr-with-regions endpoint tests
# =============================================================================


class TestOcrWithRegionsEndpoint:
    """Tests for the POST /ocr-with-regions endpoint."""

    async def test_ocr_with_regions_structured(self, client, mock_triton):
        """Structured JSON output produces region list."""
        mock_triton.infer.return_value = _make_triton_json_output(
            {
                "quad_boxes": [[10, 20, 100, 20, 100, 50, 10, 50]],
                "labels": ["EXIT"],
            }
        )

        response = await client.post(
            "/ocr-with-regions",
            json={"image": _make_b64_image()},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["regions"]) == 1
        assert data["regions"][0]["text"] == "EXIT"
        assert len(data["regions"][0]["bbox"]) > 0

    async def test_ocr_with_regions_plain_text(self, client, mock_triton):
        """Plain text output (not JSON) returns empty regions."""
        mock_triton.infer.return_value = _make_triton_text_output("Just text, no JSON")

        response = await client.post(
            "/ocr-with-regions",
            json={"image": _make_b64_image()},
        )

        assert response.status_code == 200
        assert response.json()["regions"] == []


# =============================================================================
# /detect endpoint tests
# =============================================================================


class TestDetectEndpoint:
    """Tests for the POST /detect endpoint."""

    async def test_detect_success(self, client, mock_triton):
        """Object detection returns labeled bounding boxes."""
        mock_triton.infer.return_value = _make_triton_json_output(
            {
                "bboxes": [[10, 20, 100, 200]],
                "labels": ["person"],
            }
        )

        response = await client.post(
            "/detect",
            json={"image": _make_b64_image()},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["detections"]) == 1
        assert data["detections"][0]["label"] == "person"

    async def test_detect_no_objects(self, client, mock_triton):
        """No objects returns empty detections."""
        mock_triton.infer.return_value = _make_triton_json_output({"bboxes": [], "labels": []})

        response = await client.post("/detect", json={"image": _make_b64_image()})

        assert response.status_code == 200
        assert response.json()["detections"] == []


# =============================================================================
# /dense-caption endpoint tests
# =============================================================================


class TestDenseCaptionEndpoint:
    """Tests for the POST /dense-caption endpoint."""

    async def test_dense_caption_success(self, client, mock_triton):
        """Dense caption returns captioned regions."""
        mock_triton.infer.return_value = _make_triton_json_output(
            {
                "bboxes": [[0, 0, 100, 100], [200, 200, 400, 400]],
                "labels": ["A person walking", "A car parked"],
            }
        )

        response = await client.post(
            "/dense-caption",
            json={"image": _make_b64_image()},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["regions"]) == 2
        assert data["regions"][0]["caption"] == "A person walking"


# =============================================================================
# /describe-region endpoint tests
# =============================================================================


class TestDescribeRegionEndpoint:
    """Tests for the POST /describe-region endpoint."""

    async def test_describe_region_success(self, client, mock_triton):
        """Describe-region returns description for each region."""
        mock_triton.infer.return_value = _make_triton_text_output("A man in a blue shirt")

        response = await client.post(
            "/describe-region",
            json={
                "image": _make_b64_image(),
                "regions": [{"x1": 10, "y1": 20, "x2": 100, "y2": 200}],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["descriptions"]) == 1
        assert data["descriptions"][0]["caption"] == "A man in a blue shirt"

    async def test_describe_multiple_regions(self, client, mock_triton):
        """Multiple regions each get a description."""
        mock_triton.infer.side_effect = [
            _make_triton_text_output("Person standing"),
            _make_triton_text_output("Car parked"),
        ]

        response = await client.post(
            "/describe-region",
            json={
                "image": _make_b64_image(),
                "regions": [
                    {"x1": 0, "y1": 0, "x2": 50, "y2": 50},
                    {"x1": 100, "y1": 100, "x2": 200, "y2": 200},
                ],
            },
        )

        assert response.status_code == 200
        assert len(response.json()["descriptions"]) == 2


# =============================================================================
# /phrase-grounding endpoint tests
# =============================================================================


class TestPhraseGroundingEndpoint:
    """Tests for the POST /phrase-grounding endpoint."""

    async def test_phrase_grounding_success(self, client, mock_triton):
        """Phrase grounding returns bounding boxes for phrases."""
        mock_triton.infer.return_value = _make_triton_json_output({"bboxes": [[10, 20, 100, 200]]})

        response = await client.post(
            "/phrase-grounding",
            json={"image": _make_b64_image(), "phrases": ["a person"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["grounded_phrases"]) == 1
        assert data["grounded_phrases"][0]["phrase"] == "a person"
        assert len(data["grounded_phrases"][0]["bboxes"]) == 1

    async def test_phrase_grounding_no_match(self, client, mock_triton):
        """Phrase with no bounding boxes returns empty bbox list."""
        mock_triton.infer.return_value = _make_triton_json_output({"bboxes": []})

        response = await client.post(
            "/phrase-grounding",
            json={"image": _make_b64_image(), "phrases": ["unicorn"]},
        )

        assert response.status_code == 200
        assert response.json()["grounded_phrases"][0]["bboxes"] == []


# =============================================================================
# /detect_security_objects endpoint tests
# =============================================================================


class TestDetectSecurityObjectsEndpoint:
    """Tests for the POST /detect_security_objects endpoint."""

    async def test_security_objects_success(self, client, mock_triton):
        """Security object detection returns labeled detections."""
        mock_triton.infer.return_value = _make_triton_json_output(
            {
                "bboxes": [[10, 20, 100, 200]],
                "bboxes_labels": ["person"],
            }
        )

        response = await client.post(
            "/detect_security_objects",
            json={"image": _make_b64_image()},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["detections"]) == 1
        assert data["detections"][0]["label"] == "person"
        assert data["objects_queried"] == SECURITY_OBJECTS

    async def test_security_objects_empty(self, client, mock_triton):
        """No security objects returns empty detections."""
        mock_triton.infer.return_value = _make_triton_json_output(
            {"bboxes": [], "bboxes_labels": []}
        )

        response = await client.post(
            "/detect_security_objects",
            json={"image": _make_b64_image()},
        )

        assert response.status_code == 200
        assert response.json()["detections"] == []


# =============================================================================
# /analyze-scene endpoint tests
# =============================================================================


class TestAnalyzeSceneEndpoint:
    """Tests for the POST /analyze-scene endpoint."""

    async def test_analyze_scene_success(self, client, mock_triton):
        """Scene analysis returns caption, regions, and text."""
        caption_output = _make_triton_text_output("A residential front yard")
        dense_output = _make_triton_json_output(
            {"bboxes": [[0, 0, 100, 100]], "labels": ["garden"]}
        )
        ocr_output = _make_triton_json_output(
            {"quad_boxes": [[10, 10, 50, 10, 50, 30, 10, 30]], "labels": ["123"]}
        )

        mock_triton.infer.side_effect = [
            caption_output,  # <MORE_DETAILED_CAPTION>
            dense_output,  # <DENSE_REGION_CAPTION>
            ocr_output,  # <OCR_WITH_REGION>
        ]

        response = await client.post(
            "/analyze-scene",
            json={"image": _make_b64_image()},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["caption"] == "A residential front yard"
        assert len(data["regions"]) == 1
        assert len(data["text_regions"]) == 1
        assert "task_times_ms" in data


# =============================================================================
# /health endpoint tests
# =============================================================================


class TestHealthEndpoint:
    """Tests for the GET /health endpoint."""

    async def test_health_model_ready(self, client, mock_triton):
        """Returns healthy when model is ready."""
        mock_triton.is_model_ready.return_value = True

        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["model_loaded"] is True

    async def test_health_model_not_ready(self, client, mock_triton):
        """Returns degraded when model is not ready."""
        mock_triton.is_model_ready.return_value = False

        response = await client.get("/health")

        data = response.json()
        assert data["status"] == "degraded"
        assert data["model_loaded"] is False
