# WP4.4 Triage Dossier — `backend/services/ocr_service.py`

**Source under mutation:** `backend/services/ocr_service.py` (416 lines)
**Verdicts:** `mutants/backend/services/ocr_service.py.meta` — 219 keys, 131 killed, **88 survived**, 0 unchecked.
**Survivors triaged here:** **88**
**Covering test file (all 7 functions, 66 test IDs):** `backend/tests/unit/services/test_ocr_service.py` (785 lines)
**Diff source:** `uv run mutmut show <key>` succeeded for all 88 keys (54 s, zero errors, no cache contention).

Classification totals: **TEST-GAP 47 · LOW-VALUE 24 · EQUIVALENT 17** (sum 88).

---

## How the module actually behaves (facts that drive the calls)

Verified against the project venv and the real helper source, not guessed:

| Fact | Verified how | Consequence |
| --- | --- | --- |
| `Image.open(f).convert(None)` returns the image **unconverted** | venv `python -c`: JPEG-from-RGB → `RGB`; PNG-from-RGBA → `RGBA`; JPEG-from-L → `L` | `convert("RGB")` → `convert(None)` is equivalent *only* for files that already load as RGB. `test_load_image_sync` (line 707) uses a JPEG written from an **RGB** source, so its `assert result.mode == "RGB"` (line 716) cannot distinguish them. |
| `prepare_bbox_for_crop` (`backend/services/bbox_validation.py:536`) **does** swap inverted coords (576-582), clamps (609-614), and defaults `min_size: int = 1` (line 541) | read of helper | `_crop_plate_region`'s `abs(x2-x1)`/`abs(y2-y1)` (112-113) exist **only** to size padding. And dropping the explicit `min_size=1` changes nothing — the default is the same value. |
| `get_logger` returns a plain stdlib `logging.Logger` | `backend/core/logging.py:1107-1131` | `logger.warning(None)` runs without raising and logs `"None"`, so message clobbers fail silently rather than crashing. |
| Existing crop tests assert only `size > 0`, `size <= bounds`, and `size == (200, 50)` at `padding=0.0` | test file lines 110-142 | **No existing test pins any non-zero padded crop geometry.** `padding=0.0` makes every padding mutant inert by construction. This is the file's biggest hole. |
| Zero-size bbox is rejected by the helper at `x2 <= x1` (line 588) *before* the `min_size` check (line 620) is reached | helper read | `min_size=1` → `min_size=2` is unreachable on the only degenerate shape the suite exercises. |
| `texts` and `confidences` are appended in lockstep (169-170) and line 172 returns when `texts` is empty | read | the `if confidences` / `else 0.0` fallback at line 177 is **dead for every input** → EQUIVALENT. |
| `_find_image_for_plate(image_paths, loaded_images)` is called with **identical arguments every iteration** (line 308) | read of `read_plates` loop | "no image" is a batch-wide condition, never per-plate — so the no-image `continue`→`break` is unobservable in the return value. |
| Zero `caplog` usage in the covering file (grep count = 0); zero tests read `.raw_text` / `.bbox` / `.plate_detection_id` off a `read_plates` result | grep over test file | Every result-field, boundary and traceback-carrying mutant survives for lack of an assertion, not lack of execution. |
| `asyncio.to_thread` is patched with `autospec=True` plus a canned `return_value` | e.g. lines 219, 271, 347 | The delegate **and its arguments** are never inspected → the 12 call-argument clobbers survive. |

---

## Per-cluster table

Mutant keys below are suffixes of `backend.services.ocr_service.x<function>__mutmut_<n>`.

