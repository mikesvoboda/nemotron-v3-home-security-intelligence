# 4n — Alerting Design

> Step 1 of the alerting feature packages (`packages/backend.md`, "B4.\* Feature track"), copied
> from [`templates/feature-design.md`](templates/feature-design.md). One session designed the
> whole cluster, because its decisions depend on each other: what happens after a verdict.

**Packages:** `B4.1` (re-scoped), `B4.2`, `B4.3`, `F4.1`, `F4.2` · **Inventory rows:** F-050, F-078,
F-079, F-216, F-217, F-236 · **R2 ruling:** complete, priority 1 (R2a rows 1, 2, 6 and 12) · **Open
decisions settled:** OD-22 · **Designed:** 2026-10-21, with the owner

## Where it starts

Facts read at `main` `093dc3185`. Today a verdict produces three things, and nothing acts on any
of them:

- **An event row** with its score and level (`backend/services/vlm_analyzer.py:677-690`).
- **A stored notify decision.** `decide_notification`
  (`backend/services/notification_filter.py:218`) reads the global switch, each camera's
  threshold and the shared quiet hours, and upserts `event_notify_decisions`
  (`vlm_analyzer.py:973-1042`). It only paints a badge.
- **One WebSocket `event` frame** (`vlm_analyzer.py:1044-1082`), which the dashboard adds to a list.

What is dormant or half-built:

- **Alert rules** are saved but evaluated only by their Test button.
  `AlertRuleEngine.evaluate_event` (`backend/services/alert_engine.py:164`) has no production
  caller, so no `Alert` row is created.
- **Delivery.** `send_email` and `send_webhook` are called only by the settings page's test
  buttons (`backend/api/routes/notification.py:225`, `:247`); `send_push` is a stub
  (`backend/services/notification.py:539-562`); `deliver_alert` (`:633`) has no caller.
- **The browser.** `showSecurityAlert` (`frontend/src/hooks/useIntegratedNotifications.ts:225`)
  has no caller; the only `new Notification` is the settings test button.
- **The Alerts page** lists high and critical events with no `reviewed=false` filter
  (`frontend/src/hooks/useAlertsQuery.ts:155-159`), so Dismiss hides nothing.
- **Snooze** writes `events.snooze_until` (`backend/api/routes/events.py:2092-2099`); nothing reads
  it, and alerts have no snooze field.
- **Notification history** returns `[]` (`backend/api/routes/notification.py:364-419`); the table it
  names does not exist.

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

| question                                               | decision                                                                                                                                                                                                                                                                                                                 | why                                                                                             |
| ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------- |
| Which channels must work?                              | Browser (desktop notification and sound while a dashboard is open), webhook, email and Web Push. All four are offered, and each person picks theirs.                                                                                                                                                                     | "Each user would want a different notification setting."                                        |
| Whose settings are they?                               | **Shared what, personal how.** The household sets what counts as an alert: rules, arming and the master switch. A recipients list sets how and when each person is reached: their channels, their address or device, their own quiet hours. No login is needed; under `EXPOSE_LAN` a recipient may be linked to a login. | With `EXPOSE_LAN` unset the app has no login, so it cannot tell who is looking at it.           |
| How do rules and today's notify settings fit together? | **Rules are the policy.** An alert is a rule match. A fresh install ships one default rule that reproduces today's defaults. A master switch, snooze and (later) arming gate everything. `should_notify` stays the one decision function (OD-31) and asks whether a rule matched.                                        | One place decides; ruling 89 already calls the rules engine after each verdict.                 |
| What if the VLM gives no verdict?                      | A three-step chain: the local VLM, then an opt-in cloud VLM, then the detector plus the Triton specialists. In the last step a trusted household face or a known re-ID match suppresses the alert, and anything else alerts as **unverified**. Every alert records the step that decided it.                             | A VLM outage must not hide an intruder (OD-22(b)).                                              |
| Where is the cloud VLM step designed?                  | In its own Phase 4 session. This design leaves the slot and the verdict-source field.                                                                                                                                                                                                                                    | Consent, key storage, the trial terms and calibration are a feature of their own.               |
| Can a `rejected` verdict be overridden?                | By default a rejection suppresses the alert and the event stays in the timeline. A rule can be set to "alert even if the AI says no threat". The default rule keeps the suppression.                                                                                                                                     | Gives the arming session a hook without a global floor (OD-22(a)).                              |
| What does Snooze silence?                              | **The same activity:** the same camera and kind of object, for the chosen time, for the whole household.                                                                                                                                                                                                                 | The narrowest snooze that is still useful; in no-login mode a snooze cannot belong to a person. |
| Can anything break through?                            | An alert from a rule with severity critical breaks through snoozes and quiet hours. Each person can switch off critical break-through for their own quiet hours.                                                                                                                                                         | Like a phone's critical alerts getting past Do Not Disturb (OD-22(c)).                          |
| Which clock do schedules use?                          | Household local time, from `properties.timezone` (`backend/models/property.py:71`). Setup writes the host's timezone there.                                                                                                                                                                                              | Rule schedules default to UTC today and quiet hours compare naive times.                        |
| What does the Alerts page list?                        | Alert rows. Acknowledge and Dismiss set the alert's status for the household and update every open dashboard live. This replaces R2a row 6's `reviewed=false` wording.                                                                                                                                                   | The page should show what people were alerted about.                                            |
| What happens to repeats?                               | Within the rule's cooldown (default 300 s) further matches fold into the open alert (count, latest snapshot, last seen) without notifying again, unless the severity rises. After the cooldown a new alert opens.                                                                                                        | One notification per incident, louder only when it gets worse (OD-22(d)).                       |
| How is it built?                                       | A database outbox with one supervised delivery worker for email, webhook and Web Push. The browser alert goes out on the WebSocket right after commit.                                                                                                                                                                   | The owner weighed a Redis stream and inline sending; see "Approaches weighed".                  |

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
  **delivery**, **verdict source**, **activity key** (camera plus object type, what Snooze matches)
  and **break-through**.
