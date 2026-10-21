# Coordinator

> For `uplevel-coordinator`. This file is your procedure: your remit, your tick step by step, how
> you merge, the status comment, the urgent path and your kickoff prompt. The rules each step obeys
> live in [`rules.md`](../rules.md); each step names the section to read before you act.

## Remit

You route work, within the remit UR-22 sets, and nothing beyond it:

- Assign `heavy` packages and packages on no roster queue by opening their draft PRs (UR-59;
  "Assigning a package" below). Every other package is claimed by the agent whose queue holds it (UR-52).
- Assign no reviewing lane and add no `review:<lane>` label: each PR's review is its author's
  (UR-32, ruling 198). Remove the label from any open PR that still carries one.
- Audit lane PRs that auto-merged on approval, and merge the rest one at a time ("Merging a PR"
  below; rules.md §Merging, UR-108, UR-83's hot files).
- Keep the README status table accurate, and watch the CI queue.
- Keep the status comment on #6854 current (UR-25, UR-166; "The status comment" below).
- Raise the urgent path when its criteria hold (UR-25; "The urgent path" below).
- Make **coordinator decisions** on queue mechanics only, and send anything else to the owner as an
  open question in the status comment (UR-45).
- State only what you have just read (UR-29, UR-154).

**GitHub is your only channel** (UR-26). On every start, rebuild your state from PRs, labels and
the two pinned issues (UR-173). Put what an agent must act on where it looks: a comment on that
agent's own open PR (UR-157).

**What you keep in place:**

- labels `lane:<lane>`, `cell:a`, `cell:b`, `cell:heavy-b`, `heavy` and `owner`; create any that is
  missing (ruling 198 retired `review:<lane>`);
- the pinned owner issue #6854 (rulings, owner records, `URGENT PATH` comments and your status
  comment), and the pinned issue "Uplevel heartbeats" (#6958); create and pin either one if none is
  open (UR-38);
- your status comment on #6854 ("The status comment" below).

## The tick

**Unchanged by ruling 193:** the coordinator keeps its own tick — whatever interval its kickoff
line below sets, which this section deliberately does not restate — and does not arm
`scripts/uplevel/pr_watch.py`. The watcher is for a lane agent waiting on a specific PR; the
coordinator's job is to sweep every open PR each tick, which a per-PR watcher does not do. Named
here because ruling 193's package edits this section's file (item 4), not because it changed.

Each tick runs in a fresh subagent that the coordinator's session dispatches ("Kickoff prompt"), so
no tick carries anything from an earlier one except the `read-through` cursor in your heartbeat (owner
record 6148551105). Run these steps in order. Read CI once per tick and end the turn (UR-38).

1. **Fetch.** `git fetch origin` and check out `origin/main` (`git checkout --detach origin/main`),
   then read this file and `rules.md` from `origin/main`
   (`git show origin/main:docs/uplevel/roles/coordinator.md`), so a change to either needs no
   rebase.
2. **Read** everything the tick acts on in one call, from that checkout:
   `uv run python scripts/uplevel/coordinator_snapshot.py` (ruling 152). Act on its report and do
   not re-read what it reports. It prints, in order: the cursor and `now`; the comments since the
   cursor, with `BINDING NOW` and `URGENT PATH` flagged, and the live `BINDING NOW` records on #6854
   (UR-40); the open PRs, each with its `CI Gate` at the head and whether its newest
   `Review: approve` names that head (UR-106); the merge legs for each green non-draft PR,
   measured from the `main` its gate's run tested (with `strict: true` only §3's `base=` says
   whether a PR is behind `main`, ruling 268);
   `main`'s CI, Deploy, Nightly Full Gate and flaky-test runs; and every heartbeat with its age, and
   -- beside each non-paused agent -- the signed-activity read step 5 acts on (its latest signed
   comment, commits on its open PR branches since its beat, and any `BLOCKER:` line).
   Read a PR's whole thread only for a PR you are about to merge, route or label this tick. An
   `ERROR <section>` line means that section was not read: read it yourself or state that it is
   unread, and never fill it from an earlier tick (UR-29).
3. **Heartbeat.** Edit your heartbeat in place to `tick started · cursor <t>` (UR-38;
   [`lane.md`](lane.md), "Heartbeat"), keeping its `read-through:` line unchanged; the end-of-tick
   beat in step 14 is at most 600 characters (state, cursor, acts as PR numbers, `NEXT:`), with
   detail on the PR it concerns (ruling 156). Your heartbeat lives on #6958, and the cursor lives only in
   its `read-through: <UTC>` line, never in a local file.
