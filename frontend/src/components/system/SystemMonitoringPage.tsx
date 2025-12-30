import { Card, Title, Text, Badge, Metric } from '@tremor/react';
import { clsx } from 'clsx';
import {
  Server,
  Clock,
  Camera,
  AlertCircle,
  Activity,
  CheckCircle,
  XCircle,
  AlertTriangle,
} from 'lucide-react';
import { useEffect, useState } from 'react';

import WorkerStatusPanel from './WorkerStatusPanel';
import { useHealthStatus } from '../../hooks/useHealthStatus';
import {
  fetchStats,
  fetchTelemetry,
  fetchGPUStats,
  type GPUStats,
  type TelemetryResponse,
  type ServiceStatus,
} from '../../services/api';
import GpuStats from '../dashboard/GpuStats';
import PipelineQueues from '../dashboard/PipelineQueues';

/**
 * SystemStats from the /api/system/stats endpoint
 */
interface SystemStatsData {
  total_cameras: number;
  total_events: number;
  total_detections: number;
  uptime_seconds: number;
}

/**
 * Formats uptime seconds into a human-readable string
 */
function formatUptime(seconds: number): string {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);

  const parts: string[] = [];
  if (days > 0) parts.push(`${days}d`);
  if (hours > 0) parts.push(`${hours}h`);
  if (minutes > 0) parts.push(`${minutes}m`);

  return parts.length > 0 ? parts.join(' ') : '< 1m';
}

/**
 * Gets the badge color for service status
 */
function getServiceStatusColor(status: string): 'green' | 'yellow' | 'red' | 'gray' {
  switch (status) {
    case 'healthy':
      return 'green';
    case 'degraded':
      return 'yellow';
    case 'unhealthy':
      return 'red';
    default:
      return 'gray';
  }
}

/**
 * Gets the icon for service status
 */
function ServiceStatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'healthy':
      return <CheckCircle className="h-4 w-4 text-green-500" />;
    case 'degraded':
      return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
    case 'unhealthy':
      return <XCircle className="h-4 w-4 text-red-500" />;
    default:
      return <AlertCircle className="h-4 w-4 text-gray-500" />;
  }
}

/**
 * SystemMonitoringPage - Comprehensive system monitoring dashboard
 *
 * Aggregates system metrics from multiple endpoints:
 * - GET /api/system/stats - Total cameras/events/detections/uptime
 * - GET /api/system/health - Detailed service health
 * - GET /api/system/telemetry - Queue depths + latency percentiles
 * - GET /api/system/gpu - Current GPU metrics
 *
 * Reuses existing components:
 * - PipelineQueues - Shows detection and analysis queue depths
 * - GpuStats - Shows GPU utilization, memory, temperature, and FPS
 *
 * Features NVIDIA dark theme styling with green accents.
 */
