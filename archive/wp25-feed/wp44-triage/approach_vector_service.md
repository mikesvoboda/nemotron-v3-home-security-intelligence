# WP4.4 Triage Dossier — backend/services/approach_vector_service.py

- **Survivors:** 95 of 334 checked (239 killed, 0 unchecked) — source: `mutants/backend/services/approach_vector_service.py.meta`
- **Diff capture:** all 95 via `get_diff_for_mutant()` in one batch process (no `mutmut run`), saved to `/tmp/wp25/wp44-triage/approach_diffs.json`
- **Covering test file (all functions):** `backend/tests/unit/services/test_approach_vector_service.py` (from `mutants/mutmut-stats.json::tests_by_mangled_function_name`)
- **Classification totals:** TEST-GAP 76 · EQUIVALENT 17 · LOW-VALUE 2 (sum = 95 ✓)

## Why so many survive (root cause)

Every test in `test_approach_vector_service.py` is either (a) a geometry helper called directly with **axis-aligned, origin-touching inputs** (square `(0,0)-(1,1)`, segments with `y1=0`/`x1=0`, 2-vertex guards) or (b) an async integration test where `_get_zone`/`_get_active_dweller_track_ids`/`_get_recent_detections` are **patched and whose return values are only ever asserted to be `[]`**. The service's success path (valid zone + ≥2 detections + expected vector fields), its 3+ detection trajectories, its exact numeric outputs, its output-dict keys, and all non-origin/non-axis-aligned geometry are never asserted. Existing assertions are also range-loose (`speed > 0`, `0 <= dir < 360`, `< 0.01` tolerance) so wrong-but-plausible numbers pass.

## Cluster table

