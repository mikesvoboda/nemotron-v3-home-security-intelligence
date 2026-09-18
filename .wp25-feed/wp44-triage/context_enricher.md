# WP4.4 Triage Dossier — backend/services/context_enricher.py

- **Snapshot time:** 2026-09-18, mid-run (live meta read; 82 keys still `null`/unchecked — counts below are of SURVIVED keys only and may grow as the run proceeds).
- **Survivors at snapshot:** 134 (killed 234, null ~82, total 450).
- **Diffs obtained via:** `uv run mutmut show <key>` (one transient JSONDecodeError from concurrent cache write, retry succeeded).
- **Covering test file (all six functions):** `backend/tests/unit/services/test_context_enricher.py`
  - `TestGetZoneContext` L769-977 — mocks `session.execute` wholesale; asserts returned ZoneContext content only, never the SQL statement.
  - `TestGetBaselineContext` L980-1356 — same pattern; deviation assertions are range-only (`> 0.5`, `0.0 <= x <= 1.0`, `>= 0.5`).
  - `TestGetCrossCameraActivity` L1359-1616 — window test at L1524 literally asserts `mock_session.execute.assert_called()` ("we trust the query is correct").
  - `TestFormatZoneAnalysis` / `TestFormatBaselineComparison` / `TestFormatCrossCameraSummary` L361-501 — substring `in` checks; no exact-line or exact-join checks; sensitivity-label text never asserted.
- **Root-cause pattern #1:** every DB query mutant survives because tests mock `session.execute` and never inspect the statement it was called with (`stmt = mock_session.execute.call_args.args[0]; str(stmt.compile())` would kill dozens).
- **Root-cause pattern #2:** deviation-score math is asserted only as ranges/thresholds, so constant/coefficient mutations inside the formula are invisible.

## Cluster table (counts sum to 134)

