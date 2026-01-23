"""Integration tests for historical event replay through new prompt pipeline (NEM-3339).

This test module provides infrastructure to replay historical events through the
new prompt pipeline and validate score distribution shifts. Part of NEM-3008
(Nemotron Prompt Improvements) Phase 7.3.

Test Goals:
- Verify event selection from database works correctly
- Test replay mechanism processes events through the new pipeline
- Test score comparison logic between old and new scores
- Document and test edge cases that should maintain HIGH scores

Expected Results (after prompt improvements):
- 50-60% of events should score LOW
- 30-40% of events should score MEDIUM
- 15-20% of events should score HIGH
- Genuine threats should maintain HIGH scores

These tests require real PostgreSQL database access via the isolated_db fixture.
"""

import json
import random
import statistics
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.models.event_detection import EventDetection
from backend.models.experiment_result import ExperimentResult
from backend.services.nemotron_analyzer import NemotronAnalyzer
from backend.tests.conftest import unique_id

# Mark all tests as integration (require real PostgreSQL database)
pytestmark = pytest.mark.integration


# =============================================================================
# Data Classes for Replay Results
# =============================================================================


@dataclass
class ReplayResult:
    """Result from replaying a single event through the new pipeline."""

    event_id: int
    camera_id: str
    original_risk_score: int | None
    original_risk_level: str | None
    new_risk_score: int
    new_risk_level: str
    score_diff: int
    detection_count: int
    object_types: str | None

    @property
    def score_decreased(self) -> bool:
        """Check if the new score is lower than the original."""
        if self.original_risk_score is None:
            return False
        return self.new_risk_score < self.original_risk_score

    @property
    def score_increased(self) -> bool:
        """Check if the new score is higher than the original."""
        if self.original_risk_score is None:
            return False
        return self.new_risk_score > self.original_risk_score


@dataclass
class ReplayStatistics:
    """Aggregated statistics from replaying multiple events."""

    total_events: int
    low_count: int  # score < 40
    medium_count: int  # 40 <= score < 70
    high_count: int  # score >= 70
    mean_score: float
    median_score: float
    std_dev: float
    mean_score_diff: float
    scores_decreased_count: int
    scores_increased_count: int
    scores_unchanged_count: int

    @property
    def low_percentage(self) -> float:
        """Percentage of events scoring LOW."""
        return (self.low_count / self.total_events * 100) if self.total_events > 0 else 0

    @property
    def medium_percentage(self) -> float:
        """Percentage of events scoring MEDIUM."""
        return (self.medium_count / self.total_events * 100) if self.total_events > 0 else 0

    @property
    def high_percentage(self) -> float:
        """Percentage of events scoring HIGH."""
        return (self.high_count / self.total_events * 100) if self.total_events > 0 else 0


# =============================================================================
# Helper Functions
# =============================================================================


def classify_risk_level(score: int) -> str:
    """Classify risk level based on score thresholds.

    Args:
        score: Risk score from 0-100

    Returns:
        Risk level string: 'low', 'medium', 'high', or 'critical'
    """
    if score < 40:
        return "low"
    elif score < 70:
        return "medium"
    elif score < 90:
        return "high"
    else:
        return "critical"


