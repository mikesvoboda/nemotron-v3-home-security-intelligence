# WP4.4 Triage Dossier — backend/services/orchestrator/registry.py

Source: `mutants/backend/services/orchestrator/registry.py.meta` (exit_code 0 = survived).
**Survivors: 125** of 221 checked (96 killed, 114 not-yet-checked). Diffs generated offline from
`registry.py.spans` (0-based line ranges into the mutant copy) + unified diff vs `__mutmut_orig`;
spot-verified against `uv run mutmut show`.

## Covering tests (from mutmut-stats.json tests_by_mangled_function_name)

Two files are the real covering surface; everything else (test_container_orchestrator,
test_lifecycle_manager, test_model_warmup, test_health_monitor_orchestrator) exercises the
registry only incidentally.

| File                                                        | Role                                                                                                                         | Key anchors                                                                                                                                                          |
| ----------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/tests/unit/services/orchestrator/test_registry.py` | canonical direct-import tests                                                                                                | fixtures :22/:31/:35 · `test_persist_state` :241 · `test_load_state` :260 · `test_clear_state` :325                                                                  |
| `backend/tests/unit/services/test_service_registry.py`      | rich persistence/error tests via shim `backend/services/service_registry.py:56` (pure re-export — mutations DO execute here) | `TestServiceRegistryPersistence` :583 (`test_persist_state` :587, `test_load_state` :623) · `TestServiceRegistryRedisErrorHandling` :725 · `TestGlobalRegistry` :868 |

No test anywhere uses `caplog` against this module — no log record or `extra` payload is asserted,
which is why the ~95 logging mutants all swim.

## Cluster table (counts sum to 125)

| #   | Cluster                                                                                                                                                                                                                                                         | N   | Class        | Example keys (of `backend.services.orchestrator.registry.` prefix)                                                                    | Evidence / verdict                                                                                                                                                                                                                                                                                |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| C1  | `_apply_loaded_state`: `state.get(key, DEFAULT)` default dropped or wrong on restore (enabled→None/False, failure_count→None/1, restart_count→None/1; ", )" variants drop the default → None)                                                                   | 9   | **TEST-GAP** | `xǁServiceRegistryǁ_apply_loaded_state__mutmut_6` / `_8` / `_11`                                                                      | Both load tests (`orchestrator/test_registry.py:260`, `test_service_registry.py:623`) feed Redis payloads containing ALL six keys — the `default` branch never runs. Missing-key restore (pre-schema payloads after a deploy) silently sets `enabled=None`/`failure_count=None`. Drafted test #1. |
| C2  | `persist_state`: timestamp ternary guard `if service.last_failure_at` → `if (…) and False` ⇒ `last_failure_at`/`last_restart_at` always persisted as `None`                                                                                                     | 2   | **TEST-GAP** | `xǁServiceRegistryǁpersist_state__mutmut_21` / `_25`                                                                                  | Best persist test (`test_service_registry.py:587`) only asserts `"last_failure_at" in data` — presence, not value. Round-trip loses failure/restart recency silently. Drafted test #2.                                                                                                            |
| C3  | `get_service_registry` singleton discards the `init_redis()` client (`redis_client = None` / `ServiceRegistry(redis_client=None)`) — global registry persists nothing, no error                                                                                 | 2   | **TEST-GAP** | `x_get_service_registry__mutmut_2` / `_4`                                                                                             | `TestGlobalRegistry` (`test_service_registry.py:872`) asserts only `registry1 is registry2` identity. Drafted test #3.                                                                                                                                                                            |
| E1  | log message literal changed (`"msg"` → `None` / `"XXmsgXX"` / `"msg"`-case flips) in `logger.debug`/`logger.warning` calls across unregister, reset_failures, record_restart, set_enabled, update_container_id, update_warmth_state, persist_state, clear_state | 54  | EQUIVALENT   | `xǁServiceRegistryǁunregister__mutmut_6`, `xǁServiceRegistryǁclear_state__mutmut_8`, `xǁServiceRegistryǁpersist_state__mutmut_41`     | Pure message text; nothing consumes it. Not worth killing.                                                                                                                                                                                                                                        |
| E2  | singleton log message literal changed in `get_service_registry`/`reset_service_registry`                                                                                                                                                                        | 8   | EQUIVALENT   | `x_get_service_registry__mutmut_5` / `_6` / `_7`                                                                                      | Same.                                                                                                                                                                                                                                                                                             |
| C7c | log `extra` payload KEY renamed (`"service_name"`→`"XXservice_nameXX"`/`"SERVICE_NAME"`, likewise `error`, `restart_count`, `enabled`, `container_id`, `warmth_state`)                                                                                          | 24  | LOW-VALUE    | `xǁServiceRegistryǁclear_state__mutmut_20`, `xǁServiceRegistryǁrecord_restart__mutmut_12`, `xǁServiceRegistryǁset_enabled__mutmut_13` | Real change to structured-log contract (breaks log-agg queries), but no test asserts record `extra`. Only worth killing if the project ever adopts a caplog contract test.                                                                                                                        |
| C7a | log `extra=None` (drops whole structured payload)                                                                                                                                                                                                               | 11  | LOW-VALUE    | `xǁServiceRegistryǁclear_state__mutmut_5`, `xǁServiceRegistryǁpersist_state__mutmut_3`                                                | As C7c.                                                                                                                                                                                                                                                                                           |
| C7b | log `extra=` kwarg removed entirely                                                                                                                                                                                                                             | 11  | LOW-VALUE    | `xǁServiceRegistryǁclear_state__mutmut_7`, `xǁServiceRegistryǁpersist_state__mutmut_39`                                               | As C7c.                                                                                                                                                                                                                                                                                           |
| C8  | log `extra["error"]` value `str(e)` → `str(None)` (exception context lost in warning)                                                                                                                                                                           | 2   | LOW-VALUE    | `xǁServiceRegistryǁclear_state__mutmut_24`, `xǁServiceRegistryǁpersist_state__mutmut_56`                                              | Error tests (`test_service_registry.py:729/:755`) run the warning path but assert nothing about the record.                                                                                                                                                                                       |
| C6  | `logger.debug(extra={...})` — msg positional arg removed ⇒ `TypeError: missing 1 required positional argument: 'msg'` at runtime                                                                                                                                | 2   | LOW-VALUE    | `xǁServiceRegistryǁclear_state__mutmut_6`, `xǁServiceRegistryǁpersist_state__mutmut_38`                                               | The TypeError is raised _inside the surrounding `try`_ and swallowed by `except Exception` (degrades to a warning). Confirmed: stdlib Logger requires `msg`. Nobody should assert debug-log signature validity; a caplog "no WARNING on success" test would kill these incidentally.              |

TEST-GAP total: 13 · LOW-VALUE: 50 · EQUIVALENT: 62 · **Sum: 125**

## Drafted tests — UNVERIFIED - not yet run red/green

TDD procedure (all three): run against the mutant copy → assertion FAILS (red); run against
`backend/services/orchestrator/registry.py` → PASSES (green).

### Test 1 — kills C1 (9 mutants) → add to `backend/tests/unit/services/orchestrator/test_registry.py` (class `TestServiceRegistry`, after `test_load_state` :293)

```python
    @pytest.mark.asyncio
    async def test_load_state_partial_payload_uses_documented_defaults(
        self,
        registry: ServiceRegistry,
        sample_service: ManagedService,
        mock_redis: MagicMock,
    ) -> None:
        """Missing keys in Redis state restore defaults (True/0/0), not None/False/1."""
        registry.register(sample_service)
        registry.increment_failure(sample_service.name)
        registry.record_restart(sample_service.name)

        # Legacy payload: intentionally omits enabled, failure_count and restart_count.
        mock_redis.get.return_value = {"status": "running"}

        await registry.load_state(sample_service.name)

        service = registry.get(sample_service.name)
        assert service.enabled is True          # kills _6/_8 (None) and _11 (False)
        assert service.failure_count == 0       # kills _14/_16 (None) and _19 (1)
        assert service.restart_count == 0       # kills _22/_24 (None) and _27 (1)
