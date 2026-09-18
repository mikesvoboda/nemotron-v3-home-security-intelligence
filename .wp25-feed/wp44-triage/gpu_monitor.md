# WP4.4 Triage Dossier — backend/services/gpu_monitor.py

**Generated:** 2026-09-17 (WP4.3 feed → WP4.4). **UNVERIFIED — no tests were run (live mutation run owns the machine).**

- Surviving mutants: **194** (of 1650 keys with verdicts; `mutants/backend/services/gpu_monitor.py.meta`, exit_code == 0)
- Every survivor is in one of two near-identical twins:
  - `GPUMonitor._get_gpu_stats_nvidia_smi` (sync; source lines 266–369; key prefix `backend.services.gpu_monitor.xǁGPUMonitorǁ_get_gpu_stats_nvidia_smi__mutmut_N`, abbreviated **SMI#N**)
  - `GPUMonitor._get_gpu_stats_nvidia_smi_async` (async twin; source lines 372–479; `..._nvidia_smi_async__mutmut_N`, abbreviated **ASYNC#N**)
- Diff extraction method: per-mutant variant bodies from `mutants/backend/services/gpu_monitor.py.spans` (line ranges) compared against `__mutmut_orig` body in the mutants copy; no test execution.

## Covering tests (from mutants/mutmut-stats.json → tests_by_mangled_function_name)

All in **`backend/tests/unit/services/test_gpu_monitor.py`**:

| Test | Line | Exercises |
|---|---|---|
| `test_nvidia_smi_stats_parsing` | 381 | happy-path parse of `"39, 29.61, 35, 175, 24576, NVIDIA RTX A5500"` (all 6 fields valid) |
| `test_nvidia_smi_handles_na_values` | 404 | `"​[N/A], [N/A], 35, 175, 24576, GPU"` (leading N/As only) |
| `test_nvidia_smi_timeout_handling` | 425 | TimeoutExpired side-effect |
| `test_nvidia_smi_async_stats_parsing` | 444 | async happy path |
| `test_nvidia_smi_async_handles_errors` | 473 | returncode 1, matches prefix only |
| `test_nvidia_smi_not_available_raises_error` | 2293 | guard with available=False **and** path=None |
| `test_nvidia_smi_async_not_available_raises_error` | 2309 | same, async |
| `test_nvidia_smi_subprocess_error` | 2324 | returncode 1, matches prefix only |
| `test_nvidia_smi_unexpected_output_format` | 2349 / async 2373 | only 2 fields |
| `test_nvidia_smi_async_timeout` | 2402 | async timeout |
| `test_nvidia_smi_generic_exception` | 2427 / async 2447 | generic exception wrap |
| `test_nvidia_smi_parsing_all_na_values` | 2493 / async 2521 | all fields `[N/A]` + name |

Key blind spots shared by all these tests: they mock `subprocess.run` / `async_subprocess_run` and **never inspect the call arguments**; they always feed a **fully-valid 6-field line** (or all-`[N/A]`); they **never assert the stats dict's key set**; they never assert `recorded_at`; and every error assertion is a regex-prefix `match=` that still matches XX-clobbered messages.

## Cluster table (counts sum = 194)

| # | Pattern | n | Class | Example keys |
|---|---|---|---|---|
| K1 | Return-dict key renamed (typed contract keys `recorded_at` + 38 constant-`None` keys → `"XXkeyXX"`/`"KEY"`) | 80 | TEST-GAP | SMI#117, SMI#114, ASYNC#121 |
| K2 | `"recorded_at": datetime.now(UTC)` → `datetime.now(None)` (naive timestamp) | 2 | TEST-GAP | SMI#116, ASYNC#120 |
| K3 | nvidia-smi argv mutated (query/format strings XX-clobbered or UPPERCASED; whole argv list → `None`/removed) | 11 | TEST-GAP | SMI#18, SMI#19, SMI#8 |
| K4 | `subprocess.run` kwargs mutated (`capture_output`/`text`/`timeout`/`check` → None/removed/False/6) | 21 | TEST-GAP | SMI#10, SMI#25, ASYNC#22 |
| K5 | Field-parse condition **index shift** (truthiness or `!= "[N/A]"` guard reads the *sibling* field) | 20 | TEST-GAP | SMI#45, SMI#46, ASYNC#49 |
| K6 | `len(parts)` boundary mutated (`< 5`→`<= 5`/`< 6`; `gpu_name = parts[5] if len > 5` → `or True`/`>=`) | 8 | TEST-GAP | SMI#36, SMI#98, SMI#100 |
| K7 | Async `stderr_str` conversion mutated (`and False`, `or True`, `str(None)`, `else "XXXX"`) | 4 | TEST-GAP | ASYNC#26, ASYNC#28, ASYNC#29 |
| K8 | `split("\n")` → `split("XX\nXX")` (multi-GPU first-line selection broken) | 2 | TEST-GAP | SMI#31, ASYNC#35 |
| K9 | Availability guard `or` → `and` (mismatched available/path state no longer rejected) | 2 | TEST-GAP | SMI#1, ASYNC#1 |
| K10 | Field-parse condition rewrites **absorbed by `except ValueError`** (`... or True`, `and`→`or`, sentinel `"XX[N/A]XX"`, `"[n/a]"`) — output identical for every input | 40 | EQUIVALENT | SMI#41, SMI#44, SMI#48 |
| K11 | Exception **message text** only (`"nvidia-smi not available"`, `"nvidia-smi timed out"` → `"XX...XX"`) — existing `pytest.raises(match=)` still matches (re.search finds the substring) | 4 | EQUIVALENT | SMI#5, SMI#156, ASYNC#160 |

**TEST-GAP total 150, EQUIVALENT 44, LOW-VALUE 0.**

### Per-cluster reasoning

- **K1 (80)** — the returned dict is the `GPUStatsDict` TypedDict contract (gpu_monitor.py:51–84); renaming any of its keys drops a declared key and adds a bogus one. Tests read 6 fields by name on happy path, so renames of the 38 always-`None` extended keys and of `recorded_at` are invisible. Downstream code (`_store_stats`, `get_stats_history` at gpu_monitor.py:973, WebSocket broadcast) consumes the dict by key — a missing `recorded_at` would raise there, so this is a real contract break nobody asserts. Killable by one shape+tz test per function.
- **K2 (2)** — `now(None)` yields a naive datetime; `get_stats_history`'s `stats["recorded_at"] >= cutoff_time` (aware) would raise `TypeError`. No nvidia-smi test asserts `recorded_at` at all.
- **K3 (11)** — argv is only observable through the mocked call; a real nvidia-smi would fail or return garbage on a clobbered/UPPERCASED `--query-gpu=`/`--format=`. Tests patch `subprocess.run` with `return_value=mock_result` and never touch `call_args` (confirmed: only the httpx timeout test at test file line 1591 uses `call_args` anywhere).
- **K4 (21)** — same mechanism; `check=False→True`, `text=True→False`, `timeout=5→6`, kwarg removals all change real-subprocess semantics (unexpected CalledProcessError, bytes not str, unbounded/longer wait). Members: SMI#9–12,14–17 (incl. removals), ASYNC#9,10,11,13–15, SMI#22–25, ASYNC#20–22. `timeout 5→6` is the weakest member (arguably LOW-VALUE) but the same `call_args` assertion that kills the rest kills it for free.
- **K5 (20)** — real misparse: e.g. SMI#46 `float(parts[0]) if parts[0] and parts[1] != "[N/A]"` returns `temperature=None` whenever the *power* field is `[N/A]` (orig: `39.0`); SMI#45 gates temperature on the *power* field's emptiness. Every existing input feeds either all-valid or all-`[N/A]` fields, where sibling==self behavior. Killed by a malformed-layout parametrization (draft below).
- **K6 (8)** — for a **5-field** line (no trailing name — legitimate nvidia-smi output shape), orig parses and falls back to `self._gpu_name`; mutants raise `RuntimeError` (`<6`/`<=5` guard, or `parts[5]` `IndexError` under `or True`/`>=`). The unexpected-format test uses 2 fields, which all variants treat identically.
- **K7 (4)** — async `stderr_str: str = str(result.stderr) if result.stderr else ""` (gpu_monitor.py:405): ASYNC#26/#28 drop the driver error text from the raised message, #29 injects `"XXXX"`, #27 stringifies `None`→`"None"`. `test_nvidia_smi_async_handles_errors` (line 473) only matches the `"nvidia-smi returned error"` prefix — loss of the diagnostic is unasserted. (27/29 are message-content-only; 26/28 lose real stderr data.)
- **K8 (2)** — `split("XX\nXX")` returns the whole stdout as one "line" → the comma-split then bleeds the *second* GPU's line into `gpu_name` (`"GPU0\n44"`) and later fields. All tests feed single-line stdout.
- **K9 (2)** — `if not available or not path: raise` → `and`: with `available=True, path=None` the orig raises `"nvidia-smi not available"`; the mutant proceeds and `subprocess.run([None, ...])` becomes the generic wrapped `"Failed to get GPU stats via nvidia-smi: ..."`. Existing test sets *both* to falsey, which both variants reject.
- **K10 (40) EQUIVALENT** — verified semantically for all four rewrite families: any path where the mutated condition now attempts `float(...)` on `""`/`"[N/A]"`/`"[n/a]"` raises `ValueError`, is caught by the inner `except ValueError`, and yields `None` — identical to the orig short-circuit; valid numbers parse identically either way. Purely defensive-condition mutants; mark as equivalent-noise in WP4.4.
- **K11 (4) EQUIVALENT** — message text only; `pytest.raises(match=...)` uses `re.search`, so `"XXnvidia-smi timed outXX"` still matches. No consumer parses these strings.

## Drafted tests (kill 148 of 150 TEST-GAP survivors)

All "// UNVERIFIED - not yet run red/green". Style copies the file's existing idiom (`GPUMonitor.__new__`, `MagicMock` result, `patch("subprocess.run", ..., autospec=True)`, `@pytest.mark.asyncio` + `AsyncMock` on `backend.core.async_utils.async_subprocess_run`). Add `GPUStatsDict` to the existing import line `from backend.services.gpu_monitor import GPUMonitor`.

**TDD procedure (same for all):** apply the cluster's mutant to `backend/services/gpu_monitor.py`, run the new test — it must FAIL (red); revert the mutant, run again — it must PASS (green). Then re-run the module's test file to confirm no collateral breaks.

### T1 — stats-dict contract: key set + tz-aware `recorded_at` → kills K1 (80) + K2 (2)

```python
def test_nvidia_smi_stats_dict_contract():
    """Stats dict must expose the full GPUStatsDict key set with tz-aware timestamp.

    Given: nvidia-smi returns a valid metrics line
    When: _get_gpu_stats_nvidia_smi() is called
    Then: Returned dict matches the GPUStatsDict contract exactly and
          recorded_at is timezone-aware (history filtering relies on that)
    """
    monitor = GPUMonitor.__new__(GPUMonitor)
    monitor._nvidia_smi_available = True
    monitor._nvidia_smi_path = "/usr/bin/nvidia-smi"
    monitor._gpu_name = "Test GPU"

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "39, 29.61, 35, 175, 24576, NVIDIA RTX A5500"

    with patch("subprocess.run", return_value=mock_result, autospec=True):
        stats = monitor._get_gpu_stats_nvidia_smi()

    assert set(stats.keys()) == set(GPUStatsDict.__annotations__.keys())
    assert stats["recorded_at"].tzinfo is UTC
    # Extended metrics are declared but unavailable via the basic query
    assert stats["fan_speed"] is None
    assert stats["pcie_link_gen"] is None


@pytest.mark.asyncio
async def test_nvidia_smi_async_stats_dict_contract():
    """Async stats dict must satisfy the same GPUStatsDict contract."""
    monitor = GPUMonitor.__new__(GPUMonitor)
    monitor._nvidia_smi_available = True
    monitor._nvidia_smi_path = "/usr/bin/nvidia-smi"
    monitor._gpu_name = "Test GPU"

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "42, 32.5, 45, 2048, 24576, NVIDIA RTX A5500"
    mock_result.stderr = ""

    with patch(
        "backend.core.async_utils.async_subprocess_run",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        stats = await monitor._get_gpu_stats_nvidia_smi_async()

    assert set(stats.keys()) == set(GPUStatsDict.__annotations__.keys())
    assert stats["recorded_at"].tzinfo is UTC
    assert stats["fan_speed"] is None
```

// UNVERIFIED - not yet run red/green. On any K1 key rename the key-set assert fails (and `KeyError` on `stats["fan_speed"]`); on K2 `now(None)` the tzinfo assert fails.

### T2 — invocation construction → kills K3 (11) + K4 (21)

```python
def test_nvidia_smi_invocation_arguments():
    """The nvidia-smi call must pin argv, output capture, text mode, timeout, check=False.

    Given: nvidia-smi is available
    When: _get_gpu_stats_nvidia_smi() builds the subprocess call
    Then: argv and safety kwargs are exactly as specified (bounded wait,
          captured output, no CalledProcessError bypass)
    """
    monitor = GPUMonitor.__new__(GPUMonitor)
    monitor._nvidia_smi_available = True
    monitor._nvidia_smi_path = "/usr/bin/nvidia-smi"
    monitor._gpu_name = "Test GPU"

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "39, 29.61, 35, 175, 24576, NVIDIA RTX A5500"

    with patch("subprocess.run", return_value=mock_result, autospec=True) as mock_run:
        monitor._get_gpu_stats_nvidia_smi()

    args, kwargs = mock_run.call_args
    assert args[0] == [
        "/usr/bin/nvidia-smi",
        "--query-gpu=temperature.gpu,power.draw,utilization.gpu,memory.used,memory.total,name",
        "--format=csv,noheader,nounits",
    ]
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert kwargs["timeout"] == 5
    assert kwargs["check"] is False


@pytest.mark.asyncio
async def test_nvidia_smi_async_invocation_arguments():
    """Async wrapper must pass the same argv with text mode and a bounded timeout."""
    monitor = GPUMonitor.__new__(GPUMonitor)
    monitor._nvidia_smi_available = True
    monitor._nvidia_smi_path = "/usr/bin/nvidia-smi"
    monitor._gpu_name = "Test GPU"

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "42, 32.5, 45, 2048, 24576, NVIDIA RTX A5500"
    mock_result.stderr = ""

    with patch(
        "backend.core.async_utils.async_subprocess_run",
        new_callable=AsyncMock,
        return_value=mock_result,
    ) as mock_run:
        await monitor._get_gpu_stats_nvidia_smi_async()

    args, kwargs = mock_run.call_args
    assert args[0] == [
        "/usr/bin/nvidia-smi",
        "--query-gpu=temperature.gpu,power.draw,utilization.gpu,memory.used,memory.total,name",
        "--format=csv,noheader,nounits",
    ]
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert kwargs["timeout"] == 5.0
```

// UNVERIFIED - not yet run red/green. Any argv text change / removal kills `args[0]`; each kwargs flip/removal kills its own `kwargs[...]` assert (removed kwarg → `KeyError`).

### T3 — malformed field layout sensitivity → kills K5 (20) + K6 (8)

```python
@pytest.mark.parametrize(
    ("stdout", "expected"),
    [
        # 5 fields, no name -> gpu_name falls back to self._gpu_name
        ("39, 29.61, 35, 175, 24576", (39.0, 29.61, 35.0, 175, 24576, "Test GPU")),
        # empty field must poison only ITS OWN value, never a neighbour's
        ("39, , 35, 175, 24576, Test GPU", (39.0, None, 35.0, 175, 24576, "Test GPU")),
        ("39, 29.61, , 175, 24576, Test GPU", (39.0, 29.61, None, 175, 24576, "Test GPU")),
        ("39, 29.61, 35, , 24576, Test GPU", (39.0, 29.61, 35.0, None, 24576, "Test GPU")),
        ("39, 29.61, 35, 175, , Test GPU", (39.0, 29.61, 35.0, 175, None, "Test GPU")),
        ("39, 29.61, 35, 175, 24576, ", (39.0, 29.61, 35.0, 175, 24576, "")),
        # [N/A] in one field must not null the previous field's valid value
        ("39, [N/A], 35, 175, 24576, Test GPU", (39.0, None, 35.0, 175, 24576, "Test GPU")),
        ("39, 29.61, [N/A], 175, 24576, Test GPU", (39.0, 29.61, None, 175, 24576, "Test GPU")),
        ("39, 29.61, 35, [N/A], 24576, Test GPU", (39.0, 29.61, 35.0, None, 24576, "Test GPU")),
        ("39, 29.61, 35, 175, [N/A], Test GPU", (39.0, 29.61, 35.0, 175, None, "Test GPU")),
        ("39, 29.61, 35, 175, 24576, [N/A]", (39.0, 29.61, 35.0, 175, 24576, "[N/A]")),
    ],
)
def test_nvidia_smi_field_position_sensitivity(stdout, expected):
    """Each field's parse guard must read ONLY its own column and honor len(parts).

    Given: nvidia-smi output with empty/[N/A]/missing columns in various positions
    When: _get_gpu_stats_nvidia_smi() parses it
    Then: every metric is keyed strictly to its own column index,
          and a 5-field line (no name) still parses with the cached name
    """
    monitor = GPUMonitor.__new__(GPUMonitor)
    monitor._nvidia_smi_available = True
    monitor._nvidia_smi_path = "/usr/bin/nvidia-smi"
    monitor._gpu_name = "Test GPU"

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = stdout

    with patch("subprocess.run", return_value=mock_result, autospec=True):
        stats = monitor._get_gpu_stats_nvidia_smi()

    temperature, power_usage, gpu_utilization, memory_used, memory_total, gpu_name = expected
    assert stats["temperature"] == temperature
    assert stats["power_usage"] == power_usage
    assert stats["gpu_utilization"] == gpu_utilization
    assert stats["memory_used"] == memory_used
    assert stats["memory_total"] == memory_total
    assert stats["gpu_name"] == gpu_name


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("stdout", "expected"),
    [
        ("39, 29.61, 35, 175, 24576", (39.0, 29.61, 35.0, 175, 24576, "Test GPU")),
        ("39, , 35, 175, 24576, Test GPU", (39.0, None, 35.0, 175, 24576, "Test GPU")),
        ("39, 29.61, , 175, 24576, Test GPU", (39.0, 29.61, None, 175, 24576, "Test GPU")),
        ("39, 29.61, 35, , 24576, Test GPU", (39.0, 29.61, 35.0, None, 24576, "Test GPU")),
        ("39, 29.61, 35, 175, , Test GPU", (39.0, 29.61, 35.0, 175, None, "Test GPU")),
        ("39, 29.61, 35, 175, 24576, ", (39.0, 29.61, 35.0, 175, 24576, "")),
        ("39, [N/A], 35, 175, 24576, Test GPU", (39.0, None, 35.0, 175, 24576, "Test GPU")),
        ("39, 29.61, [N/A], 175, 24576, Test GPU", (39.0, 29.61, None, 175, 24576, "Test GPU")),
        ("39, 29.61, 35, [N/A], 24576, Test GPU", (39.0, 29.61, 35.0, None, 24576, "Test GPU")),
        ("39, 29.61, 35, 175, [N/A], Test GPU", (39.0, 29.61, 35.0, 175, None, "Test GPU")),
        ("39, 29.61, 35, 175, 24576, [N/A]", (39.0, 29.61, 35.0, 175, 24576, "[N/A]")),
    ],
)
async def test_nvidia_smi_async_field_position_sensitivity(stdout, expected):
    """Async parser must bind each metric strictly to its own column too."""
    monitor = GPUMonitor.__new__(GPUMonitor)
    monitor._nvidia_smi_available = True
    monitor._nvidia_smi_path = "/usr/bin/nvidia-smi"
    monitor._gpu_name = "Test GPU"

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = stdout
    mock_result.stderr = ""

    with patch(
        "backend.core.async_utils.async_subprocess_run",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        stats = await monitor._get_gpu_stats_nvidia_smi_async()

    temperature, power_usage, gpu_utilization, memory_used, memory_total, gpu_name = expected
    assert stats["temperature"] == temperature
    assert stats["power_usage"] == power_usage
    assert stats["gpu_utilization"] == gpu_utilization
    assert stats["memory_used"] == memory_used
    assert stats["memory_total"] == memory_total
    assert stats["gpu_name"] == gpu_name
```

// UNVERIFIED - not yet run red/green. Coverage map: empty at column j kills field j-1's first-operand shift; `[N/A]` at column j (left neighbour valid) kills field j-1's second-operand shift; the 5-field case kills `<5→<=5`, `<5→<6`, `>5→>=`, `>5→(… or True)`, and both memory_total sibling shifts (IndexError→RuntimeError vs clean fallback).

### T4 — async error message carries stderr → kills K7 (4)

```python
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("stderr", "must_contain", "must_not_contain"),
    [
        (
            "NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver",
            "NVIDIA-SMI has failed",
            [],
        ),
        # stderr missing/empty -> no fabricated placeholder text in the message
        (None, "nvidia-smi returned error", ["XXXX", "None"]),
        ("", "nvidia-smi returned error", ["XXXX"]),
    ],
)
async def test_nvidia_smi_async_error_message_includes_stderr(stderr, must_contain, must_not_contain):
    """The RuntimeError must relay the real stderr and invent nothing when stderr is empty."""
    monitor = GPUMonitor.__new__(GPUMonitor)
    monitor._nvidia_smi_available = True
    monitor._nvidia_smi_path = "/usr/bin/nvidia-smi"
    monitor._gpu_name = "Test GPU"

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = stderr

    with (
        patch(
            "backend.core.async_utils.async_subprocess_run",
            new_callable=AsyncMock,
            return_value=mock_result,
        ),
        pytest.raises(RuntimeError) as exc_info,
    ):
        await monitor._get_gpu_stats_nvidia_smi_async()

    message = str(exc_info.value)
    assert must_contain in message
    for junk in must_not_contain:
        assert junk not in message
```

// UNVERIFIED - not yet run red/green. Case 1 kills ASYNC#26 (message loses stderr) and #28 (`"None"` relayed instead). Case 2 kills #27 (`str(None)`→"None"). Case 3 kills #29 (`else "XXXX"`).

### T5 — multi-GPU output uses the first line → kills K8 (2)

```python
def test_nvidia_smi_multiple_gpus_uses_first_line():
    """With several GPUs reported, the first GPU's line must be parsed, whole.

    Given: nvidia-smi returns one CSV line per GPU (multi-line stdout)
    When: _get_gpu_stats_nvidia_smi() parses it
    Then: only GPU0's fields appear in the stats
    """
    monitor = GPUMonitor.__new__(GPUMonitor)
    monitor._nvidia_smi_available = True
    monitor._nvidia_smi_path = "/usr/bin/nvidia-smi"
    monitor._gpu_name = "Test GPU"

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = (
        "39, 29.61, 35, 175, 24576, GPU0\n"
        "44, 33.2, 50, 2048, 24576, GPU1"
    )

    with patch("subprocess.run", return_value=mock_result, autospec=True):
        stats = monitor._get_gpu_stats_nvidia_smi()

    assert stats["gpu_name"] == "GPU0"
    assert stats["temperature"] == 39.0
    assert stats["power_usage"] == 29.61
    assert stats["memory_used"] == 175
```

// UNVERIFIED - not yet run red/green. On SMI#31/ASYNC#35 (`split("XX\nXX")`) the newline is never a separator, so `gpu_name` becomes `"GPU0\n44"` and later fields bleed GPU1's values.

### T6 — availability guard rejects mismatched state → kills K9 (2)

```python
def test_nvidia_smi_guard_requires_both_available_and_path():
    """available-without-path (or path-without-available) must be refused, not executed.

    Given: nvidia-smi availability flags disagree (e.g. init race)
    When: _get_gpu_stats_nvidia_smi() is called
    Then: RuntimeError('nvidia-smi not available') without touching subprocess.run
    """
    for available, path in ((True, None), (False, "/usr/bin/nvidia-smi")):
        monitor = GPUMonitor.__new__(GPUMonitor)
        monitor._nvidia_smi_available = available
        monitor._nvidia_smi_path = path
        monitor._gpu_name = "Test GPU"

        with (
            patch(
                "subprocess.run",
                side_effect=AssertionError("subprocess must not run"),
                autospec=True,
            ),
            pytest.raises(RuntimeError, match="nvidia-smi not available"),
        ):
            monitor._get_gpu_stats_nvidia_smi()


@pytest.mark.asyncio
async def test_nvidia_smi_async_guard_requires_both_available_and_path():
    """Async guard must reject mismatched availability state as well."""
    for available, path in ((True, None), (False, "/usr/bin/nvidia-smi")):
        monitor = GPUMonitor.__new__(GPUMonitor)
        monitor._nvidia_smi_available = available
        monitor._nvidia_smi_path = path
        monitor._gpu_name = "Test GPU"

        with (
            patch(
                "backend.core.async_utils.async_subprocess_run",
                new_callable=AsyncMock,
                side_effect=AssertionError("subprocess must not run"),
            ),
            pytest.raises(RuntimeError, match="nvidia-smi not available"),
        ):
            await monitor._get_gpu_stats_nvidia_smi_async()
```

// UNVERIFIED - not yet run red/green. On the `or→and` mutants the guard passes, the mocked runner raises AssertionError, which the broad `except Exception` re-wraps as `"Failed to get GPU stats via nvidia-smi: ..."` — the `match=` assertion fails.

## Notes for WP4.4

- Highest yield per effort: **T1 (82 kills, 2 tests)**, then **T3 (28 kills)** and **T2 (32 kills)**. The six drafts above kill 148/150 TEST-GAP survivors.
- K10/K11 (44 survivors) should ship as an **equivalent-mutant suppression list**, not tests — every member was shown semantically identical (ValueError path yields the same `None`) or message-text-only under `re.search` matching.
- Both draft suites are symmetric per function because the twins' survivor sets mirror 1:1 (SMI#N ↔ ASYNC#N±offset); a shared helper/fixture could dedupe T3's parametrize table if the duplication trips review.
- Async mock path note: the async function imports `async_subprocess_run` *inside* the body at call time (gpu_monitor.py:387), so patching `backend.core.async_utils.async_subprocess_run` (as existing tests do) is correct and hermetic.
