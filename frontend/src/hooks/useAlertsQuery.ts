/**
 * useAlertsQuery - React Query hook for the alerts table (F4.1)
 *
 * Reads the alert rows the alerting pipeline writes (B4.1) through the Alert
 * Service list endpoint, not the events feed this hook read before F4.1. The
 * page shows open alerts by default, or all; live updates ride the existing
 * `useAlertWebSocket`, which invalidates `alertsQueryKeys.all` on every alert
 * frame — so the key family below is chosen to stay under that root.
 *
 * @module hooks/useAlertsQuery
 */

import { useQuery, type QueryKey } from '@tanstack/react-query';
import { useMemo } from 'react';

import {
  fetchAlerts,
  acknowledgeAlert,
  dismissAlert,
  isConflictError,
  type AlertServiceResponse,
} from '../services/alertsApi';
import { DEFAULT_STALE_TIME } from '../services/queryClient';

// ============================================================================
// Types
// ============================================================================

/** Status filter for the alerts list — the page's open/all toggle. */
export type AlertStatusFilter = 'open' | 'all';

/** Map the toggle to the API's status filter (the API has no "all" value). */
function statusFilterParam(status: AlertStatusFilter): string | undefined {
  return status === 'all' ? undefined : status;
}

/**
 * Options for the useAlertsQuery hook
 */
export interface UseAlertsQueryOptions {
  /**
   * Which alerts to show: open only (the page default) or all statuses
   * @default 'open'
   */
  statusFilter?: AlertStatusFilter;

  /**
   * Severity filter forwarded to the API (none by default)
   */
  severity?: string;

  /**
   * Maximum number of results per page
   * @default 50 (the endpoint's own default)
   */
  limit?: number;

  /**
   * Whether to enable the query
   * @default true
   */
  enabled?: boolean;

  /**
   * Refetch interval in milliseconds
   * @default false (no auto-refetch)
   */
  refetchInterval?: number | false;

  /**
   * Custom stale time in milliseconds
   * @default DEFAULT_STALE_TIME
   */
  staleTime?: number;
}

/**
 * Return type for the useAlertsQuery hook
 */
export interface UseAlertsQueryReturn {
  /** Alert rows for the current filters, newest first */
  alerts: AlertServiceResponse[];

  /** Total count of alerts matching the filter (server-side) */
  totalCount: number;

  /** Whether the initial fetch is in progress */
  isLoading: boolean;

  /** Whether any fetch is in progress (including background refetch) */
  isFetching: boolean;

  /** Error object if the query failed */
  error: Error | null;

  /** Whether the query has errored */
  isError: boolean;

  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

// ============================================================================
// Query Key Factory
// ============================================================================

/**
 * Query keys for the alerts cache. `all` is the invalidation root shared with
 * `useAlertWebSocket` (it invalidates `alertsQueryKeys.all` on every alert
 * frame) and `useSnoozeEvent` — every key this factory produces lives under
 * it, so a WebSocket push or a snooze refetches whatever is mounted.
 */
export const alertsQueryKeys = {
  all: ['alerts'] as const,
  /** The F4.1 alert-rows list keyed by its filters. */
  list: (filters: { statusFilter?: AlertStatusFilter; severity?: string; limit?: number }) =>
    [...alertsQueryKeys.all, 'list', filters] as const,
  /** Kept for the WebSocket hook's direct-key callers; same root. */
  infinite: (riskLevel: 'high' | 'critical', limit: number) =>
    [...alertsQueryKeys.all, 'infinite', { riskLevel, limit }] as const,
};

// ============================================================================
// Main Hook Implementation
// ============================================================================

/**
 * Hook to fetch alert rows from the Alert Service.
 *
 * Reads `GET /api/alert-service/alerts` with the page's status filter (open
 * by default, or all). Live updates arrive through `useAlertWebSocket`, whose
 * cache invalidation lands on this hook's keys automatically.
 *
 * @param options - Configuration options
 * @returns Alert rows and query state
 *
 * @example
 * ```tsx
 * const {
 *   alerts,
 *   totalCount,
 *   isLoading,
 * } = useAlertsQuery({ statusFilter: 'open' });
 * ```
 */
export function useAlertsQuery(options: UseAlertsQueryOptions = {}): UseAlertsQueryReturn {
  const {
    statusFilter = 'open',
    severity,
    limit = 50,
    enabled = true,
    refetchInterval = false,
    staleTime = DEFAULT_STALE_TIME,
  } = options;

  const filters = useMemo(
    () => ({ statusFilter, severity, limit }),
    [statusFilter, severity, limit]
  );

  const query = useQuery<
    Awaited<ReturnType<typeof fetchAlerts>>,
    Error,
    Awaited<ReturnType<typeof fetchAlerts>>,
    QueryKey
  >({
    queryKey: alertsQueryKeys.list(filters),
    queryFn: () =>
      fetchAlerts({
        status: statusFilterParam(statusFilter),
        severity,
        limit,
      }),
    enabled,
    refetchInterval,
    staleTime,
  });

  // Newest first: the endpoint sorts by created_at DESC already, but the
  // page pins its order locally so a refetch reorder cannot surprise a
  // reader mid-scan. last_seen_at (the fold's most recent match) is the
  // row's real recency; created_at breaks ties and covers rows without one.
  const alerts = useMemo(() => {
    const items = query.data?.items ?? [];
    return [...items].sort((a, b) => {
      const aTime = new Date(a.last_seen_at ?? a.created_at).getTime();
      const bTime = new Date(b.last_seen_at ?? b.created_at).getTime();
      return bTime - aTime;
    });
  }, [query.data?.items]);

  const totalCount = query.data?.pagination.total ?? 0;

  return {
    alerts,
    totalCount,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    isError: query.isError,
    refetch: query.refetch,
  };
}

export { acknowledgeAlert, dismissAlert, isConflictError };
export default useAlertsQuery;
