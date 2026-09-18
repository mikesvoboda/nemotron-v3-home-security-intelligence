# WP4.4 Triage Dossier — `backend/services/websocket_service.py`

- **Module:** `backend/services/websocket_service.py` (WebSocket sharded pub/sub, NEM-3415)
- **Verdict source:** `mutants/backend/services/websocket_service.py.meta` → `exit_code_by_key`
- **Totals:** 204 mutants · **69 SURVIVED** · 135 killed · 0 unchecked
- **Diff source:** `uv run mutmut show <key>` (all 69 fetched cleanly; no manual fallback needed)
- **Covering tests:** `backend/tests/unit/services/test_websocket_service.py` (993 lines, the sole covering file per `tests_by_mangled_function_name`)
- **Status of drafted tests:** UNVERIFIED — not yet run red/green (harness constraint: no pytest execution).

## Headline

68 of the 69 survivors are **purely logging mutations** or **dead/equivalent tweaks**. The sharded
message dict (the one thing consumers actually parse) is fully test-guarded — every key mutation on
the *published* message dict was killed by `test_publish_event_message_format`
(`test_websocket_service.py:316`, asserts `message["camera_id"]/["event_type"]/["payload"]/["correlation_id"]`).
The 9 genuine TEST-GAPs are all **observability/wiring the tests never pin**: the hash radix, the
singleton constructor's redis/base_channel wiring, the `subscribe_cameras` shard-channel + active-shard
tracking, the `subscribe_all_shards` counter accumulator, and the `get_shard_channel` method's
base-channel argument. Every one is a one-line assertion away from dead.

## Per-cluster table

Legend: keys abbreviated by function; full key = `backend.services.websocket_service.` + shown.

