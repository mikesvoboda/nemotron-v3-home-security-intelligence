# TARGET-MODULE: backend.api.routes.gpu_config
"""Battery AS — campaign #43 kill battery for backend/api/routes/gpu_config.py.

Style (proven on AQ/AR): every observable the entered branch WRITES is
asserted, not merely "reached" (see [[entered-branch-must-assert-every-
observable-it-writes]]).

- DB helpers: a recording Session whose pins are the FULL normalized
  statement STRING + compiled PARAMS dict per execute (AQ capture:
  .where(None) COMPILES to 'WHERE NULL', select(None) -> 'SELECT NULL AS
  anon_1', func.max(None) -> 'max(NULL)', a None statement RAISES TypeError
  mirroring SQLAlchemy "query expected").  Results are consumed
  POSITIONALLY — a skipped/duplicated execute surfaces as IndexError.
- ORM write paths: added objects pinned FIELD-BY-FIELD against non-default
  values — a dropped / =None ctor kwarg on an unflushed SQLAlchemy model
  reads back None (measured), and where a column default EQUALS the shipped
  value (enabled=True) the UPDATE-branch twin is pinned from a flipped
  starting value instead ([[helper-none-default-hides-none-polarity...]]).
- Redis helpers: fake recording ("get", key) / ("set", key, value, expire) /
  ("delete", *keys) with per-method failure injection; the module-global
  fallback dict pinned per-key with identity-asserted booleans
  (is True / is False kills =None twins), restored in finally.
- Logging: module logs via plain f-strings (NOT extra=), recorder stores
  (method, args, kwargs), FULL tuple equality — rename/XX/UPPER/lower
  message twins die ([[fragment-count-asserts-pass-xx-mutants]]).
- _calculate_auto_assignments: GpuAssignment is pydantic with
  vram_budget_override: float | None = None — an explicit None kwarg is
  UNOBSERVABLE on the value but OBSERVABLE via model_fields_set (measured),
  so every constructed assignment carries a fields_set pin killing the x6
  drop family.  Sorted output order IS the observable for the x2
  key=sorted(...) families; the 0->1 miss-default flip needs a service
  ABSENT from the table ordered AFTER a service worth exactly 0 MB
  (stable-sort tie breaks by input order — measured).
- GpuDevice.vram_available_mb is a COMPUTED property (total - used —
  measured), so expected values derive from the ctor numbers.
- BIRTH extension (post-run-1: the battery newly covered 73 keys, 11
  survived).  The AI_SERVICE_VRAM_REQUIREMENTS_MB miss-default trio (0 ->
  1 / None / trailing-comma) needs an absent service ACCUMULATED with a
  present one landing EXACTLY on capacity: shipped silent, default-1 tips
  the overage, None / trailing-comma (both miss -> None) raise TypeError
  on `usage += None` (measured).  The VRAM fallback max(sorted_gpus, key=
  ...) trio only raises / diverges with >=2 GPUs and a PRIOR successful
  assignment skewing gpu_remaining (a pure fallback keeps remaining ==
  totals so max-by-remaining agrees with first-element) — measured.
  GpuDevice is an UNORDERED dataclass, so max(sorted_gpus, ) / key=None
  RAISES once a real comparison happens.  The joiner and == -> != affinity
  twins need 2+ co-tenants (single co-tenant join is separator-blind) and a
  THIRD unrelated one (the self-match and shipped-match strings are BYTE-
  IDENTICAL, so only the COUNT differs — [[fragment-count-asserts-pass-xx-
  mutants]]).
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any
from unittest import mock

import backend.api.routes.gpu_config as gc
from backend.api.schemas.gpu_config import GpuAssignment, GpuAssignmentStrategy
from backend.models.gpu_config import (
    GpuConfiguration,
    GpuConfigurationVersion,
    SystemSetting,
)
from backend.models.gpu_config import (
    GpuDevice as GpuDeviceModel,
)
from backend.services.gpu_detection_service import GpuDevice

# ============================================================================
# Measured constants
# ============================================================================

OPS_KEY = "gpu_config:current_operation_id"
STRAT_KEY = "gpu_assignment_strategy"
NO_GPU_MSG = "No GPUs detected - cannot calculate auto-assignments"
SOLO_MSG = "Only one GPU detected - isolation strategy not possible, all services assigned to GPU 0"

STRAT_SELECT = (
    "SELECT system_settings.key, system_settings.value, system_settings.updated_at "
    "FROM system_settings WHERE system_settings.key = :key_1"
)
# One exact-shape pin per query site: every is_/None/kwarg mutant COMPILES to
# a DIFFERENT string (measured: 'IS false', 'IS NULL', 'WHERE NULL',
# 'SELECT NULL AS anon_1', '!= :key_1'), so full equality on the shipped
# string kills the whole family at that site — no per-mutant strings needed.
CFG_BASE = (
    "SELECT gpu_configurations.id, gpu_configurations.service_name, "
    "gpu_configurations.gpu_index, gpu_configurations.strategy, "
    "gpu_configurations.vram_budget_override, gpu_configurations.enabled, "
    "gpu_configurations.exclusive_gpu, gpu_configurations.priority_weight, "
    "gpu_configurations.incompatible_with, gpu_configurations.created_at, "
    "gpu_configurations.updated_at FROM gpu_configurations"
)
CFG_SELECT_TRUE = CFG_BASE + " WHERE gpu_configurations.enabled IS true"
DEV_SELECT = (
    "SELECT gpu_devices.id, gpu_devices.gpu_index, gpu_devices.name, "
    "gpu_devices.vram_total_mb, gpu_devices.vram_available_mb, "
    "gpu_devices.compute_capability, gpu_devices.last_seen_at FROM gpu_devices"
)
UPDT_SELECT = "SELECT max(gpu_configurations.updated_at) AS max_1 FROM gpu_configurations"
NEXTV_SELECT = (
    "SELECT max(gpu_configuration_versions.version_number) AS max_1 FROM gpu_configuration_versions"
)

VRAM_TABLE = {"big": 200, "small": 60, "tiny": 0}


def norm(stmt: Any) -> str:
    return " ".join(str(stmt).split())


# ============================================================================
# Fakes
# ============================================================================


class Result:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def scalar_one_or_none(self) -> Any:
        return self._payload

    def scalars(self) -> Result:
        return self

    def all(self) -> list[Any]:
        return list(self._payload)


class Session:
    """Mirrors AsyncSession.execute: a None statement RAISES (SQLAlchemy
    'query expected' ArgumentError); every accepted statement pins as
    (normalized-string, compiled-params); results POSITIONAL."""

    def __init__(self, results: list[Any] | None = None) -> None:
        self.results = list(results or [])
        self.queries: list[tuple[str, dict[str, Any]]] = []
        self.added: list[Any] = []

    async def execute(self, query: Any) -> Result:
        if query is None:
            raise TypeError("query expected")
        stmt = query
        self.queries.append((norm(stmt), dict(stmt.compile().params)))
        if not self.results:
            raise IndexError("unexpected execute — shipped issues no further queries")
        return Result(self.results.pop(0))

    def add(self, obj: Any) -> None:
        self.added.append(obj)


class Rec:
    """f-string logger: pins (method, args, kwargs) with FULL tuple equality."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def debug(self, *args: Any, **kw: Any) -> None:
        self.calls.append(("debug", args, kw))

    def info(self, *args: Any, **kw: Any) -> None:
        self.calls.append(("info", args, kw))

    def warning(self, *args: Any, **kw: Any) -> None:
        self.calls.append(("warning", args, kw))

    def error(self, *args: Any, **kw: Any) -> None:
        self.calls.append(("error", args, kw))


