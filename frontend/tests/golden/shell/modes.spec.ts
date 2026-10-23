/**
 * F4.9 Golden Path — Easy and Advanced view modes (`F-299`, `docs/uplevel/4n-modes.md`).
 *
 * Verifies the 6 steps from `docs/uplevel/4n-modes.md` §Golden path:
 * 1. A fresh browser shows the five Easy items and no GPU pill.
 * 2. An event's modal shows Details and Video Clip, the verdict badge and the
 *    detected objects, and no AI Analysis tab.
 * 3. `/operations` opens with the Advanced banner and the Operations & Monitoring
 *    tab bar (with no sidebar item highlighted).
 * 4. Switching to Advanced shows nine items, the GPU pill and the AI Analysis tab.
 * 5. A reload keeps Advanced.
 * 6. Switching back returns the five items.
 */

import type { Page } from '@playwright/test';

import { GUARD_MESSAGE, expect, test } from '../guard';
import {
  adminSession,
  apiShell as api,
  apiWrite,
  BOOT_QUIET_MS,
  closedByGuard,
  hardDeleteFixtureRows,
  openShell,
  quietBootShell as quietBoot,
  readShellHarness,
  readTimelineHarness,
  seedDefaultViewMode,
  type Session,
  type ShellHarness,
  type TimelineHarness,
} from '../harness';

const shellState = readShellHarness();
const timelineState = readTimelineHarness();
test.skip(
  !shellState.ready || !timelineState.ready,
  `golden path needs the feature-check stack (${
    !shellState.ready ? shellState.why : !timelineState.ready ? timelineState.why : ''
  })`
);

const h = shellState as ShellHarness;
const timelineH = timelineState as TimelineHarness;

const EASY_HUB_IDS = [
  'dashboard',
  'timeline-search',
  'alerts-rules',
  'household',
  'settings',
] as const;

const ADVANCED_HUB_IDS = [
  'ai-workbench',
  'gpu-models',
  'entities-reid',
  'operations-monitoring',
] as const;

const ALL_HUB_IDS = [...EASY_HUB_IDS, ...ADVANCED_HUB_IDS] as const;

const MODES_CAMERA_NAME = 'F4.9 Modes Golden Probe';

let cameraId = '';
let seededEventId = 0;

interface CameraListBody {
  items?: { id: string; name: string }[];
}

interface BulkResultBody {
  succeeded: number;
  results: { id: number | null; status: string; error?: string | null }[];
}

async function ensureModesFixture(
  session: Session
): Promise<{ cameraId: string; eventId: number }> {
  const cams = await api<CameraListBody | { id: string; name: string }[]>(
    timelineH,
    session,
    '/api/cameras'
  );
  const camList = Array.isArray(cams) ? cams : (cams.items ?? []);
  let found = camList.find((c) => c.name === MODES_CAMERA_NAME);
  if (!found) {
    found = await apiWrite<{ id: string; name: string }>(
      timelineH,
      session,
      'POST',
      '/api/cameras',
      {
        name: MODES_CAMERA_NAME,
        folder_path: `/cameras/f49_modes_probe_${Date.now()}`,
        status: 'online',
      }
    );
  }

  const salt = Date.now();
  const nowIso = new Date().toISOString();
  const detBulk = await apiWrite<BulkResultBody>(
    timelineH,
    session,
    'POST',
    '/api/detections/bulk',
    {
      detections: [
        {
          camera_id: found.id,
          object_type: 'person',
          confidence: 0.93,
          detected_at: nowIso,
          file_path: `/cameras/f49_modes_probe_${salt}.jpg`,
          bbox_x: 20,
          bbox_y: 20,
          bbox_width: 100,
          bbox_height: 180,
          media_type: 'image',
        },
      ],
    }
  );
  const detId = detBulk.results[0]?.id;
  if (!detId) {
    throw new Error(`f4.9 fixture: detection bulk create failed: ${JSON.stringify(detBulk)}`);
  }

  const evBulk = await apiWrite<BulkResultBody>(timelineH, session, 'POST', '/api/events/bulk', {
    events: [
      {
        batch_id: `f49-modes-${salt}`,
        camera_id: found.id,
        started_at: nowIso,
        risk_score: 68,
        risk_level: 'high',
        summary: 'F4.9 modes golden fixture event',
        reasoning: 'Test reasoning for F4.9 modes golden path',
        detection_ids: [detId],
      },
    ],
  });
  const evId = evBulk.results[0]?.id;
  if (!evId) {
    throw new Error(`f4.9 fixture: event bulk create failed: ${JSON.stringify(evBulk)}`);
  }

  return { cameraId: found.id, eventId: evId };
}

async function assertEasySidebarHubs(page: Page): Promise<void> {
  const sidebar = page.getByTestId('sidebar');
  await expect(sidebar.locator('[data-testid^="sidebar-hub-"]')).toHaveCount(5);
  for (const id of EASY_HUB_IDS) {
    await expect(page.getByTestId(`sidebar-hub-${id}`)).toBeVisible();
  }
  for (const id of ADVANCED_HUB_IDS) {
    await expect(page.getByTestId(`sidebar-hub-${id}`)).toHaveCount(0);
  }
}