| Cluster | Function | Mutants | N | Class | Evidence / reasoning |
| --- | --- | --- | --- | --- | --- |
| **C01** crop padding geometry derived from wrong axes or forced to zero | `_crop_plate_region` | 5, 8, 10, 15, 16, 18, 23, 24 | **8** | **TEST-GAP** | `w=abs(x2+x1)` (5) and `h=abs(y2+y1)` (8) inflate padding for any bbox not anchored at the origin; `if … and False` (10, 18) zero the padding on the non-degenerate branch; `w>1`/`h>1` (15, 23) drop padding for 1-px boxes; `else 1` (16, 24) injects a stray pixel on a zero-dimension axis. Verified geometry for bbox `(100,200,300,250)` @ `padding=.05` in a 1000×800 image: original → crop box `(90,190,310,260)` = **220×70**; #5 → 240×90, #8 → 244×94, #10 → 204×54. 13 tests execute lines 112-115 but assert only `size > 0` / `size <= bounds` / `(200,50)` at `padding=0.0` — wide enough to admit all eight. |
| **C02** crop padding guard tautologized | `_crop_plate_region` | 11, 14, 19, 22 | 4 | EQUIVALENT | `or True` (11, 19) takes the arithmetic branch when `w == 0`, but `int(0 * padding) == 0` is exactly the `else 0` value. `w >= 0` / `h >= 0` (14, 22) are always true because `abs()` never returns negative — same reason. No input separates them from the original. |
| **C03** `padding=` kwarg dropped from `prepare_bbox_for_crop` | `_crop_plate_region` | 34 | 1 | LOW-VALUE | Helper default `padding=0` applies, so the crop is exactly the bbox (200×50 vs 220×70). Real, but `padding: float = 0.05` is a tuning constant, not a contract. Dies for free with T1. |
| **C04** `min_size=` kwarg dropped | `_crop_plate_region` | 35 | 1 | EQUIVALENT | The helper signature defaults `min_size: int = 1` (bbox_validation.py:541) — the removed literal was the default. Identical for all inputs. |
| **C05** `min_size=1` → `min_size=2` | `_crop_plate_region` | 40 | 1 | LOW-VALUE | The only degenerate bbox the suite uses (`test_crop_plate_region_zero_size_bbox`, line 513) is rejected earlier at `x2 <= x1` (helper line 588), before the `min_size` check at 620 is reached; the smallest surviving box in the suite is 200×50. |
| **C06** invalid-bbox warning message → `None` | `_crop_plate_region` | 42 | 1 | LOW-VALUE | `Logger.warning(None)` logs `"None"`, no raise (verified). Text only; the `return None` is asserted by line 507's test. |
| **C07** `cls=True` direction-classification flag dropped from `ocr_model.ocr()` | `_run_ocr_sync` | 5, 6, 7, 8 | **4** | **TEST-GAP** | `cls=None` (5) / `cls=False` (8) disable PaddleOCR's text-direction classifier; `ocr(plate_array, )` (7) drops the flag; `ocr(cls=True)` (6) drops the image entirely. Line 153's comment makes the flag deliberate ("cls=True enables text direction classification"). All 8 covering tests use `MagicMock().ocr`, which accepts any call shape and returns the canned value, so nothing pins the delegate contract — upside-down plate text silently stops being corrected. |
| **C08** input ndarray clobbered (`np.array(...)` → `None` / arg removed) | `_run_ocr_sync` | 1, 2, 4 | 3 | LOW-VALUE | Crash material on a real model, but the mock accepts anything. Asserting "the crop becomes an ndarray" duplicates C07's delegate-identity test; crash-on-real-model is not a contract worth pinning. |
| **C09** parsed-line `len()` guards weakened | `_run_ocr_sync` | 22, 25, 26, 30, 33 | 5 | LOW-VALUE | `> 0` → `or True` / `>= 0` (22, 25) are tautologies; `> 0` → `> 1` (26) and `> 1` → `or True` / `>= 1` (30, 33) only diverge when PaddleOCR hands back a **1-element or empty** text tuple (`("ABC",)` or `()`), a payload shape the real library never emits. Reachable only via a fabricated fixture, and asserting it is noise. |
| **C10** `if confidences` guard tautologized | `_run_ocr_sync` | 45 | 1 | EQUIVALENT | `confidences` is empty only when `texts` is empty, and line 172 already returned in that case. The `or True` cannot change any execution. Dead defensive tweak. |
| **C11** malformed-line well-formedness guard `and` → `or` | `_run_ocr_sync` | 17 | **1** | **TEST-GAP** | Line 165. With `or`, a 1-element line evaluates `line[1]` → `IndexError`, caught by the outer `except`, so the **whole plate** returns `(None, 0.0)` instead of skipping that line and keeping the good ones. `test_run_ocr_sync_malformed_line_structure` (line 546) uses an *all*-malformed fixture, where original and mutant both land on `(None, 0.0)`; a mixed `[malformed, valid]` fixture separates them. Real resilience contract, too-weak fixture. |
| **C12** result-presence guard `or` → `and` | `_run_ocr_sync` | 9 | 1 | EQUIVALENT | Case analysis: truthy `result` → both forms fall through to the same loop; falsy `result` → original returns `(None, 0.0)` immediately, mutant raises on `result[0]` and the `except` returns the same `(None, 0.0)`; falsy `result[0]` (`[None]`/`[[]]`) → original returns `(None, 0.0)`, mutant falls through, the loop yields no texts, line 172 returns `(None, 0.0)`. `test_run_ocr_sync_null_result` covers the `None` case and passes either way. No input separates them. |
| **C13** missing-confidence fallback `0.0` → `1.0` | `_run_ocr_sync` | 35 | 1 | LOW-VALUE | Divergence observable only with a fabricated 1-element text tuple (avg confidence 0.0 vs 1.0). Same unreachable-in-practice payload as C09. |
| **C14** empty-confidence average fallback `0.0` → `1.0` | `_run_ocr_sync` | 48 | 1 | EQUIVALENT | The `else` branch is unreachable whenever line 177 executes (lockstep append + line 172 guard). Dead defensive tweak. |
| **C15** empty-text fallback `""` → `"XXXX"` | `_run_ocr_sync` | 27 | 1 | LOW-VALUE | Diverges only with a fabricated empty text tuple, where the mutant invents a plate reading `"XXXX"` instead of nothing. Payload shape real OCR never produces. |
| **C16** OCR-failure warning message → `None` | `_run_ocr_sync` | 49 | 1 | LOW-VALUE | Text only. `test_run_ocr_sync_handles_exception` (167) asserts the `(None, 0.0)` return, which still holds. |
| **C17** `PlateText` provenance fields flattened to `None` / kwargs dropped | `read_plates` | 46, 48, 49, 51, 53, 54 | **6** | **TEST-GAP** | `raw_text=None` (46), `plate_detection_id=None` (48), `bbox=None` (49), plus the three kwarg removals (51, 53, 54) that leave the same fields at their dataclass defaults. `test_read_plates_success` (214) asserts only `.text` and `.confidence`; grep confirms **no** test reads `.raw_text`, `.bbox` or `.plate_detection_id` off a `read_plates` result (`test_plate_text_creation`, 406, exercises the dataclass, not the service). `plate_detection_id=None` is the worst: every result loses the join key that ties it to its detection. |
| **C18** `asyncio.to_thread` delegate/arguments clobbered | `read_plates` | 28, 29, 30, 31, 32, 33 | **6** | **TEST-GAP** | `_run_ocr_sync` → `None` (28) / removed (31); `ocr_model` → `None` (29) / removed (32); `plate_crop` → `None` (30) / removed (33). Survive solely because the suite patches `backend.services.ocr_service.asyncio.to_thread` with `autospec=True` + canned `return_value` and never reads `call_args`. On a real run: `await to_thread(None, …)` → `TypeError`, or OCR of `None`. The module's central promise (docstring lines 6-7, inference off the event loop) is currently unverifiable. |
| **C19** `continue` → `break` on the per-plate skip paths | `read_plates` | 26, 38, 43, 61 | **4** | **TEST-GAP** | Invalid-crop (322), below-threshold (337), too-short-text (346) and exception (367) skips become batch aborts, silently abandoning every remaining detection. Every multi-detection test gives both detections the same canned OCR answer, so a filtered case asserts `len(results) == 0` and an admitted case asserts `len(results) == 2` — neither can tell "skipped one" from "stopped early". Needs a mixed detection list. |
| **C20** `continue` → `break` on the no-image path | `read_plates` | 18 | 1 | EQUIVALENT | `_find_image_for_plate` receives the *same* `image_paths` / `loaded_images` on every iteration (line 308), so "no image" is a batch-wide condition: if plate 1 has no image, no plate does. The loop would end on the next iteration anyway, and the only difference is log volume — which no test observes. |
| **C21** `min_confidence` threshold `<` → `<=` | `read_plates` | 36 | **1** | **TEST-GAP** | Line 331. `test_read_plates_success` uses 0.95 vs threshold 0.5; the filtered test uses 0.3 vs 0.5. Never a result sitting **exactly** on the threshold, which is the entire contract of a "minimum confidence to include result" parameter. |
| **C22** `exc_info=True` dropped on the per-plate failure log | `read_plates` | 57, 59, 60 | **3** | **TEST-GAP** | Lines 363-366: `exc_info=None`, kwarg removed, `exc_info=False`. The module's documented strategy is "best-effort, errors logged but not raised" (lines 9-12), so the log record is the *only* observable of a swallowed failure — dropping the traceback makes a broken camera's plate OCR permanently undebuggable. Zero `caplog` usage in the covering file. |
| **C23** log messages → `None` | `read_plates` | 3, 17, 25, 37, 42, 55, 56, 62 | 8 | LOW-VALUE | Four warnings, three debug lines, the exception message, and the sole `logger.info` summary (369) replaced by `None`. Runs fine on a stdlib logger; control flow is already asserted elsewhere. |
| **C24** log message string casing / `XX…XX` padding tweaks | `read_plates` | 4, 5, 6 | 3 | EQUIVALENT | Lowercase / UPPERCASE / `XX…XX` variants of the no-model warning at line 297. Pure message text; the `return []` is asserted by `test_read_plates_no_model`. |
| **C25** `asyncio.to_thread` delegate/arguments clobbered | `read_single_plate` | 7, 8, 9, 10, 11, 12 | **6** | **TEST-GAP** | Exact mirror of C18 at lines 395-399 (`_run_ocr_sync`/`ocr_model`/`plate_image` → `None` or removed). Same root cause. |
| **C26** `raw_text` field flattened / kwarg dropped | `read_single_plate` | 20, 23 | **2** | **TEST-GAP** | `raw_text=None` (line 410) / kwarg removed. `test_read_single_plate_success` (343) asserts `.text` and `.confidence` only. `raw_text` is documented (line 45) as the pre-cleaning OCR output — precisely what a reviewer needs to judge a misread plate. |
| **C27** `exc_info=True` dropped on the failure log | `read_single_plate` | 26, 28, 29 | **3** | **TEST-GAP** | Line 415. `test_read_single_plate_handles_exception` (391) asserts `result is None` — which every one of these mutants still returns. No `caplog`. |
| **C28** `min_confidence` threshold `<` → `<=` | `read_single_plate` | 15 | **1** | **TEST-GAP** | Line 401, the same boundary as C21 at the single-plate entry point. `test_read_single_plate_low_confidence` (374) uses 0.3 vs 0.5 — never the exact threshold. |
| **C29** log message → `None` | `read_single_plate` | 2, 25 | 2 | LOW-VALUE | `Logger.warning(None)` at 391, message-only clobber at 415. No raise, no control-flow change. |
| **C30** log message string casing / padding tweaks | `read_single_plate` | 3, 4, 5 | 3 | EQUIVALENT | `XX…XX` / lowercase / UPPERCASE variants of "No OCR model provided". |
| **C31** minimum-plate-length boundary mutated | `clean_plate_text` | 10, 11 | **2** | **TEST-GAP** | Line 82: `< 2` → `<= 2` and → `< 3` both reject every 2-character plate. `test_clean_plate_text_returns_none_for_short` (84) probes only `"A"`, `""`, `"   "` — lengths 0 and 1, strictly **below** the boundary, where both mutants look identical to the original. Real 2-char state plates silently vanish from results. |
| **C32** color-space normalization dropped (`convert("RGB")` → `convert(None)`) | `_load_image_sync`, `_find_image_for_plate` | `__load_image_sync__1`, `__find_image_for_plate__5` | 2 | EQUIVALENT | Verified `convert(None)` returns the image unconverted. Both covering tests build fixtures by saving an **RGB** image (JPEG → reloads as `RGB`), so the unconverted result is already RGB and `assert result.mode == "RGB"` passes with no difference — identical on every input this module's JPEG snapshots produce. Flagged for revisit if captures ever yield PNG/RGBA or grayscale (verified: `convert(None)` yields `L` / `RGBA` there). |

