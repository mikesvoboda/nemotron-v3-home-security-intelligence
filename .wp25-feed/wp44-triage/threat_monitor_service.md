# WP4.4 Triage Dossier — backend/services/threat_monitor_service.py

**Run**: WP4.3 meta (mutants/backend/services/threat_monitor_service.py.meta), triaged 2026-09-17.
**Mutants**: 362 total - 118 killed - **244 survived** (0 unchecked).
**Diffs**: `uv run mutmut show <key>` for all 244 (0 failures, ~170s). Full key prefix
`backend.services.threat_monitor_service.xǁThreatMonitorServiceǁ` - example keys below are
abbreviated as `<fn>__mutmut_<n>` (append that prefix to recover the full key).
**Covering test file (all functions)**: `backend/tests/unit/services/test_threat_monitor_service.py`
(Coverage set per-function: only file listed in mutmut-stats.json `tests_by_mangled_function_name`.)

| Test region | Lines |
| --- | --- |
| TestThreatMonitorServiceAutoCreateAlert | :265-387 |
| TestThreatMonitorServiceConfidenceThreshold | :394-486 |
| TestThreatMonitorServiceMultipleWeapons | :493-633 |
| TestThreatMonitorServiceWebSocketBroadcast | :640-688 |
| TestThreatMonitorServiceAlertEngineIntegration (cooldown) | :694-755 |
| TestThreatMonitorServiceEdgeCases | :811-931 |

## Why the survivor pile is so deep (root causes)

1. **The DB is a canned-answer mock.** Every test stubs `session.execute` (or leaves it default).
   `_check_cooldown` builds a real SQLAlchemy `select(...)` and executes it against a mock that
   ignores the statement - the cutoff arithmetic, `==`/`>=` operators, `LIMIT 1`, rule filter,
   even `stmt=None` are invisible. Probed mock semantics: an unconfigured `AsyncMock`
   `session.execute(...)` returns an `AsyncMock` whose `.scalar_one_or_none()` yields a coroutine
   -> the mock-tolerance guard at threat_monitor_service.py:456-458 returns `None` -> cooldown is
   transparently "no existing alert" in every mock test.
2. **The Redis publish result is never parsed.** `test_broadcasts_alert_created_event` (:644) only
   asserts `publish.assert_called()`; `test_broadcast_includes_severity_and_threat_type` (:665-688)
   grabs `call_args` and asserts NOTHING ("exact format depends on implementation"). The whole WS
   payload schema (`alert.created`, channel, data keys, uuid/now fallbacks) survives.
3. **Webhooks are never reached.** No test patches `get_webhook_service`, so the lazy import at
   :138 raises inside the two process_* methods -> swallowed by the broad `except Exception` at
   :560 -> `logger.warning` -> nobody asserts. All 43 `_trigger_webhooks` survivors live in this
   never-executed branch.
4. **The multi-threat path never carries a rule and never asserts metadata.**
   `process_multiple_threat_detections` is only called with `rule=None` (its 3 tests), so every
   rule ternary/passthrough there is dead; `auto_generated`/`source`/`event_id`/`rule_id` are
   unasserted (contrast the single-threat metadata test :343-364 which DOES assert two metadata
   keys - that is why the same mutants died in `process_threat_detection` and survive here).
5. **Log text/`extra` payloads are mutated wholesale** (message -> None, key -> XX/CASE) and are
   genuinely unobservable - nobody should assert on log strings.

## Cluster table (machine fold of all 244 diffs; counts sum exactly to 244)

