# 20 — Frontend Lane

> Owns `frontend/` (including `frontend/docker-entrypoint.sh`, the nginx config) and the feature
> inventory at `docs/reference/feature-inventory.md`. Read [`README.md`](README.md) first: its
> vocabulary, contract and rulings (`UR-n`) bind every package here. Evidence: [`00-audit.md`](00-audit.md).

Work the phases in order. Inside a phase, packages are independent unless a package names a
dependency. One package per PR.

---

## Phase 1 — Stop the bleeding

### F1.1 Endpoint truth (D2)

**Files:** `frontend/src/services/api.ts`, `frontend/src/hooks/useHouseholdApi.ts`, a new contract
test under `frontend/src/__tests__/`, a known-missing list beside it.

The Cameras settings page calls `/api/cameras/{id}/anomalies`; the backend serves
`/api/cameras/{camera_id}/baseline/anomalies`. Four more client paths are absent from
`docs/openapi.json` (`00 §3` D2). Every test passes because every layer mocks the API.

- [ ] Write the failing contract test: every method and path the client calls exists in
      `docs/openapi.json`. Cover `fetchApi` callers and the ~24 hooks that call `fetch(` directly.
      **DECIDE** the mechanism: a static scan of the URL templates, or typing the client's path
      argument against the generated `paths` type so a wrong path fails to compile.
- [ ] Fix the anomalies path. Check that the response shape (`AnomalyListResponse`) matches what
      `CameraAnomalyTimeline` renders.
- [ ] Put the other four paths (`/api/jobs/{id}/retry`, `/api/events/{id}/entity-matches`,
      `/api/debug/profile/download`, `/api/household/members/{id}/detections`) on the known-missing
      list, each pointing to `00 §3` D2. Each is a half-built seed for `F2.2`, which replaces the
      pointers with inventory row ids; the list drains as `R2` rulings land.

**Done when:** the contract test runs in CI and fails on any mismatch not on the known-missing
list; the PR shows the anomaly timeline's request answered `200` by a running backend.

### F1.2 Verdict-engine banner (UR-18, frontend part)

**Depends on:** `B1.4`.

- [ ] Write the failing component test: when engine state is `unavailable`, a persistent banner
      reads that the verdict engine is unavailable since a time and that new events need review;
      it clears when the state returns to `available`.
- [ ] Read the state from `B1.4`'s readiness field on load and its WebSocket event afterwards.

**Done when:** the test passes, and the PR shows the banner appearing and clearing as `ai-vlm` is
stopped and started on a running stack.

### F1.3 Exposure and auth, frontend part (D10; OD-12)

**Depends on:** `B1.5` (its design note fixes the credential and session mechanism).

**Files:** `frontend/docker-entrypoint.sh`, the auth context and login flow, `fetchApi`'s error
handling, the WebSocket manager.

- [ ] Write the failing tests: a `401` from `fetchApi` routes to login; the WebSocket manager
      attaches the credential.
- [ ] nginx forwards the credential `B1.5` chose to `/api` and `/ws`.
- [ ] A login screen appears only when the backend reports auth required.

**Done when:** on a running stack with `EXPOSE_LAN=true` the UI requires login and works after it,
and with `EXPOSE_LAN` unset no login appears. The PR carries both runs. If `O1.6` has already
landed, this PR marks ISS-029 done in the register.

---

## Phase 2 — Feature truth

### F2.1 Golden-path harness

**Depends on:** `O2.1` (fake AI stack), `O2.2` (harness script).

**Files:** `frontend/playwright.config.ts` (a new `golden` project), `frontend/tests/golden/`.

- [ ] Add a Playwright project with **no API mocking**, pointed at the stack `O2.2` brings up.
      A guard fails the run if any spec in the project calls `page.route` on `/api` or `/ws`, so
      mocks cannot creep back in.
- [ ] Write the first golden path: a fixture image dropped into a camera folder (through `O2.2`'s
      helper) → an event on the dashboard carrying the fake VLM's verdict → the event detail shows
      its score and summary.

**Done when:** the `golden` project runs green inside `O2.2`'s CI job on the fake stack, and a
deliberately mocked spec in it fails the guard.

### F2.2 Feature inventory (UR-13)

**Files:** create `docs/reference/feature-inventory.md`; edit `frontend/knip.json`, fill
`docs/uplevel/r2-sheet.md` (it exists; fill it around its §2b, never copy the template over it)
and set the `next` fields of `frontend/src/__tests__/api-endpoint-contract-known-missing.json`
(owner, 2026-10-09). Read-only everywhere else.

