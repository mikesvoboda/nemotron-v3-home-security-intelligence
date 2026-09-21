# WP4.4 Triage Dossier — backend/services/weather_loader.py

- **Meta**: `mutants/backend/services/weather_loader.py.meta` — 279 mutants: 127 killed, **152 survived**, 0 un-checked.
- **Source**: `backend/services/weather_loader.py` (496 lines).
- **Diff method**: spans-file extraction (each `x_<fn>__mutmut_N` variant in the clobbered copy diffed against its `__mutmut_orig` sibling). No `mutmut run`, no pytest executed (constraints honored).
- **Covering test files** (from `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`):
  - `backend/tests/unit/services/test_weather_loader.py` — primary, 928 lines. All `format_*`, `visibility`, `nighttime`, `risk_modifier`, `load_weather_model` coverage lives here.
  - `backend/tests/unit/services/test_enrichment_pipeline.py` — secondary; touches `classify_weather` only through `EnrichmentPipeline._classify_weather` with `{"model": MagicMock(), "processor": MagicMock()}` model data (fixture at line 167; patched to a canned `WeatherResult` at ~3517-3537). **No enrichment test asserts anything about `classify_weather`'s computed output.**

## Headline

`classify_weather` has **zero happy-path coverage**: `test_classify_weather_runtime_error` (test_weather_loader.py:472-488) only asserts `pytest.raises(RuntimeError, match="Weather classification failed")`, which *every crash mutant still satisfies*. `test_classify_weather_callable` (line 462) asserts it's a coroutine. `test_weather_typo_strom_to_storm` (line 494) asserts the **constant** `WEATHER_LABELS`, never the normalization code path. That single gap accounts for 67 of the 152 survivors. Secondary gaps: nighttime-brightness boundary arithmetic, per-condition note strings, and `load_weather_model`'s inner `_load()` (tests assert `"model" in result` / `"processor" in result` — key presence only, never identity or call path).

## Cluster table (counts sum to 152)

Prefix `backend.services.weather_loader.` omitted from example keys.

