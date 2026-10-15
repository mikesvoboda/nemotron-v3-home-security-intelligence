/**
 * [r134] guard: the batch-history views are retired (ruling 134).
 *
 * Three legs.
 *
 *  A. DELETE — the closure-reason chart and the per-camera table are gone by
 *     exact path, their barrel exports are gone, and the dashboard paints
 *     neither surface even with `hasData` ARMED. The arming is the point: the
 *     dashboard renders both views only inside `{hasData && …}`
 *     (`BatchStatisticsDashboard.tsx:232` at this head; the pre-deletion tree
 *     had it at `:235`), and `hasData` was
 *     `activeBatchCount > 0 || totalClosedCount > 0 || perCameraStats non-empty`
 *     (base `:74-75`, narrowed to two terms at head `:72` when the map
 *     retired), so a guard that left the hook mocked at zero data would assert
 *     an absence that was never reachable — the vacuity trap the rate-limit
 *     spec's `retiredSurface` comment names. Here the mocked hook supplies two
 *     active and two closed batches plus non-empty `perCameraStats`, so
 *     pre-deletion both doomed surfaces paint and this file is RED; after the
 *     deletion it is green, and stays green forever (a reintroduced surface
 *     trips it).
 *  B. DELETE (measured scope) — the ruling names a third view, the
 *     "completed-batch timeline". Measured at the base commit, NOTHING renders
 *     completed batches as a timeline: `BatchTimelineChart.tsx` takes
 *     `activeBatches: BatchInfoResponse[]` and nothing else (`:25`) and its
 *     heading is the literal "Active Batches" (`:63`), and the base hook read
 *     `completedBatches` into exactly four derived values
 *     (base `useBatchStatistics.ts:145`, the `useDetectionStream` destructure):
 *     `closureReasonStats` (base `:193`), `closureReasonPercentages` (base
 *     `:213`), `perCameraStats` (base `:233`) — the three aggregates the leg A
 *     surfaces rendered — and `averageDurationSeconds` (base `:268-280`), which
 *     survives as a stat card (head `:150-162`). `totalClosedCount` is NOT one
 *     of them: base `:288` returns it as `batchCount`, the count the stream
 *     already carried, which is why it lives on. So leg B pins what that claim
 *     actually covers: the three aggregates are gone from the hook and from the
 *     dashboard's destructure (base `:66-68`, absent at head, where the name
 *     `perCameraStats` survives only in the `:69` comment), and no heading or
 *     testid the retired views used paints with the hook armed. The measured
 *     `grep -c completedBatches BatchStatisticsDashboard.tsx` is 0 at BOTH
 *     revisions — the dashboard never named it, only its derived aggregates —
 *     so that count is stated as a baseline, not as the removal. A separate unmounted component
 *     (`components/BatchProcessingIndicator.tsx:209`) consumes its OWN
 *     `completedBatches` from `useBatchProcessingStatus` with no importer
 *     anywhere in `src` — a dead component, not this ruling's three views, and
 *     deliberately not touched here.
 *  C. KEEP — the active-batches view survives: `BatchTimelineChart.tsx`
 *     exists, the barrel still exports it, and the same armed render above
 *     paints `batch-timeline-chart`. That render is what makes leg C's
 *     existence claim structural rather than a filesystem wish: the kept view
 *     is proven to render from the same dashboard that lost the other two.
 *
 * Why exact paths rather than the `no-browser-api-key.test.ts` filesystem
 * walk: a walk of `frontend/` selects whatever is on disk, including gitignored
 * local scratch that carries these identifiers; an exact path is the same fact
 * on every machine.
 *
 * Why no mutation kill-loss ledger (`01-mutation-policy.md` §The scored set):
 * this PR changes production bytes, so its mutant set changes with the code,
 * and UR-16 settles the battery's future: deleted with its module in Phase 3.
 */
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import BatchStatisticsDashboard from '../components/batch/BatchStatisticsDashboard';
import { useBatchStatistics } from '../hooks/useBatchStatistics';

vi.mock('../hooks/useBatchStatistics', () => ({
  useBatchStatistics: vi.fn(),
}));

const mockUseBatchStatistics = vi.mocked(useBatchStatistics);

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.resolve(__dirname, '..'); // frontend/src/

/** Arm `hasData`: two active batches, two closed, per-camera stats non-empty.
 *  The `closureReasonStats`/`perCameraStats` fields below are the doomed
 *  views' inputs. They stay in this literal deliberately: the object is a
 *  module-level const (not a fresh literal at the call site), so TypeScript
 *  does not reject the extra properties after the return type narrows, and
 *  pre-deletion the armed values are what make the doomed surfaces paint. */
