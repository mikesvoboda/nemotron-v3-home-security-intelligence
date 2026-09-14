# M2 Task 3 — risk notes (draft)

## R1. Gate-10's crash classes under parallelism: mask, worsen, or survive?

Gate 10 (`/tmp/validate-full-10.log`, serial forks, red tree) ended with
**2 "Unhandled Error" blocks** — 1 is `Worker forks emitted error / Worker
exited unexpectedly` (a fork-worker crash; the ledger's "+2 fork crashes" count
comes from the 20-file/18-test failure census, the log itself shows 1 visible
worker-exit block + the CleanupRow exception block), and 1 **Uncaught
Exception**: `ReferenceError: window is not defined` in
`@tremor/react Tooltip` `Timeout._onTimeout` → react-dom `dispatchSetState`,
attributed to `src/components/developer-tools/CleanupRow.test.tsx` — a timer
still live after that file's jsdom window was torn down. CleanupRow itself
PASSED (9 tests, 911 ms, log line 33215): the timer outlived the file.

- **isolate:true is preserved by the patch** (`pool: 'forks'` +
  `isolate: true` untouched) — every file gets a **fresh fork process**, so
  leaked timers/module state die with their process; parallelism does not
  create *cross-file* bleed (no thread-pool sharing — that's why `pool` is
  forks, and the comment block above it stays).
- **Does parallelism mask them?** Partially, and this is the honest caveat:
  the leaked-timer `window is not defined` fires when a stray timer lands
  *after* teardown — timing-sensitive. With 8 forks and CPU contention the
  post-teardown window widens (event-loop lag), so recurrence is at least as
  likely, not less; but because the fork is *reused for the next file* only
  when isolate recycles it — vitest 4 with `isolate: true` under forks
  recreates the environment per file while the process may be reused — a late
  timer can now also fire **while the next file is already executing in the
  same recycled process**, attributing the error to a *different* file. Ledger
  2007-2056 already predicts "crash candidates were probably the
  unhandled-rejection files above, not CleanupRow itself" (5 of 6 classes now
  fixed test-side on this branch) — the re-assessment must be done **after**
  the App.test/App.lazy item-6 fix lands, on a green-except-these tree, or
  attribution will be noise.
- **Does it worsen the fork-worker crashes?** The `emitUnexpectedExit` crash
  is a worker process dying (heap exhaustion or a segfault-class exit).
  Sequentially, exactly one heap-capped process runs, so an OOM needs a single
  file to blow ~8 GB. In parallel, **N heaps + main + esbuild** contend for
  physical RAM, and the kernel OOM-killer (or a worker's own V8 heap fatal)
  can kill a worker *whose own file was innocent*. That is a new failure mode
  parallelism *adds*, mitigated only by keeping workers×heap < MemTotal with
  margin (R2) — the whole reason this box auto-stays-serial under the 64 GiB
  gate and why the measurement plan arms start at 8×8192, not 8×16384.
- Acceptance wording (§6 row 2) demands **zero saturation-shaped failures** on
  the §6 protocol rerun of the previously-flaky 18-file set plus green-alone
  equivalence — a fork crash under parallel that passes alone is exactly the
  signature to watch for; if it appears, it's a §3.3-class finding for Task 3
  review (per the plan's Step 4), not noise to retry away.

## R2. Heap-per-worker math vs MemTotal (this box: 65,744,332 kB ≈ 62.7 GiB)

`--max-old-space-size` is **per Node process** (NODE_OPTIONS is inherited by
every fork). Ceiling arithmetic:

| Arm | Processes (workers + main) | Heap cap each | Sum of ceilings | vs 62.7 GiB MemTotal |
| --- | --- | --- | --- | --- |
| validate.sh auto on a ≥64 GB box | 8 + 1 | 16 GiB | **144 GiB** | fine only on the 494 GB box as specced; would swap-fuse a 64–96 GB machine — flag for the notes doc |
| 8 × 8192 (manual arm on THIS box) | 8 + 1 | 8 GiB | 72 GiB ceiling | over MemTotal as a *ceiling*; V8 only reserves lazily — realistic vitest/jsdom per-worker RSS in this suite looks ~1–3 GiB (gate 10 ran the same files under one process without OOM; measure RSS per measurement-plan step 4), so ~10–25 GiB realistic → fits |
| 16 × 4096 (headroom arm) | 16 + 1 | 4 GiB | 68 GiB ceiling | same shape; realistic ~20–40 GiB; 16 workers == nproc |
| nproc-derived 16 × 16384 | 17 | 16 GiB | 272 GiB | **never on this box** |

The ceiling exceeding MemTotal is survivable-but-fragile: OOM risk is a
function of *summed actual RSS*, not ceilings — which is why the plan measures
RSS before endorsing any auto-raise, and why on THIS box the safe posture is
what validate.sh already does (serial, single 8 GiB process) unless manually
overridden. Also: MemAvailable (63.2 GB now) will be materially lower during
the concurrently-running full gate — never launch the parallel arms while the
lease is held.

## R3. isolate:true keeps per-file state isolation

Unchanged by the patch: `pool:'forks'` + `isolate:true` (vite.config.ts:386,
hunk keeps it as context). Per-file process/environment recycling is the
backstop that makes file-parallelism *safe-by-construction* for this suite's
known cross-file hazards (module-global GET-dedup map, dual setupServer
interference, fake-timer leaks — all documented R-T7-VITEST knowledge in the
ledger). Parallelism changes *scheduling*, not *isolation*; that's the
difference between this and a threads-pool change, which would not be safe.

## R4. R-T7-VITEST 16-file quarantine must stay untouched

The `exclude` array at vite.config.ts:357–377 (16 quarantined entries incl. 3
zero-byte files) is owned by M2 test-repair work. The t3.patch hunk starts at
line 378 (context `// Fork-based parallelization...`) and **does not modify
the array or its comment block**; verify with
`git diff --stat` (3 files, 0 lines inside :337–377) on every rebase. If a
parallel run makes a quarantined file relevant again, that's ledger-driven
un-quarantine in a separate commit, never smuggled through Task 3.

## R5. Minor / accepted

- `fileParallelism:false` already forces maxWorkers to 1 internally (vitest 4
  type doc), so the new `maxWorkers` line is provably inert when off.
- `/proc/meminfo` absence (macOS) → `MEM_KB=0` → sequential: fails safe.
- `${VITEST_HEAP_MB:-8192}` in package.json is evaluated by npm's `sh -c`:
  portable POSIX; single→double quote change keeps the expanded string
  identical when unset.
- `test:ui` left with literal 8192 per plan scope (dev-only path).
- Plan snippet's `minWorkers: 1` dropped: removed option in vitest 4.0.18
  (zero hits in its dist); see apply-notes.md deviation 1.
