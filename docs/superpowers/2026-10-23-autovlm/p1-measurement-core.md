# P1: Measurement core

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Index and global constraints: [`README.md`](README.md).

**Goal:** A human can run `python -m autovlm eval` on a recipe and get honest, tier-scoped S2/S3 readings on blinded inputs, starting with the realistic baseline of the shipped stack.

**Architecture:** A new top-level `autovlm/` package. `blinding` turns a synthbench VSS export into label-free inputs plus a labels store; `splits` draws a three-tier scenario split; `stages` run the product's detector and VLM client; `scorer` computes S2/S3 with per-incident floors, the OD-26 paired test, tier-scoped answers and a query ledger; `checks` and `envelope` hold the mechanical checks and the noise floor. Everything is pure Python except the two stages, which are tested with fakes.

**Spec:** [`docs/auto-vlm-research/`](../../auto-vlm-research/README.md), sections `01` §3.1–3.6 and `02` §1–7.

**Interfaces verified at `origin/main` `9cb9e60b0`** (each task that uses one re-checks it in its Step 0):

| Interface                                                                                                                           | Shape relied on                                                                                                                                                                                                                                                                                                                        |
| ----------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `synthbench.export.vss.read_sets(export_dir) -> list[ExportedSet]`                                                                  | `.item_id`, `.category`, `.set_dir`, `.labels`, `.facts`, `.still`; labels keys `category`, `risk.min_score/max_score`, `timestamp`, `synthbench.label` (`benign`/`incident`), `synthbench.cell.scenario`, `synthbench.corpus_version`, `synthbench.kind`/`frame_files` for sequences; category dirs `normal`, `suspicious`, `threats` |
| `synthbench.export.vss.draw_split(corpus_version, incident_scenarios) -> {"seed", "k", "scenarios": [{"scenario", "rank_sha256"}]}` | holdout = first `k` rows                                                                                                                                                                                                                                                                                                               |
| `backend.evaluation.levels.floor_for_expected_score(int) -> str`                                                                    | `low`/`medium`/`high`/`critical`                                                                                                                                                                                                                                                                                                       |
| `backend.evaluation.cluster_stats.cluster_bootstrap_diff(pairs, *, resamples, seed)`                                                | pairs `(nb, fa_arm, fa_control, ni, hit_arm, hit_control)`; returns `point_pts`, `point3_pts`, `ci_pts`, `ci3_pts` (4-dp lists)                                                                                                                                                                                                        |
| `backend.evaluation.cluster_stats.cluster_bootstrap(clusters, *, resamples, seed)`                                                  | clusters `(n, k)`; returns `point_pct`, `ci_pct`                                                                                                                                                                                                                                                                                       |
| `backend.services.vlm_client.VlmClient(settings=, transport=, base_url=)`, `.assess(VlmAssessRequest) -> VlmVerdict`                | raises `VlmClientError` subclasses; `VlmTruncatedError` for a token-budget cut                                                                                                                                                                                                                                                         |
| `backend.services.vlm_verdict.VlmAssessRequest(image_paths: 1–4, context: VlmAssessContext)`                                        | context requires `camera_id`, `timestamp`; `detections` rows `{"object_type", "confidence", "bbox": [x, y, w, h]}`                                                                                                                                                                                                                     |
| `backend.core.config.get_settings()`                                                                                                | `.model_copy(update=...)`; `detection_class_thresholds`, `detection_confidence_threshold`, `foscam_base_path`, `camera_timezone`, `ai_vlm_read_timeout`                                                                                                                                                                                |
| ai-gateway `POST /yolo26/detect` (multipart `file`)                                                                                 | `{"detections": [{"class", "confidence", "bbox": {"x", "y", "width", "height"}}], "image_width", "image_height", "inference_time_ms"}`                                                                                                                                                                                                 |

**Known answers** (from `docs/benchmarks/synthbench/sweep-2026-10-03/` at `9cb9e60b0`, threshold 30):

| Arm               | False alarms | Hits      | Refusals | AUROC              | Recall at 5% (single cutoff) |
| ----------------- | ------------ | --------- | -------- | ------------------ | ---------------------------- |
| `control-q4km`    | 21 / 209     | 94 / 241  | 2        | 0.6770831265262364 | 42.32365145228216            |
| `qwen38-27b-q4km` | 16 / 209     | 119 / 241 | 0        | 0.810349619805833  | 61.82572614107884            |
| `gemma4-26b-a4b`  | 42 / 209     | 138 / 241 | 0        | 0.795251047271139  | 58.09128630705395            |

Paired against the control, seed 20261004, 10,000 resamples: 27B dS2 [−5.9524, 1.6216], dS3 [−0.5376, 24.0343] (no clear harm, no clear benefit); Gemma dS2 [−2.3026, 22.2222], dS3 [7.5893, 33.7079] (harm, benefit). The ISS-016 holdout roster for `tierb-v0` is `tailgating`, `blunt_weapon`, `car_break_in`, `casing_with_phone`, `knife_visible`, `peering_into_windows`; the corpus has 12 benign and 19 incident scenarios, none mixing labels.

## File structure

```
autovlm/
├── __init__.py            version
├── __main__.py            python -m autovlm
├── AGENTS.md              boundary guide
├── cli.py                 argparse root; COMMANDS registry
├── recipe.py              Recipe v1, load_recipe, stage_hashes, recipe_hash
├── recipes/shipped-8b.yaml
├── inputs.py              BlindedItem, load_items, select_frames
├── blinding.py            strip_jpeg_metadata, opaque_id, expected_floor, blind_export
├── splits.py              SplitManifest, draw_three_tier, reserved_from_iss016, read/write
├── checks.py              CheckResult and the six mechanical checks
├── envelope.py            Envelope, envelope, classify, jpeg_reencode
├── evaluate.py            run_items, readings, evaluate
├── scorer/
│   ├── __init__.py
│   ├── labels.py          LabelRow, read_labels, write_labels
│   ├── metrics.py         Flag, Rates, flags, rates, auroc_recall, threshold_for_s2
│   ├── stats.py           Paired, Od26, cluster_pairs, paired_test, od26
│   ├── tiers.py           HoldoutLocked, aggregates, answer
│   └── ledger.py          Query, QueryLedger
├── stages/
│   ├── __init__.py
│   ├── detector.py        DetectionRow, GatewayDetector
│   └── vlm.py             VlmOutcome, shipped_client, VlmStage
└── commands/
    ├── __init__.py
    ├── blind.py           autovlm blind
    ├── split.py           autovlm split
    └── eval_cmd.py        autovlm eval
backend/tests/unit/autovlm/
├── __init__.py, conftest.py, helpers.py
├── fixtures/sweep_items.csv
└── test_*.py              one per module
```

---

### Task 1: Package scaffold and tooling registration

**Files:**

- Create: `autovlm/__init__.py`, `autovlm/__main__.py`, `autovlm/cli.py`, `autovlm/AGENTS.md`
- Create: `backend/tests/unit/autovlm/__init__.py`, `backend/tests/unit/autovlm/conftest.py`, `backend/tests/unit/autovlm/test_cli.py`
- Modify: every tooling file that lists `synthbench` as a code root (Step 6)

**Interfaces:**

- Produces: `autovlm.cli.Command(help, add_arguments, run)`, `autovlm.cli.COMMANDS: dict[str, Command]`, `autovlm.cli.main(argv) -> int`

- [ ] **Step 0: Re-verify the test conventions**

Run: `sed -n 1,20p backend/tests/unit/synthbench/conftest.py; grep -n '"gpu' pyproject.toml; uv run python -c "import yaml, PIL, httpx, pydantic; print('ok')"`
Expected: the synthbench conftest imports `backend.core.config` and `backend.services.severity` at collection; a `gpu` marker is registered; `ok`. If the conftest changed, copy its current form in Step 2.

- [ ] **Step 1: Write the failing test**

`backend/tests/unit/autovlm/test_cli.py`:

```python
"""The autovlm command line."""

from __future__ import annotations

import pytest

from autovlm import __version__
from autovlm.cli import main


def test_version_prints_and_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"autovlm {__version__}"
```

- [ ] **Step 2: Add the test package and conftest**

`backend/tests/unit/autovlm/__init__.py`: empty.

`backend/tests/unit/autovlm/conftest.py`:

```python
"""Import the backend modules the inherited autouse fixtures import, at collection.

Same reason as backend/tests/unit/synthbench/conftest.py: pytest-timeout times setup, and
importing these lazily inside the first test's budget fails it under load.
"""

import importlib

for _module in ("backend.core.config", "backend.services.severity"):
    importlib.import_module(_module)
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest backend/tests/unit/autovlm/test_cli.py -n0 -p no:randomly`
Expected: FAIL with `ModuleNotFoundError: No module named 'autovlm'`

- [ ] **Step 4: Write the package**

`autovlm/__init__.py`:

```python
"""autovlm: an agentic search for VLM threat-detection accuracy.

Design: docs/auto-vlm-research/. Plan: docs/superpowers/2026-10-23-autovlm/.
"""

__version__ = "0.1.0"
```

`autovlm/__main__.py`:

```python
from autovlm.cli import main

raise SystemExit(main())
```

`autovlm/cli.py`:

```python
"""python -m autovlm <command>: exit 0 done, 1 error or incomplete run, 2 usage error."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from autovlm import __version__


@dataclass(frozen=True)
class Command:
    help: str
    add_arguments: Callable[[argparse.ArgumentParser], None]
    run: Callable[[argparse.Namespace], int]


COMMANDS: dict[str, Command] = {}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="autovlm", description=__doc__)
    parser.add_argument("--version", action="version", version=f"autovlm {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, command in sorted(COMMANDS.items()):
        command.add_arguments(sub.add_parser(name, help=command.help))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return COMMANDS[args.command].run(args)
```

`autovlm/AGENTS.md` (the boundary guide; extend it as tasks add modules):

```markdown
# autovlm — Agent Guide

## Purpose

An agentic search for VLM threat-detection accuracy. Design: `docs/auto-vlm-research/`. Plan:
`docs/superpowers/2026-10-23-autovlm/`.

## Rules

- Blinded inputs never carry labels, scenario names, categories, item ids, generation prompts or
  declared subjects and props. Only `autovlm/scorer/` reads the labels store.
- S3 keeps each incident's floor at every threshold: hit iff score >= max(threshold, floor).
- The holdout answers only the owner's confirmation; nothing here automates it.
- Tests live in `backend/tests/unit/autovlm/`; no GPU in unit tests (`@pytest.mark.gpu` otherwise).
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest backend/tests/unit/autovlm/test_cli.py -n0 -p no:randomly`
Expected: PASS

- [ ] **Step 6: Register `autovlm` wherever `synthbench` is registered as a code root**

Run: `grep -n "synthbench" pyproject.toml .pre-commit-config.yaml .github/workflows/ci.yml .agents-md-validator.yml`
For each hit that names `synthbench` as a **code root** (ruff and mypy file patterns, the CI path filters and `ruff check`/`ruff format --check` arguments, the mutation copy list, the AGENTS.md boundary list), add `autovlm` beside it the same way. Skip hits about synthbench's own dependencies or its per-file ruff targets. The boundary entry reads: `- path: autovlm` with `reason: 'lane root: the autovlm search harness (docs/auto-vlm-research)'`.

- [ ] **Step 7: Check and commit**

```bash
uv run ruff check autovlm backend/tests/unit/autovlm && uv run mypy autovlm
uvx pre-commit run --files autovlm/*.py autovlm/AGENTS.md backend/tests/unit/autovlm/*.py pyproject.toml .pre-commit-config.yaml .github/workflows/ci.yml .agents-md-validator.yml
git add autovlm backend/tests/unit/autovlm pyproject.toml .pre-commit-config.yaml .github/workflows/ci.yml .agents-md-validator.yml
git commit -m "feat(autovlm): scaffold the package and register it with the tooling"
```

---

### Task 2: Recipe v1

**Files:**

- Create: `autovlm/recipe.py`, `autovlm/recipes/shipped-8b.yaml`
- Test: `backend/tests/unit/autovlm/test_recipe.py`

**Interfaces:**

- Produces: `Recipe`, `FramesConfig(mode: "still"|"burst", count: 1..4)`, `DetectorConfig(model: "yolo26", thresholds: "shipped")`, `VlmConfig`, `DecisionConfig`; `load_recipe(path: Path) -> Recipe`; `stage_hashes(recipe) -> dict[str, str]` keyed `frames`, `detector`, `vlm`, `decision`; `recipe_hash(recipe) -> str`

- [ ] **Step 1: Write the failing tests**

`backend/tests/unit/autovlm/test_recipe.py`:

```python
"""Recipe v1: a detection stack as data."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from autovlm.recipe import Recipe, load_recipe, recipe_hash, stage_hashes

SHIPPED = Path(__file__).resolve().parents[4] / "autovlm" / "recipes" / "shipped-8b.yaml"


def _doc() -> dict:
    return {
        "recipe": 1,
        "inputs": "realistic",
        "vlm": {"model_sha256": "a" * 64, "mmproj_sha256": "b" * 64, "build": "b7972"},
    }


def test_minimal_recipe_takes_defaults() -> None:
    recipe = Recipe.model_validate(_doc())
    assert recipe.frames.mode == "still" and recipe.frames.count == 1
    assert recipe.detector.thresholds == "shipped"
    assert recipe.vlm.prompt == "shipped"


def test_oracle_inputs_are_refused() -> None:
    with pytest.raises(ValidationError):
        Recipe.model_validate(_doc() | {"inputs": "oracle"})


def test_unknown_keys_are_refused() -> None:
    with pytest.raises(ValidationError):
        Recipe.model_validate(_doc() | {"secret_knob": 1})


def test_more_than_four_frames_is_refused() -> None:
    with pytest.raises(ValidationError):
        Recipe.model_validate(_doc() | {"frames": {"mode": "burst", "count": 5}})


def test_stage_hashes_chain_downstream_only() -> None:
    base = Recipe.model_validate(_doc())
    new_vlm = Recipe.model_validate(_doc() | {"vlm": _doc()["vlm"] | {"build": "b11376"}})
    new_frames = Recipe.model_validate(_doc() | {"frames": {"mode": "burst", "count": 4}})
    a, b, c = stage_hashes(base), stage_hashes(new_vlm), stage_hashes(new_frames)
    assert a["detector"] == b["detector"] and a["vlm"] != b["vlm"]
    assert a["decision"] != b["decision"] and recipe_hash(base) == a["decision"]
    assert a["frames"] != c["frames"] and a["detector"] != c["detector"]


def test_shipped_recipe_loads() -> None:
    recipe = load_recipe(SHIPPED)
    assert recipe.vlm.build == "b7972"
    assert recipe.vlm.model_sha256.startswith("67d1659b")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest backend/tests/unit/autovlm/test_recipe.py -n0 -p no:randomly`
