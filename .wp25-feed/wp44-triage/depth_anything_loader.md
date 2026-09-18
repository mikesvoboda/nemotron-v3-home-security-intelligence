# WP4.4 Triage Dossier — backend/services/depth_anything_loader.py

- **Survivors:** 167 of 595 checked mutants (428 killed, 0 unchecked).
- **Verdict source:** `mutants/backend/services/depth_anything_loader.py.meta` (`exit_code_by_key`, 0 = survived).
- **Diff source:** variant-vs-`__mutmut_orig` diffing of `mutants/backend/services/depth_anything_loader.py` (the copy holds each variant as its own function; bracket-depth body bounds). Spot-checked against `uv run mutmut show` — identical.
- **Covering test files (from `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`):**
  - `backend/tests/unit/services/test_depth_anything_loader.py` — primary (all functions)
  - `backend/tests/unit/services/test_enrichment_pipeline.py` — executes analyze_depth/get_depth_at_bbox/depth_to_feet indirectly (all mocks)
  - `backend/tests/unit/services/test_model_zoo.py` — signature/registration level only
  - `backend/tests/unit/services/test_prompts.py`, `test_prompt_formatters.py` — unrelated same-named `to_context_string`

**Totals: TEST-GAP 106 · EQUIVALENT 50 · LOW-VALUE 11 = 167.**

Structural note: `analyze_depth` alone owns 70 survivors (line-dense + unasserted result fields). Its top killers: never assert `has_close_objects`, `average_depth`, `depth_variance`, per-detection `DetectionDepth` fields, malformed-input skip paths, or `depth_sampling_method` pass-through.

## Per-cluster table

