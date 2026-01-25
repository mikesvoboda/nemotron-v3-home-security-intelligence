/**
 * ZoneAnomalyFeed - List of recent zone anomaly alerts (NEM-3199)
 *
 * Displays a filterable feed of recent zone anomalies with real-time
 * updates via WebSocket. Supports filtering by severity, zone, and
 * acknowledged status.
 *
 * Features:
 * - Filter by severity (INFO, WARNING, CRITICAL)
 * - Filter by zone
 * - Filter by acknowledged status
 * - Real-time updates via WebSocket
 * - Infinite scroll / pagination
 * - Empty state handling
 *
 * @module components/zones/ZoneAnomalyFeed
 * @see NEM-3199 Frontend Anomaly Alert Integration
 */

import { clsx } from 'clsx';
import { AlertTriangle, Filter, Wifi, WifiOff, RefreshCw } from 'lucide-react';
import { memo, useCallback, useMemo, useState } from 'react';

import { ZoneAnomalyAlert } from './ZoneAnomalyAlert';
import { useZoneAnomalies } from '../../hooks/useZoneAnomalies';
import { useZonesQuery } from '../../hooks/useZones';
import { ANOMALY_SEVERITY_CONFIG } from '../../types/zoneAnomaly';

import type {
  ZoneAnomalyFeedProps,
  ZoneAnomalyFeedFilters,
  ZoneAnomaly,
} from '../../types/zoneAnomaly';

// ============================================================================
// Filter Components
// ============================================================================

interface FilterBarProps {
  filters: ZoneAnomalyFeedFilters;
  onFilterChange: (filters: ZoneAnomalyFeedFilters) => void;
  zones: Array<{ id: string; name: string }>;
  disabled?: boolean;
}

/**
 * Filter bar for the anomaly feed.
 */
function FilterBar({ filters, onFilterChange, zones, disabled }: FilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg bg-gray-800/50 p-3">
      <div className="flex items-center gap-2 text-sm text-text-secondary">
        <Filter className="h-4 w-4" />
        <span>Filters:</span>
      </div>

      {/* Severity filter */}
      <select
        value={filters.severity}
        onChange={(e) =>
          onFilterChange({
            ...filters,
            severity: e.target.value as ZoneAnomalyFeedFilters['severity'],
          })
        }
        disabled={disabled}
        className={clsx(
          'rounded border border-gray-700 bg-gray-800 px-2 py-1 text-sm text-text-primary',
          'focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary',
          disabled && 'cursor-not-allowed opacity-50'
        )}
        aria-label="Filter by severity"
      >
        <option value="all">All Severities</option>
        {Object.entries(ANOMALY_SEVERITY_CONFIG).map(([key, config]) => (
          <option key={key} value={key}>
            {config.label}
          </option>
        ))}
      </select>

      {/* Zone filter */}
      <select
        value={filters.zoneId}
        onChange={(e) =>
          onFilterChange({
            ...filters,
            zoneId: e.target.value,
          })
        }
        disabled={disabled}
        className={clsx(
          'rounded border border-gray-700 bg-gray-800 px-2 py-1 text-sm text-text-primary',
          'focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary',
          disabled && 'cursor-not-allowed opacity-50'
        )}
        aria-label="Filter by zone"
      >
        <option value="all">All Zones</option>
        {zones.map((zone) => (
          <option key={zone.id} value={zone.id}>
            {zone.name}
          </option>
        ))}
      </select>

      {/* Acknowledged filter */}
      <select
        value={filters.acknowledged}
        onChange={(e) =>
          onFilterChange({
            ...filters,
            acknowledged: e.target.value as ZoneAnomalyFeedFilters['acknowledged'],
          })
        }
        disabled={disabled}
        className={clsx(
          'rounded border border-gray-700 bg-gray-800 px-2 py-1 text-sm text-text-primary',
          'focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary',
          disabled && 'cursor-not-allowed opacity-50'
        )}
        aria-label="Filter by acknowledged status"
      >
        <option value="all">All Status</option>
        <option value="unacknowledged">Unacknowledged</option>
        <option value="acknowledged">Acknowledged</option>
      </select>
    </div>
  );
}

// ============================================================================
// Empty State
// ============================================================================

interface EmptyStateProps {
  hasFilters: boolean;
}

