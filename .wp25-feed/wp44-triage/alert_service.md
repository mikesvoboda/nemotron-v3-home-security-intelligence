# WP4.4 Triage Dossier — `backend/services/alert_service.py`

**Source:** `mutants/backend/services/alert_service.py.meta` (`exit_code_by_key`).
**Survivors (exit_code == 0):** 101 of 376 total keys (220 killed, 55 still null).
**Covering test files:**

- `backend/tests/unit/services/test_alert_service.py` (unit CRUD + WS emissions, mock-session based)
- `backend/tests/unit/services/test_webhook_integration.py` (NEM-3624 webhook trigger integration)

Diffs obtained by locally AST-diffing each `__mutmut_N` variant in the mutant copy against the
original body (per task constraints — no pytest / mutmut run). Two signature-only mutants
(`_emit_alert_updated__1`, `_build_alert_updated_payload__1`) confirmed via read-only
`mutmut show`. All 101 keys are placed in exactly one cluster (sum = 101).

## Semantic probes (plain `python`, not tests)

- `AlertSeverity.HIGH == "high"` is **True** (StrEnum), and `AlertSeverity.HIGH.value == "high"`.
  So any `alert.X.value if hasattr(alert.X,"value") else alert.X` ternary that still yields the
  StrEnum member produces a payload value **equal** to the original `.value` string → EQUIVALENT.
- `select(Alert).where(None)` builds a WHERE-less select (no error at build time);
  `where(Alert.id == None)` renders `alerts.id IS NULL`. `select(None)` → `SELECT NULL`.
  All four differ from the correct statement under `stmt.compare(expected)` (verified: True for
  original, False for all four mutants) → killable via a `compare()` assertion.

## Classification totals

- **TEST-GAP:** 28 mutants (9 clusters: C3,C4,C5,C6,C7,C8,C10,C12,C13) — real behavior change, covered line never asserted.
- **EQUIVALENT:** 32 mutants (3 clusters: C1,C9,C14) — pure log-message text + StrEnum/dead-default tweaks.
- **LOW-VALUE:** 41 mutants (3 clusters: C2,C11,C15) — log `extra` metadata + dead/unexercised fallback branch.

> Headline: 49/101 survivors (C1+C2) are pure **logging** concerns (message text + `extra` dict).
> 20/101 (C9) are StrEnum `hasattr(…,"value")` ternary mutations that are value-equivalent.
> The 28 TEST-GAP mutants are the real WP4.4 work and cluster into 9 focused assertions.

## Cluster table

