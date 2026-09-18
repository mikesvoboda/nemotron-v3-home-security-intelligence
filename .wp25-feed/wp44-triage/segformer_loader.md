# WP4.4 finding feed — triage of SURVIVING mutants: `backend/services/segformer_loader.py`

**Run basis**: `mutants/backend/services/segformer_loader.py.meta` → 262 keys, 77 killed,
**185 survived** (exit_code 0), 0 unchecked. Diffs recovered offline by diffing each clobbered
variant region in `mutants/backend/services/segformer_loader.py` (offsets from `.spans`) against
`backend/services/segformer_loader.py` — `mutmut show` not used (cache under concurrent write).
Every survivor carries exactly one mutation; each is assigned to exactly one cluster (Σ = 185).

**Covering test file (the only one)**: `backend/tests/unit/services/test_segformer_loader.py`
(1154 lines). Cross-checked against
`mutants/mutmut-stats.json → tests_by_mangled_function_name`.

| function                             | survivors / total | tests touching it (file:line)                                                                                             |
| ------------------------------------ | ----------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `segment_clothing`                   | 152 / 153         | `test_segformer_loader.py:849` (`test_segment_clothing_success_path`), `:925` (`_with_shoes`), `:547` (`_error_handling`) |
| `load_segformer_model`               | 20 / 46           | `:404`, `:435`, `:460`, `:476`                                                                                            |
| `segment_clothing_batch`             | 8 / 12            | `:1017`, `:1037`, `:1056`, `:580`                                                                                         |
| `format_clothing_context`            | 4 / 18            | `:183`, `:192`, `:207`, `:220`, `:233`, `:248`                                                                            |
| `format_batch_clothing_context`      | 1 / 24            | `:269`–`:396`                                                                                                             |
| `ClothingSegmentationResult.to_dict` | 0 / 9             | `:55`, `:75`, `:739`, `:773`, `:1087` (all 9 killed — well covered)                                                       |

## Why 71 % of this module survives

The two tests that drive `segment_clothing`'s success path
(`test_segment_clothing_success_path:849-922`, `test_segment_clothing_with_shoes:925-969`) build a
complete mock inference graph and then assert **only** `isinstance(result,
ClothingSegmentationResult)` (`:922`, `:969`). The mocks pre-bake `np.unique` returns and a fake
mask, yet none of that value is checked. Worse: the module's blanket
`except Exception: return ClothingSegmentationResult()` (`segformer_loader.py:304-306`) turns _any_
mock breakage caused by a mutation into an empty-but-valid result, which still passes `isinstance`.
So every mutation to the inference pipeline, coverage arithmetic, shoe consolidation, face-covered
rule and result construction is invisible. The "face covered logic" test (`:972-999`) never calls
`segment_clothing` — it constructs a `ClothingSegmentationResult(has_face_covered=True)` and asserts
the dataclass echoes the flag back. `to_dict` (fully value-asserted) dying at 9/9 is the control
case proving the mechanism.

## Cluster table (Σ n = 185 · TEST-GAP 144 · LOW-VALUE 27 · EQUIVALENT 14)

Example keys are suffixed on `backend.services.segformer_loader.`.

