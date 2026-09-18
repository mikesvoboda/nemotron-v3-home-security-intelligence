# WP4.4 Triage Dossier — backend/services/gender_classifier_loader.py

**Survivors: 96 / 96** (meta: all 96 keys `exit_code: 0`; 0 killed, 0 unchecked).
Mutant-function split: `x_classify_genders_batch` 75, `x_load_gender_classifier_model` 18, `x__find_label_index` 3.

## Method

- Verdicts read from `mutants/backend/services/gender_classifier_loader.py.meta` (`exit_code_by_key`, 0 == survived).
- Diffs via span-slicing `mutants/.../gender_classifier_loader.py` (spans = **1-based inclusive line ranges**, `x_<fn>__mutmut_N` blocks) against each `x_<fn>__mutmut_orig` block. All 96 survivor diffs extracted and inspected individually; raw dump at `/tmp/wp25/gcl-diffs.json`.
- PIL `convert()` semantics checked empirically in the project venv: `convert("rgb")` / `convert("XXRGBXX")` raise `ValueError`; `convert(None)` returns the image in its *own* mode (identity); `convert("RGB")` on an RGB image is a functional no-op. This settles three "always-convert" mutants as EQUIVALENT.
- `mutmut show` was not used (live run owns the cache); manual span diffing used throughout.

## Covering tests (mutmut-stats.json `tests_by_mangled_function_name`)

| Mutant function | Recorded tests | Nature |
|---|---|---|
| `x_load_gender_classifier_model` | `backend/tests/unit/services/test_enrichment_pipeline.py::TestEnrichmentPipelineVideoHandling::test_enrich_batch_with_video_path` (file `/agents/agent-nemo2/workspace/backend/tests/unit/services/test_enrichment_pipeline.py`, class :4866, test :5125) | incidental |
| `x_classify_genders_batch` | `test_enrichment_pipeline_household_matching.py::TestEnrichmentPipelineHouseholdMatching` (class :237, 3 tests), `test_enrichment_parallelization.py` (classes :191, :425, :651, :894, 7 tests), `test_enrichment_pipeline.py::TestEnrichmentPipelineErrorHandlingExtended::test_face_detection_model_not_available` (class :3040) — all under `/agents/agent-nemo2/workspace/backend/tests/unit/services/` | incidental |
| `x__find_label_index` | same 11 pipeline tests as batch | incidental |

