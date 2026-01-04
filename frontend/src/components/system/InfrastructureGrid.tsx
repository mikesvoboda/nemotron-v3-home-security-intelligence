import { Card, Title, Text, Badge, ProgressBar } from '@tremor/react';
import { clsx } from 'clsx';
import {
  Server,
  Database,
  HardDrive,
  Box,
  Monitor,
  Zap,
  CheckCircle,
  XCircle,
  AlertTriangle,
  ChevronUp,
} from 'lucide-react';
import { useState } from 'react';

/**
 * Infrastructure component status
 */
export type ComponentStatus = 'healthy' | 'degraded' | 'unhealthy' | 'unknown';

/**
 * PostgreSQL component details
 */
export interface PostgresDetails {
  /** Connection pool active/max */
  poolActive?: number;
  poolMax?: number;
  /** Query latency */
  queryLatencyMs?: number;
  queryLatencyP95Ms?: number;
  /** Active queries count */
  activeQueries?: number;
  /** Database size */
  databaseSizeGb?: number;
  /** Last backup timestamp */
  lastBackup?: string;
  /** Cache hit ratio */
  cacheHitRatio?: number;
}

/**
 * Redis component details
 */
export interface RedisDetails {
  /** Memory usage */
  memoryMb?: number;
  memoryMaxMb?: number;
  /** Operations per second */
  opsPerSec?: number;
  /** Connected clients */
  connectedClients?: number;
  /** Hit rate */
  hitRate?: number;
  /** Blocked clients */
  blockedClients?: number;
}

/**
 * Container status
 */
export interface ContainerStatus {
  name: string;
  status: 'running' | 'stopped' | 'unhealthy';
  cpuPercent?: number;
  memoryMb?: number;
  restarts?: number;
}

/**
 * Container component details
 */
export interface ContainersDetails {
  containers: ContainerStatus[];
}

/**
 * Host system details
 */
export interface HostDetails {
  /** CPU usage */
  cpuPercent?: number;
  /** RAM usage */
  ramUsedGb?: number;
  ramTotalGb?: number;
  /** Disk usage */
  diskUsedGb?: number;
  diskTotalGb?: number;
}

/**
 * Circuit breaker status
 */
export interface CircuitBreakerStatus {
  name: string;
  state: 'closed' | 'open' | 'half_open';
  failureCount: number;
}

/**
 * Circuits component details
 */
export interface CircuitsDetails {
  breakers: CircuitBreakerStatus[];
}

/**
 * Infrastructure component
 */
export interface InfraComponent {
  /** Component ID */
  id: 'postgresql' | 'redis' | 'containers' | 'host' | 'circuits';
  /** Display label */
  label: string;
  /** Current status */
  status: ComponentStatus;
  /** Key metric to display in card (e.g., "12ms", "5/5") */
  keyMetric?: string;
  /** Component-specific details */
  details?: PostgresDetails | RedisDetails | ContainersDetails | HostDetails | CircuitsDetails;
}

/**
 * Props for InfrastructureGrid component
 */
export interface InfrastructureGridProps {
  /** PostgreSQL status */
  postgresql: InfraComponent;
  /** Redis status */
  redis: InfraComponent;
  /** Containers status */
  containers: InfraComponent;
  /** Host system status */
  host: InfraComponent;
  /** Circuit breakers status */
  circuits: InfraComponent;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Get status icon
 */
function StatusIcon({ status }: { status: ComponentStatus }) {
  switch (status) {
    case 'healthy':
      return <CheckCircle className="h-5 w-5 text-green-500" />;
    case 'degraded':
      return <AlertTriangle className="h-5 w-5 text-yellow-500" />;
    case 'unhealthy':
      return <XCircle className="h-5 w-5 text-red-500" />;
    default:
      return <AlertTriangle className="h-5 w-5 text-gray-500" />;
  }
}

/**
 * Get component icon
 */
function ComponentIcon({ id, className }: { id: InfraComponent['id']; className?: string }) {
  const baseClass = clsx('h-5 w-5', className);

  switch (id) {
    case 'postgresql':
      return <Database className={baseClass} />;
    case 'redis':
      return <HardDrive className={baseClass} />;
    case 'containers':
      return <Box className={baseClass} />;
    case 'host':
      return <Monitor className={baseClass} />;
    case 'circuits':
      return <Zap className={baseClass} />;
    default:
      return <Server className={baseClass} />;
  }
}

/**
 * Status card for each infrastructure component
 */
interface StatusCardProps {
  component: InfraComponent;
  isSelected: boolean;
  onClick: () => void;
}

function StatusCard({ component, isSelected, onClick }: StatusCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={clsx(
        'flex flex-col items-center justify-center rounded-lg border p-3 transition-all duration-200 cursor-pointer min-w-[80px]',
        isSelected
          ? 'border-[#76B900] bg-[#76B900]/10'
          : component.status === 'healthy'
            ? 'border-gray-700 bg-gray-800/50 hover:border-gray-600'
            : component.status === 'degraded'
              ? 'border-yellow-500/30 bg-yellow-500/10 hover:border-yellow-500/50'
              : component.status === 'unhealthy'
                ? 'border-red-500/30 bg-red-500/10 hover:border-red-500/50'
                : 'border-gray-700 bg-gray-800/50 hover:border-gray-600'
      )}
      data-testid={`infra-card-${component.id}`}
    >
      <ComponentIcon id={component.id} className="text-gray-400" />
      <Text className="mt-1 text-xs font-semibold text-white">{component.label}</Text>
      <StatusIcon status={component.status} />
      {component.keyMetric && (
        <Text className="mt-1 text-xs text-gray-400">{component.keyMetric}</Text>
      )}
    </button>
  );
}

