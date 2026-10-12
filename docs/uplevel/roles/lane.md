# Lane and heavy agents

> For the lane agents (`uplevel-backend`, `uplevel-frontend`, `uplevel-ops-a`, `uplevel-ops-b`,
> `uplevel-docs`) and the heavy agents (`uplevel-heavy`, `uplevel-heavy-2`). This file is your
> procedure: your tick, claiming, building, self-review, reviewing other lanes' PRs, posting, and
> your kickoff prompt. The rules each step obeys live in [`rules.md`](../rules.md); each step names
> the section to read before you act. Your packages are in `packages/<lane>.md`.

## Who takes what

**The roster.** The sandboxes of the programme and the queue each was given. The coordinator
assigns from it (rules.md §Claiming and assigning work: an assignment-only agent's "next roster
package"), and `scripts/uplevel/sandboxes.toml` declares the same sessions.

| sandbox               | model     | Phase 0              | Phase 1 queue                                                                                                               | kickoff prompt                    |
| --------------------- | --------- | -------------------- | --------------------------------------------------------------------------------------------------------------------------- | --------------------------------- |
| `uplevel-coordinator` | fast      | labels, pinned issue | assignments, reviews, merges, the daily batch                                                                               | `roles/coordinator.md`            |
| `uplevel-ops-b`       | fast      | `O0.1`, the launcher | `O1.1`, `O1.9`, `O1.12`, `O1.10`, `O1.2`, `O1.4`, `O1.5`, `O1.7`, `O1.8`                                                    | this file + cell B                |
| `uplevel-ops-a`       | fast      | —                    | `O1.3`, `O1.6` (after `B1.5`), `O1.11` (after `O1.6`); then `O2.3`, `O2.3b`, and `F2.3` UI batches                          | this file + cell A                |
| `uplevel-backend`     | fast      | —                    | `B1.1`, `B1.3`, `B1.4`; then `B2.1`, the inventory's backend tracing, `F2.3`'s API batches and `B2.2`'s cleanup             | this file, backend line           |
| `uplevel-frontend`    | fast      | —                    | `F1.1`; `F1.2` after `B1.4`; `F1.3` after `B1.5`                                                                            | this file, frontend line          |
| `uplevel-docs`        | fast      | —                    | `W1.1`, `W1.3`, `W1.2`; then `F2.3` UI batches                                                                              | this file, docs line              |
| `uplevel-heavy`       | strongest | —                    | `B1.5`, `B1.2`, `B1.6`; then `O2.1`, `O2.2`; paused from 2026-10-10 (owner ruling 88)                                       | this file, `uplevel-heavy` line   |
| `uplevel-operator`    | fast      | —                    | real-tier runs: `B1.2`, and `B1.1`'s reply-length tail (its S4 p95 stays the owner's, on the A5500); then `O2.2`'s `--real` | `roles/operator.md`               |
| `uplevel-heavy-2`     | strongest | —                    | `F2.2`, the inventory, from mid-Phase 1; then `B2.2`; paused from 2026-10-10 (owner ruling 88)                              | this file, `uplevel-heavy-2` line |

**How each takes work:**

| sandbox            | model     | takes work                                             | review label      |
| ------------------ | --------- | ------------------------------------------------------ | ----------------- |
| `uplevel-backend`  | fast      | its assignment, otherwise claims its own               | `review:backend`  |
| `uplevel-frontend` | fast      | its assignment, otherwise claims its own               | `review:frontend` |
| `uplevel-ops-a`    | fast      | only packages the coordinator assigns to `cell:a`      | `review:ops-a`    |
| `uplevel-ops-b`    | fast      | only packages the coordinator assigns to `cell:b`      | `review:ops-b`    |
| `uplevel-docs`     | fast      | its assignment, otherwise claims its own               | `review:docs`     |
| `uplevel-heavy`    | strongest | only draft PRs labelled `heavy` without `cell:heavy-2` | none              |
| `uplevel-heavy-2`  | strongest | only draft PRs labelled `heavy` and `cell:heavy-2`     | none              |

**Split lanes.** A cell splits a lane between two agents along file sets that do not overlap. An
agent in a split lane takes only packages the coordinator assigns to its cell and never claims one
itself.

| lane    | cell A                                                                                                        | cell B                                                           |
| ------- | ------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| backend | the VLM path: `backend/services/vlm_*`, `constrained_decoding.py`, `backend/evaluation/`, the circuit breaker | API and auth: `backend/api/`, middleware, `backend/main.py`      |
| ops     | runtime: `ai/`, compose, `setup.py`, `setup_lib/`, the fake stack and harness                                 | tooling: `scripts/`, `.github/`, the mutation scorer, `archive/` |

Ops runs as two cells. Backend runs as one agent until Phase 3 and splits into cells A and B for
Phase 3's deletions. Frontend and docs run as one cell each; in Phase 3 the frontend may split into
retirement (`F3.1`) and reachability (`F3.2`, `F3.3`).

