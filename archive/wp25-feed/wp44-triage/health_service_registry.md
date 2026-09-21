# WP4.4 Triage Dossier — backend/services/health_service_registry.py

- **Source:** `backend/services/health_service_registry.py` (655 lines)
- **Mutants:** 280 total | 192 killed | **88 survivors** (exit_code 0)
- **Covering test file (sole):** `backend/tests/unit/services/test_health_service_registry.py` (381 lines)
  - `TestHealthCircuitBreaker` :26–110, `TestHealthServiceRegistry` :113–294, `TestDIContainerIntegration` :343–381
- Diff source: manual diff of `mutants/backend/services/health_service_registry.py` clobbered variants vs originals (per-key line mapping via AST). No test execution performed.

## Why almost everything lives in one test file

The module has ONE test file. Its blind spots map 1:1 onto the survivors:
1. Every mock service is a `MagicMock` — attribute lookups (`getattr(x, "running", default)`, `mock.get_async(...)`) never exercise defaults/args.
2. Only gpu_monitor + cleanup_service are ever passed to `__init__`/`get_worker_statuses` (broadcaster/file_watcher/performance_collector/health_event_emitter never asserted when set).
3. Pipeline status only ever uses the **legacy** `{"state": ...}` shape; the NEM-5375 **multi-worker** `{"count": N, "workers": [...]}` shape is never exercised.
4. Pipeline workers are only ever `"running"` or `"stopped"` — never `"error"`, never a missing `"state"` key, never a missing section.
5. Circuit-breaker timeout tests use `reset_timeout=timedelta(0)` and never re-fail after reset (post-reset counter never observed).

## Cluster table (counts sum to 88)

| # | Pattern (function @ source line) | Count | Keys (≤3) | Class | Note |
|---|---|---|---|---|---|
| 1 | Log-message text mutations — `logger.info/debug/warning` payload replaced by None/XX/lower/UPPER (`__init__`:234, `register_gpu_monitor`:306, `register_cleanup_service`:315, `record_failure`:141-145) | 13 | `__init___mutmut_12`, `register_gpu_monitor__mutmut_3`, `record_failure__mutmut_14` | EQUIVALENT | Pure log strings; no observable behavior. |
| 2 | `WorkerStatus.message` conditional `None if is_running else "…"` broken: kwarg dropped, `and False`/`or True` injected, `message=None`, text case/wrap (408, 419, 474, 502, 514) | 16 | `get_worker_statuses__mutmut_16`, `__mutmut_94`, `__mutmut_157` | TEST-GAP | Tests assert the message only for cleanup-not-running and analysis-stopped; the gpu-not-running, detection-stopped, analysis-running and timeout-stopped message slots are never asserted. |
| 3 | `getattr(svc, "running", False)` default mutated to None/True/removed, or receiver → None (gpu 403, cleanup 414) | 7 | `get_worker_statuses__mutmut_12`, `__mutmut_29`, `__mutmut_37` | TEST-GAP | MagicMock always HAS `.running`, so defaults are unreachable; cleanup is never set running=True. Need a plain object without `.running` + cleanup.running=True. |
| 4 | Multi-worker branch `if *_info.get("workers"):` key mutated → NEM-5375 shape silently falls through to legacy path (gws 455/483, are_critical 542/554) | 12 | `get_worker_statuses__mutmut_69`, `…__mutmut_102`, `are_critical_…_mutmut_24` | TEST-GAP | The headline NEM-5375 multi-worker aggregation is COMPLETELY untested in both functions. |
| 5 | `manager_status.get("workers", {})` default → None/removed → `"detection" in None` raises TypeError when status lacks "workers" (gws 448, are_critical 533) | 4 | `get_worker_statuses__mutmut_58`, `are_critical_…_mutmut_6` | TEST-GAP | Manager returning `{}` is never tested; mutant crashes instead of reporting unhealthy. |
| 6 | are_critical section defaults `detection_running/analysis_running = False` → None/True (539, 551) | 4 | `are_critical_…_mutmut_17`, `__mutmut_33` | TEST-GAP | Workers-dict missing a whole section is never tested; None leaks out of the return (`None and x` → None, `is False` would fail). |
| 7 | `OPERATIONAL_STATES = {"running","error"}` — "error" → "XXerrorXX"/"ERROR" (536) | 2 | `are_critical_…_mutmut_14` | TEST-GAP | Documented behavior (error = will-resume operational) never asserted with an `"error"` worker. |
| 8 | Legacy fallback `.get("state", "stopped")` default → None/removed/"XXstopped"/"STOPPED" (detection 468, analysis 496, timeout 508) | 12 | `get_worker_statuses__mutmut_74`, `__mutmut_113`, `__mutmut_141` | TEST-GAP | Worker dict without a `"state"` key never tested; message string is user-facing API content. |
| 9 | Legacy lookup key arg `analysis_info.get("state",…)` → None/"XXstateXX"/"STATE" (496) | 3 | `get_worker_statuses__mutmut_106` | TEST-GAP | Mutant reads the wrong key → an actually-running analysis worker is reported stopped. Test never has analysis legacy `state="running"`. |
| 10 | Legacy comparison `analysis_state == "running"` → `"XXrunningXX"`/`"RUNNING"` (497) | 2 | `get_worker_statuses__mutmut_116` | TEST-GAP | Same blind spot: running analysis never exercised via legacy path. |
| 11 | Registration presence check `if self._x is not None:` → `is None` (broadcaster 424, file_watcher 435) | 2 | `get_worker_statuses__mutmut_52` | TEST-GAP | No test registers a broadcaster/file_watcher AND no test asserts the status list of an empty registry (mutant emits phantom entries for unregistered services). |
| 12 | `__init__` stores constructor arg → None (`_system_broadcaster` 224, `_file_watcher` 225, `_performance_collector` 230, `_health_event_emitter` 231) | 4 | `__init____mutmut_3`, `__init____mutmut_10` | TEST-GAP | `test_initialization_with_services` (:131) only checks gpu + cleanup; 4 of 10 constructor args are never identity-checked. |
| 13 | Circuit-breaker post-reset failure count `_failures[service] = 0` → None/1 in `is_open` (113) | 2 | `is_open__mutmut_6` | TEST-GAP | After timeout reset, re-failure never exercised: None → TypeError on next `+1`; 1 → circuit re-opens one failure early. |
| 14 | Circuit-breaker freshness operator `datetime.now(UTC) < _open_until` → `<=` (109) | 1 | `is_open__mutmut_3` | TEST-GAP | Exact-deadline boundary untested (classic timestamp `<`/`<=` flip); `reset_timeout=0` tests never freeze the clock at the deadline. |
| 15 | DI lookup key `container.get_async("health_service_registry")` arg → None/"XX…"/UPPER (627) | 3 | `x_get_health_registry__mutmut_4` | TEST-GAP | Test mock returns the registry for ANY key (`AsyncMock` ignores args); never asserts the awaited key. |
| 16 | `get_health_events(limit: int = 50)` default → 51 (593) | 1 | `get_health_events__mutmut_1` | TEST-GAP | Existing test always passes `limit=10` explicitly; default never flows to the monitor. |

