import { ProgressBar, Text } from '@tremor/react';
import { clsx } from 'clsx';
import {
  Database,
  Server,
  Box,
  Monitor,
  Zap,
  CheckCircle,
  XCircle,
  AlertTriangle,
  AlertCircle,
  ChevronDown,
} from 'lucide-react';

// ============================================================================
// Type Definitions
// ============================================================================

/**
 * PostgreSQL infrastructure details
 */
export interface PostgreSQLDetails {
  status: 'healthy' | 'degraded' | 'unhealthy';
  latency_ms: number;
  pool_active: number;
  pool_max: number;
  active_queries: number;
  db_size_gb: number;
}

/**
 * Redis infrastructure details
 */
export interface RedisDetails {
  status: 'healthy' | 'degraded' | 'unhealthy';
  ops_per_sec: number;
  memory_mb: number;
  connected_clients: number;
  hit_rate: number;
}

/**
 * Single container metrics
 */
export interface ContainerInfo {
  name: string;
  status: 'running' | 'stopped' | 'restarting';
  cpu_percent: number;
  memory_mb: number;
  restart_count: number;
}

/**
 * Containers infrastructure details
 */
export interface ContainerDetails {
  status: 'healthy' | 'degraded' | 'unhealthy';
  running: number;
  total: number;
  containers: ContainerInfo[];
}

/**
 * Host system infrastructure details
 */
export interface HostDetails {
  status: 'healthy' | 'degraded' | 'unhealthy';
  cpu_percent: number;
  memory_used_gb: number;
  memory_total_gb: number;
  disk_used_gb: number;
  disk_total_gb: number;
}

/**
 * Single circuit breaker info
 */
export interface CircuitBreakerInfo {
  name: string;
  state: 'closed' | 'open' | 'half_open' | 'unavailable';
  failure_count: number;
}

/**
 * Circuit breakers infrastructure details
 */
export interface CircuitDetails {
  status: 'healthy' | 'degraded' | 'unhealthy';
  healthy: number;
  total: number;
  breakers: CircuitBreakerInfo[];
}

/**
 * Complete infrastructure data
 */
export interface InfrastructureData {
  postgresql: PostgreSQLDetails | null;
  redis: RedisDetails | null;
  containers: ContainerDetails | null;
  host: HostDetails | null;
  circuits: CircuitDetails | null;
}

/**
 * Card identifier for accordion expansion
 */
export type InfrastructureCardId = 'postgresql' | 'redis' | 'containers' | 'host' | 'circuits';

/**
 * Props for InfrastructureStatusGrid component
 */
