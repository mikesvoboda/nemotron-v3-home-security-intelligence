/**
 * ZoneAlertFeed - Unified feed for zone anomaly and trust violation alerts (NEM-3196)
 *
 * Aggregates and displays trust violation alerts and anomaly alerts in a unified
 * feed with priority sorting, grouping options, and batch acknowledge functionality.
 *
 * Features:
 * - Unified feed combining anomaly alerts and trust violations
 * - Priority sorting: CRITICAL > WARNING > INFO
 * - Grouping by zone, time, or severity
 * - Acknowledge all / acknowledge by severity
 * - Sound notification toggle for critical alerts
 * - Real-time updates via WebSocket
 *
 * @module components/zones/ZoneAlertFeed
 * @see NEM-3196 ZoneAlertFeed component implementation
 */

import { clsx } from 'clsx';
import { formatDistanceToNow, format, isToday, isYesterday, startOfDay } from 'date-fns';
import {
  AlertTriangle,
  AlertOctagon,
  Bell,
  Check,
  CheckCheck,
  Clock,
  Filter,
  Info,
  RefreshCw,
  ShieldOff,
  UserX,
  Volume2,
  VolumeX,
  Wifi,
  WifiOff,
} from 'lucide-react';
import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';

import { useZoneAlerts } from '../../hooks/useZoneAlerts';
import { useZonesQuery } from '../../hooks/useZones';
import {
  TrustViolationType,
  TRUST_VIOLATION_TYPE_CONFIG,
  isAnomalyAlert,
  isTrustViolationAlert,
} from '../../types/zoneAlert';
import { ANOMALY_SEVERITY_CONFIG, AnomalyType, ANOMALY_TYPE_CONFIG, AnomalySeverity } from '../../types/zoneAnomaly';

import type {
  ZoneAlertFeedProps,
  ZoneAlertFeedFilters,
  UnifiedZoneAlert,
  AlertGroup,
  AlertSource,
  SeverityValue,
} from '../../types/zoneAlert';


// ============================================================================
// Constants
// ============================================================================

/** Audio file path for critical alert sound */
const CRITICAL_ALERT_SOUND = '/sounds/critical-alert.mp3';

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Get the severity icon component based on severity level.
 */
function SeverityIcon({
  severity,
  className,
}: {
  severity: SeverityValue;
  className?: string;
}) {
  const iconProps = { className: clsx('h-5 w-5', className) };

  switch (severity) {
    case 'critical':
    case AnomalySeverity.CRITICAL:
      return <AlertOctagon {...iconProps} />;
    case 'warning':
    case AnomalySeverity.WARNING:
      return <AlertTriangle {...iconProps} />;
    case 'info':
    case AnomalySeverity.INFO:
    default:
      return <Info {...iconProps} />;
  }
}

/**
 * Get the source icon component based on alert source.
 */
function SourceIcon({
  alert,
  className,
}: {
  alert: UnifiedZoneAlert;
  className?: string;
}) {
  const iconProps = { className: clsx('h-4 w-4', className) };

  if (isAnomalyAlert(alert)) {
    const anomalyType = alert.originalAlert.anomaly_type;
    switch (anomalyType) {
      case AnomalyType.UNUSUAL_TIME:
        return <Clock {...iconProps} />;
      case AnomalyType.UNUSUAL_FREQUENCY:
        return <AlertTriangle {...iconProps} />;
      case AnomalyType.UNUSUAL_DWELL:
        return <Clock {...iconProps} />;
      case AnomalyType.UNUSUAL_ENTITY:
        return <UserX {...iconProps} />;
      default:
        return <Info {...iconProps} />;
    }
  }

  if (isTrustViolationAlert(alert)) {
    const violationType = alert.originalAlert.violation_type;
    switch (violationType) {
      case TrustViolationType.UNKNOWN_ENTITY:
        return <UserX {...iconProps} />;
      case TrustViolationType.UNAUTHORIZED_TIME:
        return <Clock {...iconProps} />;
      case TrustViolationType.RESTRICTED_ZONE:
        return <ShieldOff {...iconProps} />;
      default:
        return <AlertTriangle {...iconProps} />;
    }
  }

  return <Info {...iconProps} />;
}

/**
 * Get source label for an alert.
 */
