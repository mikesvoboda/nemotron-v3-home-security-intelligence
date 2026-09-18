# WP4.4 Triage Dossier — backend/services/mqtt_client.py

- **Survivors:** 232 of 477 mutants (245 killed, 0 unchecked) — `mutants/backend/services/mqtt_client.py.meta`
- **Covering test file (all clusters):** `backend/tests/unit/services/test_mqtt_client.py` (939 lines; fixtures: `mqtt_settings` :67, `mock_aiomqtt_client` :84, `mock_prometheus_metrics` :97, `mqtt_client` :128)
- **Raw per-mutant diffs:** `/tmp/wp25/wp44-triage/mqtt_client_diffs.txt` (segment-diff of `mutants/backend/services/mqtt_client.py` vs `backend/services/mqtt_client.py`)
- **Original source anchors:** connect guards :385/:391, `aiomqtt.Client(...)` ctor :405-413, connect backoff sleep :450-465, exhausted-path error :468-471; publish topic_type :547, `max_publish_retries=3` :553, success metrics :565-569, retry guard :587, publish backoff :592; subscribe :610-640; unsubscribe :648-661; health_check :663-686; `_handle_message` :714/:735; `_find_callback` :751; pump loop :797/:802
- **Headline:** TEST-GAP 70 / LOW-VALUE 141 / EQUIVALENT 21 (sums to 232).

## Why so many log mutants survive (context for the 141 LOW-VALUE)

`mock_prometheus_metrics` patches `Counter/Gauge/Histogram` **classes** and the tests never inspect log records — so (a) 42 metric name/description-string mutants are inert (names never reach a real registry), and (b) 89 `logger.*(msg, extra={...})` mutations (message → None/XX-padded/UPPER/lower, `extra` dropped, dict-key renames/case flips) are never asserted anywhere. These are real changes with cosmetic effect only.

## Cluster table (every survivor key assigned exactly once)

fn = `backend.services.mqtt_client.` prefix; `MQTTClient` shown as `MC`.

### TEST-GAP — 70 keys, 13 clusters

| # | Pattern (mutation kind + concern) | n | Example keys (≤3) | Kill |
|---|-----------------------------------|---|-------------------|------|
| T1 | Prometheus **label/gauge values** never asserted — tests only call `labels.assert_called()`/`inc.assert_called()`, never with which kwargs; `gauge.set(N)` value unchecked; histogram `observe()` value unchecked | 22 | MC connect__33 (`status="success"`→None), MC publish__42 (`monotonic()-start`→`+`), MC disconnect__16 (`.set(0)`→`.set(1)`) | Draft A |
| T2 | publish `topic_type` first-segment derivation `topic.split("/", maxsplit=1)[0] if "/" in topic else topic` (:547) — label value never asserted | 9 | MC publish__25 (`[0]`→`[1]`), __22 (`split`→`rsplit`), __26 (`"/" in`→`"XX/XX" in`) | Draft B |
| T3 | `aiomqtt.Client(...)` ctor kwargs (:405-413) entirely unasserted — hostname/port/identifier/username/password/keepalive/tls_context → None or kwarg dropped; no test ever inspects the constructed call | 14 | MC connect__17 (`port=`→None), __24 (port kwarg dropped), __20 (`password=`→None) | Draft C1 |
| T4 | TLS branch never exercised on the connect path — `tls_context = _build_tls_context() if use_tls else None` (:399) forced to always-None / always-build / never-gated; `test_tls_configuration` only constructs Settings, never connects with `use_tls=True` | 3 | MC connect__11 (`tls_context=None`), __13 (`if True`), __12 (`if False`) | Draft C2 |
| T5 | `MQTTConnectionError.original_error` cause-chaining (:71, :471) unasserted — `original_error=last_exception` → None/dropped, `last_exception = e` → None; tests match only message text | 5 | MCConnectionError __init____2 (`self.original_error = None`), MC connect__105, MC connect__55 | Draft D |
| T6 | publish retry-count contract: `max_publish_retries = 3` (:553) → 4, and loop guard `if attempt < max_publish_retries - 1` (:587) boundary flips (`<=`, `+1`, `-2`) — existing retry test succeeds on attempt 3 so total-attempt count is never pinned | 4 | MC publish__31 (3→4), __78 (`<`→`<` minus 2), __76 (`<`→`<=`) | Draft E |
| T7 | publish retry **backoff schedule** `sleep(reconnect_interval * (2**attempt))` (:592) — publish-path sleep args never asserted (connect-path ones are, :292) | 3 | MC publish__83 (`*`→`/`), __84 (`2**attempt`→`2*attempt`), __85 (base 3) | Draft E |
| T8 | broker unsubscribe **topic argument** never asserted — `full_topic = f"{prefix}/{topic}"` → None and `unsubscribe(full_topic)` → `unsubscribe(None)` pass `assert_called_once()` (:654); same on disconnect fan-out (:496-497) | 4 | MC unsubscribe__4 (full_topic=None), MC disconnect__11 (full_topic=None) | Draft F |
| T9 | connect idempotency guard `if self._connected and self._client is not None` (:385/:391) mutated `is not None`→`is None` (both guards together) → second `connect()` **re-creates the client and re-enters `__aenter__`**; `test_connect_is_idempotent` asserts only `connected is True` — no Client call-count check (weak existing test) | 2 | MC connect__2, MC connect__8 | Draft G |
| T10 | disconnect guard `if self._client is not None and self._subscriptions` (:493) → `is None and` → broker-unsubscribe fan-out silently skipped when connected; `test_graceful_shutdown_with_active_subscriptions` asserts only `len(_subscriptions)==0`, never `unsubscribe` calls | 1 | MC disconnect__9 | Draft F |
| T11 | `publish_duration` Histogram built without `buckets=MQTT_PUBLISH_DURATION_BUCKETS` (:148) — histogram config never asserted (mocked class) | 1 | `_get_metric`__73 (kwarg dropped) | Draft H |
| T12 | subscribe broker qos `await self._client.subscribe(full_topic, qos=self.settings.qos_default)` (:616) → `qos=None` or kwarg dropped; existing test asserts only the positional topic (:567) | 2 | MC subscribe__6 (qos=None), __8 (kwarg dropped) | Draft H |

