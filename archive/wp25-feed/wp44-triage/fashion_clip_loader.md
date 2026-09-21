# WP4.4 triage dossier — `backend/services/fashion_clip_loader.py`

**Source:** `backend/services/fashion_clip_loader.py` (586 lines)
**Verdict cache:** `mutants/backend/services/fashion_clip_loader.py.meta` — 175 keys total, **91 SURVIVED (exit 0)**, 84 killed. All 91 diffs read via `uv run mutmut show <key>` (no fallback diffing needed; one key needed a re-fetch because the batch loop dropped the last line — re-read, counted).
**Module split of survivors:** `x_classify_clothing` 29 · `x_classify_clothing_batch` 26 · `x_load_fashion_clip_model` 26 · `x_format_clothing_context` 10.

## Root cause (one sentence)

`classify_clothing` / `classify_clothing_batch` are **never executed successfully by any test**. The only tests that call them at all
(`test_fashion_clip_loader.py:522` and `:693`) force a failure (`mock_preprocess.side_effect = ValueError`) and assert only the
`RuntimeError` text. Worse, `test_fashion_clip_loader.py:543-772` contains six "**_reimplementation_**" tests that copy the
sort / flag / description / top-k logic *into the test body* and assert on the copy — they give the appearance of coverage for
`_classify` while the real inner function is never entered. Every model_dict lookup, tensor-op argument, `run_in_executor`
plumbing argument and default-prompts binding therefore survives untouched.

`load_fashion_clip_model` has a good happy-path suite (`:293-476`) — its survivors are almost entirely log/raise **text**
mutations plus two un-asserted structured-log fields and one dropped call argument.
`format_clothing_context` is well covered (22 of 32 killed); its survivors are string-literal wraps (equivalent) and the
alternative-selection sort key, which existing tests feed **score-ordered** `all_scores` to, so removing/reversing the sort is
invisible.

## Per-cluster table

