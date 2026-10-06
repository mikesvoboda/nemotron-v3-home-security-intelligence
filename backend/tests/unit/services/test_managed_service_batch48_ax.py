# TARGET-MODULE: backend.services.managed_service
"""Battery AX - campaign #48 kill battery for backend/services/managed_service.py.

Style (proven AT..AW): every observable an entered branch WRITES is asserted
([[entered-branch-must-assert-every-observable-it-writes]]); log pins ride REAL
LogRecords on the REAL logger with BY-NAME extras access
([[log-context-filter-fakes-extra-kwarg-mutants]]); message asserts are FULL
equality over the FULL ordered sequence, never fragments
([[fragment-count-asserts-pass-xx-mutants]]); dataclasses pinned by EXACT
instance equality (one row kills kwarg-drop, kwarg-None and value-twins at
once) and dicts by exact equality including the key SET; Redis calls pinned as
the FULL call tuple (key, positional args, kwargs) - a dropped or None'd
kwarg is invisible on any instance-level assert
([[dropped-kwarg-mutants-needs-a-call-site-spy]]); NO pytest fixtures
([[b30-sweep-no-fixtures-tmp-path-fake-hang-storm]]) - coroutines are driven
with asyncio.run so the battery survives the fixture-less b30 sweep
([[single-process-trampoline-sweep-harness]]); timestamps are a FIXED
timezone-aware instant, never datetime.now().

Measured semantics from the SHIPPED source (read 2026-10-06, lines cited) and
a same-day live probe of every world pinned below:
- Enums are StrEnums with auto() values: ServiceCategory {infrastructure, ai,
  monitoring}; ContainerServiceStatus {running, starting, unhealthy, stopped,
  disabled, not_found}. ManagedService/ServiceConfig are @dataclass(slots=True)
  so `==` compares the full field tuple AND the class.
- to_dict (L159-185): 18 keys, enums lowered to .value, datetimes to
  .isoformat(), None when falsy. Measured ISO rendering of the pinned instant
  DT = datetime(2026,10,6,12,30,45,123456, UTC) is
  "2026-10-06T12:30:45.123456+00:00" == DT.isoformat().
- from_dict (L187-229): datetime fields parsed ONLY when data.get(...) is
  TRUTHY (an empty string or null both leave None); category =
  ServiceCategory(data["category"]) REQUIRED; status falls back to
  ContainerServiceStatus(NOT_FOUND.value); defaults display_name=name,
  enabled=True, failure_count=0, restart_count=0, max_failures=5,
  restart_backoff_base=5.0, restart_backoff_max=300.0,
  startup_grace_period=60. Measured: the minimal {"name","port","category"}
  dict yields the full default instance.
- from_config (L231-267): status ALWAYS ContainerServiceStatus.NOT_FOUND
  (written explicitly, never copied from config); name=config_key,
  container_id/image are the extra args; everything else copied off the
  ServiceConfig. Measured instance in _CONFIG_EXPECTED.
- ServiceRegistry.register/unregister/update_status/set_enabled/
  update_container_id/reset_failures/increment_failure/record_restart
  (L322-525): all `with self._lock`; every one is SILENT when the name is
  ABSENT (no log, no write) - that no-op path is what kills the
  guard-polarity and body-drop mutants. increment_failure RETURNS the new
  count (0 when absent); reset_failures writes failure_count=0 AND
  last_failure_at=None (both asserted); record_restart writes
  restart_count += 1 AND last_restart_at.
- persist_state (L531-575): no-redis -> ONE DEBUG f-string
  'No Redis client, skipping persist for {name}' with NO extras then return;
  absent service (redis present) -> SILENT return; else the state dict is
  EXACTLY the 6 keys measured (enabled, failure_count, last_failure_at ISO or
  None, last_restart_at ISO or None, restart_count, status .value) and the
  call is `await self._redis.set(key, state, expire=86400)` with
  key = f"orchestrator:service:{name}:state"; success -> DEBUG 'Persisted
  service state to Redis' {service_name}; ANY exception -> WARNING 'Failed to
  persist service state to Redis' {service_name, error=str(e)}.
- _apply_state_to_service (L577-605): enabled/failure_count/restart_count via
  .get with defaults True/0/0; the two timestamps via
  `datetime.fromisoformat(v) if v else None`; status ONLY when state.get
  ("status") is truthy and parseable - an unparseable value logs WARNING
  'Invalid status in Redis state' {service_name, status=value} and LEAVES the
  previous status. Measured: apply with an EMPTY dict is SILENT and yields
  enabled=True, counts 0, both timestamps None, status untouched.
- load_state (L607-656): no-redis -> ONE DEBUG f-string
  'No Redis client, skipping load_state for {name}' (no extras); absent
  service -> SILENT; `await self._redis.get(key)` (key alone, no kwargs);
  falsy payload -> DEBUG 'No Redis state found for service'; str payload is
  json.loads'd; then _apply_state_to_service(service, state, name) and DEBUG
  'Loaded service state from Redis'. A bogus status emits WARNING FIRST then
  the success DEBUG (2 records, measured). json.JSONDecodeError -> WARNING
  'Failed to parse Redis state JSON' {service_name, error=str(e)} (measured
  str(e) = 'Expecting value: line 1 column 1 (char 0)' for "not-json");
  any other exception -> WARNING 'Failed to load service state from Redis'.
- load_all_state (L658-673): snapshots names, awaits load_state per name,
  then ONE INFO 'Loaded state for all services from Redis'
  {service_count: len(names)}. Measured with 2 names and redis=None: exactly
  3 records in that order.
- clear_state (L675-692): no-redis -> SILENT (no log at all); else
  `await self._redis.delete(key)` + DEBUG 'Cleared service state from Redis';
  exception -> WARNING 'Failed to clear service state from Redis'.
- get_service_registry (L703-722) / reset_service_registry (L725-734):
  singleton built once under _registry_lock with a LOCAL
  `from backend.core.redis import init_redis` (resolved at CALL time, so a
  module-level patch is seen - measured: the stub's sentinel lands in
  _service_registry._redis and the 2nd call returns the SAME object);
  creation logs INFO 'Created global ServiceRegistry singleton' with NO
  extras; reset sets the global to None and logs DEBUG 'Reset global
  ServiceRegistry singleton'.
EQUIV DISPOSITIONS (proof sketch per family; each is RE-PROVEN by the 485-key
redcheck sweep + the close-sweep attribution - NOTHING is tolerated):
- none claimed at authoring. Every one of the 189 survivor keys has a
  deliberate divergence world above (full-instance/full-dict equality, exact
  call tuples, or full ordered log sequences). Families that LOOK unreachable
  are still given rows and adjudicated by measurement, not diff-shape
  ([[survivor-disposition-requires-sweep-not-diffshape]]): the get-default
  twins get an ABSENT-key world (the helper-None-default trap does not apply -
  no local `at=None` shim exists in this module), the `... if v or True else
  None` guards get the falsy world where shipped takes the else-branch and the
  mutant calls .isoformat()/fromisoformat() on None (AttributeError/TypeError),
  and the `+= 1` -> `= 1` twins get a count-from-2 world.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from dataclasses import replace as dc_replace
from datetime import UTC, datetime
from typing import Any

from backend.api.schemas.services import ContainerServiceStatus, ServiceCategory
from backend.services import managed_service as ms_mod
from backend.services.managed_service import (
    REDIS_KEY_PREFIX,
    ManagedService,
    ServiceConfig,
    ServiceRegistry,
)

# ---------------------------------------------------------------------------
# Fixed world (no wall-clock anywhere - [[await-time-getters-need-live-stubs]]
# applies to datetime.now(UTC) inside increment_failure/record_restart: those
# two asserts are tz-identity + monotonic-order pins, not equality pins).
# ---------------------------------------------------------------------------

DT = datetime(2026, 10, 6, 12, 30, 45, 123456, tzinfo=UTC)
DT_ISO = "2026-10-06T12:30:45.123456+00:00"

_STATE: dict[str, Any] = {
    "name": "svc-a",
    "display_name": "Svc A",
    "container_id": "cid-1",
    "image": "img:1",
    "port": 8095,
    "category": ServiceCategory.AI,
    "health_endpoint": "/health",
    "health_cmd": "hcmd",
    "status": ContainerServiceStatus.RUNNING,
}


def _svc(**kw: Any) -> ManagedService:
    """ManagedService from the fixed world with overrides applied."""
    merged = {**_STATE}
    merged.update(kw)
    return ManagedService(**merged)


_CONFIG = ServiceConfig(
    display_name="Cfg",
    category=ServiceCategory.MONITORING,
    port=3000,
    health_endpoint="/cfg",
    health_cmd="cfgcmd",
    startup_grace_period=33,
    max_failures=7,
    restart_backoff_base=11.0,
    restart_backoff_max=222.0,
)
# Measured full instance for from_config("cfgkey", _CONFIG, "cid-cfg", "cfgimg:2")
_CONFIG_EXPECTED = ManagedService(
    name="cfgkey",
    display_name="Cfg",
    container_id="cid-cfg",
    image="cfgimg:2",
    port=3000,
    category=ServiceCategory.MONITORING,
    health_endpoint="/cfg",
    health_cmd="cfgcmd",
    status=ContainerServiceStatus.NOT_FOUND,
    max_failures=7,
    restart_backoff_base=11.0,
    restart_backoff_max=222.0,
    startup_grace_period=33,
)

# Measured full instances for from_dict
_MINIMAL_IN = {"name": "svc-b", "port": 9000, "category": "infrastructure"}
_MINIMAL_EXPECTED = ManagedService(
    name="svc-b",
    display_name="svc-b",
    container_id=None,
    image=None,
    port=9000,
    category=ServiceCategory.INFRASTRUCTURE,
)
_FULL_IN = {
    "name": "svc-c",
    "display_name": "Svc C",
    "container_id": "cid-3",
    "image": "img3",
    "port": 9001,
    "health_endpoint": "/h3",
    "health_cmd": "c3",
    "category": "ai",
    "status": "unhealthy",
    "enabled": False,
    "failure_count": 4,
    "last_failure_at": DT_ISO,
    "last_restart_at": DT_ISO,
    "restart_count": 5,
    "max_failures": 9,
    "restart_backoff_base": 4.25,
    "restart_backoff_max": 404.5,
    "startup_grace_period": 77,
}
_FULL_EXPECTED = ManagedService(
    name="svc-c",
    display_name="Svc C",
    container_id="cid-3",
    image="img3",
    port=9001,
    health_endpoint="/h3",
    health_cmd="c3",
    category=ServiceCategory.AI,
    status=ContainerServiceStatus.UNHEALTHY,
    enabled=False,
    failure_count=4,
    last_failure_at=DT,
    last_restart_at=DT,
    restart_count=5,
    max_failures=9,
    restart_backoff_base=4.25,
    restart_backoff_max=404.5,
    startup_grace_period=77,
)


class _Redis:
    """Async Redis stub recording FULL call tuples (spy on key+args+kwargs)."""

    def __init__(self, payload: Any = None, raises: BaseException | None = None) -> None:
        self.payload = payload
        self.raises = raises
        self.calls: list[tuple[Any, ...]] = []

    async def get(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append(("get", args, kwargs))
        if self.raises is not None:
            raise self.raises
        return self.payload

    async def set(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append(("set", args, kwargs))
        if self.raises is not None:
            raise self.raises
        return None

    async def delete(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append(("delete", args, kwargs))
        if self.raises is not None:
            raise self.raises
        return None


class _CapturingHandler(logging.Handler):
    def __init__(self, sink: list) -> None:
        super().__init__()
        self._sink = sink

    def emit(self, record: logging.LogRecord) -> None:
        self._sink.append(record)


@contextlib.contextmanager
def logs() -> Any:
    """Capture REAL LogRecords emitted to ms_mod.logger (BY-NAME extras)."""
    sink: list[logging.LogRecord] = []
    handler = _CapturingHandler(sink)
    old_level, old_prop = ms_mod.logger.level, ms_mod.logger.propagate
    ms_mod.logger.setLevel(logging.DEBUG)
    ms_mod.logger.addHandler(handler)
    ms_mod.logger.propagate = False
    try:
        yield sink
    finally:
        ms_mod.logger.removeHandler(handler)
        ms_mod.logger.setLevel(old_level)
        ms_mod.logger.propagate = old_prop


def _pin(recs: list, expected: list[tuple[int, str, dict]]) -> None:
    """Full ordered pin: LEVEL, exact MESSAGE, exact extras dict by name."""
    assert [(r.levelno, r.getMessage()) for r in recs] == [
        (lvl, msg) for lvl, msg, _ in expected
    ], [(logging.getLevelName(r.levelno), r.getMessage()) for r in recs]
    for rec, (_, _, extras) in zip(recs, expected, strict=True):
        for key, want in extras.items():
            assert getattr(rec, key, "<absent>") == want, (
                key,
                getattr(rec, key, "<absent>"),
                want,
            )


# ===========================================================================
# ManagedService.to_dict   (survivors d26, d30)
# ===========================================================================


def test_k48_to_dict_empty_world_exact() -> None:
    """d26/d30 (falsy-guard `or True` on the two timestamps): the EMPTY world
    pins the full 18-key dict with both timestamp slots None - the mutant
    reaches .isoformat() on None and dies with AttributeError."""
    s = _svc(enabled=False, failure_count=0, restart_count=0)
    out = s.to_dict()
    assert out == {
        "name": "svc-a",
        "display_name": "Svc A",
        "container_id": "cid-1",
        "image": "img:1",
        "port": 8095,
        "health_endpoint": "/health",
        "health_cmd": "hcmd",
        "category": "ai",
        "status": "running",
        "enabled": False,
        "failure_count": 0,
        "last_failure_at": None,
        "last_restart_at": None,
        "restart_count": 0,
        "max_failures": 5,
        "restart_backoff_base": 5.0,
        "restart_backoff_max": 300.0,
        "startup_grace_period": 60,
    }
    assert DT.isoformat() == DT_ISO


def test_k48_to_dict_populated_world_exact() -> None:
    """The populated world renders BOTH timestamps as the measured ISO string
    (kills any render-path change that the empty world could not see)."""
    s = _svc(
        enabled=False,
        failure_count=3,
        last_failure_at=DT,
        last_restart_at=DT,
        restart_count=5,
        status=ContainerServiceStatus.UNHEALTHY,
        max_failures=7,
        restart_backoff_base=11.0,
        restart_backoff_max=222.0,
        startup_grace_period=33,
    )
    out = s.to_dict()
    assert out["last_failure_at"] == DT_ISO
    assert out["last_restart_at"] == DT_ISO
    assert out["status"] == "unhealthy"
    assert out["category"] == "ai"
    assert (out["enabled"], out["failure_count"], out["restart_count"]) == (False, 3, 5)
    assert (out["max_failures"], out["restart_backoff_base"]) == (7, 11.0)
    assert (out["restart_backoff_max"], out["startup_grace_period"]) == (222.0, 33)


# ===========================================================================
# ManagedService.from_config   (survivors c7, c11, c12, c20, c22, c24, c25)
# ===========================================================================


def test_k48_from_config_full_instance_equality() -> None:
    """Every kwarg of the return-cls line is pinned by EXACT dataclass
    equality (class + all 18 fields): a None'd or dropped kwarg falls to the
    field default and breaks the pin. Status is NOT_FOUND in shipped."""
    got = ManagedService.from_config("cfgkey", _CONFIG, "cid-cfg", "cfgimg:2")
    assert got == _CONFIG_EXPECTED
    assert type(got) is ManagedService
    assert got.status is ContainerServiceStatus.NOT_FOUND


def test_k48_from_config_zero_overrides() -> None:
    """Divergence twin: a config whose values are all falsy/zero differs from
    every field default, so the same full-equality pin catches the drops from
    the other side."""
    cfg = ServiceConfig(
        display_name="",
        category=ServiceCategory.INFRASTRUCTURE,
        port=0,
        health_endpoint="",
        health_cmd="",
        startup_grace_period=0,
        max_failures=0,
        restart_backoff_base=0.0,
        restart_backoff_max=0.0,
    )
    got = ManagedService.from_config("zkey", cfg, "z", "zi")
    assert got == ManagedService(
        name="zkey",
        display_name="",
        container_id="z",
        image="zi",
        port=0,
        category=ServiceCategory.INFRASTRUCTURE,
        health_endpoint="",
        health_cmd="",
        status=ContainerServiceStatus.NOT_FOUND,
        max_failures=0,
        restart_backoff_base=0.0,
        restart_backoff_max=0.0,
        startup_grace_period=0,
    )


# ===========================================================================
# ManagedService.from_dict   (survivors f1, f10, f11, f12, f13, f41, f59,
#                             f97, f99, f102, f104, f106, f109, f111, f113,
#                             f116, f118, f120, f123, f125, f127, f130, f132,
#                             f134, f137)
# ===========================================================================


def test_k48_from_dict_minimal_full_equality() -> None:
    """Minimal required-key dict -> the EXACT default instance; catches every
    default-twin (None/absent-value/+1) in the return-cls line."""
    assert ManagedService.from_dict(_MINIMAL_IN) == _MINIMAL_EXPECTED


def test_k48_from_dict_full_full_equality() -> None:
    """Full dict -> the EXACT parsed instance (both timestamps become the
    pinned DT); catches last_*_at=None, the dropped last_restart_at kwarg, the
    parsed-line None and every default-twin from the other side."""
    assert ManagedService.from_dict(_FULL_IN) == _FULL_EXPECTED


def test_k48_from_dict_last_failure_key_live() -> None:
    """f10/f11/f12 family (data.get key -> None/XX/UPPER): with ONLY
    last_failure_at present the parse happens iff that exact key is read."""
    got = ManagedService.from_dict({**_MINIMAL_IN, "last_failure_at": DT_ISO})
    assert got.last_failure_at == DT
    assert got.last_restart_at is None


def test_k48_from_dict_last_restart_key_live() -> None:
    """Mirror row for the last_restart_at guard keys f13/f14/f15."""
    got = ManagedService.from_dict({**_MINIMAL_IN, "last_restart_at": DT_ISO})
    assert got.last_restart_at == DT
    assert got.last_failure_at is None


def test_k48_from_dict_falsy_timestamp_strings_stay_none() -> None:
    """Empty-string timestamps are FALSY -> both slots None (shipped); the
    `if v or True` polarity would call fromisoformat('') and raise."""
    got = ManagedService.from_dict({**_MINIMAL_IN, "last_failure_at": "", "last_restart_at": ""})
    assert got.last_failure_at is None
    assert got.last_restart_at is None


# ===========================================================================
# ServiceRegistry.register   (survivors g2, g3, g5, g6, g7, g8, g9, g10,
#                             g11, g12)
# ===========================================================================


def test_k48_register_exact_log() -> None:
    """Full ordered pin of register's single DEBUG: message + BOTH extras by
    name (service_name, category) - kills msg->None/XX/lower/UPPER,
    extra=None, extra-drop and all four extras-key renames."""
    reg = ServiceRegistry(redis_client=None)
    with logs() as recs:
        reg.register(_svc())
    _pin(
        recs,
        [
            (
                logging.DEBUG,
                "Registered service",
                {"service_name": "svc-a", "category": "ai"},
            )
        ],
    )


def test_k48_register_overwrite_returns_none() -> None:
    """register overwrites by name and RETURNS None; the second DEBUG carries
    the NEW service's category, and the stored object is the NEW one."""
    reg = ServiceRegistry(redis_client=None)
    reg.register(_svc())
    with logs() as recs:
        assert reg.register(dc_replace(_svc(), category=ServiceCategory.MONITORING)) is None
    _pin(
        recs,
        [
            (
                logging.DEBUG,
                "Registered service",
                {"service_name": "svc-a", "category": "monitoring"},
            )
        ],
    )
    assert reg.get("svc-a").category is ServiceCategory.MONITORING