| # | Function | Pattern | n | Class | Example keys |
|---|----------|---------|---|-------|--------------|
| C1 | classify_weather | `model_dict["model"/"processor"]` extraction → None / key case / XX-wrap (KeyError or None deref) | 6 | TEST-GAP | x_classify_weather__mutmut_1, _2, _3 |
| C2 | classify_weather | `processor(images=..., return_tensors="pt")` call-arg mutations (None args, dropped kwargs, `"PT"`/`"XXptXX"`) | 7 | TEST-GAP | _8, _10, _14 |
| C3 | classify_weather | executor/device-move plumbing → `None` substitutions / dropped args (`loop`, `next(model.parameters())`, `inputs`, `outputs`, `logits`, `run_in_executor`) | 8 | TEST-GAP | _7, _16, _65 |
| C4a | classify_weather | `softmax(logits, dim=-1)[0]` crash-or-value mutations (`probs=None`, `softmax(None…)`, dropped `logits`, `dim=-2`, `[1]`) | 5 | TEST-GAP | _19, _25, _26 |
| C4b | classify_weather | `dim=None` / dropped-`dim` arg — on production batch-1 logits, all-elements softmax ≡ per-row softmax (processor never batches) | 2 | LOW-VALUE | _21, _23 |
| C4c | classify_weather | `dim=+1` — identical to `dim=-1` for ANY 2-D tensor; model logits are always 2-D | 1 | EQUIVALENT | _24 |
| C5 | classify_weather | `pred_idx` / `confidence` extraction → None / `int(None)` | 3 | TEST-GAP | _27, _28, _29 |
| C6 | classify_weather | `hasattr(model.config, "id2label") and …` guard + `.get(pred_idx, WEATHER_LABELS[...])` arg mutations (and→or, None/dropped/mutated attrs & defaults) | 12 | TEST-GAP | _30, _31, _37 |
| C7 | classify_weather | `"strom" in raw_label` typo-normalization mutated (`"XXstromXX"`, `"STROM"`, `not in`) | 3 | TEST-GAP | _42, _43, _44 |
| C8 | classify_weather | `all_scores` construction → None dict / None items / `enumerate(None)` | 4 | TEST-GAP | _45, _46, _48 |
| C9 | classify_weather | `WEATHER_SIMPLE_LABELS.get(raw_label, raw_label.split("/")[0])` fallback mutations (`split("/")[1]`, `split(None)`, dropped/None args, None key — `_50` maps dict labels to fallback, killed by scenario B) | 8 | TEST-GAP | _49, _50, _55 |
| C10 | classify_weather | `WeatherResult(condition=…, simple_condition=…, confidence=…, all_scores=…)` kwarg mutations → None / removed required args | 8 | TEST-GAP | _57, _61, _64 |
| C11 | classify_weather | except-block `logger.error(msg, exc_info=…)` message-text / exc_info mutations | 7 | EQUIVALENT | _68, _72, _75 |
| F1 | format_weather_for_nemotron | `None`-branch return string case/XX text variants (still contain "unknown") | 3 | LOW-VALUE | x_format_weather_for_nemotron__mutmut_2, _3, _4 |
| F2 | format_weather_for_nemotron | per-condition `elif` chain broken (`==`→`!=`, label case/XX) → that condition's note silently missing | 8 | TEST-GAP | _16, _17, _23 |
| F3 | format_weather_for_nemotron | `notes = None` assignments → output ends `…).None` | 3 | TEST-GAP | _19, _26, _33 |
| F4 | format_weather_for_nemotron | `notes` string literals case/XX variants (foggy/rainy/snowy/cloudy/clear) | 15 | LOW-VALUE | _13, _21, _42 |
| F5 | format_weather_for_nemotron | initial `notes = ""` → `None`/`"XXXX"` (only reachable for out-of-set conditions) | 2 | LOW-VALUE | _7, _8 |
| V1 | get_visibility_factor | unknown-condition fallback default `0.8` → `None`/dropped/`1.8` | 3 | TEST-GAP | x_get_visibility_factor__mutmut_23, _25, _26 |
| R1 | get_weather_risk_modifier | confidence gate `<` → `<=` (conf exactly 0.5 now returns 0.0 instead of applying modifier) | 1 | TEST-GAP | x_get_weather_risk_modifier__mutmut_3 |
| R2 | get_weather_risk_modifier | `("foggy", "snowy")` tuple label mutated → **snowy loses +0.1** (falls to 0.0) | 2 | TEST-GAP | _14, _15 |
| R3 | get_weather_risk_modifier | `condition == "clear" and is_nighttime` → `or` (clear daytime AND any-night conditions now return +0.25) | 1 | TEST-GAP | _17 |
| N1 | is_nighttime | unused `timezone="UTC"` default string mutated (param is `noqa: ARG001`, "reserved for future use") — dead | 2 | EQUIVALENT | x_is_nighttime__mutmut_1, _2 |
| N2 | is_nighttime | `hour < NIGHTTIME_END_HOUR` → `<=` (6 AM flips night→"is nighttime"; docstring: END hour 6 AM = *end*) | 1 | TEST-GAP | _6 |
| I1 | is_nighttime_from_image | `shape[2] >= 3` → `> 3` / `>= 4`: 3-channel RGB silently loses luminance, uses plain mean | 2 | TEST-GAP | x_is_nighttime_from_image__mutmut_10, _11 |
| I2 | is_nighttime_from_image | luminance channel indexing (`r`/`g` reads wrong channel) | 2 | TEST-GAP | _13, _14 |
| I3 | is_nighttime_from_image | luminance arithmetic flips (`+0.114*b`→`-b`, `0.299*r`→`0.299/r`, `/g`, `/b`) | 4 | TEST-GAP | _19, _21, _25 |
| I4 | is_nighttime_from_image | brightness `/255.0` → `/256.0` (grayscale + RGB branches) | 2 | TEST-GAP | _8, _27 |
| I5 | is_nighttime_from_image | `brightness < THRESHOLD` → `<=` (exactly-threshold flips daytime→nighttime; docstring says *below* threshold) | 1 | TEST-GAP | _29 |
| L1 | load_weather_model | `logger.info/warning/error` message text, `exc_info`, `extra=` payload mutations (incl. `extra={"model_path":…}` key case) | 20 | EQUIVALENT | x_load_weather_model__mutmut_6, _14, _44 |
| L2 | load_weather_model | `raise RuntimeError("…CUDA GPU…")` / `raise ImportError("…transformers and torch…")` message case/XX variants — existing `match=` substrings still hit | 3 | LOW-VALUE | _3, _31, _32 |
| L3 | load_weather_model | `_load()` internals: `from_pretrained(None)` path swap ×2, `processor = None` — success test asserts only `"model"/"processor" in result` (key presence, not identity) | 3 | TEST-GAP | _9, _10, _12 |