| # | Cluster | N | Class | Why / what the covering test misses | Example keys |
|---|---------|---|-------|-------------------------------------|--------------|
| C1 | `classify_clothing`: `model_dict["model"/"preprocess"/"tokenizer"]` → `None`, `["XXkXX"]`, `["K"]` | 9 | TEST-GAP | Only reached via the forced-failure test; a happy path (KeyError→`RuntimeError("Clothing classification failed")`) is never taken. No test asserts the three dict keys are consumed or that a good `model_dict` succeeds. | `x_classify_clothing__mutmut_3`, `_4`, `_5` |
| C2 | `classify_clothing`: device + image-tensor pipeline args (`device=None`, `next(None)`, `.to(None)`, `unsqueeze(None/1)`, `preprocess(None)`, `image_tensor=None`) | 7 | TEST-GAP | `test_classify_clothing_runtime_error:522` deliberately breaks `preprocess` *before* these lines produce anything; nothing asserts the `.to(device)` target, the `unsqueeze(0)` axis or the image handed to `preprocess`. | `x_classify_clothing__mutmut_13`, `_16`, `_19` |
| C3 | `classify_clothing`: default-prompts binding (`if prompts is None` → `is not None`; `SECURITY_CLOTHING_PROMPTS` → `None`) | 2 | TEST-GAP | No test calls `classify_clothing` without `prompts` and inspects what the tokenizer received; both mutants only change behaviour on the un-exercised happy path. | `x_classify_clothing__mutmut_1`, `_2` |
| C4 | `classify_clothing`: executor offload plumbing (`loop=None`, `run_in_executor(None, None)`, dropped executor arg, dropped fn arg) | 4 | TEST-GAP | `test_classify_clothing_runtime_error:522` proves the `except` tail is live but nothing asserts the work was handed to an executor with `(None, _classify)`. `loop=None` survives only because no test reaches that call. | `x_classify_clothing__mutmut_12`, `_20`, `_21` |
| C5 | `classify_clothing_batch`: `model_dict[...]` → `None` / `["XXkXX"]` / `["K"]` | 9 | TEST-GAP | Batch happy path never runs: `test_batch_empty_images:683` returns before it, `test_batch_runtime_error:693` fails inside it. Rest of the class is reimplementation tests (`:714`, `:760`). | `x_classify_clothing_batch__mutmut_4`, `_5`, `_6` |
| C6 | `classify_clothing_batch`: device / tensor arg clobbers (`device=None`, `next(None)`, `.to(None)`, `preprocess(None)`) | 4 | TEST-GAP | Same as C2 for the batch loop; `torch.stack(...).to(device)` target and per-image `preprocess(img)` argument are unasserted. | `x_classify_clothing_batch__mutmut_14`, `_17`, `_19` |
| C7 | `classify_clothing_batch`: default-prompts binding (guard flip; default → `None`) | 2 | TEST-GAP | As C3; the empty-images test short-circuits above the binding. | `x_classify_clothing_batch__mutmut_2`, `_3` |
| C8 | `classify_clothing_batch`: executor offload plumbing (`loop=None`, fn→`None`, dropped args) | 4 | TEST-GAP | As C4. | `x_classify_clothing_batch__mutmut_13`, `_20`, `_21` |
| C9 | `classify_clothing` + `classify_clothing_batch`: `logger.error` **message text** (`→None`, `XX…XX`, lower/upper case), both sites | 8 | LOW-VALUE | Real change to the emitted log text, but the *user-visible* error is the separately-raised `RuntimeError` f-string, which the two tests **do** assert (`"Clothing classification failed" in str(...)`). Nobody consumes these log strings. | `x_classify_clothing__mutmut_23`, `_27`, `_28` |
| C10 | `classify_clothing` + `classify_clothing_batch`: `logger.error` **`exc_info`** dropped / `None` / `False`, both sites | 6 | TEST-GAP | Tests execute the line but never look at the log record. Dropping `exc_info=True` silently loses the traceback from the JSON log pipeline (`backend/core/logging.py` → `CustomJsonFormatter`); `exc_info=None`/`False` both yield `record.exc_info is None`, so one assertion separates them from the original. | `x_classify_clothing__mutmut_24`, `_26`, `_30` |
| C11 | `load_fashion_clip_model`: CUDA-guard `RuntimeError` **text** wrapped in `XX…XX` | 1 | LOW-VALUE | `test_load_model_success_without_cuda:330` matches `"requires a CUDA GPU"` as a *substring*, so the wrap survives. Message text only — no behaviour change. | `x_load_fashion_clip_model__mutmut_3` |
| C12 | `load_fashion_clip_model`: `get_tokenizer(hub_path)` → `get_tokenizer(None)` | 1 | TEST-GAP | `:293`/`:350`/`:408`/`:443` assert `create_model_from_pretrained.assert_called_once_with("hf-hub:Marqo/marqo-fashionSigLIP")` but **never** `get_tokenizer(...)` — the canonical hf-hub identifier is only half-pinned. (One-line fix to an existing test, see Note.) | `x_load_fashion_clip_model__mutmut_15` |
| C13 | `load_fashion_clip_model`: `logger.info` / `logger.warning` / `raise ImportError` **message text** incl. `→None` (17 sites: 6 info, 3 warning, 4 ImportError, 4 error) | 17 | LOW-VALUE | `test_load_model_import_error_torch:478` accepts `(ImportError, TypeError)` and asserts nothing about the message, and no test inspects `logger.info` args. Diagnostics only; the raise *type* is unchanged. | `x_load_fashion_clip_model__mutmut_17`, `_32`, `_35` |
| C14 | `load_fashion_clip_model`: error-site `logger.error` `exc_info` dropped / `None` / `False` | 3 | TEST-GAP | `test_load_model_runtime_error:385` asserts only the re-raised message; the traceback flag on the record is never read. | `x_load_fashion_clip_model__mutmut_40`, `_43`, `_48` |
| C15 | `load_fashion_clip_model`: error-site `extra={"model_path": model_path}` → dropped / `None` / key clobbered (`"XXmodel_pathXX"`, `"MODEL_PATH"`) | 4 | TEST-GAP | The structured field that makes loader failures diagnosable is never asserted — `caplog` records carry `model_path` directly and no test reads it. | `x_load_fashion_clip_model__mutmut_41`, `_44`, `_49` |
| C16 | `format_clothing_context`: `XX…XX` wrap of the `[ALERT: …]` / `[Service/delivery worker …]` line literals and of the `"\n"` join separator | 3 | EQUIVALENT | Substring assertions still pass; the only downstream consumer (`enrichment_pipeline.py:1150`) embeds the string in a bigger LLM prompt and its test (`test_enrichment_pipeline.py:2356`) asserts only `"Clothing Classifications"` / `"Person 1"`. Cosmetic whitespace/markers — not worth a test. | `x_format_clothing_context__mutmut_3`, `_7`, `_32` |
| C17 | `format_clothing_context`: alternative-selection clobbers — `sorted(key=None)`, `key=lambda` dropped, `reverse=None`/`reverse=False`/dropped, and inner `len(sorted_scores) > 1` → `>= 1` | 6 | TEST-GAP | `test_format_low_confidence_with_alternative:822` feeds `all_scores` **already in descending score order**, so removing or reversing the sort key changes nothing observable; the inner `>= 1` is dead because its guard (`:580`) already requires `len > 1`. Misses: out-of-order `all_scores` and a single-entry `all_scores`. | `x_format_clothing_context__mutmut_18`, `_25`, `_26` |
| C18 | `format_clothing_context`: outer guard `len(classification.all_scores) > 1` → `>= 1` (non-adjacent line, not in the span mutmut compares) | 1 | EQUIVALENT | `all_scores` is a dict, so `len == 1` implies `len(sorted_scores) == 1` and the inner guard blocks the alternative anyway. Genuinely equivalent; only `test_format_low_confidence_single_score:855` reaches it and it asserts the correct shared outcome. | `x_format_clothing_context__mutmut_14` |

