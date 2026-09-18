# WP4.4 triage dossier — `backend/services/age_classifier_loader.py`

**Survivors: 79 / 79 mutants (100% survival, 0 killed).** Two mangled functions only:
`x_classify_ages_batch` (61 survivors) and `x_load_age_classifier_model` (18 survivors).

## Why the survival rate is 100% — structural root cause

`pyproject.toml:639` sets `pytest_add_cli_args_test_selection = ["backend/tests/unit"]`.
The **only** test file in the repo that imports this module directly is
`backend/tests/integration/services/test_model_loaders.py` (line 16) — and the integration
tree is **outside mutmut's test selection**. So the whole `load_age_classifier_model`
function is exercised only by tests mutmut never runs.

`tests_by_mangled_function_name` (mutants/mutmut-stats.json) lists for both functions only
`backend/tests/unit/services/test_enrichment_{pipeline,parallelization,household_matching}.py`
tests. Those reach `classify_ages_batch` through the real call site
`backend/services/enrichment_pipeline.py:3177` (`age_batch = await classify_ages_batch(model_dict, crops)`)
with a `MagicMock` model_dict — they check pipeline orchestration, never the returned
`AgeClassificationResult`. **No unit test in the selected set asserts a single field of
anything this module returns.** That is the entire test-gap story for this module.

Consequence for remediation: **drafted tests must live under `backend/tests/unit/`** or mutmut
will keep scoring them as survivors regardless of how strong they are.

Covering-test files (with what they miss):

| File | Relevance | What it misses |
| --- | --- | --- |
| `backend/tests/unit/services/test_enrichment_parallelization.py` | only executor that actually calls `classify_ages_batch` | all result fields; passes MagicMock model_dict |
| `backend/tests/unit/services/test_enrichment_pipeline_household_matching.py` | same indirect path | ditto |
| `backend/tests/unit/services/test_enrichment_pipeline.py` | one video-path test reaching the loader | ditto |
| `backend/tests/integration/services/test_model_loaders.py:626-661` | **the only good assertions in the repo**: asserts `"model" in result` and `pytest.raises(RuntimeError, match="Failed to load age classifier")` | not in mutmut's selection → scores zero |
| `backend/tests/unit/services/test_vehicle_damage_loader.py` | style template for a sibling loader (no coverage here) | — |

## Cluster table (counts sum to 79)

`P` = production line in `backend/services/age_classifier_loader.py`.

