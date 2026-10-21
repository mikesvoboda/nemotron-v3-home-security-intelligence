# 4n — Timeline Filters and Detections Design

> Step 1 of the Timeline feature package (`packages/backend.md`, "B4.\* Feature track"), copied
> from [`templates/feature-design.md`](templates/feature-design.md).

**Package:** `F4.4` (frontend leads; a small backend part in the same PR, UR-9) · **Inventory
rows:** F-044, F-055 · **R2 ruling:** complete, priority 1 (R2a rows 3 and 4) · **Designed:**
2026-10-21, with the owner

## Where it starts

Facts read at `main` `bc89bf68a`.

- **The confidence filter does nothing.** "High Only (85%+)" and "Medium+ (70%+)"
  (`frontend/src/components/events/EventTimeline.tsx:1370-1373`) set state that is counted as an
  active filter, but the list pipeline only sorts (`:522-524`), and nothing is sent to
  `/api/events`.
- **The only confidence number the system produces is the detector's.** Each detection carries
  `confidence` (`backend/models/detection.py:49`). The VLM produces a risk score and a verdict,
  not a confidence.
- **A verdict filter already exists in the API.** `GET /api/events` takes `verdict`
  (`confirmed`, `rejected`, `uncertain`, `verification_failed`, or `none` for never verified;
  `backend/models/event_verification.py:60`), applied as a correlated `EXISTS`
  (`verdict_filter_condition`, `:64`; `backend/api/routes/events.py:482`). The timeline honours it
  only from a deep link (`EventTimeline.tsx:310-320`); the filter panel has no control for it.
- **The detected-objects list and the overlay never appear.** The modal reads `event.detections`
  for its overlay (`frontend/src/components/events/EventDetailModal.tsx:463`, `:527`) and its
  detected-objects list (`:922-968`), but the timeline passes `detections: []`
  (`EventTimeline.tsx:1049`, `:1085`) and so does the Alerts page
  (`frontend/src/components/alerts/AlertsPage.tsx:325`). The detections the modal fetches from
  `GET /api/events/{event_id}/detections` (`backend/api/routes/events.py:2222`) are never copied
  in.
- **Only still images have a frame a box fits.** A still's boxes are in the original image's
  pixels, and `/api/detections/{id}/image?full=true` returns that image unchanged
  (`backend/api/routes/detections.py:1272`). A video detection's `file_path` is the video; its
  sampled frames are deleted after detection and no frame offset is stored, and `full=true` on a
  video returns a frame near the start, padded to 1920x1080 (`detections.py:1206-1229`). The
  default `/image` is a 320x240 thumbnail with the box already drawn in.
- **The overlay draws threats only.** `ThreatBoundingBox.tsx` boxes weapons, and the weapons model
  is off (OD-7). `DetectionImage` and `BoundingBoxOverlay` (`frontend/src/components/detection/`)
  already colour boxes by kind and scale through an SVG `viewBox` of the image's own size.

## What the user can do when this is done

In the timeline's filters the user picks a minimum confidence (High 85%+, Medium+ 70%+, or any
detection) and a verification state (confirmed, uncertain, rejected, failed, never verified), and
the list changes. Opening an event shows its detected objects, each with its kind and a confidence
bar. Picking one from a still image shows that image with every object on it boxed; one from a
video plays the clip.

## Decisions

| question                                 | decision                                                                                                                                                                                                                            | why                                                                                                        |
| ---------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Confidence in what?                      | The detector's: an event matches when any of its detections is at or above the threshold. Applied by the API so it works with pagination.                                                                                           | It is the only percentage the system produces; the VLM's risk score already has its own filter.            |
| Should the VLM's view be filterable too? | Yes, as a separate Verification filter on the existing `verdict` parameter. "Verified in the cloud" joins when the cloud VLM step exists (`4n-alerting.md`).                                                                        | Confidence says how sure a thing is there; verification says what the AI concluded.                        |
| Which detections are boxed?              | Every still-image detection, coloured by kind, with label and confidence, drawn on the original image with the other detections from the same file. Video detections are listed and play in the existing video player, with no box. | A box only fits the frame it came from, and no video frame is kept. Threats-only would draw nothing today. |
| Is the video frame stored for later?     | No. A follow-up that stores a frame offset and source size per detection is drafted only if real data shows video detections are common.                                                                                            | The audit has the cameras sending stills over FTP; the schema change would buy little today.               |

