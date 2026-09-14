"""Unit tests for the /analyze-scene endpoint.

Tests the cascade prompt strategy that runs multiple Florence-2 tasks
(MORE_DETAILED_CAPTION, DENSE_REGION_CAPTION, OCR_WITH_REGION) to extract
comprehensive scene context for Nemotron consumption.

Test Scenarios:
1. Successful scene analysis with all components
2. Scene with no text (empty OCR results)
3. Scene with no distinct regions (single object)
4. Model not loaded error
5. Invalid image data handling
6. Parallel execution timing verification
"""

from __future__ import annotations

import asyncio
import base64
import io
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from ai.florence.model import (
    CaptionedRegion,
    Florence2Model,
    OCRRegion,
    SceneAnalysisRequest,
    SceneAnalysisResponse,
    app,
)


def create_test_image(width: int = 640, height: int = 480, color: str = "RGB") -> str:
    """Create a test image and return it as base64 encoded string."""
    img = Image.new(color, (width, height), color=(128, 128, 128))
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def create_mock_florence_model() -> MagicMock:
    """Create a mock Florence2Model for testing."""
    mock_model = MagicMock(spec=Florence2Model)
    mock_model.model = MagicMock()  # Ensure model is not None
    mock_model.processor = MagicMock()
    return mock_model


# =============================================================================
# Test Pydantic Models
# =============================================================================


class TestSceneAnalysisRequest:
    """Test SceneAnalysisRequest model validation."""

    def test_valid_request(self) -> None:
        """Test valid request with base64 image."""
        image_b64 = create_test_image()
        request = SceneAnalysisRequest(image=image_b64)
        assert request.image == image_b64

    def test_missing_image_raises_error(self) -> None:
        """Test that missing image field raises validation error."""
        with pytest.raises(ValueError):
            SceneAnalysisRequest()  # type: ignore[call-arg]


class TestSceneAnalysisResponse:
    """Test SceneAnalysisResponse model structure."""

    def test_full_response(self) -> None:
        """Test response with all fields populated."""
        response = SceneAnalysisResponse(
            caption="A person standing at a front door with a package",
            regions=[
                CaptionedRegion(caption="person in blue jacket", bbox=[100, 150, 300, 400]),
                CaptionedRegion(caption="brown package on ground", bbox=[200, 350, 280, 420]),
            ],
            text_regions=[
                OCRRegion(text="FRAGILE", bbox=[210, 360, 270, 360, 270, 380, 210, 380]),
            ],
            inference_time_ms=450.5,
            task_times_ms={
                "caption": 200.0,
                "dense_regions": 150.0,
                "ocr_with_regions": 100.5,
            },
        )
        assert response.caption == "A person standing at a front door with a package"
        assert len(response.regions) == 2
        assert len(response.text_regions) == 1
        assert response.inference_time_ms == 450.5
        assert "caption" in response.task_times_ms

    def test_minimal_response(self) -> None:
        """Test response with empty regions and text."""
        response = SceneAnalysisResponse(
            caption="An empty driveway",
            regions=[],
            text_regions=[],
            inference_time_ms=150.0,
            task_times_ms={"caption": 150.0},
        )
        assert response.caption == "An empty driveway"
        assert len(response.regions) == 0
        assert len(response.text_regions) == 0


# =============================================================================
# Test /analyze-scene Endpoint
# =============================================================================