**Totals:** TEST-GAP 75, EQUIVALENT 13, LOW-VALUE 0. (Sum: 13+16+7+12+4+4+2+12+3+2+2+4+2+1+3+1 = 88 ✓)

## Drafted kill-tests (6 tests, cover clusters 2–16 gaps for 60 of 75 TEST-GAP survivors)

All go in `backend/tests/unit/services/test_health_service_registry.py`. Add `datetime` to the existing import at line 12: `from datetime import datetime, timedelta`.
`// UNVERIFIED - not yet run red/green` — TDD procedure for each: add test → run against mutant copy (expect FAILED) → run against original (expect PASSED).

### T1 — `test_get_health_registry_uses_exact_registration_key` (kills cluster 15)
Adds to `TestDIContainerIntegration` (after :357). TDD: key arg differs on mutant → `assert_awaited_once_with` fails; passes on original.
```python
    @pytest.mark.asyncio
    async def test_get_health_registry_uses_exact_registration_key(self) -> None:
        """get_health_registry must look up the exact container registration key."""
        mock_registry = MagicMock()

        with patch("backend.core.container.get_container", autospec=True) as mock_get:
            mock_container = MagicMock()
            mock_container.get_async = AsyncMock(return_value=mock_registry)
            mock_get.return_value = mock_container

            result = await get_health_registry()

            assert result is mock_registry
            mock_container.get_async.assert_awaited_once_with("health_service_registry")
```

### T2 — `test_initialization_with_all_services` (kills cluster 12)
Adds to `TestHealthServiceRegistry`. TDD: mutated store lines yield `None` → identity assert fails; passes on original.
```python
    def test_initialization_with_all_services(self) -> None:
        """Constructor must store every one of the ten service dependencies."""
        mocks = {
            name: MagicMock()
            for name in (
                "gpu_monitor",
                "cleanup_service",
                "system_broadcaster",
                "file_watcher",
                "pipeline_manager",
                "batch_aggregator",
                "degradation_manager",
                "service_health_monitor",
                "performance_collector",
                "health_event_emitter",
            )
        }

        registry = HealthServiceRegistry(**mocks)

        assert registry.gpu_monitor is mocks["gpu_monitor"]
        assert registry.cleanup_service is mocks["cleanup_service"]
        assert registry.system_broadcaster is mocks["system_broadcaster"]
        assert registry.file_watcher is mocks["file_watcher"]
        assert registry.pipeline_manager is mocks["pipeline_manager"]
        assert registry.batch_aggregator is mocks["batch_aggregator"]
        assert registry.degradation_manager is mocks["degradation_manager"]
        assert registry.service_health_monitor is mocks["service_health_monitor"]
        assert registry.performance_collector is mocks["performance_collector"]
        assert registry.health_event_emitter is mocks["health_event_emitter"]
```