/**
 * PostgreSQL detail panel
 */
function PostgresDetailPanel({ details }: { details: PostgresDetails }) {
  const poolPercent = details.poolMax
    ? ((details.poolActive ?? 0) / details.poolMax) * 100
    : 0;

  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
      <div>
        <Text className="text-xs text-gray-500">Connection Pool</Text>
        <Text className="text-sm font-medium text-white">
          {details.poolActive ?? 0}/{details.poolMax ?? 20} active
        </Text>
        <ProgressBar value={poolPercent} color="blue" className="mt-1 h-1" />
      </div>
      <div>
        <Text className="text-xs text-gray-500">Query Latency</Text>
        <Text className="text-sm font-medium text-white">
          {details.queryLatencyMs ?? '-'}ms avg
        </Text>
        <Text className="text-xs text-gray-600">
          {details.queryLatencyP95Ms ?? '-'}ms p95
        </Text>
      </div>
      <div>
        <Text className="text-xs text-gray-500">Active Queries</Text>
        <Text className="text-sm font-medium text-white">{details.activeQueries ?? 0}</Text>
      </div>
      <div>
        <Text className="text-xs text-gray-500">Database Size</Text>
        <Text className="text-sm font-medium text-white">
          {details.databaseSizeGb?.toFixed(2) ?? '-'} GB
        </Text>
      </div>
      {details.cacheHitRatio !== undefined && (
        <div>
          <Text className="text-xs text-gray-500">Cache Hit Ratio</Text>
          <Text className="text-sm font-medium text-white">
            {details.cacheHitRatio.toFixed(1)}%
          </Text>
        </div>
      )}
      {details.lastBackup && (
        <div>
          <Text className="text-xs text-gray-500">Last Backup</Text>
          <Text className="text-sm font-medium text-white">{details.lastBackup}</Text>
        </div>
      )}
    </div>
  );
}

/**
 * Redis detail panel
 */
function RedisDetailPanel({ details }: { details: RedisDetails }) {
  const memoryPercent = details.memoryMaxMb
    ? ((details.memoryMb ?? 0) / details.memoryMaxMb) * 100
    : 0;

  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
      <div>
        <Text className="text-xs text-gray-500">Memory Usage</Text>
        <Text className="text-sm font-medium text-white">
          {details.memoryMb?.toFixed(1) ?? '-'} MB
        </Text>
        {details.memoryMaxMb && (
          <ProgressBar value={memoryPercent} color="red" className="mt-1 h-1" />
        )}
      </div>
      <div>
        <Text className="text-xs text-gray-500">Operations/sec</Text>
        <Text className="text-sm font-medium text-white">
          {details.opsPerSec?.toLocaleString() ?? '-'}
        </Text>
      </div>
      <div>
        <Text className="text-xs text-gray-500">Connected Clients</Text>
        <Text className="text-sm font-medium text-white">{details.connectedClients ?? '-'}</Text>
      </div>
      <div>
        <Text className="text-xs text-gray-500">Hit Rate</Text>
        <Text className="text-sm font-medium text-white">
          {details.hitRate?.toFixed(1) ?? '-'}%
        </Text>
      </div>
      {details.blockedClients !== undefined && details.blockedClients > 0 && (
        <div>
          <Text className="text-xs text-gray-500">Blocked Clients</Text>
          <Text className="text-sm font-medium text-red-400">{details.blockedClients}</Text>
        </div>
      )}
    </div>
  );
}

