# Uplevel — from working prototype to production platform

> Designed 2026-10-07 with the owner, at `main` tip `d6ba78d5`. Evidence lives in
> [`00-audit.md`](00-audit.md); this file holds the goal, the path, the contract every package
> inherits, the rulings of record and the one status table.

**The goal:** every feature in the UI works end to end, or is retired on purpose. The tree holds
only code that ships, and the tests protect behaviour instead of pinning implementation.

## Read this first

You are executing one **lane**. Read, in order:

1. This file — the vocabulary, the contract, the rulings.
2. Your lane plan: [`10-backend.md`](10-backend.md), [`20-frontend.md`](20-frontend.md),
   [`30-ops.md`](30-ops.md) or [`40-docs.md`](40-docs.md).
3. The `00-audit.md` sections your package cites (`00 §4.1`). Re-measure any **[A]** number before
   acting on it.
4. [`01-mutation-policy.md`](01-mutation-policy.md) whenever your package deletes, merges or writes
   tests.
5. [`50-coordination.md`](50-coordination.md) — how to claim a package, get it reviewed and merged.

The rules in the root [`AGENTS.md`](../../AGENTS.md) apply unchanged: TDD, hooks never bypassed,
podman, ports from `.env`, coverage floors never lowered.

## Vocabulary

These words carry exact meanings everywhere in `docs/uplevel/`.

| word                                                                                        | meaning                                                                                                                                                                                                                                                                                                                                                                                      |
| ------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **ships**                                                                                   | reachable, by the reachability check, from a production entry point (`backend/main.py` and its workers, `ai/gateway`) or a declared tool entry point (the synthbench CLI, CI-referenced scripts). Code that does not ship is a deletion candidate.                                                                                                                                           |
| **feature**                                                                                 | a user-visible capability: a UI page, panel or action, or an external interface (inbound webhooks, MQTT commands), traced UI → API route → service → store                                                                                                                                                                                                                                   |
| **works**                                                                                   | the feature's golden path is green on the fake stack and confirmed on the real tier                                                                                                                                                                                                                                                                                                          |
| **unverified**                                                                              | the inventory's provisional status for a feature that appears to work but has no golden path yet; `F2.3` promotes it to **works** or demotes it to **half-built**                                                                                                                                                                                                                            |
| **half-built**                                                                              | the surface exists, but the backend is a stub, missing, or reports success it did not achieve                                                                                                                                                                                                                                                                                                |
| **leftover**                                                                                | a surface for a capability that was retired (R8 and earlier)                                                                                                                                                                                                                                                                                                                                 |
| **complete** / **retire**                                                                   | the owner's two rulings on a feature that does not work                                                                                                                                                                                                                                                                                                                                      |
| **golden path**                                                                             | one unmocked spec that drives a feature end to end against a running stack: a Playwright spec for a UI feature, an HTTP or MQTT client spec for an external interface                                                                                                                                                                                                                        |
| **fake stack**                                                                              | the CI compose stack plus a deterministic fake VLM and fake detector; runs anywhere, no GPU                                                                                                                                                                                                                                                                                                  |
| **real tier**                                                                               | the same golden paths run by `scripts/feature-check.sh --real` on the GB300 with real models, always on a test deployment; operator-run, never from CI                                                                                                                                                                                                                                       |
| **test deployment**                                                                         | a disposable stack created for one run: its own compose project, env file, host ports, volumes and camera directory, sharing only read-only model weights with anything else on the machine (`O2.2`). Every real-tier command runs against one, including Phase 1's hand-written commands. A run that would touch the live deployment's database, camera folder or containers stops instead. |
| **operator**                                                                                | whoever runs real-tier commands: the `uplevel-operator` agent, whose sandbox reaches the GB300 through `agent-gpu` (UR-30), or the owner for the runs that path cannot make. A lane agent writes the command into its PR and the operator runs it, following [`operator.md`](operator.md).                                                                                                   |
| **feature inventory**                                                                       | `docs/reference/feature-inventory.md` (created by `F2.2`): one row per feature with status, evidence, modules and ruling. Built in Phase 2, kept current after.                                                                                                                                                                                                                              |
| **interface bar**, **kill-loss**, **zero kill-loss**, **accepted survivor**, **scored set** | mutation terms, defined in [`01-mutation-policy.md`](01-mutation-policy.md)                                                                                                                                                                                                                                                                                                                  |
| **lane**, **package**                                                                       | a lane owns a set of files (below); a package (`B1.2`, `O2.1`) is one independently landable unit of work inside a lane                                                                                                                                                                                                                                                                      |
| **current phase**                                                                           | for a lane, the lowest-numbered phase in which that lane still has a package not `done`                                                                                                                                                                                                                                                                                                      |
| **living docs**                                                                             | every doc except history: history is dated plans and specs (`docs/plans/`, `docs/superpowers/`), `docs/vss-integration/` and `docs/uplevel/`                                                                                                                                                                                                                                                 |
| **boundary**                                                                                | a directory that keeps an `AGENTS.md`: the root, a lane root, or a package with real invariants or traps; listed with a reason in `.agents-md-validator.yml` (UR-21, `40-docs.md`)                                                                                                                                                                                                           |

