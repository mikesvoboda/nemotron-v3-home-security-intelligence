# WP4.4 Triage Dossier — backend/services/alert_engine.py

- **Survivors:** 140 of 735 mutants (exit_code 0)
- **Method:** diffs extracted by AST-pairing each `xǁAlertRuleEngineǁ<fn>__mutmut_N` copy against its `__mutmut_orig` sibling in `mutants/backend/services/alert_engine.py` (no mutmut run). Full raw per-key diff: `/tmp/wp25/wp44-triage/alert_engine.diff.txt`.
- **Covering tests (from mutmut-stats.json `tests_by_mangled_function_name`):**
  - `backend/tests/unit/services/test_webhook_integration.py:213` (`TestAlertEngineWebhookIntegration.test_create_alerts_triggers_webhooks`) — asserts ONLY `assert_called_once` + `call_args[0][1] == ALERT_FIRED`. Never inspects the payload.
  - `backend/tests/unit/services/test_alert_engine.py:290` (`TestLoadEventDetections`), `:1320` (`TestCreateAlertsForEvent`), `:1882` (`TestDwellTimeCondition`)
  - `backend/tests/unit/services/test_alert_engine_new_conditions.py:161` (Pose), `:420` (Action), `:631` (Threat), `:894` (Smoke)
- **Root mock-blindness (explains most survivors):** every test stubs `session.execute` with a pre-baked `MagicMock` result. The **statement object passed to `execute` is never inspected**, so any mutation inside `select(...)/where(...)` is invisible. Confidence/severity tests always use _strictly above/below_ values — never _exactly at_ threshold. The webhook test never reads `webhook_data`.

## Cluster table (counts sum to exactly 140)

Per-key membership was enumerated exhaustively (verified: function buckets 58+25+18+14+11+7+6+1 = 140).

