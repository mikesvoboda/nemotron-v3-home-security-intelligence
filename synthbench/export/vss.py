"""The VSS eval-store layout for synthbench events (P5a design §2).

`import_generated_items` (`backend/evaluation/label_import.py`) reads
`<category>/<set>/expected_labels.json` plus the set's media, with one attribution sidecar per
frame. This module holds the pure pieces of writing that layout and of reading it back for the
audit and the scorer. It imports nothing from `backend`; a test pins the category vocabulary
below equal to the importer's.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from synthbench.contract.clip import ClipSpec
from synthbench.contract.spec import Spec

# Scenario group -> the eval store's category directory. Ambiguous events are not exported: S2
# and S3 count neither label, and the store has no ambiguous category.
CATEGORY = {
    "benign": "normal",
    "hard_negative": "normal",
    "suspicious": "suspicious",
    "threat": "threats",
}
# The importer's own vocabulary (`backend/evaluation/eval_store.py` `_CATEGORY_LABELS`).
CATEGORY_LABEL = {"normal": "benign", "suspicious": "incident", "threats": "incident"}

CAMERA_TIMEZONE = "America/New_York"  # the owner's cameras (parent spec P0)
SNOW_DATE = date(2026, 1, 15)
OTHER_DATE = date(2026, 4, 15)

LABELS_FILE = "expected_labels.json"
STILL_FILE = "still.jpg"
SIDECAR_FILE = "still.json"
LICENSE = "FLUX.2 [dev] Non-Commercial License (black-forest-labs/FLUX.2-dev)"


class ExportConflict(Exception):
    """A set already on disk holds different content than the corpus now gives it."""


def category_of(spec: Spec | ClipSpec) -> str | None:
    """The event's category directory, or None for an ambiguous event, which is not exported.

    `Spec | ClipSpec`: the two specs share the identical `Cell`, and `export vss --sequences`
    reads a clip's group through this same rule (ISS-037)."""
    return CATEGORY.get(spec.cell.group)


def scene_timestamp(scene_time: str, weather: str) -> str:
    """The scene's clock time on a fixed date in the camera timezone, with its UTC offset.

    Snow scenes are dated in January and the rest in April, so the date the VLM reads never
    contradicts the weather it sees.
    """
    hours, minutes = (int(part) for part in scene_time.split(":"))
    day = SNOW_DATE if weather == "snow" else OTHER_DATE
    moment = datetime.combine(day, time(hours, minutes), tzinfo=ZoneInfo(CAMERA_TIMEZONE))
    return moment.isoformat()


def declared_detections(spec: Spec) -> list[dict[str, Any]]:
    """The event's declared subjects and props, as an ideal detector would report them.

    One row per declared subject, then one per declared prop, in the spec's order:
    object type and confidence 1.0, nothing else (no box, id, role, attribute or held_by — a
    detector reports a class, not intent). In production the VLM runs only after the detector
    fires; a stills-only prompt gets an empty `Detections: []` and refuses to judge (Task 1's
    live probe), so replay stands in for the detector with the event's own declared objects.
    """
    subjects = [{"object_type": subject.cls, "confidence": 1.0} for subject in spec.subjects]
    props = [{"object_type": prop.cls, "confidence": 1.0} for prop in spec.props]
    return subjects + props


def labels_document(spec: Spec, still_sha256: str) -> dict[str, Any]:
    """`expected_labels.json`: the keys the importer reads, plus the event's facts for scoring."""
    category = CATEGORY[spec.cell.group]
    lo, hi = spec.risk_band
    return {
        "category": category,
        "risk": {"min_score": lo, "max_score": hi},
        "timestamp": scene_timestamp(spec.scene_time, spec.cell.weather),
        "detections": declared_detections(spec),
        "synthbench": {
            "event_id": spec.event_id,
            "corpus_version": spec.corpus_version,
            "batch": spec.batch,
            "label": spec.label,
            "risk_band": [lo, hi],
            "scene_time": spec.scene_time,
            "cell": spec.cell.model_dump(mode="json"),
            "subjects": [s.model_dump(mode="json", by_alias=True) for s in spec.subjects],
            "props": [p.model_dump(mode="json", by_alias=True) for p in spec.props],
            "still_sha256": still_sha256,
        },
    }


def attribution(version: str) -> dict[str, str]:
    """The sidecar the importer requires beside each frame: a license and an artist."""
    return {"license": LICENSE, "artist": f"synthbench {version}, FLUX.2 [dev] (synthetic)"}


