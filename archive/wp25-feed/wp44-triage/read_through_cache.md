# WP4.4 Triage Dossier — `backend/services/read_through_cache.py`

**Surviving mutants:** 122 of 278 checked (107 killed, 49 not-yet-checked/null). Source of truth: `mutants/backend/services/read_through_cache.py.meta` (`exit_code == 0`).

**Covering test file (all coverage):** `backend/tests/unit/services/test_read_through_cache.py` — the sole test file, exercised via `tests_by_mangled_function_name` in `mutants/mutmut-stats.json`.

**Method:** `uv run mutmut show <key>` (read-only) for all 122 survivors; diffs parsed to `minus`/`plus` line pairs and clustered by (function, mutated concern).

## Root causes of the survivors (why tests are blind)

1. **Mocked-Redis key blindness.** Every test uses `mock_redis` and asserts only `call_count` / `assert_called_once()` — never `call_args`. So `redis.get(cache_key)` → `redis.get(None)` and `redis.set(cache_key,…)` → `redis.set(None,…)` are invisible.
2. **`result.cache_key` never asserted.** No test reads `.cache_key` off a `ReadThroughResult`, so `cache_key=cache_key` → `cache_key=None` on every return path survives.
3. **`record_cache_hit/miss` never asserted.** No test imports or patches the metrics; `self._cache_type` → `None` survives.
4. **DB loaders mock `session.execute` to ignore its argument and set only 2 of the returned dict's fields.** So the entire `select(...).where(Model.id == …)` clause can be deleted and unasserted keys ("id"/"status"/"severity"/…) renamed.
5. **Singleton builders checked for identity/prefix only.** `_loader`, `_cache_type`, `_ttl` (camera/alert) are never inspected, so the whole construction argument list is unasserted.

## Per-cluster table

Counts sum to 122. `example_keys` are the mutmut suffix after the function token.

