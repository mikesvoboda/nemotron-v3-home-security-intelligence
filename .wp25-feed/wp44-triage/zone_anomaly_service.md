# WP4.4 Triage Dossier — backend/services/zone_anomaly_service.py

**Run state (meta snapshot taken this session):** 527 mutant keys — 103 killed, **137 survived**, 287 unchecked.
The unchecked blocks are `_check_unusual_time` (114), `_check_unusual_dwell` (102), `_emit_websocket_event` (59),
`__init__`/`_deviation_to_severity`/`_persist_and_emit` (4/4/4) — survivors in those functions cannot be triaged
until first verdicts land. All 137 *current* survivors: `_check_unusual_frequency` 62, `check_detection` 39,
`get_anomaly_counts_by_zone` 17, `get_anomalies_for_zone` 12, `acknowledge_anomaly` 6, `reset_zone_anomaly_service` 1.
Diff source: `uv run mutmut show <key>` for all 137 (raw dump: /tmp/wp25/zone_diffs.txt).

**Covering test file (every function, per `mutants/mutmut-stats.json` tests_by_mangled_function_name):**
`backend/tests/unit/services/test_zone_anomaly_service.py`

| Area | Class / lines | What it asserts | Why mutants survive |
|---|---|---|---|
| `_check_unusual_frequency` | `TestCheckUnusualFrequency` L196–285; `TestAdditionalCoverage.test_check_unusual_frequency_without_timestamp` L983–1002 | only `result is None` / `anomaly_type` / tracker `len()` | anomaly payload never inspected; tracker tuple contents never inspected; window never boundary-tested; baseline/detection attrs always present |
| `check_detection` | `TestCheckDetection` L399–488; `TestAdditionalCoverage.test_check_detection_with_normal_values` L1029–1063 | `result.severity in [WARNING, CRITICAL]` (set membership); `_persist_and_emit` patched bare `AsyncMock` | winner identity/order never asserted; persist call args never checked; sub-check call signatures unchecked (plain MagicMock accepts anything); baseline always has `sample_count` |
| `get_anomalies_for_zone` | `TestGetAnomaliesForZone` L688–750; `TestAdditionalCoverage` L1065–1089 | canned AsyncMock return + `execute.assert_called_once()` | the query object handed to `session.execute` is never examined → all WHERE/ORDER mutations invisible |
| `acknowledge_anomaly` | `TestAcknowledgeAnomaly` L753–798 | mock row returned regardless of query | same — query shape unchecked |
| `get_anomaly_counts_by_zone` | `TestGetAnomalyCountsByZone` L801–827; `TestAdditionalCoverage` L1091–1123 | canned rows; `pytest.raises(match="session is required")` (substring — passes even on `"XXsession is requiredXX"`) | query shape unchecked; match too loose |
| `reset_zone_anomaly_service` | `TestZoneAnomalySingleton` L835–864 | identity of two `get()` results | `""` (mutant) behaves like a singleton too unless type is asserted |

**Facts used in classification** (verified this session):
- `ZoneAnomaly` (`backend/models/zone_anomaly.py` L61–113) is plain declarative (no custom `__init__`);
  `id` String PK **no default** → dropping `id=` leaves it None; unit tests never flush, so `nullable=False`
  never bites — field corruption is only visible through asserts on the returned object.
- `uuid.UUID(uuid_instance)` raises `AttributeError` ⇒ freq mutant 20 (`isinstance(...) or True`) is a real crash
  path for non-str `zone.id`, not equivalent.
- `select(...).where(None)` compiles to `WHERE NULL` (no error) — silently matches nothing.
- `order_by(None)`/`group_by(None)` **clear** the clause — unordered / single-group results.

---

## Cluster table (34 clusters, counts sum to 137)

Key keys below are `__mutmut_N` numbers within the named function.

### `_check_unusual_frequency` (62)

