# WP4.4 triage dossier — backend/services/plate_detector.py

Source: run6 FINAL meta (`mutants/backend/services/plate_detector.py.meta`).
205 mutants generated, 159 killed, **46 SURVIVED**. Diffs extracted by
AST-segment normalisation against the mutated copy
(`mutants/backend/services/plate_detector.py`, `x_<fn>__mutmut_N` variants) —
every key mapped to exactly one cluster, zero unmapped.
Covering tests: **backend/tests/unit/services/test_plate_detector.py** (483
lines; crop 78–113, convert 116–156, sync-detect 159–194, detect_plates
197–483; fixtures 24–75). `is_vehicle_class` mutants all killed (module
score 77.6).

**Tally: 46 = 32 TEST-GAP / 10 EQUIVALENT / 4 LOW-VALUE. 8 drafted tests (all
UNVERIFIED — not run red/green; a live mutation run owns this machine).**

## Cluster table

| # | Cluster (pattern) | Keys | n | Class | Killed by |
|---|---|---|--:|---|---|
| C1 | `_convert_crop_bbox_to_original`: padding op `*`→`/` (`pad_w/pad_h = int(orig * padding)` → `/`) | 6, 9 | 2 | TEST-GAP | T1 |
| C2 | `_convert…`: crop-origin padding flip `- pad`→`+ pad` (crop starts inside the vehicle) | 16, 23 | 2 | TEST-GAP | T1 |
| C3 | `_convert…`: normalized→pixel op `* crop_w/h`→`/ crop_w/h` | 25, 28 | 2 | TEST-GAP | T1 |
| C4 | `_convert…`: normalized-index swap (x1 reads idx1, x2 reads idx3) | 26, 32 | 2 | TEST-GAP | T1 |
| C5 | `_convert…`: origin-offset add→subtract (`crop_x1 + x1_crop`→`- x1_crop`) | 37, 39 | 2 | TEST-GAP | T1 |
| C6 | `_convert…`: crop-origin clamp floor `max(0,…)`→`max(1,…)` (only fires when padding clamps the origin to 0) | 15, 22 | 2 | TEST-GAP | T2 |
| C7 | `_convert…`: final clamp floor `max(0,min(…))`→`max(1,…)` on the **x1/y1** legs (fires when the plate corner sits at image edge 0) | 49, 59 | 2 | TEST-GAP | T2 |
| C8 | `_convert…`: final clamp floor→`max(1,…)` on **x2/y2** legs — distinguishable only when `min(img_w, x2_orig) < 1`, i.e. a sub-pixel/degenerate detector box; pinning 0.0 vs 1.0 for a zero-area plate is not behavior worth an assertion | 69, 79 | 2 | LOW-VALUE | — (suppress w/ record) |
| C9 | `_crop_bbox_with_padding`: clamp floor `max(0,…)`→`max(1,…)`. Verified NOT equivalent: real Pillow 12.3 shows `crop((0,0,130,106))` → size (130,106), `crop((1,0,130,106))` → (129,106) — different size AND pixels. Existing clamp test asserts only `size <= w` (line 102–103), passes | 14, 21 | 2 | TEST-GAP | T3 |
| C10 | `_load_image_sync`: `.convert("RGB")`→`.convert(None)`. Verified real: Pillow 12.3 `convert(None)` preserves native mode (L stays L) — contract "returns PIL Image in RGB" (docstring line 168) silently violated for grayscale/palette sources. Never asserted anywhere | 1 | 1 | TEST-GAP | T4 |
| C11 | `_run_plate_detection_sync`: `model.predict(...)` arg plumbing — source crop→None (2), crop arg dropped (5), `conf=` dropped (6), conf→None (4), verbose kwarg dropped (7). Under MagicMock the call still returns the mocked result, so every existing test passes; production would error→`[]` or run at the wrong threshold. Existing test (159) uses a mock but never asserts call args | 2, 4, 5, 6, 7 | 5 | TEST-GAP | T5 |
| C12 | `_run_plate_detection_sync`: `verbose=False`→None (3) / True (8). Console-chattiness only; no assertion should pin model verbosity | 3, 8 | 2 | LOW-VALUE | — |
| C13 | `_run_plate_detection_sync`: guard `predictions and len(predictions) > 0` → `or` (10) / `>= 0` (11). Provably output-equivalent: k11 — any truthy sequence has len>0; k10 — `[]`→False→`[]`, truthy→same path, `None` raises TypeError inside the try and the handler returns `[]` too, identical to original's falsy short-circuit | 10, 11 | 2 | EQUIVALENT | — |
| C14 | `detect_plates` + `_run_plate_detection_sync`: logger argument mutants (warning(None) ×3 at keys dp:3, dp:16, sync:20; message-case/wrapper text dp:4,5,6; debug/info arg→None dp:58,59). Pure log/message text | 3,4,5,6,16,58,59 (dp) + 20 (sync) | 8 | EQUIVALENT | — |