| #   | Cluster (pattern @ function)                                                                                                                                                                                                                                                     | N   | Class      | Example keys (≤3)                                                                                            | Notes / killing test                                                                                                                                                                                                                                                                                                 |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --- | ---------- | ------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Whole-clause / operator mutations in zone query `select(Zone).where(camera_id==, enabled==True).order_by(priority.desc())` → `_get_zone_context`                                                                                                                                 | 10  | TEST-GAP   | `..._get_zone_context__mutmut_2` (select→None), `_9` (`==`→`!=` on camera_id), `_10` (`enabled==True`→`!=`)  | Drafted T1. SQL never inspected; also no multi-zone data-plane check.                                                                                                                                                                                                                                                |
| 2   | Sort-order mutations `zone_contexts.sort(key=detection_count, reverse=True)` → `_get_zone_context`                                                                                                                                                                               | 6   | TEST-GAP   | `_74` (key→None), `_79`/`_80` (reverse True→False)                                                           | Drafted T1 (2-zone ordering assertion). Survives because every existing test returns ≤1 zone.                                                                                                                                                                                                                        |
| 3   | bbox guard `or`→`and` pairs (`x is None or y is None` → `x is None and y is None`) → `_get_zone_context`                                                                                                                                                                         | 3   | TEST-GAP   | `_18`, `_19`, `_20`                                                                                          | Drafted T2 kills `_19`,`_20`; `_18` (bbox_height pair) is **unobservable** — `bbox_center` raises ValueError for `None` height, so the `and`-path still skips. Note for triage: 1 of 3 effectively low-value.                                                                                                        |
| 4   | `continue`→`break` in bbox-skip and ValueError-skip loops → `_get_zone_context`                                                                                                                                                                                                  | 2   | TEST-GAP   | `_25`, `_39`                                                                                                 | Drafted T2. No test has an incomplete/invalid detection followed by a good one.                                                                                                                                                                                                                                      |
| 5   | `ZONE_RISK_WEIGHTS.get(zone_type, "low")` default-arg mutations → `_get_zone_context`                                                                                                                                                                                            | 4   | EQUIVALENT | `_58` (default None), `_61` (`"XXlowXX"`), `_62` (`"LOW"`)                                                   | All 5 enum members of CameraZoneType are keys in the dict → fallback unreachable; `.get(zone, )` is the same as `.get(zone)`.                                                                                                                                                                                        |
| 6   | `logger.debug(...)` message → None (×2) → `_get_zone_context`                                                                                                                                                                                                                    | 2   | LOW-VALUE  | `_15`, `_80`                                                                                                 | Pure log text.                                                                                                                                                                                                                                                                                                       |
| 7   | Cross-camera window sign flips `start - timedelta` / `end + timedelta` → `_get_cross_camera_activity`                                                                                                                                                                            | 2   | TEST-GAP   | `_2`, `_5`                                                                                                   | Drafted T3 (assert compiled bind params = window bounds).                                                                                                                                                                                                                                                            |
| 8   | Cross-camera detection query clause/operator mutations (`execute(select(...))`→None, order_by→None, each `where` clause→None/dropped, `!=`→`==`, `>=`→`>`, `<=`→`<`) → `_get_cross_camera_activity`                                                                              | 12  | TEST-GAP   | `_8`, `_17` (`!=`→`==` includes own camera), `_18`                                                           | Drafted T3. SQL never inspected.                                                                                                                                                                                                                                                                                     |
| 9   | Camera-name lookup `execute(select(Camera).where(Camera.id.in_(ids)))` mutations → `_get_cross_camera_activity`                                                                                                                                                                  | 3   | TEST-GAP   | `_30` (execute→None), `_31` (where→None), `_32` (select→None)                                                | Drafted T3 (second-call SQL + name resolution).                                                                                                                                                                                                                                                                      |
| 10  | Reference-time midpoint `start + (end-start)/2` → `-…/2`, `*2`, `/3` → `_get_cross_camera_activity`                                                                                                                                                                              | 3   | TEST-GAP   | `_37`, `_38`, `_40`                                                                                          | Drafted T4. Existing tests only assert the empty-offsets case (`== 0.0`) where mutations coincide.                                                                                                                                                                                                                   |
| 11  | Avg-time-offset real mutations (`time_offsets`→None, ternary→`and False`, sum÷len→sum×len, kwarg `time_offset_seconds=` dropped) → `_get_cross_camera_activity`                                                                                                                  | 4   | TEST-GAP   | `_43`, `_47`, `_49`                                                                                          | Drafted T4 (nonzero expected average kills all 4).                                                                                                                                                                                                                                                                   |
| 12  | `sum/len if time_offsets else 0.0` → `if (time_offsets) or True` → `_get_cross_camera_activity`                                                                                                                                                                                  | 1   | EQUIVALENT | `_48`                                                                                                        | `time_offsets` is empty exactly when all `detected_at` are None; then `sum([])/len` = 0.0 = else-branch.                                                                                                                                                                                                             |
| 13  | `logger.debug(...)` → None → `_get_cross_camera_activity`                                                                                                                                                                                                                        | 1   | LOW-VALUE  | `_73`                                                                                                        | Log text.                                                                                                                                                                                                                                                                                                            |
| 14  | ClassBaseline query clause/operator mutations (`camera_id==`→None/`!=`, `hour==`→None/`!=`, select→None, clause dropped) → `_get_baseline_context`                                                                                                                               | 8   | TEST-GAP   | `_23`, `_29` (`camera_id`→`!=`), `_30` (`hour`→`!=`)                                                         | Not drafted in full; same fix recipe as T3: `stmt = mock_session.execute.call_args_list[0].args[0]`, assert `"camera_baselines"` + `"camera_id ="` + `"hour ="` in `str(stmt.compile())`.                                                                                                                            |
| 15  | ActivityBaseline query clause/operator mutations (3 clauses → None/dropped, `==`→`!=`, select→None) → `_get_baseline_context`                                                                                                                                                    | 11  | TEST-GAP   | `_37`, `_45`, `_46`                                                                                          | Same recipe on second execute call; assert `"activity_baselines"`, `"hour ="`, `"day_of_week ="`.                                                                                                                                                                                                                    |
| 16  | `total_expected` accumulator mutations (`0.0`→`1.0`, `+=`→`=`, `-=`) → `_get_baseline_context`                                                                                                                                                                                   | 3   | EQUIVALENT | `_19`, `_34`, `_35`                                                                                          | `total_expected` is written at L406/L420 and never read (grep confirms) — dead local.                                                                                                                                                                                                                                |
| 17  | `sample_count >= 10` → `> 10`, `>= 11` boundary → `_get_baseline_context`                                                                                                                                                                                                        | 2   | TEST-GAP   | `_54`, `_55`                                                                                                 | Drafted T5 case 3 (sample_count == 10 exactly). Existing test uses 5 vs 15.                                                                                                                                                                                                                                          |
| 18  | `expected_activity > 0` → `> 1` → `_get_baseline_context`                                                                                                                                                                                                                        | 1   | TEST-GAP   | `_58`                                                                                                        | Drafted T5 case 4 (avg_count = 1.0). Existing test only probes avg 0.0.                                                                                                                                                                                                                                              |
| 19  | Deviation formula mutations: `/`→`*`, `1.0−1/ratio`→`1.0+…`/`2.0−…`, `ratio>1`→`ratio>2`/`(ratio>1) or True`, `(1−ratio)*0.5`→`/0.5`,`(1+ratio)*0.5`,`(2−ratio)*0.5`,`*1.5`, clamp floor `max(0.0→1.0, …)` (`_60,_63,_64,_65,_69,_70,_71,_72,_73,_79`) → `_get_baseline_context` | 10  | TEST-GAP   | `_60` (`ratio = total*expected`), `_70` (`(1−ratio)/0.5`), `_79` (`max(1.0, min(1.0, s))` pins score to 1.0) | Drafted T5 exact-value parametrize kills 9 of 10. `_69` (`ratio>2`) boundary-unobservable: every ratio>1 in tests is >2 and exact 1.0 is unreachable (total_current=0 short-circuits elsewhere).                                                                                                                     |
| 20  | `if ratio > 1` → `>= 1` → `_get_baseline_context`                                                                                                                                                                                                                                | 1   | EQUIVALENT | `_68`                                                                                                        | At ratio == 1.0 both branches evaluate to 0.0.                                                                                                                                                                                                                                                                       |
| 21  | Clamp `max(0.0, min(1.0, s))` → `min(2.0, s)` → `_get_baseline_context`                                                                                                                                                                                                          | 1   | EQUIVALENT | `_84`                                                                                                        | Unclamped paths can exceed 1.0 only via the later `min(0.95, …)` boost paths; anomaly_score inputs are normalized 0-1, so 1.0 cap never binds differently in-reach.                                                                                                                                                  |
| 22  | `is_anomalous = deviation_score > 0.5` → `None`, `>= 0.5`, `> 1.5` (`_85,_86,_87`) → `_get_baseline_context`                                                                                                                                                                     | 3   | TEST-GAP   | `_85` (None), `_87` (`> 1.5`)                                                                                | Drafted T5 asserts `is_anomalous is True` (case 1, deviation 0.75 → kills `_85 None` and `_87 >1.5`) plus `is False` (non-anomalous cases). `_86` (`>=0.5`) needs deviation exactly 0.5 → boundary-unobservable. Real kill = 2 of 3.                                                                                 |
| 23  | `self._baseline_service.is_anomalous(camera_id, obj_type, reference_time, session=session)` positional/kwarg mutations + arg drops → `_get_baseline_context`                                                                                                                     | 8   | TEST-GAP   | `_92` (camera_id→None), `_95` (session=None), `_96`-`_98` (arg dropped)                                      | Drafted T6 (`mock.assert_called_with(...)` — mock is never call-asserted today).                                                                                                                                                                                                                                     |
| 24  | Boost `max(s, anomaly_score * 0.8)` → `/0.8`, `*1.8` → `_get_baseline_context`                                                                                                                                                                                                   | 2   | TEST-GAP   | `_107`, `_108`                                                                                               | Drafted T6 (`deviation == pytest.approx(0.76)` for score 0.95; existing test asserts only `>= 0.76` at L2005).                                                                                                                                                                                                       |
| 25  | `format_class_anomaly_context(camera_id=…, current_hour=…)` args → None → `_get_baseline_context`                                                                                                                                                                                | 2   | LOW-VALUE  | `_111`, `_112`                                                                                               | Only effect: anomaly-lookup key `"None:None:cls"` mismatches → anomalies silently disappear (output shape identical, all-empty). Asserting call identity is tautological; real anomaly-boost path already covered by `_107/_108` cluster + prompts-module tests.                                                     |
| 26  | `logger.debug(...)` → None → `_get_baseline_context`                                                                                                                                                                                                                             | 1   | LOW-VALUE  | `_119`                                                                                                       | Log text.                                                                                                                                                                                                                                                                                                            |
| 27  | Return-dataclass field mutations: `class_anomalies=…`→None / dropped, `class_anomaly_context=…`→None / dropped → `_get_baseline_context`                                                                                                                                         | 4   | TEST-GAP   | `_126`, `_127`, `_134`                                                                                       | Default `""`/`[]` masks them; test exists (test_anomalous_class) but never asserts these two fields. Recipe: drive a real anomalous class via real ClassBaseline path (or patch `format_class_anomaly_context` return) and assert `baseline.class_anomalies == [anomaly]` / `class_anomaly_context == "<sentinel>"`. |
| 28  | Sensitivity lookup removal: `sensitivity = None` / `get(None, …)` / `get(zone_type, )` (drops the 2nd arg) → `format_zone_analysis`                                                                                                                                              | 3   | TEST-GAP   | `_8` (whole call → None), `_9` (key → None), `_11` (default dropped)                                         | Output text becomes `"- Entry (entry_point - None): …"` / wrong label; tests never assert the sensitivity string. Recipe: assert full formatted line (exact string) per zone type.                                                                                                                                   |
| 29  | Sensitivity default-fallback string mutations (`"low sensitivity - general area"`→None/None-dropped/`XX…XX`/UPPER) → `format_zone_analysis`                                                                                                                                      | 4   | EQUIVALENT | `_10`, `_13`                                                                                                 | All five `zone_type` values (`zone.zone_type.value` of the 5-member enum) are keys of `_ZONE_SENSITIVITY_LABELS` → default branch unreachable. (`.get(k, )` ≡ `.get(k)`.)                                                                                                                                            |
| 30  | Join separator `"\n".join(lines)` → `"XX\nXX".join(lines)` → `format_zone_analysis`                                                                                                                                                                                              | 1   | TEST-GAP   | `_17`                                                                                                        | `result.strip().split("\n")` in test_multiple_zones (L398-399) leniently tolerates `XX` lines. Assert exact multi-line string.                                                                                                                                                                                       |
| 31  | Prompt label text clobbers (`"Expected activity:"`, `"No historical baseline…"`, `"Current activity:"` → `XX…XX`) → `format_baseline_comparison`                                                                                                                                 | 3   | LOW-VALUE  | `_7`, `_13`, `_17`                                                                                           | Existing tests assert exact fragments (`assert "Expected activity:" in result` L427/L2021, `"No historical baseline"` L422) — the tests DO check these strings, so the mutants should die once the whole file runs green; surviving ⇒ check test selection, not a gap. Treat as prompt-label churn.                  |
| 32  | Join separator `"XX\nXX".join` → `format_baseline_comparison`                                                                                                                                                                                                                    | 1   | TEST-GAP   | `_24`                                                                                                        | No test splits this output into lines. Assert exact multi-line string.                                                                                                                                                                                                                                               |
| 33  | Empty-list message + `"unknown"` placeholder text clobbers → `format_cross_camera_summary`                                                                                                                                                                                       | 2   | LOW-VALUE  | `_2`, `_32`                                                                                                  | Same situation as #31: `"No activity detected on other cameras"` (L458) and `"unknown"` (L1755) ARE asserted; investigate run/selection.                                                                                                                                                                             |
| 34  | `offset_desc = ""` init → `None` / `"XXXX"` → `format_cross_camera_summary`                                                                                                                                                                                                      | 2   | TEST-GAP   | `_6`, `_7`                                                                                                   | Small-offset line becomes `"- Garage: 1 detection(s) [car]None"` or `"[car]XXXX"`; `test_small_time_offset_not_shown` only checks `"min" not in result`. Assert exact line.                                                                                                                                          |
| 35  | Offset threshold / minutes divisor: `>60`→`>=60`, `>61`; `/60`→`/61` → `format_cross_camera_summary`                                                                                                                                                                             | 3   | TEST-GAP   | `_9`, `_10`, `_14`                                                                                           | Boundary 60s and divisor not pinned. Recipe: offset 121s → `assert "2 min after" in result` (kills `/61`) and offset == 60.0 → `assert "min" not in result` (kills `>=60`); `>61` boundary unobservable at integer display resolution (61s renders `"1 min"` under either).                                          |
| 36  | `direction = "before" if offset < 0 else "after"` → `<= 0`, `< 1` → `format_cross_camera_summary`                                                                                                                                                                                | 2   | EQUIVALENT | `_20`, `_21`                                                                                                 | Only differs at offset 0 and (0,1); both render `"0 min …"` and the 0s branch is display-irrelevant at `:.0f`.                                                                                                                                                                                                       |
| 37  | Join/separator: `", ".join(object_types)`→`"XX, XX".join`, final `"\n".join`→`"XX\nXX".join` → `format_cross_camera_summary`                                                                                                                                                     | 2   | TEST-GAP   | `_31`, `_36`                                                                                                 | Assert exact line (`[person, dog]`) and exact multi-line output.                                                                                                                                                                                                                                                     |
| 38  | `logger.info("ContextEnricher initialized…")` → None → `__init__`                                                                                                                                                                                                                | 1   | LOW-VALUE  | `..._x__init____mutmut_5`                                                                                    | Log text.                                                                                                                                                                                                                                                                                                            |

