# WP4.4 Triage Dossier — backend/services/smoke_fire_loader.py

Survivors: **135** of 207 checked (72 killed, 78 not yet checked).
Diffs: `uv run mutmut show <key>` (all 135 captured cleanly; 2 keys needed a retry for concurrent-cache JSON races, both recovered).
Covering test file (sole): `backend/tests/unit/services/test_smoke_fire_loader.py`
(plus indirect execution via `test_enrichment_pipeline*.py`, which mocks the loader wholesale — no asserts on these lines).

## Context: why so many survivors are mock-shaped

Every loader/detection test patches `backend.services.smoke_fire_loader.YOLO` with a **plain
MagicMock** (the test file comments at :107-112 explain why autospec is avoided). Consequences:

1. `is_mock = hasattr(yolo_class, "_mock_name") or hasattr(yolo_class, "assert_called")`
   is always **True** via the second arm → the real weights-discovery branch
   (`model.pt` → `best.pt` → `smoke-fire-yolov8n.pt` → `glob("*.pt")`) **never executes**.
2. The returned model is a MagicMock, so `hasattr(model,"model")`/`getattr`/`is_fused`
   probes are trivially satisfied and the code always lands on `model.fuse()` — the same
   outcome as the original for every fuse-path mutant.
3. Context-formatting tests use **single-detection inputs** and **case-insensitive
   `in` asserts** (`test_smoke_fire_loader.py:406`, `:568`, `:587-588`, `:607`), so sort
   order, `[:5]` cap, priority markers, casing, and the time-of-day block are never pinned.

The batch tests (`:524-551`) use `boxes=None` results and never inspect `predict()` kwargs.

## Cluster table (counts sum to 135)