| #   | Pattern                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | Count | Class      | Keys (fn\_\_mutmut_N)                                                                                                                          | Draft                                                               |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----- | ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| 1   | Webhook payload outer keys renamed (`"XXalert_idXX"`, `"SEVERITY"`, …): each of 11 keys × {XXwrap, UPPERCASE}                                                                                                                                                                                                                                                                                                                                                                              | 22    | TEST-GAP   | \_trigger_alert_webhook\_\_mutmut_3, \_19, \_51; also \_4,\_5,\_6,\_7,\_8,\_9,\_10,\_20,\_29,\_30,\_31,\_32,\_34,\_35,\_44,\_45,\_52,\_53,\_54 | T1                                                                  |
| 2   | Webhook call-shape corruption: `webhook_data=None`, `session→None`, `webhook_data` arg dropped, `event_id=None`, `event_id=` kwarg dropped, `channels or []`→`and []`                                                                                                                                                                                                                                                                                                                      | 7     | TEST-GAP   | \_trigger_alert_webhook\_\_mutmut_2, \_55, \_62; also \_33,\_57,\_58,\_61                                                                      | T1                                                                  |
| 3   | `alert_metadata` guard/read mutants: `if alert.alert_metadata`→`and False`/`or True` ×4 (\_36,\_37,\_46,\_47), `.get("matched_conditions"…)` key/default swaps ×5 (\_38,\_39,\_41,\_42,\_43), `.get("rule_name")` key/default swaps ×3 (\_48,\_49,\_50)                                                                                                                                                                                                                                    | 12    | TEST-GAP   | \_trigger_alert_webhook\_\_mutmut_36, \_42, \_50                                                                                               | T2                                                                  |
| 4   | severity/status `.value` unwrap via `hasattr(…, "value")` mutants (`and False`/`or True`/`hasattr(None…)`/attr-case swaps)                                                                                                                                                                                                                                                                                                                                                                 | 10    | EQUIVALENT | \_trigger_alert_webhook\_\_mutmut_11, \_22, \_28; also \_12,\_13,\_17,\_18,\_21,\_23,\_27                                                      | —                                                                   |
| 5   | Webhook-failure `logger.warning` message→None / `extra` dict key renames / arg removals                                                                                                                                                                                                                                                                                                                                                                                                    | 7     | LOW-VALUE  | \_trigger_alert_webhook\_\_mutmut_63, \_64, \_68; also \_66,\_67,\_69,\_70                                                                     | —                                                                   |
| 6   | SQL predicate weakened/inverted _inside_ where-clauses (drop or invert a filter): dwell `camera_id =`→None/_8→`!=`, `loitering_alert_enabled.is_(True)`→None/_19,_20 removal/_23→is_(None)/_24→is_(False), `id.in*(…)`→None/_17,_19, `zone_id =`→None/_34,_36→`!=`, `exit_time is*(None)`→None/_5,_33; junction `event*id =`→None/_12,_14→`!=`; pose/action/threat/smoke `where(in*…)`→None (\_check_pose_type_8, \_check_action_type_8, \_check_threat_detected_8, \_check_smoke_fire_14) | 18    | TEST-GAP   | \_check_dwell_time**mutmut_18, \_check_dwell_time**mutmut_24, \_load_event_detections\_\_mutmut_14                                             | T3 kills dwell+load (14); pattern-extend kills 4                    |
| 7   | Query-construction args clobbered to `None` — invisible under mocked session, crash or drop-table on real DB: `stmt=None`, `select(None)`, `execute(None)` (dwell \_4,\_7,\_10,\_16,\_21,\_26,\_32,\_35,\_38 = 9; load \_11,\_13,\_16; pose \_7,\_9,\_12; action \_7,\_9,\_12; threat \_7,\_9,\_12; smoke \_13,\_15,\_18)                                                                                                                                                                  | 24    | TEST-GAP   | \_check_dwell_time**mutmut_16, \_check_pose_type**mutmut_7, \_load_event_detections\_\_mutmut_11                                               | T3 kills dwell+load (12); pattern-extend kills 12                   |
| 8   | Threshold boundary flips (`>=`→`>`, `<`→`<=`) — behavior differs only AT equality: dwell \_42; threat \_35 (severity), \_37 (confidence); pose \_25; action \_25; smoke \_23 (confidence), \_26 (consecutive)                                                                                                                                                                                                                                                                              | 7     | TEST-GAP   | \_check_dwell_time**mutmut_42, \_check_threat_detected**mutmut_35, \_check_action_type\_\_mutmut_25                                            | T3 (dwell) + T4 (6)                                                 |
| 9   | `continue`→`break` in rejection branches — later valid candidate skipped                                                                                                                                                                                                                                                                                                                                                                                                                   | 4     | TEST-GAP   | \_check_threat_detected**mutmut_36, \_38; \_check_smoke_fire**mutmut_24, \_27                                                                  | T5                                                                  |
| 10  | Threat severity-priority table/default tweaks: rule-min `.get(…, 0)` default→None/missing/1 (\_23,\_25,\_26), ternary `else 0`→`1` (\_27), threat-side `.get(threat.severity,…)` key→None and default→None/missing/1 (\_30,\_31,\_33,\_34) — unknown/unset severity silently shifts or crashes with TypeError                                                                                                                                                                              | 8     | TEST-GAP   | \_check_threat_detected\_\_mutmut_26, \_31, \_34                                                                                               | T6                                                                  |
| 11  | Smoke/fire constant tweaks: `consecutive_required or 2`→`and 2` (\_11, → None → TypeError when field unset) and `or 3` (\_12), accepted-type tuple `"fire"`→`"XXfireXX"`/`"FIRE"` (\_33,\_34 — fire detection silently lost)                                                                                                                                                                                                                                                               | 4     | TEST-GAP   | \_check_smoke_fire\_\_mutmut_11, \_33, \_34                                                                                                    | recipe in notes                                                     |
| 12  | `_load_event_detections` `inspect()` bypass: `state=None` / `inspect(None)` — always falls into the mock-except path; defeats the lazy-load-avoidance the function exists for                                                                                                                                                                                                                                                                                                              | 2     | TEST-GAP   | \_load_event_detections\_\_mutmut_1, \_2                                                                                                       | none — kill needs a real instrumented ORM Event (integration level) |
| 13  | `batch_fetch_detections(self.session, ids)` arg corruption: session→None, ids→None, session dropped, ids dropped                                                                                                                                                                                                                                                                                                                                                                           | 4     | TEST-GAP   | \_load_event_detections\_\_mutmut_20, \_22, \_21, \_23                                                                                         | T3                                                                  |
| 14  | `action.action and`→`or`: `action=None` now evaluates `None.lower()` → AttributeError crash instead of graceful skip                                                                                                                                                                                                                                                                                                                                                                       | 1     | TEST-GAP   | \_check_action_type\_\_mutmut_20                                                                                                               | T6                                                                  |
| 15  | Dead-guard / forced-ternary boolean flips with no reachable divergence: guard `not X or not detections`→`and` in pose \_1, action \_1, threat \_1, smoke \_1; threat `if rule.threat_min_severity`→`or True` \_21 (get(None,0)==else-0)                                                                                                                                                                                                                                                    | 5     | EQUIVALENT | \_check_pose_type**mutmut_1, \_check_threat_detected**mutmut_21, \_check_smoke_fire\_\_mutmut_1                                                | —                                                                   |
| 16  | Dwell time-source clobber: `current_time = utc_now_naive()`→None, `calculate_dwell_time(None)` (mock records hide it; real model crashes or mis-computes)                                                                                                                                                                                                                                                                                                                                  | 2     | TEST-GAP   | \_check_dwell_time\_\_mutmut_15, \_41                                                                                                          | T3                                                                  |
| 17  | Dwell `logger.debug` message→None                                                                                                                                                                                                                                                                                                                                                                                                                                                          | 1     | LOW-VALUE  | \_check_dwell_time\_\_mutmut_52                                                                                                                | —                                                                   |
| 18  | `create_alerts_for_event`: `session.add(alert)`→`add(None)` (tests assert `call_count==1` never the argument)                                                                                                                                                                                                                                                                                                                                                                              | 1     | TEST-GAP   | create_alerts_for_event\_\_mutmut_22                                                                                                           | T1                                                                  |
| 19  | Smoke filter `isinstance(str) AND in ("smoke","fire")`→`OR` — any non-listed string now fires                                                                                                                                                                                                                                                                                                                                                                                              | 1     | TEST-GAP   | \_check_smoke_fire\_\_mutmut_29                                                                                                                | recipe in notes                                                     |

