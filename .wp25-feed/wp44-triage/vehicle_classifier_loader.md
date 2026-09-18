# WP4.4 Triage Dossier — backend/services/vehicle_classifier_loader.py

- **Survivors:** 116 / 327 keys (exit_code 0)
- **Per-function:** load_vehicle_classifier 63 · classify_vehicles_batch 39 · format_vehicle_classification_context 13 · VehicleClassificationResult.to_context_string 1
- **Diff source:** `uv run mutmut show <key>` cross-checked against offline diffs of the clobbered variant copies in `mutants/backend/services/vehicle_classifier_loader.py` (both agree on the sampled keys).
- **Covering test file (primary):** `backend/tests/unit/services/test_vehicle_classifier_loader.py`
  - load: lines 329, 366, 397, 441, 498, 557 · batch: 755, 769, 790, 866 · format: 241, 257, 274, 292, 308, 995 · to_context_string: 188, 205, 222
  - Secondary (to_dict/to_context_string only, substring/field asserts): `backend/tests/unit/services/test_enrichment_pipeline.py`, `backend/tests/unit/services/test_enrichment_data_consistency.py`

## Why so many survive (root cause)

The load/batch success tests mock `torch`/`torchvision` with bare `MagicMock`s and then assert only "the dict has keys / the result is the expected type / vehicle_type". Every argument to `torch.load`, `nn.Linear`, `Compose`/`Resize`/`Normalize`, `stack`, `.to(device)`, `model(...)`, `softmax(...)` and every result *field* except `vehicle_type`/`is_commercial` is never asserted, so all arg-mutation mutants are invisible. The string-formatting tests assert with `in` (substring), so any XX-wrapped or case-changed output that still contains the pinned substring survives. Boundary comparisons (`< 0.6`, `len > 1|2`) are never probed at the boundary values.

## Cluster table

Keys abbreviated: prefix `backend.services.vehicle_classifier_loader.` omitted; `#N` = `__mutmut_N` in the named function.

