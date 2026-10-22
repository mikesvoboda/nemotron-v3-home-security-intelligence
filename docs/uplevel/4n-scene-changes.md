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
  read only by the settings route; R2 retires it and says to "re-add a toggle only with the
  feature it controls" (`r2-sheet.md:230`).
- **Frames pass one place per camera.** `DetectionQueueWorker._process_image_detection`
  (`backend/services/pipeline_workers.py:493`) takes each uploaded frame to `DetectorClient`, which
  reads the bytes at `backend/services/detector_client.py:1084`, after its circuit-breaker check
  (`:1068`). A frame with no detections never reaches the batch aggregator. Cameras upload on
  motion, so frames come in bursts and stop when nothing moves.
- **An alert needs an event.** `AlertPipeline.process(event_id)` is the only entry
  (`backend/services/alerting/pipeline.py:132`); an event needs a camera and a unique `batch_id`
  (`backend/models/event.py:54-57`). `B4.7` (not yet merged) adds the external-event path an
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

| question                                     | decision                                                                                                                                                                                                                                                                                                                                                               | why                                                                                                                                               |
| -------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| What happens when a camera is tampered with? | An incident creates an event with source `scene_change`, which `AlertPipeline` judges under a seeded, editable rule "Camera tampering". The header badge, the dashboard and the Scene changes page show it as well (owner, SC-1).                                                                                                                                      | "A blocked or moved camera is a security event" (R2); notifications, snooze, cooldown, recipients and arming then come for free.                  |
| What is a frame compared with?               | Two baselines per camera, day (colour) and night (IR), picked by the frame's colour saturation and stored in the database. Each updates slowly, and only from frames that clearly match it. A featureless frame (black, covered, glare) never seeds or teaches a baseline. Acknowledging offers "This is the new normal", which re-baselines (owner, SC-2; review S1). | A restart keeps them, the dusk and dawn switch to IR never alerts, a sudden change is never learned, and a covered lens is never taken for night. |
| Can slow learning absorb a slow tamper?      | No: each baseline keeps a fixed anchor, its first seed or the last "new normal". When the learned baseline matches its anchor below 0.75, learning stops and a `view_drifted` incident opens: "Garage view has drifted from its set view. Check it, then confirm the new normal." It alerts like any incident; one tap re-anchors (owner, review S2).                  | A patient covering, turn or pan spread over days of uploads is caught; seasonal change asks for one confirmation now and then.                    |
| How does a tamper become one incident?       | Every uploaded frame is checked, in capture order. Two mismatching frames in a row open one incident per camera: one row, one event, one alert. It stays open until three matching frames in a row set `cleared_at` (owner, SC-3).                                                                                                                                     | A burst of frames is one incident, a passing truck is not, and a covered camera that stops uploading keeps its incident open.                     |
| How severe is it?                            | High. It alerts when the camera is armed; when it is not, the incident is recorded and shown, and nobody is notified. Raising the seeded rule to critical pages in every mode (owner, SC-4).                                                                                                                                                                           | Cleaning or re-aiming a camera while disarmed stays quiet; the household can choose to be paged always.                                           |
| Does it say what happened?                   | Yes, from cheap checks on the frame: blocked, angle changed, blurred or tampered, plus drifted from the anchor; `view_blurred` and `view_drifted` are new types (owner, SC-5).                                                                                                                                                                                         | CPU-only and testable with synthetic frames; the alert and the page's filter can say what happened. The VLM is not used.                          |
| How is it acknowledged?                      | An incident and its alert are linked: acknowledging either acknowledges both, with its own audit action and the person who did it.                                                                                                                                                                                                                                     | One household action, wherever it is taken.                                                                                                       |
| How long are incidents kept?                 | An incident carries its `event_id` and its own picture, and follows the event: Trash closes and hides it, and a purge erases it and its picture.                                                                                                                                                                                                                       | No second retention rule, and `4n-trash.md`'s erasure promise holds.                                                                              |
| How sensitive is it?                         | One global similarity threshold, default 0.90. A camera is left out through the rule's camera list.                                                                                                                                                                                                                                                                    | One number to tune; per-camera thresholds wait for a need.                                                                                        |
| Can it be switched off?                      | `scene_change_enabled` comes back with a reader, default on. Off, no frame is checked.                                                                                                                                                                                                                                                                                 | R2 retired it only until the feature existed.                                                                                                     |

## Approaches weighed