**Totals (machine-checked against the meta snapshot):** 38 clusters, counts sum to 134. TEST-GAP **106** · EQUIVALENT **16** · LOW-VALUE **12**.

## Drafted tests (target: `backend/tests/unit/services/test_context_enricher.py`)

All six follow the file's existing style: module fixtures / inline `MagicMock(spec=…)` models, `mock_session.execute.side_effect`, `patch("backend.services.context_enricher.get_baseline_service")`, `@pytest.mark.asyncio`. Append to the matching class.

**TDD procedure (same for every test):** apply the cluster's mutant diff to `backend/services/context_enricher.py`, run the new test — it must FAIL (red) on the mutant; revert the diff, run again — it must PASS (green). `// UNVERIFIED - not yet run red/green` on each.

### T1 — zone query predicate + output order (kills clusters #1 (10 keys), #2 (6 keys))

```python
    @pytest.mark.asyncio
    async def test_zone_query_filters_enabled_zones_for_camera_and_output_is_sorted(self):
        """SQL predicate and count-descending order of _get_zone_context (WP4.4 mutants)."""
        from sqlalchemy import select

        mock_session = AsyncMock()

        # Two full-image zones; execute returns them in z1,z2 order regardless of DB order.
        mock_zone1 = MagicMock(spec=Zone)
        mock_zone1.id = "z1"
        mock_zone1.name = "Zone One"
        mock_zone1.zone_type = ZoneType.OTHER
        mock_zone1.coordinates = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]

        mock_zone2 = MagicMock(spec=Zone)
        mock_zone2.id = "z2"
        mock_zone2.name = "Zone Two"
        mock_zone2.zone_type = ZoneType.OTHER
        mock_zone2.coordinates = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]

        mock_zones_result = MagicMock()
        mock_zones_result.scalars.return_value.all.return_value = [mock_zone1, mock_zone2]
        mock_session.execute.return_value = mock_zones_result

        # 1 detection lands in z1 only? Both zones cover everything, so give z1 one
        # and z2 three by making zones differ: z2 covers full image, z1 covers nothing.
        mock_zone1.coordinates = [[0.0, 0.0], [0.01, 0.0], [0.01, 0.01], [0.0, 0.01]]

        detections = []
        for _ in range(4):
            d = MagicMock(spec=Detection)
            d.bbox_x, d.bbox_y, d.bbox_width, d.bbox_height = 900, 500, 100, 100
            detections.append(d)

        enricher = ContextEnricher()
        zones = await enricher._get_zone_context("front_door", detections, mock_session)

        # 1) The statement handed to execute() must filter THIS camera's ENABLED zones
        #    by priority — never None, never flipped operators, never select(None).
        stmt = mock_session.execute.call_args.args[0]
        sql = str(stmt.compile())
        assert "FROM camera_zones" in sql
        assert "camera_id =" in sql
        assert "enabled =" in sql
        assert "ORDER BY camera_zones.priority DESC" in sql

        # 2) Data plane: highest detection count first (z2 has 4, z1 has 0 hits).
        assert [z.zone_id for z in zones] == ["z2"]
        assert zones[0].detection_count == 4

// UNVERIFIED - not yet run red/green
```

