/**
 * AlertDrawer - Slide-out drawer showing active Prometheus alerts
 *
 * Displays a list of infrastructure alerts grouped by severity (critical first).
 * Shows alertname, summary, description, and timestamp for each alert.
 *
 * NEM-3123: Phase 3.2 - Prometheus alert UI components
 *
 * @example
 * ```tsx
 * <AlertDrawer
 *   isOpen={isDrawerOpen}
 *   onClose={() => setIsDrawerOpen(false)}
 *   alerts={alerts}
 *   alertsBySeverity={alertsBySeverity}
 * />
 * ```
 */

import { Dialog, Transition } from '@headlessui/react';
import { clsx } from 'clsx';
import { formatDistanceToNow } from 'date-fns';
import { AlertOctagon, AlertTriangle, Info, X, Clock, CheckCircle2 } from 'lucide-react';
import { Fragment, useMemo } from 'react';

import IconButton from './IconButton';

import type { PrometheusAlert } from '../../hooks/usePrometheusAlerts';
import type { PrometheusAlertSeverity } from '../../types/websocket-events';

// ============================================================================
// Types
// ============================================================================

export interface AlertDrawerProps {
  /** Whether the drawer is open */
  isOpen: boolean;

  /** Called when the drawer should close */
  onClose: () => void;

  /** All active alerts */
  alerts: PrometheusAlert[];

  /** Alerts grouped by severity */
  alertsBySeverity: {
    critical: PrometheusAlert[];
    warning: PrometheusAlert[];
    info: PrometheusAlert[];
  };

  /** Optional: resolved alerts to show with "Resolved" badge */
  resolvedAlerts?: PrometheusAlert[];

  /** Additional CSS classes for the drawer panel */
  className?: string;
}

// ============================================================================
// Helper Components
// ============================================================================

interface SeverityHeaderProps {
  severity: PrometheusAlertSeverity;
  count: number;
}

/**
 * Section header for a severity group
 */
function SeverityHeader({ severity, count }: SeverityHeaderProps) {
  const config = {
    critical: {
      icon: AlertOctagon,
      label: 'CRITICAL',
      colorClass: 'text-risk-critical',
      bgClass: 'bg-risk-critical/10',
    },
    warning: {
      icon: AlertTriangle,
      label: 'WARNING',
      colorClass: 'text-risk-medium',
      bgClass: 'bg-risk-medium/10',
    },
    info: {
      icon: Info,
      label: 'INFO',
      colorClass: 'text-nvidia-blue',
      bgClass: 'bg-nvidia-blue/10',
    },
  }[severity];

  const Icon = config.icon;

  return (
    <div
      className={clsx(
        'flex items-center gap-2 px-4 py-2 text-sm font-semibold uppercase tracking-wide',
        config.bgClass,
        config.colorClass
      )}
      data-testid={`alert-drawer-severity-header-${severity}`}
    >
      <Icon className="h-4 w-4" />
      <span>{config.label}</span>
      <span className="bg-nvidia-surface ml-auto rounded-full px-2 py-0.5 text-xs font-medium">
        {count}
      </span>
    </div>
  );
}

interface AlertCardProps {
  alert: PrometheusAlert;
  isResolved?: boolean;
}

/**
 * Card displaying a single alert
 */