- **Its units:**

| unit          | job                                             | interface                                                                                                                                                                                                                                                   |
| ------------- | ----------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `verdict.py`  | Walks the chain to a resolved verdict.          | `resolve(event, detections, specialists) -> ResolvedVerdict(source: local \| cloud \| detector, verdict: confirmed \| uncertain \| rejected \| None, risk_score, suppressed_by)`. The cloud step is an empty slot until its own package.                    |
| `policy.py`   | Decides which rules match. Pure: no I/O.        | `evaluate(ctx: PolicyContext) -> list[RuleMatch(rule, severity, dedup_key)]`. Checks, in order: master switch; per rule its cameras, object types, minimum confidence, schedule in household time, and verdict handling; then snooze, which critical skips. |
| `pipeline.py` | The single entry point after a verdict commits. | `AlertPipeline.process(event_id)`. One transaction: run `policy`, fold into or create alerts, write `event_notify_decisions`, plan deliveries. After commit: broadcast `alert_created` or `alert_updated`, wake the worker. Idempotent per event.           |
| `planner.py`  | Decides who is told on what, now. Pure.         | `plan(alert, recipients, now, tz) -> list[PlannedDelivery]`. Applies channels, quiet hours, break-through and each person's opt-out; a delivery skipped for quiet hours is recorded as `suppressed`.                                                        |
| `worker.py`   | Sends the outbox.                               | `NotificationDeliveryWorker`, supervised like the pipeline workers. Claims rows with `FOR UPDATE SKIP LOCKED`, sends, records each attempt, backs off 30 s, 2 min, 10 min, 30 min, then marks the row `failed`.                                             |
| `channels/`   | One adapter per external channel.               | `Channel.send(delivery, payload) -> SendResult`. `email` and `webhook` wrap today's `send_email` and `send_webhook`; `webpush` is new. Every send carries an idempotency key (a webhook header, the email `Message-ID`).                                    |

- **Its adapters:** the analyzer's post-commit step calls `AlertPipeline.process` in place of
  `_notify_decision` (`vlm_analyzer.py:973`); the recovery path (`_recover_committed_event`,
  `vlm_analyzer.py:799`) calls it too, so a recovered event is no longer skipped; a sweep every
  minute re-runs it for events committed in the last hour that have no notify decision (an older
  event would alert too late to help, so it is logged instead). `should_notify` becomes a thin
  wrapper over `policy`, so OD-31's guarded name survives. HTTP routes call the snooze, acknowledge
  and dismiss operations; the worker calls the channels.
- **Browser alerts** do not go through the outbox. A browser that turns alerts on registers as a
  device of a recipient. The `alert_created` frame lists the recipients to alert now (the planner's
  browser rows), and a tab shows the notification and plays the sound if its recipient is listed.
  Those rows are logged as `broadcast`, so history stays complete.

## What changes

### Data model, one reversible Alembic migration

New tables:

