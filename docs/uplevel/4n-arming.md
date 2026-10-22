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

| question                                                      | decision                                                                                                                                                                                                                                                                        | why                                                                                                                                                                       |
| ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| What does arming gate?                                        | Alert creation. Analysis and the timeline run in every mode; the arm state decides whether an event may become an alert. Notifications follow alerts as `4n-alerting.md` designs them.                                                                                          | History stays complete, and the Alerts page means "what needed attention while armed".                                                                                    |
| How much arming does the product have?                        | Always armed by default. Modes exist for households that need them, typically to leave indoor cameras out while home.                                                                                                                                                           | Face suppression, rule schedules and snooze cover most time at home; modes cover what they cannot.                                                                        |
| What is a mode?                                               | One of four fixed modes, Home, Away, Night and Disarmed, each the set of cameras it arms. A mode stores the cameras it leaves out, so a new camera is armed in Home, Away and Night; Disarmed leaves out every camera.                                                          | Rules stay as designed: an alert can come only from a rule's cameras that the mode arms.                                                                                  |
| Does a critical alert respect the mode?                       | No. An alert whose effective severity is critical is created from any camera in any mode, Disarmed included, and is marked "raised while unarmed". Each person's quiet-hours opt-out still applies to delivery.                                                                 | Like a smoke alarm that is never off.                                                                                                                                     |
| Are zones armed?                                              | Not yet. Modes arm cameras. A zone command answers "zones are not supported yet" until a later package makes detections carry a zone, which also unlocks rules' `zone_ids`.                                                                                                     | Nothing carries a zone to gate on; a half-behaviour would mislead.                                                                                                        |
| How does the mode change?                                     | From the app, the webhooks and MQTT, and an optional weekly schedule in the household's time zone. A manual, webhook or MQTT change holds until the next scheduled entry.                                                                                                       | Night is only useful if it happens without a habit or an integration.                                                                                                     |
| How do modes relate to rule schedules and quiet hours?        | Each keeps its own job: the mode decides which cameras may alert, a rule's schedule when that rule applies, quiet hours when a person is pushed (OD-22 as `4n-alerting.md` settles it).                                                                                         | Three questions, three places to look.                                                                                                                                    |
| Can a rule alert on a "no threat" verdict only in some modes? | Yes. The rule's override reads "Never", "In chosen modes" or "Always". The default rule stays "Never".                                                                                                                                                                          | While away, any person may matter even when the VLM judges it benign.                                                                                                     |
| What does the `/alert` webhook do?                            | It creates an external event on the camera the payload names (a door sensor names the door camera). The seeded, editable rule "External alerts" turns it into an alert when that camera is armed or the severity is critical. No camera named is a 422.                         | Modes, snooze, recipients and the footage around it all apply, like any event; an alert stays a rule match, so a household can mute a source (owner, A4).                 |
| Which MQTT commands are built?                                | Mode, arm and disarm (they switch the household mode), alert acknowledge and PTZ. Sensitivity is retired from MQTT.                                                                                                                                                             | Nothing reads sensitivity; giving it meaning is a detection feature for later. Narrows ruling 89 by one.                                                                  |
| How does MQTT start and authenticate?                         | It starts only when enabled in Settings › Arming, which refuses a broker without credentials or one that accepts an anonymous login, and warns when TLS is off. Every command also carries the household's command token. Commands are rate-limited, de-duplicated and audited. | The token stops publishers that have never seen a command; anyone who can read the command topics can read it, so the broker's ACL keeps them to the backend (owner, A1). |
| Where is the mode seen and changed?                           | A chip in the header on every page, and Settings › Arming for the cameras per mode, the schedule, MQTT and its token, and the change history.                                                                                                                                   | The mode is the one state worth seeing everywhere.                                                                                                                        |
| What is stored and audited?                                   | The current mode with its source, the exclusions, the schedule, and every change of the mode or of a mode's cameras (from, to, source kind and name, time), kept 365 days.                                                                                                      | "Who disarmed the house" must have an answer.                                                                                                                             |

## Approaches weighed

