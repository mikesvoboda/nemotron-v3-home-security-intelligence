/**
 * PerformanceDashboard - Main dashboard component displaying real-time performance metrics.
 *
 * Displays system performance data using Tremor components, receiving updates via WebSocket
 * from the /ws/system endpoint. Shows GPU metrics, AI model status, database metrics,
 * host system metrics, and container health status.
 *
 * Updates automatically every 5 seconds via WebSocket connection.
 *
 * @see usePerformanceMetrics hook for data structure and WebSocket handling
 */

import { Card, Title, Text, ProgressBar, Badge } from '@tremor/react';
import { clsx } from 'clsx';
import {
  Cpu,
  Brain,
  Database,
  HardDrive,
  Box,
  Thermometer,
  Zap,
  Activity,
  Users,
  Wifi,
  WifiOff,
  MemoryStick,
  Layers,
  Monitor,
  CheckCircle,
  XCircle,
  AlertCircle,
} from 'lucide-react';

import {
  usePerformanceMetrics,
  type GpuMetrics,
  type AiModelMetrics,
  type NemotronMetrics,
  type DatabaseMetrics,
  type RedisMetrics,
  type HostMetrics,
  type ContainerMetrics,
  type TimeRange,
} from '../../hooks/usePerformanceMetrics';

export interface PerformanceDashboardProps {
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Time Range Selector
// ============================================================================

interface TimeRangeSelectorProps {
  selectedRange: TimeRange;
  onRangeChange: (range: TimeRange) => void;
}

const TIME_RANGES: { value: TimeRange; label: string }[] = [
  { value: '5m', label: '5m' },
  { value: '15m', label: '15m' },
  { value: '60m', label: '60m' },
];

function TimeRangeSelector({ selectedRange, onRangeChange }: TimeRangeSelectorProps) {
  return (
    <div
      role="group"
      aria-label="Time range selection"
      className="flex items-center gap-1 rounded-lg bg-gray-800/50 p-1"
      data-testid="time-range-selector"
    >
      {TIME_RANGES.map(({ value, label }) => {
        const isSelected = selectedRange === value;
        return (
          <button
            key={value}
            type="button"
            onClick={() => onRangeChange(value)}
            aria-pressed={isSelected}
            className={clsx(
              'rounded-md px-3 py-1.5 text-sm font-medium transition-all duration-150',
              isSelected
                ? 'bg-[#76B900] text-gray-950 shadow-sm'
                : 'text-gray-400 hover:bg-gray-700/50 hover:text-gray-200'
            )}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get badge color based on status string
 */
function getStatusColor(status: string): 'green' | 'yellow' | 'red' | 'gray' {
  switch (status.toLowerCase()) {
    case 'healthy':
      return 'green';
    case 'loading':
    case 'degraded':
    case 'starting':
      return 'yellow';
    case 'unhealthy':
    case 'error':
    case 'unreachable':
      return 'red';
    default:
      return 'gray';
  }
}

/**
 * Get progress bar color based on percentage thresholds
 */
function getUsageColor(
  percent: number,
  thresholds = { warning: 80, critical: 95 }
): 'green' | 'yellow' | 'red' {
  if (percent >= thresholds.critical) return 'red';
  if (percent >= thresholds.warning) return 'yellow';
  return 'green';
}

/**
 * Get temperature color based on GPU temperature thresholds
 */
function getTemperatureColor(temp: number): 'green' | 'yellow' | 'red' {
  if (temp >= 85) return 'red';
  if (temp >= 70) return 'yellow';
  return 'green';
}

/**
 * Type guard to check if model metrics are for RT-DETRv2 (detection model)
 */
function isAiModelMetrics(model: AiModelMetrics | NemotronMetrics): model is AiModelMetrics {
  return 'vram_gb' in model && 'device' in model;
}

/**
 * Type guard to check if model metrics are for Nemotron (LLM model)
 */
function isNemotronMetrics(model: AiModelMetrics | NemotronMetrics): model is NemotronMetrics {
  return 'slots_active' in model && 'context_size' in model;
}

/**
 * Type guard to check if database metrics are for PostgreSQL
 */
function isDatabaseMetrics(db: DatabaseMetrics | RedisMetrics): db is DatabaseMetrics {
  return 'connections_active' in db && 'cache_hit_ratio' in db;
}

/**
 * Type guard to check if database metrics are for Redis
 */
function isRedisMetrics(db: DatabaseMetrics | RedisMetrics): db is RedisMetrics {
  return 'memory_mb' in db && 'hit_ratio' in db;
}

/**
 * Capitalize first letter of a string
 */
function capitalize(str: string): string {
  return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
}

// ============================================================================
// GPU Card
// ============================================================================

interface GpuCardProps {
  gpu: GpuMetrics | null;
}

function GpuCard({ gpu }: GpuCardProps) {
  if (!gpu) {
    return (
      <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="gpu-card">
        <Title className="mb-4 flex items-center gap-2 text-white">
          <Cpu className="h-5 w-5 text-[#76B900]" />
          GPU
        </Title>
        <div className="flex h-32 items-center justify-center">
          <Text className="text-gray-500">No GPU data available</Text>
        </div>
      </Card>
    );
  }

  const vramPercent = Math.round((gpu.vram_used_gb / gpu.vram_total_gb) * 100);

  return (
    <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="gpu-card">
      <div className="mb-4 flex items-center justify-between">
        <Title className="flex items-center gap-2 text-white">
          <Cpu className="h-5 w-5 text-[#76B900]" />
          GPU
        </Title>
        <Badge color="green" size="sm">
          {gpu.name}
        </Badge>
      </div>

      <div className="space-y-4">
        {/* Utilization */}
        <div>
          <div className="mb-1 flex items-center justify-between">
            <Text className="flex items-center gap-1 text-sm text-gray-400">
              <Activity className="h-4 w-4" />
              Utilization
            </Text>
            <span
              className={clsx(
                'text-sm font-medium',
                getUsageColor(gpu.utilization) === 'green' && 'text-green-400',
                getUsageColor(gpu.utilization) === 'yellow' && 'text-yellow-400',
                getUsageColor(gpu.utilization) === 'red' && 'text-red-400'
              )}
              data-testid="gpu-utilization"
            >
              {gpu.utilization}%
            </span>
          </div>
          <ProgressBar
            value={gpu.utilization}
            color={getUsageColor(gpu.utilization)}
            className="h-2"
            data-testid="gpu-utilization-bar"
          />
        </div>

        {/* VRAM */}
        <div>
          <div className="mb-1 flex items-center justify-between">
            <Text className="flex items-center gap-1 text-sm text-gray-400">
              <MemoryStick className="h-4 w-4" />
              VRAM
            </Text>
            <span className="text-sm text-gray-200" data-testid="gpu-vram">
              {gpu.vram_used_gb.toFixed(1)}/{gpu.vram_total_gb.toFixed(1)} GB ({vramPercent}%)
            </span>
          </div>
          <ProgressBar
            value={vramPercent}
            color={getUsageColor(vramPercent)}
            className="h-2"
            data-testid="gpu-vram-bar"
          />
        </div>

        {/* Temperature & Power */}
        <div className="grid grid-cols-2 gap-4 rounded-lg bg-gray-800/50 p-3">
          <div className="flex items-center gap-2">
            <Thermometer
              className={clsx(
                'h-4 w-4',
                getTemperatureColor(gpu.temperature) === 'green' && 'text-green-400',
                getTemperatureColor(gpu.temperature) === 'yellow' && 'text-yellow-400',
                getTemperatureColor(gpu.temperature) === 'red' && 'text-red-400'
              )}
            />
            <div>
              <Text className="text-xs text-gray-500">Temperature</Text>
              <span
                className={clsx(
                  'block font-medium',
                  getTemperatureColor(gpu.temperature) === 'green' && 'text-green-400',
                  getTemperatureColor(gpu.temperature) === 'yellow' && 'text-yellow-400',
                  getTemperatureColor(gpu.temperature) === 'red' && 'text-red-400'
                )}
                data-testid="gpu-temperature"
              >
                {gpu.temperature}C
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Zap className="h-4 w-4 text-yellow-400" />
            <div>
              <Text className="text-xs text-gray-500">Power</Text>
              <span className="block font-medium text-gray-200" data-testid="gpu-power">
                {gpu.power_watts}W
              </span>
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
}

// ============================================================================
// AI Models Card
// ============================================================================

interface AiModelsCardProps {
  aiModels: Record<string, AiModelMetrics | NemotronMetrics>;
  nemotron: NemotronMetrics | null;
}

function AiModelsCard({ aiModels, nemotron }: AiModelsCardProps) {
  // Combine aiModels and nemotron data
  const models: Array<{ key: string; data: AiModelMetrics | NemotronMetrics }> = [];

  // Add models from aiModels record
  Object.entries(aiModels).forEach(([key, data]) => {
    if (data) {
      models.push({ key, data });
    }
  });

  // Add nemotron if not already present and data exists
  if (nemotron && !models.some((m) => m.key.toLowerCase() === 'nemotron')) {
    models.push({ key: 'nemotron', data: nemotron });
  }

  // Sort models: rtdetr first, nemotron second
  models.sort((a, b) => {
    const order: Record<string, number> = { rtdetr: 0, nemotron: 1 };
    const orderA = order[a.key.toLowerCase()] ?? 99;
    const orderB = order[b.key.toLowerCase()] ?? 99;
    return orderA - orderB;
  });

  return (
    <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="ai-models-card">
      <Title className="mb-4 flex items-center gap-2 text-white">
        <Brain className="h-5 w-5 text-[#76B900]" />
        AI Models
      </Title>

      {models.length === 0 ? (
        <div className="flex h-32 items-center justify-center">
          <Text className="text-gray-500">No AI model data available</Text>
        </div>
      ) : (
        <div className="space-y-3">
          {models.map(({ key, data }) => {
            const displayName = key.toLowerCase() === 'rtdetr' ? 'RT-DETRv2' : capitalize(key);
            const isLlm = isNemotronMetrics(data);
            const Icon = isLlm ? Brain : Cpu;

            return (
              <div
                key={key}
                className="rounded-lg border border-gray-700 bg-gray-800/50 p-3"
                data-testid={`ai-model-${key}`}
              >
                <div className="mb-2 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Icon className="h-4 w-4 text-[#76B900]" />
                    <Text className="font-medium text-gray-200">{displayName}</Text>
                  </div>
                  <Badge
                    color={getStatusColor(data.status)}
                    size="sm"
                    data-testid={`ai-model-${key}-status`}
                  >
                    {capitalize(data.status)}
                  </Badge>
                </div>

                {isLlm && isNemotronMetrics(data) && (
                  <div className="flex items-center justify-between text-sm text-gray-400">
                    <span className="flex items-center gap-1">
                      <Layers className="h-3 w-3" />
                      Slots: {data.slots_active}/{data.slots_total}
                    </span>
                    <span>{data.context_size.toLocaleString()} tokens</span>
                  </div>
                )}

                {!isLlm && isAiModelMetrics(data) && (
                  <div className="flex items-center justify-between text-sm text-gray-400">
                    <span className="flex items-center gap-1">
                      <MemoryStick className="h-3 w-3" />
                      VRAM: {data.vram_gb.toFixed(2)} GB
                    </span>
                    <span>{data.device}</span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}

// ============================================================================
// Database Card
// ============================================================================

interface DatabaseCardProps {
  databases: Record<string, DatabaseMetrics | RedisMetrics>;
}

function DatabaseCard({ databases }: DatabaseCardProps) {
  const postgresql = databases.postgresql;
  const postgresqlData = postgresql && isDatabaseMetrics(postgresql) ? postgresql : null;

  return (
    <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="database-card">
      <Title className="mb-4 flex items-center gap-2 text-white">
        <Database className="h-5 w-5 text-[#76B900]" />
        PostgreSQL
      </Title>

      {!postgresqlData ? (
        <div className="flex h-32 items-center justify-center">
          <Text className="text-gray-500">No database data available</Text>
        </div>
      ) : (
        <div className="space-y-3">
          {/* Status */}
          <div className="flex items-center justify-between">
            <Text className="text-sm text-gray-400">Status</Text>
            <Badge color={getStatusColor(postgresqlData.status)} size="sm" data-testid="db-status">
              {capitalize(postgresqlData.status)}
            </Badge>
          </div>

          {/* Connections */}
          <div>
            <div className="mb-1 flex items-center justify-between">
              <Text className="flex items-center gap-1 text-sm text-gray-400">
                <Users className="h-4 w-4" />
                Connections
              </Text>
              <span className="text-sm text-gray-200" data-testid="db-connections">
                {postgresqlData.connections_active}/{postgresqlData.connections_max}
              </span>
            </div>
            <ProgressBar
              value={(postgresqlData.connections_active / postgresqlData.connections_max) * 100}
              color={getUsageColor(
                (postgresqlData.connections_active / postgresqlData.connections_max) * 100
              )}
              className="h-2"
            />
          </div>

          {/* Cache Hit Ratio */}
          <div className="flex items-center justify-between">
            <Text className="flex items-center gap-1 text-sm text-gray-400">
              <Zap className="h-4 w-4" />
              Cache Hit Ratio
            </Text>
            <span
              className={clsx(
                'text-sm font-medium',
                postgresqlData.cache_hit_ratio >= 90 && 'text-green-400',
                postgresqlData.cache_hit_ratio >= 80 &&
                  postgresqlData.cache_hit_ratio < 90 &&
                  'text-yellow-400',
                postgresqlData.cache_hit_ratio < 80 && 'text-red-400'
              )}
              data-testid="db-cache-hit"
            >
              {postgresqlData.cache_hit_ratio.toFixed(1)}%
            </span>
          </div>

          {/* Transactions */}
          <div className="flex items-center justify-between">
            <Text className="flex items-center gap-1 text-sm text-gray-400">
              <Activity className="h-4 w-4" />
              Transactions
            </Text>
            <span className="text-sm text-gray-200" data-testid="db-transactions">
              {postgresqlData.transactions_per_min}/min
            </span>
          </div>
        </div>
      )}
    </Card>
  );
}

// ============================================================================
// Redis Card
// ============================================================================

interface RedisCardProps {
  databases: Record<string, DatabaseMetrics | RedisMetrics>;
}

function RedisCard({ databases }: RedisCardProps) {
  const redis = databases.redis;
  const redisData = redis && isRedisMetrics(redis) ? redis : null;

  return (
    <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="redis-card">
      <Title className="mb-4 flex items-center gap-2 text-white">
        <HardDrive className="h-5 w-5 text-red-400" />
        Redis
      </Title>

      {!redisData ? (
        <div className="flex h-32 items-center justify-center">
          <Text className="text-gray-500">No Redis data available</Text>
        </div>
      ) : (
        <div className="space-y-3">
          {/* Status */}
          <div className="flex items-center justify-between">
            <Text className="text-sm text-gray-400">Status</Text>
            <Badge color={getStatusColor(redisData.status)} size="sm" data-testid="redis-status">
              {capitalize(redisData.status)}
            </Badge>
          </div>

          {/* Memory */}
          <div className="flex items-center justify-between">
            <Text className="flex items-center gap-1 text-sm text-gray-400">
              <MemoryStick className="h-4 w-4" />
              Memory
            </Text>
            <span className="text-sm text-gray-200" data-testid="redis-memory">
              {redisData.memory_mb.toFixed(2)} MB
            </span>
          </div>

          {/* Hit Ratio */}
          <div className="flex items-center justify-between">
            <Text className="flex items-center gap-1 text-sm text-gray-400">
              <Zap className="h-4 w-4" />
              Hit Ratio
            </Text>
            <span
              className={clsx(
                'text-sm font-medium',
                redisData.hit_ratio >= 50 && 'text-green-400',
                redisData.hit_ratio >= 10 && redisData.hit_ratio < 50 && 'text-yellow-400',
                redisData.hit_ratio < 10 && 'text-red-400'
              )}
              data-testid="redis-hit-ratio"
            >
              {redisData.hit_ratio.toFixed(1)}%
            </span>
          </div>

          {/* Connected Clients */}
          <div className="flex items-center justify-between">
            <Text className="flex items-center gap-1 text-sm text-gray-400">
              <Users className="h-4 w-4" />
              Clients
            </Text>
            <span className="text-sm text-gray-200" data-testid="redis-clients">
              {redisData.connected_clients}
            </span>
          </div>
        </div>
      )}
    </Card>
  );
}

// ============================================================================
// Host Card
// ============================================================================

interface HostCardProps {
  host: HostMetrics | null;
}

function HostCard({ host }: HostCardProps) {
  if (!host) {
    return (
      <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="host-card">
        <Title className="mb-4 flex items-center gap-2 text-white">
          <Monitor className="h-5 w-5 text-[#76B900]" />
          Host System
        </Title>
        <div className="flex h-32 items-center justify-center">
          <Text className="text-gray-500">No host data available</Text>
        </div>
      </Card>
    );
  }

  const ramPercent = Math.round((host.ram_used_gb / host.ram_total_gb) * 100);
  const diskPercent = Math.round((host.disk_used_gb / host.disk_total_gb) * 100);

  return (
    <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="host-card">
      <Title className="mb-4 flex items-center gap-2 text-white">
        <Monitor className="h-5 w-5 text-[#76B900]" />
        Host System
      </Title>

      <div className="space-y-4">
        {/* CPU */}
        <div>
          <div className="mb-1 flex items-center justify-between">
            <Text className="flex items-center gap-1 text-sm text-gray-400">
              <Cpu className="h-4 w-4" />
              CPU
            </Text>
            <span
              className={clsx(
                'text-sm font-medium',
                getUsageColor(host.cpu_percent) === 'green' && 'text-green-400',
                getUsageColor(host.cpu_percent) === 'yellow' && 'text-yellow-400',
                getUsageColor(host.cpu_percent) === 'red' && 'text-red-400'
              )}
              data-testid="host-cpu"
            >
              {host.cpu_percent}%
            </span>
          </div>
          <ProgressBar
            value={host.cpu_percent}
            color={getUsageColor(host.cpu_percent)}
            className="h-2"
            data-testid="host-cpu-bar"
          />
        </div>

        {/* RAM */}
        <div>
          <div className="mb-1 flex items-center justify-between">
            <Text className="flex items-center gap-1 text-sm text-gray-400">
              <MemoryStick className="h-4 w-4" />
              RAM
            </Text>
            <span className="text-sm text-gray-200" data-testid="host-ram">
              {host.ram_used_gb.toFixed(1)}/{host.ram_total_gb.toFixed(1)} GB ({ramPercent}%)
            </span>
          </div>
          <ProgressBar
            value={ramPercent}
            color={getUsageColor(ramPercent, { warning: 85, critical: 95 })}
            className="h-2"
            data-testid="host-ram-bar"
          />
        </div>

        {/* Disk */}
        <div>
          <div className="mb-1 flex items-center justify-between">
            <Text className="flex items-center gap-1 text-sm text-gray-400">
              <HardDrive className="h-4 w-4" />
              Disk
            </Text>
            <span className="text-sm text-gray-200" data-testid="host-disk">
              {host.disk_used_gb.toFixed(1)}/{host.disk_total_gb.toFixed(1)} GB ({diskPercent}%)
            </span>
          </div>
          <ProgressBar
            value={diskPercent}
            color={getUsageColor(diskPercent, { warning: 80, critical: 90 })}
            className="h-2"
            data-testid="host-disk-bar"
          />
        </div>
      </div>
    </Card>
  );
}

// ============================================================================
// Containers Card
// ============================================================================

interface ContainersCardProps {
  containers: ContainerMetrics[];
}

function ContainersCard({ containers }: ContainersCardProps) {
  const healthyCount = containers.filter((c) => c.health.toLowerCase() === 'healthy').length;

  function getHealthIcon(health: string) {
    switch (health.toLowerCase()) {
      case 'healthy':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'unhealthy':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'starting':
        return <AlertCircle className="h-4 w-4 text-yellow-500" />;
      default:
        return <AlertCircle className="h-4 w-4 text-gray-500" />;
    }
  }

  return (
    <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="containers-card">
      <div className="mb-4 flex items-center justify-between">
        <Title className="flex items-center gap-2 text-white">
          <Box className="h-5 w-5 text-[#76B900]" />
          Containers
        </Title>
        <Badge
          color={healthyCount === containers.length ? 'green' : 'red'}
          size="sm"
          data-testid="containers-summary"
        >
          {healthyCount}/{containers.length} Healthy
        </Badge>
      </div>

      {containers.length === 0 ? (
        <div className="flex h-32 items-center justify-center">
          <Text className="text-gray-500">No container data available</Text>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {containers.map((container) => (
            <div
              key={container.name}
              className={clsx(
                'flex items-center gap-2 rounded-lg border p-2',
                container.health.toLowerCase() === 'healthy'
                  ? 'border-gray-700 bg-gray-800/50'
                  : container.health.toLowerCase() === 'starting'
                    ? 'border-yellow-500/30 bg-yellow-500/10'
                    : 'border-red-500/30 bg-red-500/10'
              )}
              data-testid={`container-${container.name}`}
            >
              {getHealthIcon(container.health)}
              <Text className="truncate text-sm text-gray-200">{container.name}</Text>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

// ============================================================================
// Connection Status Indicator
// ============================================================================

interface ConnectionStatusProps {
  isConnected: boolean;
}

function ConnectionStatus({ isConnected }: ConnectionStatusProps) {
  return (
    <div
      className={clsx(
        'flex items-center gap-2 rounded-lg px-3 py-1.5',
        isConnected ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'
      )}
      data-testid="connection-status"
    >
      {isConnected ? (
        <>
          <Wifi className="h-4 w-4" />
          <span className="text-sm font-medium">Connected</span>
        </>
      ) : (
        <>
          <WifiOff className="h-4 w-4" />
          <span className="text-sm font-medium">Disconnected</span>
        </>
      )}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * PerformanceDashboard - Main dashboard component displaying real-time performance metrics.
 *
 * Displays:
 * - GPU Card: utilization %, VRAM %, temperature, power
 * - AI Models Card: RT-DETRv2 and Nemotron status with slots info
 * - Database Card: PostgreSQL connections, cache hit ratio, transactions/min
 * - Redis Card: memory usage, hit ratio, connected clients
 * - Host Card: CPU %, RAM %, disk %
 * - Containers Status: list with health badges
 * - Time Range Selector: 5m/15m/60m tabs
 *
 * @example
 * ```tsx
 * <PerformanceDashboard />
 * ```
 */
export function PerformanceDashboard({ className }: PerformanceDashboardProps) {
  const { current, isConnected, timeRange, setTimeRange } = usePerformanceMetrics();

  return (
    <div className={clsx('space-y-6', className)} data-testid="performance-dashboard">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">System Performance</h1>
          <p className="text-sm text-gray-400">Real-time metrics updated every 5 seconds</p>
        </div>
        <div className="flex items-center gap-4">
          <TimeRangeSelector selectedRange={timeRange} onRangeChange={setTimeRange} />
          <ConnectionStatus isConnected={isConnected} />
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {/* GPU */}
        <GpuCard gpu={current?.gpu ?? null} />

        {/* AI Models */}
        <AiModelsCard aiModels={current?.ai_models ?? {}} nemotron={current?.nemotron ?? null} />

        {/* Database */}
        <DatabaseCard databases={current?.databases ?? {}} />

        {/* Redis */}
        <RedisCard databases={current?.databases ?? {}} />

        {/* Host System */}
        <HostCard host={current?.host ?? null} />

        {/* Containers */}
        <ContainersCard containers={current?.containers ?? []} />
      </div>
    </div>
  );
}

export default PerformanceDashboard;
