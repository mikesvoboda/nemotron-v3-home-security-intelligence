# TARGET-MODULE: backend.services.orchestrator.registry
"""Battery AR for mutation campaign #42 — orchestrator/registry.py.

Kill-craft (carried from AQ #41): the module logs every mutation-relevant
observable through ``extra=`` KWARGS, so the recorder stores the full
``(method, args, kwargs)`` tuple and every row pins FULL tuple equality —
key renames, XX-wraps, upper/lower twins, str(None) and dropped ``extra``
all die on the dict equality, message twins on the args equality.

Semantic rows beyond the logs: the persist state dict is pinned WHOLE
(both isoformat ternaries non-None in one row AND both None in another —
the m21/m25 ``and False`` twins), the Redis key string is pinned exactly
(the m5 ``key = None`` and m7 ``get(None)`` twins), ``_apply_loaded_state``
runs an ABSENT-keys row over a service pre-set to non-defaults (the
trailing-comma ``.get(key, )`` mutants become 2-arg ``.get(key)`` and RAISE
KeyError — the shipped default is what survives), and the singleton rows
patch ``init_redis`` on its SOURCE module because get_service_registry
imports it function-locally (AQ capture (5): patch where it is imported AT
CALL TIME; a call-count pin kills the ``is None`` guard relax).

Every ctor-written field is non-default in the pin rows (AQ capture (7):
a default-valued fixture field makes the ->default mutant invisible).
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import UTC, datetime
from unittest.mock import patch

from backend.services.orchestrator import registry as reg_mod
from backend.services.orchestrator.enums import ContainerServiceStatus, ServiceCategory
from backend.services.orchestrator.models import ManagedService
from backend.services.orchestrator.registry import ServiceRegistry

FIXED = datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC)
FIXED_ISO = "2026-03-04T05:06:07+00:00"
KEY_SVC = "orchestrator:service:svc:state"
# measured: json.loads("{{bad") raises with EXACTLY this message
JSON_ERR = "Expecting property name enclosed in double quotes: line 1 column 2 (char 1)"


class Rec:
    """Logger stand-in storing (level, args, kwargs) — full-tuple equality."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []

    def debug(self, *a, **k) -> None:
        self.calls.append(("debug", a, k))

    def info(self, *a, **k) -> None:
        self.calls.append(("info", a, k))

    def warning(self, *a, **k) -> None:
        self.calls.append(("warning", a, k))

    def error(self, *a, **k) -> None:
        self.calls.append(("error", a, k))

    def critical(self, *a, **k) -> None:
        self.calls.append(("critical", a, k))


@contextmanager
def logged():
    """Patch the registry module logger with a fresh Rec."""
    rec = Rec()
    with patch.object(reg_mod, "logger", rec):
        yield rec


class Redis:
    """Recording Redis stand-in with per-method failure injection."""

    def __init__(self, get_value=None, get_exc=None, set_exc=None, del_exc=None) -> None:
        self.calls: list[tuple] = []
        self.get_value = get_value
        self.get_exc = get_exc
        self.set_exc = set_exc
        self.del_exc = del_exc

    async def set(self, key, value):
        self.calls.append(("set", key, value))
        if self.set_exc is not None:
            raise self.set_exc
        return True

    async def get(self, key):
        self.calls.append(("get", key))
        if self.get_exc is not None:
            raise self.get_exc
        return self.get_value

    async def delete(self, key):
        self.calls.append(("delete", key))
        if self.del_exc is not None:
            raise self.del_exc
        return 1


def svc(name="svc", **over) -> ManagedService:
    """Fully-populated ManagedService — every loggable field non-default."""
    base = {
        "name": name,
        "display_name": "Svc Display",
        "container_id": "cid-1",
        "image": "img:1",
        "port": 8081,
        "category": ServiceCategory.INFRASTRUCTURE,
        "status": ContainerServiceStatus.RUNNING,
        "enabled": False,
        "warmth_state": "cold",
        "failure_count": 4,
        "last_failure_at": FIXED,
        "last_restart_at": FIXED,
        "restart_count": 2,
    }
    base.update(over)
    return ManagedService(**base)


def found(name="svc") -> dict:
    """The exact Redis state payload shipped persist_state writes for svc()."""
    return {
        "enabled": False,
        "failure_count": 4,
        "last_failure_at": FIXED_ISO,
        "last_restart_at": FIXED_ISO,
        "restart_count": 2,
        "status": "running",
    }


# ---------------------------------------------------------------- registration


