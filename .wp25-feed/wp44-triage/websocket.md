# WP4.4 Triage Dossier — backend/api/routes/websocket.py

**Wave**: mutation-testing survivors triage (WP4.3 feed → WP4.4). **UNVERIFIED** — no tests were run (live mutation run owns the machine; read-only analysis).

## Verdict source

- `mutants/backend/api/routes/websocket.py.meta`: 304 mutants, **200 killed, 104 SURVIVED, 0 unchecked**.
- Diffs obtained via `uv run mutmut show <key>` (authoritative dump: `/tmp/wp25/ws-triage/diffs.txt`, all 104 keys) **and** independently re-derived by diffing each `x_<fn>__mutmut_N` variant in `mutants/backend/api/routes/websocket.py` against its `__mutmut_orig` sibling — **0 mismatches** between the two methods. Cluster assignments below are validated against that dump.
- All survivors live in 5 functions: `x_handle_validated_message` (49), `x_handle_resync_with_replay` (27), `x_send_heartbeat` (20), `x_validate_websocket_message` (7), `x__check_message_size` (1).

## Covering test files (mutmut-stats `tests_by_mangled_function_name`)

| Function | Test files (file :: tests hitting it) |
| --- | --- |
| `x__check_message_size` | `backend/tests/unit/routes/test_websocket_routes.py` (12), `backend/tests/unit/api/routes/test_websocket_error_handling.py` (7), `backend/tests/unit/routes/test_websocket_job_logs.py` (3), `backend/tests/unit/core/test_websocket_timeout.py` (3) — **all indirect via endpoints; zero direct unit tests of the helper** |
| `x_validate_websocket_message` | `backend/tests/unit/api/routes/test_websocket.py` (18), `backend/tests/unit/core/test_websocket_validation.py` (11), `backend/tests/unit/routes/test_websocket_routes.py` (7), `backend/tests/unit/api/routes/test_websocket_error_handling.py` (6), others (2) |
| `x_handle_validated_message` | `backend/tests/unit/api/routes/test_websocket.py` (19), `backend/tests/unit/core/test_websocket_validation.py` (9), error_handling (1), timeout (1) |
| `x_handle_resync_with_replay` | `backend/tests/unit/api/routes/test_websocket_resync.py` (5), test_websocket.py (2) |
| `x_send_heartbeat` | `backend/tests/unit/api/routes/test_websocket.py` (6), `backend/tests/unit/core/test_websocket_timeout.py` (4) |

Key existing tests referenced below by file:line:
- test_websocket.py: `TestValidateWebSocketMessage` :66 (empty-string :109, preview :168), `TestHandleValidatedMessage` :187 (subscribe-error :267, unsubscribe-all :345, resync-defaults :427), `TestSendHeartbeat` :481 (periodic pings :485 asserts `'{"type": "ping", "lastSeq": 0}'` :506), `TestSubscriptionEdgeCases` :717 (subscribe null-data :741).
- test_websocket_resync.py: `TestResyncHandler` :17 (gap_too_old :149 uses oldest=50 vs last_sequence=10; missing-last_sequence :185).

## Cluster table (counts sum to 104)

