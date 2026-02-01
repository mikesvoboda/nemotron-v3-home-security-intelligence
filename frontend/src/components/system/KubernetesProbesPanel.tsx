import { Card, Title, Text, Badge } from '@tremor/react';
import { clsx } from 'clsx';
import {
  HeartPulse,
  CheckCircle,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Loader2,
  Activity,
} from 'lucide-react';
import { useEffect, useState, useCallback, useRef } from 'react';

import { fetchLivenessProbe, fetchReadiness } from '../../services/api';

/**
 * Props for KubernetesProbesPanel component
 */
export interface KubernetesProbesPanelProps {
  /** Polling interval in milliseconds (default: 15000) */
  pollingInterval?: number;
  /** Additional CSS classes */
  className?: string;
  /** Optional data-testid attribute for testing */
  'data-testid'?: string;
}

/**
 * Probe status type
 */
type ProbeStatus = 'healthy' | 'unhealthy' | 'unknown';

/**
 * Combined probes data
 */
interface ProbesData {
  liveness: {
    status: ProbeStatus;
    timestamp: string | null;
    responseTime?: number;
  };
  readiness: {
    status: ProbeStatus;
    ready: boolean;
    statusText: string;
    timestamp: string | null;
    responseTime?: number;
    workersHealthy: number;
    workersTotal: number;
    servicesHealthy: number;
    servicesTotal: number;
    supervisorHealthy: boolean;
  };
}

/**
 * Get badge color for probe status
 */
function getStatusColor(status: ProbeStatus): 'emerald' | 'red' | 'gray' {
  switch (status) {
    case 'healthy':
      return 'emerald';
    case 'unhealthy':
      return 'red';
    default:
      return 'gray';
  }
}

/**
 * Status icon component
 */
function StatusIcon({ status }: { status: ProbeStatus }) {
  switch (status) {
    case 'healthy':
      return <CheckCircle className="h-5 w-5 text-green-500" data-testid="probe-status-healthy" />;
    case 'unhealthy':
      return <XCircle className="h-5 w-5 text-red-500" data-testid="probe-status-unhealthy" />;
    default:
      return <AlertTriangle className="h-5 w-5 text-gray-500" data-testid="probe-status-unknown" />;
  }
}

/**
 * Probe card component
 */
interface ProbeCardProps {
  name: string;
  displayName: string;
  description: string;
  status: ProbeStatus;
  details?: React.ReactNode;
  responseTime?: number;
  timestamp?: string | null;
}

function ProbeCard({
  name,
  displayName,
  description,
  status,
  details,
  responseTime,
  timestamp,
}: ProbeCardProps) {
  return (
    <div
      className={clsx(
        'rounded-lg border p-4 transition-colors',
        status === 'healthy' && 'border-gray-700 bg-gray-800/50',
        status === 'unhealthy' && 'border-red-500/30 bg-red-500/10',
        status === 'unknown' && 'border-gray-600 bg-gray-800/30'
      )}
      data-testid={`probe-card-${name}`}
    >
      <div className="flex items-start justify-between gap-3">
        {/* Left side: Icon and info */}
        <div className="flex items-start gap-3">
          <StatusIcon status={status} />
          <div className="flex flex-col">
            <Text className="text-sm font-medium text-gray-200">{displayName}</Text>
            <Text className="text-xs text-gray-500">{description}</Text>
            {responseTime !== undefined && (
              <Text className="mt-1 text-xs text-gray-400">
                Response time: {responseTime.toFixed(0)}ms
              </Text>
            )}
            {details && <div className="mt-2">{details}</div>}
          </div>
        </div>

        {/* Right side: Status badge */}
        <Badge
          color={getStatusColor(status)}
          size="sm"
          data-testid={`probe-status-badge-${name}`}
        >
          {status === 'healthy' ? 'Passing' : status === 'unhealthy' ? 'Failing' : 'Unknown'}
        </Badge>
      </div>

      {/* Timestamp */}
      {timestamp && (
        <Text className="mt-2 text-xs text-gray-500">
          Last check: {new Date(timestamp).toLocaleTimeString()}
        </Text>
      )}
    </div>
  );
}