# ===========================================================================
# ServiceRegistry.unregister   (survivors n2, n3, n5, n6, n7, n8, n9, n10)
# ===========================================================================


def test_k48_unregister_exact_log() -> None:
    reg = ServiceRegistry(redis_client=None)
    reg.register(_svc())
    with logs() as recs:
        reg.unregister("svc-a")
    _pin(recs, [(logging.DEBUG, "Unregistered service", {"service_name": "svc-a"})])
    assert reg.get("svc-a") is None
    assert reg.list_names() == []


def test_k48_unregister_absent_is_silent() -> None:
    """Absent name: SILENT no-op - the guard polarity and body-drop mutants
    either log or raise here."""
    reg = ServiceRegistry(redis_client=None)
    with logs() as recs:
        reg.unregister("nope")
    assert recs == []
    assert reg.list_names() == []


# ===========================================================================
# ServiceRegistry.update_status   (survivors u4, u5, u7, u8, u9, u10, u11,
#                                  u12, u13, u14)
# ===========================================================================


def test_k48_update_status_exact_log() -> None:
    reg = ServiceRegistry(redis_client=None)
    reg.register(_svc())
    with logs() as recs:
        reg.update_status("svc-a", ContainerServiceStatus.UNHEALTHY)
    _pin(
        recs,
        [
            (
                logging.DEBUG,
                "Updated service status",
                {"service_name": "svc-a", "status": "unhealthy"},
            )
        ],
    )
    assert reg.get("svc-a").status is ContainerServiceStatus.UNHEALTHY


