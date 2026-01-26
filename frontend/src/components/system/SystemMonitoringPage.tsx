import { Callout } from '@tremor/react';
import {
  Settings,
  AlertTriangle,
  BarChart2,
  ExternalLink,
  HardDrive,
  Activity,
  Video,
  FileText,
  Terminal,
  Database,
  Wrench,
  Server,
} from 'lucide-react';
import { useEffect, useState, useRef, useCallback, useMemo } from 'react';

import { useRedisDebugInfoQuery } from '../../hooks/useDebugQueries';
import { useLocalStorage } from '../../hooks/useLocalStorage';
import { usePerformanceMetrics } from '../../hooks/usePerformanceMetrics';
import { useSystemPageSections } from '../../hooks/useSystemPageSections';
import {
  fetchTelemetry,
  fetchConfig,
  fetchCircuitBreakers,
  fetchReadiness,
  resetCircuitBreaker,
  type TelemetryResponse,
  type CircuitBreakersResponse,
  type WorkerStatus,
} from '../../services/api';
import { BatchStatisticsDashboard } from '../batch';
import { ErrorState } from '../common';
import {
  ProfilingPanel,
  RecordingReplayPanel,
  ConfigInspectorPanel,
  LogLevelPanel,
  TestDataPanel,
} from '../developer-tools';
import CircuitBreakerPanel from './CircuitBreakerPanel';
import CollapsibleSection from './CollapsibleSection';
import DatabasesPanel from './DatabasesPanel';
import DebugModeToggle from './DebugModeToggle';
import FileOperationsPanel from './FileOperationsPanel';
import PipelineFlowVisualization from './PipelineFlowVisualization';
import ServicesPanel from './ServicesPanel';

import type { DatabaseMetrics, RedisMetrics, DatabaseHistoryData } from './DatabasesPanel';
import type {
  PipelineStageData,
  BackgroundWorkerStatus,
  TotalLatency,
} from './PipelineFlowVisualization';

/**
 * OperationsPage - Streamlined operations dashboard
 *
 * Contains only interactive/actionable components:
 * - PipelineFlowVisualization - Visual pipeline diagram
 * - CircuitBreakerPanel - Circuit breaker reset actions
 * - FileOperationsPanel - File cleanup actions
 * - DebugModeToggle - Toggle debug mode
 *
 * Metrics-only panels have been removed as Grafana now handles detailed metrics.
 */
