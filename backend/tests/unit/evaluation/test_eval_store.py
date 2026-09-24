"""Unit tests for the G0.4 eval-item schema and SQLite store.

Privacy invariant (design D10 / goal): real-camera imagery, labels and snapshots
never live under the repo. The store path is an explicit argument; production
callers pass a path outside the workspace (owner-confirmed, ledger F6). Tests
use tmp_path only.
"""

from __future__ import annotations

import pytest

from backend.evaluation.assess_input import AssessInput, EvalItem
from backend.evaluation.eval_store import EvalStore


def _item(i: int = 1, label: str = "incident") -> EvalItem:
    return EvalItem(
        item_id=f"syn-{i:04d}",
        media_paths=[],
        expected_label=label,
        expected_risk_score=80 if label == "incident" else 10,
        snapshot=AssessInput(
            camera_id="cam-front-door",
            detections=[{"class": "person", "confidence": 0.9, "bbox": [1, 2, 3, 4]}],
            zones=["front_yard"],
            zone_crossing=True,
            household={"known_residents": 2, "has_pets": True},
            timestamp="2026-09-24T12:00:00+00:00",
        ),
        source="synthetic",
    )


class TestAssessInput:
    def test_minimal_valid_snapshot(self) -> None:
        a = AssessInput(
            camera_id="c",
            detections=[],
            zones=[],
            zone_crossing=False,
            household={},
            timestamp="2026-09-24T00:00:00+00:00",
        )
        assert a.camera_id == "c"

    def test_rejects_missing_required_field(self) -> None:
        with pytest.raises(Exception):
            AssessInput(camera_id="c", detections=[], zones=[])  # type: ignore[call-arg]

    def test_freezes_when_items_exist(self) -> None:
        assert (
            AssessInput.model_config.get("frozen")
            or AssessInput.model_config.get("extra") == "forbid"
        )


class TestEvalStore:
    def test_roundtrip_item(self, tmp_path) -> None:
        with EvalStore(tmp_path / "eval.sqlite") as s:
            s.put_item(_item(1))
            got = s.get_item("syn-0001")
            assert got is not None and got.expected_label == "incident"

    def test_items_are_immutable(self, tmp_path) -> None:
        with EvalStore(tmp_path / "eval.sqlite") as s:
            s.put_item(_item(2))
            with pytest.raises(Exception):
                s.put_item(_item(2, label="benign"))  # same id, different content

    def test_record_run_result_and_replay(self, tmp_path) -> None:
        with EvalStore(tmp_path / "eval.sqlite") as s:
            s.put_item(_item(3))
            run = s.start_run(engine="llama.cpp@b7972", model="Qwen3-VL-4B-Instruct-Q4_K_M")
            s.put_result(
                run,
                "syn-0003",
                verdict="confirmed",
                risk_score=85,
                raw_response={"verdict": "confirmed", "risk_score": 85},
            )
            rows = s.replay(run)
            assert len(rows) == 1
            assert rows[0]["risk_score"] == 85

    def test_real_media_guard(self, tmp_path) -> None:
        """D10: refuse items whose media path points into the repo or a
        camera-capture root."""
        with EvalStore(tmp_path / "eval.sqlite") as s:
            item = _item(4)
            item = item.model_copy(update={"media_paths": ["/data/captures/frame.jpg"]})
            with pytest.raises(ValueError, match="privacy"):
                s.put_item(item)