@contextmanager
def log_rec():
    rec = Rec()
    with mock.patch.object(gc, "logger", rec):
        yield rec


class Redis:
    def __init__(
        self,
        *,
        get_exc: Exception | None = None,
        set_exc: Exception | None = None,
        delete_exc: Exception | None = None,
    ) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.get_exc = get_exc
        self.set_exc = set_exc
        self.delete_exc = delete_exc

    async def get(self, key: str) -> Any:
        self.calls.append(("get", key))
        if self.get_exc is not None:
            raise self.get_exc
        return "op-get"

    async def set(
        self, key: str, value: Any, expire: int | None = None, *, nx: bool = False
    ) -> bool:
        self.calls.append(("set", key, value, expire))
        if self.set_exc is not None:
            raise self.set_exc
        return True

    async def delete(self, *keys: str) -> int:
        self.calls.append(("delete", *keys))
        if self.delete_exc is not None:
            raise self.delete_exc
        return 1


def dev(index: int, vram_total: int, cc: str | None = None, vram_used: int = 0) -> GpuDevice:
    return GpuDevice(
        index=index,
        name=f"gpu-{index}",
        vram_total_mb=vram_total,
        vram_used_mb=vram_used,
        uuid=f"u{index}",
        compute_capability=cc,
    )


def cfg_row(service: str, **kw: Any) -> GpuConfiguration:
    c = GpuConfiguration(service_name=service)
    c.gpu_index = kw.get("gpu_index", 3)
    c.strategy = kw.get("strategy", "stale")
    c.vram_budget_override = kw.get("vram_budget_override", 1.5)
    c.enabled = kw.get("enabled", False)
    c.exclusive_gpu = kw.get("exclusive_gpu", True)
    c.priority_weight = kw.get("priority_weight", 7)
    c.incompatible_with = kw.get("incompatible_with", ["stale"])
    return c