| table                     | columns                                                                                                                                                                                                | why                              |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------- |
| `recipients`              | name, enabled, `user_id` (optional link to a login), `critical_breaks_quiet` (default on)                                                                                                              | Personal how.                    |
| `recipient_channels`      | `recipient_id`, kind (`browser` \| `email` \| `webhook` \| `webpush`), target (address, URL or browser device id), push subscription keys, enabled, last success, last error                           | One recipient, several channels. |
| `notification_deliveries` | `alert_id`, `recipient_id`, `channel_id`, status (`pending` \| `sent` \| `broadcast` \| `retrying` \| `failed` \| `suppressed`), attempts, `next_attempt_at`, `last_error`, idempotency key, sent time | The outbox and F-236's history.  |
| `activity_snoozes`        | `camera_id`, `object_type`, until, the event or alert it came from                                                                                                                                     | Same-activity snooze.            |

Changed tables:

- **`alerts`:** add `verdict_source`, `match_count`, `last_seen_at`, `last_event_id`; the status
  becomes the household's handling state (`open`, `acknowledged`, `dismissed`); drop
  `delivered_at`, the never-set `DELIVERED` status and `channels`.
- **`alert_rules`:** add `alert_on_rejected`; drop `channels` (recipients choose channels) and the
  columns nothing reads: `conditions`, `dwell_time_enabled`, `dwell_threshold_seconds`,
  `exclude_household_members` and the `threat_*` fields. `zone_ids` stays, unused, until zone
  matching is designed (detections must carry a zone first).
- **`quiet_hours_periods`:** gains `recipient_id`.
- **`events`:** drops `snooze_until` (and the `is_snoozed` property); the snooze badge shows when an
  active activity snooze matches the event.
- **`event_notify_decisions`:** kept as OD-31's record; `notify` means the event created or
  escalated an alert, and `decided_by` names the rule.

Today's settings map without changing any delivered behaviour, because nothing was delivered:

| today                                                           | becomes                                                                                           |
| --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `notification_preferences.enabled`                              | The master switch.                                                                                |
| `risk_filters` (medium and above) and the camera threshold (60) | The shipped default rule: all cameras, risk at least 60.                                          |
| `camera_notification_settings`                                  | Dropped; the migration logs any camera that was not on the defaults.                              |
| Shared quiet hours                                              | Moved to a first recipient, "Household", which starts with browser alerts on.                     |
| `sound`                                                         | A setting on each browser device.                                                                 |
| `PATCH /api/notification/config` (written, never read)          | Removed. The SMTP server stays in `.env`, which setup writes; recipients hold only their address. |

The SMTP credential and the VAPID private key stay out of the database (`.env` or a secret file).
Webhook signing secrets are stored per channel the way outbound webhook secrets are; the build
PR checks that handling first.

### Files per lane

- **backend:** `backend/services/alerting/` (new); `vlm_analyzer.py` (the post-commit call and the
  recovery path); `notification_filter.py` (`should_notify` over `policy`); `alert_engine.py`
  (its rule matching moves into `policy`, the rest is deleted); `notification.py` (the senders
  behind the channel adapters); `backend/models/` (the tables above); the alert, event, notification
  and notification-preferences routes; the migration; `setup.py`/`setup_lib` writes
  `properties.timezone` and the VAPID keys (ops reviews).
- **frontend:** the Alerts page on alert rows; the timeline's Snooze; the rules dialog; Settings ›
  Notifications (recipients, this browser, history); the browser alert and sound; the
  `/notifications` page merges into Settings › Notifications and redirects.
- **ops:** the CI harness admits a mail sink and a webhook sink for the golden path (today it
  keeps only `FAKE_SERVICES`, `scripts/feature_check.py:96`, `:463`).

### Screens (Easy mode, UR-182)

- **Alerts** (`/alerts`): open alerts by default, or all. Each row: rule, severity, camera, a
  verdict badge (verified locally, verified in the cloud, unverified), first and last seen, match
  count, who was told. Actions: Acknowledge, Dismiss, Snooze (15 min, 1 h, 4 h, until tomorrow),
  Open event. Live through the existing `useAlertWebSocket`. The nav item shows the open count;
  the header badge stays for Prometheus infrastructure alerts.
- **Settings › Rules:** the dialog gains "Alert even if the AI says no threat", loses the channel
  picker, and shows schedules in household time. Test stays.
