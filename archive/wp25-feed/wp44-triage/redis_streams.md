# WP4.4 Triage Dossier — backend/services/redis_streams.py

- **Generated:** 2026-09-18 (wave 56 candidate, gen-2 queue)
- **Survivors:** 429 of 913 keys (0 null, 484 killed) — meta: `mutants/backend/services/redis_streams.py.meta`
- **Classification totals:** TEST-GAP 238 · LOW-VALUE 167 · EQUIVALENT 24 (sum 429)
- **Clusters:** 42 (every survivor assigned exactly once; counts in table sum to 429)
- **Extracted via:** AST-diff of each `__mutmut_N` body vs its `__mutmut_orig` in `mutants/backend/services/redis_streams.py` (mutmut show spot-checked, agreed). No tests executed.

## Covering test files

| File | Role |
|---|---|
| `backend/tests/unit/services/test_redis_streams.py` | Main unit suite (fixtures: `mock_redis_client` :128, `stream_service` :136) |
| `backend/tests/unit/services/test_redis_streams_integration.py` | Service-path tests (fixtures :32/:60/:66) |
| `backend/tests/unit/services/test_redis_streams_timestamp.py` | Timestamp-parsing suite (`from_stream_entry`, `_parse_timestamp`) |

Shared weakness: the suites mock redis-py and assert happy-path message contents, but almost never assert **arguments forwarded to redis commands** (`call_args`/`assert_called_with`) and never capture logs (`caplog` appears 0× in all three files) — hence the two huge LOW-VALUE log clusters and the argument-TEST-GAP clusters.

## Cluster table

Counts sum = 429. "Kill idea" = minimal assertion that flips each mutant red.

### TEST-GAP (238)