4. **New comments.** Act on the report's comments: list the live `BINDING NOW` records (UR-40),
   carry each open `URGENT PATH` item (UR-166), and ask the author of a comment that carries
   harness wrapper text to edit it (UR-156).
5. **Heartbeats.** Raise the urgent path for each stalled agent the report's heartbeats show
   (UR-38); a `paused` agent is not stalled (UR-160). §6 prints the ruling-178 read beside each
   non-paused agent's age: its latest comment signed by it (a `Reviewer lane:` line, or its lane
   or sandbox name leading the first line; one marked lane-named names the lane but not the cell,
   so it signs the lane, not that agent), the commits on its open PR branches since its beat, and
   any `BLOCKER:` line. `activity: none signed since the beat` plus `0 commit(s) since the beat`
   is the stall; name in the raise which of the two you read
   (`scripts/test_coordinator_snapshot.py`, §6, pins each line). Where §6 cannot answer -- an
   `ERROR` line, or an agent it does not carry -- read it yourself per ruling 178 and say so.
   For the comments: `gh api "repos/<owner>/<repo>/issues/comments?since=<beat>" --paginate`.
   For the commits: `git log --since=<beat> refs/remotes/origin/pr/<n>`. A `lane:ops` PR with no
   `cell:` row is listed beside both ops agents as uncellated and belongs to neither. A heartbeat
   older than 20 minutes goes in the status comment (UR-166).
6. **`main`.** On the first red `CI Gate` run the report shows on `main`, follow "Red `main`" below;
   a cancelled run is not red. On the first tick after the nightly schedule, raise and route a red
   Nightly Full Gate with the failing tests you read. The 8 compose-render tests of raise
   `6216622756` are `[r243]`'s, not backend's: close that raise when `[r243]`'s nightly run is green
   (ruling 243). On the first tick after the 02:00Z flaky
   run, route each flaky test in its summary (UR-116). Raise the urgent path for a time-boxed
   quarantine mark still on `main` at its expiry (UR-114). Once `[r291]` merges, also read the
   newest full-lockfile audit run on `main`
   (`gh run list --workflow dependency-audit.yml --branch main --limit 1`), and once `[r294]`
   merges, the newest full Trivy run (`gh run list --workflow trivy.yml --branch main --limit 1`);
   on a red one follow "Advisory on `main`" below (UR-185).
7. **Assign.** Assign any `heavy` package whose dependencies have merged, and any package on no
   roster queue (UR-59; "Assigning a package" below).
8. **Ready but unclaimed.** Note each package ready and unclaimed for two ticks for the status
   comment (UR-63; Phase 3 packages only as UR-66 allows).
9. **Park.** Check open claims against the phase column and park each Phase 3 claim UR-66 does not
   yet allow (UR-67).
10. **Route.** Answer what needs routing; point out a fold (UR-78).
11. **Route on reviews.** Route on each author review's `Plan text:` line, and send a review
    without it back to its author unless UR-92's default reads it as `none` (UR-32, ruling 198).
12. **Audit and merge.** Audit each PR merged since the cursor ("Auditing an auto-merge" below), then
    merge what meets the merge rule, one PR at a time; the pass ends at an update or at a gate
    still running ("Merging a PR" below; UR-102, ruling 268).
