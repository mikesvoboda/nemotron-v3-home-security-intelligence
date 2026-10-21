# 4n — Alerting Design

> Step 1 of the alerting feature packages (`packages/backend.md`, "B4.\* Feature track"), copied
> from [`templates/feature-design.md`](templates/feature-design.md). One session designed the
> whole cluster, because its decisions depend on each other: what happens after a verdict.

**Packages:** `B4.1` (re-scoped), `B4.2`, `B4.3`, `B4.5`, `F4.1`, `F4.2` · **Inventory rows:**
F-050, F-078, F-079, F-216, F-217, F-236; changed too: F-231, F-232, F-235 · **R2 ruling:**
complete, priority 1 (R2a rows 1, 2, 6 and 12) · **Open decisions settled:** OD-22 · **Designed:**
2026-10-21, with the owner · **Reviewed:** an adversarial review the same day; the owner accepted
all 13 amendments (see "Review")

## Where it starts

Facts read at `main` `093dc3185`, and the review's additions at `bc89bf68a`. Today a verdict
produces three things, and nothing acts on any of them:

- **An event row** with its score and level (`backend/services/vlm_analyzer.py:677-690`).
- **A stored notify decision.** `decide_notification`
  (`backend/services/notification_filter.py:218`) reads the global switch, the risk filters, each
  camera's switch and threshold, and the shared quiet hours (`:115-136`), and upserts
  `event_notify_decisions` (`vlm_analyzer.py:973-1042`). It only paints a badge, but the settings
  it reads are choices users made in the UI.
- **One WebSocket `event` frame** (`vlm_analyzer.py:1044-1082`), which the dashboard adds to a list.

What is dormant or half-built:

- **Alert rules** are saved but evaluated only by their Test button.
  `AlertRuleEngine.evaluate_event` (`backend/services/alert_engine.py:164`) has no production
  caller, so the pipeline creates no `Alert` row. The Test route does reach `_evaluate_rule`,
  which reads `dwell_time_enabled` and the `threat_*` fields (`alert_engine.py:512-523`).
- **A second alert API is mounted.** `/api/alert-service` (`backend/main.py:1562`) creates and
  updates alerts, accepting a `delivered` status and `channels`
  (`backend/api/routes/alert_service.py:182-194`, `:235-250`), and `AlertService.create_alert`
  fires `ALERT_FIRED` outbound webhooks (`backend/services/alert_service.py:143-146`). Nothing in
  the frontend or scripts calls it.
- **Delivery.** `send_email` and `send_webhook` are called only by the settings page's test
  buttons (`backend/api/routes/notification.py:225`, `:247`); `send_push` is a stub
  (`backend/services/notification.py:539-562`); `deliver_alert` (`:633`) has no caller. The SMTP
  client is opened without a timeout (`notification.py:278`, `:288`), and the webhook URL check
  rejects private addresses, local names such as `.local` and plain HTTP
  (`backend/core/url_validation.py:95-105`, `:246-251`, `:269-274`).
- **The browser.** `showSecurityAlert` (`frontend/src/hooks/useIntegratedNotifications.ts:225`)
  has no caller; the only `new Notification` is the settings test button.
- **The Alerts page** lists high and critical events with no `reviewed=false` filter
  (`frontend/src/hooks/useAlertsQuery.ts:155-159`), so Dismiss hides nothing.
- **Snooze** writes `events.snooze_until` (`backend/api/routes/events.py:2092-2099`); nothing reads
  it, and alerts have no snooze field.
- **Notification history** returns `[]` (`backend/api/routes/notification.py:364-419`); the table it
  names does not exist.
- **Schema changes are recorded SQL upgrades, not Alembic.** Startup runs `create_all` and then
  `backend.migrations.runner.apply_all` (`backend/core/database.py:408-421`) over the registry
  (`backend/migrations/registry.py`); there is no downgrade.
- **VLM summaries can carry names.** The specialists put "known person <name>" and "matches
  household member <name>" into the prompt (`backend/services/vlm_specialists.py:236`, `:300`),
  and the summary is stored unchanged.

## What the user can do when this is done

