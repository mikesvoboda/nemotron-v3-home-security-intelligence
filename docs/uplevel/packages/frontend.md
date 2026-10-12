# Frontend packages

Open packages of the frontend lane: every package whose row in the
[README status table](../README.md#status) is not `done`. How to claim, build, review and merge
one is in [`../rules.md`](../rules.md) and [`../roles/lane.md`](../roles/lane.md). Finished
packages are in [`../history/packages-done.md`](../history/packages-done.md).

## Lane scope

- The lane owns `frontend/` (including `frontend/docker-entrypoint.sh` and the nginx config) and the
  feature inventory at `docs/reference/feature-inventory.md`. Evidence for every package is in
  [`00-audit.md`](../00-audit.md); `00 §n` cites its sections.
- The lane records the `R2` session: the rulings, priorities and OD decisions go into the inventory
  and `docs/vss-integration/17-action-plan.md` (`R2b` below).
- The inventory's ruling column is the input to every Phase 3 package.
- Phase 4 runs in the priority order the inventory's priority column records: `R2a`'s tiers P1–P4
  (ruling 89) and `R2b` round 1's (ruling 135).

## Phase 1 — Stop the bleeding

### F1.2 Verdict-engine banner (UR-18, frontend part)

**Flags:** none. **Depends on:** `B1.4`.

- [ ] Write the failing component test: when engine state is `unavailable`, a persistent banner
      reads that the verdict engine is unavailable since a time and that new events need review;
      it clears when the state returns to `available`.
- [ ] Read the state from `B1.4`'s readiness field on load and its WebSocket event afterwards.

**Done when:** the test passes, and the PR shows the banner appearing and clearing as `ai-vlm` is
stopped and started on a running stack.

## Phase 2 — Feature truth

### F2.3 Golden paths for every working feature

**Flags:** none; the heavy agents take none of it (ruling 87). **Depends on:** `F2.1`. Its status is
`in progress` (UR-144).

- [ ] Write a golden path for every **unverified** row. A green golden path moves the row to
      **awaiting real tier**, citing the spec (owner ruling 103), and the real tier promotes it to
      **works**; a golden path that cannot pass demotes the row to **half-built**, with the failure
      as its evidence, and adds it to the `R2` sheet.
- [ ] The operator runs the real tier (`scripts/feature-check.sh --real`) and the inventory records
      the date per row.
- [ ] Rows demoted only because the CI stack cannot reach them (UR-153) are reached this way:
  - **Real tier:** the Grafana and GPU rows (F-102, F-115, F-117, F-164–F-167, F-169, F-174; F-176,
    F-178, F-182) get their witness from the `O2.5` run. If `O2.5`'s spike says no, they are
    checked on the test deployment in the per-batch real-tier runs, and ops adds what they need to
    the test deployment's compose (rulings 127, 144).
  - **Seeded on CI:** a golden project with `DEBUG=true`, which covers the debug-gated rows and the
    request recorder; a fault seed behind the debug guard that trips a breaker and a threshold; a
    fixture that plants an orphan file; and a writable `runtime.env` in the CI compose. Ops-b owns
    the compose and harness changes; the lane that owns each row writes its spec (ruling 127).
- [ ] Which runs count as a witness for a row: rules.md §Test tiers and the real tier.

**Lanes** (owner ruling 87). `F2.3` is split by feature area across the fast-model agents.

- **Frontend** owns `F2.3`: the shared harness, the split and the UI batches it keeps. On `F2.1`'s
  merge it posted the split on #6854 (comment `6103539478`): the **unverified** rows grouped into
  area batches, each named with its rows and its agent. A change to the split goes as a comment on
  each affected agent's own `F2.3` claim PR (UR-157).
- **Backend** takes the rows whose evidence is an external API behaviour, as pytest specs in
  `backend/tests/golden/` (the contract in `O2.2`'s PR body, #6961).
- **ops-a** (after `O2.3b`) and **docs** take UI batches as `golden` Playwright specs.
- **One claim PR per agent** (UR-56).
- **Files:** a batch touches only `frontend/tests/golden/<area>/` or `backend/tests/golden/<area>/`
  and its own rows in the inventory. Frontend reviews every batch; a batch that needs a harness
  change asks frontend for it. For its own skips and `xfail`s only, a batch may also touch the
  suppression files they require — `.github/suppression-baseline.json`,
  `.github/suppression-registry.yml` and `.secrets.baseline` (UR-83),
  one `HOST_JUSTIFIED` entry per skip site in `scripts/suppression-registry-gen.py`, and the
  matching count in `scripts/test_suppression_census.py` — and the shared
  `backend/tests/golden/__init__.py` (owner rulings 104 and 111). A batch touching `scripts/` or
  `.github/` also gets ops-b's review of those hunks.
- **The guard stands:** `F2.1`'s no-mocking guard (UR-127) applies to every batch. A path that
  cannot pass demotes its row as above, for `R2b`.
- **Operator:** records real-tier dates per batch as batches merge, under `O2.2`'s `--real` (the
  real VLM, a fake detector; owner ruling 66).

**Done when:** no row says **unverified**; every **works** row cites a green golden path and a
real-tier date; the `R2` sheet is final.

### R2b Phase 2 RULING session, part 2 (after `F2.3`)

**Flags:** `owner`; the owner rules, the frontend lane records. **Depends on:** `F2.3`'s demotions,
round by round.

After each of the owner's ruling sessions or rounds, this lane writes the record as UR-149 says;
the OD rulings it carries are OD-7 and OD-17, and OD-33 – OD-39 for `R2a`. When `R2` is `done`:
UR-148.

**Ruling 86 split the session into `R2a` and `R2b`.** `R2a` — the sheet as it stood — was recorded
on 2026-10-10 (#6980). `R2b` rules the rows `F2.3` demotes plus the sheet's §3, and is recorded the
same way after the owner's `R2b` session.

- **Rounds** (UR-148). Round 1 ruled the 41 `half-built` rows with an empty ruling column at
  `9bc51ece0`; rows `F2.3` demotes later are ruled in a later round, each recorded as above.
- **Round 1's record** (ruling 135): one PR writes rulings 127–135 into the inventory's ruling and
  priority columns for the 41 rows, returns ruling 127's 22 rows to **unverified** with their
  reachability notes, sets `R2b` to `in progress` in the README status table, and carries no code
  change.
- Which Phase 3 packages may start after a round's record merges: UR-66.

**Done when:** the last `R2b` round is recorded and the README row reads `done` (rulings 86, 127).

## Phase 3 — The tree matches the rulings

### F3.1 Retire ruled-out features, frontend part

**Flags:** `heavy · owner`. **Depends on:** `R2` (rules.md §Claiming and assigning work).

Lands in the same PR as `B3.1`, feature by feature, starting with OD-20's enrichment surface.

- [ ] For each feature ruled **retire**: delete its routes, components, hooks, types, stores, MSW
      handlers, tests, snapshots, visual baselines and Playwright specs, and its `docs/ui/` page.
- [ ] `R2b` round 1's retirements and splits (frontend only, no backend part):
  - **F-022, rate-limit indicator** (ruling 132): the pill stays and reads "Rate limited,
    retrying…" with no count, limit or time; the countdown overlay, the invented defaults in
    `updateRateLimitStoreFromError` (`frontend/src/services/queryClient.ts:249-297`) and any store
    fields only it reads are deleted. The flipped spec asserts the pill and that no countdown or
    number renders.
  - **F-023, the in-page PWA install prompt** (ruling 133): delete
    `frontend/src/components/pwa/InstallPrompt.tsx`, its 2-visit and 30 s engagement gates, its
    7-day dismissal store and its tests, including `frontend/tests/golden/shell/pwa-install.spec.ts`.
    `frontend/public/manifest.json`, `/sw.js` and their registration stay.
  - **F-135, batch statistics** (ruling 134): the active-batches view stays; the closure-reason
    chart, the per-camera table and the completed-batch timeline go, in
    `frontend/src/components/batch/BatchStatisticsDashboard.tsx` and any hook or type only those
    three views use.

**Done when:** for every retired feature, a grep for the identifiers its inventory row lists finds
nothing in `frontend/`.

### F3.2 Unreachable files and the knip gate

**Flags:** none. **Depends on:** `R2`.

- [ ] **MEASURE** the unreachable production files (236 files, ~71,800 lines at `d6ba78d5`,
      `00 §4.3`). Delete them and the tests that test only them — except files a **complete**
      feature's row claims, which stay and go on knip's ignore list with that row's id.
- [ ] Remove the dead contexts and stores, the duplicate `Result`, `ModelContributionChart`,
      `BulkActionBar` and toast implementations, the stale `modulePreload` filter in
      `vite.config.ts`, and `bun.lock` (CI and the Dockerfile run `npm ci`).

**Done when:** `npx knip --production` exits 0 and the PR reports files and lines removed. (`O3.4`
wires it into CI.)

### F3.3 Quarantined tests

**Flags:** none. **Depends on:** `R2`.

`vite.config.ts` excludes 16 test files; three are empty.

- [ ] Fix or delete each excluded file.

**Done when:** the exclusion list is empty, or every remaining entry carries a reason and an
inventory row.

## Phase 4 — Complete the product

### F4.\* Feature track, frontend parts

**Flags:** design: `heavy`. **Depends on:** `R2`'s ruling and priority for the feature.

The frontend parts of each feature package in the backend lane's feature track
([`backend.md`](backend.md), `B4.*`), running the same six steps. This lane writes the UI golden
paths and sets the inventory row to **works**. Features rulings have already shaped:

- **Trash** (F-087 with R2a's F-088; P1; one package): a Delete action in the event detail modal and
  a bulk Delete on the timeline, both calling the existing soft-delete routes
  (`DELETE /api/events/{id}`, `routes/events.py:2713`, and the bulk delete, `:1780`), so deleted
  events land in `/trash`; no backend change is expected. Golden path: delete an event from the UI,
  find it in `/trash`, restore it, then delete it permanently; it replaces the spec's API-side
  seeding (rulings 131, 135).
- **Monitoring** (F-102, F-115, F-117, F-164–F-167, F-169, F-174; P3): one Monitoring page with a
  dashboard picker over the provisioned dashboards, built on one shared embed component, replaces
  the eight wrapper pages and their routes (`AIServicesPage`, `PyroscopePage`,
  `OperationsDashboardPage`, `GpuMetricsPage`, `RequestProfilingPage`, `TracingPage`, `LogsPage`,
  `VideoAnalyticsPage`); the sidebar's per-dashboard entries become one Monitoring entry. `/ai`
  keeps its Model Zoo section (F-104), and its dashboard half moves into the picker. The embed works
  on the real stack: Grafana's embedding setting and the frame policy, behind the app's login
  (`O1.11`, UR-33). The golden path drives the picker on the test deployment. The design session
  settles the picker's list, deep links and old-route redirects. Until it is built, Grafana stays
  reachable directly behind `O1.11`'s login (rulings 128, 135).

### FB.\* Background track

**Flags:** none. **Depends on:** none named.

Each package opens with a design session against the code that remains.

| package | target                                                                                                                                             | evidence |
| ------- | -------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| FB.1    | The generated client: replace the 369 hand-written interfaces that shadow generated names, and route the ~24 raw `fetch(` hooks through one client | `00 §5`  |
| FB.2    | Test helpers: `src/test/`, `src/test-utils/` and `src/__tests__/` become one; duplicate hook tests merge                                           | `00 §6`  |
| FB.3    | Server state: health data has five implementations; `setInterval` polling (43 files) and react-query settle on one approach                        | `00 §5`  |
| FB.4    | Modals: four patterns become one                                                                                                                   | `00 §5`  |

**Done when** (every background package): one implementation remains, and its tests pass.

## Ruling-ordered fixes

Fixes an owner ruling ordered outside the phase order. Each keeps the ruling's tag as its id, queues
where its ruling says, and takes the normal queue and review (UR-113). None has a README status row;
the PR that finishes one updates its row in [`../history/ruling-map.md`](../history/ruling-map.md).

### [r130f] Small bugs from `F2.3`'s demotions, frontend half

**Flags:** none. **Assigned:** frontend, as lane bug fixes outside Phase 4's priority order.
**Depends on:** none; it runs in parallel with backend's `[r130b]`. **PR:** none yet.

- [ ] **F-125, F-129.** `/settings/ai-models` crashes on every load: `StatusIndicator` destructures
      `config[status]`, and `GET /api/system/models` sends no `status` field at all
      (`model_management.py:631-639`). Give the indicator a fallback; whether the API should send a
      status is for the package to decide, and if it should, that half is backend's.
- [ ] **F-158.** Map `body.config` instead of the envelope (`useDebugConfigQuery.ts:91`), so the
      settings show and the redaction fires.
- [ ] **F-017.** Make the Sidebar mount gate (`Layout.tsx:93`, `< 640`) and the hamburger
      (`Header.tsx:287`, `md:hidden`) agree on what "mobile" means.
- [ ] **F-021.** No tour step may target an element that never renders (`tourSteps.ts:115`, `:124`,
      `:133`); fix the steps or the targets.
- [ ] **F-020.** Share settings state between the panel and `AmbientStatusProvider`, so a toggle
      takes effect in the same tab.
- [ ] **F-038.** Render the DLQ count the row promises (`dlqItems` currently has no render site), or
      drop the clause from the row. Frontend picks one and says which.
- [ ] **F-034.** If frontend adds an `/events/:id` redirect, backend's `[r130b]` leaves its link
      line alone; one side changes, not both.

**Done when:** for each row, its golden spec, already written to pin the broken behaviour, is
flipped to assert the fix and passes (ruling 130).
