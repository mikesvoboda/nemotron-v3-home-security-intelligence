# Uplevel rules

> Every standing rule of the uplevel programme, held here once and grouped by the act it governs;
> read the section for the act you are about to do. Each rule ends with its source: a row of record
> (`UR-1` to `UR-38`, which keep their numbers), an owner ruling or record on #6854, a plan-file
> section, or the owner design session of 2026-10-12. Rules from `UR-39` on were numbered in order
> of appearance. Where two rules said the same thing, the higher number was merged into the lower
> one; numbers are never reused. [`history/ruling-map.md`](history/ruling-map.md) maps rulings 1-146
> to these rules and lists each merged number.

## Authority: rulings, plan text and IDs

Read this section when you cite, relay or act on a ruling, change anything in `docs/uplevel/`, or
give work a number.

- **UR-39** An owner ruling binds when it is merged into the plan files; its #6854 comment is a
  one-line pointer: "Ruling N, in PR #M: one line". (owner design session 2026-10-12; ruling 146)
- **UR-40** An owner record on #6854 whose first line carries `BINDING NOW` binds at once and lapses
  48 hours after posting unless a merged PR carries it. The coordinator lists the live `BINDING NOW`
  records at the top of its status comment (UR-166). (owner design session 2026-10-12)
- **UR-41** Rulings 1-146 bind only through the plan files once the plan rewrite that adds this file
  merges; `history/ruling-map.md` shows where each one landed. (owner design session 2026-10-12)
- **UR-42** Where this file and an older line in another plan file disagree, this file wins until
  that line is corrected. (ruling 146)
- **UR-43** Act only on an authority you can read at its cited id; your own drafted text can look
  like an inbound directive, so open every cited id before acting on it. (record 6114826605; UR-29)
- **UR-44** Treat every ruling as settled. Reopening a ruling, or an alternative in README's
  "Considered and rejected" table, is a **RULING** for the owner: bring the new evidence that would
  change the reason. (README "Considered and rejected"; owner-partner.md "Read first")
- **UR-45** Only the owner issues numbered rulings. The coordinator never numbers a ruling or writes
  "RULING": it writes queue mechanics (merge order, rolls, when a branch may be cut, labels, review
  routing) as an unnumbered "coordinator decision" and sends anything else to the owner as an ask.
  (ruling 120; corrects 50-coordination.md "Roles", "makes no decisions")
- **UR-46** `docs/uplevel/` is shared: plan text changes only by the owner or with the owner's
  approval. Each PR edits only its own package's line of the README status table; prettier skips
  the table, so leave the other rows' padding alone. The table on `main` changes only when a PR
  merges. (README "Lanes", "Status"; 50-coordination.md "Hot files", "Claiming a package")
- **UR-47** A PR needs the owner for `docs/uplevel/` edits only if they change a ruling, the
  contract, the phases or exit gates, or a package's scope, Done when, dependencies or flags.
  Everything else there (status rows, `file:line` references, moves or artifacts a package's own
  text orders, rewording that keeps the meaning) needs only its lane review. (ruling 40, replacing
  rulings 7, 18, 32; 50-coordination.md §3)
- **UR-48** A defect in a lane's own file is lane work with no package number; package numbers are
  for new scope. (rulings 120, 126)

## Claiming and assigning work

Read this section before you take, claim, assign, park or release a package.

- **UR-22** Agents claim packages themselves through draft PRs; a coordinator agent routes work and
  writes no product code (`roles/coordinator.md`). Routing is: assigning packages and reviewing
  lanes, merging, keeping the README status table accurate, watching the CI queue, keeping the
  status comment, raising the urgent path, and making unnumbered coordinator decisions on queue
  mechanics (UR-45). The coordinator acts on nothing beyond that remit and never provisions a
  sandbox. (UR-22; 50-coordination.md "Roles"; coordinator kickoff prompt; ruling 120)
- **UR-24** `heavy` packages go only to the strongest available model or to an owner pairing; the
  fast local model takes the rest. The status table's `heavy` flag marks them, and every Phase 4
  design session is heavy; with neither a strong model nor the owner free, a heavy package waits.
  (UR-24; 50-coordination.md "Heavy packages")
- **UR-35** Agents read the new comments on their own open PRs before resuming a package; an owner
  ruling or a requested change there comes before new work. (UR-35)
- **UR-51** Work the phases in order. Inside a phase, packages are independent unless a package
  names a dependency; the ops background packages (`OB.n`) may run in any phase after Phase 1.
  (10-backend.md, 20-frontend.md, 30-ops.md headers)
- **UR-52** Each agent works its own queue in the roster (`roles/lane.md` "Who takes what"), the ops
  cells included. On any tick where it has no open package, it claims the next package in its queue
  that is `not started`, unclaimed, not `heavy`, and whose dependencies have merged (UR-54). A
  ruling-ordered fix (`[rNNN]`) sits in the queue of the lane its ruling names, in the order the
  roster gives. A package is claimed or unclaimed; "parked unchanged" is not a state. (owner design
  session 2026-10-12; lane kickoff prompts; rulings 82, 120; record 6083435595)
- **UR-53** Claim a package before writing any work: an empty commit on branch
  `uplevel/<package>-<slug>` from `main`, pushed, and a draft PR titled `[<package>] <name>` opened
  with the `uplevel.md` template and `lane:<lane>`. The open draft PR is the claim. (ruling 39 item
  M; 50-coordination.md "Claiming a package")
- **UR-54** Depend only on merged work: a dependency is met when its PR has merged to `main`, a
  merge as `awaiting real tier` included, and you claim your next package on the tick it lands.
  Branch from `main`, never from another agent's open branch. (ruling 82; 50-coordination.md
  "Claiming a package")
- **UR-55** Release a claim you abandon by closing its draft PR with a comment saying why.
  (50-coordination.md "Claiming a package")