| # | Cluster (pattern @ concern) | N | Class | Example keys | Test |
| - | --- | - | ----- | ---------- | ---- |
| C1 | `_check_cooldown`: cutoff semantics - `now(UTC) - timedelta` -> `+` / `datetime.now(None)` naive; `dedup_key ==` -> `!=`; `created_at >=` -> `>` (lines 440-445) | 4 | TEST-GAP | _check_cooldown__mutmut_2, _10, _11 | T1 |
| C2 | `_check_cooldown`: query-shape collapses invisible to canned mocks - `stmt=None`, `select(None)`, `where(None)` x2, `limit(1)->2/None`, `execute(None)` | 7 | TEST-GAP | _check_cooldown__mutmut_5, _9, _6 | (none drafted) |
| C3 | `_check_cooldown`: mock-tolerance guard (:456-458) - `or`->`and` flips, `hasattr` operand/string mutations | 13 | TEST-GAP (weak) | _check_cooldown__mutmut_16, _19, _25 | (seam test sketched) |
| R1 | rule/cooldown wiring on BOTH creation paths - `_build_dedup_key(event, t, None)`, `cooldown_seconds ... and False`, `_check_cooldown(dedup=None, ..., rule=None)`, `existing_alert = None` swap (lines 227-231, 326-330) | 14 | TEST-GAP | ptd__mutmut_28, pmt__mutmut_34, pmt__mutmut_36 | T2 |
| R2 | alert-construction field wiring both paths - `rule_id=None` ternary collapse x6, `channels=None`/dropped x4, `status=None` x2, `event_id=None` x2, `dedup_key=None` x2, `session.add(None)`/`refresh(None)` x2 (lines 243-261, 347-367) | 20 | TEST-GAP | ptd__mutmut_53, pmt__mutmut_58, pmt__mutmut_61 | T2 |
| S1 | multi-threat selection semantics - threshold `>= -> >` (line 309), `get_threat_severity(type, hint)` hint drops in severity_key/highest/detected_threats (`threat.severity` -> None/dropped/reordered) | 10 | TEST-GAP | pmt__mutmut_3, pmt__mutmut_8, pmt__mutmut_23 | T3 |
| S2 | `SEVERITY_PRIORITY.get(...)` default-arg mutants (`None` key / default 0->1 / drop) - all 4 severities are map keys so default is unreachable: survivor-equivalent | 4 | EQUIVALENT | pmt__mutmut_11, _12, _15 | - |
| MV | alert_metadata VALUE mutants both paths - `auto_generated: True -> False`, `source` string values, `threat_detection_id` renames (lines 250-256, 354-362) | 12 | TEST-GAP | ptd__mutmut_76, pmt__mutmut_86, pmt__mutmut_89 | T6 |
| PK | multi metadata KEY renames (XX/UPPER of threat_type/threat_confidence/total_threats/detected_threats subkeys etc.) - keys never fully enumerated by tests | 18 | TEST-GAP (weak) | pmt__mutmut_82, pmt__mutmut_47 | T6 |
| W1 | WebSocket publish args - channel `"websocket:events"` -> None/XX/CASE, `publish(None, ...)`, payload -> None / `json.dumps(None)` / arg drops (lines 510-511) | 8 | TEST-GAP | bc__mutmut_41, bc__mutmut_44 | T4 |
| W2 | WS payload schema - `alert_data=None`, 24 key XX/CASE renames, `"type": "alert.created"` value+key renames, `"id": alert.id or str(uuid4())` -> `and`/`str(None)`, created/updated_at `if x and False` fallback defeat, `now_iso` None/tz None | 36 | TEST-GAP | bc__mutmut_36, bc__mutmut_7, bc__mutmut_21 | T4 |
| WH1 | `_trigger_webhooks` call contract - `get_webhook_service() -> None`, `webhook_data=None`, session/event-type/payload args -> None or dropped, `event_id=None`, `channels or [] -> and []` (lines 538-558) | 11 | TEST-GAP | tw__mutmut_1, tw__mutmut_29, tw__mutmut_31 | T5 |
| WH2 | webhook payload VALUES - `matched_conditions: ["threat_detected"]` -> XX/UPPER values, error log `str(e) -> str(None)` | 3 | TEST-GAP | tw__mutmut_20, tw__mutmut_44 | T5 |
| WH3 | webhook payload key renames (XX/CASE of 11 keys) - payload dict never observed by any test | 22 | TEST-GAP (weak) | tw__mutmut_3, tw__mutmut_18 | T5 |
| X | downstream handoff arg swaps - `_broadcast_alert_created(alert, None, ...)`, `(alert, event, None)`, `_trigger_webhooks(alert, None)` (lines 275-278, 381-384) | 4 | TEST-GAP (weak) | pmt__mutmut_106, pmt__mutmut_112 | (seam asserts sketched) |
| V | `raise ValueError("XX...requiredXX")` message renames - tests use `pytest.raises(match=...)` substring; XX-wrapped text still contains the matched substring -> contract-identical | 2 | EQUIVALENT | ptd__mutmut_3, ptd__mutmut_7 | - |
| LG1 | `process_threat_detection` log mutations - skip/create/cooldown messages -> None, `extra` dicts dropped/renamed (lines 211-219, 233-239, 263-272) | 29 | LOW-VALUE | ptd__mutmut_10, ptd__mutmut_83 | - |
| LG2 | `_broadcast_alert_created` debug-log message/extra mutations (:513-519) | 8 | LOW-VALUE | bc__mutmut_48, bc__mutmut_52 | - |
| LG3 | `_trigger_webhooks` failure-branch warning message/extra mutations (:562-565) | 7 | LOW-VALUE | tw__mutmut_36, tw__mutmut_40 | - |
| LG4 | `process_multiple_threat_detections` log mutations (:312-315, 332, 369-378) | 12 | LOW-VALUE | pmt__mutmut_5, pmt__mutmut_97 | - |

