# WP4.4 Triage Dossier — backend/services/threat_detection_loader.py

**Status: UNVERIFIED — read-only triage; no tests were run, no repo files modified.**

- Survivors: **128** of 343 mutants (215 killed, 0 unchecked).
- Sole covering test file: `backend/tests/unit/services/test_threat_detection_loader.py` (810 lines).
  Anchors: `TestThreatDetection` L31, `TestThreatDetectionResult` L74, `to_dict` test L136,
  `to_context_string` tests L152–195, `TestLoadThreatDetectionModel` L198–395,
  `TestDetectThreats` L398–602, `TestDetectThreatsBatch` L605–667,
  `TestFormatThreatContext` L670–748, integration L776–810.
- All diffs pulled via `uv run mutmut show <key>` (all 128 succeeded; no fallback needed).

## Why so many survive (root causes)

1. **Substring asserts instead of exact-string contract.** Every `to_context_string` /
   `format_threat_context` test checks `assert "CRITICAL" in context` — an `XX...XX`-wrapped or
   case-flipped line still contains the substring. Kills XX-wrap/case mutants of *rendered output*
   (TEST-GAP: fix the assertion strength). NOTE: this is the opposite of log-message mutants —
   these strings are the product (LLM prompt text), so mutation there is a real behavior change.
2. **Detections never field-checked.** Batch tests assert `has_threats` / `len(threats)` but never
   `class_name`, `confidence`, `bbox`, `is_high_priority`; single-detect tests assert class_name only.
3. **`model.predict` call kwargs barely pinned.** Only `conf` is asserted, and only in
   `test_detect_threats_custom_confidence_threshold` (L532) — `source=` and the batch `conf=` are
   never checked. `verbose` is genuinely nobody's business (LOW-VALUE).
4. **MagicMock auto-vivification hides guards.** `hasattr(mock, "XXnamesXX")` /
   `hasattr(mock, "XXis_fusedXX")` is True for any MagicMock, so string-clobber mutants of
   `hasattr` names in the class-lookup and fuse blocks are invisible. Needs `types.SimpleNamespace`
   / real objects.
5. **`Path` is monkeypatched to a stub in every loader test** — filename-chain and rglob-fallback
   mutants are unreachable; needs real `tmp_path` filesystem tests.
6. **`time_of_day` only ever "night"/"afternoon"** — the `late_night` / `early_morning` tuple
   members are dead test inputs.
7. **Logging mutants** (message text, `exc_info`, `extra` keys) mutate log output only →
   EQUIVALENT (message text) / LOW-VALUE (`exc_info`/`extra`). Not worth killing.

## Cluster table

Counts sum to 128. (K) = covered by a drafted test below.

