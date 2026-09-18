# Triage dossier — backend/services/violence_loader.py (WP4.3 survivors, gen-2)

- Source: `backend/services/violence_loader.py` (284 lines). Mutant copy: `mutants/backend/services/violence_loader.py`.
- Verdict source: `mutants/backend/services/violence_loader.py.meta` — 178 mutants, 103 killed, **75 survived**, 0 unchecked.
- Diff extraction: `uv run mutmut show <key>` for all 75 (75/75, no fallback needed).
- Covering tests (mutmut-stats `tests_by_mangled_function_name`): `x_load_violence_model` and `x_classify_violence` are covered exclusively by **`backend/tests/unit/services/test_violence_loader.py`** (the only file that matters here; `test_enrichment_pipeline.py` touches only `ViolenceDetectionResult.to_dict`, which has no survivors).

## Headline

Every mock in the covering test file is **argument-blind**: `MagicMock()` collaborators (transformers loaders, the image processor, `torch.nn.functional.softmax`) are configured with `return_value`/lambda results that fire **regardless of the arguments the source passes**, and every `id2label` fixture map is chosen so the hard-coded default indices (violent=1, non-violent=0) already equal what correct label-matching would resolve. Result: 41/75 survivors are real production behavior changes — the loader args, meta-tensor guard, softmax/logits args, label→index resolution, confidence source, and the 10 s timeout are all executed and never pinned. The remaining 34 are pure log-message / exc_info / extra= / raise-message-text mutants.

Two structural gaps in the existing battery that explain most TEST-GAP mass:

1. **`test_violence_loader.py:457-458` etc.**: `mock_probs.__getitem__ = lambda _self, _idx: MagicMock(cpu=...tolist [x,y])` — index-blind, so `probs[0]→probs[1]` and softmax-arg mutants cannot be seen.
2. **`TestClassifyViolenceMocked` (:442-702) + `TestClassifyViolenceConfidenceTiers` (:961-1107)**: every id2label map puts violent at the default index 1; `confidence` is never asserted on a classify-returned result (only on directly-constructed dataclasses); processor/softmax call-args never asserted; no classify test uses violent_score exactly 0.55 (dataclass-level boundary tests at :889 construct directly); no timeout test exists anywhere.

## Cluster table (counts sum to 75)

