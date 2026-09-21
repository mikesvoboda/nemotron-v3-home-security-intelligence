# WP4.4 Triage Dossier — backend/services/frame_extractor.py

- **Survivors:** 27 of 132 checked (105 killed, 0 un-checked). Source: `mutants/backend/services/frame_extractor.py.meta` (`exit_code_by_key`, exit_code 0 = survived).
- **Covering test file:** `backend/tests/unit/services/test_frame_extractor.py` (main tree). Mutants-tree copy `mutants/backend/tests/unit/services/test_frame_extractor.py` verified **byte-identical (IN-SYNC)** at 2026-09-19 — but per the stale-mutants-tree protocol, any drafted tests must be copied into the mutants tree before kill-probes run there.
- **Diffs collected via** `uv run mutmut show <key>` (all 27 succeeded; raw dump at `/tmp/wp25/wp44-triage/fe_survivor_diffs.txt`).
- **Verified environment facts used in classifications:** on a `Mock`, `hasattr(m, "_mock_name") == hasattr(m, "XX_mock_nameXX") == hasattr(m, "_MOCK_NAME") == hasattr(m, "assert_called") == True` (auto-attribute), so the `_is_mock` attr-name mutants are only observable on non-auto-attr objects; and `np.count_nonzero(empty)/empty.size` yields `nan` (RuntimeWarning, no exception), `bool(nan > t) == False` — so the empty-mask guard mutants survive by *coincidentally* returning False, and are killable only with single-element (size-1) inputs.

## Cluster table (counts sum to 27)