**Totals:** TEST-GAP 22+7+12+18+24+7+4+8+4+2+4+1+2+1+1 = **117**; EQUIVALENT 10+5 = **15**; LOW-VALUE 7+1 = **8**. Sum = 140.

**EQUIVALENT justification:**

- Cluster 4: `AlertSeverity`/`AlertStatus` are `StrEnum` aliases (backend/models/alert.py:50,59,69), so the enum instance _is_ a str equal to its `.value` — payload equality and JSON serialization are byte-identical either way; `alert.severity`/`status` are `nullable=False` so `hasattr(None,…)` swaps never hit a None target.
- Cluster 15: `_evaluate_rule` (backend/services/alert*engine.py:498-523) invokes each `\_check*\*` only when the rule flag is set, and the second guard (`if not detection_ids: return False`) still rejects empty/idless detections, so the `or`→`and`guard flip has no reachable divergence. Threat _21:`THREAT_SEVERITY_PRIORITY.get(None, 0) == 0 == else-branch`for every falsy`threat_min_severity`.

## Drafted tests — ALL UNVERIFIED (not yet run red/green)

TDD procedure for every draft: run the test against the mutant source (the one-line change from the cluster diff); the new assertion must FAIL. Run against `backend/services/alert_engine.py` as-is; it must PASS. Verify only in the serial pytest lane.

### T1 — `test_alert_webhook_payload_matches_documented_contract`

Target file: `backend/tests/unit/services/test_webhook_integration.py` (add to `TestAlertEngineWebhookIntegration`, after line 253). Kills clusters 1 (22), 2 (7), 18 (1) = 30.

```python
    @pytest.mark.asyncio
    async def test_alert_webhook_payload_matches_documented_contract(
        self,
        mock_session: AsyncMock,
        mock_webhook_service: MagicMock,
        sample_alert: Alert,
    ) -> None:
        """WP4.4: pin the full ALERT_FIRED payload contract (keys, values, call shape).

        Kills key-rename, payload-clobber and call-shape mutants in
        AlertRuleEngine._trigger_alert_webhook. // UNVERIFIED - not yet run red/green
        """
        from backend.models import AlertRule, Event
        from backend.services.alert_engine import AlertRuleEngine, TriggeredRule

        with patch(
            "backend.services.alert_engine.get_webhook_service",
            return_value=mock_webhook_service,
            autospec=True,
        ):
            engine = AlertRuleEngine(mock_session)

            event = MagicMock(spec=Event)
            event.id = 1
            event.camera_id = "front_door"
            event.risk_score = 75

            rule = MagicMock(spec=AlertRule)
            rule.id = str(uuid.uuid4())
            rule.name = "High Risk Alert"
            rule.channels = ["push"]

            triggered = TriggeredRule(
                rule=rule,
                severity=AlertSeverity.HIGH,
                matched_conditions=["risk_threshold"],
                dedup_key="front_door:rule1",
            )

            alerts = await engine.create_alerts_for_event(event, [triggered])
            alert = alerts[0]

            # add() must receive the Alert object itself, not None (cluster 18)
            mock_session.add.assert_called_once_with(alert)

            mock_webhook_service.trigger_webhooks_for_event.assert_called_once()
            call_args = mock_webhook_service.trigger_webhooks_for_event.call_args
            # positional shape: (session, event_type, payload); keyword: event_id (cluster 2)
            assert call_args[0][0] is mock_session
            assert call_args[0][1] == WebhookEventType.ALERT_FIRED
            payload = call_args[0][2]
            assert payload is not None
            assert set(payload) == {  # cluster 1: exact key set
                "alert_id",
                "event_id",
                "rule_id",
                "severity",
                "status",
                "dedup_key",
                "channels",
                "matched_conditions",
                "rule_name",
                "camera_id",
                "risk_score",
            }
            assert payload["event_id"] == event.id
            assert payload["rule_id"] == rule.id
            assert payload["severity"] == "high"
            assert payload["status"] == "pending"
            assert payload["dedup_key"] == "front_door:rule1"
            assert payload["channels"] == ["push"]  # kills channels `or []`->`and []`
            assert payload["matched_conditions"] == ["risk_threshold"]
            assert payload["rule_name"] == "High Risk Alert"
            assert payload["camera_id"] == "front_door"
            assert payload["risk_score"] == 75

            # Direct call with an id-bearing alert pins event_id=alert.id (cluster 2)
            mock_webhook_service.trigger_webhooks_for_event.reset_mock()
            await engine._trigger_alert_webhook(sample_alert, event)
            call_args = mock_webhook_service.trigger_webhooks_for_event.call_args
            payload = call_args[0][2]
            assert call_args[1] == {"event_id": sample_alert.id}
            assert payload["alert_id"] == sample_alert.id
            assert payload["event_id"] == sample_alert.event_id
            assert payload["dedup_key"] == sample_alert.dedup_key
```

