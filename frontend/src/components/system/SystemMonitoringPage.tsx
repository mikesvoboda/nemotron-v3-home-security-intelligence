import { Card, Title, Text, Badge, Metric, Callout } from '@tremor/react';
import { clsx } from 'clsx';
import {
  Server,
  AlertCircle,
  Activity,
  CheckCircle,
  XCircle,
  AlertTriangle,
  BarChart2,
  ExternalLink,
} from 'lucide-react';
import { useEffect, useState, useRef } from 'react';

import AiModelsPanel from './AiModelsPanel';
import CircuitBreakerPanel from './CircuitBreakerPanel';
import ContainersPanel from './ContainersPanel';
import DatabasesPanel from './DatabasesPanel';
import HostSystemPanel from './HostSystemPanel';
import InfrastructureStatusGrid from './InfrastructureStatusGrid';
import ModelZooPanel from './ModelZooPanel';
import PerformanceAlerts from './PerformanceAlerts';
import PipelineFlowVisualization from './PipelineFlowVisualization';
import PipelineMetricsPanel from './PipelineMetricsPanel';
import ServicesPanel from './ServicesPanel';
import SystemSummaryRow from './SystemSummaryRow';
import TimeRangeSelector from './TimeRangeSelector';
import WorkerStatusPanel from './WorkerStatusPanel';
import { useHealthStatus } from '../../hooks/useHealthStatus';
import { useModelZooStatus } from '../../hooks/useModelZooStatus';
import { usePerformanceMetrics } from '../../hooks/usePerformanceMetrics';
import {
  fetchStats,
  fetchTelemetry,
  fetchGPUStats,
  fetchConfig,
  fetchCircuitBreakers,
  resetCircuitBreaker,
  type GPUStats,
  type TelemetryResponse,
  type ServiceStatus,
  type CircuitBreakersResponse,
} from '../../services/api';
import GpuStats from '../dashboard/GpuStats';

