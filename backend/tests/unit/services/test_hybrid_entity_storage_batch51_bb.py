"""Campaign #51 (batch-51, battery BB) - `backend.services.hybrid_entity_storage`.

# TARGET-MODULE: backend.services.hybrid_entity_storage

The module sat at 183 survivors / 266 keys (31.2030% killed - the LOWEST-killed
head of the wave). The shipped test file drives the storage entry points
through AsyncMock twins and asserts RESULTS and bare `assert_called_once()`
awaits, but never the exact log message/args surface, never the FORWARDING
kwargs of the four awaited seams, never the dedup bookkeeping (`seen_ids` +
the `primary_detection_id` None-arms), never the ternary STRING legs, and
never the constructors' field-by-field mapping - so four families survived:

  * every log site (init line, Entity created/matched, Redis stored/failed,
    Found Redis / Found PostgreSQL / Total matches, Retrieved entity /
    Entity not found / Retrieved %d/%d) under the None / XX-wrap / lower /
    UPPER / DROP-argument arms (~95 keys),
  * every awaited seam's kwargs (clustering.assign_entity,
    reid.find_matching_entities, entity_repo.find_by_embedding, repo.list)
    under None-swap and DROP arms (~45 keys),
  * the EntityEmbedding the module builds inside store_detection_embedding
    (`str(detection_id)`, `attributes or {}`, `model_id or LEGACY_MODEL_ID`),
  * the two classmethod constructors' field mapping (embedding `or []`,
    metadata-absent "unknown", `str(pd) if pd else None`, `or {}`, the
    created/matched ternary, and the dedup `if`-guard arms.

Harness contract (b30 sweep, /home/agent/runs/b30-sweep.py): NO pytest
fixtures, NO parametrize, NO monkeypatch - the sweep imports this file
directly and calls every module-level ``test_*`` with zero arguments in ONE
process, flipping os.environ[MUTANT_UNDER_TEST] per key. Async entry points
are driven with asyncio.run INSIDE the test body. Every collaborator is a
FRESH in-body Spy twin handed in through the CONSTRUCTOR - no module-
attribute patching anywhere, so a mid-test assert failure cannot leak a patch
into the next key's window; the only global touch is the CollectorCtx
save/restore around hes.logger. No filesystem, no sleeps, no TZ dependence:
every datetime is tz-aware UTC.

KILL CONSTRUCTIONS (why each family bites its keys, not just its shipped run):

  * CollectorCtx + FULL CENSUS per drive: the drive's records are compared to
    a COMPLETE ordered list of (levelno, message, args) triples. Message
    EQUALITY kills XX/lower/UPPER; the args TUPLE kills None-swaps, drops and
    `str(e) -> str(None)` (a dropped arg shortens the tuple); whole-list
    equality kills any added or removed line. Never a substring or a
    level-only census (fragment-count is a documented survivor cause).
  * Every seam records (args, kwargs) and drives assert the FULL kwargs dict
    by EQUALITY (dropped-kwarg memory: an arg drop whose default equals the
    value is invisible downstream - only the call-site dict sees it), plus
    IDENTITY where an object is forwarded (storage.redis into both seams, the
    Entity row into `entity=`).
  * The EntityEmbedding captured from `store_embedding` is checked FIELD BY
    FIELD on BOTH legs: belt present ("m-77") and belt None -> LEGACY, so the
    `or`->`and` swap and the None/drop arms each diverge on at least one leg.
  * Ternary STRING arms (created/matched, "unknown", `str(pd) if pd else
    None`) are driven on BOTH polarities with the STRING asserted.
  * Dedup matrix over `seen_ids`: a PG row whose primary_detection_id matches
    a Redis detection_id is SKIPPED (kills the `not in` swap, the unconditional
    `add(None)`, and the `and False`/None-initializer arms); a FRESH row must
    survive (kills the `or True` arm, which skips every non-empty id); two
    primary_detection_id=None rows BOTH survive (kills `if pd or True`, which
    stringifies None to "None" and dedups the pair); two rows sharing one id
    COLLAPSE to one (kills `str(None) if pd else None`, which records the
    wrong id and keeps both).
  * Both constructors: full field capture on a fully-populated twin (belt
    leg + `entity is` identity + source + every value) plus the metadata-
    absent, vector-empty and belt-empty legs.

LEDGER CANDIDATE (pre-adjudicated, env-independent proof; disposition is
confirmed post-run by BODY identity - never by key number). ONE key:

  * from_redis_match - DROP of the `entity=None,` kwarg. `entity` is a plain
    dataclass field of HybridEntityMatch declared with a default of EXACTLY
    None (`entity: Entity | None = None`), so the mutant's omitted kwarg
    materializes the identical object: every field, the slots layout, and the
    dataclass __eq__ of the return value agree with shipped for every input.
    No environment separates the two, and the module never reads
    `match.source`-style provenance back off `entity` on the Redis path (the
    Redis branch never sets it - shipped writes None, the mutant omits it,
    the default answers None). Witness test below (the #48 from_config
    value-equal-default precedent). Every OTHER arm of that constructor
    family (the m1-m11 None-swaps, the model_id drop) changes a field VALUE
    and IS killed by the full-capture drive.

Key numbers cited in comments are the b51-era tree spellings from the live
meta (real key numbers, NOT diff line numbers - the b49 lesson); post-run
adjudication is BY BODY.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from backend.services import hybrid_entity_storage as hes

TS = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
SINCE = datetime(2026, 1, 8, 0, 0, 0, tzinfo=UTC)
EMB = [0.1, 0.2, 0.30000000000000004]
PG_ID = UUID("3f3f3f3f-3f3f-3f3f-3f3f-3f3f3f3f3f3f")
OTHER_ID = UUID("99999999-9999-9999-9999-999999999999")
HES_ID = UUID("11111111-2222-3333-4444-555555555555")
LEGACY = hes.LEGACY_MODEL_ID
DEBUG = logging.DEBUG
WARNING = logging.WARNING


# ---------------------------------------------------------------------------
# Harness helpers (b30-clean: no fixtures, no monkeypatch, no parametrize)
# ---------------------------------------------------------------------------


class LogCollector(logging.Handler):
    """Collects records off hes.logger (DEBUG level, propagation off)."""

    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class CollectorCtx:
    """hes.logger DEBUG sink with save/restore (leak-proof across keys)."""

    def __init__(self) -> None:
        self.collector = LogCollector()
        self._old_level = 0
        self._old_propagate = False

    def __enter__(self) -> LogCollector:
        self._old_level = hes.logger.level
        self._old_propagate = hes.logger.propagate
        hes.logger.addHandler(self.collector)
        hes.logger.setLevel(logging.DEBUG)
        hes.logger.propagate = False
        return self.collector

    def __exit__(self, *exc: Any) -> bool:
        hes.logger.removeHandler(self.collector)
        hes.logger.setLevel(self._old_level)
        hes.logger.propagate = self._old_propagate
        return False


def census(collector: LogCollector) -> list[tuple[int, Any, Any]]:
    """The full observable surface of a drive: (levelno, msg, args) in order."""
    return [(r.levelno, r.msg, r.args) for r in collector.records]


class Twin:
    """Attribute-only stand-in (the redis client handle, entity rows)."""

    def __init__(self, **over: Any) -> None:
        for key, value in over.items():
            setattr(self, key, value)


class Spy:
    """Awaitable-method recorder for the collaborator seams.

    Each awaited seam appends ``(args, kwargs)`` to ``.calls[name]`` and then
    answers with the canned return, or raises ``.raises[name]`` if set.
    """

    def __init__(
        self,
        returns: dict[str, Any] | None = None,
        raises: dict[str, Any] | None = None,
    ) -> None:
        self.calls: dict[str, list[tuple[tuple, dict]]] = {}
        self._returns = returns or {}
        self._raises = raises or {}

    def _fire(self, name: str, args: tuple, kwargs: dict) -> Any:
        self.calls.setdefault(name, []).append((args, kwargs))
        if name in self._raises:
            raise self._raises[name]
        return self._returns.get(name)


class ReidSpy(Spy):
    async def store_embedding(self, redis: Any, embedding: Any) -> None:
        self._fire("store_embedding", (redis, embedding), {})  # return is ignored by the module

    async def find_matching_entities(self, **kwargs: Any) -> Any:
        return self._fire("find_matching_entities", (), kwargs)


class RepoSpy(Spy):
    async def find_by_embedding(self, **kwargs: Any) -> Any:
        return self._fire("find_by_embedding", (), kwargs)

    async def get_by_id(self, entity_id: Any) -> Any:
        return self._fire("get_by_id", (entity_id,), {})

    async def list(self, **kwargs: Any) -> Any:
        return self._fire("list", (), kwargs)


class ClusterSpy(Spy):
    async def assign_entity(self, **kwargs: Any) -> Any:
        return self._fire("assign_entity", (), kwargs)


class Rig:
    """Storage plus its fresh twins, handed to drives as one bundle."""

    def __init__(
        self, returns: dict[str, Any] | None = None, raises: dict[str, Any] | None = None
    ) -> None:
        self.reid = ReidSpy(returns, raises)
        self.repo = RepoSpy(returns, raises)
        self.clustering = ClusterSpy(returns, raises)
        self.redis = Twin(handle="redis-handle")
        self.storage = hes.HybridEntityStorage(
            redis_client=self.redis,
            entity_repository=self.repo,
            clustering_service=self.clustering,
            reid_service=self.reid,
        )


def one(spy: Spy, name: str) -> tuple[tuple, dict]:
    calls = spy.calls.get(name, [])
    assert len(calls) == 1, f"{name}: expected exactly 1 call, got {len(calls)}"
    return calls[0]


def emb_twin(detection_id: str = "1001", **over: Any) -> Twin:
    """EntityEmbedding-shaped input (the Redis match's `.entity`)."""
    fields: dict[str, Any] = {
        "entity_type": "person",
        "embedding": EMB,
        "camera_id": "cam-a",
        "timestamp": TS,
        "detection_id": detection_id,
        "attributes": {"color": "blue"},
        "model_id": "m-77",
    }
    fields.update(over)
    return Twin(**fields)


def match_twin(detection_id: str = "1001", similarity: float = 0.91, **over: Any) -> Twin:
    return Twin(entity=emb_twin(detection_id), similarity=similarity, time_gap_seconds=1.5, **over)


def pg_twin(primary_detection_id: int | None = 2002, **over: Any) -> Twin:
    """Entity-row twin (find_by_embedding rows / from_postgresql_match)."""
    fields: dict[str, Any] = {
        "id": PG_ID,
        "entity_type": "person",
        "entity_metadata": {"camera_id": "cam-pg", "extra": 1},
        "last_seen_at": TS,
        "primary_detection_id": primary_detection_id,
        "detection_count": 3,
    }
    fields.update(over)
    twin = Twin(**fields)
    twin.get_embedding_vector = lambda: [0.5, 0.5]
    twin.get_embedding_model = lambda: "m-pg"
    return twin


def run(coro: Any) -> Any:
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# __init__ - survivors m5..m8 (logger.debug None / XX / lower / UPPER)
# ---------------------------------------------------------------------------


def test_init_logs_the_init_line_exactly() -> None:
    rig = Rig()
    # Construction happens INSIDE the window: the init line is the whole
    # census, so a None'd/XX/case-flipped message or a dropped line dies.
    with CollectorCtx() as collector:
        storage = hes.HybridEntityStorage(rig.redis, rig.repo, rig.clustering, rig.reid)
    assert census(collector) == [(DEBUG, "HybridEntityStorage initialized", ())]
    assert storage.redis is rig.redis
    assert storage.entity_repo is rig.repo
    assert storage.clustering is rig.clustering
    assert storage.reid is rig.reid


# ---------------------------------------------------------------------------
# HybridEntityMatch.from_redis_match - survivors m1..m11 (field -> None),
# m22 (DROP entity=  -> LEDGER, value-equal default), m23 (DROP model_id=)
# ---------------------------------------------------------------------------


def test_from_redis_match_captures_every_field() -> None:
    match = match_twin(detection_id="1001", similarity=0.91)
    got = hes.HybridEntityMatch.from_redis_match(match)
    assert got.entity_id == "1001"
    assert got.entity_type == "person"
    assert got.embedding == EMB
    assert got.camera_id == "cam-a"
    assert got.timestamp is TS
    assert got.detection_id == "1001"
    assert got.attributes == {"color": "blue"}
    assert got.similarity == 0.91
    assert got.time_gap_seconds == 1.5
    assert got.source == "redis"
    assert got.entity is None
    # m23 (DROP of model_id=) lands on the dataclass default (the sentinel)
    # where shipped carries the incoming belt - the exact-belt leg kills it.
    assert got.model_id == "m-77"


def test_from_redis_match_second_belt_and_ids() -> None:
    # A second, DIFFERENT-value drive: every field -> None arm has to fail on
    # at least one input, and distinct values stop a swapped pair cancelling.
    match = match_twin(detection_id="det-9", similarity=0.125)
    match.entity.camera_id = "cam-z"
    match.entity.model_id = LEGACY
    match.time_gap_seconds = -2.25
    got = hes.HybridEntityMatch.from_redis_match(match)
    assert (got.entity_id, got.detection_id) == ("det-9", "det-9")
    assert (got.camera_id, got.model_id, got.similarity) == ("cam-z", LEGACY, 0.125)
    assert got.time_gap_seconds == -2.25
    assert got.embedding == EMB and got.attributes == {"color": "blue"}


def test_from_redis_match_dropped_entity_is_the_default_rebuild() -> None:
    """LEDGER WITNESS (from_redis_match, DROP of `entity=None,`): shipped's
    output EQUALS the entity-kwarg-omitted rebuild, because the field's own
    default IS None. This passes under the mutant too - it DOCUMENTS the
    equivalence, it does not kill it."""
    match = match_twin(detection_id="1001", similarity=0.91)
    shipped = hes.HybridEntityMatch.from_redis_match(match)
    rebuilt = hes.HybridEntityMatch(
        entity_id=shipped.entity_id,
        entity_type=shipped.entity_type,
        embedding=shipped.embedding,
        camera_id=shipped.camera_id,
        timestamp=shipped.timestamp,
        detection_id=shipped.detection_id,
        attributes=shipped.attributes,
        similarity=shipped.similarity,
        time_gap_seconds=shipped.time_gap_seconds,
        source=shipped.source,
        # `entity` deliberately omitted: its default is the dropped value.
        model_id=shipped.model_id,
    )
    assert shipped == rebuilt
    assert shipped.entity is rebuilt.entity is None


# ---------------------------------------------------------------------------
# HybridEntityMatch.from_postgresql_match - survivors m1..m9/m11 (field ->
# None), m23 (DROP entity=), m25 (`or []` -> `and []`), m26/m27 ("unknown"
# XX/CASE), m28..m30 (str(pd) if pd arms), m31 (`or {}` -> `and {}`)
# ---------------------------------------------------------------------------


def test_from_postgresql_match_captures_every_field() -> None:
    row = pg_twin(primary_detection_id=2002)
    got = hes.HybridEntityMatch.from_postgresql_match(row, similarity=0.42, time_gap_seconds=7.5)
    assert got.entity_id == PG_ID
    assert got.entity_type == "person"
    assert got.embedding == [0.5, 0.5]
    assert got.camera_id == "cam-pg"
    assert got.timestamp is TS
    assert got.detection_id == "2002"
    assert got.attributes == {"camera_id": "cam-pg", "extra": 1}
    assert got.similarity == 0.42
    assert got.time_gap_seconds == 7.5
    assert got.source == "postgresql"
    assert got.entity is row  # kills m11 (entity -> None) and m23 (DROP)
    assert got.model_id == "m-pg"


def test_from_postgresql_match_metadata_absent_leg() -> None:
    row = pg_twin(primary_detection_id=None, entity_metadata=None)
    row.get_embedding_model = lambda: ""  # empty belt -> the sentinel
    got = hes.HybridEntityMatch.from_postgresql_match(row, similarity=0.5)
    assert got.camera_id == "unknown"  # m26 XX / m27 UPPER die on EQUALITY
    assert got.attributes == {}  # `entity_metadata or {}` falsy leg (m7/m31)
    assert got.detection_id is None  # the falsy leg of str(pd) if pd (m6/m28/m29/m30)
    assert got.model_id == LEGACY


def test_from_postgresql_match_vector_and_belt_legs() -> None:
    # Both legs of `get_embedding_vector() or []`: the TRUTHY leg is the one
    # `and []` breaks, so it must be driven too (inclusive-boundary lesson).
    empty = pg_twin(primary_detection_id=9)
    empty.get_embedding_vector = lambda: []
    got_empty = hes.HybridEntityMatch.from_postgresql_match(empty, similarity=0.25)
    assert got_empty.embedding == []

    full = pg_twin(primary_detection_id=9)
    got_full = hes.HybridEntityMatch.from_postgresql_match(full, similarity=0.25)
    assert got_full.embedding == [0.5, 0.5]
    assert got_full.model_id == "m-pg"
    assert got_full.detection_id == "9"


def test_from_postgresql_match_metadata_without_camera_key() -> None:
    # The `.get("camera_id", "unknown")` DEFAULT arm: metadata present but no
    # camera key must still read "unknown" (a swapped default would not).
    row = pg_twin(primary_detection_id=None, entity_metadata={"extra": 1})
    got = hes.HybridEntityMatch.from_postgresql_match(row, similarity=0.1)
    assert got.camera_id == "unknown"
    assert got.attributes == {"extra": 1}


# ---------------------------------------------------------------------------
# store_detection_embedding - survivors m2, m4..m15 (assign kwargs),
# m16..m32 (Entity-census + created/matched strings), m37/m38/m40/m47/m48/m50
# (EntityEmbedding fields), m51 (redis handle), m55..m71 (stored/failed lines)
# ---------------------------------------------------------------------------

STORE_ARGS: dict[str, Any] = {
    "detection_id": 7,
    "entity_type": "person",
    "embedding": EMB,
    "camera_id": "cam-7",
    "timestamp": TS,
    "attributes": {"color": "blue"},
    "model_id": "m-77",
}


def store_args(**over: Any) -> dict[str, Any]:
    merged = dict(STORE_ARGS)
    merged.update(over)
    return merged


def test_store_forwards_exact_assign_kwargs() -> None:
    rig = Rig(returns={"assign_entity": (Twin(id=HES_ID), True, 0.42)})
    run(rig.storage.store_detection_embedding(**store_args()))
    args, kwargs = one(rig.clustering, "assign_entity")
    assert args == ()
    assert kwargs == STORE_ARGS  # every None-swap / DROP arm of m2..m15 dies


def test_store_success_census_and_return() -> None:
    rig = Rig(returns={"assign_entity": (Twin(id=HES_ID), True, 0.42)})
    with CollectorCtx() as collector:
        out = run(rig.storage.store_detection_embedding(**store_args()))
    assert out == (HES_ID, True)
    assert census(collector) == [
        (DEBUG, "Entity %s for detection %d (is_new=%s)", ("created", 7, True)),
        (DEBUG, "Stored embedding in Redis for detection %d", (7,)),
    ]


def test_store_matched_ternary_leg() -> None:
    # m27..m32: the and/or swaps and the XX/CASE arms on created/matched are
    # only visible on the FALSE leg with the STRING asserted.
    rig = Rig(returns={"assign_entity": (Twin(id=HES_ID), False, 0.3)})
    with CollectorCtx() as collector:
        out = run(rig.storage.store_detection_embedding(**store_args(detection_id=8)))
    assert out == (HES_ID, False)
    assert census(collector) == [
        (DEBUG, "Entity %s for detection %d (is_new=%s)", ("matched", 8, False)),
        (DEBUG, "Stored embedding in Redis for detection %d", (8,)),
    ]


def test_store_builds_entity_embedding_field_by_field() -> None:
    rig = Rig(returns={"assign_entity": (Twin(id=HES_ID), True, 0.42)})
    run(rig.storage.store_detection_embedding(**store_args()))
    args, kwargs = one(rig.reid, "store_embedding")
    assert kwargs == {}
    redis_arg, entity_embedding = args
    assert redis_arg is rig.storage.redis  # m51 (redis handle -> None)
    assert entity_embedding.entity_type == "person"
    assert entity_embedding.embedding == EMB
    assert entity_embedding.camera_id == "cam-7"
    assert entity_embedding.timestamp is TS
    assert entity_embedding.detection_id == "7"  # m38 None / m48 str(None)
    assert entity_embedding.attributes == {"color": "blue"}
    assert entity_embedding.model_id == "m-77"  # m40 None / m47 DROP / m50 `and`


def test_store_null_legs_attributes_and_belt() -> None:
    # The falsy legs: attributes None -> {} in the EMBEDDING but the RAW
    # None into assign_entity; model_id None -> the sentinel in the
    # embedding, raw None downstream. `or` -> `and` diverges right here.
    rig = Rig(returns={"assign_entity": (Twin(id=HES_ID), False, 0.3)})
    run(rig.storage.store_detection_embedding(**store_args(attributes=None, model_id=None)))
    args, _ = one(rig.reid, "store_embedding")
    entity_embedding = args[1]
    assert entity_embedding.attributes == {}
    assert entity_embedding.model_id == LEGACY
    _, assign_kwargs = one(rig.clustering, "assign_entity")
    assert assign_kwargs["attributes"] is None
    assert assign_kwargs["model_id"] is None


def test_store_redis_failure_warns_and_succeeds() -> None:
    rig = Rig(
        returns={"assign_entity": (Twin(id=HES_ID), True, 0.42)},
        raises={"store_embedding": RuntimeError("redis-down")},
    )
    with CollectorCtx() as collector:
        out = run(rig.storage.store_detection_embedding(**store_args()))
    assert out == (HES_ID, True)  # the Redis failure must NOT bubble
    assert census(collector) == [
        (DEBUG, "Entity %s for detection %d (is_new=%s)", ("created", 7, True)),
        (WARNING, "Failed to store embedding in Redis for detection %d: %s", (7, "redis-down")),
    ]  # m62..m70 (msg/args arms) + m71 (str(e) -> str(None)) die here


# ---------------------------------------------------------------------------
# find_matches - survivors m4..m15 (redis kwargs), m18 (seen add), m20..m30
# (redis line), m31..m38 (redis-failure line), m40..m50 (pg kwargs/limit),
# m51..m56 (dedup arms), m63..m73 (pg line), m80..m88 (total line)
# ---------------------------------------------------------------------------

FIND_ARGS: dict[str, Any] = {
    "embedding": EMB,
    "entity_type": "person",
    "threshold": 0.85,
    "exclude_detection_id": "det-excl-77",
    "include_historical": True,
    "model_id": "m-77",
}


def find_args(**over: Any) -> dict[str, Any]:
    merged = dict(FIND_ARGS)
    merged.update(over)
    return merged


def test_find_matches_forwards_exact_seam_kwargs() -> None:
    rig = Rig(returns={"find_matching_entities": [], "find_by_embedding": []})
    with CollectorCtx():
        assert run(rig.storage.find_matches(**find_args())) == []
    args, redis_kwargs = one(rig.reid, "find_matching_entities")
    assert args == ()
    assert redis_kwargs == {
        "redis_client": rig.storage.redis,
        "embedding": EMB,
        "entity_type": "person",
        "threshold": 0.85,
        "exclude_detection_id": "det-excl-77",
        "model_id": "m-77",
    }  # kills m4..m12 and the m15 DROP (identity pins the client object)
    args2, pg_kwargs = one(rig.repo, "find_by_embedding")
    assert args2 == ()
    assert pg_kwargs == {
        "embedding": EMB,
        "entity_type": "person",
        "threshold": 0.85,
        "limit": 50,  # the m50 `limit=51` arm dies on this exact value
        "model_id": "m-77",
    }


def test_find_matches_historical_off_never_touches_repo() -> None:
    rig = Rig(returns={"find_matching_entities": []})
    with CollectorCtx() as collector:
        assert run(rig.storage.find_matches(**find_args(include_historical=False))) == []
    assert rig.repo.calls.get("find_by_embedding", []) == []
    assert census(collector) == [
        (DEBUG, "Found %d Redis matches for %s (threshold=%.2f)", (0, "person", 0.85)),
        (DEBUG, "Total matches for %s: %d (Redis + PostgreSQL)", ("person", 0)),
    ]  # no PostgreSQL line - a mutant that always queries would add one


def test_find_matches_success_census_three_lines() -> None:
    rig = Rig(
        returns={
            "find_matching_entities": [match_twin(detection_id="1001", similarity=0.91)],
            "find_by_embedding": [(pg_twin(primary_detection_id=2002), 0.55)],
        }
    )
    with CollectorCtx() as collector:
        out = run(rig.storage.find_matches(**find_args()))
    assert [m.similarity for m in out] == [0.91, 0.55]  # sorted DESC
    assert [m.source for m in out] == ["redis", "postgresql"]
    assert census(collector) == [
        (DEBUG, "Found %d Redis matches for %s (threshold=%.2f)", (1, "person", 0.85)),
        (DEBUG, "Found %d PostgreSQL matches for %s (threshold=%.2f)", (1, "person", 0.85)),
        (DEBUG, "Total matches for %s: %d (Redis + PostgreSQL)", ("person", 2)),
    ]  # every m20..m30 / m63..m73 / m80..m88 None, XX, case and DROP arm dies


def test_find_matches_redis_failure_census() -> None:
    rig = Rig(
        raises={"find_matching_entities": RuntimeError("redis-down")},
        returns={"find_by_embedding": [(pg_twin(primary_detection_id=2002), 0.55)]},
    )
    with CollectorCtx() as collector:
        out = run(rig.storage.find_matches(**find_args()))
    assert [m.source for m in out] == ["postgresql"]
    assert census(collector) == [
        (WARNING, "Redis lookup failed, falling back to PostgreSQL only: %s", ("redis-down",)),
        (DEBUG, "Found %d PostgreSQL matches for %s (threshold=%.2f)", (1, "person", 0.85)),
        (DEBUG, "Total matches for %s: %d (Redis + PostgreSQL)", ("person", 1)),
    ]  # m31..m37 arms and m38 (str(e) -> str(None)) die on the tuple value


def test_find_matches_dedups_pg_against_a_redis_detection() -> None:
    # Redis already carries detection 1001, so the PostgreSQL row whose
    # primary_detection_id is 1001 must be SKIPPED: that needs seen to hold
    # exactly {"1001"} (kills the m56 `not in` swap, the m18 unconditional
    # add(None), the m52 `and False` and the m51/m54 None-initializers).
    rig = Rig(
        returns={
            "find_matching_entities": [match_twin(detection_id="1001", similarity=0.91)],
            "find_by_embedding": [(pg_twin(primary_detection_id=1001), 0.55)],
        }
    )
    with CollectorCtx() as collector:
        out = run(rig.storage.find_matches(**find_args()))
    assert [m.source for m in out] == ["redis"]
    assert census(collector)[2] == (
        DEBUG,
        "Total matches for %s: %d (Redis + PostgreSQL)",
        ("person", 1),
    )


def test_find_matches_fresh_pg_row_survives() -> None:
    # m55 (`eid or eid in seen` -> always true for a non-empty id) skips this
    # never-seen row, so it dies on a KEEP.
    rig = Rig(returns={"find_matching_entities": [], "find_by_embedding": [(pg_twin(2002), 0.55)]})
    out = run(rig.storage.find_matches(**find_args()))
    assert [m.source for m in out] == ["postgresql"]
    assert out[0].entity_id == PG_ID


def test_find_matches_two_null_id_rows_both_survive() -> None:
    # m53 (`if pd or True`): the mutant stringifies None to "None", records
    # it in seen and DROPS the second null row. Shipped dedups nothing for a
    # null primary_detection_id.
    first = pg_twin(None)
    second = pg_twin(None, id=OTHER_ID)
    rig = Rig(
        returns={"find_matching_entities": [], "find_by_embedding": [(first, 0.7), (second, 0.6)]}
    )
    out = run(rig.storage.find_matches(**find_args()))
    assert [m.entity_id for m in out] == [PG_ID, OTHER_ID]


def test_find_matches_two_rows_sharing_one_id_collapse() -> None:
    # m54 (`str(None) if pd else None`): the mutant records the WRONG id
    # ("None") and therefore keeps both rows; shipped keeps the first only.
    first = pg_twin(2002)
    second = pg_twin(2002, id=OTHER_ID)
    rig = Rig(
        returns={"find_matching_entities": [], "find_by_embedding": [(first, 0.7), (second, 0.6)]}
    )
    out = run(rig.storage.find_matches(**find_args()))
    assert [m.entity_id for m in out] == [PG_ID]


def test_find_matches_null_pg_row_keeps_none_detection() -> None:
    # The m18 witness leg: a null-id row enters without poisoning `seen`
    # (shipped adds nothing for it, so a later row's outcome is unchanged).
    row = pg_twin(None)
    rig = Rig(returns={"find_matching_entities": [], "find_by_embedding": [(row, 0.5)]})
    out = run(rig.storage.find_matches(**find_args()))
    assert out[0].detection_id is None
    assert out[0].entity is row


# ---------------------------------------------------------------------------
# get_entity_full_history - survivors m3..m11 (found line) and m12..m18
# (not-found line)
# ---------------------------------------------------------------------------


def test_history_found_line_and_lookup_are_exact() -> None:
    entity = pg_twin(10, detection_count=12)
    rig = Rig(returns={"get_by_id": entity})
    with CollectorCtx() as collector:
        assert run(rig.storage.get_entity_full_history(HES_ID)) is entity
    assert one(rig.repo, "get_by_id") == ((HES_ID,), {})
    assert census(collector) == [(DEBUG, "Retrieved entity %s with %d detections", (HES_ID, 12))]


def test_history_missing_line_is_exact() -> None:
    rig = Rig(returns={"get_by_id": None})
    with CollectorCtx() as collector:
        assert run(rig.storage.get_entity_full_history(HES_ID)) is None
    # m12 (msg -> None) / m13, m15 (id -> None / DROP) / m14 (args collapse)
    # / m16..m18 (XX, lower, UPPER) all die on this one tuple.
    assert census(collector) == [(DEBUG, "Entity %s not found", (HES_ID,))]


# ---------------------------------------------------------------------------
# get_entities_by_timerange - survivors m2/m3 (kwargs -> None), m6/m7
# (kwargs DROP), m10..m22 (the Retrieved %d/%d line)
# ---------------------------------------------------------------------------


def test_timerange_forwards_kwargs_and_logs_exact() -> None:
    first, second = pg_twin(1), pg_twin(2)
    rig = Rig(returns={"list": ([first, second], 7)})
    with CollectorCtx() as collector:
        out = run(
            rig.storage.get_entities_by_timerange(
                entity_type="person", since=SINCE, limit=20, offset=5
            )
        )
    assert out == ([first, second], 7)
    args, kwargs = one(rig.repo, "list")
    assert args == ()
    assert kwargs == {"entity_type": "person", "since": SINCE, "limit": 20, "offset": 5}
    assert census(collector) == [
        (DEBUG, "Retrieved %d/%d entities (type=%s, since=%s)", (2, 7, "person", SINCE))
    ]


def test_timerange_default_legs_forward_verbatim() -> None:
    # The None-default legs: the defaults must ride into repo.list AND into
    # the log args. A DROP arm (m6/m7) loses the key from the recorded dict;
    # the None-swap of m2/m3 is only killable with a NON-None value (driven
    # in the test above) - this leg pins the complementary path.
    rig = Rig(returns={"list": ([], 0)})
    with CollectorCtx() as collector:
        assert run(rig.storage.get_entities_by_timerange()) == ([], 0)
    _, kwargs = one(rig.repo, "list")
    assert kwargs == {"entity_type": None, "since": None, "limit": 50, "offset": 0}
    assert census(collector) == [
        (DEBUG, "Retrieved %d/%d entities (type=%s, since=%s)", (0, 0, None, None))
    ]
