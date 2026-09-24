"""G0.4 eval store: a small SQLite ledger of frozen items, runs and results.

Off-repo by construction: the DB path is a required argument and production
callers pass a location outside the workspace (owner-confirmed path pending,
ledger F6). Items carry media PATHS only, and a privacy guard refuses paths that
point into the repo or a capture root — D10 is a privacy invariant, so a wrong
path is treated as a hard error, not a warning.

Replay discipline (spec §5): items are immutable once written; a run pins
engine+model provenance; replay reads exactly the rows of one run.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from backend.evaluation.assess_input import AssessInput, EvalItem

_LOG = logging.getLogger(__name__)

# Path prefixes that can only ever hold real-camera media (D10). Item media
# under these roots is refused at write time.
_REAL_MEDIA_PREFIXES = ("/data/captures", "/var/lib/hsi", "captures/", "data/events")
# D10's real test is RESIDENCE: media resolving inside the repo checkout is
# refused wherever the checkout lives. (An earlier "/agents/" substring guess
# refused the owner-ruled off-repo GPU eval root wholesale - F6 2026-09-24.)
_REPO_ROOT = Path(__file__).resolve().parents[2]


class EvalStore:
    def __init__(self, db_path: str | Path) -> None:
        self._db = sqlite3.connect(str(db_path))
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS items(
                item_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                fingerprint TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS runs(
                run_id TEXT PRIMARY KEY,
                engine TEXT NOT NULL,
                model TEXT NOT NULL,
                started_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS results(
                run_id TEXT NOT NULL REFERENCES runs(run_id),
                item_id TEXT NOT NULL REFERENCES items(item_id),
                verdict TEXT NOT NULL,
                risk_score INTEGER,
                raw_response TEXT NOT NULL,
                UNIQUE(run_id, item_id)
            );
            """
        )
        self._db.commit()

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> EvalStore:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # -- items ---------------------------------------------------------------
    def put_item(self, item: EvalItem) -> None:
        for p in item.media_paths:
            low = str(p).lower()
            if any(m in low for m in _REAL_MEDIA_PREFIXES):
                raise ValueError(
                    f"privacy: media path {p!r} looks like real-camera "
                    "media; eval items must reference synthetic/off-repo copies (D10)"
                )
            try:
                resolved = Path(p).expanduser().resolve()
            except OSError:
                resolved = Path(p)
            if resolved == _REPO_ROOT or _REPO_ROOT in resolved.parents:
                raise ValueError(
                    f"privacy: media path {p!r} resolves inside the repo checkout "
                    f"({_REPO_ROOT}); eval media must live off-repo (D10)"
                )
        payload = item.model_dump_json()
        digest = _fingerprint(item)
        try:
            self._db.execute(
                "INSERT INTO items(item_id, payload, fingerprint) VALUES(?,?,?)",
                (item.item_id, payload, digest),
            )
            self._db.commit()
        except sqlite3.IntegrityError as e:
            row = self._db.execute(
                "SELECT fingerprint FROM items WHERE item_id=?", (item.item_id,)
            ).fetchone()
            if row and row[0] != digest:
                raise ValueError(
                    f"item {item.item_id!r} is frozen; replaying over it changes content"
                ) from e
            # identical re-put is a no-op (idempotent ingest)

    def get_item(self, item_id: str) -> EvalItem | None:
        row = self._db.execute("SELECT payload FROM items WHERE item_id=?", (item_id,)).fetchone()
        return EvalItem.model_validate_json(row[0]) if row else None

    # -- runs / results ------------------------------------------------------
    def start_run(self, engine: str, model: str) -> str:
        run_id = uuid.uuid4().hex
        self._db.execute(
            "INSERT INTO runs(run_id, engine, model) VALUES(?,?,?)", (run_id, engine, model)
        )
        self._db.commit()
        return run_id

    def put_result(
        self, run_id: str, item_id: str, *, verdict: str, risk_score: int | None, raw_response: dict
    ) -> None:
        self._db.execute(
            "INSERT INTO results(run_id, item_id, verdict, risk_score, raw_response) VALUES(?,?,?,?,?)",
            (run_id, item_id, verdict, risk_score, json.dumps(raw_response)),
        )
        self._db.commit()

    def replay(self, run_id: str) -> list[dict[str, Any]]:
        cur = self._db.execute(
            "SELECT item_id, verdict, risk_score, raw_response FROM results WHERE run_id=? ORDER BY item_id",
            (run_id,),
        )
        return [
            {"item_id": r[0], "verdict": r[1], "risk_score": r[2], "raw_response": json.loads(r[3])}
            for r in cur.fetchall()
        ]


def _fingerprint(item: EvalItem) -> str:
    import hashlib

    return hashlib.sha256(item.model_dump_json().encode()).hexdigest()


# -------------------------------------------------------- synthetic loader

