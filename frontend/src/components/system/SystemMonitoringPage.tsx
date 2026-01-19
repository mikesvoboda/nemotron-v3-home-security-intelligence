import { Callout } from '@tremor/react';
import {
  Settings,
  AlertCircle,
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
} from 'lucide-react';
import { useEffect, useState, useRef } from 'react';

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
import {
  ProfilingPanel,
  RecordingReplayPanel,
  ConfigInspectorPanel,
  LogLevelPanel,
  TestDataPanel,
} from '../developer-tools';
import CircuitBreakerPanel from './CircuitBreakerPanel';
import CollapsibleSection from './CollapsibleSection';
import DebugModeToggle from './DebugModeToggle';
import FileOperationsPanel from './FileOperationsPanel';
import PipelineFlowVisualization from './PipelineFlowVisualization';

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

  // Fetch initial telemetry data
  useEffect(() => {
    async function loadData() {
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
  const getWorkerStatus = (
    workerName: string
  ): 'running' | 'degraded' | 'stopped' => {
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

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-[#121212] p-8" data-testid="operations-loading">
        <div className="mx-auto max-w-[1920px]">
          {/* Header skeleton */}
          <div className="mb-8">
            <div className="h-10 w-72 animate-pulse rounded-lg bg-gray-800"></div>
            <div className="mt-2 h-5 w-96 animate-pulse rounded-lg bg-gray-800"></div>
          </div>

          {/* Grid skeleton */}
          <div className="grid gap-6 lg:grid-cols-2">
            {Array.from({ length: 4 }, (_, i) => (
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
        data-testid="operations-error"
      >
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-6 text-center">
          <AlertCircle className="mx-auto mb-4 h-12 w-12 text-red-500" />
          <h2 className="mb-2 text-xl font-bold text-red-500">Error Loading Operations Data</h2>
          <p className="text-sm text-gray-300">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 rounded-md bg-red-700 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-800"
          >
            Reload Page
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#121212] p-8" data-testid="operations-page">
      <div className="mx-auto max-w-[1920px]">
        {/* Header with DebugModeToggle */}
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
      </div>
    </div>
  );
}
