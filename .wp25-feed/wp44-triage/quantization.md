# WP4.4 Triage Dossier — backend/services/quantization.py

- Survivors: **101** (meta: mutants/backend/services/quantization.py.meta; 120 killed, 43 pending)
- Covering test file (only one): `backend/tests/unit/services/test_quantization.py`
  - Key anchors: `_is_bitsandbytes_available` tests L176–221/L816–829; `get_bnb_4bit_config` L323–435; `get_bnb_8bit_config` L443–502; dynamic success/string-backend L510–581; static success L596–643; async dispatch L651–697, L1065–1117; async calibration-called L1121–1177.
- Method note: all 101 diffs pulled via `uv run mutmut show <key>` (no failures). No tests executed here.

## Why so many survivors (root pattern)

The success-path tests (test_apply_dynamic_int8_quantization_success L510, test_apply_static_int8_quantization_success L596) mock
`torch` / `torch.ao.quantization` wholesale and then assert only `isinstance(result, QuantizationResult)`,
`quantization_type`, `backend`, and `eval()`/calibration-call — never the metrics, never the call
arguments, never `result.model`. Nearly every real-behavior survivor hides in those unasserted slots.

## Cluster table (counts sum to 101)

| #   | Cluster                                                                                                                                                         | Count | Class      | Example keys (suffix of `backend.services.quantization.`) | Evidence / why                                                                                                                                                                                                                       |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----- | ---------- | --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | Compression-ratio arithmetic (`original/quant if size>0 else 1.0`): `/`→`*`, guard→`and False`/`or True`, `>0`→`>1`/`>=0`, fallback `1.0`→`2.0` — dyn+static    | 10    | TEST-GAP   | dyn**17, dyn**19, static\_\_24                            | Tests run the line but never assert `compression_ratio` (L546–551, L637–643). Killed by metric asserts + zero-size fallback test. Keys: dyn 17,19,21,22; static 21,22,23,24,25,26                                                    |
| 2   | `QuantizationResult` returned with fields set to `None` (`model=`, `original_size_mb=`, `quantized_size_mb=`, `compression_ratio=`) — dyn+static                | 8     | TEST-GAP   | dyn**24, dyn**27, static\_\_28                            | Success tests never read those fields off the result. Keys: dyn 24,25,26,27; static 28,29,30,31                                                                                                                                      |
| 3   | `quant.quantize_dynamic(...)` call contract broken: model→None / arg dropped, layers set→None/dropped, `dtype=qint8` dropped/altered                            | 6     | TEST-GAP   | dyn**8, dyn**10, dyn\_\_12                                | `mock_quant.quantize_dynamic` is a plain MagicMock — return_value set, call args never checked. Real torch would raise TypeError. Keys: dyn 8,9,10,11,12,13                                                                          |
| 4   | Static pipeline contract: `qconfig = None` / `get_default_qconfig(None)`, `prepare(None)`, `quantized_model = None` / `convert(None)`                           | 5     | TEST-GAP   | static**7, static**10, static\_\_16                       | L637–643 doesn't assert `model.qconfig`, prepare/convert args, or `result.model`. Keys: static 7,8,10,16,17                                                                                                                          |
| 5   | Async wrapper call-through args: static/dynamic called with `backend=None` / `model=None` / arg dropped/repositioned                                            | 6     | TEST-GAP   | async**12, async**20, async\_\_22                         | Async tests patch the sync functions with autospec but only assert the returned result (L663–697). Keys: async 12,15,20,21,22,23                                                                                                     |
| 6   | `_get_model_size_mb(model/quantized_model)` → `(None)` → reported sizes/ratio silently become 0.0/1.0 — dyn+static                                              | 4     | TEST-GAP   | dyn**5, dyn**15, static\_\_5                              | Same blind spot as #1/#2: the size fields are computed and stored but never asserted. Keys: dyn 5,15; static 5,19                                                                                                                    |
| 7   | `importlib.util.find_spec("bitsandbytes")` arg → `None` / `"XXbitsandbytesXX"` / `"BITSANDBYTES"`                                                               | 3     | TEST-GAP   | x**is_bitsandbytes_available**1, \_\_3                    | All 3 tests patch `find_spec` and ignore the argument (L176–221); wrong name makes the real check always report "not installed".                                                                                                     |
| 8   | Static backend plumbing: `backend_str = None` (ternary→None), `result.backend=None` / kwarg dropped                                                             | 3     | TEST-GAP   | static**1, static**33, static\_\_39                       | `result.backend` asserted only in the _dynamic_ tests (L550/L581); static success never checks it, and `torch.backends.quantized.engine` is never checked.                                                                           |
| 9   | `torch.backends.quantized.engine = backend_str` → `= None` — dyn+static                                                                                         | 2     | TEST-GAP   | dyn**6, static**6                                         | Mock backend object accepts any assignment; never asserted.                                                                                                                                                                          |
| 10  | `dtype_map` key `"float32"` → `"XXfloat32XX"` / `"FLOAT32"` in `get_bnb_4bit_config`                                                                            | 2     | TEST-GAP   | x_get_bnb_4bit_config**11, **12                           | Tests exercise float16/bfloat16 only (L334, L370); `compute_dtype="float32"` would now raise ValueError.                                                                                                                             |
| 11  | Static ternary `isinstance(...) or True` → calls `.value` on a plain str backend → AttributeError → RuntimeError                                                | 1     | TEST-GAP   | static\_\_3                                               | Dynamic has a string-backend test (L554); static has none — asymmetry is the gap.                                                                                                                                                    |
| 12  | `apply_int8_quantization_async` default `use_static: bool = False` → `True`                                                                                     | 1     | TEST-GAP   | x_apply_int8_quantization_async\_\_1                      | The calibration-data-without-static test passes `use_static=False` explicitly (L1087), so the _default_ is untested.                                                                                                                 |
| 13  | Log / raised-exception **message text** mutants (XX-wrapped, case flips, message→`None`) across `_is_bnb` guard, both bnb config fns, both INT8 fn except-paths | 42    | EQUIVALENT | 4bit**32, dyn**40, static\_\_12                           | Pure message text; exception type + already-asserted substrings (`pytest.raises(match=...)`) unchanged. Not worth asserting verbatim strings. Covers 4bit 3,4,32–36,38,39; 8bit 3,4,14–18,20,21; dyn 23,36–44; static 11–14,27,40–48 |
| 14  | `backend.value if isinstance(backend, QuantizationBackend) else backend` with `and False` appended — dyn+static                                                 | 2     | EQUIVALENT | dyn**2, static**2                                         | `QuantizationBackend` is a `str` Enum: member == `.value` (`'x86' == QB.X86` True, JSON-safe), so the skipped `.value` is unobservable.                                                                                              |
| 15  | `logger.error(..., exc_info=True)` → `None`/`False`/dropped — dyn+static except-paths                                                                           | 6     | LOW-VALUE  | dyn**45, dyn**47, static\_\_52                            | Only suppresses traceback in error logs; nobody should assert logger internals here. Keys: dyn 45,47,48; static 49,51,52                                                                                                             |