def asg(
    service: str,
    gpu_index: int | None = 0,
    override: float | None = None,
    exclusive: bool = False,
    weight: int = 50,
    incompatible: list[str] | None = None,
) -> GpuAssignment:
    return GpuAssignment(
        service=service,
        gpu_index=gpu_index,
        vram_budget_override=override,
        exclusive_gpu=exclusive,
        priority_weight=weight,
        incompatible_with=incompatible,
    )


def assert_explicit_none_overrides(assignments: list[GpuAssignment]) -> None:
    for x in assignments:
        assert "vram_budget_override" in x.model_fields_set
        assert x.vram_budget_override is None


# ============================================================================
# Redis operation-id helpers
# ============================================================================


async def test_get_operation_id_reads_pinned_key() -> None:
    r = Redis()
    assert await gc._get_current_operation_id(r) == "op-get"
    assert r.calls == [("get", OPS_KEY)]


async def test_get_operation_id_falls_back_when_no_redis() -> None:
    gc._apply_state_fallback["operation_id"] = "fb-op"
    try:
        assert await gc._get_current_operation_id(None) == "fb-op"
    finally:
        gc._apply_state_fallback["operation_id"] = None


async def test_get_operation_id_swallows_error_with_pinned_warning() -> None:
    r = Redis(get_exc=ValueError("boom"))
    with log_rec() as rec:
        assert await gc._get_current_operation_id(r) is None
    assert r.calls == [("get", OPS_KEY)]
    assert rec.calls == [("warning", ("Failed to get current operation ID from Redis: boom",), {})]


async def test_set_operation_id_redis_set_pins_ttl() -> None:
    r = Redis()
    await gc._set_current_operation_id(r, "op-9")
    assert r.calls == [("set", OPS_KEY, "op-9", 3600)]


async def test_set_operation_id_redis_clear_pins_delete() -> None:
    r = Redis()
    await gc._set_current_operation_id(r, None)
    assert r.calls == [("delete", OPS_KEY)]


async def test_set_operation_id_set_failure_warns_pinned() -> None:
    r = Redis(set_exc=OSError("down"))
    with log_rec() as rec:
        await gc._set_current_operation_id(r, "op-x")
    assert rec.calls == [("warning", ("Failed to set current operation ID in Redis: down",), {})]


async def test_set_operation_id_no_redis_writes_both_fallback_keys() -> None:
    try:
        await gc._set_current_operation_id(None, "op-f")
        assert gc._apply_state_fallback["operation_id"] == "op-f"
        assert gc._apply_state_fallback["in_progress"] is True
        await gc._set_current_operation_id(None, None)
        assert gc._apply_state_fallback["operation_id"] is None
        assert gc._apply_state_fallback["in_progress"] is False
    finally:
        gc._apply_state_fallback["operation_id"] = None
        gc._apply_state_fallback["in_progress"] = False


# ============================================================================
# Strategy persistence helpers
# ============================================================================


async def test_get_current_strategy_found_maps_enum_and_pins_query() -> None:
    setting = SystemSetting(key=STRAT_KEY, value={"strategy": "balanced"})
    s = Session([setting])
    assert await gc._get_current_strategy(s) is GpuAssignmentStrategy.BALANCED
    assert s.queries == [(STRAT_SELECT, {"key_1": STRAT_KEY})]


async def test_get_current_strategy_invalid_value_warns_and_defaults() -> None:
    setting = SystemSetting(key=STRAT_KEY, value={"strategy": "no-such"})
    s = Session([setting])
    with log_rec() as rec:
        assert await gc._get_current_strategy(s) is GpuAssignmentStrategy.MANUAL
    assert s.queries == [(STRAT_SELECT, {"key_1": STRAT_KEY})]
    assert rec.calls == [("warning", ("Invalid strategy value in settings: no-such",), {})]


async def test_get_current_strategy_missing_inner_key_defaults_quietly() -> None:
    setting = SystemSetting(key=STRAT_KEY, value={"other": 1})
    s = Session([setting])
    with log_rec() as rec:
        assert await gc._get_current_strategy(s) is GpuAssignmentStrategy.MANUAL
    assert rec.calls == []


async def test_get_current_strategy_absent_setting_defaults_quietly() -> None:
    s = Session([None])
    with log_rec() as rec:
        assert await gc._get_current_strategy(s) is GpuAssignmentStrategy.MANUAL
    assert rec.calls == []
    assert s.queries == [(STRAT_SELECT, {"key_1": STRAT_KEY})]


async def test_set_current_strategy_existing_replaces_value_wholesale() -> None:
    setting = SystemSetting(key=STRAT_KEY, value={"strategy": "manual", "junk": 2})
    s = Session([setting])
    await gc._set_current_strategy(s, GpuAssignmentStrategy.VRAM_BASED)
    assert setting.value == {"strategy": "vram_based"}
    assert s.added == []
    assert s.queries == [(STRAT_SELECT, {"key_1": STRAT_KEY})]