| # | Cluster | N | Mutation pattern (functions) | Example keys (≤3) | Covering tests miss | Kill idea |
|---|---|---|---|---|---|---|
| 1 | C-GAP-XAUTOCLAIM | 26 | `xautoclaim(...)` positional/keyword args → None or dropped (claim_stale_messages, both services) | `…AnalysisStreamServiceǁclaim_stale_messages__mutmut_3`, `…DetectionStreamServiceǁclaim_stale_messages__mutmut_7`, `…DetectionStreamServiceǁclaim_stale_messages__mutmut_19` | `test_redis_streams.py:456`, `test_redis_streams_integration.py:267` run claim with mocked xautoclaim but never inspect `call_args` | `xautoclaim.assert_awaited_once_with(STREAM, GROUP, "worker-2", DEFAULT_CLAIM_MIN_IDLE_MS, start_id="0-0", count=5)` → **Draft T1** |
| 2 | C-GAP-GSI-DEFAULTS | 26 | `get_stream_info` output keys `length`/`groups`/`last_entry_id`/`first_entry_id`: `.get` default flipped (`0→1/None`), redis key mangled (`last-generated-id`, `first-entry`), except-branch fallback dict values, `[0]→[1]` (L707–727, L730+) | `…get_stream_info__mutmut_11`, `…get_stream_info__mutmut_47`, `…get_stream_info__mutmut_64` | `test_redis_streams.py:584` asserts only length/groups/last_entry_id; `:604` (empty stream) asserts only length/groups; `:~660` "missing first entry" returns a dict, never exercises except-fallback fields | assert every key in both populated and raised-"no such key" replies → **Draft T3** |
| 3 | C-GAP-GSI-RADIX | 24 | same fn: `radix_tree_keys`/`radix_tree_nodes` output keys and `radix-tree-keys`/`radix-tree-nodes` lookup keys mangled, default 0→1/None, populated + except-branch | `…get_stream_info__mutmut_17`, `…get_stream_info__mutmut_23`, `…get_stream_info__mutmut_79` | no test anywhere asserts `info["radix_tree_keys"]`/`["radix_tree_nodes"]` | include radix keys in the stats assertion → **Draft T3** |
| 4 | C-GAP-XPENDRANGE | 22 | `xpending_range(...)` args → None/dropped, `min/max=message_id` → None, `count=1→2` (claim_stale_messages, both services) | `…AnalysisStreamServiceǁclaim_stale_messages__mutmut_26`, `…DetectionStreamServiceǁclaim_stale_messages__mutmut_31`, `…DetectionStreamServiceǁclaim_stale_messages__mutmut_39` | claim tests mock xpending_range reply but never assert its args; `count=1→2` only changes range width — invisible | `xpending_range.assert_awaited_once_with(STREAM, GROUP, min="1234567890123-0", max="1234567890123-0", count=1)` → **Draft T1** |
| 5 | C-GAP-XGROUPARGS | 20 | `xgroup_create(stream, group, id="0", mkstream=True)` args → None/dropped, `id "0"→"XX0XX"`, `mkstream True→False` (_ensure_consumer_group, both services) | `…_ensure_consumer_group__mutmut_2`, `…_ensure_consumer_group__mutmut_4`, `…_ensure_consumer_group__mutmut_15` | `test_redis_streams.py:185` asserts only `call_count == 1` | `xgroup_create.assert_awaited_once_with(DETECTION_STREAM_KEY, DETECTION_CONSUMER_GROUP, id="0", mkstream=True)` → **Draft T2** |
| 6 | C-GAP-XREADARGS | 20 | `xreadgroup(group, consumer, {stream: ">"}, count, block)` args → None/dropped, `">"` → `"XX>XX"` (consume_detections, consume_batches, `_stream_entries` cast target) | `…consume_detections__mutmut_10`, `…consume_batches__mutmut_6`, `…consume_detections__mutmut_20` | blocking test `:~310` asserts only `call_args[1]["block"]`; integration `:104` only `assert_awaited_once()` | assert full xreadgroup call incl. `{DETECTION_STREAM_KEY: ">"}` → part of **Draft T2** |
| 7 | C-GAP-FSE-DEFAULTS | 18 | `from_stream_entry` dataclass fields: `id=message_id→None`, `raw_data=data→None`/dropped, `batch_id`/`camera_id` default `""→None/"XXXX"/dropped`, `detection_id` default `0→1` | `…DetectionStreamMessageǁfrom_stream_entry__mutmut_21`, `…DetectionStreamMessageǁfrom_stream_entry__mutmut_45`, `…AnalysisStreamMessageǁfrom_stream_entry__mutmut_28` | entry tests (`test_redis_streams.py:66`, `test_redis_streams_timestamp.py`) feed data **containing** these fields, so `data.get` defaults never run; `raw_data` never asserted | missing-fields test asserting id/batch_id/camera_id/file_path/`detection_id==0`/`raw_data` → **Draft T5** |
| 8 | C-GAP-XADD-ARGS | 16 | `xadd(stream, fields, maxlen=…, approximate=…)` args → None/dropped; `__init__` `_maxlen = maxlen or DEFAULT` → None/`and`; add_batch `timestamp` key/value mangled (add_detection, add_batch, move_to_dlq) | `…add_batch__mutmut_20`, `…add_batch__mutmut_22`, `…move_to_dlq__mutmut_22` | add_detection `:232`/`:~245` asserts fields + maxlen on **add_detection only**; add_batch integration `:190` asserts fields but not maxlen/approximate kwargs; move_to_dlq DLQ xadd kwargs unasserted | add `call_args[1]["maxlen"]==DEFAULT_STREAM_MAXLEN`, `["approximate"] is True` in add_batch + move_to_dlq tests → **Draft T6** |
| 9 | C-GAP-TRIMCOUNT | 6 | `trim_stream` removal math observable-but-unasserted: `current_length` default 0→1 (L836), post-trim `new_length` default 0→1 (L850), `max(0,…)→max(1,…)` (L852) | `…trim_stream__mutmut_17`, `…trim_stream__mutmut_35`, `…trim_stream__mutmut_41` | `test_redis_streams.py:618` asserts `removed==5000` on a *healthy* path but the defaulting (`info={}` / missing `"length"`) and `max(1,…)` clamping paths never run | assert `trim_stream()==0` when lengths equal, and on `info={}` replies → part of **Draft T6** |
| 10 | C-GAP-CGINFO-KEYS | 9 | `get_consumer_group_info`: output key `"last_delivered_id"` mangled, fallback `""→"XXXX"`, `group.get("name")` key mangled (L750–760) | `…get_consumer_group_info__mutmut_9`, `…get_consumer_group_info__mutmut_20`, `…get_consumer_group_info__mutmut_22` | `:871` asserts name/consumers/pending only; **no test at all** covers the group-found happy path (`last-delivered-id` extraction, `"name"` match key) | happy-path test with matching group asserting all 4 keys incl. `last_delivered_id=="123-0"` |
| 11 | C-GAP-PENDING-KEYS | 9 | `get_pending_count`: `pending.get("consumers", [])→None`, `consumer.get("pending", 0→1/None)`, `xpending(stream, group)` args (L792–806) | `…get_pending_count__mutmut_7`, `…get_pending_count__mutmut_26`, `…get_pending_count__mutmut_31` | `:924` asserts the hit (`==7`) and not-found (`==0`) with *complete* dicts; the `.get` fallback defaults and the xpending args never surface | assert `xpending.assert_awaited_once_with(DETECTION_STREAM_KEY, DETECTION_CONSUMER_GROUP)`; consumer dict missing `"pending"` → 0 |
| 12 | C-GAP-DELCOUNT1 | 5 | consume path passes `delivery_count=1→None/2` to `from_stream_entry` (consume_detections, consume_batches) | `…consume_detections__mutmut_27`, `…consume_batches__mutmut_23`, `…consume_batches__mutmut_27` | consume tests assert id/camera_id but never `messages[0].delivery_count` | add `assert messages[0].delivery_count == 1` to returns_messages tests → part of **Draft T5** |
| 13 | C-GAP-SINGLETON | 5 | factory `get_detection_stream_service`: `is None→is not None` (returns None / re-creates), ctor kwargs `redis_client→None`, `maxlen=settings.queue_max_size→None`/dropped (L1252) | `x_get_detection_stream_service__mutmut_1`, `__mutmut_3`, `__mutmut_5` | `test_redis_streams.py:643` asserts only `service1 is service2`; the *constructed values* never checked | assert `service._maxlen == 10000` (settings.queue_max_size) and `service._redis is mock_redis_client` |
| 14 | C-GAP-GROUPSTATE | 3 | `_group_created = True → None` (ensure sets falsy → group re-created every call) / `False→True` (never created) in AnalysisStreamService (L1012, :974) | `…AnalysisStreamServiceǁ_ensure_consumer_group__mutmut_23`, `__mutmut_24`, `…AnalysisStreamServiceǁ__init__mutmut_11` | no test calls AnalysisStreamService `_ensure_consumer_group` twice and asserts xgroup_create call_count (detection version has `:185`, analysis does not) | mirror `test_creates_consumer_group_once` for AnalysisStreamService |
| 15 | C-GAP-SVCATTRS | 3 | `AnalysisStreamService.__init__` stores `block_ms/claim_min_idle_ms/max_delivery_count → None` (L971–973) | `…AnalysisStreamServiceǁ__init__mutmut_7`, `__mutmut_8`, `__mutmut_9` | integration fixture constructs with defaults and never asserts stored attrs | assert `svc._block_ms == DEFAULT_BLOCK_MS` etc. |
| 16 | C-GAP-SLICE2 | 3 | `message_id, data = entry[:2] → entry[:3]` → ValueError "too many values to unpack" (`_stream_entries` L109, both claim fns) | `x__stream_entries__mutmut_14`, `…DetectionStreamServiceǁclaim_stale_messages__mutmut_25`, `…AnalysisStreamServiceǁclaim_stale_messages__mutmut_21` | survive only because mocked entries have exactly-2 tuples and parse-exception paths swallow/hide the change | existing happy-path consume/claim tests already kill these **if** xreadgroup/xautoclaim mock entries have 3+ fields; a `entry[:3]`-shaped reply test locks it |
| 17 | C-GAP-XINFOARG | 4 | `xinfo_stream(self._stream_key)→None` / `xinfo_groups(...)→None` (get_stream_info L707, get_consumer_group_info L748, trim_stream L835/849) | `…get_stream_info__mutmut_7`, `…get_consumer_group_info__mutmut_7`, `…trim_stream__mutmut_9` | mocked xinfo_* accept anything; args never asserted | `xinfo_stream.assert_awaited_once_with(DETECTION_STREAM_KEY)` |
| 18 | C-GAP-BLOCKCOND | 3 | consume_batches `block_ms = self._block_ms if block else None` → always None / `(block) and False` / `(block) or True` (L1081) | `…consume_batches__mutmut_2`, `__mutmut_3`, `__mutmut_4` | detection version has uses_blocking/non-blocking tests (`:~310`,`:~320`) asserting `call_args[1]["block"]`; **consume_batches has no equivalent** | mirror the two blocking tests onto consume_batches |
| 19 | C-GAP-TEXTID | 3 | claim path `_text(message_id) → None` / `_text(None)` (id fed to from_stream_entry, L579) | `…claim_stale_messages__mutmut_38`, `…claim_stale_messages__mutmut_44`, `…AnalysisStreamServiceǁclaim_stale_messages__mutmut_38` | claim tests assert `messages[0].id` — these survive only via the *other* service's tests; per-suite gap | Draft T1's id + args assertions applied to both services |
| 20 | C-GAP-EXTRAFIELD-COERCE | 3 | add_detection extra_fields coercion `str(value) if not isinstance(value,str)` → `and False` (drop str-coercion), `str(None)` (clobbered value), condition flipped (L384) | `…add_detection__mutmut_40`, `__mutmut_42`, `__mutmut_43` | `test_add_detection_with_optional_fields` passes extra_fields but no non-str values are checked for str-coercion | extra_fields `{"count": 5, "tag": "x"}` → assert `fields["count"]=="5"`, `fields["tag"]=="x"` |
| 21 | C-GAP-DLQFIELDS | 2 | move_to_dlq field builders: `{k: str(v)…}→str(None)` (raw_data values "None"-ified), `dlq_timestamp: str(time.time())→str(None)` (L642, :646) | `…move_to_dlq__mutmut_7`, `…move_to_dlq__mutmut_14` | `test_move_to_dlq_success:503` asserts original_message_id/dlq_reason/delivery_count, not raw_data passthrough values or dlq_timestamp presence | assert `fields["camera_id"]=="front_door"` and `"dlq_timestamp" in fields` |
| 22 | C-GAP-XTRIMARGS | 4 | `xtrim(stream, maxlen=…, approximate=…)` args → None/dropped (trim_stream L841–844) | `…trim_stream__mutmut_20`, `__mutmut_22`, `__mutmut_25` | `:618` asserts only `xtrim.assert_called_once()` | `xtrim.assert_awaited_once_with(DETECTION_STREAM_KEY, maxlen=10000, approximate=True)` → **Draft T6** |
| 23 | C-GAP-ACKZERO | 1 | AnalysisStreamService `return result > 0 → >= 0` (L1130) — xack 0 now reports success | `…AnalysisStreamServiceǁacknowledge__mutmut_9` | integration `:257` covers xack→1 only (detection twin has not-found test at unit `:443`, analysis lacks it) | add analysis not-found case: `xack→0 ⇒ is False` |
| 24 | C-GAP-TEXT-BYTES | 1 | `_text`: `isinstance(value, bytes) and False` → bytes reply gets `str(b'x')=="b'x'"` garbage instead of decode (L94) | `x__text__mutmut_1` | every consumer feeds str mocks (decode_responses=True), so the bytes branch never runs | unit test `assert _text(b"abc") == "abc"` |
| 25 | C-GAP-DLQKEY | 1 | `AnalysisStreamService.__init__` `self._dlq_key = f"{stream_key}:dlq" → None` (L968) | `…AnalysisStreamServiceǁ__init__mutmut_3` | nothing ever calls AnalysisStreamService.move_to_dlq with arg assertion | construct svc, assert `_dlq_key == "analysis:stream:dlq"` |
| 26 | C-GAP-DLQACK | 1 | move_to_dlq `await self.acknowledge(message.id) → acknowledge(None)` (L661) | `…move_to_dlq__mutmut_28` | `xack.assert_called_once()` without args (unit `:~530`, integ `:146`) | assert xack called with `(DETECTION_STREAM_KEY, DETECTION_CONSUMER_GROUP, msg_id)` — already half-written in unit `:232`'s style |