| # | Cluster | Fn | Ctx | N | Class | Examples |
|---|---------|----|-----|---|-------|----------|
| L1 | `logger.info` message args → None/text in `load_smoke_fire_model` | load | 200/252/257 | 3 | EQUIVALENT | _3, _73, _78 |
| L2 | ImportError/Exception handler log message text (XX/case/None) | load | 261, 268 | 12 | EQUIVALENT | _80, _85, _94 |
| L3 | Error-log kwargs (`exc_info` True→False/None/removed, `extra={"model_path":…}`) | load | 269-270 | 7 | EQUIVALENT | _88, _92, _96 |
| L4 | Weights filename text mutations (`model.pt`/`best.pt`/`smoke-fire-yolov8n.pt` XX-wrapped/case) — resolved path never observed under MagicMock | load | 225-232 | 8 | EQUIVALENT | _24, _28, _33 |
| L5 | Pre-fuse path probes (`hasattr "fuse"/"is_fused"` text, `getattr(model,"model")`→None/None-arg, boolean rewrites) — mock model lands on `else: model.fuse()` for ALL variants (incl. `is not None`→`is None` _65 and `and`→`or` _64); behaviorally inert even with a real model | load | 244-250 | 10 | EQUIVALENT | _56, _64, _70 |
| L6 | Lazy-import assignment `YOLO = _YOLO` → None — module global never read back (tests always patch it) | load | 198 | 1 | EQUIVALENT | _2 |
| L7 | `is_mock` mock-detection predicate mutants (`or`→`and`, `yolo_class`→None, attribute-name text, `hasattr` arity) — only the `_mock_name` arm ever executes | load | 221 | 10 | **TEST-GAP** | _9, _16, _20 |
| L8 | `model_dir.glob("*.pt")` pattern text/None — final-fallback branch never entered | load | 235 | 4 | **TEST-GAP** | _43, _44, _45 |
| L9 | Weights fallback chain mutants (`if not weights_file.exists()`→`if exists` ×3, `/`→`*` ×3, assignments→None, FileNotFoundError msg→None) — real branch never entered because mocked YOLO ⇒ `is_mock` True | load | 228-239 | 11 | **TEST-GAP** | _27, _30, _40 |
| F1 | `format_smoke_fire_context(None)` sentinel text (`"Smoke/Fire detection: Not performed"` case/XX) | fmt | 451 | 3 | EQUIVALENT | _2, _3, _4 |
| F2 | No-detections sentinel text (`"Smoke/Fire detection: No smoke or fire detected"` — test only asserts `"no" in result.lower()`) | fmt | 454 | 3 | **TEST-GAP** | _5, _6, _7 |
| F3 | Fire/smoke alert BODY text in `format_smoke_fire_context` (`IMMEDIATE EVACUATION…`, `Contact emergency services…`, `Potential fire hazard…`) — never executed: only a 1-detection smoke case exists | fmt | 460-464 | 8 | EQUIVALENT | _11, _14, _22 |
| F4 | SMOKE header text (`**SMOKE DETECTION ALERT**` XX/case — test asserts `"SMOKE" in context.upper()`) | fmt | 463 | 3 | EQUIVALENT | _18, _19, _20 |
| F5 | FIRE header text (`**CRITICAL FIRE ALERT**` XX/case — test asserts `"CRITICAL" in context.upper()`) | fmt | 459 | 3 | EQUIVALENT | _8, _9, _10 |
| F6 | Confidence-desc `sorted(..., key=lambda d: d.confidence, reverse=True)` mutants in `format_...` (`key`→None, `reverse`→None/False, removal) — single-detection input makes sort unobservable | fmt | 468 | 6 | **TEST-GAP** | _27, _30, _32 |
| F7 | Detail-list cap `[:5]` → `[:6]` | fmt | 469 | 1 | **TEST-GAP** | _33 |
| F8 | `" **HIGH PRIORITY**"` marker in `format_...` (condition const `and False`/`or True`, both arms →None/`"XXXX"`, marker text case) | fmt | 471 | 6 | **TEST-GAP** | _34, _36, _39 |
| F9 | `detection.detection_type.upper()`→`.lower()` in per-detection line | fmt | 473 | 2 | **TEST-GAP** | _41, _43 |
| F10 | Time-of-day tuple mutants (`"night"/"late_night"/"early_morning"` XX/case) + `.lower()`→`.upper()` on the probe | fmt | 477 | 6 | **TEST-GAP** | _43, _46, _48 |
| F11 | Night-escalation block: `in` → `not in` tuple membership (_44) + join separator `"\n"`→`"XX\nXX"` (_52) — escalation block never executed by any test | fmt | 477-481 | 2 | **TEST-GAP** | _44, _52 |
| T1 | `to_context_string` `if not self.has_detections:` flip — unreachable: function returns before the mutated line | tcs | 142 | 1 | EQUIVALENT | _1 |
| T2 | FIRE header text (`**CRITICAL FIRE ALERT**`) | tcs | 148 | 3 | EQUIVALENT | _4, _5, _6 |
| T3 | Fire body text (`IMMEDIATE ACTION REQUIRED!`) | tcs | 149 | 2 | EQUIVALENT | _7, _8 |
| T4 | SMOKE header text (`**SMOKE DETECTION ALERT**`) | tcs | 151 | 2 | EQUIVALENT | _12, _13 |
| T5 | Confidence-desc sort mutants (key→None, key removed, `reverse`→None/False) — single-detection input | tcs | 153 | 6 | **TEST-GAP** | _11, _14, _16 |
| T6 | `" [HIGH PRIORITY]"` marker mutants (condition const, both arms →None/`"XXXX"`, text case) | tcs | 154 | 6 | **TEST-GAP** | _17, _19, _22 |
| T7 | `detection_type.upper()`→`.lower()` + join `"\n"`→`"XX\nXX"` | tcs | 156, 160 | 2 | **TEST-GAP** | _24, _26 |
| B1 | `model.predict(source=images, conf=confidence_threshold, verbose=False)` kwargs in `_detect_batch` (source→None/removed, conf→None/removed, verbose→None/True/removed) — batch tests never assert call args (unlike single-image `test_detect_respects_confidence_threshold` :487-499) | batch | 384-388 | 7 | **TEST-GAP** | _4, _5, _10 |
| B2 | `len(result.boxes) > 0` guard flips (`>= 0`, `> 1`) — single-box or boxes=None results only | batch | 395 | 2 | **TEST-GAP** | _15, _16 |
| B3 | Defensive crash mutants (`detections=[]`→None, `append(None)`, `detections=None`) — produce TypeError/None-list, i.e. loud crashes no caller contracts on | batch | 393, 426 | 3 | LOW-VALUE | _12, _17, _18 |

Totals: 66 (load: 66 = 41 EQUIVALENT + 25 TEST-GAP) · 38 (format: 17 EQUIVALENT + 21 TEST-GAP) ·
19 (to_context_string: 8 EQUIVALENT + 11 TEST-GAP) · 12 (batch: 7+2 TEST-GAP + 3 LOW-VALUE).
By class: **EQUIVALENT 66 · TEST-GAP 66 · LOW-VALUE 3 = 135.**

### Judgment notes