| # | Cluster (function — pattern) | n | Class | Example keys | Kill note |
|---|---|---|---|---|---|
| 1 | detect_threats — `predict(source=…)` arg removed/None | 2 | TEST-GAP | …x_detect_threats__mutmut_3, __6 | T3 (K) assert `call_args[1]["source"] is image` |
| 2 | detect_threats — `verbose` kwarg mutated/removed | 3 | LOW-VALUE | __5, __8, __9 | stdout verbosity only; nobody should assert it |
| 3 | detect_threats — `not results or len==0` → `and` | 1 | EQUIVALENT | __10 | for lists `not X` ⇔ `len(X)==0`; `A or A` = `A and A` |
| 4 | detect_threats — boxes `len(boxes) > 0` → `>= 0` | 1 | EQUIVALENT | __19 | entering loop with `range(0)` yields same empty threats list |
| 5 | detect_threats — bbox tuple coords swapped / bbox None | 5 | TEST-GAP | __39, __41, __53 | T3 (K) assert `t.bbox == (10.,20.,30.,40.)` |
| 6 | detect_threats — `logger.error` message text variants | 4 | EQUIVALENT | __63, __67, __68 | log-only text |
| 7 | detect_threats — `logger.error` `exc_info` mutated/removed | 3 | LOW-VALUE | __64, __66, __70 | traceback in logs only |
| 8 | detect_threats_batch — `predict(source=images)` removed/None | 2 | TEST-GAP | __4, __7 | T2 (K) |
| 9 | detect_threats_batch — `predict(conf=…)` removed/None | 2 | TEST-GAP | __5, __8 | T2 (K) — batch has NO threshold test at all |
| 10 | detect_threats_batch — `verbose` kwarg | 3 | LOW-VALUE | __6, __9, __10 | same as #2 |
| 11 | detect_threats_batch — boxes `>0`→`>=0` | 1 | EQUIVALENT | __15 | same as #4 |
| 12 | detect_threats_batch — class-name resolution (hasattr/`in`/`.lower()`/fallback) | 8 | TEST-GAP | __21, __28, __30 | T1 (K) — batch never asserts `class_name`; unknown-class & no-names paths untested |
| 13 | detect_threats_batch — `conf=None`, `is_high_priority` None/flipped | 3 | TEST-GAP | __31, __43, __44 | T2 (K) |
| 14 | detect_threats_batch — bbox tuple swapped/None | 5 | TEST-GAP | __34, __36, __48 | T2 (K) |
| 15 | detect_threats_batch — `ThreatDetection(...)` kwargs None/omitted | 4 | TEST-GAP | __46, __47, __53 | T2 (K) |
| 16 | detect_threats_batch — `logger.error` message text | 4 | EQUIVALENT | __59, __63, __64 | log-only |
| 17 | detect_threats_batch — `logger.error` `exc_info` | 3 | LOW-VALUE | __60, __62, __66 | log-only |
| 18 | format_threat_context — early-return strings (None / no-threats) | 2 | TEST-GAP | __2, __6 | T5 (K) assert full string equality |
| 19 | format_threat_context — header line XX-wrapped | 1 | TEST-GAP | __10 | T5 (K) `splitlines()[0] ==` |
| 20 | format_threat_context — CRITICAL / "Immediate review" lines wrapped/cased | 4 | TEST-GAP | __13, __17, __18 | T5 (K) exact lines; "Immediate review" line has ZERO coverage |
| 21 | format_threat_context — detail sort `reverse=True`→None/removed/False | 3 | TEST-GAP | __24, __27, __29 | T5 (K) detail-line order; wrong order also picks wrong 5 when >5 threats |
| 22 | format_threat_context — `" **HIGH PRIORITY**"` marker mutants | 6 | TEST-GAP | __31, __33, __35 | T5 (K) marker present on high-prio line, absent on normal line |
| 23 | format_threat_context — time tuple members `late_night`/`early_morning` clobbered | 4 | TEST-GAP | __43, __44, __45 | T4 (K) parametrize over late_night/early_morning/uppercase |
| 24 | format_threat_context — escalation line XX-wrapped | 1 | TEST-GAP | __49 | T5 (K) exact line |
| 25 | format_threat_context — `"\n".join` → `"XX\nXX".join` | 1 | TEST-GAP | __53 | T5 (K) exact output |
| 26 | load_threat_detection_model — `logger.info/warning/error` message text | 11 | EQUIVALENT | __1, __59, __72 | log-only text |
| 27 | load_threat_detection_model — `Path(model_path)` → `Path(None)` | 1 | TEST-GAP | __4 | Path stubbed by every test; T6 (K) with real fs |
| 28 | load_threat_detection_model — weights-name chain (`model.pt`/`best.pt`/`threat-detection-yolov8n.pt`) clobbered/cased | 6 | TEST-GAP | __7, __8, __12 | T6 (K) preference test on real `tmp_path` |
| 29 | load_threat_detection_model — rglob fallback / FileNotFoundError msg / `YOLO(str(w))` arg | 8 | TEST-GAP | __20, __25, __27 | T6 (K) rglob step + `match="No model weights"` + YOLO call-path assert |
| 30 | load_threat_detection_model — fuse-guard string names & `and`→`or` & getattr default | 6 | TEST-GAP | __33, __40, __43 | T6 (K) plain objects (no MagicMock auto-viv) |
| 31 | load_threat_detection_model — raised `ImportError` message XX-wrapped | 1 | TEST-GAP | __63 | weak `match=` substring in test L228; tighten to `excinfo.value.args[0] == "Threat detection requires ultralytics. Install with: pip install ultralytics"` |
| 32 | load_threat_detection_model — `logger.error` `exc_info`/`extra` dict mutants | 7 | LOW-VALUE | __67, __68, __76 | log structure only |
| 33 | ThreatDetectionResult.to_context_string — no-threats return XX-wrapped | 1 | TEST-GAP | …ǁto_context_string__mutmut_2 | T5 (K) exact equality |
| 34 | to_context_string — header / CRITICAL lines XX-wrapped | 2 | TEST-GAP | __6, __9 | T5 (K) exact lines incl. leading spaces |
| 35 | to_context_string — `" [HIGH PRIORITY]"` marker mutants (None/`and False`/`or True`/wrap/case/else-text) | 6 | TEST-GAP | __20, __22, __24 | T5 (K) — marker never asserted anywhere |
| 36 | to_context_string — `"\n".join` → `"XX\nXX".join` | 1 | TEST-GAP | __28 | T5 (K) exact output |
| 37 | ThreatDetectionResult.to_dict — `"threat_summary"` key name clobbered/cased | 2 | TEST-GAP | …ǁto_dict__mutmut_9, __10 | T5 (K) assert `d["threat_summary"]` (test L136 checks other keys only) |

