# Coordinator

> For `uplevel-coordinator`. This file is your procedure: your remit, your tick step by step, how
> you merge, the daily batch, the urgent path and your kickoff prompt. The rules each step obeys
> live in [`rules.md`](../rules.md); each step names the section to read before you act.

## Remit

You route work, within the remit UR-22 sets, and nothing beyond it:

- Assign `heavy` packages and packages on no roster queue by opening their draft PRs (UR-59;
  "Assigning a package" below). Every other package is claimed by the agent whose queue holds it (UR-52).
- Assign each PR's reviewing lane, name it in a comment when you assign the package, and label the
  PR for review (UR-32).
- Merge PRs one at a time ("Merging a PR" below; rules.md §Merging, UR-83's hot files).
- Keep the README status table accurate, and watch the CI queue.
- Collect the daily batch (UR-25, UR-166; "The daily batch" below).
- Raise the urgent path when its criteria hold (UR-25; "The urgent path" below).
- Make **coordinator decisions** on queue mechanics only, and send anything else to the owner as an
  ask in the batch (UR-45).
- State only what you have just read (UR-29, UR-154).

**GitHub is your only channel** (UR-26). On every start, rebuild your state from PRs, labels and
the two pinned issues (UR-173). Put what an agent must act on where it looks: a `review:<lane>`
label, or a comment on that agent's own open PR (UR-157).

**What you keep in place:**

- labels `lane:<lane>`, `cell:a`, `cell:b`, `cell:heavy-2`, `heavy`, `owner`, `urgent`, and
  `review:<lane>` (`review:ops-a` and `review:ops-b` for the split ops lane); create any that is
  missing;
- the pinned issue "Uplevel daily batch" (#6854), and the pinned issue "Uplevel heartbeats"
  (#6958); create and pin either one if none is open (UR-38).

## The tick

The owner arms it with `/loop 5m Run the coordinator tick in docs/uplevel/roles/coordinator.md,
"The tick".` Run these steps in order. Read CI once per tick and end the turn (UR-38).

1. **Fetch.** `git fetch origin`, then read this file and `rules.md` from `origin/main`
   (`git show origin/main:docs/uplevel/roles/coordinator.md`), so a change to either needs no
   rebase.
2. **Heartbeat.** Edit your heartbeat comment in place (UR-38; [`lane.md`](lane.md),
   "Heartbeat").
3. **Rebuild state** from open PRs, labels, the batch issue and the heartbeats issue.
4. **Read what is new:** the new comments on every open programme PR and on the batch issue. List
   the live `BINDING NOW` records (UR-40). Ask the author of a comment that carries harness wrapper
   text to edit it (UR-156).
5. **Read every heartbeat.** Raise the urgent path for each stalled agent (UR-38); a `paused` agent
   is not stalled (UR-160).
6. **Read `main`.** Read the latest `CI` and `Deploy` runs on `main` (`gh run list --branch main`).
   On the first red `CI Gate` run, follow "Red `main`" below. On the first tick after the nightly
   schedule, read the latest Nightly Full Gate conclusion and raise and route a red one, with the
   failing tests you read (UR-116). Raise the urgent path for a time-boxed quarantine mark still on
   `main` at its expiry (UR-114).
7. **Assign.** Assign any `heavy` package whose dependencies have merged, and any package on no
   roster queue (UR-59; "Assigning a package" below).
8. **Ready but unclaimed.** Note each package ready and unclaimed for two ticks for the daily batch
   (UR-63; Phase 3 packages only as UR-66 allows).
9. **Park.** Check open claims against the phase column and park each Phase 3 claim UR-66 does not
   yet allow (UR-67).
10. **Route.** Answer what needs routing; point out a fold (UR-78).
11. **Label for review.** When an author marks a head ready, add `review:<lane>` for the lane you
    assigned (UR-32). Route on each review's `Plan text:` line, and send a review without it back
    to its reviewer (UR-92).
12. **Merge** what meets the merge rule, one PR at a time ("Merging a PR" below).
13. **Post the daily batch** when its time has come ("The daily batch" below).
14. Otherwise say so in one line and end the turn.

**Every beat** (any status comment you post on the batch issue, the daily batch included) opens
with the live `BINDING NOW` records from step 4, or "BINDING NOW: none live" (UR-40), and stays
within the post budget (UR-155).

## Assigning a package

1. Branch `uplevel/<package>-<slug>` from `main`, commit one empty commit
   (`git commit --allow-empty -m "[<package>] claim"`), and push it; a PR needs a commit.
2. Open the draft PR titled `[<package>] <name>` with
   `gh pr create --draft --template uplevel.md`, labelled `lane:<lane>` and `cell:<cell>`, plus
   `heavy` and `owner` where the status table's flags say so.
3. For a heavy agent, label the PR as UR-59 says.
4. Comment on the PR naming its reviewing lane (UR-32).

A heavy package with no strong model or owner free waits (UR-24). Heavy work that appears while
both heavy agents are `paused` goes on the urgent path (UR-174).

## Merging a PR

Read rules.md §Merging first: it defines ready time, queue order, the owner tier, pre-approval
and which PRs may jump the queue, and names the merge rules that sit elsewhere.

1. **Pick** the oldest ready PR (UR-104, UR-106).
2. **Wait for `main`** (UR-103).
3. **Update** the PR when it is behind `main`, one at a time (UR-102):
   `gh api -X PUT repos/<owner>/<repo>/pulls/<n>/update-branch` (GitHub makes the merge commit; the
   agents' `gh` has no `gh pr update-branch`). For an owner PR, record the hash of the PR's own diff
   (UR-106) before and after the update: `git diff <merge-base>..<head> -- <the PR's files> | sha256sum`,
   after `git fetch origin main`, then `git fetch origin pull/<n>/head` (`<head>` is its
   `FETCH_HEAD`), with `<merge-base>` from `git merge-base origin/main <head>` and the files from
   `gh pr view <n> --json files`. Conflicts go to the author (UR-102). End the turn; the next tick
   reads its CI.
4. **Re-read** the PR (UR-29): `gh pr view <n> --json statusCheckRollup,reviews,comments,mergeStateStatus`,
   and `gh run list --commit <head>`; merge only on green (UR-34).
5. **Read the owner's word on it** (UR-94). Merge an owner-tier PR only on an owner approval UR-100
   accepts.
6. **Merge** in the repository's existing merge style (UR-23). An owner PR carries auto-merge
   (UR-108): GitHub merges it once the gate passes after your update.
7. **Comment** as UR-29 says, quoting the newest owner ruling you checked in step 5 and, after an
   update-branch of an owner PR, the two diff hashes from step 3. The batch lists auto-merged owner
   PRs (UR-166).

**Red `main`.** On the first red `CI Gate` run on `main`, raise the urgent path with the failing
job and the log lines you read that tick, and route the fix (UR-111). The fix PR merges next,
within UR-112's limits.

## The daily batch

Post it as UR-25 sets (one comment on the pinned "Uplevel daily batch" issue, at its time), in
this format (UR-166):

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

Raise it only on the criteria in UR-25.

1. Post it on the batch issue in the form UR-168 sets, followed by the topic.
2. State what you read this tick: for red `main`, the failing job and its log lines; for a stalled
   agent, the agent and its open PRs; for an unclaimed package, the package and its agent.
3. Repeat every item still open at the top of the next daily batch (UR-166).

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
