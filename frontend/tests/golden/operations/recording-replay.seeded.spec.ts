/**
 * F-154, F-155, F-156 (inventory 3.8, seeded golden project — rulings 127, 187):
 * Operations › Developer tools › Recording & Replay on `/operations` when
 * `REQUEST_RECORDING_ENABLED=true` and `Run.seed_debug_fixtures()` has recorded
 * live requests into `/app/data/recordings`.
 *
 *   - F-154: expands Recording & Replay; sees recorded requests; clicks one to
 *            open the detail modal (`GET /api/debug/recordings`,
 *            `GET /api/debug/recordings/{recording_id}`)
 *   - F-155: clicks Replay on a recording; sees the replay-results modal
 *            comparing the original and new response
 *            (`POST /api/debug/replay/{recording_id}`)
 *   - F-156: clicks Delete on one recording; the list refreshes
 *            (`DELETE /api/debug/recordings/{recording_id}`)
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { api, closedByGuard, loginAsAdmin, openSection, readOpsHarness } from './harness';

const harness = readOpsHarness();

interface RecordingEntry {
  recording_id: string;
  timestamp: string;
  method: string;
  path: string;
  status_code: number;
  duration_ms: number;
  body_truncated: boolean;
}

interface RecordingsListBody {
  recordings: RecordingEntry[];
  total: number;
  timestamp: string;
}

test.describe('seeded golden path: recording and replay (F-154, F-155, F-156) @critical', () => {
  test.setTimeout(90_000);

  test('views recording detail modal (F-154), replays a recording (F-155), and deletes a recording (F-156)', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    test.info().annotations.push({
      type: 'seeded-branch',
      description: 'F-154/F-155/F-156 view, replay, and delete against live recorded requests',
    });

    const listed = await api<RecordingsListBody>(h, session, '/api/debug/recordings');
    expect(listed.recordings.length).toBeGreaterThanOrEqual(2);
    expect(listed.total).toBe(listed.recordings.length);
    const first = listed.recordings[0];

    let recordingsFetches = 0;
    let detailFetches = 0;
    let replayPosts = 0;
    let deleteCalls = 0;
    page.on('response', (res) => {
      try {
        const pathname = new URL(res.url()).pathname;
        if (pathname === '/api/debug/recordings') recordingsFetches += 1;
        if (pathname === `/api/debug/recordings/${first.recording_id}`) {
          if (res.request().method() === 'GET') detailFetches += 1;
          if (res.request().method() === 'DELETE') deleteCalls += 1;
        }
        if (pathname === `/api/debug/replay/${first.recording_id}`) replayPosts += 1;
      } catch {
        /* ignore non-URL responses */
      }
    });

    await page.goto(`${h.ui}/operations`, { waitUntil: 'domcontentloaded' });
    await openSection(page, 'recording-replay');

    const panel = page.getByTestId('recording-replay-panel');
    await expect(panel).toBeVisible();
    await expect(panel.getByRole('heading', { name: 'Request Recordings' })).toBeVisible();
    await expect(panel.getByText('No recordings yet')).toHaveCount(0);

    // ── F-154: View recording detail modal ──────────────────────────────────
    const viewBtn = panel.getByRole('button', { name: `View recording ${first.recording_id}` });
    await expect(viewBtn).toBeVisible();
    await viewBtn.click();

    await expect.poll(() => detailFetches, { timeout: 15_000, intervals: [300] }).toBe(1);
    await expect(page.getByRole('heading', { name: 'Recording Details' })).toBeVisible();
    await expect(page.getByText(first.recording_id).first()).toBeVisible();
    await expect(page.getByText(first.path).first()).toBeVisible();
    await page.getByRole('button', { name: 'Close' }).first().click();
    await expect(page.getByRole('heading', { name: 'Recording Details' })).toHaveCount(0);

    // ── F-155: Replay a recording ───────────────────────────────────────────
    const replayBtn = panel.getByRole('button', { name: `Replay recording ${first.recording_id}` });
    await expect(replayBtn).toBeVisible();
    await replayBtn.click();

    await expect.poll(() => replayPosts, { timeout: 15_000, intervals: [300] }).toBe(1);
    await expect(page.getByRole('heading', { name: 'Replay Results' })).toBeVisible({
      timeout: 15_000,
    });
    const comparison = page.getByTestId('status-comparison');
    await expect(comparison).toBeVisible();
    await expect(comparison).toContainText(/Status codes (match|differ)/);
    await expect(comparison).toContainText('Original:');
    await expect(comparison).toContainText('Replay:');
    await expect(comparison).toContainText(String(first.status_code));
    await page.getByRole('button', { name: 'Close' }).first().click();
    await expect(page.getByRole('heading', { name: 'Replay Results' })).toHaveCount(0);

    // ── F-156: Delete a recording ───────────────────────────────────────────
    page.once('dialog', (dialog) => {
      void dialog.accept();
    });
    const fetchesBeforeDelete = recordingsFetches;
    const deleteBtn = panel.getByRole('button', { name: `Delete recording ${first.recording_id}` });
    await expect(deleteBtn).toBeVisible();
    await deleteBtn.click();

    await expect.poll(() => deleteCalls, { timeout: 15_000, intervals: [300] }).toBe(1);
    await expect
      .poll(() => recordingsFetches, { timeout: 15_000, intervals: [300] })
      .toBeGreaterThan(fetchesBeforeDelete);
    await expect(
      panel.getByRole('button', { name: `View recording ${first.recording_id}` })
    ).toHaveCount(0);

    const after = await api<RecordingsListBody>(h, session, '/api/debug/recordings');
    expect(after.recordings.some((r) => r.recording_id === first.recording_id)).toBe(false);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