function getSourceLabel(alert: UnifiedZoneAlert): string {
  if (isAnomalyAlert(alert)) {
    const anomalyType = alert.originalAlert.anomaly_type;
    return ANOMALY_TYPE_CONFIG[anomalyType]?.label ?? 'Anomaly';
  }
  if (isTrustViolationAlert(alert)) {
    const violationType = alert.originalAlert.violation_type;
    return TRUST_VIOLATION_TYPE_CONFIG[violationType]?.label ?? 'Trust Violation';
  }
  return 'Alert';
}

/**
 * Format time period label for grouping.
 */
function formatTimePeriod(date: Date): string {
  if (isToday(date)) {
    return 'Today';
  }
  if (isYesterday(date)) {
    return 'Yesterday';
  }
  return format(date, 'MMMM d, yyyy');
}

/**
 * Group alerts by the specified criteria.
 */
function groupAlerts(
  alerts: UnifiedZoneAlert[],
  groupBy: 'zone' | 'time' | 'severity',
  zoneNameMap: Map<string, string>
): AlertGroup[] {
  const groups = new Map<string, UnifiedZoneAlert[]>();

  alerts.forEach((alert) => {
    let key: string;
    switch (groupBy) {
      case 'zone':
        key = alert.zone_id;
        break;
      case 'time':
        key = startOfDay(new Date(alert.timestamp)).toISOString();
        break;
      case 'severity':
        key = alert.severity;
        break;
      default:
        key = 'all';
    }

    const existing = groups.get(key) ?? [];
    groups.set(key, [...existing, alert]);
  });

  // Convert to AlertGroup array
  const result: AlertGroup[] = [];
  groups.forEach((groupAlerts, key) => {
    let label: string;
    switch (groupBy) {
      case 'zone':
        label = zoneNameMap.get(key) ?? `Zone ${key.substring(0, 8)}`;
        break;
      case 'time':
        label = formatTimePeriod(new Date(key));
        break;
      case 'severity':
        label = ANOMALY_SEVERITY_CONFIG[key as AnomalySeverity]?.label ?? key;
        break;
      default:
        label = 'All Alerts';
    }

    result.push({
      key,
      label,
      alerts: groupAlerts,
      unacknowledgedCount: groupAlerts.filter((a) => !a.acknowledged).length,
    });
  });

  // Sort groups
  if (groupBy === 'severity') {
    const severityOrder = { critical: 0, warning: 1, info: 2 };
    result.sort((a, b) => {
      const aOrder = severityOrder[a.key as AnomalySeverity] ?? 3;
      const bOrder = severityOrder[b.key as AnomalySeverity] ?? 3;
      return aOrder - bOrder;
    });
  } else if (groupBy === 'time') {
    result.sort((a, b) => new Date(b.key).getTime() - new Date(a.key).getTime());
  }

  return result;
}

// ============================================================================
// Sub-components
// ============================================================================