async def test_set_current_strategy_absent_inserts_pinned_setting() -> None:
    s = Session([None])
    await gc._set_current_strategy(s, GpuAssignmentStrategy.ISOLATION_FIRST)
    assert s.queries == [(STRAT_SELECT, {"key_1": STRAT_KEY})]
    assert len(s.added) == 1
    row = s.added[0]
    assert isinstance(row, SystemSetting)
    assert row.key == STRAT_KEY
    assert row.value == {"strategy": "isolation_first"}


# ============================================================================
# _get_assignments_from_db
# ============================================================================


async def test_get_assignments_pins_true_filter_and_full_fields() -> None:
    c1 = cfg_row(
        "svc-a",
        gpu_index=1,
        vram_budget_override=2.5,
        exclusive_gpu=False,
        priority_weight=11,
        incompatible_with=["x", "y"],
        enabled=True,
    )
    c2 = cfg_row(
        "svc-b",
        gpu_index=None,
        vram_budget_override=None,
        exclusive_gpu=True,
        priority_weight=100,
        incompatible_with=None,
        enabled=True,
    )
    s = Session([[c1, c2]])
    out = await gc._get_assignments_from_db(s)
    assert s.queries == [(CFG_SELECT_TRUE, {})]
    assert [a.service for a in out] == ["svc-a", "svc-b"]
    assert out[0].gpu_index == 1
    assert out[0].vram_budget_override == 2.5
    assert out[0].exclusive_gpu is False
    assert out[0].priority_weight == 11
    assert out[0].incompatible_with == ["x", "y"]
    assert out[1].exclusive_gpu is True
    assert out[1].priority_weight == 100
    assert out[1].incompatible_with is None


async def test_get_assignments_none_fields_take_defaults() -> None:
    c = cfg_row(
        "svc-n",
        gpu_index=0,
        exclusive_gpu=None,
        priority_weight=None,
        incompatible_with=[],
        enabled=True,
    )  # type: ignore[arg-type]
    s = Session([[c]])
    (a,) = await gc._get_assignments_from_db(s)
    assert a.exclusive_gpu is False
    assert a.priority_weight == 50
    assert a.incompatible_with == []


# ============================================================================
# _get_latest_config_update_time / _get_next_version_number / _save_version
# ============================================================================


async def test_latest_update_time_pins_max_query_and_passthrough() -> None:
    stamp = datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC)
    s = Session([stamp])
    assert (await gc._get_latest_config_update_time(s)) is stamp
    assert s.queries == [(UPDT_SELECT, {})]


async def test_latest_update_time_none_passthrough() -> None:
    s = Session([None])
    assert (await gc._get_latest_config_update_time(s)) is None
    assert s.queries == [(UPDT_SELECT, {})]


async def test_next_version_pins_max_query_and_arithmetic() -> None:
    s = Session([7])
    assert (await gc._get_next_version_number(s)) == 8
    assert s.queries == [(NEXTV_SELECT, {})]


async def test_next_version_none_becomes_one() -> None:
    s = Session([None])
    assert (await gc._get_next_version_number(s)) == 1


async def test_save_version_pins_row_and_json_keys() -> None:
    s = Session([7])
    v = await gc._save_version(
        s,
        "balanced",
        [asg("svc-a", 1, 2.5), asg("svc-b", None, None)],
        description="because",
        created_by="tester",
    )
    assert isinstance(v, GpuConfigurationVersion)
    assert s.queries == [(NEXTV_SELECT, {})]
    assert s.added == [v]
    assert v.version_number == 8
    assert v.strategy == "balanced"
    assert v.assignments == [
        {"service": "svc-a", "gpu_index": 1, "vram_budget_override": 2.5},
        {"service": "svc-b", "gpu_index": None, "vram_budget_override": None},
    ]
    assert v.description == "because"
    assert v.created_by == "tester"


# ============================================================================
# _validate_vram_assignments
# ============================================================================


def test_validate_vram_skips_none_flags_absent_then_still_counts_later() -> None:
    # THREE rows in this exact order: the None-index row kills the first
    # continue->break, the ghost row must NOT short-circuit the OVERAGE row
    # behind it (kills the second continue->break — with only two rows that
    # mutant has nothing left to skip and survives).
    gpus = [dev(0, 5)]
    with mock.patch.object(gc, "AI_SERVICE_VRAM_REQUIREMENTS_MB", {"over": 10}):
        out = gc._validate_vram_assignments(
            [asg("none-gpu", None), asg("ghost", 9), asg("over", 0)], gpus
        )
    assert out == [
        "Service 'ghost' assigned to non-existent GPU 9",
        "GPU 0 is over budget by 5 MB (assigned: 10 MB, available: 5 MB)",
    ]


def test_validate_vram_override_exact_capacity_boundary_silent() -> None:
    gpus = [dev(0, 1024)]
    assert gc._validate_vram_assignments([asg("s", 0, 1.0)], gpus) == []