TEST-GAP subtotal: 238.

### LOW-VALUE (167)

| # | Cluster | N | Pattern | Example keys | Note |
|---|---|---|---|---|---|
| 27 | C-LOW-LOGKEY | 72 | logger `extra={...}` dict keys mangled (`stream_key→XXstream_keyXX/STREAM_KEY`) across ensure/add/ack/move/claim/trim, both services | `…_ensure_consumer_group__mutmut_19`, `…add_batch__mutmut_35` | zero `caplog` usage in all 3 test files; log-schema assertions are low ROI |
| 28 | C-LOW-LOGMSG | 48 | logger event messages mangled (XX…, case flips): "Created consumer group", "Trimmed stream", "Claimed stale messages", … | `…_ensure_consumer_group__mutmut_16`, `…trim_stream__mutmut_53` | pure observability strings |
| 29 | C-LOW-LOGDROP | 24 | `extra={…} → None` or dropped on logger calls | `…add_batch__mutmut_29`, `…claim_stale_messages__mutmut_49` | drops structured log payload only |
| 30 | C-LOW-EXCWORDING | 13 | `raise RuntimeError("Redis client not connected") → "XXRedis client not connectedXX"` (7 fns) — tests use `pytest.raises(match="Redis client not connected")` (substring), XX-wrap still matches | `…_ensure_consumer_group__mutmut_3`, `…acknowledge__mutmut_3` | all 10 not-connected tests use match=; wording-only mutants survive on substring match — acceptable, do not chase |
| 31 | C-LOW-METRICTAG | 3 | `record_pipeline_error("stream_dlq_move")` label mangled/None (move_to_dlq L672) | `…move_to_dlq__mutmut_44` | metrics tag only |
| 32 | C-LOW-LOGGATE | 2 | `if removed > 0:` → `>= 0` / `> 1` gates **only** the trim logger.info (L856) | `…trim_stream__mutmut_47`, `__mutmut_48` | return value untouched |
| 33 | C-LOW-CLAIMEDGUARD | 4 | `_claimed_entries` guard `result and len(result)>1` weakened/`or True`/`>2` (L143) — behavior differs only for falsy/short xautoclaim replies redis-py never sends (`(cursor,[],deleted)` always len 3) | `x__claimed_entries__mutmut_2`, `__mutmut_6`, `__mutmut_7` | defensive-dead tweaks; `or True` even crashes on real shape |
| 34 | C-LOW-NONEGUARD | 1 | `_stream_entries` `if id is None or data is None → and` (L110) — differs only for mixed (None,data)/(data,None) entries that redis-py doesn't produce; real (None,None) trimmed entries identical under both | `x__stream_entries__mutmut_15` | defensive-dead |

