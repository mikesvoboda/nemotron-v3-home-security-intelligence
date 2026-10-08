# 50 — Coordination

> How several agents execute the uplevel packages at once: who does what, how work is claimed,
> reviewed and merged, and how the owner's time is batched. Rulings UR-22 to UR-30
> ([`README.md`](README.md)). Every agent reads this file; the coordinator works from it.

## Roles

| role            | who                                                                   | does                                                                                                 |
| --------------- | --------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| **owner**       | you                                                                   | rulings, Phase 4 design sessions, owner-tier reviews, final say on merges — once a day, in the batch |
| **operator**    | `uplevel-operator` (UR-30), and the owner for the runs it cannot make | real-tier runs ([`operator.md`](operator.md))                                                        |
| **coordinator** | one agent                                                             | routes work; writes no product code and makes no decisions (below)                                   |
| **lane agent**  | one or two per lane, by phase                                         | claims packages, builds them, self-reviews, and reviews other lanes' PRs                             |

**The coordinator's remit**, and nothing beyond it:

- assign packages: `heavy` packages to the strongest available model or to an owner pairing, the rest
  to lane agents (UR-24);
- assign each PR's reviewing lane, by rotation, never the author's own, and label the PR
  `review:<lane>` when it goes ready (UR-32);
- merge PRs that meet the merge rule, in the order the hot-file rules require;
- keep the README status table accurate, and watch the CI queue;
- collect every question, owner-tier PR and owner-kept real-tier run into the daily batch (UR-25);
- raise the urgent path when its criteria hold;
- state only what it has just read (UR-29): every commit, PR, issue, label, file and check it cites
  comes from `gh` or `git` output it ran in the same turn.

## How many agents

| phase | agents                                                                                          | what limits it                                             |
| ----- | ----------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| 0     | 2, started by hand: the coordinator and `uplevel-ops-b`, which builds the launcher              | nothing: the owner starts Phase 1 by hand (UR-28)          |
| 1     | 8: on the fast model ops ×2, backend, frontend, docs, the coordinator and the operator; 1 heavy | `B1.5`'s auth design unblocks three packages               |
| 2     | 4: ops, frontend (inventory), backend (supporting the inventory), docs                          | one serial chain, `O2.1` → `O2.2` → `F2.1` → `F2.3` → `R2` |
| 3     | 6: backend ×2, frontend, ops ×2, docs                                                           | the hot files                                              |
| 4     | 2–3 feature packages at once, plus one background agent                                         | the owner's design sessions, and modules that overlap      |

More agents do not go faster: CI jobs already queue about six times their runtime
(`.github/workflows/ci.yml:2023-2025`), `main` requires branches to be up to date before merge, and
every agent adds PRs, conflicts and questions for one owner.

**Cells** split a lane between two agents along file sets that do not overlap:

| lane    | cell A                                                                                                        | cell B                                                           |
| ------- | ------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| backend | the VLM path: `backend/services/vlm_*`, `constrained_decoding.py`, `backend/evaluation/`, the circuit breaker | API and auth: `backend/api/`, middleware, `backend/main.py`      |
| ops     | runtime: `ai/`, compose, `setup.py`, `setup_lib/`, the fake stack and harness                                 | tooling: `scripts/`, `.github/`, the mutation scorer, `archive/` |

Ops splits from Phase 1: `uplevel-ops-b` already exists from Phase 0, and ops holds eleven Phase 1
packages. Backend runs as one agent until Phase 3, because the heavy sandbox takes three of its six
Phase 1 packages; it splits into cells A and B for Phase 3's deletions. Frontend and docs run as one
cell each until Phase 3, when the frontend may split into retirement (`F3.1`) and reachability
(`F3.2`, `F3.3`).

**Two schedule rules:**

- The frontend lane starts `F2.2`, the inventory, as soon as its Phase 1 waits on `B1.4` and
  `B1.5` — the blocked-lane rule allows it, and it is the longest job beside the Phase 2 chain.
- In Phase 2 the backend lane, once `B2.1` is done, supports `F2.2` by tracing each feature's
  backend path; `F2.2` integrates what it writes.

## Where agents run (UR-26, UR-28)

```
HOST (owner)               agent-dgx · sbx · the launcher (O0.1) · the local model server · the strongest model
├── uplevel-coordinator    own clone · network: GitHub + model endpoint
├── uplevel-ops-a / -b     own clone · network: GitHub, PyPI, npm, image registries, model endpoint
├── uplevel-backend          · Docker, for the fake stack · backend splits into -a / -b in Phase 3
├── uplevel-frontend
├── uplevel-docs
├── uplevel-heavy (-2)     the strongest model, for heavy packages; the second one is optional
├── uplevel-operator       --gpu: the GB300 through agent-gpu, for the real tier (operator.md)
└── owner on the host      the real-tier runs the operator cannot make (operator.md)
```

