# WP4.4 Triage Dossier — backend/services/zone_service.py

- **Checked keys:** 514 | **Killed:** 455 | **Survivors:** 59 (all exit_code 0 from `mutants/backend/services/zone_service.py.meta`; diffs via `uv run mutmut show <key>`, all 59 captured in `/tmp/wp25/wp44-triage/scratch/zone_diffs.txt`, spot-verified against the clobbered copies in `mutants/backend/services/zone_service.py`).
- **Covering test file (all survivors):** `backend/tests/unit/services/test_zone_service.py` (per `mutmut-stats.json` `tests_by_mangled_function_name`; `test_approach_vector_service.py` / `test_dwell_time_service.py` / `test_line_zone_service.py` do NOT import this module).
- Classification split: **TEST-GAP 40 / EQUIVALENT 17 / LOW-VALUE 2**.
- Equivalence and kill inputs were verified by a pure-math re-implementation (no repo execution): `/tmp/wp25/wp44-triage/scratch/sim_zone.py` (ran standalone; never imported backend code).

## Key structural facts that explain the survivals

1. **Boundary semantics deliberately unpinned.** `test_point_on_boundary_horizontal_edge` / `_vertical_edge` / `_vertex` (test_zone_service.py:216-235) and `test_float_precision_boundary` (:1176) assert only `isinstance(result, bool)` — every `<=`→`<` relaxation on the ray-cast gate/intersection survives this.
2. **`_point_to_segment_distance` suite uses ONLY axis-aligned segments through the origin** (`(0,0)-(1,0)` at :949-972 and boundary tests on the axis-aligned rectangle). Algebra check: with `x1=y1=0, y2=0`, the projection term `(py - y1)*dy == py*y2 == py*(y2 + y1)`, `dx*dx + dy*dy == 1` so `num/1 == num*1`, and `closest_y = y1 + t*dy == y1 - t*dy == 0`. All 7 arithmetic mutants are provably equivalent *on the suite's inputs only*.
3. **Symmetric test zone.** `rectangle_zone` is `[0.1,0.4]²` — symmetric in x/y, so `point_in_zone(center[0],center[1])`→`(center[1],center[1])` swaps (dwell :437, crossing :517-518, exit :556-557, approach :642) are undetectable with rectangle points; killable with `triangle_zone` where `(0.7,0.2)` is inside but `(0.2,0.7)` is outside.
4. **Degenerate guards only tested at 0 coordinates.** `test_empty_coordinates*` (:242, :989, :1015) cover the `[]` branch; the `len < 3` branch (2-vertex zones, `or`→`and` mutants) is never fed 2 vertices.
5. **Self-intersecting/collinear polygons declared "may vary"** (:277-308, :1123) — mutants that only change those answers can't be killed without pinning unspecified behavior (LOW-VALUE).
6. **Adjacent-guard redundancy** makes several `None`→`""` and `or`→`and` chains in `calculate_approach_vector` truly equivalent (first_detection/first_center/last_detection/last_center are set in lock-step in the loop at :601-608).

## Per-cluster table

n=59 total. "Line" = zone_service.py line. Keys abbreviated as `__NN` within the function.

