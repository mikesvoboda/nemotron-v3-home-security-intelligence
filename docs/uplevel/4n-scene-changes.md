# 4n — Scene Changes Design

> Step 1 of the Scene changes feature packages (`packages/backend.md`, "B4.\* Feature track"),
> copied from [`templates/feature-design.md`](templates/feature-design.md).

**Packages:** `B4.9`, `F4.6` · **Inventory rows:** F-008, F-030, F-208, F-287, F-288 · **R2
ruling:** complete, priority 2 ("run the detector on frames in the pipeline and emit the event",
R2a row 24; `r2-sheet.md:217`) · **Designed:** 2026-10-22, with the owner · **Builds on:**
[`4n-alerting.md`](4n-alerting.md) (the pipeline that turns an incident into an alert) and
[`4n-arming.md`](4n-arming.md) (the external-event mechanism `B4.7` builds)

## Where it starts

Facts read at `main` `aec5580aa`.

- **Nothing in production runs the detector.** `SceneChangeDetector`
  (`backend/services/scene_change_detector.py:47`) compares a frame with a per-camera baseline by
  SSIM against a 0.90 class constant (`:62`) and reports only `change_detected`,
  `similarity_score` and `is_first_frame`. Its baselines are an in-memory dict (`:94`), and the
  first frame a camera sends becomes its baseline (`:208-216`), so a restart forgets every baseline
  and a camera covered at boot is learned as normal. Its last caller, the old enrichment
  pipeline, was deleted in `602379e29`; `scripts/reachability/keep.toml:22-24` keeps the module
  alive for F-287 (ruling 183).
- **Nothing in production writes `scene_changes`.** The table (`backend/models/scene_change.py:57`)
  holds `camera_id`, `detected_at`, `change_type`, `similarity_score`, `acknowledged`,
  `acknowledged_at` and `file_path`; its types are `view_blocked`, `angle_changed`,
  `view_tampered` and `unknown` (`:30-36`). Only the dev seeder writes rows
  (`scripts/seed-events.py:4560`).
- **The routes and the UI exist.** `GET /api/cameras/{camera_id}/scene-changes`
  (`backend/api/routes/cameras.py:1604`) lists one camera's rows, and `POST …/acknowledge`
  (`:1701`) sets the shared flag and writes an audit row that borrows `EVENT_REVIEWED` with actor
  `anonymous` (`:1768-1775`). The header badge (`frontend/src/hooks/useSceneChangeAlerts.ts`), the
  dashboard indicator and toasts and the Scene changes page's live feed
  (`frontend/src/hooks/useSceneChangeEvents.ts`) and the camera modal (`SceneChangePanel`) are
  built. The page fetches each camera separately and filters type and time in the browser
  (`frontend/src/hooks/useSceneChangesQuery.ts:231`).
- **The live messages never reach a browser.** The WebSocket emitter's event broadcaster is never
  attached in production; only the system broadcaster is (`backend/main.py:1018-1029`), so
  `scene_change.detected` ends at "No broadcaster available"
  (`backend/services/websocket_emitter.py:386`), and `SCENE_CHANGE_ACKNOWLEDGED` has no branch in
  the dispatch at all. The alert pipeline sends its own messages through `get_broadcaster(redis)`
  directly (`backend/services/alerting/pipeline.py:789-797`), and that path works.
- **The on/off setting has no reader.** `scene_change_enabled` (`backend/core/config.py:1415`) is
  read only by the settings route; R2 retires it "until the feature it controls exists"
  (`r2-sheet.md:230`).
- **Frames pass one place per camera.** `DetectionQueueWorker._process_image_detection`
  (`backend/services/pipeline_workers.py:493`) takes each uploaded frame to `DetectorClient`, which
  reads the bytes at `backend/services/detector_client.py:1084`, after its circuit-breaker check
  (`:1068`). A frame with no detections never reaches the batch aggregator. Cameras upload on
  motion, so frames come in bursts and stop when nothing moves.
- **An alert needs an event.** `AlertPipeline.process(event_id)` is the only entry
  (`backend/services/alerting/pipeline.py:132`); an event needs a camera and a unique `batch_id`
  (`backend/models/event.py:55-57`). `B4.7` (not yet merged) adds the external-event path an
  incident reuses: an event `source`, rules' `sources`, a namespaced `batch_id` inserted
  `ON CONFLICT DO NOTHING`, and the minute sweep's clause for undecided events
  (`4n-arming.md`, A4 and A5).
- **No golden path covers scene changes.**

