# WP4.4 Triage Dossier — backend/services/gpu_detection_service.py

**Run context**: mutmut baseline, meta `mutants/backend/services/gpu_detection_service.py.meta`
(242 keys: 159 killed, **83 survived**, 0 unchecked). All survivor diffs extracted by
diffing clobbered variant bodies in `mutants/backend/services/gpu_detection_service.py`
against `__mutmut_orig` (async-aware region splitter; `uv run mutmut show` confirmed
working for spot checks).

**Covering test file (sole)**: `backend/tests/unit/services/test_gpu_detection_service.py`
- fixtures: L46–200 (`mock_pynvml`, `nvidia_smi_output_two_gpus`, `nvidia_smi_utilization_output`, `service_reset`)
- `TestGpuDetectionServiceInit` L323–351 · `TestGpuDetectionPynvml` L358–434 ·
  `TestGpuDetectionNvidiaSmi` L441–553 · `TestGpuUtilizationQueries` L556–636 ·
  `TestVramRequirements` L639–710 · `TestErrorHandling` L713–790 ·
  `TestContainerEnvironment` L793–838 · `TestGpuDetectionIntegration` L841–887

**Systemic weakness found**: every nvidia-smi test replaces
`async_subprocess_run` with a `MagicMock` whose return value is a single canned
`CompletedProcess` (or a plain `MagicMock()` for the secondary memory.total call) and
never inspects the call args. That one fixture shape hides 3 whole clusters
(C2/C3/C6, 30 mutants): the subprocess argv contract, the separate
`_get_gpu_vram_total_nvidia_smi` call, and the multi-COLUMN csv parsing (only the FIRST
CSV field is read for the whole stdout — `int(result.stdout.strip())` would crash on the
utilization output, yet tests still pass). The pynvml side's weakness is exact-value
assertions with `pytest.approx(rel=0.01)` plus no test of the optional-field FAILURE
paths (temperature / power / compute-capability raising).

## Cluster table (83 = 51 TEST-GAP + 23 EQUIVALENT + 9 LOW-VALUE)