**Totals: TEST-GAP 87 / EQUIVALENT 22 / LOW-VALUE 19 = 128.**
The six drafted tests below kill 86 of the 87 TEST-GAP mutants (#31 is a one-line assert tightening,
not drafted); EQUIVALENT/LOW-VALUE clusters are deliberately left unkilled.

## Drafted tests

// UNVERIFIED — not yet run red/green. TDD procedure for each: append the test to
`backend/tests/unit/services/test_threat_detection_loader.py`, run the single test — it must FAIL
(red) on each mutant in its cluster(s) and PASS (green) on the original; then run the whole file to
confirm no regression, and re-run `mutmut` on the module to confirm the cluster's keys flip to killed.

Shared helper (add once, module level, following the inline-mock style of `TestDetectThreats`):

```python
def _mock_box_result(cls_values, conf_values, xyxy_at):
    """Build a mock ultralytics result whose .boxes yields the given per-index values."""
    boxes = MagicMock()
    boxes.__len__ = lambda self: len(cls_values)
    boxes.cls = MagicMock()
    boxes.cls.__getitem__ = lambda self, i: MagicMock(item=lambda: cls_values[i])
    boxes.conf = MagicMock()
    boxes.conf.__getitem__ = lambda self, i: MagicMock(item=lambda: conf_values[i])
    boxes.xyxy = MagicMock()
    boxes.xyxy.__getitem__ = lambda self, i: MagicMock(tolist=lambda: xyxy_at(i))
    result = MagicMock()
    result.boxes = boxes
    return result
```

### T1 — kills cluster 12 (batch class-name resolution, 8 mutants)

```python
class TestWp44BatchClassResolution:
    """UNVERIFIED - not yet run red/green. WP4.4: batch class-name paths were never field-checked."""

    @pytest.mark.asyncio
    async def test_detect_threats_batch_class_name_resolution(self) -> None:
        """Batch: known id lower-cased; unknown id -> class_<id>; no names attr -> fallback."""
        r_known = _mock_box_result([0], [0.85], lambda i: [10.0, 20.0, 30.0, 40.0])
        r_unknown = _mock_box_result([99], [0.85], lambda i: [10.0, 20.0, 30.0, 40.0])

        model = MagicMock()
        model.names = {0: "Knife"}  # mixed case: .lower() must normalise
        model.predict.return_value = [r_known, r_unknown]

        results = await detect_threats_batch(model, [MagicMock(), MagicMock()])

        assert results[0].threats[0].class_name == "knife"
        assert results[1].threats[0].class_name == "class_99"

        # Model without a names attribute must fall back to class_<id>
        model_no_names = MagicMock()
        del model_no_names.names
        model_no_names.predict.return_value = [r_known]

        results = await detect_threats_batch(model_no_names, [MagicMock()])

        assert results[0].threats[0].class_name == "class_0"
```

Red mechanism: `__mutmut_19` (cls_id None → `class_None`), `__mutmut_21` (`and`→`or` → AttributeError
on `.names` when missing → RuntimeError), `__mutmut_22/26/27` (`hasattr` clobber → fallback name on
known class), `__mutmut_28` (`not in` swap), `__mutmut_29` (class None), `__mutmut_30` (`.upper()`)
each break one assertion. Green: original takes the mapped lower-cased name, `class_99`, `class_0`.