def test_validate_vram_accumulates_and_prints_exact_usage() -> None:
    gpus = [dev(0, 10)]
    with mock.patch.object(gc, "AI_SERVICE_VRAM_REQUIREMENTS_MB", {"a": 6, "b": 6}):
        out = gc._validate_vram_assignments([asg("a", 0), asg("b", 0)], gpus)
    assert out == ["GPU 0 is over budget by 2 MB (assigned: 12 MB, available: 10 MB)"]


def test_validate_vram_usage_equals_total_is_silent() -> None:
    gpus = [dev(0, 10)]
    with mock.patch.object(gc, "AI_SERVICE_VRAM_REQUIREMENTS_MB", {"a": 10}):
        assert gc._validate_vram_assignments([asg("a", 0)], gpus) == []


def test_validate_vram_zero_total_guard_silences() -> None:
    gpus = [dev(0, 0)]
    with mock.patch.object(gc, "AI_SERVICE_VRAM_REQUIREMENTS_MB", {"a": 5}):
        assert gc._validate_vram_assignments([asg("a", 0)], gpus) == []


def test_validate_vram_total_one_still_flags() -> None:
    gpus = [dev(0, 1)]
    with mock.patch.object(gc, "AI_SERVICE_VRAM_REQUIREMENTS_MB", {"a": 2}):
        out = gc._validate_vram_assignments([asg("a", 0)], gpus)
    assert out == ["GPU 0 is over budget by 1 MB (assigned: 2 MB, available: 1 MB)"]


def test_validate_vram_absent_service_accumulates_with_present() -> None:
    # BIRTH trio (vram_mb default 0 -> 1 / None / trailing-comma): 'ghost'
    # is ABSENT from the table and ACCUMULATES after yolo fills the GPU
    # EXACTLY.  Shipped default 0 -> usage 100 == total 100 -> SILENT
    # (the used>total>0 chain stays false).  Default 1 -> 101 > 100 > 0 ->
    # exact overage message.  Default None / trailing-comma-2-arg: the 2-arg
    # .get RAISES KeyError and the None default poisons `usage += None`
    # with TypeError (measured) — both RED by raising.
    gpus = [dev(0, 100)]
    with mock.patch.object(gc, "AI_SERVICE_VRAM_REQUIREMENTS_MB", {"ai-yolo26": 100}):
        out = gc._validate_vram_assignments([asg("ai-yolo26", 0), asg("ghost", 0)], gpus)
    assert out == []


# ============================================================================
# _validate_affinity_constraints
# ============================================================================


def test_affinity_exclusive_and_incompatible_warnings_both() -> None:
    out = gc._validate_affinity_constraints(
        [
            asg("mine", 0, exclusive=True),
            asg("freeloader", 0),
            asg("hater", 1, incompatible=["enemy"]),
            asg("enemy", 1),
        ]
    )
    assert out == [
        "Service 'mine' requires exclusive GPU but shares GPU 0 with: freeloader",
        "Service 'hater' is incompatible with 'enemy' but both are on GPU 1",
    ]


def test_affinity_none_gpu_participates_in_no_group() -> None:
    assert (
        gc._validate_affinity_constraints([asg("mine", None, exclusive=True), asg("other", None)])
        == []
    )


def test_affinity_exclusive_alone_is_silent() -> None:
    assert gc._validate_affinity_constraints([asg("solo", 0, exclusive=True)]) == []


def test_affinity_joiner_and_incompatible_count_pin() -> None:
    # BIRTH pair.  m13 mutmaps the joiner ", " -> "XX, XX": a SINGLE co-
    # tenant never exercises the separator (one element joins to itself), so
    # 'mine' shares GPU 0 with TWO others — shipped renders "b, c", the XX
    # joiner renders "bXX, XXc" (FULL-string equality, not a fragment).
    # m14 flips `other.service == incompatible_service` to !=: the mutant
    # matches every OTHER co-tenant with the SAME byte-identical message,
    # so 'hater' (incompatible_with ['enemy']) on a GPU shared with 'enemy'
    # AND an unrelated 'bystander' yields shipped 1 warning vs the mutant's 2
    # — the count differs, the strings do not ([[fragment-count-asserts...]]
    # territory: exact LIST equality is the pin).
    out = gc._validate_affinity_constraints(
        [
            asg("mine", 0, exclusive=True),
            asg("b", 0),
            asg("c", 0),
            asg("hater", 1, incompatible=["enemy"]),
            asg("enemy", 1),
            asg("bystander", 1),
        ]
    )
    assert out == [
        "Service 'mine' requires exclusive GPU but shares GPU 0 with: b, c",
        "Service 'hater' is incompatible with 'enemy' but both are on GPU 1",
    ]


# ============================================================================
# _save_assignments_to_db
# ============================================================================