- **EQUIVALENT (66):** pure logger message/kwargs text (L1-L3), message text in code paths the
  current tests never enter or assert only case-insensitively (F1, F3-F5, T2-T4), mock-probe
  short-circuits where every mutant produces identical control flow (L5, L6), unreachable
  guard (T1), and filename text under mocked path resolution (L4 — killable for free by
  Draft-6's exact-path assert).
- **L5 is EQUIVALENT, not TEST-GAP, even though it guards the thread-safety fuse contract:**
  with the MagicMock model used in tests, `getattr(model,"model")` returns a truthy auto-child
  for BOTH original and mutants, and that child's `is_fused()` returns a truthy MagicMock, so
  `if not inner_model.is_fused(): model.fuse()` never fires — `model.fuse()` is reached via
  the `else` branch for original and all 10 mutants identically. A real-model pin (fuse called
  exactly once when `is_fused()` False) would need fakes, but the surviving mutants cannot
  flip that outcome; the residual (never-fuse race bug) is out of mutant scope.
- **B2 caveat:** `_15` (`>0`→`>=0`) is not killable by any input (empty vs zero boxes behave
  identically at loop level); `_16` (`>1`) is killed by Draft-5's single-box result.
- **Covering asserts to fix in place** (weaker than they look): `:406` `assert "FIRE" in
  context.upper() or "CRITICAL" in context.upper()`; `:568` `assert "not performed" in
  result.lower() or "no" in result.lower()`; `:587-588` / `:607` same case-folded pattern.

## Drafted tests (append to `backend/tests/unit/services/test_smoke_fire_loader.py`)

// UNVERIFIED - not yet run red/green. TDD procedure per test: run against mutant → assert
fails (assertion or expected TypeError/RuntimeError shape changes); run against original → passes.

```python
# ===========================================================================
# Test: Strict contracts for LLM context formatting (WP4.4 survivor kill-set)
# ===========================================================================


class TestFormatSmokeFireContextStrict:
    """Exact-string contracts for format_smoke_fire_context.

    Existing tests assert case-folded substrings on single-detection inputs,
    which lets sort order, the [:5] cap, priority markers, casing, sentinel
    strings, and the night-escalation block mutate silently.
    """

    def test_lists_detections_highest_first_with_priority_and_cap(self) -> None:
        from backend.services.smoke_fire_loader import (
            SmokeFireDetection,
            SmokeFireDetectionResult,
            format_smoke_fire_context,
        )

        def det(kind: str, conf: float) -> SmokeFireDetection:
            return SmokeFireDetection(detection_type=kind, confidence=conf, bbox=(0, 0, 1, 1))

        result = SmokeFireDetectionResult(
            detections=[
                det("smoke", 0.85),   # last listed, boundary HIGH
                det("fire", 0.95),    # highest
                det("smoke", 0.50),   # LOW
                det("fire", 0.72),    # fire is always HIGH
                det("smoke", 0.90),
                det("smoke", 0.84),   # LOW (< 0.85)
            ]
        )

        context = format_smoke_fire_context(result)

        # Exact rendering pins: header text, confidence-desc sort, [:5] cap
        # (the 0.84 smoke must be dropped), uppercase type, and the
        # " **HIGH PRIORITY**" marker on exactly the high-priority rows.
        assert context == (
            "**CRITICAL FIRE ALERT**\n"
            "  IMMEDIATE EVACUATION RECOMMENDED!\n"
            "  Contact emergency services immediately.\n"
            "  Highest confidence: 95%\n"
            "    - FIRE (95%) **HIGH PRIORITY**\n"
            "    - SMOKE (90%) **HIGH PRIORITY**\n"
            "    - SMOKE (85%) **HIGH PRIORITY**\n"
            "    - FIRE (72%) **HIGH PRIORITY**\n"
            "    - SMOKE (50%)"
        )

    def test_no_detections_sentinel_is_exact(self) -> None:
        from backend.services.smoke_fire_loader import (
            SmokeFireDetectionResult,
            format_smoke_fire_context,
        )

        assert format_smoke_fire_context(None) == "Smoke/Fire detection: Not performed"
        assert (
            format_smoke_fire_context(SmokeFireDetectionResult())
            == "Smoke/Fire detection: No smoke or fire detected"
        )

    def test_night_escalation_and_daytime_negative(self) -> None:
        from backend.services.smoke_fire_loader import (
            SmokeFireDetection,
            SmokeFireDetectionResult,
            format_smoke_fire_context,
        )

        result = SmokeFireDetectionResult(
            detections=[SmokeFireDetection(detection_type="fire", confidence=0.9, bbox=(0, 0, 1, 1))]
        )

        for tod in ("night", "late_night", "early_morning"):
            context = format_smoke_fire_context(result, time_of_day=tod)
            assert f"  TIME CONTEXT: Detection during {tod}" in context
            assert "Elevated concern" in context

        # Daytime must NOT add the escalation block (kills `in` -> `not in`).
        daytime = format_smoke_fire_context(result, time_of_day="afternoon")
        assert "TIME CONTEXT" not in daytime

        # None time_of_day must be silent too.
        assert "TIME CONTEXT" not in format_smoke_fire_context(result)


class TestSmokeFireResultContextStringStrict:
    """Exact-string contracts for SmokeFireDetectionResult.to_context_string."""

    def test_smoke_context_string_ordering_priority_and_join(self) -> None:
        from backend.services.smoke_fire_loader import (
            SmokeFireDetection,
            SmokeFireDetectionResult,
        )

        result = SmokeFireDetectionResult(
            detections=[
                SmokeFireDetection(detection_type="smoke", confidence=0.60, bbox=(0, 0, 1, 1)),
                SmokeFireDetection(detection_type="smoke", confidence=0.90, bbox=(0, 0, 1, 1)),
            ]
        )

        assert result.to_context_string() == (
            "**SMOKE DETECTION ALERT**\n"
            "  - SMOKE: 90% confidence [HIGH PRIORITY]\n"
            "  - SMOKE: 60% confidence"
        )

    def test_fire_context_string_exact(self) -> None:
        from backend.services.smoke_fire_loader import (
            SmokeFireDetection,
            SmokeFireDetectionResult,
        )

        result = SmokeFireDetectionResult(
            detections=[SmokeFireDetection(detection_type="fire", confidence=0.80, bbox=(0, 0, 1, 1))]
        )

        assert result.to_context_string() == (
            "**CRITICAL FIRE ALERT**\n"
            "  IMMEDIATE ACTION REQUIRED!\n"
            "  - FIRE: 80% confidence [HIGH PRIORITY]"
        )


class TestDetectSmokeFireBatchStrict:
    """Batch path must forward predict kwargs and handle a real single-box result."""

    @pytest.mark.asyncio
    async def test_batch_predict_kwargs_and_single_box_detection(self) -> None:
        from backend.services.smoke_fire_loader import detect_smoke_fire_batch

        images = [MagicMock(), MagicMock()]

        boxes = MagicMock()
        boxes.__len__ = MagicMock(return_value=1)  # exactly one box — kills `len(...) > 1`
        boxes.cls = [MagicMock(item=MagicMock(return_value=1))]
        boxes.conf = [MagicMock(item=MagicMock(return_value=0.95))]
        boxes.xyxy = [MagicMock(tolist=MagicMock(return_value=[5, 6, 7, 8]))]

        r_with_boxes = MagicMock()
        r_with_boxes.boxes = boxes
        r_empty = MagicMock(boxes=None)

        mock_model = MagicMock()
        mock_model.names = {0: "smoke", 1: "fire"}
        mock_model.predict.return_value = [r_with_boxes, r_empty]

        results = await detect_smoke_fire_batch(mock_model, images, confidence_threshold=0.6)

        kwargs = mock_model.predict.call_args[1]
        assert kwargs["source"] is images
        assert kwargs["conf"] == 0.6
        assert kwargs["verbose"] is False

        assert len(results) == 2
        assert results[0].has_fire is True
        assert results[0].detections[0].confidence == 0.95
        assert results[1].has_detections is False


class TestLoadSmokeFireModelRealClass:
    """Drive _load_and_fuse with a REAL (non-mock) YOLO class.

    The module's `is_mock` probe treats MagicMock as mocked and skips the
    entire weights-discovery branch; every surviving fallback mutant hides in
    that dead branch. A plain class with recording __init__ is the only
    stand-in that walks model.pt -> best.pt -> default -> glob("*.pt").
    """

    class RecorderYOLO:
        """Non-mock stand-in: no _mock_name / assert_called attributes."""

        calls: list[str] = []

        def __init__(self, weights: str) -> None:
            RecorderYOLO.calls.append(weights)

        def fuse(self) -> None:  # keeps the pre-fuse else-branch quiet
            pass

    @pytest.mark.asyncio
    async def test_fallback_chain_and_glob_and_missing(self, tmp_path) -> None:
        from backend.services import smoke_fire_loader as sf_mod

        RecorderYOLO = self.RecorderYOLO

        # 1. model.pt absent, best.pt present -> second rung of the chain.
        (tmp_path / "best.pt").touch()
        RecorderYOLO.calls = []
        with patch.object(sf_mod, "YOLO", RecorderYOLO):
            await sf_mod.load_smoke_fire_model(str(tmp_path))
        assert RecorderYOLO.calls == [str(tmp_path / "best.pt")]

        # 2. only an arbitrary .pt -> glob("*.pt") fallback (kills pattern mutants).
        (tmp_path / "best.pt").unlink()
        (tmp_path / "other.pt").touch()
        RecorderYOLO.calls = []
        with patch.object(sf_mod, "YOLO", RecorderYOLO):
            await sf_mod.load_smoke_fire_model(str(tmp_path))
        assert RecorderYOLO.calls == [str(tmp_path / "other.pt")]

        # 3. nothing at all -> FileNotFoundError naming the directory
        #    (kills the message -> None mutant; str(exc) of the mutant is "None").
        (tmp_path / "other.pt").unlink()
        RecorderYOLO.calls = []
        with patch.object(sf_mod, "YOLO", RecorderYOLO):
            with pytest.raises(FileNotFoundError) as exc_info:
                await sf_mod.load_smoke_fire_model(str(tmp_path))
        assert str(tmp_path) in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_mock_predicate_arms(self, tmp_path) -> None:
        """is_mock must be True via EITHER arm alone."""
        from backend.services import smoke_fire_loader as sf_mod

        class MockNameOnly:
            _mock_name = "yolo"
            calls: list[str] = []

            def __init__(self, weights: str) -> None:
                MockNameOnly.calls.append(weights)

        class AssertCalledOnly:
            assert_called = True
            calls: list[str] = []

            def __init__(self, weights: str) -> None:
                AssertCalledOnly.calls.append(weights)

        # First arm only: mocked branch -> default weights path, no exists() checks.
        MockNameOnly.calls = []
        with patch.object(sf_mod, "YOLO", MockNameOnly):
            await sf_mod.load_smoke_fire_model(str(tmp_path))
        assert MockNameOnly.calls == [str(tmp_path / "smoke-fire-yolov8n.pt")]

        # Second arm only: same contract (kills the `or` -> `and`, `yolo_class`
        # -> None, and attribute-arity mutants).
        AssertCalledOnly.calls = []
        with patch.object(sf_mod, "YOLO", AssertCalledOnly):
            await sf_mod.load_smoke_fire_model(str(tmp_path))
        assert AssertCalledOnly.calls == [str(tmp_path / "smoke-fire-yolov8n.pt")]
```

### Kill mapping for drafts (UNVERIFIED)

| Draft | Kills (primary) | Incidental | TDD one-liner |
|-------|-----------------|------------|----------------|
| `TestFormatSmokeFireContextStrict.test_lists_detections_highest_first_with_priority_and_cap` | F6, F7, F8, F9 | F5 | exact-render assert fails on flipped sort/cap/marker/case, passes on original |
| `TestFormatSmokeFireContextStrict.test_no_detections_sentinel_is_exact` | F2 | F1 | equality fails on case/XX'd sentinel |
| `TestFormatSmokeFireContextStrict.test_night_escalation_and_daytime_negative` | F10, F11 | (m43) | `in`→`not in` puts block on daytime call → negative assert fires; case'd tuple drops night lines |
| `TestSmokeFireResultContextStringStrict.test_smoke_context_string_ordering_priority_and_join` (+`_fire_context_string_exact`) | T5, T6, T7 | T2-T4 | exact string fails on reorder/marker/sep/case variants |
| `TestDetectSmokeFireBatchStrict.test_batch_predict_kwargs_and_single_box_detection` | B1, B2 | — | kwargs assert + single-box `has_fire` fails on None/True/removed kwargs and `>1` guard |
| `TestLoadSmokeFireModelRealClass.test_fallback_chain_and_glob_and_missing` (+`test_mock_predicate_arms`) | L9, L8, L7 | L4 | recorder captures wrong weights path / TypeError from `/`→`*`, `hasattr` arity, or FileNotFoundError with "None" message on mutants |

Remaining survivors (EQUIVALENT log-text / mock-probe clusters L1-L6, T1, F1/F3/F4/F5 and
LOW-VALUE B3) need no new tests; they are either semantically identical or message text on a
not-worth-pinning contract.
