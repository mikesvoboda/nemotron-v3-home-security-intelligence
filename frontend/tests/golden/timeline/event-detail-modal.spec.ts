/**
 * FE-3 golden paths (F2.3): F-054 (event detail modal, Details tab).
 *
 * Row clause (verbatim from docs/reference/feature-inventory.md:190):
 *   F-054 "Event detail modal › Details tab `/timeline` — opens an event (also
 *          from `/alerts`); sees the header badges (verdict, risk, notify,
 *          snooze), the detection thumbnail strip, the selected image or video
 *          with lightbox, AI summary, risk breakdown, VLM verification (scene,
 *          criteria, reviewed frames) and metadata; steps prev/next with the
 *          arrow keys; prints"
 *
 * `?event=` DEEP LINK IS THIS ROW'S, NOT A NEIGHBOUR'S. timeline/event-list.spec.ts
 * disclaims it ("the `?event=` deep link … belongs to F-054's modal row, not this
 * one"), and EventTimeline.tsx:329-334 is the shipped door: it reads `event`,
 * validates it with parseEventId and calls setSelectedEventForModal.
 *
 * ONE DROPPED EVENT CARRIES THE CONTENT CLAUSES — everything the clause names is
 * VLM-tier, and only the sanctioned drop path produces it. A `POST /api/events/
 * bulk` row has NO detection: the bulk builder never sets `detection_ids`
 * (backend/api/routes/events.py:1551-1560) and the column defaults NULL, so
 * `GET /api/events/{id}/detections` answers `items: []` and ThumbnailStrip
 * `return null` on an empty list (ThumbnailStrip.tsx:69); harness.ts says its own
 * rows read `verification: null`. So DETAIL_ROWS-style rows cannot show a strip,
 * an image, or a verification section at all. The scenario choice is a RESOURCE
 * CLAIM: the book's `person-at-door` bytes are F2.1's (analytics-alerts/harness.ts
 * claims them) and the fake's scenario key is the image's CONTENT DIGEST
 * (backend/ai_contract/fake/scenarios.py:56-62 rejects two scenarios sharing an
 * image), with dedupe holding a dropped file for `dedupe_ttl_seconds` = 300
 * (backend/core/config.py:2089-2092) and the file watcher SKIPPING the duplicate
 * outright (backend/services/file_watcher.py:871-878, `return` — not a delay). So
 * this spec drops `cat-on-porch`, which analytics-alerts/harness.ts leaves
 * unclaimed, and reuses the newest verified row already on that camera when the
 * 300 s window suppresses its own drop — reusing a row with IDENTICAL content is
 * sound because every assertion mirrors the API row into the DOM and the beforeAll
 * gate proves that row matches the book.
 *
 * THE FOUR-CLAUSE BADGE SET, AND WHERE TWO OF THEM ACTUALLY LIVE. Header column
 * is EventDetailModal.tsx:619-646 and MEASUREMENT beats the component's own
 * intent here:
 *   • risk — `<div data-testid="risk-score">` :626 holds RiskBadge iff
 *     `riskLevel !== null` :627, else VerdictBadge :635. `riskLevel` is
 *     `event.risk_score === null ? null : getRiskLevel(event.risk_score)` :540 —
 *     derived from the SCORE by the shipped thresholds (utils/risk.ts:95-105,
 *     LOW_MAX 29 / MEDIUM_MAX 59 / HIGH_MAX 84), NOT the server's `risk_level`
 *     column (that word is `resolveRiskLevel`'s job and this component never calls
 *     it). So the badge tier is a client computation over the server's score, and
 *     the leg pins both the score and the tier it implies. RiskBadge's own strings
 *     are `${label} (${score})` and `Risk level: ${label}, score ${score}`
 *     (RiskBadge.tsx:62-69); measured on the drop: "Low (4)" /
 *     "Risk level: Low, score 4".
 *   • verdict — VerdictBadge carries NO data-testid (common/VerdictBadge.tsx):
 *     it is `<span role="status" aria-label="Verification verdict: <Label>"
 *     data-verdict="<verdict>">` + text. Measured inside the modal: exactly one,
 *     aria "Verification verdict: Rejected", data-verdict "rejected", text
 *     "Rejected", rendered by EventVerificationSection.tsx:49. The spec's earlier
 *     `verdict-badge` / `verification-verdict-badge` testids do not exist in
 *     frontend/src at all — the claim is fixed to the shipped instrument.
 *   • notify — `<NotifyBadge notify={event.notify} size="md" />` :625. It renders
 *     NOTHING unless a decision exists, and its attribute is
 *     `data-notify={notify ? 'yes' : 'no'}` (common/NotifyBadge.tsx:46) — NOT
 *     "true"/"false", which is what an earlier draft asserted. The cat row's
 *     decision is `false`, so the shipped pair is aria "Notification decision:
 *     Not notifying" + data-notify="no" + text "Not notifying"; measured on the
 *     wire: `notify: false`. Both branches are pinned by a pure mapping table so
 *     the row's own value selects which one the DOM must show.
 *   • snooze — SEE "THE SNOOZE BADGE CANNOT RENDER ON /timeline" BELOW. The
 *     footer's SnoozeButton is driven and the STORED decision is asserted; the
 *     badge itself is F-080's /alerts surface.
 *
 * THE SNOOZE BADGE CANNOT RENDER ON /timeline — PROVEN, AND THE CONTROL THAT
 * PROVES IT IS A CONTROL. `ModalEvent` declares `snooze_until?` (EventDetailModal
 * .tsx:128-129) and the header's `<SnoozeBadge snoozeUntil={event.snooze_until}>`
 * :621 renders null while it is empty (common/SnoozeBadge.tsx `if (!isCurrently
 * Snoozed) return null`). But `getModalEvent()` (EventTimeline.tsx:1060-1090) —
 * the projection that builds the modal's props on THIS surface — never sets the
 * key: grepping its body for `snooze` yields nothing, while the OTHER caller that
 * does pass it is the ROW LIST (EventTimeline.tsx:1687, for EventList) and
 * AlertsPage.tsx:274/:330. Measured on the held stack, three ways: after the UI
 * click stored the snooze (`GET /api/events/4` → snooze_until
 * "2026-10-15T21:29:40.669Z", version 6), the badge count stayed 0 at +0.3 s,
 * +1.5 s, +4 s and +8 s; after a full RELOAD it was still 0; and the button's
 * `aria-label` stayed "Snooze event" (it becomes "<status>. Click to change."
 * when snoozed, SnoozeButton.tsx:151) and its menu still offered NO
 * `unsnooze-option` (SnoozeButton.tsx:205-213 mounts that item only
 * `currentlySnoozed`). A row known-snoozed on the wire is therefore the negative
 * control: if the projection ever hands the key over, the badge appears, the
 * aria-label changes and `unsnooze-option` mounts, and this leg reddens naming
 * it. Snooze RESIDUE IS CLEARED, NOT FATAL: a run that died between its snooze
 * click and its restore would leave a value, and throwing there would redden
 * every LATER run over state this fixture owns, so beforeAll unsnoozes the row
 * through the client's own route and re-reads it. The stored half of the clause
 * IS asserted, and it is asserted against
 * value-reachability rather than a boolean key: the client's list query is
 * `useEventsInfiniteQuery({filters, limit: 20})` (EventTimeline.tsx:182-184)
 * against a server default of `limit: 50` (events.py:299) and `ORDER BY
 * started_at DESC, id DESC` (:479), so a UI-stored snooze reaches the modal's own
 * row within the measured 24-event list (page 1 == the limit-50 read), while
 * pinning the INSTANT would need a 21-event window that turns false at 30 — the
 * kind of threshold this package's last review corrected. Cleanup is a wire
 * unsnooze PATCH (api.ts:2514 does the same), because the UI's unsnooze door is
 * unreachable for the reason above.
 *
 * THE ARROW STAGE IS SEED-IT-YOURSELF, NOT BORROWED. `handleNavigate`
 * (EventTimeline.tsx:966-979) walks `filteredEvents`, which is
 * `pipe(getSortTransform<Event>(sortOption))(events)` :523 with the default
 * `sortOption` `'newest'` :104 → `sortByDate('desc')` (utils/pipeline.ts:284-156)
 * — the same order the server already answers, so the modal's walk order is the
 * list order. Booting `?camera=<this camera>` would make `filteredEvents` hold
 * only that camera's rows, so the old draft's "step left, the camera changes" was
 * an out-of-range no-op with a false assertion on top; these legs boot `?event=`
 * with NO camera filter and RECOMPUTE the expected order from the server's own
 * rows and name map (mirror-the-response) rather than assuming it. WHAT THEY WALK
 * IS NOW SEEDS THIS FILE OWNS: beforeAll's `seedWalkRows` posts a small
 * detection-less set onto this run's own camera through the sanctioned bulk route,
 * dated older than the drop so the drop is the list's newest row. That replaced a
 * version that counted on the stack's SEED rows (`person_at_door`,
 * `harness_smoke`) being present — FALSE on any boot that has already run the Full
 * Database Reset in ../operations/test-data.spec.ts (marker 58 of 104), whose
 * handler runs unqualified `delete(Event)`/`delete(Detection)`/`delete(Camera)`
 * (backend/api/routes/admin.py:702-710) and restores only cameras. Since the
 * golden project is serial in sorted file order (playwright.config.ts:289-290) and
 * this file is 86 of 99, EVERY one of its rows is one it seeded itself. The set is
 * two seeded rows plus the drop: enough that each direction gets a REAL key step
 * and a REAL button step before its bound, and small enough to sit inside the
 * client's `limit=20` page the legs hold it to as a precondition. The drop and the
 * seeds share ONE camera, so the header camera word is the same string for every
 * row — which is exactly why each step is witnessed by the metadata block's unique
 * Event ID and not by the camera word. There are NO disabled flags to read:
 * EventDetailModal never disables `Previous event`/`Next event` (:1263/:1272), the
 * only in handleNavigate's guard (:971-975), so at its end each leg CLICKS both
 * doors and asserts the row did not move — an activation the shipped code must
 * ignore, by the same instruments that moved one row per press one step earlier.
 * THE TWO DIRECTIONS ARE TWO TESTS, NOT ONE LEG: a single leg that pressed both
 * keys could report green with one direction dead (its own sweeps would cover the
 * other's moves), and the row's clause names both. Each test owns ONE direction: it
 * deep-links the row at the end that direction walks AWAY from (first row for
 * ArrowRight, last row for ArrowLeft — the shipped `?event=` door positions it, so
 * neither leg spends a press of the opposite key to get into position), sweeps one
 * row per press to its own end, drives its LAST step through the FOOTER BUTTON so
 * each direction has a mover witness and not only an ignored click, then asserts
 * its bound. Neither leg presses the other direction's key at all.
 *
 * CLOSING THE LIGHTBOX CLOSES THE MODAL TOO — MEASURED, NOT ASSUMED. Lightbox's
 * document keydown handles Escape (:101) and EventDetailModal has its OWN
 * document keydown that closes the modal on Escape with no lightbox guard
 * (:399-410). So one Escape dismisses both: measured `lightbox: 0, modal: 0`.
 * The close BUTTON is the lightbox-only door (its onClose is :1361) and is what
 * the lightbox legs use; Escape is asserted as the shipped both-closes
 * behaviour.
 *
 * PRINT: THE PAGE'S OWN SHIPPED SHEET, NO INJECTION. An earlier draft read
 * `frontend/tailwind.print.css` and died with ENOENT in EVERY leg. That file has
 * never existed: `git ls-files` finds no `tailwind.print.css` and package.json has
 * no `build:css` script. The real supply chain is src/main.tsx:9 →
 * src/styles/index.css:1 (`@import './print.css'`) → src/styles/print.css:14
 * (`@media print {`), and the stack serves a BUILT bundle, so the rules are
 * already in the browser: measured without any injection, `styleTags: 1,
 * linkTags: 1, printRules: 25`. Under `emulateMedia({media:'print'})` the modal
 * panel goes 896x807 → 1248x1270 (print.css:403 makes it the page) and the
 * hidden set is header, nav, the Headless UI backdrop, EVERY button
 * (`button:not(.print-button)` :61 — so close/print/snooze/prev/next), the modal
 * FOOTER (:435) and the tab strip (:424), while the panel, the media, the AI
 * summary, the verification section and the risk badge all stay. Back on screen
 * all of it returns. THE TAB STRIP CLAIM IS THEREFORE FIXED: the old draft said
 * the strip "carries no print-hidden class, so it WOULD print" — false; print.css
 * :424 (`[data-testid='event-detail-modal'] .border-b button`) hides it. What
 * cannot be witnessed is the paper: headless Chromium has no print preview, so no
 * leg asserts anything about `window.print()` firing (the button's only handler,
 * :1326-1334) — that would be a 0-vs-0 mirror (UR-128).
 *
 * THREE THINGS THIS FILE CANNOT HONESTLY COVER, EACH PROVEN ON THE WIRE on this
 * row's held stack (`/tmp/fe3-stacks/f054`, 2026-10-15, admin session cookie).
 * All three are storage/scenario facts of the stack, not choices:
 *   1. NO PIXEL FROM A THUMBNAIL OR A REVIEWED FRAME. The strip's `<img src>` is
 *      `/api/detections/<id>/image` (EventDetailModal.tsx:219-233,
 *      `getDetectionImageUrl`) and the reviewed frame's is
 *      `/api/detections/<id>/thumbnail` (EventVerificationSection). Both routes
 *      must GENERATE on this stack, because `thumbnail_path` is NULL for a
 *      pipeline detection and the backend container is `read_only: true` with
 *      tmpfs only on /tmp and /home/appuser/.cache, so the write fails and
 *      `generate_thumbnail` returns None. Measured, detection 4:
 *        GET /api/detections/4/thumbnail → 500 "Failed to generate thumbnail image"
 *        GET /api/detections/4/image     → 500 (same)
 *        GET /api/detections/4/image?full=true → 200 image/jpeg 52907 B (this one
 *                                            only READS file_path, detections.py:1211)
 *      Measured in the DOM: the strip's `<img>` is `src=/api/detections/4/image`
 *      with naturalWidth 0, the reviewed frame is `src=/api/detections/4/thumbnail`
 *      with naturalWidth 0. So both are asserted as the SHIPPED CONTRACT (one img
 *      per server item, the shipped src and alt) and never as a decoded pixel.
 *      `?full=true` is the one path that answers, and it is what the selected
 *      media and both lightboxes use (getDetectionFullImageUrl) — so those legs DO
 *      assert naturalWidth > 0 (measured 640).
 *   2. THE "OR VIDEO" HALF HAS NO SUPPLIER. All five book images are stills, so
 *      media_type is "image" and the VideoPlayer branch is unreachable. Wire:
 *      `GET /api/detections/4/video` → 500 "[Errno 30] Read-only file system:
 *      'data/transcoded_cache'" and `GET /api/detections/4/video/thumbnail` → 400
 *      "Detection 4 is not a video (media_type: image)". The leg asserts the
 *      shipped IMAGE branch and the row's own `media_type`, and names this.
 *   3. PRINTED PAPER, as above.
 *   Also NOT this file's: "(also from `/alerts`)" — that door is F-080's and is
 *   already driven (analytics-alerts/alerts.spec.ts opens this same modal from an
 *   alert card). Nothing here duplicates or claims it.
 *
 * WHAT THE DETAILS TAB SHOWS, and what it structurally cannot. The modal gets
 * a PROJECTION of the list row (EventTimeline.tsx:1101-1129):
 *   no `detections` key → the "Detected Objects" block (:893) is driven by the
 *     modal's OWN fetch (useEventDetectionsQuery, EventDetailModal.tsx:212) since
 *     F4.4 — it renders for events with server detections (asserted below), not
 *     from the projection
 *   no `image_url`/`thumbnail_url` → `imageUrl` :751 is empty and the
 *     event-level fallback branch :774+ is dead; the media is the selected
 *     DETECTION's (:755-772)
 *   no `scene_caption` → `scene-caption-section` :888 is absent, though the scene
 *     description IS shown via verification (:924)
 *   no `entities`/`flags`/`recommended_action`/`confidence_factors` → the
 *     breakdown's only populated input is `reasoning` :910, which is why
 *     RiskFactorsBreakdown renders at all (hasReasoning :172) and why its content
 *     sits behind a collapsed toggle (:163, :204)
 * `verification` :1077 and `risk_score` :1072 DO ride, so those clauses are live.
 * (The list response DOES carry risk_factors/confidence_factors/entities/flags,
 * measured — it is the PROJECTION that drops them, not the API.)
 *
 * TWO FORMATTERS, NOT ONE (an earlier draft conflated them):
 *   • the modal header's timestamp is `formatTimestamp` :469-483,
 *     `toLocaleString('en-US', {month:'long', day:'numeric', year:'numeric',
 *     hour:'numeric', minute:'2-digit', second:'2-digit', hour12:true})` with NO
 *     timeZone — browser-local. Measured "October 15, 2026 at 7:18:16 PM" for a
 *     row stamped 19:18:16.523Z, i.e. the BROWSER ran at UTC (container
 *     /etc/localtime → Etc/UTC) and the browser's fractional-seconds default
 *     DROPS the `.523`. `Date.parse` of that string is NaN, so the leg asserts the
 *     exact text built in the browser through the shipped option list (the
 *     timeline-scrubber.spec.ts:401 precedent for browser-side locale), and its
 *     tolerance is a whole minute — the formatter has no sub-second field.
 *   • the strip's per-entry timestamp is ThumbnailStrip's OWN formatter
 *     (:73-86): `hour:'2-digit', minute:'2-digit', second:'2-digit',
 *     hour12:false, timeZone:'UTC'` → measured
 *     "View detection 1 at 19:18:16. Double-click to enlarge."
 * NOT asserted here, with reasons (UR-128): the /alerts door (F-080); the video
 * branch; a decoded thumbnail or reviewed-frame pixel; printed paper; the snooze
 * BADGE (projection, above); `lightbox-counter`'s rendered text (it is absent for
 * a one-image lightbox, Lightbox.tsx:140/:196, so there is nothing to mirror); the
 * clip/analysis/audit tabs (other rows).
 */
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import type { Page } from '@playwright/test';

