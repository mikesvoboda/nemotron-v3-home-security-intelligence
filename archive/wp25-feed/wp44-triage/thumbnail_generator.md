# WP4.4 Triage Dossier — backend/services/thumbnail_generator.py

**Surviving mutants:** 118 of 257 keys (meta `exit_code == 0`).
**Covering test file (sole):** `backend/tests/unit/services/test_thumbnail_generator.py` (1,138 lines; per-function coverage confirmed via `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`).
**Diff source:** AST diff of each surviving `__mutmut_N` variant vs its `__mutmut_orig` inside `mutants/backend/services/thumbnail_generator.py`. Raw per-mutant diffs: `/tmp/wp25/wp44-triage/thumbnail_diffs.txt`.
**PIL-semantics probes** (read-only snippets, Pillow 12.3.0): `resize(..., None)` ≡ LANCZOS; `textbbox` without `font` ≡ `load_default()`; RGB channel 256 clamps to 255; `Image.new` color None/omitted ≡ black; `save(path, None/omitted)` infers JPEG from `.jpg`; `truetype(path, None)` raises TypeError.

## Structural finding

The test file is **assertion-shallow for every rendering path**: `draw_bounding_boxes` / `_resize_with_padding` / `generate_thumbnail` tests assert only `isinstance(result, Image.Image)`, `result.size`, file existence, output-path substring, and `img.format`. **Zero pixel-level or draw-call assertions** → every mutation that changes *what gets drawn* (color, label position, stroke width, font argument, paste geometry, extraction keys) survives. Skip-guards are never proven by observing *what was skipped*. Log mutations survive because no test uses `caplog`.

Per-function survivor counts (sum 118): draw 61, generate_thumbnail 17, _resize_with_padding 17, get_system_font 9, delete_thumbnail 6, _ensure_output_dir 4, async_generate_thumbnail 3, __init__ 1.

## Cluster table (every surviving key enumerated exactly once; counts sum to 118)

