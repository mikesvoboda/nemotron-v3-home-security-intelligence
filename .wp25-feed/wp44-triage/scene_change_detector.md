# WP4.4 Triage Dossier — backend/services/scene_change_detector.py

- Run stats: 203 mutant keys total, 169 killed, **34 survivors** (meta exit_code 0), 0 unchecked.
- Diffs: all 34 via `uv run mutmut show <key>` (read-only; rc=0, no fallback diffing needed). Raw dump: `/tmp/wp25/wp44-triage/_scd_diffs.txt`, survivor keys: `/tmp/wp25/wp44-triage/_scd_surv.txt`.
- Sole covering test file for all survivors: `backend/tests/unit/services/test_scene_change_detector.py` (mutmut-stats `tests_by_mangled_function_name`; `SceneChangeResult.to_dict` is covered only by `backend/tests/unit/services/test_enrichment_data_consistency.py` — no survivors there).
- Equivalence rulings verified against the installed libraries' sources (no test execution anywhere):
  - Pillow `_fromarray_typemap` (`.venv/.../PIL/Image.py` ~L3540): the only `(1,1,3)`/`(1,1,4)` uint8 entries map to typemode `RGB`/`RGBA`, and `(1,1)` uint8 → `L`; so `mode="RGB"|"RGBA"|"L"` vs `mode=None` (inference) builds byte-identical images for every dtype that doesn't raise in **both** variants.
  - Pillow `Image.resize` (L2329+): `resample=None → Resampling.BICUBIC` (NOT LANCZOS) — real pixel change; but `if self.size == size …: return self.copy()` — same-size resize is a filter-independent fast path.
  - skimage `structural_similarity`: `win_size=None → 7` then raises `ValueError('win_size exceeds image extent')` if `shape - win_size < 0` and `ValueError('Window size must be odd.')` if `win_size % 2 == 0`; `data_range=None` derives `255` from uint8 dtype (`dtype_range[uint8] = (0,255)`).
  - Production input contract: `enrichment_pipeline.py:2719` feeds `np.array(pil_image)` → always uint8; baselines are always prepared (2-D uint8), so `shape[:3]` unpacks of a 2-tuple are inert and float-dtype passthrough frames are outside the established (uint8) contract.

## Cluster table (counts sum to 34)