## What the user can do when this is done

When someone covers, blurs, sprays or turns one of the household's cameras, the app notices on the
camera's next frames. If that camera is armed, the household is alerted like any other alert, with
the frame that tripped it and what happened ("Garage view blocked"). The header badge, the
dashboard and the Scene changes page show the incident while it is open, and show it cleared once
the camera sees its usual view again. Acknowledging it closes it, and "This is the new normal"
teaches the camera a view someone moved on purpose.

## Decisions

| question                                     | decision                                                                                                                                                                                                                                                                     | why                                                                                                                              |
| -------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| What happens when a camera is tampered with? | An incident creates an event with source `scene_change`, which `AlertPipeline` judges under a seeded, editable rule "Camera tampering". The header badge, the dashboard and the Scene changes page show it as well (owner, SC-1).                                            | "A blocked or moved camera is a security event" (R2); notifications, snooze, cooldown, recipients and arming then come for free. |
| What is a frame compared with?               | Two baselines per camera, day (colour) and night (IR), picked by the frame's colour saturation and stored in the database. Each updates slowly, and only from frames that clearly match it. Acknowledging offers "This is the new normal", which re-baselines (owner, SC-2). | A restart keeps them, the dusk and dawn switch to IR never alerts, and a sudden change is never learned.                         |
| How does a tamper become one incident?       | Every uploaded frame is checked. Two mismatching frames in a row open one incident per camera: one row, one event, one alert. It stays open until three matching frames in a row set `cleared_at` (owner, SC-3).                                                             | A burst of frames is one incident, a passing truck is not, and a covered camera that stops uploading keeps its incident open.    |
| How severe is it?                            | High. It alerts when the camera is armed; when it is not, the incident is recorded and shown, and nobody is notified. Raising the seeded rule to critical pages in every mode (owner, SC-4).                                                                                 | Cleaning or re-aiming a camera while disarmed stays quiet; the household can choose to be paged always.                          |
| Does it say what happened?                   | Yes, from cheap checks on the frame: blocked, angle changed, blurred (a new type) or tampered (owner, SC-5).                                                                                                                                                                 | CPU-only and testable with synthetic frames; the alert and the page's filter can say what happened. The VLM is not used.         |
| How is it acknowledged?                      | An incident and its alert are linked: acknowledging either acknowledges both, with its own audit action and the person who did it.                                                                                                                                           | One household action, wherever it is taken.                                                                                      |
| How long are incidents kept?                 | An incident carries its `event_id` and follows the event: Trash hides it, and a purge erases it and its frame.                                                                                                                                                               | No second retention rule, and `4n-trash.md`'s erasure promise holds.                                                             |
| How sensitive is it?                         | One global similarity threshold, default 0.90. A camera is left out through the rule's camera list.                                                                                                                                                                          | One number to tune; per-camera thresholds wait for a need.                                                                       |
| Can it be switched off?                      | `scene_change_enabled` comes back with a reader, default on. Off, no frame is checked.                                                                                                                                                                                       | R2 retired it only until the feature existed.                                                                                    |

## Approaches weighed

| approach                                            | for                                                                                     | against                                                                              |
| --------------------------------------------------- | --------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| **A. An event through the alert pipeline** (chosen) | Notifications, snooze, cooldown, recipients and arming apply unchanged; one alert list. | Waits for `B4.7`'s event source and rule `sources`.                                  |
| B. Shown only, no alert                             | Independent of `B4.7`; the least code.                                                  | Someone covering a camera reaches the household only if they are looking at the app. |
| C. Always critical                                  | Catches tampering in every mode.                                                        | Pages the household every time a camera is cleaned or adjusted.                      |
| Baseline: operator-set only                         | Nothing is learned, so nothing slow is learned.                                         | Every camera needs setting up, day and night, and again whenever it is re-aimed.     |
| Baseline: one rolling baseline                      | The simplest; drifts through dusk.                                                      | A slow, deliberate move or a gradual covering is absorbed as normal.                 |

## Shape

- **The module behind the seam:** `backend/services/scene_watch.py`. Domain terms, added to
  `docs/reference/glossary.md`: **scene baseline** (day or night), **scene incident** (open,
  cleared, acknowledged), **new normal**.