| # | Function / concern | Pattern | Count | Class | Example keys | Note |
|---|---|---|---|---|---|---|
| 1 | analyze_depth | closest-detection tracking seeds/edges: init `None`→`""`, `min_depth = 1.0`→`2.0`, `<`→`<=` | 3 | TEST-GAP | x_analyze_depth__mutmut_17 / _19 / _99 | Tests use strictly-increasing depths; no 1.0 sample, no tie (tie → last-winner in mutant) |
| 2 | analyze_depth | **has_close_objects** mutations: `in`→`not in`, label literals case/XX-broken, →`None`, kwarg removed → default `False` | 8 | TEST-GAP | x_analyze_depth__mutmut_104 / _102 / _106 | `result.has_close_objects` never asserted anywhere; 104 survives close scenes, killed only by all-far scene |
| 3 | analyze_depth | **average_depth** mutations: →`None`, ternary guard collapse (`and False`/`or True`), else 0.5→1.5, kwarg →`None`/removed | 6 | TEST-GAP | x_analyze_depth__mutmut_109 / _114 / _111 | `average_depth` never asserted; 111 differs only for empty values (np.mean → nan) |
| 4 | analyze_depth | **depth_variance** mutations: →`None`, guard collapse, `>1`→`>2`, else 0.0→1.0, kwarg →`None`/removed | 7 | TEST-GAP | x_analyze_depth__mutmut_115 / _121 / _117 | `depth_variance` never asserted; 117 nan on empty |
| 5 | analyze_depth | DetectionDepth record field mutations: `detection_id`/`class_name`/`depth_value`/`proximity_label` = `None`, `is_approaching` → None/True | 7 | TEST-GAP | x_analyze_depth__mutmut_85 / _87 / _97 | Produced records' fields never inspected; `to_dict` contract tested only for hand-built DetectionDepth |
| 6 | analyze_depth | bbox/id validation guards weakened: `not bbox or not det_id`→`and`; `isinstance(...) and len>=4`→`or`; `bbox[:4]`→`bbox[:5]` | 3 | TEST-GAP | x_analyze_depth__mutmut_54 / _63 / _68 | Malformed-bbox skip path never fed; 3-tuple bbox crashes under mutant |
| 7 | analyze_depth | bbox duck-typing `hasattr(bbox,"to_tuple")` broken | 3 | TEST-GAP | x_analyze_depth__mutmut_57 / _61 / _62 | BoundingBox-like object never passed by tests (tuples only) |
| 8 | analyze_depth | `depth_sampling_method` kwarg dropped calling get_depth_at_bbox | 1 | TEST-GAP | x_analyze_depth__mutmut_75 | No test passes a non-default sampling method through analyze_depth |
| 9 | analyze_depth | `depth_pipeline(image)` → `depth_pipeline(None)` | 1 | TEST-GAP | x_analyze_depth__mutmut_4 | MagicMock returns return_value for any arg; kill = assert called_with(image) |
| 10 | analyze_depth | det_id extraction `.get` mutations (`'id'` fallback renamed/dropped, default → None/'XXXX') | 9 | TEST-GAP | x_analyze_depth__mutmut_28 / _33 / _23 | No test builds a detection keyed only by `'id'`, or lacking both keys |
| 11 | analyze_depth | class_name extraction `.get` mutations (`'label'` fallback / `'object'` default broken; whole expr → None) | 15 | TEST-GAP | x_analyze_depth__mutmut_35 / _42 / _47 | Fallback chain + produced-record class_name never asserted |
| 12 | analyze_depth | logger.error on failure path msg/exc_info None/False variants | 4 | EQUIVALENT | x_analyze_depth__mutmut_11 / _13 / _14 | Log payload only; msg still logged, re-raise unchanged |
| 13 | analyze_depth | logger.error(**exc_info=True) drops positional msg — with a stdlib logger this raises TypeError inside the except handler and replaces the re-raise; structlog absorbs it silently | 1 | TEST-GAP | x_analyze_depth__mutmut_12 | No test makes the pipeline raise; failure path never entered |
| 14 | analyze_depth | `is_approaching=False` kwarg removed = dataclass default | 1 | EQUIVALENT | x_analyze_depth__mutmut_95 | |
| 15 | analyze_depth | variance guard `len>1`→`len>=1`; np.var([x]) == 0.0 == else-branch | 1 | EQUIVALENT | x_analyze_depth__mutmut_120 | |
| 16 | depth_to_feet | calibration_points `.get` default []→None/dropped — absorbed by `if not calibration_points` | 2 | EQUIVALENT | x_depth_to_feet__mutmut_4 / _6 | |
| 17 | depth_to_feet | bracketing boundary comparisons `<=`→`<`, `>=`→`>` — interpolation is continuous at nodes, value identical | 2 | EQUIVALENT | x_depth_to_feet__mutmut_24 / _29 | Hand-verified interior/end/out-of-range |
| 18 | depth_to_feet | multi-point bracketing degradation: `lower_point`/`upper_point` → None, once-guard flips | 4 | TEST-GAP | x_depth_to_feet__mutmut_26 / _31 / _30 | Every test is 2-point calibration where the fallback pair == the true bracket; needs 3+ points |
| 19 | depth_to_feet | below-range extrapolation picks `points[1]` twice → depth_range 0 → wrong point's distance | 1 | TEST-GAP | x_depth_to_feet__mutmut_34 | No below-range call in tests |
| 20 | depth_to_feet | `elif upper_point is None` → `is not None` → TypeError on above-range depth | 1 | TEST-GAP | x_depth_to_feet__mutmut_36 | No above-range call in tests |
| 21 | depth_to_feet | clamp floor `max(0.1, result)` → `max(1.1, result)` | 1 | TEST-GAP | x_depth_to_feet__mutmut_69 | Kill with any expected distance in (0.1, 1.1) |
| 22 | estimate_relative_distances | method kwarg dropped calling get_depth_at_bbox | 1 | TEST-GAP | x_estimate_relative_distances__mutmut_6 | Only method='center' ever passed |
| 23 | format_depth_for_nemotron | length-mismatch warning inverted / msg → None | 2 | EQUIVALENT | x_format_depth_for_nemotron__mutmut_7 / _8 | Warning never asserted |
| 24 | format_depth_for_nemotron | zip `strict=False` → None / removed (falsy==default) | 2 | EQUIVALENT | x_format_depth_for_nemotron__mutmut_12 / _15 | |
| 25 | format_depth_for_nemotron | early-return guard `or`→`and` — partial empty input | 1 | TEST-GAP | x_format_depth_for_nemotron__mutmut_1 | |
| 26 | format_depth_for_nemotron_with_distances | early-return guard `or`→`and` | 1 | TEST-GAP | x_format_depth_for_nemotron_with_distances__mutmut_1 | |
| 27 | format_depth_for_nemotron_with_distances | `count = min(...)` arg removals + zip strict mutations — slice-to-min + zip-shortest provably identical | 7 | EQUIVALENT | x_format_depth_for_nemotron_with_distances__mutmut_4 / _8 / _23 | |
| 28 | both formatters | class_name fallback mutations (key case, wrong key, default → None/'OBJECT'/'XXobjectXX') | 11 | TEST-GAP | x_format_depth_for_nemotron_with_distances__mutmut_38 / _26; x_format_depth_for_nemotron__mutmut_30 | with_distances has **no fallback test**; FM's `assert "object" in result` substring-matches `'XXobjectXX'` — exact per-item equality kills |
| 29 | both formatters | prompt prefix / join-separator case & XX mutations pass loose membership asserts | 6 | TEST-GAP | x_format_depth_for_nemotron_with_distances__mutmut_47 / _46 / _50; x_format_depth_for_nemotron__mutmut_40 | LLM prompt text is product surface; needs exact-string asserts |
| 30 | get_depth_at_bbox | `shape[:2]`→`shape[:3]` (2-D contract) | 1 | EQUIVALENT | x_get_depth_at_bbox__mutmut_3 | |
| 31 | get_depth_at_bbox | upper clamp `w-1`→`w+1`, `h-1`→`h+1` — oversized x1/y1 lands in invalid-bbox 0.5 branch in original too | 2 | EQUIVALENT | x_get_depth_at_bbox__mutmut_15 / _28 | x2/y2 clamp untouched ⇒ x1>w-1 ⇒ x2≤w-1 < x1 ⇒ both return 0.5 |
| 32 | get_depth_at_bbox | upper clamp `w-1`→`w-2`, `h-1`→`h-2` — bbox touching last col/row | 2 | TEST-GAP | x_get_depth_at_bbox__mutmut_16 / _29 | |
| 33 | get_depth_at_bbox | x2/y2 lower clamp `0`→`1` — off-left bbox returns edge pixel, not 0.5 | 2 | TEST-GAP | x_get_depth_at_bbox__mutmut_35 / _48 | |
| 34 | get_depth_at_point | `shape[:2]`→`shape[:3]` | 1 | EQUIVALENT | x_get_depth_at_point__mutmut_2 | |
| 35 | load_depth_model | logger.info/warning/error msg, exc_info, extra mutations | 19 | EQUIVALENT | x_load_depth_model__mutmut_6 / _39 / _49 | Log payload only; no caplog usage in this module |
| 36 | load_depth_model | `is_local = Path(model_path).is_dir()` → None — local-dir branch (explicit from_pretrained, the huggingface_hub repo-id workaround) never taken | 1 | TEST-GAP | x_load_depth_model__mutmut_15 | Both success tests pass fake non-dir paths |
| 37 | load_depth_model | CUDA-guard / ImportError exception message case & XX mutations — key-phrase substring still matches | 4 | LOW-VALUE | x_load_depth_model__mutmut_3 / _36 / _34 | Diagnostic prose |
| 38 | normalize_depth_map | `.get('depth', default)` default broken — np.array(TypeError) in original too; unassertable | 2 | LOW-VALUE | x_normalize_depth_map__mutmut_9 / _11 | |
| 39 | normalize_depth_map | PIL-detect `hasattr 'convert'` broken — both branches run identical `np.array(depth_data, float32)` | 3 | EQUIVALENT | x_normalize_depth_map__mutmut_15 / _19 / _20 | |
| 40 | normalize_depth_map | `max-min > 0` → `> 1` — range ≤1 maps collapse to all-zeros | 1 | TEST-GAP | x_normalize_depth_map__mutmut_27 | Tests feed range-100/uniform-50 only; analyze_depth's 0.1–0.7 maps would collapse |
| 41 | rank_detections_by_proximity | zip `strict=True` → None/False/removed — lengths pre-checked equal, strict inert | 3 | EQUIVALENT | x_rank_detections_by_proximity__mutmut_14 / _10 / _13 | |
| 42 | rank_detections_by_proximity | ValueError message XX-wrapped — pytest.raises match still passes | 1 | LOW-VALUE | x_rank_detections_by_proximity__mutmut_3 | |
| 43 | DepthAnalysisResult.to_dict | output keys `average_depth` / `depth_variance` renamed or case-changed | 4 | TEST-GAP | xǁDepthAnalysisResultǁto_dict__mutmut_7 / _8 / _9 | test_depth_analysis_result_to_dict (line 769) asserts only 3 of 5 keys; downstream JSON consumers read the rest |
| 44 | to_context_string | depth sort key removed (key=None / kwarg dropped) — order silently flips to det_id order | 2 | TEST-GAP | xǁDepthAnalysisResultǁto_context_string__mutmut_11 / _13 | No ordering assertion; key=None sorts tuples by det_id |
| 45 | to_context_string | risk_note default `''`→None/'XXXX' — 'None'/'XXXX' garbage in every no-risk line | 2 | TEST-GAP | xǁDepthAnalysisResultǁto_context_string__mutmut_16 / _17 | |
| 46 | to_context_string | joiner `'\n'` → `'XX\nXX'` — layout carries literal XX | 1 | TEST-GAP | xǁDepthAnalysisResultǁto_context_string__mutmut_36 | No line-structure assert |
| 47 | to_context_string | header / `[CLOSE TO CAMERA]` / `[APPROACHING]` / blank-summary-line XX-wrapped — membership asserts still match inside the XX wrapper | 4 | LOW-VALUE | xǁDepthAnalysisResultǁto_context_string__mutmut_6 / _22 / _25 / _33 | |