| # | Pattern | Fn | Keys | N | Class | Rationale |
|---|---------|----|------|---|-------|-----------|
| A1 | Box color lookup / outline / stroke mutations (color→None, wrong .get key/default, `.upper()`, outline dropped/None, width 3→4/dropped) | draw | db#49, db#54, db#61 | 10 | TEST-GAP | All of 49,50,51,52,53,54,56,59,60,61: box pixels change or vanish (white outline, no outline, 1px stroke — PIL default verified ≠ width=3). Tests: only `isinstance` (:435-476). Killed by T1 |
| A2 | bbox-field extraction replaced with `None` (box silently never drawn) | draw | db#22, db#26, db#30 | 4 | TEST-GAP | 22,26,30,34 (`bbox_* = detection.get(...)` → `None`): every detection looks incomplete → output == input image. Killed by T5 |
| A3 | Detection dict-key string mutations (`"k"` → None/`"XXkXX"`/`"K"`) | draw | db#6, db#10, db#16 | 18 | TEST-GAP | 6,10,11,15,19,20,23,24,25,27,28,29,31,32,33,35,36,37: lookup misses → same silent-skip as A2. Killed by T5 |
| A4 | Detection default mutations (`"unknown"`/`0.0` defaults → None/dropped/text; confidence 0.0→1.0) | draw | db#7, db#9, db#12 | 7 | TEST-GAP | 7,9,12,13,16,18,21: `None.lower()` crash, label `1.00` instead of `0.00`, missing-default crash. Killed by T5 |
| A5 | Label background + text draw-arg mutations (fill=None, font=None, args dropped) | draw | db#77, db#82, db#83 | 5 | TEST-GAP | 77,79,82,83,86: label bg/text vanish or reflow (font=None → PIL 6px default font shifts ink). Killed by T2 |
| A6 | Label text fill RGB 255→256 | draw | db#88, db#89, db#90 | 3 | EQUIVALENT | PIL clamps channels; ink identical (verified) |
| A7 | Label position (`label_y = y1-18` → `y1+18`, `y1-19`) | draw | db#67, db#68 | 2 | TEST-GAP | Label moves inside/below box or by 1px; no pixel assertion exists. Killed by T2 |
| A8 | None-guard logic flips (is-None→is-not-None, continue→break, or→and) | draw | db#39, db#41, db#42 | 8 | TEST-GAP | 39,41,42,43,44,63,64,65: guards admit incomplete detections into arithmetic (TypeError) or stop processing later valid detections. Killed by T5 |
| A9 | textbbox `font=` argument mutations | draw | db#72, db#75 | 2 | EQUIVALENT | `font=None`/omitted ≡ `load_default()`; bbox identical (verified) |
| A10 | Skip-guard warning log → None | draw | db#40 | 1 | LOW-VALUE | Log text only; no caplog assertions |
| A11 | text call trailing-comma no-op | draw | db#87 | 1 | EQUIVALENT | `font=font,` → `font=font` — syntactic no-op |
| A12 | Save format-argument mutations (`"JPEG"` → None/omitted/`"jpeg"`) | gen | gt#31, gt#39 | 4 | EQUIVALENT | 31,35,37,39: JPEG inferred from `.jpg` path (verified) |
| A13 | Save encoding tweaks (quality kwarg dropped, `optimize` False/dropped) | gen | gt#36, gt#40 | 2 | LOW-VALUE | 36,40: real encoder-flag change (q75 vs q85, no optimize) but observable only via file size/quality heuristics nobody should pin byte-exact |
| A14 | RGB-mode guard mutations (`!=`→`==`, `"RGB"`→`"XXRGBXX"`/`"rgb"`, `convert(None)`) | gen | gt#7, gt#8, gt#9 | 4 | TEST-GAP | 7,8,9,11: non-RGB inputs converted wrongly or `convert(None)` TypeError; the RGBA test (:843) passes anyway (no pixel/mode assertion). Killed by T6 |
| A15 | `detection_id = Path(image_path).stem` → None | gen | gt#25 | 1 | TEST-GAP | Filename becomes `None_thumb.jpg`; existing test (:325-337) asserts only `"_thumb.jpg" in output_path`. Killed by T6 |
| A16 | Log-call mutations (message→None, exc_info toggles) | gen | gt#41, gt#43, gt#44 | 6 | LOW-VALUE | 41,43,44,45,47,48 |
| A17 | Async wrapper drops forwarded args (output_size→None, quality→None, quality arg dropped) | async | ag#4, ag#6, ag#12 | 3 | TEST-GAP | Async success test always passes output_size equal to the default, and quality is never asserted → fallbacks invisible. Killed by T3 |
| A18 | Log-call mutations | delete | dt#3, dt#5, dt#7 | 6 | LOW-VALUE | 3,5,7,8,10,11 |
| A19 | Letterbox padding-color mutations (`(0,0,0)` → red/green/blue) | rwp | rwp#30, rwp#31, rwp#32 | 3 | TEST-GAP | Colored letterbox bars; `result.size == target_size` still passes (:581-638). Killed by T4 |
| A20 | Padding color arg mutations that are equivalent (`color=None`/omitted → black) | rwp | rwp#24, rwp#27 | 2 | EQUIVALENT | `Image.new` with None/omitted color = black (verified) |
| A21 | Aspect-preserving scale mutations (`/`→`*` in min(); `dim*scale`→`dim/scale`) | rwp | rwp#8, rwp#9, rwp#12 | 4 | TEST-GAP | 8,9,12,15: content ratio wrong (or crash at scale=0); tests check frame size only. Killed by T4 |
| A22 | Resize interpolation-argument mutations (`LANCZOS` → None/omitted) | rwp | rwp#18, rwp#20 | 2 | EQUIVALENT | Default resample IS LANCZOS; pixels identical (verified) |
| A23 | Center-paste geometry mutations (`-`→`+`, `//2`→`//3`) | rwp | rwp#35, rwp#36, rwp#39 | 4 | TEST-GAP | 35,36,39,40: content off-center/partially off-canvas; corner/row pixel checks absent. Killed by T4 |
| A24 | Paste position argument mutations (`(paste_x,paste_y)` → None/omitted → paste at (0,0)) | rwp | rwp#42, rwp#44 | 2 | TEST-GAP | Centering lost. Killed by T4 |
| A25 | Explicit-quality mutation in `__init__` (`quality if quality is not None` → `and False`) | init | init#7 | 1 | TEST-GAP | Explicit constructor quality silently ignored (85 always); no test constructs with `quality=` and asserts `_default_quality` or output encoding. Killed by T3 (constructor assert added there) |
| A26 | Font-size handling mutations in font discovery (`size is None` flip; `size=None` from settings; `truetype(path, None)`) | gsf | gsf#1, gsf#3, gsf#28 | 3 | TEST-GAP | `truetype(path, None)` raises TypeError on every candidate → always bitmap fallback (verified); flip routes explicit size into settings lookup. No test asserts the size passed to truetype. Killed by T7 |
| A27 | Log-call mutations | gsf | gsf#13, gsf#14, gsf#31 | 6 | LOW-VALUE | 13,14,31,32,33,34 (debug/warning text, attempted-paths bookkeeping feeding only log text) |
| A28 | `_ensure_output_dir` mkdir-kwargs mutations (`parents=True`→None/False/dropped) + ready-log text | ensure | ens#1, ens#3, ens#5 | 4 | LOW-VALUE | 1,3,5: real behavior change for nested paths, but test :297 already asserts `mkdir.assert_any_call(ANY, parents=True, exist_ok=True)` — it survives only because get_settings() emits a matching mkdir; strengthening that one assertion (assert on the *instance's* call, e.g. `mock_mkdir.call_args_list` filtering `self==generator.output_dir` or patch `ThumbnailGenerator._ensure_output_dir` scope) would kill 1/3/5 — one-line fix, no new test warranted. 7 = log text |