export interface InfrastructureStatusGridProps {
  /** Infrastructure data from API */
  data: InfrastructureData;
  /** Loading state */
  loading: boolean;
  /** Error message if fetch failed */
  error: string | null;
  /** Callback when a card is clicked */
  onCardClick: (cardId: InfrastructureCardId | null) => void;
  /** Currently expanded card (null = all collapsed) */
  expandedCard: InfrastructureCardId | null;
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Format operations per second with k suffix
 */
function formatOpsPerSec(ops: number): string {
  if (ops >= 10000) {
    return `${Math.round(ops / 1000)}k/s`;
  }
  if (ops >= 1000) {
    return `${(ops / 1000).toFixed(1)}k/s`;
  }
  return `${ops}/s`;
}

/**
 * Get border color class based on status
 */
function getStatusBorderClass(status: 'healthy' | 'degraded' | 'unhealthy' | null): string {
  switch (status) {
    case 'healthy':
      return 'border-gray-700 hover:border-[#76B900]';
    case 'degraded':
      return 'border-yellow-500';
    case 'unhealthy':
      return 'border-red-500';
    default:
      return 'border-gray-700';
  }
}

/**
 * Get status icon component
 */
function StatusIcon({ status }: { status: 'healthy' | 'degraded' | 'unhealthy' | null }) {
  switch (status) {
    case 'healthy':
      return <CheckCircle className="h-5 w-5 text-green-500" />;
    case 'degraded':
      return <AlertTriangle className="h-5 w-5 text-yellow-500" />;
    case 'unhealthy':
      return <XCircle className="h-5 w-5 text-red-500" />;
    default:
      return <AlertCircle className="h-5 w-5 text-gray-500" />;
  }
}

/**
 * Get color for progress bar based on percentage
 */
function getProgressColor(percent: number): 'green' | 'yellow' | 'red' {
  if (percent >= 90) return 'red';
  if (percent >= 75) return 'yellow';
  return 'green';
}

/**
 * Get circuit state styling
 */
function getCircuitStateClass(state: 'closed' | 'open' | 'half_open' | 'unavailable'): string {
  switch (state) {
    case 'closed':
      return 'text-green-400';
    case 'open':
      return 'text-red-400';
    case 'half_open':
      return 'text-yellow-400';
    case 'unavailable':
      return 'text-gray-500';
    default:
      return 'text-gray-400';
  }
}

// ============================================================================
// Sub-Components
// ============================================================================

/**
 * Loading skeleton for infrastructure grid
 */
function LoadingSkeleton() {
  return (
    <div
      className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5"
      data-testid="infrastructure-grid-loading"
    >
      {[1, 2, 3, 4, 5].map((i) => (
        <div
          key={i}
          className="h-24 animate-pulse rounded-lg border border-gray-700 bg-gray-800/50"
        />
      ))}
    </div>
  );
}

/**
 * Error display for infrastructure grid
 */
function ErrorDisplay({ message }: { message: string }) {
  return (
    <div
      className="flex items-center gap-3 rounded-lg border border-red-500/30 bg-red-500/10 p-4"
      data-testid="infrastructure-grid-error"
    >
      <AlertCircle className="h-5 w-5 text-red-500" />
      <Text className="text-red-400">{message}</Text>
    </div>
  );
}

/**
 * Single infrastructure card
 */
interface InfraCardProps {
  id: InfrastructureCardId;
  title: string;
  icon: React.ReactNode;
  status: 'healthy' | 'degraded' | 'unhealthy' | null;
  metric: string;
  isExpanded: boolean;
  onClick: () => void;
}

function InfraCard({ id, title, icon, status, metric, isExpanded, onClick }: InfraCardProps) {
  return (
    <button
      className={clsx(
        'flex w-full flex-col items-center justify-center rounded-lg border p-3 text-center transition-all',
        'bg-gray-800/50 hover:bg-gray-800',
        'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#121212]',
        getStatusBorderClass(status),
        isExpanded && 'ring-2 ring-[#76B900]'
      )}
      onClick={onClick}
      data-testid={`infra-card-${id}`}
      aria-expanded={isExpanded}
      aria-controls={`infra-details-${id}`}
    >
      <div className="mb-1 flex items-center gap-1.5">
        {icon}
        <Text className="text-sm font-medium text-gray-200">{title}</Text>
      </div>
      <div className="mb-1" data-testid={`infra-status-icon-${id}`}>
        <StatusIcon status={status} />
      </div>
      <span className="text-xs text-gray-400" data-testid={`infra-metric-${id}`}>
        {metric}
      </span>
      <ChevronDown
        className={clsx(
          'mt-1 h-3 w-3 text-gray-500 transition-transform',
          isExpanded && 'rotate-180'
        )}
      />
    </button>
  );
}

/**
 * PostgreSQL detail panel
 */
function PostgreSQLDetails({ data }: { data: PostgreSQLDetails }) {
  const poolPercent = Math.round((data.pool_active / data.pool_max) * 100);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <Text className="text-sm text-gray-400">Pool usage:</Text>
        <Text className="text-sm text-gray-200">{data.pool_active}/{data.pool_max} active</Text>
      </div>
      <ProgressBar value={poolPercent} color={getProgressColor(poolPercent)} className="h-1.5" />

      <div className="flex items-center justify-between">
        <Text className="text-sm text-gray-400">Query latency:</Text>
        <Text className="text-sm text-gray-200">{data.latency_ms}ms</Text>
      </div>

      <div className="flex items-center justify-between">
        <Text className="text-sm text-gray-400">Active queries:</Text>
        <Text className="text-sm text-gray-200">{data.active_queries}</Text>
      </div>

      <div className="flex items-center justify-between">
        <Text className="text-sm text-gray-400">DB size:</Text>
        <Text className="text-sm text-gray-200">{data.db_size_gb.toFixed(1)} GB</Text>
      </div>
    </div>
  );
}

/**
 * Redis detail panel
 */
function RedisDetailsPanel({ data }: { data: RedisDetails }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <Text className="text-sm text-gray-400">Memory usage:</Text>
        <Text className="text-sm text-gray-200">{data.memory_mb} MB</Text>
      </div>

      <div className="flex items-center justify-between">
        <Text className="text-sm text-gray-400">Ops/sec:</Text>
        <Text className="text-sm text-gray-200">{data.ops_per_sec.toLocaleString()}</Text>
      </div>

      <div className="flex items-center justify-between">
        <Text className="text-sm text-gray-400">Connected clients:</Text>
        <Text className="text-sm text-gray-200">{data.connected_clients}</Text>
      </div>

      <div className="flex items-center justify-between">
        <Text className="text-sm text-gray-400">Hit rate:</Text>
        <Text className="text-sm text-gray-200">{data.hit_rate.toFixed(1)}%</Text>
      </div>
    </div>
  );
}