def test_register_stores_identity_and_logs_full_tuple() -> None:
    reg = ServiceRegistry(redis_client=None)
    s = svc()
    with logged() as rec:
        reg.register(s)
    assert reg.get("svc") is s
    assert rec.calls == [
        (
            "debug",
            ("Registered service",),
            {"extra": {"service_name": "svc", "category": "infrastructure"}},
        )
    ]


def test_unregister_removes_logs_and_stays_silent_when_absent() -> None:
    reg = ServiceRegistry(redis_client=None)
    s = svc()
    reg.register(s)
    with logged() as rec:
        reg.unregister("svc")
        reg.unregister("absent")
    assert reg.get("svc") is None
    assert rec.calls == [("debug", ("Unregistered service",), {"extra": {"service_name": "svc"}})]


def test_getters_snapshot_stores_with_identity_and_order() -> None:
    reg = ServiceRegistry(redis_client=None)
    a = svc("a", category=ServiceCategory.AI, enabled=True)
    b = svc("b", category=ServiceCategory.MONITORING, enabled=False)
    reg.register(a)
    reg.register(b)
    assert reg.get("a") is a
    assert reg.get("missing") is None
    assert reg.get_all() == [a, b]
    assert isinstance(reg.get_all(), list)
    assert reg.list_names() == ["a", "b"]
    assert isinstance(reg.list_names(), list)
    assert reg.get_by_category(ServiceCategory.AI) == [a]
    assert reg.get_by_category(ServiceCategory.INFRASTRUCTURE) == []
    assert reg.get_enabled() == [a]
    assert reg.get_enabled_services() == [a]


# -------------------------------------------------------------- state updates


def test_update_status_mutates_and_logs_found_and_absent() -> None:
    reg = ServiceRegistry(redis_client=None)
    s = svc()
    reg.register(s)
    with logged() as rec:
        reg.update_status("svc", ContainerServiceStatus.UNHEALTHY)
        reg.update_status("absent", ContainerServiceStatus.STOPPED)
    assert s.status is ContainerServiceStatus.UNHEALTHY
    assert rec.calls == [
        (
            "debug",
            ("Updated service status",),
            {"extra": {"service_name": "svc", "status": "unhealthy"}},
        )
    ]


def test_increment_failure_returns_post_count_and_logs() -> None:
    reg = ServiceRegistry(redis_client=None)
    s = svc()
    reg.register(s)
    with logged() as rec:
        got = reg.increment_failure("svc")
        absent = reg.increment_failure("absent")
    assert (got, absent) == (5, 0)
    assert s.failure_count == 5
    assert s.last_failure_at is not None and s.last_failure_at.tzinfo is not None
    assert rec.calls == [
        (
            "debug",
            ("Incremented failure count",),
            {"extra": {"service_name": "svc", "failure_count": 5}},
        )
    ]


def test_increment_failures_alias_still_mutates_service() -> None:
    reg = ServiceRegistry(redis_client=None)
    s = svc()
    reg.register(s)
    with logged():
        assert reg.increment_failures("svc") is None
    assert s.failure_count == 5


def test_reset_failures_clears_both_fields_and_logs() -> None:
    reg = ServiceRegistry(redis_client=None)
    s = svc()
    reg.register(s)
    with logged() as rec:
        reg.reset_failures("svc")
        reg.reset_failures("absent")
    assert (s.failure_count, s.last_failure_at) == (0, None)
    assert rec.calls == [("debug", ("Reset failure tracking",), {"extra": {"service_name": "svc"}})]


def test_record_restart_increments_logs_and_stamps_tz_aware() -> None:
    reg = ServiceRegistry(redis_client=None)
    s = svc()
    reg.register(s)
    with logged() as rec:
        reg.record_restart("svc")
        reg.record_restart("absent")
    assert s.restart_count == 3
    assert s.last_restart_at is not None and s.last_restart_at.tzinfo is not None
    assert rec.calls == [
        (
            "debug",
            ("Recorded restart",),
            {"extra": {"service_name": "svc", "restart_count": 3}},
        )
    ]


def test_set_enabled_logs_both_polarities_and_absent_silent() -> None:
    reg = ServiceRegistry(redis_client=None)
    s = svc()  # enabled=False already
    reg.register(s)
    with logged() as rec:
        reg.set_enabled("svc", False)
        reg.set_enabled("svc", True)
        reg.set_enabled("absent", True)
    assert s.enabled is True
    assert rec.calls == [
        ("debug", ("Set service enabled",), {"extra": {"service_name": "svc", "enabled": False}}),
        ("debug", ("Set service enabled",), {"extra": {"service_name": "svc", "enabled": True}}),
    ]