| # | Cluster (pattern @ function) | n | Keys (examples) | Class | Note / test weakness |
|---|---|---|---|---|---|
| 1 | logger.warning/debug message + `extra=` payload mutations (text→None, extra removed, extra key renames/case, count 1→2) @ `get_zone_approach_vectors` | 12 | gva_4, gva_37, gva_47 | EQUIVALENT | Log-only; return value unaffected. gva_4/10/36/37/39/40/41/42/43/44/45/47 |
| 2 | Debug-extra key rename `v["XXis_approachingXX"]`/`v["IS_APPROACHING"]` inside the `sum()` — KeyError if vectors list non-empty @ `get_zone_approach_vectors` | 2 | gva_48, gva_49 | LOW-VALUE | Crash would surface only in debug-log evaluation; tests never produce non-empty vectors anyway; nobody should assert log payloads. |
| 3 | `None` clobber of query/derived values (`zone=None`, `polygon=None`, `normalized_polygon=None`, `zone_centroid=None`, `active_in_zone=None`, `camera_id=None`) @ `get_zone_approach_vectors` | 6 | gva_1, gva_5, gva_16 | TEST-GAP | All 4 integration tests assert only `== []`; success path untested. Killed by draft 6. |
| 4 | `None` clobber of helper **call arguments** (`_get_zone(None)`, centroid arg, dwellers arg, `camera_id=None`, `exclude_track_ids=None`) @ `get_zone_approach_vectors` | 5 | gva_2, gva_22, gva_23 | TEST-GAP | Mocked helpers, zero call-argument assertions. Killed by draft 6. |
| 5 | Polygon-validity guard boundary (`if polygon or`, `<=3`, `<4`) — 3-vertex polygon rejected / valid polygon treated invalid @ `get_zone_approach_vectors` | 3 | gva_7, gva_8, gva_9 | TEST-GAP | Tests use 1-point (invalid) and 4-point (valid) polygons only; triangle acceptance boundary untested. Killed by draft 6. |
| 6 | Polygon pixel→normalized math (`p[0]*image_width`, `p[1]/p[1]`, `p[1]*image_height`) @ `get_zone_approach_vectors` | 3 | gva_12, gva_13, gva_14 | TEST-GAP | Wrong coordinates only observable through success-path vectors/ETA. Killed by draft 6. |
| 7 | Track-loop logic: `track_id is None` flip, `sort(key=None)`, `sort(key=lambda: None)`, `<= MIN_DETECTIONS_FOR_VECTOR`, `continue`→`break` @ `get_zone_approach_vectors` | 5 | gva_27, gva_34, gva_35 | TEST-GAP | Every test feed ≤1 detection per track and ≤1 short track; sort with 1 element never compares. Killed by draft 6 (needs a 2-detection track + a 1-detection track). |
| 8 | `detections[-1]` → `detections[+1]` (== index 1) for last position & last timestamp @ `_calculate_approach_vector` | 2 | cav_18, cav_25 | TEST-GAP | Identical for all existing 2-detection fixtures; 3-point trajectory never used. Killed by draft 2. |
| 9 | Guard `first_pos is None or last_pos is None` → `and` @ `_calculate_approach_vector` | 1 | cav_20 | TEST-GAP | Divergence needs exactly-one None position (mixed-bbox track). Killed by draft 3. |
| 10 | Movement arithmetic: `dx/dy` `-`→`+`, component swap x↔y, `dx*dx`→`dx/dx` in `sqrt`, `speed = dist*time_delta` @ `_calculate_approach_vector` | 7 | cav_31, cav_41, cav_44 | TEST-GAP | Verified divergent: dir 113.96 vs 150.64, speed 0.1139 vs 0.0531 — but tests assert only `speed>0`, `0≤dir<360`. Killed by draft 1 (exact values). |
| 11 | Direction: `atan2(dx,-dy)`→`atan2(dx,+dy)`; wrap-block `<0`→`<=0`/`<1`, `+=360`→`=360`/`-=360`/`+=361` @ `_calculate_approach_vector` | 6 | cav_50, cav_53, cav_56 | TEST-GAP | dir flips 150.64→29.36 (atan); `dir==0.0` case kills `<=0`/`<1` (yields 360.0); negative-raw dir 330.64 kills `=360`/`-360`/`+361`. Killed by draft 1. |
| 12 | Distance call arg `last_pos[0],last_pos[1]` → `last_pos[1],last_pos[1]` @ `_calculate_approach_vector` | 1 | cav_65 | TEST-GAP | dist 0.1728 vs 0.2962, never asserted. Killed by draft 1. |
| 13 | `is_approaching = current < first` → `<=` @ `_calculate_approach_vector` | 1 | cav_77 | TEST-GAP | Equidistant (parallel-to-boundary) fixture: orig `False`, mutant `True` + bogus ETA. Killed by draft 3. |
| 14 | ETA branch guards `speed>0`→`>=0`, `current_distance>0`→`>=0` @ `_calculate_approach_vector` | 2 | cav_81, cav_83 | EQUIVALENT | 81: `is_approaching=True ∧ speed==0` impossible (positions would be equal ⇒ equal distances). 83: when `cd==0` both paths yield `eta=0.0`; `cd<0` impossible. |
| 15 | ETA estimation: `current/speed`→`current*speed`; `elif current_distance == 0`→`== 1` @ `_calculate_approach_vector` | 2 | cav_86, cav_88 | TEST-GAP | Verified: 0.0157 vs 5.576; inside-zone `eta` `None` vs `0.0`. Killed by drafts 1 & 3. |
| 16 | Returned dict key `"distance_to_zone"` → `"XXdistance_to_zoneXX"`/`"DISTANCE_TO_ZONE"` @ `_calculate_approach_vector` | 2 | cav_95, cav_96 | TEST-GAP | Would KeyError the caller (`get_zone_approach_vectors` reads the key) but the dict's keys are never asserted and caller success path untested. Killed by draft 1 (key assertion). |
| 17 | `float("inf")`→`float("INF")`; edge wrap `(i+1)%n`→`(i-1)%n` @ `_distance_to_polygon_boundary` | 2 | dpb_11, dpb_17 | EQUIVALENT | `float("INF")==inf` (case-insensitive). `(i-1)` iterates the **same undirected edge set**; point-to-segment distance is endpoint-symmetric ⇒ identical min. |
| 18 | `if len(polygon) < 3` → `<= 3` / `< 4` @ `_point_in_polygon` | 2 | pip_1, pip_2 | TEST-GAP | Triangle (len 3) acceptance untested — helper tests use only a 4-vertex square + a 2-vertex reject. Killed by draft 4. |
| 19 | Ray-cast loop range mutations: start edge `polygon[1]`, `range(n+1)`, `range(2,n+1)`, `range(1,n-1)`, `range(1,n+2)` @ `_point_in_polygon` | 4 | pip_8, pip_13, pip_15 | TEST-GAP | (11 `range(0,…)` is EQUIVALENT — see #20.) Grid-verified kills: tri `(0.3,0.5)` kills 13/14 (orig True→False); `(0.0,0.5)` kills 8/15. Axis-aligned square can't expose edge drops. Killed by draft 4. |
| 20 | `range(1,n+1)` → `range(0,n+1)` (leading degenerate v0→v0 iteration, cond always false) @ `_point_in_polygon` | 1 | pip_11 | EQUIVALENT | Verified no divergence on square/triangle/pentagon/notch grids. |
| 21 | Crossing-condition boundaries: `y<=max`→`y<max`, `x<=max`→`x<max` @ `_point_in_polygon` | 2 | pip_25, pip_30 | TEST-GAP | Deterministic originals at vertex-aligned/edge rows: tri `(0.1,0.5)` orig False vs ylt True; tri `(0.2,0.5)` (on edge) orig False vs xlt True. On-edge test deliberately asserts only `isinstance(bool)`. Killed by draft 4. |
| 22 | xinters arithmetic: `if p1y != p2y`→`==` (UnboundLocalError on non-vertical crossings), `xinters=None`, `+p1x`→`-p1x`, `/`→`*`, `(y-p1y)`→`(y+p1y)`, `(p2x-p1x)`→`(p2x+p1x)`, `(p2y-p1y)`→`(p2y+p1y)` @ `_point_in_polygon` | 7 | pip_35, pip_37, pip_41 | TEST-GAP | Every existing caller uses the vertical-left-edge square (guard `p1x==p2x` short-circuits, xinters never evaluated). Tri assertions kill all: `(0.3,0.5)` True (kills 35/36 crash, 37), `(0.5,0.25)` False + `(0.5,0.6)` True (kill 38/40/42), `(0.5,0.25)` kills 41. Killed by draft 4. |
| 23 | Flip-guard `p1x==p2x or x<=xinters` → `and` / `!=` / `<` @ `_point_in_polygon` | 3 | pip_43, pip_44, pip_45 | TEST-GAP | Kills: `(0.1,0.5)`→False (43), `(0.5,0.3)`→False (44), `(0.4,0.3)` (x==xinters exactly)→True (45). Killed by draft 4. |
| 24 | Point-segment degenerate branch: `px-x1`→`px+x1`, `py-y1`→`py+y1`, `**2`→`**3` (×2) @ `_point_to_segment_distance` | 4 | ptsd_13, ptsd_14, ptsd_16 | TEST-GAP | Existing degenerate test uses endpoint `(0,0)` — `+`/`-` and `2`/`3` coincide on coordinates 0/1. Non-origin degenerate seg `(2,3)-(2,3)` pt `(5,7)`: 5.0 vs 8.06/10.44/9.54. Killed by draft 5. |
| 25 | Point-segment projection `t`: `/`→`*`, `px-x1`→`px+x1`, `py-y1`→`py+y1` @ `_point_to_segment_distance` | 3 | ptsd_29, ptsd_32, ptsd_34 | TEST-GAP | Existing tests use unit horizontal segments from origin (denominator 1, x1=y1=0 ⇒ no-op). Kills: seg `(0,0)-(2,0)` pt `(0.5,0.5)` 0.5 vs 1.581 (29); non-origin oblique seg `(1,1)-(3,2)` pt `(2.5,2.5)` 0.6708 vs 0.707 (32/34). Killed by draft 5. |
| 26 | `dy = y2-y1` → `y2+y1` @ `_point_to_segment_distance` | 1 | ptsd_4 | TEST-GAP | No-op when `y1=0` (all existing segments). Killed by draft 5 (oblique seg at y-offset 1). |
| 27 | bbox None-guard `or`→`and` for (width,height) and (y,width) pairs @ `_get_normalized_position` | 2 | gnp_1, gnp_2 | TEST-GAP | Existing no-bbox test only sets `bbox_x=None` (an untouched guard clause); partial-bbox track would TypeError downstream instead of returning None. Killed by draft 6. |
| 28 | Position arithmetic: center `/2`→`/3`; clamp `min(1.0,·)`→`min(2.0,·)` x and y @ `_get_normalized_position` | 3 | gnp_11, gnp_26, gnp_38 | TEST-GAP | `/3` shifts 0.5→0.4913 — hidden by the test's `0.01` tolerance; clamp only matters off-frame (`bbox_x=1900,w=100` → 1.0156). Killed by draft 6 (exact assertions). |
| 29 | `self.db = db` → `self.db = None` @ `__init__` | 1 | init_1 | TEST-GAP | No test asserts the stored session; helpers that use `self.db` are all patched. Killed by draft 6. |

Key legend: `gva_N` = `…ApproachVectorServiceǁget_zone_approach_vectors__mutmut_N`, likewise `cav_` = `_calculate_approach_vector`, `dpb_` = `_distance_to_polygon_boundary`, `pip_` = `_point_in_polygon`, `ptsd_` = `_point_to_segment_distance`, `gnp_` = `_get_normalized_position`, `init_` = `__init__`. Full key prefix: `backend.services.approach_vector_service.xǁApproachVectorServiceǁ`.

## Covering test file(s)

- `backend/tests/unit/services/test_approach_vector_service.py` — the ONLY covering file for every surviving function (classes: `TestApproachVectorServiceHelpers`, `TestApproachVectorCalculation`, `TestGetNormalizedPosition`, `TestGetZoneApproachVectors`).
- What it misses: success path of `get_zone_approach_vectors` (non-empty vectors + helper call args), exact numeric vector values, output dict keys, 3+ detection trajectories, triangles/non-origin geometry, clamp/partial-bbox behavior, stored session.

## Drafted tests

Style follows the existing file (MagicMock detections, sync helper tests, `patch.object(..., autospec=True)` async tests). Fixture numbers were computed with a standalone replica of the exact functions in `/tmp/wp25/wp44-triage/geom_check{,2,3,4}.py` — not run against the repo.

**TDD procedure (one line):** add the test, run `uv run pytest backend/tests/unit/services/test_approach_vector_service.py -k <new_test> -q` — must be RED against each mutant copy (`mutants/backend/…`, via `uv run mutmut run --mutate backend/services/approach_vector_service.py` re-run later in the serial lane) and GREEN against `backend/services/approach_vector_service.py`.

### Draft 1 — exact approach-vector values (`test_calculate_approach_vector_exact_vector_values`)
**Kills clusters 10, 11, 12, 15 (ETA×speed), 16** (keys cav_31-35,41,42,44,50,53-57,65,86,95,96).

```python
    def test_calculate_approach_vector_exact_vector_values(self) -> None:
        """Assert exact direction/speed/distance/ETA and the returned key set.

        Mutation baseline: catches dx/dy sign flips and component swaps,
        atan2 sign, direction-wrap block mutations, distance-call argument
        swap, ETA multiplication, and output key renames.
        """
        now = datetime.now(UTC)
        polygon = [(0.4, 0.4), (0.6, 0.4), (0.6, 0.6), (0.4, 0.6)]

        # Approaching diagonally: bbox centers (150,200) -> (250,300).
        approaching = self.service._calculate_approach_vector(
            detections=[
                self._create_detection(100, 100, now - timedelta(seconds=2)),
                self._create_detection(200, 200, now),
            ],
            normalized_polygon=polygon,
            image_width=1920,
            image_height=1080,
        )

        assert approaching is not None
        assert set(approaching.keys()) == {
            "is_approaching",
            "direction_degrees",
            "speed_normalized",
            "distance_to_zone",
            "estimated_arrival_seconds",
        }
        assert approaching["is_approaching"] is True
        assert approaching["direction_degrees"] == pytest.approx(150.642246, abs=1e-4)
        assert approaching["speed_normalized"] == pytest.approx(0.05311794, abs=1e-6)
        assert approaching["distance_to_zone"] == pytest.approx(0.29618544, abs=1e-6)
        assert approaching["estimated_arrival_seconds"] == pytest.approx(5.57599646, abs=1e-4)

        # Moving away: reversed pair, raw direction is negative and must be
        # normalized to 330.64... (kills +=360 -> =360 / -=360 / +=361 variants).
        away = self.service._calculate_approach_vector(
            detections=[
                self._create_detection(200, 200, now - timedelta(seconds=2)),
                self._create_detection(100, 100, now),
            ],
            normalized_polygon=polygon,
            image_width=1920,
            image_height=1080,
        )
        assert away is not None
        assert away["is_approaching"] is False
        assert away["direction_degrees"] == pytest.approx(330.642246, abs=1e-4)
        assert away["speed_normalized"] == pytest.approx(0.05311794, abs=1e-6)
        assert away["distance_to_zone"] == pytest.approx(0.38697406, abs=1e-6)
        assert away["estimated_arrival_seconds"] is None

        # Straight up: raw direction is exactly 0.0 and must NOT wrap to 360
        # (kills the `< 0` -> `<= 0` / `< 1` wrap-guard mutants).
        up = self.service._calculate_approach_vector(
            detections=[
                self._create_detection(910, 440, now - timedelta(seconds=2)),
                self._create_detection(910, 200, now),
            ],
            normalized_polygon=polygon,
            image_width=1920,
            image_height=1080,
        )
        assert up is not None
        assert up["direction_degrees"] == pytest.approx(0.0, abs=1e-9)
```
// UNVERIFIED - not yet run red/green

### Draft 2 — 3-detection trajectory (`test_calculate_approach_vector_three_detection_trajectory`)
**Kills cluster 8** (cav_18, cav_25 — `detections[-1]`→`detections[+1]`).

```python
    def test_calculate_approach_vector_three_detection_trajectory(self) -> None:
        """Last position/time must come from detections[-1], not index 1."""
        now = datetime.now(UTC)
        polygon = [(0.4, 0.4), (0.6, 0.4), (0.6, 0.6), (0.4, 0.6)]

        vector = self.service._calculate_approach_vector(
            detections=[
                self._create_detection(100, 100, now - timedelta(seconds=4)),
                self._create_detection(150, 150, now - timedelta(seconds=2)),
                self._create_detection(200, 200, now),
            ],
            normalized_polygon=polygon,
            image_width=1920,
            image_height=1080,
        )

        # Same as the 2-point (100,100)->(200,200) case: full 4 s span, last
        # position at bbox center (250, 300). Index-1 mutants give the
        # (150,150) midpoint / 2 s span instead.
        assert vector is not None
        assert vector["speed_normalized"] == pytest.approx(0.05311794, abs=1e-6)
        assert vector["distance_to_zone"] == pytest.approx(0.29618544, abs=1e-6)
        assert vector["estimated_arrival_seconds"] == pytest.approx(5.57599646, abs=1e-4)
```
// UNVERIFIED - not yet run red/green

### Draft 3 — vector edge conditions (`test_calculate_approach_vector_edge_conditions`)
**Kills clusters 9, 13, 15 (elif constant)** (cav_20, cav_77, cav_88).

```python
    def test_calculate_approach_vector_edge_conditions(self) -> None:
        """Equidistant motion is not approaching; inside zone ETA is 0.0;
        a half-missing bbox (exactly one position None) returns None."""
        now = datetime.now(UTC)
        polygon = [(0.4, 0.4), (0.6, 0.4), (0.6, 0.6), (0.4, 0.6)]

        # Parallel to the zone edge: both points at y-center, symmetric in x.
        parallel = self.service._calculate_approach_vector(
            detections=[
                self._create_detection(142, 116, now - timedelta(seconds=2)),   # center (192, 216)
                self._create_detection(1678, 116, now),                          # center (1728, 216)
            ],
            normalized_polygon=polygon,
            image_width=1920,
            image_height=1080,
        )
        # Equal boundary distances: strict < keeps this NOT approaching.
        assert parallel is not None
        assert parallel["is_approaching"] is False
        assert parallel["estimated_arrival_seconds"] is None

        # Last position inside the zone -> distance 0, ETA 0.0 (not None).
        entered = self.service._calculate_approach_vector(
            detections=[
                self._create_detection(142, 116, now - timedelta(seconds=2)),
                self._create_detection(910, 440, now),                            # center (960, 540)
            ],
            normalized_polygon=polygon,
            image_width=1920,
            image_height=1080,
        )
        assert entered is not None
        assert entered["distance_to_zone"] == 0.0
        assert entered["estimated_arrival_seconds"] == 0.0

        # Exactly one position None (last detection missing bbox) -> None.
        broken_last = self._create_detection(150, 150, now)
        broken_last.bbox_width = None
        partial = self.service._calculate_approach_vector(
            detections=[self._create_detection(100, 100, now - timedelta(seconds=2)), broken_last],
            normalized_polygon=polygon,
            image_width=1920,
            image_height=1080,
        )
        assert partial is None
```
// UNVERIFIED - not yet run red/green

### Draft 4 — point-in-polygon triangle geometry (`test_point_in_polygon_triangle_and_boundary_semantics`)
**Kills clusters 18, 19, 21, 22, 23** (pip_1,2,8,13,14,15,25,30,35-37,38,40-45). Square-only tests hide every ray-cast mutation because the square's crossings all take the `p1x == p2x` short-circuit.

```python
    def test_point_in_polygon_triangle_and_boundary_semantics(self) -> None:
        """Ray casting on a triangle with a non-vertical right edge.

        The existing square-only tests never evaluate the xinters
        interpolation (the square's crossing edge is vertical and
        short-circuits the flip guard), so every xinters / loop-range /
        guard mutant survives. This triangle exercises them, including the
        vertex row (y == 0.5) and the exact x == xinters boundary.
        """
        triangle = [(0.2, 0.2), (0.2, 0.8), (0.8, 0.5)]

        # Interior (kills dropped/truncated edge-iteration and xinters sign
        # mutants; would raise UnboundLocalError/TypeError on the
        # `p1y != p2y` inversion and `xinters = None` mutants).
        assert self.service._point_in_polygon(0.3, 0.5, triangle) is True
        assert self.service._point_in_polygon(0.5, 0.5, triangle) is True
        assert self.service._point_in_polygon(0.5, 0.6, triangle) is True
        assert self.service._point_in_polygon(0.75, 0.5, triangle) is True

        # Exterior.
        assert self.service._point_in_polygon(0.1, 0.5, triangle) is False   # vertex row
        assert self.service._point_in_polygon(0.5, 0.25, triangle) is False
        assert self.service._point_in_polygon(0.5, 0.3, triangle) is False   # right of edge
        assert self.service._point_in_polygon(2.0, 0.5, triangle) is False

        # Deterministic ray-cast boundary conventions (documented, asserted).
        assert self.service._point_in_polygon(0.2, 0.5, triangle) is False   # on vertical edge
        assert self.service._point_in_polygon(0.4, 0.3, triangle) is True    # x == xinters

        # 3-vertex polygons must be accepted (guard is `< 3`, not `<= 3`).
        assert self.service._point_in_polygon(0.5, 0.5, [(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)]) is True
```
// UNVERIFIED - not yet run red/green

### Draft 5 — segment distances off the origin (`test_point_to_segment_distance_non_origin_geometry`)
**Kills clusters 24, 25, 26** (ptsd_4,13,14,16,17,29,32,34). Existing fixtures sit at origin / unit-horizontal segments where every sign/exponent/operator mutation is a numerical no-op.

```python
    def test_point_to_segment_distance_non_origin_geometry(self) -> None:
        """Distances for an oblique, non-origin segment and a non-origin
        degenerate segment (the existing tests put the segment at the
        origin where x1/y1 == 0 makes + / - and 2 ** / 3 ** indistinguishable).
        """
        # Oblique unit-ish segment (1,1)-(3,2); perpendicular foot lands
        # mid-segment at t = 0.8. Mutants 4/32/34 give 0.7071 here.
        dist = self.service._point_to_segment_distance(2.5, 2.5, 1.0, 1.0, 3.0, 2.0)
        assert dist == pytest.approx(0.67082039, abs=1e-6)

        # Long segment (0,0)-(2,0); perpendicular projection must scale by
        # the true squared length (kills the `/ -> *` on the t denominator).
        dist2 = self.service._point_to_segment_distance(0.5, 0.5, 0.0, 0.0, 2.0, 0.0)
        assert dist2 == pytest.approx(0.5, abs=1e-9)

        # Degenerate segment at (2,3), point (5,7): exact 3-4-5 distance.
        deg = self.service._point_to_segment_distance(5.0, 7.0, 2.0, 3.0, 2.0, 3.0)
        assert deg == pytest.approx(5.0, abs=1e-9)
```
// UNVERIFIED - not yet run red/green
// NOTE: add `import math` to the test file header (also used if the
// degenerate assertion is rewritten with math.sqrt).

### Draft 6 — success path + plumbing (`test_get_zone_approach_vectors_success_path`)
**Kills clusters 3, 4, 5, 6, 7, 27, 28, 29** (gva_1,2,5,7,8,9,11,12,13,14,16,17,18,19,20,22,23,27,32,33,34,35; gnp_1,2,11,26,38; init_1). Adds the missing end-to-end happy path with call-argument assertions.

```python
    @pytest.mark.asyncio
    async def test_get_zone_approach_vectors_success_path(self) -> None:
        """End-to-end: valid zone, dwellers excluded, 2-detection track yields
        a fully-populated vector; a 1-detection track is skipped, not fatal.

        Mutation baseline: catches None-clobbers of every query/derived
        value and helper argument, polygon guard + normalization mutants,
        the sort/min-count/break loop mutants, and (via the helper asserts
        below) the _get_normalized_position guard, divisor and clamp
        mutants plus the __init__ session clobber.
        """
        mock_db = AsyncMock()
        service = ApproachVectorService(mock_db)
        assert service.db is mock_db  # constructor stores the session

        mock_zone = MagicMock()
        # Corner triangle zone (pixel coords, 1920x1080 frame) - also exercises
        # the 3-vertex polygon acceptance boundary.
        mock_zone.polygon = [[1500, 600], [1900, 600], [1700, 1000]]
        mock_zone.camera_id = "cam-1"

        now = datetime.now(UTC)
        dwellers = {42}

        def make_det(track_id: int, x: int, y: int, when: datetime) -> MagicMock:
            det = MagicMock()
            det.track_id = track_id
            det.bbox_x = x
            det.bbox_y = y
            det.bbox_width = 100
            det.bbox_height = 100
            det.detected_at = when
            det.object_type = "person"
            return det

        recent = [
            make_det(7, 100, 100, now - timedelta(seconds=2)),
            make_det(7, 150, 150, now),                      # track 7: 2 detections
            make_det(9, 800, 800, now - timedelta(seconds=1)),  # track 9: 1 detection (skipped)
        ]

        with (
            patch.object(service, "_get_zone", return_value=mock_zone, autospec=True),
            patch.object(
                service, "_get_active_dweller_track_ids", return_value=dwellers, autospec=True
            ) as mock_dwellers,
            patch.object(
                service, "_get_recent_detections", return_value=recent, autospec=True
            ) as mock_recent,
        ):
            vectors = await service.get_zone_approach_vectors(zone_id=1)

        # Helpers queried with the right arguments.
        service._get_zone.assert_awaited_once_with(1)
        mock_dwellers.assert_awaited_once_with(1)
        mock_recent.assert_awaited_once_with(camera_id="cam-1", exclude_track_ids=dwellers)

        # Exactly one vector (track 9 skipped for < 2 detections; loop must
        # continue, not break).
        assert len(vectors) == 1
        v = vectors[0]
        assert v["track_id"] == 7
        assert v["object_class"] == "person"
        assert set(v.keys()) == {
            "track_id", "object_class", "is_approaching", "direction_degrees",
            "speed_normalized", "distance_to_zone", "estimated_arrival_seconds",
            "current_position", "zone_centroid",
        }
        # Track 7 centers (150,150) -> (200,200) px move toward the corner
        # zone: boundary distance 0.8173 -> 0.7718 (verified on replica).
        assert v["is_approaching"] is True
        assert v["speed_normalized"] == pytest.approx(
            math.hypot(50 / 1920, 50 / 1080) / 2.0, abs=1e-9
        )
        assert v["distance_to_zone"] == pytest.approx(0.77176165, abs=1e-6)
        # Corner-triangle centroid: means of normalized vertices.
        assert v["zone_centroid"]["x"] == pytest.approx(0.88541667, abs=1e-6)
        assert v["zone_centroid"]["y"] == pytest.approx(0.67901235, abs=1e-6)
        # current position = last detection center (200,200)/1920x1080.
        assert v["current_position"]["x"] == pytest.approx(200 / 1920, abs=1e-9)
        assert v["current_position"]["y"] == pytest.approx(200 / 1080, abs=1e-9)
        eta = v["estimated_arrival_seconds"]
        assert eta is not None
        assert eta == pytest.approx(v["distance_to_zone"] / v["speed_normalized"], abs=1e-6)

    def test_get_normalized_position_guard_and_clamp(self) -> None:
        """Partial bbox -> None; exact center; off-frame clamps to 1.0."""
        det = MagicMock()
        det.bbox_x = 910
        det.bbox_y = 490
        det.bbox_width = 100
        det.bbox_height = 100
        pos = self.service._get_normalized_position(det, 1920, 1080)
        assert pos == pytest.approx((0.5, 0.5), abs=1e-9)  # /2 divisor, not /3

        # Missing width (with height present) must still return None.
        det.bbox_width = None
        assert self.service._get_normalized_position(det, 1920, 1080) is None

        # Missing y only must return None.
        det2 = MagicMock()
        det2.bbox_x = 0
        det2.bbox_y = None
        det2.bbox_width = 100
        det2.bbox_height = 100
        assert self.service._get_normalized_position(det2, 1920, 1080) is None

        # Off-frame centers clamp to exactly 1.0 (not 1.0156...).
        det3 = MagicMock()
        det3.bbox_x = 1900
        det3.bbox_y = 1040
        det3.bbox_width = 100
        det3.bbox_height = 100
        pos3 = self.service._get_normalized_position(det3, 1920, 1080)
        assert pos3 == pytest.approx((1.0, 1.0), abs=1e-9)
```
// UNVERIFIED - not yet run red/green
// NOTE: the async test lives in `TestGetZoneApproachVectors` (which lacks
// setup_method; construct `service` inline as shown).
// `test_get_normalized_position_guard_and_clamp` lives in
// `TestGetNormalizedPosition`. All geometry expectations (approach,
// distance 0.77176165, centroid 0.88541667/0.67901235) were verified on the
// standalone replica; numeric constants carry 1e-6 tolerance against float
// noise in the replica rounding.

## Notes

- The 17 EQUIVALENT (clusters 1, 14, 17, 20) need no tests; recommend marking in the baseline (log-payload text, `float("INF")`, undirected edge re-walk, unreachable ETA guard relaxations, no-op leading degenerate ray-cast iteration).
- The 2 LOW-VALUE (cluster 2) would only crash debug-log evaluation; not worth asserting log internals.
- Drafted tests collectively target all 76 TEST-GAP survivors. Highest value: **Draft 6** (31 survivors incl. the entire orchestration layer), **Draft 4** (18, the ray-cast core), **Draft 1** (21, all vector arithmetic).
- Cross-cutting weakness for the ledger: `test_approach_vector_service.py` asserts empties/inequalities where it could assert exact values on cheap synthetic geometry — the same anti-pattern that produced this module's 95-survivor tail.