| #   | n   | Class      | Cluster (pattern @ function/concern)                                                                                                                                                                                                                                                                                                                                                                                            | Example keys                                                                               |
| --- | --- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| 1   | 28  | TEST-GAP   | `segment_clothing`: inference-pipeline argument forwarding — `processor(images=…)` / `return_tensors="pt"` variants, `next(model.parameters()).device`, `v.to(device)`, `model(**inputs)`, `outputs.logits`, `interpolate(logits, size=person_crop.size[::-1], mode="bilinear", align_corners=False)` (incl. `size[::+1]`, `size[::-2]`, `align_corners=True`, `mode="BILINEAR"`, required-arg deletions), `argmax(dim=2/None)` | `x_segment_clothing__mutmut_3`, `_17`, `_28`                                               |
| 2   | 26  | TEST-GAP   | `segment_clothing`: security-item membership + shoe consolidation — `label in SECURITY_CLOTHING_LABELS`→`not in`, `add(label)`→`add(None)`, `elif label in SHOE_LABELS`→`not in`, `"shoes"` literal case/XX variants, `get("shoes", 0.0)` key/default corruption, `round(current + coverage*100, 2)`→`-`/`/100`/`*101`/ndigits-3/None, `pop(label, None)` key→None                                                              | `_71`, `_84`, `_92`                                                                        |
| 3   | 28  | TEST-GAP   | `segment_clothing`: `has_face_covered` rule + `has_bag` membership — `in`→`not in` on sunglasses/hat/scarf/bag, label-literal case & XX variants, `hat or scarf`→`and`, `has_sunglasses and`→`or`, `(… or face_coverage < 5.0)`→`and`/`<=`/`< 6.0`, `get("face", 0.0)` key/default corruption                                                                                                                                   | `_104`, `_121`, `_123`                                                                     |
| 4   | 18  | TEST-GAP   | `segment_clothing`: mask-stats + coverage-value arithmetic — whole-line `predicted_mask = …`→None, `total_pixels = predicted_mask.size`→None, `np.unique(…, return_counts=True)`→`False`/`None`/dropped, `count / total_pixels`→`*`, `round(coverage*100, 2)`→`/100`/`*101`/ndigits-3/None/whole→None, `coverage_percentages`/`clothing_items` init→None                                                                        | `_29`, `_38`, `_68`                                                                        |
| 5   | 13  | TEST-GAP   | `segment_clothing`: coverage gate + label lookup — `label != "background"`→`==`/`"XXbackgroundXX"`/`"BACKGROUND"`, gate `and`→`or`, `coverage >= min_coverage`→`>`, `zip(unique_classes, counts, strict=True)` required-arg drops, `CLOTHING_LABELS.get(int(class_id), "unknown")` required-arg drops (incl. `_51` `get("unknown")` → key miss → `label=None` for EVERY class)                                                  | `_59`, `_62`, `_51`                                                                        |
| 6   | 11  | LOW-VALUE  | `load_segformer_model`: log/message **text** only — CUDA-raise first line, `logger.info(None)` ×2, ImportError warning text (incl. both-args→None), `logger.error(None, …)`, case/XX variants                                                                                                                                                                                                                                   | `x_load_segformer_model__mutmut_6`, `_27`, `_34`                                           |
| 7   | 10  | TEST-GAP   | `segment_clothing`: result-construction kwargs nulled/deleted — `clothing_items=None`, `has_face_covered=None`, `has_bag=None`, `coverage_percentages=None`, `raw_mask=None`, plus each kwarg deleted (→ dataclass default silently wins)                                                                                                                                                                                       | `_128`, `_131`, `_132`                                                                     |
| 8   | 7   | TEST-GAP   | `segment_clothing_batch`: per-crop call forwarding — `segment_clothing(None, processor, …)`, `(model, None, …)`, `(model, processor, None, …)`, `min_coverage`→None/dropped, positional shifts `(model, crop, min_coverage)`, `(processor, crop, min_coverage)`                                                                                                                                                                 | `x_segment_clothing_batch__mutmut_4`, `_7`, `_10`                                          |
| 9   | 7   | TEST-GAP   | `segment_clothing`: executor wiring broken — `loop=None`, `run_in_executor(None, None)`, `run_in_executor(_segment)` (executor dropped), whole call nulled/deleted; each lands in the blanket `except` and returns an **empty** result that still passes the `isinstance` assertions                                                                                                                                            | `_1`, `_142`, `_143`                                                                       |
| 10  | 4   | EQUIVALENT | `segment_clothing`: `CLOTHING_LABELS` maps ids 0-17 contiguously and `argmax` ids are always in range, so the `.get(…, "unknown")` DEFAULT is unreachable — `"UNKNOWN"`, `"XXunknownXX"`, `None` default, default-dropped are semantic no-ops                                                                                                                                                                                   | `_50`, `_54`, `_55`                                                                        |
| 11  | 5   | TEST-GAP   | `format_clothing_context` / `format_batch_clothing_context`: exact output delimiters/appendages — `", ".join`→`"XX, XX".join`, `" ".join(parts)`, `"(face appears covered)"`, `"(carrying bag)"`, `"\n".join(lines)`; existing tests assert with `in`, so decoration survives                                                                                                                                                   | `x_format_clothing_context__mutmut_9`, `_18`; `x_format_batch_clothing_context__mutmut_24` |
| 12  | 4   | LOW-VALUE  | `segment_clothing`: `logger.error("Failed to segment clothing")` **text** only (`None`, case, XX)                                                                                                                                                                                                                                                                                                                               | `_146`, `_151`, `_152`                                                                     |
| 13  | 3   | LOW-VALUE  | `segment_clothing`: `exc_info` truthiness dropped on the error log (`exc_info=False`/`None`/omitted) — traceback lost, control flow unchanged                                                                                                                                                                                                                                                                                   | `_147`, `_149`, `_153`                                                                     |
| 14  | 4   | LOW-VALUE  | `load_segformer_model`: `extra={"model_path": …}` dropped or renamed — `extra=None`, `extra` kwarg deleted (`_39`), `"MODEL_PATH"`, `"XXmodel_pathXX"`                                                                                                                                                                                                                                                                          | `x_load_segformer_model__mutmut_36`, `_39`, `_44`                                          |
| 15  | 3   | LOW-VALUE  | `load_segformer_model`: `exc_info=True` → `None`/`False`/deleted on the load-failure log — traceback lost, control flow unchanged                                                                                                                                                                                                                                                                                               | `x_load_segformer_model__mutmut_35`, `_38`, `_43`                                          |
| 16  | 6   | EQUIVALENT | Pure-text trailing-comma / arg-list-closure removals — the parsed call is byte-for-byte the same: `processor(images=person_crop, )` `_6`, `np.unique(predicted_mask, )` `_37`, `round(coverage * 100, )` `_67`, `round(current + coverage * 100, )` `_91`, `coverage_percentages.pop(label, )` `_98`, `segment_clothing(model, processor, crop, )` batch-`_11`                                                                  | `x_segment_clothing__mutmut_6`, `_91`; `x_segment_clothing_batch__mutmut_11`               |
| 17  | 3   | EQUIVALENT | `segment_clothing`: `zip(…, strict=True)` → `False`/`None`/omitted — `np.unique(…, return_counts=True)` always returns equal-length arrays, so the strict check can never fire                                                                                                                                                                                                                                                  | `_43`, `_46`, `_47`                                                                        |
| 18  | 2   | LOW-VALUE  | `segment_clothing`: timeout tuning only — `timeout=15.0` → `16.0`/`None`; no test asserts the bound and the 15 s timeout branch is never exercised                                                                                                                                                                                                                                                                              | `_139`, `_145`                                                                             |
| 19  | 2   | TEST-GAP   | `load_segformer_model`: processor construction — `processor = None`, `from_pretrained(None)`; `test_load_segformer_model_success_cuda:476` asserts the returned tuple and model kwargs but never _which_ processor came back or with what path                                                                                                                                                                                  | `x_load_segformer_model__mutmut_9`, `_10`                                                  |
| 20  | 1   | EQUIVALENT | `segment_clothing`: `coverage_percentages.get("face", 0.0)` default → `1.0`; the default applies only when face coverage is below `min_coverage` (1 %), and 0.0 and 1.0 are both `< 5.0`, so `has_face_covered` is unchanged in every reachable state                                                                                                                                                                           | `_118`                                                                                     |

