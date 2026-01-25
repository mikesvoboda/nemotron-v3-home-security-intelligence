/**
 * NotificationHistoryPanel - Display notification delivery history
 *
 * This component displays a paginated table of notification delivery history
 * with filtering capabilities by channel and success status.
 *
 * @module components/notifications/NotificationHistoryPanel
 */

import { Card, Title, Text, Badge, Select, SelectItem, Button } from '@tremor/react';
import {
  AlertCircle,
  CheckCircle,
  ChevronLeft,
  ChevronRight,
  Clock,
  Filter,
  History,
  Loader2,
  Mail,
  RefreshCw,
  Webhook,
  X,
  XCircle,
} from 'lucide-react';
import { useState, useCallback, useMemo } from 'react';

import {
  useNotificationHistoryQuery,
  type NotificationHistoryFilters,
  type NotificationChannel,
  type NotificationHistoryEntry,
} from '../../hooks/useNotificationHistoryQuery';

export interface NotificationHistoryPanelProps {
  /** Optional CSS class name */
  className?: string;
  /** Optional alert ID to filter by (for alert-specific history views) */
  alertId?: string;
  /** Number of entries per page */
  pageSize?: number;
}

/** Channel display configuration */
const CHANNEL_CONFIG: Record<NotificationChannel, { icon: typeof Mail; label: string; color: string }> = {
  email: { icon: Mail, label: 'Email', color: 'blue' },
  webhook: { icon: Webhook, label: 'Webhook', color: 'purple' },
  push: { icon: AlertCircle, label: 'Push', color: 'orange' },
};

/** Filter options for channel dropdown */
const CHANNEL_OPTIONS = [
  { value: '', label: 'All Channels' },
  { value: 'email', label: 'Email' },
  { value: 'webhook', label: 'Webhook' },
  { value: 'push', label: 'Push' },
];

/** Filter options for status dropdown */
const STATUS_OPTIONS = [
  { value: '', label: 'All Statuses' },
  { value: 'true', label: 'Success' },
  { value: 'false', label: 'Failed' },
];

/**
 * Format a timestamp for display.
 */
function formatTimestamp(timestamp: string | null): string {
  if (!timestamp) return '-';
  try {
    const date = new Date(timestamp);
    return date.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return timestamp;
  }
}

/**
 * Truncate text with ellipsis if too long.
 */
function truncateText(text: string | null, maxLength: number): string {
  if (!text) return '-';
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength - 3) + '...';
}

/**
 * NotificationHistoryPanel component displays notification delivery history
 * in a filterable, paginated table.
 *
 * Features:
 * - Paginated table of notification history entries
 * - Filter by channel (email/webhook/push)
 * - Filter by status (success/failed)
 * - Shows delivery timestamp, channel, recipient, and error details
 * - Empty state when no history exists
 * - Loading and error states
 *
 * @example
 * ```tsx
 * // Basic usage
 * <NotificationHistoryPanel />
 *
 * // With custom page size
 * <NotificationHistoryPanel pageSize={10} />
 *
 * // For a specific alert
 * <NotificationHistoryPanel alertId="alert-123" />
 * ```
 */
