import { AlertTriangle, Bell, Loader2, RefreshCw } from 'lucide-react';
import { useCallback, useMemo, useState } from 'react';

import { useAlertsQuery, useCamerasQuery, useSnoozeEvent } from '../../hooks';
import { acknowledgeAlert, dismissAlert, isConflictError } from '../../services/alertsApi';
import { SNOOZE_OPTIONS } from '../../utils/snooze';
import { FeatureErrorBoundary } from '../common/FeatureErrorBoundary';
import SafeErrorMessage from '../common/SafeErrorMessage';
import { AlertCardSkeleton } from '../common/skeletons';


import type { AlertStatusFilter } from '../../hooks';
import type { AlertServiceResponse } from '../../services/alertsApi';

/**
 * Human-readable verdict badge for a row's verdict_source (F4.1 design):
 * "verified locally" (the local VLM), "verified in the cloud" (the cloud VLM),
 * "unverified" (the detector alone matched).
 */
function verdictBadge(verdictSource: string | null | undefined): string {
  if (verdictSource === 'local') return 'verified locally';
  if (verdictSource === 'cloud') return 'verified in the cloud';
  return 'unverified';
}

/** The rule that fired, from the pipeline's metadata payload. */
function ruleName(alert: AlertServiceResponse): string {
  const name = alert.metadata?.rule_name;
  return typeof name === 'string' ? name : 'Unmatched alert';
}

/** The recognised subject line, from the pipeline's metadata payload. The
 * pipeline writes `recognised` as a LIST of subject strings (pipeline.py), so
 * accept both a bare string and a list — a string-only read would silently
 * never render for real pipeline rows. */
function recognisedLine(alert: AlertServiceResponse): string | null {
  const recognised = alert.metadata?.recognised;
  if (typeof recognised === 'string' && recognised.length > 0) return recognised;
  if (Array.isArray(recognised)) {
    const names = recognised.filter((n): n is string => typeof n === 'string' && n.length > 0);
    return names.length > 0 ? names.join(', ') : null;
  }
  return null;
}

/** Short user-facing timestamp (household wall clock). */
function formatTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export interface AlertsPageProps {
  onViewEventDetails?: (eventId: number) => void;
  className?: string;
}

/**
 * AlertsPage — the F4.1 Alerts page over alert rows.
 *
 * Reads `GET /api/alert-service/alerts` (the alerts table B4.1's pipeline
 * writes) instead of the events feed this page used before F4.1. Open alerts
 * by default, or all. Each row: rule, severity, camera, verdict badge
 * (verified locally / verified in the cloud / unverified), who was recognised,
 * first and last seen, match count, who was told. Actions: Acknowledge,
 * Dismiss, Snooze (15 min, 1 h, 4 h, until tomorrow), Open event. Live through
 * the existing `useAlertWebSocket`, which invalidates `alertsQueryKeys.all` on
 * every alert frame.
 */
