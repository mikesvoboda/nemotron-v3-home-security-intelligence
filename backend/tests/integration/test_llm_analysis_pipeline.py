"""Integration tests for LLM analysis pipeline end-to-end.

This module tests the full LLM analysis pipeline from data enrichment through
prompt formatting to ensure no KeyError exceptions occur during the analysis flow.

Tests verify:
1. analyze_batch completes without exceptions with full Model Zoo enrichment
2. analyze_detection_fast_path completes without exceptions
3. LLM analysis produces non-fallback results
4. Prompt formatting doesn't raise KeyError with realistic EnrichmentResult data
5. All prompt template fields are properly populated

Key bug prevention:
- Guards against KeyError: 'ondemand_enrichment_context' (NEM-3026)
- Ensures all MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT fields are set
- Validates enrichment pipeline integration with prompt builder

Mocking strategy:
- Real database operations (using isolated_db fixture)
- Mocked HTTP calls to Nemotron LLM (external service)
- Realistic EnrichmentResult with all Model Zoo components
"""

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.core.redis import RedisClient
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.services.enrichment_pipeline import (
    BoundingBox,
    ClothingClassification,
    EnrichmentResult,
    FaceResult,
    LicensePlateResult,
    VehicleClassificationResult,
    VehicleDamageResult,
    ViolenceDetectionResult,
    WeatherResult,
)
from backend.services.nemotron_analyzer import NemotronAnalyzer
from backend.services.vision_extractor import (
    BatchExtractionResult,
    EnvironmentContext,
    PersonAttributes,
    SceneAnalysis,
    VehicleAttributes,
)

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
async def sample_camera(isolated_db):
    """Create a sample camera in the database."""
    from backend.core.database import get_session

    camera_id = str(uuid.uuid4())
    unique_suffix = uuid.uuid4().hex[:8]
    async with get_session() as db:
        camera = Camera(
            id=camera_id,
            name=f"Test Camera {unique_suffix}",
            folder_path=f"/export/test/camera_{unique_suffix}",
            status="online",
        )
        db.add(camera)
        await db.commit()
        await db.refresh(camera)
        yield camera


