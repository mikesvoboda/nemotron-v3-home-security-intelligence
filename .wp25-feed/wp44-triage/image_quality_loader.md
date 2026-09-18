# WP4.4 Triage Dossier — backend/services/image_quality_loader.py

- **Meta file**: `mutants/backend/services/image_quality_loader.py.meta`
- **Mutant copy**: `mutants/backend/services/image_quality_loader.py`
- **Covering test file (primary)**: `backend/tests/unit/services/test_image_quality_loader.py`
- **Secondary callers exercised in tests**: `backend/tests/unit/services/test_enrichment_pipeline.py`, `backend/tests/unit/services/test_enrichment_pipeline_household_matching.py`
- **Survivors**: 97 of 175 checked (78 killed, 0 unchecked)
- **Diffs obtained by**: manual diff of each `__mutmut_N` block against its `__mutmut_orig` block in the mutant copy (160 blocks parsed; all 97 survivors resolved, 0 missing).

## Why so many survive: the existing success-path test is a hallucinated-mock test

`test_image_quality_loader.py::test_assess_image_quality_success` (file:579-625) mocks torch/torchvision wholesale and asserts only three things: `isinstance(result, ImageQualityResult)`, `quality_score == 75.0`, `brisque_score == 25.0`. It never asserts `is_blurry/is_noisy/is_low_quality/quality_issues`, never feeds a real image through the real transform path, never touches the clamp bounds, the `wait_for` timeout, or the `brisque_fn(...)` kwargs. And because the mock is a `MagicMock`, *any* clobber that just swaps an argument for another object or string silently passes (the mock accepts anything and still returns 25.0). That single weak test is the root cause behind ~35 of the 97 survivors.

The message-constant survivors (C12–C17) dominate the rest: the tests consistently use *substring* asserts against a *different* half of the string ("Quality stable" tested via `"stable" in description.lower()`), and log lines are never asserted at all.

## Cluster table (counts sum to 97)

Key prefix `backend.services.image_quality_loader.` abbreviated to leaf key. Original lines cited from `backend/services/image_quality_loader.py`.