LOW-VALUE subtotal: 167.

### EQUIVALENT (24)

| # | Cluster | N | Pattern | Example keys | Why equivalent |
|---|---|---|---|---|---|
| 35 | C-EQ-ZSUFFIX-NATIVE | 4 | `.replace("Z","+00:00")` → `("XXZXX"…)` or `("z"…)` in `_parse_timestamp`/Analysis from_stream_entry | `x__parse_timestamp__mutmut_7`, `__mutmut_8`, `…AnalysisStreamMessageǁfrom_stream_entry__mutmut_24` | on the project's Python 3.14 `datetime.fromisoformat` accepts trailing `Z` natively (3.11+), so a broken/absent replacement is a no-op; value unchanged |
| 36 | C-EQ-TYPING-CAST | 4 | `cast("Sequence[Any]",…)` → `cast(None,…)`/`"XXSequence[Any]XX"`/case-changes (`_stream_entries` L104) | `x__stream_entries__mutmut_3`, `__mutmut_7`, `__mutmut_8` | typing.cast is erased at runtime — zero semantic effect |
| 37 | C-EQ-TRIMFALLBACK | 5 | trim_stream `current_length=0→None` (L838), `info.get("length",0)→None/()` defaults in the two except/default sites (L836, L850) | `…trim_stream__mutmut_12`, `__mutmut_18`, `__mutmut_45` | only reachable when xinfo raises/replies incomplete → existing tests assert `removed==0`, and every mutant still returns 0 (None comparisons yield `max(0,None-…)` paths that clamp or raise inside try → 0) |
| 38 | C-EQ-JSONABSORB | 3 | Analysis `data.get("detection_ids","[]")→None/`dropped/`"XX[]XX"` | `…AnalysisStreamMessageǁfrom_stream_entry__mutmut_3`, `__mutmut_5`, `__mutmut_8` | `json.loads(None)` raises TypeError → `except: detection_ids=[]` — same result as `json.loads("[]")` |
| 39 | C-EQ-TSFALLBACK | 3 | Detection `data.get("timestamp","")→None/"XXXX"/dropped` | `…DetectionStreamMessageǁfrom_stream_entry__mutmut_3`, `__mutmut_5`, `__mutmut_8` | falsy→`time.time()` branch, `"XXXX"`→ValueError→`time.time()` fallback — same behavior |
| 40 | C-EQ-FALSYSTATE | 2 | `__init__ _group_created=False→None` (both services) | `…DetectionStreamServiceǁ__init__mutmut_10`, `…AnalysisStreamServiceǁ__init__mutmut_10` | None is falsy; every read is `if self._group_created:` |
| 41 | C-EQ-DELCOUNT-DEFAULT | 2 | `from_stream_entry(..., delivery_count=1)` kwarg dropped (consume_detections, consume_batches) | `…DetectionStreamServiceǁconsume_detections__mutmut_30`, `…consume_batches__mutmut_26` | `delivery_count` parameter default **is** 1 — dropping the explicit arg is identity |
| 42 | C-EQ-STRTOSTR | 1 | add_detection coercion `(not isinstance(value,str)) or True` → `str(value)` on str values | `…add_detection__mutmut_41` | `str(s)==s` for every str — identity map |