**Sum check:** crop 8+4+1+1+1+1 = 16 · `_run_ocr_sync` 4+3+5+1+1+1+1+1+1+1 = 19 · `read_plates` 6+6+4+1+1+3+8+3 = 32 · `read_single_plate` 6+2+3+1+2+3 = 17 · `clean_plate_text` 2 · image loading 2 → **88** ✔
**By class:** TEST-GAP 8+4+1+6+6+4+1+3+6+2+3+1+2 = **47** · LOW-VALUE 1+1+1+3+5+1+1+1+8+2 = **24** · EQUIVALENT 4+1+1+1+1+1+3+3+2 = **17** → 47+24+17 = **88** ✔

---

## Drafted kill-tests

Six tests, all **UNVERIFIED — not yet run red/green** (no test execution was permitted in this triage).
Append to `backend/tests/unit/services/test_ocr_service.py`; they reuse the file's existing `temp_test_image` / `sample_plate_detections` / `mock_paddleocr` fixtures (lines 22-62) and its `patch("backend.services.ocr_service.asyncio.to_thread", autospec=True)` idiom.

TDD procedure (identical for all six): *add the test, run it against the mutant copy to watch the new assertion fail, run it against the original `backend/services/ocr_service.py` to watch it pass, then re-sweep the module to confirm the cluster's keys flip survived → killed.*