def _json_bytes(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()


def set_files(spec: Spec, still: bytes, still_sha256: str) -> dict[str, bytes]:
    """Every file of one event's set, by name."""
    return {
        LABELS_FILE: _json_bytes(labels_document(spec, still_sha256)),
        STILL_FILE: still,
        SIDECAR_FILE: _json_bytes(attribution(spec.corpus_version)),
    }


def write_set(export_dir: Path, category: str, name: str, files: dict[str, bytes]) -> bool:
    """Write one set once: True if written now, False if identical content was already there.

    A new set is built in a staging directory beside the export (never under it, where the
    importer would read it) and renamed into place, so no reader sees half a set. Raises
    ExportConflict if a set on disk holds different content.
    """
    set_dir = export_dir / category / name
    if set_dir.exists():
        for file_name, data in files.items():
            path = set_dir / file_name
            if not path.is_file() or path.read_bytes() != data:
                raise ExportConflict(f"{path} differs from the corpus; an export is create-once")
        return False
    staging = export_dir.parent / f".{export_dir.name}-staging" / name
    if staging.exists():
        shutil.rmtree(staging)  # a crashed run's leftover: never renamed into the export
    staging.mkdir(parents=True)
    for file_name, data in files.items():
        (staging / file_name).write_bytes(data)
    set_dir.parent.mkdir(parents=True, exist_ok=True)
    staging.rename(set_dir)
    return True


@dataclass(frozen=True)
class ExportedSet:
    """One set read back from an export directory."""

    category: str
    set_dir: Path
    labels: dict[str, Any]

    @property
    def item_id(self) -> str:
        """The importer's id (`item_id_for_generated`); the round-trip test pins the format."""
        return f"generated:{self.category}:{self.set_dir.name}"

    @property
    def facts(self) -> dict[str, Any]:
        facts: dict[str, Any] = self.labels["synthbench"]
        return facts

    @property
    def still(self) -> Path:
        """The set's representative image: the still, or a sequence's first frame.

        The scorer names one image per item (the gallery shows it, the audit page serves it);
        a sequence's chronology starts at `frame_1.jpg`, so its first frame IS that image.
        `frame_files` is declared in the set's own labels — read from the document, never
        re-derived from a constant, so a future frame count cannot silently repoint old sets."""
        sequence = self.labels.get("synthbench", {})
        if sequence.get("kind") == "sequence" and sequence.get("frame_files"):
            return self.set_dir / str(sequence["frame_files"][0])
        return self.set_dir / STILL_FILE


def read_sets(export_dir: Path) -> list[ExportedSet]:
    """Every set under an export directory, sorted by item id."""
    sets = [
        ExportedSet(
            category=path.parent.parent.name,
            set_dir=path.parent,
            labels=json.loads(path.read_text(encoding="utf-8")),
        )
        for path in export_dir.glob(f"*/*/{LABELS_FILE}")
        if path.parent.parent.name in CATEGORY_LABEL
    ]
    return sorted(sets, key=lambda s: s.item_id)


# --- the dev/holdout split (ISS-016 design §2) ---------------------------------------------
#
# The roster is a published hash order, not a choice: ranking the incident scenario names by
# `sha256("<corpus_version>|<seed>|<scenario>")` and taking the first K. Anyone holding three
# published strings recomputes it, so nobody — including the owner — can pick a flattering holdout.

SPLIT_FILE = "splits.json"
# Pre-registered by the owner; changing a value changes that corpus's roster. A corpus version
# absent here has no split: there is no fallback seed, because reusing another corpus's seed would
# correlate two rosters for no reason.
SPLIT_SEEDS: dict[str, str] = {"tierb-v0": "vss-iss016-s3-holdout-2026-10-06"}
SPLIT_HOLDOUT_K = 6


def scenario_rank(corpus_version: str, seed: str, scenario: str) -> str:
    """The scenario's ranking key: the UTF-8 digest, lowercase hex, as the spec's recipe states."""
    return hashlib.sha256(f"{corpus_version}|{seed}|{scenario}".encode()).hexdigest()


def draw_split(
    corpus_version: str,
    incident_scenarios: Sequence[str],
    *,
    seed: str | None = None,
    k: int | None = None,
) -> dict[str, Any]:
    """The holdout/dev assignment of the incident scenarios, ranked by hash (ties by name).

    `incident_scenarios` are the scenarios with at least one incident item in the population being
    exported — the scenarios that actually appear in the sets, not a hardcoded list. A benign name
    reaching this function is the caller's error to prevent: benign stays in dev by rule (B1), so
    it never enters the draw. The drawn size is clamped to `max(0, min(k, n - 1))`, so dev always
    keeps an incident scenario (a split with no dev incidents measures nothing) and the size never
    goes negative; the clamped value is what the record carries, beside the full ranked list.
    Raises KeyError for a corpus version with no pre-registered seed.
    """
    seed = SPLIT_SEEDS[corpus_version] if seed is None else seed
    k = SPLIT_HOLDOUT_K if k is None else k
    rows = sorted(
        (
            {"scenario": name, "rank_sha256": scenario_rank(corpus_version, seed, name)}
            for name in incident_scenarios
        ),
        key=lambda row: (row["rank_sha256"], row["scenario"]),
    )
    holdout_k = max(0, min(k, len(rows) - 1))
    for index, row in enumerate(rows):
        row["arm"] = "holdout" if index < holdout_k else "dev"
    return {"seed": seed, "k": holdout_k, "scenarios": rows}


def split_manifest_document(
    corpus_version: str,
    scenario_arm: Mapping[str, str],
    *,
    items_by_scenario: Mapping[str, Mapping[str, int]],
    seed: str | None = None,
    k: int | None = None,
) -> dict[str, Any]:
    """The `splits.json` document: the ranked draw beside the roster and item counts it implies.

    `scenario_arm` covers every scenario in the export, benign ones as `dev` (rule B1);
    `items_by_scenario` holds the export's per-scenario item counts by label, which the command
    has and this module must not go find. The counts also decide the draw's population: only a
    scenario with an incident item can be drawn, so a caller that arms from `draw["scenarios"]`
    and joins benign as `dev` — the way the export command does — cannot put one document's `arms`
    and `draw` at odds. Item totals are aggregated by arm, so the published 64/177/209 arithmetic
    is derived here rather than transcribed. Raises KeyError for a corpus version with no
    pre-registered seed, and ExportConflict for a scenario armed outside dev/holdout or carrying a
    label outside benign/incident — the ways this module fails, all of which the command turns
    into its exit-2 paths.
    """
    draw = draw_split(
        corpus_version,
        sorted(name for name, counts in items_by_scenario.items() if counts.get("incident")),
        seed=seed,
        k=k,
    )
    arms: dict[str, list[str]] = {"dev": [], "holdout": []}
    items: dict[str, dict[str, int]] = {
        "dev": {"benign": 0, "incident": 0},
        "holdout": {"benign": 0, "incident": 0},
    }
    for name, arm in sorted(scenario_arm.items()):
        if arm not in arms:
            raise ExportConflict(f"{name} is armed '{arm}'; the split arms are dev and holdout")
        arms[arm].append(name)
        for label, count in items_by_scenario[name].items():
            if label not in items[arm]:
                raise ExportConflict(
                    f"{name} contributes label '{label}'; the split's labels are benign and "
                    "incident"
                )
            items[arm][label] += count
    return {
        "corpus_version": corpus_version,
        "seed": draw["seed"],
        "holdout_k": draw["k"],
        "unit": "scenario",
        "arms": arms,
        "draw": draw["scenarios"],
        "items": items,
    }


def split_sha256(document: dict[str, Any]) -> str:
    """The manifest's fingerprint: sha256 of the same canonical bytes `write_split` puts on disk."""
    return hashlib.sha256(_json_bytes(document)).hexdigest()


def write_split(export_dir: Path, document: dict[str, Any]) -> bool:
    """Write `splits.json` once: True if written now, False if identical bytes were already there.

    Create-once like `write_set`, but a manifest is one small file rather than a set's directory,
    so there is no half-written set to hide from a reader and no staging directory needed. The
    parent is created as `write_set` creates its category directory — a run that exported no set
    has no export directory yet. Raises ExportConflict if the file on disk holds different
    content: an export's split is not editable.
    """
    path = export_dir / SPLIT_FILE
    data = _json_bytes(document)
    if path.is_file():
        if path.read_bytes() != data:
            raise ExportConflict(f"{path} differs from the corpus; an export is create-once")
        return False
    export_dir.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return True


def read_split(export_dir: Path) -> dict[str, Any] | None:
    """The export's split manifest, or None for a pre-split export, which scores as unrecorded."""
    path = export_dir / SPLIT_FILE
    if not path.is_file():
        return None
    document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return document