def test_k48_update_status_absent_silent_no_write() -> None:
    reg = ServiceRegistry(redis_client=None)
    with logs() as recs:
        reg.update_status("nope", ContainerServiceStatus.RUNNING)
    assert recs == []
    assert reg.list_names() == []


# ===========================================================================
# ServiceRegistry.increment_failure   (survivors i3, i7, i8, i9, i11..i18)
# ===========================================================================


def test_k48_increment_failure_from_two() -> None:
    """i3 (`+= 1` -> `= 1`) needs a count-from-2 world; the DEBUG extras pin the
    POST-increment count by name."""
    reg = ServiceRegistry(redis_client=None)
    reg.register(_svc(failure_count=2))
    with logs() as recs:
        assert reg.increment_failure("svc-a") == 3
    _pin(
        recs,
        [
            (
                logging.DEBUG,
                "Incremented failure count",
                {"service_name": "svc-a", "failure_count": 3},
            )
        ],
    )
    assert reg.get("svc-a").failure_count == 3


def test_k48_increment_failure_writes_tz_aware_now() -> None:
    """i7 (datetime.now(UTC) -> now(None)): the written timestamp must be
    tz-aware AND span the call (>= t_pre, <= t_post as UTC instants)."""
    reg = ServiceRegistry(redis_client=None)
    reg.register(_svc())
    t_pre = datetime.now(UTC)
    reg.increment_failure("svc-a")
    t_post = datetime.now(UTC)
    stamp = reg.get("svc-a").last_failure_at
    assert stamp is not None
    assert stamp.tzinfo is UTC
    assert t_pre <= stamp <= t_post


