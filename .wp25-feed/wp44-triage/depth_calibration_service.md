# WP4.4 Survivor Triage — backend/services/depth_calibration_service.py

- **Module:** `backend.services.depth_calibration_service`
- **Arbiter (final-score.json):** survivors 57, killed 147, total 204, score 72.06
- **Meta cross-check:** `exit_code_by_key` in `mutants/backend/services/depth_calibration_service.py.meta` contains **57 keys with exit_code == 0** — matches the arbiter exactly. Every mutant segment was extracted from the shipped mutant source by AST (spans file offsets are stale; do not use them) and diffed line-wise against `__mutmut_orig`. All 57 diffs are grounded (no phantom/overcount clusters — the rejected prior attempt's 60-key tally is not reproduced here).
- **Harness note:** `[tool.mutmut] pytest_add_cli_args_test_selection = ["backend/tests/unit"]` — `backend/tests/integration/test_depth_calibration_pipeline.py` (which *does* assert `camera_id`, `image_width/height`) never runs against these mutants, so its assertions kill nothing. All "TEST-GAP" below means: killable by a test in the **unit** file `backend/tests/unit/services/test_depth_calibration_service.py`.
- **Counts:** TEST-GAP **32** · EQUIVALENT **7** · LOW-VALUE **18** · clusters **23** · drafts **14**

Key shorthand: `x_validate_calibration_data__mutmut_N`, `x_depth_to_feet__mutmut_N`, `x_get_depth_calibration_service__mutmut_N`, `x_reset_depth_calibration_service__mutmut_N`, `xǁ…ǁ` = class-qualified (meta keys use U+01C1 separators, e.g. `xǁDepthCalibrationServiceǁ_parse_calibration_dict__mutmut_12`).

## Coverage snapshot (unit tier)

`test_depth_calibration_service.py` covers validation raises (empty/negative/zero/out-of-range/duplicate), the non-monotonic *warning occurrence* (`match="non-monotonic"`), interpolation at knots and midpoints, extrapolation *bounds* (`result < 5.0`, `result > 50.0`, `> 0`), single-point scaling, format strings, registration/query/caching surface, DB-load happy path (`execute` called once), corrupt/exception paths (return None). Error-message `match=` patterns are loose substrings, so literal message mutations with intact substrings survive. Message *content* beyond the substring, warning message *values*, stacklevel, log payloads, and the shape of the DB *statement* are unasserted.

---

# TEST-GAP clusters (32 keys, 14 clusters)

## G-A. Depth-range validation off-by-one at documented boundaries — 2 keys

**Keys:** `x_validate_calibration_data__mutmut_17`, `x_validate_calibration_data__mutmut_19`

```python
- if point.depth_value < 0 or point.depth_value > 1:
+ if point.depth_value <= 0 or point.depth_value > 1:   # mutmut_17 → rejects legitimate depth 0.0
+ if point.depth_value < 0 or point.depth_value >= 1:   # mutmut_19 → rejects legitimate depth 1.0
```

**Why TEST-GAP:** verified against shipped code: `depth_value=0.0` and `depth_value=1.0` are ACCEPTED (no raise), and the codebase's own `TestCalibrationPoint.test_depth_value_boundaries` documents 0.0/1.0 as valid depths. Each mutant flips a documented-inclusive boundary into exclusive, spuriously rejecting valid calibration data. The existing out-of-range test uses 1.5 / -0.1 — strictly-outside values that still raise under the mutants — so it survives.

## G-B. Non-monotonic loop lower bound — spurious warning on valid data — 1 key

**Key:** `x_validate_calibration_data__mutmut_33`

```python
- for i in range(1, len(sorted_points)):
+ for i in range(len(sorted_points)):
```

**Why TEST-GAP:** at `i=0`, `sorted_points[i-1]` wraps to the LAST point, so on any valid monotonic multi-point calibration the first comparison is (last.distance, first.distance) → `curr < prev` → a spurious `UserWarning("non-monotonic...")` fires on *valid* data. Simulated against shipped behavior: original emits zero warnings for the 3-point monotonic fixture; mutant warns. No unit test runs `validate_calibration_data` on multi-point valid data under a warning-as-error/recwarn check (the one valid-data test uses a single point, where the mutant compares the point to itself and stays silent).

## G-C. Non-monotonic inequality made inclusive — 1 key

**Key:** `x_validate_calibration_data__mutmut_40`

```python
- if curr_distance < prev_distance:
+ if curr_distance <= prev_distance:
```

**Why TEST-GAP:** equal distances at two depths (a plateau, e.g. 0.2→10, 0.5→10, 0.8→20) are legitimate monotonic-non-decreasing data. Verified: shipped code emits **zero** warnings on a plateau; the mutant warns. No unit test feeds plateau distances to `validate_calibration_data` with a no-warn assertion.

## G-D. Non-monotonic warning interpolates the WRONG previous depth — 1 key

**Key:** `x_validate_calibration_data__mutmut_48`

```python
- f"but previous point at depth {sorted_points[i - 1].depth_value} "
+ f"but previous point at depth {sorted_points[i - 2].depth_value} "
```

**Why TEST-GAP:** this is not a cosmetic literal change — it changes the *data* reported by the warning (the whole product of this code path). At `i=1`, `i-2` wraps to the last point, so the warning names a different depth/distance pair than the actual inversion. The existing test only does `pytest.warns(UserWarning, match="non-monotonic")`, which passes on any wording. A 3-point fixture `[0.2→30, 0.5→10, 0.8→40]` inverts at i=1: original names "depth 0.2 … maps to 30 feet", mutant names "depth 0.8 … maps to 40 feet" — an assertion on the reported previous depth/distance kills it.

## G-E. Single-point zero-depth guard — ZeroDivisionError path — 1 key

**Key:** `x_depth_to_feet__mutmut_15`

```python
- if point.depth_value == 0:
+ if point.depth_value == 1:
```

**Why TEST-GAP:** the guard exists to prevent division by zero on single-point calibrations measured *at the camera*. Verified: shipped `depth_to_feet(0.5, single point (0.0, 7.5))` returns `7.5`; the mutant falls through to `depth * (distance / 0.0)` → **ZeroDivisionError**. Second observable facet: a single point with `depth_value=1.0` (query 0.5) returns `10.0` shipped but `20.0` (raw `distance_feet`) on the mutant. The existing single-point test uses depth 0.5 — unaffected by either change.

## G-F. Distance clamp floor raised — 1 key

**Key:** `x_depth_to_feet__mutmut_52`

```python
- return max(0.1, result)
+ return max(1.1, result)
```

**Why TEST-GAP:** every extrapolation that clamps returns exactly `0.1` feet shipped; the mutant returns `1.1`. Verified reachable with a calibration that extrapolates negative near zero: `[(0.1,0.4),(0.2,0.8),(0.9,45.0)]` at depth 0.001 → shipped `0.1`, mutant `1.1`. The existing near-zero tests assert only `result > 0` and `result < 2.0` — `1.1` satisfies both, hence the survival.

## G-G. DB query statement mutated (shape of the SELECT) — 4 keys

**Keys:** `xǁDepthCalibrationServiceǁ_load_calibration_from_db__mutmut_3`, `..._mutmut_4`, `..._mutmut_5`, `..._mutmut_6`

```python
- result = await self._session.execute(select(Camera).where(Camera.id == camera_id))
+ result = await self._session.execute(None)                                        # _3
+ result = await self._session.execute(select(Camera).where(None))                  # _4 → renders "WHERE NULL"
+ result = await self._session.execute(select(None).where(Camera.id == camera_id))  # _5 → projects "NULL AS anon_1"
+ result = await self._session.execute(select(Camera).where(Camera.id != camera_id))# _6 → inverted predicate
```

**Why TEST-GAP:** under an `AsyncMock` session the return value is canned, so the *only* difference is the statement the mock records — and that difference is real and inspectable (all four verified against live SQLAlchemy text rendering): `_3` records `None` instead of a `Select`; `_4` loses the `cameras.id` predicate (`WHERE NULL`); `_5` keeps the predicate but projects `NULL AS anon_1` instead of the camera columns; `_6` inverts the predicate (`!=`). A unit test capturing `mock_session.execute.call_args` and asserting the compiled statement (a `Select`, contains `cameras.id`, params `== camera_id`, no `!=`, not projecting NULL) kills all four. The existing DB-load test only asserts `execute.assert_called_once()`.

## G-H. Parsed calibration loses its camera_id — 2 keys

**Keys:** `xǁDepthCalibrationServiceǁ_load_calibration_from_db__mutmut_11`, `xǁDepthCalibrationServiceǁ_parse_calibration_dict__mutmut_23`

```python
- return self._parse_calibration_dict(camera_id, camera.calibration_data)   # load_11
+ return self._parse_calibration_dict(None, camera.calibration_data)
- return CalibrationData(camera_id=camera_id, ...)                          # parse_23
+ return CalibrationData(camera_id=None, ...)
```

**Why TEST-GAP:** the returned `CalibrationData.camera_id` becomes `None`. The service cache is keyed by the *argument*, so conversions still work — which is why every existing test passes: the unit load test asserts only the converted distance (`≈12.0`), and the integration tests that DO assert `camera_id` are out of the unit tier. Direct kill: `service._parse_calibration_dict("cam7", {...}).camera_id == "cam7"`; load-path kill: after a DB conversion, `service.get_calibration("db_camera").camera_id == "db_camera"`.

## G-I. Parsed points lose reference_name — 5 keys

**Keys:** `xǁDepthCalibrationServiceǁ_parse_calibration_dict__mutmut_12`, `_15`, `_20`, `_21`, `_22`

```python
- reference_name=p.get("reference_name"),
+ reference_name=None,                      # _12
+ (line dropped → dataclass default None)   # _15
+ reference_name=p.get(None),               # _20  (dict.get(None) is legal → always None)
+ reference_name=p.get("XXreference_nameXX"),  # _21
+ reference_name=p.get("REFERENCE_NAME"),   # _22  (wrong key)
```

**Why TEST-GAP:** all five silently drop the optional reference name from DB-loaded calibration points (`p.get` on a wrong/None key returns `None`; no exception is raised, so the `except (KeyError, TypeError)` path never fires). `reference_name` is a first-class documented field of `CalibrationPoint`, and the payload format written by the Camera model carries it. The unit DB-load fixture omits `reference_name`, so nothing distinguishes shipped from mutant. Kill: parse a payload whose point has `"reference_name": "porch"` and assert `parsed.calibration_points[0].reference_name == "porch"`.

## G-J. image_width lost on parse — 5 keys

**Keys:** `xǁDepthCalibrationServiceǁ_parse_calibration_dict__mutmut_25`, `_29`, `_31`, `_32`, `_33`

```python
- image_width=data.get("image_width"),
+ image_width=None,                 # _25
+ (arg dropped → default None)      # _29
+ image_width=data.get(None),       # _31
+ image_width=data.get("XXimage_widthXX"),  # _32
+ image_width=data.get("IMAGE_WIDTH"),      # _33
```

**Why TEST-GAP:** every variant yields `image_width=None` regardless of payload; `CalibrationData.image_width` is a documented field consumed by the calibration API. No unit test asserts `image_width` after a parse/DB load (the integration file does — but it is not in the harness's unit selection). Kill: `service._parse_calibration_dict("cam", {"calibration_points":[…], "image_width": 1920}).image_width == 1920`.

## G-K. image_height lost on parse — 5 keys

**Keys:** `xǁDepthCalibrationServiceǁ_parse_calibration_dict__mutmut_26`, `_30`, `_34`, `_35`, `_36`

```python
- image_height=data.get("image_height"),
+ image_height=None,                # _26
+ (arg dropped → default None)      # _30
+ image_height=data.get(None),      # _34
+ image_height=data.get("XXimage_heightXX"),  # _35
+ image_height=data.get("IMAGE_HEIGHT"),      # _36
```

**Why TEST-GAP:** mirror of G-J for `image_height`; same reasoning, same kill (`… .image_height == 1080`).

## G-L. Cache-hit still consults the database — 1 key

**Key:** `xǁDepthCalibrationServiceǁconvert_depth_to_feet__mutmut_3`

```python
- if calibration is None and self._session is not None:
+ if calibration is None or self._session is not None:
```

**Why TEST-GAP:** with a registered (cached) calibration AND a session attached, the shipped code returns the cached conversion without touching the DB (verified: 0 `execute` calls, result 10.0); the mutant enters the load branch, and the DB result overwrites the cache hit — end-to-end verified with a plain `AsyncMock` session the load resolves to `None` and the conversion returns **None instead of the correct cached distance**. The existing cached-conversion test runs a session-less service, and the DB-load test runs an empty cache — the cache-hit + session combination is untested.

## G-M. DB loader invoked with camera_id=None — 1 key

**Key:** `xǁDepthCalibrationServiceǁconvert_depth_to_feet__mutmut_7`

```python
- calibration = await self._load_calibration_from_db(camera_id)
+ calibration = await self._load_calibration_from_db(None)
```

**Why TEST-GAP:** the emitted query is parameterized with `None` instead of the requested camera — on a real database it loads the WRONG (or no) camera's calibration while returning a plausible number through a mock. The mocked session in the only DB-load test ignores the query, so the mutant survives. Kill: capture `mock_session.execute.call_args[0][0]` and assert the compiled params contain `"db_camera"` (mutant: `{'id_1': None}`).

## G-N. Write-through cache inverted / nulled — 2 keys

**Keys:** `xǁDepthCalibrationServiceǁconvert_depth_to_feet__mutmut_8`, `_mutmut_9`

```python
- if calibration is not None:          # _8
+ if calibration is None:
- self._calibration_cache[camera_id] = calibration   # _9
+ self._calibration_cache[camera_id] = None
```

**Why TEST-GAP:** after a successful DB load the shipped code caches the CalibrationData (verified: second conversion reuses cache — 1 execute call total; `get_calibration` returns the parsed object; `is_calibrated` True). Mutant `_8` never caches positives (and *does* cache the None of failed loads, poisoning `is_calibrated` to True for corrupt cameras); mutant `_9` stores `None` under the camera id. Both are killed by asserting the cache surface after one DB-backed conversion: `service.get_calibration("db_camera") is not None` (fails on both mutants — `_9` stores None, `_8` never stores) and/or that the second conversion performs no further `execute`.

---

# EQUIVALENT clusters (7 keys, 4 clusters)

## E-A. warnings.warn category omitted / set to None — 2 keys

**Keys:** `x_validate_calibration_data__mutmut_42`, `x_validate_calibration_data__mutmut_45`

```python
- UserWarning,                          # _42: category → None
+ None,
- UserWarning,                          # _45: category argument removed entirely
```

**Why EQUIVALENT (per key):** `_42`: `warnings.warn(msg, None, stacklevel=2)` — `None` is Python's "use default" marker for the category argument; verified experimentally: no error, the emitted warning's category is `UserWarning`. `_45`: omitting the category entirely also defaults to `UserWarning` (same C-level default). Both are bit-identical in observable behavior (`pytest.warns(UserWarning)` still matches, message and timing unchanged) — semantically identical, no test can or should kill them.

## E-B. Loop-exit `break` → `return` at function tail — 1 key

**Key:** `x_validate_calibration_data__mutmut_50`

```python
- break
+ return
```

**Why EQUIVALENT:** AST-verified: the monotonic-check `for` loop is the *last statement* of `validate_calibration_data` — `break` exits the loop and then falls off the end returning `None`; `return` exits the function returning `None`. Identical control flow, return value, warnings, and side effects for every input. Unobservable by construction.

## E-C. Bracket-selection tie at an exact calibration knot — 2 keys

**Keys:** `x_depth_to_feet__mutmut_20`, `x_depth_to_feet__mutmut_23`

```python
- if point.depth_value <= depth:                    # _20
+ if point.depth_value < depth:
- if point.depth_value >= depth and upper_point is None:   # _23
+ if point.depth_value > depth and upper_point is None:
```

**Why EQUIVALENT (per key):** both conditions differ from the original ONLY when the queried depth exactly equals a calibration knot; elsewhere `<` and `<=` select the identical point. Verified against shipped code at every knot of the 3-point fixture (0.15→5.0, 0.45→20.0, 0.75→50.0): the mutants' shifted bracket still interpolates with factor exactly 0.0 or 1.0, which returns the knot's own distance exactly (e.g. mutant `_20` at 0.75: bracket (0.45,0.75), factor `(0.75-0.45)/(0.75-0.45)==1.0` → `20.0 + 1.0*30.0 == 50.0`; mutant `_23` at 0.45: bracket (0.45,0.75), factor 0.0 → exactly `20.0`). The endpoints' `depth_range == 0 → return distance` fast path and the extrapolation branches collapse to the same knot distance too. Caveat, stated for the record: the mutants become observable only on payloads validation rejects — duplicate depth values at the queried depth (e.g. two points at 0.5): shipped returns 30.0, `_20` returns 10.0. `validate_calibration_data` explicitly forbids duplicates and the service's registered path enforces it; direct `depth_to_feet` calls with contract-violating input are out of the module's behavior contract, so these are equivalent-through-the-contract. Testing the duplicate-payload difference would pin invalid-data behavior — not recommended; if the arbiter wants it, one assertion (`depth_to_feet(0.5, dup) == 30.0`) kills `_20` only, leaving `_23` genuinely equivalent.

## E-D. calibration_points fallback default mutated between falsy values — 2 keys

**Keys:** `xǁDepthCalibrationServiceǁ_parse_calibration_dict__mutmut_3`, `..._mutmut_5`

```python
- calibration_points_data = data.get("calibration_points", [])
+ calibration_points_data = data.get("calibration_points", None)   # _3
+ calibration_points_data = data.get("calibration_points", )       # _5 (trailing comma = single-arg call → default None)
```

**Why EQUIVALENT (per key):** the very next statement is `if not calibration_points_data: return None`. For a payload *with* the key, all three calls return the same list. For a payload *without* the key, `[]` (original) and `None` (both mutants) are both falsy → both hit `return None` → same result. `_5` is additionally a pure syntax-level mutation (the trailing comma makes it `.get("calibration_points")` — the one-arg call whose default is already `None`). No input distinguishes any pair.

---

# LOW-VALUE clusters (18 keys, 5 clusters)

## L-A. Singleton lifecycle log-message literals — 8 keys

**Keys:** `x_get_depth_calibration_service__mutmut_9`, `_10`, `_11`, `_12`; `x_reset_depth_calibration_service__mutmut_4`, `_5`, `_6`, `_7`

```python
- logger.info("Initialized global DepthCalibrationService")
+ logger.info(None) / "XXInitialized global DepthCalibrationServiceXX" / "initialized global depthcalibrationservice" / "INITIALIZED GLOBAL DEPTHCALIBRATIONSERVICE"
- logger.debug("Reset global DepthCalibrationService")
+ logger.debug(None) / "XX…XX" / lower / upper
```

**Why LOW-VALUE:** the singleton create/reuse/reset *behavior* (instance identity, `_singleton` contents) is unchanged — only the diagnostic message string varies. No test should pin logger wording; killing these would require `caplog` message-equality assertions with zero behavioral value.

## L-B. Service lifecycle log-message literals — 3 keys

**Keys:** `xǁDepthCalibrationServiceǁregister_calibration__mutmut_3`, `xǁDepthCalibrationServiceǁunregister_calibration__mutmut_2`, `xǁDepthCalibrationServiceǁ_load_calibration_from_db__mutmut_15`

```python
- logger.info(f"Registered calibration for camera {data.camera_id} with {len(data.calibration_points)} points")
+ logger.info(None)                                             # register_3
- logger.info(f"Unregistered calibration for camera {camera_id}")
+ logger.info(None)                                             # unregister_2
- logger.warning(f"Failed to load calibration from database for camera {camera_id}: {e}")
+ logger.warning(None)                                          # load_15
```

**Why LOW-VALUE:** cache write/removal semantics, error propagation, and return values are untouched; only log payloads change. Not worth tests.

## L-C. Validation error-message literals (cosmetic rewordings) — 4 keys

**Keys:** `x_validate_calibration_data__mutmut_3`, `_4`, `_13`, `_14`

```python
- raise InvalidCalibrationError("Calibration data must have at least one calibration point")
+ raise ...("XXCalibration data must have at least one calibration pointXX")   # _3
+ raise ...("calibration data must have at least one calibration point")        # _4
- "Calibration point has zero distance - distance must be positive"
+ "XXCalibration point has zero distance - distance must be positiveXX"         # _13
+ "calibration point has zero distance - distance must be positive"             # _14
```

**Why LOW-VALUE:** exception type, raise site, and the information content of the message are unchanged — only case/decoration of the same text (which is why the existing `pytest.raises(match="at least one calibration point")` / `match="zero distance"` substring matches still pass). Reword-only; killing them means asserting message case for no behavioral gain.

## L-D. warnings.warn stacklevel cosmetics — 2 keys

**Keys:** `x_validate_calibration_data__mutmut_46`, `x_validate_calibration_data__mutmut_49`

```python
- stacklevel=2,               # _46: argument removed → default 1
+ (dropped)
- stacklevel=2,               # _49
+ stacklevel=3,
```

**Why LOW-VALUE:** the warning's category, message, and firing conditions are identical; only which *frame* the warning blames in a terminal is affected. `pytest.warns` ignores it. Diagnostic polish, not behavior.

## L-E. Guard short-circuit inversion with log-only delta — 1 key

**Key:** `xǁDepthCalibrationServiceǁ_load_calibration_from_db__mutmut_8`

```python
- if camera is None or camera.calibration_data is None:
+ if camera is None and camera.calibration_data is None:
```

**Why LOW-VALUE:** return value is `None` for every input on both variants (end-to-end verified: `camera is None` → shipped returns None silently, mutant raises AttributeError *inside its own try* and the `except Exception` returns None; `calibration_data is None` → shipped returns None, mutant enters `_parse_calibration_dict(camera_id, None)` → `.get` on None → same except → None; camera-with-data → identical). The ONLY observable difference is a spurious "Failed to load calibration…" warning line on the two no-data paths — a log-only delta. A `caplog` test could pin "no warning on clean miss", but that is log-message policing, not behavior. (Flag: if the arbiter's rubric prefers "observable-via-caplog ⇒ TEST-GAP", this is the single key that moves; the totals line reflects the log-only ruling.)

---

## Key → cluster map (exhaustive, non-overlapping)

| Cluster | Class | Count | Keys |
|---|---|---|---|
| G-A | TEST-GAP | 2 | vcd 17, 19 |
| G-B | TEST-GAP | 1 | vcd 33 |
| G-C | TEST-GAP | 1 | vcd 40 |
| G-D | TEST-GAP | 1 | vcd 48 |
| G-E | TEST-GAP | 1 | dtf 15 |
| G-F | TEST-GAP | 1 | dtf 52 |
| G-G | TEST-GAP | 4 | load 3, 4, 5, 6 |
| G-H | TEST-GAP | 2 | load 11, parse 23 |
| G-I | TEST-GAP | 5 | parse 12, 15, 20, 21, 22 |
| G-J | TEST-GAP | 5 | parse 25, 29, 31, 32, 33 |
| G-K | TEST-GAP | 5 | parse 26, 30, 34, 35, 36 |
| G-L | TEST-GAP | 1 | convert 3 |
| G-M | TEST-GAP | 1 | convert 7 |
| G-N | TEST-GAP | 2 | convert 8, 9 |
| E-A | EQUIVALENT | 2 | vcd 42, 45 |
| E-B | EQUIVALENT | 1 | vcd 50 |
| E-C | EQUIVALENT | 2 | dtf 20, 23 |
| E-D | EQUIVALENT | 2 | parse 3, 5 |
| L-A | LOW-VALUE | 8 | get 9, 10, 11, 12; reset 4, 5, 6, 7 |
| L-B | LOW-VALUE | 3 | register 3; unregister 2; load 15 |
| L-C | LOW-VALUE | 4 | vcd 3, 4, 13, 14 |
| L-D | LOW-VALUE | 2 | vcd 46, 49 |
| L-E | LOW-VALUE | 1 | load 8 |

Per-function cross-check: validate 14 (5G/3E/6L) · depth_to_feet 4 (2G/2E) · get 4 (4L) · reset 4 (4L) · load 7 (5G/2L) · parse 18 (16G/2E) · convert 4 (4G) · register 1 (1L) · unregister 1 (1L). 5+2+5+16+4 = **32 G**; 3+2+2 = **7 E**; 6+4+4+2+1+1 = **18 L**.

**Totals: TEST-GAP 32, EQUIVALENT 7, LOW-VALUE 18 — sum 57**

---

# Drafted kill-tests (14 drafts — one per TEST-GAP cluster)

All target `backend/tests/unit/services/test_depth_calibration_service.py` (the mutmut selection). Existing fixtures (`sample_calibration_data`, `multi_point_calibration_data`) and imports (`AsyncMock`, `MagicMock`, `pytest`) are reused. **ALL DRAFTS UNVERIFIED — do not run in this tier (serial pytest lane owns the box).**

**D1 — G-A (kills vcd 17, 19)** `::TestValidateCalibrationData::test_accepts_boundary_depth_values_0_and_1`
```python
def test_accepts_boundary_depth_values_0_and_1(self) -> None:
    for dv in (0.0, 1.0):
        data = CalibrationData(camera_id="c", calibration_points=[CalibrationPoint(depth_value=dv, distance_feet=10.0)])
        validate_calibration_data(data)  # boundary depths are documented-valid; must NOT raise
```
UNVERIFIED — fails on mutant (InvalidCalibrationError on 0.0 [_17] / 1.0 [_19]), passes on original (verified accepted).

**D2 — G-B (kills vcd 33)** `::TestValidateCalibrationData::test_monotonic_multi_point_does_not_warn`
```python
def test_monotonic_multi_point_does_not_warn(self, multi_point_calibration_data: CalibrationData) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)   # NOTE: warns(None) is deprecated; error-filter is the idiom
        validate_calibration_data(multi_point_calibration_data)
```
UNVERIFIED — fails on mutant (spurious UserWarning from wrapped `sorted_points[-1]` comparison), passes on original (0 warnings, verified).

**D3 — G-C (kills vcd 40)** `::TestValidateCalibrationData::test_plateau_distance_does_not_warn`
```python
def test_plateau_distance_does_not_warn(self) -> None:
    data = CalibrationData(camera_id="c", calibration_points=[
        CalibrationPoint(depth_value=0.2, distance_feet=10.0),
        CalibrationPoint(depth_value=0.5, distance_feet=10.0),   # plateau — still monotonic non-decreasing
        CalibrationPoint(depth_value=0.8, distance_feet=20.0)])
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        validate_calibration_data(data)
```
UNVERIFIED — fails on mutant (`<=` warns on the plateau), passes on original (verified silent).

**D4 — G-D (kills vcd 48)** `::TestValidateCalibrationData::test_non_monotonic_warning_reports_previous_point_depth`
```python
def test_non_monotonic_warning_reports_previous_point_depth(self) -> None:
    data = CalibrationData(camera_id="c", calibration_points=[
        CalibrationPoint(depth_value=0.2, distance_feet=30.0),
        CalibrationPoint(depth_value=0.5, distance_feet=10.0),   # inversion at i=1
        CalibrationPoint(depth_value=0.8, distance_feet=40.0)])
    with pytest.warns(UserWarning) as rec:
        validate_calibration_data(data)
    msg = str(rec[0].message)
    assert "depth 0.5" in msg and "previous point at depth 0.2" in msg and "30 feet" in msg
```
UNVERIFIED — fails on mutant (names `0.8 … 40 feet` via wrapped `i-2`), passes on original.

**D5 — G-E (kills dtf 15)** `::TestDepthToFeet::test_single_point_calibration_zero_depth_point_returns_distance`
```python
def test_single_point_calibration_zero_depth_point_returns_distance(self) -> None:
    zero = CalibrationData(camera_id="c", calibration_points=[CalibrationPoint(depth_value=0.0, distance_feet=7.5)])
    assert depth_to_feet(0.5, zero) == pytest.approx(7.5)      # guard: no divide-by-zero
    one = CalibrationData(camera_id="c", calibration_points=[CalibrationPoint(depth_value=1.0, distance_feet=20.0)])
    assert depth_to_feet(0.5, one) == pytest.approx(10.0)      # dv==1.0 still scales linearly
```
UNVERIFIED — fails on mutant (ZeroDivisionError / 20.0), passes on original (7.5 / 10.0 verified).

**D6 — G-F (kills dtf 52)** `::TestDepthToFeet::test_clamps_extrapolation_to_minimum_distance_floor`
```python
def test_clamps_extrapolation_to_minimum_distance_floor(self) -> None:
    data = CalibrationData(camera_id="c", calibration_points=[
        CalibrationPoint(depth_value=0.1, distance_feet=0.4),
        CalibrationPoint(depth_value=0.2, distance_feet=0.8),
        CalibrationPoint(depth_value=0.9, distance_feet=45.0)])
    assert depth_to_feet(0.001, data) == pytest.approx(0.1)    # documented floor, not 1.1
```
UNVERIFIED — fails on mutant (1.1), passes on original (0.1 verified).

**D7 — G-G (kills load 3, 4, 5, 6)** `::TestDepthCalibrationServiceConversion::test_db_load_selects_camera_by_id`
```python
@pytest.mark.asyncio
async def test_db_load_selects_camera_by_id(self, calibration_service: DepthCalibrationService) -> None:
    from sqlalchemy import Select
    session = AsyncMock()
    result = MagicMock(); result.scalar_one_or_none.return_value = None
    session.execute.return_value = result
    calibration_service._session = session
    await calibration_service.convert_depth_to_feet("db_camera", 0.4)
    stmt = session.execute.call_args[0][0]
    assert isinstance(stmt, Select)                      # kills _3 (None passed to execute)
    text = str(stmt); params = stmt.compile().params
    assert "cameras.id" in text and "!=" not in text     # kills _4 (WHERE NULL) and _6 (inverted)
    assert "NULL AS anon_1" not in text                  # kills _5 (projected NULL)
    assert set(params.values()) == {"db_camera"}
```
UNVERIFIED — fails per-mutant as annotated (all four renderings verified against live SQLAlchemy), passes on original.

**D8 — G-H (kills load 11, parse 23)** `::TestDepthCalibrationServiceQuery::test_parsed_calibration_preserves_camera_id`
```python
@pytest.mark.asyncio
async def test_parsed_calibration_preserves_camera_id(self, calibration_service: DepthCalibrationService) -> None:
    parsed = calibration_service._parse_calibration_dict(
        "cam7", {"calibration_points": [{"depth_value": 0.4, "distance_feet": 12.0}]})
    assert parsed is not None and parsed.camera_id == "cam7"          # kills parse 23 directly
    session = AsyncMock(); result = MagicMock()
    camera = MagicMock(); camera.calibration_data = {"calibration_points": [{"depth_value": 0.4, "distance_feet": 12.0}]}
    result.scalar_one_or_none.return_value = camera; session.execute.return_value = result
    calibration_service._session = session
    await calibration_service.convert_depth_to_feet("db_camera", 0.4)
    assert calibration_service.get_calibration("db_camera").camera_id == "db_camera"   # kills load 11
```
UNVERIFIED — fails on mutants (`camera_id is None`), passes on original.

**D9 — G-I (kills parse 12, 15, 20, 21, 22)** `::TestDepthCalibrationServiceQuery::test_parse_preserves_reference_name`
```python
def test_parse_preserves_reference_name(self, calibration_service: DepthCalibrationService) -> None:
    parsed = calibration_service._parse_calibration_dict(
        "cam7", {"calibration_points": [{"depth_value": 0.4, "distance_feet": 12.0, "reference_name": "porch"}]})
    assert parsed.calibration_points[0].reference_name == "porch"
```
UNVERIFIED — fails on all five mutants (`reference_name is None`), passes on original.

**D10 — G-J (kills parse 25, 29, 31, 32, 33)** `::TestDepthCalibrationServiceQuery::test_parse_preserves_image_width`
```python
def test_parse_preserves_image_width(self, calibration_service: DepthCalibrationService) -> None:
    parsed = calibration_service._parse_calibration_dict(
        "cam7", {"calibration_points": [{"depth_value": 0.4, "distance_feet": 12.0}], "image_width": 1920})
    assert parsed.image_width == 1920
```
UNVERIFIED — fails on mutants (None), passes on original.

**D11 — G-K (kills parse 26, 30, 34, 35, 36)** `::TestDepthCalibrationServiceQuery::test_parse_preserves_image_height`
```python
def test_parse_preserves_image_height(self, calibration_service: DepthCalibrationService) -> None:
    parsed = calibration_service._parse_calibration_dict(
        "cam7", {"calibration_points": [{"depth_value": 0.4, "distance_feet": 12.0}], "image_height": 1080})
    assert parsed.image_height == 1080
```
UNVERIFIED — fails on mutants (None), passes on original.

**D12 — G-L (kills convert 3)** `::TestDepthCalibrationServiceConversion::test_cache_hit_skips_database`
```python
@pytest.mark.asyncio
async def test_cache_hit_skips_database(
    self, calibration_service: DepthCalibrationService, sample_calibration_data: CalibrationData) -> None:
    calibration_service.register_calibration(sample_calibration_data)
    session = AsyncMock()          # DB would answer with garbage; correct code must never ask it
    calibration_service._session = session
    result = await calibration_service.convert_depth_to_feet("front_door", 0.3)
    assert result == pytest.approx(10.0)          # mutant returns None (DB result clobbers the hit)
    session.execute.assert_not_called()
```
UNVERIFIED — fails on mutant (verified: None returned + execute called), passes on original (0 execute calls, 10.0, verified).

**D13 — G-M (kills convert 7)** `::TestDepthCalibrationServiceConversion::test_db_query_parameterized_with_camera_id`
```python
@pytest.mark.asyncio
async def test_db_query_parameterized_with_camera_id(self, calibration_service: DepthCalibrationService) -> None:
    session = AsyncMock(); result = MagicMock(); result.scalar_one_or_none.return_value = None
    session.execute.return_value = result
    calibration_service._session = session
    await calibration_service.convert_depth_to_feet("db_camera", 0.4)
    params = session.execute.call_args[0][0].compile().params
    assert set(params.values()) == {"db_camera"}   # mutant queries with None
```
UNVERIFIED — fails on mutant (`{'id_1': None}`), passes on original.

**D14 — G-N (kills convert 8, 9)** `::TestDepthCalibrationServiceConversion::test_db_loaded_calibration_is_cached`
```python
@pytest.mark.asyncio
async def test_db_loaded_calibration_is_cached(self, calibration_service: DepthCalibrationService) -> None:
    session = AsyncMock(); result = MagicMock()
    camera = MagicMock(); camera.calibration_data = {"calibration_points": [{"depth_value": 0.4, "distance_feet": 12.0}]}
    result.scalar_one_or_none.return_value = camera; session.execute.return_value = result
    calibration_service._session = session
    assert await calibration_service.convert_depth_to_feet("db_camera", 0.4) == pytest.approx(12.0)
    assert calibration_service.is_calibrated("db_camera") is True
    assert calibration_service.get_calibration("db_camera") is not None   # _8 never caches, _9 caches None
    assert await calibration_service.convert_depth_to_feet("db_camera", 0.4) == pytest.approx(12.0)
    assert session.execute.call_count == 1                                 # write-through verified
```
UNVERIFIED — fails on mutants (get_calibration None / re-execute), passes on original (1 execute across two converts, cached object verified).

---

*Triage notes: extraction via AST-segment diff of the shipped `mutants/.../depth_calibration_service.py` against `__mutmut_orig` (the `.spans` character offsets are stale against the on-disk file — first-pass diffs built from them were garbage and were discarded). Borderline semantics were checked by importing the shipped module in a scratch script (read-only): vcd 17/19 boundary acceptance, vcd 33/40 spurious-warning behavior, vcd 42 category-None default, vcd 50 tail-loop structure, dtf 15 ZeroDivisionError, dtf 20/23 knot identity + duplicate-payload caveat, dtf 52 clamp reachability (0.1 vs 1.1), load 8 all-input None equivalence, load 3–6 live-SQLAlchemy statement renderings, convert 3/8/9 cache end-to-end. No repo file touched; no pytest or mutmut executed.*