TEST-GAP 51 + EQUIVALENT 44 + LOW-VALUE 6 = 101.

## Drafted tests (highest-value clusters)

Target file: `backend/tests/unit/services/test_quantization.py` (append; same style — MagicMock torch via `monkeypatch.setitem(sys.modules, ...)`, no real torch).
**TDD procedure:** add test → run against mutant copy (expect RED at the new assert) → run against original `backend/services/quantization.py` (expect GREEN). One test run per direction, same command.

// UNVERIFIED — not yet run red/green

### D1. Metrics test (kills clusters 1-partial, 2, 6; sizes chosen <1MB so the `>1` guard mutants also die)

```python
def test_apply_dynamic_int8_quantization_reports_metrics(monkeypatch):
    """Reported sizes and compression ratio must reflect the actual models."""
    import sys

    mock_torch = MagicMock()
    mock_torch.nn.Linear = MagicMock()
    mock_torch.nn.LSTM = MagicMock()
    mock_torch.qint8 = "qint8"
    mock_torch.backends = MagicMock()
    mock_torch.float16 = "float16"
    mock_torch.int8 = "int8"

    # original: 262144 fp32 params -> exactly 1.0 MB
    orig_param = MagicMock()
    orig_param.numel.return_value = 262144
    orig_param.dtype = "float32"
    mock_original_model = MagicMock()
    mock_original_model.parameters.return_value = [orig_param]

    # quantized: 131072 fp32 params -> 0.5 MB (deliberately < 1 MB so a
    # `quantized_size > 1` guard flip changes the branch)
    quant_param = MagicMock()
    quant_param.numel.return_value = 131072
    quant_param.dtype = "float32"
    mock_quantized_model = MagicMock()
    mock_quantized_model.parameters.return_value = [quant_param]

    mock_quant = MagicMock()
    mock_quant.quantize_dynamic.return_value = mock_quantized_model
    mock_torch.ao = MagicMock()
    mock_torch.ao.quantization = mock_quant

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "torch.ao.quantization", mock_quant)

    result = apply_dynamic_int8_quantization(mock_original_model, QuantizationBackend.X86)

    assert result.model is mock_quantized_model
    assert result.original_size_mb == pytest.approx(1.0, rel=0.01)
    assert result.quantized_size_mb == pytest.approx(0.5, rel=0.01)
    assert result.compression_ratio == pytest.approx(2.0, rel=0.01)
```