**Reconciliation**: 4+7+13 + 14+20 + 10+4 + 12+18 + 8+36 + 11+3+22 + 4+2 + 29+8+7+12 = **244**.
By classification: TEST-GAP 182 - LOW-VALUE 56 - EQUIVALENT 6.
By function: `_check_cooldown` 24 - `process_threat_detection` 54 - `_broadcast_alert_created` 52 -
`_trigger_webhooks` 43 - `process_multiple_threat_detections` 71.

## Classification notes

- **V (EQUIVALENT)**: `pytest.raises(match="threat_detection is required")` (test file :826, :844)
  is a regex-substring match; `"XXthreat_detection is requiredXX"` contains the matched substring,
  so the mutation is unobservable under the project's documented contract. Same logic: the 4 S2
  `dict.get` default mutants are unreachable (all four AlertSeverity members are in
  SEVERITY_PRIORITY).
- **LG1-4, and WH3/PK-remainder (LOW-VALUE / weak)**: log strings + `extra` dicts are real diffs but
  zero observable contract - do not write log-string assertions. WH3/PK key renames are "weak
  TEST-GAP" because they die for free the moment T5/T6 assert payload/metadata dicts by equality;
  only write per-key checks if those clusters still bite after T5/T6 land.
- **C3**: guard purpose is "mock result without id/created_at counts as no-cooldown". Only assertable
  at the seam (pass a plain object through a stubbed `session.execute`). One such test kills the 9
  semantic `or`/operand flips; the 4 pure `"id"->"ID"`/`"XX..XX"` hasattr renames are
  survivor-equivalent at any seam that returns real attribute-bearing objects.
- **C2 vs C1**: C1 is semantic and needs a **real in-memory-SQLite** test (T1) - mock-free,
  permanent. C2 (limit/where(None)/select(None)) is only killable by asserting compiled SQL through
  the mock; T1 makes most of C2's production value moot, so C2 is flagged "coverable by a
  compiled-SQL assert if the team wants 100%".
- **WH1/WH2 vs WH3**: no test currently patches `get_webhook_service`
  (`backend/services/threat_monitor_service.py:138` module-level symbol) - T5 opens the whole
  43-mutant branch. Payload dict equality inside T5 then kills WH3 too.

## Drafted tests (6 highest-value clusters: C1, R1+R2, S1, W1+W2, WH1+WH2+WH3, MV+PK)

All target `backend/tests/unit/services/test_threat_monitor_service.py`, reusing its existing
fixtures (`mock_session`, `mock_redis_client`, `sample_event`, `gun_threat_detection`,
`sample_detection`). **TDD procedure for each**: apply the cluster's mutant diff to
`backend/services/threat_monitor_service.py` -> the new assertion FAILS (red); revert -> PASSES
(green). UNVERIFIED - not yet run red/green (mutation run owns this machine; no pytest executed).

