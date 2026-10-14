/**
 * F-154, F-155, F-156 (inventory 3.8): Operations › Developer tools ›
 * Recording & Replay panel on `/operations`:
 *   - F-154: expands Recording & Replay; sees recorded requests; clicks one to
 *            open the detail modal (`GET /api/debug/recordings`,
 *            `GET /api/debug/recordings/{recording_id}`)
 *   - F-155: clicks Replay on a recording; sees the replay-results modal
 *            comparing the original and new response
 *            (`POST /api/debug/replay/{recording_id}`)
 *   - F-156: clicks Delete on one recording; the list refreshes
 *            (`DELETE /api/debug/recordings/{recording_id}`)
 *
 * On the unseeded CI stack (`request_recording_enabled=False` by default,
 * `backend/core/config.py:2951`, and `read_only: true` on `backend`), the store
 * at `data/recordings` holds zero files (`{"recordings":[],"total":0}`). This
 * spec verifies the live panel mount, the backend list read, the Refresh
 * re-fetch, and the empty-state guards when `total === 0`; when recordings are
 * present (`total > 0`, under the ruling-127 recorder seed), it drives View
 * (F-154), Replay (F-155) and Delete (F-156) end to end.
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

test.describe('golden path: recording and replay panel (F-154, F-155, F-156) @critical', () => {
  test.setTimeout(90_000);

  test('expands Recording & Replay, mirrors GET /api/debug/recordings, and drives Refresh or row actions', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    // ── NODE LEG ────────────────────────────────────────────────────────────
    const listed = await api<RecordingsListBody>(h, session, '/api/debug/recordings');
    expect(Array.isArray(listed.recordings)).toBe(true);
    expect(listed.total).toBe(listed.recordings.length);

    let recordingsFetches = 0;
    page.on('response', (res) => {
      try {
        if (new URL(res.url()).pathname === '/api/debug/recordings') recordingsFetches += 1;
      } catch {
        /* ignore non-URL responses */
      }
    });

    // ── BROWSER LEG ─────────────────────────────────────────────────────────
    await page.goto(`${h.ui}/operations`, { waitUntil: 'domcontentloaded' });
    await openSection(page, 'recording-replay');

    const panel = page.getByTestId('recording-replay-panel');
    await expect(panel).toBeVisible();
    await expect(panel.getByRole('heading', { name: 'Request Recordings' })).toBeVisible();

    await expect
      .poll(() => recordingsFetches, { timeout: 15_000, intervals: [300] })
      .toBeGreaterThanOrEqual(1);

    if (listed.recordings.length === 0) {
      // Unseeded stack (`request_recording_enabled=False`): empty state renders,
      // Clear All is disabled, and no per-row View/Replay/Delete buttons mount.
      await expect(panel.getByText('No recordings yet')).toBeVisible();
      await expect(panel.getByRole('button', { name: 'Clear all recordings' })).toBeDisabled();
      await expect(panel.locator('button[aria-label^="View recording "]')).toHaveCount(0);
      await expect(panel.locator('button[aria-label^="Replay recording "]')).toHaveCount(0);
      await expect(panel.locator('button[aria-label^="Delete recording "]')).toHaveCount(0);

      const beforeRefresh = recordingsFetches;
      await panel.getByRole('button', { name: 'Refresh' }).click();
      await expect
        .poll(() => recordingsFetches, { timeout: 15_000, intervals: [300] })
        .toBeGreaterThan(beforeRefresh);
    } else {
      const first = listed.recordings[0];

      // F-154: click View to open the detail modal.
      await panel.getByRole('button', { name: `View recording ${first.recording_id}` }).click();
      await expect(page.getByRole('heading', { name: 'Recording Details' })).toBeVisible();
      await expect(page.getByText(first.recording_id)).toBeVisible();
      await page.getByRole('button', { name: 'Close' }).first().click();

      // F-155: click Replay to open the replay-results modal.
      await panel.getByRole('button', { name: `Replay recording ${first.recording_id}` }).click();
      await expect(page.getByRole('heading', { name: 'Replay Results' })).toBeVisible({
        timeout: 15_000,
      });
      await expect(page.getByTestId('status-comparison')).toBeVisible();
      await page.getByRole('button', { name: 'Close' }).first().click();

      // F-156: click Delete on the recording and confirm.
      page.once('dialog', (dialog) => {
        void dialog.accept();
      });
      const beforeDelete = recordingsFetches;
      await panel.getByRole('button', { name: `Delete recording ${first.recording_id}` }).click();
      await expect
        .poll(() => recordingsFetches, { timeout: 15_000, intervals: [300] })
        .toBeGreaterThan(beforeDelete);
    }

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
