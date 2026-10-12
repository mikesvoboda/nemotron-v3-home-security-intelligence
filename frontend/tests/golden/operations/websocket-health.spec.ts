/**
 * F-146 (inventory 3.8): WebSocket health — the event and system broadcaster
 * cards render with circuit state.
 *
 * GET /api/system/health/websocket first (both broadcasters reported Healthy
 * on the harness stack's DOM probe); the section then carries a card and a
 * status badge per broadcaster.
 *
 * The badge LABELS are mirrored from the fetched body, not just their
 * presence: WebSocketHealthPanel renders getStateLabel(status?.state ??
 * 'unavailable') — closed → Healthy, open → Open (Failing), half_open →
 * Testing, unavailable → Unknown. So the expected label is computed with the
 * component's own mapping from the body this spec already fetches; a body
 * like {"garbage": 1} (which a key-count read accepts) renders Unavailable
 * and fails the mirror instead of sailing through.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { api, closedByGuard, loginAsAdmin, openSection, readOpsHarness } from './harness';

const harness = readOpsHarness();

// Local shape of GET /api/system/health/websocket — mirrors
// services/api.ts WebSocketHealthResponse (golden specs don't import src types).
type BroadcasterState = { state?: string } | null | undefined;

// The component's label mapping, verbatim (WebSocketHealthPanel getStateLabel).
function stateLabel(state: string | undefined): string {
  switch (state) {
    case 'closed':
      return 'Healthy';
    case 'open':
      return 'Open (Failing)';
    case 'half_open':
      return 'Testing';
    case 'unavailable':
      return 'Unavailable';
    default:
      return 'Unknown';
  }
}

test.describe('golden path: websocket health @critical', () => {
  test.setTimeout(60_000);

  test('both broadcaster cards render with health badges', async ({ page }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    const health = await api<{
      event_broadcaster?: BroadcasterState;
      system_broadcaster?: BroadcasterState;
    }>(h, session, '/api/system/health/websocket');
    // Keyed presence, not Object.keys > 0: a body like {"garbage": 1} must NOT
    // satisfy this — the panel renders a card per broadcaster, keyed by name.
    expect(health.event_broadcaster, 'event_broadcaster missing from health body').toBeTruthy();
    expect(health.system_broadcaster, 'system_broadcaster missing from health body').toBeTruthy();

    await page.goto(`${h.ui}/operations`, { waitUntil: 'domcontentloaded' });
    await openSection(page, 'websocket-health');
    await expect(page.getByTestId('websocket-health-panel')).toBeVisible();
    for (const which of ['event', 'system'] as const) {
      await expect(page.getByTestId(`broadcaster-card-${which}`)).toBeVisible();
      // undefined → 'Unknown' in the component only when the status object is
      // present but stateless; our truthiness checks above pin the object, so
      // the label mirrors whatever state the fetched body carries.
      await expect(page.getByTestId(`broadcaster-status-badge-${which}`)).toHaveText(
        stateLabel(health[`${which}_broadcaster`]?.state)
      );
    }

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
