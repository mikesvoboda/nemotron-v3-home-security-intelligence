# Lane and heavy agents

> For the lane agents (`uplevel-backend`, `uplevel-frontend`, `uplevel-ops-a`, `uplevel-ops-b`,
> `uplevel-docs`) and the heavy agents (`uplevel-heavy-a`, `uplevel-heavy-b`). This file is your
> procedure: your tick, claiming, building, self-review, reviewing other lanes' PRs, posting, and
> your kickoff prompt. The rules each step obeys live in [`rules.md`](../rules.md); each step names
> the section to read before you act. Your packages are in `packages/<lane>.md`.

## Who takes what

**The roster.** Each sandbox and its queue, in order. An agent claims the next package in its own
queue (UR-52); the coordinator assigns only `heavy` packages and packages on no queue (UR-59).
`scripts/uplevel/sandboxes.toml` declares the same sessions. Phase 3 entries wait as UR-66 says.
The owner sets these queues; a change is a ruling. Ruling 175 rebalanced `F2.3` so every lane
works on it: packages a ruling routed after a lane's `F2.3` rows wait for them, and routed bug
fixes (`[r130b]`, `[r130f]`) keep their place. Ruling 184 gave the heavy agents FE-4 and OP-1.

| sandbox               | model     | queue                                                                                                                                                                                                           | review label      |
| --------------------- | --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------- |
| `uplevel-coordinator` | fast      | routing (`roles/coordinator.md`)                                                                                                                                                                                | none              |
| `uplevel-backend`     | fast      | `[r149d]`, `[r129]`, `[r130b]`, `[r94]`, `[r95]`, `F2.3` API batches, `B3.3`; cells A and B for Phase 3's deletions                                                                                             | `review:backend`  |
| `uplevel-frontend`    | fast      | `[r165a]`, `[r130f]`, `[r144n]`, `[r148b]`, `[r148c]`, `[r149e]`, `[r132]`, `[r133]`, `[r134]`, `F2.3` UI (FE-1, FE-2, FE-3; reviews every batch), `[r168]`, `[r173]`, `[r148a]`, `R2b` records, `F3.2`, `F3.3` | `review:frontend` |
| `uplevel-ops-a`       | fast      | `[r189]`, `OB.3`, `F2.3` UI (OP-2, OP-4; OP-1 to heavy-b, ruling 184), `[r164a]`, `O2.5`, `[r96i11]`, `[r184]`, `O3.1`, `O3.2`, `O3.3`                                                                          | `review:ops-a`    |
| `uplevel-ops-b`       | fast      | `[r157]`, `[r141]` follow-up (ruling 145), `[r151]`, `[r149b]`, `[r149f]`, `F2.3` UI (OP-3, after `[r157]`'s runner is ready for the owner), `[r181]`, `[r172]`, `O3.4`, `O3.5`, `O3.7`; `OB.4` on its trigger  | `review:ops-b`    |
| `uplevel-docs`        | fast      | `[r165b]`, `F2.3` UI batches (DO-2, DO-3; FE-4 to heavy-a, ruling 184), `W3.1`, `W3.2`, `W3.3`, `W3.4`                                                                                                          | `review:docs`     |
| `uplevel-heavy-a`     | strongest | heavy-b's queue while it is out of service (ruling 190): #7155, OP-1's seeded rows, then `B2.3`; then `heavy` PRs without `cell:heavy-b`: `B3.1` with `F3.1`, `B3.2`, `O3.6`, Phase 4 design sessions           | none              |
| `uplevel-heavy-b`     | strongest | out of service (ruling 190); its queue is heavy-a's until the owner restarts it with a record                                                                                                                   | none              |
| `uplevel-operator`    | fast      | real-tier runs: rows `awaiting real tier` (`B1.1`, `F1.2`, `O1.11`, `O2.2`), `F2.3`'s per-batch runs (ruling 103), ruling 142's verdict spread, `O2.5`                                                          | none              |

**Split lanes.** A cell splits a lane between two agents along file sets that do not overlap. Each
cell claims from its own roster queue (UR-52).

| lane    | cell A                                                                                                        | cell B                                                           |
| ------- | ------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| backend | the VLM path: `backend/services/vlm_*`, `constrained_decoding.py`, `backend/evaluation/`, the circuit breaker | API and auth: `backend/api/`, middleware, `backend/main.py`      |
| ops     | runtime: `ai/`, compose, `setup.py`, `setup_lib/`, the fake stack and harness                                 | tooling: `scripts/`, `.github/`, the mutation scorer, `archive/` |

Ops runs as two cells. Backend runs as one agent until Phase 3 and splits into cells A and B for
Phase 3's deletions. Frontend and docs run as one cell each; in Phase 3 the frontend may split into
retirement (`F3.1`) and reachability (`F3.2`, `F3.3`).

**Heavy agents.** Take the `heavy` draft PRs the coordinator assigns you, and follow the owning
lane's package text, file ownership and kickoff line below (UR-59), and the `00-audit.md` sections
the package cites. You have no review label.

## The tick

The owner arms it with `/loop 15m Run the agent tick in docs/uplevel/roles/lane.md, "The tick".`
Run these steps in order. Read CI once per tick and end the turn (UR-38).

1. **Read the tick in one call.** Run

   ```bash
   uv run python scripts/uplevel/lane_tick.py --sandbox <your-sandbox>
   ```

   (`scripts/uplevel/lane_tick.py`; `scripts/test_lane_tick.py` pins every line it prints.) It is
   read-only: it does the `git fetch`, reads this file and `rules.md` from `origin/main` itself (so
   a change to either needs no rebase), and prints, in tick order: your heartbeat id, age and prose;
   the coordinator's age, with the UR-162 raise named when one is owed; disk use of `/` and
   `/var/lib/docker`, pointing at UR-180's cleanup ORDER above 90% (never a routine full prune,
   ruling 176); the live `BINDING NOW` records the ruling map does not yet carry (ruling 177's
   filter, applied at the source -- the 48-hour window is never fetched unfiltered); the PRs
   labelled `review:<lane>` and your own open PRs, each with head, merge state, `CI Gate` at that
   head (re-read past 100 check runs; in-flight jobs named when it is still running), commits behind
   `main`, and comments/reviews since your beat; and the next claimable roster package (UR-52). An
   `ERROR <section>` line means that section was not read: read it yourself or say it is unread, and
   never fill it from an earlier tick (UR-29). A `NOTE no package file for lane <lane>` is the
   roster's answer for a lane with no package file (operator, heavy, coordinator), not a fault.
   Then act on the printed `BINDING NOW` records that name your lane or all agents and whose state
   does not already hold; one already carried out is a no-op (UR-40, rulings 163, 170, 177).