async def test_save_assignments_updates_existing_fields() -> None:
    existing = cfg_row(
        "svc-a",
        gpu_index=99,
        strategy="stale",
        vram_budget_override=9.9,
        enabled=False,
        exclusive_gpu=False,
        priority_weight=1,
        incompatible_with=None,
    )
    s = Session([[existing]])
    await gc._save_assignments_to_db(
        s,
        [asg("svc-a", gpu_index=2, override=3.5, exclusive=True, weight=42, incompatible=["q"])],
        GpuAssignmentStrategy.LATENCY_OPTIMIZED,
    )
    assert s.queries == [(CFG_BASE, {})]
    assert s.added == []
    assert existing.gpu_index == 2
    assert existing.strategy == "latency_optimized"
    assert existing.vram_budget_override == 3.5
    assert existing.enabled is True
    assert existing.exclusive_gpu is True
    assert existing.priority_weight == 42
    assert existing.incompatible_with == ["q"]


async def test_save_assignments_creates_new_row_with_all_kwargs() -> None:
    s = Session([[]])
    await gc._save_assignments_to_db(
        s,
        [asg("fresh", gpu_index=5, override=7.25, exclusive=True, weight=61, incompatible=["z"])],
        GpuAssignmentStrategy.BALANCED,
    )
    assert s.queries == [(CFG_BASE, {})]
    assert len(s.added) == 1
    row = s.added[0]
    assert isinstance(row, GpuConfiguration)
    assert row.service_name == "fresh"
    assert row.gpu_index == 5
    assert row.strategy == "balanced"
    assert row.vram_budget_override == 7.25
    assert row.enabled is True
    assert row.exclusive_gpu is True
    assert row.priority_weight == 61
    assert row.incompatible_with == ["z"]


# ============================================================================
# _update_gpu_devices_in_db
# ============================================================================


async def test_update_devices_existing_fields_and_seen_stamp() -> None:
    before = datetime(2000, 1, 1, tzinfo=UTC)
    row = GpuDeviceModel(
        gpu_index=0,
        name="old",
        vram_total_mb=1,
        vram_available_mb=2,
        compute_capability="0.0",
        last_seen_at=before,
    )
    s = Session([[row]])
    await gc._update_gpu_devices_in_db(s, [dev(0, 111, cc="8.6", vram_used=1)])
    assert s.queries == [(DEV_SELECT, {})]
    assert s.added == []
    assert row.name == "gpu-0"
    assert row.vram_total_mb == 111
    assert row.vram_available_mb == 110  # property: total - used (measured)
    assert row.compute_capability == "8.6"
    seen = row.last_seen_at
    assert isinstance(seen, datetime)
    assert seen > before
    assert seen.tzinfo is not None


async def test_update_devices_insert_new_row_all_fields() -> None:
    d = GpuDevice(
        index=2, name="d2", vram_total_mb=333, vram_used_mb=111, uuid="u2", compute_capability="9.0"
    )
    s = Session([[]])
    await gc._update_gpu_devices_in_db(s, [d])
    assert s.queries == [(DEV_SELECT, {})]
    assert len(s.added) == 1
    row = s.added[0]
    assert isinstance(row, GpuDeviceModel)
    assert row.gpu_index == 2
    assert row.name == "d2"
    assert row.vram_total_mb == 333
    assert row.vram_available_mb == 222  # device property: 333 - 111 (measured)
    assert row.compute_capability == "9.0"
    assert isinstance(row.last_seen_at, datetime)
    assert row.last_seen_at.tzinfo is not None


# ============================================================================
# _calculate_auto_assignments
# ============================================================================


def test_calc_no_gpus_exact_empty_and_message() -> None:
    a, w = gc._calculate_auto_assignments(GpuAssignmentStrategy.BALANCED, [])
    assert a == []
    assert w == [NO_GPU_MSG]


def test_calc_manual_pins_first_gpu_and_explicit_none() -> None:
    a, w = gc._calculate_auto_assignments(
        GpuAssignmentStrategy.MANUAL, [dev(0, 100), dev(1, 200)], services=["s1", "s2"]
    )
    assert w == []
    assert [x.service for x in a] == ["s1", "s2"]
    assert [x.gpu_index for x in a] == [0, 0]
    assert_explicit_none_overrides(a)


def test_calc_manual_default_services_is_table_keys() -> None:
    with mock.patch.object(gc, "AI_SERVICE_VRAM_REQUIREMENTS_MB", VRAM_TABLE):
        a, w = gc._calculate_auto_assignments(GpuAssignmentStrategy.MANUAL, [dev(0, 999)])
    assert w == []
    assert [x.service for x in a] == ["big", "small", "tiny"]
    assert [x.gpu_index for x in a] == [0, 0, 0]
    assert_explicit_none_overrides(a)


