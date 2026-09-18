# WP4.4 Triage Dossier — backend/services/face_detector.py

Date: 2026-09-18 · Wave: gen-2 triage (UNVERIFIED — no tests run per live-mutation-run constraint)

## Inputs

- Verdicts: `mutants/backend/services/face_detector.py.meta` — 241 keys, **50 SURVIVED (exit_code 0)**, 191 killed, 0 unchecked.
- Diffs: `uv run mutmut show <key>` for all 50 (saved at `/tmp/wp25/wp44-triage/fd_survivor_diffs.txt`).
- Source: `backend/services/face_detector.py` (375 lines).
- Covering tests (from `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`):
  - `backend/tests/unit/services/test_face_detector.py` — covers `_get_head_region`, `_crop_bbox_with_padding`, `_convert_crop_bbox_to_original`, `_load_image_sync`, `_run_face_detection_sync`, `detect_faces`, `is_person_class` (ALL surviving mutants; the only test file needed).
  - Indirect consumers only (not the asserter of these lines): `backend/tests/unit/services/test_enrichment_pipeline.py`, `backend/tests/unit/services/test_ai_services.py`.

## Why the tests miss so much (root causes)

1. **No bbox-value assertions.** `test_face_convert_crop_bbox_to_original` (test_face_detector.py:159) asserts only length/float/ordering; `test_convert_crop_bbox_clamps_to_bounds` (:178) asserts only inequalities. No test anywhere pins the *numeric* bbox a face detection gets. Every arithmetic mutation inside `_convert_crop_bbox_to_original` slips through.
2. **No call-argument assertions on the inference call.** `test_detect_faces_uses_thread_pool` (:525) does `mock_to_thread.assert_called_once()` with zero argument inspection; `_run_face_detection_sync` tests pass a plain `MagicMock` model, so any `model.predict(...)` kwarg/arg mutation (None kwargs, dropped args, replaced image) is absorbed.
3. **No log assertions (no `caplog` anywhere in the file).** All message-text mutants survive; most are also semantically inert.
4. **Weak clamp tests.** `max(0,·)` → `max(1,·)` only changes output in the zero-clamped branch at coordinate 0; no test crops/converts a bbox touching x=0/y=0, and the clamp tests assert `<= size`, not exact geometry.
5. **Single-detection negative tests.** `test_detect_faces_missing_image` (:288) uses ONE detection, so `continue`→`break` is indistinguishable.
6. **Defaults never exercised without overrides.** Every `detect_faces` test passes `confidence_threshold=0.3` explicitly or never checks what was forwarded, so default-value mutations (`0.3`→`1.3`, `0.2`→`1.2`) and dropped-forwarding-arg mutants are invisible.

## Cluster table (counts sum to 50)

