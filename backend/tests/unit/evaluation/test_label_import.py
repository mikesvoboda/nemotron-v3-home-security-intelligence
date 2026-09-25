"""P0.5 (spec §5/§8 step 0.5) label + eval-item import — CODE half.

Premise (ledger F9, owner ruling 2026-09-25): the feedback-UI labeling pass
has no running system to label, so the ≥100-benign/≥20-incident bar's label
PROVENANCE shifts to born-labeled synthetic generation (the generator knows
each clip's label). The import path and the size-check test are unchanged by
that ruling — they read labels, whoever minted them. The owner labeling
execution box stays open for a returning home stack (R8: an empty state, not
a deletion).

What this module does (plan Task 5 boxes):

  1. EventFeedback -> eval items per spec §5 ("Historical, post-switch" row):
     false_positive -> benign; missed_threat, or accurate on high -> incident
     with expected_severity (the SAME mapping control_freeze pins — one
     source for §5's table); keyed by source_event_id, which rides the
     item_id ("post-switch::{event_id}", no FK). Unlabeled events are NOT
     imported as labeled items and are excluded from the S2/S3 bar.
  2. Synthetic incidents: import path for the media-bearing scenarios that
     arrive after Task 0. Born-labeled: the label comes from where the
     generator placed the set (category/scenario), never invented here.
     Control = the OFFLINE-30B-REPLAY PLACEHOLDER (control_score None,
     control_source "offline-30b-replay-pending") — the replay harness
     itself is Phase 2's 2.1 and is deliberately NOT built here.
  3. Size bar enforced in code: an import never calls a <100-benign or
     <20-incident store "M0-complete" (spec §5 size: 100/20).

Tier split: this unit file pins the core on fabricated loaded rows and
tmp_path corpora (mirrors test_control_freeze.py). The real ORM read seam
(import_event / import_labeled_events over staged production rows) is pinned
by backend/tests/integration/test_p05_label_import.py on the live test PG.

Privacy (D10): fabricated rows + synthetic bytes under tmp_path only; the
store path is a required argument and EvalStore.put_item still decides
residence at write time.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from backend.evaluation.eval_store import EvalStore
from backend.evaluation.label_import import (
    FEEDBACK_KIND,
    GENERATED_KIND,
    M0_MIN_BENIGN,
    M0_MIN_INCIDENTS,
    ImportResult,
    import_generated_items,
    import_loaded_event,
    item_id_for_event,
    item_id_for_generated,
    m0_size_report,
    severity_floor,
    write_import_manifest,
)

pytestmark = [pytest.mark.unit, pytest.mark.timeout(120)]


# =============================================================================
# Fake loaded rows (fabricated; exactly the attributes the import reads)
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
        camera_id: str = "front_door",
    ):
        self.id = id_
        self.batch_id = f"batch-{id_}"
        self.camera_id = camera_id
        self.started_at = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)
        self.risk_score = risk_score
        self.summary = "Person at the door"
        self.detections = detections if detections is not None else []
        self.feedback = feedback
        self.llm_interaction = None


@pytest.fixture
def store_dir(tmp_path):
    d = tmp_path / "import-store"
    d.mkdir()
    return d


@pytest.fixture
def store(store_dir):
    s = EvalStore(store_dir / "eval.sqlite")
    yield s
    s.close()


def _media(tmp_path):
    src = tmp_path / "source-media"
    src.mkdir(exist_ok=True)
    img = src / "det.jpg"
    img.write_bytes(b"\xff\xd8synthetic-pretend-jpeg\xff\xd9")
    thumb = src / "det-thumb.jpg"
    thumb.write_bytes(b"\xff\xd8tiny-synthetic\xff\xd9")
    return img, thumb


def _labeled_event(tmp_path, feedback_type="false_positive", severity=None, event_id=101):
    img, thumb = _media(tmp_path)
    return FakeEvent(
        event_id,
        risk_score=85,
        detections=[FakeDetection(11, str(img), str(thumb))],
        feedback=FakeFeedback(feedback_type, severity),
    )


# =============================================================================
# Box 1: EventFeedback -> eval item per spec §5, keyed by source_event_id
# =============================================================================


class TestFeedbackMapping:
    """§5 mapping is ONE source (control_freeze.map_feedback) - these tests
    pin that the import actually routes through it and records what §5's
    'Historical, post-switch' row says about the CONTROL: a post-switch
    recorded verdict is NOT a control (the placeholder Nano-4B produced it),
    so every imported item carries the offline-30B-replay placeholder."""

    def test_false_positive_becomes_benign_item(self, store, store_dir, tmp_path):
        event = _labeled_event(tmp_path, "false_positive")
        res = import_loaded_event(event, store=store, store_media_dir=store_dir / "media")
        assert not res.skipped, res.reason
        assert res.kind == FEEDBACK_KIND
        assert res.label == "benign"
        assert res.label_source == "owner-feedback"
        item = store.get_item(res.item_id)
        assert item is not None
        assert item.expected_label == "benign"

    def test_missed_threat_becomes_incident_with_severity(self, store, store_dir, tmp_path):
        event = _labeled_event(tmp_path, "missed_threat", "critical")
        res = import_loaded_event(event, store=store, store_media_dir=store_dir / "media")
        assert not res.skipped, res.reason
        assert res.label == "incident"
        assert res.expected_severity == "critical"
        # §5 S3 semantics: the item's expected score is the owner-asserted
        # MINIMUM (the severity band floor), never the placeholder score.
        assert res.control_score is None  # control arrives with 2.1 replay
        item = store.get_item(res.item_id)
        assert item.expected_label == "incident"
        assert item.expected_risk_score == severity_floor("critical")

    def test_accurate_on_high_becomes_incident(self, store, store_dir, tmp_path):
        event = _labeled_event(tmp_path, "accurate")
        event.risk_score = 70  # high band (60-84): accurate endorses it
        res = import_loaded_event(event, store=store, store_media_dir=store_dir / "media")
        assert not res.skipped, res.reason
        assert res.label == "incident"
        assert res.expected_severity == "high"

    def test_accurate_on_low_is_not_a_label(self, store, store_dir, tmp_path):
        event = _labeled_event(tmp_path, "accurate", event_id=102)
        event.risk_score = 20  # accurate endorsed a LOW verdict -> not a label
        res = import_loaded_event(event, store=store, store_media_dir=store_dir / "media")
        assert res.skipped
        assert "no label" in res.reason
        assert store.get_item(item_id_for_event(102)) is None

    def test_severity_wrong_is_not_a_label(self, store, store_dir, tmp_path):
        event = _labeled_event(tmp_path, "severity_wrong", "medium")
        res = import_loaded_event(event, store=store, store_media_dir=store_dir / "media")
        assert res.skipped and "no label" in res.reason

    def test_control_placeholder_never_borrows_the_recorded_score(self, store, store_dir, tmp_path):
        """The event's own 42 score is the placeholder pipeline's verdict —
        §5 row 2 forbids using it as control; expected score comes from the
        owner's severity claim only."""
        event = _labeled_event(tmp_path, "missed_threat", "medium", event_id=103)
        event.risk_score = 42
        res = import_loaded_event(event, store=store, store_media_dir=store_dir / "media")
        assert not res.skipped, res.reason
        assert res.control_source == "offline-30b-replay-pending"
        assert res.control_score is None
        item = store.get_item(res.item_id)
        assert item.expected_risk_score == severity_floor("medium")
        assert item.expected_risk_score != 42