2. **Heartbeat.** Edit your heartbeat in place ("Heartbeat" below) from what the digest read, and
   keep your disks under 90% (UR-180). Read the coordinator's age from the digest; if it is older
   than 20 minutes with no live `URGENT PATH` on record, follow "Stale coordinator" below.
3. **Reviews first** (UR-32): clear the PRs labelled with your review label ("Reviewing another
   lane's PR" below), reading each one's whole thread only now. Heavy agents skip this step.
4. **Your own open PRs** (UR-35): read the full thread of a row the digest shows with new comments,
   reviews or a `DIRTY`/red gate; fix what is red, answer what is requested, and rebase what
   conflicts with `main` (what a new head resets: UR-106). Before you push to a PR on auto-merge,
   run `gh pr merge <n> --disable-auto` (UR-108). The digest is this step's one CI read (UR-38).
5. **Continue your package,** or take the next one ("Claiming a package" below).
6. If none of these has work, say so in one line and end the turn.

## Heartbeat

Keep your heartbeat comment on the pinned issue "Uplevel heartbeats" as UR-38 says; post it once
if you have none. It is two lines, and at most 600 characters in all (UR-155); detail goes on the
PR it concerns. Only when you are blocked, add a third line, `BLOCKER: <one line>` (for example
`BLOCKER: /var/lib/docker 100%, UR-180 cleanup failed`; ruling 181):

```text
<!-- heartbeat:<sandbox> -->
<sandbox> · <HH:MMZ, read from date -u> · idle | working #<n> | waiting on <what> | paused · <why>
```

Find the issue with `gh issue list --state open --search "Uplevel heartbeats in:title"`, find your
comment by its first line, and edit it with
`gh api -X PATCH repos/<owner>/<repo>/issues/comments/<id> -f body=<the two lines>`.

**Before a long step.** Before any step you expect to run over 15 minutes (a local test or golden
run, a UR-89 self-review subagent), edit your heartbeat to
`<sandbox> · <HH:MMZ> · working #<n> · <step> since <HH:MMZ>`. It is a beat, not a wait (UR-38).
(ruling 178)

**Stale coordinator.** When the coordinator's heartbeat is older than 20 minutes, act as UR-162
says: one plain `URGENT PATH` comment on #6854 per hour, no label and no @-mention (UR-168). The
owner restarts the coordinator (UR-163).

**Paused.** A heavy agent whose queue is empty posts the final `paused` heartbeat and ends its turn
(UR-160). When the owner restarts it, it runs its kickoff line and `/loop 15m` (UR-174).

## Claiming a package

Read rules.md §Claiming and assigning work first.

1. **Look for an assignment**: an open draft PR the coordinator created, labelled with your lane and
   cell (`heavy` for a heavy agent); continue on its branch. Heavy agents stop here (UR-59).
2. **Choose** the next package in your roster queue as UR-52 and UR-65 say, or, when your queue has
   nothing you can claim, from another queue in your lane's area as UR-52 says; a Phase 3 package
   only as UR-66 allows. Claim your
   next package on the tick its dependency lands (UR-54).
3. **Check** that nobody holds it: `gh pr list --state open --search "[<package>] in:title"`.
4. **Claim** it before writing any code (UR-53, UR-54): branch `uplevel/<package>-<slug>` from
   `main`, commit nothing but an empty commit (`git commit --allow-empty -m "[<package>] claim"`),
   push it, and open a draft PR titled `[<package>] <name>` with
   `gh pr create --draft --template uplevel.md --label lane:<lane>`.
5. **Release** a claim you abandon by closing its draft PR with a comment saying why (UR-55).

## Building a package

Read rules.md §Building a package first: one package per PR, the hot-file rules, and the contract.

1. Write the failing test first (UR-69).
2. Build until the package's Done when holds. Push your branch after every commit (UR-28).
3. Fill the PR body from the template and write commit subjects as UR-10 (contract rule 2) says.
   Edit the `AGENTS.md` lines that describe what you changed (UR-81).
4. Set the package's README status row in the same PR, with the operator's command in the PR's
   "Real tier" section if it needs one (UR-10, contract rule 5).
5. When the plan does not answer a question, stop and report it under "Questions for the owner" in
   the PR body (UR-10, contract rule 4).
6. Authors of `F2.2`, `O2.3` and R2's list of modules serving no feature dispatch
   `codebase-archaeologist` on their scope (UR-95).

**Self-review.** Run the fresh-context self-review UR-89 describes, record its findings in the PR,
then mark the PR ready once its code is complete. A Done-when clause that only a CI run shows (a
draft skips every job but the gate) is ticked from the first ready run, naming it; a red run is
fixed on the ready PR, and the reviewer approves only with those clauses green (ruling 161).

## Reviewing another lane's PR

Read rules.md §Reviewing first.

1. List your queue: `gh pr list --state open --label review:<your label>`.
2. Review each PR independently (UR-91). Write its `Plan text:` line as UR-92 says. For a
   security-and-auth package, dispatch `security-auditor` on the diff (UR-95, UR-96).
3. Post the review as a PR comment in this form:

   ```text
   Review: approve | changes requested
   Reviewer lane: <lane>
   Done when: <each clause> — observed | not observed (where)
   Contract: rules 1-5 — ok | <which rule, why>
   Plan text: none | <which kind of plan text it changes (rules.md §Authority: rulings, plan text and IDs), and where>
   Notes:
   ```

4. On `approve` of a lane-tier PR (its `Plan text:` is `none` or a UR-47 lane-review kind, and no
   other UR-98 trigger applies), run `gh pr merge <n> --auto --merge` and add `Auto-merge: on` to the
   review's `Notes:` (UR-108, ruling 156). Owner-tier PRs get no auto-merge from you.
5. Remove the review label.

## Posting

Every comment, PR body and review follows UR-10 (contract rule 2: your own text only), UR-31
(state only what you have just read) and UR-155 (the post budget).

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

Claim the next package on your roster queue as lane.md, "Claiming a package",
says; a heavy agent takes the package the coordinator assigns it. Build it as lane.md,
"Building a package", says. Reviews come first, then the new comments on your
own open PRs, then your package. Before each act, read the rules.md section the
step names.

Then run the tick in lane.md, "The tick".
```

**Per-lane lines.** Find the sentence your kickoff line carries and follow its paragraph.

- **"You are the backend lane."** Your packages are in `docs/uplevel/packages/backend.md`; your
  review label is `review:backend`. You own `backend/`. The cross-lane rule (UR-9) governs every
  other file you touch.
- **"You are the frontend lane."** Your packages are in `docs/uplevel/packages/frontend.md`; your
  review label is `review:frontend`. You own `frontend/` and `docs/reference/feature-inventory.md`.
  The cross-lane rule (UR-9) governs every other file you touch.
- **"You are cell A of the ops lane."** or **"You are cell B of the ops lane."** Your packages are
  in `docs/uplevel/packages/ops.md`; claim from your cell's roster queue (UR-52). Your review label
  is `review:ops-a` or `review:ops-b`. You own `ai/`, compose, `scripts/`, `.github/`, `setup.py`,
  `setup_lib/`, root config and `archive/`. The cross-lane rule (UR-9) governs every other file you
  touch. Real-model checks are the operator's (UR-15).
- **"You are the docs lane."** Your packages are in `docs/uplevel/packages/docs.md`; your review
  label is `review:docs`. Read the AGENTS.md standard at `docs/developer/agents-md-standard.md`
  after the packages file, and apply it (UR-88). Start Phase 3 work as UR-68 allows. You own
  `docs/`, every `AGENTS.md` (UR-81), `llms.txt`, `mkdocs.yml`, the root markdown files and the
  AGENTS.md validator.
- **"You are uplevel-heavy-a."** You run on the strongest available model and take only `heavy` PRs
  without `cell:heavy-b` ("Heavy agents" above). For each package, read the packages file and the
  line above of the lane that owns it, and follow them. You have no review label.
- **"You are uplevel-heavy-b; take only heavy PRs labelled cell:heavy-b."** As `uplevel-heavy-a`,
  for the PRs labelled `heavy` and `cell:heavy-b`.