/**
 * KubernetesProbesPanel - Displays Kubernetes liveness and readiness probe status (NEM-4950)
 *
 * Shows:
 * - Liveness probe status (indicates process is running)
 * - Readiness probe status (indicates application can handle traffic)
 * - Worker and service health summaries
 * - Response times for each probe
 */
export default function KubernetesProbesPanel({
  pollingInterval = 15000,
  className,
  'data-testid': testId = 'kubernetes-probes-panel',
}: KubernetesProbesPanelProps) {
  const [data, setData] = useState<ProbesData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  // Track if component is mounted
  const isMountedRef = useRef(true);

  // Fetch both probe statuses
  const fetchData = useCallback(async (isRefresh = false) => {
    if (!isMountedRef.current) return;

    if (isRefresh) {
      setRefreshing(true);
    }

    try {
      // Fetch both probes in parallel with timing
      const livenessStart = performance.now();
      const readinessStart = performance.now();

      const [livenessResult, readinessResult] = await Promise.allSettled([
        fetchLivenessProbe(),
        fetchReadiness(),
      ]);

      const livenessTime = performance.now() - livenessStart;
      const readinessTime = performance.now() - readinessStart;

      if (!isMountedRef.current) return;

      // Process liveness result
      let livenessData: ProbesData['liveness'];
      if (livenessResult.status === 'fulfilled') {
        const liveness = livenessResult.value;
        livenessData = {
          status: liveness.status === 'alive' ? 'healthy' : 'unhealthy',
          timestamp: liveness.timestamp,
          responseTime: livenessTime,
        };
      } else {
        livenessData = {
          status: 'unhealthy',
          timestamp: null,
          responseTime: livenessTime,
        };
      }

      // Process readiness result
      let readinessData: ProbesData['readiness'];
      if (readinessResult.status === 'fulfilled') {
        const readiness = readinessResult.value;
        const services = readiness.services || {};
        const workers = readiness.workers || [];

        const servicesHealthy = Object.values(services).filter(
          (s) => s.status === 'healthy'
        ).length;
        const workersHealthy = workers.filter((w) => w.running).length;

        readinessData = {
          status: readiness.ready ? 'healthy' : 'unhealthy',
          ready: readiness.ready,
          statusText: readiness.status,
          timestamp: readiness.timestamp,
          responseTime: readinessTime,
          workersHealthy,
          workersTotal: workers.length,
          servicesHealthy,
          servicesTotal: Object.keys(services).length,
          supervisorHealthy: readiness.supervisor_healthy ?? true,
        };
      } else {
        readinessData = {
          status: 'unhealthy',
          ready: false,
          statusText: 'not_ready',
          timestamp: null,
          responseTime: readinessTime,
          workersHealthy: 0,
          workersTotal: 0,
          servicesHealthy: 0,
          servicesTotal: 0,
          supervisorHealthy: false,
        };
      }

      setData({
        liveness: livenessData,
        readiness: readinessData,
      });
      setError(null);
      setLoading(false);
      setRefreshing(false);
    } catch (err) {
      if (isMountedRef.current) {
        console.error('Failed to fetch probes:', err);
        setError(err instanceof Error ? err.message : 'Failed to fetch probes');
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, []);

  // Initial fetch
  useEffect(() => {
    isMountedRef.current = true;
    void fetchData();

    return () => {
      isMountedRef.current = false;
    };
  }, [fetchData]);

  // Polling
  useEffect(() => {
    if (pollingInterval <= 0) return;

    const intervalId = setInterval(() => {
      void fetchData();
    }, pollingInterval);

    return () => clearInterval(intervalId);
  }, [pollingInterval, fetchData]);

  // Handle refresh button click
  const handleRefresh = () => {
    void fetchData(true);
  };

  // Calculate overall health
  const allHealthy = data?.liveness.status === 'healthy' && data?.readiness.status === 'healthy';
  const hasIssues = data !== null && !allHealthy;

  // Loading state
  if (loading) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid={`${testId}-loading`}
      >
        <Title className="mb-4 flex items-center gap-2 text-white">
          <HeartPulse className="h-5 w-5 text-[#76B900]" />
          Kubernetes Probes
        </Title>
        <div className="space-y-3">
          {Array.from({ length: 2 }, (_, i) => (
            <div key={i} className="h-24 animate-pulse rounded-lg bg-gray-800"></div>
          ))}
        </div>
      </Card>
    );
  }

  // Error state
  if (error && !data) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid={`${testId}-error`}
      >
        <Title className="mb-4 flex items-center gap-2 text-white">
          <HeartPulse className="h-5 w-5 text-[#76B900]" />
          Kubernetes Probes
        </Title>
        <div className="flex items-center gap-3 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <XCircle className="h-5 w-5 text-red-500" />
          <div>
            <Text className="text-sm font-medium text-red-400">Failed to load</Text>
            <Text className="text-xs text-gray-400">{error}</Text>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card
      className={clsx(
        'border-gray-800 bg-[#1A1A1A] shadow-lg',
        hasIssues && 'border-yellow-500/30',
        className
      )}
      data-testid={testId}
    >
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <Title className="flex items-center gap-2 text-white">
          <HeartPulse className="h-5 w-5 text-[#76B900]" />
          Kubernetes Probes
        </Title>
        <div className="flex items-center gap-2">
          <Badge
            color={allHealthy ? 'emerald' : hasIssues ? 'red' : 'gray'}
            size="sm"
            data-testid="probes-overall-badge"
          >
            {allHealthy ? 'All Passing' : hasIssues ? 'Issues Detected' : 'Unknown'}
          </Badge>
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="rounded p-1 text-gray-400 transition-colors hover:bg-gray-700 hover:text-white disabled:opacity-50"
            data-testid="probes-refresh-btn"
            title="Refresh probes"
          >
            {refreshing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
          </button>
        </div>
      </div>

      {/* Probe cards */}
      <div className="space-y-3">
        {/* Liveness Probe */}
        <ProbeCard
          name="liveness"
          displayName="Liveness Probe"
          description="Indicates the process is running and can handle HTTP requests"
          status={data?.liveness.status ?? 'unknown'}
          responseTime={data?.liveness.responseTime}
          timestamp={data?.liveness.timestamp}
        />

        {/* Readiness Probe */}
        <ProbeCard
          name="readiness"
          displayName="Readiness Probe"
          description="Indicates the application is ready to receive traffic"
          status={data?.readiness.status ?? 'unknown'}
          responseTime={data?.readiness.responseTime}
          timestamp={data?.readiness.timestamp}
          details={
            data?.readiness && (
              <div className="flex flex-wrap gap-2">
                <Badge
                  color={
                    data.readiness.servicesHealthy === data.readiness.servicesTotal
                      ? 'emerald'
                      : 'yellow'
                  }
                  size="xs"
                  data-testid="readiness-services-badge"
                >
                  <Activity className="mr-1 h-3 w-3" />
                  Services: {data.readiness.servicesHealthy}/{data.readiness.servicesTotal}
                </Badge>
                <Badge
                  color={
                    data.readiness.workersHealthy === data.readiness.workersTotal
                      ? 'emerald'
                      : 'yellow'
                  }
                  size="xs"
                  data-testid="readiness-workers-badge"
                >
                  Workers: {data.readiness.workersHealthy}/{data.readiness.workersTotal}
                </Badge>
                {!data.readiness.supervisorHealthy && (
                  <Badge color="red" size="xs" data-testid="readiness-supervisor-badge">
                    Supervisor Unhealthy
                  </Badge>
                )}
              </div>
            )
          }
        />
      </div>

      {/* Info text */}
      <div className="mt-4 rounded-lg bg-gray-800/50 p-3">
        <Text className="text-xs text-gray-400">
          <strong>Liveness:</strong> Used by Kubernetes to determine if the container needs to be
          restarted. Checks if the process is alive.
        </Text>
        <Text className="mt-1 text-xs text-gray-400">
          <strong>Readiness:</strong> Used by Kubernetes to determine if the container can receive
          traffic. Checks database, Redis, and worker status.
        </Text>
      </div>
    </Card>
  );
}