def test_calc_vram_based_orders_by_need_and_fills_capacity() -> None:
    gpus = [dev(1, 200), dev(0, 100)]
    with mock.patch.object(gc, "AI_SERVICE_VRAM_REQUIREMENTS_MB", VRAM_TABLE), log_rec() as rec:
        a, w = gc._calculate_auto_assignments(
            GpuAssignmentStrategy.VRAM_BASED,
            gpus,
            services=["absent", "big", "small", "tiny"],
        )
    assert w == []
    assert rec.calls == []
    # desc need (stable sort: equal-0 'absent' keeps input order before 'tiny'):
    # big(200)->GPU1 remaining 0; small(60)->GPU0; absent(0)->GPU1 (0>=0);
    # tiny(0)->GPU1.
    assert [x.service for x in a] == ["big", "small", "absent", "tiny"]
    assert [x.gpu_index for x in a] == [1, 0, 1, 1]
    assert_explicit_none_overrides(a)


def test_calc_vram_based_zero_need_assigns_silently() -> None:
    # service absent from the table needs 0: zero-remaining GPU still fits.
    gpus = [dev(0, 5)]
    with mock.patch.object(gc, "AI_SERVICE_VRAM_REQUIREMENTS_MB", {}):
        a, w = gc._calculate_auto_assignments(
            GpuAssignmentStrategy.VRAM_BASED, gpus, services=["zero"]
        )
    assert w == []
    assert [(x.service, x.gpu_index) for x in a] == [("zero", 0)]


def test_calc_sort_miss_default_zero_vs_one_flips_order() -> None:
    # 'tiny' is worth EXACTLY 0, input BEFORE the absent 'zero': shipped keys
    # tie at 0 -> stable input order [tiny, zero]; default 1 lifts 'zero'
    # above 'tiny' -> [zero, tiny].  (The flip needs this exact input order.)
    gpus = [dev(0, 10_000)]
    with mock.patch.object(gc, "AI_SERVICE_VRAM_REQUIREMENTS_MB", VRAM_TABLE):
        a, w = gc._calculate_auto_assignments(
            GpuAssignmentStrategy.VRAM_BASED, gpus, services=["tiny", "zero"]
        )
    assert w == []
    assert [x.service for x in a] == ["tiny", "zero"]


def test_calc_vram_based_overflow_warns_with_pinned_index() -> None:
    gpus = [dev(0, 100)]
    with mock.patch.object(gc, "AI_SERVICE_VRAM_REQUIREMENTS_MB", {"huge": 500}):
        a, w = gc._calculate_auto_assignments(
            GpuAssignmentStrategy.VRAM_BASED, gpus, services=["huge"]
        )
    assert [(x.service, x.gpu_index) for x in a] == [("huge", 0)]
    assert w == ["Service 'huge' assigned to GPU 0 but may exceed VRAM budget"]
    assert_explicit_none_overrides(a)


def test_calc_vram_based_fallback_max_by_remaining_skewed() -> None:
    # BIRTH trio on the fallback line `best_gpu = max(sorted_gpus, key=
    # lambda g: gpu_remaining[g.index])`.  Construction (measured against
    # the VRAM_BASED loop): gpus sorted DESC by total = [g0(100), g1(50)];
    # table {"s1": 60, "s2": 60}.  s1 fits g0 first (100>=60) -> remaining
    # [40, 50]; s2 does NOT fit 40 -> fallback branch.  Shipped max-by-
    # remaining picks g1 (50>40) -> GPU 1.  key=None and the 1-arg max()
    # twin RAISE (GpuDevice is an UNORDERED dataclass and a real comparison
    # happens between two different GPUs), and key=lambda g: None also
    # raises comparing None keys — a pure 2-service input with NO prior fit
    # would keep remaining == totals where max-by-remaining agrees with
    # first-element, so the prior fit is load-bearing.
    gpus = [dev(0, 100), dev(1, 50)]
    with mock.patch.object(gc, "AI_SERVICE_VRAM_REQUIREMENTS_MB", {"s1": 60, "s2": 60}):
        a, w = gc._calculate_auto_assignments(
            GpuAssignmentStrategy.VRAM_BASED, gpus, services=["s1", "s2"]
        )
    assert [(x.service, x.gpu_index) for x in a] == [("s1", 0), ("s2", 1)]
    assert w == ["Service 's2' assigned to GPU 1 but may exceed VRAM budget"]
    assert_explicit_none_overrides(a)


def test_calc_latency_three_gpus_pick_last_not_next() -> None:
    # BIRTH m131: `other_gpu = sorted_gpus[-1]` -> [+1].  With exactly TWO
    # GPUs [+1] == [-1] (that's why the old 2-GPU rows can't kill it): with
    # THREE GPUs sorted by compute score [g0(9.0), g1(8.6), g2(1.0)],
    # shipped picks g2 (the SLOWEST, index 2) while [+1] picks g1 (index 1).
    # (m130 `or True` / m133 `>= 1` twins are EQUIV: they only change which
    # branch runs when len==1, where sorted_gpus[-1] IS fastest_gpu.)
    gpus = [dev(0, 1000, cc="9.0"), dev(1, 500, cc="8.6"), dev(2, 100, cc="1.0")]
    a, w = gc._calculate_auto_assignments(
        GpuAssignmentStrategy.LATENCY_OPTIMIZED, gpus, services=["ai-yolo26", "rest"]
    )
    assert w == []
    assert [(x.service, x.gpu_index) for x in a] == [("ai-yolo26", 0), ("rest", 2)]
    assert_explicit_none_overrides(a)


