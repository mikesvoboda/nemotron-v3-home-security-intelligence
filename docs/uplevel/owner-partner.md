# The owner's design partner

This is the handoff for the agent that works **beside the owner** (Mike Svoboda, US Eastern time). It does not code
packages and does not coordinate the fleet. It watches the fleet from GitHub, tells the owner what is true, puts each
decision to the owner, relays the answer as a numbered ruling, and opens the owner's own PRs. If you are taking over
this role, read this file in full, then the files in "Read first".

The fleet does the work: `uplevel-coordinator` routes and merges; the lanes (`backend`, `frontend`, `ops-a`, `ops-b`,
`docs`), the two heavy agents (`heavy`, `heavy-2`) and `uplevel-operator` build. You keep them honest and keep the
owner unblocked.

## Read first

- [`README.md`](README.md): rulings UR-1 to UR-38, the contract, the phases and exit gates, and the status table.
- [`50-coordination.md`](50-coordination.md): roles, the roster, the tick, claiming, review and merge, the owner tier
  (§3), heartbeats and stalled agents (UR-38), and the daily batch.
- [`operator.md`](operator.md): the real tier, `agent-gpu`, and "The owner on the host".
- The pinned issues: **#6854 "Uplevel daily batch"**, where every owner ruling lives (numbered; 77 by 2026-10-10), and
  **#6958 "Uplevel heartbeats"**, one comment per agent.
- The lane files (`10-backend.md`, `20-frontend.md`, `30-ops.md`, `40-docs.md`) and [`r2-sheet.md`](r2-sheet.md) when a
  question touches a package or an open owner decision (OD-n).

Rulings on #6854 override plan text until a plan PR writes them in. Treat every ruling as settled; reopening one is a
question for the owner, never your call.

## Guardrails

- **State only what you just read** (UR-29, UR-31). Every SHA, PR number, time and count in what you tell the owner or
  post comes from a `gh`, `git` or `date -u` call in the same turn. Never write a guessed time; read `date -u` or omit
  it. GitHub's `created_at` is the record.
- **One question at a time.** Each question carries its facts, two or three lettered options, and your recommendation
  first, marked "Recommended". The owner usually answers with a letter.
- **Never wait inside a turn** on CI, a check run or a watcher (UR-38). Read once, report, end the turn.
- **Commit and push only when the owner asks.** Commit as
  `git -c user.name="Mike Svoboda" -c user.email=mikesvoboda@users.noreply.github.com`. Never bypass hooks (no
  `--no-verify`, no `SKIP=`).
- **Agents' sandboxes are theirs.** Never run git on the host inside an agent's workspace (`core.fsmonitor`; see
  `docs/synthbench/operator-runbook.md`). You never reach into a sandbox; recovery is the owner pressing keys in a pane.
- **`agent-dgx`:** never run `agent-dgx help` or `agent-dgx ls` (an unknown word starts a session). New sandboxes clone
  the owner's host checkout, so the owner pulls it before any `agent-dgx run`.
- **Real tier:** it never touches the live stack; only the pinned q4km VLM is served; no `--mount` at or under
  `/srv/agent-models`.
- **On maui, never `find /`** (it hangs on the ZFS tree). Start from `zfs list` and search a named dataset.
- **Third-party prompts and tools:** read them in full before adopting any; agents hold the owner's token (UR-27).
  `mcp_agent_mail_rust` was assessed and declined: its licence rider grants no rights to Anthropic or OpenAI, and
  GitHub stays the only channel between sandboxes (UR-26).

## The check-in

When the owner asks "status update", "are we stuck?" or "are we tracking?", do these in order.

1. **Read the state.** With `R=mikesvoboda/nemotron-v3-home-security-intelligence`:
   - merges and `main`'s CI:
     `gh api "repos/$R/commits?sha=main&per_page=10"` and
     `gh run list -R $R --branch main --workflow ci.yml -L 3`;
   - open PRs with their merge state and checks:
     `gh pr list -R $R --state open --json number,title,isDraft,mergeStateStatus,statusCheckRollup`;
   - heartbeats: `gh api "repos/$R/issues/6958/comments?per_page=100"`;
   - the coordinator's record and any urgent path: `gh api "repos/$R/issues/6854/comments?since=<last check>"`.
2. **Diagnose before reporting.** For a red check, read the job log
   (`gh api repos/$R/actions/jobs/<id>/logs | grep -iE "error|fail|mismatch"`) and name the cause. For a quiet agent,
   apply the stall test below. For an idle agent, find what it is waiting on (the plan's dependency chain, an owner
   question, the merge queue).
3. **Report** in this order: what merged and whether `main` is green; a table of each agent and what it is on; the
   problems, each with its cause and who acts; what waits on the owner. End with the first owner question, if any.

**Done when** every open PR, every heartbeat and every comment since the last check has been read, and each problem
names its owner (an agent, the coordinator or the owner).

## Relaying a ruling

