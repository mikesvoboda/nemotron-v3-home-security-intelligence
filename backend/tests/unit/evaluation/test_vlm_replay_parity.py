"""Replay parity (B1.2, D6): replay measures the judge production runs.

Each test sends one input through BOTH real paths and compares what comes out:
the analyzer's `analyze_batch` (against the fakes `test_vlm_analyzer` already
uses) and the replay's `replay_item`. A parity pin that restated the shared
function instead of running the analyzer would pass even if the analyzer
stopped calling it.

* A score the analyzer stores is the score replay records: production passes
  every verdict through `apply_verdict_invariants`, whose table clamps a
  `rejected` verdict to the LOW band. Thresholds picked from replay numbers
  (OD-29's alert floor) were picked on raw scores production never emits.
* The frames the analyzer attaches are the frames replay feeds: production's
  key-frame selection, with production's settings (`key_frame_spread_seconds`),
  not the item's first four media paths.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from backend.core.config import get_settings
from backend.evaluation.assess_input import AssessInput, EvalItem
from backend.evaluation.vlm_replay import replay_item, run_replay
from backend.services.severity import get_severity_service
from backend.tests.unit.evaluation.test_vlm_replay import FakeClient as ItemClient
from backend.tests.unit.evaluation.test_vlm_replay import _item, _store, _verdict
from backend.tests.unit.services.test_vlm_analyzer import (
    FakeClient,
    analyze,
    make_analyzer,
    make_detection_row,
    make_verdict,
)

CAMERA = "front_door"
SPAN_START = datetime(2026, 4, 15, 18, 32, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _arrival_clock(monkeypatch: pytest.MonkeyPatch):
    """Both paths on the shipped default: no camera timezone (compose passes it
    empty), so the selector's spread runs on the rows' own times."""
    monkeypatch.delenv("CAMERA_TIMEZONE", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _still(tmp_path: Path) -> EvalItem:
    frame = tmp_path / "still.jpg"
    frame.write_bytes(b"\xff\xd8z" * 100)
    return EvalItem(
        item_id="still-1",
        media_paths=[str(frame)],
        expected_label="benign",
        expected_risk_score=10,
        snapshot=AssessInput(
            camera_id=CAMERA, detections=[], zones=["front_yard"], timestamp=SPAN_START.isoformat()
        ),
        source="synthetic",
    )


def _spanning_frames(tmp_path: Path) -> list[tuple[Path, float, datetime]]:
    """One class over five frames, the last 30 s after the first: a span longer
    than the shipped `key_frame_spread_seconds` (10), so production's selector
    spends its spare slots on the pair's far frames (ISS-005) instead of
    collapsing the class to its strongest frame, and the far fifth frame is one
    that "the first four media paths" would never feed."""
    out = []
    timeline = ((0.95, 0), (0.90, 5), (0.85, 8), (0.80, 9), (0.70, 30))
    for i, (confidence, offset) in enumerate(timeline, start=1):
        frame = tmp_path / f"span-frame{i}.jpg"
        frame.write_bytes(b"\xff\xd8z" * 100)
        out.append((frame, confidence, SPAN_START + timedelta(seconds=offset)))
    return out


class TestScoreParity:
    async def test_a_clamped_verdict_reads_the_same_through_replay(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The package's failing test: a `rejected` verdict with a high score gives the
        same verdict, score and level through replay as through the analyzer."""
        verdict = make_verdict(verdict="rejected", risk_score=90)

        analyzer, session, _ = make_analyzer(monkeypatch, client=FakeClient([verdict]))
        event = await analyze(analyzer)
        production = (session.added[1].verdict, event.risk_score, event.risk_level)
        assert production[1] is not None and production[1] < 90  # the invariant table fired

        row = await replay_item(FakeClient([verdict]), _still(tmp_path))

        assert (row["verdict"], row["risk_score"], row["risk_level"]) == production

    async def test_the_raw_score_stays_auditable(self, tmp_path: Path) -> None:
        """The clamp is visible, as production keeps it visible in the stored reasoning:
        the model's own score stays in the row's raw verdict dump."""
        verdict = make_verdict(verdict="rejected", risk_score=90)

        row = await replay_item(FakeClient([verdict]), _still(tmp_path))

        assert row["raw_response"]["risk_score"] == 90
        assert row["risk_score"] < 90

    async def test_an_unclamped_verdict_reads_the_same_through_replay(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        verdict = make_verdict(verdict="confirmed", risk_score=85)

        analyzer, session, _ = make_analyzer(monkeypatch, client=FakeClient([verdict]))
        event = await analyze(analyzer)
        row = await replay_item(FakeClient([verdict]), _still(tmp_path))

        assert (row["verdict"], row["risk_score"], row["risk_level"]) == (
            session.added[1].verdict,
            event.risk_score,
            event.risk_level,
        )


class TestFrameParity:
    @pytest.mark.parametrize("frames_mode", [None, "selector"], ids=["default", "selector"])
    @pytest.mark.parametrize(
        ("spread_setting", "spread_fires"),
        [(None, True), ("40", False)],
        ids=["shipped-spread", "spread-40"],
    )
    async def test_replay_feeds_the_frames_production_attaches(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        frames_mode: str | None,
        spread_setting: str | None,
        spread_fires: bool,
    ) -> None:
        """Both paths read the SAME setting: at the shipped 10 s the 30 s span spreads,
        and at 40 s it does not. A replay with its own spread constant would agree with
        production at one setting and fail at the other."""
        if spread_setting is not None:
            monkeypatch.setenv("KEY_FRAME_SPREAD_SECONDS", spread_setting)
            get_settings.cache_clear()
        frames = _spanning_frames(tmp_path)
        rows = [
            make_detection_row(
                i,
                camera_id=CAMERA,
                object_type="knife",
                confidence=confidence,
                detected_at=moment,
                file_path=str(frame),
            )
            for i, (frame, confidence, moment) in enumerate(frames, start=1)
        ]
        production_client = FakeClient([make_verdict()])
        analyzer, _, _ = make_analyzer(monkeypatch, client=production_client, detections=rows)
        await analyzer.analyze_batch("b1", camera_id=CAMERA, detection_ids=[1, 2, 3, 4, 5])
        attached = production_client.calls[0].image_paths
        # the spread fired (more than the class's one strongest frame) or did not
        assert (len(attached) > 1) is spread_fires

        item = EvalItem(
            item_id="span-1",
            media_paths=[str(frame) for frame, _, _ in frames],
            expected_label="incident",
            expected_risk_score=80,
            snapshot=AssessInput(
                camera_id=CAMERA,
                detections=[
                    {
                        "id": i,
                        "object_type": "knife",
                        "confidence": confidence,
                        "file_path": frame.name,  # the exported shape: the name in the set
                        "detected_at": moment.isoformat(),
                    }
                    for i, (frame, confidence, moment) in enumerate(frames, start=1)
                ],
                zones=["front_yard"],
                timestamp=SPAN_START.isoformat(),
            ),
            source="synthetic",
        )
        replay_client = FakeClient([make_verdict()])
        mode = {} if frames_mode is None else {"frames_mode": frames_mode}
        await replay_item(replay_client, item, **mode)

        assert replay_client.calls[0].image_paths == attached


class TestTheReportCountsTheGap:
    async def test_a_run_says_how_many_scores_clamped_and_items_fell_back(
        self, tmp_path: Path
    ) -> None:
        """A run reports its distance from production as counts: the clamps the
        invariant table made, and the items the default selector could not feed
        (a still names no frame per detection row, so it is fed its one image)."""
        clamped, plain = _item(tmp_path, 1), _item(tmp_path, 2)
        store = _store(tmp_path, [clamped, plain])
        client = ItemClient(
            {
                clamped.media_paths[0]: _verdict("rejected", 90),
                plain.media_paths[0]: _verdict("confirmed", 60),
            }
        )

        report = await run_replay(store, candidate="F@test", make_client=lambda: client)

        assert report["parity"] == {"clamped": 1, "fell_back": 2}
        assert report["frames_mode"] == "selector"
        assert report["selector_spread_seconds"] == get_settings().key_frame_spread_seconds
        # ISS-014: the run records the bands its levels and clamps came from.
        severity = get_severity_service()
        assert report["severity_thresholds"] == {
            "low_max": severity.low_max,
            "medium_max": severity.medium_max,
            "high_max": severity.high_max,
        }