| # | Pattern (function : line) | Keys (≤3 shown) | N | Class | Why |
| --- | --- | --- | --- | --- | --- |
| C1 | `_check_message_size` :87 — size guard boundary `>` → `>=` | `...x__check_message_size__mutmut_2` | 1 | **TEST-GAP** | No test targets the helper at all; a message of *exactly* max_size is rejected by the mutant. Endpoint tests pin `websocket_max_message_size=65536` (test_websocket_timeout.py:543) but never send a boundary-size message. |
| C2 | `validate_websocket_message` :126 — legacy tuple member `"value_error.jsondecode"` string-mutated (XX/UPPER) | `..._12`, `..._13` | 2 | EQUIVALENT | Vestigial pydantic-v1 JSON-decode error type; `model_validate_json` in pydantic 2 raises `json_invalid` for parse errors — no reachable input selects this tuple member, so mutant and original are indistinguishable without forging a ValidationError. |
| C3 | `validate_websocket_message` :131/:140 — error `message=` prose string mutated (XX/lowercase) | `..._22`, `..._38`, `..._39` | 3 | LOW-VALUE | Real wire-string change, but tests deliberately assert *substrings* (`"valid JSON" in message` :106, `"schema" in message` :152) which the variants preserve. Exact-string assertions would be brittle; nobody should assert these. |
| C4 | `validate_websocket_message` :135 — preview guard `if raw_data` → `if (raw_data) or True` | `..._28` | 1 | **TEST-GAP** | Only observable for empty `raw_data`: `details.raw_data_preview` becomes `""` instead of `None`. `test_empty_string_returns_none_and_sends_error` (test_websocket.py:109) runs that exact input but never asserts `details`. |
| C5 | `validate_websocket_message` :144 — `logger.warning(f"...{e}")` → `logger.warning(None)` | `..._30` | 1 | EQUIVALENT | Log payload only. |
| C6 | `handle_validated_message` :193/:216 etc. — `logger.debug/info/warning` message strings + `extra=` dicts mutated (None / XX / lower / UPPER / dropped) across PING, SUBSCRIBE, UNSUBSCRIBE, PONG, unknown-type branches | `..._12`, `..._64`, `..._130` | 23 | EQUIVALENT | Pure observability; values flow only into log records, never into wire responses or downstream calls. 5 log sites × ~4 variants. |
| C7a | `handle_validated_message` :184 — subscribe `VALIDATION_ERROR` payload `details={"example": {...}}` mutated (None / dropped / XX / UPPER at every nested key and value) | `..._38`, `..._41`, `..._55` | 14 | **TEST-GAP** | `details` is client-facing wire content (frontend renders the usage example), executed by `test_subscribe_without_events_sends_error` (:267) which asserts only `type`/`error`/message-substring — never `details`. |
| C7b | `handle_validated_message` :182 — same error's `message=` prose mutated | `..._42`, `..._43` | 2 | LOW-VALUE | Same substring-assertion reasoning as C3 (`"events" in response["message"]` at :286 survives). |
| C8 | `handle_validated_message` :175/:178 — SUBSCRIBE `.get("events"/"channels", [])` default → `None`/omitted | `..._20`, `..._22`, `..._29` | 4 | EQUIVALENT | Default is only read when the key is absent, and both `[]` and `None` hit identical falsy branches (`if not events and message.data`, `if not events:`) — no observable difference. |
| C9 | `handle_validated_message` :202/:205 — UNSUBSCRIBE `.get(...)` default → `None`/omitted | `..._83`, `..._85`, `..._92` | 4 | EQUIVALENT | Same falsy-branch argument via `if events:` → unsubscribe-all in both. |
| C10 | `handle_validated_message` :202 — UNSUBSCRIBE guard `if message.data` → `if (message.data) or True` | `..._81` | 1 | **TEST-GAP** | Real crash path: with `data=None` the mutant calls `None.get(...)` → AttributeError out of `handle_validated_message` → connection torn down instead of the graceful unsubscribe-all ack. Covered on the SUBSCRIBE side (`test_subscribe_null_data_sends_error` :741 — which is why the twin mutation there died) but **no test sends `unsubscribe` with `data=None`**. |
| C11 | `handle_validated_message` :232 — RESYNC dispatch passes `connection_id=None` to `handle_resync_with_replay` | `..._126` | 1 | EQUIVALENT | Inside the handler `connection_id` is used *only* in `extra=` log fields (:281, :305, :327) — buffer/tracker calls don't take it. Wire output identical. |
| C12 | `handle_resync_with_replay` :275 — `channel` fallback `"unknown"` mutated: `.get("channel", None)` / default omitted / `"XXunknownXX"` / `"UNKNOWN"` | `..._5`, `..._7`, `..._10` | 4 | **TEST-GAP** | `ack["channel"]` is wire contract. Existing coverage only exercises the *other* fallback arm: `test_resync_message_with_missing_data_uses_defaults` (test_websocket.py:427) sends `data=None` and the resync-file tests always include `"channel": "events"` — the data-present-but-channel-key-missing input is never asserted. |
| C13 | `handle_resync_with_replay` :279-284/:324-332 — `logger.info` message + `extra=` dict mutations (both call sites, every key) | `..._26`, `..._71`, `..._82` | 22 | EQUIVALENT | Log payload only; nothing downstream consumes the extra dict. |
| C14 | `handle_resync_with_replay` :292 — freshness operator `last_sequence < oldest_seq` → `<=` | `..._40` | 1 | **TEST-GAP** | Boundary: when the client's `last_sequence` **equals** the buffer's oldest seq, the original says the gap is fine (buffer `get_since` returns `seq > last`, and the client demonstrably *has* the oldest message); the mutant falsely reports `gap_too_old=True` + `oldest_available`, telling the client to do a full re-fetch. `test_resync_with_gap_too_old` (:149) only tries last=10 vs oldest=50 (strict `<`, both agree). |
| C15 | `send_heartbeat` :397/:410/:413 — `break` → `return` at the 3 loop-exit sites | `..._4`, `..._34`, `..._36` | 3 | EQUIVALENT | Nothing follows the `while` loop — end-of-loop `break` and `return` both terminate the coroutine identically. Unkillable by design. |
| C16 | `send_heartbeat` :401 — `get_current_sequence(connection_id)` → `get_current_sequence(None)` | `..._7` | 1 | **TEST-GAP** | NEM-3142 gap-detection contract: mutant reads the tracker under key `None` → heartbeat `lastSeq` is permanently 0 for every client. `test_sends_periodic_pings` (:485) asserts `lastSeq: 0` with an *unregistered empty* connection_id — the exact value both variants produce; no test registers a nonzero sequence. |
| C17 | `send_heartbeat` :392/:403-407/:409/:412 — debug log messages + `extra={"connection_id","lastSeq"}` mutations | `..._18`, `..._27`, `..._35` | 16 | EQUIVALENT | Log payload only. The wire payload literal `{"type": "ping", "lastSeq": last_seq}` is separately covered (`:506` string equality killed those). |

