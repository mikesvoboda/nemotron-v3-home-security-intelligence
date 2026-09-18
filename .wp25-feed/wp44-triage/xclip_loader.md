# WP4.4 Triage Dossier — backend/services/xclip_loader.py

Wave: xclip_loader (mutmut baseline, WP4.3 feed)
Meta: `mutants/backend/services/xclip_loader.py.meta` — 396 keys, 285 killed, **111 survived**, 0 pending.
Diff source: `uv run mutmut show <key>` (all 111 succeeded; no manual diffing fallback needed).
Covering tests (from `mutants/mutmut-stats.json` `tests_by_mangled_function_name`): **every** mutated
function is covered exclusively by `backend/tests/unit/services/test_xclip_loader.py`
(classify_actions: 30 tests L232/627/1135/1253/1670/1786; load: 8 tests L97/183;
_validate_and_convert_frames / _is_valid_pil_image / _convert_to_numpy_safe: L1414/1489; sample: 11 tests L915).

## Per-cluster table

Counts sum to 111. TEST-GAP = 30, LOW-VALUE = 35, EQUIVALENT = 46.

| # | Cluster | Fn | Count | Class | Example keys (suffix after `x_`) | Reasoning |
|---|---------|----|-------|-------|----------------------------------|-----------|
| 1 | `processor()` call kwargs never asserted (text/return_tensors/padding removed, set to None, "XXptXX"/"PT", padding=False) | classify_actions | 9 | **TEST-GAP** | __104, __106, __114 | Tests mock the processor as `MagicMock(**kwargs)` and (TestPixelValuesNoneFix L1786) capture only `images=`. A real XCLIPProcessor needs `text=prompts` + `return_tensors="pt"`; nothing pins them. Draft D1. |
| 2 | Output math on mocked torch — `torch.softmax` / `.squeeze` call args never asserted (logits→None, dim=-1→None/+1/-2, arg drops, squeeze(0)→None/1) | classify_actions | 9 | **TEST-GAP** | __162, __165, __172 | `mock_torch.softmax.return_value = mock_probs` ignores args, so every arg mutation is invisible. Real semantics: softmax over the prompt axis, squeeze batch dim. Draft D2. (squeeze(None) is identity on shape (1,N) → borderline-equiv, still killed by D2.) |
| 3 | Input device offload unasserted (`device=None`, `.to(device)` gate flipped/`and False`/`or True`, `.to(None)`) | classify_actions | 5 | **TEST-GAP** | __143, __147, __149 | Mocks set `pv.to.return_value = pv`; no test asserts `.to` is called with the parameter's device, nor that None-valued input entries are skipped (mut 147 `or True` crashes on them in real code). Draft D3. |
| 4 | float16 casting: dtype-gate `and`→`or`, half() stored under wrong dict key | classify_actions | 3 | **TEST-GAP** | __150, __157, __158 | `test_classify_handles_float16_model` (L631) asserts `half()` was *called*, not that the fp16 tensor landed under `"pixel_values"` in what the model receives; no negative test for fp32 models. Draft D4. |
| 5 | 16-frame normalization: padding count `(16 - len)`→`(16 + len)`; uniform-sample index formula broken (all indices → 0) | classify_actions | 2 | **TEST-GAP** | __47, __52 | Fewer/more-than-16 tests (L411, L451) never capture `images=`; the >16 test uses 32 *identical* frames so degenerate sampling is invisible. Draft D5. |
| 6 | `XCLIPModel.from_pretrained(None)` — model path not propagated | load_xclip_model | 1 | **TEST-GAP** | __11 | Tests assert `from_pretrained` on the *processor* class only (L222); the model-class call is unasserted. One-line fix: add `mock_xclip_model_cls.from_pretrained.assert_called_once_with(path)` to `test_load_model_with_huggingface_path`. Not separately drafted (fold into D6 note). |
| 7 | Zero-dimension guard: `arr.shape[1] == 0` → `== 1` (width-0 accepted, width-1 rejected) | _convert_to_numpy_safe | 1 | **TEST-GAP** | __19 | `test_convert_to_numpy_safe_zero_dimensions` (L1576) only exercises shape `(0,100,3)` (height). Width axis never tested. Draft D6. |
| 8 | Frame-filter telemetry: count arithmetic (`+` vs `-`, →None) and warning-gate `>0`→`>=0`/`>1` feed only the warning f-string | classify_actions | 8 | LOW-VALUE | __21, __22, __28 | Changes logged numbers / whether a diagnostic warning fires; no caller consumes them. Not worth asserting. |
| 9 | Diagnostic payload of classify logging/raise messages: message→None, `exc_info` dropped/None/False, wrong index or `type(None)` inside debug/error f-strings, shape-message→None | classify_actions | 15 | LOW-VALUE | __92, __138, __216 | Real but diagnostic-only; `pytest.raises(match=...)` anchors all still match. Nobody should assert debug text. |
| 10 | Diagnostic payload of load logging: message→None, `exc_info`/`extra={"model_path":…}` dropped, extra-key case flips | load_xclip_model | 12 | LOW-VALUE | __6, __34, __43 | Same rule as 9; the load-error contract (raise types/messages) is already asserted elsewhere. |
| 11 | classify raise-message text (XX padding, case) on ValueErrors/RuntimeErrors that existing `match=`/`in str()` asserts still substring-match | classify_actions | 7 | EQUIVALENT | __3, __10, __17 | e.g. `match="all frames failed numpy conversion"` survives `"XX…XX"` padding. |
| 12 | classify log-message text variants ('N/A'→'n/a'/'XXN/AXX', case/XX on failure msg) | classify_actions | 7 | EQUIVALENT | __96, __220, __221 | Pure text. |
| 13 | load raise/log message text (case, XX padding incl. the CUDA-guard RuntimeError and ImportError strings) | load_xclip_model | 12 | EQUIVALENT | __3, __31, __41 | `match="requires a CUDA GPU"` / `"transformers" in str(...)` still pass. |
| 14 | Dead defensive numpy-shape/dtype validation rewrites (`or`→`and` combos, `<2`→`<=2`/`<3`, `!=3 or`→`!=3 and`, uint8 gate flip) | classify_actions | 6 | EQUIVALENT | __69, __80, __87 | `arr = np.array(rgb_frame)` is *always* a 3-D uint8 `(H,W,3)` ndarray — first guard is unreachable dead code; second guard's `and`-flip either matches original or raises IndexError that lands in the same `except Exception` frame-replacement path; float-normalization branch (L501-506) is dead for PIL inputs. |
| 15 | RGB-mode guard collapses to unconditional `convert("RGB")` (`or True`, compare-literal "RGB"→"XXRGBXX"/"rgb") | classify_actions | 3 | EQUIVALENT | __60, __65, __66 | Mutated literal is the *comparison* operand, not the convert arg — branch just becomes always-taken; `convert("RGB")` of an RGB image is pixel-identical. |
| 16 | `zip(prompts, probs_np, strict=True)` → strict removed/None/False | classify_actions | 3 | EQUIVALENT | __177, __181 | Length mismatch impossible (probs width == #prompts from softmax); strictness guard never fires. |
| 17 | 16-frame boundary flips at equality (`<`→`<=`, `>`→`>=`) | classify_actions | 2 | EQUIVALENT | __41, __48 | At `len==16`, pad-by-zero or identity uniform sampling (step=1) both yield the identical list. |
| 18 | `_validate_and_convert_frames` debug-message text (→None, XX, case) | _validate_and_convert_frames | 4 | EQUIVALENT | __9, __10, __11 | Filter behavior asserted (L1592-1668); message text is not. |
| 19 | Dead `.mode` liveness probe dropped (`_ = obj.mode` → `_ = None`) | _is_valid_pil_image | 1 | EQUIVALENT | __6 | `.mode` is a plain attribute; cannot raise after `.size` succeeds on a real PIL image — probe was dead. |
| 20 | `len(frame_paths) <= target_count` → `<` | sample_frames_from_batch | 1 | EQUIVALENT | __1 | At `len==target`, uniform sampling with step=1.0 reconstructs the identical list (`int(i*1.0)==i`). |

Totals: TEST-GAP 30 (clusters 1-7), LOW-VALUE 35 (8-10), EQUIVALENT 46 (11-20). 30+35+46 = 111.

## Drafted tests — append to `backend/tests/unit/services/test_xclip_loader.py`

**TDD procedure (same for all six):** apply the cluster's mutant diff (or `uv run mutmut run` the
specific key), run the new test — the added assert must FAIL (red); revert to original source —
it must PASS (green). Only then wire into the suite.