function AlertCard({ alert, isResolved = false }: AlertCardProps) {
  const timeAgo = useMemo(() => {
    try {
      return formatDistanceToNow(new Date(alert.startsAt), { addSuffix: true });
    } catch {
      return 'Unknown time';
    }
  }, [alert.startsAt]);

  // Extract summary and description from annotations
  const summary = alert.annotations.summary || alert.alertname;
  const description = alert.annotations.description || '';

  return (
    <div
      className={clsx(
        'mx-4 my-2 rounded-lg border p-4',
        'bg-nvidia-surface border-nvidia-border',
        'transition-colors duration-150',
        'hover:border-nvidia-border-light',
        isResolved && 'opacity-60'
      )}
      data-testid="alert-drawer-card"
      data-alert-fingerprint={alert.fingerprint}
    >
      {/* Header with alertname and resolved badge */}
      <div className="flex items-start justify-between gap-2">
        <h4
          className="text-nvidia-text-primary text-sm font-semibold"
          data-testid="alert-card-name"
        >
          {alert.alertname}
        </h4>
        {isResolved && (
          <span
            className={clsx(
              'inline-flex items-center gap-1 rounded-full px-2 py-0.5',
              'bg-risk-low/20 text-xs font-medium text-risk-low'
            )}
            data-testid="alert-card-resolved-badge"
          >
            <CheckCircle2 className="h-3 w-3" />
            Resolved
          </span>
        )}
      </div>

      {/* Summary */}
      <p className="text-nvidia-text-secondary mt-1 text-sm" data-testid="alert-card-summary">
        {summary}
      </p>

      {/* Description (if different from summary) */}
      {description && description !== summary && (
        <p className="text-nvidia-text-muted mt-1 text-xs" data-testid="alert-card-description">
          {description}
        </p>
      )}

      {/* Timestamp */}
      <div className="text-nvidia-text-muted mt-2 flex items-center gap-1 text-xs">
        <Clock className="h-3 w-3" />
        <span data-testid="alert-card-timestamp">{timeAgo}</span>
      </div>

      {/* Labels (optional, show key ones) */}
      {alert.labels.instance && (
        <div className="mt-2 flex flex-wrap gap-1">
          <span className="bg-nvidia-surface-light text-nvidia-text-muted rounded px-1.5 py-0.5 text-[10px]">
            {alert.labels.instance}
          </span>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * AlertDrawer displays a slide-out panel with all active Prometheus alerts.
 *
 * Alerts are grouped by severity (critical first, then warning, then info).
 * Each alert shows its name, summary, description, and when it started.
 */
export default function AlertDrawer({
  isOpen,
  onClose,
  alerts,
  alertsBySeverity,
  resolvedAlerts = [],
  className,
}: AlertDrawerProps) {
  const { critical, warning, info } = alertsBySeverity;
  const hasAlerts = alerts.length > 0;
  const hasResolved = resolvedAlerts.length > 0;

  return (
    <Transition show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={onClose} data-testid="alert-drawer">
        {/* Backdrop */}
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div
            className="fixed inset-0 bg-black/50"
            aria-hidden="true"
            data-testid="alert-drawer-backdrop"
          />
        </Transition.Child>

        {/* Drawer panel - slides from right */}
        <div className="fixed inset-0 overflow-hidden">
          <div className="absolute inset-0 overflow-hidden">
            <div className="pointer-events-none fixed inset-y-0 right-0 flex max-w-full pl-10">
              <Transition.Child
                as={Fragment}
                enter="transform transition ease-in-out duration-300"
                enterFrom="translate-x-full"
                enterTo="translate-x-0"
                leave="transform transition ease-in-out duration-200"
                leaveFrom="translate-x-0"
                leaveTo="translate-x-full"
              >
                <Dialog.Panel
                  className={clsx(
                    'pointer-events-auto w-screen max-w-md',
                    'bg-nvidia-bg border-nvidia-border border-l',
                    'flex h-full flex-col',
                    className
                  )}
                  data-testid="alert-drawer-panel"
                >
                  {/* Header */}
                  <div className="border-nvidia-border flex items-center justify-between border-b px-4 py-4">
                    <Dialog.Title
                      className="text-nvidia-text-primary text-lg font-semibold"
                      data-testid="alert-drawer-title"
                    >
                      Active Alerts
                    </Dialog.Title>
                    <IconButton
                      icon={<X />}
                      aria-label="Close alert drawer"
                      onClick={onClose}
                      variant="ghost"
                      size="sm"
                      data-testid="alert-drawer-close"
                    />
                  </div>

                  {/* Content - scrollable */}
                  <div className="flex-1 overflow-y-auto pb-4">
                    {hasAlerts ? (
                      <>
                        {/* Critical alerts */}
                        {critical.length > 0 && (
                          <div data-testid="alert-drawer-critical-section">
                            <SeverityHeader severity="critical" count={critical.length} />
                            {critical.map((alert) => (
                              <AlertCard key={alert.fingerprint} alert={alert} />
                            ))}
                          </div>
                        )}

                        {/* Warning alerts */}
                        {warning.length > 0 && (
                          <div data-testid="alert-drawer-warning-section">
                            <SeverityHeader severity="warning" count={warning.length} />
                            {warning.map((alert) => (
                              <AlertCard key={alert.fingerprint} alert={alert} />
                            ))}
                          </div>
                        )}

                        {/* Info alerts */}
                        {info.length > 0 && (
                          <div data-testid="alert-drawer-info-section">
                            <SeverityHeader severity="info" count={info.length} />
                            {info.map((alert) => (
                              <AlertCard key={alert.fingerprint} alert={alert} />
                            ))}
                          </div>
                        )}

                        {/* Resolved alerts (if any) */}
                        {hasResolved && (
                          <div className="mt-4" data-testid="alert-drawer-resolved-section">
                            <div className="text-nvidia-text-muted bg-nvidia-surface flex items-center gap-2 px-4 py-2 text-sm font-semibold uppercase tracking-wide">
                              <CheckCircle2 className="h-4 w-4" />
                              <span>Recently Resolved</span>
                              <span className="bg-nvidia-surface-light ml-auto rounded-full px-2 py-0.5 text-xs font-medium">
                                {resolvedAlerts.length}
                              </span>
                            </div>
                            {resolvedAlerts.map((alert) => (
                              <AlertCard key={alert.fingerprint} alert={alert} isResolved />
                            ))}
                          </div>
                        )}
                      </>
                    ) : (
                      /* Empty state */
                      <div
                        className="flex flex-col items-center justify-center py-16 text-center"
                        data-testid="alert-drawer-empty"
                      >
                        <CheckCircle2 className="mb-4 h-12 w-12 text-risk-low" />
                        <h3 className="text-nvidia-text-primary text-lg font-medium">
                          No Active Alerts
                        </h3>
                        <p className="text-nvidia-text-muted mt-1 text-sm">
                          All systems are operating normally.
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Footer with alert count */}
                  {hasAlerts && (
                    <div className="border-nvidia-border text-nvidia-text-muted border-t px-4 py-3 text-sm">
                      {alerts.length} active alert{alerts.length !== 1 ? 's' : ''}
                    </div>
                  )}
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
}
