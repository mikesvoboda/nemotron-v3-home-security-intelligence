/**
 * F4.4 golden path — the confidence filter and the detected-objects boxes,
 * through the fake-stack drop path.
 *
 * Row clauses (verbatim from docs/reference/feature-inventory.md):
 *   F-044 (timeline): "…filters by … min confidence …" — the shipped UI choice
 *     map is CONFIDENCE_THRESHOLD (EventTimeline.tsx:86): 'high' → 0.85,
 *     'medium' → 0.70, 'any' → 0; '' removes the parameter. The list reloads
 *     server-side: min_confidence is an EXISTS through event_detections
 *     (events.py:499-518) on the SAME query the page reads.
 *   F-055 (event detail): "…shows detected objects (with confidence) and draws
 *     bounding boxes on the still image …". The modal's list is its OWN fetch
 *     (EventDetailModal.tsx:430), and boxesForSelectedImage (:452) draws every
 *     IMAGE detection sharing the selected detection's file_path on
 *     DetectionImage via BoundingBoxOverlay.
 *
 * The design doc's golden path (docs/uplevel/4n-timeline.md:93-99, verbatim):
 *   "with seeded events whose best detections score 0.90 and 0.75, 'High'
 *    shows one and 'Medium+' shows both; 'Rejected' shows the rejected seed;
 *    opening an event shows its objects and draws their boxes on the still."
 *   "Fake-stack scenario: seeded still-image events whose image files exist at
 *    file_path (`full=true` answers 404 otherwise), one with several detections
 *    and one with a rejected verdict."
 *
 * SUPPLY, measured (this is the reason the scenario book grew by two rows):
 * bulk-create writes Event rows ONLY (no junction write exists — the
 * event_detections junction has no API surface), admin seed/events writes
 * junctions but with random confidences and nonexistent mock paths, and debug
 * add-detection is aggregator-only. The DROP PATH is the only sanctioned
 * supplier of an event WITH its detections AND a real image file — and the
 * book's five pre-existing scenarios carry none of the thresholds the doc
 * names (0.90 / 0.75), so this file extended the book (scenarios.json, appended
 * so dashboard-drop.spec.ts's first-match predicate keeps person-at-door; both
 * new risk_scores stay under 60 so assertSoleAlertIsSmoke's one-alert pin is
 * untouched):
 *   f4.4-gold-high     — confirmed, detections person 0.90 + person 0.78
 *                        (the doc's "several detections": 'High' must match by
 *                        BEST detection, the modal must draw BOTH boxes), risk 52.
 *   f4.4-gold-rejected — rejected, detection cat 0.75 (≥ 0.70, so the Medium+
 *                        band includes it; the rejected verdict serves the
 *                        Rejected leg), risk 12.
 *
 * The contract tests pin the extension (test_feature_check.py:
 * test_the_scenario_book_outcomes_survive_a_fixture_image_swap now names all
 * seven; test_fake_ai_stack.py echoes every scenario's detections through the
 * fake's real /yolo26/detect route).
 *
 * Claim ledger update (frontend/tests/golden/harness.ts:3333+): this file
 * claims f4.4-gold-high AND f4.4-gold-rejected; nobody else references them.
 * A second drop of the same bytes inside the 300 s dedupe window would land
 * nothing — so this file's purge/poll/keeper pattern (event-detail-modal
 * .spec.ts:640-760, proven at this head) reuses a previous run's VERIFIED row
 * rather than demanding a fresh one.
 *
 * TIER ROBUSTNESS (UR-140 revision, T252 routed to frontend 2026-10-23). The
 * operator ran the row's posted real-tier command (--real --playwright-grep
 * "F-044" at 553dfd137, run hsi-check-20261023015333-560b8f): the stack legs
 * were all green and the smoke leg produced a REAL verdict
 * (`uncertain`, risk 0, model Qwen3VL-8B-Instruct-Q4_K_M), but the fixture poll
 * burned its 180 s and threw — its predicate demanded
 * `row.summary === scenario.verdict.summary`, the scenario book's canned
 * fake-AI string, which the real VLM never produces (it writes its own
 * summary/verdict/risk). 1 failed at the fixture, 4 did not run. UR-140: the
 * lane revises; the fix mirrors the harness's own smoke check (scripts/
 * feature_check.py:1739 smoke_problems) by branching on the row's OWN
 * provenance:
 *   - the fake gateway always writes `model_id: "fake-ai-vlm"` (a constant
 *     stem of MODEL_PATH, ai_contract/fake/app.py:87,:164);
 *   - a real VLM writes the served model's stem (its own provenance;
 *     services/vlm_analyzer.py:695), which is never the fake's constant.
 *   So `verification.model_id === 'fake-ai-vlm'` IS the tier marker, read
 *   from the row itself — no env plumbing, and the [r282] whitelist
 *   (feature_check.py:2041-2052, ten names, deliberately without
 *   FEATURE_CHECK_MODE so the option's existence cannot change an unused
 *   leg's argv) stays untouched. The list payload carries it: the events
 *   list route embeds `verification` via verification_payload()
 *   (api/routes/events.py:643), whose model_id is REQUIRED
 *   (schemas/event_verification.py:63).
 *   Anchors that stay pinned on BOTH tiers (tier-invariant, ruling 207 /
 *   UR-136: --real is the fake stack minus ai-vlm — the DETECTOR stays
 *   fake, so detection count, classes, confidences, bboxes and media_type
 *   are the fake detector's own on both tiers): all of them. Only the
 *   VLM-written verdict/risk_score/summary pins are fake-tier-only now.
 *   UR-128 deviations recorded below at each branch.
 *
 * NOT asserted here, with reasons (UR-128): the select's own click-drive leg
 * (a deep link exercises the same server filter end-to-end, and the unit tests
 * already pin CONFIDENCE_THRESHOLD's mapping); ?min_confidence deep-link
 * select-sync beyond the canonical values (unit-pinned); a video detection in
 * the modal (the book ships only stills; download-media.spec.ts owns the video
 * branch's 500-envelope witness). The real tier IS exercised: the fixture
 * converges on any verified row and pins only tier-invariant facts on it
 * (detections), branching the VLM-written pins on the row's own model_id —
 * on the real tier the model's own verdict/risk/summary are what the rows
 * carry, and this file asserts the shipped UI against whatever the tier's
 * verifier wrote rather than demanding the book's strings. What is still NOT
 * asserted on the real tier: the book's exact verdict/risk/summary values
 * (fake-only by definition), and leg 3's seed-match guarantee — see the
 * deviation note at that leg.
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
  closedByGuard,
  hardDeleteFixtureRows,
  loginAsAdminShell as loginAsAdmin,
  quietBoot,
  readTimelineHarness,
  seedDefaultViewMode,
  seedTourDismissed,
  waitForEventCards,
  type Session,
  type TimelineHarness,
} from '../harness';

/* ----------------------------- the scenario claim -------------------------- */