**Totals:** 61 TEST-GAP · 26 LOW-VALUE · 4 EQUIVALENT = **91** (matches the meta exactly).

## Killing map

| Drafted test | Kills clusters | Mutants |
|---|---|---|
| `TestClassifyClothingHappyPath::test_classify_clothing_consumes_all_model_dict_members` (+ batch twin) | C1, C5 | 18 |
| `test_classify_clothing_pins_device_and_tensor_arguments` (+ batch twin) | C2, C6 | 11 |
| `test_classify_clothing_defaults_to_security_prompts` (+ batch twin) | C3, C7 | 4 |
| `test_classify_clothing_offloads_classify_to_default_executor` (+ batch twin) | C4, C8 | 8 |
| `TestFormatClothingContext::test_format_alternative_uses_score_sorted_runner_up` | C17 | 6 |
| `test_load_model_failure_logs_traceback_and_model_path_context` | C10, C14, C15 | 13 |
| *(C12 — one-line strengthening, see Note)* | C12 | 1 |

60 of 61 TEST-GAP mutants covered by the six drafted tests; C12 closed by one added assertion in an existing test.

## Drafted tests

All six are **UNVERIFIED — not yet run red/green** (no test execution was permitted in this triage). They are written to be
appended to `/agents/agent-nemo2/workspace/backend/tests/unit/services/test_fashion_clip_loader.py`, following that file's
conventions (`from __future__ import annotations`, class-scoped grouping, `-> None` annotations, local `import numpy as np`
inside the body, explicit `@pytest.mark.asyncio`, `patch.dict(sys.modules, {...})` for the dynamic `import torch`).

Required extra imports (module header, alongside the existing `from unittest.mock import MagicMock, patch`):

```python
import asyncio
from unittest.mock import MagicMock, call, patch
```

### Shared fixtures/helpers (module level of the test file)

```python
# =============================================================================
# Shared helpers for the classify_clothing / classify_clothing_batch happy path
# =============================================================================
# ``mutmut_survivors`` note: these helpers exist because no existing test ever lets
# classify_clothing or classify_clothing_batch run to completion, so the entire
# tensor/executor body of both functions is unexercised (WP4.4 C1-C8).


class _Scores:
    """Stand-in for the open_clip ``(...).softmax(dim=-1)`` output tensor.

    Mirrors exactly the two accesses the loader makes on it:

    * ``similarity[0].cpu().numpy()``   — single-image path (classify_clothing)
    * ``similarity.cpu().numpy()``      — batch path, ``[num_images, num_prompts]``
    """

    def __init__(self, rows: object) -> None:
        import numpy as np

        self._rows = np.atleast_2d(np.asarray(rows, dtype=float))

    def __getitem__(self, index: int) -> "_Row":
        return _Row(self._rows[index])

    def cpu(self) -> "_Scores":
        return self

    def numpy(self) -> object:
        return self._rows


class _Row:
    """One row of the softmax output — ``.cpu().numpy()`` yields a 1-D array."""

    def __init__(self, vec: object) -> None:
        import numpy as np

        self._vec = np.asarray(vec, dtype=float)

    def cpu(self) -> "_Row":
        return self

    def numpy(self) -> object:
        return self._vec


def _wire_softmax(model: MagicMock, rows: object) -> None:
    """Route ``(100.0 * image_features @ text_features.T).softmax(dim=-1)`` to ``rows``."""
    model.encode_image.return_value.__matmul__.return_value.softmax.return_value = _Scores(rows)


def _model_params_on(device: str = "cpu") -> MagicMock:
    """A mock model whose ``next(model.parameters()).device`` is ``device``."""
    mock_model = MagicMock()
    mock_param = MagicMock()
    mock_param.device = device
    mock_model.parameters.return_value = iter([mock_param])
    return mock_model


def _mock_torch(*, cuda_available: bool = True) -> MagicMock:
    """A ``torch`` stand-in: inference-mode context manager + real-ish ``stack``."""
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = cuda_available
    ctx = mock_torch.inference_mode.return_value
    ctx.__enter__ = MagicMock(return_value=None)
    ctx.__exit__ = MagicMock(return_value=False)
    return mock_torch
```

