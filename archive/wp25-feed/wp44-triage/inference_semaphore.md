# WP4.4 Triage Dossier — backend/services/inference_semaphore.py

**Wave**: gen-2 NEW tier (first tally of this module)
**Source**: `backend/services/inference_semaphore.py` (312 lines) — asyncio.Semaphore singleton + memory-pressure permit throttling (NEM-1463, NEM-1727)
**Mutants**: 135 total → 58 killed / **77 survived** / 0 unchecked (meta read clean, single pass)
**Diffs**: all 77 via `uv run mutmut show` (scratch copy: /tmp/wp25/wp44-triage/scratch/all_diffs.txt) — no manual fallback needed.

## Covering tests (from mutmut-stats.json tests_by_mangled_function_name)

| File | Role / key lines |
|---|---|
| `backend/tests/unit/services/test_inference_semaphore.py` | PRIMARY. fixture `mock_settings` :40-49 (patches module `get_settings`, ai_max=4); autouse `reset_semaphore` :33-40. Init/singleton :58-93; `TestMemoryPressureThrottling` :305-418; `TestEdgeCases` :421-507 |
| `backend/tests/unit/services/test_memory_pressure.py` | `TestInferenceSemaphoreThrottling` :461-548 — **unpatched settings** (uses real config default), assertions loose (`<`, `>=`); `TestMemoryPressureIntegration::test_full_pressure_cycle` :684 |
| `backend/tests/unit/services/test_ai_inference_semaphore.py` | `TestInferenceSemaphoreModule` :460+ — singleton identity + concurrency limiting only |
| `backend/tests/unit/core/test_executors.py` | Tests a **different** `is_free_threaded` (backend.core.executors) — no coverage for this module's copy |

## Structural facts that drive classification

- `get_inference_semaphore()` calls `get_settings()`; the **actual** limit is `settings.ai_max_concurrent_inferences`. `is_free_threaded()` / `_get_default_permits()` feed ONLY the init log payload (diagnostics) — but `is_free_threaded()` is a public, docstring-promised API.
- The `is None` guards in reduce (:214) / restore (:288) are **dead code**: both run `semaphore = get_inference_semaphore()` first (:208/:286), which always sets both counts to ints → `or`→`and` there cannot change behavior in any reachable state.
- `_throttled_for_pressure` and `_current_permit_count` desyncs surface ONLY through a follow-up `reduce`/`restore` call or a spy on `get_inference_semaphore`.
- `None` swaps of falsy flags (`False`→`None`) are semantically equivalent (both falsy under `if not ...`).

## Cluster table (counts sum to 77)