### T1 - kills C1 (cooldown cutoff/selector semantics) - REAL DB, no session mocks

```python
# add at top of backend/tests/unit/services/test_threat_monitor_service.py:
#   from datetime import timedelta
#   from sqlalchemy import func, select
#   from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
#   from sqlalchemy.pool import StaticPool
#   from backend.models import Base   # the shared declarative Base (backend/models/__init__.py)
# (datetime/timedelta, uuid, AsyncMock/MagicMock, pytest already imported)


class TestCheckCooldownDatabaseSemantics:
    """WP4.4 gap-fill: _check_cooldown SQL semantics.

    Existing tests stub session.execute, so the select() never runs and the cutoff
    sign, tz-awareness, dedup equality and created_at boundary all survive mutation
    (_check_cooldown__mutmut_2/-3/-10/-11). This runs the real SQL against in-memory
    SQLite with REAL Alert rows - no session mocks - per owner ruling F2 (M1 Task 7)
    that the cutoff must stay tz-aware.
    """

    async def _make_db(self):
        engine = create_async_engine(
            "sqlite+aiosqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return engine, async_sessionmaker(engine, expire_on_commit=False)

    async def _utcnow(self, session) -> datetime:
        """Clock read on the SAME connection that wrote the rows (avoids the
        aiosqlite in-memory fresh-connection-per-session pitfall)."""
        result = await session.execute(select(func.text("datetime('now')")))
        value = result.scalar()
        if isinstance(value, str):
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
        return value

    @pytest.mark.asyncio
    async def test_cooldown_selects_by_dedup_key_and_cutoff(self) -> None:
        from backend.services.threat_monitor_service import ThreatMonitorService

        engine, maker = await self._make_db()
        try:
            async with maker() as session:
                service = ThreatMonitorService(session, redis_client=None, cooldown_seconds=300)
                now = await self._utcnow(session)
                session.add(Alert(dedup_key="cam_a:gun:threat",
                                  created_at=now - timedelta(seconds=10),
                                  severity=AlertSeverity.CRITICAL, status=AlertStatus.PENDING, channels=[]))
                session.add(Alert(dedup_key="cam_a:knife:threat",
                                  created_at=now - timedelta(seconds=10),
                                  severity=AlertSeverity.HIGH, status=AlertStatus.PENDING, channels=[]))
                session.add(Alert(dedup_key="cam_a:gun:threat",
                                  created_at=now - timedelta(seconds=600),
                                  severity=AlertSeverity.CRITICAL, status=AlertStatus.PENDING, channels=[]))
                await session.flush()

                hit = await service._check_cooldown("cam_a:gun:threat", 300)
                assert hit is not None, (
                    "cooldown missed a fresh same-dedup_key alert: cutoff must be "
                    "now(UTC) - timedelta(seconds=cooldown_seconds), tz-aware"
                )
                wrong_key = await service._check_cooldown("cam_a:rifle:threat", 300)
                assert wrong_key is None, (
                    "no alert exists for cam_a:rifle:threat - dedup_key equality broken"
                )
        finally:
            await engine.dispose()
```

Note: SQLite stores datetimes to second granularity; an exact-300s-boundary fixture for the
`>= -> >` member (mutmut_11) can be added as a second case - keep it if green, else scope to
mutmut_2/-3/-10.

### T2 - kills R1 + R2 (rule/cooldown wiring + alert field wiring, both paths)

