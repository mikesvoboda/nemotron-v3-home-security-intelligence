# WP4.4 Triage Dossier — backend/services/managed_service.py

**Survivors:** 179 of 485 mutants (290 killed, 16 untested). Extracted from
`mutants/backend/services/managed_service.py.meta` (`exit_code_by_key == 0`), diffs via
`uv run mutmut show <key>` (all 179 succeeded; harvested copy at `/tmp/wp25/wp44-triage/ms-diffs.txt`).

**Covering test file (sole):** `backend/tests/unit/services/test_managed_service.py`
(key tests: `test_to_dict`:143, `test_from_dict`:177, `test_from_dict_minimal`:212,
`test_from_config`:231, `test_roundtrip_serialization`:290, `test_increment_failure`:547,
`test_record_restart`:619, `test_persist_state`:700, `test_load_state`:766,
`test_load_all_state`:851, singleton test:908). Source regions:
`managed_service.py`:178-179 (to_dict isoformat), :198-228 (from_dict parse + defaults),
:253-267 (from_config), :444-452 (increment_failure), :487-489 (record_restart),
:552-569 (persist_state state dict + TTL), :587-595 (_apply_state_to_service defaults),
:629-643 (load_state key + apply), :714-719 (singleton wiring).

**Balance check:** cluster counts sum to 179. TEST-GAP 57 / EQUIVALENT 77 / LOW-VALUE 45.

---

## Cluster table

