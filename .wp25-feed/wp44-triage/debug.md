# WP4.4 Triage Dossier — backend/api/routes/debug.py

Generated 2026-09-17 by triage wave (UNVERIFIED: no tests run; diffs read via `uv run mutmut show`).

## Raw counts

- Verdict file: `mutants/backend/api/routes/debug.py.meta` — 406 keys total: **107 survived (exit_code 0)**, 55 killed, 244 still null (unchecked). This triage covers only the 107 survivors.
- Full survivor diff dump (working evidence): `/tmp/wp25/wp44-triage/debug.diff` (all 107 diffs, one block per key).

## Covering tests (from mutmut-stats.json `tests_by_mangled_function_name`)

| Function | Survivors | Covering tests |
|---|---|---|
| `_get_redis_info` | 79 | `backend/tests/unit/api/routes/test_debug.py` — `TestDebugRedisInfoEndpoint` (:182), `TestRedisInfoHelpers` (:387); mock Redis fixture with full INFO dict at :23 |
| `_get_websocket_broadcaster_status` | 12 | `backend/tests/unit/api/routes/test_debug.py` — `TestDebugWebSocketConnectionsEndpoint::test_get_websocket_connections_returns_state` (:237) |
| `record_pipeline_error_to_redis` | 16 | `backend/tests/unit/api/routes/test_debug_api.py` — `TestRecordPipelineErrorToRedis` (:593) |

Why they survive (root cause): the existing tests assert only **presence** (`"status" in data`, `"info" in data`, `assert_called_once()` with no args) and never assert **values or call arguments**. E.g. `test_get_redis_info_returns_stats` (test_debug.py:186) checks three key-presence assertions on a fully-populated response; `test_record_error_stores_in_redis` (test_debug_api.py:597) checks the three Redis calls happened but not *with what*.

## Cluster table (counts sum to 107)

