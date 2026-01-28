"""Unit tests for Florence-2 region description and phrase grounding endpoints.

Tests cover:
- Region description endpoint (NEM-3911): Describe what's in a specific bounding box
- Phrase grounding endpoint (NEM-3911): Find objects matching a text description
- Pydantic model validation for request/response schemas
- Error handling for invalid inputs
- Metrics tracking

Test Scenarios:
1. Region description with valid bounding box
2. Region description with multiple regions (batch)
3. Phrase grounding with single phrase
4. Phrase grounding with multiple phrases
5. Model not loaded error handling
6. Invalid image data handling
7. Invalid bounding box coordinates
"""

from __future__ import annotations

import base64
import io
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from ai.florence.model import (
    BoundingBox,
    CaptionedRegion,
    Florence2Model,
    GroundedPhrase,
    PhraseGroundingRequest,
    PhraseGroundingResponse,
    RegionDescriptionRequest,
    RegionDescriptionResponse,
    app,
)


def create_test_image(width: int = 640, height: int = 480) -> str:
    """Create a test image and return it as base64 encoded string."""
    img = Image.new("RGB", (width, height), color=(128, 128, 128))
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


class TestBoundingBoxModel:
    """Test BoundingBox model validation."""

    def test_valid_bounding_box(self) -> None:
        """Test valid bounding box with x1, y1, x2, y2 coordinates."""
        bbox = BoundingBox(x1=100, y1=150, x2=300, y2=400)
        assert bbox.x1 == 100
        assert bbox.y1 == 150
        assert bbox.x2 == 300
        assert bbox.y2 == 400

    def test_bounding_box_as_list(self) -> None:
        """Test that bounding box can be converted to list format."""
        bbox = BoundingBox(x1=10, y1=20, x2=100, y2=200)
        assert bbox.as_list() == [10, 20, 100, 200]

    def test_bounding_box_from_list(self) -> None:
        """Test creating bounding box from list."""
        bbox = BoundingBox.from_list([50, 75, 150, 250])
        assert bbox.x1 == 50
        assert bbox.y1 == 75
        assert bbox.x2 == 150
        assert bbox.y2 == 250

    def test_bounding_box_negative_coordinates(self) -> None:
        """Test that bounding box rejects negative coordinates."""
        with pytest.raises(ValueError):
            BoundingBox(x1=-10, y1=0, x2=100, y2=100)

    def test_bounding_box_invalid_range(self) -> None:
        """Test that bounding box validates x1 < x2 and y1 < y2."""
        with pytest.raises(ValueError):
            BoundingBox(x1=200, y1=100, x2=100, y2=200)  # x1 > x2


class TestRegionDescriptionRequest:
    """Test RegionDescriptionRequest model validation."""

    def test_valid_single_region_request(self) -> None:
        """Test valid request with single region."""
        image_b64 = create_test_image()
        request = RegionDescriptionRequest(
            image=image_b64, regions=[BoundingBox(x1=100, y1=150, x2=300, y2=400)]
        )
        assert len(request.regions) == 1

    def test_valid_multi_region_request(self) -> None:
        """Test valid request with multiple regions."""
        image_b64 = create_test_image()
        request = RegionDescriptionRequest(
            image=image_b64,
            regions=[
                BoundingBox(x1=0, y1=0, x2=100, y2=100),
                BoundingBox(x1=200, y1=200, x2=400, y2=400),
            ],
        )
        assert len(request.regions) == 2

    def test_empty_regions_not_allowed(self) -> None:
        """Test that empty regions list is not allowed."""
        image_b64 = create_test_image()
        with pytest.raises(ValueError):
            RegionDescriptionRequest(image=image_b64, regions=[])

    def test_missing_image_raises_error(self) -> None:
        """Test that missing image field raises validation error."""
        with pytest.raises(ValueError):
            RegionDescriptionRequest(regions=[BoundingBox(x1=0, y1=0, x2=100, y2=100)])  # type: ignore[call-arg]