def test_k48_increment_failure_absent_zero_silent() -> None:
    reg = ServiceRegistry(redis_client=None)
    with logs() as recs:
        assert reg.increment_failure("nope") == 0
    assert recs == []


# ===========================================================================
# ServiceRegistry.reset_failures   (survivors r6, r7, r9, r10, r11, r12,
#                                   r13, r14)
# ===========================================================================


def test_k48_reset_failures_clears_both_and_logs() -> None:
    reg = ServiceRegistry(redis_client=None)
    reg.register(_svc(failure_count=4, last_failure_at=DT))
    with logs() as recs:
        reg.reset_failures("svc-a")
    _pin(recs, [(logging.DEBUG, "Reset failure tracking", {"service_name": "svc-a"})])
    s = reg.get("svc-a")
    assert s.failure_count == 0
    assert s.last_failure_at is None


def test_k48_reset_failures_absent_silent() -> None:
    reg = ServiceRegistry(redis_client=None)
    with logs() as recs:
        reg.reset_failures("nope")
    assert recs == []


# ===========================================================================
# ServiceRegistry.record_restart   (survivors e3, e7, e8, e9, e11..e18)
# ===========================================================================


def test_k48_record_restart_from_two() -> None:
    reg = ServiceRegistry(redis_client=None)
    reg.register(_svc(restart_count=2))
    with logs() as recs:
        reg.record_restart("svc-a")
    _pin(
        recs,
        [
            (
                logging.DEBUG,
                "Recorded restart",
                {"service_name": "svc-a", "restart_count": 3},
            )
        ],
    )
    assert reg.get("svc-a").restart_count == 3


