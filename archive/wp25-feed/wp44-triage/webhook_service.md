# WP4.4 Triage Dossier — backend/services/webhook_service.py

- **Source:** `backend/services/webhook_service.py` (1,278 lines) · Mutant copy: `mutants/backend/services/webhook_service.py`
- **Verdict file:** `mutants/backend/services/webhook_service.py.meta` — 1,075 keys, **571 survived** (exit_code 0), 504 killed, 0 unchecked.
- **Method:** all 571 per-mutant diffs extracted mechanically by diffing each `…__mutmut_N` variant body against its `__mutmut_orig` in the mutant copy (truncating mutmut's trailing registration lines). Cluster counts below partition 571 exactly (sum verified programmatically). No tests were run; all drafted tests are **UNVERIFIED**.
- **Key structural fact:** `WebhookEventType` and `IntegrationType` are `StrEnum`. `str(member) == member.value` in Python 3.11+ (verified), so every mutation of the defensive pattern `X.value if hasattr(X,"value") else str(X)` is semantically a no-op for the actual inputs (`hasattr` → False, key renamed, `or True`/`and False`, receiver → None, `str(None)` → `'None'` which equals `str(event_type)` — all collapse to the same string).
- **Another dead field:** `self._http_client` is written in `__init__` and **never read anywhere in the module** (verified: only the docstring and the assignment reference it) — `__init__` mutants are unkillable through any observable behavior.

## Covering test files (from `tests_by_mangled_function_name`, filtered to webhook tests)

| File | Role | Key anchor tests (line) |
|---|---|---|
| `backend/tests/unit/services/test_webhook_service.py` | primary unit suite for every `WebhookService` method | `test_get_health_summary` :870 (scalar mocks only), `test_deliver_webhook_success` :447, `test_get_deliveries` :934, `test_send_request_with_signature` :1334, `test_format_slack_payload` :1050, `test_format_discord_payload` :1068, `test_format_teams_payload` :1087, `test_build_payload_*` :983–1048, `test_build_test_event_data_*` :1419–1451, `test_get_webhook_service_singleton` :1459, `test_trigger_webhook_background_*` :1470/:1498 |
| `backend/tests/unit/services/test_webhook_integration.py` | call-site integration (alert engine → webhook trigger) | :79–:417 |
| `backend/tests/integration/test_webhook_service.py` | real-DB CRUD/trigger/health | `TestWebhookServiceCRUD` :50, `TestWebhookServiceHealth` :381 |
| `backend/tests/unit/api/routes/test_webhooks.py` | route layer | (appears in several functions' test lists) |

**Recurring weakness (why so many TEST-GAPs):** every CRUD/delivery/health test stubs `mock_db_session.execute` with canned `MagicMock` results (`test_webhook_service.py:226–235` etc.) and only asserts the canned values flow through — the SQL text (where/order/limit/avg/status predicates) is never inspected. And shape asserts on payloads are existence-only (`"fields" in result["embeds"][0]`), never full-shape equality, so key renames/case flips/`inline:False`/list-cap changes all survive.

## Cluster table (sums to 571)

| # | Cluster | Count | Class | Example keys (short) | Verdict basis |
|---|---|---|---|---|---|
| 1 | bted-values: `_build_test_event_data` literal dict keys/values changed (`XX…XX`, `UPPER`, `1.95`/`1.87` floats) | 87 | TEST-GAP | WS._build_test_event_data#22, #75, #100 | tests :1419–1451 assert only `"alert_id" in data` membership, never equality of the canned sample payloads |
| 2 | query-build: CRUD/delivery SELECTs mutated (`select(None)`, `where(None)`, `==`→`!=`, `is_(True)`→`is_(False/None)`, `order_by(None)`, `limit/offset(None)`, `db.execute(None)`, `get_webhook(db, None)`) | 45 | TEST-GAP | WS.delete_webhook#3, WS.get_deliveries#12, WS.list_webhooks#6 | mock-session execute never inspects the statement; DB-side tests only happy-path |
| 3 | health-queries: `get_health_summary` count/avg statements mutated (`where(None)`, `>=`→`>`, `==SUCCESS/FAILED`→`!=`, `.is_(None/False)`, `and_` args dropped) | 40 | TEST-GAP | WS.get_health_summary#13, #27, #41 | test :870 mocks every scalar; SQL text never asserted |
| 4 | delivery-record: `deliver_webhook`/`retry`/`test`/`trigger` call+construction args → None (payload, webhook_id, event_type, event_id, `request_payload`, `_build_payload(None,…)`, `_send_request(None,…)`, positional drops) | 34 | TEST-GAP | WS.deliver_webhook#1, #11, #13 | `test_deliver_webhook_success` asserts status/stats but never `delivery.webhook_id/event_type/event_id/request_payload` or that the built payload reached `_send_request` |
| 5 | fmt-discord: `_format_discord_payload` keys/values/limits mutated (`"name"`→`"NAME"`, `inline:True`→`False`, `fields[:25]`→`[:26]`, timestamp lookup broken, whole field-dict → None) | 30 | TEST-GAP | WS._format_discord_payload#26, #39, #54 | test :1068 checks only `"embeds" in`, title, `"fields" in` |
| 6 | fmt-teams: `_format_teams_payload` same pattern (`@context`/`themeColor`/`summary` keys+values, `facts[:10]`→`[:11]`) | 29 | TEST-GAP | WS._format_teams_payload#36, #45, #58 | test :1087 checks `@type`, title, `"facts" in` only |
| 7 | fmt-slack: `_format_slack_payload` blocks keys/values mutated (`"type":"section"`→`"SECTION"`, nested `"text"`→`"TEXT"`, `mrkdwn`→`MRKDWN`) | 18 | TEST-GAP | WS._format_slack_payload#24, #31, #34 | test :1050 checks only `"text" in`/`"blocks" in`/substring |
| 8 | stats: webhook counters `+= 1`→`= 1`/`-= 1`/`+= 2`, `last_delivery_at = None` in success/failure/retry paths | 16 | TEST-GAP | WS.deliver_webhook#46, #90, WS.retry_delivery#47 | fixture starts counters at 0 so `+=1`==`=1`; `last_delivery_at` never asserted |
| 9 | signature: `_sign_payload` json canonicalization kwargs mutated (`sort_keys`→False/None, `separators`, receiver None) and `_send_request` `X-Webhook-Signature*` headers → None | 14 | TEST-GAP | WS._send_request#83, #92, WS._sign_payload#9 | test :1334 asserts only key presence + `sha256=` prefix; signature never recomputed/compared |
| 10 | resp-fields: `delivery.response_body=None`, `response_time_ms=None`, `error_message=str(e)[:500]`→`[:501]` (deliver/retry/test) | 14 | TEST-GAP | WS.deliver_webhook#67, #78, WS.test_webhook#54 | success test asserts response_time but survives per verdicts — assertion set doesn't cover every assignment path; truncation never checked |
| 11 | create-fields: `create_webhook` stores `integration_type/payload_template/max_retries/retry_delay_seconds = None` (or kwarg dropped) | 8 | TEST-GAP | WS.create_webhook#8, #13, #24 | test :124 asserts name/url/event_types/enabled/secret only |
| 12 | int-routing: `_format_for_integration` comparison targets `"slack"/"discord"/"teams"` renamed (falls through to generic passthrough) | 6 | TEST-GAP | WS._format_for_integration#11, #15, #17 | no test routes a non-generic `integration_type` through `_format_for_integration`/`_build_payload` |
| 13 | boundary300: `200 <= status < 300` → `<= 300` / `< 301` (deliver/retry/test success classification) | 6 | TEST-GAP | WS.deliver_webhook#39, WS.retry_delivery#30, WS.test_webhook#33 | no test uses status 300 |
| 14 | health-boundary: `total_deliveries > 0`→`> 1`, `>= 0.9`→`> 0.9`, `< 0.5`→`<= 0.5`, `count += 1`→`= 1`, avg-truthiness `if x`→`if x or True` | 6 | TEST-GAP | WS.get_health_summary#80, #85, #107 | test uses rates .95/.80/.45 — never the exact .9/.5/.0 or avg==0 edges |
| 15 | or-default: `scalar() or 0`→`or 1` (health summary counts, `get_deliveries` total) | 6 | TEST-GAP | WS.get_health_summary#17, WS.get_deliveries#9 | tests mock scalar to nonzero; zero-count path never fed |
| 16 | jinja-context: `template.render(event_type=…, timestamp=…, webhook_id=…)` values → None / kwargs dropped (silent jinja Undefined → empty string) | 6 | TEST-GAP | WS._build_payload#28, #30, #32 | template tests :1000/:1574 only use `data.*`/direct fields, never `event_type`/`webhook_id`/`timestamp` |
| 17 | db-args: `db.add(None)`, `db.refresh(None)` (create/deliver/retry/update) | 6 | TEST-GAP | WS.create_webhook#40, WS.deliver_webhook#105 | tests assert `add.assert_called_once()` without arguments |
| 18 | post-args: `client.post(webhook.url, json=payload)` → url/json None or dropped; `AsyncClient(timeout=DEFAULT_TIMEOUT)`→`timeout=None` | 5 | TEST-GAP | WS._send_request#100, #101, #98 | `post.assert_called_once()` + status echo only; url/json/timeout unasserted |
| 19 | singleton: `get_webhook_service` `is None`→`is not None`, instance → None (returns None service) | 2 | TEST-GAP | get_webhook_service#1, #2 | :1459 asserts `service1 is service2` — true for None==None and for the not-None flip after first call |
| 20 | bted-fallback: `event_specific_data.get(value, {})` → `None` / arg dropped (unknown event types raise TypeError on merge) | 2 | TEST-GAP | WS._build_test_event_data#125, #127 | :1443 mislabels its input: `SYSTEM_HEALTH_CHANGED` IS a mapped key; no truly-unknown enum (`BATCH_ANALYSIS_*`) tested |
| 21 | timing-formula: `* 1000` → `/ 1000` / `* 1001` in `_send_request` ms conversion | 2 | TEST-GAP | WS._send_request#110, #112 | test asserts only `response_time >= 0` (mocked call ≈0 ms, all formulas agree) |
| 22 | tw-body: `test_webhook` response_body `if response_body else None` → always None / condition removed / `and False` | 3 | TEST-GAP | WS.test_webhook#37, #42, #44 | :659 success test never asserts `result.response_body` |
| 23 | hdrs-names: `_send_request` headers dict **keys** renamed (`"XXContent-TypeXX"`, `"XXUser-AgentXX"`) | 3 | TEST-GAP | WS._send_request#2, #5, #7 | tests inspect only auth/signature header keys |
| 24 | auth-defaults: `.get("type"/"token"/"username"/…,"")` default tweaks (`None`, `"XXXX"`, missing kwarg) | 19 | LOW-VALUE | WS._send_request#16, #33, #56 | most pairs are true equivalents (`""`/missing/`None` all yield the same header value or skip path); the rest fire only on malformed auth_config (schema types make `None` values unrepresentable through validated creation); auth-header behavior is asserted where observable (:1176/:1213/:1255) |
| 25 | UA-string: `User-Agent` value → `XXNemotronWebhook/1.0XX`/lower/upper | 3 | LOW-VALUE | WS._send_request#10, #11, #12 | cosmetic client identification string; nobody should assert exact casing |
| 26 | tw-body-edge: `response_body = X if X or True else None` (`''` stays `''` instead of `None`) | 1 | LOW-VALUE | WS.test_webhook#45 | behavior differs only for empty-string response bodies — unspecified |
| 27 | log: all `logger.*` message strings → None, `extra` dicts → None/removed, extra-dict key renames (`XXwebhook_idXX`, `WEBHOOK_ID`), `exc_info=True`→None/False (16 functions) | 88 | EQUIVALENT | trigger_webhook_background#10, WS.deliver_webhook#54, WS.create_webhook#43 | pure observability; no test should assert log text |
| 28 | strvalue: `X.value if hasattr(X,"value") else str(X)` defensive mutations (StrEnum ⇒ `str(e)=="alert_fired"`) — build_payload/bted/deliver/create/update/trigger/format_for_integration | 45 | EQUIVALENT | WS._build_payload#3, WS.trigger_webhooks_for_event#9, WS.create_webhook#28 | `StrEnum.__str__ == value` (verified in this Python); mutants produce identical output |
| 29 | updated-fields: `updated_fields.append("name"/"url"/…)` text mutations (list flows only into `logger.debug` extra) | 15 | EQUIVALENT | WS.update_webhook#11, #32, #45 | never returned or persisted; log-only sink |
| 30 | dead-store: writes immediately overwritten/never read (`status=PENDING`→None (column default is PENDING, `models/outbound_webhook.py:285`; later overwritten before flush), retry `status=None`→then overwritten, `_handle_delivery_failure(db→None)` (param is `# noqa: ARG002` unused)) | 5 | EQUIVALENT | WS.deliver_webhook#12, #18, WS.deliver_webhook#70 | no observable state change |
| 31 | hdr-case: HTTP header **keys** case variants (`content-type`, `USER-AGENT`) | 5 | EQUIVALENT | WS._send_request#3, #8 | httpx `Headers` is case-insensitive; wire format canonicalizes |
| 32 | tokenhex-default: `secrets.token_hex(32)` → `token_hex(None)` | 1 | EQUIVALENT | WS.create_webhook#2 | CPython default for `nbytes` is 32 — identical output distribution (verified) |
| 33 | init: `self._http_client = http_client` → `= None` | 1 | EQUIVALENT | WS.__init__#1 | `_http_client` never read anywhere (verified by grep) — dead attribute |

**Totals:** TEST-GAP 388 · EQUIVALENT 160 · LOW-VALUE 23 · **sum 571** (partition verified against the 33-cluster JSON).

## Drafted kill-tests (UNVERIFIED — not yet run red/green)

Target file for all six: `backend/tests/unit/services/test_webhook_service.py` (append; fixtures `webhook_service`, `sample_webhook`, `mock_db_session` and imports already exist there — additions needed are `DEFAULT_TIMEOUT` from the service module and `re`).

TDD procedure (same for all): apply the mutant diff → the new assert fails; original source → passes (green); then re-run the module's mutants against the test to confirm kills.

### D1 — kills cluster #1 bted-values (87) + #20 bted-fallback (2)

```python
def test_build_test_event_data_exact_payloads(webhook_service):
    """UNVERIFIED - not yet run red/green. Kills key/value text mutations in the
    sample-event-data table (XX…XX, case flips, 1.95/1.87) and the .get(default={}) loss."""
    fired = webhook_service._build_test_event_data(WebhookEventType.ALERT_FIRED)
    assert fired["alert_id"] == "test-alert-001"
    assert fired["severity"] == "high"
    assert fired["camera_id"] == "front_door"
    assert fired["description"] == "Test alert triggered"
    for et, key in [
        (WebhookEventType.ALERT_DISMISSED, "alert_id"),
        (WebhookEventType.ALERT_ACKNOWLEDGED, "alert_id"),
    ]:
        assert webhook_service._build_test_event_data(et)[key] == "test-alert-001"
    created = webhook_service._build_test_event_data(WebhookEventType.EVENT_CREATED)
    assert created["event_id"] == "test-event-001"
    assert created["camera_id"] == "front_door"
    assert created["event_type"] == "motion_detected"
    enriched = webhook_service._build_test_event_data(WebhookEventType.EVENT_ENRICHED)
    assert enriched["event_id"] == "test-event-001"
    assert enriched["enrichment_type"] == "person_detection"
    assert enriched["confidence"] == 0.95
    entity = webhook_service._build_test_event_data(WebhookEventType.ENTITY_DISCOVERED)
    assert entity["entity_id"] == "test-entity-001"
    assert entity["entity_type"] == "person"
    assert entity["label"] == "Unknown Person"
    anomaly = webhook_service._build_test_event_data(WebhookEventType.ANOMALY_DETECTED)
    assert anomaly["anomaly_id"] == "test-anomaly-001"
    assert anomaly["zone_id"] == "driveway"
    assert anomaly["anomaly_type"] == "unusual_activity"
    assert anomaly["score"] == 0.87
    health = webhook_service._build_test_event_data(WebhookEventType.SYSTEM_HEALTH_CHANGED)
    assert health["component"] == "ai-yolo26"
    assert health["status"] == "degraded"
    assert health["message"] == "High latency detected"

def test_build_test_event_data_unmapped_event_returns_base_only(webhook_service):
    """UNVERIFIED - not yet run red/green. BATCH_ANALYSIS_STARTED is in the enum but
    absent from the lookup table: must merge {} (no raise, no None)."""
    data = webhook_service._build_test_event_data(WebhookEventType.BATCH_ANALYSIS_STARTED)
    assert data["test"] is True
    assert set(data) == {"test", "timestamp"}
```

### D2 — kills cluster #2 query-build (45, incl. every `get_webhook(db, None)` member) + #15 or-default `get_deliveries` member

```python
def _sql(stmt):
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))

@pytest.mark.asyncio
async def test_query_builders_filter_order_and_page(webhook_service, mock_db_session, sample_webhook):
    """UNVERIFIED - not yet run red/green. Captures every statement handed to
    db.execute() and pins id/equality predicates, enabled filter, ORDER BY, LIMIT/OFFSET,
    and the `or 0` count fallback. Kills select(None)/where(None)/!=/is_(False/None)/
    order_by(None)/limit|offset(None)/get_webhook(db, None)/scalar() or 1."""
    wid = sample_webhook.id
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_webhook
    count_result = MagicMock()
    count_result.scalar.return_value = 0          # zero-count path for `or 0`
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    page_result = MagicMock()
    page_result.scalars.return_value = mock_scalars

    mock_db_session.execute = AsyncMock(side_effect=[mock_result, mock_result, mock_result,
                                                     mock_result, count_result, page_result])
    await webhook_service.get_webhook(mock_db_session, wid)
    await webhook_service.list_webhooks(mock_db_session, enabled_only=True)
    await webhook_service.list_webhooks(mock_db_session, enabled_only=False)
    await webhook_service.get_delivery(mock_db_session, wid)
    deliveries, total = await webhook_service.get_deliveries(mock_db_session, wid, limit=50, offset=0)

    stmts = [c.args[0] for c in mock_db_session.execute.call_args_list]
    get_sql, on_sql, off_sql, getd_sql, cnt_sql, page_sql = [_sql(s) for s in stmts]
    assert "outbound_webhooks" in get_sql and wid in get_sql and "!=" not in get_sql
    assert "enabled IS true" in on_sql.lower()
    assert " WHERE " not in off_sql.upper()          # enabled_only=False adds no filter
    assert "webhook_deliveries" in getd_sql and wid in getd_sql and "!=" not in getd_sql
    assert total == 0                                 # kills `scalar() or 1`
    assert "webhook_deliveries" in cnt_sql and wid in cnt_sql
    assert "LIMIT 50" in page_sql.upper() and "OFFSET 0" in page_sql.upper()
    assert "ORDER BY" in page_sql.upper() and "DESC" in page_sql.upper()
    assert "created_at" in page_sql
    # same id-equality contract via delete/update/test entry points (get_webhook(db, None) mutants)
    del_result = MagicMock()
    del_result.scalar_one_or_none.return_value = None
    mock_db_session.execute = AsyncMock(return_value=del_result)
    mock_db_session.delete = AsyncMock()
    await webhook_service.delete_webhook(mock_db_session, wid)
    sql = _sql(mock_db_session.execute.call_args.args[0])
    assert wid in sql, "delete must look up the webhook by the passed id"
```

### D3 — kills clusters #3 health-queries (40) + #14 health-boundary (6) + #15 or-default (5 health members)

```python
@pytest.mark.asyncio
async def test_health_summary_query_shapes_and_thresholds(webhook_service, mock_db_session):
    """UNVERIFIED - not yet run red/green. Pins each of the six aggregate statements
    (table, >=cutoff, status==SUCCESS/FAILED, avg, IS NOT NULL, enabled IS true),
    the `or 0` fallbacks (all-zero scalars), the >0/>=0.9/<0.5 health thresholds at the
    exact boundary rates .9/.5/.0, avg==0.0 truthiness, and +=1 counters."""
    def canned(value):
        r = MagicMock()
        r.scalar.return_value = value
        return r
    mock_db_session.execute = AsyncMock(side_effect=[
        canned(0), canned(0), canned(0), canned(0), canned(0), canned(0.0),
    ])
    webhooks = [
        MagicMock(total_deliveries=100, successful_deliveries=95),   # .95 healthy
        MagicMock(total_deliveries=100, successful_deliveries=90),   # .90 healthy (>= boundary)
        MagicMock(total_deliveries=100, successful_deliveries=50),   # .50 neither (< boundary)
        MagicMock(total_deliveries=100, successful_deliveries=45),   # .45 unhealthy
        MagicMock(total_deliveries=100, successful_deliveries=30),   # .30 unhealthy
        MagicMock(total_deliveries=0, successful_deliveries=0),      # skipped by >0
    ]
    with patch.object(webhook_service, "list_webhooks", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = webhooks
        summary = await webhook_service.get_health_summary(mock_db_session)

    stmts = [c.args[0] for c in mock_db_session.execute.call_args_list]
    sqls = [_sql(s) for s in stmts]
    total_sql, enabled_sql, deliv_sql, succ_sql, fail_sql, avg_sql = sqls
    assert "outbound_webhooks" in total_sql and "enabled" not in total_sql.lower().split("where", 1)[-1]
    assert "enabled IS true" in enabled_sql.lower()
    for s in (deliv_sql, succ_sql, fail_sql, avg_sql):
        assert "webhook_deliveries" in s
        assert ">=" in s, "24h cutoff comparison must be >="
    assert "SUCCESS" in succ_sql.upper() and "!=" not in succ_sql
    assert "FAILED" in fail_sql.upper() and "!=" not in fail_sql
    assert "AVG" in avg_sql.upper() and "IS NOT NULL" in avg_sql.upper()
    assert mock_list.call_args.args[0] is mock_db_session      # kills list_webhooks(None)
    assert summary.total_webhooks == 0 and summary.enabled_webhooks == 0
    assert summary.total_deliveries_24h == 0 and summary.successful_deliveries_24h == 0
    assert summary.failed_deliveries_24h == 0                  # kills `scalar() or 1`
    assert summary.healthy_webhooks == 2                       # >0.9 → 1, +=1→=1 → 1
    assert summary.unhealthy_webhooks == 2                     # <=0.5 → 3, =1 → 1
    assert summary.average_response_time_ms is None            # kills `if x or True` → 0.0
```

### D4 — kills clusters #4 delivery-record (34) + #8 stats (16) + #13 boundary300 (6) + #10 resp-fields (14) + #17 db-args (6)

```python
@pytest.mark.asyncio
async def test_delivery_record_fields_stats_and_status_boundary(
    webhook_service, mock_db_session, sample_webhook
):
    """UNVERIFIED - not yet run red/green. Pre-seeds counters (7/3) so `+=1`!=`=1`/`+=2`/`-=1`,
    asserts full WebhookDelivery construction (webhook_id/event_type/event_id/request_payload),
    db.add/db.refresh argument identity, last_delivery_at set, response body/time stored,
    HTTP 300 classified as success (301 not), and network errors truncated at exactly 500 chars."""
    sample_webhook.total_deliveries = 7
    sample_webhook.successful_deliveries = 3
    mock_db_session.flush = AsyncMock()
    mock_db_session.refresh = AsyncMock()

    with patch.object(webhook_service, "_send_request", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (300, "multi-choice", 42)   # 300 must count as success
        delivery = await webhook_service.deliver_webhook(
            mock_db_session, sample_webhook, WebhookEventType.ALERT_FIRED,
            {"alert_id": "a1"}, event_id="evt-9",
        )
    sent = mock_send.call_args.args
    assert sent[0] is sample_webhook
    assert sent[1]["event_type"] == "alert_fired"
    assert sent[1]["data"] == {"alert_id": "a1"}
    assert mock_db_session.add.call_args.args[0] is delivery            # kills db.add(None)
    assert mock_db_session.refresh.call_args.args[0] is delivery        # kills refresh(None)
    assert delivery.webhook_id == sample_webhook.id
    assert delivery.event_type == "alert_fired"
    assert delivery.event_id == "evt-9"
    assert delivery.status == WebhookDeliveryStatus.SUCCESS             # kills <=300/<301
    assert delivery.request_payload == sent[1]
    assert delivery.response_body == "multi-choice"
    assert delivery.response_time_ms == 42
    assert delivery.delivered_at is not None
    assert sample_webhook.total_deliveries == 8                          # kills =1/+=2/-=1
    assert sample_webhook.successful_deliveries == 4
    assert sample_webhook.last_delivery_at is not None

    with patch.object(webhook_service, "_send_request", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (301, "moved", 42)
        d301 = await webhook_service.deliver_webhook(
            mock_db_session, sample_webhook, WebhookEventType.ALERT_FIRED, {},
        )
    assert d301.status == WebhookDeliveryStatus.RETRYING                 # 301 is not success
    assert d301.status_code == 301
    assert d301.response_body == "moved" and d301.response_time_ms == 42

    with patch.object(webhook_service, "_send_request", new_callable=AsyncMock) as mock_send:
        mock_send.side_effect = httpx.RequestError("x" * 600)
        dnet = await webhook_service.deliver_webhook(
            mock_db_session, sample_webhook, WebhookEventType.ALERT_FIRED, {},
        )
    assert dnet.error_message == "x" * 500        # kills str(e)[:500]→[:501]
    assert sample_webhook.last_delivery_at is not None
```

### D5 — kills clusters #9 signature (14) + #18 post-args (5) + #23 hdrs-names (3) + #21 timing-formula (partial, `/1000`)

```python
@pytest.mark.asyncio
async def test_send_request_pins_url_json_headers_and_signature(webhook_service, sample_webhook):
    """UNVERIFIED - not yet run red/green. Asserts post() got webhook.url positionally and
    json=payload, exact default header names/values, and X-Webhook-Signature* equal a
    signature recomputed in-test via the service's own canonicalization (kills json
    sort_keys/separators tweaks, signature None, header key renames, timeout=None,
    and the /1000 timing formula via a realistic elapsed assertion)."""
    payload = {"zz": 1, "aa": {"y": 2, "b": 3}}
    expected_sig = webhook_service._sign_payload(payload, sample_webhook.signing_secret)
    with patch("httpx.AsyncClient", autospec=True) as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client
        _, _, ms = await webhook_service._send_request(sample_webhook, payload)

    assert mock_client_class.call_args.kwargs["timeout"] == DEFAULT_TIMEOUT
    call = mock_client.post.call_args
    assert call.args[0] == sample_webhook.url
    assert call.kwargs["json"] == payload
    headers = call.kwargs["headers"]
    assert headers["Content-Type"] == "application/json"
    assert headers["User-Agent"] == "NemotronWebhook/1.0"
    assert headers["X-Webhook-Signature"] == f"sha256={expected_sig}"
    assert headers["X-Webhook-Signature-256"] == expected_sig
    assert ms < 60_000        # /1000 formula under the mocked call is 0 ms, so also:
    assert ms >= 0
```
Note: `*1001` (`_send_request#112`) is only killable with a clock-injection seam; the realistic-elapsed assertion kills `/1000` in the same cluster; cluster #21 is therefore counted partially killed by D5.

### D6 — kills clusters #5 fmt-discord (30) + #6 fmt-teams (29) + #7 fmt-slack (18) + #12 int-routing (6) + #16 jinja-context (6) + #22 tw-body (3)

```python
def test_format_integrations_full_shape_and_routing(webhook_service):
    """UNVERIFIED - not yet run red/green. Routes through _format_for_integration for all
    four integration types and asserts the complete payload shapes: Slack blocks keys
    (type/text/mrkdwn), Discord embed field dicts (name/value/inline True, title-cased
    underscore replacement, payload timestamp, [:25] cap), Teams (@context, themeColor
    0076D7, summary, [:10] cap), generic passthrough, and missing-key fallbacks."""
    def wh(kind):
        return OutboundWebhook(id=str(uuid4()), name="T", url="https://x.test/hook",
                               event_types=["alert_fired"], integration_type=kind,
                               enabled=True, signing_secret="a" * 64,
                               total_deliveries=0, successful_deliveries=0)
    payload = {"event_type": "camera_motion", "timestamp": "TS",
               "data": {"zone_id": "driveway", "score": 0.5}}
    slack = webhook_service._format_for_integration(wh(IntegrationType.SLACK), payload)
    assert slack["text"].startswith("*camera_motion*")
    assert slack["blocks"] == [{"type": "section",
                                "text": {"type": "mrkdwn", "text": slack["text"]}}]
    missing = webhook_service._format_slack_payload({})
    assert missing["text"].startswith("*event*")            # kills XXeventXX/EVENT default
    discord = webhook_service._format_for_integration(wh(IntegrationType.DISCORD), payload)
    embed = discord["embeds"][0]
    assert embed["title"] == "Camera Motion"
    assert embed["timestamp"] == "TS"
    assert embed["fields"] == [{"name": "Zone Id", "value": "0.5", "inline": True}]
    wide = {"event_type": "e", "timestamp": "T", "data": {f"k{i}": i for i in range(26)}}
    assert len(webhook_service._format_discord_payload(wide)["embeds"][0]["fields"]) == 25
    teams = webhook_service._format_for_integration(wh(IntegrationType.TEAMS), payload)
    assert teams["@type"] == "MessageCard"
    assert teams["@context"] == "https://schema.org/extensions"
    assert teams["summary"] == "camera_motion"
    assert teams["themeColor"] == "0076D7"
    assert teams["title"] == "Camera Motion"
    assert teams["sections"][0]["facts"] == [{"title": "Zone Id", "value": "0.5"}]
    assert len(webhook_service._format_teams_payload(wide)["sections"][0]["facts"]) == 10
    generic = webhook_service._format_for_integration(wh(IntegrationType.GENERIC), payload)
    assert generic == payload

def test_build_payload_template_context_and_test_body(webhook_service):
    """UNVERIFIED - not yet run red/green. Template must receive event_type, webhook_id,
    timestamp (kills render-kwargs → None/dropped); test_webhook must pass response body through."""
    webhook = OutboundWebhook(id="WHID-1", name="T", url="https://x.test/hook",
                              event_types=["alert_fired"],
                              integration_type=IntegrationType.GENERIC, enabled=True,
                              payload_template='{"et":"{{ event_type }}","wid":"{{ webhook_id }}","ts":"{{ timestamp }}"}',
                              signing_secret="a" * 64, total_deliveries=0, successful_deliveries=0)
    payload = webhook_service._build_payload(webhook, WebhookEventType.ALERT_FIRED, {})
    assert payload["et"] == "alert_fired"
    assert payload["wid"] == "WHID-1"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T[0-9:.+]+", payload["ts"])

@pytest.mark.asyncio
async def test_test_webhook_returns_response_body(webhook_service, mock_db_session, sample_webhook):
    """UNVERIFIED - not yet run red/green. Success test previously ignored response_body."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_webhook
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    with patch.object(webhook_service, "_send_request", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (200, "pong", 5)
        result = await webhook_service.test_webhook(
            mock_db_session, sample_webhook.id, WebhookEventType.ALERT_FIRED)
    assert result.success is True
    assert result.response_body == "pong"          # kills `response_body=None` mutants
```
(`re` import must be added to the test file.)

**Clusters not covered by drafts** (remaining kill-work if the tier continues): #11 create-fields (8 — one added assert block in existing create test), #21 timing-formula `*1001` half, singleton #19 (2 — trivial: assert `isinstance(get_webhook_service(), WebhookService)` in a fresh-process test that resets `_WebhookServiceHolder.instance = None` first).

## Notes / judgment calls

- **EQ-strvalue (45)** is the single biggest equivalent class and is *provably* equivalent for all production inputs because both enums are `StrEnum` (`str(m) == m.value`, verified on this interpreter). If the baseline ever mutates these with a plain `Enum`, this reclassifies to TEST-GAP.
- **EQ-log (88)** contains the `extra=` dict mutations on `logger.warning/error` calls in `_handle_delivery_failure`/`deliver_webhook`/`trigger_webhook_background`: structlog-formatted extras are unobservable in the unit suite and asserting on them would osserve implementation, so EQUIVALENT rather than LOW-VALUE by the "nobody should assert this" rule.
- **LOW-auth-defaults (19)**: `get(k, "")` → `get(k, None)` renders `Bearer None` only when the key is missing, which the `WebhookAuthConfig` schema (fields default to `None`, `.get()` returns `None` → same `f"Bearer {token}"` as the "" case when model_dump yields None) makes hard to distinguish; the `"XXXX"`-default variants only differ on hand-crafted malformed dicts. Low value, not equivalent.
- **Cluster #2 vs SetupGuard caveat** (memory: `setup-guard-cache-poisoning`): the drafted D2 runs in the unit file with mocked sessions — no DB, no 503 poisoning risk.