## Cluster notes

- **Clusters 1-5, 7, 9 (the `segment_clothing` core, 125 survivors)** share one root cause: no test
  asserts anything about the _value_ `segment_clothing` returns on its success path. One value-
  asserting harness (drafted below) kills all of them. Deliberately **not** `MagicMock`ing numpy —
  the current harness's mocked `np.unique` is what lets arithmetic mutants through (a `MagicMock`
  absorbs `round(x*101, 3)` without complaint). Real numpy + a minimal logits stand-in makes every
  arithmetic mutant observable.
- **Cluster 2 (`segformer_loader.py:266-275`)** — shoe consolidation is a three-part contract: add
  `"shoes"` to items, SUM both shoes into `coverage_percentages["shoes"]`, `pop()` the individual
  `left_shoe`/`right_shoe` entries. No test asserts any part. `_84` (`get("shoes", 1.0)`) is a real
  numeric bug — a phantom +1.0 point on the first shoe propagates through the sum (28.12 → 29.13);
  `_92` (subtract) yields **negative** coverage `-28.12`; `_96/_97` leave stale `left_shoe`/
  `right_shoe` entries in the dict sent to the LLM prompt.
- **Cluster 3 (`:277-285`)** — `_121` turns the documented rule `sunglasses AND (head_covering OR
face_coverage < 5 %)` into `… AND face_coverage < 5 %`: sunglasses + hat with a visible face stops
  being flagged face-covered. `_104` (or→and) requires hat AND scarf. `_110` makes EVERY bare-face
  person (no hat/scarf) head-covered. These are the module's security headline features and no
  existing test executes the expression.
