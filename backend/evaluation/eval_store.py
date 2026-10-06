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
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Annotation-only: the face types are imported lazily inside the render
    # helpers so the eval-store import closure stays light (same reason the
    # shipped text builders are imported in-function, not at module level).
    from backend.services.vlm_specialists import FaceOutcome

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
        # The store DIRECTORY names the generation (gen-1 / gen-2 / ... by
        # ruling, one dir per generation at a new path) - a replay report
        # must be able to say which corpus it measured without carrying an
        # absolute path anywhere near git (D10).
        self.dir_name = Path(db_path).resolve().parent.name
        self._db = sqlite3.connect(str(db_path))
        self._db.execute("PRAGMA foreign_keys = ON")
        # A contended write waits instead of aborting (G0 close-out audit #12):
        # a sharded freeze run shares one store file.
        self._db.execute("PRAGMA busy_timeout = 30000")
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
            CREATE TABLE IF NOT EXISTS splits(
                corpus_version TEXT NOT NULL,
                scenario TEXT NOT NULL,
                arm TEXT NOT NULL CHECK (arm IN ('dev','holdout')),
                seed TEXT NOT NULL,
                manifest_sha256 TEXT NOT NULL,
                PRIMARY KEY (corpus_version, scenario)
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
            # casefold as well as compare: on a case-insensitive dev FS (macOS)
            # /AGENTS/... and the real root are the same file, but a plain
            # parents check misses it on the case-sensitive box (audit #18).
            r_low, root_low = str(resolved).casefold(), str(_REPO_ROOT).casefold()
            if (
                r_low == root_low
                or root_low in [str(x) for x in Path(r_low).parents]
                or resolved == _REPO_ROOT
                or _REPO_ROOT in resolved.parents
            ):
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

    def iter_items(self, *, with_media_only: bool = False) -> list[EvalItem]:
        """Every frozen item, ordered by id (the replay walks the corpus in a
        fixed order so two runs of the same generation are comparable line for
        line). Purely a read - `replay()` is the results-side twin of this
        items-side need; neither had a caller until the Phase 2 harness."""
        sql = "SELECT payload FROM items"
        if with_media_only:
            # A cheap pre-filter only: the pattern also matches the EMPTY
            # array (`"media_paths":[]`), so it narrows the scan and decides
            # nothing - the parse below re-checks each row. The pin
            # `test_with_media_only_excludes_born_labeled_items` is what keeps
            # this honest.
            sql += " WHERE payload LIKE '%\"media_paths\":[%'"
        rows = self._db.execute(sql + " ORDER BY item_id").fetchall()
        out: list[EvalItem] = []
        for (payload,) in rows:
            item = EvalItem.model_validate_json(payload)
            if with_media_only and not item.media_paths:
                continue
            out.append(item)
        return out

    # -- splits (ISS-016) ----------------------------------------------------
    def put_split(
        self,
        corpus_version: str,
        rows: Sequence[Mapping[str, Any]],
        *,
        seed: str,
        manifest_sha256: str,
    ) -> None:
        """Record one corpus version's dev/holdout roster (spec §3).

        Flat rows on purpose: the table stores no JSON, so a later change to
        `splits.json`'s shape is the writer's problem, not the store's. A
        store's split is born once, same posture as the frozen-item rule —
        re-putting identical rows is a no-op (the replay's import step is
        idempotent end to end, so a rerun of a crashed run re-puts every row
        it already wrote), and anything that would EDIT a recorded row raises.

        The version-level manifest check runs BEFORE the first write, not off
        the primary-key conflict: a roster that only ADDS a scenario never
        collides, so a sha check hung off the conflict alone would silently
        accept a second manifest for one corpus version. Commits are per row
        like `put_item`'s — §3 needs no shared transaction, because every
        refusal is decided by the recorded rows and the incoming digest, so a
        rerun reaches the same answer whichever row it stopped at.
        """
        stored = {
            scenario: (arm, row_seed, row_sha)
            for scenario, arm, row_seed, row_sha in self._db.execute(
                "SELECT scenario, arm, seed, manifest_sha256 FROM splits WHERE corpus_version=?",
                (corpus_version,),
            )
        }
        recorded = {sha for _, _, sha in stored.values()}
        if recorded and recorded != {manifest_sha256}:
            raise ValueError(
                f"split for corpus version {corpus_version!r} is already recorded under "
                f"manifest_sha256 {sorted(recorded)}; refusing {manifest_sha256!r}"
            )
        for row in rows:
            scenario, arm = str(row["scenario"]), str(row["arm"])
            if existing := stored.get(scenario):
                stored_arm, stored_seed, stored_sha = existing
                if stored_arm != arm:
                    raise ValueError(
                        f"split for {corpus_version!r}: scenario {scenario!r} is already "
                        f"recorded as {stored_arm!r}; refusing {arm!r}"
                    )
                if (stored_seed, stored_sha) != (seed, manifest_sha256):
                    raise ValueError(
                        f"split for {corpus_version!r}: scenario {scenario!r} is already "
                        f"recorded under seed {stored_seed!r}/"
                        f"manifest_sha256 {stored_sha!r}; refusing {seed!r}/{manifest_sha256!r}"
                    )
                continue
            try:
                self._db.execute(
                    "INSERT INTO splits(corpus_version, scenario, arm, seed, manifest_sha256) "
                    "VALUES(?,?,?,?,?)",
                    (corpus_version, scenario, arm, seed, manifest_sha256),
                )
                self._db.commit()
            except sqlite3.IntegrityError as e:
                row_now = self._db.execute(
                    "SELECT arm, seed, manifest_sha256 FROM splits "
                    "WHERE corpus_version=? AND scenario=?",
                    (corpus_version, scenario),
                ).fetchone()
                if row_now == (arm, seed, manifest_sha256):
                    # identical re-put racing another writer: a no-op, like items
                    continue
                # an arm outside dev/holdout trips the CHECK, which arrives as
                # IntegrityError; the caller's refusal path is ValueError (the
                # frozen-item rule's shape), so wrap it with the row shown.
                raise ValueError(
                    f"split row for corpus version {corpus_version!r} is refused: {row!r}"
                ) from e

    def get_split(self, corpus_version: str) -> list[dict[str, Any]] | None:
        """The recorded roster by scenario, or None when this version was
        never split — an unsplit export must not read as an empty roster."""
        rows = self._db.execute(
            "SELECT scenario, arm, seed, manifest_sha256 FROM splits "
            "WHERE corpus_version=? ORDER BY scenario",
            (corpus_version,),
        ).fetchall()
        if not rows:
            return None
        return [
            {"scenario": r[0], "arm": r[1], "seed": r[2], "manifest_sha256": r[3]} for r in rows
        ]

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


def resolve_category_label(placement: str, declared: Any, *, origin: str) -> str:
    """THE label authority for a corpus set: the DIRECTORY it lives in.

    A set's `expected_labels.json` may carry a `category` key, and that key
    may CONFIRM the placement — it may never overrule it, and it may never
    rescue an unknown directory into a guessed label (ledger item 33). Two
    disagreeing sources is a refusal, not a precedence decision: an incident
    that reads benign deflates the exact side S2 ranks incidents against, so
    silently picking a winner would bend the measurement, not just report it.

    Refusing is also the cheap option here: measured on the committed corpus
    before this existed, 366 sets agree, 47 declare nothing, and ZERO
    conflicted or used an out-of-vocabulary name.

    `origin` names the set in the error so whoever generated it can find the
    directory — "bad category" alone is not actionable.
    """
    if placement not in _CATEGORY_LABELS:
        raise ValueError(
            f"synthetic corpus {origin}: placed under {placement!r}, which is "
            f"outside the category vocabulary {sorted(_CATEGORY_LABELS)}. The "
            "directory is the label's authority, so an unknown one cannot be "
            "labeled at all — moving the set is the fix, not adding a name."
        )
    if declared is None:
        return _CATEGORY_LABELS[placement]
    if declared not in _CATEGORY_LABELS:
        raise ValueError(
            f"synthetic corpus {origin}: declares category {declared!r}, which "
            f"is outside the vocabulary {sorted(_CATEGORY_LABELS)}. It would "
            "become a label no reader counts, and the size bar would report "
            "it as `unknown` on neither side."
        )
    if declared != placement:
        raise ValueError(
            f"synthetic corpus {origin}: sits under {placement!r} but declares "
            f"category {declared!r}. The two sources disagree about whether "
            "this is a benign or an incident item; refusing rather than "
            "choosing, because a flipped label here is invisible downstream."
        )
    return _CATEGORY_LABELS[placement]


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

    An ambiguous LABEL is also a hard error, not a skip: a set that disagrees
    with its own directory, or names a category outside the vocabulary, is
    refused whole by `resolve_category_label`. Skipping it would freeze the
    silence that made the bug invisible in the first place.
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
        if not isinstance(labels, dict):
            _LOG.warning(
                "skipping label set %s: JSON is %s, not an object", path, type(labels).__name__
            )
            continue
        category = path.parent.parent.name
        label = resolve_category_label(
            category, labels.get("category"), origin=f"{category}/{path.parent.name}"
        )
        # a malformed risk band is "unknown", never a crash (audit #14)
        raw_risk = labels.get("risk")
        risk = raw_risk if isinstance(raw_risk, dict) else {}
        if raw_risk is not None and not isinstance(raw_risk, dict):
            _LOG.warning(
                "label set %s has a non-object risk band %r; scoring unknown", path, raw_risk
            )
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
                    specialist_outputs=_render_specialist_outputs(
                        labels, origin=f"{category}/{path.parent.name}"
                    ),
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
        if not isinstance(frames, list):
            _LOG.warning(
                "skipping stock scenario %s: manifest is %s, not a list",
                scenario,
                type(frames).__name__,
            )
            continue
        # Containment (G0 close-out audit #1): D10 answers "is this repo/
        # capture media?" — an off-repo /etc/shadow passes it. The fetcher's
        # contract is frames-live-in-their-scenario-dir, so the loader holds
        # the manifest to that: a named frame must resolve inside dirpath.
        paths: list[str] = []
        for entry in frames:
            raw = entry.get("file") if isinstance(entry, dict) else None
            if not raw:
                continue
            resolved = Path(str(raw)).expanduser()
            resolved = resolved if resolved.is_absolute() else (dirpath / resolved)
            resolved = resolved.resolve()
            if dirpath.resolve() not in resolved.parents:
                _LOG.warning(
                    "skipping stock scenario %s: manifest path %r escapes the scenario dir",
                    scenario,
                    raw,
                )
                continue  # the frame is refused; if that empties the item, the no-frames check below skips the scenario
            paths.append(str(resolved))
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


def _render_specialist_outputs(labels: dict[str, Any], *, origin: str) -> dict[str, str]:
    """1.3b: a label set's declared `specialist_context` becomes the snapshot's
    `specialist_outputs` — rendered through the SHIPPED classifier and text
    builders (vlm_specialists), never a literal string stored on the label
    set. That is what makes the F12 clause ("a tiny or night face yields
    `not identifiable`, never `unknown`") a property of the corpus rather
    than a restatement: the loader and the live stage run the same gate, off
    the same config knobs (face_min_size_px / face_scrfd_threshold).

    The block is the scenario's GIVEN (which faces/plates the stage would
    find), so it carries synthetic px/score values with no gate risk; real
    pixels are not involved. Every key of SPECIALIST_KEYS lands when the
    block exists: an undeclared specialist records `unavailable`, per the
    plan's rule that an absent specialist never stays silent. A key that
    cannot render degrades to unavailable loudly — the item still loads,
    like a malformed risk band scoring unknown.
    """
    raw = labels.get("specialist_context")
    if not isinstance(raw, dict) or not raw:
        return {}
    if unknown_keys := set(raw) - {"faces", "plates", "person_reid"}:
        _LOG.warning("label set %s declares unknown specialist keys %s", origin, unknown_keys)

    from backend.core.config import get_settings
    from backend.services.vlm_specialists import SPECIALIST_KEYS, face_text, plate_text, reid_text

    settings = get_settings()

    def render(key: str) -> str:
        # The dict's VALUE is the bare census line (the stage's own shape -
        # the key names the specialist; the prompt renders the pair).
        spec = raw.get(key)
        if spec is None:
            # Declared block, undeclared specialist: honestly unavailable.
            # The shipped _unavailable_line is deliberately NOT called here:
            # it increments the live metric, and loading a corpus is not a
            # specialist failing in the field.
            return "unavailable: specialist did not run"
        try:
            if key == "faces":
                return face_text(_face_outcomes(spec, settings))
            if key == "plates":
                return plate_text(*_plate_args(spec))
            if key == "person_reid":
                return reid_text(*_reid_args(spec))
        except (TypeError, ValueError, KeyError) as exc:
            _LOG.warning(
                "label set %s has an unrenderable %s spec %r: %s — recording unavailable",
                origin,
                key,
                spec,
                exc,
            )
        return "unavailable: specialist did not run"

    return {key: render(key) for key in sorted(SPECIALIST_KEYS)}


def _face_outcomes(spec: Any, settings: Any) -> list[FaceOutcome]:
    """Face specs drive the shipped classify_face_outcome (gate first, then
    the gallery) — same function the live leg and enrollment share."""
    from backend.services.vlm_specialists import classify_face_outcome

    if not isinstance(spec, dict):
        raise TypeError(f"faces spec must be an object, got {type(spec).__name__}")
    outcomes: list[FaceOutcome] = []
    match = spec.get("known_person")
    if match:
        outcomes.append(
            classify_face_outcome(
                face_px=float(spec.get("known_face_px", 120)),
                scrfd_score=float(spec.get("known_scrfd_score", 0.83)),
                match={
                    "matched": True,
                    "person_name": str(match),
                    "similarity": float(spec.get("similarity", 0.7)),
                },
                min_px=settings.face_min_size_px,
                min_score=settings.face_scrfd_threshold,
            )
        )
    # unknown_count crops carry a size (unknown_face_px) so a config change
    # moves them through the gate exactly like a live crop would.
    for _ in range(int(spec.get("unknown_count", 0))):
        outcomes.append(
            classify_face_outcome(
                face_px=float(spec.get("unknown_face_px", max(settings.face_min_size_px, 120))),
                scrfd_score=float(spec.get("unknown_scrfd_score", 0.83)),
                match=None,
                min_px=settings.face_min_size_px,
                min_score=settings.face_scrfd_threshold,
            )
        )
    # tiny_count is the declared gate-FAILING crop (the owner's night case):
    # sized below any sane floor on purpose, the classifier must not call it
    # unknown whatever the gallery says.
    for _ in range(int(spec.get("tiny_count", 0))):
        outcomes.append(
            classify_face_outcome(
                face_px=float(spec.get("tiny_face_px", 24)),
                scrfd_score=float(spec.get("tiny_scrfd_score", 0.82)),
                match=None,
                min_px=settings.face_min_size_px,
                min_score=settings.face_scrfd_threshold,
            )
        )
    if not outcomes:
        raise ValueError("faces spec declares no outcome")
    return outcomes


class _SpecPlate:
    def __init__(self, text: str) -> None:
        self.text = text


class _SpecPlateMatch:
    def __init__(self, text: str, member: str) -> None:
        self.text = text
        self.matched = True
        self.member_name = member


def _plate_args(spec: Any) -> tuple[list[_SpecPlate], list[_SpecPlateMatch]]:
    if not isinstance(spec, dict) or not isinstance(spec.get("plates"), list):
        raise TypeError("plates spec must be {'plates': [...]}")
    results: list[_SpecPlate] = []
    matches: list[_SpecPlateMatch] = []
    for entry in spec["plates"]:
        if not isinstance(entry, dict) or "text" not in entry:
            raise ValueError(f"plate entry needs a text, got {entry!r}")
        text = str(entry["text"])
        results.append(_SpecPlate(text))
        member = entry.get("household_member")
        if member:
            matches.append(_SpecPlateMatch(text, str(member)))
    if not results:
        raise ValueError("plates spec declares no plate")
    return results, matches


def _reid_args(spec: Any) -> tuple[Any, str | None]:
    """reid_text(matches, unavailable_reason) — the corpus declares which arm:
    a match list, no-match, or an explicit unavailable reason."""
    if not isinstance(spec, dict):
        raise TypeError("person_reid spec must be an object")
    if spec.get("unavailable"):
        return None, str(spec["unavailable"])
    members = spec.get("known_matches") or []
    if not isinstance(members, list):
        raise ValueError("known_matches must be a list")
    if not members:
        return [], None  # the leg ran and found nothing

    class _M:
        def __init__(self, name: str, similarity: float | None) -> None:
            self.member_name = name
            self.similarity = similarity

    return [_M(str(m["name"]), m.get("similarity")) for m in members], None


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


# ------------------------------------------------------ generation builder
def build_gen2(
    store_dir: str | Path,
    *,
    corpus_dir: str | Path,
    stock_root: str | Path,
) -> dict[str, Any]:
    """Eval-store GENERATION 2 - the corpus the Phase 2 replay can actually run
    against (plan 2.0.1).

    WHY THIS EXISTS (measured on the frozen store, Phase 2 plan §0): gen-1's
    421 frozen snapshots carry the PRE-rev-6 six keys - zero of them hold
    `specialist_outputs` - and the freeze makes that unfixable in place
    (`put_item` refuses a changed fingerprint). A replay over gen-1 sends an
    empty specialist block on every item and measures a system 1.3b did not
    ship. The repo corpus has since grown the five 1.3b verdict-changing sets,
    so the fix is a NEW generation at a NEW path built by the SAME shipped
    loaders - never an edit of the frozen file (D-P2-1). gen-1 stays on disk,
    byte-identical, as the record of what G0.4 froze.

    Guards, in the order that writes nothing on a rejected build:

    1. a missing corpus is a hard error (the loaders already refuse);
    2. ZERO items with a rendered specialist block aborts the build - that is
       gen-1's defect rebuilt and green, the one outcome 2.0 must not ship;
    3. pointing at a generation that already holds items the new corpus does
       not contain refuses, because that is the mutation the per-item freeze
       exists to prevent, spotted here as one aggregate error instead of
       hundreds of item-by-item ones.

    The report is read BACK OUT OF THE DATABASE, not from the in-memory list:
    the numbers a run is later compared against have to be the numbers the
    write actually produced. Aggregate counts only - no item content (D10).
    """
    out_dir = Path(store_dir)
    # The store DIRECTORY is the D10 boundary - the item-level guard checks
    # where media resolves; nothing checks where the corpus itself lands. A
    # labeled store inside the checkout is one `git add -A` from the privacy
    # line, so this refuses before a corpus is read or a file is created.
    try:
        resolved_dir = out_dir.resolve()
    except OSError:
        resolved_dir = out_dir.absolute()
    if resolved_dir == _REPO_ROOT or _REPO_ROOT in resolved_dir.parents:
        raise RuntimeError(
            f"gen-2 build refused: {out_dir} resolves INSIDE the repo checkout "
            f"({_REPO_ROOT}). The eval store is off-repo by ruling (D10/F6) - "
            f"pass a location outside the workspace, e.g. "
            f"$AGENT_GPU_DIR/out/eval-store/gen-2."
        )

    synthetic = load_synthetic_items(corpus_dir)
    stock = load_stock_items(stock_root)
    items = [*synthetic, *stock]

    if not any(i.snapshot.specialist_outputs for i in items):
        raise RuntimeError(
            f"gen-2 build refused: 0 of {len(items)} items carry a rendered "
            f"specialist_outputs block. That is gen-1's defect rebuilt - the "
            f"corpus must include the label sets declaring specialist_context "
            f"(1.3b's verdict-changing cases), or the replay measures a "
            f"system without the specialist stage."
        )

    db_file = out_dir / "eval.sqlite"
    pre_existed = db_file.exists()
    out_dir.mkdir(parents=True, exist_ok=True)
    store = EvalStore(db_file)

    if pre_existed:
        # Idempotent rebuild (identical inputs -> identical fingerprints, and
        # put_item's no-op on an identical re-put) is allowed. Anything else
        # is writing a different corpus into an existing generation.
        incoming = {_fingerprint(i) for i in items}
        stale = [
            item_id
            for (item_id, fp) in store._db.execute("SELECT item_id, fingerprint FROM items")
            if fp not in incoming
        ]
        if stale:
            raise RuntimeError(
                f"gen-2 build refused: {len(stale)} items in the EXISTING store "
                f"at {db_file} are not in this corpus (first: {stale[0]!r}). "
                f"A generation is immutable once built - build a new one at a "
                f"new path."
            )

    for item in items:
        store.put_item(item)

    report: dict[str, Any] = {
        "items": 0,
        "benign": 0,
        "incident": 0,
        "with_media": 0,
        "with_specialist_outputs": 0,
    }
    for (payload,) in store._db.execute("SELECT payload FROM items ORDER BY item_id"):
        d = json.loads(payload)
        report["items"] += 1
        label = d.get("expected_label")
        if label in ("benign", "incident"):
            report[label] += 1
        if d.get("media_paths"):
            report["with_media"] += 1
        if d.get("snapshot", {}).get("specialist_outputs"):
            report["with_specialist_outputs"] += 1
    report["store"] = str(db_file)
    _LOG.info(
        "eval-store gen-2 built at %s: %d items (benign %d / incident %d), "
        "%d media-bearing, %d with specialist context",
        db_file,
        report["items"],
        report["benign"],
        report["incident"],
        report["with_media"],
        report["with_specialist_outputs"],
    )
    return report