| # | Pattern | N | Keys (examples ≤3) | Class | Evidence / why tests miss it |
|---|---------|---|--------------------|-------|------------------------------|
| C1 | Validation `raise ValueError` message padded with `XX…XX` (`__init__`, `_to_grayscale`, `detect_changes`) | 4 | `__init___mutmut_7`, `__init___mutmut_15`, `_to_grayscale__mutmut_3` (+ `detect_changes__mutmut_3`) | EQUIVALENT | Tests use `pytest.raises(match=…)` with substrings that survive the padding: `"between 0 and 1"` (test:69,74,89), `"cannot be None"` (test:508,523). Message text only. |
| C2 | Error-message type interpolation swapped `type(frame)/type(current_frame).__name__` → `type(None).__name__` | 2 | `_to_grayscale__mutmut_22`, `detect_changes__mutmut_14` | EQUIVALENT | Only observable as a wrong type *name* inside the message ("got str" → "got NoneType"); `match="must be a numpy array"` / `"numpy array with shape"` (test:513,528) never inspects the tail. Exception type/branch unchanged. |
| C3 | `Image.fromarray(..., mode="RGB"/"RGBA"/"L")` neutralized to `mode=None` or kwarg dropped (`_to_grayscale` RGB+RGBA, `_resize_frame` L) | 6 | `_to_grayscale__mutmut_32`, `_to_grayscale__mutmut_47`, `_resize_frame__mutmut_7` (+34, +49, +9) | EQUIVALENT | Verified against Pillow `_fromarray_typemap`: inference yields byte-identical mode for every uint8 input, and every dtype lacking a typemap entry raises `TypeError` in *both* variants (the typekey lookup precedes the mode override). |
| C4 | `frame.shape[:2]` / `baseline.shape[:2]` → `shape[:3]` unpack | 2 | `_resize_frame__mutmut_2`, `detect_changes__mutmut_30` | EQUIVALENT | All reachable inputs are 2-D prepared arrays (`_prepare_frame` → `_to_grayscale` first; baselines always stored prepared) — `[:3]` of a 2-tuple is still 2 values. A direct 3-D call raises `ValueError` in both variants (too-many-values vs too-many-dimensions). |
| C5 | `resize_width <= 0` guard → `<= 1` (`__init__`) — resize_width=1 becomes invalid | 1 | `__init___mutmut_13` | TEST-GAP | `test_invalid_resize_width` (test:87–92) only tries `0` and `-100`; no test constructs `resize_width=1`. Kill: Draft 5. |
| C6 | `if not hasattr(frame,"ndim") or not hasattr(frame,"shape")` → `and` (`_to_grayscale`) — duck-typed objects pass the guard | 1 | `_to_grayscale__mutmut_6` | TEST-GAP | Test inputs ("not an array", list, None) all lack *both* attrs (test:521–529), so or/and coincide. Mutant lets an `ndim`-only object through and returns it raw / dies with `AttributeError` instead of the documented `ValueError`. Kill: Draft 7 (one-liner). |
| C7 | `img.resize(..., Image.Resampling.LANCZOS)` → `None`/dropped in `_resize_frame` (explicit-target branch) — Pillow defaults to **BICUBIC** | 2 | `_resize_frame__mutmut_14`, `_resize_frame__mutmut_16` | TEST-GAP | Verified `resize()` L2367: `resample=None → BICUBIC`. Real pixel change on any genuine downscale; size-change tests (test:311–343) assert only `0<=score<=1`. `detect_changes` hits this branch whenever frame ≠ baseline size. Kill: Draft 6. |
| C8 | `if w <= self._resize_width` → `w <` (`_resize_frame`) | 1 | `_resize_frame__mutmut_18` | EQUIVALENT | At `w == resize_width`, `scale = 1.0` → `new_h = int(h*1.0) = h` → Pillow same-size fast path (`self.size == size → self.copy()`, verified L2397) returns byte-identical output. Only the branch differs. |
| C9 | `win_size = min(7, min_dim)` → `min(8, min_dim)` (`detect_changes`) | 1 | `detect_changes__mutmut_46` | EQUIVALENT | For every `min_dim ≥ 8` the mutant's 8 is pulled back to 7 by the untouched even→odd adjust; `min_dim < 7` is unaffected by the constant. Exhaustive value-by-value check. |
| C10 | win_size odd/floor guard clobbered so skimage gets an **even or oversized** window (`%2==0→/2==0`; `%2==0→%3==0`; `max(,3)→None`; `max(,3)→max(,4)`; `win_size=win_size→None`/omitted) | 6 | `detect_changes__mutmut_47`, `_48`, `_51` (+56, _60, _64) | TEST-GAP | Differ exactly for frames with `min_dim ∈ {4, 6}` (e.g. 4×4 → mutant passes win_size 4 or 7): skimage raises "Window size must be odd." / "win_size exceeds image extent." Smallest test frame is 10×10 (`test_very_small_frame`, test:345) — the guard's whole reason to exist is never exercised. Kill: Draft 3. |
| C11 | SSIM `data_range=255` neutralized (`→None`, dropped) or changed (`→256`) | 3 | `detect_changes__mutmut_61`, `_65`, `_66` | TEST-GAP | `_66` shifts every similarity (256² normalization) — loose asserts (`test:148,176,321`) hide it; `_61/_65` are numerically inert for the uint8-only contract (dtype_range derives 255) but silently drop the *explicit* data_range contract skimage's own docs demand (and crash on a float passthrough frame). Kill: Draft 4 (call-arg spy asserts `data_range==255`). |
| C12 | Clamp upper bound `min(1.0, sim)` → `min(2.0, sim)` | 1 | `detect_changes__mutmut_77` | LOW-VALUE | Real change only where SSIM returns >1.0; with uint8 inputs and data_range=255 SSIM ≤ 1.0 in practice (the clamp is a float-precision belt). No producible input distinguishes the variants — an assert could only pin an unreachable value. |
| C13 | Result boolean literal `False` → `None` in `SceneChangeResult(...)` (first-frame `change_detected`, comparison `is_first_frame`) | 2 | `detect_changes__mutmut_19`, `detect_changes__mutmut_81` | TEST-GAP | Existing asserts are truthiness: `assert not result.change_detected` (test:125), `assert not result.is_first_frame` (test:150) — both pass for `None`. JSON payload via `to_dict()` ships `null` instead of `false` to storage consumers. Kill: Draft 2. |
| C14 | `is_first_frame=False,` kwarg dropped from `SceneChangeResult(...)` | 1 | `detect_changes__mutmut_84` | EQUIVALENT | Falls through to the identical dataclass default `is_first_frame: bool = False` (source L32). |
| C15 | Core rule `change_detected = clamped_similarity < self._threshold` → `<=` | 1 | `detect_changes__mutmut_85` | TEST-GAP | At similarity == threshold the mutant flips "no change" to "change". `test_threshold_boundary` (test:229–242) is tautological — it recomputes `expected = result.similarity_score < 0.90` from the result itself. Kill: Draft 1. |