- **UR-56** One package, one claim PR, except `F2.3`, where each agent carries all its area batches
  in one draft claim PR. (ruling 97; 50-coordination.md "Claiming a package")
- **UR-59** The coordinator assigns only `heavy` packages and packages on no roster queue: it opens
  the draft PR on a branch holding one empty commit, labelled `lane:<lane>` and, where they apply,
  `cell:<cell>`, `heavy` and `owner`. A `heavy` PR labelled `cell:heavy-2` belongs to
  `uplevel-heavy-2`; every other belongs to `uplevel-heavy`. To give a heavy agent a package the
  status table does not mark `heavy`, label its PR `heavy` with no cell label; the row keeps its
  flags. A heavy agent takes only the PRs assigned to it and follows the owning lane's package text,
  file ownership and kickoff line. (rulings 50, 53; owner design session 2026-10-12;
  50-coordination.md "Two heavy sandboxes", "Where agents run")
- **UR-63** The status comment lists every package whose dependencies have merged, whose row is not
  `done` or `awaiting real tier`, and that has stayed unclaimed for two coordinator ticks, with the
  agent whose queue holds it. (ruling 82; owner design session 2026-10-12)
- **UR-64** A lane with no work keeps ticking, says so in one line and ends the turn; the
  coordinator lists idle lanes in the status comment and says when one has work again. (ruling 43;
  50-coordination.md "The tick")
- **UR-65** When every remaining package in a lane's current phase waits on another lane, the lane
  takes the next phase's first package whose dependencies have landed. (README "The path"; lane
  kickoff prompts)
