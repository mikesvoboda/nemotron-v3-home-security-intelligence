# HANDOFF — sandbox migration during run5 (WP4.3) — 2026-09-17

Written 17:45 UTC from sandbox `agent-nemo2` (16 CPU / 94GiB), while run5 —
the first honest mutation baseline — is mid-flight (~27% and climbing).
You are a fresh session in a NEW, resized sandbox. The old sandbox is gone or
about to be; everything this doc depends on is either in git, in the mounted
tree, or listed as a loss below.

**Order of operations for the new session:**

1. Boot-verify the new box (§1).
2. Restart run5 at the new size (§2) — start it FIRST, it's the long pole.
3. Arm the close-out watcher, then let the WP4.3 close-out commit happen (§3).
4. WP4.4 verification lane from the triage queue (§4); keep drafting waves during long tiers (§5).

---

## 0. What was achieved before the migration (state you inherit)

- **WP4.3 WIP checkpoint is PUSHED**: `feat/phase3` @ `99829f9c` on origin —
  all 11 WP4.3 files (mutation-run.sh, mutation-score.py, test_mutation_score.py,
  workflow, pyproject [tool.mutmut], test_websocket.py, docs, .gitignore,
  stryker header, ci.yml). Verified by credentialed `ls-remote`. The branch
  was auto-rebased onto main (which contains #6551) and force-with-lease
  pushed; all pre-commit + pre-push fast-tier gates passed on it.
- **run5** (`uv run mutmut run --max-children 12`, started ~11:34 UTC, log
  /tmp/wp25/mutation-run5.log in the OLD sandbox — the log itself dies with
  the box): denominator 88,329 mutants over 269 files (backend/services/ +
  backend/api/routes/); at 24,206 checked (27.4%): 🎉13,808 killed, ⏰471
  timeout, 🙁9,907 survived. **Verdicts survive** — per-mutant `.py.meta` +
  the 269-file meta files and the stats cache live under `mutants/` IN THE
  MOUNTED TREE (§2).
- **WP4.4 triage program**: 38 modules dispatched (36 + gpu_monitor +
  insight_generator in flight as wave 9), ~4,900 survivors classified
  TEST-GAP ~67% / EQUIVALENT ~22% / LOW-VALUE ~10%, ~220 drafted UNVERIFIED
  kill-tests + 8 cross-module fix patterns. All in `.wp25-feed/` (§5).
- The mutation pipeline was found DEAD pre-WP4.3 (mutmut 3 rejects the 2.x
  flags every call site used; `|| true` shielded it for months) — full story
  in the WIP commit message `99829f9c` and `.wp25-feed/commit-wp43.txt`.

## 1. Boot verification in the new sandbox (do before trusting anything)

**THE mount check comes before everything else.** The 24k+ verdicts, the
stats cache, and this feed live in the HOST working tree mounted at
`/agents/agent-nemo2/workspace` (direct mode). A new sandbox must mount the
SAME host directory — if the new sandbox's workspace is a fresh clone (no
`mutants/` dir, no `.wp25-feed/` here), STOP: the verdicts are still on the
old host path (find it from the host: `ls /agents/*/workspace/mutants`);
re-mount or copy before restarting the run. Restarting generation on a cold
tree throws away 5+ hours of checked mutants.

```bash
test -f mutants/mutmut-stats.json && find mutants -name '*.py.meta' | wc -l  # expect 269 meta FILES
ls .wp25-feed/HANDOFF-WP43.md                                                # this file, present = right tree
nproc                          # resize arbiter — if still 16, the resize didn't land
free -g                        # target was "more CPU AND memory"
ss -ltn | grep -E '5432|6379'  # Postgres 16 + Redis are HOST processes, not containers
uv run python -c "import asyncpg" # then a real connect to $TEST_DATABASE_URL
test -f /etc/sandbox-persistent.sh && grep TEST_ /etc/sandbox-persistent.sh
```

Known recreate casualties (from memory `sandbox-recreate-vs-reboot`, verified twice):

- `/etc/sandbox-persistent.sh` comes up EMPTY → re-append the exports from
  `.wp25-feed/sandbox-persistent-exports.txt` (TEST_DATABASE_URL /
  TEST_REDIS_URL / REDIS_URL).
- **Containers NEVER work here** (`/dev/fuse` + `/dev/net/tun` absent →
  podman/docker die). Postgres/redis must be restored as HOST processes if
  dead; check before suspecting the tree.
- `apt` libs may be missing: `sudo -n apt-get install -y libgl1 libglib2.0-0`
  if `import cv2` fails (memory of a 1,908-failed gate run caused exactly by this).
- **`.venv`**: if the new sandbox rebuilt it, `uv sync` has run → it prunes
  `pre-commit` (declared in neither pyproject nor uv.lock) →
  `uv pip install pre-commit` BEFORE any `git commit`, or hooks die with
  `No module named pre_commit` (memory `uv-sync-prunes-manual-venv-packages`).