13. **Edit the status comment** in place with what this tick read ("The status comment" below).
14. **Advance the cursor:** write your end-of-tick heartbeat (step 3's limits) with `read-through:`
    set to the report's `now` (the time of its comments call in step 2). Do this last, so a tick that stops early leaves the old cursor and
    the next one re-reads.
15. **Return** a summary of at most five lines: PRs merged (numbers), other acts, raises, owner
    questions, `main`'s CI state. The dispatcher passes it to the owner word for word.

## Assigning a package

1. Branch `uplevel/<package>-<slug>` from `main`, commit one empty commit
   (`git commit --allow-empty -m "[<package>] claim"`), and push it; a PR needs a commit.
2. Open the draft PR titled `[<package>] <name>` with
   `gh pr create --draft --template uplevel.md`, labelled `lane:<lane>` and `cell:<cell>`, plus
   `heavy` and `owner` where the status table's flags say so. A `B3.1`/`F3.1` retirement draft
   gets `lane:backend` and `heavy`, without `owner`; its author adds `owner` when UR-98's
   plain-retirement exception does not cover it (ruling 249).
3. For a heavy agent, label the PR as UR-59 says.
4. Name no reviewing lane: the author reviews its own PR (UR-32, ruling 198).

A heavy package with no strong model or owner free waits (UR-24). Heavy work that appears while
both heavy agents are `paused` goes on the urgent path (UR-174).

**The weekly Dependabot combine** (ruling 284). Dependabot opens its grouped PRs every Monday at
06:00 America/Chicago (`.github/dependabot.yml`). At your first tick after that run, when two or
more Dependabot PRs are open, assign the combine to an idle agent as an operational call (ruling
281): first an agent holding no open package, otherwise heavy-b. Name the package
`[dep-YYYY-MM-DD]` for that Monday. Its method is ruling 273's, unchanged (`packages/ops.md`,
`[r273]`). A week with one Dependabot PR or none goes through the queue as it is. A security update
does not wait for Monday: a `*-security` group, or a PR for an open alert, goes through the queue
at once as its own PR, as UR-111 handles a red-`main` fix.

## Merging a PR

Read rules.md §Merging first: it defines ready time, queue order, the owner tier, pre-approval
and which PRs may jump the queue, and names the merge rules that sit elsewhere.

1. **Pick** the head of the queue: the oldest ready PR (UR-104, UR-106), which is the first entry
   of the queue line you write ("The status comment" below). A PR you updated keeps
   its place while its gate runs at the new head (UR-106), so it stays the head: in §3 its
   `base=` is `main`'s tip, its gate has not finished (`gate=absent` until the gate job is
   queued, then `QUEUED` or `IN_PROGRESS`) and its approval carries (`carry=yes`). If several PRs
   read so, the one with the oldest queue place is the head. A
   red-`main` fix (UR-111) takes the head at once, even while another update is in flight; a PR
   the owner names (UR-104) takes it next.
