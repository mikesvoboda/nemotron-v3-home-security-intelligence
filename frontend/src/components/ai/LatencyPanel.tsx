/**
 * LatencyPanel - Displays detailed pipeline latency metrics
 *
 * Shows latency statistics for each pipeline stage with percentile breakdowns.
 * Includes visual indicators for latency thresholds.
 */

import { Card, Title, Text, ProgressBar } from '@tremor/react';
import { clsx } from 'clsx';
import { Clock, ArrowRight, Timer } from 'lucide-react';

import type { AILatencyMetrics } from '../../services/metricsParser';

/**
 * Pipeline stage latency data
 */
interface PipelineStageLatency {
  avg_ms: number | null;
  min_ms?: number | null;
  max_ms?: number | null;
  p50_ms: number | null;
  p95_ms: number | null;
  p99_ms: number | null;
  sample_count: number;
}

/**
 * Full pipeline latency response
 */
interface PipelineLatencyData {
  watch_to_detect: PipelineStageLatency | null;
  detect_to_batch: PipelineStageLatency | null;
  batch_to_analyze: PipelineStageLatency | null;
  total_pipeline: PipelineStageLatency | null;
  window_minutes?: number;
  timestamp?: string;
}

export interface LatencyPanelProps {
  /** RT-DETR detection latency */
  detectionLatency?: AILatencyMetrics | null;
  /** Nemotron analysis latency */
  analysisLatency?: AILatencyMetrics | null;
  /** Pipeline stage latencies */
  pipelineLatency?: PipelineLatencyData | null;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Format milliseconds for display
 */
function formatMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return '-';
  if (ms < 1) return '< 1ms';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
}

/**
 * Get color based on latency thresholds
 */
function getLatencyColor(ms: number | null | undefined, thresholds: { warning: number; critical: number }): string {
  if (ms === null || ms === undefined) return 'gray';
  if (ms >= thresholds.critical) return 'red';
  if (ms >= thresholds.warning) return 'yellow';
  return 'green';
}

/**
 * Get progress bar color class
 */
function getProgressColor(ms: number | null | undefined, thresholds: { warning: number; critical: number }): 'green' | 'yellow' | 'red' | 'gray' {
  const color = getLatencyColor(ms, thresholds);
  if (color === 'green') return 'green';
  if (color === 'yellow') return 'yellow';
  if (color === 'red') return 'red';
  return 'gray';
}

/**
 * Calculate progress percentage capped at 100%
 */
function getProgressPercent(ms: number | null | undefined, maxMs: number): number {
  if (ms === null || ms === undefined) return 0;
  return Math.min((ms / maxMs) * 100, 100);
}

/**
 * Single latency stat row
 */
interface LatencyStatRowProps {
  label: string;
  latency: PipelineStageLatency | AILatencyMetrics | null;
  thresholds: { warning: number; critical: number };
  maxDisplay: number;
  icon?: React.ReactNode;
}

function LatencyStatRow({ label, latency, thresholds, maxDisplay, icon }: LatencyStatRowProps) {
  if (!latency || latency.sample_count === 0) {
    return (
      <div className="rounded-lg bg-gray-800/50 p-3">
        <div className="mb-2 flex items-center gap-2">
          {icon}
          <Text className="text-sm font-medium text-gray-400">{label}</Text>
        </div>
        <Text className="text-center text-sm text-gray-500">No data available</Text>
      </div>
    );
  }

  const progressColor = getProgressColor(latency.avg_ms, thresholds);

  return (
    <div className="rounded-lg bg-gray-800/50 p-3">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {icon}
          <Text className="text-sm font-medium text-gray-300">{label}</Text>
        </div>
        <Text className="text-xs text-gray-500">
          {latency.sample_count.toLocaleString()} samples
        </Text>
      </div>

      {/* Progress bar for average latency */}
      <div className="mb-3">
        <ProgressBar
          value={getProgressPercent(latency.avg_ms, maxDisplay)}
          color={progressColor}
          className="h-2"
        />
      </div>

      {/* Percentile breakdown */}
      <div className="grid grid-cols-4 gap-2 text-center">
        <div>
          <Text className="text-xs text-gray-500">Avg</Text>
          <Text className={clsx(
            'text-sm font-semibold',
            getLatencyColor(latency.avg_ms, thresholds) === 'red' ? 'text-red-400' :
            getLatencyColor(latency.avg_ms, thresholds) === 'yellow' ? 'text-yellow-400' :
            'text-white'
          )}>
            {formatMs(latency.avg_ms)}
          </Text>
        </div>
        <div>
          <Text className="text-xs text-gray-500">P50</Text>
          <Text className="text-sm font-semibold text-white">
            {formatMs(latency.p50_ms)}
          </Text>
        </div>
        <div>
          <Text className="text-xs text-gray-500">P95</Text>
          <Text className={clsx(
            'text-sm font-semibold',
            getLatencyColor(latency.p95_ms, thresholds) === 'red' ? 'text-red-400' :
            getLatencyColor(latency.p95_ms, thresholds) === 'yellow' ? 'text-yellow-400' :
            'text-white'
          )}>
            {formatMs(latency.p95_ms)}
          </Text>
        </div>
        <div>
          <Text className="text-xs text-gray-500">P99</Text>
          <Text className={clsx(
            'text-sm font-semibold',
            getLatencyColor(latency.p99_ms, thresholds) === 'red' ? 'text-red-400' :
            getLatencyColor(latency.p99_ms, thresholds) === 'yellow' ? 'text-yellow-400' :
            'text-white'
          )}>
            {formatMs(latency.p99_ms)}
          </Text>
        </div>
      </div>
    </div>
  );
}

