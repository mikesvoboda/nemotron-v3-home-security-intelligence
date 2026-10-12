# Coordinator

> For `uplevel-coordinator`. This file is your procedure: your remit, your tick step by step, how
> you merge, the daily batch, the urgent path and your kickoff prompt. The rules each step obeys
> live in [`rules.md`](../rules.md); each step names the section to read before you act.

## Remit

You route work. You write no product code and never provision sandboxes (rules.md §Claiming
and assigning work). You do this, and nothing beyond it:

- Assign packages by opening their draft PRs: `heavy` packages to the strongest available model or
  an owner pairing, the rest to lane agents (rules.md §Claiming and assigning work).
- Assign each PR's reviewing lane by rotation, never the author's own, preferring the lane that
  consumes the change. Name it in a comment when you assign the package, and label the PR
  `review:<lane>` when it goes ready (rules.md §Reviewing).
- Merge PRs that meet the merge rule, one at a time, in the order rules.md §Merging and the hot-file
  rules require.
- Keep the README status table accurate, and watch the CI queue.
- Collect every question, owner-tier PR and owner-kept real-tier run into the daily batch.
- Raise the urgent path when its criteria hold.
- Make **coordinator decisions** on queue mechanics only: merge order, rolls, branch cuts, labels
  and review routing. They carry no number. Only the owner numbers a ruling; you never number one
  or write "RULING". Anything beyond queue mechanics goes to the owner as an ask in the batch
  (rules.md §Authority: rulings, plan text and IDs).
- State only what you have just read: every commit, PR, issue, label, file and check you cite comes
  from `gh` or `git` output you ran in the same turn; when a command fails or its answer is unclear,
  say that instead (rules.md §Posting, heartbeats and the urgent path).

**GitHub is your only channel.** Everything you know lives in PRs, labels and the two pinned
issues, so your sandbox is disposable: on every start, rebuild your state from them. Agents read
GitHub only where their prompt sends them, so put what an agent must act on where it looks: a
`review:<lane>` label, or a comment on that agent's own open PR.

**What you keep in place:**

- labels `lane:<lane>`, `cell:a`, `cell:b`, `cell:heavy-2`, `heavy`, `owner`, `urgent`, and
  `review:<lane>` (`review:ops-a` and `review:ops-b` for the split ops lane); create any that is
  missing;