| # | Cluster (pattern) | n | Class | Example keys (suffix) | Kill test |
|---|-------------------|---|-------|----------------------|-----------|
| 1 | Debug-log message/`extra` key **string edits** (`"X"`→`"XX X XX"`, case flips) across 13 registry/singleton functions | 76 | EQUIVALENT | `…unregister__mutmut_6`, `…load_state__mutmut_14`, `x_reset_service_registry__mutmut_3` | — (pure text, debug level, no consumer) |
| 2 | Debug/info-log **structural arg removal** (`logger.debug(None,…)`, `extra=None`, drop `extra=`) across the same functions | 44 | LOW-VALUE | `…unregister__mutmut_2`, `…update_status__mutmut_4`, `…persist_state__mutmut_31` | — (asserting debug-log payloads is not worth pinning) |
| 3 | `from_dict`: **`data.get(k, default)` default broken** for 6 numeric/bool fields (`failure_count`, `restart_count`, `max_failures`, `restart_backoff_base`, `restart_backoff_max`, `startup_grace_period`) — flipped (0→1, 5→6, 5.0→6.0, 300.0→301.0, 60→61), flipped to None, **or the default arg dropped entirely → `None` on missing key** | 18 | TEST-GAP | `…from_dict__mutmut_97`, `__mutmut_99`, `__mutmut_137` | T1 |
| 4 | `from_dict`: **`last_failure_at`/`last_restart_at` parsing never asserted** — guard-key mangled (`if data.get(None)` / `"XXlast_restart_atXX"` / `"LAST_RESTART_AT"`), parse replaced by `None`, `last_restart_at=` kwarg nulled/dropped, `last_failure_at = None` init→`""` | 7 | TEST-GAP | `…from_dict__mutmut_1`, `__mutmut_10`, `__mutmut_41` | T1 |
| 5 | `from_config`: config-field propagation **not asserted** — `health_cmd`, `restart_backoff_base`, `restart_backoff_max` nulled or kwarg dropped (test never deviates them from class defaults) | 6 | TEST-GAP | `…from_config__mutmut_7`, `__mutmut_11`, `__mutmut_24` | T6 |
| 6 | `from_config`: `status=ContainerServiceStatus.NOT_FOUND` kwarg dropped → **identical** dataclass default | 1 | EQUIVALENT | `…from_config__mutmut_22` | — (true equivalent) |
| 7 | Datetime truthiness guard poisoned: `if x else None` → `if (x) or True else None` → **`None.isoformat()` AttributeError / `fromisoformat(None)` TypeError when timestamps are None** (persist_state's crash is inside `try:` → silent log-and-continue zombie) | 6 | TEST-GAP | `…to_dict__mutmut_26`, `…persist_state__mutmut_14`, `…_apply_state_to_service__mutmut_31` | T2 (apply half) + T3 (to_dict/persist half) |
| 8 | `_apply_state_to_service`: **`state.get` defaults broken or assignment dropped** (`enabled`→None/False, `failure_count`/`restart_count`→None/1/default removed) | 9 | TEST-GAP | `…_apply_state_to_service__mutmut_3`, `__mutmut_8`, `__mutmut_24` | T2 |
| 9 | `increment_failure`/`record_restart`: `x += 1` → **`x = 1`** (counter resets instead of accumulating past 1) | 2 | TEST-GAP | `…increment_failure__mutmut_3`, `…record_restart__mutmut_3` | T5 |
| 10 | `increment_failure`/`record_restart`: `datetime.now(UTC)` → `datetime.now(None)` (**naive local timestamps** feed backoff math and Redis ISO strings) | 2 | TEST-GAP | `…increment_failure__mutmut_7`, `…record_restart__mutmut_7` | T5 |
| 11 | `persist_state`: **Redis TTL never asserted** — `expire=86400` → None / dropped / 86401 (existing test checks only positional key+state) | 3 | TEST-GAP | `…persist_state__mutmut_26`, `__mutmut_29`, `__mutmut_30` | T4 |
| 12 | `load_state`: **Redis key construction never asserted** (`key = None`, then `redis.get(None)`) — mock returns state regardless of key | 2 | TEST-GAP | `…load_state__mutmut_6`, `__mutmut_8` | T2 |
| 13 | `get_service_registry`: **singleton Redis wiring not asserted** — `init_redis()` result or the whole `redis_client=` arg replaced by None (registry silently loses persistence) | 2 | TEST-GAP | `x_get_service_registry__mutmut_2`, `__mutmut_4` | one-line note below |
| 14 | `load_state`: `name` arg to `_apply_state_to_service` → None (feeds only the warning-log `extra` on invalid status) | 1 | LOW-VALUE | `…load_state__mutmut_24` | — |

Key subtlety behind cluster 3: `data.get(k, )` (default arg removed) is **not** equivalent to
`data.get(k, 0)` — it returns `None`, which is passed explicitly into the constructor and
overrides the dataclass default. These 18 mutants are exactly the "defaults silently vanish"
class and none of them was caught because `test_from_dict_minimal` asserts none of these
fields. Likewise the three `from_config` default-removals (cluster 5) fall back to class
defaults that the existing test never varies — that's why they survived.

---

## Drafted tests (6) — kill 55 of the 57 TEST-GAP survivors (+2 via one-line patch = full TEST-GAP sweep)

All target `backend/tests/unit/services/test_managed_service.py`. Style follows the existing
classes; imports already present in that file (`UTC`, `datetime`, `timedelta`, `AsyncMock`,
`pytest`, enums, `REDIS_KEY_PREFIX`). **Every test below is UNVERIFIED — not yet run red/green.**
TDD procedure (applies to each): run the test against the mutant variant → assertion must FAIL;
run against `backend/services/managed_service.py` → must PASS.

### T1 — `test_from_dict_defaults_and_datetime_parsing` (class `TestManagedService`)
Kills clusters 3 (18) + 4 (7). Missed today: `test_from_dict_minimal`:212 asserts only
name/port/category/status/enabled; `test_from_dict`:177 sets `last_restart_at=None` so parsing
is never exercised; `test_roundtrip_serialization`:290 never feeds dicts with missing keys.

```python
    def test_from_dict_defaults_and_datetime_parsing(self) -> None:
        """Missing keys fall back to canonical defaults; timestamps are parsed, not dropped."""
        minimal = ManagedService.from_dict(
            {"name": "svc", "port": 8080, "category": "ai"}
        )
        assert minimal.last_failure_at is None
        assert minimal.last_restart_at is None
        assert minimal.enabled is True
        assert minimal.status == ContainerServiceStatus.NOT_FOUND
        assert minimal.failure_count == 0
        assert minimal.restart_count == 0
        assert minimal.max_failures == 5
        assert minimal.restart_backoff_base == 5.0
        assert minimal.restart_backoff_max == 300.0
        assert minimal.startup_grace_period == 60

        ts = "2026-09-17T12:00:00+00:00"
        parsed = ManagedService.from_dict(
            {
                "name": "svc",
                "port": 8080,
                "category": "ai",
                "last_failure_at": ts,
                "last_restart_at": ts,
            }
        )
        assert parsed.last_failure_at == datetime.fromisoformat(ts)
        assert parsed.last_restart_at == datetime.fromisoformat(ts)  # guards mangled/dropped parsing
```
UNVERIFIED - not yet run red/green.

### T2 — `test_load_state_applies_defaults_and_missing_timestamps` (class `TestServiceRegistryPersistence`)
Kills cluster 8 (9) + `_apply_state_to_service` half of cluster 7 (2) + cluster 12 (2).
Missed today: `test_load_state`:766 passes a *complete* state (defaults never used) and never
checks the Redis key; `test_load_all_state`:851 hides exceptions behind `load_state`'s broad
`except Exception`.

```python
    @pytest.mark.asyncio
    async def test_load_state_applies_defaults_and_missing_timestamps(self) -> None:
        """State missing optional fields resets tracking to defaults; Redis key is canonical."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = {"note": "no tracking fields present"}

        registry = ServiceRegistry(redis_client=mock_redis)
        registry.register(
            ManagedService(
                name="load-defaults",
                display_name="Load Defaults",
                container_id="ld",
                image="test:latest",
                port=8080,
                category=ServiceCategory.AI,
                enabled=False,          # non-default runtime values so defaults/omissions must overwrite
                failure_count=9,
                restart_count=4,
                last_failure_at=datetime.now(UTC),
                last_restart_at=datetime.now(UTC),
            )
        )

        await registry.load_state("load-defaults")

        mock_redis.get.assert_awaited_once_with(f"{REDIS_KEY_PREFIX}:load-defaults:state")
        service = registry.get("load-defaults")
        assert service is not None
        assert service.enabled is True
        assert service.failure_count == 0
        assert service.restart_count == 0
        # fromisoformat(None) must not sneak through: guard says "absent -> None", not crash
        assert service.last_failure_at is None
        assert service.last_restart_at is None
```
UNVERIFIED - not yet run red/green.

### T3 — `test_none_timestamps_serialize_and_persist_as_none` (class `TestServiceRegistryPersistence`)
Kills the `to_dict` + `persist_state` half of cluster 7 (4). Missed today: every serialization
test (`test_to_dict`:143, `test_persist_state`:700) populates both timestamps, so the
`or True`-poisoned guards (which call `None.isoformat()` → AttributeError) never execute.

```python
    @pytest.mark.asyncio
    async def test_none_timestamps_serialize_and_persist_as_none(self) -> None:
        """Services that never failed serialize None timestamps without crashing."""
        mock_redis = AsyncMock()
        registry = ServiceRegistry(redis_client=mock_redis)
        service = ManagedService(
            name="ts-none",
            display_name="Ts None",
            container_id="tn",
            image="test:latest",
            port=8080,
            category=ServiceCategory.AI,
        )
        registry.register(service)

        data = service.to_dict()
        assert data["last_failure_at"] is None
        assert data["last_restart_at"] is None
        restored = ManagedService.from_dict(data)
        assert restored.last_failure_at is None
        assert restored.last_restart_at is None

        await registry.persist_state("ts-none")
        state = mock_redis.set.call_args[0][1]
        assert state["last_failure_at"] is None
        assert state["last_restart_at"] is None
```
UNVERIFIED - not yet run red/green.

### T4 — `test_persist_state_sets_24h_ttl` (class `TestServiceRegistryPersistence`)
Kills cluster 11 (3). Missed today: `test_persist_state`:725-728 asserts only positional
`call_args[0][0]` / `[0][1]`; the `expire` kwarg is unasserted.

```python
    @pytest.mark.asyncio
    async def test_persist_state_sets_24h_ttl(self) -> None:
        """Persisted state carries the 24h TTL so removed services don't leak keys."""
        mock_redis = AsyncMock()
        registry = ServiceRegistry(redis_client=mock_redis)
        registry.register(
            ManagedService(
                name="ttl-test",
                display_name="TTL Test",
                container_id="tt",
                image="test:latest",
                port=8080,
                category=ServiceCategory.AI,
            )
        )

        await registry.persist_state("ttl-test")

        mock_redis.set.assert_awaited_once()
        assert mock_redis.set.call_args.kwargs["expire"] == 86400
```
UNVERIFIED - not yet run red/green.

### T5 — `test_counter_updates_accumulate_and_are_timezone_aware` (class `TestServiceRegistry`)
Kills clusters 9 + 10 (4). Missed today: `test_increment_failure`:547 increments once from 0
(`= 1` is indistinguishable); `test_record_restart`:619 likewise; neither checks tzinfo —
`datetime.now(None)` produces naive local stamps that poison backoff math downstream.

```python
    def test_counter_updates_accumulate_and_are_timezone_aware(self) -> None:
        """Counters add to existing totals; failure/restart stamps are timezone-aware UTC."""
        registry = ServiceRegistry()
        registry.register(
            ManagedService(
                name="count-test",
                display_name="Count Test",
                container_id="ct",
                image="test:latest",
                port=8080,
                category=ServiceCategory.AI,
                failure_count=2,
                restart_count=3,
            )
        )

        assert registry.increment_failure("count-test") == 3
        assert registry.increment_failure("count-test") == 4
        registry.record_restart("count-test")
        registry.record_restart("count-test")

        service = registry.get("count-test")
        assert service is not None
        assert service.failure_count == 4
        assert service.restart_count == 5
        # naive datetime.now(None).utcoffset() is None, not timedelta(0)
        assert service.last_failure_at.utcoffset() == timedelta(0)
        assert service.last_restart_at.utcoffset() == timedelta(0)
```
UNVERIFIED - not yet run red/green.

### T6 — `test_from_config_propagates_all_config_fields` (class `TestManagedService`)
Kills cluster 5 (6). Missed today: `test_from_config`:233-240 leaves `health_cmd` at its None
default and both backoffs at class defaults (5.0/300.0), so null/drop mutants are invisible.

```python
    def test_from_config_propagates_all_config_fields(self) -> None:
        """from_config copies every ServiceConfig field, not just the ones the old test varied."""
        config = ServiceConfig(
            display_name="Florence",
            category=ServiceCategory.AI,
            port=8092,
            health_endpoint="/health",
            health_cmd="python check_florence.py",
            startup_grace_period=90,
            max_failures=8,
            restart_backoff_base=7.0,   # differs from dataclass default 5.0
            restart_backoff_max=45.0,   # differs from dataclass default 300.0
        )

        service = ManagedService.from_config(
            config_key="ai-florence",
            config=config,
            container_id="cid-1",
            image="florence:latest",
        )

        assert service.health_endpoint == "/health"
        assert service.health_cmd == "python check_florence.py"
        assert service.startup_grace_period == 90
        assert service.max_failures == 8
        assert service.restart_backoff_base == 7.0
        assert service.restart_backoff_max == 45.0
```
UNVERIFIED - not yet run red/green.

### Not drafted (cluster 13, 2 mutants) — one-line kill
`test_get_service_registry_creates_singleton`:908 should add
`assert registry._redis is mock_redis` (kills `x_get_service_registry__mutmut_2/__mutmut_4`,
which replace the `init_redis()` result / the `redis_client=` kwarg with `None`).

---

## Notes for the mutation-score ledger

- Clusters 1+2 (120/179, 67% of survivors) are log-only. If the team wants these off the
  backlog rather than asserted, a mutmut skip/exclusion on `logger.*` argument mutations is
  the cheaper lever than 120 tests.
- Cluster 7 is the sharpest real finding: `if x else None` guards are load-bearing (None
  timestamps must serialize as null, and persist_state must not silently swallow the crash).
  T2/T3 make that invariant explicit.
- Cluster 6 (1 mutant) is the only true equivalent outside the log cluster (dropped kwarg =
  identical dataclass default). Do not chase it.
- 16 mutants remain `null` (not yet checked) in the meta at harvest time (meta mtime
  2026-09-17 10:03 while the run was live); re-count before finalizing the module score.