| approach                                 | for                                                                                                            | against                                                                                        |
| ---------------------------------------- | -------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| **A. Arming as a policy input** (chosen) | One place decides alert creation; arming tests alone; thin adapters (UR-12); the decision record names arming. | The policy depends on one more module (a cached read per event).                               |
| B. A filter in front of the pipeline     | No policy change.                                                                                              | Effective severity is known only inside the policy; the override cannot live there; no record. |
| C. Modes rewrite rules                   | No policy or pipeline change.                                                                                  | Overwrites what the household set; races with edits; a confusing audit.                        |
| D. Gate delivery                         | Smallest.                                                                                                      | Ruled out: arming gates alert creation.                                                        |

## Shape

- **The module behind the seam:** `backend/services/arming.py`. Domain terms, added to
  `docs/reference/glossary.md`: **arming mode**, **armed camera**, **raised while unarmed**.
- **Its interface:**
  - `mode_at(t) -> Mode` and `is_armed(camera_id, at) -> bool`, from the change log. It records
    every change of the mode and of a mode's cameras, each row carrying every mode's exclusions
    after it, so an event is judged by the arming at its start, as the recovery and sweep paths
    need, however long its decision waits (A2);
  - `set_mode(mode, source) -> Change`, serialised by a row lock on `arming_state`;
  - `apply_schedule(now) -> Change | None`, under the same lock (A3, below);
  - `next_scheduled() -> (time, mode) | None`.
