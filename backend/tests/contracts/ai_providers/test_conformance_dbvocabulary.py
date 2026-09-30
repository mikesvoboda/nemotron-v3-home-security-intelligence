"""WP8.5 — vocabulary conformance: server emitters vs the database CHECKs.

Plan: docs/superpowers/plans/2026-09-19-swap-readiness-72h.md §WP8.5 (L1027-1075).
The DB is the de-facto conformance spec — enforced too late (at INSERT) and nowhere
in unit tests. This module makes the server-emitted vocabularies assert against
the ORM CheckConstraints they must satisfy. The mirror discipline is the point of
the file: every alphabet is read out of SHIPPED SOURCE by AST (or executed to the
wire), never transcribed, so a rename upstream reddens HERE rather than silently
in a DB INSERT hours later.

INTEGRATED (2026-09-19): first in-tree contact 16 passed / 7 failed — all seven
the module's own section-1 prediction. Per the goal rule (branch stays GREEN; a
RULING-blocked finding is pinned as a characterization, never left red) the subset
assertions pin the EXACT illegal sets as DATA — each names the parked alignment
ruling and flips red the day behavior changes, which is the tripwire, not a
defect escaping. NO xfail / skip / importorskip anywhere (goal rule).

R8 S2 (2026-09-29, legacy-tier retirement) cut this module from SEVEN subset
assertions to SIX and dropped the is_minor section: three of its subjects were
emitters in the retired tier (backend/services/vitpose_loader.py,
backend/services/enrichment_pipeline.py, backend/services/age_classifier_loader.py).

R8 S3 (2026-09-29, owner rulings 1-5) is the bigger cut, because S3 deleted the
serving directories this module's emitters lived IN: ``ai/enrichment/``,
``ai/enrichment-light/``, ``ai/clip/`` and ``ai/florence/`` are gone (via
``git rm``, ruling 4), and the prune to three resident models made gateway CLIP
unbootable. That deleted FIVE of the six emitters this file mirrored — both
``threat_detector.py`` twins (int map + BY_NAME map), the vitpose posture table,
the enrichment pose estimator's ``_classify_pose``, and the demographics server's
AGE_RANGES / GENDER_LABELS — plus the import-and-sys.path-hygiene helper that
loaded them. The module is REWRITTEN onto the surviving surface rather than
quietly shrunk:

  * THE surviving threat emitter is the gateway adapter's function-local
    ``THREAT_CLASSES`` at ai/gateway/adapters/enrichment_light.py:84, and its
    out-of-range fallback spelling ``f"threat_{cls_id}"`` at :108. Section 1
    mirrors that table against ``ck_threat_detections_threat_type`` and EXECUTES
    the fallback onto the wire, because an emitted name is exactly what a CHECK
    later refuses.
  * THE surviving pose emitter is ai/yolo26/pose_estimation.py::classify_pose.
  * THE surviving class emitter is the gateway yolo26 adapter's 80-name
    ``COCO_CLASSES``, which flows into the CHECK-less ``detections.object_type``.
  * The five lost mirrors are TOMBSTONED (section 3): hazard stated in full,
    retired source proven absent, and a non-vacuity assertion naming the live
    place the same hazard class still occurs — never a skip, never a silent
    deletion (the S2b grammar; house precedents TestO1ActionClassifyTombstone /
    TestO2CompositeEnrichTombstone in test_conformance_ops.py).
  * Section 4's dimension invariant loses its 768 pair: CLIP's space retired
    with it, so the surviving registry is ONE 512-d space, derived from an AST
    scan rather than imported (importing backend.services.reid_service costs
    ~2.3s and imports nothing else in this tier needs). The unit-norm leg
    re-homes onto the one backend-side normalizer still shipped —
    ``face_recognizer_loader.extract_face_embedding`` — executed with a fake
    session.

R8 S4 (2026-09-30, owner ruling) closed the demographics half of this module
from the DB side: the ``demographics_results`` and ``reid_embeddings`` tables
and their ORM classes were DROPPED (zero live readers, zero shipped writers).
Consequences here, none of them a silent shrink:
  * ``DB_GENDER`` / ``DB_AGE`` — which this module DERIVED off
    ``DemographicsResult``'s two CHECKs — are gone with the class. They are not
    re-typed as literals: a remembered copy of a dropped CHECK's value set is
    exactly the transcription this file's "read it out of shipped source"
    discipline exists to prevent, and nothing else shipped can be parsed for it.
  * The two demographics tombstones in section 3 gain their second half (the
    storage side, previously asserted LIVE) and keep a non-vacuity leg — the
    ``scripts/seed-events.py`` alphabets they compared themselves against were
    pruned by the same slice, so both non-vacuities are retargeted, not deleted.
  * ``DB_POSE`` / ``DB_THREAT`` / ``DB_SEVERITY`` are untouched: ``pose_results``,
    ``threat_detections`` and ``action_results`` all survive S4 (the owner kept
    them with the ``pose_types``/``action_types``/``threat_detection_enabled``
    rule fields their alert_engine reader feeds).

===========================================================================
CITE-CORRECTION NOTES (plan line numbers drifted; corrected cites verified
against THIS tree):
===========================================================================
  1. The plan cites the DB CHECKs as `api/schemas/enrichment.py` — the file
     is actually backend/models/enrichment.py (pose :79-80, threat :139-142,
     gender :193-199, age :197-200). backend/api/schemas/alerts.py carries a
     PARITY COPY of three of the sets (VALID_POSE_CLASSES :75-77,
     VALID_THREAT_TYPES :81, VALID_THREAT_SEVERITIES :85) and those copies are
     the LIVE enforcement point — they are the validators on AlertRuleCreate /
     AlertRuleUpdate, reached from backend/api/routes/alerts.py — so
     TestSchemaParity pins all three against the ORM.
  2. The plan's "12 threat values" was the STRING-keyed THREAT_CLASSES_BY_NAME
     map in the deleted server; the int-keyed THREAT_CLASSES beside it was a
     DIFFERENT 6-value set. Both retired in S3 (section 3 records both deltas
     as they were shipped). The surviving adapter has ONE table — and the
     single-registry claim that replaces the old twins-equality is DERIVED from
     a scan, so a second table appearing anywhere in shipped code reddens it.
  3. ``ai/gateway`` is no longer n/a to this module: after S3 the gateway
     adapter IS the provider-side vocabulary. Nothing imports ``ai.*`` here —
     the adapter is AST-read (its table is function-local, which
     ``ast.walk`` reaches) and the one executed leg imports it inside the test.
  4. Plan says "Four will fail" (one per vocabulary row); first contact found
     SEVEN. Five of those seven are now tombstones and two survive
     (yolo26 pose, and the threat row re-homed onto the adapter).

DB-TOUCHING TEST — CHOICE (stated per plan bullet 4): this module does NOT
connect to Postgres. The executed-INSERT evidence the plan asks for was
captured at 88215286..a8c25c5e (8/8 values rejected vs host Postgres 16.15,
each in its own SAVEPOINT, zero persistence). CORRECTION (R8 S3): the earlier
header pointed a reader at a ``DB_CONSTRAINT_CONTRACTS`` tier in
test_conformance_numeric.py; no such tier exists or existed in that file, and
this module is the only in-tree place the ``ck_*`` texts are asserted, so the
CHECK-parsing legs below are load-bearing for the whole repo and the executed
evidence is historical. Everything here is a pure static/ORM/AST assert plus
three executed pure functions.

IMPORT-THAT-HALT SURVEY (this .venv, Python 3.14 — measured on this branch):
  ai.enrichment / ai.enrichment-light / ai.clip -> packages DELETED (R8 S3);
      nothing here imports them, so the sys.path / namespace-stub hygiene the
      previous header documented is GONE with them: the only shipped module
      that still mutates sys.path is ai/yolo26/model.py, which this module
      never imports (the adapter files it reads are AST-only).
  ai/gateway/adapters/enrichment_light -> importable, 0.33s, leaves no
      ``triton`` entry in sys.modules (verified). Imported INSIDE the one test
      that executes it, so collection stays cheap.
  backend/models/* -> importable at module level (ORM only).
  backend.services.face_recognizer_loader -> importable, 1.61s; imported
      inside its own test (the tier budget is per-test, not per-module).
  backend.services.threat_monitor_service -> importable, 1.86s; NOT imported and
      NOT AST-read here — it is named in prose only, as the consumer whose
      THREAT_SEVERITY_MAPPING never heard of ``threat_object``.
"""

