"""ISS-005 wiring: a long dwell gets its far frames into the batch.

The selector half (``select_key_frames``'s ``spread_seconds`` parameter) is
pinned in test_key_frame_selector.py. This file pins what only the analyzer
can answer:

  * ``build_frame_refs`` stamps ``capture_timestamp`` from the frame's own
    filename (the STRICT parse - never the row's arrival; a stamped unknown
    is None, because an unknown capture is not a span bound). Without a
    stamp, production's pairs never spread at all;
  * ``build_assess_request`` threads ``spread_seconds`` into selection, so a
    spanning pair's companions attach - and the ISS-033 reorder stamps them
    oldest-first like any other pick;
  * ``key_frame_ids`` must reproduce the SAME pick set: called without the
    spread (or without the timezone), it silently drops the frames whose
    provenance it is supposed to name - the filter is ``if p in by_path``,
    so the failure is a missing row, not an error;
  * with no timezone the arrival clock still spreads a spanning pair (the
    uniform-clock basis), and with ``spread_seconds`` unset the builder is
    byte-for-byte the shipped builder - the A/B baseline.

Fixture arithmetic (America/New_York, EDT = UTC-04:00): local 06:00:00 is
10:00:00Z, 06:00:40 is 10:00:40Z, 06:01:30 is 10:01:30Z - a 90 s dwell, far
outside the 10 s default threshold.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from backend.services.vlm_analyzer import (
    build_assess_context,
    build_assess_request,
    build_frame_refs,
    key_frame_ids,
)

ARRIVAL = datetime(2026, 9, 25, 15, 0, tzinfo=UTC)  # upload lag, hours later

F_START = "/media/front_door/snap/MDAlarm_20260925-060000.jpg"  # 10:00:00Z
F_MID = "/media/front_door/snap/MDAlarm_20260925-060040.jpg"  # 10:00:40Z
F_END = "/media/front_door/snap/MDAlarm_20260925-060130.jpg"  # 10:01:30Z
PLAIN_1 = "/media/front_door/det_1.jpg"  # unparseable names: capture unknown
PLAIN_2 = "/media/front_door/det_2.jpg"
PLAIN_3 = "/media/front_door/det_3.jpg"


def _row(
    det_id: int,
    *,
    file_path: str,
    confidence: float | None = 0.9,
    object_type: str = "person",
    detected_at: datetime = ARRIVAL,
) -> dict[str, Any]:
    return {
        "id": det_id,
        "camera_id": "front_door",
        "object_type": object_type,
        "confidence": confidence,
        "detected_at": detected_at,
        "file_path": file_path,
        "thumbnail_path": None,
        "track_id": None,
        "bbox": None,
    }


# One (camera, person) pair spanning 90 s of dwell time, confidence falling
# with time so the shipped peak pick is also the EARLIEST frame - a companion
# that shows up is unambiguously the spread's doing, not a re-order.
DWELL = [
    _row(1, file_path=F_START, confidence=0.90),
    _row(2, file_path=F_MID, confidence=0.80),
    _row(3, file_path=F_END, confidence=0.70),
]


def _request(
    rows: list[dict[str, Any]], *, capture_tz: str | None = None, spread: int | None = None
):
    context = build_assess_context(
        camera_id="front_door",
        detections=rows,
    )
    return build_assess_request(
        context=context, detections=rows, camera_timezone=capture_tz, spread_seconds=spread
    )


class TestFrameRefStamping:
    def test_a_foscam_name_stamps_the_capture_time_not_the_arrival(self) -> None:
        (ref,) = build_frame_refs(
            [_row(1, file_path=F_START)], "front_door", camera_timezone="America/New_York"
        )
        assert ref.capture_timestamp == int(datetime(2026, 9, 25, 10, 0, tzinfo=UTC).timestamp())
        # the two clocks answer different questions and both survive:
        assert ref.timestamp == int(ARRIVAL.timestamp())

    def test_an_unparseable_name_stamps_unknown(self) -> None:
        # Never arrival: an unknown capture is not a span bound (FrameRef doc).
        (ref,) = build_frame_refs(
            [_row(1, file_path=PLAIN_1)], "front_door", camera_timezone="America/New_York"
        )
        assert ref.capture_timestamp is None

    def test_without_a_timezone_nothing_stamps(self) -> None:
        # capture_time's scope rule: unset CAMERA_TIMEZONE changes nothing.
        (ref,) = build_frame_refs([_row(1, file_path=F_START)], "front_door")
        assert ref.capture_timestamp is None


class TestSpreadReachesTheRequest:
    def test_a_spanning_pair_attaches_its_far_stills_oldest_first(self) -> None:
        request = _request(DWELL, capture_tz="America/New_York", spread=10)
        assert request.image_paths == [F_START, F_MID, F_END]
        assert request.frame_capture_times == [
            "2026-09-25T10:00:00+00:00",
            "2026-09-25T10:00:40+00:00",
            "2026-09-25T10:01:30+00:00",
        ]

    def test_the_shipped_call_unchanged_yields_the_single_peak(self) -> None:
        """spread_seconds unset (the replay/A-B baseline call) is byte-for-byte
        the shipped builder: one pair, one peak frame."""
        request = _request(DWELL, capture_tz="America/New_York")
        assert request.image_paths == [F_START]
        assert request.frame_capture_times == ["2026-09-25T10:00:00+00:00"]

    def test_no_timezone_spreads_on_the_uniform_arrival_clock(self) -> None:
        """Plain names, three arrivals 240 s apart: the arrival-clock basis.
        Attach order is the selector's (companions by distance: newest, then
        the midpoint) - with no timezone ISS-033's reorder never runs."""
        rows = [
            _row(
                1,
                file_path=PLAIN_1,
                confidence=0.90,
                detected_at=datetime(2026, 9, 25, 12, 0, tzinfo=UTC),
            ),
            _row(
                2,
                file_path=PLAIN_2,
                confidence=0.80,
                detected_at=datetime(2026, 9, 25, 12, 2, tzinfo=UTC),
            ),
            _row(
                3,
                file_path=PLAIN_3,
                confidence=0.70,
                detected_at=datetime(2026, 9, 25, 12, 4, tzinfo=UTC),
            ),
        ]
        request = _request(rows, capture_tz=None, spread=10)
        assert request.image_paths == [PLAIN_1, PLAIN_3, PLAIN_2]
        assert request.frame_capture_times is None