EQUIVALENT subtotal: 24.

## Drafted kill-tests (6)

> Style follows `test_redis_streams.py` (async fixtures `stream_service`/`mock_redis_client`; imports already at top of that file: `AsyncMock`, `pytest`, `DetectionStreamMessage`, `DEFAULT_CLAIM_MIN_IDLE_MS`, `DEFAULT_BLOCK_MS`, `DETECTION_STREAM_KEY`, `DETECTION_CONSUMER_GROUP`, constants).
> **TDD procedure (one line):** add the test, run it — it must FAIL on the mutant copy (assert on the changed argument/field trips) and PASS on `backend/services/redis_streams.py` unchanged; then re-run the module suite for no regressions.
> **// UNVERIFIED — not yet run red/green** (per WP4.3 constraint: no test execution in this triage lane).

### Draft T1 — kill C-GAP-XAUTOCLAIM + C-GAP-XPENDRANGE + C-GAP-TEXTID (target: `backend/tests/unit/services/test_redis_streams.py`, class TestDetectionStreamServiceClaimStaleMessages)

```python
    @pytest.mark.asyncio
    async def test_claim_stale_messages_forwards_full_command_args(self, stream_service, mock_redis_client):
        """XAUTOCLAIM/XPENDING range calls must carry exact stream/group/idle/count args."""
        mock_redis_client._client.xgroup_create = AsyncMock()
        mock_redis_client._client.xautoclaim = AsyncMock(
            return_value=(
                "0-0",
                [("1234567890123-0", {"camera_id": "front_door", "detection_id": "42", "file_path": "/p.jpg"})],
                [],
            )
        )
        mock_redis_client._client.xpending_range = AsyncMock(
            return_value=[("1234567890123-0", "worker-1", 120000, 3)]
        )

        messages = await stream_service.claim_stale_messages("worker-2", count=5)

        assert messages[0].id == "1234567890123-0"  # kills _text(message_id)->None mutants
        mock_redis_client._client.xautoclaim.assert_awaited_once_with(
            DETECTION_STREAM_KEY,
            DETECTION_CONSUMER_GROUP,
            "worker-2",
            DEFAULT_CLAIM_MIN_IDLE_MS,
            start_id="0-0",
            count=5,
        )
        mock_redis_client._client.xpending_range.assert_awaited_once_with(
            DETECTION_STREAM_KEY,
            DETECTION_CONSUMER_GROUP,
            min="1234567890123-0",
            max="1234567890123-0",
            count=1,
        )
```