export default function SystemMonitoringPage() {
  // State for fetched data
  const [stats, setStats] = useState<SystemStatsData | null>(null);
  const [telemetry, setTelemetry] = useState<TelemetryResponse | null>(null);
  const [gpuStats, setGpuStats] = useState<GPUStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Use the health status hook for service health
  const {
    health,
    services,
    overallStatus,
    isLoading: healthLoading,
  } = useHealthStatus({
    pollingInterval: 30000,
  });

  // Fetch initial data
  useEffect(() => {
    async function loadData() {
      setLoading(true);
      setError(null);

      try {
        const [statsData, telemetryData, gpuData] = await Promise.all([
          fetchStats(),
          fetchTelemetry(),
          fetchGPUStats(),
        ]);

        setStats(statsData as SystemStatsData);
        setTelemetry(telemetryData);
        setGpuStats(gpuData);
      } catch (err) {
        console.error('Failed to load system monitoring data:', err);
        setError(err instanceof Error ? err.message : 'Failed to load system data');
      } finally {
        setLoading(false);
      }
    }

    void loadData();
  }, []);

  // Poll for telemetry and GPU updates every 5 seconds
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const [telemetryData, gpuData] = await Promise.all([fetchTelemetry(), fetchGPUStats()]);
        setTelemetry(telemetryData);
        setGpuStats(gpuData);
      } catch (err) {
        console.error('Failed to update telemetry/GPU data:', err);
      }
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  // Loading state
  if (loading || healthLoading) {
    return (
      <div className="min-h-screen bg-[#121212] p-8" data-testid="system-monitoring-loading">
        <div className="mx-auto max-w-[1920px]">
          {/* Header skeleton */}
          <div className="mb-8">
            <div className="h-10 w-72 animate-pulse rounded-lg bg-gray-800"></div>
            <div className="mt-2 h-5 w-96 animate-pulse rounded-lg bg-gray-800"></div>
          </div>

          {/* Grid skeleton */}
          <div className="grid gap-6 lg:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 6 }, (_, i) => (
              <div key={i} className="h-64 animate-pulse rounded-lg bg-gray-800"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div
        className="flex min-h-screen items-center justify-center bg-[#121212] p-8"
        data-testid="system-monitoring-error"
      >
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-6 text-center">
          <AlertCircle className="mx-auto mb-4 h-12 w-12 text-red-500" />
          <h2 className="mb-2 text-xl font-bold text-red-500">Error Loading System Data</h2>
          <p className="text-sm text-gray-300">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 rounded-md bg-red-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-600"
          >
            Reload Page
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#121212] p-8" data-testid="system-monitoring-page">
      <div className="mx-auto max-w-[1920px]">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3">
            <Server className="h-8 w-8 text-[#76B900]" />
            <h1 className="text-4xl font-bold text-white">System Monitoring</h1>
          </div>
          <p className="mt-2 text-sm text-gray-400">
            Real-time system metrics, service health, and pipeline performance
          </p>
        </div>

        {/* Main Grid */}
        <div className="grid gap-6 lg:grid-cols-2 xl:grid-cols-3">
          {/* System Overview Card */}
          <Card
            className="border-gray-800 bg-[#1A1A1A] shadow-lg"
            data-testid="system-overview-card"
          >
            <Title className="mb-4 flex items-center gap-2 text-white">
              <Activity className="h-5 w-5 text-[#76B900]" />
              System Overview
            </Title>

            <div className="space-y-4">
              {/* Uptime */}
              <div className="flex items-center justify-between rounded-lg bg-gray-800/50 p-3">
                <div className="flex items-center gap-2">
                  <Clock className="h-4 w-4 text-gray-400" />
                  <Text className="text-gray-300">Uptime</Text>
                </div>
                <Metric className="text-lg text-[#76B900]">
                  {stats ? formatUptime(stats.uptime_seconds) : 'N/A'}
                </Metric>
              </div>

              {/* Total Cameras */}
              <div className="flex items-center justify-between rounded-lg bg-gray-800/50 p-3">
                <div className="flex items-center gap-2">
                  <Camera className="h-4 w-4 text-gray-400" />
                  <Text className="text-gray-300">Total Cameras</Text>
                </div>
                <Metric className="text-lg text-white">{stats?.total_cameras ?? 0}</Metric>
              </div>

              {/* Total Events */}
              <div className="flex items-center justify-between rounded-lg bg-gray-800/50 p-3">
                <div className="flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 text-gray-400" />
                  <Text className="text-gray-300">Total Events</Text>
                </div>
                <Metric className="text-lg text-white">
                  {stats?.total_events?.toLocaleString() ?? 0}
                </Metric>
              </div>

              {/* Total Detections */}
              <div className="flex items-center justify-between rounded-lg bg-gray-800/50 p-3">
                <div className="flex items-center gap-2">
                  <Activity className="h-4 w-4 text-gray-400" />
                  <Text className="text-gray-300">Total Detections</Text>
                </div>
                <Metric className="text-lg text-white">
                  {stats?.total_detections?.toLocaleString() ?? 0}
                </Metric>
              </div>
            </div>
          </Card>

          {/* Service Health Card */}
          <Card
            className="border-gray-800 bg-[#1A1A1A] shadow-lg"
            data-testid="service-health-card"
          >
            <div className="mb-4 flex items-center justify-between">
              <Title className="flex items-center gap-2 text-white">
                <CheckCircle className="h-5 w-5 text-[#76B900]" />
                Service Health
              </Title>
              {overallStatus && (
                <Badge
                  color={getServiceStatusColor(overallStatus)}
                  size="lg"
                  data-testid="overall-health-badge"
                >
                  {overallStatus.charAt(0).toUpperCase() + overallStatus.slice(1)}
                </Badge>
              )}
            </div>

            <div className="space-y-3">
              {Object.entries(services).length > 0 ? (
                Object.entries(services).map(([serviceName, serviceStatus]) => (
                  <ServiceHealthRow key={serviceName} name={serviceName} status={serviceStatus} />
                ))
              ) : (
                <Text className="text-gray-500">No service data available</Text>
              )}
            </div>

            {health?.timestamp && (
              <Text className="mt-4 text-xs text-gray-500">
                Last checked: {new Date(health.timestamp).toLocaleTimeString()}
              </Text>
            )}
          </Card>

          {/* Background Workers Panel - Shows status of all 8 workers */}
          <WorkerStatusPanel pollingInterval={10000} />

          {/* Pipeline Queues Card - Reusing existing component */}
          <PipelineQueues
            detectionQueue={telemetry?.queues.detection_queue ?? 0}
            analysisQueue={telemetry?.queues.analysis_queue ?? 0}
            warningThreshold={10}
          />

          {/* GPU Stats Card - Reusing existing component (spans 2 columns on xl) */}
          <div className="xl:col-span-2">
            <GpuStats
              gpuName={gpuStats?.gpu_name ?? null}
              utilization={gpuStats?.utilization ?? null}
              memoryUsed={gpuStats?.memory_used ?? null}
              memoryTotal={gpuStats?.memory_total ?? null}
              temperature={gpuStats?.temperature ?? null}
              powerUsage={gpuStats?.power_usage ?? null}
              inferenceFps={gpuStats?.inference_fps ?? null}
            />
          </div>

          {/* Latency Stats Card */}
          {telemetry?.latencies && (
            <Card
              className="border-gray-800 bg-[#1A1A1A] shadow-lg"
              data-testid="latency-stats-card"
            >
              <Title className="mb-4 flex items-center gap-2 text-white">
                <Clock className="h-5 w-5 text-[#76B900]" />
                Pipeline Latency
              </Title>

              <div className="space-y-4">
                {/* Detection Latency */}
                {telemetry.latencies.detect && (
                  <div className="rounded-lg bg-gray-800/50 p-3">
                    <Text className="mb-2 text-sm font-medium text-gray-300">
                      Detection (RT-DETRv2)
                    </Text>
                    <div className="grid grid-cols-3 gap-2 text-center">
                      <div>
                        <Text className="text-xs text-gray-500">Avg</Text>
                        <Text className="font-medium text-white">
                          {telemetry.latencies.detect.avg_ms?.toFixed(0) ?? 'N/A'}ms
                        </Text>
                      </div>
                      <div>
                        <Text className="text-xs text-gray-500">P95</Text>
                        <Text className="font-medium text-white">
                          {telemetry.latencies.detect.p95_ms?.toFixed(0) ?? 'N/A'}ms
                        </Text>
                      </div>
                      <div>
                        <Text className="text-xs text-gray-500">P99</Text>
                        <Text className="font-medium text-white">
                          {telemetry.latencies.detect.p99_ms?.toFixed(0) ?? 'N/A'}ms
                        </Text>
                      </div>
                    </div>
                  </div>
                )}

                {/* Analysis Latency */}
                {telemetry.latencies.analyze && (
                  <div className="rounded-lg bg-gray-800/50 p-3">
                    <Text className="mb-2 text-sm font-medium text-gray-300">
                      Analysis (Nemotron)
                    </Text>
                    <div className="grid grid-cols-3 gap-2 text-center">
                      <div>
                        <Text className="text-xs text-gray-500">Avg</Text>
                        <Text className="font-medium text-white">
                          {telemetry.latencies.analyze.avg_ms?.toFixed(0) ?? 'N/A'}ms
                        </Text>
                      </div>
                      <div>
                        <Text className="text-xs text-gray-500">P95</Text>
                        <Text className="font-medium text-white">
                          {telemetry.latencies.analyze.p95_ms?.toFixed(0) ?? 'N/A'}ms
                        </Text>
                      </div>
                      <div>
                        <Text className="text-xs text-gray-500">P99</Text>
                        <Text className="font-medium text-white">
                          {telemetry.latencies.analyze.p99_ms?.toFixed(0) ?? 'N/A'}ms
                        </Text>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {telemetry.timestamp && (
                <Text className="mt-4 text-xs text-gray-500">
                  Updated: {new Date(telemetry.timestamp).toLocaleTimeString()}
                </Text>
              )}
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * ServiceHealthRow - Displays a single service's health status
 */
interface ServiceHealthRowProps {
  name: string;
  status: ServiceStatus;
}

function ServiceHealthRow({ name, status }: ServiceHealthRowProps) {
  // Format service name for display (e.g., "redis" -> "Redis", "rtdetr_server" -> "RT-DETR Server")
  const displayName = name
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');

  return (
    <div
      className={clsx(
        'flex items-center justify-between rounded-lg p-3',
        status.status === 'unhealthy' && 'border border-red-500/30 bg-red-500/10',
        status.status === 'degraded' && 'border border-yellow-500/30 bg-yellow-500/10',
        status.status === 'healthy' && 'bg-gray-800/50',
        status.status !== 'healthy' &&
          status.status !== 'degraded' &&
          status.status !== 'unhealthy' &&
          'bg-gray-800/50'
      )}
      data-testid={`service-row-${name}`}
    >
      <div className="flex items-center gap-2">
        <ServiceStatusIcon status={status.status} />
        <div>
          <Text className="text-sm font-medium text-gray-300">{displayName}</Text>
          {status.message && <Text className="text-xs text-gray-500">{status.message}</Text>}
        </div>
      </div>
      <Badge color={getServiceStatusColor(status.status)} size="sm">
        {status.status}
      </Badge>
    </div>
  );
}