| # | Function : line | Pattern (mutation) | Keys (≤3 shown) | n | Class | Evidence |
|---|---|---|---|---|---|---|
| 1 | point_in_zone :72-73 | Loop start `coordinates[0]`→`[1]`; `range(1,n+1)`→`range(1,n+2)` — differ only on self-intersecting/collinear polygons | x_point_in_zone__mutmut_13, __20 | 2 | LOW-VALUE | sim: differ ONLY at (FIG8,0.5,0.5) and (COLL,0.5,0.5); suite asserts `isinstance(bool)` there (:277-308,:1123) — pinning degenerate-polygon raycast output is unspecified behavior |
| 2 | point_in_zone :73 | Extra iteration `range(n+1)` adds a zero-length edge v0→v0 | x_point_in_zone__mutmut_16 | 1 | EQUIVALENT | `y > min(p1y,p1y)` is False for a degenerate edge → can never flip; sim: 0 diffs over 38 probes |
| 3 | point_in_zone :76,79 | Edge-membership relaxations: gate `x <= max(p1x,p2x)`→`x <`; `x <= xinters`→`x <`; xinters `/ (p2y-p1y)`→`* (p2y-p1y)` | x_point_in_zone__mutmut_35, __43, __50 | 3 | TEST-GAP | suite's boundary tests assert only `isinstance(bool)` (:216-235). Sim: orig (RECT,0.1,0.25)=False vs __35 True; (RECT,0.4,0.25)=True vs __35 False; (TRI,0.8,0.3)=True (exact slanted-edge midpoint) vs __50 False; (TRI,0.87,0.2)=False vs __43 True |
| 4 | point_in_zone :65 | Guard `not coordinates or len<3` → `and` | x_point_in_zone__mutmut_4 | 1 | EQUIVALENT | With 1-2 coords the loop walks the degenerate line back and forth; both passes make identical flip decisions → parity cancels → always False. Sim agrees |
| 5 | bbox_center :112 | Image-dimension guard off-by-one `<= 0` → `<= 1` (width / height) | x_bbox_center__mutmut_3, __5 | 2 | TEST-GAP | tests only exercise dims 0/negative (:357-370); width==1/height==1 accepted by original, rejected by mutant — contract says reject `<=0` |
| 6 | bbox_center :113,116,119 | ValueError message wrapped in `XX...XX` | x_bbox_center__mutmut_7, __16, __25 | 3 | EQUIVALENT | pure message text; tests use `pytest.raises(match=...)` substring search → substring still present; no semantic change |
| 7 | _get_detection_center :275-281 | None-guard `or`→`... or bbox_width is None and bbox_height is None` (precedence) | x__get_detection_center__mutmut_1, __2 | 2 | TEST-GAP | test_missing_bbox (:1032) uses only `bbox_x=None`, still caught. width-only/hheight-only None → mutant skips guard and `bbox_center` does `None/2` → TypeError instead of None |
| 8 | _get_zone_centroid :303 | Guard `or`→`and` | x__get_zone_centroid__mutmut_2 | 1 | TEST-GAP | 2-vertex zone: orig None, mutant returns 2-pt average tuple; suite only tests `[]` (:1015) |
| 9 | _distance_to_zone_boundary :341-342 | Vertex-count guard mutations: `or`→`and`; `len<3`→`len<=3` / `len<4` | x__distance_to_zone_boundary__mutmut_2, __4, __5 | 3 | TEST-GAP | `__4`/`__5` return inf for ALL triangles (3 vertices) — suite only measures boundary distance on the 4-vertex rect (:983) + empty (:989). Sim: `_distance_to_zone_boundary(0.7,0.7,TRI)=0.2` orig vs inf mutant. `__2`: 2-vertex zone inf→0.1414 |
| 10 | _distance_to_zone_boundary :342,348 | `float("inf")` → `float("INF")` | x__distance_to_zone_boundary__mutmut_8, __19 | 2 | EQUIVALENT | Python `float()` accepts "INF" case-insensitively — identical value (verified) |
| 11 | _distance_to_zone_boundary :354 | Edge endpoint `(i+1)%n` → `(i-1)%n` | x__distance_to_zone_boundary__mutmut_25 | 1 | EQUIVALENT | same edge set walked in reverse; segment distance is symmetric → identical min (sim: identical outputs) |
| 12 | _distance_to_zone_boundary :354 | Edge endpoint `(i+1)%n` → `(i+2)%n` (skips a vertex → chords) | x__distance_to_zone_boundary__mutmut_26 | 1 | TEST-GAP | kills differ only on concave polygons: concave notch point (0.35,0.8): orig 0.1 vs mutant 0.0354 (sim). Suite's only outside-probe is a convex rect |
| 13 | _point_to_segment_distance :378-389 | Projection-math mutants: `dy=y2+y1` (__4); `num*den` (__25); `num` sign flip (__26); `(px+x1)` (__28); `(py+y1)` (__30); `den=dx²-dy²` (__31, ZeroDivisionError on 45° segments); `closest_y=y1-t*dy` (__38) | x__point_to_segment_distance__mutmut_4, __25, __26, __28, __30, __31, __38 | 7 | TEST-GAP | See structural fact 2 — provably equivalent on the suite's `(0,0)-(1,0)` probes. Differ on off-origin/diagonal segments: sim: (0.5,0.5)→(1,1)-(3,3): 0.7071 vs 1.4142 (__28/__30) / ZeroDivision (__31); (4,4)→same seg: 1.4142 vs 1.3416/4.2426/5.099 (__4/__26/__38); (0,3)→(1,0)-(3,2): 2.8284 vs 3.1623 (__25/__26) |
| 14 | calculate_dwell_time :421 | Guard `not detections or not zone.enabled` → `and` | x_calculate_dwell_time__mutmut_1 | 1 | EQUIVALENT | empty list still caught by `len<2`; enabled=False + nonempty → loop calls point_in_zone which returns False for disabled zones → 0.0 either way |
| 15 | calculate_dwell_time :425 | `len(detections) < 2` → `<= 2` / `< 3` | x_calculate_dwell_time__mutmut_5, __6 | 2 | TEST-GAP | exactly-2-detection dwell lists never asserted: suite min is 1 or ≥3 (:463-503). [in@0s, in@5s] → orig 5.0 vs mutant 0.0 |
| 16 | calculate_dwell_time :435 | `continue`→`break` on invalid-center | x_calculate_dwell_time__mutmut_19 | 1 | TEST-GAP | invalid bbox mid-list: [in@0, bad@5, out@10, in@15] → orig 10.0 vs mutant 15.0 (break makes _calculate_remaining_dwell run to t=15). Existing bad-bbox test (:587) has bad first + no later exit — both yield 0.0 |
| 17 | calculate_dwell_time :437 | `point_in_zone(center[0],center[1])` → `(center[1],center[1])` | x_calculate_dwell_time__mutmut_27 | 1 | TEST-GAP | undetectable on symmetric rectangle (fact 3); kills on triangle: center (0.7,0.2) in / (0.2,0.7) out → 5.0 vs 0.0 |
| 18 | calculate_dwell_time :447 | `total_dwell += dwell_seconds` → `=` (overwrite) | x_calculate_dwell_time__mutmut_38 | 1 | TEST-GAP | multiple_entries (:541) has one full + one trailing partial → unaffected; two FULL periods [in@0,out@10,in@15,out@25] → orig 20.0 vs mutant 10.0 |
| 19 | detect_line_crossing :517-518 / detect_line_exit :556-557 | Same x/y center swap at prev/curr in_zone calls | x_detect_line_crossing__mutmut_28, __37; x_detect_line_exit__mutmut_27, __36 | 4 | TEST-GAP | all suite prev/curr centers are either both-in or both-out under swap (rect symmetric). Triangle probe prev=(0.2,0.7)out,curr=(0.7,0.2)in → crossing True orig / False mutant (kills __28,__37); reversed for exit (kills __27,__36) |
| 20 | detect_line_exit :557 | `curr_in_zone = point_in_zone(...)` → `= None` | x_detect_line_exit__mutmut_29 | 1 | TEST-GAP | behaves as "curr outside" → returns True whenever prev inside; inside→inside (no movement) must be False — never tested (suite has inside→out, outside→in, disabled only) |
| 21 | detect_line_exit :560 | `prev_in_zone and not curr_in_zone` → `or` | x_detect_line_exit__mutmut_38 | 1 | TEST-GAP | outside→outside must be False, mutant True — crossing has an outside→outside test (:647) but exit has none |
| 22 | detect_line_exit :553 | Guard `prev_center is None or curr_center is None` → `and` | x_detect_line_exit__mutmut_17 | 1 | TEST-GAP | one missing bbox → mutant runs `point_in_zone(None[0],...)` → TypeError. Crossing's twin mutant was killed by test_line_crossing_missing_bbox (:687); exit has no missing-bbox test |
| 23 | calculate_approach_vector :597-599 | Init sentinel `None` → `""` for first_center/last_detection/last_center | x_calculate_approach_vector__mutmut_9, __10, __11 | 3 | EQUIVALENT | detection/center vars are set in lock-step (:604-608); the remaining `is None` checks on the co-variables fire on all-bad input (test_missing_bbox path returns None identically) |
| 24 | calculate_approach_vector :610-615 | first/last None-guard `or`-chain partial `and` fusion | x_calculate_approach_vector__mutmut_25, __26, __27 | 3 | EQUIVALENT | same lock-step invariant (fc None ⟺ fd None, lc None ⟺ ld None) makes each fused conjunction a subset of a surviving disjunct |
| 25 | calculate_approach_vector :620 | `time_delta <= 0` → `<= 1` | x_calculate_approach_vector__mutmut_35 | 1 | TEST-GAP | 0 < dt ≤ 1s now returns None. Tests use dt=0 (:817) or dt≥2 (:774-846); sub-second detection spacing is realistic |
| 26 | calculate_approach_vector :631,642,653 | Result-value mutants: `speed = dist/time` → `*time`; `_distance_to_zone_boundary(last_center[1],last_center[1])` swap; `arrival = dist/speed` → `*speed` | x_calculate_approach_vector__mutmut_50, __71, __92 | 3 | TEST-GAP | approaching test (:774) asserts only `speed>0` / `arrival is not None`; inside-zone test (:848) asserts 0.0 values that survive the swap. Exact asserts kill all three (see T6) |
| 27 | calculate_approach_vector :637-638 | Direction wrap trigger/offset: `<0`→`<=0`/`<1`; `+=360` → `=360` / `-=360` / `+=361` | x_calculate_approach_vector__mutmut_59, __60, __61, __62, __63 | 5 | TEST-GAP | no test enters the wrap body or asserts 0: right-move (:827) gives +90 (no wrap); up-move (:1185) gives 0.0 and asserts `<10 or >350` (360 passes). Exact asserts: pure-up == 0.0 kills __59/__60; pure-left == 270.0 kills __61/__62/__63 |
| 28 | calculate_approach_vector :651 | ETA guard `speed > 0` → `>= 0`; `current_distance > 0` → `>= 0` | x_calculate_approach_vector__mutmut_87, __89 | 2 | EQUIVALENT | `is_approaching and speed==0` impossible (same center ⇒ same distance); `current_distance==0` branch already yields 0.0 via the elif — mutant also yields 0/speed = 0.0 |