| # | Cluster | n | Keys (≤3) | P | Class |
| --- | --- | --- | --- | --- | --- |
| L1 | CUDA guard inverted: `if not torch.cuda.is_available()` → `if …` | 1 | `x_load_age_classifier_model__mutmut_1` | 143 | TEST-GAP |
| L2 | CPU-only `RuntimeError` message text clobbered/cased/None | 4 | `…_model__mutmut_2`, `_3`, `_4` | 144-148 | TEST-GAP |
| L3 | error-handler log message case-changed | 3 | `…_model__mutmut_12`, `_13`, `_14` | 208 | LOW-VALUE |
| L3b | error-handler log message → None / arg removed | 2 | `…_model__mutmut_6`, `_9` | 208 | LOW-VALUE |
| L4 | error-handler `exc_info=True` → None/False/removed | 3 | `…_model__mutmut_7`, `_10`, `_15` | 209 | LOW-VALUE |
| L5 | error-handler `extra={"model_path":…}` → None / key clobbered | 4 | `…_model__mutmut_8`, `_11`, `_16` | 211 | LOW-VALUE |
| L6 | `raise RuntimeError(f"Failed to load …: {e}")` → `RuntimeError(None)` | 1 | `…_model__mutmut_18` | 213 | TEST-GAP |
| B1 | empty-input guard flipped: `if not images: return []` → `if images:` | 1 | `x_classify_ages_batch__mutmut_1` | 310 | TEST-GAP |
| B2 | bad dict key: `model_dict["model"]` → `["XXmodelXX"]`/`["MODEL"]` (KeyError) | 6 | `…_batch__mutmut_3`, `_4`, `_6` | 316-318 | TEST-GAP |
| B3 | value → None / arg removed → TypeError downstream (22 mutants) | 22 | `…_batch__mutmut_2`, `_5`, `_8` | 316-372 | TEST-GAP |
| B4 | RGB-conversion guard inverted / mode arg broken (5) | 5 | `…_batch__mutmut_13`, `_15`, `_16` | 325 | TEST-GAP |
| B5 | mode-arg clobbered to a value that never matches (`"XXRGBXX"`/`"rgb"`) | 2 | `…_batch__mutmut_19`, `_20` | 325 | EQUIVALENT |
| B6 | convert-guard `!=` → `or True`: always converts | 1 | `…_batch__mutmut_14` | 325 | EQUIVALENT |
| B7 | `processor(...)` kwargs clobbered: `return_tensors`/`padding` None/False/removed/cased (7) | 7 | `…_batch__mutmut_23`, `_24`, `_26` | 328 | TEST-GAP |
| B8 | `v.to(device=…, dtype=…)` args dropped/nulled | 4 | `…_batch__mutmut_36`, `_37`, `_38` | 333 | TEST-GAP |
| B9 | `softmax(all_logits, dim=-1)` → `dim=-2` (real numeric change) | 1 | `…_batch__mutmut_48` | 341 | TEST-GAP |
| B10 | `softmax` → implicit-dim / `dim=None` / `dim=+1` | 4 | `…_batch__mutmut_44`, `_45`, `_46` | 341 | EQUIVALENT |
| B12 | batch error-handler log message case-changed | 3 | `…_batch__mutmut_57`, `_58`, `_59` | 375 | LOW-VALUE |
| B13 | batch error-handler `exc_info=True` → None/False/removed | 3 | `…_batch__mutmut_54`, `_56`, `_60` | 375 | LOW-VALUE |
| B14 | batch error-handler log message → None / removed | 1 | `…_batch__mutmut_53` | 375 | LOW-VALUE |
| B15 | `raise RuntimeError(f"Batch age classification failed: {e}")` → `RuntimeError(None)` | 1 | `…_batch__mutmut_61` | 376 | TEST-GAP |

**Totals: TEST-GAP 53, EQUIVALENT 7, LOW-VALUE 19 → 79.**

Full key lists per cluster are in `/tmp/wp25/wp44-triage/acl_diffs.json` (all 79 raw diffs)
and the assignment script's output below.

## Cluster detail and reasoning

### L1 / L2 — CUDA guard + its message (2 mutants of real consequence)

`load_age_classifier_model:143-148` is the CPU fast-fail from commit 3396d3ef: without it,
ViT CPU inference holds the GIL 5-15 s/frame and starves the event loop. Mutant 1 inverts
the guard, so the loader happily loads onto a CPU-only host — exactly the failure the guard
exists to prevent. Mutants 2-5 turn the diagnostic into `None`, `XX…XX`-wrapped, lower- and
upper-case. The integration test at `test_model_loaders.py:626` mocks `cuda.is_available` to
**True**, so it never even enters the guard branch, and its only message assertion
(`match="Failed to load age classifier"`, line 660) is on the generic wrapper, not the CUDA
text. Both clusters are TEST-GAP: real behavior, zero assertion in the selected set.

### B1 — the empty-list contract

`classify_ages_batch:310-311`: `if not images: return []`. Mutant 1 inverts it — with a
non-empty list the function **skips inference entirely and falls through to `return None`**
(`await loop.run_in_executor(...)` never runs; the `try` block just ends). With an empty list
it calls the real path instead. The enrichment pipeline at line 3177 iterates the return
value, so this mutant turns every real batch into `TypeError: 'NoneType' is not iterable` —
and the pipeline tests still pass because they never assert on `age_batch`. The `return []`
for empty input is also a contract worth pinning. Highest-value single mutant in the module.