- **Cluster 4 (`:249-263`)** — `_38`/`_35` (`return_counts=False/None`) are input-validation misses:
  `np.unique` returns a bare array, which unpacks into `unique_classes = counts = <ndarray>`; the
  `zip` then pairs class ids with _mask values_ instead of counts — plausible-but-wrong output,
  never an error. `_29` (`predicted_mask = None`) is masked by the blanket `except`. `_68` (`/100`)
  reports percentages 10 000× small; `_69`/`_94` (`*101`) +6 % skew; `_70`/`_95` (ndigits 3) break
  the 2-dp contract `test_coverage_percentages_float_precision:1087` asserts only on the
  _dataclass_. **Kill design**: the shoe fixture uses 9+9 px of 64 so nd-3 (14.062/28.124) and
  `*101` (14.2) genuinely differ from the real 14.06/28.12 — integer-percentage masks would hide
  those three (e.g. `round(9.0, 3) == 9.0`).
- **Cluster 5 (`:258-262`)** — `_62` (`>=`→`>`) is the exact-boundary case: with total=100 and
  count=1, `1/100 == 0.01` is exactly true in IEEE and the mutant silently drops the class.
  `_58` (`and`→`or`) admits background + sub-threshold classes; `_59` inverts the background
  exclusion entirely; `_51` (`get("unknown")`) rebinds the dict's _key_, yielding `label=None` for
  every class (background guard passes, no items added). `_44/_45` (zip arg drops) crash → empty
  result → caught only by value assertions.
- **Cluster 8 (`:334-335`)** — `test_segment_clothing_batch_with_custom_min_coverage:1037` passes
  `min_coverage=0.05` but asserts only `len(results) == 1`, so `_7` (min_coverage→None), `_10`
  (dropped) and positional shifts `_8`/`_9` are unobserved.
- **Cluster 11 (`format_*`)** — two exact-equality assertions (drafted) kill all five; existing
  tests are substring checks (`:202-204`, `:230`, `:394`) that cannot see `"XX, XX".join`,
  `"XX XX".join` or `"XX\nXX".join`.