### T1 — pins padded crop geometry → kills **C01** (8) and **C03** (1)

```python
# // UNVERIFIED - not yet run red/green
def test_crop_plate_region_pads_by_the_dominant_axis_of_the_box():
    """Padding must be derived from each axis of the box and applied.

    prepare_bbox_for_crop already fixes inverted coordinates and clamps to
    bounds, so abs(x2 - x1) / abs(y2 - y1) here exist solely to size the
    pixel padding passed through as max(pad_w, pad_h). Asserting a loose
    size lets a mutant inflate or zero that padding; the geometry has to be
    exact, and both axes have to be pinned.
    """
    image = Image.new("RGB", (1000, 800), color=(255, 0, 0))

    # w=200, h=50 -> pad_w=int(200*0.05)=10, pad_h=int(50*0.05)=2
    # max(10, 2) = 10px of padding -> crop box (90, 190, 310, 260)
    wide = _crop_plate_region(image, (100.0, 200.0, 300.0, 250.0), padding=0.05)
    assert wide is not None
    assert wide.size == (220, 70)

    # Tall box: pad_w=2, pad_h=10. Shrinking only the *width* padding also
    # changes this result, so the second axis is pinned too.
    tall = _crop_plate_region(image, (100.0, 200.0, 150.0, 400.0), padding=0.05)
    assert tall is not None
    assert tall.size == (70, 220)

    # Padding is proportional, not a constant: doubling the ratio doubles the
    # expansion on the dominant axis.
    roomy = _crop_plate_region(image, (100.0, 200.0, 300.0, 250.0), padding=0.10)
    assert roomy is not None
    assert roomy.size == (240, 90)
```