// UNVERIFIED - not yet run red/green

### D1 — processor call contract (kills cluster 1: keys 104,106,107,108,110,111,112,113,114)

```python
class TestProcessorCallContract:
    """NEM-3506 context: the processor call contract (text=prompts, images=frames,
    return_tensors="pt", padding=True) is load-bearing — real XCLIPProcessor returns
    None pixel_values without it. WP4.4: mutants that drop/these kwargs survived."""

    @pytest.mark.asyncio
    async def test_processor_called_with_prompt_text_and_pt_tensors(self) -> None:
        """text=prompts, return_tensors="pt", padding=True must reach the processor."""
        mock_model = MagicMock(spec=XCLIPModel)
        mock_processor = MagicMock(spec=XCLIPProcessor)

        mock_param = MagicMock(spec=torch.nn.Parameter)
        mock_param.device = "cpu"
        mock_param.dtype = torch.float32
        mock_model.parameters.return_value = iter([mock_param, mock_param])

        captured_kwargs: list[dict[str, Any]] = []

        def capture_processor_call(**kwargs: Any) -> dict[str, Any]:
            captured_kwargs.append(kwargs)
            return {"pixel_values": create_mock_pixel_values()}

        mock_processor.side_effect = capture_processor_call

        mock_outputs = MagicMock(spec=XCLIPOutput)
        mock_probs = MagicMock(spec=torch.Tensor)
        mock_probs.squeeze.return_value.cpu.return_value.numpy.return_value = np.array(
            [0.6, 0.2, 0.2]
        )
        mock_outputs.logits_per_video = MagicMock(spec=torch.Tensor)
        mock_model.return_value = mock_outputs

        model_dict = {"model": mock_model, "processor": mock_processor}
        frames = [Image.new("RGB", (224, 224)) for _ in range(16)]
        prompts = ["walk", "run", "loiter"]

        mock_torch = MagicMock(spec=["cuda", "float16", "softmax", "no_grad", "inference_mode"])
        mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)
        mock_torch.softmax.return_value = mock_probs
        mock_torch.float16 = "float16"

        with patch.dict(sys.modules, {"torch": mock_torch}):
            await classify_actions(model_dict, frames, prompts=prompts)

        assert len(captured_kwargs) == 1
        kwargs = captured_kwargs[0]
        # Dropped-kwargs mutants (108/110/111) raise KeyError here:
        assert kwargs["text"] == prompts          # kills 104 (text=None)
        assert kwargs["return_tensors"] == "pt"   # kills 106 (None), 112 ("XXptXX"), 113 ("PT")
        assert kwargs["padding"] is True          # kills 107 (None), 114 (False)
```

