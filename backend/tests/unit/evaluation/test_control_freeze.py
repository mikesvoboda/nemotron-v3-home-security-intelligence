"""P0.1 (spec §5/§8 step 0.1) control-freeze tool - CODE half only.

Premise (ledger F9, owner ruling 2026-09-25, re-stated in the module
docstring): the freeze EXECUTION is deferred — the home system is offline
and no pre-switch traffic exists to timestamp, so execution is ruled N/A.
The tool ships tested so a returning production system can run it (R8: an
empty state, not a deletion). The 0.1-before-0.2 dormancy rule is intact.

What a freeze is (spec §5 "Historical, pre-switch" row):
  pre-switch Event -> EvalItem in the eval store:
    * the event's detection images COPIED INTO the store (retention can
      delete the originals - the item must survive that; cleanup keeps
      images by default, but the freeze copies anyway),
    * the AssessInput snapshot (camera, detections, timestamp),
    * the control = the verdict RECORDED on the event (its risk score /
      LLMInteraction) plus the owner's EventFeedback label
      (false_positive -> benign; missed_threat or accurate-on-high ->
      incident with expected_severity),
    * source_event_id provenance-only.
  Plus one manifest row per item: kind (historical-pre-switch), label
  source, control source.

Tier split: this unit file pins the freeze CORE (freeze_loaded_event) on
fabricated loaded rows - the plan's "fabricated rows" branch. The real ORM
read seam (freeze_event over a staged DB) is pinned by
backend/tests/integration/test_p01_control_freeze.py on the live test PG -
the plan's other branch, since aiosqlite is not in this repo's dependency
set and adding a runtime/test dependency is out of a slice's authority.

Privacy (D10): tests stage fabricated rows and synthetic bytes only, under
tmp_path (outside the repo). No real imagery exists in this repo or these
tests, and the store path is a required argument with EvalStore's write-time
guard deciding residence.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from backend.evaluation.control_freeze import (
    ControlFreezeError,
    FreezeResult,
    freeze_loaded_event,
    write_manifest,
)
from backend.evaluation.eval_store import EvalStore

pytestmark = [pytest.mark.unit, pytest.mark.timeout(120)]


# =============================================================================
# Fake loaded rows (fabricated; exactly the attributes the freeze reads -
# .id/.camera_id/.started_at/.risk_score/.detections/.feedback/.llm_interaction)
# =============================================================================


class FakeDetection:
    def __init__(self, id_: int, file_path: str, thumbnail_path: str | None = None):
        self.id = id_
        self.file_path = file_path
        self.thumbnail_path = thumbnail_path
        self.object_type = "person"
        self.confidence = 0.91
        self.bbox_x, self.bbox_y = 10, 20
        self.bbox_width, self.bbox_height = 30, 40
        self.detected_at = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)


class FakeFeedback:
    def __init__(self, feedback_type: str, expected_severity: str | None = None):
        self.feedback_type = feedback_type
        self.expected_severity = expected_severity


class FakeEvent:
    def __init__(
        self,
        id_: int,
        risk_score: int | None = 85,
        detections=None,
        feedback=None,
        llm_interaction=None,
        camera_id: str = "front_door",
    ):
        self.id = id_
        self.batch_id = f"batch-{id_}"
        self.camera_id = camera_id
        self.started_at = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)
        self.risk_score = risk_score
        self.summary = "Person at the door"
        self.detections = detections if detections is not None else [FakeDetection(11, "x")]
        self.feedback = feedback
        self.llm_interaction = llm_interaction


# =============================================================================
# Pure logic: label mapping + control resolution (spec §5 table, verbatim)
# =============================================================================


class TestLabelMapping:
    def test_false_positive_is_benign(self):
        from backend.evaluation.control_freeze import map_feedback

        assert map_feedback(FakeFeedback("false_positive")) == ("benign", None)

    def test_missed_threat_is_incident(self):
        from backend.evaluation.control_freeze import map_feedback

        label, sev = map_feedback(FakeFeedback("missed_threat", "high"))
        assert label == "incident"
        assert sev == "high"

    def test_accurate_on_high_is_incident(self):
        from backend.evaluation.control_freeze import map_feedback

        label, sev = map_feedback(FakeFeedback("accurate", None), event_risk_score=85)
        assert label == "incident"
        # expected minimum severity falls back to the event's OWN score band
        # (85 = critical under the severity taxonomy) - never left null for an
        # incident, since S3 scores recall "at or above their expected level"
        assert sev == "critical"

    def test_accurate_on_low_is_not_forced_incident(self):
        from backend.evaluation.control_freeze import map_feedback

        label, _sev = map_feedback(FakeFeedback("accurate", None), event_risk_score=20)
        assert label is None  # stays unlabeled -> excluded from S2/S3 (spec §5)

    def test_no_feedback_is_unlabeled(self):
        from backend.evaluation.control_freeze import map_feedback

        assert map_feedback(None) == (None, None)


class TestControlSource:
    def test_recorded_score_is_the_control_when_present(self):
        from backend.evaluation.control_freeze import resolve_control

        control = resolve_control(FakeEvent(1, risk_score=85))
        assert control == 85

    def test_null_score_falls_back_to_recorded_llm_response(self):
        """The 30B pipeline's raw response is the recorded verdict too - a
        NULL column must not lose a control that WAS recorded."""

        class LI:
            raw_response = '{"risk_score": 72}'

        from backend.evaluation.control_freeze import resolve_control

        assert resolve_control(FakeEvent(1, risk_score=None, llm_interaction=LI())) == 72

    def test_null_score_event_with_unparseable_response_has_no_control(self):
        class LI:
            raw_response = "not json"

        from backend.evaluation.control_freeze import resolve_control

        assert resolve_control(FakeEvent(1, risk_score=None, llm_interaction=LI())) is None


# =============================================================================
# freeze_loaded_event over fabricated loaded rows + synthetic bytes (tmp_path,
# OUTSIDE the repo - the D10 residence guard judges the resolved path)
# =============================================================================


def _media(tmp_path):
    src = tmp_path / "source-media"
    src.mkdir(exist_ok=True)
    img = src / "det-11.jpg"
    img.write_bytes(b"\xff\xd8synthetic-pretend-jpeg\xff\xd9")
    thumb = src / "det-11-thumb.jpg"
    thumb.write_bytes(b"\xff\xd8tiny-synthetic\xff\xd9")
    return img, thumb


@pytest.fixture
def store_dir(tmp_path):
    d = tmp_path / "eval-store"
    d.mkdir()
    return d


@pytest.fixture
def store(store_dir):
    s = EvalStore(store_dir / "eval.sqlite")
    yield s
    s.close()


def _freeze(store, store_dir, event):
    return freeze_loaded_event(
        event,
        store=store,
        store_media_dir=store_dir / "media",
    )


class TestFreezeLoadedEvent:
    def test_freeze_copies_images_into_store(self, store, store_dir, tmp_path):
        img, thumb = _media(tmp_path)
        event = FakeEvent(1, detections=[FakeDetection(11, str(img), str(thumb))])
        result = _freeze(store, store_dir, event)
        assert isinstance(result, FreezeResult)
        assert not result.skipped
        item = store.get_item(result.item_id)
        assert item is not None
        # images COPIED INTO the store (spec §5 "copied") and the item
        # references the copies, never the source paths
        assert item.media_paths, "media must be copied into the store"
        source_dir = tmp_path / "source-media"
        for p in item.media_paths:
            pp = __import__("pathlib").Path(p)
            assert store_dir in pp.parents or store_dir / "media" in pp.parents
            assert source_dir not in pp.parents
            assert pp.exists()
            assert pp.read_bytes() == (img if pp.name == img.name else thumb).read_bytes(), (
                "the copy must be the bytes, not a stub"
            )

    def test_freeze_snapshots_assess_input(self, store, store_dir, tmp_path):
        img, _thumb = _media(tmp_path)
        event = FakeEvent(2, detections=[FakeDetection(11, str(img))])
        result = _freeze(store, store_dir, event)
        item = store.get_item(result.item_id)
        assert item.snapshot.camera_id == event.camera_id
        assert item.snapshot.detections, "snapshot carries detection context"
        assert item.snapshot.timestamp == event.started_at.isoformat()
        # honest snapshot: zone/household state is NOT on event rows -> empty,
        # never invented (the eval_store stock-loader discipline)
        assert item.snapshot.zones == []
        assert item.snapshot.zone_crossing is False

    def test_recorded_verdict_is_the_control(self, store, store_dir, tmp_path):
        img, _thumb = _media(tmp_path)
        event = FakeEvent(3, risk_score=85, detections=[FakeDetection(11, str(img))])
        result = _freeze(store, store_dir, event)
        assert result.control_score == 85  # the RECORDED 30B-era score
        assert result.control_source == "recorded-30b"
        item = store.get_item(result.item_id)
        assert item.expected_risk_score == 85

    def test_provenance_is_source_event_id_only(self, store, store_dir, tmp_path):
        """Provenance rides the item_id (spec: source_event_id, provenance
        ONLY, no foreign key) - the EvalItem contract has no FK field and
        freezing must not invent production linkage."""
        img, _thumb = _media(tmp_path)
        event = FakeEvent(42, detections=[FakeDetection(11, str(img))])
        result = _freeze(store, store_dir, event)
        assert result.item_id == "pre-switch::42"
        assert result.source_event_id == 42
        # the store holds no production linkage beyond the id text itself
        assert store.get_item("event::42") is None

    def test_feedback_label_flows_through(self, store, store_dir, tmp_path):
        img, _thumb = _media(tmp_path)
        event = FakeEvent(
            4,
            detections=[FakeDetection(11, str(img))],
            feedback=FakeFeedback("false_positive"),
        )
        result = _freeze(store, store_dir, event)
        item = store.get_item(result.item_id)
        assert item.expected_label == "benign"
        assert result.label_source == "owner-feedback"

    def test_unlabeled_event_freezes_with_empty_label(self, store, store_dir, tmp_path):
        """Spec §5 requires an offline-30B control on EVERY item, so an
        unlabeled event still freezes - with the empty label (the frozen
        analogue of a NULL verdict) and label_source "none". Metrics/S2-S3
        skip empty labels; the item still gets its run."""
        img, _thumb = _media(tmp_path)
        event = FakeEvent(5, detections=[FakeDetection(11, str(img))])
        result = _freeze(store, store_dir, event)
        assert not result.skipped
        assert result.label == ""
        assert result.label_source == "none"
        assert store.get_item(result.item_id).expected_label == ""

    def test_manifest_written_per_item(self, store, store_dir, tmp_path):
        img, _thumb = _media(tmp_path)
        results = [
            _freeze(store, store_dir, FakeEvent(6, detections=[FakeDetection(11, str(img))]))
        ]
        manifest_path = tmp_path / "freeze-manifest.jsonl"
        write_manifest(results, manifest_path)
        lines = [json.loads(x) for x in manifest_path.read_text().splitlines() if x.strip()]
        assert len(lines) == 1
        row = lines[0]
        # "Freeze manifest: one JSON row per item - kind (historical-pre-switch),
        # label source, control source" (plan Task 1) - this is what "frozen"
        # means for M0.
        assert row["kind"] == "historical-pre-switch"
        assert set(row) >= {"item_id", "source_event_id", "label_source", "control_source"}

    def test_manifest_includes_loud_skips(self, store, store_dir):
        """A manifest that hides losses is not evidence: the skip row rides
        with its reason."""
        results = [_freeze(store, store_dir, FakeEvent(7, detections=[]))]
        manifest_path = store_dir.parent / "m2.jsonl"
        write_manifest(results, manifest_path)
        row = json.loads(manifest_path.read_text().splitlines()[0])
        assert row["skipped"] is True
        assert row["reason"]

    def test_freeze_is_idempotent(self, store, store_dir, tmp_path):
        img, thumb = _media(tmp_path)
        event = FakeEvent(8, detections=[FakeDetection(11, str(img), str(thumb))])
        first = _freeze(store, store_dir, event)
        second = _freeze(store, store_dir, event)
        assert first.item_id == second.item_id
        assert second.skipped  # frozen items are immutable (store doctrine)
        assert "already frozen" in (second.reason or "")

    def test_missing_media_loud_skip(self, store, store_dir, tmp_path):
        """An event whose detection file is gone (retention already ran?) is
        SKIPPED LOUDLY, not frozen with a broken path or a crash."""
        event = FakeEvent(9, detections=[FakeDetection(12, str(tmp_path / "gone.jpg"))])
        result = _freeze(store, store_dir, event)
        assert result.skipped and result.reason
        assert store.get_item(result.item_id) is None, "a skipped event writes no item"

    def test_no_control_score_loud_skip(self, store, store_dir, tmp_path):
        """NULL score AND no recorded response = no control to replay
        against: skip loudly, the manifest carries the reason."""
        img, _thumb = _media(tmp_path)
        event = FakeEvent(10, risk_score=None, detections=[FakeDetection(11, str(img))])
        result = _freeze(store, store_dir, event)
        assert result.skipped
        assert "no recorded control" in (result.reason or "")

    def test_media_root_inside_repo_fails_run_loudly(self, store, tmp_path):
        """D10: copies land wherever the media root points, so a media root
        INSIDE the repo checkout misconfigures the whole run - a raised
        ControlFreezeError (nothing written), not a per-event skip."""
        img, _thumb = _media(tmp_path)
        repo_media = Path(__file__).resolve().parents[4] / "eval-media-bad"
        with pytest.raises(ControlFreezeError):
            freeze_loaded_event(
                FakeEvent(11, detections=[FakeDetection(13, str(img))]),
                store=store,
                store_media_dir=repo_media,
            )
        assert not repo_media.exists(), "the preflight must fire before any write"

    def test_copy_refuses_source_inside_media_root(self, store, store_dir):
        """Recursive-copy-bomb guard: a source already inside the media tree
        the freeze copies INTO (e.g. a previously frozen copy) is refused -
        freezing a copy would silently re-point an item at another item's
        media."""
        media_root = store_dir / "media"
        media_root.mkdir(parents=True, exist_ok=True)
        inside = media_root / "sneaky.jpg"
        inside.write_bytes(b"\xff\xd8x\xff\xd9")
        event = FakeEvent(12, detections=[FakeDetection(14, str(inside))])
        result = _freeze(store, store_dir, event)
        assert result.skipped
        assert "inside the store root" in (result.reason or "")
