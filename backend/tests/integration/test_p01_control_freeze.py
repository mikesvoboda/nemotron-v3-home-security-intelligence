"""P0.1 (spec §5/§8 step 0.1) control freeze on the LIVE test Postgres:
the ORM read seam (`freeze_event` loads a staged production row and hands it
to the freeze core).

Why this tier: the plan's fixture branch is "sqlite or the test PG with rows
staged by fixture" - aiosqlite is not in this repo's dependency set, so the
real-DB branch runs here. The freeze CORE (label mapping, copy, snapshot,
manifest, guards) is pinned in backend/tests/unit/evaluation/
test_control_freeze.py on fabricated loaded rows; this file pins only what
needs a database: the eager load of detections/feedback/llm_interaction and
idempotence against a real store.

Premise (ledger F9): EXECUTION is ruled N/A (no pre-switch traffic exists);
this test exists so a returning production system can trust the tool (R8).

Privacy (D10): staged rows are fabricated and detection "images" are
synthetic bytes under tmp_path. No real imagery.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from backend.evaluation.control_freeze import freeze_event, item_id_for
from backend.evaluation.eval_store import EvalStore
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.models.event_detection import EventDetection
from backend.models.event_feedback import EventFeedback

pytestmark = pytest.mark.integration


@pytest.fixture
def store_dir(tmp_path):
    d = tmp_path / "freeze-store"
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
    img = src / "det.jpg"
    img.write_bytes(b"\xff\xd8synthetic-pretend-jpeg\xff\xd9")
    thumb = src / "det-thumb.jpg"
    thumb.write_bytes(b"\xff\xd8tiny-synthetic\xff\xd9")
    return img, thumb


async def _stage_event(db_session, tmp_path, with_feedback=True):
    cam = Camera(
        id=f"p01cam-{uuid.uuid4().hex[:8]}",
        name=f"p01-{uuid.uuid4().hex[:8]}",
        folder_path="/export/foscam/p01",
    )
    db_session.add(cam)
    await db_session.commit()
    img, thumb = _synthetic_media(tmp_path)
    event = Event(
        batch_id=str(uuid.uuid4()),
        camera_id=cam.id,
        started_at=datetime(2026, 9, 1, 8, 0, tzinfo=UTC),
        risk_score=85,
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
    if with_feedback:
        db_session.add(EventFeedback(event_id=event.id, feedback_type="false_positive"))
    await db_session.commit()
    return event


class TestFreezeEventOrmSeam:
    async def test_freeze_event_loads_staged_row_and_freezes_it(
        self, db_session, store, store_dir, tmp_path
    ):
        """freeze_event over the REAL eager-loaded ORM row: detections + the
        owner feedback arrive through the selectinload options, the images
        copy into the store, and the control is the RECORDED score."""
        event = await _stage_event(db_session, tmp_path)
        result = await freeze_event(
            session=db_session,
            event_id=event.id,
            store=store,
            store_media_dir=store_dir / "media",
        )
        assert not result.skipped, result.reason
        assert result.item_id == item_id_for(event.id)
        item = store.get_item(result.item_id)
        assert item is not None
        assert item.expected_risk_score == 85  # recorded 30B-era verdict
        assert item.expected_label == "benign"  # false_positive -> benign (§5)
        assert len(item.media_paths) == 2  # image + thumbnail, copied in
        for p in item.media_paths:
            assert Path(p).exists()
            assert store_dir / "media" in Path(p).parents

    async def test_freeze_event_missing_event_skips_loudly(self, db_session, store, store_dir):
        result = await freeze_event(
            session=db_session,
            event_id=999_999_999,
            store=store,
            store_media_dir=store_dir / "media",
        )
        assert result.skipped and "not found" in result.reason

    async def test_rerun_is_idempotent_no_second_item(self, db_session, store, store_dir, tmp_path):
        event = await _stage_event(db_session, tmp_path, with_feedback=False)
        first = await freeze_event(
            session=db_session, event_id=event.id, store=store, store_media_dir=store_dir / "media"
        )
        second = await freeze_event(
            session=db_session, event_id=event.id, store=store, store_media_dir=store_dir / "media"
        )
        assert not first.skipped
        assert second.skipped and "already frozen" in second.reason
        # one item, and the unlabeled event froze with the empty label
        assert store.get_item(first.item_id).expected_label == ""