async function assertAllNineSidebarHubs(page: Page): Promise<void> {
  const sidebar = page.getByTestId('sidebar');
  await expect(sidebar.locator('[data-testid^="sidebar-hub-"]')).toHaveCount(9);
  for (const id of ALL_HUB_IDS) {
    await expect(page.getByTestId(`sidebar-hub-${id}`)).toBeVisible();
  }
}

test.describe('F4.9 Easy and Advanced view modes golden path (F-299) @critical', () => {
  test.beforeAll(async () => {
    test.setTimeout(120_000);
    const session = await adminSession(timelineH);
    const created = await ensureModesFixture(session);
    cameraId = created.cameraId;
    seededEventId = created.eventId;
  });

  test.afterAll(async () => {
    if (!seededEventId) return;
    const session = await adminSession(timelineH);
    await hardDeleteFixtureRows(timelineH, session, [seededEventId]);
  });

  test('F-299: fresh browser starts in Easy, /operations shows Advanced banner, switching to Advanced reveals 9 hubs + GPU pill + AI Analysis tab, persists across reload, and switches back', async ({
    page,
  }) => {
    test.setTimeout(180_000);
    await page.setViewportSize({ width: 1440, height: 900 });
    await seedDefaultViewMode(page);
    await openShell(page, h);

    // 1. A fresh browser shows the five Easy items and no GPU pill.
    await assertEasySidebarHubs(page);
    await expect(page.getByText('GPU:', { exact: true })).toHaveCount(0);
    const headerSwitch = page.getByTestId('header-mode-switch-container');
    await expect(headerSwitch.getByTestId('mode-switch-easy')).toHaveAttribute(
      'aria-pressed',
      'true'
    );
    await expect(headerSwitch.getByTestId('mode-switch-advanced')).toHaveAttribute(
      'aria-pressed',
      'false'
    );

    // 2. An event's modal shows Details and Video Clip, the verdict badge and the
    //    detected objects, and no AI Analysis tab.
    await quietBoot(
      page,
      h,
      `/timeline?camera=${encodeURIComponent(cameraId)}&event=${seededEventId}`
    );
    const modal = page.getByTestId('event-detail-modal');
    await expect(modal).toBeVisible();
    await expect(modal.getByRole('button', { name: 'Details' })).toBeVisible();
    await expect(modal.getByTestId('video-clip-tab')).toBeVisible();
    await expect(modal.getByTestId('ai-analysis-tab')).toHaveCount(0);
    await expect(modal.getByRole('status', { name: /^Verification verdict:/ })).toBeVisible();
    await expect(modal.getByTestId('detection-objects')).toBeVisible();
    await modal.getByTestId('close-modal-button').click();
    await expect(modal).toHaveCount(0);

    // 3. `/operations` opens with the Advanced banner and the Operations & Monitoring
    //    tab bar, with no sidebar item highlighted.
    await quietBoot(page, h, '/operations');
    const banner = page.getByTestId('advanced-page-banner');
    await expect(banner).toBeVisible();
    await expect(banner).toContainText('This is an Advanced page');
    await expect(page.getByTestId('banner-switch-to-advanced')).toBeVisible();
    await expect(page.getByTestId('banner-back-to-home')).toBeVisible();
    await expect(
      page.getByRole('tablist', { name: 'Operations & Monitoring sections' })
    ).toBeVisible();
    for (const id of EASY_HUB_IDS) {
      await expect(page.getByTestId(`sidebar-hub-${id}`)).not.toHaveAttribute(
        'aria-current',
        'page'
      );
    }

    // 4. Switching to Advanced shows nine items, the GPU pill and the AI Analysis tab.
    await headerSwitch.getByTestId('mode-switch-advanced').click();
    await expect(banner).toHaveCount(0);
    await assertAllNineSidebarHubs(page);
    await expect(page.getByText('GPU:', { exact: true })).toBeVisible();

    await quietBoot(
      page,
      h,
      `/timeline?camera=${encodeURIComponent(cameraId)}&event=${seededEventId}`
    );
    await expect(modal).toBeVisible();
    await expect(modal.getByTestId('ai-analysis-tab')).toBeVisible();
    await modal.getByTestId('close-modal-button').click();
    await expect(modal).toHaveCount(0);
    await page.evaluate(() => window.history.replaceState(null, '', '/timeline'));

    // 5. A reload keeps Advanced.
    await page.waitForTimeout(BOOT_QUIET_MS);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('header-branding')).toBeVisible({ timeout: 20_000 });
    await assertAllNineSidebarHubs(page);
    await expect(page.getByText('GPU:', { exact: true })).toBeVisible();

    // 6. Switching back returns the five items.
    await headerSwitch.getByTestId('mode-switch-easy').click();
    await assertEasySidebarHubs(page);
    await expect(page.getByText('GPU:', { exact: true })).toHaveCount(0);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