| # | Function / concern | Pattern | Keys (≤3 ex.) | Count | Class | Why |
|---|--------------------|---------|---------------|:-----:|-------|-----|
| C1 | `_get_shard` | `hashlib.md5(..., usedforsecurity=False)` → `None` / arg-dropped / `True` | `x__get_shard__mutmut_3` `_5` `_6` | 3 | EQUIVALENT | Non-FIPS CPython: digest byte-identical regardless of `usedforsecurity`. Tests run non-FIPS → output unchanged. |
| C2 | `_get_shard` | `int(hash_digest, 16) % n` → `int(hash_digest, 17)` | `x__get_shard__mutmut_12` | 1 | **TEST-GAP** | Base-16→17 re-maps every camera to a different shard. `test_specific_camera_id_shard` (`:157`) only checks bounds + self-consistency, never the actual value. Golden pin kills it. |
| C3 | `get_websocket_sharded_service` | `logger.info(f"...{shard_count} shards")` msg → `None` | `x_get_websocket_sharded_service__mutmut_11` | 1 | EQUIVALENT | Log message text only; no control-flow/return effect. |
| C4 | `get_websocket_sharded_service` | singleton ctor: `redis_client=redis_client`→`None`; `base_channel=base_channel`→`None`/arg-dropped | `..._service__mutmut_5` `_7` `_10` | 3 | **TEST-GAP** | Singleton would hold `_redis=None` and default channel. `TestGetWebSocketShardedService` (`:541`) passes only `redis`+`shard_count`, asserts only identity + `shard_count` — never `_redis` or a non-default `base_channel`. |
| C5 | `WebSocketShardedService.__init__` | `self._subscriptions = {}` → `None` | `xǁWebSocketShardedServiceǁ__init____mutmut_5` | 1 | EQUIVALENT | Dead attribute: assigned once, never read anywhere in the repo (verified by grep). |
| C6 | `.get_shard_channel` (method) | `_get_shard_channel(shard, self._base_channel)` → drops `self._base_channel` arg | `xǁ…ǁget_shard_channel__mutmut_4` | 1 | **TEST-GAP** | Returns `events:shard:N` instead of `{custom}:shard:N` for a non-default-base service. `test_get_shard_channel_method` (`:246`) uses `base_channel="events"` so default == mutant. No method test uses a custom base. |
| C7 | `.publish_event` | success-path `logger.debug` — msg→`None`, `extra`→`None`/removed, `extra` keys `XX…XX`/`UPPERCASE` (`camera_id`,`event_type`,`shard`,`channel`,`subscribers`) | `xǁ…ǁpublish_event__mutmut_25` `_26` `_28` | 13 | LOW-VALUE | Structured-log `extra` fields + msg text. Real change to log records; no test asserts log records (only `redis.publish` args, which are intact). |
| C8 | `.publish_event` | failure-path `logger.error` — msg→`None`, `extra`→`None`/removed, `extra` keys cased, `exc_info`→`None`/removed/`False` | `xǁ…ǁpublish_event__mutmut_39` `_40` `_41` | 12 | LOW-VALUE | Exception still `raise`d (verified — `raise` untouched; killed mutant covers that). Only error-record fields differ. `test_publish_event_handles_redis_error` (`:631`) asserts the raise, not the log. |
| C9 | `.subscribe_all_shards` | `self._subscribe_count += 1` → `= 1` | `xǁ…ǁsubscribe_all_shards__mutmut_11` | 1 | **TEST-GAP** | `+= 1` vs `= 1` diverge only on the **2nd** call. `test_subscribe_all_shards_increments_counter` (`:772`) calls it exactly once (0→1 == 1). Second-call assert kills it. |
| C10 | `.subscribe_all_shards` | log msg text: `logger.warning(json-fail)`, cancel-`logger.debug`, all-shard `logger.debug` → `None`/cased | `xǁ…ǁsubscribe_all_shards__mutmut_4` `_26` `_28` | 6 | EQUIVALENT | Message text only. |
| C11 | `.subscribe_all_shards` | `logger.debug(extra={"channels":…})` → `None`/removed, key `XXchannelsXX`/`CHANNELS` | `xǁ…ǁsubscribe_all_shards__mutmut_5` `_7` `_8` | 4 | LOW-VALUE | Structured-log `extra` field, unasserted. |
| C12 | `.subscribe_cameras` | `channels = [get_shard_channel(shard) …]` → `get_shard_channel(None)` | `xǁ…ǁsubscribe_cameras__mutmut_7` | 1 | **TEST-GAP** | Subscribes to `events:shard:None` instead of the real shard channels. No `subscribe_cameras` test asserts `_subscribed_channels` (only the all-shards test at `:749` does); message-filtering still passes. |
| C13 | `.subscribe_cameras` | active-subscription tracking `.add(shard)`/`.discard(shard)` → `.add(None)`/`.discard(None)` | `xǁ…ǁsubscribe_cameras__mutmut_23` `_56` | 2 | **TEST-GAP** | `active_shards` becomes `{None}` and cleanup fails to remove real shards. `test_stats_track_active_subscriptions` (`:912`) only asserts `>= 1`; exact `active_shards` value asserted only for the all-shards path (`:835`). |
| C14 | `.subscribe_cameras` | `data.decode("utf-8")` → `decode("UTF-8")` | `xǁ…ǁsubscribe_cameras__mutmut_36` | 1 | EQUIVALENT | Codec alias — identical decode. |
| C15 | `.subscribe_cameras` | success `logger.debug` — msg→`None`, `extra`→`None`/removed, keys `XX…`/`UPPERCASE` (`camera_ids`,`shards`,`channels`) | `xǁ…ǁsubscribe_cameras__mutmut_8` `_9` `_11` | 9 | LOW-VALUE | Structured-log `extra` fields, unasserted. |
| C16 | `.subscribe_cameras` | log msg text: json-fail `warning`, cancel `debug`, cleanup-fail `debug`, error-msg → `None`/cased | `xǁ…ǁsubscribe_cameras__mutmut_39` `_46` `_47` | 7 | EQUIVALENT | Message text only. |
| C17 | `.subscribe_cameras` | `logger.error(..., exc_info=True)` → `exc_info` `None`/removed/`False` | `xǁ…ǁsubscribe_cameras__mutmut_51` `_53` `_54` | 3 | LOW-VALUE | exc_info attachment on error record. Exception still raised (`test_subscribe_cameras_handles_general_exception` `:670` proves the raise, not the record). |

