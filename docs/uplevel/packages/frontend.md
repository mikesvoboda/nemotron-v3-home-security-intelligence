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

**Flags:** none; the heavy agents take only FE-4 and OP-1 (rulings 87, 184). **Depends on:** `F2.1`. Its status is
`in progress` (UR-144).

- [ ] Write a golden path for every **unverified** row. A green golden path moves the row to
      **awaiting real tier**, citing the spec (owner ruling 103), and the real tier promotes it to
      **works**; a golden path that cannot pass demotes the row to **half-built**, with the failure
      as its evidence, and adds it to the `R2` sheet.
- [ ] The operator runs the real tier (`scripts/feature-check.sh --real`) and the inventory records
      the date per row.
- [ ] Rows demoted only because the CI stack cannot reach them (UR-153) are reached this way:
  - **Real tier:** the GPU rows (F-176, F-178, F-182) and six Grafana rows (F-164–F-167, F-169,
    F-174) get their witness from `O2.5`'s item 2 (rulings 256, 323). F-102, F-115 and F-117 get
    theirs from the Monitoring package's golden path, and F-295 and F-296 from `[r323b]` (ruling
    323).
  - **Seeded on CI:** a golden project with `DEBUG=true`, which covers the debug-gated rows and the
    request recorder; a fault seed behind the debug guard that trips a breaker and a threshold; a
    fixture that plants an orphan file; a writable `runtime.env` in the CI compose; and, after the
    OP-1 rows flip, a small volume filled past 90 % at the parent of `VIDEO_THUMBNAILS_DIR` for
    F-012. heavy-a builds the compose and harness changes (heavy-b's work while it is out of
    service) and ops-b reviews them, as a CI job separate from `Feature check (fake AI)`; the lane
    that owns each row writes its spec (rulings 127, 187, 190, 192).
- [ ] Which runs count as a witness for a row: rules.md §Test tiers and the real tier.

**Lanes** (owner ruling 87). `F2.3` is split by feature area across the fast-model agents, and ruling
184 gives two batches to the heavy agents.

- **Frontend** owns `F2.3`: the shared harness, the split and the UI batches it keeps. On `F2.1`'s
  merge it posted the split on #6854 (comment `6103539478`): the **unverified** rows grouped into
  area batches, each named with its rows and its agent. A change to the split goes as a comment on
  each affected agent's own `F2.3` claim PR (UR-157).
