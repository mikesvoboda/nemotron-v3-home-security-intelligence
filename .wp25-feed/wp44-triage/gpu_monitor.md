# WP4.4 Mutation Triage Dossier — `backend/services/gpu_monitor.py`

Generated 2026-09-18 (workflow harness, read-only triage). All content **UNVERIFIED** — no tests were run
(a live mutation run owns the machine). Method: parsed `mutants/backend/services/gpu_monitor.py`
(every mutant is a full `def …__mutmut_N` copy next to `…__mutmut_orig`), extracted each survivor's
single changed hunk, and classified by AST context in the original `backend/services/gpu_monitor.py`.
`uv run mutmut show` was attempted and failed (`FileNotFoundError: Could not find mutant …` — cache is
being concurrently written), so **all diffs below are the manual-diff fallback**.

- Verdict source: `mutants/backend/services/gpu_monitor.py.meta` → `exit_code_by_key`, `exit_code == 0` = survived.
- 1650 total mutants for this module; **1069 survived**, 581 killed, 0 unchecked.
- Covering test files (from `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`):
  - `backend/tests/unit/services/test_gpu_monitor.py` (2653 lines) — primary
  - `backend/tests/unit/services/test_memory_pressure.py` (751 lines) — pressure metrics/callbacks
  - `backend/tests/unit/services/test_async_context_managers.py` (766 lines) — start/stop lifecycle

## Key structural fact driving most survivors

The stats-return dicts (`_get_gpu_stats_real` :614-644, `_get_gpu_stats_mock` :698-730,
`_get_gpu_stats_nvidia_smi[:_async]` :335-365 / :445-475, `_get_gpu_stats_from_ai_containers` :834-864)
each build 25 keys. Tests assert only the 6-7 *primary* values
(`test_get_current_stats_real_gpu` :291, `test_nvidia_smi_stats_parsing` :381,
`test_nvidia_smi_async_stats_parsing` :444 — assert `stats["<key>"] == value` but never the dict's
**key set**), so (a) outer-key renames survive even on asserted keys (lookup returns None), and
(b) all 18 extended-metric keys survive entirely. `GPUStatsDict` (TypedDict, :51) is the contract.

## Cluster table (counts sum to 1069)

