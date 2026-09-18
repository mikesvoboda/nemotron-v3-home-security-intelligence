# WP4.4 Triage Dossier — backend/services/bbox_validation.py

- **Survivors:** 114 of 320 checked (114/438 keys; exit_code==0 in `mutants/backend/services/bbox_validation.py.meta`)
- **Source:** `backend/services/bbox_validation.py` (all mutants fall in 4 functions: `validate_bbox` 24, `validate_and_clamp_bbox` 47, `prepare_bbox_for_crop` 36, `scale_bbox_to_image` 7)
- **Covering tests:** `backend/tests/unit/services/test_bbox_validation.py` (classes: TestValidateBbox L157, TestValidateAndClampBbox L303, TestPrepareBboxForCrop L508, TestScaleBboxToImage L1285, property class TestBboxValidationProperties L742); `backend/tests/unit/services/test_bbox_validation_integration.py` (TestDetectionBboxClamping L369–428). Strategies: `backend/tests/utils/strategies.py` L540–589.
- **Why the hypothesis properties missed:** `bbox_and_image_strategy` (strategies.py:580) only generates bboxes already inside the image and non-negative (x1∈[0,W-2], x2≤W), and `invalid_bbox_xyxy_strategy` uses zero/inverted dims with y2>y1 offsets — so strict-bounds disjuncts, edge-tight "completely outside" boxes, single-dimension invalidity, and negative-coordinate branches are never generated. Unit tests then assert only `is_valid`/`was_empty_after_clamp` flags or loose `in` substrings, never the warning strings, `original_bbox` on failure paths, or exact clamped tuples. No test uses `caplog` — log-text mutants are unkillable by construction.
- Note: `except TypeError, ValueError:` at original L156 is PEP 758 syntax (valid on the run's Python 3.14), not a corruption.

## Cluster table

| # | Function (orig line) | Mutation pattern | Count | Keys (≤3 examples) | Class | Why surviving |
|---|---|---|---|---|---|---|
| 1 | validate_bbox (187,194*,201,207,215,220,233) | `bbox=bbox` kwarg dropped/None at 6 raise sites (format, NaN, height, neg-x1y1, neg-x2y2, OOB) | 10 | x_…_validate_bbox__mutmut_3, _11, _21 | TEST-GAP | Only the zero-width site (L194, killed) has `exc.bbox` asserted (test file L170). Other sites assert message only. *width-site mutants 19/20-ish are killed, not survivors. |
| 2 | validate_bbox (217) | dead defensive branch `if x2 < 0 or y2 < 0` — or→and, `<=0` tweaks | 3 | _34, _35, _37 | EQUIVALENT | Branch unreachable: at L217, x2>x1≥0 and y2>y1≥0 always; mutated conditions still always False. |
| 3 | validate_bbox (217) | same branch, `< 1` constant swaps | 2 | _36, _38 | TEST-GAP | Sub-pixel float box `(0,0,0.5,5.0)` satisfies mutated `x2<1` → spurious InvalidBoundingBoxError; valid tiny box is legitimate input, never tested. |
| 4 | validate_bbox (223–231) | strict-bounds disjunct: or→and, `<=`/`<1`/`>=` on x1,y1,x2,y2 | 9 | _44, _47, _51 | TEST-GAP | Sole strict test (L212) uses a box violating BOTH axes with margins; boundary-equal valid box `(0,0,100,100)` in 100x100 never run with strict_bounds=True; single-disjunct violations never run. |
| 5 | validate_and_clamp_bbox (374) | invalid-dimension guard or→and, `<` swaps → wrong warning path | 3 | _18, _19, _20 | TEST-GAP | Single-axis-degenerate boxes still end `is_valid=False` via the too-small clamp path; existing test (L323) uses (50,50,50,50) which violates both axes → guard hit anyway. Only `warnings[0]` text distinguishes. |
| 6 | validate_and_clamp_bbox (369,378,402,421) | `original_bbox=bbox` → None on the 4 failure returns | 4 | _8, _22, _57 | TEST-GAP | Property (L981) asserts `original_bbox == bbox` only on in-bounds inputs (final return, L430, not in survivor set); unit tests of failure paths never assert it. |
| 7 | validate_and_clamp_bbox (386–388) | negative-coord warning: or→and, `<=0`/`<1` boundary, `warnings.append(None)`, `was_clamped`→None/False | 8 | _33, _38, _40 | TEST-GAP | Existing warning test (L315) uses a box violating BOTH negative and oversized branches, so the second `was_clamped=True` (L395) masks the mutated one, and it asserts `len(warnings)>0` (passes with `[None]`). Boxes with x1==0/y1==0 never asserted warnings==[]. |
| 8 | validate_and_clamp_bbox (391–393) | oversized warning: `>=` boundary flips, message→None | 3 | _42, _43, _44 | TEST-GAP | No test with box exactly touching edge (x2==image_width) asserting no warning; message content only loosely asserted elsewhere. |
| 9 | validate_and_clamp_bbox (398) | "completely outside" disjunct: or→and, `>`/`<`/`<=1` on each of x1,y1,x2,y2 | 9 | _47, _50, _53 | TEST-GAP | Weakened guard lets edge-tight boxes (x1==W, x2==0, x2==1…) fall through to the clamp path, which *also* returns is_valid=False + was_empty_after_clamp=True (too-small); only `warnings[0]` text / (x2==1: is_valid=True!) distinguishes. Existing outside tests use far-outside (200,200,300,300). |
| 10 | validate_and_clamp_bbox (402–406) | outside-return: `warnings=None`, `was_clamped`→None/removed(False), message case/XX variants | 7 | _59, _65, _68 | TEST-GAP | Tests assert only is_valid + was_empty_after_clamp; `was_clamped is True` never asserted on this path; message case never pinned (lowercase mutant contains `in` substring). |
| 11 | validate_and_clamp_bbox (419–425) | too-small-return: `warnings=None`, message case/XX, `was_clamped`→None/removed | 6 | _88, _89, _95 | TEST-GAP | test_bbox_too_small (integration L412) asserts flags only; was_clamped value and warning contents never asserted on this path. |
| 12 | validate_and_clamp_bbox (371,380) | NaN / invalid-dim warning f-string content (XX wrap, `x2 - x1`→`x2 + x1`) | 3 | _15, _29, _30 | TEST-GAP | Tests assert `"NaN" in warnings[0]` / `"invalid dimensions" in warnings[0]` — substrings still present in every mutant; numeric interpolation (`width=100` vs `width=0`) never asserted. |
| 13 | validate_and_clamp_bbox (433) | success-return `was_empty_after_clamp=False` → None / True | 2 | _107, _115 | TEST-GAP | Success-path tests (L306, integration L375) never assert `was_empty_after_clamp is False`. |
| 14 | validate_and_clamp_bbox (414,433) | arg removed equals default: `return_none_if_empty=True` dropped (default True); `was_empty_after_clamp=False` dropped (default False) | 2 | _83, _113 | EQUIVALENT | Identical semantics. |
| 15 | prepare_bbox_for_crop (576,580) | swap guard `<` → `<=` | 2 | _2, _5 | EQUIVALENT | Swapping equal coords is a no-op; zero-dim guard (L588) still returns None. |
| 16 | prepare_bbox_for_crop (577,581,589,596,599,621–624) | `logger.debug(f"…")` → `logger.debug(None)` / f-string arg math | 7 | _3, _26, _89 | EQUIVALENT | Log text only; zero caplog/log assertions in covering files. |
| 17 | prepare_bbox_for_crop (594) | crop "completely outside" disjunct: or→and, `>`/`<`/`<=1` per coord | 9 | _17, _20, _23 | TEST-GAP | Weakened guard makes edge-tight boxes (x1==W, x2==0) return a 1-px box instead of None — exactly the crop-safety bug class; and `<=1` mutants return None for valid 1-px-touching boxes. Existing tests only use far-outside / clearly-inside boxes. |
| 18 | prepare_bbox_for_crop (602) | padding guard `> 0` → `> 1` | 1 | _28 | TEST-GAP | padding=1 never tested (existing: 0 and 10) → box silently not expanded. |
| 19 | prepare_bbox_for_crop (609,610,611,612,615→) | clamp constants: `max(1,…)`, `max(2,…)`, `image_width - 2` | 6 | _42, _48, _66 | TEST-GAP | Edge-touching boxes (x1 negative→0, width-1 box at right edge) shift output tuple; existing clamping test asserts inequalities (`x1 >= 0`), never exact tuples. |
| 20 | prepare_bbox_for_crop (609,610) | `min(x1, image_width + 1)` / height mirror | 2 | _47, _59 | EQUIVALENT | x1≤W-1 after the outside guard, so the wider clamp ceiling is inert. |
| 21 | prepare_bbox_for_crop (615) | post-clamp validity guard (or→and, `<` swaps) | 3 | _81, _82, _83 | EQUIVALENT | Post-clamp x2≤x1 is unreachable (guard chain + int clamp bounds keep x2>x1), mutated conditions all still False. |
| 22 | prepare_bbox_for_crop (620) | min-size guard: or→and, `<=`, `x2 - x1`→`x2 + x1` | 5 | _84, _86, _88 | TEST-GAP | test_min_size_filter (L590) uses a box violating BOTH axes with default min_size; single-axis violations and width==min_size exactly never tested. |
| 23 | prepare_bbox_for_crop (602) | padding guard `> 0` → `>= 0` | 1 | _27 | EQUIVALENT | Padding block with padding=0 is arithmetic no-op. |
| 24 | scale_bbox_to_image (666,672) | invalid-dim guard `<= 0` → `<= 1` on width/height | 4 | _3, _5, _9 | TEST-GAP | Degenerate-but-valid dimension 1 (e.g. source_width==1) must still scale; mutant returns the *unscaled* bbox. Existing tests use 0/negative only. |
| 25 | scale_bbox_to_image (668,674) | `logger.warning(f"…")` → `logger.warning(None)` | 2 | _6, _12 | EQUIVALENT | Log text only; no log assertions. |
| 26 | scale_bbox_to_image (679) | no-op fast path `and … ==` → `!=` | 1 | _15 | TEST-GAP | Widths-equal/heights-different pair (640,480→640,240) never tested (test_non_uniform_scaling varies only the X axis) → mutant returns unscaled bbox. |

**Totals:** TEST-GAP 92 (clusters 1,3,4,5,6,7,8,9,10,11,12,13,17,18,19,22,24,26) · EQUIVALENT 22 (clusters 2,14,15,16,20,21,23,25) · LOW-VALUE 0. Sum = 114. ✔

## Drafted tests (UNVERIFIED — not yet run red/green)

TDD procedure for every test below: run against the mutant copy (or apply the one-line diff) → assertion fails (red); run against `backend/services/bbox_validation.py` original → passes (green). Style follows `backend/tests/unit/services/test_bbox_validation.py`. Add to that file. "// UNVERIFIED - not yet run red/green"

### T1 — validate_bbox: every raise site must retain `.bbox`; valid sub-pixel box must not raise
Kills clusters 1 (10 keys) + 3 (2 keys). File: `backend/tests/unit/services/test_bbox_validation.py` (append to `TestValidateBbox`).

```python
# UNVERIFIED - not yet run red/green
    @pytest.mark.parametrize(
        "bbox,reason",
        [
            ((1, 2, 3), "invalid format"),
            ((float("nan"), 0, 100, 100), "NaN"),
            ((0, 50, 100, 50), "zero height"),
            ((-10, 0, 100, 100), "negative x1"),
            ((0.0, 0.0, -5.0, 100.0), "negative x2 (inverted caught by width check)" ),
        ],
    )
    def test_error_sites_retain_bbox_attribute(
        self, bbox: tuple[float, float, float, float], reason: str
    ) -> None:
        """Test that every InvalidBoundingBoxError raise site carries the offending bbox."""
        with pytest.raises(BoundingBoxValidationError) as exc_info:
            validate_bbox(bbox)
        assert exc_info.value.bbox == bbox, f"bbox attribute lost at site: {reason}"

    def test_out_of_bounds_error_retains_bbox(self) -> None:
        """Test that the strict-bounds error carries the bbox (only image_size is asserted today)."""
        with pytest.raises(BoundingBoxOutOfBoundsError) as exc_info:
            validate_bbox((0, 0, 150, 150), image_width=100, image_height=100, strict_bounds=True)
        assert exc_info.value.bbox == (0, 0, 150, 150)

    def test_valid_subpixel_box_does_not_raise(self) -> None:
        """Test that a tiny but valid float bbox with a zero start coordinate passes."""
        # Kills x2<1 / y2<1 mutants on the (dead for integers) second negative-coordinate branch.
        validate_bbox((0.0, 0.0, 0.5, 5.0))  # should not raise
        validate_bbox((0.0, 0.0, 5.0, 0.5))  # should not raise
```

Note: the `(0.0, 0.0, -5.0, 100.0)` parametrization exercises the width-branch site (already killed elsewhere) — harmless; drop it if you want exactly the survivor sites. The `negative x1` case kills the L215 site; the OOB method kills the L233 site; format/NaN/height cases kill L187/194/201/207 sites (both `bbox=None` and kwarg-removal variants).

### T2 — validate_bbox: strict-bounds matrix (each disjunct alone; boundary-equal must pass)
Kills cluster 4 (9 keys). File: same, `TestValidateBbox`.

```python
# UNVERIFIED - not yet run red/green
    @pytest.mark.parametrize(
        "bbox",
        [
            (0, 0, 100, 100),   # exact right/bottom edge: legal
            (10, 0, 100, 100),  # exact right edge with inset x1
            (0, 0, 50, 100),    # exact bottom edge only
        ],
    )
    def test_strict_bounds_boundary_equal_passes(self, bbox: tuple[int, int, int, int]) -> None:
        """Test that coords exactly on the image edge are not 'beyond' bounds."""
        validate_bbox(bbox, image_width=100, image_height=100, strict_bounds=True)

    @pytest.mark.parametrize(
        "bbox,reason",
        [
            ((-5, 10, 50, 50), "x1 below 0 only"),
            ((10, -5, 50, 50), "y1 below 0 only"),
            ((0, 0, 150, 50), "x2 beyond width only"),
            ((0, 0, 50, 150), "y2 beyond height only"),
        ],
    )
    def test_strict_bounds_single_disjunct_raises(
        self, bbox: tuple[int, int, int, int], reason: str
    ) -> None:
        """Test that violating ANY single bound raises (kills or->and / associativity mutants)."""
        with pytest.raises(BoundingBoxOutOfBoundsError):
            validate_bbox(bbox, image_width=100, image_height=100,
                          strict_bounds=True, allow_negative=True)
```

Red check: `_47`/`_48`/`_51`/`_52` raise on the boundary-equal cases (fail first test); `_44`–`_46` skip the raise on single-disjunct cases (fail second test).

### T3 — validate_and_clamp_bbox: per-path return contract (warnings, original_bbox, was_clamped, was_empty_after_clamp)
Kills clusters 5,6,7,8,9,10,11,12,13 (45 keys). File: same, `TestValidateAndClampBbox`.

```python
# UNVERIFIED - not yet run red/green
    def test_nan_path_exact_warning_and_original_bbox(self) -> None:
        bbox = (float("nan"), 0.0, 100.0, 100.0)
        result = validate_and_clamp_bbox(bbox, 100, 100)
        assert result.is_valid is False
        assert result.warnings == ["Bounding box contains NaN or infinite values"]
        assert result.original_bbox == bbox

    @pytest.mark.parametrize(
        "bbox,expect_width,expect_height",
        [
            ((50.0, 0.0, 50.0, 100.0), True, False),   # zero width only
            ((50.0, 0.0, 100.0, 0.0), False, True),    # zero height only
        ],
    )
    def test_single_axis_degenerate_reports_invalid_dimensions(
        self, bbox: tuple[float, float, float, float], expect_width: bool, expect_height: bool
    ) -> None:
        """Single-axis degeneracy must report 'invalid dimensions' with the real delta,
        not fall through to the too-small path."""
        result = validate_and_clamp_bbox(bbox, 100, 100)
        assert result.is_valid is False
        assert "invalid dimensions" in result.warnings[0]
        assert result.original_bbox == bbox
        assert ("width=0" in result.warnings[0]) is expect_width
        assert ("height=0" in result.warnings[0]) is expect_height

    def test_negative_only_box_flags_negative_warning(self) -> None:
        """Negative coords without any oversize: only the first warning branch can set flags."""
        result = validate_and_clamp_bbox((-10, 10, 50, 50), 100, 100)
        assert result.is_valid is True
        assert result.was_clamped is True
        assert result.warnings == ["Bounding box has negative coordinates: (-10, 10)"]

    def test_zero_start_coords_are_not_negative(self) -> None:
        """x1==0 / y1==0 must not trigger the negative-coordinate warning."""
        result = validate_and_clamp_bbox((0, 0, 50, 50), 100, 100)
        assert result.warnings == []
        assert result.was_clamped is False

    def test_exact_edge_box_produces_no_warning(self) -> None:
        """A box exactly filling the image is neither negative nor oversized."""
        result = validate_and_clamp_bbox((0, 0, 100, 100), 100, 100)
        assert result.is_valid is True
        assert result.warnings == []
        assert result.was_clamped is False
        assert result.was_empty_after_clamp is False

    def test_oversized_warning_exact_text(self) -> None:
        result = validate_and_clamp_bbox((0, 0, 150, 100), 100, 100)
        assert result.warnings == [
            "Bounding box exceeds image bounds: (150, 100) > (100, 100)"
        ]

    @pytest.mark.parametrize(
        "bbox,expect_completely_outside",
        [
            ((200.0, 200.0, 300.0, 300.0), True),   # far outside (existing input)
            ((100.0, 10.0, 150.0, 50.0), True),      # x1 == width (edge-tight)
            ((10.0, 100.0, 50.0, 150.0), True),      # y1 == height
            ((-50.0, 10.0, 0.0, 50.0), True),        # x2 == 0
            ((10.0, -50.0, 50.0, 0.0), True),        # y2 == 0
            ((-50.0, 10.0, 1.0, 50.0), False),       # x2 == 1: clips to a real 1-px sliver
            ((10.0, -50.0, 50.0, 1.0), False),       # y2 == 1 likewise
        ],
    )
    def test_outside_guard_attribution(
        self, bbox: tuple[float, float, float, float], expect_completely_outside: bool
    ) -> None:
        """Edge-tight violations must be attributed to 'completely outside', and 1-px
        clips must survive as valid clamped boxes."""
        result = validate_and_clamp_bbox(bbox, 100, 100)
        if expect_completely_outside:
            assert result.is_valid is False
            assert result.was_clamped is True
            assert result.warnings == ["Bounding box is completely outside image boundaries"]
            assert result.original_bbox == bbox
        else:
            assert result.is_valid is True
            assert result.clamped_bbox is not None

    def test_too_small_path_full_contract(self) -> None:
        result = validate_and_clamp_bbox((639.0, 479.0, 700.0, 500.0), 640, 480, min_size=5.0)
        assert result.is_valid is False
        assert result.was_clamped is True
        assert result.was_empty_after_clamp is True
        assert result.original_bbox == (639.0, 479.0, 700.0, 500.0)
        assert result.warnings == [
            "Bounding box exceeds image bounds: (700, 500) > (640, 480)",
            "Bounding box became too small after clamping",
        ]

    def test_valid_path_empty_after_clamp_is_false(self) -> None:
        result = validate_and_clamp_bbox((10, 20, 80, 90), 100, 100)
        assert result.was_empty_after_clamp is False
```

Red check: `warnings ==` equality kills all case-fold/XX/None variants (clusters 10,11,12); `was_clamped is True` kills None/default-False kwargs; edge-tight parametrizations kill the guard-weakening cluster 9 (mutants return the "too small" warning or, for x2==1, an is_valid mismatch); original_bbox asserts kill cluster 6; single-axis degenerates kill cluster 5; zero-start/exact-edge cases kill the `<=`/`<1` boundary flips in clusters 7,8.

### T4 — prepare_bbox_for_crop: edge-contract (outside guard, clamp constants, min-size, padding=1)
Kills clusters 17,18,19,22 (21 keys). File: same, `TestPrepareBboxForCrop`.

```python
# UNVERIFIED - not yet run red/green
    @pytest.mark.parametrize(
        "bbox,expect_none",
        [
            ((150, 10, 200, 50), True),    # x1 beyond width
            ((100, 10, 150, 50), True),    # x1 == width
            ((10, 100, 50, 150), True),    # y1 == height
            ((-50, 10, 0, 50), True),      # x2 == 0
            ((10, -50, 50, 0), True),      # y2 == 0
            ((-50, 10, 1, 50), False),     # x2 == 1: legitimate 1-px clip
            ((10, -50, 50, 1), False),     # y2 == 1 likewise
        ],
    )
    def test_outside_guard_edge_tight(self, bbox: tuple[int, int, int, int], expect_none: bool) -> None:
        """Boxes touching the image from outside return None; 1-px overlaps produce a crop."""
        result = prepare_bbox_for_crop(bbox, 100, 100)
        assert (result is None) is expect_none, f"bbox={bbox} -> {result}"

    @pytest.mark.parametrize(
        "bbox,expected",
        [
            ((-10, 10, 50, 50), (0, 10, 50, 50)),   # x1 clamps to 0, not 1
            ((10, -10, 50, 50), (10, 0, 50, 50)),   # y1 clamps to 0
            ((99, 10, 100, 50), (99, 10, 100, 50)), # right-edge 1-px box keeps x1=99
            ((10, 99, 50, 100), (10, 99, 50, 100)),
            ((0, 10, 1, 50), (0, 10, 1, 50)),       # x2 == 1 stays 1, not bumped to 2
            ((10, 0, 50, 1), (10, 0, 50, 1)),
        ],
    )
    def test_clamp_constants_exact(
        self, bbox: tuple[int, int, int, int], expected: tuple[int, int, int, int]
    ) -> None:
        """Clamped output tuples must be exact — PIL crop coordinates are off-by-one sensitive."""
        assert prepare_bbox_for_crop(bbox, 100, 100) == expected

    @pytest.mark.parametrize(
        "bbox,min_size",
        [
            ((50, 50, 51, 60), 5),   # width below min, height fine
            ((50, 50, 60, 51), 5),   # height below min, width fine
        ],
    )
    def test_min_size_single_axis(self, bbox: tuple[int, int, int, int], min_size: int) -> None:
        """Either axis under min_size rejects the crop (kills or->and / x2+x1 mutants)."""
        assert prepare_bbox_for_crop(bbox, 100, 100, min_size=min_size) is None

    def test_min_size_equality_boundary(self) -> None:
        """A box whose size equals min_size must survive (kills <= flip)."""
        assert prepare_bbox_for_crop((99, 99, 100, 100), 100, 100) == (99, 99, 100, 100)

    def test_padding_one_pixel_expands(self) -> None:
        """padding=1 must expand the crop by one pixel on every side."""
        assert prepare_bbox_for_crop((20, 20, 80, 80), 100, 100, padding=1) == (19, 19, 81, 81)
```

### T5 — scale_bbox_to_image: degenerate-but-valid dimensions and the width-equal fast path
Kills clusters 24,26 (5 keys). File: same, `TestScaleBboxToImage`.

```python
# UNVERIFIED - not yet run red/green
    def test_source_width_one_still_scales(self) -> None:
        """source_width == 1 is a valid (degenerate) image and must scale, not pass through."""
        result = scale_bbox_to_image((10.0, 20.0, 30.0, 40.0), 1, 480, 640, 240)
        assert result == (6400.0, 10.0, 19200.0, 20.0)

    def test_source_height_one_still_scales(self) -> None:
        result = scale_bbox_to_image((10.0, 20.0, 30.0, 40.0), 640, 1, 640, 240)
        assert result == (10.0, 4800.0, 30.0, 9600.0)

    def test_target_width_one_still_scales(self) -> None:
        result = scale_bbox_to_image((10.0, 20.0, 30.0, 40.0), 640, 480, 1, 240)
        assert result == pytest.approx((10.0 / 640, 10.0, 30.0 / 640, 20.0))

    def test_target_height_one_still_scales(self) -> None:
        result = scale_bbox_to_image((10.0, 20.0, 30.0, 40.0), 640, 480, 640, 1)
        assert result == pytest.approx((10.0, 20.0 / 480, 30.0, 40.0 / 480))

    def test_width_equal_height_differs_still_scales(self) -> None:
        """Fast path only applies when BOTH dimensions match (widths equal, heights differ)."""
        result = scale_bbox_to_image((10.0, 20.0, 30.0, 40.0), 640, 480, 640, 240)
        assert result == (10.0, 10.0, 30.0, 20.0)
```

## Notes for the fixer lane

- Clusters 10–12, 13: message equality (`warnings == [...]`) is the killer form; `in`-substring asserts let every case-fold/XX mutant through. Prefer exact equality but the tests above already encode it.
- Cluster 2/14/15/16/20/21/23/25 EQUIVALENT: consider `# pragma: no mutate` or mutmut config exclusions if the baseline is being curated; no test can (or should) kill them.
- The `prepare_bbox_for_crop` / `validate_and_clamp_bbox` outside-guard weakening (clusters 9, 17) is the highest-risk survivor class: a weakened guard silently converts "reject the crop" into a 1-pixel crop at an image edge — a plausible source of garbage thumbnails in the enrichment pipeline.
- All drafts placed in `backend/tests/unit/services/test_bbox_validation.py` to keep the unit lane (`uv run pytest backend/tests/unit/ -n auto` per CLAUDE.md). Integration lane (test_bbox_validation_integration.py) untouched.
