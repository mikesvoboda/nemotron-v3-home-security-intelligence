# M2 Task 3 — §6.2 acceptance measurement plan (draft, NOT executed — box lease)

## Box reality (measured 2026-09-14, read-only)

- `/proc/meminfo` **MemTotal: 65,744,332 kB = 62.69 GiB** (free: 62 GB total, ~54 GB available).
- `nproc` = **16** cores.
- **The validate.sh auto-parallel gate is a `>= 67,108,864 kB` (64 GiB) MemTotal
  test. This box is 65,744,332 kB → BELOW the threshold by ~1.3 GiB.
  This box TRIPS the gate in the negative direction: validate.sh with the Task-3
  patch stays SERIAL here.** No banner, 8192 MB heap, byte-identical to today.
- Design-doc friction to flag in the PR/ledger: the spec's §1 baselines are
  labeled "GB300 dev box: 72 cores, 494 GB RAM", but the gate-10 run the task
  brief anchors on (`/tmp/validate-full-10.log`, Duration 2981.18s) was measured
  on THIS 16-core / 62.7 GiB box. The §6.2 "< 10 min on the GB300" target was
  written for a much fatter machine; on this box it is a stretch goal (§
  "plausible wall time" below). If the owner wants the auto-path here, the
  threshold knob belongs in a follow-up (e.g. 48 GiB) — Task 3's shipped
  threshold stays 64 GiB exactly as planned.

## Baseline (gate 10, serial forks) — from /tmp/validate-full-10.log

- **Vitest stage wall: 2981.18 s (~49.7 min)**, fileParallelism:false (one fork
  at a time), heap cap 8192 MB.
- Internal breakdown: `transform 23.89s, setup 350.85s, import 556.89s,
  tests 743.30s, environment 855.94s` — i.e. only 25% is test bodies; 75% is
  module import + jsdom environment + setup, all of which parallelizes across
  forks almost as well as test time. 781 test files executed, 20,340 tests,
  run red (18 failures + 2 error events) — duration is still reported on red,
  but the acceptance run must be green (see sequencing).

## Protocol (run only after the concurrent full-gate lease ends)

0. **Sequencing precondition:** the App.test/App.lazy NEM-5322 repair (ledger
   item 6, still OPEN) must land first, or "acceptance" runs green-on-a-red-
   tree. Wall-time numbers below can be taken on a red tree (duration prints
   anyway); the <10 min claim cannot.
1. **Control (serial, confirms patch inert):** `env -u VITEST_PARALLEL
   -u VITEST_MAX_WORKERS -u VITEST_HEAP_MB ./scripts/validate.sh --frontend`
   → expect NO "Parallel vitest" banner (box < 64 GiB) and a duration within
   noise of 2981 s. Also run the plan Step 3 check (`npx vitest related --run
   src/hooks/useAlertsQuery.ts` with a concurrent `ps` fork census ≤ 1).
2. **Manual-override parallel arm (this box's ONLY parallel route):**
   `VITEST_PARALLEL=1 VITEST_MAX_WORKERS=8 VITEST_HEAP_MB=8192
   ./scripts/validate.sh --frontend` (kill-switch semantics: explicit 0 wins;
   here we opt IN past the RAM gate manually). Recommended first arm at
   **heap 8192, workers 8** — see heap math in risk-notes.md: 9 processes ×
   16 GiB ceilings vs 62.7 GiB physical is not defensible until measured RSS
   proves otherwise; 8×8192 ceilings over ~16–32 GiB realistic is.
3. Second arm once RSS data exists: `VITEST_MAX_WORKERS=16
   VITEST_HEAP_MB=4096` (workers == nproc; 4 GiB ceiling × 17 ≈ 68 GiB ceiling,
   realistic far below) — only if arm 2's per-file isolation survives.
4. While each arm runs, sample worker memory every 5 s:
   `ps -eo pid,rss,comm,args | grep -i [v]itest` → peak per-worker RSS and
   peak summed RSS (record; this is the number that justifies or lowers the
   big-box heap default in the notes doc Task 15 owns).
5. **Saturation-shape re-prove (§6 row 2):** the previously-flaky 18-file set
   from gate 10 + §6's protocol, run under arm 2's env, green, AND each file
   green-alone afterward (green-alone equivalence must still hold — same test
   can't pass alone but fail in parallel).
6. Record both durations + RSS peaks in the `docs/development/` measurements
   doc (Task 15 owns the file; Task 3 just feeds numbers).

## Plausible wall time on THIS box (the honest forecast)

- Ideal Amdahl over the 2981 s total at 8 workers: 2981/8 ≈ **373 s**.
- Realistic on 16 cores with per-file fork spawn + jsdom + import contention,
  shared disk, one vite dep-optimizer/esbuild process: **~4–7× speedup ⇒
  ~7–12.5 min (420–750 s)**. At 16 workers with heap trimmed: **~5–8 min**
  if memory headroom holds (17 node procs).
- So §6.2's < 10 min is *plausible but not assured* here at 8 workers; it is
  comfortably met at 16 workers/4 GiB if the risk-note crash classes don't
  regress. A result in the 600–750 s band at 8 workers should be reported as a
  §3.3-class measurement, not silently re-baselined: the plan's own Step-4
  wording on "3–6×" was for the 72-core box; this box's core count caps it.
- CI (GitHub runners) remains untouched-by-default: no env ⇒ sequential + 8 GB,
  byte-identical (Task 4 opts CI in separately with measured values).