### B2 / B3 — the `except Exception → RuntimeError` net (28 mutants, TEST-GAP)

B3's 22 mutants null out `model`/`processor`/`labels`/`loop`/`rgb_images`/`inputs`/`outputs`/
`all_logits`/`all_probs`/`results` or drop a required positional arg (`softmax(None, …)`,
`run_in_executor(_classify_batch)`, `logger.error(exc_info=True)`). Every one raises
`TypeError`/`AttributeError`/`KeyError` somewhere inside `_classify_batch`, which the outer
`except Exception` (line 374-376) converts to `RuntimeError("Batch age classification
failed: …")`. The tests reach the function but assert nothing about the raise, so the
conversion net is untested. A single "failure path becomes RuntimeError, not the raw
exception" test kills all 22 plus B2's 6.

Note `mutmut_55` (`logger.error(exc_info=True)` — msg positional dropped) lands in B3 rather
than B14 because with the MagicMock logger used by callers it does not crash; it is scored as
a real-behavior crash-path variant. Counted once, in B3.

### B4 vs B5 vs B6 — the RGB conversion line (three different verdicts on one line)

Line 325: `img.convert("RGB") if img.mode != "RGB" else img`.

- **B4 (5, TEST-GAP)**: guard inverted (`==`), condition short-circuited (`and False`), and
  the mode arg made `None`/`"XXRGBXX"`/`"rgb"`. Verified against real Pillow 12.3.0:
  `L_image.convert("rgb")` and `convert("XXRGBXX")` **raise `ValueError: image has wrong
  mode`**, and `convert(None)` is a **silent no-op returning mode `L`**. So under `==` (mut 18),
  an L-mode image skips conversion (stays L → wrong tensor shape at the processor); with
  `convert(None)` (mut 15), L images are passed through unconverted. Both are real bugs for
  grayscale crops — the guard is load-bearing.
- **B5 (2, EQUIVALENT)**: `img.mode != "XXRGBXX"` / `!= "rgb"`. PIL `mode` is literally
  `"RGB"` for RGB images, so these predicates are always True exactly as the original is for
  a non-RGB image, and the convert target is unchanged. For every image that reaches the
  false-branch in the original, the mutant also takes the true-branch and re-converts RGB→RGB,
  which Pillow short-circuits to the same image. Behaviorally identical on every input.
- **B6 (1, EQUIVALENT)**: `(img.mode != "RGB") or True` → always converts. `convert("RGB")`
  on an already-RGB image is a no-op returning an equivalent RGB image, so output is the same.
  (Wastes a copy; nobody should assert that.)

### B7 / B8 — processor and `.to()` call shape (11, TEST-GAP)

`processor(images=…, return_tensors="pt", padding=True)` at line 328 and
`{k: v.to(device=…, dtype=…)}` at line 333. Under a `MagicMock` processor the kwargs are
invisible unless a test **asserts the call kwargs** (`return_tensors="pt"`, `padding=True`) and
that each input tensor was moved to the model's device/dtype. Without `return_tensors="pt"`
the real processor hands back a list of ndarrays instead of a tensor — a hard production
break. Nobody asserts either property.

### B9 vs B10 — softmax `dim` (1 real + 4 equivalent)

Line 341: `softmax(all_logits, dim=-1)`. Verified with real torch: for logits shaped
`(batch, num_labels)` (what a ViT image-classification head emits), `dim=-1` and `dim=-2`
give genuinely different numbers — e.g. logits `[[0.1,2.0,0.5],[1.0,0.2,3.0]]` produce row 0
`[0.109, 0.7285, 0.1625]` (conf 0.729, row sums to 1.0) vs `[0.2891, 0.8581, 0.0759]`
(conf 0.858, row sums to 1.22 — **not a probability distribution**). `dim=-1` is correct;
mutant 48 silently breaks calibration of every confidence the system reports, and downstream
`format_age_context`'s `<0.5 / <0.7` confidence qualifiers. TEST-GAP.