class TestKeyedBySourceEventId:
    def test_item_id_carries_the_event_id(self, store, store_dir, tmp_path):
        event = _labeled_event(tmp_path, event_id=777)
        res = import_loaded_event(event, store=store, store_media_dir=store_dir / "media")
        assert res.source_event_id == 777
        assert res.item_id == "post-switch::777"
        assert item_id_for_event(777) == "post-switch::777"

    def test_rerun_is_idempotent(self, store, store_dir, tmp_path):
        event = _labeled_event(tmp_path, event_id=104)
        first = import_loaded_event(event, store=store, store_media_dir=store_dir / "media")
        second = import_loaded_event(event, store=store, store_media_dir=store_dir / "media")
        assert not first.skipped
        assert second.skipped and "already" in second.reason

    def test_media_copied_into_store_survives_retention(self, store, store_dir, tmp_path):
        event = _labeled_event(tmp_path, event_id=105)
        res = import_loaded_event(event, store=store, store_media_dir=store_dir / "media")
        assert not res.skipped, res.reason
        assert len(res.media_paths) == 2
        for p in res.media_paths:
            assert Path(p).exists()
            assert store_dir / "media" in Path(p).parents
        assert store.get_item(res.item_id).media_paths == list(res.media_paths)

    def test_repo_resident_store_media_root_fails_the_run(self, store, tmp_path):
        # D10 mirror of the freeze's preflight: copies land wherever the
        # media root points, so a repo-resident root misconfigures the whole
        # run - a hard error, before anything is written.
        from backend.evaluation.label_import import LabelImportError

        event = _labeled_event(tmp_path, event_id=107)
        repo_root = Path(__file__).resolve().parents[4]
        bad_root = repo_root / "scratch-import-media"
        with pytest.raises(LabelImportError):
            import_loaded_event(event, store=store, store_media_dir=bad_root)
        assert not bad_root.exists()

    def test_event_without_detections_skips_loudly(self, store, store_dir, tmp_path):
        event = FakeEvent(106, feedback=FakeFeedback("false_positive"), detections=[])
        res = import_loaded_event(event, store=store, store_media_dir=store_dir / "media")
        assert res.skipped and "no detections" in res.reason