- **UR-66** No Phase 3 package starts before `R2` is `done`, except a package scoped only to
  `R2a`-ruled features and modules (once #6980 and the plan PR carrying ruling 86 have merged) or to
  an `R2b` round's rulings (once that round's record PR merges). A lane out of other work says so in
  its heartbeat (the status comment lists it, UR-64) and does not start Phase 3. (rulings 41, 86,
  135; corrects the kickoff prompts' "never start Phase 3 before R2 is done")
- **UR-67** Each coordinator tick parks any open Phase 3 claim the rule above does not allow (draft,
  first body line "Parked by owner ruling 54 until R2 is done.") and lists it in the status comment.
  (rulings 54, 86)
- **UR-68** The docs lane starts Phase 3 work on a lane's directories only after that lane's Phase 3
  packages are `done`. In Phase 4 it opens a package only on a trigger: a validator failure, or a
  report of a stale claim. (README "Lanes"; 40-docs.md "Phase 3", "Phase 4")

## Building a package

Read this section while you write a package's code, tests, docs and PR.

- **UR-69** The rules in the root `AGENTS.md` apply unchanged: TDD (write the failing test first),
  hooks never bypassed, podman, ports from `.env`, coverage floors never lowered. (README "Read this
  first"; lane kickoff prompts)
- **UR-70** Read the `00-audit.md` sections your package cites and re-measure any **[A]** number
  before acting on it. Read `01-mutation-policy.md` whenever your package deletes, merges or writes
  tests. (README "Read this first")
- **UR-10** The five-rule contract every package inherits. (UR-10; README "The contract")
  1. **Outcome, not target:** a package ends on a **Done when** that a reviewer can observe (a test
     that passes, a command's output, a file that no longer exists). Numbers are measured and
     reported, never climbed.
  2. **Evidence in the PR:** open every package PR with `gh pr create --template uplevel.md`, and
     put each command and its output in the body. Commit subjects stay at 72 characters or fewer;
     ledger files take no rows from this programme; comments, PR bodies and reviews carry only the
     agent's own text, never its harness's framing of a subagent's or another session's output.
     (ruling 56)
  3. **Tools live in the repo:** commit every script, fixture and harness a package relies on. Work
     from `/tmp` or a home directory does not count as evidence.
  4. **Rulings come in batches:** a phase's RULING items are settled at the phase boundary. When a
     package meets a question its plan does not answer, stop and report the question; never widen
     your own scope. (lane kickoff prompts)
  5. **One status table:** the PR that finishes a package sets its README row to `done` with the PR
     number and marks done any `17-action-plan.md` entry it closes. A package needing real-tier
     numbers merges with the operator's command in its body at `awaiting real tier`, and the
     operator posts the output and sets `done` (UR-146). A phase exits when all its rows say `done`, except
     packages a ruling leaves open: `O2.4` and `B2.3` (ruling 117) and `O2.5` (ruling 144, which
     gates only ruling 127's twelve real-tier rows) do not gate Phase 2's exit and may finish
     alongside Phase 3; the coordinator does not hold Phase 3 for them. (rulings 117, 144)
- **UR-76** Mark package steps the house way: **MEASURE** produces the number and puts it in the PR;
  **DECIDE** chooses on evidence and records why in the PR; **RULING** stops and asks the owner.
  (README "The contract")
- **UR-77** One package per PR. The one exception is a Phase 4 package: a test-only PR consolidates
  the tests of the modules it will touch under `01`'s zero kill-loss protocol, changing no
  production bytes, and a second PR builds or refactors. (README "The path"; 10-backend.md "Phase
  4")
- **UR-78** When one lane has two or more draft PRs fixing the same tool, fold them into one PR
  before any goes ready. Separate packages, or a package plus an unrelated fix, never combine; the
  coordinator may point out a fold as a coordinator decision, and the lane makes it. (ruling 136)
- **UR-79** Each Phase 4 package opens with a design session against the code that remains; a
  feature package's design goes to `docs/uplevel/4n-<feature>.md`, copied from
  `templates/feature-design.md`. (README "The path"; 10-backend.md, 20-frontend.md "Phase 4")
- **UR-9** Lanes that own files (four), under the cross-lane rule: the PR that removes
  or changes a thing does so everywhere at once, whichever lane owns the files (a dead setting
  leaves `config.py`, `.env.example` and the compose `environment:` block in one PR). The lane
  owning the primary change leads; a package spanning lanes names its parts and their order. (UR-9;
  README "Lanes")
- **UR-81** The lane whose PR changes behaviour updates the docs and `AGENTS.md` lines that describe
  it in the same PR; docs reviews such edits against the standard only if asked. The docs lane owns
  every `AGENTS.md` except those lines. (README "Lanes"; ruling 121)
- **UR-82** Touch `synthbench/` only under the cross-lane rule, when a deletion removes something
  synthbench imports; the synthbench workstream continues alongside this programme. (README "Lanes")
- **UR-83** Hot files; the coordinator sequences their merges: (50-coordination.md "Hot files")
  - `docs/openapi.json`, `frontend/src/types/generated/api.ts`: regenerate after rebasing, never
    hand-merge;
  - `backend/core/config.py`, `.env.example`, compose files: small hunks, rebased immediately before
    merge, merged one at a time;
  - `.pre-commit-config.yaml`, `backend/main.py`: small hunks, merged one at a time;
  - `scripts/retired_paths.txt`: append-only;
  - `docs/reference/feature-inventory.md`: during `F2.3` edit only your own batch's rows; frontend
    owns the rest (ruling 87);
  - `.github/suppression-baseline.json`, `.secrets.baseline`: regenerate after rebasing, immediately
    before merge; never hand-merge a count (two PRs adding one marker each write the same number,
    and git merges them silently).
- **UR-88** The AGENTS.md standard has one home, `docs/developer/agents-md-standard.md`; apply it
  and restate none of it elsewhere. In an `AGENTS.md`, write what an agent cannot find by looking
  and leave inventories to the code. (40-docs.md "The AGENTS.md standard"; docs kickoff prompt)

### Product decisions in force

Constraints on what you build; reopening one is a ruling (UR-44).

- **UR-18** `ai-vlm` starts by default; backend readiness and a UI banner report the engine's
  runtime state; GPU-less development uses the fake VLM through an explicit overlay. (UR-18)
- **UR-84** Out of scope: rewriting git history, renaming `setup.py`, and widening frontend Stryker
  beyond its three utility files. (README "Rulings of record")
- **UR-85** Production re-ID stays OSNet-AIN on the CPU (`REID_BACKEND=local`) until a later ruling.
  Re-ID may depend on the GPU only once a proven GPU path exists, and then no CPU fallback is
  required. (ruling 107)
- **UR-86** Triton stays the one model server: any new GPU-served model joins Triton, and its `nv_*`
  metrics stay (OD-39). (ruling 89)
- **UR-87** Future plans go in `docs/superpowers/<date>-<slug>/`; `docs/plans/` is frozen history,
  and a dated plan created anywhere else is a violation (OD-33). (ruling 89)
- **UR-21** `AGENTS.md` files live only at boundaries, listed with a reason; the validator fails on
  dead references and on files outside the list. (UR-21)
- **UR-12** Inbound webhooks: **implement** (an arming module with webhook and MQTT adapters,
  designed after Phase 3); until then they answer `501` and validate keys against
  `settings.api_keys`. (UR-12)

## Reviewing

Read this section before you self-review your own PR or review another lane's.

- **UR-32** Reviews come first. The coordinator assigns each PR's reviewing lane by rotation, never
  the author's own, preferring the lane that consumes the change, and names it when it assigns the
  package. It labels the PR `review:<lane>` (`review:ops-a`/`review:ops-b` for ops) each time the
  author marks a head ready; a lane agent clears its label's PRs before starting or resuming a
  package. (UR-32; 50-coordination.md §2)
- **UR-89** Before marking a PR ready, the author dispatches a fresh-context subagent given only the
  package text, the diff and the PR body, to check each Done-when clause against the evidence, the
  contract, the cross-lane parts and the hot-file rules; the author fixes or answers each finding
  and records them in the PR. (50-coordination.md §1)
- **UR-91** The reviewer runs the same checks independently, posts the review as a PR comment in the
  form `roles/lane.md` gives (the owner's account cannot approve its own PRs), and removes the
  label. Each new head's merge resolution is reviewed again. (50-coordination.md §2; ruling 39 item
  G)
- **UR-92** Every review carries `Plan text: none | <which kind in UR-47 it changes, and where>`,
  written `none` only after reading every `docs/uplevel/` hunk. The coordinator routes on it
  (anything but `none` makes the PR owner-tier) and asks the reviewer for a missing line rather than
  judging the diff. (ruling 40)
- **UR-94** Before merging a PR or posting a verdict on it, the coordinator and every reviewer open
  every owner ruling, record and pointer that names it, on the PR and on #6854, not only approval
  comments; if any bars the head, the merge or verdict waits. (ruling 145)
- **UR-95** `.claude/agents/` holds two read-only subagents, adapted from
  `msitarzewski/agency-agents`. The reviewer of a security-and-auth package dispatches
  `security-auditor` on the diff; the authors of `F2.2`, `O2.3` and `R2`'s module list dispatch
  `codebase-archaeologist`. Findings are claims until the dispatcher reproduces them; quote only
  reproduced ones and say which you set aside and why. (ruling 45; UR-29)
- **UR-96** If your session cannot list a project subagent, dispatch a fresh-context subagent with
  the agent file's body and say so. A new reproduced high or critical finding returns the PR to its
  author; medium and low ones do not block. (ruling 48)

## Merging

Read this section before you update, queue or merge a PR, or decide whether it needs the owner.
Three merge rules sit elsewhere: green is UR-34, the owner-ruling check before a merge is UR-94,
and the re-read and merge comment are UR-29.

- **UR-23** A PR merges on green CI plus an approving review from another lane's agent, after the
  author's own fresh-context self-review; owner-tier PRs also need the owner. The coordinator
  merges: when `CI Gate (Required Checks)` is green at its head, its review says approve and, in
  the owner tier, the owner has approved, keeping the repository's existing merge style. (UR-23;
  50-coordination.md §4)
- **UR-98** Owner tier: these PRs also need an owner approval recorded on #6854 (a ruling or owner
  record); the status table's `owner` flag marks the packages that carry it. (50-coordination.md
  "Review and merge" §3; ruling 40)
  - security and auth;
  - risk acceptance (dismissing an alert or a finding);
  - production safety;
  - privileged host tooling (the launcher and anything run with host privileges);
  - destructive work;
  - plan text, as UR-47 defines it;
  - any PR with an entry under "Questions for the owner".
- **UR-99** Once the owner answers a PR's "Questions for the owner" and they leave its body, they no
  longer make it owner-tier; it merges on lane review and green CI unless another owner-tier trigger
  applies. (rulings 4, 8, 10, 11, 108)
- **UR-100** An agent writes approvals only in its own role. The coordinator merges an owner-tier PR
  only on an owner approval recorded on #6854 (a ruling or owner record), or one given elsewhere
  once quoted in the status comment with the owner's words and time. (50-coordination.md "Trust
  model"; UR-27, UR-29)
- **UR-101** A ruling ending with the exact line "Pre-approved: merges on lane review and green CI."
  pre-approves the follow-up it specifies: the coordinator merges it without the owner when the lane
  review states the diff does that and nothing more and `CI Gate` is green at its head; if the
  reviewer cannot state that, the PR comes to the owner. Never pre-approved: destructive work
  (`B3.1`, `F3.1`, `B3.2`), security or auth or plan text beyond the ruling, or a PR with owner
  questions. (ruling 84)
- **UR-102** `main` keeps "require branches to be up to date". Only the coordinator updates a queued
  PR, one at a time, with `gh api -X PUT repos/<owner>/<repo>/pulls/<n>/update-branch`, and merges
  one PR at a time; authors rebase their own PRs to resolve conflicts. The owner revisits the
  requirement if the open-PR count in the status comment keeps growing. (rulings 19, 27;
  50-coordination.md §4)
- **UR-104** The queue runs oldest ready first, and a PR waiting on its author cannot hold the slot.
  Only an owner ruling or a red-`main` fix moves a PR ahead; activity on a thread, newness or the
  coordinator's own reading of the critical path do not. To propose a jump, the coordinator asks in
  the status comment with the reason. A ruling's order for an agent's work is not a merge order, and
  a PR's named place in a ruling lasts only until its head moves, unless the owner names it again.
  GitHub's merge queue is unavailable on this user-owned repository. (rulings 21, 26, 83, 101; owner
  design session 2026-10-12 dropped the wait for `main`'s own run after each merge, rulings 63
  and 101)
- **UR-106** A PR is ready at the latest of: `CI Gate` passing at its head, the approving review of
  that head, and, in the owner tier, the owner's approval. An update-branch with `main` keeps the
  queue place, the review and the owner's approval if the PR's own diff
  (`git diff <merge-base>..<head> -- <the PR's files>`) is byte-identical before and after; an
  author commit, a conflict fix included, resets all three. A red run or re-opened review takes the
  PR out, and the gate must be green at the new head before merge. (rulings 26, 55, 59; record 6128195816; owner design
  session 2026-10-12)
- **UR-107** Never combine PRs already in the queue: reviews and carry proofs are keyed to heads.
  (ruling 97)
- **UR-108** Owner PRs carry auto-merge and join the same queue; the coordinator updates one in its
  turn, and GitHub merges it once the gate passes. No owner watcher updates branches. (ruling 15)

## Red main and the nightly

Read this section when `CI` or `Deploy` fails on `main`, the Nightly Full Gate is red, or you are
fixing either.

- **UR-111** On the first red `CI Gate` run on `main`, unless an open package already owns that
  failure, the coordinator raises the urgent path with the failing job and the log lines it read.
  The lane owning the failing file fixes it on its next tick; if that lane is stalled or the owner
  unclear, the coordinator assigns an idle agent. (ruling 83)
- **UR-112** A red-`main` fix merges next, ahead of the queue, on lane review and a green `CI Gate`,
  without the owner. It may change tests, CI or the least product code the failure points to; it
  never deletes, skips or `xfail`s a test, raises a limit or baseline, or touches an owner-tier
  area, and a fix beyond that goes to the owner on the urgent path. (ruling 83)
- **UR-113** A follow-up a ruling orders is not a red-`main` fix: it takes the normal queue and
  review. (ruling 145)
- **UR-114** Only the owner may authorize skipping a test, for example a time-boxed `test.fixme`
  quarantine with an expiry; the red-`main` permission never covers one. No lane extends a
  quarantine mark, and if a mark is still on `main` at its expiry the coordinator raises the urgent
  path. (ruling 125)
- **UR-115** A pytest worker count is a scheduling setting, not a limit, so the red-`main` limits do
  not cover it: the nightly runs `-n auto` like PR CI, and `pyproject.toml`'s `-n 8` stays. (ruling 113)
- **UR-116** On the first tick after the nightly schedule, the coordinator reads the latest Nightly
  Full Gate conclusion; a red one is raised and routed like red `main`, fixed within the same
  limits, and does not freeze the merge queue. (ruling 109)

## CI and shared jobs

Read this section before you change a workflow, a CI job, a hook or the gate.

- **UR-34** CI is green only when the required check `CI Gate (Required Checks)` is present and
  passed at the PR's head. A check list with no failures is not green: a workflow file GitHub
  rejects fails with no jobs and leaves no check behind, so also read `gh run list --commit <head>`.
  Before pushing a change to `.github/workflows/*.yml`, run
  `docker run --rm -v "$PWD":/repo -w /repo rhysd/actionlint:latest -shellcheck= -pyflakes= .github/workflows/*.yml`
  and compare its findings with `main`'s; a YAML parse does not check GitHub's expressions. (UR-34;
  50-coordination.md "Review and merge" §4, "Hot files"; coordinator kickoff prompt)
- **UR-119** Branch protection keeps one required check, `CI Gate (Required Checks)`; a new check
  runs inside it rather than becoming a separate required check. (ruling 9)
- **UR-37** The gate checks what the hooks check: the repository's pre-commit hooks run on each PR's
  changed files inside `CI Gate (Required Checks)` (`O1.12`). A hook left out of CI is listed with
  its reason and ruled by the owner; the four hooks ruling 39 (item E) excluded from the gate's hook
  stage stay out of it, with the suppression census delegating to `check-mock-spec`. (UR-37;
  ruling 39)
- **UR-121** In a shared job of `.github/workflows/ci.yml`, the only allowed edit is appending a
  single entry, such as one test-script path, to an existing list in a step. Anything else (a new
  step, new logic, or a changed flag, condition or command) goes in its own job or its own workflow
  file; review enforces this until a check exists. (ruling 137; corrects 50-coordination.md "Hot
  files", `ci.yml` row)
- **UR-122** An edit an owner ruling orders is never barred by UR-121. (ruling 145)
- **UR-123** The repository uses one prettier version, the one `frontend/package-lock.json`
  resolves. The gate's hooks job reports a formatting disagreement as a named finding listing the
  files; it never rewrites. (ruling 24)
- **UR-124** The scoped `scripts.validate_docs` directory list in `ci.yml` widens only in the PR
  that fixes that directory's citations, never before. Its AST, code-match, cross-ref and staleness
  levels stay out of CI until separately decided. (ruling 140)

## Test timing gates

Read this section when a test is slow, a timing gate is red, or you would change a test's timeout or
the gates.

- **UR-125** The real-sleep gate fails a unit test over 4.0 s only when the breach reproduces: the
  gate re-runs that one test once, in the same job, and the run is red only if the re-run also
  breaches; a test that passes on its re-run is listed as a warning with both timings. Any unit
  test over 1.5 s is listed as a warning that never fails the run. There is no cross-run allowance
  and no baseline file. (rulings 93, 122; owner design session 2026-10-12, pass 2 Q9; supersedes
  ruling 74)
- **UR-126** A reproduced breach is red, and the remedy is in the test, not the gate.
  `SLOW_TEST_PATTERNS`, each entry with its measured note, is the only channel for a genuinely slow
  test; `@pytest.mark.slow` is read by neither gate. (ruling 122; owner design session 2026-10-12,
  pass 2 Q9)

## Test tiers and the real tier

Read this section when you write, consolidate or delete tests, flip a row on test evidence, or run
or write anything for the real tier. Who holds the GPU, and which runs the owner keeps, is UR-30.

### Mutation testing

- **UR-1** The mutation score is a diagnostic with a no-regression floor on shipping code. The 85%
  target is retired. (UR-1)
- **UR-2** The mutation campaign holds after M54 (PR #6844). (UR-2)
- **UR-3** The mutation scored set is what the reachability check reaches. (UR-3)
- **UR-4** The floor is enforced by a weekly alert (never blocking) and by before/after evidence on
  PRs that delete or merge tests. (UR-4)
- **UR-5** A "drop" is split by path: zero kill-loss on test-only PRs; a per-module drop beyond a
  measured noise band on the weekly run; the global score is informational. (UR-5)
- **UR-6** A kill counts only through the interface bar; mutants killed only by below-bar tests may
  be surrendered as recorded accepted survivors. (UR-6)
- **UR-7** One home per kind of evidence: PR body, CI-written weekly history (compacted), one
  accepted-survivors file; the L ledger takes no new mutation rows. (UR-7)
- **UR-16** Test consolidation is just in time inside feature packages, plus a background track.
  (UR-16)

### Golden paths and witnesses

- **UR-14** "Works" is proven by golden paths: green on the fake stack in CI, then confirmed on the
  real tier. (UR-14)
- **UR-127** Golden paths mock nothing: a guard fails any `golden` Playwright spec that calls
  `page.route` on `/api` or `/ws`. External-interface golden paths are pytest specs in
  `backend/tests/golden/`, outside the default test paths, run by `scripts/feature-check.sh`.
  (20-frontend.md `F2.1`; 10-backend.md "Phase 4")
- **UR-128** A test witnesses only if it executed and passed: a golden run with zero tests turns
  Feature Check red, and a skipped or quarantined spec, or a CI log that cannot contain the run, is
  no witness. An inventory row flips only on a run where its test executed and passed. (rulings 114,
  123, 125)
- **UR-129** A spec counts as `passed` only if its final attempt passed and was not skipped; any
  spec with a failed attempt is `flaky`, whatever its final outcome. The gate keeps reading
  Playwright's exit code. (ruling 126)
- **UR-130** On the real tier, golden specs check the pipeline (an event stored with a verdict; the
  UI shows exactly what the API holds), not the model's verdict. Verdict-dependent checks run on the
  fake tier only and skip on the real tier with a reason. (ruling 142)
- **UR-131** The golden stage runs inside the official Playwright container
  (`mcr.microsoft.com/playwright:v<version>-noble`), its tag read from `frontend/package-lock.json`,
  on the harness's engine, with no browser-install step. A blocked registry or download host is
  named in the failure, never worked around. (rulings 116, 143)

### The real tier

- **UR-15** The real tier is operator-run on the GB300 by a committed script; no self-hosted runner.
  Real-model checks run there through the operator, never from CI or GitHub: a lane agent writes the
  real-tier command into its PR's "Real tier" section, and the operator runs it. (UR-15; README
  vocabulary "operator"; ops kickoff prompt; 30-ops.md `O2.2`)
- **UR-133** Every real-tier command runs on a test deployment, never the live stack: its own
  compose project, generated env file (never the checkout's `.env`), remapped ports, volumes and
  fresh camera directory, sharing only read-only model weights. A run that would touch the live
  database, camera folder or containers stops instead. (ruling 22; README vocabulary; operator.md
  "The one rule")
- **UR-134** A test deployment always runs with `ORCHESTRATOR_ENABLED=false` and no container-engine
  socket in any container, and no writable bind mount outside the run's own directory. (30-ops.md
  `O2.2`; operator.md "The owner on the host")
- **UR-135** Tear down every run, also after a failure, only with
  `<compose> -p <run project> down -v`, never a bare `down`; on the `agent-gpu` path also
  `agent-gpu stop` and `agent-gpu rm` your containers until `agent-gpu ps` lists none. (operator.md
  "The agent-gpu path", "The owner on the host"; 30-ops.md `O2.2`)
- **UR-136** The real tier (`--real`) serves the real VLM, the production q4km pin, through
  `agent-gpu` with the fake detector; it refuses where `agent-gpu` is absent and takes
  `FEATURE_CHECK_ENGINE=docker` or `podman`. (ruling 66)
- **UR-137** Serve only the production pin, `qwen3vl-8b-instruct-q4km/` from the model library, and
  stop unless its `sha256sum` and `/props`' `model_path` match the pin; add no `--mount` at or under
  `/srv/agent-models`. (operator.md "The agent-gpu path"; 30-ops.md `O1.10`; owner-partner.md
  "Guardrails")
- **UR-138** When the `agent-gpu` runner refuses a run, post the `agent-gpu status` output on the
  row's PR (the coordinator lists the run in the status comment) and stop; never lower `--vram` to
  get admitted. (record 6116458014; operator.md "The agent-gpu path")
- **UR-140** The operator writes no product code and changes no command. When a command fails for a
  reason its PR did not anticipate, post the output and the exit code; the lane agent revises it.
  (ruling 22; operator.md "When something goes wrong", kickoff prompt)
- **UR-141** Every number in a real-tier results comment comes from output in that comment, headed
  with the date, the commit and the hardware, with the teardown evidence. (operator.md "Posting
  results"; UR-29)
- **UR-142** Name every store a result depends on by path and `sha256sum`; a store only in a
  sandbox's broker directory (`/agents/<sandbox>/gpu/out` on the host) is flagged on the PR for the
  owner to copy to a durable path under `/synthbench` before a report depends on it. Agents never
  copy a store or re-root `SYNTHBENCH_ROOT` around a mount; they post the error and stop. (rulings
  49, 57; operator.md "Posting results")
- **UR-143** Restore no live data yourself. If a live container stopped or restarted or a volume
  vanished, start what stopped, say so on the PR, raise the urgent path and leave the row
  `awaiting real tier`; the package is not done until a clean run. Live data that looks wrong goes
  on the urgent path, and you investigate it with the owner. (operator.md "When something goes
  wrong")

## Statuses, rows, the inventory and R2

Read this section when you set a status row, edit the feature inventory or the `R2` sheet, or reason
about phase exits and `R2`. Who edits which status row is UR-46; the row a finishing PR sets, and
when a phase exits, are UR-10 (contract rule 5).

- **UR-144** Statuses: `not started`, `in progress`, `awaiting real tier`, `done`. `in progress` is
  only for a package the owner ruled to span several PRs (`F2.3`, `R2b`'s rounds); any other work in
  progress shows as an open draft PR titled `[<package>] …`, and its row reads `not started`.
  (ruling 138; README "Status")
- **UR-146** The operator sets a row from `awaiting real tier` to `done` in a one-line follow-up PR,
  or asks the lane agent to. (operator.md "Posting results")
- **UR-147** Flags: `heavy` (UR-24) and `owner` (the owner's approval before merge, UR-23,
  UR-98). A Phase 4 package gets its own row when it opens: the PR that opens it adds the row under
  the matching `*` line. (README "Status")
- **UR-13** The owner rules per feature, from a verified feature inventory; modules follow their
  feature's ruling; modules serving no feature come to the owner as one list. (UR-13)
- **UR-148** `R2` is held in two parts: `R2a` (the sheet as it stood) and `R2b` (after `F2.3`);
  `R2b` runs in rounds, and `R2` is `done` only when `R2b`'s last round is recorded. `R2b` rules on
  re-ID from the CPU evidence. (rulings 86, 117, 127)
- **UR-149** The frontend lane records each `R2` session or round in one PR: the rulings and
  priorities into the inventory's ruling column, the OD rulings into
  `docs/vss-integration/17-action-plan.md`, and the recorded part's status row. (README "The path";
  20-frontend.md "Record R2"; ruling 135)
- **UR-151** A `half-built` row goes to the `R2b` list, and the owner decides at `R2b` whether and
  when it is fixed; nobody else creates a fix package for it unless the owner orders the fix (as rulings 129 and 130 did). (ruling 120)
- **UR-152** "Half-built" includes a break at the UI end. The `R2` sheet's §1 rules by cause, each
  row's id cell listing its inventory ids. (ruling 59; README vocabulary "half-built")
- **UR-153** A row demoted only because the CI stack cannot reach it returns to `unverified`, its
  note saying why, and `F2.3` reaches it by the real tier or a seeded golden path; a row is ruled
  only if it fails once reachable, and that failure is a demotion in a later `R2b` round. (ruling 127)

## Posting, heartbeats and the urgent path

Read this section before you post any comment, review, heartbeat, status comment or urgent item.

- **UR-31** Every agent, not only the coordinator, states only what it has just read: each commit,
  PR, file, test result and question it cites comes from output it ran in the same turn. (UR-31)
- **UR-29** The coordinator states only what it has just read (UR-31). Before each merge it re-reads
  the PR (`gh pr view <n> --json statusCheckRollup,reviews,comments,mergeStateStatus`). Whenever it
  acted on a PR (updated, re-ran or merged it) it posts one short merge comment quoting the merge
  rule's evidence: each check's conclusion, the approving review, any owner approval, the newest
  owner ruling it checked (or "no owner ruling names this PR"), and, after an update-branch of an
  owner PR, both diff hashes. An owner PR that auto-merges with no coordinator act gets no comment.
  An owner approval counts as UR-100 says. (UR-29; rulings 17, 145; record 6128195816; owner design
  session 2026-10-12)
- **UR-154** When a command fails or its answer is unclear, say that instead of stating a fact; read
  times from `date -u` or omit them, and treat GitHub's `created_at` as the record. (coordinator
  kickoff prompt; owner-partner.md "Guardrails")
- **UR-155** Heartbeats, beats, verdicts and lane notes run about 1,500 characters: what I read,
  what I did, what comes next. Evidence goes in a collapsed `<details>` block or a link to the job
  log, not in the body. (ruling 146)
- **UR-156** The coordinator asks an author to edit a comment that carries harness wrapper text
  (contract rule 2). (ruling 56)
- **UR-157** Agents read GitHub only when their prompt sends them there: put what an agent must act
  on where it looks, a `review:<lane>` label or a comment on that agent's own open PR. (coordinator
  kickoff prompt; UR-35)
- **UR-36** Every agent runs on a `/loop` tick that checks GitHub — coordinator 5 minutes, lanes and
  heavy 15, operator 30 (`roles/coordinator.md`, `roles/lane.md` and `roles/operator.md`, "The
  tick"). GitHub stays the only channel between agents; the owner re-arms ticks weekly and after a
  restart. Before arming a tick, list the agent's scheduled tasks and arm a new one only if none is
  listed, so ticks never run twice; a recurring `/loop` expires after seven days and a restart,
  resume or `/clear` drops it. (UR-36; 50-coordination.md "Keeping ticks alive")
- **UR-38** No agent waits inside a turn on CI, a check run, a watcher or a sleep: it reads once,
  reports and ends the turn. Each tick edits its own heartbeat on the pinned "Uplevel heartbeats"
  issue; a stalled agent goes to the owner on the urgent path (`roles/lane.md`, "The tick").
  (UR-38; ruling 64)
  - **Ticks.** Long work inside a turn is fine; waiting is not. A `/loop` tick's prompt re-runs
    verbatim and fires only between turns: a busy agent gets it once, when its turn ends, and
    missed ticks do not pile up. Read CI once per tick, report what you see and end the turn; the
    next tick reads it again. (50-coordination.md "The tick")
  - **Heartbeat.** Each agent keeps one heartbeat comment on that issue (first line
    `<!-- heartbeat:<sandbox> -->`, then the one-line status `roles/lane.md` gives), edited in place
    each tick, never reposted; extras are deleted, and the coordinator creates and pins the issue
    if missing. (rulings 77, 85)
  - **Stalled.** An agent is stalled when its heartbeat is older than three of its intervals (45
    minutes for lane and heavy agents, 90 for the operator) and it has pushed no commit and posted
    no comment since. The coordinator raises the urgent path for it, naming the agent and its open
    PRs. (ruling 64; 50-coordination.md "Stalled agents")
- **UR-160** A heavy agent whose queue is empty posts a final heartbeat
  `paused · queue empty (ruling 88)` and ends its turn, and the owner stops its loop. When the owner
  stops an agent, the owner's session may write its `paused` heartbeat. An agent whose heartbeat
  reads `paused` is not stalled and gets no assignment. (ruling 88; record 6103795550)
- **UR-162** A lane that reads the coordinator's heartbeat older than 20 minutes checks #6854 for an
  `URGENT PATH · coordinator stale` comment in the last hour; if there is none, it posts one
  (heartbeat age, read time, nothing more) in UR-168's form. (rulings 64, 81; owner design session
  2026-10-12, pass 2 Q8; corrects 50-coordination.md "Stalled agents")
- **UR-163** Recovery of a stalled agent is the owner's, with no watchdog agent: Esc in the agent's
  pane, a catch-up prompt that names its open work, and a new tick only if the agent lists none
  scheduled. No agent reaches into another's sandbox. (ruling 64; 50-coordination.md "Stalled
  agents"; owner design session 2026-10-12)
- **UR-25** The owner works from one status comment the coordinator keeps on #6854; the urgent
  path is for what cannot wait for it. (UR-25; owner design session 2026-10-12, pass 2 Q8)
  - **The status comment** is one comment on the pinned issue #6854 whose first line is
    `<!-- status:uplevel-coordinator -->`. The coordinator edits it in place every tick, like a
    heartbeat, and never reposts it, linking rather than quoting. It carries UR-166's list
    and never re-asks a decided ruling. It has no fixed posting time. The owner answers questions
    and approves owner-tier PRs through the design partner, as a ruling or an owner record on
    #6854, never by replying to the status comment. (ruling 29; owner design session 2026-10-12,
    pass 2 Q8)
  - **The urgent path** is only for a security exposure, anything touching or threatening the live
    deployment, `main` red (`CI` or `Deploy` failing, from the first red `CI Gate` run), a stalled
    agent, or another case a rule here sends to it. (UR-38; ruling 83)
- **UR-166** The status comment (UR-25; procedure in `roles/coordinator.md`, "The status comment")
  holds what needs the owner or signals trouble, in this order: the live `BINDING NOW` records
  (UR-40) and every open `URGENT PATH` item; `main`'s state (green, or red with the failing job);
  open questions for the owner, each with its facts, its lettered options and the coordinator's
  recommendation; owner-tier PRs ready for the owner's approval, each with its reviewer's verdict;
  real-tier runs only the owner can make (UR-30) and operator results waiting on the owner; status
  rows owed; stalled agents and heartbeats older than 20 minutes; packages ready but unclaimed
  (UR-63), idle lanes (UR-64) and parked claims (UR-67); and one closing line of counts: open
  programme PRs, and PRs merged since the newest owner ruling pointer or owner record on #6854,
  auto-merged ones included. Merges stay a count and claims in flight are not listed. The comment
  is edited in place, so UR-155's length does not bind it. An answered question leaves the
  comment; its answer lives in the ruling's PR. (rulings 17, 19, 43, 54, 81; owner design session
  2026-10-12, pass 2 Q8 and the final-verify follow-up)