# Committed label sets (data/synthetic/<category>/<set>/expected_labels.json)
# carry no media and no camera/zone truth. The loader turns each set into a
# DRAFT EvalItem: media_paths stays empty (inventing a path would be a D10
# fabrication), camera_id is a constant synthetic sentinel, zone_crossing is
# never claimed from labels. Freezing the corpus into the store waits on the
# owner's F6 path decision and the pinned AssessInput shape.
_SYNTHETIC_CAMERA_ID = "synthetic-source"
_CATEGORY_LABELS = {"normal": "benign", "suspicious": "incident", "threats": "incident"}
# Each of the 13 scenarios exists as a committed label set in exactly one
# category (e.g. data/synthetic/normal/delivery_driver,
# data/synthetic/threats/package_theft) - verified 2026-09-24. Stock frames
# inherit that placement rather than a new judgement.
_SCENARIO_CATEGORY = {
    "delivery_driver": "normal",
    "pet_activity": "normal",
    "resident_arrival": "normal",
    "vehicle_parking": "normal",
    "yard_maintenance": "normal",
    "casing": "suspicious",
    "loitering": "suspicious",
    "prowling": "suspicious",
    "tailgating": "suspicious",
    "break_in_attempt": "threats",
    "package_theft": "threats",
    "vandalism": "threats",
    "weapon_visible": "threats",
}


def load_synthetic_items(corpus_dir: str | Path) -> list[EvalItem]:
    """Every `expected_labels.json` under corpus_dir becomes a draft item,
    sorted by id for a stable, fingerprintable order. Unreadable sets are
    skipped loudly (never fabricated around); a missing corpus is a hard error.
    """
    root = Path(corpus_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"synthetic corpus not found: {root}")
    out: list[EvalItem] = []
    for path in sorted(root.glob("*/*/expected_labels.json")):
        try:
            labels = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as e:
            _LOG.warning("skipping unreadable label set %s: %s", path, e)
            continue
        category = path.parent.parent.name
        label = _CATEGORY_LABELS.get(labels.get("category", category), category)
        risk = labels.get("risk") or {}
        vid = labels.get("video_id")
        item_id = f"synthetic:{category}:{path.parent.name}" + (f"::{vid}" if vid else "")
        out.append(
            EvalItem(
                item_id=item_id,
                media_paths=[],
                expected_label=label,
                expected_risk_score=_midpoint(risk),
                snapshot=AssessInput(
                    camera_id=_SYNTHETIC_CAMERA_ID,
                    detections=list(labels.get("detections") or []),
                    zones=[],
                    zone_crossing=False,
                    household={},
                    timestamp=_generated_at(path),
                ),
                source="synthetic",
            )
        )
    return out


def load_stock_items(media_root: str | Path) -> list[EvalItem]:
    """Stock frames (F5, off-repo) become media-bearing DRAFT items.

    One item per scenario directory: the frame paths are what the VLM
    verifier will actually see, so this is the corpus S-3 has been waiting
    on. Nothing here is invented —

    * the benign/incident label comes from `_SCENARIO_CATEGORY`, which mirrors
      where the COMMITTED corpus places each scenario (`normal/delivery_driver`
      etc. exist beside `threats/package_theft`), not a guess;
    * detections/zones are not claimed from a still frame: the snapshot carries
      zero detections and zone_crossing False, and expected_risk_score is 0
      (unknown) rather than a fabricated band;
    * a still frame has no generation timestamp; the honest epoch sentinel
      stands (never invented). Attribution rides beside each frame as its
      sidecar JSON, not inside the item.

    A missing root is a hard error; an unreadable manifest skips the scenario
    loudly. The D10 guard in put_item still decides residence.
    """
    root = Path(media_root)
    if not root.is_dir():
        raise FileNotFoundError(f"stock media root not found: {root}")
    out: list[EvalItem] = []
    for dirpath in sorted(p for p in root.iterdir() if p.is_dir()):
        scenario = dirpath.name
        category = _SCENARIO_CATEGORY.get(scenario)
        if category is None:
            _LOG.warning("skipping unknown stock scenario %s (no committed label)", scenario)
            continue
        manifest = dirpath / "manifest.json"
        try:
            frames = json.loads(manifest.read_text())
        except (OSError, json.JSONDecodeError) as e:
            _LOG.warning("skipping stock scenario %s: unreadable manifest: %s", scenario, e)
            continue
        paths = [str(f["file"]) for f in frames if isinstance(f, dict) and f.get("file")]
        if not paths:
            _LOG.warning("skipping stock scenario %s: manifest lists no frames", scenario)
            continue
        out.append(
            EvalItem(
                item_id=f"stock:{scenario}",
                media_paths=paths,
                expected_label=_CATEGORY_LABELS[category],
                expected_risk_score=0,  # stills carry no risk band; unknown is honest
                snapshot=AssessInput(
                    camera_id=_SYNTHETIC_CAMERA_ID,
                    detections=[],  # never claimed from a still frame
                    zones=[],
                    zone_crossing=False,
                    household={},
                    timestamp=_generated_at(manifest),
                ),
                source="stock",
            )
        )
    return out


def _midpoint(risk: dict[str, Any]) -> int:
    """Expected score = the set's declared risk band midpoint (normal 10-30,
    suspicious 35-60, threats 85-100); unbounded band -> 0 (unknown, honest)."""
    lo, hi = risk.get("min_score"), risk.get("max_score")
    if isinstance(lo, (int, float)) and isinstance(hi, (int, float)):
        return int((lo + hi) // 2)
    return 0


def _generated_at(labels_path: Path) -> str:
    """Timestamp from the sibling metadata.json when present; epoch 0 as the
    honest sentinel otherwise (the snapshot must carry a timestamp, but the
    loader must not invent one)."""
    meta = labels_path.parent / "metadata.json"
    try:
        data = json.loads(meta.read_text())
        ts = data.get("generated_at")
        if isinstance(ts, str) and ts:
            return ts
    except OSError, json.JSONDecodeError:
        pass
    return "1970-01-01T00:00:00+00:00"