A person walks up the drive at night. The local VLM confirms a threat and the default rule
matches. Within a second every open dashboard shows a browser alert with a sound, and each person
on the recipients list is told on the channels they chose (email, a webhook to Home Assistant or
ntfy, or phone push), except anyone in their quiet hours, unless the alert is critical. The person
keeps moving; the new detections fold into the same alert and nobody gets another message. The
user opens Alerts and sees which rule fired, whether the AI verified it (locally, in the cloud,
or unverified) and who was told, then snoozes the activity for an hour or dismisses it. Settings ›
Notifications › History shows every delivery attempt and its outcome.

## Decisions

| question                                                      | decision                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | why                                                                                                                                                                                                 |
| ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Which channels must work?                                     | Browser (desktop notification and sound while a dashboard is open), webhook, email and Web Push. All four are offered, and each person picks theirs.                                                                                                                                                                                                                                                                                                                                                         | "Each user would want a different notification setting."                                                                                                                                            |
| Whose settings are they?                                      | **Shared what, personal how.** The household sets what counts as an alert: rules, arming and the master switch. A recipients list sets how and when each person is reached: their channels, their address or device, their own quiet hours. No login is needed; under `EXPOSE_LAN` a recipient may be linked to a login.                                                                                                                                                                                     | With `EXPOSE_LAN` unset the app has no login, so it cannot tell who is looking at it.                                                                                                               |
| How do rules and today's notify settings fit together?        | **Rules are the policy.** An alert is a rule match. A master switch, snooze and (later) arming gate everything. `should_notify` stays the one decision function (OD-31) and asks whether a rule matched.                                                                                                                                                                                                                                                                                                     | One place decides; ruling 89 already calls the rules engine after each verdict.                                                                                                                     |
| What happens to today's per-camera settings and risk filters? | They become rules, not a log line. Until the contract package, the default rule uses each camera's saved threshold (60 when none) and skips a disabled camera; the contract upgrade then writes equivalent rules and archives the originals (F6).                                                                                                                                                                                                                                                            | They are choices users made; a disabled camera must not start alerting.                                                                                                                             |
| What if the VLM gives no verdict?                             | A three-step chain: the local VLM, then an opt-in cloud VLM, then the detector plus the Triton specialists. In the detector step a rule's minimum risk does not apply; today's detector rule replaces it (a person or vehicle at or above `detection_confidence_threshold`, `notification_filter.py:146-164`) (F2). Every alert records the step that decided it.                                                                                                                                            | A VLM outage must not hide an intruder (OD-22(b)).                                                                                                                                                  |
| When does a recognised person suppress the alert?             | Only when no face is unknown and trusted matches cover every person detected. A trusted match is a face match to a known person marked household, or a re-ID match to a household member with full trust. A match to a non-household or auto-enrolled person, or to a member with partial or monitor trust, leaves the alert unverified, and the alert names who was recognised. `suppressed_by` records the person and the leg. Photo spoofing is an accepted residual risk, shared with the VLM path (F1). | Similarity is not identity; a mixed group must not be silenced because one person is known.                                                                                                         |
| Where is the cloud VLM step designed?                         | In its own Phase 4 session. This design leaves the slot and the verdict-source field.                                                                                                                                                                                                                                                                                                                                                                                                                        | Consent, key storage, the trial terms and calibration are a feature of their own.                                                                                                                   |
| Can a `rejected` verdict be overridden?                       | By default a rejection suppresses the alert and the event stays in the timeline. A rule can be set to "alert even if the AI says no threat". The default rule keeps the suppression.                                                                                                                                                                                                                                                                                                                         | Gives the arming session a hook without a global floor (OD-22(a)).                                                                                                                                  |
| What does Snooze silence?                                     | **The same activity:** the same camera and kind of object, for the chosen time, for the whole household.                                                                                                                                                                                                                                                                                                                                                                                                     | The narrowest snooze that is still useful; detections carry no track or entity id the pipeline writes (`Detection.track_id` is never set), and in no-login mode a snooze cannot belong to a person. |
| How severe is an alert?                                       | The higher of the rule's severity and the event's risk level from `SeverityService`; a detector-sourced alert takes the rule's severity (F5).                                                                                                                                                                                                                                                                                                                                                                | A fixed rule severity could never escalate.                                                                                                                                                         |
| Can anything break through?                                   | An alert whose severity is critical breaks through snoozes and quiet hours. Each person can switch off critical break-through for their own quiet hours.                                                                                                                                                                                                                                                                                                                                                     | Like a phone's critical alerts getting past Do Not Disturb (OD-22(c)).                                                                                                                              |
| Which clock do schedules use?                                 | Household local time, from `properties.timezone` (`backend/models/property.py:71`). Setup writes the host's timezone there.                                                                                                                                                                                                                                                                                                                                                                                  | Rule schedules default to UTC today and quiet hours compare naive times.                                                                                                                            |
| What does the Alerts page list?                               | Alert rows. Acknowledge and Dismiss set the alert's status for the household and update every open dashboard live. This replaces R2a row 6's `reviewed=false` wording.                                                                                                                                                                                                                                                                                                                                       | The page should show what people were alerted about.                                                                                                                                                |
| What happens to repeats?                                      | Within the rule's cooldown (default 300 s) further matches fold into the open alert (count, latest snapshot, last seen) without notifying again, unless the alert's severity rises. After the cooldown a new alert opens.                                                                                                                                                                                                                                                                                    | One notification per incident, louder only when it gets worse (OD-22(d)).                                                                                                                           |
| What about the rules' threat condition?                       | `threat_*` stays and `policy` evaluates it; OD-7 part 1 (ruling 89) owns it (F7).                                                                                                                                                                                                                                                                                                                                                                                                                            | Dropping it would reverse an owner ruling.                                                                                                                                                          |
| How is it built?                                              | A database outbox with one supervised delivery worker for email, webhook and Web Push. The browser alert is published on the WebSocket right after commit, with its delivery rows in the outbox so the worker can republish one that never went out (F3).                                                                                                                                                                                                                                                    | The owner weighed a Redis stream and inline sending; see "Approaches weighed".                                                                                                                      |

