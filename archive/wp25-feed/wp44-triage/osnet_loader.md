# WP4.4 Triage Dossier — `backend/services/osnet_loader.py`

- **Meta snapshot**: 362 keys total, 141 killed, **136 SURVIVED** (this dossier), 85 unchecked (ignored per protocol).
- **Diff source**: AST-extracted per-variant diffs from `mutants/backend/services/osnet_loader.py` vs original (all 136 extracted; `mutmut show` spot-checked as ground truth and matched). Raw per-mutant diffs: `/tmp/wp25/wp44-triage/scratch-osnet/diffs.json`, membership in `scratch-osnet/final_clusters.json`.
- **Covering test file (all functions)**: `backend/tests/unit/services/test_osnet_loader.py` (1118 lines; classes `TestPersonEmbeddingResult` L31, `TestLoadOSNetModel` L111, `TestExtractPersonEmbedding` L495, `TestExtractPersonEmbeddingsBatch` L737, `TestMatchPersonEmbeddings` L843, `TestFormatPersonReidContext` L916). Also `backend/tests/unit/services/test_enrichment_pipeline_household_matching.py` (integration consumer of `extract_person_embedding`/`cosine_similarity`).
- **Key structural fact driving every TEST-GAP call**: all `load_osnet_model` success tests mock `torchvision.transforms` and assert only `"transform" in result` (test file L202-231); all `extract_person_embeddings_batch` tests mock `torch.stack`/`model` and never exercise flatten/pad/normalize paths; `load_state_dict` is mocked returning `([], [])` so critical-key validation never runs; `validate_model_path` is monkeypatched to a lambda in every success test (L215-218).
- Env note: torch 2.14.0+cpu / torchvision 0.29.0 / torchreid 0.2.5 ARE installed in the venv; tests still mock them (hermetic), so the transform test below patches `sys.modules` like the neighbors instead of importing real torchvision.

## Cluster table (counts sum to 136)