- **How the policy uses it** (`4n-alerting.md`'s `policy.evaluate`): `PolicyContext` gains `mode`
  and `armed`. A rule match on an unarmed camera survives only when its effective severity is
  critical, and the alert is marked `raised_while_unarmed`. A `rejected` verdict matches only when
  the rule's override covers the mode. When arming is the reason no alert was created, the event's
  notify decision says so ("Home leaves out Living room"). If arming state cannot be read, the
  camera counts as armed.
- **External events in the policy** (A4): `4n-alerting.md`'s resolver gains the source `external`,
  with no verdict; the risk level is the payload's severity and the risk score the top of that
  band in `SeverityService`, so the two agree. Rules gain `sources` (`camera`, `external`; existing
  rules `camera`). Only a rule whose sources include `external` matches an external event, and a
  rule with object types or a minimum confidence never does. The seeded, editable rule "External
  alerts" (all cameras, every severity, no object types, sources `external`) makes a default
  `/alert` call alert on an armed camera. Face suppression needs at least one person on the event,
  so an event with none is never suppressed by it. The master switch, snooze and arming apply as
  for any event; the activity key is the camera plus `external:<source>`, and the alert's
  `verdict_source` is `external`.
- **Its adapters:**
  - **App routes:** `GET /api/arming` (mode, since, by whom, next scheduled change),
    `PUT /api/arming/mode`, `GET`/`PUT /api/arming/modes/{mode}/cameras`,
    `GET`/`PUT /api/arming/schedule`, `GET /api/arming/changes`. The source name is the user.
  - **Inbound webhooks** (`X-API-Key` as today; the source name is the key's fingerprint, never the
    key): `/mode {mode}`; `/arm {mode?}` (default `away`); `/disarm {reason?}`. A `zone_ids` field
    or a legacy arm mode (`full`, `perimeter`, `instant`) is a 422 naming the four modes.
    `/alert {camera_id, source, message, severity, idempotency_key?}` creates an external event
    (A5): its `batch_id` is `external:<key fingerprint>:<sha256 of the idempotency key>`, or
    `external:<uuid>` without one, inserted `ON CONFLICT (batch_id) DO NOTHING` and read back; no
    VLM runs; a severity other than low, medium, high or critical is a 422. Every request, first or
    repeated, calls `AlertPipeline.process` after the commit, and the minute sweep also selects
    undecided events whose `source` is `external`, so a crash between the two still alerts.
  - **MQTT** (`<prefix>/commands/…`, JSON payloads carrying `token` and an `id` matching
    `^[A-Za-z0-9_-]{1,64}$`): `system/mode`, `system/arm`, `system/disarm`; `alerts/{id}/ack` (the
    alerting Acknowledge); `cameras/{id}/ptz` (move, stop, preset, through the ONVIF service);
    `zones/+/…` answers "zones are not supported yet". Every command gets a result on
    `<prefix>/results/{id}`, outside the commands prefix, not retained, which never echoes the
    token or the payload.
    The token is generated in Settings, shown once and stored as a SHA-256 digest.
  - **MQTT's trust** (A1, owner): the token stops only publishers that have never seen a command,
    since any client that can read `<prefix>/commands/#` reads it. The operator README gives a
    Mosquitto ACL that lets only the backend's user read that prefix, and lets command senders read
    `<prefix>/results/#`. Enabling is refused without broker credentials, or when a test connection
    without them is accepted; with TLS off Settings shows a warning. Startup when enabled runs the
    same check, so a restored or hand-edited config that fails it leaves MQTT off and Settings says
    why. With TLS on, the certificate and host name are checked against the CA path in the stored
    config. MQTT does not say who published a message, so the rate limit is global and the audit
    names the token's fingerprint. One stored config, seeded from `MQTT_*`; the broker password
    stays in `.env` or a secret file.
  - **Scheduler** (A3): an in-process job that sleeps until the next occurrence, or until a
    schedule save wakes it, then calls `apply_schedule(now)` with the source `schedule`; boot calls
    it too. Under the `arming_state` lock it re-reads the schedule and takes the latest occurrence
    at or before now, one per entry per local date: a time that daylight saving skips moves to the
    first valid instant, and a repeated time takes its first. It changes the mode only if that
    occurrence is later than both `arming_state.set_at` and `schedule_updated_at`. So a manual
    change holds until the next entry, a deleted entry never fires, an entry added for a time
    already past waits for its next occurrence, and a restart or a repeated hour changes the mode
    once. The backend runs one worker process, so the wake is in-process, as the alerting worker's
    is.

## What changes

- **Data model** (recorded upgrades, additive, as `4n-alerting.md` describes them):
  - new: `arming_state` (one row: mode, set at, source kind, source name, `schedule_updated_at`),
    `arming_mode_exclusions` (mode, camera, `ON DELETE CASCADE`), `arming_schedule` (days, time,
    mode), `arming_changes` (kind `mode` or `cameras`, from, to, every mode's exclusions after
    it, source kind and name, time; pruned after 365 days, keeping the newest row before the
    cutoff so `mode_at` still answers);
  - `alert_rules.alert_on_rejected_modes` (null means every mode) and `alert_rules.sources`, with
    the seeded "External alerts" rule; `alerts.raised_while_unarmed`; `events.source` (`camera` or
    `external`) and `events.external_source`.
- **backend (`B4.7`):** `arming.py`; the policy and pipeline hook; the resolver's `external` source
  and the sweep's external clause; the app routes; `inbound_webhooks.py` on the new vocabulary, with
  `/alert`'s external event; the scheduler; the schemas and generated API types (regenerated,
  UR-83). Arming configuration (each mode's exclusions, the schedule) stays out of backups: a
  restore never changes arming, so a reinstalled system restored from an archive arms every camera
  in Home, Away and Night, the safe direction, and a restore in place keeps the local choices.
  `alert_rules.sources` defaults to `camera`, so an older archive's rules insert as camera rules and
  keep their local value on update (`4n-restore.md`, "Versions"); no restore adapter changes. The
  seeded "External alerts" rule carries a fixed UUID, so a restore merges an archived copy into it
  by id instead of inserting a second rule that would alert twice; an archive without it keeps the
  local one (`4n-restore.md`'s merge keeps rows not in the archive).
- **backend (`B4.8`):** `mqtt_command_handler.py` (topics, token, id check, global rate limit,
  de-duplication, results, the id fix at `:378` and the same read at `:383`, `:393`, `:398`,
  acknowledge, PTZ; sensitivity removed); `mqtt_client.py` and `mqtt_config.py` merged onto one
  stored config with a CA path; the credential check on enable and again at startup; startup in
  `main.py`'s lifespan when enabled; the `keep.toml` entries removed once the modules have a
  production importer.
- **frontend (`F4.5`):** the header arming chip; Settings › Arming (cameras per mode, schedule,
  change history); the rules dialog's override gains "In chosen modes" (whichever of `F4.2` and
  `F4.5` lands second carries it); the Alerts page marks "raised while unarmed" on the alert rows
  `F4.1` brings. Settings › Arming's MQTT section (enable, status, the TLS warning, the token shown
  once) goes with whichever of `B4.8` and `F4.5` lands second (A6).
- **ops:** an MQTT broker (Mosquitto, with a password file, the README's ACL, a TLS listener and a
  second listener that accepts anonymous logins) in the CI harness for `B4.8`'s golden path,
  beside `[r308a]`'s sinks.
- **docs:** the operator README gains the MQTT section and its Mosquitto ACL; it and
  `docs/ROADMAP.md` stop describing the deleted MQTT publisher and
  Home Assistant discovery; `frontend/src/components/settings/AGENTS.md` drops the deleted MQTT
  settings UI (UR-81).