import { GUARD_MESSAGE, expect, test } from '../guard';

import {
  adminSession,
  apiShell as api,
  apiWrite,
  closedByGuard,
  hardDeleteFixtureRows,
  openTimelineEventModal,
  quietBoot,
  readTimelineHarness,
  setMode,
  settledReload,
  type Session,
  type TimelineHarness,
} from '../harness';

/* ----------------------------- the scenario claim -------------------------- */

interface Scenario {
  name: string;
  image: string;
  detections: { class: string; confidence: number }[];
  verdict: {
    verdict: string;
    risk_score: number;
    summary: string;
    reasoning?: string;
    description?: string;
    criteria?: { name: string; passed: boolean; evidence?: string }[];
    provenance?: { engine?: string; model_id?: string };
  };
  reply_delay_seconds?: number;
}

interface DropHarness {
  ready: true;
  scenario: Scenario;
  scenarioImagePath: string;
  cameraRoot: string;
  cameraId: string;
  timeline: TimelineHarness;
}

type DropState = DropHarness | { ready: false; why: string };

/** The scenario nobody else claims and whose tier still puts it on /timeline. */
const CLAIMED_SCENARIO = 'cat-on-porch';

/**
 * Collection-time and defensive like readTimelineHarness(): Playwright runs
 * COLLECTION before any runtime skip, so a missing file is a skip reason here,
 * never a `--list` crash outside the harness.
 */
function readDropHarness(): DropState {
  const timeline = readTimelineHarness();
  if (!timeline.ready) return timeline;
  const bookPath = process.env.FEATURE_CHECK_SCENARIOS;
  const camerasPath = process.env.FEATURE_CHECK_CAMERAS;
  const cameraRoot = process.env.FEATURE_CHECK_CAMERA_ROOT;
  if (!bookPath) return { ready: false, why: 'missing FEATURE_CHECK_SCENARIOS' };
  if (!camerasPath) return { ready: false, why: 'missing FEATURE_CHECK_CAMERAS' };
  if (!cameraRoot) return { ready: false, why: 'missing FEATURE_CHECK_CAMERA_ROOT' };
  if (!existsSync(bookPath)) return { ready: false, why: `no scenario book at ${bookPath}` };
  if (!existsSync(camerasPath)) return { ready: false, why: `no cameras file at ${camerasPath}` };
  let scenarios: Scenario[];
  let cameras: Record<string, string>;
  try {
    scenarios = (JSON.parse(readFileSync(bookPath, 'utf8')) as { scenarios: Scenario[] }).scenarios;
    cameras = JSON.parse(readFileSync(camerasPath, 'utf8')) as Record<string, string>;
  } catch (error) {
    return { ready: false, why: `harness JSON unreadable: ${String(error)}` };
  }
  const scenario = scenarios.find((entry) => entry.name === CLAIMED_SCENARIO);
  if (!scenario) return { ready: false, why: `scenario book has no ${CLAIMED_SCENARIO}` };
  if (scenario.reply_delay_seconds) {
    return {
      ready: false,
      why: `${CLAIMED_SCENARIO} delays its reply, so it never lands a verdict`,
    };
  }
  const cameraId = cameras[scenario.name];
  if (!cameraId) return { ready: false, why: `harness seeded no camera named ${scenario.name}` };
  const scenarioImagePath = path.join(path.dirname(bookPath), scenario.image);
  if (!existsSync(scenarioImagePath)) {
    return { ready: false, why: `no scenario image at ${scenarioImagePath}` };
  }
  return {
    ready: true,
    scenario,
    scenarioImagePath,
    cameraRoot,
    cameraId,
    timeline,
  };
}

const h = readDropHarness();
test.skip(!h.ready, h.ready ? '' : h.why);
const harness = h as DropHarness;
const timeline = harness.timeline;
const scenario = harness.scenario;

/** The badge tier the CLIENT derives from the server's score — the shipped
 *  thresholds (src/utils/risk.ts:80-84, :95-105), which EventDetailModal.tsx:540
 *  applies. Derived here so a change to the book reddens the leg that names the
 *  wrong tier, and so this file never re-derives the tier from risk_level (which
 *  the component does not do). */
const RISK_THRESHOLDS = { LOW_MAX: 29, MEDIUM_MAX: 59, HIGH_MAX: 84 } as const;
function riskLevelFromScore(score: number): string {
  if (score <= RISK_THRESHOLDS.LOW_MAX) return 'low';
  if (score <= RISK_THRESHOLDS.MEDIUM_MAX) return 'medium';
  if (score <= RISK_THRESHOLDS.HIGH_MAX) return 'high';
  return 'critical';
}
const LABELS: Record<string, string> = {
  low: 'Low',
  medium: 'Medium',
  high: 'High',
  critical: 'Critical',
};
const VERDICT_LABELS: Record<string, string> = {
  confirmed: 'Confirmed',
  rejected: 'Rejected',
  uncertain: 'Uncertain',
  verification_failed: 'Verification failed',
};
const serverRiskLevel = riskLevelFromScore(scenario.verdict.risk_score);
const riskBadgeText = `${LABELS[serverRiskLevel]} (${scenario.verdict.risk_score})`;
const riskBadgeAria = `Risk level: ${LABELS[serverRiskLevel]}, score ${scenario.verdict.risk_score}`;
const verdictLabelText = VERDICT_LABELS[scenario.verdict.verdict];