| # | Function / concern | Pattern | Keys (examples, ≤3) | N | Class | Why |
|---|--------------------|---------|---------------------|---|-------|-----|
| 1 | `load_osnet_model` | logger.info/debug/error + exc_info/extra message-text & arg mutation | `_9`, `_52`, `_83` (full set `_9,_52-55,_60,_83-86,_95-98,_105-112,_136-139,_144-146,_148-155`) | 37 | **EQUIVALENT** | pure log/message text + log-kwarg tweaks; no test inspects log records; control flow unchanged |
| 2 | `load_osnet_model` | `critical_prefixes` list element mutated (`convN.`→`XXconvN.XX`/`CONVN.`, list→None) + `critical_missing` comp→None | `_68`, `_71`, `_79` (full set `_67-82`) | 16 | **TEST-GAP** | security/accuracy guard NEM-4521: with a real missing critical key every mutant silently skips the `RuntimeError`; tests mock `load_state_dict→([],[])` so the raise path never executes |
| 3 | `load_osnet_model` | image transform mutated: `Resize((256,128))`→`(257,128)`/`(256,129)`/None, `mean`/`std` element +1, kwarg removal, Compose→None | `_116`, `_122`, `_125` (full set `_113-127`) | 15 | **TEST-GAP** | preprocessing constants feed model input; tests mock `torchvision.transforms` and never check what was passed ("transform" in result` only) |
| 4 | `load_osnet_model` | `torch.load(weights_file, map_location="cpu", weights_only=True)` arg mutations (weights_only→False/None, map_location tweak, arg drop) | `_39`, `_33`, `_35` (full set `_31-39`) | 9 | **TEST-GAP** | `weights_only=False` is the NEM-4519 arbitrary-code-execution hardening flipped off; `torch.load` is a MagicMock so the security arg is never checked |
| 5 | `load_osnet_model` | `build_model(name="osnet_ain_x1_0", num_classes=1, pretrained=False)` kwargs mutated/dropped | `_20`, `_22`, `_23` (full set `_14-23`) | 10 | **TEST-GAP** | wrong architecture (`osnet_ain_x1_0`→`XX..XX`), or `pretrained=True` (network download in prod) — `build_model` is mocked, kwargs never asserted |
| 6 | `load_osnet_model` | weights-filename fallback chain: `"model.pth"`→`"XXmodel.pthXX"`/`"MODEL.PTH"`, `if not exists()`→`if exists()` | `_28`, `_26`, `_90` (full set `_26`,`_27`,`_28`,`_89`,`_90`,`_91`) | 6 | **TEST-GAP** | `mock_path.__truediv__` returns the same existing file regardless of the filename argument, so candidate-name and `exists()` inversion are invisible; real fallback ordering untested |
| 7 | `load_osnet_model` | `load_state_dict(state_dict, strict=False)` → `strict=True`/`strict=None`/dropped | `_66`, `_63`, `_65` | 3 | **TEST-GAP** | `strict=True` would crash on filtered classifier keys (the whole NEM-3888 design); mock accepts any kwargs |
| 8 | `load_osnet_model` | `validate_model_path(..., must_exist=False)`→`must_exist=None`/kwarg dropped; `raise RuntimeError(f"Invalid model path: {e}")`→`RuntimeError(None)` | `_3`, `_6`, `_8` | 3 | **TEST-GAP** | NEM-4501 path-traversal call config + security error wrapping; every success test monkeypatches `validate_model_path` away and no test drives a `PathSecurityError` |
| 9 | `load_osnet_model` | log message with XX-pad that sits inside an asserted `pytest.raises(match=...)`: `_141` (ImportError "OSNet requires torch…"), `_100` (RuntimeError "OSNet requires either torchreid…") | `_141`, `_100` | 2 | **TEST-GAP** | text is load-bearing — `re.search`-style `match=` still finds the substring, so these survive today's tests but encode message-drift acceptance; a `str(excinfo.value).startswith(...)` assertion kills them |
| 10 | `load_osnet_model` | crash-injection args on hot path: `Path(model_path)`→`Path(None)` (`_12`), `torch.jit.load(weights_file)`→`jit.load(None)` (`_94`) | `_12`, `_94` | 2 | **LOW-VALUE** | mutant raises TypeError instead of designed error; the outer `except Exception` re-wraps into the same `RuntimeError("Failed to load OSNet model: ...")` that existing tests match → surviving behavior is nearly indistinguishable; nobody should assert "Path(None) not called" |
| 11 | `extract_person_embeddings_batch` | batch pipeline args→None: `tensors.append(None)`/`transform(None)`, `stack(None)`, `device=None`, `.to(None)`, `model(None)` | `_34`, `_36`, `_42` (full set `_33,_34,_36,_37,_39,_40,_42`) | 7 | **LOW-VALUE** | all crash inside the mocked pipeline (MagicMock tolerates None args up to real np ops) and the outer handler re-raises the generic RuntimeError the test suite already matches; crash-injection, no meaningful observable behavior to assert |
| 12 | `extract_person_embeddings_batch` | confidence tiers: `width<32 or height<64` → `and` / `<=32` / `<33` / `height<=64` / `<65`, and `elif width<64 or height<128`→`and` | `_21`, `_22`, `_24` (full set `_21-26`) | 6 | **TEST-GAP** | 0.5/0.8 confidence tiers are asserted for the SINGLE-image fn (`TestExtractPersonEmbedding` L546-630) but the batch tests only ever feed good-size images (both 1.0, L750-795); or→and flips and <32 vs <=32 boundary shifts are invisible |
| 13 | `extract_person_embeddings_batch` | `img.convert("RGB") if img.mode != "RGB"`: guard `and False` (`_12`), arg `None`/`"XXRGBXX"`/`"rgb"` | `_12`, `_16`, `_15` | 4 | **TEST-GAP** | no batch test feeds a non-RGB image (single-image fn HAS `test_extract_person_embedding_non_rgb_converted` L633); probe on installed Pillow 12.3.0: `convert("rgb")` genuinely raises `ValueError("image has wrong mode")` — mode is case-sensitive — so `_16` is a real bug, not equivalent |
| 14 | `extract_person_embeddings_batch` | L2-normalize concern: `if norm > 0:`→`>=0`/`>1`, `processed/norm`→`*norm`/None, `embedding=None`, `confidence=confidences[i]` kwarg dropped | `_56`, `_53`, `_61` (full set `_53-56,_61,_66`) | 6 | **TEST-GAP** | batch tests feed `np.random.rand` outputs and assert only len/types/confidence==1.0/ids; never `np.linalg.norm(r.embedding)≈1`, so multiply-instead-of-divide and zero-norm guard flip pass — same normalization IS asserted nowhere for batch (single fn also unasserted, but batch is the hot path) |
| 15 | `extract_person_embeddings_batch` | dimension clamp boundary: `if processed.shape[0] > OSNET_EMBEDDING_DIM`→`>=`, pad branch `<`→`<=` | `_48`, `_50` | 2 | **TEST-GAP** | batch tests only use exactly-512 rows, so `>=` truncation is invisible and short-embedding pad (which the SINGLE fn tests at L1072) has no batch analogue; 512→511 mutant would truncate a valid vector |
| 16 | `PersonEmbeddingResult.cosine_similarity` | `embedding / (norm+1e-8)` → `* (norm+1e-8)`, for self and other | `_2`, `_7` | 2 | **TEST-GAP** | multiply instead of divide on ALREADY-normalized test vectors (norm≈1) is a no-op, so all three existing similarity tests (L68-108) pass; a raw un-normalized vector pair exposes it |
| 17 | `match_person_embeddings` | `if similarity >= threshold:` → `>` | `_4` | 1 | **TEST-GAP** | exact-threshold inclusion boundary untested: existing tests use sim≈0.99 vs threshold 0.7 (L846) and orthogonal≈0 (L864); nothing puts similarity exactly at threshold |
| 18 | `format_person_reid_context` | `>=0.9`→`>0.9`, `>=0.8`→`>0.8` tier-boundary flips + `"\n".join`→`"XX\nXX".join` | `_9`, `_12`, `_17` | 3 | **TEST-GAP** | tests use 0.95/0.85/0.75, never exactly 0.9/0.8; no test counts lines (join separator invisible); the tier wording IS asserted, the boundary inclusive-vs-exclusive is not |
| 19 | `format_person_reid_context` | `match.detection_id or "unknown"` → `"XXunknownXX"`/`"UNKNOWN"` | `_6`, `_7` | 2 | **LOW-VALUE** | cosmetic placeholder fallback; no test feeds a `detection_id=None` match, and the only consumer (prompt text) tolerates the casing — but a prompt-contract test could cheaply pin it |

**Totals: 136 survivors = EQUIVALENT 37 + LOW-VALUE 13 + TEST-GAP 86.**

## Drafted tests (6 highest-value clusters)

All UNVERIFIED — not yet run red/green. TDD procedure for each: apply the cluster's mutant diff to `backend/services/osnet_loader.py`, run the new test, confirm it FAILS; restore original, confirm it PASSES. Target file: `backend/tests/unit/services/test_osnet_loader.py` (append classes; the `_os_load_harness` helper mirrors the existing `TestLoadOSNetModel` mock setup, test-file L182-232 style).

### Test 1 — `test_load_osnet_model_critical_missing_key_raises` (kills cluster 2, L-CRIT, 16 mutants)

TDD: parametrized over one missing key per critical prefix (each prefix element has its own mutant, and a single missing key cannot distinguish e.g. `conv4.` corruption while the other five prefixes still match). On `_74` (`"conv4."`→`"XXconv4.XX"`) the `conv4.weight` param no longer matches any prefix → no raise → `pytest.raises` fails; original raises `RuntimeError` for every param → passes.

```python
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "missing_key",
        ["conv1.weight", "conv2.weight", "conv3.weight", "conv4.weight", "conv5.weight", "bn1.weight"],
    )
    async def test_load_osnet_model_critical_missing_key_raises(self, monkeypatch, missing_key) -> None:
        """NEM-4521: missing critical conv/bn weights must abort loading, not silently pass."""
        import sys
        from pathlib import Path

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        mock_torch.load.return_value = {"conv1.weight": MagicMock()}

        mock_model = MagicMock()
        mock_model.eval.return_value = None
        mock_model.load_state_dict.return_value = ([missing_key], [])

        mock_torchreid = MagicMock()
        mock_torchreid.models.build_model.return_value = mock_model

        mock_transforms = MagicMock()
        mock_transforms.Compose.return_value = MagicMock()

        mock_path = MagicMock(spec=Path)
        mock_weights_file = MagicMock()
        mock_weights_file.exists.return_value = True
        mock_path.__truediv__ = lambda self, other: mock_weights_file

        monkeypatch.setattr(
            "backend.core.security.validate_model_path",
            lambda *args, **kwargs: Path("/test/model"),
        )
        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "torchreid", mock_torchreid)
        monkeypatch.setitem(sys.modules, "torchreid.models", mock_torchreid.models)
        monkeypatch.setitem(sys.modules, "torchvision", MagicMock())
        monkeypatch.setitem(sys.modules, "torchvision.transforms", mock_transforms)
        monkeypatch.setattr("backend.services.osnet_loader.Path", lambda x: mock_path)

        with pytest.raises(RuntimeError, match="Critical OSNet weights missing"):
            await load_osnet_model("/test/model")