Expected: FAIL with `ModuleNotFoundError: No module named 'autovlm.recipe'`

- [ ] **Step 3: Write the module and the shipped recipe**

`autovlm/recipe.py`:

```python
"""Recipe v1: one detection stack as data (design 01 §3.1).

v1 covers what the shipped path does today: the product's detector and thresholds, one to four
frames, the shipped prompt, and the VLM score as the decision. Later phases add fields with
defaults, so an older recipe keeps its meaning.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FramesConfig(_Strict):
    mode: Literal["still", "burst"] = "still"
    count: int = Field(default=1, ge=1, le=4)  # VlmAssessRequest takes 1-4 images


class DetectorConfig(_Strict):
    model: Literal["yolo26"] = "yolo26"
    thresholds: Literal["shipped"] = "shipped"  # the product's per-class thresholds


class VlmConfig(_Strict):
    model_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    mmproj_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    build: str = Field(min_length=1)  # part of the identity: builds disagree (ISS-087)
    server: dict[str, str | int | float | bool] = Field(default_factory=dict)
    prompt: Literal["shipped"] = "shipped"
    parallel: int = Field(default=2, ge=1, le=8)


class DecisionConfig(_Strict):
    head: Literal["vlm-score"] = "vlm-score"


class Recipe(_Strict):
    recipe: Literal[1]
    inputs: Literal["realistic"]  # oracle inputs name the answer; never allowed
    frames: FramesConfig = FramesConfig()
    detector: DetectorConfig = DetectorConfig()
    vlm: VlmConfig
    decision: DecisionConfig = DecisionConfig()


STAGES: tuple[str, ...] = ("frames", "detector", "vlm", "decision")


def _digest(payload: object) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def stage_hashes(recipe: Recipe) -> dict[str, str]:
    """Each stage's hash covers its own config and every upstream stage's hash."""
    out: dict[str, str] = {}
    upstream = ""
    for stage in STAGES:
        config = getattr(recipe, stage).model_dump(mode="json")
        upstream = _digest({"stage": stage, "config": config, "upstream": upstream})
        out[stage] = upstream
    return out


def recipe_hash(recipe: Recipe) -> str:
    """The last stage's hash, which covers every stage."""
    return stage_hashes(recipe)[STAGES[-1]]


def load_recipe(path: Path) -> Recipe:
    return Recipe.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
```

`autovlm/recipes/shipped-8b.yaml` (weights and server settings from the 2026-10-06 dogfood replay):

```yaml
# The shipped stack at 9cb9e60b0: Qwen3-VL-8B-Instruct Q4_K_M on llama.cpp b7972, one still,
# the product's detector thresholds and prompt, the VLM score as the decision.
recipe: 1
inputs: realistic
frames:
  mode: still
  count: 1
detector:
  model: yolo26
  thresholds: shipped
vlm:
  model_sha256: 67d1659bfe71b89d50b45a4ad1a9e5b997e5bb16ce5da66a6a6167abd569e9e2
  mmproj_sha256: c6ba85508d82f42590e6eb77d5340369ab6fecf107a7561d809523d8aa5f3bfd
  build: b7972
  server:
    ctx-size: 32768
    parallel: 2
    batch-size: 2048
    ubatch-size: 512
    cache-type-k: q8_0
    cache-type-v: q8_0
    cache-reuse: 256
    flash-attn: 'on'
  prompt: shipped
  parallel: 2
decision:
  head: vlm-score
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest backend/tests/unit/autovlm/test_recipe.py -n0 -p no:randomly`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
uvx pre-commit run --files autovlm/recipe.py autovlm/recipes/shipped-8b.yaml backend/tests/unit/autovlm/test_recipe.py
git add autovlm/recipe.py autovlm/recipes backend/tests/unit/autovlm/test_recipe.py
git commit -m "feat(autovlm): recipe v1 with chained stage hashes"
```

---

### Task 3: Labels store, blinded items and blinding

**Files:**

- Create: `autovlm/scorer/__init__.py`, `autovlm/scorer/labels.py`, `autovlm/inputs.py`, `autovlm/blinding.py`
- Create: `backend/tests/unit/autovlm/helpers.py`
- Test: `backend/tests/unit/autovlm/test_blinding.py`

**Interfaces:**

- Consumes: `synthbench.export.vss.read_sets`, `backend.evaluation.levels.floor_for_expected_score`; `FramesConfig` (Task 2)
- Produces: `LabelRow(opaque_id, item_id, label, category, scenario, floor_score, corpus_version, s3_group=None)`; `write_labels(path, rows)`, `read_labels(path) -> list[LabelRow]`; `BlindedItem(opaque_id, timestamp, camera_id, frames: tuple[str, ...])`; `load_items(inputs_root) -> list[BlindedItem]`; `select_frames(item, frames: FramesConfig) -> tuple[str, ...]`; `strip_jpeg_metadata(bytes) -> bytes`; `opaque_id(salt, item_id) -> str`; `expected_floor(risk: dict) -> int`; `blind_export(export_dir, out_dir, salt, groups=None) -> BlindingSummary(items, inputs_dir, labels_file)`; constants `CAMERA_ID = "camera"`, `FIXED_MTIME`

- [ ] **Step 0: Re-verify the export interface**

Run: `uv run python -c "from synthbench.export.vss import read_sets, CATEGORY_LABEL; print(CATEGORY_LABEL)"; uv run python -c "from backend.evaluation.levels import floor_for_expected_score as f; print([f(x) for x in (20, 47, 65, 92)])"`
Expected: `{'normal': 'benign', 'suspicious': 'incident', 'threats': 'incident'}` and `['low', 'medium', 'high', 'critical']`. If either moved, update the imports and the helper below to match before continuing.

- [ ] **Step 1: Write the test helpers**

`backend/tests/unit/autovlm/helpers.py`:

```python
"""Builders shared by the autovlm tests."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from PIL import Image

from autovlm.scorer.labels import LabelRow

FIXTURES = Path(__file__).parent / "fixtures"
ARMS: tuple[str, ...] = ("control-q4km", "qwen38-27b-q4km", "gemma4-26b-a4b")


def jpeg_bytes(color: tuple[int, int, int] = (40, 80, 120), comment: bytes | None = None) -> bytes:
    """A small JPEG; with `comment`, a COM segment is spliced in right after SOI."""
    buf = io.BytesIO()
    Image.new("RGB", (32, 24), color).save(buf, format="JPEG", quality=90)
    data = buf.getvalue()
    if comment is None:
        return data
    segment = b"\xff\xfe" + (len(comment) + 2).to_bytes(2, "big") + comment
    return data[:2] + segment + data[2:]


def labels_doc(
    *,
    category: str,
    label: str,
    scenario: str,
    risk: tuple[int, int],
    frame_files: list[str] | None = None,
) -> dict[str, Any]:
    facts: dict[str, Any] = {
        "event_id": f"ev-{scenario}",
        "corpus_version": "test-v0",
        "batch": "B-test",
        "label": label,
        "risk_band": list(risk),
        "scene_time": "21:30",
        "cell": {"scenario": scenario, "camera": "doorbell_fisheye", "zone": "front_porch"},
        "subjects": [{"class": "person"}],
        "props": [{"class": "crowbar"}],
        "still_sha256": "0" * 64,
    }
    if frame_files is not None:
        facts |= {"kind": "sequence", "frame_files": frame_files}
    return {
        "category": category,
        "risk": {"min_score": risk[0], "max_score": risk[1]},
        "timestamp": "2026-04-15T21:30:00-04:00",
        "detections": [{"object_type": "crowbar", "confidence": 1.0}],
        "synthbench": facts,
    }


def write_set(export: Path, category: str, name: str, doc: dict[str, Any], files: dict[str, bytes]) -> None:
    set_dir = export / category / name
    set_dir.mkdir(parents=True)
    (set_dir / "expected_labels.json").write_text(json.dumps(doc), encoding="utf-8")
    for fname, data in files.items():
        (set_dir / fname).write_bytes(data)


def make_export(root: Path) -> Path:
    """A benign still, an incident still carrying a COM segment, and an incident sequence."""
    export = root / "export"
    write_set(
        export,
        "normal",
        "B-test-000",
        labels_doc(category="normal", label="benign", scenario="pool_service", risk=(0, 20)),
        {"still.jpg": jpeg_bytes()},
    )
    write_set(
        export,
        "suspicious",
        "B-test-001",
        labels_doc(
            category="suspicious", label="incident", scenario="peering_into_windows", risk=(50, 80)
        ),
        {"still.jpg": jpeg_bytes((90, 10, 10), comment=b"peering_into_windows prompt text")},
    )
    write_set(
        export,
        "threats",
        "B-test-002",
        labels_doc(
            category="threats",
            label="incident",
            scenario="car_break_in",
            risk=(85, 100),
            frame_files=["frame_1.jpg", "frame_2.jpg"],
        ),
        {"frame_1.jpg": jpeg_bytes((10, 10, 10)), "frame_2.jpg": jpeg_bytes((220, 220, 220))},
    )
    return export


def load_sweep() -> tuple[list[LabelRow], dict[str, dict[str, int | None]]]:
    """The 2026-10-03 sweep's 450 items: labels (opaque id = item id) and each arm's scores."""
    with (FIXTURES / "sweep_items.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    labels = [
        LabelRow(
            opaque_id=r["item_id"],
            item_id=r["item_id"],
            label=r["label"],
            category="",
            scenario=r["scenario"],
            floor_score=int(r["floor_level"]) if r["floor_level"] else None,
            corpus_version="tierb-v0",
            s3_group=r["s3_group"] or None,
        )
        for r in rows
    ]
    scores = {
        arm: {
            r["item_id"]: None if r[f"{arm}__score"] == "" else int(float(r[f"{arm}__score"]))
            for r in rows
        }
        for arm in ARMS
    }
    return labels, scores
```

- [ ] **Step 2: Write the failing tests**

`backend/tests/unit/autovlm/test_blinding.py`:

```python
"""Blinding: inputs that cannot reveal the answer."""

from __future__ import annotations

import io
import stat
from pathlib import Path

import pytest
from PIL import Image

from autovlm.blinding import FIXED_MTIME, blind_export, expected_floor, opaque_id, strip_jpeg_metadata
from autovlm.inputs import load_items, select_frames
from autovlm.recipe import FramesConfig
from autovlm.scorer.labels import read_labels

from .helpers import jpeg_bytes, make_export

FORBIDDEN = [
    b"pool_service", b"peering_into_windows", b"car_break_in", b"normal", b"suspicious",
    b"threats", b"benign", b"incident", b"B-test", b"crowbar", b"generated:", b"doorbell",
    b"front_porch",
]


def test_strip_drops_comment_and_keeps_pixels() -> None:
    original = jpeg_bytes(comment=b"secret scenario words")
    stripped = strip_jpeg_metadata(original)
    assert b"secret scenario words" in original
    assert b"secret scenario words" not in stripped
    assert Image.open(io.BytesIO(stripped)).tobytes() == Image.open(io.BytesIO(original)).tobytes()


def test_strip_refuses_non_jpeg() -> None:
    with pytest.raises(ValueError, match="not a JPEG"):
        strip_jpeg_metadata(b"\x89PNG\r\n\x1a\n")


def test_inputs_carry_no_answer(tmp_path: Path) -> None:
    summary = blind_export(make_export(tmp_path), tmp_path / "blind", salt="s")
    for path in summary.inputs_dir.rglob("*"):
        assert not any(word in path.name.encode() for word in FORBIDDEN), path
        if path.is_file():
            data = path.read_bytes()
            assert not any(word in data for word in FORBIDDEN), path


def test_labels_rows_floors_and_modes(tmp_path: Path) -> None:
    summary = blind_export(make_export(tmp_path), tmp_path / "blind", salt="s")
    rows = {r.scenario: r for r in read_labels(summary.labels_file)}
    assert rows["pool_service"].label == "benign" and rows["pool_service"].floor_score is None
    assert rows["peering_into_windows"].floor_score == 60  # midpoint 65 is high
    assert rows["car_break_in"].floor_score == 85  # midpoint 92 is critical
    assert stat.S_IMODE(summary.labels_file.stat().st_mode) == 0o600
    assert stat.S_IMODE(summary.labels_file.parent.stat().st_mode) == 0o700


def test_sequence_frames_keep_their_order(tmp_path: Path) -> None:
    summary = blind_export(make_export(tmp_path), tmp_path / "blind", salt="s")
    seq = next(r for r in read_labels(summary.labels_file) if r.scenario == "car_break_in")
    item = next(i for i in load_items(summary.inputs_dir) if i.opaque_id == seq.opaque_id)
    assert item.frames == ("frame-00.jpg", "frame-01.jpg")
    first = Image.open(summary.inputs_dir / seq.opaque_id / "frame-00.jpg").convert("RGB")
    assert first.getpixel((0, 0))[0] < 100  # frame_1 was dark, frame_2 light
    assert select_frames(item, FramesConfig(mode="still", count=1)) == ("frame-01.jpg",)
    assert select_frames(item, FramesConfig(mode="burst", count=4)) == item.frames


def test_mtimes_are_fixed(tmp_path: Path) -> None:
    summary = blind_export(make_export(tmp_path), tmp_path / "blind", salt="s")
    for path in [summary.inputs_dir, *summary.inputs_dir.rglob("*")]:
        assert path.stat().st_mtime == FIXED_MTIME, path


def test_opaque_ids_are_stable_and_salted() -> None:
    assert opaque_id("a", "generated:normal:x") == opaque_id("a", "generated:normal:x")
    assert opaque_id("a", "generated:normal:x") != opaque_id("b", "generated:normal:x")
    assert len(opaque_id("a", "x")) == 16


def test_refuses_to_blind_into_an_existing_directory(tmp_path: Path) -> None:
    export = make_export(tmp_path)
    blind_export(export, tmp_path / "blind", salt="s")
    with pytest.raises(FileExistsError):
        blind_export(export, tmp_path / "blind", salt="s")


def test_expected_floor_uses_the_band_midpoint() -> None:
    assert expected_floor({"min_score": 40, "max_score": 70}) == 30  # 55 is medium
    assert expected_floor({"min_score": 55, "max_score": 70}) == 60  # 62 is high
    assert expected_floor({"min_score": 70, "max_score": 100}) == 85  # 85 is critical
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest backend/tests/unit/autovlm/test_blinding.py -n0 -p no:randomly`
Expected: FAIL with `ModuleNotFoundError: No module named 'autovlm.blinding'`

- [ ] **Step 4: Write the modules**

`autovlm/scorer/__init__.py`:

```python
"""The scorer: the only autovlm code that reads labels (design 01 §3.6)."""
```

`autovlm/scorer/labels.py`:

```python
"""Label rows, the scorer's side of the blinding. Never mounted into a sandbox."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class LabelRow:
    opaque_id: str
    item_id: str
    label: str  # "benign" or "incident"
    category: str
    scenario: str
    floor_score: int | None  # S3's per-incident floor; None for benign
    corpus_version: str
    s3_group: str | None = None