## The path

| phase | name                             | outcome                                                                      | exit gate                                                                                                                                                |
| ----- | -------------------------------- | ---------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0     | **Bootstrap**                    | the coordinator and `uplevel-ops-b` run                                      | the labels and the pinned issue exist (`50-coordination.md`, "Phases 0 and 1")                                                                           |
| 1     | **Stop the bleeding**            | shipped paths do what they claim                                             | D1–D3, D5, D6 and D8–D12 in `00 §3` closed, each by a committed test or check that fails if the defect returns. D4 and D7 are features; they go to `R2`. |
| 2     | **Feature truth**                | every feature has a verified status and an owner ruling                      | fake stack green in CI; feature inventory complete; reachability check built; owner RULING session held and recorded in the inventory                    |
| 3     | **The tree matches the rulings** | retired features are gone end to end; only shipping code remains             | retired features absent from UI, API, services, tables, settings and docs; reachability gates green in CI; mutation scored set switched                  |
| 4     | **Complete the product**         | half-built features become features that work, in the owner's priority order | per feature: golden path green on the fake stack, real-tier check recorded, inventory row says **works**                                                 |

Lanes move through the phases independently, with two shared gates: **Phase 2's RULING session
gates Phase 3 in every lane** (deletion follows rulings), and Phase 4's order comes from that same
session. **A blocked lane moves ahead:** when every remaining package in a lane's current phase
waits on another lane, the lane takes the next phase's first package whose dependencies have
landed — except that no Phase 3 package starts before `R2` is `done`.

**`R2`, the Phase 2 RULING session.** Runs after `F2.3`, so features its golden paths demoted are
ruled too. The owner walks the sheet `F2.2` prepares. Each half-built or leftover feature is ruled
**complete** or **retire**; the completes get a priority order; the list of modules serving no
feature is approved; OD-7 and OD-17 are ruled. **The frontend lane records the session:** one PR
writes the rulings into the inventory's ruling column and the OD rulings into
`docs/vss-integration/17-action-plan.md`, and sets `R2` to `done`.

**Phase 4 runs two tracks.** The **feature track** takes features in ruled priority. Each feature
package opens with a design session for that feature; then a **test-only PR** consolidates the
tests of the modules it will touch, under `01`'s zero kill-loss protocol; then a build PR adds the
feature and its golden path. That consolidation PR is the one named exception to "one package per
PR": a feature package lands as two PRs, so the test-only rule can apply. The **background track**
consolidates tests of modules no feature touches (test-only PRs, same protocol) and deepens seams
no feature has triggered (resilience primitives, the broadcaster, the config split). Every seam is
designed when it is reached, against the code that remains — never in advance.

**Paused while Phase 1 runs:** VLM prompt and threshold selection (the prompt programme, OD-26,
OD-29) waits for replay parity, `B1.2`. Synthbench corpus generation continues; it ships no
production code.

## Lanes

