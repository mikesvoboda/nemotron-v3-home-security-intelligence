# WP4.4 triage dossier — backend/services/webhook_service.py

Surviving mutants: **158** of 1075 checked (770 not yet run). Diff source: `uv run mutmut show` per key
(captured in `/tmp/wp25/wp44-triage/webhook-diffs.txt`; every survivor anchored to a source line by
diff-hunk context — mapping at `/tmp/wp25/wp44-triage/assign.pkl`, placement at `placement.pkl`).

Cluster counts sum to 158 (±0). Full per-cluster key lists in Appendix A.

## Why 93 of 158 survivors are structurally unkillable by the current unit tests

The whole mutation run executes **unit tests only** (`pyproject.toml [tool.mutmut]
pytest_add_cli_args_test_selection = ["backend/tests/unit"]`). Every unit DB test passes an
`AsyncMock` session whose `execute` is stubbed (`backend/tests/conftest.py:1930 mock_db_session`), so
the SQLAlchemy statements the service builds are **never compiled or inspected**. Any mutant that
changes a statement's shape — `.where(...)` predicates, `.limit()/.offset()`, table/order args, or the
whole statement expression → `None` — produces identical return values under the mock and survives by
construction. Real-SQL coverage exists in `backend/tests/integration/test_webhook_service.py`
(`test_db` fixture), but that tree is not in the mutmut selection — hence the same functions have
integration tests that would kill some of these (e.g. `None`-statement mutants raise at execute) yet
count as survivors.

Test files that DO execute these functions (all unit, mock-session):
`backend/tests/unit/services/test_webhook_service.py` — lines 254/272 (`test_list_webhooks_*`),
408/427 (`test_delete_webhook_*`), 870 (`test_get_health_summary`), 934 (`test_get_deliveries`),
963 (`test_get_delivery`), 1050/1068/1087 (`test_format_{slack,discord,teams}_payload`).
Their assertions are loose: membership/`in` checks on partial output, `>=` on SQL-backed counts, and
zero assertion on the built query.

## Cluster table