(Note: with the 0.01-square z1 the 900,500 center hits only z2; a mutant that returns
`select(None)`-style garbage makes the SQL asserts or the count assert fail. If you prefer
two entries in the result, use two covering zones and assert `["z2", "z1"]` with counts 3/1 —
either ordering assertion kills the reverse=False mutants `_79/_80`.)

### T2 — per-detection skip, not loop abort (kills cluster #4 (2 keys) + `_19`/`_20` of #3)

```python
    @pytest.mark.asyncio
    async def test_zone_context_skips_partial_and_invalid_bbox_detections_without_aborting(self):
        """A detection missing ONE bbox field or with an invalid bbox is skipped; the
        remaining detections still map to zones (WP4.4 or->and and continue->break mutants)."""
        mock_session = AsyncMock()

        mock_zone = MagicMock(spec=Zone)
        mock_zone.id = "zone-1"
        mock_zone.name = "Driveway"
        mock_zone.zone_type = ZoneType.DRIVEWAY
        mock_zone.coordinates = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]

        mock_zones_result = MagicMock()
        mock_zones_result.scalars.return_value.all.return_value = [mock_zone]
        mock_session.execute.return_value = mock_zones_result

        # 1) Only bbox_width is None -> must be SKIPPED (and-mutants would process it)
        det_partial = MagicMock(spec=Detection)
        det_partial.bbox_x, det_partial.bbox_y = 900, 500
        det_partial.bbox_width, det_partial.bbox_height = None, 100

        # 2) Invalid bbox (negative width -> ValueError) -> must be skipped, loop continues
        det_invalid = MagicMock(spec=Detection)
        det_invalid.bbox_x, det_invalid.bbox_y = 900, 500
        det_invalid.bbox_width, det_invalid.bbox_height = -50, 100

        # 3) Valid detection -> must still map to the zone (break-mutants would abort)
        det_good = MagicMock(spec=Detection)
        det_good.bbox_x, det_good.bbox_y = 900, 500
        det_good.bbox_width, det_good.bbox_height = 100, 100

        enricher = ContextEnricher()
        zones = await enricher._get_zone_context(
            "front_door", [det_partial, det_invalid, det_good], mock_session
        )

        assert [z.zone_id for z in zones] == ["zone-1"]
        assert zones[0].detection_count == 1  # only det_good counted

// UNVERIFIED - not yet run red/green
```

