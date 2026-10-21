# 4n — Timeline Filters and Detections Design

> Step 1 of the Timeline feature package (`packages/backend.md`, "B4.\* Feature track"), copied
> from [`templates/feature-design.md`](templates/feature-design.md).

**Package:** `F4.4` (frontend leads; a small backend part in the same PR, UR-9) · **Inventory
rows:** F-044, F-055 · **R2 ruling:** complete, priority 1 (R2a rows 3 and 4) · **Designed:**
2026-10-21, with the owner

## Where it starts

Facts read at `main` `c75111487`.

- **The confidence filter does nothing.** "High Only (85%+)" and "Medium+ (70%+)"
  (`frontend/src/components/events/EventTimeline.tsx:1370-1373`) set state that is counted as an
  active filter, but the list pipeline only sorts (`:522-524`), and nothing is sent to
  `/api/events`.
- **The only confidence number the system produces is the detector's.** Each detection carries
  `confidence` (`backend/models/detection.py:49`). The VLM produces a risk score and a verdict,
  not a confidence.
- **A verdict filter already exists in the API.** `GET /api/events` takes `verdict`
  (`confirmed`, `rejected`, `uncertain`, `verification_failed`, or `none` for never verified;
  `backend/models/event_verification.py:50-64`). The timeline honours it only from a deep link
  (`EventTimeline.tsx:310-320`); the filter panel has no control for it.
- **The detected-objects list and the overlay never appear.** The modal reads `event.detections`
  (`frontend/src/components/events/EventDetailModal.tsx:463`, `:527`), but the timeline passes
  `detections: []` (`EventTimeline.tsx:1049`, `:1085`) and so does the Alerts page
  (`frontend/src/components/alerts/AlertsPage.tsx:325`). The detections the modal fetches from
  `GET /api/events/{event_id}/detections` (`backend/api/routes/events.py:2222`) are never copied
  in.
- **The overlay draws threats only.** `ThreatBoundingBox.tsx` boxes weapons, and the weapons model
  is off (OD-7).

## What the user can do when this is done

In the timeline's filters the user picks a minimum confidence (High 85%+, Medium+ 70%+, or any
detection) and a verification state (confirmed, uncertain, rejected, failed, never verified), and
the list changes. Opening an event shows its detected objects, each with its kind, a confidence
bar and its frame, with every object boxed on the frame it came from.

## Decisions

| question                                 | decision                                                                                                                                                     | why                                                                                             |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------- |
| Confidence in what?                      | The detector's: an event matches when its most confident detection is at or above the threshold. Applied by the API so it works with pagination.             | It is the only percentage the system produces; the VLM's risk score already has its own filter. |
| Should the VLM's view be filterable too? | Yes, as a separate Verification filter on the existing `verdict` parameter. "Verified in the cloud" joins when the cloud VLM step exists (`4n-alerting.md`). | Confidence says how sure a thing is there; verification says what the AI concluded.             |
| Which detections are boxed?              | Every detection, coloured by kind, with label and confidence, each on its own frame. A weapon draws red if OD-7 ever turns the weapons model on.             | A box only fits the frame it came from, and threats-only would draw nothing today.              |

## Shape

- **No new backend module.** `list_events` gains one query parameter; the `verdict` filter is
  reused unchanged.
- **Its interface:** `GET /api/events?min_confidence=<0..1>`. An event matches when any of its
  detections has `confidence >= min_confidence`; the frontend's "Any detection" sends `0` and
  means the event has at least one detection. Values outside 0 to 1 are a 422.
- **Frontend:** `DetectionOverlay` (generalised from `ThreatBoundingBox`) takes a frame image and
  its detections and draws `bbox_x`, `bbox_y`, `bbox_width`, `bbox_height` scaled to the image's
  displayed size. The modal's detected-objects list selects which frame the overlay shows.

## What changes

- **backend:** `backend/api/routes/events.py` (`list_events`'s `min_confidence`, joined through
  `event_detections`), its schema description, and the generated API types (regenerated, never
  hand-merged, UR-83).
- **frontend:** `EventTimeline.tsx` (send `min_confidence`; a Verification select driving
  `verdict`); `EventDetailModal.tsx` (fill the list from its own fetch); `DetectionOverlay`
  replacing `ThreatBoundingBox`; the timeline and Alerts page stop relying on the `detections: []`
  they pass.

## Tests

- **Consolidation scope:** `list_events` and its tests; `EventTimeline`, `EventDetailModal` and
  `ThreatBoundingBox` with their tests.
- **Tests through the interface:**
  - API: `min_confidence=0.85` includes an event whose best detection is 0.85 and excludes one at
    0.849; `0` includes only events with a detection; out-of-range values are a 422.
  - Frontend: each filter sends its parameter and the list reloads; the overlay places a box
    correctly at two display sizes; the modal lists the detections it fetched.

## Golden path

- **Spec (Playwright):** with seeded events whose best detections score 0.90 and 0.75, "High"
  shows one and "Medium+" shows both; "Rejected" shows the rejected seed; opening an event shows
  its objects and draws their boxes.
- **Fake-stack scenario:** seeded events with detections and frames, one with a rejected verdict.
- **Real-tier check:** the operator opens a real event and confirms the boxes sit on the objects.

## Privacy and security

No new data is stored or shown beyond what the event already holds. Under `EXPOSE_LAN` the routes
keep their existing authentication.

## Rollout and reversal

No migration. The new parameter is optional, so older clients are unaffected. Code reversal is a
revert.

## Done when

The golden path is green on the fake stack, the real-tier check is posted, and F-044 and F-055 read
**works**.
