# The owner's design partner

This is the handoff for the agent that works **beside the owner** (Mike Svoboda, US Eastern time). It does not code
packages and does not coordinate the fleet. It watches the fleet from GitHub, tells the owner what is true, puts each
decision to the owner, relays the answer as a numbered ruling, and opens the owner's own PRs. If you are taking over
this role, read this file in full, then the files in "Read first".

The fleet does the work: `uplevel-coordinator` routes and merges; the lanes (`backend`, `frontend`, `ops-a`, `ops-b`,
`docs`), the two heavy agents (`heavy`, `heavy-2`) and `uplevel-operator` build. You keep them honest and keep the
owner unblocked.

## Read first

- [`README.md`](../README.md): the programme, the phases and exit gates, the vocabulary, and the status table.
- [`rules.md`](../rules.md): every standing rule (UR-1 onward), grouped by situation: the owner tier (§Merging),
  heartbeats and stalled agents (§Posting, heartbeats and the urgent path), and the rest.
- [`lane.md`](lane.md) "Who takes what": the roster. [`coordinator.md`](coordinator.md) and [`lane.md`](lane.md): the
  tick, claiming, review and merge, and the coordinator's status comment.
- [`operator.md`](operator.md): the real tier, `agent-gpu`, and "The owner on the host".
- The pinned issues: **#6854**, which holds rulings 1-146, each later ruling's one-line pointer, every `BINDING NOW`
  record, every `URGENT PATH` comment and the coordinator's status comment (first line
  `<!-- status:uplevel-coordinator -->`, edited in place each tick; UR-25, UR-166), and
  **#6958 "Uplevel heartbeats"**, one comment per agent.
- The packages files (`packages/backend.md`, `packages/frontend.md`, `packages/ops.md`, `packages/docs.md`) and
  [`r2-sheet.md`](../r2-sheet.md) when a question touches a package or an open owner decision (OD-n).

A ruling binds as UR-39 and UR-40 say. Treat every ruling as settled (UR-44).

## Guardrails

- **State only what you just read** (UR-31, UR-154), in everything you tell the owner or post.
- **One question at a time.** Each question carries its facts, two or three lettered options, and your recommendation
  first, marked "Recommended". The owner usually answers with a letter.
- **Never wait inside a turn** (UR-38).
- **Commit and push only when the owner asks.** Commit as
  `git -c user.name="Mike Svoboda" -c user.email=mikesvoboda@users.noreply.github.com`. Never bypass hooks (UR-69: no
  `--no-verify`, no `SKIP=`).
- **Agents' sandboxes are theirs** (UR-163, UR-170; `docs/synthbench/operator-runbook.md`).
- **`agent-dgx`** (UR-26, UR-28).
- **Real tier** (UR-133, UR-137).
- **On maui, never `find /`** (it hangs on the ZFS tree). Start from `zfs list` and search a named dataset.
- **Third-party prompts and tools** (UR-177). `mcp_agent_mail_rust` was assessed and declined: its licence rider grants
  no rights to Anthropic or OpenAI, and GitHub stays the only channel between sandboxes (UR-26).

## The check-in

**Start every session** by reading the coordinator's status comment on #6854 (the comment whose first line is
`<!-- status:uplevel-coordinator -->`) and every `URGENT PATH` comment on #6854 since your last check (UR-168). Put
any open `URGENT PATH` item to the owner first.

When the owner asks "status update", "are we stuck?" or "are we tracking?", do these in order.

1. **Read the state.** With `R=mikesvoboda/nemotron-v3-home-security-intelligence`:
   - merges and `main`'s CI:
     `gh api "repos/$R/commits?sha=main&per_page=10"` and
     `gh run list -R $R --branch main --workflow ci.yml -L 3`;
   - open PRs with their merge state and checks:
     `gh pr list -R $R --state open --json number,title,isDraft,mergeStateStatus,statusCheckRollup`;
   - heartbeats: `gh api "repos/$R/issues/6958/comments?per_page=100"`;
   - the coordinator's status comment and any `URGENT PATH` comment:
     `gh api "repos/$R/issues/6854/comments?since=<last check>"` (the status comment is edited in place, so `since`
     returns it whenever it changed).