| # | Cluster (pattern @ function/concern) | Count | Class | Example keys (≤3) | Why it survives |
|---|---|---|---|---|---|
| 1 | `info_dict = None` whole-assignment swap @ `_get_redis_info` | 1 | TEST-GAP | `x__get_redis_info__mutmut_5` | success test only asserts `"info" in data`; `info: dict \| None` in the schema, so `None` sails through |
| 2 | info_dict **output keys renamed** (`"XXkeyXX"` / `"KEY_UPPER"`) @ `_get_redis_info` | 14 | TEST-GAP | `_6`, `_7`, `_16` (also `_25,_26,_35,_36,_45,_46,_54,_55,_63,_64`) | response payload key set never asserted |
| 3 | info **lookup keys mutated** (`info.get(None/XX/UPPER/0, …)`) → real INFO values silently become `unknown`/`0`/`None` @ `_get_redis_info` | 28 | TEST-GAP | `_8`, `_12`, `_20` (also `_13,_18,_22,_23,_27,_29,_31,_32,_37,_39,_41,_42,_47,_49,_51,_52,_56,_58,_60,_61,_65,_67,_69,_70`) | mock INFO fixture (:23-33) contains every real value, but no test compares extracted values |
| 4 | info `.get(key, DEFAULT)` **default tweaks** (`unknown`↔`UNKNOWN`/None/0↔1/default dropped) @ `_get_redis_info` | 24 | LOW-VALUE | `_9`, `_24`, `_71` (all `_11,_14,_15,_19,_21,_28,_30,_33,_34,_38,_40,_43,_44,_48,_50,_53,_57,_59,_62,_66,_68`) | only observable when Redis INFO omits a field; tests always feed a complete dict. Debug-panel fallback cosmetics; killable via the bonus method in Draft A if the feed wants them gone |
| 5 | pub/sub **bytes-decode guards disabled** (`isinstance(...) and False`) and `channel_counts = None` @ `_get_redis_info` | 3 | TEST-GAP | `_74`, `_77`, `_78` | `test_redis_info_handles_string_channels` asserts only `channel in channels` membership; decoded-key mapping and `subscriber_counts` payload never asserted |
| 6 | pubsub dict **key renames** (`subscriber_counts` → XX/UPPER, both success and error-fallback dicts) @ `_get_redis_info` | 4 | TEST-GAP | `_83`, `_84`, `_89` (also `_90`) | pubsub-error test asserts `["channels"] == []` only; success test asserts nothing inside `pubsub` |
| 7 | `logger.warning(f"…")` → `logger.warning(None)` @ `_get_redis_info` (both except handlers) | 2 | EQUIVALENT | `_85`, `_93` | log-message text only; no API/return-value effect, no caplog assertions in this suite |
| 8 | status/error **string literals mutated** (`"connected"`→`"XXconnectedXX"`/`"CONNECTED"`; error detail `str(e)`→`str(None)`) @ `_get_redis_info` | 3 | TEST-GAP | `_91`, `_92`, `_98` | success path only checks `"status" in data`; error test checks `"error" in info` but not the message. (`"unavailable"` IS asserted, which is why its literal mutants died) |
| 9 | redundant `channel_name=None,` **arg removal** from `DebugWebSocketBroadcasterStatus(...)` (both else-branches) @ `_get_websocket_broadcaster_status` | 2 | EQUIVALENT | `_11`, `_27` | field has Pydantic `default=None` (debug.py:156) — constructed model identical |
| 10 | **null-broadcaster default status fields mutated** (`connection_count=0`→1, `is_listening/is_degraded=False`→True, `circuit_state="UNKNOWN"`→XX/lower; event + system branches) @ `_get_websocket_broadcaster_status` | 10 | TEST-GAP | `_12`, `_15`, `_29` (also `_13,_14,_16,_28,_30,_31,_32`) | the one covering test asserts only `"connection_count" in data[…]`; broadcasters are `None` under test, so this IS the executed branch |
| 11 | Redis **key argument → `None`** (`lpush`/`ltrim`/`expire(PIPELINE_ERRORS_KEY→None, …)`) @ `record_pipeline_error_to_redis` | 3 | TEST-GAP | `_11`, `_16`, `_25` | tests assert `assert_called_once()` with no argument check |
| 12 | `ltrim` **argument mutations** (start/end → None, arg shift `ltrim(0, max-1)`, arg truncation) @ `record_pipeline_error_to_redis` | 5 | TEST-GAP | `_17`, `_19`, `_21` (also `_18,_20`) | AsyncMock accepts anything; call args never inspected |
| 13 | `ltrim` **trim-boundary off-by-ones** (`start 0`→1 drops the *newest* error just pushed; `max-1`→`max+1`/`max-2` breaks the cap) @ `record_pipeline_error_to_redis` | 3 | TEST-GAP | `_22`, `_23`, `_24` | highest-real-harm cluster here: `_22` silently discards every recorded error; nothing asserts trim bounds |
| 14 | `expire` **argument mutations** (`ttl`→None, arg shift `expire(TTL_SECONDS)`, arg truncation) @ `record_pipeline_error_to_redis` | 3 | TEST-GAP | `_26`, `_27`, `_28` | TTL contract (list expiry, prevents leaked Redis keys) unasserted |
| 15 | **naive timestamp** (`datetime.now(UTC)` → `datetime.now(None)` → tz-naive local ISO string) @ `record_pipeline_error_to_redis` | 1 | TEST-GAP | `_4` | error-without-message test asserts `"timestamp" in stored_data` (presence) only; downstream `_get_recent_errors` sorts/compares these stamps |
| 16 | `logger.warning(f"…")` → `logger.warning(None)` @ `record_pipeline_error_to_redis` except-handler | 1 | EQUIVALENT | `_30` | log text only |

**Classification totals:** TEST-GAP 101 (clusters 1,2,3,5,6,8,10,11,12,13,14,15), LOW-VALUE 24 (cluster 4), EQUIVALENT 6 (clusters 7,9,16). 101+24+6 = 107.

## Drafted tests

All UNVERIFIED — not yet run red/green. TDD procedure (same for each): run the new test against the mutant copy (`uv run mutmut show <key>` diff applied) → assertion fails (red); run against `backend/api/routes/debug.py` original → passes (green); spot-check one key per killed cluster.

### Draft A — `test_debug.py` :: `TestRedisInfoHelpers.test_redis_info_info_dict_exact` (+2 methods)
Kills clusters 1, 2, 3, and 8's `_91/_92` (bonus method kills cluster 4); exact-dict equality on `info` is the load-bearing assertion.

