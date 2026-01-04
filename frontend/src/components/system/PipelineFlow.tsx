import { Card, Title, Text, Badge } from '@tremor/react';
import { clsx } from 'clsx';
import {
  Activity,
  FileImage,
  Search,
  Package,
  Brain,
  ArrowRight,
  ChevronDown,
  ChevronUp,
  CheckCircle,
  AlertTriangle,
  XCircle,
} from 'lucide-react';
import { useState } from 'react';

/**
 * Health status for pipeline stages
 */
export type StageHealth = 'healthy' | 'degraded' | 'critical' | 'unknown';

/**
 * Pipeline stage metrics
 */
export interface PipelineStage {
  /** Stage name */
  name: string;
  /** Stage display label */
  label: string;
  /** Current queue depth */
  queueDepth?: number;
  /** Average latency display string (e.g., "14ms", "2.1s") */
  avgLatency?: string;
  /** P95 latency display string */
  p95Latency?: string;
  /** Items per minute (for Files stage) */
  itemsPerMin?: number;
  /** Pending count (for Batch stage) */
  pendingCount?: number;
  /** Stage health status */
  health: StageHealth;
}

/**
 * Background worker status
 */
export interface WorkerStatus {
  /** Worker name */
  name: string;
  /** Display name */
  displayName: string;
  /** Whether worker is running */
  running: boolean;
  /** Worker abbreviation for compact display */
  abbreviation: string;
}

/**
 * Props for PipelineFlow component
 */