- **One sandbox per agent, each with its own clone.** `agent-dgx run <session>` clones the host
  checkout to `/agents/agent-<session>/workspace` and mounts that clone into the sandbox
  `agent-<session>`, so no two agents edit the same files. A clone keeps its commits until they are
  pushed, so an agent pushes its branch after every commit; its draft PR makes the branch visible
  to everyone. Start every agent from a clean host checkout of `main`: `agent-dgx` copies
  uncommitted changes into the clone, and `agent-dgx inspect <session> --json` shows the commit it
  cloned.
- **On the host, read an agent's workspace; run git in it only through `sbx exec`.** Its
  `.git/config` is the agent's to write, and settings such as `core.fsmonitor` run commands when
  the host's git opens the repository (`docs/synthbench/operator-runbook.md`).
- **Only `uplevel-operator` holds the GPU (UR-30).** The owner starts it with `agent-dgx --gpu`,
  which gives its sandbox the `agent-gpu` broker. Real-tier runs go one at a time through that one
  session, under the runner's 40 GiB cap, which every GPU session on the host shares, and no lane sandbox gets the flag.
- **Provisioning stays with the owner.** Creating and removing sandboxes, setting their secrets and
  opening their network policy are privileged, so no agent holds `agent-dgx` or `sbx`. The owner
  starts Phases 0 and 1 by hand and runs the launcher at the later phase boundaries. The
  coordinator routes inside its sandbox and never provisions.
- **GitHub is the only channel between sandboxes.** The coordinator assigns a package by opening its
  draft PR — on a branch holding one empty commit, since a PR needs a commit — with labels
  `lane:<lane>`, `cell:<cell>` and, where they apply, `heavy` and `owner`. The
  daily batch is a comment on a pinned issue titled "Uplevel daily batch", so the owner gets
  GitHub's notifications. The urgent path is the `urgent` label with an @-mention of the owner.
  Everything the coordinator knows lives in GitHub, so its sandbox is disposable: restarted, it
  rebuilds its state from PRs, labels and the pinned issue.
- **Optional hardening.** Tokens are set per sandbox (`sbx secret set github --sandbox agent-<session>`).
  Giving the lane sandboxes a separate machine account's token turns reviews into real GitHub
  approvals, so branch protection can require one — enforcing in GitHub what is policy today.

### The roster

| sandbox               | model     | Phase 0              | Phase 1 queue                                                                                                               | kickoff prompt       |
| --------------------- | --------- | -------------------- | --------------------------------------------------------------------------------------------------------------------------- | -------------------- |
| `uplevel-coordinator` | fast      | labels, pinned issue | assignments, reviews, merges, the daily batch                                                                               | this file            |
| `uplevel-ops-b`       | fast      | `O0.1`, the launcher | `O1.1`, `O1.9`, `O1.10`, `O1.2`, `O1.4`, `O1.5`, `O1.7`, `O1.8`                                                             | `30-ops.md` + cell B |
| `uplevel-ops-a`       | fast      | —                    | `O1.3`, `O1.6` (after `B1.5`), `O1.11` (after `O1.6`); then `O2.1` early                                                    | `30-ops.md` + cell A |
| `uplevel-backend`     | fast      | —                    | `B1.1`, `B1.3`, `B1.4`; then `B2.1` and the inventory's backend tracing                                                     | `10-backend.md`      |
| `uplevel-frontend`    | fast      | —                    | `F1.1`; `F1.2` after `B1.4`; `F1.3` after `B1.5`                                                                            | `20-frontend.md`     |
| `uplevel-docs`        | fast      | —                    | `W1.1`, `W1.3`, `W1.2`                                                                                                      | `40-docs.md`         |
| `uplevel-heavy`       | strongest | —                    | `B1.5`, `B1.2`, `B1.6`; then `F2.2`                                                                                         | below                |
| `uplevel-operator`    | fast      | —                    | real-tier runs: `B1.2`, and `B1.1`'s reply-length tail (its S4 p95 stays the owner's, on the A5500); then `O2.2`'s `--real` | `operator.md`        |
| `uplevel-heavy-2`     | strongest | —                    | optional: `F2.2`, the inventory, from mid-Phase 1                                                                           | below                |