/** The shipped NotifyBadge pair for a decision, both branches (the row's own
 *  value picks which the DOM must show; common/NotifyBadge.tsx:41-51). */
const notifyContract = (notify: boolean) => ({
  aria: `Notification decision: ${notify ? 'Notifies' : 'Not notifying'}`,
  attr: notify ? 'yes' : 'no',
  text: notify ? 'Notifies' : 'Not notifying',
});

/** scripts/feature-check.sh lives at the repo root: FOUR up from
 *  frontend/tests/golden/timeline (dashboard-drop.spec.ts:121 is three up —
 *  this file is one level deeper). */
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../..');

/* ------------------------------- the shapes -------------------------------- */

interface Verification {
  verdict: string;
  scene_description: string | null;
  criteria: { name: string; passed: boolean; evidence: string | null }[];
  key_frame_detection_ids: number[];
  engine: string | null;
  model_id: string | null;
  latency_ms: number | null;
}

interface EventRow {
  id: number;
  camera_id: string;
  started_at: string;
  risk_score: number | null;
  risk_level: string | null;
  summary: string | null;
  reasoning: string | null;
  version: number;
  reviewed: boolean;
  snooze_until: string | null;
  detection_ids: number[];
  verification?: Verification;
  notify?: boolean;
}

interface DetectionItem {
  id: number;
  detected_at: string;
  object_type: string | null;
  confidence: number | null;
  media_type: string | null;
  thumbnail_path: string | null;
}

interface CameraRow {
  id: string;
  name: string;
}

const eventRow = (session: Session, id: number) =>
  api<EventRow>(timeline, session, `/api/events/${id}`);
const detectionItems = (session: Session, id: number) =>
  api<{ items: DetectionItem[]; pagination: { total: number } }>(
    timeline,
    session,
    `/api/events/${id}/detections?limit=100`
  );
const cameraRows = (session: Session) =>
  api<CameraRow[] | { items: CameraRow[] }>(timeline, session, '/api/cameras');
/** The list route the page itself reads. The CLIENT sends limit=20
 *  (EventTimeline.tsx:182-184) and the server DEFAULT is 50 (events.py:299); both
 *  answer `ORDER BY started_at DESC, id DESC` (events.py:479). Read the whole
 *  first page at limit=100, which the walk legs then bound to the client's 20 as
 *  an explicit precondition. An earlier note here claimed "the measured stack
 *  holds 4 rows, so page 1 is the whole list" — FALSE after the boot's Full
 *  Database Reset (../operations/test-data.spec.ts, marker 58 of 104): that reset
 *  runs unqualified `delete(Event)`/`delete(Detection)`/`delete(Camera)`
 *  (backend/api/routes/admin.py:702-710) and restores only CAMERAS, so every file
 *  sorting after it — this one included (file 86) — boots to an EMPTY event table
 *  and the rows in this list are exactly the ones the timeline specs have seeded.
 *  That is the reason this file seeds its own walk rows (see seedWalkRows) rather
 *  than borrowing the stack's. */
const eventList = (session: Session, limit = 50) =>
  api<{ items: EventRow[] }>(timeline, session, `/api/events?limit=${limit}`);

/**
 * The metadata block's Revision row, pinned to the value the modal can actually
 * have — and the instrument that replaced an EARLIER, WRONG version of this
 * helper, which polled for equality with `GET /api/events/{id}` and timed out at
 * `printed "Rev. 1", wire Rev. 3`. The measured truth, on this stack, is that they
 * are NEVER equal, and the reason is worth the paragraph because it is the shipped
 * behaviour being witnessed rather than a flake being soothed:
 *
 *   • The modal's row is a PROJECTION of the LIST route (`getModalEvent`,
 *     EventTimeline.tsx:1060-1090), and `list_events` builds its item dict BY
 *     HAND (backend/api/routes/events.py:513-567) — `id`, `camera_id`,
 *     `started_at`, `reviewed`, `notes`, `verification`, `notify`… and NO
 *     `version` key. The dict is re-validated against `EventResponse`, whose
 *     `version` is `Field(1)` (api/schemas/events.py:167-170), so EVERY row the
 *     list route answers carries version **1** regardless of the column.
 *   • `GET /api/events/{id}` (the single read) DOES pass `version=event.version`
 *     (events.py:1966), so it reports the true 3/4/5.
 *   • Proved discriminating, not a frozen response: after a PATCH that set
 *     `reviewed=true`, the list route answered `reviewed: true` (live) while
 *     `version` stayed 1 and the single read moved 3→4. A stale cache would have
 *     frozen reviewed too — so this is the projection, not the 60 s cache.
 *   • Nothing can heal it client-side either: `snoozeEvent`/`clearSnooze`
 *     (services/api.ts:2500-2514) call `updateEvent` WITHOUT a `version`, so the
 *     server's 409 branch (events.py:2018-2027) never fires, and the modal keeps
 *     rendering the list projection.
 *
 * So the row the modal prints is the shipped behaviour: `Rev. 1`. Asserting the
 * single read's value would assert a number no modal can show, and would be red
 * forever — that IS the finding, recorded here rather than hidden by deleting the
 * check. The witness keeps its teeth two ways: it is EXACT equality against the
 * list route's own key-by-key value for THIS row (so a modal that printed a
 * revision the list never said is red), and it is paired in each caller with the
 * camera word, which the same projection fills from a live `camera_id`.
 */
const revisionMatchesList = async (page: Page, session: Session, id: number) => {
  // Poll until the row is IN the list answer, then compare the printed Revision to
  // what THAT answer says — assertion against the source the widget is built from.
  // Why poll rather than read once: the row can still be UNCOMMITTED, not
  // unfresh. `list_events` performs ZERO cache reads or writes (the whole handler,
  // events.py:283-598, touches no cache; caching on this router lives only on
  // /stats :599, /timeline-summary :753 and /clusters :914, and there is no
  // CacheKeys.event_list), so an empty or short answer here is the TRUE current
  // state, and the only thing that changes it is the write landing. An earlier note
  // blamed a 60 s SHORT_TTL snapshot on this route — that cache is real but sits on
  // the OTHER routes, and this poll is a commit-readiness wait, not a
  // cache-freshness wait. The distinction matters because a reader who believes the
  // cache story would "fix" a slow poll by adding a key, which cannot help a route
  // that never consults one.
  await expect
    .poll(
      async () => {
        const [printed, list] = await Promise.all([
          metaValue(page, 'Revision'),
          eventList(session, 100),
        ]);
        const row = list.items.find((r) => r.id === id);
        if (!row) return `row ${id} not in the list answer yet`;
        const want = `Rev. ${row.version}`;
        return printed === want ? '' : `printed ${JSON.stringify(printed)}, list says ${want}`;
      },
      {
        timeout: 90_000,
        message:
          'the printed Revision row must equal what the LIST route answers for ' +
          'this row (the projection source); the difference follows, empty = agree',
      }
    )
    .toBe('');
  // And the frozen-value claim itself, asserted rather than narrated: whatever the
  // column holds, the modal shows the list route's constant.
  expect(
    await metaValue(page, 'Revision'),
    'the list projection carries the schema default revision'
  ).toBe('Rev. 1');
};

/** The modal header's own formatter (EventDetailModal.tsx:469-483), run in the
 *  BROWSER so locale and time zone are the ones that render the pixels. It is
 *  given the row's own ISO instant, the same input `event.timestamp` carries
 *  (EventTimeline.tsx:1071 hands over `started_at`). */
const headerLabelIn = (page: Page, iso: string) =>
  page.evaluate(
    (value) =>
      new Date(value).toLocaleString('en-US', {
        month: 'long',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        second: '2-digit',
        hour12: true,
      }),
    iso
  );

/** ThumbnailStrip's OWN formatter (:73-86) — fixed UTC, 24-hour, zero-padded, so
 *  this one CAN be built in Node. */
const stripLabel = (iso: string) =>
  new Date(iso).toLocaleString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
    timeZone: 'UTC',
  });

const percent = (confidence: number | null) => `${Math.round(Number(confidence) * 100)}%`;

/* ------------------------------- fixtures ---------------------------------- */

let dropEventId: number;
let cameraName: string;
/** This run's own drop, deleted in afterAll; a reused row is left for its owner. */
let ownedEventIds: number[] = [];

/** Rows on the drop camera AFTER beforeAll, newest-first, with the server's own
 *  names — so a stale row from an earlier run changes the arrow walk and the
 *  legs notice rather than silently indexing a shifted list. */
let walk: { id: number; camera: string }[] = [];

/** The seeded walk set is two rows. WHY TWO: an arrow leg needs three positions
 *  to witness both of its instruments — the shipped `handleNavigate` guard fires
 *  only at the bounds (:971-975), so with two total rows there is exactly ONE
 *  step available per direction and each leg's escape hatch gives that single
 *  step to the KEY, leaving the footer BUTTON witnessed only as
 *  "enabled-and-ignored". Three rows (two seeds + the drop) buy a real key step
 *  AND a real button step before the bound, which is what the row's clause names.
 *  WHY NOT MORE: the client's page is `limit=20` (EventTimeline.tsx:182-184) and
 *  both legs assert the walk fits in one page, so the whole unfiltered list has
 *  to stay under 20 — every extra seed spends that budget. */
const WALK_SEED_ROWS = 2;

/** Ids this run seeded, reported by the bulk route itself. */
let seededWalkIds: number[] = [];

/** Raw fetch rather than apiWrite, and it must carry the session cookie itself —
 *  apiWrite adds that header for you, which is exactly why the hand-rolled call
 *  that replaced it would otherwise post UNAUTHENTICATED and report a 401 as if
 *  the fixture were broken. (Caught by tsc's unused-parameter rule: `session` was
 *  declared and never used, which is the same fact stated twice.) */
const postBulk = (session: Session, body: string) =>
  fetch(`${timeline.api}/api/events/bulk`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Cookie: `${session.name}=${session.value}`,
    },
    body,
  });

/** Seed the arrow legs' walk onto THIS run's own camera, older than the drop.
 *
 *  WHY THIS EXISTS: the boot's Full Database Reset (../operations/test-data.spec.ts,
 *  marker 58 of 104) runs unqualified `delete(Event)`/`delete(Detection)`/
 *  `delete(Camera)` (backend/api/routes/admin.py:702-710) and its restore leg
 *  recreates only CAMERAS, so by file 86 the event table holds nothing but what
 *  timeline specs have seeded. Witnessed as this file's CI red: `golden fixture:
 *  the unfiltered list holds 1 row(s) (62)` — the drop alone, where both
 *  directions are out-of-range no-ops and both arrow legs would have passed on a
 *  dead handler.
 *
 *  WHY BULK AND WHY DETECTION-LESS: POST /api/events/bulk is the sanctioned supply
 *  for Event-shaped state and constructs Event rows ONLY (events.py:1553,
 *  :1599-1609) — it writes no Detection, which matters twice: this file's camera is
 *  the one the F-064 spec's ownership prose assigns to F-054 (that spec is
 *  heavy-a's per owner ruling 226, and its draft names cat-on-porch as F-054's by
 *  elimination), and detection-shaped state is that spec's own supply to make.
 *  The legs need only
 *  `id` + `started_at` (the walk order) and `camera_name`, and the metadata block
 *  renders `Revision` from the LIST projection's schema-default version (see
 *  revisionMatchesList), so a detection-less row satisfies the legs' closing
 *  witness exactly as well as a real one.
 *
 *  WHY ON THIS CAMERA RATHER THAN A SIXTH: cat-on-porch has exactly ONE writer in
 *  the corpus — every other file that mentions it does so in the ownership prose,
 *  not as a writer (./video-clip.spec.ts:131, ./download-media.spec.ts:135,
 *  ./live-socket-arrival.spec.ts:40; the F-064 spec that once sat here was a
 *  READER of this camera's prose too, and is heavy-a's now per ruling 226).
 *  This file's own claim is the `CLAIMED_SCENARIO` constant above. Rows here are
 *  therefore self-attributing: step 1 of beforeAll already purges this camera of
 *  anything that is not the verified keeper, so a run that died between seeding and
 *  afterAll is cleaned by the NEXT run instead of poisoning one, and no foreign
 *  spec's exactly-one predicate can be reached by them. The camera is already
 *  seeded and already in the 60 s camera-list cache, so no `waitForCameraInList`
 *  wait is needed and the header's camera word is the same string for every walk
 *  row. */