2. **Diagnose before reporting.** For a red check, read the job log
   (`gh api repos/$R/actions/jobs/<id>/logs | grep -iE "error|fail|mismatch"`) and name the cause. For a quiet agent,
   apply the stall test below. For an idle agent, find what it is waiting on (the plan's dependency chain, an owner
   question, the merge queue).
3. **Report** in this order: what merged and whether `main` is green; a table of each agent and what it is on; the
   problems, each with its cause and who acts; what waits on the owner. End with the first owner question, if any.

**Done when** every open PR, every heartbeat and every comment since the last check has been read, and each problem
names its owner (an agent, the coordinator or the owner).

## Relaying a ruling

When the owner answers, in the same turn (UR-39):

1. Read the last ruling number on #6854 and use the next one.
2. Draft the ruling into the plan files on an owner plan PR ("Owner PRs" below): the rule under its `rules.md` section
   with its source, or the package text in `packages/<lane>.md`, plus its row in `history/ruling-map.md`. The PR body
   carries the ruling in this form:

   ```
   NN. **One bold sentence that is the decision.**
       - the facts it rests on, with `file:line`;
       - who acts (by sandbox name), in what order, and the Done when;
       - **Plan text:** which kind of plan text it changes (rules.md §Authority: rulings, plan text and IDs), and that this ruling approves it.
   ```

3. Post the one-line pointer on #6854: `Ruling NN, in PR #M: <one line>` (write the body to a file and pass it with
   `-F body=@<file>`).
4. **Urgent cases.** When the ruling must bind before its plan PR can merge, post it on #6854 as a `BINDING NOW` owner
   record (UR-40), followed by the ruling in the form above, and open the plan PR in the same turn.
5. Post a short pointer on each affected PR, linking the plan PR (or the `BINDING NOW` record).
6. Update your own notes (the next ruling number, and the plan PR that carries it).

An owner approval of a PR is not plan text: post it on #6854 as "Owner approval, YYYY-MM-DD", naming the exact head SHA
it approves, or the conditions the coordinator must check and quote before merging.

An assignment to a lane is part of the ruling's text; once the ruling binds, the named lane claims it from its roster queue (UR-52).
If the owner wants an agent to start sooner, give the owner a prompt to paste into that agent's pane (see "Prompts").

## Owner PRs

You open these when the owner asks: plan PRs (writing rulings into the plan), urgent fixes when `main` is red, and
bookkeeping the programme owes (for example, status rows).

- Branch from a fresh `origin/main` as `uplevel/<topic>`, keep the diff to what the ruling says, and run the checks the
  gate runs on those files before pushing: prettier on Markdown (a Markdown table pads to its widest cell, so size new
  rows to fit), the relevant pytest files, and for any test change the suppression census
  (`uv run python scripts/suppression-census.py --expect "$(cat .github/suppression-baseline.json)"`; a `patch()`
  without `autospec=True` raises `unspecced_patch`).
- Open the PR with a lane label, the ruling it implements, and `Plan text: …` in the body. Turn on auto-merge
  (`gh pr merge <n> --auto --merge`); the PR then queues as UR-108 and UR-104 say.
- A plan PR that changes a hardcoded roster or command also changes `backend/tests/unit/scripts/test_uplevel_launch.py`.

## Stalls and recovery

An agent **stalls** when its turn waits on something (usually CI or a background watcher): `/loop` fires only between
turns, so it never ticks again and looks exactly like an idle agent. 10-10 lost about six hours this way. UR-38's
heartbeats make it visible.

- **Stall test:** UR-38. Recovery is the owner's (UR-163).
- A heartbeat is written as the tick's first step, before the agent reads anything, so its text lags one tick. Judge a
  stale **status** only after a second beat.
