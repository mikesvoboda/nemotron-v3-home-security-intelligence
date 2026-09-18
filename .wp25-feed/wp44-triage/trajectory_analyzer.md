# WP4.4 triage dossier — `backend/services/trajectory_analyzer.py`

- **Survivors:** 113 of 452 mutants (exit_code 0 in `mutants/backend/services/trajectory_analyzer.py.meta`, read 2026-09-17 11:20). 339 killed, 0 unchecked.
- **Covering tests:** single file `backend/tests/unit/test_trajectory_analyzer.py` (502 lines) — per `mutants/mutmut-stats.json` `tests_by_mangled_function_name`, every function is covered only by this file.
- **Method:** per-mutant diffs taken from `mutants/...trajectory_analyzer.py.spans` (variant line ranges) + unified diff vs `__mutmut_orig`; cross-checked against `uv run mutmut show` (works, clean). Every drafted assertion below was hand-executed against **both** the unmutated module and each mutant (via a /tmp-only exec harness that re-runs the real module source with one string replaced — **no pytest, no repo writes**). `mutmut run` was never invoked.
- Note: the `except ValueError, TypeError:` on source line 190 is valid Python 3.14 (PEP 758, comma-separated bare except) — not a syntax error.

## Cluster table (counts sum to 113)

| #   | Cluster                                                                                                                                                                                                                                                                                                                                    | n   | Class      | Example keys (`backend.services.trajectory_analyzer.` prefix omitted)                                                     |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --- | ---------- | ------------------------------------------------------------------------------------------------------------------------- |
| C1  | `_check_approach_depart`: approach/depart consistency math — counter seeds `=0→1`, `+=1→+=2`, denominator `len-1 → +1/-2`, window start `range(1,n)`, adjacent-vs-2-back comparisons, `<`/`>` vs `<=`/`>=` (equal-step miscount), ratio `/` vs `*`, `>=`→`>` threshold, `len<3` guard, `cx` denorm uses `p[1]`/height, min-dist `**2`→`*2` | 21  | TEST-GAP   | `x__check_approach_depart__mutmut_42`, `__67`, `__16`                                                                     |
| C2  | `_is_approaching_entry_point`: recent-window size `min(5)→min(6)`, first/last point index swaps (`[0]↔[1]`, `[-1]↔[-2]/[+1]`), `last<first → <=` (equal-distance flip), len guards, `cx` denorm swap, min-dist `**2→*2`                                                                                                                  | 15  | TEST-GAP   | `x__is_approaching_entry_point__mutmut_69`, `__40`, `__76`                                                                |
| C3  | `TrajectoryAnalyzer.analyze_trajectory`: duration/speed guard math — `max(duration, 0)→1`, `round(x,2)` places `None/0/3`, `duration>0` flips (`>=0`, `>1`, `or True`), `else 0.0→1.0`, `len<2` branch, args passed to `_classify_movement` (`zones/width/height→None`), zone-guard `and→or`, `track_id=None`, summary→None                | 16  | TEST-GAP   | `analyze_trajectory__mutmut_27`, `__40`, `__48`                                                                           |
| C4  | `_build_summary`: exact prompt-string contract — dwell `>0` boundary, `3600` s/min split (`<=3600`, `<3601`, `or True`, `/60→*60`, `/60→/61`), zone join `', '→'XX, XX'`, warning literal case/wrap, sentence join `'. '` + trailing `.`, `pattern`/`speed_desc → None`                                                                    | 15  | TEST-GAP   | `x__build_summary__mutmut_10`, `__23`, `__27`                                                                             |
| C5  | `_classify_movement`: threshold edges & geometry — `MIN_MOVEMENT < → <=`, `>=10s → >10s`, circling `>`/`<=` flips, return-distance `**2 → *2/**3` (dx and dy), start/end point index swaps, zone-guard `and→or` (both variants)                                                                                                            | 13  | TEST-GAP   | `x__classify_movement__mutmut_6`, `__29`, `__37`                                                                          |
| C6  | `_detect_zone_transitions` output text: first-point skip `i>0 → i>=0` (crash), `name` fallback `Unknown` → `None`/`()`/case variants (sortedness + literal)                                                                                                                                                                                | 6   | TEST-GAP   | `x__detect_zone_transitions__mutmut_41`, `__32`, `__38`                                                                   |
| C7  | `_describe_speed` tier boundaries: all 4 thresholds `< v` vs `<= v` and `v` vs `v+1`                                                                                                                                                                                                                                                       | 8   | TEST-GAP   | `x__describe_speed__mutmut_1`, `__5`, `__9`                                                                               |
| C8  | `_point_in_polygon` ray-cast geometry: closing-edge init `j=n-1→n-2`, edge `px<` vs `px<=` (on-boundary containment), `/→*` in edge-intersection formula                                                                                                                                                                                   | 3   | TEST-GAP   | `x__point_in_polygon__mutmut_14`, `__16`, `__6`                                                                           |
| C9  | `_parse_timestamps`: bad-timestamp / missing-timestamp `continue→break` (truncates the trajectory)                                                                                                                                                                                                                                         | 2   | TEST-GAP   | `x__parse_timestamps__mutmut_7`, `__12`                                                                                   |
| C10 | guarded `zone.get("coordinates", [])` default → `None`/`()` (immediately `if not coords: continue` — all falsy)                                                                                                                                                                                                                            | 5   | EQUIVALENT | `x__check_approach_depart__mutmut_6`, `x__detect_zone_transitions__mutmut_18`, `x__is_approaching_entry_point__mutmut_16` |
| C11 | dead guard/init in `_detect_zone_transitions`: `not zones or not pts` → `and` (both empty-input paths still return `[]`); `prev_in_zones = set() → None` (the `set()` is only read at i>0, where it has been overwritten; `None` never observed — brute-forced 40k inputs, 0 diffs)                                                        | 2   | EQUIVALENT | `x__detect_zone_transitions__mutmut_1`, `__5`                                                                             |
| C12 | `_classify_movement` stationary off-by-ones: `total < 5 → <= 5` and `duration >= 10 → > 10` — outcome identical because the AND-guard fall-through (`total < MIN_MOVEMENT` + `duration >= 10 → stationary`) reproduces the same result at exactly 5.0 px / exactly 10.0 s (brute-forced 80k/100k inputs, 0 diffs)                          | 2   | EQUIVALENT | `x__classify_movement__mutmut_2`, `__3`                                                                                   |
| C13 | `_check_approach_depart` dead guard: `total_segments > 0` → `>= 0` / `> 1` — unreachable-false: `len(points)>=3` ⇒ `total_segments>=2` (brute-forced 40k inputs each, 0 diffs)                                                                                                                                                             | 2   | EQUIVALENT | `x__check_approach_depart__mutmut_65`, `__66`                                                                             |
| C14 | `_parse_timestamps` log message arg only (`logger.debug(f"...{ts}") → debug(None)`) — pure log text                                                                                                                                                                                                                                        | 1   | EQUIVALENT | `x__parse_timestamps__mutmut_11`                                                                                          |
| C15 | `_is_approaching_entry_point` guard `or → and` (`not entry_zones or len<2` → `and`): case analysis over all 4 (empty-entry-zones × len<2) combinations + 150k random inputs, output identical everywhere (the `len(recent_points) < 2` re-guard downstream absorbs every newly-allowed call)                                               | 1   | EQUIVALENT | `x__is_approaching_entry_point__mutmut_8`                                                                                 |