export default function NotificationHistoryPanel({
  className,
  alertId,
  pageSize = 10,
}: NotificationHistoryPanelProps) {
  // Filter state
  const [channelFilter, setChannelFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [currentPage, setCurrentPage] = useState(0);

  // Build filters
  const filters: NotificationHistoryFilters = useMemo(() => {
    const f: NotificationHistoryFilters = {};
    if (alertId) f.alertId = alertId;
    if (channelFilter) f.channel = channelFilter as NotificationChannel;
    if (statusFilter !== '') f.success = statusFilter === 'true';
    return f;
  }, [alertId, channelFilter, statusFilter]);

  // Fetch history
  const {
    entries,
    totalCount,
    page,
    totalPages,
    hasNextPage,
    hasPreviousPage,
    isLoading,
    isRefetching,
    error,
    refetch,
  } = useNotificationHistoryQuery({
    filters,
    limit: pageSize,
    page: currentPage,
  });

  // Handlers
  const handleChannelChange = useCallback((value: string) => {
    setChannelFilter(value);
    setCurrentPage(0); // Reset to first page on filter change
  }, []);

  const handleStatusChange = useCallback((value: string) => {
    setStatusFilter(value);
    setCurrentPage(0);
  }, []);

  const handleNextPage = useCallback(() => {
    if (hasNextPage) setCurrentPage((p) => p + 1);
  }, [hasNextPage]);

  const handlePreviousPage = useCallback(() => {
    if (hasPreviousPage) setCurrentPage((p) => p - 1);
  }, [hasPreviousPage]);

  const handleRefresh = useCallback(() => {
    void refetch();
  }, [refetch]);

  const handleClearFilters = useCallback(() => {
    setChannelFilter('');
    setStatusFilter('');
    setCurrentPage(0);
  }, []);

  const hasFilters = channelFilter !== '' || statusFilter !== '';

  return (
    <Card className={`border-gray-800 bg-[#1A1A1A] shadow-lg ${className || ''}`}>
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <Title className="flex items-center gap-2 text-white">
          <History className="h-5 w-5 text-[#76B900]" />
          Notification History
        </Title>
        <Button
          size="xs"
          onClick={handleRefresh}
          disabled={isLoading || isRefetching}
          className="bg-gray-700 text-white hover:bg-gray-600"
        >
          {isRefetching ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4" />
          )}
        </Button>
      </div>

      {/* Filters */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-gray-400" />
          <Select
            value={channelFilter}
            onValueChange={handleChannelChange}
            placeholder="All Channels"
            className="w-36"
          >
            {CHANNEL_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </Select>
        </div>

        <Select
          value={statusFilter}
          onValueChange={handleStatusChange}
          placeholder="All Statuses"
          className="w-32"
        >
          {STATUS_OPTIONS.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </Select>

        {hasFilters && (
          <button
            onClick={handleClearFilters}
            className="flex items-center gap-1 rounded-lg px-2 py-1 text-sm text-gray-400 transition-colors hover:bg-gray-800 hover:text-white"
          >
            <X className="h-3 w-3" />
            Clear
          </button>
        )}

        {totalCount > 0 && (
          <Text className="ml-auto text-sm text-gray-500">
            {totalCount} {totalCount === 1 ? 'entry' : 'entries'}
          </Text>
        )}
      </div>

      {/* Error State */}
      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <AlertCircle className="h-5 w-5 flex-shrink-0 text-red-400" />
          <Text className="text-red-400">{error.message || 'Failed to load notification history'}</Text>
        </div>
      )}

      {/* Loading State */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-[#76B900]" />
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !error && entries.length === 0 && (
        <div className="py-12 text-center">
          <History className="mx-auto mb-3 h-12 w-12 text-gray-600" />
          <Text className="text-gray-400">
            {hasFilters
              ? 'No notification history matches your filters'
              : 'No notification history yet'}
          </Text>
          <Text className="mt-1 text-sm text-gray-600">
            {hasFilters
              ? 'Try adjusting your filter criteria'
              : 'Notification delivery records will appear here'}
          </Text>
        </div>
      )}

      {/* History Table */}
      {!isLoading && entries.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-800 text-left">
                <th className="px-3 py-2 text-xs font-medium text-gray-400">Time</th>
                <th className="px-3 py-2 text-xs font-medium text-gray-400">Channel</th>
                <th className="px-3 py-2 text-xs font-medium text-gray-400">Recipient</th>
                <th className="px-3 py-2 text-xs font-medium text-gray-400">Status</th>
                <th className="px-3 py-2 text-xs font-medium text-gray-400">Error</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry: NotificationHistoryEntry) => {
                const channelConfig = CHANNEL_CONFIG[entry.channel];
                const ChannelIcon = channelConfig?.icon || AlertCircle;

                return (
                  <tr
                    key={entry.id}
                    className="border-b border-gray-800/50 transition-colors hover:bg-gray-800/30"
                  >
                    {/* Time */}
                    <td className="px-3 py-3">
                      <div className="flex items-center gap-2 text-sm text-gray-300">
                        <Clock className="h-3 w-3 text-gray-500" />
                        {formatTimestamp(entry.delivered_at || entry.created_at)}
                      </div>
                    </td>

                    {/* Channel */}
                    <td className="px-3 py-3">
                      <Badge
                        color={channelConfig?.color as 'blue' | 'purple' | 'orange' || 'gray'}
                        size="sm"
                        className="flex w-fit items-center gap-1"
                      >
                        <ChannelIcon className="h-3 w-3" />
                        {channelConfig?.label || entry.channel}
                      </Badge>
                    </td>

                    {/* Recipient */}
                    <td className="px-3 py-3">
                      <Text className="text-sm text-gray-300" title={entry.recipient || undefined}>
                        {truncateText(entry.recipient, 30)}
                      </Text>
                    </td>

                    {/* Status */}
                    <td className="px-3 py-3">
                      {entry.success ? (
                        <Badge color="green" size="sm" className="flex w-fit items-center gap-1">
                          <CheckCircle className="h-3 w-3" />
                          Success
                        </Badge>
                      ) : (
                        <Badge color="red" size="sm" className="flex w-fit items-center gap-1">
                          <XCircle className="h-3 w-3" />
                          Failed
                        </Badge>
                      )}
                    </td>

                    {/* Error */}
                    <td className="px-3 py-3">
                      {entry.error ? (
                        <Text
                          className="text-sm text-red-400"
                          title={entry.error}
                        >
                          {truncateText(entry.error, 40)}
                        </Text>
                      ) : (
                        <Text className="text-sm text-gray-600">-</Text>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {!isLoading && totalPages > 1 && (
        <div className="mt-4 flex items-center justify-between border-t border-gray-800 pt-4">
          <Text className="text-sm text-gray-500">
            Page {page + 1} of {totalPages}
          </Text>
          <div className="flex items-center gap-2">
            <Button
              size="xs"
              onClick={handlePreviousPage}
              disabled={!hasPreviousPage}
              className="bg-gray-700 text-white hover:bg-gray-600 disabled:opacity-50"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button
              size="xs"
              onClick={handleNextPage}
              disabled={!hasNextPage}
              className="bg-gray-700 text-white hover:bg-gray-600 disabled:opacity-50"
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}