class TestRegionDescriptionResponse:
    """Test RegionDescriptionResponse model structure."""

    def test_full_response(self) -> None:
        """Test response with all fields populated."""
        response = RegionDescriptionResponse(
            descriptions=[
                CaptionedRegion(caption="a person in blue jacket", bbox=[100, 150, 300, 400]),
                CaptionedRegion(caption="a brown package on ground", bbox=[200, 350, 280, 420]),
            ],
            inference_time_ms=350.5,
        )
        assert len(response.descriptions) == 2
        assert response.descriptions[0].caption == "a person in blue jacket"
        assert response.inference_time_ms == 350.5

    def test_single_description_response(self) -> None:
        """Test response with single region description."""
        response = RegionDescriptionResponse(
            descriptions=[CaptionedRegion(caption="a red car", bbox=[0, 0, 640, 480])],
            inference_time_ms=150.0,
        )
        assert len(response.descriptions) == 1
        assert response.descriptions[0].caption == "a red car"


class TestPhraseGroundingRequest:
    """Test PhraseGroundingRequest model validation."""

    def test_valid_single_phrase_request(self) -> None:
        """Test valid request with single phrase."""
        image_b64 = create_test_image()
        request = PhraseGroundingRequest(image=image_b64, phrases=["a person in blue jacket"])
        assert len(request.phrases) == 1
        assert request.phrases[0] == "a person in blue jacket"

    def test_valid_multi_phrase_request(self) -> None:
        """Test valid request with multiple phrases."""
        image_b64 = create_test_image()
        request = PhraseGroundingRequest(
            image=image_b64, phrases=["person", "car", "package", "dog"]
        )
        assert len(request.phrases) == 4

    def test_empty_phrases_not_allowed(self) -> None:
        """Test that empty phrases list is not allowed."""
        image_b64 = create_test_image()
        with pytest.raises(ValueError):
            PhraseGroundingRequest(image=image_b64, phrases=[])

    def test_empty_string_phrase_not_allowed(self) -> None:
        """Test that empty string phrases are not allowed."""
        image_b64 = create_test_image()
        with pytest.raises(ValueError):
            PhraseGroundingRequest(image=image_b64, phrases=["valid phrase", ""])


class TestGroundedPhrase:
    """Test GroundedPhrase model structure."""

    def test_grounded_phrase_with_single_bbox(self) -> None:
        """Test grounded phrase with single bounding box."""
        grounded = GroundedPhrase(
            phrase="person", bboxes=[[100, 150, 300, 400]], confidence_scores=[0.95]
        )
        assert grounded.phrase == "person"
        assert len(grounded.bboxes) == 1
        assert grounded.confidence_scores[0] == 0.95

    def test_grounded_phrase_with_multiple_bboxes(self) -> None:
        """Test grounded phrase with multiple bounding boxes (same phrase, multiple instances)."""
        grounded = GroundedPhrase(
            phrase="car",
            bboxes=[[0, 0, 100, 100], [200, 200, 400, 400]],
            confidence_scores=[0.9, 0.85],
        )
        assert len(grounded.bboxes) == 2
        assert len(grounded.confidence_scores) == 2

    def test_grounded_phrase_no_matches(self) -> None:
        """Test grounded phrase with no matches (empty bboxes)."""
        grounded = GroundedPhrase(phrase="elephant", bboxes=[], confidence_scores=[])
        assert len(grounded.bboxes) == 0


class TestPhraseGroundingResponse:
    """Test PhraseGroundingResponse model structure."""

    def test_full_response(self) -> None:
        """Test response with all fields populated."""
        response = PhraseGroundingResponse(
            grounded_phrases=[
                GroundedPhrase(
                    phrase="person", bboxes=[[100, 150, 300, 400]], confidence_scores=[0.95]
                ),
                GroundedPhrase(
                    phrase="car", bboxes=[[400, 200, 600, 400]], confidence_scores=[0.88]
                ),
            ],
            inference_time_ms=280.5,
        )
        assert len(response.grounded_phrases) == 2
        assert response.inference_time_ms == 280.5

    def test_response_with_unmatched_phrases(self) -> None:
        """Test response where some phrases have no matches."""
        response = PhraseGroundingResponse(
            grounded_phrases=[
                GroundedPhrase(
                    phrase="person", bboxes=[[100, 150, 300, 400]], confidence_scores=[0.95]
                ),
                GroundedPhrase(phrase="elephant", bboxes=[], confidence_scores=[]),  # No match
            ],
            inference_time_ms=200.0,
        )
        assert len(response.grounded_phrases) == 2
        assert len(response.grounded_phrases[1].bboxes) == 0


# =============================================================================
# Test /describe-region Endpoint
# =============================================================================


