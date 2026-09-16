# Selector evaluation: fast_select vs testmon (WP2.1)

**Status: COMPLETE — decision made (see DECIDE below).** Plan
`docs/superpowers/plans/2026-09-15-test-platform-improvement.md` WP2.1; spec
§Phase 2: "Pick one and delete or clearly demote the other… recorded with its
rationale." All numbers below come from the corrected derive backfill (raw
`.log` re-parse) and the frozen-truth rebench — NOT from the live driver lines,
which the v1 parser had poisoned (defect ledger item 1).

Two selectors competed for the fast tier's selection role:

- `scripts/fast_select.py` — static: dotted-reference truth from test-file
  text, extended (WP2.2) with the producer-graph closure.
- `pytest --testmon` 2.2.0 — dynamic: coverage-derived from a warmed
  `.testmondata` database, transitive by construction.

## Protocol (v3)

20 sampled commits touching `backend/*.py` (33-candidate sweep across
`feat/phase2` + `main` history, spread across the timeline). One detached git
worktree per commit, shared venv, execution strictly serial (repo rule).
Universe: `backend/tests/unit` (+ `contracts` where present at that HEAD),
`-n 8 --dist=worksteal -m 'not gpu' --timeout=90 -p no:randomly`. Both
selectors run AS OF TODAY against the sampled commit's own test corpus (the
honest retrospective pairing); fast_select's selection is tier-filtered to
unit+contracts and its out-of-tier count recorded.

### Ground truth, two arms

1. **Outcome-difference arm** — failures(`<sha>`) Δ failures(`<sha>^`): tests
   THIS commit changed the outcome of (broke or fixed). Honest to history, but
   undefined on commits that change no outcome (14/20 here — the deciding arm
   could not be this one).
2. **Injected-fault arm** — inject `raise AssertionError` into the first
   multi-line function of the first changed backend `.py`; truth = tests that
   fail faulted but not clean. A fault reaching nothing = INERT, recorded as
   such, excluded from recall. 12/20 injectable (`NO_PY_TARGET` = 8: the
   sampled commit had no eligible production `.py` — test-only or infra
   commits); 0 INERT among the 12 — every injected fault broke ≥1 test.

### Harness-defect ledger (found, fixed, backfilled — each one could have lied)

1. **v1 fails() parser**: tail-truncated node IDs before stripping the
   `FAILED` prefix, so every truth/affected/fs.fail/tm.fail artifact was the
   literal word `FAILED`. Live driver recall lines were wrong (most
   pessimistically: real fs 3/6 printed as 0/6). Fixed parser → `derive.sh`
   re-derived every artifact from the RAW logs (runs themselves were valid).
2. **comm -3 tab prefix**: the right column of `comm -3` is tab-led;
   downstream `cut -d: -f1` kept the tab, so `affected.files` joined nothing —
   FALSE 0/1 recall for BOTH selectors on case 09872e45 (both had selected
   the file). Fixed with `sed 's/^\t//'`.
3. **testmon db recycle**: worktree `.testmondata` could vanish between arms;
   harness db-guard re-warms and marks `warm_rerun` (0 occurrences in this
   run — guard never needed to fire).
4. **`-m` deactivation claim disproven**: testmon docs suggest marker
   filtering may skip selection; did not reproduce — `--testmon` selected
   normally under `-m 'not gpu'` in all 20 cases.

## Results (corrected; recall = files, frozen lists)

Outcome arm (truth = affected files; `-` = affected 0, undefined):

| case      | affected | shipped fs  | testmon      | closure (WP2.2) |
| --------- | -------- | ----------- | ------------ | --------------- |
| 096d38be  | 2        | 1/2         | 2/2          | **2/2**         |
| 09872e45  | 1        | 1/1         | 1/1          | **1/1**         |
| 42acc048  | 1        | 0/1         | 1/1          | **1/1**         |
| 8ea70057  | 6        | 3/6         | 5/6          | **6/6**         |
| a4507909  | 4        | 0/4         | 4/4          | **4/4**         |
| a743cd64  | 2        | 1/2         | 1/2          | **2/2**         |
| (14 more) | 0        | —           | —            | — (undefined)   |
| **total** | **15**   | **6 (40%)** | **14 (93%)** | **15 (100%)**   |