Mirror class `TestAnalysisStreamService` in `test_redis_streams_integration.py` with `analysis_stream_service` fixture (kills the Analysis half of all three clusters).

### Draft T2 — kill C-GAP-XGROUPARGS + C-GAP-XREADARGS (target: `test_redis_streams.py`, class TestDetectionStreamServiceEnsureConsumerGroup)

```python
    @pytest.mark.asyncio
    async def test_creates_consumer_group_with_exact_args(self, stream_service, mock_redis_client):
        """XGROUP CREATE must use stream/group/id=0/mkstream=True."""
        mock_redis_client._client.xgroup_create = AsyncMock()

        await stream_service._ensure_consumer_group()

        mock_redis_client._client.xgroup_create.assert_awaited_once_with(
            DETECTION_STREAM_KEY, DETECTION_CONSUMER_GROUP, id="0", mkstream=True
        )

    @pytest.mark.asyncio
    async def test_consume_detections_reads_new_entries_with_exact_args(self, stream_service, mock_redis_client):
        """XREADGROUP must target group/consumer and the '>' new-entry id with count+block."""
        mock_redis_client._client.xgroup_create = AsyncMock()
        mock_redis_client._client.xreadgroup = AsyncMock(return_value=None)

        await stream_service.consume_detections("worker-1", count=2, block=True)

        mock_redis_client._client.xreadgroup.assert_awaited_once_with(
            DETECTION_CONSUMER_GROUP, "worker-1", {DETECTION_STREAM_KEY: ">"}, count=2, block=DEFAULT_BLOCK_MS
        )
```