### T1 — kills C1 + C5 (18 mutants): the `model_dict` contract

**TDD procedure:** on any C1/C5 mutant the lookup yields `None`/`KeyError`, the function's `except` tail re-raises
`RuntimeError("Clothing classification failed…")` (or `RuntimeError("Batch …")`), so `await classify_clothing(...)` fails the
`assert result.top_category == …` line; on the original the classification completes and every assertion passes.

```python
class TestClassifyClothingHappyPath:
    """Tests that drive classify_clothing / classify_clothing_batch to completion.

    The pre-existing error-path tests (:class:`TestClassifyClothing`,
    :class:`TestClassifyClothingBatch`) break ``preprocess`` on purpose, so the
    ``model_dict`` unpacking and the tensor pipeline were never asserted.
    """

    @pytest.mark.asyncio
    async def test_classify_clothing_consumes_all_model_dict_members(self) -> None:
        """Every model_dict member is used and a well-formed dict classifies."""
        prompts = ["person wearing dark hoodie", "delivery uniform", "casual clothing"]
        mock_model = _model_params_on("cpu")
        mock_tensor = MagicMock()
        mock_tensor.unsqueeze.return_value = mock_tensor
        mock_tensor.to.return_value = mock_tensor
        mock_preprocess = MagicMock(return_value=mock_tensor)
        mock_tokenizer = MagicMock(return_value=MagicMock(**{"to.return_value": MagicMock()}))
        _wire_softmax(mock_model, [0.92, 0.05, 0.03])

        model_dict = {
            "model": mock_model,
            "preprocess": mock_preprocess,
            "tokenizer": mock_tokenizer,
        }

        with patch.dict(sys.modules, {"torch": _mock_torch()}):
            result = await classify_clothing(model_dict, MagicMock(), prompts=prompts)

        assert result.top_category == "person wearing dark hoodie"
        assert result.is_suspicious is True
        assert result.is_service_uniform is False
        # The tokenizer must have been driven by the model_dict["tokenizer"] member.
        mock_tokenizer.assert_called_once_with(prompts)
        mock_model.encode_image.assert_called_once()
        mock_model.encode_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_classify_clothing_batch_consumes_all_model_dict_members(self) -> None:
        """Batch path uses all three model_dict members and returns one result per image."""
        prompts = ["person wearing dark hoodie", "delivery uniform", "casual clothing"]
        mock_model = _model_params_on("cpu")
        mock_preprocess = MagicMock(return_value=MagicMock())
        mock_tokenizer = MagicMock(return_value=MagicMock(**{"to.return_value": MagicMock()}))
        _wire_softmax(
            mock_model,
            [
                [0.92, 0.05, 0.03],  # image 1: suspicious
                [0.05, 0.88, 0.07],  # image 2: service
            ],
        )

        model_dict = {
            "model": mock_model,
            "preprocess": mock_preprocess,
            "tokenizer": mock_tokenizer,
        }

        with patch.dict(sys.modules, {"torch": _mock_torch()}):
            results = await classify_clothing_batch(
                model_dict, [MagicMock(), MagicMock()], prompts=prompts
            )

        assert [r.top_category for r in results] == [
            "person wearing dark hoodie",
            "delivery uniform",
        ]
        assert results[0].is_suspicious is True
        assert results[1].is_service_uniform is True
        mock_tokenizer.assert_called_once_with(prompts)
```

### T2 — kills C2 + C6 (11 mutants): device + tensor argument pinning

**TDD procedure:** each mutant perturbs exactly one argument (`device`, the `unsqueeze` axis, the `.to()` target, the
`preprocess` argument, or the whole tensor), so the matching `assert_called_once_with(...)` fails red; on the original every
call carries the pinned argument and the test is green.