### D2. Zero-size fallback (kills cluster 1 remainder: dyn**22, static**22/24/26, plus size fields on empty models)

```python
def test_int8_quantization_zero_size_fallback(monkeypatch):
    """With empty parameter sets the ratio must fall back to 1.0, not divide or use 2.0."""
    import sys

    mock_torch = MagicMock()
    mock_torch.nn.Linear = MagicMock()
    mock_torch.nn.LSTM = MagicMock()
    mock_torch.qint8 = "qint8"
    mock_torch.backends = MagicMock()
    mock_torch.no_grad = MagicMock(
        return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock())
    )

    empty_model = MagicMock()
    empty_model.parameters.return_value = []

    mock_quant = MagicMock()
    mock_quant.quantize_dynamic.return_value = empty_model
    mock_quant.get_default_qconfig.return_value = MagicMock()
    mock_quant.prepare.return_value = empty_model
    mock_quant.convert.return_value = empty_model
    mock_torch.ao = MagicMock()
    mock_torch.ao.quantization = mock_quant

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "torch.ao.quantization", mock_quant)

    dyn = apply_dynamic_int8_quantization(empty_model)
    assert dyn.original_size_mb == 0.0
    assert dyn.quantized_size_mb == 0.0
    assert dyn.compression_ratio == 1.0

    stat = apply_static_int8_quantization(empty_model, MagicMock())
    assert stat.original_size_mb == 0.0
    assert stat.quantized_size_mb == 0.0
    assert stat.compression_ratio == 1.0
```

(On `static__22`/`static__24` the zero-size case divides by zero and the call raises
RuntimeError instead of returning — the assert never runs, still RED.)

### D3. Dynamic call contract (kills cluster 3 + dyn\_\_6 of cluster 9)

```python
def test_apply_dynamic_int8_quantization_call_contract(monkeypatch):
    """quantize_dynamic must receive the real model, the Linear/LSTM set, and qint8."""
    import sys

    mock_torch = MagicMock()
    mock_torch.nn.Linear = MagicMock()
    mock_torch.nn.LSTM = MagicMock()
    mock_torch.qint8 = "qint8"
    mock_torch.backends = MagicMock()
    mock_torch.float16 = "float16"
    mock_torch.int8 = "int8"

    mock_quantized_model = MagicMock()
    mock_quantized_model.parameters.return_value = []

    mock_quant = MagicMock()
    mock_quant.quantize_dynamic.return_value = mock_quantized_model
    mock_torch.ao = MagicMock()
    mock_torch.ao.quantization = mock_quant

    mock_model = MagicMock()
    mock_model.parameters.return_value = []

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "torch.ao.quantization", mock_quant)

    apply_dynamic_int8_quantization(mock_model, QuantizationBackend.FBGEMM)

    assert mock_torch.backends.quantized.engine == "fbgemm"
    mock_quant.quantize_dynamic.assert_called_once_with(
        mock_model,
        {mock_torch.nn.Linear, mock_torch.nn.LSTM},
        dtype=mock_torch.qint8,
    )
```

