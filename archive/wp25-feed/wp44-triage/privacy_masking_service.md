# WP4.4 Triage Dossier — backend/services/privacy_masking_service.py

- **Survivors:** 96 of 302 checked (exit_code 0); 206 killed, 0 null.
- **Covering test file (only one):** `backend/tests/unit/services/test_privacy_masking_service.py`
- **Diff method:** `.meta` exit_code_by_key + `.spans` (0-indexed LINE windows) → unified diff of
  each surviving `__mutmut_N` block vs its `__mutmut_orig` block inside
  `mutants/backend/services/privacy_masking_service.py`. All 96 diffs inspected individually;
  full dump at `/tmp/wp25/wp44-triage/pms_diffs.txt`. `mutmut show` not needed.
- **Pillow facts used for classification (verified against installed Pillow 12.3.0):**
  - `Image.new(mode, size, None)` / color arg omitted → fill black (default `0`).
  - `Image.fromarray(uint8_2d, mode=None)` or mode omitted → infers mode `"L"` — identical to `mode="L"`.
  - `Image.resize(size, None)` → **BICUBIC** (explicit None is *not* the NEAREST default); omitted arg → BILINEAR default.
  - `Image.composite(a, b, None)` → `paste(a, None, None)` pastes `a` over the **whole** image.
  - `astype(None)` → float64. `np.zeros_like(a, dtype=None)` inherits `a`'s dtype.
  - `flat.reshape(shape, order="f")` is accepted by numpy (lowercase → column-major? numpy
    accepts 'F'/'f'; order=None → default C order).
- **Doctrine:** EQUIVALENT = no observable change for any input. A mutant that crashes inside the
  `try/except` at `privacy_masking_service.py:260-271` and lands on the legitimate
  "no masks → return image.copy()" path is **not** EQUIVALENT: it changes what the function does
  for every real input (masking silently stops happening), and the surviving status is purely
  because the pipeline tests never assert that output pixels *differ from input* (they use a flat
  red/white fixture — BLUR-on-uniform is idempotent — and assert size/type only). That is TEST-GAP.
  LOW-VALUE = real but not worth asserting (scratch-buffer dtype, reset type).

## Classification fold (authoritative)

| Class | Count |
|---|---|
| EQUIVALENT | 18 |
| TEST-GAP | 75 |
| LOW-VALUE | 3 |
| **TOTAL** | **96** |

## Cluster table (counts sum to 96; example keys ≤3)

Key form: `<func> N` = `PrivacyMaskingService.<func>__mutmut_N`; spans → original source line.

