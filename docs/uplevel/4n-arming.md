# 4n — Arming Design

> Step 1 of the Arming feature packages (`packages/backend.md`, "B4.\* Feature track",
> "**Arming (UR-12)**"), copied from [`templates/feature-design.md`](templates/feature-design.md).

**Packages:** `B4.7`, `B4.8`, `F4.5` · **Inventory rows:** F-290, F-291 · **R2 ruling:** complete,
priority 2 (R2a rows 7 and 8; ruling 89; UR-12) · **Designed:** 2026-10-21, with the owner ·
**Builds on:** [`4n-alerting.md`](4n-alerting.md) (the policy this design gates)

## Where it starts

Facts read at `main` `23030f252`.

- **The inbound webhooks are stubs.** `/api/webhooks/inbound/alert`, `/arm`, `/disarm` and `/mode`
  (`backend/api/routes/inbound_webhooks.py:55`) each log and answer 501 (`:190-192`), behind
  `X-API-Key` (`backend/api/middleware/auth.py:315-372`) and the `EXPOSE_LAN` gate. Their payloads
  carry two vocabularies: arm modes `full`, `perimeter`, `instant`, and system modes `home`,
  `away`, `night`, `disarmed`.
- **The MQTT command handler only logs, and never starts.**
  `backend/services/mqtt_command_handler.py` subscribes to zone arm/disarm, camera sensitivity and
  PTZ, alert ack and system mode (`:290-297`), logs each with `success=True`, and keeps the mode in
  memory (`:518-519`). Nothing in `backend/main.py` starts it; it ships only through
  `scripts/reachability/keep.toml:26-32` ("F-291, R2a row 8"). It reads part 1 of
  `commands/zones/{id}/arm` as the id (`:378`), which is `zones`. Its `require_auth`,
  `auth_token` and `rate_limit_per_minute` (`:100-120`) are never checked. Two configs never meet:
  the `MQTT_*` settings (prefix `hsi`) and the `mqtt_config`
  setting (`backend/api/routes/mqtt_config.py:48`, prefix `home-security`).
- **No arm or mode state is stored anywhere,** and the frontend has no arming control.
- **Detections and events carry no zone,** so nothing can be gated by zone; `4n-alerting.md`
  leaves `alert_rules.zone_ids` unused for the same reason.
- **Camera sensitivity has no reader.** `cameras.motion_sensitivity`
  (`backend/models/camera.py:132`) can be set, and nothing reads it. **PTZ works** through
  `OnvifService.execute_ptz_command` (`backend/services/onvif_service.py:347`).
- **An event needs a camera** (`backend/models/event.py:55`), and an alert needs an event
  (`backend/models/alert.py:93`).

## What the user can do when this is done

The household sees its mode in the header (Home, Away, Night or Disarmed) and switches it with one
tap, or Home Assistant switches it through a webhook or MQTT, or a weekly schedule does. Out of the
box every camera is armed in every mode except Disarmed, so nothing changes until the household
chooses, for example, to leave the indoor cameras out of Home. An unarmed camera still records and
analyses; it just cannot raise an alert, unless the alert is critical. Every change of mode is
listed with who or what made it.

## Decisions