/**
 * LatencyPanel - Comprehensive latency metrics display
 */
export default function LatencyPanel({
  detectionLatency,
  analysisLatency,
  pipelineLatency,
  className,
}: LatencyPanelProps) {
  return (
    <div className={clsx('space-y-4', className)} data-testid="latency-panel">
      {/* AI Service Latencies */}
      <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="ai-latency-card">
        <Title className="mb-4 flex items-center gap-2 text-white">
          <Timer className="h-5 w-5 text-[#76B900]" />
          AI Service Latency
        </Title>

        <div className="space-y-4">
          <LatencyStatRow
            label="RT-DETRv2 Detection"
            latency={detectionLatency ?? null}
            thresholds={{ warning: 500, critical: 2000 }}
            maxDisplay={2000}
            icon={<Clock className="h-4 w-4 text-gray-500" />}
          />

          <LatencyStatRow
            label="Nemotron Analysis"
            latency={analysisLatency ?? null}
            thresholds={{ warning: 5000, critical: 30000 }}
            maxDisplay={30000}
            icon={<Clock className="h-4 w-4 text-gray-500" />}
          />
        </div>
      </Card>

      {/* Pipeline Stage Latencies */}
      {pipelineLatency && (
        <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="pipeline-latency-card">
          <Title className="mb-4 flex items-center gap-2 text-white">
            <ArrowRight className="h-5 w-5 text-[#76B900]" />
            Pipeline Stage Latency
            {pipelineLatency.window_minutes && (
              <Text className="ml-2 text-sm font-normal text-gray-500">
                (last {pipelineLatency.window_minutes} min)
              </Text>
            )}
          </Title>

          <div className="space-y-4">
            <LatencyStatRow
              label="File Watch to Detection"
              latency={pipelineLatency.watch_to_detect}
              thresholds={{ warning: 100, critical: 500 }}
              maxDisplay={500}
            />

            <LatencyStatRow
              label="Detection to Batch"
              latency={pipelineLatency.detect_to_batch}
              thresholds={{ warning: 200, critical: 1000 }}
              maxDisplay={1000}
            />

            <LatencyStatRow
              label="Batch to Analysis"
              latency={pipelineLatency.batch_to_analyze}
              thresholds={{ warning: 100, critical: 500 }}
              maxDisplay={500}
            />

            {/* Total Pipeline (highlighted) */}
            {pipelineLatency.total_pipeline && pipelineLatency.total_pipeline.sample_count > 0 && (
              <div className="rounded-lg border border-[#76B900]/30 bg-[#76B900]/10 p-4">
                <div className="mb-2 flex items-center justify-between">
                  <Text className="text-sm font-semibold text-[#76B900]">Total Pipeline</Text>
                  <Text className="text-xs text-gray-400">
                    {pipelineLatency.total_pipeline.sample_count.toLocaleString()} samples
                  </Text>
                </div>
                <div className="grid grid-cols-4 gap-2 text-center">
                  <div>
                    <Text className="text-xs text-gray-400">Avg</Text>
                    <Text className="text-lg font-bold text-white">
                      {formatMs(pipelineLatency.total_pipeline.avg_ms)}
                    </Text>
                  </div>
                  <div>
                    <Text className="text-xs text-gray-400">P50</Text>
                    <Text className="text-lg font-bold text-white">
                      {formatMs(pipelineLatency.total_pipeline.p50_ms)}
                    </Text>
                  </div>
                  <div>
                    <Text className="text-xs text-gray-400">P95</Text>
                    <Text className="text-lg font-bold text-white">
                      {formatMs(pipelineLatency.total_pipeline.p95_ms)}
                    </Text>
                  </div>
                  <div>
                    <Text className="text-xs text-gray-400">P99</Text>
                    <Text className="text-lg font-bold text-white">
                      {formatMs(pipelineLatency.total_pipeline.p99_ms)}
                    </Text>
                  </div>
                </div>
              </div>
            )}
          </div>

          {pipelineLatency.timestamp && (
            <Text className="mt-4 text-xs text-gray-500">
              Updated: {new Date(pipelineLatency.timestamp).toLocaleTimeString()}
            </Text>
          )}
        </Card>
      )}
    </div>
  );
}