const armedStatistics = {
  isLoading: false,
  error: null,
  activeBatchCount: 2,
  activeBatches: [
    {
      batch_id: 'batch-1',
      camera_id: 'front_door',
      detection_count: 5,
      started_at: 1737806400,
      age_seconds: 45.5,
      last_activity_seconds: 10.2,
    },
    {
      batch_id: 'batch-2',
      camera_id: 'backyard',
      detection_count: 3,
      started_at: 1737806380,
      age_seconds: 65.5,
      last_activity_seconds: 5.1,
    },
  ],
  totalClosedCount: 2,
  batchWindowSeconds: 90,
  idleTimeoutSeconds: 30,
  averageDurationSeconds: 60,
  closureReasonStats: { timeout: 1, idle: 1, max_size: 0 },
  closureReasonPercentages: { timeout: 50, idle: 50, max_size: 0 },
  perCameraStats: {
    front_door: {
      completedBatchCount: 1,
      activeBatchCount: 1,
      totalDetections: 10,
    },
  },
  isWebSocketConnected: true,
  refetch: vi.fn(),
};

describe('[r134] the batch-history views are retired (ruling 134)', () => {
  it('leg A: the two history-view files and their barrel exports are gone', () => {
    // Anti-vacuity: the exact-path reads below run against a real tree.
    expect(
      fs.existsSync(path.join(SRC, 'components', 'batch', 'BatchStatisticsDashboard.tsx'))
    ).toBe(true);
    const dir = path.join(SRC, 'components', 'batch');
    expect(fs.existsSync(path.join(dir, 'BatchClosureReasonChart.tsx'))).toBe(false);
    expect(fs.existsSync(path.join(dir, 'BatchPerCameraTable.tsx'))).toBe(false);
    const barrel = fs.readFileSync(path.join(dir, 'index.ts'), 'utf8');
    expect(barrel).not.toContain('BatchClosureReasonChart');
    expect(barrel).not.toContain('BatchPerCameraTable');
    // SAFE by this file's purpose: every path is path.join of a directory
    // baked in at authoring; no input ever enters them.
    const hook = fs.readFileSync(path.join(SRC, 'hooks', 'useBatchStatistics.ts'), 'utf8');
    expect(hook).not.toMatch(/closureReasonStats|closureReasonPercentages|perCameraStats/);
  });

  it('legs A+B: neither doomed surface paints with hasData armed', () => {
    mockUseBatchStatistics.mockReturnValue(armedStatistics as never);
    render(<BatchStatisticsDashboard />);

    // Anti-vacuity for the absences: the armed render really mounted, and it
    // mounted the section that hosts both the doomed views and the kept one.
    expect(screen.getByTestId('batch-statistics-dashboard')).toBeInTheDocument();
    expect(screen.getByTestId('active-batch-count')).toHaveTextContent('2');

    // Leg A: the two retired surfaces, by the exact testids they rendered
    // (`BatchClosureReasonChart.tsx:79,92` and `BatchPerCameraTable.tsx:48,61`
    // at the base commit).
    expect(screen.queryByTestId('closure-reason-chart')).toBeNull();
    expect(screen.queryByTestId('per-camera-table')).toBeNull();

    // Leg B: no completed-batch timeline anywhere in the section. The heading
    // strings are the doomed components' own copy at the base commit
    // ("Closure Reasons", "Per-Camera Breakdown").
    expect(screen.queryByText('Closure Reasons')).toBeNull();
    expect(screen.queryByText('Per-Camera Breakdown')).toBeNull();
  });

  it('leg C: the active-batches view survives the deletion and renders', () => {
    expect(fs.existsSync(path.join(SRC, 'components', 'batch', 'BatchTimelineChart.tsx'))).toBe(
      true
    );
    expect(fs.readFileSync(path.join(SRC, 'components', 'batch', 'index.ts'), 'utf8')).toContain(
      'BatchTimelineChart'
    );

    mockUseBatchStatistics.mockReturnValue(armedStatistics as never);
    render(<BatchStatisticsDashboard />);
    const kept = screen.getByTestId('batch-timeline-chart');
    expect(kept).toBeInTheDocument();
    // The heading that settles the naming collision: this component's data is
    // `activeBatches` alone, so the ruling's kept "active-batches view" is
    // exactly this file.
    expect(kept).toHaveTextContent('Active Batches');
    expect(kept).toHaveTextContent('batch-1');
  });
});