| # | Pattern | Func(s) | n | Class | Keys (func__mutmut_N) |
|---|---------|---------|---|-------|----------------------|
| C1 | NVML init-state flips: `_ensure_nvml` guard `or`→`and` / `not initialized`→`initialized`; `_nvml_initialized=True`→falsy after successful `nvmlInit()` | `_ensure_nvml`, `_init_pynvml` | 4 | TEST-GAP | _ensure_nvml 1,5; _init_pynvml 4,5 |
| C2 | nvidia-smi **vram-total call unasserted + guard flips**: `if not path`→`if path`, `result=None`, cmd-arg dropped, `returncode==0 and stdout` → `or` / `!=0` / `==1`, `int(None)`, final `return 0`→`return 1`, and `vram_total_mb=None` in the util builder | `_get_gpu_vram_total_nvidia_smi`, `_get_utilization_nvidia_smi` | 10 | TEST-GAP | vram_total 1,2,5,12,13,14,15,16; _get_utilization_nvidia_smi 21,27 |
| C3 | nvidia-smi **argv contract unasserted**: cmd list → `None`, flag text `XX…XX`-wrapped or CASE-SWAPPED (`--QUERY-GPU=…`) in all three subprocess call sites | `_detect_gpus_nvidia_smi`, `_get_utilization_nvidia_smi`, `_get_gpu_vram_total_nvidia_smi` | 15 | TEST-GAP | detect 3,7,8,9,10; util 3,7,8,9,10; vram_total 3,7,8,9,10 |
| C4 | pynvml VRAM bytes→MB `//`→`/` (int→float) in both info paths | `_get_gpu_info_pynvml`, `_get_utilization_pynvml` | 4 | TEST-GAP | gpu_info 11,16; util_pynvml 11,16 |
| C5 | pynvml optional-field **failure paths never taken**: `temperature=None`/`power_watts=None` sentinel→`""`, temperature type const→`None`, power `mw/1000.0`→`/1001.0` (passes `approx(rel=0.01)`) | `_get_utilization_pynvml` | 4 | TEST-GAP | util_pynvml 20,24,27,32 |
| C6 | nvidia-smi utilization **optional-column parsing unasserted**: `mem_util 0.0`→`None`/`1.0`, `float(parts[2]) if parts[2]` → `… if (parts[2]) or True` (temp), `if parts[3]` (power swapped in) — empty-field CSV never fed | `_get_utilization_nvidia_smi` | 5 | TEST-GAP | util 25,39,43,46,48 |
| C7 | **gpu_index not threaded / not asserted** in nvidia-smi fallback: `get_gpu_utilization` passes `None`, builder gets `gpu_index=None`, vram lookup gets `None` | `get_gpu_utilization`, `_get_utilization_nvidia_smi` | 3 | TEST-GAP | get_gpu_utilization 2; util 22,23 |
| C8 | Constructor defaults under weak assert (`service._nvml_available is not None`): `_pynvml=None`→`""`; `shutil.which("nvidia-smi")` name → `"XXnvidia-smiXX"` / `"NVIDIA-SMI"` | `__init__` | 3 | TEST-GAP | __init__ 1,9,10 |
| C9 | pynvml compute-capability optionality: sentinel `None`→`""` when probe raises; `nvmlDeviceGetCudaComputeCapability(None)` (mock ignores the discarded arg) | `_get_gpu_info_pynvml` | 2 | TEST-GAP | gpu_info 20,22 |
| C16 | nvidia-smi parsed device: `uuid=parts[4]`→`uuid=None` — fallback tests assert name/vram but **never uuid** | `_detect_gpus_nvidia_smi` | 1 | TEST-GAP | detect 29 |
| C10 | Log **message-text** mutants (→`None`, `XX…XX`, UPPER/lower case) on warning/error/info lines | `_init_pynvml`(6,7,8,9), `_detect_gpus_nvidia_smi`(14,44,45,46), `_detect_gpus_pynvml`(8), `_get_gpu_info_pynvml`(36), `_get_utilization_pynvml`(49), `detect_gpus`(1,2,3,4) | 15 | EQUIVALENT | — |
| C11 | Constructor dead initializations: all `_init_pynvml` branches (success / ImportError / Exception) unconditionally re-assign `_nvml_available`; `_nvidia_smi_path` re-assigned from `shutil.which` — falsy/True swaps never read before overwrite | `__init__` | 5 | EQUIVALENT | __init__ 2,3,4,5,6 |
| C13 | `_init_pynvml` failure-path `_nvml_available=False`→`None`/`True`: all readers are truthiness checks (`if not self._nvml_available`), identical behavior | `_init_pynvml` | 2 | EQUIVALENT | _init_pynvml 10,11 |
| C17 | Dropped explicit `compute_capability=None` kwarg → dataclass default is also `None` | `_detect_gpus_nvidia_smi` | 1 | EQUIVALENT | detect 35 |
| C12 | nvidia-smi subprocess **timeout constants**: `10.0`→`None`/`11.0`/kwarg-deleted, `5.0`→`None`/`6.0`/kwarg-deleted — real change, but pinning exact timeout seconds is brittle; nobody should assert `timeout == 10.0` | detect / util / vram_total | 9 | LOW-VALUE | detect 4,6,11; util 4,6,11; vram_total 4,6,11 |

Sum check: 4+10+15+4+4+5+3+3+2+1 = 51 TEST-GAP; 15+5+2+1 = 23 EQUIVALENT; 9 LOW-VALUE → **83**.

## Why each TEST-GAP cluster is a gap, not "no coverage"

`tests_by_mangled_function_name` (mutmut-stats.json) lists the covering tests for every
function below; each mutant's line IS executed by those tests, but no assertion
discriminates. Notable per-cluster evidence:

- **C2**: only covering test for `_get_gpu_vram_total_nvidia_smi` is
  `test_get_gpu_utilization_nvidia_smi_fallback` (file L607–636) — it never asserts
  `util.vram_total_mb`, and its single canned stdout answers BOTH subprocess calls, so
  every success/failure guard flip returns the same (unasserted) number.