**Totals:** TEST-GAP = 3+2+2+1+3+1+7+2+1+1+1+4+1+1+1+1+3+5 = **40**; EQUIVALENT = 1+1+3+2+1+1+3+3+2 = **17**; LOW-VALUE = **2**. Sum = 59.

## Kill geometry (verified numbers)

Normalized centers at 1920×1080 for `make_detection(x, y, 50, 50)`: `((x+25)/1920, (y+25)/1080)`.

- `bbox(1319, 191)` → (0.7, 0.2) INSIDE `triangle_zone`; `bbox(359, 731)` → (0.2, 0.7) OUTSIDE; `bbox(1511, 947)` → (0.8, 0.9) OUTSIDE.
- Rect zone `[0.1,0.4]²`: (0.4,0.25)→True (right edge inclusive), (0.1,0.25)→False (left exclusive). Triangle slanted-edge midpoint (0.8,0.3)→True; (0.87,0.2)→False.
- Segment exact: d((0.5,0.5),(1,1)-(3,3))=√0.5≈0.7071067811865476; d((4,4),(1,1)-(3,3))=√2; d((0,3),(1,0)-(3,2))=√8.
- Boundary exact: TRI(0.7,0.7)=0.2; concave notch (0.35,0.8)=0.1 (__26 mutant 0.03536); RECT(0.6,0.25)=0.2.
- Approaching pair (dets at bbox (1500,800,100,100)@t0 and (1000,500,100,100)@t0+5s, rect zone): speed=0.07615177847035176 (mul-mutant 1.90379), distance_to_zone=0.18305696206067124 (swap-mutant 0.15452), arrival=2.4038435574021553 (mul-mutant 0.01394). Pure-up pair → direction 0.0; pure-left pair → 270.0.