Totals (folded against the physical count): TEST-GAP **97** (C1–C10 excl. C4b/C4c = 64, F2 = 8, F3 = 3, V1 = 3, R1–R3 = 4, N2 = 1, I1–I5 = 11, L3 = 3), EQUIVALENT **30** (C4c = 1, C11 = 7, N1 = 2, L1 = 20), LOW-VALUE **25** (C4b = 2, F1 = 3, F4 = 15, F5 = 2, L2 = 3). 97 + 30 + 25 = 152 ✓

Cross-check: 74 (classify) + 31 (format) + 3 (visibility factor) + 4 (risk modifier) + 3 (is_nighttime) + 11 (image nighttime) + 26 (load) = 152 ✓.

## Judgment notes

- **C1–C10 (67 mutants, one root gap)**: the RuntimeError-match-only test means even total-crash mutants inside `_classify` *pass*. A mock-driven happy-path test (drafts T1a/T1b) kills every C-cluster mutant that changes values and every one that crashes (a crash raises where the test expects a `WeatherResult`).
- **C7**: `test_weather_typo_strom_to_storm` (test_weather_loader.py:494-501) is the "test exists but asserts too weakly" case — it checks `WEATHER_LABELS` constants, never the `"strom" in raw_label → replace` line at weather_loader.py:236-237.
- **F4 (15) LOW-VALUE**: pinning the full LLM-prompt sentence in a unit test is brittle — wording tweaks shouldn't break tests. The existing substring asserts are the right strength; case/XX variants are cosmetic. Draft T4 kills them too as a side effect of exact-match; the note-substring variant (given) kills F2/F3 without pinning prose.
- **I4 (2) / I5 (1)**: killable only with crafted brightness values (see T2 math) — real normalization/contract bugs (/256 off-by-one, threshold inclusivity contradicting the docstring), so TEST-GAP rather than LOW-VALUE.
- **L1 (20)**: per feed convention, pure logging text/`exc_info`/`extra` mutations are EQUIVALENT.
- **N1 (2)**: mutated parameter is never read (future-use stub) — dead defensive tweak.

## Drafted tests (UNVERIFIED - not yet run red/green)

All go in `backend/tests/unit/services/test_weather_loader.py` (append after `test_weather_typo_strom_to_storm`, ~line 502). Style follows the file: module-level async tests with `MagicMock`, `pytest.approx`. TDD procedure for each: apply that cluster's single mutant edit to `backend/services/weather_loader.py`, run the new test — the assertion must FAIL (or raise RuntimeError); revert — it must PASS; then `mutmut run --paths-to-mutate backend/services/weather_loader.py` shows the keys killed.

### T1 — `test_classify_weather_happy_path_maps_id2label` (kills C1–C6, C8, C10, and C7 via scenario B)

