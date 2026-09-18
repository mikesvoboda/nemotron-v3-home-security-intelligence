# WP4.4 Triage Dossier — backend/services/redis_streams.py

- Survivors: **184** (of 913 generated for this module; exit_code==0 in `mutants/backend/services/redis_streams.py.meta`)
- Diffs verified with `uv run mutmut show <key>` (all 184; zero failures). Condensed change-lines: `/tmp/wp25/wp44-triage/summary.txt`, raw diffs: `/tmp/wp25/wp44-triage/diffs/<key>.diff` (prefix `backend.services.redis_streams.`).
- Covering test files (from `mutmut-stats.json` `tests_by_mangled_function_name`):
  - `backend/tests/unit/services/test_redis_streams.py` (unit; mock `RedisClient` with `AsyncMock` `_client`; class-per-method suites)
  - `backend/tests/unit/services/test_redis_streams_integration.py` (mock-based "integration" path; fixtures `analysis_stream_service` / `mock_redis_client`)

## Headline

129 TEST-GAP / 55 EQUIVALENT / 0 LOW-VALUE. Two systematic root causes:

1. **Redis call-argument contracts are never asserted on the Analysis side** — AsyncMock returns canned values no matter what args are passed, so `None`/removed/garbage arguments to `xgroup_create`, `xreadgroup`, `xautoclaim`, `xpending_range`, `xadd` all survive. The Detection side has such assertions (`call_args[1]["block"]`, `xack.assert_called_once_with(...)`) — the Analysis twins have none.
2. **Result dicts/fields are only partially asserted** — tests assert 2–3 of 6 keys (`length`, `groups`, `last_entry_id`), so every other key rename, lookup-key flip and default tweak survives.
   Plus a subtle singleton trap: `test_creates_singleton` asserts `service1 is service2`, which passes even when the factory is mutated to **never create** the service (`None is None` → True).

## Cluster table (counts sum to 184)

Key-prefix `backend.services.redis_streams.` omitted from keys below.