export default function AlertsPage({ onViewEventDetails, className = '' }: AlertsPageProps) {
  // Open alerts by default, or all (the page's single status toggle).
  const [statusFilter, setStatusFilter] = useState<AlertStatusFilter>('open');
  const [busyAlertId, setBusyAlertId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Fetch cameras for camera name lookup.
  const { cameras } = useCamerasQuery();

  // Snooze rides the alert's triggering event (the backend syncs event
  // snooze_until into activity snoozes; see _sync_event_activity_snooze).
  const { snooze } = useSnoozeEvent();

  const { alerts, totalCount, isLoading, error, isError, refetch } = useAlertsQuery({
    statusFilter,
    limit: 50,
  });

  // Camera name lookup.
  const cameraNameMap = useMemo(() => {
    const map = new Map<string, string>();
    cameras.forEach((camera) => {
      map.set(camera.id, camera.name);
    });
    return map;
  }, [cameras]);

  // Run the alert action, then refetch; the acknowledge/dismiss frames also
  // land through useAlertWebSocket's alertsQueryKeys.all invalidation.
  const runAction = useCallback(
    async (alertId: string, action: (id: string) => Promise<unknown>) => {
      setBusyAlertId(alertId);
      setActionError(null);
      try {
        await action(alertId);
        void refetch();
      } catch (err) {
        if (isConflictError(err)) {
          setActionError('This alert was changed elsewhere. The list will refresh.');
          void refetch();
        } else {
          setActionError(err instanceof Error ? err.message : 'Action failed');
        }
      } finally {
        setBusyAlertId(null);
      }
    },
    [refetch]
  );

  const handleAcknowledge = useCallback(
    (alert: AlertServiceResponse) => void runAction(alert.id, acknowledgeAlert),
    [runAction]
  );
  const handleDismiss = useCallback(
    (alert: AlertServiceResponse) => void runAction(alert.id, dismissAlert),
    [runAction]
  );

  const handleSnooze = useCallback(
    (alert: AlertServiceResponse, seconds: number) => {
      void snooze(alert.event_id, seconds);
    },
    [snooze]
  );

  const handleOpenEvent = useCallback(
    (alert: AlertServiceResponse) => {
      if (onViewEventDetails) onViewEventDetails(alert.event_id);
    },
    [onViewEventDetails]
  );

  const handleRefresh = () => {
    void refetch();
  };

  return (
    <div data-testid="alerts-page" className={`flex flex-col ${className}`}>
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3">
          <AlertTriangle className="h-8 w-8 text-orange-500" />
          <h1 className="text-3xl font-bold text-white">Alerts</h1>
        </div>
        <p className="mt-2 text-gray-400">What the household was alerted about</p>
      </div>

      {/* Filter and refresh bar */}
      <div className="mb-6 flex flex-col gap-4 rounded-lg border border-gray-800 bg-[#1F1F1F] p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <label htmlFor="status-filter" className="text-sm font-medium text-gray-300">
            Show:
          </label>
          <select
            id="status-filter"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as AlertStatusFilter)}
            className="rounded-md border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
          >
            <option value="open">Open alerts</option>
            <option value="all">All alerts</option>
          </select>
        </div>

        <button
          onClick={handleRefresh}
          aria-label="Refresh alerts"
          className="flex items-center gap-2 rounded-md bg-[#76B900]/10 px-4 py-2 text-sm font-medium text-[#76B900] transition-colors hover:bg-[#76B900]/20"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      </div>

      {/* Action error (conflict / failure banner) */}
      {actionError && (
        <div
          className="mb-4 rounded-lg border border-yellow-700/50 bg-yellow-950/20 px-4 py-3 text-sm text-yellow-300"
          data-testid="alerts-action-error"
        >
          {actionError}
        </div>
      )}

      {/* Results summary */}
      <div className="mb-4">
        <p className="text-sm text-gray-400">
          {isLoading ? 'Loading...' : `${totalCount} alert${totalCount !== 1 ? 's' : ''} found`}
        </p>
      </div>

      {/* Alert rows */}
      {isLoading ? (
        <div className="space-y-4">
          {Array.from({ length: 6 }, (_, i) => (
            <AlertCardSkeleton key={i} />
          ))}
        </div>
      ) : isError ? (
        <div className="flex min-h-[400px] items-center justify-center rounded-lg border border-red-900/50 bg-red-950/20">
          <div className="text-center">
            <p className="mb-2 text-lg font-semibold text-red-400">Error Loading Alerts</p>
            <SafeErrorMessage
              message={error?.message || 'An error occurred'}
              size="sm"
              color="gray"
            />
          </div>
        </div>
      ) : alerts.length === 0 ? (
        <div className="flex min-h-[400px] items-center justify-center rounded-lg border border-gray-800 bg-[#1F1F1F]">
          <div className="text-center">
            <Bell className="mx-auto mb-4 h-16 w-16 text-gray-600" />
            <p className="mb-2 text-lg font-semibold text-gray-300">No Alerts at This Time</p>
            <p className="text-sm text-gray-500">
              {statusFilter === 'open'
                ? 'There are no open alerts. Keep up the good work!'
                : 'There are no alerts to show.'}
            </p>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-4" data-testid="alerts-rows">
          {alerts.map((alert) => {
            const cameraName = alert.camera_id
              ? (cameraNameMap.get(alert.camera_id) ?? alert.camera_id)
              : 'Unknown camera';
            const busy = busyAlertId === alert.id;
            return (
              <div
                key={alert.id}
                data-testid="alert-row"
                className="rounded-lg border border-gray-800 bg-[#1F1F1F] p-4"
              >
                {/* Row header: rule + severity + verdict badge */}
                <div className="flex flex-wrap items-center gap-3">
                  <span className="text-base font-semibold text-white">{ruleName(alert)}</span>
                  <span
                    data-testid={`alert-severity-${alert.severity}`}
                    className="rounded-full border border-gray-700 px-2 py-0.5 text-xs font-medium uppercase text-gray-300"
                  >
                    {alert.severity}
                  </span>
                  <span className="rounded-full bg-[#76B900]/10 px-2 py-0.5 text-xs text-[#76B900]">
                    {verdictBadge(alert.verdict_source)}
                  </span>
                </div>

                {/* Row body: camera, recognised, first/last seen, matches, told */}
                <div className="mt-3 grid grid-cols-1 gap-2 text-sm text-gray-400 sm:grid-cols-2">
                  <div>
                    Camera: <span className="text-gray-200">{cameraName}</span>
                  </div>
                  <div>
                    First seen:{' '}
                    <span className="text-gray-200">{formatTime(alert.created_at)}</span>
                  </div>
                  <div>
                    Last seen:{' '}
                    <span className="text-gray-200">{formatTime(alert.last_seen_at)}</span>
                  </div>
                  <div>
                    Matches: <span className="text-gray-200">{alert.match_count ?? 1}</span>
                  </div>
                  {recognisedLine(alert) && (
                    <div className="sm:col-span-2">
                      Recognised: <span className="text-gray-200">{recognisedLine(alert)}</span>
                    </div>
                  )}
                  <div className="sm:col-span-2">
                    Who was told:{' '}
                    <span className="text-gray-200">
                      {alert.channels && alert.channels.length > 0
                        ? alert.channels.join(', ')
                        : 'nobody yet'}
                    </span>
                  </div>
                </div>

                {/* Actions */}
                <div className="mt-4 flex flex-wrap items-center gap-2">
                  <button
                    onClick={() => handleAcknowledge(alert)}
                    disabled={busy}
                    className="rounded-md bg-[#76B900]/10 px-3 py-1.5 text-sm font-medium text-[#76B900] transition-colors hover:bg-[#76B900]/20 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {busy ? <Loader2 className="inline h-4 w-4 animate-spin" /> : null} Acknowledge
                  </button>
                  <button
                    onClick={() => handleDismiss(alert)}
                    disabled={busy}
                    className="rounded-md border border-gray-700 px-3 py-1.5 text-sm font-medium text-gray-300 transition-colors hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Dismiss
                  </button>
                  <select
                    aria-label={`Snooze alert ${alert.id}`}
                    value=""
                    onChange={(e) => {
                      const seconds = Number(e.target.value);
                      if (seconds > 0) handleSnooze(alert, seconds);
                    }}
                    className="rounded-md border border-gray-700 bg-[#1A1A1A] px-3 py-1.5 text-sm text-gray-300"
                  >
                    <option value="">Snooze…</option>
                    {SNOOZE_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={() => handleOpenEvent(alert)}
                    disabled={!onViewEventDetails}
                    className="ml-auto rounded-md border border-gray-700 px-3 py-1.5 text-sm font-medium text-gray-300 transition-colors hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Open event
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/**
 * AlertsPage with FeatureErrorBoundary wrapper.
 *
 * Wraps the AlertsPage component in a FeatureErrorBoundary to prevent
 * errors in the Alerts page from crashing the entire application.
 * Other parts of the dashboard will continue to work if this page errors.
 */
function AlertsPageWithErrorBoundary(props: AlertsPageProps) {
  return (
    <FeatureErrorBoundary
      feature="Alerts"
      fallback={
        <div className="flex min-h-[400px] flex-col items-center justify-center rounded-lg border border-red-500/30 bg-red-900/20 p-8 text-center">
          <AlertTriangle className="mb-4 h-12 w-12 text-red-400" />
          <h3 className="mb-2 text-lg font-semibold text-red-400">Alerts Unavailable</h3>
          <p className="max-w-md text-sm text-gray-400">
            Unable to load alerts. Please refresh the page or try again later. Other parts of the
            application should still work.
          </p>
        </div>
      }
    >
      <AlertsPage {...props} />
    </FeatureErrorBoundary>
  );
}

export { AlertsPageWithErrorBoundary };