**Heavy agents.** The coordinator assigns you packages by draft PRs labelled `heavy`; the label
`cell:heavy-2` addresses `uplevel-heavy-2`, its absence `uplevel-heavy` (rules.md §Claiming
and assigning work). For each package, read and follow the packages file of the lane that owns
it — its package text, its file ownership and its kickoff line below — and the `00-audit.md`
sections it cites. You have no review label.

## The tick

The owner arms it with `/loop 15m Run the agent tick in docs/uplevel/roles/lane.md, "The tick".`
Run these steps in order. Long work inside a turn is fine; waiting is not: read CI once per tick,
report what you see and end the turn (rules.md §Posting, heartbeats and the urgent path).

1. **Fetch.** `git fetch origin`, then read this file and `rules.md` from `origin/main`
   (`git show origin/main:docs/uplevel/roles/lane.md`), so a change to either needs no rebase.
2. **Heartbeat.** Edit your heartbeat ("Heartbeat" below). Read the coordinator's; if it is older
   than 20 minutes, follow "Stale coordinator" below.
3. **Reviews first:** clear the PRs labelled with your review label ("Reviewing another lane's PR"
   below). Heavy agents skip this step.
4. **Your own open PRs:** read the new comments and reviews on each (`gh pr view <n> --comments`).
   An owner ruling or a requested change there comes before new work; nobody tells you about a
   comment except by writing it. Read CI at the head once, fix what is red, answer what is
   requested, and rebase what conflicts with `main` (rules.md §Merging says what a new head resets).
5. **Continue your package,** or take the next one ("Claiming a package" below).
6. If none of these has work, say so in one line and end the turn.

## Heartbeat

The pinned issue "Uplevel heartbeats" holds one comment per agent. Edit yours in place on every
tick, never post a new one; post it once if you have none. It is two lines:

```text
<!-- heartbeat:<sandbox> -->
<sandbox> · <HH:MMZ, read from date -u> · idle | working #<n> | waiting on <what> | paused · <why>
```

Find the issue with `gh issue list --state open --search "Uplevel heartbeats in:title"`, find your
comment by its first line, and edit it with
`gh api -X PATCH repos/<owner>/<repo>/issues/comments/<id> -f body=<the two lines>`.

**Stale coordinator.** When the coordinator's heartbeat is older than 20 minutes, read #6854 for a
comment from the last hour whose first line starts `URGENT PATH · coordinator stale`. If there is
none, post one: that first line, the heartbeat's age and the time you read it, nothing more, and no
@-mention. The owner restarts the coordinator; no agent reaches into another's sandbox.

**Paused.** A heavy agent whose queue is empty posts a final heartbeat
`paused · queue empty (ruling 88)` and ends its turn; the owner stops its loop (rules.md §Posting,
heartbeats and the urgent path). When the owner
restarts it, it runs its kickoff line from `scripts/uplevel/sandboxes.toml` and `/loop 15m` as
usual (rules.md §Agents, sandboxes and models).

## Claiming a package

Read rules.md §Claiming and assigning work first.

1. **Look for an assignment:** an open draft PR the coordinator created, labelled with your lane
   and cell (`heavy` for a heavy agent). It is yours; continue on its branch. Split lanes and heavy
   agents stop here: they take only assignments.
2. **Choose:** the lowest-numbered package in your current phase that is `not started`, not
   flagged `heavy`, unclaimed and whose dependencies are merged. If every remaining package in your
   phase waits on another lane, take the next phase's first ready package. Start a Phase 3 package
   only as rules.md §Claiming and assigning work allows (`R2` done, or the `R2a` and `R2b`-round
   exceptions). Claim your next package on the tick its dependency lands.
3. **Check** that nobody holds it: `gh pr list --state open --search "[<package>] in:title"`.
4. **Claim** it before writing any code: branch `uplevel/<package>-<slug>` from `main`, commit
   nothing but an empty commit (`git commit --allow-empty -m "[<package>] claim"`), push it, and
   open a draft PR titled `[<package>] <name>` with
   `gh pr create --draft --template uplevel.md --label lane:<lane>`. The open draft PR is the
   claim. Branch from `main`, never from another agent's open branch.
5. **Release** a claim you abandon: close the draft PR with a comment saying why.

## Building a package

Read rules.md §Building a package first: one package per PR, the hot-file rules, and the contract.

1. Write the failing test first.
2. Build until the package's Done when holds. Push your branch after every commit: your clone keeps
   commits until they are pushed, and the draft PR makes the branch visible to everyone.
3. Fill the PR body from the template: each command and its output. Keep commit subjects at 72
   characters or fewer. Edit the `AGENTS.md` lines that describe what you changed.