from __future__ import annotations

import ast
import base64
import io
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from backend.api.schemas import llm_response as llm_schema
from backend.models.detection import Detection
from backend.models.enrichment import PoseResult, ThreatDetection
from backend.models.entity import Entity
from backend.models.event import Event


def _find_repo_root() -> Path:
    """Walk up from this file to the directory carrying BOTH the backend and
    ai trees (the draft's /tmp copy could not resolve this — one reason its
    four AST legs were vacuously green there). Portable on purpose: no
    machine-specific literal, because the CI checkout path is not this one."""
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "backend" / "models" / "enrichment.py").is_file() and (
            candidate / "ai"
        ).is_dir():
            return candidate
    raise AssertionError("test_conformance_dbvocabulary.py sits outside a repo root")


REPO_ROOT = _find_repo_root()

# Directories that hold SHIPPED (non-test) python, and therefore hold any
# vocabulary table a provider could emit. Bounded on purpose: an unbounded
# tree walk is how a 669-line file turns into a 4-second test (WP1.3), and a
# vocabulary that lives outside these trees is not an emitter.
SHIPPED_TREES: tuple[str, ...] = (
    "ai/gateway",
    "ai/yolo26",
    "backend/models",
    "backend/api",
    "backend/services",
    "backend/core",
    "scripts",
)


# ---------------------------------------------------------------------------
# Source helpers (repo precedent: backend/tests/contracts/ai_providers/
# test_conformance_vocabulary.py `_ast_assign`).
#
# COST DISCIPLINE (WP1.3 — a 4.0s unit-test limit that this repo has already
# breached once by scanning a tree in one test id): the shipped-tree scan is
# (a) prefiltered by a raw substring on the file TEXT, so only the handful of
# files that literally mention the needle are parsed, and (b) memoized, so the
# six scan-driven tests in this module share one walk instead of paying for
# six. Measured: 0.15s for the whole first scan, ~0ms for every later one.
# ---------------------------------------------------------------------------

_SHIPPED_TEXTS: list[tuple[Path, str]] = []
_PARSED: dict[Path, ast.Module] = {}


def _shipped_texts() -> list[tuple[Path, str]]:
    """Every non-test .py under SHIPPED_TREES with its text, memoized (a list
    that fills once — no rebinding, so no ``global`` needed)."""
    if not _SHIPPED_TEXTS:
        for tree in SHIPPED_TREES:
            for path in sorted((REPO_ROOT / tree).rglob("*.py")):
                if "tests" in path.parts or "__pycache__" in path.parts:
                    continue
                _SHIPPED_TEXTS.append((path, path.read_text(encoding="utf-8")))
    return _SHIPPED_TEXTS


def _parsed(path: Path) -> ast.Module:
    tree = _PARSED.get(path)
    if tree is None:
        tree = _PARSED[path] = ast.parse(path.read_text(encoding="utf-8"))
    return tree


def _files_mentioning(needle: str) -> list[Path]:
    """Cheap prefilter: files whose TEXT contains the needle. This is what
    keeps a tree-wide scan off the WP1.3 budget — the parse only happens for
    the few files that hit, and the text read is memoized across tests."""
    return [p for p, text in _shipped_texts() if needle in text]


def _all_assignments(tree: ast.Module) -> list[tuple[str, ast.expr]]:
    """Every ``NAME = value`` assignment in the tree, module-level OR
    FUNCTION-LOCAL, in source order. Function-local is not a nicety: the
    surviving threat table lives inside ``_postprocess_threat``
    (adapters/enrichment_light.py:84), so a module-level-only reader calls the
    shipped emitter "missing" — the mirror's own failure mode."""
    out: list[tuple[str, ast.expr]] = []
    for node in ast.walk(tree):
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
        for t in targets:
            if isinstance(t, ast.Name):
                out.append((t.id, node.value))
    return out


def _module_assignments(tree: ast.Module) -> dict[str, ast.expr]:
    """Module-level assignments only — for the dimension-constant registry,
    where a function-local counter would be a different claim."""
    found: dict[str, ast.expr] = {}
    for node in tree.body:
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
        for t in targets:
            if isinstance(t, ast.Name):
                found[t.id] = node.value
    return found


def _named_constants(
    tree_dir: str | None, needle: str, *, module_level_only: bool = False
) -> list[tuple[str, str, Any]]:
    """[(file, name, literal value)] for every shipped constant whose NAME
    contains ``needle`` — DERIVED, never hand-listed (WP4.2: hand-listed
    subjects rot; derived sets do not). Duplicated names across files are all
    kept: two files carrying the same constant name at different values is
    exactly the drift this module hunts, so collapsing them by name would hide
    it. ``tree_dir`` narrows the scan for the dimension registry."""
    root = REPO_ROOT / tree_dir if tree_dir else None
    out: list[tuple[str, str, Any]] = []
    for path in _files_mentioning(needle):
        if root is not None and root not in path.parents:
            continue
        tree = _parsed(path)
        items: list[tuple[str, ast.expr]] = (
            list(_module_assignments(tree).items()) if module_level_only else _all_assignments(tree)
        )
        for name, value in items:
            if needle not in name:
                continue
            try:
                out.append((str(path.relative_to(REPO_ROOT)), name, ast.literal_eval(value)))
            except ValueError:
                continue  # computed value, not a literal alphabet
    return out


def _threat_name_tables() -> list[tuple[str, Any]]:
    """Every shipped ``*THREAT_CLASSES*`` constant that is a NAME TABLE
    (list/dict — the shape a post-processor indexes to produce an emitted
    string), as [(file, value)]. A brace-SET under the same needle is NOT an
    emitter: it is a synonym recognizer matched against names someone else
    produced, and confusing the two would make the single-emitter claim either
    false (today's seed-events recognizer) or accidentally true."""
    return [
        (path, value)
        for path, _name, value in _named_constants(None, "THREAT_CLASSES")
        if isinstance(value, (list, dict))
    ]


def _threat_recognizers() -> list[str]:
    """Names of the shipped ``*THREAT_CLASSES*`` constants that are SETS —
    recognizers, not emitters (pinned as data, never silently dropped)."""
    return sorted(
        {
            name
            for _p, name, value in _named_constants(None, "THREAT_CLASSES")
            if isinstance(value, (frozenset, set))
        }
    )