**Totals**: TEST-GAP 23 keys (7 clusters: C1, C4, C7a, C10, C12, C14, C16) · EQUIVALENT 76 keys (8 clusters: C2, C5, C6, C8, C9, C11, C13, C15, C17) · LOW-VALUE 5 keys (2 clusters: C3, C7b). 23+76+5 = 104 ✓

## Drafted tests (6 highest-value TEST-GAP clusters)

`// UNVERIFIED - not yet run red/green`. TDD procedure for each: apply the drafted test, confirm it FAILS on the mutant source (per-key diff above shows which assertion breaks), confirm it PASSES on `backend/api/routes/websocket.py` original, then commit test and re-run mutmut to fold the keys.

### T1 → C16 (`send_heartbeat__7`) — target `backend/tests/unit/api/routes/test_websocket.py`, append to `TestSendHeartbeat`

Kills: `get_current_sequence(None)`. Existing :506 assertion runs against an unregistered connection where the bug is invisible.

```python
    @pytest.mark.asyncio
    async def test_heartbeat_reports_connection_lastseq(self, mock_websocket):
        """Heartbeat lastSeq must come from THIS connection's sequence (NEM-3142).

        Guards get_current_sequence(connection_id): passing a null/None key makes
        every client's lastSeq permanently 0, defeating client-side gap detection.
        """
        stop_event = asyncio.Event()
        tracker = MagicMock()
        tracker.get_current_sequence.return_value = 7

        with patch(
            "backend.api.routes.websocket.get_sequence_tracker",
            return_value=tracker,
            autospec=True,
        ):
            task = asyncio.create_task(
                send_heartbeat(mock_websocket, 0.1, stop_event, "conn-42")
            )
            await asyncio.sleep(0.25)  # allow ~2 heartbeats
            stop_event.set()
            await task

        # Sequence lookup must use the connection's id, not a null key
        assert tracker.get_current_sequence.call_args.args[0] == "conn-42"
        payload = json.loads(mock_websocket.send_text.call_args.args[0])
        assert payload == {"type": "ping", "lastSeq": 7}
```