## Failure handling

| what fails                                                                           | what happens                                                                                             |
| ------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------- |
| Arming state cannot be read                                                          | The camera counts as armed: an alert rather than a miss.                                                 |
| The MQTT broker is unreachable                                                       | Reconnect with backoff; Settings shows the status; the app and webhooks are unaffected.                  |
| MQTT is enabled with no broker credentials, or the broker accepts an anonymous login | Refused, naming the reason. With TLS off it is enabled with a warning.                                   |
| A command has a bad token, a malformed id, an unknown topic or a zone                | Refused, with a result message that never echoes the token, and an audit entry; the log is rate-limited. |
| Two mode changes arrive at once                                                      | The row lock serialises them; the last wins; both are audited.                                           |
| A scheduled occurrence is older than the current mode or the last schedule edit      | Skipped: a manual change holds until the next entry.                                                     |
| A schedule entry is edited or deleted while the job sleeps                           | The save wakes the job, which recomputes; a deleted entry never fires.                                   |
| The backend is down at a schedule entry                                              | Applied on boot, if nothing changed the mode or the schedule since.                                      |
| A daylight-saving change skips or repeats an entry time                              | A skipped entry fires at the first valid time; a repeated hour fires once.                               |
| `/alert` names an unknown camera, or repeats a key                                   | A 422; a repeated `idempotency_key` returns the first event and reruns the pipeline.                     |
| The backend dies after an external event commits                                     | The minute sweep finds it with no notify decision and alerts.                                            |

## Tests

- **Consolidation scope:** `inbound_webhooks.py`, `mqtt_command_handler.py`, `mqtt_client.py`,
  `mqtt_config.py`, the alerting `policy` and `pipeline`, and their tests (48 webhook, 124 MQTT).
- **Tests through the interface:**
  - `mode_at` and `is_armed` over a change log; a new camera armed by default; Disarmed arms none;
    a camera left out of Away between an event's start and its decision: the normal path and the
    sweep both alert, a later event does not, and the history lists the edit;
  - the policy: unarmed and not critical gives no alert, with arming named; unarmed and critical
    gives an alert marked raised while unarmed; the mode-scoped override; the fail-armed stance;
  - external events under the shipped rules: low and medium on an armed camera alert; on an
    unarmed camera only critical does; a `person` rule never matches; no person means no face
    suppression; the master switch off means no alert;
  - the scheduler on a fixed clock with a real database: it fires; a webhook change one second
    after an occurrence holds; boot catch-up after a manual change holds; an entry deleted while
    the job sleeps never fires; an entry added for earlier today waits; two wakes and a restart
    inside a repeated hour change the mode once;
  - the webhooks' vocabulary and 422s; `/alert`'s event, alert and idempotency: a crash between
    the event's commit and the pipeline, then the sweep alerts; a retry after it gives the same
    event and an alert; two identical requests at once give one event and one alert; one key under
    two API keys gives two events;
  - MQTT: the token, the global rate limit, duplicate ids, malformed ids (`a/b`, `+`, `#`, 65
    characters) refused with nothing published outside `results/<valid id>`, no token bytes in a
    result, the topic id (regression tests for `:378`, `:383`, `:393`, `:398`), acknowledge, PTZ
    against an ONVIF fake; against the CI broker: an anonymous broker refused on enable; under the
    README's ACL a second user subscribed to `<prefix>/commands/#` receives nothing; TLS with no CA
    path or a host-name mismatch fails, and the right CA connects.

## Golden path

- **Backend (pytest, `backend/tests/golden/external/`):** Away by webhook, then a confirmed person
  on camera X gives an alert; Home leaving X out, then the same fixture gives no alert and the
  decision names arming; a critical fixture while Disarmed gives an alert marked raised while
  unarmed; `/alert` with the default severity on an armed camera gives an external event and an
  alert from "External alerts".
- **MQTT (pytest, `B4.8`):** a mode command with the token switches the mode and publishes a result;
  one without it is refused; enabling against an anonymous broker is refused, and an enabled
  stored config against the anonymous listener stays off at startup.
- **UI (Playwright, `F4.5`):** the header chip switches to Away and the change history shows it;
  Home's cameras are edited; a schedule entry is added; with the chip on Disarmed, a critical
  fixture's row on the Alerts page reads "raised while unarmed".