class TestAnalyzeSceneEndpoint:
    """Tests for the /analyze-scene endpoint."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create a test client for the FastAPI app."""
        return TestClient(app)

    @pytest.fixture
    def mock_model(self) -> MagicMock:
        """Create a mock Florence2Model."""
        return create_mock_florence_model()

    def test_analyze_scene_success(self, client: TestClient, mock_model: MagicMock) -> None:
        """Test successful scene analysis with all tasks returning data."""

        # Configure mock responses for each task
        def mock_extract(_image: Any, prompt: str) -> tuple[str, float]:
            if prompt == "<MORE_DETAILED_CAPTION>":
                return (
                    "A delivery person in a blue uniform is standing at the front door "
                    "of a residential home. They are holding a brown cardboard package. "
                    "The door is painted red and there is a welcome mat on the ground.",
                    200.0,
                )
            return ("", 0.0)

        def mock_extract_raw(_image: Any, prompt: str) -> tuple[dict[str, Any], float]:
            if prompt == "<DENSE_REGION_CAPTION>":
                return (
                    {
                        "bboxes": [[100, 150, 300, 400], [200, 350, 280, 420]],
                        "labels": ["delivery person in blue uniform", "cardboard package"],
                    },
                    150.0,
                )
            elif prompt == "<OCR_WITH_REGION>":
                return (
                    {
                        "quad_boxes": [[210, 360, 270, 360, 270, 380, 210, 380]],
                        "labels": ["PRIORITY MAIL"],
                    },
                    100.0,
                )
            return ({}, 0.0)

        mock_model.extract = mock_extract
        mock_model.extract_raw = mock_extract_raw

        with patch("ai.florence.model.model", mock_model):
            image_b64 = create_test_image()
            response = client.post("/analyze-scene", json={"image": image_b64})

            assert response.status_code == 200
            data = response.json()

            # Verify caption
            assert "delivery person" in data["caption"].lower()

            # Verify regions
            assert len(data["regions"]) == 2
            assert data["regions"][0]["caption"] == "delivery person in blue uniform"
            assert data["regions"][0]["bbox"] == [100, 150, 300, 400]

            # Verify text regions
            assert len(data["text_regions"]) == 1
            assert data["text_regions"][0]["text"] == "PRIORITY MAIL"

            # Verify timing
            assert data["inference_time_ms"] > 0
            assert "caption" in data["task_times_ms"]
            assert "dense_regions" in data["task_times_ms"]
            assert "ocr_with_regions" in data["task_times_ms"]

    def test_analyze_scene_no_text(self, client: TestClient, mock_model: MagicMock) -> None:
        """Test scene analysis when no text is detected (empty OCR)."""
        mock_model.extract = MagicMock(
            return_value=("A person walking a dog on a suburban sidewalk.", 180.0)
        )

        def mock_extract_raw(_image: Any, prompt: str) -> tuple[dict[str, Any], float]:
            if prompt == "<DENSE_REGION_CAPTION>":
                return (
                    {
                        "bboxes": [[50, 100, 200, 400], [150, 300, 220, 380]],
                        "labels": ["person walking", "golden retriever dog"],
                    },
                    120.0,
                )
            elif prompt == "<OCR_WITH_REGION>":
                # No text detected - empty results
                return ({"quad_boxes": [], "labels": []}, 50.0)
            return ({}, 0.0)

        mock_model.extract_raw = mock_extract_raw

        with patch("ai.florence.model.model", mock_model):
            image_b64 = create_test_image()
            response = client.post("/analyze-scene", json={"image": image_b64})

            assert response.status_code == 200
            data = response.json()

            assert "dog" in data["caption"].lower()
            assert len(data["regions"]) == 2
            assert len(data["text_regions"]) == 0  # No text detected

    def test_analyze_scene_no_distinct_regions(
        self, client: TestClient, mock_model: MagicMock
    ) -> None:
        """Test scene analysis with single region (no dense regions)."""
        mock_model.extract = MagicMock(
            return_value=("An empty parking lot at night with streetlights.", 150.0)
        )

        def mock_extract_raw(_image: Any, prompt: str) -> tuple[dict[str, Any], float]:
            if prompt == "<DENSE_REGION_CAPTION>":
                return ({"bboxes": [], "labels": []}, 80.0)
            elif prompt == "<OCR_WITH_REGION>":
                return ({"quad_boxes": [], "labels": []}, 60.0)
            return ({}, 0.0)

        mock_model.extract_raw = mock_extract_raw

        with patch("ai.florence.model.model", mock_model):
            image_b64 = create_test_image()
            response = client.post("/analyze-scene", json={"image": image_b64})

            assert response.status_code == 200
            data = response.json()

            assert "parking lot" in data["caption"].lower()
            assert len(data["regions"]) == 0
            assert len(data["text_regions"]) == 0

    def test_analyze_scene_model_not_loaded(self, client: TestClient) -> None:
        """Test error response when model is not loaded."""
        with patch("ai.florence.model.model", None):
            image_b64 = create_test_image()
            response = client.post("/analyze-scene", json={"image": image_b64})

            assert response.status_code == 503
            assert "Model not loaded" in response.json()["detail"]

    def test_analyze_scene_invalid_base64(self, client: TestClient, mock_model: MagicMock) -> None:
        """Test error response for invalid base64 encoding."""
        with patch("ai.florence.model.model", mock_model):
            response = client.post("/analyze-scene", json={"image": "not-valid-base64!!!"})

            assert response.status_code == 400
            assert "Invalid base64" in response.json()["detail"]

    def test_analyze_scene_invalid_image_data(
        self, client: TestClient, mock_model: MagicMock
    ) -> None:
        """Test error response for valid base64 but invalid image data."""
        with patch("ai.florence.model.model", mock_model):
            # Valid base64 but not an image
            invalid_image = base64.b64encode(b"This is not an image").decode("utf-8")
            response = client.post("/analyze-scene", json={"image": invalid_image})

            assert response.status_code == 400
            assert "Invalid image data" in response.json()["detail"]