class TestDescribeRegionEndpoint:
    """Tests for the /describe-region endpoint."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create a test client for the FastAPI app."""
        return TestClient(app)

    @pytest.fixture
    def mock_model(self) -> MagicMock:
        """Create a mock Florence2Model."""
        return create_mock_florence_model()

    def test_describe_region_single_region(self, client: TestClient, mock_model: MagicMock) -> None:
        """Test describing a single region in the image."""

        def mock_extract_raw(_image: Any, prompt: str) -> tuple[Any, float]:
            # Florence-2 returns a string description for REGION_TO_DESCRIPTION
            return "a person wearing a blue jacket and holding a package", 150.0

        mock_model.extract_raw = mock_extract_raw

        with patch("ai.florence.model.model", mock_model):
            image_b64 = create_test_image()
            response = client.post(
                "/describe-region",
                json={
                    "image": image_b64,
                    "regions": [{"x1": 100, "y1": 150, "x2": 300, "y2": 400}],
                },
            )

            assert response.status_code == 200
            data = response.json()

            assert "descriptions" in data
            assert "inference_time_ms" in data
            assert len(data["descriptions"]) == 1
            assert "person" in data["descriptions"][0]["caption"].lower()

    def test_describe_region_multiple_regions(
        self, client: TestClient, mock_model: MagicMock
    ) -> None:
        """Test describing multiple regions in the image."""
        call_count = 0

        def mock_extract_raw(_image: Any, prompt: str) -> tuple[Any, float]:
            nonlocal call_count
            call_count += 1
            descriptions = [
                "a delivery driver in blue uniform",
                "a brown cardboard package",
                "a white front door",
            ]
            idx = (call_count - 1) % len(descriptions)
            return descriptions[idx], 100.0

        mock_model.extract_raw = mock_extract_raw

        with patch("ai.florence.model.model", mock_model):
            image_b64 = create_test_image()
            response = client.post(
                "/describe-region",
                json={
                    "image": image_b64,
                    "regions": [
                        {"x1": 100, "y1": 80, "x2": 280, "y2": 450},
                        {"x1": 250, "y1": 350, "x2": 350, "y2": 450},
                        {"x1": 10, "y1": 50, "x2": 140, "y2": 450},
                    ],
                },
            )

            assert response.status_code == 200
            data = response.json()

            assert len(data["descriptions"]) == 3
            # Verify bounding boxes are preserved in the response
            assert data["descriptions"][0]["bbox"] == [100, 80, 280, 450]
            assert data["descriptions"][1]["bbox"] == [250, 350, 350, 450]

    def test_describe_region_model_not_loaded(self, client: TestClient) -> None:
        """Test error response when model is not loaded."""
        with patch("ai.florence.model.model", None):
            image_b64 = create_test_image()
            response = client.post(
                "/describe-region",
                json={
                    "image": image_b64,
                    "regions": [{"x1": 0, "y1": 0, "x2": 100, "y2": 100}],
                },
            )

            assert response.status_code == 503
            assert "Model not loaded" in response.json()["detail"]

    def test_describe_region_invalid_base64(
        self, client: TestClient, mock_model: MagicMock
    ) -> None:
        """Test error response for invalid base64 encoding."""
        with patch("ai.florence.model.model", mock_model):
            response = client.post(
                "/describe-region",
                json={
                    "image": "not-valid-base64!!!",
                    "regions": [{"x1": 0, "y1": 0, "x2": 100, "y2": 100}],
                },
            )

            assert response.status_code == 400
            assert "Invalid base64" in response.json()["detail"]

    def test_describe_region_invalid_bbox_coordinates(
        self, client: TestClient, mock_model: MagicMock
    ) -> None:
        """Test error response for invalid bounding box coordinates."""
        with patch("ai.florence.model.model", mock_model):
            image_b64 = create_test_image()
            # x1 > x2 is invalid
            response = client.post(
                "/describe-region",
                json={
                    "image": image_b64,
                    "regions": [{"x1": 300, "y1": 0, "x2": 100, "y2": 100}],
                },
            )

            assert response.status_code == 422  # Pydantic validation error


# =============================================================================
# Test /phrase-grounding Endpoint
# =============================================================================