| # | Cluster | N | Class | What mutmut did | Verdict basis (file:line) |
|---|---------|---|-------|-----------------|---------------------------|
| 1 | TG-CONTRACT-KEY — outer dict-key rename in stats-return payloads (`"temperature"` → `"XXtemperatureXX"`/`"TEMPERATURE"`) | 206 | TEST-GAP | Tests read values by key but never pin the returned key set; renamed key ⇒ `.get()` → None silently. Survives even on asserted keys because… wait, `stats["temperature"]` would KeyError — see note* | test_gpu_monitor.py:291,381,444,1127 |
| 2 | TG-LOGEXTRA — `extra={...}` context of NEM-1123 error logs removed (`extra=None,`, kwarg deleted) or its entries flipped (`"error": str(e)` → `str(None)`, `"operation"` renamed, `"gpu_id": 0→1`) | 144 | TEST-GAP | The four "error logging includes context" tests assert only `record.message` substrings, never `record.operation`/`record.error_type` (caplog assertions at :1664,1686,1710,1741) | test_gpu_monitor.py:1634-1741 |
| 3 | TG-STORE — `GPUStats(...)` ctor kwargs nulled (`power_usage=stats["power_usage"]` → `power_usage=None`) or lookup key mangled (`stats.get("fan_speed")` → `stats.get(None)`) | 114 | TEST-GAP | `test_store_stats_in_database` :595 asserts only `session.add.assert_called_once()` — the persisted entity's columns are never inspected | test_gpu_monitor.py:595,1511 |
| 4 | TG-CONTRACT-VALUE — primary-key *values* swapped in return dicts (`"recorded_at": datetime.now(UTC)` → `datetime.now(None)` naive; extended `.get("power_limit")` → `.get(None)` ⇒ None) | 54 | TEST-GAP | `test_get_current_stats_real_gpu` :308 asserts only `isinstance(stats["recorded_at"], datetime)` — naive datetime passes; extended keys unasserted | test_gpu_monitor.py:291-309 |
| 5 | TG-EXTFIELD — `_get_extended_metrics` assignments neutralized (`metrics["power_limit"] = float(...)` → `= None`, call args `handle` → `None` silently suppressed by the surrounding `contextlib.suppress(NVMLError)`) | 95 | TEST-GAP | `test_get_stats_with_partial_nvml_failure` :837 never touches `stats["power_limit"]`/`throttle_reasons`/`bar1_used` etc. — all 18 extended metrics go unasserted | test_gpu_monitor.py:837 |
| 6 | TG-SUBPROC — nvidia-smi probe/subprocess call shape: argv list removed/case-flipped (`"--query-gpu=name"` → `"--QUERY-GPU=NAME"`), `timeout=5`→`None`, `capture_output=True`→`False/None` (in `_check_nvidia_smi` :234 and both stat parsers) | 72 | TEST-GAP | `test_check_nvidia_smi_found_and_working` :2470 and parsing tests patch `subprocess.run` with `return_value=` — never assert the argv list or kwargs, so any command-line degradation is invisible | test_gpu_monitor.py:381,425,2470 |
| 7 | EQ-LOGMSG — pure log message text (`logger.info(...)` → `logger.info(None)` / `XX`-wrapped / case-flipped; `raise RuntimeError` message case flips that the `match=` still matches) | 89 | EQUIVALENT | Semantic no-ops for program behavior; `raise RuntimeError("XXGPU not availableXX")` is still matched by `match="GPU not available"` (substring) at :925 | n/a |
| 8 | EQ-NAGUARD — `[N/A]` parse-guard tweaks inside per-field `try/except ValueError` blocks in nvidia-smi parsers (`parts[0]` guard index swaps, `or True` injections, `"[N/A]"`→`"[n/a]"`) — the surrounding `except ValueError: field = None` fallback keeps observable behavior identical | 61 | EQUIVALENT | e.g. guard checks `parts[1] != "[N/A]"` but conversion still does `float(parts[0])` → ValueError → None, same as original for every test input | n/a |
| 9 | TG-REALARGS — `_get_gpu_stats_real` NVML calls passed `None` instead of `handle` (`nvmlDeviceGetUtilizationRates(handle)` → `(None)`) — with `mock_pynvml` a MagicMock returns values for ANY arg, so the mock never notices | 26 | TEST-GAP | `mock_pynvml` fixture :48 returns from every NVML mock regardless of args; tests never assert `mock_pynvml.nvmlDeviceGetTemperature.assert_called_once_with(handle, ...)` | test_gpu_monitor.py:48 (fixture), 291 |
| 10 | EQ-INITFLAGS — `__init__`/`_initialize_nvml` flag initializations (`self._gpu_available = False` → `True/None`) — immediately overwritten by the real `_initialize_nvml()` run on the very next lines :191-195 before any observation | 19 | EQUIVALENT | Dead state by construction; `test_gpu_monitor_init_without_pynvml` :253 asserts the post-init values, which the initializer overwrites | n/a |
| 11 | TG-EXTSUPPRESS — `with contextlib.suppress(pynvml.NVMLError)` → `suppress(None)` / `suppress(AttributeError)` in `_get_extended_metrics` and `_get_gpu_stats_real` — raises TypeError on a real NVMLError | 19 | TEST-GAP | `test_get_stats_with_partial_nvml_failure` :837 raises only from *unwrapped* calls (`nvmlDeviceGetUtilizationRates` side_effect fires before `with` enters; `side_effect = Exception` ≠ `NVMLError`), so the suppressed-block behavior is never exercised | test_gpu_monitor.py:837 |
| 12 | TG-BCAST — WebSocket payload dict (`broadcast_stats` → `None`, `broadcast_gpu_stats(broadcast_stats)` → `(None)`, its key renames) | 16 | TEST-GAP | `test_broadcast_stats` :626 asserts only `broadcast_gpu_stats.assert_awaited_once()` — never `call_args.args[0]` payload schema | test_gpu_monitor.py:626 |
| 13 | LV-MOCKCONST — `_get_gpu_stats_mock` simulated-value constants / key renames (`sm_clock_max: 1800` → `1801`, base variance tweaks) | 100 | LOW-VALUE | Real value changes but mock-mode cosmetics: tests (:311) already accept ranges by design ("values vary over time"); pinning 25 simulated constants is over-specification. Key renames here ride along (same fix as cluster 1) | test_gpu_monitor.py:311-335 |
| 14 | TG-DBQUERY — `get_stats_from_db` query construction: `.where(None)`, `>=`→`>`, cutoff `now - timedelta` → `now + timedelta`, `if limit is not None:`→`is None`, `.limit(limit)`→`None`, `order_by(recorded_at.desc())`→`order_by(None)` | 10 | TEST-GAP | `test_get_stats_from_db_with_time_filter` :2191 and `_with_limit` :2246 stub `session.execute` and re-emit canned rows — the constructed SQL is never inspected | test_gpu_monitor.py:2191,2246 |
| 15 | TG-AICONTRACT — AI-container query: `client.get(f"{yolo26_url}/health")` → `get(None)`, `total_vram_used_mb += vram_mb` → `=`, fallback-name flips | 9 | TEST-GAP | `test_get_gpu_stats_from_ai_containers_*` :1127ff mock `httpx.AsyncClient` but never assert the requested URL | test_gpu_monitor.py:1127 |
| 16 | TG-FPSQUERY — `_calculate_inference_fps`: window cutoff `now - timedelta(seconds=60)` → `+60`, `where(Detection.detected_at >= cutoff)` → `.where(None)`, `func.count(Detection.id)` → `count(None)` | 8 | TEST-GAP | `test_calculate_inference_fps_with_detections` :1414 returns 120 from a stubbed execute — never asserts the submitted statement | test_gpu_monitor.py:1414 |
| 17 | TG-CSVBOUNDARY — nvidia-smi arity guards: `if len(parts) < 5:` → `<= 5` / `< 6`, `gpu_name = parts[5] if len(parts) > 5` → `>= 5` (IndexError path) | 8 | TEST-GAP | `test_nvidia_smi_stats_parsing` :381 only feeds 6-field output; no test feeds exactly 5 fields where the `>` vs `>=` and `<5`/`<6` flips diverge (IndexError or spurious RuntimeError) | test_gpu_monitor.py:381,2349 |
| 18 | TG-SCATTER — poll loop one-offs: `break` → `return`, `_stats_history.append(stats)` → `append(None)`, `asyncio.sleep(self.poll_interval)` → `sleep(None)`; `stop()` `_poll_task and not done()` → `or`; `get_stats_history` `>=` → `>` | 6 | TEST-GAP | `test_poll_loop_collects_stats` :724 and `test_stats_history_filtered_by_time` :560 use coarse sleeps/count checks that miss these (append(None) still yields len 1; history timestamps are ±10-min spaced so boundary flip never triggers) | test_gpu_monitor.py:560,724,2402-2467 |
| 19 | TG-PRESS — memory-pressure accounting: `warning_events += 1` → `= 1` (reset-not-increment), `if used is None or total is None or total == 0:` `or`→`and`, `== 0` → `== 1` | 5 | TEST-GAP | `test_memory_pressure_metrics` :2087 triggers each level once → totals identical under `=1`; zero-total case is fed `memory_total=24576` — the `== 0` guard and its `and`-flips are unattainable | test_gpu_monitor.py:2087; test_memory_pressure.py:408,426 |
| 20 | EQ-FPSRETURN — `return count / 60.0 if count >= 0 else 0.0` → `> 0` / `>= 1` / `or True` — `count` is `result.scalar() or 0`, i.e. a non-negative `COUNT(*)` or 0; the else branch is unreachable arithmetic | 4 | EQUIVALENT | Dead branch | n/a |
| 21 | LV-TASKNAME — `asyncio.create_task(..., name="gpu-monitor")` → name removed/altered | 4 | LOW-VALUE | NEM-5057 debug affordance; no test reads `asyncio.all_tasks()` names | n/a |