### D2 — softmax/squeeze call args (kills cluster 2: keys 162,164,165,166,167,168,169,171,172)

```python
class TestSoftmaxCallContract:
    """WP4.4: torch is fully mocked in this suite, so every argument mutation on
    torch.softmax / .squeeze survived. Pin the call: softmax(logits, dim=-1) then
    squeeze(0) to drop the batch dim."""

    @pytest.mark.asyncio
    async def test_probs_built_from_logits_with_last_dim_and_batch_squeeze(self) -> None:
        mock_model = MagicMock(spec=XCLIPModel)
        mock_processor = MagicMock(spec=XCLIPProcessor)

        mock_param = MagicMock(spec=torch.nn.Parameter)
        mock_param.device = "cpu"
        mock_param.dtype = torch.float32
        mock_model.parameters.return_value = iter([mock_param, mock_param])

        mock_inputs = {"pixel_values": create_mock_pixel_values()}
        for v in mock_inputs.values():
            v.to.return_value = v
        mock_processor.return_value = mock_inputs

        mock_outputs = MagicMock(spec=XCLIPOutput)
        mock_logits = MagicMock(spec=torch.Tensor)
        mock_probs = MagicMock(spec=torch.Tensor)
        mock_probs.squeeze.return_value.cpu.return_value.numpy.return_value = np.array(
            [0.7, 0.2, 0.1]
        )
        mock_outputs.logits_per_video = mock_logits
        mock_model.return_value = mock_outputs

        model_dict = {"model": mock_model, "processor": mock_processor}
        frames = [Image.new("RGB", (224, 224)) for _ in range(16)]

        mock_torch = MagicMock(spec=["cuda", "float16", "softmax", "no_grad", "inference_mode"])
        mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)
        mock_torch.softmax.return_value = mock_probs
        mock_torch.float16 = "float16"

        with patch.dict(sys.modules, {"torch": mock_torch}):
            result = await classify_actions(model_dict, frames, prompts=["a", "b", "c"])

        # 162/164 pass None (or drop the tensor), 165/166/167 drop dim or tensor,
        # 168 dim=+1, 169 dim=-2 — all fail this exact-call assert:
        mock_torch.softmax.assert_called_once_with(mock_logits, dim=-1)
        # 171 squeeze(None) / 172 squeeze(1):
        mock_probs.squeeze.assert_called_once_with(0)
        assert result["detected_action"] == "a"
```

