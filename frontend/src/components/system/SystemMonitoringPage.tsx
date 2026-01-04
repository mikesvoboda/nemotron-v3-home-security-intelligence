import {
  Server,
  AlertCircle,
  Activity,
  ExternalLink,
} from 'lucide-react';
import { useEffect, useState, useRef, useCallback, useMemo } from 'react';

import GpuStatistics from './GpuStatistics';
import InfrastructureGrid from './InfrastructureGrid';
import ModelZooPanel from './ModelZooPanel';
import PerformanceAlerts from './PerformanceAlerts';
import PipelineFlow from './PipelineFlow';
import SummaryRow from './SummaryRow';
import TimeRangeSelector from './TimeRangeSelector';
import { useHealthStatus } from '../../hooks/useHealthStatus';
import { useModelZooStatus } from '../../hooks/useModelZooStatus';
import { usePerformanceMetrics } from '../../hooks/usePerformanceMetrics';
import {
  fetchStats,
  fetchTelemetry,
  fetchGPUStats,
  fetchConfig,
  fetchCircuitBreakers,
  fetchReadiness,
  type GPUStats,
  type TelemetryResponse,
  type CircuitBreakersResponse,
  type WorkerStatus,
} from '../../services/api';

import type { AiModelStatus } from './GpuStatistics';
import type { InfraComponent, PostgresDetails, RedisDetails, ContainersDetails, HostDetails, CircuitsDetails } from './InfrastructureGrid';
import type { PipelineStage, WorkerStatus as PipelineWorkerStatus } from './PipelineFlow';
import type { ThroughputPoint } from './PipelineMetricsPanel';
import type { IndicatorData, HealthStatus } from './SummaryRow';
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
  const [_circuitBreakersLoading, setCircuitBreakersLoading] = useState(true);
  const [_circuitBreakersError, setCircuitBreakersError] = useState<string | null>(null);

  // State for background workers
  const [workers, setWorkers] = useState<WorkerStatus[]>([]);

  // Use the health status hook for service health
  const {
    health: _health,
    services: _services,
    overallStatus: _overallStatus,
    isLoading: healthLoading,
    error: _healthError,
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
  // ai_models is a Record<string, AiModelMetrics | NemotronMetrics> with dynamic keys
  const aiModelsData = useMemo<Record<string, { status: string } | null> | null>(() => {
    return performanceData
      ? {
          ...(performanceData.ai_models ?? {}),
          ...(performanceData.nemotron ? { nemotron: performanceData.nemotron } : {}),
        }
      : null;
  }, [performanceData]);

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

  // Extract host metrics
  const hostMetrics = performanceData?.host ?? null;

  // Extract container metrics
  const containerMetrics = useMemo(() => performanceData?.containers ?? [], [performanceData]);

  // Throughput history for PipelineMetricsPanel
  const [_throughputHistory, setThroughputHistory] = useState<ThroughputPoint[]>([]);
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

  // Fetch workers data
  useEffect(() => {
    async function loadWorkers() {
      try {
        const readiness = await fetchReadiness();
        setWorkers(readiness.workers || []);
      } catch (err) {
        console.error('Failed to load workers:', err);
      }
    }

    void loadWorkers();
    // Poll every 10 seconds
    const interval = setInterval(() => void loadWorkers(), 10000);
    return () => clearInterval(interval);
  }, []);

  // Handler for scrolling to section when summary indicator is clicked
  const handleSummaryIndicatorClick = useCallback((id: string) => {
    const sectionMap: Record<string, string> = {
      overall: 'summary-section',
      gpu: 'gpu-section',
      pipeline: 'pipeline-section',
      aiModels: 'ai-models-section',
      infrastructure: 'infra-section',
    };
    const sectionId = sectionMap[id];
    if (sectionId) {
      const element = document.getElementById(sectionId);
      if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }
  }, []);

  // Compute Summary Row data
  const computeSummaryData = useCallback((): {
    overall: IndicatorData;
    gpu: IndicatorData;
    pipeline: IndicatorData;
    aiModels: IndicatorData;
    infrastructure: IndicatorData;
  } => {
    // GPU status
    const gpuUtil = performanceData?.gpu?.utilization ?? gpuStats?.utilization ?? null;
    const gpuTemp = performanceData?.gpu?.temperature ?? gpuStats?.temperature ?? null;
    const gpuMemUsed = performanceData?.gpu?.vram_used_gb ?? (gpuStats?.memory_used ? gpuStats.memory_used / 1024 : null);
    const gpuMemTotal = performanceData?.gpu?.vram_total_gb ?? (gpuStats?.memory_total ? gpuStats.memory_total / 1024 : null);

    let gpuHealth: HealthStatus = 'unknown';
    if (gpuUtil !== null) {
      if (gpuUtil < 90 && (gpuTemp === null || gpuTemp < 80)) {
        gpuHealth = 'healthy';
      } else if (gpuUtil >= 95 || (gpuTemp !== null && gpuTemp >= 85)) {
        gpuHealth = 'critical';
      } else {
        gpuHealth = 'degraded';
      }
    }

    // Pipeline status
    const detectionQueue = telemetry?.queues.detection_queue ?? 0;
    const analysisQueue = telemetry?.queues.analysis_queue ?? 0;
    const totalQueue = detectionQueue + analysisQueue;
    let pipelineHealth: HealthStatus = 'healthy';
    if (totalQueue > 50) {
      pipelineHealth = 'critical';
    } else if (totalQueue > 10) {
      pipelineHealth = 'degraded';
    }

    // AI Models status
    const rtdetrStatus = aiModelsData?.['rtdetr'];
    const nemotronStatus = aiModelsData?.['nemotron'];
    const modelsHealthy = (rtdetrStatus?.status === 'healthy' ? 1 : 0) + (nemotronStatus?.status === 'healthy' ? 1 : 0);
    const totalModels = 2;
    let aiModelsHealth: HealthStatus = 'healthy';
    if (modelsHealthy === 0) {
      aiModelsHealth = 'critical';
    } else if (modelsHealthy < totalModels) {
      aiModelsHealth = 'degraded';
    }

    // Infrastructure status
    const pgHealthy = postgresMetrics?.status === 'healthy';
    const redisHealthy = redisMetrics?.status === 'healthy';
    const containersHealthy = containerMetrics.filter(c => c.health === 'healthy').length;
    const containersTotal = containerMetrics.length;
    const circuitsHealthy = circuitBreakers?.circuit_breakers
      ? Object.values(circuitBreakers.circuit_breakers).filter(b => b.state === 'closed').length
      : 0;
    const circuitsTotal = circuitBreakers?.circuit_breakers
      ? Object.values(circuitBreakers.circuit_breakers).length
      : 0;

    let infraHealth: HealthStatus = 'healthy';
    if (!pgHealthy || !redisHealthy) {
      infraHealth = 'critical';
    } else if (containersHealthy < containersTotal || circuitsHealthy < circuitsTotal) {
      infraHealth = 'degraded';
    }

    // Overall - worst of all
    const statuses: HealthStatus[] = [gpuHealth, pipelineHealth, aiModelsHealth, infraHealth];
    let overallHealth: HealthStatus = 'healthy';
    if (statuses.includes('critical')) {
      overallHealth = 'critical';
    } else if (statuses.includes('degraded')) {
      overallHealth = 'degraded';
    } else if (statuses.includes('unknown')) {
      overallHealth = 'unknown';
    }

    return {
      overall: {
        id: 'overall',
        label: 'Overall',
        status: overallHealth,
      },
      gpu: {
        id: 'gpu',
        label: 'GPU',
        status: gpuHealth,
        primaryValue: gpuUtil !== null ? `${gpuUtil}%` : undefined,
        secondaryValue: gpuTemp !== null ? `${gpuTemp}C` : undefined,
        tertiaryValue: gpuMemUsed !== null && gpuMemTotal !== null
          ? `${gpuMemUsed.toFixed(1)}/${gpuMemTotal.toFixed(0)}GB`
          : undefined,
      },
      pipeline: {
        id: 'pipeline',
        label: 'Pipeline',
        status: pipelineHealth,
        primaryValue: `${totalQueue} queue`,
      },
      aiModels: {
        id: 'aiModels',
        label: 'AI Models',
        status: aiModelsHealth,
        primaryValue: `${modelsHealthy}/${totalModels}`,
      },
      infrastructure: {
        id: 'infrastructure',
        label: 'Infra',
        status: infraHealth,
        primaryValue: `${containersHealthy}/${containersTotal}`,
      },
    };
  }, [performanceData, gpuStats, telemetry, aiModelsData, postgresMetrics, redisMetrics, containerMetrics, circuitBreakers]);

  // Compute Pipeline Flow data
  const computePipelineFlowData = useCallback((): {
    files: PipelineStage;
    detect: PipelineStage;
    batch: PipelineStage;
    analyze: PipelineStage;
  } => {
    const detectionQueue = telemetry?.queues.detection_queue ?? 0;
    const analysisQueue = telemetry?.queues.analysis_queue ?? 0;
    const detectionLatency = telemetry?.latencies?.detect?.avg_ms;
    const detectionP95 = telemetry?.latencies?.detect?.p95_ms;
    const analysisLatency = telemetry?.latencies?.analyze?.avg_ms;
    const analysisP95 = telemetry?.latencies?.analyze?.p95_ms;

    const getQueueHealth = (depth: number): 'healthy' | 'degraded' | 'critical' => {
      if (depth > 50) return 'critical';
      if (depth > 10) return 'degraded';
      return 'healthy';
    };

    return {
      files: {
        name: 'files',
        label: 'Files',
        itemsPerMin: 12, // Could come from metrics
        health: 'healthy',
      },
      detect: {
        name: 'detect',
        label: 'Detect',
        queueDepth: detectionQueue,
        avgLatency: detectionLatency ? `${(detectionLatency / 1000).toFixed(1)}s` : undefined,
        p95Latency: detectionP95 ? `${(detectionP95 / 1000).toFixed(1)}s` : undefined,
        health: getQueueHealth(detectionQueue),
      },
      batch: {
        name: 'batch',
        label: 'Batch',
        pendingCount: 0, // Could come from metrics
        health: 'healthy',
      },
      analyze: {
        name: 'analyze',
        label: 'Analyze',
        queueDepth: analysisQueue,
        avgLatency: analysisLatency ? `${(analysisLatency / 1000).toFixed(1)}s` : undefined,
        p95Latency: analysisP95 ? `${(analysisP95 / 1000).toFixed(1)}s` : undefined,
        health: getQueueHealth(analysisQueue),
      },
    };
  }, [telemetry]);

  // Transform workers for PipelineFlow
  const transformWorkersForPipeline = useCallback((): PipelineWorkerStatus[] => {
    const abbreviations: Record<string, string> = {
      detection_worker: 'Det',
      analysis_worker: 'Ana',
      batch_timeout_worker: 'Batch',
      cleanup_service: 'Clean',
      file_watcher: 'Watch',
      gpu_monitor: 'GPU',
      metrics_worker: 'Metr',
      system_broadcaster: 'Bcast',
    };

    const displayNames: Record<string, string> = {
      detection_worker: 'Detection Worker',
      analysis_worker: 'Analysis Worker',
      batch_timeout_worker: 'Batch Timeout',
      cleanup_service: 'Cleanup Service',
      file_watcher: 'File Watcher',
      gpu_monitor: 'GPU Monitor',
      metrics_worker: 'Metrics Worker',
      system_broadcaster: 'System Broadcaster',
    };

    return workers.map(w => ({
      name: w.name,
      displayName: displayNames[w.name] || w.name,
      running: w.running,
      abbreviation: abbreviations[w.name] || w.name.slice(0, 4),
    }));
  }, [workers]);

  // Compute Infrastructure Grid data
  const computeInfrastructureData = useCallback((): {
    postgresql: InfraComponent;
    redis: InfraComponent;
    containers: InfraComponent;
    host: InfraComponent;
    circuits: InfraComponent;
  } => {
    const pgStatus: ComponentStatus = postgresMetrics?.status === 'healthy' ? 'healthy'
      : postgresMetrics?.status === 'degraded' ? 'degraded'
      : postgresMetrics?.status ? 'unhealthy' : 'unknown';

    const redisStatus: ComponentStatus = redisMetrics?.status === 'healthy' ? 'healthy'
      : redisMetrics?.status === 'degraded' ? 'degraded'
      : redisMetrics?.status ? 'unhealthy' : 'unknown';

    const containersHealthy = containerMetrics.filter(c => c.health === 'healthy').length;
    const containersTotal = containerMetrics.length;
    const containersStatus: ComponentStatus = containersHealthy === containersTotal ? 'healthy'
      : containersHealthy > 0 ? 'degraded' : 'unhealthy';

    const hostStatus: ComponentStatus = hostMetrics
      ? (hostMetrics.cpu_percent ?? 0) < 90 ? 'healthy' : 'degraded'
      : 'unknown';

    const circuitsArr = circuitBreakers?.circuit_breakers
      ? Object.values(circuitBreakers.circuit_breakers)
      : [];
    const circuitsHealthy = circuitsArr.filter(b => b.state === 'closed').length;
    const circuitsTotal = circuitsArr.length;
    const circuitsStatus: ComponentStatus = circuitsHealthy === circuitsTotal ? 'healthy'
      : circuitsHealthy > 0 ? 'degraded' : 'unhealthy';

    return {
      postgresql: {
        id: 'postgresql',
        label: 'PostgreSQL',
        status: pgStatus,
        keyMetric: postgresMetrics ? `${postgresMetrics.connections_active}/${postgresMetrics.connections_max}` : undefined,
        details: postgresMetrics ? {
          poolActive: postgresMetrics.connections_active,
          poolMax: postgresMetrics.connections_max,
          cacheHitRatio: postgresMetrics.cache_hit_ratio,
        } as PostgresDetails : undefined,
      },
      redis: {
        id: 'redis',
        label: 'Redis',
        status: redisStatus,
        keyMetric: redisMetrics ? `${redisMetrics.memory_mb.toFixed(1)}MB` : undefined,
        details: redisMetrics ? {
          memoryMb: redisMetrics.memory_mb,
          connectedClients: redisMetrics.connected_clients,
          hitRate: redisMetrics.hit_ratio,
          blockedClients: redisMetrics.blocked_clients,
        } as RedisDetails : undefined,
      },
      containers: {
        id: 'containers',
        label: 'Containers',
        status: containersStatus,
        keyMetric: `${containersHealthy}/${containersTotal}`,
        details: {
          containers: containerMetrics.map(c => ({
            name: c.name,
            status: c.health === 'healthy' ? 'running' : 'unhealthy',
          })),
        } as ContainersDetails,
      },
      host: {
        id: 'host',
        label: 'Host',
        status: hostStatus,
        keyMetric: hostMetrics ? `CPU ${hostMetrics.cpu_percent}%` : undefined,
        details: hostMetrics ? {
          cpuPercent: hostMetrics.cpu_percent,
          ramUsedGb: hostMetrics.ram_used_gb,
          ramTotalGb: hostMetrics.ram_total_gb,
          diskUsedGb: hostMetrics.disk_used_gb,
          diskTotalGb: hostMetrics.disk_total_gb,
        } as HostDetails : undefined,
      },
      circuits: {
        id: 'circuits',
        label: 'Circuits',
        status: circuitsStatus,
        keyMetric: `${circuitsHealthy}/${circuitsTotal}`,
        details: {
          breakers: circuitsArr.map(b => ({
            name: b.name,
            state: b.state,
            failureCount: b.failure_count,
          })),
        } as CircuitsDetails,
      },
    };
  }, [postgresMetrics, redisMetrics, containerMetrics, hostMetrics, circuitBreakers]);

  // Compute AI model status for GpuStatistics mini-cards
  const computeAiModelStatus = useCallback((): { rtdetr: AiModelStatus | null; nemotron: AiModelStatus | null } => {
    const rtdetr = aiModelsData?.['rtdetr'];
    const nemotron = aiModelsData?.['nemotron'];

    const mapStatus = (status?: string): AiModelStatus['status'] => {
      if (status === 'healthy') return 'healthy';
      if (status === 'unhealthy' || status === 'error') return 'unhealthy';
      if (status === 'loading') return 'loading';
      return 'unknown';
    };

    return {
      rtdetr: rtdetr ? {
        name: 'RT-DETRv2',
        status: mapStatus(rtdetr.status),
        latency: telemetry?.latencies?.detect?.avg_ms
          ? `${(telemetry.latencies.detect.avg_ms / 1000).toFixed(1)}s`
          : undefined,
        count: stats?.total_detections ?? 0,
        errors: 0,
      } : null,
      nemotron: nemotron ? {
        name: 'Nemotron',
        status: mapStatus(nemotron.status),
        latency: telemetry?.latencies?.analyze?.avg_ms
          ? `${(telemetry.latencies.analyze.avg_ms / 1000).toFixed(1)}s`
          : undefined,
        count: stats?.total_events ?? 0,
        errors: 0,
      } : null,
    };
  }, [aiModelsData, telemetry, stats]);

  // Memoized computed data
  const summaryData = computeSummaryData();
  const pipelineFlowData = computePipelineFlowData();
  const pipelineWorkers = transformWorkersForPipeline();
  const infraData = computeInfrastructureData();
  const aiModelStatus = computeAiModelStatus();

  // Type alias for infrastructure component status
  type ComponentStatus = 'healthy' | 'degraded' | 'unhealthy' | 'unknown';

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
        <div className="mb-6 flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3">
              <Server className="h-8 w-8 text-[#76B900]" />
              <h1 className="text-4xl font-bold text-white">System Monitoring</h1>
            </div>
            <p className="mt-2 text-sm text-gray-400">
              Real-time system metrics, service health, and pipeline performance
            </p>
          </div>
          <div className="flex items-center gap-4">
            <TimeRangeSelector
              selectedRange={timeRange}
              onRangeChange={setTimeRange}
              data-testid="system-time-range-selector"
            />
            <a
              href={grafanaUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
              data-testid="grafana-link"
            >
              Open Grafana
              <ExternalLink className="h-4 w-4" />
            </a>
          </div>
        </div>

        {/* Summary Row - Quick health check indicators */}
        <div id="summary-section" className="mb-6">
          <SummaryRow
            overall={summaryData.overall}
            gpu={summaryData.gpu}
            pipeline={summaryData.pipeline}
            aiModels={summaryData.aiModels}
            infrastructure={summaryData.infrastructure}
            onIndicatorClick={handleSummaryIndicatorClick}
            data-testid="summary-row"
          />
        </div>

        {/* Performance Alerts - Prominent banner when alerts active */}
        {transformedAlerts.length > 0 && (
          <PerformanceAlerts
            alerts={transformedAlerts}
            className="mb-6"
            data-testid="system-performance-alerts"
          />
        )}

        {/*
          Reorganized Layout per Design Spec:
          Section 1: GPU & AI Models
          Section 2: Pipeline
          Section 3: Infrastructure
        */}
        <div className="space-y-6">
          {/* ========== Section 1: GPU & AI MODELS ========== */}
          <section id="gpu-section" className="scroll-mt-4">
            <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
              <Activity className="h-5 w-5 text-[#76B900]" />
              GPU & AI Models
            </h2>
            <div id="ai-models-section" className="grid gap-4 lg:grid-cols-2">
              {/* GPU Statistics with stacked sparklines and AI model mini-cards */}
              <GpuStatistics
                gpuName={performanceData?.gpu?.name ?? gpuStats?.gpu_name ?? null}
                utilization={performanceData?.gpu?.utilization ?? gpuStats?.utilization ?? null}
                temperature={performanceData?.gpu?.temperature ?? gpuStats?.temperature ?? null}
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
                powerUsage={performanceData?.gpu?.power_watts ?? gpuStats?.power_usage ?? null}
                inferenceFps={gpuStats?.inference_fps ?? null}
                historyData={gpuHistoryData.length > 0 ? gpuHistoryData : undefined}
                rtdetr={aiModelStatus.rtdetr}
                nemotron={aiModelStatus.nemotron}
                grafanaUrl={grafanaUrl}
                data-testid="gpu-statistics-section"
              />

              {/* AI Model Zoo with show/hide toggle */}
              <ModelZooPanel
                models={modelZooModels}
                vramStats={modelZooVramStats}
                isLoading={modelZooLoading}
                error={modelZooError}
                onRefresh={() => void refreshModelZoo()}
                data-testid="model-zoo-panel-section"
              />
            </div>
          </section>

          {/* ========== Section 2: PIPELINE ========== */}
          <section id="pipeline-section" className="scroll-mt-4">
            <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
              <Activity className="h-5 w-5 text-[#76B900]" />
              Pipeline
            </h2>
            <PipelineFlow
              files={pipelineFlowData.files}
              detect={pipelineFlowData.detect}
              batch={pipelineFlowData.batch}
              analyze={pipelineFlowData.analyze}
              totalLatency={
                telemetry?.latencies?.detect && telemetry?.latencies?.analyze
                  ? {
                      avg: `${(((telemetry.latencies.detect.avg_ms ?? 0) + (telemetry.latencies.analyze.avg_ms ?? 0)) / 1000).toFixed(1)}s`,
                      p95: `${(((telemetry.latencies.detect.p95_ms ?? 0) + (telemetry.latencies.analyze.p95_ms ?? 0)) / 1000).toFixed(1)}s`,
                      p99: telemetry.latencies.detect.p99_ms && telemetry.latencies.analyze.p99_ms
                        ? `${((telemetry.latencies.detect.p99_ms + telemetry.latencies.analyze.p99_ms) / 1000).toFixed(0)}s`
                        : undefined,
                    }
                  : undefined
              }
              workers={pipelineWorkers}
              data-testid="pipeline-flow-section"
            />
          </section>

          {/* ========== Section 3: INFRASTRUCTURE ========== */}
          <section id="infra-section" className="scroll-mt-4">
            <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
              <Server className="h-5 w-5 text-[#76B900]" />
              Infrastructure
            </h2>
            <InfrastructureGrid
              postgresql={infraData.postgresql}
              redis={infraData.redis}
              containers={infraData.containers}
              host={infraData.host}
              circuits={infraData.circuits}
              data-testid="infrastructure-grid-section"
            />
          </section>
        </div>
      </div>
    </div>
  );
}