def test_update_container_id_logs_value_and_none_and_absent() -> None:
    reg = ServiceRegistry(redis_client=None)
    s = svc()
    reg.register(s)
    with logged() as rec:
        reg.update_container_id("svc", None)
        reg.update_container_id("absent", "zz")
    assert s.container_id is None
    assert rec.calls == [
        (
            "debug",
            ("Updated container ID",),
            {"extra": {"service_name": "svc", "container_id": None}},
        )
    ]


def test_update_warmth_state_logs_and_absent_silent() -> None:
    reg = ServiceRegistry(redis_client=None)
    s = svc()
    reg.register(s)
    with logged() as rec:
        reg.update_warmth_state("svc", "warming")
        reg.update_warmth_state("absent", "warm")
    assert s.warmth_state == "warming"
    assert rec.calls == [
        (
            "debug",
            ("Updated warmth state",),
            {"extra": {"service_name": "svc", "warmth_state": "warming"}},
        )
    ]


def test_get_ai_warmth_states_filters_ai_services_only() -> None:
    reg = ServiceRegistry(redis_client=None)
    reg.register(svc("ai1", category=ServiceCategory.AI, warmth_state="warm"))
    reg.register(svc("ai2", category=ServiceCategory.AI, warmth_state="cold"))
    reg.register(svc("db", category=ServiceCategory.INFRASTRUCTURE, warmth_state="warm"))
    got = reg.get_ai_warmth_states()
    assert got == {"ai1": "warm", "ai2": "cold"}
    assert isinstance(got, dict)


# ------------------------------------------------------------- redis: persist


async def test_persist_state_no_redis_logs_skip_and_sends_nothing() -> None:
    reg = ServiceRegistry(redis_client=None)
    reg.register(svc())
    with logged() as rec:
        assert await reg.persist_state("svc") is None
    assert rec.calls == [
        ("debug", ("No Redis client, skipping persist",), {"extra": {"service_name": "svc"}})
    ]


async def test_persist_state_absent_service_is_silent_noop() -> None:
    redis = Redis()
    reg = ServiceRegistry(redis_client=redis)
    with logged() as rec:
        await reg.persist_state("absent")
    assert (redis.calls, rec.calls) == ([], [])


async def test_persist_state_success_sends_exact_key_and_whole_state_dict() -> None:
    redis = Redis()
    reg = ServiceRegistry(redis_client=redis)
    reg.register(svc())
    with logged() as rec:
        await reg.persist_state("svc")
    assert redis.calls == [("set", KEY_SVC, found())]
    assert rec.calls == [
        ("debug", ("Persisted service state to Redis",), {"extra": {"service_name": "svc"}})
    ]


async def test_persist_state_null_datetimes_serialize_as_none() -> None:
    redis = Redis()
    reg = ServiceRegistry(redis_client=redis)
    reg.register(
        svc(
            enabled=True,
            failure_count=0,
            last_failure_at=None,
            last_restart_at=None,
            restart_count=7,
            status=ContainerServiceStatus.DISABLED,
        )
    )
    with logged():
        await reg.persist_state("svc")
    assert redis.calls == [
        (
            "set",
            KEY_SVC,
            {
                "enabled": True,
                "failure_count": 0,
                "last_failure_at": None,
                "last_restart_at": None,
                "restart_count": 7,
                "status": "disabled",
            },
        )
    ]


async def test_persist_state_redis_error_warns_full_tuple() -> None:
    redis = Redis(set_exc=RuntimeError("redis down"))
    reg = ServiceRegistry(redis_client=redis)
    reg.register(svc())
    with logged() as rec:
        await reg.persist_state("svc")
    assert redis.calls == [("set", KEY_SVC, found())]
    assert rec.calls == [
        (
            "warning",
            ("Failed to persist service state to Redis",),
            {"extra": {"service_name": "svc", "error": "redis down"}},
        )
    ]


# ---------------------------------------------------------------- redis: load


def _state(**over) -> dict:
    base = {
        "enabled": True,
        "failure_count": 3,
        "last_failure_at": FIXED_ISO,
        "last_restart_at": FIXED_ISO,
        "restart_count": 8,
        "status": "unhealthy",
    }
    base.update(over)
    return base