```python
    @pytest.mark.asyncio
    async def test_classify_clothing_pins_device_and_tensor_arguments(self) -> None:
        """The crop is preprocessed, unsqueezed on axis 0 and moved to the model's device."""
        prompts = ["person wearing dark hoodie", "casual clothing"]
        mock_model = _model_params_on("cpu")
        mock_tensor = MagicMock()
        mock_tensor.unsqueeze.return_value = mock_tensor
        mock_tensor.to.return_value = mock_tensor
        mock_preprocess = MagicMock(return_value=mock_tensor)
        mock_tokenizer = MagicMock(return_value=MagicMock(**{"to.return_value": MagicMock()}))
        _wire_softmax(mock_model, [0.9, 0.1])
        image = MagicMock()

        model_dict = {
            "model": mock_model,
            "preprocess": mock_preprocess,
            "tokenizer": mock_tokenizer,
        }

        with patch.dict(sys.modules, {"torch": _mock_torch()}):
            await classify_clothing(model_dict, image, prompts=prompts)

        mock_preprocess.assert_called_once_with(image)
        mock_tensor.unsqueeze.assert_called_once_with(0)
        mock_tensor.to.assert_called_once_with("cpu")
        # The device-moved tensor, not the raw image, is what reaches the encoder.
        mock_model.encode_image.assert_called_once_with(mock_tensor)
        mock_tokenizer.return_value.to.assert_called_once_with("cpu")

    @pytest.mark.asyncio
    async def test_classify_clothing_batch_pins_device_and_tensor_arguments(self) -> None:
        """Every image is preprocessed individually and the stack is moved to the device."""
        prompts = ["person wearing dark hoodie", "casual clothing"]
        mock_model = _model_params_on("cpu")
        per_image = MagicMock()
        mock_preprocess = MagicMock(return_value=per_image)
        mock_tokenizer = MagicMock(return_value=MagicMock(**{"to.return_value": MagicMock()}))
        _wire_softmax(mock_model, [[0.9, 0.1], [0.2, 0.8]])
        images = [MagicMock(), MagicMock()]

        model_dict = {
            "model": mock_model,
            "preprocess": mock_preprocess,
            "tokenizer": mock_tokenizer,
        }
        mock_torch = _mock_torch()

        with patch.dict(sys.modules, {"torch": mock_torch}):
            await classify_clothing_batch(model_dict, images, prompts=prompts)

        mock_preprocess.assert_has_calls([call(images[0]), call(images[1])])
        assert mock_preprocess.call_count == 2
        mock_torch.stack.assert_called_once_with([per_image, per_image])
        mock_torch.stack.return_value.to.assert_called_once_with("cpu")
        mock_tokenizer.return_value.to.assert_called_once_with("cpu")
```

### T3 — kills C3 + C7 (4 mutants): default prompts

**TDD procedure:** with the guard flipped (`is not None`) or the default replaced by `None`, the tokenizer receives something
other than `SECURITY_CLOTHING_PROMPTS` (or the function raises `ValueError`→`RuntimeError` because `zip(..., strict=True)`
sees a length mismatch) — the assertion fails red; on the original the default list is forwarded verbatim.

```python
    @pytest.mark.asyncio
    async def test_classify_clothing_defaults_to_security_prompts(self) -> None:
        """Omitting ``prompts`` falls back to SECURITY_CLOTHING_PROMPTS."""
        import numpy as np

        mock_model = _model_params_on("cpu")
        mock_tensor = MagicMock()
        mock_tensor.unsqueeze.return_value = mock_tensor
        mock_tensor.to.return_value = mock_tensor
        mock_preprocess = MagicMock(return_value=mock_tensor)
        mock_tokenizer = MagicMock(return_value=MagicMock(**{"to.return_value": MagicMock()}))
        probs = np.full(len(SECURITY_CLOTHING_PROMPTS), 0.01)
        probs[0] = 0.9
        _wire_softmax(mock_model, probs)

        model_dict = {
            "model": mock_model,
            "preprocess": mock_preprocess,
            "tokenizer": mock_tokenizer,
        }

        with patch.dict(sys.modules, {"torch": _mock_torch()}):
            result = await classify_clothing(model_dict, MagicMock())

        mock_tokenizer.assert_called_once_with(SECURITY_CLOTHING_PROMPTS)
        assert result.top_category == SECURITY_CLOTHING_PROMPTS[0]

    @pytest.mark.asyncio
    async def test_classify_clothing_batch_defaults_to_security_prompts(self) -> None:
        """Batch classification falls back to SECURITY_CLOTHING_PROMPTS too."""
        import numpy as np

        mock_model = _model_params_on("cpu")
        mock_preprocess = MagicMock(return_value=MagicMock())
        mock_tokenizer = MagicMock(return_value=MagicMock(**{"to.return_value": MagicMock()}))
        probs = np.full((1, len(SECURITY_CLOTHING_PROMPTS)), 0.01)
        probs[0][1] = 0.9
        _wire_softmax(mock_model, probs)

        model_dict = {
            "model": mock_model,
            "preprocess": mock_preprocess,
            "tokenizer": mock_tokenizer,
        }

        with patch.dict(sys.modules, {"torch": _mock_torch()}):
            results = await classify_clothing_batch(model_dict, [MagicMock()])

        mock_tokenizer.assert_called_once_with(SECURITY_CLOTHING_PROMPTS)
        assert results[0].top_category == SECURITY_CLOTHING_PROMPTS[1]
```