- **Clusters 6, 12-15, 18 (27 log/timeout mutants, LOW-VALUE)** — `load_segformer_model`'s four
  tests already `pytest.raises(match=…)` the _exception_ strings, which killed 26 of its 46; what
  survives is the `logger.*` payload only. Log wording is a legitimate non-goal; `exc_info=False`
  and `extra=None` do remove operator-visible data but nothing call-reachable. Recommend NOT
  writing per-mutant log tests; if the baseline wants them killed, one `caplog` helper (pattern at
  `backend/tests/unit/services/test_event_broadcaster.py:27`) covers all 27 in ~10 lines.
- **Clusters 10, 16, 17, 20 (14 EQUIVALENT)** — true semantic no-ops (unreachable dict default,
  trailing-comma text, never-firing `zip(strict=)`, default value below the gate). Permanent
  baseline noise: mark `skip` in the WP4.4 suppression list; do not chase tests for these.

## Drafted tests (clusters 1-5, 7-9, 11, 19)

**UNVERIFIED — not yet run red/green.** Style follows the existing file (module-level functions,
`monkeypatch.setitem(sys.modules, …)`, `@pytest.mark.asyncio`; repo runs `asyncio_mode="auto"`).
Append after `test_segment_clothing_min_coverage_filter` at `test_segformer_loader.py:1009`.

