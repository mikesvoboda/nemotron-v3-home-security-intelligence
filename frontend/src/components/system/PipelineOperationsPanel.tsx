/**
 * PipelineOperationsPanel - Dashboard showing pipeline operations status
 *
 * Displays real-time status of:
 * - FileWatcher: Monitoring camera directories for new uploads
 * - BatchAggregator: Grouping detections into time-based batches
 * - DegradationManager: Graceful degradation and service health
 *
 * Uses NVIDIA dark theme styling consistent with the rest of the dashboard.
 */

import { Card, Title, Text, Badge, ProgressBar } from '@tremor/react';
import { clsx } from 'clsx';
import {
  Eye,
  Layers,
  ShieldAlert,
  Folder,
  Clock,
  Activity,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Server,
  Pause,
  RefreshCw,
} from 'lucide-react';
import { useEffect, useState, useCallback } from 'react';

import {
  fetchPipelineStatus,
  type PipelineStatusResponse,
  type FileWatcherStatus,
  type BatchAggregatorStatus,
  type DegradationStatus,
  type BatchInfo,
  type DegradationMode,
} from '../../services/api';

interface PipelineOperationsPanelProps {
  /** Polling interval in milliseconds (default: 5000) */
  pollingInterval?: number;
}

/**
 * Get badge color based on degradation mode
 */
function getDegradationModeColor(mode: DegradationMode): 'green' | 'yellow' | 'orange' | 'red' {
  switch (mode) {
    case 'normal':
      return 'green';
    case 'degraded':
      return 'yellow';
    case 'minimal':
      return 'orange';
    case 'offline':
      return 'red';
    default:
      return 'green';
  }
}

/**
 * Get status icon component
 */
function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'healthy':
      return <CheckCircle className="h-4 w-4 text-green-500" />;
    case 'unhealthy':
      return <XCircle className="h-4 w-4 text-red-500" />;
    default:
      return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
  }
}

/**
 * Format seconds into human readable string
 */
function formatSeconds(seconds: number): string {
  if (seconds < 60) {
    return `${seconds.toFixed(1)}s`;
  } else if (seconds < 3600) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}m ${secs}s`;
  } else {
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${mins}m`;
  }
}

/**
 * FileWatcher status section
 */