```python
# UNVERIFIED - not yet run red/green
@pytest.mark.asyncio
async def test_classify_weather_happy_path_maps_id2label():
    """Happy path pins id2label mapping, typo normalization, all_scores, confidence.

    Existing coverage only asserts classify_weather RAISES (test_weather_
    classify_weather_runtime_error), so every crash/value mutant survives.
    """
    import torch
    from types import SimpleNamespace
    from PIL import Image

    from backend.services.weather_loader import (
        WEATHER_LABELS,
        classify_weather,
    )

    image = Image.new("RGB", (224, 224))
    id2label = {0: "overcast", 2: "rain/strom", 4: "sun/clear"}  # model's real typo at 2

    def make_model_dict(logits_row):
        model = MagicMock()
        model.parameters.return_value = [MagicMock(is_cuda=False)]
        model.config = SimpleNamespace(id2label=dict(id2label))
        model.return_value = SimpleNamespace(
            logits=torch.tensor([logits_row], dtype=torch.float32)
        )
        processor = MagicMock(return_value={"pixel_values": MagicMock()})
        return {"model": model, "processor": processor}, model, processor

    # Scenario A: predicted index IS in id2label and its label deliberately
    # DIFFERS from WEATHER_LABELS[0] -> kills hasattr-guard mutants that would
    # silently fall back to WEATHER_LABELS (mutmut_35/_36), and .get-arg
    # mutants (mutmut_38 returns WEATHER_LABELS[0] instead of "overcast").
    model_dict, model, processor = make_model_dict([2.0, 0.5, -0.5, 0.1, 0.0])
    result = await classify_weather(model_dict, image)
    processor.assert_called_once_with(images=image, return_tensors="pt")  # kills C2
    expected_probs = torch.softmax(
        torch.tensor([[2.0, 0.5, -0.5, 0.1, 0.0]]), dim=-1
    )[0]
    assert result.condition == "overcast"
    assert result.simple_condition == "overcast"  # split("/") fallback for unknown label
    assert result.confidence == pytest.approx(expected_probs[0].item())
    assert set(result.all_scores) == set(WEATHER_LABELS)  # kills C8
    for i, label in enumerate(WEATHER_LABELS):
        assert result.all_scores[label] == pytest.approx(expected_probs[i].item())

    # Scenario B: id2label typo "rain/strom" must normalize -> kills C7
    # (_42/_43 skip normalization, _44 inverts the guard -> condition stays "rain/strom")
    model_dict, _, _ = make_model_dict([0.0, 0.1, 2.0, 0.2, -0.5])
    result = await classify_weather(model_dict, image)
    assert result.condition == "rain/storm"
    assert result.simple_condition == "rainy"

    # Scenario C: predicted index 3 is ABSENT from id2label -> .get default
    # must be WEATHER_LABELS[3] -> kills mutmut_39/_41 (default None ->
    # TypeError on `"strom" in raw_label` / simple_condition None)
    model_dict, _, _ = make_model_dict([0.0, 0.1, -0.5, 2.0, 0.2])
    result = await classify_weather(model_dict, image)
    assert result.condition == "snow/frosty"
    assert result.simple_condition == "snowy"

    # Scenario D: CUDA branch (is_cuda=True) - the device-move dict
    # comprehension must run; mutmut_16 (`inputs = None` there) turns the
    # model call into model(**None) -> RuntimeError where we expect a result
    model_dict, model, _ = make_model_dict([2.0, 0.5, -0.5, 0.1, 0.0])
    model.parameters.return_value = [MagicMock(is_cuda=True)]
    result = await classify_weather(model_dict, image)
    assert result.condition == "overcast"
    assert result.simple_condition == "overcast"
```

Scenario D additionally drives the CUDA device-move branch (`is_cuda=True`), killing `_16` (`inputs = None` inside that branch is unreachable when `is_cuda` is False).

**Not killed (by design):** `_24` (`dim=+1`) is identical to `dim=-1` for any 2-D tensor — model logits are always 2-D (C4c, EQUIVALENT). `_21`/`_23` (`dim=None` / dropped `dim`): torch softmax with no dim reduces over all elements but preserves shape; on the processor's single-row logits `(1, 5)` that is value-identical to `dim=-1` (C4b, LOW-VALUE — no classify_weather call can batch, so no test can distinguish them). The rest of C4 die in scenario A: `_19`/`_20`/`_22` crash (RuntimeError where the test expects a result), `_25` (`dim=-2` on shape `(1,5)` → all-1.0 probs, breaks the confidence/all_scores approx asserts), `_26` (`[1]` → IndexError inside `_classify`).

### T2 — `test_classify_weather_no_id2label_uses_module_labels` (kills `_30`; enables C9 pair)

```python
# UNVERIFIED - not yet run red/green
@pytest.mark.asyncio
async def test_classify_weather_no_id2label_uses_module_labels():
    """Config without an id2label attribute must take the WEATHER_LABELS branch.

    The `and`->`or` mutant (mutmut_30) then touches model.config.id2label and
    raises AttributeError, proving the short-circuit guard is load-bearing.
    """
    import torch
    from types import SimpleNamespace
    from PIL import Image

    from backend.services.weather_loader import classify_weather

    image = Image.new("RGB", (224, 224))
    model = MagicMock()
    model.parameters.return_value = [MagicMock(is_cuda=False)]
    model.config = SimpleNamespace()  # NOTE: no id2label attribute at all
    model.return_value = SimpleNamespace(
        logits=torch.tensor([[0.1, 0.0, 0.2, 1.5, 0.3]], dtype=torch.float32)
    )
    processor = MagicMock(return_value={"pixel_values": MagicMock()})

    result = await classify_weather({"model": model, "processor": processor}, image)

    assert result.condition == "snow/frosty"  # WEATHER_LABELS[3]
    assert result.simple_condition == "snowy"
```

