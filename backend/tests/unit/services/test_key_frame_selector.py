"""Property tests for `key_frame_selector` (Phase 1.3, spec §2:100).

The selector's contract is a PROPERTY, not a table: for ANY multiset of
detection refs it returns a deterministic 0-4 frame set that (a) never
drops a camera/class the input contained without a higher-confidence
representative taking its slot, (b) prefers the best confidence per
camera/class, then most recent, and (c) carries paths only - never image
bytes (spec §6 privacy: stored rows reference images by path).

Hypothesis is the honest tool here because the interesting failures are
ordering/pathological-input cases (all-equal confidence, None confidence,
single camera with 50 classes) that a hand-written example table tends to
miss. Deterministic examples live alongside the properties for the
spec-named cases (the 1-4 bounds, the tie-break).
"""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from backend.services.key_frame_selector import (
    FrameRef,
    select_key_frames,
)

# deadline=None: the selector is pure CPU work; CI profile's 1000 ms deadline
# is not the property under test and slow CI boxes make it flaky.
_SETTINGS = settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])

_CONFIDENCE = st.one_of(st.none(), st.floats(min_value=0.0, max_value=1.0, allow_nan=False))

# A SMALL pool of stills, on purpose (added 2026-09-27). `st.text()` used to
# draw a unique path per row, which made every generated batch "one file per
# detection" - a shape no real batch has, because the detector emits one row
# per OBJECT over a shared `file_path`. The physical-still property below was
# invisible to the suite for exactly that reason: all its other invariants
# held while the still budget was being double-spent.
_FILE_PATHS = st.sampled_from([f"/export/foscam/img/{c}.jpg" for c in "abcdefgh"])

_FRAME = st.builds(
    FrameRef,
    detection_id=st.integers(min_value=1, max_value=10_000),
    camera_id=st.sampled_from(["front_door", "driveway", "back_yard"]),
    object_type=st.sampled_from(["person", "car", "dog", "package"]),
    confidence=_CONFIDENCE,
    timestamp=st.integers(min_value=1_700_000_000, max_value=1_700_001_000),
    file_path=_FILE_PATHS,
    thumbnail_path=st.one_of(
        st.none(), st.text(min_size=1, max_size=20).map(lambda s: f"/export/foscam/thumbs/{s}.jpg")
    ),
)


def _sorted_unique(frames: list[FrameRef]) -> list[FrameRef]:
    """Unique by detection_id, in a canonical input order - so properties
    speak about the SET the selector was handed."""
    seen: dict[int, FrameRef] = {}
    for f in frames:
        seen.setdefault(f.detection_id, f)
    return sorted(seen.values(), key=lambda f: f.detection_id)


class TestProperties:
    @_SETTINGS
    @given(st.lists(_FRAME, max_size=30))
    def test_never_exceeds_four_frames(self, frames: list[FrameRef]) -> None:
        assert len(select_key_frames(frames)) <= 4

    @_SETTINGS
    @given(st.lists(_FRAME, max_size=30))
    def test_output_is_a_subset_of_input_ids(self, frames: list[FrameRef]) -> None:
        pool = {f.detection_id for f in frames}
        assert {f.detection_id for f in select_key_frames(frames)} <= pool

    @_SETTINGS
    @given(st.lists(_FRAME, max_size=30))
    def test_no_still_is_shown_twice(self, frames: list[FrameRef]) -> None:
        """The frame budget counts STILLS, so the picks are distinct FILES -
        not merely distinct ids. `test_no_duplicate_detection_ids` alone
        allowed the same JPEG to fill all four slots."""
        picked = select_key_frames(frames)
        paths = [f.file_path for f in picked]
        assert len(paths) == len(set(paths))

    @_SETTINGS
    @given(st.lists(_FRAME, max_size=30))
    def test_no_duplicate_detection_ids(self, frames: list[FrameRef]) -> None:
        picked = [f.detection_id for f in select_key_frames(frames)]
        assert len(picked) == len(set(picked))

    @_SETTINGS
    @given(st.lists(_FRAME, max_size=30))
    def test_deterministic(self, frames: list[FrameRef]) -> None:
        """Same multiset -> same tuple, byte for byte. The replay story
        (2.1's frozen items re-running) depends on it: a selector that
        drifts with input arrival order makes a replay a different question."""
        first = select_key_frames(_sorted_unique(frames))
        second = select_key_frames(list(reversed(_sorted_unique(frames))))
        assert [f.detection_id for f in first] == [f.detection_id for f in second]

    @_SETTINGS
    @given(st.lists(_FRAME, max_size=30))
    def test_best_confidence_per_camera_class_is_never_lost_for_a_worse_one(
        self, frames: list[FrameRef]
    ) -> None:
        """Per (camera, class) the best-confidence frame dominates every
        other frame of that pair. If a pair's representative is missing from
        the result while a WORSE member of the same pair was taken, the
        priority order is wrong."""
        picks = select_key_frames(frames)
        picked_ids = {f.detection_id for f in picks}
        groups: dict[tuple[str, str], list[FrameRef]] = {}
        for f in _sorted_unique(frames):
            groups.setdefault((f.camera_id, f.object_type), []).append(f)
        for members in groups.values():
            best = max(members, key=lambda f: f.confidence if f.confidence is not None else -1.0)
            taken = [m for m in members if m.detection_id in picked_ids]
            for t in taken:
                if t.detection_id != best.detection_id:
                    worse_conf = t.confidence if t.confidence is not None else -1.0
                    best_conf = best.confidence if best.confidence is not None else -1.0
                    assert worse_conf >= best_conf, (
                        f"took a weaker member of {(best.camera_id, best.object_type)} "
                        f"while the best was available"
                    )

    @_SETTINGS
    @given(st.lists(_FRAME, max_size=30))
    def test_refs_are_paths_never_bytes(self, frames: list[FrameRef]) -> None:
        for f in select_key_frames(frames):
            assert isinstance(f.file_path, str)
            if f.thumbnail_path is not None:
                assert isinstance(f.thumbnail_path, str)

    @_SETTINGS
    @given(st.lists(_FRAME, min_size=1, max_size=30))
    def test_nonempty_input_never_returns_empty(self, frames: list[FrameRef]) -> None:
        """1-4 stills per batch (spec §2): a non-empty pool always yields at
        least one frame - an empty result would silently skip verification."""
        assert len(select_key_frames(frames)) >= 1

    def test_empty_input_yields_empty(self) -> None:
        assert select_key_frames([]) == []