**Totals:** 10+4+18+7+5+3+2+8+2+1+1+4+2+4+1+6+3+6+3+2+4+2+4+2+1+3+6+4 = **118** ✔
**Class split:** TEST-GAP **79**, LOW-VALUE **25**, EQUIVALENT **14**.
TEST-GAP clusters: A1,A2,A3,A4,A5,A7,A8,A14,A15,A17,A19,A21,A23,A24,A25,A26 (10+4+18+7+5+2+8+4+1+3+3+4+4+2+1+3 = 79).
EQUIVALENT clusters: A6,A9,A11,A12,A20,A22 (3+2+1+4+2+2 = 14). LOW-VALUE: A10,A13,A16,A18,A27,A28 (1+2+6+6+6+4 = 25).

## Drafted tests (6 drafts; append to `backend/tests/unit/services/test_thumbnail_generator.py`)

Existing imports at top of file already cover `os`, `tempfile`, `Path`, `MagicMock`, `patch`, `pytest`, `Image`, `ImageFont`, `OBJECT_COLORS`; add only `from backend.core.config import get_settings` (T7) and `DEFAULT_COLOR` to the module import list (T1).

**// UNVERIFIED - not yet run red/green.** TDD procedure for each: apply one cluster mutant (or run the suite against `mutants/` copy) → the named test's assertion FAILS; revert to original → PASSES.

### T1 — kills A1 (10 mutants): box color/geometry/stroke pixel contract

```python
def test_draw_bounding_boxes_renders_expected_box_pixels_and_stroke(thumbnail_generator):
    """Pixel contract: 3px object-color outline exactly at bbox edges, interior untouched.

    Kills: color=None / wrong OBJECT_COLORS.get key-or-default / .upper() lookup
    (white box instead of person-red), outline dropped/None (no stroke at all),
    width dropped / width=4 (stroke-band pixel set differs).
    """
    bg = (100, 150, 200)
    img = Image.new("RGB", (300, 300), color=bg)
    detections = [
        {
            "object_type": "person",
            "confidence": 0.95,
            "bbox_x": 50,
            "bbox_y": 50,
            "bbox_width": 100,
            "bbox_height": 100,
        }
    ]

    result = thumbnail_generator.draw_bounding_boxes(img, detections)

    expected = OBJECT_COLORS["person"]
    assert expected != DEFAULT_COLOR  # distinguishability guard

    # Left stroke band: 3px wide starting at x=50, then interior background.
    assert result.getpixel((50, 100)) == expected
    assert result.getpixel((51, 100)) == expected
    assert result.getpixel((52, 100)) == expected
    assert result.getpixel((53, 100)) == bg
    # Bottom edge y=150 outlined in object color (not DEFAULT_COLOR / not absent).
    assert result.getpixel((100, 150)) == expected
    # Interior untouched.
    assert result.getpixel((100, 100)) == bg
```