```python
# =============================================================================
# WP4.4: segment_clothing value assertions (mutation-feed clusters 1-5, 7, 9)
# UNVERIFIED - not yet run red/green
# =============================================================================


def _flat_mask(counts_by_id: dict[int, int]):
    """Build a flat int64 mask with exactly counts_by_id[class_id] pixels of each class."""
    import numpy as np

    return np.concatenate(
        [np.full(count, class_id, dtype=np.int64) for class_id, count in counts_by_id.items()]
    ).reshape(1, -1)


@pytest.fixture
def seg_mocks(monkeypatch):
    """Mock only torch + model/processor; let REAL numpy compute coverage.

    Real numpy is what makes arithmetic mutants (round/*101/ndigits/subtract) observable -
    a MagicMock numpy absorbs them silently, which is exactly why the existing harness
    (test_segformer_loader.py:849) lets 152 segment_clothing mutants survive.
    """
    import sys

    class _ArgmaxResult:
        def __init__(self, mask):
            self.mask = mask

        def squeeze(self):
            return self

        def cpu(self):
            return self

        def numpy(self):
            return self.mask

    class _Logits:
        def __init__(self, mask):
            self.mask = mask

        def argmax(self, dim):
            assert dim == 1, f"argmax must reduce the class axis: got dim={dim}"
            return _ArgmaxResult(self.mask)

    mock_torch = MagicMock()
    no_grad = MagicMock()
    no_grad.__enter__ = MagicMock(return_value=None)
    no_grad.__exit__ = MagicMock(return_value=None)
    mock_torch.inference_mode.return_value = no_grad
    mock_torch.no_grad.return_value = no_grad
    monkeypatch.setitem(sys.modules, "torch", mock_torch)

    mock_model = MagicMock()
    mock_model.parameters.return_value = iter([MagicMock(device="cuda:0")])
    mock_outputs = MagicMock()

    mock_pixel_values = MagicMock()
    moved = MagicMock(device="cuda:0")

    def _to(device):
        assert device == "cuda:0", f"inputs moved to wrong device: {device!r}"
        return moved

    mock_pixel_values.to.side_effect = _to
    mock_processor = MagicMock()
    mock_processor.return_value = {"pixel_values": mock_pixel_values}

    mock_image = MagicMock()
    mock_image.size = (224, 112)  # (width, height): interpolate size must arrive (112, 224)

    def install(counts_by_id: dict[int, int]):
        """Install a mask; returns (mask, logits) so tests can assert the call graph."""
        mask = _flat_mask(counts_by_id)
        logits = _Logits(mask)
        mock_outputs.logits = logits
        mock_torch.nn.functional.interpolate.side_effect = lambda *a, **k: logits
        return mask, logits

    return {
        "install": install,
        "model": mock_model,
        "processor": mock_processor,
        "image": mock_image,
        "torch": mock_torch,
        "pixel_values": mock_pixel_values,
    }


@pytest.mark.asyncio
async def test_segment_clothing_reports_items_and_coverage(seg_mocks):
    """Full value assertions on the success path (kills clusters 2, 4, 5, 7, 9)."""
    seg_mocks["install"]({0: 55, 1: 9, 4: 10, 6: 15, 16: 5, 11: 6})  # 100 px total

    result = await segment_clothing(seg_mocks["model"], seg_mocks["processor"], seg_mocks["image"])

    assert result.clothing_items == {"hat", "upper_clothes", "pants", "bag"}
    assert result.coverage_percentages == {
        "hat": 9.0, "upper_clothes": 10.0, "pants": 15.0, "bag": 5.0, "face": 6.0,
    }
    assert "background" not in result.coverage_percentages
    assert result.has_bag is True
    assert result.has_face_covered is False  # no sunglasses
    assert result.raw_mask is not None


@pytest.mark.asyncio
async def test_segment_clothing_consolidates_shoes(seg_mocks):
    """Both shoes merge into one item and one SUMMED percentage; individual keys are popped."""
    seg_mocks["install"]({0: 46, 9: 9, 10: 9})  # 64 px; kills nd-3 and *101 too

    result = await segment_clothing(seg_mocks["model"], seg_mocks["processor"], seg_mocks["image"])

    assert result.clothing_items == {"shoes"}
    assert result.coverage_percentages == {"shoes": 28.12}  # round(14.06 + 14.0625, 2)
    assert "left_shoe" not in result.coverage_percentages
    assert "right_shoe" not in result.coverage_percentages


@pytest.mark.asyncio
async def test_segment_clothing_at_exact_min_coverage_boundary(seg_mocks):
    """1 px of 100 = 0.01 == default min_coverage exactly: class must be KEPT (kills >= -> >)."""
    seg_mocks["install"]({0: 99, 16: 1})

    result = await segment_clothing(seg_mocks["model"], seg_mocks["processor"], seg_mocks["image"])

    assert result.has_bag is True
    assert result.coverage_percentages == {"bag": 1.0}


@pytest.mark.asyncio
async def test_segment_clothing_below_min_coverage_is_dropped(seg_mocks):
    """Sub-threshold classes are invisible (kills the and->or gate flip and background leak)."""
    seg_mocks["install"]({0: 999, 16: 1})  # 1/1000 = 0.001 < 0.01

    result = await segment_clothing(seg_mocks["model"], seg_mocks["processor"], seg_mocks["image"])

    assert result.clothing_items == set()
    assert result.coverage_percentages == {}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("counts", "expected_items", "expected_face", "expected_bag"),
    [
        # sunglasses + hat, face AT the 5.0 boundary -> covered via the head-covering branch
        # (kills _121 or->and flip: forces False here)
        ({0: 80, 3: 9, 1: 6, 11: 5}, {"sunglasses", "hat"}, True, False),
        # sunglasses + scarf -> covered (kills XXhat/HAT/_104 or->and/_116/_117 face-key flips)
        ({0: 85, 3: 9, 17: 6}, {"sunglasses", "scarf"}, True, False),
        # sunglasses + hat, high face visibility -> still covered
        ({0: 40, 3: 9, 1: 5, 11: 45}, {"sunglasses", "hat"}, True, False),
        # sunglasses, face exactly 5.0, NO head covering -> NOT covered (strict <)
        # (kills _122 <= flip, _123 <6.0 flip, _110 scarf-not-in flip: all force True here)
        ({0: 86, 3: 9, 11: 5}, {"sunglasses"}, False, False),
        # sunglasses + low face visibility, no head covering -> covered
        ({0: 87, 3: 9, 11: 4}, {"sunglasses"}, True, False),
        # sunglasses, face class ABSENT -> default 0.0 < 5 -> covered
        # (kills face_coverage=None / get("face", None): comparison crashes -> empty result -> False)
        ({0: 91, 3: 9}, {"sunglasses"}, True, False),
        # hat alone -> not covered (kills _120 has_sunglasses-or flip: forces True there)
        ({0: 80, 1: 20}, {"hat"}, False, False),
        # bag flags (kills BAG/XXbag/`not in`/None has_bag variants; also _134/_135 kwarg drops)
        ({0: 50, 16: 50}, {"bag"}, False, True),
    ],
)
async def test_segment_clothing_face_covered_and_bag_flags(
    seg_mocks, counts, expected_items, expected_face, expected_bag
):
    """Exercises the REAL has_face_covered / has_bag expressions (kills cluster 3)."""
    seg_mocks["install"](counts)

    result = await segment_clothing(seg_mocks["model"], seg_mocks["processor"], seg_mocks["image"])

    assert result.clothing_items == expected_items
    assert result.has_face_covered is expected_face
    assert result.has_bag is expected_bag


@pytest.mark.asyncio
async def test_segment_clothing_drives_model_with_crop_on_model_device(seg_mocks):
    """Pipeline-forwarding assertions (kills cluster 1)."""
    _mask, logits = seg_mocks["install"]({0: 84, 1: 16})

    result = await segment_clothing(seg_mocks["model"], seg_mocks["processor"], seg_mocks["image"])
    assert result.coverage_percentages == {"hat": 16.0}  # guard: pipeline actually ran

    seg_mocks["processor"].assert_called_once_with(
        images=seg_mocks["image"], return_tensors="pt"
    )
    seg_mocks["model"].assert_called_once()
    call = seg_mocks["model"].call_args
    assert call.args == ()
    assert list(call.kwargs) == ["pixel_values"]
    seg_mocks["pixel_values"].to.assert_called_once_with("cuda:0")
    interp = seg_mocks["torch"].nn.functional.interpolate.call_args
    assert interp.args == (logits,)  # kills logits=None / outputs=None variants
    assert interp.kwargs["size"] == (112, 224)  # person_crop.size (224,112) reversed -> (h, w)
    assert interp.kwargs["mode"] == "bilinear"
    assert interp.kwargs["align_corners"] is False


@pytest.mark.asyncio
async def test_segment_clothing_result_carries_computed_values(seg_mocks):
    """Every result field must hold the computed value, not a default (kills clusters 7, 9)."""
    mask, _logits = seg_mocks["install"]({0: 84, 1: 16})

    result = await segment_clothing(seg_mocks["model"], seg_mocks["processor"], seg_mocks["image"])

    assert result.raw_mask is not None
    assert result.raw_mask.tolist() == mask.tolist()
    assert result.clothing_items == {"hat"}
    assert result.has_face_covered is False
    assert result.has_bag is False
    assert result.to_dict()["clothing_items"] == ["hat"]
```

