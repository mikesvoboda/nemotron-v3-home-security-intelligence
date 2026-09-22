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
            autospec=True,
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
            autospec=True,
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
            autospec=True,
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
            autospec=True,
        ):
            count = await recover_orphaned_detections(mock_aggregator)

        assert count == 0
        mock_aggregator.add_detection.assert_not_called()

    def test_constants_are_reasonable(self) -> None:
        """Verify recovery constants match documented constraints."""
        assert ORPHAN_RECOVERY_LIMIT == 500
        assert ORPHAN_MIN_AGE_MINUTES == 3

    # ------------------------------------------------------------------
    # WP4.4 kill tests (frozen triage feed archive/wp25-feed/wp44-triage,
    # clusters C6/C7/C8/C9 -- 26 surviving mutants of recover_orphaned_-
    # detections). The pre-existing tests mock session.execute and never
    # inspect the statement it receives, so mutations to the query's
    # WHERE/join/cutoff/limit/order/projection and to the add_detection
    # kwargs all survived. The statement IS the shipped contract here:
    # LEFT JOIN + event_id IS NULL defines "orphaned", the cutoff is the
    # age gate, ORDER BY ASC re-injects oldest first, LIMIT bounds one
    # pass, load_only fixes the columns add_detection may read.
    # ------------------------------------------------------------------

    async def _run_and_capture_stmt(self) -> tuple[int, object]:
        """Run recovery against mocks; return (count, executed statement)."""
        orphans = [_make_detection(1, "cam_front")]
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = orphans
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_aggregator = AsyncMock()
        mock_aggregator.add_detection = AsyncMock(return_value="batch-x")

        with patch(
            "backend.core.database.get_session",
            return_value=_mock_session_ctx(mock_session),
            autospec=True,
        ):
            count = await recover_orphaned_detections(mock_aggregator)

        assert mock_session.execute.call_count == 1
        return count, mock_session.execute.call_args.args[0]

    @pytest.mark.asyncio
    async def test_scan_statement_is_the_shipped_query_contract(self) -> None:
        """C6/C7: join, orphan filter, order and bound limit are asserted in SQL."""
        from sqlalchemy import Select

        count, stmt = await self._run_and_capture_stmt()
        assert count == 1  # a mutated/None stmt crashes the compile -> count 0
        assert isinstance(stmt, Select)

        sql = " ".join(
            str(stmt.compile(compile_kwargs={"literal_binds": True})).split()
        )
        # C6: orphan definition = LEFT JOIN that MISSES event_detections rows.
        assert (
            "LEFT OUTER JOIN event_detections ON detections.id = event_detections.detection_id" in sql
        )
        assert "event_detections.event_id IS NULL" in sql
        # C6: the age gate is a strict LESS-THAN against the cutoff literal.
        assert "detected_at < '" in sql
        assert "detected_at <=" not in sql
        # C7: oldest first, bounded by the shipped constant.
        assert "ORDER BY detections.detected_at ASC" in sql
        assert sql.endswith(f"LIMIT {ORPHAN_RECOVERY_LIMIT}")

    @pytest.mark.asyncio
    async def test_projection_load_only_carries_every_reinjected_column(self) -> None:
        """C8: dropping ANY load_only column would defer-load outside the session."""
        count, stmt = await self._run_and_capture_stmt()
        assert count == 1
        sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        select_clause = sql.split("FROM")[0]
        # add_detection reads exactly these five columns off each row; the
        # projection must carry them all or the re-injection would lazy-load
        # after the session closed (and the mutant silently "passes" the mocks).
        for col in ("id", "camera_id", "file_path", "confidence", "object_type"):
            assert f"detections.{col}" in select_clause, f"load_only dropped {col}"

    @pytest.mark.asyncio
    async def test_cutoff_is_exactly_min_age_before_now(self) -> None:
        """C6: the bound cutoff is now() - ORPHAN_MIN_AGE_MINUTES, to the second."""
        import re
        from datetime import datetime

        before = datetime.now(UTC)
        count, stmt = await self._run_and_capture_stmt()
        after = datetime.now(UTC)
        assert count == 1

        sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        match = re.search(r"detected_at < '([^']+)'", sql)
        assert match, sql
        cutoff = datetime.fromisoformat(match.group(1)).replace(tzinfo=UTC)
        lo = before - timedelta(minutes=ORPHAN_MIN_AGE_MINUTES)
        hi = after - timedelta(minutes=ORPHAN_MIN_AGE_MINUTES)
        assert lo <= cutoff <= hi, f"cutoff {cutoff} outside [{lo}, {hi}]"

    @pytest.mark.asyncio
    async def test_reinjection_kwargs_are_the_exact_contract(self) -> None:
        """C9: every add_detection kwarg is asserted by name and value."""
        orphans = [_make_detection(7, "cam_front", minutes_ago=40)]
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = orphans
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_aggregator = AsyncMock()
        mock_aggregator.add_detection = AsyncMock(return_value="batch-y")

        with patch(
            "backend.core.database.get_session",
            return_value=_mock_session_ctx(mock_session),
            autospec=True,
        ):
            count = await recover_orphaned_detections(mock_aggregator)

        assert count == 1
        mock_aggregator.add_detection.assert_called_once_with(
            camera_id="cam_front",
            detection_id=7,
            _file_path="/images/cam_front/frame_7.jpg",
            confidence=0.85,
            object_type="person",
        )