```python
class TestThreatMonitorServiceRuleWiring:
    """WP4.4 gap-fill: the multi path is never called with a rule (root cause 4) and no
    test asserts rule_id/channels/dedup wiring. Drive both paths WITH a rule."""

    @staticmethod
    def _rule() -> MagicMock:
        rule = MagicMock()
        rule.id = 7
        rule.cooldown_seconds = 90  # distinct from the service default of 300
        rule.dedup_key_template = "tpl:{camera_id}:{rule_id}:{threat_type}"
        return rule

    @staticmethod
    def _no_cooldown(mock_session: AsyncMock) -> None:
        mock_session.execute.return_value = MagicMock(
            scalar_one_or_none=MagicMock(return_value=None))

    @pytest.mark.asyncio
    async def test_multi_rule_template_and_id_reach_alert(
        self, mock_session, mock_redis_client, sample_event, sample_detection
    ) -> None:
        from backend.services.threat_monitor_service import ThreatMonitorService

        self._no_cooldown(mock_session)
        gun = ThreatDetection(id=30, detection_id=sample_detection.id, threat_type="gun",
                              confidence=0.9, severity="critical", bbox=[0, 0, 1, 1],
                              created_at=datetime.now(UTC))
        service = ThreatMonitorService(mock_session, mock_redis_client)

        alert = await service.process_multiple_threat_detections([gun], sample_event, self._rule())

        assert alert is not None
        assert alert.dedup_key == f"tpl:{sample_event.camera_id}:7:gun"  # pmt_26/-29/-32
        assert alert.rule_id == 7                                          # pmt_59/-66/-72, ptd_53/-60/-66
        assert alert.status == AlertStatus.PENDING                         # pmt_61/-68
        assert alert.channels == []                                        # ptd_57/-64, pmt_63/-70
        assert alert.event_id == sample_event.id                           # pmt_58/-65
        assert alert.dedup_key  # non-empty (pmt_62/-69 dedup_key=None collapse)

    @pytest.mark.asyncio
    async def test_multi_rule_cooldown_seconds_passed_to_check(
        self, mock_session, mock_redis_client, sample_event, sample_detection
    ) -> None:
        from unittest.mock import patch
        from backend.services.threat_monitor_service import ThreatMonitorService

        self._no_cooldown(mock_session)
        gun = ThreatDetection(id=31, detection_id=sample_detection.id, threat_type="gun",
                              confidence=0.9, severity="critical", bbox=[0, 0, 1, 1],
                              created_at=datetime.now(UTC))
        service = ThreatMonitorService(mock_session, mock_redis_client, cooldown_seconds=300)

        with patch.object(ThreatMonitorService, "_check_cooldown",
                          new=AsyncMock(return_value=None)) as cd:
            await service.process_multiple_threat_detections([gun], sample_event, self._rule())

        cd.assert_awaited_once()
        args = cd.await_args.args
        assert args[0] == f"tpl:{sample_event.camera_id}:7:gun"   # rule-aware dedup key (pmt_37)
        assert args[1] == 90                                       # rule cooldown wins (pmt_34, ptd_33)
        assert args[2] is self._rule or args[2] is not None        # rule forwarded (pmt_39/-42, ptd_38/-41)

    @pytest.mark.asyncio
    async def test_multi_in_cooldown_returns_none(
        self, mock_session, mock_redis_client, sample_event, sample_detection
    ) -> None:
        """Cooldown hit -> no new alert (kills pmt_36 `existing_alert = None` swap;
        pmt mirror of the existing single-path cooldown test :697)."""
        from backend.services.threat_monitor_service import ThreatMonitorService

        recent = MagicMock(spec=Alert)   # spec'd Alert passes the :456 guard (has id/created_at)
        recent.id, recent.created_at = uuid.uuid4(), datetime.now(UTC)
        mock_session.execute.return_value = MagicMock(
            scalar_one_or_none=MagicMock(return_value=recent))
        gun = ThreatDetection(id=32, detection_id=sample_detection.id, threat_type="gun",
                              confidence=0.9, severity="critical", bbox=[0, 0, 1, 1],
                              created_at=datetime.now(UTC))
        service = ThreatMonitorService(mock_session, mock_redis_client)

        alert = await service.process_multiple_threat_detections([gun], sample_event)
        assert alert is None
        mock_session.add.assert_not_called()          # also kills pmt_91 session.add(None)

    @pytest.mark.asyncio
    async def test_single_rule_wiring(
        self, mock_session, mock_redis_client, sample_event, gun_threat_detection
    ) -> None:
        from backend.services.threat_monitor_service import ThreatMonitorService

        self._no_cooldown(mock_session)
        service = ThreatMonitorService(mock_session, mock_redis_client)

        alert = await service.process_threat_detection(
            threat_detection=gun_threat_detection, event=sample_event, rule=self._rule())

        assert alert.dedup_key == f"tpl:{sample_event.camera_id}:7:gun"  # ptd_28/-31 rule drop
        assert alert.rule_id == 7
        mock_session.add.assert_called_once_with(alert)   # kills ptd_81/pmt_91 add(None)
        mock_session.refresh.assert_awaited_once_with(alert)  # ptd_82/pmt_92 refresh(None)
```