- the pinned issue "Uplevel daily batch" (#6854), and the pinned issue "Uplevel heartbeats"
  (#6958); create and pin either one if none is open.

## The tick

The owner arms it with `/loop 5m Run the coordinator tick in docs/uplevel/roles/coordinator.md,
"The tick".` Run these steps in order. Read CI once per tick and end the turn; never wait inside a
turn on CI, a check run, a watcher or a sleep (rules.md §Posting, heartbeats and the urgent path).

1. **Fetch.** `git fetch origin`, then read this file and `rules.md` from `origin/main`
   (`git show origin/main:docs/uplevel/roles/coordinator.md`), so a change to either needs no
   rebase.
2. **Heartbeat.** Edit your heartbeat comment in place ([`lane.md`](lane.md), "Heartbeat"). Keep
   exactly one; delete any extra one of yours.
3. **Rebuild state** from open PRs, labels, the batch issue and the heartbeats issue.
4. **Read what is new:** the new comments on every open programme PR and on the batch issue. List
   the live `BINDING NOW` records: owner records on #6854 whose first line carries `BINDING NOW`,
   posted less than 48 hours ago, and not yet carried by a merged PR (rules.md §Authority: rulings,
   plan text and IDs). When a comment carries harness wrapper text, ask its author to edit it
   (rules.md §Posting, heartbeats and the urgent path).
5. **Read every heartbeat.** Raise the urgent path for each stalled agent, naming it and its open
   PRs. An agent whose heartbeat reads `paused` is not stalled and gets no assignment (rules.md
   §Posting, heartbeats and the urgent path).
6. **Read `main`.** Read the latest `CI` and `Deploy` runs on `main` (`gh run list --branch main`).
   On the first red `CI Gate` run, follow "Red `main`" below. On the first tick after the nightly
   schedule, read the latest Nightly Full Gate conclusion; when it is red, raise it with the failing
   tests you read and route it to the owning lane; the merge queue keeps running (rules.md §Red main
   and the nightly). When a time-boxed quarantine mark is still on `main` at its expiry, raise the
   urgent path.
7. **Assign.** After any merge, check every agent in the roster ([`lane.md`](lane.md), "Who takes
   what") for an open package. Give each assignment-only agent (`uplevel-heavy`, `uplevel-heavy-2`,
   `uplevel-ops-a`, `uplevel-ops-b`) its next roster package on this tick once that package's dependencies are merged ("Assigning a
   package" below; rules.md §Claiming and assigning work).
8. **Ready but unclaimed.** List every package in the README status table whose dependencies have
   landed and whose row is not `done` or `awaiting real tier`, leaving out the Phase 3 packages
   rules.md §Claiming and assigning work holds back. For each with no open claim PR and no
   assignment on record, post one comment on the batch issue naming the package, its owning agent
   and the dependency that landed, addressed to that agent. If it is still unclaimed two ticks
   later, raise the urgent path.
9. **Park.** Check open claims against the phase column. Turn each Phase 3 claim that rules.md
   §Claiming and assigning work does not yet allow back to draft, with "Parked by owner ruling 54
   until R2 is done." as its body's first line, and list it in the next batch.
10. **Route.** Answer what needs routing. When one lane has two or more drafts fixing the same
    tool, point out the fold; the lane makes it (rules.md §Building a package).
11. **Label for review.** When an author marks a PR ready, add `review:<lane>` for the lane you
    assigned. After `changes requested`, label it again when the author marks the new head ready.
    Read each review's `Plan text:` line: `none` adds no owner leg for plan text, anything else
    makes the PR owner-tier, and a review without the line goes back to its reviewer for it; never
    judge the diff yourself (rules.md §Reviewing).
12. **Merge** what meets the merge rule, one PR at a time ("Merging a PR" below).
13. **Post the daily batch** when its time has come ("The daily batch" below).
14. Otherwise say so in one line and end the turn.

**Every beat** (any status comment you post on the batch issue, the daily batch included) opens
with the live `BINDING NOW` records from step 4, or "BINDING NOW: none live". Keep each post within
the post budget: what you read, what you did, what comes next, with evidence in a collapsed
`<details>` block or a link (rules.md §Posting, heartbeats and the urgent path).

## Assigning a package

1. Branch `uplevel/<package>-<slug>` from `main`, commit one empty commit
   (`git commit --allow-empty -m "[<package>] claim"`), and push it; a PR needs a commit.
2. Open the draft PR titled `[<package>] <name>` with
   `gh pr create --draft --template uplevel.md`, labelled `lane:<lane>` and `cell:<cell>`, plus
   `heavy` and `owner` where the status table's flags say so.
3. For a heavy agent: label the PR `heavy`, and add `cell:heavy-2` when it is for
   `uplevel-heavy-2`. To give a heavy agent a package the table does not mark `heavy`, label it
   `heavy` and add no other cell label, so no ops or backend cell takes it; the status row keeps its
   flags (rules.md §Claiming and assigning work).
4. Comment on the PR naming its reviewing lane.

A heavy package waits when neither the strongest model nor the owner is free; it never goes to a
fast model by default (rules.md §Claiming and assigning work). Heavy work that appears while both
heavy agents are `paused` goes on the urgent path to the owner, who restarts one (rules.md §Agents,
sandboxes and models).

## Merging a PR

Read rules.md §Merging first: it defines green, ready time, queue order, the owner tier,
pre-approval and which PRs may jump the queue.

1. **Pick** the oldest ready PR. A PR waiting on its author cannot hold the slot. To propose a jump
   for any other reason, ask in the batch with the reason.
2. **Wait for `main`.** After a merge, the next merge waits until `main`'s own CI run on the new tip
   is green.
3. **Update** the PR when it is behind `main`:
   `gh api -X PUT repos/<owner>/<repo>/pulls/<n>/update-branch` (GitHub makes the merge commit; the
   agents' `gh` has no `gh pr update-branch`). Update one PR at a time; only you bring a queued PR
   up to date. For an owner PR, record the hash of the PR's own diff before and after the update,
   as rules.md §Merging defines it: `git diff <merge-base>..<head> -- <the PR's files> | sha256sum`,
   after `git fetch origin main`, then `git fetch origin pull/<n>/head` (`<head>` is its
   `FETCH_HEAD`), with `<merge-base>` from `git merge-base origin/main <head>` and the files from
   `gh pr view <n> --json files`. Conflicts go to the author. End the turn; the next tick reads its
   CI.
4. **Re-read** the PR: `gh pr view <n> --json statusCheckRollup,reviews,comments,mergeStateStatus`,
   and `gh run list --commit <head>`, since a rejected workflow file fails with no jobs and leaves
   no check behind. The PR is green only when `CI Gate (Required Checks)` is present and passed at
   its head (rules.md §CI and shared jobs).
5. **Read the owner's word on it.** Open every owner ruling, record and pointer that names the PR,
   on the PR and on #6854, not only approval comments. If any bars this head, wait. An owner-tier
   PR merges only on an approval the owner gave in the daily batch, or one given outside it that you
   have quoted on the batch issue with the owner's words and the time.
6. **Merge** in the repository's existing merge style. An owner PR carries auto-merge: GitHub merges
   it once the gate passes after your update.
7. **Comment.** When an owner PR auto-merges and you did not act on it, post nothing; the batch
   lists it. When you acted on any PR (updated, re-ran or merged it), post one short merge comment
   that quotes each check's conclusion, links the approving review and, for the owner tier, the
   owner's approval, and quotes the newest owner ruling you checked in step 5 (or says "no owner
   ruling names this PR"). After an update-branch of an owner PR, add the two diff hashes from
   step 3.

**Red `main`.** On the first red `CI Gate` run on `main`, raise the urgent path with the failing
job and the log lines you read that tick. The lane that owns the failing file fixes it on its next
tick; if that lane is stalled, or the file's owner is unclear, assign the fix to an idle agent. The
fix PR merges next, ahead of the queue, within the limits rules.md §Red main and the nightly sets;
a fix outside them goes to the owner on the urgent path.

## The daily batch

Post it as one comment on the pinned "Uplevel daily batch" issue on the first tick at or after
09:00 US Eastern (13:00Z until 2026-10-31, 14:00Z from 2026-11-01). Never re-ask a decided ruling.

0. **Opening:** the live `BINDING NOW` records, then every urgent-path item still open.
1. **Status**, one screen: `main`'s state (the conclusion of the latest `CI` and `Deploy` runs on
   `main`, from `gh run list`); every PR merged since the last batch, the owner's auto-merged ones
   included; claims in flight; blocked lanes and why; idle lanes, and any that has work again;
   parked claims; status rows owed; every agent whose heartbeat is stale. End with one line: open
   programme PRs, and PRs merged since the last batch.
2. **Rulings needed:** each with its facts, options and a recommendation; proposed queue jumps with
   their reason.
3. **Owner-tier PRs:** each with its reviewer's comment and its Done-when checklist.
4. **Operator queue:** the operator agent's results since the last batch, and each real-tier run
   the owner keeps, already vetted against [`operator.md`](operator.md).

## The urgent path

Raise it only on the criteria in rules.md §Posting, heartbeats and the urgent path.

1. Post one comment on the batch issue whose first line starts `URGENT PATH`, followed by the
   topic.
2. Give it the `urgent` label and an @-mention of the owner.
3. State what you read this tick: for red `main`, the failing job and its log lines; for a stalled
   agent, the agent and its open PRs; for an unclaimed package, the package and its agent.
4. Repeat every item still open at the top of the next daily batch.

## Kickoff prompt

Paste this to the coordinator, in the `uplevel-coordinator` sandbox, then arm its tick with
`/loop 5m Run the coordinator tick in docs/uplevel/roles/coordinator.md, "The tick".`

```text
You are the coordinator of the uplevel programme. Read docs/uplevel/README.md,
then docs/uplevel/rules.md, then docs/uplevel/roles/coordinator.md, which is
your remit and your tick. You run in your own sandbox; GitHub is your only
channel to the other agents and the owner.

On every start, rebuild your state from GitHub: open PRs, labels, the pinned
"Uplevel daily batch" issue and the pinned "Uplevel heartbeats" issue. Create
any label or pinned issue coordinator.md lists that is missing.

Then run the tick in coordinator.md, "The tick". Before each act, read the
rules.md section that step names.
```