| #   | Function / concern                             | Pattern                                                                                                                                                       | n   | Class      | Example keys                                                           | Why                                                                                                                                                                                                                                                  |
| --- | ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- | --- | ---------- | ---------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `get_detection_stream_service`                 | singleton guard flip / service replaced by `None` / ctor args dropped (`redis_client=None`, `maxlen=None`, drop `maxlen=`)                                    | 5   | TEST-GAP   | `x_get_detection_stream_service__mutmut_1`, `__mutmut_3`, `__mutmut_5` | Only covering test asserts `service1 is service2` (test_redis_streams.py:656) — passes vacuously when factory returns `None` twice (`None is None`). `queue_max_size` mocked to 10000 == `DEFAULT_STREAM_MAXLEN`, so settings-wiring loss invisible. |
| 2   | `AnalysisStreamService._ensure_consumer_group` | `xgroup_create` args → `None`/removed/garbage (`stream_key`, `group`, `id="0"`→`"XX0XX"`/None, `mkstream=True`→False/None)                                    | 10  | TEST-GAP   | `..._ensure_consumer_group__mutmut_2`, `__mutmut_4`, `__mutmut_11`     | Covered only incidentally by consume/claim tests; `xgroup_create.call_args` never asserted on the Analysis side.                                                                                                                                     |
| 3   | `AnalysisStreamService._ensure_consumer_group` | log message text + `extra` dict key casing                                                                                                                    | 10  | EQUIVALENT | `__mutmut_12`, `__mutmut_16`, `__mutmut_19`                            | Pure logging text; nothing captures logger.                                                                                                                                                                                                          |
| 4   | `AnalysisStreamService._ensure_consumer_group` | memo flag `_group_created = None`                                                                                                                             | 1   | EQUIVALENT | `__mutmut_23`                                                          | Flag only used in truthiness guards; `None` behaves as `False`-then-`True`... same truthy value.                                                                                                                                                     |
| 5   | `AnalysisStreamService._ensure_consumer_group` | memo flag `_group_created = False` (never memoized)                                                                                                           | 1   | TEST-GAP   | `__mutmut_24`                                                          | Every consume/claim re-issues XGROUP CREATE (real perf/behavior regression). No `call_count==1` assertion exists for the Analysis service (unlike Detection, test_redis_streams.py:194).                                                             |
| 6   | `AnalysisStreamService.acknowledge`            | `result > 0` → `result >= 0`                                                                                                                                  | 1   | TEST-GAP   | `xǁAnalysisStreamServiceǁacknowledge__mutmut_9`                        | ack of nonexistent message now reports success. Detection has `test_acknowledge_not_found` (xack→0→False); Analysis twin test only exercises xack→1 (test_redis_streams_integration.py:257).                                                         |
| 7   | `AnalysisStreamService.add_batch`              | `xadd` kwargs: `maxlen`→None/dropped, `approximate`→None/dropped, stream key→None                                                                             | 5   | TEST-GAP   | `__mutmut_20`, `__mutmut_22`, `__mutmut_27`                            | Test asserts fields dict but never `xadd.call_args[0][0]` nor `call_args[1]` kwargs (integration test lines 202–207 assert fields only; maxlen/approx loss ⇒ unbounded stream growth).                                                               |
| 8   | `AnalysisStreamService.add_batch`              | `"timestamp"` stream field: key rename/case, value `str(None)`                                                                                                | 3   | TEST-GAP   | `__mutmut_10`, `__mutmut_12`                                           | Wire-format field; test never asserts `fields["timestamp"]` (Detection twin does, test_redis_streams.py:273).                                                                                                                                        |
| 9   | `AnalysisStreamService.add_batch`              | log text + `extra` keys                                                                                                                                       | 14  | EQUIVALENT | `__mutmut_28`, `__mutmut_32`, `__mutmut_35`                            | Pure logging.                                                                                                                                                                                                                                        |
| 10  | `AnalysisStreamService.consume_batches`        | `xreadgroup` call contract: group/consumer/streams-dict/count/block kwargs → None/dropped; block ternary `and False`/`or True`/always-None; `">"` → `"XX>XX"` | 14  | TEST-GAP   | `__mutmut_2`, `__mutmut_10`, `__mutmut_16`                             | Detection twin asserts `call_kwargs["block"]` both ways (test_redis_streams.py:373–392); Analysis has zero call-arg assertions. `"XX>XX"` as last-id breaks new-message delivery on a real server.                                                   |
| 11  | `AnalysisStreamService.consume_batches`        | parse identity: `message_id`→None, `delivery_count` 1→None/2/dropped in `from_stream_entry(...)`                                                              | 4   | TEST-GAP   | `__mutmut_21`, `__mutmut_23`, `__mutmut_27`                            | Test asserts batch_id/camera_id/detection_ids but not `msg.id` or `msg.delivery_count`. `msg.id=None` ⇒ worker acks `None` (message never leaves PEL); count=2 mis-feeds the DLQ threshold.                                                          |
| 12  | `AnalysisStreamService.claim_stale_messages`   | `xautoclaim` args: stream/group/consumer/min_idle → None/dropped; `start_id="0-0"` → None/`"XX0-0XX"`; `count`→None/dropped                                   | 13  | TEST-GAP   | `__mutmut_3`, `__mutmut_6`, `__mutmut_15`                              | Covering test only checks returned message content; no `xautoclaim.await_args` assertion.                                                                                                                                                            |
| 13  | `AnalysisStreamService.claim_stale_messages`   | `xpending_range` args: stream/group/min/max/count → None/dropped; `count=1`→`count=2`                                                                         | 11  | TEST-GAP   | `__mutmut_24`, `__mutmut_28`, `__mutmut_34`                            | Delivery-count lookup runs with garbage range args and is never asserted.                                                                                                                                                                            |
| 14  | `AnalysisStreamService.claim_stale_messages`   | claimed msg identity: `_text(message_id)` → `None` / `_text(None)`                                                                                            | 2   | TEST-GAP   | `__mutmut_38`, `__mutmut_44`                                           | Test never asserts `messages[0].id` (Detection twin does, test_redis_streams.py:485). `_text(None)` ⇒ id `"None"` silently.                                                                                                                          |
| 15  | `AnalysisStreamService.claim_stale_messages`   | `entry[:2]` → `entry[:3]`                                                                                                                                     | 1   | EQUIVALENT | `__mutmut_21`                                                          | redis-py parses XAUTOCLAIM entries as 2-tuples; slice of a 2-tuple never differs.                                                                                                                                                                    |
| 16  | `AnalysisStreamService.claim_stale_messages`   | log text + `extra` keys                                                                                                                                       | 10  | EQUIVALENT | `__mutmut_48`, `__mutmut_52`, `__mutmut_55`                            | Pure logging.                                                                                                                                                                                                                                        |
| 17  | `DetectionStreamService.get_stream_info`       | success-path output dict: returned-key rename / info lookup-key flip (`None`/case/`XX…XX`/`[1]` index)                                                        | 16  | TEST-GAP   | `__mutmut_17`, `__mutmut_23`, `__mutmut_57`                            | `test_get_stream_info_returns_stats` asserts only 3 of 6 output keys (test_redis_streams.py:599–601); `first_entry_id`/radix keys unobserved.                                                                                                        |
| 18  | `DetectionStreamService.get_stream_info`       | `info.get(...)` **default** values on success-path lines (`0`→None/drop/`1`, `""`→None/drop/`"XXXX"`) where input mock has every key                          | 15  | TEST-GAP   | `__mutmut_11`, `__mutmut_16`, `__mutmut_25`                            | Real contract ("missing key ⇒ 0/''") is simply never exercised — mock info carries all keys. Sparse-info test kills them.                                                                                                                            |
| 19  | `DetectionStreamService.get_stream_info`       | same default tweaks on `first-entry` **fallback** arg (lines where `if info.get("first-entry")` guard passes ⇒ default unreachable)                           | 3   | EQUIVALENT | `__mutmut_58`, `__mutmut_60`, `__mutmut_63`                            | Guard and value read the same key, so the `["…"]` default is dead code in both original and mutants.                                                                                                                                                 |
| 20  | `DetectionStreamService.get_stream_info`       | missing-key fallback dict (keys renamed / values `0`→`1`, `""`→`"XXXX"`)                                                                                      | 12  | TEST-GAP   | `__mutmut_77`, `__mutmut_79`, `__mutmut_88`                            | `test_get_stream_info_empty_stream` asserts only `length`/`groups`; rest of fallback contract unasserted.                                                                                                                                            |
| 21  | `DetectionStreamService.get_stream_info`       | `xinfo_stream(self._stream_key)` → `xinfo_stream(None)`                                                                                                       | 1   | TEST-GAP   | `__mutmut_7`                                                           | Wrong stream introspected in production; no call-arg assertion.                                                                                                                                                                                      |
| 22  | `DetectionStreamService.get_stream_info`       | first-entry guard `if info.get("first-entry")` → `and False` / wrong lookup key (`None`/case/`XX…XX`)                                                         | 4   | TEST-GAP   | `__mutmut_55`, `__mutmut_65`, `__mutmut_66`                            | Guarded branch always falls to `""` ⇒ `first_entry_id` silently wrong for populated streams; unasserted key.                                                                                                                                         |
| 23  | `DetectionStreamService.get_stream_info`       | `RuntimeError("Redis client not connected")` message text                                                                                                     | 1   | EQUIVALENT | `__mutmut_3`                                                           | Test uses bare `pytest.raises(RuntimeError)` without `match` (test_redis_streams.py:719).                                                                                                                                                            |
| 24  | `DetectionStreamService.move_to_dlq`           | raw-data passthrough `str(v)` → `str(None)` for every copied field                                                                                            | 1   | TEST-GAP   | `__mutmut_7`                                                           | DLQ loses the original payload (all fields become `"None"`); test asserts only the 3 metadata fields, not the copied `camera_id`/`file_path`.                                                                                                        |
| 25  | `DetectionStreamService.move_to_dlq`           | `dlq_timestamp` field key rename / value `str(None)`                                                                                                          | 3   | TEST-GAP   | `__mutmut_12`, `__mutmut_14`                                           | `dlq_timestamp` never asserted anywhere.                                                                                                                                                                                                             |
| 26  | `DetectionStreamService.move_to_dlq`           | DLQ `xadd` kwargs `maxlen`/`approximate` → None/dropped                                                                                                       | 4   | TEST-GAP   | `__mutmut_22`, `__mutmut_23`, `__mutmut_27`                            | DLQ grows unbounded; `test_move_to_dlq_success` asserts fields dict only (test_redis_streams.py:526–531).                                                                                                                                            |
| 27  | `DetectionStreamService.move_to_dlq`           | `acknowledge(message.id)` → `acknowledge(None)`                                                                                                               | 1   | TEST-GAP   | `__mutmut_28`                                                          | Original message never leaves the PEL (phantom redelivery). Tests assert only `xack.assert_called_once()` / `await_count == 1` — args unobserved.                                                                                                    |
| 28  | `DetectionStreamService.move_to_dlq`           | `record_pipeline_error("stream_dlq_move")` label → None / `XX…XX` / case                                                                                      | 3   | TEST-GAP   | `__mutmut_44`, `__mutmut_45`, `__mutmut_46`                            | Wrong metric label poisons the DLQ-move counter; no test patches `record_pipeline_error` in this module (only `pipeline_workers`/`clip_client` do).                                                                                                  |
| 29  | `DetectionStreamService.move_to_dlq`           | log text + `extra` keys                                                                                                                                       | 14  | EQUIVALENT | `__mutmut_29`, `__mutmut_33`, `__mutmut_36`                            | Pure logging.                                                                                                                                                                                                                                        |
| 30  | `DetectionStreamService.move_to_dlq`           | `RuntimeError` message text                                                                                                                                   | 1   | EQUIVALENT | `__mutmut_3`                                                           | Same as #23.                                                                                                                                                                                                                                         |