| Cluster | N | Keys | Class | Kill vector |
|---|---|---|---|---|
| F1 freq_getattr_local — getattr target/attrname/fallback mangled (or whole call → None) on `timestamp`, `detection_id` local, `typical_rate`, `typical_std` | 20 | 7,10,14,15,16,22,23,25,28,29,30,31,41,43,46,49,51,53,56,59 | TEST-GAP | Tests always hand a full MagicMock baseline+detection ⇒ the fallback branches (defaults 10.0/5.0, `id(detection)`, attr-name lookup) are never exercised; deviations never asserted. Sub-shapes: target→None (10,23,41,51), attr-name mangle (15,16,29,30), fallback value mangled (22 const-None, 25/31 fallback, 43/46/53/56 fallback→None/removed, 49→11.0, 59→6.0). Trailing-comma "3rd getattr arg removed" mutants (7,14,28) differ only for *attribute-absent* objects — spec'd-mock leg in T2-absent kills them (AttributeError vs default). |
| F2 freq_getattr_field — same getattr mangling inside the `ZoneAnomaly(...)` kwargs (`detection_id=`, `thumbnail_url=`) | 8 | 97,101,102,103,104,108,109,110 | TEST-GAP | T1 payload asserts (`result.detection_id == 999`, `result.thumbnail_url == ...`). |
| F3 freq_field_none — constructor field hard-set to `None` (id, zone_id, camera_id, severity, title, description, expected/actual/deviation, detection_id, thumbnail_url, timestamp) | 12 | 70,71,72,74,75,76,77,78,79,80,81,82 | TEST-GAP | T1: assert every payload field. |
| F4 freq_kwarg_drop — constructor keyword deleted entirely (attr falls to None/model-default) | 12 | 83,84,85,87,88,89,90,91,92,93,94,95 | TEST-GAP | T1 (same asserts; `id` PK has no default → None ≠ uuid str). |
| F5 freq_cutoff_math — `cutoff = timestamp - timedelta(hours=1)` → `+ hours=1` / `- hours=2` | 2 | 33,35 | TEST-GAP | Existing cleanup test (L255–285) uses 2.5–3.5h-old entries, len==1 either way. T2-window with a 60-min boundary entry. |
| F6 freq_cutoff_op — tracker filter `ts > cutoff` → `ts >= cutoff` | 1 | 37 | TEST-GAP | Needs an entry exactly on cutoff; T2-window. |
| F7 freq_anom_id_local — `anomaly_id = str(uuid.uuid4())` → None / `str(None)` ("None") | 2 | 68,69 | TEST-GAP | T1 asserts `result.id` parses as UUID and != "None". |
| F8 freq_append_none — tracker `append((ts, detection_id))` → `append(None)` | 1 | 38 | TEST-GAP | len still trips threshold (19 seeded); T2-window asserts tuple contents. |
| F9 freq_std_clamp — `if typical_std <= 0` → `< 0` / `<= 1` | 2 | 60,61 | TEST-GAP | No test uses `typical_crossing_std` ≤ 0 (or ≤ 1): clamp branch dead in suite. T2-zerostd (std=0 → divide-by-zero on mutant `<0`; wrong deviation on `<=1`). |
| F10 freq_thresh_op — anomaly gate `deviation < threshold` → `<=` | 1 | 65 | TEST-GAP | deviation exactly == threshold never built; T2-boundary. |
| F11 freq_uuid_ternary — `uuid.UUID(zone.id) if isinstance(zone.id, str)` → `... or True` | 1 | 20 | TEST-GAP | All tests pass str zone.id; UUID-object path (verified crash) never taken. T2-zerostd uses UUID id. |

### `check_detection` (39)

| Cluster | N | Keys | Class | Kill vector |
|---|---|---|---|---|
| D1 cd_sev_critical_rank — map `CRITICAL: 0→1` (ties with WARNING) | 1 | 52 | TEST-GAP | Scenario A (T4): CRITICAL anomaly inserted *after* WARNING; tie → insertion order → wrong winner. Current test's set-membership assert blind. |
| D2 cd_sev_warning_rank — map `WARNING: 1→2` (ties with INFO) | 1 | 53 | TEST-GAP | Scenario B (T4): only INFO(time) + WARNING(freq) — WARN inserted later; tie → wrong winner. |
| D3 cd_sev_info_rank — map `INFO: 2→3` | 1 | 54 | **EQUIVALENT** | Rank 3 vs 2 is order-indistinguishable from all other ranks (0,1, default 99); no observable behavior change. |
| D4 cd_sort_key_arg — `severity_order.get(a.severity, 99)` → `.get(None, 99)` (all anomalies tie) | 1 | 57 | TEST-GAP | Stable sort falls back to insertion order; T4 scenario A/B (winner = first inserted ≠ most severe). |
| D5 cd_sort_default_none — sort fallback default → None / dropped (→None) | 2 | 58,60 | TEST-GAP | Unknown severity string → key None → `TypeError` comparing None to ints. T4-unknown: one anomaly with `severity="bogus"` must still sort last, not raise. |
| D6 cd_sort_default_100 — fallback default `99 → 100` | 1 | 61 | **EQUIVALENT** | Both > 2 for every known severity; integer ranks leave no gap — unobservable. |
| D7 cd_pick_second — `most_severe = anomalies[0]` → `anomalies[1]` | 1 | 63 | TEST-GAP | T4 scenario A asserts exact returned object. |
| D8 cd_persist_args — `_persist_and_emit` call mangled: anomaly→None; session→None; session kwarg dropped (falls to None → new-session path); anomaly kwarg dropped | 4 | 64,65,66,67 | TEST-GAP | Existing test patches the method with bare AsyncMock and never checks call args. T4: `assert_called_once_with(result, session=mock_session)` + sub-check arg capture. |
| D9 cd_subcheck_result_none — `time/freq/dwell_anomaly = None` (check skipped) | 3 | 21,31,40 | TEST-GAP | Existing "most severe" test passes because dwell alone stays CRITICAL. T4: exact-winner + only-one-anomaly scenarios. |
| D10 cd_callarg_mangle — call-site args mangled for `get_baseline` and each sub-check (arg→None, `session=` kwarg dropped, positional shifts, trailing-arg drop) | 21 | 4,5,7,22,24,26,27,28,29,32,34,36,37,38,39,41,43,45,46,47,48 | TEST-GAP | Plain `MagicMock`/`AsyncMock` sub-checks swallow shifted args; unpatched real sub-checks hit `getattr()` on shifted MagicMocks that mostly return MagicMocks. No test verifies the call signature/args. T4 captures call tuples: `assert calls == [(detection, zone, baseline, threshold)]`, `get_baseline` called with `(zone.id, session=mock_session)`. |
| D11 cd_sample_count_default — `getattr(baseline, "sample_count", 0)` default → None / dropped / → 1 | 3 | 11,14,17 | TEST-GAP | Baselines in tests always *have* sample_count; the "unknown sample count = no data" contract (default 0) never tested. T4-missing: baseline without the attr must yield None (mutants proceed). |