interface BookScenario {
  name: string;
  image: string;
  detections: {
    class: string;
    confidence: number;
    bbox: { x: number; y: number; width: number; height: number };
  }[];
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

interface FilterHarness {
  ready: true;
  high: BookScenario;
  rejected: BookScenario;
  highImagePath: string;
  rejectedImagePath: string;
  highCameraId: string;
  rejectedCameraId: string;
  cameraRoot: string;
  timeline: TimelineHarness;
}

type FilterState = FilterHarness | { ready: false; why: string };

/** The two scenarios this file claims, by name. Appended to the book's END so
 *  dashboard-drop.spec.ts's predicate ("the book's first fast confirmed
 *  non-harness-smoke row") still resolves to person-at-door. */
const HIGH_SCENARIO = 'f4.4-gold-high';
const REJECTED_SCENARIO = 'f4.4-gold-rejected';

/** The tier marker, read from the row itself: the fake gateway writes this
 *  exact model_id on EVERY verification it produces — a constant stem of its
 *  MODEL_PATH (ai_contract/fake/app.py:87 MODEL_PATH "/models/fake-ai-vlm.gguf",
 *  :164 provenance = {"engine": build_info, "model_id": stem}). A real VLM
 *  writes the served model's stem (services/vlm_analyzer.py:695 takes the
 *  verdict's own provenance), which is never this constant. So
 *  `verification.model_id === 'fake-ai-vlm'` classifies the row's tier with
 *  no env plumbing — FEATURE_CHECK_MODE is deliberately absent from the [r282]
 *  container whitelist (scripts/feature_check.py:2041-2052) so a leg's argv
 *  cannot depend on the mode. The list payload carries the field: the events
 *  list route embeds `verification` via verification_payload()
 *  (api/routes/events.py:643) whose model_id is REQUIRED
 *  (api/schemas/event_verification.py:63). */
const FAKE_VLM_MODEL_ID = 'fake-ai-vlm';

/** The verdict vocabulary a MODEL may write (scripts/feature_check.py:206
 *  MODEL_VERDICTS — the same set smoke_problems demands on --real). A
 *  `verification_failed` row is the analyzer failing closed, not a model
 *  verdict; step 5 rejects it by name on the real tier. */
const MODEL_VERDICTS = ['confirmed', 'rejected', 'uncertain'] as const;

/** Collection-time and defensive, like readDropHarness() in
 *  event-detail-modal.spec.ts: any missing piece is a skip reason, never a
 *  `--list` crash outside the harness. */
function readFilterHarness(): FilterState {
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
  let scenarios: BookScenario[];
  let cameras: Record<string, string>;
  try {
    // Parse to unknown first, then shape-check — the same discipline
    // readHarnessAlerts() documents (JSON.parse("null") is fine JS).
    const book = JSON.parse(readFileSync(bookPath, 'utf8')) as unknown;
    const parsedCameras = JSON.parse(readFileSync(camerasPath, 'utf8')) as unknown;
    if (
      typeof book !== 'object' ||
      book === null ||
      !Array.isArray((book as { scenarios?: unknown }).scenarios)
    ) {
      return { ready: false, why: `${bookPath} has no "scenarios" array` };
    }
    if (
      typeof parsedCameras !== 'object' ||
      parsedCameras === null ||
      Array.isArray(parsedCameras)
    ) {
      return { ready: false, why: `${camerasPath} is not a JSON object` };
    }
    scenarios = (book as { scenarios: BookScenario[] }).scenarios;
    cameras = parsedCameras as Record<string, string>;
  } catch (error) {
    return { ready: false, why: `harness JSON unreadable: ${String(error)}` };
  }
  const high = scenarios.find((entry) => entry.name === HIGH_SCENARIO);
  const rejected = scenarios.find((entry) => entry.name === REJECTED_SCENARIO);
  if (!high) return { ready: false, why: `scenario book has no ${HIGH_SCENARIO}` };
  if (!rejected) return { ready: false, why: `scenario book has no ${REJECTED_SCENARIO}` };
  if (high.reply_delay_seconds) return { ready: false, why: `${HIGH_SCENARIO} delays its reply` };
  if (rejected.reply_delay_seconds) {
    return { ready: false, why: `${REJECTED_SCENARIO} delays its reply` };
  }
  // The thresholds this file's legs assert are book facts, pinned here so a
  // book edit reddens this file instead of silently re-pointing the legs.
  if (high.detections[0]?.confidence !== 0.9) {
    return { ready: false, why: `${HIGH_SCENARIO} best detection is not 0.90` };
  }
  if (rejected.detections[0]?.confidence !== 0.75) {
    return { ready: false, why: `${REJECTED_SCENARIO} detection is not 0.75` };
  }
  const highCameraId = cameras[high.name];
  const rejectedCameraId = cameras[rejected.name];
  if (!highCameraId) return { ready: false, why: `harness seeded no camera named ${high.name}` };
  if (!rejectedCameraId) {
    return { ready: false, why: `harness seeded no camera named ${rejected.name}` };
  }
  const highImagePath = path.join(path.dirname(bookPath), high.image);
  const rejectedImagePath = path.join(path.dirname(bookPath), rejected.image);
  if (!existsSync(highImagePath))
    return { ready: false, why: `no scenario image at ${highImagePath}` };
  if (!existsSync(rejectedImagePath)) {
    return { ready: false, why: `no scenario image at ${rejectedImagePath}` };
  }
  return {
    ready: true,
    high,
    rejected,
    highImagePath,
    rejectedImagePath,
    highCameraId,
    rejectedCameraId,
    cameraRoot,
    timeline,
  };
}

const h = readFilterHarness();
test.skip(!h.ready, h.ready ? '' : h.why);
const harness = h as FilterHarness;
const timeline = harness.timeline;

/* --------------------------------- shapes ---------------------------------- */

interface EventRow {
  id: number;
  camera_id: string;
  started_at: string;
  risk_score: number | null;
  risk_level: string | null;
  summary: string | null;
  detection_ids: number[];
  verification?: { verdict: string; model_id?: string } | null;
}

interface DetectionItem {
  id: number;
  detected_at: string;
  object_type: string | null;
  confidence: number | null;
  media_type: string | null;
  file_path: string | null;
  bbox_x: number | null;
  bbox_y: number | null;
  bbox_width: number | null;
  bbox_height: number | null;
}

const eventRow = (session: Session, id: number) =>
  api<EventRow>(timeline, session, `/api/events/${id}`);
const detectionItems = (session: Session, id: number) =>
  api<{ items: DetectionItem[]; pagination: { total: number } }>(
    timeline,
    session,
    `/api/events/${id}/detections?limit=100`
  );

/** The scenario's DETECTOR-written identity: same count, same class@confidence
 *  multiset. This is the tier-invariant anchor — the detector is the fake
 *  stack's own on BOTH tiers (ruling 207 / UR-136: --real is the fake stack
 *  minus ai-vlm), so the set identifies the scenario's row regardless of which
 *  tier's VLM verified it. Bboxes are leg 5's business; identity needs the
 *  set only. */
function detectionsMatchBook(items: DetectionItem[], scenario: BookScenario): boolean {
  if (items.length !== scenario.detections.length) return false;
  const key = (objectType: string | null, confidence: number | null) =>
    `${objectType}@${confidence}`;
  const book = scenario.detections.map((d) => key(d.class, d.confidence)).sort();
  const row = items.map((d) => key(d.object_type, d.confidence)).sort();
  return book.every((k, i) => k === row[i]);
}

/* scripts/feature-check.sh lives at the repo root: FOUR up from
 * frontend/tests/golden/timeline (the event-detail-modal.spec.ts precedent). */
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../..');

/* -------------------------------- fixtures --------------------------------- */

let highEventId: number;
let rejectedEventId: number;
let highCameraName: string;
/** Rows this run owns (residue + older duplicates), hard-deleted in afterAll. */
let ownedEventIds: number[] = [];

/**
 * Drop one scenario image and converge on the event it (or an earlier run)
 * produced. The keeper pattern is event-detail-modal.spec.ts's, proven here:
 * the 300 s content-hash dedupe makes the watcher SKIP a re-drop outright
 * (file_watcher.py:871-878), and dedupe.clear_hash has no API route — so a
 * re-run reuses the previous run's VERIFIED row instead of hanging in the poll.
 *
 * One camera per scenario, both images dropped in beforeAll: separate cameras
 * mean each camera's exactly-one-event read is its own, and neither scenario's
 * row can disturb the other's count.
 */
async function dropAndConverge(
  session: Session,
  scenario: BookScenario,
  cameraId: string,
  imagePath: string
): Promise<number> {
  // 1. Read this camera's rows BEFORE the drop: a verified row the book's
  //    DETECTIONS identify is the reuse candidate (the poll below finds it
  //    even when the dedupe suppressed this drop); everything else on the
  //    camera is residue this run owns and step 4 collects for afterAll.
  //    Nothing is deleted here — deleting before the drop would destroy the
  //    very row a suppressed run needs to reuse.
  await api<{ items: EventRow[] }>(
    timeline,
    session,
    `/api/events?camera_id=${encodeURIComponent(cameraId)}&limit=100`
  );

  // 2. The drop — O2.2's own helper, the sanctioned supply for VLM-shaped rows.
  execFileSync(
    path.join(repoRoot, 'scripts/feature-check.sh'),
    ['drop', imagePath, scenario.name],
    {
      cwd: repoRoot,
      env: { ...process.env, FEATURE_CHECK_CAMERA_ROOT: harness.cameraRoot },
      encoding: 'utf8',
      timeout: 30_000,
    }
  );

  // 3. Poll for the verified row (the keeper path returns instantly when the
  //    dedupe suppressed this drop).
  //
  //    TIER-ROBUST predicate (the UR-140 revision): candidates are VERIFIED
  //    rows on this camera — `row.verification?.verdict` truthy, newest
  //    first. Identity is decided by the row's OWN provenance:
  //      - fake-tier row (model_id === FAKE_VLM_MODEL_ID): must name the
  //        book's canned summary, as before — the fake echoes the book
  //        verbatim, so a fake row whose summary differs is a DIFFERENT
  //        scenario's row, not this one;
  //      - real-tier row (any other model_id): identified by the
  //        DETECTOR-written facts instead (detectionsMatchBook) — the
  //        scenario's exact detection set is the fake detector's own on BOTH
  //        tiers (ruling 207 / UR-136), and the verifier is per-event, so
  //        verified-row + this-detection-set IS this scenario. Its
  //        verdict/summary are the model's own and are not demanded to match
  //        anything here.
  //    A fake candidate that fails the summary equality is still reported to
  //    the log (the 2026-10-23 run could not distinguish "no row" from
  //    "unmatched rows"; this poll can, at the last tick).
  const deadline = Date.now() + 180_000;
  let chosen: EventRow | undefined;
  while (Date.now() < deadline) {
    const list = await api<{ items: EventRow[] }>(
      timeline,
      session,
      `/api/events?camera_id=${encodeURIComponent(cameraId)}&limit=100`
    );
    const verified = [...list.items]
      .filter((row) => row.verification?.verdict)
      .sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime());
    // Pass 1 — rows this poll can classify from the LIST payload alone: fake
    // rows by their summary, real rows by their detections (one fetch per
    // real candidate, bounded by the camera's purge-kept row count).
    const classified: EventRow[] = [];
    for (const row of verified) {
      if (row.verification?.model_id === FAKE_VLM_MODEL_ID) {
        if (row.summary === scenario.verdict.summary) classified.push(row);
      } else {
        const dets = await detectionItems(session, row.id);
        if (detectionsMatchBook(dets.items, scenario)) classified.push(row);
      }
    }
    if (classified.length > 0) {
      // A MODEL verdict outranks a fail-closed row regardless of recency: a
      // re-drop after the dedupe window can land a new verification_failed
      // row ON TOP of the previous run's good keeper — the good row must
      // still win. When ONLY fail-closed rows exist, waiting longer is
      // pointless (one drop = one event = one verification attempt), so the
      // loop exits and step 5 rejects the row by name.
      const good = classified.filter((r) =>
        MODEL_VERDICTS.includes(r.verification?.verdict as (typeof MODEL_VERDICTS)[number])
      );
      chosen = good[0] ?? classified[0];
      break;
    }
    if (verified.length > 0) {
      // Log-only diagnostic, never a throw: an unmatched verified row is
      // stack state this file must not own (it may be another scenario's).
      console.warn(
        `golden fixture: verified row(s) on ${cameraId} unmatched — ` +
          verified
            .map(
              (r) =>
                `id ${r.id} verdict=${r.verification?.verdict} model=${r.verification?.model_id ?? '?'} summary=${JSON.stringify(r.summary)}`
            )
            .join('; ')
      );
    }
    await new Promise((resolve) => setTimeout(resolve, 5_000));
  }
  if (!chosen) {
    throw new Error(
      `golden fixture: ${scenario.name} produced no verified event on camera ${cameraId} ` +
        'in 180 s (and none was kept from an earlier run), so the stack is not supplying ' +
        'the scenario this file is written against'
    );
  }