**Totals: TEST-GAP 129 · EQUIVALENT 55 · LOW-VALUE 0 · sum 184.**

## Drafted tests (top 6 TEST-GAP clusters by mutant count)

All UNVERIFIED — drafted from source + existing test style only; nothing was executed (live mutation run owns the machine). TDD procedure for each: run the new test against the mutated module → assertion fails on the mutant's diff line; run against the original `backend/services/redis_streams.py` → passes.

### D1 — get_stream_info exact contract (kills clusters 17, 18, 20, 21, 22 = 48 mutants)

Target file: `backend/tests/unit/services/test_redis_streams.py` → class `TestDetectionStreamServiceGetStreamInfo`

```python
    # UNVERIFIED - not yet run red/green
    @pytest.mark.asyncio
    async def test_get_stream_info_exact_contract(self, stream_service, mock_redis_client):
        """Full output contract: every key mapped from the right info field."""
        mock_redis_client._client.xinfo_stream = AsyncMock(
            return_value={
                "length": 1000,
                "radix-tree-keys": 100,
                "radix-tree-nodes": 200,
                "groups": 1,
                "last-generated-id": "1234567890123-99",
                "first-entry": ("1234567890000-0", {"data": "value"}),
            }
        )

        info = await stream_service.get_stream_info()

        assert info == {
            "length": 1000,
            "radix_tree_keys": 100,
            "radix_tree_nodes": 200,
            "groups": 1,
            "last_entry_id": "1234567890123-99",
            "first_entry_id": "1234567890000-0",
        }
        mock_redis_client._client.xinfo_stream.assert_awaited_once_with(DETECTION_STREAM_KEY)

    # UNVERIFIED - not yet run red/green
    @pytest.mark.asyncio
    async def test_get_stream_info_sparse_and_missing_defaults(
        self, stream_service, mock_redis_client
    ):
        """Missing info keys and missing-key fallback must both yield 0/'' defaults."""
        mock_redis_client._client.xinfo_stream = AsyncMock(return_value={"length": 3})

        info = await stream_service.get_stream_info()

        assert info == {
            "length": 3,
            "radix_tree_keys": 0,
            "radix_tree_nodes": 0,
            "groups": 0,
            "last_entry_id": "",
            "first_entry_id": "",
        }

        mock_redis_client._client.xinfo_stream = AsyncMock(side_effect=Exception("ERR no such key"))

        info = await stream_service.get_stream_info()

        assert info == {
            "length": 0,
            "radix_tree_keys": 0,
            "radix_tree_nodes": 0,
            "groups": 0,
            "last_entry_id": "",
            "first_entry_id": "",
        }
```