The long-lived map of the product. Start from the seeds in `00 §10`; re-verify each one.

- [ ] Enumerate every feature: each route in `App.tsx`, each panel, tab and modal reachable from
      them, each user action that calls the API, each settings toggle, and the external interfaces
      (inbound webhooks, MQTT commands).
- [ ] Trace each one: component → API calls → backend route → service → store. List its modules
      in every lane.
- [ ] Give each a status with evidence: **unverified** (appears to work; `F2.3` decides),
      **half-built** (cite the stub, the missing endpoint, or the false success, by file and line),
      or **leftover** (cite the retirement).
- [ ] Fix `knip.json` so it can see unreachable files: entry points are `src/main.tsx` and config
      files (tests are not entries); `exports` checking on; the six ignore entries that name
      deleted files removed. Today's config hides them (`00 §4.3`).
- [ ] Attach the **modules serving no feature**: the non-shipping lists from `O2.3` (Python) and
      `npx knip --production` (frontend), minus every module some row claims.
- [ ] Replace `F1.1`'s known-missing pointers with inventory row ids.
- [ ] **DECIDE** the row format. It carries at least: id, surface, action, API calls, backend
      route/service/store, status, evidence, modules, real-tier last verified, ruling, priority.
- [ ] Prepare the `R2` sheet: copy [`templates/r2-sheet.md`](templates/r2-sheet.md) to
      `docs/uplevel/r2-sheet.md` and fill it — every half-built and leftover feature, OD-7 and
      OD-17 with the facts the inventory found, and the modules serving no feature.

**Done when:** every route in `App.tsx` and every API-calling action maps to a row; every row has a
status with evidence; the module list is attached; the `R2` sheet is drafted (`F2.3` finalises it).

### F2.3 Golden paths for every working feature

**Depends on:** `F2.1`.

- [ ] Write a golden path for every **unverified** row. A green golden path promotes the row to
      **works** once the real tier confirms it; a golden path that cannot pass demotes the row to
      **half-built**, with the failure as its evidence, and adds it to the `R2` sheet.
- [ ] The operator runs the real tier (`scripts/feature-check.sh --real`) and the inventory records
      the date per row.

**Lanes** (owner ruling 87). `F2.3` is split by feature area across the fast-model agents; the
heavy agents take none of it.

- **Frontend** owns `F2.3`: the shared harness, the split and the UI batches it keeps. On `F2.1`'s
  merge it posts the split on the batch issue: the **unverified** rows grouped into area batches,
  each named with its rows and its agent.
- **Backend** takes the rows whose evidence is an external API behaviour, as pytest specs in
  `backend/tests/golden/` (the contract in `O2.2`'s PR body, #6961).
- **ops-a** (after `O2.3b`) and **docs** take UI batches as `golden` Playwright specs.
- **One claim PR per agent** (owner ruling 97): each agent carries all its batches in one draft
  claim PR.
- **Files:** a batch touches only `frontend/tests/golden/<area>/` or `backend/tests/golden/<area>/`
  and its own rows in the inventory. Frontend reviews every batch; a batch that needs a harness
  change asks frontend for it.
- **The guard stands:** `F2.1`'s no-mocking guard applies to every batch. A path that cannot pass
  demotes its row as above, for `R2b`.
- **Operator:** records real-tier dates per batch as batches merge, under `O2.2`'s `--real` (the
  real VLM, a fake detector; owner ruling 66).

**Done when:** no row says **unverified**; every **works** row cites a green golden path and a
real-tier date; the `R2` sheet is final.

### Record `R2`

After the owner's ruling session, this lane writes the record in one PR: each ruling and priority
into the inventory's ruling column, the OD-7 and OD-17 rulings into
`docs/vss-integration/17-action-plan.md`, and `R2` set to `done` in the README status table. Every
Phase 3 package waits on this PR.