*Why it kills:* the original geometry `(90,190,310,260)` → `220×70` was produced by calling the real `prepare_bbox_for_crop` in the project venv. #5 → `240×90`, #8 → `244×94`, #10 → `204×54`, #18 (tall box) → `54×204`, #15/#23 change the 1-px path pinned by the third block, #16/#24 add a stray pixel. C03 drops `padding=` → `200×50`. (C04 cannot be killed: EQUIVALENT.)

### T2 — pins every `PlateText` field `read_plates` populates → kills **C17** (6) and **C21** (1)

```python
# // UNVERIFIED - not yet run red/green
@pytest.mark.asyncio
async def test_read_plates_populates_full_plate_text_provenance(
    temp_test_image, sample_plate_detections, mock_paddleocr
):
    """Each PlateText must carry raw text, its detection id and its bbox.

    Downstream plate matching joins on plate_detection_id and reviewers triage
    misreads from raw_text, so these are contracts rather than decoration. The
    second detection's id also proves the loop ran to completion. Confidence
    sits exactly on min_confidence: the threshold is a minimum, inclusive.
    """
    images = {temp_test_image: Image.open(temp_test_image).convert("RGB")}

    with patch("backend.services.ocr_service.asyncio.to_thread", autospec=True) as mock_to_thread:
        mock_to_thread.return_value = ("ABC 123", 0.5)  # exactly on threshold

        results = await read_plates(
            ocr_model=mock_paddleocr,
            plate_detections=sample_plate_detections,
            images=images,
            min_confidence=0.5,
        )

    assert len(results) == 2
    first, second = results
    assert first.text == "ABC123"
    assert first.raw_text == "ABC 123"
    assert first.plate_detection_id == 1
    assert first.bbox == (100.0, 200.0, 300.0, 250.0)
    assert first.confidence == 0.5
    assert second.plate_detection_id == 2
    assert second.bbox == (500.0, 300.0, 700.0, 350.0)
```