# =============================================================================
# Box 2: synthetic incidents — born-labeled, media-bearing, replay placeholder
# =============================================================================


def _make_corpus(
    root: Path,
    category: str,
    set_name: str,
    *,
    with_frames=1,
    risk=None,
    manifest=True,
    extra_ext=None,
):
    """Fabricated born-labeled generated corpus: <root>/<category>/<set>/ with
    expected_labels.json (+ manifest.json frames or bare media files)."""
    d = root / category / set_name
    d.mkdir(parents=True, exist_ok=True)
    labels = {"category": category, "scenario": set_name}
    if risk is not None:
        labels["risk"] = risk
    (d / "expected_labels.json").write_text(json.dumps(labels))
    frames = []
    for i in range(with_frames):
        name = f"frame_{i}.jpg"
        (d / name).write_bytes(b"\xff\xd8synthetic\xff\xd9")
        frames.append({"file": name})
    if extra_ext:
        (d / f"clip{extra_ext}").write_bytes(b"synthetic-video-bytes")
    if manifest:
        (d / "manifest.json").write_text(json.dumps(frames))
    return d


class TestSyntheticIncidentImport:
    def test_missing_corpus_is_a_hard_error(self, store, tmp_path):
        with pytest.raises(FileNotFoundError):
            import_generated_items(corpus_dir=tmp_path / "nope", store=store)

    def test_manifest_frames_import_with_born_label(self, store, tmp_path):
        _make_corpus(
            tmp_path, "threats", "break_in_attempt", risk={"min_score": 85, "max_score": 100}
        )
        rows = import_generated_items(corpus_dir=tmp_path, store=store)
        assert len(rows) == 1
        row = rows[0]
        assert not row.skipped, row.reason
        assert row.kind == GENERATED_KIND
        assert row.label == "incident"  # born from placement: threats/
        assert row.label_source == "born-labeled-scenario-spec"
        item = store.get_item(row.item_id)
        assert item.expected_label == "incident"
        # expected score = the set's declared risk band midpoint (same
        # discipline as load_synthetic_items), severity = that band's level
        assert item.expected_risk_score == 92  # (85+100)//2
        assert row.expected_severity == "critical"  # 92 > _HIGH_MAX 84

    def test_control_is_the_replay_placeholder_not_a_real_score(self, store, tmp_path):
        _make_corpus(tmp_path, "threats", "package_theft", risk={"min_score": 85, "max_score": 100})
        row = import_generated_items(corpus_dir=tmp_path, store=store)[0]
        # Phase 2.1 owns the offline 30B replay; NOTHING here may mint a
        # control score. The placeholder is named, visible and score-less.
        assert row.control_source == "offline-30b-replay-pending"
        assert row.control_score is None

    def test_benign_generated_set_has_no_severity_claim(self, store, tmp_path):
        _make_corpus(tmp_path, "normal", "delivery_driver", risk={"min_score": 10, "max_score": 30})
        row = import_generated_items(corpus_dir=tmp_path, store=store)[0]
        assert row.label == "benign"
        assert row.expected_severity is None

    def test_dir_scan_finds_bare_media_files_when_no_manifest(self, store, tmp_path):
        d = _make_corpus(
            tmp_path,
            "suspicious",
            "loitering",
            manifest=False,
            risk={"min_score": 35, "max_score": 60},
        )
        row = import_generated_items(corpus_dir=tmp_path, store=store)[0]
        assert not row.skipped, row.reason
        assert len(row.media_paths) == 1  # the bare .jpg, not the .json sidecars
        assert row.media_paths[0].endswith(".jpg")
        assert d.name in row.media_paths[0]

    def test_video_extensions_count_as_media(self, store, tmp_path):
        _make_corpus(tmp_path, "threats", "vandalism", with_frames=0, extra_ext=".mp4")
        row = import_generated_items(corpus_dir=tmp_path, store=store)[0]
        assert not row.skipped, row.reason
        assert row.media_paths[0].endswith(".mp4")

    def test_label_only_set_skips_loudly_never_invents_paths(self, store, tmp_path):
        # A set with NO media is the committed-corpus case: load_synthetic_items
        # already carries it as a DRAFT; the media-bearing import must skip it
        # loudly rather than freeze a fabricated path (D10).
        _make_corpus(tmp_path, "threats", "weapon_visible", with_frames=0, manifest=True)
        row = import_generated_items(corpus_dir=tmp_path, store=store)[0]
        assert row.skipped and "no media" in row.reason

    def test_manifest_escape_is_refused(self, store, tmp_path):
        d = _make_corpus(tmp_path, "threats", "casing", manifest=False)
        (d / "manifest.json").write_text(json.dumps([{"file": "../../../etc/passwd"}]))
        row = import_generated_items(corpus_dir=tmp_path, store=store)[0]
        assert row.skipped and "escapes" in row.reason

    def test_unreadable_label_set_skips_loudly(self, store, tmp_path):
        d = _make_corpus(tmp_path, "threats", "tailgating", manifest=False)
        (d / "expected_labels.json").write_text("{not json")
        rows = import_generated_items(corpus_dir=tmp_path, store=store)
        assert len(rows) == 1 and rows[0].skipped

    def test_rerun_is_idempotent(self, store, tmp_path):
        _make_corpus(
            tmp_path, "threats", "break_in_attempt", risk={"min_score": 85, "max_score": 100}
        )
        first = import_generated_items(corpus_dir=tmp_path, store=store)
        second = import_generated_items(corpus_dir=tmp_path, store=store)
        assert not first[0].skipped
        assert second[0].skipped and "already" in second[0].reason

    def test_generated_id_never_collides_with_draft_id(self):
        assert (
            item_id_for_generated("threats", "break_in_attempt")
            != "synthetic:threats:break_in_attempt"
        )
        assert item_id_for_generated("threats", "x", "vid9") == "generated:threats:x::vid9"