### T3 — cross-camera SQL predicates + expanded window + camera lookup (kills clusters #7 (2), #8 (12), #9 (3))

```python
    @pytest.mark.asyncio
    async def test_cross_camera_query_window_predicates_and_camera_lookup(self):
        """The cross-camera query must exclude this camera, bound the ±window and
        order by time; the camera-name lookup must be an id-IN query (WP4.4 mutants)."""
        mock_session = AsyncMock()
        now = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
        start_time = now - timedelta(seconds=60)
        end_time = now

        mock_detection = MagicMock(spec=Detection)
        mock_detection.camera_id = "back_yard"
        mock_detection.object_type = "person"
        mock_detection.detected_at = now - timedelta(seconds=10)

        mock_detections_result = MagicMock()
        mock_detections_result.scalars.return_value.all.return_value = [mock_detection]

        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "back_yard"
        mock_camera.name = "Back Yard"
        mock_cameras_result = MagicMock()
        mock_cameras_result.scalars.return_value.all.return_value = [mock_camera]

        mock_session.execute.side_effect = [mock_detections_result, mock_cameras_result]

        enricher = ContextEnricher()
        cross = await enricher._get_cross_camera_activity(
            "front_door", start_time, end_time, mock_session
        )

        assert cross[0].camera_name == "Back Yard"

        calls = mock_session.execute.call_args_list
        assert len(calls) == 2

        # 1) Detection query: other-camera + closed time window + chronological order.
        det_sql = str(calls[0].args[0].compile())
        assert "FROM detections" in det_sql
        assert "camera_id !=" in det_sql          # kills ==-flip and clause removal
        assert "detected_at >=" in det_sql
        assert "detected_at <=" in det_sql
        assert "ORDER BY detections.detected_at" in det_sql

        # 2) Window VALUES: start-300s .. end+300s (kills the sign-flip mutants).
        params = calls[0].args[0].compile().params
        times = sorted(v for v in params.values() if isinstance(v, datetime))
        assert times == [
            start_time - timedelta(seconds=300),
            end_time + timedelta(seconds=300),
        ]

        # 3) Camera-name lookup is an IN-query over the observed camera ids.
        cam_sql = str(calls[1].args[0].compile())
        assert "FROM cameras" in cam_sql
        assert "IN (" in cam_sql

// UNVERIFIED - not yet run red/green
```