export interface PipelineFlowProps {
  /** Files/FileWatch stage */
  files: PipelineStage;
  /** Detection stage */
  detect: PipelineStage;
  /** Batch aggregation stage */
  batch: PipelineStage;
  /** Analysis stage */
  analyze: PipelineStage;
  /** Total pipeline latency */
  totalLatency?: {
    avg: string;
    p95: string;
    p99?: string;
  };
  /** Background workers status */
  workers?: WorkerStatus[];
  /** Whether workers section is expanded by default */
  workersDefaultExpanded?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Get stage background color based on health
 */
function getStageBackgroundClass(health: StageHealth): string {
  switch (health) {
    case 'healthy':
      return 'bg-green-500/10 border-green-500/30';
    case 'degraded':
      return 'bg-yellow-500/10 border-yellow-500/30';
    case 'critical':
      return 'bg-red-500/10 border-red-500/30';
    default:
      return 'bg-gray-500/10 border-gray-500/30';
  }
}

/**
 * Get text color based on health
 */
function getHealthTextClass(health: StageHealth): string {
  switch (health) {
    case 'healthy':
      return 'text-green-400';
    case 'degraded':
      return 'text-yellow-400';
    case 'critical':
      return 'text-red-400';
    default:
      return 'text-gray-400';
  }
}

/**
 * Get stage icon based on stage name
 */
function StageIcon({ stage, className }: { stage: string; className?: string }) {
  const baseClass = clsx('h-6 w-6', className);

  switch (stage) {
    case 'files':
      return <FileImage className={baseClass} />;
    case 'detect':
      return <Search className={baseClass} />;
    case 'batch':
      return <Package className={baseClass} />;
    case 'analyze':
      return <Brain className={baseClass} />;
    default:
      return <Activity className={baseClass} />;
  }
}

/**
 * Worker status icon
 */
function WorkerStatusIcon({ running }: { running: boolean }) {
  if (running) {
    return <CheckCircle className="h-3 w-3 text-green-500" />;
  }
  return <XCircle className="h-3 w-3 text-red-500" />;
}

/**
 * Individual pipeline stage box component
 */
interface StageBoxProps {
  stage: PipelineStage;
  showArrow?: boolean;
}

function StageBox({ stage, showArrow = true }: StageBoxProps) {
  return (
    <div className="flex items-center gap-2">
      <div
        className={clsx(
          'flex flex-col items-center rounded-lg border p-3 min-w-[100px]',
          getStageBackgroundClass(stage.health)
        )}
        data-testid={`stage-${stage.name}`}
      >
        {/* Icon */}
        <StageIcon
          stage={stage.name}
          className={getHealthTextClass(stage.health)}
        />

        {/* Label */}
        <Text className="mt-1 text-xs font-semibold text-white">
          {stage.label}
        </Text>

        {/* Primary metric */}
        <div className="mt-2 text-center">
          {stage.queueDepth !== undefined && (
            <Text className={clsx('text-xs', getHealthTextClass(stage.health))}>
              Queue: {stage.queueDepth}
            </Text>
          )}
          {stage.itemsPerMin !== undefined && (
            <Text className="text-xs text-gray-400">
              {stage.itemsPerMin}/min
            </Text>
          )}
          {stage.pendingCount !== undefined && (
            <Text className="text-xs text-gray-400">
              {stage.pendingCount} pending
            </Text>
          )}
        </div>

        {/* Latency metrics */}
        {stage.avgLatency && (
          <div className="mt-1 text-center">
            <Text className="text-xs text-gray-500">
              Avg: {stage.avgLatency}
            </Text>
            {stage.p95Latency && (
              <Text className="text-xs text-gray-600">
                P95: {stage.p95Latency}
              </Text>
            )}
          </div>
        )}
      </div>

      {/* Arrow to next stage */}
      {showArrow && (
        <ArrowRight className="h-5 w-5 text-gray-600 flex-shrink-0" />
      )}
    </div>
  );
}

/**
 * Compact worker grid with 8 status dots
 */
interface WorkerGridProps {
  workers: WorkerStatus[];
  onExpandClick: () => void;
  isExpanded: boolean;
}

function WorkerGrid({ workers, onExpandClick, isExpanded }: WorkerGridProps) {
  const runningCount = workers.filter((w) => w.running).length;

  return (
    <div
      className="mt-4 rounded-lg border border-gray-700 bg-gray-800/30 p-3"
      data-testid="worker-grid"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-[#76B900]" />
          <Text className="text-sm font-medium text-gray-300">Background Workers</Text>
        </div>
        <div className="flex items-center gap-3">
          <Badge
            color={runningCount === workers.length ? 'green' : 'amber'}
            size="sm"
            data-testid="workers-summary-badge"
          >
            {runningCount}/{workers.length} Running
          </Badge>
          <button
            type="button"
            onClick={onExpandClick}
            className="flex items-center gap-1 text-xs text-gray-400 hover:text-white transition-colors"
            data-testid="expand-workers-btn"
          >
            {isExpanded ? 'Collapse' : 'Expand Details'}
            {isExpanded ? (
              <ChevronUp className="h-3 w-3" />
            ) : (
              <ChevronDown className="h-3 w-3" />
            )}
          </button>
        </div>
      </div>

      {/* Compact dot grid */}
      <div className="mt-3 flex flex-wrap justify-center gap-3" data-testid="worker-dots">
        {workers.map((worker) => (
          <div
            key={worker.name}
            className="flex flex-col items-center gap-1"
            title={`${worker.displayName}: ${worker.running ? 'Running' : 'Stopped'}`}
            data-testid={`worker-dot-${worker.name}`}
          >
            <div
              className={clsx(
                'h-3 w-3 rounded-full',
                worker.running ? 'bg-green-500' : 'bg-red-500'
              )}
            />
            <Text className="text-[10px] text-gray-500">{worker.abbreviation}</Text>
          </div>
        ))}
      </div>

      {/* Expanded worker details */}
      {isExpanded && (
        <div
          className="mt-4 grid grid-cols-2 gap-2 border-t border-gray-700 pt-3 sm:grid-cols-4"
          data-testid="worker-details"
        >
          {workers.map((worker) => (
            <div
              key={worker.name}
              className={clsx(
                'flex items-center gap-2 rounded-md px-2 py-1.5',
                worker.running ? 'bg-gray-800/50' : 'bg-red-500/10'
              )}
              data-testid={`worker-detail-${worker.name}`}
            >
              <WorkerStatusIcon running={worker.running} />
              <Text className="text-xs text-gray-300">{worker.displayName}</Text>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * PipelineFlow - Visual pipeline flow diagram with stage metrics
 *
 * Displays a left-to-right flow diagram showing data journey through:
 * - Files: File watcher stage (items/min)
 * - Detect: RT-DETRv2 detection (queue depth, latency)
 * - Batch: Batch aggregation (pending count)
 * - Analyze: Nemotron analysis (queue depth, latency)
 *
 * Features:
 * - Color-coded health states (green/yellow/red)
 * - Queue depth and latency metrics per stage
 * - Total pipeline latency at bottom
 * - Compact 8-dot worker grid with expand option
 *
 * @example
 * ```tsx
 * <PipelineFlow
 *   files={{ name: 'files', label: 'Files', itemsPerMin: 12, health: 'healthy' }}
 *   detect={{ name: 'detect', label: 'Detect', queueDepth: 0, avgLatency: '14ms', p95Latency: '43s', health: 'healthy' }}
 *   batch={{ name: 'batch', label: 'Batch', pendingCount: 3, health: 'healthy' }}
 *   analyze={{ name: 'analyze', label: 'Analyze', queueDepth: 0, avgLatency: '2.1s', p95Latency: '4.8s', health: 'healthy' }}
 *   totalLatency={{ avg: '16.1s', p95: '47.8s', p99: '102s' }}
 *   workers={[...]}
 * />
 * ```
 */
export default function PipelineFlow({
  files,
  detect,
  batch,
  analyze,
  totalLatency,
  workers = [],
  workersDefaultExpanded = false,
  className,
}: PipelineFlowProps) {
  const [workersExpanded, setWorkersExpanded] = useState(workersDefaultExpanded);

  // Calculate overall pipeline health (worst of all stages)
  const stages = [files, detect, batch, analyze];
  const hasAnyDegraded = stages.some((s) => s.health === 'degraded');
  const hasAnyCritical = stages.some((s) => s.health === 'critical');

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="pipeline-flow-panel"
    >
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <Title className="flex items-center gap-2 text-white">
          <Activity className="h-5 w-5 text-[#76B900]" />
          Pipeline
          {(hasAnyDegraded || hasAnyCritical) && (
            <AlertTriangle
              className={clsx(
                'h-4 w-4',
                hasAnyCritical ? 'text-red-500' : 'text-yellow-500'
              )}
              data-testid="pipeline-warning-icon"
            />
          )}
        </Title>
        {totalLatency && (
          <Badge color="gray" size="sm" data-testid="total-latency-badge">
            Total: {totalLatency.avg} avg
          </Badge>
        )}
      </div>

      {/* Pipeline Flow Diagram */}
      <div
        className="flex flex-wrap items-center justify-center gap-1 sm:flex-nowrap sm:justify-start"
        data-testid="pipeline-stages"
      >
        <StageBox stage={files} />
        <StageBox stage={detect} />
        <StageBox stage={batch} />
        <StageBox stage={analyze} showArrow={false} />
      </div>

      {/* Total Pipeline Latency Summary */}
      {totalLatency && (
        <div
          className="mt-4 flex items-center justify-center gap-4 rounded-lg bg-gray-800/30 px-4 py-2"
          data-testid="total-latency-summary"
        >
          <Text className="text-xs text-gray-500">Total Pipeline:</Text>
          <div className="flex items-center gap-3 text-xs">
            <span className="text-gray-300">
              <span className="text-gray-500">Avg:</span> {totalLatency.avg}
            </span>
            <span className="text-gray-300">
              <span className="text-gray-500">P95:</span> {totalLatency.p95}
            </span>
            {totalLatency.p99 && (
              <span className="text-gray-300">
                <span className="text-gray-500">P99:</span> {totalLatency.p99}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Background Workers Grid */}
      {workers.length > 0 && (
        <WorkerGrid
          workers={workers}
          onExpandClick={() => setWorkersExpanded(!workersExpanded)}
          isExpanded={workersExpanded}
        />
      )}
    </Card>
  );
}