| # | Pattern (function — change) | Count | Keys (≤3 ex.) | Class |
|---|---|---|---|---|
| C1 | `assess_image_quality` L189 — RGB-convert branch *behaviorally changed* on a real non-RGB image: whole expr→None (7), `and False` kill-guard (8), mode string mutated `convert(None)`/`"XXRGBXX"`/`"rgb"` (10,11,12), branch polarity flipped `!=`→`==` (13) | 6 | x_assess_image_quality__mutmut_7, _11, _13 | TEST-GAP |
| C2 | `assess_image_quality` L189 — condition mutations on `"RGB"` that are **no-ops for every real PIL mode** (`or True`≡condition, `"XXRGBXX"`/`"rgb"` never match a real mode, so convert-always behaves as today for RGB test fixtures) | 3 | x_assess_image_quality__mutmut_9, _14, _15 | EQUIVALENT |
| C3 | `assess_image_quality` L182 — `transforms.Compose([...])` argument list → `None` | 1 | x_assess_image_quality__mutmut_6 | EQUIVALENT (see note) |
| C4 | `assess_image_quality` L191 — tensor build clobbers (`transform(...)→None` 16, `unsqueeze(None)` 17, `transform(None)` 18) or **batch-dim moved to wrong axis** `unsqueeze(1)` (19) | 4 | x_assess_image_quality__mutmut_19 | TEST-GAP |
| C5 | `assess_image_quality` L195 — `brisque_fn()` call kwargs mutated: `data_range=2.0` (27), `reduction="MEAN"` (29), arg dropped (24,25,26), None-clobbers (21,22,23) — all silently accepted because brisque_fn is a MagicMock in tests | 9 | x_assess_image_quality__mutmut_27, _29 | TEST-GAP |
| C6 | `assess_image_quality` L199 — clamp bounds widened/shifted: `max(1.0,…)` floors at 1 not 0 (35), `min(101.0,…)` allows 100<s<101 (40) | 2 | x_assess_image_quality__mutmut_35, _40 | TEST-GAP |
| C7 | `assess_image_quality` L209-211 — threshold comparison **boundary flipped** `>=`→`>` for is_blurry/is_noisy/is_low_quality; exactly-at-threshold frames get misclassified | 3 | x_assess_image_quality__mutmut_46, _48, _50 | TEST-GAP |
| C8 | `assess_image_quality` — result-construction None-clobbers: `is_blurry=None` (59), `is_noisy=None` (60), `is_low_quality=None` (61), `quality_issues=None` (62,68), locals→None (44,45,47,49) — falsy `None` slips through `isinstance`-only asserts | 9 | x_assess_image_quality__mutmut_61, _62 | TEST-GAP |
| C9 | `assess_image_quality` L215-217 — quality_issues branch: operator swap `and`→`or` inside (53,54), `not` removal on is_blurry/is_noisy (55,56), inner `>=`→`>` (52) → issue list wrong (extra "general quality degradation" when blurry, etc.) | 5 | x_assess_image_quality__mutmut_55 | TEST-GAP |
| C10 | `assess_image_quality` L215 — `is_noisy and brisque_score >= noise_threshold` → `or`: dead-clause change, **never fires** under default thresholds (blur 50 < noise 60 ⇒ is_noisy ⇒ already ≥ threshold) | 1 | x_assess_image_quality__mutmut_51 | EQUIVALENT |
| C11 | `assess_image_quality` L230-232 — assessment `asyncio.wait_for` timeout changed: `15.0→None` disables timeout (70), `→16.0` (76) | 2 | x_assess_image_quality__mutmut_70 | TEST-GAP |
| C12 | `assess_image_quality` L239,243 — logger.error message/kwargs clobbers (`exc_info=True→None/False/dropped`, text case/prefix tweaks, `logger.error(None)`) | 11 | x_assess_image_quality__mutmut_84, _90 | LOW-VALUE |
| C13 | `assess_image_quality` L240,244 — **raised-error text** clobbered: `RuntimeError("torch and torchvision required…")` (81), `RuntimeError(f"Image quality assessment failed: {e}")→RuntimeError(None)` (91) | 2 | x_assess_image_quality__mutmut_81, _91 | LOW-VALUE |
| C14 | `load_brisque_model` L111,118,123,127,133 — logger.info/warning/error message/kwargs clobbers across all 5 call sites (text case, prefix, `exc_info` tweaks, `logger.info(None)`) | 23 | x_load_brisque_model__mutmut_4, _29 | LOW-VALUE |
| C15 | `load_brisque_model` L128-130 — ImportError **message** text mutated (prefix/case) | 2 | x_load_brisque_model__mutmut_25 | LOW-VALUE |
| C16 | `detect_quality_change` L266,277 — non-trigger return **text** mutated: `"First frame…"` prefixed (3), `"Quality stable"` → XX-prefixed/lower/upper (11,12,13) — substring test asserts the other word, so never sees it | 4 | x_detect_quality_change__mutmut_3, _12 | LOW-VALUE |
| C17 | `interpret_blur_with_motion` L298,303,308,313 — the four return-string branches text-mutated (prefix/case) — tests assert substrings like `"motion blur"` (case-insensitive) / `"camera issue"` / `"running"` that survive the cosmetic edit | 8 | x_interpret_blur_with_motion__mutmut_9, _16 | LOW-VALUE |
| C18 | `ImageQualityResult.format_context` L86 — fallback-string clobbers: separator `", "→"XX, XX"` (5), `"general degradation"→"XXgeneral degradationXX"` (6) | 2 | xǁImageQualityResultǁformat_context__mutmut_5, _6 | LOW-VALUE |

**Classification totals**: TEST-GAP 41 (C1,4,5,6,7,8,9,11), EQUIVALENT 5 (C2,3,10), LOW-VALUE 51 (C12–C18).

### Cluster notes