| # | Function / concern | Mutation pattern | n | Class | example_keys | Test-file gap |
|---|---|---|---|---|---|---|
| C1 | `get` result metadata | `cache_key=cache_key` → `None` on both returns | 2 | **TEST-GAP** | get_14, get_50 | no test reads `result.cache_key` |
| C2 | `get` redis-lookup / cache-path wiring | `redis.get(cache_key)`→`get(None)`/`None`; `_make_cache_key(key)`→`None`/`_make_cache_key(None)`; `_load_with_lock/_load_without_lock(…,None,…)` | 6 | **TEST-GAP** | get_4, get_7, get_8, get_22, get_30 | `test_get_cache_hit` asserts `get.assert_called_once()`, not `call_args[0][0]` |
| C3 | `get` ttl passthrough to lock path | `ttl`→`None` into `_load_with_lock` | 1 | **TEST-GAP** | get_23 | ttl tests use `stampede_protection=False`, bypass this arg |
| C4 | `get` metrics | `record_cache_hit/miss(self._cache_type)`→`None` | 2 | **TEST-GAP** | get_10, get_19 | metrics never patched/asserted |
| C5 | `get` debug log text | `logger.debug(f"…hit/miss…")`→`None` | 2 | EQUIVALENT | get_11, get_20 | log-message text only |
| C6 | `get` redis-error warning | warning message `None`; `extra=` dict removed/`None`/key-cased/`str(None)`/arg-drop | 8 | EQUIVALENT | get_37, get_41, get_44 | pure log payload text |
| C7 | `_load_with_lock` no-op | drop trailing comma (no kwarg actually removed) | 1 | EQUIVALENT | lwl_11 | syntactic no-op |
| C8 | `_load_with_lock` lock value | `"1"`→`None`/`"XX1XX"` (lock value never inspected) | 2 | EQUIVALENT | lwl_5, lwl_12 | lock value is a placeholder |
| C9 | `_load_with_lock` lock-key derivation | `_make_lock_key(key)`→`None`/`(None)`; `set(None,…)` | 3 | **TEST-GAP** | lwl_1, lwl_4 | `set.assert_called()` never checks lock key |
| C10 | `_load_with_lock` lock TTL / `expire` | `expire=`→`None`; `expire=` kwarg dropped | 2 | **TEST-GAP** | lwl_6, lwl_10 | no test asserts lock `expire` |
| C11 | `_load_with_lock` NX semantics | `nx=True`→`None`/`False`; `nx=` kwarg dropped | 2 | **TEST-GAP** | lwl_7, lwl_13 | `nx` never asserted |
| C12 | `_load_with_lock` double-check | `redis.get(cache_key)`→`None`/`get(None)` | 2 | **TEST-GAP** | lwl_24, lwl_25 | double-check lookup key/arg unchecked |
| C13 | `_load_with_lock` value-cache write | `redis.set(cache_key,value,expire=ttl)` key/value/TTL clobbered or dropped | 6 | **TEST-GAP** | lwl_30, lwl_31, lwl_34, lwl_35 | only `call_count==2`, not `call_args` |
| C14 | `_load_with_lock` wait-branch | `_wait_for_cache(...)` arg clobbers: lwl_15 debug `None`, lwl_16/17/19 real key/redis drops, lwl_18 `ttl`→`None` | 5 | EQUIVALENT | lwl_15, lwl_16, lwl_17, lwl_19 | `test_…waits…` patches `_wait_for_cache`; the dropped args are `_`-private names, unobservable — 4 EQUIVALENT, lwl_18 (`ttl`, dead in `_wait_for_cache`) LOW-VALUE |
| C15 | `_load_with_lock` result metadata | `cache_key=cache_key`→`None` | 1 | **TEST-GAP** | lwl_39 | same as C1 |
| C16 | `_load_with_lock` debug text | `logger.debug(…)`→`None` | 1 | EQUIVALENT | lwl_36 | log text only |
| C17 | `_load_with_lock` lock release | `redis.delete(lock_key)`→`delete(None)` | 1 | **TEST-GAP** | lwl_44 | `delete.assert_called()` never checks key |
| C18 | `invalidate` cache-key derivation | `_make_cache_key(key)`→`None`/`(None)`; `delete(None)` | 3 | **TEST-GAP** | inv_2, inv_5 | `delete.assert_called_once()` arg-unchecked |
| C19 | `invalidate` debug-log guard | `if deleted > 0`→`>= 0`/`> 1` (log guard only; `return` expr is a separate occurrence) | 2 | EQUIVALENT | inv_6, inv_7 | return value unchanged — verified source |
| C20 | `invalidate` log text | debug/warning message →`None` | 2 | EQUIVALENT | inv_8, inv_11 | log text only |
| C21 | `refresh` arg forwarding | `invalidate(None)` / `self.get(None)` | 2 | **TEST-GAP** | ref_1, ref_2 | `test_refresh` checks delete count, not key |
| C22 | `_load_camera` WHERE clause | `execute(select(Camera).where(Camera.id==camera_id))`→`execute(None)`/`where(None)`/`select(None)`/`!=` | 4 | **TEST-GAP** | cam_2, cam_5 | `session.execute` mocked to ignore its argument |
| C23 | `_load_camera` result dict keys | `"folder_path"`/`"status"` → `XX…XX`/`UPPER` (unasserted keys) | 4 | **TEST-GAP** | cam_11, cam_14 | test asserts only `id`,`name` |
| C24 | `_load_camera` `created_at` ternary | `if camera.created_at`→`and False` (real value forced to `None`) | 1 | **TEST-GAP** | cam_17 | has-value branch asserts `== isoformat()`? test only covers `None` case |
| C25 | `_load_event` WHERE clause | same as C22 for `Event.id==event_uuid` | 4 | **TEST-GAP** | evt_4, evt_7 | argument ignored by mock |
| C26 | `_load_event` result dict keys | `"id"`→`XXidXX`/`ID`/`str(None)`; `risk_level`/`summary`/`reviewed` case/XX | 9 | **TEST-GAP** | evt_9, evt_11, evt_21 | test asserts only `camera_id`,`risk_score` |
| C27 | `_load_event` `started_at` ternary | `if event.started_at`→`and False` | 1 | **TEST-GAP** | evt_24 | has-value branch never asserted |
| C28 | `_load_alert_rule` WHERE clause | same as C22 for `AlertRule.id==alert_uuid` | 4 | **TEST-GAP** | ar_4, ar_7 | argument ignored by mock |
| C29 | `_load_alert_rule` result dict keys | `"id"`→`XXidXX`/`ID`/`str(None)`; `enabled`/`created_at` case/XX | 7 | **TEST-GAP** | ar_11, ar_19, ar_20 | test asserts only `name`,`severity` |
| C30 | `_load_alert_rule` `created_at` ternary | `and False` / `or True` | 2 | **TEST-GAP** | ar_22, ar_23 | has-value branch never asserted |
| C31 | `get_camera_read_through_cache` construction | `loader`→`None`; `cache_type`→`None`/dropped/`XXcamerasXX`/`CAMERAS`; `ttl=` dropped/`None` | 7 | **TEST-GAP** | camrt_5, camrt_7, camrt_14 | only `_prefix` asserted |
| C32 | `get_event_read_through_cache` construction | `cache_prefix`/`loader`/`cache_type` dropped/cased | 8 | **TEST-GAP** | evrt_4, evrt_12, evrt_14 | only `is` singleton + `_ttl` asserted |
| C33 | `get_alert_read_through_cache` construction | `cache_prefix`/`loader`/`cache_type` dropped/cased; whole `ReadThroughCache(...)`→`_alert_cache=None` | 11 | **TEST-GAP** | alt_3, alt_4, alt_12 | only `is` singleton asserted |
| C34 | `get_alert_read_through_cache` re-init guard | `if _alert_cache is None`→`is not None` (singleton re-created every call) | 1 | LOW-VALUE | alt_1 | real behavior change; nobody should assert the guard itself |
| C35 | `reset_read_through_caches` sentinel | `_alert_cache = None`→`""` (falsy; next getter re-creates) | 1 | LOW-VALUE | rst_3 | cosmetic; reset still functionally works |