### D2 — Analysis claim_stale_messages Redis-call contract (kills clusters 12, 13, 14 = 26 mutants)

Target file: `backend/tests/unit/services/test_redis_streams_integration.py` → class `TestAnalysisStreamService`
(add `from backend.services.redis_streams import DEFAULT_CLAIM_MIN_IDLE_MS` to the existing import block)

```python
    # UNVERIFIED - not yet run red/green
    @pytest.mark.asyncio
    async def test_claim_stale_redis_call_contract(self, analysis_stream_service, mock_redis_client):
        """XAUTOCLAIM/XPENDING get exact stream/group/id arguments; claimed msg keeps its ID."""
        mock_redis_client._client.xautoclaim.return_value = (
            "0-0",
            [("5555-0", {"batch_id": "b", "camera_id": "c", "detection_ids": "[7]"})],
            [],
        )
        mock_redis_client._client.xpending_range.return_value = [("5555-0", "old-worker", 120000, 4)]

        messages = await analysis_stream_service.claim_stale_messages("worker-2", count=5)

        assert len(messages) == 1
        assert messages[0].id == "5555-0"
        assert messages[0].delivery_count == 4
        xautoclaim = mock_redis_client._client.xautoclaim
        assert xautoclaim.await_args[0] == (
            "analysis:stream",
            "analysis-workers",
            "worker-2",
            DEFAULT_CLAIM_MIN_IDLE_MS,
        )
        assert xautoclaim.await_args[1] == {"start_id": "0-0", "count": 5}
        mock_redis_client._client.xpending_range.assert_awaited_once_with(
            "analysis:stream",
            "analysis-workers",
            min="5555-0",
            max="5555-0",
            count=1,
        )
```