### T3 - kills S1 (multi threshold boundary + severity-hint drops)

```python
class TestThreatMonitorServiceMultiThreatThresholdAndHints:
    """WP4.4 gap-fill: pmt_3 (`>= -> >`) and hint-arg drops (pmt_6/-8/-9/-10/-23/-25/-52/-53/-54)."""

    def _threat(self, id_, type_, conf, sev, detection_id=1):
        return ThreatDetection(id=id_, detection_id=detection_id, threat_type=type_,
                               confidence=conf, severity=sev, bbox=[0, 0, 1, 1],
                               created_at=datetime.now(UTC))

    def _no_cooldown(self, mock_session):
        mock_session.execute.return_value = MagicMock(
            scalar_one_or_none=MagicMock(return_value=None))

    @pytest.mark.asyncio
    async def test_multi_creates_alert_at_exactly_threshold(
        self, mock_session, mock_redis_client, sample_event
    ) -> None:
        """confidence == threshold (0.70) is valid (kills pmt_3)."""
        from backend.services.threat_monitor_service import ThreatMonitorService

        self._no_cooldown(mock_session)
        service = ThreatMonitorService(mock_session, mock_redis_client)
        alert = await service.process_multiple_threat_detections(
            [self._threat(40, "gun", 0.70, "critical")], sample_event)
        assert alert is not None
        assert alert.severity == AlertSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_hint_only_unknown_threats_keep_severity(
        self, mock_session, mock_redis_client, sample_event
    ) -> None:
        """Unknown types resolved ONLY via the severity hint: dropping the hint
        (mutants default both to HIGH) must change the winner / metadata severities."""
        from backend.services.threat_monitor_service import ThreatMonitorService

        self._no_cooldown(mock_session)
        bat_hint = self._threat(41, "blunt_thing", 0.9, "medium")     # listed first
        knife_hint = self._threat(42, "sharp_thing", 0.9, "critical")
        service = ThreatMonitorService(mock_session, mock_redis_client)

        alert = await service.process_multiple_threat_detections(
            [bat_hint, knife_hint], sample_event)

        assert alert.severity == AlertSeverity.CRITICAL            # own hint used for winner (pmt_23/-25)
        assert alert.alert_metadata["threat_type"] == "sharp_thing"
        by_type = {t["type"]: t["severity"]
                   for t in alert.alert_metadata["detected_threats"]}
        assert by_type["sharp_thing"] == "critical"                # own hint in metadata (pmt_52/-53/-54)
        assert by_type["blunt_thing"] == "medium"                  # pmt_6/-8/-9/-10 (severity_key hints)
```

### T4 - kills W1 + W2 (WebSocket channel + payload contract)