- **Settings › Notifications:** the master switch; **Recipients** (name, channels each with a Test
  button, quiet hours, critical break-through, optional login link); **This browser** ("Alert me
  here as …", sound, the notification permission and, if chosen, the Web Push subscription);
  **History**.

## Failure handling

| failure                                       | what happens                                                                                                                             |
| --------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| The pipeline throws after the event committed | The event is safe. `process()` is idempotent, and the one-minute sweep re-runs it for events from the last hour with no notify decision. |
| A channel fails                               | Backoff 30 s, 2 min, 10 min, 30 min, then `failed`. The health endpoint reports `DEGRADED` naming the channel; History shows the error.  |
| A push subscription expires (HTTP 410)        | That channel is switched off and shown so in the recipient's settings.                                                                   |
| The worker dies                               | The supervisor restarts it; pending rows wait; health reports the oldest pending delivery's age.                                         |
| A channel is misconfigured                    | Its Test button sends through the same adapter and logs a history row tagged `test`.                                                     |

## Tests

- **Consolidation scope:** `vlm_analyzer` (the post-commit step), `notification_filter`,
  `alert_engine`, `notification`, the alert, event, notification and notification-preferences
  routes and models; frontend `AlertsPage`, `useAlertsQuery`, `NotificationSettings`,
  `AlertRulesSettings` and `SnoozeButton`.
- **Tests through the interface:**
  - `policy`: table-driven, one row per decision, including ruling 139's schedule boundary on a
    fixed clock in household time (23:59:30 matches; an overnight window wraps; the instant after
    the end minute does not).
  - `planner`: quiet hours, critical break-through and the per-person opt-out.
  - The pipeline on a real database: idempotency, folding, escalation, the recovery sweep.
  - The worker with a fake channel: retry, backoff, `failed`.
  - The channel adapters against a local SMTP sink, webhook sink and push-service fake.
  - OD-31's guard stays on `should_notify`; ISS-001's "notify=true reaches a surface" becomes a
    delivery row plus an `alert_created` frame.

## Golden path

- **Spec (Playwright):** the fake VLM confirms a person; the alert appears live and the browser
  notification is captured; the webhook sink receives the payload with its idempotency key and
  History reads `sent`; Snooze 1 h holds the next matching fixture; Dismiss removes the alert from
  the open list. Two fallback cases: the VLM fails and the alert is unverified; a trusted household
  face produces no alert.
- **Fake-stack scenario:** the person fixture with a `confirmed` verdict; a failure from the fake
  VLM for the fallback case.
- **Real-tier check:** the operator runs a real verdict through to the webhook sink on a test
  deployment and records the latency from commit to delivery.

## Privacy and security

- **Stored:** recipients' names, addresses, webhook URLs and push endpoints. Under `EXPOSE_LAN`
  only logged-in users reach them, and the API never returns secrets or push keys in full.
- **What leaves the house:** email and webhook carry the title, camera, time and the VLM's summary
  text; push carries the title only; images never leave on any channel. Push payloads are
  encrypted end to end (Web Push), and the link opens the user's own dashboard.
- **Web Push needs:** HTTPS from the phone (the `EXPOSE_LAN` TLS setup), outbound access to the
  browser vendor's push service, and VAPID keys generated at setup.
- **Retention and erasure:** deliveries are pruned under the existing alert and event retention;
  expired snoozes are deleted; deleting a recipient deletes its channels and anonymises its
  history rows (OD-18, OD-19).

## Rollout and reversal

- **Fresh install:** the default rule, and the "Household" recipient with browser alerts on.
- **Upgrade:** the master switch keeps its value. Browser alerts start where nothing notified
  before; that is the feature.
- **Reversal:** the master switch stops every alert at once, and each channel can be switched off
  alone. Code reversal is a revert plus the migration's downgrade, which restores the dropped
  columns empty and says so.

## Packages

Each runs the six steps as a test-only PR, then a build PR (UR-77).

| package                                                                                                                                                                           | lane                              | covers                     | order            |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------- | -------------------------- | ---------------- |
| `B4.1` Alert pipeline core (re-scoped from "Snooze an event or alert"): `verdict`, `policy`, `pipeline`, rules after each verdict, activity snoozes, the alert changes, the sweep | backend (#7287)                   | F-050, F-079, F-216, F-217 | 1                |
| `B4.2` Recipients and delivery: recipients, channels, `planner`, the outbox worker, email and webhook, the settings migration, history                                            | backend; ops reviews the CI sinks | F-236                      | 2                |
| `F4.1` The Alerts page on alert rows: live, Acknowledge, Dismiss, Snooze                                                                                                          | frontend                          | F-078, F-079               | 2, beside `B4.2` |
| `F4.2` The rules dialog, Settings › Notifications, the browser alert and sound                                                                                                    | frontend                          | F-216, F-217, F-236        | 3                |
| `B4.3` The Web Push channel                                                                                                                                                       | backend                           | none                       | 4                |

Out of scope, with hooks left: arming and modes (the P2 arming session uses the
`alert_on_rejected` override), and the cloud VLM step (its own session).

## Done when

Every package: its golden path green on the fake stack, its real-tier check posted, and its
inventory rows set to **works**. For the cluster: a real verdict reaches a configured recipient
on each of the four channels, every attempt appears in History, and the Alerts page, Snooze and
Dismiss behave as the golden path says.