**Totals:** TEST-GAP = **9** (C2, C4, C6, C9, C12, C13) · EQUIVALENT = **19** (C1, C3, C5, C10, C14, C16) · LOW-VALUE = **41** (C7, C8, C11, C15, C17). **9+19+41 = 69.** ✓

## Why the LOW-VALUE/EQUIVALENT split

- **EQUIVALENT** = pure message-text (log msg string or codec alias), dead attribute, or a hint arg
  (`usedforsecurity`) whose value cannot change output in the non-FIPS test env. Semantically
  identical to the original at runtime.
- **LOW-VALUE** = a genuine change to the emitted log record (`extra` payload keys, `exc_info`
  flag) — behavior nobody should assert. `extra`/`exc_info` DO produce observable differences in a
  log record, so they are not EQUIVALENT, but no sane consumer test pins structured-log field names.

## Drafted kill-tests (all UNVERIFIED — not yet run red/green)

TDD procedure (applies to each): land the test, run it against the surviving **mutant** source → it
must go RED (assertion false under the mutant's one-line diff); run against the **original**
`backend/services/websocket_service.py` → it must go GREEN. Add to the matching class in
`backend/tests/unit/services/test_websocket_service.py`.

### T1 — `test_get_shard_golden_values` (kills C2, cluster x__get_shard__mutmut_12)

Add to `class TestGetShard` (after `test_specific_camera_id_shard`, `:157`). The existing
"regression test" checks only bounds + self-consistency; pin the actual MD5-derived values.

```python
    def test_get_shard_golden_values(self) -> None:
        """Lock the exact MD5-based shard mapping (kills radix/base mutations)."""
        # Computed from hashlib.md5(cid).hexdigest() base-16 % n. Any change to the
        # radix (e.g. int(...,16)->int(...,17)) or hash reorders these and fails.
        assert _get_shard("front_door", 16) == 14
        assert _get_shard("back_yard", 16) == 9
        assert _get_shard("garage", 16) == 1
        assert _get_shard("cam_1", 16) == 7
        assert _get_shard("front_door", 4) == 2
        assert _get_shard("cam_1", 32) == 23
```

- On mutant `_12` (base 17): `front_door`→6 ≠ 14 → **RED**. On original: all equal → **GREEN**.
- C1 (usedforsecurity) still passes this test (digest unchanged) — correct, C1 is EQUIVALENT.

### T2 — `test_get_shard_channel_method_custom_base_channel` (kills C6)

Add to `class TestWebSocketShardedService` (near `test_get_shard_channel_method`, `:246`).

```python
    def test_get_shard_channel_method_custom_base_channel(self) -> None:
        """get_shard_channel/get_camera_channel must honor the instance base_channel."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=16, base_channel="security")

        assert service.get_shard_channel(7) == "security:shard:7"
        # and the camera-channel path carries the custom prefix too
        assert service.get_camera_channel("front_door") == "security:shard:14"
```

- On mutant `get_shard_channel__mutmut_4` (drops `self._base_channel`): returns `"events:shard:7"` → **RED**. On original → **GREEN**.

### T3 — `test_subscribe_cameras_subscribes_expected_channels_and_tracks_shards` (kills C12 + C13)

Add to `class TestSubscribeCameras` (after `test_subscribe_cameras_skips_non_message_types`, `:477`).

```python
    @pytest.mark.asyncio
    async def test_subscribe_cameras_subscribes_expected_channels_and_tracks_shards(self) -> None:
        """subscribe_cameras subscribes to the right shard channels and tracks exact shards."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=16)
        camera_ids = ["front_door", "back_yard"]
        redis.set_pubsub_messages(
            [{"type": "message", "data": json.dumps({"camera_id": "front_door", "event": "1"})}]
        )

        expected_channels = {
            service.get_shard_channel(s) for s in service.get_shards_for_cameras(camera_ids)
        }
        expected_shards = service.get_shards_for_cameras(camera_ids)

        async for _event in service.subscribe_cameras(camera_ids):
            pubsub = redis._pubsub_instance
            # C12: channels built from real shard numbers, not get_shard_channel(None)
            assert set(pubsub._subscribed_channels) == expected_channels
            # C13 (add): active shards are the real numbers, not {None}
            assert set(service.get_stats()["active_shards"]) == expected_shards
            break

        # C13 (discard): cleanup removed the real shards on exit
        assert service.get_stats()["active_shards"] == []
```

- On `subscribe_cameras__mutmut_7` (get_shard_channel(None)): subscribed = `{"events:shard:None"}` → **RED**.
- On `mutmut_23` (add(None)): in-loop `active_shards == {None}` → **RED**.
- On `mutmut_56` (discard(None)): post-exit `active_shards == [14, 9]` ≠ `[]` → **RED**. On original → all **GREEN**.

### T4 — `test_subscribe_all_shards_increments_counter_across_calls` (kills C9)

Add to `class TestSubscribeAllShards` (after `test_subscribe_all_shards_increments_counter`, `:772`).

```python
    @pytest.mark.asyncio
    async def test_subscribe_all_shards_increments_counter_across_calls(self) -> None:
        """_subscribe_count is a running total across successive subscribe_all_shards calls."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=4)
        messages = [{"type": "message", "data": json.dumps({"camera_id": "test", "event": "1"})}]

        redis.set_pubsub_messages(messages)
        async for _ in service.subscribe_all_shards():
            break
        assert service.subscribe_count == 1

        redis.set_pubsub_messages(messages)  # fresh pubsub for the 2nd subscription
        async for _ in service.subscribe_all_shards():
            break
        assert service.subscribe_count == 2
```

- On `subscribe_all_shards__mutmut_11` (`= 1`): after 2nd call count stays 1 → `== 2` **RED**. First `== 1` passes on both (why the existing single-call test missed it). On original → **GREEN**.

### T5 — `test_get_websocket_sharded_service_wires_redis_and_base_channel` (kills C4)

Add to `class TestGetWebSocketShardedService` (near `:545`). Existing singleton tests pass only
`shard_count` and never touch `_redis` or a custom `base_channel`.

```python
    @pytest.mark.asyncio
    async def test_get_websocket_sharded_service_wires_redis_and_base_channel(self) -> None:
        """The singleton is constructed with the passed redis client and base_channel."""
        redis = _FakeRedis()

        service = await get_websocket_sharded_service(
            redis, shard_count=8, base_channel="alerts"
        )

        assert service.shard_count == 8
        assert service._redis is redis          # kills redis_client=None
        assert service.base_channel == "alerts" # kills base_channel=None / dropped
```

- On `get_websocket_sharded_service__mutmut_5` (`redis_client=None`): `_redis is None` → **RED**.
- On `_mutmut_7` (`base_channel=None`): `base_channel == None` → **RED**.
- On `_mutmut_10` (arg dropped → default `"events"`): `base_channel == "events"` ≠ `"alerts"` → **RED**. On original → all **GREEN**.

## Covering-test file references (for the fixing engineer)

`backend/tests/unit/services/test_websocket_service.py`
- `TestGetShard` `:82`–`:186` — hash tests; weak pin at `test_specific_camera_id_shard:157`.
- `TestWebSocketShardedService.test_get_shard_channel_method:246` — default base only.
- `TestSubscribeCameras:416`–`:502` — filters/bytes/non-message; **no channel assertion**.
- `TestSubscribeAllShards.test_subscribe_all_shards_subscribes_to_all_channels:749` (asserts `_subscribed_channels`, exact 4) — the pattern T3 borrows.
- `TestSubscribeAllShards.test_subscribe_all_shards_increments_counter:772` — single-call only.
- `TestSubscribeAllShards.test_subscribe_all_shards_tracks_active_shards:835` (exact `active_shards`) vs `TestStatsTrackingAdvanced.test_stats_track_active_subscriptions:912` (only `>= 1`).
- `TestGetWebSocketShardedService:541` — singleton, never passes/asserts base_channel or `_redis`.