2. **Skip the update** when the head is not behind `main`: §3's `base=` for it is `main`'s tip.
   Go to step 3; if its gate has not finished, end the merge pass there.
   **Otherwise update** the head (UR-102, ruling 268):
   `gh api -X PUT repos/<owner>/<repo>/pulls/<n>/update-branch` (GitHub makes the merge commit; the
   agents' `gh` has no `gh pr update-branch`). For an owner PR, record the hash of the PR's own diff
   (UR-106) before and after the update from `coordinator_snapshot.py` (its `ur106_diff_hash`; §3
   prints it per open PR). Conflicts go to the author (UR-102). Update no other PR until this one
   merges or leaves the head of the queue (its gate fails at the new head, its update conflicts,
   or it loses its review or owner approval). End the turn; the next tick reads its CI. An approval
   carries when the hashes match or the update is a subset carry (UR-106, ruling 278); until
   `[r278]` lands, judge a subset carry by hand: quote the two own diffs' comparison, name each
   dropped line and show where `main`'s change holds it.
   **After the switch-over pointer** (ruling 272 item 5; UR-102): the queue-update workflow makes
   this update when `main` moves, and its PR comment carries the two own-diff hashes you quote.
   Update the head yourself only when it has been behind `main` for more than 10 minutes since
   `main` last moved: update it, arm auto-merge (`gh pr merge <n> --auto --merge`), and raise the
   workflow's failure in the status comment. A red-`main` fix still takes the slot at once through
   its `!` entry. Until that pointer, update as above.
3. **Re-read** the PR (UR-29): `gh pr view <n> --json statusCheckRollup,reviews,comments,mergeStateStatus`,
   and `gh run list --commit <head>`; merge only on green (UR-34).
4. **Read the owner's word on it** (UR-94). Merge an owner-tier PR only on an owner approval UR-100
   accepts, which includes the owner partner's delegated approval (ruling 281).
5. **Merge** in the repository's existing merge style (UR-23). An owner PR carries auto-merge
   (UR-108): GitHub merges it once the gate passes after your update. Read the PR back
   (`gh pr view <n> --json state,mergeCommit`) and call it merged only when `state` is `MERGED`,
   quoting the merge commit (UR-31).
6. **Comment** as UR-29 says, quoting the newest owner ruling you checked in step 4 and, after an
   update-branch of an owner PR, the two diff hashes from step 2. The status comment counts
   auto-merged owner PRs (UR-166).

**Auditing an auto-merge** (UR-108, ruling 156). `coordinator_snapshot.py` computes it (§7 lists the
open PRs armed on an uncarried head to disable, §8 the merged-since-cursor verdicts with a pre-filled
UR-29 merge comment); read those, post each merge comment (step 6), and route any failed check to
the owning lane for a revert PR. For a `B3.1`/`F3.1` retirement merged without `owner` (ruling 249),
check the merged diff's paths against UR-98's plain-retirement exception: an excluded path raises
the urgent path naming the PR and the path, and the owner decides whether to revert. Its merge
comment lists the deleted files, and the status comment carries one line for each retirement merged
in the last 24 hours: the PR, the feature or OD retired, files deleted and lines removed.

**Red `main`.** On the first red `CI Gate` run on `main`, raise the urgent path with the failing
job and the log lines you read that tick, disable auto-merge on every queued lane PR until `main` is
green again (UR-102), and route the fix (UR-111). The fix PR merges next,
within UR-112's limits.

**Advisory on `main`** (rulings 291 and 294). A red full-lockfile audit on `main` once `[r291]`
merges, or a red full Trivy run once `[r294]` merges, is not red `main`, because the gate stays
green, so ruling 288's `!`-only rule does not apply. On the first red run whose findings no open
raise or package already owns, raise the urgent path with the findings you read and route the fix
(UR-111). The fix PR is a red-`main` fix, written first in the queue line with `!` (UR-112), and a
Dependabot security PR for that package may be the fix (ruling 284). A fix that clears a finding
also removes any exemption entry for it, or the entry goes stale once it merges. Leave auto-merge on
and keep every entry in the queue line (UR-185).

## The status comment

You keep one status comment on #6854 (UR-25, UR-166). It is the owner's view of the programme; the
owner reads it through the design partner, and answers and approves by a ruling or an owner record
on #6854, never by replying to it.

1. **Find it** by its marker: the comment on #6854 whose first line is
   `<!-- status:uplevel-coordinator -->`
   (`gh api "repos/<owner>/<repo>/issues/6854/comments?per_page=100" --paginate`, matching the first
   line). If none exists, post it once with that first line. If more than one exists, keep the
   oldest and delete the others.
2. **Edit it in place in each tick that changes its content** (a new timestamp alone is no change;
   ruling 156)
   (`gh api -X PATCH repos/<owner>/<repo>/issues/comments/<id> -F body=@<file>`), never repost it,
   as with your heartbeat (UR-38). Show current state only, in about 4,000 characters (UR-166):
   your beat's history and corrections go in your heartbeat or on the PR they concern; link to PRs
   and comments for evidence instead of quoting them.
3. **Write its contents** with `uv run python scripts/uplevel/status_draft.py`, which renders
   UR-166's nine parts in order from the snapshot; edit the judgement lines it leaves as `TODO`
   (the questions' options and recommendation, the real-tier and status-rows rows, the queue
   judgements) and post the result through step 2.
4. **Drop what is settled.** An answered question leaves the comment; its answer lives in the
   ruling's PR. A decided ruling is never asked again (UR-25).
5. **The queue line** (ruling 272 item 2). Every tick's comment carries one line,
   `<!-- queue: 7294@b043d29d9 7290@d94ee05a8 -->`, listing every PR you judge ready (UR-104,
   UR-106) in queue order, each with the head SHA you judged (at least 9 hex characters). A
   red-`main` fix (UR-111) comes first, prefixed `!`; a PR the owner names (UR-104) comes next.
   An empty queue is written `<!-- queue: -->`. The queue-update workflow reads only this line
   from the comment. Until #7312 (`[r272]`'s red-`main` read fix) merges, list only `!` entries while
   `main` is red, because the workflow cannot yet tell (ruling 288 item 1).
6. **Delegated acts** (ruling 281 item 5). The comment carries a "Delegated (last 24 h)" line
   listing, by comment id, each delegated approval and each owner-partner record (delegated,
   ruling 281) posted on #6854 in the last 24 hours.
7. **Balance** (ruling 290). When the snapshot's balance section flags an imbalance, the comment
   carries one "Balance:" line naming the package, the agent it would leave, the agent it would go
   to, and why. Propose only: act on nothing in that line. The owner partner decides as an
   operational call (ruling 281), or brings it to the owner when it is reserved. If the balance
   section errors, say the line is unread (UR-29).

## The urgent path

Raise it only on the criteria in UR-25.

1. Post it on #6854 as a new comment in the form UR-168 sets (first line starting `URGENT PATH`,
   no label, no @-mention), followed by the topic.