```python
class TestThreatMonitorServiceWebSocketPayloadContract:
    """WP4.4 gap-fill: existing WS tests never parse the publish payload (root cause 2)."""

    @pytest.mark.asyncio
    async def test_publishes_alert_created_on_websocket_channel(
        self, mock_session, mock_redis_client, sample_event, gun_threat_detection
    ) -> None:
        import json as json_mod
        from backend.services.threat_monitor_service import ThreatMonitorService

        service = ThreatMonitorService(mock_session, mock_redis_client)
        await service.process_threat_detection(
            threat_detection=gun_threat_detection, event=sample_event)

        mock_redis_client.publish.assert_called_once()
        channel, raw = mock_redis_client.publish.call_args.args
        assert channel == "websocket:events"        # W1: bc_40/-41/-42, bc_43
        message = json_mod.loads(raw)               # valid JSON (W1: bc_44/-45/-46/-47)
        assert message["type"] == "alert.created"   # W2: bc_34..-37
        data = message["data"]                      # W2: bc_4, bc_38/-39
        assert data["event_id"] == sample_event.id
        assert data["camera_id"] == sample_event.camera_id
        assert data["threat_type"] == "gun"
        assert data["threat_confidence"] == gun_threat_detection.confidence
        assert data["severity"] == "critical"
        assert data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_broadcast_falls_back_to_uuid_and_now(
        self, mock_session, mock_redis_client, sample_event, gun_threat_detection
    ) -> None:
        """Mock session never populates id/created_at: broadcast must fall back to a
        UUID (kills bc_7 `or -> and`, bc_8 `str(None)`) and ISO timestamp (kills
        bc_21/-25 `and False`, bc_2/-3 now_iso mutations)."""
        import json as json_mod
        import uuid as uuid_mod
        from backend.services.threat_monitor_service import ThreatMonitorService

        service = ThreatMonitorService(mock_session, mock_redis_client)
        await service.process_threat_detection(
            threat_detection=gun_threat_detection, event=sample_event)

        _, raw = mock_redis_client.publish.call_args.args
        data = json_mod.loads(raw)["data"]
        assert data["id"] is not None
        uuid_mod.UUID(data["id"])                    # valid uuid4 string
        assert data["created_at"] and data["updated_at"]
        datetime.fromisoformat(data["created_at"])   # parseable ISO-8601
```

(W2's 24 pure XX/CASE key renames: extend to `assert set(data) == {...11 keys...}` if any
survive the value assertions above.)

### T5 - kills WH1 + WH2 (and WH3 with full-dict equality) - webhooks via patched service

```python
class TestThreatMonitorServiceWebhookContract:
    """WP4.4 gap-fill: all 43 _trigger_webhooks survivors are in the never-executed
    branch (root cause 3). Patch the module-level lazy lookup (get_webhook_service at
    threat_monitor_service.py:138) and assert the full call."""

    @pytest.mark.asyncio
    async def test_alert_fired_webhook_payload(
        self, mock_session, mock_redis_client, sample_event, gun_threat_detection
    ) -> None:
        from unittest.mock import patch
        from backend.services.threat_monitor_service import ThreatMonitorService

        webhook_service = MagicMock()
        webhook_service.trigger_webhooks_for_event = AsyncMock()
        service = ThreatMonitorService(mock_session, mock_redis_client)

        with patch("backend.services.threat_monitor_service.get_webhook_service",
                   return_value=webhook_service):
            alert = await service.process_threat_detection(
                threat_detection=gun_threat_detection, event=sample_event)

        webhook_service.trigger_webhooks_for_event.assert_awaited_once()
        args, kwargs = webhook_service.trigger_webhooks_for_event.await_args
        assert args[0] is mock_session              # WH1: tw_28/-32
        assert args[1] == "alert_fired"             # WebhookEventType.ALERT_FIRED (tw_29/-33)
        assert kwargs.get("event_id") == alert.id   # WH1: tw_31/-35
        payload = args[2]                           # tw_2/-30 (webhook_data None/drop)
        assert payload["matched_conditions"] == ["threat_detected"]   # WH2: tw_20/-21
        assert payload["alert_id"] == alert.id
        assert payload["severity"] == "critical"
        assert payload["status"] == "pending"
        assert payload["camera_id"] == sample_event.camera_id
        assert payload["risk_score"] == sample_event.risk_score
        assert payload["channels"] == []            # tw_17 (`or [] -> and []` on None channels)
        assert payload["threat_metadata"] == alert.alert_metadata
        # kills tw_1 (get_webhook_service() -> None): failure must never break the alert
        webhook_service.trigger_webhooks_for_event.side_effect = RuntimeError("boom")
        alert2 = await service.process_threat_detection(
            threat_detection=gun_threat_detection, event=sample_event)
        assert alert2 is not None
```

