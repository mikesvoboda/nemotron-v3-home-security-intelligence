/**
 * FE-2 golden path (F2.3): F-038 — the AI Performance Summary Row (ON by
 * default): detection/analysis queue depth, events per minute, stage
 * latencies and DLQ error count, refreshed every 5 s.
 *
 * Decided from shipped code + one measured probe-stack read before writing
 * (each claim cites where). Probe reads are recon, never witnesses (ruling
 * 114): they motivated the shapes below; the witness is CI's own run.
 *
 * - The row's clause names FOUR numbers. Three are rendered by
 *   AIPerformanceSummaryRow.tsx as IndicatorCards whose value string is
 *   derived by the component's OWN code, mirrored below with cites:
 *     • Queues    = `${detectionQueueDepth + analysisQueueDepth} queued`
 *       (:420-422; the two depths come from GET /api/system/telemetry
 *       queues.*_queue, hook fallback chain useAIMetrics.ts:378-381).
 *     • Throughput = `${calculatedThroughput.toFixed(1)}/min` (:445-447;
 *       throughputPerMinute = events_per_min from GET /api/system/
 *       performance inference.throughput.events_per_min — DashboardPage
 *       passes it (:517) so the totalEvents fallback at :338-339 never runs).
 *     • Errors    = totalErrors === 0 ? 'None' : `${totalErrors} total`
 *       (:471-473) where totalErrors = Σ hsi_pipeline_errors_total counters
 *       from the /api/metrics exposition (DashboardPage.tsx:513-516,
 *       metricsParser.ts:368 getCountersByLabel). MEASURED on the probe
 *       stack: this counter is CUMULATIVE and LIVE (+6 per 6 s, 3732→3744),
 *       so this mirror is an agreement poll — each poll re-reads
 *       /api/metrics and compares to the DOM; a persistent mismatch fails
 *       naming both values. A one-shot equality could race the counter.
 * - The fourth number — "DLQ error count" — was the row's break and is now
 *   FIXED (ruling 130: this bullet asserted the break; it now asserts the
 *   fix). What was true when this spec was written: the hook fetched
 *   GET /api/dlq/stats into `dlqItems` (useAIMetrics.ts:313, :378) and NO
 *   rendered component read it — its only reader, ai/PipelineHealthPanel.tsx
 *   :105,112, has zero render sites, and PipelineQueues.tsx's DLQRow reads a
 *   DIFFERENT call (queuesStatus, :89-90, :161-162) in a widget that is off by
 *   default. What the fix changed, and where to look:
 *     • A sixth card, testId="dlq-indicator", in the row the clause is about:
 *       AIPerformanceSummaryRow.tsx:497-519 — label "DLQ" (:499), value
 *       `${totalDlqItems} parked` / "None" at zero (:500), status from
 *       getDlqStatus (:185, stricter than getErrorStatus: 1 parked is already
 *       yellow, ≥10 red, because a parked job is a CURRENT condition rather
 *       than a cumulative counter).
 *     • Fed from the field that always existed: DashboardPage.tsx:521
 *       `dlqCounts: aiMetrics.dlqItems`.
 *     • The card's total is the same arithmetic the API uses: the component
 *       sums the map (:334), and backend/services/retry_handler.py:628 sets
 *       total_count = detection_count + analysis_count. The hook drops
 *       zero-valued keys (useAIMetrics.ts:315-322), so summing `dlqItems`
 *       reproduces total_count exactly rather than approximately.
 *   WHY THIS SPEC CANNOT PROVE THE WIRE, AND WHAT DOES: on the golden stack
 *   the DLQ is empty, and an empty DLQ renders "None" whether the wire is live
 *   or the card is a hardcoded "None". So test 2 below asserts the card
 *   EXISTS, is the row's only DLQ surface, and agrees with the endpoint's own
 *   number — and the load-bearing falsification of the WIRING lives in
 *   DashboardPage.test.tsx ("passes the hook DLQ counts through to the AI
 *   summary row"), which fakes dlqItems={detection:3, analysis:2} and asserts
 *   data-dlq-total="5". That test was mutation-controlled: deleting
 *   DashboardPage.tsx:521 turns it RED.
 * - The latency cards render formatLatency(:194-199: null/undefined → '--',
 *   < 1 → '< 1ms', < 1000 → `${round}ms`) over latency?.avg_ms with the
 *   hook's documented preference (useAIMetrics.ts:328-357): Prometheus
 *   histogram first (metricsParser.ts:343-361 reads
 *   hsi_ai_request_duration_seconds / hsi_stage_duration_seconds — ZERO
 *   lines of either family in the probe exposition), else the telemetry
 *   stage latencies, which the fake stack reports as 0.0 with
 *   sample_count 0. So the golden regime renders '< 1ms' for both cards —
 *   mirrored from the SAME endpoint the fallback reads, not hardcoded.
 * - "refreshed every 5 s" is the pollingInterval at DashboardPage.tsx:129
 *   feeding the setInterval in useAIMetrics.ts:413-419. Same ruling as this
 *   lane's F-040 (pipeline-telemetry.spec.ts header): the golden spec
 *   CITES the shipped 5 s default and does not manufacture a timed wait —
 *   timing a wall-clock poll needs a second data mutation the guard rightly
 *   forbids; the cadence itself is unit-territory.
 * - Guard: no page.route anywhere; the Node reads go through harness.api
 *   (never the UI origin); every body closes with the tripwire.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import {
  adminSession,
  api,
  closedByGuard,
  loginAsAdmin,
  quietBoot,
  readDashboardHarness,
  seedTourDismissed,
  type DashboardHarness,
} from './harness';

const harness = readDashboardHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

interface Telemetry {
  queues: { detection_queue: number; analysis_queue: number };
  latencies: {
    detect?: { avg_ms: number | null } | null;
    analyze?: { avg_ms: number | null } | null;
  } | null;
}
interface PerformanceBody {
  inference?: { throughput?: { events_per_min?: number } | null } | null;
}
interface DlqStats {
  detection_queue_count: number;
  analysis_queue_count: number;
  total_count: number;
}

/** Mirror of AIPerformanceSummaryRow.tsx:194-199 (the card's own number→string rule). */
function formatLatency(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return '--';
  if (ms < 1) return '< 1ms';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/** Σ of hsi_pipeline_errors_total{...} lines in the /api/metrics exposition —
 * the exact family metricsParser.ts:368 feeds DashboardPage.tsx:513's sum. */
function sumPipelineErrors(exposition: string): number {
  let total = 0;
  for (const line of exposition.split('\n')) {
    if (line.startsWith('hsi_pipeline_errors_total{')) {
      const value = Number(line.slice(line.lastIndexOf(' ') + 1));
      if (Number.isFinite(value)) total += value;
    }
  }
  return total;
}

async function openDashboard(page: import('@playwright/test').Page, h: DashboardHarness) {
  await seedTourDismissed(page);
  await loginAsAdmin(page, h);
  await quietBoot(page, h);
  await expect(page.getByTestId('dashboard-layout')).toBeVisible({ timeout: 20_000 });
}

const flat = async (locator: import('@playwright/test').Locator) =>
  (await locator.innerText()).replace(/\s+/g, ' ').trim();

test.describe('golden path: dashboard AI summary row @critical', () => {
  test('F-038: the default-on row mirrors queue depth, throughput and the live error count from its endpoints', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(90_000);

    await openDashboard(page, h);
    // ON by default (DEFAULT_WIDGETS visible:true, dashboard-config-store.ts
    // :125-129) — no enable leg, unlike F-039/F-040.
    const row = page.getByTestId('ai-summary-row');
    await expect(row, 'the AI summary row is on by default').toBeVisible({ timeout: 15_000 });

    const session = await adminSession(h);
    const queues = page.getByTestId('queues-indicator');
    const throughput = page.getByTestId('throughput-indicator');
    const errors = page.getByTestId('errors-indicator');

    // --- Queues == `${telemetry.queues.detection_queue + analysis_queue} queued` ---
    await expect
      .poll(
        async () => {
          const t = await api<Telemetry>(h, session, '/api/system/telemetry');
          const want = `${(t.queues?.detection_queue ?? 0) + (t.queues?.analysis_queue ?? 0)} queued`;
          const dom = await flat(queues);
          return dom.includes(want) ? 'agree' : `dom="${dom}" want="${want}"`;
        },
        {
          message: 'queues-indicator mirrors telemetry queue depths',
          timeout: 20_000,
          intervals: [1_000],
        }
      )
      .toBe('agree');

    // --- Throughput == performance events_per_min.toFixed(1)+'/min' ---
    await expect
      .poll(
        async () => {
          const p = await api<PerformanceBody>(h, session, '/api/system/performance');
          const want = `${(p.inference?.throughput?.events_per_min ?? 0).toFixed(1)}/min`;
          const dom = await flat(throughput);
          return dom.includes(want) ? 'agree' : `dom="${dom}" want="${want}"`;
        },
        {
          message: 'throughput-indicator mirrors performance events_per_min',
          timeout: 20_000,
          intervals: [1_000],
        }
      )
      .toBe('agree');

    // --- Errors == Σ hsi_pipeline_errors_total (LIVE counter → agreement poll) ---
    await expect
      .poll(
        async () => {
          const exposition = await (
            await fetch(`${h.api}/api/metrics`, {
              headers: { Cookie: `${session.name}=${session.value}` },
            })
          ).text();
          const n = sumPipelineErrors(exposition);
          const want = n === 0 ? 'None' : `${n} total`;
          const dom = await flat(errors);
          return dom.includes(want) ? 'agree' : `dom="${dom}" want="${want}"`;
        },
        {
          message: 'errors-indicator mirrors the pipeline-errors counters',
          timeout: 25_000,
          intervals: [1_000],
        }
      )
      .toBe('agree');

    // --- Stage-latency cards mirror the hook's fallback (telemetry avg_ms) ---
    // Prometheus histograms are absent on this stack (header), so the cards
    // render formatLatency(telemetry.latencies.<stage>.avg_ms) — mirrored
    // from the SAME endpoint, so a pass proves the fallback chain end-to-end.
    const t = await api<Telemetry>(h, session, '/api/system/telemetry');
    for (const [testId, stage] of [
      ['rtdetr-indicator', t.latencies?.detect?.avg_ms],
      ['nemotron-indicator', t.latencies?.analyze?.avg_ms],
    ] as const) {
      const want = formatLatency(stage ?? null);
      const dom = await flat(page.getByTestId(testId));
      expect(dom, `${testId} renders formatLatency(${stage})`).toContain(want);
    }

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('F-038: the row renders its DLQ count — the card the clause promised (ruling 130 flip)', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(60_000);

    await openDashboard(page, h);
    const session = await adminSession(h);
    const row = page.getByTestId('ai-summary-row');
    await expect(row, 'the AI summary row is on by default').toBeVisible({ timeout: 15_000 });

    // THE FLIP. This test used to assert `dlqShown === 0` — that no element
    // anywhere on the dashboard mentioned a dead-letter queue, which was the
    // measured shipped contract and the row's half-built evidence. Now it
    // asserts the opposite: the word is on screen, on a card, carrying the
    // endpoint's own number. Same boot, same endpoint read, inverted polarity.
    const card = row.getByTestId('dlq-indicator');
    await expect(card, 'the row renders a DLQ card').toBeVisible();

    // The card mirrors GET /api/dlq/stats total_count, in the card's own
    // wording (AIPerformanceSummaryRow.tsx:500). Polled rather than compared
    // once because these are CURRENT counts — a job moving to the DLQ between
    // the API read and the DOM read would fail a one-shot equality, exactly
    // like the cumulative Errors mirror in test 1. On this stack the DLQ is
    // empty, so the steady state is 'None'; a non-empty DLQ is still asserted
    // against the endpoint rather than a literal.
    await expect
      .poll(
        async () => {
          const dlq = await api<DlqStats>(h, session, '/api/dlq/stats');
          const want = dlq.total_count === 0 ? 'None' : `${dlq.total_count} parked`;
          const dom = await flat(card);
          return dom.includes(want) ? 'agree' : `dom="${dom}" want="${want}"`;
        },
        {
          message: 'dlq-indicator mirrors /api/dlq/stats total_count',
          timeout: 25_000,
          intervals: [1_000],
        }
      )
      .toBe('agree');

    // The clause is about THIS row, so the card must be the row's own child —
    // not a widget elsewhere that happens to mention DLQs (PipelineQueues'
    // DLQRow reads a different endpoint and is off by default, so it would
    // satisfy a page-wide search while leaving this row's clause false).
    const dlqInRow = await row.getByText(/^DLQ$/).count();
    expect(dlqInRow, 'the DLQ label is inside ai-summary-row, not a page-wide match').toBe(1);

    // The row's own shape: six indicators, the sixth being this one. The
    // pre-fix row had five and the fifth (Errors) was the only error-looking
    // card, fed pipelineErrors — so counting here is what distinguishes "a
    // DLQ was folded into Errors" from "a DLQ count exists".
    const cards = await row.locator('[data-testid$="-indicator"]').count();
    expect(cards, 'the row now carries six indicators').toBe(6);

    // The pre-fix assertions still hold where they should: Errors is still the
    // cumulative pipeline count and is NOT the DLQ number wearing a hat.
    const errors = await flat(row.getByTestId('errors-indicator'));
    const dlqText = await flat(card);
    expect(errors, 'the Errors card still mirrors pipeline errors').toMatch(/None|total/);
    expect(dlqText).not.toBe(errors);

    // The rest of the row is untouched by this fix.
    const rowText = await flat(row);
    expect(rowText, 'the row still mirrors its queue-depth number').toContain('queued');

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
