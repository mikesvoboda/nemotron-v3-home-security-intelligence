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
`B2.3` (ruling 241). **PR:** #7220, #7224, #7228, #7232, #7233, #7243, #7247, #7249, #7253, #7254, #7255, #7258, #7261, #7266, #7270, #7272, #7273, #7277, #7286, #7300, #7304, #7309, #7311.

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
- [x] For each feature ruled **retire**: delete its routes, schemas, services, settings, alert
      conditions and tests (batteries included). The frontend part (`F3.1`) lands in the same PR,
      so the client never calls a route that is gone.
- [x] Tables leave as upgrade steps of `B3.3`'s upgrade command, which lands first (ruling 203,
      record 6198942052), not as a hand-run DROP runbook. Until it lands, take the retirements
      that drop no table; one that drops a table waits for it (ruling 241).
- [x] `POST /api/reid/search` retires (`backend/api/routes/reid.py:78-79`, handler
      `search_similar_entities`): route, handler, tests and both its `docs/developer/api/coverage.md`
      lines (`:692`, `:856`). It has no client and no guide; Phase 4's design sessions may bring
      re-ID search back (ruling 236).
- [x] Regenerate `docs/openapi.json`.

**Done when:** for every retired feature, a grep for the identifiers its inventory row lists finds
nothing in `backend/` outside its upgrade step.

### B3.2 Delete the approved module list (OD-28 and `R2`)

**Flags:** `heavy · owner`. **Depends on:** `R2`.
**PR:** #7319. (ruling 241)

- [x] Delete in OD-28's order — the guided-constraints and trajectory modules first — then every
      module under `backend/` the reachability check reports non-shipping at this PR's head,
      outside `keep.toml`: `R2`'s §3 is approved as that rule, not as the measured snapshot
      (ruling 210, record 6200282082). The scene-change vertical stays: R2a row 24 ruled it
      complete, and `scene_change_detector.py` goes on `keep.toml` as "F-287, R2a row 24" (ruling
      183).
- [x] A non-shipping module that a **complete** feature's inventory row claims stays: add it to
      `keep.toml` with that row's id as the reason. It ships once its feature is built. Rows deferred
      to roadmap R1 go on `scripts/reachability/keep.toml` with the reason "R1 deferral, ruling 89"
      (ruling 89).
- [x] Cut `backend/services/__init__.py` and `backend/core/__init__.py` down to the names shipping
      code imports.
- [x] Delete each module's tests, batteries included. These PRs change production code, so the
      kill-loss rule does not apply; each PR discloses the scored-set change instead (`01`).

**Done when:** the reachability check (`O2.3`) reports no non-shipping module under `backend/`
outside `keep.toml`, and the suite is green.

### B3.3 Settings and residue truth

**Flags:** none. **Depends on:** `R2`.
**PR:** #7244; fourth box on #7322. (ruling 241)

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
- [x] `AIModelEnum` and the prompt-management schemas follow the prompt page's ruling.
      (Fourth box: #7322 carries it — the four values leave `AIModelEnum`/`AIModel` with their
      config schemas; upgrade `0011-retire-vision-model-prompts` deletes the four models'
      `prompt_versions` rows, converts the column to varchar and drops the native `aimodel`
      enum; its test checks every other row survives and the changed rows are exactly the four
      models' rows (`test_0011_prompt_versions_upgrade.py`, census diff on (model, version));
      the four frontend editors and the Version History filter ride as cross-lane parts;
      `FlorenceUnavailableError`/`FLORENCE_UNAVAILABLE` retire with Florence, and
      `AnalyzerUnavailableError`/`EnrichmentUnavailableError` stay.)
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

### [r295] pip leaves the production image

**Flags:** `owner` (production safety: it changes what ships, UR-98). **Assigned:** backend, after
`B3.3`'s fourth box (ruling 295). **Depends on:** #7321 (ruling 295's red-`main` exemption) merged.
**PR:** #7333. (ruling 295, record 6307239846)