/**
 * Containers detail panel
 */
function ContainersDetailPanel({ details }: { details: ContainersDetails }) {
  return (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
      {details.containers.map((container) => (
        <div
          key={container.name}
          className={clsx(
            'flex items-center justify-between rounded-md px-3 py-2',
            container.status === 'running' ? 'bg-gray-800/50' : 'bg-red-500/10'
          )}
        >
          <div className="flex items-center gap-2">
            <div
              className={clsx(
                'h-2 w-2 rounded-full',
                container.status === 'running' ? 'bg-green-500' : 'bg-red-500'
              )}
            />
            <Text className="text-sm text-white">{container.name}</Text>
          </div>
          <div className="flex items-center gap-2 text-xs text-gray-500">
            {container.cpuPercent !== undefined && (
              <span>CPU: {container.cpuPercent}%</span>
            )}
            {container.memoryMb !== undefined && (
              <span>Mem: {container.memoryMb}MB</span>
            )}
            {container.restarts !== undefined && container.restarts > 0 && (
              <Badge color="red" size="xs">{container.restarts} restarts</Badge>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * Host system detail panel
 */
function HostDetailPanel({ details }: { details: HostDetails }) {
  const ramPercent = details.ramTotalGb
    ? ((details.ramUsedGb ?? 0) / details.ramTotalGb) * 100
    : 0;
  const diskPercent = details.diskTotalGb
    ? ((details.diskUsedGb ?? 0) / details.diskTotalGb) * 100
    : 0;

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
      <div>
        <div className="mb-1 flex items-center justify-between">
          <Text className="text-xs text-gray-500">CPU</Text>
          <Text className="text-sm font-medium text-white">{details.cpuPercent ?? '-'}%</Text>
        </div>
        <ProgressBar
          value={details.cpuPercent ?? 0}
          color={
            (details.cpuPercent ?? 0) > 90
              ? 'red'
              : (details.cpuPercent ?? 0) > 70
                ? 'yellow'
                : 'blue'
          }
          className="h-2"
        />
      </div>
      <div>
        <div className="mb-1 flex items-center justify-between">
          <Text className="text-xs text-gray-500">RAM</Text>
          <Text className="text-sm font-medium text-white">
            {details.ramUsedGb?.toFixed(1) ?? '-'}/{details.ramTotalGb?.toFixed(0) ?? '-'} GB
          </Text>
        </div>
        <ProgressBar
          value={ramPercent}
          color={ramPercent > 90 ? 'red' : ramPercent > 70 ? 'yellow' : 'violet'}
          className="h-2"
        />
      </div>
      <div>
        <div className="mb-1 flex items-center justify-between">
          <Text className="text-xs text-gray-500">Disk</Text>
          <Text className="text-sm font-medium text-white">
            {details.diskUsedGb?.toFixed(0) ?? '-'}/{details.diskTotalGb?.toFixed(0) ?? '-'} GB
          </Text>
        </div>
        <ProgressBar
          value={diskPercent}
          color={diskPercent > 90 ? 'red' : diskPercent > 80 ? 'yellow' : 'orange'}
          className="h-2"
        />
      </div>
    </div>
  );
}

/**
 * Circuit breakers detail panel
 */
function CircuitsDetailPanel({ details }: { details: CircuitsDetails }) {
  return (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
      {details.breakers.map((breaker) => (
        <div
          key={breaker.name}
          className={clsx(
            'flex items-center justify-between rounded-md px-3 py-2',
            breaker.state === 'closed'
              ? 'bg-gray-800/50'
              : breaker.state === 'open'
                ? 'bg-red-500/10'
                : 'bg-yellow-500/10'
          )}
        >
          <div className="flex items-center gap-2">
            <Zap
              className={clsx(
                'h-4 w-4',
                breaker.state === 'closed'
                  ? 'text-green-500'
                  : breaker.state === 'open'
                    ? 'text-red-500'
                    : 'text-yellow-500'
              )}
            />
            <Text className="text-sm text-white">{breaker.name}</Text>
          </div>
          <div className="flex items-center gap-2">
            {breaker.failureCount > 0 && (
              <Text className="text-xs text-red-400">{breaker.failureCount} failures</Text>
            )}
            <Badge
              color={
                breaker.state === 'closed'
                  ? 'green'
                  : breaker.state === 'open'
                    ? 'red'
                    : 'yellow'
              }
              size="xs"
            >
              {breaker.state}
            </Badge>
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * Detail panel wrapper that renders the appropriate detail component
 */
function DetailPanel({ component }: { component: InfraComponent }) {
  if (!component.details) {
    return (
      <div className="py-4 text-center">
        <Text className="text-gray-500">No details available</Text>
      </div>
    );
  }

  switch (component.id) {
    case 'postgresql':
      return <PostgresDetailPanel details={component.details as PostgresDetails} />;
    case 'redis':
      return <RedisDetailPanel details={component.details as RedisDetails} />;
    case 'containers':
      return <ContainersDetailPanel details={component.details as ContainersDetails} />;
    case 'host':
      return <HostDetailPanel details={component.details as HostDetails} />;
    case 'circuits':
      return <CircuitsDetailPanel details={component.details as CircuitsDetails} />;
    default:
      return null;
  }
}

/**
 * InfrastructureGrid - Infrastructure status grid with expandable detail panels
 *
 * Displays 5 compact status cards in a row:
 * - PostgreSQL
 * - Redis
 * - Containers
 * - Host System
 * - Circuit Breakers
 *
 * Features:
 * - Clickable cards that expand to show details below
 * - Accordion style (one panel at a time)
 * - Color-coded status indicators
 * - Component-specific detail panels
 *
 * @example
 * ```tsx
 * <InfrastructureGrid
 *   postgresql={{ id: 'postgresql', label: 'PostgreSQL', status: 'healthy', keyMetric: '12ms' }}
 *   redis={{ id: 'redis', label: 'Redis', status: 'healthy', keyMetric: '1.2k/s' }}
 *   containers={{ id: 'containers', label: 'Containers', status: 'healthy', keyMetric: '5/5' }}
 *   host={{ id: 'host', label: 'Host', status: 'healthy', keyMetric: 'CPU 12%' }}
 *   circuits={{ id: 'circuits', label: 'Circuits', status: 'healthy', keyMetric: '3/3' }}
 * />
 * ```
 */
export default function InfrastructureGrid({
  postgresql,
  redis,
  containers,
  host,
  circuits,
  className,
}: InfrastructureGridProps) {
  const [selectedId, setSelectedId] = useState<InfraComponent['id'] | null>(null);

  const components = [postgresql, redis, containers, host, circuits];
  const selectedComponent = components.find((c) => c.id === selectedId);

  const handleCardClick = (id: InfraComponent['id']) => {
    setSelectedId((current) => (current === id ? null : id));
  };

  // Calculate overall health
  const hasAnyUnhealthy = components.some((c) => c.status === 'unhealthy');
  const hasAnyDegraded = components.some((c) => c.status === 'degraded');

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="infrastructure-grid"
    >
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <Title className="flex items-center gap-2 text-white">
          <Server className="h-5 w-5 text-[#76B900]" />
          Infrastructure
          {(hasAnyUnhealthy || hasAnyDegraded) && (
            <AlertTriangle
              className={clsx('h-4 w-4', hasAnyUnhealthy ? 'text-red-500' : 'text-yellow-500')}
              data-testid="infra-warning-icon"
            />
          )}
        </Title>
      </div>

      {/* Status Cards Grid */}
      <div
        className="flex flex-wrap justify-center gap-3 sm:justify-start"
        data-testid="infra-cards"
      >
        {components.map((component) => (
          <StatusCard
            key={component.id}
            component={component}
            isSelected={selectedId === component.id}
            onClick={() => handleCardClick(component.id)}
          />
        ))}
      </div>

      {/* Expandable Detail Panel */}
      {selectedComponent && (
        <div
          className="mt-4 rounded-lg border border-gray-700 bg-gray-800/30 p-4"
          data-testid="infra-detail-panel"
        >
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ComponentIcon id={selectedComponent.id} className="text-[#76B900]" />
              <Text className="text-sm font-semibold text-white">
                {selectedComponent.label} Details
              </Text>
            </div>
            <button
              type="button"
              onClick={() => setSelectedId(null)}
              className="flex items-center gap-1 text-xs text-gray-400 hover:text-white"
              data-testid="close-detail-btn"
            >
              Close
              <ChevronUp className="h-3 w-3" />
            </button>
          </div>
          <DetailPanel component={selectedComponent} />
        </div>
      )}
    </Card>
  );
}
