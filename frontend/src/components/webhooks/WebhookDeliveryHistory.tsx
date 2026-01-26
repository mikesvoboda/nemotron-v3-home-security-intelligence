/**
 * WebhookDeliveryHistory - Delivery log table for a webhook
 *
 * Displays delivery attempts with:
 * - Time, Event Type, Status columns
 * - Response Code, Duration
 * - Retry button for failed deliveries
 * - Pagination
 *
 * @module components/webhooks/WebhookDeliveryHistory
 * @see NEM-3624 - Webhook Management Feature
 */

import { clsx } from 'clsx';
import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  Loader2,
  RefreshCw,
  XCircle,
} from 'lucide-react';

import { WEBHOOK_EVENT_LABELS, DELIVERY_STATUS_LABELS } from '../../types/webhook';
import Button from '../common/Button';
import EmptyState from '../common/EmptyState';

import type { WebhookDelivery, WebhookDeliveryStatus } from '../../types/webhook';

// ============================================================================
// Types
// ============================================================================

export interface WebhookDeliveryHistoryProps {
  /** Webhook name for display */
  webhookName: string;
  /** Deliveries to display */
  deliveries: WebhookDelivery[];
  /** Total count for pagination */
  total: number;
  /** Whether there are more deliveries */
  hasMore: boolean;
  /** Current page (0-indexed) */
  page: number;
  /** Items per page */
  pageSize: number;
  /** Loading state */
  isLoading?: boolean;
  /** Refetching state */
  isRefetching?: boolean;
  /** Handler for page change */
  onPageChange: (page: number) => void;
  /** Handler for retry */
  onRetry: (deliveryId: string) => void;
  /** Handler for refresh */
  onRefresh: () => void;
  /** ID of delivery being retried */
  retryingId?: string | null;
  /** Close handler */
  onClose?: () => void;
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Format timestamp for display
 */
function formatTimestamp(isoString: string): { date: string; time: string } {
  const date = new Date(isoString);
  return {
    date: date.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
    }),
    time: date.toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    }),
  };
}

/**
 * Get status icon and color
 */
function getStatusDisplay(status: WebhookDeliveryStatus): {
  icon: React.ComponentType<{ className?: string }>;
  colorClass: string;
  bgClass: string;
} {
  switch (status) {
    case 'success':
      return {
        icon: CheckCircle2,
        colorClass: 'text-green-400',
        bgClass: 'bg-green-500/10',
      };
    case 'failed':
      return {
        icon: XCircle,
        colorClass: 'text-red-400',
        bgClass: 'bg-red-500/10',
      };
    case 'retrying':
      return {
        icon: RefreshCw,
        colorClass: 'text-yellow-400',
        bgClass: 'bg-yellow-500/10',
      };
    case 'pending':
    default:
      return {
        icon: Clock,
        colorClass: 'text-gray-400',
        bgClass: 'bg-gray-500/10',
      };
  }
}

/**
 * Format response time for display
 */
function formatResponseTime(ms: number | null): string {
  if (ms === null) return '-';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

// ============================================================================
// Sub-components
// ============================================================================

/**
 * Loading skeleton
 */
function TableSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="mb-4 h-10 rounded bg-gray-700" />
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="mb-2 h-14 rounded bg-gray-800" />
      ))}
    </div>
  );
}

/**
 * Status badge component
 */
function StatusBadge({ status }: { status: WebhookDeliveryStatus }) {
  const { icon: Icon, colorClass, bgClass } = getStatusDisplay(status);

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium',
        colorClass,
        bgClass
      )}
    >
      <Icon className="h-3.5 w-3.5" />
      {DELIVERY_STATUS_LABELS[status]}
    </span>
  );
}

/**
 * HTTP status code badge
 */
function HttpStatusBadge({ code }: { code: number | null }) {
  if (code === null) {
    return <span className="text-sm text-gray-500">-</span>;
  }

  const isSuccess = code >= 200 && code < 300;
  const isClientError = code >= 400 && code < 500;
  const isServerError = code >= 500;

  const colorClass = isSuccess
    ? 'text-green-400 bg-green-500/10'
    : isClientError
      ? 'text-yellow-400 bg-yellow-500/10'
      : isServerError
        ? 'text-red-400 bg-red-500/10'
        : 'text-gray-400 bg-gray-500/10';

  return (
    <span className={clsx('rounded px-2 py-0.5 text-xs font-mono font-medium', colorClass)}>
      {code}
    </span>
  );
}

/**
 * Delivery row component
 */