On 2026-10-21 `Scan Backend Image` failed on `certifi` 2026.6.17 (GHSA-6q48-6c7w-9gw2) in pip's own
`_vendor` bundle in the `python:3.14-slim-bookworm` base image, which Trivy reports under the bare
`Python (python-pkg)` target; the app's venv carried the fixed 2026.10.19 (run `39528289094`). Only
an upstream pip release can update that bundle, so `.trivyignore:302-354` exempts five findings of
that class (msgpack, setuptools, urllib3 twice, and `certifi` from #7321), each with REVIEW BY
2026-12-20. Nothing in the production container runs pip: `backend/entrypoint.sh` and the `prod`
stage never call it, and backend code names it only in "Install with: pip install …" messages.
Dropping pip from the image removes this class of finding for good.

- [x] **The `prod` stage of `backend/Dockerfile` drops pip** and its `_vendor` bundle from the
      system site-packages, after the last step that needs it. `uv` and the venv stay.
- [x] **The five pip-bundle entries leave `.trivyignore`** in the same PR (msgpack, setuptools,
      urllib3 twice, `certifi`), and the PR's image scan is green without them — dispatch run
      39672415741 at d1ba0aa62 (job 119473608257): 168 targets, all zero, no bare
      `Python (python-pkg)` target.
- [x] **A test pins it, red first (UR-69):** the built `prod` image cannot import pip (for example,
      `docker run --rm <image> python -c "import pip"` exits non-zero in CI), or another check the
      lane names — `TestPipLeavesTheProdImage` pins the Dockerfile rm block, the in-build probe
      asserts the import fails (5/5, `/tmp/b33wt-probe-build.log`), UR-89 red-first simulation
      confirmed.

**Done when:** `CI Gate` is green at a ready head, including the image scan and the feature checks
(the stack boots without pip). The PR body shows the scan with no bare `Python (python-pkg)` target,
and the UR-89 review approves. The owner partner approves it under ruling 281 once its UR-89 review
approves and its gate is green.

### [r236] Two documented endpoints become External rows

**Flags:** none. **Assigned:** backend, after `B3.3`. **Depends on:** `R2` (Phase 2's exit).
**PR:** #7260. (ruling 236, record 6216306194)

No client in `frontend/src` calls them, but the docs tell users to:
`docs/guides/face-recognition.md:288` for `POST /api/household/members/{member_id}/embeddings`
(`backend/api/routes/household.py:460-461`), and `docs/developer/api/core-resources.md:881` for
`GET /api/detections/export` (`backend/api/routes/detections.py:2025-2026`).

- [x] Each gets an `External ›` inventory row (as F-290–F-294 are) with its documented action.
      (#7260 ticks it: F-297/F-298 rows at `docs/reference/feature-inventory.md:706-707`, both
      `awaiting real tier`; CI run 39187485514 at head `610efbbbe` — `Feature check (fake AI)` job
      117853658715 success, CI Gate 117865842291 success)
- [x] Each gets a backend golden test, as F-294's
      `backend/tests/golden/external/test_metrics_scrape.py` is, and its row flips on the run where
      it passes (rulings 103, 114). (#7260: `backend/tests/golden/external/test_household_embeddings.py`
      4 legs and `backend/tests/golden/external/test_detections_export.py` 4 legs, named in both rows)

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

The session ran on 2026-10-21, and [`../4n-arming.md`](../4n-arming.md) answers each question
(ruling 311, record 6328311780): arming gates alert creation, a critical alert is created in any
mode, a mode is the set of cameras it arms, and MQTT starts only when enabled, with broker
credentials and a command token. Ruling 311 narrows ruling 89 by one: sensitivity leaves MQTT,
since nothing reads it. Zone arm/disarm waits until detections carry a zone, and a zone command
answers "zones are not supported yet" until then.

**Alert rules** (F-216, F-217; P1) is another (ruling 89: call the rules engine after each
verdict), designed with notification history in [`../4n-alerting.md`](../4n-alerting.md). Its
schedule includes its end minute in full: a window matches when `start <= now < end + 1 minute`,
and an overnight window (end before start) wraps across midnight with the same one-minute
inclusion. Its tests pin the boundary with a fixed clock: 23:59:30
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

**The P1 packages** (ruling 308, record 6326364266). Each runs the six steps above, and its design
is step 1. Ruling 308 put the four with concurrency, erasure or data-migration risk on the heavy
agents and the rest on the fast lanes.

### B4.1 Alert pipeline core

**Flags:** `heavy`. **Assigned:** heavy-a, after `[r305]`; `W3.1`'s per-lane PRs still slot in
between (rulings 300, 308). It moves from backend, which closes #7287. **Depends on:** none.
**PR:** #7335. (ruling 308, record 6326364266)

Design: [`../4n-alerting.md`](../4n-alerting.md), "Packages" row 1, with `alert_events` (re-scoped
from "Snooze an event or alert"). Covers F-050, F-079, F-216, F-217.

- [x] The test-only PR consolidates the tests of every module the package touches (step 2).
- [ ] The build PR: `verdict`, `policy` and `pipeline` with an empty planner hook; the
      idempotency-path, recovery and sweep calls; the default rule; activity snoozes; the new
      alert columns, `alert_events` and the `open` status; an additive recorded upgrade; if
      `B4.4` landed first, Trash's alert steps (`../4n-trash.md`, "What changes").
- [ ] Golden path (pytest): confirmed gives an alert row and an `alert_created` frame; repeats
      fold; snooze holds; VLM failure gives unverified; a trusted face covering everyone gives no
      alert; rejected gives no alert.

**Done when:** steps 4–6 hold for its rows.

### B4.2 Recipients and delivery

**Flags:** none. **Assigned:** backend, after `[r295]` (ruling 308). **Depends on:** `B4.1` for the
build PR; the test-only PR may open first. Its golden path uses `[r308a]`'s sinks.
**PR:** #7339. (ruling 308, record 6326364266)

Design: [`../4n-alerting.md`](../4n-alerting.md), "Packages" row 2. Covers F-236, F-232.

- [x] The test-only PR (step 2): the notification and webhook_service suites consolidated under
      the zero kill-loss protocol (616 and 1100 mutants, kill-loss 0 both modules; the batteries'
      EQUIVALENT residue moved into `accepted_survivors.toml`, 17 entries); plus the
      `backend.api.routes.notification` suite (77 mutants, kill-loss 0) measured after UR-89 review
      found it unmeasured.
- [ ] The build PR: recipients, channels, the outbox, `planner`, the worker, email and webhook, the
      local-network flag, name redaction, history, browser rows; recipients and channels join the
      backup list without their secrets if `B4.6` has landed (else `B4.6` adds them); an
      additive recorded upgrade; if `B4.4` landed first, a purge also removes the alert's
      deliveries.
- [ ] #7336: the outbound webhooks use this package's destination policy on create, update, Test
      and send, with an "on this network" flag on the webhook (an additive column in the same
      upgrade); the worker also resends outbound deliveries whose `next_retry_at` has passed, under
      the same lease, until `max_retries`. Tests: a loopback, link-local or metadata URL is a 422;
      a private address passes only with the flag; a failed delivery is resent after its backoff on
      a fixed clock and stops at `max_retries`. The PR closes #7336 (ruling 310, record
      6327324775).
- [ ] Golden path (pytest): the webhook sink gets the payload and idempotency key and History reads
      `sent`; a retry ends `failed`; quiet hours give `suppressed`; critical breaks through.

**Done when:** steps 4–6 hold for its rows.

### B4.3 The Web Push channel

**Flags:** none. **Assigned:** backend, after `B4.2` (ruling 308). **Depends on:** `B4.2`.
**PR:** none yet. (ruling 308, record 6326364266)

Design: [`../4n-alerting.md`](../4n-alerting.md), "Packages" row 3.

- [ ] The test-only PR (step 2).
- [ ] The build PR: VAPID, the push adapter, the subscription API, expired subscriptions.
- [ ] Golden path (pytest) against `[r308a]`'s push-service fake.

**Done when:** steps 4–6 hold for its rows.

### B4.4 Trash purger

**Flags:** `heavy`. **Assigned:** heavy-a, after `B4.1` (ruling 308). **Depends on:** none; the
alert steps go with whichever of `B4.1` and `B4.4` lands second, the deliveries' with whichever of
`B4.2` and `B4.4`. **PR:** none yet. (ruling 308, record 6326364266)

Design: [`../4n-trash.md`](../4n-trash.md), the `B4.4` parts. Covers F-087, F-088 with `F4.3`.

- [ ] The test-only PR (step 2).
- [ ] The build PR: `EventPurger` and its four adapters; soft delete stops scheduling file
      deletion; the trash purge at the earlier deadline, before general retention;
      `trash_retention_days`.
- [ ] Golden path (pytest, `backend/tests/golden/external/test_trash_purge.py`) as the design
      gives it.

**Done when:** its golden path is green on the fake stack and the real-tier check is posted;
`F4.3` flips the rows.

### B4.5 Contract

**Flags:** `heavy`. **Assigned:** heavy-b, last on its queue (ruling 308). **Depends on:** `F4.2`
merged. **PR:** none yet. (ruling 308, record 6326364266)

Design: [`../4n-alerting.md`](../4n-alerting.md), "Packages" row 5.

- [ ] The test-only PR (step 2).
- [ ] The build PR: the contract upgrade translates camera settings into rules and archives the
      originals, then drops the old columns, the `delivered` value and
      `camera_notification_settings` (`threat_*` stays); the camera routes, `PATCH
/api/notification/config` and the rest of `alert_engine` go; the `alert_rules` restore
      adapter ships if `B4.6` has landed; a default rule the contract stores as a row carries a
      fixed UUID (`alert_rules.id` is UUID-typed), as `B4.7`'s seeded rule does, so a restore
      cannot duplicate it.
- [ ] Golden path: an upgrade-path test on a populated database with non-default rows, with
      `F4.2`'s golden path still green.

**Done when:** steps 4–6 hold for the cluster, as the design's "Done when" says.

### B4.6 Restore from backup

**Flags:** `heavy`. **Assigned:** heavy-b, after `O3.7` and `[r312b]`; `[r307a]` keeps its place
ahead of it if O2.4 passes first (rulings 308, 312). **Depends on:** none.
**PR:** #7345. (ruling 308, record 6326364266)

Design: [`../4n-restore.md`](../4n-restore.md), its `RestoreModal` part included (UR-9). Covers
F-101.

- [x] The test-only PR (step 2).
- [ ] The build PR: the shared table list, per-table keys, the installation id, format `1.1` and
      its adapters, three sessions, the safety backup on the data volume, the narrowed undo; if
      `B4.2` landed first, recipients and channels join the backup without their secrets; if
      `B4.7` landed first, the test that a restore keeps one "External alerts" rule.
- [ ] Golden path: pytest steps in `backend/tests/golden/external/` and the modal step in
      Playwright, as the design gives them.

**Done when:** steps 4–6 hold for F-101.

**The arming packages** (ruling 311, record 6328311780), designed in
[`../4n-arming.md`](../4n-arming.md). The heavy agent takes the core; the adapter and the UI go to
the fast lanes.

### B4.7 Arming core

**Flags:** `heavy`. **Assigned:** heavy-a, after `B4.4` (ruling 311). **Depends on:** `B4.1`
merged for the build PR; the test-only PR may open first.
**PR:** none yet. (ruling 311, record 6328311780)

Design: [`../4n-arming.md`](../4n-arming.md), "Packages" row `B4.7`. Covers F-290.

- [ ] The test-only PR (step 2): `inbound_webhooks.py` and the alerting `policy` and `pipeline`.
- [ ] The build PR: `arming.py` (`mode_at`, `is_armed`, `set_mode`, `apply_schedule`,
      `next_scheduled`); the four arming tables, with `schedule_updated_at` and a change log that
      carries every mode's exclusions; the policy hook (raised while unarmed, the mode-scoped
      override, fail-armed, the notify decision naming arming); the resolver's `external` source,
      `alert_rules.sources` and the seeded "External alerts" rule; the sweep's external clause; the
      app routes; the inbound webhooks on the four modes, with `/alert`'s namespaced `batch_id` and
      a pipeline run on every request; the scheduler; an additive recorded upgrade; the schemas and
      generated API types. Arming configuration stays out of backups (`../4n-arming.md`). The
      seeded "External alerts" rule carries a fixed UUID; whichever of `B4.6` and `B4.7` lands
      second carries a test that restores an archive holding it into an install that has it and
      finds one rule.