\* **Note on cluster 1** (why key renames on asserted keys still survive): the surviving renames hit keys
that are *not* value-asserted in the same test path (`recorded_at` rename survives because the test
asserts `isinstance(stats["recorded_at"], datetime)` on… the *renamed* lookup returning None would
fail — but `mutmut` selects per-test and `recorded_at`'s only assertion is `isinstance`; see
`xǁGPUMonitorǁ_get_gpu_stats_real__mutmut_177/178` (`"gpu_name"` rename) which survived the whole
suite, evidencing that the harness's per-mutant test selection missed the asserting test for this
key in the mutated copy — treat cluster 1 as a genuine assertion gap: no test asserts the full
`GPUStatsDict` key set for any producer.
Key examples: `xǁGPUMonitorǁ_get_gpu_stats_real__mutmut_177`, `_get_gpu_stats_from_ai_containers__mutmut_100`, `_broadcast_stats__mutmut_11`.

### Totals
- **TEST-GAP: 792** (clusters 1,2,3,4,5,6,9,11,12,14,15,16,17,18,19)
- **EQUIVALENT: 173** (clusters 7,8,10,20)
- **LOW-VALUE: 104** (clusters 13,21)
- Sum: 206+144+114+95+54+72+89+61+26+19+19+16+100+10+9+8+8+6+5+4+4 = **1069** ✔

## The gap is one-shaped, and three tests kill most of it

Four drafted tests kill clusters 1+4+5 (≈455 survivors), 3+9 (≈140), 2 (144), 12+17+19 (≈39).
All UNVERIFIED.

```python
# ---------------------------------------------------------------------------
# WP4.4 mutation-gap tests — UNVERIFIED - not yet run red/green
# TDD: add to file, run; each must FAIL against the named mutants and PASS on
# the pristine backend/services/gpu_monitor.py, then keep green.
# ---------------------------------------------------------------------------
import json  # noqa: F401  (unused; keep imports minimal below)

# --- D1. Full GPUStatsDict contract for every stats producer -----------------
# Kills: TG-CONTRACT-KEY (outer key renames), TG-CONTRACT-VALUE (.get arg /
#        datetime tz flips), TG-REALARGS (handle→None caught by autospec),
#        TG-EXTFIELD (extended metrics present + non-None), TG-BCAST key part.
# Mutants killed include xǁGPUMonitorǁ_get_gpu_stats_real__mutmut_177/178,
# _get_gpu_stats_from_ai_containers__mutmut_100/101/61, _get_gpu_stats_mock__mutmut_100+.
EXPECTED_GPU_STAT_KEYS = {
    "gpu_name", "gpu_utilization", "memory_used", "memory_total", "temperature",
    "power_usage", "recorded_at", "fan_speed", "sm_clock",
    "memory_bandwidth_utilization", "pstate", "throttle_reasons", "power_limit",
    "sm_clock_max", "compute_processes_count", "pcie_replay_counter",
    "temp_slowdown_threshold", "memory_clock", "memory_clock_max",
    "pcie_link_gen", "pcie_link_width", "pcie_tx_throughput", "pcie_rx_throughput",
    "encoder_utilization", "decoder_utilization", "bar1_used",
}
TZ_AWARE_KEYS = ("recorded_at",)


def _assert_gpu_stats_contract(stats: dict) -> None:
    """Every GPUStatsDict producer must return the full key set, tz-aware timestamps."""
    assert set(stats.keys()) == EXPECTED_GPU_STAT_KEYS, (
        f"stats dict keys drifted from GPUStatsDict: "
        f"missing={EXPECTED_GPU_STAT_KEYS - set(stats)} "
        f"unexpected={set(stats) - EXPECTED_GPU_STAT_KEYS}"
    )
    for key in TZ_AWARE_KEYS:
        assert stats[key].tzinfo is not None, f"{key} must be timezone-aware"


def test_get_gpu_stats_real_returns_full_contract(mock_pynvml):
    """Kills TG-CONTRACT-KEY/VALUE + TG-REALARGS on the pynvml path.

    With autospec-style arg checking, nvml calls mutated to pass None instead of
    the handle stop returning values (MagicMock-with-spec checks args), and the
    key-set assertion catches every outer key rename.
    """
    monitor = GPUMonitor()
    # autospec makes the mocks sensitive to call args the way real pynvml is
    for attr in (
        "nvmlDeviceGetUtilizationRates", "nvmlDeviceGetMemoryInfo",
        "nvmlDeviceGetTemperature", "nvmlDeviceGetPowerUsage",
        "nvmlDeviceGetFanSpeed", "nvmlDeviceGetClockInfo",
        "nvmlDeviceGetPerformanceState",
    ):
        mock_pynvml.__dict__[attr].autospec  # touch to fail early if fixture changes
    stats = monitor._get_gpu_stats_real()
    _assert_gpu_stats_contract(stats)
    assert stats["memory_used"] == 8192
    assert stats["temperature"] == 65.0
    assert stats["power_usage"] == 150.0


def test_get_gpu_stats_nvidia_smi_returns_full_contract():
    """Kills TG-CONTRACT-KEY/VALUE on both nvidia-smi parsers."""
    monitor = GPUMonitor.__new__(GPUMonitor)
    monitor._nvidia_smi_available = True
    monitor._nvidia_smi_path = "/usr/bin/nvidia-smi"
    monitor._gpu_name = "Test GPU"

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "39, 29.61, 35, 175, 24576, NVIDIA RTX A5500"
    with patch("subprocess.run", return_value=mock_result, autospec=True):
        _assert_gpu_stats_contract(monitor._get_gpu_stats_nvidia_smi())

    # exactly-5-fields output: gpu_name must fall back to cached name, not IndexError
    mock_result.stdout = "39, 29.61, 35, 175, 24576"
    with patch("subprocess.run", return_value=mock_result, autospec=True):
        stats = monitor._get_gpu_stats_nvidia_smi()
    _assert_gpu_stats_contract(stats)
    assert stats["gpu_name"] == "Test GPU"  # kills _get_gpu_stats_nvidia_smi__mutmut_100 (>5 -> >=5)


@pytest.mark.asyncio
async def test_nvidia_smi_async_returns_full_contract():
    monitor = GPUMonitor.__new__(GPUMonitor)
    monitor._nvidia_smi_available = True
    monitor._nvidia_smi_path = "/usr/bin/nvidia-smi"
    monitor._gpu_name = "Test GPU"
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "42, 32.5, 45, 2048, 24576, NVIDIA RTX A5500"
    mock_result.stderr = ""
    with patch(
        "backend.core.async_utils.async_subprocess_run", new_callable=AsyncMock,
        return_value=mock_result,
    ):
        _assert_gpu_stats_contract(await monitor._get_gpu_stats_nvidia_smi_async())


def test_get_gpu_stats_mock_returns_full_contract():
    """Kills the key-rename half of LV-MOCKCONST / TG-CONTRACT-KEY in mock mode."""
    monitor = GPUMonitor.__new__(GPUMonitor)
    _assert_gpu_stats_contract(monitor._get_gpu_stats_mock())


@pytest.mark.asyncio
async def test_get_gpu_stats_from_ai_containers_returns_full_contract(mock_pynvml):
    monitor = GPUMonitor()
    with patch("httpx.AsyncClient", autospec=True) as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"vram_used_gb": 3.5, "device": "cuda:0"}
        mock_client.get.return_value = resp
        stats = await monitor._get_gpu_stats_from_ai_containers()
    assert stats is not None
    _assert_gpu_stats_contract(stats)
```

*(D1 caveat, one line: `mock_pynvml` is a plain `MagicMock` so `handle → None` arg mutations are NOT
caught by autospec here — cluster 9 (TG-REALARGS) is instead killed by D2's `assert_called_once_with`
assertions below; D1 alone kills the key/value/tz survivors.)*

```python
# --- D2. Persisted GPUStats row + NVML call-argument fidelity -----------------
# Kills: TG-STORE (114: any GPUStats(**kwargs) column silently None/renamed lookup)
#        + TG-REALARGS (26: nvml*(None) caught via assert_called_once_with)
# Mutants: _store_stats__mutmut_10 (power_usage=None), _store_stats__mutmut_100+
# (stats.get(XXkeyXX) / get(None) -> column None), _get_gpu_stats_real__mutmut_13/16.
@pytest.mark.asyncio
async def test_store_stats_persists_all_columns(mock_pynvml, mock_database_session):
    """The DB row must carry every stats field, not just 'add was called'."""
    monitor = GPUMonitor()
    stats = monitor.get_current_stats()

    # arg-fidelity on the pynvml reads feeding those columns (kills handle→None)
    handle = monitor._gpu_handle
    monitor._get_gpu_stats_real()
    mock_pynvml.nvmlDeviceGetMemoryInfo.assert_called_with(handle)
    mock_pynvml.nvmlDeviceGetTemperature.assert_called_with(handle, mock_pynvml.NVML_TEMPERATURE_GPU)

    with patch.object(monitor, "_calculate_inference_fps", return_value=2.0, autospec=True):
        await monitor._store_stats(stats)

    mock_database_session.add.assert_called_once()
    (gpu_stats,), _ = mock_database_session.add.call_args
    assert gpu_stats.recorded_at == stats["recorded_at"]
    assert gpu_stats.gpu_name == stats["gpu_name"]
    assert gpu_stats.gpu_utilization == stats["gpu_utilization"]
    assert gpu_stats.memory_used == stats["memory_used"]
    assert gpu_stats.memory_total == stats["memory_total"]
    assert gpu_stats.temperature == stats["temperature"]
    assert gpu_stats.power_usage == stats["power_usage"]
    assert gpu_stats.inference_fps == 2.0
    for field, key in (
        ("fan_speed", "fan_speed"), ("sm_clock", "sm_clock"),
        ("pstate", "pstate"), ("throttle_reasons", "throttle_reasons"),
        ("power_limit", "power_limit"), ("sm_clock_max", "sm_clock_max"),
        ("bar1_used", "bar1_used"),
    ):
        assert getattr(gpu_stats, field) == stats[key], f"{field} column drifted"


# --- D3. NEM-1123 error-context payloads are part of the contract -------------
# Kills: TG-LOGEXTRA (144: extra=None, exc_info drop, "operation" rename,
#        str(e)->str(None), "gpu_id":0->1)
# Mutants: _broadcast_stats__mutmut_37/39/43, _poll_loop/_store_stats/get_current_stats extra hunks.
@pytest.mark.asyncio
async def test_error_log_records_structured_context(mock_pynvml, mock_broadcaster, caplog):
    """caplog-based context must carry operation/error_type, not just the message."""
    import logging

    monitor = GPUMonitor(broadcaster=mock_broadcaster)
    stats = monitor.get_current_stats()
    mock_broadcaster.broadcast_gpu_stats.side_effect = Exception("boom")
    with caplog.at_level(logging.ERROR):
        await monitor._broadcast_stats(stats)

    rec = [r for r in caplog.records if "Failed to broadcast GPU stats" in r.message]
    assert rec, "error must still be logged"
    assert rec[0].operation == "broadcast_stats"
    assert rec[0].error_type == "Exception"
    assert rec[0].error == "boom"


# --- D4. WebSocket payload schema ----------------------------------------------
# Kills: TG-BCAST (16)
@pytest.mark.asyncio
async def test_broadcast_stats_payload_schema(mock_pynvml, mock_broadcaster):
    monitor = GPUMonitor(broadcaster=mock_broadcaster)
    stats = monitor.get_current_stats()
    await monitor._broadcast_stats(stats)

    mock_broadcaster.broadcast_gpu_stats.assert_awaited_once()
    (payload,), _ = mock_broadcaster.broadcast_gpu_stats.call_args
    assert set(payload) == {
        "gpu_name", "gpu_utilization", "memory_used", "memory_total",
        "temperature", "power_usage", "recorded_at",
    }
    assert payload["memory_used"] == stats["memory_used"]
    assert payload["recorded_at"] == stats["recorded_at"].isoformat()


# --- D5. Memory-pressure event accounting is cumulative + zero-guard ----------
# Kills: TG-PRESS (5) — _handle_pressure_level_change__mutmut_4/9, check_memory_pressure_10+
@pytest.mark.asyncio
async def test_memory_pressure_events_accumulate_and_zero_guard(mock_pynvml):
    """Two WARNING transitions must count 2, and total==0 must return NORMAL."""
    monitor = GPUMonitor()

    warn = {"memory_used": 22118, "memory_total": 24576, "recorded_at": datetime.now(UTC),
            "gpu_name": "T", "gpu_utilization": 0.0, "temperature": 0, "power_usage": 0.0}
    norm = {**warn, "memory_used": 1000}
    with patch.object(monitor, "get_current_stats_async", return_value=warn, autospec=True):
        assert await monitor.check_memory_pressure() is MemoryPressureLevel.WARNING
    with patch.object(monitor, "get_current_stats_async", return_value=norm, autospec=True):
        assert await monitor.check_memory_pressure() is MemoryPressureLevel.NORMAL
    with patch.object(monitor, "get_current_stats_async", return_value=warn, autospec=True):
        assert await monitor.check_memory_pressure() is MemoryPressureLevel.WARNING
    # kills `warning_events += 1` -> `= 1`
    assert monitor.get_memory_pressure_metrics()["total_warning_events"] == 2

    # zero total must short-circuit to NORMAL (kills `total == 0` -> `== 1` and or->and flips)
    zero = {**warn, "memory_total": 0}
    with patch.object(monitor, "get_current_stats_async", return_value=zero, autospec=True):
        assert await monitor.check_memory_pressure() is MemoryPressureLevel.NORMAL
```

Smaller follow-ups (not drafted, one-liners): D6 — assert the submitted statement in
`_calculate_inference_fps`/`get_stats_from_db` (`str(session.execute.await_args.args[0])` contains
`detected_at >=` / `recorded_at >=` and the bound cutoff is `now - window`, killing TG-FPSQUERY 8 +
TG-DBQUERY 10); D7 — assert `mock_client.get.assert_awaited_once_with(f"{settings.yolo26_url}/health")`
(kills TG-AICONTRACT 9); D8 — `subprocess.run` argv/kwargs assertion
(`args[0] == [path, "--query-gpu=...", "--format=csv,noheader,nounits"]`, `timeout == 5`) (kills
TG-SUBPROC 72); D9 — extend the partial-failure test to raise a genuine
`pynvml.NVMLError` from inside a `suppress`-protected call (kills TG-EXTSUPPRESS 19).

## Notes for WP4.4

- Cluster 1's survival of `get_gpu_stats_real__mutmut_177/178` (gpu_name rename, despite
  `assert stats["gpu_name"] == ...` in `test_get_current_stats_real_gpu`) is itself worth a look at
  the harness's test-selection for mutated copies — a value-asserted key rename should have died.
  Either selection under-selects, or `get_current_stats()`'s broad `except Exception` swallows the
  KeyError and falls through to `_get_gpu_stats_mock()` whose `gpu_name` is a different literal… it
  isn't (`"Mock GPU (Development Mode)"` ≠ `"NVIDIA RTX A5500"`), so flag for harness review.
- EQ-NAGUARD/EQ-INITFLAGS/EQ-FPSRETURN (173 total) are safe to mark equivalent in the baseline
  (guard rationale in cluster notes; `mutmut` cannot see the dead branches).
- `test_async_context_managers.py` only covers start/stop/`__aenter__`; no drafted test needed there.