### LOW-VALUE — 141 keys, 7 clusters

| # | Pattern | n | Example keys | Note |
|---|---------|---|--------------|------|
| L1 | `logger.<lvl>(msg, extra={...})` mutations across MC `__init__`/connect/publish/subscribe/unsubscribe/disconnect: message→None/`XX..XX`/UPPER/lower, `extra=`→None/dropped, extra dict-key renames/case-flips, `str(e)`→`str(None)`, `attempt+1`→`attempt±k` inside log text | 89 | MC connect__100 (extra dropped), MC publish__68 (`duration_ms *1000`→`/1000`), MC `__init__`__17 (`"broker_host"`→`"XXbroker_hostXX"`) | No test asserts record text or `record.<extra-attr>`; cosmetic |
| L2 | background task metadata `name="mqtt-message-pump"` → None/`XX..XX`/UPPER (:632) | 4 | MC subscribe__24 | task name unasserted, nobody should |
| L4 | pump idle-sleep constant `asyncio.sleep(0.1)` (:802) → None (TypeError caught by loop's `except Exception` → internal error path) / 1.1 | 2 | `_message_processing_loop`__3, __4 | internal timing constant |
| L5 | Prometheus metric **name/description string** mutations in `_get_metric` defs (:130-164) — inert because `mock_prometheus_metrics` patches the metric classes; observable only against a real registry | 42 | `_get_metric`__26 (`"hsi_mqtt_connections_total"`→XX-pad), __29 (description lowercased) | renames = code-review surface, not test surface under current mock pattern |
| L6 | auto client_id slice `uuid4().hex[:8]` → `[:9]` (:Settings) | 1 | MCSettings __init____10 | client-id length unasserted |
| L7 | pump `while self._connected and self._client is not None` (:797) `and`→`or`/`is None` — only differs inside the disconnect cancel-race; deterministic unit tests cancel the task before the condition re-evaluates → unkillable in mock harness | 2 | `_message_processing_loop`__1, __2 | accepted |
| L8 | API default flip `health_check(ping: bool = False)` → `True` (:663) — repo callers pass explicit args; unobservable under mocks | 1 | MC health_check__1 | accepted |

### EQUIVALENT — 21 keys, 7 clusters

| # | Pattern | n | Example keys | Reason |
|---|---------|---|--------------|--------|
| E1 | `hasattr(obj, "attr")` attr-name string pad/case flips (`"ping"`→`"PING"`, `"value"`→`"VALUE"/"XXvalueXX"`) | 4 | MC health_check__11, MC _handle_message__6 | `AsyncMock`/`MagicMock` auto-create **any** attribute → `hasattr` returns True for every string → mutant takes the identical branch; on a real aiomqtt client (no lowercase `.ping`) original and mutant both skip |
| E2 | `__aexit__(None, None, None)` → `__aexit__(None, None)` / `(None, None, )` arg-count pad (:508) | 3 | MC disconnect__18-20 | AsyncMock accepts any signature; call still made |
| E3 | `topic.split("/", maxsplit=1)` pad variants: `maxsplit` dropped (=-1), `maxsplit=2`, `if ... or True` (:547) | 3 | MC publish__17, __21, __24 | all still yield the first path segment; `or True` is identical because `"x".split("/")==["x"]` |
| E4 | `dict.pop(topic, None)` → `dict.pop(topic,)` default-omitted (:658) | 1 | MC unsubscribe__8 | identical semantics |
| E5 | guard conjunct flips whose differing state is **unreachable via public API** (dead defensive tweaks): `and`→`or` in idempotency/connected guards, `is not None`→`is None` in singles | 7 | MC connect__1, MC publish__1, MC health_check__2 | (connected=True, client=None) and (False, client≠None) are never observable — connect sets both, disconnect clears both; mutants agree on all reachable states |
| E6 | dead initialization `last_exception: Exception \| None = None` → `""` / `publish` same (:394/:552) | 2 | MC connect__9, MC publish__29 | overwritten by `last_exception = e` before every read (the read only occurs after ≥1 failure) |
| E7 | `_find_callback` `if topic in self._subscriptions` → `not in` (:751) | 1 | MC _find_callback__1 | mutant still lands on the callback via the wildcard loop (`_topic_matches` returns True for exact matches) — same return for every input |

## Drafted tests — 6 highest-value clusters (T1,T2,T3,T4,T5,T6+T7,T8,T10)

All go in `backend/tests/unit/services/test_mqtt_client.py`, using existing fixtures/style. **UNVERIFIED — not yet run red/green.** TDD procedure (identical each): apply the cluster's mutant via the mutmut trampoline build → the new assertion FAILS (it contradicts the one-line diff); run against original `backend/services/mqtt_client.py` → PASSES.

### Draft C1 — kills T3 (14 keys). Needs no new imports.

```python
@pytest.mark.asyncio
async def test_connect_passes_all_settings_to_aiomqtt_client(
    mqtt_client, mock_aiomqtt_client, mqtt_settings
):
    """T3 lock: every aiomqtt.Client kwarg must come from settings.

    No existing test inspects the Client(...) construction, so
    hostname=None / port dropped / password=None mutants all survive.
    """
    with patch(
        "backend.services.mqtt_client.aiomqtt.Client",
        return_value=mock_aiomqtt_client,
        autospec=True,
    ) as mock_cls:
        await mqtt_client.connect()

        mock_cls.assert_called_once()
        kwargs = mock_cls.call_args.kwargs
        assert kwargs["hostname"] == MQTT_BROKER_HOST
        assert kwargs["port"] == MQTT_BROKER_PORT
        assert kwargs["identifier"] == MQTT_CLIENT_ID
        assert kwargs["username"] == MQTT_USERNAME
        assert kwargs["password"] == MQTT_PASSWORD
        assert kwargs["keepalive"] == 60
        assert kwargs["tls_context"] is None  # use_tls False in fixture
```

### Draft C2 — kills T4 (3 keys). Needs `import ssl` at top of test file.

```python
@pytest.mark.asyncio
async def test_connect_builds_tls_context_when_use_tls_true(mock_aiomqtt_client):
    """T4 lock: use_tls=True must pass a real SSLContext; use_tls=False must not."""
    settings = MQTTClientSettings(broker_host=MQTT_BROKER_HOST, use_tls=True)
    client = MQTTClient(settings=settings)
    with patch(
        "backend.services.mqtt_client.aiomqtt.Client",
        return_value=mock_aiomqtt_client,
        autospec=True,
    ) as mock_cls:
        await client.connect()
        tls_ctx = mock_cls.call_args.kwargs["tls_context"]
        assert isinstance(tls_ctx, ssl.SSLContext)  # kills tls_context=None mutants

    # and NOT built when TLS is off (kills always-build mutant __13).
    # use_tls passed explicitly: SettingsConfigDict(env_file=".env") could
    # otherwise pick MQTT_USE_TLS up from the developer .env.
    plain = MQTTClient(
        settings=MQTTClientSettings(broker_host=MQTT_BROKER_HOST, use_tls=False)
    )
    with patch(
        "backend.services.mqtt_client.aiomqtt.Client",
        return_value=mock_aiomqtt_client,
        autospec=True,
    ) as mock_cls2:
        await plain.connect()
        assert mock_cls2.call_args.kwargs["tls_context"] is None
```

### Draft A — kills T1 (22 keys). Needs `from unittest.mock import call` added to test imports.

```python
@pytest.mark.asyncio
async def test_metrics_record_exact_label_values_and_gauges(
    mqtt_client, mock_aiomqtt_client, mock_prometheus_metrics
):
    """T1 lock: metric label VALUES, not just that labels() was called.

    Existing tests only assert labels()/inc()/observe() happened with
    anything — status=None / "SUCCESS", state.set(2), duration computed
    with monotonic()+start all survive. Locks the observable contract:
      connections_total{status="success"|"failure"}, connection_state 1/0,
      errors_total{error_type="connection"}, messages_published_total
      {topic_type,qos}, publish_duration observed in sane seconds.
    """
    counter = mock_prometheus_metrics["counter_instance"]
    gauge = mock_prometheus_metrics["gauge_instance"]
    histogram = mock_prometheus_metrics["histogram_instance"]

    with patch(
        "backend.services.mqtt_client.aiomqtt.Client",
        return_value=mock_aiomqtt_client,
        autospec=True,
    ):
        await mqtt_client.connect()
        assert call(status="success") in counter.labels.call_args_list
        gauge.set.assert_called_with(1)

        await mqtt_client.publish("events/cam1", {"a": 1})
        assert call(topic_type="events", qos="1") in counter.labels.call_args_list
        assert call(topic_type="events") in histogram.labels.call_args_list  # kills #51
        observed = [
            c.args[0]
            for c in histogram.labels.return_value.observe.call_args_list
        ]
        assert observed and all(0 <= d < 60 for d in observed)  # kills #42 (+ => ~2e5)

        await mqtt_client.disconnect()
        # last-two gauge writes are subscriptions_active.set(0) then
        # connection_state.set(0) — value-list, not last-call, so a
        # set(1) on either gauge is caught
        assert gauge.set.call_args_list[-2:] == [call(0), call(0)]  # kills disconnect__16/__27

    # exhausted-connect: exact failure labels + state reset
    with (
        patch("backend.services.mqtt_client.aiomqtt.Client", autospec=True) as cls,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        cls.return_value.__aenter__.side_effect = ConnectionError("boom")
        client2 = MQTTClient(settings=mqtt_client.settings)
        client2.settings.max_retries = 1
        with pytest.raises(MQTTConnectionError):
            await client2.connect()

        assert call(status="failure") in counter.labels.call_args_list
        assert call(error_type="connection") in counter.labels.call_args_list
        gauge.set.assert_called_with(0)

    # subscribe + _handle_message: exact topic_pattern label
    async def cb(topic: str, payload: dict) -> None:
        pass

    mock_message = MagicMock()
    mock_message.topic.value = f"{MQTT_TOPIC_PREFIX}/commands/x"
    mock_message.payload = b'{"a": 1}'

    async def one_msg():
        yield mock_message

    mock_aiomqtt_client.messages = one_msg()
    with patch(
        "backend.services.mqtt_client.aiomqtt.Client",
        return_value=mock_aiomqtt_client,
        autospec=True,
    ):
        client3 = MQTTClient(settings=mqtt_client.settings)
        await client3.connect()
        await client3.subscribe("commands/x", cb)
        await client3._process_messages()
        assert call(topic_pattern="commands/x") in counter.labels.call_args_list
```

### Draft B — kills T2 (9 keys). No new imports.

```python
@pytest.mark.asyncio
async def test_publish_metrics_use_first_path_segment_as_topic_type(
    mqtt_client, mock_aiomqtt_client, mock_prometheus_metrics
):
    """T2 lock: topic_type must be the FIRST '/'-segment (maxsplit=1).

    rsplit / [1] / inverted-condition mutants survive because no test
    asserts the label VALUE (only labels.assert_called()).
    """
    counter = mock_prometheus_metrics["counter_instance"]
    with patch(
        "backend.services.mqtt_client.aiomqtt.Client",
        return_value=mock_aiomqtt_client,
        autospec=True,
    ):
        await mqtt_client.connect()

        await mqtt_client.publish("events/camera/front_door", {"a": 1})
        assert call(topic_type="events", qos="1") in counter.labels.call_args_list

        counter.labels.reset_mock()
        await mqtt_client.publish("health", {"a": 1})
        assert call(topic_type="health", qos="1") in counter.labels.call_args_list
```

### Draft D — kills T5 (5 keys). No new imports.

```python
@pytest.mark.asyncio
async def test_connect_exhaustion_chains_original_error(mqtt_client):
    """T5 lock: MQTTConnectionError.original_error must carry the last broker
    exception. Tests today match only the message text, so
    original_error=None / dropped / last_exception=None all survive."""
    boom = ConnectionError("refused-xyz")
    with (
        patch("backend.services.mqtt_client.aiomqtt.Client", autospec=True) as cls,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        cls.return_value.__aenter__.side_effect = boom
        mqtt_client.settings.max_retries = 1

        with pytest.raises(MQTTConnectionError) as exc_info:
            await mqtt_client.connect()

        assert exc_info.value.original_error is boom
```

### Draft E — kills T6+T7 (7 keys). Needs `MQTTPublishError` added to the file's import of `backend.services.mqtt_client`.

```python
@pytest.mark.asyncio
async def test_publish_exhausts_exactly_three_attempts_with_doubling_backoff(
    mqtt_client, mock_aiomqtt_client
):
    """T6/T7 lock: exactly max_publish_retries=3 publish attempts and
    sleep(1s), sleep(2s) between them. The existing retry test stops on
    attempt-3 success, so neither the count constant nor the publish-path
    backoff schedule is pinned."""
    with (
        patch(
            "backend.services.mqtt_client.aiomqtt.Client",
            return_value=mock_aiomqtt_client,
            autospec=True,
        ),
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        boom = ConnectionError("down")
        mock_aiomqtt_client.publish.side_effect = boom
        await mqtt_client.connect()

        with pytest.raises(MQTTPublishError) as exc_info:
            await mqtt_client.publish("t/x", {"a": 1})

        assert mock_aiomqtt_client.publish.call_count == 3  # kills count 3->4, < vs <=
        assert [c.args[0] for c in mock_sleep.call_args_list] == [1, 2]  # kills 2**attempt mutants
        # raised error keeps its cause (kills publish__70 last_exception=None)
        assert exc_info.value.original_error is boom
```

### Draft F — kills T8+T10 (5 keys). No new imports (uses existing fixtures).

```python
@pytest.mark.asyncio
async def test_unsubscribe_paths_pass_prefixed_topic_to_broker(
    mqtt_client, mock_aiomqtt_client
):
    """T8/T10 lock: the broker must receive the PREFIXED topic on both
    unsubscribe paths; disconnect() must actually fan out broker unsubscribes
    (not merely clear the local dict). Today tests assert only
    unsubscribe.assert_called_once()/len(_subscriptions)==0, so
    full_topic=None and skip-the-loop mutants survive."""

    async def cb(topic: str, payload: dict) -> None:
        pass

    with patch(
        "backend.services.mqtt_client.aiomqtt.Client",
        return_value=mock_aiomqtt_client,
        autospec=True,
    ):
        await mqtt_client.connect()
        await mqtt_client.subscribe("commands/test", cb)

        mock_aiomqtt_client.unsubscribe.reset_mock()
        await mqtt_client.unsubscribe("commands/test")
        mock_aiomqtt_client.unsubscribe.assert_called_once_with(
            f"{MQTT_TOPIC_PREFIX}/commands/test"
        )

        await mqtt_client.subscribe("status/a", cb)
        await mqtt_client.subscribe("status/b", cb)
        mock_aiomqtt_client.unsubscribe.reset_mock()
        await mqtt_client.disconnect()
        called = [c.args[0] for c in mock_aiomqtt_client.unsubscribe.call_args_list]
        assert f"{MQTT_TOPIC_PREFIX}/status/a" in called
        assert f"{MQTT_TOPIC_PREFIX}/status/b" in called  # kills disconnect__9 skip
```

### Draft G/H (documented, folded) — T9 (2), T11+T12 (3)

TDD procedure as above; drafts sketched for the next wave:
- **T9:** extend `test_connect_is_idempotent` with `mock_cls.assert_called_once()` after double-connect (kills connect__2/__8 re-create path).
- **T11:** with `mock_prometheus_metrics`, publish once and assert `histogram.call_args.kwargs["buckets"] == MQTT_PUBLISH_DURATION_BUCKETS` (import the constant).
- **T12:** in `test_subscribe_topic` add `mock_aiomqtt_client.subscribe.assert_called_once_with(f"{MQTT_TOPIC_PREFIX}/{topic}", qos=1)` (kills subscribe__6/__8).

## Residual notes

- T9 note: mutant re-enters `__aenter__` — harmless in tests, double-subscribes the broker in production; flagged to WP4.4 as a real defect the idempotency test was written to prevent but under-asserts.
- L1/L5 accepted: killing them needs caplog + real-registry tests; module policy treats log/metric-name text as code-review surface.
- E1 relies on the MagicMock `hasattr`-is-always-True property; if the team replaces mocks with `MagicMock(spec=aiomqtt.Client)` (memory: forward-ref/spec hygiene), E1 flips to TEST-GAP — re-triage then.
- All 232 keys reconciled exactly once (script-verified: assigned=232, missing=0, extra=0).
