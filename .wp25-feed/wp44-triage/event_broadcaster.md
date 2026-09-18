# WP4.4 triage dossier — backend/services/event_broadcaster.py

Wave: serial triage lane (event_broadcaster), 2026-09-17. UNVERIFIED throughout —
no tests were run; a live `mutmut run` owns the machine.

- Survivors at extraction: **104** (meta snapshot 2026-09-17 14:08: 1288 keys —
  148 killed, 104 survived, 1036 unchecked). Counts/keys shift as the run
  advances; clusters are pattern-based and hold for later verdicts on the same
  shapes.
- Survivor functions/indices (exact, from eb_diffs.json):
  to_dict {9,10,17,19}; \_resubscribe_for_supervisor {2,4}; record_ack {6,7};
  broadcast_alert {17,18,19,25,26,27,28,29,31}; broadcast_summary_update
  {2,3,4,5,12,13,14,15,23,24,25,26,33,34,35,41..57}; broadcast_zone_dwell_started
  /\_dwell_alert /\_zone_approach /broadcast_entity_track_updated
  /broadcast_ai_action_recognized {10,11,12,14,18..24 each}.
- Source: `backend/services/event_broadcaster.py` (2445 lines)
- Full machine-readable diffs: `/tmp/wp25/wp44-triage/eb_diffs.json`
  (key → unified diff of the mutant function vs its `__mutmut_orig`).

## Extraction method (tooling caveat — `mutmut show` is broken under the live run)

`uv run mutmut show <key>` raises `FileNotFoundError: Could not find original
function "to_dict"` — the live run resets every `mutants/**.py` copy to a plain
source copy during generation/check phases, so the trampoline copies
(`x...__mutmut_N`) are absent from the file `show` parses; its spans fallback
then fails because the on-disk copy (2445 lines) is not the 79,067-line mutated
file the `.spans` index describes.

Workaround (read-only, no cache touched):

