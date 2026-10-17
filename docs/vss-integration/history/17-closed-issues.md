# 17 (History) — Closed Issue Blocks

> **Historical companion to [`../17-action-plan.md`](../17-action-plan.md) (`OD-34`, ruling 89).** This file holds the full blocks (original evidence, update notes, and closure notes) for the 13 closed (`done`) issues moved out of `17-action-plan.md`. Each moved issue retains its heading, metadata line, and a one-line dated pointer at its original position in `17-action-plan.md`.

#### ISS-001 — Wire the notification decision into the VLM event path: nothing calls `should_notify`

`P0` (verifiers read `P1`) · `gap` · actor `agent-now` · status `done` · closed 2026-10-06 (see the closure note)

- **Evidence**
  - `backend/services/notification_filter.py:35` `should_notify` (`:75` is the `rejected` early
    return) [V]
  - Non-test grep of `backend/` for `should_notify`, `NotificationFilterService`, `evaluate_event`,
    `create_alerts_for_event` and `deliver_alert` finds definitions and docstrings only:
    `backend/services/alert_engine.py:166`, `backend/services/alert_engine.py:1039`,
    `backend/services/notification.py:633`. The one other hit, `backend/api/routes/ai_audit.py:193`,
    is an unrelated route [V]
  - `backend/services/vlm_analyzer.py:638` `_set_idempotency` then
    `backend/services/vlm_analyzer.py:643` `_broadcast`; nothing follows it. Its only
    `notif`/`alert` hits are comments (`:16`, `:285`, `:525`) [V]
  - `AlertRuleEngine` is built in production only by the FastAPI dependency
    `backend/api/dependencies.py:918` and the factory `backend/services/alert_engine.py:1172`
    `get_alert_engine`, whose only other non-test mentions are the import and export in
    `backend/services/__init__.py` (`:9`, `:532`);
    `NotificationService` is reached only from the test/send routes
    (`backend/api/routes/notification.py:224` sends to a mock alert) [V]
  - Frontend: `showSecurityAlert` is called only inside
    `frontend/src/hooks/useIntegratedNotifications.ts:247`; `useAlertWebSocket` has no non-test
    importer beyond the re-export `frontend/src/hooks/index.ts:269` [V]
  - The design promises the opposite:
    `docs/superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md:345` 'The owner is never
    left blind'; the ledger close pointer says 'the notification link is unwired'
    (`docs/plans/2026-09-23-vss-gaming-gpu-ledger.md:415`) [V]
  - Stale pointers to fix with it: `docs/superpowers/plans/2026-09-25-vss-phase1-vlm-path.md:67`
    calls `backend/services/alert_engine.py:451` the live notification decision;
    `backend/api/schemas/websocket.py:235` names the deleted `backend/services/nemotron_analyzer.py`
    [V]
- **Why it matters.** Every safety net in spec section 6 (rejected never notifies, uncertain/NULL
  fall back to the detector rule, an outage must not leave the owner blind) is implemented and
  unit-tested but unreachable. At `5c605e1d` a confirmed 'person at the back door at 3am' verdict is
  stored and pushed to an open dashboard tab only; a real incident during an ai-vlm outage produces
  a silent NULL-score row and no alert. This is the sole open M1 item; spec S5 requires failures to
  reach 'the dashboard and the notification path'. The plan words the gate as landed 'in the LIVE
  decision (alert_engine)' (`docs/superpowers/plans/2026-09-25-vss-phase1-vlm-path.md:89`) and
  checks off a gate where NULL-score events 'ride the live pipe ... notification' (`:123`), and
  `backend/tests/unit/services/test_alert_engine.py:3104` pins the `rejected` rule, yet no
  production code calls the functions those rules live in; the ledger's 1.3 row does record the
  gap ('`should_notify`/`evaluate_event` have ZERO production callers today',
  `docs/plans/2026-09-23-vss-gaming-gpu-ledger.md:117`, 'Live-ness caveat') [V: read].
- **World-class gap.** A single post-commit notify stage owned by the analyzer (or a queue consumer
  of the committed event): resolve prefs/camera setting/quiet hours, apply verdict rules, evaluate
  alert rules, create Alert rows, deliver per channel with persisted delivery receipts and a
  dead-letter metric, and fan out to WS so every channel sees the same decision; hit rate and
  dropped-alert count measured end to end from a synthetic incident replay through to a delivered
  message.
- **Acceptance.** Integration test through VlmAnalyzer.`analyze_batch` with FakeProvider/stubbed
  VLM: (a) confirmed score-75/80 event on a camera with default prefs -> exactly one `deliver_alert`
  call (or recorded delivery); (b) rejected -> none; (c) VlmUnavailableError/`verification_failed` +
  person@>=threshold -> one (operator-visible alert). An AST reachability guard fails if
  `should_notify`, `evaluate_event`, `create_alerts_for_event` or `deliver_alert` has zero non-test
  callers; frontend consumer test with a real WS payload asserts an alert hook is mounted. Plan line
  67 and the `websocket.py` docstring are corrected; `docs/vss-integration` notification section
  states which components are wired; ledger item 41 pointer / M1 closed with the commit.
- **Depends on.** Nothing — the scope question this line waited on was ruled the same day (OD-1
  follow-up, Intake log entry 2026-10-05: the smallest slice).
- **Tracked as.** M1 is open on this link (ledger close pointer, above). No roadmap R-row.
- **Update 2026-10-03 (after `ab3bd002`) [V unless marked].** The evidence bullets above describe
  `5c605e1d`. `ab3bd002` gives the analyzer a call to `should_notify`: `decide_notification`
  (`backend/services/notification_filter.py:201` at that commit) loads the global preferences, the
  camera setting and the quiet hours and asks `should_notify`, and `VlmAnalyzer._notify_decision`
  runs it in its own short session after the event commits (production only; replay computes
  nothing). The answer is broadcast as `WebSocketEventData.notify`, with the key left out when it is
  `None`, so absence means 'no decision' and not `False`. A failed settings read falls back to the
  shipped default preferences. The docstring pointer at `backend/api/schemas/websocket.py:235` no
  longer names `nemotron_analyzer.py` [V: read]. Still open: nothing consumes `notify` (I found no
  frontend reader outside the generated types), `evaluate_event`, `create_alerts_for_event` and
  `deliver_alert` still have no production caller, and the commit adds neither the AST reachability
  guard nor the frontend consumer test of the acceptance [V: grep; `git show --stat ab3bd002`]. The
  commit message says no integration test against a live database ran, the sandbox having none [A].
  So clause (a) of the acceptance, one `deliver_alert` call for a confirmed event, is unmet and the
  P0 stays `open`. The commit message records an owner decision of 2026-10-03, 'analyzer-only
  first', with alert rules and delivery channels as follow-ups [A: no ruling is recorded in
  `docs/plans`]; that is option (a) of OD-1.
- **Update 2026-10-05 (the OD-1 follow-up ruling) [O: Intake log entry 2026-10-05].** The
  follow-up scope is now ruled durably: **the smallest slice** — an in-app consumer reads the
  decision (the agent picks the minimal mechanism the code supports: persisting the decision
  and/or letting the event/alert surface consume `notify`); `evaluate_event` and `deliver_alert`
  stay parked (not deleted, not wired); OD-16's push channel is out of the slice; and **ISS-018
  rides inside it** — its bands must agree with the stored ones before or with the consumer, since
  the consumer makes today's dormant divergence live. This turns the P0 from a blocked question
  into well-defined agent work: the acceptance above stands, and its closure condition is a test
  that an event decided `notify=true` reaches a surface a human sees, run against a live database.
- **Update 2026-10-05 (the slice's mechanism chosen; the acceptance-vs-ruling conflict raised as
  OD-31) [A survey at HEAD; the closure test's live-DB shape [V run here]].** The delegated
  mechanism pick is on the record in the Intake log entry "the notification slice planned by
  evidence": persist the decision in **a new table** (the `EventVerification` precedent — the
  migration note there states `create_all` creates new tables and never ALTERs, so the
  alternatives that need a new `events` column are out on repo law), expose it on the events REST
  surface mirroring the shipped `verification` field's `exclude_if` absence semantics (absent
  means "no decision", never `False`), and render it in the ActivityFeed/EventTimeline mapping —
  which `AlertsPage` also rides (`useAlertsQuery` reads `GET /api/events`), so one change covers
  both surfaces. Eliminated by measured facts, so nobody re-litigates: a frontend-only WS badge
  (no reader of `notify` exists outside generated types, `backend/api/routes/events.py` carries
  none, and a live-only badge fails the [O] closure test and vanishes on reload); read-time
  recompute (re-arms the ISS-018 divergence on the display path; a post-hoc preference edit
  rewrites an event's history); emitting via `alert.created` (re-touches machinery the [O] ruling
  parks). Dead neighbors needing nothing: `useAlertWebSocket` (unmounted), the notification-history
  stub, `PgNotifyListener` (dead code — never started in `main.py`). Two things this block cannot
  self-resolve: the AST-guard conflict (the acceptance says it stands while the ruling parks
  three of its four functions — raised as **OD-31**, recommended narrow reading there), and
  acceptance clause (c), the NULL-score alert, which stays gated on ISS-019/OD-22 — the slice's
  tests map (a) to the persisted-decision closure and (b) to the rejected rule, not to a
  `deliver_alert` call count. The live-DB criterion is measured achievable here: the conftest
  Postgres tier ran ISS-103's pins green in ~5s on `-n0 --timeout=30`.
- **Update 2026-10-05 (OD-31 ruled) [O: Intake log entry 2026-10-05].** The owner ruled "check the
  one live function": the guard narrows to `should_notify`, "(or recorded delivery)" is the
  persisted decision in the new table, closure is the live-DB `notify=true`-reaches-a-surface test,
  and the parked functions stay unguarded. The reading the update above describes as the slice's
  working assumption is now the owner's construction of the acceptance text — the text itself
  stands unamended. Clause (c)'s gate on ISS-019/OD-22 is unchanged. **No open owner question
  remains inside this block**; the remaining work is the implementation itself (agent-now).