# =============================================================================
# Box 4: the 100/20 size bar is code, not vibes
# =============================================================================


def _put_labelled_item(store, item_id: str, label: str, score: int = 0):
    from backend.evaluation.assess_input import AssessInput, EvalItem

    store.put_item(
        EvalItem(
            item_id=item_id,
            media_paths=[],
            expected_label=label,
            expected_risk_score=score,
            snapshot=AssessInput(
                camera_id="synthetic-source", timestamp="1970-01-01T00:00:00+00:00"
            ),
            source="test",
        )
    )


class TestM0SizeBar:
    def test_bar_values_match_the_spec(self):
        assert (M0_MIN_BENIGN, M0_MIN_INCIDENTS) == (100, 20)

    def test_empty_store_is_not_m0_complete(self, store):
        rep = m0_size_report(store)
        assert rep["benign"] == 0 and rep["incidents"] == 0
        assert rep["m0_complete"] is False

    def test_99_benign_is_refused(self, store):
        for i in range(99):
            _put_labelled_item(store, f"b{i}", "benign")
        for i in range(20):
            _put_labelled_item(store, f"i{i}", "incident")
        rep = m0_size_report(store)
        assert rep["m0_complete"] is False
        assert any("benign" in r for r in rep["reasons"])

    def test_19_incidents_is_refused(self, store):
        for i in range(100):
            _put_labelled_item(store, f"b{i}", "benign")
        for i in range(19):
            _put_labelled_item(store, f"i{i}", "incident")
        rep = m0_size_report(store)
        assert rep["m0_complete"] is False
        assert any("incident" in r for r in rep["reasons"])

    def test_exactly_100_and_20_passes(self, store):
        for i in range(100):
            _put_labelled_item(store, f"b{i}", "benign")
        for i in range(20):
            _put_labelled_item(store, f"i{i}", "incident")
        rep = m0_size_report(store)
        assert rep["m0_complete"] is True
        assert rep["reasons"] == []

    def test_unlabeled_items_are_excluded_from_every_side_of_the_bar(self, store):
        # "" is the unlabeled sentinel (control_freeze doctrine); it counts
        # on NO side - the S2/S3 exclusion is arithmetic, not a flag.
        for i in range(250):
            _put_labelled_item(store, f"u{i}", "")
        rep = m0_size_report(store)
        assert rep["unlabeled"] == 250
        assert rep["benign"] == 0 and rep["incidents"] == 0
        assert rep["m0_complete"] is False

    def test_report_is_purely_reads_never_writes(self, store):
        n_before = store._db.execute("SELECT count(*) FROM items").fetchone()[0]
        m0_size_report(store)
        assert store._db.execute("SELECT count(*) FROM items").fetchone()[0] == n_before