| lane         | owns                                                                                                                                                                                                                                                                           |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **backend**  | `backend/` (except `backend/tests/unit/setup_lib/`)                                                                                                                                                                                                                            |
| **frontend** | `frontend/` (including `frontend/docker-entrypoint.sh`, the nginx config) and the feature inventory                                                                                                                                                                            |
| **ops**      | `ai/`, compose files, `scripts/` (except the AGENTS.md validator), `.github/`, `setup.py`, `setup_lib/` and its tests, root config files, `archive/`, and the root directories `tests/`, `monitoring/`, `docker/`, `config/`, `env-templates/`, `data/`, `certs/`              |
| **docs**     | `docs/` (except the feature inventory and `docs/uplevel/`), every `AGENTS.md`, `llms.txt`, `mkdocs.yml`, the root `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md` and `SECURITY.md`, and the AGENTS.md validator (`scripts/agents_md_validator.py`, `.agents-md-validator.yml`) |

`docs/uplevel/` is shared: each PR updates its own package's status row, and changes to plan text
are made by the owner or with the owner's approval.

`synthbench/` belongs to the synthbench workstream, which continues alongside this programme
(UR-8). A package touches it only under the cross-lane rule — when a deletion removes something
synthbench imports.

**Cross-lane rule:** the PR that removes or changes a thing does so everywhere at once, whichever
lane owns the files. A dead setting leaves `config.py`, `.env.example` and the compose `environment:`
block in one PR. A PR also updates the docs and `AGENTS.md` lines that describe what it changed.
The lane that owns the primary change leads; packages that span lanes name their parts and their
order.

**Cross-lane dependencies:** `B1.4` → `F1.2` (engine status, then the banner). `B1.5` → `F1.3` and
`O1.6` (OD-12 has parts in all three; whichever of `F1.3` and `O1.6` lands last marks ISS-029 done).
`O2.1` → `O2.2` → `F2.1` → `F2.3` → `R2` (the stack, its harness, its specs, then the rulings).
`O1.5` and `B1.5` → `O1.8` (they close 18 of its 21 alerts). `O2.3` → `F2.2`'s module list. `B3.1` and `F3.1` land each retired feature in one PR. The docs
lane's Phase 3 starts on a lane's directories only after that lane's Phase 3 is `done`.

## The contract

Every package inherits five rules. Each answers a failure the audit found (`00 §6`).

1. **Outcome, not target.** A package ends on a **Done when** that a reviewer can observe: a test
   that passes, a command's output, a file that no longer exists. Numbers are measured and reported,
   never climbed.
2. **Evidence in the PR.** Open every package PR with `gh pr create --template uplevel.md`
   (`.github/PULL_REQUEST_TEMPLATE/uplevel.md`). The PR body carries each command and its output.
   Commit subjects stay at 72 characters or fewer. Ledger files take no rows from this programme.
3. **Tools live in the repo.** Every script, fixture and harness a package relies on is committed.
   Work from `/tmp` or a home directory does not count as evidence.
4. **Rulings come in batches.** A phase's RULING items are settled at the phase boundary. When a
   package meets a question its plan does not answer, it stops and reports the question; it does not
   widen its own scope.
5. **One status table.** The table below. The PR that finishes a package sets its row to `done`
   with the PR number, and marks any `17-action-plan.md` entry it closes as done in the same PR.
   A package whose Done when needs real-tier numbers merges with the operator's command in its PR
   body and sets its row to `awaiting real tier`; the operator posts the output as a PR comment and
   sets the row to `done` in a one-line follow-up commit. A phase exits only when all its rows say
   `done`.

Package markers follow the house plan format: **MEASURE** — produce the number and put it in the
PR; **DECIDE** — choose on evidence and record why in the PR; **RULING** — stop and ask the owner.

## Rulings of record (2026-10-07)

Packages cite these as `UR-n`.

