# WP4.4 Triage Dossier — backend/services/yolo_world_loader.py

Generated: 2026-09-19 (triage-only; NOTHING executed — all drafts UNVERIFIED)

## Census

- Meta: `mutants/backend/services/yolo_world_loader.py.meta` — 135 keys, 108 killed, **27 survived**, 0 unchecked.
- Survivors live in exactly two functions:
  - `load_yolo_world_model` (23): m2,m3,m4,m5,m6,m11,m16,m17,m18,m19,m20,m22,m25,m26,m27,m29,m30,m31,m32,m33,m34,m35,m36
  - `detect_with_prompts` (4): m24,m64,m70,m71
- All 27 diffs obtained via `uv run mutmut show <key>` (no manual diffing needed).

## Covering test files (from mutants/mutmut-stats.json → tests_by_mangled_function_name)

- `backend/tests/unit/services/test_yolo_world_loader.py` — primary; load-model tests at lines 212–305, detect tests at lines 312–528. **Zero** `caplog` usage anywhere; `torch.cuda.is_available` patched only to `True` (lines 276, 298); no timeout/TimeoutError tests.
- `backend/tests/unit/services/test_model_zoo.py` — `TestYoloWorldLoader` (line 1423), `TestDetectWithPrompts` (line 1626). Same blind spots: success/error-wrapping paths only, no logging or CPU-guard assertions.

## Cluster table (27 = 4+12+7+1+1+2)

| # | Cluster | Count | Keys | Class |
|---|---------|-------|------|-------|
| A | CPU-guard RuntimeError message text (`raise RuntimeError("YOLO-World requires a CUDA GPU — …")`); the entire `if not torch.cuda.is_available():` guard is never executed by any test — every test patches `cuda.is_available → True` or lets the import fail first. Mutants mangle the message (None / XX-wrap / lowercase / UPPERCASE) and all survive because the line never runs. | 4 | `x_load_yolo_world_model__mutmut_2`, `_3`, `_4`, `_5` | **TEST-GAP** |
| B | Pure log-message text mutations (`logger.info/warning/error/debug` message → None / XX-wrapped / lowercase / UPPERCASE). Program behavior unchanged; no test inspects log records. | 12 | `x_load_yolo_world_model__mutmut_6`, `_11`, `_16`, `_17`, `_18`, `_19`, `_20`, `_25`, `_31`, `_32`, `_33`; `x_detect_with_prompts__mutmut_71` | **EQUIVALENT** |
| C | Structured-logging kwargs on the `except Exception` handler: `exc_info=True → None/False/removed`, `extra={"model_path": …} → None/removed`, extra dict key `"model_path" → "XXmodel_pathXX"/"MODEL_PATH"`. Real observability change, but the surrounding contract (RuntimeError raised + `from e` chaining) IS asserted by `test_load_yolo_world_model_runtime_error`; nobody should pin exc_info/extra-key spelling in unit tests. | 7 | `x_load_yolo_world_model__mutmut_26`, `_27`, `_29`, `_30`, `_34`, `_35`, `_36` | **LOW-VALUE** |
| D | `raise ImportError("YOLO-World requires ultralytics. …")` message XX-wrapped (m22). Survives because the existing test uses substring `match="YOLO-World requires ultralytics"` (`re.search`), which the XX-wrapped string still contains. Message-text-only; raise + chaining already asserted. | 1 | `x_load_yolo_world_model__mutmut_22` | **LOW-VALUE** |
| E | `for result in results: if result.boxes is None: continue → break`. With ≥2 results where an early one has `boxes is None` and a later one carries boxes, `break` silently drops the later detections. All existing detect tests feed a **single**-result list (lines 340–528), where continue ≡ break. | 1 | `x_detect_with_prompts__mutmut_24` | **TEST-GAP** |
| F | `asyncio.wait_for(..., timeout=15.0)` → `timeout=None` (m64) / `timeout=16.0` (m70). The 15 s watchdog (protects the 90 s batch window) executes in every detect test but its value is never asserted; the `except TimeoutError: return []` arm is also untested. Deterministic kill: spy on `asyncio.wait_for` (no timing). | 2 | `x_detect_with_prompts__mutmut_64`, `_70` | **TEST-GAP** |

## Drafted tests (UNVERIFIED — not yet run red/green)

Target file for all four: `backend/tests/unit/services/test_yolo_world_loader.py` (append in the relevant section; imports already present at module top: `MagicMock`, `pytest`, `load_yolo_world_model`, `detect_with_prompts`, `SECURITY_PROMPTS`; existing style: `@pytest.mark.asyncio async def test_…(monkeypatch)` + `patch("torch.cuda.is_available", …)`).

### T1 — kills cluster A (m2, m3, m4, m5)

TDD: on each mutant the wrapper message becomes `…: None` / `…: XXYOLO-World…` / `…: yolo-world…` / `…: YOLO-WORLD…`, so the anchored regex fails and the `pytest.raises` match assertion is red; green on original.

