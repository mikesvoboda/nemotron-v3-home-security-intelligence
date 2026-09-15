# Ruling packet — M3 T5: pytest timeout config (P2, owner decision required)

Date: 2026-09-14. Asker: M3 execution (plan
`docs/superpowers/plans/2026-09-14-test-suite-hygiene-milestone3.md` Task 5).
Nothing below is applied — pyproject.toml and conftest.py change ONLY on an
approved ruling (M3 global constraint: pyproject via T5 owner ruling only).

## 1. The proposed diff (exact, to be applied only on approval)

```diff
--- a/pyproject.toml
+++ b/pyproject.toml
@@
 timeout = 5
-timeout_method = "thread"
-timeout_func_only = true  # Only timeout test functions, not fixture setup/teardown (prevents pytest-rerunfailures server thread from being killed)
+timeout_method = "signal"
+timeout_func_only = false
```

plus, in `backend/tests/conftest.py::_apply_timeout_marker`: honor a nonzero
CLI `--timeout` instead of stamping 5s over it — the marker-vs-CLI precedence
that made `validate.sh`'s `--timeout=30` a no-op (R-T7-TIMEOUT-GATE). That
retires the `/tmp/timeout_stamp_plugin.py` protocol workaround (M3 DoD).

## 2. Why each line

- **method signal, not thread.** [VERIFIED, audit Part 6 + this session's
  waves I/J/K] thread-method timeouts `os._exit(1)` the ENTIRE process:
  no summary, no `-rf`, xdist reports "node down: Not properly
  terminated". Every mystery hang this cycle (export J-6, mqtt J-7, wave
  I-5) ended that way — we could not even tell WHICH test hung until a
  name-printing plugin was added. signal interrupts only the test's own
  asyncio loop, pytest-timeout reports a normal failure, the session
  survives. signal cannot kill a wedged non-python await — that residual
  risk stays covered by the outer driver timeout.
- **func_only=false closes the setup-hole.** [VERIFIED run-9] the gw6
  media_api hang class: setup-phase awaits were untimed under
  func_only=true and consumed a worker silently (R-T7-TIMEOUT-GATE caught
  red-handed in the faulthandler dump).
- **rerunfailures interaction (the scar comment's claim).** The current
  scar comment says func_only=true "prevents the pytest-rerunfailures
  server thread from being killed." Provenance [VERIFIED via git]: the
  comment entered via unrelated squashed commit 07bd5657 — not a measured
  finding. Under signal there is no process-kill at all, so the claimed
  harm mechanism cannot occur. REMAINING CHECK (runs at T5 execution, not
  done yet): rerunfailures-active smoke with a synthetic timeout, proving
  rerun+signal compose cleanly. Until that smoke is green the packet is
  incomplete — do not approve on this document alone if the smoke has not
  run.

## 3. Blast radius (run-9 per-phase data, /tmp/test_durations.csv, 4303 rows)

| phase    | p50   | p90   | p99   | max  | sum    |
| -------- | ----- | ----- | ----- | ---- | ------ |
| setup    | 0.10s | 1.17s | 1.33s | 2.48 | 2179s  |
| call     | 0.01s | 0.07s | 1.53s | —    | 280s   |
| teardown | 1.14s | 2.13s | 2.42s | 2.86 | 4795s  |

func_only=false shares ONE budget across setup+call+teardown: per-test total
p99=4.16s, max=17.5s. Consequences at the proposed `timeout = 5`:

- 4 setups >2s (0.1%) — fine.
- p99 total 4.16s sits just under 5s; the 17.5s max and the >5s tail
  (~0.5% of tests, dominated by teardown 2.4s + slow calls) would start
  FAILING at the cap. T4's split collapses setup+teardown (6974s of the
  934s tier wall) — post-T4 these margins are expected to widen, but the
  rule needs T4's post-split numbers, which is exactly why **T4 gates T5**.

Decision rule (plan-mandated, re-checked post-T4): setup p99 ≪ 2s → keep
`timeout = 5` + `@pytest.mark.slow` on offenders; else `timeout = 10`.
(30s off the table — it reopens the silent-worker-eating window.)

## 4. What approval unlocks / what it costs if refused

Unlocks: honest timeouts that report failures instead of nuking sessions
(this cycle's 4 mystery hangs were 3 investigations and 0 summaries),
timed fixture setup, retirement of the /tmp stamp-plugin workaround, and
validate.sh's --timeout flag meaning what it says.
If refused: the stamp-plugin workaround stays a permanent protocol fixture
(outside the repo — every future session relearns it from the ledger), and
setup-hangs keep eating workers.

## 5. Approval mechanics

Reply on this doc: approve (as written) / approve with `timeout = 10` /
modify. Execution order on approval: conftest fix + stamp-plugin retirement
first (pure honesty fix, no marker change), then pyproject swap, then the
synthetic setup-hang harness (a scripts/ test proving a hang now fails
inside budget with NO node-down), then gate ×2 green zero node-downs — each
its own commit citing this packet.