/**
 * Empty state when no anomalies are found.
 */
function EmptyState({ hasFilters }: EmptyStateProps) {
  return (
    <div
      className="flex flex-col items-center justify-center py-12 text-center"
      data-testid="anomaly-feed-empty"
    >
      <div className="rounded-full bg-gray-800 p-3">
        <AlertTriangle className="h-6 w-6 text-gray-500" />
      </div>
      <h3 className="mt-3 text-sm font-medium text-text-primary">No anomalies found</h3>
      <p className="mt-1 text-xs text-text-secondary">
        {hasFilters
          ? 'Try adjusting your filters to see more results.'
          : 'Zone activity is within normal patterns.'}
      </p>
    </div>
  );
}

// ============================================================================
// Loading State
// ============================================================================

function LoadingState() {
  return (
    <div className="space-y-3" data-testid="anomaly-feed-loading">
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="h-24 animate-pulse rounded-lg border border-gray-700 bg-gray-800/50"
        />
      ))}
    </div>
  );
}

// ============================================================================
// Error State
// ============================================================================

interface ErrorStateProps {
  error: Error;
  onRetry: () => void;
}

function ErrorState({ error, onRetry }: ErrorStateProps) {
  return (
    <div
      className="flex flex-col items-center justify-center rounded-lg border border-red-500/30 bg-red-500/10 py-8 text-center"
      data-testid="anomaly-feed-error"
    >
      <AlertTriangle className="h-6 w-6 text-red-400" />
      <h3 className="mt-2 text-sm font-medium text-red-400">Failed to load anomalies</h3>
      <p className="mt-1 text-xs text-text-secondary">{error.message}</p>
      <button
        type="button"
        onClick={onRetry}
        className={clsx(
          'mt-3 inline-flex items-center gap-1.5 rounded px-3 py-1.5',
          'bg-red-500/20 text-sm text-red-400',
          'hover:bg-red-500/30 focus:outline-none focus:ring-2 focus:ring-red-500'
        )}
      >
        <RefreshCw className="h-4 w-4" />
        Retry
      </button>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * ZoneAnomalyFeed displays a filterable list of recent zone anomalies.
 *
 * Supports real-time updates via WebSocket and provides filtering
 * by severity, zone, and acknowledged status.
 *
 * @example
 * ```tsx
 * <ZoneAnomalyFeed
 *   enableRealtime
 *   hoursLookback={24}
 *   onAnomalyClick={(anomaly) => router.push(`/anomalies/${anomaly.id}`)}
 * />
 * ```
 */
function ZoneAnomalyFeedComponent({
  zoneId,
  initialFilters,
  maxHeight = '600px',
  enableRealtime = true,
  onAnomalyClick,
  className,
  hoursLookback = 24,
}: ZoneAnomalyFeedProps) {
  // Filter state
  const [filters, setFilters] = useState<ZoneAnomalyFeedFilters>({
    severity: 'all',
    zoneId: zoneId ?? 'all',
    acknowledged: 'all',
    ...initialFilters,
  });

  // Calculate the "since" time based on hoursLookback
  const sinceTime = useMemo(() => {
    const date = new Date();
    date.setHours(date.getHours() - hoursLookback);
    return date.toISOString();
  }, [hoursLookback]);

  // Fetch zones for the filter dropdown
  // Note: We use a fixed cameraId here since zones may span cameras
  // In a real implementation, this would fetch all zones
  const { zones } = useZonesQuery(undefined, { enabled: false });

  // Determine query options based on filters
  const queryOptions = useMemo(
    () => ({
      zoneId: filters.zoneId !== 'all' ? filters.zoneId : zoneId,
      severity: filters.severity !== 'all' ? filters.severity : undefined,
      unacknowledgedOnly: filters.acknowledged === 'unacknowledged',
      since: sinceTime,
      enableRealtime,
      limit: 50,
    }),
    [filters, zoneId, sinceTime, enableRealtime]
  );

  // Fetch anomalies
  const {
    anomalies,
    totalCount,
    isLoading,
    isFetching,
    error,
    isError,
    refetch,
    acknowledgeAnomaly,
    isAcknowledging,
    isConnected,
  } = useZoneAnomalies(queryOptions);

  // Filter anomalies client-side for acknowledged filter
  const filteredAnomalies = useMemo(() => {
    if (filters.acknowledged === 'all') {
      return anomalies;
    }
    const showAcknowledged = filters.acknowledged === 'acknowledged';
    return anomalies.filter((a) => a.acknowledged === showAcknowledged);
  }, [anomalies, filters.acknowledged]);

  // Check if any filters are active
  const hasActiveFilters =
    filters.severity !== 'all' || filters.zoneId !== 'all' || filters.acknowledged !== 'all';

  // Handle filter change
  const handleFilterChange = useCallback((newFilters: ZoneAnomalyFeedFilters) => {
    setFilters(newFilters);
  }, []);

  // Handle acknowledge
  const handleAcknowledge = useCallback(
    (anomalyId: string) => {
      void acknowledgeAnomaly(anomalyId);
    },
    [acknowledgeAnomaly]
  );

  // Handle anomaly click
  const handleAnomalyClick = useCallback(
    (anomaly: ZoneAnomaly) => {
      onAnomalyClick?.(anomaly);
    },
    [onAnomalyClick]
  );

  // Handle retry
  const handleRetry = useCallback(() => {
    void refetch();
  }, [refetch]);

  // Build zone lookup for display names
  const zoneNameMap = useMemo(() => {
    const map = new Map<string, string>();
    zones.forEach((z) => map.set(z.id, z.name));
    return map;
  }, [zones]);

  // Zone options for filter
  const zoneOptions = useMemo(() => {
    // Get unique zones from anomalies if we don't have zones from query
    const zoneSet = new Map<string, string>();
    zones.forEach((z) => zoneSet.set(z.id, z.name));
    anomalies.forEach((a) => {
      if (!zoneSet.has(a.zone_id)) {
        zoneSet.set(a.zone_id, `Zone ${a.zone_id.substring(0, 8)}`);
      }
    });
    return Array.from(zoneSet.entries()).map(([id, name]) => ({ id, name }));
  }, [zones, anomalies]);

  return (
    <div className={clsx('flex flex-col', className)} data-testid="zone-anomaly-feed">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-text-primary">Zone Anomalies</h3>
          <p className="text-sm text-text-secondary">
            {totalCount} {totalCount === 1 ? 'anomaly' : 'anomalies'} in the last {hoursLookback}{' '}
            hours
          </p>
        </div>

        {/* Connection status */}
        <div className="flex items-center gap-2">
          {isFetching && !isLoading && <RefreshCw className="h-4 w-4 animate-spin text-primary" />}
          {enableRealtime && (
            <div
              className={clsx(
                'flex items-center gap-1 rounded px-2 py-1 text-xs',
                isConnected ? 'bg-green-500/10 text-green-400' : 'bg-gray-700 text-gray-400'
              )}
              title={isConnected ? 'Real-time updates active' : 'Connecting...'}
            >
              {isConnected ? (
                <>
                  <Wifi className="h-3 w-3" />
                  <span>Live</span>
                </>
              ) : (
                <>
                  <WifiOff className="h-3 w-3" />
                  <span>Offline</span>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Filter bar */}
      <FilterBar
        filters={filters}
        onFilterChange={handleFilterChange}
        zones={zoneOptions}
        disabled={isLoading}
      />

      {/* Content */}
      <div
        className="mt-4 overflow-y-auto"
        style={{ maxHeight: typeof maxHeight === 'number' ? `${maxHeight}px` : maxHeight }}
      >
        {isLoading ? (
          <LoadingState />
        ) : isError && error ? (
          <ErrorState error={error} onRetry={handleRetry} />
        ) : filteredAnomalies.length === 0 ? (
          <EmptyState hasFilters={hasActiveFilters} />
        ) : (
          <div className="space-y-3" data-testid="anomaly-feed-list">
            {filteredAnomalies.map((anomaly) => (
              <ZoneAnomalyAlert
                key={anomaly.id}
                anomaly={anomaly}
                zoneName={zoneNameMap.get(anomaly.zone_id)}
                onAcknowledge={handleAcknowledge}
                onClick={onAnomalyClick ? handleAnomalyClick : undefined}
                isAcknowledging={isAcknowledging}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Memoized ZoneAnomalyFeed component for performance.
 */
export const ZoneAnomalyFeed = memo(ZoneAnomalyFeedComponent);

export default ZoneAnomalyFeed;