export default function SystemMonitoringPage() {
  // Section state management with localStorage persistence
  const { sectionStates, toggleSection } = useSystemPageSections();

  // Debug mode state from localStorage
  const [debugMode] = useLocalStorage('system-debug-mode', false);

  // Performance metrics from WebSocket (includes database metrics)
  const { current: performanceData, history: performanceHistory, timeRange } = usePerformanceMetrics();

  // Redis debug info query (only enabled when debugMode is active)
  const {
    redisInfo: redisDebugInfo,
    pubsubInfo,
    isLoading: redisDebugLoading,
    error: redisDebugError,
  } = useRedisDebugInfoQuery({ enabled: debugMode });

  // State for Grafana URL
  const [grafanaUrl, setGrafanaUrl] = useState<string>('http://localhost:3002');

  // State for telemetry (minimal, for PipelineFlowVisualization)
  const [telemetry, setTelemetry] = useState<TelemetryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // State for circuit breakers
  const [circuitBreakers, setCircuitBreakers] = useState<CircuitBreakersResponse | null>(null);
  const [circuitBreakersLoading, setCircuitBreakersLoading] = useState(true);
  const [circuitBreakersError, setCircuitBreakersError] = useState<string | null>(null);

  // State for workers (for PipelineFlowVisualization background workers)
  const [workers, setWorkers] = useState<WorkerStatus[]>([]);

  // Throughput tracking for pipeline visualization
  const prevTelemetryRef = useRef<TelemetryResponse | null>(null);
  const prevTimestampRef = useRef<number | null>(null);
  const [throughputPerMin, setThroughputPerMin] = useState<number>(0);

  // Derive database metrics from performance data
  const postgresqlMetrics: DatabaseMetrics | null = useMemo(() => {
    const postgres = performanceData?.databases?.postgresql;
    if (!postgres) return null;
    return postgres as DatabaseMetrics;
  }, [performanceData]);

  const redisMetrics: RedisMetrics | null = useMemo(() => {
    const redis = performanceData?.databases?.redis;
    if (!redis) return null;
    return redis as RedisMetrics;
  }, [performanceData]);

  // Build history data for database charts from performance history
  const databaseHistory: DatabaseHistoryData = useMemo(() => {
    const historyData = performanceHistory[timeRange] || [];
    return {
      postgresql: {
        connections: historyData
          .filter((d) => d.databases?.postgresql)
          .map((d) => ({
            timestamp: d.timestamp,
            value: (d.databases.postgresql as DatabaseMetrics)?.connections_active ?? 0,
          })),
        cache_hit_ratio: historyData
          .filter((d) => d.databases?.postgresql)
          .map((d) => ({
            timestamp: d.timestamp,
            value: (d.databases.postgresql as DatabaseMetrics)?.cache_hit_ratio ?? 0,
          })),
      },
      redis: {
        memory: historyData
          .filter((d) => d.databases?.redis)
          .map((d) => ({
            timestamp: d.timestamp,
            value: (d.databases.redis as RedisMetrics)?.memory_mb ?? 0,
          })),
        clients: historyData
          .filter((d) => d.databases?.redis)
          .map((d) => ({
            timestamp: d.timestamp,
            value: (d.databases.redis as RedisMetrics)?.connected_clients ?? 0,
          })),
      },
    };
  }, [performanceHistory, timeRange]);

  // Fetch Grafana URL from config API
  useEffect(() => {
    const loadConfig = async () => {
      try {
        const config = await fetchConfig();
        const configWithGrafana = config as typeof config & { grafana_url?: string };
        if (configWithGrafana.grafana_url) {
          setGrafanaUrl(configWithGrafana.grafana_url);
        }
      } catch (err) {
        console.error('Failed to fetch config:', err);
      }
    };
    void loadConfig();
  }, []);

  // Fetch telemetry data - extracted for retry functionality
  const loadTelemetryData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const telemetryData = await fetchTelemetry();
      setTelemetry(telemetryData);
    } catch (err) {
      console.error('Failed to load telemetry data:', err);
      setError(err instanceof Error ? err.message : 'Failed to load telemetry data');
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch initial telemetry data
  useEffect(() => {
    void loadTelemetryData();
  }, [loadTelemetryData]);

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
        setCircuitBreakersError(
          err instanceof Error ? err.message : 'Failed to load circuit breakers'
        );
      } finally {
        setCircuitBreakersLoading(false);
      }
    }

    void loadCircuitBreakers();
  }, []);

  // Fetch workers data (for PipelineFlowVisualization)
  useEffect(() => {
    async function loadWorkers() {
      try {
        const readinessData = await fetchReadiness();
        setWorkers(readinessData.workers || []);
      } catch (err) {
        console.error('Failed to load workers:', err);
      }
    }

    void loadWorkers();
    const interval = setInterval(() => {
      void loadWorkers();
    }, 10000);

    return () => clearInterval(interval);
  }, []);

  // Calculate throughput from telemetry changes
  useEffect(() => {
    if (!telemetry) return;

    const now = Date.now();

    if (prevTelemetryRef.current && prevTimestampRef.current) {
      const timeDiffMs = now - prevTimestampRef.current;
      const timeDiffMin = timeDiffMs / 60000;

      if (timeDiffMin > 0) {
        const detectionsPerMin = Math.max(
          0,
          Math.round(
            ((prevTelemetryRef.current.queues.detection_queue - telemetry.queues.detection_queue) /
              timeDiffMin) *
              60
          )
        );
        setThroughputPerMin(detectionsPerMin);
      }
    }

    prevTelemetryRef.current = telemetry;
    prevTimestampRef.current = now;
  }, [telemetry]);

  // Poll for telemetry updates every 5 seconds
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const telemetryData = await fetchTelemetry();
        setTelemetry(telemetryData);
      } catch (err) {
        if (err instanceof Error && err.message !== 'Failed to fetch') {
          console.error('Failed to update telemetry:', err);
        }
      }
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  // Handler for resetting circuit breakers
  const handleResetCircuitBreaker = async (name: string) => {
    try {
      await resetCircuitBreaker(name);
      const data = await fetchCircuitBreakers();
      setCircuitBreakers(data);
    } catch (err) {
      console.error(`Failed to reset circuit breaker ${name}:`, err);
      setCircuitBreakersError(err instanceof Error ? err.message : `Failed to reset ${name}`);
    }
  };

  // Derive worker statuses for pipeline visualization
  const getWorkerStatus = (workerName: string): 'running' | 'degraded' | 'stopped' => {
    const worker = workers.find((w) => w.name === workerName);
    if (!worker) return 'stopped';
    return worker.running ? 'running' : 'stopped';
  };

  // Pipeline stages data for PipelineFlowVisualization
  const pipelineStages: PipelineStageData[] = [
    {
      id: 'files',
      name: 'Files',
      icon: 'folder',
      metrics: {
        pending: telemetry?.queues?.detection_queue ?? 0,
      },
    },
    {
      id: 'detect',
      name: 'Detect',
      icon: 'search',
      metrics: {
        queueDepth: telemetry?.queues?.detection_queue ?? 0,
        avgLatency: telemetry?.latencies?.detect?.avg_ms ?? null,
        p95Latency: telemetry?.latencies?.detect?.p95_ms ?? null,
      },
    },
    {
      id: 'batch',
      name: 'Batch',
      icon: 'package',
      metrics: {
        throughput: throughputPerMin > 0 ? `${throughputPerMin}/min` : undefined,
        pending: telemetry?.queues?.analysis_queue ?? 0,
      },
    },
    {
      id: 'analyze',
      name: 'Analyze',
      icon: 'brain',
      metrics: {
        queueDepth: telemetry?.queues?.analysis_queue ?? 0,
        avgLatency: telemetry?.latencies?.analyze?.avg_ms ?? null,
        p95Latency: telemetry?.latencies?.analyze?.p95_ms ?? null,
      },
    },
  ];

  // Background workers data for PipelineFlowVisualization
  const backgroundWorkers: BackgroundWorkerStatus[] = [
    {
      id: 'file-watcher',
      name: 'Watcher',
      status: getWorkerStatus('file_watcher'),
    },
    {
      id: 'detector',
      name: 'Detector',
      status: getWorkerStatus('detection_worker'),
    },
    {
      id: 'aggregator',
      name: 'Aggregator',
      status: getWorkerStatus('batch_aggregator'),
    },
    {
      id: 'analyzer',
      name: 'Analyzer',
      status: getWorkerStatus('analysis_worker'),
    },
    {
      id: 'cleanup',
      name: 'Cleanup',
      status: getWorkerStatus('cleanup_service'),
    },
  ];

  // Total pipeline latency for PipelineFlowVisualization
  const totalPipelineLatency: TotalLatency = {
    avg: (telemetry?.latencies?.detect?.avg_ms ?? 0) + (telemetry?.latencies?.analyze?.avg_ms ?? 0),
    p95: (telemetry?.latencies?.detect?.p95_ms ?? 0) + (telemetry?.latencies?.analyze?.p95_ms ?? 0),
    p99: (telemetry?.latencies?.detect?.p99_ms ?? 0) + (telemetry?.latencies?.analyze?.p99_ms ?? 0),
  };

  return (
    <div
      className="min-h-screen bg-[#121212] p-8"
      data-testid={loading ? 'operations-loading' : error ? 'operations-error' : 'operations-page'}
    >
      <div className="mx-auto max-w-[1920px]">
        {/* Header with DebugModeToggle - Always visible */}
        <div className="mb-8 flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3">
              <Settings className="h-8 w-8 text-[#76B900]" />
              <h1 className="text-4xl font-bold text-white">Operations</h1>
            </div>
            <p className="mt-2 text-sm text-gray-400">
              Pipeline visualization and operational controls
            </p>
          </div>
          <div className="flex items-center gap-3">
            <DebugModeToggle data-testid="operations-debug-mode-toggle" />
          </div>
        </div>

        {/* Loading state */}
        {loading && (
          <div className="grid gap-6 lg:grid-cols-2">
            {Array.from({ length: 4 }, (_, i) => (
              <div key={i} className="h-64 animate-pulse rounded-lg bg-gray-800"></div>
            ))}
          </div>
        )}

        {/* Error state */}
        {error && !loading && (
          <ErrorState
            title="Error Loading Operations Data"
            message={error}
            onRetry={() => void loadTelemetryData()}
            testId="operations-error-state"
          />
        )}

        {/* Main content - only show when not loading and no error */}
        {!loading && !error && (
          <>
            {/* Grafana Monitoring Banner */}
        <Callout
          title="Detailed Metrics in Grafana"
          icon={BarChart2}
          color="blue"
          className="mb-6"
          data-testid="grafana-monitoring-banner"
        >
          <span className="inline-flex flex-wrap items-center gap-2">
            <span>
              View detailed metrics, historical data, and system monitoring dashboards in Grafana.
            </span>
            <a
              href={grafanaUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 font-medium text-blue-400 hover:text-blue-300"
              data-testid="grafana-link"
            >
              Open Grafana
              <ExternalLink className="h-4 w-4" />
            </a>
          </span>
        </Callout>

        {/* Pipeline Flow Visualization - Full width */}
        <PipelineFlowVisualization
          stages={pipelineStages}
          workers={backgroundWorkers}
          totalLatency={totalPipelineLatency}
          isLoading={loading}
          error={error}
          className="mb-6"
          data-testid="pipeline-flow-visualization"
        />

        {/* Batch Processing Statistics - Full width (NEM-3653) */}
        <div id="section-batch-statistics" className="mb-6">
          <CollapsibleSection
            title="Batch Processing Statistics"
            icon={<BarChart2 className="h-5 w-5 text-[#76B900]" />}
            isOpen={sectionStates['batch-statistics']}
            onToggle={() => toggleSection('batch-statistics')}
            data-testid="batch-statistics-section"
          >
            <BatchStatisticsDashboard data-testid="batch-statistics-dashboard" />
          </CollapsibleSection>
        </div>

        {/* Two-column grid for actionable panels */}
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Circuit Breakers Panel */}
          <div id="section-circuit-breakers">
            <CollapsibleSection
              title="Circuit Breakers"
              icon={<AlertTriangle className="h-5 w-5 text-[#76B900]" />}
              isOpen={sectionStates['circuit-breakers']}
              onToggle={() => toggleSection('circuit-breakers')}
              data-testid="circuit-breakers-section"
            >
              <CircuitBreakerPanel
                data={circuitBreakers}
                loading={circuitBreakersLoading}
                error={circuitBreakersError}
                onReset={handleResetCircuitBreaker}
                data-testid="circuit-breaker-panel-section"
              />
            </CollapsibleSection>
          </div>

          {/* File Operations Panel */}
          <div id="section-file-operations">
            <CollapsibleSection
              title="File Operations"
              icon={<HardDrive className="h-5 w-5 text-[#76B900]" />}
              isOpen={sectionStates['file-operations']}
              onToggle={() => toggleSection('file-operations')}
              data-testid="file-operations-section"
            >
              <FileOperationsPanel
                pollingInterval={30000}
                data-testid="file-operations-panel-section"
              />
            </CollapsibleSection>
          </div>

          {/* Services Panel */}
          <div id="section-services">
            <CollapsibleSection
              title="Services"
              icon={<Server className="h-5 w-5 text-[#76B900]" />}
              isOpen={sectionStates['services']}
              onToggle={() => toggleSection('services')}
              data-testid="services-section"
            >
              <ServicesPanel
                pollingInterval={30000}
                data-testid="services-panel-section"
              />
            </CollapsibleSection>
          </div>

          {/* Databases Panel */}
          <div id="section-databases">
            <CollapsibleSection
              title="Databases"
              icon={<Database className="h-5 w-5 text-[#76B900]" />}
              isOpen={sectionStates['databases']}
              onToggle={() => toggleSection('databases')}
              data-testid="databases-section"
            >
              <DatabasesPanel
                postgresql={postgresqlMetrics}
                redis={redisMetrics}
                timeRange={timeRange}
                history={databaseHistory}
                debugMode={debugMode}
                redisDebugInfo={redisDebugInfo}
                pubsubInfo={pubsubInfo}
                redisDebugLoading={redisDebugLoading}
                redisDebugError={redisDebugError?.message ?? null}
                data-testid="databases-panel-section"
              />
            </CollapsibleSection>
          </div>
        </div>

        {/* Developer Tools Section */}
        <div className="mt-8">
          <div className="mb-4 flex items-center gap-2">
            <Wrench className="h-5 w-5 text-[#76B900]" />
            <h2 className="text-xl font-semibold text-white">Developer Tools</h2>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            {/* Profiling Panel */}
            <div id="section-profiling">
              <CollapsibleSection
                title="Performance Profiling"
                icon={<Activity className="h-5 w-5 text-[#76B900]" />}
                isOpen={sectionStates['profiling']}
                onToggle={() => toggleSection('profiling')}
                data-testid="profiling-section"
              >
                <ProfilingPanel data-testid="profiling-panel-section" />
              </CollapsibleSection>
            </div>

            {/* Recording & Replay Panel */}
            <div id="section-recording-replay">
              <CollapsibleSection
                title="Recording & Replay"
                icon={<Video className="h-5 w-5 text-[#76B900]" />}
                isOpen={sectionStates['recording-replay']}
                onToggle={() => toggleSection('recording-replay')}
                data-testid="recording-replay-section"
              >
                <RecordingReplayPanel data-testid="recording-replay-panel-section" />
              </CollapsibleSection>
            </div>

            {/* Config Inspector Panel */}
            <div id="section-config-inspector">
              <CollapsibleSection
                title="Configuration Inspector"
                icon={<FileText className="h-5 w-5 text-[#76B900]" />}
                isOpen={sectionStates['config-inspector']}
                onToggle={() => toggleSection('config-inspector')}
                data-testid="config-inspector-section"
              >
                <ConfigInspectorPanel data-testid="config-inspector-panel-section" />
              </CollapsibleSection>
            </div>

            {/* Log Level Panel */}
            <div id="section-log-level">
              <CollapsibleSection
                title="Log Level Control"
                icon={<Terminal className="h-5 w-5 text-[#76B900]" />}
                isOpen={sectionStates['log-level']}
                onToggle={() => toggleSection('log-level')}
                data-testid="log-level-section"
              >
                <LogLevelPanel data-testid="log-level-panel-section" />
              </CollapsibleSection>
            </div>

            {/* Test Data Panel */}
            <div id="section-test-data">
              <CollapsibleSection
                title="Test Data Management"
                icon={<Database className="h-5 w-5 text-[#76B900]" />}
                isOpen={sectionStates['test-data']}
                onToggle={() => toggleSection('test-data')}
                data-testid="test-data-section"
              >
                <TestDataPanel data-testid="test-data-panel-section" />
              </CollapsibleSection>
            </div>
          </div>
        </div>
          </>
        )}
      </div>
    </div>
  );
}
