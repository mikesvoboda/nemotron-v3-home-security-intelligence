"""Unit tests for DepthCalibrationService.

Tests for the depth-to-distance calibration service that converts
normalized depth values (0-1) to real-world distances (feet).

These tests are written in RED phase - they should FAIL until
the DepthCalibrationService is implemented.

NEM-5283: Phase 2 - Depth Distance Conversion
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

# These imports will FAIL until the service is implemented
from backend.services.depth_calibration_service import (
    CalibrationData,
    CalibrationPoint,
    DepthCalibrationService,
    InvalidCalibrationError,
    depth_to_feet,
    format_distance_context,
    get_depth_calibration_service,
    reset_depth_calibration_service,
    validate_calibration_data,
)

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def calibration_service() -> DepthCalibrationService:
    """Create a DepthCalibrationService instance."""
    return DepthCalibrationService()


@pytest.fixture
def sample_calibration_point() -> CalibrationPoint:
    """Create a sample calibration point.

    A calibration point maps a known depth value at a known location
    to a real-world distance in feet.
    """
    return CalibrationPoint(
        depth_value=0.3,  # Normalized depth at calibration location
        distance_feet=10.0,  # Known real-world distance
        reference_name="front_door_entrance",  # Named reference point
    )


@pytest.fixture
def sample_calibration_data(sample_calibration_point: CalibrationPoint) -> CalibrationData:
    """Create sample calibration data for a camera.

    Calibration data contains reference points and optional zone-specific
    calibrations for accurate depth-to-distance conversion.
    """
    return CalibrationData(
        camera_id="front_door",
        calibration_points=[sample_calibration_point],
        created_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        image_width=1920,
        image_height=1080,
    )


@pytest.fixture
def multi_point_calibration_data() -> CalibrationData:
    """Create calibration data with multiple reference points.

    Multiple points allow for more accurate interpolation across
    different depth ranges.
    """
    return CalibrationData(
        camera_id="driveway",
        calibration_points=[
            CalibrationPoint(
                depth_value=0.15,
                distance_feet=5.0,
                reference_name="near_garage",
            ),
            CalibrationPoint(
                depth_value=0.45,
                distance_feet=20.0,
                reference_name="mid_driveway",
            ),
            CalibrationPoint(
                depth_value=0.75,
                distance_feet=50.0,
                reference_name="street_edge",
            ),
        ],
        created_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        image_width=1920,
        image_height=1080,
    )


@pytest.fixture(autouse=True)
def reset_service_singleton() -> None:
    """Reset the depth calibration service singleton before and after each test."""
    reset_depth_calibration_service()
    yield
    reset_depth_calibration_service()


# =============================================================================
# CalibrationPoint Dataclass Tests
# =============================================================================


class TestCalibrationPoint:
    """Tests for CalibrationPoint dataclass."""

    def test_creation_with_required_fields(self) -> None:
        """Test CalibrationPoint creates with required fields."""
        point = CalibrationPoint(
            depth_value=0.25,
            distance_feet=8.0,
        )
        assert point.depth_value == 0.25
        assert point.distance_feet == 8.0
        assert point.reference_name is None  # Optional

    def test_creation_with_all_fields(self, sample_calibration_point: CalibrationPoint) -> None:
        """Test CalibrationPoint creates with all fields."""
        assert sample_calibration_point.depth_value == 0.3
        assert sample_calibration_point.distance_feet == 10.0
        assert sample_calibration_point.reference_name == "front_door_entrance"

    def test_depth_value_boundaries(self) -> None:
        """Test CalibrationPoint accepts valid depth value boundaries."""
        # Minimum valid depth
        point_min = CalibrationPoint(depth_value=0.0, distance_feet=1.0)
        assert point_min.depth_value == 0.0

        # Maximum valid depth
        point_max = CalibrationPoint(depth_value=1.0, distance_feet=100.0)
        assert point_max.depth_value == 1.0


# =============================================================================
# CalibrationData Dataclass Tests
# =============================================================================


class TestCalibrationData:
    """Tests for CalibrationData dataclass."""

    def test_creation_with_defaults(self) -> None:
        """Test CalibrationData creates with default values."""
        data = CalibrationData(
            camera_id="test_camera",
            calibration_points=[
                CalibrationPoint(depth_value=0.5, distance_feet=15.0),
            ],
        )
        assert data.camera_id == "test_camera"
        assert len(data.calibration_points) == 1
        assert data.image_width is None
        assert data.image_height is None

    def test_creation_with_all_fields(self, sample_calibration_data: CalibrationData) -> None:
        """Test CalibrationData creates with all fields."""
        assert sample_calibration_data.camera_id == "front_door"
        assert len(sample_calibration_data.calibration_points) == 1
        assert sample_calibration_data.image_width == 1920
        assert sample_calibration_data.image_height == 1080

    def test_multiple_calibration_points(
        self, multi_point_calibration_data: CalibrationData
    ) -> None:
        """Test CalibrationData with multiple calibration points."""
        assert len(multi_point_calibration_data.calibration_points) == 3
        # Points should be in order by depth
        depths = [p.depth_value for p in multi_point_calibration_data.calibration_points]
        assert depths == [0.15, 0.45, 0.75]


# =============================================================================
# Calibration Data Validation Tests
# =============================================================================


class TestValidateCalibrationData:
    """Tests for calibration data validation."""

    def test_validate_valid_calibration_data(
        self, sample_calibration_data: CalibrationData
    ) -> None:
        """Test validation passes for valid calibration data."""
        # Should not raise
        validate_calibration_data(sample_calibration_data)

    def test_validate_empty_calibration_points_raises(self) -> None:
        """Test validation fails when no calibration points provided."""
        data = CalibrationData(
            camera_id="test_camera",
            calibration_points=[],
        )
        with pytest.raises(InvalidCalibrationError, match="at least one calibration point"):
            validate_calibration_data(data)

    def test_validate_negative_distance_raises(self) -> None:
        """Test validation fails for negative distance values."""
        data = CalibrationData(
            camera_id="test_camera",
            calibration_points=[
                CalibrationPoint(depth_value=0.5, distance_feet=-10.0),
            ],
        )
        with pytest.raises(InvalidCalibrationError, match="negative distance"):
            validate_calibration_data(data)

    def test_validate_zero_distance_raises(self) -> None:
        """Test validation fails for zero distance values."""
        data = CalibrationData(
            camera_id="test_camera",
            calibration_points=[
                CalibrationPoint(depth_value=0.5, distance_feet=0.0),
            ],
        )
        with pytest.raises(InvalidCalibrationError, match="zero distance"):
            validate_calibration_data(data)

    def test_validate_depth_out_of_range_raises(self) -> None:
        """Test validation fails for depth values outside 0-1 range."""
        # Depth > 1
        data_high = CalibrationData(
            camera_id="test_camera",
            calibration_points=[
                CalibrationPoint(depth_value=1.5, distance_feet=10.0),
            ],
        )
        with pytest.raises(InvalidCalibrationError, match="depth value.*out of range"):
            validate_calibration_data(data_high)

        # Depth < 0
        data_low = CalibrationData(
            camera_id="test_camera",
            calibration_points=[
                CalibrationPoint(depth_value=-0.1, distance_feet=10.0),
            ],
        )
        with pytest.raises(InvalidCalibrationError, match="depth value.*out of range"):
            validate_calibration_data(data_low)

    def test_validate_duplicate_depth_values_raises(self) -> None:
        """Test validation fails for duplicate depth values."""
        data = CalibrationData(
            camera_id="test_camera",
            calibration_points=[
                CalibrationPoint(depth_value=0.5, distance_feet=10.0),
                CalibrationPoint(depth_value=0.5, distance_feet=15.0),  # Duplicate
            ],
        )
        with pytest.raises(InvalidCalibrationError, match="duplicate depth"):
            validate_calibration_data(data)

    def test_validate_non_monotonic_distance_warns(self) -> None:
        """Test validation warns for non-monotonic depth-distance relationship.

        As depth increases (farther from camera), distance should generally increase.
        """
        data = CalibrationData(
            camera_id="test_camera",
            calibration_points=[
                CalibrationPoint(depth_value=0.3, distance_feet=20.0),
                CalibrationPoint(depth_value=0.6, distance_feet=10.0),  # Decreasing distance
            ],
        )
        # Should warn but not raise (user might have valid reasons)
        with pytest.warns(UserWarning, match="non-monotonic"):
            validate_calibration_data(data)


# =============================================================================
# depth_to_feet Function Tests
# =============================================================================


class TestDepthToFeet:
    """Tests for depth_to_feet conversion function."""

    def test_exact_calibration_point(self, sample_calibration_data: CalibrationData) -> None:
        """Test depth_to_feet at exact calibration point."""
        # Calibration point is depth=0.3 -> 10 feet
        result = depth_to_feet(0.3, sample_calibration_data)
        assert result == pytest.approx(10.0)

    def test_interpolation_between_points(
        self, multi_point_calibration_data: CalibrationData
    ) -> None:
        """Test depth_to_feet interpolates between calibration points."""
        # Points: 0.15->5ft, 0.45->20ft, 0.75->50ft
        # Midpoint between first two: 0.30 should be ~12.5ft
        result = depth_to_feet(0.30, multi_point_calibration_data)
        assert result == pytest.approx(12.5)

    def test_extrapolation_below_min_point(
        self, multi_point_calibration_data: CalibrationData
    ) -> None:
        """Test depth_to_feet extrapolates below minimum calibration point."""
        # Minimum point is 0.15 -> 5ft
        # At depth=0.05, should extrapolate to closer distance
        result = depth_to_feet(0.05, multi_point_calibration_data)
        assert result is not None
        assert result < 5.0  # Should be closer than the min reference

    def test_extrapolation_above_max_point(
        self, multi_point_calibration_data: CalibrationData
    ) -> None:
        """Test depth_to_feet extrapolates above maximum calibration point."""
        # Maximum point is 0.75 -> 50ft
        # At depth=0.90, should extrapolate to farther distance
        result = depth_to_feet(0.90, multi_point_calibration_data)
        assert result is not None
        assert result > 50.0  # Should be farther than the max reference

    def test_uncalibrated_camera_returns_none(self) -> None:
        """Test depth_to_feet returns None for uncalibrated camera."""
        result = depth_to_feet(0.5, None)
        assert result is None

    def test_single_point_calibration(self) -> None:
        """Test depth_to_feet with single calibration point uses linear scaling."""
        data = CalibrationData(
            camera_id="test",
            calibration_points=[
                CalibrationPoint(depth_value=0.5, distance_feet=20.0),
            ],
        )
        # With single point at 0.5->20ft, depth=0.25 should give ~10ft
        result = depth_to_feet(0.25, data)
        assert result == pytest.approx(10.0)

    def test_boundary_depth_values(self, sample_calibration_data: CalibrationData) -> None:
        """Test depth_to_feet handles boundary depth values (0 and 1)."""
        # Depth = 0 (very close)
        result_close = depth_to_feet(0.0, sample_calibration_data)
        assert result_close is not None
        assert result_close >= 0

        # Depth = 1 (very far)
        result_far = depth_to_feet(1.0, sample_calibration_data)
        assert result_far is not None
        assert result_far > 0


# =============================================================================
# format_distance_context Function Tests
# =============================================================================


class TestFormatDistanceContext:
    """Tests for format_distance_context function."""

    def test_format_with_calibrated_distance(self) -> None:
        """Test format_distance_context with known distance."""
        result = format_distance_context(
            class_name="person",
            distance_feet=5.0,
            location_name="front door",
        )
        assert result == "Person is approximately 5 feet from front door"

    def test_format_rounds_distance(self) -> None:
        """Test format_distance_context rounds distance appropriately."""
        result = format_distance_context(
            class_name="person",
            distance_feet=7.3,
            location_name="entrance",
        )
        # Should round to nearest foot for readability
        assert "7 feet" in result or "7.3 feet" in result

    def test_format_with_very_close_distance(self) -> None:
        """Test format_distance_context with very close distance."""
        result = format_distance_context(
            class_name="person",
            distance_feet=1.5,
            location_name="doorway",
        )
        # Very close distances might use special phrasing
        assert "1" in result or "2" in result
        assert "doorway" in result

    def test_format_with_large_distance(self) -> None:
        """Test format_distance_context with large distance."""
        result = format_distance_context(
            class_name="car",
            distance_feet=100.0,
            location_name="street",
        )
        assert "100 feet" in result or "approximately 100" in result.lower()

    def test_format_fallback_without_distance(self) -> None:
        """Test format_distance_context falls back to proximity label when no distance."""
        result = format_distance_context(
            class_name="person",
            distance_feet=None,
            location_name="camera",
            proximity_label="very close",
        )
        assert "very close" in result.lower()
        assert "feet" not in result.lower()  # Should not mention feet

    def test_format_capitalizes_class_name(self) -> None:
        """Test format_distance_context capitalizes class name properly."""
        result = format_distance_context(
            class_name="delivery_truck",
            distance_feet=15.0,
            location_name="driveway",
        )
        # Should handle underscores and capitalization
        assert "Delivery truck" in result or "delivery truck" in result

    def test_format_with_default_location(self) -> None:
        """Test format_distance_context with default location name."""
        result = format_distance_context(
            class_name="person",
            distance_feet=10.0,
        )
        # Should use "camera" as default location
        assert "camera" in result.lower() or "10 feet" in result


# =============================================================================
# DepthCalibrationService Unit Tests
# =============================================================================


class TestDepthCalibrationServiceInit:
    """Tests for DepthCalibrationService initialization."""

    def test_default_initialization(self, calibration_service: DepthCalibrationService) -> None:
        """Test DepthCalibrationService initializes with correct defaults."""
        assert calibration_service is not None
        assert calibration_service._calibration_cache == {}

    def test_with_database_session(self) -> None:
        """Test DepthCalibrationService can be initialized with database session."""
        mock_session = AsyncMock()
        service = DepthCalibrationService(session=mock_session)
        assert service._session is mock_session


class TestDepthCalibrationServiceSingleton:
    """Tests for depth calibration service singleton pattern."""

    def test_get_returns_same_instance(self) -> None:
        """Test get_depth_calibration_service returns the same instance."""
        service1 = get_depth_calibration_service()
        service2 = get_depth_calibration_service()
        assert service1 is service2

    def test_reset_clears_singleton(self) -> None:
        """Test reset_depth_calibration_service clears the singleton."""
        service1 = get_depth_calibration_service()
        reset_depth_calibration_service()
        service2 = get_depth_calibration_service()
        assert service1 is not service2


class TestDepthCalibrationServiceConversion:
    """Tests for DepthCalibrationService depth-to-feet conversion."""

    @pytest.mark.asyncio
    async def test_convert_depth_calibrated_camera(
        self,
        calibration_service: DepthCalibrationService,
        sample_calibration_data: CalibrationData,
    ) -> None:
        """Test convert_depth_to_feet with calibrated camera."""
        # Register calibration data
        calibration_service.register_calibration(sample_calibration_data)

        result = await calibration_service.convert_depth_to_feet(
            camera_id="front_door",
            depth_value=0.3,
        )

        assert result == pytest.approx(10.0)

    @pytest.mark.asyncio
    async def test_convert_depth_uncalibrated_camera_returns_none(
        self,
        calibration_service: DepthCalibrationService,
    ) -> None:
        """Test convert_depth_to_feet returns None for uncalibrated camera."""
        result = await calibration_service.convert_depth_to_feet(
            camera_id="unknown_camera",
            depth_value=0.5,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_convert_depth_loads_from_database(
        self,
        calibration_service: DepthCalibrationService,
    ) -> None:
        """Test convert_depth_to_feet loads calibration from database if not cached."""
        # Mock database lookup
        mock_session = AsyncMock()
        mock_camera = MagicMock()
        mock_camera.calibration_data = {
            "calibration_points": [
                {"depth_value": 0.4, "distance_feet": 12.0},
            ],
        }
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_camera
        mock_session.execute.return_value = mock_result

        calibration_service._session = mock_session

        result = await calibration_service.convert_depth_to_feet(
            camera_id="db_camera",
            depth_value=0.4,
        )

        assert result == pytest.approx(12.0)
        mock_session.execute.assert_called_once()


class TestDepthCalibrationServiceRegistration:
    """Tests for calibration data registration."""

    def test_register_calibration(
        self,
        calibration_service: DepthCalibrationService,
        sample_calibration_data: CalibrationData,
    ) -> None:
        """Test registering calibration data."""
        calibration_service.register_calibration(sample_calibration_data)

        assert "front_door" in calibration_service._calibration_cache
        cached = calibration_service._calibration_cache["front_door"]
        assert cached.camera_id == "front_door"

    def test_register_calibration_overwrites_existing(
        self,
        calibration_service: DepthCalibrationService,
        sample_calibration_data: CalibrationData,
    ) -> None:
        """Test registering new calibration data overwrites existing."""
        calibration_service.register_calibration(sample_calibration_data)

        # Create new calibration with different values
        new_calibration = CalibrationData(
            camera_id="front_door",
            calibration_points=[
                CalibrationPoint(depth_value=0.5, distance_feet=25.0),
            ],
        )
        calibration_service.register_calibration(new_calibration)

        cached = calibration_service._calibration_cache["front_door"]
        assert cached.calibration_points[0].distance_feet == 25.0

    def test_register_invalid_calibration_raises(
        self,
        calibration_service: DepthCalibrationService,
    ) -> None:
        """Test registering invalid calibration data raises error."""
        invalid_calibration = CalibrationData(
            camera_id="test",
            calibration_points=[],  # Invalid: empty
        )
        with pytest.raises(InvalidCalibrationError):
            calibration_service.register_calibration(invalid_calibration)

    def test_unregister_calibration(
        self,
        calibration_service: DepthCalibrationService,
        sample_calibration_data: CalibrationData,
    ) -> None:
        """Test unregistering calibration data."""
        calibration_service.register_calibration(sample_calibration_data)
        calibration_service.unregister_calibration("front_door")

        assert "front_door" not in calibration_service._calibration_cache


class TestDepthCalibrationServiceQuery:
    """Tests for querying calibration status."""

    def test_is_calibrated_returns_true(
        self,
        calibration_service: DepthCalibrationService,
        sample_calibration_data: CalibrationData,
    ) -> None:
        """Test is_calibrated returns True for calibrated camera."""
        calibration_service.register_calibration(sample_calibration_data)

        assert calibration_service.is_calibrated("front_door") is True

    def test_is_calibrated_returns_false(
        self,
        calibration_service: DepthCalibrationService,
    ) -> None:
        """Test is_calibrated returns False for uncalibrated camera."""
        assert calibration_service.is_calibrated("unknown_camera") is False

    def test_get_calibration(
        self,
        calibration_service: DepthCalibrationService,
        sample_calibration_data: CalibrationData,
    ) -> None:
        """Test get_calibration returns calibration data."""
        calibration_service.register_calibration(sample_calibration_data)

        result = calibration_service.get_calibration("front_door")

        assert result is not None
        assert result.camera_id == "front_door"

    def test_get_calibration_returns_none_uncalibrated(
        self,
        calibration_service: DepthCalibrationService,
    ) -> None:
        """Test get_calibration returns None for uncalibrated camera."""
        result = calibration_service.get_calibration("unknown_camera")
        assert result is None


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_depth_exactly_at_calibration_reference(
        self, multi_point_calibration_data: CalibrationData
    ) -> None:
        """Test conversion when depth is exactly at calibration reference point."""
        # Test at each calibration point
        for point in multi_point_calibration_data.calibration_points:
            result = depth_to_feet(point.depth_value, multi_point_calibration_data)
            assert result == pytest.approx(point.distance_feet)

    def test_edge_of_frame_depth_estimation(self) -> None:
        """Test depth estimation at edge of frame (less accurate).

        Edge regions of depth maps are typically less accurate due to
        model limitations. The service should handle this gracefully.
        """
        # Create calibration with edge region marker
        data = CalibrationData(
            camera_id="test",
            calibration_points=[
                CalibrationPoint(depth_value=0.5, distance_feet=15.0),
            ],
        )

        # Edge of frame depth values should still work
        result = depth_to_feet(0.5, data)
        assert result is not None

    def test_multiple_zones_with_different_references(self) -> None:
        """Test calibration with zone-specific reference points.

        Different zones in the camera view might have different
        depth-to-distance mappings (e.g., driveway vs sidewalk).
        """
        data = CalibrationData(
            camera_id="multi_zone",
            calibration_points=[
                CalibrationPoint(
                    depth_value=0.3,
                    distance_feet=10.0,
                    reference_name="zone_entry_point",
                ),
                CalibrationPoint(
                    depth_value=0.5,
                    distance_feet=25.0,
                    reference_name="zone_driveway",
                ),
                CalibrationPoint(
                    depth_value=0.7,
                    distance_feet=40.0,
                    reference_name="zone_sidewalk",
                ),
            ],
        )

        # Interpolation should work across zones
        result = depth_to_feet(0.4, data)
        assert result is not None
        assert 10.0 < result < 25.0

    def test_very_close_depth_values(self) -> None:
        """Test handling of very close (near-zero) depth values."""
        data = CalibrationData(
            camera_id="test",
            calibration_points=[
                CalibrationPoint(depth_value=0.1, distance_feet=2.0),
                CalibrationPoint(depth_value=0.5, distance_feet=20.0),
            ],
        )

        # Very close to camera
        result = depth_to_feet(0.02, data)
        assert result is not None
        assert result > 0  # Should still be positive
        assert result < 2.0  # Should be closer than min reference

    def test_very_far_depth_values(self) -> None:
        """Test handling of very far (near-one) depth values."""
        data = CalibrationData(
            camera_id="test",
            calibration_points=[
                CalibrationPoint(depth_value=0.3, distance_feet=10.0),
                CalibrationPoint(depth_value=0.7, distance_feet=40.0),
            ],
        )

        # Very far from camera
        result = depth_to_feet(0.95, data)
        assert result is not None
        assert result > 40.0  # Should be farther than max reference

    def test_conversion_precision(self) -> None:
        """Test that conversion maintains reasonable precision."""
        data = CalibrationData(
            camera_id="test",
            calibration_points=[
                CalibrationPoint(depth_value=0.25, distance_feet=7.5),
                CalibrationPoint(depth_value=0.75, distance_feet=30.0),
            ],
        )

        # Midpoint should give precise result
        result = depth_to_feet(0.5, data)
        expected = (7.5 + 30.0) / 2  # 18.75
        assert result == pytest.approx(expected, rel=0.01)


# =============================================================================
# Integration with Context Enricher Tests
# =============================================================================


class TestContextEnricherIntegration:
    """Tests for integration with ContextEnricher.

    These tests verify that the depth calibration service properly
    integrates with the context enricher for LLM prompt generation.
    """

    @pytest.mark.asyncio
    async def test_enriched_context_includes_distance(
        self,
        calibration_service: DepthCalibrationService,
        sample_calibration_data: CalibrationData,
    ) -> None:
        """Test that enriched context includes calibrated distance."""
        calibration_service.register_calibration(sample_calibration_data)

        # Simulate building context for a detection
        detection = {
            "class_name": "person",
            "depth_value": 0.3,
            "camera_id": "front_door",
        }

        distance = await calibration_service.convert_depth_to_feet(
            camera_id=detection["camera_id"],
            depth_value=detection["depth_value"],
        )

        context_string = format_distance_context(
            class_name=detection["class_name"],
            distance_feet=distance,
            location_name="front door",
        )

        assert "10 feet" in context_string or "10.0 feet" in context_string
        assert "Person" in context_string or "person" in context_string

    @pytest.mark.asyncio
    async def test_enriched_context_fallback_without_calibration(
        self,
        calibration_service: DepthCalibrationService,
    ) -> None:
        """Test that enriched context falls back to proximity label without calibration."""
        # No calibration registered

        detection = {
            "class_name": "person",
            "depth_value": 0.2,
            "camera_id": "uncalibrated_camera",
            "proximity_label": "close",
        }

        distance = await calibration_service.convert_depth_to_feet(
            camera_id=detection["camera_id"],
            depth_value=detection["depth_value"],
        )

        assert distance is None  # No calibration

        context_string = format_distance_context(
            class_name=detection["class_name"],
            distance_feet=distance,
            location_name="camera",
            proximity_label=detection["proximity_label"],
        )

        assert "close" in context_string.lower()
        assert "feet" not in context_string.lower()


# =============================================================================
# Database Model Integration Tests
# =============================================================================


class TestCameraCalibrationDataField:
    """Tests for Camera model calibration_data field integration.

    The Camera model should have a calibration_data JSON field to store
    depth calibration settings.
    """

    def test_camera_model_has_calibration_data_field(self) -> None:
        """Test that Camera model has calibration_data field."""
        from backend.models.camera import Camera

        # The field should exist (will fail until implemented)
        camera = Camera(
            id="test_camera",
            name="Test Camera",
            folder_path="/test/path",
        )
        # Should be able to set calibration_data
        assert hasattr(camera, "calibration_data")

    def test_calibration_data_json_serialization(self) -> None:
        """Test that calibration_data properly serializes to JSON."""
        from backend.models.camera import Camera

        calibration = {
            "calibration_points": [
                {
                    "depth_value": 0.3,
                    "distance_feet": 10.0,
                    "reference_name": "entrance",
                }
            ],
            "image_width": 1920,
            "image_height": 1080,
        }

        camera = Camera(
            id="test_camera",
            name="Test Camera",
            folder_path="/test/path",
            calibration_data=calibration,
        )

        assert camera.calibration_data is not None
        assert camera.calibration_data["calibration_points"][0]["depth_value"] == 0.3

    def test_calibration_data_nullable(self) -> None:
        """Test that calibration_data can be None (uncalibrated camera)."""
        from backend.models.camera import Camera

        camera = Camera(
            id="test_camera",
            name="Test Camera",
            folder_path="/test/path",
        )

        # calibration_data should be None by default
        assert camera.calibration_data is None


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling in depth calibration."""

    def test_invalid_calibration_error_message(self) -> None:
        """Test InvalidCalibrationError has informative message."""
        error = InvalidCalibrationError("Test error message")
        assert str(error) == "Test error message"

    @pytest.mark.asyncio
    async def test_corrupt_calibration_data_handling(
        self,
        calibration_service: DepthCalibrationService,
    ) -> None:
        """Test handling of corrupt calibration data from database."""
        # Simulate corrupt data
        mock_session = AsyncMock()
        mock_camera = MagicMock()
        mock_camera.calibration_data = {"invalid": "data"}  # Missing required fields
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_camera
        mock_session.execute.return_value = mock_result

        calibration_service._session = mock_session

        # Should handle gracefully and return None
        result = await calibration_service.convert_depth_to_feet(
            camera_id="corrupt_camera",
            depth_value=0.5,
        )

        assert result is None  # Graceful fallback

    @pytest.mark.asyncio
    async def test_database_error_handling(
        self,
        calibration_service: DepthCalibrationService,
    ) -> None:
        """Test handling of database errors during calibration lookup."""
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("Database connection error")

        calibration_service._session = mock_session

        # Should handle gracefully and return None
        result = await calibration_service.convert_depth_to_feet(
            camera_id="error_camera",
            depth_value=0.5,
        )

        assert result is None  # Graceful fallback