## Highest-value TEST-GAP clusters chosen for drafted tests

1. **Cluster 2+3+4 — analyze_depth result statistics never asserted** (21 mutants)
2. **Cluster 29 (+28) — formatter output exact string never asserted; class_name fallback path** (17 mutants)
3. **Cluster 43 — to_dict drops two output keys silently** (4 mutants)
4. **Cluster 1 — closest_detection_id edge cases (1.0 sample, tie)** (3 mutants)
5. **Cluster 18+19+20 — depth_to_feet out-of-range & multi-point calibration** (6 mutants)
6. **Cluster 6 — malformed detection/bbox validation guards in analyze_depth** (3 mutants)
7. **Cluster 32+33 — get_depth_at_bbox clamp boundaries** (4 mutants)

## Drafted tests (UNVERIFIED — not yet run red/green)

All target `backend/tests/unit/services/test_depth_anything_loader.py` (append; style follows existing file). TDD procedure for each: add test → run, expect FAIL (assertion) against each mutant diff in the cluster → keep, expect PASS on original, then re-run `mutmut run` for the module to confirm kills.

```python
# =============================================================================
# WP4.4: kill depth_anything_loader survivor clusters (DRAFTED - UNVERIFIED)
# UNVERIFIED - not yet run red/green
# =============================================================================


@pytest.mark.asyncio
async def test_analyze_depth_result_statistics(self_free_names):
    """analyze_depth must populate has_close_objects / average_depth /
    depth_variance exactly. Kills x_analyze_depth__mutmut_{102,104-108,
    109-111,114-117,121,122,125-127,130-132} (has_close/avg/variance -> None,
    guard collapse, in->not in, kwarg-removal -> dataclass defaults)."""
    from backend.services.depth_anything_loader import analyze_depth

    depth_map = np.array(
        [[0.10, 0.90], [0.90, 0.90]],  # range 0.8 so cluster 40 (normalize >1) stays out
        dtype=np.float32,
    )
    mock_pipeline = MagicMock()
    mock_pipeline.return_value = {"depth": depth_map}

    result = await analyze_depth(
        mock_pipeline,
        MagicMock(),
        [
            {"detection_id": "a", "class_name": "person", "bbox": (0, 0, 1, 1)},
            {"detection_id": "b", "class_name": "car", "bbox": (1, 1, 2, 2)},
        ],
    )

    assert result.has_close_objects is True          # 'a' at depth 0.10 = "very close"
    assert result.average_depth == pytest.approx(0.5)
    assert result.depth_variance == pytest.approx(0.16)
    # all-far scene kills the inverted `not in` and default-False variants
    far_map = np.array([[0.80, 0.95], [0.95, 0.95]], dtype=np.float32)
    mock_pipeline.return_value = {"depth": far_map}
    far = await analyze_depth(
        mock_pipeline, MagicMock(), [{"detection_id": "c", "class_name": "tree", "bbox": (0, 0, 1, 1)}]
    )
    assert far.has_close_objects is False
    assert far.depth_variance == 0.0                 # single detection -> else-branch
    assert far.average_depth == pytest.approx(0.8)


@pytest.mark.asyncio
async def test_analyze_depth_calibration_closest_edges_and_fields():
    """closest_detection_id: a detection at depth exactly 1.0 must NOT be
    'closest' (kills __mutmut_19 min_depth=2.0); on a tie the FIRST wins
    (kills __mutmut_99 <=); result.closest_depth/record fields asserted
    (kills __mutmut_17, 82, 85-89, 97); pipeline must receive the image
    (kills __mutmut_4)."""
    from backend.services.depth_anything_loader import analyze_depth

    pipeline = MagicMock()
    pipeline.return_value = {"depth": np.array([[0.10, 1.00], [1.00, 1.00]], dtype=np.float32)}
    image = MagicMock()

    result = await analyze_depth(
        pipeline,
        image,
        [
            {"detection_id": "close", "class_name": "person", "bbox": (0, 0, 1, 1)},
            {"detection_id": "far", "class_name": "wall", "bbox": (1, 1, 2, 2)},
        ],
    )

    pipeline.assert_called_once_with(image)
    assert result.closest_detection_id == "close"
    assert result.closest_depth == pytest.approx(0.10)
    assert result.detection_depths["close"].class_name == "person"
    assert result.detection_depths["close"].is_approaching is False
    assert result.detection_depths["far"].proximity_label == "very far"


@pytest.mark.asyncio
async def test_analyze_depth_malformed_detections_skipped():
    """Malformed inputs must be skipped, never crash or store garbage:
    bbox with 3 coords (__mutmut_63 'or'), 5-coord bbox (__mutmut_68 [:5]),
    detection without bbox (__mutmut_54 'and'), detection without any id key
    (__mutmut_23/28-34 variants via the '' skip)."""
    from backend.services.depth_anything_loader import analyze_depth

    pipeline = MagicMock()
    pipeline.return_value = {"depth": np.array([[0.1, 0.9], [0.9, 0.9]], dtype=np.float32)}

    result = await analyze_depth(
        pipeline,
        MagicMock(),
        [
            {"detection_id": "bad3", "class_name": "person", "bbox": (0, 0, 1)},
            {"detection_id": "bad5", "class_name": "person", "bbox": (0, 0, 1, 1, 9)},
            {"detection_id": "nobbox", "class_name": "person"},
            {"class_name": "person"},  # no detection_id and no id -> skipped
            {"detection_id": "good", "class_name": "person", "bbox": (0, 0, 1, 1)},
        ],
    )

    assert result.detection_count == 1
    assert result.detection_depths["good"].class_name == "person"


def test_depth_to_feet_out_of_range_and_multipoint():
    """depth_to_feet must extrapolate outside the calibration range using the
    EDGE pairs (kills __mutmut_34 points[1] twice -> depth_range 0;
    __mutmut_36 `is not None` -> TypeError; __mutmut_25/26/30/31 bracketing
    assignment/guard collapses) and must pick the right bracket with 3+
    points (kills __mutmut_30/31 'first >= depth' breakage)."""
    from backend.services.depth_anything_loader import depth_to_feet

    calib3 = {
        "calibration_points": [
            {"depth_value": 0.2, "distance_feet": 5.0},
            {"depth_value": 0.5, "distance_feet": 15.0},
            {"depth_value": 0.8, "distance_feet": 40.0},
        ]
    }
    # depth 0.1 below range: extrapolate from points[0],[1]: 5 + (-0.5)*(10) = 0 -> clamp 0.1
    assert depth_to_feet(0.1, calib3) == pytest.approx(0.1)
    # depth 0.9 above range: extrapolate from points[-2],[-1]: 40 + 0.5*25 = 62.5
    assert depth_to_feet(0.9, calib3) == pytest.approx(62.5)
    # depth 0.65: bracket points 2&3 -> 15 + 0.5*25 = 27.5 (kills once-guard flips)
    assert depth_to_feet(0.65, calib3) == pytest.approx(27.5)


def test_depth_to_feet_clamp_floor_is_0_1_feet():
    """Negative interpolation result clamps to 0.1 feet, NOT 1.1
    (kills x_depth_to_feet__mutmut_69)."""
    from backend.services.depth_anything_loader import depth_to_feet

    calib = {
        "calibration_points": [
            {"depth_value": 0.2, "distance_feet": 0.5},
            {"depth_value": 0.4, "distance_feet": 1.5},
        ]
    }
    assert depth_to_feet(0.1, calib) == pytest.approx(0.1)  # raw 0.0 -> floor 0.1
    assert depth_to_feet(0.15, calib) == pytest.approx(0.25)


def test_format_depth_for_nemotron_exact_strings_and_fallbacks():
    """Exact output (kills prefix/separator case+XX mutants 36/40, 46-48/50)
    and 'label'/'object' fallback chain with NO class_name key (kills the
    XXobjectXX substring-survivor FM_30 and all of WD 26-38)."""
    from backend.services.depth_anything_loader import (
        format_depth_for_nemotron,
        format_depth_for_nemotron_with_distances,
    )

    out = format_depth_for_nemotron([{"class_name": "person"}], [0.12])
    assert out == "Spatial context: person is very close (depth: 0.12)"
    # fallback: no class_name, has label
    out = format_depth_for_nemotron([{"label": "dog"}], [0.2])
    assert out == "Spatial context: dog is close (depth: 0.20)"
    # fallback: neither -> exact 'object' (not 'XXobjectXX'/'OBJECT'/None)
    out = format_depth_for_nemotron([{"confidence": 0.9}], [0.3])
    assert out == "Spatial context: object is close (depth: 0.30)"
    # partial-empty guard: empty detections with non-empty depths -> sentinel (kills *_1)
    assert format_depth_for_nemotron([], [0.5]) == "No spatial depth information available."

    out = format_depth_for_nemotron_with_distances(
        [{"label": "dog"}, {"confidence": 0.5}], [0.2, 0.5], [6.4, None]
    )
    assert out == "Spatial context: dog is approximately 6 feet away, close, object is moderate distance (depth: 0.50)"
    assert format_depth_for_nemotron_with_distances([], [0.5], [1.0]) == "No spatial depth information available."


def test_depth_analysis_result_to_dict_full_contract():
    """to_dict must expose all five keys with exact names
    (kills xǁDepthAnalysisResultǁto_dict__mutmut_7..10)."""
    from backend.services.depth_anything_loader import (
        DepthAnalysisResult,
        DetectionDepth,
    )

    result = DepthAnalysisResult(
        detection_depths={"d": DetectionDepth("d", "person", 0.2, "close")},
        closest_detection_id="d",
        has_close_objects=True,
        average_depth=0.2,
        depth_variance=0.01,
    )
    data = result.to_dict()
    assert data["average_depth"] == pytest.approx(0.2)
    assert data["depth_variance"] == pytest.approx(0.01)
    assert set(data) == {
        "detection_depths", "closest_detection_id", "has_close_objects",
        "average_depth", "depth_variance",
    }


def test_to_context_string_ordering_and_no_stray_text():
    """Lines must be ordered closest-first, lines joined by exactly '\n',
    and non-risk lines carry no risk note (kills to_context_string
    __mutmut_11/13 ordering, 16/17 risk_note default, 36 joiner)."""
    from backend.services.depth_anything_loader import (
        DepthAnalysisResult,
        DetectionDepth,
    )

    # det ids deliberately reverse of depth order
    result = DepthAnalysisResult(
        detection_depths={
            "zz": DetectionDepth("zz", "person", 0.05, "very close"),
            "aa": DetectionDepth("aa", "car", 0.80, "very far"),
        },
    )
    lines = result.to_context_string().split("\n")
    assert lines[0] == "Spatial depth analysis:"
    assert lines[1].startswith("  person") and lines[2].startswith("  car")
    assert "None" not in result.to_context_string()
    assert "XX" not in result.to_context_string()


def test_get_depth_at_bbox_edge_clamps():
    """Clamps are exactly [0, w-1]/[0, h-1]: bbox touching the last
    column/row samples the real region (kills __mutmut_16/29 -2), bbox fully
    off the left/top edge returns the 0.5 sentinel (kills __mutmut_35/48
    lower clamp ->1)."""
    depth_map = np.zeros((4, 4), dtype=np.float32)
    depth_map[0, 3] = 0.9
    depth_map[3, 0] = 0.7
    # last column touched: x2=3 stays 3 (mutant w-2 -> 2 => invalid -> 0.5)
    assert get_depth_at_bbox(depth_map, (3.0, 0.0, 3.0, 0.0), method="center") == 0.5  # x2<=x1 invalid
    assert get_depth_at_bbox(depth_map, (2.0, 0.0, 3.0, 1.0), method="min") == pytest.approx(0.9)
    # mutant y-2 clamp: bbox y2=3 -> 2 excludes row 3
    assert get_depth_at_bbox(depth_map, (0.0, 2.0, 1.0, 3.0), method="max" if False else "mean") is not None
    # off-image bbox: x2 clamps to 0 -> x2 <= x1(=0)? x1 also clamps 0: original returns 0.5
    assert get_depth_at_bbox(depth_map, (-5.0, -5.0, -1.0, -1.0), method="center") == 0.5


def test_estimate_relative_distances_passes_method():
    """method='min' must reach get_depth_at_bbox (kills
    x_estimate_relative_distances__mutmut_6 and x_analyze_depth__mutmut_75
    sibling behaviour)."""
    depth_map = np.array([[0.9, 0.1], [0.9, 0.9]], dtype=np.float32)
    result = estimate_relative_distances(depth_map, [(0, 0, 2, 2)], method="min")
    assert result == [pytest.approx(0.1)]
```