def _ast_assign(path: Path, name: str) -> Any:
    """literal_eval the assignment of `name` anywhere in `path`, module level
    first, then function-local — which is where the surviving adapter keeps its
    table (adapters/enrichment_light.py:84, inside ``_postprocess_threat``), so
    a module-level-only reader would call the surviving emitter "missing"
    (the old module's own vacuity failure mode, inverted)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
        for t in targets:
            if isinstance(t, ast.Name) and t.id == name:
                return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found as a literal in {path}")


def _ast_fstring_template(path: Path, name: str) -> str:
    """The TEMPLATE of an ``f"{prefix}{var}"`` fallback whose literal prefix is
    ``name`` — e.g. ``f"threat_{cls_id}"`` -> ``"threat_{}"``. Read, not
    typed: the fallback spelling is what reaches the wire for an out-of-range
    class id, so it is part of the emitted vocabulary."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.JoinedStr)):
            continue
        first = node.values[0] if node.values else None
        if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
            continue
        if not first.value.startswith(name):
            continue
        if any(isinstance(v, ast.FormattedValue) for v in node.values[1:]):
            return first.value + "{}"
    raise AssertionError(f"no f-string fallback starting with {name!r} in {path}")


def _ast_return_literals(path: Path, func: str) -> frozenset[str]:
    """All string literals appearing in `return` statements of `func` —
    literals only (a dict-indexed return is NOT captured). Captures tuple and
    ternary returns."""

    def parts(n: ast.AST) -> list[str]:
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            return [n.value]
        if isinstance(n, ast.Tuple):
            return [x for e in n.elts for x in parts(e)]
        if isinstance(n, ast.IfExp):
            return parts(n.body) + parts(n.orelse)
        return []

    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func:
            return frozenset(
                x
                for r in ast.walk(node)
                if isinstance(r, ast.Return) and r.value is not None
                for x in parts(r.value)
            )
    raise AssertionError(f"function {func} not found in {path}")


def _check_sql(model: Any, name: str) -> str:
    """The SQL text of an ORM CheckConstraint, by name."""
    for c in model.__table__.constraints:
        if getattr(c, "name", None) == name:
            return str(c.sqltext)
    raise AssertionError(f"{name} not found on {model.__name__}")


def _check_values(model: Any, name: str) -> frozenset[str]:
    """Values from a `col IN ('a','b',...)` CHECK, parsed off the ORM
    constraint text — the DB spec as a set, no live connection needed. Every
    surviving CHECK in this model is `IS NULL OR col IN (...)`, which this
    parse handles unchanged."""
    sql = _check_sql(model, name)
    start = sql.index("IN (") + 4
    end = sql.index(")", start)  # values contain no parens
    return frozenset(ast.literal_eval(f"({sql[start:end]})"))


# ---------------------------------------------------------------------------
# DB spec (read from the ORM CheckConstraints — backend/models/enrichment.py)
# ---------------------------------------------------------------------------

DB_POSE = _check_values(PoseResult, "ck_pose_results_pose_class")
DB_THREAT = _check_values(ThreatDetection, "ck_threat_detections_threat_type")
DB_SEVERITY = _check_values(ThreatDetection, "ck_threat_detections_severity")
# DB_GENDER / DB_AGE were derived here off ``DemographicsResult``'s two CHECKs.
# R8 S4 (owner ruling 2026-09-30) dropped the ``demographics_results`` table
# along with that class, so the two derived sets are gone and the two hazards
# they mirrored are now TOMBSTONED in TestRetiredEmitterTombstones below (their
# emitters had already gone in S3; the CHECKs were the last live half, and this
# module is the last reader they had).

# ---------------------------------------------------------------------------
# Surviving server emitters (all AST-read, none transcribed)
# ---------------------------------------------------------------------------

LIGHT_ADAPTER = REPO_ROOT / "ai/gateway/adapters/enrichment_light.py"
YOLO26_ADAPTER = REPO_ROOT / "ai/gateway/adapters/yolo26.py"
YOLO26_POSE = REPO_ROOT / "ai/yolo26/pose_estimation.py"

# THE surviving threat vocabulary: ["knife", "pistol", "rifle", "threat_object"]
LIGHT_THREAT_TABLE = _ast_assign(LIGHT_ADAPTER, "THREAT_CLASSES")
LIGHT_THREAT_EMITTED = frozenset(LIGHT_THREAT_TABLE)
# Its out-of-range fallback template, read off the adapter's own f-string.
LIGHT_THREAT_FALLBACK = _ast_fstring_template(LIGHT_ADAPTER, "threat_")
# The class-id -> name table of the OTHER surviving adapter, whose fallback is
# `f"class_{cls_id}"` and whose names land in detections.object_type.
YOLO26_CLASSES = _ast_assign(YOLO26_ADAPTER, "COCO_CLASSES")
YOLO26_CLASS_FALLBACK = _ast_fstring_template(YOLO26_ADAPTER, "class_")
# The surviving pose classifier's emitted alphabet.
YOLO26_POSE_RETURNS = _ast_return_literals(YOLO26_POSE, "classify_pose")

# Emitted threat names, INCLUDING the fallback shape (the CHECK refuses a
# generated name exactly as hard as a table name).
THREAT_EMITTED_WITH_FALLBACK = LIGHT_THREAT_EMITTED | {LIGHT_THREAT_FALLBACK.format(99)}


# ===========================================================================
# 1. STATIC MIRROR (plan bullet 1) — the surviving emitters vs their DB
#    CHECK, with the illegal delta pinned AS DATA. These are the shipped-behavior
#    characterizations; each names the parked WP8.5-vocab-alignment ruling and
#    reddens the day the delta moves (that is the tripwire).
# ===========================================================================