The heavy queue runs in that order for a reason. `B1.5` unblocks `F1.3` and `O1.6` and removes the
critical `python-jose` alert. `B1.2` lifts the pause on VLM prompt work (UR-8). `B1.6` hardens
production, while test deployments are already protected by `O2.2`'s socket rule. The optional
second heavy sandbox runs the inventory beside the Phase 2 chain, which is the largest schedule win
available, at the cost of more strong-model time; the inventory is not owner-tier, so it adds no
review load.

**Split lanes.** An agent in a split lane — the ops cells, and the backend cells from Phase 3 — takes
only packages the coordinator assigns to its cell, never claiming one itself. Its kickoff line
carries one more sentence: `You are cell <A|B> of the <lane> lane; take only packages
the coordinator assigns to your cell.`

**The heavy sandbox's kickoff prompt:**

```text
You are a heavy-package agent of the uplevel programme, running on the
strongest available model. Read docs/uplevel/README.md, then
docs/uplevel/50-coordination.md. Take only packages the coordinator assigns you
(draft PRs labelled heavy). For each one, read and follow the plan of the lane
that owns it — its package text, its file ownership and its kickoff rules — and
the 00-audit.md sections it cites.

One package per PR. Write the failing test first. Before marking the PR ready,
dispatch a fresh-context subagent to self-review it against the package's Done
when, and record what it found. Keep commit subjects at 72 characters or fewer.
State only what you have just read (UR-31): every commit, PR, file, test result
and question you cite comes from output you ran in the same turn. Before
resuming work, read the new comments on your own open PRs (UR-35). When the plan
does not answer a question, stop and report the question.
```

**Phases 0 and 1, started by hand (UR-28).** From a clean host checkout of `main`, the owner
creates each agent with `agent-dgx run <session> --agent claude --endpoint dgx --split` (for
`uplevel-heavy`, the arguments that select the strongest model), then pastes its kickoff line:
"Follow the kickoff prompt in <the roster's file>", plus the cell sentence for a split lane.

Then the owner arms the agent's tick (below, "The tick").

1. Phase 0: the owner starts `uplevel-coordinator` and `uplevel-ops-b`.
2. The coordinator creates the labels and the pinned "Uplevel daily batch" issue, and assigns
   `O0.1` to ops cell B.
3. Phase 1: the owner starts the rest of the roster, without waiting for `O0.1`.
4. `uplevel-ops-b` builds `O0.1` first in its queue. From the Phase 2 boundary on, the owner runs
   the launcher instead of starting agents by hand.

## The tick (UR-36)

Agents act only when prompted, so each one runs on a cadence. After pasting an agent's kickoff line,
the owner arms its tick with Claude Code's `/loop`. The tick's prompt re-runs verbatim on every
tick, fires only between turns (a busy agent gets it once, when its turn ends, and missed ticks do
not pile up), and points here, so an edit to this section reaches every agent at its next tick.

| agent                 | arm with                                                                            |
| --------------------- | ----------------------------------------------------------------------------------- |
| coordinator           | `/loop 5m Run the coordinator tick in docs/uplevel/50-coordination.md, "The tick".` |
| lane agents and heavy | `/loop 15m Run the agent tick in docs/uplevel/50-coordination.md, "The tick".`      |
| operator              | `/loop 30m Run the operator tick in docs/uplevel/50-coordination.md, "The tick".`   |

Every tick starts with `git fetch origin` and reads this section from `origin/main`
(`git show origin/main:docs/uplevel/50-coordination.md`), so a change here needs no rebase.

**The agent tick,** in order:

1. Reviews first: clear the PRs labelled with your review label (UR-32). Heavy has none.
2. Your own open PRs: read the new comments and reviews (UR-35), confirm CI is green at the head
   (UR-34), fix what is red, answer what is requested, and rebase what conflicts with `main`.
3. Continue your package, or take the next one as your kickoff prompt says.
4. If none of these has work, say so in one line and end the turn.

**The coordinator tick:** rebuild state from open PRs, labels and the batch issue; read the new
comments on every open programme PR and on the batch issue; route what needs routing; label ready
PRs for review; merge what meets the merge rule, one at a time; post the daily batch when its time
comes; otherwise say so in one line and end the turn.

**The operator tick:** take the oldest README row on `main` that says `awaiting real tier` and run it
(`operator.md`); otherwise say so in one line and end the turn.