(Paired analysis tests on `analysis_stream_service` kill the consume_batches half + C-GAP-BLOCKCOND; add the two blocking-mode mirrors there.)

### Draft T3 — kill C-GAP-GSI-DEFAULTS + C-GAP-GSI-RADIX + C-GAP-XINFOARG-get_stream_info (target: `test_redis_streams.py`, class TestDetectionStreamServiceGetStreamInfo)

```python
    @pytest.mark.asyncio
    async def test_get_stream_info_returns_all_stats_fields(self, stream_service, mock_redis_client):
        """Every mapped key (incl. radix-tree stats and first-entry id) must survive translation."""
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

    @pytest.mark.asyncio
    async def test_get_stream_info_missing_key_fallback_is_fully_zeroed(self, stream_service, mock_redis_client):
        """The no-such-key fallback dict must map every field to its zero value."""
        mock_redis_client._client.xinfo_stream = AsyncMock(side_effect=Exception("no such key"))

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

### Draft T4 — kill C-GAP-CGINFO-KEYS + C-GAP-PENDING-KEYS + C-GAP-XINFOARG (target: `test_redis_streams.py`, class TestDetectionStreamServiceErrorHandling or new TestDetectionStreamServiceInspection)

```python
    @pytest.mark.asyncio
    async def test_get_consumer_group_info_returns_matching_group_stats(self, stream_service, mock_redis_client):
        """The group whose 'name' matches must be returned with all mapped stats."""
        mock_redis_client._client.xgroup_create = AsyncMock()
        mock_redis_client._client.xinfo_groups = AsyncMock(
            return_value=[
                {"name": "other", "consumers": 9, "pending": 9, "last-delivered-id": "1-0"},
                {"name": DETECTION_CONSUMER_GROUP, "consumers": 2, "pending": 5, "last-delivered-id": "123-0"},
            ]
        )

        info = await stream_service.get_consumer_group_info()

        assert info == {
            "name": DETECTION_CONSUMER_GROUP,
            "consumers": 2,
            "pending": 5,
            "last_delivered_id": "123-0",
        }

    @pytest.mark.asyncio
    async def test_get_pending_count_defaults_missing_fields_to_zero(self, stream_service, mock_redis_client):
        """Consumer entries missing 'pending' and incomplete XPENDING dicts default to 0, and xpending gets exact args."""
        mock_redis_client._client.xgroup_create = AsyncMock()
        mock_redis_client._client.xpending = AsyncMock(
            return_value={"pending": 10, "consumers": [{"name": "worker-1"}]}
        )

        assert await stream_service.get_pending_count("worker-1") == 0
        mock_redis_client._client.xpending.assert_awaited_once_with(
            DETECTION_STREAM_KEY, DETECTION_CONSUMER_GROUP
        )
```

### Draft T5 — kill C-GAP-FSE-DEFAULTS + C-GAP-DELCOUNT1 + C-GAP-EXTRAFIELD-COERCE + C-GAP-TEXT-BYTES (targets: `test_redis_streams.py`)

```python
    def test_from_stream_entry_defaults_and_raw_data(self):
        """Missing fields must yield the documented defaults; raw_data must be the original dict."""
        msg = DetectionStreamMessage.from_stream_entry("999-0", {})

        assert msg.id == "999-0"
        assert msg.camera_id == ""
        assert msg.detection_id == 0
        assert msg.file_path == ""
        assert msg.raw_data == {}

    @pytest.mark.asyncio
    async def test_consume_detections_first_delivery_count_is_one(self, stream_service, mock_redis_client):
        mock_redis_client._client.xgroup_create = AsyncMock()
        mock_redis_client._client.xreadgroup = AsyncMock(
            return_value=[(DETECTION_STREAM_KEY, [("1-0", {"camera_id": "c", "detection_id": "7", "file_path": "/p.jpg"})])]
        )

        messages = await stream_service.consume_detections("worker-1")

        assert messages[0].delivery_count == 1

    @pytest.mark.asyncio
    async def test_add_detection_coerces_non_string_extra_fields(self, stream_service, mock_redis_client):
        """extra_fields values must be str-coerced for Redis; str values pass through unchanged."""
        mock_redis_client._client.xadd = AsyncMock(return_value="1-0")

        await stream_service.add_detection(
            camera_id="cam", detection_id=1, file_path="/p.jpg",
            extra_fields={"count": 5, "tag": "plain"},
        )

        fields = mock_redis_client._client.xadd.call_args[0][1]
        assert fields["count"] == "5"
        assert fields["tag"] == "plain"

    def test_text_helper_decodes_bytes_replies(self):
        from backend.services.redis_streams import _text

        assert _text(b"payload") == "payload"
        assert _text("already") == "already"