### Query methods (35)

| Cluster | N | Keys | Class | Kill vector |
|---|---|---|---|---|
| Q1 gafz_where_mangle — `get_anomalies_for_zone` WHERE mutations: `where(None)` (matches nothing), `select(None)`, `zone_id ==` → `!=` / `str(None)`, `timestamp >=` → `where(None)` / `>` , `acknowledged == False` → None / `!= False` / `== True` | 9 | 2,3,4,5,8,9,11,12,13 | TEST-GAP | AsyncMock never sees the SQL; tests assert only call count / canned rows. T3a compiles the captured query and asserts SQL fragments. |
| Q2 gafz_order_drop — `order_by(ZoneAnomaly.timestamp.desc())` → `query = None` / `order_by(None)` (clause cleared) | 2 | 14,15 | TEST-GAP | T3a: assert captured query is a Select with a desc timestamp ORDER BY (a cleared `order_by(None)` yields no ORDER BY). |
| Q3 gafz_execute_none — `session.execute(query)` → `execute(None)` | 1 | 18 | TEST-GAP | Real crash in production, invisible under AsyncMock; assert `execute.call_args[0][0]` is the Select (folded into T3a). |
| Q4 ack_query_mangle — `acknowledge_anomaly` query mutations: `query = None`, `where(None)`, `select(None)`, `id ==` → `!=` / `str(None)` | 5 | 2,3,4,5,6 | TEST-GAP | T3c: compiled SQL must contain `zone_anomalies.id = '<uuid>'`. |
| Q5 ack_execute_none — `execute(query)` → `execute(None)` | 1 | 8 | TEST-GAP | T3c call-arg assert. |
| Q6 gacz_where_mangle — `get_anomaly_counts_by_zone` WHERE mutations: `timestamp >=` → None / `>`; `acknowledged == False` → None / `!= False` / `== True` | 5 | 12,13,15,16,17 | TEST-GAP | T3b SQL fragment asserts. |
| Q7 gacz_group_drop — `group_by(ZoneAnomaly.zone_id)` → `query = None` / `group_by(None)` (one lump group) | 2 | 18,19 | TEST-GAP | T3b: captured query must carry exactly one GROUP BY column == zone_id. |
| Q8 gacz_select_cols — select-list mutations: `select(None, count)`, count→None, zone_id column dropped, `count(None)` | 5 | 2,3,4,5,7 | TEST-GAP | T3b: assert SELECT contains `zone_anomalies.zone_id` and `count(zone_anomalies.id)`. |
| Q9 gacz_label_text — `.label("count")` → None / "XXcountXX" / "COUNT" | 3 | 6,8,9 | **LOW-VALUE** | Result rows are read positionally (`row[0]/row[1]`, L494); the label name is never observed anywhere. Asserting it would pin a cosmetic. Leave surviving (or note: `pytest.raises` match tightening belongs to Q10). |
| Q10 gacz_exc_text — `raise ValueError("session is required")` → `"XXsession is requiredXX"` | 1 | 22 | TEST-GAP | Existing `pytest.raises(match="session is required")` (L1122) passes via substring. Fix: `match="^session is required$"` (or `==` on `excinfo.value.args[0]`). |
| Q11 gacz_execute_none — `execute(query)` → `execute(None)` | 1 | 25 | TEST-GAP | T3b call-arg assert (same pattern as Q3/Q5). |

### Module level (1)

| Cluster | N | Keys | Class | Kill vector |
|---|---|---|---|---|
| S1 reset_singleton_falsy — `reset_zone_anomaly_service()` sets `_zone_anomaly_service = ""` instead of None | 1 | x_reset_zone_anomaly_service__mutmut_1 | TEST-GAP | `get_zone_anomaly_service()` checks `is None`; `""` slips past and is returned as "the service". Identity test can't see it (two `""`s can be identical by interning). T5 asserts `mod._zone_anomaly_service is None` and `isinstance(get(), ZoneAnomalyService)`. |