### T4 — kills C4 + C8 (8 mutants): executor offload

**TDD procedure:** `run_in_executor` is patched, so the real `_classify` never runs and the test inspects the *await*. Under
`loop=None` / dropped-fn mutants the await never happens (`AttributeError`/`TypeError` → `RuntimeError`, killing the
`await_count == 1` assertion); under `fn → None` the recorded arg is `None`, so `assert fn is not None` fails; under
`run_in_executor(_classify)` (dropped executor) `assert_awaited_once_with(None, ANY)` fails. On the original the recorded
callable runs and returns the expected classification.

```python
```python
    @pytest.mark.asyncio
    async def test_classify_clothing_offloads_classify_to_default_executor(self) -> None:
        """Classification is handed to the default executor, not run on the event loop."""
        prompts = ["person wearing dark hoodie", "casual clothing"]
        mock_model = _model_params_on("cpu")
        mock_tensor = MagicMock()
        mock_tensor.unsqueeze.return_value = mock_tensor
        mock_tensor.to.return_value = mock_tensor
        model_dict = {
            "model": mock_model,
            "preprocess": MagicMock(return_value=mock_tensor),
            "tokenizer": MagicMock(return_value=MagicMock(**{"to.return_value": MagicMock()})),
        }
        _wire_softmax(mock_model, [0.9, 0.1])
        seen: list[tuple[object, object]] = []

        async def _fake_run_in_executor(executor: object, fn: object, *args: object) -> object:
            """Stand-in for ``loop.run_in_executor`` that runs the work inline."""
            seen.append((executor, fn))
            return fn(*args)

        fake_loop = MagicMock()
        fake_loop.run_in_executor.side_effect = _fake_run_in_executor

        with (
            patch.dict(sys.modules, {"torch": _mock_torch()}),
            patch.object(asyncio, "get_running_loop", return_value=fake_loop),
        ):
            result = await classify_clothing(model_dict, MagicMock(), prompts=prompts)

        assert len(seen) == 1
        executor, work = seen[0]
        assert executor is None
        assert work is not None
        assert result.top_category == "person wearing dark hoodie"

    @pytest.mark.asyncio
    async def test_classify_clothing_batch_offloads_classify_to_default_executor(self) -> None:
        """Batch classification is offloaded the same way."""
        prompts = ["person wearing dark hoodie", "casual clothing"]
        mock_model = _model_params_on("cpu")
        model_dict = {
            "model": mock_model,
            "preprocess": MagicMock(return_value=MagicMock()),
            "tokenizer": MagicMock(return_value=MagicMock(**{"to.return_value": MagicMock()})),
        }
        _wire_softmax(mock_model, [[0.9, 0.1]])
        seen: list[tuple[object, object]] = []

        async def _fake_run_in_executor(executor: object, fn: object, *args: object) -> object:
            seen.append((executor, fn))
            return fn(*args)

        fake_loop = MagicMock()
        fake_loop.run_in_executor.side_effect = _fake_run_in_executor

        with (
            patch.dict(sys.modules, {"torch": _mock_torch()}),
            patch.object(asyncio, "get_running_loop", return_value=fake_loop),
        ):
            results = await classify_clothing_batch(model_dict, [MagicMock()], prompts=prompts)

        assert len(seen) == 1
        executor, work = seen[0]
        assert executor is None
        assert work is not None
        assert results[0].top_category == "person wearing dark hoodie"
