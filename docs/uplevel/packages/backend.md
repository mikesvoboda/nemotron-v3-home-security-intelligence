# Backend packages

Open packages of the backend lane: every package whose row in the
[README status table](../README.md#status) is not `done`. How to claim, build, review and merge
one is in [`../rules.md`](../rules.md) and [`../roles/lane.md`](../roles/lane.md). Finished
packages are in [`../history/packages-done.md`](../history/packages-done.md).

## Lane scope

- The lane owns `backend/`, except `backend/tests/unit/setup_lib/` (ops). Evidence for every package
  is in [`00-audit.md`](../00-audit.md); `00 §n` cites its sections.
- The feature inventory's ruling column is the input to every Phase 3 package.
- External-interface golden paths: UR-127 (`O2.2`'s harness runs them).
- Phase 4 runs in the priority order the inventory's priority column records: `R2a`'s tiers P1–P4
  (ruling 89) and `R2b` round 1's (ruling 135).
- On next touch: the module docstring of `backend/services/batch_aggregator.py` says batches go to
  "the Nemotron analysis queue"; the VLM analyses them now. The PR that next touches the file fixes
  it (ruling 134).

## Phase 1 — Stop the bleeding

### B1.1 VLM timeout ladder (D1)

**Flags:** none. **Depends on:** none.

**Files:** `backend/services/vlm_client.py`, `backend/core/config.py`; `.env.example` and the
compose `environment:` line if a default changes.

`_ASSESS_MAX_TOKENS = 2048` is justified by a 180 s read timeout that no longer exists; the real
default is 25 s. A reply past roughly 1,400 tokens times out, is retried identically at
temperature 0, and charges the circuit breaker twice (`00 §3` D1).

- [ ] Write the failing test: a stub transport slower than the read timeout. Assert the target —
      the breaker charged at most once, no identical retry. It fails today, which records a
      transport error, retries identically and charges the breaker twice.
- [ ] **DECIDE** the ladder under spec S4 (p95 ≤ 30 s including cold starts, `config.py:1134`).
      The options: derive the per-attempt timeout from the token budget and measured throughput;
      cap `max_tokens` to what the timeout can hold; classify a read timeout as a budget outcome
      that skips the identical retry and the breaker. Whatever you choose, a slow reply never
      counts as a broken engine.
- [ ] Replace the stale comment with the real arithmetic: tokens, throughput, timeout.
- [ ] **MEASURE** on the real tier: p95 latency and the reply-length tail. The operator agent
      measures the tail on the GB300 ([`roles/operator.md`](../roles/operator.md), "The agent-gpu
      path"); S4's p95 is defined on 24 GB-class hardware, so the owner measures it on the A5500.
      Until `O2.2` exists, put both commands in the PR, using `$VLM_URL` and written to run against
      a test deployment (UR-133).
  - The tail measurement runs `latency_tail.py` on synthbench stills from `/synthbench/corpus`,
    which the operator mounts read-only; no camera stills are needed. Pick at least the script's
    minimum number of stills with a `--pattern`, preferring event scenes (people, vehicles). The post
    states that the stills are synthetic, and gives the `--dir`, the `--pattern`, the count and the
    corpus batch or batches, so the sample can be re-run on the same frames. It runs after `O2.2`'s
    `--real` re-run, unless the runner admits both at once (owner record `6116476010`).
  - The owner's A5500 run is deferred; the row stays `awaiting real tier` until it is posted
    (ruling 23).

**Done when:** the test passes; the comment's numbers match `config.py`; the operator's S4 p95
measurement is posted on the PR (the row sits at `awaiting real tier` until then, contract rule 5).

## Phase 2 — Feature truth

### B2.3 Re-ID model bake-off

**Flags:** `heavy`; label `cell:heavy-b` (ruling 258). **Depends on:** `O2.4` (its `RESULT: PASS` posted).
Approved by owner ruling 107 (issue #6854, comment `6109720693`, 2026-10-11). It may stay open past
Phase 2's exit (UR-10, contract rule 5).
**Assigned:** heavy-b, next once `O2.4`'s `RESULT: PASS` is posted, after the PR heavy-b holds then
(rulings 258 and 260). **PR:** none yet.

- [ ] Export CLIP-ReID ViT-B/16 and PersonViT ViT-S/16 through `O2.4`'s TensorRT path.
- [ ] Score them with OSNet-AIN x1.0 on a labelled set of person crops from the owner's setting:
      Rank-1, mAP, a calibrated match threshold per model, and GPU milliseconds per crop. The
      labelled set (source, who labels, size) is settled with the owner as the package's first
      question.

**Done when:** the PR posts a recommendation with these numbers, for an owner ruling. Nothing in
production changes: no `models.yml` swap and no switch flip. A swap, if ruled, is a new model ID
with its calibrated threshold, and stored person vectors go to "unavailable (re-enroll)" by design.

## Phase 3 — The tree matches the rulings

### B3.1 Retire ruled-out features, backend part

**Flags:** `heavy`; `owner` for a retirement UR-98's plain-retirement exception does not cover
(ruling 249). **Depends on:** `R2` (rules.md §Claiming and assigning work); lands in
one PR with `F3.1`.
**Assigned:** heavy-a, after `[r238]`, ahead of `B2.3`; its remaining retirements resume after
`B2.3` (ruling 241). **PR:** #7220, #7224, #7228, #7232, #7233, #7243, #7247, #7249, #7253, #7254, #7255, #7258, #7261, #7266.

**Files:** whatever each retired feature's inventory row lists under "modules".

**One R2a row per PR** (ruling 255, amending ruling 241 item 1). A `B3.1`/`F3.1` PR retires every
feature ruled retire under one R2a row, across backend and frontend, and never spans two rows. It
may retire less of its row when part of the row must wait (a table drop waits for `B3.3`'s upgrade
command) or when the author's review finds the diff too large for one round; the body names the
features left out and why, and they follow as one later PR for that row. UR-98's plain-retirement
exception (ruling 249) is judged once for the whole PR, and the Done-when grep is checked for each
feature it retires; if any feature misses a condition, the PR keeps `owner` and its Owner tier line
names that feature and condition. Ruling 258 lifts the pause in the assignment above: the
retirements continue without waiting for `B2.3`, which is heavy-b's.

- [x] First, OD-20's already-ruled retirement of the enrichment surface (hook, route, types and
      tombstone in one commit; ISS-073).
- [ ] For each feature ruled **retire**: delete its routes, schemas, services, settings, alert
      conditions and tests (batteries included). The frontend part (`F3.1`) lands in the same PR,
      so the client never calls a route that is gone.
- [ ] Tables leave as upgrade steps of `B3.3`'s upgrade command, which lands first (ruling 203,
      record 6198942052), not as a hand-run DROP runbook. Until it lands, take the retirements
      that drop no table; one that drops a table waits for it (ruling 241).
- [x] `POST /api/reid/search` retires (`backend/api/routes/reid.py:78-79`, handler
      `search_similar_entities`): route, handler, tests and both its `docs/developer/api/coverage.md`
      lines (`:692`, `:856`). It has no client and no guide; Phase 4's design sessions may bring
      re-ID search back (ruling 236).
- [ ] Regenerate `docs/openapi.json`.

**Done when:** for every retired feature, a grep for the identifiers its inventory row lists finds
nothing in `backend/` outside its upgrade step.

### B3.2 Delete the approved module list (OD-28 and `R2`)

**Flags:** `heavy · owner`. **Depends on:** `R2`.
**PR:** none yet. (ruling 241)

- [ ] Delete in OD-28's order — the guided-constraints and trajectory modules first — then every
      module under `backend/` the reachability check reports non-shipping at this PR's head,
      outside `keep.toml`: `R2`'s §3 is approved as that rule, not as the measured snapshot
      (ruling 210, record 6200282082). The scene-change vertical stays: R2a row 24 ruled it
      complete, and `scene_change_detector.py` goes on `keep.toml` as "F-287, R2a row 24" (ruling
      183).
- [ ] A non-shipping module that a **complete** feature's inventory row claims stays: add it to
      `keep.toml` with that row's id as the reason. It ships once its feature is built. Rows deferred
      to roadmap R1 go on `scripts/reachability/keep.toml` with the reason "R1 deferral, ruling 89"
      (ruling 89).
- [ ] Cut `backend/services/__init__.py` and `backend/core/__init__.py` down to the names shipping
      code imports.
- [ ] Delete each module's tests, batteries included. These PRs change production code, so the
      kill-loss rule does not apply; each PR discloses the scored-set change instead (`01`).

**Done when:** the reachability check (`O2.3`) reports no non-shipping module under `backend/`
outside `keep.toml`, and the suite is green.

### B3.3 Settings and residue truth

**Flags:** none. **Depends on:** `R2`.
**PR:** #7244. (ruling 241)

- [x] **MEASURE** the settings fields read nowhere outside `config.py` (50 at `d6ba78d5`, `00 §4.1`)
      and delete them with their `.env.example` and compose lines.
- [x] Add a ratchet test: every `Settings` field is read outside `config.py`, or sits on an
      allowlist with a reason.
- [x] Rename live code still carrying retired names (`get_nemotron_analyzer_dep`,
      `summary_generator._call_nemotron`, Nemotron-named metrics); delete the uncalled metrics and
      unused exception classes `00 §4.1` lists. (Box 3's work is #7244's: the renames
      (`65275de9b`), the dead-symbol census `scripts/audit/dead_symbols.py` with its CI leg
      (`d2a0eb0b0`) — two exception classes deleted, zero uncalled or Nemotron-named metrics in the
      registry, and the audit's "11" not reproducible under any stated definition (the census
      records why the rest is not residue, and the FLORENCE_UNAVAILABLE consumers make it an owner
      contract call that rides the fourth box's PR); the repo-wide ratchet test pins the census.)
- [ ] `AIModelEnum` and the prompt-management schemas follow the prompt page's ruling.
- [x] The upgrade path (ruling 203, record 6198942052). Startup builds the schema with
      `create_all` (`backend/core/database.py:408`), which never changes an existing table, and
      `docs/api/migrations/` is applied by hand. One ordered, checked upgrade command records which
      upgrades a database has had; Alembic or a small runner over `docs/api/migrations/` is this
      package's design choice, and the `alembic` dependency stays or goes with it (`00 §7`). The
      four existing SQL files become its first recorded upgrades or are marked applied.
- [x] A test starts from a saved pre-upgrade schema with rows in it, upgrades it, and checks the
      rows survive. The integration tests boot through the command; no fixture adds a column. (The
      three fixture sites that did -- `backend/tests/integration/conftest.py`,
      `backend/tests/conftest.py`'s two twins -- are deleted in this PR; the duplicate-camera
      DELETEs and unique indexes stay, because the index cannot be built before them and deleting
      rows is owner-tier, UR-98.)

**Done when:** the ratchet test passes; a database saved from today's `main` upgrades with its rows
intact in CI; and the PR reports the before/after count of `nemotron`, `florence` and `enrichment`
hits in `backend/`.

**The fourth box, as ruling 254 reads it** (R2a row 27). `florence2`, `yolo_world`, `xclip` and
`fashion_clip` leave `AIModelEnum` and `AIModel` with their config schemas, as a recorded upgrade on
the fifth box's runner that lands after the runner does. The upgrade removes or rewrites the
`prompt_versions` rows storing those values, as backend's design chooses; its test checks that every
other row survives and that the changed rows are exactly those four models' rows. That is how the
Done when's "rows intact" reads for this upgrade. In the same PR (UR-9), backend leading and
frontend's files riding as cross-lane parts: the frontend's four prompt editors and the Version
History filter and labels change, so no editor sends a value the API refuses; and
`FlorenceUnavailableError` and the `FLORENCE_UNAVAILABLE` code retire with Florence, with the
frontend copy and the docs row. `AnalyzerUnavailableError` and `EnrichmentUnavailableError` stay,
with their codes. The PR that carries this is owner tier (UR-98), and backend chooses which `B3.3`
PR it is. The row's design note stays with Phase 4's prompt-management package.

### [r236] Two documented endpoints become External rows

**Flags:** none. **Assigned:** backend, after `B3.3`. **Depends on:** `R2` (Phase 2's exit).
**PR:** #7260. (ruling 236, record 6216306194)

No client in `frontend/src` calls them, but the docs tell users to:
`docs/guides/face-recognition.md:288` for `POST /api/household/members/{member_id}/embeddings`
(`backend/api/routes/household.py:460-461`), and `docs/developer/api/core-resources.md:881` for
`GET /api/detections/export` (`backend/api/routes/detections.py:2025-2026`).

- [ ] Each gets an `External ›` inventory row (as F-290–F-294 are) with its documented action.
- [ ] Each gets a backend golden test, as F-294's
      `backend/tests/golden/external/test_metrics_scrape.py` is, and its row flips on the run where
      it passes (rulings 103, 114).

**Done when:** both rows exist and neither says **unverified**.

## Phase 4 — Complete the product

### B4.\* Feature track

**Flags:** design: `heavy`. **Depends on:** `R2`'s ruling and priority for the feature.

One package per feature ruled **complete**, in the priority order set at `R2`. Every feature
package runs the same six steps, as two PRs (rules.md §Building a package):

1. **Design session.** The owner and the executing agent settle the feature's open questions;
   the result is a design at `docs/uplevel/4n-<feature>.md`, copied from
   [`templates/feature-design.md`](../templates/feature-design.md).
2. **Consolidate first, in its own test-only PR.** Consolidate the tests of every module the
   feature will touch, under `01`'s zero kill-loss protocol. This PR changes no production bytes.
3. **Build** test-first, in the second PR.
4. **Golden path** green on the fake stack. The frontend lane writes UI golden paths; this lane
   writes external-interface golden paths as pytest specs in `backend/tests/golden/`.
5. **Real-tier check** recorded by the operator.
6. **Inventory row** set to **works**.

**Done when** (every feature package): steps 4–6 hold.

**Arming (UR-12)** is one of these features (P2, ruling 89). Its shape is fixed: one arming module
behind the seam, with the inbound webhooks and the MQTT command handler as two thin adapters,
replacing both stubs. The MQTT adapter carries zone arm/disarm, system mode, alert ack and camera
sensitivity/PTZ (F-291 ruled complete, all of it; ruling 89). Its design session settles:

- what arming gates — alert creation, notification delivery, or analysis;
- whether a critical tier alerts regardless of arm state, as life-safety alarms do;
- what a mode (home, away, night) is — a named set of armed zones, or something else;
- how arm state relates to `AlertRule.schedule` and notification quiet hours — settle OD-22
  (notification policy) in the same session;
- the persisted state and its audit trail, and the UI control (a frontend part);
- whether the MQTT handler starts with the app, and how it authenticates.

**Alert rules** (F-216, F-217; P1) is another (ruling 89: call the rules engine after each
verdict). Its schedule includes its end minute in full: a window matches when
`start <= now < end + 1 minute`, and an overnight window (end before start) wraps across midnight
with the same one-minute inclusion. Its tests pin the boundary with a fixed clock: 23:59:30
matches, 00:00:00 the next day matches for an all-day rule, and the instant after the end minute
does not (ruling 139).

**Notification history** (F-236, P1) is another. Its delivery log is written where notifications are
sent, and today nothing sends on an event: `NotificationService` (email, webhook) is called only by
the settings page's test buttons (`backend/api/routes/notification.py`), while the per-event notify
decision is the record under OD-31's narrow reading (ISS-001). Its design session also settles
which channels an event with `notify: true` sends on (email, webhook, or none), with each attempt
and its outcome in the log; settle it with Arming's "notification delivery" question and OD-22
(ruling 206, record 6199786907).

**Prompt management** (row 27 of ruling 89) starts with a design note on how activating a prompt
version relates to replay measurement; the package is flagged `owner` and the owner reviews that
note. OD-36 (debug tooling) and OD-37 ("Clear All Test Data") packages are flagged `owner`
(ruling 89).

### BB.\* Background track

**Flags:** none. **Depends on:** none named.

Modules and seams no feature reaches. Each package opens with a design session against the code
that remains, then consolidates the tests it will touch in a test-only PR (`01`'s zero kill-loss
protocol), then refactors in a second PR. `BB.1` is test-only throughout.

| package | target                                                                                                                                                                                                                                                                                                                                                       | evidence    |
| ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------- |
| BB.1    | Test consolidation for untouched modules: the 2,010 literal-only tests (`scripts/parametrize-guard.py` proves merges safe), ~215 shadowed fixtures, copy-pasted battery helpers into `backend/tests/utils`, `unit/routes/` merged into `unit/api/routes/`, the three permanently skipped `stream_config` files, the "moved" skips in `test_system_models.py` | `00 §6`     |
| BB.2    | Resilience primitives: one circuit breaker (four today), one retry (two), one HTTP client factory (31 construction sites); detection's three-deep retry stack collapses                                                                                                                                                                                      | `00 §5`     |
| BB.3    | Broadcast: `EventBroadcaster`, `WebSocketEmitterService` and `SystemBroadcaster` become one module driven by a typed event table                                                                                                                                                                                                                             | `00 §5`     |
| BB.4    | Service registry: `ServiceConfig` ×3 and `ManagedService`/`ServiceRegistry` ×2 become one                                                                                                                                                                                                                                                                    | `00 §5`     |
| BB.5    | Configuration: `config.py` (3,366 lines, 19 `BaseSettings` classes repo-wide) split by concern                                                                                                                                                                                                                                                               | `00 §2, §5` |
| BB.6    | The VLM seam — build → call → judge: one prompt fit and one key-frame selection per batch, the prompt as a versioned template whose hash is stored on `EventVerification`, the analyzer built once. Unless a VLM feature reaches it first.                                                                                                                   | `00 §5`     |
| BB.7    | Oversized route modules, starting with `api/routes/system.py` (5,515 lines)                                                                                                                                                                                                                                                                                  | `00 §2`     |

**Done when** (every background package): one implementation of the concept remains (a grep proves
it), and the module's tests pass through its interface.

## Ruling-ordered fixes

Fixes an owner ruling ordered outside the phase order. Each keeps the ruling's tag as its id, queues
where its ruling says, and takes the normal queue and review (UR-113). None has a README status row;
the PR that finishes one updates its row in [`../history/ruling-map.md`](../history/ruling-map.md).

### [r94] `setup.py` re-runs keep the existing configuration; `--convert-monitoring-key`

**Flags:** owner tier (security and auth), pre-approved by ruling 94 (UR-101).
**Assigned:** `uplevel-backend`, test-first; `setup.py` is ops's file, so the PR lists it as a
cross-lane part. **Depends on:** none named. **PR:** #7038 (merged).

- [ ] **The defect:** on a re-run, the LAN-exposure prompt defaults to `n` (`setup.py:685` quick
      path, `:900` guided), and that answer drives `EXPOSE_LAN`, `FRONTEND_BIND_ADDRESS` and the
      Grafana anonymous-auth derives (`:447`, `:449`, `:482`–`:491`). Pressing Enter through a
      re-run on a LAN-exposed install silently re-binds the frontend to loopback and disarms the
      gate key scoping depends on.
- [ ] **Fix 1:** on a re-run, every prompt's default is the value already in `.env`. A first run
      keeps today's defaults.
- [ ] **Fix 2:** a `--convert-monitoring-key` flag rewrites only the plain monitoring-key entry in
      `API_KEYS` as a scoped entry (`{"key": …, "scope": "monitoring"}`, #6959's format) and touches
      nothing else in `.env`. Ruling 79's docs line (`docs/operator/admin/security.md`) points at
      this flag instead of a full re-run.

**Done when:** tests pin that an Enter-only re-run over a LAN-exposed `.env` keeps
`EXPOSE_LAN=true`, `FRONTEND_BIND_ADDRESS` and the Grafana derives unchanged; that
`--convert-monitoring-key` changes only that one entry (byte-compare the rest of `.env`); that a key
already scoped is left alone; and the docs line is updated (ruling 94).

### [r95] Close both monitoring-key gaps (S1, S4)

**Flags:** owner tier (security and auth), pre-approved by ruling 95 (UR-101); ops-b reviews.
**Assigned:** `uplevel-backend`, test-first, one PR. **Depends on:** none named. **PR:** #7135.

- [x] **S1:** with `API_KEY_ENABLED=true` and `EXPOSE_LAN=false`, the 9 routes guarded by the legacy
      `verify_api_key` copies (`backend/api/routes/dlq.py`, `backend/api/routes/system.py`;
      including `POST /api/dlq/requeue/{q}`, `POST /api/dlq/requeue-all/{q}`, `DELETE /api/dlq/{q}`
      and `PATCH /api/system/config…`) accept a key that holds only the `monitoring` scope. The
      legacy copies refuse scoped entries, so scope has one rule.
- [x] **S4:** the `monitoring` scope admits `GET /api/events`, which serves sparse fieldsets
      including `reasoning`, and `include_deleted`. Enumerate what each monitoring consumer
      (Prometheus, json-exporter, Grafana, the frontend machine listener) actually calls, record
      that list in the PR, and narrow the scope to exactly it. If a consumer needs `/api/events`,
      admit only the fields it reads: no `reasoning`, no `include_deleted`.
- [ ] **Proof:** ops-b re-runs its auditor's S1 probe at the PR's head and quotes the 9/9 → 401
      result in its review.

**Done when:** a test shows all 9 routes answer 401 to a monitoring-only key in that configuration
and still accept an unscoped key, and a test pins the narrowed `monitoring` grant (ruling 95).

### [r122] WARN-band unit tests made cheaper in the tests

**Flags:** pre-approved under ruling 83's limits (UR-112). **Assigned:**
backend. **Depends on:** queues behind #7003 (merged). **PR:** #7027 (merged).

- [ ] The unit tests that land in the 1.5–4.0 s WARN band every run (about 10 ids, mostly
      100-example property tests) are made cheaper in the tests themselves: draw counts, fixtures,
      fake clocks. Neither timing gate is edited (rules.md §Test timing gates).

**Done when:** the slowest unit test in each of 5 consecutive green `main` runs is at or under
3.0 s, giving at least 1 s of headroom under the 4.0 s line (ruling 122).

### [r129] Backups and the batch audit load the deferred columns

**Flags:** none. **Assigned:** backend, as a bug fix outside Phase 4's priority order. **Depends
on:** queues behind `[r122]`. **PR:** #7031 (merged).

F-100, F-106 and F-108 are ruled **complete**. `Event.reasoning` and `Event.llm_prompt` are
`deferred()` (`backend/models/event.py:72-74`). `_export_table`
(`backend/services/backup_service.py:336`) and the batch audit
(`backend/api/routes/ai_audit.py:475`) read them inside an `AsyncSession`, which raises
`MissingGreenlet`: every backup fails once any event exists, and the audit fails on every event.

- [ ] Items (4) and (5) of the Done when touch `frontend/`: backend either takes frontend's review on
      those lines or splits them into a small frontend PR that merges after `[r129]`.

**Done when** (ruling 129):

1. Both jobs load the deferred columns explicitly.
2. A test backs up a populated `events` table, and the backup completes with every row present.
3. A test audits a populated table, and `processed_events` equals the number of events with
   `failed_events` at 0.
4. The Batch Audit tab and its Trigger button render when the stats are zero (`AIAuditPage.tsx`
   `hasData` gate).
5. The trigger toast reads the field the backend actually returns, either by renaming
   `queued_count` to `total_events` or by changing the schema; one side changes and the contract
   test pins it.

### [r130b] Small bugs from `F2.3`'s demotions, backend half

**Flags:** none. **Assigned:** backend, as lane bug fixes outside Phase 4's priority order.
**Depends on:** queues after `[r129]`; frontend's `[r130f]` runs in parallel. **PR:** #7088 (merged).

- [x] **F-187, F-190, F-191.** `GET /api/v1/settings` returns 500: `settings_api.py:117` feeds
      `fast_path_confidence_threshold` (default `2.0`, the deliberate "disabled" value,
      `config.py:1952`) into `DetectionSettings.fast_path_threshold`, whose schema caps it at
      `le=1.0` (`schemas/settings_api.py:53`). Make the schema and the config agree, and keep the
      disabled sentinel expressible. Ruling 168 (option b) settles the mechanism: the disabled
      state becomes an explicit `fast_path_enabled: bool` (default false) rather than an
      out-of-band threshold, so this row is met by `[r130b]` and the `2.0`/`le=10.0` above
      describe the base, not the fix.
- [x] **F-089.** Give the `job_type` query parameter `alias="type"` (`routes/jobs.py:296-299`),
      matching `job_status`.
- [ ] **F-034, link half.** `summary_detail_service.py:147` builds `/events/{id}`, a route the app
      does not have; it builds the app's working target, `/timeline?event=…`. If frontend adds an
      `/events/:id` redirect instead, backend leaves this line alone. One side changes, not both.

**Done when:** for each row, its golden spec, already written to pin the broken behaviour, is
flipped to assert the fix and passes. F-190 and F-191 also need ruling 127's writable `runtime.env`
on the CI compose before their save leg can go green; until then they flip on the read leg only
(ruling 130).

### [r149d] F-057: the event list returns `notes`

**Flags:** none. **Assigned:** backend, fix now. **Depends on:** none. **PR:** #7070 (merged).
(rulings 149, 238; records 6146380050, 6216702824)

- [x] `list_events` returns `notes`: add it to the row dict (`backend/api/routes/events.py:499-536`)
      and to `VALID_EVENT_LIST_FIELDS` (`:142`), with a test that a saved note comes back from
      `GET /api/events`.
- [ ] The read-back `test.fixme` in `frontend/tests/golden/timeline/event-detail.spec.ts` is
      flipped by `[r238]` (heavy-a; ruling 238); that golden path rules F-057. No `R2b` entry.

**Done when:** `GET /api/events` returns a saved note, and `[r238]` merges with F-057's read-back
golden leg passing.

### [r160b] Deferred Python major: huggingface-hub 2

**Flags:** none. **Assigned:** backend. **Depends on:** Phase 2's exit. **PR:** none yet. (ruling
160; dependabot #7062, closed with `@dependabot ignore this major version`)

- [ ] Bump `huggingface-hub` to 2.x in its own PR, lifting the ignore
      (`@dependabot unignore huggingface-hub`).

**Done when:** `huggingface-hub` 2.x is on `main` with the backend and AI-path suites green at its
head.

### [r211b] F-048: search skips deleted events and filters the severity it reports

**Flags:** none. **Assigned:** backend, first on its queue (fix now). **Depends on:** none.
**PR:** #7187 (merged 2026-10-16T04:40:26Z as `5365165f8`, head `4819ce171`). (rulings 211, 221;
records 6200331506, 6205729827)

- [ ] `search_events` (`backend/services/search.py`) takes the browse route's `deleted_at` predicate
      (`backend/api/routes/events.py:410`), so search never lists a soft-deleted event.
- [ ] The severity filter (`search.py:332`) tests the value the response reports
      (`backend/api/schemas/search.py:44` derives `risk_level` from `risk_score`): one derivation,
      read by both.
- [ ] Tests: a soft-deleted event never appears in search; a filter on the level a result displays
      finds it (a `high` row at score 91 is found by the level it shows).

- [ ] Frontend's `[r211f]` commits on this PR invert F-048's golden fixture (ruling 221): search
      excludes the soft-deleted row, `searchTotal` is the live count, and the defect half of the
      leg at `frontend/tests/golden/timeline/timeline-search.spec.ts:585` takes a live row on search
      page 2. Neither lane force-pushes the branch, and each fetches it before it pushes.

**Done when:** the tests pass in CI at a ready head, and `Feature check (fake AI)` passes at the
head carrying both lanes' commits, with `timeline-search.spec.ts`'s 6 legs green and its 2
`test.fixme` marks unchanged (ruling 221); `[r211f]` then removes those marks.

### [r228] One cache key shape

**Flags:** none. **Assigned:** backend, first on its queue, ahead of `[r223]` (a lane bug fix
outside Phase 4's priority order). **Depends on:** none. **PR:** #7215. (ruling 228, record 6215814018)

`[r223]`'s MEASURE (`6208408388`) found the invalidators miss the keys their routes store.
`CacheKeys` (`backend/services/cache_service.py:730`) builds keys that already carry the global
prefix, and `get` (`:123`) and `set` (`:196`) prepend `CACHE_PREFIX` (`:82`) again, so a camera
list is stored as `cache:hsi:cache:cameras:list:all`. `invalidate_pattern` (`:463`) prepends it to
the short-form pattern (`:486`), which does not match. `_get_cache_prefix()` (`:75`) has no caller.

- [ ] `CacheService`'s `get`, `set`, `invalidate_pattern` and the other `f"{CACHE_PREFIX}{key}"`
      sites, and `CacheKeys`, agree on one key shape, so each invalidator reaches the key its route
      stores. The PR states the form chosen (for example, `CacheKeys` authoritative and
      `_get_cache_prefix()` used or deleted).
- [ ] **MEASURE** against a real Redis, before and after: each cached route's stored key and
      whether its invalidator deletes it, as a table in the PR.
- [ ] Tests: the short-form pins in `backend/tests/integration/test_cache_invalidation_comprehensive.py`
      (`:440-448`) pin the stored shape, and a test proves an invalidator deletes a key its route
      stored.

**Done when:** the tests pass in CI at a ready head, and the PR's table shows every listed
invalidator deleting its route's stored key.

### [r223] The developer tools' seed and clear refresh the caches they change

**Flags:** none. **Assigned:** backend, after `[r228]` (a lane bug fix outside Phase 4's priority
order). **Depends on:** `[r228]` merged. **PR:** #7201. (rulings 223, 228; records 6205796977, 6215814018)

`seed_cameras` (`backend/api/routes/admin.py:299`) and `clear_seeded_data` (`:671`) commit without
invalidating the camera list cache, which every camera route does
(`_invalidate_cameras_cache_background`, `backend/api/routes/cameras.py:132`). `GET /api/cameras`
caches for 60 s (`cameras.py:261`), so F-197's toast names cameras the list does not show yet.

- [ ] `seed_cameras` and `clear_seeded_data` schedule the same background invalidation of the
      cameras cache as the camera routes.
- [ ] **MEASURE** every other cached read the three developer-tool writes change, and list it in the
      PR: `clear_seeded_data` deletes all events and detections (`admin.py:714-715`), `seed_events`
      (`:450`) adds events, and `backend/api/routes/events.py` caches `get_event_stats` (`:731`) and
      `get_timeline_summary` (`:907`). Each one a handler's write changes is invalidated the same way.
- [ ] Unit tests pin each handler scheduling its invalidations. No golden spec changes; #7189's
      F-197 leg reads around the cache and does not wait for this.

**Done when:** the unit tests pass in CI at a ready head, and the PR's list names every cached read
the three handlers change, each invalidated.

### [r244] The monitoring key gets no recommendation prose

**Flags:** `owner` (security and auth). **Assigned:** `uplevel-backend`, after `[r223]`. #7157
becomes this package's PR, retitled with `[r244]`, and the hold ruling 209 item 3 put on it ends.
**Depends on:** none. **PR:** #7157. (ruling 244, record 6222984876)

`GET /api/ai-audit/recommendations` is in the monitoring scope (`backend/core/constants.py`,
`MONITORING_SCOPE_PATHS`), and each item's `suggestion` is the LLM's free-text advice
(`backend/api/schemas/ai_audit.py`, `RecommendationItem`). Ruling 95 admits to a monitoring-scoped
key only the fields its consumer reads, and Grafana's panel shows `$.recommendations[*].suggestion`
through that key (`monitoring/grafana/dashboards/consolidated.json:5934`).

- [x] A monitoring-scoped key gets `suggestion: null`, through the `scoped_key_ceiling` posture
      #7135 takes. A session cookie and an unscoped key still get the prose.
- [x] `RecommendationItem.suggestion` becomes `str | None` in the same commit, and
      `docs/openapi.json` and `frontend/src/types/generated/api.ts` are regenerated in it.
- [x] The panel labels its rows by `category` and `priority`, not by `suggestion`
      (`consolidated.json:5934`), as a cross-lane part (UR-9) that ops reviews.
- [x] Tests: the clamp is red on the unclamped handler, a leg is red if the schema flip is omitted,
      and both postures are checked (the monitoring key nulled; a cookie and an unscoped key get
      the prose).

**Done when:** the tests pass in CI, and the panel's query no longer reads `suggestion`.

### [r199] An analysis message is acknowledged only for a stored event or a terminal failure

**Flags:** `heavy`. **Assigned:** heavy-a, ahead of `B2.3`; heavy-a opens its own draft PR.
**Depends on:** none. **PR:** #7182 (merged 2026-10-15T20:25:39Z as `5d990377e`, head `3aca9abfc`).
(ruling 199, record 6198662741)

The analysis worker acknowledges each stream message once `_process_analysis_item` returns
(`backend/services/pipeline_workers.py:943`, and `:931` on the reclaim path), and that method
catches every exception and returns (`:1153`). So a failure other than a VLM error (a Postgres
write error, a Redis error, a bug) is acknowledged with no event stored. VLM errors are already
stored as a `verification_failed` event (`backend/services/vlm_analyzer.py:656`).

- [ ] `_process_analysis_item` returns a disposition, and the loop acts on it. **Stored** (the
      batch has an event): acknowledge. **Terminal** (the payload fails validation, or the batch is
      missing or has no detections): move it to the dead-letter stream with its reason. **Retry**
      (anything else): leave it pending for the existing reclaim (`:925-931`), whose third
      delivery goes to the dead-letter stream. The `batch.analysis_failed` broadcast's `retryable`
      field follows the disposition.
- [ ] When the Redis key misses (`vlm_analyzer.py:468`), `analyze_batch` looks up `events.batch_id`
      (unique, `backend/models/event.py:54`). If an event exists, it returns that event without
      calling the VLM, and writes whatever post-commit step is missing: the Redis key, and the
      notify decision when the event has none.
- [ ] Test (a), integration tier: a write that fails before the commit leaves the message pending,
      and a redelivery stores exactly one event.
- [ ] Test (b): a process that stops after the commit, before the Redis key and the notify
      decision. The redelivery stores no second event, makes no VLM call, and writes the notify
      decision.
- [ ] Test (c): an invalid payload leaves one dead-letter entry and nothing pending. Test (d): a
      failure on all three deliveries leaves one dead-letter entry.
- [ ] The PR body says whether the detection worker's stream loop (`pipeline_workers.py:400-418`)
      has the same shape. It changes nothing there.

**Done when:** tests (a) to (d) pass in CI at a ready head, and the PR body names the line where
each disposition is decided.

### [r200] One owner for the running pipeline workers

**Flags:** `heavy`. **Assigned:** heavy-a, after `[r199]`; heavy-a opens its own draft PR.
**Depends on:** `[r199]` merged (both edit `pipeline_workers.py`). **PR:** #7191 (merged
2026-10-16T00:34:47Z as `78951c9b9`, head `2d8fce09f`). (ruling 200)

`PipelineWorkerManager.start()` (`backend/main.py:964`) starts the configured detection and
analysis workers (default 2 each, `backend/core/config.py:1077`, `:1085`), one batch-timeout worker
and one metrics worker. `main.py:1008-1030` then registers the four `create_*_worker` factories
(`backend/services/pipeline_workers.py:2109`, `:2140`, `:2171`, `:2202`) with `WorkerSupervisor`,
and each builds and starts one more worker: three analysis consumers where two are configured, and
two batch-timeout and two metrics workers. The manager passes no supervisor to its own workers, so
the supervisor's heartbeats and restarts cover only the extra set. Record 6198757258.

- [ ] The supervisor restarts the workers the manager built and reads their heartbeats; the
      factories that build a second set are deleted.
- [ ] Shutdown has one path: whichever owner stays stops each worker once.
- [ ] Tests: after startup the process runs exactly the configured number of detection and
      analysis consumers, one batch-timeout worker and one metrics worker; a worker whose task dies
      is restarted without the count growing; shutdown stops each worker once.
- [ ] The PR body reports whether today's two batch-timeout workers can close the same batch twice.

**Done when:** the tests pass in CI at a ready head, and `backend/main.py` builds no pipeline worker
outside `PipelineWorkerManager`.