**Classification totals:** TEST-GAP 32 clusters / 132 mutants; EQUIVALENT 2 clusters / 2 mutants (D3, D6);
LOW-VALUE 1 cluster / 3 mutants (Q9). Sum 137 = survivors_total.

---

## Drafted tests (highest-value clusters)

All **UNVERIFIED — not yet run red/green**. TDD procedure (same for every test below): run it against the
mutant variant (`mutmut`'s mutated module) — the specific assert must FAIL on the mutant diff; run against
`backend/services/zone_anomaly_service.py` original — must PASS. Then keep it in the suite as the cluster killer.
Style follows the existing file: MagicMock detection/zone/baseline, `@pytest.mark.asyncio`, `patch.object`.

New class `TestFrequencyPayloadAndWindow` targets `TestCheckUnusualFrequency` (L196); new class
`TestQueryShape` next to `TestGetAnomaliesForZone` (L688); `TestCheckDetectionWinner` next to
`TestCheckDetection` (L399); singleton addition in `TestZoneAnomalySingleton` (L835).

### T1 — full frequency-anomaly payload contract → kills F2(8) F3(12) F4(12) F7(2) and part of F1 (41,51)

```python
class TestFrequencyPayloadAndWindow:
    """WP4.4: frequency anomaly payload + window semantics (kills field/kwarg/getattr mutants)."""

    @pytest.mark.asyncio
    async def test_high_frequency_anomaly_payload_is_fully_populated(self) -> None:
        """Every ZoneAnomaly field must be populated and numerically correct."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()
        zone_id = uuid.uuid4()
        base_time = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
        service._frequency_tracker[zone_id] = [
            (base_time - timedelta(minutes=i), i) for i in range(1, 20)
        ]

        detection = MagicMock()
        detection.detected_at = base_time
        detection.id = 999
        detection.thumbnail_path = "/thumbnails/det_999.jpg"

        zone = MagicMock()
        zone.id = str(zone_id)
        zone.camera_id = "front_door"
        zone.name = "Front Yard"

        baseline = MagicMock()
        baseline.typical_crossing_rate = 0.5
        baseline.typical_crossing_std = 0.1

        result = await service._check_unusual_frequency(detection, zone, baseline, threshold=2.0)

        assert result is not None
        assert result.id is not None and result.id != "None"
        uuid.UUID(result.id)  # real uuid4 string (kills 68/69, 83)
        assert result.zone_id == zone.id  # kills 71, 84
        assert result.camera_id == "front_door"  # kills 72, 85
        assert result.anomaly_type == AnomalyType.UNUSUAL_FREQUENCY
        assert result.severity == AnomalySeverity.CRITICAL.value  # kills 74, 87 (deviation 195)
        assert result.title == "High activity frequency in Front Yard"  # kills 75, 88
        assert result.description is not None and "20 crossings" in result.description  # 76, 89
        assert result.expected_value == pytest.approx(0.5)  # kills 77, 90, 41, 51 (would be 10.0)
        assert result.actual_value == pytest.approx(20.0)  # kills 78, 91
        assert result.deviation == pytest.approx((20 - 0.5) / 0.1)  # kills 79, 92, 49(→11.0), 59(→6.0)
        assert result.detection_id == 999  # kills 80, 93, 97, 101, 102, 103
        assert result.thumbnail_url == "/thumbnails/det_999.jpg"  # kills 81, 94, 104, 108, 109, 110
        assert result.timestamp == base_time  # kills 82, 95
        # UNVERIFIED - not yet run red/green
```

### T2 — window semantics, tracker tuples, getattr fallback legs, std clamp, threshold equality, UUID zone ids
→ kills F1 (sub-legs, see per-key notes), F5, F6, F8, F9, F10, F11

Key→leg map for F1's 20: 41,51 → T1 (`expected_value`/`deviation` assert); 22,23,29,30 → T2a tuple assert
(detection.id present); 25,28,31 → T2d absent-id leg; 7 → T2b (spec'd detection without `detected_at` →
AttributeError vs default); 14 → T2e (both attrs absent → None; mutant raises); 15,16 → T2b (attr name);
43,46,53,56 → T2c (baseline attrs absent → TypeError/AttributeError vs documented defaults);
49,59 → T2c (defaults 11.0/6.0 shift deviation below threshold → None vs anomaly).

```python
    @pytest.mark.asyncio
    async def test_frequency_window_boundary_prunes_exactly_one_hour_old(self) -> None:
        """Entry exactly 1h old sits on cutoff: strict `ts > cutoff` prunes it, `>=` keeps it.
        Also pins the tracker tuple payload (kills append(None) and detection_id mangling)."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()
        zone_id = uuid.uuid4()
        current_time = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
        service._frequency_tracker[zone_id] = [(current_time - timedelta(hours=1), 1)]

        detection = MagicMock()
        detection.detected_at = current_time
        detection.id = 55
        detection.thumbnail_path = None

        zone = MagicMock()
        zone.id = str(zone_id)
        zone.camera_id = "front_door"
        zone.name = "Front Yard"
        baseline = MagicMock()
        baseline.typical_crossing_rate = 10.0
        baseline.typical_crossing_std = 5.0

        await service._check_unusual_frequency(detection, zone, baseline, threshold=2.0)

        entries = service._frequency_tracker[zone_id]
        assert len(entries) == 1  # mutant 37 (>=): boundary entry kept -> len 2 -> red
        assert entries[0] == (current_time, 55)  # kills 38 (None), 22, 23, 29, 30
        # UNVERIFIED - not yet run red/green

    @pytest.mark.asyncio
    async def test_frequency_cutoff_window_is_exactly_one_hour(self) -> None:
        """90-min-old entry: original cutoff (ts-1h) prunes it; +1h cutoff prunes the fresh entry
        on the next call; -2h cutoff keeps the stale one. Two calls, one seeded stale entry."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()
        zone_id = uuid.uuid4()
        t1 = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
        service._frequency_tracker[zone_id] = [(t1 - timedelta(minutes=90), 1)]

        zone = MagicMock()
        zone.id = str(zone_id)
        zone.camera_id = "front_door"
        zone.name = "Front Yard"
        baseline = MagicMock()
        baseline.typical_crossing_rate = 10.0
        baseline.typical_crossing_std = 5.0

        d1 = MagicMock()
        d1.detected_at = t1
        d1.id = 1
        await service._check_unusual_frequency(d1, zone, baseline, threshold=2.0)
        # mutant 35 (-2h): cutoff 12:30 keeps the 13:00 entry -> len 2 -> red

        d2 = MagicMock()
        d2.detected_at = t1 + timedelta(seconds=30)
        d2.id = 2
        await service._check_unusual_frequency(d2, zone, baseline, threshold=2.0)
        # mutant 33 (+1h): second call's cutoff is in the future -> prunes the 14:30 entry too
        assert len(service._frequency_tracker[zone_id]) == 2  # original: 14:30 + 14:30:30
        # UNVERIFIED - not yet run red/green

    @pytest.mark.asyncio
    async def test_frequency_timestamp_fallback_when_detected_at_absent(self) -> None:
        """Detection WITHOUT `detected_at` attribute must fall back to `timestamp`."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()
        zone_id = uuid.uuid4()
        base_time = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)

        detection = MagicMock(spec=["timestamp", "id", "thumbnail_path"])
        detection.timestamp = base_time
        detection.id = 1
        detection.thumbnail_path = None

        zone = MagicMock()
        zone.id = str(zone_id)
        zone.camera_id = "front_door"
        zone.name = "Front Yard"
        baseline = MagicMock()
        baseline.typical_crossing_rate = 0.5
        baseline.typical_crossing_std = 0.1

        result = await service._check_unusual_frequency(detection, zone, baseline, threshold=2.0)
        assert result is not None
        assert result.timestamp == base_time  # kills 15,16 (attr name), 10 (getattr(None,...))
        # mutant 7 (`getattr(detection, "detected_at", )` -> no default on absent attr) ->
        # AttributeError -> red
        # UNVERIFIED - not yet run red/green

    @pytest.mark.asyncio
    async def test_frequency_returns_none_when_both_timestamp_attrs_absent(self) -> None:
        """No detected_at AND no timestamp attr -> documented None, not an AttributeError."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()
        detection = MagicMock(spec=[])  # no attrs at all

        zone = MagicMock()
        zone.id = str(uuid.uuid4())
        baseline = MagicMock()
        baseline.typical_crossing_rate = 10.0
        baseline.typical_crossing_std = 5.0

        result = await service._check_unusual_frequency(detection, zone, baseline, threshold=2.0)
        assert result is None
        # mutant 14 drops the 2nd getattr default -> AttributeError on absent attr -> red
        # UNVERIFIED - not yet run red/green

    @pytest.mark.asyncio
    async def test_frequency_documented_defaults_when_baseline_attrs_absent(self) -> None:
        """Baseline without typical_crossing_* falls back to 10.0 / 5.0 (documented defaults)."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()
        zone_id = uuid.uuid4()
        base_time = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
        service._frequency_tracker[zone_id] = [
            (base_time - timedelta(minutes=i), i) for i in range(1, 20)
        ]

        detection = MagicMock()
        detection.detected_at = base_time
        detection.id = 1

        zone = MagicMock()
        zone.id = str(zone_id)
        zone.camera_id = "front_door"
        zone.name = "Front Yard"
        baseline = MagicMock(spec=[])  # NO attributes

        result = await service._check_unusual_frequency(detection, zone, baseline, threshold=2.0)
        # defaults rate 10.0 std 5.0 -> deviation (20-10)/5 = 2.0 -> gate `2.0 < 2.0` False -> anomaly
        assert result is not None
        assert result.expected_value == pytest.approx(10.0)
        # mutants 43/53 (fallback -> None): TypeError on arithmetic -> red
        # mutants 46/56 (3rd getattr arg dropped): AttributeError -> red
        # mutants 49 (rate 11.0) / 59 (std 6.0): deviation 1.8/1.67 < 2 -> result None -> red
        # UNVERIFIED - not yet run red/green

    @pytest.mark.asyncio
    async def test_frequency_deviation_exactly_at_threshold_is_anomaly(self) -> None:
        """deviation == threshold must still flag (gate is `deviation < threshold`)."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()
        zone_id = uuid.uuid4()
        base_time = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
        service._frequency_tracker[zone_id] = [(base_time - timedelta(minutes=10), 1)]

        detection = MagicMock()
        detection.detected_at = base_time
        detection.id = 77

        zone = MagicMock()
        zone.id = str(zone_id)
        zone.camera_id = "front_door"
        zone.name = "Front Yard"
        baseline = MagicMock()
        baseline.typical_crossing_rate = 0.0
        baseline.typical_crossing_std = 1.0  # (2-0)/1 == 2.0 == threshold

        result = await service._check_unusual_frequency(detection, zone, baseline, threshold=2.0)
        assert result is not None  # mutant 65 (`<=`) returns None -> red
        # UNVERIFIED - not yet run red/green

    @pytest.mark.asyncio
    async def test_frequency_zero_std_clamps_uuid_zone_id_and_small_std_not_clamped(self) -> None:
        """std<=0 clamps to 1.0; std=0.5 must NOT be clamped; UUID zone.id must not crash."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        zone_id = uuid.uuid4()  # UUID object, NOT str -> ternary else-branch
        base_time = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)

        def make(detection_id: int):
            detection = MagicMock()
            detection.detected_at = base_time
            detection.id = detection_id
            zone = MagicMock()
            zone.id = zone_id  # raw UUID
            zone.camera_id = "front_door"
            zone.name = "Front Yard"
            return detection, zone

        # leg 1: std 0.0 must clamp to 1.0 (no ZeroDivisionError), deviation 1.0 -> None
        service = ZoneAnomalyService()
        detection, zone = make(88)
        baseline = MagicMock()
        baseline.typical_crossing_rate = 0.0
        baseline.typical_crossing_std = 0.0
        result = await service._check_unusual_frequency(detection, zone, baseline, threshold=2.0)
        assert result is None
        assert service._frequency_tracker[zone_id]  # keyed under the raw UUID
        # mutant 20 (`isinstance(...) or True`): uuid.UUID(UUID) raises AttributeError (verified) -> red
        # mutant 60 (clamp `< 0`): std stays 0.0 -> ZeroDivisionError -> red

        # leg 2: std 0.5 is above 0 -> NOT clamped; deviation (1-0)/0.5 == 2.0 -> anomaly
        service2 = ZoneAnomalyService()
        detection2, zone2 = make(89)
        baseline2 = MagicMock()
        baseline2.typical_crossing_rate = 0.0
        baseline2.typical_crossing_std = 0.5
        result2 = await service2._check_unusual_frequency(detection2, zone2, baseline2, threshold=2.0)
        assert result2 is not None
        assert result2.deviation == pytest.approx(2.0)
        # mutant 61 (clamp `<= 1`): 0.5 clamped to 1.0 -> deviation 1.0 -> None -> red
        # UNVERIFIED - not yet run red/green

    @pytest.mark.asyncio
    async def test_frequency_tracker_falls_back_to_object_id_when_detection_id_absent(self) -> None:
        """detection without `id` -> tracker stores `id(detection)`, not None/`id(None)`."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()
        zone_id = uuid.uuid4()
        base_time = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)

        detection = MagicMock(spec=[])  # no id attribute
        # spec=[] MagicMock also lacks detected_at -> give it just enough attrs instead:
        detection = MagicMock(spec=["detected_at"])
        detection.detected_at = base_time

        zone = MagicMock()
        zone.id = str(zone_id)
        zone.camera_id = "front_door"
        zone.name = "Front Yard"
        baseline = MagicMock()
        baseline.typical_crossing_rate = 10.0
        baseline.typical_crossing_std = 5.0

        await service._check_unusual_frequency(detection, zone, baseline, threshold=2.0)
        (ts, did), = service._frequency_tracker[zone_id]
        assert ts == base_time
        assert did == id(detection)  # kills 25/28 (fallback None/removed -> None stored)
        # kills 31 (`id(None)` stored) since id(None) != id(detection)
        # UNVERIFIED - not yet run red/green
```

Note: T2's last test overrides `detection` twice (spec=[] then spec=["detected_at"]) — collapse to the second
only when landing; left explicit for the red/green pass.


### T3 — captured-query SQL shape (kills Q1–Q8, Q10 tighten, Q3/Q5/Q11 call args)

```python
class TestQueryShape:
    """WP4.4: the query object reaching session.execute() is the real behavior under test."""

    @pytest.mark.asyncio
    async def test_get_anomalies_query_encodes_zone_since_order(self) -> None:
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()
        zone_id = uuid.uuid4()
        since = datetime(2026, 1, 20, 0, 0, 0, tzinfo=UTC)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        await service.get_anomalies_for_zone(
            zone_id, since=since, unacknowledged_only=True, session=mock_session
        )

        query = mock_session.execute.call_args[0][0]
        assert query is not None  # kills 18 (execute(None))
        sql = str(query.compile(compile_kwargs={"literal_binds": True})).lower()
        assert f"zone_anomalies.zone_id = '{zone_id}'" in sql  # kills 2,3,4,5
        assert "zone_anomalies.timestamp >=" in sql  # kills 8,9 (`>`/None flip)
        assert "acknowledged = false" in sql  # kills 11,12,13
        order_cols = list(query._order_by_clauses)  # kills 14 (query None -> line above), 15 (cleared)
        assert len(order_cols) == 1
        assert order_cols[0].expr.column.name == "timestamp"
        assert order_cols[0].expr.desc
        # UNVERIFIED - not yet run red/green

    @pytest.mark.asyncio
    async def test_anomaly_counts_query_encodes_select_group_where(self) -> None:
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()
        since = datetime(2026, 1, 20, 0, 0, 0, tzinfo=UTC)

        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        await service.get_anomaly_counts_by_zone(
            since=since, unacknowledged_only=True, session=mock_session
        )

        query = mock_session.execute.call_args[0][0]
        assert query is not None  # kills 25
        sql = str(query.compile(compile_kwargs={"literal_binds": True})).lower()
        assert "zone_anomalies.zone_id" in sql  # kills 2,4,5 (column drops)
        assert "count(zone_anomalies.id)" in sql  # kills 3,7
        assert "zone_anomalies.timestamp >=" in sql  # kills 12,13
        assert "acknowledged = false" in sql  # kills 15,16,17
        group_cols = list(query._group_by_clauses)  # kills 18 (query None), 19 (cleared)
        assert len(group_cols) == 1 and group_cols[0].name == "zone_id"
        # UNVERIFIED - not yet run red/green

    @pytest.mark.asyncio
    async def test_acknowledge_query_targets_exact_id(self) -> None:
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()
        anomaly_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        await service.acknowledge_anomaly(anomaly_id, session=mock_session)

        query = mock_session.execute.call_args[0][0]
        assert query is not None  # kills 8
        sql = str(query.compile(compile_kwargs={"literal_binds": True}))
        assert f"zone_anomalies.id = '{anomaly_id}'" in sql  # kills 2,3,4,5,6
        # UNVERIFIED - not yet run red/green
```

(Fallback if `literal_binds` string formatting proves brittle across SQLAlchemy versions: compare
`str(query._whereclause)` to an inline-built `str(ZoneAnomaly.zone_id == str(zone_id))` — decide at
red/green time. The Q10 fix is one line in the existing test L1122:
`match="^session is required$"`.)

### T4 — check_detection winner, persist call, sub-check signatures, missing sample_count
→ kills D1, D2, D4, D5, D7, D8, D9, D10, D11

```python
class TestCheckDetectionWinner:
    """WP4.4: severity ordering, persist call, and sub-check call contract of check_detection."""

    @staticmethod
    def _fake_anomaly(severity: str) -> MagicMock:
        obj = MagicMock()
        obj.severity = severity
        return obj

    @pytest.mark.asyncio
    async def test_three_anomalies_worst_is_returned_persisted_with_session(self) -> None:
        """Scenario A: INFO(time) inserted first, WARNING(freq), CRITICAL(dwell) last."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()
        detection = MagicMock()
        zone = MagicMock()
        zone.id = str(uuid.uuid4())
        baseline = MagicMock()
        baseline.sample_count = 100
        session = AsyncMock()

        time_a = self._fake_anomaly(AnomalySeverity.INFO.value)
        freq_a = self._fake_anomaly(AnomalySeverity.WARNING.value)
        dwell_a = self._fake_anomaly(AnomalySeverity.CRITICAL.value)
        bogus = self._fake_anomaly("bogus-severity")  # D5: fallback default must be an int (99)

        seen: list[tuple] = []

        async def fake_freq(*args, **kwargs):
            seen.append(("freq", args, kwargs))
            return freq_a

        async def fake_dwell(*args, **kwargs):
            seen.append(("dwell", args, kwargs))
            return dwell_a

        with patch.object(
            service._baseline_service, "get_baseline", return_value=baseline, autospec=True
        ) as get_bl:
            with patch.object(service, "_check_unusual_time", return_value=bogus) as chk_time:
                with patch.object(service, "_check_unusual_frequency", side_effect=fake_freq):
                    with patch.object(service, "_check_unusual_dwell", side_effect=fake_dwell):
                        with patch.object(
                            service, "_persist_and_emit", new_callable=AsyncMock
                        ) as persist:
                            result = await service.check_detection(
                                detection, zone, session=session, threshold=2.0
                            )

        assert result is dwell_a  # kills 63; D1 (tie CRIT/WARN -> freq_a); D4 (all-tie -> bogus);
                                  # D9 (21/31/40 change winners), D2 via scenario B below
        persist.assert_called_once_with(dwell_a, session=session)  # kills 64,65,66,67
        get_bl.assert_called_once_with(zone.id, session=session)  # kills 4,5,7
        chk_time.assert_called_once_with(detection, zone, baseline, 2.0)  # kills 22,24,26,27,28,29
        assert seen[0] == ("freq", (detection, zone, baseline, 2.0), {})  # kills 32,34,36,37,38,39
        assert seen[1] == ("dwell", (detection, zone, baseline, 2.0), {})  # kills 41,43,45,46,47,48
        # unknown severity sorts last via default 99; mutants 58/60 raise TypeError comparing
        # None to ints -> this call explodes on those mutants -> red. (D5)
        # UNVERIFIED - not yet run red/green

    @pytest.mark.asyncio
    async def test_warning_inserted_after_info_wins_by_severity_not_insertion(self) -> None:
        """Scenario B: only INFO(time) + WARNING(freq); D2 (WARN tied with INFO) flips the winner."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()
        detection = MagicMock()
        zone = MagicMock()
        zone.id = str(uuid.uuid4())
        baseline = MagicMock()
        baseline.sample_count = 100
        session = AsyncMock()

        time_a = self._fake_anomaly(AnomalySeverity.INFO.value)
        freq_a = self._fake_anomaly(AnomalySeverity.WARNING.value)

        async def fake_freq(*args, **kwargs):
            return freq_a

        with patch.object(
            service._baseline_service, "get_baseline", return_value=baseline, autospec=True
        ):
            with patch.object(service, "_check_unusual_time", return_value=time_a):
                with patch.object(service, "_check_unusual_frequency", side_effect=fake_freq):
                    with patch.object(service, "_check_unusual_dwell", return_value=None):
                        with patch.object(
                            service, "_persist_and_emit", new_callable=AsyncMock
                        ) as persist:
                            result = await service.check_detection(
                                detection, zone, session=session, threshold=2.0
                            )

        assert result is freq_a  # mutant 53 (WARNING rank 1->2 ties INFO -> stable order keeps time_a)
        persist.assert_called_once_with(freq_a, session=session)  # also kills 31 (freq skipped ->
                                                                  # result time_a -> first assert red)
        # UNVERIFIED - not yet run red/green

    @pytest.mark.asyncio
    async def test_baseline_missing_sample_count_is_treated_as_no_data(self) -> None:
        """getattr default 0 encodes: unknown sample count -> refuse to evaluate."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()
        detection = MagicMock()
        detection.detected_at = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
        zone = MagicMock()
        zone.id = str(uuid.uuid4())

        baseline = MagicMock(spec=[])  # no sample_count attribute
        with patch.object(
            service._baseline_service, "get_baseline", return_value=baseline, autospec=True
        ):
            with patch.object(service, "_check_unusual_time") as chk_time:
                result = await service.check_detection(detection, zone, session=AsyncMock())

        assert result is None
        chk_time.assert_not_called()  # mutants 11/14/17 proceed into the checks -> red
        # UNVERIFIED - not yet run red/green
```

### T5 — singleton reset must clear to None (kills S1)

```python
    def test_reset_clears_singleton_to_none_not_falsy_placeholder(self) -> None:
        """reset sets the module global to None; "" would slip past the `is None` check."""
        from backend.services import zone_anomaly_service as mod
        from backend.services.zone_anomaly_service import (
            ZoneAnomalyService,
            get_zone_anomaly_service,
            reset_zone_anomaly_service,
        )

        get_zone_anomaly_service()
        reset_zone_anomaly_service()
        assert mod._zone_anomaly_service is None  # kills reset_1 (= "")
        assert isinstance(get_zone_anomaly_service(), ZoneAnomalyService)
        reset_zone_anomaly_service()
        # UNVERIFIED - not yet run red/green
```

---

## Kill coverage accounting (exact, per key)

- **T1** (payload): F2 8 + F3 12 + F4 12 + F7 2 + F1 {41,51} 2 = **34**
- **T2** (window/fallback legs): F1 remaining 18 + F5 2 + F6 1 + F8 1 + F9 2 + F10 1 + F11 1 = **26**
- **T3** (captured-query SQL): Q1 9 + Q2 2 + Q3 1 + Q4 5 + Q5 1 + Q6 5 + Q7 2 + Q8 5 + Q11 1 = **31**
- **T3-fix** (one-line `match="^session is required$"` at test L1122): Q10 = **1**
- **T4** (winner/persist/signature): D1 1 + D2 1 + D4 1 + D5 2 + D7 1 + D8 4 + D9 3 + D10 21 + D11 3 = **37**
- **T5** (singleton type): S1 = **1**

34 + 26 + 31 + 1 + 37 + 1 = **132 = total TEST-GAP keys** (freq 62 + cd 37 + Q 32 + reset 1).
D3, D6 (EQUIVALENT, 2 keys) and Q9 (LOW-VALUE, 3 keys) are intentionally left unkilled.
