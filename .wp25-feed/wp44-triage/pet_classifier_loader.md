# WP4.4 Triage Dossier — backend/services/pet_classifier_loader.py

- **Module:** `backend/services/pet_classifier_loader.py`
- **Meta:** `mutants/backend/services/pet_classifier_loader.py.meta` — 155 keys, 83 killed, **72 survived (0 null/unchecked)**
- **Diffs:** all 72 collected via `uv run mutmut show <key>` (clean, no fallback needed); raw dump at `/tmp/wp25/wp44-triage/pcl_diffs.txt`
- **Covering test file:** `backend/tests/unit/services/test_pet_classifier_loader.py`
  - `test_classify_pet_success` @ L512, `test_load_pet_classifier_model_success_cuda` @ L432, `format_pet_for_nemotron` tests @ L235–306, design-check `test_pet_classification_result_label_normalization` @ L705
  - Note: `is_likely_pet_false_positive` and the `PetClassificationResult` methods are fully killed — not part of this survivor set.
- **Cluster partition machine-verified:** union of C1–C16 == exactly the 72 meta survivors, pairwise-disjoint (script check: `cluster union: 72, overlap: 72, in-meta-not-clustered: [], clustered-not-in-meta: []`).

## Structural root cause

Both GPU functions are only exercised against `MagicMock` torch/transformers (the sandbox has no GPU), so **every value that crosses the torch/transformers mock boundary flows into the result unchecked**. The success tests additionally assert weakly: `animal_type in ["cat", "cats"]` (accepts un-normalized labels), never `result.confidence / cat_score / dog_score` at all, and never the kwargs passed into `processor(...)` / `softmax(...)` / `from_pretrained(...)`. `format_pet_for_nemotron` is asserted with `in`-fragments, never exact full strings. Config objects are `MagicMock`s, which answer `hasattr` for any attribute — so guard mutants on `model.config` are invisible under the existing mock style.

## Cluster table (counts sum to 72; TEST-GAP 34, LOW-VALUE 36, EQUIVALENT 2)