### T2 — `test_alert_webhook_metadata_fields_and_none_metadata_resilience`

Target file: `backend/tests/unit/services/test_webhook_integration.py` (same class). Kills cluster 3 (12).

```python
    @pytest.mark.asyncio
    async def test_alert_webhook_metadata_fields_and_none_metadata_resilience(
        self,
        mock_session: AsyncMock,
        mock_webhook_service: MagicMock,
    ) -> None:
        """WP4.4: matched_conditions/rule_name read from alert_metadata; None metadata must not crash.

        // UNVERIFIED - not yet run red/green
        """
        from backend.models import Event
        from backend.services.alert_engine import AlertRuleEngine

        event = MagicMock(spec=Event)
        event.id = 1
        event.camera_id = "front_door"
        event.risk_score = 50

        def make_alert(metadata: object) -> Alert:
            return Alert(
                id=str(uuid.uuid4()),
                event_id=1,
                rule_id=str(uuid.uuid4()),
                severity=AlertSeverity.HIGH,
                status=AlertStatus.PENDING,
                dedup_key="k",
                channels=[],
                alert_metadata=metadata,
            )

        with patch(
            "backend.services.alert_engine.get_webhook_service",
            return_value=mock_webhook_service,
            autospec=True,
        ):
            engine = AlertRuleEngine(mock_session)

            # 1) populated metadata flows into the payload (kills and-False + key swaps)
            await engine._trigger_alert_webhook(
                make_alert({"matched_conditions": ["c1", "c2"], "rule_name": "Fire Safety"}),
                event,
            )
            payload = mock_webhook_service.trigger_webhooks_for_event.call_args[0][2]
            assert payload["matched_conditions"] == ["c1", "c2"]
            assert payload["rule_name"] == "Fire Safety"

            # 2) metadata without the keys -> [] and None defaults (kills default->None)
            mock_webhook_service.trigger_webhooks_for_event.reset_mock()
            await engine._trigger_alert_webhook(make_alert({"other": 1}), event)
            payload = mock_webhook_service.trigger_webhooks_for_event.call_args[0][2]
            assert payload["matched_conditions"] == []
            assert payload["rule_name"] is None

            # 3) alert_metadata=None -> graceful, webhook still fired (kills or-True crash)
            mock_webhook_service.trigger_webhooks_for_event.reset_mock()
            await engine._trigger_alert_webhook(make_alert(None), event)
            mock_webhook_service.trigger_webhooks_for_event.assert_called_once()
            payload = mock_webhook_service.trigger_webhooks_for_event.call_args[0][2]
            assert payload["matched_conditions"] == []
            assert payload["rule_name"] is None
```

### T3 — dwell + detection-loading SQL contract (3 tests)

Target file: `backend/tests/unit/services/test_alert_engine.py` (new class after `TestDwellTimeCondition`, ~line 2122; fixtures copied locally). Kills clusters 6 dwell+load (14), 7 dwell+load (12), 8 dwell (1), 13 (4), 16 (2) = 33. The same `str(stmt)`-predicate pattern applied inside the existing pose/action/threat/smoke tests kills the remaining 4+12 of clusters 6/7.