- **C1 vs C2 split**: C1 mutants change observable behavior whenever `image.mode != "RGB"` ever evaluates true (a grayscale/L/CMYK/RGBA frame — a real camera-frame case per the module docstring). C2 mutants are provably no-ops for every real PIL mode value, so the branch outcome is unchanged even for those inputs: `or True` on `mode != "RGB"` is the condition itself; `"XXRGBXX"`/`"rgb"` are compared against/converted-to but the converted-mode result equals the un-converted original for RGB fixtures and `"rgb" != "RGB"` still triggers a convert — the resulting image data is identical. They are unkillable without an exotic fixture and are not a test gap.
- **C3** (`Compose(None)`): `transforms.Compose(None)` does not raise — it iterates None and throws `TypeError` only *inside the executor*, which then gets caught by the broad `except Exception` at L242 and re-raised as `RuntimeError("Image quality assessment failed: …")`. The outer behavior is the same as any other internal failure. With real `Compose([ToTensor()])` the list-vs-None change would crash → but existing success test mocks the entire transform, so the difference is invisible there, and no test runs the real torchvision path. Classified EQUIVALENT *as observable through the mocked test harness*; the honest root cause is the mock, recorded under C5.
- **C10**: under the default thresholds the `and`-clause is entailed by `is_noisy` (blur 50 ≤ noise 60), so `or` cannot differ; only a hand-crafted call with `noise_threshold < blur_threshold` distinguishes it — not behavior anyone should rely on, so EQUIVALENT for baseline purposes.
- **C6**: `quality_score = 100 - brisque` is asserted only for a 25.0 score (well inside the clamp). A BRISQUE score of e.g. −3.0 (piq can emit negatives, per the "can exceed in extreme cases" comment at L198) yields quality_score 103.0 vs the original's capped 100.0 — a real invariant break nobody checks.
- **C11**: `timeout=None` means a hung BRISQUE call wedges the 90-second batch window forever instead of timing out after 15 s. Tests never execute the timeout path (no slow-fake executor).

## Drafted kill-tests

Style follows the existing file: module-level `pytest.mark.asyncio` async tests, `monkeypatch.setitem(sys.modules, ...)`, plain asserts, PIL images built with `Image.new`. `// UNVERIFIED - not yet run red/green` on every draft (per harness constraints no tests were executed; TDD: each assert must FAIL on the mutant diff and PASS on the original).

### T1 — kills C1 (non-RGB input really gets converted; RGB input does not)

Target file: `backend/tests/unit/services/test_image_quality_loader.py`

Keeps the file's mock style (no real torchvision needed); the `Compose` result is an identity callable so the test can observe *which* image the pipeline received:

```python
@pytest.mark.asyncio
async def test_assess_image_quality_converts_non_rgb_image(monkeypatch):
    """Non-RGB input must be .convert("RGB")'d before tensor creation; RGB must not.

    // UNVERIFIED - not yet run red/green
    """
    import sys

    from PIL import Image

    mock_torch = MagicMock()
    mock_no_grad = MagicMock()
    mock_no_grad.__enter__ = MagicMock(return_value=None)
    mock_no_grad.__exit__ = MagicMock(return_value=None)
    mock_torch.inference_mode.return_value = mock_no_grad
    monkeypatch.setitem(sys.modules, "torch", mock_torch)

    mock_transforms = MagicMock()
    composed = MagicMock()
    composed.side_effect = lambda img: img  # pass the image through so we can see it
    mock_transforms.Compose.return_value = composed
    mock_torchvision = MagicMock()
    mock_torchvision.transforms = mock_transforms
    monkeypatch.setitem(sys.modules, "torchvision", mock_torchvision)
    monkeypatch.setitem(sys.modules, "torchvision.transforms", mock_transforms)

    mock_score = MagicMock()
    mock_score.item.return_value = 25.0
    mock_brisque_fn = MagicMock(return_value=mock_score)

    gray = Image.new("L", (16, 16))
    result = await assess_image_quality({"brisque_fn": mock_brisque_fn}, gray)

    assert isinstance(result, ImageQualityResult)
    # The tensor pipeline must have received an RGB-converted copy:
    converted = mock_brisque_fn.call_args[0][0]  # through side-effect identity
    # gray.convert("RGB") on a MagicMock-free Image returns a real Image:
    assert composed.call_args[0][0].mode == "RGB"

    # RGB input must NOT be converted (mutmut_13 polarity flip kills this leg):
    mock_brisque_fn.reset_mock()
    composed.reset_mock()
    rgb = Image.new("RGB", (16, 16))
    await assess_image_quality({"brisque_fn": mock_brisque_fn}, rgb)
    assert composed.call_args[0][0] is rgb
```