| # | Pattern | Count | Class | Example keys (≤3) |
|---|---|---|---|---|
| 1 | init log payload text: message/extra-key renames & deletions in `get_inference_semaphore` logger.info | 14 | EQUIVALENT | x_get_inference_semaphore__mutmut_10, _14, _17 |
| 2 | init log payload VALUES: `free_threading`/`default_permits`→None, `using_custom_limit` !=→== | 3 | LOW-VALUE | x_get_inference_semaphore__mutmut_8, _9, _25 |
| 3 | `_get_default_permits` GIL default `return 4`→`5` (feeds only log fields) | 1 | LOW-VALUE | x__get_default_permits__mutmut_1 |
| 4 | `is_free_threaded`: hasattr target/name corrupt (×3) + `not` polarity flip | 4 | **TEST-GAP** | x_is_free_threaded__mutmut_1, _5, _7 |
| 5 | dead init-guard `or`→`and` in reduce & restore (counts always ints — guard unreachable) | 2 | EQUIVALENT | x_reduce_permits_for_memory_pressure__mutmut_3, x_restore_permits_after_pressure__mutmut_3 |
| 6 | reduce target floor `max(1,`→`max(2,` (CRITICAL `//2` and WARNING `*0.75`) — diverges at limits 2-3, hidden by existing ai_max=4/1 tests | 2 | **TEST-GAP** | x_reduce_permits_for_memory_pressure__mutmut_12, _20 |
| 7 | reduce `permits_to_remove <= 0`→`< 0`: at-boundary falls through, recomputes `_current_permit_count = original − 0`, desyncs → next restore releases nothing | 1 | **TEST-GAP** | x_reduce_permits_for_memory_pressure__mutmut_26 |
| 8 | acquire-loop guard `_value > 0`→`>= 0`: adds a 0.1s wait_for stall when exhausted, final `acquired` identical | 1 | LOW-VALUE | x_reduce_permits_for_memory_pressure__mutmut_44 |
| 9 | acquire-loop guard `_value > 0`→`> 1`: skips the acquire when exactly 1 permit free → reduction silently under-counts | 1 | **TEST-GAP** | x_reduce_permits_for_memory_pressure__mutmut_45 |
| 10 | `wait_for` timeout `0.1`→`None` / `1.1` (timeout path only entered via check→acquire race; never hit by tests) | 2 | LOW-VALUE | x_reduce_permits_for_memory_pressure__mutmut_47, _50 |
| 11 | reduce debug-log payload text/keys ("already at or below target") | 12 | EQUIVALENT | x_reduce_permits_for_memory_pressure__mutmut_28, _32, _35 |
| 12 | reduce warning-log payload text/keys ("Reduced … memory pressure") | 11 | EQUIVALENT | x_reduce_permits_for_memory_pressure__mutmut_58, _62, _66 |
| 13 | reset leaves `_original_permit_count`/`_current_permit_count = ""` — reinit always overwrites before any read; unobservable via public API | 2 | LOW-VALUE | x_reset_inference_semaphore__mutmut_2, _3 |
| 14 | reset `_throttled_for_pressure` False→None (falsy→falsy) | 1 | EQUIVALENT | x_reset_inference_semaphore__mutmut_4 |
| 15 | reset `_throttled_for_pressure` False→**True**: a post-reset `restore()` skips its short-circuit and **constructs the singleton as a side effect** | 1 | **TEST-GAP** | x_reset_inference_semaphore__mutmut_5 |
| 16 | reset debug-log text | 4 | EQUIVALENT | x_reset_inference_semaphore__mutmut_6, _7, _8 |
| 17 | restore `permits_to_restore <= 0`→`< 0`: at-0 fall-through releases `range(0)` = nothing; state identical, only info log differs | 1 | EQUIVALENT | x_restore_permits_after_pressure__mutmut_8 |
| 18 | restore `<= 0`→`<= 1`: a single-permit reduction is never released (existing restore tests all move ≥2 permits) | 1 | **TEST-GAP** | x_restore_permits_after_pressure__mutmut_9 |
| 19 | restore `_current_permit_count = _original_permit_count`→`None`: after one restore, the None-guard deadens all **future** throttling (silent no-op under real pressure) | 1 | **TEST-GAP** | x_restore_permits_after_pressure__mutmut_11 |
| 20 | restore `_throttled_for_pressure` False→None (falsy→falsy) | 1 | EQUIVALENT | x_restore_permits_after_pressure__mutmut_12 |
| 21 | restore `_throttled_for_pressure` False→**True**: redundant restores skip the short-circuit and hit the semaphore (observable only via spy — same kill vector as #15) | 1 | **TEST-GAP** | x_restore_permits_after_pressure__mutmut_13 |
| 22 | restore info-log payload text/keys | 10 | EQUIVALENT | x_restore_permits_after_pressure__mutmut_14, _18, _21 |

**Totals**: EQUIVALENT 56 (14+2+12+11+1+4+1+1+10) · LOW-VALUE 9 (3+1+1+2+3... = #2:3 + #3:1 + #8:1 + #10:2 + #13:2 = 9) · TEST-GAP 12 (4+2+1+1+1+1+1+1). **77 = 56+9+12** ✓

## TEST-GAP cluster notes

- **#4 is_free_threaded (4)**: tests execute the line (every `get_inference_semaphore()` call) but only feed a log field; `test_executors.py` covers the *other* module's copy. Flip `not` (mutmut_7) inverts free-threading detection — a public-API return assertion pair kills all 4 (draft T1).
- **#6 reduce floor (2)**: `test_minimum_one_permit_enforced` uses ai_max=1 (both floors behave identically at 1) and `test_reduce_permits_for_critical_pressure` uses ai_max=4 (`4//2=2 == max(2,2)`); nothing uses 2-3 where `max(1,x)` vs `max(2,x)` diverge.
- **#7 (1)**: double-reduce at the same level leaves `_current_permit_count` stale-high → restore releases 0 permits → capacity permanently stuck low. Existing `test_concurrent_pressure_changes` asserts nothing (exception-free only).
- **#9 (1)**: `test_reduce_permits_handles_exhausted_semaphore` uses `_value==0` (guard False for both) — no test exercises the `_value==1` boundary.
- **#15/#21 (2)**: throttle-flag clearing is never asserted; both killable with a `patch(...get_inference_semaphore)` spy asserting the no-op short-circuit (draft T4).
- **#18/#19 (2)**: restore tests always restore 2 permits (CRITICAL @ ai_max=4) and never run a second reduce/restore cycle.

## Drafted tests — target file: `backend/tests/unit/services/test_inference_semaphore.py`

**TDD procedure (all)**: run against mutant copy → the marked assert FAILS; run against original → passes. `# UNVERIFIED - not yet run red/green`

```python
// UNVERIFIED - not yet run red/green
# === add to imports at top of test_inference_semaphore.py ===
import sys
from backend.services.inference_semaphore import (
    get_inference_semaphore,
    is_free_threaded,           # NEW
    reduce_permits_for_memory_pressure,
    reset_inference_semaphore,
    restore_permits_after_pressure,
)


class TestFreeThreadedDetection:
    """Public-API contract for is_free_threaded() (kills cluster #4: mutmut_1/5/6/7)."""

    def test_gil_enabled_python_is_not_free_threaded(self) -> None:
        """With GIL enabled (standard builds), must return False (kills not-flip mutmut_7)."""
        with patch.object(sys, "_is_gil_enabled", return_value=True, create=True):
            assert is_free_threaded() is False

    def test_gil_disabled_python_is_free_threaded(self) -> None:
        """Free-threaded build (GIL disabled) must return True.

        Kills hasattr-target/name corruption (mutmut_1/5/6): those take the
        fallback branch and return False here.
        """
        with patch.object(sys, "_is_gil_enabled", return_value=False, create=True):
            assert is_free_threaded() is True

    def test_falls_back_to_false_without_gil_probe(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Old interpreters without sys._is_gil_enabled must report not free-threaded."""
        monkeypatch.delattr(sys, "_is_gil_enabled", raising=False)
        assert is_free_threaded() is False


class TestThrottleCycleAtMinimumLimit:
    """Full reduce→reduce→restore→reduce→restore cycle at ai_max=2.

    Kills clusters #6 (mutmut_12/20: max(2,...) floor skips the reduction),
    #7 (mutmut_26: <=→< desyncs _current_permit_count → restore releases nothing),
    #18 (restore mutmut_9: <=1 skips the single-permit release),
    #19 (restore mutmut_11: _current_permit_count=None deadens the next reduce).
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize("level_name", ["WARNING", "CRITICAL"])
    async def test_single_permit_throttle_cycle_restores_and_reapplies(
        self, mock_settings, level_name: str
    ) -> None:
        from backend.services.gpu_monitor import MemoryPressureLevel

        level = MemoryPressureLevel[level_name]
        mock_settings.return_value.ai_max_concurrent_inferences = 2
        semaphore = get_inference_semaphore()

        # 2 -> 1 permit: the reduction floor must allow 1, never clamp up to 2.
        await reduce_permits_for_memory_pressure(level)
        assert semaphore._value == 1

        # Idempotent re-application at the target must not corrupt tracked state.
        await reduce_permits_for_memory_pressure(level)
        assert semaphore._value == 1

        # Relief must give the single held permit back (kills the <=1 skip and
        # the desynced-count no-restore).
        await restore_permits_after_pressure()
        assert semaphore._value == 2

        # Throttling must still WORK after a restore cycle (kills the
        # _current_permit_count=None silent no-op).
        await reduce_permits_for_memory_pressure(level)
        assert semaphore._value == 1

        await restore_permits_after_pressure()
        assert semaphore._value == 2


class TestPartialUtilizationReduction:
    """Kills cluster #9 (reduce mutmut_45: `_value > 1` skips the last free permit)."""

    @pytest.mark.asyncio
    async def test_reduce_acquires_from_partially_utilized_semaphore(self, mock_settings) -> None:
        from backend.services.gpu_monitor import MemoryPressureLevel

        mock_settings.return_value.ai_max_concurrent_inferences = 4
        semaphore = get_inference_semaphore()
        # Leave exactly one free permit: the `_value == 1` boundary.
        await semaphore.acquire()
        await semaphore.acquire()
        await semaphore.acquire()
        assert semaphore._value == 1

        # WARNING target is 75% of 4 = 3 permits -> the one free permit must be taken.
        await reduce_permits_for_memory_pressure(MemoryPressureLevel.WARNING)
        assert semaphore._value == 0


class TestThrottleFlagShortCircuits:
    """_throttled_for_pressure bookkeeping via a get_inference_semaphore spy.

    Kills cluster #15 (reset mutmut_5: flag survives reset → restore constructs
    the singleton) and #21 (restore mutmut_13: flag survives restore → redundant
    restore hits the semaphore).
    """

    @pytest.mark.asyncio
    async def test_restore_short_circuits_after_reset(self) -> None:
        # reset_inference_semaphore() must clear _throttled_for_pressure so that
        # restore() never initializes the singleton.
        with patch("backend.services.inference_semaphore.get_inference_semaphore") as mock_get:
            await restore_permits_after_pressure()
        mock_get.assert_not_called()

    @pytest.mark.asyncio
    async def test_second_restore_after_full_restore_is_noop(self, mock_settings) -> None:
        from backend.services.gpu_monitor import MemoryPressureLevel

        mock_settings.return_value.ai_max_concurrent_inferences = 4
        semaphore = get_inference_semaphore()
        await reduce_permits_for_memory_pressure(MemoryPressureLevel.CRITICAL)
        await restore_permits_after_pressure()
        assert semaphore._value == 4

        # A redundant restore must short-circuit on the flag, not touch the semaphore.
        with patch("backend.services.inference_semaphore.get_inference_semaphore") as mock_get:
            await restore_permits_after_pressure()
        mock_get.assert_not_called()
        assert semaphore._value == 4
```

**Coverage of TEST-GAP clusters**: T1 → #4 (4 mutants); T2 → #6, #7, #18, #19 (5); T3 → #9 (1); T4 → #15, #21 (2). **12/12 TEST-GAP mutants addressed.**

## Draft verification notes (manual kill-trace, no execution)

- T2/WARNING mutant-20: `int(2*0.75)=1→max(2,1)=2` → `to_remove=0` → early return → `_value==2` ≠ 1 → **red**. Original: `_value==1` green.
- T2/CRITICAL mutant-12: `2//2=1→max(2,1)=2` → same skip → **red** at first assert.
- T2 mutant-26 (`<0`): 2nd reduce recomputes `current = 2 − 0 = 2` → restore `to_restore=0` → `_value` stuck at 1 → **red** at restore assert.
- T2 restore-mutmut_9 (`<=1`): `to_restore=1` → skipped release → **red** at restore assert.
- T2 restore-mutmut_11 (`current=None`): second reduce hits None-guard → no-op → **red** at second reduce assert.
- T3 mutant-45: `_value==1` fails `>1` → free permit kept → **red** (`_value==1`).
- T4 reset-mutmut_5: flag True survives reset → `get_inference_semaphore` (mock) called → **red**. NOTE: T4a relies on the autouse `reset_semaphore` fixture ordering (fires before `mock_settings`, module starts fully clean) — the mutant path returns at the None-guard so no settings access occurs; no `mock_settings` fixture needed.
- T4b restore-mutmut_13: redundant restore calls the spied getter → **red**.
- T1: mutant-7 `return sys._is_gil_enabled()` inverts both present-attribute asserts; mutmut_1/5/6 fail `test_gil_disabled_python_is_free_threaded`.

## Why existing tests are weak (for the ledger)

1. All throttling math is asserted only at ai_max ∈ {1, 2-fully-exhausted, 4, 8} — exactly the points where `max(1,x)`/`max(2,x)`, `<=0`/`<0`, `<=1` boundaries agree or the guard is inert.
2. `test_concurrent_pressure_changes` / `test_reduce_permits_without_initialization` / `test_restore_permits_without_initialization` are no-exception smoke tests with zero state assertions.
3. `test_memory_pressure.py::TestInferenceSemaphoreThrottling` uses loose inequalities AND unpatched real settings (brittle to config default changes; a side-finding, not a mutant).
4. Throttle-flag bookkeeping (`_throttled_for_pressure`) has no direct or spy-based assertion anywhere.