**Class totals:** TEST-GAP 97 (C1-4,C9-13,C15,C17,C18,C21-C33), EQUIVALENT 22 (C5,C6,C7,C8,C14 minus lwl_18,C16,C19,C20), LOW-VALUE 3 (lwl_18,C34,C35). Sum = 122.

## Drafted tests

Target file for all: `backend/tests/unit/services/test_read_through_cache.py`. Style mirrors existing fixtures (`mock_settings`, `mock_redis`, `patch(...get_settings…)`, direct private-method calls).

**// UNVERIFIED - not yet run red/green**

### T1 — `get` passes the real cache key to redis (kills C2)
```python
    @pytest.mark.asyncio
    async def test_get_cache_hit_uses_fully_prefixed_cache_key(
        self, mock_settings, mock_redis
    ):
        """The redis lookup must use the fully-prefixed cache key, not None.

        Kills C2: redis.get(cache_key)->get(None)/None and the cache-path
        arg clobbers are invisible to call_count-only assertions.
        // UNVERIFIED - not yet run red/green
        """
        async def loader(key: str) -> dict:
            return {"id": key}

        mock_redis.get.return_value = {"id": "key1"}

        with patch(
            "backend.services.read_through_cache.get_settings",
            return_value=mock_settings,
            autospec=True,
        ):
            cache = ReadThroughCache(
                cache_prefix="test", loader=loader, ttl=300,
            )
            cache._redis = mock_redis

            await cache.get("key1")

        mock_redis.get.assert_called_once_with("hsi:cache:test:key1")
```

### T2 — result `cache_key` is the fully-prefixed key on hit, miss, and fallback (kills C1, C15)
```python
    @pytest.mark.asyncio
    async def test_result_cache_key_is_fully_prefixed(self, read_through_cache, mock_redis):
        """ReadThroughResult.cache_key must carry the real prefixed key.

        Kills C1/C15: cache_key=cache_key -> cache_key=None on every return.
        // UNVERIFIED - not yet run red/green
        """
        mock_redis.get.return_value = {"id": "1"}
        hit = await read_through_cache.get("1")
        assert hit.cache_key == "hsi:cache:test:1"

        mock_redis.get.return_value = None
        mock_redis.set.return_value = True
        miss = await read_through_cache.get("existing")
        assert miss.cache_key == "hsi:cache:test:existing"
```

### T3 — stampede lock is SET NX with the right key and expiry (kills C9, C10, C11)
```python
    @pytest.mark.asyncio
    async def test_load_with_lock_sets_nx_lock_with_key_and_expiry(
        self, mock_settings, mock_redis
    ):
        """The lock must be SET NX with the derived lock key + configured timeout.

        Kills C9/C10/C11: lock_key->None, expire->None/omitted, nx->None/False/omitted.
        // UNVERIFIED - not yet run red/green
        """
        async def loader(key: str) -> dict:
            return {"id": key}

        mock_redis.set.return_value = True   # lock acquired
        mock_redis.get.return_value = None
        mock_redis.delete.return_value = 1

        with patch(
            "backend.services.read_through_cache.get_settings",
            return_value=mock_settings,
            autospec=True,
        ):
            cache = ReadThroughCache(
                cache_prefix="test", loader=loader, ttl=300,
                stampede_protection=True, lock_timeout=30,
            )
            cache._redis = mock_redis

            await cache._load_with_lock(
                "key1", "hsi:cache:test:key1", 300, mock_redis,
            )

        call = mock_redis.set.call_args_list[0]
        assert call[0][0] == "hsi:cache:test:key1:loading"
        assert call[1]["expire"] == 30
        assert call[1]["nx"] is True
```