| # | Pattern (function / kind) | Keys (≤3 examples) | N | Class | Kill mechanism |
|---|---|---|---|---|---|
| C1 | `classify_pet`: returned `confidence` swapped to `None` (`confidence = probs[pred_idx].item()` → None; `confidence=confidence` → `confidence=None`) | x_classify_pet__mutmut_28, x_classify_pet__mutmut_53 | 2 | TEST-GAP | Assert `result.confidence == 0.95` in success test (mocks supply it but nothing reads it) |
| C2 | `classify_pet`: `cat_score`/`dog_score` → `None` or wrong `probs[idx]` index (0↔1, 1→2) at extraction AND at result kwargs | x_classify_pet__mutmut_48, _49, _50 | 6 | TEST-GAP | Assert exact `cat_score == 0.95 and dog_score == 0.05`; score map raises on unexpected index (kills `probs[2]`) |
| C3 | `classify_pet`: `processor(images=image, return_tensors="pt")` preproc kwargs clobbered (images→None/dropped, return_tensors→None/`XXptXX`/`PT`) | x_classify_pet__mutmut_10, _11, _13 | 6 | TEST-GAP | `mock_processor.assert_called_once_with(images=test_image, return_tensors="pt")`; real torch would crash on wrong tensor type |
| C4 | `classify_pet`: `probs` row selector `[0]` → `[1]` after softmax (reads wrong batch row) | x_classify_pet__mutmut_25 | 1 | TEST-GAP | Softmax mock returns a distinct decoy probs object for index ≠ 0, then assert values |
| C5 | `classify_pet`: `logits = outputs.logits` → None; `softmax(logits, dim=-1)` args clobbered (`logits`→None/dropped, `dim` None/+1/-2) | x_classify_pet__mutmut_17, _19, _23 | 7 | TEST-GAP | `mock_torch.nn.functional.softmax.assert_called_once_with(mock_outputs.logits, dim=-1)` (dropped-arg mutants also raise TypeError → RuntimeError → uncaught in success test) |
| C6 | `classify_pet`: `hasattr(...) and model.config.id2label` → `or` | x_classify_pet__mutmut_29 | 1 | EQUIVALENT | `hasattr` is unconditionally True on a reachable config, so `and X` ≡ `or X` here |
| C7 | `classify_pet`: hasattr attr-name string mutations (`hasattr(None, ...)`, `"XXid2labelXX"`, `"ID2LABEL"`) — silently routes to PET_LABELS fallback | x_classify_pet__mutmut_30, _34, _35 | 3 | TEST-GAP | id2label-priority test with a **SimpleNamespace** config (real hasattr semantics) whose labels differ from PET_LABELS |
| C8 | `classify_pet`: plural-label normalization clobbered (`endswith("s")` → `endswith("XXsXX")` / `endswith("S")`) — "cats" leaks unnormalized | x_classify_pet__mutmut_43, _44 | 2 | TEST-GAP | Assert exact `animal_type == "cat"` — today's `in ["cat","cats"]` accepts both |
| C9 | `classify_pet`: `id2label.get(str(pred_idx), PET_LABELS[pred_idx])` key/default clobbered (`None` key, `str(None)` key, default→`None`/dropped) | x_classify_pet__mutmut_37, _38, _40 | 4 | TEST-GAP | Two mocks: labels differ from PET_LABELS (kills key mutants _37/_41); dict missing predicted key (default mutants _38/_40 → `None.endswith` crashes → RuntimeError) |
| C10 | `load_pet_classifier_model`: `logger.info` message → None/case/XX variants at 3 sites (loading, fp16-moved, success) | x_load_pet_classifier_model__mutmut_6, _13, _25 | 6 | LOW-VALUE | Cosmetic diagnostics; killable only via caplog message asserts, not worth pinning |
| C11 | `classify_pet`: explicit `is_household_pet=True` kwarg dropped at return site | x_classify_pet__mutmut_61 | 1 | EQUIVALENT | Dataclass field default is `True` — zero behavioral delta |
| C12 | `classify_pet`: catch-all `logger.error("Pet classification failed", exc_info=True)` message/exc_info mutations (None/None-exc/dropped/XX/case) | x_classify_pet__mutmut_66, _67, _70 | 7 | LOW-VALUE | Wrapping `RuntimeError("Pet classification failed: ...")` is already asserted by `test_classify_pet_runtime_error`; only the log prose/traceback flag changes |
| C13 | `format_pet_for_nemotron`: returned sentinel/risk-note strings XX-wrapped (`"XXhousehold pet, low security riskXX"` etc. — literal chars inserted into the returned string) | x_format_pet_for_nemotron__mutmut_2, _11, _17 | 4 | LOW-VALUE | Real change but cosmetic prose: existing `in`-fragment assertions still pass because the fragment is embedded in the wrap; only a full-string equality assert kills it (T5 optional) |
| C14 | `load_pet_classifier_model`: CUDA-gate RuntimeError message, ImportError warn/raise messages clobbered (None/case/XX) | x_load_pet_classifier_model__mutmut_2, _3, _26 | 8 | LOW-VALUE | Raise sites are already proven by `pytest.raises(match="Failed to load pet classifier" / "Pet classifier requires transformers and torch")`; only prose differs |
| C15 | `load_pet_classifier_model`: `processor = None` and `from_pretrained(model_path)` → `from_pretrained(None)` (both processor and model loaders) — success test only checks `"model" in result` | x_load_pet_classifier_model__mutmut_8, _9, _11 | 3 | TEST-GAP | Identity assert `result["processor"] is mock_processor` + `from_pretrained.assert_called_once_with("/test/model/path")` |
| C16 | `load_pet_classifier_model`: failure `logger.error` fields — message XX/case, `exc_info` None/False/dropped, `extra=None`/dropped, `extra` key renames (`XXmodel_pathXX`, `MODEL_PATH`) | x_load_pet_classifier_model__mutmut_33, _35, _44 | 11 | LOW-VALUE | Structured-log fields only; nothing consumes `extra` keys; the wrapping RuntimeError string is already matched by existing error tests |

**Verified totals: TEST-GAP = C1 2 + C2 6 + C3 6 + C4 1 + C5 7 + C7 3 + C8 2 + C9 4 + C15 3 = 34; LOW-VALUE = C10 6 + C12 7 + C13 4 + C14 8 + C16 11 = 36; EQUIVALENT = C6 1 + C11 1 = 2. Sum = 72.**

## Classification rationale (key judgment calls)