| #   | Function / concern                                              | Mutation pattern                                                                                                                                                                                                                                                                          | Count | Class          | Example keys (fn\_\_mutmut_N)                                                |
| --- | --------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----- | -------------- | ---------------------------------------------------------------------------- |
| C1  | create/update/delete/ack/dismiss `_emit_alert_created`          | `logger.<debug/warning>` **message arg**: `f"…"`→`None`, case-flip, `XX…XX` wrap                                                                                                                                                                                                          | 11    | **EQUIVALENT** | create_alert**30, \_emit_alert_created**3, \_emit_alert_created\_\_5         |
| C2  | same set of public methods                                      | `logger…(msg, extra={…})`: `extra=None`, drop `extra=`, rename keys `alert_id`→`ALERT_ID`/`XXalert_idXX` etc.                                                                                                                                                                             | 38    | **LOW-VALUE**  | create_alert**31, create_alert**35, delete_alert\_\_18                       |
| C3  | create/update/ack/dismiss                                       | session write hand-off: `_session.add(alert)`→`add(None)`, `refresh(alert)`→`refresh(None)`                                                                                                                                                                                               | 4     | **TEST-GAP**   | create_alert**17, update_alert**25, acknowledge_alert\_\_11                  |
| C4  | update/delete/ack/dismiss                                       | lookup identity: `get_alert(alert_id)`→`get_alert(None)`                                                                                                                                                                                                                                  | 4     | **TEST-GAP**   | update_alert**2, delete_alert**2, dismiss_alert\_\_2                         |
| C5  | get_alert                                                       | query construction: `execute(stmt)`→`execute(None)`, `where(x)`→`where(None)`, `select(Alert)`→`select(None)`, `==`→`!=`                                                                                                                                                                  | 4     | **TEST-GAP**   | get_alert**5 (`!=` — fetches wrong row), get_alert**2, get_alert\_\_4        |
| C6  | update_alert                                                    | field assignment wipe: `alert.severity = severity`→`= None`, `alert.channels = channels`→`= None`                                                                                                                                                                                         | 2     | **TEST-GAP**   | update_alert**15, update_alert**20                                           |
| C7  | create/ack/dismiss                                              | webhook call args: `event_data`→`None`, `alert.id`→`None` (event_id kwarg)                                                                                                                                                                                                                | 5     | **TEST-GAP**   | create_alert**24, create_alert**25, dismiss_alert\_\_30                      |
| C8  | ack/dismiss                                                     | metadata timestamp value: `["acknowledged_at"/"dismissed_at"] = now(UTC).isoformat()` → `= None` / `now(None)` (naive)                                                                                                                                                                    | 4     | **TEST-GAP**   | acknowledge_alert**7, acknowledge_alert**10, dismiss_alert\_\_10             |
| C9  | `_build_alert_created_payload` / `_build_alert_updated_payload` | `alert.{severity,status}.value if hasattr(alert.{s},"value") else …`: `and False`/`or True`/`hasattr(None,`/`"value"`→`"XXvalueXX"`/`"VALUE"`                                                                                                                                             | 20    | **EQUIVALENT** | \_build_alert_created_payload**9, **20, \_build_alert_updated_payload\_\_37  |
| C10 | created + updated payload                                       | timestamp condition forced to fallback: `alert.created_at`→`(alert.created_at) and False`, `alert.updated_at`→`(…) and False` (uses wall-clock `now` instead of stored ts)                                                                                                                | 3     | **TEST-GAP**   | \_build_alert_created_payload**31, **36, \_build_alert_updated_payload\_\_11 |
| C11 | created payload fallback                                        | fallback `datetime.now(UTC)`→`now(None)` in the `else` branch (naive) — branch unreachable when ts set (DB always populates)                                                                                                                                                              | 2     | **LOW-VALUE**  | \_build_alert_created_payload**33, **38                                      |
| C12 | updated payload                                                 | `payload["severity"] = <ternary>` → `None` (key stays present, value nulled)                                                                                                                                                                                                              | 1     | **TEST-GAP**   | \_build_alert_updated_payload\_\_32                                          |
| C13 | `_emit_alert_updated`                                           | signature default `acknowledged: bool = False`→`True` — relied upon by update/dismiss callers → wrongly emits `acknowledged=True`                                                                                                                                                         | 1     | **TEST-GAP**   | \_emit_alert_updated\_\_1                                                    |
| C14 | `_build_alert_updated_payload`                                  | signature default `acknowledged: bool = False`→`True` — dead: every caller passes it explicitly                                                                                                                                                                                           | 1     | **EQUIVALENT** | \_build_alert_updated_payload\_\_1                                           |
| C15 | updated payload                                                 | timestamp condition `alert.updated_at`→`(alert.updated_at) or True` — guard becomes truthy, so the `else now()` branch (reachable only if updated_at is None) crashes instead of falling back. Not a value change on any covered path (DB always populates updated_at); not worth killing | 1     | **LOW-VALUE**  | \_build_alert_updated_payload\_\_12                                          |

### Per-cluster TEST-GAP justification (what the covering test misses)

- **C3** — `test_alert_service.py:129` does `mock_session.add.assert_called_once()` and `:131`
  `refresh.assert_called_once()`: **no argument check**. `add` is a `MagicMock` and `refresh` is an
  `AsyncMock` (in update/ack/dismiss tests it has no `side_effect`), so `add(None)`/`refresh(None)`
  are recorded silently. The created/updated alert is the same returned object, so value asserts pass.
  → assert `add`/`refresh` called _with the alert instance_.
- **C4** — every CRUD test stubs `mock_session.execute.return_value = mock_result` unconditionally
  (`scalar_one_or_none` → the sample), so `get_alert(None)` still returns the found alert. Nothing
  asserts the id used for lookup. → assert `get_alert` was called with `alert_id`.