class TestProvenanceReproducesTheSpreadPickSet:
    def test_key_frame_ids_name_every_attached_still(self) -> None:
        rows = DWELL
        request = _request(rows, capture_tz="America/New_York", spread=10)
        ids = key_frame_ids(
            request, detections=rows, camera_timezone="America/New_York", spread_seconds=10
        )
        by_id = {r["id"]: r["file_path"] for r in rows}
        assert [by_id[i] for i in ids] == request.image_paths

    def test_calling_ids_without_the_spread_would_silently_drop_a_frame(
        self,
    ) -> None:
        # Characterization of WHY the params thread: the provenance filter is
        # `if p in by_path`, so an unthreaded call returns the pre-spread ids
        # and the spread stills ship without a named evidence row - no error.
        rows = DWELL
        request = _request(rows, capture_tz="America/New_York", spread=10)
        assert key_frame_ids(request, detections=rows) == [1]


class TestAnalyzeBatchEndToEnd:
    """The production call site: assess gets the spread frames, the stored
    provenance names them, and the specialist stage describes the SHIPPED
    peak picks (its call deliberately stays unthreaded until its own probe).

    The fake session hands its whole fixture back for any detection SELECT
    and the harness's `analyze` posts batch "front_door"/[11], so the three
    dwell rows flow as one batch. The spy seam is the module-level import
    the analyzer itself patches (its own docstring's style note)."""

    async def test_batch_attaches_the_dwell_and_proves_it(self, monkeypatch) -> None:
        from backend.tests.unit.services.test_vlm_analyzer import (
            FakeClient,
            analyze,
            make_analyzer,
            make_verdict,
        )

        client = FakeClient([make_verdict()])
        analyzer, session, _ = make_analyzer(monkeypatch, client=client, detections=DWELL)
        # Pinned per-test so no .env drift can move the threshold this test
        # leans on (the SEV-note style of test_vlm_analyzer); the dwell's
        # clock is the filenames', so only the zone completes the pair.
        analyzer._settings = analyzer._settings.model_copy(
            update={"camera_timezone": "America/New_York", "key_frame_spread_seconds": 10}
        )
        await analyze(analyzer)
        shown = client.calls[0]
        assert shown.image_paths == [F_START, F_MID, F_END]
        assert shown.frame_capture_times == [
            "2026-09-25T10:00:00+00:00",
            "2026-09-25T10:00:40+00:00",
            "2026-09-25T10:01:30+00:00",
        ]
        verification = next(o for o in session.added if type(o).__name__ == "EventVerification")
        assert verification.key_frame_detection_ids == [1, 2, 3]

    async def test_the_specialist_texts_describe_the_shipped_peak_picks(self, monkeypatch) -> None:
        from backend.tests.unit.services.test_vlm_analyzer import (
            FakeClient,
            analyze,
            make_analyzer,
            make_verdict,
        )

        captured: list[Any] = []

        async def spy(**kwargs: Any) -> dict[str, str]:
            captured.append(kwargs["key_frame_paths"])
            return dict.fromkeys(("faces", "plates", "person_reid"), "unavailable: spy")

        monkeypatch.setattr("backend.services.vlm_analyzer.collect_specialist_outputs", spy)
        client = FakeClient([make_verdict()])
        analyzer, _, _ = make_analyzer(monkeypatch, client=client, detections=DWELL)
        analyzer._settings = analyzer._settings.model_copy(
            update={"camera_timezone": "America/New_York", "key_frame_spread_seconds": 10}
        )
        await analyze(analyzer)
        (picks,) = captured
        assert [f.file_path for f in picks] == [F_START]  # not the spread's 3
        # and the verifier still saw all three:
        assert client.calls[0].image_paths == [F_START, F_MID, F_END]