- **C1/C2/C4 TEST-GAP (not EQUIVALENT):** the mutations replace a computed float with `None`/wrong-index in the *returned* `PetClassificationResult`. `test_classify_pet_success` (L512) asserts only `isinstance`, `animal_type in ["cat","cats"]`, `is_household_pet is True`. The mock supplies 0.95/0.05 but no assertion ever reads `confidence`, `cat_score`, or `dog_score`. Downstream (`is_likely_pet_false_positive`, enrichment context) consumes `confidence` — a real behavior change flowing through unasserted.
- **C5 caveat:** under *real* torch with 2-D `[1, 2]` logits, `dim=None`/`dim=+1` happen to be numerically equivalent to `dim=-1`; they are observably wrong for batched/multi-class shapes and via the mock call contract. Still TEST-GAP because the call contract (`return_tensors="pt"`, `dim=-1`) is the documented device/dtype-correctness path and nothing asserts it. Under the existing MagicMock suite, several C5 mutants additionally crash (TypeError→RuntimeError) yet survive because the success test never crosses that path with a real check — same gap.
- **C6 EQUIVALENT:** `hasattr(obj, "id2label")` is unconditionally True for every config that reaches this line (HF `PretrainedConfig` always exposes the attribute); with the guard always truthy, `and config.id2label` ≡ `or config.id2label` — no input distinguishes them.
- **C7 TEST-GAP:** unlike C6, the string mutations change the *guard's result* on a real config lacking `id2label` — the mutant routes to the PET_LABELS fallback. The existing success test passes either way because its mock's `id2label = {"0": "cats"}` normalizes to the same `"cat"`. Kill needs a config with distinctive labels on a **SimpleNamespace** (a MagicMock answers `hasattr` for any name — which is exactly why these mutants are invisible under the current mock style).
- **C8 TEST-GAP:** the normalization `"cats"→"cat"` exists so downstream consumers get canonical labels; the test's `in ["cat","cats"]` was written to accept the bug. The "design check" at L705 greps source text for `endswith("s")` — a text assertion that survives operator-level mutants.
- **C9 kill split:** key mutants (`get(None, ...)`, `get(str(None), ...)`) are killed only when the queried key IS present but the mutated key misses (labels differ from PET_LABELS → mutant returns "cat" instead of config label); default mutants (`default=None`/dropped) are killed only when the key is ABSENT (original falls back to PET_LABELS, mutant produces `None` → `None.endswith` raises → RuntimeError). Drafts T2+T3 cover both.
- **C11 EQUIVALENT:** dropped `is_household_pet=True` kwarg is refilled by the dataclass field default `True` — zero behavioral delta (the existing `is True` assertion cannot and should not kill it).
- **C13/C14/C16 rationale:** message/prose and structured-log-field changes. The XX wraps *do* change the string (literal `XX` chars), so they are real-but-cosmetic = LOW-VALUE, not EQUIVALENT. Existing `match=` assertions already pin the exception strings that matter; the survivors are all at sites where only log-line prose or `extra` dict keys changed. Recommend the baseline accept these 36 rather than grow caplog-only tests.
- **C15 TEST-GAP:** `test_load_pet_classifier_model_success_cuda` (L432) asserts `assert "model" in result and "processor" in result` — a `None` *value* under a present key passes, and `from_pretrained(None)` also passes because MagicMock accepts any call. Identity + exact-path asserts are the fix.

## Drafted tests (UNVERIFIED — not run red/green per harness constraint)

All go in `backend/tests/unit/services/test_pet_classifier_loader.py`, following the existing mock style (MagicMock torch via `monkeypatch.setitem(sys.modules, ...)`, real PIL image, `@pytest.mark.asyncio`).

### T1 — kills C1, C2, C3, C4, C5, C8  (primary kill-test: mock-boundary value flow)

TDD procedure: each named assert fails on the mutant diff (None / wrong value / wrong call args) and passes on the original.