  // 4. Own every OTHER row on this camera (residue from a crashed run). The
  //    surviving keeper is what a suppressed-drop run reuses, so it is never
  //    deleted here.
  const survivors = await api<{ items: EventRow[] }>(
    timeline,
    session,
    `/api/events?camera_id=${encodeURIComponent(cameraId)}&limit=100`
  );
  ownedEventIds.push(...survivors.items.filter((r) => r.id !== chosen.id).map((r) => r.id));

  // 5. The server's own truth, asserted HERE so every leg mirrors pixels
  //    against a row this fixture knows is what the book says.
  //
  //    TIER BRANCH (UR-140, mirroring smoke_problems scripts/feature_check.py
  //    :1739-1777): on the FAKE tier the fake echoed the book, so the book's
  //    verdict/risk/summary are pinned as before. On the REAL tier the VLM
  //    wrote its own verdict/risk/summary — pinning the book's strings there
  //    is exactly the failure that burned the 2026-10-23 run — so the row's
  //    identity rests on the detector-written facts (the poll above) and this
  //    step asserts only what any tier's verifier owes: a MODEL verdict
  //    (scripts/feature_check.py:206 MODEL_VERDICTS). `verification_failed`
  //    is the analyzer failing closed, not a model verdict — named here
  //    because a real-tier row CAN carry it and, within the 300 s dedupe
  //    window, a retried run would otherwise reuse that row silently.
  const row = await eventRow(session, chosen.id);
  const isFake = row.verification?.model_id === FAKE_VLM_MODEL_ID;
  if (isFake) {
    if (row.risk_score !== scenario.verdict.risk_score) {
      throw new Error(
        `golden fixture: dropped event risk_score=${String(row.risk_score)}, book says ` +
          scenario.verdict.risk_score
      );
    }
    if (row.verification?.verdict !== scenario.verdict.verdict) {
      throw new Error(
        `golden fixture: dropped event verdict=${String(row.verification?.verdict)}, book says ` +
          scenario.verdict.verdict
      );
    }
    if (row.summary !== scenario.verdict.summary) {
      throw new Error(
        `golden fixture: row summary ${JSON.stringify(row.summary)} is not the book's ` +
          `${JSON.stringify(scenario.verdict.summary)} — the row is not ${scenario.name}'s`
      );
    }
  } else {
    const verdict = row.verification?.verdict;
    if (
      verdict === undefined ||
      !MODEL_VERDICTS.includes(verdict as (typeof MODEL_VERDICTS)[number])
    ) {
      throw new Error(
        `golden fixture: real-tier row ${chosen.id} carries verdict ` +
          `${JSON.stringify(verdict)} — a model's verdict is one of ` +
          `${MODEL_VERDICTS.join(', ')}; 'verification_failed' is the analyzer failing closed, ` +
          'not a model verdict (re-drop after the 300 s dedupe window retries it)'
      );
    }
    // UR-128 deviation, recorded: on the real tier this file does NOT pin
    // risk_score or summary — they are the served model's own output (the
    // 2026-10-23 run's smoke event: verdict uncertain, risk 0, the model's
    // own summary). The fake tier's pins above remain the book's exact
    // values. Detection pins below run on BOTH tiers (tier-invariant).
  }
  const dets = await detectionItems(session, chosen.id);
  if (dets.items.length !== scenario.detections.length) {
    throw new Error(
      `golden fixture: ${dets.items.length} detections, the book declares ` +
        `${scenario.detections.length} for ${scenario.name}`
    );
  }
  if (dets.items.some((d) => d.media_type !== 'image')) {
    throw new Error(
      `golden fixture: a non-image detection arrived for ${scenario.name}, so the file's ` +
        'still-image claims need re-measuring before the legs run'
    );
  }
  return chosen.id;
}