### T3 — `test_classify_weather_unknown_label_falls_back_to_first_segment` (kills C9, `_49`–`_56` except `_50`)

```python
# UNVERIFIED - not yet run red/green
@pytest.mark.asyncio
async def test_classify_weather_unknown_label_falls_back_to_first_segment():
    """A label missing from WEATHER_SIMPLE_LABELS simplifies via split("/")[0].

    split("/") is only exercised when id2label yields an out-of-catalogue
    label - the realistic SigLIP fine-tune case.
    """
    import torch
    from types import SimpleNamespace
    from PIL import Image

    from backend.services.weather_loader import classify_weather

    image = Image.new("RGB", (224, 224))
    model = MagicMock()
    model.parameters.return_value = [MagicMock(is_cuda=False)]
    model.config = SimpleNamespace(id2label={0: "windy/dusty"})
    model.return_value = SimpleNamespace(
        logits=torch.tensor([[2.0, 0.0, 0.1, 0.2, 0.3]], dtype=torch.float32)
    )
    processor = MagicMock(return_value={"pixel_values": MagicMock()})

    result = await classify_weather({"model": model, "processor": processor}, image)

    assert result.condition == "windy/dusty"
    assert result.simple_condition == "windy"  # not "dusty", not "windy/dusty", not None
```

### T4 — `test_is_nighttime_from_image_luminance_and_threshold_boundary` (kills I1–I5)

```python
# UNVERIFIED - not yet run red/green
    def test_is_nighttime_from_image_luminance_and_threshold_boundary(self):
        """Pin the luminance formula, /255.0 normalization, and strict < threshold.

        Values verified against float64 arithmetic:
        - (78,76,76): luminance 76.598 -> 0.30038 >= 0.3 -> NOT nighttime,
          while plain-mean and every arithmetic-flip mutant fall under 0.3;
          /256.0 mutant also drops to 0.29921.
        - (10,10,230): luminance 35.08 (nighttime) vs plain mean 83.33
          (daytime) -> discriminates the shape[2] >= 3 branch (I1).
        - (10,86,10)/(50,20,100)/(10,10,230) flip under r/g channel swaps (I2).
        - grayscale mean exactly 76.5 -> brightness EXACTLY 0.3 -> strict <
          says daytime; `<=` mutant says nighttime (I5).
        """
        import numpy as np
        from PIL import Image

        from backend.services.weather_loader import is_nighttime_from_image

        # Just-above-threshold RGB: only the true luminance formula keeps this daytime
        borderline = Image.new("RGB", (10, 10), color=(78, 76, 76))
        assert is_nighttime_from_image(borderline) is False

        # Blue-heavy: nighttime by luminance (35.08/255), NOT by plain mean (83.33/255)
        blue_heavy = Image.new("RGB", (10, 10), color=(10, 10, 230))
        assert is_nighttime_from_image(blue_heavy) is True

        # Channel-swap discriminators (each true-formula answer is nighttime;
        # the r/g index mutants compute a brighter value above threshold)
        assert is_nighttime_from_image(Image.new("RGB", (4, 4), color=(10, 86, 10))) is True
        assert is_nighttime_from_image(Image.new("RGB", (4, 4), color=(50, 20, 100))) is True

        # Grayscale with mean EXACTLY 76.5 -> brightness EXACTLY 0.3 -> NOT nighttime
        gray = np.full((2, 2), 76, dtype=np.uint8)
        gray[0, 1] = 77
        assert is_nighttime_from_image(Image.fromarray(gray)) is False
```

### T5 — `test_get_weather_risk_modifier_branch_boundaries` (kills R1, R2, R3)