async def test_load_state_no_redis_logs_skip() -> None:
    reg = ServiceRegistry(redis_client=None)
    reg.register(svc())
    with logged() as rec:
        await reg.load_state("svc")
    assert rec.calls == [
        ("debug", ("No Redis client, skipping load",), {"extra": {"service_name": "svc"}})
    ]


async def test_load_state_absent_service_never_touches_redis() -> None:
    redis = Redis(get_value=_state())
    reg = ServiceRegistry(redis_client=redis)
    with logged() as rec:
        await reg.load_state("absent")
    assert (redis.calls, rec.calls) == ([], [])


async def test_load_state_missing_value_logs_debug_and_keeps_service() -> None:
    s = svc()
    redis = Redis(get_value=None)
    reg = ServiceRegistry(redis_client=redis)
    reg.register(s)
    with logged() as rec:
        await reg.load_state("svc")
    assert redis.calls == [("get", KEY_SVC)]
    assert (s.failure_count, s.restart_count, s.status) == (4, 2, ContainerServiceStatus.RUNNING)
    assert rec.calls == [
        ("debug", ("No Redis state found for service",), {"extra": {"service_name": "svc"}})
    ]


async def test_load_state_empty_dict_counts_as_missing() -> None:
    redis = Redis(get_value={})
    reg = ServiceRegistry(redis_client=redis)
    reg.register(svc())
    with logged() as rec:
        await reg.load_state("svc")
    assert rec.calls == [
        ("debug", ("No Redis state found for service",), {"extra": {"service_name": "svc"}})
    ]


async def test_load_state_json_string_applies_every_field() -> None:
    s = svc()
    redis = Redis(get_value=json.dumps(_state()))
    reg = ServiceRegistry(redis_client=redis)
    reg.register(s)
    with logged() as rec:
        await reg.load_state("svc")
    assert redis.calls == [("get", KEY_SVC)]
    assert s.enabled is True
    assert s.failure_count == 3
    assert s.restart_count == 8
    assert s.last_failure_at == FIXED
    assert s.last_restart_at == FIXED
    assert s.status is ContainerServiceStatus.UNHEALTHY
    assert rec.calls == [
        ("debug", ("Loaded service state from Redis",), {"extra": {"service_name": "svc"}})
    ]


async def test_load_state_dict_payload_skips_json_parses_identical() -> None:
    s = svc()
    redis = Redis(get_value=_state())
    reg = ServiceRegistry(redis_client=redis)
    reg.register(s)
    with logged() as rec:
        await reg.load_state("svc")
    assert (s.failure_count, s.restart_count, s.last_failure_at) == (3, 8, FIXED)
    assert s.status is ContainerServiceStatus.UNHEALTHY
    assert rec.calls == [
        ("debug", ("Loaded service state from Redis",), {"extra": {"service_name": "svc"}})
    ]


async def test_load_state_absent_keys_apply_defaults_over_nondefaults() -> None:
    # trailing-comma `.get(key, )` mutants become 2-arg .get(key) -> KeyError
    # swallowed by load_state -> warning site; shipped keeps defaults applied.
    # {} short-circuits at `if not state`, so feed a truthy dict whose TARGET
    # keys are all ABSENT — _apply_loaded_state must apply shipped defaults.
    s = svc()
    redis = Redis(get_value={"other": 1})
    reg = ServiceRegistry(redis_client=redis)
    reg.register(s)
    with logged() as rec:
        await reg.load_state("svc")
    assert s.enabled is True  # default True over pre-set False
    assert s.failure_count == 0  # default 0 over pre-set 4
    assert s.restart_count == 0  # default 0 over pre-set 2
    assert s.last_failure_at is None
    assert s.last_restart_at is None
    assert s.status is ContainerServiceStatus.RUNNING  # no "status" key -> untouched
    assert rec.calls == [
        ("debug", ("Loaded service state from Redis",), {"extra": {"service_name": "svc"}})
    ]


async def test_load_state_invalid_status_warns_and_keeps_previous() -> None:
    s = svc()
    redis = Redis(get_value=_state(status="bogus"))
    reg = ServiceRegistry(redis_client=redis)
    reg.register(s)
    with logged() as rec:
        await reg.load_state("svc")
    assert s.status is ContainerServiceStatus.RUNNING
    assert rec.calls == [
        (
            "warning",
            ("Invalid status in Redis state",),
            {"extra": {"service_name": "svc", "status": "bogus"}},
        ),
        ("debug", ("Loaded service state from Redis",), {"extra": {"service_name": "svc"}}),
    ]