| approach                                            | for                                                                                     | against                                                                                                                                                                                                 |
| --------------------------------------------------- | --------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A. An event through the alert pipeline** (chosen) | Notifications, snooze, cooldown, recipients and arming apply unchanged; one alert list. | Waits for `B4.7`'s event source and rule `sources`.                                                                                                                                                     |
| B. Shown only, no alert                             | Independent of `B4.7`; the least code.                                                  | Someone covering a camera reaches the household only if they are looking at the app.                                                                                                                    |
| C. Always critical                                  | Catches tampering in every mode.                                                        | Pages the household every time a camera is cleaned or adjusted.                                                                                                                                         |
| Baseline: operator-set only                         | Nothing is learned, so nothing slow is learned.                                         | Every camera needs setting up, day and night, and again whenever it is re-aimed.                                                                                                                        |
| Baseline: one rolling baseline, no anchor           | The simplest; drifts through dusk.                                                      | Dusk and dawn alert, and any change spread over enough frames is learned. Review S2 measured it for the chosen design without an anchor: a covering, turn or pan over 1,000–10,000 frames was absorbed. |

## Shape

- **The module behind the seam:** `backend/services/scene_watch.py`. Domain terms, added to
  `docs/reference/glossary.md`: **scene baseline** (day or night), **anchor**, **scene incident**
  (open, cleared, acknowledged, closed), **new normal**.
- **Its interface:**
  - `observe(camera_id, frame, at) -> Observation`, one of `seeded`, `match`, `pending`,
    `opened(incident)`, `cleared(incident)` or `skipped(reason)`. `at` is the frame's capture
    time; a frame no newer than the camera's last observed one is `skipped(stale)`, so a frame
    replayed from the dead-letter queue never opens or clears anything (S6). In order:
    1. **Featureless first** (S1): a frame whose mean luminance or spread is near zero is
       featureless. With any baseline it counts as a mismatch (`view_blocked`); with none it is
       `skipped(featureless)`. It never seeds or teaches a baseline.
    2. **The kind:** mean saturation below a starting value of 0.05 is `night`, else `day`.
    3. **Seeding:** a missing baseline of that kind is seeded from the frame, and its anchor with
       it. While the other kind exists, a seed is accepted only when the frame's edge map agrees
       with the other baseline's, so a camera re-aimed before its first night does not learn the
       new view as night (S1).
    4. **Comparison:** `SceneChangeDetector`'s SSIM against the baseline. The per-camera state
       keeps the run of mismatches, the run of matches and the open incident. Two mismatches in a
       row open an incident; three matches in a row clear it.
    5. **Learning:** a matching frame whose similarity is at least the threshold plus 0.05, with
       no incident open, moves the baseline towards it by a weight of 0.02. A mismatch never moves
       it.
    6. **The anchor** (S2): after each learning step, when the baseline matches its anchor below
       0.75, learning stops for that kind and a `view_drifted` incident opens. Nothing more is
       learned for that kind until a new normal re-anchors it.
  - `classify(frame, baseline) -> ChangeType`, pure: `view_blocked` when the frame is
    featureless; `angle_changed` when phase correlation finds a whole-image shift and the shifted
    frame matches; `view_blurred` when its sharpness (variance of the Laplacian) falls below a
    quarter of the baseline's; otherwise `view_tampered`. `view_drifted` comes only from the
    anchor check. The starting values are named constants, pinned by tests on synthetic frames.
  - `set_normal(camera_id)` (S5): the camera's next frame of the current kind becomes that kind's
    baseline and anchor; the other kind's baseline is dropped and re-seeds from its next frame,
    under step 3's guard. Nothing is copied from an old frame of the other kind.
  - `acknowledge(incident_id, by, new_normal) -> Incident`: acknowledges the incident and its open
    alert, writes the audit action `scene_change.acknowledged`, and, with `new_normal`, calls
    `set_normal` for that camera.
  - `close(incident_id)` (S7): called when the incident's event goes to Trash. It closes the
    incident and resets the camera's runs, so a camera still covered opens a new incident on its
    next two frames.
  - Invariants: at most one open incident per camera; an incident's event is created once (its
    `batch_id` is `scene_change:<incident id>`, inserted `ON CONFLICT DO NOTHING`); a baseline is
    never moved by a featureless or mismatching frame, while an incident is open, or past its
    drift cap; frames are observed in capture order.
  - Errors: a frame that cannot be decoded is `skipped`, logged, and never fails the frame's
    detection. Configuration: `scene_change_enabled` (default on) and
    `SCENE_CHANGE_SIMILARITY_THRESHOLD` (default 0.90) beside `scene_change_resize_width`.
- **The incident's picture** (S3): opening an incident writes the frame it opened on, from the
  bytes already read, to an incident-owned file under the data volume
  (`scene_changes/<incident id>.jpg`), never pointing at the upload or at an extracted video frame,
  which the worker deletes (`backend/services/pipeline_workers.py:687-689`).
  `GET /api/scene-changes/{id}/image` serves it. The four readers that build an event's
  `thumbnail_url` from detection ids (`backend/api/routes/events.py:558-561`, `:1543-1544`,
  `:2115-2118`; `backend/services/search.py:393-394`) become source-aware: a `scene_change` event
  uses its incident's image, an external event stays without one. The purger deletes the file with
  its incident.