## Drafted tests (UNVERIFIED - not yet run red/green)

Append to `backend/tests/unit/services/test_zone_service.py`. Style follows the existing file (fixtures, `make_detection`, `pytest.approx`). TDD procedure (same for every test): add test → run the specific mutant copy / apply the diff → assert must FAIL on the mutant (wrong value, `None`, or raised TypeError/ZeroDivisionError) → revert diff → must PASS on original code.

```python
# =============================================================================
# WP4.4 mutant-kill tests // UNVERIFIED - not yet run red/green
# =============================================================================

# Normalized-center pixel probes (image 1920x1080, bbox 50x50 => center (x+25, y+25)):
# (1319, 191) -> (0.7, 0.2) INSIDE triangle_zone; (359, 731) -> (0.2, 0.7) OUTSIDE;
# (1511, 947) -> (0.8, 0.9) OUTSIDE. These are asymmetric under x/y swap, which the
# rectangle (symmetric 0.1-0.4 in both axes) can never be.
BBOX_TRI_INSIDE = dict(bbox_x=1319, bbox_y=191, bbox_width=50, bbox_height=50)
BBOX_TRI_OUTSIDE_LOW = dict(bbox_x=359, bbox_y=731, bbox_width=50, bbox_height=50)
BBOX_TRI_OUTSIDE_HIGH = dict(bbox_x=1511, bbox_y=947, bbox_width=50, bbox_height=50)


class TestPizEdgeMembershipWP44:
    """Pin edge membership so `<=`→`<` relaxations in the ray-cast cannot hide
    behind isinstance(bool) boundary tests. Kills point_in_zone __35/__43/__50."""

    def test_vertical_edges_are_asymmetric(self, rectangle_zone: Zone) -> None:
        # Current ray-cast semantics: right edge inclusive, left edge exclusive.
        # Mutant x<max(p1x,p2x) (__35) flips both.
        assert point_in_zone(0.4, 0.25, rectangle_zone) is True
        assert point_in_zone(0.1, 0.25, rectangle_zone) is False

    def test_slanted_edge_membership(self, triangle_zone: Zone) -> None:
        # (0.8, 0.3) is the exact midpoint of edge (0.9,0.1)-(0.7,0.5): inclusive.
        # Mutant x<xinters (__50) flips it.
        assert point_in_zone(0.8, 0.3, triangle_zone) is True
        # Just outside the same edge: mutant xinters *= (p2y-p1y) (__43) says True.
        assert point_in_zone(0.87, 0.2, triangle_zone) is False


class TestSegmentDistanceWP44:
    """The existing suite only uses the axis-aligned segment (0,0)-(1,0), on which
    every projection mutation is provably equal. Kills _point_to_segment_distance
    __4/__25/__26/__28/__30/__31/__38.

    // UNVERIFIED - not yet run red/green
    """

    def test_diagonal_segment_interior_and_beyond(self) -> None:
        # __28/__30 give sqrt(2) for the first; __31 raises ZeroDivisionError
        # (dx*dx - dy*dy == 0 on 45-degree segments).
        assert _point_to_segment_distance(0.5, 0.5, 1, 1, 3, 3) == pytest.approx(math.sqrt(0.5))
        # __4 gives 1.3416, __26 gives 4.2426, __38 gives 5.0990 here.
        assert _point_to_segment_distance(4, 4, 1, 1, 3, 3) == pytest.approx(math.sqrt(2))

    def test_oblique_segment_projection(self) -> None:
        # __25 (multiply instead of divide) clamps t to 1 and returns 3.1623.
        assert _point_to_segment_distance(0, 3, 1, 0, 3, 2) == pytest.approx(math.sqrt(8))


class TestZoneBoundaryGuardsWP44:
    """Kill the vertex-count guard mutants and the edge-skip mutant.
    // UNVERIFIED - not yet run red/green
    """

    def test_triangle_boundary_is_measured_not_rejected(self, triangle_zone: Zone) -> None:
        # __4 (len<=3) and __5 (len<4) return inf for any triangle.
        result = _distance_to_zone_boundary(0.7, 0.7, triangle_zone)
        assert result == pytest.approx(0.2, abs=1e-9)

    def test_concave_notch_uses_adjacent_edges(self, concave_zone: Zone) -> None:
        # __26 connects vertex i to i+2 (chords) and reports 0.0354 here.
        result = _distance_to_zone_boundary(0.35, 0.8, concave_zone)
        assert result == pytest.approx(0.1, abs=1e-9)

    def test_two_vertex_zone_is_rejected(self) -> None:
        # or->and guard mutants (__2) fall through to segment math: 0.1414, not inf.
        zone = MagicMock(spec=Zone)
        zone.enabled = True
        zone.coordinates = [[0.1, 0.1], [0.4, 0.4]]  # a line, not a polygon
        assert _distance_to_zone_boundary(0.5, 0.5, zone) == float("inf")
        # centroid twin of the same guard mutant: must be None, not a 2-pt average.
        assert _get_zone_centroid(zone) is None

    def test_bbox_center_accepts_one_pixel_image(self) -> None:
        # Guard must reject dims <= 0, not < 1; __3/__5 raise for dim == 1.
        assert bbox_center(0, 0, 2, 2, 1, 10) == (1.0, 0.1)
        assert bbox_center(0, 0, 10, 2, 100, 1) == (0.05, 1.0)

    def test_get_detection_center_rejects_missing_width_or_height(self) -> None:
        # or->and precedence mutants (__1/__2) skip the guard and raise TypeError
        # inside bbox_center (None/2) instead of returning None.
        for missing in ({"bbox_width": None}, {"bbox_height": None}):
            kwargs: dict = dict(bbox_x=100, bbox_y=100, bbox_width=50, bbox_height=50)
            kwargs.update(missing)
            detection = make_detection(**kwargs)  # type: ignore[arg-type]
            assert _get_detection_center(detection, 1000, 1000) is None


class TestDwellTimeWP44:
    """Kill threshold, control-flow, accumulation and swap mutants.
    // UNVERIFIED - not yet run red/green
    """

    def test_dwell_time_with_exactly_two_detections(self, rectangle_zone: Zone) -> None:
        # __5 (len<=2) and __6 (len<3) return 0.0 for a 2-detection in-zone pair.
        now = datetime.now(UTC)
        detections = [
            make_detection(bbox_x=300, bbox_y=150, bbox_width=100, bbox_height=100, detected_at=now),
            make_detection(
                bbox_x=310, bbox_y=160, bbox_width=100, bbox_height=100,
                detected_at=now + timedelta(seconds=5),
            ),
        ]
        assert calculate_dwell_time(detections, rectangle_zone, 1920, 1080) == 5.0

    def test_dwell_time_accumulates_multiple_full_periods(self, rectangle_zone: Zone) -> None:
        # __38 replaces `+=` with `=`: second full period overwrites the first -> 10.0.
        now = datetime.now(UTC)
        inside = dict(bbox_x=300, bbox_y=150, bbox_width=100, bbox_height=100)
        outside = dict(bbox_x=1500, bbox_y=800, bbox_width=100, bbox_height=100)
        detections = [
            make_detection(**inside, detected_at=now),
            make_detection(**outside, detected_at=now + timedelta(seconds=10)),
            make_detection(**inside, detected_at=now + timedelta(seconds=15)),
            make_detection(**outside, detected_at=now + timedelta(seconds=25)),
        ]
        assert calculate_dwell_time(detections, rectangle_zone, 1920, 1080) == 20.0

    def test_dwell_time_on_triangle_is_not_coordinate_swapped(self, triangle_zone: Zone) -> None:
        # __27 checks point_in_zone(center[1], center[1]): (0.7,0.2) in, (0.2,0.7)
        # out -> 0.0. The rectangle fixture can never distinguish these.
        now = datetime.now(UTC)
        detections = [
            make_detection(**BBOX_TRI_INSIDE, detected_at=now),
            make_detection(**BBOX_TRI_INSIDE, detected_at=now + timedelta(seconds=5)),
        ]
        assert calculate_dwell_time(detections, triangle_zone, 1920, 1080) == 5.0

    def test_invalid_bbox_is_skipped_not_a_stop_sign(self, rectangle_zone: Zone) -> None:
        # __19 breaks instead of continuing: dwell runs from t=0 to the final
        # detected_at (t=15) instead of the real in->out span (10s).
        now = datetime.now(UTC)
        detections = [
            make_detection(bbox_x=300, bbox_y=150, bbox_width=100, bbox_height=100, detected_at=now),
            make_detection(bbox_x=None, bbox_y=None, bbox_width=None, bbox_height=None,
                           detected_at=now + timedelta(seconds=5)),
            make_detection(bbox_x=1500, bbox_y=800, bbox_width=100, bbox_height=100,
                           detected_at=now + timedelta(seconds=10)),
            make_detection(bbox_x=300, bbox_y=150, bbox_width=100, bbox_height=100,
                           detected_at=now + timedelta(seconds=15)),
        ]
        assert calculate_dwell_time(detections, rectangle_zone, 1920, 1080) == 10.0


class TestLineCrossingExitWP44:
    """Triangle probes kill the x/y swaps (__28/__37/__27/__36); degenerate
    prev/curr state pairs kill __29 (curr=None), __38 (and->or) and __17 (guard
    or->and, raises TypeError). // UNVERIFIED - not yet run red/green
    """

    def test_crossing_uses_x_and_y_in_order(self, triangle_zone: Zone) -> None:
        now = datetime.now(UTC)
        prev = make_detection(**BBOX_TRI_OUTSIDE_LOW, detected_at=now)  # (0.2,0.7) out
        curr = make_detection(**BBOX_TRI_INSIDE, detected_at=now + timedelta(seconds=1))  # (0.7,0.2) in
        assert detect_line_crossing(prev, curr, triangle_zone, 1920, 1080) is True

    def test_exit_uses_x_and_y_in_order(self, triangle_zone: Zone) -> None:
        now = datetime.now(UTC)
        prev = make_detection(**BBOX_TRI_INSIDE, detected_at=now)  # in
        curr = make_detection(**BBOX_TRI_OUTSIDE_LOW, detected_at=now + timedelta(seconds=1))  # out
        assert detect_line_exit(prev, curr, triangle_zone, 1920, 1080) is True

    def test_exit_inside_to_inside_is_not_an_exit(self, triangle_zone: Zone) -> None:
        # __29 (curr_in_zone = None) reports every still-inside pair as an exit.
        now = datetime.now(UTC)
        prev = make_detection(**BBOX_TRI_INSIDE, detected_at=now)
        curr = make_detection(**BBOX_TRI_INSIDE, detected_at=now + timedelta(seconds=1))
        assert detect_line_exit(prev, curr, triangle_zone, 1920, 1080) is False

    def test_exit_outside_to_outside_is_not_an_exit(self, triangle_zone: Zone) -> None:
        # __38 (`prev or not curr`) returns True for any outside pair.
        now = datetime.now(UTC)
        prev = make_detection(**BBOX_TRI_OUTSIDE_LOW, detected_at=now)
        curr = make_detection(**BBOX_TRI_OUTSIDE_HIGH, detected_at=now + timedelta(seconds=1))
        assert detect_line_exit(prev, curr, triangle_zone, 1920, 1080) is False

    def test_exit_missing_bbox_returns_false(self, triangle_zone: Zone) -> None:
        # __17 (guard `or`->`and`) skips the early return and crashes on
        # point_in_zone(None[0], ...).
        now = datetime.now(UTC)
        prev = make_detection(bbox_x=None, bbox_y=None, detected_at=now)
        curr = make_detection(**BBOX_TRI_INSIDE, detected_at=now + timedelta(seconds=1))
        assert detect_line_exit(prev, curr, triangle_zone, 1920, 1080) is False


class TestApproachVectorValuesWP44:
    """Existing tests assert inequalities (`speed > 0`, `arrival is not None`,
    `dir < 10 or > 350`); exact-value and exact-quadrant asserts kill the value,
    swap, wrap and sub-second mutants. // UNVERIFIED - not yet run red/green
    """

    def test_exact_speed_distance_and_arrival(self, rectangle_zone: Zone) -> None:
        # Same geometry as test_approach_vector_approaching.
        # __50 speed *= time_delta (1.90379), __71 distance uses (y,y) (0.15452),
        # __92 arrival *= speed (0.01394).
        now = datetime.now(UTC)
        detections = [
            make_detection(bbox_x=1500, bbox_y=800, bbox_width=100, bbox_height=100, detected_at=now),
            make_detection(bbox_x=1000, bbox_y=500, bbox_width=100, bbox_height=100,
                           detected_at=now + timedelta(seconds=5)),
        ]
        result = calculate_approach_vector(detections, rectangle_zone, 1920, 1080)
        assert result is not None
        assert result.speed_normalized == pytest.approx(0.07615177847035176, rel=1e-9)
        assert result.distance_to_zone == pytest.approx(0.18305696206067124, rel=1e-9)
        assert result.estimated_arrival_seconds == pytest.approx(2.4038435574021553, rel=1e-9)

    def test_sub_second_time_delta_still_produces_vector(self, rectangle_zone: Zone) -> None:
        # __35 rejects any time_delta <= 1 -> returns None for a 0.5s track.
        now = datetime.now(UTC)
        detections = [
            make_detection(bbox_x=1500, bbox_y=800, detected_at=now),
            make_detection(bbox_x=1000, bbox_y=500, detected_at=now + timedelta(microseconds=500_000)),
        ]
        assert calculate_approach_vector(detections, rectangle_zone, 1920, 1080) is not None

    def test_direction_pure_up_is_exactly_zero(self, rectangle_zone: Zone) -> None:
        # The wrap test accepts `<10 or >350`, so __59/__60 (0 -> 360) slip past.
        now = datetime.now(UTC)
        detections = [
            make_detection(bbox_x=500, bbox_y=600, bbox_width=100, bbox_height=100, detected_at=now),
            make_detection(bbox_x=500, bbox_y=400, bbox_width=100, bbox_height=100,
                           detected_at=now + timedelta(seconds=2)),
        ]
        result = calculate_approach_vector(detections, rectangle_zone, 1920, 1080)
        assert result is not None
        assert result.direction_degrees == pytest.approx(0.0, abs=1e-9)

    def test_direction_pure_left_is_exactly_270(self, rectangle_zone: Zone) -> None:
        # Exercises the wrap BODY (direction_deg = -90): __61 gives 360, __62
        # gives -450, __63 gives 271.
        now = datetime.now(UTC)
        detections = [
            make_detection(bbox_x=700, bbox_y=500, bbox_width=100, bbox_height=100, detected_at=now),
            make_detection(bbox_x=300, bbox_y=500, bbox_width=100, bbox_height=100,
                           detected_at=now + timedelta(seconds=2)),
        ]
        result = calculate_approach_vector(detections, rectangle_zone, 1920, 1080)
        assert result is not None
        assert result.direction_degrees == pytest.approx(270.0, abs=1e-9)
```

Not drafted on purpose: clusters 1 (LOW-VALUE — would pin degenerate/self-intersecting raycast output the suite declares unspecified), 23/24/28/10/11/14/6/4/2 (EQUIVALENT — no input distinguishes them).

## Covering test file line index (backend/tests/unit/services/test_zone_service.py)

- fixtures: rectangle_zone :53, triangle_zone :69, concave_zone :85, disabled_zone :108, empty_coordinates_zone :123, very_small_zone :138, make_detection :153
- TestPointInZone :181 (weak boundary tests :216-235); self-intersecting :277; TestBboxCenter :316 (raises :357-395); TestCalculateDwellTime :455 (weak bad-bbox test :587); TestDetectLineCrossing :612 (missing-bbox :687); TestDetectLineExit :701 (NO missing-bbox test, NO outside→outside test); TestCalculateApproachVector :750 (inequality-only asserts :774, wrap test :1185); TestDistance :923; TestPointToSegmentDistance :946 (all five probes are `(0,0)-(1,0)`-shaped); TestDistanceToZoneBoundary :975 (only rect + empty); TestGetZoneCentroid :995; TestGetDetectionCenter :1021; TestEdgeCases :1120.