test.beforeAll(async () => {
  // Two drops + verifier replies + possible dedupe waits: the HOOK's timeout.
  // Each test body also calls test.setTimeout(90_000) — inside a test,
  // test.setTimeout moves THAT test's clock, not the hook's.
  test.setTimeout(480_000);
  const session = await adminSession(timeline);
  highEventId = await dropAndConverge(
    session,
    harness.high,
    harness.highCameraId,
    harness.highImagePath
  );
  rejectedEventId = await dropAndConverge(
    session,
    harness.rejected,
    harness.rejectedCameraId,
    harness.rejectedImagePath
  );

  const cameras = await api<CameraRow[] | { items: CameraRow[] }>(
    timeline,
    session,
    '/api/cameras'
  );
  const list = Array.isArray(cameras) ? cameras : cameras.items;
  highCameraName = list.find((c) => c.id === harness.highCameraId)?.name ?? '';
  if (!highCameraName) {
    throw new Error(`golden fixture: no camera name for id ${harness.highCameraId}`);
  }
});

test.afterAll(async () => {
  // DELETE /api/events/bulk with soft_delete:false cascades the detections and
  // their verification rows (the harness helper the modal spec's afterAll
  // cites). Settle, don't throw; the next run's purge removes anything left.
  if (ownedEventIds.length === 0) return;
  const session = await adminSession(timeline);
  await hardDeleteFixtureRows(timeline, session, ownedEventIds);
});

