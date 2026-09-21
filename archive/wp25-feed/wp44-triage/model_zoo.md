# WP4.4 Triage Dossier — backend/services/model_zoo.py

**Snapshot frozen:** 2026-09-18 ~02:3x UTC. The survivor set grew while this dossier was built (130 → 141 → 185 survivors; the live run still had 4 keys unchecked at freeze). All counts are for the frozen set of **185 survivors** (`exit_code_by_key` == 0 in `mutants/backend/services/model_zoo.py.meta`). Artifacts: survivor list `/tmp/wp25/wp44-triage/model_zoo_survivors_final2.txt`, full diffs `model_zoo_diffs.txt` + `model_zoo_diffs2.txt` + `model_zoo_diffs3.txt`, cluster↔key map `model_zoo_clusters_final.json` (the table below is generated from this map — if the run finishes with different verdicts, fold the delta onto the map, don't re-type).

**Verdict:** TEST-GAP 78 / EQUIVALENT 104 / LOW-VALUE 3 (sums to 185). 13 drafted tests (all **UNVERIFIED**) cover the full TEST-GAP set.

**Covering test file (primary):** `backend/tests/unit/services/test_model_zoo.py` (2,499 lines; 46 of 55 mutmut-covered tests for this module's functions).
Key anchors: `TestModelZoo` L87, `TestModelManager` L166, `TestModelManagerMetrics` L570, `TestModelZooLoadFunctions` L1184, `TestPaddleocrAvailability` L1276, `TestOptionalDependencyHandling` L1305 (L1319 asserts only `pytest.raises` + `is_loaded` — it never inspects log levels), `TestConcurrentModelLoading` L1338.
Secondary: `backend/tests/unit/services/test_smoke_fire_loader.py:190-232` (`TestSmokeFireModelPriority` — lax `or`/`getattr` asserts), `test_model_zoo.py:1443/1753/2134` (config.path assertions for yolo-world/depth/vitpose — all falsy-`runtime_path` models), `test_vitpose_loader.py:1003`, `test_pet_classifier_loader.py`, `test_florence_loader.py`, `test_violence_loader.py:187`, `test_vehicle_damage_loader.py:657`.

**Source anchors:** `load_yolo_model` validation L177-200 + diagnostics L180-196; `_is_paddleocr_available` L262-267; `load_paddle_ocr` ctor L310-313; `_get_model_zoo_base_path` L347-349; `_resolve_model_path` L413-428; `_init_model_zoo` ModelConfig build L471-482; `_load_model` timeout L659-687, optdep classifier L689-704, duration metric L711-712; `unload` L835-837; `reload` L887-896.

---

## Cluster table (generated from `model_zoo_clusters_final.json`; counts sum to 185)

| Cluster | N | Class | Example keys (after `backend.services.model_zoo.`) |
|---|---|---|---|
| GAP:init-model-zoo-eviction-flags-strict | 20 | TEST-GAP | `x__init_model_zoo__mutmut_36`, `x__init_model_zoo__mutmut_37`, `x__init_model_zoo__mutmut_38` |
| GAP:paddleocr-ctor-kwargs-and-executor-call | 14 | TEST-GAP | `x_load_paddle_ocr__mutmut_11`, `x_load_paddle_ocr__mutmut_13`, `x_load_paddle_ocr__mutmut_14` |
| GAP:yolo-local-path-validation-guard | 9 | TEST-GAP | `x_load_yolo_model__mutmut_2`, `x_load_yolo_model__mutmut_3`, `x_load_yolo_model__mutmut_10` |
| GAP:optdep-error-classifier-or-terms-and-case | 9 | TEST-GAP | `xǁModelManagerǁ_load_model__mutmut_23`, `xǁModelManagerǁ_load_model__mutmut_25`, `xǁModelManagerǁ_load_model__mutmut_28` |
| GAP:yolo-missing-file-diagnostics-warning | 6 | TEST-GAP | `x_load_yolo_model__mutmut_11`, `x_load_yolo_model__mutmut_12`, `x_load_yolo_model__mutmut_15` |
| GAP:load-model-timeout-constant-and-duration-metric | 4 | TEST-GAP | `xǁModelManagerǁ_load_model__mutmut_11`, `xǁModelManagerǁ_load_model__mutmut_12`, `xǁModelManagerǁ_load_model__mutmut_63` |
| GAP:resolve-model-path-runtime-path-branch | 4 | TEST-GAP | `x__resolve_model_path__mutmut_1`, `x__resolve_model_path__mutmut_2`, `x__resolve_model_path__mutmut_4` |
| GAP:is-paddleocr-available-find-spec-arg | 3 | TEST-GAP | `x__is_paddleocr_available__mutmut_1`, `x__is_paddleocr_available__mutmut_2`, `x__is_paddleocr_available__mutmut_3` |
| GAP:model-zoo-base-path-env-var-name | 2 | TEST-GAP | `x__get_model_zoo_base_path__mutmut_5`, `x__get_model_zoo_base_path__mutmut_6` |
| GAP:reload-reference-count-restore | 2 | TEST-GAP | `xǁModelManagerǁreload__mutmut_16`, `xǁModelManagerǁreload__mutmut_17` |
| GAP:reload-stale-unload-and-cuda-clear | 2 | TEST-GAP | `xǁModelManagerǁreload__mutmut_6`, `xǁModelManagerǁreload__mutmut_7` |
| GAP:load-fn-invocation-path-arg | 1 | TEST-GAP | `xǁModelManagerǁ_load_model__mutmut_21` |
| GAP:resolve-model-path-empty-local-prefix | 1 | TEST-GAP | `x__resolve_model_path__mutmut_12` |
| GAP:unload-phantom-load-count-entry | 1 | TEST-GAP | `xǁModelManagerǁunload__mutmut_1` |
| LOW:pyroscope-tag-label-key | 2 | LOW-VALUE | `xǁModelManagerǁ_load_model__mutmut_14`, `xǁModelManagerǁ_load_model__mutmut_15` |
| LOW:paddle-importbranch-raise-message-toctou | 1 | LOW-VALUE | `x_load_paddle_ocr__mutmut_2` |
| EQ:load-model-error-log-message-kwarg | 23 | EQUIVALENT | `xǁModelManagerǁ_load_model__mutmut_38`, `xǁModelManagerǁ_load_model__mutmut_39`, `xǁModelManagerǁ_load_model__mutmut_50` |
| EQ:init-model-zoo-unreachable-default-branches | 22 | EQUIVALENT | `x__init_model_zoo__mutmut_45`, `x__init_model_zoo__mutmut_50`, `x__init_model_zoo__mutmut_77` |
| EQ:yolo-error-log-message-kwarg | 11 | EQUIVALENT | `x_load_yolo_model__mutmut_21`, `x_load_yolo_model__mutmut_27`, `x_load_yolo_model__mutmut_32` |
| EQ:paddle-error-log-message-kwarg | 7 | EQUIVALENT | `x_load_paddle_ocr__mutmut_27`, `x_load_paddle_ocr__mutmut_31`, `x_load_paddle_ocr__mutmut_34` |
| EQ:load-model-info-log-message-kwarg | 5 | EQUIVALENT | `xǁModelManagerǁ_load_model__mutmut_32`, `xǁModelManagerǁ_load_model__mutmut_33`, `xǁModelManagerǁ_load_model__mutmut_36` |
| EQ:unload-model-log-text | 5 | EQUIVALENT | `xǁModelManagerǁ_unload_model__mutmut_2`, `xǁModelManagerǁ_unload_model__mutmut_3`, `xǁModelManagerǁ_unload_model__mutmut_4` |
| EQ:yolo-importerror-warning-text | 4 | EQUIVALENT | `x_load_yolo_model__mutmut_17`, `x_load_yolo_model__mutmut_18`, `x_load_yolo_model__mutmut_20` |
| EQ:init-manager-log-text | 4 | EQUIVALENT | `xǁModelManagerǁ__init____mutmut_5`, `xǁModelManagerǁ__init____mutmut_6`, `xǁModelManagerǁ__init____mutmut_8` |
| EQ:unload-all-log-text | 4 | EQUIVALENT | `xǁModelManagerǁunload_all__mutmut_4`, `xǁModelManagerǁunload_all__mutmut_5`, `xǁModelManagerǁunload_all__mutmut_7` |
| EQ:init-model-zoo-summary-log | 4 | EQUIVALENT | `x__init_model_zoo__mutmut_99`, `x__init_model_zoo__mutmut_101`, `x__init_model_zoo__mutmut_103` |
| EQ:load-model-success-log-text | 3 | EQUIVALENT | `xǁModelManagerǁ_load_model__mutmut_9`, `xǁModelManagerǁ_load_model__mutmut_81`, `xǁModelManagerǁ_load_model__mutmut_82` |
| EQ:paddle-guard-log-text | 3 | EQUIVALENT | `x_load_paddle_ocr__mutmut_3`, `x_load_paddle_ocr__mutmut_4`, `x_load_paddle_ocr__mutmut_5` |
| EQ:paddle-importerror-log-text | 2 | EQUIVALENT | `x_load_paddle_ocr__mutmut_7`, `x_load_paddle_ocr__mutmut_8` |
| EQ:reload-pop-default-removed | 2 | EQUIVALENT | `xǁModelManagerǁreload__mutmut_8`, `xǁModelManagerǁreload__mutmut_10` |
| EQ:yolo-start-log-text | 1 | EQUIVALENT | `x_load_yolo_model__mutmut_1` |
| EQ:paddle-start-log-text | 1 | EQUIVALENT | `x_load_paddle_ocr__mutmut_10` |
| EQ:init-model-zoo-debug-log | 1 | EQUIVALENT | `x__init_model_zoo__mutmut_21` |
| EQ:reload-valid-reasons-join-sep | 1 | EQUIVALENT | `xǁModelManagerǁreload__mutmut_4` |
| EQ:reset-model-zoo-assigns-none | 1 | EQUIVALENT | `x_reset_model_zoo__mutmut_1` |
| **Totals** | **78 GAP / 104 EQ / 3 LOW = 185** | | |

### Per-cluster notes

- **GAP:init-model-zoo-eviction-flags-strict (20)** — `priority/preload/never_evict` values ARE present in models.yml for every registered entry, but the mutants damage the *read* (value replaced by `None`: 36/37/38/74/83/91; key renamed `None`/single-arg/`XX…XX`/UPPER: 75/79/80/84/88/89/92/96/97 → silently wrong defaults `"medium"`/`False`; kwarg dropped entirely: 46/47/48 → TypeError) or the wrapper (`bool(...)` → raw `'True'`/'False' string semantics). The line executes via every `get_model_zoo()` test, but `test_smoke_fire_loader.py:204` asserts `config.priority == "critical" or getattr(config, "never_evict", False)` — the `or` is satisfied by `never_evict=None`, and nothing strictly pins the trio. `None`/wrong flags silently disable never-evict and `BACKEND_MODEL_PRELOAD` startup behavior without any TypeError. → **D4** kills all 20 (kwarg-drop members 46/47/48 kill as a construction TypeError in `setup_method`).
- **GAP:paddleocr-ctor-kwargs-and-executor-call (14)** — only failure paths tested (`test_model_zoo.py:1233,1254`, `:1319`); paddleocr is uninstalled here so the success path (ctor kwargs `use_angle_cls=True, lang="en", show_log=False` + `run_in_executor(None, lambda)`) never executes under test. Kwargs change real OCR behavior (rotated-text, English plates, log noise); executor damage breaks the non-blocking contract. → **D3**.
- **GAP:yolo-local-path-validation-guard (9)** — `and`→`or`, `"/"`→`"XX/XX"`/`not in`, http-prefix damage, `exists()` flip. Both existing tests *bypass* the guard: the ImportError test's `__import__` mock raises at L170 before validation; the runtime-error test uses `"invalid/path"` where every mutant behaves identically (missing + not-http → RuntimeError at both). → **D2a**.
- **GAP:optdep-error-classifier-or-terms-and-case (9)** — `or`→`and`, search-terms XX/UPPER, `in`→`not in`, `.lower()`→`.upper()`, `str(e)`→`str(None)`. The documented INFO-vs-ERROR contract for optional deps (module docstring L273-278, NEM-2540) is never asserted — `:1319` catches the exception and checks `is_loaded` only. Every mutant silently flips OCR-missing handling to ERROR-with-traceback (log spam + false alarms). → **D1**.
- **GAP:yolo-missing-file-diagnostics-warning (6)** — `parent_dir`→None, `Path(None).is_dir()`, warning messages→None. The diagnostics are the operator-facing payload of the guard branch. → **D2b**.
- **GAP:load-model-timeout-constant-and-duration-metric (4)** — `_MODEL_LOAD_TIMEOUT = 20.0`→None/21.0, `timeout=`→None: the timeout branch never executes under tests, and `timeout=None` silently removes the event-loop protection the comment L654-658 promises. Member 63 flips `perf_counter() - start` to `+ start` → `MODEL_LOAD_DURATION` gauge records ~1e9 s; existing asserts are all `>=` lower bounds (`:604-606`, `:811`). → **D5**.
- **GAP:resolve-model-path-runtime-path-branch (4)** + **empty-local-prefix (1)** — truthy `runtime_path` branch executes in every zoo init (4 registered entries: `piq`, `fast-alpr`, `model-zoo/fashion-siglip`, `ultralytics/yolo26`) but only falsy-branch models have `config.path` assertions. Damaged key lookups fall through to the directory branch → silently wrong load paths. → **D6**.
- **GAP:is-paddleocr-available-find-spec-arg (3)** — all three existing tests stub `find_spec` with a fixed return and `autospec=True`; the *argument* is never observed. Damaged names → `find_spec` returns None → OCR permanently "unavailable". → **D8**.
- **GAP:model-zoo-base-path-env-var-name (2)** — `grep -r MODEL_ZOO_PATH backend/tests/` → **zero hits anywhere in the test suite**. Wrong env name silently reverts deployments to the baked-in `/models/model-zoo`. Per CLAUDE.md the env-var/port contract is load-bearing. → **D7**.
- **GAP:reload-reference-count-restore (2)** — `_load_counts[model_name] = 1` → `None`/`2`. Tests do `preload → reload → unload` and never read `get_status()["load_counts"]` after a reload; `=2` strands a phantom ref, `=None` breaks later `count - 1` arithmetic. → **D9**.
- **GAP:reload-stale-unload-and-cuda-clear (2)** — `if model_name in` → `not in`, `_unload_model(None)`. The stale model is never actually dropped → VRAM double-allocates (the exact failure `reload` exists to fix) and `cuda.empty_cache()` is skipped. No test asserts stale-model release or cache clearing for reload (only for context-load / unload_all: `:339`, `:365`). → **D10**.
- **GAP:load-fn-invocation-path-arg (1)** — `config.load_fn(config.path)` → `load_fn(None)`. Every mock loader in the suite ignores its arg. Kills real loading of every model (no config path is falsy). → **D12**.
- **GAP:unload-phantom-load-count-entry (1)** — `unload()`'s `_load_counts.pop(model_name, None)` → `pop(None, None)` leaves a phantom count visible in `get_status()` and corrupting `load()`'s refcount on the next cycle. `test_preload_and_unload` (`:266`) checks `is_loaded` only. → **D11**.
- **LOW:pyroscope-tag-label-key (2)** — pyroscope-io is in `uv.lock` but NOT installed in this sandbox (`find_spec('pyroscope')` → None), so the tagged branch (L664-670) never executes in the test env — unkillable without stubbing the module for a profiling label. Not worth writing.
- **LOW:paddle-importbranch-raise-message-toctou (1)** — TOCTOU-race branch (L318-326) that re-raises with chained cause; message text only. Not worth writing.
- **EQ rows** — log/kwarg text tweaks in the six loader/manager functions (~90 mutants): raised-exception behavior asserted, log payloads never inspected; asserting exact log strings is behavior nobody should have to assert. Plus: `x_reset_model_zoo__mutmut_1` (`MODEL_ZOO = None`) is equivalent because `get_model_zoo()` guards on truthiness (`if not MODEL_ZOO`); `reload` pop-default twins are unreachable (`_load_model` always sets a count first); `reload` join-sep only touches the ValueError detail matched as prefix (`:731`); `_init_model_zoo__mutmut_77` (`str(m.get("priority"))`) and the **21 unreachable default-branch** members (`get("XXcategoryXX","other")` etc.) are dead against current models.yml — every registered entry defines all six defaulted keys (audit below).

### The models.yml audit that splits the `_init_model_zoo` family

`models.yml` has 30 entries; 27 are registered (`service: backend|both` **and** in `_LOADER_MAP`). All 27 define `category/vram_mb/enabled/priority/preload/never_evict` explicitly — the only two entries omitting them (`nemotron-3-nano…` service `ai-llm`, `florence-2-base` service `ai-gateway`) are filtered out before any `ModelConfig` is constructed (L462/L466). So default-value mutants are EQUIVALENT *for today's data* (dead branch), while key-replacement mutants damage live data → TEST-GAP. **If models.yml ever grows a registered entry without these keys, the 22 EQ members wake up as real config bugs** — D4 already pins the eviction trio strictly; add `config.enabled is True` there if the data changes.

---

## Drafted tests — UNVERIFIED, not yet run red/green

All target `backend/tests/unit/services/test_model_zoo.py`. Existing imports (L15-42: `asyncio`, `Any`, `MagicMock`/`patch`, `pytest`, `ModelManager`, `get_model_config`, `reset_model_zoo`, `reset_model_manager`) suffice; D5 additionally does a local `import backend.services.model_zoo as mz`. Style follows the file: class-scoped, `setup/teardown_method` resetting globals, `patch.object(get_model_config(...), "load_fn", …)`, `pytest.mark.asyncio` explicit.

**TDD procedure (one line, per test):** apply the cluster's mutant (or `mutmut run` that single key) → the named assertion fails (or the test errors for TypeError members); restore original → passes; re-run the whole class twice to confirm no global-registry leakage.

### D1 — kills GAP:optdep-error-classifier (9)

```python
class TestOptionalDependencyLogRouting:
    """INFO-vs-ERROR routing of optional-dependency load failures is the
    documented graceful-degradation contract (load_paddle_ocr docstring,
    NEM-2540); existing tests only catch the exception."""

    def setup_method(self) -> None:
        reset_model_zoo()
        reset_model_manager()

    def teardown_method(self) -> None:
        reset_model_zoo()
        reset_model_manager()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "dep_message",
        [
            "paddleocr package not installed",  # exercises the 'not installed' arm alone
            "this dependency is optional",       # exercises the 'optional' arm alone
        ],
    )
    async def test_load_model_logs_info_not_error_for_optional_dep(
        self, dep_message: str
    ) -> None:
        manager = ModelManager()

        async def missing_dep_load(path: str) -> Any:
            raise RuntimeError(dep_message)

        mock_logger = MagicMock()
        with (
            patch.object(
                get_model_config("yolo11-license-plate"), "load_fn", missing_dep_load
            ),
            patch("backend.services.model_zoo.logger", mock_logger),
            pytest.raises(RuntimeError, match=dep_message),
        ):
            await manager.preload("yolo11-license-plate")

        info_msgs = [str(c.args[0]) for c in mock_logger.info.call_args_list if c.args]
        err_msgs = [str(c.args[0]) for c in mock_logger.error.call_args_list if c.args]
        assert any("unavailable" in m for m in info_msgs), (
            f"optional-dep failure '{dep_message}' must log INFO with 'unavailable', "
            f"got INFO={info_msgs}"
        )
        assert not any("Failed to load model" in m for m in err_msgs), (
            f"optional-dep failure '{dep_message}' must not reach the ERROR branch"
        )
```

Red: the `and`-flip (25), `.upper()` (23), and each XX/UPPER/`not in` term mutant route at least one param to `logger.error("Failed to load model", exc_info=True)` → second assert fails (str(None) mutant 24 fails both). Green: both params route INFO. Uses a mocked `model_zoo.logger` rather than `caplog` because `backend.core.logging` is structlog-wrapped and caplog propagation is unproven.

### D2a — kills GAP:yolo-local-path-validation-guard (9)

```python
    @pytest.mark.asyncio
    async def test_load_yolo_model_missing_local_file_raises_runtime_error(
        self, tmp_path: Any
    ) -> None:
        """Local paths (contain '/', not http) are pre-validated: a missing file
        raises RuntimeError('Model file not found') before ultralytics loads."""
        from backend.services.model_zoo import load_yolo_model

        missing = str(tmp_path / "models" / "yolo11-face.pt")
        with patch.dict("sys.modules", {"ultralytics": MagicMock(YOLO=MagicMock())}):
            with pytest.raises(RuntimeError, match="Model file not found"):
                await load_yolo_model(missing)

    @pytest.mark.asyncio
    async def test_load_yolo_model_skips_validation_for_non_local_paths(self) -> None:
        """Repo-style names (no '/') and http URLs must NOT be pre-validated —
        ultralytics resolves those itself."""
        from backend.services.model_zoo import load_yolo_model

        mock_yolo_cls = MagicMock()
        mock_model = MagicMock()
        mock_yolo_cls.return_value = mock_model
        fake_torch = MagicMock()
        fake_torch.cuda.is_available.return_value = False
        with patch.dict(
            "sys.modules",
            {"ultralytics": MagicMock(YOLO=mock_yolo_cls), "torch": fake_torch},
        ):
            for repo_style in ("some-org/YOLOv11n-face", "http://example.com/y.pt"):
                assert await load_yolo_model(repo_style) is mock_model
```

Red: guard-skip mutants (3 `XX/XX`, 4 `not in`, 5 `startswith` flip, 9 `exists()` flip) let the mocked YOLO return cleanly in test 1 → `pytest.raises` fails. Over-validate mutants (2 `or`, 6 `startswith(None)`, 7 XX, 8 `"HTTP"`) make test 2 raise inside the guard (or TypeError for 6). Green: original validates `missing` and passes both repo-style paths through.

### D2b — kills GAP:yolo-missing-file-diagnostics-warning (6)

```python
    @pytest.mark.asyncio
    async def test_load_yolo_model_warns_with_available_model_files(
        self, tmp_path: Any
    ) -> None:
        """Branch A (parent dir exists): the warning must list the sibling
        .pt/.pth/.onnx files — that filtered listing is the diagnostic's payload."""
        from backend.services.model_zoo import load_yolo_model

        (tmp_path / "dir").mkdir()
        (tmp_path / "dir" / "a.pt").write_bytes(b"")
        (tmp_path / "dir" / "b.txt").write_text("")
        missing = str(tmp_path / "dir" / "ghost.pt")

        mock_logger = MagicMock()
        with (
            patch("backend.services.model_zoo.logger", mock_logger),
            pytest.raises(RuntimeError, match="Model file not found"),
        ):
            await load_yolo_model(missing)

        warn_msgs = [str(c.args[0]) for c in mock_logger.warning.call_args_list if c.args]
        assert any(
            "Available model files" in m and "['a.pt']" in m for m in warn_msgs
        ), f"warning must list exactly the .pt/.onnx siblings, got {warn_msgs}"

    @pytest.mark.asyncio
    async def test_load_yolo_model_warns_with_mount_hint_when_dir_missing(
        self, tmp_path: Any
    ) -> None:
        """Branch B (no parent dir): the warning must carry the container-mount
        and download hint."""
        from backend.services.model_zoo import load_yolo_model

        missing = str(tmp_path / "ghosts" / "ghost.pt")
        mock_logger = MagicMock()
        with (
            patch("backend.services.model_zoo.logger", mock_logger),
            pytest.raises(RuntimeError, match="Model file not found"),
        ):
            await load_yolo_model(missing)

        warn_msgs = [str(c.args[0]) for c in mock_logger.warning.call_args_list if c.args]
        assert any("does not exist" in m for m in warn_msgs), warn_msgs
```

Real `tmp_path` files — no `Path` stubbing. Red: 11/12/13 (`parent_dir`→None variants) break the dir branch → mount-hint warning instead of the sibling list → first test fails; 14 (`Path(None).is_dir()`) raises/`False` → same; 15/16 (warning payloads→None) fail both asserts. Green: `tmp_path` parent exists and yields `['a.pt']`.

### D3 — kills GAP:paddleocr-ctor-kwargs-and-executor-call (14)

```python
    @pytest.mark.asyncio
    async def test_load_paddle_ocr_constructs_with_expected_options(self) -> None:
        """PaddleOCR is uninstalled in CI so its success path never runs under
        test — pin the ctor contract: use_angle_cls=True (rotated plates),
        lang='en' (deliberate), show_log=False (quiet), constructed off the
        event loop via run_in_executor (the returned model proves the hop)."""
        from backend.services.model_zoo import load_paddle_ocr

        mock_module = MagicMock()
        mock_ctor = MagicMock()
        mock_instance = MagicMock()
        mock_ctor.return_value = mock_instance
        mock_module.PaddleOCR = mock_ctor

        with (
            patch(
                "backend.services.model_zoo._is_paddleocr_available",
                return_value=True,
                autospec=True,
            ),
            patch.dict("sys.modules", {"paddleocr": mock_module}),
        ):
            model = await load_paddle_ocr("config/path")

        assert model is mock_instance
        mock_ctor.assert_called_once_with(use_angle_cls=True, lang="en", show_log=False)
```

Red: kwarg mutants (17-26) fail `assert_called_once_with`; executor mutants (11 `loop=None`, 13 lambda→None, 14 executor-arg drop, 15 call drop) raise TypeError/AttributeError caught by the generic handler → RuntimeError → test errors before the assert. Green: original constructs with exactly those kwargs on the executor thread.

### D4 — kills GAP:init-model-zoo-eviction-flags-strict (20)

```python
class TestModelZooEvictionFlags:
    """models.yml is the single source of truth for VRAM eviction/preload flags.
    smoke-fire-yolov8n is the only registered entry with priority=critical /
    preload=true / never_evict=true (models.yml L406-410) and the existing
    assert there is an `or` form that None still satisfies. These feed the
    eviction logic and the BACKEND_MODEL_PRELOAD startup pass — a dropped
    str()/bool() wrapper or damaged key read silently disables both."""

    def setup_method(self) -> None:
        reset_model_zoo()

    def teardown_method(self) -> None:
        reset_model_zoo()

    def test_smoke_fire_eviction_fields_are_strictly_typed(self) -> None:
        config = get_model_config("smoke-fire-yolov8n")
        assert config is not None
        assert type(config.priority) is str
        assert config.priority == "critical"
        assert config.preload is True       # bool True, not None / not 'True'
        assert config.never_evict is True   # bool True, not None / not 'True'
        assert type(config.category) is str
        assert config.category == "detection"
```

Red: key-damage mutants yield `"medium"`/`False`/`None`/`'False'`; kwarg-drop members (46/47/48) raise TypeError in `setup_method`'s `reset_model_zoo()` → test errors. Green: original types/values match.

### D5 — kills GAP:load-model-timeout-constant-and-duration-metric (4)

```python
    @pytest.mark.asyncio
    async def test_load_model_applies_20s_timeout_constant(self) -> None:
        """The hard load timeout must stay exactly 20s; timeout=None silently
        removes the event-loop protection promised at L654-658."""
        import backend.services.model_zoo as mz

        captured: dict[str, Any] = {}

        async def spy_wait_for(awaitable: Any, timeout: float | None = None) -> Any:
            captured["timeout"] = timeout
            awaitable.close()
            return MagicMock()

        manager = ModelManager()

        async def dummy_load(path: str) -> Any:
            return MagicMock()

        with (
            patch.object(mz.asyncio, "wait_for", spy_wait_for),
            patch.object(
                get_model_config("yolo11-license-plate"), "load_fn", dummy_load
            ),
        ):
            async with manager.load("yolo11-license-plate"):
                pass

        assert captured["timeout"] == 20.0

    @pytest.mark.asyncio
    async def test_load_duration_metric_is_a_realistic_duration(self) -> None:
        """MODEL_LOAD_DURATION must record a *duration* (perf_counter delta),
        not an absolute clock reading (the - -> + mutant records ~1e9 s)."""
        from backend.core.metrics import MODEL_LOAD_DURATION

        manager = ModelManager()

        async def slowish_load(path: str) -> Any:
            await asyncio.sleep(0.01)
            return MagicMock()

        with patch.object(get_model_config("yolo11-face"), "load_fn", slowish_load):
            async with manager.load("yolo11-face"):
                pass

        value = MODEL_LOAD_DURATION.labels(model="yolo11-face")._value.get()
        assert 0.01 <= value < 10.0
```

Red: 11/12/18 break the equality (`None`/`21.0`/`None`); 63 records ~1e9 → `< 10.0` fails. Green: 20.0 and a sub-second delta.

### D6 — kills GAP:resolve-model-path-runtime-path-branch (4) + empty-local-prefix (1)

```python
class TestResolveModelPathContracts:
    """runtime_path is priority 1 in _resolve_model_path and the sentinel
    entries (fast-alpr/piq/…) depend on it being used VERBATIM — damaged key
    lookups silently fall through to the base_path join and hand loaders a
    nonexistent directory. falsy local_path must fall back to base_path."""

    def test_runtime_path_wins_verbatim(self) -> None:
        from backend.services.model_zoo import _resolve_model_path

        sentinel = {"runtime_path": "fast-alpr", "local_path": "model-zoo/fast-alpr"}
        assert _resolve_model_path(sentinel, "/models/model-zoo") == "fast-alpr"

    def test_empty_local_path_falls_back_to_base(self) -> None:
        from backend.services.model_zoo import _resolve_model_path

        assert _resolve_model_path({"local_path": None}, "/models/model-zoo") == (
            "/models/model-zoo"
        )
        assert _resolve_model_path({}, "/models/model-zoo") == "/models/model-zoo"

    def test_registry_sentinel_paths(self) -> None:
        """Tripwire for the whole branch against real models.yml data."""
        assert get_model_config("fast-alpr").path == "fast-alpr"
```

Red: 1/2/3 fall through to the joined directory → assertion fails; 4 returns `"None"`; 12 yields `"/models/model-zoo/XXXX"`. Green: verbatim + base fallback.

### D7 — kills GAP:model-zoo-base-path-env-var-name (2)

```python
class TestModelZooBasePathEnv:
    """MODEL_ZOO_PATH is the container-mount override (the .env/env contract is
    load-bearing per CLAUDE.md); a renamed lookup silently reverts every
    deployment to the baked-in default."""

    def test_env_var_name_is_exact(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from backend.services.model_zoo import _get_model_zoo_base_path

        monkeypatch.setenv("MODEL_ZOO_PATH", "/mnt/custom-models")
        assert _get_model_zoo_base_path() == "/mnt/custom-models"

    def test_default_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from backend.services.model_zoo import _get_model_zoo_base_path

        monkeypatch.delenv("MODEL_ZOO_PATH", raising=False)
        assert _get_model_zoo_base_path() == "/models/model-zoo"
```

### D8 — kills GAP:is-paddleocr-available-find-spec-arg (3)

```python
    def test_is_paddleocr_available_queries_exact_module_name(self) -> None:
        from backend.services.model_zoo import _is_paddleocr_available

        seen: list[Any] = []

        def fake_find_spec(name: Any) -> Any:
            seen.append(name)
            return MagicMock() if name == "paddleocr" else None

        with patch("importlib.util.find_spec", side_effect=fake_find_spec, autospec=True):
            assert _is_paddleocr_available() is True
        assert seen == ["paddleocr"]
```

Red: `find_spec(None)`/XX/UPPER names → fake returns None → availability False → first assert fails (name recorded too). Green.

### D9 — kills GAP:reload-reference-count-restore (2)

```python
    @pytest.mark.asyncio
    async def test_reload_sets_single_reference_count(self) -> None:
        """After reload() the model is owned exactly once (reload == preload
        ownership); get_status() is the public window onto _load_counts."""
        manager = ModelManager()
        mock_model = MagicMock()

        async def mock_load(path: str) -> Any:
            return mock_model

        with patch.object(
            get_model_config("yolo11-license-plate"), "load_fn", mock_load
        ):
            await manager.preload("yolo11-license-plate")
            await manager.reload("yolo11-license-plate", "oom")
            assert manager.get_status()["load_counts"] == {"yolo11-license-plate": 1}

            await manager.unload("yolo11-license-plate")
            assert manager.get_status()["load_counts"] == {}
            assert not manager.is_loaded("yolo11-license-plate")
```

Red: `=2` → status dict mismatch; `=None` → next `count - 1` TypeErrors inside unload.

### D10 — kills GAP:reload-stale-unload-and-cuda-clear (2)

```python
    @pytest.mark.asyncio
    async def test_reload_unloads_stale_model_and_clears_cuda_cache(self) -> None:
        """reload() must drop the stale instance (else VRAM double-allocates —
        the exact failure reload exists to fix) and clear the CUDA cache."""
        manager = ModelManager()
        models = iter([MagicMock(name="first-load"), MagicMock(name="second-load")])

        async def mock_load(path: str) -> Any:
            return next(models)

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True

        with (
            patch.object(get_model_config("yolo11-face"), "load_fn", mock_load),
            patch.dict("sys.modules", {"torch": mock_torch}),
        ):
            await manager.preload("yolo11-face")
            mock_torch.cuda.empty_cache.assert_not_called()

            await manager.reload("yolo11-face", "crash")
            mock_torch.cuda.empty_cache.assert_called_once()
            assert manager.is_loaded("yolo11-face")
```

Red: 6 (guard flip) skips the unload branch → `empty_cache` never called; 7 (`_unload_model(None)`) hits the not-in-dict early return → same → `assert_called_once` fails.

### D11 — kills GAP:unload-phantom-load-count-entry (1)

```python
    @pytest.mark.asyncio
    async def test_unload_removes_load_count_entry(self) -> None:
        manager = ModelManager()
        mock_model = MagicMock()

        async def mock_load(path: str) -> Any:
            return mock_model

        with patch.object(get_model_config("yolo11-face"), "load_fn", mock_load):
            await manager.preload("yolo11-face")
            await manager.unload("yolo11-face")

        assert manager.get_status()["load_counts"] == {}
```

### D12 — kills GAP:load-fn-invocation-path-arg (1)

```python
    @pytest.mark.asyncio
    async def test_load_model_passes_configured_path_to_load_fn(self) -> None:
        manager = ModelManager()
        mock_model = MagicMock()
        seen_paths: list[Any] = []

        async def capture_load(path: Any) -> Any:
            seen_paths.append(path)
            return mock_model

        config = get_model_config("yolo11-license-plate")
        assert config is not None
        with patch.object(config, "load_fn", capture_load):
            async with manager.load("yolo11-license-plate"):
                pass

        assert seen_paths == [config.path]
```

---

## Coverage roll-up

| Draft | Kills cluster | N |
|---|---|---|
| D1 | GAP:optdep-error-classifier-or-terms-and-case | 9 |
| D2a | GAP:yolo-local-path-validation-guard | 9 |
| D2b | GAP:yolo-missing-file-diagnostics-warning | 6 |
| D3 | GAP:paddleocr-ctor-kwargs-and-executor-call | 14 |
| D4 | GAP:init-model-zoo-eviction-flags-strict | 20 |
| D5 | GAP:load-model-timeout-constant-and-duration-metric | 4 |
| D6 | GAP:resolve-model-path-runtime-path-branch + empty-local-prefix | 5 |
| D7 | GAP:model-zoo-base-path-env-var-name | 2 |
| D8 | GAP:is-paddleocr-available-find-spec-arg | 3 |
| D9 | GAP:reload-reference-count-restore | 2 |
| D10 | GAP:reload-stale-unload-and-cuda-clear | 2 |
| D11 | GAP:unload-phantom-load-count-entry | 1 |
| D12 | GAP:load-fn-invocation-path-arg | 1 |
| **total** | | **78 = full TEST-GAP set** |

Not worth writing: the 3 LOW-VALUE (pyroscope module absent in the run env; TOCTOU-branch message text).

**Residual risk notes:** (a) 4 keys unchecked at freeze — any that newly *survive* are near-certainly more `_init_model_zoo` default-branch or log-text tweaks (same EQUIVALENT verdicts); fold via `model_zoo_clusters_final.json`. (b) EQ:init-model-zoo-unreachable-default-branches is data-dependent — see the models.yml audit; re-audit if models.yml changes shape. (c) D5's first test patches `mz.asyncio.wait_for` module-wide — if the pyroscope branch is live in CI (`pyroscope-io` installed per uv.lock) the spy covers both call sites identically; if it proves flaky, assert on `timeout` via `caplog` of the timeout log instead. (d) D1's `str(c.args[0]) for c in … if c.args` guards the structlog call-shape; if `logger.info` is called with kwargs-only in some path, the guard skips it without failing.
