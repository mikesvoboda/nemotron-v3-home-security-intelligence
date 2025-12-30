import { Card, Title, Text, Badge, Button, ProgressBar } from '@tremor/react';
import { clsx } from 'clsx';
import {
  Trash2,
  Clock,
  Calendar,
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Image,
  PlayCircle,
} from 'lucide-react';
import { useEffect, useState, useCallback } from 'react';

import { fetchCleanupStatus, type CleanupStatusResponse } from '../../services/api';

/**
 * Props for CleanupStatusCard component
 */
export interface CleanupStatusCardProps {
  /** Polling interval in milliseconds (default: 60000) */
  pollingInterval?: number;
  /** Optional callback when cleanup status changes */
  onStatusChange?: (status: CleanupStatusResponse) => void;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Format a time string to human-readable format
 */
function formatTime(time: string): string {
  const [hours, minutes] = time.split(':');
  const hour = parseInt(hours, 10);
  const ampm = hour >= 12 ? 'PM' : 'AM';
  const displayHour = hour % 12 || 12;
  return `${displayHour}:${minutes} ${ampm}`;
}

/**
 * Calculate time remaining until next cleanup
 */
function getTimeUntilCleanup(nextCleanup: string | null): string {
  if (!nextCleanup) return 'Not scheduled';

  const next = new Date(nextCleanup);
  const now = new Date();
  const diff = next.getTime() - now.getTime();

  if (diff <= 0) return 'Running soon';

  const hours = Math.floor(diff / (1000 * 60 * 60));
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

  if (hours > 24) {
    const days = Math.floor(hours / 24);
    return `${days}d ${hours % 24}h`;
  }

  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }

  return `${minutes}m`;
}

/**
 * Format next cleanup date
 */
function formatNextCleanup(nextCleanup: string | null): string {
  if (!nextCleanup) return 'Not scheduled';

  const date = new Date(nextCleanup);
  const today = new Date();
  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);

  const isToday = date.toDateString() === today.toDateString();
  const isTomorrow = date.toDateString() === tomorrow.toDateString();

  const timeStr = date.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });

  if (isToday) return `Today at ${timeStr}`;
  if (isTomorrow) return `Tomorrow at ${timeStr}`;

  return date.toLocaleString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

/**
 * Calculate progress to next cleanup (for visual indicator)
 */
function getCleanupProgress(nextCleanup: string | null): number {
  if (!nextCleanup) return 0;

  const next = new Date(nextCleanup);
  const now = new Date();

  // Assume cleanup runs daily at the same time
  // Calculate how much of the 24-hour cycle has passed
  const oneDay = 24 * 60 * 60 * 1000;
  const timeToNext = next.getTime() - now.getTime();

  if (timeToNext <= 0) return 100;
  if (timeToNext >= oneDay) return 0;

  return Math.round(((oneDay - timeToNext) / oneDay) * 100);
}

/**
 * CleanupStatusCard - Displays the status of the cleanup service
 *
 * Shows:
 * - Cleanup service running status
 * - Retention policy (days)
 * - Scheduled cleanup time
 * - Time until next cleanup
 * - Whether original images are deleted
 *
 * Fetches data from GET /api/system/cleanup/status endpoint.
 */