async def test_load_state_bad_json_warns_parse_site_full_tuple() -> None:
    redis = Redis(get_value="{{bad")
    reg = ServiceRegistry(redis_client=redis)
    reg.register(svc())
    with logged() as rec:
        await reg.load_state("svc")
    assert rec.calls == [
        (
            "warning",
            ("Failed to parse Redis state JSON",),
            {"extra": {"service_name": "svc", "error": JSON_ERR}},
        )
    ]


async def test_load_state_redis_error_warns_generic_site_full_tuple() -> None:
    redis = Redis(get_exc=RuntimeError("net down"))
    reg = ServiceRegistry(redis_client=redis)
    reg.register(svc())
    with logged() as rec:
        await reg.load_state("svc")
    assert rec.calls == [
        (
            "warning",
            ("Failed to load service state from Redis",),
            {"extra": {"service_name": "svc", "error": "net down"}},
        )
    ]


async def test_load_all_state_loads_each_name_and_logs_count() -> None:
    reg = ServiceRegistry(redis_client=None)
    reg.register(svc("a"))
    reg.register(svc("b"))
    with logged() as rec:
        await reg.load_all_state()
    assert rec.calls == [
        ("debug", ("No Redis client, skipping load",), {"extra": {"service_name": "a"}}),
        ("debug", ("No Redis client, skipping load",), {"extra": {"service_name": "b"}}),
        ("info", ("Loaded state for all services from Redis",), {"extra": {"service_count": 2}}),
    ]


async def test_load_all_state_empty_registry_logs_zero() -> None:
    reg = ServiceRegistry(redis_client=None)
    with logged() as rec:
        await reg.load_all_state()
    assert rec.calls == [
        ("info", ("Loaded state for all services from Redis",), {"extra": {"service_count": 0}})
    ]


async def test_load_all_state_real_redis_drives_per_name_gets() -> None:
    redis = Redis(get_value=None)
    reg = ServiceRegistry(redis_client=redis)
    reg.register(svc("a"))
    reg.register(svc("b"))
    with logged() as rec:
        await reg.load_all_state()
    assert redis.calls == [
        ("get", "orchestrator:service:a:state"),
        ("get", "orchestrator:service:b:state"),
    ]
    assert rec.calls[-1] == (
        "info",
        ("Loaded state for all services from Redis",),
        {"extra": {"service_count": 2}},
    )


# --------------------------------------------------------------- redis: clear


async def test_clear_state_success_deletes_exact_key_and_logs() -> None:
    redis = Redis()
    reg = ServiceRegistry(redis_client=redis)
    with logged() as rec:
        await reg.clear_state("svc")
    assert redis.calls == [("delete", KEY_SVC)]
    assert rec.calls == [
        ("debug", ("Cleared service state from Redis",), {"extra": {"service_name": "svc"}})
    ]


async def test_clear_state_no_redis_is_total_silence() -> None:
    reg = ServiceRegistry(redis_client=None)
    with logged() as rec:
        await reg.clear_state("svc")
    assert rec.calls == []


async def test_clear_state_error_warns_full_tuple() -> None:
    redis = Redis(del_exc=RuntimeError("gone"))
    reg = ServiceRegistry(redis_client=redis)
    with logged() as rec:
        await reg.clear_state("svc")
    assert rec.calls == [
        (
            "warning",
            ("Failed to clear service state from Redis",),
            {"extra": {"service_name": "svc", "error": "gone"}},
        )
    ]


# --------------------------------------------------------------- singleton


async def test_get_service_registry_builds_once_wired_to_init_redis() -> None:
    import backend.core.redis as core_redis

    client = object()
    calls: list[int] = []

    async def fake_init():
        calls.append(1)
        return client

    reg_mod.reset_service_registry()
    try:
        with logged() as rec, patch.object(core_redis, "init_redis", new=fake_init):
            first = await reg_mod.get_service_registry()
            second = await reg_mod.get_service_registry()
        assert first is second
        assert isinstance(first, ServiceRegistry)
        assert first._redis is client
        assert calls == [1]
        assert rec.calls == [
            ("info", ("Created global ServiceRegistry singleton",), {}),
        ]
    finally:
        reg_mod.reset_service_registry()


def test_reset_service_registry_clears_global_and_logs() -> None:
    with logged() as rec:
        reg_mod.reset_service_registry()
    assert reg_mod._service_registry is None
    assert rec.calls == [
        ("debug", ("Reset global ServiceRegistry singleton",), {}),
    ]