- Git push auth: the sandbox proxy's credential injection is often inert even
  with a valid token. Diagnose `curl -H "Authorization: token $GH_TOKEN"
https://api.github.com/user` → 200, then push with the one-shot helper:
  `GIT_TERMINAL_PROMPT=0 git -c credential.helper="!f() { echo username=x-access-token; echo \"password=\$GH_TOKEN\"; }; f" push -u origin feat/phase3`
  (memory `github-push-one-shot-helper`). Never `--no-verify`, never `SKIP=`.
- The repo's pre-push `auto-rebase` hook rebases onto origin/main; if the
  push is then rejected non-fast-forward, verify remote-unique commits are
  patch-equivalent (`git cherry origin/feat/phase3 feat/phase3`) and push
  `--force-with-lease`. That sequence is what landed `99829f9c` today.

## 2. Restart run5 at the new size (THE long pole — do first)

run5's PID belonged to the old sandbox; assume it's dead. Nothing was lost
except at most ~12 in-flight mutants: mutmut saves every checked mutant's
verdict immediately (`_register_mutant_result`, mutmut/**main**.py:920) into
`mutants/**/*.py.meta` + carries the stats cache `mutants/mutmut-stats.json`
— all on the mounted tree, 1.4 GB total.

**Ordering rule:** the old run must be DEAD before this run starts — two
mutmut processes writing the same `mutants/` cache corrupts verdicts (and
they'd fight over CPU anyway). The old session's plan was: keep run5 alive
until the new sandbox boots and mount-checks green, then tear down the old
sandbox (that kills run5), then start run6 here. If you find stale `[m]utmut`
processes that somehow survived, kill by PID (never `pkill -f` — self-match
trap, memory `pkill-self-match-trap`).

```bash
cd /agents/agent-nemo2/workspace
ps -eo pid,args | grep '[m]utmut'   # any survivor of the old box? kill by PID
                                     # (bracketed pattern — plain pkill -f hits itself)
N=$(nproc); M=$((N-4))               # honesty brake below; e.g. 64 -> 60
MUTMAX=$M nohup ./scripts/mutation-run.sh > /tmp/wp25-run6.log 2>&1 &
echo $! > /tmp/wp25-run6.pid
```

What the restart does: re-generates mutant copies (~19 min for 269 files —
measured, no test execution), hash-merges, **keeps every existing verdict**,
and resumes at the first unchecked mutant. Expect the checked counter to jump
back to ~24k within the first minutes; from then on it climbs at the new rate.

**Why `nproc - 4`, never `= nproc`:** mutants are judged by wall-clock
`--timeout=120`, and **timeout counts as KILLED**. Saturating the box makes
legitimate-but-slow mutants fake-timeout and silently INFLATES the baseline.
The 16-CPU box ran 12 workers at ~99% each for exactly this reason.

Expected speedup is near-linear (boot-bound: every mutant pays a fresh ~8.5 s
pytest boot; 1.15 GB RSS/worker, fine to ~48 workers if RAM came along). At
64 visible CPUs (`MUTMAX=60`): remaining ~64k mutants ≈ 3.5–4 h. Recompute
with `uv run python scripts/.eta.py` (repo copy, runs from anywhere) once
~500 new mutants have landed. **Standing rule from the owner: every status
update must carry % complete + ETA.**

Close-out watcher (session survives, restart it if this session dies):

```bash
RUNPID=$(pgrep -f 'mutmut run --max-children' | head -1)
while kill -0 "$RUNPID" 2>/dev/null; do sleep 60; done
tr '\r' '\n' < /tmp/wp25-run6.log | tail -25   # final counters
```

## 3. WP4.3 close-out commit (when the run exits, or is stopped for the day)

One heavy pytest tier at a time — run this only after mutmut exits.

1. `uv run python scripts/mutation-score.py` → full JSON (per-module scores,
   totals, progress{checked,total,not_checked,torn_metas,completed}). This is
   the FIRST honest baseline number. If the run was interrupted again, the
   scorer still scores the partial cache (pessimistic by construction;
   `completed=false`).
2. Fill `<BASELINE>` in `.wp25-feed/ledger-wp43-draft.md` and
   `.wp25-feed/commit-wp43.txt`; touch the WP4.4-feed numbers to the final
   triage state (`wc -l .wp25-feed/triage-waves/dispatched.txt`, dossier
   count, drafts = sum of `drafted_tests` in
   `.wp25-feed/wp44-triage/final_clusters.json` journals — see the queue
   index's aggregate line for the format).
3. Re-sync the feed: `cp -r /tmp/wp25/wp44-triage/. .wp25-feed/wp44-triage/`
   and refresh `wp44-queue-index.md` (workflow journals regenerate it —
   recipe at the bottom of the index's session notes / ask the queue).
4. `./scripts/validate.sh` (full — the box is free; ~40 min; needs pg/redis
   live and pre-commit installed).
5. Append the ledger draft into `L=docs/plans/2026-09-12-context-map-doc-updates.md`
   (L's row format), prettier fixed-point (backtick bare markdown tokens —
   memory `wp25-resume-pack-2026-09-16` root-cause note).
6. `git add` the L + any final doc touch-ups + `.wp25-feed/` (decide: commit
   the feed into the repo under docs, or delete after close-out) → ONE commit
   using `.wp25-feed/commit-wp43.txt` → push via §1's credential path → watch
   CI (`gh pr checks` has no `--json` here — plain output).
   The WIP commit `99829f9c` + close-out commit together are WP4.3 —
   close-out carries the baseline story; the squashed PR body can say so.

## 4. WP4.4 — verification lane (owner-approved doctrine)

Queue: `.wp25-feed/wp44-queue-index.md` — modules ordered by TEST-GAP
survivors desc, cluster tables per module in `.wp25-feed/wp44-triage/`, 8
cross-module patterns worth starting with, and the lane rules:

- A drafted test enters the tree ONLY red-on-mutant-diff → green-on-original →
  killed. ONE serial pytest lane at a time (this is the tier — nothing else
  heavy while it runs). `UNVERIFIED` is not a status that survives contact with git.
- EQUIVALENT claims get one-input spot-checks before being accepted as
  "do not chase"; LOW-VALUE stays recorded (no deletion without record —
  PLAN's WP4.4 rule).
- The final-score gap: ~145+ modules never crossed the triage bar during
  run5; re-run the triage waves against the FINAL score JSON (§5).
- WP4.4 = its own commit (then 4.5: the five coverage omits).

## 5. Drafting waves during long tiers (parallel; read-only)

Doctrine (memory `parallel-triage-serial-verify`): drafting agents are
READ-ONLY (dossiers + drafts to /tmp, marked UNVERIFIED); fixes enter the
tree only through §4's serial lane. Dispatch gate: module ≥150 checked AND
≥100 survivors (survivors never flip once checked).

```bash
uv run python scripts/.new-stable.py   # prints + ledger-appends newly-stable modules
                                       # (tree ledger is now canonical: .wp25-feed/triage-waves/dispatched.txt)
```

Then dispatch the saved workflow (copy in `.wp25-feed/wp44-triage-workflow.js`;
canonical path
`~/.claude/projects/-agents-agent-nemo2-workspace/79a1f342-0c47-43c3-bc69-b513f06e89fc/workflows/scripts/wp44-survivor-triage-wf_2bf3f33f-29f.js`
— **if that project dir died with the old session, the copy is inside
`.wp25-feed/`**; it takes `args: {modules: [...]}`, one agent per module,
dossiers to /tmp/wp25/wp44-triage/<name>.md — sync into `.wp25-feed/` after
each wave, /tmp is volatile).

## 6. Where everything lives

| What                                                              | Where                                                                                                                                              | Survived migration?                               |
| ----------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| WP4.3 code (11 files)                                             | git `feat/phase3` @ `99829f9c` (pushed)                                                                                                            | ✅                                                |
| run5 verdicts (24k+) + stats cache + 1.4 GB mutant tree           | `mutants/` in the mounted workspace (gitignored)                                                                                                   | ✅                                                |
| WP4.3 close-out drafts (`<BASELINE>` open), ledger text           | `.wp25-feed/{commit-wp43.txt, ledger-wp43-draft.md}`                                                                                               | ✅                                                |
| WP4.4 queue index + 38 dossiers + dispatch ledger + wave workflow | `.wp25-feed/`                                                                                                                                      | ✅                                                |
| ETA/detector scripts                                              | `scripts/.eta.py`, `scripts/.new-stable.py` (dot-prefixed: WIP, excluded from test-name gates; originals mirrored in `.wp25-feed/`)                | ✅                                                |
| Memory files (23)                                                 | `.wp25-feed/memory/` (also in the OLD sandbox's `~/.claude/projects/.../memory/` — copy back to the new sandbox's equivalent path so recall works) | ✅                                                |
| run5 stdout log                                                   | old `/tmp/wp25/mutation-run5.log` (tail copied to `.wp25-feed/run5-last-counters.txt`)                                                             | ❌ (counters only; verdicts are the truth anyway) |
| Old exit-watcher, triage cron, wave-9 workflow                    | old session                                                                                                                                        | ❌ rebuild: §2 watcher, §5 detector loop          |
| Goal prompt                                                       | `.wp25-feed/goal-prompt-phase3-closeout-2026-09-17.txt` (also `/home/agent/goal-prompt-test-platform-2026-09-16.txt` in old box)                   | ✅                                                |

## 7. Dead-on-arrival ideas (don't rediscover these)

- Running `validate.sh` or any heavy pytest tier **while mutmut is live** —
  collides on security_test_gwN and load can flip mutants to fake-timeouts
  (score inflation). The push fast-tier (~8 min) is the only sanctioned
  overlap and only for safety commits.
- "Fixing" Hypothesis `differing_executors` in test files — the fix is
  `[tool.mutmut] process_isolation="forkserver"` (already configured); tests
  are correct under single execution.
- Suppressing/quieting any gate to pass; lowering floors; widening quarantine.
- `mangle`-ing `--timeout` down to speed the run: boot (8.5 s) dominates, and
  shorter timeouts = inflated kills.
- Editing pyproject outside a WP's named files → STOP AND ASK first.
- Telling the user to push from their host terminal: sandbox pushes work via §1.