```python
class TestDwellAndLoadingSqlContract:
    """WP4.4: the mocked-session blind spot — assert what was actually queried.

    // UNVERIFIED - not yet run red/green
    """

    @pytest.fixture
    def mock_polygon_zone(self) -> MagicMock:
        zone = MagicMock()
        zone.id = 1
        zone.name = "Front Yard"
        zone.loitering_threshold_seconds = 60.0
        zone.loitering_alert_enabled = True
        return zone

    @pytest.fixture
    def dwell_rule(self) -> AlertRule:
        return AlertRule(
            id=str(uuid.uuid4()),
            name="Loitering Rule",
            enabled=True,
            severity=AlertSeverity.HIGH,
            dwell_time_enabled=True,
            zone_ids=[1],
            cooldown_seconds=300,
        )

    def _capturing_session(self, results: list[MagicMock]) -> tuple[AsyncMock, list[object]]:
        executed: list[object] = []
        queue = iter(results)

        async def fake_execute(stmt: object, *args: object, **kwargs: object) -> MagicMock:
            executed.append(stmt)
            return next(queue)

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=fake_execute)
        session.add = MagicMock()
        session.flush = AsyncMock()
        return session, executed

    @pytest.mark.asyncio
    async def test_dwell_time_queries_preserve_scoping_predicates(
        self, sample_event: MagicMock, dwell_rule: AlertRule, mock_polygon_zone: MagicMock
    ) -> None:
        """Zones and dwell-record queries must keep camera/zone/active/enabled predicates."""
        zones_result = MagicMock()
        zones_result.scalars.return_value.all.return_value = [mock_polygon_zone]
        record = MagicMock()
        record.zone_id = 1
        record.track_id = 42
        record.exit_time = None
        record.calculate_dwell_time.return_value = 90.0
        dwell_result = MagicMock()
        dwell_result.scalars.return_value.all.return_value = [record]

        session, executed = self._capturing_session([zones_result, dwell_result])
        engine = AlertRuleEngine(session)
        matches, _, _ = await engine._check_dwell_time(dwell_rule, sample_event)

        assert matches is True
        assert len(executed) == 2
        assert all(stmt is not None for stmt in executed)  # kills execute(None)/stmt=None

        zone_sql = str(executed[0])
        assert "polygon_zones" in zone_sql
        assert "polygon_zones.id IN" in zone_sql  # kills id.in_ removal
        assert "loitering_alert_enabled IS true" in zone_sql.lower()  # kills is_(True) flips

        dwell_sql = str(executed[1])
        assert "dwell_time_records" in dwell_sql
        assert "dwell_time_records.zone_id =" in dwell_sql  # kills == -> !=
        assert "!=" not in dwell_sql
        assert "exit_time IS NULL" in dwell_sql  # kills active-record filter loss

        # cluster 16: dwell calc must use a real current time, not None
        record.calculate_dwell_time.assert_called_once()
        assert isinstance(record.calculate_dwell_time.call_args[0][0], datetime)

    @pytest.mark.asyncio
    async def test_dwell_time_all_zones_query_scopes_by_camera(
        self, sample_event: MagicMock
    ) -> None:
        """rule.zone_ids empty -> distinct-zone query must keep camera_id and exit_time filters."""
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Loitering Rule",
            enabled=True,
            severity=AlertSeverity.HIGH,
            dwell_time_enabled=True,
            zone_ids=None,
            cooldown_seconds=300,
        )
        zone_ids_result = MagicMock()
        zone_ids_result.scalars.return_value.all.return_value = [1]
        zone = MagicMock()
        zone.id = 1
        zone.name = "Zone 1"
        zone.loitering_threshold_seconds = 60.0
        zone.loitering_alert_enabled = True
        zones_result = MagicMock()
        zones_result.scalars.return_value.all.return_value = [zone]
        record = MagicMock()
        record.zone_id = 1
        record.track_id = 10
        record.exit_time = None
        record.calculate_dwell_time.return_value = 60.0  # EXACTLY at threshold
        dwell_result = MagicMock()
        dwell_result.scalars.return_value.all.return_value = [record]

        session, executed = self._capturing_session([zone_ids_result, zones_result, dwell_result])
        engine = AlertRuleEngine(session)
        matches, _, _ = await engine._check_dwell_time(rule, sample_event)

        first_sql = str(executed[0])
        assert "DISTINCT" in first_sql.upper()
        assert "dwell_time_records.camera_id =" in first_sql  # kills camera scoping mutants
        assert "!=" not in first_sql
        assert "exit_time IS NULL" in first_sql

        # cluster 8: dwell at exactly the threshold must alert (>=, not >)
        assert matches is True

    @pytest.mark.asyncio
    async def test_load_event_detections_junction_query_and_batch_fetch_args(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        """Junction query must filter by event_id (not !=) and pass session+ids to batch fetch."""
        sample_event.detections = []
        junction_result = MagicMock()
        junction_result.scalars.return_value.all.return_value = [1, 2, 3]

        executed: list[object] = []

        async def fake_execute(stmt: object, *a: object, **k: object) -> MagicMock:
            executed.append(stmt)
            return junction_result

        mock_session.execute = AsyncMock(side_effect=fake_execute)
        engine = AlertRuleEngine(mock_session)

        with patch(
            "backend.services.alert_engine.batch_fetch_detections",
            new_callable=AsyncMock,
            return_value=sample_detections,
        ) as batch_mock:
            detections = await engine._load_event_detections(sample_event)

        assert detections == sample_detections
        sql = str(executed[0])
        assert "event_detections" in sql
        assert "event_detections.event_id =" in sql  # kills == -> !=
        assert "!=" not in sql
        batch_mock.assert_called_once_with(mock_session, [1, 2, 3])  # kills arg clobbers
```

(`datetime` is already imported in the target file: `from datetime import UTC, datetime`, line 15. Caveat: SQLAlchemy renders `IN` as `IN (__det_0, __det_1)` for bound lists — if `str(stmt)` shows the bound-param form, loosen the `IN` check to `"polygon_zones.id IN"` only, and run `str(stmt.compile(compile_kwargs={"literal_binds": False}))` style checks for `=`.)