*Why it kills:* #46/#48/#49 null `raw_text`/`plate_detection_id`/`bbox`; #51/#53/#54 drop the kwargs so those fields take their dataclass defaults of `None` — either way the provenance assertions fail. C21's `<=` rejects a result whose confidence *equals* `min_confidence`, so `len(results) == 2` fails.

### T3 — pins the thread-pool dispatch → kills **C18** (6) and **C25** (6)

```python
# // UNVERIFIED - not yet run red/green
@pytest.mark.asyncio
async def test_ocr_runs_on_the_crop_via_the_thread_pool(
    temp_test_image, sample_plate_detections, mock_paddleocr
):
    """OCR must be dispatched as to_thread(_run_ocr_sync, model, crop).

    The module's stated design is that inference leaves the event loop.
    Patching asyncio.to_thread without inspecting the call lets a mutant hand
    the pool a None callable or silently drop the model or the crop.
    """
    images = {temp_test_image: Image.open(temp_test_image).convert("RGB")}
    plate_image = Image.new("RGB", (200, 50), color=(255, 255, 255))

    with patch("backend.services.ocr_service.asyncio.to_thread", autospec=True) as mock_to_thread:
        mock_to_thread.return_value = ("ABC 123", 0.95)

        results = await read_plates(
            ocr_model=mock_paddleocr,
            plate_detections=sample_plate_detections,
            images=images,
        )
        assert mock_to_thread.call_count == 2
        for call in mock_to_thread.call_args_list:
            func, model, crop = call.args
            assert func is _run_ocr_sync
            assert model is mock_paddleocr
            assert isinstance(crop, Image.Image)
            assert crop.size[0] > 0 and crop.size[1] > 0

        single = await read_single_plate(
            ocr_model=mock_paddleocr, plate_image=plate_image
        )

    assert single is not None
    func, model, passed_image = mock_to_thread.call_args.args
    assert func is _run_ocr_sync
    assert model is mock_paddleocr
    assert passed_image is plate_image
```