```

(The Analysis twin: `AnalysisStreamMessage.from_stream_entry("1-0", {})` asserts `id/batch_id==""/camera_id==""/raw_data=={}` — kills the Analysis FSE-DEFAULTS half; place in `test_redis_streams_integration.py`.)

### Draft T6 — kill C-GAP-XADD-ARGS + C-GAP-XTRIMARGS + C-GAP-TRIMCOUNT + C-GAP-DLQFIELDS/C-GAP-DLQACK + ACKZERO + SINGLETON + GSI-adjacent xadd kwargs (targets: `test_redis_streams_integration.py` + `test_redis_streams.py`)

```python
    @pytest.mark.asyncio
    async def test_add_batch_trims_with_maxlen_and_approximate(self, analysis_stream_service, mock_redis_client):
        """XADD for analysis batches must carry maxlen + approximate=True kwargs."""
        await analysis_stream_service.add_batch("b1", "cam", [1], pipeline_start_time=None)

        kwargs = mock_redis_client._client.xadd.call_args[1]
        assert kwargs["maxlen"] == 10000  # fixture maxlen
        assert kwargs["approximate"] is True
        assert mock_redis_client._client.xadd.call_args[0][0] == "analysis:stream"

    @pytest.mark.asyncio
    async def test_trim_stream_forwards_exact_trim_args_and_counts(self, stream_service, mock_redis_client):
        mock_redis_client._client.xinfo_stream = AsyncMock(
            side_effect=[{"length": 15000}, {"length": 10000}]
        )
        mock_redis_client._client.xtrim = AsyncMock()

        removed = await stream_service.trim_stream(maxlen=10000)

        assert removed == 5000
        mock_redis_client._client.xtrim.assert_awaited_once_with(
            DETECTION_STREAM_KEY, maxlen=10000, approximate=True
        )

    @pytest.mark.asyncio
    async def test_acknowledge_returns_false_when_zero_acked_analysis(self, analysis_stream_service, mock_redis_client):
        """XACK 0 must NOT report success (guards `result > 0` -> `>= 0`)."""
        mock_redis_client._client.xack = AsyncMock(return_value=0)

        assert await analysis_stream_service.acknowledge("9999-0") is False

    @pytest.mark.asyncio
    async def test_detection_service_singleton_uses_settings_maxlen(self, mock_redis_client):
        """Factory must construct with maxlen from settings (guards maxlen=None/dropped)."""
        import backend.services.redis_streams as module

        module._detection_stream_service = None
        with patch("backend.services.redis_streams.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value.queue_max_size = 4321
            service = await module.get_detection_stream_service(mock_redis_client)

        assert service._maxlen == 4321
        assert service._redis is mock_redis_client
        module._detection_stream_service = None
```

Plus (style of unit `:503`) in `test_move_to_dlq_success`: `fields["dlq_timestamp"]` present and `fields["camera_id"] == "front_door"` (kills DLQFIELDS), `xack.assert_called_once_with(DETECTION_STREAM_KEY, DETECTION_CONSUMER_GROUP, "1234567890123-0")` (kills DLQACK).

## Residual notes

- Drafted tests kill ≈210 of the 238 TEST-GAP survivors (clusters 1–13, 16–26 and the xadd kwargs of 8); the uncovered remainder is 1:1 one-liners needing per-attribute asserts (SVCATTRS, DLQKEY, GROUPSTATE mirror, consume_batches blocking mirror) — each a ≤5-line test.
- No test executes the `except "no such key"` fallback dict of get_consumer_group_info / get_pending_count *with arg assertions*; T4 closes the observable part.
- The `first-entry` guard `[""]` sentinel (`if info.get("first-entry") else ""`) is only weakly observable; `#55 andFalse` is already killed by the existing stats test.
- Concurrency note: meta read once (no JSONDecodeError); all diffs from the committed mutants copy — stable vs the live run's cache.