```python
    # ---- WP4.4 finding feed: debug.py survivors 5-71, 91, 92, 98 ----
    # UNVERIFIED - not yet run red/green
    @pytest.mark.asyncio
    async def test_redis_info_info_dict_exact(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Every Redis INFO field must surface under its exact key with its real value."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        async def mock_redis_gen():
            yield mock_redis

        with patch(
            "backend.api.routes.debug.get_settings", return_value=debug_settings, autospec=True
        ):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with authenticated_async_client() as client:
                    response = await client.get("/api/debug/redis/info")

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "connected"  # kills _91/_92
                assert data["info"] == {  # kills _5 (None), _6/_7-likes (renames), _8/_12/_20-likes (bad lookups)
                    "redis_version": "7.0.0",
                    "connected_clients": 3,
                    "used_memory_human": "1.5M",
                    "used_memory_peak_human": "2.0M",
                    "total_connections_received": 100,
                    "total_commands_processed": 5000,
                    "uptime_in_seconds": 86400,
                }
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_redis_info_error_message_preserved(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """The INFO failure detail string must be surfaced verbatim for operators."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        mock_redis.info = AsyncMock(side_effect=Exception("boom-detail-xyz"))

        async def mock_redis_gen():
            yield mock_redis

        with patch(
            "backend.api.routes.debug.get_settings", return_value=debug_settings, autospec=True
        ):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with authenticated_async_client() as client:
                    response = await client.get("/api/debug/redis/info")

                data = response.json()
                assert data["status"] == "error"
                assert data["info"]["error"] == "boom-detail-xyz"  # kills _98
            finally:
                app.dependency_overrides.clear()

    # Bonus (kills LOW-VALUE cluster 4 if the feed wants it; keep only if cheap):
    @pytest.mark.asyncio
    async def test_redis_info_defaults_when_fields_missing(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Missing INFO fields must fall back to the documented sentinel defaults."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        mock_redis.info = AsyncMock(return_value={})

        async def mock_redis_gen():
            yield mock_redis

        with patch(
            "backend.api.routes.debug.get_settings", return_value=debug_settings, autospec=True
        ):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with authenticated_async_client() as client:
                    response = await client.get("/api/debug/redis/info")

                assert response.json()["info"] == {
                    "redis_version": "unknown",
                    "connected_clients": 0,
                    "used_memory_human": "unknown",
                    "used_memory_peak_human": "unknown",
                    "total_connections_received": 0,
                    "total_commands_processed": 0,
                    "uptime_in_seconds": 0,
                }
            finally:
                app.dependency_overrides.clear()
```

### Draft B — `test_debug.py` :: `TestRedisInfoHelpers.test_redis_info_pubsub_payload_exact` (+1 method)
Kills clusters 5, 6. The mock fixture already returns bytes channels + numsub pairs (test_debug.py:36-37), so exact-equality on the decoded payload is free.

```python
    # UNVERIFIED - not yet run red/green
    @pytest.mark.asyncio
    async def test_redis_info_pubsub_payload_exact(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Channels must be decoded to str and mapped to exact subscriber counts."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        async def mock_redis_gen():
            yield mock_redis

        with patch(
            "backend.api.routes.debug.get_settings", return_value=debug_settings, autospec=True
        ):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with authenticated_async_client() as client:
                    response = await client.get("/api/debug/redis/info")

                assert response.json()["pubsub"] == {  # kills _74/_78 (undecoded bytes), _77 (None), _83/_84 (renames)
                    "channels": ["security_events", "system_status"],
                    "subscriber_counts": {"security_events": 2, "system_status": 1},
                }
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_redis_info_pubsub_error_fallback_exact(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Pubsub failure fallback must use the exact documented empty-payload keys."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        mock_redis.pubsub_channels = AsyncMock(side_effect=Exception("Pubsub failed"))

        async def mock_redis_gen():
            yield mock_redis

        with patch(
            "backend.api.routes.debug.get_settings", return_value=debug_settings, autospec=True
        ):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with authenticated_async_client() as client:
                    response = await client.get("/api/debug/redis/info")

                assert response.json()["pubsub"] == {  # kills _89/_90
                    "channels": [],
                    "subscriber_counts": {},
                }
            finally:
                app.dependency_overrides.clear()
```

### Draft C — `test_debug.py` :: `TestDebugWebSocketConnectionsEndpoint.test_get_websocket_connections_null_broadcaster_defaults`
Kills cluster 10 (all 10). Patch both broadcaster globals to `None` for determinism — the function imports them at call time (debug.py:446-447), so `patch.object` on the module attribute is honored.

```python
    # UNVERIFIED - not yet run red/green
    @pytest.mark.asyncio
    async def test_get_websocket_connections_null_broadcaster_defaults(
        self, debug_settings: Settings
    ) -> None:
        """With no live broadcasters, both statuses must report the exact null-state tuple."""
        from backend.core.redis import get_redis_optional
        from backend.main import app
        from backend.services import event_broadcaster, system_broadcaster

        async def mock_redis_gen():
            yield MagicMock()

        with (
            patch.object(event_broadcaster, "_broadcaster", None),
            patch.object(system_broadcaster, "_system_broadcaster", None),
            patch(
                "backend.api.routes.debug.get_settings", return_value=debug_settings, autospec=True
            ),
        ):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with authenticated_async_client() as client:
                    response = await client.get("/api/debug/websocket/connections")

                assert response.status_code == 200
                data = response.json()
                null_state = {
                    "connection_count": 0,
                    "is_listening": False,
                    "is_degraded": False,
                    "circuit_state": "UNKNOWN",
                    "channel_name": None,
                }
                assert data["event_broadcaster"] == null_state  # kills _12.._16
                assert data["system_broadcaster"] == null_state  # kills _28.._32
            finally:
                app.dependency_overrides.clear()
```

