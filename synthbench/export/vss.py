"""The VSS eval-store layout for synthbench events (P5a design §2).

`import_generated_items` (`backend/evaluation/label_import.py`) reads
`<category>/<set>/expected_labels.json` plus the set's media, with one attribution sidecar per
frame. This module holds the pure pieces of writing that layout and of reading it back for the
audit and the scorer. It imports nothing from `backend`; a test pins the category vocabulary
below equal to the importer's.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

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


def category_of(spec: Spec) -> str | None:
    """The event's category directory, or None for an ambiguous event, which is not exported."""
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


def labels_document(spec: Spec, still_sha256: str) -> dict[str, Any]:
    """`expected_labels.json`: the keys the importer reads, plus the event's facts for scoring."""
    category = CATEGORY[spec.cell.group]
    lo, hi = spec.risk_band
    return {
        "category": category,
        "risk": {"min_score": lo, "max_score": hi},
        "timestamp": scene_timestamp(spec.scene_time, spec.cell.weather),
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