def _frame(did: int, cam: str, cls: str, conf: float | None, ts: int) -> FrameRef:
    return FrameRef(
        detection_id=did,
        camera_id=cam,
        object_type=cls,
        confidence=conf,
        timestamp=ts,
        file_path=f"/export/foscam/{cam}/{did}.jpg",
        thumbnail_path=None,
    )


class TestOneStillOneSlot:
    """A still is a PHYSICAL thing: one image file. The frame budget is a
    budget of STILLS (spec §2's "1-4 key frames", and the ctx/slot arithmetic
    that sizes CTX_SIZE around 4 images), so two detections that share a
    `file_path` are the SAME still and can never claim two slots.

    This is not an edge case - it is the dominant shape of a real batch:
    `detector_client` emits one Detection ROW per object and gives every row
    the same `file_path` (:1184 loop over result["detections"]), and the
    video path additionally pins every extracted frame's rows to the one
    `.mp4` (:1174). A batch of one frame containing a person, a car and a
    dog is therefore three (camera, class) PAIRS on ONE FILE: under a
    detection-id-only dedupe the four-slot budget filled with the same JPEG
    up to four times, the verifier saw one image while the request claimed
    four, and the provenance row listed detections whose pixels were never
    shown. The property suite above never caught it because its generator
    draws `file_path` from `st.text()` - independent paths per row - so
    "unique detection ids" and "at most four frames" both held while the
    physical budget was being double-spent.
    """

    def _at(self, did: int, path: str, cls: str = "person", conf: float = 0.9) -> FrameRef:
        return FrameRef(
            detection_id=did,
            camera_id="cam_a",
            object_type=cls,
            confidence=conf,
            timestamp=100,
            file_path=path,
        )

    def test_objects_sharing_one_still_claim_one_slot(self) -> None:
        """Three objects, one JPEG (the detector's real output shape)."""
        frames = [
            self._at(1, "/media/cam_a/f1.jpg", "person", 0.90),
            self._at(2, "/media/cam_a/f1.jpg", "car", 0.80),
            self._at(3, "/media/cam_a/f1.jpg", "dog", 0.70),
        ]
        picked = select_key_frames(frames)
        assert len(picked) == 1, "one file, one slot"
        assert picked[0].detection_id == 1, "the best member represents the still"

    def test_distinct_stills_still_fill_the_budget(self) -> None:
        """The no-regression half: genuinely different frames still get their
        slots - the guard dedupes files, it does not cap a diverse batch."""
        frames = [self._at(i, f"/media/cam_a/f{i}.jpg", f"type{i}") for i in range(1, 7)]
        assert len(select_key_frames(frames)) == 4

    def test_a_shared_still_never_starves_the_distinct_ones(self) -> None:
        """The budget, spent honestly. One JPEG holding four objects, plus
        two more stills that each carry one weaker object. The crowded file
        supplies FOUR (camera, class) pairs, so pair-ranking hands it all
        four slots: the verifier receives the same image four times and the
        two genuinely different frames are never shown - the request's
        "1-4 key frames" is one frame wearing four hats. With a per-file
        budget, the crowded still gets the ONE slot it deserves and the
        distinct frames keep the other two."""
        crowded = [
            self._at(1, "/media/cam_a/f1.jpg", "person", 0.95),
            self._at(2, "/media/cam_a/f1.jpg", "car", 0.90),
            self._at(3, "/media/cam_a/f1.jpg", "dog", 0.85),
            self._at(4, "/media/cam_a/f1.jpg", "package", 0.80),
        ]
        # Classes the crowded file never carries, so each of these IS a pair
        # representative - and they still lose the PAIR ranking to the
        # crowded file's four, so today they are squeezed out entirely. Once
        # the budget is per STILL they get their two slots back.
        others = [
            self._at(5, "/media/cam_a/f2.jpg", "bicycle", 0.50),
            self._at(6, "/media/cam_b/f3.jpg", "backpack", 0.45),
        ]
        picked = select_key_frames(crowded + others)
        assert len(picked) == 3, "one crowded still + two distinct stills = three STILLS"
        assert len({f.file_path for f in picked}) == len(picked), "no file appears twice"
        assert {f.file_path for f in picked} == {
            "/media/cam_a/f1.jpg",
            "/media/cam_a/f2.jpg",
            "/media/cam_b/f3.jpg",
        }

    def test_the_representative_is_the_strongest_member_of_the_still(self) -> None:
        """Which detection id stands in for a shared file is not arbitrary:
        the strongest member wins, so the provenance row names a detection
        the model actually saw at its best confidence."""
        frames = [
            self._at(7, "/media/cam_a/f1.jpg", "car", 0.30),
            self._at(8, "/media/cam_a/f1.jpg", "person", 0.99),
        ]
        assert [f.detection_id for f in select_key_frames(frames)] == [8]