def test_k48_record_restart_writes_tz_aware_now() -> None:
    reg = ServiceRegistry(redis_client=None)
    reg.register(_svc())
    t_pre = datetime.now(UTC)
    reg.record_restart("svc-a")
    t_post = datetime.now(UTC)
    stamp = reg.get("svc-a").last_restart_at
    assert stamp is not None
    assert stamp.tzinfo is UTC
    assert t_pre <= stamp <= t_post


def test_k48_record_restart_absent_silent() -> None:
    reg = ServiceRegistry(redis_client=None)
    with logs() as recs:
        reg.record_restart("nope")
    assert recs == []


# ===========================================================================
# ServiceRegistry.set_enabled   (survivors t4, t5, t7, t8, t9, t10, t11, t12,
#                                t13, t14)
# ===========================================================================


def test_k48_set_enabled_false_exact_log() -> None:
    reg = ServiceRegistry(redis_client=None)
    reg.register(_svc(enabled=True))
    with logs() as recs:
        reg.set_enabled("svc-a", False)
    _pin(
        recs,
        [
            (
                logging.DEBUG,
                "Set service enabled",
                {"service_name": "svc-a", "enabled": False},
            )
        ],
    )
    assert reg.get("svc-a").enabled is False


def test_k48_set_enabled_true_polarity() -> None:
    """Polarity twin: enabled=True must also be forwarded EXACTLY (an inverted
    or None'd extras value passes only the False world)."""
    reg = ServiceRegistry(redis_client=None)
    reg.register(_svc(enabled=False))
    with logs() as recs:
        reg.set_enabled("svc-a", True)
    _pin(
        recs,
        [
            (
                logging.DEBUG,
                "Set service enabled",
                {"service_name": "svc-a", "enabled": True},
            )
        ],
    )
    assert reg.get("svc-a").enabled is True


def test_k48_set_enabled_absent_silent() -> None:
    reg = ServiceRegistry(redis_client=None)
    with logs() as recs:
        reg.set_enabled("nope", False)
    assert recs == []


# ===========================================================================
# ServiceRegistry.update_container_id   (survivors v4, v5, v7, v8, v9, v10,
#                                        v11, v12, v13, v14)
# ===========================================================================


def test_k48_update_container_id_exact_log() -> None:
    reg = ServiceRegistry(redis_client=None)
    reg.register(_svc(container_id="cid-1"))
    with logs() as recs:
        reg.update_container_id("svc-a", "cid-new")
    _pin(
        recs,
        [
            (
                logging.DEBUG,
                "Updated container_id",
                {"service_name": "svc-a", "container_id": "cid-new"},
            )
        ],
    )
    assert reg.get("svc-a").container_id == "cid-new"


def test_k48_update_container_id_none_world() -> None:
    reg = ServiceRegistry(redis_client=None)
    reg.register(_svc())
    with logs() as recs:
        reg.update_container_id("svc-a", None)
    _pin(
        recs,
        [
            (
                logging.DEBUG,
                "Updated container_id",
                {"service_name": "svc-a", "container_id": None},
            )
        ],
    )
    assert reg.get("svc-a").container_id is None


def test_k48_update_container_id_absent_silent() -> None:
    reg = ServiceRegistry(redis_client=None)
    with logs() as recs:
        reg.update_container_id("nope", "x")
    assert recs == []


# ===========================================================================
# ServiceRegistry.persist_state   (survivors p2, p14, p18, p26, p29, p30,
#                                  p31..p39)
# ===========================================================================


