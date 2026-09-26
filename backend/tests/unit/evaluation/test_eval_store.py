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
        # 408 G0 label sets + the 5 1.3b specialist-context cases
        assert len(items) == 413, "corpus moved out from under the loader"
        assert all(i.source == "synthetic" for i in items)
        # category mapping: normal -> benign, suspicious/threats -> incident
        by_label = {i.expected_label for i in items}
        assert by_label == {"benign", "incident"}
        # 134+2 normal (the 1.3b benign pair members) + 132+3 suspicious + 142
        # threats label sets (some dirs in the corpus carry no
        # expected_labels.json; the loader skips them)
        assert sum(1 for i in items if i.expected_label == "benign") == 136

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


class TestSyntheticSpecialistContext:
    """1.3b: verdict-changing synthetic cases. A label set may carry a
    `specialist_context` block - the scenario's declared specialist GIVEN
    (a known household face, a household plate, a tiny night face) - and the
    loader renders it into the snapshot's `specialist_outputs` through the
    SHIPPED classifier and text builders (never a literal string stored on
    the label set), so the F12 rule the plan pins - a gate-FAILING crop is
    `not identifiable`, never `unknown` - is proven through the same code the
    live stage uses, not restated in test copy.

    Texts are exactly what the VLM prompt carries in production
    (vlm_specialists.face_text/plate_text/reid_text, prompt hygiene ruling
    2026-09-26: one short model-facing line)."""

    @staticmethod
    def _write_set(tmp_path, name: str, labels: dict) -> Path:
        d = tmp_path / "suspicious" / name
        d.mkdir(parents=True)
        (d / "expected_labels.json").write_text(json.dumps(labels))
        return d

    def test_pre_rev6_label_sets_still_load_with_empty_outputs(self) -> None:
        """The 408 G0 label sets carry no specialist_context; every one of
        them keeps the empty default (the pre-rev-6 round-trip rule - the
        ONLY sets carrying specialist_context are the 1.3b cases, asserted
        separately)."""
        items = load_synthetic_items(REPO_ROOT / "data" / "synthetic")
        one_thirdb = {
            "resident_arrival_known_face",
            "casing_unknown_face",
            "night_approach_tiny_face",
            "vehicle_parking_household_plate",
            "vehicle_visit_unknown_plate",
        }
        pre_rev6 = [i for i in items if i.item_id.split(":")[2] not in one_thirdb]
        assert len(pre_rev6) == 408
        assert all(i.snapshot.specialist_outputs == {} for i in pre_rev6)
        assert len(items) - len(pre_rev6) == 5

    def test_known_face_renders_the_shipped_match_line(self, tmp_path) -> None:
        self._write_set(
            tmp_path,
            "resident_casing_ambiguous",
            {
                "category": "suspicious",
                "detections": [{"class": "person", "min_confidence": 0.7, "count": 1}],
                "risk": {"min_score": 35, "max_score": 60},
                "specialist_context": {"faces": {"known_person": "Dad", "similarity": 0.72}},
            },
        )
        (item,) = load_synthetic_items(tmp_path)
        assert item.snapshot.specialist_outputs["faces"] == "known person Dad (72% match)"
        # "unknown" must not leak into a known-person scenario's line
        assert "unknown" not in item.snapshot.specialist_outputs["faces"]

    def test_tiny_night_face_is_not_identifiable_never_unknown(self, tmp_path) -> None:
        """F12's pinned clause, through the SHIPPED classifier: the case
        declares one gate-PASSING crop and one gate-FAILING crop; the face
        line counts the passing one as unknown and names the failing one
        not-identifiable - the ordering rule the classifier exists for."""
        self._write_set(
            tmp_path,
            "night_casing_tiny_face",
            {
                "category": "suspicious",
                "detections": [{"class": "person", "min_confidence": 0.7, "count": 1}],
                "scene": {"time_of_day": "night"},
                "risk": {"min_score": 35, "max_score": 60},
                "specialist_context": {"faces": {"unknown_count": 1, "tiny_count": 1}},
            },
        )
        (item,) = load_synthetic_items(tmp_path)
        line = item.snapshot.specialist_outputs["faces"]
        assert "1 unknown face(s)" in line  # the gate-PASSING crop
        assert "1 face(s) not identifiable (too small or low quality)" in line

    def test_tiny_face_alone_never_reads_unknown(self, tmp_path) -> None:
        self._write_set(
            tmp_path,
            "night_casing_only_tiny",
            {
                "category": "suspicious",
                "detections": [{"class": "person", "min_confidence": 0.7, "count": 1}],
                "risk": {"min_score": 35, "max_score": 60},
                "specialist_context": {"faces": {"tiny_count": 1}},
            },
        )
        (item,) = load_synthetic_items(tmp_path)
        assert item.snapshot.specialist_outputs["faces"] == (
            "1 face(s) not identifiable (too small or low quality)"
        )

    def test_gate_config_moves_the_loader_like_the_stage(self, tmp_path, monkeypatch) -> None:
        """The loader reads the SAME config knobs the live stage reads
        (get_settings().face_min_size_px): the same one-crop spec reads
        `unknown` under the shipped default floor and flips to
        `not identifiable` under a raised floor - config moves the floor,
        never the copy. House env+cache_clear idiom (unit/conftest)."""
        from backend.core.config import get_settings

        self._write_set(
            tmp_path,
            "small_face_high_floor",
            {
                "category": "suspicious",
                "detections": [{"class": "person"}],
                "risk": {"min_score": 35, "max_score": 60},
                # 120 px passes the shipped default floor (40) but fails 200
                "specialist_context": {"faces": {"unknown_count": 1, "unknown_face_px": 120}},
            },
        )
        (default_floor,) = load_synthetic_items(tmp_path)
        assert default_floor.snapshot.specialist_outputs["faces"] == "1 unknown face(s)"

        monkeypatch.setenv("FACE_MIN_SIZE_PX", "200")
        get_settings.cache_clear()
        try:
            (raised_floor,) = load_synthetic_items(tmp_path)
            assert raised_floor.snapshot.specialist_outputs["faces"] == (
                "1 face(s) not identifiable (too small or low quality)"
            )
        finally:
            monkeypatch.delenv("FACE_MIN_SIZE_PX", raising=False)
            get_settings.cache_clear()

    def test_plate_specs_render_the_shipped_grammar(self, tmp_path) -> None:
        self._write_set(
            tmp_path,
            "vehicle_visit",
            {
                "category": "suspicious",
                "detections": [{"class": "vehicle", "min_confidence": 0.7, "count": 2}],
                "risk": {"min_score": 35, "max_score": 60},
                "specialist_context": {
                    "plates": {
                        "plates": [
                            {"text": "ABC123", "household_member": "Dad's car"},
                            {"text": "XYZ789"},
                        ]
                    }
                },
            },
        )
        (item,) = load_synthetic_items(tmp_path)
        assert item.snapshot.specialist_outputs["plates"] == (
            "ABC123 - household vehicle (Dad's car); XYZ789 - not a household plate"
        )

    def test_absent_specialist_is_unavailable_never_silent(self, tmp_path) -> None:
        """A declared block must cover every specialist: the plan's rule is
        "a failing or ABSENT specialist records unavailable" - so declaring
        only faces still lands plates/person_reid lines (the shipped
        unavailable phrases), never an omitted or empty value that would
        read to the VLM as "not reported". Absent the whole block, the
        snapshot stays the pre-rev-6 empty dict."""
        self._write_set(
            tmp_path,
            "faces_only",
            {
                "category": "suspicious",
                "detections": [{"class": "person"}],
                "risk": {"min_score": 35, "max_score": 60},
                "specialist_context": {"faces": {"unknown_count": 1}},
            },
        )
        (item,) = load_synthetic_items(tmp_path)
        outs = item.snapshot.specialist_outputs
        assert set(outs) == {"faces", "plates", "person_reid"}
        assert outs["faces"] == "1 unknown face(s)"
        assert all(outs[k].startswith("unavailable") for k in ("plates", "person_reid"))
        self._write_set(
            tmp_path / "x",
            "no_context",
            {"category": "suspicious", "detections": [], "risk": {"min_score": 1, "max_score": 9}},
        )
        (legacy,) = load_synthetic_items(tmp_path / "x")
        assert legacy.snapshot.specialist_outputs == {}

    def test_malformed_spec_is_loud_and_unavailable_not_fabricated(self, tmp_path, caplog) -> None:
        """An unrenderable faces spec degrades that ONE key to the unavailable
        line and warns - the item still loads, like a malformed risk band
        scoring unknown rather than crashing the corpus."""
        self._write_set(
            tmp_path,
            "bad_spec",
            {
                "category": "suspicious",
                "detections": [],
                "risk": {"min_score": 1, "max_score": 9},
                "specialist_context": {"faces": {"telepathy": True}},
            },
        )
        with caplog.at_level("WARNING"):
            (item,) = load_synthetic_items(tmp_path)
        assert item.snapshot.specialist_outputs["faces"].startswith("unavailable")
        assert "bad_spec" in caplog.text

    def test_committed_verdict_changing_cases(self) -> None:
        """The 1.3b corpus additions, pinned through the committed corpus
        (not tmp fixtures): the two SCENES a human reads the same way flip
        ONLY on the specialist line, so the Phase 2 bake-off can measure
        whether the VLM uses it - and report whether S-3's `uncertain`
        hedging changes when the context is present."""
        items = {
            i.item_id.split("::")[0]: i
            for i in load_synthetic_items(REPO_ROOT / "data" / "synthetic")
        }
        face_pair = (
            "synthetic:normal:resident_arrival_known_face",
            "synthetic:suspicious:casing_unknown_face",
        )
        plate_pair = (
            "synthetic:normal:vehicle_parking_household_plate",
            "synthetic:suspicious:vehicle_visit_unknown_plate",
        )
        by_id = items

        # Benign half of each pair carries the reassuring line; suspicious
        # half carries the alarming one - through the SHIPPED builders.
        assert by_id[face_pair[0]].expected_label == "benign"
        assert by_id[face_pair[0]].snapshot.specialist_outputs["faces"] == (
            "known person Dad (78% match)"
        )
        assert by_id[face_pair[1]].expected_label == "incident"
        assert by_id[face_pair[1]].snapshot.specialist_outputs["faces"] == "1 unknown face(s)"
        assert by_id[plate_pair[0]].snapshot.specialist_outputs["plates"] == (
            "HOMETEST1 - household vehicle (Dad's car)"
        )
        assert by_id[plate_pair[1]].snapshot.specialist_outputs["plates"] == (
            "UNKNOWN9 - not a household plate"
        )

        # F12's pinned clause, committed: the tiny/night case is
        # not-identifiable and the word "unknown" never appears in its face line.
        tiny = by_id["synthetic:suspicious:night_approach_tiny_face"]
        assert tiny.snapshot.specialist_outputs["faces"] == (
            "1 face(s) not identifiable (too small or low quality)"
        )

        # Every case declared a block, so every case covers all three keys -
        # re-ID is the honest unavailable (its store stays cross-space).
        for k in face_pair + plate_pair + ("synthetic:suspicious:night_approach_tiny_face",):
            outs = by_id[k].snapshot.specialist_outputs
            assert set(outs) == {"faces", "plates", "person_reid"}
            assert outs["person_reid"].startswith("unavailable")


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