- **UR-168** The urgent path stays on GitHub: a plain comment on #6854 whose first line starts
  `URGENT PATH`, with no label and no @-mention (agents post with the owner's own token, so neither
  would notify the owner). There is no push channel and no second account; the owner's design
  partner checks #6854 for `URGENT PATH` comments at the start of every session. (ruling 81;
  50-coordination.md "Where agents run"; owner design session 2026-10-12, pass 2 Q8)

## Agents, sandboxes and models

Read this section when you start, restart, pause or provision an agent, or touch a sandbox, the GPU
or an agent's memory.

- **UR-26** The coordinator runs in its own sandbox; every agent runs in its own clone-mode sandbox,
  created by an owner-run launcher at phase boundaries; GitHub is the only channel between them.
  UR-28 says how. Provisioning stays with the owner: no agent holds `agent-dgx` or `sbx`, and the
  sandbox launcher (`scripts/uplevel/launch.py`) is a host-side tool only the owner runs. Never run
  `agent-dgx help` or `agent-dgx ls`; `agent-dgx` reads an unknown word as a new session's name, so
  always name the subcommand. (UR-26; 50-coordination.md "Where agents run"; 30-ops.md `O0.1`;
  owner-partner.md "Guardrails")
- **UR-28** Sandboxes come from `agent-dgx`, which gives each agent its own clone of the host
  checkout; the owner starts them, by hand or with the launcher (`O0.1`). Each agent runs in the sandbox `agent-<session>` on its own clone
  at `/agents/agent-<session>/workspace`. Start every agent from a clean, freshly pulled host
  checkout of `main` (`agent-dgx` copies uncommitted changes into the clone;
  `agent-dgx inspect <session> --json` shows the commit it cloned), and push your branch after every
  commit, since a clone keeps unpushed commits to itself. (UR-28; 50-coordination.md "Where agents
  run")
- **UR-30** The operator role goes to an agent: `uplevel-operator`, the only sandbox started with
  `agent-dgx --gpu`, runs every real-tier command through the `agent-gpu` broker
  (`roles/operator.md`). (UR-30)
  - **The GPU.** Only `uplevel-operator` holds the GPU and the `/synthbench` mounts: the owner
    starts it with `agent-dgx run uplevel-operator --agent claude --endpoint dgx --gpu --split`, no
    lane sandbox gets `--gpu`, and real-tier runs go one at a time through that session under the
    runner's 40 GiB cap, which every GPU session on the host shares. (ruling 2; 50-coordination.md
    "Where agents run"; 30-ops.md `O1.10`; owner-partner.md "Prompts")
  - **The owner's runs.** The owner keeps the runs that path cannot make: those that must exercise
    the deployed `ai-vlm`, those the runner will not admit, and S1/S4 latency claims, defined on 24
    GB-class hardware; latency numbers belong to the hardware that produced them. (operator.md)