For WH3 (22 key renames): change `payload` assertions to full-dict equality -
`assert payload == {"alert_id": ..., "event_id": ..., "rule_id": ..., "severity": ..., "status": ...,
"dedup_key": ..., "channels": [], "matched_conditions": [...], "camera_id": ..., "risk_score": ...,
"threat_metadata": ...}` - which also pins every key name.

### T6 - kills MV + PK (alert_metadata full-surface equality, both paths)

```python
class TestThreatMonitorServiceAlertMetadataFullSurface:
    """WP4.4 gap-fill: existing tests assert only 2 metadata keys on the single path and
    only `type` membership on the multi path. Equality-assert the whole dicts."""

    @pytest.mark.asyncio
    async def test_single_threat_metadata_exact(
        self, mock_session, mock_redis_client, sample_event, gun_threat_detection
    ) -> None:
        from backend.services.threat_monitor_service import ThreatMonitorService

        mock_session.execute.return_value = MagicMock(
            scalar_one_or_none=MagicMock(return_value=None))
        service = ThreatMonitorService(mock_session, mock_redis_client)

        alert = await service.process_threat_detection(
            threat_detection=gun_threat_detection, event=sample_event)

        assert alert.alert_metadata == {
            "threat_type": "gun",
            "threat_confidence": gun_threat_detection.confidence,
            "threat_detection_id": gun_threat_detection.id,   # MV: ptd_72/-73
            "auto_generated": True,                            # MV: ptd_76 -> False
            "source": "threat_monitor_service",                # MV: ptd_77..-80
        }

    @pytest.mark.asyncio
    async def test_multi_threat_metadata_exact(
        self, mock_session, mock_redis_client, sample_event, sample_detection
    ) -> None:
        from backend.services.threat_monitor_service import ThreatMonitorService

        mock_session.execute.return_value = MagicMock(
            scalar_one_or_none=MagicMock(return_value=None))
        gun = ThreatDetection(id=50, detection_id=sample_detection.id, threat_type="gun",
                              confidence=0.9, severity="critical", bbox=[0, 0, 1, 1],
                              created_at=datetime.now(UTC))
        knife = ThreatDetection(id=51, detection_id=sample_detection.id, threat_type="knife",
                                confidence=0.85, severity="high", bbox=[0, 0, 1, 1],
                                created_at=datetime.now(UTC))
        service = ThreatMonitorService(mock_session, mock_redis_client)

        alert = await service.process_multiple_threat_detections([gun, knife], sample_event)

        assert alert.alert_metadata == {
            "threat_type": "gun",
            "threat_confidence": 0.9,
            "threat_detection_id": 50,
            "detected_threats": [
                {"type": "gun", "confidence": 0.9, "severity": "critical", "detection_id": 50},
                {"type": "knife", "confidence": 0.85, "severity": "high", "detection_id": 51},
            ],
            "total_threats": 2,
            "auto_generated": True,                            # MV: pmt_86
            "source": "threat_monitor_service",                # MV: pmt_89/-90
        }   # PK: every XX/CASE key rename in the metadata dicts dies to the exact-key dict
```

## Residual (deliberately not drafted)

- **C2** (7 query-shape mutants): killable only via compiled-SQL asserts through the mock
  (`str(stmt.compile())` captured from `session.execute`); T1 renders their production value moot.
  Mark "covered at DB level by T1" or add the compile assert if the team wants zero survivors.
- **C3 residual** (4 hasattr string renames): survivor-equivalent at any realistic seam; a
  seam test (stub `session.execute` to return an object lacking `id`) kills the 9 semantic
  members.
- **X** (4 handoff swaps): seam fix = spy `_broadcast_alert_created`/`_trigger_webhooks` with
  `patch.object(..., new=AsyncMock())` and assert `await_args.args[1] is event`. Two lines;
  include if survivors still bite after T1-T6.
- **LG1-4, V, S2**: log text / match-substring / unreachable-default mutants - do not write tests
  (LOW-VALUE / EQUIVALENT policy).
