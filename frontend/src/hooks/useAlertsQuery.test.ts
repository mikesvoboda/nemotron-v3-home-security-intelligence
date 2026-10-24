/**
 * Tests for useAlertsQuery — the F4.1 alert-rows hook over the Alert Service
 * list endpoint (the alerts table, not the events feed).
 */

import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useAlertsQuery, alertsQueryKeys } from './useAlertsQuery';
import * as alertsApi from '../services/alertsApi';
import { createQueryClient } from '../services/queryClient';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

import type { AlertServiceListResponse } from '../services/alertsApi';

vi.mock('../services/alertsApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/alertsApi')>();
  return {
    ...actual,
    fetchAlerts: vi.fn(),
  };
});

/** Build a list response with the given items. */
function makeListResponse(
  items: Partial<AlertServiceListResponse['items'][number]>[]
): AlertServiceListResponse {
  return {
    items: items.map((item, index) => ({
      id: `alert-${index}`,
      event_id: 1,
      rule_id: null,
      severity: 'high',
      status: 'open',
      dedup_key: `front_door:${index}`,
      channels: [],
      metadata: {},
      created_at: '2026-10-22T10:00:00Z',
      updated_at: '2026-10-22T10:00:00Z',
      delivered_at: null,
      verdict_source: 'local',
      match_count: 1,
      last_seen_at: null,
      last_event_id: null,
      camera_id: 'front_door',
      ...item,
    })),
    pagination: { total: items.length, limit: 50, offset: 0, has_more: false },
  };
}

describe('useAlertsQuery', () => {
  let queryClient: ReturnType<typeof createQueryClient>;

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = createQueryClient();
  });

  afterEach(() => {
    queryClient.clear();
  });

  function render(options?: Parameters<typeof useAlertsQuery>[0]) {
    return renderHook(() => useAlertsQuery(options), {
      wrapper: createQueryWrapper(queryClient),
    });
  }

  describe('initialization', () => {
    it('starts loading then returns the alert rows', async () => {
      vi.mocked(alertsApi.fetchAlerts).mockResolvedValue(
        makeListResponse([{ id: 'a1' }, { id: 'a2' }])
      );

      const { result } = render({ statusFilter: 'open' });

      await waitFor(() => expect(result.current.isLoading).toBe(false));
      expect(result.current.alerts).toHaveLength(2);
      expect(result.current.totalCount).toBe(2);
      expect(result.current.isError).toBe(false);
    });

    it('sends the open status filter by default', async () => {
      vi.mocked(alertsApi.fetchAlerts).mockResolvedValue(makeListResponse([]));

      render();

      await waitFor(() => expect(alertsApi.fetchAlerts).toHaveBeenCalled());
      expect(alertsApi.fetchAlerts).toHaveBeenCalledWith(
        expect.objectContaining({ status: 'open' })
      );
    });

    it('sends no status param for the all filter', async () => {
      vi.mocked(alertsApi.fetchAlerts).mockResolvedValue(makeListResponse([]));

      render({ statusFilter: 'all' });

      await waitFor(() => expect(alertsApi.fetchAlerts).toHaveBeenCalled());
      expect(alertsApi.fetchAlerts).toHaveBeenCalledWith(
        expect.objectContaining({ status: undefined })
      );
    });

    it('forwards severity and limit', async () => {
      vi.mocked(alertsApi.fetchAlerts).mockResolvedValue(makeListResponse([]));

      render({ severity: 'critical', limit: 25 });

      await waitFor(() => expect(alertsApi.fetchAlerts).toHaveBeenCalled());
      expect(alertsApi.fetchAlerts).toHaveBeenCalledWith(
        expect.objectContaining({ severity: 'critical', limit: 25 })
      );
    });
  });

  describe('sorting', () => {
    it('sorts by last_seen_at falling back to created_at, newest first', async () => {
      vi.mocked(alertsApi.fetchAlerts).mockResolvedValue(
        makeListResponse([
          { id: 'old', created_at: '2026-10-20T10:00:00Z', last_seen_at: null },
          {
            id: 'fresh-fold',
            created_at: '2026-10-21T10:00:00Z',
            last_seen_at: '2026-10-22T09:00:00Z',
          },
          { id: 'mid', created_at: '2026-10-21T10:00:00Z' },
        ])
      );

      const { result } = render();

      await waitFor(() => expect(result.current.alerts).toHaveLength(3));
      const ids = result.current.alerts.map((a) => a.id);
      expect(ids).toEqual(['fresh-fold', 'mid', 'old']);
    });

    it('does not reorder when the source array is the same reference', async () => {
      const response = makeListResponse([
        { id: 'a', created_at: '2026-10-22T10:00:00Z' },
        { id: 'b', created_at: '2026-10-22T09:00:00Z' },
      ]);
      vi.mocked(alertsApi.fetchAlerts).mockResolvedValue(response);

      const { result } = render();

      await waitFor(() => expect(result.current.alerts).toHaveLength(2));
      // first render order: memo applies on data
      expect(result.current.alerts.map((a) => a.id)).toEqual(['a', 'b']);
    });
  });

  describe('error handling', () => {
    it('surfaces the error and isError state', async () => {
      vi.mocked(alertsApi.fetchAlerts).mockRejectedValue(
        new alertsApi.AlertsApiError('boom', 500, false)
      );

      const { result } = render();

      await waitFor(() => expect(result.current.isError).toBe(true));
      expect(result.current.error?.message).toBe('boom');
      expect(result.current.alerts).toEqual([]);
      expect(result.current.totalCount).toBe(0);
    });
  });

  describe('enabled option', () => {
    it('does not fetch when disabled', async () => {
      vi.mocked(alertsApi.fetchAlerts).mockResolvedValue(makeListResponse([]));

      render({ enabled: false });

      await act(async () => {
        await Promise.resolve();
      });
      expect(alertsApi.fetchAlerts).not.toHaveBeenCalled();
    });
  });

  describe('refetch function', () => {
    it('refetches and updates the rows', async () => {
      vi.mocked(alertsApi.fetchAlerts).mockResolvedValueOnce(makeListResponse([{ id: 'a1' }]));
      vi.mocked(alertsApi.fetchAlerts).mockResolvedValueOnce(makeListResponse([{ id: 'a2' }]));

      const { result } = render();

      await waitFor(() => expect(result.current.alerts[0]?.id).toBe('a1'));

      await act(async () => {
        await result.current.refetch();
      });

      await waitFor(() => expect(result.current.alerts[0]?.id).toBe('a2'));
    });
  });

  describe('query keys', () => {
    it('keeps every key under the shared alerts root', () => {
      expect(alertsQueryKeys.all).toEqual(['alerts']);
      expect(alertsQueryKeys.list({ statusFilter: 'open', limit: 50 })).toEqual([
        'alerts',
        'list',
        { statusFilter: 'open', limit: 50 },
      ]);
      expect(alertsQueryKeys.infinite('high', 25)[0]).toBe('alerts');
    });
  });
});