| question                                                      | decision                                                                                                                                                                                                               | why                                                                                                      |
| ------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| What does arming gate?                                        | Alert creation. Analysis and the timeline run in every mode; the arm state decides whether an event may become an alert. Notifications follow alerts as `4n-alerting.md` designs them.                                 | History stays complete, and the Alerts page means "what needed attention while armed".                   |
| How much arming does the product have?                        | Always armed by default. Modes exist for households that need them, typically to leave indoor cameras out while home.                                                                                                  | Face suppression, rule schedules and snooze cover most time at home; modes cover what they cannot.       |
| What is a mode?                                               | One of four fixed modes, Home, Away, Night and Disarmed, each the set of cameras it arms. A mode stores the cameras it leaves out, so a new camera is armed in Home, Away and Night; Disarmed leaves out every camera. | Rules stay as designed: an alert can come only from a rule's cameras that the mode arms.                 |
| Does a critical alert respect the mode?                       | No. An alert whose effective severity is critical is created from any camera in any mode, Disarmed included, and is marked "raised while unarmed". Each person's quiet-hours opt-out still applies to delivery.        | Like a smoke alarm that is never off.                                                                    |
| Are zones armed?                                              | Not yet. Modes arm cameras. A zone command answers "zones are not supported yet" until a later package makes detections carry a zone, which also unlocks rules' `zone_ids`.                                            | Nothing carries a zone to gate on; a half-behaviour would mislead.                                       |
| How does the mode change?                                     | From the app, the webhooks and MQTT, and an optional weekly schedule in the household's time zone. A manual, webhook or MQTT change holds until the next scheduled entry.                                              | Night is only useful if it happens without a habit or an integration.                                    |
| How do modes relate to rule schedules and quiet hours?        | Each keeps its own job: the mode decides which cameras may alert, a rule's schedule when that rule applies, quiet hours when a person is pushed (OD-22 as `4n-alerting.md` settles it).                                | Three questions, three places to look.                                                                   |
| Can a rule alert on a "no threat" verdict only in some modes? | Yes. The rule's override reads "Never", "In chosen modes" or "Always". The default rule stays "Never".                                                                                                                 | While away, any person may matter even when the VLM judges it benign.                                    |
| What does the `/alert` webhook do?                            | It creates an external event on the camera the payload names (a door sensor names the door camera), and an alert if that camera is armed or the severity is critical. No camera named is a 422.                        | Modes, snooze, recipients and the footage around it all apply, like any event.                           |
| Which MQTT commands are built?                                | Mode, arm and disarm (they switch the household mode), alert acknowledge and PTZ. Sensitivity is retired from MQTT.                                                                                                    | Nothing reads sensitivity; giving it meaning is a detection feature for later. Narrows ruling 89 by one. |
| How does MQTT start and authenticate?                         | It starts only when enabled in Settings › Arming. The broker uses its username, password and TLS, and every command also carries the household's command token. Commands are rate-limited, de-duplicated and audited.  | On a home LAN the broker is often open; without the token anyone on it could disarm the house.           |
| Where is the mode seen and changed?                           | A chip in the header on every page, and Settings › Arming for the cameras per mode, the schedule, MQTT and its token, and the change history.                                                                          | The mode is the one state worth seeing everywhere.                                                       |
| What is stored and audited?                                   | The current mode with its source, the exclusions, the schedule, and every change (from, to, source kind and name, time), kept 365 days.                                                                                | "Who disarmed the house" must have an answer.                                                            |

## Approaches weighed

| approach                                 | for                                                                                                            | against                                                                                        |
| ---------------------------------------- | -------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| **A. Arming as a policy input** (chosen) | One place decides alert creation; arming tests alone; thin adapters (UR-12); the decision record names arming. | The policy depends on one more module (a cached read per event).                               |
| B. A filter in front of the pipeline     | No policy change.                                                                                              | Effective severity is known only inside the policy; the override cannot live there; no record. |
| C. Modes rewrite rules                   | No policy or pipeline change.                                                                                  | Overwrites what the household set; races with edits; a confusing audit.                        |
| D. Gate delivery                         | Smallest.                                                                                                      | Ruled out: arming gates alert creation.                                                        |

## Shape

- **The module behind the seam:** `backend/services/arming.py`. Domain terms, added to
  `docs/reference/glossary.md`: **mode**, **armed camera**, **raised while unarmed**.
- **Its interface:**
  - `mode_at(t) -> Mode`, from the change log, so an event is judged by the mode at its start, as
    the recovery and sweep paths need;
  - `is_armed(camera_id, at) -> bool`;
  - `set_mode(mode, source) -> Change`, serialised by a row lock on `arming_state`;
  - `next_scheduled() -> (time, mode) | None`.