### T3 — `test_get_worker_statuses_multi_worker_structure` + `test_are_critical_pipeline_workers_healthy_multi_worker_error` (kills clusters 4, 7; also 2 for detection/analysis running messages)
TDD: mutant `get(None/XXworkers/WORKERS)` falls into legacy path → reported stopped instead of running → assert fails; "error"-state mutants flip healthy→False; passes on original.
```python
    def test_get_worker_statuses_multi_worker_structure(self) -> None:
        """NEM-5375: multi-worker {count, workers:[...]} structures must aggregate."""
        mock_pipeline = MagicMock()
        mock_pipeline.get_status.return_value = {
            "workers": {
                "detection": {
                    "count": 2,
                    "workers": [{"state": "stopped"}, {"state": "running"}],
                },
                "analysis": {"count": 1, "workers": [{"state": "error"}]},
            }
        }

        registry = HealthServiceRegistry(pipeline_manager=mock_pipeline)
        statuses = {s.name: s for s in registry.get_worker_statuses()}

        # "running" if ANY worker is operational ("running" or "error")
        assert statuses["detection_worker"].running is True
        assert statuses["detection_worker"].message is None
        assert statuses["analysis_worker"].running is True
        assert statuses["analysis_worker"].message is None

    def test_are_critical_pipeline_workers_healthy_multi_worker_error(self) -> None:
        """NEM-5375: one operational (incl. error) worker keeps health True."""
        mock_pipeline = MagicMock()

        # Multi-worker: detection only "error", analysis legacy "error"
        mock_pipeline.get_status.return_value = {
            "workers": {
                "detection": {
                    "count": 2,
                    "workers": [{"state": "stopped"}, {"state": "error"}],
                },
                "analysis": {"state": "error"},
            }
        }
        registry = HealthServiceRegistry(pipeline_manager=mock_pipeline)
        assert registry.are_critical_pipeline_workers_healthy() is True

        # Both fully stopped -> False (guards the True-default mutants)
        mock_pipeline.get_status.return_value = {
            "workers": {
                "detection": {"count": 1, "workers": [{"state": "stopped"}]},
                "analysis": {"state": "stopped"},
            }
        }
        assert registry.are_critical_pipeline_workers_healthy() is False
```

### T4 — `test_are_critical_pipeline_workers_healthy_missing_sections` (kills clusters 6, 5, and multi-worker keys 40-42 via the running multi-worker case)
TDD: section-default mutants return `None`/`True` where `is False` is required → fail; `{}`-status mutants raise TypeError; passes on original.
```python
    def test_are_critical_pipeline_workers_healthy_missing_sections(self) -> None:
        """A missing detection/analysis section (or missing workers dict) is unhealthy."""
        mock_pipeline = MagicMock()

        # No "workers" key at all
        mock_pipeline.get_status.return_value = {}
        registry = HealthServiceRegistry(pipeline_manager=mock_pipeline)
        assert registry.are_critical_pipeline_workers_healthy() is False

        # Analysis section missing entirely
        mock_pipeline.get_status.return_value = {"workers": {"detection": {"state": "running"}}}
        assert registry.are_critical_pipeline_workers_healthy() is False

        # Detection section missing entirely
        mock_pipeline.get_status.return_value = {"workers": {"analysis": {"state": "running"}}}
        assert registry.are_critical_pipeline_workers_healthy() is False
```