- **C5** — `test_returns_alert_when_found:253-265` stubs `execute` to return the row regardless of the
  statement and only asserts `result == sample_alert`. A `!=` predicate (fetches the _wrong_ alert) is
  invisible. → don't blind-stub: capture the statement and assert `stmt.compare(select(Alert).where(Alert.id==id))`.
- **C6** — `test_updates_multiple_fields:369-390` asserts `updated_fields` membership only, never
  `result.severity` / `result.channels`. Assigning `None` still appends the field to `updated_fields`.
  → assert the assigned values survive.
- **C7** — `test_create_alert_triggers_webhook:106-108` / acknowledge `:136-138` assert only
  `call_args[0][1] == WebhookEventType.ALERT_*` (the type). dismiss `:166-171` checks
  `webhook_data["dismissed_reason"]` but not the `event_id` kwarg. `event_data=None` and
  `event_id=None` pass. → assert the data dict content and `event_id` kwarg.
- **C8** — `test_adds_acknowledged_at_to_metadata:524-540` / `test_adds_dismissed_metadata:608-625`
  assert key **presence** (`"acknowledged_at" in metadata`), never the value. `= None` keeps the key;
  `now(None)` yields a naive (UTC-stripped) string. → assert value is a UTC-aware ISO string.
- **C10** — `test_build_alert_created_payload:664-665` asserts `"created_at" in payload` only. The
  `and False` mutants swap the stored timestamp for wall-clock `now()`. → assert the value equals the
  alert's stored `created_at.isoformat()` (use a fixed old date to avoid timing flake).
- **C12** — `test_build_alert_updated_payload:684` asserts `"severity" in payload` (key present), so
  `payload["severity"] = None` survives. → assert the value equals `alert.severity.value`.
- **C13** — `test_emits_alert_updated_event` (update `:307-330`, dismiss `:583-606`) never assert that
  `acknowledged` is **absent**. Default flip to `True` wrongly tags plain update/dismiss emissions.
  → assert `"acknowledged" not in payload` for a non-acknowledge update.

## Drafted tests

Add to `backend/tests/unit/services/test_alert_service.py` (new imports required: `patch` from
`unittest.mock`, `timedelta` from `datetime`, `select` from `sqlalchemy`, `Alert` already imported).
Style matches the existing file: fixtures `mock_session` / `mock_emitter` / `sample_alert`.

**// UNVERIFIED — not yet run red/green.** TDD: add the test, confirm it FAILS against the listed
mutant(s), then confirm it PASSES against the unmutated `backend/services/alert_service.py`.

### T1 — kills C5 (get_alert query integrity) — HIGHEST VALUE

```python
@pytest.mark.asyncio
async def test_get_alert_queries_by_primary_key(self, mock_session: AsyncMock) -> None:
    """get_alert must execute 'SELECT ... FROM alerts WHERE alerts.id = <alert_id>'.

    Kills get_alert__2 (execute(None)), __3 (where(None)), __4 (select(None)),
    __5 (== -> !=). The existing tests stub session.execute to return the same row
    for ANY statement, so the wrong/absent predicate is never observable there.
    """
    alert_id = str(uuid.uuid4())
    captured: dict[str, object] = {}

    async def fake_execute(stmt):
        captured["stmt"] = stmt
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        return result

    mock_session.execute.side_effect = fake_execute
    service = AlertService(mock_session)
    await service.get_alert(alert_id)

    expected = select(Alert).where(Alert.id == alert_id)
    assert captured["stmt"] is not None, "statement handed to execute() must not be None"
    assert captured["stmt"].compare(expected), (
        f"query must select alerts by primary key, got: {captured['stmt']}"
    )
```

Red on `!=`/`where(None)`/`select(None)` (compare → False) and on `execute(None)` (`is not None` fails);
green on the original (compare → True).

### T2 — kills C6 (update silently nulls severity/channels)

```python
@pytest.mark.asyncio
async def test_update_alert_assigns_severity_and_channels(
    self, mock_session: AsyncMock, mock_emitter: AsyncMock, sample_alert: Alert
) -> None:
    """update_alert must persist the NEW values, not None.

    Kills update_alert__15 (severity = None) and __20 (channels = None). Existing
    test_updates_multiple_fields only checks 'updated_fields' membership.
    """
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_alert
    mock_session.execute.return_value = mock_result

    service = AlertService(mock_session, mock_emitter)
    result = await service.update_alert(
        sample_alert.id,
        severity=AlertSeverity.CRITICAL,   # sample is HIGH -> differs -> block runs
        channels=["sms"],
    )

    assert result is not None
    assert result.severity == AlertSeverity.CRITICAL
    assert result.channels == ["sms"]
```