(14 clusters above + 2 below = full 46-key partition.)

| C15 | `detect_plates`: image-cache contract broken — `images.copy() if images else {}` → `if (images) and False` (9): caller's cache is always discarded, forcing disk re-reads. Existing cached-image test (line 274) survives because its cache key is an on-disk temp file, so the re-load succeeds. Also `continue`→`break` on missing image (17): one unreadable image silently drops every later vehicle; existing missing-image test (line 251) has a single detection, indistinguishable | 9, 17 | 2 | TEST-GAP | T6 |
| C16 | `detect_plates`: result-plumbing — padding default 0.1 injected into `_crop_bbox_with_padding` (29) and `_convert_crop_bbox_to_original` (50) (caller's padding ignored); computed bbox dropped entirely (40) or passed as `bbox=None` (52); `asyncio.to_thread` args broken (34 crop→None, 35 conf→None, 38 crop arg dropped, 39 conf arg dropped). The thread-pool test (line 459) patches `to_thread` with autospec but only asserts `call_count`, and no test ever asserts `plate.bbox` | 29,34,35,38,39,40,50,52 | 8 | TEST-GAP | T7, T8 |

**Sums: 2+2+2+2+2+2+2+2+2+1+5+2+2+8+2+8 = 46 ✓. TEST-GAP = C1–C7, C9–C11, C15, C16 = 14+2+5+2+8 = 32. EQUIVALENT = C13+C14 = 10. LOW-VALUE = C8+C12 = 4.**

## Why the covering tests miss these (file:line)

- `test_plate_convert_crop_bbox_to_original` (line 116–137): asserts length, float-ness and `x1<x2` inequalities — none of C1–C7 can flip those orderings under its inputs, so all arithmetic mutants live inside the asserted envelope.
- `test_convert_crop_bbox_clamps_to_image_bounds` (140–156): `assert result[0] >= 0` — passes for 1.0; and its origin never clamps to 0, so the floor mutants are invisible.
- `test_crop_bbox_with_padding_clamps_to_image_bounds` (92–103): `size[0] <= 500` — mutant sizes are smaller, pass.
- `_load_image_sync` has no direct test (never imported at lines 10–19).
- `test_run_plate_detection_sync_with_detections` (159–168): mock returns the canned box regardless of args.
- `test_detect_plates_*` (197–363): assert `len(plates)`, `vehicle_detection_id`, `confidence` — never `plate.bbox`, never the padding effect, never cache-usage when the file is absent, never multi-detection skip semantics.
- `test_detect_plates_uses_thread_pool` (459–483): `mock_to_thread.assert_called_once()` only — C16's arg mutations are unasserted.

## Drafted tests — UNVERIFIED, not yet run red/green

TDD procedure per draft: apply the cluster's mutant → the exact-value/call-args
assertion goes RED; revert to original → GREEN. All helpers/fixtures reuse the
existing file's style (MagicMock models, tmp JPEG/PNG, `pytest.mark.asyncio`).

```python
# UNVERIFIED - not yet run red/green. Target file: backend/tests/unit/services/test_plate_detector.py

# ---------- T1: kills C1 (6,9), C2 (16,23), C3 (25,28), C4 (26,32), C5 (37,39) ----------
def test_convert_crop_bbox_exact_mapping():
    """Every arithmetic path of the crop->original transform, pinned exactly.

    Geometry: crop_x1=max(0,100-20)=80, crop_y1=80 (pad=int(200*0.1)=20 both axes)
    norm (0.1,0.2,0.8,0.9) x 240 -> (24,48,192,216) -> (104,128,272,296).
    Any * <-> / flip (C1/C3), - <-> + flip (C2/C5), or index swap (C4) changes a
    leg of this tuple.
    """
    result = _convert_crop_bbox_to_original(
        [0.1, 0.2, 0.8, 0.9],
        (100, 100, 200, 200),
        (240, 240),
        (1000, 800),
        padding=0.1,
    )
    assert result == (104.0, 128.0, 272.0, 296.0)


# ---------- T2: kills C6 (15,22), C7 (49,59) ----------
def test_convert_crop_bbox_clamps_origin_and_corner_to_zero_not_one():
    """Vehicle at the image corner: padding clamps crop origin to 0 and the plate
    corner lands at 0. max(0,..) -> max(1,..) (floor mutants) shifts these to 1.

    crop_x1 = max(0, 0-10) = 0; norm[2]*120 = 120 -> x2=120 (< img_w, unclamped).
    Original: (0, 0, 120.0, 120.0). Mutants k15/k22 -> (1,1,121,121);
    k49/k59 -> (1, 1, 120.0, 120.0).
    """
    result = _convert_crop_bbox_to_original(
        [0.0, 0.0, 1.0, 1.0],
        (0, 0, 100, 100),
        (120, 120),
        (1000, 800),
        padding=0.1,
    )
    assert result == (0, 0, 120.0, 120.0)


# ---------- T3: kills C9 (14, 21) ----------
def test_crop_bbox_with_padding_exact_box_at_edge():
    """Edge-clamped crop box pinned exactly. Bbox (10,10,100,80) pad .2 ->
    pad 20x16 -> box (0,0,130,106) -> size (130,106). max(1,..) mutants yield
    (129,106) / (130,105) — verified against real Pillow crop sizing.
    """
    image = Image.new("RGB", (500, 400), color=(255, 0, 0))
    cropped = _crop_bbox_with_padding(image, (10, 10, 100, 80), padding=0.2)
    assert cropped.size == (130, 106)


# ---------- T4: kills C10 (load key 1) ----------
def test_load_image_sync_forces_rgb_mode(tmp_path):
    """Grayscale source must be converted to RGB; convert(None) keeps mode L."""
    from backend.services.plate_detector import _load_image_sync

    src = tmp_path / "gray.png"
    Image.new("L", (32, 24), color=128).save(src)
    loaded = _load_image_sync(src)
    assert loaded.mode == "RGB"


# ---------- T5: kills C11 (sync keys 2,4,5,6,7) ----------
def test_run_plate_detection_sync_forwards_predict_call_args(mock_yolo_model):
    """The crop, verbosity and confidence threshold must reach model.predict.
    Mutants pass None / drop args; mocks happily return anyway, so only the
    call args expose them.
    """
    image = Image.new("RGB", (400, 300), color=(100, 100, 100))
    _run_plate_detection_sync(mock_yolo_model, image, confidence_threshold=0.5)

    args, kwargs = mock_yolo_model.predict.call_args
    assert args == (image,)          # kills k2 (None) and k5 (dropped)
    assert kwargs["conf"] == 0.5     # kills k4 (None) and k7 (dropped)
    assert kwargs["verbose"] is False  # k6 (dropped) lands via the assert below too
    assert "conf" in kwargs and "verbose" in kwargs  # kills k6


# ---------- T6: kills C15 (dp 9, 17) ----------
@pytest.mark.asyncio
async def test_detect_plates_uses_image_cache_without_touching_disk(temp_test_image):
    """Cache hit must be honored (mutant k9 discards the cache) and a missing
    image must not abort later vehicles (mutant k17 breaks the loop).
    Detection 1 points at a path that is NOT on disk but IS in the cache —
    original serves it from cache; k9 reloads from disk, warns and skips.
    """
    cached = Image.open(temp_test_image).convert("RGB")
    detections = [
        VehicleDetection(id=1, bbox_x=100, bbox_y=100, bbox_width=200,
                         bbox_height=150, file_path="/no/such/cached.jpg"),
        VehicleDetection(id=2, bbox_x=100, bbox_y=100, bbox_width=200,
                         bbox_height=150, file_path="/does/not/exist.jpg"),
        VehicleDetection(id=3, bbox_x=100, bbox_y=100, bbox_width=200,
                         bbox_height=150, file_path=temp_test_image),
    ]
    plates = await detect_plates(
        model=mock_yolo_model_for_cache(),  # helper below
        vehicle_detections=detections,
        images={"/no/such/cached.jpg": cached},
    )
    # Detections 1 and 3 produce plates; detection 2 is skipped WITHOUT aborting
    assert [p.vehicle_detection_id for p in plates] == [1, 3]


def mock_yolo_model_for_cache():
    model = MagicMock()
    box = MagicMock()
    box.xyxyn = [MagicMock()]
    box.xyxyn[0].tolist.return_value = [0.2, 0.3, 0.8, 0.7]
    box.conf = [0.9]
    result = MagicMock()
    result.boxes = [box]
    model.predict.return_value = [result]
    return model


# ---------- T7: kills C16 keys 29, 50, 40, 52 ----------
@pytest.mark.asyncio
async def test_detect_plates_end_to_end_exact_bbox(temp_test_image):
    """Non-default padding flows through crop AND convert, and the computed
    bbox must survive onto PlateDetection (k40/k52 null it; k29/k50 ignore
    the caller's 0.15 padding).
    pad = int(400*0.15)=60 x int(300*0.15)=45 -> crop box (40,55,560,445)
    size (520,390); norm (.2,.3,.8,.7) -> (40+104, 55+117, 40+416, 55+273).
    """
    detections = [VehicleDetection(id=7, bbox_x=100, bbox_y=100,
                                   bbox_width=400, bbox_height=300,
                                   file_path=temp_test_image)]
    model = MagicMock()
    box = MagicMock()
    box.xyxyn = [MagicMock()]
    box.xyxyn[0].tolist.return_value = [0.2, 0.3, 0.8, 0.7]
    box.conf = [0.9]
    result = MagicMock()
    result.boxes = [box]
    model.predict.return_value = [result]

    plates = await detect_plates(model=model, vehicle_detections=detections,
                                 padding=0.15)
    assert len(plates) == 1
    assert plates[0].bbox == (144.0, 172.0, 456.0, 328.0)


# ---------- T8: kills C16 keys 34,35,38,39 ----------
@pytest.mark.asyncio
async def test_detect_plates_forwards_inference_args_to_thread_pool(temp_test_image, mock_yolo_model):
    """to_thread must receive (model, crop, confidence_threshold) — patched
    autospec sees the call but existing test ignores the args.
    """
    detections = [VehicleDetection(id=1, bbox_x=100, bbox_y=100,
                                   bbox_width=200, bbox_height=150,
                                   file_path=temp_test_image)]
    with patch("asyncio.to_thread", autospec=True) as mock_to_thread:
        mock_to_thread.return_value = [([0.2, 0.3, 0.8, 0.7], 0.92)]
        await detect_plates(model=mock_yolo_model,
                            vehicle_detections=detections,
                            confidence_threshold=0.42)
        fn, model_arg, crop_arg, conf_arg = mock_to_thread.call_args[0]
        assert fn is _run_plate_detection_sync
        assert model_arg is mock_yolo_model
        assert crop_arg is not None and crop_arg.size[0] > 0  # kills k34/k38
        assert conf_arg == 0.42                              # kills k35/k39
```

(T8 needs `from unittest.mock import patch` — already imported at line 5 — and
`_run_plate_detection_sync` — already imported at line 16. T4 imports
`_load_image_sync` locally because the module's import list omits it.)

## Notes

- C8/C12 LOW-VALUE: suppress with record; killable (degenerate sub-pixel box /
  call-arg inspection of verbose) but no reviewer should pin that behavior.
- C13 EQUIVALENT proof is in-table; if the verification lane wants belt-and-
  braces, `predictions=None` + `side_effect`-free model is the edge that makes
  k10's TypeError path observable — both paths return `[]`, nothing to assert.
- Highest kill-per-test: T1 (10), T5 (5), T7+T8 (8 combined). T2 is next (4).