*Why it kills:* every `None` substitution (#28/#29/#30, #7/#8/#9) trips an identity assertion; every argument removal (#31/#32/#33, #10/#11/#12) trips the 3-tuple unpack with a `ValueError`.

### T4 — pins the multi-detection skip contract → kills **C19** (4)

```python
# // UNVERIFIED - not yet run red/green
@pytest.mark.asyncio
async def test_read_plates_keeps_going_after_a_skipped_plate(temp_test_image):
    """A skipped plate must not abort the rest of the batch.

    read_plates is documented as best-effort: errors are logged, not raised,
    "allowing the pipeline to continue processing other plates". A continue
    turned into break is indistinguishable from a skip when every detection
    shares one canned OCR answer, so this fixture is deliberately mixed.
    """
    detections = [
        PlateDetection(bbox=(100.0, 200.0, 300.0, 250.0), confidence=0.9, vehicle_detection_id=1),
        PlateDetection(bbox=(0.0, 0.0, 0.0, 0.0), confidence=0.9, vehicle_detection_id=2),  # invalid -> no crop
        PlateDetection(bbox=(500.0, 300.0, 700.0, 350.0), confidence=0.9, vehicle_detection_id=3),
    ]
    images = {temp_test_image: Image.open(temp_test_image).convert("RGB")}

    with patch("backend.services.ocr_service.asyncio.to_thread", autospec=True) as mock_to_thread:
        mock_to_thread.side_effect = [
            ("ABC123", 0.9),  # detection 1 accepted
            ("DEF456", 0.9),  # detection 3 accepted
        ]
        results = await read_plates(
            ocr_model=MagicMock(), plate_detections=detections, images=images
        )

    assert [r.plate_detection_id for r in results] == [1, 3]
```

*Why it kills:* a `break` on the below-threshold / too-short / invalid-crop / exception paths stops at detection 2 and yields `[1]` (or `[]`) instead of `[1, 3]`. `mock_paddleocr` is not used here because `_crop_plate_region` must actually reject detection 2's degenerate bbox — the invalid-crop variant (#26) is killed by the crop returning `None` for `(0,0,0,0)`, and #38/#43/#61 by making detection 2's canned answer short or by raising mid-list if the invalid bbox is rejected earlier; keep the `side_effect` list at two entries so any mutant that *reaches* detection 2 consumes a value and desynchronises, failing the id-list assertion.

### T5 — pins the 2-character plate boundary → kills **C31** (2)

```python
# // UNVERIFIED - not yet run red/green
def test_clean_plate_text_accepts_two_character_plates():
    """The < 2 guard is an exclusive floor: exactly two chars must survive.

    Existing coverage probes only length 0 and 1, strictly below the boundary,
    so both `<= 2` and `< 3` pass while silently discarding every
    two-character plate the OCR reads.
    """
    assert clean_plate_text("AB") == "AB"
    assert clean_plate_text("a1") == "A1"
    assert clean_plate_text("A B") == "AB"  # separators stripped, then length 2
    assert clean_plate_text("A") is None    # still rejected below the floor
```

*Why it kills:* both `<= 2` and `< 3` return `None` for `"AB"`. The final line keeps the original intent (length 1 rejected) pinned, so the test cannot be satisfied by loosening the guard outright.

### T6 — pins the swallowed-failure traceback → kills **C22** (3) and **C27** (3)

```python
# // UNVERIFIED - not yet run red/green
@pytest.mark.asyncio
async def test_swallowed_ocr_failures_keep_their_traceback(temp_test_image, caplog):
    """A swallowed per-plate failure must keep its traceback.

    This module never raises, so the log record is the only observable of a
    failed plate; exc_info dropped means the failure is undebuggable.
    """
    detections = [
        PlateDetection(bbox=(100.0, 200.0, 300.0, 250.0), confidence=0.95, vehicle_detection_id=1)
    ]
    images = {temp_test_image: Image.open(temp_test_image).convert("RGB")}

    with caplog.at_level("WARNING", logger="backend.services.ocr_service"):
        with patch("backend.services.ocr_service.asyncio.to_thread", autospec=True) as mock_to_thread:
            mock_to_thread.side_effect = RuntimeError("OCR crashed")
            results = await read_plates(
                ocr_model=MagicMock(), plate_detections=detections, images=images
            )

    assert results == []
    record = next(r for r in caplog.records if "Failed to OCR plate" in r.getMessage())
    assert record.exc_info is not None
    assert record.exc_info[0] is RuntimeError

    plate_image = Image.new("RGB", (200, 50), color=(255, 255, 255))
    with caplog.at_level("WARNING", logger="backend.services.ocr_service"):
        with patch("backend.services.ocr_service.asyncio.to_thread", autospec=True) as mock_to_thread:
            mock_to_thread.side_effect = RuntimeError("single crashed")
            assert await read_single_plate(
                ocr_model=MagicMock(), plate_image=plate_image
            ) is None

    single_record = next(r for r in caplog.records if "Single plate OCR failed" in r.getMessage())
    assert single_record.exc_info is not None
```

*Why it kills:* #57/#59/#60 and the single-plate twins #26/#28/#29 all leave `record.exc_info` as `None`, while `results == []` and `result is None` still hold — which is exactly why the current suite misses them.

### Small extension for C11 (no new test needed)

`test_run_ocr_sync_malformed_line_structure` (test file line 546) needs a **second, mixed** fixture rather than a new test — add:

```python
# // UNVERIFIED - not yet run red/green
def test_run_ocr_sync_skips_malformed_line_but_keeps_the_rest():
    """One malformed line must not cost the whole plate (covers the and-guard)."""
    model = MagicMock()
    model.ocr.return_value = [
        [
            [[[0, 0], [100, 0], [100, 25], [0, 25]]],            # malformed: no tuple
            [[[0, 25], [100, 25], [100, 50], [0, 50]], ("ABC", 0.9)],
        ]
    ]
    text, confidence = _run_ocr_sync(model, Image.new("RGB", (200, 50)))
    assert text == "ABC"
    assert confidence == 0.9
```

The `or` mutant raises `IndexError` on the first line and loses the good one, returning `(None, 0.0)`.

---

## Notes for the fix lane

- **Highest leverage, one file:** C01, C17, C18/C25 and C19 hold **24 of the 47** TEST-GAP survivors and are closed by T1-T4 entirely inside `backend/tests/unit/services/test_ocr_service.py`.
- **Two structural blind spots, not eight missing tests:** (a) no assertion anywhere pins a *padded* crop geometry — every existing crop test asserts a loose inequality or passes `padding=0.0`, which makes the padding code invisible by construction; (b) zero `caplog` usage combined with `autospec`-patched `asyncio.to_thread` whose arguments are never inspected. (b) is a **pattern** problem: any module whose tests stub `to_thread` this way carries the identical 6-mutant hole, so the fix should be a convention change (`assert mock.call_args.args[0] is _run_ocr_sync`) applied repo-wide, not just here.
- **C32 (`convert(None)`) is the one EQUIVALENT worth re-testing** if captures ever yield non-RGB files: verified that `convert(None)` returns `L` for a grayscale JPEG and `RGBA` for a PNG, which would hand PaddleOCR a 2-D or 4-channel array. Today's fixtures cannot see the difference.
- **Do not chase** C09, C13, C15 (7 mutants): each needs PaddleOCR to emit an empty or 1-element text tuple, a payload the library never produces. C10 and C14 are dead branches (`if confidences` is always true when reached). C20 is unobservable because image lookup is batch-wide. C04 is literally the helper's own default value.