### T4 — `test_threshold_comparisons_are_inclusive_at_equality` (6 tests)

Target file: `backend/tests/unit/services/test_alert_engine_new_conditions.py` (new class at end; fixtures `mock_session`/`sample_event`/`sample_detections` already exist there). Kills cluster 8 minus dwell = 6.

```python
class TestThresholdsInclusiveAtEquality:
    """WP4.4: every `>=`/`<` boundary must trigger AT the threshold, not only past it.

    // UNVERIFIED - not yet run red/green
    """

    @pytest.mark.asyncio
    async def test_pose_confidence_exactly_at_threshold_matches(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Exact Pose",
            enabled=True,
            severity=AlertSeverity.HIGH,
            pose_types=["crouching"],
            pose_confidence_threshold=0.8,
            cooldown_seconds=300,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        pose = PoseResult(
            id=1, detection_id=1, keypoints=[[0, 0, 0.9]] * 17,
            pose_class="crouching", confidence=0.8, is_suspicious=True,
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [pose]
        mock_session.execute.return_value = mock_result
        engine = AlertRuleEngine(mock_session)
        matches, _, _ = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )
        assert matches is True

    @pytest.mark.asyncio
    async def test_action_confidence_exactly_at_threshold_matches(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Exact Action",
            enabled=True,
            severity=AlertSeverity.HIGH,
            action_types=["loitering"],
            action_confidence_threshold=0.7,
            cooldown_seconds=300,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        action = ActionResult(
            id=1, detection_id=1, action="loitering", confidence=0.7,
            is_suspicious=True, all_scores={"loitering": 0.7},
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [action]
        mock_session.execute.return_value = mock_result
        engine = AlertRuleEngine(mock_session)
        matches, _, _ = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )
        assert matches is True

    @pytest.mark.asyncio
    async def test_smoke_fire_confidence_exactly_at_threshold_matches(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Exact Smoke Conf",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            smoke_fire_detection_enabled=True,
            smoke_fire_confidence_threshold=0.9,
            cooldown_seconds=0,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        smoke = MagicMock()
        smoke.confidence = 0.9  # exactly the threshold
        smoke.detection_type = "smoke"  # consecutive_count left as MagicMock (non-numeric)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [smoke]
        mock_session.execute.return_value = mock_result
        engine = AlertRuleEngine(mock_session)
        matches, _, _ = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )
        assert matches is True

    @pytest.mark.asyncio
    async def test_smoke_fire_consecutive_exactly_at_required_matches(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Exact Smoke Count",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            smoke_fire_detection_enabled=True,
            smoke_fire_consecutive_required=2,
            cooldown_seconds=0,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        smoke = MagicMock()
        smoke.confidence = 0.95
        smoke.consecutive_count = 2  # exactly the requirement
        smoke.detection_type = None  # only the consecutive branch may return True
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [smoke]
        mock_session.execute.return_value = mock_result
        engine = AlertRuleEngine(mock_session)
        matches, _, _ = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )
        assert matches is True

    @pytest.mark.asyncio
    async def test_threat_severity_exactly_at_min_matches(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Min High",
            enabled=True,
            severity=AlertSeverity.HIGH,
            threat_detection_enabled=True,
            threat_min_severity="high",
            cooldown_seconds=0,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        threat = ThreatDetection(
            id=1, detection_id=1, threat_type="knife", confidence=0.9,
            severity="high", bbox=[0, 0, 1, 1],
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [threat]
        mock_session.execute.return_value = mock_result
        engine = AlertRuleEngine(mock_session)
        matches, _, _ = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )
        assert matches is True

    @pytest.mark.asyncio
    async def test_threat_confidence_exactly_at_threshold_matches(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Exact Threat Conf",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            threat_detection_enabled=True,
            threat_confidence_threshold=0.9,
            cooldown_seconds=0,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        threat = ThreatDetection(
            id=1, detection_id=1, threat_type="gun", confidence=0.9,
            severity="critical", bbox=[0, 0, 1, 1],
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [threat]
        mock_session.execute.return_value = mock_result
        engine = AlertRuleEngine(mock_session)
        matches, _, _ = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )
        assert matches is True
```

### T5 — `TestRejectionSkipsOnlyThatCandidate` (3 tests)

Target file: `backend/tests/unit/services/test_alert_engine_new_conditions.py`. Kills cluster 9 (4).