### D4. Static pipeline + backend string-through (kills clusters 4, 8, 9-static, 11, 2-static, 1-static-partial)

```python
def test_apply_static_int8_quantization_pipeline(monkeypatch):
    """qconfig/prepare/convert run with the real objects, backend string flows end-to-end."""
    import sys

    mock_torch = MagicMock()
    mock_torch.no_grad = MagicMock(
        return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock())
    )
    mock_torch.backends = MagicMock()
    mock_torch.float16 = "float16"
    mock_torch.int8 = "int8"

    orig_param = MagicMock()
    orig_param.numel.return_value = 262144
    orig_param.dtype = "float32"
    mock_original_model = MagicMock()
    mock_original_model.parameters.return_value = [orig_param]

    quant_param = MagicMock()
    quant_param.numel.return_value = 131072
    quant_param.dtype = "int8"  # mock_torch.int8 -> 1 byte -> 0.125 MB

    mock_prepared = MagicMock()
    mock_converted = MagicMock()
    mock_converted.parameters.return_value = [quant_param]

    mock_qconfig = MagicMock()
    mock_quant = MagicMock()
    mock_quant.get_default_qconfig.return_value = mock_qconfig
    mock_quant.prepare.return_value = mock_prepared
    mock_quant.convert.return_value = mock_converted
    mock_torch.ao = MagicMock()
    mock_torch.ao.quantization = mock_quant

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "torch.ao.quantization", mock_quant)

    calibration_fn = MagicMock()
    result = apply_static_int8_quantization(mock_original_model, calibration_fn, "qnnpack")

    assert mock_original_model.qconfig is mock_qconfig
    mock_quant.get_default_qconfig.assert_called_once_with("qnnpack")
    assert mock_torch.backends.quantized.engine == "qnnpack"
    mock_quant.prepare.assert_called_once_with(mock_original_model)
    calibration_fn.assert_called_once_with(mock_prepared)
    mock_quant.convert.assert_called_once_with(mock_prepared)

    assert result.model is mock_converted
    assert result.original_size_mb == pytest.approx(1.0, rel=0.01)
    assert result.quantized_size_mb == pytest.approx(0.125, rel=0.01)
    assert result.compression_ratio == pytest.approx(8.0, rel=0.01)
    assert result.backend == "qnnpack"
```

(The string `"qnnpack"` kills `static__3`: `str.value` raises → RuntimeError → RED.
`static__21` (`and False`) and `static__23`/`static__25` die on the ratio assert.)

### D5. Async call-through + default routing (kills clusters 5 and 12)

