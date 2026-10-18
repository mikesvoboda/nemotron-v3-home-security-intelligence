/**
 * F-138 (inventory 3.8, seeded golden project — rulings 127, 187):
 * Operations › Circuit breakers › Reset on `/operations` when `HSI_FAULT_SEED=1`
 * behind the debug guard trips the `redis` breaker in `_get_registry()` to
 * `open`.
 *
 * Clicking `reset-button-${name}` POSTs `/api/system/circuit-breakers/${name}/reset`,
 * re-fetches `/api/system/circuit-breakers`, transitions the card's status
 * badge from `open` to `closed`, and unmounts the Reset button.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { api, closedByGuard, loginAsAdmin, openSection, readOpsHarness } from '../harness';

const harness = readOpsHarness();

interface BreakerEntry {
  name: string;
  state: 'closed' | 'open' | 'half_open';
  failure_count: number;
}

interface CircuitBreakersBody {
  circuit_breakers?: Record<string, BreakerEntry>;
  open_count?: number;
}

test.describe('seeded golden path: circuit breaker reset (F-138) @critical', () => {
  test.setTimeout(60_000);

  test('clicks Reset on the fault-seeded open breaker, re-fetches the list, and transitions it to closed', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    test.info().annotations.push({
      type: 'seeded-branch',
      description: 'F-138 open breaker reset through UI',
    });

    const before = await api<CircuitBreakersBody>(h, session, '/api/system/circuit-breakers');
    const entries = Object.values(before.circuit_breakers ?? {});
    const nonClosed = entries.find((b) => b.state !== 'closed');
    expect(
      nonClosed,
      `expected fault-seeded non-closed breaker in ${JSON.stringify(before)}`
    ).toBeTruthy();

    let listFetches = 0;
    let resetPosts = 0;
    page.on('response', (res) => {
      try {
        const pathname = new URL(res.url()).pathname;
        if (pathname === '/api/system/circuit-breakers') listFetches += 1;
        if (pathname === `/api/system/circuit-breakers/${nonClosed!.name}/reset`) resetPosts += 1;
      } catch {
        /* ignore non-URL responses */
      }
    });

    await page.goto(`${h.ui}/operations`, { waitUntil: 'domcontentloaded' });
    await openSection(page, 'circuit-breakers');
    await expect(page.getByTestId('circuit-breaker-summary')).toBeVisible();

    const statusBadge = page.getByTestId(`circuit-breaker-status-${nonClosed!.name}`);
    const resetBtn = page.getByTestId(`reset-button-${nonClosed!.name}`);
    await expect(statusBadge).toHaveText(nonClosed!.state);
    await expect(resetBtn).toBeVisible();

    const fetchesBeforeClick = listFetches;
    await resetBtn.click();

    await expect.poll(() => resetPosts, { timeout: 15_000, intervals: [300] }).toBe(1);
    await expect
      .poll(() => listFetches, { timeout: 15_000, intervals: [300] })
      .toBeGreaterThan(fetchesBeforeClick);

    await expect(statusBadge).toHaveText('closed');
    await expect(resetBtn).toHaveCount(0);

    const after = await api<CircuitBreakersBody>(h, session, '/api/system/circuit-breakers');
    expect(after.circuit_breakers?.[nonClosed!.name]?.state).toBe('closed');

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