### D3 — device offload (kills cluster 3: keys 143,146,147,148,149)

```python
class TestInputDeviceOffload:
    """WP4.4: `.to(device)` mapping survived all argument/gate mutations because
    mocks returned themselves. Assert tensors are moved to the model's device and
    that None-valued input entries pass through untouched (real crash for 147)."""

    @pytest.mark.asyncio
    async def test_inputs_moved_to_parameter_device(self) -> None:
        mock_model = MagicMock(spec=XCLIPModel)
        mock_processor = MagicMock(spec=XCLIPProcessor)

        mock_param = MagicMock(spec=torch.nn.Parameter)
        mock_param.device = "cuda:7"          # distinctive sentinel
        mock_param.dtype = torch.float32      # not fp16 -> half path skipped
        mock_model.parameters.return_value = iter([mock_param, mock_param])

        mock_pixel_values = create_mock_pixel_values()
        to_args: list[Any] = []

        def record_to(device: Any) -> MagicMock:
            to_args.append(device)
            return mock_pixel_values

        mock_pixel_values.to.side_effect = record_to

        # attention_mask=None exercises the `if v is not None` guard:
        # mutant 147 (or True) calls None.to(None-ish) -> AttributeError -> RuntimeError.
        mock_inputs = {"pixel_values": mock_pixel_values, "attention_mask": None}
        mock_processor.return_value = mock_inputs

        mock_outputs = MagicMock(spec=XCLIPOutput)
        mock_probs = MagicMock(spec=torch.Tensor)
        mock_probs.squeeze.return_value.cpu.return_value.numpy.return_value = np.array(
            [0.5, 0.5]
        )
        mock_outputs.logits_per_video = MagicMock(spec=torch.Tensor)
        mock_model.return_value = mock_outputs

        model_dict = {"model": mock_model, "processor": mock_processor}
        frames = [Image.new("RGB", (224, 224)) for _ in range(16)]

        mock_torch = MagicMock(spec=["cuda", "float16", "softmax", "no_grad", "inference_mode"])
        mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)
        mock_torch.softmax.return_value = mock_probs
        mock_torch.float16 = "float16"

        with patch.dict(sys.modules, {"torch": mock_torch}):
            result = await classify_actions(model_dict, frames, prompts=["a", "b"])

        assert to_args == ["cuda:7"]   # kills 143 (None), 146 (never), 148 (to(None)), 149 (flipped)
        assert "detected_action" in result   # None entry survived pass-through
```

### D4 — float16 key + gate (kills cluster 4: keys 150,157,158)