function DeliveryRow({
  delivery,
  onRetry,
  isRetrying,
}: {
  delivery: WebhookDelivery;
  onRetry: () => void;
  isRetrying: boolean;
}) {
  const { date, time } = formatTimestamp(delivery.created_at);
  const canRetry = delivery.status === 'failed';

  return (
    <tr className="border-b border-gray-800 transition-colors hover:bg-gray-800/50">
      {/* Time */}
      <td className="px-4 py-3">
        <div className="text-sm">
          <p className="font-medium text-white">{time}</p>
          <p className="text-xs text-gray-500">{date}</p>
        </div>
      </td>

      {/* Event Type */}
      <td className="px-4 py-3">
        <span className="rounded bg-gray-700 px-2 py-0.5 text-xs text-gray-300">
          {WEBHOOK_EVENT_LABELS[delivery.event_type]}
        </span>
      </td>

      {/* Status */}
      <td className="px-4 py-3">
        <StatusBadge status={delivery.status} />
      </td>

      {/* Response Code */}
      <td className="px-4 py-3">
        <HttpStatusBadge code={delivery.status_code} />
      </td>

      {/* Duration */}
      <td className="px-4 py-3">
        <span className="text-sm text-gray-400">
          {formatResponseTime(delivery.response_time_ms)}
        </span>
      </td>

      {/* Attempts */}
      <td className="px-4 py-3">
        <span className="text-sm text-gray-400">{delivery.attempt_count}</span>
      </td>

      {/* Error / Retry */}
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          {delivery.error_message && (
            <span
              className="max-w-[200px] truncate text-xs text-red-400"
              title={delivery.error_message}
            >
              {delivery.error_message}
            </span>
          )}
          {canRetry && (
            <button
              type="button"
              onClick={onRetry}
              disabled={isRetrying}
              className={clsx(
                'rounded p-1.5 text-gray-400 transition-colors hover:bg-gray-700 hover:text-[#76B900]',
                isRetrying && 'cursor-wait opacity-50'
              )}
              title="Retry delivery"
              aria-label="Retry delivery"
            >
              {isRetrying ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}

/**
 * Pagination controls
 */
function Pagination({
  page,
  pageSize,
  total,
  hasMore,
  onPageChange,
  isLoading,
}: {
  page: number;
  pageSize: number;
  total: number;
  hasMore: boolean;
  onPageChange: (page: number) => void;
  isLoading: boolean;
}) {
  const totalPages = Math.ceil(total / pageSize);
  // Use Math.min to handle empty state (total=0) correctly - prevents "1-0 of 0"
  const startItem = Math.min(page * pageSize + 1, total);
  const endItem = Math.min((page + 1) * pageSize, total);

  return (
    <div className="flex items-center justify-between border-t border-gray-800 px-4 py-3">
      <p className="text-sm text-gray-400">
        Showing {startItem}-{endItem} of {total} deliveries
      </p>

      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          leftIcon={<ChevronLeft className="h-4 w-4" />}
          onClick={() => onPageChange(page - 1)}
          disabled={page === 0 || isLoading}
        >
          Previous
        </Button>

        <span className="text-sm text-gray-400">
          Page {page + 1} of {totalPages}
        </span>

        <Button
          variant="outline"
          size="sm"
          rightIcon={<ChevronRight className="h-4 w-4" />}
          onClick={() => onPageChange(page + 1)}
          disabled={!hasMore || isLoading}
        >
          Next
        </Button>
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * WebhookDeliveryHistory displays the delivery log for a webhook
 */
export default function WebhookDeliveryHistory({
  webhookName,
  deliveries,
  total,
  hasMore,
  page,
  pageSize,
  isLoading = false,
  isRefetching = false,
  onPageChange,
  onRetry,
  onRefresh,
  retryingId = null,
  onClose,
  className = '',
}: WebhookDeliveryHistoryProps) {
  return (
    <div
      className={clsx('rounded-lg border border-gray-800 bg-[#1F1F1F]', className)}
      data-testid="webhook-delivery-history"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-800 px-4 py-3">
        <div>
          <h3 className="text-lg font-semibold text-white">Delivery History</h3>
          <p className="text-sm text-gray-500">{webhookName}</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            leftIcon={
              isRefetching ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )
            }
            onClick={onRefresh}
            disabled={isRefetching}
          >
            Refresh
          </Button>
          {onClose && (
            <Button variant="ghost" size="sm" onClick={onClose}>
              Close
            </Button>
          )}
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="p-4">
          <TableSkeleton />
        </div>
      ) : deliveries.length === 0 ? (
        <EmptyState
          icon={Clock}
          title="No Deliveries Yet"
          description="Delivery attempts will appear here when events are sent to this webhook."
          variant="muted"
          size="sm"
        />
      ) : (
        <>
          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full min-w-[700px]">
              <thead>
                <tr className="border-b border-gray-700 bg-[#1A1A1A]">
                  <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-400">
                    Time
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-400">
                    Event
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-400">
                    Status
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-400">
                    Response
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-400">
                    Duration
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-400">
                    Attempts
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-400">
                    Error / Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {deliveries.map((delivery) => (
                  <DeliveryRow
                    key={delivery.id}
                    delivery={delivery}
                    onRetry={() => onRetry(delivery.id)}
                    isRetrying={retryingId === delivery.id}
                  />
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {total > pageSize && (
            <Pagination
              page={page}
              pageSize={pageSize}
              total={total}
              hasMore={hasMore}
              onPageChange={onPageChange}
              isLoading={isRefetching}
            />
          )}
        </>
      )}
    </div>
  );
}
