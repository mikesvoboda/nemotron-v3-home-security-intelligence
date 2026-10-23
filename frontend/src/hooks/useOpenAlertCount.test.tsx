/**
 * Unit tier for useOpenAlertCount (F4.1's nav-badge hook).
 *
 * What this tier proves: the badge number is the SERVER's pagination.total of
 * the status=open list (limit 1 — one row fetched, the total still counts),
 * it reads 0 while loading so the badge never flashes, `enabled: false`
 * fetches nothing, and the query key shares the alerts family so a WebSocket
 * invalidation of alertsQueryKeys.all reaches it. The wire behaviour of
 * fetchAlerts itself is mocked here and pinned by the AlertsPage unit tier
 * and the golden spec.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { type ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { alertsQueryKeys } from './useAlertsQuery';
import { useOpenAlertCount } from './useOpenAlertCount';
import * as alertsApi from '../services/alertsApi';

vi.mock('../services/alertsApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/alertsApi')>();
  return { ...actual, fetchAlerts: vi.fn() };
});

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

function listResponse(total: number) {
  return {
    items: [],
    pagination: { total, limit: 1, offset: 0, has_more: false },
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});
afterEach(() => {
  vi.useRealTimers();
});

describe('useOpenAlertCount', () => {
  it('reads the server pagination.total of the status=open list, not the rows', async () => {
    // limit 1 fetches one row; the badge is the TOTAL (7 open alerts behind
    // it), which is the whole point of reading pagination.total.
    vi.mocked(alertsApi.fetchAlerts).mockResolvedValue(listResponse(7));
    const { result } = renderHook(() => useOpenAlertCount(), { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(result.current).toBe(7);
    });
    expect(vi.mocked(alertsApi.fetchAlerts)).toHaveBeenCalledWith({ status: 'open', limit: 1 });
  });

  it('reads 0 while the first fetch is in flight (no badge flash)', () => {
    vi.mocked(alertsApi.fetchAlerts).mockImplementation(() => new Promise(() => {}));
    const { result } = renderHook(() => useOpenAlertCount(), { wrapper: makeWrapper() });
    expect(result.current).toBe(0);
  });

  it('reads 0 when the list fails (an erroring badge hides, not NaN)', async () => {
    vi.mocked(alertsApi.fetchAlerts).mockRejectedValue(new Error('boom'));
    const { result } = renderHook(() => useOpenAlertCount(), { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(vi.mocked(alertsApi.fetchAlerts)).toHaveBeenCalled();
    });
    expect(result.current).toBe(0);
  });

  it('enabled=false fetches nothing and reads 0', () => {
    vi.mocked(alertsApi.fetchAlerts).mockImplementation(() => new Promise(() => {}));
    renderHook(() => useOpenAlertCount(false), { wrapper: makeWrapper() });
    expect(vi.mocked(alertsApi.fetchAlerts)).not.toHaveBeenCalled();
  });

  it('keys under alertsQueryKeys.all, so the WebSocket invalidation reaches it', async () => {
    vi.mocked(alertsApi.fetchAlerts).mockResolvedValue(listResponse(2));
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 } },
    });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
    const { result } = renderHook(() => useOpenAlertCount(), { wrapper });
    await waitFor(() => {
      expect(result.current).toBe(2);
    });
    // The exact invalidation useAlertWebSocket fires on every alert frame:
    // invalidateQueries({queryKey: alertsQueryKeys.all}). With the hook
    // mounted, the invalidated entry refetches at once (the refetch also
    // clears isInvalidated, so polling that flag races the very refetch the
    // invalidation schedules) — the observable is a SECOND fetchAlerts call:
    // the badge updates wherever it's mounted.
    const calls = vi.mocked(alertsApi.fetchAlerts).mock.calls.length;
    await queryClient.invalidateQueries({ queryKey: alertsQueryKeys.all });
    await waitFor(() => {
      expect(vi.mocked(alertsApi.fetchAlerts).mock.calls.length).toBeGreaterThan(calls);
    });
  });
});