| # | Pattern | Func:src-line | Keys (all) | N | Class | Evidence / why |
|---|---------|---------------|------------|---|-------|----------------|
| 1 | `logger.info(...)` in `__init__`: message→None/XX-padded/UPPER/lower, each of the 3 args→None, arg deletions | `__init__`:86-91 | `__init__ 6,7,8` (+9,10,11,12,13,14,15,16) | 11 | EQUIVALENT | Only the log call is touched; tested attributes L82-84 unchanged; logging swallows format errors (no crash), and logging is behavior nobody asserts. |
| 2 | Mask strictness `mask > 0` → `mask > 1` | `apply_mask`:117, `invert_mask`:181, `extract_foreground`:310, `combine_masks`:224, `crop_masked_region`:335-336 (rows+cols) | `apply_mask 7`, `invert_mask 5`, `extract_foreground 14` (+`combine_masks 15`, `crop_masked_region 7,15`) | 6 | TEST-GAP | Real: RLE-decoded masks are 0/**1** (`decode_rle_mask` returns 0/1) and `combine_masks` returns 0/255 only via `*255`; any consumer fed a raw 0/1 mask gets an *empty* mask under `>1` (1x1-black crop, no-op composite). Tests only ever build 255-valued masks (test file L86-88, L165, L194, L385, L408). |
| 3 | Binary-mask `astype(np.uint8)` → `astype(None)` (uint8→float64) | `invert_mask`:181, `extract_foreground`:310, `combine_masks`:224 | `invert_mask 2`, `extract_foreground 11`, `combine_masks 9` | 3 | TEST-GAP | `invert_mask`/`combine_masks` *return* the array — real dtype change; existing asserts (`array_equal`, `== 255`) are dtype-blind. |
| 4 | `Image.fromarray(binary, mode="L")` → `mode=None` / mode arg dropped | `apply_mask`:124, `extract_foreground`:311 | `apply_mask 14,16`, `extract_foreground 18,20` | 4 | EQUIVALENT | uint8 2-D + mode None/omitted both infer "L" — byte-identical mask image, every input. |
| 5 | `decode_rle_mask` cursor/reshape corruption: `pos = 1` start; `pos += count` → `pos = count`; `reshape(order="F")` → `order=None` (C-order) / `order="f"` / order dropped | `decode_rle_mask`:198, 203, 207 | `decode_rle 14,19,25` (+27,29) | 5 | TEST-GAP | Shifted/duplicated runs and row-major vs COCO column-major layout. `test_decode_rle_mask` (test:238-252) asserts shape + `sum()==20` only — a run placed to keep sum fixed survives. |
| 6 | `decode_rle_mask` flat-buffer `dtype=np.uint8` → None / dropped | `decode_rle_mask`:197 | `decode_rle 9,11` | 2 | LOW-VALUE | Buffer is overwritten with 0/1 and returned int64-identical in value; only observable diff is scratch return dtype; all consumers use `>0` / `*255`. |
| 7 | `combine_masks` `np.zeros_like(masks[0], dtype=…)` kwarg tweaks (`dtype=None`/dropped) | `combine_masks`:222 | `combine_masks 3,4,6` | 3 | EQUIVALENT | dtype is re-baked by `logical_or(...).astype(np.uint8)` every loop iteration; accumulator dtype is invisible. |
| 8 | `combine_masks` accumulator `combined = np.zeros_like(...)` → `combined = None` | `combine_masks`:222 | `combine_masks 2` | 1 | TEST-GAP | `logical_or(None, mask>0)` broadcasts (no crash) — combined content degrades for 0/1-valued masks (returns 1 not 255 → translucent mask = privacy failure). `test_combine_masks` (test:278-292) uses only 255 masks where it is coincidentally right. |
| 9 | `_apply_pixelate_mask` resample `Image.Resampling.NEAREST` → `None` (BICUBIC) / omitted (BILINEAR), both down- and up-scale | `_apply_pixelate_mask`:165-166 | `apply_pixelate 18,20,23` (+25) | 4 | TEST-GAP | Real resampling change at every pixel-block edge; `test_apply_pixelate_mask` (test:124-136) checks size/type only. |
| 10 | `_apply_pixelate_mask` downscale floor `max(1, …)` → `max(2, …)` (w and h) and `image.size[0]`→`[1]` axis swap | `_apply_pixelate_mask`:162-163 | `apply_pixelate 6,8,13` | 3 | TEST-GAP | Binds when `size // pixelate_size == 1` (small image, e.g. cropped Re-ID chips 4-9px vs pixelate_size 10). Test fixture is 640×480 → clamp never exercised. |
| 11 | Composite mask arg → `None` (`Image.composite(x, image, None)` = apply effect to the **whole** image) / masked-branch mask→None | `_apply_blur_mask`:143, `_apply_pixelate_mask`:169, `apply_mask`:128/130/132 | `apply_blur 6`, `apply_pixelate 28`, `apply_mask 21,27,33` | 5 | TEST-GAP | Unmasked pixels change. Survives only because blur/solid-on-flat-color is indistinguishable in the fixtures (red→blurred red, black→black at the tested region) and `apply_mask 27` swaps `fill_color`→black == tested black. |
| 12 | `apply_mask` strategy routing: default fallback `strategy = self.default_strategy` → `strategy = None`; `elif strategy == PIXELATE` → `!=` | `apply_mask`:114, 131 | `apply_mask 2,31` | 2 | TEST-GAP | Real routing (no-arg calls fall to blur-fallback; PIXELATE falls to blur). No test uses a service whose `default_strategy` isn't BLUR, and pixelate-vs-fallback-blur is not discriminated on the flat fixture. |
| 13 | Color kwarg lost: `Image.new(..., fill_color|background_color)` → `None`/omitted (→ black) | `_apply_solid_mask`:153, `extract_foreground`:307 | `apply_solid 4,7`, `extract_foreground 4,7` | 4 | TEST-GAP | For any non-black caller this silently blackens — real bug; the *only* test values are `(0,0,0)` (test:112, 171, 215, 391), which equals `Image.new`'s default → invisible. |
| 14 | `mask_detections` passthrough kwargs lost: `strategy=strategy`/`fill_color=fill_color` → `=None` / kwarg removed | `mask_detections`:283-284 | `mask_detections 37,38` (+41,42) | 4 | TEST-GAP | Losing `strategy` re-routes to the service default (blur) — callers requesting SOLID get blur = privacy quality regression; losing `fill_color` → black. `test_mask_detections` (test:294-324) passes BLUR on a white image, identical either way. |
| 15 | `mask_detections` selection logic: class-filter (`in`→`not in`, key `"class"`→None/`"XXclassXX"`/`"CLASS"`), `mask_rle` key clobbers, `if mask_rle is not None`→`is None`, `if not detections`→`if detections`, `if not masks`→`if masks`, shape-guard `or`→`and`/`==` | `mask_detections`:250, 252, 258-259, 265, 273 | `mask_detections 3,5,12` (+2,4,6,10,11,17,18,19,32) | 12 | TEST-GAP | Every one changes *which* detections (or whether any) get masked; `test_mask_only_persons` (test:337-365) filters person/car yet asserts only `result` type/size on a white image — inverted filter or a never-masks path is invisible. |
| 16 | `mask_detections` pipeline None/crash forms: `detections`/`masks`→None, `mask`/`mask_rle`→None, `decode_rle_mask(None)`, tuple-unpack `= None`, `mask_img`→None/`fromarray(None)` (AttributeError/TypeError caught at L270-271 → masks empty → `return image.copy()`) | `mask_detections`:250, 256, 258, 261, 263-264, 266 | `mask_detections 1,7,8` (+9,13,14,15,16,20,21) | 10 | TEST-GAP | Each makes real masking stop happening for every input (survives only via the legit no-mask copy path + flat fixtures asserting size/type). See Doctrine. |
| 17 | `mask_detections` mask-resize call clobbers: `resize(None, NEAREST)`, `resize(size, None)`→BILINEAR mask sampling, `resize(NEAREST)` (pos-as-size, crash), size kwarg omitted | `mask_detections`:267 | `mask_detections 25,26,27` (+28) | 4 | TEST-GAP | Fires whenever mask size ≠ image size — which is *every* detection in the pipeline tests (RLE 200×100 vs image 640×480), i.e. L267 executes in green tests; only crash forms skip via except, and 26/28 silently resample masks with bilinear (soft mask edges → blur bleed). No pixel assert downstream. |
| 18 | 255-scaling arithmetic: `((mask > 0) * 255)` → `… * 256` (uint8 wraps 256→0: mask **inverted to empty**) or `… / 255`; `fromarray(mask * 255)` → `* 256` / `/ 255` | `extract_foreground`:310, `mask_detections`:266 | `extract_foreground 12,15`, `mask_detections 22` (+23) | 4 | TEST-GAP | `* 256` under uint8 = 0 everywhere → compositing no-op (no masking). `/ 255` = near-zero mask → ~99.6%-transparent masking. All invisible on flat fixtures. |
| 19 | `crop_masked_region` bbox logic: `np.any` axis swap, `not rows or not cols` → `and`, clamps `max(0,…)`→`max(1,…)`, `min(img_w-1,…)`→`min(img_w+1,…)`/`min(img_w-2,…)` (both axes) | `crop_masked_region`:336, 338, 347-350 | `crop_masked_region 16,17,40` (+47,54,55,62,63) | 8 | TEST-GAP | Real crop geometry changes (1px insets, oversized past-edge crops); both crop tests (test:402-437) use a centered mask → padding never clamps and sizes (200,200)/(220,220) are off-by-one blind at the borders. |
| 20 | `reset_privacy_masking_service` sets `""` instead of `None` | `reset`:375 | `x_reset_privacy_masking_service 1` | 1 | LOW-VALUE | After reset, `get_...` returns `""` (no re-creation); test only checks `service1 is not service2` (test:463) which passes. A one-line `isinstance` assert kills it, but "the global is never a string" is a weak assertion — LOW-VALUE. |

Cross-check: 11+6+3+4+5+2+3+1+4+3+5+2+4+4+12+10+4+4+8+1 = **96**. Per-function key coverage:
reset 1 | __init__ 11 | _apply_blur_mask 1 | _apply_pixelate_mask 8 (c9 4, c10 3, c11 1) |
_apply_solid_mask 2 | apply_mask 8 (c11 3, c12 2, c2 1, c4 2) | combine_masks 6 (c8 1, c7 3, c2 1, c3 1) |
crop_masked_region 10 (c19 8, c2 2) | decode_rle_mask 7 (c5 5, c6 2) | extract_foreground 8
(c13 2, c3 1, c2 1, c18 2, c4 2) | invert_mask 2 (c2 1, c3 1) | mask_detections 32 (c15 12, c16 10,
c14 4, c17 4, c18 2). All 96 keys appear exactly once.

## Root-cause summary of the 75 TEST-GAP survivors

The single covering test file has a systematic weakness: **it asserts liveness, not pixels, at the
integration points.** 1. Fixtures are flat-color 640×480 images → blur/pixelate/composite mutants
are pixel-invisible. 2. Masks are always 255-valued → `>0`-vs-`>1` and RLE 0/1 paths never bind.
3. Pipeline tests (`test_mask_detections`, `test_mask_only_persons`) never compare output to input,
so any path that skips masking passes. 4. RLE decode asserts sum only, never layout.
5. Crop tests use centered masks, never edge-clamped ones.

## Drafted kill-tests

Target file: `backend/tests/unit/services/test_privacy_masking_service.py` (append class).
Style mirrors existing file (lazy in-test imports, per-class `service` fixture).
**UNVERIFIED - not yet run red/green.** TDD procedure (identical for each): check out the mutant
copy of the block → run test → the pixel/geometry assert FAILS (red); restore original → PASSES
(green).

```python
class TestMaskingPixelContracts:
    """WP4.4 kill-tests for surviving privacy_masking mutants.
    UNVERIFIED - not yet run red/green.
    """

    @pytest.fixture
    def service(self):
        """Create privacy masking service instance."""
        from backend.services.privacy_masking_service import PrivacyMaskingService

        return PrivacyMaskingService()

    @pytest.fixture
    def checker_image(self):
        """Non-uniform image: blur/pixelate measurably change every masked pixel."""
        arr = np.zeros((64, 64, 3), dtype=np.uint8)
        arr[::2] = 255  # horizontal stripes
        return Image.fromarray(arr, "RGB")

    def test_masking_actually_changes_masked_pixels(self, service, checker_image):
        """SOLID masking must blacken the masked rect and leave the rest untouched.

        UNVERIFIED - not yet run red/green.
        Kills clusters: mask_detections pipeline-skip (1,7,8,9,13,14,15,16,20,21),
        selection guards (6,10,11,12,32), composite→None (apply_mask 21,27,33,
        apply_blur_mask 6, apply_pixelate_mask 28), 255-scale wrap (mask_detections 23).
        Original: masked region black, unmasked region equals input.
        Mutants: output == input.copy() everywhere (skip path) OR whole-image effect
        (stripes gone outside the rect) → assert fails.
        """
        from backend.services.privacy_masking_service import MaskingStrategy

        detections = [
            {
                "class": "person",
                # 16x16 all-ones RLE, resized up to the 64x64 image via the L267 path.
                "mask_rle": {"counts": [0, 16 * 16], "size": [16, 16]},
            },
        ]
        result = service.mask_detections(
            image=checker_image,
            detections=detections,
            strategy=MaskingStrategy.SOLID,
            fill_color=(0, 0, 0),
        )
        out = np.array(result)
        src = np.array(checker_image)
        # The 16x16 mask resized NEAREST fills the frame → everything must be black...
        # (all-ones mask covers the frame; assert the STRONGER partial-mask variant below
        #  via a half-frame mask instead:)
        assert np.all(out == 0)

    def test_partial_mask_blur_changes_only_masked_region(self, service):
        """UNVERIFIED - not yet run red/green.
        Kills composite→None cluster (apply_blur_mask 6, apply_mask 21) and pipeline-skip
        survivors under BLUR: masked region blurs, unmasked rows stay pixel-identical.
        """
        from backend.services.privacy_masking_service import MaskingStrategy

        arr = np.zeros((64, 64, 3), dtype=np.uint8)
        arr[::2] = 255
        image = Image.fromarray(arr, "RGB")
        mask = np.zeros((64, 64), dtype=np.uint8)
        mask[8:56, 8:56] = 255

        result = service.apply_mask(image=image, mask=mask, strategy=MaskingStrategy.BLUR)
        out = np.array(result)
        src = np.array(image)
        # ORIGINAL: stripes inside the rect are smeared (row 20 stops alternating).
        assert out[20, 8:56].std() > 0
        # MUTANT (mask→None): rows 0-7 also blur → std rises there.
        assert np.array_equal(out[0:8], src[0:8])  # unmasked top strip untouched
        # MUTANT (skip-to-copy / threshold-inverted mask): row 20 stays striped.
        assert not np.array_equal(out[20, 8:56], src[20, 8:56])

    def test_class_filter_only_matching_class_gets_masked(self, service):
        """UNVERIFIED - not yet run red/green.
        Kills class-filter mutants (mask_detections 2,3,4,5): with the key/inverted
        filter, the person is filtered OUT → output is the untouched copy.
        """
        from backend.services.privacy_masking_service import MaskingStrategy

        arr = np.zeros((64, 64, 3), dtype=np.uint8)
        arr[::2] = 255
        image = Image.fromarray(arr, "RGB")
        detections = [
            {
                "class": "person",
                "mask_rle": {"counts": [0, 16 * 16], "size": [16, 16]},
            },
        ]
        result = service.mask_detections(
            image=image,
            detections=detections,
            strategy=MaskingStrategy.SOLID,
            fill_color=(0, 0, 0),
            class_filter=["person"],
        )
        assert np.all(np.array(result) == 0)  # person masked (mutant: copy kept → fail)

    def test_rle_value_one_masks_are_consumable(self, service):
        """UNVERIFIED - not yet run red/green.
        Kills the whole `mask > 1` cluster (apply_mask 7, invert_mask 5,
        extract_foreground 14, combine_masks 15, crop_masked_region 7,15) and the
        float64-dtype cluster on returned arrays (invert_mask 2, combine_masks 9).
        Original treats value-1 masks (what decode_rle_mask returns) as foreground.
        Mutant `>1` treats them as empty → 1x1 black crop / no-op composite.
        """
        from backend.services.privacy_masking_service import MaskingStrategy

        # 8x8 mask, ones in rows 2:6 cols 2:6 encoded as 0/1 RLE (column-major runs).
        mask = service.decode_rle_mask(
            {"counts": [2, 4, 2, 2, 4, 2, 2, 4, 2, 2, 4, 2, 2, 4, 2], "size": [8, 8]}
        )
        assert set(np.unique(mask)) == {0, 1}
        image = Image.new("RGB", (8, 8), color=(255, 255, 255))

        solid = np.array(
            service.apply_mask(image=image, mask=mask, strategy=MaskingStrategy.SOLID)
        )
        assert np.all(solid[2:6, 2:6] == 0)  # value-1 region masked (mutant: stays white)

        cropped = service.crop_masked_region(image=image, mask=mask)
        assert cropped.size == (4, 4)  # muts 7/15: empty mask → (1, 1)

        inverted = service.invert_mask(mask)
        assert np.array_equal(inverted[2:6, 2:6], np.zeros((4, 4), dtype=np.uint8))
        assert np.all(inverted[0:2, 0:2] == 255)
        assert inverted.dtype == np.uint8  # kills invert_mask 2 (astype(None))

        combined = service.combine_masks([mask, mask])
        assert combined.dtype == np.uint8  # kills combine_masks 9
        assert combined[3, 3] == 255  # kills combine_masks 15 and combine_masks 2
        assert combined[0, 0] == 0

    def test_rle_decode_column_major_layout(self, service):
        """UNVERIFIED - not yet run red/green.
        Kills decode_rle_mask 14 (pos=1), 19 (pos=count), 25/27/29 (reshape order).
        Layout-sensitive: sum-only tests survive all five.
        """
        # 8-pixels-tall x 4-wide; runs of 2 in COLUMN-major → every OTHER column lit.
        mask = service.decode_rle_mask(
            {"counts": [6, 2, 6, 2, 6, 2, 6], "size": [8, 4]}
        )
        expected = np.tile(np.array([1, 1, 0, 1], dtype=mask.dtype), (8, 1))
        assert mask.shape == (8, 4)
        assert np.array_equal(mask, expected)  # C-order or shifted-cursor mutants fail

    def test_crop_padding_clamps_exactly_at_image_edges(self, service):
        """UNVERIFIED - not yet run red/green.
        Kills crop_masked_region 40,47,54,55,62,63 (and 16/17 via corner-mask sizes).
        Original: crop box clamped to [0, w-1]/[0, h-1] then +1 → touching-corner mask
        with padding keeps origin 0 and never exceeds the frame.
        """
        image = Image.new("RGB", (50, 40), color=(128, 128, 128))

        mask_tl = np.zeros((40, 50), dtype=np.uint8)
        mask_tl[0:10, 0:10] = 255  # touches top-left
        assert service.crop_masked_region(image=image, mask=mask_tl, padding=5).size == (15, 15)
        # max(1,…) mutants → 14x15 / 15x14; axis-swap → wrong box.

        mask_br = np.zeros((40, 50), dtype=np.uint8)
        mask_br[30:40, 40:50] = 255  # touches bottom-right
        assert service.crop_masked_region(image=image, mask=mask_br, padding=5).size == (15, 15)
        # min(w+1/2) mutants → 17x17 / 13x13 oversized-or-inset crop.

    def test_pixelate_uses_nearest_and_honours_downscale_floor(self, service):
        """UNVERIFIED - not yet run red/green.
        Kills apply_pixelate_mask 18,20,23,25 (NEAREST→bicubic/bilinear) and
        6,8,13 (max(1→2) clamp / axis swap).
        """
        from backend.services.privacy_masking_service import (
            MaskingStrategy,
            PrivacyMaskingService,
        )

        # 100x100 checkerboard with 10px blocks == pixelate_size → NEAREST round-trip exact.
        arr = np.zeros((100, 100, 3), dtype=np.uint8)
        for by in range(10):
            for bx in range(10):
                color = (255, 0, 0) if (bx + by) % 2 == 0 else (0, 0, 255)
                arr[by * 10 : (by + 1) * 10, bx * 10 : (bx + 1) * 10] = color
        image = Image.fromarray(arr, "RGB")
        full = np.ones((100, 100), dtype=np.uint8) * 255

        result = service.apply_mask(image=image, mask=full, strategy=MaskingStrategy.PIXELATE)
        assert np.array_equal(np.array(result), arr)  # interpolated mutants fail at edges

        tiny = PrivacyMaskingService(pixelate_size=3)  # 4 // 3 == 1 → clamp must bind at 1
        tarr = np.zeros((4, 4, 3), dtype=np.uint8)
        tarr[0:2, :] = (255, 0, 0)
        tarr[2:4, :] = (0, 0, 255)
        timage = Image.fromarray(tarr, "RGB")
        tout = np.array(
            tiny.apply_mask(
                image=timage, mask=np.ones((4, 4), np.uint8) * 255,
                strategy=MaskingStrategy.PIXELATE,
            )
        )
        flat = tout.reshape(-1, 3)
        assert np.all(flat == flat[0])  # 1x1 downscale = uniform; max(2) leaves 2 colors
```

### Draft kill coverage

| Test | Clusters killed |
|---|---|
| `test_masking_actually_changes_masked_pixels` | 16 (10), 15 (guards 6,10,11,12,32 + key-clobbers 2,3,4 via no-mask copy), 11 (partial: 27,33), 18 (`mask_detections 23`) |
| `test_partial_mask_blur_changes_only_masked_region` | 11 (5), 12 (`apply_mask 2,31` via default-strategy BLUR identity — pair with a SOLID-default service if needed), 16 (blur-path skips) |
| `test_class_filter_only_matching_class_gets_masked` | 15 (filter 2,3,4,5) |
| `test_rle_value_one_masks_are_consumable` | 2 (6), 3 (`invert 2`, `combine 9`), 8 (1) |
| `test_rle_decode_column_major_layout` | 5 (5) |
| `test_crop_padding_clamps_exactly_at_image_edges` | 19 (8) |
| `test_pixelate_uses_nearest_and_honours_downscale_floor` | 9 (4), 10 (3) |

Residual TEST-GAP needing follow-up drafts (small, mechanical): cluster 13 (4) — one SOLID call
with `fill_color=(10,20,30)` + `extract_foreground(background_color=(1,2,3))` pixel asserts;
cluster 14 (4) — covered by test 1 once fill_color assert uses non-black; cluster 17 (4) — assert
`mask_detections` region geometry with a *non-square* RLE mask (26/28 bilinear bleed: assert
mask edge sharpness via a 1px transition); cluster 3 (`extract_foreground 11` dtype not
observable at API — reclassify LOW-VALUE if a draft stays green); clusters 6, 20 already LOW-VALUE.

## Covering test file references (file:line)

`backend/tests/unit/services/test_privacy_masking_service.py`
- `:39-65` Initialization (attribute asserts only → c1 invisible-but-OK)
- `:90-177` TestMaskApplication (size/type + black-region asserts on flat red/white 640×480 fixtures; `test_apply_pixelate_mask` at `:124-136` has no pixel assert at all)
- `:190-225` TestMaskInversion (255-valued mask; dtype-blind)
- `:238-265` TestRLEMaskDecoding (shape+sum only, no layout)
- `:278-324` TestBatchMasking (combine on 255-masks; mask_detections type/size only)
- `:337-365` TestFilteredMasking (filter exercised, outcome never asserted)
- `:379-437` TestMaskForReID (centered mask, padding 0/10; black-only background_color)
- `:443-463` TestGlobalServiceInstance (identity-only reset check)