### T4 — time_offset_seconds is the per-detection average around the window midpoint (kills clusters #10 (3), #11 (4))

```python
    @pytest.mark.asyncio
    async def test_cross_camera_time_offset_is_mean_of_per_detection_offsets(self):
        """time_offset_seconds must average each detection against the window MIDPOINT
        (WP4.4 reference-time and avg-mutants)."""
        mock_session = AsyncMock()
        start_time = datetime(2025, 6, 1, 9, 59, 30, tzinfo=UTC)
        end_time = datetime(2025, 6, 1, 10, 0, 30, tzinfo=UTC)
        midpoint = start_time + timedelta(seconds=30)

        det_at_mid = MagicMock(spec=Detection)
        det_at_mid.camera_id = "other_cam"
        det_at_mid.object_type = "person"
        det_at_mid.detected_at = midpoint                      # offset   +0
        det_late = MagicMock(spec=Detection)
        det_late.camera_id = "other_cam"
        det_late.object_type = "person"
        det_late.detected_at = midpoint + timedelta(seconds=150)  # offset +150

        mock_detections_result = MagicMock()
        mock_detections_result.scalars.return_value.all.return_value = [det_at_mid, det_late]

        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "other_cam"
        mock_camera.name = "Other"
        mock_cameras_result = MagicMock()
        mock_cameras_result.scalars.return_value.all.return_value = [mock_camera]

        mock_session.execute.side_effect = [mock_detections_result, mock_cameras_result]

        enricher = ContextEnricher()
        cross = await enricher._get_cross_camera_activity(
            "front_door", start_time, end_time, mock_session
        )

        assert len(cross) == 1
        assert cross[0].time_offset_seconds == pytest.approx(75.0)

// UNVERIFIED - not yet run red/green
```

