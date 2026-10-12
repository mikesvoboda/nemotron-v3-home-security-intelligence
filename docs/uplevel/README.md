# Uplevel — from working prototype to production platform

**The goal:** every feature in the UI works end to end, or is retired on purpose. The tree holds
only code that ships, and the tests protect behaviour instead of pinning implementation. The
programme was designed with the owner on 2026-10-07 at `main` tip `d6ba78d5`, from the evidence in
[`00-audit.md`](00-audit.md). Four lanes (backend, frontend, ops, docs) each work through their own
packages, phase by phase, with one or two agents per lane by phase; a coordinator routes work and an
operator runs the real-tier checks. The owner gives the rulings, holds the Phase 4 design sessions,
reviews owner-tier PRs and has the final say on merges, through rulings and owner records on #6854,
working from the coordinator's status comment there. What is out of scope is UR-84.

Every standing rule is in [`rules.md`](rules.md), grouped by the act it governs, including the
contract every package inherits and the `UR-n` rulings of record. Each role's procedure is in
a file under `roles/` (see [Files](#files)).

## Phases and exit gates

| phase | name                             | outcome                                                                      | exit gate                                                                                                                                                |
| ----- | -------------------------------- | ---------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0     | **Bootstrap**                    | the coordinator and `uplevel-ops-b` run                                      | the labels and the pinned issue exist ([`roles/coordinator.md`](roles/coordinator.md))                                                                   |
| 1     | **Stop the bleeding**            | shipped paths do what they claim                                             | D1–D3, D5, D6 and D8–D12 in `00 §3` closed, each by a committed test or check that fails if the defect returns. D4 and D7 are features; they go to `R2`. |
| 2     | **Feature truth**                | every feature has a verified status and an owner ruling                      | fake stack green in CI; feature inventory complete; reachability check built; `R2a` and `R2b` held and recorded in the inventory (ruling 86)             |
| 3     | **The tree matches the rulings** | retired features are gone end to end; only shipping code remains             | retired features absent from UI, API, services, tables, settings and docs; reachability gates green in CI; mutation scored set switched                  |
| 4     | **Complete the product**         | half-built features become features that work, in the owner's priority order | per feature: golden path green on the fake stack, real-tier check recorded, inventory row says **works**                                                 |

**When a phase exits**, and which packages may stay open past the Phase 2 boundary, is UR-10
(contract rule 5).

Lanes move through the phases independently, with two shared gates: **Phase 2's RULING session
gates Phase 3 in every lane** (deletion follows rulings), and Phase 4's order comes from that same
session. When a lane may start the next phase's work is in rules.md §Claiming and assigning work.

**`R2`, the Phase 2 RULING session.** The owner walks the sheet `F2.2` prepares: each half-built or
leftover feature is ruled **complete** or **retire**, the completes get a priority order, the list
of modules serving no feature is approved, and OD-7 and OD-17 are ruled. Its two parts, `R2a`
(recorded #6980, 2026-10-10) and `R2b`'s rounds, and when `R2` is `done`, are UR-148; a row demoted
only because the CI stack cannot reach it is UR-153. The frontend lane records each part (UR-149;
`packages/frontend.md`, `R2b`).

**Phase 4 runs two tracks.** The **feature track** takes features in ruled priority, each as a
design session, a test-only PR and a build PR with the feature and its golden path (UR-77, UR-79).
The **background track** consolidates tests of modules no feature touches and deepens seams no
feature has triggered. Seams are designed when reached (UR-11).

## Cross-lane dependencies

- `B1.4` → `F1.2` (engine status, then the banner).
- `B1.5` → `F1.3` and `O1.6` (OD-12 has parts in all three; the B-1 follow-up (#6927) is the
  closing entry that marks ISS-029 done). `B1.5` and `O1.6` → `O1.11`.
- `O1.5` and `B1.5` → `O1.8` (they close 18 of its 21 alerts).
- `O2.1` → `O2.2` → `F2.1` → `R2a` → `F2.3` → `R2b` (the stack, its harness, its specs, then the
  rulings, split by ruling 86; `R2a` recorded 2026-10-10 in #6980).
- `O2.3` → `O2.3b` → `F2.2`'s module list and `R2`'s §3.
- `O2.4` → `B2.3` (TensorRT re-ID, then the bake-off; ruling 107).
- `O2.5` → ruling 127's 12 real-tier rows in `F2.3` (ruling 144).
- `B3.1` and `F3.1` land each retired feature in one PR.
- Each lane's Phase 3 → the docs lane's Phase 3 on that lane's directories (UR-68).

## Vocabulary

These words carry exact meanings everywhere in `docs/uplevel/`.

- **ships** — reachable, by the reachability check, from a production entry point
  (`backend/main.py` and its workers, `ai/gateway`) or a declared tool entry point (the synthbench
  CLI, CI-referenced scripts). Code that does not ship is a deletion candidate.
- **feature** — a user-visible capability: a UI page, panel or action, or an external interface
  (inbound webhooks, MQTT commands), traced UI → API route → service → store.
- **works** — the feature's golden path is green on the fake stack and confirmed on the real tier.
- **unverified** — the inventory's provisional status for a feature that appears to work but has
  no golden path yet; `F2.3` promotes it to **works** or demotes it to **half-built**.
- **half-built** — the surface exists, but the backend is a stub, missing, or reports success it
  did not achieve; or the break is at the UI end: a control wired to nothing, a success message
  over a write that never happens, a component wired to the API that no route renders (UR-152).
- **leftover** — a surface for a capability that was retired (R8 and earlier).
- **complete** / **retire** — the owner's two rulings on a feature that does not work.
- **golden path** — one unmocked spec that drives a feature end to end against a running stack: a
  Playwright spec for a UI feature, an HTTP or MQTT client spec for an external interface.
- **fake stack** — the CI compose stack plus a deterministic fake VLM and fake detector; runs
  anywhere, no GPU.
- **real tier** — the same golden paths run by `scripts/feature-check.sh --real` on the GB300 with
  real models (who runs it and where: UR-15, UR-133).
- **test deployment** — a disposable stack created for one run: its own compose project, env file,
  host ports, volumes and camera directory, sharing only read-only model weights with anything
  else on the machine (`O2.2`). When one is required: UR-133.
- **operator** — whoever runs real-tier commands: the `uplevel-operator` agent, whose sandbox
  reaches the GB300 through `agent-gpu`, or the owner for the runs that path cannot make (UR-30,
  UR-15); its procedure is [`roles/operator.md`](roles/operator.md).
- **feature inventory** — `docs/reference/feature-inventory.md` (created by `F2.2`): one row per
  feature with status, evidence, modules and ruling. Built in Phase 2, kept current after.
- **interface bar**, **kill-loss**, **zero kill-loss**, **accepted survivor**, **scored set** —
  mutation terms: the bar and survivors in
  [`mutation-testing.md`](../developer/patterns/mutation-testing.md), the rest in
  [`01-mutation-policy.md`](01-mutation-policy.md).
- **lane**, **package** — a lane owns a set of files (below); a package (`B1.2`, `O2.1`) is one
  independently landable unit of work inside a lane.
- **current phase** — for a lane, the lowest-numbered phase in which that lane still has a package
  not `done`.
- **living docs** — every doc except history: history is dated plans and specs (`docs/plans/`,
  `docs/superpowers/`), `docs/vss-integration/` and `docs/uplevel/`.
- **boundary** — a directory that keeps an `AGENTS.md`: the root, a lane root, or a package with
  real invariants or traps; listed with a reason in `.agents-md-validator.yml` (UR-21,
  [`packages/docs.md`](packages/docs.md)).
- **MEASURE** / **DECIDE** / **RULING** — the package markers of the house plan format (UR-76).

## Lanes and ownership

- **backend:** `backend/` (except `backend/tests/unit/setup_lib/`).
- **frontend:** `frontend/` (including `frontend/docker-entrypoint.sh`, the nginx config) and the
  feature inventory.
- **ops:** `ai/`, compose files, `scripts/` (except the AGENTS.md validator), `.github/`,
  `setup.py`, `setup_lib/` and its tests, root config files, `archive/`, and the root directories
  `tests/`, `monitoring/`, `docker/`, `config/`, `env-templates/`, `data/`, `certs/`.
- **docs:** `docs/` (except the feature inventory and `docs/uplevel/`), every `AGENTS.md` except
  the lines a lane's own change updates (UR-81), `llms.txt`, `mkdocs.yml`, the root
  `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md` and `SECURITY.md`, and the AGENTS.md validator
  (`scripts/agents_md_validator.py`, `.agents-md-validator.yml`).

`docs/uplevel/` is shared; who may change which part is UR-46 and UR-47. `synthbench/` belongs to
the synthbench workstream; when a package may touch it is UR-82.

## Considered and rejected

Alternatives the design session weighed and turned down. Reopening one: UR-44.

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

The single status table. Who edits which row: UR-46. The row a finishing PR sets, and the packages
that may stay open past the Phase 2 boundary: UR-10 (contract rule 5). Statuses: UR-144. Flags, and
the rows Phase 4 packages add when they open (`B4.2` or `FB.1` under the matching `*` line):
UR-147.

<!-- prettier-ignore -->
| package | lane                    | phase      | name                                           | flags         | status      | PR  |
| ------- | ----------------------- | ---------- | ---------------------------------------------- | ------------- | ----------- | --- |
| O0.1    | ops                     | 0          | The sandbox launcher (UR-26, UR-28)            | owner         | done        | #6855 |
| B1.1    | backend                 | 1          | VLM timeout ladder (D1)                        |               | awaiting real tier | #6868 |
| B1.2    | backend                 | 1          | Replay parity (D6)                             | heavy         | done        | #6924 |
| B1.3    | backend                 | 1          | Honest inbound webhooks (D3)                   |               | done        | #6880 |
| B1.4    | backend                 | 1          | Verdict-engine status (UR-18)                  |               | done        | #6886 |
| B1.5    | backend                 | 1          | Exposure and auth, backend part (D8, D10)      | heavy · owner | done        | #6861 |
| B1.6    | backend                 | 1          | Scope the orchestrator and its recovery (D11)  | heavy · owner | done | #6929 |
| F1.1    | frontend                | 1          | Endpoint truth (D2)                            |               | done        | #6869 |
| F1.2    | frontend                | 1          | Verdict-engine banner (UR-18)                  |               | awaiting real tier | #6909 |
| F1.3    | frontend                | 1          | Exposure and auth, frontend part (D10)         | owner         | done        | #6922 |
| O1.1    | ops                     | 1          | Mutation hold and supersede (UR-2, UR-7)       |               | done        | #6863 |
| O1.2    | ops                     | 1          | Retire ghcr (UR-17)                            |               | done        | #6907 |
| O1.3    | ops                     | 1          | `ai-vlm` on by default (UR-18)                 |               | done        | #6862 |
| O1.4    | ops                     | 1          | Broken workflows (D9)                          |               | done        | #6926 |
| O1.5    | ops                     | 1          | Delete the archives (UR-19)                    |               | done        | #6931 |
| O1.6    | ops                     | 1          | Exposure and auth, compose part (D10)          | owner         | done        | #6925 |
| O1.7    | ops                     | 1          | Audit measurement scripts                      |               | done        | #6934 |
| O1.8    | ops                     | 1          | Dependabot alerts                              | owner         | done        | #6947 |
| O1.9    | ops                     | 1          | Deploy green on `main`                         |               | done        | #6875 |
| O1.10   | ops                     | 1          | The operator sandbox (UR-30)                   | owner         | done        | #6867 |
| O1.11 | ops | 1 | Monitoring behind the gate (UR-33) | owner | awaiting real tier | #6930 |
| O1.12 | ops | 1 | The hooks run in the gate (UR-37) | | done | #6901 |
| B2.1    | backend                 | 2          | Interface bar and accepted survivors (`01` M3) |               | done     | #6921 |
| B2.2 | backend | 2 | Re-ID on the GPU (OD-17 re-ID half) — parked: GPU path fails on GB300 (ruling 106); CPU path measured | heavy · owner | done | #6970 |
| B2.3    | backend                 | 2          | Re-ID model bake-off                           | heavy         | not started |       |
| F2.1    | frontend                | 2          | Golden-path harness                            |               | done        | #6976 |
| F2.2    | frontend                | 2          | Feature inventory                              | heavy         | done        | #6941 |
| F2.3    | frontend                | 2          | Golden paths for every working feature         |               | in progress | #6997 |
| O2.1    | ops                     | 2          | Fake AI stack                                  |               | done        | #6946 |
| O2.2    | ops                     | 2          | Feature-check harness (fake and real)          | heavy · owner | awaiting real tier | #6961 |
| O2.3    | ops                     | 2          | Reachability check (`01` M1)                   |               | done        | #6954 |
| O2.3b   | ops                     | 2          | Reachability: ancestor packages ship           |               | done        | #6973 |
| O2.4    | ops                     | 2          | Re-ID on the GB300 GPU via TensorRT            |               | not started |     |
| O2.5    | ops                     | 2          | Production-shape real tier                     |               | not started |     |
| R2a     | owner; frontend records | 2          | Phase 2 RULING session, part 1 (as it stood)   | owner         | done        | #6980 |
| R2b     | owner; frontend records | 2          | Phase 2 RULING session, part 2 (after `F2.3`)  | owner         | not started |     |
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
| OB.2    | ops                     | after 1    | CI dedupe                                      |               | done        | #6963 |
| OB.3    | ops                     | after 1    | Image weight                                   |               | not started |     |
| OB.4    | ops                     | on trigger | Lane map and cross-lane check                  |               | not started |     |
| W1.1    | docs                    | 1          | The validator with teeth                       |               | done        | #6870 |
| W1.2    | docs                    | 1          | Root truth                                     |               | done        | #6884 |
| W1.3    | docs                    | 1          | Remove dead references now                     |               | done        | #6915 |
| W2.1    | docs                    | 2          | The boundary list and the line caps            |               | done        | #6920 |
| W2.2    | docs                    | 2          | Docs rulings for `R2`                          |               | done        | #6923 |
| W3.1    | docs                    | 3          | Boundaries only                                |               | not started |     |
| W3.2    | docs                    | 3          | Rewrite the boundary files to the standard     |               | not started |     |
| W3.3    | docs                    | 3          | Living docs truth                              |               | not started |     |
| W3.4    | docs                    | 3          | Carry out the docs rulings                     |               | not started |     |

## Files

- [`README.md`](README.md): the goal, phases, dependencies, vocabulary, lanes, the alternatives
  considered and rejected, status and this map.
- [`rules.md`](rules.md): every standing rule, grouped by situation, with its source.
- [`roles/coordinator.md`](roles/coordinator.md): the coordinator's remit, tick, status comment
  and kickoff prompt.
- [`roles/lane.md`](roles/lane.md): the lane and heavy agents' tick, split-lane and heavy-sandbox
  specifics, and the lane kickoff prompts.
- [`roles/operator.md`](roles/operator.md): the operator's real-tier runbook and kickoff prompt.
- [`roles/owner-partner.md`](roles/owner-partner.md): the owner's design partner — role, relay form
  and handoff state.
- [`packages/backend.md`](packages/backend.md), [`frontend.md`](packages/frontend.md),
  [`ops.md`](packages/ops.md), [`docs.md`](packages/docs.md): each lane's scope and open packages.
- [`history/packages-done.md`](history/packages-done.md): finished packages, verbatim, by lane.
- [`history/ruling-map.md`](history/ruling-map.md): where each owner ruling 1–146 went.
- History, kept at these paths because code reads them: [`00-audit.md`](00-audit.md) (the evidence
  baseline at `d6ba78d5`), [`01-mutation-policy.md`](01-mutation-policy.md) (the mutation policy,
  UR-1 to UR-7, and its packages), [`r2-sheet.md`](r2-sheet.md) (the `R2` ruling sheet, filled by
  `F2.2` and `F2.3`), [`templates/r2-sheet.md`](templates/r2-sheet.md) (the sheet's template) and
  [`templates/feature-design.md`](templates/feature-design.md) (the Phase 4 design, one per
  feature).
- `.github/PULL_REQUEST_TEMPLATE/uplevel.md`: the PR template every package uses.