- **Backend** takes the rows whose evidence is an external API behaviour, as pytest specs in
  `backend/tests/golden/` (the contract in `O2.2`'s PR body, #6961).
- **ops-a** (after `O2.3b`), **ops-b** and **docs** take UI batches as `golden` Playwright specs. An
  ops cell with no batch opens its claim PR, `[F2.3] claim: <cell> golden UI batch`, and frontend
  names the batch's `unverified` rows, from rows no open batch holds, in a comment on that PR within
  its next tick (ruling 150).
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
- **The last idle rows** (ruling 191): docs flips F-256, then writes the specs for F-254 and F-278
  (F-278 follows UR-153 if the fake stack cannot seed a face embedding); frontend writes FE-3's six
  unwritten rows (F-045, F-052–F-054, F-059, F-064) after its `[r134]` PR #7145. Ruling 192 adds
  two rows whose legs skip on CI: frontend fixes F-028's leg 2 with F-007's offline-then-reload
  approach, and docs makes F-234's notification grant take effect or returns the row to the owner;
  docs tests the grant with `channel: 'chromium'` set in `permission.spec.ts` alone, leaving the
  golden project's config unchanged (ruling 194).

**Done when:** no row says **unverified** except the rows `O2.5` witnesses (ruling 127's 12,
F-295 and F-296; UR-10, ruling 237); every **works** row cites a green golden path and a real-tier
date; the `R2` sheet is final.

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
- **Ruling 182's record** (record `6174228588`, BINDING NOW 17:24Z): #7131 (merged) writes that
  record's seven rows into the ruling and priority columns. It moves no status, so §2 is not in its
  diff and it merges in any order with the three PRs that rewrite the `**all**` line.
- **Round 2's record** (rulings 210-215): the owner's session writes it in the owner PR that carries
  them (ruling 216, record 6200852082), into the ruling and priority columns only; later rounds
  return to this lane.
- Which Phase 3 packages may start after a round's record merges: UR-66.
- **The last round** (rulings 233-236, closed by ruling 237): F-045 and F-052 are complete, P1,
  fix now (`[r211f]` and `[r234]`); seeded-only rows reach **works** on a `--real --seeded` run
  (`[r235]`); `POST /api/reid/search` retires with `B3.1`, and the household embeddings and
  detections export endpoints become External rows (`[r236]`). The owner's session writes its
  record (ruling 237), as it did round 2's.

**Done when:** the last `R2b` round is recorded and the README row reads `done` (rulings 86, 127).

## Phase 3 — The tree matches the rulings

### F3.1 Retire ruled-out features, frontend part

**Flags:** `heavy`; `owner` for a retirement UR-98's plain-retirement exception does not cover
(ruling 249). **Depends on:** `R2` (rules.md §Claiming and assigning work).
**Assigned:** heavy-a, with `B3.1` and in its order (ruling 241). **PR:** #7220, #7224, #7228, #7232, #7233, #7243, #7247, #7249, #7253, #7254, #7255, #7258, #7261, #7266, #7270, #7272, #7273, #7277, #7286, #7300, #7304, #7309, #7311.

Lands in the same PR as `B3.1`, one R2a row per PR (ruling 255; `B3.1` states the rule), starting
with OD-20's enrichment surface.

- [x] For each feature ruled **retire**: delete its routes, components, hooks, types, stores, MSW
      handlers, tests, snapshots, visual baselines and Playwright specs, and its `docs/ui/` page.
- [x] `R2b` round 1's retirements and splits (frontend only, no backend part):
  - **F-022, rate-limit indicator** (ruling 132): the pill stays and reads "Rate limited,
    retrying…" with no count, limit or time; the countdown overlay, the invented defaults in
    `updateRateLimitStoreFromError` (`frontend/src/services/queryClient.ts:249-297`) and any store
    fields only it reads are deleted. The flipped spec asserts the pill and that no countdown or
    number renders.
  - **F-023, the in-page PWA install prompt** (ruling 133): delete
    `frontend/src/components/pwa/InstallPrompt.tsx`, its 2-visit and 30 s engagement gates, its
    7-day dismissal store and its tests, including `frontend/tests/golden/shell/pwa-install.spec.ts`.
    `frontend/public/manifest.json` and its registration stay, and so does `/sw.js` — which is
    never a tracked file: `frontend/vite.config.ts:59`'s `VitePWA(...)` generates it at build.
  - **F-135, batch statistics** (ruling 134): the active-batches view stays; the closure-reason
    chart, the per-camera table and the completed-batch timeline go, in
    `frontend/src/components/batch/BatchStatisticsDashboard.tsx` and any hook or type only those
    three views use.

**Done when:** for every retired feature, a grep for the identifiers its inventory row lists finds
nothing in `frontend/`.

### F3.2 Unreachable files and the knip gate

**Flags:** none. **Depends on:** `R2`.
**PR:** #7246. (ruling 241)

- [x] **MEASURE** the unreachable production files (236 files, ~71,800 lines at `d6ba78d5`,
      `00 §4.3`). Delete them and the tests that test only them — except files a **complete**
      feature's row claims, which stay and go on knip's ignore list with that row's id.
- [x] Remove the dead contexts and stores, the duplicate `Result`, `ModelContributionChart`,
      `BulkActionBar` and toast implementations, the stale `modulePreload` filter in
      `vite.config.ts`, and `bun.lock` (CI and the Dockerfile run `npm ci`).

**Done when:** the PR reports files and lines removed, and records in its body what `npx knip
--production` still reports at its head (unused exports, files and dependencies) as not cleared:
that is the baseline `O3.4` pins, so "exits 0" reads relative to it (ruling 257). `knip.json` keeps
`exports: "error"`, and the PR does not edit the 239 kept modules to clear their unused exports.
(`O3.4` wires the gate into CI.)

### F3.3 Quarantined tests

**Flags:** none. **Depends on:** `R2`.
**PR:** #7325. (ruling 241)

`vite.config.ts` excluded 13 test files (the R-T7-VITEST set: 62 deterministic
test-drift failures quarantined 2026-09-12, later shrank to 13 when F3.2 found
three of the 16 entries named files no longer on disk).

- [x] Fix or delete each excluded file. All 12 remaining files repaired and
      green (634 passed | 3 skipped across the 12); one file deleted
      (`TimeGroupedEvents.simple.test.tsx`, empty scaffold with no suite left to
      run). The repair also surfaced two production bugs: the local
      `handleResponse` in `useHouseholdApi.ts` threw bare `Error`s, silently
      disabling the NEM-1940 smart-retry layer for every household endpoint (now
      throws `ApiError` so 503 retries and 500 does not), and
      `EventTimeline.tsx` passed a `snoozedUntil` prop EventCard does not read,
      so the NEM-3640 SnoozeBadge never rendered from the timeline page (now
      passes `snooze_until`).

**Done when:** the exclusion list is empty, or every remaining entry carries a reason and an
inventory row. The exclusion list is empty; the full unquarantined suite is green.

## Phase 4 — Complete the product

### F4.\* Feature track, frontend parts

**Flags:** design: `heavy`. **Depends on:** `R2`'s ruling and priority for the feature.

The frontend parts of each feature package in the backend lane's feature track
([`backend.md`](backend.md), `B4.*`), running the same six steps. This lane writes the UI golden
paths; the inventory row reads **works** once the operator records the real-tier check. Features rulings have already shaped:

- **Trash** (F-087 with R2a's F-088; P1): designed in [`../4n-trash.md`](../4n-trash.md) as two
  packages, `B4.4` then `F4.3`, each with its own golden path (rulings 131, 135, 308).
- **Monitoring** (F-102, F-115, F-117, F-164–F-167, F-169, F-174; P3): one Monitoring page with a
  dashboard picker over the provisioned dashboards, built on one shared embed component, replaces
  the eight wrapper pages and their routes (`AIServicesPage`, `PyroscopePage`,
  `OperationsDashboardPage`, `GpuMetricsPage`, `RequestProfilingPage`, `TracingPage`, `LogsPage`,
  `VideoAnalyticsPage`); the sidebar's per-dashboard entries become one Monitoring entry. `/ai`
  keeps its Model Zoo section (F-104), and its dashboard half moves into the picker. The embed works
  on the real stack: Grafana's embedding setting and the frame policy, behind the app's login
  (`O1.11`, UR-33). The golden path drives the picker on the test deployment. The design session
  settles the picker's list, deep links and old-route redirects. Until it is built, Grafana stays
  reachable directly behind `O1.11`'s login (rulings 128, 135). The package removes the zone panels
  from `monitoring/grafana/dashboards/video-analytics.json`, and F-117's inventory row says why:
  nothing in the product writes `hsi_zone*` since #7319 deleted `zone_crossing_service.py`, so the
  panels have never shown data. F-117 stays complete. The package's golden path is the witness for
  F-102, F-115 and F-117, which stay **unverified** until it lands (ruling 323). A future zone
  feature adds the panels back with a writer, and until then no PR adds a writer for `hsi_zone*`
  (ruling 301).

**The P1 packages' frontend parts** (ruling 308, record 6326364266), each with its design as step 1.
**The P2 packages' frontend parts** (ruling 317, record 6347331324) follow them: `F4.8`, `F4.6` and
`F4.7`. **The modes and debug tools packages** (ruling 321, record 6355356496): `F4.9` (heavy-a,
now) and `F4.10` (frontend, after `F4.7`).

### F4.4 Timeline filters and detections

**Flags:** none. **Assigned:** frontend, after `[r299]` (ruling 308). **Depends on:** none; its
small backend part (`min_confidence`) rides in the same PR (UR-9).
**PR:** #7352, #7362. (ruling 308, record 6326364266)

Design: [`../4n-timeline.md`](../4n-timeline.md). Covers F-044, F-055.

- [x] The test-only PR (step 2).
- [x] The build PR: `min_confidence` as a correlated `EXISTS`; the Verification select; the
      modal's detections from its own fetch; boxes on still images through `BoundingBoxOverlay`;
      `ThreatBoundingBox` retired. — #7362, gate green at `69e41badb` (CI run 39819713638).
- [x] Golden path (Playwright) as the design gives it. — #7362:
      `frontend/tests/golden/timeline/confidence-filter.spec.ts` (5 tests), witnessed green by
      the `Feature check (fake AI)` run above.

**Done when:** steps 4–6 hold for its rows.

### F4.1 The Alerts page

**Flags:** none. **Assigned:** frontend, after `F4.4` (ruling 308). **Depends on:** `B4.1`
merged; it runs beside `B4.2`. **PR:** #7367, #7370. (ruling 308, record 6326364266)

Design: [`../4n-alerting.md`](../4n-alerting.md), "Packages" row 2, beside `B4.2`. Covers F-078,
F-079.

- [x] The test-only PR (step 2).
- [x] The build PR: alert rows; Acknowledge, Dismiss, Snooze; the timeline's Snooze moves to
      activity snoozes; `alerts.spec.ts` and the snooze steps of `event-detail-modal.spec.ts`
      rewritten.
- [x] Golden path (Playwright): the alert appears live, then acknowledge, dismiss, snooze —
      `frontend/tests/golden/analytics-alerts/alerts.spec.ts`, witnessed green by this PR's CI
      `Feature check (fake AI)` run.

**Done when:** steps 4–6 hold for its rows.

### F4.3 The Trash UI

**Flags:** none. **Assigned:** frontend, after `F4.1` (ruling 308). **Depends on:** `B4.4`
merged. **PR:** none yet. (ruling 308, record 6326364266)

Design: [`../4n-trash.md`](../4n-trash.md), the `F4.3` parts. Covers F-087, F-088 with `B4.4`.

- [ ] The test-only PR (step 2).
- [ ] The build PR: Delete in `EventDetailModal`, bulk Delete on the timeline, the Undo toast;
      `permanentlyDeleteEvent` sends `?permanent=true`; Trash shows the deleted and purge dates;
      the setting under Settings › Data.
- [ ] Golden path (Playwright) as the design gives it; it replaces the spec's API-side seeding
      (ruling 135).

**Done when:** steps 4–6 hold for F-087 and F-088.

### F4.2 The rules dialog and Settings › Notifications

**Flags:** none. **Assigned:** frontend, after `F4.3` (ruling 308). **Depends on:** `B4.3`
merged. **PR:** none yet. (ruling 308, record 6326364266)

Design: [`../4n-alerting.md`](../4n-alerting.md), "Packages" row 4. Covers F-216, F-217, F-231,
F-232, F-235, F-236.

- [ ] The test-only PR (step 2).
- [ ] The build PR: as designed, the push subscription included; the channel checks of
      `alert-rules.spec.ts` and the UI steps of `notify.spec.ts` and `quiet-hours.spec.ts`
      rewritten; if `F4.5` landed first, the override's "In chosen modes" (ruling 311).
- [ ] Golden path (Playwright): the cluster's golden path.

**Done when:** steps 4–6 hold for its rows.

### F4.5 Arming in the UI

**Flags:** none. **Assigned:** frontend, after `F4.2` (ruling 311). **Depends on:** `B4.7` and
`F4.1` merged. **PR:** none yet. (ruling 311, record 6328311780)

Design: [`../4n-arming.md`](../4n-arming.md), "Packages" row `F4.5`. Covers F-290 with `B4.7`.

- [ ] The test-only PR (step 2).
- [ ] The build PR: the header arming chip; Settings › Arming (cameras per mode, schedule, change
      history); "raised while unarmed" on the Alerts page's rows; if `F4.2` landed first, the
      override's "In chosen modes"; if `B4.8` landed first, the MQTT section (enable, status, the
      TLS warning, the token shown once) and its Playwright step.
- [ ] Golden path (Playwright) as the design gives it.

**Done when:** steps 4–6 hold for its rows.

### F4.8 System status in the UI (contract)

**Flags:** `owner` (it retires control routes, re-enables host-privileged self-healing and builds
the shared admin check, UR-98; ruling 321). **Assigned:** frontend, after `F4.5` (ruling 317).
**Depends on:** `B4.11` merged.
**PR:** none yet. (ruling 317, record 6347331324; ruling 321, record 6355356496)

Design: [`../4n-status.md`](../4n-status.md), "Packages" row `F4.8`. Covers the status rows with
`B4.11`.

- [ ] The test-only PR (step 2): the hooks and components the design names, with their fixtures.
- [ ] The build PR: the header badge on `ai_service_status`; the dashboard row, the model cards and
      the services panel (Restart only, the sign-in prompt, Postgres no longer blocked); the shared
      `useIsAdmin` and `AdminSignInPrompt` that `F4.10` reuses (`4n-debug-tools.md`, DT5); the
      per-model latency chart; the banner's `ai-vlm`; the alert badge on the events socket with its
      page-open load; the palette and `g y`; Tracing's Tempo link. Its cross-lane part (UR-9):
      removes the old `nemotron` and `rtdetr` fields, moves the `ai_models` key, regenerates the
      contract and types, and edits `operations/performance.spec.ts:55` and `:66`; and it retires
      the enable, disable and `/start` service routes and the worker stop and start routes with
      their callers (the start, stop, enable and disable mutations in `useServiceMutations` and
      `useWorkerActions`, their clients and the panels' buttons), each pinned by a 404 test, and
      clears every persisted `enabled=false` once. It edits
      `operations/worker-management.spec.ts:88-113` (F-143's golden path) and F-143's row.
- [ ] Golden path (Playwright) as the design gives it.

**Done when:** steps 4–6 hold for its rows.

### F4.6 Scene changes in the UI

**Flags:** none. **Assigned:** frontend, after `F4.8` (ruling 317). **Depends on:** `B4.9` and
`F4.1` merged. **PR:** none yet. (ruling 317, record 6347331324)

Design: [`../4n-scene-changes.md`](../4n-scene-changes.md), "Packages" row `F4.6`. Covers F-008,
F-030 and F-288, and F-208 and F-287 with `B4.9`.

- [ ] The test-only PR (step 2): `useSceneChangeAlerts`, `useSceneChangeEvents`,
      `useSceneChangesQuery`, `SceneChangePanel`, `SceneChangesPage` and `SceneChangeIndicator`.
- [ ] The build PR: the header badge, the dashboard indicator and toasts on open and cleared; the
      camera modal's incidents with their pictures and "Set as normal"; the Scene changes page on
      `GET /api/scene-changes` with its filters and state; Acknowledge with "This is the new
      normal"; the drifted incident's text.
- [ ] Golden path (Playwright) as the design gives it.

**Done when:** steps 4–6 hold for its rows.

### F4.7 Exports in the UI

**Flags:** none. **Assigned:** frontend, after `F4.6` (ruling 317). **Depends on:** `B4.10` merged.
**PR:** none yet. (ruling 317, record 6347331324)

Design: [`../4n-exports.md`](../4n-exports.md), "Packages" row `F4.7`. Covers F-051, F-098 and
F-099 with `B4.10`.

- [ ] The test-only PR (step 2): `ExportButton`, `ExportModal`, `ExportProgress`, `useExportJobs`
      and Data › Export; the e2e spec that mocks a missing route.
- [ ] The build PR: the button on `POST /api/exports` and `/download`, with every timeline filter;
      Events and Alerts in the modal and Data › Export, and the Backups link; Cancel through
      `DELETE` everywhere; the cancelled and expired states; the two old clients go. Its cross-lane
      part (UR-9): retires `POST /api/events/export` with its tracker job and
      `GET /api/events/export`, with their tests, a 404 test, the regenerated contract and types,
      and the docs that name them.
- [ ] Golden path (Playwright) as the design gives it.

**Done when:** steps 4–6 hold for its rows.

### F4.9 Easy and Advanced modes

**Flags:** `heavy`. **Assigned:** heavy-a, now (ruling 321; `[r320]` closed moot, ruling 320's
correction); it follows this block (UR-59). **Depends on:** none.
**PR:** #7376, #7380. (ruling 321, record 6355356496)

Design: [`../4n-modes.md`](../4n-modes.md), "Packages" row `F4.9`. Covers F-299 (new) and the rows
the design re-cites.

- [x] The test-only PR (step 2): one navigation fixture and one event-modal fixture for the tests of
      every file the build edits (the design's "Consolidation scope").
- [x] The build PR: `config/surfaces.ts` and `ViewModeContext`; `ModeSwitch`, `AdvancedOnly`,
      `HubTabBar` and `AdvancedBanner`; the sidebar, phone bar, palette, chords and help modal read
      the registry; the header, the event modal and Trends gate on the view mode; `SettingsPage`
      takes its heading and tab bar from the hub; `sidebarNav.ts` and `settingsTabsConfig.ts` go;
      every spec and unit test the design lists moves, with the `setMode` harness helper; the
      glossary, the inventory (F-299 and the re-cites) and the docs the design names (UR-81).
- [x] Golden path (Playwright, `shell/modes.spec.ts`) as the design gives it.

**Done when:** steps 4–6 hold for F-299, and the design's re-cited rows pass
`feature-inventory.test.ts`.

### F4.10 Debug tools in the UI (contract)

**Flags:** `owner` (ruling 89; it closes routes behind an auth check, UR-98). **Assigned:**
frontend, after `F4.7` (ruling 321). **Depends on:** `B4.12` and `F4.8` merged.
**PR:** none yet. (ruling 321, record 6355356496)

Design: [`../4n-debug-tools.md`](../4n-debug-tools.md), "Packages" row `F4.10`. Covers F-145,
F-151–F-159 and F-195 with `B4.12`.

- [ ] The test-only PR (step 2): the Developer Tools, Logging Settings and Databases panel tests.
- [ ] The build PR: the Developer Tools section, Logging Settings and the Redis INFO block render
      for an admin and show `F4.8`'s `AdminSignInPrompt` otherwise; the profiling client on
      `/profile/stats` and its `results`, Download on `B4.12`'s route, Clear all per recording;
      a new `operations/profiling.spec.ts`; every spec the design lists signs in as admin,
      `shell/rate-limit` always. Its cross-lane part (UR-9): `require_debug_mode` goes and the
      22 routes take `get_current_admin_user`; `scripts/feature_check.py` sends the harness
      admin's cookie, with `test_feature_check.py`; `scripts/load_test.py`; the backend tests
      the design names; the refusal leg of
      `backend/tests/golden/external/test_debug_access.py`; the contract's known-missing debug
      entries; the regenerated contract and types; the stale docstring, 404 responses and
      `backend/api/routes/AGENTS.md`.
- [ ] Golden path (Playwright and pytest) as the design gives it.

**Done when:** steps 4–6 hold for its rows, and the known-missing list holds no debug entry.

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
**Depends on:** none; it runs in parallel with backend's `[r130b]`. **PR:** #7039 (merged
2026-10-14T16:50:44Z as `01e02136d`, head `ec92ab3ec`; self-review dispositioned). The tick of its
boxes is this file's own register work, below.

- [x] **F-125, F-129.** `/settings/ai-models` crashes on every load: `StatusIndicator` destructures
      `config[status]`, and `GET /api/system/models` sends no `status` field at all
      (`model_management.py:631-639`). Give the indicator a fallback; whether the API should send a
      status is for the package to decide, and if it should, that half is backend's.
      Witness: the fallback is structural — the parent looked up
      `config[status]` bare (`ModelManagementPanel.tsx:81` at `932ec4aef`); at `origin/main` the
      lookup carries `?? FALLBACK` (`:119`) and the render status gained an `'unknown'` member
      (`ModelDisplayStatus`, `:72`, with its config entry at `:111`), so a missing `status` renders
      instead of throwing. CI's
      `Feature check (fake AI)` job `115961340950` (run 38594610450, head `ec92ab3ec`) passed the
      leg "the AI Models tab mounts its panel and mirrors both live model feeds". **Deviation from
      the `Done when`'s wording, stated rather than smoothed:** this row had NO golden spec before
      #7039 (`git log --diff-filter=A` on `settings/ai-models-panel.spec.ts` returns `0f0134bac`, an
      interior commit of that PR), so there was no pre-existing pin to flip; the box is ticked on the
      added spec passing, which is what the row's own `awaiting real tier` status already reflects.
- [x] **F-158.** Map `body.config` instead of the envelope (`useDebugConfigQuery.ts:91`), so the
      settings show and the redaction fires.
      Witness: `useDebugConfigQuery.ts:106` reads `const config = body?.config;` at `origin/main`. CI's
      `Feature check (fake AI)` job `115961340950` (run 38594610450) passed the leg "the table lists
      the settings map, not the envelope, and flags masked values" — a leg that fails both ways if
      either half regresses (`config-inspector.spec.ts:115` asserts `rowCount` equals
      `settingsKeys.length`, and `:78` floors that map above 50 keys). **Deviation, stated:** this
      spec is NEW at #7039 (`--diff-filter=A` → `2099deab6`, interior to that PR), so no pin was
      flipped here. **Credit refined, in the second surface's favour:** the same bug reached a second
      consumer — `LoggingSettings.tsx` read the envelope too and now reads `debugConfig?.config`
      (`:120`, changed by #7039), so the fix is broader than the inspector. The approving review
      (`6173593783`) counted `gpu-storage-admin/admin-logging` as that surface's golden witness; it is
      a legitimate consumer of the fixed hook, but it is not a witness of the flip: #7039 never edits
      that spec (`git diff --name-only 932ec4aef 01e02136d` omits it), it passed at the pre-fix
      baseline (main's 175 rows = 162 passed + the 13 skips that review names, none of them this
      spec), and no assert on its legs routes through `debugConfig.config` — the level assert compares
      against `GET /api/debug/log-level`, which `effectiveLevel` prefers (`:246`, ahead of the
      `loggingConfig` fallback), the slider is fed by `fetchConfig()` (`:138`, `/api/system/config`),
      and the one clause that would render the debug-config readout — "sees log file/DB config" — is
      the clause the spec itself declares NOT executed (`admin-logging.spec.ts:5-8`). What covers the
      second surface is the unit tier: `useDebugConfigQuery.test.ts`, +14/−11 in #7039.
- [x] **F-017.** Make the Sidebar mount gate (`Layout.tsx:93`, `< 640`) and the hamburger
      (`Header.tsx:287`, `md:hidden`) agree on what "mobile" means.
      Witness: the flip is a polarity inversion on one selector — `shell/nav.spec.ts:180` at
      `932ec4aef` asserted `getByTestId('sidebar')` `toHaveCount(0)` (the measured break) and `:267`
      at `origin/main` asserts `toHaveCount(1)`. CI's `Feature check (fake AI)` job `115961340950`
      (run 38594610450) passed both legs, desktop and "phone viewport (width < 640 ⇒ isMobile)". This
      also discharges the row's own deferral: `docs/reference/feature-inventory.md` F-017 promised
      "the golden witness for the shipped bytes is the first `Feature check (fake AI)` run on a ready
      head, named at the flip" — the shipped spec blob `653010eec` is byte-identical at `ec92ab3ec`
      and in the merged tree, so those are the bytes that ran.
- [x] **F-021.** No tour step may target an element that never renders (`tourSteps.ts:115`, `:124`,
      `:133`); fix the steps or the targets.
      Witness: `shell/tour.spec.ts:168` at `932ec4aef` asserted the tour overlay `toHaveCount(0)`;
      `:343` at `origin/main` asserts `tour.locator('[data-tour="risk-card"]')` `toHaveCount(1)`, i.e.
      the named target renders. Job `115961340950` (run 38594610450) passed all five legs, including
      "all 7 targets render on a camera-less stack" and "a hidden widget cannot kill the tour".
- [x] **F-020.** Share settings state between the panel and `AmbientStatusProvider`, so a toggle
      takes effect in the same tab.
      Witness: `shell/ambient.spec.ts:233` at `932ec4aef` asserted
      `expect(frozen.background, 'provider never re-read the settings jar').toBe(true)`; `:254` at
      `origin/main` asserts `expect(off.background).toBe(false)` — the toggle now lands in the same
      tab. Job `115961340950` (run 38594610450) passed all three legs, including the feed-truth
      cross-check against the backend.
- [x] **F-038.** Render the DLQ count the row promises (`dlqItems` currently has no render site), or
      drop the clause from the row. Frontend picks one and says which.
      **Frontend picked RENDER** (#7039's body, recorded there). Witness: the flip inverts what the
      word on screen means — `dashboard/ai-summary-row.spec.ts:245` at `932ec4aef` counted
      `getByText(/dlq|dead[- ]letter/i)` as measured absence, and `:252` at `origin/main` takes
      `row.getByTestId('dlq-indicator')`. Job `115961340950` (run 38594610450) passed both legs,
      including "the row renders its DLQ count — the card the clause promised (ruling 130 flip)".
- [ ] **F-034.** If frontend adds an `/events/:id` redirect, backend's `[r130b]` leaves its link
      line alone; one side changes, not both.
      **Left unticked on purpose (UR-91's exception, already granted by the approving review
      `6173593783`, which names this box, why, and where it is checked).** The redirect shipped
      (#7039 built it per owner ruling 167 option b), and the panel leg passes, but the leg this box
      rests on — "the per-event link … WHERE IT LANDS when followed", `summary-detail.spec.ts:410` —
      self-skips on the CI stack at `:423` ("no summary exists to open"), so no golden run has
      executed the landing. It is checked under the **Unit job**:
      `frontend/src/components/common/EventDeepLinkRedirect.test.tsx:104` "lands a followed
      /events/<id> on /timeline?event=<id>, not on the catch-all", with the unusable-id fallback at
      `:112` as its negative control. F-034's inventory row therefore stays `half-built`.

**Done when:** for each row, its golden spec, already written to pin the broken behaviour, is
flipped to assert the fix and passes (ruling 130).

### [r144n] Route notes for ruling 127's real-tier rows

**Flags:** none. **Assigned:** frontend. **Depends on:** #7030 (R2b round 1 record) merged. **PR:**
#7109 (merged). Ordered by the owner's approval of #7030 (record 6136889433).

- [x] Rewrite the route notes of ruling 127's 12 real-tier rows in
      `docs/reference/feature-inventory.md` to ruling 144's route: the row gets its witness from the
      `O2.5` run, falling back to ruling 127's route if `O2.5` cannot deliver it. Grafana rows F-102,
      F-115, F-117, F-164–F-167, F-169, F-174; GPU rows F-176, F-178, F-182. Statuses, ruling cells
      and priorities stay as #7030 records them. Witness: #7109 merged at `a55dd2eb5`; ops-b's
      review (`6163810759`, head `88800e5b5`) counted the route clauses 12/12 `O2.5`, `ruling 103`
      in 0 of the 12, and row identity by first cell as exactly the named 12.

**Done when:** none of the 12 notes names the per-batch real tier (ruling 103) or an ops-b
owner-tier ruling as its route.

### [r148a] One shared golden harness

**Flags:** none; test-only. **Assigned:** frontend. **Depends on:** `F2.3`'s last batch merged.
**PR:** #7241. (ruling 148, record 6136930446)

- [x] Merge every batch's `frontend/tests/golden/*/harness.ts` into one
      `frontend/tests/golden/harness.ts`, keeping every comment that explains a fix, and repoint each
      spec's import. Until `F2.3`'s last batch merges, each batch keeps its own copy.

**Done when:** one `harness.ts` remains under `frontend/tests/golden/`, and the golden project is
green on it.

### [r148b] F-256's action text

**Flags:** none. **Assigned:** frontend. **Depends on:** none. **PR:** #7050 (merged). (ruling 148)

- [x] Narrow F-256's action text to "filters the cards by zone type; the time range sets the anomaly
      feed's lookback": the time range drives `<ZoneAnomalyFeed>` (`ZonesPage.tsx:660`, `:789-790`),
      not the card grid (`:507-512`). F-256 is judged on that text; it takes no `half-built` status
      and no `R2b` entry.

**Done when:** the row's action text says what the page does, and its golden path cites it.

### [r148c] `works` in the inventory

**Flags:** none. **Assigned:** frontend. **Depends on:** none. **PR:** #7051 (merged). (ruling 148)

- [x] Add `works` to the inventory legend, to `STATUSES` in
      `frontend/scripts/feature-inventory-lib.mjs`, and as a column in the §2 count table, with its
      README meaning (UR-14). A lane whose golden path is green on the fake stack sets
      `awaiting real tier`; the operator's real-tier confirmation sets `works`.

**Done when:** the inventory gate accepts a `works` row and the §2 table counts it.

### [r149e] Type-check the golden specs

**Flags:** none. **Assigned:** frontend. **Depends on:** none. **PR:** #7069 (merged). (ruling 149,
record 6146380050)

- [x] Add `frontend/tsconfig.golden.json` (extends `tsconfig.json`, includes `tests/golden/**`) and a
      `tsc --noEmit` step over it in CI, appended as one entry (ruling 137). Ticked with two
      deviations from the box's literal text, both recorded rather than glossed: (a) `include` is
      `tests/golden/**/*`, not the literal `**` — that literal is tsc error TS5010 and `**/*` selects
      the same set; (b) "appended as one entry" is not realizable here — the shared
      `frontend-typecheck` job holds its check as a `run:` command, not a list a step reads, so
      UR-121 ("Anything else … goes in its own job") routes it to its own job
      `frontend-golden-typecheck` at `.github/workflows/ci.yml:3823`, which is what #7069 shipped.
      The box asks for a `tsc --noEmit` step over the config in CI; that half is met exactly.
- [x] Fix the 9 errors it finds today in the same PR, including the unused `closedByGuard` in
      `dashboard/activity-feed.spec.ts:80`, so that spec checks the guard. The `:80` was right where
      the package wrote it (`acb1e39ad^`) but #7069's own fix shifts it +11, so it reads `:91` at
      main; the spec now calls the tripwire at `:305` and `:354`, where the named-but-never-called
      import had been a decoy. #7069's Done-when ticked per ruling 161 on run 38446238266 — its
      ready head `41c74b8b1`, `Golden Spec Type Check (TypeScript)` and the whole run both `success`.

**Done when:** the type-check step runs in CI and is green.

### [r132] F-022: retire the rate-limit countdown

**Flags:** none. **Assigned:** frontend. **Depends on:** #7030 merged (UR-66's R2b-round exception).
**PR:** #7077 (merged). (rulings 132, 150, 155)

- [x] Delete the countdown overlay, the invented defaults in `updateRateLimitStoreFromError`
      (`frontend/src/services/queryClient.ts:249-297`) and every store field only they read.
      Third limb now met: the follow-up (ruling 155 item 3) deleted `secondsUntilReset` — field,
      writes, `useRateLimitStatus` member, test seeds. `current` stays by the ruling's own fence
      (it names only that field) and F-022's row records why; the backend review of #7077
      (finding 2) offered exactly these two homes for the strand and the row took the second.
- [x] The pill reads "Rate limited, retrying…" and shows no count, limit or time
      (`RetryingIndicator.tsx` is renamed to this text; ruling 155).
      Met by merged #7077: `649475fb4` — an interior commit of its head `66db84789`, not the head
      itself — renames the kept pill to the owner's string (U+2026) at
      `frontend/src/components/RetryingIndicator.tsx:64`, and it renders exactly one span plus an
      `aria-hidden` spinner, no count, limit or time (it returns `null` unless limited AND
      in-flight). The authority for the string is **ruling 155 item 1** ("the string is the owner's
      ruling, not derived prose"). The component test
      (`frontend/src/components/RetryingIndicator.test.tsx`) agrees — it pins that exact text plus a
      no-digit check — but both asserts are `+` lines of the rename commit, so they show the two
      files co-moved rather than independently pinning the copy. The **golden positive leg** is the
      place ruling 155 item 1 actually asks that exact-text assert to live, and it is _not_ what this
      box states; it is unchanged here — it stays the **Done when** paragraph's requirement, tracked
      by F-022's `half-built` status, not something this tick erases.
- [x] F-022's row records that the nginx 429, which sends no `X-RateLimit-*` headers, sets no
      `isLimited` and shows no pill; only the backend's header-complete 429 does (ruling 155).
      Met by merged #7077. Ruling 155 item 2 directs this exact record, and `62c72165e` (the
      retirement commit, refined by `8864ee71a`) wrote it into F-022's row in
      `docs/reference/feature-inventory.md` ("…it feeds the store **nothing**, because it carries no
      `X-RateLimit-*`"); the rename commit `649475fb4` only touched that row's description cell, so
      it is not this box's witness. The row's own status is still `half-built` for the golden-positive
      reason above; this box only required the record to exist, and it does.

**Done when:** F-022's flipped golden spec asserts the pill's exact text and that no countdown or
number renders, and passes. Ruling 125's quarantine of F-022 ends with this PR (ruling 155).
After it merges, frontend deletes the dead `secondsUntilReset` store field in its own one-commit
PR (UR-48).

### [r133] F-023: retire the in-page PWA install prompt

**Flags:** none. **Assigned:** frontend. **Depends on:** #7030 merged. **PR:** #7139 (merged).
(rulings 133, 150)

- [x] Delete `frontend/src/components/pwa/InstallPrompt.tsx`, its 2-visit and 30 s gates, its 7-day
      dismissal store and its tests, `frontend/tests/golden/shell/pwa-install.spec.ts` included.
      Witness: merge `1e1c241ed` lands five deletions — `InstallPrompt.tsx` (the component holds the
      gates and the dismissal store), `InstallPrompt.test.tsx`, `pwa/index.ts`, `pwa/AGENTS.md`,
      `tests/golden/shell/pwa-install.spec.ts`. `git grep InstallPrompt -- frontend` at that tip
      returns 3 hits (unscoped it returns 6: three more are this file's own prose),
      all inside the retired-path guard `src/__tests__/pwa-install-prompt-retired.test.tsx`, which
      asserts the file is gone (`:115`) rather than importing it.
- [x] Keep `frontend/public/manifest.json`, `/sw.js` and their registration. One deviation from the
      box's literal text, recorded: `/sw.js` is not a tracked file — `vite.config.ts:59`'s
      `VitePWA(...)` generates it at build — so the kept leg is the manifest (still tracked) plus the
      generated-SW pipeline, which `tests/golden/shell/offline-cache.spec.ts:173` pins — the served
      `/sw.js` by token (NetworkFirst, `cacheName:"api-cache"`, `skipWaiting`, the index fallback) and
      the precached `index.html` byte-wise (its revision is the served bytes' md5) — and `main.tsx:42`
      still registers.

**Done when:** nothing imports `InstallPrompt`, and the golden project and unit tests are green.

### [r134] F-135: retire the batch-history views

**Flags:** none. **Assigned:** frontend. **Depends on:** #7030 merged. **PR:** #7145.
(rulings 134, 150)

- [x] Delete the closure-reason chart, the per-camera table and the completed-batch timeline from
      `frontend/src/components/batch/BatchStatisticsDashboard.tsx`, and any hook or type only they
      use. The active-batches view stays. Witness: #7145's first commit deletes both component files
      and narrows the hook's three aggregates (a branch SHA is no witness here — every rebase of this
      branch rewrote it twice); the "completed-batch timeline" leg is a measurement, not
      a deletion — `BatchTimelineChart` takes `activeBatches` alone, so nothing ever rendered
      completed batches as a timeline, and the guard's leg B records that. Guard
      `frontend/src/__tests__/batch-history-views-retired.test.tsx` was proven RED with the render
      armed, then green; leg C pins the kept view. The package's `Done when` is met: the row's action
      cell reads the required text verbatim, its golden spec passed first-attempt in CI (run
      `38725128069` attempt 2, `operations/batch-statistics.spec.ts:150` — the declaration's line in
      the tree that run stamped AND in this head, so the cite holds on both sides of the later
      rebase, with no failed-attempt child in its JUnit), and both retired component files are absent
      with the guard pinning it. The row sits at `awaiting real tier`, not `works`: a fake-tier green
      is the lane's ceiling (rulings 103, 148) and `F2.3` owns the real-tier flip.

**Done when:** F-135's row reads "expands the section; sees active batches", its golden path covers
that, and nothing renders the three history views.

### [r160a] Deferred npm majors: vite-plugin-pwa 2, framer-motion 14, @vitejs/plugin-react 6

**Flags:** none. **Assigned:** frontend. **Depends on:** Phase 2's exit. **PR:** none yet.
(ruling 160; dependabot #7058, #7059, #7060, closed with `@dependabot ignore this major version`)

- [ ] One major per PR, each lifting its dependabot ignore (`@dependabot unignore <dependency>`).

**Done when:** each of the three majors is on `main` with the unit, golden and lint suites green at
its head.

### [r165a] F-007: cure the quarantined ws-status spec

**Flags:** none. **Assigned:** frontend, first on its queue. **Depends on:** none. **PR:** #7123
(merged). (rulings 123, 125, 165)

- [x] First commit: the ruling-125 mark's expiry in `frontend/tests/golden/shell/ws-status.spec.ts`
      reads 2026-10-16T00:00Z. Witness: `6f1066eba` adds the stamp beside the mark.
- [x] Test 2 runs whatever precedes it (ruling 123) and passes; the `test.fixme` mark is removed.
      Witness: `67fe6c04b` deletes the mark (its diff removes one `test.fixme`, adds none; the file
      has none at head), and CI's `Feature check (fake AI)` job `115963028206` (run 38595855657)
      passed Test 2 (`:332` partition + reload, 16.7 s) and the chip leg (`:267`, 3.5 s).

**Done when:** the spec passes in CI's `Feature check (fake AI)` with no mark, before
2026-10-16T00:00Z.

### [r196a] F2.3's last frontend rows

**Flags:** none. **Assigned:** frontend, first on its queue; F-012 and F-064 to heavy-a, now
(ruling 226). **Depends on:** none. **PR:** #7184, #7192, #7194, #7200 and #7203 (all merged; the
last, #7194, on 2026-10-16T11:02:30Z as `0ee241c4d`). (rulings 191, 192, 196, 226)

Rulings 191 and 192 assigned these rows as prose inside `F2.3`, which `lane_tick.py` cannot offer
as a claim; ruling 196 makes them a package. Each PR's title carries `[r196a]`.

- [ ] FE-3's five unwritten rows, F-045, F-052, F-053, F-054 and F-059, on one FE-3 build PR
      off `main` (ruling 87's file rule). F-045's "arriving over the socket" clause needs the fake
      VLM's drop path, not the bulk fixture.
- [ ] F-028's leg 2, using F-007's offline-then-reload approach, in its own PR.
- [ ] **heavy-a (ruling 226):** F-012's spec, `frontend/tests/golden/shell/disk-warning.spec.ts`,
      runs in `Feature check (seeded)` against #7178's volume, in its own PR.
- [ ] **heavy-a (ruling 226):** F-064 ("Add Face to Known Persons" on a person detection) gets a
      new spec under `frontend/tests/golden/timeline/`, in its own PR, running in
      `Feature check (seeded)` if it needs `[r215a]`'s seeded person. If no sanctioned supply gives
      the enroll a person detection, the PR states the measured cause and the row goes to `R2b`
      with it; the supply is never faked (ruling 86).

For F-012 and F-064, heavy-a edits only those two inventory rows (ruling 87's file rule), frontend
does no work on either, and frontend reads heavy-a's `frontend/` diffs for both (ruling 184).

**Done when:** none of these eight rows says **unverified**; each flipped on a CI run where its
leg executed and passed, or was demoted for `R2b` with the failure as evidence (rulings 103, 114).

### [r211f] F-048: a search result opens what was clicked

**Flags:** none. **Assigned:** frontend, after `[r196a]` (fix now). **Depends on:** `[r211b]` merged,
for the spec's legs. **PR:** #7210, #7225. (rulings 211, 221, 233; records 6200331506, 6205729827, 6216193689)

- [x] **Now, ahead of the rest of `[r196a]`:** invert the search fixture as `[r211f]` commits on
      #7187's branch (ruling 221). `frontend/tests/golden/harness.ts:2351` requires search
      to exclude the soft-deleted row, and `harness.ts:2375`'s `searchTotal` is the live count. In
      `frontend/tests/golden/timeline/timeline-search.spec.ts` the `fx.searchTotal` reads follow,
      `timeline-search.spec.ts:650` reads `false`, `timeline-search.spec.ts:654`'s 404 stays, and
      the `timeline-search.spec.ts:570` leg's defect half takes a live row on search page 2 that the
      browse list's first page does not hold. No leg gains a mark. Neither lane force-pushes the
      branch, and each fetches it before it pushes. Witness: run 38932915995's
      `Feature check (fake AI)` passed all eight legs of that file (`:214`–`:570`, job
      117083054790), including the `:650` read and the `:654` 404 inside the `:570` leg. (Those three
      line numbers are this PR's own re-authoring of the file; the numbers this box first carried —
      `:585`/`:627`/`:638` — were the same three sites before it shifted them.)
- [x] Clicking a search result opens that result; `getModalEvent()` no longer looks the id up in the
      browse list (`frontend/src/components/events/EventTimeline.tsx:1096`). The
      `timeline-search.spec.ts:570` leg's defect half becomes "the page-2 row opens". Witness: that
      run's reporter log prints the leg green at its own line number —
      `timeline-search.spec.ts:570:3` then the leg title then `(24.8s)` with a ✓ — and
      `frontend/src/hooks/useEventModalRow.ts:69` is the lookup that leg exercises.
- [x] Remove both `test.fixme` marks in `frontend/tests/golden/timeline/timeline-search.spec.ts`.
      Witness: the file has zero `test.fixme(` calls at this head (it had 2 at `4cefe81e4`, at
      `:474` and `:535`), and both legs that carried them ran green in the same run, at reporter
      positions `:472:3` (5.4s) and `:520:3` (861ms).
- [x] **F-045 (ruling 233):** the same lookup serves a live-activity click, so remove the
      `test.fixme` at `frontend/tests/golden/timeline/live-socket-arrival.spec.ts:598` in this PR or
      one right after it. F-045 flips to **awaiting real tier** on the run where that leg and the
      row's other legs pass. **Both halves land here.** The mark is gone and the leg is un-skipped —
      a running `test(...)` at spec `:598`, not `test.skip` — because `fixme` publishes "this would
      fail" and this head refutes that (the modal opens on a socket-only click;
      `Expected: 0, Received: 1` at job 117083054790). What kept the leg from passing was supply,
      not behaviour: its drop re-sent bytes `dropAndAwaitCard` had already sent, which the 300 s
      content-hash window swallows (`backend/services/file_watcher.py:871-873`). The supply ruling
      233 assigns to a PR titled `[r211f]` is this PR: the leg now re-drops the same bytes after
      the window lapses (`live-socket-arrival.spec.ts:375`, after `SUPPLY_TTL_WAIT_MS`). The run the
      box was waiting on is `38966718386` (attempt 1, `head_sha` proven `dabd3dd34`): its
      `Feature check (fake AI)` job 117196287379 read all three `F-045` legs `passed` in
      `summary.json`, and the inventory witness re-run over that summary prints
      `F-045 (half-built): 3 leg(s) mapped (3 passed); not judged` — the row was unjudged only
      because of its own cell. This commit flips the cell, so the next head's run judges it
      (ruling 218); the text pasted into the row is `paste_text()` output, not hand-written prose.

**Done when:** all 8 legs pass in `Feature check (fake AI)` at a ready head, and F-048 flips to
**awaiting real tier** on that run (rulings 103, 114); and F-045 flips the same way once its `:598`
leg passes (ruling 233). If #7210 merges first, F-045's leg lands in a follow-up PR with `[r211f]`
in its title, and the package is not done until it does.

### [r234] F-052: the export modal's dates reach the export

**Flags:** none. **Assigned:** heavy-a, now, ahead of `B2.3` (fix now; ruling 234). **Depends on:**
none. **PR:** #7213. (ruling 234, record 6216216005)

ExportModal uses `useDateRangeState({ persistToUrl: false })`
(`frontend/src/components/exports/ExportModal.tsx:59`). In that mode the hook reads its range only
from the URL (`frontend/src/hooks/useDateRangeState.ts:328`, `:340`) and every write returns early
(`:391`), so `setCustomRange` does nothing and the export sends null bounds.

- [ ] In one PR with `[r234]` in its title: `useDateRangeState` keeps a custom range and preset in
      local state when `persistToUrl` is false, so ExportModal's chosen bounds reach the export
      request. A unit test pins it.
- [ ] Remove the `test.fixme` at `frontend/tests/golden/timeline/export-modal.spec.ts:751`; the leg
      passes.
- [ ] F-052's action drops "cancels or": F-099 owns Cancel (R2a row 13). heavy-a edits only F-052's
      inventory row (ruling 87), and frontend reads heavy-a's `frontend/` diff (ruling 184).

**Done when:** F-052 flips to **awaiting real tier** on a CI run where its legs, the dates leg
among them, pass (rulings 103, 114).

### [r238] F-057: the saved note reads back

**Flags:** none. **Assigned:** heavy-a, after `[r234]`, ahead of `B2.3` (ruling 238). **Depends
on:** none. **PR:** #7219. (rulings 149, 238; record 6216702824)

`[r149d]` (#7070) made `list_events` return `notes` (`backend/api/routes/events.py:543`), but its
second box, the golden read-back leg, never had a roster slot, so F-057 stays **half-built** with
that leg unrun.

- [ ] In one PR with `[r238]` in its title: remove the `test.fixme` at
      `frontend/tests/golden/timeline/event-detail.spec.ts:358` ("the saved note is read back"); the
      leg passes. heavy-a edits only F-057's inventory row (ruling 87), and frontend reads heavy-a's
      `frontend/` diff (ruling 184).

**Done when:** F-057 flips to **awaiting real tier** on a CI run where its legs, the read-back leg
among them, pass (rulings 103, 114).

### [r212] F-061 and F-062: the audit tab can run an evaluation, and both legs re-run

**Flags:** none. **Assigned:** heavy-a, ahead of `B2.3` (fix now; ruling 224). **Depends on:** none.
**PR:** #7197 (merged 2026-10-16T04:29:41Z as `c92be2ae0`, head `e91478058`). (rulings 212, 224;
records 6200384247, 6205825842)

F-106 and F-108 share this surface and are fix-now; `[r129]` (#7031) made the batch audit load the
deferred `Event.llm_prompt`, after these rows' evidence run at `7971475db`.

- [ ] On an event with no audit, `EventAuditDetail.tsx` renders the Run control instead of returning
      its error screen (`:241-257`) before the header that holds it (`:321`).
- [ ] The golden fixture seeds an audit by running the batch audit on the fake stack; remove both
      `test.fixme` marks in `frontend/tests/golden/timeline/event-reevaluate.spec.ts`.

**Done when:** each row flips to **awaiting real tier** on a run where its legs pass (rulings 103,
114), or the PR posts the run where a leg still breaks and that row returns to the owner.

### [r213] F-060: the saved feedback card shows what was stored

**Flags:** none. **Assigned:** heavy-a, after `[r212]` (fix now; ruling 224). **Depends on:** none.
**PR:** #7205 (merged 2026-10-16T08:45:03Z as `d6344e031`, head `1ee8d9ac5`). (rulings 213, 224;
records 6200455263, 6205825842)

F-060 is split: the panel is a labelling tool (complete), and learning thresholds from feedback is
retired with F-131 (R2a row 11). The labels are stored and round-trip `GET /api/feedback/event/{id}`.

- [ ] The saved card (`frontend/src/components/feedback/FeedbackPanel.tsx:281-293`) shows every
      field that was stored, not only the type, the notes and the date.
- [ ] Remove the `test.fixme` mark in `frontend/tests/golden/timeline/event-feedback.spec.ts`.

**Done when:** all legs pass in `Feature check (fake AI)` at a ready head, and F-060 flips to
**awaiting real tier** on that run (rulings 103, 114).

### [r214] F-213 and F-277: the owner pick saves, and a saved person appears

**Flags:** none. **Assigned:** heavy-a, after `[r213]` (fix now; ruling 224). **Depends on:** none.
**PR:** #7208 (merged 2026-10-16T10:15:38Z as `0dc74845d`, head `662fbd575`). (rulings 214, 224;
records 6200676782, 6205825842)

- [ ] F-213: the owner `<Select>`'s listbox renders above the `z-50` configure modal
      (`frontend/src/components/zones/ZoneOwnershipPanel.tsx:846`, `:883-899`), so choosing an
      owner saves it; the leg at `frontend/tests/golden/settings-cameras/cameras-zones.spec.ts:223`
      asserts the saved owner.
- [ ] F-277: the person modal invalidates the key the page reads (`useKnownPersonsApi.ts:33`,
      `:146` against `useFaceRecognitionApi.ts:58`); a leg in
      `frontend/tests/golden/identity/persons.spec.ts` asserts the new person in the list with no
      reload.

**Done when:** each row flips to **awaiting real tier** on a run where its legs pass (rulings 103,
114).

### [r204] One realtime connection owner

**Flags:** none. **Assigned:** frontend, after `[r196a]`. **Depends on:** none.
**PR:** #7230 (ruling 204, record 6199283332)

`webSocketManager.ts` shares one connection per URL (`subscribe`, `:254`), but `useConnectionStatus`
opens its own events and system sockets through `useWebSocketStatus` (`:290`, `:298`;
`new WebSocket` at `useWebSocketStatus.ts:145`), and both `Layout.tsx:38` and `Header.tsx:171` call
it. The manager stops on the auth close codes (`AUTH_TERMINAL_CLOSE_CODES`, `:155`);
`useWebSocketStatus`'s `onclose` (`:176`) reads no code and keeps reconnecting.

- [x] `useConnectionStatus` reads channel state from `webSocketManager` (`subscribe`,
      `getConnectionState`, `reconnect`) and opens no socket; one provider feeds Layout and Header;
      `useWebSocketStatus`'s socket code and its tests are deleted.
- [x] `isPollingFallback` and `retryConnection` keep their meaning; a terminal auth close shows as
      such and is not retried.
- [x] Tests: the mounted shell holds one manager connection per channel; neither Layout nor Header
      opens a socket; a `4001` close stops reconnection on the status path.
- [x] F-007's `frontend/tests/golden/shell/ws-status.spec.ts` passes unchanged in
      `Feature check (fake AI)`.

**Done when:** these pass in CI at a ready head, and under `frontend/src/` (tests and mocks aside)
`new WebSocket(` appears only in `webSocketManager.ts`.

### [r205] No status is not "healthy"; health is not an alert count

**Flags:** none. **Assigned:** frontend, after `[r204]`. **Depends on:** `[r204]` merged.
**PR:** #7234. (ruling 205, record 6199725340)

`DashboardPage.tsx:289` reads `deferredSystemStatus?.health ?? 'healthy'`, so a dashboard that
never receives a status reads as healthy. `AmbientStatusProvider.tsx:94-109` turns service health
into the favicon's alert count (`unhealthy` 3, `degraded` 1).

- [x] Until a system status arrives, the dashboard shows a neutral connecting or unknown state,
      never `healthy`; a no-flash treatment must not render healthy's word or colour.
- [x] The badge shows health as health (colour or icon) and a number only from a real alert count;
      with no such source it shows no number. `alertCountOverride` keeps working.
- [x] Tests: no status, or a dashboard that never connects, never renders "healthy"; an unhealthy
      or degraded service gives no numeric badge without a real count; a real count shows as given.
- [x] The golden specs over the dashboard and ambient status pass unchanged, or the PR names the leg
      it changes and why.

**Done when:** these pass in CI at a ready head, and under `frontend/src/` (tests aside) no
`?? 'healthy'` default and no health-to-count mapping remain.

### [r168] The fast-path switch

**Flags:** none. **Assigned:** frontend, after `[r165a]`. **Depends on:** `[r130b]`'s
`fast_path_enabled` field merged. **PR:** #7174. (ruling 168)

- [ ] The processing settings show a "Fast path" switch bound to `fast_path_enabled`, off by default,
      with `config.py`'s warning as its help text; the threshold slider shows only when it is on.
      Ticked from the first ready vitest run naming this PR's leg
      (`ProcessingSettings.test.tsx › fast-path switch (ruling 168)`) — that is the
      `Frontend Tests (Vitest)` job or its `Frontend Tests (Vitest N/8)` shards; there is no job named
      "Backend+Frontend Unit Tests", which is what this row said until this commit. A draft skips
      every job.
- [ ] The page never writes a threshold while the switch is off. Two cards on this page write this
      one setting, so the witness is a pair, one per card: `ProcessingSettings.test.tsx` (never
      sends a fast-path threshold while the switch is off) and `DetectionThresholdsPanel.test.tsx`
      (omits fast_path_threshold from the saved settings while the switch is off).

**Done when:** a test saves the settings page with the fast path off and reads it back off; backend
then removes the two read clamps in `system.py` as UR-48 lane work.

### [r173] Golden Playwright skips join the suppression registry

**Flags:** none. **Assigned:** frontend, after `[r168]`; ops-b reviews the `scripts/` and `.github/`
hunks. **Depends on:** none. **PR:** #7236. (ruling 173)

- [x] `scripts/suppression-registry-gen.py` and `test_suppression_census.py` scan
      `frontend/tests/golden/**/*.spec.ts` for `test.fixme(` and unconditional `test.skip(` call
      sites, excluding conditional guards as the pytest arm does.
- [x] One registry row per site in a golden reason class citing its authorizing ruling or package;
      the baseline rises in the same commit.
- [x] Sites with no authorizing ruling are listed on the PR for the coordinator to route.

**Done when:** the census fails CI on an unregistered golden `test.fixme`, and every current site has
a row.

### [r267a] The service-status hook accepts what the backend broadcasts

**Flags:** none. **Assigned:** frontend, first on its queue after the PR it holds (UR-52).
**Depends on:** none. **PR:** #7293. (ruling 267, record 6266846674; audit item Q-001 of
`[r262]`)

`frontend/src/hooks/useServiceStatus.ts`:80 keeps only `redis`, `rtdetr` and `nemotron`, and its
status guard keeps only its own status values. The backend's health monitor probes `yolo26`
(`backend/main.py`), the container orchestrator broadcasts container names and the worker
supervisor broadcasts `worker:<name>`, all through `broadcast_service_status`. So no broadcast
passes, and `yolo26`'s health never reaches `ServiceStatusAlert` or the services panel's badge.

- [x] **MEASURE** each `service_status` emitter and the names and status values it sends, and
      where else the frontend shows each one. The PR states, for the container and worker
      broadcasts, whether the hook takes them and why.
- [x] The hook accepts the health monitor's probe names and status values and every other
      in-scope emitter's, and drops `rtdetr` and `nemotron`; the alert's label map follows. The
      backend's payloads do not change.
- [x] A test feeds each in-scope emitter's real payload shape through the hook, and an unhealthy
      `yolo26` lights `ServiceStatusAlert`.

**Done when:** the tests above pass in CI at a ready head, and the PR names each emitter's decision.

### [r299] The E2E global setup writes the tour keys under the origin the specs run

**Flags:** none. **Assigned:** frontend, after `F3.3` (ruling 299). **Depends on:** none.
**PR:** #7349. (ruling 299, record 6321779954; audit item Q-179 of `[r262]`)

`frontend/tests/e2e/global-setup.ts:30` writes the tour-suppression keys under the origin
`https://localhost:8444`, but the specs run at `http://localhost:8444` (`global-setup.ts:71`,
`playwright.config.ts:194`). Playwright applies `localStorage` per origin, so the keys never land,
and the tour overlay opens and blocks clicks. The committed `tests/e2e/.auth/storage-state.json`
(`playwright.config.ts:213`) carries the right origin, but the setup overwrites it on every
non-golden run. The specs that don't use the shared fixtures' init script
(`fixtures/index.ts:53-57`) are exposed: local runs and the nightly visual specs, since the rest
skip themselves under CI.

- [x] `frontend/tests/e2e/global-setup.ts` writes the storage state under the origin the specs run,
      derived from the configured base URL (`E2E_BASE_URL` or the Playwright config's `baseURL`),
      not a literal.
- [x] **A test pins it, red first (UR-69).** For example, the written state's origin equals the
      configured base URL, or a spec that opens the app without the fixtures' init script finds no
      tour overlay.
- [x] **The PR decides whether `tests/e2e/.auth/storage-state.json` stays committed,** and says why.
      A file the setup rewrites on every run may leave the tree (ignored instead).

**Done when:** the test passes in CI at a ready head and the UR-89 review approves.

### [r323b] F-295 and F-296 get witnesses outside `O2.5`

**Flags:** none. **Assigned:** frontend, last on its queue; it gates nothing (ruling 323).
**Depends on:** none.
**PR:** none yet. (ruling 323, record 6356971214)

Neither run of `O2.5` could witness these two rows. F-295's push cannot be driven inside any golden
run: the summary job runs once at boot, then sleeps 3600 s. F-296's two legs are `test.fixme`,
because the fake tier supplies no video detection and no event with two detections.

- [ ] **F-295.** A backend integration test runs `SummaryJob.run()` and receives the
      `summary_update` frame on `/ws/events`; it is the PR's cross-lane part (UR-9). A
      `useSummaries` unit test shows the refetch on that frame. Together they are F-295's witness:
      the owner waives UR-14's golden-path bar for this row alone, and the golden leg keeps its
      stated skip.
- [ ] **F-296.** The fake tier supplies a video detection and an event with two detections whose
      orderings disagree, and the two `test.fixme` legs in `timeline/download-media.spec.ts` become
      running tests. The supply-witness leg at `:768` changes with them: on prod-shape it got the
      route's own 400, where it expects CI's 500.

**Done when:** CI is green, both rows record their witness, and the UR-89 review approves.