| # | Pattern | N | Keys | Class | Note |
|---|---------|---|------|-------|------|
| A | `validate_model_path(must_exist=True)` weakened (None/removed/False) — NEM-4501 path-existence gate | 3 | load#3, load#6, load#7 | **TEST-GAP** | Security-relevant. Tests only ever pass existing tmp dirs, so the gate's failure branch (`RuntimeError("Invalid model path")`) is never executed. Draft T1. |
| B | `classes.txt` filename constant mutated (`"XXclasses.txtXX"`, `"CLASSES.TXT"`) | 2 | load#14, load#15 | **TEST-GAP** | Success test writes classes.txt with the *same* content as the fallback list, so a broken lookup silently falls back and still sees 11 classes. Draft T2 reads custom content. |
| C | Pure log-message text mutations (`logger.info/warning` msgs → None/XX/case) | 16 | load#8,19,20,21,47–54,80,81,82,83 | EQUIVALENT | Log text only, no control flow. |
| D | `model.fc` rebuild unasserted (`num_ftrs=None`, `model.fc=None`, `Linear` arg swaps/removals) | 6 | load#23–28 | **TEST-GAP** | `Linear` is a mock; nobody asserts its call args or that `model.fc` was replaced. Draft T2. |
| E | `FileNotFoundError("Model weights not found…")` message → None | 1 | load#34 | LOW-VALUE | Error type & wrapper message unchanged; only inner diagnostic text lost. |
| F | Weight-loading call contract unasserted: `torch.load(...)` args (incl. **`weights_only=True` = NEM-4519**, map_location, first-arg removal, case/XX tweaks) + `state_dict=None` + `load_state_dict(None)` | 11 | load#35–45 (35,36,37,38,39,40,41,42,43,44,45) | **TEST-GAP** | Highest-value gap in the module: #41 (weights_only dropped) and #44 (`weights_only=False`) re-enable arbitrary-pickle loading; tests use `MagicMock().load` so anything passes. Draft T2. |
| H | Image-transform pipeline unasserted (`transform=None`, `Compose(None)`, `Resize((225,224))`, Normalize mean/std tweaks) | 15 | load#55–69 | **TEST-GAP** | `Compose/Resize/Normalize` mocked, call args never checked; wrong resize/normalize silently corrupts inference. Draft T3. |
| I | ImportError message prefix tweaks (`"XX…XX"`, lowercase) | 2 | load#85, load#86 | LOW-VALUE | Existing `match="torch and torchvision"` still contained; wording is not assert-worthy. |
| J | `logger.error(...)` message / `exc_info` mutations in load error path | 7 | load#88,89,91,92,93,94,95 | LOW-VALUE | Traceback-in-log only; wrapper `RuntimeError` unchanged and asserted. |
| K1 | RGB conversion broken invisibly (`rgb_img=None`, `… and False`, `convert(None)`, `!=`→`==`) | 4 | batch#13,14,16,19 | **TEST-GAP** | `transform` is a mock so it never checks it received an RGB-mode image. Draft T4 uses an RGBA image + arg-mode assert. |
| K2 | RGB predicate made always-true (`or True`, `"XXRGBXX"`, `"rgb"`) | 3 | batch#15,20,21 | EQUIVALENT | `convert("RGB")` on an RGB image is a pixel-identical copy; output mode/data unchanged for every input. |
| L | Tensor prep contract unasserted (`append(None)`, `transform(None)`, `stack(None)`) | 3 | batch#22,23,25 | **TEST-GAP** | Draft T4 (call-count + call-args). |
| M | Device movement unasserted (`device=None`, `batch=None`, `.to(None)`) | 3 | batch#26,28,29 | **TEST-GAP** | Draft T4 (`.to(device)` args, model call arg). |
| N | Model invocation unasserted (`outputs=None`, `model(None)`) | 2 | batch#30,31 | **TEST-GAP** | Draft T4 (`model.assert_called_once_with(moved)`). |
| O | `softmax(outputs, dim=-1)` args mutated incl. `dim=-2` (batch-vs-class axis flip, real semantic bug) | 6 | batch#33,34,35,36,37,38 | **TEST-GAP** | Softmax return is a fixed mock so arg changes are invisible. Draft T4. |
| P | Batch result **field values** unasserted: `confidence` (None / second-place / kwarg None), `all_scores` (None), `display_name` (None / wrong key / fallback-default removal) | 11 | batch#58,59,61,63,64,65,66,67,72,73,75 | **TEST-GAP** | Success test asserts only vehicle_type + is_commercial. #65–67 only observable via a class outside `VEHICLE_DISPLAY_NAMES` → custom `classes` list. Draft T5. |
| Q | `logger.error(...)` message / `exc_info` mutations in batch error path | 7 | batch#84,85,87,88,89,90,91 | LOW-VALUE | Same as J. |
| R | Output string changed but only substring-asserted (XX-markers, `"XX\nXX".join`, to_context_string marker) | 3 | to_context_string#5, format#3, format#33 | **TEST-GAP** | Tests use `"Commercial/delivery vehicle" in formatted`. Draft T6 full-string equality. |
| S | Alternative-block boundary probes missing (`< 0.6`→`<= 0.6`; inner `len > 1`→`> 2`) | 2 | format#8, format#23 | **TEST-GAP** | No fixture at confidence exactly 0.6 or with exactly 2 scores below 0.6. Draft T6. |
| T | Redundant-guard tweaks (`len(all_scores) > 1`→`>= 1` at outer/inner where the other guard dominates) | 3 | format#10, format#11, format#22 | EQUIVALENT | Outer & inner guards re-check the same dict; each mutation is masked by the surviving guard (or unreachable). |
| U | Sort direction flipped (`reverse=True`→None/False/removed) — existing test's 3-score dict has the same middle element in both directions, hiding the bug | 3 | format#15,18,21 | **TEST-GAP** | Killed by a 4-score fixture where 2nd-highest ≠ 2nd-lowest. Draft T6. |
| V | Alternative display-name fallback default removed (`get(alt_type, alt_type)`→`get(alt_type[, None])`) | 3 | format#28,29,30 | **TEST-GAP** | Only observable when the alternative class is outside `VEHICLE_DISPLAY_NAMES`. Draft T6. |

