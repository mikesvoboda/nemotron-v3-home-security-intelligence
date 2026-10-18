/**
 * F-138 (inventory 3.8): Operations › Circuit breakers › Reset on `/operations`
 * (`POST /api/system/circuit-breakers/{name}/reset`, `GET /api/system/circuit-breakers`).
 *
 * `CircuitBreakerRow` (`frontend/src/components/system/CircuitBreakerPanel.tsx:360`)
 * renders `reset-button-${name}` only when `breaker.state !== 'closed'`. On a
 * healthy stack with no fault seed, every registered breaker in
 * `GET /api/system/circuit-breakers` is `closed`, so this spec verifies the
 * backend reset route directly and pins the `toHaveCount(0)` closed-state gate
 * on every card; when a breaker is non-closed (under the ruling-127 fault
 * seed), it clicks `reset-button-${name}` and asserts the breaker transitions
 * back to `closed` and the list re-fetches.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import {
  api,
  authPost,
  closedByGuard,
  loginAsAdmin,
  openSection,
  readOpsHarness,
} from '../harness';

const harness = readOpsHarness();

interface BreakerEntry {
  name: string;
  state: 'closed' | 'open' | 'half_open';
  failure_count: number;
}

interface CircuitBreakersBody {
  circuit_breakers?: Record<string, BreakerEntry>;
}

interface CircuitBreakerResetBody {
  name: string;
  previous_state: string;
  new_state: string;
  message: string;
}

test.describe('golden path: circuit breaker reset (F-138) @critical', () => {
  test.setTimeout(60_000);

  test('resets a non-closed breaker through the UI, or pins the closed-state Reset gate when all breakers are closed', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    const body = await api<CircuitBreakersBody>(h, session, '/api/system/circuit-breakers');
    const entries = Object.values(body.circuit_breakers ?? {});
    expect(entries.length).toBeGreaterThan(0);

    let listFetches = 0;
    page.on('response', (res) => {
      try {
        if (new URL(res.url()).pathname === '/api/system/circuit-breakers') listFetches += 1;
      } catch {
        /* ignore non-URL responses */
      }
    });

    await page.goto(`${h.ui}/operations`, { waitUntil: 'domcontentloaded' });
    await openSection(page, 'circuit-breakers');
    await expect(page.getByTestId('circuit-breaker-summary')).toBeVisible();

    const nonClosed = entries.find((b) => b.state !== 'closed');

    if (nonClosed) {
      const resetBtn = page.getByTestId(`reset-button-${nonClosed.name}`);
      await expect(resetBtn).toBeVisible();
      const beforeClick = listFetches;
      await resetBtn.click();
      await expect
        .poll(() => listFetches, { timeout: 15_000, intervals: [300] })
        .toBeGreaterThan(beforeClick);
      await expect(page.getByTestId(`circuit-breaker-status-${nonClosed.name}`)).toHaveText(
        'closed'
      );
      await expect(resetBtn).toHaveCount(0);
    } else {
      // Every breaker is closed: Reset buttons do not mount in the UI
      // (CircuitBreakerPanel.tsx:360), while the backend reset route itself is
      // live and idempotent.
      for (const entry of entries) {
        await expect(page.getByTestId(`circuit-breaker-${entry.name}`)).toBeVisible();
        await expect(page.getByTestId(`circuit-breaker-status-${entry.name}`)).toHaveText('closed');
        await expect(page.getByTestId(`reset-button-${entry.name}`)).toHaveCount(0);
      }
      const first = entries[0];
      const resetRes = await authPost<CircuitBreakerResetBody>(
        h,
        session,
        `/api/system/circuit-breakers/${first.name}/reset`
      );
      expect(resetRes.name).toBe(first.name);
      expect(resetRes.new_state).toBe('closed');
    }

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