class TestStaticSubset:
    def test_db_checks_parse_as_expected(self) -> None:
        """Spec sanity (GREEN): the CHECK texts parse to the legal sets this
        module mirrors against. Three alphabets remain: the two the plan named
        that survive (POSE, THREAT) are pinned as captured live at
        88215286..a8c25c5e (Postgres 16.15 pg_constraint); the SEVERITY row is
        DERIVED off the ORM today rather than remembered, because after R8 S3 it
        is the only threat-side CHECK with a surviving parity copy to mirror.

        R8 S4 took the GENDER and AGE rows with the ``demographics_results``
        table, and they are NOT re-derivable from anything else — the CHECK
        object no longer exists, so a remembered copy of its value set here
        would be a transcription (the failure mode this module's whole "read it
        out of shipped source" discipline exists to prevent). The retired hazards
        those two alphabets carried are recorded in
        TestRetiredEmitterTombstones instead."""
        assert (
            frozenset(
                {
                    "standing",
                    "crouching",
                    "bending_over",
                    "arms_raised",
                    "sitting",
                    "lying_down",
                    "unknown",
                }
            )
            == DB_POSE
        )
        assert frozenset({"gun", "knife", "grenade", "explosive", "weapon", "other"}) == DB_THREAT
        assert frozenset({"critical", "high", "medium", "low"}) == DB_SEVERITY
        # Non-vacuity for the parser itself: a parse that silently returned an
        # empty set would keep every subset assertion below green.
        for name, values in (
            ("DB_POSE", DB_POSE),
            ("DB_THREAT", DB_THREAT),
            ("DB_SEVERITY", DB_SEVERITY),
        ):
            assert len(values) >= 3, f"{name} parsed to {sorted(values)}"

    def test_threat_registries_are_derived_and_single(self) -> None:
        """The premise under every threat-side assertion here: how many
        shipped threat tables exist, derived — not remembered from the two
        twins this module used to compare. R8 S3 collapsed the pair (heavy
        server + light twin) to ONE EMITTER table, and the derived scan is what
        says so; a second alphabet appearing anywhere in shipped code reddens
        this and forces the twins-equality back into existence.

        The scan separates two artifacts it finds by the same needle, because
        only one of them EMITS a name onto the wire: a list/dict NAME TABLE
        (positional or keyed — the shape a post-processor indexes) versus a
        brace-SET of synonyms (a recognizer, matched against names someone else
        produced). The recognizer is pinned as DATA rather than quietly
        filtered out: if it ever becomes a table, the cardinality reddens."""
        locations = _threat_name_tables()
        recognizers = _threat_recognizers()
        assert len(locations) == 1, (
            f"shipped threat NAME TABLES: {[f for f, _v in locations]} — the "
            "module mirrored TWO twins before S3 deleted them; a second live "
            "table means the single-source claim below is stale and the twins "
            "equality must come back (a drifting duplicate is precisely the "
            "hazard WP8.5 is about)"
        )
        path, table = locations[0]
        assert path.endswith("ai/gateway/adapters/enrichment_light.py"), (
            f"the surviving threat registry moved to {path}; re-point the "
            "mirror (the emitted vocabulary and the CHECK are the same pair "
            "of facts no matter which module holds the table)"
        )
        assert frozenset(table) == LIGHT_THREAT_EMITTED, (
            f"the mirror reads {sorted(LIGHT_THREAT_EMITTED)} but the scan "
            f"finds {sorted(table)} — two readers of one table disagreeing is "
            "the drift class this file exists to catch"
        )
        assert recognizers, (
            f"no threat synonym set found anywhere "
            f"({sorted(_named_constants(None, 'THREAT_CLASSES'))}) — the "
            "table/recognizer split below is unexercised; re-derive it"
        )

    def test_threat_emitter_delta_vs_db_check(self) -> None:
        """WP8.5 discovery red — RULING parked (L1036), RETARGETED to the
        surviving emitter (R8 S3): the gateway adapter's 4-class threat table
        (ai/gateway/adapters/enrichment_light.py:84) vs
        ck_threat_detections_threat_type (backend/models/enrichment.py:139-142).
        THREE of the four names are illegal: ``pistol``, ``rifle`` and
        ``threat_object``. Only ``knife`` is legal.

        The adapter is the shipped producer of the threat stream — POST
        /enrich-lt/threat-detect runs the ``threat`` Triton model and names its
        detections from exactly this table — so every non-knife threat that
        ever reaches a ``threat_detections`` row violates the CHECK at INSERT.
        That is the plan's "enforced too late, nowhere in unit tests" finding
        restated on the lane that survived, and it is WORSE than the retired
        server's version: the retired maps at least named weapons the CHECK
        had a chance of matching.

        LANDED AS CHARACTERIZATION (goal rule): pins the exact illegal delta.
        RULING `WP8.5-vocab-alignment` parked — widen the CHECK or normalize
        at the client boundary. When either lands this equality reddens and
        this docstring tells the next reader why that is expected.
        """
        assert (
            frozenset({"pistol", "rifle", "threat_object"}) == LIGHT_THREAT_EMITTED - DB_THREAT
        ), (
            f"adapter THREAT_CLASSES delta vs the CHECK moved to "
            f"{sorted(LIGHT_THREAT_EMITTED - DB_THREAT)} — the "
            "WP8.5-vocab-alignment ruling landed; rewrite to the new shape"
        )
        assert frozenset({"knife"}) == LIGHT_THREAT_EMITTED & DB_THREAT, (
            "exactly one name in the shipped threat vocabulary is storable; "
            f"now {sorted(LIGHT_THREAT_EMITTED & DB_THREAT)}"
        )

    def test_threat_fallback_spellings_reach_the_wire(self) -> None:
        """The emitted vocabulary is the table PLUS its out-of-range fallback,
        and the fallback is assertable only by EXECUTION — the CHECK cannot see
        a name that is generated at post-processing time. Driven for real: a
        threat tensor whose argmax class ids are ``[0, 5, 7]`` against the
        shipped ``_postprocess_threat`` yields ``knife`` from the table and
        ``threat_5`` / ``threat_7`` from ``f"threat_{cls_id}"``
        (adapters/enrichment_light.py:108).

        Both generated names are illegal, and neither is a WEAPON NAME A
        HUMAN WOULD WRITE — so the alert-side consequence is not a rejected
        row but an unnamed object: the fallback swallows every class id past
        the table's end into an anonymous ``threat_N`` that the DB refuses and
        the severity map (backend/services/threat_monitor_service.py
        THREAT_SEVERITY_MAPPING — keyed gun/pistol/rifle/knife/…) has never
        heard of. The template is AST-read from the adapter, so renaming the
        fallback reddens here rather than in a rejected INSERT."""
        assert LIGHT_THREAT_FALLBACK == "threat_{}", (
            f"the adapter's out-of-range fallback template now reads "
            f"{LIGHT_THREAT_FALLBACK!r} — re-point the emitted-name assertions "
            "below at whatever a runaway class id becomes"
        )
        assert LIGHT_THREAT_FALLBACK.format(99) not in DB_THREAT, (
            "the generated fallback name became CHECK-legal — an anonymous "
            "threat class would start being STORABLE, which is how a "
            "post-processing index bug turns into silently wrong alerts"
        )

        import asyncio
        from unittest.mock import patch

        import ai.gateway.adapters.enrichment_light as el
        import numpy as np
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient
        from PIL import Image

        # (1, 4 + n_classes, n_candidates): the orientation the adapter's own
        # transpose guard normalizes at :87-88. Class ids 5 and 7 exist only
        # because the tensor carries 8 score rows while the table has 4 names.
        tensor = np.zeros((1, 12, 17), dtype=np.float32)
        for i, cls_id in enumerate((0, 5, 7)):
            tensor[0, 0:4, i] = (320.0, 240.0, 60.0, 120.0)
            tensor[0, 4 + cls_id, i] = 0.9 - 0.05 * i

        buf = io.BytesIO()
        Image.new("RGB", (64, 64), color=(9, 9, 9)).save(buf, format="PNG")
        payload = {"image": base64.b64encode(buf.getvalue()).decode()}

        app = FastAPI()
        app.include_router(el.router, prefix="/enrich-lt")
        triton = AsyncMock()

        # model_name is explicit: the adapter calls infer(model_name="threat")
        # and an unnamed stub would pass even if the model name changed.
        def _infer(inputs=None, model_name="", **_kw):
            assert model_name == "threat", f"adapter asked Triton for {model_name!r}"
            return {"output0": tensor}

        triton.infer = AsyncMock(side_effect=_infer)

        async def drive() -> list[str]:
            with patch(
                "ai.gateway.adapters.enrichment_light.get_triton_client", return_value=triton
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://t"
                ) as client:
                    r = await client.post("/enrich-lt/threat-detect", json=payload)
            assert r.status_code == 200, r.text[:200]
            return [d["class"] for d in r.json()["threats_detected"]]

        emitted = asyncio.run(drive())
        assert emitted == ["knife", "threat_5", "threat_7"], (
            f"the wire emitted {emitted}; the shipped post-processor's name "
            "source or its fallback moved, and this file's mirror of it is "
            "now a description of a wire that does not exist"
        )
        assert set(emitted) - DB_THREAT == {"threat_5", "threat_7"}, (
            "the two generated names are the illegal half of what this request "
            "just emitted — 2 of 3 detections on one healthy call"
        )

    def test_yolo26_pose_classifier_delta_vs_db_check(self) -> None:
        """WP8.5 discovery red — RULING parked (F1): RETARGETED onto the only
        pose classifier left in the tree. ai/yolo26/pose_estimation.py:502
        ``classify_pose`` (called by its own pipeline at :800, exported at :950)
        emits ``fallen``, ``reaching_up`` and ``aggressive`` — all rejected by
        ck_pose_results_pose_class; ``aggressive`` additionally collides
        semantically with the DB's ``arms_raised`` slot, so the two alphabets
        are not even disjoint-by-accident.

        LANDED AS CHARACTERIZATION (goal rule; RULING `WP8.5-vocab-alignment`
        parked): pins the exact illegal return set as shipped."""
        assert (
            frozenset({"fallen", "reaching_up", "aggressive"}) == YOLO26_POSE_RETURNS - DB_POSE
        ), (
            f"yolo26 classify_pose delta moved to {sorted(YOLO26_POSE_RETURNS - DB_POSE)} — "
            "the WP8.5-vocab-alignment ruling landed; rewrite to the new shape"
        )
        # Non-vacuity in the same test: the classifier also emits legal names,
        # so the delta is a partial-overlap hazard, not a wholesale mismatch.
        assert {"standing", "crouching", "lying_down"} <= YOLO26_POSE_RETURNS & DB_POSE, (
            f"legal overlap is {sorted(YOLO26_POSE_RETURNS & DB_POSE)} — if the "
            "classifier stopped emitting legal classes too, every pose row "
            "would be illegal and the finding changes shape entirely"
        )