- **How an incident becomes an alert:** opening an incident inserts the event (the camera,
  `source` `scene_change`, no detections, no VLM; risk level high, and the risk score the top of
  the high band in `SeverityService`, so the two agree) and calls `AlertPipeline.process` after
  the commit; the minute sweep also selects undecided events whose source is `scene_change`.
  `4n-alerting.md`'s resolver gains the source `scene_change` with no verdict, rules' `sources`
  gain `scene_change`, and the seeded rule "Camera tampering" (all cameras, high, sources
  `scene_change`, a fixed UUID as "External alerts" has) is the only default rule that matches it.
  The activity key is the camera plus `scene_change`, so the rule's cooldown folds an incident that
  reopens within it. The alert's text names the type and the camera.
- **Its adapters:**
  - **The pipeline worker:** `_process_image_detection` reads each frame once and, with
    `scene_change_enabled` on, hands it to `observe` in a worker thread before detection and
    before the circuit breaker, so a detector outage does not blind it. Extracted video frames go
    the same way, each with its capture time. Frames of one camera are observed one at a time.
  - **HTTP:** `GET /api/scene-changes` lists incidents across cameras with server-side filters
    (camera, type, state: open, cleared, acknowledged or closed; time) and a cursor;
    `GET /api/cameras/{camera_id}/scene-changes` stays; `POST …/acknowledge` takes
    `{new_normal: bool}`; `POST /api/cameras/{camera_id}/scene-baseline` sets the new normal
    without an incident; `GET /api/scene-changes/{id}/image`. The person is the session's user.
  - **The alert pipeline and Trash:** acknowledging the alert from the Alerts page calls
    `acknowledge` on its incident, through the event; trashing the event calls `close`.
  - **Live messages:** `scene_change.detected`, `scene_change.cleared` and
    `scene_change.acknowledged`, sent through `get_broadcaster(redis)` as the alert pipeline sends
    its own, so they reach the header, the dashboard and the page.

## What changes

- **backend (`B4.9`):** `backend/services/scene_watch.py` (new); `scene_change_detector.py` keeps
  SSIM and its frame preparation and loses its in-memory baselines; `pipeline_workers.py` (the
  hook, with capture times); `backend/models/scene_change.py` (`event_id`, `cleared_at`,
  `closed_at`, `acknowledged_by`, `image_path`, the types `view_blurred` and `view_drifted`) and a
  new `scene_baselines` table (camera, kind, the prepared greyscale baseline, its anchor, the
  drift-capped flag, updated at, frames seen), one recorded upgrade; the incident image route and
  the source-aware thumbnail in `events.py` and `search.py`; the alerting resolver's source, rules'
  `sources` value and the seeded rule; `cameras.py` and a new `scene_changes.py` route module; the
  audit action; the purger's and Trash's hooks (`4n-trash.md`); `config.py`, `.env.example` and the
  compose `environment:` block (UR-9); `keep.toml`'s F-287 entry leaves, since the module gains a
  caller.
- **frontend (`F4.6`):** the header badge counts open, unacknowledged incidents; the dashboard
  indicator and toasts follow open and cleared; the camera modal lists the camera's incidents with
  their pictures and offers "Set as normal"; the Scene changes page reads `GET /api/scene-changes`
  with its filters and the state column, shows each incident's picture, and its Acknowledge dialog
  offers "This is the new normal"; a drifted incident's text asks to confirm the new normal; the
  Alerts page shows a tamper alert, with its picture, like any other (`F4.1`).
- **docs:** the glossary terms, and the camera-settings page of the operator docs (UR-81).
- **Not changed:** backups. Baselines and anchors are relearned after a restore, and the seeded
  rule's fixed UUID keeps a restore from duplicating it (`4n-restore.md`).

## Failure handling

- **A frame that cannot be checked** (decode error, wrong shape) is skipped and logged; its
  detection carries on.