TDD procedure: on mutmut_13 (`!=`→`==`) the L-image leg fails (mode stays "L"); on mutmut_10/11/12 `convert` gets a bad mode and raises (caught → RuntimeError, fails `isinstance` assert); on mutmut_7/8 the L-image leg gets a non-RGB image → mode assert fails; on the original all asserts pass.

### T2 — kills C4 + C5 (real tensor built once, batched on dim 0; brisque called with exact kwargs)

```python
@pytest.mark.asyncio
async def test_assess_image_quality_builds_batch_tensor_and_calls_brisque_exact(monkeypatch):
    """Real ToTensor path: [1,3,H,W] tensor, data_range=1.0, reduction='mean'.

    // UNVERIFIED - not yet run red/green
    """
    import sys

    from PIL import Image

    # torch is mocked only for inference_mode; the REAL torchvision transforms run,
    # so the tensor is a real one. (If the CI image lacks torchvision, swap the
    # Compose mock per T1's style and feed a fake tensor of shape (3,8,8).)
    mock_torch_ns = MagicMock()
    mock_no_grad = MagicMock()
    mock_no_grad.__enter__ = MagicMock(return_value=None)
    mock_no_grad.__exit__ = MagicMock(return_value=None)
    mock_torch_ns.inference_mode.return_value = mock_no_grad
    monkeypatch.setitem(sys.modules, "torch", mock_torch_ns)

    mock_score = MagicMock()
    mock_score.item.return_value = 25.0

    def fake_brisque(tensor, *, data_range, reduction):
        assert tuple(tensor.shape) == (1, 3, 8, 8)  # kills mutmut_16/17/18/19
        assert 0.0 <= float(tensor.min()) and float(tensor.max()) <= 1.0
        assert data_range == 1.0                     # kills mutmut_22/27
        assert reduction == "mean"                   # kills mutmut_23/28/29
        return mock_score

    img = Image.new("RGB", (8, 8))
    result = await assess_image_quality({"brisque_fn": fake_brisque}, img)

    assert isinstance(result, ImageQualityResult)
    assert result.brisque_score == 25.0
```

If the CI image lacks torchvision, swap the body for a fake-transform harness that returns `real_torch.zeros((3,8,8))`-like shape from `MagicMock` `Compose` capturing the pipeline; the assert block is identical. Note the current success test *also* never calls `torch.inference_mode` correctly (it stubs the obsolete `torch.no_grad`, so the with-block in the original runs on a MagicMock attribute) — T2 additionally pins `inference_mode` by using a MagicMock whose `inference_mode` is set; `mutmut_18` (`transform(None)`) fails the shape assert via the `TypeError` → RuntimeError path; `mutmut_24` (`brisque_fn(...)` missing positional) raises inside `_assess` → wrapped RuntimeError → `isinstance` assert fails; `mutmut_26` (`reduction=` dropped) hits the keyword assert.

### T3 — kills C7 + C9 (threshold boundaries + quality_issues branch)