async function seedWalkRows(session: Session): Promise<number[]> {
  // ONE clock sample seeds both the id salt and the date anchor, so they cannot
  // drift apart the way two `Date.now()` calls can across a slow boot. The dates
  // sit a fixed distance BEHIND that sample and further back per index, so the
  // walk's newest row is always the drop (ArrowRight's target end) whatever clock
  // the stack runs on and no seed can tie with it. batch_id is salted because
  // events.batch_id is UNIQUE (measured), and the route echoes ids in request
  // order (harness.ts's own createDetailFixture relies on that).
  const salt = Date.now();
  const anchor = salt - 3_600_000;
  const events = Array.from({ length: WALK_SEED_ROWS }, (_, i) => ({
    batch_id: `fe3w-${salt}-${i}`,
    camera_id: harness.cameraId,
    started_at: new Date(anchor - i * 600_000).toISOString(),
    risk_score: 20 + i * 10,
    risk_level: 'low',
    summary: `FE-3 walk fixture row ${i} — owns nothing but a slot in the arrow list`,
  }));

  // Raw fetch, deliberately NOT apiWrite: /api/events/bulk is the BULK tier (10 per
  // minute + burst 2 = 12 per sliding minute, per CLIENT IP — events.py:1538,
  // rate_limit.py:322), and ../shell/rate-limit.spec.ts (file 77, before this one)
  // spends that whole window deliberately before waiting it out. apiWrite's
  // contract is "a non-2xx THROWS", so on a 429 it would report a fixture bug where
  // the truth is "the window is full" — and a retry is the only correct response.
  // The status must be READ to branch on it, which is the shape
  // ../export-modal.spec.ts:364-382 already uses for this tier.
  const body = JSON.stringify({ events });
  let res = await postBulk(session, body);
  if (res.status === 429) {
    await new Promise((r) => setTimeout(r, 65_000)); // one 60 s window + margin
    res = await postBulk(session, body);
  }
  const parsed = (await res.json().catch(() => null)) as {
    succeeded?: number;
    results?: { status: string; id: number | null; error?: string }[];
  } | null;
  if (res.status !== 200 && res.status !== 207) {
    throw new Error(
      `walk fixture: POST /api/events/bulk answered ${res.status} ${JSON.stringify(parsed ?? {}).slice(0, 200)} ` +
        `(after ${res.status === 429 ? 'one 65 s window retry' : 'no retry'})`
    );
  }
  if (parsed?.succeeded !== WALK_SEED_ROWS) {
    throw new Error(
      `walk fixture: bulk created ${String(parsed?.succeeded)}/${WALK_SEED_ROWS} walk rows; ` +
        `first error: ${String(parsed?.results?.find((r) => r.status !== 'success')?.error).slice(0, 200)}`
    );
  }
  const ids = (parsed?.results ?? []).map((r) => r.id).filter((id): id is number => id !== null);
  if (ids.length !== WALK_SEED_ROWS) {
    throw new Error(
      `walk fixture: got ${ids.length} ids for ${WALK_SEED_ROWS} rows — the legs index the ` +
        'walk positionally, so a missing id must fail here, not mid-sweep.'
    );
  }
  return ids;
}

/** The unfiltered order the page's own list holds, computed the way the client
 *  computes it: the server's rows, sorted by `sortByDate('desc')` semantics
 *  (utils/pipeline.ts:144-156 — a numeric compare on started_at). */
const walkOrder = async (session: Session): Promise<{ id: number; camera: string }[]> => {
  const [list, cameras] = await Promise.all([eventList(session), cameraRows(session)]);
  const flat = Array.isArray(cameras) ? cameras : cameras.items;
  const names = new Map(flat.map((c) => [c.id, c.name]));
  return [...list.items]
    .sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime())
    .map((r) => ({ id: r.id, camera: names.get(r.camera_id) ?? '' }));
};

test.beforeAll(async () => {
  // The drop + the fake VLM's reply + a possible dedupe wait is real work; this
  // is the HOOK's timeout (a test.setTimeout inside a test does not move it).
  test.setTimeout(420_000);
  const session = await adminSession(timeline);

  // 1. Read THIS camera's existing rows BEFORE purging, and split them:
  //    a VERIFIED row from this book image is the reuse candidate, everything
  //    else is residue to delete. The split is what makes consecutive runs work:
  //    the 300 s content-hash dedupe (config.py:2089-2094) makes the watcher SKIP
  //    a re-drop of the same bytes outright (file_watcher.py:871-878, `return`,
  //    not a delay), and a hash has NO clearing route (dedupe.clear_hash is a
  //    method with no API surface) — so if the purge deleted the verified row too,
  //    a suppressed drop would leave this file with NO event at all and every later
  //    run would hang in the poll. Deleting only unverified rows also clears the
  //    detection-less leftovers a suppressed drop can leave, which would otherwise
  //    break waitForEventCards' landed-marker race. Two things can put a row on
  //    this camera and BOTH are this spec's own: a drop of this book image
  //    (feature_check.py seeds cameras, never events) and this file's walk seeds
  //    (seedWalkRows, step 3b below — same camera on purpose, see its note). So
  //    this purge deletes everything that is not the verified keeper, INCLUDING a
  //    previous run's seeds if that run died before afterAll, which is what makes
  //    a crashed run self-healing rather than poisoning: the next run starts from
  //    one keeper plus whatever it seeds itself.
  const existing = await api<{ items: EventRow[] }>(
    timeline,
    session,
    `/api/events?camera_id=${encodeURIComponent(harness.cameraId)}&limit=100`
  );
  const keeper = existing.items
    .filter((row) => row.verification?.verdict && row.summary === scenario.verdict.summary)
    .sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime())[0];
  await hardDeleteFixtureRows(
    timeline,
    session,
    existing.items.filter((row) => row.id !== keeper?.id).map((row) => row.id)
  );

  // 2. The drop, through O2.2's own helper — the sanctioned data supply for
  //    anything detection- or VLM-shaped.
  execFileSync(
    path.join(repoRoot, 'scripts/feature-check.sh'),
    ['drop', harness.scenarioImagePath, harness.scenario.name],
    {
      cwd: repoRoot,
      env: { ...process.env, FEATURE_CHECK_CAMERA_ROOT: harness.cameraRoot },
      encoding: 'utf8',
      timeout: 30_000,
    }
  );

  // 3. The backend BEFORE the UI: a row that never arrived would otherwise only
  //    prove the page renders. The poll takes the NEWEST verified row whose
  //    summary matches the book — which is either this run's drop, or the keeper
  //    the purge deliberately left when the dedupe window suppressed the drop.
  //    The keeper path returns INSTANTLY, so a suppressed run costs nothing.
  //    Reusing that row is sound rather than a shortcut: the fake's scenario key
  //    is the image's CONTENT DIGEST (scenarios.py:56-62), so the same bytes
  //    carry this book entry's verdict byte for byte, and every leg mirrors the
  //    API row into the DOM instead of a constant.
  const landed = async () => {
    const list = await api<{ items: EventRow[] }>(
      timeline,
      session,
      `/api/events?camera_id=${encodeURIComponent(harness.cameraId)}&limit=100`
    );
    return [...list.items]
      .filter((row) => row.verification?.verdict && row.summary === scenario.verdict.summary)
      .sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime())[0];
  };
  const deadline = Date.now() + 180_000;
  let chosen: EventRow | undefined;
  while (Date.now() < deadline) {
    chosen = await landed();
    if (chosen) break;
    await new Promise((resolve) => setTimeout(resolve, 5_000));
  }
  if (!chosen) {
    throw new Error(
      `golden fixture: ${harness.scenario.name} produced no verified event on camera ` +
        `${harness.cameraId} in 180 s (and none was kept from an earlier run), so the ` +
        'stack is not supplying the scenario this file is written against'
    );
  }
  dropEventId = chosen.id;
  // OWN only the rows this run can afford to lose: keep the row we are about to
  // drive, delete any older duplicate. Deleting the LAST verified row is the one
  // thing this fixture must never do, because a suppressed drop cannot replace it
  // — mark_processed runs only on the NOT-duplicate branch (dedupe.py:489-492), so
  // the TTL is not refreshed and no new row can exist for ~300 s after a real one.
  // Converging on exactly one surviving row is what makes back-to-back runs and a
  // cold stack both work, with no sleep anywhere.
  const survivors = await api<{ items: EventRow[] }>(
    timeline,
    session,
    `/api/events?camera_id=${encodeURIComponent(harness.cameraId)}&limit=100`
  );
  ownedEventIds = survivors.items.filter((r) => r.id !== dropEventId).map((r) => r.id);

  // 3b. Seed the arrow legs' stage (why this must be seeded rather than read off
  //     the stack is in seedWalkRows). Deliberately AFTER the survivors read above:
  //     ownership then stays in ONE place per kind of row — `ownedEventIds` holds
  //     this camera's residue, `seededWalkIds` holds what this call created —
  //     instead of the same id arriving in both lists and the cleanup route
  //     reporting the second deletion as a failure.
  seededWalkIds = await seedWalkRows(session);

  // 4. The server's own truth about that row, asserted HERE so every leg below
  //    mirrors pixels against a row this fixture knows is what the book says.
  const row = await eventRow(session, dropEventId);
  if (row.risk_score !== scenario.verdict.risk_score) {
    throw new Error(
      `golden fixture: dropped event risk_score=${String(row.risk_score)}, book says ` +
        scenario.verdict.risk_score
    );
  }
  if (riskLevelFromScore(Number(row.risk_score)) !== serverRiskLevel) {
    throw new Error(
      `golden fixture: score ${String(row.risk_score)} does not derive ${serverRiskLevel} ` +
        'from the shipped thresholds (src/utils/risk.ts:80-84)'
    );
  }
  if (row.summary !== scenario.verdict.summary) {
    throw new Error(
      `golden fixture: row summary ${JSON.stringify(row.summary)} is not the book's ` +
        `${JSON.stringify(scenario.verdict.summary)} — the row this file reads is not ` +
        `${CLAIMED_SCENARIO}'s`
    );
  }
  // The snooze leg starts from "nothing stored", so its before-state control is
  // true. A run that died between its snooze click and its restore would leave a
  // value here, and THROWING would redden every later run over residue this
  // fixture owns — so clear it the way the client does (api.ts:2514
  // unsnoozeEvent PATCHes snooze_until null) and re-read.
  if (row.snooze_until !== null) {
    await apiWrite<EventRow>(timeline, session, 'PATCH', `/api/events/${dropEventId}`, {
      snooze_until: null,
    });
    const cleared = await eventRow(session, dropEventId);
    if (cleared.snooze_until !== null) {
      throw new Error(
        `golden fixture: event ${dropEventId} is still snoozed (${String(cleared.snooze_until)}) ` +
          'after the wire unsnooze, so the snooze leg has no valid before-state'
      );
    }
  }
  const dets = await detectionItems(session, dropEventId);
  if (dets.items.length !== scenario.detections.length) {
    throw new Error(
      `golden fixture: ${dets.items.length} detections, the book declares ` +
        `${scenario.detections.length} for ${harness.scenario.name}`
    );
  }
  if (dets.items.some((d) => d.media_type !== 'image')) {
    throw new Error(
      'golden fixture: a non-image detection arrived, so the header claim that the ' +
        'video branch has no supplier on this stack needs re-measuring before the legs run'
    );
  }
  // No cast: `cameraRows` already declares the two shapes `/api/cameras` can
  // answer (bare array, or paginated `{items}`), and `Array.isArray` narrows the
  // union. Casting to `CameraRow[]` here narrowed the FALSE branch to `never`, so
  // `camera.items` was a TS2339 on `never` — one bogus assertion was the whole
  // error cascade; the union is the fix.
  const camera = await cameraRows(session);
  const list = Array.isArray(camera) ? camera : camera.items;
  cameraName = list.find((c) => c.id === row.camera_id)?.name ?? '';
  if (!cameraName) {
    throw new Error(`golden fixture: no camera name for id ${row.camera_id}`);
  }

  // 5. The arrow legs' stage, read AFTER the purge, the drop AND the seeds: my row
  //    is in the unfiltered list the legs walk, and the list holds the rows this
  //    fixture just created — with fewer than two rows both directions are
  //    out-of-range no-ops and both legs would pass on a dead handler, which is
  //    exactly the CI red this seed replaced (`the unfiltered list holds 1 row(s)
  //    (62)` after the boot's Full Database Reset). The legs themselves boot the
  //    FIRST/LAST row (not mine) so each direction gets a full sweep; see the
  //    STEPPING section.
  walk = await walkOrder(session);
  const index = walk.findIndex((r) => r.id === dropEventId);
  if (index < 0) {
    throw new Error(
      `golden fixture: event ${dropEventId} is not in the first page of the unfiltered ` +
        `list (${walk.map((r) => r.id).join(',')}), so the arrow-key walk could not step to it`
    );
  }
  // The floor is 1 + WALK_SEED_ROWS, and it is asserted as a FLOOR rather than an
  // equality because a foreign row on this camera (a crashed run's residue) is a
  // thing the purge above would have deleted but a concurrent writer could add.
  // The ceiling is the legs' own one-page precondition, asserted where it is a
  // premise about the client's limit rather than about this fixture.
  if (walk.length < 1 + WALK_SEED_ROWS) {
    throw new Error(
      `golden fixture: the unfiltered list holds ${walk.length} row(s) ` +
        `(${walk.map((r) => r.id).join(',')}), fewer than the ${1 + WALK_SEED_ROWS} this ` +
        `fixture seeds (drop ${dropEventId} + walk seeds [${seededWalkIds.join(', ')}]), so ` +
        'prev/next are bounds no-ops and the stepping clause cannot be pinned. The seeds were ' +
        'reported created, so something deleted them between seeding and this read.'
    );
  }
});