```python
@pytest.mark.asyncio
async def test_classify_pet_success_maps_probabilities_and_scores(monkeypatch):
    """Success path: every value crossing the torch/transformers mock boundary
    is asserted. Kills mutants that swap confidence/scores to None or wrong
    probs index, clobber processor()/softmax() call args, or skip label
    normalization. (C1, C2, C3, C4, C5, C8)

    // UNVERIFIED - not yet run red/green
    """
    import sys

    from PIL import Image

    test_image = Image.new("RGB", (224, 224))

    mock_torch = MagicMock()

    # probs[0] = cat 0.95, probs[1] = dog 0.05; any other index raises
    # (kills dog_score = probs[2] mutant via KeyError -> RuntimeError)
    def score_item(idx):
        scores = {0: 0.95, 1: 0.05}
        return MagicMock(item=lambda: scores[idx])

    mock_probs = MagicMock()
    mock_probs.argmax.return_value = MagicMock(item=lambda: 0)  # cat wins
    mock_probs.__getitem__ = lambda _self, idx: score_item(idx)

    # softmax result index 0 is the real probs row; other indices are a
    # decoy that would classify "dog" with 0.05 confidence — kills the
    # probs[...] row-selector mutant (C4)
    decoy_probs = MagicMock()
    decoy_probs.argmax.return_value = MagicMock(item=lambda: 1)
    decoy_probs.__getitem__ = lambda _self, idx: score_item(1 - idx)
    mock_softmax_result = MagicMock()
    mock_softmax_result.__getitem__ = (
        lambda _self, idx: mock_probs if idx == 0 else decoy_probs
    )
    mock_torch.nn.functional.softmax.return_value = mock_softmax_result

    mock_model = MagicMock()
    mock_param = MagicMock()
    mock_param.is_cuda = False
    mock_model.parameters.return_value = iter([mock_param])
    mock_model.config = MagicMock()
    mock_model.config.id2label = {"0": "cats", "1": "dogs"}

    mock_outputs = MagicMock()
    mock_outputs.logits = MagicMock()
    mock_model.return_value = mock_outputs

    mock_processor = MagicMock()
    mock_processor.return_value = {"pixel_values": MagicMock()}

    monkeypatch.setitem(sys.modules, "torch", mock_torch)

    result = await classify_pet({"model": mock_model, "processor": mock_processor}, test_image)

    # Call-contract across the mock boundary (kills C3, C5)
    mock_processor.assert_called_once_with(images=test_image, return_tensors="pt")
    mock_torch.nn.functional.softmax.assert_called_once_with(mock_outputs.logits, dim=-1)

    # Value flow into the result (kills C1, C2, C4)
    assert result.confidence == 0.95
    assert result.cat_score == 0.95
    assert result.dog_score == 0.05
    assert result.is_household_pet is True
    # Exact label — rejects the unnormalized "cats" leak (kills C8)
    assert result.animal_type == "cat"
```

### T2 — kills C7, C9 key mutants (x_37, x_41), plus C8  (id2label priority with real hasattr semantics)

```python
@pytest.mark.asyncio
async def test_classify_pet_prefers_id2label_over_pet_labels(monkeypatch):
    """With a config whose id2label differs from PET_LABELS, the label must
    come from id2label. SimpleNamespace (not MagicMock) so hasattr has real
    semantics — kills the hasattr attr-name mutants that silently route to
    the PET_LABELS fallback (C7), and the id2label.get key mutants (C9:
    None / str(None) key miss the present "0" key).

    // UNVERIFIED - not yet run red/green
    """
    import sys
    from types import SimpleNamespace

    from PIL import Image

    test_image = Image.new("RGB", (224, 224))
    mock_torch = MagicMock()

    mock_probs = MagicMock()
    mock_probs.argmax.return_value = MagicMock(item=lambda: 0)
    mock_probs.__getitem__ = lambda _self, idx: MagicMock(
        item=lambda: {0: 0.97, 1: 0.03}[idx]
    )
    softmax_row = MagicMock()
    softmax_row.__getitem__ = lambda _self, idx: mock_probs
    mock_torch.nn.functional.softmax.return_value = softmax_row

    mock_model = MagicMock()
    mock_param = MagicMock()
    mock_param.is_cuda = False
    mock_model.parameters.return_value = iter([mock_param])
    # Real-ish config: hasattr(SimpleNamespace(), "XXid2labelXX") is False
    mock_model.config = SimpleNamespace(id2label={"0": "kitty", "1": "puppy"})
    mock_model.return_value = SimpleNamespace(logits=MagicMock())

    monkeypatch.setitem(sys.modules, "torch", mock_torch)

    result = await classify_pet({"model": mock_model, "processor": MagicMock()}, test_image)

    assert result.animal_type == "kitty"  # not PET_LABELS fallback "cat"
    assert result.confidence == 0.97
```

### T3 — kills C9 default mutants (x_38, x_40)