Mutant breaks assertion 1 (`args[0] is None`). Original passes.

### T2 → C14 (`handle_resync_with_replay__40`) — target `backend/tests/unit/api/routes/test_websocket_resync.py`, append to `TestResyncHandler`

Kills: `<=` flip. `get_since` returns `seq > last_sequence`, so a client holding exactly the oldest buffered message is current, not too-old.

```python
    @pytest.mark.asyncio
    async def test_resync_last_sequence_equal_to_oldest_is_not_too_old(
        self, mock_websocket: MagicMock, mock_message_buffer: MagicMock
    ) -> None:
        """Boundary (NEM-4983): last_sequence == oldest buffered seq is NOT gap_too_old.

        The client demonstrably received the oldest retained message, and
        get_since() replays everything strictly newer — the ack must not tell
        this client their gap is unrecoverable.
        """
        from backend.api.routes.websocket import handle_resync_with_replay
        from backend.api.schemas.websocket import WebSocketMessage

        mock_message_buffer.get_oldest_sequence.return_value = 50
        mock_message_buffer.get_since.return_value = [
            (51, {"type": "event", "seq": 51, "replay": True}),
        ]

        message = WebSocketMessage(type="resync", data={"channel": "events", "last_sequence": 50})

        with patch(
            "backend.api.routes.websocket.get_message_buffer",
            return_value=mock_message_buffer,
            autospec=True,
        ):
            await handle_resync_with_replay(mock_websocket, message, "test-conn-1")

        sent = [json.loads(call.args[0]) for call in mock_websocket.send_text.call_args_list]
        ack = next(m for m in sent if m.get("type") == "resync_ack")
        assert not ack.get("gap_too_old")  # absent (False) in original; True in mutant
        assert "oldest_available" not in ack
        assert ack["replayed_count"] == 1
```

### T3 → C1 (`__check_message_size__2`) — target `backend/tests/unit/api/routes/test_websocket.py`, new class

Kills: `>` → `>=` boundary rejection. First direct test for the helper (all existing hits are endpoint-indirect).

```python
# =============================================================================
# Tests for _check_message_size (NEM-4986)
# =============================================================================


class TestCheckMessageSize:
    """Direct boundary tests for the WebSocket message-size guard."""

    def test_message_exactly_at_limit_is_accepted(self):
        """A message of exactly max_size bytes is within limits (guard is `>`)."""
        from backend.api.routes.websocket import _check_message_size

        with patch("backend.api.routes.websocket.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value.websocket_max_message_size = 100
            result = _check_message_size("x" * 100)

        assert result is None  # mutant (>=) returns "Message too large (100 bytes, max 100)"

    def test_message_over_limit_is_rejected(self):
        """One byte over the limit is rejected with size details."""
        from backend.api.routes.websocket import _check_message_size

        with patch("backend.api.routes.websocket.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value.websocket_max_message_size = 100
            result = _check_message_size("x" * 101)

        assert result is not None
        assert "101" in result and "100" in result
```

### T4 → C10 (`handle_validated_message__81`) — target `backend/tests/unit/api/routes/test_websocket.py`, append to `TestSubscriptionEdgeCases`

Kills: `(message.data) or True` on the UNSUBSCRIBE guard — mutant raises AttributeError on `data=None` instead of a graceful unsubscribe-all ack (the SUBSCRIBE twin already has `test_subscribe_null_data_sends_error`; this is its missing counterpart).