class TestPhraseGroundingEndpoint:
    """Tests for the /phrase-grounding endpoint."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create a test client for the FastAPI app."""
        return TestClient(app)

    @pytest.fixture
    def mock_model(self) -> MagicMock:
        """Create a mock Florence2Model."""
        return create_mock_florence_model()

    def test_phrase_grounding_single_phrase(
        self, client: TestClient, mock_model: MagicMock
    ) -> None:
        """Test phrase grounding with single phrase that matches."""

        def mock_extract_raw(_image: Any, prompt: str) -> tuple[dict[str, Any], float]:
            # Florence-2 returns bboxes and labels for phrase grounding
            return {
                "bboxes": [[150, 100, 350, 450]],
                "labels": ["person in blue jacket"],
            }, 180.0

        mock_model.extract_raw = mock_extract_raw

        with patch("ai.florence.model.model", mock_model):
            image_b64 = create_test_image()
            response = client.post(
                "/phrase-grounding",
                json={"image": image_b64, "phrases": ["person in blue jacket"]},
            )

            assert response.status_code == 200
            data = response.json()

            assert "grounded_phrases" in data
            assert "inference_time_ms" in data
            assert len(data["grounded_phrases"]) == 1
            assert data["grounded_phrases"][0]["phrase"] == "person in blue jacket"
            assert len(data["grounded_phrases"][0]["bboxes"]) == 1

    def test_phrase_grounding_multiple_phrases(
        self, client: TestClient, mock_model: MagicMock
    ) -> None:
        """Test phrase grounding with multiple phrases."""
        call_count = 0

        def mock_extract_raw(_image: Any, prompt: str) -> tuple[dict[str, Any], float]:
            nonlocal call_count
            call_count += 1

            # Return different results for each phrase
            results = [
                {"bboxes": [[100, 80, 280, 450]], "labels": ["delivery driver"]},
                {"bboxes": [[250, 350, 350, 450]], "labels": ["package"]},
                {"bboxes": [], "labels": []},  # No match for "elephant"
            ]
            idx = (call_count - 1) % len(results)
            return results[idx], 120.0

        mock_model.extract_raw = mock_extract_raw

        with patch("ai.florence.model.model", mock_model):
            image_b64 = create_test_image()
            response = client.post(
                "/phrase-grounding",
                json={
                    "image": image_b64,
                    "phrases": ["delivery driver", "package", "elephant"],
                },
            )

            assert response.status_code == 200
            data = response.json()

            assert len(data["grounded_phrases"]) == 3
            # First phrase has a match
            assert len(data["grounded_phrases"][0]["bboxes"]) == 1
            # Second phrase has a match
            assert len(data["grounded_phrases"][1]["bboxes"]) == 1
            # Third phrase has no match
            assert len(data["grounded_phrases"][2]["bboxes"]) == 0

    def test_phrase_grounding_multiple_instances(
        self, client: TestClient, mock_model: MagicMock
    ) -> None:
        """Test phrase grounding when same object appears multiple times."""

        def mock_extract_raw(_image: Any, prompt: str) -> tuple[dict[str, Any], float]:
            # Multiple people in the scene
            return {
                "bboxes": [[50, 100, 200, 400], [300, 150, 450, 420], [500, 80, 600, 380]],
                "labels": ["person", "person", "person"],
            }, 200.0

        mock_model.extract_raw = mock_extract_raw

        with patch("ai.florence.model.model", mock_model):
            image_b64 = create_test_image()
            response = client.post(
                "/phrase-grounding",
                json={"image": image_b64, "phrases": ["person"]},
            )

            assert response.status_code == 200
            data = response.json()

            assert len(data["grounded_phrases"]) == 1
            assert data["grounded_phrases"][0]["phrase"] == "person"
            assert len(data["grounded_phrases"][0]["bboxes"]) == 3

    def test_phrase_grounding_model_not_loaded(self, client: TestClient) -> None:
        """Test error response when model is not loaded."""
        with patch("ai.florence.model.model", None):
            image_b64 = create_test_image()
            response = client.post(
                "/phrase-grounding",
                json={"image": image_b64, "phrases": ["person"]},
            )

            assert response.status_code == 503
            assert "Model not loaded" in response.json()["detail"]

    def test_phrase_grounding_invalid_base64(
        self, client: TestClient, mock_model: MagicMock
    ) -> None:
        """Test error response for invalid base64 encoding."""
        with patch("ai.florence.model.model", mock_model):
            response = client.post(
                "/phrase-grounding",
                json={"image": "not-valid-base64!!!", "phrases": ["person"]},
            )

            assert response.status_code == 400
            assert "Invalid base64" in response.json()["detail"]

    def test_phrase_grounding_empty_phrases(
        self, client: TestClient, mock_model: MagicMock
    ) -> None:
        """Test error response for empty phrases list."""
        with patch("ai.florence.model.model", mock_model):
            image_b64 = create_test_image()
            response = client.post(
                "/phrase-grounding",
                json={"image": image_b64, "phrases": []},
            )

            assert response.status_code == 422  # Pydantic validation error