```python
class TestRejectionSkipsOnlyThatCandidate:
    """WP4.4: a rejected candidate must `continue`, not `break` — later candidates still match.

    // UNVERIFIED - not yet run red/green
    """

    @pytest.mark.asyncio
    async def test_threat_below_severity_then_matching_threat(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Critical Only",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            threat_detection_enabled=True,
            threat_min_severity="critical",
            cooldown_seconds=0,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        threats = [
            ThreatDetection(id=1, detection_id=1, threat_type="knife", confidence=0.99,
                            severity="high", bbox=[0, 0, 1, 1]),   # rejected (severity)
            ThreatDetection(id=2, detection_id=1, threat_type="gun", confidence=0.99,
                            severity="critical", bbox=[0, 0, 1, 1]),  # must still match
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = threats
        mock_session.execute.return_value = mock_result
        engine = AlertRuleEngine(mock_session)
        matches, _, _ = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )
        assert matches is True

    @pytest.mark.asyncio
    async def test_threat_below_confidence_then_matching_threat(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="High Conf Threats",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            threat_detection_enabled=True,
            threat_confidence_threshold=0.95,
            cooldown_seconds=0,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        threats = [
            ThreatDetection(id=1, detection_id=1, threat_type="gun", confidence=0.5,
                            severity="critical", bbox=[0, 0, 1, 1]),  # rejected (confidence)
            ThreatDetection(id=2, detection_id=1, threat_type="gun", confidence=0.99,
                            severity="critical", bbox=[0, 0, 1, 1]),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = threats
        mock_session.execute.return_value = mock_result
        engine = AlertRuleEngine(mock_session)
        matches, _, _ = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )
        assert matches is True

    @pytest.mark.asyncio
    async def test_smoke_fire_rejected_results_do_not_abort_scan(
        self, mock_session: AsyncMock, sample_event: MagicMock, sample_detections: list[Detection]
    ) -> None:
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Smoke Multi",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            smoke_fire_detection_enabled=True,
            smoke_fire_consecutive_required=2,
            smoke_fire_confidence_threshold=0.9,
            cooldown_seconds=0,
            dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        r1 = MagicMock()  # rejected on confidence
        r1.confidence = 0.5
        r1.consecutive_count = 1
        r1.detection_type = "smoke"
        r2 = MagicMock()  # rejected on consecutive count
        r2.confidence = 0.95
        r2.consecutive_count = 1
        r2.detection_type = None
        r3 = MagicMock()  # meets everything
        r3.confidence = 0.95
        r3.consecutive_count = 2
        r3.detection_type = None
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [r1, r2, r3]
        mock_session.execute.return_value = mock_result
        engine = AlertRuleEngine(mock_session)
        matches, _, _ = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )
        assert matches is True
```

### T6 — `TestThreatSeverityPriorityTable` (7 tests)

Target file: `backend/tests/unit/services/test_alert_engine_new_conditions.py`. Kills cluster 10 (8) and cluster 14 (1).

```python
class TestThreatSeverityPriorityTable:
    """WP4.4: unknown/absent severities must fall back to priority 0, never crash or silently shift.

    // UNVERIFIED - not yet run red/green
    """

    def _rule(self, **kw):  # noqa: ANN003
        base = dict(
            id=str(uuid.uuid4()), name="T", enabled=True,
            severity=AlertSeverity.HIGH, threat_detection_enabled=True,
            cooldown_seconds=0, dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        )
        base.update(kw)
        return AlertRule(**base)

    def _threat(self, severity, conf=0.99):  # noqa: ANN001, ANN003
        return ThreatDetection(
            id=1, detection_id=1, threat_type="gun", confidence=conf,
            severity=severity, bbox=[0, 0, 1, 1],
        )

    @pytest.mark.asyncio
    async def test_unknown_rule_min_severity_falls_back_to_zero_and_matches_critical(
        self, mock_session, sample_event, sample_detections
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [self._threat("critical")]
        mock_session.execute.return_value = mock_result
        engine = AlertRuleEngine(mock_session)
        matches, _, _ = await engine._evaluate_rule(
            self._rule(threat_min_severity="bogus"), sample_event, sample_detections,
            datetime.now(UTC),
        )
        assert matches is True

    @pytest.mark.asyncio
    async def test_unknown_rule_min_severity_does_not_filter_low_threats(
        self, mock_session, sample_event, sample_detections
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [self._threat("low")]
        mock_session.execute.return_value = mock_result
        engine = AlertRuleEngine(mock_session)
        matches, _, _ = await engine._evaluate_rule(
            self._rule(threat_min_severity="bogus"), sample_event, sample_detections,
            datetime.now(UTC),
        )
        assert matches is True

    @pytest.mark.asyncio
    async def test_unset_min_severity_allows_low_threats(
        self, mock_session, sample_event, sample_detections
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [self._threat("low")]
        mock_session.execute.return_value = mock_result
        engine = AlertRuleEngine(mock_session)
        matches, _, _ = await engine._evaluate_rule(
            self._rule(), sample_event, sample_detections, datetime.now(UTC)
        )
        assert matches is True

    @pytest.mark.asyncio
    async def test_unknown_threat_severity_with_no_filter_matches(
        self, mock_session, sample_event, sample_detections
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [self._threat("mystery")]
        mock_session.execute.return_value = mock_result
        engine = AlertRuleEngine(mock_session)
        matches, _, _ = await engine._evaluate_rule(
            self._rule(), sample_event, sample_detections, datetime.now(UTC)
        )
        assert matches is True

    @pytest.mark.asyncio
    async def test_unknown_threat_severity_is_below_medium_filter(
        self, mock_session, sample_event, sample_detections
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [self._threat("mystery")]
        mock_session.execute.return_value = mock_result
        engine = AlertRuleEngine(mock_session)
        matches, _, _ = await engine._evaluate_rule(
            self._rule(threat_min_severity="medium"), sample_event, sample_detections,
            datetime.now(UTC),
        )
        assert matches is False

    @pytest.mark.asyncio
    async def test_known_critical_threat_satisfies_medium_filter(
        self, mock_session, sample_event, sample_detections
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [self._threat("critical")]
        mock_session.execute.return_value = mock_result
        engine = AlertRuleEngine(mock_session)
        matches, _, _ = await engine._evaluate_rule(
            self._rule(threat_min_severity="medium"), sample_event, sample_detections,
            datetime.now(UTC),
        )
        assert matches is True

    @pytest.mark.asyncio
    async def test_action_result_with_none_action_skips_gracefully(
        self, mock_session, sample_event, sample_detections
    ) -> None:
        rule = AlertRule(
            id=str(uuid.uuid4()), name="NoneAction", enabled=True,
            severity=AlertSeverity.HIGH, action_types=["loitering"],
            cooldown_seconds=300, dedup_key_template="{camera_id}:{rule_id}",
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        )
        action = ActionResult(
            id=1, detection_id=1, action=None, confidence=0.95,
            is_suspicious=True, all_scores={},
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [action]
        mock_session.execute.return_value = mock_result
        engine = AlertRuleEngine(mock_session)
        matches, _, _ = await engine._evaluate_rule(
            rule, sample_event, sample_detections, datetime.now(UTC)
        )
        assert matches is False  # must not raise (mutant or-flip does None.lower())
```