# ===========================================================================
# 2. CHARACTERIZATION (GREEN pins of today's behaviour — the plan's
#    "Pin today's behaviour" bullet; remediation stays RULING-blocked).
# ===========================================================================


class TestCharacterization:
    def test_legal_but_unproduced_threats(self) -> None:
        """Four of the six CHECK-legal threat types are produced by NOTHING in
        the surviving vocabulary (derived: DB minus the adapter's table minus
        its fallback shape). Before S3 this bullet read "grenade + explosive +
        other"; the prune made the gap much larger, and the derived subtraction
        is what noticed without anyone editing a literal."""
        unproduced = DB_THREAT - THREAT_EMITTED_WITH_FALLBACK
        assert unproduced == frozenset({"gun", "explosive", "grenade", "other", "weapon"}), (
            f"legal-but-unproduced threats moved to {sorted(unproduced)} — the "
            "gap between what the schema allows and what the shipped producer "
            "can name is the whole WP8.5 vocab finding, so it is pinned as data"
        )
        assert "knife" in LIGHT_THREAT_EMITTED, (
            "the one storable threat name disappeared from the emitter; the "
            "unproduced set above would then be the whole CHECK and the "
            "threat stream could never persist"
        )

    def test_alert_side_vocabularies_match_the_checks(self) -> None:
        """backend/api/schemas/alerts.py carries hand-maintained PARITY COPIES
        of three DB sets, and they are the LIVE enforcement point — the
        AlertRuleCreate / AlertRuleUpdate validators at :405-440 reject a rule
        naming anything else, which means the API refuses a threat type the DB
        would accept and vice versa. Pin all three against the ORM: the second
        enforcement point must not drift. (The retired copies covered two sets;
        the severity copy is pinned too because S3 left it as the only threat
        vocabulary with a live validator behind it.)"""
        from backend.api.schemas import alerts

        assert alerts.VALID_POSE_CLASSES == DB_POSE
        assert alerts.VALID_THREAT_TYPES == DB_THREAT
        assert alerts.VALID_THREAT_SEVERITIES == DB_SEVERITY
        # Non-vacuity: these are not decorative constants — the alert engine
        # filters the threat stream by the rule's threat_types, so a parity
        # copy that drifted changes WHICH rows alert, silently.
        engine = (REPO_ROOT / "backend/services/alert_engine.py").read_text(encoding="utf-8")
        assert "if threat.threat_type not in rule.threat_types:" in engine, (
            "alert_engine stopped filtering on threat_type — the parity copy "
            "would no longer be an enforcement point and this pin would be "
            "comparing two inert lists"
        )

    def test_detection_class_vocabulary_is_unconstrained_at_the_db(self) -> None:
        """The OTHER surviving emitter's mirror, and the one with no CHECK to
        mirror against: the gateway yolo26 adapter names every detection from
        its 80-name ``COCO_CLASSES`` table with an ``f"class_{cls_id}"``
        fallback (:186, :311), ``detector_client`` copies that string into
        ``detections.object_type``, and the column is an unconstrained String —
        so this vocabulary has NO DB-side spec at all. The hazard is inverted
        from the threat lane (illegal values are not refused, they are
        INVISIBLE): a class-name change upstream silently re-keys every
        per-class alert rule, threshold and analytics group with nothing to
        redden. Derived lengths, both fallback templates read from source:
        an 80-name table and a generated-name family that no constraint can
        ever reject."""
        import sqlalchemy as sa

        col = Detection.__table__.c.object_type
        assert isinstance(col.type, sa.String) and col.type.length is None
        assert len(YOLO26_CLASSES) >= 80, (
            f"the adapter's class table shrank to {len(YOLO26_CLASSES)} — any "
            "name removed here silently orphans the alert rules that name it"
        )
        assert "person" in YOLO26_CLASSES and "bicycle" in YOLO26_CLASSES
        assert YOLO26_CLASS_FALLBACK == "class_{}", (
            f"the detection fallback is now {YOLO26_CLASS_FALLBACK!r}; a "
            "runaway class id reaches object_type through this template"
        )
        assert YOLO26_CLASS_FALLBACK.format(999) not in YOLO26_CLASSES, (
            "a generated fallback name would be indistinguishable from a real "
            "COCO class in object_type — no CHECK, no length, no validation"
        )
        # Non-vacuity: object_type really is written from the wire string.
        client = (REPO_ROOT / "backend/services/detector_client.py").read_text(encoding="utf-8")
        assert 'object_type=detection_data.get("class")' in client, (
            "detector_client no longer maps the adapter's class name onto "
            "object_type — the emitter->column mirror above needs re-pointing"
        )


# ===========================================================================
# 3. TOMBSTONES (R8 S3). Five of this module's six mirrored emitters were
#    deleted with their serving directories (owner rulings 4+5). Each record
#    states the hazard the retired test pinned IN FULL, proves the retired
#    source is ABSENT, and carries a NON-VACUITY assertion naming the live
#    place the same hazard class still occurs. No skips — a skip would be a
#    suppression needing a registry entry; the tier's rule is that a retired
#    property is a tombstone with assertions in it.
# ===========================================================================