```python
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "score, is_blurry, is_noisy, is_low_quality, issues",
    [
        (39.9, False, False, False, []),                      # below all thresholds
        (40.0, False, False, True, ["general quality degradation"]),  # exactly low_quality
        (50.0, True, False, True, ["blur detected"]),         # exactly blur
        (60.0, True, True, True, ["blur detected", "noise/artifacts detected"]),  # exactly noise
    ],
)
async def test_assess_image_quality_threshold_boundaries_are_inclusive(
    monkeypatch, score, is_blurry, is_noisy, is_low_quality, issues
):
    """>= on all three thresholds: exactly-at-threshold must classify true.

    // UNVERIFIED - not yet run red/green
    """
    import sys

    from PIL import Image

    mock_torch = MagicMock()
    mock_no_grad = MagicMock()
    mock_no_grad.__enter__ = MagicMock(return_value=None)
    mock_no_grad.__exit__ = MagicMock(return_value=None)
    mock_torch.inference_mode.return_value = mock_no_grad
    monkeypatch.setitem(sys.modules, "torch", mock_torch)

    mock_transforms = MagicMock()
    mock_transforms.Compose.return_value = MagicMock(return_value=MagicMock(unsqueeze=MagicMock(return_value=MagicMock())))
    mock_torchvision = MagicMock()
    mock_torchvision.transforms = mock_transforms
    monkeypatch.setitem(sys.modules, "torchvision", mock_torchvision)
    monkeypatch.setitem(sys.modules, "torchvision.transforms", mock_transforms)

    mock_score = MagicMock()
    mock_score.item.return_value = score
    mock_brisque_fn = MagicMock(return_value=mock_score)

    result = await assess_image_quality({"brisque_fn": mock_brisque_fn}, Image.new("RGB", (4, 4)))

    assert result.is_blurry is is_blurry
    assert result.is_noisy is is_noisy
    assert result.is_low_quality is is_low_quality
    assert result.quality_issues == issues
    assert result.is_good_quality is not any([is_blurry, is_noisy, is_low_quality])
```

TDD procedure: `mutmut_46/48/50` (`>=`→`>`) fail the exactly-at-threshold rows; `mutmut_55` (`not is_blurry`→`is_blurry`) fails the (50.0) row because it drops/adds the wrong issue entry; `mutmut_53/54` (and/or swaps) fail the (40.0)/(50.0) rows where `is_low_quality and not is_blurry or not is_noisy` admits "general quality degradation" alongside blur; `mutmut_52` fails nothing here (noise clause redundant under defaults) — covered by its EQUIVALENT-adjacent status under C10 reasoning but this test still pins the issues list.

### T4 — kills C8 + C6 (result fields are real bools/lists; scores stay inside 0-100)

```python
@pytest.mark.asyncio
async def test_assess_image_quality_result_fields_are_typed_and_scores_bounded(monkeypatch):
    """is_* fields are bool (not None), quality_issues is a list, scores within [0,100].

    // UNVERIFIED - not yet run red/green
    """
    import sys

    from PIL import Image

    def harness(score_value):
        mock_torch = MagicMock()
        mock_no_grad = MagicMock()
        mock_no_grad.__enter__ = MagicMock(return_value=None)
        mock_no_grad.__exit__ = MagicMock(return_value=None)
        mock_torch.inference_mode.return_value = mock_no_grad
        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        mock_transforms = MagicMock()
        mock_transforms.Compose.return_value = MagicMock(
            return_value=MagicMock(unsqueeze=MagicMock(return_value=MagicMock()))
        )
        mock_torchvision = MagicMock()
        mock_torchvision.transforms = mock_transforms
        monkeypatch.setitem(sys.modules, "torchvision", mock_torchvision)
        monkeypatch.setitem(sys.modules, "torchvision.transforms", mock_transforms)
        mock_score = MagicMock()
        mock_score.item.return_value = score_value
        return {"brisque_fn": MagicMock(return_value=mock_score)}

    result = await assess_image_quality(harness(25.0), Image.new("RGB", (4, 4)))
    assert result.is_blurry is False
    assert result.is_noisy is False
    assert result.is_low_quality is False
    assert isinstance(result.quality_issues, list)
    assert result.quality_issues == []
    # to_dict must serialize real bools for the JSON layer:
    d = result.to_dict()
    assert d["is_blurry"] is False and d["is_noisy"] is False
    assert d["is_low_quality"] is False

    # Clamping: piq can emit out-of-range scores (module comment L197-198).
    extreme = await assess_image_quality(harness(-5.0), Image.new("RGB", (4, 4)))
    assert extreme.brisque_score == 0.0      # max(0.0, ...) — kills mutmut_35 (floor 1.0)
    assert extreme.quality_score == 100.0

    hot = await assess_image_quality(harness(150.0), Image.new("RGB", (4, 4)))
    assert hot.brisque_score == 100.0        # min(100.0, ...) — kills mutmut_40 (cap 101.0)
    assert hot.quality_score == 0.0
```