export default function CleanupStatusCard({
  pollingInterval = 60000,
  onStatusChange,
  className,
}: CleanupStatusCardProps) {
  const [status, setStatus] = useState<CleanupStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetchCleanupStatus();
      setStatus(response);
      setLastUpdated(new Date(response.timestamp));
      setError(null);
      onStatusChange?.(response);
    } catch (err) {
      console.error('Failed to fetch cleanup status:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch cleanup status');
    } finally {
      setLoading(false);
    }
  }, [onStatusChange]);

  // Initial fetch
  useEffect(() => {
    void fetchStatus();
  }, [fetchStatus]);

  // Polling
  useEffect(() => {
    const interval = setInterval(() => {
      void fetchStatus();
    }, pollingInterval);

    return () => clearInterval(interval);
  }, [pollingInterval, fetchStatus]);

  // Update countdown every minute
  const [, forceUpdate] = useState({});
  useEffect(() => {
    const interval = setInterval(() => {
      forceUpdate({});
    }, 60000);
    return () => clearInterval(interval);
  }, []);

  // Loading state
  if (loading && !status) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid="cleanup-status-card-loading"
      >
        <Title className="mb-4 flex items-center gap-2 text-white">
          <Trash2 className="h-5 w-5 text-[#76B900]" />
          Cleanup Service
        </Title>
        <div className="space-y-3">
          <div className="h-6 animate-pulse rounded bg-gray-800"></div>
          <div className="h-6 animate-pulse rounded bg-gray-800"></div>
          <div className="h-16 animate-pulse rounded bg-gray-800"></div>
        </div>
      </Card>
    );
  }

  // Error state (without cached data)
  if (error && !status) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid="cleanup-status-card-error"
      >
        <Title className="mb-4 flex items-center gap-2 text-white">
          <Trash2 className="h-5 w-5 text-[#76B900]" />
          Cleanup Service
        </Title>
        <div className="flex items-center gap-3 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <AlertTriangle className="h-5 w-5 text-red-500" />
          <div>
            <Text className="text-sm font-medium text-red-400">Failed to load cleanup status</Text>
            <Text className="text-xs text-gray-400">{error}</Text>
          </div>
          <Button
            size="xs"
            variant="secondary"
            onClick={() => void fetchStatus()}
            className="ml-auto"
          >
            <RefreshCw className="mr-1 h-3 w-3" />
            Retry
          </Button>
        </div>
      </Card>
    );
  }

  if (!status) {
    return null;
  }

  const timeUntilCleanup = getTimeUntilCleanup(status.next_cleanup);
  const nextCleanupFormatted = formatNextCleanup(status.next_cleanup);
  const cleanupProgress = getCleanupProgress(status.next_cleanup);

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="cleanup-status-card"
    >
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <Title className="flex items-center gap-2 text-white">
          <Trash2 className="h-5 w-5 text-[#76B900]" />
          Cleanup Service
        </Title>

        {/* Running Status Badge */}
        <Badge
          color={status.running ? 'green' : 'red'}
          size="sm"
          data-testid="running-status-badge"
        >
          <span className="flex items-center gap-1">
            {status.running ? (
              <PlayCircle className="h-3 w-3" />
            ) : (
              <XCircle className="h-3 w-3" />
            )}
            {status.running ? 'Running' : 'Stopped'}
          </span>
        </Badge>
      </div>

      {/* Error banner (if error but we have cached data) */}
      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-2">
          <AlertTriangle className="h-4 w-4 text-amber-500" />
          <Text className="text-xs text-amber-400">{error}</Text>
        </div>
      )}

      {/* Next Cleanup Countdown */}
      {status.running && status.next_cleanup && (
        <div className="mb-4 rounded-lg bg-gray-800/30 p-3">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-[#76B900]" />
              <Text className="text-sm text-gray-300">Next Cleanup</Text>
            </div>
            <Text className="text-lg font-bold text-[#76B900]" data-testid="time-until-cleanup">
              {timeUntilCleanup}
            </Text>
          </div>
          <ProgressBar value={cleanupProgress} color="emerald" className="mb-1" />
          <Text className="text-xs text-gray-500" data-testid="next-cleanup-time">
            {nextCleanupFormatted}
          </Text>
        </div>
      )}

      {/* Not running message */}
      {!status.running && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3">
          <AlertTriangle className="h-4 w-4 text-amber-500" />
          <Text className="text-sm text-amber-400">
            Cleanup service is not running. Data will not be automatically cleaned up.
          </Text>
        </div>
      )}

      {/* Configuration Details */}
      <div className="space-y-3">
        {/* Retention Policy */}
        <div className="flex items-center justify-between rounded-lg bg-gray-800/30 p-3">
          <div className="flex items-center gap-2">
            <Calendar className="h-4 w-4 text-gray-400" />
            <Text className="text-sm text-gray-300">Retention Period</Text>
          </div>
          <span className="font-medium text-white" data-testid="retention-days">
            {status.retention_days} days
          </span>
        </div>

        {/* Scheduled Time */}
        <div className="flex items-center justify-between rounded-lg bg-gray-800/30 p-3">
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-gray-400" />
            <Text className="text-sm text-gray-300">Daily Schedule</Text>
          </div>
          <span className="font-medium text-white" data-testid="cleanup-time">
            {formatTime(status.cleanup_time)}
          </span>
        </div>

        {/* Image Deletion Setting */}
        <div className="flex items-center justify-between rounded-lg bg-gray-800/30 p-3">
          <div className="flex items-center gap-2">
            <Image className="h-4 w-4 text-gray-400" />
            <Text className="text-sm text-gray-300">Delete Original Images</Text>
          </div>
          <span data-testid="delete-images-badge">
            <Badge
              color={status.delete_images ? 'amber' : 'green'}
              size="xs"
            >
              <span className="flex items-center gap-1">
                {status.delete_images ? (
                  <>
                    <CheckCircle className="h-3 w-3" /> Enabled
                  </>
                ) : (
                  <>
                    <XCircle className="h-3 w-3" /> Disabled
                  </>
                )}
              </span>
            </Badge>
          </span>
        </div>
      </div>

      {/* Last Updated */}
      {lastUpdated && (
        <div className="mt-4 flex items-center justify-between">
          <span className="text-xs text-gray-500" data-testid="last-updated">
            Last updated: {lastUpdated.toLocaleTimeString()}
          </span>
          <Button
            size="xs"
            variant="secondary"
            onClick={() => void fetchStatus()}
            disabled={loading}
            className="text-gray-400 hover:text-white"
          >
            <RefreshCw className={clsx('h-3 w-3', loading && 'animate-spin')} />
          </Button>
        </div>
      )}
    </Card>
  );
}