Mutants 44/45/46 (`dim=None`, positional arg dropped, trailing-comma) collapse to torch's
implicit-dim softmax, which for a 2-D tensor normalizes along the last dimension — verified
byte-identical to `dim=-1` on the same input. Equivalence holds for exactly the 2-D logits
this head emits. 47 (`dim=+1`) raises `IndexError: Dimension out of range` on 2-D input, so it
is caught by the same failure-path test as B3; it is grouped with B10 for the pattern, and
killed by the same drafted test either way.

### L3/L3b/L4/L5, B12/B13/B14 — logging cosmetics (20, LOW-VALUE)

Log message case (`"Batch age classification failed"` → `"BATCH AGE CLASSIFICATION FAILED"`),
`exc_info=True` → `False`/`None`/removed, and `extra={"model_path": …}` → `None` or key
renamed. These change only log rendering: whether the traceback is attached and whether the
JSON handler emits a `model_path` field. No production consumer reads the log text or the
`extra` keys of these two handlers, and asserting exact log strings is the kind of test that
locks implementation, not behavior. Real changes, nothing worth asserting → LOW-VALUE.
(The one arguable exception is `extra={"model_path"}` — if the ops dashboards ever filter on
it, promote L5 to TEST-GAP with a `caplog` record assertion. Not today.)

## Drafted tests — UNVERIFIED, never run red/green

**Target file: `backend/tests/unit/services/test_age_classifier_loader.py` (new).**

Two hard requirements, both learned from the root cause above: (a) it must be under
`backend/tests/unit/` or mutmut will not see it; (b) nothing imports this module from the
unit tree today, so the file is created from scratch, following the conventions of
`backend/tests/unit/services/test_vehicle_damage_loader.py` (`from __future__ import
annotations`, `MagicMock`, class-per-function, `pytest.mark.asyncio` under
`asyncio_mode = "auto"`).