### T3 — kills C8 (metadata timestamp must be a real UTC-aware ISO string)

```python
@pytest.mark.asyncio
@pytest.mark.parametrize("method,key", [("acknowledge", "acknowledged_at"), ("dismiss", "dismissed_at")])
async def test_status_timestamp_metadata_is_utc_aware(
    self,
    mock_session: AsyncMock,
    mock_emitter: AsyncMock,
    sample_alert: Alert,
    method: str,
    key: str,
) -> None:
    """acknowledged_at / dismissed_at must be a tz-aware ISO-8601 timestamp.

    Kills acknowledge/dismiss __7 (value -> None) and __10 (datetime.now(UTC) ->
    datetime.now(None), naive). Existing tests only assert key presence.
    """
    sample_alert.alert_metadata = None
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_alert
    mock_session.execute.return_value = mock_result

    service = AlertService(mock_session, mock_emitter)
    if method == "acknowledge":
        result = await service.acknowledge_alert(sample_alert.id)
    else:
        result = await service.dismiss_alert(sample_alert.id)

    raw = result.alert_metadata[key]
    assert isinstance(raw, str), f"{key} must be a timestamp string, got {raw!r}"
    parsed = datetime.fromisoformat(raw)
    assert parsed.tzinfo is not None and parsed.utcoffset() == timedelta(0), (
        f"{key} must be UTC-aware, got naive {raw!r}"
    )
```

### T4 — kills C3 (session add/refresh receive the alert instance, not None)

```python
@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["create", "update", "acknowledge", "dismiss"])
async def test_persistence_calls_receive_the_alert_instance(self, method: str) -> None:
    """add()/refresh() must receive the Alert object, never None.

    Kills create_alert__17 (add(None)), update_alert__25, acknowledge_alert__11,
    dismiss_alert__14 (all refresh(None)). Existing tests assert add/refresh were
    *called* but never *with what*.
    """
    session = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    emitter = AsyncMock()
    emitter.broadcast = AsyncMock(return_value=True)
    service = AlertService(session, emitter)
    alert_id = str(uuid.uuid4())

    if method == "create":
        async def _set_ids(a: Alert) -> None:
            a.id = alert_id
            a.created_at = datetime.now(UTC)
            a.updated_at = datetime.now(UTC)

        session.refresh.side_effect = _set_ids
        alert = await service.create_alert(
            event_id=1, severity=AlertSeverity.HIGH, dedup_key="k"
        )
        session.add.assert_called_once_with(alert)
        session.refresh.assert_called_once_with(alert)
    else:
        existing = Alert(
            id=alert_id, event_id=1, rule_id=str(uuid.uuid4()),
            severity=AlertSeverity.HIGH, status=AlertStatus.PENDING,
            dedup_key="k", channels=[], created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        result = MagicMock()
        result.scalar_one_or_none.return_value = existing
        session.execute.return_value = result

        if method == "update":
            returned = await service.update_alert(alert_id, status=AlertStatus.DELIVERED)
        elif method == "acknowledge":
            returned = await service.acknowledge_alert(alert_id)
        else:
            returned = await service.dismiss_alert(alert_id, reason="r")

        assert returned is existing
        session.refresh.assert_called_once_with(existing)
```

### T5 — kills C7 (webhook receives the real payload dict + event_id)