### D3 — Analysis consume_batches XREADGROUP contract (kills clusters 10, 11 = 18 mutants)

Target file: `backend/tests/unit/services/test_redis_streams_integration.py` → class `TestAnalysisStreamService`
(add `DEFAULT_BLOCK_MS` to the import block)

```python
    # UNVERIFIED - not yet run red/green
    @pytest.mark.asyncio
    async def test_consume_batches_readgroup_contract(
        self, analysis_stream_service, mock_redis_client
    ):
        """XREADGROUP uses the '>' cursor with exact group/consumer/count/block; msg keeps id+count."""
        mock_redis_client._client.xreadgroup.return_value = [
            (
                "analysis:stream",
                [
                    (
                        "9999-0",
                        {"batch_id": "b", "camera_id": "c", "detection_ids": "[1]"},
                    )
                ],
            )
        ]

        messages = await analysis_stream_service.consume_batches("worker-1", count=7)

        assert len(messages) == 1
        assert messages[0].id == "9999-0"
        assert messages[0].delivery_count == 1
        call = mock_redis_client._client.xreadgroup.call_args
        assert call[0] == ("analysis-workers", "worker-1", {"analysis:stream": ">"})
        assert call[1]["count"] == 7
        assert call[1]["block"] == DEFAULT_BLOCK_MS

        await analysis_stream_service.consume_batches("worker-1", block=False)
        assert mock_redis_client._client.xreadgroup.call_args[1]["block"] is None
```

### D4 — move_to_dlq full contract (kills clusters 24, 25, 26, 27, 28 = 12 mutants)

Target file: `backend/tests/unit/services/test_redis_streams.py` → class `TestDetectionStreamServiceMoveToDlq`