Fault arm (truth = files broken by the injected fault; 8 cases `NO_PY_TARGET`,
no injectable production file — recorded, not scored):

| case      | truth   | shipped fs   | testmon      | closure (WP2.2) |
| --------- | ------- | ------------ | ------------ | --------------- |
| 096d38be  | 3       | 3/3          | 3/3          | **3/3**         |
| 09872e45  | 3       | 3/3          | 3/3          | **3/3**         |
| 15d7b5a2  | 14      | 10/14        | 8/14         | **14/14**       |
| 3396d3ef  | 105     | 48/105       | 67/105       | **105/105**     |
| 6062d5d5  | 1       | 1/1          | 1/1          | **1/1**         |
| 813a2a66  | 2       | 2/2          | 2/2          | **2/2**         |
| 8861a6e4  | 1       | 1/1          | 1/1          | **1/1**         |
| 8ea70057  | 2       | 2/2          | 2/2          | **2/2**         |
| 978bb04c  | 1       | 1/1          | 1/1          | **1/1**         |
| a1c3c289  | 2       | 2/2          | 2/2          | **2/2**         |
| a4507909  | 1       | 1/1          | 1/1          | **1/1**         |
| a743cd64  | 1       | 1/1          | 1/1          | **1/1**         |
| **total** | **136** | **75 (55%)** | **92 (68%)** | **136 (100%)**  |

Closure column = `scripts/fast_select.py` at 697aa1a5, replayed against the
frozen truth lists (never re-derived post-fix — the lists predate it).

### Cost

| dimension                | fast_select (shipped/closure) | testmon                                                                                           |
| ------------------------ | ----------------------------- | ------------------------------------------------------------------------------------------------- |
| selection time           | 0–1s / 0–2s                   | 6–17s                                                                                             |
| selection run cost       | none (static)                 | full parent commit run to WARM the db: 82–114s typical, 165s outlier                              |
| stale-db behavior        | n/a                           | db miss = full-suite fallback (measured as run cost, e.g. 71–109s rows where selection was stale) |
| cold cost total per push | 0–2s                          | ~90–180s BEFORE selection even answers                                                            |

fast_select's over-selection was measured (fs_out_of_tier rows recorded per
case); the tier never under-runs and the selection cost stays seconds.

## DECIDE — keep fast_select (+WP2.2 closure); DEMOTE testmon to advisory

Evidence-based rationale (also in the ledger):

1. **Recall on the deciding arm is 100% vs 68%/55%** — the closure, which the
   bake-off itself justified building (WP2.2), dominates on both arms and
   every miss class (transitive intermediates, package re-exports,
   fixture-indirect conftest, changed-test identity, compose filename).
   testmon misses 44/136 fault files even WARM with full coverage data —
   transitive-by-construction does not mean complete-at-selection-time
   (stale-coverage gaps show exactly here).
2. **Cost is not close**: closure answers in 0–2s with no state; testmon's
   honest cold cost is a full parent run (82–165s) PLUS 6–17s selection.
   Pre-push budgets the closure fits trivially, testmon spends a third of a
   300s budget before the first test runs.
3. **Determinism/no-db-in-worktree**: closure output is a pure function of
   tree+diff (CI-reproducible, no `.testmondata` to warm, share, or go stale);
   testmon's correctness depends on db currency the repo cannot guarantee
   (worktrees, CI caching, `.gitignore`d).
4. **Why demote and not delete**: testmon remains the only tool measuring the
   COVERAGE-actual dependency (what a test really executed). That is exactly
   the auditor role for offline audit runs — cross-checking the static
   selector's blind classes and feeding this evaluation's future re-runs.
   The bake-off verdict (loser on both recall and cost for the gate role)
   says: out of the gate path, kept advisory with this file as its evidence
   dossier.

Per-case data: `/tmp/wp21/results/<sha>/` (raw logs + corrected artifacts +
`fs.meta`/`tm.meta`), roll-ups in `rebench.tsv`; protocol scripts
(`driver.sh`, `derive.sh`, `rebench.sh`) under `/tmp/wp21/` (sandbox-local;
the protocol's durable record is THIS file + the ledger rows).