```python
class TestFloat16InputKeying:
    """WP4.4: half() was asserted as *called*, but mutants stored the fp16 tensor
    under a mangled key (model then gets fp32 inputs) or cast even for fp32 models."""

    @pytest.mark.asyncio
    async def test_fp16_model_receives_half_pixel_values_under_pixel_values_key(self) -> None:
        mock_model = MagicMock(spec=XCLIPModel)
        mock_processor = MagicMock(spec=XCLIPProcessor)

        mock_param = MagicMock(spec=torch.nn.Parameter)
        mock_param.device = "cuda"

        mock_torch = MagicMock(spec=["cuda", "float16", "softmax", "no_grad", "inference_mode"])
        mock_torch.float16 = "float16_type"
        mock_param.dtype = mock_torch.float16
        mock_model.parameters.return_value = iter([mock_param, mock_param])

        mock_pixel_values = create_mock_pixel_values()
        halfed = MagicMock(spec=torch.Tensor)
        mock_pixel_values.half.return_value = halfed
        mock_pixel_values.to.return_value = mock_pixel_values

        mock_inputs = {"pixel_values": mock_pixel_values}
        mock_processor.return_value = mock_inputs

        captured_model_kwargs: list[dict[str, Any]] = []

        def fake_inference(**kwargs: Any) -> MagicMock:
            captured_model_kwargs.append(kwargs)
            outputs = MagicMock(spec=XCLIPOutput)
            probs = MagicMock(spec=torch.Tensor)
            probs.squeeze.return_value.cpu.return_value.numpy.return_value = np.array(
                [0.5, 0.3, 0.2]
            )
            outputs.logits_per_video = MagicMock(spec=torch.Tensor)
            return outputs

        mock_model.side_effect = fake_inference

        model_dict = {"model": mock_model, "processor": mock_processor}
        frames = [Image.new("RGB", (224, 224)) for _ in range(16)]

        mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)
        mock_torch.inference_mode.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.inference_mode.return_value.__exit__ = MagicMock(return_value=None)
        probs_out = MagicMock(spec=torch.Tensor)
        probs_out.squeeze.return_value.cpu.return_value.numpy.return_value = np.array(
            [0.5, 0.3, 0.2]
        )
        mock_torch.softmax.return_value = probs_out

        with patch.dict(sys.modules, {"torch": mock_torch}):
            await classify_actions(model_dict, frames, prompts=["a", "b", "c"])

        assert len(captured_model_kwargs) == 1
        model_kwargs = captured_model_kwargs[0]
        # 157/158 write half under "XXpixel_valuesXX"/"PIXEL_VALUES":
        assert model_kwargs["pixel_values"] is halfed

    @pytest.mark.asyncio
    async def test_fp32_model_does_not_receive_half_pixel_values(self) -> None:
        """Kills 150: dtype-gate `and`->`or` casts to fp16 even for float32 models."""
        mock_model = MagicMock(spec=XCLIPModel)
        mock_processor = MagicMock(spec=XCLIPProcessor)

        mock_param = MagicMock(spec=torch.nn.Parameter)
        mock_param.device = "cpu"
        mock_param.dtype = torch.float32      # NOT float16
        mock_model.parameters.return_value = iter([mock_param, mock_param])

        mock_pixel_values = create_mock_pixel_values()
        mock_pixel_values.to.return_value = mock_pixel_values
        mock_processor.return_value = {"pixel_values": mock_pixel_values}

        mock_outputs = MagicMock(spec=XCLIPOutput)
        mock_probs = MagicMock(spec=torch.Tensor)
        mock_probs.squeeze.return_value.cpu.return_value.numpy.return_value = np.array(
            [0.6, 0.4]
        )
        mock_outputs.logits_per_video = MagicMock(spec=torch.Tensor)
        mock_model.return_value = mock_outputs

        model_dict = {"model": mock_model, "processor": mock_processor}
        frames = [Image.new("RGB", (224, 224)) for _ in range(16)]

        mock_torch = MagicMock(spec=["cuda", "float16", "softmax", "no_grad", "inference_mode"])
        mock_torch.float16 = "float16_type"   # distinct from param dtype
        mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)
        mock_torch.inference_mode.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.inference_mode.return_value.__exit__ = MagicMock(return_value=None)
        mock_torch.softmax.return_value = mock_probs

        with patch.dict(sys.modules, {"torch": mock_torch}):
            await classify_actions(model_dict, frames, prompts=["a", "b"])

        mock_pixel_values.half.assert_not_called()
```