- **How the policy uses it** (`4n-alerting.md`'s `policy.evaluate`): `PolicyContext` gains `mode`
  and `armed`. A rule match on an unarmed camera survives only when its effective severity is
  critical, and the alert is marked `raised_while_unarmed`. A `rejected` verdict matches only when
  the rule's override covers the mode. When arming is the reason no alert was created, the event's
  notify decision says so ("Home leaves out Living room"). If arming state cannot be read, the
  camera counts as armed.
- **Its adapters:**
  - **App routes:** `GET /api/arming` (mode, since, by whom, next scheduled change),
    `PUT /api/arming/mode`, `GET`/`PUT /api/arming/modes/{mode}/cameras`,
    `GET`/`PUT /api/arming/schedule`, `GET /api/arming/changes`. The source name is the user.
  - **Inbound webhooks** (`X-API-Key` as today; the source name is the key's fingerprint, never the
    key): `/mode {mode}`; `/arm {mode?}` (default `away`); `/disarm {reason?}`. A `zone_ids` field
    or a legacy arm mode (`full`, `perimeter`, `instant`) is a 422 naming the four modes.
    `/alert {camera_id, source, message, severity, idempotency_key?}` creates an external event: the
    risk score comes from the severity, no VLM runs, the pipeline creates an alert when the camera
    is armed or the severity is critical, snooze and recipients apply, and a repeated key returns
    the first event.
  - **MQTT** (`<prefix>/commands/…`, JSON payloads carrying `token` and `id`):
    `system/mode`, `system/arm`, `system/disarm`; `alerts/{id}/ack` (the alerting Acknowledge);
    `cameras/{id}/ptz` (move, stop, preset, through the ONVIF service); `zones/+/…` answers "zones
    are not supported yet". Every command gets a result on `<prefix>/commands/results/{id}`. The
    token is generated in Settings, shown once and stored as a SHA-256 digest. One stored config,
    seeded from `MQTT_*`; the broker password stays in `.env` or a secret file.
  - **Scheduler:** an in-process job that sleeps until the next entry and calls `set_mode` with the
    source `schedule`. On boot it applies the latest entry that passed while the backend was down,
    if nothing changed the mode since.

## What changes

- **Data model** (recorded upgrades, additive, as `4n-alerting.md` describes them):
  - new: `arming_state` (one row: mode, set at, source kind, source name), `arming_mode_exclusions`
    (mode, camera, `ON DELETE CASCADE`), `arming_schedule` (days, time, mode), `arming_changes`
    (from, to, source kind and name, time; pruned after 365 days);
  - `alert_rules.alert_on_rejected_modes` (null means every mode); `alerts.raised_while_unarmed`;
    `events.source` (`camera` or `external`) and `events.external_source`.
- **backend (`B4.7`):** `arming.py`; the policy and pipeline hook; the app routes;
  `inbound_webhooks.py` on the new vocabulary, with `/alert`'s external event; the scheduler;
  the schemas and generated API types (regenerated, UR-83).
- **backend (`B4.8`):** `mqtt_command_handler.py` (topics, token, rate limit, de-duplication,
  results, the id fix, acknowledge, PTZ; sensitivity removed); `mqtt_client.py` and
  `mqtt_config.py` merged onto one stored config; startup in `main.py`'s lifespan when enabled;
  the `keep.toml` entries removed once the modules have a production importer.
- **frontend (`F4.5`):** the header mode chip; Settings › Arming (cameras per mode, schedule, MQTT
  with its token, change history); the rules dialog's override gains "In chosen modes" (whichever of
  `F4.2` and `F4.5` lands second carries it); the Alerts page marks "raised while unarmed".
- **ops:** an MQTT broker (Mosquitto) in the CI harness for `B4.8`'s golden path, beside
  `[r308a]`'s sinks.
- **docs:** the operator README and `docs/ROADMAP.md` stop describing the deleted MQTT publisher and
  Home Assistant discovery; `frontend/src/components/settings/AGENTS.md` drops the deleted MQTT
  settings UI (UR-81).

## Failure handling