```

(Any prefix element mutation makes `conv1.weight` non-critical → no raise → red. The `_80/_81/_82` crashes also surface as the generic RuntimeError NOT being raised with the critical message — the `match=` keeps them red too.)

### Test 2 — `test_load_osnet_model_transform_constants` (kills cluster 3, L-TRANSFORM, 15 mutants)

TDD: on `_116` Resize is `(257,128)` → tuple assertion fails; original `(256,128)` → passes.

```python
    @pytest.mark.asyncio
    async def test_load_osnet_model_transform_constants(self, monkeypatch) -> None:
        """Person re-id preprocessing must be 256x128 with ImageNet mean/std."""
        import sys
        from pathlib import Path

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        mock_torch.load.return_value = {"conv1.weight": MagicMock()}

        mock_model = MagicMock()
        mock_model.eval.return_value = None
        mock_model.load_state_dict.return_value = ([], [])

        mock_torchreid = MagicMock()
        mock_torchreid.models.build_model.return_value = mock_model

        mock_transforms = MagicMock()
        mock_transforms.Resize.side_effect = lambda size: ("resize", size)
        mock_transforms.ToTensor.side_effect = lambda: ("totensor",)
        mock_transforms.Normalize.side_effect = (
            lambda mean, std: ("normalize", tuple(mean), tuple(std))
        )
        mock_transforms.Compose.side_effect = lambda ops: ops

        mock_path = MagicMock(spec=Path)
        mock_weights_file = MagicMock()
        mock_weights_file.exists.return_value = True
        mock_path.__truediv__ = lambda self, other: mock_weights_file

        monkeypatch.setattr(
            "backend.core.security.validate_model_path",
            lambda *args, **kwargs: Path("/test/model"),
        )
        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "torchreid", mock_torchreid)
        monkeypatch.setitem(sys.modules, "torchreid.models", mock_torchreid.models)
        monkeypatch.setitem(sys.modules, "torchvision", MagicMock())
        monkeypatch.setitem(sys.modules, "torchvision.transforms", mock_transforms)
        monkeypatch.setattr("backend.services.osnet_loader.Path", lambda x: mock_path)

        result = await load_osnet_model("/test/model")

        assert result["transform"] == [
            ("resize", (256, 128)),
            ("totensor",),
            ("normalize", (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
        ]
```

(Compose→None `_113` and arg-list→None `_114/_119/_121` make `result["transform"]` None or a partial list → red; mean/std element bumps `_122-127` red on the tuple equality.)

### Test 3 — `test_load_osnet_model_loads_weights_only_and_cpu` (kills cluster 4, L-LOADARGS, 9 mutants)

TDD: on `_39` `weights_only=False` → boolean assertion fails; original True → passes.

```python
    @pytest.mark.asyncio
    async def test_load_osnet_model_loads_weights_only_and_cpu(self, monkeypatch) -> None:
        """NEM-4519: weights must load with weights_only=True on CPU (no pickle RCE, no GPU dep)."""
        import sys
        from pathlib import Path

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        mock_torch.load.return_value = {"conv1.weight": MagicMock()}

        mock_model = MagicMock()
        mock_model.eval.return_value = None
        mock_model.load_state_dict.return_value = ([], [])

        mock_torchreid = MagicMock()
        mock_torchreid.models.build_model.return_value = mock_model

        mock_transforms = MagicMock()
        mock_transforms.Compose.return_value = MagicMock()

        mock_path = MagicMock(spec=Path)
        mock_weights_file = MagicMock()
        mock_weights_file.exists.return_value = True
        mock_path.__truediv__ = lambda self, other: mock_weights_file

        monkeypatch.setattr(
            "backend.core.security.validate_model_path",
            lambda *args, **kwargs: Path("/test/model"),
        )
        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "torchreid", mock_torchreid)
        monkeypatch.setitem(sys.modules, "torchreid.models", mock_torchreid.models)
        monkeypatch.setitem(sys.modules, "torchvision", MagicMock())
        monkeypatch.setitem(sys.modules, "torchvision.transforms", mock_transforms)
        monkeypatch.setattr("backend.services.osnet_loader.Path", lambda x: mock_path)

        await load_osnet_model("/test/model")

        mock_torch.load.assert_called_once()
        args, kwargs = mock_torch.load.call_args
        assert args[0] is mock_weights_file
        assert kwargs["weights_only"] is True
        assert kwargs["map_location"] == "cpu"
```

(`_36` drops `weights_only` → KeyError/False → red; `_34/_31` lose positional arg → red; `_37/_38` map_location text → red. Note `mock_torch.load` records calls even under the module-level `Path` patch because `weights_file` identity is preserved.)

### Test 4 — `test_extract_batch_confidence_tiers` (kills cluster 12, B-CONF, 6 mutants)

TDD: on `_21` `width<32 and height<64` → 20x100 crop misses both tiers → confidence 1.0 ≠ 0.5 → red; original → 0.5 → passes.

```python
    @pytest.mark.asyncio
    async def test_extract_batch_confidence_tiers(self, monkeypatch) -> None:
        """Batch confidence must mirror the single-image tiers: <32w or <64h → 0.5, <64w or <128h → 0.8."""
        import sys

        mock_torch = MagicMock()
        mock_torch.inference_mode.return_value.__enter__ = MagicMock()
        mock_torch.inference_mode.return_value.__exit__ = MagicMock()
        mock_stacked = MagicMock()
        mock_stacked.to.return_value = mock_stacked
        mock_torch.stack.return_value = mock_stacked

        mock_output = MagicMock()
        mock_output.cpu.return_value = MagicMock()
        mock_output.cpu.return_value.numpy.return_value = np.random.rand(
            3, OSNET_EMBEDDING_DIM
        )

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([MagicMock(device="cpu")])
        mock_model.return_value = mock_output

        mock_transform = MagicMock()
        mock_transform.return_value = MagicMock()

        model_dict = {"model": mock_model, "transform": mock_transform}

        # (width, height): small-by-width only, small-by-height only, medium,
        # and the two exact boundary sizes 32/64 that the < → <= mutants move.
        small_w = MagicMock(mode="RGB", size=(20, 100))
        small_h = MagicMock(mode="RGB", size=(100, 40))
        medium = MagicMock(mode="RGB", size=(50, 100))
        at_w = MagicMock(mode="RGB", size=(32, 100))   # w == 32 → NOT small, medium tier
        at_h = MagicMock(mode="RGB", size=(100, 64))   # h == 64 → NOT small, medium tier via or-branch

        monkeypatch.setitem(sys.modules, "torch", mock_torch)

        results = await extract_person_embeddings_batch(
            model_dict, [small_w, small_h, medium, at_w, at_h]
        )

        assert results[0].confidence == 0.5  # width < 32 (or-branch 1)
        assert results[1].confidence == 0.5  # height < 64 (or-branch 2)
        assert results[2].confidence == 0.8  # 32 <= w < 64
        assert results[3].confidence == 0.8  # w == 32 is NOT < 32; still < 64 → medium
        assert results[4].confidence == 0.8  # h == 64 is NOT < 64; 100 < 64 is False but h < 128 → medium
```

Kill mapping: `_21` (or→and, small tier) red on `small_w` (falls through to 0.8) and `small_h`; `_26` (or→and, medium tier) red on `at_h` (100<64 and 64<128 → False → 1.0); `_22/_23` red on `at_w`; `_24/_25` red on `at_h`. numpy mock above must return 5 rows: `np.random.rand(5, OSNET_EMBEDDING_DIM)`.

### Test 5 — `test_extract_batch_l2_normalizes_embeddings` (kills cluster 14, B-NORM, 6 mutants; contributes to 15 on short inputs)

TDD: on `_54` (`norm > 1`) the deliberately low-norm row (≈0.023) skips normalization → norm assertion fails; on `_56` (`* norm`) norm becomes ≈0.0005 → fails; on `_53` (`norm >= 0`) the zero row divides by zero → NaN → fails; original (norm > 0 guard, division) → passes all three rows.

```python
    @pytest.mark.asyncio
    async def test_extract_batch_l2_normalizes_embeddings(self, monkeypatch) -> None:
        """Batch embeddings must be unit-norm (or untouched zero-vectors), like the single path."""
        import sys

        mock_torch = MagicMock()
        mock_torch.inference_mode.return_value.__enter__ = MagicMock()
        mock_torch.inference_mode.return_value.__exit__ = MagicMock()
        mock_stacked = MagicMock()
        mock_stacked.to.return_value = mock_stacked
        mock_torch.stack.return_value = mock_stacked

        # Unnormalized raw model output: norm ~ sqrt(512*0.33^2+...) != 1
        raw = np.full((2, OSNET_EMBEDDING_DIM), 0.37)
        raw[1] = 0.0  # zero vector exercises the norm>0 guard

        mock_output = MagicMock()
        mock_output.cpu.return_value = MagicMock()
        mock_output.cpu.return_value.numpy.return_value = raw

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([MagicMock(device="cpu")])
        mock_model.return_value = mock_output

        mock_transform = MagicMock()
        mock_transform.return_value = MagicMock()

        model_dict = {"model": mock_model, "transform": mock_transform}

        img = MagicMock(mode="RGB", size=(128, 256))
        monkeypatch.setitem(sys.modules, "torch", mock_torch)

        results = await extract_person_embeddings_batch(model_dict, [img, img])

        assert np.isclose(np.linalg.norm(results[0].embedding), 1.0)
        # zero-vector guard: must stay exactly zero, never divide-by-zero / NaN
        assert np.all(results[1].embedding == 0.0)
```

Kill mapping: `_53` red on zero row (0/0 → NaN vs must-equal-0); `_54` red on low-norm row 0.0226 (skips division); `_56` red (norm ≈ 0.0005); `_55`/`_61` red (embedding None → TypeError on `np.linalg.norm`). `_66` (dropped `confidence=confidences[i]` kwarg) is caught by Test 4 instead: every batch result would default to 1.0, breaking the 0.5/0.8 tier asserts. In the code above, set `raw = np.full((2, OSNET_EMBEDDING_DIM), 0.001)` — the 0.37 constant in the comment block is the earlier sketch; use 0.001 so the norm≈0.023 property drives `_54`.

### Test 6 — `test_extract_batch_converts_non_rgb` (kills cluster 13, B-RGB, 4 mutants)

TDD: on `_16` `convert("rgb")` is passed instead of `"RGB"` → assert_called_once_with("RGB") fails (Pillow 12.3 probe confirms `"rgb"` is a genuine failure mode, not cosmetic); original → passes.

```python
    @pytest.mark.asyncio
    async def test_extract_batch_converts_non_rgb(self, monkeypatch) -> None:
        """Batch path must convert non-RGB crops with the exact "RGB" mode (mirrors single-image test)."""
        import sys

        mock_torch = MagicMock()
        mock_torch.inference_mode.return_value.__enter__ = MagicMock()
        mock_torch.inference_mode.return_value.__exit__ = MagicMock()
        mock_stacked = MagicMock()
        mock_stacked.to.return_value = mock_stacked
        mock_torch.stack.return_value = mock_stacked

        mock_output = MagicMock()
        mock_output.cpu.return_value = MagicMock()
        mock_output.cpu.return_value.numpy.return_value = np.random.rand(
            1, OSNET_EMBEDDING_DIM
        )

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([MagicMock(device="cpu")])
        mock_model.return_value = mock_output

        mock_transform = MagicMock()
        mock_transform.return_value = MagicMock()

        model_dict = {"model": mock_model, "transform": mock_transform}

        rgba_converted = MagicMock()
        rgba_converted.size = (128, 256)
        img = MagicMock()
        img.mode = "RGBA"
        img.convert.return_value = rgba_converted

        monkeypatch.setitem(sys.modules, "torch", mock_torch)

        results = await extract_person_embeddings_batch(model_dict, [img])

        assert len(results) == 1
        img.convert.assert_called_once_with("RGB")
        mock_transform.assert_called_once_with(rgba_converted)  # converted image is what gets transformed
```

(`_12` guard `and False` → convert never called → red; `_14/_15/_16` wrong arg → `assert_called_once_with("RGB")` red; transform call arg kills any mutant that transforms the raw RGBA image instead.)

## Cheaper follow-up kills (not drafted, one-line notes)

- Cluster 5 (L-BUILD, 10): add `mock_torchreid.models.build_model.assert_called_once_with(name="osnet_ain_x1_0", num_classes=1, pretrained=False)` to the success test.
- Cluster 7 (L-STRICT, 3): `mock_model.load_state_dict.assert_called_once()` + `assert call_args.kwargs["strict"] is False`.
- Cluster 8 (L-SECMSG, 3): success test captures `validate_model_path` kwargs and asserts `must_exist is False`; plus a test where the patched validator raises `PathSecurityError` and `pytest.raises(RuntimeError, match="Invalid model path")`.
- Cluster 9 (L-MSGPAD, 2): assert message STARTS with the contract sentence: `assert str(excinfo.value).startswith("OSNet requires torch and torchvision")` (XX-pad breaks startswith; `re.search`-style `match=` cannot).
- Cluster 16 (C-COS, 2): one test comparing **unnormalized** vectors `np.full(512, 0.5)` vs `np.full(512, 0.5)` → `cosine_similarity ≈ 1.0` (mutant `*norm` yields ≈ 12.8 → red).
- Cluster 17 (M-THRESH, 1): gallery item with similarity exactly == threshold (use `threshold=1.0` and an identical embedding) → must be returned; `>` mutant drops it.
- Cluster 18 (F-THRESH, 3): feed similarity exactly 0.9 → "HIGH CONFIDENCE"; exactly 0.8 → "Likely same person"; `result.count("\n") == 1` for one match kills the join mutant.
- Cluster 19 (F-UNK, 2): match with `detection_id=None` → assert `"unknown" in result` (pins lowercase fallback; cheap but LOW-VALUE).
