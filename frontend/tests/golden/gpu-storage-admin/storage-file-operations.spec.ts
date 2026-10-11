/**
 * F-184 (inventory 3.9): the File Operations panel at /settings/storage.
 *
 * App.tsx:301 mounts <FileOperationsPanel /> bare on the storage route — the
 * SAME component OP-1's cleanup-preview.spec.ts proves through its
 * /operations host (row F-163's own note says F-184..F-186 is the same
 * chain). What is new here is the row's "auto-polls every 30 s" clause and
 * its header-banner coupling clause, and this spec proves both as behavior:
 *
 * - polling: the component setInterval's its own fetchData every 30 s
 *   (FileOperationsPanel.tsx:426, :494-500). An observer counts responses the
 *   PAGE itself fetches (page.on('response') reads traffic, never intercepts —
 *   the guard's ban is on route/routeFromHAR/routeWebSocket), then waits out
 *   one interval and requires the counter to move.
 * - banner coupling: the panel writes disk usage into useStorageStatusStore
 *   (:474) and Header renders the storage-warning chip only at >= 90%
 *   (Header.tsx:404-412, threshold constants storage-status-store.ts:57,61).
 *   The CI container filesystem measured 65.5% used at the sweep of this
 *   batch, so the honest live assertion is the BELOW-threshold pair: the
 *   panel shows the real percent and the header chip is absent. The warning
 *   arm itself is a fixture problem — read_only: true (docker-compose.ci.yml
 *   :103) makes ~30 GB of fill impossible — so the 85% disk-usage warning
 *   branch (FileOperationsPanel.tsx:691 disk-usage-warning) cannot be
 *   performed on the CI stack; that clause is cited in the row's demotion.
 *
 * Every number asserted is first read from the live API (backend leg first)
 * so the spec proves the UI MIRRORS the API rather than pinning a snapshot
 * that ages when the stack's event count moves.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { api, closedByGuard, loginAsAdmin, readOpsHarness } from '../operations/harness';

const harness = readOpsHarness();

interface Category {
  file_count: number;
  size_bytes: number;
}

interface StorageStats {
  disk_used_bytes: number;
  disk_total_bytes: number;
  disk_free_bytes: number;
  disk_usage_percent: number;
  thumbnails: Category;
  images: Category;
  clips: Category;
  events_count: number;
  detections_count: number;
  gpu_stats_count: number;
  logs_count: number;
}

interface CleanupStatus {
  running: boolean;
  retention_days: number;
  cleanup_time: string;
}

interface JobList {
  items: Array<{ job_type: string; status: string }>;
}

// formatBytes/formatNumber mirrored from FileOperationsPanel.tsx:66-76 —
// the UI renders these exact formatters, so the mirror assertion compares
// against what the component would print for the API's own numbers.
function formatBytes(bytes: number, decimals = 1): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

test.describe('golden path: storage settings file operations panel @critical', () => {
  // 90 s, not 60: the poll clause waits out the component's own 30 s interval.
  test.setTimeout(90_000);

  test('the panel mirrors the live storage/cleanup APIs, polls on its 30 s interval, and keeps the header banner in step', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    // Observer (see header): count storage fetches AND capture the bodies the
    // PAGE itself received. Every mirrored number below is asserted against
    // the page's own snapshot, not a node-side pre-read — the panel renders
    // from its fetch, and on a live stack two reads of /api/system/storage are
    // two different moments (event/log counts move between sweeps), so a
    // pre-read mirror would be a latent race.
    let storageFetches = 0;
    let storageBody: StorageStats | null = null;
    let statusBody: CleanupStatus | null = null;
    let jobsBody: JobList | null = null;
    page.on('response', (res) => {
      try {
        const path = new URL(res.url()).pathname;
        if (path === '/api/system/storage') {
          storageFetches += 1;
          void res.json().then((b) => {
            storageBody = b as StorageStats;
          });
        } else if (path === '/api/system/cleanup/status') {
          void res.json().then((b) => {
            statusBody = b as CleanupStatus;
          });
        } else if (path === '/api/jobs') {
          void res.json().then((b) => {
            jobsBody = b as JobList;
          });
        }
      } catch {
        /* non-URL-ish response — not our endpoint */
      }
    });

    // Backend leg: prove the three legs of the panel's Promise.all are live
    // for an admin session (the mirrored asserts below read the page's own
    // bodies; this proves the endpoints answer independently of the page).
    await api<StorageStats>(h, session, '/api/system/storage');
    await api<CleanupStatus>(h, session, '/api/system/cleanup/status');
    await api<JobList>(h, session, '/api/jobs');

    await page.goto(`${h.ui}/settings/storage`, { waitUntil: 'domcontentloaded' });
    // defaultExpanded defaults to true and App.tsx:301 mounts the component
    // bare, so the panel is open on arrival (no openSection click, unlike
    // OP-1's /operations host where the section is default-collapsed).
    const panel = page.getByTestId('file-operations-panel');
    await expect(panel).toBeVisible();

    // The panel's Promise.all has now answered — take the snapshots IT
    // rendered from. (Disk usage renders only after /api/system/storage
    // returns, so these polls land immediately; the 30 s interval next ticks
    // ~26 s from here, well after this mirror block finishes, so the frozen
    // snapshot cannot be overtaken mid-assertion.)
    await expect.poll(() => storageBody).not.toBeNull();
    await expect.poll(() => statusBody).not.toBeNull();
    await expect.poll(() => jobsBody).not.toBeNull();
    const storage = storageBody as StorageStats;
    const status = statusBody as CleanupStatus;
    const exportJobs = (jobsBody as JobList).items.filter((j) => j.job_type === 'export');

    // Disk usage block renders only once /api/system/storage answered.
    const usage = panel.getByTestId('storage-usage-section');
    await expect(usage).toBeVisible();
    await expect(usage).toContainText(
      `${formatBytes(storage.disk_used_bytes)} / ${formatBytes(storage.disk_total_bytes)}`
    );
    await expect(usage).toContainText(`${storage.disk_usage_percent.toFixed(1)}%`);

    // Breakdown categories (measured on the sweep stack: thumbnails 0 files,
    // images 1, clips 0 — the loop asserts each against its own API numbers).
    for (const [key, testId] of [
      ['thumbnails', 'storage-category-thumbnails'],
      ['images', 'storage-category-images'],
      ['clips', 'storage-category-clips'],
    ] as const) {
      const cat = storage[key];
      const el = panel.getByTestId(testId);
      await expect(el).toBeVisible();
      await expect(el).toContainText(`${cat.file_count.toLocaleString()} files`);
      await expect(el).toContainText(formatBytes(cat.size_bytes));
    }

    // Record counts and the cleanup-service summary come from the other two
    // legs of the same Promise.all (:455-463).
    //
    // Label and value are adjacent sibling nodes, so the DOM text is tight —
    // "Events:3", "Status:Running" — and toContainText normalizes whitespace
    // runs but never inserts one. \s* keeps this a true UI-mirrors-API check
    // (the number still has to be the API's own) while matching today's render
    // and surviving a cosmetic fix that adds the space.
    await expect(panel).toContainText(
      new RegExp(`Events:\\s*${storage.events_count.toLocaleString()}`)
    );
    await expect(panel).toContainText(
      new RegExp(`Detections:\\s*${storage.detections_count.toLocaleString()}`)
    );
    const summary = panel.getByTestId('cleanup-summary');
    await expect(summary).toContainText(
      new RegExp(`Status:\\s*${status.running ? 'Running' : 'Stopped'}`)
    );
    await expect(summary).toContainText(new RegExp(`Retention:\\s*${status.retention_days} days`));

    // Export Jobs section: the component filters jobs to job_type 'export'
    // (:553), and with none present renders the empty state.
    await expect(panel.getByTestId('active-exports-section')).toBeVisible();
    if (exportJobs.length === 0) {
      await expect(panel.getByTestId('no-exports-message')).toBeVisible();
    }

    // The 85% warning arms only at the threshold, so branch on the API's own
    // percent rather than assuming the stack stays cool (header note).
    if (storage.disk_usage_percent >= 85) {
      await expect(panel.getByTestId('disk-usage-warning')).toBeVisible();
    } else {
      await expect(panel.getByTestId('disk-usage-warning')).toHaveCount(0);
    }

    // Banner coupling clause: Header hides storage-warning below 90%.
    const critical = storage.disk_usage_percent >= 90;
    if (critical) {
      await expect(page.getByTestId('storage-warning')).toBeVisible();
    } else {
      await expect(page.getByTestId('storage-warning')).toHaveCount(0);
    }

    // "clicks Refresh": the button calls fetchData directly (:835); the
    // observer proves the CLICK produced a browser fetch, not just a DOM
    // shuffle. The response may arrive after the click returns, so poll.
    const atRefresh = storageFetches;
    await panel.getByTestId('refresh-button').click();
    await expect
      .poll(() => storageFetches, { timeout: 10_000, intervals: [500] })
      .toBeGreaterThan(atRefresh);

    // "auto-polls every 30 s": same counter, no click — a page that fetched
    // only on mount and on click would leave the counter frozen here.
    const atPoll = storageFetches;
    await expect
      .poll(() => storageFetches, { timeout: 40_000, intervals: [2_000] })
      .toBeGreaterThan(atPoll);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