**Totals (verified against the meta JSON, per-function: load 63 = 3+2+16+6+1+11+15+2+7; batch 39 = 4+3+3+3+2+6+11+7; format+to_context_string 14 = 3+2+3+3+3):**

| Classification | Clusters | Count |
|---|---|---|
| TEST-GAP | A, B, D, F, H, K1, L, M, N, O, P, R, S, U, V | **77** |
| EQUIVALENT | C, K2, T | **22** |
| LOW-VALUE | E, I, J, Q | **17** |
| | | **116** |

## Drafted tests (UNVERIFIED — not yet run red/green)

TDD procedure for each: apply the cluster's mutant (or read its diff), run the new test → expect FAIL on mutant; run on original → expect PASS. Style follows `backend/tests/unit/services/test_vehicle_classifier_loader.py`.

### T1 — kills cluster A (`test_load_vehicle_classifier_rejects_nonexistent_model_path`)

```python
@pytest.mark.asyncio
async def test_load_vehicle_classifier_rejects_nonexistent_model_path(monkeypatch, tmp_path):
    """NEM-4501: a nonexistent model path must fail the path-validation gate."""
    import sys

    # torch/torchvision must import cleanly so execution reaches validate_model_path
    monkeypatch.setitem(sys.modules, "torch", MagicMock())
    monkeypatch.setitem(sys.modules, "torchvision", MagicMock())
    monkeypatch.setitem(sys.modules, "torchvision.models", MagicMock())
    monkeypatch.setitem(sys.modules, "torchvision.transforms", MagicMock())

    missing = tmp_path / "no-such-model-dir"
    with pytest.raises(RuntimeError, match="Invalid model path"):
        await load_vehicle_classifier(str(missing))
```

On mutants A (`must_exist` weakened), validation passes, loading proceeds and dies later with `RuntimeError("Failed to load …")` → match fails → red. Original raises "Invalid model path" → green.

Discriminator validity: `validate_model_path` (backend/core/security.py:68) checks the directory allowlist BEFORE `must_exist` (line 162); `/tmp` is in `DEFAULT_ALLOWED_MODEL_DIRECTORIES` (security.py:47) and pytest's `tmp_path` resolves under `/tmp/pytest-*`, so the mutant path passes every earlier gate and only the existence check separates mutant from original.

### T2 — kills clusters F, D, B (`test_load_vehicle_classifier_weight_loading_contract`)

```python
@pytest.mark.asyncio
async def test_load_vehicle_classifier_weight_loading_contract(monkeypatch, tmp_path):
    """NEM-4519: weights load with weights_only=True from the real file, state dict
    flows to load_state_dict, fc is rebuilt with the real feature/class counts, and
    classes.txt (exact filename) is actually read."""
    import sys

    model_dir = tmp_path / "model"
    model_dir.mkdir()
    weights = model_dir / "pytorch_model.bin"
    weights.write_bytes(b"fake weights")
    # Content deliberately DIFFERENT from VEHICLE_SEGMENT_CLASSES so a broken
    # filename lookup (which falls back to the defaults) is observable.
    (model_dir / "classes.txt").write_text("car\nspaceship")

    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    loaded_state = {"fc.weight": 1}
    mock_torch.load.return_value = loaded_state

    mock_linear = MagicMock()
    mock_nn = MagicMock()
    mock_nn.Linear.return_value = mock_linear
    mock_torch.nn = mock_nn

    mock_model = MagicMock()
    mock_model.fc = MagicMock()
    mock_model.fc.in_features = 2048
    mock_model.eval.return_value = None
    mock_model.load_state_dict.return_value = None

    mock_models = MagicMock()
    mock_models.resnet50.return_value = mock_model

    mock_transforms = MagicMock()
    mock_transforms.Compose.return_value = MagicMock()

    mock_torchvision = MagicMock()
    mock_torchvision.models = mock_models
    mock_torchvision.transforms = mock_transforms

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "torch.nn", mock_nn)
    monkeypatch.setitem(sys.modules, "torchvision", mock_torchvision)
    monkeypatch.setitem(sys.modules, "torchvision.models", mock_models)
    monkeypatch.setitem(sys.modules, "torchvision.transforms", mock_transforms)

    result = await load_vehicle_classifier(str(model_dir))

    assert result["classes"] == ["car", "spaceship"]          # kills B
    mock_nn.Linear.assert_called_once_with(2048, 2)           # kills D
    assert mock_model.fc is mock_linear                       # kills D (model.fc=None)
    mock_torch.load.assert_called_once_with(                  # kills F arg mutants,
        weights, map_location="cpu", weights_only=True        # incl. #41/#44 security
    )
    mock_model.load_state_dict.assert_called_once_with(loaded_state)  # kills load#45
```