### T2 — kills clusters 8, 9, 13, 14, 15 (batch field fidelity + predict kwargs, 16 mutants)

```python
class TestWp44BatchFieldFidelity:
    """UNVERIFIED - not yet run red/green. WP4.4: batch results never had fields asserted."""

    @pytest.mark.asyncio
    async def test_detect_threats_batch_field_fidelity_and_predict_kwargs(self) -> None:
        """Batch must forward source/conf and populate every ThreatDetection field."""
        boxes = _mock_box_result(
            [0, 1],
            [0.85, 0.95],
            lambda i: [10.0 + i * 10, 20.0 + i * 10, 30.0 + i * 10, 40.0 + i * 10],
        )
        model = MagicMock()
        model.names = {0: "knife", 1: "gun"}
        model.predict.return_value = [boxes]
        images = [MagicMock()]

        results = await detect_threats_batch(model, images, confidence_threshold=0.4)

        kwargs = model.predict.call_args[1]
        assert kwargs["source"] is images  # kills __4/__7
        assert kwargs["conf"] == 0.4  # kills __5/__8

        t0, t1 = results[0].threats
        assert (t0.class_name, t0.confidence, t0.bbox, t0.is_high_priority) == (
            "knife",
            0.85,
            (10.0, 20.0, 30.0, 40.0),
            False,
        )
        assert (t1.class_name, t1.confidence, t1.bbox, t1.is_high_priority) == (
            "gun",
            0.95,
            (20.0, 30.0, 40.0, 50.0),
            True,
        )
```

Red mechanism: `__mutmut_31` (conf None), `__mutmut_34/36/38/40/48` (bbox None/coord swaps),
`__mutmut_43/44/49/53` (is_high_priority None/flipped/dropped — `t1` would be False/None ≠ True),
`__mutmut_46/47` (class/confidence kwargs None). Deliberately does NOT assert `verbose` (LOW-VALUE
clusters 2/10 stay unkilled).

### T3 — kills clusters 1, 5 (detect_threats source kwarg + bbox, 7 mutants)

```python
class TestWp44DetectFieldFidelity:
    """UNVERIFIED - not yet run red/green. WP4.4: single-detect bbox & source never asserted."""

    @pytest.mark.asyncio
    async def test_detect_threats_field_fidelity_and_predict_source(self) -> None:
        """detect_threats must pass the image through as source and preserve the bbox."""
        result = _mock_box_result([0], [0.85], lambda i: [10.0, 20.0, 30.0, 40.0])
        model = MagicMock()
        model.names = {0: "gun"}
        model.predict.return_value = [result]
        image = MagicMock()

        threat_result = await detect_threats(model, image, confidence_threshold=0.4)

        kwargs = model.predict.call_args[1]
        assert kwargs["source"] is image  # kills __mutmut_3 / __mutmut_6
        assert kwargs["conf"] == 0.4

        threat = threat_result.threats[0]
        assert threat.bbox == (10.0, 20.0, 30.0, 40.0)  # kills __39/__41/__43/__45/__53
        assert threat.is_high_priority is True
```

### T4 — kills cluster 23 (time_of_day tuple members, 4 mutants)

```python
class TestWp44TimeOfDayVariants:
    """UNVERIFIED - not yet run red/green. WP4.4: only 'night'/'afternoon' were ever exercised."""

    @pytest.mark.parametrize(
        "tod",
        ["night", "NIGHT", "late_night", "LATE_NIGHT", "early_morning", "EARLY_MORNING"],
    )
    def test_format_threat_context_time_of_day_escalation_variants(self, tod: str) -> None:
        result = ThreatDetectionResult(
            threats=[ThreatDetection("gun", 0.95, (10.0, 20.0, 30.0, 40.0), True)]
        )

        context = format_threat_context(result, time_of_day=tod)

        assert f"TIME CONTEXT: Detection during {tod}" in context.splitlines()
        assert "  Elevated concern: Armed threat at unusual hour" in context.splitlines()
```