```

> **Red/green note (per-mutant kill path):** `loop = None` → `None.run_in_executor` `AttributeError` → `RuntimeError`, so
> `result` is never assigned (red). `run_in_executor(None, None)` / `run_in_executor(None,)` / `run_in_executor(_classify)` →
> `TypeError` inside the fake (`None(...)` or a missing positional) → `RuntimeError` (red). The original runs the real
> `_classify` through the fake and asserts the completed classification (green).

### T5 — kills C17 (6 mutants): alternative selection ordering

**TDD procedure:** `all_scores` is inserted with the highest score **first** and a *third* entry so the runner-up is not
reversal-invariant. Dropping the sort key (or `key=None`) sorts the `(prompt, score)` tuples and picks `yankee` (10.0%);
dropping/`None`-ing `reverse` sorts ascending and also picks `yankee`; the single-entry case makes the inner
`len(sorted_scores) > 1` guard's `>= 1` mutant raise `IndexError`. All red; on the original the second-highest **score** is
named. (A 3-entry dict is *not* enough: the middle element of a 3-element list is unchanged by reversal, and with prompt names
in score order the tuple-sort also lands there — hence 4 entries and deliberately non-score-ordered names.)

```python
class TestFormatClothingContextOrdering:
    """Ordering of the low-confidence alternative line (WP4.4 C17)."""

    def test_format_alternative_uses_score_sorted_runner_up(self) -> None:
        """The alternative is the 2nd-highest SCORE, not the 2nd dict entry or 2nd name."""
        classification = ClothingClassification(
            top_category="alpha",
            confidence=0.35,
            all_scores={
                "alpha": 0.35,  # inserted first AND highest — the existing tests' blind spot
                "mike": 0.30,  # the true runner-up by score
                "yankee": 0.10,
                "zulu": 0.05,
            },
            raw_description="Alpha",
        )
        result = format_clothing_context(classification)

        assert "Alternative: mike (30.0%)" in result
        assert "yankee" not in result

    def test_format_no_alternative_when_only_one_score(self) -> None:
        """A single-entry all_scores must not produce an alternative (and must not crash)."""
        classification = ClothingClassification(
            top_category="alpha",
            confidence=0.35,
            all_scores={"alpha": 0.35},
            raw_description="Alpha",
        )
        result = format_clothing_context(classification)

        assert "Alternative:" not in result