| id    | ruling                                                                                                                                                                                                                                                                                           |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| UR-1  | The mutation score is a diagnostic with a no-regression floor on shipping code. The 85% target is retired.                                                                                                                                                                                       |
| UR-2  | The mutation campaign holds after M54 (PR #6844).                                                                                                                                                                                                                                                |
| UR-3  | The mutation scored set is what the reachability check reaches.                                                                                                                                                                                                                                  |
| UR-4  | The floor is enforced by a weekly alert (never blocking) and by before/after evidence on PRs that delete or merge tests.                                                                                                                                                                         |
| UR-5  | A "drop" is split by path: zero kill-loss on test-only PRs; a per-module drop beyond a measured noise band on the weekly run; the global score is informational.                                                                                                                                 |
| UR-6  | A kill counts only through the interface bar; mutants killed only by below-bar tests may be surrendered as recorded accepted survivors.                                                                                                                                                          |
| UR-7  | One home per kind of evidence: PR body, CI-written weekly history (compacted), one accepted-survivors file; the L ledger takes no new mutation rows.                                                                                                                                             |
| UR-8  | Targeted pause: VLM prompt and threshold selection waits for replay parity; synthbench continues; all other agents move to this programme.                                                                                                                                                       |
| UR-9  | Lanes that own files (four since UR-20); the cross-lane rule above.                                                                                                                                                                                                                              |
| UR-10 | The five-rule contract above.                                                                                                                                                                                                                                                                    |
| UR-11 | One plan per lane; seams are designed when reached.                                                                                                                                                                                                                                              |
| UR-12 | Inbound webhooks: **implement** (an arming module with webhook and MQTT adapters, designed after Phase 3); until then they answer `501` and validate keys against `settings.api_keys`.                                                                                                           |
| UR-13 | The owner rules per feature, from a verified feature inventory; modules follow their feature's ruling; modules serving no feature come to the owner as one list.                                                                                                                                 |
| UR-14 | "Works" is proven by golden paths: green on the fake stack in CI, then confirmed on the real tier.                                                                                                                                                                                               |
| UR-15 | The real tier is operator-run on the GB300 by a committed script; no self-hosted runner.                                                                                                                                                                                                         |
| UR-16 | Test consolidation is just in time inside feature packages, plus a background track.                                                                                                                                                                                                             |
| UR-17 | The ghcr install path is retired; local build plus the prod compose file is the one supported install.                                                                                                                                                                                           |
| UR-18 | `ai-vlm` starts by default; backend readiness and a UI banner report the engine's runtime state; GPU-less development uses the fake VLM through an explicit overlay.                                                                                                                             |
| UR-19 | `archive/` and `docs/archive/` are deleted; the two `setup.py` test files return to the live suite; git history is not rewritten.                                                                                                                                                                |
| UR-20 | A fourth lane, docs, owns the documentation and makes it true: Phase 1 stops active misdirection, Phase 3 rewrites after the deletions.                                                                                                                                                          |
| UR-21 | `AGENTS.md` files live only at boundaries, listed with a reason; the validator fails on dead references and on files outside the list.                                                                                                                                                           |
| UR-22 | Agents claim packages themselves through draft PRs; a coordinator agent routes work and writes no product code (`50-coordination.md`).                                                                                                                                                           |
| UR-23 | A PR merges on green CI plus an approving review from another lane's agent, after the author's own fresh-context self-review; owner-tier PRs also need the owner. The coordinator merges.                                                                                                        |
| UR-24 | `heavy` packages go only to the strongest available model or to an owner pairing; the fast local model takes the rest.                                                                                                                                                                           |
| UR-25 | The owner works from one daily batch at a fixed time; the urgent path interrupts only for security, the live deployment, or a red `main`.                                                                                                                                                        |
| UR-26 | The coordinator runs in its own sandbox; every agent runs in its own clone-mode sandbox, created by an owner-run launcher at phase boundaries; GitHub is the only channel between them. UR-28 says how.                                                                                          |
| UR-27 | Every agent keeps acting through the owner's GitHub token. The owner accepts the risk: peer reviews and owner approvals are a policy agents follow, not something GitHub authenticates, and any agent could forge one.                                                                           |
| UR-28 | Sandboxes come from `agent-dgx`, which gives each agent its own clone of the host checkout. The owner starts Phases 0 and 1 by hand; `O0.1` builds the launcher around `agent-dgx`, used from the Phase 2 boundary.                                                                              |
| UR-29 | The coordinator states only what a `gh` or `git` command it ran in the same turn shows. Before each merge it posts a comment quoting the merge rule's evidence, and an owner approval given outside the batch counts once the coordinator quotes it on the batch issue.                          |
| UR-30 | The operator role goes to an agent: `uplevel-operator`, the only sandbox started with `agent-dgx --gpu`, runs every real-tier command through the `agent-gpu` broker (`operator.md`). The owner keeps the runs that path cannot make.                                                            |
| UR-31 | Every agent, not only the coordinator, states only what it has just read: each commit, PR, file, test result and question it cites comes from output it ran in the same turn.                                                                                                                    |
| UR-32 | Reviews come first. When a PR goes ready, the coordinator labels it `review:<lane>`; a lane agent clears its label's PRs before starting or resuming a package.                                                                                                                                  |
| UR-33 | With `EXPOSE_LAN=true`, monitoring is denied by default like every other path: `B1.5` closes `/api/metrics` and `/api/system/{gpu,stats,telemetry}`, and `O1.11` gives the monitoring callers credentials and puts `/grafana/` behind the app's login. The default, unexposed mode is unchanged. |
| UR-34 | CI is green only when the required check `CI Gate (Required Checks)` is present and passed at the PR's head; a workflow change runs `actionlint` against `main`'s findings before it is pushed.                                                                                                  |
| UR-35 | Agents read the new comments on their own open PRs before resuming a package; an owner ruling or a requested change there comes before new work.                                                                                                                                                 |
| UR-36 | Every agent runs on a `/loop` tick that checks GitHub — coordinator 5 minutes, lanes and heavy 15, operator 30 (`50-coordination.md`, "The tick"). GitHub stays the only channel between agents; the owner re-arms ticks weekly and after a restart.                                             |

Already ruled in the register and executed here: OD-12 (loopback unless `EXPOSE_LAN=true`,
deny-by-default auth when exposed) by `B1.5`, `F1.3` and `O1.6`; OD-20 (retire the enrichment
surface: hook, route, types and tombstone, ISS-073) by `B3.1` and `F3.1`, first in their queues;
OD-28 (delete the dead service modules) by `B3.2`. Deferred to the Phase 2 RULING session: OD-7 (threat fast paths), OD-17 (Triton
`reid`/`threat` lane, `ai-llm-vllm`), and every feature-level complete/retire call.

Out of scope: rewriting git history, renaming `setup.py`, widening frontend Stryker (it stays on
three utility files).

## Considered and rejected

Alternatives the design session weighed and turned down. Reopening one is a **RULING**; bring the
new evidence that would change the reason.

| alternative                                                                | why not                                                                                                                                                                 | instead |
| -------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- |
| A mutation-score target (85%)                                              | tests were written to move the number: source-comment pins, kwargs spies, campaigns on dead code (`00 §4.4, §6`)                                                        | UR-1    |
| Deleting the 130 batteries at once                                         | up to ~22 points of kills lost, unmeasured                                                                                                                              | UR-16   |
| A blocking per-PR mutation job                                             | 60–90 minutes of setup per run before any mutant executes                                                                                                               | UR-4    |
| A self-hosted runner on the GB300                                          | the repo is public; a fork PR could execute on the GPU box                                                                                                              | UR-15   |
| Moving dead code into `archive/`                                           | relocates sediment; git history already keeps every deleted file                                                                                                        | UR-19   |
| Deleting everything unreachable by default                                 | would delete half-built features the owner wants finished                                                                                                               | UR-13   |
| Owner rulings per module                                                   | hundreds of sign-offs on files whose purpose must be reconstructed from code                                                                                            | UR-13   |
| A full feature freeze                                                      | idles synthbench GPU work, which ships no production code                                                                                                               | UR-8    |
| Lanes split by phase across the whole repo                                 | deletion and consolidation would collide in `backend/tests`                                                                                                             | UR-9    |
| Designing the Phase 4 seams now                                            | they would be designed around ~38K lines Phase 3 deletes                                                                                                                | UR-11   |
| Deleting the inbound webhooks                                              | the owner wants the integration; it gets built instead                                                                                                                  | UR-12   |
| Mocked end-to-end tests as proof that a feature works                      | mocks are how a call to a missing endpoint (D2) stayed green                                                                                                            | UR-14   |
| Publishing prebuilt images to ghcr                                         | `ai-vlm` is built per CUDA architecture; a multi-arch, multi-CUDA image matrix for one install path                                                                     | UR-17   |
| Rewriting git history to shrink the pack                                   | breaks every clone and fork of a public repository                                                                                                                      | —       |
| Separate GitHub identities for agents (a machine account, or one per lane) | owner's call, 2026-10-07: the shared token stays and its risk is accepted; reopen if an agent is ever compromised or the programme widens beyond the owner's own agents | UR-27   |

## Status

The single status table. Update your row in the PR that finishes the package, and change only that
line: prettier skips this table, so a longer cell never re-pads the other rows. Statuses: `not started`,
`awaiting real tier`, `done`. Work in progress shows as an open draft PR titled `[<package>] …`
(`50-coordination.md`), not as a row status. Flags: `heavy` — assigned by the coordinator to the
strongest available model or an owner pairing (UR-24); `owner` — needs the owner's approval before
merge (UR-23). Phase 4 packages get their own row when they open: the
PR that opens `B4.2` or `FB.1` adds its row under the matching `*` line.

<!-- prettier-ignore -->
| package | lane                    | phase      | name                                           | flags         | status      | PR  |
| ------- | ----------------------- | ---------- | ---------------------------------------------- | ------------- | ----------- | --- |
| O0.1    | ops                     | 0          | The sandbox launcher (UR-26, UR-28)            | owner         | not started |     |
| B1.1    | backend                 | 1          | VLM timeout ladder (D1)                        |               | not started |     |
| B1.2    | backend                 | 1          | Replay parity (D6)                             | heavy         | not started |     |
| B1.3    | backend                 | 1          | Honest inbound webhooks (D3)                   |               | not started |     |
| B1.4    | backend                 | 1          | Verdict-engine status (UR-18)                  |               | not started |     |
| B1.5    | backend                 | 1          | Exposure and auth, backend part (D8, D10)      | heavy · owner | not started |     |
| B1.6    | backend                 | 1          | Scope the orchestrator and its recovery (D11)  | heavy · owner | not started |     |
| F1.1    | frontend                | 1          | Endpoint truth (D2)                            |               | not started |     |
| F1.2    | frontend                | 1          | Verdict-engine banner (UR-18)                  |               | not started |     |
| F1.3    | frontend                | 1          | Exposure and auth, frontend part (D10)         | owner         | not started |     |
| O1.1    | ops                     | 1          | Mutation hold and supersede (UR-2, UR-7)       |               | done        | #6863 |
| O1.2    | ops                     | 1          | Retire ghcr (UR-17)                            |               | not started |     |
| O1.3    | ops                     | 1          | `ai-vlm` on by default (UR-18)                 |               | not started |     |
| O1.4    | ops                     | 1          | Broken workflows (D9)                          |               | not started |     |
| O1.5    | ops                     | 1          | Delete the archives (UR-19)                    |               | not started |     |
| O1.6    | ops                     | 1          | Exposure and auth, compose part (D10)          | owner         | not started |     |
| O1.7    | ops                     | 1          | Audit measurement scripts                      |               | not started |     |
| O1.8    | ops                     | 1          | Dependabot alerts                              | owner         | not started |     |
| O1.9    | ops                     | 1          | Deploy green on `main`                         |               | not started |     |
| O1.10   | ops                     | 1          | The operator sandbox (UR-30)                   | owner         | not started |     |
| O1.11 | ops | 1 | Monitoring behind the gate (UR-33) | owner | not started | |
| B2.1    | backend                 | 2          | Interface bar and accepted survivors (`01` M3) |               | not started |     |
| F2.1    | frontend                | 2          | Golden-path harness                            |               | not started |     |
| F2.2    | frontend                | 2          | Feature inventory                              | heavy         | not started |     |
| F2.3    | frontend                | 2          | Golden paths for every working feature         |               | not started |     |
| O2.1    | ops                     | 2          | Fake AI stack                                  |               | not started |     |
| O2.2    | ops                     | 2          | Feature-check harness (fake and real)          | heavy · owner | not started |     |
| O2.3    | ops                     | 2          | Reachability check (`01` M1)                   |               | not started |     |
| R2      | owner; frontend records | 2          | Phase 2 RULING session (after `F2.3`)          | owner         | not started |     |
| B3.1    | backend                 | 3          | Retire ruled-out features, backend part        | heavy · owner | not started |     |
| B3.2    | backend                 | 3          | Delete the approved module list                | heavy · owner | not started |     |
| B3.3    | backend                 | 3          | Settings and residue truth                     |               | not started |     |
| F3.1    | frontend                | 3          | Retire ruled-out features, frontend part       | heavy · owner | not started |     |
| F3.2    | frontend                | 3          | Unreachable files and the knip gate            |               | not started |     |
| F3.3    | frontend                | 3          | Quarantined tests                              |               | not started |     |
| O3.1    | ops                     | 3          | Prune `ai/` to what ships                      |               | not started |     |
| O3.2    | ops                     | 3          | Compose base and overlays                      |               | not started |     |
| O3.3    | ops                     | 3          | `models.yml` and env truth                     |               | not started |     |
| O3.4    | ops                     | 3          | Reachability gates in CI                       |               | not started |     |
| O3.5    | ops                     | 3          | Weekly mutation scorer and history (`01` M2)   |               | not started |     |
| O3.6    | ops                     | 3          | PR mutation evidence tool (`01` M4)            | heavy         | not started |     |
| O3.7    | ops                     | 3          | `scripts/` truth                               |               | not started |     |
| B4.\*   | backend                 | 4          | Feature track (arming among them, UR-12)       | design: heavy | not started |     |
| BB.\*   | backend                 | 4          | Background track                               |               | not started |     |
| F4.\*   | frontend                | 4          | Feature track, frontend parts                  | design: heavy | not started |     |
| FB.\*   | frontend                | 4          | Background track                               |               | not started |     |
| OB.2    | ops                     | after 1    | CI dedupe                                      |               | not started |     |
| OB.3    | ops                     | after 1    | Image weight                                   |               | not started |     |
| OB.4    | ops                     | on trigger | Lane map and cross-lane check                  |               | not started |     |
| W1.1    | docs                    | 1          | The validator with teeth                       |               | not started |     |
| W1.2    | docs                    | 1          | Root truth                                     |               | not started |     |
| W1.3    | docs                    | 1          | Remove dead references now                     |               | not started |     |
| W2.1    | docs                    | 2          | The boundary list and the line caps            |               | not started |     |
| W2.2    | docs                    | 2          | Docs rulings for `R2`                          |               | not started |     |
| W3.1    | docs                    | 3          | Boundaries only                                |               | not started |     |
| W3.2    | docs                    | 3          | Rewrite the boundary files to the standard     |               | not started |     |
| W3.3    | docs                    | 3          | Living docs truth                              |               | not started |     |
| W3.4    | docs                    | 3          | Carry out the docs rulings                     |               | not started |     |

## Files

| file                                                         | holds                                                                             |
| ------------------------------------------------------------ | --------------------------------------------------------------------------------- |
| [`00-audit.md`](00-audit.md)                                 | the evidence baseline at `d6ba78d5`                                               |
| [`01-mutation-policy.md`](01-mutation-policy.md)             | the mutation policy (UR-1 to UR-7) and its packages                               |
| [`10-backend.md`](10-backend.md)                             | backend lane plan and kickoff prompt                                              |
| [`20-frontend.md`](20-frontend.md)                           | frontend lane plan and kickoff prompt                                             |
| [`30-ops.md`](30-ops.md)                                     | ops lane plan and kickoff prompt                                                  |
| [`40-docs.md`](40-docs.md)                                   | docs lane plan, the AGENTS.md standard, kickoff prompt                            |
| [`50-coordination.md`](50-coordination.md)                   | roles, claiming, review and merge, hot files, the daily batch, coordinator prompt |
| [`operator.md`](operator.md)                                 | the operator's runbook for the real tier                                          |
| [`templates/r2-sheet.md`](templates/r2-sheet.md)             | the `R2` ruling sheet, filled by `F2.2` and `F2.3`                                |
| [`templates/feature-design.md`](templates/feature-design.md) | the Phase 4 design, one per feature                                               |
| `.github/PULL_REQUEST_TEMPLATE/uplevel.md`                   | the PR template every package uses                                                |