class TestRetiredEmitterTombstones:
    """One class, five lost mirrors. See the module docstring for the ruling
    that swept them; the assertions below never read a dead form — they read
    LIVE files and the LIVE CHECKs, and assert the dead packages are gone."""

    def test_vitpose_posture_table_retired_with_its_service(self) -> None:
        """HAZARD IT PINNED: ``ai/enrichment/vitpose.py:44-51``
        ``POSTURE_LABELS`` = standing, walking, sitting, crouching,
        lying_down, running against ``ck_pose_results_pose_class`` —
        ``walking`` and ``running`` were ILLEGAL, and both were EXECUTED live
        against host Postgres 16.15 and RAISED a CHECK violation
        (a8c25c5e). Motion verbs are the most useful pose classes a rule
        author writes, so the mismatch was not academic: the labels a rule
        most wants are exactly the two the schema refuses. It was also DEAD
        DATA even before the sweep (the enrichment server classified poses
        through ``_classify_pose``, and grep found zero readers of the table) —
        a pinned alphabet nobody reads is the second failure mode.

        NOT RETARGETABLE: no shipped module emits a posture table (derived
        scan below), so there is no live emitter to re-point it at. The pose
        mirror's live side is the yolo26 classifier pinned above."""
        assert not (REPO_ROOT / "ai/enrichment").exists()
        assert not (REPO_ROOT / "ai/enrichment-light").exists()
        assert not _named_constants(None, "POSTURE_LABELS"), (
            "a posture label table came back — the motion-verb-vs-CHECK "
            "finding has a live emitter again and the subset assertion must "
            "be restored, not left as this record"
        )
        # Non-vacuity: the pose CHECK still refuses, and a live emitter still
        # disagrees with it (the yolo26 pin above).
        assert "walking" not in DB_POSE and "running" not in DB_POSE, (
            "the CHECK now accepts the motion verbs — the retired hazard was "
            "resolved by widening the schema, and this record should be "
            "replaced by whatever normalizes the surviving classifier's names"
        )
        assert YOLO26_POSE_RETURNS - DB_POSE, (
            "the surviving pose emitter no longer disagrees with the pose "
            "CHECK: this class would be asserting nothing has live work"
        )

    def test_enrichment_pose_estimator_classifier_retired(self) -> None:
        """HAZARD IT PINNED: the enrichment server's ACTUAL runtime pose
        classifier (``ai/enrichment/models/pose_estimator.py::_classify_pose``
        — not the plan's cited POSTURE_LABELS table) emitted
        ``crawling``, ``reaching_up`` and ``running`` outside
        ``ck_pose_results_pose_class``. This was the module's F1 finding: the
        plan named one table, and AST-extracting the classifiers actually
        reachable at runtime widened the illegal alphabet considerably.

        NOT RETARGETABLE as a second pose emitter: only one pose classifier
        ships now (the scan below derives it), and its delta is pinned live in
        TestStaticSubset — asserting the same delta twice would duplicate a
        green pin rather than record a distinct hazard."""
        assert not (REPO_ROOT / "ai/enrichment/models/pose_estimator.py").exists()
        assert not (REPO_ROOT / "ai/enrichment-light/models/pose_estimator.py").exists()
        classifiers = sorted(
            str(p.relative_to(REPO_ROOT))
            for p in _files_mentioning("def classify_pose")
            if any(
                isinstance(n, ast.FunctionDef) and n.name == "classify_pose"
                for n in ast.walk(_parsed(p))
            )
        )
        assert classifiers == ["ai/yolo26/pose_estimation.py"], (
            f"shipped classify_pose implementations: {classifiers} — a second "
            "pose classifier re-arms the F1 finding and needs its own subset "
            "assertion (crawling was the retired one's signature name)"
        )
        # Non-vacuity: the F1 method (AST-extract the reachable classifier
        # instead of trusting the cited table) still has a live subject and a
        # live delta, and `crawling` is still unnameable.
        assert "crawling" not in DB_POSE, "the CHECK gained the retired emitter's name"
        assert YOLO26_POSE == REPO_ROOT / "ai/yolo26/pose_estimation.py"
        assert YOLO26_POSE.is_file()

    def test_demographics_age_buckets_retired_with_the_service(self) -> None:
        """HAZARD IT PINNED: ``ai/enrichment/models/demographics.py:44-51``
        ``AGE_RANGES`` vs ``ck_demographics_results_age_range`` (:197-200).
        FOUR of six server buckets were illegal — ``21-35``, ``36-50``,
        ``51-65``, ``65+`` — because the DB sliced decades (21-30/31-40/…)
        while the model sliced its own boundaries, and only ``0-10`` /
        ``11-20`` overlapped. All four RAISED live (a8c25c5e). The class of bug
        is the nastiest kind here: both sides are *plausible age buckets*, so
        nothing looks wrong until an INSERT refuses a demographic row for
        every adult over 20.

        RETIRED IN TWO STEPS, and both halves are asserted. S3 deleted the
        emitter; R8 S4 (owner ruling 2026-09-30) dropped ``demographics_results``
        and with it the CHECK — the hazard's other half. This is now the full
        closure record: no shipped module emits an age vocabulary (derived scan)
        and nothing shipped can store one. The non-vacuity this record used to
        carry was ``scripts/seed-events.py``'s own ``age_ranges`` literal
        measured against the live CHECK; that writer left in the same S4 commit,
        so the leg is RETARGETED rather than dropped (dropping it is how a
        tombstone becomes a comment).

        NOT RETARGETABLE as a live subset: nothing shipped holds an age bucket to
        compare against. The hazard CLASS — two plausible vocabularies for one
        concept, only one of them storable — is pinned live and asserted one
        emitter over, on a DIFFERENT concept than the vitpose record beside it:
        the light adapter's threat table emits ``pistol``/``rifle``/
        ``threat_object``, none of which ``ck_threat_detections_threat_type``
        accepts, and that delta is DATA in TestStaticSubset."""
        assert not (REPO_ROOT / "ai/enrichment/models/demographics.py").exists()
        assert not _named_constants(None, "AGE_RANGES"), (
            "a shipped age-range table came back — the bucket-boundary mismatch "
            "has a live emitter again; if a column to store it in came back too, "
            "restore the subset assertion instead of editing this record"
        )
        # The storage side went with the table: no shipped constant named
        # *age_range* survives, so the mismatch cannot silently return as a live
        # INSERT risk. Same derived-scan discipline as the emitter scan above.
        stale_age = [(rel, name) for rel, name, _ in _named_constants(None, "age_range")]
        assert not stale_age, (
            f"a shipped age_range alphabet is back: {stale_age} — decide whether "
            "the column it targets is live, then re-derive the CHECK it must "
            "satisfy rather than widening this tombstone"
        )
        # Non-vacuity: the same hazard class has a live, asserted instance, so
        # this record sits beside real work rather than standing in for it.
        assert LIGHT_THREAT_EMITTED - DB_THREAT, (
            "the surviving threat emitter no longer disagrees with its CHECK — "
            "the two-plausible-vocabularies class would have no live pin, and a "
            "tombstone would be the only thing left claiming it exists"
        )

    def test_demographics_gender_ordering_retired(self) -> None:
        """HAZARD IT PINNED: ``GENDER_LABELS = ['female', 'male']`` at
        demographics.py:54, consumed POSITIONALLY (``GENDER_LABELS[:num_labels]``,
        the HF id2label convention). Reordering the list INVERTS every
        prediction while remaining fully schema-valid — both orders are
        subsets of ``ck_demographics_results_gender``, so the CHECK was blind to
        the only thing that mattered. That made it the module's purest
        "storable and wrong" pin: no constraint can express a class INDEX.

        R8 S4 CLOSED IT: the CHECK went with the table, so the ordering hazard
        lost even its nominal guard (the label list went first, in S3). The
        earlier non-vacuity here — ``scripts/seed-events.py``'s ``genders``
        literal against that CHECK — is retargeted onto the positional shape
        itself, since the writer left in the same S4 commit.

        NOT RETARGETABLE: no shipped module emits a gender label list (derived
        scan), so there is no positional convention left to pin. The hazard
        CLASS survives as a live, asserted shape one emitter over — the threat
        adapter's ``np.argmax`` class id indexes ``THREAT_CLASSES`` the same
        positional way, and its delta is pinned in TestStaticSubset."""
        assert not (REPO_ROOT / "ai/enrichment/models/demographics.py").exists()
        assert not _named_constants(None, "GENDER_LABELS"), (
            "a shipped gender-label list came back — positional class ids are "
            "back and the ordering pin must be restored (it is the one hazard "
            "no CHECK in this schema can express)"
        )
        # Non-vacuity 1: the class this pin exemplified is still expressed as
        # ORDERED literals somewhere shipped, so "no CHECK can see an index" is
        # not a claim about a corner of the tree that no longer exists.
        ordered = [
            (rel, name)
            for rel, name, value in _named_constants(None, "CLASSES")
            if isinstance(value, list)
        ]
        assert ordered, (
            "no shipped ordered class-name table left — the positional-index "
            "hazard class has no live instance for this record to sit beside"
        )
        # Non-vacuity 2: the live positional emitter is the one the docstring
        # names, and order still decides what it emits (an argmax reads it).
        assert isinstance(LIGHT_THREAT_TABLE, list), (
            "the light adapter's threat table is no longer a positional list — "
            "check whether its argmax still indexes it before retiring this pin"
        )
        assert {"male", "female"} == {"female", "male"}, (
            "set equality is what a CHECK expresses — the reason an ORDERED "
            "alphabet can violate nothing while inverting every row"
        )

    def test_threat_twin_maps_and_their_twelve_name_map_retired(self) -> None:
        """HAZARD THEY PINNED (three records, one sweep):
          * ``THREAT_CLASSES_BY_NAME`` (ai/enrichment/models/threat_detector.py
            :76-88, 12 names) vs the threat CHECK — NINE of twelve rejected:
            rifle, pistol, firearm, bat, crowbar, hammer, sword, machete, axe;
            ``rifle`` and ``hammer`` EXECUTED live (a8c25c5e).
          * the int-keyed COCO-style ``THREAT_CLASSES`` beside it (:66-73) — a
            DIFFERENT 6-value vocabulary the plan conflated with BY_NAME; four
            of six rejected (rifle, pistol, bat, crowbar).
          * the twins' EQUALITY (``ai/enrichment`` vs ``ai/enrichment-light``
            carried byte-identical tables around machinery that otherwise
            differed) — drift between two copies of one alphabet is itself a
            WP8.5 finding.

        NOT RETARGETABLE: those maps are gone and the surviving emitter has ONE
        table, whose legality the live pins above already grade. The twins
        equality is NOT kept as a tautology over literals transcribed into this
        file (that would assert only the test); it is kept as the DERIVED
        cardinality pin in TestStaticSubset.test_threat_registries_are_derived_and_single,
        which reddens the moment a second shipped table exists."""
        assert not (REPO_ROOT / "ai/enrichment/models/threat_detector.py").exists()
        assert not (REPO_ROOT / "ai/enrichment-light/models/threat_detector.py").exists()
        assert len(_threat_name_tables()) == 1, (
            f"threat name tables back to {[f for f, _v in _threat_name_tables()]} "
            "— the twin-copy hazard is live again and needs its equality, not "
            "this record"
        )
        assert "THREAT_CLASSES_BY_NAME" not in sorted(
            name for _p, name, _v in _named_constants(None, "THREAT_CLASSES")
        ), (
            "a 12-name BY_NAME map came back — the 9-of-12-rejected finding "
            "has a live emitter again and needs its subset assertion"
        )
        # Non-vacuity: the retired maps' sharpest names are STILL unnameable to
        # the schema, and the surviving emitter names both of them — so the
        # 9-of-12 hazard this record describes is not historical, it just
        # changed address from a 12-name map to a 4-name table.
        assert {"rifle", "pistol"} & DB_THREAT == frozenset(), (
            f"the CHECK now accepts rifle/pistol: {sorted(DB_THREAT)} — the "
            "retired hazard was resolved by widening the schema and this "
            "record should be replaced by whatever normalizes names now"
        )
        assert {"rifle", "pistol"} <= LIGHT_THREAT_EMITTED, (
            "the surviving adapter stopped emitting the retired maps' worst "
            "names — the retargeted delta pin's premise changed"
        )
        # The retired severity vocabulary still has a live enforcement point, so
        # the threat-side CHECK family is not an orphan either.
        from backend.api.schemas import alerts

        assert alerts.VALID_THREAT_SEVERITIES == DB_SEVERITY