4. Set the package's README status row in the same PR: `done` with the PR number, or
   `awaiting real tier` with the operator's command in the PR's "Real tier" section (rules.md
   §Statuses, rows, the inventory and R2).
5. When the plan does not answer a question, stop and report the question, under "Questions for the
   owner" in the PR body.
6. Authors of `F2.2`, `O2.3` and R2's list of modules serving no feature dispatch
   `codebase-archaeologist` on their scope, and quote only the findings they reproduced (rules.md
   §Reviewing).

**Self-review.** Before marking the PR ready, dispatch a fresh-context subagent given only the
package text, the diff and the PR body. It checks each Done-when clause against the evidence, the
contract, the cross-lane parts and the hot-file rules. Fix what it finds or answer it, record the
findings in the PR, then mark the PR ready.

## Reviewing another lane's PR

Read rules.md §Reviewing first.

1. List your queue: `gh pr list --state open --label review:<your label>`.
2. Review each PR independently against its package's Done when, the contract and the hot-file
   rules. Read every `docs/uplevel/` hunk before you write its `Plan text:` line. For a
   security-and-auth package, dispatch `security-auditor` on the diff, and quote only the findings
   you reproduced, saying which you set aside and why.
3. Post the review as a PR comment in this form:

   ```text
   Review: approve | changes requested
   Reviewer lane: <lane>
   Done when: <each clause> — observed | not observed (where)
   Contract: rules 1-5 — ok | <which rule, why>
   Plan text: none | <which kind of plan text it changes (rules.md §Authority: rulings, plan text and IDs), and where>
   Notes:
   ```

4. Remove the review label.

## Posting

Every comment, PR body and review carries only your own text, never the framing your harness wraps
around a subagent's output. State only what you have just read: every commit, PR, file, test result
and question you cite comes from output you ran in the same turn. Keep heartbeats and lane notes
within the post budget (rules.md §Posting, heartbeats and the urgent path).

## Kickoff prompt

The owner pastes the line from `scripts/uplevel/sandboxes.toml` for the sandbox; it points here and
names the lane. Then the owner arms the tick with
`/loop 15m Run the agent tick in docs/uplevel/roles/lane.md, "The tick".` The shared prompt:

```text
You are a lane agent of the uplevel programme; your kickoff line names your
lane. Read docs/uplevel/README.md, then docs/uplevel/rules.md, then
docs/uplevel/roles/lane.md, which is your procedure, then your lane's line
under "Kickoff prompt" in lane.md, then the packages file it names and the
docs/uplevel/00-audit.md sections each package cites.

Take the package the coordinator assigns you; otherwise claim one as lane.md,
"Claiming a package", says, if your line lets you. Build it as lane.md,
"Building a package", says. Reviews come first, then the new comments on your
own open PRs, then your package. Before each act, read the rules.md section the
step names.

Then run the tick in lane.md, "The tick".
```

**Per-lane lines.** Find the sentence your kickoff line carries and follow its paragraph.

- **"You are the backend lane."** Your packages are in `docs/uplevel/packages/backend.md`; your
  review label is `review:backend`. You own `backend/`. The cross-lane rule (rules.md §Building a
  package) governs every other file you touch.
- **"You are the frontend lane."** Your packages are in `docs/uplevel/packages/frontend.md`; your
  review label is `review:frontend`. You own `frontend/` and `docs/reference/feature-inventory.md`.
  The cross-lane rule (rules.md §Building a package) governs every other file you touch.
- **"You are cell A of the ops lane"** or **"You are cell B of the ops lane"**. Your packages are
  in `docs/uplevel/packages/ops.md`; take only packages the coordinator assigns to your cell. Your
  review label is `review:ops-a` or `review:ops-b`. You own `ai/`, compose, `scripts/`, `.github/`,
  `setup.py`, `setup_lib/`, root config and `archive/`. The cross-lane rule (rules.md §Building a
  package) governs every other file you touch. Real-model checks run on the GB300 by the operator,
  never from CI.
- **"You are the docs lane."** Your packages are in `docs/uplevel/packages/docs.md`; your review
  label is `review:docs`. Read the AGENTS.md standard at `docs/developer/agents-md-standard.md`
  after the packages file. Start Phase 3 work on a lane's directories only after that lane's
  Phase 3 is `done`. You own `docs/`, every `AGENTS.md`, `llms.txt`, `mkdocs.yml`, the root
  markdown files and the AGENTS.md validator. Write what an agent cannot find by looking; leave
  inventories to the code.
- **"You are uplevel-heavy."** You run on the strongest available model and take only `heavy` PRs
  without `cell:heavy-2` ("Heavy agents" above). For each package, read the packages file and the
  line above of the lane that owns it, and follow them. You have no review label.
- **"You are uplevel-heavy-2; take only heavy PRs labelled cell:heavy-2."** As `uplevel-heavy`,
  for the PRs labelled `heavy` and `cell:heavy-2`.