Red mechanism: `__mutmut_43/45` (`"XXlate_nightXX"` / `"XXearly_morningXX"` never match the
lower-cased input) and `__mutmut_44/46` (`"LATE_NIGHT"`/`"EARLY_MORNING"` in the tuple while input is
`.lower()`-ed) suppress the escalation block. The `LATE_NIGHT`/`EARLY_MORNING` *inputs* pass because
of `.lower()` — that is exactly the contract.

### T5 — kills clusters 18–22, 24, 25, 33–37 (exact output contracts, 29 mutants)

```python
class TestWp44ExactOutputContracts:
    """UNVERIFIED - not yet run red/green. WP4.4: substring asserts let XX-wrap/case/order
    mutants of LLM-facing prompt text through. These strings are the product — pin them exactly."""

    def test_to_context_string_exact_output(self) -> None:
        assert (
            ThreatDetectionResult().to_context_string()
            == "Threat scan: No weapons or threatening objects detected"
        )

        threats = [
            ThreatDetection("knife", 0.85, (10.0, 20.0, 30.0, 40.0), False),
            ThreatDetection("gun", 0.95, (50.0, 60.0, 70.0, 80.0), True),
        ]
        context = ThreatDetectionResult(threats=threats).to_context_string()

        assert context == "\n".join(
            [
                "**THREAT DETECTION ALERT**",
                "  CRITICAL: High-priority threat(s) detected!",
                "  - gun: 95% confidence [HIGH PRIORITY]",
                "  - knife: 85% confidence",
            ]
        )

    def test_result_to_dict_includes_threat_summary_key(self) -> None:
        result = ThreatDetectionResult(
            threats=[ThreatDetection("knife", 0.85, (1.0, 2.0, 3.0, 4.0), False)]
        )
        assert result.to_dict()["threat_summary"] == "1x knife"

    def test_format_threat_context_exact_output(self) -> None:
        assert format_threat_context(None) == "Threat detection: Not performed"
        assert (
            format_threat_context(ThreatDetectionResult())
            == "Threat detection: No weapons or threatening objects detected"
        )

        threats = [
            ThreatDetection("bat", 0.40, (1.0, 2.0, 3.0, 4.0), False),
            ThreatDetection("gun", 0.95, (5.0, 6.0, 7.0, 8.0), True),
        ]
        context = format_threat_context(ThreatDetectionResult(threats=threats))

        assert context.splitlines() == [
            "**WEAPON/THREAT DETECTION**",
            "  CRITICAL ALERT: High-priority weapon detected!",
            "  Immediate review recommended.",
            "  Threats found: 1x bat, 1x gun",
            "  Highest confidence: 95%",
            "    - gun (95%) **HIGH PRIORITY**",
            "    - bat (40%)",
        ]

    def test_format_threat_context_exact_output_with_time_escalation(self) -> None:
        threats = [ThreatDetection("gun", 0.95, (5.0, 6.0, 7.0, 8.0), True)]
        context = format_threat_context(ThreatDetectionResult(threats=threats), time_of_day="night")

        assert context.splitlines()[-2:] == [
            "  TIME CONTEXT: Detection during night",
            "  Elevated concern: Armed threat at unusual hour",
        ]
        assert context.splitlines()[0] == "**WEAPON/THREAT DETECTION**"
```

Red mechanism: any `XX`-wrap breaks line equality (`"XX**WEAPON…XX"` ≠ header); `reverse` removal
flips detail order (bat before gun — also visible via the `[:5]` slice when >5 threats);
`or True` markers add `"**HIGH PRIORITY**"` to the bat line; `and False`/None markers strip or emit
`"None"`; `else "XXXX"` pollutes the bat line; `"XX\nXX".join` corrupts every line. Green on
original by construction.

### T6 — kills clusters 27–30 (weights resolution + fuse semantics on real objects, 21 mutants)