```python
# UNVERIFIED - not yet run red/green
    def test_get_weather_risk_modifier_branch_boundaries(self):
        """Pin the exact confidence gate, the snowy member, and clear-AND-night."""
        from backend.services.weather_loader import get_weather_risk_modifier

        # Gate is strict `<`: confidence EXACTLY 0.5 must still apply the modifier
        # (mutmut_3 `<=` would zero it out)
        borderline_fog = WeatherResult(
            condition="foggy/hazy", simple_condition="foggy",
            confidence=0.5, all_scores={},
        )
        assert get_weather_risk_modifier(borderline_fog, is_nighttime=False) == pytest.approx(0.1, abs=0.01)

        # Snowy is a member of ("foggy", "snowy") - tuple-label mutants drop it to 0.0
        snowy = WeatherResult(
            condition="snow/frosty", simple_condition="snowy",
            confidence=0.8, all_scores={},
        )
        assert get_weather_risk_modifier(snowy, is_nighttime=False) == pytest.approx(0.1, abs=0.01)

        # Clear DAYTIME must stay neutral - the `and`->`or` mutant returns 0.25
        clear_day = WeatherResult(
            condition="sun/clear", simple_condition="clear",
            confidence=0.9, all_scores={},
        )
        assert get_weather_risk_modifier(clear_day, is_nighttime=False) == 0.0
```

### T6 — `test_visibility_factor_unknown_condition_uses_neutral_default` + `test_format_weather_per_condition_notes` (kills V1; F2, F3)

```python
# UNVERIFIED - not yet run red/green
def test_visibility_factor_unknown_condition_uses_neutral_default():
    """Out-of-catalogue condition must fall back to the 0.8 neutral base.

    Tests only cover the 5 known conditions, so the `.get(condition, 0.8)`
    default is never executed - mutants swap it to None / 1.8 / dropped.
    """
    weather = WeatherResult(
        condition="windy/dusty",
        simple_condition="windy",
        confidence=1.0,
        all_scores={},
    )
    factor = get_visibility_factor(weather)
    assert factor == pytest.approx(0.8)


def test_format_weather_per_condition_notes():
    """Each condition must yield its OWN visibility note (no fall-through)."""
    for simple, condition, note_frag in (
        ("foggy", "foggy/hazy", "fog"),
        ("rainy", "rain/storm", "detection accuracy"),
        ("snowy", "snow/frosty", "camera image quality"),
        ("cloudy", "cloudy/overcast", "reduced lighting"),
        ("clear", "sun/clear", "Good visibility"),
    ):
        weather = WeatherResult(
            condition=condition, simple_condition=simple,
            confidence=0.8, all_scores={},
        )
        result = format_weather_for_nemotron(weather)
        assert note_frag in result, f"{simple}: note missing or wrong branch"
        assert "None" not in result  # kills `notes = None` mutants (F3)
```

### T7 — strengthen `test_load_weather_model_success_cuda` identity asserts (kills L3: `_9`, `_10`, `_12`)

```python
# UNVERIFIED - not yet run red/green
# Append to the existing test at test_weather_loader.py:424 (it currently only
# asserts key PRESENCE - "model"/"processor" in result - which even
# processor=None satisfies):
    assert result["processor"] is mock_processor          # kills mutmut_9 (processor=None)
    assert result["model"] is mock_half_model             # identity: _load returns the CUDA/fp16 model
    mock_transformers.AutoImageProcessor.from_pretrained.assert_called_once_with("/test/model/cuda")
    mock_transformers.AutoModelForImageClassification.from_pretrained.assert_called_once_with("/test/model/cuda")
    # the two from_pretrained(None) mutants (_10, _12) fail the path asserts
```

### Not drafted (remaining single-mutant TEST-GAPs)

- **N2** (`is_nighttime` `hour < END` -> `<=`, flips exactly 6 AM): one-line draft — `assert is_nighttime(datetime(2024, 6, 15, 6, 0, 0)) is False` (docstring: 6 AM is the *end* of nighttime). Fold into `TestIsNighttimeDuskDawnEdgeCases` when fixing.

## Covering-test file pointers

- Primary: `backend/tests/unit/services/test_weather_loader.py:462-488` (classify gap), `:494-501` (weak typo test), `:693-761` (image nighttime), `:847-928` (risk modifier), `:268-347` (visibility factor), `:125-202` (format).
- Secondary (mocked pipeline only, no direct asserts): `backend/tests/unit/services/test_enrichment_pipeline.py:167`, `:3517-3537`.

## Constraint compliance

- No pytest / mutmut run executed; no repo file modified. Only write: this dossier.
- Diffs via spans-file extraction from `mutants/backend/services/weather_loader.py` (safe against the live run; `mutmut show` not needed).