### D5 — 16-frame normalization (kills cluster 5: keys 47,52)

```python
class TestFrameNormalizationCounts:
    """WP4.4: padding-count and uniform-sampling-index mutants survived because no
    test inspected WHICH frames (count/values) reach the processor."""

    @pytest.mark.asyncio
    async def test_fewer_than_16_frames_pads_to_exactly_16_with_last_frame(self) -> None:
        """Padding must reach exactly 16 frames, cloning the LAST frame (not 16+len)."""
        grays = [10, 20, 30, 40, 50]
        frames = [Image.new("RGB", (16, 16), color=(g, g, g)) for g in grays]

        mock_model = MagicMock(spec=XCLIPModel)
        mock_processor = MagicMock(spec=XCLIPProcessor)

        mock_param = MagicMock(spec=torch.nn.Parameter)
        mock_param.device = "cpu"
        mock_param.dtype = torch.float32
        mock_model.parameters.return_value = iter([mock_param, mock_param])

        captured_images: list[Any] = []

        def capture_processor_call(**kwargs: Any) -> dict[str, Any]:
            captured_images.append(kwargs.get("images"))
            return {"pixel_values": create_mock_pixel_values()}

        mock_processor.side_effect = capture_processor_call

        mock_outputs = MagicMock(spec=XCLIPOutput)
        mock_probs = MagicMock(spec=torch.Tensor)
        mock_probs.squeeze.return_value.cpu.return_value.numpy.return_value = np.array(
            [0.5, 0.3, 0.2]
        )
        mock_outputs.logits_per_video = MagicMock(spec=torch.Tensor)
        mock_model.return_value = mock_outputs

        model_dict = {"model": mock_model, "processor": mock_processor}

        mock_torch = MagicMock(spec=["cuda", "float16", "softmax", "no_grad", "inference_mode"])
        mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)
        mock_torch.softmax.return_value = mock_probs
        mock_torch.float16 = "float16"

        with patch.dict(sys.modules, {"torch": mock_torch}):
            await classify_actions(model_dict, frames, prompts=["a", "b", "c"])

        images_arg = captured_images[0]
        assert len(images_arg) == 16  # kills 47: pads to 16 + len(frames) = 26
        for i, g in enumerate(grays):
            assert int(images_arg[i][0, 0, 0]) == g, f"frame {i} pixel value"
        for i in range(len(grays), 16):
            assert int(images_arg[i][0, 0, 0]) == grays[-1], f"padded frame {i} must clone last"

    @pytest.mark.asyncio
    async def test_more_than_16_frames_samples_uniformly_not_all_first(self) -> None:
        """32 distinct frames must sample uniformly (indices 0,2,4,...30), not collapse to 0."""
        frames = [Image.new("RGB", (16, 16), color=(i, i, i)) for i in range(32)]

        mock_model = MagicMock(spec=XCLIPModel)
        mock_processor = MagicMock(spec=XCLIPProcessor)

        mock_param = MagicMock(spec=torch.nn.Parameter)
        mock_param.device = "cpu"
        mock_param.dtype = torch.float32
        mock_model.parameters.return_value = iter([mock_param, mock_param])

        captured_images: list[Any] = []

        def capture_processor_call(**kwargs: Any) -> dict[str, Any]:
            captured_images.append(kwargs.get("images"))
            return {"pixel_values": create_mock_pixel_values()}

        mock_processor.side_effect = capture_processor_call

        mock_outputs = MagicMock(spec=XCLIPOutput)
        mock_probs = MagicMock(spec=torch.Tensor)
        mock_probs.squeeze.return_value.cpu.return_value.numpy.return_value = np.array(
            [0.5, 0.3, 0.2]
        )
        mock_outputs.logits_per_video = MagicMock(spec=torch.Tensor)
        mock_model.return_value = mock_outputs

        model_dict = {"model": mock_model, "processor": mock_processor}

        mock_torch = MagicMock(spec=["cuda", "float16", "softmax", "no_grad", "inference_mode"])
        mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)
        mock_torch.softmax.return_value = mock_probs
        mock_torch.float16 = "float16"

        with patch.dict(sys.modules, {"torch": mock_torch}):
            await classify_actions(model_dict, frames, prompts=["a", "b", "c"])

        images_arg = captured_images[0]
        assert len(images_arg) == 16
        expected = [int(idx * 32 / 16) for idx in range(16)]  # [0, 2, 4, ..., 30]
        got = [int(arr[0, 0, 0]) for arr in images_arg]
        # kills 52: int(i / len(frames) / num_frames) == 0 for all i -> got == [0]*16
        assert got == expected
```

