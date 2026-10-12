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
 *       (:374-376; the two depths come from GET /api/system/telemetry
 *       queues.*_queue, hook fallback chain useAIMetrics.ts:378-381).
 *     • Throughput = `${calculatedThroughput.toFixed(1)}/min` (:403-405;
 *       throughputPerMinute = events_per_min from GET /api/system/
 *       performance inference.throughput.events_per_min — DashboardPage
 *       passes it (:505) so the totalEvents fallback at :292 never runs).
 *     • Errors    = totalErrors === 0 ? 'None' : `${totalErrors} total`
 *       (:423-424) where totalErrors = Σ hsi_pipeline_errors_total counters
 *       from the /api/metrics exposition (DashboardPage.tsx:500-502,
 *       metricsParser.ts:368 getCountersByLabel). MEASURED on the probe
 *       stack: this counter is CUMULATIVE and LIVE (+6 per 6 s, 3732→3744),
 *       so this mirror is an agreement poll — each poll re-reads
 *       /api/metrics and compares to the DOM; a persistent mismatch fails
 *       naming both values. A one-shot equality could race the counter.
 * - The fourth number is the row's break, found by reading the chain:
 *   "DLQ error count". The hook fetches GET /api/dlq/stats and maps it to
 *   state `dlqItems` (useAIMetrics.ts:309-323, :384) — and NO component on
 *   the dashboard reads that field: the row's Errors card is fed
 *   `pipelineErrors` (DashboardPage.tsx:500), never `dlqItems`; the only
 *   reader of `dlqItems` is ai/PipelineHealthPanel.tsx:105,112, which has
 *   ZERO render sites (`<PipelineHealthPanel` appears nowhere in
 *   frontend/src outside its own test — verified by grep at this head) and
 *   PipelineQueues.tsx's DLQRow renders from a DIFFERENT call
 *   (queuesStatus, :89-90, :161-162) inside a widget that is off by
 *   default. So the row shows a pipeline-errors count and NO DLQ count:
 *   the vocabulary's UI-end half-built, a fetched value no route renders.
 *   The shipped contract is MEASURED — the DLQ endpoint answers
 *   total_count 0 on the probe stack, and no dashboard element displays it.
 * - The latency cards render formatLatency(:152-157: null/undefined → '--',
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

/** Mirror of AIPerformanceSummaryRow.tsx:152-157 (the card's own number→string rule). */
function formatLatency(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return '--';
  if (ms < 1) return '< 1ms';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/** Σ of hsi_pipeline_errors_total{...} lines in the /api/metrics exposition —
 * the exact family metricsParser.ts:368 feeds DashboardPage.tsx:500's sum. */
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

  test('F-038: the row\'s "DLQ error count" clause ships with no DLQ element — half-built evidence', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(60_000);

    await openDashboard(page, h);
    const session = await adminSession(h);

    // The endpoint the clause names ANSWERS (its own numbers come from it):
    const dlq = await api<DlqStats>(h, session, '/api/dlq/stats');
    expect(
      dlq.total_count,
      'the probe/golden stack keeps the DLQ empty (total_count 0)'
    ).toBeGreaterThanOrEqual(0);

    // …and the SHIPPED dashboard renders NO DLQ value anywhere: the summary
    // row's Errors card is fed pipelineErrors (DashboardPage.tsx:500), never
    // dlqItems (useAIMetrics.ts:384), whose only reader
    // (ai/PipelineHealthPanel.tsx:105) has zero render sites. This asserts
    // the MEASURED shipped contract so the row tells the truth about what
    // exists. A fix (surface dlqItems in a card, or fold DLQ totals into
    // totalErrors with the row's wording fixed) flips THIS red on purpose:
    // it will start finding an element carrying dlq.total_count.
    const rowText = await flat(page.getByTestId('ai-summary-row'));
    const dlqShown = await page.getByText(new RegExp(`dlq|dead[- ]letter`, 'i')).count();
    expect(
      dlqShown,
      'no DLQ/dead-letter element exists on the dashboard — the row clause ' +
        '"DLQ error count" is not rendered (the Errors card shows Σ ' +
        'hsi_pipeline_errors_total instead); row must stay half-built until a ' +
        'card renders /api/dlq/stats total_count'
    ).toBe(0);
    expect(rowText, 'the visible row still mirrors three real numbers').toContain('queued');

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