Batch forwarding (kills cluster 8) — add next to
`test_segment_clothing_batch_with_custom_min_coverage:1037`:

```python
@pytest.mark.asyncio
async def test_segment_clothing_batch_forwards_all_arguments(monkeypatch):
    """segment_clothing_batch must forward model, processor, crop AND min_coverage per crop."""
    import backend.services.segformer_loader as segformer_loader

    calls = []

    async def fake_segment(model, processor, person_crop, min_coverage):
        calls.append((model, processor, person_crop, min_coverage))
        return ClothingSegmentationResult(clothing_items={"hat"})

    monkeypatch.setattr(segformer_loader, "segment_clothing", fake_segment)

    model, processor = MagicMock(), MagicMock()
    crop_a, crop_b = MagicMock(), MagicMock()

    results = await segment_clothing_batch(model, processor, [crop_a, crop_b], min_coverage=0.05)

    assert calls == [
        (model, processor, crop_a, 0.05),
        (model, processor, crop_b, 0.05),
    ]
    assert [r.clothing_items for r in results] == [{"hat"}, {"hat"}]
```

Exact-string format assertions (kill cluster 11) — append near
`test_format_clothing_context_sorted:248` and the batch section at `:396`:

```python
def test_format_clothing_context_exact_string():
    """Exact output, not substring containment (kills delimiter/appendage mutants)."""
    result = ClothingSegmentationResult(
        clothing_items={"hat", "pants"}, has_face_covered=True, has_bag=True
    )

    assert (
        format_clothing_context(result)
        == "Clothing: hat, pants (face appears covered) (carrying bag)"
    )


def test_format_batch_clothing_context_exact_string():
    """Exact multi-line join: two-space bullet, ID/index labels, one newline between rows."""
    results = [
        ClothingSegmentationResult(clothing_items={"pants"}, has_bag=True),
        ClothingSegmentationResult(),  # skipped
        ClothingSegmentationResult(clothing_items={"hat"}, has_face_covered=True),
    ]

    assert format_batch_clothing_context(results, ["a1"]) == (
        "  - Person a1: Clothing: pants (carrying bag)\n"
        "  - Person 3: Clothing: hat (face appears covered)"
    )
```

