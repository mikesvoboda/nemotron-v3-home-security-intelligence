"""Unit tests for entity recognition summary service.

Tests cover:
- Face detection aggregation (known vs unknown)
- Vehicle plate matching against household vehicles
- Time window filtering for summary stats

Implements NEM-5394: Entity Recognition Summary - Backend Service

TDD: Tests written BEFORE implementation
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.entity_recognition_service import (
    EntityRecognitionService,
    EntityRecognitionStats,
    PersonStats,
    VehicleStats,
)

pytestmark = pytest.mark.unit


# =============================================================================
# PersonStats Tests
# =============================================================================


class TestPersonStats:
    """Tests for PersonStats dataclass."""

    def test_total_persons_calculation(self) -> None:
        """Test that total_persons returns sum of known and unknown."""
        stats = PersonStats(known=3, unknown=2)
        assert stats.total_persons == 5

    def test_total_persons_with_zero_values(self) -> None:
        """Test total_persons when both values are zero."""
        stats = PersonStats(known=0, unknown=0)
        assert stats.total_persons == 0

    def test_breakdown_text_with_both(self) -> None:
        """Test breakdown_text with both known and unknown persons."""
        stats = PersonStats(known=3, unknown=2)
        assert stats.breakdown_text == "3 known, 2 unknown"

    def test_breakdown_text_known_only(self) -> None:
        """Test breakdown_text with only known persons."""
        stats = PersonStats(known=5, unknown=0)
        assert stats.breakdown_text == "5 known"

    def test_breakdown_text_unknown_only(self) -> None:
        """Test breakdown_text with only unknown persons."""
        stats = PersonStats(known=0, unknown=7)
        assert stats.breakdown_text == "7 unknown"

    def test_breakdown_text_empty(self) -> None:
        """Test breakdown_text with no persons."""
        stats = PersonStats(known=0, unknown=0)
        assert stats.breakdown_text == "No persons detected"


# =============================================================================
# VehicleStats Tests
# =============================================================================


class TestVehicleStats:
    """Tests for VehicleStats dataclass."""

    def test_total_vehicles_calculation(self) -> None:
        """Test that total_vehicles returns sum of known and unknown."""
        stats = VehicleStats(known=4, unknown=1)
        assert stats.total_vehicles == 5

    def test_total_vehicles_with_zero_values(self) -> None:
        """Test total_vehicles when both values are zero."""
        stats = VehicleStats(known=0, unknown=0)
        assert stats.total_vehicles == 0

    def test_breakdown_text_with_both(self) -> None:
        """Test breakdown_text with both known and unknown vehicles."""
        stats = VehicleStats(known=2, unknown=3)
        assert stats.breakdown_text == "2 known, 3 unknown"

    def test_breakdown_text_known_only(self) -> None:
        """Test breakdown_text with only known vehicles."""
        stats = VehicleStats(known=4, unknown=0)
        assert stats.breakdown_text == "4 known"

    def test_breakdown_text_unknown_only(self) -> None:
        """Test breakdown_text with only unknown vehicles."""
        stats = VehicleStats(known=0, unknown=6)
        assert stats.breakdown_text == "6 unknown"

    def test_breakdown_text_empty(self) -> None:
        """Test breakdown_text with no vehicles."""
        stats = VehicleStats(known=0, unknown=0)
        assert stats.breakdown_text == "No vehicles detected"


# =============================================================================
# EntityRecognitionStats Tests
# =============================================================================


class TestEntityRecognitionStats:
    """Tests for EntityRecognitionStats dataclass."""

    def test_to_dict(self) -> None:
        """Test conversion to dictionary for API response."""
        stats = EntityRecognitionStats(
            persons=PersonStats(known=3, unknown=2),
            vehicles=VehicleStats(known=1, unknown=4),
            window_start=datetime(2026, 2, 3, 10, 0, 0, tzinfo=UTC),
            window_end=datetime(2026, 2, 3, 11, 0, 0, tzinfo=UTC),
        )

        result = stats.to_dict()

        assert result["persons"]["known"] == 3
        assert result["persons"]["unknown"] == 2
        assert result["persons"]["total"] == 5
        assert result["persons"]["breakdown"] == "3 known, 2 unknown"

        assert result["vehicles"]["known"] == 1
        assert result["vehicles"]["unknown"] == 4
        assert result["vehicles"]["total"] == 5
        assert result["vehicles"]["breakdown"] == "1 known, 4 unknown"

        assert result["window_start"] == "2026-02-03T10:00:00+00:00"
        assert result["window_end"] == "2026-02-03T11:00:00+00:00"


# =============================================================================
# EntityRecognitionService Tests
# =============================================================================


class TestEntityRecognitionService:
    """Tests for EntityRecognitionService."""

    @pytest.fixture
    def service(self) -> EntityRecognitionService:
        """Create service instance."""
        return EntityRecognitionService()

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create mock database session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        return session

    async def test_get_face_stats_counts_known_and_unknown(
        self,
        service: EntityRecognitionService,
        mock_session: AsyncMock,
    ) -> None:
        """Test that face stats correctly counts known and unknown faces."""
        # Mock query result: [(is_unknown=False, count=3), (is_unknown=True, count=2)]
        mock_result = MagicMock()
        mock_result.all.return_value = [
            (False, 3),  # known persons
            (True, 2),  # unknown persons
        ]
        mock_session.execute.return_value = mock_result

        window_start = datetime(2026, 2, 3, 10, 0, 0, tzinfo=UTC)
        window_end = datetime(2026, 2, 3, 11, 0, 0, tzinfo=UTC)

        stats = await service.get_face_stats(mock_session, window_start, window_end)

        assert stats.known == 3
        assert stats.unknown == 2

    async def test_get_face_stats_handles_empty_results(
        self,
        service: EntityRecognitionService,
        mock_session: AsyncMock,
    ) -> None:
        """Test that face stats handles no face detections gracefully."""
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute.return_value = mock_result

        window_start = datetime(2026, 2, 3, 10, 0, 0, tzinfo=UTC)
        window_end = datetime(2026, 2, 3, 11, 0, 0, tzinfo=UTC)

        stats = await service.get_face_stats(mock_session, window_start, window_end)

        assert stats.known == 0
        assert stats.unknown == 0

    async def test_get_vehicle_stats_matches_plates_against_household(
        self,
        service: EntityRecognitionService,
        mock_session: AsyncMock,
    ) -> None:
        """Test that vehicle stats matches plates against household vehicles."""
        # First query: household vehicle plates
        household_result = MagicMock()
        household_result.scalars.return_value.all.return_value = ["ABC123", "XYZ789"]

        # Second query: detected plates in time window
        plates_result = MagicMock()
        plates_result.scalars.return_value.all.return_value = [
            "ABC123",  # matches household
            "ABC123",  # duplicate match
            "UNKNOWN1",  # no match
            "XYZ789",  # matches household
            "UNKNOWN2",  # no match
        ]

        mock_session.execute.side_effect = [household_result, plates_result]

        window_start = datetime(2026, 2, 3, 10, 0, 0, tzinfo=UTC)
        window_end = datetime(2026, 2, 3, 11, 0, 0, tzinfo=UTC)

        stats = await service.get_vehicle_stats(mock_session, window_start, window_end)

        # 2 unique known plates (ABC123, XYZ789), 2 unique unknown (UNKNOWN1, UNKNOWN2)
        assert stats.known == 2
        assert stats.unknown == 2

    async def test_get_vehicle_stats_handles_no_household_vehicles(
        self,
        service: EntityRecognitionService,
        mock_session: AsyncMock,
    ) -> None:
        """Test vehicle stats when no household vehicles are registered."""
        # No household vehicles
        household_result = MagicMock()
        household_result.scalars.return_value.all.return_value = []

        # Some detected plates
        plates_result = MagicMock()
        plates_result.scalars.return_value.all.return_value = ["PLATE1", "PLATE2"]

        mock_session.execute.side_effect = [household_result, plates_result]

        window_start = datetime(2026, 2, 3, 10, 0, 0, tzinfo=UTC)
        window_end = datetime(2026, 2, 3, 11, 0, 0, tzinfo=UTC)

        stats = await service.get_vehicle_stats(mock_session, window_start, window_end)

        assert stats.known == 0
        assert stats.unknown == 2

    async def test_get_vehicle_stats_handles_no_plate_reads(
        self,
        service: EntityRecognitionService,
        mock_session: AsyncMock,
    ) -> None:
        """Test vehicle stats when no plates were detected."""
        household_result = MagicMock()
        household_result.scalars.return_value.all.return_value = ["ABC123"]

        plates_result = MagicMock()
        plates_result.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [household_result, plates_result]

        window_start = datetime(2026, 2, 3, 10, 0, 0, tzinfo=UTC)
        window_end = datetime(2026, 2, 3, 11, 0, 0, tzinfo=UTC)

        stats = await service.get_vehicle_stats(mock_session, window_start, window_end)

        assert stats.known == 0
        assert stats.unknown == 0

    async def test_get_vehicle_stats_case_insensitive_matching(
        self,
        service: EntityRecognitionService,
        mock_session: AsyncMock,
    ) -> None:
        """Test that plate matching is case-insensitive."""
        household_result = MagicMock()
        household_result.scalars.return_value.all.return_value = ["abc123"]

        plates_result = MagicMock()
        plates_result.scalars.return_value.all.return_value = ["ABC123", "abc123"]

        mock_session.execute.side_effect = [household_result, plates_result]

        window_start = datetime(2026, 2, 3, 10, 0, 0, tzinfo=UTC)
        window_end = datetime(2026, 2, 3, 11, 0, 0, tzinfo=UTC)

        stats = await service.get_vehicle_stats(mock_session, window_start, window_end)

        # Both should match (case-insensitive), but count unique
        assert stats.known == 1
        assert stats.unknown == 0

    async def test_get_summary_stats_combines_face_and_vehicle(
        self,
        service: EntityRecognitionService,
        mock_session: AsyncMock,
    ) -> None:
        """Test that get_summary_stats combines face and vehicle stats."""
        with (
            patch.object(
                service,
                "get_face_stats",
                return_value=PersonStats(known=3, unknown=2),
            ) as mock_face,
            patch.object(
                service,
                "get_vehicle_stats",
                return_value=VehicleStats(known=1, unknown=4),
            ) as mock_vehicle,
        ):
            window_start = datetime(2026, 2, 3, 10, 0, 0, tzinfo=UTC)
            window_end = datetime(2026, 2, 3, 11, 0, 0, tzinfo=UTC)

            stats = await service.get_summary_stats(mock_session, window_start, window_end)

            assert stats.persons.known == 3
            assert stats.persons.unknown == 2
            assert stats.vehicles.known == 1
            assert stats.vehicles.unknown == 4
            assert stats.window_start == window_start
            assert stats.window_end == window_end

            mock_face.assert_called_once_with(mock_session, window_start, window_end)
            mock_vehicle.assert_called_once_with(mock_session, window_start, window_end)

    async def test_get_hourly_stats_uses_correct_window(
        self,
        service: EntityRecognitionService,
        mock_session: AsyncMock,
    ) -> None:
        """Test that get_hourly_stats uses a 1-hour window."""
        with patch.object(
            service,
            "get_summary_stats",
            return_value=EntityRecognitionStats(
                persons=PersonStats(known=0, unknown=0),
                vehicles=VehicleStats(known=0, unknown=0),
                window_start=datetime.now(UTC),
                window_end=datetime.now(UTC),
            ),
        ) as mock_summary:
            await service.get_hourly_stats(mock_session)

            # Verify the time window is approximately 1 hour
            call_args = mock_summary.call_args
            window_start = call_args[0][1]
            window_end = call_args[0][2]
            delta = window_end - window_start

            # Should be within a few seconds of 1 hour
            assert timedelta(minutes=59) < delta < timedelta(hours=1, seconds=5)