```python
    # UNVERIFIED - not yet run red/green
    @pytest.mark.asyncio
    async def test_move_to_dlq_preserves_payload_and_acks_original(
        self, stream_service, mock_redis_client
    ):
        """DLQ entry carries real raw values + parseable dlq_timestamp, trims, acks the real id, emits metric."""
        mock_redis_client._client.xadd = AsyncMock(return_value="dlq-123-0")
        mock_redis_client._client.xack = AsyncMock(return_value=1)

        message = DetectionStreamMessage(
            id="1234567890123-0",
            camera_id="front_door",
            detection_id=42,
            file_path="/path/to/image.jpg",
            delivery_count=3,
            raw_data={
                "camera_id": "front_door",
                "detection_id": "42",
                "file_path": "/path/to/image.jpg",
            },
        )

        with patch(
            "backend.services.redis_streams.record_pipeline_error", autospec=True
        ) as mock_metric:
            await stream_service.move_to_dlq(message, reason="processing_failed")

        call = mock_redis_client._client.xadd.call_args
        fields = call[0][1]
        # original payload survives the str-coercion passthrough
        assert fields["camera_id"] == "front_door"
        assert fields["detection_id"] == "42"
        assert fields["file_path"] == "/path/to/image.jpg"
        # DLQ metadata
        assert fields["original_message_id"] == "1234567890123-0"
        assert float(fields["dlq_timestamp"]) > 0
        # trimming kwargs
        assert call[1]["maxlen"] == DEFAULT_STREAM_MAXLEN
        assert call[1]["approximate"] is True
        # the ORIGINAL id is acked, not None
        mock_redis_client._client.xack.assert_called_once_with(
            DETECTION_STREAM_KEY, DETECTION_CONSUMER_GROUP, "1234567890123-0"
        )
        mock_metric.assert_called_once_with("stream_dlq_move")
```

### D5 — Analysis consumer-group creation contract (kills clusters 2, 5 = 11 mutants)

Target file: `backend/tests/unit/services/test_redis_streams_integration.py` → class `TestAnalysisStreamService`

```python
    # UNVERIFIED - not yet run red/green
    @pytest.mark.asyncio
    async def test_group_created_with_explicit_arguments_once(
        self, analysis_stream_service, mock_redis_client
    ):
        """XGROUP CREATE uses id='0' + mkstream=True on the right stream/group, exactly once."""
        await analysis_stream_service._ensure_consumer_group()
        await analysis_stream_service._ensure_consumer_group()

        mock_redis_client._client.xgroup_create.assert_awaited_once_with(
            "analysis:stream", "analysis-workers", id="0", mkstream=True
        )
```

### D6 — Factory actually builds the service (kills cluster 1 = 5 mutants)

Target file: `backend/tests/unit/services/test_redis_streams.py` → class `TestGetDetectionStreamService`

```python
    # UNVERIFIED - not yet run red/green
    @pytest.mark.asyncio
    async def test_creates_service_from_settings(self, mock_redis_client):
        """Factory must construct (not alias None) and wire redis_client + settings.queue_max_size."""
        import backend.services.redis_streams as module

        module._detection_stream_service = None

        with patch("backend.services.redis_streams.get_settings", autospec=True) as mock_settings:
            # deliberately distinct from DEFAULT_STREAM_MAXLEN so a dropped maxlen= arg is visible
            mock_settings.return_value.queue_max_size = 7777

            service = await get_detection_stream_service(mock_redis_client)

        assert isinstance(service, DetectionStreamService)
        assert service._redis is mock_redis_client
        assert service._maxlen == 7777

        module._detection_stream_service = None
```

(TDD note: `assert isinstance(...)` is what the existing `service1 is service2` misses — `None is None` made `is not None` / `= None` mutants survive.)

## Remaining TEST-GAP clusters not drafted (small; fold into existing tests)

- **add_batch xadd contract (clusters 7+8, 8 mutants)** — extend `test_add_batch_calls_xadd_with_json_detection_ids` (test_redis_streams_integration.py:190) with:
  `assert mock_redis_client._client.xadd.call_args[0][0] == "analysis:stream"`, `call_args[1]["maxlen"] == 10000`, `call_args[1]["approximate"] is True`, `float(fields["timestamp"]) > 0`, and `"pipeline_start_time" not in fields` when omitted.
- **Analysis acknowledge zero-case (cluster 6, 1 mutant)** — mirror `test_acknowledge_not_found`: set `xack` return 0, assert result is False (kills `> 0` → `>= 0`).

## Equivalence notes (for the baseline record)

- Logging families (clusters 3, 9, 16, 29) and exception-message-text tweaks (23, 30): no test captures log records, and `pytest.raises` uses no `match` at those sites.
- `_group_created = None` (4): flag is only read in `if self._group_created:` truthiness guards.
- `entry[:3]` (15): XAUTOCLAIM entries are 2-tuples from redis-py's parser; slicing past the end is a no-op.
- Dead first-entry defaults (19): `info.get("first-entry", DEFAULT)[0] if info.get("first-entry") else ""` — the guard and the value read the same key, so the default arg is unreachable in every reachable state.