- **UR-170** On the host, read an agent's workspace but run git in it only through `sbx exec`: its
  `.git/config` is the agent's to write, and settings such as `core.fsmonitor` run commands when the
  host's git opens it. (50-coordination.md "Where agents run"; 30-ops.md `O0.1`)
- **UR-173** The coordinator stays on the fast model on a 5-minute loop; the owner may reopen this
  if it stops assigning, leaves the status comment unedited for over an hour, or states a fact it
  did not read. Its sandbox is disposable: restarted, it rebuilds its state from PRs, labels and the
  pinned issues. (ruling 85; 50-coordination.md "Where agents run")
- **UR-174** Heavy work that appears while both heavy agents are paused goes on the urgent path; the
  owner restarts the agent with `agent-dgx run <name> --agent claude --split`, its kickoff from
  `scripts/uplevel/sandboxes.toml`, and `/loop 15m`. (ruling 88; 50-coordination.md "Paused")
- **UR-175** An agent's auto-memory is its own and not a channel: only the parent agent writes it,
  its subagents return findings to the parent, and only the harness's limits bind it. (ruling 112)
- **UR-176** Sandboxes may use `sudo` for development installs, such as
  `sudo npx playwright install-deps chromium`, with no record. Production Dockerfiles never gain
  browser packages, and nothing is built into the host sandbox image for this. (ruling 143;
  supersedes record 6123811294)