- **Its interface:**
  - `observe(camera_id, frame, at) -> Observation`, one of `seeded`, `match`, `pending`,
    `opened(incident)`, `cleared(incident)` or `skipped(reason)`. It picks the baseline kind from
    the frame's mean saturation (below a starting value of 0.05 is `night`), compares with
    `SceneChangeDetector`'s SSIM, and keeps a per-camera state: the run of mismatches, the run of
    matches, and the open incident. Two mismatches in a row open an incident; three matches in a
    row clear it. A missing baseline of that kind is seeded from the frame (`seeded`). A matching
    frame whose similarity is at least the threshold plus 0.05, with no incident open, moves the
    baseline towards it by a weight of 0.02. A mismatch never moves it.
  - `classify(frame, baseline) -> ChangeType`, pure: `view_blocked` when the frame's mean
    luminance or its spread is near zero; `angle_changed` when phase correlation finds a
    whole-image shift and the shifted frame matches; `view_blurred` when its sharpness (variance
    of the Laplacian) falls below a quarter of the baseline's; otherwise `view_tampered`. The
    starting values are named constants, pinned by tests on synthetic frames.
  - `set_normal(camera_id, kind=None)`: replace the baseline (both kinds when `kind` is `None`)
    with the camera's latest frame of that kind.
  - `acknowledge(incident_id, by, new_normal) -> Incident`: acknowledges the incident and its open
    alert, writes the audit action `scene_change.acknowledged`, and, with `new_normal`, calls
    `set_normal` for that camera.
  - Invariants: at most one open incident per camera; an incident's event is created once (its
    `batch_id` is `scene_change:<incident id>`, inserted `ON CONFLICT DO NOTHING`); a baseline is
    never moved by a frame that mismatches or while an incident is open.
  - Errors: a frame that cannot be decoded is `skipped`, logged, and never fails the frame's
    detection. Configuration: `scene_change_enabled` (default on) and
    `SCENE_CHANGE_SIMILARITY_THRESHOLD` (default 0.90) beside `scene_change_resize_width`.
- **How an incident becomes an alert:** opening an incident inserts the event (the camera, the
  incident's frame as its thumbnail, `source` `scene_change`, no detections, no VLM; risk level
  high, and the risk score the top of the high band in `SeverityService`, so the two agree) and
  calls `AlertPipeline.process` after the commit; the minute sweep also selects undecided events
  whose source is `scene_change`. `4n-alerting.md`'s resolver gains the source `scene_change` with
  no verdict, rules' `sources` gain `scene_change`, and the seeded rule "Camera tampering" (all
  cameras, high, sources `scene_change`, a fixed UUID as "External alerts" has) is the only
  default rule that matches it. The activity key is the camera plus `scene_change`, so the rule's
  cooldown folds an incident that reopens within it. The alert's text names the type and the
  camera.
- **Its adapters:**
  - **The pipeline worker:** `_process_image_detection` reads each frame once and, with
    `scene_change_enabled` on, hands it to `observe` in a worker thread before detection and
    before the circuit breaker, so a detector outage does not blind it. Extracted video frames go
    the same way.
  - **HTTP:** `GET /api/scene-changes` lists incidents across cameras with server-side filters
    (camera, type, state: open, cleared or acknowledged; time) and a cursor;
    `GET /api/cameras/{camera_id}/scene-changes` stays; `POST …/acknowledge` takes
    `{new_normal: bool}`; `POST /api/cameras/{camera_id}/scene-baseline` sets the new normal
    without an incident. The person is the session's user.
  - **The alert pipeline:** acknowledging the alert from the Alerts page calls `acknowledge` on
    its incident, through the event.
  - **Live messages:** `scene_change.detected`, `scene_change.cleared` and
    `scene_change.acknowledged`, sent through `get_broadcaster(redis)` as the alert pipeline sends
    its own, so they reach the header, the dashboard and the page.

## What changes

- **backend (`B4.9`):** `backend/services/scene_watch.py` (new); `scene_change_detector.py` keeps
  SSIM and its frame preparation and loses its in-memory baselines; `pipeline_workers.py` (the
  hook); `backend/models/scene_change.py` (`event_id`, `cleared_at`, `acknowledged_by`, the type
  `view_blurred`) and a new `scene_baselines` table (camera, kind, the prepared greyscale image,
  updated at, frames seen), one recorded upgrade, additive; the alerting resolver's source, rules'
  `sources` value and the seeded rule; `cameras.py` and a new `scene_changes.py` route module; the
  audit action; `config.py`, `.env.example` and the compose `environment:` block (UR-9);
  `keep.toml`'s F-287 entry leaves, since the module gains a caller. The cascade from an event's
  purge to its incident and frame goes in the purger's list (`4n-trash.md`).
