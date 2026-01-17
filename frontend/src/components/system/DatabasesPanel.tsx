import { Card, Title, Text, Badge, ProgressBar, AreaChart } from '@tremor/react';
import { clsx } from 'clsx';
import {
  Database,
  Server,
  HardDrive,
  Activity,
  Users,
  Zap,
  Bug,
  AlertCircle,
  Radio,
} from 'lucide-react';

import type { RedisInfo, RedisPubsubInfo } from '../../services/api';

/**
 * PostgreSQL database metrics
 */
export interface DatabaseMetrics {
  status: string;
  connections_active: number;
  connections_max: number;
  cache_hit_ratio: number;
  transactions_per_min: number;
}

/**
 * Redis metrics
 */
export interface RedisMetrics {
  status: string;
  connected_clients: number;
  memory_mb: number;
  hit_ratio: number;
  blocked_clients: number;
}

/**
 * History data point
 */
export interface HistoryDataPoint {
  timestamp: string;
  value: number;
}

/**
 * Database history data for charts
 */
export interface DatabaseHistoryData {
  postgresql: {
    connections: HistoryDataPoint[];
    cache_hit_ratio: HistoryDataPoint[];
  };
  redis: {
    memory: HistoryDataPoint[];
    clients: HistoryDataPoint[];
  };
}

/**
 * Props for DatabasesPanel component
 */
export interface DatabasesPanelProps {
  /** PostgreSQL metrics (null if unavailable) */
  postgresql: DatabaseMetrics | null;
  /** Redis metrics (null if unavailable) */
  redis: RedisMetrics | null;
  /** Current time range for historical data */
  timeRange: string;
  /** Historical data for charts */
  history: DatabaseHistoryData;
  /** Additional CSS classes */
  className?: string;
  /** Optional data-testid attribute for testing */
  'data-testid'?: string;
  /** Whether debug mode is enabled - shows additional debug info */
  debugMode?: boolean;
  /** Redis debug info from /api/debug/redis/info (only shown when debugMode is true) */
  redisDebugInfo?: RedisInfo | null;
  /** Pub/sub channel information (only shown when debugMode is true) */
  pubsubInfo?: RedisPubsubInfo | null;
  /** Whether Redis debug info is loading */
  redisDebugLoading?: boolean;
  /** Error message if Redis debug info failed to load */
  redisDebugError?: string | null;
}

/**
 * Format transactions per minute with k suffix for large numbers
 */
function formatTransactions(txns: number): string {
  if (txns >= 1000) {
    return `${(txns / 1000).toFixed(1)}k/min`;
  }
  return `${txns}/min`;
}

/**
 * Get badge color based on status
 */
function getStatusColor(status: string): 'green' | 'red' | 'yellow' | 'gray' {
  switch (status.toLowerCase()) {
    case 'healthy':
      return 'green';
    case 'unhealthy':
    case 'unreachable':
      return 'red';
    case 'degraded':
      return 'yellow';
    default:
      return 'gray';
  }
}

/**
 * Get color for cache hit ratio
 */
function getCacheHitColor(ratio: number): 'green' | 'yellow' | 'red' {
  if (ratio >= 90) return 'green';
  if (ratio >= 80) return 'yellow';
  return 'red';
}

/**
 * Get color for Redis hit ratio
 */
function getHitRatioColor(ratio: number): 'green' | 'yellow' | 'red' {
  if (ratio >= 50) return 'green';
  if (ratio >= 10) return 'yellow';
  return 'red';
}

/**
 * Get color for connection pool usage
 */
function getConnectionColor(active: number, max: number): 'green' | 'yellow' | 'red' {
  const usage = (active / max) * 100;
  if (usage >= 95) return 'red';
  if (usage >= 80) return 'yellow';
  return 'green';
}

/**
 * Transform history data to chart format
 */
function transformToChartData(data: HistoryDataPoint[]): { time: string; value: number }[] {
  return data.map((point) => ({
    time: new Date(point.timestamp).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
    }),
    value: point.value,
  }));
}

/**
 * Capitalize first letter of status
 */
function formatStatus(status: string): string {
  return status.charAt(0).toUpperCase() + status.slice(1).toLowerCase();
}