### T3 — kills cluster H (`test_load_vehicle_classifier_builds_standard_transform`)

```python
@pytest.mark.asyncio
async def test_load_vehicle_classifier_builds_standard_transform(monkeypatch, tmp_path):
    """Preprocessing must be the trained ResNet-50 pipeline: Resize((224,224)),
    ToTensor(), Normalize(ImageNet mean/std)."""
    import sys

    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "pytorch_model.bin").write_bytes(b"fake weights")
    (model_dir / "classes.txt").write_text("\n".join(VEHICLE_SEGMENT_CLASSES))

    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    mock_torch.load.return_value = {}
    mock_torch.nn = MagicMock()

    mock_model = MagicMock()
    mock_model.fc = MagicMock()
    mock_model.fc.in_features = 2048
    mock_models = MagicMock()
    mock_models.resnet50.return_value = mock_model

    resize = MagicMock()
    to_tensor = MagicMock()
    normalize = MagicMock()
    composed = MagicMock()
    mock_transforms = MagicMock()
    mock_transforms.Resize.return_value = resize
    mock_transforms.ToTensor.return_value = to_tensor
    mock_transforms.Normalize.return_value = normalize
    mock_transforms.Compose.return_value = composed

    mock_torchvision = MagicMock()
    mock_torchvision.models = mock_models
    mock_torchvision.transforms = mock_transforms

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "torchvision", mock_torchvision)
    monkeypatch.setitem(sys.modules, "torchvision.models", mock_models)
    monkeypatch.setitem(sys.modules, "torchvision.transforms", mock_transforms)

    result = await load_vehicle_classifier(str(model_dir))

    mock_transforms.Resize.assert_called_once_with((224, 224))
    mock_transforms.ToTensor.assert_called_once_with()
    mock_transforms.Normalize.assert_called_once_with(
        [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]
    )
    mock_transforms.Compose.assert_called_once_with([resize, to_tensor, normalize])
    assert result["transform"] is composed  # kills load#55 (transform = None)
```

### T4 — kills clusters K1, L, M, N, O (`test_classify_vehicles_batch_pipeline_contract`)