test.afterAll(async () => {
  // The harness's own helper, not a made-up route: DELETE /api/events/bulk with
  // soft_delete:false (events.py:1733-1803) cascades the detection and its
  // verification row. The previous draft's `/api/admin/events/{id}/hard` is not a
  // route at all, and its swallowed catch is how a run left event 4 behind.
  // Settle-don't-throw is the helper's own policy: cleanup must not turn a green
  // run red, and the next run's purge removes anything left here.
  const ids = [...ownedEventIds, ...seededWalkIds];
  if (ids.length === 0) return;
  const session = await adminSession(timeline);
  await hardDeleteFixtureRows(timeline, session, ids);
});

/* --------------------------------- helpers --------------------------------- */

/**
 * Boot through the shipped `?event=` door with the burst drained first, and wait
 * for the modal. `cameraFilter` is the row's own camera for the CONTENT legs
 * (nothing else can join the strip or the counts); the stepping leg boots
 * UNFILTERED because that is the only list with more than one row in it.
 */
async function bootModal(page: Page, eventId: number, cameraFilter = true): Promise<Session> {
  await setMode(page, 'advanced');
  return openTimelineEventModal(page, timeline, {
    cameraId: cameraFilter ? harness.cameraId : undefined,
    eventId,
  });
}

/** The modal, scoped. Two reasons, both measured: `risk-badge` is 1 inside the
 *  panel and 4 page-wide (the event cards carry their own), and StatsRow.tsx:231
 *  carries a second `data-testid="risk-score"`. */
const modal = (page: Page) => page.getByTestId('event-detail-modal');

/** One metadata row of the Details block's <dl>: label → value text. The block
 *  prints Event ID / Camera / Risk Score / Duration / Status / Revision
 *  (EventDetailModal.tsx:1154-1204) and Event ID is unique per row, which is why
 *  the stepping leg pins this rather than the camera word (two same-camera rows
 *  sit adjacent in the walk). */
const metadataRows = (page: Page) =>
  modal(page)
    .locator('dl > div')
    .evaluateAll((els) =>
      els.map((el) => ({
        label: el.querySelector('dt')?.textContent?.trim() ?? '',
        value: el.querySelector('dd')?.textContent?.trim() ?? '',
      }))
    );

const metaValue = async (page: Page, label: string): Promise<string> => {
  const rows = await metadataRows(page);
  return rows.find((r) => r.label === label)?.value ?? '';
};

/** The strip's entry buttons (ThumbnailStrip.tsx:117-127). */
const stripButtons = (page: Page) => modal(page).locator('button[aria-label^="View detection "]');

/* ---------------------------------- legs ----------------------------------- */

