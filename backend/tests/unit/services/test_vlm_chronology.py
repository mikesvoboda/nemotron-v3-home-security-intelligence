"""ISS-033: a multi-frame prompt must say WHEN, not just rank (register acceptance).

The selector's picks are strongest-first, and `build_assess_request` used to
attach them in that order, so a 2-4 frame batch read as a confidence ranking
with no timeline: the register's evidence names the sort key, the pick-order
`image_paths`, and `build_frame_refs` using arrival time (or 0) where
`capture_time.py` had already parsed the filename. These tests pin the fix's
contract, phrased as the acceptance phrases them:

  * frames attached oldest-first — SELECTION stays strength-based; capture
    time may only reorder the picks, never add or drop one;
  * unknown capture time renders as unknown, NEVER as arrival time;
  * with `camera_timezone` unset nothing changes anywhere (the capture_time
    module's own scope rule) — the field is absent and prompts byte-identical;
  * `key_frame_ids` stays index-aligned with the reordered `image_paths`.

Fixture arithmetic (America/New_York, EDT = UTC-04:00): local 06:00 is
10:00 UTC, local 07:00 is 11:00 UTC. The `detected_at` arrivals sit hours away
from every filename time, so a test that ever leaked arrival into the
timeline fails loudly.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from backend.services.vlm_analyzer import (
    build_assess_context,
    build_assess_request,
    key_frame_ids,
)

CAPTURED_1_ISO = "2026-09-25T10:00:00+00:00"  # MDAlarm 060000 local
CAPTURED_3_ISO = "2026-09-25T11:00:00+00:00"  # MDAlarm 070000 local
ARRIVAL = datetime(2026, 9, 25, 15, 0, tzinfo=UTC)  # upload lag, hours later

FOSCAM_1 = "/media/front_door/snap/MDAlarm_20260925-060000.jpg"
FOSCAM_2 = "/media/front_door/snap/MDAlarm_20260925-063000.jpg"
FOSCAM_3 = "/media/front_door/snap/MDAlarm_20260925-070000.jpg"
PLAIN = "/media/front_door/det_9.jpg"  # unparseable name: capture time is unknown


def _row(
    det_id: int,
    *,
    file_path: str,
    confidence: float | None = 0.9,
    object_type: str = "person",
    detected_at: datetime = ARRIVAL,
) -> dict[str, Any]:
    """A detection dict in the shape production hands the builder (arrival
    in `detected_at`; capture time lives only in the filename)."""
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


def _request(rows: list[dict[str, Any]], *, capture_tz: str | None = None):
    tz = ZoneInfo(capture_tz) if capture_tz else None
    context = build_assess_context(
        camera_id="front_door",
        detections=rows,
        capture_tz=tz,
    )
    return build_assess_request(context=context, detections=rows, camera_timezone=capture_tz)


class TestOldestFirstOrder:
    """Selection stays strength-based; attachment order becomes capture-time order."""

    def test_picks_attach_oldest_first_regardless_of_confidence(self) -> None:
        # Distinct classes, so each still is its own (camera, class) pair and
        # the selector keeps all three; confidence DESCENDS with time, so the
        # old strength order is exactly newest-first — if the attachment order
        # came from the selector at all, this fails.
        rows = [
            _row(1, file_path=FOSCAM_1, confidence=0.60, object_type="person"),
            _row(2, file_path=FOSCAM_2, confidence=0.75, object_type="car"),
            _row(3, file_path=FOSCAM_3, confidence=0.90, object_type="dog"),
        ]
        request = _request(rows, capture_tz="America/New_York")
        assert request.image_paths == [FOSCAM_1, FOSCAM_2, FOSCAM_3]

    def test_capture_times_are_utc_iso_index_aligned_with_the_paths(self) -> None:
        rows = [
            _row(3, file_path=FOSCAM_3, confidence=0.90, object_type="dog"),
            _row(1, file_path=FOSCAM_1, confidence=0.60, object_type="person"),
        ]
        request = _request(rows, capture_tz="America/New_York")
        assert request.image_paths == [FOSCAM_1, FOSCAM_3]
        assert request.frame_capture_times == [CAPTURED_1_ISO, CAPTURED_3_ISO]

    def test_selection_is_untouched_only_the_order_moves(self) -> None:
        """The 4-frame budget and the per-pair strength pick are the
        selector's; the reorder may permute, never add or drop."""
        paths_and_confidence = [
            (FOSCAM_3, 0.95),
            (FOSCAM_1, 0.50),
            (PLAIN, 0.90),
            (FOSCAM_2, 0.55),
            ("/media/front_door/snap/MDAlarm_20260925-080000.jpg", 0.40),
        ]
        rows = [
            _row(index, file_path=path, confidence=confidence, object_type=f"type{index}")
            for index, (path, confidence) in enumerate(paths_and_confidence, start=1)
        ]
        reordered = _request(rows, capture_tz="America/New_York")
        selected = build_assess_request(
            context=build_assess_context(camera_id="front_door", detections=rows),
            detections=rows,
        )
        assert len(reordered.image_paths) == 4
        assert set(reordered.image_paths) == set(selected.image_paths), (
            "the un-reordered builder's pick set — the reorder may not edit the selection"
        )

    def test_unknown_time_sinks_to_the_end_after_the_known_chain(self) -> None:
        rows = [
            _row(1, file_path=FOSCAM_1, confidence=0.50, object_type="person"),
            _row(9, file_path=PLAIN, confidence=0.99, object_type="car"),
            _row(3, file_path=FOSCAM_3, confidence=0.40, object_type="dog"),
        ]
        request = _request(rows, capture_tz="America/New_York")
        assert request.image_paths == [FOSCAM_1, FOSCAM_3, PLAIN]
        assert request.frame_capture_times == [CAPTURED_1_ISO, CAPTURED_3_ISO, None]

    def test_two_unknowns_stay_in_the_strength_order_they_were_selected_in(self) -> None:
        """Unknowns sort stable: their relative order is the selector's pick
        order (strength), so the whole pipeline stays deterministic."""
        rows = [
            _row(1, file_path="/media/a/det_1.jpg", confidence=0.90, object_type="person"),
            _row(2, file_path="/media/a/det_2.jpg", confidence=0.80, object_type="car"),
        ]
        request = _request(rows, capture_tz="America/New_York")
        assert request.image_paths == ["/media/a/det_1.jpg", "/media/a/det_2.jpg"]
        assert request.frame_capture_times == [None, None]

    def test_key_frame_ids_stay_aligned_after_the_reorder(self) -> None:
        rows = [
            _row(1, file_path=FOSCAM_1, confidence=0.50, object_type="person"),
            _row(3, file_path=FOSCAM_3, confidence=0.95, object_type="dog"),
        ]
        request = _request(rows, capture_tz="America/New_York")
        assert request.image_paths == [FOSCAM_1, FOSCAM_3]
        assert key_frame_ids(request, detections=rows) == [1, 3]


class TestFieldIsAbsentUnlessTheTimezoneIsSet:
    """capture_time's scope rule: with CAMERA_TIMEZONE unset, nothing changes."""

    def test_no_timezone_means_no_field(self) -> None:
        request = _request([_row(1, file_path=FOSCAM_1)], capture_tz=None)
        assert request.frame_capture_times is None

    def test_field_is_none_by_default_so_old_stores_validate_unchanged(self) -> None:
        from backend.services.vlm_verdict import VlmAssessRequest

        request = VlmAssessRequest.model_validate(
            {
                "image_paths": ["/x/a.jpg"],
                "context": {
                    "camera_id": "c",
                    "detections": [],
                    "zones": [],
                    "timestamp": "2026-09-25T12:00:00+00:00",
                },
            }
        )
        assert request.frame_capture_times is None