### Approaches weighed

- **Database outbox (chosen).** The alert and its pending deliveries are written in one
  transaction, survive a restart, retry with backoff, and the delivery table is F-236's history.
  Costs: a poll interval unless the worker is woken (it is), at-least-once delivery (each send
  carries an idempotency key), and a retention prune.
- **Redis stream.** Push-based and decoupled, but the verdict commits in Postgres while the
  publish goes to Redis, so a crash between them loses the alert unless an outbox is added; Redis
  has no delayed retry; history still needs a Postgres table. Made reliable, it is the outbox plus
  a Redis hop.
- **Inline sending.** The fewest parts, but a slow SMTP server stalls the analyzer, a restart loses
  sends in flight, and there are no retries.

## Shape

- **The module behind the seam:** `backend/services/alerting/`. Domain terms, added to
  `docs/reference/glossary.md` in the build PR: **alert**, **rule**, **recipient**, **channel**,
  **delivery**, **verdict source**, **activity key** (camera plus object type, what Snooze matches),
  **effective severity** and **break-through**.
- **Its units:**

| unit          | job                                             | interface                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| ------------- | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `verdict.py`  | Walks the chain to a resolved verdict.          | `resolve(event, detections, specialists) -> ResolvedVerdict(source: local \| cloud \| detector, verdict: confirmed \| uncertain \| rejected \| None, risk_score, recognised, suppressed_by)`. Applies the suppression rule above. The cloud step is an empty slot until its own package.                                                                                                                                                                                                                                                                                        |
| `policy.py`   | Decides which rules match. Pure: no I/O.        | `evaluate(ctx: PolicyContext) -> list[RuleMatch(rule, effective_severity, dedup_key)]`. Checks, in order: master switch; per rule its cameras, object types, minimum confidence, threat condition, schedule in household time, and verdict handling (the minimum risk for VLM verdicts, the detector rule for detector ones); then snooze, which a critical effective severity skips. `PolicyContext` carries the face check's result (trusted or unknown) as an input a later rule can match.                                                                                  |
| `pipeline.py` | The single entry point after a verdict commits. | `AlertPipeline.process(event_id)`. One transaction: run `policy`; for each match, take `pg_advisory_xact_lock` on (rule id, activity key) in sorted order (F10), then fold into or create the alert; write `event_notify_decisions`; plan deliveries, browser rows `pending`. After commit: publish `alert_created` or `alert_updated`, mark the browser rows `broadcast` once the publish returns, and wake the worker. Idempotent per event.                                                                                                                                  |
| `planner.py`  | Decides who is told on what, now. Pure.         | `plan(alert, recipients, now, tz) -> list[PlannedDelivery]`. Applies channels, quiet hours, break-through and each person's opt-out; a delivery skipped for quiet hours is recorded as `suppressed`.                                                                                                                                                                                                                                                                                                                                                                            |
| `worker.py`   | Sends the outbox.                               | `NotificationDeliveryWorker`, supervised like the pipeline workers. Claiming is a lease: a short transaction selects due rows `FOR UPDATE SKIP LOCKED`, increments `attempts`, moves `next_attempt_at` 2 minutes out and commits. The send runs outside any transaction under a per-channel `asyncio.timeout`, concurrently with a small per-channel limit; a send that dies becomes due again when its lease ends. Backoff 30 s, 2 min, 10 min, 30 min, then `failed`. Browser rows still `pending` after 15 s are republished, and marked `expired` after 5 minutes (F3, F9). |
| `channels/`   | One adapter per external channel.               | `Channel.send(delivery, payload) -> SendResult`. `email` wraps `send_email` and passes `timeout=` to `smtplib.SMTP`; `webhook` signs with the `X-Webhook-Signature: sha256=…` HMAC convention F-246 uses and checks its URL against the shared policy in `url_validation.py` (F12); `webpush` is new. Every send carries an idempotency key (a webhook header, the email `Message-ID`).                                                                                                                                                                                         |

