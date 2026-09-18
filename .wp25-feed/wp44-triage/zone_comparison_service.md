# WP4.4 Triage Dossier — backend/services/zone_comparison_service.py

**Run snapshot** (mutants/backend/services/zone_comparison_service.py.meta): total keys 207 ·
killed 95 · **survived 111** · unchecked 1. All 111 diffs read via `uv run mutmut show <key>` (no errors).

**Covering tests** (mutmut-stats.json tests_by_mangled_function_name): every function is covered only by
- `backend/tests/unit/services/test_zone_comparison_service.py` — ALL metric fetchers run against a
  `MagicMock`-backed session whose `execute()` return value is canned; the SQL text is never inspected;
  collaborator methods are `patch.object`-mocked with `side_effect` lists, so call arguments are never asserted;
  result dicts are checked key-by-key but omit `zone_type`/`camera_id` in the crossings and dwell tests.
- `backend/tests/unit/api/routes/test_zone_comparison.py` — route-level; mocks the whole service, so it
  cannot see anything inside it.

**Structural root cause**: 64 of 111 survivors (all "SQL-builder" clusters + the `zone_id == str(None)`
member) are provably invisible to mock-style tests — SQLAlchemy renders every mutated shape as valid SQL
(`where(None)` → `WHERE NULL`, `and_(None,…)` → `NULL AND …`, `select(None)` → `SELECT NULL`,
`func.count(None)` → `count(*)`, `func.avg(None)` → `avg(NULL)`; verified by compiling real statements in
this sandbox). Only SQL-text/param assertions kill them; alternatively integration DB tests would kill the
13 `!=`/drop-predicate/`str(None)` real-semantics members, but not the ~50 that compile to `WHERE NULL …`
(0 rows → same 0.0 the mock returns). **SQL-text assertions are the load-bearing recommendation.**

---

## Cluster table (18 clusters, sum = 111)