```python
"""Unit tests for the ViT age classifier loader.

Tests cover:
- load_age_classifier_model CUDA fast-fail and error wrapping
- classify_ages_batch empty-input contract
- classify_ages_batch failure-to-RuntimeError wrapping
- classify_ages_batch processor/device/dtype call shape
- classify_ages_batch softmax normalization and returned result fields
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest
import torch
from PIL import Image

from backend.services.age_classifier_loader import (
    AGE_DISPLAY_NAMES,
    AgeClassificationResult,
    classify_ages_batch,
    load_age_classifier_model,
)


@pytest.fixture
def mock_torch(monkeypatch):
    """Install a fake torch whose CUDA is available.

    Production load_age_classifier_model fast-fails on CPU-only hosts
    (3396d3ef); simulating a GPU host is the established pattern used by
    the integration loader tests.
    """
    fake = MagicMock()
    fake.cuda.is_available.return_value = True
    monkeypatch.setitem(sys.modules, "torch", fake)
    return fake


# ---------------------------------------------------------------------------
# load_age_classifier_model
# ---------------------------------------------------------------------------


class TestLoadAgeClassifierModel:
    """CUDA guard and error-wrapping for the loader."""

    @pytest.mark.asyncio
    async def test_raises_runtime_error_on_cpu_only_host(self, monkeypatch) -> None:
        """Kills load_age_classifier_model__mutmut_1 (guard inverted).

        The guard must reject CPU-only hosts: ViT CPU inference holds the GIL
        for seconds per frame and starves the event loop.
        """
        fake_torch = MagicMock()
        fake_torch.cuda.is_available.return_value = False
        monkeypatch.setitem(sys.modules, "torch", fake_torch)
        monkeypatch.setitem(sys.modules, "transformers", MagicMock())

        with pytest.raises(RuntimeError) as exc_info:
            await load_age_classifier_model("/models/model-zoo/vit-age-classifier")

        assert "CUDA" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_cpu_error_message_is_human_readable(self, monkeypatch) -> None:
        """Kills load_age_classifier_model__mutmut_2..5 (message -> None/case/clobber)."""
        fake_torch = MagicMock()
        fake_torch.cuda.is_available.return_value = False
        monkeypatch.setitem(sys.modules, "torch", fake_torch)
        monkeypatch.setitem(sys.modules, "transformers", MagicMock())

        with pytest.raises(RuntimeError) as exc_info:
            await load_age_classifier_model("/models/model-zoo/vit-age-classifier")

        message = str(exc_info.value)
        assert message
        assert "XX" not in message
        assert message == message.strip()
        assert "Age Classifier requires a CUDA GPU" in message

    @pytest.mark.asyncio
    async def test_load_failure_wrapped_in_runtime_error(self, monkeypatch) -> None:
        """Kills load_age_classifier_model__mutmut_18 (RuntimeError(None))."""
        fake_torch = MagicMock()
        fake_torch.cuda.is_available.return_value = True
        monkeypatch.setitem(sys.modules, "torch", fake_torch)

        fake_transformers = MagicMock()
        fake_transformers.AutoModelForImageClassification.from_pretrained.side_effect = (
            ValueError("weights missing")
        )
        monkeypatch.setitem(sys.modules, "transformers", fake_transformers)

        with pytest.raises(RuntimeError) as exc_info:
            await load_age_classifier_model("/nonexistent/path")

        assert "weights missing" in str(exc_info.value)
        assert "None" not in str(exc_info.value)


# ---------------------------------------------------------------------------
# classify_ages_batch
# ---------------------------------------------------------------------------


def _labels() -> list[str]:
    return ["child", "adult", "senior"]


def _logits() -> torch.Tensor:
    # (batch=2, num_labels=3): row 0 peaks on "adult", row 1 peaks on "senior".
    return torch.tensor([[0.1, 2.0, 0.5], [1.0, 0.2, 3.0]])


def _model_dict(processor: MagicMock, model: MagicMock) -> dict:
    return {"model": model, "processor": processor, "labels": _labels()}


class TestClassifyAgesBatchEmpty:
    """The empty-input contract."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_no_images(self) -> None:
        """Kills classify_ages_batch__mutmut_1 (empty guard inverted)."""
        model_dict = _model_dict(MagicMock(), MagicMock())

        result = await classify_ages_batch(model_dict, [])

        assert result == []

    @pytest.mark.asyncio
    async def test_non_empty_input_produces_one_result_per_image(self) -> None:
        """Kills classify_ages_batch__mutmut_1 from the other side: with the guard
        inverted the function skips inference and returns None."""
        processor = MagicMock(return_value={"pixel_values": torch.zeros(2, 3, 4, 4)})
        model = MagicMock()
        model.parameters.return_value = iter(
            [torch.zeros(1, dtype=torch.float32, device="cpu")]
        )
        outputs = MagicMock()
        outputs.logits = _logits()
        model.return_value = outputs

        images = [Image.new("RGB", (8, 8)), Image.new("RGB", (8, 8))]
        result = await classify_ages_batch(_model_dict(processor, model), images)

        assert isinstance(result, list)
        assert len(result) == 2


class TestClassifyAgesBatchFailurePath:
    """Failures inside the executor must surface as RuntimeError."""

    @pytest.mark.asyncio
    async def test_processor_failure_raises_runtime_error(self) -> None:
        processor = MagicMock()
        processor.side_effect = ValueError("bad tensors")
        model = MagicMock()

        images = [Image.new("RGB", (8, 8))]
        with pytest.raises(RuntimeError, match="Batch age classification failed"):
            await classify_ages_batch(_model_dict(processor, model), images)

    @pytest.mark.asyncio
    async def test_model_dict_missing_keys_raises_runtime_error(self) -> None:
        """Kills classify_ages_batch__mutmut_3/4/6/7/9/10 (model_dict['XXmodelXX'])."""
        images = [Image.new("RGB", (8, 8))]

        for key in ("model", "processor", "labels"):
            broken = _model_dict(MagicMock(), MagicMock())
            broken[key] = broken.pop(key)  # keep dict, rename the lookup source below
            broken["__sentinel__"] = broken.pop(key)
            with pytest.raises(RuntimeError) as exc_info:
                await classify_ages_batch(broken, images)
            assert "Batch age classification failed" in str(exc_info.value)


class TestClassifyAgesBatchCallShape:
    """Processor / device / dtype plumbing."""

    @pytest.mark.asyncio
    async def test_processor_called_with_pt_tensors_and_padding(self) -> None:
        """Kills classify_ages_batch__mutmut_23/24/26/27/28/29/30."""
        processor = MagicMock(return_value={"pixel_values": torch.zeros(2, 3, 4, 4)})
        model = MagicMock()
        model.parameters.return_value = iter(
            [torch.zeros(1, dtype=torch.float32, device="cpu")]
        )
        outputs = MagicMock()
        outputs.logits = _logits()
        model.return_value = outputs

        await classify_ages_batch(
            _model_dict(processor, model),
            [Image.new("RGB", (8, 8)), Image.new("RGB", (8, 8))],
        )

        _, kwargs = processor.call_args
        assert kwargs["return_tensors"] == "pt"
        assert kwargs["padding"] is True
        assert len(kwargs["images"]) == 2

    @pytest.mark.asyncio
    async def test_inputs_moved_to_model_device_and_dtype(self) -> None:
        """Kills classify_ages_batch__mutmut_36/37/38/39."""
        moved: list[tuple] = []

        class TrackingTensor:
            def __init__(self) -> None:
                self.children: list[TrackingTensor] = []

            def to(self, **kwargs):
                moved.append(tuple(sorted(kwargs.items())))
                child = TrackingTensor()
                self.children.append(child)
                return child

            def __len__(self) -> int:
                return 2

            def __getitem__(self, idx):
                return self.children[idx]

        tracker = TrackingTensor()
        processor = MagicMock(return_value={"pixel_values": tracker})
        param = MagicMock()
        param.device = torch.device("cpu")
        param.dtype = torch.float32
        model = MagicMock()
        model.parameters.return_value = iter([param])
        outputs = MagicMock()
        outputs.logits = _logits()
        model.return_value = outputs

        await classify_ages_batch(
            _model_dict(processor, model),
            [Image.new("RGB", (8, 8)), Image.new("RGB", (8, 8))],
        )

        assert moved, "inputs were never moved to the model device/dtype"
        for call in moved:
            assert ("device", torch.device("cpu")) in call
            assert ("dtype", torch.float32) in call


class TestClassifyAgesBatchResults:
    """The numbers the rest of the system trusts."""

    @pytest.mark.asyncio
    async def test_probabilities_normalized_per_image(self) -> None:
        """Kills classify_ages_batch__mutmut_48 (softmax dim=-1 -> dim=-2).

        Per-image scores must be a probability distribution over the label set.
        dim=-2 normalizes along the batch axis and yields rows summing to != 1.
        """
        processor = MagicMock(return_value={"pixel_values": torch.zeros(2, 3, 4, 4)})
        model = MagicMock()
        model.parameters.return_value = iter(
            [torch.zeros(1, dtype=torch.float32, device="cpu")]
        )
        outputs = MagicMock()
        outputs.logits = _logits()
        model.return_value = outputs

        results = await classify_ages_batch(
            _model_dict(processor, model),
            [Image.new("RGB", (8, 8)), Image.new("RGB", (8, 8))],
        )

        for result in results:
            assert sum(result.all_scores.values()) == pytest.approx(1.0, abs=1e-6)

        # dim=-2 would put row 0 "adult" at 0.8581 instead of 0.7285.
        assert results[0].confidence == pytest.approx(0.7285, abs=1e-3)
        assert results[0].age_group == "adult"
        assert results[1].age_group == "senior"
        assert results[1].confidence > results[0].confidence

    @pytest.mark.asyncio
    async def test_result_fields_and_minor_flag(self) -> None:
        processor = MagicMock(return_value={"pixel_values": torch.zeros(2, 3, 4, 4)})
        model = MagicMock()
        model.parameters.return_value = iter(
            [torch.zeros(1, dtype=torch.float32, device="cpu")]
        )
        outputs = MagicMock()
        outputs.logits = _logits()
        model.return_value = outputs

        results = await classify_ages_batch(
            _model_dict(processor, model),
            [Image.new("RGB", (8, 8)), Image.new("RGB", (8, 8))],
        )

        first = results[0]
        assert isinstance(first, AgeClassificationResult)
        assert first.display_name == AGE_DISPLAY_NAMES[first.age_group]
        assert len(first.all_scores) == 3  # top-3 only
        assert first.is_minor is (first.age_group == "child")


class TestClassifyAgesBatchNonRGB:
    """Grayscale crops must still be converted to RGB."""

    @pytest.mark.asyncio
    async def test_grayscale_images_converted_to_rgb(self) -> None:
        """Kills classify_ages_batch__mutmut_13/15/16/17/18 (RGB guard/arg).

        convert(None) is a silent no-op and the inverted == guard skips the
        conversion for L-mode images -- both hand the processor non-RGB input.
        """
        processor = MagicMock(return_value={"pixel_values": torch.zeros(2, 3, 4, 4)})
        model = MagicMock()
        model.parameters.return_value = iter(
            [torch.zeros(1, dtype=torch.float32, device="cpu")]
        )
        outputs = MagicMock()
        outputs.logits = _logits()
        model.return_value = outputs

        await classify_ages_batch(
            _model_dict(processor, model),
            [Image.new("L", (8, 8)), Image.new("RGBA", (8, 8))],
        )

        _, kwargs = processor.call_args
        for image in kwargs["images"]:
            assert image.mode == "RGB"
```

