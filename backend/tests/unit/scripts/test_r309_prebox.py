"""Tests for scripts/uplevel/r309_prebox.py — the [r309] OWLv2 pre-box pass.

The pass must:
* read deliverable 1's selection list and refuse an empty/broken one (exit 2);
* keep detections at/above the score threshold, cap boxes per frame by score;
* write COCO (images carry stratum; annotations carry score) that stays
  host-side — paths only, no pixels;
* count per class and report unreadable frames rather than guessing past them;
* import its detector weights behind one seam (`load_owlv2`) so tests stub
  the model and never touch the network.

Fixtures write real (tiny) images with PIL itself — the pass actually
decodes frames, so a hand-rolled header-only PNG would fail `Image.open`
and fake an "unreadable frame" — and `Image.open` is exercised against
actual files, per UR-69 spirit (the test must be able to FAIL).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from PIL import Image

# Add project root to path for imports - must be before script imports
PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.uplevel import r309_prebox as prebox  # noqa: E402

# --- fixture builders -------------------------------------------------------


def write_frame(path: Path, width: int = 64, height: int = 48) -> None:
    """A real, decodable image file (PIL writes actual pixel data)."""
    Image.new("RGB", (width, height), color=(64, 96, 64)).save(path)


def selection_list(tmp_path: Path, relative: bool = False) -> Path:
    """A two-frame selection list over two real PNG frames of DISTINCT
    sizes, so a size-keyed fake detector can tell them apart."""
    root = tmp_path / "foscam"
    snap = root / "Front Yard" / "snap"
    snap.mkdir(parents=True)
    day_name = "MDAlarm_20260911-120000.jpg"
    night_name = "MDAlarm_20260911-020000.jpg"
    write_frame(snap / day_name, width=64, height=48)
    write_frame(snap / night_name, width=96, height=64)
    day_path = f"Front Yard/snap/{day_name}" if relative else str(snap / day_name)
    night_path = (f"Front Yard/snap/{night_name}" if relative
                  else str(snap / night_name))
    sel = {
        "selected": [
            {"path": day_path, "stratum": "day", "distant": False},
            {"path": night_path, "stratum": "night_ir", "distant": False},
        ],
    }
    p = tmp_path / "selection.json"
    p.write_text(json.dumps(sel))
    return p


class FakeDetector:
    """detect() returns (label, [x, y, w, h], score) keyed by PIL image size
    (each fixture frame has a distinct size)."""

    def __init__(self, script: dict[str, list[tuple[str, list[float], float]]]):
        self.script = script

    def detect(self, image, queries: list[str]):
        return list(self.script.get(str(image.size), []))


def stub_detector(monkeypatch, script) -> None:
    monkeypatch.setattr(prebox, "load_owlv2",
                        lambda model_dir, device: FakeDetector(script))


def run(argv: list[str], monkeypatch) -> None:
    """Drive the pass's main() in-process; SystemExit(2) propagates."""
    monkeypatch.setattr(sys, "argv", ["r309_prebox", *argv], raising=False)
    prebox.main()


# --- tests ------------------------------------------------------------------


def test_coco_carries_images_annotations_categories(
    tmp_path: Path, monkeypatch
) -> None:
    """A person above threshold and a sub-threshold vehicle: only the person
    survives; category ids resolve; the image carries its stratum."""
    sel = selection_list(tmp_path)
    out = tmp_path / "prebox.coco.json"
    stub_detector(monkeypatch, {
        "(64, 48)": [("person", [10, 10, 30, 40], 0.9),
                     ("vehicle", [1, 1, 8, 8], 0.1)],
    })
    run(["--selection", str(sel), "--root", str(tmp_path / "foscam"),
         "--out", str(out)], monkeypatch)
    coco = json.loads(out.read_text())
    assert [c["name"] for c in coco["categories"]] == prebox.DEFAULT_CLASSES
    assert [c["id"] for c in coco["categories"]] == [1, 2]
    assert len(coco["images"]) == 2
    anns = coco["annotations"]
    assert len(anns) == 1
    assert anns[0]["category_id"] == 1  # person
    assert anns[0]["score"] == 0.9
    assert anns[0]["bbox"] == [10, 10, 30, 40]
    day = next(im for im in coco["images"] if im["file_name"].endswith("120000.jpg"))
    assert day["stratum"] == "day"


def test_max_per_frame_keeps_highest_scores(tmp_path: Path,
                                            monkeypatch) -> None:
    """More detections than --max-per-frame keeps the highest-scoring ones."""
    sel = selection_list(tmp_path)
    out = tmp_path / "prebox.coco.json"
    script = [("person", [0, 0, 10, 10], 0.5 + i / 10) for i in range(5)]
    stub_detector(monkeypatch, {"(64, 48)": script})
    run(["--selection", str(sel), "--root", str(tmp_path / "foscam"),
         "--out", str(out), "--max-per-frame", "3"], monkeypatch)
    coco = json.loads(out.read_text())
    scores = [a["score"] for a in coco["annotations"]]
    assert len(scores) == 3
    assert scores == sorted(scores, reverse=True)