```python
@pytest.mark.asyncio
async def test_classify_vehicles_batch_pipeline_contract(monkeypatch):
    """Batch pipeline contract: transform sees RGB-mode images, tensors are stacked,
    moved to the model's device, fed to the model, and softmaxed over dim=-1."""
    import sys

    from PIL import Image

    images = [Image.new("RGB", (64, 64)), Image.new("RGBA", (64, 64))]

    mock_torch = MagicMock()
    tensor_0, tensor_1 = MagicMock(name="t0"), MagicMock(name="t1")
    mock_transform = MagicMock(side_effect=[tensor_0, tensor_1])

    stacked = MagicMock(name="stacked")
    moved = MagicMock(name="moved")
    stacked.to.return_value = moved
    mock_torch.stack.return_value = stacked

    outputs = MagicMock(name="outputs")
    device = MagicMock(name="device")
    mock_model = MagicMock()
    mock_model.parameters.return_value = iter([MagicMock(device=device)])
    mock_model.return_value = outputs

    # per-image probs (car wins) so downstream result building doesn't explode
    items = [0.01, 0.01, 0.01, 0.02, 0.80, 0.02, 0.01, 0.01, 0.05, 0.03, 0.03]

    def make_probs():
        p = MagicMock()
        p.__getitem__ = lambda _s, i: MagicMock(item=lambda: items[i])
        return p

    all_probs = MagicMock()
    all_probs.__iter__ = lambda _s: iter([make_probs(), make_probs()])
    mock_torch.nn.functional.softmax.return_value = all_probs

    monkeypatch.setitem(sys.modules, "torch", mock_torch)

    model_dict = {
        "model": mock_model,
        "transform": mock_transform,
        "classes": VEHICLE_SEGMENT_CLASSES,
    }
    await classify_vehicles_batch(model_dict, images)

    assert mock_transform.call_count == 2  # kills batch#22 (append(None) drops the call)
    for c in mock_transform.call_args_list:  # kills batch#13,16,19,23
        arg = c.args[0]
        assert isinstance(arg, Image.Image) and arg.mode == "RGB"
    mock_torch.stack.assert_called_once_with([tensor_0, tensor_1])  # kills batch#25
    stacked.to.assert_called_once_with(device)                      # kills batch#26,29
    mock_model.assert_called_once_with(moved)                       # kills batch#28,30,31
    mock_torch.nn.functional.softmax.assert_called_once_with(outputs, dim=-1)  # kills batch#33-38
```

### T5 — kills cluster P (`test_classify_vehicles_batch_result_fields`)

```python
@pytest.mark.asyncio
async def test_classify_vehicles_batch_result_fields(monkeypatch):
    """Every VehicleClassificationResult field the batch builder sets must carry the
    right value: confidence, display_name (incl. unknown-class fallback), all_scores."""
    import sys

    from PIL import Image

    mock_torch = MagicMock()
    mock_torch.stack.return_value = MagicMock()
    mock_model = MagicMock()
    mock_model.parameters.return_value = iter([MagicMock(device=MagicMock())])
    mock_transform = MagicMock()

    monkeypatch.setitem(sys.modules, "torch", mock_torch)

    def probs_for(values):
        p = MagicMock()
        p.__getitem__ = lambda _s, i: MagicMock(item=lambda: values[i])
        return p

    all_probs = MagicMock()

    # --- standard classes: car wins with 0.80 -------------------------------
    items = [0.01, 0.01, 0.01, 0.02, 0.80, 0.02, 0.01, 0.01, 0.05, 0.03, 0.03]
    all_probs.__iter__ = lambda _s: iter([probs_for(items)])
    mock_torch.nn.functional.softmax.return_value = all_probs
    (result,) = await classify_vehicles_batch(
        {"model": mock_model, "transform": mock_transform,
         "classes": VEHICLE_SEGMENT_CLASSES},
        [Image.new("RGB", (32, 32))],
    )
    assert result.vehicle_type == "car"
    assert result.confidence == 0.80            # kills batch#58,59,72
    assert result.display_name == "car/sedan"   # kills batch#63 (None), #64 (top_class)
    assert result.is_commercial is False
    assert list(result.all_scores.items()) == [  # kills batch#61,73,75
        ("car", 0.80),
        ("pickup_truck", 0.05),
        ("single_unit_truck", 0.03),
    ]

    # --- custom classes: display falls back to the raw class name ----------
    all_probs2 = MagicMock()
    all_probs2.__iter__ = lambda _s: iter([probs_for([0.30, 0.70])])
    mock_torch.nn.functional.softmax.return_value = all_probs2
    (result2,) = await classify_vehicles_batch(
        {"model": mock_model, "transform": mock_transform,
         "classes": ["car", "spaceship"]},
        [Image.new("RGB", (32, 32))],
    )
    assert result2.vehicle_type == "spaceship"
    assert result2.confidence == 0.70
    assert result2.display_name == "spaceship"  # kills batch#65,66,67 (default dropped)
    assert result2.is_commercial is False
```

### T6 — kills clusters R, S, U, V (`test_context_strings_are_exact_and_alternative_block_is_pinned`)