## Shape

- **No new backend module.** `list_events` gains one query parameter; the `verdict` filter is
  reused unchanged.
- **Its interface:** `GET /api/events?min_confidence=<0..1>`, declared
  `Query(None, ge=0.0, le=1.0)`, so values outside 0 to 1 are a 422. The filter is a correlated
  `EXISTS (SELECT 1 FROM event_detections ed JOIN detections d ON d.id = ed.detection_id WHERE
ed.event_id = events.id AND d.confidence >= :min)`, applied to the base query beside `verdict`
  so the count and the cursor see it. Never a join or `GROUP BY` on the event query, which would
  repeat an event once per detection. The existing indexes on `event_detections(event_id, …)` and
  `detections.id` serve it; no new index. The frontend's "Any detection" sends `0` and means the
  event has at least one detection (every writer sets `confidence`).
- **Frontend:** the modal shows the selected still on `DetectionImage` with `BoundingBoxOverlay`,
  loading `/api/detections/{id}/image?full=true` and passing every detection from the same
  `file_path`. `BoundingBoxOverlay` changes `preserveAspectRatio="none"` to `"xMidYMid meet"` so
  the boxes letterbox exactly as the image's `object-contain` does; a weapon draws red as a colour
  override. `ThreatBoundingBox` is retired. The event-thumbnail fallback never gets boxes.

## What changes

- **backend:** `backend/api/routes/events.py` (`list_events`'s `min_confidence`, an `EXISTS` on
  `event_detections` and `detections` mirroring `verdict_filter_condition`), its schema
  description, and the generated API types (regenerated, never hand-merged, UR-83).
- **frontend:** `EventTimeline.tsx` (send `min_confidence`; a Verification select driving
  `verdict`); `EventDetailModal.tsx` (fill the list from its own fetch; the still or the video
  for the selected detection); `BoundingBoxOverlay.tsx` (aspect ratio, weapon colour);
  `ThreatBoundingBox` removed; the timeline and Alerts page stop relying on the `detections: []`
  they pass.

## Tests

- **Consolidation scope:** `list_events` and its tests; `EventTimeline`, `EventDetailModal`,
  `BoundingBoxOverlay` and `ThreatBoundingBox` with their tests.
- **Tests through the interface:**
  - API: `min_confidence=0.85` includes an event whose best detection is 0.85 and excludes one at
    0.849; an event with three qualifying detections appears once and `total` counts it once,
    across cursor and offset pages; `0` includes only events with a detection; out-of-range
    values are a 422.
  - Frontend: each filter sends its parameter and the list reloads; the overlay places a box
    correctly in a letterboxed container at two display sizes; a video detection draws no box;
    the modal lists the detections it fetched.

## Golden path

- **Spec (Playwright):** with seeded events whose best detections score 0.90 and 0.75, "High"
  shows one and "Medium+" shows both; "Rejected" shows the rejected seed; opening an event shows
  its objects and draws their boxes on the still.
- **Fake-stack scenario:** seeded still-image events whose image files exist at `file_path`
  (`full=true` answers 404 otherwise), one with several detections and one with a rejected
  verdict.
- **Real-tier check:** the operator opens a real event and confirms the boxes sit on the objects.

## Privacy and security

No new data is stored or shown beyond what the event already holds. Under `EXPOSE_LAN` the routes
keep their existing authentication.

## Rollout and reversal

No migration. The new parameter is optional, so older clients are unaffected. Code reversal is a
revert.

## Review

An adversarial review (2026-10-21) and a fresh-context check of it found two issues; every cite
held at `origin/main` `bc89bf68a`. The owner ruled on the second:

| #   | finding                                                  | amendment                                                                                                 |
| --- | -------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| L1  | A join through detections repeats events in counts/pages | A correlated `EXISTS` on the base query, as `verdict` does; a test for one event with several detections  |
| L2  | Video detections keep no frame to draw on                | Boxes on still images only, over the original; video listed and played without a box (owner, stills only) |

## Done when

The golden path is green on the fake stack, the real-tier check is posted, and F-044 and F-055 read
**works**.