**Ruling 86 split the session into `R2a` and `R2b`.** This section ran for `R2a` — the sheet as it
stood — on 2026-10-10 (#6980): rulings and tiers into the inventory, and OD-7, OD-17 and OD-33 – OD-39
into `docs/vss-integration/17-action-plan.md`. A Phase 3 package may start once that PR and the owner’s
plan PR carrying ruling 86 have merged, if it touches only `R2a`-ruled features and modules. `R2b` —
the rows `F2.3` demotes plus the sheet’s §3 — is recorded the same way after the owner’s `R2b` session;
`R2` is `done` only when both records are.

---

## Phase 3 — The tree matches the rulings

Starts after `R2`. The inventory's ruling column is the input.

### F3.1 Retire ruled-out features, frontend part

Lands in the same PR as `B3.1`, feature by feature, starting with OD-20's enrichment surface.

- [ ] For each feature ruled **retire**: delete its routes, components, hooks, types, stores, MSW
      handlers, tests, snapshots, visual baselines and Playwright specs, and its `docs/ui/` page.

**Done when:** for every retired feature, a grep for the identifiers its inventory row lists finds
nothing in `frontend/`.

### F3.2 Unreachable files and the knip gate

- [ ] **MEASURE** the unreachable production files (236 files, ~71,800 lines at `d6ba78d5`,
      `00 §4.3`). Delete them and the tests that test only them — except files a **complete**
      feature's row claims, which stay and go on knip's ignore list with that row's id.
- [ ] Remove the dead contexts and stores, the duplicate `Result`, `ModelContributionChart`,
      `BulkActionBar` and toast implementations, the stale `modulePreload` filter in
      `vite.config.ts`, and `bun.lock` (CI and the Dockerfile run `npm ci`).

**Done when:** `npx knip --production` exits 0 and the PR reports files and lines removed. (`O3.4`
wires it into CI.)

### F3.3 Quarantined tests

`vite.config.ts` excludes 16 test files; three are empty.

- [ ] Fix or delete each excluded file.

**Done when:** the exclusion list is empty, or every remaining entry carries a reason and an
inventory row.

---

## Phase 4 — Complete the product

### Feature track (`F4.n`)

The frontend parts of each feature package in `10-backend.md`'s feature track, running the same
six steps. This lane writes the UI golden paths and sets the inventory row to **works**.

### Background track (`FB.n`)

Each package opens with a design session against the code that remains.

| package | target                                                                                                                                             | evidence |
| ------- | -------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| FB.1    | The generated client: replace the 369 hand-written interfaces that shadow generated names, and route the ~24 raw `fetch(` hooks through one client | `00 §5`  |
| FB.2    | Test helpers: `src/test/`, `src/test-utils/` and `src/__tests__/` become one; duplicate hook tests merge                                           | `00 §6`  |
| FB.3    | Server state: health data has five implementations; `setInterval` polling (43 files) and react-query settle on one approach                        | `00 §5`  |
| FB.4    | Modals: four patterns become one                                                                                                                   | `00 §5`  |

**Done when** (every background package): one implementation remains, and its tests pass.

---

## Kickoff prompt

Paste this to the agent taking the frontend lane.

```text
You are the frontend lane of the uplevel programme. Read docs/uplevel/README.md
(vocabulary, contract, rulings), then docs/uplevel/20-frontend.md, then the
docs/uplevel/00-audit.md sections each package cites.

Take the package the coordinator assigns you. Otherwise claim one yourself: the
lowest-numbered package in your current phase that is "not started", not
flagged heavy, unclaimed (no open draft PR titled [<package>]) and whose
dependencies are merged. Claim it by opening that draft PR with
gh pr create --draft --template uplevel.md (docs/uplevel/50-coordination.md).
If every remaining package in your phase waits on another lane, take the next
phase's first ready package; never start Phase 3 before R2 is done.

One package per PR. Write the failing test first. Before marking the PR ready,
dispatch a fresh-context subagent to self-review it against the package's Done
when, and record what it found. Keep commit subjects at 72 characters or fewer.
The PR sets the package's README status row to done, with its number, when it
merges.

Reviews come first (UR-32). Before you start or resume a package, run
gh pr list --state open --label review:frontend; review each PR independently against
its package's Done when, the contract and the hot-file rules, post the review
comment in the form 50-coordination.md gives, and remove the label.

Read your own open PRs before resuming a package (UR-35): gh pr view <n>
--comments for each. An owner ruling or a requested change there comes before
new work; nobody tells you about a comment except by writing it.

State only what you have just read (UR-31): every commit, PR, file, test result
and question you cite comes from output you ran in the same turn.

You own frontend/ and docs/reference/feature-inventory.md. The README's
cross-lane rule governs every other file you touch. When the plan does not
answer a question, stop and report the question.

Never wait inside a turn on CI, a check run or a background watcher: read it
once, report what you see and end the turn; your next tick re-reads (UR-38).
```
