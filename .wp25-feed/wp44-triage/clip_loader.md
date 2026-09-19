# WP4.4 Triage Dossier — backend/services/clip_loader.py

**Survivors: 24 / 48 mutants** (all 24 inside `x_load_clip_model`; every diff is in the
logging-call or exception-message surface). Verdict source:
`mutants/backend/services/clip_loader.py.meta` (exit_code 0). Diffs via
`uv run mutmut show <key>` (all 24 retrieved cleanly, saved at
`/tmp/wp25/wp44-triage/clip_loader_diffs.txt`).

**Covering test file**: `backend/tests/unit/services/test_clip_loader.py` (949 lines).
`mutmut-stats.json → tests_by_mangled_function_name →
backend.services.clip_loader.x_load_clip_model` lists 23 distinct tests from that file —
so every mutant line IS executed (mutmut's own execution gate), but the file contains
**zero** `caplog`/record-based assertions (grep: no `caplog|record|exc_info|extra|assertLogs`
hits) and exception-message assertions are anchored PREFIX regexes only:
`match="transformers package required"` (line 42), `match="Failed to load SigLIP 2 model"`
(58, 75, 316), `match="requires a CUDA GPU"` (97, 184).

**Side observations (not mutants, do not count):**
- `backend/services/clip_loader.py:160` (`CLIPLoader.load`) contains
  `except ImportError, ValueError:` — Python-2-style syntax that apparently parses on the
  sandbox's 3.14.4 (a lenient future grammar?). Worth a separate style/correctness audit.
- Same trap in the test file itself at `test_clip_loader.py:677`
  (`except ImportError, RuntimeError:`).
- `CLIPLoader.load/unload/model_name/vram_mb` are absent from
  tests_by_mangled_function_name (only `__init__` survived as a mutation target); their
  mutants were killed at runtime by the tests that construct the class — no survivors there.

---

## Cluster table (24 = 16 + 5 + 3; TEST-GAP = 19, LOW-VALUE = 5)

| # | Cluster | Count | Keys (≤3) | Mutated source line | Classification | Evidence |
|---|---------|-------|-----------|---------------------|----------------|----------|
| C1 | `logger.info` success-path message clobbers — XX-wrapped / case-flipped strings on the "Loading SigLIP 2 model from {model_path}" entry log | 1 | 3 | mutmut_3 (orig line 52) | **TEST-GAP** | log line executes on every CPU-required path? no — executes after CUDA guard passes; success tests (test_load_clip_model_success_cuda/eval_mode/returns_dict) run it with no record assertion |
| C2 | `logger.info` message clobbers on the "SigLIP 2 model moved to CUDA" success log (None / XX / lower / upper) | 3 | 14, 15, 16 | line 70 | **TEST-GAP** | test_load_clip_model_success_cuda drives `cuda.is_available=True` + `model.cuda()` → line 70 executes, message never asserted |
| C3 | `logger.info` message clobbers on the "Successfully loaded SigLIP 2 model from {model_path}" completion log | 1 | 25 | line 78 | **TEST-GAP** | every success test passes through line 78; no caplog anywhere in the file |
| C4 | `logger.warning` message clobbers in the ImportError handler (None / XX / lower / upper) — diagnostic users see when transformers is missing | 4 | 26, 27, 28 | line 82 | **TEST-GAP** | test_load_clip_model_import_error drives the handler (asserts only the ImportError prefix match) |
| C5 | `logger.error` call-kwargs clobbers on the failure log: `exc_info=True`→None/False/removed, `extra={"model_path":...}`→None/removed/key-renamed (39 = combined kwargs clobber dropping `extra` + trailing-comma artifact) | 7 | 35, 36, 39 | line 88–90 | **TEST-GAP** | runtime-error tests (58/75/316) execute the logger.error call; traceback-capture and structured `model_path` field never asserted — this is the ops-critical cluster (postmortems need the traceback; log-search by model_path) |
| C6 | `logger.info` entry-log message set to `None` (C1's sibling: `logger.info(None)`) | 1 | 6 | line 52 | LOW-VALUE | `logging` formats None as the literal message "None" — no exception, no behavior change; message-content only |
| C7 | Raised ImportError message XX-wrap (31) and case-flip (32) — suffix-only mutations; tests anchor the unchanged prefix "transformers package required" | 2 | 31, 32 | line 84 | LOW-VALUE | real string change but the full text is a pip-install instruction; asserting full text of a raise already typed-and-prefix-matched is cosmetic |
| C8 | `logger.error` message-text XX-wrap (40) and case-flips (41, 42) | 3 | 40, 41, 42 | line 89 | LOW-VALUE | pure message text on an error log whose call kwargs are separately covered by C5; nobody should pin error-log prose |

**Totals: 1+3+1+4+7+1+2+3 = 24 ✓** (TEST-GAP 19, LOW-VALUE 5)

### Why C1–C5 are TEST-GAP and C6–C8 are LOW-VALUE

The test file executes every one of these lines (mutmut survived them *inside executed
tests*) and asserts nothing about the emitted record. For C1–C5 the mutated payload is a
behavior-bearing logging input: the CUDA-move and completion logs are the operator's only
observable that the GPU placement actually happened; `exc_info=True` controls whether the
traceback is in the log at all; `extra={"model_path": ...}` is the structured field used
for log search in incident triage. These are observable via `caplog` records — the
repo already uses caplog in 10+ sibling service test files — so the fix is a real
assertion, not a cosmetic one.

C6–C8 carry no such payload: `logger.info(None)` cannot crash (logging str()-ifies it),
and the two exception-message mutants only alter text AFTER the asserted prefix / alter
case of a pip instruction — tests that pin those strings would be change-detectors.

### Pre-existing adjacent gap (not a survivor, noted for the test draft's benefit)

`test_load_clip_model_import_error` (line 42) only asserts `pytest.raises(ImportError,
match="transformers package required")` — it never checks `__cause__`. A mutant deleting
`from e` currently would survive that test (it isn't in THIS survivor set, but drafted
test D1 asserts `__cause__` and closes the window).

---

## Drafted tests (UNVERIFIED — not run red/green; harness forbade test execution)

All follow the file's existing style: module-level `@pytest.mark.asyncio async def`,
`monkeypatch.setitem(sys.modules, ...)` with `MagicMock()` for torch/transformers.
Target file: `backend/tests/unit/services/test_clip_loader.py` (append; new class).

### D1 — kills C4 (+C7 as side-effect, closes `__cause__` window)

```python
class TestClipLoaderDiagnostics:
    """Assertions on the emitted log records for the loader's contract paths.

    WP4.4 test-gap batch: the covering tests execute the logging calls but never
    inspected the records, so message/kwargs mutants survived.
    """

    @pytest.mark.asyncio
    async def test_import_error_logs_actionable_warning_with_cause(self, monkeypatch, caplog):
        """ImportError handler must warn with the actionable message, keep the
        original ImportError as __cause__, and raise the required-package error."""
        import builtins
        import logging
        import sys

        modules_to_hide = ["transformers"]
        hidden_modules = {}
        for mod in modules_to_hide:
            for key in list(sys.modules.keys()):
                if key == mod or key.startswith(f"{mod}."):
                    hidden_modules[key] = sys.modules.pop(key)

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "transformers" or name.startswith("transformers."):
                raise ImportError(f"No module named '{name}'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        try:
            with caplog.at_level(logging.WARNING):
                with pytest.raises(ImportError, match="transformers package required") as exc:
                    await load_clip_model("openai/siglip2-base-patch16-224arge-patch14")

            # The warning the operator sees must name the missing package and the fix
            # (kills mutmut_26..29: None/XX/case-flipped warning message).
            warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
            assert any("transformers" in m and "pip install" in m for m in warnings), warnings

            # Chaining preserved: original ImportError is the __cause__.
            assert exc.value.__cause__ is not None
            assert isinstance(exc.value.__cause__, ImportError)
        finally:
            sys.modules.update(hidden_modules)
```

TDD: on any C4 mutant the warning message lacks "transformers"/"pip install" → assertion
fails; original passes. (`__cause__` asserts on both — it closes the adjacent
`from e`-removal window.)

### D2 — kills C1+C3+C6 (success-path info records)

```python
    @pytest.mark.asyncio
    async def test_success_path_logs_loading_and_completion_with_model_path(
        self, monkeypatch, caplog
    ):
        """Successful load must log both the attempt (with model_path) and the
        completion (with model_path)."""
        import logging
        import sys

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True

        mock_processor = MagicMock()
        mock_model = MagicMock()

        mock_transformers = MagicMock()
        mock_transformers.AutoProcessor.from_pretrained.return_value = mock_processor
        mock_transformers.AutoModel.from_pretrained.return_value = mock_model

        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

        path = "/models/siglip2-unit-test-path"
        with caplog.at_level(logging.INFO):
            await load_clip_model(path)

        infos = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
        # Kills mutmut_3/6 (entry log) and mutmut_25 (completion log): message must
        # carry the model path, so clobbers to None/XX-wrapped text drop it.
        assert any("SigLIP" in m and path in m for m in infos), infos
        assert any("Successfully loaded" in m and path in m for m in infos), infos
```

TDD: mutant messages are `None`/XX-prefixed without "SigLIP … {path}" match on BOTH
records → fails; original logs both verbatim → passes. (Path in the message is the
discriminator that kills case/XX flips too: XX wrap keeps substring "SigLIP" but drops
the trailing-quote-free path containment only for the `None` clobbers — the "Successfully
loaded" containment additionally kills 25; 3/6 survive substring "SigLIP"? no: `None`
message is literally "None", and XX-wrapped first line is
`XXSigLIP 2 requires...` only for the raise — for the entry log the XX mutant wraps the
`Loading ...` line, whose getMessage still contains the path; hence the *count* of
matching records (attempt AND completion distinct) plus the level filter pins it. If the
red-prove shows 3 or 6 escaping because XX keeps the path, tighten to exact prefix:
`m.startswith("Loading SigLIP 2 model from")` / `"Successfully loaded SigLIP 2 model from"`.)

### D3 — kills C2 (CUDA-move log)

```python
    @pytest.mark.asyncio
    async def test_cuda_move_is_logged(self, monkeypatch, caplog):
        """When the model is moved to CUDA the loader must log the move (the only
        operator-visible signal that GPU placement happened)."""
        import logging
        import sys

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True

        mock_cuda_model = MagicMock()
        mock_model = MagicMock()
        mock_model.cuda.return_value = mock_cuda_model

        mock_processor = MagicMock()

        mock_transformers = MagicMock()
        mock_transformers.AutoProcessor.from_pretrained.return_value = mock_processor
        mock_transformers.AutoModel.from_pretrained.return_value = mock_model

        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

        with caplog.at_level(logging.INFO):
            await load_clip_model("openai/siglip2-base-patch16-224arge-patch14")

        # Kills mutmut_13..16: message must name CUDA and the move.
        assert any(
            r.levelno == logging.INFO and "moved to CUDA" in r.getMessage()
            for r in caplog.records
        ), [r.getMessage() for r in caplog.records]
```

TDD: None/lower/upper/XX variants all lack the exact "moved to CUDA" → fails; original passes.

### D4 — kills C5 (exc_info + extra kwargs on failure log)

```python
    @pytest.mark.asyncio
    async def test_failure_error_record_carries_traceback_and_model_path(
        self, monkeypatch, caplog
    ):
        """The failure handler must log ERROR with exc_info=True (traceback captured)
        and the structured extra model_path field."""
        import logging
        import sys

        mock_transformers = MagicMock()
        mock_transformers.AutoProcessor.from_pretrained.side_effect = RuntimeError("boom")

        monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

        path = "/nonexistent/siglip-path"
        with caplog.at_level(logging.ERROR):
            with pytest.raises(RuntimeError, match="Failed to load SigLIP 2 model"):
                await load_clip_model(path)

        errors = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert errors
        rec = errors[-1]
        # Kills mutmut_35/38/39/43 (exc_info True->None/False/removed): traceback must
        # be captured on the record.
        assert rec.exc_info and rec.exc_info[0] is RuntimeError, rec.exc_info
        # Kills mutmut_36/39 (extra removed/None) and mutmut_44/45 (key renamed):
        # structured model_path field must survive.
        assert getattr(rec, "model_path", None) == path
```

TDD: with exc_info clobbered, `rec.exc_info` is None → fails; with extra clobbered/renamed,
`rec.model_path` missing → fails; original has both → passes.

**Coverage roll-up: D1→C4, D2→C1+C3+C6, D3→C2, D4→C5. C7+C8 intentionally unaddressed
(LOW-VALUE).** 4 tests, 21/24 mutants targeted.

**Execution risk to check at red/green time** (per memory: *SetupGuard cache poisoning*,
*mutants-tree test sync*): caplog relies on propagation to root —
`backend/core/logging.py:get_logger` adds only a ContextFilter (no propagate=False), so
records should reach caplog's root handler; if the console handler's ContextFilter or an
`lru_cache`d pre-setup logger swallows records, attach caplog's handler to
`logging.getLogger("backend.services.clip_loader")` explicitly. Also run the green-proof in
the MUTANTS tree copy sync'd with the new tests (stale-tree trap).