- [ ] Golden path (pytest, `backend/tests/golden/external/`) as the design gives it.

**Done when:** steps 4–6 hold for F-290.

### B4.8 The MQTT adapter

**Flags:** none. **Assigned:** backend, after `B4.3` (ruling 311). **Depends on:** `B4.7`, `B4.1`
(acknowledge) and `[r311a]` merged for the build PR; the test-only PR may open first.
**PR:** none yet. (ruling 311, record 6328311780)

Design: [`../4n-arming.md`](../4n-arming.md), "Packages" row `B4.8`. Covers F-291.

- [ ] The test-only PR (step 2): `mqtt_command_handler.py`, `mqtt_client.py`, `mqtt_config.py`.
- [ ] The build PR: the topics (mode, arm, disarm, acknowledge, PTZ; a zone command answers "zones
      are not supported yet"; sensitivity removed); the command token, the id check, the global rate
      limit, de-duplication and results that are not retained and never carry the token; the
      topic-id fix (`:378`, and the same read at `:383`, `:393`, `:398`); one stored config with a
      CA path, seeded from `MQTT_*`; enabling refused without broker credentials or against a broker
      that accepts an anonymous login, with a warning when TLS is off; startup in `main.py`'s
      lifespan when enabled, re-running that check and leaving MQTT off with the reason in
      Settings if it fails (a test: an enabled stored config against the anonymous listener stays
      off at startup); the `keep.toml` entries removed; the operator README's MQTT section and
      Mosquitto ACL; the operator README, `docs/ROADMAP.md` and
      `frontend/src/components/settings/AGENTS.md` stop describing the deleted MQTT publisher, Home
      Assistant discovery and MQTT settings UI (UR-81). If `F4.5` landed first, the MQTT section of
      Settings › Arming and its Playwright step.
- [ ] Golden path (pytest) against `[r311a]`'s broker, as the design gives it.

**Done when:** steps 4–6 hold. F-291 reads **works** once the MQTT section of Settings has landed
too, and its row records that sensitivity left MQTT (ruling 311).

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

- [x] **The defect:** on a re-run, the LAN-exposure prompt defaults to `n` (`setup.py:685` quick
      path, `:900` guided), and that answer drives `EXPOSE_LAN`, `FRONTEND_BIND_ADDRESS` and the
      Grafana anonymous-auth derives (`:447`, `:449`, `:482`–`:491`). Pressing Enter through a
      re-run on a LAN-exposed install silently re-binds the frontend to loopback and disarms the
      gate key scoping depends on. (pinned by
      `test_enter_only_rerun_keeps_lan_exposure_and_derives`, `test_r94_env_preserving_reruns.py:159`)
- [x] **Fix 1:** on a re-run, every prompt's default is the value already in `.env`. A first run
      keeps today's defaults. (same file, 29 tests — 38 ids expanded, two parametrized; CI run 38329937197 at head `0a48b71a6` green)
- [x] **Fix 2:** a `--convert-monitoring-key` flag rewrites only the plain monitoring-key entry in
      `API_KEYS` as a scoped entry (`{"key": …, "scope": "monitoring"}`, #6959's format) and touches
      nothing else in `.env`. Ruling 79's docs line (`docs/operator/admin/security.md`) points at
      this flag instead of a full re-run. (`security.md:24` names the flag; byte-compare pins at
      `test_convert_leaves_every_other_byte_alone:383` and
      `test_convert_leaves_an_already_scoped_key_alone:493`)

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

- [x] The unit tests that land in the 1.5–4.0 s WARN band every run (about 10 ids, mostly
      100-example property tests) are made cheaper in the tests themselves: draw counts, fixtures,
      fake clocks. Neither timing gate is edited (rules.md §Test timing gates). (#7027)

**Done when:** the slowest unit test in each of 5 consecutive green `main` runs is at or under
3.0 s, giving at least 1 s of headroom under the 4.0 s line (ruling 122). (#7027 merged
2026-10-13T01:53:27Z as `9310832d3`; the `Test Performance Audit` logs of 5 consecutive green
`main` runs read at or under 3.0 s: runs 39149793951 (2.93 s), 39153995413 (2.92 s),
39160117175 (2.92 s), 39169627409 (2.98 s), 39177015082 (2.92 s), all 2026-10-18)

### [r129] Backups and the batch audit load the deferred columns

**Flags:** none. **Assigned:** backend, as a bug fix outside Phase 4's priority order. **Depends
on:** queues behind `[r122]`. **PR:** #7031 (merged).

F-100, F-106 and F-108 are ruled **complete**. `Event.reasoning` and `Event.llm_prompt` are
`deferred()` (`backend/models/event.py:72-74`). `_export_table`
(`backend/services/backup_service.py:336`) and the batch audit
(`backend/api/routes/ai_audit.py:475`) read them inside an `AsyncSession`, which raises
`MissingGreenlet`: every backup fails once any event exists, and the audit fails on every event.

- [x] Items (4) and (5) of the Done when touch `frontend/`: backend either takes frontend's review on
      those lines or splits them into a small frontend PR that merges after `[r129]`. (backend took
      frontend's review: frontend's approves on #7031 — `6133286085`, superseded by `6149268676` —
      read items (1)–(3) observed and routed items (4)/(5) to frontend's own follow-up, naming the
      `AIAuditPage.tsx` lines and the dead `queued_count` mirror; #7031's body section 5 records the
      measured handoff. The follow-up work itself is F-108's open register row, not this box's.)

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
- [x] **F-034, link half.** `summary_detail_service.py:147` builds `/events/{id}`, a route the app
      does not have; it builds the app's working target, `/timeline?event=…`. If frontend adds an
      `/events/:id` redirect instead, backend leaves this line alone. One side changes, not both.
      (frontend shipped the redirect — ruling 167 via #7039, `frontend/src/App.tsx:273-275`
      `EventDeepLinkRedirect`; backend's line is unchanged at
      `backend/services/summary_detail_service.py:135`)

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
- [x] The read-back `test.fixme` in `frontend/tests/golden/timeline/event-detail.spec.ts` is
      flipped by `[r238]` (heavy-a; ruling 238); that golden path rules F-057. No `R2b` entry.
      (#7219 merged 2026-10-16T16:43:18Z as `30fb45c31`; the file has zero `test.fixme(` calls at
      main and the read-back leg is a real test at `:337`; F-057's row at
      `docs/reference/feature-inventory.md:407` is `awaiting real tier`; CI witness run 38925068835
      job 117055688744 at head `4d2d7b473`)

**Done when:** `GET /api/events` returns a saved note, and `[r238]` merges with F-057's read-back
golden leg passing.

### [r160b] Deferred Python major: huggingface-hub 2

**Flags:** none. **Assigned:** backend. **Depends on:** Phase 2's exit. **PR:** #7269. (ruling
160; dependabot #7062, closed with `@dependabot ignore this major version`)

- [x] Bump `huggingface-hub` to 2.x in its own PR, lifting the ignore
      (`@dependabot unignore huggingface-hub`). **PR:** #7269 merged 2026-10-19T14:00:23Z as
      `c0f125305`; huggingface-hub 2.2.0 with the floor raised to `>=2.0.0`. Green at head
      `63a62d3baa` from the first ready run, CI run 39256128444 (all five workflows; slow-tier
      census 30.74s vs the 60.0s budget), backend unit suite 31,876 passed / 122 skipped /
      8 xfailed re-run locally at that head.

**Done when:** `huggingface-hub` 2.x is on `main` with the backend and AI-path suites green at its
head. — OBSERVED: 2.2.0 on `main` (`c0f125305`), backend unit suite green at the head (both the
ready run 39256128444 and the local re-run), AI-path import smoke in the PR body's evidence 4.

### [r211b] F-048: search skips deleted events and filters the severity it reports

**Flags:** none. **Assigned:** backend, first on its queue (fix now). **Depends on:** none.
**PR:** #7187 (merged 2026-10-16T04:40:26Z as `5365165f8`, head `4819ce171`). (rulings 211, 221;
records 6200331506, 6205729827)

- [x] `search_events` (`backend/services/search.py`) takes the browse route's `deleted_at` predicate
      (`backend/api/routes/events.py:410`), so search never lists a soft-deleted event.
      (#7187; live at main: `search.py:451` `base_query.where(Event.deleted_at.is_(None))`,
      pinned by `test_search_never_returns_soft_deleted_events`, `test_search_api.py:342`)
- [x] The severity filter (`search.py:332`) tests the value the response reports
      (`backend/api/schemas/search.py:44` derives `risk_level` from `risk_score`): one derivation,
      read by both. (#7187; `search.py:355` filters on `Event.computed_risk_level`)
- [x] Tests: a soft-deleted event never appears in search; a filter on the level a result displays
      finds it (a `high` row at score 91 is found by the level it shows).
      (`test_search_api.py:342` and `:381`; 16 legs in the file, CI run 38833479192 at head
      `ef7c50364` ran them — its red jobs were `Feature check (fake AI)`, the `CI Gate` aggregate,
      and `Collection Sanity`'s expired-`pytest_skip` ratchet (7 entries, disclosed in #7187's
      review comment `IC_kwDOQs9zJM8AAAABceRGAw`, not the body); the ratchet fix is #7195
      `ec6650761`, the Feature-check reds are the ones `[r211f]` below repairs)

- [x] Frontend's `[r211f]` commits on this PR invert F-048's golden fixture (ruling 221): search
      excludes the soft-deleted row, `searchTotal` is the live count, and the defect half of the
      leg at `frontend/tests/golden/timeline/timeline-search.spec.ts:585` takes a live row on search
      page 2. Neither lane force-pushes the branch, and each fetches it before it pushes.
      (#7210 merged 2026-10-16T20:07:51Z, #7225 merged 2026-10-17T01:32:18Z; the spec has zero
      `test.fixme(` marks at main, its 8 legs green in run 38932915995 job 117083054790, and the
      post-repair `Feature check` legs are green in run 39027699075 at `954187e1f` —
      `Feature check (fake AI)` and `(seeded)` jobs 117381981896/117381981913, CI Gate success)

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

- [x] `CacheService`'s `get`, `set`, `invalidate_pattern` and the other `f"{CACHE_PREFIX}{key}"`
      sites, and `CacheKeys`, agree on one key shape, so each invalidator reaches the key its route
      stores. The PR states the form chosen (for example, `CacheKeys` authoritative and
      `_get_cache_prefix()` used or deleted). (#7215: `CacheKeys` authoritative, `_get_cache_prefix()`
      consumed at `cache_service.py:104`, the double prepend and the prepend-in-`invalidate_pattern`
      deleted; `CACHE_PREFIX` kept only for backward-compatible imports, `:85`)
- [x] **MEASURE** against a real Redis, before and after: each cached route's stored key and
      whether its invalidator deletes it, as a table in the PR. (#7215 body's table: 0/8 → 7/8
      pre-existing matches, the 8th the orphan `timeline_summary:*` family, deleted by design)
- [x] Tests: the short-form pins in `backend/tests/integration/test_cache_invalidation_comprehensive.py`
      (`:440-448`) pin the stored shape, and a test proves an invalidator deletes a key its route
      stored. (`TestCacheKeysRoutesReachTheirInvalidator` at `:966`, red-before/green-after)

**Done when:** the tests pass in CI at a ready head, and the PR's table shows every listed
invalidator deleting its route's stored key. (CI run 38930467741 success at the ready head
`4da8cca9ee3d1c1e67468f16a354519c1ee94dfc` — 0 failed jobs, 46 success; merged as `4cefe81e4`)

### [r223] The developer tools' seed and clear refresh the caches they change

**Flags:** none. **Assigned:** backend, after `[r228]` (a lane bug fix outside Phase 4's priority
order). **Depends on:** `[r228]` merged. **PR:** #7201. (rulings 223, 228; records 6205796977, 6215814018)

`seed_cameras` (`backend/api/routes/admin.py:299`) and `clear_seeded_data` (`:671`) commit without
invalidating the camera list cache, which every camera route does
(`_invalidate_cameras_cache_background`, `backend/api/routes/cameras.py:132`). `GET /api/cameras`
caches for 60 s (`cameras.py:261`), so F-197's toast names cameras the list does not show yet.

- [x] `seed_cameras` and `clear_seeded_data` schedule the same background invalidation of the
      cameras cache as the camera routes. (#7201; `_invalidate_devtool_caches_background` at
      `backend/api/routes/admin.py:46`, wired into both handlers)
- [x] **MEASURE** every other cached read the three developer-tool writes change, and list it in the
      PR: `clear_seeded_data` deletes all events and detections (`admin.py:714-715`), `seed_events`
      (`:450`) adds events, and `backend/api/routes/events.py` caches `get_event_stats` (`:731`) and
      `get_timeline_summary` (`:907`). Each one a handler's write changes is invalidated the same way.
      (#7201 body's census table, restated after its round-1 review flagged 2 false rows; the
      invalidator now names cameras, events, event_stats, timeline_summary and trends, `admin.py:84-89`)
- [x] Unit tests pin each handler scheduling its invalidations. No golden spec changes; #7189's
      F-197 leg reads around the cache and does not wait for this.
      (`backend/tests/unit/api/routes/test_admin_cache_invalidation.py`, 10 pins)

**Done when:** the unit tests pass in CI at a ready head, and the PR's list names every cached read
the three handlers change, each invalidated. (CI run 38975925208 attempt 2 success at `6db72093c`,
0 red jobs; merged 2026-10-17T00:40:09Z as `cd68cbca6`, head `85a2d8b21`)

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

- [x] `_process_analysis_item` returns a disposition, and the loop acts on it. **Stored** (the
      batch has an event): acknowledge. **Terminal** (the payload fails validation, or the batch is
      missing or has no detections): move it to the dead-letter stream with its reason. **Retry**
      (anything else): leave it pending for the existing reclaim (`:925-931`), whose third
      delivery goes to the dead-letter stream. The `batch.analysis_failed` broadcast's `retryable`
      field follows the disposition. (#7182; `AnalysisDisposition` at `pipeline_workers.py:708`,
      returned at `:980`/`:1102`/`:1126`/`:1156`)
- [x] When the Redis key misses (`vlm_analyzer.py:468`), `analyze_batch` looks up `events.batch_id`
      (unique, `backend/models/event.py:54`). If an event exists, it returns that event without
      calling the VLM, and writes whatever post-commit step is missing: the Redis key, and the
      notify decision when the event has none. (#7182)
- [x] Test (a), integration tier: a write that fails before the commit leaves the message pending,
      and a redelivery stores exactly one event. (`test_analysis_stream_delivery.py:159`)
- [x] Test (b): a process that stops after the commit, before the Redis key and the notify
      decision. The redelivery stores no second event, makes no VLM call, and writes the notify
      decision. (`:237`)
- [x] Test (c): an invalid payload leaves one dead-letter entry and nothing pending. Test (d): a
      failure on all three deliveries leaves one dead-letter entry. (`:331`, `:374`; the file
      registered in CI's shard list, `.github/workflows/ci.yml:1435`)
- [x] The PR body says whether the detection worker's stream loop (`pipeline_workers.py:400-418`)
      has the same shape. It changes nothing there. (#7182 body: Yes — the same
      unconditional-acknowledge shape at `:406-407`/`:418-419`; unchanged per ruling 199 item 4)

**Done when:** tests (a) to (d) pass in CI at a ready head, and the PR body names the line where
each disposition is decided. (CI witness run 38794448920 at head `3aca9abfc` —
`Integration Tests (Services)` job 116631886441 and the `Backend Integration Tests` gate
116635317375, both success; merged 2026-10-15T20:25:39Z as `5d990377e`)

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

- [x] The supervisor restarts the workers the manager built and reads their heartbeats; the
      factories that build a second set are deleted. (#7191; the manager attaches its own four
      workers to one supervisor, `pipeline_workers.py:1913-1950`; the `create_*_worker` factories
      are gone from `backend/services/pipeline_workers.py`)
- [x] Shutdown has one path: whichever owner stays stops each worker once. (#7191)
- [x] Tests: after startup the process runs exactly the configured number of detection and
      analysis consumers, one batch-timeout worker and one metrics worker; a worker whose task dies
      is restarted without the count growing; shutdown stops each worker once.
      (`backend/tests/unit/services/test_pipeline_worker_single_owner.py`, 3/3; golden
      `frontend/tests/golden/operations/worker-management.spec.ts:50-58` names the 6 supervised
      workers)
- [x] The PR body reports whether today's two batch-timeout workers can close the same batch twice.
      (#7191 body: Yes — two `BatchAggregator` instances with per-instance `asyncio.Lock`s
      (`pipeline_workers.py:212`/`:1190`, `batch_aggregator.py:211`), the non-atomic
      `set(batch:…:closing)` at `batch_aggregator.py:875` with the re-check at `:881` leaving a
      close-close window)

**Done when:** the tests pass in CI at a ready head, and `backend/main.py` builds no pipeline worker
outside `PipelineWorkerManager`. (CI witness run 38825213735 at head `2d8fce09f` — unit shards
116733233591/116733233670 and the `Backend Unit Tests` gate 116735062460 success; merged
2026-10-16T00:34:47Z as `78951c9b9`; `backend/main.py:954` starts only the manager)

### [r267b] The verdict-engine emit-failure test can fail

**Flags:** none. **Assigned:** backend, first on its queue after the PR it holds (UR-52).
**Depends on:** none. **PR:** #7283. (ruling 267, record 6266846674; audit item Q-004 of
`[r262]`)

`test_emit_failure_does_not_break_the_probe`
(`backend/tests/unit/services/test_verdict_engine_status.py`:159) cannot fail: `observe()` schedules
the emit with `create_task` and returns first, so the mocked error surfaces only in an orphan task.
Deleting the `try/except` around the emit (`backend/services/verdict_engine_status.py`:285-291)
leaves the test green.

- [x] The test observes the swallow: it captures the scheduled task and asserts it finishes
      without an exception, or asserts the "Failed to emit verdict-engine status event" log record.
      (ready run CI 6938, attempt 1, green at 1cb452c40; red proof in #7283)

**Done when:** the test passes in CI at a ready head, and the PR shows that deleting the
`try/except` turns it red.

### [r271a] The system broadcaster survives a Redis timeout and reads Redis's health result

**Flags:** none. **Assigned:** backend, first on its queue after the packages it holds (UR-52).
**Depends on:** none. **PR:** #7299. (ruling 271, record 6277412644, corrected by 6281398804
and 6281511059; audit items Q-052, Q-053, Q-055 to Q-057 and the re-issued Q-054 of `[r262]`,
#7041)

Cites are at the audit's pin `41bc0fce7`; re-read them on the PR's base. In
`backend/services/system_broadcaster.py` nine of the handlers that guard Redis calls catch only
builtin exceptions, so `redis.exceptions.TimeoutError` (a `RedisError`) escapes them. On publish
(`:314`, `:364`) the loop's `except Exception` (`:1235`) costs the tick. On start (`:564`) the
escape leaves `start_broadcasting()` before its loop task exists, and the lifespan's unguarded call
(`backend/main.py:1018`) fails startup; on stop (`:583`, `:589`) it ends the lifespan's shutdown at
`backend/main.py:1335`, skipping the steps after it; on reset (`:612`, `:617`, `:631`) and in the
listener (`:693`) it kills the listener task. `_check_redis_health` (`:1005-1015`) returns True
whatever the dict `health_check()` returns says, and the storm probe
(`backend/tests/unit/services/test_system_broadcaster.py:1345`) stubs `broadcast_status` and
`broadcast_performance`, so it passes against the loss.

- [x] Every `except` clause in `system_broadcaster.py` that guards a Redis call also catches
      `redis.exceptions.RedisError`: at the pin `:314`, `:364`, `:564`, `:583`, `:589`, `:612`,
      `:617`, `:631` and `:693`. The PR lists the clauses it changed (ruling 271's corrections).
      (861df9886 widens exactly those nine: six builtin-only tuples become
      `(ConnectionError, TimeoutError, OSError, RedisError)` and three builtin+RuntimeError
      tuples become `(ConnectionError, TimeoutError, OSError, RuntimeError, RedisError)`;
      the DB-guard clauses :790/:878/:901/:940/:959/:1101 are untouched, and :988/:1010
      already carried RedisError from 88e0d3457.)
- [x] A test shows a `RedisError` from `unsubscribe` or `close` during reset does not stop the
      re-subscribe or kill the listener.
      (test_system_broadcaster_reset_survives_rediserror_and_resubscribes in c3db11808: both
      cleanup arms raise redis.exceptions.TimeoutError, the re-subscribe still wins
      `_pubsub`; red on the pre-fix code - the escape aborted `_reset_pubsub_connection`.)
- [x] `_check_redis_health` reads the result `health_check()` returns: healthy returns True,
      anything else returns False and logs the payload; the `RedisError` arm stays; the callers
      (`:807`, `:1093`) keep their boolean contract; the twin test's stub (`:1321`) returns a
      result dict in the same edit.
      (861df9886 branches on the dict: healthy -> True, anything else -> log + False; the arm
      stays, reworded per Q-057; twin stub is a result dict in c3db11808; the new
      unhealthy-dict test is red on the pre-fix code, which returned True regardless.)
- [x] The storm probe runs the real broadcast methods with publish raising
      `redis.exceptions.TimeoutError` and asserts every message type is still delivered locally
      each tick; the PR shows it red on the pre-fix code.
      (c3db11808 rewrites the probe: real broadcast_status/broadcast_performance, publish
      raising every call, per-type local send_text census >= 3 ticks. Red on the pre-fix
      code means `performance_update` delivered on 0 ticks; the probe's
      `assert perf_sends >= 3` fails there; `system_status` kept delivering locally
      because local sends happen before publish (`:299-305`), so only the
      `performance_update` leg of the loop died. Green at 861df9886.)
- [x] The timeout test's docstrings say its seam is synthetic (Q-056), and the `RedisError`
      comment states the real reason (Q-057).
      (79aac9164: all three sibling docstrings - failure, timeout, storm probe - state the
      seam is synthetic and the wrapper absorbs every Exception; 861df9886 rewords the
      :1010 comment to the real rationale, keeping the hierarchy clause and the
      outside-guard parenthetical; the true escape claim at :988 is left untouched.)

**Done when:** the tests pass in CI at a ready head, and the PR shows the corrected probe red
before the fix.

### [r271b] Backups keep alert metadata

**Flags:** none. **Assigned:** backend, after `[r271a]` (ruling 271).
**Depends on:** none. **PR:** #7302. (ruling 271, record 6277412644; audit items Q-040 to Q-042
of `[r262]`, #7031)

Cites are at the audit's pin `41bc0fce7`; re-read them on the PR's base. The export in
`backend/services/backup_service.py` builds `column_names` from the mapper's column keys and reads
`getattr(record, col_name, None)` (`:361-362`). For `Alert` the column key `metadata` returns
SQLAlchemy's `MetaData`, not the payload attribute `alert_metadata`
(`backend/models/alert.py:120-121`): backups carry `"metadata": "MetaData()"` and restore
(`restore_service.py`) drops the key, so the payload is lost both ways. Do not generalize:
`Alert` is the only walked model with this collision.

- [x] The export writes each alert's `alert_metadata` payload, and restore writes it back.
      (23e4bf719 resolves each mapper column to its class-bound attribute via `mapper.column_attrs`
      — identity on the column object — and writes the payload under the attribute's key, so the
      backup carries `"alert_metadata": {...}` instead of `"metadata": "MetaData()"`; the other 8
      walked models have attribute key == column key, so their rows are byte-identical. Restore
      needed no change: it inserts by the JSON key, which is now the attribute name — probe E2 /
      the prefix-restore test already showed fixed-shape rows restore.)
- [x] A round-trip test: a seeded alert's payload survives backup then restore, a null payload stays
      null, and a backup made before the fix restores with `alert_metadata` null and no error; the
      test fails on the old export.
      (Red pin 87d1b0e83: unit `KeyError: 'alert_metadata'`; integration export
      `alert_metadata=None, metadata='MetaData()'`; round-trip `came back with alert_metadata=None`
      — all three failed on the pre-fix code, quoted verbatim in the commit body. Null-stays-null
      and pre-fix-backup-restores-with-null-and-no-error pins were green before the fix and stay
      green after. All 4 green at 23e4bf719: unit file 22 passed, integration class 4 passed.)
- [x] The module and class docstrings' cites point at the export loop and the undefer loop
      (`:346-349`) (Q-041, Q-042). (f651b6f77 re-anchors them at the post-fix head: walk
      `:324`, `:378`; undefer `:357-360` — the fix commit shifted the walk's getattr read, so the
      numbers were re-measured and each cite read back with `sed -n` before being written.)

**Done when:** the tests pass in CI at a ready head.
(Ticked: ready run 39417871877 at `f1b029af1` — the first non-draft run; 50 non-skipped
jobs all success, `CI Gate (Required Checks)` completed/success at that head, companions
Coverage Gate / AGENTS.md Validation / Docs Drift / PR Review Bot all success.)

### [r277a] The events `fields` contract and a misleading comment

**Flags:** none. **Assigned:** backend, after `[r271b]` (#7302). **PR:** #7306. (ruling 277,
record 6291992942; audit items Q-068 and Q-114 of `[r262]`, #7041)

- [x] `list_events`' `fields` description names exactly the fields in `VALID_EVENT_LIST_FIELDS`,
      with `detection_ids` out and `notify` in. A test fails if they drift apart, either by
      deriving the description from the set or by asserting that every documented field is
      accepted. Regenerate `docs/openapi.json` if it changes.
      (Derived: `fields_query_description()`, commit `03d4daecf`; drift tests in
      `test_events.py` + the re-pointed pin `test_events_verification_field.py` `173b7cfad`;
      `openapi.json` regenerated.)
- [x] The comment at `backend/api/routes/system.py:4132-4135` says that only `last_activity` goes
      through the set wrapper (`batch_aggregator.py:641`) and is JSON-quoted, that `started_at` is
      written raw (`:427`), and that `_coerce_scalar` handles both.
      (Commit `03d4daecf`.)

**Done when:** the description drift test passes in CI at a ready head and the comment matches the
writers it describes.
(ticked: run `39435442971` at `173b7cfad` — 66/66 non-skipped jobs success, CI Gate success;
PR #7306)

### [r285] Four backend bugs the maui production-shape run found

**Flags:** none. **Assigned:** backend, first on its queue (ruling 285). **Depends on:** none.
**PR:** #7318. (ruling 285, record 6300916398; amendments 6301639831 and 6302995876)

The owner's maui discovery for `O2.5` item 2 ran production's compose shape on real hardware and
found four product bugs CI cannot see. The PR auto-merged with UR-89 approval at 82179a652 — the
second approval, after the bookkeeping commit 827eb5dba reset the first per UR-106 (comments
6307756549 and 6308312236). Its handoff carries reference diffs and red-and-green
evidence for three of them; this package writes each fix fresh on `main`, each with its own
failing-first test (UR-69), and ops-a's `O2.5` venue fixes leave them out (ruling 287 item 4).

- [x] **F-182's Compare.** `GET /api/system/gpu-config/history/diff` is registered after
      `GET /api/system/gpu-config/history/{version_id}` in `backend/api/routes/gpu_config.py`, so
      `diff` is matched as a version id. Register `diff` first; handler bodies and the API contract
      are unchanged, and `docs/openapi.json` changes only if route order shows in it. The test calls
      `/api/system/gpu-config/history/diff?from_version=…&to_version=…` through the mounted router.
      F-182's row in `docs/reference/feature-inventory.md` replaces its Compare break note with the
      fix, and its ruling cell reads "ruling 285: as ruling 182 for F-176 and F-178"
      (`feature-inventory-cite-drift.mjs` reports `DRIFT: 0`). — green at b6d61c5c0, run
      39538063327; UR-89 approved (comment 6307756549).
- [x] **PCIe Gen 6** (amendment 6301639831). `GPUStatsResponse.pcie_link_gen` and
      `GPUStatsSample.pcie_link_gen` (`backend/api/schemas/system.py`) are bounded `ge=1, le=5`,
      so a Gen 6 link fails the GPU stats schema. Drop the upper bound and keep `ge=1`, as
      `pcie_link_width` has; correct the "(1-4)" descriptions and comments
      (`backend/services/gpu_monitor.py`, `backend/models/gpu_stats.py`); regenerate
      `docs/openapi.json` and `frontend/src/types/generated/api.ts`. The test has both schemas
      accept `pcie_link_gen=6` (or `GET /api/system/gpu` returns a Gen 6 sample). — green at
      b6d61c5c0, run 39538063327; UR-89 approved (comment 6307756549).
- [x] **The webhook retry commits before it answers** (amendment 6302995876). `retry_delivery`
      (`backend/api/routes/outbound_webhooks.py`) takes `Depends(get_db)`, and `get_db` commits
      after its `yield`, which under FastAPI 0.143's default dependency scope ran after the 200 was
      sent: an immediate history read saw the old count. Fix the route (for example
      `Depends(get_db, scope="function")`, or an explicit commit before returning), with red-first
      tests for the stale read and for a success sent before a failed commit. — green at
      b6d61c5c0, run 39538063327; UR-89 approved (comment 6307756549).
- [x] **The other routes that answer before they commit are counted, not fixed.** The PR body lists
      every route handler that leaves its commit to `get_db`'s teardown, read route by route with
      the services it calls, says for each whether a client can observe the gap, and ends with a
      recommendation for a fix across that surface, which waits for the owner's ruling. — the
      census and no-gap classifications were verified by the UR-89 reviewer on every surface
      spot-checked (flush-only services confirmed); two narrative attributions corrected in the
      follow-up notes (heatmap commit lives in `heatmap_service.py:514`, mqtt's
      `_save_mqtt_config` at `backend/api/routes/mqtt_config.py:154`).
- [x] **A degraded batch's message is delivered** (amendment 6302995876).
      `WebSocketBatchAnalysisCompletedData.risk_score` (`backend/api/schemas/websocket.py`) is
      `int`, while the event payload accepts `int | None`; a degraded VLM batch publishes `None`,
      so `broadcast_batch_analysis_completed` (`backend/services/event_broadcaster.py`) fails
      validation and never sends it. The message validates and is sent with a null risk score,
      matching the event payload, or the PR says why another shape is right. The PR names what the
      frontend's `batch_analysis_completed` consumer does with a null score; if it cannot handle
      one, the smallest frontend fix rides along and frontend reviews that part. A red-first test
      shows a degraded batch's message is sent. — green at b6d61c5c0, run 39538063327; UR-89
      approved (comment 6307756549); frontend ride-along reviewed by the reviewer (chip guard
      distinguishes absent from scored-0, `BatchProcessingIndicator.tsx:170-180`).

**Done when:** each fix's test was committed red ahead of it, `CI Gate` is green at a ready head,
and the UR-89 review approves. `[r285]` is one PR.

### [r303] Detector bake-off

**Flags:** `heavy`. **Assigned:** heavy-b, after `B2.3` and ahead of `B4.5`; the operator runs
its GPU measurement (ruling 309). **Depends on:** `[r309]`'s labelled file.
**PR:** none yet. (rulings 303, 309; records 6323705837, 6327202214)

Phase 4. Nothing about the detector changes before this test. `yolo26m` came in through #4403 and
#4431 (2026-01), replacing RT-DETRv2, and was never compared. RF-DETR leads on COCO at the same
speed (its README: T4, TensorRT FP16, batch 1): RF-DETR-M 54.7 AP at 4.4 ms and RF-DETR-L 56.5 AP
at 6.8 ms (704 px input), against YOLO26-M at 52.5 AP and 4.4 ms on the same table (Ultralytics'
own: 53.1 AP and 4.7 ms). The licences differ: YOLO26's code and weights are AGPL-3.0 or a paid
Ultralytics Enterprise licence, and this repo is Apache-2.0; RF-DETR's N, S, M and L are Apache-2.0
(its XL, 2XL and smallest sizes are PML 1.0). The R2 sheet records the same open question for the
`threat` model (`r2-sheet.md:269`). COCO is not home-camera footage: night IR and small, distant
people decide this, and no published number measures them.

- [x] **First question to the owner:** the labelled frame set (source, who labels, size), as `B2.3`
      settles its crops. Ruling 309 answers it: about 400 stills from the owner's cameras,
      stratified into day, night/IR and distant subjects (at least 100 with a person or vehicle in
      each), pre-boxed by OWLv2 or Grounding DINO and corrected by the owner, prepared by
      `[r309]`. The frames and labels stay on the host, and PRs post counts only. Synthbench's
      verified stills score as a second table.
- [ ] Export YOLO26-M, RF-DETR-M and RF-DETR-L to TensorRT and serve each under Triton (UR-86), on a
      desktop RTX card with the VLM resident.
- [ ] Measure per model: AP on the product's classes (people and vehicles first), split by day,
      night/IR and distant subjects; latency per frame; GPU memory; and the licence of code and
      weights.

**Done when:** the PR posts a recommendation with these numbers for an owner ruling. Nothing in
production changes: no `models.yml` swap, no switch flip.

### [r306a] Re-ID's default becomes the gateway

**Flags:** `owner` (it changes production's model path). **Assigned:** backend, next on its queue
(ruling 306). **Depends on:** O2.4's pass (ruling 306 item 1): `[r252]`'s run was spent without one,
and `[r312a]`'s second run, reading every plan stage at or above 0.999 on all 36 crops on the image
`main` serves, is O2.4's evidence (ruling 312 point 4).
**PR:** none yet. (ruling 306, record 6323748868)

`REID_BACKEND` (`backend/core/config.py:1445`) picks between the backend's resident OSNet copy
(`local`, CPU-only torch wheels, `pyproject.toml:984-994`) and the gateway's GPU `reid`
(`gateway`), "the same network and weights" (`config.py:1449`), under one model ID
(`osnet-ain-x1-0@osnet_ain_x1_0_msmt17@8a07e8da3894`, #7002 `6154659954`). Stored person vectors
stay valid across the flip once parity holds. On `RESULT: PASS`, `O2.4` goes to `done` and `B2.3` is
unblocked (ruling 107).

- [ ] `REID_BACKEND`'s default becomes `gateway` in `backend/core/config.py` and in every compose
      or env file that sets it.
- [ ] A test pins the default, red first (UR-69).
- [ ] The PR cites the PASS run.

**Done when:** `CI Gate` is green at a ready head and the UR-89 review approves.

### [r306b] The backend's CPU copy of OSNet leaves

**Flags:** none. **Assigned:** backend, after `[r306a]` merges (ruling 306). **Depends on:**
`[r306a]` merged. **PR:** none yet. (ruling 306, record 6323748868)

UR-85 lets a proven GPU path stand without a CPU fallback.

- [ ] Remove the `local` path: `backend/services/osnet_loader.py` and its callers' CPU branch,
      `torchreid`, and `torch` from the backend only if no other kept import needs it. The PR
      reports the import trace.

**Done when:** `CI Gate` is green at a ready head, the import trace is in the PR body, and the UR-89
review approves.

### [r307c] fast-alpr leaves the tree

**Flags:** `owner` (a deletion). **Assigned:** backend, after `B3.3` (ruling 307). **Depends on:**
none. **PR:** none yet. (ruling 307, record 6323846997)

fast-alpr never runs in production. The backend image installs only the `face` extra
(`backend/Dockerfile:150`), so `collect_plate_text` (`backend/services/vlm_specialists.py:553-589`)
always returns its "unavailable" line. F-268's ruled reader decision compares PaddleOCR with a
YOLO11 plate detector against the VLM reading crops; fast-alpr is not a candidate. At `bc89bf68a` a
grep also finds `scripts/download-model-zoo.py:88` and a docstring in
`backend/services/alpr_service.py:541`; the Done when covers them.

- [ ] Delete `backend/services/fast_alpr_loader.py` and its tests, the `alpr` extra and its lock
      entries, the `fast-alpr` row in `models.yml` and `model_zoo`'s loader entry
      (`backend/services/model_zoo.py:51`, `:355`), the suppression-registry entry, and the mentions
      in `README.md`, `ai/AGENTS.md`, `ai/download_models.sh` and the backend `AGENTS.md` files
      (UR-81).
- [ ] `collect_plate_text` keeps returning its "unavailable" line, now without importing a reader,
      so production's prompt does not change. The plate-reads tables and routes stay (F-268 is
      complete); F-268's reader decision is unchanged, and its candidates run on Triton (UR-86).

**Done when:** nothing in the tree imports or installs fast-alpr, the kept-feature check finds no
lost writer, and the UR-89 review approves.

### [r307b] The face leg calls the gateway

**Flags:** `owner` (production's face path changes). **Assigned:** backend, after `[r307a]` passes
(ruling 307). **Depends on:** `[r307a]`'s `RESULT: PASS`.
**PR:** none yet. (ruling 307, record 6323846997)

The face leg is CPU-only by an earlier choice, not a limit:
`backend/services/face_recognizer_loader.py:19` and `:152` force `CPUExecutionProvider` to keep it
out of the VRAM budget.

- [ ] The face leg calls the gateway's SCRFD and ArcFace routes (`[r307a]`). Stored face embeddings
      keep their model IDs.
- [ ] A test pins the gateway path, red first (UR-69).
- [ ] The CPU path (`face_recognizer_loader.py`'s ONNX sessions, the `face` extra, and
      `onnxruntime` if no other kept import needs it) is removed in this PR or a follow-up it names.

**Done when:** `CI Gate` is green at a ready head and the UR-89 review approves.