interface FilterBarProps {
  filters: ZoneAlertFeedFilters;
  onFilterChange: (filters: ZoneAlertFeedFilters) => void;
  zones: Array<{ id: string; name: string }>;
  disabled?: boolean;
}

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
            severity: e.target.value as ZoneAlertFeedFilters['severity'],
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

      {/* Source filter */}
      <select
        value={filters.source}
        onChange={(e) =>
          onFilterChange({
            ...filters,
            source: e.target.value as ZoneAlertFeedFilters['source'],
          })
        }
        disabled={disabled}
        className={clsx(
          'rounded border border-gray-700 bg-gray-800 px-2 py-1 text-sm text-text-primary',
          'focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary',
          disabled && 'cursor-not-allowed opacity-50'
        )}
        aria-label="Filter by source"
      >
        <option value="all">All Sources</option>
        <option value="anomaly">Anomalies</option>
        <option value="trust_violation">Trust Violations</option>
      </select>

      {/* Acknowledged filter */}
      <select
        value={filters.acknowledged}
        onChange={(e) =>
          onFilterChange({
            ...filters,
            acknowledged: e.target.value as ZoneAlertFeedFilters['acknowledged'],
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

interface AlertCardProps {
  alert: UnifiedZoneAlert;
  zoneName?: string;
  onAcknowledge?: (alertId: string, source: AlertSource) => void;
  onClick?: (alert: UnifiedZoneAlert) => void;
  isAcknowledging?: boolean;
}

function AlertCard({ alert, zoneName, onAcknowledge, onClick, isAcknowledging }: AlertCardProps) {
  const severityConfig = ANOMALY_SEVERITY_CONFIG[alert.severity];
  const formattedTime = formatDistanceToNow(new Date(alert.timestamp), { addSuffix: true });

  const handleAcknowledge = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      e.preventDefault();
      onAcknowledge?.(alert.id, alert.source);
    },
    [alert.id, alert.source, onAcknowledge]
  );

  const handleClick = useCallback(() => {
    onClick?.(alert);
  }, [alert, onClick]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        onClick?.(alert);
      }
    },
    [alert, onClick]
  );

  return (
    // eslint-disable-next-line jsx-a11y/no-static-element-interactions -- role and tabIndex are conditionally set when interactive
    <div
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onClick={onClick ? handleClick : undefined}
      onKeyDown={onClick ? handleKeyDown : undefined}
      className={clsx(
        'rounded-lg border p-4 transition-all',
        severityConfig.bgColor,
        severityConfig.borderColor,
        alert.acknowledged && 'opacity-60',
        onClick && 'cursor-pointer hover:bg-opacity-75'
      )}
      data-testid="zone-alert-card"
      data-severity={alert.severity}
      data-source={alert.source}
      data-acknowledged={alert.acknowledged}
    >
      <div className="flex items-start gap-3">
        {/* Severity Icon */}
        <div className={clsx('mt-0.5 shrink-0 rounded-full p-1.5', severityConfig.bgColor)}>
          <SeverityIcon severity={alert.severity} className={severityConfig.color} />
        </div>

        {/* Content */}
        <div className="min-w-0 flex-1">
          {/* Title and timestamp row */}
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <h4
                className={clsx(
                  'font-medium leading-tight',
                  alert.acknowledged ? 'text-text-secondary' : 'text-text-primary'
                )}
              >
                {alert.title}
              </h4>

              {/* Zone name and type badge */}
              <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
                {zoneName && (
                  <Link
                    to={`/zones/${alert.zone_id}`}
                    className="text-primary hover:underline"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {zoneName}
                  </Link>
                )}
                <span
                  className={clsx(
                    'inline-flex items-center gap-1 rounded px-1.5 py-0.5',
                    'bg-gray-700/50 text-gray-400'
                  )}
                >
                  <SourceIcon alert={alert} />
                  {getSourceLabel(alert)}
                </span>
                <span
                  className={clsx(
                    'inline-flex items-center gap-1 rounded px-1.5 py-0.5',
                    alert.source === 'anomaly' ? 'bg-blue-500/20 text-blue-400' : 'bg-orange-500/20 text-orange-400'
                  )}
                >
                  {alert.source === 'anomaly' ? 'Anomaly' : 'Trust Violation'}
                </span>
              </div>
            </div>

            {/* Timestamp and acknowledge button */}
            <div className="flex shrink-0 items-center gap-2">
              <span className="text-xs text-text-secondary">{formattedTime}</span>

              {/* Acknowledge button */}
              {!alert.acknowledged && onAcknowledge && (
                <button
                  type="button"
                  onClick={handleAcknowledge}
                  disabled={isAcknowledging}
                  className={clsx(
                    'rounded p-1.5 transition-colors',
                    'text-gray-400 hover:bg-gray-700 hover:text-text-primary',
                    'focus:outline-none focus:ring-2 focus:ring-primary',
                    isAcknowledging && 'cursor-not-allowed opacity-50'
                  )}
                  title="Acknowledge alert"
                  aria-label="Acknowledge alert"
                >
                  <Check className="h-4 w-4" />
                </button>
              )}

              {/* Acknowledged indicator */}
              {alert.acknowledged && (
                <span
                  className="rounded bg-green-500/20 px-1.5 py-0.5 text-xs text-green-400"
                  title={`Acknowledged ${alert.acknowledged_at ? formatDistanceToNow(new Date(alert.acknowledged_at), { addSuffix: true }) : ''}`}
                >
                  Acknowledged
                </span>
              )}
            </div>
          </div>

          {/* Description */}
          {alert.description && (
            <p
              className={clsx(
                'mt-2 line-clamp-2 text-sm',
                alert.acknowledged ? 'text-gray-500' : 'text-text-secondary'
              )}
            >
              {alert.description}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

interface EmptyStateProps {
  hasFilters: boolean;
}

function EmptyState({ hasFilters }: EmptyStateProps) {
  return (
    <div
      className="flex flex-col items-center justify-center py-12 text-center"
      data-testid="alert-feed-empty"
    >
      <div className="rounded-full bg-gray-800 p-3">
        <Bell className="h-6 w-6 text-gray-500" />
      </div>
      <h3 className="mt-3 text-sm font-medium text-text-primary">No alerts found</h3>
      <p className="mt-1 text-xs text-text-secondary">
        {hasFilters
          ? 'Try adjusting your filters to see more results.'
          : 'No zone alerts detected. All zones are operating normally.'}
      </p>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="space-y-3" data-testid="alert-feed-loading">
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="h-24 animate-pulse rounded-lg border border-gray-700 bg-gray-800/50"
        />
      ))}
    </div>
  );
}