### Draft D — `test_debug_api.py` :: `TestRecordPipelineErrorToRedis.test_record_error_redis_call_contract`
Kills clusters 11, 12, 13, 14 (11 mutants) in one shot: exact `assert_called_once_with` on ltrim/expire plus lpush key check.

```python
    # UNVERIFIED - not yet run red/green
    @pytest.mark.asyncio
    async def test_record_error_redis_call_contract(self, mock_redis: MagicMock) -> None:
        """lpush/ltrim/expire must each hit the pipeline-errors key with exact bounds/TTL."""
        import json

        from backend.api.routes.debug import (
            PIPELINE_ERRORS_KEY,
            PIPELINE_ERRORS_MAX_SIZE,
            PIPELINE_ERRORS_TTL_SECONDS,
            record_pipeline_error_to_redis,
        )

        mock_redis.lpush = AsyncMock(return_value=1)
        mock_redis.ltrim = AsyncMock(return_value=True)
        mock_redis.expire = AsyncMock(return_value=True)

        result = await record_pipeline_error_to_redis(
            redis=mock_redis,
            error_type="connection_error",
            component="detector",
            message="boom",
        )

        assert result is True
        push_key, push_payload = mock_redis.lpush.call_args[0]
        assert push_key == PIPELINE_ERRORS_KEY  # kills _11
        stored = json.loads(push_payload)
        assert stored["error_type"] == "connection_error"
        assert stored["component"] == "detector"
        assert stored["message"] == "boom"
        # kills _16.._24 — notably _22 (start=1 would drop the newest error) and _23/_24 (cap drift)
        mock_redis.ltrim.assert_called_once_with(PIPELINE_ERRORS_KEY, 0, PIPELINE_ERRORS_MAX_SIZE - 1)
        # kills _25.._28
        mock_redis.expire.assert_called_once_with(PIPELINE_ERRORS_KEY, PIPELINE_ERRORS_TTL_SECONDS)
```

### Draft E — `test_debug_api.py` :: `TestRecordPipelineErrorToRedis.test_record_error_timestamp_is_utc`
Kills cluster 15 (`mutmut_4`).

```python
    # UNVERIFIED - not yet run red/green
    @pytest.mark.asyncio
    async def test_record_error_timestamp_is_utc(self, mock_redis: MagicMock) -> None:
        """Recorded timestamp must be tz-aware UTC (downstream error retrieval compares them)."""
        import json
        from datetime import datetime, timedelta

        from backend.api.routes.debug import record_pipeline_error_to_redis

        mock_redis.lpush = AsyncMock(return_value=1)
        mock_redis.ltrim = AsyncMock(return_value=True)
        mock_redis.expire = AsyncMock(return_value=True)

        assert await record_pipeline_error_to_redis(
            redis=mock_redis, error_type="e", component="c"
        ) is True

        stored = json.loads(mock_redis.lpush.call_args[0][1])
        ts = datetime.fromisoformat(stored["timestamp"])
        assert ts.tzinfo is not None and ts.utcoffset() == timedelta(0)  # kills _4 (datetime.now(None) → naive)
```

## Kill forecast if drafts land

- Drafts A–E kill 91 of the 107 survivors (clusters 1,2,3,5,6,8,10,11,12,13,14,15 = 78, plus the optional A-bonus method takes cluster 4's 24 → up to 102).
- The remaining 6 (clusters 7, 9, 16) are classified EQUIVALENT and are not killable by any value-observing test — candidates for the baseline suppression list.
- 244 keys in the meta file are still `null` (run incomplete); cluster analysis here covers only the checked slice, and the untested tail likely contains the same per-field patterns (mutants 1-4 of `_get_redis_info` region, etc.) — re-run this clustering against the full verdict set when the run completes.

## TDD procedure (one line, applies to all drafts)

For each drafted test: apply the mutant (view via `uv run mutmut show <key>`) → new assertion fails (RED); check out the original file → test passes (GREEN); keep RED-proof per cluster by spot-killing the example keys listed in the cluster table.