Fixup before landing: replace the odd parameter names in the first two drafted tests (`self_free_names` was a placeholder — the statistics test takes no params; drop it), and simplify the `test_get_depth_at_bbox_edge_clamps` middle assertion to `assert get_depth_at_bbox(depth_map, (0.0, 2.0, 1.0, 3.0), method="mean") == pytest.approx(0.7 / 2)` style once the expected mean of rows 2-3/cols 0-1 = (0+0+0.7+0)/4 = 0.175 is pinned; the mutant (h-2 → row 2 only) yields 0.0.

## Covering-test verdicts (TEST-GAP vs weak asserts)

- `test_depth_anything_loader.py:894 test_analyze_depth_with_detections` — executes all of analyze_depth's result-assembly lines but asserts only `has_detections`/`detection_count`/dict membership/`closest_detection_id` → clusters 2,3,4,5 are "test exists, asserts too weakly".
- `:769 test_depth_analysis_result_to_dict` — asserts 3 of 5 keys → cluster 43 weak assert.
- `:811 test_depth_analysis_result_to_context_string_with_detections` — membership asserts only, never exact string/order/absence of stray text → clusters 44,45,46,29.
- `:980 test_depth_to_feet_interpolation` — 2-point calibration, exact node → clusters 18,19,20 have no coverage at all.
- `:658 test_depth_boundaries`, `:371 mismatched_lengths` — cover label thresholds and min-length behavior, which is why those clusters are killed/equivalent.