import type { InfrastructureCardId, InfrastructureData } from './InfrastructureStatusGrid';
import type { PipelineStageData, BackgroundWorkerStatus, TotalLatency } from './PipelineFlowVisualization';
import type { ThroughputPoint } from './PipelineMetricsPanel';
import type { GpuMetricDataPoint } from '../../hooks/useGpuHistory';

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
      return <CheckCircle className="h-3 w-3 text-green-500" />;
    case 'degraded':
      return <AlertTriangle className="h-3 w-3 text-yellow-500" />;
    case 'unhealthy':
      return <XCircle className="h-3 w-3 text-red-500" />;
    default:
      return <AlertCircle className="h-3 w-3 text-gray-500" />;
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
  const [grafanaUrl, setGrafanaUrl] = useState<string>('http://localhost:3002');

  // State for circuit breakers
  const [circuitBreakers, setCircuitBreakers] = useState<CircuitBreakersResponse | null>(null);
  const [circuitBreakersLoading, setCircuitBreakersLoading] = useState(true);
  const [circuitBreakersError, setCircuitBreakersError] = useState<string | null>(null);

  // State for infrastructure grid expanded card
  const [expandedInfraCard, setExpandedInfraCard] = useState<InfrastructureCardId | null>(null);

  // Use the health status hook for service health
  const {
    health,
    services,
    overallStatus,
    isLoading: healthLoading,
    error: healthError,
  } = useHealthStatus({
    pollingInterval: 30000,
  });

  // Use performance metrics hook for real-time dashboard data
  const {
    current: performanceData,
    history: performanceHistory,
    alerts: performanceAlerts,
    timeRange,
    setTimeRange,
  } = usePerformanceMetrics();

  // Use Model Zoo status hook for AI Model Zoo panel
  const {
    models: modelZooModels,
    vramStats: modelZooVramStats,
    isLoading: modelZooLoading,
    error: modelZooError,
    refresh: refreshModelZoo,
  } = useModelZooStatus({ pollingInterval: 10000 });

  // Transform performance history for GPU stats based on selected time range
  const gpuHistoryData: GpuMetricDataPoint[] = (performanceHistory[timeRange] || [])
    .filter((update) => update.gpu !== null)
    .map((update) => ({
      timestamp: update.timestamp,
      utilization: update.gpu?.utilization ?? 0,
      memory_used: (update.gpu?.vram_used_gb ?? 0) * 1024, // Convert GB to MB
      temperature: update.gpu?.temperature ?? 0,
    }));

  // Transform alerts for PerformanceAlerts component
  const transformedAlerts = performanceAlerts.map((alert) => ({
    severity: alert.severity,
    metric: alert.metric,
    value: alert.value,
    threshold: alert.threshold,
    message: alert.message,
  }));

  // Extract AI model metrics dictionary
  // Combine ai_models with nemotron (which comes separately in the API response)
  const aiModelsData = performanceData
    ? {
        ...(performanceData.ai_models ?? {}),
        ...(performanceData.nemotron ? { nemotron: performanceData.nemotron } : {}),
      }
    : null;

  // Extract database metrics
  const postgresMetrics = performanceData?.databases?.postgresql
    ? (performanceData.databases.postgresql as {
        status: string;
        connections_active: number;
        connections_max: number;
        cache_hit_ratio: number;
        transactions_per_min: number;
      })
    : null;

  const redisMetrics = performanceData?.databases?.redis
    ? (performanceData.databases.redis as {
        status: string;
        connected_clients: number;
        memory_mb: number;
        hit_ratio: number;
        blocked_clients: number;
      })
    : null;

  // Create database history data from performance history
  const databaseHistory = {
    postgresql: {
      connections: (performanceHistory[timeRange] || []).map((update) => ({
        timestamp: update.timestamp,
        value:
          (update.databases?.postgresql as { connections_active?: number } | undefined)
            ?.connections_active ?? 0,
      })),
      cache_hit_ratio: (performanceHistory[timeRange] || []).map((update) => ({
        timestamp: update.timestamp,
        value:
          (update.databases?.postgresql as { cache_hit_ratio?: number } | undefined)
            ?.cache_hit_ratio ?? 0,
      })),
    },
    redis: {
      memory: (performanceHistory[timeRange] || []).map((update) => ({
        timestamp: update.timestamp,
        value:
          (update.databases?.redis as { memory_mb?: number } | undefined)?.memory_mb ?? 0,
      })),
      clients: (performanceHistory[timeRange] || []).map((update) => ({
        timestamp: update.timestamp,
        value:
          (update.databases?.redis as { connected_clients?: number } | undefined)
            ?.connected_clients ?? 0,
      })),
    },
  };

  // Extract host metrics
  const hostMetrics = performanceData?.host ?? null;

  // Create host history data
  const hostHistory = {
    cpu: (performanceHistory[timeRange] || []).map((update) => ({
      timestamp: update.timestamp,
      value: update.host?.cpu_percent ?? 0,
    })),
    ram: (performanceHistory[timeRange] || []).map((update) => ({
      timestamp: update.timestamp,
      value: update.host?.ram_used_gb ?? 0,
    })),
  };

  // Extract container metrics
  const containerMetrics = performanceData?.containers ?? [];

  // Create container history data
  const containerHistory: Record<string, { timestamp: string; health: string }[]> = {};
  containerMetrics.forEach((container) => {
    containerHistory[container.name] = (performanceHistory[timeRange] || []).map((update) => {
      const containerData = update.containers?.find((c) => c.name === container.name);
      return {
        timestamp: update.timestamp,
        health: containerData?.health ?? 'unknown',
      };
    });
  });

  // Throughput history for PipelineMetricsPanel
  const [throughputHistory, setThroughputHistory] = useState<ThroughputPoint[]>([]);
  const prevTelemetryRef = useRef<TelemetryResponse | null>(null);
  const prevTimestampRef = useRef<number | null>(null);

  // Calculate throughput from telemetry changes
  useEffect(() => {
    if (!telemetry) return;

    const now = Date.now();
    const timeStr = new Date(telemetry.timestamp).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });

    if (prevTelemetryRef.current && prevTimestampRef.current) {
      const timeDiffMs = now - prevTimestampRef.current;
      const timeDiffMin = timeDiffMs / 60000;

      if (timeDiffMin > 0) {
        const detectionsPerMin = Math.max(
          0,
          Math.round(((prevTelemetryRef.current.queues.detection_queue - telemetry.queues.detection_queue) / timeDiffMin) * 60)
        );
        const analysesPerMin = Math.max(
          0,
          Math.round(((prevTelemetryRef.current.queues.analysis_queue - telemetry.queues.analysis_queue) / timeDiffMin) * 60)
        );

        setThroughputHistory((prev) => {
          const newPoint: ThroughputPoint = {
            time: timeStr,
            detections: detectionsPerMin || (prev.length > 0 ? prev[prev.length - 1].detections : 0),
            analyses: analysesPerMin || (prev.length > 0 ? prev[prev.length - 1].analyses : 0),
          };
          return [...prev.slice(-29), newPoint];
        });
      }
    }

    prevTelemetryRef.current = telemetry;
    prevTimestampRef.current = now;
  }, [telemetry]);

  // Pipeline stages data for PipelineFlowVisualization
  const pipelineStages: PipelineStageData[] = [
    {
      id: 'files',
      name: 'Files',
      icon: 'folder',
      metrics: {
        throughput: performanceData?.inference?.throughput?.files_per_minute
          ? `${performanceData.inference.throughput.files_per_minute.toFixed(0)}/min`
          : undefined,
        pending: telemetry?.queues?.detection_queue ?? 0,
      },
    },
    {
      id: 'detect',
      name: 'Detect',
      icon: 'search',
      metrics: {
        queueDepth: telemetry?.queues?.detection_queue ?? 0,
        avgLatency: telemetry?.latencies?.detect?.avg_ms ?? performanceData?.inference?.rtdetr_latency_ms?.avg ?? null,
        p95Latency: telemetry?.latencies?.detect?.p95_ms ?? performanceData?.inference?.rtdetr_latency_ms?.p95 ?? null,
      },
    },
    {
      id: 'batch',
      name: 'Batch',
      icon: 'package',
      metrics: {
        throughput: throughputHistory.length > 0
          ? `${throughputHistory[throughputHistory.length - 1].detections}/min`
          : undefined,
        pending: telemetry?.queues?.analysis_queue ?? 0,
      },
    },
    {
      id: 'analyze',
      name: 'Analyze',
      icon: 'brain',
      metrics: {
        queueDepth: telemetry?.queues?.analysis_queue ?? 0,
        avgLatency: telemetry?.latencies?.analyze?.avg_ms ?? performanceData?.inference?.nemotron_latency_ms?.avg ?? null,
        p95Latency: telemetry?.latencies?.analyze?.p95_ms ?? performanceData?.inference?.nemotron_latency_ms?.p95 ?? null,
      },
    },
  ];

  // Background workers data for PipelineFlowVisualization
  const backgroundWorkers: BackgroundWorkerStatus[] = [
    {
      id: 'file-watcher',
      name: 'Watcher',
      status: services?.file_watcher?.status === 'healthy' ? 'running' :
              services?.file_watcher?.status === 'degraded' ? 'degraded' : 'stopped',
    },
    {
      id: 'detector',
      name: 'Detector',
      status: services?.rtdetr_server?.status === 'healthy' ? 'running' :
              services?.rtdetr_server?.status === 'degraded' ? 'degraded' : 'stopped',
    },
    {
      id: 'aggregator',
      name: 'Aggregator',
      status: services?.batch_aggregator?.status === 'healthy' ? 'running' :
              services?.batch_aggregator?.status === 'degraded' ? 'degraded' : 'stopped',
    },
    {
      id: 'analyzer',
      name: 'Analyzer',
      status: services?.nemotron_server?.status === 'healthy' ? 'running' :
              services?.nemotron_server?.status === 'degraded' ? 'degraded' : 'stopped',
    },
    {
      id: 'cleanup',
      name: 'Cleanup',
      status: services?.cleanup_service?.status === 'healthy' ? 'running' :
              services?.cleanup_service?.status === 'degraded' ? 'degraded' : 'stopped',
    },
  ];

  // Total pipeline latency for PipelineFlowVisualization
  const totalPipelineLatency: TotalLatency = {
    avg: (telemetry?.latencies?.detect?.avg_ms ?? 0) + (telemetry?.latencies?.analyze?.avg_ms ?? 0),
    p95: (telemetry?.latencies?.detect?.p95_ms ?? 0) + (telemetry?.latencies?.analyze?.p95_ms ?? 0),
    p99: (telemetry?.latencies?.detect?.p99_ms ?? 0) + (telemetry?.latencies?.analyze?.p99_ms ?? 0),
  };

  // Infrastructure data for InfrastructureStatusGrid
  const infrastructureData: InfrastructureData = {
    postgresql: postgresMetrics ? {
      status: postgresMetrics.status === 'healthy' ? 'healthy' :
              postgresMetrics.status === 'degraded' ? 'degraded' : 'unhealthy',
      latency_ms: performanceData?.inference?.pipeline_latency_ms?.db_query ?? 0,
      pool_active: postgresMetrics.connections_active,
      pool_max: postgresMetrics.connections_max,
      active_queries: postgresMetrics.transactions_per_min ?? 0,
      db_size_gb: 0, // Not available from current metrics
    } : null,
    redis: redisMetrics ? {
      status: redisMetrics.status === 'healthy' ? 'healthy' :
              redisMetrics.status === 'degraded' ? 'degraded' : 'unhealthy',
      ops_per_sec: 0, // Not directly available
      memory_mb: redisMetrics.memory_mb,
      connected_clients: redisMetrics.connected_clients,
      hit_rate: redisMetrics.hit_ratio,
    } : null,
    containers: containerMetrics.length > 0 ? {
      status: containerMetrics.every(c => c.status === 'running' && (c.health === 'healthy' || c.health === 'none')) ? 'healthy' :
              containerMetrics.some(c => c.status !== 'running') ? 'unhealthy' : 'degraded',
      running: containerMetrics.filter(c => c.status === 'running').length,
      total: containerMetrics.length,
      containers: containerMetrics.map(c => ({
        name: c.name,
        status: c.status === 'running' ? 'running' : c.status === 'restarting' ? 'restarting' : 'stopped',
        cpu_percent: 0, // Not available from current metrics
        memory_mb: 0, // Not available from current metrics
        restart_count: 0, // Not available from current metrics
      })),
    } : null,
    host: hostMetrics ? {
      status: hostMetrics.cpu_percent < 80 && (hostMetrics.ram_used_gb / hostMetrics.ram_total_gb) < 0.9 ? 'healthy' :
              hostMetrics.cpu_percent < 95 && (hostMetrics.ram_used_gb / hostMetrics.ram_total_gb) < 0.95 ? 'degraded' : 'unhealthy',
      cpu_percent: hostMetrics.cpu_percent,
      memory_used_gb: hostMetrics.ram_used_gb,
      memory_total_gb: hostMetrics.ram_total_gb,
      disk_used_gb: hostMetrics.disk_used_gb,
      disk_total_gb: hostMetrics.disk_total_gb,
    } : null,
    circuits: circuitBreakers ? {
      status: circuitBreakers.open_count === 0 ? 'healthy' :
              circuitBreakers.open_count < circuitBreakers.total_count / 2 ? 'degraded' : 'unhealthy',
      healthy: circuitBreakers.total_count - circuitBreakers.open_count,
      total: circuitBreakers.total_count,
      breakers: Object.values(circuitBreakers.circuit_breakers).map(cb => ({
        name: cb.name,
        state: cb.state,
        failure_count: cb.failure_count,
      })),
    } : null,
  };

  // Fetch Grafana URL from config API
  useEffect(() => {
    const loadConfig = async () => {
      try {
        const config = await fetchConfig();
        // Check for grafana_url in the config response
        // The type may not include grafana_url yet if types haven't been regenerated
        const configWithGrafana = config as typeof config & { grafana_url?: string };
        if (configWithGrafana.grafana_url) {
          setGrafanaUrl(configWithGrafana.grafana_url);
        }
      } catch (err) {
        // Silently fail and keep default URL
        console.error('Failed to fetch config:', err);
      }
    };
    void loadConfig();
  }, []);

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

  // Fetch circuit breakers data
  useEffect(() => {
    async function loadCircuitBreakers() {
      setCircuitBreakersLoading(true);
      setCircuitBreakersError(null);

      try {
        const data = await fetchCircuitBreakers();
        setCircuitBreakers(data);
      } catch (err) {
        console.error('Failed to load circuit breakers:', err);
        setCircuitBreakersError(err instanceof Error ? err.message : 'Failed to load circuit breakers');
      } finally {
        setCircuitBreakersLoading(false);
      }
    }

    void loadCircuitBreakers();
  }, []);

  // Handler for resetting circuit breakers
  const handleResetCircuitBreaker = async (name: string) => {
    try {
      await resetCircuitBreaker(name);
      // Reload circuit breakers data after reset
      const data = await fetchCircuitBreakers();
      setCircuitBreakers(data);
    } catch (err) {
      console.error(`Failed to reset circuit breaker ${name}:`, err);
      setCircuitBreakersError(err instanceof Error ? err.message : `Failed to reset ${name}`);
    }
  };

  // Poll for telemetry and GPU updates every 5 seconds
  // Uses individual try-catch to prevent one failure from stopping all updates
  useEffect(() => {
    const interval = setInterval(async () => {
      // Fetch telemetry separately from GPU stats to isolate failures
      try {
        const telemetryData = await fetchTelemetry();
        setTelemetry(telemetryData);
      } catch (err) {
        // Log but don't block GPU stats fetch
        if (err instanceof Error && err.message !== 'Failed to fetch') {
          console.error('Failed to update telemetry:', err);
        }
        // Silent for network errors to avoid console spam during connectivity issues
      }

      try {
        const gpuData = await fetchGPUStats();
        setGpuStats(gpuData);
      } catch (err) {
        // Log but don't block other updates
        if (err instanceof Error && err.message !== 'Failed to fetch') {
          console.error('Failed to update GPU stats:', err);
        }
        // Silent for network errors to avoid console spam during connectivity issues
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
        {/* Header with TimeRangeSelector */}
        <div className="mb-8 flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3">
              <Server className="h-8 w-8 text-[#76B900]" />
              <h1 className="text-4xl font-bold text-white">System Monitoring</h1>
            </div>
            <p className="mt-2 text-sm text-gray-400">
              Real-time system metrics, service health, and pipeline performance
            </p>
          </div>
          <TimeRangeSelector
            selectedRange={timeRange}
            onRangeChange={setTimeRange}
            data-testid="system-time-range-selector"
          />
        </div>

        {/* Grafana Monitoring Banner */}
        <Callout
          title="Monitoring Dashboard Available"
          icon={BarChart2}
          color="blue"
          className="mb-6"
          data-testid="grafana-monitoring-banner"
        >
          <span className="inline-flex flex-wrap items-center gap-2">
            <span>
              View detailed metrics and historical data in Grafana.
              No login required (anonymous access enabled).
            </span>
            <a
              href={grafanaUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 font-medium text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
              data-testid="grafana-link"
            >
              Open Grafana
              <ExternalLink className="h-4 w-4" />
            </a>
          </span>
        </Callout>

        {/* Performance Alerts - Prominent banner at top when alerts active */}
        {transformedAlerts.length > 0 && (
          <PerformanceAlerts
            alerts={transformedAlerts}
            className="mb-4"
            data-testid="system-performance-alerts"
          />
        )}

        {/* Summary Row - Five clickable indicators for quick system health overview */}
        <SystemSummaryRow
          className="mb-6"
          data-testid="system-summary-row"
        />

        {/* Pipeline Flow Visualization - Visual diagram of the pipeline flow */}
        <PipelineFlowVisualization
          stages={pipelineStages}
          workers={backgroundWorkers}
          totalLatency={totalPipelineLatency}
          isLoading={loading}
          error={error}
          className="mb-6"
          data-testid="pipeline-flow-visualization"
        />

        {/* Infrastructure Status Grid - Compact 5-card grid showing infrastructure status */}
        <InfrastructureStatusGrid
          data={infrastructureData}
          loading={loading}
          error={error}
          onCardClick={setExpandedInfraCard}
          expandedCard={expandedInfraCard}
          className="mb-6"
          data-testid="infrastructure-status-grid"
        />

        {/*
          Dense Grid Layout - Grafana-style dashboard
          Row 1: System Health | GPU Stats | AI Models | Alerts (4 cols on xl)
          Row 2: Pipeline Metrics | Database Metrics (2 cols spanning)
          Row 3: Background Workers | Containers (2 cols spanning)
          Row 4: Host System (full width)
        */}
        <div className="grid auto-rows-min gap-4 lg:grid-cols-2 xl:grid-cols-4">
          {/* Row 1: System Health (compact) */}
          <Card
            className="border-gray-800 bg-[#1A1A1A] shadow-lg"
            data-testid="system-overview-card"
          >
            <Title className="mb-3 flex items-center gap-2 text-white">
              <Activity className="h-5 w-5 text-[#76B900]" />
              System Health
            </Title>

            {/* Compact stats grid */}
            <div className="grid grid-cols-2 gap-2">
              <div className="rounded-lg bg-gray-800/50 p-2 text-center">
                <Text className="text-xs text-gray-500">Uptime</Text>
                <Metric className="text-base text-[#76B900]">
                  {stats ? formatUptime(stats.uptime_seconds) : 'N/A'}
                </Metric>
              </div>
              <div className="rounded-lg bg-gray-800/50 p-2 text-center">
                <Text className="text-xs text-gray-500">Cameras</Text>
                <Metric className="text-base text-white">{stats?.total_cameras ?? 0}</Metric>
              </div>
              <div className="rounded-lg bg-gray-800/50 p-2 text-center">
                <Text className="text-xs text-gray-500">Events</Text>
                <Metric className="text-base text-white">
                  {stats?.total_events?.toLocaleString() ?? 0}
                </Metric>
              </div>
              <div className="rounded-lg bg-gray-800/50 p-2 text-center">
                <Text className="text-xs text-gray-500">Detections</Text>
                <Metric className="text-base text-white">
                  {stats?.total_detections?.toLocaleString() ?? 0}
                </Metric>
              </div>
            </div>

            {/* Service Health Summary */}
            <div className="mt-3 flex items-center justify-between rounded-lg bg-gray-800/30 px-3 py-2">
              <div className="flex items-center gap-2">
                <CheckCircle className="h-4 w-4 text-[#76B900]" />
                <Text className="text-sm text-gray-300">Services</Text>
              </div>
              {overallStatus && (
                <Badge
                  color={getServiceStatusColor(overallStatus)}
                  size="sm"
                  data-testid="overall-health-badge"
                >
                  {overallStatus.charAt(0).toUpperCase() + overallStatus.slice(1)}
                </Badge>
              )}
            </div>

            {/* Compact service list */}
            <div className="mt-2 space-y-1" data-testid="service-health-card">
              {healthError ? (
                <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-2">
                  <AlertCircle className="h-3 w-3 text-red-500" />
                  <Text className="text-xs text-red-400">
                    Failed to fetch service health: {healthError}
                  </Text>
                </div>
              ) : Object.entries(services).length > 0 ? (
                Object.entries(services).map(([serviceName, serviceStatus]) => (
                  <ServiceHealthRow key={serviceName} name={serviceName} status={serviceStatus} />
                ))
              ) : (
                <Text className="text-xs text-gray-500">No service data available</Text>
              )}
            </div>

            {health?.timestamp && (
              <Text className="mt-2 text-xs text-gray-500">
                Last checked: {new Date(health.timestamp).toLocaleTimeString()}
              </Text>
            )}
          </Card>

          {/* Row 1: GPU Stats (compact with sparkline) */}
          <GpuStats
            gpuName={performanceData?.gpu?.name ?? gpuStats?.gpu_name ?? null}
            utilization={performanceData?.gpu?.utilization ?? gpuStats?.utilization ?? null}
            memoryUsed={
              performanceData?.gpu?.vram_used_gb
                ? performanceData.gpu.vram_used_gb * 1024
                : gpuStats?.memory_used ?? null
            }
            memoryTotal={
              performanceData?.gpu?.vram_total_gb
                ? performanceData.gpu.vram_total_gb * 1024
                : gpuStats?.memory_total ?? null
            }
            temperature={performanceData?.gpu?.temperature ?? gpuStats?.temperature ?? null}
            powerUsage={performanceData?.gpu?.power_watts ?? gpuStats?.power_usage ?? null}
            inferenceFps={gpuStats?.inference_fps ?? null}
            timeRange={timeRange}
            historyData={gpuHistoryData.length > 0 ? gpuHistoryData : undefined}
            showHistoryControls={gpuHistoryData.length === 0}
            data-testid="gpu-stats"
          />

          {/* Row 1: AI Models (core inference engines) */}
          <div className="xl:col-span-2">
            <AiModelsPanel
              aiModels={aiModelsData}
              data-testid="ai-models-panel-section"
            />
          </div>

          {/* Row 2: Model Zoo (enrichment models with VRAM tracking) */}
          <div className="xl:col-span-2">
            <ModelZooPanel
              models={modelZooModels}
              vramStats={modelZooVramStats}
              isLoading={modelZooLoading}
              error={modelZooError}
              onRefresh={() => void refreshModelZoo()}
              data-testid="model-zoo-panel-section"
            />
          </div>

          {/* Row 2: Pipeline Metrics (combined Queues + Latency + Throughput) */}
          <div className="xl:col-span-2">
            <PipelineMetricsPanel
              queues={{
                detection_queue: telemetry?.queues.detection_queue ?? 0,
                analysis_queue: telemetry?.queues.analysis_queue ?? 0,
              }}
              latencies={telemetry?.latencies}
              throughputHistory={throughputHistory}
              timestamp={telemetry?.timestamp}
              queueWarningThreshold={10}
              latencyWarningThreshold={10000}
              data-testid="pipeline-metrics-panel"
            />
          </div>

          {/* Row 2: Database Metrics (PostgreSQL + Redis side-by-side) */}
          <div className="xl:col-span-2">
            <DatabasesPanel
              postgresql={postgresMetrics}
              redis={redisMetrics}
              timeRange={timeRange}
              history={databaseHistory}
              data-testid="databases-panel-section"
            />
          </div>

          {/* Row 3: Background Workers (collapsible, compact list) */}
          <div className="xl:col-span-2">
            <WorkerStatusPanel
              pollingInterval={10000}
              defaultExpanded={false}
              compact={false}
            />
          </div>

          {/* Row 3: Containers (grid of status badges) */}
          <div className="xl:col-span-2">
            <ContainersPanel
              containers={containerMetrics}
              history={containerHistory}
              data-testid="containers-panel-section"
            />
          </div>

          {/* Row 4: Host System (CPU | RAM | Disk inline bars) - Full width */}
          <div className="lg:col-span-2 xl:col-span-4">
            <HostSystemPanel
              host={hostMetrics}
              timeRange={timeRange}
              history={hostHistory}
              data-testid="host-system-panel-section"
            />
          </div>

          {/* Row 5: Circuit Breakers (full width) */}
          <div className="lg:col-span-2 xl:col-span-4">
            <CircuitBreakerPanel
              data={circuitBreakers}
              loading={circuitBreakersLoading}
              error={circuitBreakersError}
              onReset={handleResetCircuitBreaker}
              data-testid="circuit-breaker-panel-section"
            />
          </div>

          {/* Row 6: Services Panel (full width) */}
          <div className="lg:col-span-2 xl:col-span-4">
            <ServicesPanel
              pollingInterval={30000}
              data-testid="services-panel-section"
            />
          </div>
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
        'flex items-center justify-between rounded-lg px-2 py-1.5',
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
      <div className="flex items-center gap-1.5">
        <ServiceStatusIcon status={status.status} />
        <div className="flex items-center gap-2">
          <Text className="text-xs font-medium text-gray-300">{displayName}</Text>
          {status.message && (
            <Text className="hidden text-xs text-gray-500 sm:inline">{status.message}</Text>
          )}
        </div>
      </div>
      <Badge color={getServiceStatusColor(status.status)} size="xs">
        {status.status}
      </Badge>
    </div>
  );
}
