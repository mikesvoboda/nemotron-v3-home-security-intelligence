"""Unit tests for orphaned detection recovery logic."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.batch_aggregator import (
    ORPHAN_MIN_AGE_MINUTES,
    ORPHAN_RECOVERY_LIMIT,
    recover_orphaned_detections,
)


def _make_detection(
    detection_id: int,
    camera_id: str,
    minutes_ago: int = 10,
) -> MagicMock:
    """Create a mock Detection row."""
    det = MagicMock()
    det.id = detection_id
    det.camera_id = camera_id
    det.file_path = f"/images/{camera_id}/frame_{detection_id}.jpg"
    det.confidence = 0.85
    det.object_type = "person"
    det.detected_at = datetime.now(UTC) - timedelta(minutes=minutes_ago)
    return det


def _mock_session_ctx(mock_session: AsyncMock) -> AsyncMock:
    """Build async context manager that yields mock_session."""
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    return mock_ctx


class TestRecoverOrphanedDetections:
    """Tests for the recover_orphaned_detections function."""

    @pytest.mark.asyncio
    async def test_no_orphans_returns_zero_and_no_log(self) -> None:
        """When no orphans exist, the function returns 0 silently."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_aggregator = AsyncMock()

        with patch(
            "backend.core.database.get_session",
            return_value=_mock_session_ctx(mock_session),
        ):
            count = await recover_orphaned_detections(mock_aggregator)

        assert count == 0
        mock_aggregator.add_detection.assert_not_called()

    @pytest.mark.asyncio
    async def test_recovers_orphans_across_cameras(self) -> None:
        """Orphaned detections from multiple cameras are re-injected."""
        orphans = [
            _make_detection(1, "cam_front", minutes_ago=10),
            _make_detection(2, "cam_front", minutes_ago=8),
            _make_detection(3, "cam_back", minutes_ago=5),
        ]

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = orphans
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_aggregator = AsyncMock()
        mock_aggregator.add_detection = AsyncMock(return_value="batch-abc12345")

        with patch(
            "backend.core.database.get_session",
            return_value=_mock_session_ctx(mock_session),
        ):
            count = await recover_orphaned_detections(mock_aggregator)

        assert count == 3
        assert mock_aggregator.add_detection.call_count == 3

        # Verify each detection was re-injected with correct args
        calls = mock_aggregator.add_detection.call_args_list
        assert calls[0].kwargs["camera_id"] == "cam_front"
        assert calls[0].kwargs["detection_id"] == 1
        assert calls[2].kwargs["camera_id"] == "cam_back"
        assert calls[2].kwargs["detection_id"] == 3

    @pytest.mark.asyncio
    async def test_partial_failure_continues(self) -> None:
        """If one detection fails to re-inject, others still proceed."""
        orphans = [
            _make_detection(1, "cam_front"),
            _make_detection(2, "cam_front"),
        ]

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = orphans
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_aggregator = AsyncMock()
        # First call raises, second succeeds
        mock_aggregator.add_detection = AsyncMock(
            side_effect=[RuntimeError("Redis down"), "batch-abc12345"]
        )

        with patch(
            "backend.core.database.get_session",
            return_value=_mock_session_ctx(mock_session),
        ):
            count = await recover_orphaned_detections(mock_aggregator)

        # Only the second one succeeded
        assert count == 1
        assert mock_aggregator.add_detection.call_count == 2

    @pytest.mark.asyncio
    async def test_database_error_returns_zero(self) -> None:
        """If the database query itself fails, return 0 gracefully."""
        mock_aggregator = AsyncMock()

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(side_effect=RuntimeError("DB offline"))
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "backend.core.database.get_session",
            return_value=mock_ctx,
        ):
            count = await recover_orphaned_detections(mock_aggregator)

        assert count == 0
        mock_aggregator.add_detection.assert_not_called()

    def test_constants_are_reasonable(self) -> None:
        """Verify recovery constants match documented constraints."""
        assert ORPHAN_RECOVERY_LIMIT == 500
        assert ORPHAN_MIN_AGE_MINUTES == 3