def write_labels(path: Path, rows: Iterable[LabelRow]) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(asdict(row), sort_keys=True) + "\n")


def read_labels(path: Path) -> list[LabelRow]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [LabelRow(**json.loads(line)) for line in lines if line]
```

`autovlm/inputs.py`:

```python
"""Blinded items as the stack sees them: frames, a timestamp and a neutral camera id."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from autovlm.recipe import FramesConfig

ITEM_FILE = "item.json"


@dataclass(frozen=True)
class BlindedItem:
    opaque_id: str
    timestamp: str
    camera_id: str
    frames: tuple[str, ...]


def load_items(inputs_root: Path) -> list[BlindedItem]:
    items = []
    for path in sorted(inputs_root.glob(f"*/{ITEM_FILE}")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        items.append(
            BlindedItem(doc["opaque_id"], doc["timestamp"], doc["camera_id"], tuple(doc["frames"]))
        )
    return items


def select_frames(item: BlindedItem, frames: FramesConfig) -> tuple[str, ...]:
    """The frames the stack sees: the last one for a still, the last `count` for a burst."""
    count = 1 if frames.mode == "still" else frames.count
    return item.frames[-count:]
```

`autovlm/blinding.py`:

```python
"""Blinding (design 01 §3.3): turn a synthbench VSS export into label-free inputs.

Inputs get opaque ids, metadata-free JPEGs, a timestamp and one neutral camera id. Labels,
floors and scenarios go to a separate store only the scorer reads.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.evaluation.levels import floor_for_expected_score
from synthbench.export.vss import ExportedSet, read_sets

from autovlm.inputs import ITEM_FILE
from autovlm.scorer.labels import LabelRow, write_labels

CAMERA_ID = "camera"  # the export's camera and zone fields correlate with scenarios
FIXED_MTIME = 946684800  # 2000-01-01 UTC: no creation-order signal in the inputs tree
FLOOR_SCORE = {"low": 0, "medium": 30, "high": 60, "critical": 85}
_DROPPED_MARKERS = frozenset({0xFE, *range(0xE1, 0xF0)})  # COM, APP1-APP15; APP0 (JFIF) stays


@dataclass(frozen=True)
class BlindingSummary:
    items: int
    inputs_dir: Path
    labels_file: Path


def strip_jpeg_metadata(data: bytes) -> bytes:
    """Drop COM and APP1-APP15 segments before the scan; the pixels are not re-encoded."""
    if data[:2] != b"\xff\xd8":
        raise ValueError("not a JPEG")
    out = bytearray(data[:2])
    i = 2
    while i + 4 <= len(data):
        if data[i] != 0xFF:
            raise ValueError(f"bad JPEG marker at byte {i}")
        marker = data[i + 1]
        if marker == 0xDA:  # start of scan: the rest is entropy-coded data
            return bytes(out + data[i:])
        length = int.from_bytes(data[i + 2 : i + 4], "big")
        if marker not in _DROPPED_MARKERS:
            out += data[i : i + 2 + length]
        i += 2 + length
    raise ValueError("JPEG has no start of scan")


def opaque_id(salt: str, item_id: str) -> str:
    return hashlib.sha256(f"{salt}|{item_id}".encode()).hexdigest()[:16]


def expected_floor(risk: Mapping[str, Any]) -> int:
    """S3's floor: the shipped level of the band midpoint (eval_store's `_midpoint`)."""
    midpoint = (int(risk["min_score"]) + int(risk["max_score"])) // 2
    return FLOOR_SCORE[floor_for_expected_score(midpoint)]


def _frame_paths(exported: ExportedSet) -> list[Path]:
    facts = exported.labels.get("synthbench", {})
    if facts.get("kind") == "sequence" and facts.get("frame_files"):
        return [exported.set_dir / str(name) for name in facts["frame_files"]]
    return [exported.still]


def _write_private(path: Path, text: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)