- **A frame replayed late** (the dead-letter queue's requeue, `backend/api/routes/dlq.py:238-252`)
  is `skipped(stale)` by its capture time.
- **A baseline write that fails** keeps the baseline in memory and retries on the next match; an
  incident is still opened from the in-memory baseline.
- **A crash between the event's commit and `AlertPipeline.process`** is caught by the minute
  sweep's `scene_change` clause.
- **A restart with an incident open** reloads the open incidents and their mismatch state from
  `scene_changes` rows whose `cleared_at` and `closed_at` are null, so the incident neither reopens
  nor alerts again.
- **A change spread over many frames** is learned only until the anchor's 0.75 cap; past it,
  `view_drifted` opens and learning stops for that kind.

## Tests

- **Consolidation scope:** `scene_change_detector.py`, `backend/models/scene_change.py`, the scene
  change routes in `cameras.py`, `pipeline_workers.py`'s image path, `websocket_emitter.py`'s scene
  branches, the event readers' thumbnail code in `events.py` and `search.py`, and the frontend
  hooks and components named above (`useSceneChangeAlerts`, `useSceneChangeEvents`,
  `useSceneChangesQuery`, `SceneChangePanel`, `SceneChangesPage`, `SceneChangeIndicator`).
- **Tests through the interface:** `observe` on synthetic frame sequences:
  - seed, match, two mismatches open, a single mismatch does not, three matches clear, and a burst
    opens one incident;
  - a camera with only a day baseline given two black frames opens `view_blocked`, and a black or
    glare frame never seeds (S1);
  - the day-to-night switch never opens an incident, and a re-aimed view does not seed night;
  - drift: slow lighting change is learned, and a covering, turn and pan each spread over 1,000 to
    10,000 frames open `view_drifted` at the anchor cap rather than being absorbed (S2);
  - restart with an incident open; a stale frame is skipped (S6);
  - Trash closes the incident, and a still-covered camera reopens (S7).

  Also: `classify` for each type, with an unclassifiable change as tampered; `set_normal`
  re-baselines the current kind and re-seeds the other (S5); `acknowledge` with and without new
  normal, in both directions of the alert link; the event's `batch_id` conflict; a `scene_change`
  event's `thumbnail_url` in the list, Trash, detail and search readers (S3); the policy: armed
  alerts, unarmed records only, a critical rule pages while disarmed, and the cooldown folds a
  reopen.

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
baselines from its next featured frames of each kind, so nothing can alert until a camera has a
baseline. Switching the setting off stops all checks.

The previous release cannot read `view_blurred` or `view_drifted` (S4): a native enum value its
code does not know raises on read. So a code revert ships with one forward upgrade that rewrites
both to `view_tampered`, keeping the labels in the type, and a revert without it is not supported.
`B4.7`'s `events.source` and `alert_rules.sources` meet the same problem if they are native enums,
so this design asks that they be strings that older readers treat as unknown.

## Packages

| package | lane (proposed) | depends on                                          | contents                                                                                                                      | its own golden path   |
| ------- | --------------- | --------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- | --------------------- |
| `B4.9`  | backend         | `B4.7` merged (the event source and rule `sources`) | The module, the hook, baselines, incidents and their event, the source and seeded rule, the routes, the live messages, audit. | Backend pytest above. |
| `F4.6`  | frontend        | `B4.9`; `F4.1` for the alert rows                   | The badge, dashboard indicator and toasts, camera modal, Scene changes page and its Acknowledge dialog.                       | Playwright above.     |

Each runs the six steps as two PRs: a test-only consolidation PR, then the build.

## Review

An adversarial review (2026-10-22) and a fresh-context check of it found seven issues. The check
confirmed every review finding and found three more; every cite in "Where it starts" held at
`origin/main` `aec5580aa` but two, corrected here. The owner ruled on one (S2):

| #   | finding                                                                                                  | amendment                                                                                                                                         |
| --- | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| S1  | A covered lens has no colour, so its first frame seeded a missing night baseline, and no incident opened | Featureless frames are checked first: never seeded or learned, a mismatch once any baseline exists; a seed must agree with the other kind's edges |
| S2  | Slow learning absorbed a slow covering, turn or pan over 1,000–10,000 frames                             | An anchor per baseline and a 0.75 drift cap that stops learning and opens `view_drifted` (owner)                                                  |
| S3  | An event without detections has no thumbnail, and extracted video frames are deleted                     | The incident's own picture file and route; four source-aware thumbnail readers; the purger owns the file                                          |
| S4  | A code revert cannot read the new types                                                                  | A forward upgrade rewrites them before a revert; `B4.7`'s source fields as strings                                                                |
| S5  | "New normal" could teach the old view as the night baseline                                              | The current kind re-baselines from the next frame; the other kind is dropped and re-seeds                                                         |
| S6  | Frames replayed from the dead-letter queue could clear an open incident                                  | Frames are observed in capture order; a stale frame is skipped                                                                                    |
| S7  | Trashing an open incident's event left the camera silent                                                 | Trash closes the incident and resets the camera's runs                                                                                            |

## Done when

Each package: its golden path green on the fake stack and its real-tier check posted. The five
rows (F-008, F-030, F-208, F-287, F-288) read **works** once both packages have merged and the
real-tier check is posted.