/**
 * Containers detail panel
 */
function ContainersDetailsPanel({ data }: { data: ContainerDetails }) {
  return (
    <div className="space-y-2">
      <div className="grid grid-cols-5 gap-2 text-xs font-medium text-gray-500">
        <span>Container</span>
        <span>Status</span>
        <span className="text-right">CPU</span>
        <span className="text-right">Memory</span>
        <span className="text-right">Restarts</span>
      </div>
      {data.containers.map((container) => {
        const hasHighRestarts = container.restart_count >= 3;
        return (
          <div
            key={container.name}
            className={clsx(
              'grid grid-cols-5 gap-2 text-xs',
              hasHighRestarts ? 'text-yellow-400' : 'text-gray-300'
            )}
            data-testid={`container-row-${container.name}`}
          >
            <span className="truncate">{container.name}</span>
            <span className={container.status === 'running' ? 'text-green-400' : 'text-red-400'}>
              {container.status}
            </span>
            <span className="text-right">{container.cpu_percent}%</span>
            <span className="text-right">{container.memory_mb}MB</span>
            <span className="text-right">
              {container.restart_count > 0 ? `${container.restart_count} restart${container.restart_count > 1 ? 's' : ''}` : '0'}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/**
 * Host system detail panel
 */
function HostDetailsPanel({ data }: { data: HostDetails }) {
  const memoryPercent = Math.round((data.memory_used_gb / data.memory_total_gb) * 100);
  const diskPercent = Math.round((data.disk_used_gb / data.disk_total_gb) * 100);

  return (
    <div className="space-y-4">
      <div>
        <div className="mb-1.5 flex items-center justify-between">
          <Text className="text-sm text-gray-400">CPU</Text>
          <Text className="text-sm text-gray-200">{data.cpu_percent}%</Text>
        </div>
        <ProgressBar
          value={data.cpu_percent}
          color={getProgressColor(data.cpu_percent)}
          className="h-2"
          data-testid="host-cpu-bar"
        />
      </div>

      <div>
        <div className="mb-1.5 flex items-center justify-between">
          <Text className="text-sm text-gray-400">Memory</Text>
          <Text className="text-sm text-gray-200">
            {data.memory_used_gb}/{data.memory_total_gb} GB ({memoryPercent}%)
          </Text>
        </div>
        <ProgressBar
          value={memoryPercent}
          color={getProgressColor(memoryPercent)}
          className="h-2"
          data-testid="host-memory-bar"
        />
      </div>

      <div>
        <div className="mb-1.5 flex items-center justify-between">
          <Text className="text-sm text-gray-400">Disk</Text>
          <Text className="text-sm text-gray-200">
            {data.disk_used_gb}/{data.disk_total_gb} GB ({diskPercent}%)
          </Text>
        </div>
        <ProgressBar
          value={diskPercent}
          color={getProgressColor(diskPercent)}
          className="h-2"
          data-testid="host-disk-bar"
        />
      </div>
    </div>
  );
}

/**
 * Circuit breakers detail panel
 */
function CircuitsDetailsPanel({ data }: { data: CircuitDetails }) {
  return (
    <div className="space-y-2">
      <div className="grid grid-cols-3 gap-2 text-xs font-medium text-gray-500">
        <span>Circuit</span>
        <span>State</span>
        <span className="text-right">Failures</span>
      </div>
      {data.breakers.map((breaker) => (
        <div
          key={breaker.name}
          className={clsx('grid grid-cols-3 gap-2 text-xs', getCircuitStateClass(breaker.state))}
          data-testid={`circuit-row-${breaker.name}`}
        >
          <span className="truncate">{breaker.name}</span>
          <span>{breaker.state}</span>
          <span className="text-right">{breaker.failure_count}</span>
        </div>
      ))}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * InfrastructureStatusGrid - Compact 5-card grid showing infrastructure status
 *
 * Shows at-a-glance status for:
 * - PostgreSQL: connection pool, latency, query activity
 * - Redis: memory, ops/sec, hit rate
 * - Containers: running/total count, individual status
 * - Host: CPU, memory, disk usage
 * - Circuits: circuit breaker states
 *
 * Click any card to expand details below (accordion - one at a time).
 * Lazy loads detail data on expand.
 */
export default function InfrastructureStatusGrid({
  data,
  loading,
  error,
  onCardClick,
  expandedCard,
  className,
}: InfrastructureStatusGridProps) {
  // Handle loading state
  if (loading) {
    return <LoadingSkeleton />;
  }

  // Handle error state
  if (error) {
    return <ErrorDisplay message={error} />;
  }

  // Handle card click - toggle if same card, otherwise switch
  const handleCardClick = (cardId: InfrastructureCardId) => {
    if (expandedCard === cardId) {
      onCardClick(null);
    } else {
      onCardClick(cardId);
    }
  };

  // Build card configurations
  const cards: {
    id: InfrastructureCardId;
    title: string;
    icon: React.ReactNode;
    status: 'healthy' | 'degraded' | 'unhealthy' | null;
    metric: string;
  }[] = [
    {
      id: 'postgresql',
      title: 'PostgreSQL',
      icon: <Database className="h-4 w-4 text-blue-400" />,
      status: data.postgresql?.status ?? null,
      metric: data.postgresql ? `${data.postgresql.latency_ms}ms` : '--',
    },
    {
      id: 'redis',
      title: 'Redis',
      icon: <Server className="h-4 w-4 text-red-400" />,
      status: data.redis?.status ?? null,
      metric: data.redis ? formatOpsPerSec(data.redis.ops_per_sec) : '--',
    },
    {
      id: 'containers',
      title: 'Containers',
      icon: <Box className="h-4 w-4 text-purple-400" />,
      status: data.containers?.status ?? null,
      metric: data.containers ? `${data.containers.running}/${data.containers.total}` : '--',
    },
    {
      id: 'host',
      title: 'Host',
      icon: <Monitor className="h-4 w-4 text-orange-400" />,
      status: data.host?.status ?? null,
      metric: data.host ? `CPU ${data.host.cpu_percent}%` : '--',
    },
    {
      id: 'circuits',
      title: 'Circuits',
      icon: <Zap className="h-4 w-4 text-[#76B900]" />,
      status: data.circuits?.status ?? null,
      metric: data.circuits ? `${data.circuits.healthy}/${data.circuits.total}` : '--',
    },
  ];

  // Render expanded details based on current card
  const renderExpandedDetails = () => {
    if (!expandedCard) return null;

    let content: React.ReactNode = null;

    switch (expandedCard) {
      case 'postgresql':
        content = data.postgresql ? (
          <PostgreSQLDetails data={data.postgresql} />
        ) : (
          <Text className="text-gray-500">No data available</Text>
        );
        break;
      case 'redis':
        content = data.redis ? (
          <RedisDetailsPanel data={data.redis} />
        ) : (
          <Text className="text-gray-500">No data available</Text>
        );
        break;
      case 'containers':
        content = data.containers ? (
          <ContainersDetailsPanel data={data.containers} />
        ) : (
          <Text className="text-gray-500">No data available</Text>
        );
        break;
      case 'host':
        content = data.host ? (
          <HostDetailsPanel data={data.host} />
        ) : (
          <Text className="text-gray-500">No data available</Text>
        );
        break;
      case 'circuits':
        content = data.circuits ? (
          <CircuitsDetailsPanel data={data.circuits} />
        ) : (
          <Text className="text-gray-500">No data available</Text>
        );
        break;
    }

    const card = cards.find((c) => c.id === expandedCard);

    return (
      <div
        className="mt-3 rounded-lg border border-gray-700 bg-gray-800/30 p-4"
        role="region"
        aria-label={`${card?.title} details`}
        data-testid={`infra-details-${expandedCard}`}
      >
        <div className="mb-3 flex items-center gap-2">
          {card?.icon}
          <Text className="font-medium text-gray-200">{card?.title} Details</Text>
        </div>
        {content}
      </div>
    );
  };

  return (
    <div
      className={clsx('space-y-0', className)}
      data-testid="infrastructure-status-grid"
    >
      {/* Status Cards Grid */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {cards.map((card) => (
          <InfraCard
            key={card.id}
            id={card.id}
            title={card.title}
            icon={card.icon}
            status={card.status}
            metric={card.metric}
            isExpanded={expandedCard === card.id}
            onClick={() => handleCardClick(card.id)}
          />
        ))}
      </div>

      {/* Expanded Details Panel */}
      {renderExpandedDetails()}
    </div>
  );
}