- **Its adapters:**
  - the analyzer's post-commit step calls `AlertPipeline.process` in place of `_notify_decision`
    (`vlm_analyzer.py:973`), and so do both idempotency-hit paths (`vlm_analyzer.py:469-482`),
    which today return before any notify step (F4);
  - the recovery path (`_recover_committed_event`, `vlm_analyzer.py:799`) calls it, so a recovered
    event is no longer skipped;
  - a sweep every minute re-runs it for every event with no notify decision whose verification
    was written after the alerting upgrade ran (`event_verifications.created_at`, oldest first,
    paged). For an event more than an hour old the alert is still created or folded, but its
    deliveries are recorded `expired` instead of sent (F4);
  - `should_notify` becomes a thin wrapper over `policy`, so OD-31's guarded name survives;
  - HTTP routes call the snooze, acknowledge and dismiss operations; the rule Test route runs
    `policy`; the worker calls the channels.
- **Browser alerts.** A browser that turns alerts on registers as a device of a recipient. The
  `alert_created` frame lists the recipients to alert now (the planner's browser rows). A tab shows
  the notification and plays the sound if its recipient is listed, using the alert id as the
  notification `tag` so a republished frame alerts once. In History, `broadcast` means published
  to open dashboards, not seen.

## What changes

### Data model, recorded schema upgrades

New tables come from `create_all`. Each package registers one recorded upgrade
(`docs/api/migrations/*.sql`, an entry in `backend/migrations/registry.py` and a check) for its
column changes, data moves and drops. There is no downgrade: a recorded upgrade is never removed,
and undoing a schema change is a new forward upgrade. Packages before the contract package only
add, with nullable columns or server defaults, so the previous release keeps working (F8, F11).

New tables:

| table                     | columns                                                                                                                                                                                                                                   | why                              |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------- |
| `recipients`              | name, enabled, `user_id` (optional link to a login), `critical_breaks_quiet` (default on)                                                                                                                                                 | Personal how.                    |
| `recipient_channels`      | `recipient_id`, kind (`browser` \| `email` \| `webhook` \| `webpush`), target (address, URL or browser device id), push subscription keys, `on_local_network` (webhook), `include_names` (default off), enabled, last success, last error | One recipient, several channels. |
| `notification_deliveries` | `alert_id`, `recipient_id`, `channel_id`, status (`pending` \| `sent` \| `broadcast` \| `retrying` \| `failed` \| `suppressed` \| `expired`), attempts, `next_attempt_at`, `last_error`, idempotency key, sent time                       | The outbox and F-236's history.  |
| `activity_snoozes`        | `camera_id`, `object_type`, until, the event or alert it came from                                                                                                                                                                        | Same-activity snooze.            |

Changed tables:

- **`alerts`:** add `verdict_source`, `match_count`, `last_seen_at`, `last_event_id`. The status
  becomes the household's handling state (`open`, `acknowledged`, `dismissed`); existing `pending`
  and `delivered` rows become `open`. The contract package drops `delivered_at`, `channels` and the
  `delivered` value, converting the native enum to a column the way upgrade 0011 does.
- **`alert_rules`:** add `alert_on_rejected` and `excluded_camera_ids`. `threat_*` stays. The
  contract package drops `channels` (recipients choose channels), `conditions`,
  `dwell_time_enabled`, `dwell_threshold_seconds` and `exclude_household_members`. `zone_ids` stays,
  unused, until zone matching is designed (detections must carry a zone first).
- **`quiet_hours_periods`:** gains `recipient_id`, nullable until the contract package.
- **`events`:** the contract package drops `snooze_until` (and the `is_snoozed` property); until
  then the old `snooze_until` write also writes an activity snooze, and the snooze badge shows when
  an active activity snooze matches the event.
- **`event_notify_decisions`:** kept as OD-31's record; `notify` means the event created or
  escalated an alert, and `decided_by` names the rule.

Today's settings carry over as policy:

| today                                                  | becomes                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| ------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `notification_preferences.enabled`                     | The master switch.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| `risk_filters` and the per-camera switch and threshold | Until the contract package, the default rule reads them. The contract upgrade then writes rules: the default rule stays all-cameras, with `excluded_camera_ids` listing disabled cameras and cameras with a higher threshold; each lower custom threshold becomes its own rule; a stricter `risk_filters` raises a rule's threshold. The original rows are copied to `legacy_notification_settings`, and an upgrade test seeds non-default rows (F6). The severity bands come from settings SQL cannot read, so this step runs as a Python data step registered with the upgrade. |
| Shared quiet hours                                     | Owned by a first recipient, "Household", which starts with browser alerts on.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `sound`                                                | A setting on each browser device.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| `PATCH /api/notification/config` (written, never read) | Removed in the contract package. The SMTP server stays in `.env`, which setup writes; recipients hold only their address.                                                                                                                                                                                                                                                                                                                                                                                                                                                         |

The SMTP credential and the VAPID private key stay out of the database (`.env` or a secret file).
Webhook signing secrets are generated per channel and must not be stored in plain text; `B4.2`'s
PR names the mechanism, or asks the owner if the app has none. F-246's plain columns are not the
precedent.

### Files per lane

- **backend:** `backend/services/alerting/` (new); `vlm_analyzer.py` (the post-commit call, both
  idempotency-hit paths and the recovery path); `notification_filter.py` (`should_notify` over
  `policy`); `alert_engine.py` (its rule matching moves into `policy`; the contract package deletes
  the rest); `notification.py` (the senders behind the channel adapters, with timeouts);
  `url_validation.py` (the shared URL policy and the local-network flag); `routes/alert_service.py`,
  its schemas, `AlertService` and the `alerts.py` instance routes move to the new statuses, with
  `channels` accepted but ignored until the contract package; pipeline alerts do not fire
  `ALERT_FIRED` outbound webhooks unless the owner rules otherwise; `backend/models/`; the alert,
  event, notification and notification-preferences routes; the recorded upgrades; `setup.py` and
  `setup_lib` write `properties.timezone` and the VAPID keys (ops reviews).
- **frontend:** the Alerts page on alert rows; the timeline's Snooze; the rules dialog; Settings ›
  Notifications (recipients, this browser, history); the browser alert and sound; the
  `/notifications` page merges into Settings › Notifications and redirects; the golden specs this
  replaces (`alert-rules.spec.ts`, `alerts.spec.ts`, `notify.spec.ts`, `quiet-hours.spec.ts` and
  the snooze steps in `event-detail-modal.spec.ts`) are rewritten in the package that replaces
  their UI.
- **ops:** the CI harness admits a mail sink and a webhook sink for the golden path (today it
  keeps only `FAKE_SERVICES`, `scripts/feature_check.py:96`, `:463`); the CI webhook sink is marked
  "on this network".

### Screens (Easy mode, UR-182)

- **Alerts** (`/alerts`): open alerts by default, or all. Each row: rule, severity, camera, a
  verdict badge (verified locally, verified in the cloud, unverified), who was recognised, first
  and last seen, match count, who was told. Actions: Acknowledge, Dismiss, Snooze (15 min, 1 h,
  4 h, until tomorrow), Open event. Live through the existing `useAlertWebSocket`. The nav item
  shows the open count; the header badge stays for Prometheus infrastructure alerts.
- **Settings › Rules:** the dialog gains "Alert even if the AI says no threat" and the excluded
  cameras, loses the channel picker, and shows schedules in household time. Test stays.
- **Settings › Notifications:** the master switch; **Recipients** (name, channels each with a Test
  button, "include names" and, for a webhook, "on this network", quiet hours, critical
  break-through, optional login link); **This browser** ("Alert me here as …", sound, the
  notification permission and, if chosen, the Web Push subscription); **History**.

## Failure handling

| failure                                                 | what happens                                                                                                                                                                                                                                                                |
| ------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| The pipeline throws after the event committed           | The event is safe. `process()` is idempotent and runs on both idempotency-hit paths; the one-minute sweep re-runs it for every event without a notify decision, with no age cutoff for creating the alert; deliveries for an event over an hour old are recorded `expired`. |
| The process dies between commit and the browser publish | The browser rows are still `pending`; the worker republishes them after 15 s, and the tab's notification `tag` keeps it to one alert.                                                                                                                                       |
| Two events for one activity arrive together             | The advisory lock on (rule id, activity key) serialises them: one alert, `match_count` 2.                                                                                                                                                                                   |
| A channel fails                                         | Backoff 30 s, 2 min, 10 min, 30 min, then `failed`. The health endpoint reports `DEGRADED` naming the channel; History shows the error.                                                                                                                                     |
| A channel hangs (an SMTP server that never answers)     | The per-channel timeout ends the attempt, and the lease returns the row; other channels keep sending.                                                                                                                                                                       |
| A push subscription expires (HTTP 410)                  | That channel is switched off and shown so in the recipient's settings.                                                                                                                                                                                                      |
| The worker dies                                         | The supervisor restarts it; leased rows become due when their lease ends; health reports the oldest pending delivery's age.                                                                                                                                                 |
| A channel is misconfigured                              | Its Test button sends through the same adapter and logs a history row tagged `test`.                                                                                                                                                                                        |

## Tests

- **Consolidation scope:** `vlm_analyzer` (the post-commit step and the idempotency paths),
  `notification_filter`, `alert_engine`, `alert_service` and its routes, `notification`,
  `url_validation`, the alert, event, notification and notification-preferences routes and models;
  frontend `AlertsPage`, `useAlertsQuery`, `NotificationSettings`, `AlertRulesSettings` and
  `SnoozeButton`.
- **Tests through the interface:**
  - `policy`: table-driven, one row per decision, including ruling 139's schedule boundary on a
    fixed clock in household time (23:59:30 matches; an overnight window wraps; the instant after
    the end minute does not); a detector-sourced verdict with a NULL score matching the shipped
    default rule; effective severity from the event's risk level; the threat condition.
  - `verdict`: a mixed group with one household face stays unverified; an auto-enrolled stranger's
    match stays unverified; full coverage by trusted matches suppresses.
  - `planner`: quiet hours, critical break-through and the per-person opt-out.
  - The pipeline on a real database: idempotency, folding, escalation, two simultaneous events for
    one activity (one alert, `match_count` 2), a crash between commit and publish (republished
    once), the idempotency-hit paths and the sweep.
  - The worker: retry, backoff and `failed` with a fake channel; an SMTP sink that accepts and never
    answers; a kill mid-send; two concurrent claimers.
  - The channel adapters against a local SMTP sink, a webhook sink on a private address marked "on
    this network", and a push-service fake; a summary containing a household name is redacted
    unless "include names" is on; email bodies are HTML-escaped.
  - The contract upgrade on a populated database with non-default camera settings, through the
    upgrade-path pattern of `test_schema_upgrade_path.py`.
  - OD-31's guard stays on `should_notify`; ISS-001's "notify=true reaches a surface" becomes a
    delivery row plus an `alert_created` frame.

## Golden path

- **Per package** (see "Packages"); every package keeps the existing golden specs green or
  rewrites the spec for the UI it replaces, and nothing is dropped before `B4.5`.
- **The cluster (Playwright, at `F4.2`):** the fake VLM confirms a person; the alert appears live
  and the browser notification is captured; the webhook sink receives the payload with its
  idempotency key and History reads `sent`; Snooze 1 h holds the next matching fixture; Dismiss
  removes the alert from the open list. Two fallback cases: the VLM fails and the alert is
  unverified; a trusted household face covering the only person produces no alert.
- **Fake-stack scenario:** the person fixture with a `confirmed` verdict; a failure from the fake
  VLM for the fallback case.
- **Real-tier check:** the operator runs a real verdict through to the webhook sink on a test
  deployment and records the latency from commit to delivery.

## Privacy and security

- **Stored:** recipients' names, addresses, webhook URLs and push endpoints. Under `EXPOSE_LAN`
  only logged-in users reach them, and the API never returns secrets or push keys in full.
- **What leaves the house:** email and webhook carry the title, camera, time and the VLM's summary
  text; push carries the title only; images never leave on any channel. Before a summary leaves,
  every gallery name (known people, household members, vehicle owners) becomes "a known person",
  unless the channel's "include names" switch is on (ISS-048). Email bodies are HTML-escaped. Push
  payloads are encrypted end to end (Web Push), and the link opens the user's own dashboard.
- **Local webhooks:** a webhook channel marked "on this network" (by the household, or under
  `EXPOSE_LAN` by a logged-in user) may use private and unique-local addresses, local names and
  HTTP, for that channel only. Metadata addresses and link-local stay blocked for every channel,
  and the resolved address is checked at send time and the connection pinned to it (F12).
- **Web Push needs:** HTTPS from the phone (the `EXPOSE_LAN` TLS setup), outbound access to the
  browser vendor's push service, and VAPID keys generated at setup.
- **Retention and erasure:** deliveries are pruned under the existing alert and event retention;
  expired snoozes are deleted; deleting a recipient deletes its channels and anonymises its
  history rows (OD-18, OD-19). Erasure cannot recall a message already sent, and the settings page
  says so.

## Rollout and reversal

- **Fresh install:** the default rule, and the "Household" recipient with browser alerts on.
- **Upgrade:** the master switch keeps its value, and existing camera settings keep their effect.
  Browser alerts start where nothing notified before; that is the feature.
- **Reversal:** the master switch stops every alert at once, and each channel can be switched off
  alone. Code reversal before `B4.5` is a revert; the recorded upgrades stay, and their columns
  are additive. After `B4.5`, undoing it is a new forward upgrade from
  `legacy_notification_settings` and the archived columns.

## Packages

Expand first, contract last. Each runs the six steps as a test-only PR, then a build PR (UR-77),
and each has its own golden path.

| order            | package                                                                | lane                              | contents                                                                                                                                                                                                                                                                                                                                                                                                                            | its own golden path                                                                                                                                                                                            |
| ---------------- | ---------------------------------------------------------------------- | --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1                | `B4.1` Alert pipeline core (re-scoped from "Snooze an event or alert") | backend (#7287)                   | `verdict`, `policy`, `pipeline` with a planner hook that plans nothing yet; the idempotency-path, recovery and sweep calls; the default rule reading today's camera settings; activity snoozes (the old `snooze_until` write also writes one); the new alert columns and `open` status; the alert-service and alert routes on the new statuses; the Test route on `policy`; an additive upgrade. Covers F-050, F-079, F-216, F-217. | Backend pytest: confirmed gives an alert row and an `alert_created` frame; repeats fold; snooze holds; VLM failure gives unverified; a trusted face covering everyone gives no alert; rejected gives no alert. |
| 2                | `B4.2` Recipients and delivery                                         | backend; ops reviews the CI sinks | Recipients, channels, the outbox, `planner`, the worker, email and webhook, the local-network flag, name redaction; "Household" owns the existing quiet hours; history; browser rows; rule `channels` stored but ignored; an additive upgrade. Covers F-236, F-232.                                                                                                                                                                 | Backend pytest: the webhook sink gets the payload and idempotency key, History reads `sent`; retry ends `failed`; quiet hours give `suppressed`; critical breaks through.                                      |
| 2, beside `B4.2` | `F4.1` The Alerts page                                                 | frontend                          | Alert rows; Acknowledge, Dismiss, Snooze; the timeline's Snooze moves to activity snoozes; rewrites `alerts.spec.ts` and the snooze steps in `event-detail-modal.spec.ts`. Covers F-078, F-079.                                                                                                                                                                                                                                     | Playwright: the alert appears live, then acknowledge, dismiss, snooze.                                                                                                                                         |
| 3                | `B4.3` The Web Push channel                                            | backend                           | VAPID, the push adapter, the subscription API, expired-subscription handling.                                                                                                                                                                                                                                                                                                                                                       | Backend pytest against a push-service fake.                                                                                                                                                                    |
| 4                | `F4.2` The rules dialog and Settings › Notifications                   | frontend                          | As designed, including the push subscription; rewrites the channel checks in `alert-rules.spec.ts` and the UI steps in `notify.spec.ts` and `quiet-hours.spec.ts`. Covers F-216, F-217, F-231, F-232, F-235, F-236.                                                                                                                                                                                                                 | Playwright: the cluster's golden path.                                                                                                                                                                         |
| 5                | `B4.5` Contract                                                        | backend                           | The contract upgrade: translate camera settings into rules and archive the originals; drop the old columns, the `delivered` value and `camera_notification_settings` (`threat_*` stays); remove the camera routes, `PATCH /api/notification/config`, the compatibility code and the rest of `alert_engine`; remove the camera-API steps in `notify.spec.ts`.                                                                        | An upgrade-path test on a populated database with non-default rows, with `F4.2`'s golden path still green.                                                                                                     |

`B4.4` is Trash's (`4n-trash.md`).

**Out of scope, with hooks left:**

- arming and modes (the P2 arming session uses the `alert_on_rejected` override);
- the cloud VLM step (its own session);
- F-284's stranger toasts, which stay a live feed on the Face recognition page and notify no
  recipient; an unknown face reaches alerts only as a `PolicyContext` input a rule can match;
- F-246's outbound webhooks: recipient webhooks do not reuse them. Its missing URL check and its
  retries that never run (`backend/services/webhook_service.py:454`) are a separate bug.

## Review

An adversarial review of this design and three fresh-context checks of it (2026-10-21) found 13
issues; every code claim held at `origin/main`. The owner accepted all 13 amendments, which the
sections above carry:

| #   | finding                                                         | amendment                                                                                                                        |
| --- | --------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| F1  | Biometric similarity cannot authorise suppression               | Suppress only when trusted matches cover every person; non-household, auto-enrolled, partial and monitor matches stay unverified |
| F2  | The default rule's minimum risk rejects the NULL-score fallback | The detector rule replaces the risk condition for detector verdicts                                                              |
| F3  | The browser publish could be lost in a crash                    | Browser rows in the outbox, republished after 15 s, expired after 5 minutes, de-duplicated by alert id                           |
| F4  | The one-hour sweep could drop alerts                            | Process on both idempotency-hit paths; no cutoff for creating alerts; stale deliveries `expired`                                 |
| F5  | Fixed rule severity could never escalate                        | Effective severity is the higher of the rule's and the event's                                                                   |
| F6  | Dropping camera settings silently changes policy                | Translate them into rules and archive the originals                                                                              |
| F7  | The dropped fields have live readers and writers                | Bring `/api/alert-service` into scope and keep `threat_*` (OD-7 part 1)                                                          |
| F8  | There is no Alembic on the upgrade path                         | Recorded SQL upgrades, no downgrade                                                                                              |
| F9  | A hung SMTP send could stall the worker                         | Leases, per-channel timeouts, concurrent sends                                                                                   |
| F10 | Folding was not serialised                                      | An advisory lock per rule and activity                                                                                           |
| F11 | The packages could not land one by one                          | Expand then contract, with `B4.5` last                                                                                           |
| F12 | The webhook adapter rejects local destinations                  | A per-channel "on this network" flag with address pinning                                                                        |
| F13 | Summaries can carry names out of the house                      | Redact gallery names by default; HTML-escape email                                                                               |

## Done when

Every package: its golden path green on the fake stack, its real-tier check posted, and its
inventory rows set to **works**. For the cluster: a real verdict reaches a configured recipient
on each of the four channels, every attempt appears in History, and the Alerts page, Snooze and
Dismiss behave as the golden path says.