- **C3**: the same fallback test patches `async_subprocess_run` (autospec) but never
  checks `mock_run.call_args` → the entire nvidia-smi CLI contract is unpinned.
- **C4**: `test_detect_gpus_two_gpus` (L362) asserts `== 24576`; `24576.0 == 24576` is
  True in Python, so `/` vs `//` is invisible without `isinstance` or a non-MiB-multiple
  byte fixture.
- **C5/C9**: `mock_pynvml` (fixture L46) configures temperature/power/compute-capability
  to SUCCEED; the `except Exception: pass` fallback branches (L386–387, L394–395,
  L279–280) are only entered by mutants that make the call itself fail
  (`nvmlDeviceGetTemperature(handle, None)` still returns 65 because the fixture's
  `side_effect = lambda h, _: …` discards the type arg — that const is also unasserted).
- **C6**: `nvidia_smi_utilization_output` (L186) is `"75, 8192, 65, 150.5"` — all fields
  present; the `if parts[2] else None` truthiness branches (L445–446) are never taken
  with empty fields, and `memory_utilization_percent` (a hardcoded `0.0`) is never
  asserted in the fallback test.
- **C7**: pynvml tests assert `util.gpu_index` (L569, L587) but the nvidia-smi fallback
  test does not — that's exactly where `gpu_index=None` mutants live.
- **C8/C16**: `test_init_default` (L326) is literally `assert service._nvml_available is
  not None`; nvidia-smi device tests (L445, L473) assert name/vram but not uuid;
  `shutil.which` is always patched to a canned path without checking the queried name.

## Drafted kill-tests (append to `backend/tests/unit/services/test_gpu_detection_service.py`)

TDD procedure (one line): each assertion set must FAIL against the cluster's mutant diff
(named above) and PASS against the unmutated module — run
`uv run pytest backend/tests/unit/services/test_gpu_detection_service.py -k
TestWp44KillTests` red-then-green before committing. **All UNVERIFIED — not yet run
red/green** (mutation run owns this machine; no test executed during this triage).

