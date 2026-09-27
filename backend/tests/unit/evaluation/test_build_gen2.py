"""Tests for `build_gen2` - eval-store generation 2 (Phase 2 plan, task 2.0).

WHY A SECOND GENERATION EXISTS AT ALL (measured on the frozen store,
2026-09-27, Phase 2 plan §0): the G0.4 freeze holds 421 items whose snapshot
keys are the PRE-rev-6 six - zero of them carry `specialist_outputs` at all -
and the store's own guard makes that unfixable in place (`put_item` raises
"is frozen; replaying over it changes content" on a changed fingerprint). A
replay over gen-1 would therefore send an empty specialist block on every
single item and measure a system 1.3b did not ship. The repo corpus has moved
on since the freeze (413 committed label sets vs the 408 frozen; the delta is
1.3b's five verdict-changing sets), so the fix is a NEW generation at a NEW
path, built by the shipped loaders - never an edit of the frozen file.

These tests are the discipline that keeps it that way: the builder must not
open the gen-1 path, must refuse to overwrite a generation whose items differ,
and must refuse to call a build "done" when zero items carry the specialist
block (which is exactly gen-1's defect, rebuilt and green).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from backend.evaluation.eval_store import EvalStore, build_gen2

REPO_ROOT = Path(__file__).resolve().parents[4]

# The committed corpus is repo content BY DESIGN (labels only, zero media -
# test_eval_store asserts the zero-media property itself). The stock frames are
# off-repo GPU-mount data, so tests stage a manifest instead of reading them.
CORPUS_DIR = REPO_ROOT / "data" / "synthetic"


def _stage_stock(tmp_path: Path, scenarios: list[str]) -> Path:
    """A stock media root in the shape `load_stock_items` reads (the
    TestStockLoader fixture's own shape), with throwaway bytes: the loaders
    path media, they never read it."""
    root = tmp_path / "stock"
    for scenario in scenarios:
        d = root / scenario
        # exist_ok: the idempotent-rebuild test stages the SAME root twice,
        # and the frame bytes are deterministic, so the second call is a no-op.
        d.mkdir(parents=True, exist_ok=True)
        frames = []
        for i in range(1, 3):
            f = d / f"{i:03d}.jpg"
            f.write_bytes(b"\xff\xd8z" * 9000)
            frames.append({"file": str(f), "license": "CC0", "title": f"File:{i}.jpg"})
        (d / "manifest.json").write_text(json.dumps(frames))
    return root


def _build(tmp_path: Path, scenarios: list[str] | None = None):
    stock, store_dir = _paths(tmp_path, scenarios)
    report = build_gen2(store_dir, corpus_dir=CORPUS_DIR, stock_root=stock)
    return report, EvalStore(store_dir / "eval.sqlite")


def _paths(tmp_path: Path, scenarios: list[str] | None = None):
    stock = _stage_stock(tmp_path, scenarios or ["casing", "delivery_driver"])
    return stock, tmp_path / "gen-2"


class TestBuildGen2:
    def test_builds_items_and_reports_aggregates(self, tmp_path) -> None:
        report, store = _build(tmp_path)
        rows = store._db.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        assert rows == report["items"]
        # 413 committed label sets + the two staged stock scenarios.
        assert report["items"] == 415
        assert report["with_media"] == 2, "only stock items carry media paths"
        assert store._db.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0
        assert store._db.execute("SELECT COUNT(*) FROM results").fetchone()[0] == 0

    def test_the_labels_match_the_committed_corpus(self, tmp_path) -> None:
        """Not a restatement of a remembered count: benign 136 / incident 277
        is what `load_synthetic_items` returns today, and 136+277=413 is the
        count 1.3b grew from 408 (the five specialist-context sets, two of them
        benign)."""
        report, _ = _build(tmp_path)
        assert report["benign"] == 136 + 1  # +1 staged benign stock scenario
        assert report["incident"] == 277 + 1

    def test_specialist_outputs_survive_the_freeze(self, tmp_path) -> None:
        """THE point of gen-2, and the pin gen-1 would fail: items with a
        declared `specialist_context` must land in the store WITH the rendered
        block readable back off the frozen payload."""
        report, store = _build(tmp_path)
        assert report["with_specialist_outputs"] == 5, (
            "1.3b committed exactly five specialist-context sets; 0 here is gen-1's defect rebuilt"
        )
        rows = store._db.execute("SELECT payload FROM items WHERE item_id LIKE '%SC-%'").fetchall()
        assert len(rows) == 5
        rendered = [json.loads(p)["snapshot"]["specialist_outputs"] for (p,) in rows]
        assert all(r for r in rendered), "a declared set never freezes to empty"

    def test_zero_specialist_items_fails_the_build_loud(self, tmp_path) -> None:
        """The discriminator. Point the builder at a corpus with no
        `specialist_context` and it must refuse, because a gen-2 with an empty
        specialist block on every item is the thing 2.0 exists to fix."""
        bare = tmp_path / "bare-corpus" / "normal" / "one_set"
        bare.mkdir(parents=True)
        (bare / "expected_labels.json").write_text(
            json.dumps(
                {
                    "source": "unit-fixture",
                    "category": "normal",
                    "video_id": "fixture",
                    "detections": [],
                    "scene": "a driveway",
                    "risk": {"min_score": 10, "max_score": 30},
                }
            )
        )
        stock = _stage_stock(tmp_path, ["casing"])
        with pytest.raises(RuntimeError, match="specialist"):
            build_gen2(tmp_path / "gen-bad", corpus_dir=bare.parent.parent, stock_root=stock)

    def test_gen1_is_never_touched(self, tmp_path) -> None:
        """D-P2-1: gen-2 is a NEW generation. A builder handed a path that
        already holds a store with DIFFERENT items must refuse rather than
        ride into it - the immutability the store enforces per item is exactly
        what this protects, and a build that opened gen-1 would trip it
        item-by-item with no aggregate explanation."""
        report, _ = _build(tmp_path)  # first build succeeds
        assert report["items"] == 415
        # A second build over the SAME generation with the SAME inputs is
        # idempotent (the store's identical re-put is a silent no-op). Same
        # paths matter: a re-staged stock root would change every item's
        # media_paths, which is a genuine content mutation, not a rebuild.
        stock, store_dir = _paths(tmp_path)
        again = build_gen2(store_dir, corpus_dir=CORPUS_DIR, stock_root=stock)
        assert again["items"] == report["items"]
        # But a DIFFERENT corpus into that same file is the mutation this forbids.
        bare = tmp_path / "bare2" / "normal" / "only"
        bare.mkdir(parents=True)
        (bare / "expected_labels.json").write_text(
            json.dumps(
                {
                    "source": "unit-fixture",
                    "category": "normal",
                    "video_id": "fixture",
                    "detections": [],
                    "scene": "a driveway",
                    "risk": {"min_score": 10, "max_score": 30},
                    "specialist_context": {"faces": {"total": 1, "match": "Dad"}},
                }
            )
        )
        with pytest.raises(RuntimeError, match="EXISTING"):
            build_gen2(store_dir, corpus_dir=bare.parent.parent, stock_root=stock)

    def test_store_path_is_created_and_outside_the_repo(self, tmp_path) -> None:
        """D10: the store lives off-repo and the builder creates its dir rather
        than failing on a missing parent (the CI PR #6678 lesson: an absent
        directory is a setup state, not a crash)."""
        target = tmp_path / "deep" / "nested" / "gen-2"
        stock = _stage_stock(tmp_path, ["casing"])
        build_gen2(target, corpus_dir=CORPUS_DIR, stock_root=stock)
        assert (target / "eval.sqlite").exists()
        assert not str(target).startswith(str(REPO_ROOT))

    def test_refuses_a_store_dir_inside_the_repo(self, tmp_path) -> None:
        """D10/F6: the eval store lives OFF-REPO by ruling - gen-1's whole path
        discipline rests on that, and a gen-2 built into the checkout would put
        a labeled corpus one `git add -A` from the privacy line."""
        stock = _stage_stock(tmp_path, ["casing"])
        with pytest.raises(RuntimeError, match="off-repo"):
            build_gen2(
                REPO_ROOT / "backend" / "tests" / "tmp-store" / "gen-2",
                corpus_dir=CORPUS_DIR,
                stock_root=stock,
            )
        assert not (REPO_ROOT / "backend" / "tests" / "tmp-store").exists()

    def test_missing_corpus_raises_file_not_found(self, tmp_path) -> None:
        stock = _stage_stock(tmp_path, ["casing"])
        with pytest.raises(FileNotFoundError):
            build_gen2(tmp_path / "g", corpus_dir=tmp_path / "nowhere", stock_root=stock)


class TestGen1IsStillFrozen:
    """The guard that motivated the generation, pinned at the NEW call site
    rather than inherited silently: if the freeze ever stops refusing a changed
    re-put, gen-2's reason to exist disappears AND the audit trail dies with it."""

    def test_a_changed_reput_still_raises(self, tmp_path) -> None:
        from backend.evaluation.assess_input import AssessInput, EvalItem

        db = tmp_path / "eval.sqlite"
        store = EvalStore(db)
        item = EvalItem(
            item_id="frozen-1",
            media_paths=[],
            expected_label="incident",
            expected_risk_score=80,
            snapshot=AssessInput(
                camera_id="cam",
                detections=[],
                zones=[],
                timestamp="2026-09-24T12:00:00+00:00",
            ),
        )
        store.put_item(item)
        changed = item.model_copy(update={"expected_risk_score": 81})
        with pytest.raises(ValueError, match="frozen"):
            store.put_item(changed)
        # and the stored bytes are still the original's
        row = (
            sqlite3.connect(str(db))
            .execute("SELECT payload FROM items WHERE item_id='frozen-1'")
            .fetchone()
        )
        assert json.loads(row[0])["expected_risk_score"] == 80