## Security

Read this section when your change touches exposure, auth, API keys, monitoring access, secrets or
the shared GitHub token.

- **UR-27** Every agent keeps acting through the owner's GitHub token. The owner accepts the risk:
  peer reviews and owner approvals are a policy agents follow, not something GitHub authenticates,
  and any agent could forge one. (UR-27)
- **UR-177** Read any third-party prompt or tool in full before adopting it, since agents hold the
  owner's token. (owner-partner.md "Guardrails"; UR-27)
- **UR-178** OD-12: the stack binds to loopback unless `EXPOSE_LAN=true`, and when exposed, auth is
  deny-by-default on `/api` and `/ws`. (README "Rulings of record"; 10-backend.md `B1.5`)
- **UR-33** With `EXPOSE_LAN=true`, monitoring is denied by default like every other path: `B1.5`
  closes `/api/metrics` and `/api/system/{gpu,stats,telemetry}`, and `O1.11` gives the monitoring
  callers credentials and puts `/grafana/` behind the app's login. The default, unexposed mode is
  unchanged. (UR-33; ruling 1)
- **UR-179** A browser bundle never carries an API key: browsers authenticate only through the
  cookie login, API keys are for non-browser clients, and a CI guard fails if `frontend/src` reads
  `VITE_API_KEY`. (ruling 44)