```python
# =============================================================================
# WP4.4 Kill Tests — mutation-survivor gaps (UNVERIFIED - not yet run red/green)
# =============================================================================


def _proc(returncode: int, stdout: str) -> MagicMock:
    """Build a CompletedProcess-like mock result."""
    result = MagicMock()
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = ""
    return result


class TestWp44KillTests:
    """Kill tests for surviving mutants in gpu_detection_service (WP4.4 feed)."""

    # ---- D1 kills C3 (argv contract, 15 mutants; also vram_total__6 timeout kwarg drop) ----
    # UNVERIFIED - not yet run red/green
    @pytest.mark.asyncio
    async def test_nvidia_smi_detect_command_exact_argv(
        self, nvidia_smi_output_two_gpus: str, service_reset: None
    ) -> None:
        """_detect_gpus_nvidia_smi must invoke nvidia-smi with the exact query argv."""
        with (
            patch("shutil.which", return_value="/usr/bin/nvidia-smi", autospec=True),
            patch(
                "backend.services.gpu_detection_service.async_subprocess_run", autospec=True
            ) as mock_run,
        ):
            mock_run.return_value = _proc(0, nvidia_smi_output_two_gpus)
            service = GpuDetectionService()
            service._nvml_available = False
            service._nvidia_smi_path = "/usr/bin/nvidia-smi"
            await service.detect_gpus()

        mock_run.assert_called_once_with(
            [
                "/usr/bin/nvidia-smi",
                "--query-gpu=index,name,memory.total,memory.used,uuid",
                "--format=csv,noheader,nounits",
            ],
            timeout=10.0,
        )

    # UNVERIFIED - not yet run red/green
    @pytest.mark.asyncio
    async def test_nvidia_smi_utilization_commands_exact_argv(self, service_reset: None) -> None:
        """Utilization query + secondary memory.total query must both pin argv + timeout."""
        with (
            patch("shutil.which", return_value="/usr/bin/nvidia-smi", autospec=True),
            patch(
                "backend.services.gpu_detection_service.async_subprocess_run", autospec=True
            ) as mock_run,
        ):
            mock_run.side_effect = [
                _proc(0, "75, 8192, 65, 150.5\n"),
                _proc(0, "24576\n"),
            ]
            service = GpuDetectionService()
            service._nvml_available = False
            service._nvidia_smi_path = "/usr/bin/nvidia-smi"
            util = await service.get_gpu_utilization(1)

        assert util is not None
        calls = mock_run.call_args_list
        assert len(calls) == 2
        assert calls[0].args[0] == [
            "/usr/bin/nvidia-smi",
            "--id=1",
            "--query-gpu=utilization.gpu,memory.used,temperature.gpu,power.draw",
            "--format=csv,noheader,nounits",
        ]
        assert calls[0].kwargs == {"timeout": 10.0}
        # kills util__mutmut_22 (gpu_index None → "--id=None") and vram_total 3/5/7-10
        assert calls[1].args[0] == [
            "/usr/bin/nvidia-smi",
            "--id=1",
            "--query-gpu=memory.total",
            "--format=csv,noheader,nounits",
        ]
        assert calls[1].kwargs == {"timeout": 5.0}

    # ---- D2 kills C2 (vram-total, 10 mutants) + C16 (uuid) + C7 (index) ----
    # UNVERIFIED - not yet run red/green
    @pytest.mark.asyncio
    async def test_vram_total_nvidia_smi_success_and_failure_paths(
        self, service_reset: None
    ) -> None:
        """_get_gpu_vram_total_nvidia_smi parses only on rc==0 + non-empty stdout, else 0."""
        with (
            patch("shutil.which", return_value="/usr/bin/nvidia-smi", autospec=True),
            patch(
                "backend.services.gpu_detection_service.async_subprocess_run", autospec=True
            ) as mock_run,
        ):
            service = GpuDetectionService()
            service._nvml_available = False
            service._nvidia_smi_path = "/usr/bin/nvidia-smi"

            mock_run.return_value = _proc(0, "24576\n")
            assert await service._get_gpu_vram_total_nvidia_smi(0) == 24576

            # rc != 0 even with parseable stdout must NOT be trusted (kills or/!=/==1 flips)
            mock_run.return_value = _proc(1, "24576\n")
            assert await service._get_gpu_vram_total_nvidia_smi(0) == 0

            # rc == 0 but empty stdout → 0
            mock_run.return_value = _proc(0, "  \n")
            assert await service._get_gpu_vram_total_nvidia_smi(0) == 0

            # rc == 0, unparseable stdout → 0 via except
            mock_run.return_value = _proc(0, "N/A\n")
            assert await service._get_gpu_vram_total_nvidia_smi(0) == 0

            # missing binary → 0 WITHOUT invoking the subprocess (kills guard flip mut_1)
            service._nvidia_smi_path = None
            calls_before = mock_run.call_count
            assert await service._get_gpu_vram_total_nvidia_smi(0) == 0
            assert mock_run.call_count == calls_before

    # UNVERIFIED - not yet run red/green
    @pytest.mark.asyncio
    async def test_nvidia_smi_fallback_preserves_uuid_index_and_total(
        self, nvidia_smi_output_two_gpus: str, service_reset: None
    ) -> None:
        """nvidia-smi fallback must carry uuid/gpu_index/vram_total through to the dataclasses."""
        with (
            patch("shutil.which", return_value="/usr/bin/nvidia-smi", autospec=True),
            patch(
                "backend.services.gpu_detection_service.async_subprocess_run", autospec=True
            ) as mock_run,
        ):
            service = GpuDetectionService()
            service._nvml_available = False
            service._nvidia_smi_path = "/usr/bin/nvidia-smi"

            mock_run.side_effect = [_proc(0, nvidia_smi_output_two_gpus)]
            gpus = await service.detect_gpus()
            assert gpus[0].uuid == "GPU-uuid-0"          # kills detect__mutmut_29 (C16)
            assert gpus[1].uuid == "GPU-uuid-1"
            assert gpus[1].index == 1

            mock_run.side_effect = [
                _proc(0, "75, 8192, 65, 150.5\n"),
                _proc(0, "24576\n"),
            ]
            util = await service.get_gpu_utilization(0)
            assert util is not None
            assert util.gpu_index == 0                    # kills get_gpu_utilization__2, util__23 (C7)
            assert util.vram_total_mb == 24576            # kills util__mutmut_21, _27 (C2)
            assert util.memory_utilization_percent == 0.0  # kills util__25/_39 (C6, shared)

    # ---- D3 kills C6 (optional-column parsing, 5 mutants) ----
    # UNVERIFIED - not yet run red/green
    @pytest.mark.asyncio
    async def test_nvidia_smi_utilization_empty_optional_fields(self, service_reset: None) -> None:
        """Empty temperature/power columns must yield None, never a float() crash."""
        with (
            patch("shutil.which", return_value="/usr/bin/nvidia-smi", autospec=True),
            patch(
                "backend.services.gpu_detection_service.async_subprocess_run", autospec=True
            ) as mock_run,
        ):
            service = GpuDetectionService()
            service._nvml_available = False
            service._nvidia_smi_path = "/usr/bin/nvidia-smi"

            # both optionals empty
            mock_run.side_effect = [_proc(0, "75, 8192, , \n"), _proc(0, "24576\n")]
            util = await service.get_gpu_utilization(0)
            assert util is not None
            assert util.temperature_celsius is None       # kills util__43, _48 (or-True flips)
            assert util.power_watts is None

            # temperature empty but power present (kills util__46: cond reads parts[3])
            mock_run.side_effect = [_proc(0, "75, 8192, , 150.5\n"), _proc(0, "24576\n")]
            util = await service.get_gpu_utilization(0)
            assert util is not None
            assert util.temperature_celsius is None
            assert util.power_watts == pytest.approx(150.5)

    # ---- D4 kills C5 (pynvml optional-failure sentinels, 4) + C4 (int MB, 4) ----
    # UNVERIFIED - not yet run red/green
    @pytest.mark.asyncio
    async def test_pynvml_utilization_optional_failures(
        self, mock_pynvml: MagicMock, service_reset: None
    ) -> None:
        """Raising temperature/power probes must leave None fields (not '' sentinels)."""
        mock_pynvml.nvmlDeviceGetTemperature.side_effect = Exception("no sensor")
        mock_pynvml.nvmlDeviceGetPowerUsage.side_effect = Exception("not supported")
        with patch.dict(sys.modules, {"pynvml": mock_pynvml}):
            service = GpuDetectionService()
            util = await service.get_gpu_utilization(0)
        assert util is not None
        assert util.temperature_celsius is None           # kills util_pynvml__20 ("" sentinel)
        assert util.power_watts is None                   # kills util_pynvml__27 ("" sentinel)

    # UNVERIFIED - not yet run red/green
    @pytest.mark.asyncio
    async def test_pynvml_utilization_exact_fields_and_int_mb(
        self, mock_pynvml: MagicMock, service_reset: None
    ) -> None:
        """Temperature type const passed through, power exact, MB fields are ints."""
        with patch.dict(sys.modules, {"pynvml": mock_pynvml}):
            service = GpuDetectionService()
            util = await service.get_gpu_utilization(0)
            gpus = await service._get_gpu_info_pynvml(0)

        assert util is not None and gpus is not None
        handle = mock_pynvml.nvmlDeviceGetHandleByIndex(0)
        # kills util_pynvml__24 (handle, None) — fixture lambda discards the const today
        mock_pynvml.nvmlDeviceGetTemperature.assert_called_with(
            handle, mock_pynvml.NVML_TEMPERATURE_GPU
        )
        # kills util_pynvml__32 (/1001.0 — existing test used approx(rel=0.01))
        assert util.power_watts == 150.0
        # kills util_pynvml__11/_16 and gpu_info__11/_16 (float from `/` not `//`)
        assert isinstance(util.vram_total_mb, int) and util.vram_total_mb == 24576
        assert isinstance(util.vram_used_mb, int) and util.vram_used_mb == 8192
        assert isinstance(gpus.vram_total_mb, int) and gpus.vram_total_mb == 24576
        assert isinstance(gpus.vram_used_mb, int) and gpus.vram_used_mb == 8192

    # ---- D5 kills C1 (_ensure_nvml / NVML init-state, 4) ----
    # UNVERIFIED - not yet run red/green
    def test_ensure_nvml_state_matrix(self, service_reset: None) -> None:
        """_ensure_nvml gates on availability AND module presence AND lazy init."""
        with (
            patch("shutil.which", return_value=None, autospec=True),
            patch.dict(sys.modules, {"pynvml": None}),
        ):
            service = GpuDetectionService()
        # unavailable module present → False (kills _ensure_nvml__1: `or`→`and` → True)
        service._nvml_available = False
        service._pynvml = MagicMock()
        service._nvml_initialized = False
        assert service._ensure_nvml() is False
        # available + uninitialized module → lazy-init exactly once, then True
        service._nvml_available = True
        mock_mod = service._pynvml
        assert service._ensure_nvml() is True
        mock_mod.nvmlInit.assert_called_once_with()       # kills _ensure_nvml__5 (flip skips init)
        assert service._nvml_initialized is True
        assert service._ensure_nvml() is True
        mock_mod.nvmlInit.assert_called_once_with()       # still once — already initialized

    # UNVERIFIED - not yet run red/green
    def test_successful_pynvml_init_marks_state_once(
        self, mock_pynvml: MagicMock, service_reset: None
    ) -> None:
        """After successful pynvml init: available+initialized flags set, nvmlInit called once."""
        with patch.dict(sys.modules, {"pynvml": mock_pynvml}):
            service = GpuDetectionService()
            assert service._nvml_available is True
            assert service._nvml_initialized is True      # kills _init_pynvml__4 (""), __5 (False)
            mock_pynvml.nvmlInit.assert_called_once_with()
            assert service._ensure_nvml() is True
            mock_pynvml.nvmlInit.assert_called_once_with()  # falsy state → re-init → kills __4/__5

    # ---- D6 kills C8 (constructor defaults + binary name, 3) ----
    # UNVERIFIED - not yet run red/green
    def test_constructor_defaults_and_binary_lookup(self, service_reset: None) -> None:
        """Clean-init (no pynvml binary) leaves exact defaults and queries the right binary."""
        with (
            patch("shutil.which", return_value=None, autospec=True) as mock_which,
            patch.dict(sys.modules, {"pynvml": None}),  # `import pynvml` → ImportError
        ):
            service = GpuDetectionService()

        mock_which.assert_called_once_with("nvidia-smi")  # kills __init__ 9 ("XXnvidia-smiXX"), 10 ("NVIDIA-SMI")
        assert service._pynvml is None                    # kills __init__ 1 ("")
        assert service._nvml_available is False           # replaces weak `is not None` (L331)
        assert service._nvml_initialized is False
        assert service._nvidia_smi_path is None
```

## Drafts → cluster coverage map

| Draft | Kills | Mutants |
|-------|-------|---------|
| D1 (both argv tests) | C3 | 15 |
| D2 | C2 + C16 + C7 | 10 + 1 + 3 (util__22 dies via D1 argv) |
| D3 | C6 | 5 |
| D4 | C5 + C4 | 4 + 4 |
| D5 | C1 | 4 |
| D6 | C8 | 3 |

Undrafted TEST-GAP clusters (lower value): **C9** (2 mutants — pynvml compute-capability
failure sentinel; a one-line `compute_capability is None` assert on a
probe-raises fixture would do it). EQUIVALENT clusters C10/C11/C13/C17 need no test
(pure log text / dead initialization / falsy-swaps read only via truthiness). LOW-VALUE
C12 (timeout constants) intentionally left unasserted.

## TDD procedure (single line)

Run the new class against the mutated sources (`uv run mutmut run` re-check or manual
variant swap): each assertion above must fail red on its cluster's mutant diff and pass
green on the unmutated `backend/services/gpu_detection_service.py` before the tests are
committed to `backend/tests/unit/services/test_gpu_detection_service.py`.