Kills: 49,50,51,52,53,54,56,59,60,61. (`width=4` mutant: pixel (53,100) becomes red → assert 53==bg fails.)

### T2 — kills A5 + A7 (7 mutants): label rendering

```python
def test_draw_bounding_boxes_label_above_box_white_on_colored_band(thumbnail_generator):
    """Pixel contract: white label text on an object-colored background band at
    y = bbox_y - 18, nothing drawn well above it.

    Kills: label_y 18px-up -> 18px-down / -19 (band row becomes pure bg),
    label-rect fill=None / dropped (no colored band), text fill=None / dropped
    (no white ink), text font=None (default 6px font: no white pixel in the
    14px-font band row band checked here at this label text).
    """
    bg = (100, 150, 200)
    img = Image.new("RGB", (300, 300), color=bg)
    detections = [
        {
            "object_type": "person",
            "confidence": 0.95,
            "bbox_x": 50,
            "bbox_y": 50,
            "bbox_width": 100,
            "bbox_height": 100,
        }
    ]
    expected = OBJECT_COLORS["person"]

    result = thumbnail_generator.draw_bounding_boxes(img, detections)

    # label_y = 50 - 18 = 32. Band row must carry the colored background...
    band = [result.getpixel((x, 32)) for x in range(50, 140)]
    assert any(px == expected for px in band), "label background band missing"
    # ...and white glyph ink.
    assert any(px == (255, 255, 255) for px in band), "white label text missing"
    # label_y mutant (+18/-19) leaves this row pure background -> both asserts fail.
    # Nothing should be drawn 20px above the label band.
    assert all(result.getpixel((x, 8)) == bg for x in range(50, 140))
```

Kills: 67,68,77,79,82,83,86 (verify 83's font=None behavior red-green — 6px font ink still lands in row 32; if it passes, rely on 82/86 for fill and let T2's band assert kill 83 via background-band bbox shift; adjust expected row if needed at verification time).

### T3 — kills A17 + A25 (4 mutants): async forwarding + explicit constructor quality

```python
@pytest.mark.asyncio
async def test_async_generate_thumbnail_forwards_size_and_quality(
    thumbnail_generator, temp_test_image, sample_detections
):
    """The async wrapper must forward output_size and quality verbatim (kills
    output_size->None, quality->None, dropped quality in asyncio.to_thread)."""
    with patch.object(
        thumbnail_generator,
        "generate_thumbnail",
        wraps=thumbnail_generator.generate_thumbnail,
    ) as spy:
        output_path = await thumbnail_generator.async_generate_thumbnail(
            image_path=temp_test_image,
            detections=sample_detections,
            output_size=(200, 100),
            detection_id="det_fwd",
            quality=50,
        )

    assert output_path is not None
    args = spy.call_args.args
    assert args[2] == (200, 100), "output_size must be forwarded, not defaulted"
    assert args[4] == 50, "quality must be forwarded, not defaulted"


def test_init_explicit_quality_overrides_setting(temp_output_dir):
    """quality= must survive construction (kills `and False` short-circuit)."""
    settings = get_settings()
    gen = ThumbnailGenerator(output_dir=temp_output_dir, quality=42)

    assert gen._default_quality == 42
    assert gen._default_quality != settings.thumbnail_quality
```