function FileWatcherSection({ status }: { status: FileWatcherStatus | null }) {
  if (!status) {
    return (
      <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
        <div className="mb-2 flex items-center gap-2">
          <Eye className="h-5 w-5 text-gray-500" />
          <Text className="font-medium text-gray-400">FileWatcher</Text>
        </div>
        <Text className="text-sm text-gray-500">Not running</Text>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Eye className="h-5 w-5 text-[#76B900]" />
          <Text className="font-medium text-white">FileWatcher</Text>
        </div>
        <Badge color={status.running ? 'green' : 'red'} size="sm">
          {status.running ? 'Running' : 'Stopped'}
        </Badge>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Folder className="h-4 w-4 text-gray-400" />
            <Text className="text-xs text-gray-400">Watch Directory</Text>
          </div>
          <Text className="max-w-[200px] truncate text-xs text-gray-300" title={status.camera_root}>
            {status.camera_root}
          </Text>
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-gray-400" />
            <Text className="text-xs text-gray-400">Pending Files</Text>
          </div>
          <Badge color={status.pending_tasks > 0 ? 'yellow' : 'gray'} size="xs">
            {status.pending_tasks}
          </Badge>
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Server className="h-4 w-4 text-gray-400" />
            <Text className="text-xs text-gray-400">Observer Type</Text>
          </div>
          <Text className="text-xs text-gray-300">{status.observer_type}</Text>
        </div>
      </div>
    </div>
  );
}

/**
 * Single batch info card
 */
function BatchCard({ batch }: { batch: BatchInfo }) {
  const windowSeconds = 90; // Default batch window
  const progress = Math.min((batch.age_seconds / windowSeconds) * 100, 100);

  return (
    <div className="rounded border border-gray-600 bg-gray-700/50 p-2">
      <div className="mb-1 flex items-center justify-between">
        <Text className="text-xs font-medium text-gray-200">{batch.camera_id}</Text>
        <Badge color="blue" size="xs">
          {batch.detection_count} detections
        </Badge>
      </div>
      <div className="mb-1">
        <ProgressBar value={progress} color="emerald" className="h-1" />
      </div>
      <div className="flex justify-between">
        <Text className="text-xs text-gray-400">Age: {formatSeconds(batch.age_seconds)}</Text>
        <Text className="text-xs text-gray-400">
          Idle: {formatSeconds(batch.last_activity_seconds)}
        </Text>
      </div>
    </div>
  );
}

/**
 * BatchAggregator status section
 */
function BatchAggregatorSection({ status }: { status: BatchAggregatorStatus | null }) {
  if (!status) {
    return (
      <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
        <div className="mb-2 flex items-center gap-2">
          <Layers className="h-5 w-5 text-gray-500" />
          <Text className="font-medium text-gray-400">BatchAggregator</Text>
        </div>
        <Text className="text-sm text-gray-500">Not available</Text>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Layers className="h-5 w-5 text-[#76B900]" />
          <Text className="font-medium text-white">BatchAggregator</Text>
        </div>
        <Badge color={status.active_batches > 0 ? 'blue' : 'gray'} size="sm">
          {status.active_batches} active
        </Badge>
      </div>

      <div className="mb-3 space-y-2">
        <div className="flex items-center justify-between">
          <Text className="text-xs text-gray-400">Batch Window</Text>
          <Text className="text-xs text-gray-300">{status.batch_window_seconds}s</Text>
        </div>
        <div className="flex items-center justify-between">
          <Text className="text-xs text-gray-400">Idle Timeout</Text>
          <Text className="text-xs text-gray-300">{status.idle_timeout_seconds}s</Text>
        </div>
      </div>

      {status.batches.length > 0 && (
        <div className="space-y-2">
          <Text className="text-xs font-medium text-gray-400">Active Batches</Text>
          <div className="max-h-32 space-y-2 overflow-y-auto">
            {status.batches.map((batch) => (
              <BatchCard key={batch.batch_id} batch={batch} />
            ))}
          </div>
        </div>
      )}

      {status.batches.length === 0 && (
        <div className="flex items-center justify-center rounded border border-dashed border-gray-600 py-4">
          <div className="flex items-center gap-2 text-gray-500">
            <Pause className="h-4 w-4" />
            <Text className="text-xs">No active batches</Text>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * DegradationManager status section
 */
function DegradationSection({ status }: { status: DegradationStatus | null }) {
  if (!status) {
    return (
      <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
        <div className="mb-2 flex items-center gap-2">
          <ShieldAlert className="h-5 w-5 text-gray-500" />
          <Text className="font-medium text-gray-400">Degradation Status</Text>
        </div>
        <Text className="text-sm text-gray-500">Not initialized</Text>
      </div>
    );
  }

  const totalFallbackItems = Object.values(status.fallback_queues).reduce((a, b) => a + b, 0);
  const hasIssues = status.is_degraded || status.memory_queue_size > 0 || totalFallbackItems > 0;

  return (
    <div
      className={clsx(
        'rounded-lg border p-4',
        hasIssues
          ? 'border-yellow-500/30 bg-yellow-500/10'
          : 'border-gray-700 bg-gray-800/50'
      )}
    >
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldAlert className={clsx('h-5 w-5', hasIssues ? 'text-yellow-500' : 'text-[#76B900]')} />
          <Text className="font-medium text-white">Degradation Status</Text>
        </div>
        <Badge color={getDegradationModeColor(status.mode)} size="sm">
          {status.mode.toUpperCase()}
        </Badge>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Text className="text-xs text-gray-400">Redis Health</Text>
          <div className="flex items-center gap-1">
            {status.redis_healthy ? (
              <CheckCircle className="h-3 w-3 text-green-500" />
            ) : (
              <XCircle className="h-3 w-3 text-red-500" />
            )}
            <Text className={clsx('text-xs', status.redis_healthy ? 'text-green-400' : 'text-red-400')}>
              {status.redis_healthy ? 'Healthy' : 'Unhealthy'}
            </Text>
          </div>
        </div>

        <div className="flex items-center justify-between">
          <Text className="text-xs text-gray-400">Memory Queue</Text>
          <Badge color={status.memory_queue_size > 0 ? 'yellow' : 'gray'} size="xs">
            {status.memory_queue_size} items
          </Badge>
        </div>

        {totalFallbackItems > 0 && (
          <div className="flex items-center justify-between">
            <Text className="text-xs text-gray-400">Fallback Queues</Text>
            <Badge color="yellow" size="xs">
              {totalFallbackItems} items
            </Badge>
          </div>
        )}
      </div>

      {/* Service Health */}
      {status.services.length > 0 && (
        <div className="mt-3 space-y-2">
          <Text className="text-xs font-medium text-gray-400">Service Health</Text>
          <div className="space-y-1">
            {status.services.map((service) => (
              <div
                key={service.name}
                className="flex items-center justify-between rounded bg-gray-700/50 px-2 py-1"
              >
                <div className="flex items-center gap-2">
                  <StatusIcon status={service.status} />
                  <Text className="text-xs text-gray-300">{service.name}</Text>
                </div>
                {service.consecutive_failures > 0 && (
                  <Badge color="red" size="xs">
                    {service.consecutive_failures} failures
                  </Badge>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Available Features */}
      {status.available_features.length > 0 && (
        <div className="mt-3">
          <Text className="mb-2 text-xs font-medium text-gray-400">Available Features</Text>
          <div className="flex flex-wrap gap-1">
            {status.available_features.map((feature) => (
              <Badge key={feature} color="gray" size="xs">
                {feature}
              </Badge>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * PipelineOperationsPanel - Main panel component
 */
export default function PipelineOperationsPanel({
  pollingInterval = 5000,
}: PipelineOperationsPanelProps) {
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const data = await fetchPipelineStatus();
      setPipelineStatus(data);
      setLastUpdate(new Date());
      setError(null);
    } catch (err) {
      console.error('Failed to fetch pipeline status:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch pipeline status');
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial fetch
  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  // Polling
  useEffect(() => {
    const interval = setInterval(() => {
      void fetchData();
    }, pollingInterval);

    return () => clearInterval(interval);
  }, [fetchData, pollingInterval]);

  if (loading) {
    return (
      <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="pipeline-operations-loading">
        <div className="mb-4 flex items-center gap-2">
          <Activity className="h-5 w-5 animate-pulse text-gray-500" />
          <Title className="text-white">Pipeline Operations</Title>
        </div>
        <div className="space-y-4">
          {Array.from({ length: 3 }, (_, i) => (
            <div key={i} className="h-32 animate-pulse rounded-lg bg-gray-800"></div>
          ))}
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="pipeline-operations-error">
        <div className="mb-4 flex items-center gap-2">
          <Activity className="h-5 w-5 text-red-500" />
          <Title className="text-white">Pipeline Operations</Title>
        </div>
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <div className="flex items-center gap-2">
            <XCircle className="h-5 w-5 text-red-500" />
            <Text className="text-red-400">{error}</Text>
          </div>
          <button
            onClick={() => void fetchData()}
            className="mt-3 flex items-center gap-2 rounded bg-red-500/20 px-3 py-1 text-sm text-red-400 transition-colors hover:bg-red-500/30"
          >
            <RefreshCw className="h-4 w-4" />
            Retry
          </button>
        </div>
      </Card>
    );
  }

  return (
    <Card
      className="border-gray-800 bg-[#1A1A1A] shadow-lg"
      data-testid="pipeline-operations-panel"
    >
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="h-5 w-5 text-[#76B900]" />
          <Title className="text-white">Pipeline Operations</Title>
        </div>
        {lastUpdate && (
          <Text className="text-xs text-gray-500">
            Updated: {lastUpdate.toLocaleTimeString()}
          </Text>
        )}
      </div>

      <div className="space-y-4">
        <FileWatcherSection status={pipelineStatus?.file_watcher ?? null} />
        <BatchAggregatorSection status={pipelineStatus?.batch_aggregator ?? null} />
        <DegradationSection status={pipelineStatus?.degradation ?? null} />
      </div>
    </Card>
  );
}