```python
def test_context_strings_are_exact_and_alternative_block_is_pinned():
    """Context outputs are asserted EXACTLY (not by substring), and the alternative
    block's boundaries/sort/fallback are probed at discriminating fixtures."""
    # to_context_string exact — kills to_context_string#5 (XX marker)
    r = VehicleClassificationResult(
        vehicle_type="articulated_truck", confidence=0.99,
        display_name="articulated truck (semi/18-wheeler)", is_commercial=True,
        all_scores={"articulated_truck": 0.99},
    )
    assert r.to_context_string() == (
        "Vehicle type: articulated truck (semi/18-wheeler) (99% confidence)"
        " [Commercial/delivery vehicle]"
    )

    # format: exact output incl. separator + commercial marker
    # kills format#3 (XX marker), format#33 ("XX\nXX".join)
    car = VehicleClassificationResult(
        vehicle_type="car", confidence=0.95, display_name="car/sedan",
        is_commercial=False, all_scores={"car": 0.95},
    )
    assert format_vehicle_classification_context(car) == (
        "Vehicle: car/sedan\n  Confidence: 95.0%"
    )
    van = VehicleClassificationResult(
        vehicle_type="work_van", confidence=0.88, display_name="work van/delivery van",
        is_commercial=True, all_scores={"work_van": 0.88},
    )
    assert format_vehicle_classification_context(van) == (
        "Vehicle: work van/delivery van\n  [Commercial/delivery vehicle]\n"
        "  Confidence: 88.0%"
    )

    # boundary: confidence exactly 0.6 → NO alternative line — kills format#8 (<=)
    edge = VehicleClassificationResult(
        vehicle_type="bus", confidence=0.6, display_name="bus",
        is_commercial=False, all_scores={"bus": 0.6, "car": 0.4},
    )
    assert "Alternative:" not in format_vehicle_classification_context(edge)

    # exactly TWO scores below 0.6 → alternative shown — kills format#23 (inner > 2)
    two = VehicleClassificationResult(
        vehicle_type="bus", confidence=0.5, display_name="bus",
        is_commercial=False, all_scores={"bus": 0.5, "car": 0.5},
    )
    assert "Alternative: car/sedan (50.0%)" in format_vehicle_classification_context(two)

    # sort direction: 4 scores so 2nd-highest != 2nd-lowest — kills format#15,18,21
    four = VehicleClassificationResult(
        vehicle_type="pickup_truck", confidence=0.55, display_name="pickup truck",
        is_commercial=False,
        all_scores={"pickup_truck": 0.50, "car": 0.30, "work_van": 0.15, "bus": 0.05},
    )
    assert "Alternative: car/sedan (30.0%)" in format_vehicle_classification_context(four)

    # unknown alternative class falls back to the raw type — kills format#28,29,30
    unk = VehicleClassificationResult(
        vehicle_type="pickup_truck", confidence=0.55, display_name="pickup truck",
        is_commercial=False, all_scores={"pickup_truck": 0.55, "spaceship": 0.30},
    )
    assert "Alternative: spaceship (30.0%)" in format_vehicle_classification_context(unk)
```

## WP4.4 intake notes

- Priority order for landing: **F** (weights_only security contract, NEM-4519) and **A** (path gate, NEM-4501) first — these are the two documented security invariants that currently have zero test coverage. Then T2's transform-pipeline (**H**) and the batch contract/fields (**K1,L,M,N,O,P**), then the cheap formatting exactness wins (**R,S,U,V**).
- EQUIVALENT clusters (C, K2, T, 22 mutants) can go straight to the `mutmut config` equivalent-kill whitelist style triage; LOW-VALUE (E,I,J,Q, 17 mutants) to the no-assert-worth list. Together they account for 39/116 survivors — the module's mutation score ceiling is ~23.6% without tests, ~66% if all TEST-GAP drafts land.
- Existing-test weakness to fix repo-wide in WP4.4 style guidance: `assert "X" in output` on formatted strings (kills nothing for XX/case mutants) and `MagicMock`-everything with no `assert_called_once_with` on security-relevant calls.