class TestSeverityFloor:
    def test_floors_are_the_taxonomy_band_edges(self):
        assert severity_floor("low") == 0
        assert severity_floor("medium") == 30
        assert severity_floor("high") == 60
        assert severity_floor("critical") == 85

    def test_unknown_severity_honest_zero(self):
        assert severity_floor("whatever") == 0
        assert severity_floor(None) == 0


class TestManifest:
    def test_manifest_rows_includes_skips_with_reasons(self, store, store_dir, tmp_path, capsys):
        good = _labeled_event(tmp_path, "false_positive", event_id=201)
        bad = FakeEvent(202, feedback=FakeFeedback("severity_wrong"), detections=[])
        rows = [
            import_loaded_event(good, store=store, store_media_dir=store_dir / "media"),
            import_loaded_event(bad, store=store, store_media_dir=store_dir / "media"),
        ]
        p = write_import_manifest(rows, store_dir / "manifest.jsonl")
        lines = [json.loads(x) for x in p.read_text().splitlines()]
        assert len(lines) == 2
        by_id = {ln["item_id"]: ln for ln in lines}
        assert by_id["post-switch::201"]["skipped"] is False
        assert by_id["post-switch::202"]["skipped"] is True
        assert "no label" in by_id["post-switch::202"]["reason"]
        assert by_id["post-switch::201"]["kind"] == FEEDBACK_KIND
        assert "imported_at" in lines[0]


def test_import_result_is_a_dataclass_row():
    assert "item_id" in ImportResult.__dataclass_fields__
    assert "source_event_id" in ImportResult.__dataclass_fields__