1. Waited for the window where the live run rewrites
   `mutants/backend/services/event_broadcaster.py` back to its mutated form (it
   does this right before checking that module's mutants) and captured it:
   79,067 lines, consistent with `event_broadcaster.py.spans` (07:43, max span
   line 79063) and the 1288-key meta — same generation pass.
2. Extracted each survivor's diff per-function from the captured copy using the
   spans index (same algorithm as `mutmut/mutation/diff_apply.py`).
3. **Cross-validation:** re-generated all mutants independently in-process with
   `mutmut.mutation.file_mutation.mutate_file_contents` over the pristine source
   (1452 candidates, no coverage filter; the live set is the coverage-filtered
   1288). Every one of the 1288 live-mutant diffs matched a diff in the
   independent set (0 misses), so the captured file is the file the meta was
   checked against, and every key→diff mapping below is verified against two
   independent generations. (Coverage-filter renumbering explains index gaps:
   e.g. live `broadcast_alert__mutmut_17` sits at 29 in the unfiltered order —
   do NOT assume unfiltered indices.)

## Cluster table (104 = 91 EQUIVALENT + 13 TEST-GAP + 0 LOW-VALUE)

| #    | Pattern (kind × function/concern)                                                                                                                                                                                                                                                                                         | Count | Class                                                      | Kill   | Example keys (≤3)                                                                                                                        |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----: | ---------------------------------------------------------- | ------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| C1   | log-text mutants (`None` whole f-string; `payload.get('k')` → `None`/`'XXkXX'`/`'K'`) in the 5 new-event fns (dwell_started/dwell_alert/zone_approach/entity_track_updated/ai_action_recognized), indices 18–24                                                                                                           |    35 | EQUIVALENT                                                 | —      | `...ǁbroadcast_zone_dwell_started__mutmut_18`, `..._20`, `...ǁbroadcast_ai_action_recognized__mutmut_23`                                 |
| C2   | `model_dump(mode="json")` → `None`/`"JSON"`/`"XXjsonXX"`: 5 new-event fns `_10-12` (15) + alert `_17-19` (3) + summary hourly `_12-14`, daily `_23-25`, envelope `_33-35` (9)                                                                                                                                             |    27 | EQUIVALENT                                                 | —      | `...ǁbroadcast_alert__mutmut_17`, `...ǁbroadcast_summary_update__mutmut_33`, `...ǁbroadcast_entity_track_updated__mutmut_10`             |
| C6   | alert/summary Redis-publish debug-log text: `broadcast_data.get('type')` key mutants, whole message → `None`, and the yes/no ternary text (incl. `and False`/`or True` arms) — all inside the log f-string                                                                                                                |    20 | EQUIVALENT                                                 | —      | `...ǁbroadcast_alert__mutmut_25`, `...ǁbroadcast_summary_update__mutmut_42`, `..._45`                                                    |
| C4   | `logger.error(f"...")` → `logger.error(None)` in except-hands of alert/summary (message text only; re-raise untouched)                                                                                                                                                                                                    |     5 | EQUIVALENT                                                 | —      | `...ǁbroadcast_alert__mutmut_29`, `..._31`, `...ǁbroadcast_summary_update__mutmut_15`                                                    |
| C3   | `broadcast_summary_update` init `data_dict = {"hourly": None, "daily": None}` key strings mutated — dead write, overwritten/validated before use                                                                                                                                                                          |     4 | EQUIVALENT                                                 | —      | `...ǁbroadcast_summary_update__mutmut_2`, `..._3`, `..._4`                                                                               |
| C5   | `to_dict` success_rate arithmetic: guard `(successful + failed) > 0` → `-` (`_17`) / `> 1` (`_19`) — changes when the rate is computed vs `0.0` fallback                                                                                                                                                                  |     2 | **TEST-GAP**                                               | D1, D2 | `...ǁBroadcastRetryMetricsǁto_dict__mutmut_17`, `..._19`                                                                                 |
| C7   | `to_dict` `"retry_counts"` key → `"XXretry_countsXX"`/`"RETRY_COUNTS"` — drops `retry_counts` from the `get_broadcast_metrics()` monitoring payload                                                                                                                                                                       |     2 | **TEST-GAP** (contract drop; no in-repo reader of the key) | D3     | `...ǁBroadcastRetryMetricsǁto_dict__mutmut_9`, `..._10`                                                                                  |
| C8   | new-event fns `publish(self._channel_name, ...)` → `publish(None, ...)` (index `_14` × 5 fns) — wrong Redis channel                                                                                                                                                                                                       |     5 | **TEST-GAP**                                               | D6     | `...ǁbroadcast_zone_dwell_started__mutmut_14`, `...ǁbroadcast_zone_approach__mutmut_14`, `...ǁbroadcast_ai_action_recognized__mutmut_14` |
| C9   | `_resubscribe_for_supervisor`: `subscribe(self._channel_name)` → `subscribe(None)` (`_2`) and failure-arm `return False` → `True` (`_4`) — success path never exercised; return value only consumed by `_handle_dead_listener` and never asserted (covering test asserts the error log text, which both mutants preserve) |     2 | **TEST-GAP**                                               | D7     | `...ǁ_resubscribe_for_supervisor__mutmut_2`, `..._4`                                                                                     |
| C10a | `record_ack` default `_client_acks.get(websocket, 0)` → `1` — a fresh client's ack of sequence **1** silently no-ops (first buffered message dropped)                                                                                                                                                                     |     1 | **TEST-GAP**                                               | D4     | `...ǁrecord_ack__mutmut_6`                                                                                                               |
| C10b | `record_ack` `if sequence > current` → `>=` — re-records equal acks, violating the documented monotonic "only updates if higher" contract (observable when current is the implicit 0)                                                                                                                                     |     1 | **TEST-GAP**                                               | D5     | `...ǁrecord_ack__mutmut_7`                                                                                                               |

**Coverage sanity:** the 4 surviving-index functions with no unit tests at all
(`broadcast_detection_batch/_new`, `broadcast_worker_status`,
`broadcast_infrastructure_alert` — `tests_by_mangled_function_name = ∅`) have
**no checked keys yet** in the 14:08 meta snapshot, so they contribute zero
survivors to this snapshot; when the run reaches them, expect this module's
signature pattern: mode mutants (equiv) + publish-channel mutants (**the same
`_14` shape as C8 — D6-style channel asserts in whatever tests get written**) +
log text (equiv).

### EQUIVALENT receipts (do-not-delete-without-record)

- **C2 — every `mode` variant is a no-op for these schemas.** Verified
  empirically on the repo's pydantic 2.13.5: `model_dump(mode=None)`,
  `mode="JSON"`, `mode="XXjsonXX"` all behave as _non-json_ mode (only the exact
  string `"json"` selects json mode; pydantic warns but does not raise). Every
  schema broadcast here holds only JSON-stable fields or `str`-valued enums:
  `WebSocketAlertData`/`WebSocketAlertDeletedData` (created_at/updated_at are
  **`str`**, not `datetime`; severity/status are `StrEnum`),
  `WebSocketSummaryData` (window_start/end/generated_at are `str`), the zone/
  entity/AI `BasePayload` schemas (`timestamp: str`, plain int/float/dict
  fields, `use_enum_values`). Direct check:
  `json.dumps(m.model_dump(mode=X))` is \*\*byte-identical for X ∈ {"json", None,
  "JSON", "XXjsonXX"}`(asserted True on`WebSocketAlertCreatedMessage`); the
remaining schemas are str/int/float-only where both modes are the identity
map. The payload tests observe on `redis.publish`is unchanged. Real-world
divergence would need a`datetime`/UUID field or a non-str enum in a broadcast
  schema — none exists today (that would be a schema-change tripwire worth a
  comment, not a test).
- **C1/C4/C6 — log text.** Mutants only change the f-string argument to
  `logger.debug`/`logger.error`; control flow, return values and re-raises are
  identical. `logger.error(None)` still logs (msg-only arg) and the adjacent
  `raise ... from ve` / `raise` is untouched.
- **C3 — dead write.** `data_dict`'s mutated keys are overwritten on the next
  lines when the arg is non-None, and when None the values are irrelevant to
  `WebSocketSummaryUpdateData.model_validate` (fields come from the
  `data_dict["hourly"]`/`["daily"]` assignments). No path publishes the literal
  initialization.

### TEST-GAP notes

- **C5** — `backend/services/event_broadcaster.py:135` (`to_dict`). Covering:
  `backend/tests/unit/services/test_broadcast_retry.py:72` (`test_to_dict`:
  2 succ / 1 fail → ~0.666) and `:89` (`test_success_rate_zero_broadcasts`:
  0/0 → 0.0). `_17` would compute `2/(2-1)=2.0` in `test_to_dict` and `_19`
  breaks only at the total==1 boundary — and **both survived**, which means
  neither test actually ran under this module's mutant checking (per-function
  dependency selection picked no runner that imports them; same story the 1036
  still-unchecked keys tell). Re-verify must confirm the tests execute; if
  selection still skips `test_broadcast_retry.py`, that is a mutmut-dependency
  finding in itself. The existing `abs(rate-0.666)<0.01` assertion also never
  pins the formula (a `/(2*s)` mutant passes it). D1/D2 assert exact values at
  the s=1/f=1 and total==1 boundaries.
- **C7** — same `to_dict`; covering also
  `test_broadcast_retry.py::TestEventBroadcasterMetricsIntegration::test_get_broadcast_metrics`
  (asserts only `successful_broadcasts`, `failed_broadcasts`, `"success_rate" in`).
  D3 pins the full key set + `retry_counts` value.
- **C8** — `backend/tests/unit/services/test_event_broadcaster_new_events.py`:
  only `test_broadcast_zone_crossing_event` asserts the channel (`assert channel
== broadcaster.CHANNEL_NAME` at :85); the dwell_started/dwell_alert/approach/
  entity/ai tests (`:87`, `:110`, `:140`, `:202`, `:262`) never assert it — that
  is precisely why 5× `_14` survived. D6 adds the channel assert for all five.
  Note `broadcaster._channel_name` and `CHANNEL_NAME` both derive from
  `get_settings().redis_event_channel` (event_broadcaster.py:375-389), so the
  crossing test passes with `publish(None,...)`? No — it passes only because it
  covers `zone.crossing`, whose `_14` variant was killed by that assert; the
  five surviving functions simply lack it.
- **C9** — `backend/tests/unit/services/test_event_broadcaster.py:2205`
  (`test_handle_dead_listener_resubscribe_failure`) drives `_resubscribe_for_supervisor`
  only through `_supervise_listener` with `subscribe` raising, and asserts
  `"Failed to re-subscribe" in caplog.text`. `_2` (`subscribe(None)`) raises
  identically under that FakeRedis; `_4` (`return True`) changes only the return
  value the supervisor ignores in that flow (it re-loops because `_is_listening`
  goes False via the fake sleep). A direct-call pair (D7) kills both.
- **C10** — `backend/services/event_broadcaster.py:560` (`record_ack`). Covering:
  `backend/tests/unit/services/test_message_buffer.py::TestEventBroadcasterAckTracking`
  (`:249`; `test_record_ack_stores_sequence` :277 acks 42 — default 0-vs-1
  unobservable; `test_record_ack_ignores_equal_sequence` :300 acks 20→20 —
  `>`-vs-`>=` unobservable, both end with `get_last_ack()==20`). The mutants
  flip exactly the two inputs the suite never exercises: sequence **1** on a
  fresh client, and an equal ack while current is the implicit **0**. D4/D5 add
  those cases.

## Drafted tests (UNVERIFIED — not yet run red/green)

TDD procedure for each: apply the cluster's mutant diff (or `mutmut`-apply the
key), run the new test — it must FAIL (red); restore the original, run — PASS
(green); then run the whole test file once to catch fixture drift.

### D1 — kills C5 (`to_dict__mutmut_17`): exact success-rate value

Append to class `TestBroadcastRetryMetrics` in
`backend/tests/unit/services/test_broadcast_retry.py` (after
`test_success_rate_zero_broadcasts`, ~:96). On the `-` mutant the guard is
`1-1 > 0` → False → `0.0` (assert fails red); original → `0.5` green.

```python
    def test_success_rate_exact_value(self) -> None:
        """success_rate must equal successful/(successful+failed) exactly."""
        metrics = BroadcastRetryMetrics()
        metrics.record_success(attempts=1)
        metrics.record_failure(attempts=3)

        result = metrics.to_dict()

        assert result["success_rate"] == 0.5
```

### D2 — kills C5 (`to_dict__mutmut_19`): boundary where total == 1

Same class/file. `> 1` mutant: `1 > 1` False → `0.0` red; original `1.0` green.

```python
    def test_success_rate_single_broadcast_is_one(self) -> None:
        """One broadcast, zero failures: rate is 1.0, not the 0.0 fallback."""
        metrics = BroadcastRetryMetrics()
        metrics.record_success(attempts=1)

        assert metrics.to_dict()["success_rate"] == 1.0
```

### D3 — kills C7 (`to_dict__mutmut_9/_10`): full metrics-dict contract

Same class/file. Mutants drop `"retry_counts"` → KeyError red; original green.

```python
    def test_to_dict_key_set_and_retry_counts(self) -> None:
        """to_dict is the monitoring payload: pin every key and its value."""
        metrics = BroadcastRetryMetrics()
        metrics.record_success(attempts=1)  # retry_counts[0] = 1
        metrics.record_failure(attempts=3)  # retries_exhausted += 1

        result = metrics.to_dict()

        assert set(result) == {
            "total_attempts",
            "successful_broadcasts",
            "failed_broadcasts",
            "retries_exhausted",
            "retry_counts",
            "success_rate",
        }
        assert result["retry_counts"] == {0: 1, 1: 0, 2: 0, 3: 0}
```

### D4 — kills C10a (`record_ack__mutmut_6`): ack of sequence 1 on a fresh client

Append to `TestEventBroadcasterAckTracking` in
`backend/tests/unit/services/test_message_buffer.py` (fixtures `broadcaster`/
`mock_websocket` already exist there; `MagicMock` already imported). Mutant
default 1: `1 > 1` False → nothing stored → `get_last_ack` returns 0 → red;
original stores → 1 → green.

```python
    def test_record_ack_accepts_first_sequence_one(
        self, broadcaster: EventBroadcaster, mock_websocket: MagicMock
    ) -> None:
        """A brand-new client acking sequence 1 must be recorded.

        record_ack falls back to 0 for unknown clients, so sequence 1 (the
        first buffered message) is strictly higher and must win — a 1-default
        silently drops it.
        """
        broadcaster.record_ack(mock_websocket, 1)

        assert broadcaster.get_last_ack(mock_websocket) == 1
```

### D5 — kills C10b (`record_ack__mutmut_7`): equal ack at the default is a true no-op

Same class/file. Original `>`: `0 > 0` False → no write → key absent → green;
mutant `>=`: writes `_client_acks[ws] = 0` → key present → `in` True → red.

```python
    def test_record_ack_equal_sequence_does_not_touch_state(
        self, broadcaster: EventBroadcaster, mock_websocket: MagicMock
    ) -> None:
        """Equal-sequence acks must not rewrite the ack map.

        With no prior ack the client's current value is the implicit 0; the
        monotonic "only updates if higher" contract forbids a write at
        sequence == 0 (mutant >= re-records it).
        """
        broadcaster.record_ack(mock_websocket, 0)

        assert mock_websocket not in broadcaster._client_acks
        assert broadcaster.get_last_ack(mock_websocket) == 0
```

### D6 — kills C8 (`_14` channel → None × 5): channel assert for all five new-event fns

Append to `backend/tests/unit/services/test_event_broadcaster_new_events.py`
(reuses the file's `_FakeRedis`; payloads are the existing tests' valid ones —
extras are ignored by the schemas). Mutant publishes on None → assert red;
original green.

```python
# ==============================================================================
# Redis-channel contract for the NEM-5073 events (WP4.4 kill-draft)
# ==============================================================================

NEW_EVENT_CHANNEL_CASES = [
    (
        "broadcast_zone_dwell_started",
        {
            "zone_id": "zone-456",
            "entity_id": "entity-789",
            "camera_id": "loading_dock",
            "timestamp": "2026-02-01T12:00:00Z",
        },
    ),
    (
        "broadcast_zone_dwell_alert",
        {
            "zone_id": "zone-789",
            "entity_id": "entity-123",
            "camera_id": "restricted_cam",
            "timestamp": "2026-02-01T12:05:00Z",
            "dwell_duration_seconds": 300,
            "threshold_seconds": 180,
        },
    ),
    (
        "broadcast_zone_approach",
        {
            "zone_id": "zone-999",
            "entity_id": "entity-555",
            "camera_id": "entry_cam",
            "timestamp": "2026-02-01T12:00:00Z",
            "direction": "north",
            "speed": 2.5,
            "eta_seconds": 15,
        },
    ),
    (
        "broadcast_entity_track_updated",
        {
            "entity_id": "entity-789",
            "camera_id": "back_yard",
            "timestamp": "2026-02-01T12:00:00Z",
            "position": {"x": 100.0, "y": 200.0},
            "bbox": {"x": 90.0, "y": 190.0, "width": 50.0, "height": 100.0},
        },
    ),
    (
        "broadcast_ai_action_recognized",
        {
            "detection_id": "det-456",
            "camera_id": "garage",
            "timestamp": "2026-02-01T12:00:00Z",
            "action_type": "climbing",
            "confidence": 0.88,
        },
    ),
]


class TestNewEventPublishChannel:
    """Every new-event broadcast must publish on the configured Redis channel.

    The per-event tests assert the envelope but (except zone.crossing) not the
    channel — a mutant publishing to None survives them.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method_name,payload", NEW_EVENT_CHANNEL_CASES)
    async def test_publishes_to_configured_channel(
        self, method_name: str, payload: dict[str, Any]
    ) -> None:
        redis = _FakeRedis()
        broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

        await getattr(broadcaster, method_name)(payload)

        channel = redis.publish.await_args.args[0]
        assert channel == broadcaster.CHANNEL_NAME
```

(No new imports needed: the file already imports `Any`, `pytest`,
`EventBroadcaster`; `_FakeRedis` and the autouse `_reset_broadcaster_state`
fixture are in-file.)

### D7 — kills C9 (`_resubscribe_for_supervisor__mutmut_2/_4`): direct-call pair

Append to `backend/tests/unit/services/test_event_broadcaster.py` (module-level
async tests, `_FakeRedis` in-file, `AsyncMock` already imported there).
`_2`: `subscribe(None)` breaks the awaited-with-channel assert → red. `_4`:
failure arm returns True → red.

```python
@pytest.mark.asyncio
async def test_resubscribe_for_supervisor_success_uses_channel() -> None:
    """Success path: subscribes the configured channel and reports success."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    assert await broadcaster._resubscribe_for_supervisor() is True

    redis.subscribe.assert_awaited_once_with(broadcaster._channel_name)


@pytest.mark.asyncio
async def test_resubscribe_for_supervisor_failure_returns_false() -> None:
    """Failure path must return False so the supervisor keeps retrying.

    A mutant returning True here would let the supervisor treat a dead
    subscription as recovered and recreate the listener on a missing pubsub.
    """
    redis = _FakeRedis()
    redis.subscribe = AsyncMock(side_effect=RuntimeError("Subscription failed"))
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    assert await broadcaster._resubscribe_for_supervisor() is False
```

## Covering test files (file:line anchors)

| Function                                       | Covering test file                                                 | Anchor                                                                                                             |
| ---------------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------ |
| `BroadcastRetryMetrics.to_dict`                | `backend/tests/unit/services/test_broadcast_retry.py`              | `test_to_dict` :72, `test_success_rate_zero_broadcasts` :89, integration `test_get_broadcast_metrics` ~:360        |
| `EventBroadcaster.record_ack`                  | `backend/tests/unit/services/test_message_buffer.py`               | `TestEventBroadcasterAckTracking` :249 (`test_record_ack_stores_sequence` :277, `..._ignores_equal_sequence` :300) |
| `EventBroadcaster._resubscribe_for_supervisor` | `backend/tests/unit/services/test_event_broadcaster.py`            | `test_handle_dead_listener_resubscribe_failure` :2205 (log-text only; success path + return value unasserted)      |
| `broadcast_alert`                              | `backend/tests/unit/services/test_event_broadcaster_alert.py`      | `TestBroadcastAlert` :79+ (18 tests)                                                                               |
| `broadcast_summary_update`                     | `backend/tests/unit/services/test_event_broadcaster_summary.py`    | `TestBroadcastSummaryUpdate` (11 tests) + `TestBroadcastSummaryUpdateMessageFormat`                                |
| 5 new-event fns                                | `backend/tests/unit/services/test_event_broadcaster_new_events.py` | crossing :60 (channel assert :85), dwell_started :87, dwell_alert :110, approach :140, entity :202, ai :262        |