### T4 — loaded value is cached under the right key/value/TTL (kills C13)
```python
    @pytest.mark.asyncio
    async def test_load_with_lock_caches_value_under_correct_key_and_ttl(
        self, mock_settings, mock_redis
    ):
        """After loading, the value must be written to the cache key with the TTL.

        Kills C13: redis.set key/value/expire clobbers on the value-cache write.
        // UNVERIFIED - not yet run red/green
        """
        async def loader(key: str) -> dict:
            return {"id": key, "v": 1}

        mock_redis.set.return_value = True
        mock_redis.get.return_value = None
        mock_redis.delete.return_value = 1

        with patch(
            "backend.services.read_through_cache.get_settings",
            return_value=mock_settings,
            autospec=True,
        ):
            cache = ReadThroughCache(
                cache_prefix="test", loader=loader, ttl=300,
                stampede_protection=True,
            )
            cache._redis = mock_redis

            await cache._load_with_lock(
                "key1", "hsi:cache:test:key1", 300, mock_redis,
            )

        assert ("hsi:cache:test:key1", {"id": "key1", "v": 1}) in [
            (c[0][0], c[0][1]) for c in mock_redis.set.call_args_list
        ]
        value_call = next(
            c for c in mock_redis.set.call_args_list
            if c[0][0] == "hsi:cache:test:key1"
        )
        assert value_call[1]["expire"] == 300
        assert "nx" not in value_call[1]
```

### T5 — loaders build a complete result dict from the right query (kills C22, C23, C24, C25, C26, C27, C28, C29, C30)
```python
    @pytest.mark.asyncio
    async def test_event_loader_returns_complete_dict_from_id_query(self, mock_settings):
        """_load_event must filter on Event.id and project every documented key.

        Kills C25/C26/C27: WHERE-clause drop and unasserted dict keys.
        // UNVERIFIED - not yet run red/green
        """
        from datetime import datetime
        from uuid import UUID, uuid4

        from backend.services.read_through_cache import _load_event

        event_id = str(uuid4())
        with patch(
            "backend.core.database.get_session", autospec=True
        ) as mock_get_session:
            mock_event = MagicMock()
            mock_event.id = UUID(event_id)
            mock_event.camera_id = "cam1"
            mock_event.risk_score = 85
            mock_event.risk_level = "high"
            mock_event.summary = "Test event"
            mock_event.reviewed = False
            mock_event.started_at = datetime(2024, 1, 1)

            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_event
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()
            mock_get_session.return_value = mock_session

            result = await _load_event(event_id)

        # the executed statement must carry an id filter bound to this uuid
        stmt = mock_session.execute.call_args[0][0]
        assert str(stmt).lower().count("where") == 1

        assert result == {
            "id": event_id,
            "camera_id": "cam1",
            "risk_score": 85,
            "risk_level": "high",
            "summary": "Test event",
            "reviewed": False,
            "started_at": "2024-01-01T00:00:00",
        }
```

### T6 — pre-configured singletons carry the correct loader/prefix/type/ttl (kills C31, C32, C33)
```python
    @pytest.mark.asyncio
    async def test_alert_cache_singleton_has_correct_wiring(self, mock_settings):
        """The alert singleton must be wired with the alerts prefix/loader/type/ttl.

        Kills C31/C32/C33: loader/cache_type/cache_prefix/ttl dropped or case-flipped.
        // UNVERIFIED - not yet run red/green
        """
        from backend.services.read_through_cache import (
            _load_alert_rule,
            get_alert_read_through_cache,
        )

        await reset_read_through_caches()
        with patch(
            "backend.services.read_through_cache.get_settings",
            return_value=mock_settings,
            autospec=True,
        ):
            cache = await get_alert_read_through_cache()

        assert cache._prefix == "alerts"
        assert cache._loader is _load_alert_rule
        assert cache._cache_type == "alerts"
        assert cache._ttl == mock_settings.cache_default_ttl
        await reset_read_through_caches()
```

## Covering test file(s)
- `backend/tests/unit/services/test_read_through_cache.py` — every cluster's covering tests live here (classes `TestReadThroughCache`, `TestPreConfiguredCaches`, `TestStampedeProtection`, `TestReadThroughCacheErrorHandling`, `TestPreConfiguredCachesExtended`).

## TDD procedure (one line)
Add each test above, run targeted pytest — assert must FAIL (red) on the mutant diff (key/arg/`call_args` mismatch), then PASS (green) on the unmutated `backend/services/read_through_cache.py`.