```python
    @pytest.mark.asyncio
    async def test_unsubscribe_with_null_data_unsubscribes_all(
        self, mock_websocket, mock_subscription_manager
    ):
        """unsubscribe with data=None must gracefully unsubscribe-all and ack.

        Guards the `if message.data` truthiness guard: dropping it makes
        message.data.get() raise AttributeError and tear down the connection.
        """
        message = WebSocketMessage(type="unsubscribe", data=None)

        with patch(
            "backend.api.routes.websocket.get_subscription_manager",
            return_value=mock_subscription_manager,
            autospec=True,
        ):
            await handle_validated_message(mock_websocket, message, "conn-123")

        mock_subscription_manager.unsubscribe.assert_called_once_with("conn-123")
        mock_websocket.send_text.assert_awaited_once()
        response = json.loads(mock_websocket.send_text.call_args[0][0])
        assert response["action"] == "unsubscribed"
```

### T5 → C12 (`handle_resync_with_replay__5, __7, __10, __11`) — target `backend/tests/unit/api/routes/test_websocket_resync.py`, append to `TestResyncHandler`

Kills all 4 channel-fallback mutants with one wire assertion on the *present-data-missing-key* arm (existing tests only cover `data=None`).

```python
    @pytest.mark.asyncio
    async def test_resync_ack_defaults_channel_when_key_missing(
        self, mock_websocket: MagicMock, mock_message_buffer: MagicMock
    ) -> None:
        """data present but no 'channel' key -> ack channel defaults to "unknown"."""
        from backend.api.routes.websocket import handle_resync_with_replay
        from backend.api.schemas.websocket import WebSocketMessage

        mock_message_buffer.get_since.return_value = []

        message = WebSocketMessage(type="resync", data={"last_sequence": 3})

        with patch(
            "backend.api.routes.websocket.get_message_buffer",
            return_value=mock_message_buffer,
            autospec=True,
        ):
            await handle_resync_with_replay(mock_websocket, message, "test-conn-1")

        sent = [json.loads(call.args[0]) for call in mock_websocket.send_text.call_args_list]
        ack = next(m for m in sent if m.get("type") == "resync_ack")
        assert ack["channel"] == "unknown"  # mutants yield None / XXunknownXX / UNKNOWN
        assert ack["last_sequence"] == 3
```

### T6 → C7a (`handle_validated_message__38, __41, __45, …14 keys`) — target `backend/tests/unit/api/routes/test_websocket.py`, append to `TestHandleValidatedMessage`

One structural-equality assertion kills every nested mutation of the wire-visible usage example.

```python
    @pytest.mark.asyncio
    async def test_subscribe_error_details_include_usage_example(
        self, mock_websocket, mock_subscription_manager
    ):
        """VALIDATION_ERROR payload carries the copy-pasteable example contract (NEM-2383)."""
        message = WebSocketMessage(type="subscribe", data={})

        with patch(
            "backend.api.routes.websocket.get_subscription_manager",
            return_value=mock_subscription_manager,
            autospec=True,
        ):
            await handle_validated_message(mock_websocket, message, "conn-123")

        response = json.loads(mock_websocket.send_text.call_args[0][0])
        assert response["details"] == {
            "example": {"type": "subscribe", "data": {"events": ["alert.*"]}}
        }
```

### Fold-in (C4, no separate test)

Extend existing `test_empty_string_returns_none_and_sends_error` (test_websocket.py:109) with:

```python
        assert error_response["details"]["raw_data_preview"] is None  # mutant yields ""
```

## Notes / caveats

- C2's EQUIVALENT call rests on pydantic 2's `model_validate_json` never emitting the legacy `value_error.jsondecode` error type (parse failures report `json_invalid`). If a pydantic upgrade ever emits it, this becomes a latent TEST-GAP — cheap insurance is a direct-call test forging that ValidationError, but not worth it now.
- C15 (break→return) and C6/C13/C17 (log payload, 61 keys total) are the bulk of the 76 EQUIVALENT — this module's mutation-survivor volume is dominated by unkillable logging variants; consider a mutmut exclusion for `logger.*` argument variants in WP4.5 tuning.
- Drafted tests target `x_*` survivors only; endpoint-level twins (`websocket_events_endpoint` etc., a different meta/triage unit) are out of scope for this dossier.
