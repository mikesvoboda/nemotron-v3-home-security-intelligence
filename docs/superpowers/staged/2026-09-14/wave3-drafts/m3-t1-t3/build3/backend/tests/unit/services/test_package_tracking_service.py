"""Unit tests for PackageTrackingService (NEM-5293).

Tests for package detection and tracking using YOLO-World model.
This module follows TDD - all tests are written BEFORE implementation.

Tests cover:
- Package detection via YOLO-World with confidence thresholds
- Package state tracking (delivered, removed, present)
- Package persistence across frames
- Multiple package tracking
- Package theft detection logic
- Integration with zones and household members
- Package event creation and linking

IMPORTANT: These tests are designed to FAIL until implementation is complete.
This is Phase 4 (Red phase) of TDD - writing failing tests first.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Custom Strategies for Property-Based Testing
# =============================================================================

# Strategy for valid confidence scores
confidence_scores = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)

# Strategy for package prompts that should be detected
package_prompts = st.sampled_from(
    [
        "cardboard delivery package",
        "Amazon shipping box",
        "FedEx package",
        "UPS package",
        "mail envelope",
        "food delivery bag",
        "pizza box",
        "package",
        "cardboard box",
        "Amazon box",
        "delivery box",
    ]
)

# Strategy for bounding box coordinates (normalized 0-1)
normalized_coords = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)

# Strategy for valid bounding boxes
bounding_boxes = st.fixed_dictionaries(
    {
        "x1": normalized_coords,
        "y1": normalized_coords,
        "x2": normalized_coords,
        "y2": normalized_coords,
    }
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_yolo_world_model():
    """Create a mock YOLO-World model for testing."""
    model = MagicMock()
    model.set_classes = MagicMock()
    model.predict = MagicMock()
    return model


@pytest.fixture
def sample_package_detection():
    """Create a sample package detection result."""
    return {
        "class_name": "cardboard delivery package",
        "confidence": 0.72,
        "bbox": {
            "x1": 0.3,
            "y1": 0.4,
            "x2": 0.5,
            "y2": 0.7,
        },
        "class_id": 0,
    }


@pytest.fixture
def sample_low_confidence_detection():
    """Create a sample low-confidence detection that should be filtered."""
    return {
        "class_name": "package",
        "confidence": 0.25,  # Below 0.35 threshold
        "bbox": {
            "x1": 0.2,
            "y1": 0.3,
            "x2": 0.4,
            "y2": 0.5,
        },
        "class_id": 1,
    }


@pytest.fixture
def sample_zone():
    """Create a sample delivery zone for testing."""
    from backend.tests.factories import ZoneFactory

    return ZoneFactory(
        id="delivery_zone_001",
        camera_id="front_door",
        name="Package Delivery Zone",
        entry_point=True,  # Use entry_point trait
        coordinates=[[0.1, 0.2], [0.6, 0.2], [0.6, 0.9], [0.1, 0.9]],
    )


@pytest.fixture
def sample_household_member():
    """Create a sample household member for testing."""
    from backend.tests.factories import HouseholdMemberFactory

    return HouseholdMemberFactory(
        id="member_001",
        name="John Doe",
        role="resident",
    )


# =============================================================================
# PackageTrackingService Import Tests (will fail until implemented)
# =============================================================================


class TestPackageTrackingServiceImports:
    """Test that PackageTrackingService module can be imported."""

    def test_package_tracking_service_importable(self) -> None:
        """Test PackageTrackingService class can be imported."""
        from backend.services.package_tracking_service import PackageTrackingService

        assert PackageTrackingService is not None

    def test_package_state_enum_importable(self) -> None:
        """Test PackageState enum can be imported."""
        from backend.services.package_tracking_service import PackageState

        assert PackageState is not None

    def test_tracked_package_importable(self) -> None:
        """Test TrackedPackage dataclass can be imported."""
        from backend.services.package_tracking_service import TrackedPackage

        assert TrackedPackage is not None

    def test_package_detection_result_importable(self) -> None:
        """Test PackageDetectionResult can be imported."""
        from backend.services.package_tracking_service import PackageDetectionResult

        assert PackageDetectionResult is not None

    def test_get_package_tracking_service_importable(self) -> None:
        """Test get_package_tracking_service function can be imported."""
        from backend.services.package_tracking_service import get_package_tracking_service

        assert callable(get_package_tracking_service)


# =============================================================================
# PackageState Enum Tests
# =============================================================================


class TestPackageStateEnum:
    """Tests for PackageState enum."""

    def test_package_state_delivered(self) -> None:
        """Test DELIVERED state exists and has correct value."""
        from backend.services.package_tracking_service import PackageState

        assert PackageState.DELIVERED.value == "delivered"

    def test_package_state_removed(self) -> None:
        """Test REMOVED state exists and has correct value."""
        from backend.services.package_tracking_service import PackageState

        assert PackageState.REMOVED.value == "removed"

    def test_package_state_present(self) -> None:
        """Test PRESENT state exists and has correct value."""
        from backend.services.package_tracking_service import PackageState

        assert PackageState.PRESENT.value == "present"

    def test_package_state_suspicious_removal(self) -> None:
        """Test SUSPICIOUS_REMOVAL state exists and has correct value."""
        from backend.services.package_tracking_service import PackageState

        assert PackageState.SUSPICIOUS_REMOVAL.value == "suspicious_removal"

    def test_package_state_is_string_enum(self) -> None:
        """Test that PackageState is a string enum."""
        from backend.services.package_tracking_service import PackageState

        for state in PackageState:
            assert isinstance(state.value, str)


# =============================================================================
# TrackedPackage Dataclass Tests
# =============================================================================


class TestTrackedPackageDataclass:
    """Tests for TrackedPackage dataclass."""

    def test_tracked_package_creation(self) -> None:
        """Test creating a TrackedPackage instance."""
        from backend.services.package_tracking_service import PackageState, TrackedPackage

        package = TrackedPackage(
            id="pkg_001",
            bbox={"x1": 0.3, "y1": 0.4, "x2": 0.5, "y2": 0.7},
            confidence=0.72,
            state=PackageState.DELIVERED,
            first_seen=datetime.now(UTC),
            last_seen=datetime.now(UTC),
            zone_id="delivery_zone_001",
            camera_id="front_door",
        )

        assert package.id == "pkg_001"
        assert package.state == PackageState.DELIVERED
        assert package.confidence == 0.72

    def test_tracked_package_zone_id_optional(self) -> None:
        """Test TrackedPackage with no zone assignment."""
        from backend.services.package_tracking_service import PackageState, TrackedPackage

        package = TrackedPackage(
            id="pkg_002",
            bbox={"x1": 0.1, "y1": 0.2, "x2": 0.3, "y2": 0.4},
            confidence=0.65,
            state=PackageState.PRESENT,
            first_seen=datetime.now(UTC),
            last_seen=datetime.now(UTC),
            zone_id=None,
            camera_id="side_door",
        )

        assert package.zone_id is None

    def test_tracked_package_removal_time_optional(self) -> None:
        """Test TrackedPackage removal_time is None by default."""
        from backend.services.package_tracking_service import PackageState, TrackedPackage

        package = TrackedPackage(
            id="pkg_003",
            bbox={"x1": 0.2, "y1": 0.3, "x2": 0.4, "y2": 0.5},
            confidence=0.80,
            state=PackageState.DELIVERED,
            first_seen=datetime.now(UTC),
            last_seen=datetime.now(UTC),
            zone_id="zone_001",
            camera_id="front_door",
        )

        assert package.removal_time is None

    def test_tracked_package_with_removal_time(self) -> None:
        """Test TrackedPackage with removal time set."""
        from backend.services.package_tracking_service import PackageState, TrackedPackage

        first_seen = datetime.now(UTC) - timedelta(minutes=30)
        last_seen = datetime.now(UTC) - timedelta(minutes=5)
        removal_time = datetime.now(UTC)

        package = TrackedPackage(
            id="pkg_004",
            bbox={"x1": 0.3, "y1": 0.4, "x2": 0.5, "y2": 0.7},
            confidence=0.75,
            state=PackageState.REMOVED,
            first_seen=first_seen,
            last_seen=last_seen,
            removal_time=removal_time,
            zone_id="zone_001",
            camera_id="front_door",
        )

        assert package.state == PackageState.REMOVED
        assert package.removal_time == removal_time


# =============================================================================
# YOLO-World Package Detection Tests
# =============================================================================


class TestYoloWorldPackageDetection:
    """Tests for YOLO-World package detection."""

    @pytest.mark.asyncio
    async def test_detect_cardboard_delivery_package(self, mock_yolo_world_model) -> None:
        """Test YOLO-World detects 'cardboard delivery package' with confidence > 0.35."""
        from backend.services.package_tracking_service import PackageTrackingService

        service = PackageTrackingService()

        # Mock detection result
        mock_detection = {
            "class_name": "cardboard delivery package",
            "confidence": 0.72,
            "bbox": {"x1": 0.3, "y1": 0.4, "x2": 0.5, "y2": 0.7},
            "class_id": 0,
        }

        with patch.object(service, "_run_yolo_world_detection", return_value=[mock_detection]):
            result = await service.detect_packages(mock_yolo_world_model, MagicMock())

        assert len(result.detections) == 1
        assert result.detections[0]["class_name"] == "cardboard delivery package"
        assert result.detections[0]["confidence"] > 0.35

    @pytest.mark.asyncio
    async def test_detect_amazon_box(self, mock_yolo_world_model) -> None:
        """Test YOLO-World detects 'Amazon box' with confidence > 0.35."""
        from backend.services.package_tracking_service import PackageTrackingService

        service = PackageTrackingService()

        mock_detection = {
            "class_name": "Amazon box",
            "confidence": 0.68,
            "bbox": {"x1": 0.2, "y1": 0.3, "x2": 0.4, "y2": 0.6},
            "class_id": 1,
        }

        with patch.object(service, "_run_yolo_world_detection", return_value=[mock_detection]):
            result = await service.detect_packages(mock_yolo_world_model, MagicMock())

        assert len(result.detections) == 1
        assert result.detections[0]["class_name"] == "Amazon box"
        assert result.detections[0]["confidence"] > 0.35

    @pytest.mark.asyncio
    async def test_package_detection_returns_bounding_box(self, mock_yolo_world_model) -> None:
        """Test package detection returns bounding box coordinates."""
        from backend.services.package_tracking_service import PackageTrackingService

        service = PackageTrackingService()

        mock_detection = {
            "class_name": "FedEx package",
            "confidence": 0.65,
            "bbox": {"x1": 0.15, "y1": 0.25, "x2": 0.45, "y2": 0.55},
            "class_id": 2,
        }

        with patch.object(service, "_run_yolo_world_detection", return_value=[mock_detection]):
            result = await service.detect_packages(mock_yolo_world_model, MagicMock())

        assert "bbox" in result.detections[0]
        bbox = result.detections[0]["bbox"]
        assert "x1" in bbox
        assert "y1" in bbox
        assert "x2" in bbox
        assert "y2" in bbox

    @pytest.mark.asyncio
    async def test_package_detection_returns_confidence(self, mock_yolo_world_model) -> None:
        """Test package detection returns confidence score."""
        from backend.services.package_tracking_service import PackageTrackingService

        service = PackageTrackingService()

        mock_detection = {
            "class_name": "UPS package",
            "confidence": 0.78,
            "bbox": {"x1": 0.2, "y1": 0.3, "x2": 0.5, "y2": 0.6},
            "class_id": 3,
        }

        with patch.object(service, "_run_yolo_world_detection", return_value=[mock_detection]):
            result = await service.detect_packages(mock_yolo_world_model, MagicMock())

        assert "confidence" in result.detections[0]
        assert isinstance(result.detections[0]["confidence"], float)

    @pytest.mark.asyncio
    async def test_package_detection_filters_low_confidence(self, mock_yolo_world_model) -> None:
        """Test package detection filters detections below 0.35 confidence threshold."""
        from backend.services.package_tracking_service import PackageTrackingService

        service = PackageTrackingService()

        mock_detections = [
            {
                "class_name": "package",
                "confidence": 0.25,  # Below threshold
                "bbox": {"x1": 0.1, "y1": 0.2, "x2": 0.3, "y2": 0.4},
                "class_id": 0,
            },
            {
                "class_name": "cardboard box",
                "confidence": 0.45,  # Above threshold
                "bbox": {"x1": 0.4, "y1": 0.5, "x2": 0.6, "y2": 0.7},
                "class_id": 1,
            },
        ]

        with patch.object(service, "_run_yolo_world_detection", return_value=mock_detections):
            result = await service.detect_packages(mock_yolo_world_model, MagicMock())

        # Should only include the detection above threshold
        assert len(result.detections) == 1
        assert result.detections[0]["confidence"] >= 0.35

    @pytest.mark.asyncio
    async def test_no_packages_detected(self, mock_yolo_world_model) -> None:
        """Test handling when no packages are detected."""
        from backend.services.package_tracking_service import PackageTrackingService

        service = PackageTrackingService()

        with patch.object(service, "_run_yolo_world_detection", return_value=[]):
            result = await service.detect_packages(mock_yolo_world_model, MagicMock())

        assert len(result.detections) == 0
        assert result.has_packages is False


# =============================================================================
# Package State Tracking Tests
# =============================================================================


class TestPackageStateTracking:
    """Tests for package state tracking across frames."""

    @pytest.mark.asyncio
    async def test_package_appears_in_zone_state_delivered(self) -> None:
        """Test package appearing in zone changes state to 'delivered'."""
        from backend.services.package_tracking_service import PackageState, PackageTrackingService

        service = PackageTrackingService()

        detection = {
            "class_name": "cardboard delivery package",
            "confidence": 0.72,
            "bbox": {"x1": 0.3, "y1": 0.4, "x2": 0.5, "y2": 0.7},
        }

        zone = MagicMock()
        zone.id = "delivery_zone_001"

        result = await service.process_detection(
            detection=detection,
            camera_id="front_door",
            zone=zone,
            frame_timestamp=datetime.now(UTC),
        )

        assert result.state == PackageState.DELIVERED

    @pytest.mark.asyncio
    async def test_package_disappears_from_zone_state_removed(self) -> None:
        """Test package disappearing from zone changes state to 'removed'."""
        from backend.services.package_tracking_service import PackageState, PackageTrackingService

        service = PackageTrackingService()

        # First, add a package
        detection = {
            "class_name": "cardboard delivery package",
            "confidence": 0.72,
            "bbox": {"x1": 0.3, "y1": 0.4, "x2": 0.5, "y2": 0.7},
        }

        zone = MagicMock()
        zone.id = "delivery_zone_001"

        await service.process_detection(
            detection=detection,
            camera_id="front_door",
            zone=zone,
            frame_timestamp=datetime.now(UTC),
        )

        # Then, mark it as no longer visible
        result = await service.mark_package_removed(
            camera_id="front_door",
            zone_id="delivery_zone_001",
            removal_timestamp=datetime.now(UTC),
        )

        assert result is not None
        assert result.state == PackageState.REMOVED

    @pytest.mark.asyncio
    async def test_package_state_persists_across_frames(self) -> None:
        """Test package state persists across consecutive frames."""
        from backend.services.package_tracking_service import PackageState, PackageTrackingService

        service = PackageTrackingService()

        detection = {
            "class_name": "Amazon box",
            "confidence": 0.68,
            "bbox": {"x1": 0.2, "y1": 0.3, "x2": 0.4, "y2": 0.6},
        }

        zone = MagicMock()
        zone.id = "delivery_zone_001"

        # Process same package in multiple frames
        for i in range(5):
            result = await service.process_detection(
                detection=detection,
                camera_id="front_door",
                zone=zone,
                frame_timestamp=datetime.now(UTC) + timedelta(seconds=i),
            )

        # Package should still be tracked with DELIVERED/PRESENT state
        assert result.state in (PackageState.DELIVERED, PackageState.PRESENT)

        # Verify single package is tracked (not creating duplicates)
        tracked = service.get_tracked_packages("front_door")
        assert len(tracked) == 1

    @pytest.mark.asyncio
    async def test_multiple_packages_tracked_independently(self) -> None:
        """Test multiple packages are tracked independently."""
        from backend.services.package_tracking_service import PackageTrackingService

        service = PackageTrackingService()

        detections = [
            {
                "class_name": "Amazon box",
                "confidence": 0.72,
                "bbox": {"x1": 0.1, "y1": 0.2, "x2": 0.3, "y2": 0.4},
            },
            {
                "class_name": "FedEx package",
                "confidence": 0.65,
                "bbox": {"x1": 0.5, "y1": 0.2, "x2": 0.7, "y2": 0.4},
            },
            {
                "class_name": "UPS package",
                "confidence": 0.78,
                "bbox": {"x1": 0.1, "y1": 0.6, "x2": 0.3, "y2": 0.8},
            },
        ]

        zone = MagicMock()
        zone.id = "delivery_zone_001"

        for detection in detections:
            await service.process_detection(
                detection=detection,
                camera_id="front_door",
                zone=zone,
                frame_timestamp=datetime.now(UTC),
            )

        tracked = service.get_tracked_packages("front_door")
        assert len(tracked) == 3


# =============================================================================
# Package Theft Detection Tests
# =============================================================================


class TestPackageTheftDetection:
    """Tests for package theft detection logic."""

    @pytest.mark.asyncio
    async def test_package_removed_with_household_member_no_alert(self) -> None:
        """Test package removed when household member present does NOT trigger alert."""
        from backend.services.package_tracking_service import PackageState, PackageTrackingService

        service = PackageTrackingService()

        # Setup: Package delivered
        detection = {
            "class_name": "cardboard delivery package",
            "confidence": 0.72,
            "bbox": {"x1": 0.3, "y1": 0.4, "x2": 0.5, "y2": 0.7},
        }

        zone = MagicMock()
        zone.id = "delivery_zone_001"

        await service.process_detection(
            detection=detection,
            camera_id="front_door",
            zone=zone,
            frame_timestamp=datetime.now(UTC),
        )

        # Package removed WITH household member present
        result = await service.check_removal_context(
            camera_id="front_door",
            zone_id="delivery_zone_001",
            household_member_present=True,
            removal_timestamp=datetime.now(UTC),
        )

        # Should be marked as removed but NOT suspicious
        assert result.state == PackageState.REMOVED
        assert result.is_suspicious is False

    @pytest.mark.asyncio
    async def test_package_removed_without_household_member_triggers_alert(self) -> None:
        """Test package removed when NO household member present triggers alert."""
        from backend.services.package_tracking_service import PackageState, PackageTrackingService

        service = PackageTrackingService()

        # Setup: Package delivered
        detection = {
            "class_name": "cardboard delivery package",
            "confidence": 0.72,
            "bbox": {"x1": 0.3, "y1": 0.4, "x2": 0.5, "y2": 0.7},
        }

        zone = MagicMock()
        zone.id = "delivery_zone_001"

        await service.process_detection(
            detection=detection,
            camera_id="front_door",
            zone=zone,
            frame_timestamp=datetime.now(UTC),
        )

        # Package removed WITHOUT household member present
        result = await service.check_removal_context(
            camera_id="front_door",
            zone_id="delivery_zone_001",
            household_member_present=False,
            removal_timestamp=datetime.now(UTC),
        )

        # Should be marked as SUSPICIOUS_REMOVAL
        assert result.state == PackageState.SUSPICIOUS_REMOVAL
        assert result.is_suspicious is True

    @pytest.mark.asyncio
    async def test_delivery_person_present_during_removal_legitimate(self) -> None:
        """Test package removed by delivery person (legitimate pickup/redelivery)."""
        from backend.services.package_tracking_service import PackageTrackingService

        service = PackageTrackingService()

        # Setup: Package delivered
        detection = {
            "class_name": "Amazon box",
            "confidence": 0.68,
            "bbox": {"x1": 0.2, "y1": 0.3, "x2": 0.4, "y2": 0.6},
        }

        zone = MagicMock()
        zone.id = "delivery_zone_001"

        await service.process_detection(
            detection=detection,
            camera_id="front_door",
            zone=zone,
            frame_timestamp=datetime.now(UTC),
        )

        # Package removed with delivery person present
        result = await service.check_removal_context(
            camera_id="front_door",
            zone_id="delivery_zone_001",
            household_member_present=False,
            delivery_person_present=True,
            removal_timestamp=datetime.now(UTC),
        )

        # Should NOT be suspicious (delivery person pickup)
        assert result.is_suspicious is False


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestPackageTrackingEdgeCases:
    """Tests for edge cases in package tracking."""

    @pytest.mark.asyncio
    async def test_multiple_packages_in_delivery_zone(self) -> None:
        """Test handling multiple packages in the same delivery zone."""
        from backend.services.package_tracking_service import PackageTrackingService

        service = PackageTrackingService()

        detections = [
            {
                "class_name": "Amazon box",
                "confidence": 0.72,
                "bbox": {"x1": 0.1, "y1": 0.4, "x2": 0.25, "y2": 0.6},
            },
            {
                "class_name": "FedEx package",
                "confidence": 0.65,
                "bbox": {"x1": 0.3, "y1": 0.4, "x2": 0.45, "y2": 0.6},
            },
        ]

        zone = MagicMock()
        zone.id = "delivery_zone_001"

        for detection in detections:
            await service.process_detection(
                detection=detection,
                camera_id="front_door",
                zone=zone,
                frame_timestamp=datetime.now(UTC),
            )

        tracked = service.get_tracked_packages("front_door", zone_id="delivery_zone_001")
        assert len(tracked) == 2

    @pytest.mark.asyncio
    async def test_package_partially_occluded(self) -> None:
        """Test handling package that becomes partially occluded."""
        from backend.services.package_tracking_service import PackageTrackingService

        service = PackageTrackingService()

        # Initial detection with high confidence
        initial_detection = {
            "class_name": "cardboard delivery package",
            "confidence": 0.85,
            "bbox": {"x1": 0.3, "y1": 0.4, "x2": 0.5, "y2": 0.7},
        }

        zone = MagicMock()
        zone.id = "delivery_zone_001"

        await service.process_detection(
            detection=initial_detection,
            camera_id="front_door",
            zone=zone,
            frame_timestamp=datetime.now(UTC),
        )

        # Later detection with lower confidence (partially occluded)
        occluded_detection = {
            "class_name": "cardboard delivery package",
            "confidence": 0.42,  # Lower but still above threshold
            "bbox": {"x1": 0.35, "y1": 0.45, "x2": 0.5, "y2": 0.7},  # Slightly different bbox
        }

        result = await service.process_detection(
            detection=occluded_detection,
            camera_id="front_door",
            zone=zone,
            frame_timestamp=datetime.now(UTC) + timedelta(seconds=5),
        )

        # Should still be tracked as the same package
        tracked = service.get_tracked_packages("front_door")
        assert len(tracked) == 1

    @pytest.mark.asyncio
    async def test_package_moves_within_zone_no_removal(self) -> None:
        """Test package moving within zone (e.g., wind) does not trigger removal."""
        from backend.services.package_tracking_service import PackageState, PackageTrackingService

        service = PackageTrackingService()

        # Initial position
        detection_1 = {
            "class_name": "cardboard delivery package",
            "confidence": 0.72,
            "bbox": {"x1": 0.3, "y1": 0.4, "x2": 0.5, "y2": 0.7},
        }

        zone = MagicMock()
        zone.id = "delivery_zone_001"

        await service.process_detection(
            detection=detection_1,
            camera_id="front_door",
            zone=zone,
            frame_timestamp=datetime.now(UTC),
        )

        # Moved position (still within zone)
        detection_2 = {
            "class_name": "cardboard delivery package",
            "confidence": 0.70,
            "bbox": {"x1": 0.35, "y1": 0.45, "x2": 0.55, "y2": 0.75},  # Slightly shifted
        }

        result = await service.process_detection(
            detection=detection_2,
            camera_id="front_door",
            zone=zone,
            frame_timestamp=datetime.now(UTC) + timedelta(seconds=10),
        )

        # Should NOT be marked as removed
        assert result.state != PackageState.REMOVED
        assert result.state in (PackageState.DELIVERED, PackageState.PRESENT)

    @pytest.mark.asyncio
    async def test_package_not_in_any_zone(self) -> None:
        """Test handling package detected outside of any defined zone."""
        from backend.services.package_tracking_service import PackageTrackingService

        service = PackageTrackingService()

        detection = {
            "class_name": "cardboard delivery package",
            "confidence": 0.72,
            "bbox": {"x1": 0.3, "y1": 0.4, "x2": 0.5, "y2": 0.7},
        }

        result = await service.process_detection(
            detection=detection,
            camera_id="front_door",
            zone=None,  # No zone
            frame_timestamp=datetime.now(UTC),
        )

        # Should still be tracked, but without zone assignment
        assert result.zone_id is None


# =============================================================================
# Service Lifecycle Tests
# =============================================================================


class TestPackageTrackingServiceLifecycle:
    """Tests for PackageTrackingService lifecycle management."""

    def test_get_package_tracking_service_singleton(self) -> None:
        """Test get_package_tracking_service returns singleton."""
        from backend.services.package_tracking_service import get_package_tracking_service

        service1 = get_package_tracking_service()
        service2 = get_package_tracking_service()

        assert service1 is service2

    def test_service_has_cleanup_method(self) -> None:
        """Test PackageTrackingService has cleanup method for old packages."""
        from backend.services.package_tracking_service import PackageTrackingService

        service = PackageTrackingService()
        assert hasattr(service, "cleanup_old_packages")
        assert callable(service.cleanup_old_packages)

    @pytest.mark.asyncio
    async def test_cleanup_removes_old_packages(self) -> None:
        """Test cleanup removes packages older than retention period."""
        from backend.services.package_tracking_service import PackageTrackingService

        service = PackageTrackingService()

        # Add a package with old timestamp
        old_detection = {
            "class_name": "cardboard delivery package",
            "confidence": 0.72,
            "bbox": {"x1": 0.3, "y1": 0.4, "x2": 0.5, "y2": 0.7},
        }

        zone = MagicMock()
        zone.id = "delivery_zone_001"

        # Simulate old package (25 hours ago)
        old_timestamp = datetime.now(UTC) - timedelta(hours=25)

        await service.process_detection(
            detection=old_detection,
            camera_id="front_door",
            zone=zone,
            frame_timestamp=old_timestamp,
        )

        # Run cleanup with 24-hour retention
        await service.cleanup_old_packages(retention_hours=24)

        # Old package should be removed
        tracked = service.get_tracked_packages("front_door")
        assert len(tracked) == 0


# =============================================================================
# Integration with Model Zoo Tests
# =============================================================================


class TestPackageTrackingModelZooIntegration:
    """Tests for integration with Model Zoo for YOLO-World loading."""

    def test_yolo_world_package_category_in_prompts(self) -> None:
        """Test YOLO-World package prompts are properly configured."""
        from backend.services.yolo_world_loader import YOLO_WORLD_PROMPTS_V2

        assert "packages" in YOLO_WORLD_PROMPTS_V2
        config = YOLO_WORLD_PROMPTS_V2["packages"]

        assert "prompts" in config
        assert "threshold" in config
        assert config["threshold"] == 0.35

    def test_package_prompts_include_expected_items(self) -> None:
        """Test package prompts include common delivery package types."""
        from backend.services.yolo_world_loader import YOLO_WORLD_PROMPTS_V2

        package_prompts = YOLO_WORLD_PROMPTS_V2["packages"]["prompts"]

        expected_prompts = [
            "cardboard delivery package",
            "Amazon shipping box",
            "FedEx package",
            "UPS package",
        ]

        for prompt in expected_prompts:
            assert prompt in package_prompts, f"Missing expected prompt: {prompt}"


# =============================================================================
# Property-Based Tests
# =============================================================================


class TestPackageTrackingProperties:
    """Property-based tests for PackageTrackingService."""

    @given(confidence=confidence_scores)
    @settings(max_examples=50)
    def test_confidence_threshold_filtering(self, confidence: float) -> None:
        """Property: Detections below 0.35 are always filtered."""
        from backend.services.package_tracking_service import PackageTrackingService

        service = PackageTrackingService()
        threshold = 0.35

        detection = {
            "class_name": "package",
            "confidence": confidence,
            "bbox": {"x1": 0.3, "y1": 0.4, "x2": 0.5, "y2": 0.7},
        }

        should_include = confidence >= threshold
        result = service._should_include_detection(detection)

        assert result == should_include

    @given(x1=normalized_coords, y1=normalized_coords, x2=normalized_coords, y2=normalized_coords)
    @settings(max_examples=50, deadline=None)
    def test_bbox_coordinates_valid(self, x1: float, y1: float, x2: float, y2: float) -> None:
        """Property: Bounding box coordinates are always in 0-1 range."""
        from backend.services.package_tracking_service import PackageTrackingService

        service = PackageTrackingService()

        bbox = {"x1": x1, "y1": y1, "x2": x2, "y2": y2}

        # Should be valid if all coords in range
        is_valid = service._is_valid_bbox(bbox)

        # Bbox is valid if all coords in 0-1 range
        expected_valid = all(0.0 <= v <= 1.0 for v in bbox.values())
        assert is_valid == expected_valid


# =============================================================================
# Serialization Tests
# =============================================================================


class TestPackageTrackingSerialization:
    """Tests for serialization of package tracking data."""

    def test_tracked_package_to_dict(self) -> None:
        """Test TrackedPackage can be serialized to dict."""
        from backend.services.package_tracking_service import PackageState, TrackedPackage

        package = TrackedPackage(
            id="pkg_001",
            bbox={"x1": 0.3, "y1": 0.4, "x2": 0.5, "y2": 0.7},
            confidence=0.72,
            state=PackageState.DELIVERED,
            first_seen=datetime.now(UTC),
            last_seen=datetime.now(UTC),
            zone_id="delivery_zone_001",
            camera_id="front_door",
        )

        d = package.to_dict()

        assert d["id"] == "pkg_001"
        assert d["state"] == "delivered"
        assert d["confidence"] == 0.72
        assert "bbox" in d
        assert "first_seen" in d
        assert "last_seen" in d

    def test_package_detection_result_to_dict(self) -> None:
        """Test PackageDetectionResult can be serialized to dict."""
        from backend.services.package_tracking_service import PackageDetectionResult

        result = PackageDetectionResult(
            detections=[
                {
                    "class_name": "cardboard delivery package",
                    "confidence": 0.72,
                    "bbox": {"x1": 0.3, "y1": 0.4, "x2": 0.5, "y2": 0.7},
                }
            ],
            processing_time_ms=45.5,
            has_packages=True,
        )

        d = result.to_dict()

        assert d["has_packages"] is True
        assert d["processing_time_ms"] == 45.5
        assert len(d["detections"]) == 1