### T5 — exact deviation-score formula incl. boundaries (kills clusters #17 (2), #18 (1), 7/9 of #19, 2/3 of #22)

```python
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("sample_count", "avg_count", "n_dets", "expected_deviation", "expected_anomalous"),
        [
            (15, 2.0, 8, 0.75, True),   # ratio 4   -> 1 - 1/4, >0.5 flags anomalous
            (20, 10.0, 5, 0.25, False),  # ratio 0.5 -> (1 - 0.5) * 0.5
            (10, 10.0, 5, 0.25, False),  # sample_count == 10 exactly (>= 10 boundary)
            (15, 1.0, 5, 0.8, True),     # avg_count == 1.0 (> 0 guard boundary), ratio 5
        ],
    )
    async def test_deviation_score_exact_formula_over_activity_baseline(
        self, sample_count, avg_count, n_dets, expected_deviation, expected_anomalous
    ):
        """deviation = 1-1/ratio (ratio>1) | (1-ratio)*0.5 (ratio<=1) with the
        sample_count>=10 and expected>0 gates (WP4.4 deviation-formula mutants)."""
        mock_session = AsyncMock()
        now = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)

        mock_class_result = MagicMock()
        mock_class_result.scalars.return_value.all.return_value = []

        mock_activity = MagicMock(spec=ActivityBaseline)
        mock_activity.sample_count = sample_count
        mock_activity.avg_count = avg_count
        mock_activity_result = MagicMock()
        mock_activity_result.scalar_one_or_none.return_value = mock_activity

        mock_session.execute.side_effect = [mock_class_result, mock_activity_result]

        detections = []
        for _ in range(n_dets):
            d = MagicMock(spec=Detection)
            d.object_type = "person"
            detections.append(d)

        mock_baseline_service = MagicMock()
        mock_baseline_service.is_anomalous = AsyncMock(return_value=(False, 0.1))

        with patch(
            "backend.services.context_enricher.get_baseline_service",
            return_value=mock_baseline_service,
            autospec=True,
        ):
            enricher = ContextEnricher()
            baseline = await enricher._get_baseline_context(
                "front_door", detections, now, mock_session
            )

        assert baseline.deviation_score == pytest.approx(expected_deviation)
        assert baseline.is_anomalous is expected_anomalous

// UNVERIFIED - not yet run red/green
```

### T6 — baseline-service call contract + anomaly boost (kills clusters #23 (8), #24 (2))