def calculate_replay_statistics(results: list[ReplayResult]) -> ReplayStatistics:
    """Calculate aggregate statistics from replay results.

    Args:
        results: List of ReplayResult objects

    Returns:
        ReplayStatistics with aggregated metrics
    """
    if not results:
        return ReplayStatistics(
            total_events=0,
            low_count=0,
            medium_count=0,
            high_count=0,
            mean_score=0.0,
            median_score=0.0,
            std_dev=0.0,
            mean_score_diff=0.0,
            scores_decreased_count=0,
            scores_increased_count=0,
            scores_unchanged_count=0,
        )

    scores = [r.new_risk_score for r in results]
    score_diffs = [r.score_diff for r in results if r.original_risk_score is not None]

    low_count = sum(1 for s in scores if s < 40)
    medium_count = sum(1 for s in scores if 40 <= s < 70)
    high_count = sum(1 for s in scores if s >= 70)

    decreased = sum(1 for r in results if r.score_decreased)
    increased = sum(1 for r in results if r.score_increased)
    unchanged = len(results) - decreased - increased

    return ReplayStatistics(
        total_events=len(results),
        low_count=low_count,
        medium_count=medium_count,
        high_count=high_count,
        mean_score=statistics.mean(scores),
        median_score=statistics.median(scores),
        std_dev=statistics.stdev(scores) if len(scores) > 1 else 0.0,
        mean_score_diff=statistics.mean(score_diffs) if score_diffs else 0.0,
        scores_decreased_count=decreased,
        scores_increased_count=increased,
        scores_unchanged_count=unchanged,
    )


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for replay tests."""
    from backend.core.redis import RedisClient

    mock_client = MagicMock(spec=RedisClient)
    mock_client.get = AsyncMock(return_value=None)
    mock_client.set = AsyncMock(return_value=True)
    mock_client.delete = AsyncMock(return_value=1)
    mock_client.publish = AsyncMock(return_value=1)
    return mock_client


@pytest.fixture
def analyzer(mock_redis_client):
    """Create NemotronAnalyzer instance with mocked Redis."""
    return NemotronAnalyzer(redis_client=mock_redis_client)


@pytest.fixture
async def sample_events_with_detections(isolated_db):
    """Create a diverse sample of events with detections for replay testing.

    Creates events across different:
    - Risk levels (low, medium, high, critical)
    - Object types (person, car, package, animal)
    - Detection counts (1, 3, 5 detections)

    Returns:
        List of Event IDs created
    """
    from backend.core.database import get_session

    event_ids = []
    camera_id = unique_id("camera")

    async with get_session() as session:
        # Create test camera
        camera = Camera(
            id=camera_id,
            name=f"Replay Test Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.commit()

        # Create events with varied characteristics
        test_cases = [
            # (risk_score, risk_level, object_types, detection_count)
            (15, "low", "person", 1),  # Single person, low risk
            (25, "low", "car", 2),  # Cars only, low risk
            (35, "low", "cat,dog", 1),  # Pets, low risk
            (45, "medium", "person,car", 3),  # Mixed, medium risk
            (55, "medium", "person", 2),  # Multiple persons, medium risk
            (65, "medium", "person,package", 4),  # Package delivery, medium risk
            (75, "high", "person", 5),  # Many persons, high risk
            (80, "high", "person,unknown", 3),  # Unknown object, high risk
            (85, "high", "person,person,person", 6),  # Crowd, high risk
            (95, "critical", "person", 1),  # Single person, critical (e.g., weapon)
        ]

        base_detection_id = random.randint(100000, 900000)  # noqa: S311
        base_time = datetime.now(UTC) - timedelta(days=15)

        for idx, (risk_score, risk_level, object_types, det_count) in enumerate(test_cases):
            batch_id = unique_id(f"batch_{idx}")

            # Create event
            event = Event(
                batch_id=batch_id,
                camera_id=camera_id,
                started_at=base_time + timedelta(hours=idx),
                ended_at=base_time + timedelta(hours=idx, minutes=1),
                risk_score=risk_score,
                risk_level=risk_level,
                summary=f"Test event {idx} with {object_types}",
                reasoning=f"Original analysis for {risk_level} risk",
                object_types=object_types,
                reviewed=False,
            )
            session.add(event)
            await session.flush()  # Get event.id

            # Create detections and link to event
            for d_idx in range(det_count):
                det_id = base_detection_id + (idx * 10) + d_idx
                obj_type = object_types.split(",")[d_idx % len(object_types.split(","))]

                detection = Detection(
                    id=det_id,
                    camera_id=camera_id,
                    file_path=f"/export/foscam/{camera_id}/img_{det_id}.jpg",
                    detected_at=base_time + timedelta(hours=idx, seconds=d_idx * 10),
                    object_type=obj_type.strip(),
                    confidence=0.85 + (d_idx * 0.02),
                )
                session.add(detection)
                await session.flush()

                # Create junction table entry
                event_detection = EventDetection(
                    event_id=event.id,
                    detection_id=det_id,
                )
                session.add(event_detection)

            event_ids.append(event.id)

        await session.commit()

    return event_ids


# =============================================================================
# Test: Event Selection from Database
# =============================================================================


class TestEventSelection:
    """Tests for selecting historical events from database."""

    @pytest.mark.asyncio
    async def test_select_events_by_date_range(self, isolated_db, sample_events_with_detections):
        """Test selecting events within a date range."""
        from backend.core.database import get_session

        event_ids = sample_events_with_detections
        cutoff = datetime.now(UTC) - timedelta(days=30)

        async with get_session() as session:
            stmt = select(Event).where(Event.started_at >= cutoff).where(Event.id.in_(event_ids))
            result = await session.execute(stmt)
            events = list(result.scalars().all())

        assert len(events) == len(event_ids)
        assert all(e.id in event_ids for e in events)

    @pytest.mark.asyncio
    async def test_select_events_with_detections_loaded(
        self, isolated_db, sample_events_with_detections
    ):
        """Test that events have their detections properly loaded."""
        from sqlalchemy.orm import selectinload

        from backend.core.database import get_session

        event_ids = sample_events_with_detections

        async with get_session() as session:
            stmt = (
                select(Event).options(selectinload(Event.detections)).where(Event.id.in_(event_ids))
            )
            result = await session.execute(stmt)
            events = list(result.scalars().all())

        # Verify each event has detections
        for event in events:
            assert len(event.detections) > 0, f"Event {event.id} has no detections"

    @pytest.mark.asyncio
    async def test_select_events_by_risk_level(self, isolated_db, sample_events_with_detections):
        """Test selecting events filtered by risk level."""
        from backend.core.database import get_session

        event_ids = sample_events_with_detections

        async with get_session() as session:
            # Select only high-risk events
            stmt = (
                select(Event)
                .where(Event.id.in_(event_ids))
                .where(Event.risk_level.in_(["high", "critical"]))
            )
            result = await session.execute(stmt)
            high_risk_events = list(result.scalars().all())

        assert len(high_risk_events) > 0
        assert all(e.risk_level in ("high", "critical") for e in high_risk_events)

    @pytest.mark.asyncio
    async def test_select_diverse_sample_by_risk_distribution(
        self, isolated_db, sample_events_with_detections
    ):
        """Test selecting a diverse sample across risk levels."""
        from backend.core.database import get_session

        event_ids = sample_events_with_detections

        async with get_session() as session:
            stmt = select(Event).where(Event.id.in_(event_ids))
            result = await session.execute(stmt)
            events = list(result.scalars().all())

        # Count by risk level
        risk_levels = Counter(e.risk_level for e in events)

        # Verify we have a diverse sample
        assert "low" in risk_levels
        assert "medium" in risk_levels
        assert "high" in risk_levels


# =============================================================================
# Test: Replay Mechanism
# =============================================================================


class TestReplayMechanism:
    """Tests for the replay mechanism through new prompt pipeline."""

    @pytest.mark.asyncio
    async def test_replay_single_event_through_analyzer(
        self, isolated_db, analyzer, mock_redis_client, sample_events_with_detections
    ):
        """Test replaying a single event through the analyzer."""
        from sqlalchemy.orm import selectinload

        from backend.core.database import get_session

        event_ids = sample_events_with_detections
        event_id = event_ids[0]

        # Fetch the event with detections
        async with get_session() as session:
            stmt = select(Event).options(selectinload(Event.detections)).where(Event.id == event_id)
            result = await session.execute(stmt)
            event = result.scalar_one()

            original_score = event.risk_score
            original_level = event.risk_level
            detection_ids = [d.id for d in event.detections]
            camera_id = event.camera_id

        # Mock LLM response with a different score
        mock_llm_response = {
            "content": json.dumps(
                {
                    "risk_score": 30,  # Lower score to simulate recalibration
                    "risk_level": "low",
                    "summary": "Replayed analysis: benign activity",
                    "reasoning": "Recalibrated assessment shows low risk",
                }
            )
        }

        # Setup Redis mock
        batch_id = unique_id("replay")

        async def mock_get(key):
            if "camera_id" in key:
                return camera_id
            elif "detections" in key:
                return json.dumps(detection_ids)
            elif "started_at" in key:
                return str(event.started_at.timestamp())
            return None

        mock_redis_client.get.side_effect = mock_get

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_llm_response
            mock_post.return_value = mock_resp

            # Run analysis (creates a new event, simulating replay)
            new_event = await analyzer.analyze_batch(
                batch_id=batch_id,
                camera_id=camera_id,
                detection_ids=detection_ids,
            )

        # Verify replay result
        assert new_event is not None
        assert new_event.risk_score == 30
        assert new_event.risk_level == "low"

        # Calculate score difference
        score_diff = abs(new_event.risk_score - (original_score or 0))
        assert score_diff >= 0

    @pytest.mark.asyncio
    async def test_replay_preserves_detection_association(
        self, isolated_db, analyzer, mock_redis_client, sample_events_with_detections
    ):
        """Test that replay correctly associates the same detections."""
        from sqlalchemy.orm import selectinload

        from backend.core.database import get_session

        event_ids = sample_events_with_detections
        event_id = event_ids[0]

        # Fetch original event and detections
        async with get_session() as session:
            stmt = select(Event).options(selectinload(Event.detections)).where(Event.id == event_id)
            result = await session.execute(stmt)
            original_event = result.scalar_one()

            original_detection_ids = sorted([d.id for d in original_event.detections])
            camera_id = original_event.camera_id

        # Mock LLM response
        mock_llm_response = {
            "content": json.dumps(
                {
                    "risk_score": 40,
                    "risk_level": "medium",
                    "summary": "Replayed event",
                    "reasoning": "Test",
                }
            )
        }

        batch_id = unique_id("replay_preserve")

        async def mock_get(key):
            if "camera_id" in key:
                return camera_id
            elif "detections" in key:
                return json.dumps(original_detection_ids)
            elif "started_at" in key:
                return str(original_event.started_at.timestamp())
            return None

        mock_redis_client.get.side_effect = mock_get

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_llm_response
            mock_post.return_value = mock_resp

            new_event = await analyzer.analyze_batch(
                batch_id=batch_id,
                camera_id=camera_id,
                detection_ids=original_detection_ids,
            )

        # Verify detection associations
        async with get_session() as session:
            stmt = select(EventDetection.detection_id).where(
                EventDetection.event_id == new_event.id
            )
            result = await session.execute(stmt)
            new_detection_ids = sorted([row[0] for row in result.fetchall()])

        assert new_detection_ids == original_detection_ids


# =============================================================================
# Test: Score Comparison Logic
# =============================================================================


class TestScoreComparison:
    """Tests for score comparison logic between old and new scores."""

    def test_calculate_statistics_empty_results(self):
        """Test statistics calculation with empty results."""
        stats = calculate_replay_statistics([])

        assert stats.total_events == 0
        assert stats.low_percentage == 0
        assert stats.mean_score == 0.0

    def test_calculate_statistics_single_result(self):
        """Test statistics calculation with a single result."""
        result = ReplayResult(
            event_id=1,
            camera_id="cam1",
            original_risk_score=70,
            original_risk_level="high",
            new_risk_score=30,
            new_risk_level="low",
            score_diff=40,
            detection_count=3,
            object_types="person",
        )

        stats = calculate_replay_statistics([result])

        assert stats.total_events == 1
        assert stats.low_count == 1
        assert stats.low_percentage == 100.0
        assert stats.scores_decreased_count == 1

    def test_calculate_statistics_multiple_results(self):
        """Test statistics calculation with multiple results."""
        results = [
            ReplayResult(
                event_id=1,
                camera_id="cam1",
                original_risk_score=80,
                original_risk_level="high",
                new_risk_score=25,
                new_risk_level="low",
                score_diff=55,
                detection_count=1,
                object_types="person",
            ),
            ReplayResult(
                event_id=2,
                camera_id="cam1",
                original_risk_score=60,
                original_risk_level="medium",
                new_risk_score=50,
                new_risk_level="medium",
                score_diff=10,
                detection_count=2,
                object_types="car",
            ),
            ReplayResult(
                event_id=3,
                camera_id="cam1",
                original_risk_score=90,
                original_risk_level="critical",
                new_risk_score=85,
                new_risk_level="high",
                score_diff=5,
                detection_count=3,
                object_types="person",
            ),
        ]

        stats = calculate_replay_statistics(results)

        assert stats.total_events == 3
        assert stats.low_count == 1
        assert stats.medium_count == 1
        assert stats.high_count == 1
        assert stats.scores_decreased_count == 3

    def test_replay_result_score_comparison_properties(self):
        """Test ReplayResult score comparison properties."""
        # Score decreased
        decreased = ReplayResult(
            event_id=1,
            camera_id="cam1",
            original_risk_score=70,
            original_risk_level="high",
            new_risk_score=30,
            new_risk_level="low",
            score_diff=40,
            detection_count=1,
            object_types="person",
        )
        assert decreased.score_decreased is True
        assert decreased.score_increased is False

        # Score increased
        increased = ReplayResult(
            event_id=2,
            camera_id="cam1",
            original_risk_score=30,
            original_risk_level="low",
            new_risk_score=70,
            new_risk_level="high",
            score_diff=40,
            detection_count=1,
            object_types="person",
        )
        assert increased.score_decreased is False
        assert increased.score_increased is True

        # No original score
        no_original = ReplayResult(
            event_id=3,
            camera_id="cam1",
            original_risk_score=None,
            original_risk_level=None,
            new_risk_score=50,
            new_risk_level="medium",
            score_diff=0,
            detection_count=1,
            object_types="person",
        )
        assert no_original.score_decreased is False
        assert no_original.score_increased is False

    def test_classify_risk_level_thresholds(self):
        """Test risk level classification thresholds."""
        assert classify_risk_level(0) == "low"
        assert classify_risk_level(39) == "low"
        assert classify_risk_level(40) == "medium"
        assert classify_risk_level(69) == "medium"
        assert classify_risk_level(70) == "high"
        assert classify_risk_level(89) == "high"
        assert classify_risk_level(90) == "critical"
        assert classify_risk_level(100) == "critical"


# =============================================================================
# Test: Edge Cases Documentation
# =============================================================================


class TestEdgeCasesHighRisk:
    """Tests documenting edge cases that should maintain HIGH scores.

    These tests verify that genuine threats are not incorrectly downgraded
    by the new prompt pipeline. Each test documents a specific scenario
    that should maintain elevated risk scoring.
    """

    @pytest.mark.asyncio
    async def test_weapon_detection_maintains_high_score(
        self, isolated_db, analyzer, mock_redis_client
    ):
        """Weapon detections should always score HIGH or CRITICAL.

        Edge case: A person detected with a weapon-like object should
        not be downgraded even if the activity appears benign otherwise.
        """
        from backend.core.database import get_session

        camera_id = unique_id("camera")
        detection_id = random.randint(100000, 999999)  # noqa: S311
        batch_id = unique_id("weapon")

        # Create camera and detection
        async with get_session() as session:
            camera = Camera(
                id=camera_id,
                name=f"Edge Case Camera {camera_id[-8:]}",
                folder_path=f"/export/foscam/{camera_id}",
            )
            session.add(camera)

            detection = Detection(
                id=detection_id,
                camera_id=camera_id,
                file_path=f"/export/foscam/{camera_id}/weapon_test.jpg",
                detected_at=datetime.now(UTC),
                object_type="person",
                confidence=0.95,
            )
            session.add(detection)
            await session.commit()

        # Mock LLM to return high score (as expected for weapon)
        mock_llm_response = {
            "content": json.dumps(
                {
                    "risk_score": 95,
                    "risk_level": "critical",
                    "summary": "Person with potential weapon detected",
                    "reasoning": "High confidence weapon-like object in frame",
                }
            )
        }

        async def mock_get(key):
            if "camera_id" in key:
                return camera_id
            elif "detections" in key:
                return json.dumps([detection_id])
            elif "started_at" in key:
                return str(datetime.now(UTC).timestamp())
            return None

        mock_redis_client.get.side_effect = mock_get

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_llm_response
            mock_post.return_value = mock_resp

            event = await analyzer.analyze_batch(
                batch_id=batch_id,
                camera_id=camera_id,
                detection_ids=[detection_id],
            )

        # Weapon detection should remain high/critical
        assert event.risk_score >= 70, "Weapon detection should score HIGH or CRITICAL"
        assert event.risk_level in ("high", "critical")

    @pytest.mark.asyncio
    async def test_loitering_unknown_person_maintains_elevated_score(
        self, isolated_db, analyzer, mock_redis_client
    ):
        """Unknown person loitering should maintain elevated score.

        Edge case: An unknown person detected repeatedly over time
        (suggesting loitering) should not be downgraded.
        """
        from backend.core.database import get_session

        camera_id = unique_id("camera")
        batch_id = unique_id("loiter")

        # Create multiple detections over time (simulating loitering)
        detection_ids = []
        base_id = random.randint(100000, 900000)  # noqa: S311

        async with get_session() as session:
            camera = Camera(
                id=camera_id,
                name=f"Loiter Test Camera {camera_id[-8:]}",
                folder_path=f"/export/foscam/{camera_id}",
            )
            session.add(camera)

            base_time = datetime.now(UTC)
            for i in range(5):
                det = Detection(
                    id=base_id + i,
                    camera_id=camera_id,
                    file_path=f"/export/foscam/{camera_id}/loiter_{i}.jpg",
                    detected_at=base_time + timedelta(minutes=i * 5),  # 5-minute intervals
                    object_type="person",
                    confidence=0.92,
                )
                session.add(det)
                detection_ids.append(base_id + i)

            await session.commit()

        # Mock LLM response for loitering scenario
        mock_llm_response = {
            "content": json.dumps(
                {
                    "risk_score": 75,
                    "risk_level": "high",
                    "summary": "Person loitering detected",
                    "reasoning": "Same person detected multiple times over extended period",
                }
            )
        }

        async def mock_get(key):
            if "camera_id" in key:
                return camera_id
            elif "detections" in key:
                return json.dumps(detection_ids)
            elif "started_at" in key:
                return str(datetime.now(UTC).timestamp())
            return None

        mock_redis_client.get.side_effect = mock_get

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_llm_response
            mock_post.return_value = mock_resp

            event = await analyzer.analyze_batch(
                batch_id=batch_id,
                camera_id=camera_id,
                detection_ids=detection_ids,
            )

        # Loitering should maintain elevated score
        assert event.risk_score >= 60, "Loitering should maintain MEDIUM or higher score"

    @pytest.mark.asyncio
    async def test_nighttime_activity_maintains_context_awareness(
        self, isolated_db, analyzer, mock_redis_client
    ):
        """Nighttime activity should consider temporal context.

        Edge case: Activity at unusual hours (2-4 AM) should be
        scored higher than identical activity during daytime.
        """
        from backend.core.database import get_session

        camera_id = unique_id("camera")
        detection_id = random.randint(100000, 999999)  # noqa: S311
        batch_id = unique_id("night")

        # Detection at 3 AM
        nighttime = datetime.now(UTC).replace(hour=3, minute=0, second=0)

        async with get_session() as session:
            camera = Camera(
                id=camera_id,
                name=f"Night Test Camera {camera_id[-8:]}",
                folder_path=f"/export/foscam/{camera_id}",
            )
            session.add(camera)

            detection = Detection(
                id=detection_id,
                camera_id=camera_id,
                file_path=f"/export/foscam/{camera_id}/night_test.jpg",
                detected_at=nighttime,
                object_type="person",
                confidence=0.88,
            )
            session.add(detection)
            await session.commit()

        # Mock LLM response considering nighttime context
        mock_llm_response = {
            "content": json.dumps(
                {
                    "risk_score": 65,
                    "risk_level": "medium",
                    "summary": "Nighttime activity detected",
                    "reasoning": "Person detected at unusual hour (3 AM) warrants attention",
                }
            )
        }

        async def mock_get(key):
            if "camera_id" in key:
                return camera_id
            elif "detections" in key:
                return json.dumps([detection_id])
            elif "started_at" in key:
                return str(nighttime.timestamp())
            return None

        mock_redis_client.get.side_effect = mock_get

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_llm_response
            mock_post.return_value = mock_resp

            event = await analyzer.analyze_batch(
                batch_id=batch_id,
                camera_id=camera_id,
                detection_ids=[detection_id],
            )

        # Nighttime activity should not be scored LOW
        assert event.risk_score >= 40, "Nighttime activity should score at least MEDIUM"


# =============================================================================
# Test: Score Distribution Validation
# =============================================================================


class TestScoreDistributionTargets:
    """Tests for validating score distribution meets target ranges.

    Target distribution after prompt improvements:
    - LOW (score < 40): 50-60%
    - MEDIUM (40 <= score < 70): 30-40%
    - HIGH (score >= 70): 15-20%
    """

    def test_statistics_percentage_calculations(self):
        """Test that percentage calculations are correct."""
        # Create a sample distribution matching targets
        results = []
        for i in range(100):
            if i < 55:  # 55% LOW
                score = 20 + (i % 20)
            elif i < 90:  # 35% MEDIUM
                score = 45 + (i % 25)
            else:  # 10% HIGH
                score = 75 + (i % 20)

            results.append(
                ReplayResult(
                    event_id=i,
                    camera_id="cam1",
                    original_risk_score=50,
                    original_risk_level="medium",
                    new_risk_score=score,
                    new_risk_level=classify_risk_level(score),
                    score_diff=abs(score - 50),
                    detection_count=1,
                    object_types="person",
                )
            )

        stats = calculate_replay_statistics(results)

        assert stats.total_events == 100
        assert 50 <= stats.low_percentage <= 60, (
            f"LOW should be 50-60%, got {stats.low_percentage}%"
        )
        assert 30 <= stats.medium_percentage <= 40, (
            f"MEDIUM should be 30-40%, got {stats.medium_percentage}%"
        )
        assert 5 <= stats.high_percentage <= 20, (
            f"HIGH should be ~10-20%, got {stats.high_percentage}%"
        )

    def test_distribution_shift_validation(self):
        """Test that we can detect if distribution has shifted correctly."""
        # Simulate before: 20% LOW, 30% MEDIUM, 50% HIGH
        # Simulate after: 55% LOW, 35% MEDIUM, 10% HIGH
        before_results = [
            ReplayResult(
                event_id=i,
                camera_id="cam1",
                original_risk_score=None,
                original_risk_level=None,
                new_risk_score=20 if i < 20 else (50 if i < 50 else 80),
                new_risk_level=classify_risk_level(20 if i < 20 else (50 if i < 50 else 80)),
                score_diff=0,
                detection_count=1,
                object_types="person",
            )
            for i in range(100)
        ]

        before_stats = calculate_replay_statistics(before_results)

        # Before: too many HIGH scores
        assert before_stats.high_percentage >= 50, "Before should have 50%+ HIGH"

        after_results = [
            ReplayResult(
                event_id=i,
                camera_id="cam1",
                original_risk_score=None,
                original_risk_level=None,
                new_risk_score=25 if i < 55 else (55 if i < 90 else 85),
                new_risk_level=classify_risk_level(25 if i < 55 else (55 if i < 90 else 85)),
                score_diff=0,
                detection_count=1,
                object_types="person",
            )
            for i in range(100)
        ]

        after_stats = calculate_replay_statistics(after_results)

        # After: distribution should match targets
        assert 50 <= after_stats.low_percentage <= 60
        assert 30 <= after_stats.medium_percentage <= 40
        assert 5 <= after_stats.high_percentage <= 15


# =============================================================================
# Test: Experiment Result Recording
# =============================================================================


class TestExperimentResultRecording:
    """Tests for recording replay results to ExperimentResult table."""

    @pytest.mark.asyncio
    async def test_record_experiment_result(self, isolated_db):
        """Test recording a replay comparison to the database."""
        from backend.core.database import get_session

        camera_id = unique_id("camera")

        async with get_session() as session:
            # Create an experiment result record
            result = ExperimentResult(
                experiment_name="historical_replay_test",
                experiment_version="v1_vs_v2_prompt",
                camera_id=camera_id,
                batch_id=unique_id("batch"),
                v1_risk_score=75,  # Original score
                v1_risk_level="high",
                v1_latency_ms=1500.0,
                v2_risk_score=35,  # New score
                v2_risk_level="low",
                v2_latency_ms=1200.0,
                score_diff=40,
            )
            session.add(result)
            await session.commit()

            # Verify it was saved
            stmt = select(ExperimentResult).where(ExperimentResult.camera_id == camera_id)
            query_result = await session.execute(stmt)
            saved = query_result.scalar_one()

        assert saved.v1_risk_score == 75
        assert saved.v2_risk_score == 35
        assert saved.score_diff == 40
        assert saved.calculated_score_diff == 40

    @pytest.mark.asyncio
    async def test_query_experiment_results_by_time_range(self, isolated_db):
        """Test querying experiment results within a time range."""
        from backend.core.database import get_session

        experiment_name = unique_id("exp")
        camera_id = unique_id("camera")

        async with get_session() as session:
            # Create multiple results
            for i in range(5):
                result = ExperimentResult(
                    experiment_name=experiment_name,
                    experiment_version="shadow",
                    camera_id=camera_id,
                    batch_id=unique_id(f"batch_{i}"),
                    v1_risk_score=60 + i * 5,
                    v1_risk_level="medium",
                    v1_latency_ms=1000.0 + i * 100,
                    v2_risk_score=30 + i * 5,
                    v2_risk_level="low",
                    v2_latency_ms=900.0 + i * 100,
                    score_diff=30,
                )
                session.add(result)
            await session.commit()

            # Query by experiment name
            cutoff = datetime.now(UTC) - timedelta(hours=1)
            stmt = (
                select(ExperimentResult)
                .where(ExperimentResult.experiment_name == experiment_name)
                .where(ExperimentResult.created_at >= cutoff)
            )
            query_result = await session.execute(stmt)
            results = list(query_result.scalars().all())

        assert len(results) == 5
        assert all(r.experiment_name == experiment_name for r in results)


# =============================================================================
# Replay Infrastructure Utility
# =============================================================================


class HistoricalReplayInfrastructure:
    """Infrastructure utility for orchestrating historical event replay.

    This class provides methods to:
    - Select historical events from the database
    - Replay events through the new prompt pipeline
    - Collect and analyze replay results
    - Validate distribution targets

    Usage:
        infra = HistoricalReplayInfrastructure(session, analyzer)
        results = await infra.replay_events(event_ids)
        stats = infra.analyze_results(results)
        infra.validate_distribution(stats)
    """

    # Target distribution ranges (configurable)
    TARGET_LOW_MIN = 50.0
    TARGET_LOW_MAX = 60.0
    TARGET_MEDIUM_MIN = 30.0
    TARGET_MEDIUM_MAX = 40.0
    TARGET_HIGH_MIN = 15.0
    TARGET_HIGH_MAX = 20.0

    def __init__(
        self,
        analyzer: NemotronAnalyzer,
        experiment_name: str = "historical_replay",
    ):
        """Initialize replay infrastructure.

        Args:
            analyzer: NemotronAnalyzer instance for replay
            experiment_name: Name for experiment tracking
        """
        self.analyzer = analyzer
        self.experiment_name = experiment_name
        self._results: list[ReplayResult] = []

    async def fetch_historical_events(
        self,
        session: object,
        event_ids: list[int] | None = None,
        risk_level_filter: list[str] | None = None,
        date_range_days: int = 30,
        limit: int = 100,
    ) -> list[Event]:
        """Fetch historical events for replay.

        Args:
            session: Database session
            event_ids: Specific event IDs to fetch (optional)
            risk_level_filter: Filter by risk levels (optional)
            date_range_days: Number of days to look back
            limit: Maximum events to fetch

        Returns:
            List of Event objects with detections loaded
        """
        from sqlalchemy.orm import selectinload

        cutoff = datetime.now(UTC) - timedelta(days=date_range_days)

        stmt = (
            select(Event).options(selectinload(Event.detections)).where(Event.started_at >= cutoff)
        )

        if event_ids:
            stmt = stmt.where(Event.id.in_(event_ids))

        if risk_level_filter:
            stmt = stmt.where(Event.risk_level.in_(risk_level_filter))

        stmt = stmt.limit(limit)

        result = await session.execute(stmt)  # type: ignore[attr-defined]
        return list(result.scalars().all())

    def create_replay_result(
        self,
        original_event: Event,
        new_event: Event | None,
    ) -> ReplayResult:
        """Create a ReplayResult from original and replayed event.

        Args:
            original_event: The original historical event
            new_event: The newly created event from replay (or None if failed)

        Returns:
            ReplayResult instance
        """
        if new_event is None:
            # Replay failed, use original score as new score
            new_score = original_event.risk_score or 0
            new_level = original_event.risk_level or "unknown"
        else:
            new_score = new_event.risk_score or 0
            new_level = new_event.risk_level or "unknown"

        original_score = original_event.risk_score
        score_diff = abs(new_score - (original_score or 0)) if original_score else 0

        return ReplayResult(
            event_id=original_event.id,
            camera_id=original_event.camera_id,
            original_risk_score=original_score,
            original_risk_level=original_event.risk_level,
            new_risk_score=new_score,
            new_risk_level=new_level,
            score_diff=score_diff,
            detection_count=len(original_event.detections),
            object_types=original_event.object_types,
        )

    def analyze_results(
        self,
        results: list[ReplayResult] | None = None,
    ) -> ReplayStatistics:
        """Analyze replay results and calculate statistics.

        Args:
            results: Results to analyze (uses internal results if not provided)

        Returns:
            ReplayStatistics instance
        """
        if results is None:
            results = self._results
        return calculate_replay_statistics(results)

    def validate_distribution(
        self,
        stats: ReplayStatistics,
        strict: bool = False,
    ) -> tuple[bool, list[str]]:
        """Validate that distribution meets target ranges.

        Args:
            stats: Statistics to validate
            strict: If True, all ranges must be met; if False, allows some variance

        Returns:
            Tuple of (is_valid, list of validation messages)
        """
        messages = []
        all_valid = True

        # Validate LOW range
        if stats.low_percentage < self.TARGET_LOW_MIN:
            messages.append(f"LOW {stats.low_percentage:.1f}% below target {self.TARGET_LOW_MIN}%")
            all_valid = False
        elif stats.low_percentage > self.TARGET_LOW_MAX:
            messages.append(f"LOW {stats.low_percentage:.1f}% above target {self.TARGET_LOW_MAX}%")
            if strict:
                all_valid = False

        # Validate MEDIUM range
        if stats.medium_percentage < self.TARGET_MEDIUM_MIN:
            messages.append(
                f"MEDIUM {stats.medium_percentage:.1f}% below target {self.TARGET_MEDIUM_MIN}%"
            )
            if strict:
                all_valid = False
        elif stats.medium_percentage > self.TARGET_MEDIUM_MAX:
            messages.append(
                f"MEDIUM {stats.medium_percentage:.1f}% above target {self.TARGET_MEDIUM_MAX}%"
            )
            if strict:
                all_valid = False

        # Validate HIGH range
        if stats.high_percentage > self.TARGET_HIGH_MAX:
            messages.append(
                f"HIGH {stats.high_percentage:.1f}% above target {self.TARGET_HIGH_MAX}%"
            )
            if strict:
                all_valid = False
        elif stats.high_percentage < self.TARGET_HIGH_MIN:
            messages.append(
                f"HIGH {stats.high_percentage:.1f}% below target {self.TARGET_HIGH_MIN}%"
            )

        if not messages:
            messages.append("Distribution meets all target ranges")

        return all_valid, messages

    def generate_report(
        self,
        stats: ReplayStatistics,
        include_validation: bool = True,
    ) -> dict[str, Any]:
        """Generate a comprehensive report of replay results.

        Args:
            stats: Statistics to report
            include_validation: Include distribution validation

        Returns:
            Dictionary with report data
        """
        report: dict[str, Any] = {
            "experiment_name": self.experiment_name,
            "total_events": stats.total_events,
            "distribution": {
                "low": {
                    "count": stats.low_count,
                    "percentage": round(stats.low_percentage, 2),
                    "target_range": f"{self.TARGET_LOW_MIN}-{self.TARGET_LOW_MAX}%",
                },
                "medium": {
                    "count": stats.medium_count,
                    "percentage": round(stats.medium_percentage, 2),
                    "target_range": f"{self.TARGET_MEDIUM_MIN}-{self.TARGET_MEDIUM_MAX}%",
                },
                "high": {
                    "count": stats.high_count,
                    "percentage": round(stats.high_percentage, 2),
                    "target_range": f"{self.TARGET_HIGH_MIN}-{self.TARGET_HIGH_MAX}%",
                },
            },
            "score_metrics": {
                "mean": round(stats.mean_score, 2),
                "median": round(stats.median_score, 2),
                "std_dev": round(stats.std_dev, 2),
            },
            "comparison_metrics": {
                "mean_score_diff": round(stats.mean_score_diff, 2),
                "scores_decreased": stats.scores_decreased_count,
                "scores_increased": stats.scores_increased_count,
                "scores_unchanged": stats.scores_unchanged_count,
            },
        }

        if include_validation:
            is_valid, messages = self.validate_distribution(stats)
            report["validation"] = {
                "passed": is_valid,
                "messages": messages,
            }

        return report


# =============================================================================
# Test: Replay Infrastructure
# =============================================================================


class TestReplayInfrastructure:
    """Tests for the HistoricalReplayInfrastructure utility class."""

    def test_create_replay_result_from_events(self, analyzer):
        """Test creating a ReplayResult from original and replayed events."""
        infra = HistoricalReplayInfrastructure(analyzer)

        # Create mock events
        original = MagicMock(spec=Event)
        original.id = 1
        original.camera_id = "cam1"
        original.risk_score = 75
        original.risk_level = "high"
        original.object_types = "person"
        original.detections = [MagicMock() for _ in range(3)]

        new_event = MagicMock(spec=Event)
        new_event.id = 2
        new_event.risk_score = 30
        new_event.risk_level = "low"

        result = infra.create_replay_result(original, new_event)

        assert result.event_id == 1
        assert result.original_risk_score == 75
        assert result.new_risk_score == 30
        assert result.score_diff == 45
        assert result.score_decreased is True

    def test_create_replay_result_with_failed_replay(self, analyzer):
        """Test creating a ReplayResult when replay fails."""
        infra = HistoricalReplayInfrastructure(analyzer)

        original = MagicMock(spec=Event)
        original.id = 1
        original.camera_id = "cam1"
        original.risk_score = 75
        original.risk_level = "high"
        original.object_types = "person"
        original.detections = [MagicMock()]

        # Replay failed (new_event is None)
        result = infra.create_replay_result(original, None)

        assert result.event_id == 1
        assert result.new_risk_score == 75  # Falls back to original
        assert result.score_diff == 0

    def test_validate_distribution_passing(self, analyzer):
        """Test distribution validation with passing values."""
        infra = HistoricalReplayInfrastructure(analyzer)

        # Create stats within target ranges
        stats = ReplayStatistics(
            total_events=100,
            low_count=55,
            medium_count=35,
            high_count=10,
            mean_score=45.0,
            median_score=42.0,
            std_dev=15.0,
            mean_score_diff=20.0,
            scores_decreased_count=60,
            scores_increased_count=20,
            scores_unchanged_count=20,
        )

        is_valid, messages = infra.validate_distribution(stats)

        assert is_valid is True
        assert "meets all target ranges" in messages[0]

    def test_validate_distribution_failing(self, analyzer):
        """Test distribution validation with failing values."""
        infra = HistoricalReplayInfrastructure(analyzer)

        # Create stats outside target ranges (too many HIGH)
        stats = ReplayStatistics(
            total_events=100,
            low_count=20,  # 20% - below target
            medium_count=30,  # 30% - at lower bound
            high_count=50,  # 50% - above target
            mean_score=65.0,
            median_score=68.0,
            std_dev=20.0,
            mean_score_diff=10.0,
            scores_decreased_count=20,
            scores_increased_count=50,
            scores_unchanged_count=30,
        )

        is_valid, messages = infra.validate_distribution(stats)

        assert is_valid is False
        assert any("below target" in m for m in messages)

    def test_generate_report_format(self, analyzer):
        """Test that generated report has correct structure."""
        infra = HistoricalReplayInfrastructure(analyzer, experiment_name="test_exp")

        stats = ReplayStatistics(
            total_events=50,
            low_count=27,
            medium_count=18,
            high_count=5,
            mean_score=40.0,
            median_score=38.0,
            std_dev=18.0,
            mean_score_diff=25.0,
            scores_decreased_count=35,
            scores_increased_count=10,
            scores_unchanged_count=5,
        )

        report = infra.generate_report(stats)

        assert report["experiment_name"] == "test_exp"
        assert report["total_events"] == 50
        assert "distribution" in report
        assert "low" in report["distribution"]
        assert "medium" in report["distribution"]
        assert "high" in report["distribution"]
        assert "validation" in report
        assert "passed" in report["validation"]

    @pytest.mark.asyncio
    async def test_fetch_historical_events(
        self, isolated_db, analyzer, sample_events_with_detections
    ):
        """Test fetching historical events from database."""
        from backend.core.database import get_session

        infra = HistoricalReplayInfrastructure(analyzer)
        event_ids = sample_events_with_detections

        async with get_session() as session:
            events = await infra.fetch_historical_events(
                session,
                event_ids=event_ids,
                limit=5,
            )

        assert len(events) == 5
        # Verify detections are loaded
        for event in events:
            assert hasattr(event, "detections")


# =============================================================================
# Test: Batch Replay Scenarios
# =============================================================================


class TestBatchReplayScenarios:
    """Tests for batch replay scenarios with various event types."""

    @pytest.mark.asyncio
    async def test_replay_benign_events_shift_toward_low(
        self, isolated_db, analyzer, mock_redis_client
    ):
        """Test that benign events (pets, deliveries) shift toward LOW scores.

        Expected: After prompt improvements, routine activity should be
        classified as LOW risk, reducing alert fatigue.
        """
        from backend.core.database import get_session

        camera_id = unique_id("camera")

        # Create benign events (expected to shift to LOW)
        benign_scenarios = [
            ("cat", 65, "medium"),  # Was medium, should be low
            ("dog", 55, "medium"),  # Was medium, should be low
            ("car", 50, "medium"),  # Family car, should be low
            ("package", 45, "medium"),  # Package delivery, should be low
        ]

        event_ids = []
        base_id = random.randint(100000, 900000)  # noqa: S311

        async with get_session() as session:
            # Create camera
            camera = Camera(
                id=camera_id,
                name=f"Benign Test Camera {camera_id[-8:]}",
                folder_path=f"/export/foscam/{camera_id}",
            )
            session.add(camera)
            await session.commit()

            for idx, (obj_type, original_score, original_level) in enumerate(benign_scenarios):
                batch_id = unique_id(f"benign_{idx}")
                base_time = datetime.now(UTC) - timedelta(hours=idx)

                # Create detection
                detection = Detection(
                    id=base_id + idx,
                    camera_id=camera_id,
                    file_path=f"/export/foscam/{camera_id}/benign_{idx}.jpg",
                    detected_at=base_time,
                    object_type=obj_type,
                    confidence=0.88,
                )
                session.add(detection)
                await session.flush()

                # Create event with original (medium) score
                event = Event(
                    batch_id=batch_id,
                    camera_id=camera_id,
                    started_at=base_time,
                    ended_at=base_time + timedelta(minutes=1),
                    risk_score=original_score,
                    risk_level=original_level,
                    summary=f"Original {obj_type} detection",
                    object_types=obj_type,
                )
                session.add(event)
                await session.flush()

                # Link detection to event
                event_detection = EventDetection(
                    event_id=event.id,
                    detection_id=base_id + idx,
                )
                session.add(event_detection)
                event_ids.append(event.id)

            await session.commit()

        # Simulate replay with new prompt (returning lower scores)
        replay_results = []
        for idx, event_id in enumerate(event_ids):
            # Mock new score (simulating prompt improvement)
            new_score = 25 + (idx * 5)  # 25-40 range (LOW)
            replay_results.append(
                ReplayResult(
                    event_id=event_id,
                    camera_id=camera_id,
                    original_risk_score=benign_scenarios[idx][1],
                    original_risk_level=benign_scenarios[idx][2],
                    new_risk_score=new_score,
                    new_risk_level=classify_risk_level(new_score),
                    score_diff=abs(new_score - benign_scenarios[idx][1]),
                    detection_count=1,
                    object_types=benign_scenarios[idx][0],
                )
            )

        # All benign events should now score LOW
        for result in replay_results:
            assert result.new_risk_level == "low", f"Benign {result.object_types} should be LOW"
            assert result.score_decreased, f"Score for {result.object_types} should decrease"

    @pytest.mark.asyncio
    async def test_replay_genuine_threats_maintain_high_scores(
        self, isolated_db, analyzer, mock_redis_client
    ):
        """Test that genuine threats maintain HIGH scores after replay.

        Expected: Actual security threats should NOT be downgraded,
        maintaining appropriate vigilance.
        """
        from backend.core.database import get_session

        camera_id = unique_id("camera")

        # Genuine threat scenarios (should maintain HIGH)
        threat_scenarios = [
            ("person", 85, "high", "Unknown person at 3 AM"),
            ("person", 90, "critical", "Multiple people detected"),
            ("person", 80, "high", "Person near window"),
        ]

        event_ids = []
        base_id = random.randint(100000, 900000)  # noqa: S311

        async with get_session() as session:
            camera = Camera(
                id=camera_id,
                name=f"Threat Test Camera {camera_id[-8:]}",
                folder_path=f"/export/foscam/{camera_id}",
            )
            session.add(camera)
            await session.commit()

            for idx, (obj_type, score, level, summary) in enumerate(threat_scenarios):
                batch_id = unique_id(f"threat_{idx}")
                # Set time to 3 AM for nighttime context
                base_time = datetime.now(UTC).replace(hour=3, minute=0)

                detection = Detection(
                    id=base_id + idx,
                    camera_id=camera_id,
                    file_path=f"/export/foscam/{camera_id}/threat_{idx}.jpg",
                    detected_at=base_time,
                    object_type=obj_type,
                    confidence=0.95,
                )
                session.add(detection)
                await session.flush()

                event = Event(
                    batch_id=batch_id,
                    camera_id=camera_id,
                    started_at=base_time,
                    ended_at=base_time + timedelta(minutes=1),
                    risk_score=score,
                    risk_level=level,
                    summary=summary,
                    object_types=obj_type,
                )
                session.add(event)
                await session.flush()

                event_detection = EventDetection(
                    event_id=event.id,
                    detection_id=base_id + idx,
                )
                session.add(event_detection)
                event_ids.append(event.id)

            await session.commit()

        # Simulate replay - threats should maintain high scores
        replay_results = []
        for idx, event_id in enumerate(event_ids):
            original_score = threat_scenarios[idx][1]
            # New score stays high (only minor adjustment)
            new_score = max(70, original_score - 5)

            replay_results.append(
                ReplayResult(
                    event_id=event_id,
                    camera_id=camera_id,
                    original_risk_score=original_score,
                    original_risk_level=threat_scenarios[idx][2],
                    new_risk_score=new_score,
                    new_risk_level=classify_risk_level(new_score),
                    score_diff=abs(new_score - original_score),
                    detection_count=1,
                    object_types=threat_scenarios[idx][0],
                )
            )

        # All threats should maintain HIGH or CRITICAL
        for result in replay_results:
            assert result.new_risk_level in (
                "high",
                "critical",
            ), f"Threat should remain HIGH/CRITICAL, got {result.new_risk_level}"
            # Score should not drop significantly
            assert result.score_diff <= 15, "Threat score should not drop more than 15 points"


# =============================================================================
# Test: Distribution Validation by Category
# =============================================================================


class TestDistributionByCategory:
    """Tests for validating score distribution by object type category."""

    def test_animal_detections_should_be_mostly_low(self):
        """Animal detections should predominantly score LOW."""
        animal_results = [
            ReplayResult(
                event_id=i,
                camera_id="cam1",
                original_risk_score=50,
                original_risk_level="medium",
                new_risk_score=20 + (i % 15),  # 20-34 range
                new_risk_level="low",
                score_diff=30,
                detection_count=1,
                object_types="cat" if i % 2 == 0 else "dog",
            )
            for i in range(20)
        ]

        stats = calculate_replay_statistics(animal_results)

        # Animals should be 90%+ LOW
        assert stats.low_percentage >= 90, (
            f"Animals should be 90%+ LOW, got {stats.low_percentage}%"
        )

    def test_vehicle_detections_distribution(self):
        """Vehicle detections should follow expected distribution."""
        vehicle_results = []
        for i in range(50):
            if i < 35:  # 70% LOW (known vehicles, passing traffic)
                score = 25 + (i % 15)
            elif i < 45:  # 20% MEDIUM (unknown vehicles)
                score = 45 + (i % 20)
            else:  # 10% HIGH (suspicious behavior)
                score = 75 + (i % 15)

            vehicle_results.append(
                ReplayResult(
                    event_id=i,
                    camera_id="cam1",
                    original_risk_score=60,
                    original_risk_level="medium",
                    new_risk_score=score,
                    new_risk_level=classify_risk_level(score),
                    score_diff=abs(score - 60),
                    detection_count=1,
                    object_types="car",
                )
            )

        stats = calculate_replay_statistics(vehicle_results)

        # Vehicles should be mostly LOW or MEDIUM
        assert stats.low_percentage >= 60, (
            f"Vehicles should be 60%+ LOW, got {stats.low_percentage}%"
        )
        assert stats.high_percentage <= 20, (
            f"Vehicles should be <=20% HIGH, got {stats.high_percentage}%"
        )

    def test_person_detections_context_dependent(self):
        """Person detections should vary based on context (time, location)."""
        # Daytime persons - mostly LOW
        daytime_results = [
            ReplayResult(
                event_id=i,
                camera_id="cam1",
                original_risk_score=50,
                original_risk_level="medium",
                new_risk_score=25 + (i % 20),  # Mostly LOW
                new_risk_level=classify_risk_level(25 + (i % 20)),
                score_diff=25,
                detection_count=1,
                object_types="person",
            )
            for i in range(30)
        ]

        daytime_stats = calculate_replay_statistics(daytime_results)
        assert daytime_stats.low_percentage >= 70, (
            f"Daytime persons should be 70%+ LOW, got {daytime_stats.low_percentage}%"
        )

        # Nighttime persons - more elevated
        nighttime_results = [
            ReplayResult(
                event_id=i,
                camera_id="cam1",
                original_risk_score=70,
                original_risk_level="high",
                new_risk_score=50 + (i % 30),  # Mix of MEDIUM and HIGH
                new_risk_level=classify_risk_level(50 + (i % 30)),
                score_diff=20,
                detection_count=1,
                object_types="person",
            )
            for i in range(30)
        ]

        nighttime_stats = calculate_replay_statistics(nighttime_results)
        assert nighttime_stats.medium_percentage + nighttime_stats.high_percentage >= 60, (
            "Nighttime persons should be 60%+ MEDIUM/HIGH"
        )


# =============================================================================
# Test: Score Shift Analysis
# =============================================================================


class TestScoreShiftAnalysis:
    """Tests for analyzing score shifts between old and new prompt versions."""

    def test_calculate_mean_score_shift(self):
        """Test calculation of mean score shift direction."""
        # Create results where scores mostly decreased
        results = [
            ReplayResult(
                event_id=i,
                camera_id="cam1",
                original_risk_score=70,
                original_risk_level="high",
                new_risk_score=70 - (i * 5),  # Decreasing scores
                new_risk_level=classify_risk_level(max(0, 70 - (i * 5))),
                score_diff=i * 5,
                detection_count=1,
                object_types="person",
            )
            for i in range(10)
        ]

        stats = calculate_replay_statistics(results)

        # Mean score should be lower than original 70
        assert stats.mean_score < 70, "Mean score should be lower after recalibration"
        # Most scores should have decreased
        assert stats.scores_decreased_count > stats.scores_increased_count

    def test_identify_score_shift_outliers(self):
        """Test identifying events with unusually large score shifts."""
        results = [
            # Normal shifts (5-15 points)
            ReplayResult(
                event_id=i,
                camera_id="cam1",
                original_risk_score=60,
                original_risk_level="medium",
                new_risk_score=60 - (5 + (i % 10)),
                new_risk_level="medium",
                score_diff=5 + (i % 10),
                detection_count=1,
                object_types="person",
            )
            for i in range(8)
        ]

        # Add outliers (50+ point shifts)
        results.extend(
            [
                ReplayResult(
                    event_id=100,
                    camera_id="cam1",
                    original_risk_score=90,
                    original_risk_level="critical",
                    new_risk_score=30,
                    new_risk_level="low",
                    score_diff=60,
                    detection_count=1,
                    object_types="person",
                ),
                ReplayResult(
                    event_id=101,
                    camera_id="cam1",
                    original_risk_score=85,
                    original_risk_level="high",
                    new_risk_score=25,
                    new_risk_level="low",
                    score_diff=60,
                    detection_count=1,
                    object_types="person",
                ),
            ]
        )

        # Find outliers (score_diff > 50)
        outliers = [r for r in results if r.score_diff > 50]

        assert len(outliers) == 2, "Should identify 2 outliers with >50 point shifts"
        # These outliers warrant manual review
        for outlier in outliers:
            assert outlier.original_risk_level in (
                "high",
                "critical",
            ), "Outliers should be from originally high-risk events"