**TEST-GAP total 99 / EQUIVALENT total 14 / LOW-VALUE 0 = 113.**
(Drafted tests T1–T8 kill **all 99** TEST-GAP mutants; equivalence of the 14 is machine-checked, see notes.)

## Why these are gaps (covering-test weaknesses)

`backend/tests/unit/test_trajectory_analyzer.py` — the existing tests execute these lines but assert too weakly:

- `TestDescribeSpeed` (line 304): probes only interior values (2/15/50/100/200); no threshold value is ever passed → C7 survives.
- `TestClassifyMovement` (line 174): fixtures are far from boundaries (never total exactly 5.0 / 10.0 px, never return-distance exactly 20% of total) → C5 survives; `duration` is a free parameter so `>=` vs `>` at 10 s is untested.
- `_check_approach_depart` is **never called directly**; only via `test_approaching/departing_entry_point` (lines 196–222) whose 5-point strictly-monotone fixtures give 4/4 ratios — every counting, denominator, window-offset and `>=`-vs-`>` change keeps 4/4 → C1 survives (25 survivors, the module's worst hotspot).
- `TestIsApproachingEntryPoint` (line 277): one 4-point approaching + one 4-point departing case; insensitive to window size (5), first/last index choice, equal-distance case, asymmetric width/height denormalization → C2.
- `TestAnalyzeTrajectory` (line 326): never uses duration 0 or sub-second, never a 2-point trajectory end-to-end, never zones with exactly one video dimension, and asserts speed with inequalities (`< 1.0`, `> 5.0`) instead of the rounded value → C3.
- `TestBuildSummary` (line 467): substring asserts (`"30s" in`, `"approaching entry point" in summary.lower()`) tolerate case changes, join changes, and the entire s/min dwell branch → C4.
- `TestDetectZoneTransitions` (line 249): `in` membership only — never asserts exact list/order, never an unnamed zone (`"Unknown"` fallback), never multiple simultaneous zones (sortedness) → C6.
- `TestPointInPolygon` (line 154): only clean interior/exterior samples — never a point on an edge or a polygon relying on the closing edge → C8.
- `TestParseTimestamps` (line 101): single-point lists, so `continue` vs `break` after a bad timestamp is indistinguishable → C9.

## Drafted tests (append to `backend/tests/unit/test_trajectory_analyzer.py`)

Add to the existing import block (line 12–23): `_check_approach_depart` — it is currently not imported. All other names are already imported.

```python
# UNVERIFIED - not yet run red/green. TDD procedure: run each test against a
# mutant build (mutmut) -> the listed assertion must FAIL; against the original
# -> must PASS. Assertion logic was hand-verified offline against both original
# and every mutant variant via a /tmp exec harness (no pytest was run).

# ===========================================================================
# C1/_check_approach_depart: consistency-math core (kills 21 survivors)
# ===========================================================================


class TestCheckApproachDepart:
    """Exact approach/depart consistency semantics.

    The existing coverage only ever feeds strictly monotone 5-point paths
    (ratio 4/4), which is blind to every counting/offset/rounding mutant.
    """

    ENTRY_AT_ORIGIN = {  # zone center = (100, 100) px on a 1000x1000 frame
        "name": "Near Door",
        "zone_type": "entry_point",
        "coordinates": [[0.05, 0.05], [0.15, 0.05], [0.15, 0.15], [0.05, 0.15]],
    }
    TALL_NARROW = {  # center (1776, 216) on 1920x1080: cx and cy use different dims
        "name": "Side Gate",
        "zone_type": "entry_point",
        "coordinates": [[0.9, 0.1], [0.95, 0.1], [0.95, 0.3], [0.9, 0.3]],
    }

    @staticmethod
    def _radial(dists: list[float]) -> list[dict]:
        # points on y=100 -> distance to (100,100) equals dist exactly
        return _make_points([(100 + d, 100) for d in dists], interval_s=3)

    def test_three_points_is_enough(self):
        entry = _make_entry_zone()  # center (500, 500)
        points = _make_points([(100, 100), (300, 300), (450, 450)], interval_s=3)
        assert _check_approach_depart(points, [entry], 1000, 1000) == "approaching"

    def test_two_points_returns_none(self):
        points = _make_points([(100, 100), (100, 200)], interval_s=3)
        assert _check_approach_depart(points, [self.ENTRY_AT_ORIGIN], 1000, 1000) is None

    def test_exact_60_percent_decreasing_is_approaching(self):
        # 6 points -> 5 segments, 3 decreasing -> ratio exactly 0.6, boundary is INCLUSIVE
        points = self._radial([300, 180, 250, 150, 200, 100])
        assert _check_approach_depart(points, [self.ENTRY_AT_ORIGIN], 1000, 1000) == "approaching"

    def test_exact_60_percent_increasing_is_departing(self):
        points = self._radial([100, 200, 150, 250, 180, 300])
        assert _check_approach_depart(points, [self.ENTRY_AT_ORIGIN], 1000, 1000) == "departing"

    def test_no_majority_returns_none(self):
        # 2 dec / 2 inc / 1 eq -> 0.4 each; counters must start at 0 and count by 1
        points = self._radial([200, 300, 300, 100, 400, 250])
        assert _check_approach_depart(points, [self.ENTRY_AT_ORIGIN], 1000, 1000) is None

    def test_plateau_steps_do_not_count_as_trend(self):
        # 2 dec / 1 inc / 2 eq: counting equal steps as "decreasing" would flip this to approaching
        points = self._radial([300, 200, 200, 150, 150, 250])
        assert _check_approach_depart(points, [self.ENTRY_AT_ORIGIN], 1000, 1000) is None

    def test_alternating_steps_count_against_immediate_neighbour(self):
        # 3 dec / 5 with alternating radii: a 2-back comparison loses the decreasing counts
        points = self._radial([300, 200, 300, 100, 300, 0])
        assert _check_approach_depart(points, [self.ENTRY_AT_ORIGIN], 1000, 1000) == "approaching"
        points = self._radial([0, 300, 100, 300, 200, 300])
        assert _check_approach_depart(points, [self.ENTRY_AT_ORIGIN], 1000, 1000) == "departing"

    def test_pure_vertical_movement_classifies(self):
        # points directly below/above the zone center: kills mutants that drop
        # the (py-cy)**2 squaring (sqrt of a negative arg raises ValueError)
        points = _make_points([(100, 100), (100, 200), (100, 400)], interval_s=3)
        assert _check_approach_depart(points, [self.ENTRY_AT_ORIGIN], 1000, 1000) == "departing"
        points = _make_points([(100, 900), (100, 300), (100, 100)], interval_s=3)
        assert _check_approach_depart(points, [self.ENTRY_AT_ORIGIN], 1000, 1000) == "approaching"

    # (window mutants range(1..n)->range(len)/range(2..n) and the 2-back
    # comparison mutants are killed by test_no_majority_returns_none,
    # test_plateau_steps_do_not_count_as_trend, test_pure_vertical_movement_classifies
    # and the alternating-steps pair — all fixtures above were verified red on
    # each of those mutants.)

    def test_denominator_is_point_count_minus_one(self):
        # 8 points -> exactly 7 segments, 4 decreasing: 4/7 < 0.6 -> None
        points = self._radial([100, 80, 80, 60, 60, 40, 40, 20])
        assert _check_approach_depart(points, [self.ENTRY_AT_ORIGIN], 1000, 1000) is None

    def test_center_denormalized_with_width_for_x(self):
        # approaching in x toward true cx=1776; mutants using the y coord or video_height flip this
        points = _make_points([(1000, 216), (1400, 216), (1700, 216)], interval_s=3)
        assert _check_approach_depart(points, [self.TALL_NARROW], 1920, 1080) == "approaching"

    def test_mixed_magnitude_trajectory(self):
        # mixed dx/dy magnitudes (input found by exhaustive search): scaling the
        # dx term instead of squaring it flips approaching -> departing
        zone = {
            "name": "Z",
            "zone_type": "entry_point",
            "coordinates": [
                [0.3385416666666667, 0.1388888888888889],
                [0.5989583333333334, 0.1388888888888889],
                [0.5989583333333334, 0.4166666666666667],
                [0.3385416666666667, 0.4166666666666667],
            ],
        }
        points = _make_points([(30, 129), (121, 73), (389, 495), (1228, 61), (1593, 950), (668, 902)], interval_s=3)
        assert _check_approach_depart(points, [zone], 1920, 1080) == "approaching"

    def test_y_term_squared_not_scaled(self):
        # dx^2 dominates; mutants replacing (py-cy)**2 by (py-cy)*2 hit sqrt(negative) -> ValueError
        zone = {
            "name": "Z2",
            "zone_type": "entry_point",
            "coordinates": [
                [-0.026041666666666668, 0.5092592592592593],
                [0.234375, 0.5092592592592593],
                [0.234375, 0.7870370370370371],
                [-0.026041666666666668, 0.7870370370370371],
            ],
        }
        points = _make_points([(1751, 388), (378, 1048), (974, 381), (192, 914), (621, 290), (185, 85)], interval_s=3)
        assert _check_approach_depart(points, [zone], 1920, 1080) == "departing"


# ===========================================================================
# C7/_describe_speed: tier boundaries (kills all 8 survivors)
# ===========================================================================


class TestDescribeSpeedBoundaries:
    def test_tier_boundaries(self):
        assert _describe_speed(4.99) == "stationary"
        assert _describe_speed(5.0) == "slow (walking pace)"
        assert _describe_speed(29.99) == "slow (walking pace)"
        assert _describe_speed(30.0) == "moderate (brisk walk)"
        assert _describe_speed(79.99) == "moderate (brisk walk)"
        assert _describe_speed(80.0) == "fast (running)"
        assert _describe_speed(149.99) == "fast (running)"
        assert _describe_speed(150.0) == "very fast (vehicle speed)"


# ===========================================================================
# C2/_is_approaching_entry_point: recent-window semantics (kills 15 survivors)
# ===========================================================================


class TestIsApproachingWindowSemantics:
    def test_two_and_three_point_approaches(self):
        entry = _make_entry_zone()
        assert _is_approaching_entry_point(_make_points([(100, 100), (450, 450)], interval_s=3), [entry], 1000, 1000) is True
        assert _is_approaching_entry_point(_make_points([(100, 100), (300, 300), (450, 450)], interval_s=3), [entry], 1000, 1000) is True

    def test_equal_distances_is_not_approaching(self):
        # strict `last < first`: equal start/end distance must NOT flip to True
        entry = _make_entry_zone()
        points = _make_points([(0, 500), (300, 900), (1000, 500)], interval_s=3)
        assert _is_approaching_entry_point(points, [entry], 1000, 1000) is False

    def test_first_distance_uses_oldest_point_x(self):
        # oldest point (500,900) d=400; newest (0,500) d=500 -> 500<400 False.
        # reading first_dist's x from the *second* point (d=640) flips it to True.
        entry = _make_entry_zone()
        assert _is_approaching_entry_point(_make_points([(500, 900), (0, 500)], interval_s=3), [entry], 1000, 1000) is False

    def test_first_distance_uses_oldest_point_y(self):
        entry = _make_entry_zone()
        assert _is_approaching_entry_point(_make_points([(480, 500), (500, 20), (500, 450)], interval_s=3), [entry], 1000, 1000) is False

    def test_last_distance_uses_latest_point(self):
        entry = _make_entry_zone()
        # first (0,500) d=500, last (490,490) d=14 -> True; reading last from the
        # *first* point makes 500<500 False
        assert _is_approaching_entry_point(_make_points([(0, 500), (300, 0), (490, 490)], interval_s=3), [entry], 1000, 1000) is True
        # and the mirrored False case where reading [-2]/[+1] would flip to True
        assert _is_approaching_entry_point(_make_points([(0, 500), (480, 500), (0, 0)], interval_s=3), [entry], 1000, 1000) is False
        assert _is_approaching_entry_point(_make_points([(300, 500), (1000, 500), (0, 500)], interval_s=3), [entry], 1000, 1000) is False

    def test_recent_window_is_last_five(self):
        # window = track_points[-min(5, n):]; an early excursion farther than the
        # 6th point must not count (window-6 mutant flips this to True)
        entry = _make_entry_zone()
        points = _make_points([(0, 0), (450, 450), (480, 480), (490, 490), (480, 480), (420, 420)], interval_s=3)
        assert _is_approaching_entry_point(points, [entry], 1000, 1000) is False
        # early approach must not leak through the window when the last 5 depart
        points = _make_points([(900, 900), (850, 850), (300, 300), (600, 600), (700, 700), (800, 800), (950, 950)], interval_s=3)
        assert _is_approaching_entry_point(points, [entry], 1000, 1000) is False

    def test_mixed_dx_dy_distance_terms(self):
        # equal total distance but different dx vs dy parts: scaling (instead of
        # squaring) either term changes the comparison
        entry = _make_entry_zone()
        assert _is_approaching_entry_point(_make_points([(1000, 500), (500, 1000)], interval_s=3), [entry], 1000, 1000) is False

    def test_center_x_from_video_width(self):
        gate = TestCheckApproachDepart.TALL_NARROW
        points = _make_points([(1000, 216), (1400, 216), (1700, 216)], interval_s=3)
        assert _is_approaching_entry_point(points, [gate], 1920, 1080) is True

    def test_no_entry_zones_and_empty_coords(self):
        zone = _make_zone("Yard", zone_type="yard")
        points = _make_points([(100, 100), (500, 500)], interval_s=5)
        assert _is_approaching_entry_point(points, [zone], 1000, 1000) is False
        assert _is_approaching_entry_point(points, [{"name": "X", "zone_type": "entry_point", "coordinates": []}], 1000, 1000) is False


# ===========================================================================
# C3/analyze_trajectory: duration/speed/passthrough (kills all 16 survivors)
# ===========================================================================


class TestAnalyzeTrajectoryNumerics:
    def test_zero_duration_no_crash_and_zeroed_metrics(self):
        from datetime import datetime

        base = datetime.fromisoformat("2026-01-26T12:00:00+00:00")
        points = [
            {"x": 0, "y": 0, "timestamp": base.isoformat()},
            {"x": 10, "y": 0, "timestamp": base.isoformat()},
        ]
        result = TrajectoryAnalyzer.analyze_trajectory(track_id=9, track_points=points, object_class="person")
        assert result.dwell_seconds == 0.0
        assert result.speed_estimate == 0.0

    def test_sub_second_real_speed_survives(self):
        result = TrajectoryAnalyzer.analyze_trajectory(
            track_id=9, track_points=_make_points([(0, 0), (0, 5)], interval_s=0.5), object_class="person"
        )
        assert result.speed_estimate == 10.0

    def test_speed_rounded_to_two_places(self):
        result = TrajectoryAnalyzer.analyze_trajectory(
            track_id=9, track_points=_make_points([(0, 0), (100, 0)], interval_s=3), object_class="person"
        )
        assert result.speed_estimate == 33.33

    def test_two_point_path_is_not_single_observation(self):
        result = TrajectoryAnalyzer.analyze_trajectory(
            track_id=42, track_points=_make_points([(0, 0), (0, 10)], interval_s=5), object_class="person"
        )
        assert result.movement_pattern == "wandering"
        assert "single observation" not in result.trajectory_summary
        assert "#42" in result.trajectory_summary

    def test_single_point_keeps_stationary_text(self):
        result = TrajectoryAnalyzer.analyze_trajectory(
            track_id=5, track_points=_make_points([(100, 200)]), object_class="person"
        )
        assert "single observation" in result.trajectory_summary

    def test_zones_with_partial_dimensions_skip_zone_analysis(self):
        zone = _make_zone("T")
        points = _make_points([(100, 100), (500, 500), (900, 900)], interval_s=5)
        r = TrajectoryAnalyzer.analyze_trajectory(track_id=1, track_points=points, zones=[zone], object_class="person", video_width=1000)
        assert r.zone_transitions == [] and r.is_approaching_entry is False
        r = TrajectoryAnalyzer.analyze_trajectory(track_id=1, track_points=points, zones=[zone], object_class="person", video_height=1000)
        assert r.zone_transitions == [] and r.is_approaching_entry is False

    def test_full_pipeline_passes_zones_and_dimensions(self):
        zone = _make_zone("Driveway")
        entry = _make_entry_zone()
        points = _make_points([(100, 100), (200, 200), (300, 300), (400, 400), (450, 450)], interval_s=3)
        result = TrajectoryAnalyzer.analyze_trajectory(
            track_id=7, track_points=points, zones=[zone, entry], object_class="person", video_width=1000, video_height=1000
        )
        assert result.movement_pattern == "approaching"  # zones+width+height actually reach _classify_movement
        assert len(result.zone_transitions) > 0
        assert result.is_approaching_entry is True


# ===========================================================================
# C4/_build_summary: exact prompt-contract strings (kills all 15 survivors)
# ===========================================================================


class TestBuildSummaryExact:
    def test_full_sentence_contract(self):
        analysis = TrajectoryAnalysis(track_id=1, dwell_seconds=30.0, movement_pattern="stationary", speed_estimate=1.0)
        assert _build_summary(1, "person", analysis) == "Person #1: stationary for 30s. Speed: stationary."

    def test_zero_dwell_drops_duration_segment(self):
        analysis = TrajectoryAnalysis(track_id=2, dwell_seconds=0.0, movement_pattern="wandering", speed_estimate=0.0)
        assert _build_summary(2, "car", analysis) == "Car #2: wandering. Speed: stationary."

    def test_sub_second_dwell_still_shown(self):
        analysis = TrajectoryAnalysis(track_id=8, dwell_seconds=0.5, movement_pattern="wandering", speed_estimate=0.0)
        assert "for 0s" in _build_summary(8, "person", analysis)

    def test_hour_boundary_uses_minutes(self):
        a1 = TrajectoryAnalysis(track_id=3, dwell_seconds=3600.0, movement_pattern="stationary", speed_estimate=0.0)
        assert "60min" in _build_summary(3, "person", a1)
        a2 = TrajectoryAnalysis(track_id=4, dwell_seconds=3599.0, movement_pattern="stationary", speed_estimate=0.0)
        assert "3599s" in _build_summary(4, "person", a2)

    def test_zone_list_and_separators_exact(self):
        analysis = TrajectoryAnalysis(
            track_id=5, dwell_seconds=15.0, movement_pattern="wandering", speed_estimate=20.0,
            zone_transitions=["entered Driveway", "exited Sidewalk"],
        )
        assert "Zone activity: entered Driveway, exited Sidewalk." in _build_summary(5, "person", analysis)
        a2 = TrajectoryAnalysis(track_id=7, dwell_seconds=10.0, movement_pattern="wandering", speed_estimate=40.0, zone_transitions=["entered A"])
        assert _build_summary(7, "person", a2) == "Person #7: wandering for 10s. Speed: moderate (brisk walk). Zone activity: entered A."

    def test_warning_literal_exact(self):
        analysis = TrajectoryAnalysis(
            track_id=6, dwell_seconds=5.0, movement_pattern="approaching", speed_estimate=50.0, is_approaching_entry=True
        )
        assert _build_summary(6, "person", analysis).endswith("WARNING: approaching entry point.")

    def test_pattern_and_speed_values_rendered(self):
        a = TrajectoryAnalysis(track_id=1, dwell_seconds=45.0, movement_pattern="loitering", speed_estimate=2.1)
        s = _build_summary(1, "person", a)
        assert "loitering" in s
        assert "None" not in s


# ===========================================================================
# C5/_classify_movement: threshold edges & circling geometry (kills 13 survivors)
# ===========================================================================


class TestClassifyMovementEdges:
    def _f(self, coords, duration, zones=None, w=None, h=None):
        points = _make_points(coords, interval_s=3)
        return _classify_movement(points, _calculate_total_distance(points), duration, zones, w, h)

    def test_exactly_min_movement_is_not_under_minimum(self):
        assert self._f([(0, 0), (10, 0)], 5.0) == "wandering"  # total == 10.0, needs strict <

    def test_closed_loop_at_exactly_min_perimeter_not_circling(self):
        assert self._f([(0, 0), (5, 0), (0, 0)], 5.0) == "wandering"  # total == 10.0, needs >

    def test_exact_20_percent_return_is_circling(self):
        assert self._f([(0, 0), (12, 0), (4, 0)], 6.0) == "circling"  # return 4 == 20% of 20 (<=)
        assert self._f([(0, 0), (0, 12), (0, 4)], 6.0) == "circling"  # same along y

    def test_near_miss_return_is_wandering(self):
        assert self._f([(0, 0), (12.25, 0), (4.5, 0)], 6.0) == "wandering"  # 4.5 > 20% of 20
        assert self._f([(0, 0), (0, 12.25), (0, 4.5)], 6.0) == "wandering"

    def test_tall_and_wide_loops_are_circling(self):
        assert self._f([(0, 0), (0, 50), (0, 0)], 6.0) == "circling"
        assert self._f([(0, 0), (0, 10), (4, 0)], 6.0) == "circling"
        assert self._f([(0, 0), (4, 10), (4, 0)], 6.0) == "circling"

    def test_low_movement_at_exactly_10s_is_stationary(self):
        points = _make_points([(0, 0), (7, 0)], interval_s=10)
        assert _classify_movement(points, _calculate_total_distance(points), 10.0, None, None, None) == "stationary"

    def test_zone_logic_requires_both_dimensions(self):
        entry = _make_entry_zone()
        coords = [(100, 100), (200, 200), (300, 300), (400, 400), (450, 450)]
        assert self._f(coords, 12.0, [entry], None, 1000) == "wandering"
        assert self._f(coords, 12.0, [entry], 1000, None) == "wandering"
        assert self._f(coords, 12.0, [entry], 1000, 1000) == "approaching"


# ===========================================================================
# C6+C8/_detect_zone_transitions & _point_in_polygon output & geometry
# (kills 6 + 3 survivors)
# ===========================================================================


class TestZoneTransitionExact:
    def test_exit_enter_order_exact(self):
        driveway = _make_zone("Driveway", coords=[[0.0, 0.0], [0.3, 0.0], [0.3, 0.3], [0.0, 0.3]])
        porch = _make_zone("Porch", coords=[[0.4, 0.4], [0.6, 0.4], [0.6, 0.6], [0.4, 0.6]])
        leaving = _make_points([(100, 100), (500, 500)], interval_s=5)
        assert _detect_zone_transitions(leaving, [driveway], 1000, 1000) == ["exited Driveway"]  # started INSIDE
        assert _detect_zone_transitions(leaving, [porch], 1000, 1000) == ["entered Porch"]
        assert _detect_zone_transitions(_make_points([(500, 500), (100, 100)], interval_s=5), [porch], 1000, 1000) == ["exited Porch"]
        assert _detect_zone_transitions(_make_points([(100, 100), (150, 150)], interval_s=5), [driveway], 1000, 1000) == []

    def test_empty_guards(self):
        assert _detect_zone_transitions(_make_points([(1, 1), (2, 2)]), [], 10, 10) == []
        assert _detect_zone_transitions([], [_make_zone()], 10, 10) == []
        assert _detect_zone_transitions(_make_points([(100, 100), (500, 500)]), [{"name": "E", "zone_type": "x", "coordinates": []}], 1000, 1000) == []

    def test_unnamed_zone_falls_back_to_Unknown(self):
        zone = {"zone_type": "x", "coordinates": [[0.4, 0.4], [0.6, 0.4], [0.6, 0.6], [0.4, 0.6]]}
        points = _make_points([(100, 100), (500, 500)], interval_s=5)
        assert _detect_zone_transitions(points, [zone], 1000, 1000) == ["entered Unknown"]

    def test_multiple_zones_sorted(self):
        alpha = _make_zone("Alpha", coords=[[0.4, 0.4], [0.6, 0.4], [0.6, 0.6], [0.4, 0.6]])
        beta = _make_zone("Beta", coords=[[0.45, 0.45], [0.55, 0.45], [0.55, 0.55], [0.45, 0.55]])
        points = _make_points([(100, 100), (500, 500)], interval_s=5)
        assert _detect_zone_transitions(points, [beta, alpha], 1000, 1000) == ["entered Alpha", "entered Beta"]

    def test_point_on_edge_and_closing_edge(self):
        unit = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
        assert _point_in_polygon(0.5, 0.5, unit) is True
        assert _point_in_polygon(1.5, 0.5, unit) is False
        assert _point_in_polygon(1.0, 0.75, unit) is False  # on the boundary: exclusive convention
        assert _point_in_polygon(0.5, 1.0, [[0.0, 0.0], [4.0, 0.0], [1.0, 2.0]]) is True
        assert _point_in_polygon(0.25, 0.75, [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]]) is False  # closing edge parity


# ===========================================================================
# C9/_parse_timestamps: skip-not-stop (kills 2 survivors)
# ===========================================================================


class TestParseTimestampsSkipNotStop:
    def test_bad_timestamp_does_not_truncate(self):
        points = _make_points([(0, 0), (1, 1)])
        points[0]["timestamp"] = "bogus"
        assert len(_parse_timestamps(points)) == 1  # must KEEP the later point

    def test_missing_timestamp_does_not_truncate(self):
        points = [{"x": 0, "y": 0, "timestamp": None}] + _make_points([(1, 1), (2, 2)])
        assert len(_parse_timestamps(points)) == 2
```

**TDD procedure (one line):** run `uv run pytest backend/tests/unit/test_trajectory_analyzer.py` under a mutant build — each new test's assertion fails on its cluster's mutant diff and passes on the original (all fixtures above were pre-verified in both directions against the original and every mutant variant offline).

## Covering-test map (all in `backend/tests/unit/test_trajectory_analyzer.py`)

| Function                      | Existing test class (line)                      | What it misses                                                                     |
| ----------------------------- | ----------------------------------------------- | ---------------------------------------------------------------------------------- |
| `_parse_timestamps`           | TestParseTimestamps (101)                       | multi-point lists w/ one bad entry (C9)                                            |
| `_calculate_total_distance`   | TestCalculateTotalDistance (132)                | — no survivors                                                                     |
| `_point_in_polygon`           | TestPointInPolygon (154)                        | edge/closing-edge samples (C8)                                                     |
| `_classify_movement`          | TestClassifyMovement (174)                      | boundary totals/durations/return-fractions; dims-partition (C5)                    |
| `_check_approach_depart`      | none directly; via TestClassifyMovement 196/210 | all counting math (C1)                                                             |
| `_detect_zone_transitions`    | TestDetectZoneTransitions (249)                 | exact lists, fallback name, sortedness (C6)                                        |
| `_is_approaching_entry_point` | TestIsApproachingEntryPoint (277)               | window size, index, equality, denorm asymmetry (C2)                                |
| `_describe_speed`             | TestDescribeSpeed (304)                         | tier boundary values (C7)                                                          |
| `analyze_trajectory`          | TestAnalyzeTrajectory (326)                     | zero/sub-second duration, 2-point end-to-end, partial dims, exact speed value (C3) |
| `_build_summary`              | TestBuildSummary (467)                          | full-string equality, dwell/min branch, literals (C4)                              |

## Kill ledger

- T1 kills C7 (8/8), T2 kills C1 (21/21), T3 kills C2 (15/15), T4 kills C5 (13/13), T5 kills C3 (16/16), T6 kills C4 (15/15), T7 kills C6 (6/6) + C8 (3/3), T8 kills C9 (2/2) → **99/99 TEST-GAP survivors addressed**.
- C10–C15 (14): EQUIVALENT — no test should exist; recommend baseline suppressions keyed to these mutant indices rather than new tests. (Note the `check_approach_depart`/`is_approaching_entry_point` `mutmut_8` survivors are the same `zone.get("coordinates", []) → ()` pattern; `x__check_approach_depart` also has `mutmut_6`/`_8` = `[]→None`/`()`, all falsy under the immediate `if not coords: continue`.)