- **MQTT section (Playwright, whichever of `B4.8` and `F4.5` lands second):** a token is issued,
  shown once and gone on reload; MQTT is enabled; the status reads connected against the CI broker.
- **Fake-stack scenario:** the person fixture with a `confirmed` verdict, and a critical fixture.
- **Real-tier check:** the operator switches the mode from Home Assistant on a test deployment and
  confirms alerts follow it.

## Privacy and security

- **Stored:** the mode history names who or what changed it (a user, a webhook key's fingerprint,
  the MQTT command token's fingerprint, the schedule); no key or token is stored in clear. An
  external alert's message is stored as the event's summary.
- **Access:** under `EXPOSE_LAN` the app routes keep their login and the webhooks their API key;
  MQTT commands need the broker's credentials and the command token, and the README's ACL keeps
  the command topics, where the token travels, to the backend. Results are not retained and never
  carry the token.
- **Erasure:** mode history is configuration history, pruned after 365 days.

## Rollout and reversal

Every schema change is additive. Every install starts in Home with nothing left out, so behaviour is
unchanged until a household edits a mode. The 501 stubs go. Code reversal is a revert; the recorded
upgrades stay, as `4n-alerting.md`'s do.

## Packages

| package | lane                  | depends on                                    | contents                                                                                                                                                           | its own golden path    |
| ------- | --------------------- | --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------- |
| `B4.7`  | heavy-a (ruling 311)  | `B4.1` merged                                 | The arming module and tables, the policy hook, the external source and rule, the app routes, the webhooks with `/alert`, the scheduler, the audit.                 | Backend pytest, above. |
| `B4.8`  | backend (ruling 311)  | `B4.7`; `B4.1` for acknowledge; the CI broker | The MQTT adapter: one config, the credential check, startup, token, topics, results, PTZ, acknowledge; sensitivity removed; the MQTT section if `F4.5` has landed. | MQTT pytest, above.    |
| `F4.5`  | frontend (ruling 311) | `B4.7`; `F4.1` for the alert rows             | The header chip, Settings › Arming, the override's modes, "raised while unarmed" on the Alerts page; the MQTT section if `B4.8` has landed.                        | Playwright, above.     |

## Review

An adversarial review (2026-10-21) and three fresh-context checks of it found six issues; every cite
in "Where it starts" held at `origin/main` `23030f252`. Two claims were wrong: TLS does not hide the
token from a subscriber, and signed commands do not fit Home Assistant. The owner ruled on two:

| #   | finding                                                                   | amendment                                                                                                                                                |
| --- | ------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A1  | Anyone who can read the command topics reads the token                    | Credentials required, an anonymous broker refused, TLS off warned (owner); the README's ACL; ids checked; results without the token; a global rate limit |
| A2  | Exclusion edits are neither versioned nor audited                         | The change log records them with every mode's exclusions; `is_armed` reads it at the event's start                                                       |
| A3  | A scheduled change can overwrite a newer one; a deleted entry still fires | `apply_schedule(now)` under the lock, newer than the last change and the last schedule edit; a save wakes the job                                        |
| A4  | External events match no rule, and the default rule drops medium          | An `external` verdict source; rules gain `sources`; a seeded "External alerts" rule (owner); face suppression needs a person                             |
| A5  | External events escape the sweep, and a repeated key skips the pipeline   | The sweep selects external events; a namespaced `batch_id`; every request reruns the pipeline                                                            |
| A6  | `F4.5` declares MQTT and the badge with only `B4.7`                       | `F4.5` after `F4.1`; the MQTT section with whichever of `B4.8` and `F4.5` lands second                                                                   |

The plan PR's review (#7338) added two items: results move to `<prefix>/results/{id}`, so the ACL
can let senders read them without reading the commands; and arming configuration stays out of
backups, since a restored install that arms every camera fails safe and `sources` defaults to
`camera` for older archives' rules. The next plan PR (#7338's round-3 notes) added three: the
restore wording covers a restore in place; MQTT's startup re-runs the enable check; and the seeded
"External alerts" rule carries a fixed UUID, so a restore cannot duplicate it.

## Done when

Each package: its golden path green on the fake stack and its real-tier check posted. F-290 reads
**works** when `B4.7` merges, and F-291 when the MQTT section lands with the second of `B4.8` and
`F4.5`; F-291's row records that sensitivity left MQTT by this design.