def test_k48_persist_state_no_redis_log() -> None:
    """p2: the skip branch is ONE DEBUG with the f-string message and NO
    extras; nothing is written anywhere."""
    reg = ServiceRegistry(redis_client=None)
    reg.register(_svc())
    with logs() as recs:
        assert asyncio.run(reg.persist_state("svc-a")) is None
    _pin(
        recs,
        [(logging.DEBUG, "No Redis client, skipping persist for svc-a", {})],
    )


def test_k48_persist_state_absent_service_silent() -> None:
    reg = ServiceRegistry(redis_client=_Redis())
    with logs() as recs:
        asyncio.run(reg.persist_state("nope"))
    assert recs == []
    assert reg._redis.calls == []


def test_k48_persist_state_populated_exact_call() -> None:
    """The spy pins the WHOLE call: key, positional (key, state), kwargs
    expire=86400, and the exact 6-key state dict."""
    reg = ServiceRegistry(redis_client=_Redis())
    reg.register(
        _svc(
            enabled=False,
            failure_count=3,
            last_failure_at=DT,
            last_restart_at=DT,
            restart_count=5,
            status=ContainerServiceStatus.UNHEALTHY,
        )
    )
    with logs() as recs:
        asyncio.run(reg.persist_state("svc-a"))
    assert reg._redis.calls == [
        (
            "set",
            (
                "orchestrator:service:svc-a:state",
                {
                    "enabled": False,
                    "failure_count": 3,
                    "last_failure_at": DT_ISO,
                    "last_restart_at": DT_ISO,
                    "restart_count": 5,
                    "status": "unhealthy",
                },
            ),
            {"expire": 86400},
        )
    ]
    assert REDIS_KEY_PREFIX == "orchestrator:service"
    _pin(
        recs,
        [(logging.DEBUG, "Persisted service state to Redis", {"service_name": "svc-a"})],
    )


def test_k48_persist_state_empty_dates_exact_call() -> None:
    """p14/p18: the FALSY-timestamp world - shipped writes None in both slots;
    the `or True` mutants reach .isoformat() on None (AttributeError) inside
    the state build, before any call happens."""
    reg = ServiceRegistry(redis_client=_Redis())
    reg.register(_svc())
    with logs() as recs:
        asyncio.run(reg.persist_state("svc-a"))
    assert reg._redis.calls == [
        (
            "set",
            (
                "orchestrator:service:svc-a:state",
                {
                    "enabled": True,
                    "failure_count": 0,
                    "last_failure_at": None,
                    "last_restart_at": None,
                    "restart_count": 0,
                    "status": "running",
                },
            ),
            {"expire": 86400},
        )
    ]
    assert len(recs) == 1


def test_k48_persist_state_error_warning() -> None:
    """The except branch is ONE WARNING with the measured str(e) and NO
    success DEBUG after it."""
    reg = ServiceRegistry(redis_client=_Redis(raises=RuntimeError("redis down")))
    reg.register(_svc())
    with logs() as recs:
        asyncio.run(reg.persist_state("svc-a"))
    _pin(
        recs,
        [
            (
                logging.WARNING,
                "Failed to persist service state to Redis",
                {"service_name": "svc-a", "error": "redis down"},
            )
        ],
    )


# ===========================================================================
# ServiceRegistry._apply_state_to_service   (survivors a3, a5, a8, a11, a13,
#                                            a16, a19, a21, a24, a31, a39)
# ===========================================================================


def test_k48_apply_state_empty_state_defaults_silent() -> None:
    """EMPTY state dict: shipped fills enabled=True / counts=0 / both
    timestamps None and leaves status untouched, SILENTLY. The get-default
    twins write None or 1; the `or True` guards call fromisoformat(None)."""
    reg = ServiceRegistry(redis_client=None)
    svc = _svc(
        enabled=False,
        failure_count=9,
        restart_count=4,
        last_failure_at=DT,
        last_restart_at=DT,
        status=ContainerServiceStatus.RUNNING,
    )
    with logs() as recs:
        reg._apply_state_to_service(svc, {}, "svc-a")
    assert recs == []
    assert svc.enabled is True
    assert svc.failure_count == 0
    assert svc.restart_count == 0
    assert svc.last_failure_at is None
    assert svc.last_restart_at is None
    assert svc.status is ContainerServiceStatus.RUNNING


def test_k48_apply_state_explicit_values_kept() -> None:
    """Explicit present values (incl. enabled=False and 0-counts) must survive
    - the polarity/default twins flip these from the other side."""
    reg = ServiceRegistry(redis_client=None)
    svc = _svc(enabled=True, failure_count=9, restart_count=4)
    reg._apply_state_to_service(
        svc,
        {
            "enabled": False,
            "failure_count": 0,
            "restart_count": 0,
            "last_failure_at": DT_ISO,
            "last_restart_at": DT_ISO,
        },
        "svc-a",
    )
    assert svc.enabled is False
    assert svc.failure_count == 0
    assert svc.restart_count == 0
    assert svc.last_failure_at == DT
    assert svc.last_restart_at == DT


def test_k48_apply_state_valid_status_parsed() -> None:
    reg = ServiceRegistry(redis_client=None)
    svc = _svc(status=ContainerServiceStatus.RUNNING)
    with logs() as recs:
        reg._apply_state_to_service(svc, {"status": "disabled"}, "svc-a")
    assert recs == []
    assert svc.status is ContainerServiceStatus.DISABLED


def test_k48_apply_state_absent_status_silent_untouched() -> None:
    reg = ServiceRegistry(redis_client=None)
    svc = _svc(status=ContainerServiceStatus.STARTING)
    with logs() as recs:
        reg._apply_state_to_service(svc, {}, "svc-a")
    assert recs == []
    assert svc.status is ContainerServiceStatus.STARTING