test.describe('F-054 event detail modal — Details tab', () => {
  test('the deep link opens the modal and its header badges mirror the server row (risk, notify, verdict-not-in-header)', async ({
    page,
  }) => {
    test.info().skip(!h.ready, h.ready ? '' : h.why);
    if (!h.ready) return;
    test.setTimeout(150_000);
    const session = await bootModal(page, dropEventId);
    const truth = await eventRow(session, dropEventId);
    const panel = modal(page);

    // Title + timestamp, both from the server: camera_name resolved through the
    // camera map (:593 prints event.camera_name) and started_at formatted by the
    // shipped browser-local formatter (:600 → :469-483).
    await expect(panel.getByTestId('detection-camera')).toHaveText(cameraName);
    await expect(panel.getByTestId('detection-timestamp')).toHaveText(
      await headerLabelIn(page, truth.started_at)
    );

    // RISK: the header shows RiskBadge because a score exists (:626-634), and the
    // tier is the CLIENT's threshold derivation of the server's score (:540).
    const badge = panel.getByTestId('risk-badge');
    await expect(badge).toHaveCount(1);
    await expect(badge).toHaveText(riskBadgeText);
    await expect(badge).toHaveAttribute('aria-label', riskBadgeAria);
    // The message goes on `expect(...)`, NOT as toContainText's second argument:
    // that slot is Playwright's OPTIONS object, so a string there type-errors
    // (TS2559) and the leg would fail with no explanation.
    await expect(
      panel.getByTestId('risk-score'),
      'the header block carries the stored score inside the badge'
    ).toContainText(String(truth.risk_score ?? 0));
    expect(truth.risk_score, 'the row carries the book score the badge renders').toBe(
      scenario.verdict.risk_score
    );

    // VERDICT: the header is NOT where it lives while a score exists (:627-635) —
    // the verification section is. VerdictBadge has no testid, so the shipped
    // instrument is role=status + the verdict aria, and BOTH halves are pinned:
    // the header offers exactly the risk badge as a status, the verdict word
    // appears once and inside the section, and its data-verdict is the book's.
    const statuses = await panel.getByRole('status').evaluateAll((els) =>
      els.map((el) => ({
        aria: el.getAttribute('aria-label') ?? '',
        verdict: el.getAttribute('data-verdict'),
        notify: el.getAttribute('data-notify'),
        text: el.textContent ?? '',
      }))
    );
    // In F4.9 (MO2), the header always shows VerdictBadge in both modes, and in
    // Advanced mode `verification-section` renders its VerdictBadge as well.
    expect(
      statuses.filter((s) => s.aria.startsWith('Verification verdict:')).length,
      'verdict status in the modal header and the VLM verification section'
    ).toBeGreaterThanOrEqual(1);
    const verdictStatus = statuses.find((s) => s.aria.startsWith('Verification verdict:'));
    expect(verdictStatus?.aria).toBe(`Verification verdict: ${verdictLabelText}`);
    expect(verdictStatus?.verdict).toBe(scenario.verdict.verdict);
    expect(verdictStatus?.text).toBe(verdictLabelText);
    const section = panel.getByTestId('verification-section');
    await expect(section, 'the verdict badge is inside the VLM verification section').toBeVisible();
    expect(
      await section
        .getByRole('status', {
          name: `Verification verdict: ${verdictLabelText}`,
        })
        .count(),
      'and it is that section that renders it'
    ).toBe(1);
    expect(
      panel.getByTestId('risk-score').getByRole('status', { name: /^Risk level:/ }),
      'the header column itself is the risk badge'
    ).toHaveCount(1);

    // NOTIFY: a real decision exists, so the badge renders with the shipped
    // aria/`data-notify`/text triple (NOTIFY: data-notify is yes/no, never the
    // string 'true'/'false'), selected by the row's own value.
    expect(typeof truth.notify, 'the row carries a notify decision (key present)').toBe('boolean');
    const want = notifyContract(Boolean(truth.notify));
    const notifyBadge = panel.getByRole('status', { name: want.aria });
    await expect(notifyBadge, 'one badge for the stored decision').toHaveCount(1);
    await expect(notifyBadge).toHaveAttribute('data-notify', want.attr);
    await expect(notifyBadge).toHaveText(want.text);
    // The opposite branch must NOT be on the page, so a badge that always renders
    // the same words cannot pass.
    await expect(
      panel.getByRole('status', { name: notifyContract(!truth.notify).aria })
    ).toHaveCount(0);

    // SNOOZE: the projection never hands `snooze_until` over, so the badge is
    // absent while the button is present and unarmed. The wire control (the row
    // is unsnoozed now) is what makes the absence a fact about the row rather
    // than about an unmounted component; the full control runs in the snooze leg.
    expect(truth.snooze_until, 'this row is not snoozed on the wire').toBeNull();
    await expect(
      panel.getByTestId('snooze-badge'),
      'SnoozeBadge renders nothing: getModalEvent (EventTimeline.tsx:1060-1090) omits ' +
        'snooze_until, so /timeline cannot show it even for a snoozed row'
    ).toHaveCount(0);
    await expect(panel.getByTestId('snooze-button')).toHaveCount(1);
    await expect(panel.getByTestId('snooze-button')).toHaveAttribute('aria-label', 'Snooze event');

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('AI summary, risk breakdown and VLM verification mirror the server row', async ({
    page,
  }) => {
    test.info().skip(!h.ready, h.ready ? '' : h.why);
    if (!h.ready) return;
    test.setTimeout(150_000);
    const session = await bootModal(page, dropEventId);
    const truth = await eventRow(session, dropEventId);
    const panel = modal(page);

    // AI SUMMARY — the paragraph is the row's `summary` verbatim (:847 prints
    // event.summary, which EventTimeline.tsx:1078 hands over as
    // `event.summary || 'No summary available'`).
    await expect(panel.getByTestId('ai-analysis-section')).toContainText(truth.summary ?? '');
    expect(truth.summary).toBe(scenario.verdict.summary);

    // RISK BREAKDOWN — mounted iff a score exists (:907) and only because
    // `reasoning` is populated (RiskFactorsBreakdown.tsx:172, :176-183). The
    // reasoning text lives behind the collapsed toggle (:204, defaultExpanded
    // false :163), so the click is the shipped interaction, not a workaround.
    await expect(panel.getByTestId('risk-factors-breakdown')).toBeVisible();
    await expect(panel.getByTestId('risk-factors-content')).toHaveCount(0);
    const toggle = panel.getByTestId('risk-factors-toggle');
    await expect(toggle).toHaveAttribute('aria-expanded', 'false');
    await toggle.click();
    await expect(toggle).toHaveAttribute('aria-expanded', 'true');
    const reasoning = panel.getByTestId('reasoning-section');
    await expect(reasoning).toBeVisible();
    await expect(reasoning).toContainText(truth.reasoning ?? '');
    expect(truth.reasoning).toBe(scenario.verdict.reasoning);
    // The four inputs the projection never fills mean no contribution bars: the
    // section explains a score from the reasoning ALONE.
    await expect(
      panel.getByTestId('contribution-bars'),
      'entities/flags/confidence_factors are not in getModalEvent, so no bars render'
    ).toHaveCount(0);

    // VLM VERIFICATION — scene, criteria (with the per-criterion pass flag),
    // reviewed frames and the provenance footer, each compared to the API row.
    const verification = truth.verification;
    expect(verification, 'the row carries an event_verifications row').toBeTruthy();
    await expect(panel.getByTestId('verification-section')).toBeVisible();
    await expect(panel.getByTestId('verification-scene')).toHaveText(
      verification?.scene_description ?? ''
    );
    expect(verification?.scene_description).toBe(scenario.verdict.description);

    const criteria = verification?.criteria ?? [];
    expect(
      criteria.length,
      'the row carries the book criteria (a zero-criterion checklist would be vacuous)'
    ).toBe(scenario.verdict.criteria?.length);
    await expect(panel.getByTestId('verification-criteria').locator('li')).toHaveCount(
      criteria.length
    );
    for (const criterion of criteria) {
      const li = panel.getByTestId(`criterion-${criterion.name}`);
      await expect(li, `criterion ${criterion.name} is rendered`).toBeVisible();
      await expect(li).toHaveAttribute('data-passed', String(criterion.passed));
      await expect(li).toContainText(criterion.name);
      await expect(li).toContainText(criterion.evidence ?? '');
    }

    // Reviewed frames: one <img> per key frame. Its src answers 500 on this stack
    // (header wire proof), so this asserts the shipped contract — count, src, alt
    // — and never a decoded pixel. Measured: naturalWidth 0, complete true.
    const frames = verification?.key_frame_detection_ids ?? [];
    expect(frames.length > 0, 'the verification row names reviewed frames').toBe(true);
    const frameImages = panel.locator('img[alt^="Reviewed frame"]');
    await expect(frameImages).toHaveCount(frames.length);
    for (let i = 0; i < frames.length; i += 1) {
      const img = frameImages.nth(i);
      await expect(img).toHaveAttribute('alt', `Reviewed frame ${i + 1} (detection ${frames[i]})`);
      await expect(img).toHaveAttribute(
        'src',
        new RegExp(`/api/detections/${frames[i]}/thumbnail$`)
      );
    }
    const sectionText = await panel.getByTestId('verification-section').innerText();
    for (const part of [
      String(verification?.engine),
      String(verification?.model_id),
      `${String(verification?.latency_ms)} ms`,
    ]) {
      expect(sectionText, `the provenance footer names ${part}`).toContain(part);
    }
    // And the book's own provenance, so a footer that printed the row's fields
    // out of thin air could not pass: the engine/model come from the book entry.
    expect(verification?.model_id).toBe(scenario.verdict.provenance?.model_id);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('the details tab fills scene-caption and risk-factors with nothing, and sources Detected Objects from its own fetch (F4.4)', async ({
    page,
  }) => {
    test.info().skip(!h.ready, h.ready ? '' : h.why);
    if (!h.ready) return;
    test.setTimeout(150_000);
    // Ground truth first: what the modal's own fetch (useEventDetectionsQuery,
    // EventDetailModal.tsx:212) will receive for this event.
    const session = await adminSession(timeline);
    const stored = await detectionItems(session, dropEventId);
    expect(
      stored.items.length > 0,
      `the drop carries ${stored.items.length} server detections — with none, ` +
        'the presence assert below would pass an empty block as rendering'
    ).toBe(true);
    await bootModal(page, dropEventId);
    const panel = modal(page);
    // A media element IS on screen (this waits for the async detections query,
    // EventDetailModal.tsx:213-218 — a bare post-boot assert raced it and lost):
    // so the absences below are the projection's gaps, not an unrendered tab.
    await expect(panel.getByTestId('detection-image')).toBeVisible();

    await expect(
      panel.getByTestId('scene-caption-section'),
      'event.scene_caption is not in getModalEvent, so the Florence-2 block is ' +
        'absent even though the scene description renders in the verification section'
    ).toHaveCount(0);
    // F4.4 flipped the objects block's source: it renders from the modal's OWN
    // fetch (EventDetailModal.tsx:894), not from getModalEvent's projection —
    // which still passes no detections. Presence, with the count the fetch returns.
    await expect(
      panel.getByTestId('detection-objects'),
      'the modal fetches detections itself since F4.4, so the NEM-3603 block ' +
        'renders on /timeline for an event with server detections'
    ).toBeVisible();
    await expect(
      panel.getByTestId('detection-objects').getByText('cat', { exact: true }).first(),
      'the block is populated, not an empty shell (the book declares a cat detection)'
    ).toBeVisible();
    await expect(
      panel.getByTestId('risk-factors-section'),
      'event.risk_factors is not in getModalEvent either, though the LIST ROUTE ' +
        'does return the column (measured) — the projection is what drops it'
    ).toHaveCount(0);
    // The event-level fallback image is dead here for the same reason: no
    // image_url rides, so the media on screen is the DETECTION's.
    await expect(panel.getByTestId('detection-image')).toHaveAttribute(
      'src',
      /\/api\/detections\/\d+\/image\?full=true$/
    );

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('the detection strip mirrors the server detections and selecting one shows its full image', async ({
    page,
  }) => {
    test.info().skip(!h.ready, h.ready ? '' : h.why);
    if (!h.ready) return;
    test.setTimeout(150_000);
    const session = await bootModal(page, dropEventId);
    const panel = modal(page);

    // Ground truth FIRST: what GET /api/events/{id}/detections answers is what
    // the strip must match, item for item.
    const stored = await detectionItems(session, dropEventId);
    const items = stored.items;
    const heading = panel.getByText(`Detection Sequence (${items.length})`, { exact: false });
    await expect(
      heading,
      'the strip renders only for a non-empty list (ThumbnailStrip.tsx:69) and states its count'
    ).toBeVisible();

    // The strip is async; waiting on the buttons is the shipped skeleton→content
    // transition, not a sleep.
    const buttons = stripButtons(page);
    await expect(buttons).toHaveCount(items.length);
    for (let i = 0; i < items.length; i += 1) {
      const item = items[i];
      await expect(buttons.nth(i)).toHaveAttribute(
        'aria-label',
        `View detection ${i + 1} at ${stripLabel(item.detected_at)}. Double-click to enlarge.`
      );
      await expect(buttons.nth(i)).toContainText(`#${i + 1}`);
      await expect(buttons.nth(i)).toContainText(
        `${item.object_type ?? 'object'} (${percent(item.confidence)})`
      );
    }
    // The book's class/confidence ARE the server's values, so the strip is pinned
    // to the drop and not to whatever rows a neighbour left behind.
    expect(items[0]?.object_type).toBe(scenario.detections[0]?.class);
    expect(percent(items[0]?.confidence)).toBe(percent(scenario.detections[0]?.confidence));
    expect(items[0]?.media_type, 'the stills-only book means no video entry').toBe('image');
    expect(
      items[0]?.thumbnail_path,
      'a pipeline detection carries a NULL thumbnail_path, which is why the two ' +
        'thumbnail routes must generate and 500 on this read_only stack'
    ).toBeNull();
    // The strip's own <img> per item, at the route that 500s here: the shipped
    // contract is asserted, the pixel deliberately is not (header wire proof).
    const thumbs = buttons.locator('img');
    await expect(thumbs).toHaveCount(items.length);
    for (let i = 0; i < items.length; i += 1) {
      await expect(thumbs.nth(i)).toHaveAttribute('src', `/api/detections/${items[i].id}/image`);
      await expect(thumbs.nth(i)).toHaveAttribute(
        'alt',
        `Detection ${i + 1}: ${items[i].object_type ?? 'object'}`
      );
    }

    // AUTO-SELECTION: the first detection is selected on mount (:252-256), so the
    // main media is its FULL image — the one detection endpoint this stack
    // answers, and the only media leg here that can decode.
    const image = panel.getByTestId('detection-image');
    await expect(image).toHaveAttribute(
      'src',
      new RegExp(`/api/detections/${items[0]?.id}/image\\?full=true$`)
    );
    const alt = `${items[0]?.object_type ?? 'Detection'} at ${await headerLabelIn(
      page,
      items[0]?.detected_at ?? ''
    )}`;
    await expect(image).toHaveAttribute('alt', alt);
    // The clause says "the selected IMAGE", so a decoded picture is the point.
    await expect
      .poll(() =>
        panel
          .locator('img[data-testid="detection-image"]')
          .evaluate((el: HTMLImageElement) => el.naturalWidth)
      )
      .toBeGreaterThan(0);
    // There is no aria-describedby in the shipped component at all — measured
    // null, and DetectionImage.tsx:80-98 never writes the attribute, so
    // getAttribute answers null (asserting '' here would be the false way round).
    // The CONTAINER is the activator and carries the alt inside its accessible
    // name (:84-91: role=button, tabIndex 0, `View ${alt} in full size`).
    expect(
      await image.getAttribute('aria-describedby'),
      'the shipped <img> carries no aria-describedby'
    ).toBeNull();
    const container = panel.getByTestId('detection-image-container');
    await expect(container).toHaveAttribute('role', 'button');
    await expect(container).toHaveAttribute('aria-label', `View ${alt} in full size`);

    // CLICK-TO-SELECT on a reload, so the selection is a fact of THIS drive: the
    // shipped click re-aims the media (handleThumbnailClick :343-345), which is
    // the witness — not a class toggle.
    await settledReload(page);
    await expect(buttons).toHaveCount(items.length);
    await buttons.first().click();
    await expect(image).toHaveAttribute(
      'src',
      new RegExp(`/api/detections/${items[0]?.id}/image\\?full=true$`)
    );

    // The selected image's OWN lightbox: DetectionImage wires the container as a
    // button whose activation opens the shipped Lightbox on the full-size src
    // (DetectionImage.tsx:84-98, :134-135).
    await container.click();
    const lightbox = page.getByTestId('lightbox-backdrop');
    await expect(lightbox, 'the selected image opens the lightbox').toBeVisible();
    const lbImage = page.getByTestId('lightbox-image');
    await expect(lbImage).toHaveAttribute(
      'src',
      new RegExp(`/api/detections/${items[0]?.id}/image\\?full=true$`)
    );
    // The caption is the modal's own composition (:761):
    // `<camera_name> - <object> (<pct>%)`.
    await expect(page.getByTestId('lightbox-caption')).toHaveText(
      `${cameraName} - ${items[0]?.object_type ?? 'Detection'} (${percent(items[0]?.confidence)})`
    );
    await expect
      .poll(() => lbImage.evaluate((el: HTMLImageElement) => el.naturalWidth))
      .toBeGreaterThan(0);
    // One image in this lightbox, so the counter and the arrows are correctly
    // absent (Lightbox.tsx:140, :196 — hasMultipleImages gates both).
    await expect(page.getByTestId('lightbox-counter')).toHaveCount(0);
    await page.getByTestId('lightbox-close-button').click();
    await expect(lightbox, 'the close button closes just the lightbox').toHaveCount(0);
    await expect(panel, 'and the modal survives it').toBeVisible();

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('double-clicking a strip thumbnail opens the strip lightbox at that entry', async ({
    page,
  }) => {
    test.info().skip(!h.ready, h.ready ? '' : h.why);
    if (!h.ready) return;
    test.setTimeout(150_000);
    const session = await bootModal(page, dropEventId);
    const panel = modal(page);
    const stored = await detectionItems(session, dropEventId);
    const item = stored.items[0];
    const buttons = stripButtons(page);
    await expect(buttons).toHaveCount(stored.items.length);

    // handleThumbnailLightbox (:349-354) opens the STRIP's lightbox, whose image
    // list (:367-398) uses the full-size src and a `<type> (<pct>%)` caption, and
    // filters videos out (:371-375) — which is why this leg can promise a
    // decodable image on this stack.
    await buttons.first().dblclick();
    const lightbox = page.getByTestId('lightbox-backdrop');
    await expect(lightbox, 'a double-click enlarges the strip entry').toBeVisible();
    const image = page.getByTestId('lightbox-image');
    await expect(image).toHaveAttribute(
      'src',
      new RegExp(`/api/detections/${item?.id}/image\\?full=true$`)
    );
    // alt is the strip lightbox's own composition (:394):
    // `Detection <type> at <MMM D, h:mm A>`.
    await expect(page.getByTestId('lightbox-caption')).toHaveText(
      `${item?.object_type ?? 'object'} (${percent(item?.confidence)})`
    );
    await expect
      .poll(() => image.evaluate((el: HTMLImageElement) => el.naturalWidth))
      .toBeGreaterThan(0);
    await expect(page.getByTestId('lightbox-counter')).toHaveCount(0);

    // Escape is BOTH closers at once, measured: Lightbox's own keydown (:101) and
    // the modal's unguarded one (:399-410) both listen on document, so one press
    // dismisses the lightbox and the modal together. The modal then reopens
    // through the shipped door so the leg leaves the page usable.
    await page.keyboard.press('Escape');
    await expect(lightbox, 'escape closes the lightbox').toHaveCount(0);
    await expect(
      panel,
      'MEASURED SHIPPED BEHAVIOUR: Escape reaches the modal too, because its ' +
        'document keydown (:399-410) has no lightbox guard'
    ).toHaveCount(0);
    // Re-open through the SAME sanctioned boot (the burst may already be spent,
    // and a bare goto to the identical url is a full reload, not a re-trigger of
    // the deep-link effect — quietBoot re-drives until the page paints).
    await quietBoot(page, timeline, `/timeline?event=${dropEventId}`);
    await expect(panel, 'the door reopens it').toBeVisible();

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  /* The clause's "steps prev/next with the arrow keys" is TWO directions, so it is
   * driven as two tests — each owns one direction's full sweep, its own bound, and
   * the control that turns that bound into a bound rather than a freeze. Splitting
   * them makes each direction citable on its own (a single leg that pressed both
   * keys could report green while one direction was dead).
   *
   * BOTH BOOT UNFILTERED, because handleNavigate walks `filteredEvents` (:523,
   * default sort 'newest' :104 → sortByDate('desc')) and a camera filter leaves one
   * camera's rows, which is what made the old draft's "step left, the camera
   * changes" an out-of-range no-op. The START ROW IS CHOSEN SO THE SWEEP HAS A FULL
   * RUN: each leg deep-links the row sitting at the end its direction walks AWAY
   * from, so the deep link (the same shipped door, EventTimeline.tsx:329-334) does
   * the positioning and the leg never spends a press of the OPPOSITE direction to
   * get into position — no cross-direction press can mask a dead one.
   *
   * The expected order is RECOMPUTED IN THE TEST from the server's own rows
   * (walkOrder) and is that test's ONLY authority. beforeAll's earlier snapshot is
   * deliberately NOT re-compared: a suppressed drop can land LATE (measured — a run
   * chose its row at 21:27 and the drop it had suppressed surfaced as a second cat
   * row at ~21:32), so "unchanged since the hook" is a race that reddens a correct
   * page. Every step is witnessed by the DOM's own metadata Event ID (unique per
   * row — two SAME-camera rows sit adjacent, so the camera word could not pin a
   * step) against THIS read. */
  test('ArrowRight and the Next button step the modal to later events until the shipped upper bound stops it', async ({
    page,
  }) => {
    test.info().skip(!h.ready, h.ready ? '' : h.why);
    if (!h.ready) return;
    test.setTimeout(180_000);
    const session = await adminSession(timeline);
    const order = await walkOrder(session);
    // The room this leg needs, stated as an assertion so a stack with one row
    // reports "no room to step" instead of a confusing no-op green.
    expect(order.length, 'the walk needs more than one row to have a next at all').toBeGreaterThan(
      1
    );
    // Start at the FIRST row so ArrowRight has the whole list to walk.
    const startId = order[0].id;
    await bootModal(page, startId, false);
    // Re-read next to the DOM and locate the start row again (a late drop shifts
    // indices; the id does not move out of the list).
    const list = await walkOrder(session);
    const start = list.findIndex((r) => r.id === startId);
    expect(start, 'the start row is in the list the page walks').toBeGreaterThanOrEqual(0);
    // The client's own page is `limit=20` (EventTimeline.tsx:182-184), so a stack
    // holding more than 20 rows would give the PAGE a shorter list than this read
    // and the upper bound would land on a row the page never had. Naming that as a
    // precondition keeps a crowded stack reporting "the page cannot see the whole
    // list" instead of a misleading bound failure.
    expect(
      list.length,
      'the page only holds its first 20 rows, so the walk must fit in one page'
    ).toBeLessThanOrEqual(20);

    const next = page.getByRole('button', { name: 'Next event' });
    const expectAt = async (i: number, note: string) => {
      await expect
        .poll(() => metaValue(page, 'Event ID'), `${note} (walk index ${i})`)
        .toBe(String(list[i].id));
      await expect(page.getByTestId('detection-camera')).toHaveText(list[i].camera);
    };
    await expectAt(start, 'the deep link opened on its own row');

    // KEY-DRIVEN SWEEP, ONE ROW PER PRESS, over the rows before the last, each
    // press witnessed. Sweeping every row (not one) is what stops a handler that
    // advances by a wrong amount, or onto a row the current filter excludes, from
    // passing on the first press.
    for (let i = start + 1; i < list.length - 1; i += 1) {
      await page.keyboard.press('ArrowRight');
      await expectAt(i, `ArrowRight stepped to walk index ${i}`);
    }
    // The LAST forward step is driven by the BUTTON, so the footer's wiring of the
    // same handler (:1272 → :966-979) has a MOVER witness in this direction and not
    // merely a "clicking it at the end did nothing". With a single forward step
    // available there is no spare row to spend on the button, so the key takes it
    // and the button's witness is its enabled-and-ignored bound (below).
    if (list.length - 1 > start + 1) {
      await next.click();
      await expectAt(list.length - 1, 'the Next button stepped to the last row');
    } else {
      await page.keyboard.press('ArrowRight');
      await expectAt(list.length - 1, 'ArrowRight stepped to the last row');
    }

    // UPPER BOUND, BOTH DOORS. The bounds live only in handleNavigate's guard
    // (:971-975) — the modal never disables :1263/:1272 — so these are REAL
    // activations that must be ignored. `atEnd` is pinned to the last row's own id
    // below, which is what keeps the no-op non-vacuous: the post-press read must
    // equal a NON-EMPTY id, so a modal that closed (which would read '') is red.
    const atEnd = await metaValue(page, 'Event ID');
    expect(atEnd, 'the rightwards sweep reached the very last row').toBe(
      String(list[list.length - 1].id)
    );
    await expect(next, 'and the Next button is NOT disabled at the end').toBeEnabled();
    await page.keyboard.press('ArrowRight');
    await next.click();
    await expect(
      metaValue(page, 'Event ID'),
      'the last row is out of range for next, so the modal must NOT move'
    ).resolves.toBe(atEnd);
    // Why that no-op is a BOUND and not a dead handler: the SAME two instruments
    // demonstrably advanced one row per activation moments ago (every step above
    // is a witnessed move) and the button is still enabled here, so the only thing
    // that changed is the index the guard reads (:971-975).
    // The row the sweep landed on is the row the SERVER has in its list answer, not
    // a lookalike: the printed Revision is compared to what that route answers for
    // this id (see revisionMatchesList for why the single-row read is the wrong
    // control here — it sends the live column, the list projection cannot).
    await revisionMatchesList(page, session, list[list.length - 1].id);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('ArrowLeft and the Previous button step the modal to earlier events until the shipped lower bound stops it', async ({
    page,
  }) => {
    test.info().skip(!h.ready, h.ready ? '' : h.why);
    if (!h.ready) return;
    test.setTimeout(180_000);
    const session = await adminSession(timeline);
    const order = await walkOrder(session);
    expect(order.length, 'the walk needs more than one row to have a prev at all').toBeGreaterThan(
      1
    );
    // Start at the LAST row so ArrowLeft has the whole list to walk back over.
    const startId = order[order.length - 1].id;
    await bootModal(page, startId, false);
    const list = await walkOrder(session);
    const start = list.findIndex((r) => r.id === startId);
    expect(start, 'the start row is in the list the page walks').toBeGreaterThanOrEqual(0);
    // Same one-page precondition as the other leg: this leg STARTS at the list's
    // LAST row, which only exists in the page (client limit=20,
    // EventTimeline.tsx:182-184) if the whole list fits in one page.
    expect(
      list.length,
      'the page only holds its first 20 rows, so the walk must fit in one page'
    ).toBeLessThanOrEqual(20);

    const prev = page.getByRole('button', { name: 'Previous event' });
    const expectAt = async (i: number, note: string) => {
      await expect
        .poll(() => metaValue(page, 'Event ID'), `${note} (walk index ${i})`)
        .toBe(String(list[i].id));
      await expect(page.getByTestId('detection-camera')).toHaveText(list[i].camera);
    };
    await expectAt(start, 'the deep link opened on its own row');

    // KEY-DRIVEN SWEEP, ONE ROW PER PRESS, down to row 1 (not 0), each witnessed.
    for (let i = start - 1; i > 0; i -= 1) {
      await page.keyboard.press('ArrowLeft');
      await expectAt(i, `ArrowLeft stepped back to walk index ${i}`);
    }
    // The LAST backward step, INTO index 0, is driven by the BUTTON, mirroring the
    // other leg: the Previous button gets a MOVER witness, not only an ignored
    // click at the bound. Same escape hatch when only one step is available.
    if (start - 1 > 0) {
      await prev.click();
      await expectAt(0, 'the Previous button stepped to the first row');
    } else {
      await page.keyboard.press('ArrowLeft');
      await expectAt(0, 'ArrowLeft stepped to the first row');
    }

    // LOWER BOUND, BOTH DOORS; enabled-as-guard reasoning as in the other leg,
    // including the non-empties-pin-the-no-op point (a closed modal reads '').
    const atStart = await metaValue(page, 'Event ID');
    expect(atStart, 'the leftwards sweep reached the very first row').toBe(String(list[0].id));
    await expect(prev, 'the Previous button is NOT disabled at the start').toBeEnabled();
    await page.keyboard.press('ArrowLeft');
    await prev.click();
    await expect(
      metaValue(page, 'Event ID'),
      'index 0 is out of range for prev, so the modal must NOT move'
    ).resolves.toBe(atStart);
    await revisionMatchesList(page, session, list[0].id);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('the metadata block prints the stored row, and the snooze the modal stores is the one the wire agrees to', async ({
    page,
  }) => {
    test.info().skip(!h.ready, h.ready ? '' : h.why);
    if (!h.ready) return;
    test.setTimeout(150_000);
    const session = await bootModal(page, dropEventId);
    const truth = await eventRow(session, dropEventId);
    const panel = modal(page);
    const rows = await metadataRows(page);
    const byLabel = new Map(rows.map((r) => [r.label, r.value]));
    // Revision is the ONE printed field whose value depends on WHICH read the
    // projection was built from, so it gets its own instrument (see
    // revisionMatchesList for the measurement: the list route answers version 1 for
    // every row, while GET /api/events/{id} — `truth` below — carries the live
    // 3/4/5). Every other field here is compared to `truth` directly because the
    // projection does pass those through.
    await revisionMatchesList(page, session, dropEventId);

    // The Details block prints the stored row, field by field, through the
    // shipped dt/dd pairs (:1154-1204).
    expect(byLabel.get('Event ID'), 'the block names the row it came from').toBe(String(truth.id));
    expect(byLabel.get('Camera'), 'the camera the projection resolved').toBe(cameraName);
    expect(byLabel.get('Risk Score'), 'the score reads out of 100, not a percentage').toBe(
      `${String(truth.risk_score)} / 100`
    );
    expect(byLabel.get('Status'), 'an unreviewed row reads Pending Review').toBe('Pending Review');
    // `Rev. 1`, NOT `Rev. ${truth.version}`: the second time this leg ran it printed
    // Rev. 1 while the single read said 3, and the instrument that claimed they
    // converge was the wrong party — the list route never sends the key
    // (events.py:513-567) so EventResponse's `Field(1)` default (schemas/
    // events.py:167-170) is what the modal renders. Asserted against the value the
    // projection's own source answers (revisionMatchesList above); the field is
    // still WITNESSED as printed, which is what the row's clause asks for.
    expect(
      byLabel.get('Revision'),
      'the optimistic-locking revision is printed, at the value the list route answers'
    ).toBe('Rev. 1');
    expect(truth.reviewed, 'the control holds: this row is unreviewed on the wire').toBe(false);
    // And the score row's OTHER branch is reachable-by-shape, asserted as the
    // exact text the component prints for a null score (:1166-1170). Not this
    // row's state — the drop always carries a score — so it is recorded as a
    // covered-string pairing rather than a driven leg: this stack has no supplier
    // for a VLM-scored row with a NULL score, and a fixture-made null would not
    // exist alongside a verification.
    expect(
      rows.some((r) => r.label === 'Risk Score' && r.value === 'Not analyzed'),
      'a scored row must NOT read Not analyzed'
    ).toBe(false);

    // SNOOZE: the clause's "sees the snooze badge" cannot be honoured on THIS
    // surface (header: getModalEvent never passes snooze_until), so the leg
    // drives the shipped control and pins the STORED decision plus the shipped
    // absence — with a row known snoozed as the control.
    expect(truth.snooze_until, 'starts unsnoozed').toBeNull();
    await panel.getByTestId('snooze-button').click();
    const dropdown = page.getByTestId('snooze-dropdown');
    await expect(dropdown, 'the shipped menu lists the four durations').toBeVisible();
    // SnoozeButton.tsx:239 keys the items by seconds, so 1 hour is
    // snooze-option-3600 (utils/snooze.ts:21-26) — not a text match that a label
    // change could silently re-point.
    await expect(dropdown.getByRole('menuitem')).toHaveCount(4);
    await expect(
      page.getByTestId('unsnooze-option'),
      'an unsnoozed row offers no Unsnooze item (SnoozeButton.tsx:205-213)'
    ).toHaveCount(0);
    await page.getByTestId('snooze-option-3600').click();

    await expect
      .poll(
        async () => (await eventRow(session, dropEventId)).snooze_until !== null,
        'the click stored a snooze'
      )
      .toBe(true);
    const after = await eventRow(session, dropEventId);
    const deltaMinutes = (new Date(String(after.snooze_until)).getTime() - Date.now()) / 60_000;
    expect(
      deltaMinutes,
      `a one-hour option stores ~60 min ahead (got ${deltaMinutes.toFixed(2)})`
    ).toBeGreaterThan(58);
    expect(deltaMinutes).toBeLessThan(62);
    expect(after.version, 'the write moved the optimistic-locking revision').toBe(
      truth.version + 1
    );

    // The shipped absence, against a row that IS now snoozed on the wire. This is
    // the control: if the projection ever hands the key over, the badge appears,
    // the button's aria-label changes and unsnooze-option mounts — all three are
    // asserted here, so a fix that wires snooze_until through reddens this leg and
    // says so.
    await expect(
      panel.getByTestId('snooze-badge'),
      'MEASURED: the badge stays absent even with snooze_until stored, because ' +
        'getModalEvent (EventTimeline.tsx:1060-1090) never sets the key'
    ).toHaveCount(0);
    await expect(
      panel.getByTestId('snooze-button'),
      'and the button still reads the unsnoozed state for the same reason'
    ).toHaveAttribute('aria-label', 'Snooze event');

    // Cleanup in the same session: the UI's own Unsnooze door is unreachable
    // here (same projection cause), so the wire PATCH the client itself makes
    // (api.ts:2514 unsnoozeEvent) restores the row for the next run.
    await apiWrite<EventRow>(timeline, session, 'PATCH', `/api/events/${dropEventId}`, {
      snooze_until: null,
    });
    const restored = await eventRow(session, dropEventId);
    expect(restored.snooze_until, 'the row is left unsnoozed for the next run').toBeNull();

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('the print door is the shipped button and the page owns a print stylesheet', async ({
    page,
  }) => {
    test.info().skip(!h.ready, h.ready ? '' : h.why);
    if (!h.ready) return;
    test.setTimeout(150_000);
    await bootModal(page, dropEventId);
    const panel = modal(page);
    const button = panel.getByTestId('print-event-button');
    await expect(button).toBeVisible();
    await expect(button).toHaveAttribute('aria-label', 'Print event report');
    // The button's only behaviour is `onClick={() => window.print()}` (:1326-1334)
    // and headless Chromium has no print preview, so nothing here pretends to
    // have printed. What is pinned is that the DOCUMENT carries a print contract
    // at all — the built bundle's own copy of src/styles/print.css, no injection —
    // which the next leg measures. `printRules` counts top-level @media rules
    // whose condition mentions print; a page with no print stylesheet has 0.
    const printRules = await page.evaluate(() =>
      [...document.styleSheets].reduce((total, sheet) => {
        try {
          return (
            total +
            [...sheet.cssRules].filter(
              (rule) => rule instanceof CSSMediaRule && rule.conditionText.includes('print')
            ).length
          );
        } catch {
          return total;
        }
      }, 0)
    );
    expect(
      printRules,
      'the served bundle already carries the @media print block ' +
        '(src/main.tsx:9 → src/styles/index.css:1 → src/styles/print.css:14)'
    ).toBeGreaterThan(0);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('under the shipped print stylesheet the report keeps the modal and sheds the chrome', async ({
    page,
  }) => {
    test.info().skip(!h.ready, h.ready ? '' : h.why);
    if (!h.ready) return;
    test.setTimeout(150_000);
    await bootModal(page, dropEventId);
    const panel = modal(page);
    // Wait for the async media so the print measurements are of a fully rendered
    // report, and read the on-screen size the print rules must change.
    await expect(panel.getByTestId('detection-image')).toBeVisible();
    const screenBox = await panel.evaluate((el) => {
      const r = el.getBoundingClientRect();
      return { w: Math.round(r.width), h: Math.round(r.height) };
    });

    const displayOf = async () =>
      page.evaluate(
        (selectors) => {
          const out: Record<string, string> = {};
          for (const [key, selector] of Object.entries(selectors)) {
            const el = document.querySelector(selector);
            out[key] = el ? getComputedStyle(el).display : 'ABSENT';
          }
          return out;
        },
        {
          header: 'header',
          nav: 'nav',
          backdrop: '[role="dialog"] > div:first-child',
          panel: '[data-testid="event-detail-modal"]',
          media: '[data-testid="event-detail-modal"] [data-testid="detection-image"]',
          summary: '[data-testid="event-detail-modal"] [data-testid="ai-analysis-section"]',
          verification: '[data-testid="event-detail-modal"] [data-testid="verification-section"]',
          riskBadge: '[data-testid="event-detail-modal"] [data-testid="risk-badge"]',
          closeBtn: '[data-testid="event-detail-modal"] [data-testid="close-modal-button"]',
          printBtn: '[data-testid="event-detail-modal"] [data-testid="print-event-button"]',
          snoozeBtn: '[data-testid="event-detail-modal"] [data-testid="snooze-button"]',
          prevBtn: '[data-testid="event-detail-modal"] [aria-label="Previous event"]',
          tabStrip: '[data-testid="event-detail-modal"] [data-testid="ai-analysis-tab"]',
          modalFooter: '[data-testid="event-detail-modal"] > div:last-child',
        }
      );

    const screen = await displayOf();
    for (const key of ['header', 'nav', 'backdrop', 'closeBtn', 'printBtn', 'tabStrip'] as const) {
      expect(screen[key], `${key} is on screen before the emulation`).not.toBe('none');
    }

    await page.emulateMedia({ media: 'print' });
    const printed = await displayOf();
    // Chrome off the page: header/nav (print.css:55-56), every button (:61
    // `button:not(.print-button)`), the Headless UI backdrop (:78) and the modal
    // footer (:435).
    for (const key of [
      'header',
      'nav',
      'backdrop',
      'closeBtn',
      'printBtn',
      'snoozeBtn',
      'prevBtn',
      'modalFooter',
      // FIXED CLAIM: the old draft said the tab strip WOULD print. print.css:424
      // (`[data-testid='event-detail-modal'] .border-b button`) hides it.
      'tabStrip',
    ] as const) {
      expect(printed[key], `${key} is off the printed page`).toBe('none');
    }
    // Content stays on the page: the panel, the selected media, the AI summary,
    // the verification section and the score badge.
    for (const key of ['panel', 'media', 'summary', 'verification', 'riskBadge'] as const) {
      expect(printed[key], `${key} stays ON the printed page`).not.toBe('none');
    }
    // And the panel becomes the page rather than a floating dialog (:403):
    // position static, full width. Measured 896x807 → 1248x1270.
    const printBox = await panel.evaluate((el) => {
      const style = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      return { w: Math.round(r.width), position: style.position, h: Math.round(r.height) };
    });
    expect(printBox.position, 'the modal prints as static content, not a floating dialog').toBe(
      'static'
    );
    expect(
      printBox.w,
      'and it widens to the page instead of keeping the dialog width'
    ).toBeGreaterThan(screenBox.w);

    await page.emulateMedia({ media: 'screen' });
    const back = await displayOf();
    for (const key of ['header', 'nav', 'backdrop', 'closeBtn', 'printBtn', 'tabStrip'] as const) {
      expect(back[key], `${key} returns when the medium returns`).not.toBe('none');
    }
    const restored = await panel.evaluate((el) => Math.round(el.getBoundingClientRect().width));
    expect(restored, 'the dialog width returns too — the emulation is reversible').toBe(
      screenBox.w
    );

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