| ID | Function : lines | Pattern (count) | Class | Kill plan |
|----|------------------|-----------------|-------|-----------|
| C1 | `_format_discord_payload` :985,986,993; `_format_teams_payload` :1020,1027 (13) | Formatter data/timestamp lookup broken or whole field-dict literal → `None`: `payload.get("data",{})`→`get(None,…)`, key-clobber, `get("data",None)`, `timestamp`→`None`, `fields.append({...})`→`append(None)` (Teams: `data`, facts dict) | TEST-GAP | `test_format_embed_shapes_and_timestamp` (Draft D1) — existing test builds the `data` dict but never reads `embeds[0]["fields"]` / `sections[0]["facts"]` |
| C2 | `_format_slack_payload` :966-969 (12) | Slack BlockKit structure keys/values (`"type":"section"`, outer `"text"` key, `"type":"mrkdwn"`, inner `"text":text`) clobbered | TEST-GAP | `test_format_slack_blockkit_structure` (Draft D2) — existing test asserts only `"blocks" in result` |
| C3 | `_format_discord_payload` :994-996,1004; `_format_teams_payload` :1028,1029 (19) | Field/fact entry rendering: key→value swaps, `"XX_XX"`/`"XX XX"` replace-args (titles come out snake_case/uppercase), `str(None)` value, `"inline":True`→`False`, `"timestamp"` key clobber | TEST-GAP | shared by Draft D1 (assert exact `fields`/`facts` dicts + `embeds[0]["timestamp"]`) |
| C4 | `_format_teams_payload` :1035-1037 (11) | Teams MessageCard protocol constants: `"@context"` value (`https://schema.org/extensions`) swapped, `"summary": event_type` key clobbered, `"themeColor":"0076D7"` key-case/value-case clobbered | TEST-GAP | `test_format_teams_messagecard_protocol` (Draft D3) — existing test never reads these three keys |
| C5 | `_format_discord_payload` :1005; `_format_teams_payload` :1041 (2) | Truncation caps off-by-one: `fields[:25]`→`[:26]`, `facts[:10]`→`[:11]` (documented Discord limit) | TEST-GAP | `test_format_field_and_fact_caps` (Draft D4) |
| C6 | `_format_{slack,discord,teams}_payload` :953-954,984-986,1019-1020 (20) | Fallback defaults + redundant-key mutants: `get("event_type","event")` tweaks (×12), `get(…, None)`/bare-get (×7), `get("timestamp", default)`→`get(default)` (1). `_build_payload` (:~864-869) **always** emits `event_type`/`data`/`timestamp`, and the only reachable caller path passes it that payload → defaults unreachable; bare-get returns the same present key | EQUIVALENT | none — dead defensive tweaks under the real call contract |
| H1 | `get_health_summary` :716,720,730,737,749,762,773 (14) | Whole `db.execute(…)` statement arg → `None` / `select(None)` / `func.count()`→`func.avg(None)` (aggregate args); mock `execute` ignores the arg, `MagicMock.scalar()` returns the canned value | TEST-GAP (mock-blind) | `test_get_health_summary_builds_expected_queries` (Draft D5) — capture-and-compile; integration tests would also kill most (attribute access on `None` raises) but are outside selection |
| H2 | `get_health_summary` :722 (3) | Enabled-filter predicate weakened: `.where(None)`, `enabled.is_(None)`, `enabled.is_(False)` | TEST-GAP | Draft D5 |
| H3 | `get_health_summary` :727 (2) | 24h window sign/width: `utc_now() - timedelta(hours=24)` → `+ 24h` (future cutoff!) / `25h` | TEST-GAP | Draft D5 + integration Draft D9 (out-of-window delivery must be excluded) |
| H4 | `get_health_summary` :732,740-742,752-754,763-765 (22) | `and_(...)` clauses / whole `.where()` → `None`, clause removed, `created_at >= cutoff`→`> cutoff` (23/24 boundary), `status == SUCCESS/FAILED`→`!=` (flips success vs failed counts) | TEST-GAP | Draft D5 + Draft D9 |
| H5 | `get_health_summary` :717,724,734,746,758; `get_deliveries` :822 (6) | `scalar() or 0` → `scalar() or 1` — fires whenever a count query returns 0/NULL, i.e. every empty-table first-run deployment: summary reports 1 webhook/delivery that does not exist | TEST-GAP | `test_get_health_summary_empty_database_reports_zeros` (Draft D7) + `test_get_deliveries_empty_history_returns_zero_total` (Draft D8) |
| H6 | `get_health_summary` :778,780,781,782,783 (5) | Health classification: `total_deliveries > 0`→`> 1` (1-delivery webhook unclassified), `>= 0.9`→`> 0.9` (exactly-90% lost), `< 0.5`→`<= 0.5` (exactly-50% wrongly unhealthy), `+= 1`→`= 1` (multi-webhook counts collapse) | TEST-GAP | `test_get_health_summary_classifies_success_rate_boundaries` (Draft D6) |
| H7 | `get_health_summary` :793 (1) | Truthiness guard `if avg_response_time else None` → `if avg_response_time or True else None` — always-truthy branch; with `avg = 0` the original yields `None`, mutant yields `0.0` | TEST-GAP | Draft D6 (patched `list_webhooks` + avg scalar 0 → assert `average_response_time_ms is None`) |
| D1 | `get_deliveries` :818,820,826-830 (11) | Per-webhook isolation + paging: `webhook_id == → !=` (and whole clause/`.where()`/statement → `None` — leak every webhook's history), `.limit(None)` (cap lost), `.offset(None)`, `.order_by(None)` (recency sort lost) | TEST-GAP | `test_get_deliveries_filters_sorts_and_pages` (Draft D8) + integration Draft D9 |
| D2 | `get_delivery` :852 (4) | ID lookup predicate `id == delivery_id` → `!=` (returns the wrong delivery when several exist), clause/statement → `None` | TEST-GAP | `test_get_delivery_selects_by_id` (Draft D11) |
| W1 | `list_webhooks` :199,201,203,204 (7) | `enabled_only` filter dropped/inverted (`.where(None)`, `is_(None)`, `is_(False)`), order → `None`, statement → `None`/`select(None)` | TEST-GAP | `test_list_webhooks_query_construction` (Draft D10) + integration `test_list_enabled_webhooks_only` (outside selection) |
| W2 | `delete_webhook` :309 (1) | `await self.get_webhook(db, webhook_id)` → `get_webhook(db, None)` — the lookup key is lost: on a real DB the delete targets nothing → returns False while the webhook survives; mock hides it | TEST-GAP | `test_delete_webhook_looks_up_by_given_id` (Draft D12) — assert `webhook_id == …` (not `IS NULL`) in the executed SQL |
| W3 | `delete_webhook` :317-318 (5) | Audit-log only: log message f-string → `None`, `extra={"webhook_id": …}` removed/clobbered | LOW-VALUE | optional Draft D13 (caplog) — deletion behaviour unchanged; log identity matters for audit trail only |

**Totals: TEST-GAP 133 / EQUIVALENT 20 / LOW-VALUE 5 = 158.**

## Drafted tests (highest-value clusters)

All in `backend/tests/unit/services/test_webhook_service.py`, following its existing
Arrange/Act/Assert + `mock_db_session` style. **Each marked UNVERIFIED — not yet run red/green.**
TDD procedure (same for all): apply the draft, run it against the ORIGINAL module (must be GREEN),
then against each cluster mutant copy (assertion must go RED on every key in the cluster);
`uv run pytest <target>::<test> -p no:randomly` both ways.

### D1 — kills C1 + C3 (13 + 19 mutants): assert full embed/fact rendering
```python
def test_format_embed_shapes_and_timestamp(webhook_service):
    """Discord fields / Teams facts must carry humanized titles, stringified values and the payload timestamp."""
    # Arrange
    payload = {
        "event_type": "alert_fired",
        "timestamp": "2024-01-01T00:00:00Z",
        "data": {"alert_id": "evt-123", "severity": "high", "count": 3, "debug_id": None},
    }

    # Act
    discord = webhook_service._format_discord_payload(payload)
    teams = webhook_service._format_teams_payload(payload)

    # Assert - Discord embed shape: snake_case keys humanized, all values stringified
    embed = discord["embeds"][0]
    assert embed["title"] == "Alert Fired"
    assert embed["timestamp"] == "2024-01-01T00:00:00Z"
    assert embed["fields"] == [
        {"name": "Alert Id", "value": "evt-123", "inline": True},
        {"name": "Severity", "value": "high", "inline": True},
        {"name": "Count", "value": "3", "inline": True},
    ]

    # Assert - Teams facts shape: same keys rendered as title/value facts
    facts = teams["sections"][0]["facts"]
    assert facts == [
        {"title": "Alert Id", "value": "evt-123"},
        {"title": "Severity", "value": "high"},
        {"title": "Count", "value": "3"},
    ]
```
Kills: C1 `data`→None/None-default/`get(None)`/key-clobber and `append(None)` (fields/facts become
`[]` or `[None]`), C1 timestamp mutants (`embed["timestamp"]` None / key swap → KeyError), C3
`XX_XX`/`XX XX` replace-args (names stay `Alert_Id`/`ALERT ID`), key/value swaps, `str(None)`,
`inline: False`, `"XXtimestampXX"` KeyError.

### D2 — kills C2 (12 mutants): Slack BlockKit exact structure
```python
def test_format_slack_blockkit_structure(webhook_service):
    """Slack payload must expose blocks[0] as an exact section/mrkdwn block mirroring the text."""
    # Arrange
    payload = {
        "event_type": "alert_fired",
        "data": {"alert_id": "test-123", "severity": "high"},
    }

    # Act
    result = webhook_service._format_slack_payload(payload)

    # Assert
    assert result["blocks"] == [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": result["text"]},
        }
    ]
    assert result["text"].startswith("*alert_fired*")
    assert "- alert_id: test-123" in result["text"]
```
Kills every C2 key-clobber (`"XXtypeXX"`, `"TYPE"`, `"XXtextXX"`, `"TEXT"`) and value mutation
(`"XXsectionXX"`, `"SECTION"`, `"XXmrkdwnXX"`, `"MRKDWN"`) via exact dict equality.

### D3 — kills C4 (11 mutants): Teams MessageCard protocol constants
```python
def test_format_teams_messagecard_protocol(webhook_service):
    """Teams payload must be a valid MessageCard: schema.org context, event summary, blue theme color."""
    # Arrange
    payload = {"event_type": "anomaly_detected", "data": {}}

    # Act
    result = webhook_service._format_teams_payload(payload)

    # Assert - protocol constants the Teams connector validates
    assert result["@context"] == "https://schema.org/extensions"
    assert result["summary"] == "anomaly_detected"
    assert result["themeColor"] == "0076D7"
```
Kills `"XX@contextXX"`/`"@CONTEXT"` KeyErrors, value swaps, summary key-clobbers, and all five
`themeColor` variants (`themecolor`, `THEMECOLOR`, `XX0076D7XX`, `0076d7`).

### D5 — kills H1 + H2 + H3 + H4 (41 mutants): assert the compiled SQL, not just the return
```python
@pytest.mark.asyncio
async def test_get_health_summary_builds_expected_queries(webhook_service, mock_db_session):
    """get_health_summary must execute real aggregate queries: counts, enabled filter, 24h window, status filters."""
    # Arrange
    def scalar_result(value):
        result = MagicMock()
        result.scalar.return_value = value
        return result

    mock_db_session.execute = AsyncMock(
        side_effect=[
            scalar_result(5),   # total webhooks
            scalar_result(4),   # enabled webhooks
            scalar_result(10),  # deliveries 24h
            scalar_result(8),   # successful 24h
            scalar_result(2),   # failed 24h
            scalar_result(120.5),  # avg response time
        ]
    )
    cutoff = utc_now() - timedelta(hours=24)

    # Act
    with patch.object(webhook_service, "list_webhooks", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = []
        summary = await webhook_service.get_health_summary(mock_db_session)

    # Assert
    assert summary.total_webhooks == 5
    stmts = [call.args[0] for call in mock_db_session.execute.await_args_list]
    sqls = [str(s) for s in stmts]
    assert len(sqls) == 6
    mock_list.assert_awaited_once_with(mock_db_session)  # kills get_health_summary__mutmut_71 (list_webhooks(None))

    assert "FROM outbound_webhooks" in sqls[0]
    assert "count" in sqls[0].lower()

    assert "outbound_webhooks.enabled IS true" in sqls[1]  # .where(None)/is_(None)/is_(False) land here

    assert "FROM webhook_deliveries" in sqls[2]
    assert "webhook_deliveries.created_at >= :" in sqls[2]  # > cutoff or dropped clause fail

    assert "webhook_deliveries.status = :" in sqls[3]  # != renders "status != :"
    assert "webhook_deliveries.created_at >= :" in sqls[3]

    assert "webhook_deliveries.status = :" in sqls[4]
    assert "webhook_deliveries.created_at >= :" in sqls[4]

    assert "avg(webhook_deliveries.response_time_ms)" in sqls[5]  # func.avg(None) has no column
    assert "webhook_deliveries.response_time_ms IS NOT NULL" in sqls[5]

    # 24h window is a PAST cutoff ~24h back: kills the +24h (future) and 25h mutants via bind params
    window_param = next(
        v for k, v in stmts[2].compile().params.items() if k.startswith("created_at")
    )
    assert window_param < utc_now()  # +24h mutant is in the future
    assert abs((window_param - (utc_now() - timedelta(hours=24))).total_seconds()) < 5  # 25h mutant misses

    # the three windowed count queries share the same >= : cutoff predicate shape
    assert sqls[2].count("created_at >= :") == 1
```
Kills: all 14 H1 (statement → `None` renders `"None"`; `select(None)` lacks `FROM …` — or raises at
construction, which also kills), all 3 H2 (no `enabled IS true`), both H3 (`+24h` param is future;
`25h` param misses the ±5s window), and H4 predicate mutants (`==`→`!=` renders `status != :`,
dropped clauses / whole `.where()` / `and_(…)` → `None` remove the predicate text, `>=`→`>` renders
`created_at > :`). All renderings verified against SQLAlchemy string output:
`'... WHERE webhook_deliveries.created_at >= :created_at_1 AND webhook_deliveries.status = :status_1'`,
enabled filter renders `enabled IS true`, `compile().params` carries the cutoff datetime.

### D6 — kills H6 + H7 (6 mutants): success-rate boundary classification + avg guard
```python
@pytest.mark.asyncio
async def test_get_health_summary_classifies_success_rate_boundaries(webhook_service, mock_db_session):
    """Exactly-90% must be healthy, exactly-50% must NOT be unhealthy, zero-delivery/webhook with 1 delivery counted."""
    # Arrange
    def scalar_result(value):
        result = MagicMock()
        result.scalar.return_value = value
        return result

    mock_db_session.execute = AsyncMock(
        side_effect=[
            scalar_result(5), scalar_result(5), scalar_result(0),
            scalar_result(0), scalar_result(0), scalar_result(0),  # avg == 0
        ]
    )
    webhooks = [
        MagicMock(total_deliveries=10, successful_deliveries=9),   # 90% -> healthy (>= 0.9 boundary)
        MagicMock(total_deliveries=10, successful_deliveries=5),   # 50% -> neither (< 0.5 boundary)
        MagicMock(total_deliveries=1, successful_deliveries=1),    # 100% -> healthy (total > 0 boundary)
        MagicMock(total_deliveries=1, successful_deliveries=0),    # 0% -> unhealthy (total > 0 boundary)
        MagicMock(total_deliveries=2, successful_deliveries=2),    # 100% -> healthy (kills `healthy_count = 1`)
        MagicMock(total_deliveries=2, successful_deliveries=0),    # 0% -> unhealthy (kills `unhealthy_count = 1`)
    ]

    # Act
    with patch.object(webhook_service, "list_webhooks", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = webhooks
        summary = await webhook_service.get_health_summary(mock_db_session)

    # Assert
    assert summary.healthy_webhooks == 3    # 90%, 100% (1 delivery), 100% (2 deliveries)
    assert summary.unhealthy_webhooks == 2  # 0% (1 delivery), 0% (2 deliveries); 50% stays out
    # avg scalar 0 is falsy -> original yields None; `or True` mutant yields 0.0
    assert summary.average_response_time_ms is None
```
Kills `> 0.9` (healthy 2≠3), `<= 0.5` (unhealthy 3≠2), `total_deliveries > 1` (2≠3 / 1≠2),
`healthy_count = 1`, `unhealthy_count = 1`, and the H7 `or True` guard (`0.0` ≠ `None`).
(The `placeholder overwritten below` line should be cleaned to build the list in one literal — keep
or fix before committing; behaviour unchanged.)

### D7 + D8 — kill H5 (6 mutants): empty-table `or 0` fallback
```python
@pytest.mark.asyncio
async def test_get_health_summary_empty_database_reports_zeros(webhook_service, mock_db_session):
    """Counts that come back 0 (empty tables on first run) must surface as 0, not 1."""
    # Arrange — every scalar() returns 0, as an empty table's COUNT(*) does
    mock_db_session.execute = AsyncMock(side_effect=[MagicMock(scalar=MagicMock(return_value=0)) for _ in range(6)])

    # Act
    with patch.object(webhook_service, "list_webhooks", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = []
        summary = await webhook_service.get_health_summary(mock_db_session)

    # Assert
    assert summary.total_webhooks == 0
    assert summary.enabled_webhooks == 0
    assert summary.total_deliveries_24h == 0
    assert summary.successful_deliveries_24h == 0
    assert summary.failed_deliveries_24h == 0


@pytest.mark.asyncio
async def test_get_deliveries_empty_history_returns_zero_total(webhook_service, mock_db_session, sample_webhook):
    """A webhook with no deliveries must report total == 0."""
    # Arrange
    count_result = MagicMock()
    count_result.scalar.return_value = 0
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    deliveries_result = MagicMock()
    deliveries_result.scalars.return_value = mock_scalars
    mock_db_session.execute = AsyncMock(side_effect=[count_result, deliveries_result])

    # Act
    deliveries, total = await webhook_service.get_deliveries(mock_db_session, sample_webhook.id)

    # Assert
    assert deliveries == []
    assert total == 0
```
(`scalar_result` helper defined in D5/D6 is local to each test — duplicate it per test or hoist a
module-level helper at commit time.)

### D4 — kills C5 (2 mutants): Discord 25 / Teams 10 truncation caps
```python
def test_format_field_and_fact_caps(webhook_service):
    """Discord embeds cap at 25 fields, Teams cards at 10 facts (documented limits)."""
    # Arrange - 30 scalar data entries
    payload = {"event_type": "alert_fired", "data": {f"key_{i}": i for i in range(30)}}

    # Act
    discord = webhook_service._format_discord_payload(payload)
    teams = webhook_service._format_teams_payload(payload)

    # Assert
    assert len(discord["embeds"][0]["fields"]) == 25
    assert len(teams["sections"][0]["facts"]) == 10
    # and the LAST kept entry is the 25th/10th in insertion order
    assert discord["embeds"][0]["fields"][24]["value"] == "24"
    assert teams["sections"][0]["facts"][9]["value"] == "9"
```

### D9 — (integration companion) real-DB kills for H3/H4/D1 boundary clauses
`backend/tests/integration/test_webhook_service.py` currently asserts only `total >= 1` /
`health.total_deliveries_24h >= 0`. Extending it (or a WP4.5 mutmut scope that adds
`backend/tests/integration`) kills the window/status/paging predicate mutants at the SQL level —
sketched here, needs `test_db` fixtures from that file:
```python
@pytest.mark.asyncio
async def test_get_deliveries_and_health_filter_by_window_status_and_page(
    self, test_db, webhook_service: WebhookService, sample_webhook_data: WebhookCreate
) -> None:
    """Second webhook's deliveries never leak; limit/offset/DESC order are exact; health counts stay consistent."""
    async with test_db() as session:
        hook_a = await webhook_service.create_webhook(session, sample_webhook_data)
        hook_b = await webhook_service.create_webhook(session, sample_webhook_data)
        rows = []
        for i in range(3):  # inserted OLDEST-first, so un-ordered output != DESC output
            row = WebhookDelivery(
                id=str(uuid4()), webhook_id=hook_a.id, event_type="alert_fired",
                status=WebhookDeliveryStatus.SUCCESS,
                created_at=utc_now() + timedelta(minutes=i),
            )
            session.add(row)
            rows.append(row)
        session.add(WebhookDelivery(  # second webhook - must never appear in hook_a history
            id=str(uuid4()), webhook_id=hook_b.id, event_type="alert_fired",
            status=WebhookDeliveryStatus.FAILED, created_at=utc_now(),
        ))
        await session.commit()

    async with test_db() as session:
        page, total = await webhook_service.get_deliveries(session, hook_a.id, limit=2, offset=0)
        assert total == 3                                 # kills webhook_id !=/clause removal (4/4 leak)
        assert [d.id for d in page] == [rows[2].id, rows[1].id]  # kills limit(None) & order(None)
        tail, _ = await webhook_service.get_deliveries(session, hook_a.id, limit=5, offset=2)
        assert [d.id for d in tail] == [rows[0].id]       # kills offset(None)
        health = await webhook_service.get_health_summary(session)
        assert health.total_deliveries_24h == 4
        assert health.successful_deliveries_24h == 3
        assert health.failed_deliveries_24h == 1           # kills status ==/!= flips
```
Not in mutmut's unit-only selection today — schedule when integration enters the scope; it
otherwise permanently protects H3/H4/D1 boundary mutants.

### D10 — kills W1 (7 mutants): list_webhooks query construction
```python
@pytest.mark.asyncio
async def test_list_webhooks_query_construction(webhook_service, mock_db_session, sample_webhook):
    """enabled_only must add an enabled IS true filter; results always ordered newest-first."""
    # Arrange
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [sample_webhook]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    # Act
    await webhook_service.list_webhooks(mock_db_session, enabled_only=False)
    await webhook_service.list_webhooks(mock_db_session, enabled_only=True)

    # Assert - one execute per call, both real queries over outbound_webhooks
    assert mock_db_session.execute.await_count == 2
    all_sql, enabled_sql = (str(c.args[0]) for c in mock_db_session.execute.await_args_list)
    assert "FROM outbound_webhooks" in all_sql
    assert "ORDER BY outbound_webhooks.created_at DESC" in all_sql  # order_by(None) mutant drops this
    assert "ORDER BY outbound_webhooks.created_at DESC" in enabled_sql
    assert "outbound_webhooks.enabled IS true" in enabled_sql       # kills is_(None)/is_(False)/.where(None)
    assert " WHERE " not in all_sql  # enabled_only=False must not filter (clobbered predicate would add one)
```
Kills `select(None)`/whole-query `None` (render `"None"`), `.where(None)`/`is_(None)`/`is_(False)`
(no `enabled IS true`), `.order_by(None)`/`query = None` (no ORDER BY / FROM), and
`db.execute(None)` (captured arg renders `"None"`).

### D11 — kills D2 (4 mutants): get_delivery selects the right row
```python
@pytest.mark.asyncio
async def test_get_delivery_selects_by_id(webhook_service, mock_db_session):
    """The executed query must filter webhook_deliveries.id on the requested delivery_id."""
    # Arrange
    delivery_id = str(uuid4())
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = MagicMock(id=delivery_id)
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    # Act
    result = await webhook_service.get_delivery(mock_db_session, delivery_id)

    # Assert
    sql = str(mock_db_session.execute.await_args.args[0])
    assert "FROM webhook_deliveries" in sql
    assert "webhook_deliveries.id = " in sql        # kills id != / where(None) / None statement
    assert f"'{delivery_id}'" in str(mock_db_session.execute.await_args.args[0].compile(
        compile_kwargs={"literal_binds": True}
    ))
    assert result.id == delivery_id
```

### D12 — kills W2 (1 mutant): delete looks up the id it was given
```python
@pytest.mark.asyncio
async def test_delete_webhook_looks_up_by_given_id(webhook_service, mock_db_session, sample_webhook):
    """delete_webhook must fetch the row by the webhook_id argument, not NULL."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_webhook
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    mock_db_session.delete = AsyncMock()
    mock_db_session.flush = AsyncMock()

    # Act
    assert await webhook_service.delete_webhook(mock_db_session, sample_webhook.id) is True

    # Assert - lookup query binds the passed id; mutant binds NULL
    lookup = mock_db_session.execute.await_args.args[0]
    assert "outbound_webhooks.id = " in str(lookup)
    rendered = str(lookup.compile(compile_kwargs={"literal_binds": True}))
    assert f"'{sample_webhook.id}'" in rendered
    assert "IS NULL" not in rendered
```

### D13 — kills W3 (5 mutants, optional — LOW-VALUE cluster): deletion audit log
```python
@pytest.mark.asyncio
async def test_delete_webhook_logs_webhook_id(webhook_service, mock_db_session, sample_webhook, caplog):
    """Deletion must emit an INFO log carrying the webhook_id in the audit extra."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_webhook
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    mock_db_session.delete = AsyncMock()
    mock_db_session.flush = AsyncMock()

    # Act
    with caplog.at_level("INFO", logger="backend.services.webhook_service"):
        assert await webhook_service.delete_webhook(mock_db_session, sample_webhook.id) is True

    # Assert
    records = [r for r in caplog.records if "Deleted webhook" in r.getMessage()]
    assert len(records) == 1
    assert records[0].webhook_id == sample_webhook.id
```
(caplog relies on the app logger propagating to root — check at red/green time; if the app's
handlers swallow propagation, assert on the record via a `logging.Handler` attached with
`caplog.handler` semantics instead.)

## Covering-test references
- Unit (mutmut selection): `backend/tests/unit/services/test_webhook_service.py` — `test_get_health_summary` :870, `test_get_deliveries` :934, `test_get_delivery` :963, `test_list_webhooks_*` :254/:272, `test_delete_webhook_*` :408/:427, `test_format_slack/discord/teams_payload` :1050/:1068/:1087. Shared mock: `backend/tests/conftest.py:1930`.
- Integration (executes same funcs but OUTSIDE `pytest_add_cli_args_test_selection`): `backend/tests/integration/test_webhook_service.py` — `test_list_enabled_webhooks_only` :130, `test_delete_webhook` :207, `test_health_summary_returns_stats` :385 (only `>=` bounds), `test_get_deliveries_returns_history` :465 (only `total >= 1`).

## Appendix A — full survivor key lists (short keys; full form `backend.services.webhook_service.xǁWebhookServiceǁ<key>`)
**C1-fmt-dropcontent** (13): _format_discord_payload__mutmut_11, _format_discord_payload__mutmut_15, _format_discord_payload__mutmut_16, _format_discord_payload__mutmut_17, _format_discord_payload__mutmut_18, _format_discord_payload__mutmut_20, _format_discord_payload__mutmut_22, _format_discord_payload__mutmut_23, _format_discord_payload__mutmut_25, _format_teams_payload__mutmut_11, _format_teams_payload__mutmut_15, _format_teams_payload__mutmut_16, _format_teams_payload__mutmut_18

**C2-slack-blockkit** (12): _format_slack_payload__mutmut_24, _format_slack_payload__mutmut_25, _format_slack_payload__mutmut_26, _format_slack_payload__mutmut_27, _format_slack_payload__mutmut_28, _format_slack_payload__mutmut_29, _format_slack_payload__mutmut_30, _format_slack_payload__mutmut_31, _format_slack_payload__mutmut_32, _format_slack_payload__mutmut_33, _format_slack_payload__mutmut_34, _format_slack_payload__mutmut_35

**C3-fmt-rendering** (19): _format_discord_payload__mutmut_26, _format_discord_payload__mutmut_27, _format_discord_payload__mutmut_32, _format_discord_payload__mutmut_33, _format_discord_payload__mutmut_34, _format_discord_payload__mutmut_35, _format_discord_payload__mutmut_36, _format_discord_payload__mutmut_37, _format_discord_payload__mutmut_38, _format_discord_payload__mutmut_39, _format_discord_payload__mutmut_50, _format_discord_payload__mutmut_51, _format_teams_payload__mutmut_19, _format_teams_payload__mutmut_20, _format_teams_payload__mutmut_25, _format_teams_payload__mutmut_26, _format_teams_payload__mutmut_27, _format_teams_payload__mutmut_28, _format_teams_payload__mutmut_29

**C4-teams-protocol** (11): _format_teams_payload__mutmut_35, _format_teams_payload__mutmut_36, _format_teams_payload__mutmut_37, _format_teams_payload__mutmut_38, _format_teams_payload__mutmut_39, _format_teams_payload__mutmut_40, _format_teams_payload__mutmut_41, _format_teams_payload__mutmut_42, _format_teams_payload__mutmut_43, _format_teams_payload__mutmut_44, _format_teams_payload__mutmut_45

**C5-fmt-caps** (2): _format_discord_payload__mutmut_54, _format_teams_payload__mutmut_58

**C6-fmt-deaddefaults** (20): _format_discord_payload__mutmut_3, _format_discord_payload__mutmut_5, _format_discord_payload__mutmut_8, _format_discord_payload__mutmut_9, _format_discord_payload__mutmut_12, _format_discord_payload__mutmut_14, _format_discord_payload__mutmut_19, _format_discord_payload__mutmut_21, _format_slack_payload__mutmut_3, _format_slack_payload__mutmut_5, _format_slack_payload__mutmut_8, _format_slack_payload__mutmut_9, _format_slack_payload__mutmut_12, _format_slack_payload__mutmut_14, _format_teams_payload__mutmut_3, _format_teams_payload__mutmut_5, _format_teams_payload__mutmut_8, _format_teams_payload__mutmut_9, _format_teams_payload__mutmut_12, _format_teams_payload__mutmut_14

**H1-health-stmt-none** (14): get_health_summary__mutmut_2, get_health_summary__mutmut_4, get_health_summary__mutmut_9, get_health_summary__mutmut_12, get_health_summary__mutmut_23, get_health_summary__mutmut_26, get_health_summary__mutmut_32, get_health_summary__mutmut_35, get_health_summary__mutmut_46, get_health_summary__mutmut_49, get_health_summary__mutmut_60, get_health_summary__mutmut_62, get_health_summary__mutmut_63, get_health_summary__mutmut_71

**H2-health-enabled** (3): get_health_summary__mutmut_10, get_health_summary__mutmut_13, get_health_summary__mutmut_14

**H3-health-cutoff** (2): get_health_summary__mutmut_19, get_health_summary__mutmut_21

**H4-health-preds** (22): get_health_summary__mutmut_24, get_health_summary__mutmut_27, get_health_summary__mutmut_33, get_health_summary__mutmut_36, get_health_summary__mutmut_37, get_health_summary__mutmut_38, get_health_summary__mutmut_39, get_health_summary__mutmut_40, get_health_summary__mutmut_41, get_health_summary__mutmut_47, get_health_summary__mutmut_50, get_health_summary__mutmut_51, get_health_summary__mutmut_52, get_health_summary__mutmut_53, get_health_summary__mutmut_54, get_health_summary__mutmut_55, get_health_summary__mutmut_61, get_health_summary__mutmut_64, get_health_summary__mutmut_65, get_health_summary__mutmut_66, get_health_summary__mutmut_67, get_health_summary__mutmut_68

**H5-or-zero-to-one** (6): get_deliveries__mutmut_9, get_health_summary__mutmut_7, get_health_summary__mutmut_17, get_health_summary__mutmut_30, get_health_summary__mutmut_44, get_health_summary__mutmut_58

**H6-health-thresholds** (5): get_health_summary__mutmut_77, get_health_summary__mutmut_80, get_health_summary__mutmut_82, get_health_summary__mutmut_85, get_health_summary__mutmut_87

**H7-health-avgguard** (1): get_health_summary__mutmut_107

**D1-deliveries-query** (11): get_deliveries__mutmut_2, get_deliveries__mutmut_3, get_deliveries__mutmut_5, get_deliveries__mutmut_6, get_deliveries__mutmut_11, get_deliveries__mutmut_12, get_deliveries__mutmut_13, get_deliveries__mutmut_14, get_deliveries__mutmut_15, get_deliveries__mutmut_16, get_deliveries__mutmut_17

**D2-getdelivery-query** (4): get_delivery__mutmut_2, get_delivery__mutmut_3, get_delivery__mutmut_4, get_delivery__mutmut_5

**W1-list-query** (7): list_webhooks__mutmut_2, list_webhooks__mutmut_4, list_webhooks__mutmut_5, list_webhooks__mutmut_6, list_webhooks__mutmut_7, list_webhooks__mutmut_8, list_webhooks__mutmut_10

**W2-delete-lookup** (1): delete_webhook__mutmut_3

**W3-delete-log** (5): delete_webhook__mutmut_9, delete_webhook__mutmut_10, delete_webhook__mutmut_12, delete_webhook__mutmut_13, delete_webhook__mutmut_14