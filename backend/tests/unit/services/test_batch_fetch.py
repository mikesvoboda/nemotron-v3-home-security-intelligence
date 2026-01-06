"""Unit tests for batch fetching service.

These tests verify the batch_fetch_detections function that solves N+1 query problems
by batching detection ID fetches with configurable batch sizes.

Tests follow TDD approach - written before implementation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.models.detection import Detection
from backend.services.batch_fetch import (
    DEFAULT_BATCH_SIZE,
    MAX_BATCH_SIZE,
    MIN_BATCH_SIZE,
    batch_fetch_detections,
    batch_fetch_detections_by_ids,
)


class TestBatchFetchConfig:
    """Tests for batch fetch configuration constants."""

    def test_default_batch_size_is_reasonable(self) -> None:
        """Default batch size should be between 100 and 500 for optimal performance."""
        assert MIN_BATCH_SIZE <= DEFAULT_BATCH_SIZE <= MAX_BATCH_SIZE
        assert 100 <= DEFAULT_BATCH_SIZE <= 500

    def test_min_batch_size_is_positive(self) -> None:
        """Minimum batch size must be at least 1."""
        assert MIN_BATCH_SIZE >= 1

    def test_max_batch_size_has_limit(self) -> None:
        """Maximum batch size should be capped to prevent query timeouts."""
        assert MAX_BATCH_SIZE <= 10000


class TestBatchFetchDetections:
    """Tests for batch_fetch_detections function."""

    @pytest.mark.asyncio
    async def test_empty_ids_returns_empty_list(self) -> None:
        """Fetching with empty ID list should return empty list without querying."""
        mock_session = AsyncMock(spec=["execute"])

        result = await batch_fetch_detections(mock_session, [])

        assert result == []
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_single_id_fetches_single_detection(self) -> None:
        """Fetching single ID should return single detection."""
        mock_session = AsyncMock()
        mock_detection = MagicMock(spec=Detection)
        mock_detection.id = 1

        # Mock the query execution
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_detection]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await batch_fetch_detections(mock_session, [1])

        assert len(result) == 1
        assert result[0].id == 1
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_ids_within_batch_size_single_query(self) -> None:
        """IDs within batch size should be fetched in single query."""
        mock_session = AsyncMock()
        mock_detections = [MagicMock(spec=Detection, id=i) for i in range(10)]

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_detections
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        ids = list(range(10))
        result = await batch_fetch_detections(mock_session, ids, batch_size=100)

        assert len(result) == 10
        # Only one query should be made when IDs fit within batch size
        assert mock_session.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_ids_exceeding_batch_size_multiple_queries(self) -> None:
        """IDs exceeding batch size should result in multiple batched queries."""
        from datetime import timedelta

        mock_session = AsyncMock()
        now = datetime.now(UTC)

        # Create mock detections for two batches with proper detected_at values
        batch1_detections = [
            MagicMock(spec=Detection, id=i, detected_at=now + timedelta(minutes=i))
            for i in range(5)
        ]
        batch2_detections = [
            MagicMock(spec=Detection, id=i, detected_at=now + timedelta(minutes=i))
            for i in range(5, 10)
        ]

        call_count = 0

        def mock_execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_scalars = MagicMock()
            if call_count == 1:
                mock_scalars.all.return_value = batch1_detections
            else:
                mock_scalars.all.return_value = batch2_detections
            mock_result = MagicMock()
            mock_result.scalars.return_value = mock_scalars
            return mock_result

        mock_session.execute.side_effect = mock_execute_side_effect

        ids = list(range(10))
        result = await batch_fetch_detections(mock_session, ids, batch_size=5)

        assert len(result) == 10
        # Two batches should be made with batch_size=5
        assert mock_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_preserves_order_by_detection_time(self) -> None:
        """Results should be ordered by detected_at in ascending order by default."""
        mock_session = AsyncMock()

        # Create detections with different timestamps
        now = datetime.now(UTC)
        mock_detections = [
            MagicMock(spec=Detection, id=2, detected_at=now),
            MagicMock(spec=Detection, id=1, detected_at=now),
            MagicMock(spec=Detection, id=3, detected_at=now),
        ]

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_detections
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await batch_fetch_detections(mock_session, [1, 2, 3])

        # The function should execute with ORDER BY clause
        assert len(result) == 3
        assert mock_session.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_custom_batch_size_is_honored(self) -> None:
        """Custom batch size parameter should be used for splitting queries."""
        from datetime import timedelta

        mock_session = AsyncMock()
        now = datetime.now(UTC)

        # Create mock detections with proper detected_at values
        mock_detections = [
            MagicMock(spec=Detection, id=i, detected_at=now + timedelta(minutes=i))
            for i in range(30)
        ]

        call_results = [
            mock_detections[0:10],
            mock_detections[10:20],
            mock_detections[20:30],
        ]
        call_idx = 0

        def mock_execute(*args, **kwargs):
            nonlocal call_idx
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = call_results[call_idx]
            call_idx += 1
            mock_result = MagicMock()
            mock_result.scalars.return_value = mock_scalars
            return mock_result

        mock_session.execute.side_effect = mock_execute

        ids = list(range(30))
        result = await batch_fetch_detections(mock_session, ids, batch_size=10)

        assert len(result) == 30
        assert mock_session.execute.call_count == 3

    @pytest.mark.asyncio
    async def test_handles_missing_ids_gracefully(self) -> None:
        """Should handle case where some IDs don't exist in database."""
        mock_session = AsyncMock()

        # Only return 2 of 5 requested detections
        mock_detections = [
            MagicMock(spec=Detection, id=1),
            MagicMock(spec=Detection, id=3),
        ]

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_detections
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await batch_fetch_detections(mock_session, [1, 2, 3, 4, 5])

        # Should return only found detections, not raise error
        assert len(result) == 2
        assert {d.id for d in result} == {1, 3}

    @pytest.mark.asyncio
    async def test_deduplicates_input_ids(self) -> None:
        """Duplicate IDs in input should be deduplicated before querying."""
        mock_session = AsyncMock()
        mock_detection = MagicMock(spec=Detection, id=1)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_detection]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        # Pass duplicates
        result = await batch_fetch_detections(mock_session, [1, 1, 1, 1, 1])

        assert len(result) == 1
        assert mock_session.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_batch_size_clamped_to_min(self) -> None:
        """Batch size below minimum should be clamped to MIN_BATCH_SIZE."""
        mock_session = AsyncMock()
        mock_detection = MagicMock(spec=Detection, id=1)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_detection]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        # Even with tiny batch size, should work correctly
        result = await batch_fetch_detections(mock_session, [1], batch_size=0)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_batch_size_clamped_to_max(self) -> None:
        """Batch size above maximum should be clamped to MAX_BATCH_SIZE."""
        mock_session = AsyncMock()
        # Create more detections than MAX_BATCH_SIZE
        mock_detections = [MagicMock(spec=Detection, id=i) for i in range(100)]

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_detections
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        # Even with huge batch size, should use clamped value
        result = await batch_fetch_detections(mock_session, list(range(100)), batch_size=100000)

        assert len(result) == 100
        # Should work without error (batch_size clamped to MAX)