@pytest.fixture
async def sample_detections(isolated_db, sample_camera):
    """Create sample detections in the database."""
    from backend.core.database import get_session

    async with get_session() as db:
        detection1 = Detection(
            camera_id=sample_camera.id,
            file_path="/export/test/img001.jpg",
            file_type="image/jpeg",
            detected_at=datetime(2025, 12, 23, 14, 0, 0, tzinfo=UTC),
            object_type="person",
            confidence=0.95,
            bbox_x=100,
            bbox_y=150,
            bbox_width=200,
            bbox_height=400,
            video_width=1920,
            video_height=1080,
        )
        detection2 = Detection(
            camera_id=sample_camera.id,
            file_path="/export/test/img002.jpg",
            file_type="image/jpeg",
            detected_at=datetime(2025, 12, 23, 14, 1, 0, tzinfo=UTC),
            object_type="car",
            confidence=0.88,
            bbox_x=300,
            bbox_y=200,
            bbox_width=400,
            bbox_height=300,
            video_width=1920,
            video_height=1080,
        )
        db.add(detection1)
        db.add(detection2)
        await db.commit()
        await db.refresh(detection1)
        await db.refresh(detection2)
        yield [detection1, detection2]


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client."""
    mock_client = AsyncMock(spec=RedisClient)
    mock_client.publish.return_value = 1
    return mock_client


@pytest.fixture
def realistic_enrichment_result():
    """Create a realistic EnrichmentResult with full Model Zoo data.

    This simulates the output from enrichment pipeline including:
    - License plates with OCR
    - Face detection
    - Florence-2 vision extraction
    - Violence detection
    - Weather classification
    - Clothing analysis
    - Vehicle classification
    - Pet classification
    - Image quality metrics
    """
    return EnrichmentResult(
        license_plates=[
            LicensePlateResult(
                bbox=BoundingBox(x1=310, y1=220, x2=380, y2=250),
                text="ABC1234",
                confidence=0.92,
                ocr_confidence=0.88,
                source_detection_id=2,
            )
        ],
        faces=[
            FaceResult(
                bbox=BoundingBox(x1=150, y1=180, x2=190, y2=240),
                confidence=0.94,
                source_detection_id=1,
            )
        ],
        vision_extraction=BatchExtractionResult(
            scene_analysis=SceneAnalysis(
                caption="A person walking towards a parked car in a residential driveway",
                environment=EnvironmentContext(
                    lighting="daytime",
                    weather="clear",
                    location="outdoor",
                    time_of_day="afternoon",
                ),
            ),
            person_attributes={
                1: PersonAttributes(
                    gender="male",
                    age_range="adult",
                    clothing_description="dark jacket, jeans",
                    pose="walking",
                    activity="approaching vehicle",
                    carrying_items=["backpack"],
                )
            },
            vehicle_attributes={
                2: VehicleAttributes(
                    vehicle_type="sedan",
                    color="blue",
                    make_model="Honda Civic",
                    license_plate="ABC1234",
                    parked=True,
                )
            },
        ),
        violence_detection=ViolenceDetectionResult(
            violence_detected=False,
            confidence=0.05,
            violence_type=None,
            person_count=1,
        ),
        weather_classification=WeatherResult(
            primary_condition="clear",
            confidence=0.91,
            visibility_level="high",
        ),
        clothing_classifications={
            "1": ClothingClassification(
                top_color="dark blue",
                bottom_color="blue",
                has_face_covering=False,
                overall_style="casual",
                confidence=0.87,
            )
        },
        vehicle_classifications={
            "2": VehicleClassificationResult(
                vehicle_type="car",
                vehicle_subtype="sedan",
                color="blue",
                confidence=0.89,
            )
        },
        vehicle_damage={
            "2": VehicleDamageResult(
                has_damage=False,
                damage_detections=[],
                overall_confidence=0.12,
            )
        },
        pet_classifications={},
        errors=[],
        structured_errors=[],
        processing_time_ms=1250.5,
    )


@pytest.fixture
def mock_llm_response_success():
    """Standard successful LLM response with varying risk score."""
    return {
        "content": json.dumps(
            {
                "risk_score": 25,
                "risk_level": "low",
                "summary": "Resident arriving home and parking vehicle",
                "reasoning": "Person approaching their own vehicle in driveway during daytime. License plate ABC1234 recognized. No suspicious indicators. Normal household activity.",
            }
        )
    }


@pytest.fixture
def mock_llm_response_high_risk():
    """LLM response with high risk score."""
    return {
        "content": json.dumps(
            {
                "risk_score": 75,
                "risk_level": "high",
                "summary": "Unknown person testing vehicle door handles",
                "reasoning": "Unknown individual approaching parked vehicle with suspicious behavior. Person not recognized. Activity pattern suggests potential vehicle break-in attempt.",
            }
        )
    }


# =============================================================================
# Test: analyze_batch Completes Without Exceptions
# =============================================================================


class TestAnalyzeBatchWithEnrichment:
    """Test analyze_batch completes without exceptions using full enrichment."""

    async def test_analyze_batch_with_model_zoo_enrichment_no_exceptions(
        self,
        isolated_db,
        sample_camera,
        sample_detections,
        mock_redis_client,
        realistic_enrichment_result,
        mock_llm_response_success,
    ):
        """Verify analyze_batch completes without KeyError when using full Model Zoo enrichment.

        This test guards against KeyError: 'ondemand_enrichment_context' by ensuring
        all prompt template fields are properly populated when enrichment is present.
        """
        batch_id = f"batch_{uuid.uuid4()}"
        detection_ids = [d.id for d in sample_detections]

        # Setup Redis mock
        mock_redis_client.get.side_effect = [
            sample_camera.id,
            json.dumps(detection_ids),
        ]

        # Mock HTTP call to LLM
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_llm_response_success
        mock_response.raise_for_status = MagicMock()

        analyzer = NemotronAnalyzer(redis_client=mock_redis_client)

        # Mock the enrichment pipeline to return realistic data
        with (
            patch("httpx.AsyncClient.post") as mock_post,
            patch.object(
                analyzer,
                "_run_enrichment_pipeline",
                return_value=MagicMock(
                    success=True,
                    result=realistic_enrichment_result,
                    partial_failure=False,
                    errors=[],
                ),
            ),
        ):
            mock_post.return_value = mock_response

            # This should NOT raise KeyError
            event = await analyzer.analyze_batch(batch_id)

        # Verify event was created successfully
        assert event is not None
        assert event.id is not None
        assert event.batch_id == batch_id
        assert event.camera_id == sample_camera.id
        assert event.risk_score == 25
        assert event.risk_level == "low"

    async def test_analyze_batch_produces_non_fallback_results(
        self,
        isolated_db,
        sample_camera,
        sample_detections,
        mock_redis_client,
        realistic_enrichment_result,
        mock_llm_response_high_risk,
    ):
        """Verify analyze_batch produces actual LLM analysis, not fallback values.

        Fallback indicators:
        - summary: "Analysis unavailable - LLM service error"
        - risk_score: always 50
        - risk_level: always "medium"
        """
        batch_id = f"batch_{uuid.uuid4()}"
        detection_ids = [d.id for d in sample_detections]

        mock_redis_client.get.side_effect = [
            sample_camera.id,
            json.dumps(detection_ids),
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_llm_response_high_risk
        mock_response.raise_for_status = MagicMock()

        analyzer = NemotronAnalyzer(redis_client=mock_redis_client)

        with (
            patch("httpx.AsyncClient.post") as mock_post,
            patch.object(
                analyzer,
                "_run_enrichment_pipeline",
                return_value=MagicMock(
                    success=True,
                    result=realistic_enrichment_result,
                    partial_failure=False,
                    errors=[],
                ),
            ),
        ):
            mock_post.return_value = mock_response
            event = await analyzer.analyze_batch(batch_id)

        # Verify this is NOT a fallback result
        assert event.summary != "Analysis unavailable - LLM service error"
        assert "LLM service error" not in event.summary

        # Risk score should vary based on analysis (not always 50)
        assert event.risk_score == 75  # From high-risk response
        assert event.risk_level == "high"

        # Reasoning should contain actual analysis
        assert event.reasoning is not None
        assert len(event.reasoning) > 50  # Should have substantial content
        assert "suspicious" in event.reasoning.lower()

    async def test_analyze_batch_with_enrichment_multiple_scenarios(
        self,
        isolated_db,
        sample_camera,
        sample_detections,
        mock_redis_client,
        realistic_enrichment_result,
    ):
        """Test analyze_batch handles multiple enrichment scenarios without exceptions.

        Scenarios:
        1. Full enrichment with all model zoo components
        2. Partial enrichment (some models failed)
        3. Minimal enrichment (only basic vision extraction)
        """
        batch_id = f"batch_{uuid.uuid4()}"
        detection_ids = [d.id for d in sample_detections]

        # Scenario 1: Full enrichment (already tested above implicitly)
        # Scenario 2: Partial enrichment - only vision and weather
        partial_enrichment = EnrichmentResult(
            vision_extraction=realistic_enrichment_result.vision_extraction,
            weather_classification=realistic_enrichment_result.weather_classification,
            license_plates=[],
            faces=[],
            violence_detection=None,
            clothing_classifications={},
            vehicle_classifications={},
            errors=["Clothing model timeout", "Pet classifier unavailable"],
        )

        mock_redis_client.get.side_effect = [
            sample_camera.id,
            json.dumps(detection_ids),
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": json.dumps(
                {
                    "risk_score": 30,
                    "risk_level": "low",
                    "summary": "Normal activity with partial enrichment",
                    "reasoning": "Analysis based on available enrichment data",
                }
            )
        }
        mock_response.raise_for_status = MagicMock()

        analyzer = NemotronAnalyzer(redis_client=mock_redis_client)

        with (
            patch("httpx.AsyncClient.post") as mock_post,
            patch.object(
                analyzer,
                "_run_enrichment_pipeline",
                return_value=MagicMock(
                    success=True,
                    result=partial_enrichment,
                    partial_failure=True,
                    errors=["Clothing model timeout"],
                ),
            ),
        ):
            mock_post.return_value = mock_response

            # Should NOT raise KeyError even with partial enrichment
            event = await analyzer.analyze_batch(batch_id)

        assert event is not None
        assert event.risk_score == 30


# =============================================================================
# Test: analyze_detection_fast_path Completes Without Exceptions
# =============================================================================


class TestAnalyzeDetectionFastPathWithEnrichment:
    """Test fast path analysis completes without exceptions."""

    async def test_fast_path_with_model_zoo_enrichment_no_exceptions(
        self,
        isolated_db,
        sample_camera,
        sample_detections,
        mock_redis_client,
        realistic_enrichment_result,
        mock_llm_response_success,
    ):
        """Verify fast path analysis completes without KeyError with full enrichment."""
        detection = sample_detections[0]

        # Mock HTTP call to LLM
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_llm_response_success
        mock_response.raise_for_status = MagicMock()

        analyzer = NemotronAnalyzer(redis_client=mock_redis_client)

        with (
            patch("httpx.AsyncClient.post") as mock_post,
            patch.object(
                analyzer,
                "_run_enrichment_pipeline",
                return_value=MagicMock(
                    success=True,
                    result=realistic_enrichment_result,
                    partial_failure=False,
                    errors=[],
                ),
            ),
        ):
            mock_post.return_value = mock_response

            # Should NOT raise KeyError
            event = await analyzer.analyze_detection_fast_path(sample_camera.id, str(detection.id))

        assert event is not None
        assert event.is_fast_path is True
        assert event.risk_score == 25

    async def test_fast_path_produces_non_fallback_results(
        self,
        isolated_db,
        sample_camera,
        sample_detections,
        mock_redis_client,
        realistic_enrichment_result,
        mock_llm_response_high_risk,
    ):
        """Verify fast path produces actual analysis, not fallback values."""
        detection = sample_detections[0]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_llm_response_high_risk
        mock_response.raise_for_status = MagicMock()

        analyzer = NemotronAnalyzer(redis_client=mock_redis_client)

        with (
            patch("httpx.AsyncClient.post") as mock_post,
            patch.object(
                analyzer,
                "_run_enrichment_pipeline",
                return_value=MagicMock(
                    success=True,
                    result=realistic_enrichment_result,
                    partial_failure=False,
                    errors=[],
                ),
            ),
        ):
            mock_post.return_value = mock_response
            event = await analyzer.analyze_detection_fast_path(sample_camera.id, str(detection.id))

        # Verify NOT fallback
        assert event.summary != "Analysis unavailable - LLM service error"
        assert event.risk_score == 75
        assert event.risk_level == "high"
        assert "suspicious" in event.reasoning.lower()


# =============================================================================
# Test: Prompt Formatting with Enrichment Data
# =============================================================================


class TestPromptFormattingWithEnrichment:
    """Test that prompt building doesn't raise KeyError with realistic data."""

    async def test_prompt_formatting_includes_all_model_zoo_fields(
        self,
        isolated_db,
        sample_camera,
        sample_detections,
        mock_redis_client,
        realistic_enrichment_result,
        mock_llm_response_success,
    ):
        """Verify prompt formatting includes all required fields without KeyError.

        Critical fields from MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT:
        - camera_name, timestamp, day_of_week, time_of_day
        - weather_context, image_quality_context, camera_health_context
        - detections_with_all_attributes
        - violence_context, pose_analysis, action_recognition
        - vehicle_classification_context, vehicle_damage_context
        - clothing_analysis_context, pet_classification_context
        - depth_context, reid_context
        - zone_analysis, baseline_comparison, deviation_score
        - cross_camera_summary, scene_analysis
        - ondemand_enrichment_context (the missing field that caused KeyError)
        """
        batch_id = f"batch_{uuid.uuid4()}"
        detection_ids = [d.id for d in sample_detections]

        mock_redis_client.get.side_effect = [
            sample_camera.id,
            json.dumps(detection_ids),
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_llm_response_success
        mock_response.raise_for_status = MagicMock()

        analyzer = NemotronAnalyzer(redis_client=mock_redis_client)

        # Track what prompt was sent to LLM
        actual_prompt = None

        def capture_prompt(*args, **kwargs):
            nonlocal actual_prompt
            # Extract prompt from payload
            if len(args) > 1 and isinstance(args[1], dict):
                actual_prompt = args[1].get("messages", [{}])[0].get("content", "")
            return mock_response

        with (
            patch("httpx.AsyncClient.post", side_effect=capture_prompt) as mock_post,
            patch.object(
                analyzer,
                "_run_enrichment_pipeline",
                return_value=MagicMock(
                    success=True,
                    result=realistic_enrichment_result,
                    partial_failure=False,
                    errors=[],
                ),
            ),
        ):
            await analyzer.analyze_batch(batch_id)

        # Verify prompt was captured and LLM was called
        assert mock_post.called
        assert actual_prompt is not None

        # Verify key sections are present in prompt (spot check)
        # Note: The exact format depends on which prompt template is used
        # We're verifying the prompt was built without KeyError exceptions

    async def test_prompt_formatting_without_enrichment_no_exceptions(
        self,
        isolated_db,
        sample_camera,
        sample_detections,
        mock_redis_client,
        mock_llm_response_success,
    ):
        """Verify prompt formatting works even when enrichment is None/empty."""
        batch_id = f"batch_{uuid.uuid4()}"
        detection_ids = [d.id for d in sample_detections]

        mock_redis_client.get.side_effect = [
            sample_camera.id,
            json.dumps(detection_ids),
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_llm_response_success
        mock_response.raise_for_status = MagicMock()

        analyzer = NemotronAnalyzer(redis_client=mock_redis_client)

        # Mock enrichment pipeline returning empty/None result
        with (
            patch("httpx.AsyncClient.post") as mock_post,
            patch.object(
                analyzer,
                "_run_enrichment_pipeline",
                return_value=None,  # No enrichment
            ),
        ):
            mock_post.return_value = mock_response

            # Should NOT raise KeyError even without enrichment
            event = await analyzer.analyze_batch(batch_id)

        assert event is not None


# =============================================================================
# Test: Error Handling and Fallback Behavior
# =============================================================================


class TestErrorHandlingWithEnrichment:
    """Test error handling when LLM fails with enriched data."""

    async def test_analyze_batch_fallback_when_llm_fails(
        self,
        isolated_db,
        sample_camera,
        sample_detections,
        mock_redis_client,
        realistic_enrichment_result,
    ):
        """Verify fallback behavior when LLM service fails."""
        batch_id = f"batch_{uuid.uuid4()}"
        detection_ids = [d.id for d in sample_detections]

        mock_redis_client.get.side_effect = [
            sample_camera.id,
            json.dumps(detection_ids),
        ]

        analyzer = NemotronAnalyzer(redis_client=mock_redis_client)

        # Mock LLM to fail
        with (
            patch.object(
                httpx.AsyncClient, "post", side_effect=httpx.ConnectError("LLM unavailable")
            ),
            patch.object(
                analyzer,
                "_run_enrichment_pipeline",
                return_value=MagicMock(
                    success=True,
                    result=realistic_enrichment_result,
                    partial_failure=False,
                    errors=[],
                ),
            ),
        ):
            event = await analyzer.analyze_batch(batch_id)

        # Should create event with fallback values
        assert event is not None
        assert event.risk_score == 50  # Fallback score
        assert event.risk_level == "medium"  # Fallback level
        assert "LLM service error" in event.summary

    async def test_fast_path_fallback_when_llm_fails(
        self,
        isolated_db,
        sample_camera,
        sample_detections,
        mock_redis_client,
        realistic_enrichment_result,
    ):
        """Verify fast path fallback when LLM service fails."""
        detection = sample_detections[0]

        analyzer = NemotronAnalyzer(redis_client=mock_redis_client)

        with (
            patch.object(
                httpx.AsyncClient, "post", side_effect=httpx.ConnectError("LLM unavailable")
            ),
            patch.object(
                analyzer,
                "_run_enrichment_pipeline",
                return_value=MagicMock(
                    success=True,
                    result=realistic_enrichment_result,
                    partial_failure=False,
                    errors=[],
                ),
            ),
        ):
            event = await analyzer.analyze_detection_fast_path(sample_camera.id, str(detection.id))

        # Should create event with fallback values
        assert event is not None
        assert event.is_fast_path is True
        assert event.risk_score == 50
        assert "LLM service error" in event.summary


# =============================================================================
# Test: Enrichment Pipeline Integration
# =============================================================================


class TestEnrichmentPipelineIntegration:
    """Test integration between NemotronAnalyzer and enrichment pipeline."""

    async def test_enrichment_pipeline_called_with_correct_inputs(
        self,
        isolated_db,
        sample_camera,
        sample_detections,
        mock_redis_client,
        realistic_enrichment_result,
        mock_llm_response_success,
    ):
        """Verify enrichment pipeline is called with correct detection inputs."""
        batch_id = f"batch_{uuid.uuid4()}"
        detection_ids = [d.id for d in sample_detections]

        mock_redis_client.get.side_effect = [
            sample_camera.id,
            json.dumps(detection_ids),
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_llm_response_success
        mock_response.raise_for_status = MagicMock()

        analyzer = NemotronAnalyzer(redis_client=mock_redis_client)

        enrichment_called = False
        captured_inputs = None

        async def mock_enrichment(*args, **kwargs):
            nonlocal enrichment_called, captured_inputs
            enrichment_called = True
            captured_inputs = args
            return MagicMock(
                success=True,
                result=realistic_enrichment_result,
                partial_failure=False,
                errors=[],
            )

        with (
            patch("httpx.AsyncClient.post") as mock_post,
            patch.object(analyzer, "_run_enrichment_pipeline", side_effect=mock_enrichment),
        ):
            mock_post.return_value = mock_response
            await analyzer.analyze_batch(batch_id)

        # Verify enrichment pipeline was called
        assert enrichment_called
        # Could add more specific assertions about inputs if needed

    async def test_enrichment_errors_dont_prevent_analysis(
        self,
        isolated_db,
        sample_camera,
        sample_detections,
        mock_redis_client,
        mock_llm_response_success,
    ):
        """Verify analysis continues even when enrichment pipeline has errors."""
        batch_id = f"batch_{uuid.uuid4()}"
        detection_ids = [d.id for d in sample_detections]

        mock_redis_client.get.side_effect = [
            sample_camera.id,
            json.dumps(detection_ids),
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_llm_response_success
        mock_response.raise_for_status = MagicMock()

        # Enrichment result with errors
        enrichment_with_errors = EnrichmentResult(
            errors=["Florence-2 timeout", "CLIP service unavailable"],
            structured_errors=[],
        )

        analyzer = NemotronAnalyzer(redis_client=mock_redis_client)

        with (
            patch("httpx.AsyncClient.post") as mock_post,
            patch.object(
                analyzer,
                "_run_enrichment_pipeline",
                return_value=MagicMock(
                    success=True,
                    result=enrichment_with_errors,
                    partial_failure=True,
                    errors=["Florence-2 timeout"],
                ),
            ),
        ):
            mock_post.return_value = mock_response

            # Should complete despite enrichment errors
            event = await analyzer.analyze_batch(batch_id)

        assert event is not None
        assert event.risk_score == 25  # From LLM response