```python
@pytest.mark.asyncio
async def test_classify_pet_falls_back_to_pet_labels_when_id2label_missing_key(monkeypatch):
    """id2label present but lacking the predicted index must fall back to
    PET_LABELS, not produce None (mutants that drop/None the .get default
    crash at raw_label.endswith -> RuntimeError). (C9)

    // UNVERIFIED - not yet run red/green
    """
    import sys
    from types import SimpleNamespace

    from PIL import Image

    test_image = Image.new("RGB", (224, 224))
    mock_torch = MagicMock()

    mock_probs = MagicMock()
    mock_probs.argmax.return_value = MagicMock(item=lambda: 0)
    mock_probs.__getitem__ = lambda _self, idx: MagicMock(
        item=lambda: {0: 0.99, 1: 0.01}[idx]
    )
    softmax_row = MagicMock()
    softmax_row.__getitem__ = lambda _self, idx: mock_probs
    mock_torch.nn.functional.softmax.return_value = softmax_row

    mock_model = MagicMock()
    mock_param = MagicMock()
    mock_param.is_cuda = False
    mock_model.parameters.return_value = iter([mock_param])
    mock_model.config = SimpleNamespace(id2label={"7": "kitty"})  # "0" absent
    mock_model.return_value = SimpleNamespace(logits=MagicMock())

    monkeypatch.setitem(sys.modules, "torch", mock_torch)

    result = await classify_pet({"model": mock_model, "processor": MagicMock()}, test_image)

    assert result.animal_type == "cat"  # PET_LABELS[0] fallback, no exception
```

### T4 — kills C15  (load success path: values + exact path, not key presence)

```python
@pytest.mark.asyncio
async def test_load_pet_classifier_model_success_wires_exact_model_path(monkeypatch):
    """Success path must return the processor/model built from the EXACT
    model_path — `"model" in result` passes while the loaded object is None
    or built from None. (C15: x_load_pet_classifier_model__mutmut_8, _9, _11)

    // UNVERIFIED - not yet run red/green
    """
    import sys

    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = True

    mock_cuda_model = MagicMock()
    mock_cuda_model.half.return_value = mock_cuda_model
    mock_model = MagicMock()
    mock_model.cuda.return_value = mock_cuda_model

    mock_processor = MagicMock()

    mock_transformers = MagicMock()
    mock_transformers.AutoImageProcessor.from_pretrained.return_value = mock_processor
    mock_transformers.AutoModelForImageClassification.from_pretrained.return_value = mock_model

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    result = await load_pet_classifier_model("/test/model/path")

    mock_transformers.AutoImageProcessor.from_pretrained.assert_called_once_with("/test/model/path")
    mock_transformers.AutoModelForImageClassification.from_pretrained.assert_called_once_with(
        "/test/model/path"
    )
    assert result["processor"] is mock_processor  # kills processor = None
    assert result["model"] is mock_cuda_model     # kills .half() chain breakage
```

### T5 — pins C13 strings (optional; C13 is LOW-VALUE so this is defensive pinning, not a gap kill)

```python
def test_format_pet_for_nemotron_exact_canonical_strings():
    """Pin the full canonical output strings so XX-wrap prose mutants cannot
    drift silently. (C13 — LOW-VALUE class; optional)

    // UNVERIFIED - not yet run red/green
    """
    high = PetClassificationResult(
        animal_type="dog", confidence=0.92, cat_score=0.08, dog_score=0.92
    )
    med = PetClassificationResult(
        animal_type="dog", confidence=0.75, cat_score=0.25, dog_score=0.75
    )
    low = PetClassificationResult(
        animal_type="cat", confidence=0.55, cat_score=0.55, dog_score=0.45
    )

    assert format_pet_for_nemotron(high) == (
        "Pet classification: dog (92% confidence) - household pet, low security risk"
    )
    assert format_pet_for_nemotron(med) == (
        "Pet classification: dog (75% confidence) - likely household pet, minimal security concern"
    )
    assert format_pet_for_nemotron(low) == (
        "Pet classification: cat (55% confidence) - uncertain classification, "
        "evaluate as potential wildlife"
    )
    assert format_pet_for_nemotron(None) == (
        "Pet classification: unknown (classification unavailable)"
    )
```

## Recommendation

- Land **T1** first — one test kills 24 survivors (C1 2 + C2 6 + C3 6 + C4 1 + C5 7 + C8 2) and encodes the two rules the file's mocks have never enforced: *assert values across the mock boundary* and *assert call kwargs*.
- **T2/T3** (5 kills: C7 3 + C9 4 minus overlap accounted — C9's 4 all die across T2/T3, T2's C8 kills are redundant with T1) add real-`hasattr` config semantics. Rule for future loader tests: use SimpleNamespace, never MagicMock, for config objects — the MagicMock answers `hasattr` for anything and lets guard mutants survive.
- **T4** (3 kills, C15) converts the load success test from key-presence to identity assertions.
- Accept C10, C12, C13, C14, C16 (36 survivors: logger prose, `exc_info` flags, `extra` fields) and C6, C11 (2) as baseline-acceptable LOW-VALUE/EQUIVALENT. If a caplog pattern already exists elsewhere in the suite, a shared helper could pin `exc_info=True` cheaply; not otherwise recommended.
