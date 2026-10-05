# TARGET-MODULE: backend.services.reid_service
"""Campaign #40 battery AP — backend/services/reid_service.py survivor battery.

Every test is an inventory pin: each assertion was chosen against a specific
mutmut family in /home/agent/runs/c40-inventory.txt (209 survivors, 13
families).  Style follows batteries AO/AN: strict recording fakes whose
signatures mirror the real collaborator (wrong/missing args raise), call-list
spies, message EQUALITY over the full render or the raw (fmt, *%s-args)
tuple, and full-observable equality on constructed models — never an
assertion where shipped and mutant AGREE
([[assertion-pinned-where-shipped-and-mutant-agree-fake-equiv]]).

Measured this session (py3.14 / numpy, this sandbox), the kill-critical facts:
cosine PIN pair float32 = 0.8911944627761841 while a dropped
dtype=np.float32 evaluates float64 -> 0.891194426263832 and a one-side drop
-> ...3856183319, so the EXACT-equality row kills the whole 4-key dtype
family; clamp_bbox_to_image((99,99,100,100),100,100) -> the box under
min_size=1 but None under min_size=2 (and int 1 vs the float 1.0 default is
pinned with isinstance); time-gap renders 0.5s -> "0 seconds ago", 60s/90s ->
"1 minutes ago", 3540s -> "59 minutes ago", 3600s/3630s -> "1.0 hours ago",
3780s -> "1.1 hours ago" — the div-61 mutant's measured witness (the guessed
10800s was EQUAL, a fake-equiv caught at authoring).

Honesty LEDGER — PREDICTED EQUIV by per-mutant measurement this session; the
disposition sweep is the adjudicator and any prediction that turns out RED is
simply killed (c40-ledger.txt is authored FROM the sweep, never the reverse):
  * batch_cosine_similarity m27/m34/m35/m44.  np.where(None, 1.0, norms) is
    measured == norms (None coerces to an all-False mask, so the true branch
    is dead), and for a ZERO-norm row safe_norms == norms == 0 so the
    division is 0/x either way and the FINAL np.where(candidate_norms == 0,
    0.0, s) restamps 0.0 — measured [1.0, 0.0] both ways.  m35 (1.0 -> 2.0)
    divides the zero row by 2.0 — 0/2 == 0 measured identical.  m34 (mask
    == 0 -> == 1): a norm of exactly 1.0 divides by 1.0 instead of by its
    own value 1.0 — identical for every vector.
  * format_entity_match m31/m40/m49/m58 (`x = clean(raw) if raw else None`
    -> `if (raw) or True`): clean_vqa_output("") and clean(None) BOTH return
    None via its own `if not text: return None`, so guarded and unguarded
    calls agree for every falsy value; test_format_entity_match_full_lines
    pins the populated AND the falsy-attrs rows with message equality.
  * find_matching_entities m168/m171/m172 (zip strict=True -> None/False/
    dropped): batch_cosine_similarity returns len(candidates) values BY
    CONSTRUCTION and candidate_entities/candidate_embeddings are appended in
    lockstep (the dimension guard rejects mis-sized rows before append), so
    no input skews the two sequences — strictness is unobservable; every
    find row pins the complete match list, so a skew could not hide.
  * store_embedding m20 (raw_client init None -> ""): the "" state is only
    reachable for a NON-RedisClient double, where the isinstance leg rebinds
    nothing and "" is falsy exactly like None: hasattr("", "eval") False and
    "" is not None feeds the same False chain (measured truth table).  The
    wrapper states overwrite raw_client with _client anyway.
  * store_embedding m22/m23 (and -> or inside the use_atomic conjunct
    chain): for the only reachable raw-client states (None for a foreign
    double; a callable-eval object; an object WITHOUT eval) the swapped
    formulas equal shipped's False/True/False (measured truth tables).  The
    DISJUNCT members m21/m24/m25/m26 do flip those states and are killed by
    the atomic/fallback/hasattr pins.
  * generate_embedding m49 (last_exception init None -> ""): every loop
    path assigns last_exception before the exhausted tail reads it, and a
    max_retries=0 construction never enters the tail's `if last_exception:`
    differently (both falsy, same RuntimeError) — measured by the retry
    message pins below, which cover BOTH assign paths.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any
from unittest import mock
from uuid import UUID

import numpy as np
import pytest
from PIL import Image

import backend.services.reid_service as rs
from backend.core.redis import RedisClient
from backend.services import osnet_loader
from backend.services.hybrid_entity_storage import HybridEntityMatch
from backend.services.reid_service import (
    LEGACY_MODEL_ID,
    EntityEmbedding,
    EntityMatch,
    InvalidBoundingBoxError,
    ReIdentificationService,
    ReIDUnavailableError,
    batch_cosine_similarity,
    cosine_similarity,
    format_entity_match,
    format_full_reid_context,
    format_reid_context,
    format_reid_summary,
    get_reid_service,
    reset_reid_service,
)

MODEL = "osnet-ain-x1-0@osnet_ain_x1_0_msmt17@8a07e8da3894"

# Measured this session: the EXACT float32 cosine of this pair (a dropped
# dtype evaluates float64 and lands on ...426263832 instead).
V1 = [
    0.12857020276919962,
    0.49927786244011496,
    0.6014983576233575,
    0.028689008371944547,
    0.14792608457745593,
    0.9282110229603695,
    0.07042057615419683,
    0.12977394939929798,
    0.9483284532917751,
    0.6218835927963828,
]
V2 = [
    0.368993123729791,
    0.5113900218032627,
    0.6628429525167993,
    0.2753088157611293,
    0.13796807286695534,
    0.7880395945039919,
    0.6703605841024838,
    0.5123823134831604,
    0.8167364359696581,
    0.5490752688700263,
]
COS_F32 = 0.8911944627761841

# The shipped Lua body extracted VERBATIM from the source this session
# (leading newline, indentation and trailing spaces included) — the
# atomic-leg pin demands whole-string equality, which is what kills m7.
LUA = (
    "\n                local key = KEYS[1]\n"
    "                local embedding_json = ARGV[1]\n"
    "                local list_key = ARGV[2]\n"
    "                local ttl = tonumber(ARGV[3])\n"
    "\n"
    "                -- Get existing data or create empty structure\n"
    "                local data_json = redis.call('GET', key)\n"
    "                local data\n"
    "                if data_json then\n"
    "                    data = cjson.decode(data_json)\n"
    "                else\n"
    "                    data = {persons = {}, vehicles = {}}\n"
    "                end\n"
    "\n"
    "                -- Add new embedding to appropriate list\n"
    "                local embedding = cjson.decode(embedding_json)\n"
    "                table.insert(data[list_key], embedding)\n"
    "\n"
    "                -- Store with TTL\n"
    "                redis.call('SET', key, cjson.encode(data), 'EX', ttl)\n"
    "                return 1\n"
    "                "
)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


# =============================================================================
# Log recorder — swapped in for rs.logger (a module attribute every log call
# reads at call time).  Stores the RAW (method, args) so message-EQUALITY
# pins see both the f-string renders and the un-formatted %-arg tuples:
# logger.error(None) and %-arg None/drop twins die on tuple equality, and
# XX/CASE wraps die on string equality.
# =============================================================================


class Rec:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def debug(self, *args: Any) -> None:
        self.calls.append(("debug", args))

    def info(self, *args: Any) -> None:
        self.calls.append(("info", args))

    def warning(self, *args: Any) -> None:
        self.calls.append(("warning", args))

    def error(self, *args: Any) -> None:
        self.calls.append(("error", args))

    def critical(self, *args: Any) -> None:
        self.calls.append(("critical", args))

    def find(self, level: str, needle: str) -> tuple[Any, ...] | None:
        for lvl, args in self.calls:
            if lvl == level and args and isinstance(args[0], str) and needle in args[0]:
                return args
        return None

    def has(self, needle: str) -> bool:
        return any(
            args and isinstance(args[0], str) and needle in args[0] for _lvl, args in self.calls
        )


@contextmanager
def log_rec() -> Iterator[Rec]:
    rec = Rec()
    with mock.patch.object(rs, "logger", rec):
        yield rec


# =============================================================================
# Recording doubles — signatures mirror the real collaborators so dropped or
# None args surface, exactly where the real collaborator would surface them.
# =============================================================================


class Redis:
    """Key-keyed recording fake.  get() RAISES KeyError on an unseeded key
    (strict — a mutant that fetches the WRONG key dies HERE rather than
    silently like redis returning None), unless strict=False."""

    def __init__(
        self,
        gets: dict[str, Any] | None = None,
        *,
        strict: bool = True,
        raise_on: dict[str, Exception] | None = None,
    ) -> None:
        self.gets = gets or {}
        self.strict = strict
        self.raise_on = raise_on or {}
        self.calls: list[tuple[Any, ...]] = []

    async def get(self, key: str) -> Any:
        self.calls.append(("get", key))
        if key in self.raise_on:
            raise self.raise_on[key]
        if key not in self.gets:
            if self.strict:
                raise KeyError(f"unseeded get: {key}")
            return None
        return self.gets[key]

    async def set(self, key: str, value: Any, ex: int | None = None) -> None:
        self.calls.append(("set", key, value, ex))
        self.gets[key] = value


class RawEval:
    """Stands in for redis-py's underlying client: ONE async method, eval,
    recording its (script, numkeys, *keys, *args) tuple verbatim."""

    def __init__(self, *, raises: Exception | None = None) -> None:
        self.evals: list[tuple[Any, ...]] = []
        self.raises = raises

    async def eval(self, *args: Any) -> int:
        self.evals.append(args)
        if self.raises is not None:
            raise self.raises
        return 1


class RawNoEval:
    """Non-None raw client WITHOUT eval — the hasattr seam state."""

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return "RawNoEval()"


class SubRedisClient(RedisClient):
    """REAL RedisClient subclass — passes the isinstance() seam — with
    _client settable and get/set recorded as spies (fallback leg passes the
    ex= kwarg; the spy records it as received)."""

    def __init__(self, raw: Any) -> None:
        self._client = raw
        self.gets: dict[str, Any] = {}
        self.calls: list[tuple[Any, ...]] = []

    async def get(self, key: str) -> Any:
        self.calls.append(("get", key))
        return self.gets.get(key)

    async def set(self, key: str, value: Any, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("set", key, value, args, kwargs))


class Hybrid:
    """Strict recording HybridEntityStorage double — full real signatures,
    so every dropped/None kwarg at the two call sites is a TypeError."""

    def __init__(
        self,
        *,
        store_result: tuple[UUID, bool] | None = None,
        store_raises: Exception | None = None,
        find_result: list[HybridEntityMatch] | None = None,
        find_raises: Exception | None = None,
    ) -> None:
        self.store_result = store_result
        self.store_raises = store_raises
        self.find_result = find_result or []
        self.find_raises = find_raises
        self.calls: list[tuple[Any, ...]] = []

    async def store_detection_embedding(
        self,
        detection_id: int,
        entity_type: str,
        embedding: list[float],
        camera_id: str,
        timestamp: datetime,
        attributes: dict[str, Any] | None = None,
        model_id: str | None = None,
    ) -> tuple[UUID, bool]:
        self.calls.append(
            (
                "store_detection_embedding",
                {
                    "detection_id": detection_id,
                    "entity_type": entity_type,
                    "embedding": embedding,
                    "camera_id": camera_id,
                    "timestamp": timestamp,
                    "attributes": attributes,
                    "model_id": model_id,
                },
            )
        )
        if self.store_raises is not None:
            raise self.store_raises
        assert self.store_result is not None
        return self.store_result

    async def find_matches(
        self,
        embedding: list[float],
        entity_type: str,
        threshold: float = 0.85,
        exclude_detection_id: str | None = None,
        include_historical: bool = True,
        model_id: str | None = None,
    ) -> list[HybridEntityMatch]:
        self.calls.append(
            (
                "find_matches",
                {
                    "embedding": embedding,
                    "entity_type": entity_type,
                    "threshold": threshold,
                    "exclude_detection_id": exclude_detection_id,
                    "include_historical": include_historical,
                    "model_id": model_id,
                },
            )
        )
        if self.find_raises is not None:
            raise self.find_raises
        return self.find_result


class Extract:
    """osnet_loader.extract_person_embedding double.  behavior: list of
    'ok' | 'boom' | 'block' consumed per call; records each image size so
    the CROP handed to extraction is pinned."""

    def __init__(
        self,
        behavior: list[str],
        *,
        vector: list[float],
        model_id: str | None = MODEL,
    ) -> None:
        self.behavior = behavior
        self.vector = vector
        self.model_id = model_id
        self.seen: list[Any] = []

    async def __call__(
        self, _model_dict: dict[str, Any], image: Any, detection_id: str | None = None
    ) -> Any:
        idx = len(self.seen)
        self.seen.append(image.size if hasattr(image, "size") else image)
        kind = self.behavior[idx] if idx < len(self.behavior) else self.behavior[-1]
        if kind == "boom":
            msg = f"transient failure {idx}"
            raise RuntimeError(msg)
        if kind == "block":
            await asyncio.Event().wait()  # never resolves; cancelled by the timeout
        return osnet_loader.PersonEmbeddingResult(
            embedding=np.array(self.vector, dtype=np.float32),
            detection_id="det-1",
            model_id=self.model_id,
        )


class _Stamped:
    """datetime instance whose strftime VALIDATES and records the format, so
    every %-directive mutant ('%Y-%M-%D', '%y', XX-wrapped) raises
    AssertionError and every format-drop lands on an unseeded key — while
    arithmetic and isoformat delegate to the real datetime."""

    def __init__(self, real: datetime, log: list[str]) -> None:
        self._real = real
        self._log = log

    def strftime(self, fmt: str) -> str:
        self._log.append(fmt)
        if fmt != "%Y-%m-%d":
            msg = f"unexpected date format {fmt!r}"
            raise AssertionError(msg)
        return self._real.strftime("%Y-%m-%d")

    def __sub__(self, other: Any) -> Any:
        result = self._real - other
        # datetime arithmetic stays STAMPED: (now - timedelta(days=1)) must
        # run its strftime through this same validator/recorder, so the
        # yesterday-key mutants (%Y-%M-%D, %y, XX-wrap, days=2, +) cannot
        # silently bypass the pin.
        if isinstance(result, datetime):
            return _Stamped(result, self._log)
        return result

    def __add__(self, other: Any) -> Any:
        result = self._real + other
        if isinstance(result, datetime):
            return _Stamped(result, self._log)
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)


class Now:
    """datetime swap: now(tz) returns a format-pinned stamp of FIXED and
    records the tz ARGUMENT — datetime.now(UTC) -> now(None) dies there.
    fromisoformat (used by EntityEmbedding.from_dict) delegates to the real
    class so payload timestamps still decode."""

    def __init__(self, fixed: datetime) -> None:
        self.fixed = fixed
        self.tz_args: list[Any] = []
        self.formats: list[str] = []

    def now(self, tz: Any = "unset") -> _Stamped:
        self.tz_args.append(tz)
        return _Stamped(self.fixed, self.formats)

    def fromisoformat(self, text: str) -> datetime:
        return datetime.fromisoformat(text)

    def __getattr__(self, name: str) -> Any:
        msg = f"Now fake exposes only now()/fromisoformat(): {name}"
        raise AttributeError(msg)


def svc(_stub: dict[str, Any] | None = None, **kwargs: Any) -> ReIdentificationService:
    with _settings_stub(**(_stub or {"req": 7, "timeout": 30.0, "retries": 3})):
        return ReIdentificationService(**kwargs)


def _settings_stub(**over: Any) -> Any:
    st = mock.MagicMock()
    st.reid_max_concurrent_requests = over.get("req", 10)
    st.reid_embedding_timeout = over.get("timeout", 30.0)
    st.reid_max_retries = over.get("retries", 3)
    return mock.patch.object(rs, "get_settings", autospec=True, return_value=st)


def entity(
    *,
    entity_type: str = "person",
    embedding: list[float] | None = None,
    camera_id: str = "cam-7",
    timestamp: datetime | None = None,
    detection_id: str = "42",
    attributes: dict[str, Any] | None = None,
    model_id: str = MODEL,
) -> EntityEmbedding:
    return EntityEmbedding(
        entity_type=entity_type,
        embedding=embedding if embedding is not None else [1.0, 0.0, 0.0],
        camera_id=camera_id,
        timestamp=timestamp or datetime(2026, 10, 5, 12, 0, 0, tzinfo=UTC),
        detection_id=detection_id,
        attributes=attributes or {},
        model_id=model_id,
    )


def stored_row(
    detection_id: str,
    *,
    model_id: str | None = MODEL,
    camera: str = "cam-old",
    embedding: list[float] | None = None,
    ts: str = "2026-10-05T12:00:00+00:00",
    entity_type: str = "person",
) -> dict[str, Any]:
    d: dict[str, Any] = {
        "entity_type": entity_type,
        "embedding": embedding if embedding is not None else [1.0, 0.0, 0.0],
        "camera_id": camera,
        "timestamp": ts,
        "detection_id": detection_id,
        "attributes": {},
        "model_id": model_id if model_id is not None else LEGACY_MODEL_ID,
    }
    return d


def hmatch(
    *,
    entity_id: Any,
    detection_id: str | None,
    similarity: float,
    camera_id: str = "cam-h",
    ts: datetime | None = None,
    model_id: str = MODEL,
    embedding: list[float] | None = None,
) -> HybridEntityMatch:
    return HybridEntityMatch(
        entity_id=entity_id,
        entity_type="person",
        embedding=embedding if embedding is not None else [1.0, 0.0, 0.0],
        camera_id=camera_id,
        timestamp=ts or datetime(2026, 10, 5, 11, 0, 0, tzinfo=UTC),
        detection_id=detection_id,
        attributes={"color": "red"},
        similarity=similarity,
        time_gap_seconds=123.5,
        source="postgresql",
        model_id=model_id,
    )


IMG = Image.new("RGB", (100, 100))
VEC3 = [1.0, 2.0, 3.0]
NOW = datetime(2026, 10, 5, 12, 0, 0, tzinfo=UTC)
TODAY = "2026-10-05"
YDAY = "2026-10-04"


def _handle_ok() -> Any:
    return mock.patch.object(
        osnet_loader, "get_reid_handle", autospec=True, return_value={"model_id": MODEL}
    )


# =============================================================================
# cosine_similarity / batch_cosine_similarity — the dtype family dies on the
# EXACT float32 value (float64 lands elsewhere: measured).
# =============================================================================


def test_cosine_dtype_exact_and_boundaries() -> None:
    assert cosine_similarity(V1, V2) == COS_F32
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0
    assert cosine_similarity([1.0, 2.0], [0.0, 0.0]) == 0.0
    with pytest.raises(ValueError) as ei:
        cosine_similarity([1.0, 2.0], [1.0])
    assert str(ei.value) == "Vectors must have same dimension: 2 vs 1"


def test_batch_dtype_exact_and_zero_polarities() -> None:
    # Measured EXACT: the batch path normalizes THEN dots, so it lands on
    # ...4031715393 (not the cosine_similarity ...4627761841) and the
    # self-similarity is 0.9999998211860657 — a float64 build shifts every
    # digit, so EXACT equality is the dtype pin for this family too.
    assert batch_cosine_similarity(V1, [V2, V1]) == [0.8911944031715393, 0.9999998211860657]
    assert batch_cosine_similarity([1.0, 0.0, 0.0], [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]) == [
        0.0,
        1.0,
    ]
    assert batch_cosine_similarity([0.0, 0.0], [[1.0, 2.0], [3.0, 4.0]]) == [0.0, 0.0]
    assert batch_cosine_similarity([1.0, 1.0], []) == []


# =============================================================================
# __init__ — raw (fmt, *args) tuple EQUALITY kills fmt case/XX twins and
# every arg None/drop twin; both hybrid_storage polarities are pinned.
# =============================================================================

INIT_FMT = (
    "ReIdentificationService initialized with max_concurrent_requests=%d, "
    "embedding_timeout=%.1fs, max_retries=%d, hybrid_storage=%s"
)


def test_init_explicit_knobs_and_hybrid_enabled_message() -> None:
    hybrid = Hybrid(store_result=(UUID(int=0x11), True))
    with log_rec() as rec:  # svc() patches get_settings itself — an outer
        # _settings_stub would double-patch and autospec-of-mocked dies.
        s = svc(
            max_concurrent_requests=7, embedding_timeout=2.5, max_retries=2, hybrid_storage=hybrid
        )
    assert s.max_concurrent_requests == 7
    assert s._embedding_timeout == 2.5
    assert s._max_retries == 2
    assert s.hybrid_storage is hybrid
    assert rec.calls == [("info", (INIT_FMT, 7, 2.5, 2, "enabled"))]


def test_init_settings_defaults_and_hybrid_disabled_message() -> None:
    with log_rec() as rec:
        s = svc(_stub={"req": 10, "timeout": 30.0, "retries": 3})
    assert s.max_concurrent_requests == 10
    assert s._embedding_timeout == 30.0
    assert s._max_retries == 3
    assert s.hybrid_storage is None
    assert rec.calls == [("info", (INIT_FMT, 10, 30.0, 3, "disabled"))]


# =============================================================================
# generate_embedding
# =============================================================================


def _gen(s: ReIdentificationService, extract: Extract, *, bbox: Any = None) -> Any:
    with _handle_ok(), mock.patch.object(osnet_loader, "extract_person_embedding", extract):
        return run(s.generate_embedding(IMG, bbox=bbox))


def test_generate_success_vector_belt_and_debug_message() -> None:
    s = svc(max_retries=1)
    extract = Extract(["ok"], vector=VEC3)
    with log_rec() as rec:
        vec, belt = _gen(s, extract)
    assert vec == [1.0, 2.0, 3.0]
    assert all(type(x) is float for x in vec)  # native floats, not np scalars
    assert belt == MODEL
    assert extract.seen == [(100, 100)]
    assert rec.calls == [
        ("debug", (f"Generated re-ID embedding with dimension 3 from weights {MODEL}",))
    ]


def test_generate_empty_belt_becomes_sentinel_and_debug_names_it() -> None:
    s = svc(max_retries=1)
    extract = Extract(["ok"], vector=VEC3, model_id="")
    with log_rec() as rec:
        vec, belt = _gen(s, extract)
    assert vec == [1.0, 2.0, 3.0]
    assert belt == LEGACY_MODEL_ID
    assert rec.calls == [
        ("debug", (f"Generated re-ID embedding with dimension 3 from weights {LEGACY_MODEL_ID}",))
    ]


def test_generate_missing_handle_raises_with_zoo_name() -> None:
    s = svc()
    with (
        mock.patch.object(osnet_loader, "get_reid_handle", autospec=True, return_value=None),
        log_rec() as rec,
        pytest.raises(ReIDUnavailableError) as ei,
    ):
        run(s.generate_embedding(IMG))
    assert str(ei.value) == (
        f"The re-ID weights ({osnet_loader.OSNET_ZOO_NAME}) are not resident, so no person "
        "embedding can be computed. Check model zoo preload (BACKEND_MODEL_PRELOAD) "
        "and the models.yml weights path — a stored vector requires the pinned "
        "weights, and there is no stub fallback."
    )
    assert rec.calls == []


def test_generate_invalid_bbox_message_and_bbox_attr() -> None:
    s = svc()
    with pytest.raises(InvalidBoundingBoxError) as ei:
        _gen(s, Extract(["ok"], vector=VEC3), bbox=(5, 5, 5, 9))
    assert str(ei.value) == (
        "Invalid bounding box dimensions: (5, 5, 5, 9). "
        "Bounding box has zero width/height, NaN values, or inverted coordinates."
    )
    assert ei.value.bbox == (5.0, 5.0, 5.0, 9.0)


def test_generate_outside_bbox_message_and_bbox_attr() -> None:
    s = svc()
    with pytest.raises(InvalidBoundingBoxError) as ei:
        _gen(s, Extract(["ok"], vector=VEC3), bbox=(200, 200, 210, 210))
    assert str(ei.value) == (
        "Bounding box (200, 200, 210, 210) is completely outside image boundaries "
        "(100x100) or became too small after clamping."
    )
    assert ei.value.bbox == (200.0, 200.0, 210.0, 210.0)


def test_generate_clamp_debug_message_crop_and_inbounds_silence() -> None:
    s = svc(max_retries=1)
    extract = Extract(["ok"], vector=VEC3)
    with log_rec() as rec:
        _gen(s, extract, bbox=(50, 50, 150, 150))
    assert extract.seen == [(50, 50)]  # the CLAMPED box was cropped
    assert rec.find("debug", "clamped") == (
        "Bounding box clamped from (50, 50, 150, 150) to (50, 50, 100, 100) for image size 100x100",
    )
    # In-bounds polarity: NO clamp message — kills the ==/!= flip and the
    # message->None twins from BOTH branches (entered-branch-must-assert).
    s2 = svc(max_retries=1)
    extract2 = Extract(["ok"], vector=VEC3)
    with log_rec() as rec2:
        _gen(s2, extract2, bbox=(10, 20, 30, 40))
    assert extract2.seen == [(20, 20)]
    assert not rec2.has("clamped")


def test_generate_one_pixel_bbox_survives_min_size_one() -> None:
    # Measured: clamp((99,99,100,100),100,100, min_size=1) -> the box,
    # min_size=2 -> None (then the 1-px error message).  Shipped passes 1,
    # so this row must SUCCEED; the min_size mutants die here.
    s = svc(max_retries=1)
    extract = Extract(["ok"], vector=VEC3)
    with log_rec() as rec:
        vec, belt = _gen(s, extract, bbox=(99, 99, 100, 100))
    assert vec == [1.0, 2.0, 3.0] and belt == MODEL
    assert extract.seen == [(1, 1)]
    assert not rec.has("clamped") and not rec.has("completely outside")


def test_generate_min_size_and_clamp_kwargs_measured() -> None:
    real_clamp = rs.clamp_bbox_to_image
    real_valid = rs.is_valid_bbox
    clamp_calls: list[tuple[Any, dict[str, Any]]] = []
    valid_calls: list[tuple[Any, dict[str, Any]]] = []

    def clamp_spy(*args: Any, **kwargs: Any) -> Any:
        clamp_calls.append((args, kwargs))
        return real_clamp(*args, **kwargs)

    def valid_spy(*args: Any, **kwargs: Any) -> Any:
        valid_calls.append((args, kwargs))
        return real_valid(*args, **kwargs)

    s = svc(max_retries=1)
    extract = Extract(["ok"], vector=VEC3)
    with (
        _handle_ok(),
        mock.patch.object(osnet_loader, "extract_person_embedding", extract),
        mock.patch.object(rs, "clamp_bbox_to_image", clamp_spy),
        mock.patch.object(rs, "is_valid_bbox", valid_spy),
        log_rec(),
    ):
        run(s.generate_embedding(IMG, bbox=(50, 50, 150, 150)))
    assert valid_calls == [(((50.0, 50.0, 150.0, 150.0),), {"allow_negative": True})]
    assert len(clamp_calls) == 1
    args, kwargs = clamp_calls[0]
    assert args == ((50, 50, 150, 150), 100, 100)
    # Shipped passes the INT literal 1; a dropped kwarg falls back to the
    # float 1.0 default (== 1 but NOT an int), a None mutant fails the
    # comparison in clamp.  Type identity is the discriminator (measured).
    assert kwargs["min_size"] == 1 and type(kwargs["min_size"]) is int
    assert kwargs["return_none_if_empty"] is True


def test_generate_timeout_retry_warning_then_second_timeout() -> None:
    sleeps: list[Any] = []

    async def sleep_spy(d: Any) -> None:
        sleeps.append(d)

    s = svc(max_retries=2, embedding_timeout=0.05)
    extract = Extract(["block"], vector=VEC3)
    with (
        log_rec() as rec,
        mock.patch.object(rs.asyncio, "sleep", sleep_spy),
        pytest.raises(RuntimeError) as ei,
    ):
        _gen(s, extract)
    assert sleeps == [1]
    assert rec.find("warning", "timed out") == (
        "Embedding generation timed out (attempt 1/2), retrying in 1s...",
    )
    assert str(ei.value) == "Embedding generation timed out after 2 attempts"
    assert isinstance(ei.value.__cause__, TimeoutError)
    assert str(ei.value.__cause__) == "Embedding generation timed out after 0.05s"


def test_generate_retry_message_backoff_then_success() -> None:
    sleeps: list[Any] = []

    async def sleep_spy(d: Any) -> None:
        sleeps.append(d)

    s = svc(max_retries=2)
    extract = Extract(["boom", "ok"], vector=VEC3)
    with log_rec() as rec, mock.patch.object(rs.asyncio, "sleep", sleep_spy):
        vec, belt = _gen(s, extract)
    assert vec == [1.0, 2.0, 3.0] and belt == MODEL
    assert sleeps == [1]
    assert rec.find("warning", "attempt") == (
        "Embedding generation failed (attempt 1/2): transient failure 0, retrying in 1s...",
    )


def test_generate_exhausted_runtime_cause_and_messages() -> None:
    sleeps: list[Any] = []

    async def sleep_spy(d: Any) -> None:
        sleeps.append(d)

    s = svc(max_retries=2)
    extract = Extract(["boom", "boom"], vector=VEC3)
    with (
        log_rec() as rec,
        mock.patch.object(rs.asyncio, "sleep", sleep_spy),
        pytest.raises(RuntimeError) as ei,
    ):
        _gen(s, extract)
    assert str(ei.value) == "Embedding generation failed after 2 attempts"
    assert isinstance(ei.value.__cause__, RuntimeError)
    assert str(ei.value.__cause__) == "transient failure 1"
    assert sleeps == [1]
    assert rec.find("warning", "attempt") == (
        "Embedding generation failed (attempt 1/2): transient failure 0, retrying in 1s...",
    )
    assert rec.find("error", "failed after") == (
        "Embedding generation failed after 2 attempts: transient failure 1",
    )


def test_generate_timeout_backoff_delays_sequence() -> None:
    # max_retries=3 is the 2**attempt pin: at retries=2 only attempt 0
    # sleeps and 2**0 == 3**0 == 1 -- the exponential-base mutant is equal
    # there (measured). The SECOND delay is where 2**n vs 3**n diverges.
    sleeps: list[Any] = []

    async def sleep_spy(d: Any) -> None:
        sleeps.append(d)

    s = svc(max_retries=3, embedding_timeout=0.05)
    extract = Extract(["block"], vector=VEC3)
    with (
        log_rec() as rec,
        mock.patch.object(rs.asyncio, "sleep", sleep_spy),
        pytest.raises(RuntimeError) as ei,
    ):
        _gen(s, extract)
    assert sleeps == [1, 2]
    assert rec.find("warning", "(attempt 1/3)") == (
        "Embedding generation timed out (attempt 1/3), retrying in 1s...",
    )
    assert rec.find("warning", "(attempt 2/3)") == (
        "Embedding generation timed out (attempt 2/3), retrying in 2s...",
    )
    assert str(ei.value) == "Embedding generation timed out after 3 attempts"
    assert isinstance(ei.value.__cause__, TimeoutError)
    assert str(ei.value.__cause__) == "Embedding generation timed out after 0.05s"
    assert rec.find("error", "timed out") == ("Embedding generation timed out after 3 attempts",)


def test_generate_failure_backoff_delays_sequence() -> None:
    sleeps: list[Any] = []

    async def sleep_spy(d: Any) -> None:
        sleeps.append(d)

    s = svc(max_retries=3)
    extract = Extract(["boom"], vector=VEC3)
    with (
        log_rec() as rec,
        mock.patch.object(rs.asyncio, "sleep", sleep_spy),
        pytest.raises(RuntimeError) as ei,
    ):
        _gen(s, extract)
    assert sleeps == [1, 2]
    assert rec.find("warning", "(attempt 2/3)") == (
        "Embedding generation failed (attempt 2/3): transient failure 1, retrying in 2s...",
    )
    assert str(ei.value) == "Embedding generation failed after 3 attempts"
    assert str(ei.value.__cause__) == "transient failure 2"
    assert rec.find("error", "failed after") == (
        "Embedding generation failed after 3 attempts: transient failure 2",
    )


def test_generate_timeout_polarity_messages_and_cause() -> None:
    # NOTE: no asyncio.sleep spy here — patching rs.asyncio.sleep patches
    # the SHARED module attribute and would fake out Extract's own
    # block-sleep. The timeout cancels it at 0.05s instead.
    s = svc(max_retries=1, embedding_timeout=0.05)
    extract = Extract(["block"], vector=VEC3)
    with (
        log_rec() as rec,
        pytest.raises(RuntimeError) as ei,
    ):
        _gen(s, extract)
    assert str(ei.value) == "Embedding generation timed out after 1 attempts"
    assert isinstance(ei.value.__cause__, TimeoutError)
    assert str(ei.value.__cause__) == "Embedding generation timed out after 0.05s"
    assert rec.find("warning", "attempt") is None
    assert rec.find("error", "timed out") == ("Embedding generation timed out after 1 attempts",)


# =============================================================================
# store_embedding — fallback leg (foreign double), atomic leg (REAL
# RedisClient subclass), PG leg (strict signature spy).
# =============================================================================


def test_store_fallback_leg_sequence_message_and_vehicle_bucket() -> None:
    e = entity(entity_type="vehicle", detection_id="42")
    s = svc()
    r = Redis({}, strict=False)
    with log_rec() as rec:
        out = run(s.store_embedding(r, e, persist_to_postgres=False))
    key = f"entity_embeddings:{MODEL}:2026-10-05"
    assert out is None
    assert r.calls[0] == ("get", key)
    assert len(r.calls) == 2
    op, skey, svalue, sex = r.calls[1]
    assert op == "set" and skey == key and sex == 86400
    assert json.loads(svalue) == {"persons": [], "vehicles": [e.to_dict()]}
    assert rec.calls == [("debug", ("Stored vehicle embedding for camera cam-7 (atomic)",))]


def test_store_fallback_merges_existing_bucket_row() -> None:
    e = entity(detection_id="43")
    key = f"entity_embeddings:{MODEL}:2026-10-05"
    seed = {"persons": [stored_row("9")], "vehicles": []}
    s = svc()
    r = Redis({key: json.dumps(seed)}, strict=False)
    with log_rec():
        out = run(s.store_embedding(r, e, persist_to_postgres=False))
    assert out is None
    _op, skey, svalue, sex = r.calls[1]
    assert skey == key and sex == 86400
    saved = json.loads(svalue)
    assert saved["vehicles"] == []
    assert saved["persons"] == seed["persons"] + [e.to_dict()]


def test_store_atomic_leg_eval_args_lua_text_and_kwargs() -> None:
    raw = RawEval()
    w = SubRedisClient(raw)
    e = entity(detection_id="42")
    s = svc()
    with log_rec() as rec:
        out = run(s.store_embedding(w, e, persist_to_postgres=False))
    key = f"entity_embeddings:{MODEL}:2026-10-05"
    assert out is None
    assert w.calls == [] and len(raw.evals) == 1
    args = raw.evals[0]
    assert args[0] == LUA
    assert args[1:] == (1, key, json.dumps(e.to_dict()), "persons", "86400")
    assert rec.calls == [("debug", ("Stored person embedding for camera cam-7 (atomic)",))]


def test_store_hasattr_seam_falls_back_when_raw_lacks_eval() -> None:
    w = SubRedisClient(RawNoEval())
    e = entity(detection_id="42")
    s = svc()
    key = f"entity_embeddings:{MODEL}:2026-10-05"
    with log_rec() as rec:
        out = run(s.store_embedding(w, e, persist_to_postgres=False))
    assert out is None
    assert w.calls[0] == ("get", key)
    op, skey, svalue, sargs, skw = w.calls[1]
    assert op == "set" and skey == key and sargs == () and skw == {"ex": 86400}
    assert json.loads(svalue)["persons"] == [e.to_dict()]
    assert rec.find("debug", "Stored") == ("Stored person embedding for camera cam-7 (atomic)",)


def test_store_redis_failure_message_and_reraise() -> None:
    e = entity()
    key = f"entity_embeddings:{MODEL}:2026-10-05"
    s = svc()
    r = Redis({}, strict=False, raise_on={key: ConnectionError("redis down")})
    with log_rec() as rec, pytest.raises(ConnectionError):
        run(s.store_embedding(r, e))
    assert rec.calls == [("error", ("Failed to store embedding: redis down",))]


def test_store_pg_leg_kwargs_debug_and_return() -> None:
    uid = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
    h = Hybrid(store_result=(uid, True))
    e = entity(detection_id="42")
    s = svc(hybrid_storage=h)
    with log_rec() as rec:
        out = run(s.store_embedding(Redis({}, strict=False), e, persist_to_postgres=True))
    assert out == uid
    assert h.calls == [
        (
            "store_detection_embedding",
            {
                "detection_id": 42,
                "entity_type": "person",
                "embedding": [1.0, 0.0, 0.0],
                "camera_id": "cam-7",
                "timestamp": e.timestamp,
                "attributes": {},
                "model_id": MODEL,
            },
        )
    ]
    assert rec.find("debug", "Persisted") == (
        "Persisted %s embedding to PostgreSQL for camera %s (entity_id=%s)",
        "person",
        "cam-7",
        uid,
    )


def test_store_pg_non_digit_detection_id_becomes_zero() -> None:
    uid = UUID(int=0x7)
    h = Hybrid(store_result=(uid, False))
    e = entity(detection_id="det-abc")
    s = svc(hybrid_storage=h)
    with log_rec():
        out = run(s.store_embedding(Redis({}, strict=False), e, persist_to_postgres=True))
    assert out == uid
    assert h.calls[0][1]["detection_id"] == 0


def test_store_pg_gate_requires_both_flag_and_storage() -> None:
    h = Hybrid(store_result=(UUID(int=0x7), False))
    e = entity()
    s = svc(hybrid_storage=h)
    with log_rec() as rec:
        out = run(s.store_embedding(Redis({}, strict=False), e, persist_to_postgres=False))
    assert out is None
    assert h.calls == []
    assert not rec.has("Persisted")
    # no storage + persist=True also never touches PG and logs no warning
    s2 = svc()
    with log_rec() as rec2:
        assert run(s2.store_embedding(Redis({}, strict=False), e, persist_to_postgres=True)) is None
    assert not rec2.has("Failed to persist")


def test_store_pg_failure_warns_and_returns_none() -> None:
    h = Hybrid(store_raises=RuntimeError("pg down"))
    e = entity()
    s = svc(hybrid_storage=h)
    with log_rec() as rec:
        out = run(s.store_embedding(Redis({}, strict=False), e, persist_to_postgres=True))
    assert out is None
    assert rec.find("warning", "Failed to persist") == (
        "Failed to persist %s embedding to PostgreSQL for camera %s: %s",
        "person",
        "cam-7",
        "pg down",
    )


# =============================================================================
# find_matching_entities
# =============================================================================


def patch_observe() -> Any:
    return mock.patch.object(rs, "observe_reid_match_duration", autospec=True)


def test_find_hybrid_leg_kwargs_and_full_match_equality() -> None:
    hm = hmatch(entity_id=UUID(int=0x2B), detection_id="d-9", similarity=0.91)
    h = Hybrid(find_result=[hm])
    s = svc(hybrid_storage=h)
    emb = [1.0, 0.0, 0.0]
    r = Redis({}, strict=False)
    with (
        patch_observe() as observe,
        log_rec() as rec,
    ):
        matches = run(
            s.find_matching_entities(
                r,
                emb,
                entity_type="person",
                threshold=0.8,
                exclude_detection_id="x1",
                include_historical=True,
                camera_id="cam-a",
                model_id=MODEL,
            )
        )
    assert h.calls == [
        (
            "find_matches",
            {
                "embedding": emb,
                "entity_type": "person",
                "threshold": 0.8,
                "exclude_detection_id": "x1",
                "include_historical": True,
                "model_id": MODEL,
            },
        )
    ]
    assert len(matches) == 1 and isinstance(matches[0], EntityMatch)
    m = matches[0]
    assert m.similarity == 0.91
    assert m.time_gap_seconds == 123.5
    assert m.entity.entity_type == "person"
    assert m.entity.embedding == [1.0, 0.0, 0.0]
    assert m.entity.camera_id == "cam-h"
    assert m.entity.timestamp == hm.timestamp
    assert m.entity.detection_id == "d-9"
    assert m.entity.attributes == {"color": "red"}
    assert m.entity.model_id == MODEL
    assert r.calls == []  # hybrid path never reads Redis
    assert [c.args[0] for c in observe.call_args_list] == ["person"]
    dur = observe.call_args_list[0].args[1]
    assert isinstance(dur, float) and 0.0 <= dur < 60.0
    found_dbg = rec.find("debug", "hybrid matches")
    assert found_dbg is not None and len(found_dbg) == 5
    fmt, n, et, th, ih = found_dbg
    assert fmt == "Found %d hybrid matches for %s (threshold=%.2f, include_historical=%s)"
    assert (n, et, th, ih) == (1, "person", 0.8, True)


def test_find_hybrid_metrics_truth_table() -> None:
    hm = hmatch(entity_id=UUID(int=0x2D), detection_id="d-1", similarity=0.9, camera_id="cam-h")

    def call(metric: str | None) -> tuple[Any, Any, Any]:
        h = Hybrid(find_result=[hm])
        s = svc(hybrid_storage=h)
        with (
            mock.patch.object(rs, "record_reid_attempt", autospec=True) as attempts,
            mock.patch.object(rs, "record_reid_match", autospec=True) as matchm,
            mock.patch.object(rs, "record_cross_camera_handoff", autospec=True) as handoff,
            log_rec(),
        ):
            out = run(
                s.find_matching_entities(
                    Redis({}, strict=False),
                    [1.0, 0.0, 0.0],
                    include_historical=True,
                    camera_id=metric,
                    model_id=MODEL,
                )
            )
        assert len(out) == 1
        return (
            [tuple(c.args) for c in attempts.call_args_list],
            [tuple(c.args) for c in matchm.call_args_list],
            [tuple(c.args) for c in handoff.call_args_list],
        )

    # known & cross: handoff fires with the full arg triple.
    assert call("cam-a") == (
        [("person", "cam-a")],
        [("person", "cam-h")],
        [("cam-h", "cam-a", "person")],
    )
    # known, SAME camera: match recorded, no handoff (kills the or-swap and
    # the ==-flips that would emit one).
    assert call("cam-h") == (
        [("person", "cam-h")],
        [("person", "cam-h")],
        [],
    )
    # unknown camera: metric_camera_id is the sentinel literal "unknown" —
    # the XX/UNKNOWN case mutants make it 'known' and wrongly hand off.
    assert call(None) == (
        [("person", "unknown")],
        [("person", "cam-h")],
        [],
    )


def test_find_hybrid_absent_detection_id_falls_back_to_entity_id() -> None:
    uid = UUID(int=0x2C)
    hm = hmatch(entity_id=uid, detection_id="", similarity=0.77)
    h = Hybrid(find_result=[hm])
    s = svc(hybrid_storage=h)
    with log_rec():
        matches = run(
            s.find_matching_entities(
                Redis({}, strict=False),
                [1.0, 0.0, 0.0],
                include_historical=True,
                camera_id="cam-a",
                model_id=MODEL,
            )
        )
    assert matches[0].entity.detection_id == str(uid)


def test_find_hybrid_failure_warns_and_falls_back_to_redis() -> None:
    h = Hybrid(find_raises=RuntimeError("db gone"))
    s = svc(hybrid_storage=h)
    key_t = f"entity_embeddings:{MODEL}:{TODAY}"
    key_y = f"entity_embeddings:{MODEL}:{YDAY}"
    r = Redis(
        {
            key_t: json.dumps({"persons": [stored_row("5", camera="cam-old")], "vehicles": []}),
            key_y: None,
        }
    )
    with (
        mock.patch.object(rs, "datetime", NOW_STAMP := Now(NOW)),
        mock.patch.object(rs, "record_reid_attempt", autospec=True),
        log_rec() as rec,
    ):
        matches = run(
            s.find_matching_entities(
                r,
                [1.0, 0.0, 0.0],
                include_historical=True,
                camera_id=None,
                model_id=MODEL,
            )
        )
    assert [m.entity.detection_id for m in matches] == ["5"]
    assert NOW_STAMP.formats == ["%Y-%m-%d", "%Y-%m-%d"]
    assert rec.find("warning", "Hybrid storage search failed") == (
        "Hybrid storage search failed, falling back to Redis-only: %s",
        "db gone",
    )


def _rows() -> dict[str, Any]:
    return {
        "persons": [
            stored_row("dup", camera="cam-metric"),
            stored_row("ex", camera="cam-ex"),
            stored_row("leg", model_id=None, camera="cam-leg"),
            stored_row("dim", embedding=[1.0, 0.0, 0.0, 0.0], camera="cam-dim"),
            "junk",
            stored_row("m1", camera="cam-1"),
            stored_row("m2", camera="cam-metric"),
        ],
        "vehicles": [],
    }


def test_find_redis_boundary_sort_skips_and_call_keys() -> None:
    key_t = f"entity_embeddings:{MODEL}:{TODAY}"
    key_y = f"entity_embeddings:{MODEL}:{YDAY}"
    r = Redis(
        {
            key_t: json.dumps(_rows()),
            key_y: json.dumps({"persons": [], "vehicles": []}),
        }
    )
    s = svc()
    with (
        mock.patch.object(rs, "datetime", NOW_STAMP := Now(NOW)),
        mock.patch.object(rs, "record_reid_attempt", autospec=True) as attempts,
        mock.patch.object(rs, "record_reid_match", autospec=True) as matchm,
        mock.patch.object(rs, "record_cross_camera_handoff", autospec=True) as handoff,
        patch_observe() as observe,
        log_rec() as rec,
    ):
        matches = run(
            s.find_matching_entities(
                r,
                [1.0, 0.0, 0.0],
                entity_type="person",
                threshold=0.7,
                exclude_detection_id="ex",
                include_historical=False,
                camera_id="cam-metric",
                model_id=MODEL,
            )
        )
    assert NOW_STAMP.tz_args == [UTC] and NOW_STAMP.formats == ["%Y-%m-%d", "%Y-%m-%d"]
    assert sorted(c[1] for c in r.calls) == sorted([key_t, key_y])
    assert [m.entity.detection_id for m in matches] == ["dup", "m1", "m2"]
    assert [m.similarity for m in matches] == [1.0, 1.0, 1.0]
    assert [m.time_gap_seconds for m in matches] == [0.0, 0.0, 0.0]
    attempts.assert_called_once_with("person", "cam-metric")
    assert [tuple(c.args) for c in matchm.call_args_list] == [
        ("person", "cam-metric"),
        ("person", "cam-1"),
        ("person", "cam-metric"),
    ]
    assert [tuple(c.args) for c in handoff.call_args_list] == [("cam-1", "cam-metric", "person")]
    assert [c.args[0] for c in observe.call_args_list] == ["person"]
    dur = observe.call_args_list[0].args[1]
    assert isinstance(dur, float) and 0.0 <= dur < 60.0
    assert rec.find("debug", "skipped") == (
        "Re-ID search skipped %d uncomparable %s row(s) (provenance mismatch or dimension)",
        2,
        "person",
    )
    assert rec.find("warning", "Skipping malformed") == (
        "Skipping malformed entity data in Redis key %s: expected dict, got %s",
        key_t,
        "str",
    )
    assert rec.find("debug", "Found") == (f"Found 3 matching person(s) with threshold {0.7}",)


def test_find_threshold_inclusive_and_defaults_and_no_partition() -> None:
    key_t = f"entity_embeddings:{MODEL}:{TODAY}"
    key_y = f"entity_embeddings:{MODEL}:{YDAY}"
    payload = {"persons": [stored_row("exact", camera="cam-x")], "vehicles": []}
    r = Redis({key_t: json.dumps(payload), key_y: None})
    s = svc()
    with (
        mock.patch.object(rs, "datetime", Now(NOW)),
        mock.patch.object(rs, "record_reid_attempt", autospec=True) as attempts,
        log_rec() as rec,
    ):
        # similarity of the identical vector is EXACTLY 1.0: shipped >=
        # keeps it, the > mutant drops the match.
        hit = run(
            s.find_matching_entities(
                r, [1.0, 0.0, 0.0], threshold=1.0, model_id=MODEL, camera_id="cam-metric"
            )
        )
        assert [m.entity.detection_id for m in hit] == ["exact"]
        # default entity_type: the attempt arg renders it.
        hit2 = run(s.find_matching_entities(r, [1.0, 0.0, 0.0], threshold=0.7, model_id=MODEL))
        assert [m.entity.detection_id for m in hit2] == ["exact"]
        assert [tuple(c.args) for c in attempts.call_args_list] == [
            ("person", "cam-metric"),
            ("person", "unknown"),
        ]
        # model_id None / sentinel: the F11 honest answer — NO key read.
        r2 = Redis({})
        assert run(s.find_matching_entities(r2, [1.0, 0.0, 0.0], threshold=0.5)) == []
        assert r2.calls == []
        r3 = Redis({})
        assert (
            run(
                s.find_matching_entities(
                    r3, [1.0, 0.0, 0.0], threshold=0.5, model_id=LEGACY_MODEL_ID
                )
            )
            == []
        )
        assert r3.calls == []
    assert rec.find("error", "Failed to find") is None


def test_find_cross_camera_truth_table() -> None:
    def call(metric: str | None, stored_camera: str) -> list[Any]:
        key_t = f"entity_embeddings:{MODEL}:{TODAY}"
        payload = {"persons": [stored_row("t1", camera=stored_camera)], "vehicles": []}
        r = Redis({key_t: json.dumps(payload), f"entity_embeddings:{MODEL}:{YDAY}": None})
        s = svc()
        with (
            mock.patch.object(rs, "datetime", Now(NOW)),
            mock.patch.object(rs, "record_cross_camera_handoff", autospec=True) as handoff,
            log_rec(),
        ):
            out = run(
                s.find_matching_entities(
                    r, [1.0, 0.0, 0.0], threshold=0.5, camera_id=metric, model_id=MODEL
                )
            )
        assert len(out) == 1
        return [tuple(c.args) for c in handoff.call_args_list]

    assert call("cam-1", "cam-2") == [("cam-2", "cam-1", "person")]  # known & cross
    assert call("cam-1", "cam-1") == []  # known, same camera
    assert call(None, "cam-2") == []  # unknown camera never hands off
    assert call(None, "unknown-sentinel-row") == []


def test_find_vehicle_bucket_person_absent_and_list_payload_silent() -> None:
    key_t = f"entity_embeddings:{MODEL}:{TODAY}"
    key_y = f"entity_embeddings:{MODEL}:{YDAY}"
    r = Redis(
        {
            key_t: json.dumps({"persons": [stored_row("p1")]}),  # NO "vehicles" key
            key_y: json.dumps({"vehicles": [stored_row("v1", camera="cam-v")]}),  # NO "persons"
        }
    )
    s = svc()
    with (
        mock.patch.object(rs, "datetime", Now(NOW)),
        mock.patch.object(rs, "record_reid_attempt", autospec=True),
        log_rec() as rec,
    ):
        veh = run(
            s.find_matching_entities(
                r, [1.0, 0.0, 0.0], entity_type="vehicle", threshold=0.5, model_id=MODEL
            )
        )
        per = run(
            s.find_matching_entities(
                r, [1.0, 0.0, 0.0], entity_type="person", threshold=0.5, model_id=MODEL
            )
        )
    assert [m.entity.detection_id for m in veh] == ["v1"]  # person bucket never scored
    assert [m.entity.detection_id for m in per] == ["p1"]  # vehicles bucket never scored
    assert rec.find("error", "Failed to find") is None  # [] defaults held on BOTH keys
    assert rec.find("debug", "skipped") is None  # zero skips: NO skipped message


def test_find_list_payload_is_silently_empty_never_error() -> None:
    key_t = f"entity_embeddings:{MODEL}:{TODAY}"
    key_y = f"entity_embeddings:{MODEL}:{YDAY}"
    r = Redis({key_t: json.dumps([1, 2]), key_y: json.dumps([3])})
    s = svc()
    with (
        mock.patch.object(rs, "datetime", Now(NOW)),
        mock.patch.object(rs, "record_reid_attempt", autospec=True),
        log_rec() as rec,
    ):
        out = run(s.find_matching_entities(r, [1.0, 0.0, 0.0], threshold=0.5, model_id=MODEL))
    assert out == []
    assert rec.find("error", "Failed to find") is None
    assert rec.find("debug", "Found") == (f"Found 0 matching person(s) with threshold {0.5}",)


def test_find_malformed_row_message_and_skips_do_not_stop_the_bucket() -> None:
    key_t = f"entity_embeddings:{MODEL}:{TODAY}"
    payload = {"persons": ["junk", "junk2", stored_row("ok")], "vehicles": []}
    r = Redis({key_t: json.dumps(payload), f"entity_embeddings:{MODEL}:{YDAY}": None})
    s = svc()
    with (
        mock.patch.object(rs, "datetime", Now(NOW)),
        mock.patch.object(rs, "record_reid_attempt", autospec=True),
        log_rec() as rec,
    ):
        out = run(s.find_matching_entities(r, [1.0, 0.0, 0.0], threshold=0.5, model_id=MODEL))
    assert [m.entity.detection_id for m in out] == ["ok"]  # continue, not break
    warns = [args for _l, args in rec.calls if args and str(args[0]).startswith("Skipping")]
    assert warns == [
        ("Skipping malformed entity data in Redis key %s: expected dict, got %s", key_t, "str"),
        ("Skipping malformed entity data in Redis key %s: expected dict, got %s", key_t, "str"),
    ]


def test_find_total_get_failure_message_and_empty() -> None:
    async def boom_get(_key: str) -> None:
        raise ConnectionError("boom")

    r = Redis({})
    r.get = boom_get  # type: ignore[method-assign]
    s = svc()
    with (
        mock.patch.object(rs, "datetime", Now(NOW)),
        mock.patch.object(rs, "record_reid_attempt", autospec=True),
        log_rec() as rec,
    ):
        out = run(s.find_matching_entities(r, [1.0, 0.0, 0.0], model_id=MODEL))
    assert out == []
    assert rec.find("error", "Failed to find matching entities") == (
        "Failed to find matching entities: boom",
    )


def test_find_falsy_date_row_survives_either_set_order() -> None:
    # dates_to_check = list({today, yesterday}) is a SET -- its order is
    # PYTHONHASHSEED-dependent per process. The continue->break mutant on
    # the falsy data_raw row therefore kills under ONE order only (run 1
    # measured exactly this flakiness: the sweep process killed, the run
    # child did not). BOTH orders are pinned here: seeded-first and
    # seeded-last scenarios each run under whatever order the set yields.
    key_t = f"entity_embeddings:{MODEL}:{TODAY}"
    key_y = f"entity_embeddings:{MODEL}:{YDAY}"
    s = svc()
    for seeded, empty in ((key_t, key_y), (key_y, key_t)):
        r = Redis(
            {
                seeded: json.dumps({"persons": [stored_row("keep")], "vehicles": []}),
                empty: None,
            }
        )
        with (
            mock.patch.object(rs, "datetime", Now(NOW)),
            mock.patch.object(rs, "record_reid_attempt", autospec=True),
            log_rec() as rec,
        ):
            out = run(s.find_matching_entities(r, [1.0, 0.0, 0.0], model_id=MODEL))
        assert [m.entity.detection_id for m in out] == ["keep"]
        assert rec.find("debug", "Found") == (f"Found 1 matching person(s) with threshold {0.7}",)


def test_find_two_of_a_kind_provenance_skip_count() -> None:
    # The existing boundary test has ONE skip per site (provenance row +
    # mis-dimension row), so a '+=' -> '= 1' mutant on either site still
    # totals 2 there (measured run-1 survivor). TWO rows through the SAME
    # site make the accumulator mutation observable.
    key_t = f"entity_embeddings:{MODEL}:{TODAY}"
    key_y = f"entity_embeddings:{MODEL}:{YDAY}"
    r = Redis(
        {
            key_t: json.dumps(
                {
                    "persons": [
                        stored_row("leg1", model_id=None),
                        stored_row("leg2", model_id="other-model"),
                        stored_row("real"),
                    ],
                    "vehicles": [],
                }
            ),
            key_y: json.dumps({"persons": [], "vehicles": []}),
        }
    )
    s = svc()
    with (
        mock.patch.object(rs, "datetime", Now(NOW)),
        mock.patch.object(rs, "record_reid_attempt", autospec=True),
        log_rec() as rec,
    ):
        out = run(s.find_matching_entities(r, [1.0, 0.0, 0.0], model_id=MODEL))
    assert [m.entity.detection_id for m in out] == ["real"]
    assert rec.find("debug", "skipped") == (
        "Re-ID search skipped %d uncomparable %s row(s) (provenance mismatch or dimension)",
        2,
        "person",
    )


# =============================================================================
# get_entity_history
# =============================================================================


def test_history_key_set_date_formats_tz_and_camera_filter() -> None:
    nowf = Now(NOW)
    key_t = f"entity_embeddings:{TODAY}"
    key_y = f"entity_embeddings:{YDAY}"
    row_t1 = stored_row("t-late", camera="cam-a", ts="2026-10-05T11:30:00+00:00")
    row_t2 = stored_row("t-early", camera="cam-b", ts="2026-10-05T08:00:00+00:00")
    row_y = stored_row("y1", camera="cam-a", ts="2026-10-04T09:00:00+00:00")
    r = Redis(
        {
            key_t: json.dumps({"persons": [row_t1, row_t2], "vehicles": []}),
            key_y: json.dumps({"persons": [row_y], "vehicles": []}),
        }
    )
    s = svc()
    with mock.patch.object(rs, "datetime", nowf):
        rows = run(s.get_entity_history(r, "person", camera_id="cam-a"))
    assert sorted(c[1] for c in r.calls) == sorted([key_t, key_y])
    assert nowf.tz_args == [UTC]
    assert nowf.formats == ["%Y-%m-%d", "%Y-%m-%d"]
    assert [row_.detection_id for row_ in rows] == ["t-late", "y1"]  # newest first; cam-b dropped


def test_history_vehicle_polarity_and_camera_filter_drops_all() -> None:
    nowf = Now(NOW)
    r = Redis(
        {
            f"entity_embeddings:{TODAY}": json.dumps({"vehicles": [stored_row("vh")]}),
            f"entity_embeddings:{YDAY}": None,
        }
    )
    s = svc()
    with mock.patch.object(rs, "datetime", nowf):
        rows = run(s.get_entity_history(r, "vehicle", camera_id="nope"))
    assert rows == []  # vehicle bucket read; the only row fails the camera filter
    assert nowf.formats == ["%Y-%m-%d", "%Y-%m-%d"]


def test_history_merges_scanned_partitions() -> None:
    nowf = Now(NOW)
    part_key = f"entity_embeddings:{MODEL}:{YDAY}"
    payload = {"persons": [stored_row("from-partition")], "vehicles": []}

    class ScanRedis(Redis):
        def scan_iter(self, *, match: str, count: int = 100) -> Any:
            self.calls.append(("scan", match, count))

            async def _gen() -> Any:
                if match.endswith(f":{YDAY}"):
                    yield part_key.encode()

            return _gen()

    r = ScanRedis(
        {
            f"entity_embeddings:{TODAY}": None,
            f"entity_embeddings:{YDAY}": None,
            part_key: json.dumps(payload),
        }
    )
    s = svc()
    with mock.patch.object(rs, "datetime", nowf):
        rows = run(s.get_entity_history(r, "person"))
    assert [row_.detection_id for row_ in rows] == ["from-partition"]
    assert sorted(c[1] for c in r.calls if c[0] == "get") == sorted(
        [f"entity_embeddings:{TODAY}", f"entity_embeddings:{YDAY}", part_key]
    )
    # dates_to_check is a SET -> its iteration order is not an observable;
    # pin the scan-call SET (pattern + count) instead of its order.
    assert sorted(c for c in r.calls if c[0] == "scan") == sorted(
        [
            ("scan", f"entity_embeddings:*:{TODAY}", 100),
            ("scan", f"entity_embeddings:*:{YDAY}", 100),
        ]
    )


def test_history_scan_failure_debug_dict_payload_and_malformed_row() -> None:
    nowf = Now(NOW)

    class BadScan(Redis):
        def scan_iter(self, *, match: str, count: int = 100) -> Any:
            raise ConnectionError("scan down")

    key_t = f"entity_embeddings:{TODAY}"
    payload = {"persons": ["junk", stored_row("fine")]}
    r = BadScan({key_t: payload, f"entity_embeddings:{YDAY}": None})  # dict payload (wrapper style)
    s = svc()
    with log_rec() as rec, mock.patch.object(rs, "datetime", nowf):
        rows = run(s.get_entity_history(r, "person"))
    assert [row_.detection_id for row_ in rows] == ["fine"]
    scan_dbg = rec.find("debug", "partition scan failed")
    assert scan_dbg is not None and scan_dbg[0] == ("entity_embeddings partition scan failed: %s")
    assert str(scan_dbg[1]) == "scan down"
    assert rec.find("warning", "Skipping malformed") == (
        "Skipping malformed entity data in Redis key %s: expected dict, got %s",
        key_t,
        "str",
    )


def test_history_partition_scan_awaitable_close_discipline() -> None:
    # _history_partition_keys called DIRECTLY: the dates LIST is ours, so
    # unlike the find/history paths there is no set-order nondeterminism --
    # every mutant below diverges on an exact list equality.
    #  - TODAY -> an AWAITABLE scan (the Mock-double shape the shipped code
    #    closes instead of awaiting): kills the isawaitable/close/getattr/
    #    callable cluster (close recording + no-debug pins).
    #  - YDAY  -> an awaitable WITHOUT close: the absent-attribute polarity
    #    that kills the trailing-comma 2-arg getattr (default unreachable
    #    only when the attr is missing -- the documented pitfall).
    #  - ODATE -> async-gen yielding a STR key: shipped passes it through
    #    str(item); the decode-or-True mutant raises AttributeError.
    # The scan signature requires count (no default), so the call-site
    # count-DROP becomes a TypeError on the very first scan.
    closes: list[str] = []
    scans: list[tuple[str, int]] = []
    odate = "2026-10-01"  # NOT YDAY (2026-10-04) — must branch-distinct

    class AwaitableWithClose:
        def __init__(self, tag: str) -> None:
            self.tag = tag

        def __await__(self) -> Any:
            yield  # never driven -- shipped CLOSES an awaitable scan

        def close(self) -> None:
            closes.append(self.tag)

    class AwaitableNoClose:
        def __await__(self) -> Any:
            yield  # never driven

    class ScanRedis(Redis):
        def scan_iter(self, *, match: str, count: int) -> Any:
            scans.append((match, count))
            if match.endswith(f":{TODAY}"):
                return AwaitableWithClose("today")
            if match.endswith(f":{YDAY}"):
                return AwaitableNoClose()

            async def _gen() -> Any:
                yield f"entity_embeddings:{MODEL}:{odate}"

            return _gen()

    s = svc()
    r = ScanRedis({})
    with log_rec() as rec:
        keys = run(s._history_partition_keys(r, [TODAY, YDAY, odate]))
    assert keys == [f"entity_embeddings:{MODEL}:{odate}"]
    assert closes == ["today"]
    assert scans == [
        (f"entity_embeddings:*:{TODAY}", 100),
        (f"entity_embeddings:*:{YDAY}", 100),
        (f"entity_embeddings:*:{odate}", 100),
    ]
    assert rec.find("debug", "partition scan failed") is None


def test_history_failure_message_and_empty() -> None:
    nowf = Now(NOW)

    async def boom_get(_key: str) -> None:
        raise ConnectionError("hist boom")

    r = Redis({})
    r.get = boom_get  # type: ignore[method-assign]
    s = svc()
    with log_rec() as rec, mock.patch.object(rs, "datetime", nowf):
        rows = run(s.get_entity_history(r, "person"))
    assert rows == []
    assert rec.find("error", "Failed to get entity history") == (
        "Failed to get entity history: hist boom",
    )


def test_history_continue_not_break_and_absent_bucket_and_list_sibling() -> None:
    nowf = Now(NOW)
    key_t = f"entity_embeddings:{TODAY}"
    key_y = f"entity_embeddings:{YDAY}"
    late = stored_row("after-junk", ts="2026-10-05T23:00:00+00:00")
    r = Redis(
        {
            key_t: json.dumps({"persons": [stored_row("first"), "junk", late]}),
            key_y: json.dumps({"vehicles": []}),  # NO "persons" key -> [] default
        }
    )
    s = svc()
    with log_rec() as rec, mock.patch.object(rs, "datetime", nowf):
        rows = run(s.get_entity_history(r, "person"))
    assert [row_.detection_id for row_ in rows] == ["after-junk", "first"]
    assert rec.find("warning", "Skipping malformed") == (
        "Skipping malformed entity data in Redis key %s: expected dict, got %s",
        key_t,
        "str",
    )
    # a list sibling must NOT poison the healthy rows (isinstance guard)
    r2 = Redis({key_t: json.dumps({"persons": [stored_row("solo")]}), key_y: json.dumps([9])})
    with log_rec() as rec2, mock.patch.object(rs, "datetime", Now(NOW)):
        rows2 = run(s.get_entity_history(r2, "person"))
    assert [row_.detection_id for row_ in rows2] == ["solo"]
    assert rec2.find("error", "Failed to get entity history") is None


# =============================================================================
# singleton
# =============================================================================


def test_reset_then_get_recreates_the_service() -> None:
    reset_reid_service()
    with _settings_stub(), log_rec():
        a = get_reid_service()
        b = get_reid_service()
    assert a is b
    assert isinstance(a, ReIdentificationService)
    reset_reid_service()
    with _settings_stub(), log_rec():
        c = get_reid_service()
    assert isinstance(c, ReIdentificationService)
    assert c is not a
    reset_reid_service()


# =============================================================================
# format helpers — MESSAGE EQUALITY ONLY (fragments pass XX twins)
# =============================================================================


def _em(gap: float, sim: float, attrs: dict[str, Any] | None = None) -> EntityMatch:
    return EntityMatch(
        entity=entity(attributes=attrs or {}),
        similarity=sim,
        time_gap_seconds=gap,
    )


def test_format_entity_match_time_boundaries() -> None:
    assert format_entity_match(_em(0.5, 0.9)) == (
        "  - Camera: cam-7, Time: 0 seconds ago (similarity: 90%)"
    )
    assert "Time: 1 minutes ago" in format_entity_match(_em(60, 0.9))
    assert "Time: 1 minutes ago" in format_entity_match(_em(90, 0.9))
    assert "Time: 59 minutes ago" in format_entity_match(_em(3540, 0.9))
    assert "Time: 1.0 hours ago" in format_entity_match(_em(3600, 0.9))
    assert "Time: 1.0 hours ago" in format_entity_match(_em(3630, 0.9))
    assert "Time: 1.1 hours ago" in format_entity_match(_em(3780, 0.9))
    assert "Time: 2 seconds ago" in format_entity_match(_em(-2.9, 0.9))


def test_format_entity_match_full_lines_and_attributes_join() -> None:
    row = format_entity_match(
        _em(
            90,
            0.9125,
            {
                "clothing": "VQA>person wearing<loc_71><loc_86>blue jacket",
                "carrying": "<loc_10><loc_20>backpack",
                "color": "navy",
                "vehicle_type": "sedan",
            },
        )
    )
    assert row == (
        "  - Camera: cam-7, Time: 1 minutes ago (similarity: 91%)\n"
        "    Attributes: wearing blue jacket, carrying backpack, navy, sedan"
    )
    bare = format_entity_match(_em(90, 0.5, {"clothing": "", "color": None}))
    assert bare == "  - Camera: cam-7, Time: 1 minutes ago (similarity: 50%)"


def test_format_reid_context_count_cap_join_and_empties() -> None:
    ms = [_em(90, 0.9), _em(120, 0.8), _em(150, 0.7), _em(180, 0.6)]
    out = format_reid_context({"d-1": ms, "d-0": [], "d-2": [_em(60, 0.5)]})
    assert out == (
        "- [d-1] Seen 4 time(s) before:\n"
        "  - Camera: cam-7, Time: 1 minutes ago (similarity: 90%)\n"
        "  - Camera: cam-7, Time: 2 minutes ago (similarity: 80%)\n"
        "  - Camera: cam-7, Time: 2 minutes ago (similarity: 70%)\n"
        "- [d-2] Seen 1 time(s) before:\n"
        "  - Camera: cam-7, Time: 1 minutes ago (similarity: 50%)"
    )
    assert format_reid_context({}, "vehicle") == "No vehicle re-identification matches found."
    assert (
        format_reid_context({"d-1": []}, "person") == "No person re-identification matches found."
    )


def test_format_full_reid_context_sections_none_guard_and_join() -> None:
    out = format_full_reid_context({"d-1": [_em(90, 0.9)]}, {"v-1": [_em(120, 0.8)]})
    assert out == (
        "## Person Re-Identification\n"
        "- [d-1] Seen 1 time(s) before:\n"
        "  - Camera: cam-7, Time: 1 minutes ago (similarity: 90%)\n"
        "\n"
        "## Vehicle Re-Identification\n"
        "- [v-1] Seen 1 time(s) before:\n"
        "  - Camera: cam-7, Time: 2 minutes ago (similarity: 80%)"
    )
    assert format_full_reid_context(None, None) == "No entities matched with previous sightings."
    assert format_full_reid_context({"d-1": []}, {"v-1": []}) == (
        "No entities matched with previous sightings."
    )


def test_format_reid_summary_join_suffix_and_empty() -> None:
    assert format_reid_summary({"d-1": [_em(90, 0.9)]}, {}) == "1 person(s) seen before."
    assert format_reid_summary({"d-1": [_em(90, 0.9)]}, {"v-1": [_em(90, 0.9)]}) == (
        "1 person(s) seen before, 1 vehicle(s) seen before."
    )
    assert format_reid_summary({"d-1": [], "d-2": []}, {"v-1": []}) == (
        "All entities appear to be new (not seen in last 24h)."
    )
    assert format_reid_summary() == "All entities appear to be new (not seen in last 24h)."