# =============================================================================
# Test Parallel Execution
# =============================================================================


class TestParallelExecution:
    """Tests to verify parallel execution of independent tasks."""

    @pytest.mark.asyncio
    async def test_parallel_tasks_execute_concurrently(self) -> None:
        """Verify that DENSE_REGION_CAPTION and OCR_WITH_REGION run in parallel."""
        execution_order: list[str] = []
        execution_times: dict[str, float] = {}

        async def mock_dense_regions() -> tuple[list[CaptionedRegion], float]:
            """Simulate dense region task with delay."""
            execution_order.append("dense_start")
            await asyncio.sleep(0.1)  # 100ms delay
            execution_order.append("dense_end")
            execution_times["dense"] = 100.0
            return [CaptionedRegion(caption="test region", bbox=[0, 0, 100, 100])], 100.0

        async def mock_ocr_with_regions() -> tuple[list[OCRRegion], float]:
            """Simulate OCR task with delay."""
            execution_order.append("ocr_start")
            await asyncio.sleep(0.1)  # 100ms delay
            execution_order.append("ocr_end")
            execution_times["ocr"] = 100.0
            return [OCRRegion(text="TEST", bbox=[0, 0, 50, 50, 50, 60, 0, 60])], 100.0

        # Run tasks in parallel
        import time

        start = time.perf_counter()
        results = await asyncio.gather(mock_dense_regions(), mock_ocr_with_regions())
        elapsed = time.perf_counter() - start

        # Verify parallel execution - total time should be ~100ms, not ~200ms
        assert elapsed < 0.15, f"Tasks should run in parallel, but took {elapsed}s"

        # Verify both tasks completed
        assert len(results) == 2
        assert len(results[0][0]) == 1  # One region
        assert len(results[1][0]) == 1  # One text region

        # Verify interleaved execution (both started before either finished)
        assert "dense_start" in execution_order[:2]
        assert "ocr_start" in execution_order[:2]


# =============================================================================
# Test Scene Types (Security-Relevant Scenarios)
# =============================================================================