interface ErrorStateProps {
  error: Error;
  onRetry: () => void;
}

function ErrorState({ error, onRetry }: ErrorStateProps) {
  return (
    <div
      className="flex flex-col items-center justify-center rounded-lg border border-red-500/30 bg-red-500/10 py-8 text-center"
      data-testid="alert-feed-error"
    >
      <AlertTriangle className="h-6 w-6 text-red-400" />
      <h3 className="mt-2 text-sm font-medium text-red-400">Failed to load alerts</h3>
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

interface GroupHeaderProps {
  group: AlertGroup;
  onAcknowledgeGroup?: () => void;
  isAcknowledging?: boolean;
}

function GroupHeader({ group, onAcknowledgeGroup, isAcknowledging }: GroupHeaderProps) {
  return (
    <div className="sticky top-0 z-10 flex items-center justify-between bg-gray-900/95 px-2 py-2 backdrop-blur">
      <div className="flex items-center gap-2">
        <h4 className="text-sm font-medium text-text-primary">{group.label}</h4>
        {group.unacknowledgedCount > 0 && (
          <span className="rounded-full bg-red-500/20 px-2 py-0.5 text-xs text-red-400">
            {group.unacknowledgedCount} new
          </span>
        )}
      </div>
      {onAcknowledgeGroup && group.unacknowledgedCount > 0 && (
        <button
          type="button"
          onClick={onAcknowledgeGroup}
          disabled={isAcknowledging}
          className={clsx(
            'flex items-center gap-1 rounded px-2 py-1 text-xs',
            'bg-gray-700 text-gray-300 hover:bg-gray-600',
            isAcknowledging && 'cursor-not-allowed opacity-50'
          )}
        >
          <CheckCheck className="h-3 w-3" />
          Acknowledge all
        </button>
      )}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * ZoneAlertFeed displays a unified feed of zone anomaly and trust violation alerts.
 *
 * Supports grouping by zone, time, or severity, with batch acknowledge
 * functionality and optional sound notifications for critical alerts.
 *
 * @example
 * ```tsx
 * <ZoneAlertFeed
 *   zones={['zone-123']}
 *   maxAlerts={50}
 *   groupBy="severity"
 *   showAcknowledged={false}
 *   enableSound={true}
 *   onAlertClick={(alert) => router.push(`/alerts/${alert.id}`)}
 * />
 * ```
 */
function ZoneAlertFeedComponent({
  zones: filterZones,
  maxAlerts = 100,
  groupBy = 'time',
  showAcknowledged = true,
  enableSound: initialEnableSound = false,
  maxHeight = '600px',
  onAlertClick,
  className,
  hoursLookback = 24,
}: ZoneAlertFeedProps) {
  // State
  const [filters, setFilters] = useState<ZoneAlertFeedFilters>({
    severity: 'all',
    zoneId: 'all',
    acknowledged: showAcknowledged ? 'all' : 'unacknowledged',
    source: 'all',
  });
  const [soundEnabled, setSoundEnabled] = useState(initialEnableSound);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const previousCriticalCountRef = useRef(0);

  // Calculate the "since" time based on hoursLookback
  const sinceTime = useMemo(() => {
    const date = new Date();
    date.setHours(date.getHours() - hoursLookback);
    return date.toISOString();
  }, [hoursLookback]);

  // Fetch zones for filter dropdown
  const { zones: allZones } = useZonesQuery(undefined, { enabled: false });

  // Build zone name map
  const zoneNameMap = useMemo(() => {
    const map = new Map<string, string>();
    allZones.forEach((z) => map.set(z.id, z.name));
    return map;
  }, [allZones]);

  // Zone options for filter
  const zoneOptions = useMemo(() => {
    if (filterZones?.length) {
      return filterZones.map((id) => ({
        id,
        name: zoneNameMap.get(id) ?? `Zone ${id.substring(0, 8)}`,
      }));
    }
    return allZones.map((z) => ({ id: z.id, name: z.name }));
  }, [filterZones, allZones, zoneNameMap]);

  // Determine query options
  const queryZones = useMemo(() => {
    if (filters.zoneId !== 'all') {
      return [filters.zoneId];
    }
    return filterZones;
  }, [filters.zoneId, filterZones]);

  const querySeverities = useMemo((): SeverityValue[] | undefined => {
    if (filters.severity !== 'all') {
      return [filters.severity];
    }
    return undefined;
  }, [filters.severity]);

  const queryAcknowledged = useMemo(() => {
    if (filters.acknowledged === 'acknowledged') return true;
    if (filters.acknowledged === 'unacknowledged') return false;
    return undefined;
  }, [filters.acknowledged]);

  // Fetch alerts
  const {
    alerts,
    unacknowledgedCount,
    totalCount,
    isLoading,
    isFetching,
    error,
    isError,
    refetch,
    acknowledgeAlert,
    acknowledgeAll,
    acknowledgeBySeverity,
    isAcknowledging,
    isConnected,
  } = useZoneAlerts({
    zones: queryZones,
    severities: querySeverities,
    acknowledged: queryAcknowledged,
    since: sinceTime,
    limit: maxAlerts,
    enableRealtime: true,
  });

  // Filter alerts by source
  const filteredAlerts = useMemo(() => {
    if (filters.source === 'all') return alerts;
    return alerts.filter((a) => a.source === filters.source);
  }, [alerts, filters.source]);

  // Group alerts
  const groups = useMemo(
    () => groupAlerts(filteredAlerts, groupBy, zoneNameMap),
    [filteredAlerts, groupBy, zoneNameMap]
  );

  // Check if any filters are active
  const hasActiveFilters =
    filters.severity !== 'all' ||
    filters.zoneId !== 'all' ||
    filters.acknowledged !== 'all' ||
    filters.source !== 'all';

  // Handle sound for new critical alerts
  useEffect(() => {
    if (!soundEnabled) return;

    const criticalCount = alerts.filter(
      (a) => a.severity === 'critical' && !a.acknowledged
    ).length;

    // Play sound if new critical alerts appeared
    if (criticalCount > previousCriticalCountRef.current) {
      if (!audioRef.current) {
        audioRef.current = new Audio(CRITICAL_ALERT_SOUND);
      }
      audioRef.current.play().catch(() => {
        // Ignore autoplay errors
      });
    }

    previousCriticalCountRef.current = criticalCount;
  }, [alerts, soundEnabled]);

  // Handlers
  const handleFilterChange = useCallback((newFilters: ZoneAlertFeedFilters) => {
    setFilters(newFilters);
  }, []);

  const handleAcknowledge = useCallback(
    (alertId: string, source: AlertSource) => {
      void acknowledgeAlert(alertId, source);
    },
    [acknowledgeAlert]
  );

  const handleAcknowledgeAll = useCallback(() => {
    void acknowledgeAll();
  }, [acknowledgeAll]);

  const handleAcknowledgeBySeverity = useCallback(
    (severity: SeverityValue) => {
      void acknowledgeBySeverity(severity);
    },
    [acknowledgeBySeverity]
  );

  const handleRetry = useCallback(() => {
    void refetch();
  }, [refetch]);

  const toggleSound = useCallback(() => {
    setSoundEnabled((prev) => !prev);
  }, []);

  return (
    <div className={clsx('flex flex-col', className)} data-testid="zone-alert-feed">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-text-primary">Zone Alerts</h3>
          <p className="text-sm text-text-secondary">
            {unacknowledgedCount > 0 ? (
              <>
                <span className="font-medium text-red-400">{unacknowledgedCount}</span>{' '}
                unacknowledged of {totalCount} alerts
              </>
            ) : (
              <>{totalCount} alerts in the last {hoursLookback} hours</>
            )}
          </p>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {/* Sound toggle */}
          <button
            type="button"
            onClick={toggleSound}
            className={clsx(
              'flex items-center gap-1 rounded px-2 py-1 text-xs',
              soundEnabled
                ? 'bg-green-500/20 text-green-400'
                : 'bg-gray-700 text-gray-400'
            )}
            title={soundEnabled ? 'Disable alert sounds' : 'Enable alert sounds'}
            aria-label={soundEnabled ? 'Disable alert sounds' : 'Enable alert sounds'}
          >
            {soundEnabled ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
          </button>

          {/* Acknowledge all button */}
          {unacknowledgedCount > 0 && (
            <button
              type="button"
              onClick={handleAcknowledgeAll}
              disabled={isAcknowledging}
              className={clsx(
                'flex items-center gap-1 rounded px-2 py-1.5 text-xs',
                'bg-gray-700 text-gray-300 hover:bg-gray-600',
                isAcknowledging && 'cursor-not-allowed opacity-50'
              )}
              title="Acknowledge all alerts"
              aria-label="Acknowledge all alerts"
            >
              <CheckCheck className="h-4 w-4" />
              Ack All
            </button>
          )}

          {/* Loading indicator */}
          {isFetching && !isLoading && (
            <RefreshCw className="h-4 w-4 animate-spin text-primary" />
          )}

          {/* Connection status */}
          <div
            className={clsx(
              'flex items-center gap-1 rounded px-2 py-1 text-xs',
              isConnected
                ? 'bg-green-500/10 text-green-400'
                : 'bg-gray-700 text-gray-400'
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
        </div>
      </div>

      {/* Filter bar */}
      <FilterBar
        filters={filters}
        onFilterChange={handleFilterChange}
        zones={zoneOptions}
        disabled={isLoading}
      />

      {/* Severity quick filters */}
      <div className="mt-3 flex items-center gap-2">
        <span className="text-xs text-text-secondary">Quick ack:</span>
        {(['critical', 'warning', 'info'] as const).map((severity) => {
          const count = alerts.filter((a) => a.severity === severity && !a.acknowledged).length;
          if (count === 0) return null;
          const config = ANOMALY_SEVERITY_CONFIG[severity];
          return (
            <button
              key={severity}
              type="button"
              onClick={() => handleAcknowledgeBySeverity(severity)}
              disabled={isAcknowledging}
              className={clsx(
                'flex items-center gap-1 rounded px-2 py-1 text-xs',
                config.bgColor,
                config.color,
                isAcknowledging && 'cursor-not-allowed opacity-50'
              )}
            >
              <Check className="h-3 w-3" />
              {config.label} ({count})
            </button>
          );
        })}
      </div>

      {/* Content */}
      <div
        className="mt-4 overflow-y-auto"
        style={{ maxHeight: typeof maxHeight === 'number' ? `${maxHeight}px` : maxHeight }}
      >
        {isLoading ? (
          <LoadingState />
        ) : isError && error ? (
          <ErrorState error={error} onRetry={handleRetry} />
        ) : filteredAlerts.length === 0 ? (
          <EmptyState hasFilters={hasActiveFilters} />
        ) : (
          <div className="space-y-4" data-testid="alert-feed-list">
            {groups.map((group) => (
              <div key={group.key}>
                <GroupHeader
                  group={group}
                  onAcknowledgeGroup={
                    group.unacknowledgedCount > 0
                      ? () => {
                          // Acknowledge all alerts in this group
                          void Promise.all(
                            group.alerts
                              .filter((a) => !a.acknowledged)
                              .map((a) => acknowledgeAlert(a.id, a.source))
                          );
                        }
                      : undefined
                  }
                  isAcknowledging={isAcknowledging}
                />
                <div className="space-y-2 pl-2">
                  {group.alerts.map((alert) => (
                    <AlertCard
                      key={alert.id}
                      alert={alert}
                      zoneName={zoneNameMap.get(alert.zone_id)}
                      onAcknowledge={handleAcknowledge}
                      onClick={onAlertClick}
                      isAcknowledging={isAcknowledging}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Memoized ZoneAlertFeed component for performance.
 */
export const ZoneAlertFeed = memo(ZoneAlertFeedComponent);

export default ZoneAlertFeed;