| # | cluster (pattern @ concern) | n | class | example keys | note |
|---|------------------------------|---|-------|--------------|------|
| 1 | C-MATCHN: non-violent `elif` label-match clobbered (`or`→`and`, `non`→`XX`/`NON`, `not in` flip, `safe`→`XX`/`SAFE`) | 7 | TEST-GAP | x_classify_violence__mutmut_50, _53, _56 | Survives because every test map puts the non-violent class at index 0 = the fallback default. Wrong resolution silently swaps score halves on a model whose labels differ. |
| 2 | C-MATCHV: violent-branch `if` label-match clobbered (`label.lower()`→`upper()`, `and`→`or`, `"violent"`→`XX`/`VIOLENT`, `"non"`→`XX`/`NON`) | 6 | TEST-GAP | x_classify_violence__mutmut_40, _41, _43 | Same fixture blind spot: match never-fires == defaults == expected in all tests. `upper()` + uppercase constants never match the lower-cased label. |
| 3 | C-PROCARGS: `processor(images=image, return_tensors="pt")` call args clobbered (images→None/removed, rt→None/removed/`XXptXX`/`PT`) | 6 | TEST-GAP | x_classify_violence__mutmut_9, _10, _13 | `mock_processor.return_value` fires for any args. `return_tensors=None`/`PT` would return dicts of lists / raise in prod; call args never asserted. |
| 4 | C-ID2RES: id2label lookup always yields None (whole expr→None, `and False`, `hasattr(None,…)`, attr→`XXid2labelXX`/`ID2LABEL`) | 5 | TEST-GAP | x_classify_violence__mutmut_26, _27, _33 | Forces fallback indices 1/0; indistinguishable from correct in test maps. A model saved as {0:"violent",1:"safe"} gets its scores swapped in prod. |
| 5 | C-CONF: confidence ternary/field clobbered (`→None`, `and False`, `or True`, kwarg `confidence=None`) | 4 | TEST-GAP | x_classify_violence__mutmut_89, _90, _91 | Classify tests assert score/tier but never `result.confidence`; `or True`/`and False` pick the wrong half whenever is_violent disagrees with the winner. |
| 6 | C-SOFTMAXSRC: inference source → None (`logits = None`, `softmax(None, …)`) | 2 | TEST-GAP | x_classify_violence__mutmut_18, _20 | Prod: TypeError → RuntimeError. Mock: `mock_torch.nn.functional.softmax.return_value` fires for `None` args. |
| 7 | C-SOFTMAXDIM-N2: `softmax(…, dim=-2)` | 1 | TEST-GAP | x_classify_violence__mutmut_25 | For real [1,2] logits, dim=-2 normalizes over size-1 axis → every prob becomes 1.0. Index-blind/arg-blind mocks never see it. |
| 8 | C-ROW: batch-row flip `probs[0]`→`probs[1]` | 1 | TEST-GAP | x_classify_violence__mutmut_60 | Prod [1,N] → IndexError→RuntimeError (or wrong row at batch>1); mock `__getitem__` lambda is index-blind. |
| 9 | C-B55: suspected-tier boundary `>= 0.55`→`> 0.55` | 1 | TEST-GAP | x_classify_violence__mutmut_77 | violent_score exactly 0.55: suspected (review-flagged) vs marginal (silently excluded). Existing classify tests use 0.52/0.62/0.80; the 0.55 dataclass boundary test (:889) constructs the result directly, bypassing the threshold. |
| 10 | C-TIMEOUT: `asyncio.wait_for(timeout=10.0)`→None / 11.0 | 2 | TEST-GAP | x_classify_violence__mutmut_103, _109 | The 10 s hard timeout is the documented contract (comment at :261-263: frees event loop for health checks). No test exercises or pins it; `None` re-opens the GIL-starvation failure mode the guard exists for. |
| 11 | L-FROMPRETRAINED: HF loader call clobbered (`processor=None`, `from_pretrained(None)` for processor and model) | 3 | TEST-GAP | x_load_violence_model__mutmut_9, _10, _12 | `test_load_violence_model_cuda_path` (:347-378) asserts keys `"model"/"processor"` in result + cuda/eval calls, but **not** `from_pretrained` called with `model_path` nor result identity — mock accepts `None` arg, and `result["processor"] is mock_processor` is never asserted. |
| 12 | L-META: meta-tensor guard predicate clobbered (`==`→`!=`, `"meta"`→`"XXmetaXX"`/`"META"`) | 3 | TEST-GAP | x_load_violence_model__mutmut_14, _15, _16 | The whole to_empty()+load_state_dict(assign=True) materialization branch (:126-133) has zero coverage: cuda-path test leaves `mock_model.parameters()` unconfigured, so `any(...)` iterates MagicMock's default **empty** iterator — branch never entered either way. `!=`/case variants would crash real meta-tensor loads with `NotImplementedError: Cannot copy out of meta tensor`. |
| 13 | L-RAISEMSG: raise-message text clobbered (CUDA-guard, ImportError guidance) | 3 | LOW-VALUE | x_load_violence_model__mutmut_3, _36, _37 | `XX`-wrapped/UPPER text still satisfies the `match="requires CUDA"` / `match="transformers"` regexes tests use; full raise-text identity is cosmetic for operators. |
| 14 | L-EXCINFO: `logger.error(exc_info=True)`→None/removed/False (load error handler) | 3 | LOW-VALUE | x_load_violence_model__mutmut_39, _42, _47 | Traceback capture in logs only. |
| 15 | C-ERREXC: `logger.error(exc_info=True)`→None/removed/False (classify failure handler) | 3 | LOW-VALUE | x_classify_violence__mutmut_111, _113, _117 | Same; the adjacent `raise RuntimeError("Violence classification failed: {e}")` is asserted (:168) and untouched. |
| 16 | L-EXTRA: `extra={"model_path": …}` →None/removed/key-`XX`/`MODEL_PATH` | 4 | LOW-VALUE | x_load_violence_model__mutmut_40, _43, _48 | Structured-log metadata only; raise path unchanged. |
| 17 | L-LOGTEXT: logger.info/warning/error message args →None/`XX`/case swaps (7 log sites) | 14 | EQUIVALENT | x_load_violence_model__mutmut_6, _19, _31 | `logger.info(None)` / case-variants format fine; control flow + return values identical. Includes error-handler msg arg (#38,#44,#45,#46) — the asserted RuntimeError text is a separate f-string. |
| 18 | C-ERRMSG: classify failure-log message arg →None/`XX`/case | 4 | EQUIVALENT | x_classify_violence__mutmut_110, _114, _116 | Log text only. |
| 19 | C-SOFTMAXDIM-EQV: `softmax` dim→None/removed/+1 | 3 | EQUIVALENT | x_classify_violence__mutmut_21, _23, _24 | For the deployed single-image [1,N] logits shape, dim=None/+1/-1 normalize the identical element set → same probabilities. (The drafted softmax-arg pin in T4 would incidentally kill these, but they are not runtime-reachable defects.) |

**Totals: 41 TEST-GAP / 13 LOW-VALUE / 21 EQUIVALENT = 75**

## Key file:line anchors (test_violence_loader.py)

- CUDA-guard raise asserted only via `match="requires CUDA"`: :88-89, :343-344
- `test_load_violence_model_cuda_path` asserts dict keys + `cuda()`/`eval()` but not loader args nor processor identity: :347-378 (`mock_model.parameters` left unconfigured → meta guard dead: :359-360)
- classify error test asserts the **raise** text `"Violence classification failed"` (:168) — log-line mutants in the same handler are independent of it: :154-168
- `TestClassifyViolenceMocked` :442-702 — asserts is_violent/scores only; `confidence` never; processor/softmax call-args never; index-blind `__getitem__` lambdas at :457-459, :508-510, :562-564, :613-615, :663-666
- all id2label fixtures put violent at default idx 1: :472, :523, :577, :680, :995 — match-failure indistinguishable from match-success
- tier classify scores used: 0.8 / 0.62 / 0.52 — no 0.55 boundary through classify: :961-1107
- dataclass-level boundary tests (construct `ViolenceDetectionResult` directly, bypass thresholds): :857-919
- **no test anywhere exercises the 10 s wait_for timeout**

## Drafted kill-tests

All "// UNVERIFIED - not yet run red/green". Style mirrors `TestClassifyViolenceMocked` (monkeypatch `sys.modules["torch"]`, MagicMock collaborators). TDD procedure for every one: apply the cluster's mutant diff → new assert FAILS (red); revert to original source → PASSES (green).

### T1 — `test_inverted_id2label_resolves_indices` → kills clusters 2+4+1 (18 survivors)

New class appended to `backend/tests/unit/services/test_violence_loader.py`. Two inverted label maps; the pair kills all 18 mutants (individually verified against each diff: e.g. `elif "non" not in …` (#53) is killed only by map `{0:"violent",1:"non-violent"}` — nvi falls back to 0 → swapped scores; `"safe"`-clobbers (#54-56) only by map `{0:"violent",1:"safe"}`).

```python
class TestClassifyViolenceLabelIndexMapping:
    """Label→index resolution must actually depend on id2label content.

    Every existing id2label fixture maps violent onto the fallback default
    index (1), so mutants that make the matching loop never fire are
    indistinguishable. Inverted maps leave correct matching as the ONLY way
    to produce the expected scores.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "id2label",
        [
            {0: "violent", 1: "non-violent"},
            {0: "violent", 1: "safe"},
        ],
    )
    async def test_inverted_id2label_resolves_indices(
        self, monkeypatch, id2label: dict[int, str]
    ) -> None:
        import sys

        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock()
        mock_torch.no_grad.return_value.__exit__ = MagicMock()

        mock_probs = MagicMock()
        mock_probs.__getitem__ = lambda _self, _idx: MagicMock(
            cpu=lambda: MagicMock(tolist=lambda: [0.8, 0.2])  # violent row is index 0
        )
        mock_torch.nn.functional.softmax.return_value = mock_probs

        monkeypatch.setitem(sys.modules, "torch", mock_torch)

        mock_param = MagicMock()
        mock_param.is_cuda = False

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([mock_param])

        mock_config = MagicMock()
        mock_config.id2label = id2label
        mock_model.config = mock_config

        mock_outputs = MagicMock()
        mock_outputs.logits = MagicMock()
        mock_model.return_value = mock_outputs

        mock_processor = MagicMock()
        mock_processor.return_value = {"pixel_values": MagicMock()}

        result = await classify_violence(
            {"model": mock_model, "processor": mock_processor}, MagicMock()
        )

        assert result.violent_score == 0.8
        assert result.non_violent_score == 0.2
        assert result.is_violent is True
        assert result.confidence_tier == "definitive"
```

### T2 — `test_classify_violence_confidence_is_winning_score` → kills cluster 5 (4 survivors)

Case 1 kills #89/#93 (None) and #90 (`and False` → 0.2 ≠ 0.8); case 2 kills #91 (`or True` → violent_score 0.1 ≠ 0.9).

```python
class TestClassifyViolenceConfidenceSource:
    """confidence must reflect the WINNING score (NEM-5483 contract)."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "probs,expected_confidence",
        [([0.2, 0.8], 0.8), ([0.9, 0.1], 0.9)],
    )
    async def test_classify_violence_confidence_is_winning_score(
        self, monkeypatch, probs: list[float], expected_confidence: float
    ) -> None:
        import sys

        mock_torch = MagicMock()
        mock_probs = MagicMock()
        mock_probs.__getitem__ = lambda _self, _idx: MagicMock(
            cpu=lambda: MagicMock(tolist=lambda: probs)
        )
        mock_torch.nn.functional.softmax.return_value = mock_probs
        monkeypatch.setitem(sys.modules, "torch", mock_torch)

        mock_param = MagicMock()
        mock_param.is_cuda = False

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([mock_param])

        mock_config = MagicMock()
        mock_config.id2label = {0: "non-violent", 1: "violent"}
        mock_model.config = mock_config

        mock_outputs = MagicMock()
        mock_outputs.logits = MagicMock()
        mock_model.return_value = mock_outputs

        mock_processor = MagicMock()
        mock_processor.return_value = {"pixel_values": MagicMock()}

        result = await classify_violence(
            {"model": mock_model, "processor": mock_processor}, MagicMock()
        )

        assert result.confidence == expected_confidence
```

### T3 — `test_classify_violence_processor_call_arguments` → kills cluster 3 (6 survivors)

```python
    @pytest.mark.asyncio
    async def test_classify_violence_processor_call_arguments(self, monkeypatch) -> None:
        """Processor must be invoked with the actual image and pt tensors (prod
        contract: return_tensors=None returns lists, 'PT' raises Unknown tensor type)."""
        import sys

        mock_torch = MagicMock()
        mock_probs = MagicMock()
        mock_probs.__getitem__ = lambda _self, _idx: MagicMock(
            cpu=lambda: MagicMock(tolist=lambda: [0.2, 0.8])
        )
        mock_torch.nn.functional.softmax.return_value = mock_probs
        monkeypatch.setitem(sys.modules, "torch", mock_torch)

        mock_param = MagicMock()
        mock_param.is_cuda = False

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([mock_param])

        mock_config = MagicMock()
        mock_config.id2label = {0: "non-violent", 1: "violent"}
        mock_model.config = mock_config

        mock_outputs = MagicMock()
        mock_outputs.logits = MagicMock()
        mock_model.return_value = mock_outputs

        mock_processor = MagicMock()
        mock_processor.return_value = {"pixel_values": MagicMock()}
        mock_image = MagicMock()

        await classify_violence({"model": mock_model, "processor": mock_processor}, mock_image)

        mock_processor.assert_called_once_with(images=mock_image, return_tensors="pt")
```

### T4 — `test_classify_violence_softmax_receives_logits_dim_minus_one` → kills clusters 6+7 (3 survivors; incidentally 19)

```python
    @pytest.mark.asyncio
    async def test_softmax_receives_model_logits_dim_minus_one(self, monkeypatch) -> None:
        """softmax must be called on the model's own logits over the class axis."""
        import sys

        mock_torch = MagicMock()
        mock_probs = MagicMock()
        mock_probs.__getitem__ = lambda _self, _idx: MagicMock(
            cpu=lambda: MagicMock(tolist=lambda: [0.2, 0.8])
        )
        mock_torch.nn.functional.softmax.return_value = mock_probs
        monkeypatch.setitem(sys.modules, "torch", mock_torch)

        mock_param = MagicMock()
        mock_param.is_cuda = False

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([mock_param])

        mock_config = MagicMock()
        mock_config.id2label = {0: "non-violent", 1: "violent"}
        mock_model.config = mock_config

        mock_outputs = MagicMock()
        mock_outputs.logits = MagicMock()
        mock_model.return_value = mock_outputs

        mock_processor = MagicMock()
        mock_processor.return_value = {"pixel_values": MagicMock()}

        await classify_violence({"model": mock_model, "processor": mock_processor}, MagicMock())

        mock_torch.nn.functional.softmax.assert_called_once_with(mock_outputs.logits, dim=-1)
```

### T5 — `test_load_violence_model_loader_arguments` → kills cluster 11 (3 survivors)

Extends the cuda-path test's setup verbatim; adds the three missing assertions.

```python
    @pytest.mark.asyncio
    async def test_load_violence_model_loader_arguments(self, monkeypatch) -> None:
        """Both HF loaders must receive model_path and their returns must be the
        processor/model handed back (mutants that pass None or drop the processor
        are invisible to the key-presence-only assertions today)."""
        import sys

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True

        mock_cuda_model = MagicMock()
        mock_cuda_model.eval.return_value = None

        mock_model = MagicMock()
        mock_model.cuda.return_value = mock_cuda_model

        mock_processor = MagicMock()

        mock_transformers = MagicMock()
        mock_transformers.AutoImageProcessor.from_pretrained.return_value = mock_processor
        mock_transformers.AutoModelForImageClassification.from_pretrained.return_value = mock_model

        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

        result = await load_violence_model("/test/model/cuda")

        mock_transformers.AutoImageProcessor.from_pretrained.assert_called_once_with("/test/model/cuda")
        mock_transformers.AutoModelForImageClassification.from_pretrained.assert_called_once_with(
            "/test/model/cuda"
        )
        assert result["processor"] is mock_processor
        assert result["model"] is mock_cuda_model
```

### T6 — `test_classify_violence_hard_timeout_contract` → kills cluster 10 (2 survivors)

```python
    @pytest.mark.asyncio
    async def test_classify_violence_hard_timeout_contract(self, monkeypatch) -> None:
        """The executor hand-off must be wrapped in the documented 10 s hard
        timeout (None re-enables GIL starvation; 11 s drifts the contract)."""
        import asyncio
        import sys

        mock_torch = MagicMock()
        mock_probs = MagicMock()
        mock_probs.__getitem__ = lambda _self, _idx: MagicMock(
            cpu=lambda: MagicMock(tolist=lambda: [0.2, 0.8])
        )
        mock_torch.nn.functional.softmax.return_value = mock_probs
        monkeypatch.setitem(sys.modules, "torch", mock_torch)

        mock_param = MagicMock()
        mock_param.is_cuda = False

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([mock_param])

        mock_config = MagicMock()
        mock_config.id2label = {0: "non-violent", 1: "violent"}
        mock_model.config = mock_config

        mock_outputs = MagicMock()
        mock_outputs.logits = MagicMock()
        mock_model.return_value = mock_outputs

        mock_processor = MagicMock()
        mock_processor.return_value = {"pixel_values": MagicMock()}

        captured: dict = {}
        real_wait_for = asyncio.wait_for

        async def spy_wait_for(aw, *, timeout=None):
            captured["timeout"] = timeout
            return await real_wait_for(aw, timeout=timeout)

        monkeypatch.setattr(asyncio, "wait_for", spy_wait_for)

        result = await classify_violence(
            {"model": mock_model, "processor": mock_processor}, MagicMock()
        )

        assert captured["timeout"] == 10.0
        assert result.is_violent is True
```

### Not drafted (remaining TEST-GAP, one-line prescriptions)

- **Cluster 12 (L-META)**: add `test_load_violence_model_meta_tensors_materialized` to `TestLoadViolenceModelMocked` — give the mock model `parameters` returning one param with `device.type == "meta"`, assert `to_empty(device=…)` + `load_state_dict(assign=True)` called and `model.cuda` NOT called. Kills #14/#15/#16.
- **Cluster 9 (C-B55)**: parametrize the tier test at probs [0.45, 0.55] → expect `"suspected"`, `is_violent is False`. Kills #77.
- **Cluster 8 (C-ROW)**: make `mock_probs.__getitem__` index-aware (`rows = [row0, row1]`; row1 raises `IndexError` to mimic [1,N] tensors) — kills #60; adopt in the shared helper when the file is refactored.
