import { clsx } from 'clsx';
import {
  AlertCircle,
  Brain,
  ChevronDown,
  ChevronRight,
  Folder,
  Package,
  Search,
} from 'lucide-react';
import { useState } from 'react';

// ============================================================================
// Type Definitions
// ============================================================================

/**
 * Metrics for a pipeline stage
 */
export interface StageMetrics {
  throughput?: string;
  queueDepth?: number;
  avgLatency?: number | null;
  p95Latency?: number | null;
  pending?: number;
}

/**
 * Data for a single pipeline stage
 */
export interface PipelineStageData {
  id: string;
  name: string;
  icon: 'folder' | 'search' | 'package' | 'brain';
  metrics: StageMetrics;
}

/**
 * Background worker status
 */
export interface BackgroundWorkerStatus {
  id: string;
  name: string;
  status: 'running' | 'stopped' | 'degraded';
}

/**
 * Total pipeline latency metrics
 */
export interface TotalLatency {
  avg: number;
  p95: number;
  p99: number;
}

/**
 * Baseline latencies for health comparison
 */
export interface BaselineLatencies {
  [stageId: string]: number;
}

/**
 * Props for PipelineFlowVisualization component
 */
export interface PipelineFlowVisualizationProps {
  stages: PipelineStageData[];
  workers: BackgroundWorkerStatus[];
  totalLatency: TotalLatency;
  baselineLatencies?: BaselineLatencies;
  isLoading?: boolean;
  error?: string | null;
  className?: string;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Format milliseconds to human readable string
 */
function formatLatency(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return '--';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/**
 * Format total latency for display (seconds with decimal)
 */
function formatTotalLatency(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  const seconds = ms / 1000;
  if (seconds < 10) return `${seconds.toFixed(1)}s`;
  return `${Math.round(seconds)}s`;
}

/**
 * Get icon component for stage
 */
function getStageIcon(icon: string) {
  switch (icon) {
    case 'folder':
      return <Folder className="h-6 w-6" />;
    case 'search':
      return <Search className="h-6 w-6" />;
    case 'package':
      return <Package className="h-6 w-6" />;
    case 'brain':
      return <Brain className="h-6 w-6" />;
    default:
      return <Folder className="h-6 w-6" />;
  }
}

/**
 * Determine health status based on queue depth and latency
 */
function getStageHealth(
  metrics: StageMetrics,
  stageId: string,
  baselineLatencies?: BaselineLatencies
): 'healthy' | 'degraded' | 'critical' {
  const queueDepth = metrics.queueDepth;
  const avgLatency = metrics.avgLatency;
  const baseline = baselineLatencies?.[stageId];

  // Check queue depth first
  if (queueDepth !== undefined) {
    if (queueDepth > 50) return 'critical';
    if (queueDepth > 10) return 'degraded';
  }

  // Check latency against baseline
  if (avgLatency !== null && avgLatency !== undefined && baseline) {
    const ratio = avgLatency / baseline;
    if (ratio > 5) return 'critical';
    if (ratio > 2) return 'degraded';
  }

  return 'healthy';
}

/**
 * Get border color class based on health status
 */
function getHealthBorderClass(health: 'healthy' | 'degraded' | 'critical'): string {
  switch (health) {
    case 'healthy':
      return 'border-emerald-500';
    case 'degraded':
      return 'border-yellow-500';
    case 'critical':
      return 'border-red-500';
    default:
      return 'border-gray-600';
  }
}

/**
 * Get worker dot color class based on status
 */
function getWorkerDotClass(status: 'running' | 'stopped' | 'degraded'): string {
  switch (status) {
    case 'running':
      return 'bg-emerald-500';
    case 'stopped':
      return 'bg-red-500';
    case 'degraded':
      return 'bg-yellow-500';
    default:
      return 'bg-gray-500';
  }
}

// ============================================================================
// Sub-Components
// ============================================================================

/**
 * Loading skeleton
 */
function LoadingSkeleton() {
  return (
    <div
      className="animate-pulse space-y-4 rounded-lg bg-[#1A1A1A] p-4"
      data-testid="pipeline-flow-loading"
    >
      <div className="flex items-center justify-center gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="flex items-center gap-2">
            <div className="h-20 w-24 rounded-lg bg-gray-700" />
            {i < 4 && <div className="h-1 w-8 bg-gray-700" />}
          </div>
        ))}
      </div>
      <div className="h-8 w-full rounded bg-gray-700" />
    </div>
  );
}

/**
 * Error display
 */
function ErrorDisplay({ message }: { message: string }) {
  return (
    <div
      className="flex items-center gap-3 rounded-lg border border-red-500/30 bg-red-500/10 p-4"
      data-testid="pipeline-flow-error"
    >
      <AlertCircle className="h-5 w-5 text-red-500" />
      <span className="text-red-400">{message}</span>
    </div>
  );
}

/**
 * Single pipeline stage card
 */
interface StageCardProps {
  stage: PipelineStageData;
  baselineLatencies?: BaselineLatencies;
}