```

Green on original: `state.get("enabled", True)`/`(..., 0)` fire the default branch. Red on every
C1 mutant (None/False/1 ≠ expected). Existing tests can't kill it because they always send complete payloads.

### Test 2 — kills C2 (2 mutants) → same file, after `test_persist_state` :251

```python
    @pytest.mark.asyncio
    async def test_persist_state_serializes_timestamp_values(
        self,
        registry: ServiceRegistry,
        sample_service: ManagedService,
        mock_redis: MagicMock,
    ) -> None:
        """persist_state must serialize last_failure_at/last_restart_at, not null them."""
        registry.register(sample_service)
        registry.increment_failure(sample_service.name)
        registry.record_restart(sample_service.name)

        await registry.persist_state(sample_service.name)

        data = mock_redis.set.call_args[0][1]
        assert data["last_failure_at"] == sample_service.last_failure_at.isoformat()
        assert data["last_restart_at"] == sample_service.last_restart_at.isoformat()
```

Red on `persist_state#21/#25` (ternary guarded `and False` ⇒ `None.isoformat()` side never taken;
`None != isoformat string`). Green on original. Existing `test_persist_state`
(`test_service_registry.py:611-612`) checks key presence only.

### Test 3 — kills C3 (2 mutants) → add to `backend/tests/unit/services/test_service_registry.py` (class `TestGlobalRegistry` :868; file already imports `get_service_registry`, `patch`, has autouse `reset_global_registry` :40)

```python
    @pytest.mark.asyncio
    async def test_get_service_registry_wires_redis_into_persistence(
        self, mock_redis: AsyncMock, sample_service: ManagedService
    ) -> None:
        """The singleton must be built with the client returned by init_redis()."""

        async def mock_init_redis():
            return mock_redis

        with patch(
            "backend.core.redis.init_redis",
            side_effect=mock_init_redis,
            autospec=True,
        ):
            registry = await get_service_registry()
            registry.register(sample_service)

            await registry.persist_state(sample_service.name)

            mock_redis.set.assert_called_once()
```

Red on `x_get_service_registry#2/#4` (registry built with `redis_client=None` ⇒ persist is a
no-op ⇒ `set` never called). Green on original. Existing test only proves singleton identity.

## Notes for WP4.4

- 88 of 125 survivors (E1+E2+C7\*+C8+C6) are a single systemic cause: zero log-contract coverage.
  If the team wants the score up cheaply, one shared `caplog` fixture asserting
  `record.extra["service_name"]` on one happy-path call per method would sweep C7a/b/c and C8 —
  but that codifies log strings; recommend leaving E1/E2 as EQUIVALENT-noise and skipping the rest.
- `_apply_loaded_state` C1 is the highest-severity live gap: a Redis payload written by an older
  build (or a partially-written hash) currently corrupts `failure_count=None`, which then breaks
  any `>= max_failures` comparison downstream at health-monitor time.
- Do not target the 114 `null` (untested) keys from this dossier — that set is still being
  filled by the in-flight run; re-triage after it completes.