def test_extra_queries_become_categories(tmp_path: Path, monkeypatch) -> None:
    """A detected extra lands as a category after the bake-off classes; an
    extra the pass found nothing for is dropped - 'any class the pre-box
    FINDS is kept', not every query that was sent."""
    sel = selection_list(tmp_path)
    out = tmp_path / "prebox.coco.json"
    stub_detector(monkeypatch, {
        "(64, 48)": [("package", [5, 5, 5, 5], 0.6)],
    })
    run(["--selection", str(sel), "--root", str(tmp_path / "foscam"),
         "--out", str(out), "--extra-queries", "package", "dog"], monkeypatch)
    coco = json.loads(out.read_text())
    names = [c["name"] for c in coco["categories"]]
    assert names == ["person", "vehicle", "package"]  # dog: zero hits, dropped
    pkg = coco["annotations"][0]
    assert pkg["category_id"] == 3
    assert pkg["score"] == 0.6
    assert "_label" not in pkg  # the working key never reaches the file


def test_unreadable_frame_is_counted_not_fatal(tmp_path: Path, monkeypatch,
                                               capsys) -> None:
    """A frame PIL cannot open is counted and skipped, not a crash."""
    root = tmp_path / "foscam"
    snap = root / "Front Yard" / "snap"
    snap.mkdir(parents=True)
    (snap / "MDAlarm_20260911-120000.jpg").write_bytes(b"not a png")
    write_frame(snap / "MDAlarm_20260911-020000.jpg")
    sel = tmp_path / "selection.json"
    sel.write_text(json.dumps({
        "selected": [
            {"path": str(snap / "MDAlarm_20260911-120000.jpg"),
             "stratum": "day", "distant": False},
            {"path": str(snap / "MDAlarm_20260911-020000.jpg"),
             "stratum": "night_ir", "distant": False},
        ],
    }))
    out = tmp_path / "prebox.coco.json"
    stub_detector(monkeypatch, {"(64, 48)": [("person", [0, 0, 4, 4], 0.8)]})
    run(["--selection", str(sel), "--root", str(root), "--out", str(out)],
        monkeypatch)
    coco = json.loads(out.read_text())
    assert len(coco["images"]) == 1  # the good frame only
    assert "unreadable" in capsys.readouterr().out


def test_empty_selection_refused(tmp_path: Path, monkeypatch) -> None:
    """An empty selection list is a refusal (exit 2), not an empty COCO."""
    broken = tmp_path / "empty.json"
    broken.write_text(json.dumps({"selected": []}))
    with pytest.raises(SystemExit) as excinfo:
        run(["--selection", str(broken), "--root", str(tmp_path),
             "--out", str(tmp_path / "out.json")], monkeypatch)
    assert excinfo.value.code == 2


def test_broken_selection_refused(tmp_path: Path, monkeypatch) -> None:
    """A selection entry without a path is a refusal (exit 2)."""
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps({"selected": [{"stratum": "day"}]}))
    with pytest.raises(SystemExit) as excinfo:
        run(["--selection", str(broken), "--root", str(tmp_path),
             "--out", str(tmp_path / "out.json")], monkeypatch)
    assert excinfo.value.code == 2


def test_missing_root_refused(tmp_path: Path, monkeypatch) -> None:
    """A missing --root is a refusal (exit 2)."""
    sel = selection_list(tmp_path)
    with pytest.raises(SystemExit) as excinfo:
        run(["--selection", str(sel), "--root", str(tmp_path / "nope"),
             "--out", str(tmp_path / "out.json")], monkeypatch)
    assert excinfo.value.code == 2


def test_relative_paths_join_root(tmp_path: Path, monkeypatch) -> None:
    """Relative selection paths resolve under --root (the host's own tree)."""
    sel = selection_list(tmp_path, relative=True)
    out = tmp_path / "prebox.coco.json"
    stub_detector(monkeypatch, {"(64, 48)": [("person", [0, 0, 4, 4], 0.8)]})
    run(["--selection", str(sel), "--root", str(tmp_path / "foscam"),
         "--out", str(out)], monkeypatch)
    coco = json.loads(out.read_text())
    assert len(coco["images"]) == 2
    assert [im["file_name"] for im in coco["images"]] == [
        "Front Yard/snap/MDAlarm_20260911-120000.jpg",
        "Front Yard/snap/MDAlarm_20260911-020000.jpg",
    ]
    # The stub only scripts the day frame's size, so one box total.
    assert len(coco["annotations"]) == 1