function StageCard({ stage, baselineLatencies }: StageCardProps) {
  const health = getStageHealth(stage.metrics, stage.id, baselineLatencies);
  const { metrics } = stage;

  return (
    <div
      className={clsx(
        'flex flex-col items-center rounded-lg border-2 bg-gray-800/50 p-3 text-center transition-all',
        getHealthBorderClass(health)
      )}
      data-testid={`stage-${stage.id}`}
    >
      <div className="mb-1 text-gray-400">{getStageIcon(stage.icon)}</div>
      <span className="mb-2 text-sm font-medium text-gray-200">{stage.name}</span>

      <div className="space-y-0.5 text-xs text-gray-400">
        {/* Throughput */}
        {metrics.throughput && <div>{metrics.throughput}</div>}

        {/* Queue depth */}
        {metrics.queueDepth !== undefined && <div>Queue: {metrics.queueDepth}</div>}

        {/* Latency */}
        {metrics.avgLatency !== undefined && metrics.avgLatency !== null && (
          <div>Avg: {formatLatency(metrics.avgLatency)}</div>
        )}

        {/* Pending */}
        {metrics.pending !== undefined && <div>{metrics.pending} pending</div>}
      </div>
    </div>
  );
}

/**
 * Arrow between stages
 */
function StageArrow({ index }: { index: number }) {
  return (
    <div
      className="flex items-center px-2 text-gray-500"
      data-testid={`arrow-${index}`}
    >
      <ChevronRight className="h-6 w-6" />
    </div>
  );
}

/**
 * Worker dot indicator
 */
interface WorkerDotProps {
  worker: BackgroundWorkerStatus;
}

function WorkerDot({ worker }: WorkerDotProps) {
  return (
    <div className="flex flex-col items-center gap-1">
      <div
        className={clsx('h-3 w-3 rounded-full', getWorkerDotClass(worker.status))}
        data-testid={`worker-dot-${worker.id}`}
        title={`${worker.name}: ${worker.status}`}
      />
      <span className="text-[10px] text-gray-400">{worker.name}</span>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * PipelineFlowVisualization - Visual diagram of the pipeline flow
 *
 * Shows:
 * - Pipeline stages (Files → Detect → Batch → Analyze) with flow arrows
 * - Per-stage metrics (queue depth, latency, throughput)
 * - Health status coloring based on thresholds
 * - Background workers grid with status dots
 * - Total pipeline latency summary
 */
export default function PipelineFlowVisualization({
  stages,
  workers,
  totalLatency,
  baselineLatencies,
  isLoading,
  error,
  className,
}: PipelineFlowVisualizationProps) {
  const [workersExpanded, setWorkersExpanded] = useState(false);

  // Loading state
  if (isLoading) {
    return <LoadingSkeleton />;
  }

  // Error state
  if (error) {
    return <ErrorDisplay message={error} />;
  }

  // Count running workers
  const runningCount = workers.filter((w) => w.status === 'running').length;
  const totalWorkers = workers.length;

  return (
    <div
      className={clsx('rounded-lg bg-[#1A1A1A] p-4', className)}
      data-testid="pipeline-flow-visualization"
    >
      {/* Pipeline Flow Diagram */}
      <div className="mb-4 flex flex-wrap items-center justify-center gap-1">
        {stages.map((stage, index) => (
          <div key={stage.id} className="flex items-center">
            <StageCard stage={stage} baselineLatencies={baselineLatencies} />
            {index < stages.length - 1 && <StageArrow index={index} />}
          </div>
        ))}
      </div>

      {/* Total Pipeline Latency */}
      <div
        className="mb-4 flex flex-wrap items-center justify-center gap-4 text-sm text-gray-400"
        data-testid="total-pipeline-latency"
      >
        <span>Total Pipeline:</span>
        <span>{formatTotalLatency(totalLatency.avg)} avg</span>
        <span>{formatTotalLatency(totalLatency.p95)} p95</span>
        <span>{formatTotalLatency(totalLatency.p99)} p99</span>
      </div>

      {/* Background Workers Section */}
      <div
        className="border-t border-gray-700 pt-4"
        data-testid="workers-grid"
      >
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-gray-300">Background Workers</span>
            <span
              className="rounded bg-gray-700 px-2 py-0.5 text-xs text-gray-300"
              data-testid="workers-count-badge"
            >
              {runningCount}/{totalWorkers} Running
            </span>
          </div>
          <button
            className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-200"
            onClick={() => setWorkersExpanded(!workersExpanded)}
            data-testid="expand-workers-button"
          >
            {workersExpanded ? 'Collapse Details' : 'Expand Details'}
            <ChevronDown
              className={clsx('h-4 w-4 transition-transform', workersExpanded && 'rotate-180')}
            />
          </button>
        </div>

        {/* Worker dots grid */}
        <div className="flex flex-wrap items-center justify-center gap-4">
          {workers.map((worker) => (
            <WorkerDot key={worker.id} worker={worker} />
          ))}
        </div>

        {/* Expanded worker details */}
        {workersExpanded && (
          <div
            className="mt-4 space-y-2 rounded-lg bg-gray-800/50 p-3"
            data-testid="workers-expanded-list"
          >
            {workers.map((worker) => (
              <div
                key={worker.id}
                className="flex items-center justify-between text-sm"
              >
                <span className="text-gray-300">{worker.id}</span>
                <span
                  className={clsx(
                    worker.status === 'running' && 'text-emerald-400',
                    worker.status === 'stopped' && 'text-red-400',
                    worker.status === 'degraded' && 'text-yellow-400'
                  )}
                >
                  {worker.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