def test_calc_isolation_two_gpus_share_the_non_largest() -> None:
    gpus = [dev(0, 100), dev(1, 1000)]
    a, w = gc._calculate_auto_assignments(
        GpuAssignmentStrategy.ISOLATION_FIRST, gpus, services=["p", "q"]
    )
    assert w == []
    assert [x.service for x in a] == ["p", "q"]
    assert [x.gpu_index for x in a] == [0, 0]
    assert_explicit_none_overrides(a)


def test_calc_isolation_single_gpu_warns_pinned_message() -> None:
    a, w = gc._calculate_auto_assignments(
        GpuAssignmentStrategy.ISOLATION_FIRST, [dev(0, 500)], services=["p"]
    )
    assert [x.gpu_index for x in a] == [0]
    assert w == [SOLO_MSG]
    assert_explicit_none_overrides(a)


def test_calc_latency_critical_on_fastest_rest_on_slowest() -> None:
    gpus = [dev(0, 1000, cc="8.6"), dev(1, 2000, cc="6.1")]
    a, w = gc._calculate_auto_assignments(
        GpuAssignmentStrategy.LATENCY_OPTIMIZED,
        gpus,
        services=["ai-yolo26", "other"],
    )
    assert w == []
    assert [(x.service, x.gpu_index) for x in a] == [("ai-yolo26", 0), ("other", 1)]
    assert_explicit_none_overrides(a)


def test_calc_latency_single_gpu_everything_on_fastest() -> None:
    a, w = gc._calculate_auto_assignments(
        GpuAssignmentStrategy.LATENCY_OPTIMIZED,
        [dev(3, 100, cc="9.0")],
        services=["ai-yolo26", "other"],
    )
    assert w == []
    assert [x.gpu_index for x in a] == [3, 3]
    assert_explicit_none_overrides(a)


def test_calc_balanced_spreads_and_accumulates_usage() -> None:
    gpus = [dev(0, 100), dev(1, 100), dev(2, 100)]
    table = {"a300": 300, "a299": 299, "a298": 298, "a1": 1, "a2": 2}
    with mock.patch.object(gc, "AI_SERVICE_VRAM_REQUIREMENTS_MB", table):
        a, w = gc._calculate_auto_assignments(
            GpuAssignmentStrategy.BALANCED,
            gpus,
            services=["a300", "a299", "a298", "a1", "a2"],
        )
    assert w == []
    # sorted desc: a300,a299,a298,a2,a1.  a300->GPU0(300) a299->GPU1(299)
    # a298->GPU2(298) a2 -> argmin GPU2 -> 300; a1 -> argmin [300,299,300]
    # -> GPU1.  += -> = puts GPU2 at 2 -> a1 picks GPU2 instead.
    assert [(x.service, x.gpu_index) for x in a] == [
        ("a300", 0),
        ("a299", 1),
        ("a298", 2),
        ("a2", 2),
        ("a1", 1),
    ]
    assert_explicit_none_overrides(a)


def test_calc_balanced_miss_default_flip_and_order() -> None:
    gpus = [dev(0, 10_000), dev(1, 10_000)]
    with mock.patch.object(gc, "AI_SERVICE_VRAM_REQUIREMENTS_MB", VRAM_TABLE):
        a, w = gc._calculate_auto_assignments(
            GpuAssignmentStrategy.BALANCED, gpus, services=["tiny", "zero", "small"]
        )
    assert w == []
    # keys: tiny 0 (in table), zero MISSING -> 0, small 60.
    # shipped desc: [small, tiny, zero] (stable tie); default-1: zero(1) over
    # tiny(0) -> [small, zero, tiny].
    assert [x.service for x in a] == ["small", "tiny", "zero"]
    # usage: small(60)->GPU0; tiny(0)->GPU1; zero(0)-> argmin [60,0] -> GPU1.
    assert [x.gpu_index for x in a] == [0, 1, 1]
    assert_explicit_none_overrides(a)


def test_calc_unmatched_strategy_yields_nothing() -> None:
    a, w = gc._calculate_auto_assignments("mystery", [dev(0, 100)], services=["s"])
    assert a == []
    assert w == []


def test_module_constants_and_fallback_shape() -> None:
    assert gc.REDIS_CURRENT_OPERATION_KEY == OPS_KEY
    assert gc.GPU_STRATEGY_SETTING_KEY == STRAT_KEY
    assert set(gc._apply_state_fallback) == {
        "in_progress",
        "operation_id",
        "services_pending",
        "services_completed",
        "service_statuses",
        "last_updated",
    }