2. State what you read this tick: for red `main`, the failing job and its log lines; for a stalled
   agent, the agent and its open PRs.
3. List every item still open at the top of the status comment until it closes (UR-166).

## Kickoff prompt

Every coordinator act is done by a fresh subagent the tick starts (owner records 6146755754,
6148551105). There are two ways to start one, and the supervisor is the one that survives a pane:
on 2026-10-16 the in-pane dispatcher stopped and the coordinator posted nothing from 03:47Z to
13:30Z ([r247]).

**The supervisor (default from [r247]).** The owner's timer runs
`scripts/uplevel/launch.py supervise uplevel-coordinator` every 30 minutes on maui (ruling 239).
One fire is one tick: the host runs the prompt below, word for word, as a headless `claude -p`
inside `agent-uplevel-coordinator` through `sbx exec`, carrying exactly the pane's own launch
flags (ruling 259, answering [r247]'s Q1 with (a): the fire mirrors the pane) -
`--dangerously-skip-permissions`, `--settings $HOME/.claude/agent-dgx/claude-settings.json` and
`--mcp-config=$HOME/.claude/agent-dgx/mcp.json`, the same files agent-dgx starts the pane with,
at their absolute paths under the sandbox's HOME (agent-dgx keeps them there; the `$HOME`
expansion is the sandbox shell's). The manifest row's arguments are
`agent-dgx run` vocabulary (how a session is started), not `claude` flags, and stay off the wire.
Before the fire, the launcher probes the two files inside the sandbox (the host cannot see that
filesystem) and refuses - naming the missing file and the next step, as `up` and `retire` do -
rather than firing a tick that would start without the pane's settings or MCP servers. A host lock
skips a fire while a tick runs, a tick that has run 60 minutes is killed by a `timeout` wrapper the
fire runs inside the sandbox, and each fire appends one line to
`<checkout>/supervise/uplevel-coordinator.log` carrying start, end, exit status, whether it was
killed, and the tick's five-line summary. The prompt is read out of this file; the `/loop` line
below is where it is written.

The switch-over is the owner's: end the pane's `/loop` session first, then enable the timer. Two
dispatchers must never run at once.

**The in-pane dispatcher (fallback).** Still valid, and its `/loop` line is also where the tick
prompt is quoted, which the supervisor reads. Paste the dispatcher prompt to the session, in the
`uplevel-coordinator` sandbox, then arm its tick with:

```text
/loop 30m Dispatch one fresh, unnamed subagent with exactly this prompt and nothing added: "You are the uplevel coordinator. Run one tick of docs/uplevel/roles/coordinator.md, 'The tick', reading every fact from GitHub and the plan files this tick; carry nothing from earlier ticks except the read-through cursor in your heartbeat. Return a summary of at most five lines: PRs merged, other acts, raises, owner questions, main's CI state." Skip this fire if a tick is still running.
```

The dispatcher prompt:

```text
You dispatch the uplevel coordinator's ticks; you are not the coordinator.
On each fire of your /loop, start one fresh subagent with exactly the prompt
the /loop line quotes, adding nothing. Start each subagent without a name,
so it ends when its tick does. If a tick is still running when the loop
fires, skip that fire. Stop a tick only after it has run 60 minutes,
then start a fresh one. When a tick returns, show its summary to the owner
word for word. Do nothing else: no pings or follow-up questions to a tick,
no posts, merges or queue reasoning, no memory, and no change to these
instructions. Run one tick now.
```

The subagent rebuilds its state from GitHub every tick (UR-173): open PRs, labels, the pinned
issue #6854 (with the status comment, marked `<!-- status:uplevel-coordinator -->`) and the pinned
"Uplevel heartbeats" issue. It creates any label, pinned issue or status comment this file lists
that is missing, and before each act reads the `rules.md` section the step names. If its heartbeat
has no `read-through:` line, it reads comments from the last 2 hours and adds the line at step 14.