def test_k48_apply_state_invalid_status_warning() -> None:
    """Unparseable status: ONE WARNING pinning BOTH extras by name, status
    left untouched, and NO extra record."""
    reg = ServiceRegistry(redis_client=None)
    svc = _svc(status=ContainerServiceStatus.RUNNING)
    with logs() as recs:
        reg._apply_state_to_service(svc, {"status": "BOGUS"}, "svc-a")
    _pin(
        recs,
        [
            (
                logging.WARNING,
                "Invalid status in Redis state",
                {"service_name": "svc-a", "status": "BOGUS"},
            )
        ],
    )
    assert svc.status is ContainerServiceStatus.RUNNING


def test_k48_apply_state_falsy_status_untouched_silent() -> None:
    reg = ServiceRegistry(redis_client=None)
    svc = _svc(status=ContainerServiceStatus.STOPPED)
    with logs() as recs:
        reg._apply_state_to_service(svc, {"status": ""}, "svc-a")
    assert recs == []
    assert svc.status is ContainerServiceStatus.STOPPED


# ===========================================================================
# ServiceRegistry.load_state   (survivors l2, l6, l8, l10..l18, l24, l28..l36)
# ===========================================================================


def test_k48_load_state_no_redis_log() -> None:
    reg = ServiceRegistry(redis_client=None)
    reg.register(_svc())
    with logs() as recs:
        assert asyncio.run(reg.load_state("svc-a")) is None
    _pin(
        recs,
        [(logging.DEBUG, "No Redis client, skipping load_state for svc-a", {})],
    )


def test_k48_load_state_absent_service_silent() -> None:
    reg = ServiceRegistry(redis_client=_Redis(payload={"enabled": False}))
    with logs() as recs:
        asyncio.run(reg.load_state("nope"))
    assert recs == []
    assert reg._redis.calls == []


def test_k48_load_state_no_payload_log() -> None:
    """Falsy payload (None) -> the single 'No Redis state found' DEBUG and NO
    mutation of the service."""
    reg = ServiceRegistry(redis_client=_Redis(payload=None))
    svc = _svc(failure_count=7, status=ContainerServiceStatus.RUNNING)
    reg.register(svc)
    with logs() as recs:
        asyncio.run(reg.load_state("svc-a"))
    _pin(
        recs,
        [(logging.DEBUG, "No Redis state found for service", {"service_name": "svc-a"})],
    )
    assert svc.failure_count == 7
    assert svc.status is ContainerServiceStatus.RUNNING


def test_k48_load_state_dict_payload_exact() -> None:
    """Dict payload: the get call is (key,) alone, every field lands, and the
    success DEBUG is the ONLY record."""
    reg = ServiceRegistry(
        redis_client=_Redis(
            payload={
                "enabled": False,
                "failure_count": 3,
                "last_failure_at": DT_ISO,
                "last_restart_at": DT_ISO,
                "restart_count": 5,
                "status": "unhealthy",
            }
        )
    )
    svc = _svc()
    reg.register(svc)
    with logs() as recs:
        asyncio.run(reg.load_state("svc-a"))
    assert reg._redis.calls == [("get", ("orchestrator:service:svc-a:state",), {})]
    assert svc.enabled is False
    assert svc.failure_count == 3
    assert svc.restart_count == 5
    assert svc.last_failure_at == DT
    assert svc.last_restart_at == DT
    assert svc.status is ContainerServiceStatus.UNHEALTHY
    _pin(
        recs,
        [(logging.DEBUG, "Loaded service state from Redis", {"service_name": "svc-a"})],
    )


def test_k48_load_state_str_payload_json_decoded() -> None:
    reg = ServiceRegistry(
        redis_client=_Redis(payload=json.dumps({"failure_count": 3, "enabled": False}))
    )
    svc = _svc()
    reg.register(svc)
    with logs() as recs:
        asyncio.run(reg.load_state("svc-a"))
    assert svc.failure_count == 3
    assert svc.enabled is False
    _pin(
        recs,
        [(logging.DEBUG, "Loaded service state from Redis", {"service_name": "svc-a"})],
    )


def test_k48_load_state_invalid_status_warning_then_success() -> None:
    """l24: the WARNING rides _apply's `name` argument, so it must read
    svc-a; the ordered pair (WARNING, DEBUG) is pinned in full."""
    reg = ServiceRegistry(redis_client=_Redis(payload={"status": "BOGUS"}))
    svc = _svc(status=ContainerServiceStatus.RUNNING)
    reg.register(svc)
    with logs() as recs:
        asyncio.run(reg.load_state("svc-a"))
    _pin(
        recs,
        [
            (
                logging.WARNING,
                "Invalid status in Redis state",
                {"service_name": "svc-a", "status": "BOGUS"},
            ),
            (logging.DEBUG, "Loaded service state from Redis", {"service_name": "svc-a"}),
        ],
    )
    assert svc.status is ContainerServiceStatus.RUNNING


def test_k48_load_state_json_decode_error_warning() -> None:
    """The str(e) text is measured: 'Expecting value: line 1 column 1
    (char 0)'."""
    reg = ServiceRegistry(redis_client=_Redis(payload="not-json"))
    svc = _svc(failure_count=7)
    reg.register(svc)
    with logs() as recs:
        asyncio.run(reg.load_state("svc-a"))
    _pin(
        recs,
        [
            (
                logging.WARNING,
                "Failed to parse Redis state JSON",
                {
                    "service_name": "svc-a",
                    "error": "Expecting value: line 1 column 1 (char 0)",
                },
            )
        ],
    )
    assert svc.failure_count == 7