**Keeping ticks alive.** A recurring `/loop` expires seven days after it is armed, and a restarted or
resumed session drops it. The owner re-arms each tick weekly, and after a restart or a `/clear`:
first ask the agent to list its scheduled tasks, and arm a new tick only if none is listed, so ticks
never run twice.

## Claiming a package

0. **Look for an assignment first:** an open draft PR the coordinator created, labelled with your
   lane and cell. It is yours; continue on its branch.
1. **Check** that nobody holds it:
   `gh pr list --state open --search "[<package>] in:title"`.
2. **Claim** it: open a draft PR titled `[<package>] <name>` from a branch named
   `uplevel/<package>-<slug>`, with `gh pr create --draft --template uplevel.md --label lane:<lane>`. The open draft PR
   is the claim; the coordinator's status summary reads claims from open PRs. The README status
   table on `main` changes only when the PR merges.
3. **Depend only on merged work.** A dependency is met when its PR is merged to `main`. Branch from
   `main`, never from another agent's open branch.
4. **Release** a claim you abandon: close the draft PR with a comment saying why.

Packages marked `heavy` in the status table are assigned by the coordinator; a lane agent claims
only unmarked packages on its own.

## Review and merge

**1. Self-review.** Before marking the PR ready, the author dispatches a fresh-context subagent
given only the package text, the diff and the PR body. It checks each Done-when clause against the
evidence, the contract, the cross-lane parts and the hot-file rules. The author fixes what it finds,
or answers it, and records the findings in the PR.

**2. Peer review (UR-23, UR-32).** The coordinator assigns a reviewing lane, preferring the lane
that consumes the change, and names it in a comment when it assigns the package. When the author
marks the PR ready, the coordinator adds the label `review:<lane>` — `review:ops-a` or
`review:ops-b` for a split lane. Lane agents clear their label's PRs before starting or resuming a
package. The reviewer works through the same checks independently, posts the review and removes
the label; after `changes requested`, the coordinator labels the PR again when its author marks
the new head ready. Every agent acts
through the owner's GitHub account, which cannot approve its own PRs, so the review is a PR
comment in this form:

```text
Review: approve | changes requested
Reviewer lane: <lane>
Done when: <each clause> — observed | not observed (where)
Contract: rules 1-5 — ok | <which rule, why>
Notes:
```

**Trust model (UR-27).** Every agent acts through the owner's GitHub token, so GitHub cannot tell
an agent's comment from the owner's. Review comments and owner approvals are a protocol agents
follow, not an authenticated boundary; the owner accepted that risk. An agent writes approvals only
in its own role, and the coordinator merges an owner-tier PR only on an approval the owner gave in
the daily batch.

**3. Owner tier.** These PRs also need the owner's approval, given in the daily batch:

- security and auth: `B1.5`, `B1.6`, `F1.3`, `O1.6`;
- risk acceptance: `O1.8`'s alert dismissals;
- production safety: `O2.2`;
- privileged host tooling: `O0.1`, the launcher;
- destructive work: `B3.1` with `F3.1`, `B3.2`;
- any PR that changes plan text, rulings or the contract in `docs/uplevel/` — a PR setting its own
  package's row in the README status table is contract rule 5 bookkeeping, not plan text (owner,
  2026-10-08);
- any PR with an entry under "Questions for the owner".

The status table marks the fixed ones `owner`.

**4. Merge.** The coordinator merges a PR when CI is green, its review says approve, and — for the
owner tier — the owner has approved. **Green** means the required check
`CI Gate (Required Checks)` is present and passed at the PR's head (UR-34). A check list with no
failures is not enough: when GitHub rejects a workflow file, its run fails with no jobs and leaves no
check behind, so `gh run list --commit <head>` shows the failure and the PR's checks do not. It keeps the repository's existing merge style. Because
`main` requires branches to be up to date, the coordinator updates one queued PR at a time
(`gh pr update-branch`) and waits for its CI, rather than rebasing every open PR at once.

Before each merge the coordinator re-reads the PR
(`gh pr view <n> --json statusCheckRollup,reviews,comments,mergeStateStatus`) and posts a merge
comment that quotes each check's conclusion and links the approving review and, for the owner
tier, the owner's approval (UR-29). An approval the owner gives the coordinator outside the batch
counts once the coordinator has quoted it on the batch issue, with the owner's words and the time.

## Hot files

Files many packages change. The coordinator sequences their merges; authors follow these rules.