| what fails                                              | what happens                                                                            |
| ------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| Arming state cannot be read                             | The camera counts as armed: an alert rather than a miss.                                |
| The MQTT broker is unreachable                          | Reconnect with backoff; Settings shows the status; the app and webhooks are unaffected. |
| A command has a bad token, an unknown topic or a zone   | Refused, with a result message and an audit entry; the log is rate-limited.             |
| Two mode changes arrive at once                         | The row lock serialises them; the last wins; both are audited.                          |
| The backend is down at a schedule entry                 | Applied on boot, if nothing changed the mode since.                                     |
| A daylight-saving change skips or repeats an entry time | A skipped entry fires at the first valid time; a repeated hour fires once.              |
| `/alert` names an unknown camera, or repeats a key      | A 422; a repeated `idempotency_key` returns the first event.                            |

## Tests

- **Consolidation scope:** `inbound_webhooks.py`, `mqtt_command_handler.py`, `mqtt_client.py`,
  `mqtt_config.py`, the alerting `policy` and `pipeline`, and their tests (48 webhook, 124 MQTT).
- **Tests through the interface:**
  - `mode_at` over a change log; a new camera armed by default; Disarmed arms none;
  - the policy: unarmed and not critical gives no alert, with arming named; unarmed and critical
    gives an alert marked raised while unarmed; the mode-scoped override; the fail-armed stance;
  - the scheduler on a fixed clock: it fires, a manual change holds until the next entry, boot
    catch-up, daylight saving;
  - the webhooks' vocabulary and 422s; `/alert`'s event, alert and idempotency;
  - MQTT: the token, the rate limit, duplicate ids, the topic id (a regression test for `:378`),
    acknowledge, PTZ against an ONVIF fake, the result message.

## Golden path

- **Backend (pytest, `backend/tests/golden/external/`):** Away by webhook, then a confirmed person
  on camera X gives an alert; Home leaving X out, then the same fixture gives no alert and the
  decision names arming; a critical fixture while Disarmed gives an alert marked raised while
  unarmed; `/alert` on an armed camera gives an external event and an alert.
- **MQTT (pytest, `B4.8`):** a mode command with the token switches the mode and publishes a result;
  one without it is refused.
- **UI (Playwright, `F4.5`):** the header chip switches to Away and the change history shows it;
  Home's cameras are edited; a schedule entry is added.
- **Fake-stack scenario:** the person fixture with a `confirmed` verdict, and a critical fixture.
- **Real-tier check:** the operator switches the mode from Home Assistant on a test deployment and
  confirms alerts follow it.

## Privacy and security

- **Stored:** the mode history names who or what changed it (a user, a webhook key's fingerprint,
  an MQTT client id, the schedule); no key or token is stored in clear. An external alert's message
  is stored as the event's summary.
- **Access:** under `EXPOSE_LAN` the app routes keep their login and the webhooks their API key;
  MQTT commands need the broker's credentials and the command token.
- **Erasure:** mode history is configuration history, pruned after 365 days.

## Rollout and reversal

Every schema change is additive. Every install starts in Home with nothing left out, so behaviour is
unchanged until a household edits a mode. The 501 stubs go. Code reversal is a revert; the recorded
upgrades stay, as `4n-alerting.md`'s do.

## Packages

| package | lane     | depends on                                    | contents                                                                                                             | its own golden path    |
| ------- | -------- | --------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- | ---------------------- |
| `B4.7`  | backend  | `B4.1` merged                                 | The arming module and tables, the policy hook, the app routes, the webhooks with `/alert`, the scheduler, the audit. | Backend pytest, above. |
| `B4.8`  | backend  | `B4.7`; `B4.1` for acknowledge; the CI broker | The MQTT adapter: one config, startup, token, topics, results, PTZ, acknowledge; sensitivity removed.                | MQTT pytest, above.    |
| `F4.5`  | frontend | `B4.7`                                        | The header chip, Settings › Arming, the override's modes, "raised while unarmed" on the Alerts page.                 | Playwright, above.     |

## Done when

Each package: its golden path green on the fake stack and its real-tier check posted. F-290 and
F-291 read **works** when `B4.8` merges; F-291's row records that sensitivity left MQTT by this
design.