| # | Pattern (function · mutation kind) | Count | Class | Example keys (≤3) | Kill path |
|---|---|---|---|---|---|
| 1 | `detect_faces`/`_run_face_detection_sync` log text mutations (warning/debug/info msgs → None/case/XX-wrapped, `*1000`→`/1000`,`*1001`) | 10 | EQUIVALENT | `x_detect_faces__mutmut_5`, `x_detect_faces__mutmut_89`, `x__run_face_detection_sync__mutmut_20` | none needed — pure log/message payload, no control flow |
| 2 | `_run_face_detection_sync`: `model.predict(...)` arg/kwarg mutations absorbed by plain-MagicMock model (image_crop→None/dropped, verbose False→None/True/dropped, conf dropped) | 7 | TEST-GAP | `x__run_face_detection_sync__mutmut_2`, `_mutmut_4`, `_mutmut_8` | Draft T2 |
| 3 | `detect_faces` call-site arg drop/replace, mock-absorbed (crop→None/dropped at to_thread, head_ratio/padding/conf dropped in forwarded calls, `original_bbox=None`, `bbox=None`, padding dropped in convert call) | 9 | TEST-GAP | `x_detect_faces__mutmut_33`, `_mutmut_46`, `_mutmut_58` | Drafts T4 + T6 |
| 4 | `max(0,·)` → `max(1,·)` clamp-floor bump (crop: x1,y1; convert: crop_x1,crop_y1 and 4 final clamps) | 8 | LOW-VALUE | `x__crop_bbox_with_padding__mutmut_14`, `x__convert_crop_bbox_to_original__mutmut_15`, `...__mutmut_49` | see note; low priority |
| 5 | `_convert_crop_bbox_to_original` pad-arithmetic operator/sign flips (`int(w*padding)`→`int(w/padding)`, `x-pad`→`x+pad`) | 4 | TEST-GAP | `x__convert_crop_bbox_to_original__mutmut_6`, `_mutmut_9`, `_mutmut_16` | Draft T1 |
| 6 | `_convert_crop_bbox_to_original` normalized-bbox index/operand mutations (`*crop_w`→`/crop_w`, x1 reads y's index, x2 reads y2's index) | 4 | TEST-GAP | `x__convert_crop_bbox_to_original__mutmut_25`, `_mutmut_26`, `_mutmut_32` | Draft T1 |
| 7 | `detect_faces` default kwarg values (`confidence_threshold 0.3→1.3`, `padding 0.2→1.2`) never observed because no test both relies on defaults and inspects what was forwarded | 2 | TEST-GAP | `x_detect_faces__mutmut_1`, `x_detect_faces__mutmut_2` | Draft T4 |
| 8 | `_run_face_detection_sync` guard relaxation (`and`→`or`, `>0`→`>=0` in `if predictions and len(predictions)>0`) | 2 | EQUIVALENT | `x__run_face_detection_sync__mutmut_10`, `_mutmut_11` | none — `len(None)`/`len([])` makes both branches equal on all reachable inputs |
| 9 | `detect_faces` missing-image `continue`→`break` (aborts remaining person detections after one bad file) | 1 | TEST-GAP | `x_detect_faces__mutmut_23` | Draft T3 |
| 10 | `detect_faces` `images.copy() if images else {}` → `... if (images) and False else {}` (caller's image cache silently discarded) | 1 | TEST-GAP | `x_detect_faces__mutmut_11` | Draft T5 |
| 11 | `detect_faces` `inference_duration = perf_counter() - start_time` → `+ start_time` (duration metric gets an epoch-scale value instead of elapsed) | 1 | TEST-GAP | `x_detect_faces__mutmut_53` | Draft T4 (metrics spy asserts elapsed < 5s; existing test only checks `>= 0`, test_face_detector.py:596) |
| 12 | `_load_image_sync` `.convert("RGB")` → `.convert(None)` (output color mode becomes source-dependent; tests supply RGB fixtures so it's never observable) | 1 | LOW-VALUE | `x__load_image_sync__mutmut_1` | opportunistic only: feed a grayscale JPEG and assert `result.mode == "RGB"` (kills 1 mutant for ~3 lines; not drafted — priority is coordinate/inference correctness) |

Totals: **TEST-GAP 29** (clusters 2,3,5,6,7,9,10,11) · **EQUIVALENT 12** (clusters 1,8) · **LOW-VALUE 9** (clusters 4,12). 10+7+9+8+4+4+2+2+1+1+1+1 = 50 ✓

### Cluster notes

- **Cluster 1 (EQUIVALENT):** `logger.warning(None)` / re-cased strings do not change the returned value or control flow; no test asserts log output, and asserting it would have no product value. Left unkilled by choice.
- **Cluster 4 (LOW-VALUE):** the ONLY observable delta is a bbox pinned at image coordinate 0 (e.g. bbox_x=0 with padding, clamped crop edge at 0). On a 1920×1080 security cam a face bbox never lands on column/row 0, and a 1-pixel clamp floor is not behavior anyone should have to assert. A cheap opportunistic kill exists (exact-geometry asserts with a bbox touching the image origin) but is not drafted — priority goes to clusters 2/3/5/6.
- **Cluster 8 (EQUIVALENT) proof:** `or`-mutant: when `predictions` is falsy (`None`/`[]`), `len()` raises and the existing `except Exception` returns `[]` — identical to original; when truthy, both operands agree. `>=0` is always true whenever `predictions` is truthy. No input separates them.
- **Suspicious survivors (cluster 3: `_mutmut_58`, `_mutmut_68`, `_mutmut_70`):** setting `original_bbox=None`/`bbox=None` should explode `test_detect_faces_success` via the `except Exception: continue` path (empty list vs `len==1`). Their survival suggests the exception path was never observed as a failure under the run harness (possibly the SetupGuard-cache poisoning noted in project memory) — flag to the orchestrator. Draft T6 kills all three regardless of cause (explicit bbox-type + exact-value asserts).

## Drafted tests — backend/tests/unit/services/test_face_detector.py

All six are **UNVERIFIED — not yet run red/green** (mutation run owns the machine). TDD procedure for each: apply the cluster's mutant → the named assertion fails; original code → passes. Append after the existing metrics section; no new imports beyond `pytest`, `unittest.mock.patch`, `PIL.Image` already used by the file (`pytest.approx` is part of pytest).

### T1 — exact coordinate conversion (kills clusters 5 + 6, 8 mutants)

```python
def test_convert_crop_bbox_to_original_exact_coordinates():
    """Pin the exact bbox math: padding origin offset + normalized scaling.

    Existing test only checks length/float/ordering, so pad sign flips
    (* vs /, - vs +) and xyxyn index swaps all survived.
    """
    crop_bbox_norm = [0.2, 0.3, 0.6, 0.8]
    original_bbox = (100, 100, 200, 200)  # head bbox
    crop_size = (280, 280)
    image_size = (1000, 800)
    padding = 0.2

    result = _convert_crop_bbox_to_original(
        crop_bbox_norm, original_bbox, crop_size, image_size, padding
    )

    # pad = int(200 * 0.2) = 40 -> crop origin (60, 60)
    # x1 = 60 + 0.2*280 = 116 | y1 = 60 + 0.3*280 = 144
    # x2 = 60 + 0.6*280 = 228 | y2 = 60 + 0.8*280 = 284
    assert result == pytest.approx((116.0, 144.0, 228.0, 284.0), abs=1e-6)
```

Kills: `x__convert_crop_bbox_to_original__mutmut_6,9,16,23` (origin moves to 0 or 140) and `_mutmut_25,26,28,32` (scaling/index broken; distinct norm values [0.2,0.3,0.6,0.8] make x↔y index swaps observable).

### T2 — inference call arguments (kills cluster 2, 7 mutants)

```python
def test_run_face_detection_sync_passes_crop_and_threshold_to_predict():
    """The crop image and conf threshold must reach model.predict as given.

    Existing tests never inspect model.predict call args, so a MagicMock
    absorbed: image_crop->None/dropped, verbose->None/True/dropped,
    conf->None/dropped.
    """
    model = MagicMock()
    mock_box = MagicMock()
    mock_box.xyxyn = [MagicMock()]
    mock_box.xyxyn[0].tolist.return_value = [0.1, 0.1, 0.5, 0.5]
    mock_box.conf = [0.7]
    mock_result = MagicMock()
    mock_result.boxes = [mock_box]
    model.predict.return_value = [mock_result]

    image = Image.new("RGB", (200, 200), color=(50, 50, 50))

    _run_face_detection_sync(model, image, confidence_threshold=0.45)

    call = model.predict.call_args
    assert call is not None, "model.predict was never called"
    # positionals: the exact crop image (not None, not dropped)
    assert call[0][0] is image
    # keywords: verbose pinned to False (identity check kills None and True)
    assert call.kwargs["verbose"] is False
    # threshold forwarded verbatim
    assert call.kwargs["conf"] == 0.45
```

Kills: `x__run_face_detection_sync__mutmut_2,3,4,5,6,7,8` (mutated/missing positional → `call[0][0] is image` fails/IndexError; missing kwarg → KeyError; `verbose=None`/`True` → identity fails; `conf` missing/wrong → fails).

### T3 — missing image must not abort remaining detections (kills cluster 9)

```python
@pytest.mark.asyncio
async def test_detect_faces_continues_past_missing_image(temp_test_image, mock_yolo_face_model):
    """One missing file must skip that person, not stop the whole batch.

    Existing missing-image test uses a single detection, so
    continue->break was indistinguishable.
    """
    detections = [
        PersonDetection(
            id=1, bbox_x=100, bbox_y=100, bbox_width=200, bbox_height=500,
            file_path="/nonexistent/wp44-missing-image.jpg",
        ),
        PersonDetection(
            id=2, bbox_x=500, bbox_y=200, bbox_width=180, bbox_height=450,
            file_path=temp_test_image,
        ),
    ]

    faces = await detect_faces(
        model=mock_yolo_face_model,
        person_detections=detections,
    )

    assert len(faces) == 1, "missing image aborted the whole detection batch (break vs continue)"
    assert faces[0].person_detection_id == 2
```

Kills: `x_detect_faces__mutmut_23` (break → `faces == []`).

### T4 — default kwargs + forwarded call shape + sane duration metric (kills clusters 7, 11, and most of 3: mutmut_33,40,46,47,50,51)

```python
@pytest.mark.asyncio
async def test_detect_faces_forwards_defaults_and_crop_to_inference(temp_test_image, mock_yolo_face_model):
    """Defaults (conf 0.3, padding 0.2, head_ratio HEAD_REGION_RATIO) must reach
    the helpers/inference, and the crop object must be the inference input.

    No existing test both relies on defaults and inspects what got forwarded,
    so default-value bumps and dropped/None'd forwarded args all survived.
    """
    detections = [
        PersonDetection(
            id=1, bbox_x=100, bbox_y=100, bbox_width=200, bbox_height=500,
            file_path=temp_test_image,
        )
    ]

    with (
        patch("backend.services.face_detector._get_head_region", autospec=True, wraps=_get_head_region) as head_spy,
        patch("backend.services.face_detector._crop_bbox_with_padding", autospec=True, wraps=_crop_bbox_with_padding) as crop_spy,
        patch("asyncio.to_thread", autospec=True) as mock_to_thread,
        patch("backend.services.face_detector.observe_face_embedding_duration", autospec=True) as mock_duration,
    ):
        mock_to_thread.return_value = [([0.2, 0.3, 0.6, 0.8], 0.9)]

        faces = await detect_faces(
            model=mock_yolo_face_model,
            person_detections=detections,
            # no confidence_threshold / head_ratio / padding -> defaults
        )

        assert len(faces) == 1

        # head region got the explicit head_ratio argument
        assert head_spy.call_args[0][1] == HEAD_REGION_RATIO  # kills dropped arg (len==1 -> IndexError)

        # crop got the explicit padding argument == default 0.2
        assert crop_spy.call_args[0][2] == pytest.approx(0.2)  # kills drop and 0.2->1.2 default

        # inference: positional args (func, model, CROP, threshold)
        thread_args = mock_to_thread.call_args[0]
        assert isinstance(thread_args[2], Image.Image), "crop image not forwarded to inference"
        assert thread_args[3] == pytest.approx(0.3), "default confidence threshold not forwarded"

        # duration metric is an elapsed time, not perf_counter() + start_time
        assert 0.0 <= mock_duration.call_args[0][1] < 5.0
```

Kills: `x_detect_faces__mutmut_1` (1.3≠0.3), `_mutmut_2` (1.2≠0.2), `_mutmut_33` (positional count), `_mutmut_40`, `_mutmut_46` (None fails isinstance), `_mutmut_47` (None≠0.3), `_mutmut_50` (arg shift → [2] is float), `_mutmut_51` (arg count → IndexError), `_mutmut_53` (epoch-magnitude duration fails `< 5.0`).

### T5 — caller-supplied image cache is honored (kills cluster 10)

```python
@pytest.mark.asyncio
async def test_detect_faces_uses_supplied_images_cache_without_disk_load(temp_test_image, mock_yolo_face_model):
    """Pre-loaded images must be taken from the cache; the cache must never be
    silently discarded. (mutmut_11 rewrote the images.copy() condition to
    'and False', silently dropping the caller's cache.)
    """
    cached_image = Image.open(temp_test_image).convert("RGB")
    images = {temp_test_image: cached_image}

    detections = [
        PersonDetection(
            id=1, bbox_x=100, bbox_y=100, bbox_width=200, bbox_height=500,
            file_path=temp_test_image,
        )
    ]

    with (
        # Make disk access impossible: if the cache were ignored, the
        # non-loadable "disk" would yield zero faces.
        patch("backend.services.face_detector.Path", autospec=True) as mock_path,
        patch("backend.services.face_detector._load_image_sync", autospec=True) as mock_load,
    ):
        mock_path.return_value.exists.return_value = False

        faces = await detect_faces(
            model=mock_yolo_face_model,
            person_detections=detections,
            images=images,
        )

        assert len(faces) == 1, "image cache was discarded and re-load attempted"
        mock_load.assert_not_called()
```

Kills: `x_detect_faces__mutmut_11` (cache dropped → path "missing" → `faces == []`).

### T6 — exact face bbox in detect_faces output (kills cluster 3 bbox members: mutmut_58,68,70)

```python
@pytest.mark.asyncio
async def test_detect_faces_bbox_exact_geometry(temp_test_image, mock_yolo_face_model):
    """FaceDetection.bbox must be a 4-tuple of finite floats at exactly the
    recomputed coordinates (with NON-default padding, so a dropped padding
    argument in the convert call is observable).

    No existing test asserts bbox values, so original_bbox=None / bbox=None /
    padding-dropped mutants survived.
    """
    detections = [
        PersonDetection(
            id=1, bbox_x=100, bbox_y=100, bbox_width=200, bbox_height=500,
            file_path=temp_test_image,
        )
    ]

    faces = await detect_faces(
        model=mock_yolo_face_model,          # norm box [0.2, 0.2, 0.8, 0.8]
        person_detections=detections,
        padding=0.3,                        # pad = int(200*0.3) = 60
    )

    assert len(faces) == 1
    bbox = faces[0].bbox
    assert isinstance(bbox, tuple) and len(bbox) == 4, f"bbox must be a 4-tuple, got {bbox!r}"
    assert all(isinstance(v, float) for v in bbox)

    # head = (100, 100, 200, 200); padded crop origin (40, 40), size (320, 320)
    # x1 = 40 + 0.2*320 = 104 ; x2 = 40 + 0.8*320 = 296  (same for y)
    assert bbox == pytest.approx((104.0, 104.0, 296.0, 296.0), abs=1e-6)
```

Kills: `x_detect_faces__mutmut_58` and `_mutmut_70` (`bbox=None` → isinstance fails), `_mutmut_68` (padding dropped in convert call → default 0.2 → (130,130,270,270) ≠ expected).

## Drafts coverage

| Draft | Kills | Count |
|---|---|---|
| T1 | clusters 5 + 6 | 8 |
| T2 | cluster 2 | 7 |
| T3 | cluster 9 | 1 |
| T4 | clusters 7 + 11 + (3: 33,40,46,47,50,51) | 9 |
| T5 | cluster 10 | 1 |
| T6 | cluster 3 (58,68,70) | 3 |
| **Total killable by drafts** | | **29 / 50** |

Remaining 21: 12 EQUIVALENT (clusters 1, 8 — not worth killing) + 9 LOW-VALUE (cluster 4 origin-clamp bump, cluster 12 RGB-mode convert — opportunistic tests only).

## Files

- Covering test file (draft target): `backend/tests/unit/services/test_face_detector.py`
- Module under test: `backend/services/face_detector.py`
- Raw per-mutant diffs: `/tmp/wp25/wp44-triage/fd_survivor_diffs.txt`