Totals: EQUIVALENT 17 (C1,C2,C3,C4,C8,C9,C14), LOW-VALUE 1 (C12), TEST-GAP 16 (C5,C6,C7,C10,C11,C13,C15). 4+2+6+2+1+1+2+1+1+6+3+1+2+1+1 = 34. ✔

## Drafted tests (to append to backend/tests/unit/services/test_scene_change_detector.py)

// UNVERIFIED - not yet run red/green (per WP4.4 constraint: no test execution in this sandbox).
TDD procedure for each: add test → run against the mutant copy (`uv run pytest backend/tests/unit/services/test_scene_change_detector.py -k <name>` with mutmut variant active) → assert must FAIL on mutant → run against original → must PASS → then fold into the file.

### Draft 1 — kills C15 (`detect_changes__mutmut_85`, `<` → `<=`)

```python
class TestThresholdBoundaryContract:
    """Similarity exactly AT the threshold must not count as a scene change."""

    def test_similarity_exactly_at_threshold_is_not_a_change(
        self,
        detector: SceneChangeDetector,
        sample_frame: np.ndarray,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """< (original): 0.90 < 0.90 is False; mutant <= returns True."""
        import backend.services.scene_change_detector as scd

        detector.detect_changes("cam", sample_frame)
        monkeypatch.setattr(scd, "ssim", lambda *args, **kwargs: 0.90)

        result = detector.detect_changes("cam", sample_frame.copy())

        assert result.similarity_score == pytest.approx(0.90)
        assert result.change_detected is False
```

### Draft 2 — kills C13 (`detect_changes__mutmut_19`, `__mutmut_81`; bool → None)

```python
class TestResultBooleanContract:
    """SceneChangeResult flags are bools, never None (JSON must carry true/false)."""

    def test_first_frame_flags_are_exact_bools(
        self, detector: SceneChangeDetector, sample_frame: np.ndarray
    ) -> None:
        first = detector.detect_changes("camera1", sample_frame)

        assert first.change_detected is False  # mutant: None — `assert not x` missed it
        assert first.is_first_frame is True
        assert first.to_dict()["change_detected"] is False

    def test_comparison_frame_flags_are_exact_bools(
        self, detector: SceneChangeDetector, sample_frame: np.ndarray
    ) -> None:
        detector.detect_changes("camera1", sample_frame)
        second = detector.detect_changes("camera1", sample_frame.copy())

        assert second.is_first_frame is False  # mutant: None
        assert second.change_detected in (True, False)
        assert second.to_dict()["is_first_frame"] is False
```

### Draft 3 — kills C10 (`detect_changes__mutmut_47,48,51,56,60,64`)

```python
class TestSmallFrameWinSizeGuard:
    """Frames below the 7px SSIM window must still produce a result (win_size clamps)."""

    def test_4x4_frames_compare_with_odd_floor_win_size(
        self, detector: SceneChangeDetector, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import backend.services.scene_change_detector as scd
        from skimage.metrics import structural_similarity as real_ssim

        recorded: list[int | None] = []

        def spy(im1: np.ndarray, im2: np.ndarray, **kwargs: object) -> float:
            recorded.append(kwargs.get("win_size"))
            return real_ssim(im1, im2, **kwargs)

        monkeypatch.setattr(scd, "ssim", spy)

        rng = np.random.default_rng(42)
        tiny = rng.integers(0, 256, size=(4, 4), dtype=np.uint8)
        other = rng.integers(0, 256, size=(4, 4), dtype=np.uint8)

        detector.detect_changes("camera1", tiny)  # first frame -> baseline
        result = detector.detect_changes("camera1", other)

        assert isinstance(result, SceneChangeResult)
        assert 0.0 <= result.similarity_score <= 1.0
        # Original clamps 4 -> even -> 3; mutants pass 4 ("Window size must be
        # odd") or 7/None ("win_size exceeds image extent") -> ssim raises.
        assert recorded == [3]
```

### Draft 4 — kills C11 (`detect_changes__mutmut_61,65,66`)