class TestSpecNamedCases:
    """The examples spec §2 words directly - the property suite above covers
    the general case; these pin the named ones."""

    def test_single_detection_returns_one_frame(self) -> None:
        picked = select_key_frames([_frame(1, "front_door", "person", 0.9, 100)])
        assert [f.detection_id for f in picked] == [1]

    def test_best_per_camera_class_then_most_recent_caps_at_four(self) -> None:
        frames = [
            _frame(1, "cam_a", "person", 0.90, 100),  # best (cam_a, person)
            _frame(2, "cam_a", "person", 0.50, 200),  # worse, newer
            _frame(3, "cam_a", "car", 0.70, 150),  # best (cam_a, car)
            _frame(4, "cam_b", "person", 0.80, 160),  # best (cam_b, person)
            _frame(5, "cam_b", "dog", 0.60, 170),  # best (cam_b, dog) - 4th slot
            _frame(6, "cam_b", "car", 0.55, 180),  # 5th pair -> must be squeezed out
        ]
        picked = [f.detection_id for f in select_key_frames(frames)]
        assert len(picked) == 4
        assert set(picked) == {1, 3, 4, 5}, "the four best representatives win, newest-first fill"
        assert 2 not in picked and 6 not in picked

    def test_most_recent_fill_when_pairs_exceed_slots(self) -> None:
        """More distinct (camera, class) pairs than slots: every pair ties on
        confidence, so the fill order is decided by recency alone (spec §2's
        'plus the most recent'). Newest-first, and the result keeps that
        order so a caller can show the freshest frame first."""
        frames = [
            _frame(1, "cam_a", "person", 0.50, 100),  # stalest -> squeezed out
            _frame(2, "cam_b", "person", 0.50, 300),
            _frame(3, "cam_c", "person", 0.50, 200),
            _frame(4, "cam_d", "person", 0.50, 400),
            _frame(5, "cam_e", "person", 0.50, 250),
        ]
        assert [f.detection_id for f in select_key_frames(frames)] == [4, 2, 5, 3]

    def test_none_confidence_sorts_last_not_as_zero(self) -> None:
        """A None confidence is honest-absent, not a 0.0 (the model this repo
        applies everywhere - detections.confidence is nullable)."""
        frames = [
            _frame(1, "cam_a", "person", None, 900),
            _frame(2, "cam_a", "person", 0.10, 100),
        ]
        picked = select_key_frames(frames)
        assert picked[0].detection_id == 2, "a real 0.10 beats an absent confidence"

    def test_same_pair_same_confidence_breaks_to_most_recent(self) -> None:
        frames = [
            _frame(1, "cam_a", "car", 0.70, 100),
            _frame(2, "cam_a", "car", 0.70, 500),
        ]
        picked = select_key_frames(frames)
        assert [f.detection_id for f in picked] == [2]