| # | Cluster (pattern) | Count | Keys (≤3 examples) | Class | Why |
|---|---|---|---|---|---|
| C1 | `save_frame`: `cv2.imwrite` path argument clobbered to `None` / `str(None)` | 2 | `save_frame__mutmut_18`, `save_frame__mutmut_22` | TEST-GAP | `test_save_frame_calls_cv2_imwrite` (test file :340-341) asserts only `call_args[1]` (the frame), never `call_args[0]` (the path). `cv2.imwrite` is always mocked to return True, so a None-path write is invisible. Production impact: every frame written to literal path `"None"`. |
| C2 | `save_frame`: strftime filename format string clobbered (`"XX%Y%m%d_%H%M%SXX"`) | 1 | `save_frame__mutmut_12` | TEST-GAP | `test_save_frame_uses_timestamp_in_filename` (:306) uses a substring check `"20250129" in file_path` — the mutant filename `XX20250129_123045XX_123456.jpg` still contains the substring. No exact-filename assertion. |
| C3 | `save_frame`: `mkdir(parents=True, exist_ok=True)` kwargs weakened (`parents=None/False/omitted`; `exist_ok=None/False/omitted`) | 6 | `save_frame__mutmut_3`, `_5`, `_7` (parents); `_4`, `_6`, `_8` (exist_ok) | TEST-GAP | `test_save_frame_creates_camera_directory` (:253-270) uses `tmp_path` whose parent already exists and calls `save_frame` exactly once — so `parents=False` and `exist_ok=False` are both never stressed. Production impact: crash (FileNotFoundError) when `frame_save_dir` doesn't pre-exist, and crash (FileExistsError) on the *second* motion frame for the same camera. |
| C4 | `detect_motion`: empty-input guards weakened (`frame.size == 0`→`== 1`, `fg_mask.size == 0`→`== 1`, `return False`→`return True`) | 3 | `detect_motion__mutmut_2`, `_3`, `_8` | TEST-GAP | `test_motion_detection_with_empty_frame` (:588-603) only asserts `isinstance(result, bool)` — a vacuous assertion that any bool satisfies. `mutmut_3` (returns True on empty frame) passes it; `mutmut_2`/`_8` survive because tests never pass a size-1 frame/mask (with an empty *mask* they return False anyway via `nan > t == False`, so only a **size-1 input** distinguishes them). |
| C5 | `detect_motion`: motion-ratio comparison `>` → `>=` (threshold boundary) | 1 | `detect_motion__mutmut_13` | TEST-GAP | Existing behavior tests use ratio 0.5 vs threshold 0.25 (:124-142) — far from the boundary. `>` vs `>=` differs only when `motion_ratio == _motion_threshold` exactly; no test constructs that. |
| C6 | `__init__`: sensitivity range boundary flips (`0.0 <=` → `0.0 <`; `<= 1.0` → `< 1.0`) | 2 | `__init____mutmut_3`, `__init____mutmut_4` | TEST-GAP | `test_init_validates_motion_sensitivity_range` (:69-80) tests only -0.1 and 1.1; the *valid* endpoints 0.0 and 1.0 are never constructed (docstring explicitly defines them as valid: "0.0 = lowest sensitivity ... 1.0 = highest"). |
| C7 | `__init__`: threshold curve exponent `(1.0 - s) ** 2` → `** 3` | 1 | `__init____mutmut_20` | TEST-GAP | `test_motion_detection_threshold_calculation` (:618-630) asserts only `> 0.5` / `< 0.5` — 0.81 vs 0.729 and 0.01 vs 0.001 both pass. The actual documented curve (docstring: "sensitivity 0.1 -> threshold 0.81") is never asserted. |
| C8 | Error-message text mutations (`__init__` ValueError message XX-wrapped; `extract_frame` None-frame message → `None` / XX-wrapped / lowercase / uppercase) | 5 | `__init____mutmut_7`, `extract_frame__mutmut_2`, `extract_frame__mutmut_3` | LOW-VALUE | Real change, but message wording is behavior nobody should assert. `test_extract_frame_with_none_frame_raises_error` (:615) accepts `(ValueError, TypeError)` with no message match; the init test's `pytest.raises(match=r"motion_sensitivity must be between 0\.0 and 1\.0")` is a *search*-match and the XX-wrapped message still contains the substring. Asserting exact exception prose is brittle test-generality, not a product gap. |
| C9 | `_is_mock`: mock-marker argument/attribute-name mutations (`hasattr(obj, ...)` → `hasattr(None, ...)`; `"_mock_name"` → `"XX_mock_nameXX"` / `"_MOCK_NAME"`) | 3 | `_is_mock__mutmut_2`, `_is_mock__mutmut_6`, `_is_mock__mutmut_7` | TEST-GAP | The helper is only executed indirectly through `Mock` objects (auto-attribute makes all marker names True, verified above), so every existing test sees identical results. A plain object carrying only `_mock_name` (a partial/spec'd mock marker) is misclassified by all three mutants. No test calls `_is_mock` directly or uses a marker-only object. |
| C10 | `_MOG2Wrapper.__init__` stores `None` instead of the subtractor; `_create_subtractor` wraps `None` | 2 | `_MOG2Wrapper__init____mutmut_1`, `_create_subtractor__mutmut_3` | TEST-GAP | `test_init_creates_mog2_background_subtractor` (:55-67) patches the cv2 factory with a Mock, so `_is_mock` is True and the *raw* Mock is returned — the wrapper-storage line is executed on the unpatched path only in unrelated inits and never asserted (`._subtractor` is never read). Mutant would crash real motion detection (`None.apply`). |
| C11 | `_get_camera_subtractor`: defensive `getattr(..., "apply", None)` default dropped (2-arg `getattr`, raises `AttributeError` when attr missing) | 1 | `_get_camera_subtractor__mutmut_7` | EQUIVALENT | Dead defensive tweak: every real path (`_MOG2Wrapper`, cv2 subtractor, Mock, bound method) has `.apply`, so the `None` default is unreachable in any real or test configuration; the `bg_apply is not None` guard becomes vestigial but the code path is behaviorally identical for all inputs that can occur. Killing it would require fabricating an extractor whose `_bg_subtractor` lacks `apply` — an object the constructor can never produce. |

**Sums:** 2+1+6+3+1+2+1+5+3+2+1 = **27**. TEST-GAP: 18 mutants (C1,C2,C3,C4,C5,C6,C7,C9,C10) · LOW-VALUE: 5 (C8) · EQUIVALENT: 1 (C11).

## Drafted tests (UNVERIFIED — not yet run red/green)

Append to `backend/tests/unit/services/test_frame_extractor.py` (then copy the file into the mutants tree before probing). Follows file style: local import inside test, `Mock`/`patch`/`autospec`, `tmp_path`.

**TDD procedure (one line each):** run the new test against the mutants tree copy → assert fails on the cluster's mutant diff; run against original `backend/services/frame_extractor.py` → passes.

### T1 — `save_frame` directory creation: nested base dir + repeat saves  [kills C3: save_frame__mutmut_3,_4,_5,_6,_7,_8]

```python
class TestFrameExtractorSaveFrameDirectorySemantics:
    """save_frame must create the full directory chain and tolerate re-saves."""

    def test_save_frame_creates_missing_parent_directories(self, tmp_path) -> None:
        """save_frame should create frame_save_dir and its parents when missing (parents=True)."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        missing_base = tmp_path / "does" / "not" / "exist"
        extractor = FrameExtractor(redis_client=mock_redis, frame_save_dir=str(missing_base))

        frame = np.zeros((4, 4, 3), dtype=np.uint8)
        timestamp = datetime(2025, 1, 29, 12, 30, 45, 123456)

        with patch("cv2.imwrite", autospec=True) as mock_imwrite:
            mock_imwrite.return_value = True
            file_path = extractor.save_frame("camera1", frame, timestamp)

        assert (missing_base / "camera1").is_dir()
        assert Path(file_path).parent == missing_base / "camera1"

    def test_save_frame_twice_to_same_camera_does_not_raise(self, tmp_path) -> None:
        """save_frame should reuse an existing camera directory without FileExistsError (exist_ok=True)."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        extractor = FrameExtractor(redis_client=mock_redis, frame_save_dir=str(tmp_path))

        frame = np.zeros((4, 4, 3), dtype=np.uint8)
        ts1 = datetime(2025, 1, 29, 12, 30, 45, 123456)
        ts2 = datetime(2025, 1, 29, 12, 31, 0, 0)

        with patch("cv2.imwrite", autospec=True) as mock_imwrite:
            mock_imwrite.return_value = True
            first = extractor.save_frame("camera1", frame, ts1)
            second = extractor.save_frame("camera1", frame, ts2)  # mutant (exist_ok=False) raises here

        assert Path(first).parent == Path(second).parent == tmp_path / "camera1"
        assert first != second
```

*Kill mechanics:* `parents=None/False/omitted` → `FileNotFoundError` in test 1 (base dir chain missing). `exist_ok=None/False/omitted` → `FileExistsError` on the second `save_frame` in test 2. Original passes both.

### T2 — `detect_motion` guard semantics: empty vs single-element inputs  [kills C4: detect_motion__mutmut_2,_3,_8]

```python
    def test_detect_motion_empty_frame_returns_false_without_subtractor_call(self) -> None:
        """detect_motion should return exactly False for an empty frame and never touch the subtractor."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        extractor = FrameExtractor(redis_client=mock_redis)
        frame = np.zeros((0, 0, 3), dtype=np.uint8)

        with patch.object(extractor._bg_subtractor, "apply", autospec=True) as mock_apply:
            mock_apply.return_value = np.zeros((0, 0), dtype=np.uint8)
            result = extractor.detect_motion(frame, camera_id="camera1")

        assert result is False          # kills detect_motion__mutmut_3 (returns True)
        mock_apply.assert_not_called()  # kills detect_motion__mutmut_2 (guard skipped, apply called)

    def test_detect_motion_single_element_frame_is_processed_normally(self) -> None:
        """A size-1 (non-empty) frame is valid input and must go through motion detection, not the empty guard."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        extractor = FrameExtractor(redis_client=mock_redis, motion_sensitivity=0.5)
        frame = np.array([[[255, 255, 255]]], dtype=np.uint8)  # frame.size == 1

        with patch.object(extractor._bg_subtractor, "apply", autospec=True) as mock_apply:
            mock_apply.return_value = np.array([[255]], dtype=np.uint8)  # mask size == 1, fully "motion"
            result = extractor.detect_motion(frame, camera_id="camera1")

        # Original: 1.0 > 0.25 -> True. Mutant mutmut_2 (==1 guard) returns False.
        assert result is True

    def test_detect_motion_single_pixel_mask_is_not_treated_as_empty(self) -> None:
        """A size-1 foreground mask with a nonzero pixel is motion (ratio 1.0), not an empty-mask bail-out."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        extractor = FrameExtractor(redis_client=mock_redis, motion_sensitivity=0.5)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        with patch.object(extractor._bg_subtractor, "apply", autospec=True) as mock_apply:
            mock_apply.return_value = np.array([[255]], dtype=np.uint8)  # fg_mask.size == 1
            result = extractor.detect_motion(frame, camera_id="camera1")

        assert result is True  # kills detect_motion__mutmut_8 (==1 guard returns False)
```

*Kill mechanics:* verified that the empty-mask mutants return False via `nan > t == False`, which is why size-1 inputs (not empty ones) are the distinguishing vectors. Original passes: empty frame short-circuits; size-1 frame/mask gives ratio 1.0 > 0.25.

### T3 — `save_frame` exact filename + exact `cv2.imwrite` path argument  [kills C1: save_frame__mutmut_18,_22 and C2: save_frame__mutmut_12]

```python
    def test_save_frame_passes_exact_resolved_path_to_imwrite(self, tmp_path) -> None:
        """cv2.imwrite must receive the exact YYYYMMDD_HHMMSS_microseconds.jpg path under the camera dir."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        extractor = FrameExtractor(redis_client=mock_redis, frame_save_dir=str(tmp_path))

        frame = np.zeros((4, 4, 3), dtype=np.uint8)
        timestamp = datetime(2025, 1, 29, 12, 30, 45, 123456)
        expected_name = "20250129_123045_123456.jpg"

        with patch("cv2.imwrite", autospec=True) as mock_imwrite:
            mock_imwrite.return_value = True
            file_path = extractor.save_frame("camera1", frame, timestamp)

            # Path argument of cv2.imwrite — existing test only checks arg[1] (the frame).
            (written_path, _), _ = mock_imwrite.call_args.args, mock_imwrite.call_args.kwargs
            assert written_path == str(tmp_path / "camera1" / expected_name)

        assert Path(file_path).name == expected_name  # kills the XX-wrapped strftime format
```

*Kill mechanics:* `imwrite(None, ...)` / `imwrite(str(None), ...)` → written_path `"None"` ≠ expected (kills 18, 22); `"XX%Y%m%d_%H%M%SXX"` → name `"XX20250129_123045XX_123456.jpg"` ≠ expected (kills 12). Existing substring assertion at :306 was too weak to catch the wrap.

### T4 — motion-threshold curve exactness + boundary comparison  [kills C5: detect_motion__mutmut_13 and C7: __init____mutmut_20]

```python
    def test_motion_threshold_follows_documented_squared_curve(self) -> None:
        """_motion_threshold must be exactly (1.0 - sensitivity) ** 2 per the class docstring."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        for sensitivity, expected in [(0.0, 1.0), (0.1, 0.81), (0.5, 0.25), (0.9, 0.01)]:
            extractor = FrameExtractor(redis_client=mock_redis, motion_sensitivity=sensitivity)
            assert extractor._motion_threshold == pytest.approx(expected)  # kills **3 mutant

    def test_detect_motion_at_exact_threshold_boundary_is_false(self) -> None:
        """Motion ratio EQUAL to the threshold is NOT motion: comparison is strict >."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        # sensitivity 0.0 -> threshold (1-0)**2 == 1.0 exactly
        extractor = FrameExtractor(redis_client=mock_redis, motion_sensitivity=0.0)

        frame = np.zeros((8, 8, 3), dtype=np.uint8)
        with patch.object(extractor._bg_subtractor, "apply", autospec=True) as mock_apply:
            mock_apply.return_value = np.full((8, 8), 255, dtype=np.uint8)  # ratio exactly 1.0 == threshold
            result = extractor.detect_motion(frame, camera_id="camera1")

        assert result is False  # original: 1.0 > 1.0 -> False; >= mutant: True
```

*Kill mechanics:* the `pytest.approx` table distinguishes `**2` from `**3` at every row (0.81≠0.729, 0.25≠0.125, 0.01≠0.001). The boundary test pins ratio==threshold to False, killing `>=`. Original passes both.

### T5 — sensitivity range endpoints are valid  [kills C6: __init____mutmut_3,_4]

```python
    def test_init_accepts_sensitivity_range_endpoints(self) -> None:
        """Sensitivity 0.0 and 1.0 are documented as valid and must construct without ValueError."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()

        low = FrameExtractor(redis_client=mock_redis, motion_sensitivity=0.0)   # kills 0.0<= -> 0.0<
        assert low.motion_sensitivity == 0.0
        high = FrameExtractor(redis_client=mock_redis, motion_sensitivity=1.0)  # kills <=1.0 -> <1.0
        assert high.motion_sensitivity == 1.0

        # Guard against over-loosening: just outside the range still raises.
        with pytest.raises(ValueError):
            FrameExtractor(redis_client=mock_redis, motion_sensitivity=-0.001)
        with pytest.raises(ValueError):
            FrameExtractor(redis_client=mock_redis, motion_sensitivity=1.001)
```

### T6 — testability-helper contracts: `_is_mock` markers and subtractor wrapping  [kills C9: _is_mock__mutmut_2,_6,_7 and C10: _MOG2Wrapper__init____mutmut_1, _create_subtractor__mutmut_3]

```python
class TestFrameExtractorTestabilityHelpers:
    """_is_mock / _create_subtractor / _MOG2Wrapper contracts, asserted directly."""

    def test_is_mock_detects_either_marker(self) -> None:
        """_is_mock should return True for objects carrying _mock_name OR assert_called, False otherwise."""
        from types import SimpleNamespace

        from backend.services.frame_extractor import _is_mock

        assert _is_mock(Mock()) is True                        # real Mock: both markers
        assert _is_mock(SimpleNamespace(_mock_name="x")) is True   # kills mutmut_2/6/7 (marker renamed/dead)
        assert _is_mock(SimpleNamespace(assert_called=lambda: None)) is True
        assert _is_mock(SimpleNamespace()) is False
        assert _is_mock(object()) is False

    def test_mog2_wrapper_stores_and_delegates_subtractor(self) -> None:
        """_MOG2Wrapper must store the given subtractor and delegate apply() to it."""
        from backend.services.frame_extractor import _MOG2Wrapper

        class StubSubtractor:
            def __init__(self) -> None:
                self.calls = []

            def apply(self, frame):
                self.calls.append(frame)
                return frame

        stub = StubSubtractor()
        wrapper = _MOG2Wrapper(stub)

        assert wrapper._subtractor is stub  # kills _MOG2Wrapper__init____mutmut_1 (stores None)
        frame = np.zeros((2, 2, 3), dtype=np.uint8)
        np.testing.assert_array_equal(wrapper.apply(frame), frame)
        assert stub.calls == [frame]

    def test_create_subtractor_wraps_non_mock_factory_result(self) -> None:
        """_create_subtractor must wrap a real (non-Mock) subtractor, retaining it inside the wrapper."""
        from types import SimpleNamespace

        from backend.services.frame_extractor import _MOG2Wrapper, _create_subtractor

        stub = SimpleNamespace(apply=lambda frame: frame)  # deliberately NOT a Mock (no auto-attrs)
        with patch("cv2.createBackgroundSubtractorMOG2", autospec=True) as mock_factory:
            mock_factory.return_value = stub
            subtractor = _create_subtractor()

        assert isinstance(subtractor, _MOG2Wrapper)
        assert subtractor._subtractor is stub  # kills _create_subtractor__mutmut_3 (wraps None)
```

*Kill mechanics:* `_is_mock(SimpleNamespace(_mock_name=...))` is True on original, False under mutmut_2 (`hasattr(None, ...)`) and mutmut_6/7 (renamed marker) — verified Mock's auto-attribute makes existing tests blind here. The stub-based `_create_subtractor` test exercises the previously-never-taken `else` branch: on the mutant the wrapper holds `None`, failing identity. `_MOG2Wrapper(stub)._subtractor is stub` kills the None-store.

## Weak-assertion index (what the existing tests miss)

| Test file : line | Weakness |
|---|---|
| test_frame_extractor.py:306 | substring `"20250129" in file_path` — survives format-string wrapping (C2) |
| test_frame_extractor.py:340-341 | checks only imwrite arg[1]; never arg[0] path (C1) |
| test_frame_extractor.py:253-270 | dir test uses pre-existing `tmp_path` parent, single call (C3) |
| test_frame_extractor.py:603 | `isinstance(result, bool)` is vacuous (C4) |
| test_frame_extractor.py:142,179,199 | ratios far from threshold; boundary never probed (C5) |
| test_frame_extractor.py:76-80 | range test uses -0.1/1.1 only; 0.0/1.0 endpoints never constructed (C6) |
| test_frame_extractor.py:626,630 | `> 0.5` / `< 0.5` tolerates any exponent (C7) |
| test_frame_extractor.py:615 | `pytest.raises((ValueError, TypeError))` with no message (C8, accepted as-is) |
| test_frame_extractor.py:67 | asserts Mock-path passthrough only; wrapper storage never read (C10) |

## Notes / rulings

- **C8 stays LOW-VALUE deliberately.** Killing the 5 message mutants would mean pinning exact exception prose in `pytest.raises(match=...)` (or `str(excinfo.value) ==`), which is test-generality churn the WP4.4 batch ruling has historically classified LOW-VALUE; the init-message mutant even *defeats* the existing regex because `match` is a search. Do not spend assertion budget here.
- **C11 EQUIVALENT ruling:** the `getattr(..., "apply", None)` default is a dead defensive tweak — every constructor-reachable `_bg_subtractor` (cv2 object, `_MOG2Wrapper`, Mock, or patched method) has `.apply`. A kill probe would need a hand-corrupted instance; not a test gap anyone should fill.
- **Empty-mask `nan` discovery** (verified with the project's numpy): `0/0` in scalar numpy division is `nan` + RuntimeWarning, not an exception, and `bool(nan > t)` is False. This is *why* C4's `mutmut_2`/`mutmut_8` survived the empty-frame test (coincidental False) and dictates the size-1-input kill vectors in T2. If the project ever enables `filterwarnings = error` in pytest config, the empty-mask mutants would additionally die on the RuntimeWarning — do not count on that.
- **Mutants-tree sync:** test copy verified IN-SYNC today (`diff -q` clean); after landing T1-T6 in the main tree, copy `backend/tests/unit/services/test_frame_extractor.py` into `mutants/backend/tests/unit/services/` before running kill-probes, or the census silently records 0 kills (stale-tree protocol from wave-66).
- Kill coverage of drafted tests: T1→6, T2→3, T3→3, T4→2, T5→2, T6→5 = **21 of 27** survivors; the remaining 6 are the deliberately-unasserted C8 (5) and C11 (1).