```python
class TestSsimCallContract:
    """SSIM must be called with the explicit uint8 data_range and window."""

    def test_ssim_called_with_explicit_data_range_and_odd_win_size(
        self,
        detector: SceneChangeDetector,
        sample_frame: np.ndarray,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import backend.services.scene_change_detector as scd
        from skimage.metrics import structural_similarity as real_ssim

        seen: dict[str, object] = {}

        def spy(im1: np.ndarray, im2: np.ndarray, **kwargs: object) -> float:
            seen.update(kwargs)
            return real_ssim(im1, im2, **kwargs)

        monkeypatch.setattr(scd, "ssim", spy)

        detector.detect_changes("camera1", sample_frame)
        result = detector.detect_changes("camera1", sample_frame.copy())

        assert seen["data_range"] == 255  # kills None/256/dropped variants
        assert seen["win_size"] == 7  # 100x100 baseline -> default window
        assert result.similarity_score == pytest.approx(1.0, abs=1e-3)
```

### Draft 5 — kills C5 (`__init___mutmut_13`, `<= 0` → `<= 1`)

```python
class TestResizeWidthBoundary:
    """resize_width == 1 is positive and must be accepted."""

    def test_resize_width_one_is_valid(self) -> None:
        detector = SceneChangeDetector(resize_width=1)  # mutant: ValueError (1 <= 1)
        assert detector._resize_width == 1
```

### Draft 6 — kills C7 (`_resize_frame__mutmut_14,16`; LANCZOS → BICUBIC default)

```python
class TestResizeUsesLanczos:
    """Both resize paths must pass Image.Resampling.LANCZOS, not the BICUBIC default."""

    def test_resize_frame_passes_lanczos_on_both_paths(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import PIL.Image

        calls: list[object] = []
        real_resize = PIL.Image.Image.resize

        def spy(
            self_img: PIL.Image.Image,
            size: tuple[int, int],
            resample: int | None = None,
            **kwargs: object,
        ) -> PIL.Image.Image:
            calls.append(resample)
            return real_resize(self_img, size, resample, **kwargs)

        monkeypatch.setattr(PIL.Image.Image, "resize", spy)

        detector = SceneChangeDetector(resize_width=8)
        gray = np.zeros((10, 20), dtype=np.uint8)

        detector._resize_frame(gray, target_size=(5, 5))  # explicit-target path
        detector._resize_frame(gray)  # downscale path (w=20 > resize_width=8)

        assert len(calls) == 2
        assert all(r is PIL.Image.Resampling.LANCZOS for r in calls)
```

### Draft 7 (bonus, kills C6 `_to_grayscale__mutmut_6`)

```python
    def test_grayscale_conversion_requires_both_ndim_and_shape(
        self, detector: SceneChangeDetector
    ) -> None:
        """Object with ndim but no shape must raise ValueError, not pass the guard."""

        class _OnlyNdim:
            ndim = 3

        with pytest.raises(ValueError, match="must be a numpy array"):
            detector._to_grayscale(_OnlyNdim())  # type: ignore[arg-type]
```

## Covering-test weak spots (file:line in backend/tests/unit/services/test_scene_change_detector.py)

- test:87–92 `test_invalid_resize_width` — probes 0/-100 only → C5 gap.
- test:125 / test:150 `assert not result.change_detected` / `assert not result.is_first_frame` — truthiness passes for None → C13 gap.
- test:229–242 `test_threshold_boundary` — recomputes `expected` from the result itself (tautology) → C15 gap; nothing pins equality-at-threshold.
- test:345 `test_very_small_frame` — smallest frame is 10×10; win_size odd/floor guard unexercised below 7px → C10 gap.
- test:321,148,176 `assert 0 <= score <= 1` / `> 0.99` / `< 0.5` — tolerance too loose to see data_range=256 or BICUBIC-vs-LANCZOS pixel drift → C11 (partial), C7 gaps.
- test:521–529 validation tests use inputs lacking both attrs → C6 gap.

## Notes / rulings that could be challenged

- C3/C4/C9/C14/C8 equivalence arguments were checked against installed Pillow/skimage source text, not by execution; if a later wave wants belt-and-braces, Drafts 4+6 already pin `win_size == 7` and `LANCZOS`, which additionally re-verify C9 (mutant still sends 7) and would surface any inference surprise.
- C11 keeps `_61/_65` as TEST-GAP (not EQUIVALENT) on the grounds that the *explicit* `data_range=255` is itself the tested contract (skimage docs warn against dtype-derived ranges; a future float passthrough would crash); Draft 4 is the cheap kill regardless, since it also kills `_66`.
- C12 stays LOW-VALUE: SSIM > 1.0 was not producible under the uint8/data_range=255 contract, so no honest assertion distinguishes the clamp bound.