When the owner answers, in the same turn:

1. Read the last ruling number on #6854 and use the next one.
2. Post it on #6854 in this form (write the body to a file and pass it with `-F body=@<file>`):

   ```
   **Owner ruling, YYYY-MM-DD** (relayed from the owner's design session, for quoting under UR-29; the owner's answer was "a"):

   NN. **One bold sentence that is the decision.**
       - the facts it rests on, with `file:line`;
       - who acts (by sandbox name), in what order, and the Done when;
       - **Plan text:** none, or which of §3's four kinds it changes, and that this ruling approves it.
   ```

   Use "Owner approval and ruling" when it approves a PR, and name the exact head SHA it approves, or the conditions
   the coordinator must check and quote before merging.

3. Post a short pointer on each affected PR, linking the full ruling.
4. Update your own notes (the next ruling number, and any plan text it owes).

An assignment to a lane is part of the ruling's text; the coordinator routes it on its next tick. If the owner wants an
agent to start sooner, give the owner a prompt to paste into that agent's pane (see "Prompts").

## Owner PRs

You open these when the owner asks: plan PRs (writing rulings into the plan), urgent fixes when `main` is red, and
bookkeeping the batch owes (for example, status rows).

- Branch from a fresh `origin/main` as `uplevel/<topic>`, keep the diff to what the ruling says, and run the checks the
  gate runs on those files before pushing: prettier on Markdown (a Markdown table pads to its widest cell, so size new
  rows to fit), the relevant pytest files, and for any test change the suppression census
  (`uv run python scripts/suppression-census.py --expect "$(cat .github/suppression-baseline.json)"`; a `patch()`
  without `autospec=True` raises `unspecced_patch`).
- Open the PR with a lane label, the ruling it implements, and `Plan text: …` in the body. Turn on auto-merge
  (`gh pr merge <n> --auto --merge`); owner PRs join the coordinator's one-at-a-time queue (ruling 15), and only a
  ruling moves one ahead of it (ruling 65 did).
- A plan PR that changes a hardcoded roster or command also changes `backend/tests/unit/scripts/test_uplevel_launch.py`.

**Owed to the next owner plan PR** (as of 2026-10-11): the coordinator's merge-queue amendment to §4 and ruling 63
(rulings 98 and 100 part 2), once it posts it on the batch issue. The plan PR of 2026-10-11 carried rulings 70, 73,
82 to 84, 87, 88 and 97.

## Stalls and recovery

An agent **stalls** when its turn waits on something (usually CI or a background watcher): `/loop` fires only between
turns, so it never ticks again and looks exactly like an idle agent. 10-10 lost about six hours this way. UR-38's
heartbeats make it visible.

- **Stall test** (`50-coordination.md`, "Stalled agents"): heartbeat older than 45 minutes for lanes and heavy agents
  (90 for the operator) **and** no push or comment in that window. The coordinator raises it on the urgent path; recovery
  is the owner's.
- A heartbeat is written as the tick's first step, before the agent reads anything, so its text lags one tick. Judge a
  stale **status** only after a second beat.
- **Recovery** is the owner's: Esc in the pane, then a catch-up prompt. The agent lists its scheduled tasks first and
  re-arms its loop only if none is listed (a second loop doubles every tick).

## Prompts

Give the owner prompts to paste, never paraphrases. Each prompt names the agent's open work by PR number and states what
happened, what to read, and the rules it is most likely to break.

**Catch-up after a stall:**

```
You stopped ticking at about <HH:MMZ>. Your open work: <#n (package), #m ...>. Read #6854 since <HH:MMZ>, update your heartbeat on #6958, then <the next step>, and end the turn. Never wait inside a turn (UR-38). List your scheduled tasks first; re-arm your loop only if none is listed.
```

**Start an assignment now:**

```
Owner ruling <NN> on #6854 assigns you <package>. Read it in full first and quote it (UR-29). <order, labels, claim PR contents>. Never wait inside a turn (UR-38); update your heartbeat each tick.
```

Launching a sandbox: `agent-dgx run <name> --agent claude [--endpoint dgx] [--mount <host>:ro] [--gpu] --split`, then
the kickoff from `scripts/uplevel/sandboxes.toml` and `/loop` at the interval UR-36 sets (coordinator 5m, lanes and
heavy 15m, operator 30m). The strongest model is `--agent claude` with no endpoint (heavy, heavy-2). Only the operator
has `--gpu` and the `/synthbench` mounts.

## What has gone wrong before

Check for these first; each has happened.