# ===========================================================================
# 4. MISSING INVARIANTS (plan bullet 3: embedding dimensionality + unit norm,
#    risk_score integrality — the bullet's is_minor membership leg was the
#    section deleted at R8 S2).
#    The first unit-norm assertion anywhere is N1a in
#    backend/tests/contracts/ai_providers/test_conformance_numeric.py (WP8.3
#    N1b: zero unit-norm asserts existed before it). This is the BACKEND-side
#    companion, and after R8 S3 it is the backend-side companion to the
#    /enrich-lt lane as well.
# ===========================================================================


def _l2_norm(v: list[float]) -> float:
    return sum(x * x for x in v) ** 0.5


class TestMissingInvariants:
    def test_embedding_dim_registry_is_one_512_space(self) -> None:
        """MISSING invariant, RETARGETED (R8 S3): this pin used to read
        ``EMBEDDING_DIMENSION == 768`` at TWO backend service definitions and
        cross-check the scene_baseline gate that enforced it. All three
        subjects are gone — CLIP's 768-d space retired with the model (owner
        ruling 5) and ``scene_baseline.py`` was swept with it.

        The surviving registry is derived from source rather than imported
        (``backend/services/reid_service.py`` costs ~2.3s to import and nothing
        else here needs it): every module-level ``*EMBEDDING_DIM*`` constant in
        backend/services, read by AST, kept keyed BY FILE (two files carrying
        the same constant name at different values is the drift to hunt, so a
        name-keyed dict would hide it). All four are 512 — reid_service,
        osnet_loader, reid_matcher's (still-dead) default, face_recognizer_
        loader — so the backend now speaks ONE embedding space, which is the
        precondition the retired 768/512 pair could never state. The 768 half
        is pinned as ABSENT from the runtime and PRESENT only in the uncalled
        export scripts, which is where a stale CLIP-era width hides."""
        runtime = _named_constants("backend/services", "EMBEDDING_DIM", module_level_only=True)
        assert len(runtime) >= 4, (
            f"embedding-dim constants in the runtime: {runtime} — the 512 "
            "single-space claim needs its constants to exist to be derived "
            "from (this replaces the two hand-cited 768 imports)"
        )
        assert all(value == 512 for _f, _n, value in runtime), (
            f"a backend embedding dimension stopped being 512: {runtime} — "
            "two live spaces means the dim-confusion hazard (numeric cluster "
            "N5) has a second slot to collide again"
        )
        assert ("backend/services/reid_service.py", "EMBEDDING_DIMENSION", 512) in runtime, (
            "reid_service.EMBEDDING_DIMENSION — the re-ID lane's declared "
            f"space — is not the 512 the registry claims: {[r for r in runtime if 'reid_service' in r[0]]}"
        )
        # The 768-era constants are gone from everything that serves, and
        # survive only in the offline export scripts (non-vacuity: the same
        # scan CAN see a 768 at all, so the runtime absence is not a blind
        # spot of the reader).
        exports = _named_constants("ai/gateway/export", "EMBEDDING_DIM", module_level_only=True)
        assert any(value == 768 for _f, _n, value in exports), (
            f"no 768 constant left anywhere, even offline ({exports}) — the "
            "768-absence assertion above would be vacuous; re-cite what still "
            "carries a CLIP-era width"
        )
        assert not any(value == 768 for _f, _n, value in runtime)

    @pytest.mark.asyncio
    async def test_backend_unit_norm_normalizer_is_the_face_loader(self) -> None:
        """GREEN invariant, RETARGETED (R8 S3). This was scene_baseline's
        unit-norm assertion — executed through the real code path with a mocked
        Redis, proving the only backend-side normalizer on the baseline path
        emitted a unit vector. Both the service and its 768-d gate are swept;
        the normalizer that survived is
        ``face_recognizer_loader.extract_face_embedding``, reached from live
        routes (backend/api/routes/face_recognition.py) and live specialists
        (vlm_specialists), and it is a strictly STRONGER subject: it raises on
        a wrong dimension and raises on the zero vector instead of dividing
        through an epsilon.

        Executed with a fake inference session, so the three shipped
        behaviours are graded rather than described: a non-unit 512-vector
        comes out unit-normalized; a 768-d vector RAISES (the retired 768 space
        is now a refusal, not a second default); the zero vector RAISES."""
        from backend.services import face_recognizer_loader as frl

        class FakeSession:
            def __init__(self, vector: list[float]) -> None:
                self._vector = vector

            def run(self, _outputs: Any, _feed: Any) -> list[Any]:
                import numpy as np

                return [np.array([self._vector], dtype=np.float32)]

        from PIL import Image

        crop = Image.new("RGB", (64, 64), color=(7, 7, 7))
        assert frl.FACE_EMBEDDING_DIM == 512

        raw = [3.0] + [4.0] * 511  # norm sqrt(8185) = 90.47..., non-unit by design
        norm = _l2_norm(raw)
        assert norm > 90.0
        out = frl.extract_face_embedding(FakeSession(raw), crop)
        assert len(out) == 512
        assert _l2_norm(out) == pytest.approx(1.0, abs=1e-5)
        # The arithmetic proof, not just the length: each component divided by
        # THIS vector's own norm (float32 in the loader, so 1e-6 is the honest
        # tolerance — the same reason N1a's budget is 1e-5, not 1e-9).
        assert out[0] == pytest.approx(3.0 / norm, abs=1e-6)
        assert out[1] == pytest.approx(4.0 / norm, abs=1e-6)
        # The retired CLIP width is now a hard refusal, and so is the zero
        # vector (no epsilon passthrough, unlike the adapter-side guards).
        with pytest.raises(frl.FaceRecognizerError, match="512"):
            frl.extract_face_embedding(FakeSession([1.0] * 768), crop)
        with pytest.raises(frl.FaceRecognizerError, match="zero vector"):
            frl.extract_face_embedding(FakeSession([0.0] * 512), crop)

    def test_entities_embedding_vector_unconstrained(self) -> None:
        """MISSING invariant characterization (plan: 'no enforcement
        anywhere'): entities.embedding_vector is free JSONB with NO CHECK,
        and the ORM helper accepts any dimension — including a 512 vector
        tagged ``dimension=768``, with no validation error (probe-verified).

        R8 S3 note (diagnosed, not assumed): the invariant is untouched — the
        prune removed the OTHER space, which makes the silent mislabel worse,
        not moot, because a stale 768 tag is now the only way to be wrong and
        still store. The provenance gate the full swap added (``model`` is
        REQUIRED — the retired default was the literal "clip") is pinned
        alongside it, so the helper's one remaining check is on the record."""
        import sqlalchemy as sa

        col = Entity.__table__.c.embedding_vector
        assert isinstance(col.type, sa.dialects.postgresql.JSONB)
        checks = [
            getattr(c, "name", "")
            for c in Entity.__table__.constraints
            if "ck_" in str(getattr(c, "name", ""))
        ]
        assert not any("embed" in str(n) for n in checks)
        e = Entity()
        e.set_embedding([0.1] * 512, model="osnet", dimension=768)  # lies, silently accepted
        assert len(e.get_embedding_vector()) == 512
        assert e.embedding_vector["dimension"] == 768
        # the one gate that IS there: provenance, not dimension
        with pytest.raises(ValueError, match="model"):
            Entity().set_embedding([0.1] * 512)

    def test_detections_object_type_unconstrained(self) -> None:
        """MISSING invariant characterization: detections.object_type is
        unconstrained String (no length) with NO CHECK — the trigram index
        (idx_detections_object_type_trgm) is only a comment here
        (detection.py:163-164; the index lives in an Alembic migration). The
        emitter side of the same column is pinned in TestCharacterization."""
        import sqlalchemy as sa

        col = Detection.__table__.c.object_type
        assert isinstance(col.type, sa.String)
        assert col.type.length is None
        checks = sorted(
            str(getattr(c, "name", ""))
            for c in Detection.__table__.constraints
            if "ck_" in str(getattr(c, "name", ""))
        )
        assert not any("object_type" in n for n in checks)
        assert (REPO_ROOT / "backend/models/detection.py").read_text().count(
            "idx_detections_object_type_trgm"
        ) == 1

    def test_risk_score_integrality_pins(self) -> None:
        """risk_score integrality (GREEN pins of today's coercions — the
        validators that make the Integer column + 0-100 CHECK reachable):
        strict schema ge/le bounds, before-mode truncation, and the raw
        path's clamp + default-to-50."""
        import pydantic

        ok = llm_schema.LLMRiskResponse(
            risk_score=75, risk_level="high", summary="s", reasoning="r"
        )
        assert ok.risk_score == 75
        for bad in (-1, 101):
            with pytest.raises(pydantic.ValidationError):
                llm_schema.LLMRiskResponse(
                    risk_score=bad, risk_level="high", summary="s", reasoning="r"
                )
        # float input truncates toward zero (int() semantics), 74.9 -> 74
        t = llm_schema.LLMRiskResponse(
            risk_score=74.9, risk_level="high", summary="s", reasoning="r"
        )
        assert t.risk_score == 74 and isinstance(t.risk_score, int)
        # raw/lenient path: clamp + infer level; None -> 50
        raw = llm_schema.LLMRawResponse(risk_score=150, risk_level="EXTREME")
        assert raw.to_validated_response().risk_score == 100
        raw2 = llm_schema.LLMRawResponse(risk_score=None, risk_level="EXTREME")
        assert raw2.to_validated_response().risk_score == 50

    def test_risk_score_integrality_db_divergence(self) -> None:
        """DB-side integrality: events.risk_score is sa.Integer (DB-enforced
        rounding, half away from zero) inside ck_events_risk_score_range
        (event.py:242-243). Characterizes the ROUNDING DIVERGENCE: pydantic
        truncates 74.9 -> 74, Postgres rounds to 75 (live probe on host
        PG 16.15: select 74.9::integer == 75; -0.5::integer == -1). Same
        float in, two legal-but-different ints out."""
        import sqlalchemy as sa

        col = Event.__table__.c.risk_score
        assert isinstance(col.type, sa.Integer)
        assert "risk_score >= 0 AND risk_score <= 100" in _check_sql(
            Event, "ck_events_risk_score_range"
        )
        # divergence as DATA (Python truncation side; PG side from the probe):
        assert int(74.9) == 74 and int(-0.5) == 0


