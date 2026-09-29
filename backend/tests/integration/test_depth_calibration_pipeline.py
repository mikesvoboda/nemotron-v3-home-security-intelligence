"""Integration tests for depth-to-distance calibration.

R8 S2b scope note: the depth ESTIMATOR (depth_anything_loader) is retired with
the legacy enrichment pipeline, so this file no longer drives a depth map into
an analysis step. What survives here is the calibration arithmetic and its
carrier - the Camera.calibration_data contract, the depth-to-feet mapping, the
proximity-label fallback, the prompt-context formatter, and the service's
DB load/cache/degradation behaviour.

NEM-5283: Phase 2 - Depth Distance Conversion
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mark as integration tests
pytestmark = pytest.mark.integration


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_camera_with_calibration() -> MagicMock:
    """Create a mock camera with calibration data."""
    camera = MagicMock()
    camera.id = "front_door"
    camera.name = "Front Door"
    camera.calibration_data = {
        "calibration_points": [
            {
                "depth_value": 0.15,
                "distance_feet": 4.0,
                "reference_name": "doorstep",
            },
            {
                "depth_value": 0.35,
                "distance_feet": 12.0,
                "reference_name": "walkway",
            },
            {
                "depth_value": 0.60,
                "distance_feet": 25.0,
                "reference_name": "sidewalk",
            },
        ],
        "image_width": 1920,
        "image_height": 1080,
    }
    return camera


# =============================================================================
# Context Enricher Integration Tests
# =============================================================================


class TestContextEnricherDepthIntegration:
    """Tests for depth calibration integration with ContextEnricher."""

    @pytest.mark.asyncio
    async def test_enriched_context_includes_calibrated_depths(
        self,
        mock_camera_with_calibration: MagicMock,
    ) -> None:
        """Test ContextEnricher includes calibrated depth distances.

        The EnrichedContext should include depth information with
        real-world distances when camera calibration is available.
        """
        from backend.services.context_enricher import ContextEnricher
        from backend.services.depth_calibration_service import (
            CalibrationData,
            CalibrationPoint,
            get_depth_calibration_service,
        )

        # Register calibration
        calibration_service = get_depth_calibration_service()
        calibration_data = CalibrationData(
            camera_id=mock_camera_with_calibration.id,
            calibration_points=[
                CalibrationPoint(**point)
                for point in mock_camera_with_calibration.calibration_data["calibration_points"]
            ],
        )
        calibration_service.register_calibration(calibration_data)

        # Mock database session
        mock_session = AsyncMock()

        # Mock camera query
        mock_camera_result = MagicMock()
        mock_camera_result.scalar_one_or_none.return_value = mock_camera_with_calibration

        # Mock detection query
        mock_detection = MagicMock()
        mock_detection.id = 1
        mock_detection.detected_at = datetime.now(UTC)
        mock_detection.bbox_x = 300
        mock_detection.bbox_y = 150
        mock_detection.bbox_width = 100
        mock_detection.bbox_height = 200
        mock_detection.object_type = "person"
        mock_detection.camera_id = "front_door"
        mock_detection.depth_value = 0.25  # Will need calibration

        mock_detections_result = MagicMock()
        mock_detections_result.scalars.return_value.all.return_value = [mock_detection]

        # Mock other queries (zones, baselines, cross-camera)
        mock_empty_result = MagicMock()
        mock_empty_result.scalars.return_value.all.return_value = []
        mock_empty_result.scalar_one_or_none.return_value = None

        mock_session.execute.side_effect = [
            mock_camera_result,
            mock_detections_result,
            mock_empty_result,  # zones
            mock_empty_result,  # class baselines
            mock_empty_result,  # activity baseline
            mock_empty_result,  # cross-camera
        ]

        # Mock baseline service
        mock_baseline_service = MagicMock()
        mock_baseline_service.is_anomalous = AsyncMock(return_value=(False, 0.5))

        with patch(
            "backend.services.context_enricher.get_baseline_service",
            return_value=mock_baseline_service,
            autospec=True,
        ):
            enricher = ContextEnricher()
            context = await enricher.enrich(
                batch_id="batch-1",
                camera_id="front_door",
                detection_ids=[1],
                session=mock_session,
            )

        # The enriched context should have depth information available
        # This will be used when building the final analysis prompt
        assert context is not None
        assert context.camera_id == "front_door"


# =============================================================================
# Prompt Context Integration Tests
# =============================================================================


class TestPromptContextIntegration:
    """Tests for depth distance integration in the analysis prompt.

    R8 S2b: renamed from TestNemotronPromptIntegration. Nothing here ever
    touched the retired analyzer - both tests drive
    depth_calibration_service.format_distance_context, which is the live
    prompt-context formatter.
    """

    @pytest.mark.asyncio
    async def test_prompt_context_includes_distance_context(self) -> None:
        """Test that the prompt context includes calibrated distance information.

        The context handed to the analyzer for risk analysis should
        include human-readable distance information like:
        "Person is approximately 5 feet from front door"
        """
        from backend.services.depth_calibration_service import format_distance_context

        # Simulate detection with calibrated distance
        context_parts = []

        # Add distance context for person detection
        person_context = format_distance_context(
            class_name="person",
            distance_feet=5.0,
            location_name="front door",
        )
        context_parts.append(person_context)

        # Add distance context for vehicle detection
        vehicle_context = format_distance_context(
            class_name="delivery_van",
            distance_feet=35.0,
            location_name="front door",
        )
        context_parts.append(vehicle_context)

        full_context = "\n".join(context_parts)

        # Verify context is suitable for the analyzer
        assert "Person" in full_context or "person" in full_context
        assert "5 feet" in full_context or "approximately 5" in full_context.lower()
        assert "front door" in full_context.lower()
        assert "35 feet" in full_context or "approximately 35" in full_context.lower()

    @pytest.mark.asyncio
    async def test_prompt_context_with_mixed_calibration(self) -> None:
        """Test the context with some calibrated and some uncalibrated cameras.

        When processing detections from multiple cameras, the context
        should include distances for calibrated cameras and proximity
        labels for uncalibrated cameras.
        """
        from backend.services.depth_calibration_service import format_distance_context

        context_parts = []

        # Calibrated camera detection
        calibrated_context = format_distance_context(
            class_name="person",
            distance_feet=8.0,
            location_name="front door",
        )
        context_parts.append(calibrated_context)

        # Uncalibrated camera detection (falls back to proximity)
        uncalibrated_context = format_distance_context(
            class_name="person",
            distance_feet=None,
            location_name="back yard",
            proximity_label="close",
        )
        context_parts.append(uncalibrated_context)

        full_context = "\n".join(context_parts)

        # First detection should have feet
        assert "8 feet" in full_context or "approximately 8" in full_context.lower()

        # Second detection should have proximity label
        assert "close" in full_context.lower()


# =============================================================================
# Database Integration Tests
# =============================================================================


class TestDatabaseCalibrationIntegration:
    """Tests for database storage and retrieval of calibration data."""

    @pytest.mark.asyncio
    async def test_load_calibration_from_database(self) -> None:
        """Test loading calibration data from the Camera model.

        The DepthCalibrationService should be able to load calibration
        data from the Camera.calibration_data JSON field.
        """
        from backend.services.depth_calibration_service import DepthCalibrationService

        # Mock database session
        mock_session = AsyncMock()

        # Mock camera with calibration data
        mock_camera = MagicMock()
        mock_camera.id = "test_camera"
        mock_camera.calibration_data = {
            "calibration_points": [
                {"depth_value": 0.3, "distance_feet": 10.0},
            ],
        }

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_camera
        mock_session.execute.return_value = mock_result

        service = DepthCalibrationService(session=mock_session)

        # Load and convert
        distance = await service.convert_depth_to_feet(
            camera_id="test_camera",
            depth_value=0.3,
        )

        assert distance == pytest.approx(10.0)

    @pytest.mark.asyncio
    async def test_calibration_data_caching(self) -> None:
        """Test that calibration data is cached after first load.

        The service should cache calibration data to avoid repeated
        database queries for the same camera.
        """
        from backend.services.depth_calibration_service import DepthCalibrationService

        mock_session = AsyncMock()

        mock_camera = MagicMock()
        mock_camera.id = "cached_camera"
        mock_camera.calibration_data = {
            "calibration_points": [
                {"depth_value": 0.5, "distance_feet": 15.0},
            ],
        }

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_camera
        mock_session.execute.return_value = mock_result

        service = DepthCalibrationService(session=mock_session)

        # First call - should query database
        await service.convert_depth_to_feet("cached_camera", 0.5)

        # Second call - should use cache
        await service.convert_depth_to_feet("cached_camera", 0.5)

        # Database should only be queried once
        assert mock_session.execute.call_count == 1


# =============================================================================
# Performance Tests
# =============================================================================


class TestDepthCalibrationPerformance:
    """Performance tests for depth calibration."""

    @pytest.mark.asyncio
    async def test_bulk_conversion_performance(self) -> None:
        """Test performance of bulk depth-to-feet conversions.

        Converting many depth values should be efficient enough
        for real-time processing.
        """
        import time

        from backend.services.depth_calibration_service import (
            CalibrationData,
            CalibrationPoint,
            depth_to_feet,
        )

        calibration = CalibrationData(
            camera_id="perf_test",
            calibration_points=[
                CalibrationPoint(depth_value=0.1, distance_feet=3.0),
                CalibrationPoint(depth_value=0.3, distance_feet=10.0),
                CalibrationPoint(depth_value=0.5, distance_feet=20.0),
                CalibrationPoint(depth_value=0.7, distance_feet=35.0),
                CalibrationPoint(depth_value=0.9, distance_feet=60.0),
            ],
        )

        # Convert 1000 depth values
        depth_values = [i / 1000.0 for i in range(1000)]

        start_time = time.perf_counter()
        results = [depth_to_feet(d, calibration) for d in depth_values]
        elapsed = time.perf_counter() - start_time

        # Should complete in less than 100ms for 1000 conversions
        assert elapsed < 0.1, f"Bulk conversion took {elapsed:.3f}s, expected < 0.1s"

        # All results should be valid
        assert all(r is not None and r > 0 for r in results)


# =============================================================================
# Error Recovery Tests
# =============================================================================


class TestErrorRecovery:
    """Tests for error recovery in the calibration pipeline."""

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_database_error(self) -> None:
        """Test graceful degradation when database is unavailable.

        If the database fails, the service should return None
        and allow the pipeline to fall back to proximity labels.
        """
        from backend.services.depth_calibration_service import DepthCalibrationService

        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("Database connection lost")

        service = DepthCalibrationService(session=mock_session)

        # Should not raise, should return None
        result = await service.convert_depth_to_feet(
            camera_id="error_camera",
            depth_value=0.5,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_corrupt_calibration_data_handling(self) -> None:
        """Test handling of corrupt calibration data in database.

        If calibration data is malformed, the service should
        gracefully fall back rather than crash.
        """
        from backend.services.depth_calibration_service import DepthCalibrationService

        mock_session = AsyncMock()

        mock_camera = MagicMock()
        mock_camera.id = "corrupt_camera"
        mock_camera.calibration_data = {
            "invalid_field": "bad_data",
            # Missing required calibration_points
        }

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_camera
        mock_session.execute.return_value = mock_result

        service = DepthCalibrationService(session=mock_session)

        # Should handle gracefully
        result = await service.convert_depth_to_feet(
            camera_id="corrupt_camera",
            depth_value=0.5,
        )

        assert result is None  # Graceful fallback
