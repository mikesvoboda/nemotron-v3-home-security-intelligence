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

**Flags:** `heavy`; label `cell:heavy-2`. **Depends on:** `O2.4` (its `RESULT: PASS` posted).
Approved by owner ruling 107 (issue #6854, comment `6109720693`, 2026-10-11). It may stay open past
Phase 2's exit (UR-10, contract rule 5).

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

**Flags:** `heavy · owner`. **Depends on:** `R2` (rules.md §Claiming and assigning work); lands in
one PR with `F3.1`.

**Files:** whatever each retired feature's inventory row lists under "modules".

- [ ] First, OD-20's already-ruled retirement of the enrichment surface (hook, route, types and
      tombstone in one commit; ISS-073).
- [ ] For each feature ruled **retire**: delete its routes, schemas, services, settings, alert
      conditions and tests (batteries included). The frontend part (`F3.1`) lands in the same PR,
      so the client never calls a route that is gone.
- [ ] Tables leave through a dated DROP runbook in `docs/api/migrations/`, following the R8-S4
      precedent (`cafad910`).
- [ ] Regenerate `docs/openapi.json`.

**Done when:** for every retired feature, a grep for the identifiers its inventory row lists finds
nothing in `backend/` outside the DROP runbook.

### B3.2 Delete the approved module list (OD-28 and `R2`)

**Flags:** `heavy · owner`. **Depends on:** `R2`.

- [ ] Delete in OD-28's order — the guided-constraints and trajectory modules first, then the
      scene-change vertical — then the rest of the list the owner approved at `R2`.
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

- [ ] **MEASURE** the settings fields read nowhere outside `config.py` (50 at `d6ba78d5`, `00 §4.1`)
      and delete them with their `.env.example` and compose lines.
- [ ] Add a ratchet test: every `Settings` field is read outside `config.py`, or sits on an
      allowlist with a reason.
- [ ] Rename live code still carrying retired names (`get_nemotron_analyzer_dep`,
      `summary_generator._call_nemotron`, Nemotron-named metrics); delete the uncalled metrics and
      unused exception classes `00 §4.1` lists.
- [ ] `AIModelEnum` and the prompt-management schemas follow the prompt page's ruling.
- [ ] **DECIDE** whether the `alembic` dependency stays (`00 §7`: no Alembic directory exists).

**Done when:** the ratchet test passes, and the PR reports the before/after count of `nemotron`,
`florence` and `enrichment` hits in `backend/`.

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
cross-lane part. **Depends on:** none named. **PR:** none yet.

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
**Assigned:** `uplevel-backend`, test-first, one PR. **Depends on:** none named. **PR:** none yet.

- [ ] **S1:** with `API_KEY_ENABLED=true` and `EXPOSE_LAN=false`, the 9 routes guarded by the legacy
      `verify_api_key` copies (`backend/api/routes/dlq.py`, `backend/api/routes/system.py`;
      including `POST /api/dlq/requeue/{q}`, `POST /api/dlq/requeue-all/{q}`, `DELETE /api/dlq/{q}`
      and `PATCH /api/system/config…`) accept a key that holds only the `monitoring` scope. The
      legacy copies refuse scoped entries, so scope has one rule.
- [ ] **S4:** the `monitoring` scope admits `GET /api/events`, which serves sparse fieldsets
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
backend. **Depends on:** queues behind #7003 (merged). **PR:** #7027 (open).

- [ ] The unit tests that land in the 1.5–4.0 s WARN band every run (about 10 ids, mostly
      100-example property tests) are made cheaper in the tests themselves: draw counts, fixtures,
      fake clocks. Neither timing gate is edited (rules.md §Test timing gates).

**Done when:** the slowest unit test in each of 5 consecutive green `main` runs is at or under
3.0 s, giving at least 1 s of headroom under the 4.0 s line (ruling 122).

### [r129] Backups and the batch audit load the deferred columns

**Flags:** none. **Assigned:** backend, as a bug fix outside Phase 4's priority order. **Depends
on:** queues behind `[r122]`. **PR:** #7031 (open).

F-100, F-106 and F-108 are ruled **complete**. `Event.reasoning` and `Event.llm_prompt` are
`deferred()` (`backend/models/event.py:72-74`). `_export_table`
(`backend/services/backup_service.py:336`) and the batch audit
(`backend/api/routes/ai_audit.py:445`) read them inside an `AsyncSession`, which raises
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
**Depends on:** queues after `[r129]`; frontend's `[r130f]` runs in parallel. **PR:** none yet.

- [ ] **F-187, F-190, F-191.** `GET /api/v1/settings` returns 500: `settings_api.py:115` feeds
      `fast_path_confidence_threshold` (default `2.0`, the deliberate "disabled" value,
      `config.py:1966`) into `DetectionSettings.fast_path_threshold`, whose schema caps it at
      `le=1.0` (`schemas/settings_api.py:49`). Make the schema and the config agree, and keep the
      disabled sentinel expressible.
- [ ] **F-089.** Give the `job_type` query parameter `alias="type"` (`routes/jobs.py:296-299`),
      matching `job_status`.
- [ ] **F-034, link half.** `summary_detail_service.py:147` builds `/events/{id}`, a route the app
      does not have; it builds the app's working target, `/timeline?event=…`. If frontend adds an
      `/events/:id` redirect instead, backend leaves this line alone. One side changes, not both.

**Done when:** for each row, its golden spec, already written to pin the broken behaviour, is
flipped to assert the fix and passes. F-190 and F-191 also need ruling 127's writable `runtime.env`
on the CI compose before their save leg can go green; until then they flip on the read leg only
(ruling 130).