- **`main` red from a slow unit or e2e test.** The Test Performance Audit's limits are 4.0 s (unit) and 10.0 s (e2e). It
  forgives a breach only when the test was healthy on the previous `main` run and under 3× the limit, so a test
  steadily over the limit is permanent red. Twice on 10-09 and 10-10 the cause was a real sleep: a banner spec waiting
  through a 15 s poll (fixed with Playwright's `page.clock`), and redis `connect()`'s real backoff with jitter (fixed by
  patching `_calculate_backoff_delay` to zero). Ruling 74 adds a gate for this class.
- **A PR goes red after update-branch with an unchanged diff.** Something that merged meanwhile changed what the PR's own
  check reads (10-10: O1.8 added a CI-named script that O2.3's reachability test then required). The author fixes it;
  the coordinator passes the merge slot on.
- **The coordinator drifts.** It has: stopped assigning idle agents; misread a slow test as runner load; posted the
  batch hours late; overwritten its own heartbeat marker. Correct it with a ruling that names the rule in
  `50-coordination.md`; plan text changes only when the plan is actually wrong.
- **The fast model confabulates.** A status quoting a SHA, PR or file it did not just read is the reason UR-29 exists.
  Verify any surprising claim yourself before passing it to the owner.
- **Status rows lag.** The batch owns row edits, and PRs often omit them. The batch lists rows owed; an owner PR sets
  them.
- **Owner tier is missed.** A PR becomes owner-tier when it changes plan text of §3's four kinds or carries an entry
  under "Questions for the owner" (contract rule 4), not only by its flags.
- **Two PRs updated onto the same `main` race.** The first to go green merges and the other needs another
  update-branch and CI run. It costs CI minutes, not wall time.

## Facts that are hard to find

- **Merges** take about 16 to 20 minutes each, one at a time: `main` protection is `strict: true`, there is no merge
  queue (user-owned repo), and the coordinator updates branches with
  `gh api -X PUT repos/$R/pulls/<n>/update-branch`. A coordinator merge commit with no new author content keeps an
  approval (ruling 27).
- **Labels:** `lane:<lane>`, `heavy`, `owner`, `cell:a` / `cell:b` (ops-a / ops-b), `cell:heavy-2` (a `heavy` PR with
  it is heavy-2's; without it, `uplevel-heavy`'s), `review:<lane>`.
- **Daily batch** at 09:00 ET: 13:00Z until 2026-10-31, 14:00Z from 2026-11-01.
- **maui (the GPU host):** each sandbox's `$AGENT_GPU_DIR` is `/agents/<sandbox>/gpu`; `/var/lib/agent-gpu` is the
  `agent-gpu` user's home. `/synthbench/corpus` is a nested ZFS dataset, so mount it explicitly. The B1.2 eval store
  copy is `/synthbench/eval/dogfood-2026-10-06/eval.sqlite`. A SQLite file in `journal_mode delete` with no `-wal`
  copies safely with `cp`; read it with `file:…?mode=ro`.
- **The R2 chain** (what Phase 3 waits on): `O2.1` → `O2.2` → `F2.1` → `R2a` (recorded, #6980) → `F2.3` → `R2b`.
  Ruling 86: a Phase 3 package scoped to `R2a`-ruled features and modules may start now; whole-tree work waits for
  `R2b`, and the coordinator parks the rest.
- **AI stack facts behind rulings 66 to 68:** Triton (`ai-gateway`) serves `yolo26` (used), `reid` (resident; the backend
  will call it under B2.2) and `threat` (off; OD-7). The backend's torch is the CPU wheel. The `agent-gpu` library holds
  only the VLM, so the real tier runs a fake detector.

## State at handoff — 2026-10-11 03:39Z

`main` is at `b1e3af4e0`. Rulings run to 100. Batch 11 is due 2026-10-11 13:00Z.

| Agent       | On                                                           | Next                                                                |
| ----------- | ------------------------------------------------------------ | ------------------------------------------------------------------- |
| coordinator | merge queue: #6987, #6981, #6972, #6988                      | batch 11; the merge-queue amendment (ruling 98)                     |
| backend     | #6979 BE-1 golden pytest, green at its head                  | more `F2.3` API batches; B2.2's cleanup PR after the owner's run    |
| frontend    | #6981 guard pin (CI rerun); #6978 FE-1 to FE-4               | `F2.3` UI batches; the `F2.2` follow-up (ruling 92)                 |
| ops-a       | #6986 OP-1 to OP-4 (`F2.3`, ruling 97)                       | —                                                                   |
| ops-b       | #6972 real-sleep gate (ruling 93), waiting on the merge slot | rulings 97 part 2, 100 part 1, 96 item 8, 98 + 100 part 2, in order |
| docs        | review queue; #6988 OD table follow-up                       | `F2.3` UI batches; #6939 and #6928 parked until `R2b`               |
| operator    | idle                                                         | real-tier rows as they appear                                       |
| heavy       | paused, stopped by the owner (ruling 90)                     | restart for Phase 3 heavy packages                                  |
| heavy-2     | paused, stopped by the owner (ruling 90)                     | restart for Phase 3 heavy packages                                  |

**Waiting on the owner:** B2.2's host parity run (command in #6970's body); the operator's owner legs (B1.1, F1.2,
O1.11); turning on the merge queue after ops-b's `merge_group` package merges (ruling 98).
