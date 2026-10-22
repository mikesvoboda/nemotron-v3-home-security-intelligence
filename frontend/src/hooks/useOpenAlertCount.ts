/**
 * useOpenAlertCount — the Alerts nav item's open count (F4.1).
 *
 * Reads the Alert Service list with limit 1 and uses the server's
 * `pagination.total` (the count of rows matching `status=open`), so the badge
 * is a count, not a guess. Shares the `alertsQueryKeys` cache family, so a
 * WebSocket alert frame (useAlertWebSocket invalidates `alertsQueryKeys.all`
 * on every frame) or an ack/dismiss refetch updates the badge wherever it's
 * mounted.
 *
 * @module hooks/useOpenAlertCount
 */

import { useQuery } from '@tanstack/react-query';

import { alertsQueryKeys } from './useAlertsQuery';
import { fetchAlerts } from '../services/alertsApi';
import { DEFAULT_STALE_TIME } from '../services/queryClient';

/**
 * Count of open alerts for the nav badge. 0 while loading; the badge hides at
 * 0, so the initial fetch never flashes a count.
 */
export function useOpenAlertCount(enabled = true): number {
  const { data } = useQuery({
    queryKey: [...alertsQueryKeys.all, 'open-count'] as const,
    queryFn: () => fetchAlerts({ status: 'open', limit: 1 }),
    enabled,
    staleTime: DEFAULT_STALE_TIME,
  });

  return data?.pagination.total ?? 0;
}