- **Closed 2026-10-06 (the slice shipped on PR #6811, commits `db83f1f8` `0f510782` `d483cc82`
  `1fa4e35f` `b0952912`; merge is the owner's action).** What ran and what it showed [V: every
  number below was executed in this session at these commits]: **the OD-31 closure criterion is
  met** — `backend/tests/integration/test_notify_decision_wiring.py` runs the analyzer's own
  `analyze_batch` with the scripted fake VLM against the live test Postgres and asserts the
  _decision reaches a surface a human sees_: arm (a) confirmed/score 75/default prefs persists
  `EventNotifyDecision(notify=true)` **and** both REST surfaces (`GET /api/events`,
  `GET /api/events/{id}`) carry `"notify": true`; arm (b) rejected persists `notify=false` and the
  false rides the payload PRESENT (a recorded quiet is a real answer); arm (c) a decision-less row
  yields the key ABSENT, never null; arm (d) replay commits the event but no decision and the key
  stays absent — pinning the absence half against the wrong fix of re-deriving at read time. 5
  passed twice (`-n0 --timeout=300`, ~6 s/run, testcontainers Postgres). **The narrowed guard
  ships**: `backend/tests/unit/services/test_notify_reachability_guard.py` AST-scans `backend/` for
  `Load`-context uses and pins the live chain `should_notify` ← `decide_notification` ←
  `VlmAnalyzer._notify_decision`, asserting NOTHING about the parked trio per the ruling; 12 tests,
  and the two files together run 1157 passed twice (the census parametrizes 0..100 across five
  copies). **The consumer that makes the decision visible**: the decision renders on every event
  surface through the shared `NotifyBadge` (true → "Notifies", false → "Not notifying", absence →
  renders nothing — absence is never a third state), fed by the events REST field that mirrors
  `verification`'s `exclude_if` contract, on ActivityFeed, EventTimeline/EventCard/MobileEventCard,
  EventListView, EventDetailModal and the AlertsPage that rides the same endpoint; the WS twin type
  carries the field too. **The acceptance's named stale pointers are corrected**: plan line 67
  carries a dated supersession (its `should_notify`-has-no-caller claim is now false and its
  `backend/services/alert_engine.py:451` pointer names a path OD-1's follow-up parks), and the
  `websocket.py` docstring names no deleted module. **What was measured rather than assumed**: with no `fields`
  param `filter_fields` is a passthrough (`filter_fields(ev, None) is ev` → True), so the list
  path's absence comes from the `EventListResponse.items` revalidation through `EventResponse` —
  both keys vanish for None and both survive as false, measured on the live model. Gates: backend
  unit tier and the schema snapshots (the notify field is the only snapshot delta, reviewed line by
  line), frontend tsc/eslint/prettier green with the badge's 6 tests plus the surface tests; ruff
  check and format rc=0 on every touched file. **The acceptance's clause (a) as literally worded —
  "exactly one `deliver_alert` call" — is not met and was NOT the criterion the owner ruled**: OD-31
  construed "(or recorded delivery)" as the persisted decision, and delivery stays parked with the
  rules engine by the OD-1 follow-up ruling [O: Intake log 2026-10-05]; clause (c) stays gated on
  ISS-019/OD-22, unchanged. The frontend consumer half was satisfied by the rendered-badge tests on
  the surfaces that read the field, not by mounting `useAlertWebSocket` — that hook stays unmounted
  exactly as the mechanism note recorded, since the REST surface is what survives reload.

#### ISS-018 — `notification_filter` maps score to level with 40/60/80 bands; shipped bands are 30/60/85

`P1` (verifiers read `P2`) · `bug` · actor `agent-now` · status `done` · closed 2026-10-06 (see the closure note)

- **Evidence**
  - `backend/services/notification_filter.py:175` `_risk_score_to_level` hard-codes 80/60/40 (`:184`
    `score >= 80`); `backend/models/notification_preferences.py:34` documents CRITICAL 80-100, HIGH
    60-79, MEDIUM 40-59 [V]
  - The shipped bands are 29/59/84: `backend/core/config.py:2426` `severity_low_max` (default 29,
    `:2429` 59, `:2435` 84), `backend/evaluation/levels.py:22`; the analyzer stores `risk_level`
    through `SeverityService` (`backend/services/severity.py:137` `risk_score_to_severity`) [V]
  - `backend/services/event_broadcaster.py:332` `requires_ack` tests a raw `risk_score >= 80`, a
    third spelling; this one is live at `5c605e1d`, but over-acks scores 80-84 rather than missing
    an alert [V]
  - A fourth live spelling: `backend/services/summary_parser.py:322` `_severity_from_score`
    (80/60/40), reached from `backend/api/routes/summaries.py:131` via `parse_summary_content` [V]
  - Scores 30-39 are 'medium' in the stored level and the UI but 'low' to the filter; 80-84 are
    'high' in the UI but 'critical' to the filter [C from the two band tables above]
- **Why it matters.** Once the notify stage is wired (ISS-001), a user whose `risk_filters` include
  `medium` is not notified for a score-35 event the UI calls medium, and 80-84 events are treated as
  critical. The filter half is dead code at `5c605e1d`, so the only live effect is
  over-acknowledgement. The `levels.py` docstring describes the three-spelling risk as preventive,
  not as an incident that already happened.
- **World-class gap.** One severity function (SeverityService) consumed by filter, ack rule, rules
  engine and UI, with a contract test that pins every consumer to the same edges for any configured
  `SEVERITY_*` values.
- **Acceptance.** A parametrised test over scores 0..100 asserts that `should_notify`'s level,
  `requires_ack`'s critical test, `_severity_from_score` and
  `SeverityService.risk_score_to_severity` agree under the defaults and under a non-default
  `SEVERITY_*` configuration; `_risk_score_to_level` is removed or delegates to `SeverityService`.
  The other hard-coded copies the verifiers found (`backend/api/routes/analytics.py`,
  `backend/models/event.py`, `backend/evaluation/harness.py`) are listed in the test or fixed with
  it.
- **Depends on.** Best done with or before ISS-001 (OD-1) — and now ruled into that slice: the
  OD-1 follow-up ruling of 2026-10-05 (Intake log) puts this fix inside the smallest-slice work
  the consumer needs, and the same day's OD-30 ruling released its only sequencing block.
- **Tracked as.** None found; only the wiring is ledgered.
- **Severity note.** Verifiers read P2: the filter is unreachable at `5c605e1d`, and a non-default
  `SEVERITY_*` is hypothetical (no compose or env file overrides it).
- **Update 2026-10-03 (after `d8482861`) [V: `git show --stat d8482861`].** One of the 'other
  hard-coded copies' named in the acceptance, `backend/evaluation/harness.py`, no longer exists:
  the retired Nemotron harness was deleted in `d8482861`, so drop it from the list the test must
  cover. The other named copies (`backend/api/routes/analytics.py`, `backend/models/event.py`) are
  not touched by that commit, and the issue stays `open`.
- **Update 2026-10-05 (the OD-29 verification pass) [A measured here, ISS-103's evidence].**
  Sequencing, do not invert: ISS-018 must **not** merge before OD-30 rules on stored zeros. The
  band collapse moves `_risk_score_to_level`'s edges from 40/60/80 to the bands of record 29/59/84,
  which drops a pre-merge camera row's effective floor (that row stores `risk_threshold` 0, and
  OD-29's saves-wins honours it) from 40 to 30 — measured at arm B at 34/209 = 16.3% benign alerts,
  up from the 10.0% the same row produces today and the 6.7% it produced under the pre-merge arm A
  text. The band fix stays right; it just cannot land first, because the 40 edge is currently the
  only thing between a stored-0 install and the medium band's full traffic.
- **Update 2026-10-05 (OD-30 ruled, hours later) [O: Intake log entry 2026-10-05]. SUPERSEDES the
  sequencing warning above.** The owner ruled OD-30 (c) and stated no real install has saved camera
  settings — this project is building its first installation — so no stored-0 row exists or can be
  produced by current code (the get-or-create route now writes the 60 default). The warning's
  precondition is empty: **ISS-018 is NOT blocked**, it may land whenever its own acceptance is
  met. The warning text above stays as the record of what was measured when it was written, and it
  keeps force only against a hypothetical pre-`c0191f4d` database, which the owner has stated does
  not exist.
- **Update 2026-10-05 (the full band census for the fix; the ack-boundary conflict raised as
  OD-32) [V survey at HEAD].** The acceptance names two spellings; the code has six, and the fix
  has to know which are in scope. Measured today: the filter's
  `NotificationFilterService._risk_score_to_level` (40/60/80), `SeverityService.risk_score_to_severity`
  (the bands of record 29/59/84), `summary_parser._severity_from_score` (80/60/40),
  `event_broadcaster.requires_ack` (raw `risk_score >= 80`), and — missing from every prior
  inventory — `NotificationSettings.tsx`'s `RISK_LEVEL_RANGES`, which is the 40/60/80 ladder
  _rendered to users_ on the settings screen and must move with the bands or the UI lies about
  what a saved threshold means. Exempt on the record: the frontend visual ladders in
  `severityColors.ts`, whose docstring says the critical-at-80 early-warn is "deliberately NOT"
  the backend bands and tells future readers not to "unify" them. Two constraints the survey
  pins: `test_p04_verification_field.py` AST-pins the _existence_ of `_risk_score_to_level`, so
  the fix must **delegate, not delete** — a removal fails a shipped test before ISS-018 can pass
  its own; and the zero-consumers path (`PUT /api/system/severity`, no caller reads the value
  back) is noted as an observation, not slice work. One clause the agent cannot settle: aligning
  `requires_ack` to the bands would move its boundary off the raw 80, but
  `test_message_buffer.py::test_high_risk_score_requires_ack` pins score 80 / level `high` →
  **ack required** — under bands of record, 80 is `high`, and a "make ack follow the band"
  reading inverts that user-visible behavior instead of fixing it. Raised as **OD-32** with the
  recommendation to keep the raw 80 and treat ack as its own critical test. The bands of record
  sit in no shipped test's expectations at the boundaries ISS-103's pins touch (score 45 is
  `medium` under both spellings), so whichever way OD-32 lands, the two blocks stay order-safe.
- **Update 2026-10-05 (OD-32 ruled) [O: Intake log entry 2026-10-05].** The owner ruled "keep the
  popup": `requires_ack`'s raw `risk_score >= 80` edge stands as a documented deliberate
  early-ack, carved out of the agreement test by name, and
  `test_message_buffer.py::test_high_risk_score_requires_ack` is not touched — so scores 80-84
  keep prompting, and the agreement test the acceptance demands ships with that one named,
  owner-blessed exception. **No open owner question remains inside this block.**
- **Closed 2026-10-06 (the delegation shipped on PR #6811 in `ffb2d17d`; the acceptance test in
  `1fa4e35f`; merge is the owner's action).** What ran and what it showed [V: executed at these
  commits]: `backend/tests/unit/test_severity_band_agreement.py` is the contract test the
  acceptance asks for — a full **0..100 census** (deliberately a census, not a boundary sample:
  three hard-coded ladders died to produce those boundaries) over the live copies —
  `NotificationFilterService._risk_score_to_level`, `SeverityService.risk_score_to_severity`,
  `summary_parser._severity_from_score`, `Event.computed_risk_level` — each scored against an
  independent oracle derived from the settings values themselves, under the shipped defaults AND
  under a non-default `SEVERITY_*` configuration, so five copies agreeing with each other is not
  enough to pass. The acceptance's named `analytics._get_risk_level` is LISTED in the test exactly
  as the acceptance allows ("listed in the test or fixed with it"): it is a static hard-coded copy
  of the default bands in a route module that the slice's rulings do not reach, pinned as-is in
  `TestAnalyticsStaticLadder` with a delete-don't-edit-when-you-delegate note. `requires_ack` is
  carved out BY NAME (`test_od32_exception_requires_ack_acks_at_raw_80`), the OD-32 ruling's one
  owner-blessed exception; `test_message_buffer.py::test_high_risk_score_requires_ack` was not
  touched. `_risk_score_to_level` DELEGATES (not deletes — the census's own docstring records that
  `test_p04_verification_field.py` AST-pins the seam's existence, which is why delegation was the
  only landing shape); `summary_parser._severity_from_score` likewise, with its `None` passthrough
  intact. The settings-screen ladder `RISK_LEVEL_RANGES` moved to 29/59/84 with the bands. The
  exemptions the 2026-10-05 census update recorded (`severityColors.ts`, deleted `harness.py`) are
  restated in the test file so nobody re-adds them. 1145 tests in this file; the pair with the
  guard ran 1157 passed twice (`-n0 --timeout=120`, pytest-randomly rerolled); ruff check and
  format rc=0. The shipped boundary pins stay where they were (`test_notification_filter.py`
  restates the edges at the filter seam at 29/59/84 with ISS-018 comments).

#### ISS-103 — OD-29's floor 60 never reaches a camera row written before the merge: the row stores 0, saves-wins keeps it, and the level map alerts at ≥ 40

`P1` · `gap` · actor `agent-now` · status `done` · added 2026-10-05 (the OD-29 verification pass; actor moved from `owner-decision` the same day on the OD-30 ruling — see this block's ruling update; closed the same day on the pinning tests — see the closure note)

- **Evidence**
  - The get-or-create branch of `backend/api/routes/notification_preferences.py`
    (`update_camera_setting`, the `@router.put` whose path carries the camera id) writes
    `risk_threshold=DEFAULT_CAMERA_RISK_THRESHOLD` when it creates the row [V]. At the parent of
    `c0191f4d` that same branch wrote `risk_threshold=0` explicitly
    (`git show d8482861:backend/api/routes/notification_preferences.py`, the same branch) [V]
  - The schema allows 0 as a saved value:
    `backend/api/schemas/notification_preferences.py`
    `CameraNotificationSettingUpdate.risk_threshold` is `Field(None, ge=0, le=100)`, and the table's
    `CheckConstraint` is `risk_threshold >= 0 AND risk_threshold <= 100`
    (`backend/models/notification_preferences.py`, `CameraNotificationSetting.__table_args__`) [V]
  - The repo is `create_all`-only, so no upgrade migrates an existing row to 60:
    `backend/core/database.py` runs `ModelsBase.metadata.create_all` (Alembic removed in #4465, and
    `create_all` "creates NEW tables on an existing database and never ALTERS existing ones", per
    the migration note in `backend/models/event_verification.py`) [V]
  - Saves win, by ruling and by code: `backend/services/notification_filter.py`
    `_scored_notify` takes `camera_setting.risk_threshold` when a row exists and only falls back to
    `DEFAULT_CAMERA_RISK_THRESHOLD` when there is no row [V: the OD-29 comment above that branch
    states the rule]
  - With the stored 0, the gate that actually fires is the level map, not the floor:
    `_scored_notify` first maps the score through `_risk_score_to_level` (80/60/40) and tests it
    against `global_prefs.risk_filters`, whose model default is `[critical, high, medium]`
    (`backend/models/notification_preferences.py`, the `risk_filters` default in
    `NotificationPreferences.__init__`), so any score ≥ 40 passes the level test and then passes the
    threshold test too (`risk_score < 0` is never true) [C from the two reads above: effective gate
    = `score >= 40`]
  - The cited ship pair does not cover that population: re-running the frozen stage-3.5 driver
    (`stage35/operating_point_ship.py` under
    `/agents/agent-vss5/gpu/out/experiments/2026-10-04-stage1/`, read-only, over
    `/agents/agent-vss5/gpu/out/sbroot/eval/tierb-v0/eval.sqlite`, runs
    `4a94b2562919419a975bed4972646740` and `696c71687e264577b4deb6bd5c99af26`) reproduces all six
    shipped rows to the digit, and the one row the record does not carry — arm B at the effective
    floor 40 a stored-0 row enforces — reads **benign alerts 21/209 = 10.0% [6.7-14.9], incident
    hits 104/241 = 43.2% [37.1-49.5]** [A measured here at `eea4cfd5`; Wilson per F14; same
    store, same frozen gate semantics as the cited [V] rows]. The pass is itself scripted and its
    output left on disk: `stage35/verify_stored_zero_2026-10-05.py` (self-checking — it repeats
    the six ship rows first, then adds the seventh, the McNemar pairs and the refutation census)
    and `stage35/results-verify-stored-zero-2026-10-05.txt`, same off-repo kit
  - Paired, exact McNemar over the same 209 benign items: upgraded install A@40 → B@40 is 14 → 21
    (13 newly alerting, 6 stopped, p = 0.167); the cited fresh-install move A@40 → B@60 is itself
    14 → 9 (9 stopped, 4 newly, p = 0.267); the hits half is 88 → 104 (30 gained, 14 lost,
    p = 0.0226) and is identical at floors 40 and 60 [A measured here, same store]
  - Why the hits are floor-indifferent, measured rather than assumed: of the 18 incidents whose
    declared `floor_level` is 30, **none** scores in [40, 60) in either arm, so raising the floor
    from 40 to 60 cannot change a hit; meanwhile the rubric text moves _benign_ scores INTO that
    band — 4 arm-A benigns score in [40, 60) against 12 arm-B ones — which is the mechanism of the
    false-positive move [A measured here, same store]
  - The population is unmeasured and is owner-only knowledge: only that `@router.put` creates a row
    — the two GETs do not (`backend/api/routes/notification_preferences.py`, `get_camera_settings`
    and `get_camera_setting` have no `db.add`) — so a camera is affected only if someone ever saved
    a setting; no deployment inventory exists in the repo [V: read of all seven routes]
  - The UI states the stored number honestly, so the gap is invisible from the settings page:
    `frontend/src/components/settings/NotificationSettings.tsx` renders
    `setting?.risk_threshold ?? DEFAULT_CAMERA_RISK_THRESHOLD`, and in JavaScript `??` does not fall
    back on a stored 0, so a stored-0 camera displays 0 while the backend gates at 40 [V]
  - This defect is not registered anywhere: `grep -in "stored.0\|risk_threshold = 0\|backfill"
17-action-plan.md` returned zero hits before this block [V: run in-session]
- **Why it matters.** OD-29 ships an operating point whose false-positive half (6.7% → 4.3%) is a
  fresh-install reading, and on an upgraded install the same shipped code moves benign alerts
  6.7% → 10.0% — the wrong way. Stated exactly, because the statistics matter: the hit gain is
  paired-significant and population-independent, the FP move is NOT separated in either population
  (p = 0.167 upgraded, p = 0.267 fresh), so the honest claim is _the FP half of the ship claim flips
  sign and is underpowered in both populations_, never 'a proven regression'. The trigger is the
  ordinary upgrade path, and the affected population is exactly "anyone who ever saved a camera
  setting", which no repo artifact can count.
- **World-class gap.** One owner-visible floor with one mechanism: a stored value that means
  "unset" is distinguishable from a value a human chose (a nullable column, or an explicit
  `use_default` flag), the effective floor is one function the UI, the filter and the report all
  read, and an upgrade either migrates rows or is documented as not applying to them — with a
  migration test that builds a pre-merge database, upgrades it, and asserts the effective gate.
- **Acceptance.** As ruled (c), the record half is already met — README §3/§4 carry the
  fresh-install population qualifier (added with the finding, 2026-10-05) and the dated ledger row
  is drafted for the owner's merge. What remains is one red-first integration test: (1) insert a
  row with the pre-merge shape (`risk_threshold=0`, `enabled=true`) into a live database, (2) call
  `should_notify` at a score of 45 with default `risk_filters`, (3) assert alerting — under (c) a
  stored 0 stays a saved value that wins, which is the documented behavior being pinned — plus a
  second test that a DELIBERATELY saved 0 behaves identically (the two meanings stay
  indistinguishable by design; that is what (c) accepts).
- **Depends on.** Nothing now — OD-30 was raised by this issue and ruled (c) the same day [O:
  Intake log entry 2026-10-05]. The sequencing notes here are as measured at filing and one of
  them is released: the warning that **ISS-018 must NOT precede the ruling** (the band collapse
  moves a stored-0 row's effective floor 40 → 30, measured 16.3%) had an empty precondition once
  the owner stated no install has stored camera settings — see ISS-018's superseding note; the
  divergence wiring M1's consumer (ISS-001) would have made user-visible is likewise empty.
  OD-22's quiet-hours/cooldown remainder was untouched by the ruling; this issue does not touch
  suppression.
- **Tracked as.** None found — the grep above; the OD-29 rows in 17 §4, README §3/§4 and the
  `DEFAULT_CAMERA_RISK_THRESHOLD` comment all carry the 4.3% pair without a population qualifier
  (that is what this issue corrects, by dated note, not by rewrite).
- **Severity note.** P1 by the definition — "wrong … behaviour on the shipped path that changes …
  an alert" — with the live effect gated on (a) a stored-0 row existing at all and (b) ISS-001's
  consumer half, which is unbuilt, so nothing pages a user on it yet. A P2 read is defensible for
  the same reason; the filed value is P1 because the upgrade path is the normal path.
  **Update 2026-10-05 (the same day's OD-30 ruling) [O: Intake log entry 2026-10-05]:** the
  sentence "the upgrade path is the normal path" is dead — the owner stated no install has saved
  camera settings at all, so gate (a) is empty and the P2 read is now the better one. The filed
  severity stays P1 — the Dashboard counts by filed severity and the block records what was
  argued at filing — with this note as the re-grade argument. Changing the filed grade is a
  one-line edit at this block's next touch plus a Dashboard recount, not a new decision.
- **Two claims this issue does NOT make, pre-empted here.** (1) Not claimed that the 2048 budget
  raise is unmeasured on the shipped text: arm B never truncated at 1024 (that run has 450 rows, 0
  `verification_failed`, 0 NULL scores, longest raw response 3182 chars — [V: `results` table], so
  no 2048 twin was owed. (2) Not claimed that any [V] ship row is wrong: all six reproduce exactly;
  what was missing is the seventh row, and the population the six describe.
- **Provenance caveat carried from OD-29, not added by this issue.** Runs `4a94b256…`/`696c7168…`
  were collected 2026-10-03 at client `d8482861` with the rubric applied by an off-repo replay shim
  (`experiments/2026-10-03-rubric-logprob/replay_exp.py` replaced the prompt clause on the wire and
  set `logprobs: true` on every call). The recomputation over stored scores is faithful, but no
  committed command reproduces the measured REQUEST byte-for-byte; the OLD→RUBRIC literal
  equivalence is the check that should become a committed test before any re-measure is quoted
  [A: shim read in-session].
- **Update 2026-10-05 (OD-30 ruled (c) the same day it was raised) [O: Intake log entry
  2026-10-05].** The owner ruled **(c) — accept the fresh-install scope, restate, no code** — and
  answered the population question with the fact the register could not see: **no real install has
  saved camera settings; this project is building the first installation, and backwards
  compatibility is explicitly out of scope.** Read forward from the code, that closes the defect
  class rather than accepting it: the get-or-create route creates new rows at the 60 default
  (`notification_preferences.py` route, the `db.add` branch), so a first installation never writes
  the stored 0 — the 10.0% row describes an upgrade of a database that does not exist and cannot
  be produced by any code path in main. What still stands, and what this issue keeps open for:
  (1) the acceptance test — a stored-0 row behaves as documented (alerts at ≥ 40) and a
  deliberately-saved 0 stays legal and wins, pinning the semantic the PUT's `ge=0` keeps
  available; (2) the meaning collision is deferred, not solved — if an install ever does exist
  pre-dating a future change, "stored 0" again carries two meanings and needs a ruling (option (d)
  remains the durable fix). Actor moves to `agent-now`: after the ruling no owner input remains on
  the test.

#### ISS-078 — The assess call samples at temperature 0.1 with no seed: only 278 of 450 items reproduce across identical runs

`P1` · `risk` · actor `owner-decision` · status `done` (closed 2026-10-03 in `9f4e65cd`) · added
2026-10-03

- **Evidence** (as filed at `5c605e1d`; the closure follows the 'Tracked as' line)
  - `backend/services/vlm_client.py:796` sets `"temperature": 0.1` in the assess body (introduced by
    `4bfd6fa4`, 2026-09-27, per `git log -S`); `backend/services/vlm_client.py:805` and `:807` use
    temperature 0.0 only for the section-6 transport retry
    (`docs/superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md:340`); grep for `seed` in
    `vlm_client.py`, `vlm_analyzer.py` and `vlm_verdict.py` finds nothing, and none of them repeats
    or votes over samples [V]
  - Same weights, build and conditions, same server, two full replays of the 450 sets: only 278 of
    450 items (62%) returned an identical verdict and score; 164 (36%) changed score, 123 of them by
    10 points or more (max 95); 52 changed risk level
    (`docs/plans/2026-10-03-vss-vlm-exercise-handoff.md:259`) [V: read in the handoff, measured
    elsewhere]
  - Three readings of the same sets (the committed 2026-09-30 run and the two 2026-10-03 re-runs):
    S2 false alarms 14 / 19 / 18 of 209 (mean 17.0 = 8.1%, sd 2.6) and S3 hits 88 / 87 / 84 of 241
    (mean 86.3 = 35.8%, sd 2.1) [C, n=3, a rough band and not a CI]
    (`docs/plans/2026-10-03-vss-vlm-exercise-handoff.md:254`); the F14 label flipped MARGINAL to
    FAIL between runs (`docs/plans/2026-10-03-vss-vlm-exercise-handoff.md:233`) [V: handoff]
  - The 13 core files are unchanged since the baseline commit `ca73f1ef`
    (`docs/plans/2026-10-03-vss-vlm-exercise-handoff.md:224`), so the variation is sampling, not a
    regression [V: handoff]
  - [?] temperature-0 experiment pending, see intake log. A temperature-0 comparison run is in
    progress; until it lands nothing here says that temperature 0 removes the variation, or what it
    does to S2/S3 accuracy and to refusals
  - Update, appended 2026-10-03 after the bullet above was written: the experiment landed. Two
    temperature-0 replays (`20261003T134900Z-qwen3-vl-8b-T0` and
    `20261003T141303Z-qwen3-vl-8b-T0`) are identical on 450 of 450 items, both S2 18/209 = 8.6%
    and S3 88/241 = 36.5%, with 0 refusals, so the 0.1 temperature adds noise and is not a
    systematic shift (handoff Addendum 4, `docs/plans/2026-10-03-vss-vlm-exercise-handoff.md`
    heading 'Addendum 4') [V: read in the handoff; the runs are an experiment with a transport
    shim, not the shipped path]
- **Why it matters.** A verdict near the medium threshold (score 30) can flip between runs of the
  same event, so a production alert or no-alert decision is not reproducible on a re-run; and every
  S2/S3 number quoted from one replay is one draw from a distribution comparable to S2's gap to its
  bar (sd 2.6 items = 1.2 points against a 1.7-point gap = 3.5 items; the three readings span 5
  items = 2.4 points [C: items / 209]), so F14's pass, marginal or fail label is not stable. The
  noise is a property of the shipped behaviour, not only of the benchmark.
- **World-class gap.** Deterministic or explicitly ensembled verdicts: temperature 0 with a seed, or
  a median or majority over k samples with the latency cost recorded against S4; the sampling
  contract is printed on the conditions line of every report.
- **Acceptance.** After the temperature-0 experiment lands, the owner rules (OD-24) on one of: (a)
  assess at temperature 0 (and seeded) with S2, S3, S4 and S5 re-read at it; (b) a k-sample median
  or majority with the latency cost against S4; (c) keep 0.1 and report every S2/S3 as a mean over
  at least 3 runs with its spread. Whichever is chosen: the sampling contract is on the conditions
  line, a test pins the request body's temperature and seed, and an identical-verdict share between
  repeat runs is reported beside S2/S3.
- **Depends on.** OD-24; ISS-043 (the measurement side); blocks the reading of ISS-008 and ISS-017
  (ISS-016 is off this list: `done` 2026-10-06 on `vlm-pipeline`, so the split its reading needed
  exists).
- **Tracked as.** None. The handoff lists it as a candidate issue
  (`docs/plans/2026-10-03-vss-vlm-exercise-handoff.md:272`).
- **Closed 2026-10-03 in `9f4e65cd`** (`fix(vlm): the assess call samples greedily`). What was
  decided, changed and shown:
  - Ruling [O]: the owner answered 'move the shipped assess call from temperature 0.1 to 0 as a
    small code change on this branch' (handoff Addendum 5, item 3); that is option (a) of the
    acceptance, recorded under OD-24.
  - Code [V: `git show 9f4e65cd`]: `_ASSESS_TEMPERATURE = 0.0` in `backend/services/vlm_client.py`
    is the `temperature` of the assess body (it was `0.1`); the section-6 transport retry stays
    explicit at 0 and is now a plain re-send, and the comments that said 'only the temperature
    changes' on retry were corrected.
  - Test [V: I ran `uv run pytest backend/tests/unit/services/test_vlm_client.py -k
"greedily or retries_once_at_temperature_zero"`: 2 passed]: `test_assess_samples_greedily` (new)
    pins the constant, the wire value and the absence of `top_p`, `top_k`, `min_p` and `seed`;
    `test_transport_error_retries_once_at_temperature_zero` now asserts the first attempt is also 0
    (it asserted the opposite). The commit message records red-first (both fail with the constant at
    0.1) and `test_vlm_client.py` 70 passed, 474 passed with `test_vlm_analyzer.py`,
    `test_vlm_verdict.py` and `backend/tests/contracts/ai_providers` [A: not re-run here].
  - Identical-verdict share: two temperature-0 replays agreed on 450 of 450 items, both S2 18/209 =
    8.6% and S3 88/241 = 36.5% with 0 refusals, against 278 of 450 at 0.1 (handoff Addendum 4;
    commit message) [V: read in the handoff; measured elsewhere, through a transport shim before the
    commit existed].
  - Acceptance clauses not met as worded, and where each goes. 'Seeded': no seed is sent, because
    greedy decoding needs none and the test pins that none is sent. 'S4 re-read at it': not measured
    (the experiment did not time it); temperature is not among the ledger's re-take triggers (model,
    context, image handling, output budget; see ISS-046) and the S4 script is ISS-046. 'Sampling
    contract on the conditions line': the replay code and report print no temperature (a grep of
    `synthbench/run`, `synthbench/score` and `backend/evaluation` for `temperature` finds nothing at
    `d8482861`; at `5c605e1d` and `9f4e65cd` it matched only the `"temperature": 0.1` line in
    `backend/evaluation/harness.py` (the retired harness, deleted by `d8482861`) [V:
    `git grep -n -i temperature <commit> -- synthbench/run synthbench/score backend/evaluation`]),
    so the contract is now the shipped constant and not a printed condition; carried as a note under
    ISS-045. Determinism was shown on two runs, one server and one build; whether it holds across
    hardware, concurrent slots or a build change is unmeasured [?] (note under ISS-043).
  - Dependents: ISS-008, ISS-016 and ISS-017 named this issue as a blocker for the reproducibility
    of any before-and-after reading; that part is lifted. Their own preconditions stand.
  - Anchors: the commit added six lines at line 98 of `backend/services/vlm_client.py` and four
    more near line 807, and seventeen lines at line 289 of
    `backend/tests/unit/services/test_vlm_client.py`, so this document's anchors into those files
    (the `:796`, `:805` and `:807` above among them) are the `5c605e1d` numbers and sit +6, +10 and
    +17 lines away at `9f4e65cd`; the `temperature` line itself is now line 802
    [V: `git diff -U0 5c605e1d 9f4e65cd`].

#### ISS-033 — Multi-frame prompts carry no chronological order or per-frame capture time

`P2` · `gap` · actor `agent-now` · status `done` · closed 2026-10-07 (see the closure note)

- **Evidence**
  - `backend/services/key_frame_selector.py:74` the docstring says picks are 'strongest first'; the
    sort is by `_rank_key` (confidence, recency, id), not capture time [V]
  - `backend/services/vlm_analyzer.py:226` builds `image_paths` in that pick order, and
    `frame_detection_ids` follow it [V]
  - `backend/services/vlm_client.py:522`-`:526` when `camera_timezone` is set (compose threads
    `CAMERA_TIMEZONE`) each row's `detected_at` is dropped from the rendered rows; the only time
    left is the single `Time:` line (`backend/services/vlm_client.py:547`) [V]
  - The `frame: k` tag (`backend/services/vlm_client.py:527`) is the confidence rank, not a time
    rank; no prompt text says the frames are in time order [V]
  - `backend/services/vlm_analyzer.py:153` `timestamp = min(times)` is the earliest time of the
    batch, which can span the 90 s window; `backend/services/vlm_analyzer.py:196` `build_frame_refs`
    uses `detected_at` (arrival) or 0, not the capture time that `backend/services/capture_time.py`
    parses [V]
  - The claim that 'timestamp row cleanup removed the only per-frame time' rests on the in-code
    comment at `backend/services/vlm_client.py:523` only; no commit was traced [A]
- **Why it matters.** With 2-4 attached frames and the recommended timezone setting, the model
  cannot tell approach from departure, whether a person lingered, or how far apart frames are;
  temporal reasoning over frames is the point of attaching more than one. When `camera_timezone` is
  unset, rows carry arrival time, which is also not a per-frame capture time.
- **World-class gap.** Every image is paired with its capture time; the prompt reasons over an
  explicit timeline with elapsed time between frames and motion/dwell summaries rather than
  independent snapshots.
- **Acceptance.** Frames are attached oldest-first (selection stays strength-based, order is by
  capture time); the prompt states 'Frames are in chronological order' and labels each frame with
  its capture time or offset from the first, via `capture_time.py` when available; unknown time
  renders as unknown, never as arrival time; a unit test pins order and text with and without
  `camera_timezone`, regardless of detector confidence. A replay A/B on a multi-frame burst set
  needs ISS-037 first; until then the S5 check is the only regression test.
- **Depends on.** ISS-037 (replay must run the selector and multi-frame items); precondition for
  ISS-005.
- **Tracked as.** None found.
- **Update 2026-10-07 (`iss033-prompt-chronology`, PR pending owner merge).** Implemented.
  `VlmAssessRequest` carries an optional `frame_capture_times` (index-aligned with `image_paths`;
  each entry the frame's own filename parsed by `capture_time.parse_capture_time` — strict, so a
  name that says nothing stays `None` and is never filled from the row's arrival); with a camera
  timezone `build_assess_request` attaches the selector's picks oldest-first (the selection itself
  is untouched: same strength-based picks, only reordered; unknowns attach last in the pick order
  they were selected in) and the prompt states 'Frames are in chronological order' and labels each
  frame through `render_prompt_time` — local wall time with zone when the timezone is set, the
  stored UTC ISO string when it is not (a zone-less wall time would be ambiguous; the time itself
  carries more than an offset would). An absent field (timezone unset, or a store predating this)
  renders the prompt byte-identically, which is the S5 parity guarantee. Order and text are pinned
  regardless of detector confidence in `backend/tests/unit/services/test_vlm_chronology.py` and
  `TestChronologicalFrameLabels` (`backend/tests/unit/services/test_vlm_client.py`); the AI
  contract regenerated (schema + the two `vlm_assess.request` goldens, the `frame_detection_ids`
  path of `7865e340`). The acceptance's replay A/B clause stays gated on ISS-037 (PR #6831).
  Status stays `open` until the owner merges.
- **Closed 2026-10-07 [V]:** Multi-frame batches attach oldest-first with per-frame `frame_capture_times` labels; merged in PR #6833 (`4e379893`).

#### ISS-005 — Key-frame budget collapses to one still per class: add temporal-spread, motion-aware selection

`P1` (verifiers read `P2`) · `gap` · actor `agent-now` · status `done` · closed 2026-10-07 (see the closure note)

- **Evidence**
  - `backend/services/key_frame_selector.py:99-115`: one representative per (camera, class) by
    `_rank_key`, sorted strongest-first, `:109` skips a pair whose file is already shown; no motion,
    novelty or temporal-spread term [V]
  - `backend/services/key_frame_selector.py:80-81` documents that a batch with one detection type
    'yields a single frame' and that 'a second frame of one track tells the verifier nothing'; the
    claim cites no measurement [V]
  - Batches are per camera (`backend/services/batch_aggregator.py:578`), so the 4-slot budget
    (`backend/services/key_frame_selector.py:37` `MAX_KEY_FRAMES`) is capped by distinct classes;
    the window is 90 s (`backend/core/config.py:928` `batch_window_seconds`) [V]
  - The spec says 'the best detection per camera/class plus the most recent'
    (`docs/superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md:116`); the code has no
    dedicated most-recent pick, recency is only the tie-break at
    `backend/services/key_frame_selector.py:70` [V]
  - `backend/core/config.py:2248` `video_frame_interval_seconds` and `backend/core/config.py:2598`
    `video_max_frames` are uniform sampling settings for the detector, not a VLM recall design [V]
- **Why it matters.** Behaviours that need temporal context (approach, loitering, grab-and-run,
  tampering, entry, a prop that appears later) are judged from a single peak-confidence frame, and a
  one-class batch yields exactly one still by design. How many of the four slots production batches
  actually use has not been measured [?], and the effect on S3 cannot be measured until replay runs
  the selector (ISS-037).
- **World-class gap.** Evidence selection is diversity- and motion-aware: adaptive sampling driven
  by motion energy and detector novelty, first/peak/last coverage of every track, an entry/exit
  pair, novelty vs already shown frames; evaluated against a labelled multi-frame corpus rather than
  asserted by docstring.
- **Acceptance.** For a (camera, class) pair that spans more than a configured number of seconds,
  the selector returns the strongest plus the temporally farthest frame(s) when available, in
  chronological order, with capture time exposed to the prompt (see ISS-033); a pair whose
  representative file collides falls back to its next-best distinct file; a property test pins
  determinism and the 4-frame budget. The A/B needs a replay arm that runs the selector, which
  `backend/evaluation/vlm_replay.py` does not at `5c605e1d` (ISS-037), so this issue cannot show an
  S3 delta until ISS-037 lands.
- **Depends on.** ISS-037 (replay must exercise the selector to measure any change); ISS-033
  (capture time).
- **Tracked as.** None found.
- **Severity note.** Verifiers read P2: a documented design choice and an enhancement, with the harm
  unmeasured. The video-sampling clause is a different problem (the VLM path refuses video batches,
  ISS-002).
- **Update 2026-10-07 (`iss005-temporal-spread`, PR pending owner merge).** Implemented.
  `select_key_frames` takes an optional `spread_seconds`: a (camera, class) pair spanning more
  than that claims SPARE slots — what the other pairs left unused, never one another's — for its
  temporally farthest DISTINCT stills, round-robin across spanning pairs so breadth (approach +
  departure) beats depth (three midpoints). Unset is the shipped selector exactly, byte-for-byte —
  the A/B baseline. The span is measured on ONE clock per pair: `FrameRef.capture_timestamp` (the
  frame's own filename, strict-parsed by the same `capture_time.parse_capture_time` ISS-033 chose
  — never the row's arrival) when every member carries one, the uniform arrival clock when none
  does; a pair mixing the two never spreads, because two clocks cannot bound a span. The
  acceptance's file-collision clause needs no special path: it falls out of the shipped
  one-still-one-slot rule — a companion sharing the peak's JPEG never competes, and its slot goes
  to the next-farthest distinct still. Selection priority stays strength-first (representatives
  always place before companions; a property test pins the shipped pick set can only GAIN frames),
  and the acceptance's 'chronological order' is delivered where ISS-033 put it for all frames:
  `build_assess_request` attaches the picks oldest-first and labels them, so spread companions
  arrive on the same timeline as any other pick. `key_frame_spread_seconds` (default 10, `gt=0`)
  is the threshold, backend-only per the `camera_timezone` precedent; the analyzer threads it and
  the timezone IDENTICALLY into the request builder and `key_frame_ids` — a provenance call
  without them silently drops the spread frames' evidence rows (`if p in by_path`), which
  `test_calling_ids_without_the_spread_would_silently_drop_a_frame` characterizes. The specialist
  stage deliberately stays unthreaded: the measured delta must attribute to the verifier's input
  alone. The acceptance's determinism and 4-frame-budget property tests run with spread ON.
  Status stays `open` until the owner merges; the S3 delta stays gated on ISS-037 (PR #6831).
- **Closed 2026-10-07 [V]:** Implemented temporal spread (`key_frame_spread_seconds`) in `select_key_frames`; merged in PR #6834 (`d6ba78d5`).

#### ISS-016 — Freeze a dev/holdout split before any prompt or specialist tuning on tierb-v0

`P1` (verifiers read `P1`, `P2`) · `risk` · actor `agent-now` · status `done` · closed 2026-10-06 (see the closure note)

- **Evidence**
  - Grep for `holdout` and `held-out` over `synthbench/`, `backend/evaluation/`,
    `docs/superpowers/`, `docs/plans/`, `docs/benchmarks/` and `docs/vss-integration/` (excluding
    the untracked handoff note) finds no match [V]
  - F14 names the next lever: 'If no candidate reaches 90%, the lever is prompts and specialist
    context' (`docs/plans/2026-09-23-vss-gaming-gpu-ledger.md:235`); measured S3 is 36.5%
    (`docs/benchmarks/synthbench/p5a-2026-09-30.md:20`) [V]
  - Every scoring path takes all 450 items: `synthbench/export/vss.py` exports one flat store and
    `synthbench/score/report.py` scores it whole [V]
  - The prompt-path content commits all predate the corpus (corpus created 2026-09-29, last content
    commits 2026-09-28; handoff `docs/plans/2026-10-03-vss-vlm-exercise-handoff.md:224` says the
    core files are unchanged since `ca73f1ef`), so the committed baseline is a clean pre-tuning
    measurement [A]
- **Why it matters.** Once prompts are tuned against all 450 items the S3 number stops being an
  estimate, and declared truth plus a per-scenario failure gallery makes overfitting easy. The risk
  is prospective: no tuning on tierb-v0 has happened yet, so this is a 'do before the first tuning
  run' gate. A 30% holdout of 450 is about 63 benign and 72 incident items; at 0/63 the Wilson upper
  bound for S2 is about 5.7% [C], so the holdout cannot resolve S2 against a 5% bar, and a single
  replay draw is itself noisy (ISS-078).
- **World-class gap.** Pre-registered dev/holdout/regression sets, with the holdout touched once per
  release candidate.
- **Acceptance.** The export carries a fixed, hash-pinned split stratified by scenario, recorded in
  the eval store and chosen with the power limits above in mind (the S2 bar needs the benign arm
  intact; consider a split on S3 only, or on scenario rather than item). Tuning uses dev only; the
  holdout is replayed k times per candidate, not once, with the spread reported; `report.md` labels
  dev and holdout numbers.
- **Depends on.** ISS-043 and ISS-078 (repeat runs before any split decision); blocks ISS-008.
- **Update 2026-10-06 (ISS-043 closed on `vlm-pipeline`) [V].** The precondition is met: the
  scenario-cluster bootstrap, the paired dS2/dS3 form and exact McNemar are in
  `backend/evaluation/cluster_stats.py` and print in every `report.md`; the sampling choice is on
  each replay's conditions line. Split design is free to proceed; 'replayed k times per candidate'
  reads per the 2026-10-03 update above (one replay plus the determinism check the conditions line
  now makes inspectable).
- **Tracked as.** None found.
- **Severity note.** Verifiers read P1 (agree) and P2 (prospective, cheap if done first). Sequence
  it before ISS-008, ISS-024 and ISS-053 start.
- **Update 2026-10-03 (after `9f4e65cd`) [V].** The 'single replay draw is itself noisy (ISS-078)'
  remark no longer holds for the shipped client: ISS-078 is `done` and the assess call is greedy.
  The holdout's power limit is unaffected (it comes from the sample size, not from sampling), and
  'replayed k times per candidate' can drop to one replay plus a determinism check. The gate still
  has to exist before the first tuning run, and ISS-086's rubric arm is such a run: tune its prompt
  on a dev split, or report it as exploratory.
- **Correction 2026-10-03 (round-2 audit) [V].** The prompt-path commit dates in the last evidence
  bullet were slightly off: the last behaviour-changing commits are dated 2026-09-28, and one
  refactor, `0ba90d5f` (`refactor(r8-s2a)`: the constrained-decoding vocabulary moved to its own
  module, touching `vlm_client.py` and `vlm_analyzer.py`), is dated 2026-09-29 00:16:08 -0400 =
  04:16Z, 16 minutes after `corpus.json` `created` 2026-09-29T03:59:50Z. The handoff's 'unchanged
  since `ca73f1ef`' holds: `git diff --numstat ca73f1ef 5c605e1d` over `vlm_client.py`,
  `vlm_analyzer.py`, `vlm_verdict.py` and `backend/evaluation/vlm_replay.py` is empty.
- **Closure 2026-10-06 (branch `vlm-pipeline`, owner-authorized slice; commits `54d036d5`..`8cdbb412`) [V].**
  Design `docs/superpowers/specs/2026-10-06-synthbench-iss016-dev-holdout-split-design.md`, plan
  `docs/superpowers/plans/2026-10-06-synthbench-iss016-dev-holdout-split.md`. The acceptance's
  'fixed, hash-pinned split' is a published hash order rather than a choice: incident scenarios are
  ranked by `sha256("tierb-v0|vss-iss016-s3-holdout-2026-10-06|<scenario>")` and the first `k` = 6
  are the holdout, so anyone holding the three published strings recomputes the roster and nobody —
  the owner included — can pick a flattering six. **The realized roster**, beside each one's item
  count and group: `tailgating` 9 suspicious, `blunt_weapon` 9 threat, `car_break_in` 9 threat,
  `casing_with_phone` 9 suspicious, `knife_visible` 19 threat, `peering_into_windows` 9 suspicious —
  **holdout 64 incident items (27% of 241), 0 benign; dev 386 items, 209 benign and 177 incident.**
  All 209 benign items stay in dev by rule, so S2's benign arm is intact and tunable, which is what
  the acceptance's power-limit clause asked for. Unit is the scenario, never the item, so no item's
  identity or store fingerprint moves and every frozen record keeps its meaning. The split is
  recorded where it is used and checked where it is read: `splits.json` at the export root
  (create-once, canonical bytes, its sha256 the fingerprint), a `splits` table in the eval store
  (`backend/evaluation/eval_store.py`) written by replay from the export's manifest and refused on a
  store that already holds a different roster, and `score` reconciling store against export — any
  disagreement is `ScoreRefused`/exit 2, never a silent re-labelling. Tuning's enforcement half is
  the surface a tuner actually reads: `report.md` labels every dev and holdout number and states what
  the holdout cannot say (n=64 clustered, and suspicious-heavy by luck, so it reads below dev for
  any prompt that has not fixed the weak leg), while `report.html` and the failure gallery carry dev
  items only. Per-arm headlines and the dev-vs-holdout comparison print beside the ISS-043 statistics.
  Tests: `test_export_vss.py` (the six names and their order recomputed from the recipe, the seed
  asserted literally, a fixed digest pin, create-once and the conflicting-manifest exit),
  `test_eval_store.py`, `test_replay.py`, `test_score.py`; `backend/tests/unit/synthbench` plus
  `backend/tests/unit/evaluation` green (1268 passed, 1 skipped).
  **What this closure does NOT do.** It is the mechanism and the labelling, not the tuning: prompt,
  threshold and specialist-context work is ISS-008, ISS-086, ISS-024 and ISS-053, which this issue
  gates. It is not the OD-15 label work either — the pre-screen reads all 450 stills for label
  correctness, which is not tuning, and corrected labels apply to both arms; what must never touch
  the holdout is a prompt or threshold change derived from reading it. It re-scores nothing: P5a's and
  the sweep's committed records stay as frozen, and a pre-split export still scores and reports
  `split: unrecorded` exactly as before. And the real `splits.json` is not an artifact of this
  branch: the owner's export host holds the corpus, so the manifest lands on the owner's next
  `synthbench export vss` (no GPU needed, and it lands before any replay). If that run's printed
  roster is not these six, the export population changed and the design's premise needs the owner,
  not a code fix. **What it unblocks:** ISS-008's before-and-after reading (this issue was its
  blocker), and E1's rubric arm may now tune on dev instead of reporting itself exploratory.

#### ISS-037 — Eval harness cannot measure multi-frame, selector or temporal behavior

`P2` · `gap` · actor `agent-now` · status `done` · closed 2026-10-07 (see the closure note)

- **Evidence**
  - `synthbench/export/vss.py:38` `STILL_FILE = "still.jpg"`: each exported set is one still [V]
  - `backend/evaluation/vlm_replay.py:136` replay feeds `item.media_paths` (at most 4) straight to
    `VlmClient.assess`, bypassing `select_key_frames` and the batch aggregator, and passes no
    `frame_detection_ids`; `backend/evaluation/vlm_replay.py:15-19` says replay does not select key
    frames [V]
  - The committed numbers are stills with an ideal detector
    (`docs/benchmarks/synthbench/p5a-2026-09-30.md:37`) [V]
- **Why it matters.** Every published S2/S3 number is single-still. The 2-4 frame path, frame
  ordering, the prompt-fit truncation (ISS-006), the `frame: k` prompt arm and any future temporal
  feature ship with no accuracy evidence.
- **World-class gap.** Eval that mirrors the production path (batch -> selector -> prompt) and
  slices accuracy by number of frames and elapsed time.
- **Acceptance.** A corpus slice of multi-still sequences (approach, linger and leave triplets with
  declared truth) is exported alongside the singles; replay can drive `build_assess_request` and
  `select_key_frames` end to end; the report states S2/S3 for single versus multi-frame with
  intervals and the minimum-n rule.
- **Depends on.** Precondition for measuring ISS-005, ISS-006, ISS-033, ISS-035 and ISS-036.
- **Tracked as.** None found.
- **Update 2026-10-07 (branch `iss037-multiframe-harness`, owner-funded /goal slice; PR pending
  owner merge) [V].** The harness is in: `export vss --sequences 3|4` exports sequence sets beside
  the stills; replay runs `--frames stored|selector|burst` (with `--with-sequences`), the selector
  mode driving the shipped `build_assess_request`/`select_key_frames` unchanged — a same-camera
  triplet's collapse to one frame is what that mode measures (ISS-005's question); and `score`
  reports S2/S3 per depth fed, with intervals and the minimum-n rule, plus a per-row harness
  recording what the wire actually received. The corpus clause is met by owner ruling (in-session,
  2026-10-07), which replaces this acceptance's scripted wording: the sets are frame-sampled from
  rendered clips, not scripted triplets (fixed fractions, re-derivable from the sha-verified mp4;
  scripted renders wait on the owner's renderer window). They carry the clips' declared truth,
  undistributed and unaudited exactly as the clips are, and no clip S2/S3 number is published
  before the blind audit (ISS-038, ISS-044). Status stays `open` until merge; on merge, acceptance
  is met by this update's disclosure.
- **Closed 2026-10-07 [V]:** Multi-frame sequence export, selector replay (`--frames selector`), and depth-sliced scoring merged in PR #6831 (`41f2aae9`).

#### ISS-043 — Add cluster-aware intervals, repeat runs and a noise floor to S2/S3

`P2` · `gap` · actor `agent-now` · status `done` · closed 2026-10-06 (see the closure note)

- **Evidence**
  - `backend/evaluation/s_metrics.py:36` `wilson_interval` treats items as independent; events share
    scenarios (8 to 29 ready events per scenario [C: counted from the mounted corpus index]) so
    scenario-level variance is not in the interval; grep of `backend/evaluation`, `synthbench/score`
    and `synthbench/run` finds no bootstrap, McNemar, paired-test or noise-floor logic [V]
  - Run-to-run noise is measured: three readings of the same 450 sets give S2 false alarms 14 / 19 /
    18 of 209 and S3 hits 88 / 87 / 84 of 241
    (`docs/plans/2026-10-03-vss-vlm-exercise-handoff.md:254`); only 278 of 450 items (62%) returned
    an identical verdict and score across two identical runs
    (`docs/plans/2026-10-03-vss-vlm-exercise-handoff.md:259`) [V]
  - The cause is sampling: the shipped assess request uses `temperature` 0.1 with no seed
    (`backend/services/vlm_client.py:796`; see ISS-078) [V]
  - `synthbench/run/replay.py` runs one replay per model, and `synthbench/score/metrics.py:28`
    `MIN_N = 10` hides small cells [V]
  - The scenario-level swings quoted in the original (0.0% to 94.7%, 14 of 30 cells insufficient)
    and a 'worst scenarios' list could not be found in source and are withdrawn [A]
- **Why it matters.** Pass, marginal or fail calls and before/after prompt comparisons will be
  driven by sampling noise and scenario clustering. The committed S2 sits 1.7 points above its bar
  and the run-to-run sd is 2.6 items of 209 = 1.2 points of S2 (n=3, a rough band, not a CI; the
  three readings span 5 items = 2.4 points [C]), so a single run cannot decide F14's label.
- **World-class gap.** Every headline number carries a variance estimate that reflects clustering
  and run noise; changes are gated on paired significance.
- **Acceptance.** The report adds a scenario-level cluster-bootstrap interval beside Wilson, and a
  run-to-run spread from at least 3 replays per model (or a seeded or temperature-0 mode with the
  choice recorded on the conditions line). Comparisons between two prompts use a paired test (for
  example McNemar on shared items) and are never called an improvement inside the noise floor.
- **Depends on.** ISS-078 (decides whether the noise is removed or measured); precondition for
  ISS-008, ISS-016 and ISS-017.
- **Tracked as.** None found; the handoff addendum lists the consequence as a candidate issue
  (`docs/plans/2026-10-03-vss-vlm-exercise-handoff.md:272`).
- **Update 2026-10-03 (after `9f4e65cd`) [V].** The sampling cause named above is removed from the
  shipped client: ISS-078 is `done`, the assess call samples at temperature 0, and two replays
  agreed on 450 of 450 items. The 'repeat runs' half of the acceptance therefore narrows to a
  temperature-0 mode with the choice recorded (see the note under ISS-045); the cluster-aware
  interval and the paired test are unaffected, because scenario clustering and the McNemar basis do
  not depend on sampling. Determinism was shown on two runs on one server and one build; hardware,
  concurrent slots and a build change are untested [?], so a repeat-run check is still worth one
  line in any report that compares two arms.
- **Closure 2026-10-06 (branch `vlm-pipeline`, owner-authorized slice) [V].** All three acceptance
  terms are in the shipped report path:
  **(1) Cluster interval beside Wilson** — `backend/evaluation/cluster_stats.py` (new; stdlib-only,
  the sweep script's estimators promoted: the scenario-cluster bootstrap and its paired form, exact
  McNemar, and the noise-floor spread). `synthbench/score/metrics.py` `headline()` gains
  `s2_cluster`/`s3_cluster` (scenario tables over the same rows as the Wilson cells) and
  `comparison()` gains `dS2`/`dS3` with 95% cluster CIs over the shared items plus per-bar exact
  McNemar on the discordants; `report.md` prints clustered columns beside every Wilson cell and the
  paired columns in the Comparison table, with a note stating what each resamples. `SCORE_VERSION`
  bumps to 2 for the `metrics.json` schema change. **(2) The sampling choice recorded** —
  `run.json` and the report's conditions table now carry `temperature` and `seed` per model, and a
  test pins the record against the request actually sent (the ISS-045 2026-10-03 acceptance addition
  is met for the sampling half; ISS-045 stays open for its own terms). The repeat-run spread stays a
  per-report term (the noise floor lives in `cluster_stats.noise_floor`; it is computed when a report
  has reruns to describe). **(3) Paired comparisons, never 'improvement' inside the floor** — the
  paired statistics are in every comparison the report prints; OD-26's rule text (already
  'never a pick') and the Intake entry of 2026-10-06 keep the wording binding. Tests:
  `backend/tests/unit/evaluation/test_cluster_stats.py` (hand-computed pins — identical clusters at
  zero width, heterogeneous clusters strictly wider than Wilson, McNemar small-numbers by hand) and
  the additions to `test_score.py` / `test_replay.py`; full unit suite green (30,461 passed, 122
  skipped, 8 xfailed) on `vlm-pipeline`. Not in this closure: the sweep's `stats.json` was not recomputed (it is a frozen
  record of its own run) and ISS-045's remaining terms are untouched.

#### ISS-097 — The model sweep's results live only in off-repo scratch: commit its report once the sweep ends, and set the rule for what beats the 8B

`P2` · `decision` · actor `owner-decision` · status `done` · added 2026-10-03 (after `2a3f0883`, with the sweep at 5 of 15 rows)

- **Evidence**
  - The sweep is 12 model arms (`SPEC` in `sweep.py`: Qwen3-VL-8B Q8_0, Qwen3.5-4B Q8_0, Qwen3.5-9B
    Q4_K_M and Q6_K, Gemma-4-12B QAT Q4_0, Qwen3-VL-32B Q4_K_M, Gemma-4-26B-A4B QAT Q4_0, Qwen3.8-27B
    UD-Q4_K_M, UD-Q6_K and GSQ-RCO IQ2_S, Qwen3-VL-30B-A3B Q8_0, Qwen3.6-35B-A3B UD-Q6_K) and 3
    controls (`CONTROLS`: `control-q4km`, `control-rep`, `control-defaultcache`), replayed over the 450
    tierb-v0 sets. Driver, results and weights live in
    `$AGENT_GPU_DIR/out/experiments/model-sweep/` and `$AGENT_GPU_DIR/models/sweep/`, outside the repo:
    a `git ls-files | grep -i sweep` at the tip lists only unrelated files (none is a model-sweep
    driver or report), and `docs/benchmarks/synthbench/` holds six pages (`clips-probes`,
    `p1-bakeoff`, `p3-acceptance`, `p3-probes`, `p5a-2026-09-30`, `p5a-probes`), none a sweep report [V]
  - It is unfinished. At 17:49 EDT on 2026-10-03 `results.jsonl` held 5 of 15 rows (the three
    controls, `qwen3vl-8b-q8`, `qwen35-4b-q8`) and `sweep.log` showed `qwen35-9b-q4km` serving. The
    live sweep process (`/proc/<pid>/environ`) carries no `EXP_RUBRIC`, `SWEEP_LIMIT` or
    `SWEEP_DELETE_WEIGHTS`, so the remaining arms run the shipped prompt over all 450 sets and keep
    their weights. The ledger's row headed 'VLM-PATH MEASUREMENT AND CLEANUP (2026-10-03)', in its
    close pointer, says the sweep 'is RUNNING and its results are not claimed here', and ISS-087 says
    the sweep 'is unfinished and its numbers are not recorded as measured until a report is committed' [V]
  - The sequencing is recorded in the repo, not quoted from the owner. The Intake log entry 'after the
    merge of #6783 and the reorganization decisions' says 'the sweep report is committed only after
    the sweep finishes and a selection rule is set', and handoff Addendum 9 records the sweep itself
    as 'owner decision: evaluate every discovered tier pick on tierb-v0' [V: read; both are
    agent-written records of an owner answer of 2026-10-03, so the owner's statement itself is [A]
    and its own words are not in the repo]. The target directory `docs/benchmarks/synthbench/` is not
    named in any repo document about the sweep [V: grep of `docs/plans` and `docs/vss-integration`];
    it is where the committed P5a pages live [V], and the owner's choice of it is [A: stated in the
    request that triggered this block]
  - No rule for what beats the 8B exists [V: grep of the register, the ledger, the handoff and docs 18
    and 20 for 'selection rule', 'beats the 8B' and 'beat the 8B', then a read of the hits]. What
    exists: ledger item 35's three flip conditions (heading 'The flip conditions, written falsifiable
    while they are fresh'): (i) the 8B fails S1 on 24 GB, then the 4B pair; (ii) KV density binds
    stream count, then Nemotron-Nano-12B-v2-VL reopens; (iii) corpus S3 below `S3_MIN` 90%, or
    candidate C's `uncertain` rate proves a real hedging prior, then the pick reopens. These are
    triggers, not a test a challenger must pass. OD-4 asks whether declared-truth replay counts for
    (iii); `18-world-class-target.md` R10 calls the pick 'provisional'; doc 20's E3 reads its 2x2
    informally ('If 32B/shipped clearly beats 8B/rubric on B, capability is real') and does not
    define 'clearly'. The pick itself is the owner's 'lets go with Qwen3-VL-8B for now. we can revisit
    later if needed.' (ledger item 35) [V]. The sweep schedules no Nemotron arm, although flip
    condition (ii) and OD-4 name Nemotron-Nano-12B-v2-VL as the challenger [V: `nemotron` occurs
    0 times in `sweep.py` and in `recipes.json`]
  - The replay artifacts do not carry the conditions a report must print. `synthbench/run/replay.py`
    `conditions()` returns six fields (`enforcement_probe`, `request_extra`, `max_tokens`,
    `read_timeout`, `system_message`, `thinking`); the `run.json` of
    `20261003T204300Z-qwen3vl-8b-q8` adds `build`, `commit` and `served_id` and has no key for
    temperature, quantization, mmproj, weight hash, image-token cap, KV type, context or the two
    cache flags [V: read both `run.json` files of the control and the Q8 arm]. They have to be
    assembled from `sweep.py` (`COMMON`, `SPEC`, `CONTROLS`), `recipes.json` and `results.jsonl`.
    What those say [V]: - Build `b11376-a55e952b8`, image `ai-vlm:sm103-b11376`, in every row read; `COMMON` env
    `CTX_SIZE` 32768, `PARALLEL` 2, q8_0 K and V cache, flash attention, `LLAMA_ARG_IMAGE_MAX_TOKENS`
    1280, `LLAMA_ARG_CACHE_RAM` 0 and `LLAMA_ARG_CACHE_IDLE_SLOTS` 0 (both unset only for
    `control-defaultcache`). `COMMON` equals the `ai-vlm` env defaults of `docker-compose.prod.yml`
    (`VLM_CTX_SIZE`, `VLM_PARALLEL`, `VLM_THREADS`, `VLM_BATCH_SIZE`, `VLM_UBATCH_SIZE`, the q8_0
    cache types, flash attention, the 1280 image-token cap) except `GPU_LAYERS` (99 in the sweep,
    `auto` in compose) and the two cache flags, which neither the compose file nor `ai/vlm` sets
    (`grep` for `CACHE_RAM`, `cache-ram` and `CACHE_IDLE` finds nothing) - Temperature: the sweep sets none. `replay_arm.py`'s shim adds only `EXP_REQUEST_EXTRA` (and the
    rubric when `EXP_RUBRIC=1`), so the request carries the shipped client's `_ASSESS_TEMPERATURE =
0.0` (`backend/services/vlm_client.py`); that constant is 0.0 at `ab3bd002` and at `2cd619db`
    (the `commit` in the control's and the Q8 arm's `run.json`; both are ancestors of the tip), and
    `git diff --stat ab3bd002 2cd619db -- backend/services/vlm_client.py backend/evaluation
synthbench ai/vlm` is empty. Not recorded in any `run.json`, and a dirty checkout would read as
    its HEAD commit (ISS-045) [?] - Read timeout 180 s for every arm (`READ_TIMEOUT`), against 25 s in the committed P5a 'Conditions
    per model' table; `max_tokens` 1024 as shipped - Differences between arms, which handoff Addendum 9 names as confounders: thinking forced off
    (`LLAMA_ARG_REASONING=off` plus request `chat_template_kwargs`) on 9 arms (Qwen3.5 x3, Qwen3.8
    x3, Qwen3.6, Gemma x2) and not on the Qwen3-VL arms or the controls; the two Gemma arms use
    `UBATCH_SIZE` 2048 and an image-token cap of 1120; mmproj precision by file name is Q8_0 (the
    Qwen3-VL arms and the controls), F16 (Qwen3.5, Qwen3.8 Q4_K_M and Q6_K) and BF16 (Qwen3.6,
    Qwen3.8 IQ2_S), and not stated in the two Gemma file names [?]; `--vram` declared per arm runs
    10 to 40 and affects admission only - VRAM peak is the largest `vram_actual_mib` that `sample_vram` read from `agent-gpu status` at
    60 s intervals, so it is a lower bound [C]. F13 reserves S1 and S4 to 24 GB-class hardware
    (spec rev 7 header), the committed P5a page says that on the GB300 'no latency or memory figure
    here stands for a deployment', and doc 20 (bullet 'Keep extending synthbench: what exists, what
    is missing') says the 10/12/16/24/32/48 GB fit 'must come from real blob sizes + KV + buffers',
    so the column is a sizing hint and not a tier-fit result
  - Provenance is partly in scratch. `recipes.json` carries repo, file, byte size and sha256 for every
    model and mmproj file of the 12 arms, and `download()` raises on a size or sha256 mismatch; the
    control arm's files carry no hash in `run_arm` (the shipped files already on disk), though ledger
    item 35 pins the shipped pair (`Qwen3VL-8B-Instruct-Q4_K_M.gguf` sha256 `67d1659b…e9e2`,
    `mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf` sha256 `c6ba85508d82…`) and the Q8_0 arm's mmproj has the
    same `c6ba85508d82` prefix. `sweep.py` reads `recipes.json` from a session scratchpad when it
    exists and from the sweep directory otherwise; the two copies are byte-identical today (`cmp`).
    All arms write to one off-repo store (`sbroot/eval/tierb-v0/eval.sqlite`), and two replays carry
    the tag `control-q4km` (the first scored 3 items per `sweep.log` 15:42:53; the control of record
    is `20261003T194331Z-control-q4km`). Handoff Addendum 9 still says weights are deleted after each
    arm; `sweep.py` now keeps them [V]
  - The scoring path is the sweep's own in part. S2 and S3 counts are parsed from `run_replay`'s
    printed report; AUROC, recall at 5% false alarms, scene-group hits and hard-negative false alarms
    come from `analyze()` in `sweep.py`. A grep of `backend/evaluation` and `synthbench` finds no
    AUROC, and `$AGENT_GPU_DIR/out/sbroot/runs/scores/` holds two entries, both from before the sweep
    (`20261003T133003Z`, `20261003T134742Z`): no sweep replay has been through `synthbench score` [V].
    The committed P5a page shows the format to follow: 'Conditions per model' and 'Run identity'
    tables (replay id, endpoint, build, weights sha256, replay commit) and Wilson cells [V]
  - Why one column cannot order the arms, sized only from what ISS-087 already records: the same 8B
    at Q8_0 agrees with its Q4_K_M control on 252 of 450 items, so 198 of 450 answers differ under a
    precision change alone [C: 450 - 252], and the control is deterministic (450 of 450 on two
    repeats) [V: `results.jsonl` rows `control-rep`, `control-defaultcache`, `qwen3vl-8b-q8`]. A
    margin smaller than that cannot be told from a precision or configuration effect, and the rows
    read so far already show the metrics the sweep prints (S2, S3, AUROC, recall at 5% false alarms)
    disagreeing in direction for at least one arm [V: `results.jsonl` at 17:49 EDT]. The other arms'
    numbers are deliberately not copied into this register: the owner's sequencing sets the rule
    before the report, and a rule written beside the results invites fitting to them [C]
  - Update, appended 2026-10-04: done. The owner told the agent "set the selection rule and sweep report"
    (17 Intake log, 'the sweep report and the selection rule'). The report is `docs/benchmarks/synthbench/sweep-2026-10-03/report.md`, with its
    data (`items.csv`, `arms.csv`, `stats.json`) and `analysis.py`, which recomputes every reading from
    those files and asserts each count equals the harness's **[V: run this session, `stats.json`
    reproduced byte for byte]**. The OD-26 rule was set after the readings were seen, its output is a
    shortlist for confirmation and not a pick, and **no arm advances**; the nearest miss is Qwen3.8-27B
    Q4_K_M. The rule's content is agent-authored **[A]** and open to the owner's amendment. What remains
    is not this issue's: a frozen holdout to confirm any arm (ISS-016), the power to separate arms at the
    scenario level (ISS-043) and re-qualification on the pinned build (ISS-087).
- **Why it matters.** Until the report is committed the sweep's numbers are session artifacts that no
  document may cite as measured (ISS-087, ledger row 76), and the pick they bear on (flip condition
  (iii) and OD-4, and the model-size lever of ISS-086's E3 under OD-2) cannot move. Committing the
  table without a rule either leaves a table nobody can act on or makes the pick by whoever writes its
  summary line. Choosing the best of 12 arms on the same 450 items that are then quoted as the result
  is a selection on the test set [C], and no holdout (ISS-016) or paired test (ISS-043) exists yet.
  Every number also carries the claim scope of ISS-007 (declared truth, ideal detector, no specialist
  context), and if ISS-086's ceiling hypothesis holds (64 of 241 incidents not recoverable from one
  still, S3 capped near 73.4% for any model), a candidate's S3 is not the whole story.
- **World-class gap.** A model change is gated by a rule fixed before the arms were read, applied to
  an archived report whose per-arm conditions are complete and reproducible from the repo; failures,
  refusals and the 8B control print beside every candidate; and a winner is confirmed once on items
  that did not choose it.
- **Acceptance.**
  1. The owner rules on OD-26 (filed with this block) and the ruling is recorded
     as a dated line in the ledger and under section 4. The ruling settles: (a) which metrics count,
     in what order and direction (S3 hits, S2 false alarms, AUROC, recall at 5% false alarms,
     refusals); (b) the margin and the test (a paired test on shared items per ISS-043, or a fixed
     margin), and whether the F14 bars (S2 5%, S3 90%) are absolute gates or the 8B control is the
     yardstick; (c) gates beyond accuracy: S5 refusals, tier fit against the doc 20 budgets (which
     this sweep cannot measure, F13), licence (ISS-063); (d) whether selection and confirmation use
     the same 450 items (ISS-016); (e) how arms run under unequal conditions (thinking forced off,
     the 1120 image-token cap, mmproj precision) are compared. A check: `grep -n 'OD-26'` finds the
     section-4 row and the ledger line, and the ruling text answers (a) to (e).
  2. After `sweep.log` ends with `sweep finished` and `results.jsonl` holds 15 rows (an arm that
     errored keeps its `error` row and is printed as an error), a dated page is committed under
     `docs/benchmarks/synthbench/` with: a conditions table per arm (build and image tag; repo, file,
     quantization, byte size and sha256 of the model and of the mmproj, with the mmproj precision;
     server env that differs from `COMMON`; thinking and request extras; image-token cap;
     `max_tokens` and read timeout; temperature read from the client constant at the arm's replay
     `commit`; cache flags); a run-identity table (replay id, `eval_run_id`, `run.json` path); S2, S3
     with Wilson cells, AUROC, recall at 5% false alarms, refusals and truncations, and each arm's
     agreement with the control; VRAM peak with its sampling method and the F13 caveat; the three
     controls' identical-item counts; the claim scope of ISS-007; and the sha256 of `sweep.py`,
     `replay_arm.py` and `recipes.json`.
  3. A reviewer can re-derive it: each `eval_run_id` on the page is found in `eval.sqlite` and the S2
     and S3 counts recomputed from that run equal the page's; `sha256sum` of each kept weights file
     equals the page's value; `grep -c` of each of the 15 arm keys on the page is at least 1; and the
     numbers that came from `analyze()` are either re-run through `synthbench score` or labelled as
     the sweep's own computation.
  4. The page applies the OD-26 rule and states its outcome, which may be that no arm beats the 8B;
     the ledger row cites the page, and the notes under ISS-087, ISS-086 (E3) and OD-4 are updated.
- **Depends on.** OD-26 (new; the highest id in section 4 at `2a3f0883` is OD-25, so confirm the next
  free id when filing); the sweep finishing (agent-run, in progress). Related: ISS-087 (the report is
  the first user of its 'build and cache flags on the conditions line' acceptance), ISS-045 (the
  temperature on the run identity) and ISS-046 (KV, context and image-token settings on the run
  identity; until both land the conditions table is assembled by hand), ISS-043 (paired test),
  ISS-016 (dev/holdout), ISS-063 (licences), ISS-007, ISS-086 (the sweep's `qwen3vl-32b-q4km` arm is
  the shipped-prompt cell of its E3 on `b11376`; the 32B weights were downloaded and hash-verified at
  17:18 EDT per `download_all.log`; `SPEC` schedules no rubric arm, so the rubric cells are not
  run [V]), OD-2, OD-4 (whose named challenger, Nemotron-Nano-12B-v2-VL, is not in the sweep).
- **Update 2026-10-06 (ISS-016 and ISS-043 closed on `vlm-pipeline`) [V].** The 'no holdout
  (ISS-016) or paired test (ISS-043) exists yet' above is no longer true: both now exist on this
  branch (neither in main yet). The holdout is the published hash order
  (`SPLIT_SEEDS`/`SPLIT_HOLDOUT_K` in `synthbench/export/vss.py`, realized roster in ISS-016's
  closure note) and the paired test is the cluster bootstrap plus dS2/dS3 and exact McNemar in
  `backend/evaluation/cluster_stats.py`, so the OD-26 rule can name a confirmation set that did
  not choose the arm and a test that separates arms at the scenario level. What the rule still
  cannot do is run that confirmation: the split is recorded only once the owner re-exports, and
  the sweep's 450 items were read before either existed.
- **Tracked as.** Handoff Addendum 9 (the sweep and its confounders); ledger row 76 close pointer
  (the sweep RUNNING, results not claimed); the Intake log entry after the merge of #6783 (the
  sequencing); ledger item 35 (the provisional pick and its flip conditions). No register issue or
  decision names the report or the rule before this one.
- **Severity note.** Filed `P2`: neither the report nor the rule changes a bar reading or shipped
  behaviour, and the owner can rule at any time. `P1` is defensible, because the rule gates the
  model-pick question of Step 10 (flip condition (iii), OD-4) and the model-size lever of ISS-086's
  E3; it does not gate Step 6's floor and remedy rulings (OD-2's options name no model change).

#### ISS-022 — Make the GHCR ai-gateway boot: it sets no `GATEWAY_MODEL_SET` and residency now hard-raises

`P1` (verifiers read `P2`) · `bug` · actor `agent-now` · status `done` · closed 2026-10-08 (see the closure note)

- **Evidence**
  - `ai/gateway/residency.py:84` raises `KeyError` for any set name but `vlm`, and
    `ai/gateway/residency.py:95` reads `GATEWAY_MODEL_SET` with no default, so an unset variable
    raises; the docstring (`ai/gateway/residency.py:22`) claims 'compose always passes' it [V]
  - `ai/gateway/entrypoint.sh:8` is `set -e` and `ai/gateway/entrypoint.sh:131` runs
    `python3 -m ai.gateway.residency` before Triton starts, so a raise stops the container [V]
  - The `ai-gateway` service in `docker-compose.ghcr.yml:156` sets no `GATEWAY_MODEL_SET`; the only
    compose file that passes it is `docker-compose.prod.yml:387`; `docker-compose.ghcr.yml:196`
    still says 'Triton loads 14 models' [V]
  - The failing artifact is not published: `.github/workflows/deploy.yml:30` says ai-gateway and
    ai-vlm 'were never matrix images here' and that the ghcr compose pulling ai-gateway, with no
    `ai-vlm`, is 'a reported publish gap, owner-adjudicated' [V]
  - No later fix: nothing touches `docker-compose.ghcr.yml` after the R8 S3 commit `3b73b9b6`
    (verifier git log [A])
- **Why it matters.** R8 S3 turned an unset `GATEWAY_MODEL_SET` into a boot refusal and fixed only
  the prod compose, so a ghcr deploy of a post-R8 gateway image exits at the entrypoint and the
  detector never comes up. The impact sits behind a larger, already ledgered blocker: the image is
  not published and the same file has no `ai-vlm`, so the ghcr stack cannot serve the shipped
  pipeline regardless (ISS-028).
- **World-class gap.** Every shipped compose file is generated from, or pinned against, one
  residency source, and a CI boot smoke runs the gateway entrypoint against each compose file's env.
- **Acceptance.** A test parses every tracked compose file that defines `ai-gateway` and asserts
  `GATEWAY_MODEL_SET` resolves to `vlm` (or the service is removed from that file), plus a unit run
  of `python -m ai.gateway.residency` with each file's environment that exits 0; the 'Triton loads
  14 models' comment is corrected.
- **Depends on.** Fold into ISS-028 (OD-14) if the owner decides the ghcr stack is to serve the VLM
  path.
- **Tracked as.** Partial: `.github/workflows/deploy.yml:30` records the publish gap (missing image
  and `ai-vlm`), not the missing variable.
- **Severity note.** Verifiers read P2: latent one-line omission behind the publish gap.
- **Closure note — 2026-10-08 (O1.2, PR #6907) [V].** Mooted by deletion, which is the Acceptance's
  own escape hatch ("or the service is removed from that file") carried to its end: the file is
  gone. `docker-compose.ghcr.yml` no longer exists, so the only tracked compose file that defines
  `ai-gateway` is `docker-compose.prod.yml`, and its `GATEWAY_MODEL_SET` is pinned to `${GATEWAY_MODEL_SET:-vlm}`
  by `backend/tests/unit/core/test_gateway_model_set_compose.py` — the Acceptance's parse-every-
  tracked-compose leg, over the set that now has one member. The 'Triton loads 14 models' comment
  named here lived in the deleted file. `scripts/retired_paths.txt` + `scripts/test_retired_paths.py`
  (in ci.yml's collection-sanity list) keep it gone and keep living text off it, so this cannot
  silently reopen. The world-class half — a CI boot smoke running the gateway entrypoint against each
  compose file's env — is unmade rather than met: there is one compose file to boot now, and ISS-017
  (CI for the VLM path) is where a boot smoke belongs. The evidence lines above naming the deleted
  file are read as filed; its history lives here, not in the tree.

#### ISS-029 — The published frontend nginx proxies an API whose data routes have no authentication

`P1` · `bug` · actor `owner-decision` · status `done` · closed 2026-10-09 (see the closure note)

- **Evidence**
  - `docker-compose.prod.yml:911` and `docker-compose.prod.yml:912` publish the frontend nginx on
    `0.0.0.0` (HTTPS 8444, HTTP 8080); the adjacent comment names a 'Cloudflare tunnel / Brev secure
    link' and says 'use firewall to restrict if needed' [V]
  - `frontend/docker-entrypoint.sh:65` `location ^~ /api` and `:88` `location ^~ /ws` proxy to the
    backend upstream; the only guards are `limit_req`, and grep finds no `auth_request`,
    `auth_basic` or `allow`/`deny` in the file [V]
  - `backend/main.py:1490` (NEM-5527) records that the global `AuthMiddleware` is disabled;
    `backend/main.py` has no `add_middleware(AuthMiddleware)` and
    `backend/api/middleware/auth.py:214` defines the class [V] (note 2026-10-09: all three
    numbers are (at `5c605e1d`); B1.5 (#6861) deleted the disabled-note and added
    `app.add_middleware(AuthMiddleware)` at `backend/main.py:1578` — the closure note below
    carries the current state)
  - Route modules with an auth dependency: `admin`, `auth`, `dlq`, `inbound_webhooks`, `debug`,
    `system` (grep of `backend/api/routes` for `Depends(require_`/`verify_`/`get_current`). A match
    count of 0 for `events.py`, `media.py`, `face_recognition.py`, `household.py`, `notification.py`
    and `zones.py` [V]
  - `require_admin_access` (`backend/api/routes/admin.py:262`) checks only `admin_enabled` and no
    credential; `backend/core/config.py:835` defaults it True and says `admin_api_key` is enforced
    by nothing; but `docker-compose.prod.yml:618` (backend service) sets
    `ADMIN_ENABLED=${ADMIN_ENABLED:-false}`, so the admin wipe routes return 403 by default in the
    shipped compose. Behind `ADMIN_ENABLED=true` anyone who can reach the port can call them [V]
  - The WebSocket gate is a no-op by default: `backend/api/middleware/auth.py:93` returns True when
    `api_key_enabled` is false, and `backend/core/config.py:1935` defaults it False [V]
  - `POST /api/notification/test` (`backend/api/routes/notification.py:252`) accepts caller-supplied
    `email_recipients` and `webhook_url` (`backend/api/schemas/notification.py:112`, `:115`; the
    webhook URL passes SSRF validation) and records the audit actor as the literal 'anonymous'
    (`backend/api/routes/notification.py:332`); the sender cannot choose the message body [V]
  - Documented posture: `AGENTS.md:150` says the frontend nginx is intentionally `0.0.0.0` and that
    loopback binding is the primary security boundary; `AGENTS.md:353` says that after first-time
    registration the API endpoints are open; `docs/operator/admin/security.md:9` calls it a
    'single-user, local deployment' and `docs/operator/admin/security.md:24` says 'No internet
    exposure' and 'Designed for LAN access only' [V]
- **Why it matters.** Whoever can reach the published frontend port can read and write the
  unauthenticated data routes (events, media, face and household data, notification test) and open
  `/ws`; with the VLM path those rows now include stills, scene descriptions and verdict reasoning.
  The exposure is a documented, owner-chosen single-user posture, but the pages that state it also
  say the `127.0.0.1` bind is the boundary, which does not hold for the nginx port that proxies
  `/api` and `/ws`, and `API_KEY_ENABLED=true` does not protect these routes (per
  `docs/operator/admin/security.md:19-20`, the guard covers the DLQ and inbound-webhook routes).
  Whether the Cloudflare or Brev tunnel adds its own authentication is outside the repo [?]. Not
  claimed: that the admin wipe routes are open in the shipped prod compose.
- **World-class gap.** A home-security pipeline authenticates every read of footage-derived data and
  every mutation of identity data, and ships LAN-off by default. At `5c605e1d` the documented
  control is the loopback binding plus the first-run setup guard, and the shipped frontend service
  publishes on all interfaces and proxies the API.
- **Acceptance.** The owner chooses the posture (OD-12): (a) the default compose binds nginx to
  `127.0.0.1` unless an explicit `EXPOSE_LAN=true` is set, or (b) a deny-by-default authentication
  dependency covers every `/api` and `/ws` route except a documented allowlist, or (c) the LAN-trust
  model is kept and the docs are corrected to say the nginx port is outside the loopback boundary.
  Whichever is chosen: a route-table test fails when a new router has no auth dependency or
  documented exemption; the unauthenticated-request matrix (`/api/events`, `/api/media/*`,
  `/api/known-persons`, `/api/household/members`, `/api/notification/test`, `/ws/events`) is tested
  against the prod compose configuration; `AGENTS.md:150`, `AGENTS.md:353`,
  `docs/operator/admin/security.md` and `backend/core/config.py:835` are made consistent with it.
- **Depends on.** OD-12. Related: ISS-009 and ISS-062 (unauthenticated writes feed the prompt),
  ISS-030 and ISS-072 (stored data worth protecting).
- **Tracked as.** None found. `docs/vss-integration/10-audit-feature-inventory.md:967` (at
  `5c605e1d`) mentions the posture only as a comparison with VSS; no roadmap or ledger row.
- **Severity note.** Verifiers read P1 (only because the compose advertises tunnel ingress) and P2
  (LAN-only home deployment). The admin-route and SMTP-relay sub-claims in the original were
  overstated and are narrowed above.
- **Closure note — 2026-10-09 (B-1 follow-up, PR #6927) [V].** Closed per owner ruling 35 (#6854),
  which moved this flip off the F1.3/O1.6 merge-order duty onto this package. What is verified
  true at this head, leg by leg: OD-12 landed on main as the two-mode posture, and
  `EXPOSE_LAN=true` puts `AuthMiddleware` (outermost, B1.5) in front of every `/api` and `/ws`
  route — 401 or WebSocket close 4001 without a session cookie or key — pinned by the route-table
  enumeration in `backend/tests/unit/api/test_expose_lan_routes.py`, whose
  `test_exposed_iss_029_matrix_is_refused` runs this entry's own unauthenticated-request matrix.
  The docs named above (`AGENTS.md`, `docs/operator/admin/security.md`) state both modes honestly
  as of today — including the uncomfortable one: `AGENTS.md` still records the frontend nginx as
  publishing `0.0.0.0` in the default mode, which is what compose does at this head
  (`docker-compose.prod.yml:920-921`), and `security.md` says so plainly. Read that against the
  gate: at `EXPOSE_LAN` unset the gate passes requests through, so the default-mode mitigation
  until #6925 lands is honest documentation plus the first-run setup guard, not a loopback bind —
  the compose publish rebind that makes the LAN-off default physical is O1.6's own already-approved
  change (#6925), and ruling 35 moved this flip to this package precisely so that queued leg no
  longer gates this entry. The leg this package adds, complete at its head: on the authenticated
  mode the documented browser credential path — offering `api-key.<key>` in
  `Sec-WebSocket-Protocol` — completed no handshake at all, because no `accept()` in the backend
  echoed a token and RFC 6455 §4.1 makes browsers fail such a handshake before `open` fires;
  every accept now echoes the offered token (`backend/core/websocket/subprotocol.py`), pinned by
  raw-handshake tests over a live uvicorn
  (`backend/tests/integration/test_ws_subprotocol_echo_b1.py`). The world-class half —
  deny-by-default with a documented allowlist — is met on the authenticated mode by the gate's
  `OPEN_PATHS` design (a new route is covered without wiring, and the pin proves it for every
  mounted route); on the default mode it lands with #6925's rebind.

#### ISS-083 — Decide the fate of `tools/nemo_data_designer/` and the `nemo` extra, the retired harness's data generator

`P2` · `decision` · actor `owner-decision` · status `done` (closed 2026-10-03 in `efa1b586`) · added
2026-10-03 (after `d8482861`)

- **Evidence** (as filed at `d8482861`; the closure follows the 'Tracked as' line)
  - `tools/nemo_data_designer/` holds 10 Python files and 5,842 lines (14 tracked files with its
    `AGENTS.md`, `README.md`, `multimodal/AGENTS.md` and a `notebooks/.gitkeep`) [V: `git ls-tree -r
--name-only d8482861 tools/nemo_data_designer | wc -l` prints 14, and `wc -l` over its `.py`
    files in `git show d8482861:<path>` sums to 5,842; the index no longer lists them since
    `efa1b586`]. It generated the data the deleted Nemotron harness consumed; `d8482861` left it
    alone on purpose ('Left alone on purpose: ... tools/nemo_data_designer and the nemo extra', its
    commit message) [V]
  - Importers outside `tools/` at `d8482861`: two integration tests,
    `backend/tests/integration/test_multimodal_pipeline.py` (three imports) and
    `backend/tests/integration/test_enrichment_edge_cases.py` (one), each a
    `from tools.nemo_data_designer...` import. The root fixtures `synthetic_scenarios` and
    `scenario_by_type` in `backend/tests/conftest.py` read a generated `scenarios.parquet` with
    pandas and skip when it or pandas is absent; they name the generator in the skip message
    (`backend/tests/conftest.py:2585`) and do not import it. The multimodal tests call
    `pytest.importorskip("pandas", ...)` and call pandas an 'optional nemo-group dep' [V]
  - No non-test module under `backend/`, `synthbench/`, `scripts/`, `ai/` or `frontend/` imports
    `pandas`, `pyarrow` or `data_designer`, so the VLM path does not use the tool [V: `git grep -n
-E '^\s*(import|from) (pandas|pyarrow|data_designer)'` over those trees, excluding
    `backend/tests` and `tools`, prints nothing at `d8482861`]
  - The `nemo` extra (`data-designer>=0.9.2`, `pandas`, `pyarrow`, `numpy`) exists for it
    (`pyproject.toml:153`, and again as a dependency group at `:296`). At `5c605e1d` its one CI
    user was the deleted `prompt-evaluation.yml` (`uv sync --extra dev --extra nemo`); a grep of
    `.github`, `scripts`, `Makefile*`, `setup.py` and `pyproject.toml` for `--extra nemo` or
    `--group nemo` found, at `d8482861`, only the usage comments at `pyproject.toml:152` and `:294`
    [V]
  - The extra holds the resolution back: the comment at `pyproject.toml:154-161` records that the
    engine's pins (`cryptography`, `click`, `sqlfluff`) leak into the runtime and dev resolution and
    held `cryptography` back through open advisories, and the ledger entry
    headed 'MAIN-GREEN SLICE 6 (RECORD + OWNER QUEUE)' (numbered 63 at `5c605e1d`) names the extra
    as the reason the Dependabot `cryptography` security update cannot resolve, with owner option
    (2): 'if the `nemo` extra is not load-bearing, restructure it (separate lock / drop the
    extra)' [V: read in the ledger; at filing, whether removal clears it was unverified and needed
    `uv lock`; the closure below ran it]
  - Other references to remove or keep with it: `.pre-commit-config.yaml:146` (a comment and an
    exclude naming the tool), `.github/suppression-registry.yml:761` (the skip reason naming
    `generate_scenarios.py`), `docs/developer/nemo-data-designer.md`; `data/synthetic` holds 1,283
    tracked files of `expected_labels.json` sets and is read in that shape by `load_synthetic_items`
    (`backend/evaluation/eval_store.py:265`), which is independent of the tool [V: `git ls-tree -r
--name-only d8482861 data/synthetic | wc -l` prints 1,283, and so does `git ls-files
data/synthetic` after `efa1b586`]
- **Why it matters.** A 5,842-line generator, two integration tests and a dependency extra remain
  for a harness that no longer exists, and the extra is what the ledger records as blocking the
  security-update path for `cryptography`. So the decision is also dependency maintenance: it is
  OD-11's option 2, with a known scope.
- **World-class gap.** The repository carries what ships or what a gate runs, and a removed
  consumer takes its data generator and its dependency extra with it.
- **Acceptance.** The owner rules (OD-25, with OD-11): keep (and name the gate that runs the two
  tests and the generator), move the tool and its extra out of the runtime lock, or delete both in
  one commit as `d8482861` did the harness. If deleted: the two integration tests and the root
  fixtures go or carry a tombstone; the `nemo` extra, its group and their comments, the
  `.pre-commit-config.yaml` exclude and the suppression-registry entry go; `uv lock` is run and
  `cryptography` resolves past the engine's cap (checked, not assumed); the developer page is
  archived; `data/synthetic` stays while `load_synthetic_items` reads it; a repo-wide grep for
  `nemo_data_designer` and `data_designer` finds only historical records.
- **Depends on.** OD-25; OD-11 (the `cryptography` options; ISS-060).
- **Tracked as.** Handoff Addendum 7, 'Neighbors measured but NOT touched'
  (`docs/plans/2026-10-03-vss-vlm-exercise-handoff.md`); the ledger entry above (option 2);
  ISS-060 carries the Dependabot class.
- **Closed 2026-10-03 in `efa1b586`** (`chore(tools): remove the NeMo Data Designer tooling and the
nemo extra`). What was decided, changed and shown:
  - Decision: delete both, the third option of the acceptance, as `d8482861` did the harness. The
    commit message gives the direction ('The VLM path is the only supported infrastructure and no
    backward compatibility is kept'), and handoff Addendum 7 records that direction as the owner's
    for the harness removal [V: read]. A separate OD-25 ruling on this issue is not recorded in the
    repo [?]; OD-25 stays open for ISS-084 and ISS-085.
  - Deleted [V: `git show --diff-filter=D --name-only --format= efa1b586 | wc -l` prints 29]: 15
    files under `tools/` (the 14 of `tools/nemo_data_designer/` and `tools/__init__.py`),
    `backend/tests/integration/test_multimodal_pipeline.py` and `test_enrichment_edge_cases.py`, the
    10 files of `backend/tests/fixtures/synthetic/`, and `docs/developer/nemo-data-designer.md` with
    `docs/development/nemo-data-designer.md`. Edited, per the stat and the commit message: the two
    root fixtures `synthetic_scenarios` and `scenario_by_type` in `backend/tests/conftest.py`, both
    `nemo` blocks of `pyproject.toml`, `.pre-commit-config.yaml` (the comment and the exclude) and
    the suppression registry (20 entries).
  - Shown at `efa1b586` [V: ran]: `git ls-files tools` prints nothing (only ignored `__pycache__`
    files remain on disk); a grep of `pyproject.toml` for `data-designer`, `data_designer`, `nemo`
    (as a word), `pandas` and `pyarrow` finds nothing; `.pre-commit-config.yaml` has no `nemo`;
    a grep of that file, `.github/suppression-registry.yml` and `backend/tests/conftest.py` for
    `nemo_data_designer`, `data_designer`, `generate_scenarios`, `scenarios.parquet`,
    `synthetic_scenarios` and `scenario_by_type` finds nothing; `git grep -n -I -E
"nemo_data_designer|data_designer|nemo-data-designer"` outside `docs/vss-integration` finds four
    lines, all in three dated plan records (`docs/plans/2026-01-21-nemo-data-designer-integration-
design.md`, `2026-09-12-context-map-doc-updates.md`, `2026-09-22-docs-scan-findings.md`), which
    is the 'only historical records' the acceptance names; `data/synthetic` still holds 1,283 tracked
    files and `load_synthetic_items` is still at `backend/evaluation/eval_store.py:265`.
  - `uv lock` and the `cryptography` clause ('resolves past the engine's cap, checked, not
    assumed') [V: ran]: `uv.lock` drops 23 packages, adds none and changes no version (the
    `[[package]]` names and versions of the two lock files, compared with `tomllib`; the dropped
    ones include `data-designer`, `data-designer-engine`, `pandas`, `pyarrow`, `duckdb`, `mcp`,
    `sqlfluff` and `pyjwt`); uv resolves 268 packages from `d8482861`'s files and 245 from
    `efa1b586`'s; `uv lock --dry-run --upgrade-package cryptography` lists no `cryptography` update
    from `d8482861`'s files and prints `Update cryptography v49.0.0 -> v50.0.2` from `efa1b586`'s
    (each run in a scratch directory). So the extra was the ceiling, as the ledger said. The upgrade
    itself was not part of this commit; `f0ff083e` applied it later the same day (ISS-060 update).
  - Census guard [V: ran `uv run pytest scripts/test_suppression_census.py`: 8 passed;
    `uv run python scripts/suppression-registry-gen.py --check`: exit 0]: `pytest_skip_imperative`
    99 to 86 in `scripts/test_suppression_census.py`, the commit's account being 10 sites with the
    harness test in `d8482861` and 3 here. The commit message adds that `d8482861` itself left that
    guard red, because its verification ran `backend/tests/unit/scripts` and not the repo-root
    `scripts/` tests [A: from the commit message; not re-run at `d8482861`].
  - Acceptance clauses not met as worded, and where each goes. 'The developer page is archived': it
    is deleted (with its `docs/development/` stub) and survives only in history. The notes that
    blamed the old cap, the `CVE-2026-69247` entry in `.trivyignore` and the `cryptography` ignores
    in `.github/workflows/dependency-audit.yml`, were left untouched by `efa1b586` on purpose
    (its commit message) and removed by `f0ff083e` with the upgrade (ISS-060 update). The three plan
    records above still name the tool and are history.
  - Anchors: ISS-083's own `pyproject.toml`, conftest, pre-commit and registry anchors point at text
    this commit deleted; they describe `d8482861` (see the header note).
  - Unused-package claim: the commit message says a scan found no remaining use of the 23 dropped
    packages. I re-ran one for each of them [V: `git grep` over tracked `.py`, `.toml`, `.yml`,
    `.yaml`, `.sh` and `Makefile*` files, leaving out `docs` and `uv.lock`, for the import or name of
    every dropped package: no hit for `sqlfluff`, `diff-cover`, `duckdb`, `tblib`, `marko`,
    `json_repair`, `asciichartpy`, `anyascii`, `pytz`, `jwt`, `sse_starlette`, `mcp`, `chardet`,
    `httpx_sse`, `httpx_retries`, `opentelemetry-exporter-prometheus`, `jsonpath-rust`, `pandas`,
    `pyarrow` or `data_designer`, except the word `pandas` in one skip-reason regex at
    `scripts/suppression-registry-gen.py:37` and the test name `test_prompt_toolkit_not_installed`].

#### ISS-073 — Dead enrichment surface left after R8 S5: hook, route and types with no renderer

`P3` · `debt` · actor `owner-decision` · status `done` · closed 2026-10-16 (see the closure note)

- **Evidence**
  - `frontend/src/hooks/useEventEnrichmentsQuery.ts` has no non-test importer other than the hooks
    barrel (grep of `frontend/src` excluding tests) [V]
  - `backend/api/routes/events.py:2268` still serves `/{event_id}/enrichments`
    (`backend/api/routes/events.py:2272` `get_event_enrichments`) [V]
  - `frontend/src/components/events/EventDetailModal.tsx:1034` keeps a tombstone comment ('R8 S5:
    the AI Enrichment Analysis block retired here') and `enrichment_data` on the type [V]
  - No component calls the hook, so nothing fetches the route at runtime: the cost is dead code and
    surface area only (verifier [A]). Ledger item 55 and the S5 guard docstring already name this
    island and deliberately leave it out of S5 [A]
- **Why it matters.** R8 turned the empty state into a deletion but left the data path in place. The
  original's 'every detail open may call an endpoint nothing displays' is false; what remains is
  dead code, a live route and a tombstone comment. Whether the response schema and generated types
  are removable as a set was not read [?].
- **World-class gap.** API surface equals rendered surface; deprecated endpoints have a dated
  removal.
- **Acceptance.** The owner confirms retirement (OD-20), then the hook, route, schema, generated
  types and tombstone comment are removed in one commit with `api.ts` and the OpenAPI types
  regenerated; grep for `useEventEnrichmentsQuery` and `/enrichments` returns nothing.
- **Depends on.** OD-20; ISS-055 (same residue family).
- **Tracked as.** Ledger item 55 and the R8 S5 guard docstring name this island and leave it out of
  S5; the R8 section of `docs/vss-integration/12-postponed-roadmap.md:108` (at `5c605e1d`) does not
  mention the hook or route.
- **Closure note — 2026-10-16 (`B3.1`/`F3.1`, PR #7220) [V].** Executed OD-20 (`ruling 241`):
  deleted `frontend/src/hooks/useEventEnrichmentsQuery.ts` and `useEventEnrichmentsQuery.test.ts`
  and its barrel re-exports in `frontend/src/hooks/index.ts`; removed `fetchEventEnrichments`,
  `EventEnrichmentsQueryParams`, and `EventEnrichmentsResponse` from `frontend/src/services/api.ts`
  and `api.test.ts`; removed `enrichment_data?: EnrichmentData` and the R8 S5 tombstone comment from
  `frontend/src/components/events/EventDetailModal.tsx`; removed `GET /api/events/{event_id}/enrichments`
  (`get_event_enrichments`), `EventEnrichmentsResponse`, and the `/api/events/{event_id}/enrichments`
  HATEOAS link in `backend/api/schemas/hateoas.py`; regenerated `docs/openapi.json` and
  `frontend/src/types/generated/api.ts` (`./scripts/validate-api-types.sh` green); and pinned
  absence in `backend/tests/unit/frontend/test_r8_s5_frontend_panel_retirement.py` and
  `backend/tests/unit/api/schemas/test_hateoas.py` (`210 passed`).