# NOTE: roster for the serial lane, restated at R8 S3.
#
# LIVE shipped-behavior pins (the WP8.5 vocab deltas, as data):
#   test_threat_emitter_delta_vs_db_check        (pistol, rifle, threat_object)
#   test_threat_fallback_spellings_reach_the_wire (threat_5, threat_7 — executed)
#   test_yolo26_pose_classifier_delta_vs_db_check (fallen, reaching_up, aggressive)
#   test_legal_but_unproduced_threats            (gun, explosive, grenade, other, weapon)
#
# TOMBSTONED at R8 S3 (emitter deleted with its serving dir; hazard in each
# docstring, absence + non-vacuity asserted):
#   vitpose POSTURE_LABELS            (walking, running)
#   enrichment _classify_pose         (crawling, reaching_up, running)
#   demographics AGE_RANGES           (21-35, 36-50, 51-65, 65+)   [S4: +CHECK]
#   demographics GENDER_LABELS order  (positional id2label inversion, CHECK-blind)
#   threat twins + BY_NAME            (9 of 12; 4 of 6; twin drift)
#
# R8 S4 (owner ruling 2026-09-30) closed the two demographics tombstones from
# the DB side: it dropped demographics_results/reid_embeddings, so their CHECKs
# (and the DB_GENDER/DB_AGE derived sets, and seed-events.py's writer of them)
# went too. Both tombstones now assert the emitter-AND-storage side with a
# retargeted non-vacuity. pose_results/threat_detections/action_results SURVIVE
# S4, so DB_POSE/DB_THREAT/DB_SEVERITY and every pin above them are untouched.
#
# Still here from R8 S2: no is_minor section (its three spellings were
# enrichment_pipeline.py / age_classifier_loader.py members; nothing surviving
# computes is_minor from an age_range membership).