```python
@pytest.mark.asyncio
async def test_alert_webhooks_carry_payload_and_event_id(
    self, mock_session: AsyncMock, mock_emitter: AsyncMock, sample_alert: Alert
) -> None:
    """create/acknowledge/dismiss must pass the alert data + alert.id to the webhook.

    Kills create_alert__24/__25, acknowledge_alert__24/__25, dismiss_alert__30.
    Existing webhook tests assert only the event-type argument.
    """
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_alert
    mock_session.execute.return_value = mock_result
    webhook = MagicMock()
    webhook.trigger_webhooks_for_event = AsyncMock()

    with patch(
        "backend.services.alert_service.get_webhook_service",
        return_value=webhook, autospec=True,
    ):
        service = AlertService(mock_session, mock_emitter)

        await service.acknowledge_alert(sample_alert.id)
        call = webhook.trigger_webhooks_for_event.call_args
        assert call[1]["event_id"] == sample_alert.id          # kills __25 (event_id=None)
        data = call[0][2]
        assert isinstance(data, dict) and data["alert_id"] == sample_alert.id  # kills __24

        await service.dismiss_alert(sample_alert.id, reason="r")
        call = webhook.trigger_webhooks_for_event.call_args
        assert call[1]["event_id"] == sample_alert.id          # kills dismiss_alert__30

        # create path: id is minted by refresh()
        webhook.reset_mock()
        async def _ids(a: Alert) -> None:
            a.id = "created-alert-id"
            a.created_at = datetime.now(UTC)
            a.updated_at = datetime.now(UTC)
        session2 = AsyncMock()
        session2.add = MagicMock(); session2.flush = AsyncMock()
        session2.refresh = AsyncMock(side_effect=_ids)
        service2 = AlertService(session2, mock_emitter)
        await service2.create_alert(event_id=7, severity=AlertSeverity.HIGH, dedup_key="k")
        call = webhook.trigger_webhooks_for_event.call_args
        assert call[1]["event_id"] == "created-alert-id"        # kills create_alert__25
        assert isinstance(call[0][2], dict) and call[0][2]["event_id"] == 7  # kills create_alert__24
```

### T6 — kills C10 (payload reports stored timestamps, not wall-clock now)

```python
def test_payloads_use_stored_timestamps(self, mock_session: AsyncMock) -> None:
    """created/updated payloads must echo the alert's stored created_at/updated_at.

    Kills _build_alert_created_payload__31/__36 and
    _build_alert_updated_payload__11 (`alert.created_at` -> `(…) and False` forces
    the wall-clock `datetime.now()` fallback). Uses a fixed past date so the mutant's
    now() can never coincidentally match. Existing builder tests only assert key presence.
    """
    ts = datetime(2020, 1, 1, tzinfo=UTC)
    alert = Alert(
        id=str(uuid.uuid4()), event_id=1, rule_id=str(uuid.uuid4()),
        severity=AlertSeverity.HIGH, status=AlertStatus.PENDING,
        dedup_key="k", channels=[], created_at=ts, updated_at=ts,
    )
    service = AlertService(mock_session)

    created = service._build_alert_created_payload(alert)
    assert created["created_at"] == ts.isoformat()
    assert created["updated_at"] == ts.isoformat()

    updated = service._build_alert_updated_payload(alert, updated_fields=["status"])
    assert updated["updated_at"] == ts.isoformat()
```

### Untested-but-trivially-killable TEST-GAP clusters (one-line assertions; not drafted in full)

- **C4** (get_alert(None) in update/delete/ack/dismiss): after the CRUD call, assert
  `service.get_alert = AsyncMock(...)` then `service.get_alert.assert_called_once_with(alert_id)`.
- **C12** (`payload["severity"] = None`): extend `test_build_alert_updated_payload` with
  `assert payload["severity"] == sample_alert.severity.value`.
- **C13** (`_emit_alert_updated` ack default flip): in a plain-update emission test add
  `assert "acknowledged" not in payload`.

## Notes / caveats

- **C9 = 20 EQUIVALENT** rests on StrEnum semantics (`HIGH == "high"`), verified. If a future
  consumer type-checks (`isinstance(str)` is True for StrEnum, but `type(x) is str` is False) or the
  payload is compared by identity somewhere outside these tests, these would become TEST-GAP.
  Re-verify if the WS/JSON serialization contract ever tightens.
- **C2 (38) / C1 (11)** are deliberately not worth asserting: log `extra` metadata and message
  strings are diagnostic only; adding `caplog` assertions here would be brittle and low-signal.
  Recommend marking these `LOW-VALUE`/`EQUIVALENT` in the baseline rather than chasing them.
- **C13 vs C14**: the `_emit_alert_updated` default flip (C13) is real (update/dismiss rely on it);
  the `_build_alert_updated_payload` default flip (C14) is dead (all callers pass the arg), hence
  EQUIVALENT. This is a genuinely subtle distinction — keep both, opposite classifications.