### T5 — `test_get_worker_statuses_flags_and_messages` + `test_get_worker_statuses_missing_state_falls_back_to_stopped` + `test_get_worker_statuses_empty_registry_and_unflagged_services` (kills clusters 2, 3, 8, 9, 10, 11, and gws cluster 5)
TDD: each asserted literal (running flag / message string / list contents) differs on the corresponding mutant set; all pass on original.
```python
    def test_get_worker_statuses_flags_and_messages(self) -> None:
        """Running/not-running flags and per-worker message strings, incl. running analysis."""
        mock_gpu = MagicMock()
        mock_gpu.running = False
        mock_cleanup = MagicMock()
        mock_cleanup.running = True
        mock_pipeline = MagicMock()
        mock_pipeline.get_status.return_value = {
            "workers": {
                "detection": {"state": "running"},
                "analysis": {"state": "running"},
                "timeout": {"state": "running"},
            }
        }

        registry = HealthServiceRegistry(
            gpu_monitor=mock_gpu,
            cleanup_service=mock_cleanup,
            pipeline_manager=mock_pipeline,
        )
        statuses = {s.name: s for s in registry.get_worker_statuses()}

        assert statuses["gpu_monitor"].running is False
        assert statuses["gpu_monitor"].message == "Not running"
        assert statuses["cleanup_service"].running is True
        assert statuses["cleanup_service"].message is None
        assert statuses["detection_worker"].running is True
        assert statuses["detection_worker"].message is None
        assert statuses["analysis_worker"].running is True  # kills "state" key + == "running" flips
        assert statuses["analysis_worker"].message is None
        assert statuses["batch_timeout_worker"].running is True
        assert statuses["batch_timeout_worker"].message is None

    def test_get_worker_statuses_missing_state_falls_back_to_stopped(self) -> None:
        """Worker info dicts without a "state" key report State: stopped."""
        mock_pipeline = MagicMock()
        mock_pipeline.get_status.return_value = {
            "workers": {
                "detection": {"count": 0},
                "analysis": {},
                "timeout": {},
            }
        }

        registry = HealthServiceRegistry(pipeline_manager=mock_pipeline)
        statuses = {s.name: s for s in registry.get_worker_statuses()}

        assert statuses["detection_worker"].running is False
        assert statuses["detection_worker"].message == "State: stopped"
        assert statuses["analysis_worker"].running is False
        assert statuses["analysis_worker"].message == "State: stopped"
        assert statuses["batch_timeout_worker"].running is False
        assert statuses["batch_timeout_worker"].message == "State: stopped"

    def test_get_worker_statuses_empty_registry_and_unflagged_services(self) -> None:
        """Unregistered services emit no status; flag-less services default to not running;
        a manager status without "workers" yields an empty list instead of raising."""
        assert HealthServiceRegistry().get_worker_statuses() == []

        class _NoRunningFlag:
            pass

        registry = HealthServiceRegistry(
            gpu_monitor=_NoRunningFlag(), cleanup_service=_NoRunningFlag()
        )
        statuses = {s.name: s for s in registry.get_worker_statuses()}
        assert statuses["gpu_monitor"].running is False
        assert statuses["gpu_monitor"].message == "Not running"
        assert statuses["cleanup_service"].running is False
        assert statuses["cleanup_service"].message == "Not running"

        mock_pipeline = MagicMock()
        mock_pipeline.get_status.return_value = {}
        assert HealthServiceRegistry(pipeline_manager=mock_pipeline).get_worker_statuses() == []
```

### T6 — circuit breaker deadline boundary + post-reset threshold (kills clusters 14, 13; the reset assert also kills any `<=` variant)
Follows the repo's `patch("<module>.datetime", autospec=True)` idiom (cf. `backend/tests/unit/services/test_cleanup_service.py:330`). TDD: `<`/`<=` differ exactly at the deadline; post-reset counter None raises / 1 re-opens early; passes on original.
```python
    def test_circuit_closed_exactly_at_reset_deadline(self) -> None:
        """At the exact reset deadline the circuit is already closed (strict <)."""
        fixed_now = datetime(2025, 12, 23, 10, 0, 0)
        cb = HealthCircuitBreaker(failure_threshold=2, reset_timeout=timedelta(seconds=30))

        with patch("backend.services.health_service_registry.datetime", autospec=True) as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            cb.record_failure("test_service", "boom")
            cb.record_failure("test_service", "boom")
            assert cb.is_open("test_service") is True  # still within window

            mock_dt.now.return_value = fixed_now + timedelta(seconds=30)
            assert cb.is_open("test_service") is False  # mutant "<=" returns True here

    def test_circuit_requires_full_threshold_after_timeout_reset(self) -> None:
        """After a timeout reset the failure counter restarts from zero."""
        fixed_now = datetime(2025, 12, 23, 10, 0, 0)
        cb = HealthCircuitBreaker(failure_threshold=3, reset_timeout=timedelta(seconds=0))

        with patch("backend.services.health_service_registry.datetime", autospec=True) as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            cb.record_failure("test_service", "boom")
            cb.record_failure("test_service", "boom")
            # 0s reset_timeout: deadline reached, circuit resets on check
            assert cb.is_open("test_service") is False

            # Two more failures must NOT reopen (counter reset to 0; mutants reset to None/1)
            cb.record_failure("test_service", "boom")
            cb.record_failure("test_service", "boom")
            assert cb.is_open("test_service") is False

            # The third one does
            cb.record_failure("test_service", "boom")
            assert cb.is_open("test_service") is True
```

## Residual (not drafted — cheap to add later, same patterns)
- Cluster 1 (13 EQUIVALENT): do not test; recommend mutmut config triage note.
- Cluster 16 (`get_health_events` default limit): one-liner — `registry.get_health_events(); mock_monitor.get_recent_events.assert_called_once_with(limit=50)`.