**TDD procedure (one line each):** apply the mutant's one-line diff to the source, run
`uv run pytest backend/tests/unit/services/test_age_classifier_loader.py` and see the listed
test FAIL on the mutant (the assertion above names the exact field/kwargs/dim it pins), then
restore the original and see it PASS — never `mutmut run`.

Caveats, stated because they are unverified: `test_model_dict_missing_keys_raises_runtime_error`
is the weakest draft (it renames keys rather than reproducing the literal `["XXmodelXX"]`
lookup — the two `test_processor_failure_raises_runtime_error`/`test_model_dict_*` tests
together are what make the failure-path cluster bite); and `test_probabilities_normalized_per_image`
depends on the mock `model.parameters()` iterator being consumed exactly once — if a future
refactor calls `next(model.parameters())` twice, switch to a re-iterable `MagicMock(spec=...)`
rather than loosening the assertion.

## Kill forecast

| Drafted test | Kills |
| --- | --- |
| `test_returns_empty_list_for_no_images` + `test_non_empty_input_produces_one_result_per_image` | B1 (1) |
| `test_processor_failure_raises_runtime_error` + `test_model_dict_missing_keys_raises_runtime_error` | B2, B3 (28) |
| `test_processor_called_with_pt_tensors_and_padding` | B7 (7) |
| `test_inputs_moved_to_model_device_and_dtype` | B8 (4) |
| `test_probabilities_normalized_per_image` | B9, B10 partially (1-5) |
| `test_grayscale_images_converted_to_rgb` | B4 (5) |
| `test_raises_runtime_error_on_cpu_only_host` | L1 (1) |
| `test_cpu_error_message_is_human_readable` | L2 (4) |
| `test_load_failure_wrapped_in_runtime_error` | L6 (1) |

Up to **52 of 79** survivors killed (66%), leaving the 19 LOW-VALUE logging mutants and the
7 EQUIVALENT ones plus a few of B10's implicit-dim twins as permanently surviving — which is
the correct end state for this module, since asserting log text and PIL no-op copies would
test the framework rather than this code.