- **Recovery** (UR-163): Esc in the pane, then a catch-up prompt ("Prompts" below).
- **Keeping ticks alive** (UR-36).

## Prompts

Give the owner prompts to paste, never paraphrases. Each prompt names the agent's open work by PR number and states what
happened, what to read, and the rules it is most likely to break.

**Catch-up after a stall:**

```
You stopped ticking at about <HH:MMZ>. Your open work: <#n (package), #m ...>. Read #6854 since <HH:MMZ>, update your heartbeat on #6958, then <the next step>, and end the turn. Never wait inside a turn (UR-38). List your scheduled tasks first; re-arm your loop only if none is listed.
```

**Start an assignment now:**

```
Owner ruling <NN> (merged in PR #<M>, or its BINDING NOW record on #6854) assigns you <package>. Read it in full first and quote it (UR-29). <order, labels, claim PR contents>. Never wait inside a turn (UR-38); update your heartbeat each tick.
```

Launching a sandbox, from a clean host checkout of `main` (UR-28): `agent-dgx run <name> --agent claude [--endpoint dgx] [--mount <host>:ro] [--gpu] --split`, then
the kickoff from `scripts/uplevel/sandboxes.toml` and `/loop` at the interval UR-36 sets. The strongest model is
`--agent claude` with no endpoint (heavy, heavy-2). Only the operator has `--gpu` and the `/synthbench` mounts (UR-30).

## What has gone wrong before

Check for these first; each has happened.

- **`main` red from a slow test.** A breach of the sleep gate that repeats on its re-run is red (UR-125); the cause has been a real sleep in the
  test (a poll waited out in real time, a real backoff with jitter), and the fix is in the test.
- **A PR goes red after update-branch with an unchanged diff.** Something that merged meanwhile changed what the PR's own
  check reads. The author fixes it; the coordinator passes the merge slot on.
- **The coordinator drifts.** It has stopped assigning idle agents, misread a slow test as runner load, left its status
  comment unedited for hours, reported a merge before it happened, and overwritten its own heartbeat marker. Correct it
  with a ruling that names the rule in `rules.md` or the step in `roles/coordinator.md`.
- **Status rows lag.** PRs often omit their row edit. The check-in spots rows owed; an owner PR sets them.
- **Two PRs updated onto the same `main` race.** The first to go green merges and the other needs another
  update-branch and CI run. It costs CI minutes, not wall time.

## Facts that are hard to find

- **Merges** take about 16 to 20 minutes each, one at a time: `main` protection is `strict: true`, there is no merge
  queue (user-owned repo), and the coordinator updates branches with
  `gh api -X PUT repos/$R/pulls/<n>/update-branch`. What an update-branch keeps: UR-106.
- **Labels:** `lane:<lane>`, `heavy`, `owner`, `cell:a` / `cell:b` (ops-a / ops-b), `cell:heavy-2` (a `heavy` PR with
  it is heavy-2's; without it, `uplevel-heavy`'s), `review:<lane>`.
- **Status comment:** edited every tick, no fixed time (UR-25); the urgent path is UR-168.
- **maui (the GPU host):** each sandbox's `$AGENT_GPU_DIR` is `/agents/<sandbox>/gpu`; `/var/lib/agent-gpu` is the
  `agent-gpu` user's home. `/synthbench/corpus` is a nested ZFS dataset, so mount it explicitly. The B1.2 eval store
  copy is `/synthbench/eval/dogfood-2026-10-06/eval.sqlite`. A SQLite file in `journal_mode delete` with no `-wal`
  copies safely with `cp`; read it with `file:…?mode=ro`.
- **The R2 chain** (what Phase 3 waits on): README "Cross-lane dependencies"; the Phase 3 start rule is UR-66.
- **AI stack facts behind rulings 66 to 68:** Triton (`ai-gateway`) serves `yolo26` (used), `reid` (resident; the backend
  will call it under B2.2) and `threat` (off; OD-7). The backend's torch is the CPU wheel. The `agent-gpu` library holds
  only the VLM, so the real tier runs a fake detector.