```python
class TestWp44ModelLoaderRealFs:
    """UNVERIFIED - not yet run red/green. WP4.4: every loader test stubs Path/MagicMock, hiding
    filename-chain, rglob, error-message and fuse-guard mutants. Use real tmp_path + plain objects."""

    @pytest.mark.asyncio
    async def test_load_threat_detection_model_weights_resolution_and_fuse(
        self, monkeypatch, tmp_path
    ) -> None:
        import sys
        import types

        recorded: list = []

        class PlainModel:
            def __init__(self, path: str) -> None:
                recorded.append(path)
                self.path = path
                self.fused_called = False

            def fuse(self) -> None:
                self.fused_called = True

        class PlainYOLO:  # no .model attr -> getattr(..., "model", None) default path
            def __new__(cls, path):
                return PlainModel(path)

        fake_ultralytics = types.ModuleType("ultralytics")
        fake_ultralytics.YOLO = PlainYOLO
        monkeypatch.setitem(sys.modules, "ultralytics", fake_ultralytics)

        # 1) direct names win over each other, in order
        for name in ("model.pt", "best.pt", "threat-detection-yolov8n.pt"):
            (tmp_path / name).write_bytes(b"x")
        model = await load_threat_detection_model(str(tmp_path))
        assert recorded[-1] == str(tmp_path / "model.pt")  # kills __7/__8 (and __4 Path(None))
        assert model.fused_called is True  # kills __33/__34 (fuse hasattr clobber), __40 (getattr no default)

        (tmp_path / "model.pt").unlink()
        await load_threat_detection_model(str(tmp_path))
        assert recorded[-1] == str(tmp_path / "best.pt")  # kills __12/__13

        (tmp_path / "best.pt").unlink()
        (tmp_path / "aaa.pt").write_bytes(b"x")  # sorts BEFORE the threat name
        await load_threat_detection_model(str(tmp_path))
        assert recorded[-1] == str(tmp_path / "threat-detection-yolov8n.pt")  # kills __17/__18

        # 2) rglob fallback catches nested layouts (weights/best.pt)
        (tmp_path / "threat-detection-yolov8n.pt").unlink()
        nested = tmp_path / "weights"
        nested.mkdir()
        (nested / "best.pt").write_bytes(b"x")
        await load_threat_detection_model(str(tmp_path))
        assert recorded[-1] == str(nested / "best.pt")  # kills __23/__24 (rglob pattern clobber)

        # 3) nothing on disk -> RuntimeError carrying the FileNotFoundError text
        (nested / "best.pt").unlink()
        with pytest.raises(RuntimeError, match="No model weights"):
            await load_threat_detection_model(str(tmp_path))  # kills __20/__21/__22/__25

        # 4) fuse guards with plain objects (MagicMock made __30's mutants invisible)
        class FusedInner:
            def __new__(cls, path):
                obj = PlainModel(path)
                obj.model = types.SimpleNamespace(is_fused=lambda: True)
                return obj

        monkeypatch.setattr(fake_ultralytics, "YOLO", FusedInner)
        model = await load_threat_detection_model(str(tmp_path / "nothing"))
        assert model.fused_called is False  # kills __49/__50 (is_fused name clobber would fuse anyway)

        class NoIsFused:
            def __new__(cls, path):
                obj = PlainModel(path)
                obj.model = types.SimpleNamespace()  # inner without is_fused
                return obj

        monkeypatch.setattr(fake_ultralytics, "YOLO", NoIsFused)
        model = await load_threat_detection_model(str(tmp_path / "nothing"))
        assert model.fused_called is True  # kills __43 (and->or enters branch, then AttributeError)
```

Caveat to verify when running: steps 1–3 run with `Path` unpatched (real fs) — the existing tests'
`monkeypatch.setattr(... "Path", lambda x: mock_path)` must NOT leak (they are per-test, fine). The
PlainYOLO-returns-PlainModel trick via `__new__` can be replaced with a factory closure if
`__new__` confuses the executor path.

### One-line fix (not drafted): cluster 31

In `test_load_threat_detection_model_import_error` (L226–230) replace the `match=` substring with
`excinfo.value.args[0] == "Threat detection requires ultralytics. Install with: pip install ultralytics"`
to kill `__mutmut_63` (XX-wrapped exception message).

## Deliberately unkilled

- **EQUIVALENT (22):** clusters 3, 4, 6, 11, 16, 26 — provably same behavior (`not X`⇔`len==0`;
  `range(0)` no-op; log message text).
- **LOW-VALUE (19):** clusters 2, 7, 10, 17, 32 — `verbose` stdout flag, `exc_info`/`extra` log
  plumbing. Asserting these would osscribe incidental log shape for zero safety gain.