# =============================================================================
# Test Metrics Tracking
# =============================================================================


class TestEndpointMetrics:
    """Tests for metrics tracking on region endpoints."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create a test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_model(self) -> MagicMock:
        """Create a mock model."""
        mock = create_mock_florence_model()
        mock.extract_raw = MagicMock(return_value=("test description", 100.0))
        return mock

    def test_describe_region_returns_inference_time(
        self, client: TestClient, mock_model: MagicMock
    ) -> None:
        """Test that describe-region endpoint returns inference time."""
        with patch("ai.florence.model.model", mock_model):
            image_b64 = create_test_image()
            response = client.post(
                "/describe-region",
                json={
                    "image": image_b64,
                    "regions": [{"x1": 0, "y1": 0, "x2": 100, "y2": 100}],
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert "inference_time_ms" in data
            assert data["inference_time_ms"] > 0

    def test_phrase_grounding_returns_inference_time(
        self, client: TestClient, mock_model: MagicMock
    ) -> None:
        """Test that phrase-grounding endpoint returns inference time."""
        mock_model.extract_raw = MagicMock(return_value=({"bboxes": [], "labels": []}, 150.0))

        with patch("ai.florence.model.model", mock_model):
            image_b64 = create_test_image()
            response = client.post(
                "/phrase-grounding",
                json={"image": image_b64, "phrases": ["person"]},
            )

            assert response.status_code == 200
            data = response.json()
            assert "inference_time_ms" in data
            assert data["inference_time_ms"] > 0


# =============================================================================
# Test Security-Relevant Scenarios
# =============================================================================


class TestSecurityScenarios:
    """Tests for security-relevant use cases of region endpoints."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create a test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_model(self) -> MagicMock:
        """Create a mock model."""
        return create_mock_florence_model()

    def test_describe_person_at_door(self, client: TestClient, mock_model: MagicMock) -> None:
        """Test describing a person detected at front door."""
        mock_model.extract_raw = MagicMock(
            return_value=(
                "a person wearing a dark hoodie with the hood up, facing away from camera",
                200.0,
            )
        )

        with patch("ai.florence.model.model", mock_model):
            image_b64 = create_test_image()
            response = client.post(
                "/describe-region",
                json={
                    "image": image_b64,
                    "regions": [{"x1": 150, "y1": 100, "x2": 350, "y2": 500}],
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert "hoodie" in data["descriptions"][0]["caption"].lower()

    def test_ground_suspicious_items(self, client: TestClient, mock_model: MagicMock) -> None:
        """Test grounding security-relevant phrases."""
        call_count = 0

        def mock_extract_raw(_image: Any, prompt: str) -> tuple[dict[str, Any], float]:
            nonlocal call_count
            call_count += 1

            # Simulate finding a person and package but no weapon
            results = [
                {"bboxes": [[100, 80, 280, 450]], "labels": ["person"]},
                {"bboxes": [[250, 380, 350, 450]], "labels": ["package"]},
                {"bboxes": [], "labels": []},  # No weapon found
            ]
            idx = (call_count - 1) % len(results)
            return results[idx], 100.0

        mock_model.extract_raw = mock_extract_raw

        with patch("ai.florence.model.model", mock_model):
            image_b64 = create_test_image()
            response = client.post(
                "/phrase-grounding",
                json={
                    "image": image_b64,
                    "phrases": ["person", "package", "weapon"],
                },
            )

            assert response.status_code == 200
            data = response.json()

            # Person and package found
            person_result = next(
                (g for g in data["grounded_phrases"] if g["phrase"] == "person"), None
            )
            package_result = next(
                (g for g in data["grounded_phrases"] if g["phrase"] == "package"), None
            )
            weapon_result = next(
                (g for g in data["grounded_phrases"] if g["phrase"] == "weapon"), None
            )

            assert person_result is not None and len(person_result["bboxes"]) > 0
            assert package_result is not None and len(package_result["bboxes"]) > 0
            assert weapon_result is not None and len(weapon_result["bboxes"]) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