def blind_export(
    export_dir: Path, out_dir: Path, salt: str, groups: Mapping[str, str] | None = None
) -> BlindingSummary:
    inputs = out_dir / "inputs"
    labels_dir = out_dir / "labels"
    inputs.mkdir(parents=True)  # never blend two blindings into one tree
    labels_dir.mkdir(mode=0o700)
    exported = sorted(read_sets(export_dir), key=lambda s: opaque_id(salt, s.item_id))
    rows: list[LabelRow] = []
    for s in exported:
        oid = opaque_id(salt, s.item_id)
        item_dir = inputs / oid
        item_dir.mkdir()
        names = []
        for n, frame in enumerate(_frame_paths(s)):
            name = f"frame-{n:02d}.jpg"
            (item_dir / name).write_bytes(strip_jpeg_metadata(frame.read_bytes()))
            names.append(name)
        doc = {"opaque_id": oid, "timestamp": s.labels["timestamp"], "camera_id": CAMERA_ID, "frames": names}
        (item_dir / ITEM_FILE).write_text(json.dumps(doc, sort_keys=True), encoding="utf-8")
        facts = s.facts
        scenario = str(facts["cell"]["scenario"])
        incident = facts["label"] == "incident"
        rows.append(
            LabelRow(
                opaque_id=oid,
                item_id=s.item_id,
                label=str(facts["label"]),
                category=s.category,
                scenario=scenario,
                floor_score=expected_floor(s.labels["risk"]) if incident else None,
                corpus_version=str(facts["corpus_version"]),
                s3_group=(groups or {}).get(scenario),
            )
        )
    for path in [*sorted(inputs.rglob("*"), reverse=True), inputs]:
        os.utime(path, (FIXED_MTIME, FIXED_MTIME))
    labels_file = labels_dir / "labels.jsonl"
    write_labels(labels_file, rows)
    _write_private(labels_dir / "salt", salt)
    return BlindingSummary(items=len(rows), inputs_dir=inputs, labels_file=labels_file)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest backend/tests/unit/autovlm/test_blinding.py -n0 -p no:randomly`
Expected: PASS (9 tests)

- [ ] **Step 6: Commit**

```bash
uvx pre-commit run --files autovlm/scorer/*.py autovlm/inputs.py autovlm/blinding.py backend/tests/unit/autovlm/helpers.py backend/tests/unit/autovlm/test_blinding.py
git add autovlm/scorer autovlm/inputs.py autovlm/blinding.py backend/tests/unit/autovlm/helpers.py backend/tests/unit/autovlm/test_blinding.py
git commit -m "feat(autovlm): blind synthbench exports into label-free inputs"
```

---

### Task 4: Three-tier scenario splits

**Files:**

- Create: `autovlm/splits.py`, `backend/tests/unit/autovlm/fixtures/sweep_items.csv`
- Test: `backend/tests/unit/autovlm/test_splits.py`

**Interfaces:**

- Consumes: `LabelRow` (Task 3); `synthbench.export.vss.draw_split`
- Produces: `TIERS = ("train", "select", "holdout")`; `SplitManifest(seed, tiers)` with `.tier_of(scenario)`, `.document()`, `.sha256()`; `strata_from_labels(rows) -> dict[str, str]`; `draw_three_tier(strata, *, seed, holdout_counts, select_fraction, reserved_holdout=frozenset()) -> SplitManifest`; `reserved_from_iss016(corpus_version, incident_scenarios) -> frozenset[str]`; `write_manifest(path, manifest)`, `read_manifest(path) -> SplitManifest`

- [ ] **Step 0: Build the sweep fixture and re-verify the ISS-016 draw**

```bash
mkdir -p backend/tests/unit/autovlm/fixtures
git show 9cb9e60b0:docs/benchmarks/synthbench/sweep-2026-10-03/items.csv | python3 -c "
import csv, sys
cols = ['item_id', 'label', 'scenario', 's3_group', 'floor_level',
        'control-q4km__score', 'qwen38-27b-q4km__score', 'gemma4-26b-a4b__score']
w = csv.DictWriter(sys.stdout, cols, extrasaction='ignore', lineterminator='\n')
w.writeheader()
for row in csv.DictReader(sys.stdin):
    w.writerow(row)
" > backend/tests/unit/autovlm/fixtures/sweep_items.csv
wc -l backend/tests/unit/autovlm/fixtures/sweep_items.csv
uv run python -c "from synthbench.export.vss import draw_split; import inspect; print(inspect.signature(draw_split))"
```

Expected: `451` lines, and a signature `(corpus_version, incident_scenarios, *, seed=None, k=None)`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/unit/autovlm/test_splits.py`:

```python
"""Three-tier splits by whole scenario."""

from __future__ import annotations

from pathlib import Path

import pytest

from autovlm.splits import (
    draw_three_tier,
    read_manifest,
    reserved_from_iss016,
    strata_from_labels,
    write_manifest,
)

from .helpers import load_sweep

ISS016 = frozenset(
    {"tailgating", "blunt_weapon", "car_break_in", "casing_with_phone", "knife_visible", "peering_into_windows"}
)


def _strata() -> dict[str, str]:
    labels, _ = load_sweep()
    return strata_from_labels(labels)


def test_strata_are_one_label_per_scenario() -> None:
    strata = _strata()
    assert sum(1 for s in strata.values() if s == "benign") == 12
    assert sum(1 for s in strata.values() if s == "incident") == 19


def test_iss016_roster_is_reproduced() -> None:
    incidents = sorted(n for n, s in _strata().items() if s == "incident")
    assert reserved_from_iss016("tierb-v0", incidents) == ISS016


def test_draw_honours_reserve_counts_and_disjointness() -> None:
    m = draw_three_tier(
        _strata(), seed="t", holdout_counts={"benign": 2, "incident": 6},
        select_fraction=0.5, reserved_holdout=ISS016,
    )
    tiers = m.tiers
    assert all(tiers[name] == "holdout" for name in ISS016)
    strata = _strata()
    count = {(st, t): 0 for st in ("benign", "incident") for t in ("train", "select", "holdout")}
    for name, tier in tiers.items():
        count[(strata[name], tier)] += 1
    assert count[("incident", "holdout")] == 6 and count[("benign", "holdout")] == 2
    assert count[("incident", "select")] == 7 and count[("incident", "train")] == 6
    assert count[("benign", "select")] == 5 and count[("benign", "train")] == 5
    assert set(tiers) == set(strata)


def test_draw_is_deterministic_and_seeded() -> None:
    kwargs = {"holdout_counts": {"benign": 2, "incident": 6}, "select_fraction": 0.5, "reserved_holdout": ISS016}
    a = draw_three_tier(_strata(), seed="t", **kwargs)
    b = draw_three_tier(_strata(), seed="t", **kwargs)
    c = draw_three_tier(_strata(), seed="other", **kwargs)
    assert a.sha256() == b.sha256()
    assert a.sha256() != c.sha256()


def test_too_large_a_holdout_is_refused() -> None:
    with pytest.raises(ValueError, match="at least one train and one select"):
        draw_three_tier(_strata(), seed="t", holdout_counts={"benign": 11, "incident": 6}, select_fraction=0.5)


def test_manifest_round_trips_and_detects_tampering(tmp_path: Path) -> None:
    m = draw_three_tier(_strata(), seed="t", holdout_counts={"benign": 2, "incident": 6}, select_fraction=0.5)
    path = tmp_path / "split.json"
    write_manifest(path, m)
    assert read_manifest(path).sha256() == m.sha256()
    path.write_text(path.read_text().replace('"train"', '"select"', 1))
    with pytest.raises(ValueError, match="sha256"):
        read_manifest(path)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest backend/tests/unit/autovlm/test_splits.py -n0 -p no:randomly`
Expected: FAIL with `ModuleNotFoundError: No module named 'autovlm.splits'`

- [ ] **Step 3: Write the module**

`autovlm/splits.py`:

```python
"""Three-tier scenario splits (design 02 §2): whole scenarios, in a published hash order."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from synthbench.export.vss import draw_split

from autovlm.scorer.labels import LabelRow

TIERS: tuple[str, ...] = ("train", "select", "holdout")


@dataclass(frozen=True)
class SplitManifest:
    seed: str
    tiers: Mapping[str, str]  # scenario -> tier

    def tier_of(self, scenario: str) -> str:
        return self.tiers[scenario]

    def document(self) -> dict[str, Any]:
        return {"seed": self.seed, "tiers": dict(sorted(self.tiers.items()))}

    def sha256(self) -> str:
        blob = json.dumps(self.document(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(blob).hexdigest()


def rank(seed: str, scenario: str) -> str:
    return hashlib.sha256(f"{seed}|{scenario}".encode()).hexdigest()


def strata_from_labels(rows: Iterable[LabelRow]) -> dict[str, str]:
    strata: dict[str, str] = {}
    for row in rows:
        if strata.setdefault(row.scenario, row.label) != row.label:
            raise ValueError(f"scenario {row.scenario!r} mixes labels; a split needs one per scenario")
    return strata


def draw_three_tier(
    strata: Mapping[str, str],
    *,
    seed: str,
    holdout_counts: Mapping[str, int],
    select_fraction: float,
    reserved_holdout: frozenset[str] = frozenset(),
) -> SplitManifest:
    """Per stratum: reserved scenarios and then the top-ranked fill the holdout; of the rest,
    the top `select_fraction` (rounded half up) go to select and the remainder to train."""
    unknown = reserved_holdout - strata.keys()
    if unknown:
        raise ValueError(f"reserved scenarios not in the corpus: {sorted(unknown)}")
    tiers: dict[str, str] = {}
    for stratum in sorted(set(strata.values())):
        names = sorted((n for n, s in strata.items() if s == stratum), key=lambda n: (rank(seed, n), n))
        reserved = [n for n in names if n in reserved_holdout]
        free = [n for n in names if n not in reserved_holdout]
        extra = holdout_counts.get(stratum, 0) - len(reserved)
        if extra < 0:
            raise ValueError(f"{stratum}: more reserved scenarios than its holdout count")
        if len(free) - extra < 2:
            raise ValueError(f"{stratum}: each stratum keeps at least one train and one select scenario")
        rest = free[extra:]
        n_select = min(max(1, int(select_fraction * len(rest) + 0.5)), len(rest) - 1)
        tiers |= dict.fromkeys(reserved + free[:extra], "holdout")
        tiers |= dict.fromkeys(rest[:n_select], "select")
        tiers |= dict.fromkeys(rest[n_select:], "train")
    return SplitManifest(seed=seed, tiers=tiers)


def reserved_from_iss016(corpus_version: str, incident_scenarios: Sequence[str]) -> frozenset[str]:
    """The ISS-016 holdout roster, which no tuning may touch."""
    draw = draw_split(corpus_version, list(incident_scenarios))
    return frozenset(str(row["scenario"]) for row in draw["scenarios"][: draw["k"]])


def write_manifest(path: Path, manifest: SplitManifest) -> None:
    doc = manifest.document() | {"sha256": manifest.sha256()}
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)


def read_manifest(path: Path) -> SplitManifest:
    doc = json.loads(path.read_text(encoding="utf-8"))
    manifest = SplitManifest(seed=doc["seed"], tiers=doc["tiers"])
    if manifest.sha256() != doc["sha256"]:
        raise ValueError(f"{path}: sha256 does not match its tiers")
    return manifest
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest backend/tests/unit/autovlm/test_splits.py -n0 -p no:randomly`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
uvx pre-commit run --files autovlm/splits.py backend/tests/unit/autovlm/test_splits.py backend/tests/unit/autovlm/fixtures/sweep_items.csv
git add autovlm/splits.py backend/tests/unit/autovlm/test_splits.py backend/tests/unit/autovlm/fixtures/sweep_items.csv
git commit -m "feat(autovlm): three-tier scenario splits that keep the ISS-016 holdout"
```

---

### Task 5: S2, S3 and the diagnostics

**Files:**

- Create: `autovlm/scorer/metrics.py`
- Test: `backend/tests/unit/autovlm/test_metrics.py`

**Interfaces:**

- Consumes: `LabelRow` (Task 3)
- Produces: `Flag(false_alarm: bool | None, hit: bool | None, refusal: bool)`; `Rates(false_alarms, benign, hits, incidents, refusals)` with `.s2`, `.s3` fractions; `flags(scores, labels, threshold) -> dict[str, Flag]`; `rates(flags) -> Rates`; `auroc_recall(scores, labels) -> tuple[float, float]`; `threshold_for_s2(scores, labels, target=0.05) -> int`

- [ ] **Step 1: Write the failing tests**

`backend/tests/unit/autovlm/test_metrics.py`:

```python
"""S2 and S3 with per-incident floors, against the 2026-10-03 sweep's counts."""

from __future__ import annotations

import pytest

from autovlm.scorer.labels import LabelRow
from autovlm.scorer.metrics import auroc_recall, flags, rates, threshold_for_s2

from .helpers import load_sweep

KNOWN = {
    "control-q4km": (21, 94, 2, 0.6770831265262364, 42.32365145228216),
    "qwen38-27b-q4km": (16, 119, 0, 0.810349619805833, 61.82572614107884),
    "gemma4-26b-a4b": (42, 138, 0, 0.795251047271139, 58.09128630705395),
}


@pytest.mark.parametrize("arm", sorted(KNOWN))
def test_threshold_30_reproduces_the_sweep(arm: str) -> None:
    labels, scores = load_sweep()
    r = rates(flags(scores[arm], labels, threshold=30))
    fa, hit, refusals, _, _ = KNOWN[arm]
    assert (r.false_alarms, r.benign, r.hits, r.incidents, r.refusals) == (fa, 209, hit, 241, refusals)


@pytest.mark.parametrize("arm", sorted(KNOWN))
def test_auroc_and_recall_reproduce_the_sweep(arm: str) -> None:
    labels, scores = load_sweep()
    auroc, recall = auroc_recall(scores[arm], labels)
    assert auroc == pytest.approx(KNOWN[arm][3], abs=1e-12)
    assert recall == pytest.approx(KNOWN[arm][4], abs=1e-9)


def test_a_threat_below_its_floor_is_never_a_hit() -> None:
    row = LabelRow("x", "x", "incident", "threats", "s", 85, "v")
    assert flags({"x": 40}, [row], threshold=30)["x"].hit is False
    assert flags({"x": 85}, [row], threshold=30)["x"].hit is True


def test_an_incident_must_also_alert() -> None:
    row = LabelRow("x", "x", "incident", "suspicious", "s", 30, "v")
    assert flags({"x": 45}, [row], threshold=60)["x"].hit is False


def test_a_refusal_is_a_non_event_in_the_denominator() -> None:
    rows = [LabelRow("b", "b", "benign", "normal", "s", None, "v"), LabelRow("i", "i", "incident", "threats", "t", 60, "v")]
    r = rates(flags({"b": None, "i": None}, rows, threshold=30))
    assert (r.false_alarms, r.benign, r.hits, r.incidents, r.refusals) == (0, 1, 0, 1, 2)


def test_threshold_for_s2_is_the_lowest_that_meets_the_target() -> None:
    labels, scores = load_sweep()
    t = threshold_for_s2(scores["control-q4km"], labels)
    benign = [scores["control-q4km"][r.opaque_id] for r in labels if r.label == "benign"]
    def fa(th: int) -> int:
        return sum(1 for s in benign if s is not None and s >= th)
    assert fa(t) <= 0.05 * len(benign)
    assert t == 0 or fa(t - 1) > 0.05 * len(benign)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest backend/tests/unit/autovlm/test_metrics.py -n0 -p no:randomly`
Expected: FAIL with `ModuleNotFoundError: No module named 'autovlm.scorer.metrics'`

- [ ] **Step 3: Write the module**

`autovlm/scorer/metrics.py`:

```python
"""S2 and S3 (design 02 §4).

A benign item is a false alarm when its score >= T. An incident is a hit only when its score
>= max(T, its own floor), so it must both alert and reach its declared level. At T = 30 this is
the 2026-10-03 sweep's rule, because every floor is at least 30. A refusal (no score) stays in
its denominator as a non-event.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from autovlm.scorer.labels import LabelRow


@dataclass(frozen=True)
class Flag:
    false_alarm: bool | None  # benign items only
    hit: bool | None  # incident items only
    refusal: bool


@dataclass(frozen=True)
class Rates:
    false_alarms: int
    benign: int
    hits: int
    incidents: int
    refusals: int

    @property
    def s2(self) -> float:
        return self.false_alarms / self.benign if self.benign else 0.0

    @property
    def s3(self) -> float:
        return self.hits / self.incidents if self.incidents else 0.0


def flags(scores: Mapping[str, int | None], labels: Sequence[LabelRow], threshold: int) -> dict[str, Flag]:
    out: dict[str, Flag] = {}
    for row in labels:
        score = scores[row.opaque_id]
        if row.label == "benign":
            out[row.opaque_id] = Flag(score is not None and score >= threshold, None, score is None)
        else:
            if row.floor_score is None:
                raise ValueError(f"incident {row.opaque_id} has no floor")
            floor = max(threshold, row.floor_score)
            out[row.opaque_id] = Flag(None, score is not None and score >= floor, score is None)
    return out


def rates(fl: Mapping[str, Flag]) -> Rates:
    benign = [f for f in fl.values() if f.false_alarm is not None]
    incidents = [f for f in fl.values() if f.hit is not None]
    return Rates(
        false_alarms=sum(1 for f in benign if f.false_alarm),
        benign=len(benign),
        hits=sum(1 for f in incidents if f.hit),
        incidents=len(incidents),
        refusals=sum(1 for f in fl.values() if f.refusal),
    )


def _value(score: int | None) -> int:
    return -1 if score is None else score  # a refusal ranks lowest


def auroc_recall(scores: Mapping[str, int | None], labels: Sequence[LabelRow]) -> tuple[float, float]:
    """AUROC and recall (percent) at <= 5% false alarms, single cutoff: diagnostics, not S3."""
    pos = [_value(scores[r.opaque_id]) for r in labels if r.label == "incident"]
    neg = [_value(scores[r.opaque_id]) for r in labels if r.label == "benign"]
    if not pos or not neg:
        raise ValueError("AUROC needs both benign and incident items")
    vals = sorted([(v, 1) for v in pos] + [(v, 0) for v in neg])
    ranks: dict[int, float] = {}
    i = 0
    while i < len(vals):
        j = i
        while j < len(vals) and vals[j][0] == vals[i][0]:
            j += 1
        for k in range(i, j):
            ranks[k] = (i + j - 1) / 2 + 1
        i = j
    rank_sum = sum(ranks[k] for k, (_, is_pos) in enumerate(vals) if is_pos == 1)
    n1, n0 = len(pos), len(neg)
    auroc = (rank_sum - n1 * (n1 + 1) / 2) / (n1 * n0)
    best = 0.0
    for t in sorted(set(pos + neg) | {101}):
        if sum(1 for v in neg if v >= t) / n0 <= 0.05:
            best = max(best, sum(1 for v in pos if v >= t) / n1)
    return auroc, 100 * best


def threshold_for_s2(scores: Mapping[str, int | None], labels: Sequence[LabelRow], target: float = 0.05) -> int:
    """The lowest alert threshold whose false-alarm rate on `labels` is at most `target`."""
    benign = [scores[r.opaque_id] for r in labels if r.label == "benign"]
    if not benign:
        raise ValueError("a threshold for S2 needs benign items")
    for t in range(102):
        if sum(1 for s in benign if s is not None and s >= t) <= target * len(benign):
            return t
    return 101
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest backend/tests/unit/autovlm/test_metrics.py -n0 -p no:randomly`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
uvx pre-commit run --files autovlm/scorer/metrics.py backend/tests/unit/autovlm/test_metrics.py
git add autovlm/scorer/metrics.py backend/tests/unit/autovlm/test_metrics.py
git commit -m "feat(autovlm): S2 and S3 with per-incident floors, pinned to the sweep"
```

---

### Task 6: The OD-26 paired test

**Files:**

- Create: `autovlm/scorer/stats.py`
- Test: `backend/tests/unit/autovlm/test_stats.py`

**Interfaces:**

- Consumes: `Flag`, `flags` (Task 5); `backend.evaluation.cluster_stats.cluster_bootstrap_diff`
- Produces: `Paired(ds2_point, ds3_point, ds2_ci, ds3_ci, seed, resamples)`; `Od26(no_clear_harm, clear_benefit)` with `.passes`; `cluster_pairs(arm, control, scenario_of) -> list[tuple[int, int, int, int, int, int]]`; `paired_test(arm, control, scenario_of, *, seed, resamples=10_000) -> Paired`; `od26(paired, harm_s2=2.0, harm_s3=-5.0) -> Od26`

- [ ] **Step 0: Re-verify the backend function**

Run: `uv run python -c "from backend.evaluation.cluster_stats import cluster_bootstrap_diff as f; import inspect; print(inspect.signature(f))"`
Expected: `(cluster_pairs, *, resamples=10000, seed=20261006)`. If it moved or changed shape, port it into `autovlm/scorer/stats.py` verbatim and keep the tests below unchanged: they pin the numbers, not the import.

- [ ] **Step 1: Write the failing tests**

`backend/tests/unit/autovlm/test_stats.py`:

```python
"""OD-26's paired scenario-cluster test, pinned to the sweep report."""

from __future__ import annotations

from autovlm.scorer.metrics import flags
from autovlm.scorer.stats import cluster_pairs, od26, paired_test

from .helpers import load_sweep


def _paired(arm: str):
    labels, scores = load_sweep()
    scen = {r.opaque_id: r.scenario for r in labels}
    a = flags(scores[arm], labels, threshold=30)
    c = flags(scores["control-q4km"], labels, threshold=30)
    return paired_test(a, c, scen, seed=20261004)


def test_27b_matches_the_report() -> None:
    p = _paired("qwen38-27b-q4km")
    assert p.ds2_ci == (-5.9524, 1.6216)
    assert p.ds3_ci == (-0.5376, 24.0343)
    decision = od26(p)
    assert decision.no_clear_harm and not decision.clear_benefit and not decision.passes


def test_gemma_matches_the_report() -> None:
    p = _paired("gemma4-26b-a4b")
    assert p.ds2_ci == (-2.3026, 22.2222)
    assert p.ds3_ci == (7.5893, 33.7079)
    decision = od26(p)
    assert not decision.no_clear_harm and decision.clear_benefit


def test_pairs_put_the_arm_first() -> None:
    labels, scores = load_sweep()
    scen = {r.opaque_id: r.scenario for r in labels}
    a = flags(scores["qwen38-27b-q4km"], labels, threshold=30)
    c = flags(scores["control-q4km"], labels, threshold=30)
    pairs = cluster_pairs(a, c, scen)
    assert len(pairs) == 31
    assert sum(p[1] for p in pairs) == 16 and sum(p[2] for p in pairs) == 21
    assert sum(p[4] for p in pairs) == 119 and sum(p[5] for p in pairs) == 94
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest backend/tests/unit/autovlm/test_stats.py -n0 -p no:randomly`
Expected: FAIL with `ModuleNotFoundError: No module named 'autovlm.scorer.stats'`

- [ ] **Step 3: Write the module**

`autovlm/scorer/stats.py`:

```python
"""OD-26's paired test (design 02 §5), on the backend's scenario-cluster bootstrap."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from backend.evaluation.cluster_stats import cluster_bootstrap_diff

from autovlm.scorer.metrics import Flag

RESAMPLES = 10_000
HARM_S2_PTS = 2.0
HARM_S3_PTS = -5.0

Pair = tuple[int, int, int, int, int, int]


@dataclass(frozen=True)
class Paired:
    ds2_point: float | None
    ds3_point: float | None
    ds2_ci: tuple[float, float]
    ds3_ci: tuple[float, float]
    seed: int
    resamples: int


@dataclass(frozen=True)
class Od26:
    no_clear_harm: bool
    clear_benefit: bool

    @property
    def passes(self) -> bool:
        return self.no_clear_harm and self.clear_benefit


def cluster_pairs(arm: Mapping[str, Flag], control: Mapping[str, Flag], scenario_of: Mapping[str, str]) -> list[Pair]:
    """(nb, fa_arm, fa_control, ni, hit_arm, hit_control) per scenario, in name order."""
    if arm.keys() != control.keys():
        raise ValueError("a paired test needs the same items in both arms")
    by: dict[str, list[int]] = {}
    for oid, a in arm.items():
        c = control[oid]
        row = by.setdefault(scenario_of[oid], [0, 0, 0, 0, 0, 0])
        if a.false_alarm is not None:
            row[0] += 1
            row[1] += int(a.false_alarm)
            row[2] += int(bool(c.false_alarm))
        else:
            row[3] += 1
            row[4] += int(bool(a.hit))
            row[5] += int(bool(c.hit))
    return [(r[0], r[1], r[2], r[3], r[4], r[5]) for _, r in sorted(by.items())]


def paired_test(
    arm: Mapping[str, Flag],
    control: Mapping[str, Flag],
    scenario_of: Mapping[str, str],
    *,
    seed: int,
    resamples: int = RESAMPLES,
) -> Paired:
    out = cluster_bootstrap_diff(cluster_pairs(arm, control, scenario_of), resamples=resamples, seed=seed)
    if out["ci_pts"] is None or out["ci3_pts"] is None:
        raise ValueError("a paired test needs benign and incident items")
    return Paired(
        ds2_point=out["point_pts"],
        ds3_point=out["point3_pts"],
        ds2_ci=(out["ci_pts"][0], out["ci_pts"][1]),
        ds3_ci=(out["ci3_pts"][0], out["ci3_pts"][1]),
        seed=seed,
        resamples=resamples,
    )


def od26(p: Paired, harm_s2: float = HARM_S2_PTS, harm_s3: float = HARM_S3_PTS) -> Od26:
    return Od26(
        no_clear_harm=p.ds2_ci[1] <= harm_s2 and p.ds3_ci[0] >= harm_s3,
        clear_benefit=p.ds2_ci[1] < 0 or p.ds3_ci[0] > 0,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest backend/tests/unit/autovlm/test_stats.py -n0 -p no:randomly`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
uvx pre-commit run --files autovlm/scorer/stats.py backend/tests/unit/autovlm/test_stats.py
git add autovlm/scorer/stats.py backend/tests/unit/autovlm/test_stats.py
git commit -m "feat(autovlm): OD-26 paired test, pinned to the sweep report"
```

---

### Task 7: Tier-scoped answers and the query ledger

**Files:**

- Create: `autovlm/scorer/tiers.py`, `autovlm/scorer/ledger.py`
- Test: `backend/tests/unit/autovlm/test_tiers.py`

**Interfaces:**

- Consumes: `Flag`, `rates` (Task 5); `LabelRow` (Task 3); `TIERS` (Task 4); `backend.evaluation.cluster_stats.cluster_bootstrap`
- Produces: `HoldoutLocked(PermissionError)`; `aggregates(flags, labels_by_id, *, seed) -> dict`; `answer(tier, flags, labels_by_id, *, seed, owner_confirm=False) -> dict`; `Query(at, tier, recipe_hash, epoch, who)`; `QueryLedger(path)` with `.record(query)`, `.queries()`, `.count(tier, epoch)`

- [ ] **Step 1: Write the failing tests**

`backend/tests/unit/autovlm/test_tiers.py`:

```python
"""What each tier may answer, and the record of who asked."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from autovlm.scorer.ledger import Query, QueryLedger
from autovlm.scorer.metrics import flags
from autovlm.scorer.tiers import HoldoutLocked, answer

from .helpers import load_sweep


def _inputs():
    labels, scores = load_sweep()
    return flags(scores["control-q4km"], labels, threshold=30), {r.opaque_id: r for r in labels}


def test_select_answers_aggregates_without_item_ids() -> None:
    fl, by_id = _inputs()
    body = answer("select", fl, by_id, seed=1)
    text = json.dumps(body)
    assert "items" not in body
    assert not any(oid in text for oid in by_id)
    assert body["aggregates"]["s2"]["false_alarms"] == 21
    assert body["aggregates"]["s3"]["hits"] == 94
    lo, hi = body["aggregates"]["s2"]["ci_pct"]
    assert lo < 100 * 21 / 209 < hi
    assert sum(g["incidents"] for g in body["aggregates"]["s3_by_group"].values()) == 241


def test_train_answers_per_item() -> None:
    fl, by_id = _inputs()
    body = answer("train", fl, by_id, seed=1)
    assert len(body["items"]) == 450


def test_holdout_is_locked_without_the_owner() -> None:
    fl, by_id = _inputs()
    with pytest.raises(HoldoutLocked):
        answer("holdout", fl, by_id, seed=1)
    assert "items" not in answer("holdout", fl, by_id, seed=1, owner_confirm=True)


def test_ledger_appends_and_counts(tmp_path: Path) -> None:
    path = tmp_path / "queries.jsonl"
    QueryLedger(path).record(Query("2026-10-23T00:00:00Z", "select", "h1", 0, "human"))
    QueryLedger(path).record(Query("2026-10-23T00:01:00Z", "select", "h2", 0, "human"))
    QueryLedger(path).record(Query("2026-10-23T00:02:00Z", "select", "h3", 1, "human"))
    ledger = QueryLedger(path)
    assert ledger.count("select", 0) == 2 and ledger.count("select", 1) == 1
    assert [q.recipe_hash for q in ledger.queries()] == ["h1", "h2", "h3"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest backend/tests/unit/autovlm/test_tiers.py -n0 -p no:randomly`
Expected: FAIL with `ModuleNotFoundError: No module named 'autovlm.scorer.tiers'`

- [ ] **Step 3: Write the modules**

`autovlm/scorer/tiers.py`:

```python
"""What each split tier may answer (design 01 §3.6)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.evaluation.cluster_stats import cluster_bootstrap

from autovlm.scorer.labels import LabelRow
from autovlm.scorer.metrics import Flag, rates
from autovlm.scorer.stats import RESAMPLES

TIERS: tuple[str, ...] = ("train", "select", "holdout")


class HoldoutLocked(PermissionError):
    """The holdout answers only the owner's confirmation."""


def _rate(clusters: list[tuple[int, int]], seed: int) -> dict[str, Any]:
    out = cluster_bootstrap(clusters, resamples=RESAMPLES, seed=seed)
    return {"point_pct": out["point_pct"], "ci_pct": out["ci_pct"]}


def aggregates(fl: Mapping[str, Flag], labels: Mapping[str, LabelRow], *, seed: int) -> dict[str, Any]:
    r = rates(fl)
    s2_by: dict[str, list[int]] = {}
    s3_by: dict[str, list[int]] = {}
    groups: dict[str, list[int]] = {}
    for oid, f in fl.items():
        row = labels[oid]
        if f.false_alarm is not None:
            cell = s2_by.setdefault(row.scenario, [0, 0])
            cell[0] += 1
            cell[1] += int(f.false_alarm)
        else:
            cell = s3_by.setdefault(row.scenario, [0, 0])
            cell[0] += 1
            cell[1] += int(bool(f.hit))
            if row.s3_group:
                g = groups.setdefault(row.s3_group, [0, 0])
                g[0] += 1
                g[1] += int(bool(f.hit))
    return {
        "s2": {"false_alarms": r.false_alarms, "benign": r.benign}
        | _rate([(n, k) for n, k in s2_by.values()], seed),
        "s3": {"hits": r.hits, "incidents": r.incidents}
        | _rate([(n, k) for n, k in s3_by.values()], seed),
        "refusals": r.refusals,
        "s3_by_group": {name: {"hits": k, "incidents": n} for name, (n, k) in sorted(groups.items())},
    }


def answer(
    tier: str,
    fl: Mapping[str, Flag],
    labels: Mapping[str, LabelRow],
    *,
    seed: int,
    owner_confirm: bool = False,
) -> dict[str, Any]:
    if tier not in TIERS:
        raise ValueError(f"unknown tier {tier!r}")
    if tier == "holdout" and not owner_confirm:
        raise HoldoutLocked("the holdout answers only the owner's confirm")
    body: dict[str, Any] = {"tier": tier, "aggregates": aggregates(fl, labels, seed=seed)}
    if tier == "train":
        body["items"] = [
            {"opaque_id": oid, "false_alarm": f.false_alarm, "hit": f.hit, "refusal": f.refusal}
            for oid, f in sorted(fl.items())
        ]
    return body
```

`autovlm/scorer/ledger.py`:

```python
"""The query ledger: every tier answer the scorer gave, so select-set reuse is countable."""

from __future__ import annotations

import fcntl
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Query:
    at: str
    tier: str
    recipe_hash: str
    epoch: int
    who: str


class QueryLedger:
    def __init__(self, path: Path) -> None:
        self._path = path

    def record(self, query: Query) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            fh.write(json.dumps(asdict(query), sort_keys=True) + "\n")

    def queries(self) -> list[Query]:
        if not self._path.exists():
            return []
        lines = self._path.read_text(encoding="utf-8").splitlines()
        return [Query(**json.loads(line)) for line in lines if line]

    def count(self, tier: str, epoch: int) -> int:
        return sum(1 for q in self.queries() if q.tier == tier and q.epoch == epoch)
```

Then make Task 4's `autovlm/splits.py` import `TIERS` from `autovlm.scorer.tiers` instead of defining its own, so one definition exists.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest backend/tests/unit/autovlm/test_tiers.py backend/tests/unit/autovlm/test_splits.py -n0 -p no:randomly`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
uvx pre-commit run --files autovlm/scorer/tiers.py autovlm/scorer/ledger.py autovlm/splits.py backend/tests/unit/autovlm/test_tiers.py
git add autovlm/scorer/tiers.py autovlm/scorer/ledger.py autovlm/splits.py backend/tests/unit/autovlm/test_tiers.py
git commit -m "feat(autovlm): tier-scoped answers and the query ledger"
```

---

### Task 8: Mechanical checks

**Files:**

- Create: `autovlm/checks.py`
- Test: `backend/tests/unit/autovlm/test_checks.py`

**Interfaces:**

- Produces: `CheckResult(name, passed, reason)`; `taxonomy_vocabulary(path) -> set[str]`; `vocabulary_check(texts, vocabulary)`; `refusal_check(trial_refusals, incumbent_refusals)`; `uncertain_check(verdicts, incumbent_rate, floor=0.05)`; `degenerate_check(scores, verdicts)`; `group_check(trial, incumbent, margin_pts=5.0)`; each returns `CheckResult`

- [ ] **Step 0: Re-verify the taxonomy shape**

Run: `uv run python -c "import yaml; d = yaml.safe_load(open('synthbench/taxonomy/tier_b_v0.yaml')); print(type(d['scenarios']).__name__, d['scenarios'][0]['id'])"`
Expected: `list delivery_driver`

- [ ] **Step 1: Write the failing tests**

`backend/tests/unit/autovlm/test_checks.py`:

```python
"""Mechanical checks that make a trial a failure (design 02 §7)."""

from __future__ import annotations

from pathlib import Path

from autovlm.checks import (
    degenerate_check,
    group_check,
    refusal_check,
    taxonomy_vocabulary,
    uncertain_check,
    vocabulary_check,
)

TAXONOMY = Path(__file__).resolve().parents[4] / "synthbench" / "taxonomy" / "tier_b_v0.yaml"


def test_vocabulary_catches_every_spelling() -> None:
    vocab = {"peering_into_windows"}
    assert not vocabulary_check({"p.j2": "Is someone Peering Into Windows?"}, vocab).passed
    assert not vocabulary_check({"p.j2": "peering-into-windows"}, vocab).passed
    assert vocabulary_check({"p.j2": "Is a person near a window?"}, vocab).passed


def test_the_real_taxonomy_loads() -> None:
    vocab = taxonomy_vocabulary(TAXONOMY)
    assert "delivery_driver" in vocab and len(vocab) >= 31


def test_refusals_may_not_rise() -> None:
    assert refusal_check(2, 2).passed and not refusal_check(3, 2).passed


def test_uncertain_cap_is_twice_the_incumbent_or_five_percent() -> None:
    verdicts = {str(i): ("uncertain" if i < 31 else "confirmed") for i in range(450)}  # 6.9%
    assert not uncertain_check(verdicts, incumbent_rate=0.018).passed  # cap 5%
    assert uncertain_check(verdicts, incumbent_rate=0.04).passed  # cap 8%


def test_degenerate_outputs_fail() -> None:
    assert not degenerate_check({"a": 10, "b": 10}, {"a": "confirmed", "b": "rejected"}).passed
    assert not degenerate_check({"a": 10, "b": 90}, {"a": "confirmed", "b": "confirmed"}).passed
    assert degenerate_check({"a": 10, "b": 90}, {"a": "confirmed", "b": "rejected"}).passed


def test_a_group_may_not_drop_past_the_margin() -> None:
    incumbent = {"A": (10, 64), "B": (40, 82)}
    assert group_check({"A": (10, 64), "B": (37, 82)}, incumbent).passed  # -3.7 pts
    assert not group_check({"A": (6, 64), "B": (60, 82)}, incumbent).passed  # A -6.25 pts
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest backend/tests/unit/autovlm/test_checks.py -n0 -p no:randomly`
Expected: FAIL with `ModuleNotFoundError: No module named 'autovlm.checks'`

- [ ] **Step 3: Write the module**

`autovlm/checks.py`:

```python
"""Mechanical checks on every trial (design 02 §7, layer 2). A failed check is a failed trial."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    reason: str


def taxonomy_vocabulary(path: Path) -> set[str]:
    """Scenario ids from a synthbench taxonomy YAML (`scenarios: [{id: ...}, ...]`)."""
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {str(s["id"]) for s in doc["scenarios"]}


def _spellings(word: str) -> set[str]:
    w = word.lower()
    return {w, w.replace("_", " "), w.replace("_", "-")}


def vocabulary_check(texts: Mapping[str, str], vocabulary: Iterable[str]) -> CheckResult:
    words = sorted(vocabulary)
    found = sorted(
        f"{path}: {word}"
        for path, text in texts.items()
        for word in words
        if any(form in text.lower() for form in _spellings(word))
    )
    if found:
        return CheckResult("vocabulary", False, "; ".join(found))
    return CheckResult("vocabulary", True, "no taxonomy vocabulary")


def refusal_check(trial_refusals: int, incumbent_refusals: int) -> CheckResult:
    return CheckResult(
        "refusals",
        trial_refusals <= incumbent_refusals,
        f"{trial_refusals} refusals against the incumbent's {incumbent_refusals}",
    )


def uncertain_check(verdicts: Mapping[str, str | None], incumbent_rate: float, floor: float = 0.05) -> CheckResult:
    n = len(verdicts)
    rate = sum(1 for v in verdicts.values() if v == "uncertain") / n if n else 0.0
    cap = max(floor, 2 * incumbent_rate)
    return CheckResult("uncertain", rate <= cap, f"uncertain {rate:.1%} against a cap of {cap:.1%}")


def degenerate_check(scores: Mapping[str, int | None], verdicts: Mapping[str, str | None]) -> CheckResult:
    distinct_scores = sorted({s for s in scores.values() if s is not None})
    distinct_verdicts = sorted({v for v in verdicts.values() if v is not None})
    if len(distinct_scores) <= 1:
        return CheckResult("degenerate", False, f"one distinct score: {distinct_scores}")
    if len(distinct_verdicts) <= 1:
        return CheckResult("degenerate", False, f"one distinct verdict: {distinct_verdicts}")
    return CheckResult("degenerate", True, f"{len(distinct_scores)} distinct scores")


def group_check(
    trial: Mapping[str, tuple[int, int]],
    incumbent: Mapping[str, tuple[int, int]],
    margin_pts: float = 5.0,
) -> CheckResult:
    """Each value is (hits, incidents); fail when a group's S3 drops by more than the margin."""
    drops = []
    for group, (hits, n) in sorted(incumbent.items()):
        t_hits, t_n = trial[group]
        if n == 0 or t_n != n:
            raise ValueError(f"group {group!r} must have the same incidents in both runs")
        drop = 100 * (hits - t_hits) / n
        if drop > margin_pts:
            drops.append(f"{group} -{drop:.1f} pts")
    return CheckResult("groups", not drops, "; ".join(drops) or "no group dropped past the margin")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest backend/tests/unit/autovlm/test_checks.py -n0 -p no:randomly`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
uvx pre-commit run --files autovlm/checks.py backend/tests/unit/autovlm/test_checks.py
git add autovlm/checks.py backend/tests/unit/autovlm/test_checks.py
git commit -m "feat(autovlm): mechanical checks for gaming and degenerate trials"
```

---

### Task 9: The null-perturbation envelope

**Files:**

- Create: `autovlm/envelope.py`
- Test: `backend/tests/unit/autovlm/test_envelope.py`

**Interfaces:**

- Consumes: `Flag`, `rates` (Task 5); `Paired`, `od26` (Task 6)
- Produces: `Envelope(s2_pts, s3_pts)`; `point_deltas(arm, base) -> tuple[float, float]`; `envelope(base, perturbed) -> Envelope`; `classify(paired, env) -> "improved" | "neutral" | "regressed"`; `jpeg_reencode(data, quality=90) -> bytes`

- [ ] **Step 1: Write the failing tests**

`backend/tests/unit/autovlm/test_envelope.py`:

```python
"""The null-perturbation envelope (design 02 §6)."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from autovlm.envelope import Envelope, classify, envelope, jpeg_reencode
from autovlm.scorer.metrics import Flag
from autovlm.scorer.stats import Paired

from .helpers import jpeg_bytes


def _flags(fa: int, hits: int) -> dict[str, Flag]:
    out = {f"b{i}": Flag(i < fa, None, False) for i in range(100)}
    out |= {f"i{i}": Flag(None, i < hits, False) for i in range(100)}
    return out


def test_envelope_is_the_largest_null_move() -> None:
    base = _flags(10, 40)
    env = envelope(base, {"build": _flags(13, 38), "paraphrase": _flags(9, 45)})
    assert env == Envelope(s2_pts=3.0, s3_pts=5.0)


def test_envelope_needs_a_perturbation() -> None:
    with pytest.raises(ValueError):
        envelope(_flags(1, 1), {})


def _paired(ds2: tuple[float, float], ds3: tuple[float, float], p2: float, p3: float) -> Paired:
    return Paired(p2, p3, ds2, ds3, seed=1, resamples=10)


def test_a_clear_win_beyond_the_envelope_is_improved() -> None:
    assert classify(_paired((-3, 1), (2, 14), -1, 8), Envelope(3, 5)) == "improved"


def test_a_clear_win_inside_the_envelope_is_neutral() -> None:
    assert classify(_paired((-3, 1), (0.5, 9), -1, 4), Envelope(3, 5)) == "neutral"


def test_harm_is_regressed() -> None:
    assert classify(_paired((1, 9), (2, 14), 5, 8), Envelope(3, 5)) == "regressed"


def test_jpeg_reencode_returns_a_decodable_jpeg() -> None:
    out = jpeg_reencode(jpeg_bytes(), quality=80)
    assert out[:2] == b"\xff\xd8"
    assert Image.open(io.BytesIO(out)).size == (32, 24)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest backend/tests/unit/autovlm/test_envelope.py -n0 -p no:randomly`
Expected: FAIL with `ModuleNotFoundError: No module named 'autovlm.envelope'`

- [ ] **Step 3: Write the module**

`autovlm/envelope.py`:

```python
"""The null-perturbation envelope (design 02 §6).

Greedy replays repeat exactly, so rerun noise reads zero. The envelope measures what
meaning-free changes do instead (another build, a paraphrase, a JPEG re-encode), and a gain
counts as improved only past both its paired interval and that envelope.
"""

from __future__ import annotations

import io
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from PIL import Image

from autovlm.scorer.metrics import Flag, rates
from autovlm.scorer.stats import Paired, od26

Outcome = Literal["improved", "neutral", "regressed"]


@dataclass(frozen=True)
class Envelope:
    s2_pts: float  # the largest |dS2| any null perturbation produced
    s3_pts: float  # the largest |dS3|


def point_deltas(arm: Mapping[str, Flag], base: Mapping[str, Flag]) -> tuple[float, float]:
    a, b = rates(arm), rates(base)
    return 100 * (a.false_alarms - b.false_alarms) / a.benign, 100 * (a.hits - b.hits) / a.incidents


def envelope(base: Mapping[str, Flag], perturbed: Mapping[str, Mapping[str, Flag]]) -> Envelope:
    if not perturbed:
        raise ValueError("an envelope needs at least one null perturbation")
    deltas = [point_deltas(p, base) for p in perturbed.values()]
    return Envelope(max(abs(d2) for d2, _ in deltas), max(abs(d3) for _, d3 in deltas))


def classify(paired: Paired, env: Envelope) -> Outcome:
    decision = od26(paired)
    if not decision.no_clear_harm:
        return "regressed"
    beyond = (paired.ds3_point or 0.0) > env.s3_pts or -(paired.ds2_point or 0.0) > env.s2_pts
    return "improved" if decision.clear_benefit and beyond else "neutral"


def jpeg_reencode(data: bytes, quality: int = 90) -> bytes:
    """One null perturbation: decode and re-encode the same pixels."""
    out = io.BytesIO()
    Image.open(io.BytesIO(data)).convert("RGB").save(out, format="JPEG", quality=quality)
    return out.getvalue()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest backend/tests/unit/autovlm/test_envelope.py -n0 -p no:randomly`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
uvx pre-commit run --files autovlm/envelope.py backend/tests/unit/autovlm/test_envelope.py
git add autovlm/envelope.py backend/tests/unit/autovlm/test_envelope.py
git commit -m "feat(autovlm): the null-perturbation envelope and outcome classes"
```

---

### Task 10: Detector and VLM stages

**Files:**

- Create: `autovlm/stages/__init__.py`, `autovlm/stages/detector.py`, `autovlm/stages/vlm.py`
- Test: `backend/tests/unit/autovlm/test_stages.py`

**Interfaces:**

- Consumes: `BlindedItem`, `select_frames` (Task 3); `FramesConfig` (Task 2); `backend.services.vlm_client.VlmClient`, `VlmClientError`, `VlmTruncatedError`; `backend.services.vlm_verdict.VlmAssessRequest`, `VlmAssessContext`; `backend.core.config.get_settings`
- Produces: `DetectionRow(object_type, confidence, bbox)` with `.as_context() -> dict`; `GatewayDetector(base_url, *, class_thresholds, fallback, client=None)` with `.detect(image: Path) -> list[DetectionRow]`; `REFUSAL_PREFIX = "truncated:"`; `VlmOutcome(score, verdict, error, latency_ms)` with `.refused`; `shipped_client(url, inputs_root, read_timeout_s=180.0) -> VlmClient`; `VlmStage(client, inputs_root, frames, retries=2)` with `async .assess(item, detections) -> VlmOutcome`

- [ ] **Step 0: Re-verify the backend shapes**

```bash
uv run python -c "
from backend.services.vlm_verdict import VlmAssessContext, VlmAssessRequest
print(sorted(VlmAssessContext.model_fields), VlmAssessRequest.model_fields['image_paths'].metadata)
from backend.services.vlm_client import VlmClient, VlmClientError, VlmTruncatedError
import inspect; print(inspect.signature(VlmClient.__init__), VlmTruncatedError.__mro__[1].__name__)
from backend.core.config import get_settings; s = get_settings(); print(s.detection_confidence_threshold, sorted(s.detection_class_thresholds)[:3])
"
grep -n '@router.post("/detect")' ai/gateway/adapters/yolo26.py
```

Expected: the context fields include `camera_id`, `detections`, `timestamp`; `image_paths` allows 1–4; the client takes `settings`, `transport`, `base_url`; `VlmTruncatedError`'s parent is `VlmSchemaError`; a fallback of `0.4` and per-class thresholds; the `/detect` route exists. Adapt the code below to any change before writing it.

- [ ] **Step 1: Write the failing tests**

`backend/tests/unit/autovlm/test_stages.py`:

```python
"""The detector and VLM stages, with fakes in place of the services."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from autovlm.inputs import BlindedItem, load_items
from autovlm.recipe import FramesConfig
from autovlm.stages.detector import GatewayDetector
from autovlm.stages.vlm import VlmStage, shipped_client
from backend.services.vlm_client import VlmTransportError, VlmTruncatedError

from .helpers import jpeg_bytes


def _gateway(captured: list[httpx.Request]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        request.read()  # a multipart body is a stream until read
        captured.append(request)
        return httpx.Response(200, json={
            "detections": [
                {"class": "person", "confidence": 0.55, "bbox": {"x": 1, "y": 2, "width": 3, "height": 4}},
                {"class": "person", "confidence": 0.30, "bbox": {"x": 5, "y": 6, "width": 7, "height": 8}},
                {"class": "car", "confidence": 0.45, "bbox": {"x": 9, "y": 9, "width": 9, "height": 9}},
            ],
            "image_width": 32, "image_height": 24, "inference_time_ms": 1.0,
        })
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://gw")


def test_detector_posts_the_image_and_applies_class_thresholds(tmp_path: Path) -> None:
    image = tmp_path / "frame-00.jpg"
    image.write_bytes(jpeg_bytes())
    captured: list[httpx.Request] = []
    detector = GatewayDetector("http://gw", class_thresholds={"person": 0.4, "car": 0.5}, fallback=0.4, client=_gateway(captured))
    rows = detector.detect(image)
    assert captured[0].url.path == "/yolo26/detect"
    assert b'name="file"' in captured[0].content
    assert [r.as_context() for r in rows] == [{"object_type": "person", "confidence": 0.55, "bbox": [1, 2, 3, 4]}]


class FakeClient:
    def __init__(self, result: Any = None, errors: list[Exception] | None = None) -> None:
        self.result, self.errors, self.requests = result, list(errors or []), []

    async def assess(self, request: Any) -> Any:
        self.requests.append(request)
        if self.errors:
            raise self.errors.pop(0)
        return self.result


def _item(tmp_path: Path) -> BlindedItem:
    item_dir = tmp_path / "inputs" / "abc123"
    item_dir.mkdir(parents=True)
    for name in ("frame-00.jpg", "frame-01.jpg"):
        (item_dir / name).write_bytes(jpeg_bytes())
    return BlindedItem("abc123", "2026-04-15T21:30:00-04:00", "camera", ("frame-00.jpg", "frame-01.jpg"))


def test_vlm_stage_builds_the_shipped_request(tmp_path: Path) -> None:
    item = _item(tmp_path)
    client = FakeClient(SimpleNamespace(risk_score=72, verdict="confirmed"))
    stage = VlmStage(client, tmp_path / "inputs", FramesConfig(mode="burst", count=2))
    outcome = asyncio.run(stage.assess(item, []))
    assert (outcome.score, outcome.verdict, outcome.error) == (72, "confirmed", None)
    request = client.requests[0]
    assert request.image_paths == [str(tmp_path / "inputs" / "abc123" / n) for n in item.frames]
    assert request.context.camera_id == "camera" and request.context.detections == []


def test_truncation_is_a_refusal_not_retried(tmp_path: Path) -> None:
    client = FakeClient(errors=[VlmTruncatedError("cut at budget")])
    outcome = asyncio.run(VlmStage(client, tmp_path / "inputs", FramesConfig()).assess(_item(tmp_path), []))
    assert outcome.refused and outcome.score is None and len(client.requests) == 1


def test_transport_errors_retry_then_report(tmp_path: Path) -> None:
    client = FakeClient(errors=[VlmTransportError("down")] * 3)
    outcome = asyncio.run(VlmStage(client, tmp_path / "inputs", FramesConfig(), retries=2).assess(_item(tmp_path), []))
    assert not outcome.refused and outcome.error is not None and len(client.requests) == 3


@pytest.mark.gpu
def test_shipped_client_answers_a_live_endpoint() -> None:
    url, inputs = os.environ.get("AUTOVLM_VLM_URL"), os.environ.get("AUTOVLM_INPUTS")
    if not url or not inputs:
        pytest.skip("set AUTOVLM_VLM_URL and AUTOVLM_INPUTS to run against a live ai-vlm")
    root = Path(inputs)
    stage = VlmStage(shipped_client(url, root), root, FramesConfig())
    outcome = asyncio.run(stage.assess(load_items(root)[0], []))
    assert outcome.error is None or outcome.refused, json.dumps(outcome.__dict__)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest backend/tests/unit/autovlm/test_stages.py -n0 -p no:randomly`
Expected: FAIL with `ModuleNotFoundError: No module named 'autovlm.stages'`

- [ ] **Step 3: Write the modules**

`autovlm/stages/__init__.py`:

```python
"""Stages that call the product's services: the detector and the VLM client."""
```

`autovlm/stages/detector.py`:

```python
"""The production detector through the ai-gateway's /yolo26/detect, with the product's thresholds."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx


@dataclass(frozen=True)
class DetectionRow:
    object_type: str
    confidence: float
    bbox: tuple[int, int, int, int]  # x, y, width, height

    def as_context(self) -> dict[str, Any]:
        """The row shape the product's analyzer hands the VLM."""
        return {"object_type": self.object_type, "confidence": self.confidence, "bbox": list(self.bbox)}


class GatewayDetector:
    def __init__(
        self,
        base_url: str,
        *,
        class_thresholds: Mapping[str, float],
        fallback: float,
        client: httpx.Client | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._thresholds = dict(class_thresholds)
        self._fallback = fallback
        self._client = client or httpx.Client(timeout=30.0)

    def detect(self, image: Path) -> list[DetectionRow]:
        files = {"file": (image.name, image.read_bytes(), "image/jpeg")}
        response = self._client.post(f"{self._base}/yolo26/detect", files=files)
        response.raise_for_status()
        rows = []
        for d in response.json()["detections"]:
            if float(d["confidence"]) < self._thresholds.get(d["class"], self._fallback):
                continue
            b = d["bbox"]
            rows.append(
                DetectionRow(str(d["class"]), float(d["confidence"]), (int(b["x"]), int(b["y"]), int(b["width"]), int(b["height"])))
            )
        return rows
```

`autovlm/stages/vlm.py`:

```python
"""The VLM stage: the product's own VlmClient, reading images from the blinded inputs."""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from backend.core.config import get_settings
from backend.services.vlm_client import VlmClient, VlmClientError, VlmTruncatedError
from backend.services.vlm_verdict import VlmAssessContext, VlmAssessRequest

from autovlm.inputs import BlindedItem, select_frames
from autovlm.recipe import FramesConfig
from autovlm.stages.detector import DetectionRow

REFUSAL_PREFIX = "truncated:"


@dataclass(frozen=True)
class VlmOutcome:
    score: int | None
    verdict: str | None
    error: str | None
    latency_ms: float

    @property
    def refused(self) -> bool:
        """A token-budget cut: unmeasured at this budget, a non-event in the denominator."""
        return self.error is not None and self.error.startswith(REFUSAL_PREFIX)


class AssessClient(Protocol):
    async def assess(self, request: VlmAssessRequest) -> Any: ...


def shipped_client(url: str, inputs_root: Path, read_timeout_s: float = 180.0) -> VlmClient:
    """As synthbench's replay builds it: capture root = the inputs, no camera timezone, a long
    read timeout so a slow arm is not penalised."""
    settings = get_settings().model_copy(
        update={
            "camera_timezone": None,
            "foscam_base_path": str(inputs_root),
            "ai_vlm_read_timeout": read_timeout_s,
        }
    )
    return VlmClient(settings=settings, base_url=url)


def _ms(start: float) -> float:
    return round(1000 * (time.monotonic() - start), 1)


class VlmStage:
    def __init__(self, client: AssessClient, inputs_root: Path, frames: FramesConfig, retries: int = 2) -> None:
        self._client = client
        self._root = inputs_root
        self._frames = frames
        self._retries = retries

    async def assess(self, item: BlindedItem, detections: Sequence[DetectionRow]) -> VlmOutcome:
        paths = [str(self._root / item.opaque_id / name) for name in select_frames(item, self._frames)]
        request = VlmAssessRequest(
            image_paths=paths,
            context=VlmAssessContext(
                camera_id=item.camera_id,
                detections=[d.as_context() for d in detections],
                timestamp=item.timestamp,
            ),
        )
        start = time.monotonic()
        error = "no attempt made"
        for _ in range(self._retries + 1):
            try:
                verdict = await self._client.assess(request)
            except VlmTruncatedError as exc:
                return VlmOutcome(None, None, f"{REFUSAL_PREFIX} {exc}", _ms(start))
            except VlmClientError as exc:
                error = f"{type(exc).__name__}: {exc}"
                continue
            return VlmOutcome(int(verdict.risk_score), str(verdict.verdict), None, _ms(start))
        return VlmOutcome(None, None, error, _ms(start))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest backend/tests/unit/autovlm/test_stages.py -n0 -p no:randomly`
Expected: PASS (4 tests; the `gpu` test is deselected by `addopts`)

- [ ] **Step 5: Commit**

```bash
uvx pre-commit run --files autovlm/stages/*.py backend/tests/unit/autovlm/test_stages.py
git add autovlm/stages backend/tests/unit/autovlm/test_stages.py
git commit -m "feat(autovlm): detector and VLM stages on the product's own clients"
```

---

### Task 11: `evaluate` and the `blind`, `split` and `eval` commands

**Files:**

- Create: `autovlm/evaluate.py`, `autovlm/commands/__init__.py`, `autovlm/commands/blind.py`, `autovlm/commands/split.py`, `autovlm/commands/eval_cmd.py`
- Modify: `autovlm/cli.py` (register the commands)
- Test: `backend/tests/unit/autovlm/test_evaluate.py`, `backend/tests/unit/autovlm/test_commands.py`

**Interfaces:**

- Consumes: everything above
- Produces: `ItemResult(opaque_id, detections, score, verdict, error, latency_ms)`; `async run_items(items, inputs_root, recipe, detector, assessor) -> list[ItemResult]`; `readings(results, labels, manifest, *, seed, owner_confirm) -> dict`; `evaluate(*, recipe, inputs_root, labels, manifest, detector, assessor, out_dir, ledger, epoch, seed, owner_confirm=False) -> dict`; commands `blind`, `split`, `eval` in `autovlm.cli.COMMANDS`

- [ ] **Step 1: Write the failing tests**

`backend/tests/unit/autovlm/test_evaluate.py`:

```python
"""One-shot evaluation over fakes: thresholds on train, answers by tier."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from autovlm.evaluate import evaluate
from autovlm.inputs import BlindedItem
from autovlm.recipe import Recipe
from autovlm.scorer.labels import LabelRow
from autovlm.scorer.ledger import QueryLedger
from autovlm.splits import SplitManifest
from autovlm.stages.vlm import VlmOutcome

from .helpers import jpeg_bytes

RECIPE = Recipe.model_validate(
    {"recipe": 1, "inputs": "realistic", "vlm": {"model_sha256": "a" * 64, "mmproj_sha256": "b" * 64, "build": "b7972"}}
)


class NoDetections:
    def detect(self, image: Path) -> list:
        return []


class ScoreTable:
    def __init__(self, scores: dict[str, int | None]) -> None:
        self.scores = scores

    async def assess(self, item: BlindedItem, detections: list) -> VlmOutcome:
        s = self.scores[item.opaque_id]
        return VlmOutcome(s, None if s is None else "confirmed", None if s is not None else "truncated: x", 1.0)


def _corpus(tmp_path: Path) -> tuple[Path, list[LabelRow], dict[str, int | None], SplitManifest]:
    """Two scenarios per stratum per tier; two items per scenario."""
    inputs = tmp_path / "inputs"
    labels, scores, tiers = [], {}, {}
    plan = {"train": (20, 70), "select": (35, 65), "holdout": (5, 90)}  # (benign score, incident score)
    for tier, (b_score, i_score) in plan.items():
        for stratum, score, floor in (("benign", b_score, None), ("incident", i_score, 60)):
            for s in range(2):
                scenario = f"{tier}-{stratum}-{s}"
                tiers[scenario] = tier
                for k in range(2):
                    oid = f"{scenario}-{k}"
                    (inputs / oid).mkdir(parents=True)
                    (inputs / oid / "frame-00.jpg").write_bytes(jpeg_bytes())
                    (inputs / oid / "item.json").write_text(json.dumps(
                        {"opaque_id": oid, "timestamp": "2026-04-15T21:30:00-04:00", "camera_id": "camera", "frames": ["frame-00.jpg"]}
                    ))
                    labels.append(LabelRow(oid, oid, stratum, "", scenario, floor, "test-v0", None))
                    scores[oid] = score + k
    return inputs, labels, scores, SplitManifest(seed="t", tiers=tiers)


def test_threshold_comes_from_train_and_select_is_scored_with_it(tmp_path: Path) -> None:
    inputs, labels, scores, manifest = _corpus(tmp_path)
    data = evaluate(
        recipe=RECIPE, inputs_root=inputs, labels=labels, manifest=manifest, detector=NoDetections(),
        assessor=ScoreTable(scores), out_dir=tmp_path / "out", ledger=QueryLedger(tmp_path / "q.jsonl"),
        epoch=0, seed=1,
    )
    assert data["threshold"] == 22  # train benign scores are 20 and 21
    select = data["tiers"]["select"]["aggregates"]
    assert select["s2"]["false_alarms"] == 4  # select benign 35/36 alert at 22
    assert select["s3"]["hits"] == 4  # select incidents 65/66 clear max(22, 60)
    assert "holdout" not in data["tiers"]
    assert data["complete"] is True
    assert (tmp_path / "out" / "results.jsonl").exists()
    assert QueryLedger(tmp_path / "q.jsonl").count("select", 0) == 1


def test_holdout_items_are_not_even_run_without_the_owner(tmp_path: Path) -> None:
    inputs, labels, scores, manifest = _corpus(tmp_path)
    seen: list[str] = []

    class Spy(ScoreTable):
        async def assess(self, item: BlindedItem, detections: list) -> VlmOutcome:
            seen.append(item.opaque_id)
            return await super().assess(item, detections)

    evaluate(
        recipe=RECIPE, inputs_root=inputs, labels=labels, manifest=manifest, detector=NoDetections(),
        assessor=Spy(scores), out_dir=tmp_path / "out", ledger=QueryLedger(tmp_path / "q.jsonl"), epoch=0, seed=1,
    )
    assert not any(oid.startswith("holdout") for oid in seen)


def test_an_unmeasured_item_makes_the_run_incomplete(tmp_path: Path) -> None:
    inputs, labels, scores, manifest = _corpus(tmp_path)

    class Broken(ScoreTable):
        async def assess(self, item: BlindedItem, detections: list) -> VlmOutcome:
            if item.opaque_id == "select-incident-0-0":
                return VlmOutcome(None, None, "VlmTransportError: down", 1.0)
            return await super().assess(item, detections)

    data = evaluate(
        recipe=RECIPE, inputs_root=inputs, labels=labels, manifest=manifest, detector=NoDetections(),
        assessor=Broken(scores), out_dir=tmp_path / "out", ledger=QueryLedger(tmp_path / "q.jsonl"), epoch=0, seed=1,
    )
    assert data["complete"] is False
    assert data["unmeasured"] == ["select-incident-0-0"]


def test_out_dir_is_never_reused(tmp_path: Path) -> None:
    inputs, labels, scores, manifest = _corpus(tmp_path)
    (tmp_path / "out").mkdir()
    with pytest.raises(FileExistsError):
        evaluate(
            recipe=RECIPE, inputs_root=inputs, labels=labels, manifest=manifest, detector=NoDetections(),
            assessor=ScoreTable(scores), out_dir=tmp_path / "out", ledger=QueryLedger(tmp_path / "q.jsonl"),
            epoch=0, seed=1,
        )
```

`backend/tests/unit/autovlm/test_commands.py`:

```python
"""The blind, split and eval commands, end to end over fakes."""

from __future__ import annotations

from pathlib import Path

import pytest

from autovlm.cli import main
from autovlm.commands import eval_cmd
from autovlm.scorer.labels import read_labels

from .helpers import make_export


def test_blind_writes_inputs_labels_and_salt(tmp_path: Path) -> None:
    assert main(["blind", "--export", str(make_export(tmp_path)), "--out", str(tmp_path / "b")]) == 0
    assert len(read_labels(tmp_path / "b" / "labels" / "labels.jsonl")) == 3
    assert (tmp_path / "b" / "labels" / "salt").stat().st_size == 32


def test_split_refuses_a_corpus_too_small_to_split(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["blind", "--export", str(make_export(tmp_path)), "--out", str(tmp_path / "b")])
    code = main([
        "split", "--labels", str(tmp_path / "b" / "labels" / "labels.jsonl"), "--out", str(tmp_path / "split.json"),
        "--seed", "t", "--holdout", "benign=0,incident=0", "--select-fraction", "0.5",
    ])
    assert code == 1
    assert "at least one train and one select" in capsys.readouterr().err


def test_eval_wires_its_arguments_into_evaluate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict = {}

    def fake_evaluate(**kwargs: object) -> dict:
        seen.update(kwargs)
        return {"threshold": 30, "complete": True, "tiers": {}}

    monkeypatch.setattr(eval_cmd, "evaluate", fake_evaluate)
    monkeypatch.setattr(eval_cmd, "build_stages", lambda *_: ("detector", "assessor"))
    monkeypatch.setattr(eval_cmd, "read_manifest", lambda *_: "manifest")
    monkeypatch.setattr(eval_cmd, "read_labels", lambda *_: ["label"])
    recipe = Path(__file__).resolve().parents[4] / "autovlm" / "recipes" / "shipped-8b.yaml"
    code = main([
        "eval", "--recipe", str(recipe), "--inputs", str(tmp_path / "in"), "--labels", str(tmp_path / "l.jsonl"),
        "--split", str(tmp_path / "s.json"), "--detector-url", "http://gw", "--vlm-url", "http://vlm",
        "--out", str(tmp_path / "out"), "--epoch", "3",
    ])
    assert code == 0
    assert seen["detector"] == "detector" and seen["assessor"] == "assessor"
    assert seen["epoch"] == 3 and seen["owner_confirm"] is False
    assert seen["manifest"] == "manifest" and seen["labels"] == ["label"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest backend/tests/unit/autovlm/test_evaluate.py backend/tests/unit/autovlm/test_commands.py -n0 -p no:randomly`
Expected: FAIL with `ModuleNotFoundError: No module named 'autovlm.evaluate'`

- [ ] **Step 3: Write `autovlm/evaluate.py`**

```python
"""One-shot evaluation (phase P1): a recipe over blinded inputs, answered by tier."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from autovlm.inputs import BlindedItem, load_items, select_frames
from autovlm.recipe import Recipe, recipe_hash
from autovlm.scorer.labels import LabelRow
from autovlm.scorer.ledger import Query, QueryLedger
from autovlm.scorer.metrics import auroc_recall, flags, threshold_for_s2
from autovlm.scorer.tiers import answer
from autovlm.splits import SplitManifest
from autovlm.stages.detector import DetectionRow
from autovlm.stages.vlm import VlmOutcome


class Detector(Protocol):
    def detect(self, image: Path) -> list[DetectionRow]: ...


class Assessor(Protocol):
    async def assess(self, item: BlindedItem, detections: Sequence[DetectionRow]) -> VlmOutcome: ...


@dataclass(frozen=True)
class ItemResult:
    opaque_id: str
    detections: list[dict[str, Any]]
    score: int | None
    verdict: str | None
    error: str | None
    latency_ms: float

    @property
    def unmeasured(self) -> bool:
        return self.error is not None and not VlmOutcome(None, None, self.error, 0.0).refused


async def run_items(
    items: Sequence[BlindedItem], inputs_root: Path, recipe: Recipe, detector: Detector, assessor: Assessor
) -> list[ItemResult]:
    gate = asyncio.Semaphore(recipe.vlm.parallel)

    async def one(item: BlindedItem) -> ItemResult:
        rows: list[DetectionRow] = []
        for name in select_frames(item, recipe.frames):
            rows.extend(await asyncio.to_thread(detector.detect, inputs_root / item.opaque_id / name))
        async with gate:
            outcome = await assessor.assess(item, rows)
        return ItemResult(
            item.opaque_id, [r.as_context() for r in rows], outcome.score, outcome.verdict, outcome.error, outcome.latency_ms
        )

    return list(await asyncio.gather(*(one(i) for i in items)))


def readings(
    results: Sequence[ItemResult],
    labels: Sequence[LabelRow],
    manifest: SplitManifest,
    *,
    seed: int,
    owner_confirm: bool,
) -> dict[str, Any]:
    by_id = {row.opaque_id: row for row in labels}
    scores = {r.opaque_id: r.score for r in results}
    tier_rows = {t: [row for row in labels if manifest.tier_of(row.scenario) == t] for t in ("train", "select", "holdout")}
    threshold = threshold_for_s2(scores, tier_rows["train"])
    unmeasured = sorted(r.opaque_id for r in results if r.unmeasured)
    out: dict[str, Any] = {"threshold": threshold, "complete": not unmeasured, "unmeasured": unmeasured, "tiers": {}}
    for tier in ("train", "select", *(("holdout",) if owner_confirm else ())):
        rows = tier_rows[tier]
        fl = flags({row.opaque_id: scores[row.opaque_id] for row in rows}, rows, threshold)
        body = answer(tier, fl, by_id, seed=seed, owner_confirm=owner_confirm)
        if any(r.label == "benign" for r in rows) and any(r.label == "incident" for r in rows):
            auroc, recall = auroc_recall(scores, rows)
            body["diagnostics"] = {"auroc": auroc, "recall_at_5pct_single_cutoff": recall}
        out["tiers"][tier] = body
    return out


def evaluate(
    *,
    recipe: Recipe,
    inputs_root: Path,
    labels: Sequence[LabelRow],
    manifest: SplitManifest,
    detector: Detector,
    assessor: Assessor,
    out_dir: Path,
    ledger: QueryLedger,
    epoch: int,
    seed: int,
    owner_confirm: bool = False,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True)  # a run directory is never reused
    tiers = {"train", "select"} | ({"holdout"} if owner_confirm else set())
    wanted = [row for row in labels if manifest.tier_of(row.scenario) in tiers]
    ids = {row.opaque_id for row in wanted}
    items = [i for i in load_items(inputs_root) if i.opaque_id in ids]
    results = asyncio.run(run_items(items, inputs_root, recipe, detector, assessor))
    with (out_dir / "results.jsonl").open("w", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps(asdict(r), sort_keys=True) + "\n")
    data = readings(results, wanted, manifest, seed=seed, owner_confirm=owner_confirm)
    data |= {"recipe_hash": recipe_hash(recipe), "split_sha256": manifest.sha256(), "seed": seed, "epoch": epoch}
    (out_dir / "readings.json").write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    now = datetime.now(UTC).isoformat()
    for tier in data["tiers"]:
        who = "owner" if tier == "holdout" else "human"
        ledger.record(Query(at=now, tier=tier, recipe_hash=data["recipe_hash"], epoch=epoch, who=who))
    return data
```

- [ ] **Step 4: Write the commands and register them**

`autovlm/commands/__init__.py`:

```python
"""autovlm subcommands; each module exposes COMMAND."""
```

`autovlm/commands/blind.py`:

```python
"""autovlm blind: a synthbench VSS export -> blinded inputs plus a private labels store."""

from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

import yaml

from autovlm.blinding import blind_export
from autovlm.cli import Command


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("--export", type=Path, required=True, help="a synthbench VSS export directory")
    p.add_argument("--out", type=Path, required=True, help="new directory for inputs/ and labels/")
    p.add_argument("--groups", type=Path, help="YAML mapping scenario -> S3 group, kept with the labels")


def run(args: argparse.Namespace) -> int:
    groups = yaml.safe_load(args.groups.read_text(encoding="utf-8")) if args.groups else None
    summary = blind_export(args.export, args.out, secrets.token_hex(16), groups)
    sys.stdout.write(f"blinded {summary.items} items: inputs {summary.inputs_dir}, labels {summary.labels_file}\n")
    return 0


COMMAND = Command("blind a synthbench VSS export", add_arguments, run)
```

`autovlm/commands/split.py`:

```python
"""autovlm split: a three-tier scenario split over a labels store."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from autovlm.cli import Command
from autovlm.scorer.labels import read_labels
from autovlm.splits import draw_three_tier, reserved_from_iss016, strata_from_labels, write_manifest


def _counts(text: str) -> dict[str, int]:
    return {k: int(v) for k, v in (part.split("=") for part in text.split(","))}


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("--labels", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--seed", required=True)
    p.add_argument("--holdout", type=_counts, required=True, help="e.g. benign=2,incident=6")
    p.add_argument("--select-fraction", type=float, default=0.5)
    p.add_argument("--reserve-iss016", metavar="CORPUS_VERSION", help="keep ISS-016's holdout in the holdout")


def run(args: argparse.Namespace) -> int:
    strata = strata_from_labels(read_labels(args.labels))
    reserved: frozenset[str] = frozenset()
    if args.reserve_iss016:
        incidents = sorted(n for n, s in strata.items() if s == "incident")
        reserved = reserved_from_iss016(args.reserve_iss016, incidents)
    try:
        manifest = draw_three_tier(
            strata, seed=args.seed, holdout_counts=args.holdout,
            select_fraction=args.select_fraction, reserved_holdout=reserved,
        )
    except ValueError as exc:
        sys.stderr.write(f"autovlm split: {exc}\n")
        return 1
    write_manifest(args.out, manifest)
    for tier in ("train", "select", "holdout"):
        names = [n for n, t in manifest.tiers.items() if t == tier]
        sys.stdout.write(f"{tier}: {len(names)} scenarios\n")
    sys.stdout.write(f"sha256 {manifest.sha256()}\n")
    return 0


COMMAND = Command("draw a three-tier scenario split", add_arguments, run)
```

`autovlm/commands/eval_cmd.py`:

```python
"""autovlm eval: one recipe over blinded inputs, answered by tier. --confirm is the owner's."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backend.core.config import get_settings

from autovlm.cli import Command
from autovlm.evaluate import Assessor, Detector, evaluate
from autovlm.recipe import Recipe, load_recipe
from autovlm.scorer.labels import read_labels
from autovlm.scorer.ledger import QueryLedger
from autovlm.splits import read_manifest
from autovlm.stages.detector import GatewayDetector
from autovlm.stages.vlm import VlmStage, shipped_client

DEFAULT_SEED = 20261023


def build_stages(args: argparse.Namespace, recipe: Recipe) -> tuple[Detector, Assessor]:
    settings = get_settings()
    detector = GatewayDetector(
        args.detector_url,
        class_thresholds=settings.detection_class_thresholds,
        fallback=settings.detection_confidence_threshold,
    )
    return detector, VlmStage(shipped_client(args.vlm_url, args.inputs), args.inputs, recipe.frames)


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("--recipe", type=Path, required=True)
    p.add_argument("--inputs", type=Path, required=True, help="the blinded inputs/ directory")
    p.add_argument("--labels", type=Path, required=True, help="labels/labels.jsonl")
    p.add_argument("--split", type=Path, required=True, help="the split manifest")
    p.add_argument("--detector-url", required=True, help="ai-gateway base URL")
    p.add_argument("--vlm-url", required=True, help="ai-vlm base URL")
    p.add_argument("--out", type=Path, required=True, help="a new run directory")
    p.add_argument("--ledger", type=Path, help="query ledger (default: beside the labels)")
    p.add_argument("--epoch", type=int, default=0)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--confirm", action="store_true", help="owner only: also answer the holdout")


def run(args: argparse.Namespace) -> int:
    recipe = load_recipe(args.recipe)
    detector, assessor = build_stages(args, recipe)
    ledger = QueryLedger(args.ledger or args.labels.parent / "queries.jsonl")
    data = evaluate(
        recipe=recipe, inputs_root=args.inputs, labels=read_labels(args.labels),
        manifest=read_manifest(args.split), detector=detector, assessor=assessor, out_dir=args.out,
        ledger=ledger, epoch=args.epoch, seed=args.seed, owner_confirm=args.confirm,
    )
    sys.stdout.write(json.dumps({k: data[k] for k in ("threshold", "complete")}, sort_keys=True) + "\n")
    return 0 if data["complete"] else 1


COMMAND = Command("evaluate a recipe over blinded inputs", add_arguments, run)
```

Replace `autovlm/cli.py` with this version. The command modules import `Command` from it, so it registers them lazily, inside `build_parser`, to avoid an import cycle:

```python
"""python -m autovlm <command>: exit 0 done, 1 error or incomplete run, 2 usage error."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from autovlm import __version__


@dataclass(frozen=True)
class Command:
    help: str
    add_arguments: Callable[[argparse.ArgumentParser], None]
    run: Callable[[argparse.Namespace], int]


COMMANDS: dict[str, Command] = {}


def _register() -> None:
    from autovlm.commands import blind, eval_cmd, split

    COMMANDS.update({"blind": blind.COMMAND, "eval": eval_cmd.COMMAND, "split": split.COMMAND})


def build_parser() -> argparse.ArgumentParser:
    if not COMMANDS:
        _register()
    parser = argparse.ArgumentParser(prog="autovlm", description=__doc__)
    parser.add_argument("--version", action="version", version=f"autovlm {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, command in sorted(COMMANDS.items()):
        command.add_arguments(sub.add_parser(name, help=command.help))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return COMMANDS[args.command].run(args)
```

- [ ] **Step 5: Run every autovlm test**

Run: `uv run pytest backend/tests/unit/autovlm -n0 -p no:randomly`
Expected: PASS (all tests from Tasks 1–11)

- [ ] **Step 6: Type-check and commit**

```bash
uv run mypy autovlm
uvx pre-commit run --files autovlm/evaluate.py autovlm/cli.py autovlm/commands/*.py backend/tests/unit/autovlm/test_evaluate.py backend/tests/unit/autovlm/test_commands.py
git add autovlm/evaluate.py autovlm/cli.py autovlm/commands backend/tests/unit/autovlm/test_evaluate.py backend/tests/unit/autovlm/test_commands.py
git commit -m "feat(autovlm): evaluate plus the blind, split and eval commands"
```

---

### Task 12: The realistic baseline (operational, on the GB300)

**Files:**

- Create: `docs/benchmarks/autovlm/<YYYY-MM-DD>-realistic-baseline/report.md`
- Modify: `docs/auto-vlm-research/README.md` (link the report from "Why now")

**Preconditions:** P0's S6 and S7 passed and recorded; Tasks 1–11 merged; the flagship is resident and untouched.

- [ ] **Step 1: Blind the `tierb-v0` export**

```bash
uv run python -m autovlm blind --export /synthbench/exports/tierb-v0/vss --out /synthbench/autovlm/tierb-v0
```

Expected: `blinded 450 items`.

- [ ] **Step 2: Draw the split, keeping ISS-016's holdout**

```bash
uv run python -m autovlm split --labels /synthbench/autovlm/tierb-v0/labels/labels.jsonl \
  --out /synthbench/autovlm/tierb-v0/labels/split.json --seed autovlm-tierb-v0-p1 \
  --holdout benign=2,incident=6 --select-fraction 0.5 --reserve-iss016 tierb-v0
```

Expected: `train: 11 scenarios`, `select: 12 scenarios`, `holdout: 8 scenarios`.

- [ ] **Step 3: Serve the pinned VLM through agent-gpu**

Locate the weights in the shared library (`ls "$AGENT_GPU_LIBRARY"`; the files are `Qwen3VL-8B-Instruct-Q4_K_M.gguf` and `mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf`, sha256 as in `autovlm/recipes/shipped-8b.yaml`), then start the session's ai-vlm image at the pinned build:

```bash
agent-gpu run --name autovlm-vlm --image <this session's ai-vlm:sm103 image at b7972> --vram 12 --port 8098 \
  --mount library:/library -- llama-server --model /library/<dir>/Qwen3VL-8B-Instruct-Q4_K_M.gguf \
  --mmproj /library/<dir>/mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf --alias Qwen3VL-8B \
  --cache-type-k q8_0 --cache-type-v q8_0 --host 0.0.0.0 --port 8098 --n-gpu-layers auto \
  --ctx-size 32768 --parallel 2 --batch-size 2048 --ubatch-size 512 --cont-batching \
  --cache-reuse 256 --jinja --flash-attn on
agent-gpu ps   # note the published host port for autovlm-vlm
curl -s "http://127.0.0.1:<port>/props" | python3 -c "import json,sys; print(json.load(sys.stdin).get('build_info'))"
```

Expected: `build_info` names `b7972`. Verify both files' sha256 against the recipe before serving.

- [ ] **Step 4: Serve the detector** on the host S7 chose, and note its base URL.

- [ ] **Step 5: Run the evaluation**

```bash
uv run python -m autovlm eval --recipe autovlm/recipes/shipped-8b.yaml \
  --inputs /synthbench/autovlm/tierb-v0/inputs --labels /synthbench/autovlm/tierb-v0/labels/labels.jsonl \
  --split /synthbench/autovlm/tierb-v0/labels/split.json \
  --detector-url "http://127.0.0.1:<detector port>" --vlm-url "http://127.0.0.1:<vlm port>" \
  --out /synthbench/autovlm/runs/$(date -u +%Y%m%dT%H%M%SZ)-realistic-baseline
```

Expected: exit 0 and `"complete": true`. If it exits 1, read `unmeasured` in `readings.json`, fix the cause (usually the endpoint), and rerun into a new directory.

- [ ] **Step 6: Stop the containers**: `agent-gpu stop autovlm-vlm && agent-gpu rm autovlm-vlm`, and the detector's.

- [ ] **Step 7: Write the report**

`docs/benchmarks/autovlm/<date>-realistic-baseline/report.md` records:

- **Conditions:** the recipe hash, the `build_info` read from `/props`, the weights' sha256, the split's sha256 and per-tier scenario counts, the seed, the detector host, and the code commit.
- **Readings:** the train-fitted threshold; S2 and S3 with cluster intervals on train and select; S3 by group; refusals; the single-cutoff diagnostics, labelled as diagnostics.
- **Context:** the sweep control's oracle-input S2 10.0% and S3 39.0% (2026-10-03, build b11376), stating which conditions differ: realistic detections against oracle props, the build, and the split.
- **What it is not:** a holdout reading, a 24 GB-card reading, or a comparison under OD-26.

- [ ] **Step 8: Commit**

```bash
uvx pre-commit run --files docs/benchmarks/autovlm/*/report.md docs/auto-vlm-research/README.md
git add docs/benchmarks/autovlm docs/auto-vlm-research/README.md
git commit -m "docs(autovlm): the realistic baseline of the shipped stack"
```