def test_k48_load_state_generic_error_warning() -> None:
    reg = ServiceRegistry(redis_client=_Redis(raises=RuntimeError("redis down")))
    svc = _svc(failure_count=7)
    reg.register(svc)
    with logs() as recs:
        asyncio.run(reg.load_state("svc-a"))
    _pin(
        recs,
        [
            (
                logging.WARNING,
                "Failed to load service state from Redis",
                {"service_name": "svc-a", "error": "redis down"},
            )
        ],
    )
    assert svc.failure_count == 7


# ===========================================================================
# ServiceRegistry.load_all_state   (survivors o4, o5, o7..o12)
# ===========================================================================


def test_k48_load_all_state_two_names_exact_sequence() -> None:
    """Full ordered pin: per-name skip DEBUGs in registration order, then the
    summary INFO with service_count == 2."""
    reg = ServiceRegistry(redis_client=None)
    reg.register(_svc(name="svc-a"))
    reg.register(_svc(name="svc-b"))
    with logs() as recs:
        asyncio.run(reg.load_all_state())
    _pin(
        recs,
        [
            (
                logging.DEBUG,
                "No Redis client, skipping load_state for svc-a",
                {},
            ),
            (
                logging.DEBUG,
                "No Redis client, skipping load_state for svc-b",
                {},
            ),
            (
                logging.INFO,
                "Loaded state for all services from Redis",
                {"service_count": 2},
            ),
        ],
    )


def test_k48_load_all_state_empty_registry_count_zero() -> None:
    reg = ServiceRegistry(redis_client=None)
    with logs() as recs:
        asyncio.run(reg.load_all_state())
    _pin(
        recs,
        [
            (
                logging.INFO,
                "Loaded state for all services from Redis",
                {"service_count": 0},
            )
        ],
    )


# ===========================================================================
# ServiceRegistry.clear_state   (survivors s4, s5, s6, s7, s8, s9, s10, s11,
#                                s12)
# ===========================================================================


def test_k48_clear_state_exact_call_and_log() -> None:
    reg = ServiceRegistry(redis_client=_Redis())
    with logs() as recs:
        asyncio.run(reg.clear_state("svc-a"))
    assert reg._redis.calls == [("delete", ("orchestrator:service:svc-a:state",), {})]
    _pin(
        recs,
        [(logging.DEBUG, "Cleared service state from Redis", {"service_name": "svc-a"})],
    )


def test_k48_clear_state_no_redis_silent() -> None:
    reg = ServiceRegistry(redis_client=None)
    with logs() as recs:
        assert asyncio.run(reg.clear_state("svc-a")) is None
    assert recs == []


def test_k48_clear_state_error_warning() -> None:
    reg = ServiceRegistry(redis_client=_Redis(raises=RuntimeError("redis down")))
    with logs() as recs:
        asyncio.run(reg.clear_state("svc-a"))
    _pin(
        recs,
        [
            (
                logging.WARNING,
                "Failed to clear service state from Redis",
                {"service_name": "svc-a", "error": "redis down"},
            )
        ],
    )


# ===========================================================================
# Module-level singleton   (survivors k2, k4, k5, k6, k7, k8;
#                           q2, q3, q4, q5)
# ===========================================================================


def test_k48_get_service_registry_builds_once_with_redis() -> None:
    """k2/k4: the singleton must hold the client init_redis() RETURNED (the
    mutants pass None); a 2nd call returns the SAME object and logs nothing."""
    sentinel = object()

    async def fake_init_redis() -> Any:
        return sentinel

    import backend.core.redis as redis_mod

    old = redis_mod.init_redis
    ms_mod.reset_service_registry()
    with logs() as recs:
        recs.clear()
        redis_mod.init_redis = fake_init_redis
        try:
            first = asyncio.run(ms_mod.get_service_registry())
            created = list(recs)
            second = asyncio.run(ms_mod.get_service_registry())
        finally:
            redis_mod.init_redis = old
    assert first._redis is sentinel
    assert second is first
    _pin(created, [(logging.INFO, "Created global ServiceRegistry singleton", {})])
    assert [r for r in recs if r is not created[0]] == []
    ms_mod.reset_service_registry()


def test_k48_get_service_registry_creates_when_global_none() -> None:
    """The creation branch is entered iff the module global is None (the
    guard-polarity mutants skip creation entirely)."""
    sentinel = object()

    async def fake_init_redis() -> Any:
        return sentinel

    import backend.core.redis as redis_mod

    old = redis_mod.init_redis
    ms_mod.reset_service_registry()
    assert ms_mod._service_registry is None
    with logs() as recs:
        redis_mod.init_redis = fake_init_redis
        try:
            reg = asyncio.run(ms_mod.get_service_registry())
        finally:
            redis_mod.init_redis = old
    assert ms_mod._service_registry is reg
    assert reg._redis is sentinel
    assert [(r.levelno, r.getMessage()) for r in recs] == [
        (logging.INFO, "Created global ServiceRegistry singleton")
    ]
    ms_mod.reset_service_registry()


def test_k48_reset_service_registry_clears_and_logs() -> None:
    """q-family: reset() empties the global and emits EXACTLY one DEBUG."""
    sentinel = object()
    ms_mod._service_registry = sentinel
    with logs() as recs:
        assert ms_mod.reset_service_registry() is None
    _pin(recs, [(logging.DEBUG, "Reset global ServiceRegistry singleton", {})])
    assert ms_mod._service_registry is None


def test_k48_reset_service_registry_idempotent_when_none() -> None:
    ms_mod.reset_service_registry()
    with logs() as recs:
        ms_mod.reset_service_registry()
    _pin(recs, [(logging.DEBUG, "Reset global ServiceRegistry singleton", {})])
    assert ms_mod._service_registry is None