| file                                                       | rule                                                                                                                                                                                                                                                   |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `docs/openapi.json`, `frontend/src/types/generated/api.ts` | regenerate after rebasing, never hand-merge                                                                                                                                                                                                            |
| the README status table                                    | edit only your own package's line; prettier skips the table, so leave the other rows' padding alone                                                                                                                                                    |
| `backend/core/config.py`, `.env.example`, compose files    | small hunks; rebase immediately before merge; the coordinator merges one at a time                                                                                                                                                                     |
| `.github/workflows/ci.yml` (3,320 lines)                   | add a new check as its own job, or as its own workflow file, never by editing shared jobs                                                                                                                                                              |
| `.github/workflows/*.yml`                                  | before pushing, run `actionlint` (`docker run --rm -v "$PWD":/repo -w /repo rhysd/actionlint:latest -shellcheck= -pyflakes= .github/workflows/*.yml`) and compare its findings with `main`'s (UR-34); a YAML parse does not check GitHub's expressions |
| `.pre-commit-config.yaml`, `backend/main.py`               | small hunks; one at a time                                                                                                                                                                                                                             |
| `scripts/retired_paths.txt`                                | append-only                                                                                                                                                                                                                                            |
| `.github/suppression-baseline.json`, `.secrets.baseline`   | counts and line numbers: regenerate after rebasing, immediately before merge; never hand-merge a count — two PRs that each add one marker both write the same number, and git merges them silently                                                     |

## Heavy packages (UR-24)

`heavy` marks a package whose mistakes are costly and whose correctness turns on judgment: `B1.2`,
`B1.5`, `B1.6`, `O2.2`, `O3.6`, `F2.2`, `B3.1` with `F3.1`, `B3.2`, and every Phase 4 design session. The
coordinator gives them to the strongest model available, or pairs them with the owner. The
remaining packages are specified tightly enough for a fast local model. If neither a strong model
nor the owner is free, a heavy package waits; it is never handed to a fast model by default.

## The daily batch (UR-25)

Once a day, at a fixed time the owner sets, the coordinator delivers one message:

1. **Status:** one screen — `main`'s state (the conclusion of the latest `CI` and `Deploy` runs on
   `main`, from `gh run list`), packages merged since the last batch, claims in flight, blocked
   lanes and why.
2. **Rulings needed:** each with its facts, options and a recommendation.
3. **Owner-tier PRs:** each with its reviewer's comment and its Done-when checklist.
4. **Operator queue:** the operator agent's results since the last batch, and each real-tier run
   the owner keeps, already vetted against `operator.md`.

**The urgent path** interrupts the owner between batches only for a security exposure, anything
that touches or threatens the live deployment, or `main` red — `CI` or `Deploy` failing on `main` —
for more than one merge, unless an open package already owns that failure (`Deploy`, until `O1.9`
lands).

## Coordinator kickoff prompt

```text
You are the coordinator of the uplevel programme. Read docs/uplevel/README.md,
then docs/uplevel/50-coordination.md, which defines your remit. You run in your
own sandbox; GitHub is your only channel to the other agents and the owner.

On first start (Phase 0), create the labels lane:<lane>, cell:<cell>, heavy,
owner and urgent, and pin an issue titled "Uplevel daily batch". Create the
review:<lane> labels (review:ops-a and review:ops-b for the split ops lane)
whenever one is missing. On every restart, rebuild your state from open PRs,
labels and that issue.

You route work; you write no product code and make no decisions, and you never
provision sandboxes. Assign packages by opening their draft PRs with lane and
cell labels (heavy ones only to the strongest available model or an owner
pairing). Assign each PR's reviewing lane by rotation, and label the PR
review:<lane> when its author marks it ready; merge PRs that meet the
merge rule in the order the hot-file rules require, keep the README status table
accurate, and watch the CI queue.

State only what you have just read. Every commit, PR, issue, label, file and
check you cite in a batch, a comment or a message to the owner comes from gh or
git output you ran in the same turn; when a command fails or its answer is
unclear, say that instead. Before each merge, re-read the PR and post a merge
comment quoting its checks, its approving review and, for the owner tier, the
owner's approval. CI is green only when the required check CI Gate (Required
Checks) is present and passed at the head; also read gh run list --commit
<head>, since a rejected workflow file fails with no jobs and leaves no check
(UR-34).

Agents read GitHub only when their prompt sends them there. Put what an agent
must act on where it looks: a review:<lane> label, or a comment on that agent's
own open PR, which it reads before resuming work (UR-35).

Post one daily batch as a comment on the pinned issue, in the format
50-coordination.md gives. Interrupt the owner between batches only on the
urgent-path criteria, with the urgent label and an @-mention.
```