- **frontend (`F4.6`):** the header badge counts open, unacknowledged incidents; the dashboard
  indicator and toasts follow open and cleared; the camera modal lists the camera's incidents and
  offers "Set as normal"; the Scene changes page reads `GET /api/scene-changes` with its filters
  and the state column, and its Acknowledge dialog offers "This is the new normal"; the Alerts
  page shows a tamper alert like any other (`F4.1`).
- **docs:** the glossary terms, and the camera-settings page of the operator docs (UR-81).
- **Not changed:** backups. Baselines are relearned after a restore, and the seeded rule's fixed
  UUID keeps a restore from duplicating it (`4n-restore.md`).

## Failure handling

- **A frame that cannot be checked** (decode error, wrong shape) is skipped and logged; its
  detection carries on.
- **A baseline write that fails** keeps the baseline in memory and retries on the next match; an
  incident is still opened from the in-memory baseline.
- **A crash between the event's commit and `AlertPipeline.process`** is caught by the minute
  sweep's `scene_change` clause.
- **A restart with an incident open** reloads the open incidents and their mismatch state from
  `scene_changes` rows whose `cleared_at` is null, so the incident neither reopens nor alerts again.
- **Two frames of one camera at once** are serialised per camera, so a burst cannot open two
  incidents.

## Tests

- **Consolidation scope:** `scene_change_detector.py`, `backend/models/scene_change.py`, the scene
  change routes in `cameras.py`, `pipeline_workers.py`'s image path, `websocket_emitter.py`'s scene
  branches, and the frontend hooks and components named above (`useSceneChangeAlerts`,
  `useSceneChangeEvents`, `useSceneChangesQuery`, `SceneChangePanel`, `SceneChangesPage`,
  `SceneChangeIndicator`).
- **Tests through the interface:** `observe` on synthetic frame sequences: seed, match, two
  mismatches open, a single mismatch does not, three matches clear, a burst opens one incident,
  restart with an incident open, the day-to-night switch never opens one, slow drift is learned and
  a sudden change is not; `classify` for each type, with an unclassifiable change as tampered;
  `acknowledge` with and without new normal, both directions of the alert link; the event's
  `batch_id` conflict; the policy: armed alerts, unarmed records only, critical rule pages while
  disarmed, cooldown folds a reopen.

## Golden path

- **Spec, backend** (`backend/tests/golden/external/test_scene_change.py`): upload a camera's usual
  frame, then two covered frames, through the upload path on the fake stack; the incident opens as
  `view_blocked`, one event and one alert exist under "Camera tampering", and the live message is
  sent; three usual frames clear it.
- **Spec, UI** (Playwright, `frontend/tests/golden/scene-changes/`): the header badge counts the
  open incident live; the Scene changes page lists it and filters by type and state; Acknowledge
  with "This is the new normal" clears the badge and the alert.
- **Fake-stack scenario:** fixture frames for each type, generated from one camera image (black,
  blurred, shifted, patched); no VLM call.
- **Real-tier check:** the operator feeds the same sequence through the test deployment's upload
  path on the GB300 and reads the incident open and clear, the one alert, and that the VLM was not
  called.

## Privacy and security

Baselines are images of the household's views, as sensitive as event media; they live in the
database, are not in backups, and go when their camera is deleted. An incident's frame follows its
event's retention and Trash. With `EXPOSE_LAN=true` every route needs a session or API key, as
today; acknowledging and setting a new normal record the person.

## Rollout and reversal

Every schema change is additive. On upgrade `scene_change_enabled` is on, and each camera seeds its
baselines from its next frames of each kind, so nothing can alert until a camera has a baseline.
Switching the setting off stops all checks; a code revert removes the hook, and the recorded
upgrade stays.

## Packages

| package | lane (proposed) | depends on                                          | contents                                                                                                                      | its own golden path   |
| ------- | --------------- | --------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- | --------------------- |
| `B4.9`  | backend         | `B4.7` merged (the event source and rule `sources`) | The module, the hook, baselines, incidents and their event, the source and seeded rule, the routes, the live messages, audit. | Backend pytest above. |
| `F4.6`  | frontend        | `B4.9`; `F4.1` for the alert rows                   | The badge, dashboard indicator and toasts, camera modal, Scene changes page and its Acknowledge dialog.                       | Playwright above.     |

Each runs the six steps as two PRs: a test-only consolidation PR, then the build.

## Done when

Each package: its golden path green on the fake stack and its real-tier check posted. The five
rows (F-008, F-030, F-208, F-287, F-288) read **works** once both packages have merged and the
real-tier check is posted.
