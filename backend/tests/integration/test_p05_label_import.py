"""P0.5 (spec §5/§8 step 0.5) label import on the LIVE test Postgres: the
ORM read seams (`import_event` loads a staged production row and hands it to
the import core; `import_labeled_events` sweeps every event that carries
feedback).

Why this tier: aiosqlite is not in this repo's dependency set, so the
real-DB branch runs here (same tier split as P0.1's
test_p01_control_freeze.py). The import CORE (label mapping, copy, media
sweep, size bar, manifest, guards) is pinned in backend/tests/unit/
evaluation/test_label_import.py on fabricated loaded rows; this file pins
only what needs a database: the eager loads, the feedback sweep, and
idempotence against a real store.

Premise (ledger F9): the feedback-UI labeling pass is ruled N/A for now
(nothing running to label); these tests exist so a returning home stack can
trust the import (R8), and they pin the §5 "post-switch" semantics whoever
minted the labels relies on.

Privacy (D10): staged rows are fabricated and detection "images" are
synthetic bytes under tmp_path. No real imagery.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from backend.evaluation.eval_store import EvalStore
from backend.evaluation.label_import import import_event, import_labeled_events
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.models.event_detection import EventDetection
from backend.models.event_feedback import EventFeedback

pytestmark = pytest.mark.integration


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


def _synthetic_media(tmp_path):
    src = tmp_path / "source-media"
    src.mkdir(exist_ok=True)
    img = src / f"det-{uuid.uuid4().hex[:6]}.jpg"
    img.write_bytes(b"\xff\xd8synthetic-pretend-jpeg\xff\xd9")
    thumb = src / f"det-thumb-{uuid.uuid4().hex[:6]}.jpg"
    thumb.write_bytes(b"\xff\xd8tiny-synthetic\xff\xd9")
    return img, thumb


async def _stage_event(db_session, tmp_path, *, feedback_type=None, severity=None, risk=85):
    cam = Camera(
        id=f"p05cam-{uuid.uuid4().hex[:8]}",
        name=f"p05-{uuid.uuid4().hex[:8]}",
        # folder_path is UNIQUE per camera - one staging helper serves
        # multi-camera tests, so the suffix must be per-call, not per-file.
        folder_path=f"/export/foscam/p05/{uuid.uuid4().hex[:8]}",
    )
    db_session.add(cam)
    await db_session.commit()
    img, thumb = _synthetic_media(tmp_path)
    event = Event(
        batch_id=str(uuid.uuid4()),
        camera_id=cam.id,
        started_at=datetime(2026, 9, 1, 8, 0, tzinfo=UTC),
        risk_score=risk,
    )
    db_session.add(event)
    await db_session.commit()
    det = Detection(
        camera_id=cam.id,
        file_path=str(img),
        thumbnail_path=str(thumb),
        object_type="person",
        confidence=0.91,
        detected_at=datetime(2026, 9, 1, 8, 0, tzinfo=UTC),
    )
    db_session.add(det)
    await db_session.commit()
    db_session.add(EventDetection(event_id=event.id, detection_id=det.id))
    if feedback_type:
        db_session.add(
            EventFeedback(
                event_id=event.id, feedback_type=feedback_type, expected_severity=severity
            )
        )
    await db_session.commit()
    return event


class TestImportEventOrmSeam:
    async def test_import_event_loads_staged_row_and_freezes_label(
        self, db_session, store, store_dir, tmp_path
    ):
        """import_event over the REAL eager-loaded ORM row: detections + the
        owner feedback arrive through selectinload, the images copy into the
        store, and the CONTROL is the replay placeholder, not the event's
        own 42 (the placeholder-pipeline verdict is not a control, §5 row 2).
        """
        event = await _stage_event(
            db_session, tmp_path, feedback_type="missed_threat", severity="high", risk=42
        )
        result = await import_event(
            session=db_session,
            event_id=event.id,
            store=store,
            store_media_dir=store_dir / "media",
        )
        assert not result.skipped, result.reason
        assert result.source_event_id == event.id
        assert result.label == "incident"
        assert result.control_score is None
        assert result.control_source == "offline-30b-replay-pending"
        item = store.get_item(result.item_id)
        assert item is not None
        assert item.expected_label == "incident"
        assert item.expected_risk_score == 60  # high band floor, never the 42
        assert len(item.media_paths) == 2
        for p in item.media_paths:
            assert Path(p).exists()
            assert store_dir / "media" in Path(p).parents

    async def test_import_event_missing_event_skips_loudly(self, db_session, store, store_dir):
        result = await import_event(
            session=db_session,
            event_id=999_999_999,
            store=store,
            store_media_dir=store_dir / "media",
        )
        assert result.skipped and "not found" in result.reason

    async def test_rerun_is_idempotent_no_second_item(self, db_session, store, store_dir, tmp_path):
        event = await _stage_event(db_session, tmp_path, feedback_type="false_positive")
        first = await import_event(
            session=db_session, event_id=event.id, store=store, store_media_dir=store_dir / "media"
        )
        second = await import_event(
            session=db_session, event_id=event.id, store=store, store_media_dir=store_dir / "media"
        )
        assert not first.skipped
        assert second.skipped and "already" in second.reason
        assert store.get_item(first.item_id).expected_label == "benign"


class TestLabeledSweep:
    async def test_sweep_imports_only_events_carrying_feedback(
        self, db_session, store, store_dir, tmp_path
    ):
        """The sweep's candidate set is `join(Event.feedback)` - the DB
        constraint (one feedback row per event) means no fan-out; an
        unlabeled event never becomes a store row, which is what §5's
        'unlabeled excluded from S2/S3' looks like in code."""
        labeled = await _stage_event(db_session, tmp_path, feedback_type="false_positive")
        unlabeled = await _stage_event(db_session, tmp_path)  # no feedback row
        results = await import_labeled_events(
            session=db_session, store=store, store_media_dir=store_dir / "media"
        )
        ids = {r.source_event_id for r in results}
        assert labeled.id in ids
        assert unlabeled.id not in ids
        # the sweep may pick up rows from other tests' fixtures only if they
        # carry feedback; assert OUR pair's outcomes and the store contents
        by_id = {r.source_event_id: r for r in results}
        assert not by_id[labeled.id].skipped
        from backend.evaluation.label_import import item_id_for_event

        assert store.get_item(item_id_for_event(unlabeled.id)) is None

    async def test_explicit_ids_include_unlabeled_as_loud_skips(
        self, db_session, store, store_dir, tmp_path
    ):
        """Named ids still get a manifest row for an unlabeled event - a
        loud skip, never a silent omission or a wrong import."""
        unlabeled = await _stage_event(db_session, tmp_path)
        results = await import_labeled_events(
            session=db_session,
            store=store,
            store_media_dir=store_dir / "media",
            event_ids=[unlabeled.id],
        )
        assert len(results) == 1
        assert results[0].skipped and "no label" in results[0].reason