```

### T6 — kills C10 + C14 + C15 (13 mutants): error-path log record

**TDD procedure:** `caplog` reads the emitted `LogRecord`. `exc_info=True` lands as a `(type, exc, tb)` tuple, while the
`None`/`False`/dropped mutants leave `record.exc_info is None`, so `assert record.exc_info is not None` fails red; the
`extra={"model_path": ...}` mutants (dropped / `None` / key-clobbered) remove or rename the attribute, so `getattr(record,
"model_path")` raises. On the original both assertions pass.

```python
class TestErrorPathLogging:
    """The loader/classifier error paths must keep traceback + structured context (C10/C14/C15)."""

    @pytest.mark.asyncio
    async def test_load_model_failure_logs_traceback_and_model_path_context(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Load failures are logged with the exception traceback and model_path field."""
        import logging

        mock_torch = _mock_torch()
        mock_open_clip = MagicMock()
        mock_open_clip.create_model_from_pretrained.side_effect = OSError("Model not found at path")

        with (
            caplog.at_level(logging.ERROR, logger="backend.services.fashion_clip_loader"),
            patch.dict(
                sys.modules,
                {
                    "torch": mock_torch,
                    "torch.nn": MagicMock(),
                    "torch.nn.functional": MagicMock(),
                    "open_clip": mock_open_clip,
                },
            ),
        ):
            with pytest.raises(RuntimeError, match="Failed to load FashionSigLIP model"):
                await load_fashion_clip_model("/invalid/path")

        records = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert records, "expected an ERROR log record for the load failure"
        record = records[0]
        assert "Failed to load FashionSigLIP model" in record.getMessage()
        # exc_info=True -> tuple; None/False/dropped -> None (traceback lost from JSON logs).
        assert record.exc_info is not None
        assert getattr(record, "model_path") == "/invalid/path"

    @pytest.mark.asyncio
    async def test_classify_failures_log_traceback(self, caplog: pytest.LogCaptureFixture) -> None:
        """Single and batch classification failures keep the exception traceback."""
        import logging

        for fn, expected in (
            (classify_clothing, "Clothing classification failed"),
            (classify_clothing_batch, "Batch clothing classification failed"),
        ):
            caplog.clear()
            mock_model = _model_params_on("cpu")
            mock_preprocess = MagicMock(side_effect=ValueError("Processing failed"))
            model_dict = {
                "model": mock_model,
                "preprocess": mock_preprocess,
                "tokenizer": MagicMock(),
            }
            images = MagicMock() if fn is classify_clothing else [MagicMock()]

            with (
                caplog.at_level(logging.ERROR, logger="backend.services.fashion_clip_loader"),
                patch.dict(sys.modules, {"torch": _mock_torch()}),
            ):
                with pytest.raises(RuntimeError, match=expected):
                    await fn(model_dict, images)

            records = [r for r in caplog.records if r.levelno >= logging.ERROR]
            assert records, f"expected an ERROR log record from {expected}"
            assert expected in records[0].getMessage()
            assert records[0].exc_info is not None
```

## Covering test files (file:line)

| File | Relevant lines | What it does / misses |
|---|---|---|
| `/agents/agent-nemo2/workspace/backend/tests/unit/services/test_fashion_clip_loader.py` | `:513` `TestClassifyClothing` · `:522` `test_classify_clothing_runtime_error` | Sole live caller of `classify_clothing`; breaks `preprocess` on purpose, asserts only the `RuntimeError` text. Misses C1-C4. |
| ″ | `:543`, `:574`, `:599`, `:615`, `:630`, `:647` | **Reimplementation** tests: sort/flag/description/top-k logic copied into the test body. Assert nothing about the real `_classify`. |
| ″ | `:674` `TestClassifyClothingBatch` · `:683` `test_batch_empty_images` · `:693` `test_batch_runtime_error` | Empty-list test returns before the body; error test breaks `preprocess`. Misses C5-C8. `:714`/`:760` are reimplementations. |
| ″ | `:779` `TestFormatClothingContext` · `:822` `test_format_low_confidence_with_alternative` · `:855` `test_format_low_confidence_single_score` | Feeds already score-ordered `all_scores`, so C17's sort/reverse/`>= 1` mutants are invisible; `:855` uses `confidence=0.35` with a 1-entry dict but never distinguishes which guard fired. |
| ″ | `:289` `TestLoadFashionClipModel` · `:293` success+CUDA · `:330` CPU guard · `:350`/`:408`/`:443` hf-hub path · `:385` `test_load_model_runtime_error` · `:478` `test_load_model_import_error_torch` | Good happy-path coverage (why 25 of 51 load mutants died), but never asserts `get_tokenizer(...)` args (C12), nor `record.exc_info` / `record.model_path` (C14/C15), nor the log/raise texts (C11/C13 — LOW-VALUE). |
| `/agents/agent-nemo2/workspace/backend/tests/unit/services/test_enrichment_pipeline.py` | `:2356` `test_to_context_string_with_clothing_classifications` | Downstream consumer of `format_clothing_context` output (`enrichment_pipeline.py:1150`); asserts only `"Clothing Classifications"` / `"Person 1"`, so C16's string wraps pass through unnoticed. |

## Note — one-line strengthening instead of a drafted test (C12)

Add to the existing `test_load_model_success_with_cuda` (`test_fashion_clip_loader.py:293`, and equally to `:350` / `:408`):

```python
            mock_open_clip.get_tokenizer.assert_called_once_with("hf-hub:Marqo/marqo-fashionSigLIP")
```

This kills `x_load_fashion_clip_model__mutmut_15` (`tokenizer = get_tokenizer(None)`) and pins the canonical hf-hub identifier
on both open_clip entry points instead of only `create_model_from_pretrained`.

## Triage judgements worth carrying to WP4.4

1. **Reimplementation tests are the single biggest generator of survivors in this module** (`:543`-`:772`, ~140 lines). They
   look like unit coverage of `_classify`, keep `tests_by_mangled_function_name` populated, and assert zero production code.
   T1-T4 replace them with real end-to-end-of-function assertions.
2. `classify_clothing` / `classify_clothing_batch` had **exactly one** covering test each in `mutmut-stats.json` — a module whose
   happy path is untested still reports "covered", so coverage-by-test-name is a weak signal for WP4.3 baselines.
3. Mocking open_clip's arithmetic chain is cheap: `(100.0 * a @ b.T).softmax(dim=-1)` can be intercepted by configuring
   `a.__matmul__.return_value.softmax.return_value`, no real torch tensors needed. That unlocks the same pattern for the other
   SigLIP-style loaders (`xclip_loader` already does a variant of it with `spec=[...]` mocks).