/**
 * DatabasesPanel - Displays PostgreSQL and Redis metrics side by side
 *
 * Shows:
 * - Status badges for each database
 * - Connection pool usage (PostgreSQL)
 * - Cache hit ratio (PostgreSQL)
 * - Transactions per minute (PostgreSQL)
 * - Connected clients (Redis)
 * - Memory usage (Redis)
 * - Hit ratio (Redis)
 * - Historical charts for key metrics
 */
/**
 * Format uptime in seconds to human-readable format
 */
function formatUptime(seconds: number): string {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);

  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

export default function DatabasesPanel({
  postgresql,
  redis,
  timeRange: _timeRange,
  history,
  className,
  'data-testid': testId = 'databases-panel',
  debugMode = false,
  redisDebugInfo = null,
  pubsubInfo = null,
  redisDebugLoading = false,
  redisDebugError = null,
}: DatabasesPanelProps) {
  const postgresChartData = transformToChartData(history.postgresql.connections);
  const redisChartData = transformToChartData(history.redis.memory);

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid={testId}
    >
      <Title className="mb-4 flex items-center gap-2 text-white">
        <Database className="h-5 w-5 text-[#76B900]" />
        Databases
      </Title>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {/* PostgreSQL Card */}
        <div
          className="rounded-lg border border-gray-700 bg-gray-800/50 p-4"
          data-testid="postgresql-card"
        >
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Server className="h-4 w-4 text-blue-400" />
              <Text className="font-medium text-gray-200">PostgreSQL</Text>
            </div>
            {postgresql ? (
              <Badge
                color={getStatusColor(postgresql.status)}
                size="sm"
                data-testid="postgresql-status"
              >
                {formatStatus(postgresql.status)}
              </Badge>
            ) : (
              <Badge color="gray" size="sm" data-testid="postgresql-status">
                Unknown
              </Badge>
            )}
          </div>

          {postgresql ? (
            <div className="space-y-3">
              {/* Connections */}
              <div>
                <div className="mb-1 flex items-center justify-between">
                  <Text className="flex items-center gap-1 text-xs text-gray-400">
                    <Users className="h-3 w-3" />
                    Connections
                  </Text>
                  <span
                    className="text-xs font-medium text-gray-200"
                    data-testid="postgresql-connections"
                  >
                    {postgresql.connections_active}/{postgresql.connections_max}
                  </span>
                </div>
                <ProgressBar
                  value={(postgresql.connections_active / postgresql.connections_max) * 100}
                  color={getConnectionColor(
                    postgresql.connections_active,
                    postgresql.connections_max
                  )}
                  className="h-1.5"
                  data-testid="postgresql-connections-bar"
                />
              </div>

              {/* Cache Hit Ratio */}
              <div>
                <div className="mb-1 flex items-center justify-between">
                  <Text className="flex items-center gap-1 text-xs text-gray-400">
                    <Zap className="h-3 w-3" />
                    Cache Hit
                  </Text>
                  <span
                    className={clsx(
                      'text-xs font-medium',
                      getCacheHitColor(postgresql.cache_hit_ratio) === 'green' && 'text-green-400',
                      getCacheHitColor(postgresql.cache_hit_ratio) === 'yellow' &&
                        'text-yellow-400',
                      getCacheHitColor(postgresql.cache_hit_ratio) === 'red' && 'text-red-400'
                    )}
                    data-testid="postgresql-cache-hit"
                  >
                    {postgresql.cache_hit_ratio.toFixed(1)}%
                  </span>
                </div>
                <ProgressBar
                  value={postgresql.cache_hit_ratio}
                  color={getCacheHitColor(postgresql.cache_hit_ratio)}
                  className="h-1.5"
                />
              </div>

              {/* Transactions */}
              <div className="flex items-center justify-between">
                <Text className="flex items-center gap-1 text-xs text-gray-400">
                  <Activity className="h-3 w-3" />
                  Transactions
                </Text>
                <span className="text-xs font-medium text-gray-200" data-testid="postgresql-txns">
                  {formatTransactions(postgresql.transactions_per_min)}
                </span>
              </div>

              {/* Historical Chart */}
              <div className="mt-3 border-t border-gray-700 pt-3" data-testid="postgresql-chart">
                {postgresChartData.length > 0 ? (
                  <AreaChart
                    className="h-24"
                    data={postgresChartData}
                    index="time"
                    categories={['value']}
                    colors={['blue']}
                    showLegend={false}
                    showGridLines={false}
                    curveType="monotone"
                    valueFormatter={(value) => `${value}`}
                  />
                ) : (
                  <div className="flex h-24 items-center justify-center">
                    <Text className="text-xs text-gray-500">No history data</Text>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="flex h-40 items-center justify-center">
              <Text className="text-sm text-gray-500">No data available</Text>
            </div>
          )}
        </div>

        {/* Redis Card */}
        <div
          className="rounded-lg border border-gray-700 bg-gray-800/50 p-4"
          data-testid="redis-card"
        >
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <HardDrive className="h-4 w-4 text-red-400" />
              <Text className="font-medium text-gray-200">Redis</Text>
            </div>
            {redis ? (
              <Badge color={getStatusColor(redis.status)} size="sm" data-testid="redis-status">
                {formatStatus(redis.status)}
              </Badge>
            ) : (
              <Badge color="gray" size="sm" data-testid="redis-status">
                Unknown
              </Badge>
            )}
          </div>

          {redis ? (
            <div className="space-y-3">
              {/* Connected Clients */}
              <div className="flex items-center justify-between">
                <Text className="flex items-center gap-1 text-xs text-gray-400">
                  <Users className="h-3 w-3" />
                  Clients
                </Text>
                <span className="text-xs font-medium text-gray-200" data-testid="redis-clients">
                  {redis.connected_clients}
                </span>
              </div>

              {/* Memory */}
              <div className="flex items-center justify-between">
                <Text className="flex items-center gap-1 text-xs text-gray-400">
                  <HardDrive className="h-3 w-3" />
                  Memory
                </Text>
                <span className="text-xs font-medium text-gray-200" data-testid="redis-memory">
                  {redis.memory_mb.toFixed(2)} MB
                </span>
              </div>

              {/* Hit Ratio */}
              <div>
                <div className="mb-1 flex items-center justify-between">
                  <Text className="flex items-center gap-1 text-xs text-gray-400">
                    <Zap className="h-3 w-3" />
                    Hit Ratio
                  </Text>
                  <span
                    className={clsx(
                      'text-xs font-medium',
                      getHitRatioColor(redis.hit_ratio) === 'green' && 'text-green-400',
                      getHitRatioColor(redis.hit_ratio) === 'yellow' && 'text-yellow-400',
                      getHitRatioColor(redis.hit_ratio) === 'red' && 'text-red-400'
                    )}
                    data-testid="redis-hit-ratio"
                  >
                    {redis.hit_ratio.toFixed(1)}%
                  </span>
                </div>
                <ProgressBar
                  value={redis.hit_ratio}
                  color={getHitRatioColor(redis.hit_ratio)}
                  className="h-1.5"
                />
              </div>

              {/* Blocked Clients */}
              <div className="flex items-center justify-between">
                <Text className="flex items-center gap-1 text-xs text-gray-400">
                  <Activity className="h-3 w-3" />
                  Blocked
                </Text>
                <span className="text-xs font-medium text-gray-200" data-testid="redis-blocked">
                  {redis.blocked_clients}
                </span>
              </div>

              {/* Historical Chart */}
              <div className="mt-3 border-t border-gray-700 pt-3" data-testid="redis-chart">
                {redisChartData.length > 0 ? (
                  <AreaChart
                    className="h-24"
                    data={redisChartData}
                    index="time"
                    categories={['value']}
                    colors={['red']}
                    showLegend={false}
                    showGridLines={false}
                    curveType="monotone"
                    valueFormatter={(value) => `${value.toFixed(2)} MB`}
                  />
                ) : (
                  <div className="flex h-24 items-center justify-center">
                    <Text className="text-xs text-gray-500">No history data</Text>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="flex h-40 items-center justify-center">
              <Text className="text-sm text-gray-500">No data available</Text>
            </div>
          )}
        </div>
      </div>

      {/* Debug Section - Redis Debug Info */}
      {debugMode && (
        <div
          className="mt-4 rounded-lg border border-orange-500/30 bg-orange-500/5 p-3"
          data-testid="redis-debug-section"
        >
          <div className="mb-3 flex items-center gap-2">
            <Bug className="h-4 w-4 text-orange-500" />
            <Text className="text-sm font-medium text-orange-400">Redis Debug Info</Text>
            <Badge color="orange" size="xs">
              DEBUG
            </Badge>
          </div>

          {/* Loading state */}
          {redisDebugLoading && (
            <div className="space-y-2" data-testid="redis-debug-loading">
              <div className="h-8 animate-pulse rounded bg-gray-700/50" />
              <div className="h-8 animate-pulse rounded bg-gray-700/50" />
            </div>
          )}

          {/* Error state */}
          {redisDebugError && !redisDebugLoading && (
            <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2">
              <AlertCircle className="h-4 w-4 text-red-500" />
              <Text className="text-xs text-red-400">{redisDebugError}</Text>
            </div>
          )}

          {/* Empty state */}
          {!redisDebugLoading && !redisDebugError && !redisDebugInfo && (
            <Text className="text-sm text-gray-500">No debug info available</Text>
          )}

          {/* Debug info content */}
          {!redisDebugLoading && !redisDebugError && redisDebugInfo && (
            <div className="space-y-3">
              {/* Basic Info Grid */}
              <div className="grid grid-cols-2 gap-2 text-xs md:grid-cols-4">
                <div className="rounded bg-gray-800/50 p-2">
                  <Text className="text-gray-500">Version</Text>
                  <Text className="font-medium text-gray-200">{redisDebugInfo.redis_version}</Text>
                </div>
                <div className="rounded bg-gray-800/50 p-2">
                  <Text className="text-gray-500">Memory</Text>
                  <Text className="font-medium text-gray-200">
                    {redisDebugInfo.used_memory_human}
                  </Text>
                </div>
                <div className="rounded bg-gray-800/50 p-2">
                  <Text className="text-gray-500">Peak Memory</Text>
                  <Text className="font-medium text-gray-200">
                    {redisDebugInfo.used_memory_peak_human}
                  </Text>
                </div>
                <div className="rounded bg-gray-800/50 p-2">
                  <Text className="text-gray-500">Uptime</Text>
                  <Text className="font-medium text-gray-200">
                    {formatUptime(redisDebugInfo.uptime_in_seconds)}
                  </Text>
                </div>
              </div>

              {/* Connection Stats */}
              <div className="grid grid-cols-2 gap-2 text-xs md:grid-cols-3">
                <div className="rounded bg-gray-800/50 p-2">
                  <Text className="text-gray-500">Clients</Text>
                  <Text className="font-medium text-gray-200">
                    {redisDebugInfo.connected_clients}
                  </Text>
                </div>
                <div className="rounded bg-gray-800/50 p-2">
                  <Text className="text-gray-500">Total Connections</Text>
                  <Text className="font-medium text-gray-200">
                    {redisDebugInfo.total_connections_received.toLocaleString()}
                  </Text>
                </div>
                <div className="rounded bg-gray-800/50 p-2">
                  <Text className="text-gray-500">Commands Processed</Text>
                  <Text className="font-medium text-gray-200">
                    {redisDebugInfo.total_commands_processed.toLocaleString()}
                  </Text>
                </div>
              </div>

              {/* Pub/Sub Channels */}
              {pubsubInfo && pubsubInfo.channels.length > 0 && (
                <div className="border-t border-gray-700 pt-3">
                  <div className="mb-2 flex items-center gap-2">
                    <Radio className="h-3 w-3 text-orange-400" />
                    <Text className="text-xs font-medium text-gray-400">
                      Pub/Sub Channels ({pubsubInfo.channels.length})
                    </Text>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {pubsubInfo.channels.map((channel) => (
                      <div
                        key={channel}
                        className="flex items-center gap-1 rounded border border-gray-700 bg-gray-800/50 px-2 py-1"
                      >
                        <Text className="text-xs text-gray-300">{channel}</Text>
                        <Badge color="blue" size="xs">
                          {pubsubInfo.subscriber_counts[channel] || 0}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