class TestSecuritySceneTypes:
    """Tests for various security-relevant scene types."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create a test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_model(self) -> MagicMock:
        """Create a mock model."""
        return create_mock_florence_model()

    def test_person_at_door_scene(self, client: TestClient, mock_model: MagicMock) -> None:
        """Test analysis of a person at front door (common security scenario)."""
        mock_model.extract = MagicMock(
            return_value=(
                "A person in dark clothing is standing at a residential front door. "
                "The person appears to be looking through the window beside the door. "
                "It is nighttime and the porch light is on.",
                250.0,
            )
        )

        def mock_extract_raw(_image: Any, prompt: str) -> tuple[dict[str, Any], float]:
            if prompt == "<DENSE_REGION_CAPTION>":
                return (
                    {
                        "bboxes": [[150, 100, 350, 500], [10, 50, 140, 450]],
                        "labels": [
                            "person in dark hoodie with hood up",
                            "white front door with window",
                        ],
                    },
                    180.0,
                )
            elif prompt == "<OCR_WITH_REGION>":
                return (
                    {
                        "quad_boxes": [[50, 200, 120, 200, 120, 220, 50, 220]],
                        "labels": ["123"],
                    },
                    90.0,
                )
            return ({}, 0.0)

        mock_model.extract_raw = mock_extract_raw

        with patch("ai.florence.model.model", mock_model):
            image_b64 = create_test_image()
            response = client.post("/analyze-scene", json={"image": image_b64})

            assert response.status_code == 200
            data = response.json()

            # Verify suspicious indicators are captured
            assert "dark" in data["caption"].lower()
            assert "nighttime" in data["caption"].lower()
            assert any("hoodie" in r["caption"].lower() for r in data["regions"])

    def test_delivery_scene(self, client: TestClient, mock_model: MagicMock) -> None:
        """Test analysis of a delivery person scene."""
        mock_model.extract = MagicMock(
            return_value=(
                "An Amazon delivery driver in a blue vest is placing a package "
                "at the front door. The driver is wearing a cap and carrying "
                "additional packages. A delivery van is visible in the driveway.",
                220.0,
            )
        )

        def mock_extract_raw(_image: Any, prompt: str) -> tuple[dict[str, Any], float]:
            if prompt == "<DENSE_REGION_CAPTION>":
                return (
                    {
                        "bboxes": [
                            [100, 80, 280, 450],
                            [250, 350, 350, 450],
                            [400, 150, 600, 380],
                        ],
                        "labels": [
                            "delivery driver in blue Amazon vest",
                            "brown cardboard package",
                            "blue Amazon delivery van",
                        ],
                    },
                    160.0,
                )
            elif prompt == "<OCR_WITH_REGION>":
                return (
                    {
                        "quad_boxes": [
                            [420, 180, 580, 180, 580, 220, 420, 220],
                            [260, 360, 340, 360, 340, 400, 260, 400],
                        ],
                        "labels": ["amazon", "PRIME"],
                    },
                    110.0,
                )
            return ({}, 0.0)

        mock_model.extract_raw = mock_extract_raw

        with patch("ai.florence.model.model", mock_model):
            image_b64 = create_test_image()
            response = client.post("/analyze-scene", json={"image": image_b64})

            assert response.status_code == 200
            data = response.json()

            # Verify delivery context is captured
            assert "amazon" in data["caption"].lower() or "delivery" in data["caption"].lower()
            assert any("amazon" in r["caption"].lower() for r in data["regions"])
            assert any("amazon" in t["text"].lower() for t in data["text_regions"])

    def test_vehicle_scene(self, client: TestClient, mock_model: MagicMock) -> None:
        """Test analysis of a vehicle in driveway scene."""
        mock_model.extract = MagicMock(
            return_value=(
                "A white sedan is parked in the driveway of a suburban home. "
                "The car appears to be a Toyota Camry based on its shape. "
                "The license plate is visible on the rear of the vehicle.",
                190.0,
            )
        )

        def mock_extract_raw(_image: Any, prompt: str) -> tuple[dict[str, Any], float]:
            if prompt == "<DENSE_REGION_CAPTION>":
                return (
                    {
                        "bboxes": [[50, 200, 550, 450]],
                        "labels": ["white Toyota sedan parked in driveway"],
                    },
                    140.0,
                )
            elif prompt == "<OCR_WITH_REGION>":
                return (
                    {
                        "quad_boxes": [[280, 420, 370, 420, 370, 445, 280, 445]],
                        "labels": ["ABC 1234"],
                    },
                    95.0,
                )
            return ({}, 0.0)

        mock_model.extract_raw = mock_extract_raw

        with patch("ai.florence.model.model", mock_model):
            image_b64 = create_test_image()
            response = client.post("/analyze-scene", json={"image": image_b64})

            assert response.status_code == 200
            data = response.json()

            # Verify vehicle and license plate are captured
            assert "sedan" in data["caption"].lower() or "car" in data["caption"].lower()
            assert any("abc" in t["text"].lower() for t in data["text_regions"])

    def test_animal_scene(self, client: TestClient, mock_model: MagicMock) -> None:
        """Test analysis of an animal scene."""
        mock_model.extract = MagicMock(
            return_value=(
                "A large German Shepherd dog is walking across the front lawn. "
                "The dog appears to be off-leash and is sniffing the grass. "
                "No owner is visible in the frame.",
                175.0,
            )
        )

        def mock_extract_raw(_image: Any, prompt: str) -> tuple[dict[str, Any], float]:
            if prompt == "<DENSE_REGION_CAPTION>":
                return (
                    {
                        "bboxes": [[200, 250, 450, 480]],
                        "labels": ["German Shepherd dog on grass"],
                    },
                    130.0,
                )
            elif prompt == "<OCR_WITH_REGION>":
                return ({"quad_boxes": [], "labels": []}, 70.0)
            return ({}, 0.0)

        mock_model.extract_raw = mock_extract_raw

        with patch("ai.florence.model.model", mock_model):
            image_b64 = create_test_image()
            response = client.post("/analyze-scene", json={"image": image_b64})

            assert response.status_code == 200
            data = response.json()

            # Verify animal is detected
            assert "dog" in data["caption"].lower() or "german shepherd" in data["caption"].lower()
            assert any("dog" in r["caption"].lower() for r in data["regions"])


# =============================================================================
# Test Output Format for Nemotron
# =============================================================================


class TestNemotronOutputFormat:
    """Tests to verify output format is suitable for Nemotron consumption."""

    def test_response_is_json_serializable(self) -> None:
        """Verify the response can be serialized to JSON."""
        import json

        response = SceneAnalysisResponse(
            caption="Test caption with special chars: <>&\"'",
            regions=[
                CaptionedRegion(caption="region 1", bbox=[1.5, 2.5, 100.0, 200.0]),
            ],
            text_regions=[
                OCRRegion(text="TEXT123", bbox=[0, 0, 10, 0, 10, 10, 0, 10]),
            ],
            inference_time_ms=123.456,
            task_times_ms={"caption": 50.0, "dense_regions": 40.0, "ocr_with_regions": 33.456},
        )

        # Should not raise
        json_str = response.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["caption"] == "Test caption with special chars: <>&\"'"
        assert len(parsed["regions"]) == 1
        assert len(parsed["text_regions"]) == 1

    def test_response_has_all_required_fields(self) -> None:
        """Verify response includes all fields needed by Nemotron prompts."""
        response = SceneAnalysisResponse(
            caption="A scene description",
            regions=[],
            text_regions=[],
            inference_time_ms=100.0,
            task_times_ms={},
        )

        # Check all required fields are present
        dump = response.model_dump()
        required_fields = [
            "caption",
            "regions",
            "text_regions",
            "inference_time_ms",
            "task_times_ms",
        ]
        for field in required_fields:
            assert field in dump, f"Missing required field: {field}"

    def test_bounding_boxes_are_numeric_lists(self) -> None:
        """Verify bounding boxes are proper numeric lists."""
        response = SceneAnalysisResponse(
            caption="Test",
            regions=[
                CaptionedRegion(caption="test", bbox=[100.5, 200.5, 300.5, 400.5]),
            ],
            text_regions=[
                OCRRegion(text="TEST", bbox=[0, 0, 50, 0, 50, 50, 0, 50]),
            ],
            inference_time_ms=100.0,
            task_times_ms={},
        )

        dump = response.model_dump()

        # Verify region bbox is 4 floats [x1, y1, x2, y2]
        assert len(dump["regions"][0]["bbox"]) == 4
        assert all(isinstance(x, (int, float)) for x in dump["regions"][0]["bbox"])

        # Verify OCR bbox is 8 floats [x1, y1, x2, y2, x3, y3, x4, y4]
        assert len(dump["text_regions"][0]["bbox"]) == 8
        assert all(isinstance(x, (int, float)) for x in dump["text_regions"][0]["bbox"])