```python
    @pytest.mark.asyncio
    async def test_anomalous_class_calls_baseline_service_with_exact_args_and_boost(self):
        """is_anomalous() receives (camera_id, obj_type, reference_time, session=session)
        and its score boosts deviation by *0.8 (WP4.4 call-arg and boost mutants)."""
        mock_session = AsyncMock()
        now = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)

        mock_class_result = MagicMock()
        mock_class_result.scalars.return_value.all.return_value = []
        mock_activity_result = MagicMock()
        mock_activity_result.scalar_one_or_none.return_value = None
        mock_session.execute.side_effect = [mock_class_result, mock_activity_result]

        mock_detection = MagicMock(spec=Detection)
        mock_detection.object_type = "vehicle"

        mock_baseline_service = MagicMock()
        mock_baseline_service.is_anomalous = AsyncMock(return_value=(True, 0.95))

        with patch(
            "backend.services.context_enricher.get_baseline_service",
            return_value=mock_baseline_service,
            autospec=True,
        ):
            enricher = ContextEnricher()
            baseline = await enricher._get_baseline_context(
                "front_door", [mock_detection], now, mock_session
            )

        mock_baseline_service.is_anomalous.assert_called_with(
            "front_door", "vehicle", now, session=mock_session
        )
        assert baseline.is_anomalous is True
        # max(0.5 no-baseline score, 0.95 * 0.8) = 0.76 — pins the 0.8 multiplier
        assert baseline.deviation_score == pytest.approx(0.76)

// UNVERIFIED - not yet run red/green
```

## Kill-sweep summary (drafted coverage)

| Drafted test | Clusters killed                               | Keys                        |
| ------------ | --------------------------------------------- | --------------------------- |
| T1           | #1, #2                                        | 16                          |
| T2           | #4 + `_19`,`_20` of #3                        | 4                           |
| T3           | #7, #8, #9                                    | 17                          |
| T4           | #10, #11                                      | 7                           |
| T5           | #17 (2/2), #18 (1/1), 9/10 of #19, 2/3 of #22 | 14                          |
| T6           | #23, #24                                      | 10                          |
| **Total**    |                                               | **68 of 106 TEST-GAP keys** |

Remaining TEST-GAP keys (38) are covered by the recipes already embedded above:

- #14/#15 (baseline queries, 19 keys): identical SQL-call-args assertion as T3 on execute calls 0/1 (`"class_baselines"`, `"camera_baselines"`, `"hour ="`, `"day_of_week ="`).
- #27 (class_anomalies/context fields, 4): sentinel-patch `format_class_anomaly_context` and assert pass-through of both fields.
- #28/#30/#32/#34/#35/#37 (format methods, 12): one exact-output-string test per formatter (full expected line incl. sensitivity label, `[person, dog]` join, `"\n"` separators, boundary 60s, 121s→`"2 min"`).
- Boundary-unobservable keys inside TEST-GAP clusters (3): `_18` (bbox_height pair of cluster #3), `_69` (ratio>2 of #19), `_86` (>=0.5 of #22). Feed them as "boundary-unobservable — killable only via monkeypatched intermediates". (35 recipe + 3 = 38 remaining TEST-GAP keys.)

## Verification notes

- Enum exhaustiveness checked: `CameraZoneType` has exactly the 5 members that key `ZONE_RISK_WEIGHTS` and `_ZONE_SENSITIVITY_LABELS` → clusters #5/#29 EQUIVALENT confirmed.
- `total_expected` read-check (`grep`) → never read → cluster #16 EQUIVALENT confirmed.
- `bbox_center` raises `ValueError` on negative dims AND on `None` (`None < 0` TypeError is caught? — no: TypeError, but zone_service guards with explicit checks; None comparisons raise TypeError which would ESCAPE the `except ValueError`. Re-check when running T2 red: `det_partial` reaching bbox_center would raise TypeError and fail the test loudly, which is still a red on the mutant — acceptable for TDD purposes, but if TypeError escapes the except, mutant `__mutmut_19/_20` die via error, still red. Green side unaffected.)
- `str(stmt.compile())` and `.params` are used on `select()` objects — no DB needed; `in_()` renders as `IN (__[POSTCOMPILE_id_1])` under default compilation.
- Tests NOT run (harness constraint: no pytest during the live mutmut run). All drafted tests are UNVERIFIED.