### T5 — kills C11 (15 s timeout is real: a hung assessment raises RuntimeError, not an indefinite hang)

```python
@pytest.mark.asyncio
async def test_assess_image_quality_timeout_wraps_as_runtime_error(monkeypatch):
    """A hung BRISQUE call must be cancelled by the 15s wait_for and raise RuntimeError.

    // UNVERIFIED - not yet run red/green
    """
    import asyncio

    from PIL import Image

    real_wait_for = asyncio.wait_for

    async def fake_wait_for(awaitable, *, timeout):
        assert timeout == 15.0, "timeout constant must stay at 15s"  # kills mutmut_76 (16.0)
        # Simulate the executor never finishing:
        await asyncio.sleep(0)
        raise TimeoutError
        awaitable.close()

    monkeypatch.setattr("backend.services.image_quality_loader.asyncio.wait_for", fake_wait_for)
    with pytest.raises(RuntimeError, match="timed out"):
        await assess_image_quality({"brisque_fn": MagicMock()}, Image.new("RGB", (4, 4)))
```

(If patching the module's `asyncio` binding is too broad for house style, the alternative is a slow fake executor + `monkeypatch` on `loop.run_in_executor`; the `timeout == 15.0` assert inside the wrapper is what kills both C11 keys — with `timeout=None` the assert fails immediately.)

### T6 — (optional, cheap) kills C13 raised-message text (LOW-VALUE cluster, one-line strengthen)

```python
@pytest.mark.asyncio
async def test_assess_image_quality_import_error_message_exact(monkeypatch):
    """Raised RuntimeError texts are user-facing; pin them verbatim.

    // UNVERIFIED - not yet run red/green
    """
    import builtins
    from PIL import Image

    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name in ("torch", "torchvision") or name.startswith(("torch.", "torchvision.")):
            raise ImportError(name)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)
    with pytest.raises(RuntimeError) as excinfo:
        await assess_image_quality({"brisque_fn": MagicMock()}, Image.new("RGB", (4, 4)))
    assert str(excinfo.value) == "torch and torchvision required for image quality assessment"
```

## Covering-test gaps to report to the WP4.4 ledger (file:line)

| Gap | Where | Missing assertion |
|---|---|---|
| Success test mocks every dependency, asserts only 2 scores | `backend/tests/unit/services/test_image_quality_loader.py:620-625` | flags, issues list, tensor shape/kwargs, clamp bounds, timeout |
| Success test stubs `torch.no_grad` but the code uses `torch.inference_mode` (L194) — with-context silently a bare MagicMock | same file:593-596 | `inference_mode` usage never pinned |
| Substring asserts dodge half the string (`"stable" in description.lower()` vs return `"Quality stable"`) | same file:242 | exact/prefix match for C16 |
| No test ever calls `assess_image_quality` with a non-RGB PIL image | file-wide | C1 |
| No test drives the `TimeoutError` branch of the wait_for wrapper | file-wide | C11 |

## Repro commands (read-only)

```bash
# survivors
python3 -c "import json;m=json.load(open('mutants/backend/services/image_quality_loader.py.meta'));print(sum(1 for v in m['exit_code_by_key'].values() if v==0))"
# one diff, preferred path (allowed read-only; fell back to manual block-diff here because the cache is under a concurrent live run)
uv run mutmut show backend.services.image_quality_loader.x_assess_image_quality__mutmut_46
```