interface CameraRow {
  id: string;
  name: string;
}

/** Boot a /timeline deep link (the filter legs' own scope), quieted. The
 *  argument is the FULL path+query ('/timeline?camera=…'), the shape quietBoot
 *  itself takes: prefixing '/timeline' here doubled the segment
 *  ('/timeline/timeline?…' → the SPA's NotFoundPage, run 39814494113), and a
 *  404 is none of settleBootTimeline's shed coats, so every drive burned its
 *  whole 20s race before timing out. */
async function bootTimeline(page: Page, path: string): Promise<void> {
  await seedTourDismissed(page);
  await seedDefaultViewMode(page);
  await loginAsAdmin(page, timeline);
  await quietBoot(page, timeline, path);
  await expect(page.getByTestId('timeline-page')).toBeVisible();
  await waitForEventCards(page);
}

/* ---------------------------------- legs ----------------------------------- */

test.describe('F4.4 confidence filter (F-044) + detected objects (F-055) — the golden path', () => {
  test("deep link ?min_confidence=0.85 ('High') shows only the 0.90 event; the select holds the choice", async ({
    page,
  }) => {
    test.setTimeout(90_000);
    const session = await adminSession(timeline);
    // Ground truth first, from the endpoint the page itself reads.
    const truth = await api<{ items: EventRow[] }>(
      timeline,
      session,
      `/api/events?limit=100&camera_id=${encodeURIComponent(harness.highCameraId)}&min_confidence=0.85`
    );
    expect(
      truth.items.map((r) => r.id),
      'the server answer IS the leg: the 0.85 floor matches the 0.90 event and not the 0.75 one'
    ).toEqual([highEventId]);

    await bootTimeline(
      page,
      `/timeline?camera=${encodeURIComponent(harness.highCameraId)}&min_confidence=0.85`
    );
    await expect(
      page.locator('#confidence-filter'),
      "the deep link's canonical 0.85 reverse-maps to the High choice"
    ).toHaveValue('high');
    await expect(
      page.getByTestId(`event-card-${highEventId}`),
      'the 0.90 event renders under High'
    ).toBeVisible();
    // The 0.75 event lives on ANOTHER camera, so camera-scoped absence proves
    // nothing about the confidence filter. The filter's exclusion is proven at
    // the API level above (the 0.85 answer holds one row) and again at
    // unfiltered scope in the Medium+ leg's mirror — here the scope's own
    // mirror is the assertion: one row in, one card out.
    await expect(
      page.getByTestId(/^event-card-\d+$/),
      "High shows one — the doc's count, on the scope this boot read"
    ).toHaveCount(1);
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test("deep link ?min_confidence=0.7 ('Medium+') shows both seeded events; DOM mirrors the API", async ({
    page,
  }) => {
    test.setTimeout(90_000);
    const session = await adminSession(timeline);
    const truth = await api<{ items: EventRow[] }>(
      timeline,
      session,
      `/api/events?limit=100&min_confidence=0.7`
    );
    expect(
      truth.items.some((r) => r.id === highEventId),
      'the 0.90 event clears 0.7'
    ).toBe(true);
    expect(
      truth.items.some((r) => r.id === rejectedEventId),
      'the 0.75 event clears 0.7 too — the Medium+ band holds both'
    ).toBe(true);

    await bootTimeline(page, '/timeline?min_confidence=0.7');
    await expect(
      page.locator('#confidence-filter'),
      'the canonical 0.7 reverse-maps to Medium+'
    ).toHaveValue('medium');
    await expect(
      page.getByTestId(`event-card-${highEventId}`),
      'the 0.90 event renders under Medium+'
    ).toBeVisible();
    await expect(
      page.getByTestId(`event-card-${rejectedEventId}`),
      'the 0.75 event renders under Medium+'
    ).toBeVisible();
    // The DOM↔API mirror for THIS scope, unfiltered: both seeded rows plus
    // whatever else the stack legitimately holds under 0.7. This is ALSO where
    // "High shows one, Medium+ shows both" gets its teeth at one scope: the
    // API answer above holds both ids, and here the 0.90-vs-0.75 split is
    // visible in one DOM. Bounded by has_more like the event-list precedent;
    // with one page it is exact.
    const mediumScope = await api<{ items: EventRow[]; pagination?: { has_more?: boolean } }>(
      timeline,
      session,
      '/api/events?limit=20&min_confidence=0.7'
    );
    if (!mediumScope.pagination?.has_more) {
      await expect(
        page.getByTestId(/^event-card-\d+$/),
        `DOM cards mirror GET /api/events?min_confidence=0.7 (${mediumScope.items.length})`
      ).toHaveCount(mediumScope.items.length);
      expect(
        mediumScope.items.some((r) => r.id === highEventId) &&
          mediumScope.items.some((r) => r.id === rejectedEventId),
        'both seeds are inside the mirrored first page, so the two card assertions above are not vacuous'
      ).toBe(true);
    }
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('deep link ?verdict=rejected shows the rejected seed and the select holds it', async ({
    page,
  }) => {
    test.setTimeout(90_000);
    const session = await adminSession(timeline);
    // TIER-AWARE truth (UR-140): the doc's "'Rejected' shows the rejected
    // seed" names the FAKE tier's behavior — the fake echoes the book's
    // rejected verdict, so the camera's only row IS the match. On the real
    // tier the verdict is the served model's own judgement of the cat image,
    // which this file does not control — so the pinned EXPECTATION is what
    // the server answers for this camera, and the UI's job is to mirror it.
    // UR-128 deviation, recorded: on the real tier this leg proves the
    // verdict filter's end-to-end mirror (the deep link's answer renders
    // exactly), not the seed-match guarantee, which is fake-tier-only.
    const truth = await api<{ items: EventRow[] }>(
      timeline,
      session,
      `/api/events?limit=100&camera_id=${encodeURIComponent(harness.rejectedCameraId)}&verdict=rejected`
    );
    const rejectedRow = truth.items.find((r) => r.id === rejectedEventId);
    if (rejectedRow) {
      // Either tier: the seed matched the filter. The camera holds it alone
      // (one event per drop, one camera per scenario) — the doc's clause.
      expect(
        truth.items.map((r) => r.id),
        'the rejected camera holds exactly the rejected seed under this filter'
      ).toEqual([rejectedEventId]);
    }
    // When the seed did NOT match (reachable only on the real tier — the fake
    // echoes the book's rejected verdict, so its row always matches), there is
    // no seed-side API fact to pin: the answer is whatever this camera's
    // remaining rows match, and the DOM mirror below is the assertion. That
    // branch is the recorded UR-128 deviation.

    await bootTimeline(
      page,
      `/timeline?camera=${encodeURIComponent(harness.rejectedCameraId)}&verdict=rejected`
    );
    await expect(
      page.locator('#verification-filter'),
      'the verdict select holds the deep-linked value'
    ).toHaveValue('rejected');
    if (rejectedRow) {
      await expect(
        page.getByTestId(`event-card-${rejectedEventId}`),
        "'Rejected' shows the rejected seed — the doc's clause, end to end"
      ).toBeVisible();
    } else {
      // The model did not reject this image, so the filter answers without
      // it — the mirror IS the assertion, exactly as leg 2's mirror is: the
      // camera-scoped verdict=rejected answer (limit=20, the UI's page,
      // guarded by has_more like leg 2) mirrored as DOM card count.
      const mirror = await api<{ items: EventRow[]; pagination?: { has_more?: boolean } }>(
        timeline,
        session,
        `/api/events?limit=20&camera_id=${encodeURIComponent(harness.rejectedCameraId)}&verdict=rejected`
      );
      if (!mirror.pagination?.has_more) {
        await expect(
          page.getByTestId(/^event-card-\d+$/),
          `DOM mirrors the verdict=rejected answer (${mirror.items.length}) — on the real tier the seed's verdict is the model's own`
        ).toHaveCount(mirror.items.length);
      }
    }
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('selecting High in the UI sends min_confidence=0.85 and the list reloads to the 0.90 event only', async ({
    page,
  }) => {
    test.setTimeout(90_000);
    const session = await adminSession(timeline);
    await bootTimeline(page, `/timeline?camera=${encodeURIComponent(harness.highCameraId)}`);

    // The shipped control, driven as a user drives it (the panel is open when a
    // camera deep link arrives; EventTimeline.tsx:349).
    await page.locator('#confidence-filter').selectOption('high');

    // The filter is server-side, so the truth of "sent" is the DOM result
    // against the endpoint's answer for the same query.
    const truth = await api<{ items: EventRow[] }>(
      timeline,
      session,
      `/api/events?limit=100&camera_id=${encodeURIComponent(harness.highCameraId)}&min_confidence=0.85`
    );
    expect(
      truth.items.map((r) => r.id),
      'the 0.85 answer is exactly the seeded event'
    ).toEqual([highEventId]);
    await expect(
      page.getByTestId(`event-card-${highEventId}`),
      'the list reloaded: the 0.90 event remains'
    ).toBeVisible();
    // And the rest of the stack's rows (this camera has only the one seeded row
    // — the purge in beforeAll owns the camera — so the card count IS one).
    await expect(
      page.getByTestId(/^event-card-\d+$/),
      'High shows one on this camera — the doc counts, witnessed'
    ).toHaveCount(1);
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('opening the high event shows its objects (2) and draws their boxes on the still', async ({
    page,
  }) => {
    test.setTimeout(90_000);
    const session = await adminSession(timeline);
    const row = await eventRow(session, highEventId);
    const dets = await detectionItems(session, highEventId);
    const truth = [...dets.items].sort((a, b) => (b.confidence ?? 0) - (a.confidence ?? 0));
    expect(truth.length, 'the book declared two detections; the row carries them').toBe(2);
    expect(
      truth.map((d) => `${d.object_type}@${d.confidence}`),
      '0.90 first, 0.78 second (the modal sorts by confidence)'
    ).toEqual(['person@0.9', 'person@0.78']);
    expect(
      row.detection_ids.length,
      'the row links both detections (the junction the drop path wrote)'
    ).toBe(2);

    await seedTourDismissed(page);
    await seedDefaultViewMode(page);
    await loginAsAdmin(page, timeline);
    await quietBoot(
      page,
      timeline,
      `/timeline?camera=${encodeURIComponent(harness.highCameraId)}&event=${highEventId}`
    );
    await expect(page.getByTestId('timeline-page')).toBeVisible();
    const panel = page.getByTestId('event-detail-modal');
    await expect(panel, 'the `?event=` deep link opens the modal').toBeVisible();

    // THE OBJECTS: the modal's own fetch fills "Detected Objects (2)"
    // (EventDetailModal.tsx:888-891), the F-055 list.
    const objects = panel.getByTestId('detection-objects');
    await expect(objects).toBeVisible();
    await expect(objects, 'the header counts what the modal fetched itself').toHaveText(
      /Detected Objects \(2\)/
    );
    // The list rows: sorted by confidence desc (:953 sortDetectionsByConfidence).
    const objectRows = objects.locator(':scope > div.grid > div');
    await expect(objectRows, 'one row per detection').toHaveCount(2);
    await expect(objectRows.nth(0), 'the 90% detection reads its label').toHaveText(/person/);
    await expect(objectRows.nth(0)).toHaveText(/90%/);
    await expect(objectRows.nth(1)).toHaveText(/person/);
    await expect(objectRows.nth(1)).toHaveText(/78%/);

    // THE BOXES: the auto-selected first detection is the highest-confidence
    // one (EventDetailModal.tsx:250), its still is the selected-detection
    // branch (:755), and boxesForSelectedImage passes BOTH detections (same
    // file_path, both image, both with bboxes). The overlay is BoundingBox
    // Overlay's SVG (pointer-events-none absolute; viewBox = natural size).
    // The modal auto-selected the 0.90 detection, so its still's natural size
    // IS the image the book ships — the fake echoes its dims on the wire and
    // detector_client stores them, so the API's file is the same pixels.
    await expect(
      panel.locator('[data-testid="detection-image"]'),
      'the selected-detection still renders'
    ).toBeVisible();
    // naturalWidth of the full-size fetch equals the fixture's encoded size —
    // read it and assert the overlay's viewBox against THAT, not against a
    // hardcoded 1200x900, so the mirror is the pixels themselves.
    const natural = await panel
      .locator('[data-testid="detection-image"]')
      .evaluate((img: Element) =>
        img instanceof HTMLImageElement
          ? { w: img.naturalWidth, h: img.naturalHeight }
          : { w: 0, h: 0 }
      );
    expect(
      natural.w,
      'the full-size still decoded (the doc: file exists at file_path)'
    ).toBeGreaterThan(0);

    const overlay = panel.locator('svg.pointer-events-none.absolute');
    await expect(overlay, 'the overlay renders once the image loads').toBeVisible();
    await expect(overlay, 'viewBox mirrors the still the boxes were drawn on').toHaveAttribute(
      'viewBox',
      `0 0 ${natural.w} ${natural.h}`
    );
    const rects = overlay.locator('rect[stroke]');
    await expect(
      rects,
      'BOTH detections drew a box (several detections, several boxes)'
    ).toHaveCount(2);
    // Each rect's geometry mirrors the book's bbox for that detection, in the
    // image's own pixel space (the letterbox fix keeps it there).
    const geometry = await rects.evaluateAll((els) =>
      els.map((el) => ({
        x: el.getAttribute('x'),
        y: el.getAttribute('y'),
        w: el.getAttribute('width'),
        h: el.getAttribute('height'),
      }))
    );
    const expected = [...harness.high.detections]
      .sort((a, b) => b.confidence - a.confidence)
      .map((d) => ({
        x: String(d.bbox.x),
        y: String(d.bbox.y),
        w: String(d.bbox.width),
        h: String(d.bbox.height),
      }));
    expect(
      geometry,
      'the boxes sit where the book declares them — pixels, not percentages'
    ).toEqual(expected);
    // And the labels ride along (showLabels renders label + confidence text).
    const overlayText = await overlay.textContent();
    expect(overlayText, 'the 90% box is labelled').toContain('person');
    expect(overlayText).toContain('90%');
    expect(overlayText, 'the 78% box is labelled too').toContain('78%');

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
