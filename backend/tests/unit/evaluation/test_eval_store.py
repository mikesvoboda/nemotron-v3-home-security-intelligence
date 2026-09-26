"""Unit tests for the G0.4 eval-item schema, SQLite store, and synthetic loader.

Privacy invariant (design D10 / goal): real-camera imagery, labels and snapshots
never live under the repo. The store path is an explicit argument; production
callers pass a path outside the workspace (owner-confirmed, ledger F6). Tests
use tmp_path only - except the loader smoke over the repo's committed
`data/synthetic` label sets, which is repo content by design (labels only;
the corpus carries zero media files, asserted here).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from backend.evaluation.assess_input import AssessInput, EvalItem
from backend.evaluation.eval_store import EvalStore, load_stock_items, load_synthetic_items

REPO_ROOT = Path(__file__).resolve().parents[4]
# F5 stock frames live on the GPU mount (off-repo by ruling); absent on
# machines that never staged them - the one test that reads them says why.
GPU_STOCK = (
    Path(os.environ.get("AGENT_GPU_DIR", "/agents/agent-vss1/gpu")) / "out" / "media" / "stock"
)


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


class TestSpecialistOutputsField:
    """Rev 6 (F11 ruling 4): AssessInput reopens for EXACTLY one optional
    field, specialist_outputs, and the 421 pre-rev-6 items must still load."""

    def test_defaults_empty(self) -> None:
        a = AssessInput(
            camera_id="c",
            detections=[],
            zones=[],
            zone_crossing=False,
            household={},
            timestamp="2026-09-24T00:00:00+00:00",
        )
        assert a.specialist_outputs == {}

    def test_carries_short_texts(self) -> None:
        a = AssessInput(
            camera_id="c",
            detections=[],
            zones=[],
            timestamp="t",
            specialist_outputs={"face": "1 unknown adult", "plate": "ABC123, household"},
        )
        assert a.specialist_outputs["face"] == "1 unknown adult"

    def test_pre_rev6_item_still_loads(self) -> None:
        """The 421 frozen rows lack the key; model_validate_json over that
        exact stored JSON must succeed with the field defaulted — this is the
        ruling's load-pin, not a paraphrase of it."""
        pre_rev6_json = json.dumps(
            {
                "camera_id": "cam-front-door",
                "detections": [{"class": "person", "confidence": 0.9, "bbox": [1, 2, 3, 4]}],
                "zones": ["front_yard"],
                "zone_crossing": True,
                "household": {"known_residents": 2, "has_pets": True},
                "timestamp": "2026-09-24T12:00:00+00:00",
            }
        )
        a = AssessInput.model_validate_json(pre_rev6_json)
        assert a.specialist_outputs == {}
        assert "specialist_outputs" not in json.loads(pre_rev6_json)

    def test_extra_keys_still_forbidden(self) -> None:
        """The reopen is exactly one field — nothing else crept in."""
        with pytest.raises(Exception):
            AssessInput(
                camera_id="c",
                detections=[],
                zones=[],
                timestamp="t",
                specialist_outputs={},
                something_else=1,  # type: ignore[call-arg]
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

    def test_guard_refuses_repo_checkout_paths(self, tmp_path) -> None:
        """The repo root is refused by RESOLVED location - a stock frame
        staged inside the checkout is exactly the D10 leak class."""
        inside = REPO_ROOT / "fixtures" / "staged_frame.jpg"
        with EvalStore(tmp_path / "eval.sqlite") as s:
            item = _item(5).model_copy(update={"media_paths": [str(inside)]})
            with pytest.raises(ValueError, match="privacy"):
                s.put_item(item)

    def test_guard_refuses_case_twisted_repo_path(self, tmp_path) -> None:
        """G0 close-out audit #18: `/AGENTS/AGENT-VSS1/WORKSPACE/x.jpg` slipped
        past the resolved-path check (case-sensitive parents on Linux). Dead on
        Linux, live on any case-insensitive dev FS (the owner's Mac) - the
        cheap belt is a casefolded compare."""
        twisted = "/" + "/".join(REPO_ROOT.parts[1:]).upper() + "/staged.jpg"
        with EvalStore(tmp_path / "eval.sqlite") as s:
            item = _item(7).model_copy(update={"media_paths": [twisted]})
            with pytest.raises(ValueError, match="privacy"):
                s.put_item(item)

    def test_store_sets_a_busy_timeout(self, tmp_path) -> None:
        """Audit #12: a second writer hit 'database is locked' with no patience
        - a sharded freeze (2.1) would abort on the first contended write."""
        with EvalStore(tmp_path / "eval.sqlite") as s:
            ms = s._db.execute("PRAGMA busy_timeout").fetchone()[0]
            assert ms >= 30_000

    def test_guard_allows_off_repo_gpu_media(self, tmp_path) -> None:
        """F6 (owner-ruled): the GPU mount root is the sanctioned off-repo
        home for stock/eval media; the guard must not refuse it wholesale."""
        gpu_media = Path("/agents/agent-vss1/gpu/media/stock/front-door.jpg")
        with EvalStore(tmp_path / "eval.sqlite") as s:
            item = _item(6).model_copy(update={"media_paths": [str(gpu_media)]})
            s.put_item(item)  # must NOT raise
            assert s.get_item(item.item_id) is not None


class TestSyntheticLoader:
    """The committed label corpus is the item source; the loader turns each
    label set into a draft EvalItem WITHOUT freezing it (freezing waits on the
    owner's F6 store path and the pinned AssessInput shape)."""

    def test_loads_all_committed_label_sets(self) -> None:
        items = load_synthetic_items(REPO_ROOT / "data" / "synthetic")
        assert len(items) == 408, "corpus moved out from under the loader"
        assert all(i.source == "synthetic" for i in items)
        # category mapping: normal -> benign, suspicious/threats -> incident
        by_label = {i.expected_label for i in items}
        assert by_label == {"benign", "incident"}
        # 134 normal + 132 suspicious + 142 threats label sets (some dirs in
        # the corpus carry no expected_labels.json; the loader skips them)
        assert sum(1 for i in items if i.expected_label == "benign") == 134

    def test_label_set_becomes_valid_item(self) -> None:
        items = {i.item_id: i for i in load_synthetic_items(REPO_ROOT / "data" / "synthetic")}
        # dir casing_20260125_181203 under suspicious/ (fixed, committed set)
        it = next(i for k, i in items.items() if k.startswith("synthetic:suspicious:casing_"))
        assert it.expected_label == "incident"
        # expected score = risk band midpoint; casing declares 35-60 -> 47
        assert it.expected_risk_score == 47
        assert it.snapshot.camera_id == "synthetic-source"
        assert it.snapshot.detections, "detections must carry through"
        assert it.snapshot.zone_crossing is False  # never claimed from labels
        assert it.media_paths == [], "labels carry no media; loader invents none"

    def test_item_ids_are_unique(self) -> None:
        items = load_synthetic_items(REPO_ROOT / "data" / "synthetic")
        assert len({i.item_id for i in items}) == len(items)

    def test_refuses_missing_dir(self, tmp_path) -> None:
        with pytest.raises(FileNotFoundError):
            load_synthetic_items(tmp_path / "nowhere")

    def test_unreadable_set_is_skipped_not_fabricated(self, tmp_path) -> None:
        good = tmp_path / "normal" / "set_a"
        good.mkdir(parents=True)
        (good / "expected_labels.json").write_text(
            json.dumps(
                {
                    "category": "normal",
                    "detections": [{"class": "person"}],
                    "risk": {"min_score": 10, "max_score": 30},
                }
            )
        )
        bad = tmp_path / "normal" / "set_b"
        bad.mkdir()
        (bad / "expected_labels.json").write_text("{not json")
        items = load_synthetic_items(tmp_path)
        assert [i.item_id for i in items] == ["synthetic:normal:set_a"]

    def test_video_id_extends_the_id(self, tmp_path) -> None:
        d = tmp_path / "suspicious" / "casing_2026x"
        d.mkdir(parents=True)
        (d / "expected_labels.json").write_text(
            json.dumps(
                {
                    "category": "suspicious",
                    "video_id": "0007",
                    "detections": [],
                    "risk": {"min_score": 35, "max_score": 60},
                }
            )
        )
        (items,) = load_synthetic_items(tmp_path)
        assert items.item_id == "synthetic:suspicious:casing_2026x::0007"

    def test_loads_roundtrip_through_store(self, tmp_path) -> None:
        """Store wiring accepts label-derived items (plumbing evidence only -
        the items are drafts; freezing the corpus waits on F6)."""
        items = load_synthetic_items(REPO_ROOT / "data" / "synthetic")[:20]
        with EvalStore(tmp_path / "eval.sqlite") as s:
            for i in items:
                s.put_item(i)
            assert s.get_item(items[0].item_id) == items[0]


class TestStockLoader:
    """F5 imagery is on disk (Wikimedia Commons frames, off-repo), so the
    media-bearing items the S-3 re-run needs can now exist. Labels come from
    the committed corpus's OWN placement of each scenario, never a new call."""

    @staticmethod
    def _corpus(tmp_path, scenario: str = "casing", n: int = 2):
        d = tmp_path / scenario
        d.mkdir(parents=True)
        frames = []
        for i in range(1, n + 1):
            f = d / f"{i:03d}.jpg"
            f.write_bytes(b"\xff\xd8z" * 9000)
            frames.append({"file": str(f), "license": "CC0", "title": f"File:{i}.jpg"})
        (d / "manifest.json").write_text(json.dumps(frames))
        return d

    def test_loads_scenarios_with_real_media(self, tmp_path) -> None:
        self._corpus(tmp_path, "casing", 2)
        self._corpus(tmp_path, "delivery_driver", 1)
        items = load_stock_items(tmp_path)
        assert {i.item_id for i in items} == {"stock:casing", "stock:delivery_driver"}
        by_id = {i.item_id: i for i in items}
        assert by_id["stock:casing"].media_paths == [
            str(tmp_path / "casing" / "001.jpg"),
            str(tmp_path / "casing" / "002.jpg"),
        ]
        assert by_id["stock:delivery_driver"].source == "stock"

    def test_labels_inherit_the_committed_corpus(self, tmp_path) -> None:
        for s in ("casing", "loitering", "prowling", "tailgating"):
            self._corpus(tmp_path, s, 1)
        for s in ("break_in_attempt", "package_theft", "vandalism", "weapon_visible"):
            self._corpus(tmp_path, s, 1)
        for s in ("delivery_driver", "pet_activity", "yard_maintenance"):
            self._corpus(tmp_path, s, 1)
        labels = {i.item_id: i.expected_label for i in load_stock_items(tmp_path)}
        for s in ("casing", "loitering", "prowling", "tailgating", "break_in_attempt"):
            assert labels[f"stock:{s}"] == "incident"
        assert labels["stock:delivery_driver"] == "benign"

    def test_nothing_invented_in_the_snapshot(self, tmp_path) -> None:
        self._corpus(tmp_path, "casing", 1)
        (it,) = load_stock_items(tmp_path)
        assert it.expected_risk_score == 0, "a still frame carries no risk band"
        assert it.snapshot.detections == [], "detections are never claimed from a still"
        assert it.snapshot.zone_crossing is False
        assert it.snapshot.camera_id == "synthetic-source"
        assert it.snapshot.timestamp == "1970-01-01T00:00:00+00:00", "no invented timestamp"

    def test_unknown_scenario_skipped_loudly(self, tmp_path) -> None:
        self._corpus(tmp_path, "moonlanding", 1)
        assert load_stock_items(tmp_path) == []

    def test_manifest_without_frames_skipped(self, tmp_path) -> None:
        d = tmp_path / "casing"
        d.mkdir()
        (d / "manifest.json").write_text("[]")
        assert load_stock_items(tmp_path) == []

    def test_refuses_missing_root(self, tmp_path) -> None:
        with pytest.raises(FileNotFoundError):
            load_stock_items(tmp_path / "nowhere")

    def test_real_corpus_items_pass_the_d10_guard(self, tmp_path) -> None:
        """The frames live on the GPU mount OUTSIDE the checkout, so the D10
        guard must accept them - and it does only because residence is checked
        by resolved path. Frames themselves are never read, only pathed."""
        # (CI PR #6678: the absent-root case used to raise inside the loader
        # before this guard could skip it - machines without the GPU mount got
        # a FileNotFoundError instead of the declared skip. A missing corpus
        # IS "not staged", so it feeds the same guard; the production loader
        # still raises for real callers.)
        items = load_stock_items(GPU_STOCK) if GPU_STOCK.is_dir() else []
        if not items:
            pytest.skip("stock corpus not staged on this machine")
        assert {i.item_id for i in items} >= {"stock:casing", "stock:package_theft"}
        assert all(i.media_paths for i in items), "media-bearing is the whole point"
        with EvalStore(tmp_path / "eval.sqlite") as s:
            for i in items:
                s.put_item(i)
            assert s.get_item("stock:casing").media_paths

    # --- G0 close-out audit (wf_6b6035c7-9d3) regression guards ----------

    def test_manifest_paths_must_stay_in_their_scenario_dir(self, tmp_path) -> None:
        """D10 refuses repo/capture residence, but an off-repo path is NOT
        automatically scenario media: the audit drove a manifest naming
        /etc/shadow straight through the guard and into an item whose frames
        s3 would then base64-upload to the model. Frames live in their
        scenario directory (the fetcher's own contract) - containment is the
        loader's, not D10's, because D10 answers a different question."""
        d = tmp_path / "loitering"
        d.mkdir()
        (d / "manifest.json").write_text(
            json.dumps([{"file": "/etc/shadow", "license": "CC0", "title": "File:x.jpg"}])
        )
        assert load_stock_items(tmp_path) == [], "a traversal manifest must yield no item"

    def test_manifest_dotdot_escape_is_refused(self, tmp_path) -> None:
        d = tmp_path / "casing"
        d.mkdir()
        outside = tmp_path / "sneaky.jpg"
        outside.write_bytes(b"\xff\xd8z" * 9000)
        (d / "manifest.json").write_text(
            json.dumps([{"file": str(d / ".." / "sneaky.jpg"), "license": "CC0"}])
        )
        assert load_stock_items(tmp_path) == []

    def test_null_manifest_is_skipped_not_crash(self, tmp_path) -> None:
        """Audit class: valid-JSON/wrong-shape inputs crashed the loader
        (TypeError/AttributeError) where the contract is skip-loudly."""
        d = tmp_path / "casing"
        d.mkdir()
        (d / "manifest.json").write_text("null")
        assert load_stock_items(tmp_path) == []

    def test_string_risk_band_is_skipped_not_crash(self, tmp_path) -> None:
        """The synthetic twin: expected_labels.json with risk:"50" (a string)
        used to raise inside _midpoint's unpack."""
        d = tmp_path / "corpus" / "normal" / "set1"
        d.mkdir(parents=True)
        (d / "expected_labels.json").write_text(
            json.dumps({"category": "normal", "risk": "50", "detections": []})
        )
        items = load_synthetic_items(tmp_path / "corpus")
        assert len(items) == 1
        assert items[0].expected_risk_score == 0, "an unusable band reads as unknown, never a crash"

    def test_all_thirteen_scenarios_map(self) -> None:
        """The mapping must cover exactly the 13 spec-5 scenarios."""
        from backend.evaluation.eval_store import _SCENARIO_CATEGORY

        assert set(_SCENARIO_CATEGORY) == {
            "delivery_driver",
            "pet_activity",
            "resident_arrival",
            "vehicle_parking",
            "yard_maintenance",
            "casing",
            "loitering",
            "prowling",
            "tailgating",
            "break_in_attempt",
            "package_theft",
            "vandalism",
            "weapon_visible",
        }
        # ... and each agrees with where the committed corpus puts the name
        for scenario, category in _SCENARIO_CATEGORY.items():
            assert (REPO_ROOT / "data" / "synthetic" / category).is_dir()