**Root cause of the gap:** there is no direct unit test file for this module (`backend/tests/unit/services/` has `test_pet_classifier_loader.py`, `test_vehicle_classifier_loader.py`, … but no `test_gender_classifier_loader.py`; the only direct coverage is GPU-gated `backend/tests/integration/services/test_model_loaders.py`, outside the mutmut run). Every "covering" test reaches the module through `EnrichmentPipeline._classify_demographics`, which wraps `classify_genders_batch` in a blanket `try/except Exception → record_enrichment_model_error → logger.debug` (`backend/services/enrichment_pipeline.py:3192-3214`) and mocks the model manager (`vit-gender-classifier` isn't even in their mock model tables, `test_enrichment_parallelization.py:120-158`). The function bodies never execute under these tests; exceptions are swallowed. Hence 96/96 survive: **any** change — crash, None, guard flip, wrong scores — is invisible.

## Cluster table (counts sum to 96; every key assigned exactly once)

Batch keys `b_<n>` = `x_classify_genders_batch__mutmut_n`; loader `l_<n>`; index `f_<n>`.

| # | Pattern | Count | Example keys | Class |
|---|---|---|---|---|
| 1 | batch: `model_dict["model"/"processor"/"labels"]` extraction → `None` or clobbered/uppercased key (crash on any real call) | 9 | b_2, b_3, b_5 | TEST-GAP |
| 2 | batch: RGB-convert comprehension real change — `rgb_images=None`, never-convert (`and False`), flipped guard (`mode == "RGB"`, L images leak through), `convert(None)` (identity, L leaks), `convert("XXRGBXX"/"rgb")` (ValueError) | 6 | b_12, b_15, b_18 | TEST-GAP |
| 3 | batch: RGB-convert *always-convert* variants (`(cond) or True`, `mode != "XXRGBXX"`, `mode != "rgb"` — all conditions tautologies; `convert("RGB")` on an RGB image is a no-op copy) | 3 | b_14, b_19, b_20 | EQUIVALENT |
| 4 | batch: processor-call mutations — `inputs=None`, `images=None`/dropped, `return_tensors=None/"XXptXX"/"PT"`/dropped, `padding=None/False`/dropped | 10 | b_21, b_23, b_30 | TEST-GAP |
| 5 | batch: device/dtype extraction and `.to()` move — `device=None`, `next(None)`, `dtype=None`, device/dtype kwarg dropped | 9 | b_31, b_32, b_38 | TEST-GAP |
| 6 | batch: inference + softmax — `outputs=None`, `all_logits=None`, `all_probs=None`, `softmax(None)`, `dim=None/+1/-2`/dropped | 9 | b_40, b_44, b_47 | TEST-GAP |
| 7 | batch: `male_idx`/`female_idx` lookup replaced by `None` (scores silently fall to index-0/1 fallback) | 2 | b_49, b_56 | TEST-GAP |
| 8 | batch: empty-input guard flip `if not images:` → `if images:` (empty runs the model; non-empty returns `[]`) | 1 | b_1 | TEST-GAP |
| 9 | batch: `_find_label_index` args mutated — `labels=None`, `target=None`, one-arg call, `"XXmaleXX"`/`"XXfemaleXX"` (lookup returns None → wrong male/female scores with reversed-order labels) | 10 | b_50, b_54, b_61 | TEST-GAP |
| 10 | batch: `_find_label_index(labels, "MALE"/"FEMALE")` uppercase target — function lowercases target internally → identical behavior | 2 | b_55, b_62 | EQUIVALENT |
| 11 | batch: executor plumbing — `loop=None`, `run_in_executor(None, None)` / fn or executor arg dropped (TypeError on every call) | 4 | b_11, b_64, b_66 | TEST-GAP |
| 12 | batch: `results = []` → `results = None` (crashes on first `.append` in the loop) | 1 | b_63 | TEST-GAP |
| 13 | batch: error envelope — `raise RuntimeError(None)` (message gone) and `logger.error` msg dropped inside `except` → `TypeError` replaces the `RuntimeError` callers expect | 2 | b_69, b_75 | TEST-GAP |
| 14 | batch: error-path logger record tweaks — message text clobber/case/None, `exc_info` → None/False/dropped (exception type+message unchanged; nobody consumes these strings) | 7 | b_67, b_68, b_71 | LOW-VALUE |
| 15 | loader: CUDA gate flipped `if not torch.cuda.is_available():` → `if torch.cuda.is_available():` — CPU-only hosts silently run the GIL-starving ViT on CPU (the documented hazard) instead of raising | 1 | l_1 | TEST-GAP |
| 16 | loader: CPU-rejection `RuntimeError` message mutated to `None`/clobbered/lowercase/uppercase → wrapped error text no longer cites the CUDA requirement | 4 | l_2, l_3, l_4 | TEST-GAP |
| 17 | loader: `logger.error` msg arg dropped inside generic `except` → `TypeError` replaces the documented `RuntimeError` | 1 | l_9 | TEST-GAP |
| 18 | loader: `raise RuntimeError(f"Failed to load gender classifier model: {e}")` → `RuntimeError(None)` | 1 | l_18 | TEST-GAP |
| 19 | loader: error-path `logger.error` record tweaks — message None/case/clobber, `exc_info` weakened, `extra={"model_path":…}` dropped/case-clobbered | 11 | l_6, l_8, l_16 | LOW-VALUE |
| 20 | `_find_label_index` body: `target_lower = None` / `target.upper()` / `enumerate(None)` — crashes or silently returns `None` for every lookup | 3 | f_1, f_2, f_3 | TEST-GAP |

Totals: **TEST-GAP 73 · EQUIVALENT 5 · LOW-VALUE 18 = 96.**

TEST-GAP vs LOW-VALUE line drawn at observable behavior that survives the swallowing except: exception type/message and computed result values (TEST-GAP) vs pure logging-record text/flags on an already-raised error path (LOW-VALUE, clusters 14/19 — 18 survivors that should stay dead-equivalent; asserting logger call shapes here buys nothing).

## Drafted tests — target file `backend/tests/unit/services/test_gender_classifier_loader.py` (NEW; sibling donor: `backend/tests/unit/services/test_pet_classifier_loader.py` — `monkeypatch.setitem(sys.modules, "torch", …)`, MagicMock processor/model, async tests; `asyncio_mode = "auto"` in pyproject)

All five marked **UNVERIFIED — not yet run red/green.** TDD procedure for each: apply the cluster's mutant diff → the named assertion fails; revert to original → passes.

### T1 `test_load_gender_classifier_model_rejects_cpu_only_host` — kills cluster 15 + 16

```python
"""Unit tests for gender_classifier_loader service.

Covers the ViT gender classifier loader and batch classification.
WP4.4 kill-tests for the gen-2 survivor clusters.

// UNVERIFIED - not yet run red/green
"""

import math
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PIL import Image

from backend.services.gender_classifier_loader import (
    classify_genders_batch,
    load_gender_classifier_model,
)

CPU_REJECTION = (
    "Gender Classifier requires a CUDA GPU — ViT CPU inference holds the GIL for 5-15 s "
    "per frame and starves the async event loop. Skipping on CPU-only host."
)


@pytest.mark.asyncio
async def test_load_gender_classifier_model_rejects_cpu_only_host(monkeypatch):
    """CPU-only host must raise, citing the CUDA GPU requirement verbatim.

    Kills l_1 (CUDA-gate flip -> load proceeds, no rejection) and l_2..l_5
    (RuntimeError(None)/clobbered/case-flipped message changes the wrapped text).
    TDD: on mutant str(exc) lacks the exact rejection text -> assert fails; on
    original the wrapped message ends with CPU_REJECTION -> passes.
    // UNVERIFIED - not yet run red/green
    """
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "transformers", MagicMock())

    with pytest.raises(RuntimeError) as exc_info:
        await load_gender_classifier_model("/test/model/path")
    assert str(exc_info.value) == f"Failed to load gender classifier model: {CPU_REJECTION}"
```

### T2 `test_load_gender_classifier_model_wraps_load_failure_as_runtime_error` — kills cluster 17 + 18

```python
@pytest.mark.asyncio
async def test_load_gender_classifier_model_wraps_load_failure_as_runtime_error(monkeypatch):
    """Any load failure surfaces as RuntimeError('Failed to load … : <cause>').

    Kills l_9 (logger.error(msg dropped -> TypeError escapes instead of RuntimeError)
    and l_18 (RuntimeError(None) -> empty message).
    TDD: on l_9 a TypeError (not RuntimeError) is raised; on l_18 str(exc) == "None"
    -> match fails; on original passes.
    // UNVERIFIED - not yet run red/green
    """
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = True
    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    mock_transformers = MagicMock()
    mock_transformers.AutoImageProcessor.from_pretrained.side_effect = OSError("missing config")
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    with pytest.raises(RuntimeError, match="Failed to load gender classifier model: missing config"):
        await load_gender_classifier_model("/test/model/path")
```

### T3 `test_classify_genders_batch_success` — kills clusters 1,2,4,5,6,7,9,11,12,20 (63 survivors incl. all 3 `_find_label_index`)

```python
class _Scalar:
    def __init__(self, value):
        self._value = value

    def item(self):
        return self._value


def _make_row(row):
    r = MagicMock(name="row")
    r.__len__ = lambda self: len(row)
    r.__getitem__ = lambda self, i: _Scalar(row[i])
    argmax = MagicMock(name="argmax")
    argmax.item.return_value = max(range(len(row)), key=lambda i: row[i])
    r.argmax.return_value = argmax
    return r


def _make_batch_tensor(rows):
    t = MagicMock(name="batch")
    t.__iter__ = lambda self: iter([_make_row(r) for r in rows])
    return t


def _softmax(rows):
    out = []
    for row in rows:
        m = max(row)
        exps = [math.exp(x - m) for x in row]
        s = sum(exps)
        out.append([e / s for e in exps])
    return out


LOGITS = [[4.0, 1.0], [1.0, 4.0]]  # img0 -> Female, img1 -> Male (labels order below)


def _make_model_dict():
    """model_dict whose mocks police every call the function is supposed to make."""
    labels = ["Female", "Male"]  # deliberately reversed order: index 0 = female

    def fake_processor(images=None, return_tensors=None, padding=None):
        if not images:  # kills b_22, b_25 (images=None/dropped)
            raise AssertionError("processor called without images")
        assert all(img.mode == "RGB" for img in images)  # kills b_13/_15/_18 (L-mode leak)
        assert return_tensors == "pt"  # kills b_23/_26/_27/_28/_29
        assert padding is True  # kills b_24/_30
        px = MagicMock()
        px._batch = images
        px.to.return_value = px  # v.to(...) keeps identity so _batch survives
        return {"pixel_values": px}

    processor = MagicMock(side_effect=fake_processor)

    def fake_model(**inputs):
        assert len(inputs) == 1
        px = inputs["pixel_values"]
        moved = px.to.call_args
        assert moved is not None
        assert moved.kwargs.get("device") == "cpu"  # kills b_31/_32/_36/_38
        assert moved.kwargs.get("dtype") == "float16"  # kills b_33/_34/_37/_39
        assert len(px._batch) == 2
        return SimpleNamespace(logits=_make_batch_tensor(LOGITS))

    model = MagicMock(side_effect=fake_model)
    model.parameters.return_value = iter([SimpleNamespace(device="cpu", dtype="float16")])
    return {"model": model, "processor": processor, "labels": labels}


@pytest.mark.asyncio
async def test_classify_genders_batch_success(monkeypatch):
    """End-to-end happy path policing key extraction, RGB conversion, processor
    kwargs, device/dtype move, softmax(dim=-1), and label-indexed scores.

    Kills clusters 1 (b_2..b_10), 2 (b_12/_13/_15/_16/_17/_18), 4 (b_21..b_30),
    5 (b_31..b_39), 6 (b_40..b_48), 7 (b_49, b_56), 9 (b_50..b_54, b_57..b_61),
    11 (b_11, b_64..b_66), 12 (b_63) and 20 (f_1..f_3, exercised via the lookups).
    Uppercase male/female targets are covered by cluster 20's path (f_2 upper()
    lookup returns None -> wrong indexed scores).
    TDD: any listed mutant trips a mock assertion or changes an indexed score ->
    test fails; original passes.
    // UNVERIFIED - not yet run red/green
    """
    mock_torch = MagicMock()
    probs = _softmax(LOGITS)
    mock_torch.nn.functional.softmax.side_effect = lambda x, dim=-1: _make_batch_tensor(probs)
    monkeypatch.setitem(sys.modules, "torch", mock_torch)

    images = [Image.new("RGB", (8, 8)), Image.new("L", (8, 8))]  # 2nd forces convert()
    results = await classify_genders_batch(_make_model_dict(), images)

    assert len(results) == 2
    call = mock_torch.nn.functional.softmax.call_args  # kills b_42..b_48
    assert call is not None and call.kwargs.get("dim") == -1
    # labels ["Female","Male"]: img0 argmax idx0 -> female; img1 idx1 -> male
    assert results[0].gender == "female"
    assert results[1].gender == "male"
    assert results[0].female_score == pytest.approx(probs[0][0])  # index 1 would be male score
    assert results[0].male_score == pytest.approx(probs[0][1])
    assert results[1].male_score == pytest.approx(probs[1][1])
    assert results[1].female_score == pytest.approx(probs[1][0])
    assert results[0].confidence == pytest.approx(probs[0][0])
    assert results[1].confidence == pytest.approx(probs[1][1])
    assert images[1].mode == "L"  # convert() must not mutate the source in place
```

### T4 `test_classify_genders_batch_empty_input_returns_empty_without_model_access` — kills cluster 8

```python
@pytest.mark.asyncio
async def test_classify_genders_batch_empty_input_returns_empty_without_model_access():
    """Empty image list short-circuits to [] before touching model_dict.

    Kills b_1 (`if not images:` -> `if images:`): empty input would proceed and
    non-empty would return [].
    TDD: on mutant the await raises (model_dict access trips the side_effect);
    on original `== []`.
    // UNVERIFIED - not yet run red/green
    """
    boom = MagicMock(name="model_dict")
    boom.__getitem__.side_effect = AssertionError("model_dict touched for empty input")
    assert await classify_genders_batch(boom, []) == []
```

### T5 `test_classify_genders_batch_failure_raises_runtime_error_with_cause` — kills cluster 13

```python
@pytest.mark.asyncio
async def test_classify_genders_batch_failure_raises_runtime_error_with_cause(monkeypatch):
    """Model failures surface as RuntimeError('Batch gender classification failed: …').

    Kills b_75 (RuntimeError(None) -> message "None") and b_69 (logger.error msg
    dropped inside the except -> TypeError escapes instead of RuntimeError).
    TDD: on b_75 the match fails; on b_69 a TypeError is raised; on original passes.
    // UNVERIFIED - not yet run red/green
    """
    mock_torch = MagicMock()
    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    model = MagicMock()
    model.parameters.side_effect = RuntimeError("GPU OOM")
    model_dict = {"model": model, "processor": MagicMock(), "labels": ["male", "female"]}

    with pytest.raises(RuntimeError, match="Batch gender classification failed: GPU OOM"):
        await classify_genders_batch(model_dict, [Image.new("RGB", (8, 8))])
```

## Coverage accounting of the 5 drafted tests

| Killed cluster | Count | Killed by |
|---|---|---|
| 1 (9) + 2 (6) + 4 (10) + 5 (9) + 6 (9) + 7 (2) + 9 (10) + 11 (4) + 12 (1) + 20 (3) | 63 | T3 |
| 8 (1) | 1 | T4 |
| 13 (2) | 2 | T5 |
| 15 (1) + 16 (4) | 5 | T1 |
| 17 (1) + 18 (1) | 2 | T2 |
| **Total killed** | **73** = all TEST-GAP | |

Left dead by design: 5 EQUIVALENT (unkillable), 18 LOW-VALUE (logging-record tweaks; asserting them is not worthwhile — see clusters 14/19).

## Caveats

- T3 asserts `device`/`dtype` kwarg values on `.to(...)`; if `float16` is ever changed to a sentinel elsewhere, update both spots. The reversed label order `["Female","Male"]` is load-bearing — with the common `["Male","Female"]` order, clusters 7/9's `None`-idx fallback silently produces identical scores and survives.
- T1 pins the CPU_REJECTION text verbatim (em-dash included); if the loader message is intentionally reworded, update the constant.
- All five tests execute `classify_genders_batch`/`load_gender_classifier_model` directly — they must NOT be routed through `EnrichmentPipeline`, or the swallowing except re-hides everything.