```python
@pytest.mark.asyncio
async def test_load_yolo_world_model_cpu_only_raises(monkeypatch):
    """CPU-only host must be refused with the CUDA-GPU RuntimeError (NEM: GIL starvation guard).

    The guard message is re-wrapped by the generic ``except Exception`` handler,
    so the outer message embeds the inner one: assert the full prefix to pin the text.
    """
    import sys
    from unittest.mock import patch

    mock_ultralytics = MagicMock()
    monkeypatch.setitem(sys.modules, "ultralytics", mock_ultralytics)

    with patch("torch.cuda.is_available", return_value=False, autospec=True):
        with pytest.raises(
            RuntimeError,
            match="Failed to load YOLO-World model: YOLO-World requires a CUDA GPU",
        ):
            await load_yolo_world_model("yolov8s-worldv2.pt")

    # Must refuse BEFORE constructing the model
    mock_ultralytics.YOLOWorld.assert_not_called()
```

Note: `match=` is `re.search`; the `model: YOLO-World` seam is the anchor that kills the XX-wrap mutant (m3), while case-sensitive search kills m4/m5 and `RuntimeError(None)` (str `"None"`) kills m2.

### T2 — kills cluster E (m24)

TDD: on the `break` mutant the second result is dropped → `len(result) == 1` is red (0); green on the original `continue`.

```python
@pytest.mark.asyncio
async def test_detect_with_prompts_skips_none_boxes_result_and_continues():
    """A boxes=None result must be skipped, NOT abort the loop (multi-result ultralytics output)."""
    import numpy as np

    mock_model = MagicMock()
    mock_model.set_classes = MagicMock()

    # First result: no boxes at all
    empty_result = MagicMock()
    empty_result.boxes = None

    # Second result: one real detection
    mock_boxes = MagicMock()
    mock_boxes.__len__ = lambda _self: 1
    xy = MagicMock()
    xy.cpu.return_value.numpy.return_value = np.array([1, 2, 3, 4])
    mock_boxes.xyxy = [xy]
    cf = MagicMock()
    cf.cpu.return_value.numpy.return_value = np.array(0.9)
    mock_boxes.conf = [cf]
    cl = MagicMock()
    cl.cpu.return_value.numpy.return_value = np.array(0)
    mock_boxes.cls = [cl]

    real_result = MagicMock()
    real_result.boxes = mock_boxes
    real_result.names = {0: "package"}

    mock_model.predict.return_value = [empty_result, real_result]

    result = await detect_with_prompts(mock_model, MagicMock())

    assert len(result) == 1
    assert result[0]["class_name"] == "package"
```

### T3 — kills cluster F (m64, m70)

TDD: on m64 the captured timeout is `None`, on m70 `16.0`; the `== 15.0` assertion is red on both, green on original. No wall-clock timing, so no flake.

```python
@pytest.mark.asyncio
async def test_detect_with_prompts_applies_15s_inference_timeout(monkeypatch):
    """The 15 s wait_for watchdog (guards the 90 s batch window) must be passed verbatim."""
    import asyncio

    captured: dict = {}
    real_wait_for = asyncio.wait_for

    async def spy_wait_for(aw, *, timeout=None):
        captured["timeout"] = timeout
        return await real_wait_for(aw, timeout=timeout)

    monkeypatch.setattr(asyncio, "wait_for", spy_wait_for)

    mock_model = MagicMock()
    mock_model.set_classes = MagicMock()
    mock_model.predict = MagicMock(return_value=[])

    result = await detect_with_prompts(mock_model, MagicMock())

    assert result == []
    assert captured["timeout"] == 15.0
```

### T4 — hardens the timeout arm (supports cluster F; kills any `return []`-arm mutants if they resurface)

TDD: on a mutant that re-raises or returns non-empty on TimeoutError the `result == []` assertion is red; green on original.

```python
@pytest.mark.asyncio
async def test_detect_with_prompts_returns_empty_on_inference_timeout(monkeypatch):
    """A 15 s inference timeout must degrade to empty detections, never raise into the batch."""
    import asyncio

    async def fake_wait_for(aw, *, timeout=None):
        if hasattr(aw, "close"):
            aw.close()  # avoid "coroutine never awaited" warning
        raise TimeoutError

    monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)

    mock_model = MagicMock()
    mock_model.set_classes = MagicMock()
    mock_model.predict = MagicMock()

    result = await detect_with_prompts(mock_model, MagicMock())

    assert result == []
```

## Notes

- Cluster A is the strongest TEST-GAP in the module: not a weak assertion but a wholly unexecuted guard (every test patches CUDA True). One test buys 4 kills.
- Clusters B/C/D dominate the survivor list (20/27) and are logging cosmetics; a `caplog`-based assertion campaign could grind some down but is LOW-VALUE by WP4.4 policy (log text/kwargs are not behavior contracts here).
- No survivor touches `get_object_*`, prompt constants, or the lock/atomicity logic — those areas are already well covered (108 kills).
- Hermeticity of drafts: T1 reuses the established `patch("torch.cuda.is_available", autospec=True)` pattern; T3/T4 monkeypatch `asyncio.wait_for` on the stdlib module object (module does `import asyncio` then calls `asyncio.wait_for(...)`, so the patch binds). No network, no GPU. UNVERIFIED — must be run red-on-mutant/green-on-original in the serial pytest lane before batch inclusion.