Cluster 19 is a two-line append to the existing `test_load_segformer_model_success_cuda:476`
(after `assert len(result) == 2`):

```python
    assert result[1] is mock_processor  # kills `processor = None`
    mock_transformers.SegformerImageProcessor.from_pretrained.assert_called_once_with(
        "/test/model/cuda"
    )  # kills `from_pretrained(None)`
```

### TDD procedure (one line)

Run each drafted test against the mutated copy: it must FAIL red on its target mutant
(e.g. `_121` → `has_face_covered` False in param case 1; `_84` → shoe sum 29.13 ≠ 28.12;
`_62` → `coverage_percentages == {}` in the boundary test; `_28` → `align_corners is True`) and
PASS green against the unmodified `backend/services/segformer_loader.py`; then re-run the module's
mutant keys and confirm the cluster flips from exit 0 to exit 1.

## Verification caveats (UNVERIFIED by design — no test execution in this triage)

1. Mutations that break the mock graph raise `TypeError`/`AssertionError` inside `_segment`; the
   module's blanket `except Exception` converts those to empty results — the _value_ assertions
   still fail (that IS the kill), reported as assertion failures rather than crashes. The
   `pixel_values.to` side-effect deliberately asserts on a wrong device so `_9`/`_12` (device→None)
   die deterministically. `argmax(self, dim)` keyword enforcement mirrors the real call site
   (`:249`, `argmax(dim=1)`); `interpolate`'s kwargs (`size`/`mode`/`align_corners`, `:241-246`)
   arrive as kwargs, so `call_args.kwargs` unpacking is safe. Mutants `_18/_22` (mode None/deleted)
   fail via `interp.kwargs["mode"]` KeyError on the mutant — correct red behaviour, green has it.
2. Real numpy stays unpatched: `import numpy as np` inside `_segment` (`:221`) resolves through
   `sys.modules`, which the fixture does not touch (only `torch` is stubbed). If a future conftest
   stubs numpy globally, re-import the real module in `install()`.
3. Expected values are hand-exact through the two-step rounding the code performs:
   `round(9/64*100, 2) = 14.06`, then `round(14.06 + 14.0625, 2) = 28.12`; `1/100 == 0.01`
   boundary is exactly representable-comparison true. A 0.01 drift on the first green run means
   adjusting the constant to the true two-step value, not loosening the assert.
4. `test_segment_clothing_batch_forwards_all_arguments` patches the module attribute
   `segformer_loader.segment_clothing`; `segment_clothing_batch` resolves it by global name at call
   time (`:335`), so `monkeypatch.setattr` on the module works. If WP4.4 refactors to a local
   alias, patch that instead.
5. Do NOT expect cluster 16 (trailing-comma text mutants) or clusters 10/17/20 to flip to killed —
   they are semantic no-ops; they should go to the suppression list instead.