Both tests distinguish frames by the top-left pixel value (constant-color 16x16 images), so a
degenerate sampling that repeats one frame is caught.

### D6 — numpy width guard (kills cluster 7: key 19; note covers load cluster 6)

```python
    # Add to class TestNumpyConversionValidation (test_xclip_loader.py, ~L1489):
    def test_convert_to_numpy_safe_rejects_zero_width(self) -> None:
        """Zero WIDTH (axis 1) must be rejected, not just zero height."""
        from backend.services.xclip_loader import _convert_to_numpy_safe

        mock_img = MagicMock(spec=Image.Image)
        mock_img.load.return_value = None

        with patch("numpy.array", autospec=True) as mock_array:
            invalid_arr = MagicMock(spec=np.ndarray)
            invalid_arr.shape = (100, 0, 3)  # Zero width
            mock_array.return_value = invalid_arr

            assert _convert_to_numpy_safe(mock_img) is None   # mutant 19 returns arr

    def test_convert_to_numpy_safe_accepts_one_pixel_width(self) -> None:
        """Width==1 is a legitimate (slim) frame — mutant 19 wrongly rejects it."""
        from backend.services.xclip_loader import _convert_to_numpy_safe

        mock_img = MagicMock(spec=Image.Image)
        mock_img.load.return_value = None

        with patch("numpy.array", autospec=True) as mock_array:
            valid_arr = MagicMock(spec=np.ndarray)
            valid_arr.shape = (100, 1, 3)
            mock_array.return_value = valid_arr

            assert _convert_to_numpy_safe(mock_img) is valid_arr
```

**Cluster 6 fix (1-liner, no new test):** in `TestLoadXclipModelInternal.test_load_model_with_huggingface_path`
(L198), after the processor assert at L222, add:

```python
        mock_xclip_model_cls.from_pretrained.assert_called_once_with(
            "microsoft/xclip-base-patch16-16-frames"
        )
```

## Covering test file map

- `backend/tests/unit/services/test_xclip_loader.py:97` `TestLoadXclipModel`, `:183` `TestLoadXclipModelInternal` — load_xclip_model (8 tests)
- `:232` `TestClassifyActions`, `:627` `TestClassifyActionsInternal`, `:1253` edge cases, `:1670` null-frame integration, `:1786` `TestPixelValuesNoneFix` — classify_actions + nested `_classify` (30 tests; the mutation-heavy region)
- `:1414` `TestPilImageValidation`, `:1489` `TestNumpyConversionValidation` — helpers
- `:915` `TestSampleFramesFromBatch` — sample_frames_from_batch

## Notes

- The suite mocks `torch` and the HF processor wholesale, which is precisely why clusters 1-4
  survive: every mocked boundary swallows argument mutations. The drafted tests convert "mock was
  called" into "mock was called with the contract", the standard kill for this shape.
- Clusters 14/15/17/20 are genuinely dead-input-equivalent (documented per-row above); consider
  `# pragma: no mutation`-style suppression or leaving them in the baseline as known-equivalent.
- Module is DEPRECATED (NEM-5563, replaced by ST-GCN++); prompts/risk functions stay live. Test
  investment concentrated in classify_actions is still justified because action_recognition_service.py
  imports these code paths.