## Kill accounting for drafts

- Drafted and killable: clusters 1 (22) + 2 (7) + 3 (12) + 6 dwell/load (14) + 7 dwell/load (12) + 8 (7) + 9 (4) + 10 (8) + 13 (4) + 14 (1) + 16 (2) + 18 (1) = **94** mutants by T1–T6.
- TEST-GAP left without a full draft:
  - Cluster 6 remainder (4) + cluster 7 remainder (12): apply T3's `_capturing_session` + `str(stmt)` predicate checks inside the existing pose/action/threat/smoke tests in `test_alert_engine_new_conditions.py` — mechanical extension, not new logic.
  - Cluster 11 (4): kill recipe — (a) rule **without** `smoke_fire_consecutive_required` + `consecutive_count = 2` → expect `matches is True` (kills \_11 crash and \_12 2→3); (b) `detection_type = "fire"`, no numeric `consecutive_count` → expect True (kills \_33, \_34). Can be folded into T5's smoke test as two extra cases.
  - Cluster 12 (2): `inspect()` bypass needs a real instrumented SQLAlchemy Event (the mock path is indistinguishable); belongs in `backend/tests/integration/` or a test constructing a transient `Event(**…)` instance, asserting `session.execute` is skipped for a loaded relationship.
  - Cluster 19 (1): add `detection_type = "vapor"` (str, non-listed) expected no-match case to a smoke test.
- EQUIVALENT (no tests warranted): 15. LOW-VALUE (optional `caplog` assertions): 8.

## Notes for WP4.4

- The single highest-leverage fix is clusters 1+2+3+18: T1/T2 together kill **42** mutants (30% of this module's survivors). The webhook payload is an outward-facing contract (consumers key on these JSON fields) and currently zero of it is asserted.
- Clusters 6+7 (42 mutants) share one root cause: mocked `session.execute` ignores the statement. A shared helper (e.g. `assert_sql(stmt, "dwell_time_records", ["zone_id =", "exit_time IS NULL"])`) in a conftest would let every existing condition test shed its SQL blindness cheaply; same idea already used in `test_query_optimization.py` (single-query counting).
- Cluster 8 (7) is the classic "strictly-above/below-only fixtures" gap — one at-equality case per threshold closes it. Existing `_check_min_confidence` in test_alert_engine.py (`test_returns_true_when_exactly_at_threshold`, line 442) shows the pattern the newer condition tests never copied.
- `tests_by_mangled_function_name` shows `_check_dwell_time` coverage points at `test_alert_engine.py:1882` (zone-based implementation); the skipped `TestDwellTimeCondition` in `test_alert_engine_new_conditions.py:116` is dead weight, not protection.
- Incidental finding (not a mutant): `_check_smoke_fire` uses `except TypeError, AttributeError:` (bare comma, no parens) at backend/services/alert_engine.py:843,858,869 — valid only because the project runs Python 3.14 (PEP 758 relaxed the parens requirement); it compiles on the sandbox's 3.14.4 but would be a SyntaxError on any ≤3.13 runtime. Flag for the language-level audit, not for test work.