```python
@pytest.mark.asyncio
async def test_apply_int8_quantization_async_passes_model_and_backend():
    """The async wrapper must hand model+backend through to the chosen sync fn."""
    mock_result = QuantizationResult(
        model=MagicMock(),
        original_size_mb=100.0,
        quantized_size_mb=25.0,
        compression_ratio=4.0,
        quantization_type=QuantizationType.INT8,
        backend="qnnpack",
    )
    model = MagicMock()

    with patch(
        "backend.services.quantization.apply_dynamic_int8_quantization",
        return_value=mock_result,
        autospec=True,
    ) as mock_dynamic:
        result = await apply_int8_quantization_async(
            model, backend=QuantizationBackend.QNNPACK
        )

    assert result == mock_result
    mock_dynamic.assert_called_once_with(model, QuantizationBackend.QNNPACK)


@pytest.mark.asyncio
async def test_apply_int8_quantization_async_static_routing_and_defaults():
    """use_static defaults to False; when True, (model, calibration_fn, backend) flow through."""
    mock_result = QuantizationResult(
        model=MagicMock(),
        original_size_mb=100.0,
        quantized_size_mb=25.0,
        compression_ratio=4.0,
        quantization_type=QuantizationType.INT8,
        backend="qnnpack",
    )
    model = MagicMock()

    with (
        patch(
            "backend.services.quantization.apply_dynamic_int8_quantization",
            return_value=mock_result,
            autospec=True,
        ) as mock_dynamic,
        patch(
            "backend.services.quantization.apply_static_int8_quantization",
            return_value=mock_result,
            autospec=True,
        ) as mock_static,
    ):
        # calibration_data alone must NOT switch to static (default use_static=False)
        await apply_int8_quantization_async(
            model, calibration_data=[MagicMock()], backend=QuantizationBackend.QNNPACK
        )
        mock_dynamic.assert_called_once_with(model, QuantizationBackend.QNNPACK)
        mock_static.assert_not_called()

        # explicit static: backend must be forwarded unchanged
        await apply_int8_quantization_async(
            model,
            calibration_data=[MagicMock()],
            backend=QuantizationBackend.QNNPACK,
            use_static=True,
        )
    assert mock_static.call_count == 1
    called_model, called_cal_fn, called_backend = mock_static.call_args.args
    assert called_model is model
    assert called_backend == QuantizationBackend.QNNPACK
    # the wrapped calibration fn must drive the prepared model once per sample
    prepared = MagicMock()
    called_cal_fn(prepared)
    assert prepared.call_count == 1


def test_get_bnb_4bit_config_float32_compute_dtype(monkeypatch):
    """compute_dtype='float32' is a documented option and must map to torch.float32."""
    import sys

    with patch(
        "backend.services.quantization._is_bitsandbytes_available", return_value=True, autospec=True
    ):
        mock_torch = MagicMock()
        mock_torch.float16 = "float16"
        mock_torch.bfloat16 = "bfloat16"
        mock_torch.float32 = "float32"

        mock_config_class = MagicMock()
        mock_transformers = MagicMock()
        mock_transformers.BitsAndBytesConfig = mock_config_class

        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

        get_bnb_4bit_config(compute_dtype="float32")

        mock_config_class.assert_called_once_with(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype="float32",
            bnb_4bit_use_double_quant=True,
        )
```

D5 note: on `async__22` (`apply_dynamic(backend)` — backend shifted into the model slot)
the autospec mock's recorded call is `(QNNPACK,)` ≠ `(model, QNNPACK)` → RED. On `async__1`
the first block routes to static → `mock_dynamic.assert_called_once_with` RED.

### D6. find_spec argument (kills cluster 7) — append near the other `_is_bitsandbytes_available` tests

```python
def test_is_bitsandbytes_available_checks_correct_module_name(monkeypatch):
    """The availability probe must look up exactly the 'bitsandbytes' module."""
    import sys

    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = True

    with patch("importlib.util.find_spec", return_value=MagicMock(), autospec=True) as mock_find:
        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        assert _is_bitsandbytes_available() is True

    mock_find.assert_called_once_with("bitsandbytes")
```

(D1–D6 as 6 drafted test functions cover clusters 1–12 = all 51 TEST-GAP survivors;
D5's file also gained the float32 dtype_map test killing cluster 10 — place that one
next to `test_get_bnb_4bit_config_custom_params` L370. Cluster 9's static member is
covered by D4's engine assert.)

## Notes

- Mutant copy `mutants/backend/services/quantization.py` confirmed to contain the per-variant
  clobber regions (e.g. `find_spec(None)` at copy-line ~471); `mutmut show` succeeded on all
  101 keys, so no manual diffing fallback was needed.
- `except ImportError, ModuleNotFoundError:` at backend/services/quantization.py:144 is valid
  Python 3.14 (PEP 758) — not a latent bug, no action.
- 43 keys still have `exit_code: null` (unchecked at snapshot time); re-triage after the run
  finishes may add a small tail, but the pattern taxonomy above should absorb it.