| # | Cluster | Count | Keys (function:mutmut#) | Classification | Note |
|---|---------|-------|-------------------------|----------------|------|
| 1 | `_calculate_trend` previous-window bounds → None / `+` flip | 3 | trend:3, trend:4, trend:5 | **TEST-GAP** | `prev_start=start_time-period_duration`→None or `+period_duration` (future window), `prev_end=start_time`→None. Trend is computed over the wrong period. |
| 2 | `_calculate_trend` current-period dwell callsite args → None / dropped | 6 | trend:8,9,10,11,12,13 | **TEST-GAP** | `_get_avg_dwell_time(zone_id,start,end)` → zone_id=None / start_time=None / end_time=None / args dropped. |
| 3 | `_calculate_trend` previous-period dwell callsite args → None / dropped | 6 | trend:15,16,17,18,19,20 | **TEST-GAP** | same shape on the prev-period call. |
| 4 | `_calculate_trend` anomaly callsites (current + prev) args → None / dropped | 6 | trend:23,24,25,26,27,28,30,31,32,33,34,35 (12) | **TEST-GAP** | same shape for `_get_anomaly_count` both callsites. |
| 5 | `_calculate_trend` `round(…, 1)` → `round(…, 2)`/None/dropped | 3 | trend:43, trend:45, trend:50 | **TEST-GAP** | mutmut_50 (`round(…,2)`) changes the user-visible `trend_percent` precision returned to the API — unasserted by any test (killed by drafted A's `== 23.5`). mutmut_43 (`ndigits=None`) raises TypeError that only surfaces as trend=None through compare_zones' blanket except (weaker value); dropped-arg variants behave like `round(x)` → integer. All three run under existing tests without failing them → TEST-GAP per definition. |
| 6 | `_get_avg_dwell_time` full SQL predicate set mutated | 16 | dwell:1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,17 | **TEST-GAP** | stmt/and_→None, `select(None)`, `func.avg(None)`→`avg(NULL)`, each predicate→None/dropped, `zone_id ==`→`!=`, `>=`→`>`, `<=`→`<`, `execute(stmt)`→`execute(None)`. |
| 7 | `_get_anomaly_count` full SQL predicate set mutated | 15 | anom:1,2,3,4,5,6,7,8,9,10,11,12,13,14,16 | **TEST-GAP** | same family; incl. `zone_id == str(None)` → binds string `'None'` (silent wrong query) and `>=`/`<=`→`>`/`<` boundary flips. |
| 8 | `_get_zone_info` polygon query predicate mutations | 5 | zone_info:1,2,3,4,6 | **TEST-GAP** | `id ==`→`!=` (fetches a *different* zone's name/type), select/where/execute→None. |
| 9 | `_get_zone_info` line-zone query predicate mutations | 5 | zone_info:15,16,17,18,20 | **TEST-GAP** | same on the LineZone fallback query. |
| 10 | `_get_crossing_count` query predicate mutations | 5 | crossing:1,2,3,4,6 | **TEST-GAP** | `LineZone.id ==`→`!=` + None mutations. |
| 11 | `_get_current_occupancy` query predicate mutations | 5 | occupancy:1,2,3,4,6 | **TEST-GAP** | `PolygonZone.id ==`→`!=` + None mutations. |
| 12 | `compare_zones` dwell_time dispatch args → None / dropped | 6 | zc:12,13,14,15,16,17 | **TEST-GAP** | window/zone_id never forwarded correctly, undetected. |
| 13 | `compare_zones` anomalies dispatch args → None / dropped | 6 | zc:20,21,22,23,24,25 | **TEST-GAP** | same for `_get_anomaly_count` branch. |
| 14 | `compare_zones` `_calculate_trend` call kwargs → None / dropped | 8 | zc:33,34,35,36,37,38,39,40 | **TEST-GAP** | all four kwargs (zone_id/metric/start/end) individually Nulled or removed. |
| 15 | `compare_zones` single-arg callsites zone_id → None | 3 | zc:3 (get_zone_info), zc:9 (crossing_count), zc:28 (occupancy) | **TEST-GAP** | each metric's lookup keyed on None instead of the zone. |
| 16 | `compare_zones` result dict key renames `zone_type`/`camera_id` | 4 | zc:48,49 (zone_type), zc:52,53 (camera_id) | **TEST-GAP** | keys `XXzone_typeXX`/`ZONE_TYPE` — route builds `ZoneComparisonData(**z)` (backend/api/routes/analytics_zones.py:1536) → pydantic ValidationError → 500. Existing tests omit these two keys from assertions. |
| 17 | `compare_zones` logger.warning message → None | 2 | zc:5, zc:29 | EQUIVALENT | pure log-text change (skip + unknown-metric warnings); behavior identical. |
| 18 | `compare_zones` `continue`→`break` on missing zone | 1 | zc:6 | **TEST-GAP** | stops comparing after first missing zone. Existing `test_compare_zones_skips_missing_zones` puts the gap LAST, where break/continue are indistinguishable. |

**Classification totals (final)**: **TEST-GAP 109** (clusters 1-16 and 18), **EQUIVALENT 2**
(cluster 17: zc:5, zc:29 log-message text only), **LOW-VALUE 0**. Sum = 111. Cluster 5 carries
TEST-GAP because its mutmut_50 member is a real unasserted API-precision change; its mutmut_43/45
members are TypeError-path variants that existing tests also execute without asserting (noted above).

---

## Per-cluster detail

### Clusters 1-5 — `_calculate_trend` (30 keys)
Source: `backend/services/zone_comparison_service.py:257-299`. Every existing trend test
(`test_zone_comparison_service.py:455-561`, `TestCalculateTrend`) patches `_get_avg_dwell_time` /
`_get_anomaly_count` with `side_effect=[current, prev]` and asserts only the returned percentage.
The *arguments* of those calls — which window, which zone — are never checked, so any argument mutation
inside `_calculate_trend` survives. mutmut_4 (`prev_start = start_time + period_duration`) makes the
"previous period" the *next* day. Killed only by asserting `call_args` (drafted test **A**).

### Clusters 6-7 — dwell & anomaly SQL builders (31 keys)
Source: lines 180-235. Tests `TestAvgDwellTime` (test file lines 344-379) and `TestAnomalyCount`
(382-417) feed `mock_db.execute.return_value = mock_result` with a canned scalar. The mutated WHERE
clauses all compile (`WHERE NULL`, `NULL AND …`, `!=`, `avg(NULL)`, `count(*)`) and the mock is
argument-blind, so 100% survive. Real-world impact if shipped: dwell averages across *all* zones
(`zone_id !=` / dropped predicate), boundary records double-counted or dropped (`>=`→`>`), anomaly
counts queried with string `'None'` as zone_id. Killed only by SQL-text + params assertions (drafted
tests **B**, **C**).

### Clusters 8-11 — zone lookup SQL builders (20 keys)
Source: lines 123-178, 237-255. Same mock-blindness; the dangerous members are the four `==`→`!=`
flips (zone_info:4, zone_info:18, crossing:4, occupancy:4) — production would silently load an arbitrary
different zone's name/type/count. Killed by drafted test **D**.

### Clusters 12-15 — `compare_zones` dispatch args (23 keys)
Source: lines 84-102. Existing metric tests patch the collaborator with `return_value`/`side_effect`
and assert only `results[0]["value"]`. Killed by drafted test **E** (call-args for all four metrics +
trend kwargs).

### Cluster 16 — result dict keys (4 keys)
Source: lines 104-113. `ZoneComparisonData` (backend/api/schemas/zone_comparison.py) *requires*
`zone_type` and `camera_id`, and the route constructs `ZoneComparisonData(**z)` at
backend/api/routes/analytics_zones.py:1536 — so `XXzone_typeXX` is a shipped-500, caught nowhere.
`test_compare_zones_crossings_metric` asserts zone_id/zone_name/value but not zone_type/camera_id.
Killed by drafted test **F** (exact key-set assertion).

### Cluster 17 — log text (2 keys) — EQUIVALENT. `logger.warning(None)` changes only message text;
no handler assertions exist or are warranted.

### Cluster 18 — `continue`→`break` (1 key: zc:6)
`test_compare_zones_skips_missing_zones` (test file lines 172-207) uses `zone_ids=[1, 999]` — the
missing zone is last, so `break` yields the same `[zone 1]`. Reordering to `[1, 999, 2]` kills it
(drafted test **G**).

---

## Drafted tests — append to `backend/tests/unit/services/test_zone_comparison_service.py`

Style matches the existing file (class-based, AsyncMock/MagicMock, no fixtures). **All UNVERIFIED —
not yet run red/green.** TDD procedure per test: (1) add the test, run it against the original module —
it must pass green; (2) run it under each cluster mutant (mutmut's copy) — the new assertion must fail
red on the mutant's diff; (3) keep only tests that are green-original/red-mutant.

### A — trend window + argument fidelity (kills clusters 1,2,3,4 and precision member of 5)
```python
    @pytest.mark.asyncio
    async def test_calculate_trend_uses_correct_previous_window_arguments(self) -> None:
        """Trend must query current and previous windows with exact zone/time args.

        UNVERIFIED - not yet run red/green
        """
        mock_db = AsyncMock()
        service = ZoneComparisonService(mock_db)

        end_time = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)
        start_time = end_time - timedelta(days=1)
        prev_start = start_time - timedelta(days=1)

        with patch.object(service, "_get_avg_dwell_time", new_callable=AsyncMock) as mock_dwell:
            mock_dwell.side_effect = [123.456, 100.0]

            result = await service._calculate_trend(
                zone_id=1,
                metric="dwell_time",
                start_time=start_time,
                end_time=end_time,
            )

        # Previous window = [start - duration, start); current = [start, end]
        assert mock_dwell.await_args_list == [
            ((1, start_time, end_time), {}),
            ((1, prev_start, start_time), {}),
        ]
        # Contract is one-decimal precision: round(..., 1) == 23.5, NOT round(..., 2) == 23.46
        assert result == 23.5
```

### B — dwell SQL shape (kills cluster 6, all 16)
```python
    @pytest.mark.asyncio
    async def test_get_avg_dwell_time_builds_complete_filtered_query(self) -> None:
        """Dwell query must avg total_seconds filtered by zone, closed window, completed only.

        UNVERIFIED - not yet run red/green
        """
        mock_db = AsyncMock()
        service = ZoneComparisonService(mock_db)

        now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)
        start_time = now - timedelta(days=1)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        await service._get_avg_dwell_time(7, start_time, now)

        mock_db.execute.assert_awaited_once()
        stmt = mock_db.execute.await_args.args[0]
        sql = " ".join(str(stmt.compile()).split())

        assert sql.startswith(
            "SELECT avg(dwell_time_records.total_seconds) AS avg_1 FROM dwell_time_records WHERE "
        )
        assert "dwell_time_records.zone_id = :zone_id_1" in sql  # not !=, not dropped
        assert "dwell_time_records.entry_time >= :entry_time_1" in sql  # not >
        assert "dwell_time_records.entry_time <= :entry_time_2" in sql  # not <
        assert "dwell_time_records.exit_time IS NOT NULL" in sql  # completed records only
        assert "NULL" not in sql  # rejects WHERE NULL / avg(NULL) / select(None) shapes
        assert mock_db.execute.await_args.args[0].compile().params == {
            "zone_id_1": 7,
            "entry_time_1": start_time,
            "entry_time_2": now,
        }
```

### C — anomaly SQL shape (kills cluster 7, all 15; incl. `str(None)` binder)
```python
    @pytest.mark.asyncio
    async def test_get_anomaly_count_builds_complete_filtered_query(self) -> None:
        """Anomaly query must count ZoneAnomaly.id filtered by str(zone_id) and closed window.

        UNVERIFIED - not yet run red/green
        """
        mock_db = AsyncMock()
        service = ZoneComparisonService(mock_db)

        now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)
        start_time = now - timedelta(days=1)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        await service._get_anomaly_count(7, start_time, now)

        mock_db.execute.assert_awaited_once()
        stmt = mock_db.execute.await_args.args[0]
        compiled = stmt.compile()
        sql = " ".join(str(compiled).split())

        assert sql.startswith("SELECT count(zone_anomalies.id) AS count_1 FROM zone_anomalies WHERE ")
        assert "zone_anomalies.zone_id = :zone_id_1" in sql
        assert "zone_anomalies.timestamp >= :timestamp_1" in sql
        assert "zone_anomalies.timestamp <= :timestamp_2" in sql
        assert "NULL" not in sql
        assert compiled.params == {
            "zone_id_1": "7",  # zone_id is stringified — must not become "None"
            "timestamp_1": start_time,
            "timestamp_2": now,
        }
```

### D — zone lookups target the requested id (kills clusters 8,9,10,11, all 20)
```python
    @pytest.mark.asyncio
    async def test_zone_lookup_queries_filter_on_requested_zone_id(self) -> None:
        """Every lookup must select the concrete table with id = zone_id (never !=, never NULL).

        UNVERIFIED - not yet run red/green
        """
        mock_db = AsyncMock()
        service = ZoneComparisonService(mock_db)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        await service._get_zone_info(7)  # polygon then line queries
        await service._get_crossing_count(7)
        await service._get_current_occupancy(7)

        assert mock_db.execute.await_count == 4
        queries = []
        for call in mock_db.execute.await_args_list:
            stmt = call.args[0]
            queries.append((" ".join(str(stmt.compile()).split()), stmt.compile().params))

        polygon_sql, line_sql, crossing_sql, occupancy_sql = (
            queries[0][0], queries[1][0], queries[2][0], queries[3][0],
        )
        assert "FROM polygon_zones" in polygon_sql and "WHERE polygon_zones.id = :id_1" in polygon_sql
        assert "FROM line_zones" in line_sql and "WHERE line_zones.id = :id_1" in line_sql
        assert "FROM line_zones" in crossing_sql and "WHERE line_zones.id = :id_1" in crossing_sql
        assert "FROM polygon_zones" in occupancy_sql and "WHERE polygon_zones.id = :id_1" in occupancy_sql
        for _, params in queries:
            assert params == {"id_1": 7}
        for sql, _ in queries:
            assert "NULL" not in sql  # rejects where(None)/select(None)/execute(None)
```

### E — compare_zones dispatch fidelity (kills clusters 12,13,14,15, all 23)
```python
    @pytest.mark.asyncio
    async def test_compare_zones_forwards_zone_and_window_to_each_metric(self) -> None:
        """Each metric branch must receive the exact zone_id and time window; trend too.

        UNVERIFIED - not yet run red/green
        """
        mock_db = AsyncMock()
        service = ZoneComparisonService(mock_db)

        now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)
        start_time = now - timedelta(days=1)

        zone_info = {"name": "Z", "type": "line", "camera_id": "cam"}

        with patch.object(service, "_get_zone_info", new_callable=AsyncMock) as mock_info, \
             patch.object(service, "_get_crossing_count", new_callable=AsyncMock) as mock_cross, \
             patch.object(service, "_get_avg_dwell_time", new_callable=AsyncMock) as mock_dwell, \
             patch.object(service, "_get_anomaly_count", new_callable=AsyncMock) as mock_anom, \
             patch.object(service, "_get_current_occupancy", new_callable=AsyncMock) as mock_occ, \
             patch.object(service, "_calculate_trend", new_callable=AsyncMock) as mock_trend:
            mock_info.return_value = zone_info
            mock_cross.return_value = 1.0
            mock_dwell.return_value = 2.0
            mock_anom.return_value = 3.0
            mock_occ.return_value = 4.0
            mock_trend.return_value = None

            for metric, mock in [
                ("crossings", mock_cross),
                ("dwell_time", mock_dwell),
                ("anomalies", mock_anom),
                ("occupancy", mock_occ),
            ]:
                mock.await_args_list.clear()
                mock_trend.await_args_list.clear()
                await service.compare_zones(
                    zone_ids=[7], metric=metric, start_time=start_time, end_time=now
                )
                if metric == "crossings":
                    assert mock.await_args_list == [((7,), {})]
                elif metric == "occupancy":
                    assert mock.await_args_list == [((7,), {})]
                else:
                    assert mock.await_args_list == [((7, start_time, now), {})]
                assert mock_trend.await_args_list == [
                    ((), {"zone_id": 7, "metric": metric,
                          "start_time": start_time, "end_time": now}),
                ]

        assert mock_info.await_args_list == [((7,), {})] * 4
```

### F — result payload contract (kills cluster 16, all 4)
```python
    @pytest.mark.asyncio
    async def test_compare_zones_result_matches_zone_comparison_schema(self) -> None:
        """Result dicts must expose the exact ZoneComparisonData key set (route does **z).

        UNVERIFIED - not yet run red/green
        """
        mock_db = AsyncMock()
        service = ZoneComparisonService(mock_db)

        now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)
        start_time = now - timedelta(days=1)

        with patch.object(service, "_get_zone_info", new_callable=AsyncMock) as mock_zone_info, \
             patch.object(service, "_get_crossing_count", new_callable=AsyncMock) as mock_crossings, \
             patch.object(service, "_calculate_trend", new_callable=AsyncMock) as mock_trend:
            mock_zone_info.return_value = {"name": "N", "type": "line", "camera_id": "cam1"}
            mock_crossings.return_value = 10.0
            mock_trend.return_value = None

            results = await service.compare_zones(
                zone_ids=[1], metric="crossings", start_time=start_time, end_time=now
            )

        assert set(results[0]) == {
            "zone_id", "zone_name", "zone_type", "camera_id", "value", "trend_percent",
        }
        assert results[0]["zone_type"] == "line"
        assert results[0]["camera_id"] == "cam1"

        ZoneComparisonData(**results[0])  # must not raise
```
(add import at file top: `from backend.api.schemas.zone_comparison import ZoneComparisonData`)

### G — missing zone skipped, later zones still compared (kills cluster 18, zc:6)
```python
    @pytest.mark.asyncio
    async def test_compare_zones_skips_missing_zone_without_stopping(self) -> None:
        """A missing zone in the MIDDLE must not stop comparison of later zones (continue ≠ break).

        UNVERIFIED - not yet run red/green
        """
        mock_db = AsyncMock()
        service = ZoneComparisonService(mock_db)

        now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)
        start_time = now - timedelta(days=1)

        with patch.object(service, "_get_zone_info", new_callable=AsyncMock) as mock_zone_info, \
             patch.object(service, "_get_crossing_count", new_callable=AsyncMock) as mock_crossings, \
             patch.object(service, "_calculate_trend", new_callable=AsyncMock) as mock_trend:
            mock_zone_info.side_effect = [
                {"name": "Zone 1", "type": "line", "camera_id": "cam1"},
                None,  # zone 999 missing in the MIDDLE
                {"name": "Zone 2", "type": "line", "camera_id": "cam2"},
            ]
            mock_crossings.return_value = 10.0
            mock_trend.return_value = None

            results = await service.compare_zones(
                zone_ids=[1, 999, 2], metric="crossings", start_time=start_time, end_time=now
            )

        assert [r["zone_id"] for r in results] == [1, 2]
```

---

## Killing forecast

| Drafted test | Kills clusters | Keys |
|---|---|---|
| A | 1,2,3,4,5 | 30 |
| B | 6 | 16 |
| C | 7 | 15 |
| D | 8,9,10,11 | 20 |
| E | 12,13,14,15 | 23 |
| F | 16 | 4 |
| G | 18 | 1 |
| — none needed | 17 (EQUIVALENT log text: zc:5, zc:29) | 2 |

A-G together kill **109/111**; residual 2 = the EQUIVALENT log-text pair (zc:5, zc:29). Drafted-test
kill mechanics verified against each mutation shape (substring checks fail on `!=`/`>`/`<` variants
because `"id = :x"` is not a substring of `"id != :x"`; `stmt.compile()` on a None-statement errors;
call-args equality fails on every None/dropped-argument variant; A's `== 23.5` fails `round(x,2)=23.46`,
`round(x)=23`, and raises through `ndigits=None`).