class TestBatchFetchDetectionsByIds:
    """Tests for batch_fetch_detections_by_ids (dict return variant)."""

    @pytest.mark.asyncio
    async def test_returns_dict_keyed_by_id(self) -> None:
        """Should return dictionary with detection IDs as keys."""
        mock_session = AsyncMock()
        mock_detections = [
            MagicMock(spec=Detection, id=1),
            MagicMock(spec=Detection, id=5),
            MagicMock(spec=Detection, id=10),
        ]

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_detections
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await batch_fetch_detections_by_ids(mock_session, [1, 5, 10])

        assert isinstance(result, dict)
        assert set(result.keys()) == {1, 5, 10}
        assert result[1].id == 1
        assert result[5].id == 5
        assert result[10].id == 10

    @pytest.mark.asyncio
    async def test_empty_ids_returns_empty_dict(self) -> None:
        """Empty ID list should return empty dict."""
        mock_session = AsyncMock()

        result = await batch_fetch_detections_by_ids(mock_session, [])

        assert result == {}
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_ids_not_in_result(self) -> None:
        """Missing IDs should not be present in result dict."""
        mock_session = AsyncMock()
        mock_detections = [MagicMock(spec=Detection, id=1)]

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_detections
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await batch_fetch_detections_by_ids(mock_session, [1, 2, 3])

        assert 1 in result
        assert 2 not in result
        assert 3 not in result


class TestBatchFetchFilePaths:
    """Tests for batch_fetch_file_paths function."""

    @pytest.mark.asyncio
    async def test_returns_file_paths_only(self) -> None:
        """Should return only file paths, not full Detection objects."""
        from backend.services.batch_fetch import batch_fetch_file_paths

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = [
            ("/path/1.jpg",),
            ("/path/2.jpg",),
            ("/path/3.jpg",),
        ]
        mock_session.execute.return_value = mock_result

        result = await batch_fetch_file_paths(mock_session, [1, 2, 3])

        assert result == ["/path/1.jpg", "/path/2.jpg", "/path/3.jpg"]

    @pytest.mark.asyncio
    async def test_filters_none_paths(self) -> None:
        """Should filter out None file paths."""
        from backend.services.batch_fetch import batch_fetch_file_paths

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = [
            ("/path/1.jpg",),
            (None,),
            ("/path/3.jpg",),
        ]
        mock_session.execute.return_value = mock_result

        result = await batch_fetch_file_paths(mock_session, [1, 2, 3])

        assert result == ["/path/1.jpg", "/path/3.jpg"]

    @pytest.mark.asyncio
    async def test_empty_ids_returns_empty_list(self) -> None:
        """Empty ID list should return empty list."""
        from backend.services.batch_fetch import batch_fetch_file_paths

        mock_session = AsyncMock()

        result = await batch_fetch_file_paths(mock_session, [])

        assert result == []
        mock_session.execute.assert_not_called()