(Kills A17: ag#4,6,12; A25: init#7. Needs `get_settings` import only for the second.)

### T4 — kills A19 + A21 + A23 + A24 (13 mutants): letterbox geometry

```python
def test_resize_with_padding_letterboxes_16x9_black_bars_centered(thumbnail_generator):
    """1600x900 -> 320x240: scale=min(320/1600,240/900)=0.2 => content 320x180 at
    y=30, black bars. Pins scale formula, black padding color, //2 centering,
    paste position.
    """
    content = (100, 150, 200)
    img = Image.new("RGB", (1600, 900), color=content)
    result = thumbnail_generator._resize_with_padding(img, (320, 240))

    assert result.size == (320, 240)
    # Black bars top/bottom corners (padding color + paste offset).
    assert result.getpixel((0, 0)) == (0, 0, 0)
    assert result.getpixel((319, 0)) == (0, 0, 0)
    assert result.getpixel((0, 239)) == (0, 0, 0)
    assert result.getpixel((10, 10)) == (0, 0, 0)
    # Content band starts at paste_y = (240-180)//2 = 30.
    assert result.getpixel((10, 31)) == content
    assert result.getpixel((10, 120)) == content
    assert result.getpixel((10, 209)) == content
    # Bar resumes at y=210.
    assert result.getpixel((10, 215)) == (0, 0, 0)
```

Kills A19 (30,31,32: corner pixels become (1,0,0)/(0,1,0)/(0,0,1)); A23 (35,36,39,40: content shifted → y=31/209 row or corner asserts fail); A24 (42,44: paste at (0,0) → (0,0) is content); A21 (8,9: scale formula → content band wrong/raises; 12,15: `/scale` gives 8000px content → paste clipped/crash — run a portrait sibling at fix-wave if #12 only survives geometry variants).

### T5 — kills A2 + A3 + A4 + A8 (37 mutants): detection-field extraction + skip guards

```python
def test_draw_bounding_boxes_extracts_fields_and_skips_incomplete_only(thumbnail_generator):
    """A complete detection must draw its box (fields extracted); incomplete
    detections must be skipped WITHOUT raising while a following valid detection
    is STILL drawn (continue not break; or not and).

    Kills: every detection.get(key) -> None / wrong-key mutant (box never drawn),
    every default mutation (None.lower() crash / label 1.00), and all guard flips.
    """
    bg = (100, 150, 200)
    expected = OBJECT_COLORS["person"]

    # 1) Complete detection -> its box is on the canvas.
    img = Image.new("RGB", (300, 300), color=bg)
    result = thumbnail_generator.draw_bounding_boxes(
        img,
        [{"object_type": "person", "confidence": 0.95,
          "bbox_x": 50, "bbox_y": 50, "bbox_width": 100, "bbox_height": 100}],
    )
    assert result.getpixel((50, 100)) == expected, (
        "fields not extracted: detection silently skipped (get->None mutants)"
    )

    # 2) Bad-then-good list: bad entries skipped silently, good one still drawn.
    img2 = Image.new("RGB", (300, 300), color=bg)
    mixed = [
        {"object_type": "person", "confidence": 0.9,
         "bbox_x": 10, "bbox_y": None, "bbox_width": 50, "bbox_height": 50},   # incomplete -> skip
        {"object_type": "car", "confidence": 0.9,
         "bbox_x": 10, "bbox_y": 10, "bbox_width": None, "bbox_height": 50},    # None dim -> skip
        {"object_type": "person", "confidence": 0.9,
         "bbox_x": 200, "bbox_y": 200, "bbox_width": 50, "bbox_height": 50},    # valid -> draw
    ]
    result2 = thumbnail_generator.draw_bounding_boxes(img2, mixed)  # must not raise
    assert result2.getpixel((200, 225)) == expected, (
        "valid detection after skipped ones not drawn (continue->break / or->and)"
    )
    # Skipped first detection left its area untouched.
    assert all(result2.getpixel((x, 10)) == bg for x in range(10, 60))


def test_draw_bounding_boxes_missing_confidence_renders_zero_label(thumbnail_generator):
    """Detection without confidence must label '... 0.00' (default 0.0)."""
    img = Image.new("RGB", (300, 300), color=(100, 150, 200))
    with patch("backend.services.thumbnail_generator.ImageDraw.Draw") as MockDraw:
        thumbnail_generator.draw_bounding_boxes(
            img,
            [{"object_type": "person",
              "bbox_x": 50, "bbox_y": 50, "bbox_width": 100, "bbox_height": 100}],
        )
    text_calls = MockDraw.return_value.text.call_args_list
    assert text_calls, "no label drawn"
    label = text_calls[0].args[1]
    assert label.endswith(" 0.00"), f"confidence default mutated: {label!r}"
    # object_type default must survive too ('unknown' fallback, lowercase-safe)
    assert label.startswith("person"), label
```

Kills: 22,26,30,34 (A2); 6,10,11,15,19,20,23,24,25,27,28,29,31,32,33,35,36,37 (A3); 7,9,12,13,16,18,21 (A4, incl. second test); 39,41,42,43,44,63,64,65 (A8). Some A3/A4 variants raise TypeError inside the draw loop of test 1 — the un-raised exception IS the red (pytest reports it); the second test pins confidence/object_type defaults specifically.

### T6 — kills A14 + A15 (5 mutants): mode conversion + stem fallback

```python
def test_generate_thumbnail_converts_non_rgb_input(thumbnail_generator):
    """Palette-mode (P) input must be converted to RGB before drawing/saving
    (kills `!=`->`==`, `"RGB"`->`"XXRGBXX"`/`"rgb"`, `convert(None)`)."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        img = Image.new("P", (640, 480))
        img.putpalette([i % 256 for i in range(768)])
        img.save(tmp.name, "PNG")
        try:
            output_path = thumbnail_generator.generate_thumbnail(
                image_path=tmp.name, detections=[], detection_id="det_palette"
            )
            assert output_path is not None
            out = Image.open(output_path)
            assert out.mode == "RGB"
            assert out.format == "JPEG"
        finally:
            Path(tmp.name).unlink(missing_ok=True)


def test_generate_thumbnail_no_detection_id_uses_image_stem(
    thumbnail_generator, temp_test_image, sample_detections
):
    """Fallback filename is '{stem}_thumb.jpg' — never 'None_thumb.jpg'."""
    output_path = thumbnail_generator.generate_thumbnail(
        image_path=temp_test_image, detections=sample_detections
    )
    assert output_path is not None
    assert Path(output_path).name == f"{Path(temp_test_image).stem}_thumb.jpg"
    assert "None" not in Path(output_path).name
```

Kills: gt#7,8,9,11 (A14) — P-mode with flipped guard hits `draw.rectangle` on a palette image or JPEG-save crash → None ≠ path; gt#25 (A15).

### T7 — kills A26 (3 mutants): font size threading

```python
def test_get_system_font_threads_size_into_truetype():
    """size=None must use settings.thumbnail_font_size; explicit size must reach
    truetype unchanged (kills the `is None` flip and size->None mutations:
    truetype(path, None) raises TypeError, and the settings value is asserted)."""
    with (
        patch.dict(os.environ, {}, clear=False),
        patch(
            "backend.services.thumbnail_generator.platform.system",
            return_value="Linux",
            autospec=True,
        ),
        patch(
            "backend.services.thumbnail_generator.ImageFont.truetype",
            autospec=True,
        ) as mock_tt,
    ):
        os.environ.pop("THUMBNAIL_FONT_PATH", None)
        expected = get_settings().thumbnail_font_size
        get_system_font(size=None)
        assert mock_tt.call_count > 0
        for call in mock_tt.call_args_list:
            size_arg = call.args[1] if len(call.args) > 1 else call.kwargs.get("size")
            assert size_arg == expected, "settings font size not threaded to truetype"

    with (
        patch.dict(os.environ, {}, clear=False),
        patch(
            "backend.services.thumbnail_generator.platform.system",
            return_value="Linux",
            autospec=True,
        ),
        patch(
            "backend.services.thumbnail_generator.ImageFont.truetype",
            autospec=True,
        ) as mock_tt2,
    ):
        os.environ.pop("THUMBNAIL_FONT_PATH", None)
        get_system_font(size=21)
        assert mock_tt2.call_args_list[0].args[1] == 21
```

## Fix-wave notes

- **Ordering:** T5 → T4 → T1 → T2 → T6 → T3 → T7 by kill count (37, 13, 10, 7, 5, 4, 3).
- Permanent survivors after these drafts should be exactly the 14 EQUIVALENT (A6, A9, A11, A12, A20, A22) + 25 LOW-VALUE (A10, A13, A16, A18, A27, A28) = 39 keys; anything else that still survives after red/green verification needs a second look.
- A28 (mkdir kwargs): one-line strengthening of existing test :297 (filter mkdir calls to the generator's own output_dir, e.g. `assert any(c.args[0] is gen.output_dir and c.kwargs.get("parents") is True ...)`) — no new test drafted per scope budget.
- All drafted tests are **UNVERIFIED - not yet run red/green** (harness constraint: no pytest during live mutation run).
