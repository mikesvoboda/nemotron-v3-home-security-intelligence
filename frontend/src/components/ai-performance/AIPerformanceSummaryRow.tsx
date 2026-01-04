/**
 * AIPerformanceSummaryRow - Summary row for AI Performance page
 *
 * Displays 5 key indicators in a horizontal row:
 * - RT-DETRv2: Object detection model status and latency
 * - Nemotron: LLM analysis model status and latency
 * - Queues: Combined queue depth (detection + analysis)
 * - Throughput: Events processed per minute
 * - Errors: Total pipeline errors
 *
 * Features:
 * - Color-coded status indicators (green/yellow/red)
 * - Click-to-scroll to relevant sections
 * - Hover tooltips with additional detail
 * - Real-time updates via props
 * - Responsive: 5 columns desktop, 2x3 grid mobile
 */

import { clsx } from 'clsx';
import { CheckCircle, XCircle, AlertCircle, Layers, TrendingUp, AlertTriangle } from 'lucide-react';
import { useState, useCallback, type RefObject } from 'react';

import type { AIModelStatus } from '../../hooks/useAIMetrics';
import type { AILatencyMetrics } from '../../services/metricsParser';

export type IndicatorType = 'rtdetr' | 'nemotron' | 'queues' | 'throughput' | 'errors';
export type StatusColor = 'green' | 'yellow' | 'red' | 'gray';

export interface SectionRefs {
  rtdetr?: RefObject<HTMLElement | null>;
  nemotron?: RefObject<HTMLElement | null>;
  queues?: RefObject<HTMLElement | null>;
  throughput?: RefObject<HTMLElement | null>;
  errors?: RefObject<HTMLElement | null>;
}

export interface AIPerformanceSummaryRowProps {
  /** RT-DETR model status */
  rtdetr: AIModelStatus;
  /** Nemotron model status */
  nemotron: AIModelStatus;
  /** RT-DETR detection latency (for inline stats) */
  detectionLatency?: AILatencyMetrics | null;
  /** Nemotron analysis latency (for inline stats) */
  analysisLatency?: AILatencyMetrics | null;
  /** Detection queue depth */
  detectionQueueDepth: number;
  /** Analysis queue depth */
  analysisQueueDepth: number;
  /** Total detections processed */
  totalDetections: number;
  /** Total events created */
  totalEvents: number;
  /** Total errors */
  totalErrors: number;
  /** Throughput per minute (optional - can be calculated) */
  throughputPerMinute?: number;
  /** Refs to section elements for scroll-to behavior */
  sectionRefs?: SectionRefs;
  /** Callback when an indicator is clicked */
  onIndicatorClick?: (indicator: IndicatorType) => void;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Determine RT-DETRv2 status color based on model health and latency
 * Green: Running, <50ms
 * Yellow: Running, 50-200ms
 * Red: Down or >200ms
 */
function getRtdetrStatus(model: AIModelStatus, latency: AILatencyMetrics | null | undefined): StatusColor {
  // Red if model is down
  if (model.status === 'unhealthy') return 'red';

  // Gray if unknown
  if (model.status === 'unknown' || !latency?.avg_ms) return 'gray';

  // Check latency thresholds
  const avgMs = latency.avg_ms;
  if (avgMs > 200) return 'red';
  if (avgMs >= 50) return 'yellow';
  return 'green';
}

/**
 * Determine Nemotron status color based on model health and latency
 * Green: Running, <5s
 * Yellow: Running, 5-15s
 * Red: Down or >15s
 */
function getNemotronStatus(model: AIModelStatus, latency: AILatencyMetrics | null | undefined): StatusColor {
  // Red if model is down
  if (model.status === 'unhealthy') return 'red';

  // Gray if unknown
  if (model.status === 'unknown' || !latency?.avg_ms) return 'gray';

  // Check latency thresholds (in ms, so multiply by 1000)
  const avgMs = latency.avg_ms;
  if (avgMs > 15000) return 'red';
  if (avgMs >= 5000) return 'yellow';
  return 'green';
}

/**
 * Determine queue status color based on total queue depth
 * Green: 0-10 items
 * Yellow: 11-50 items
 * Red: 50+ items
 */
function getQueueStatus(totalDepth: number): StatusColor {
  if (totalDepth > 50) return 'red';
  if (totalDepth > 10) return 'yellow';
  return 'green';
}

/**
 * Determine throughput status color
 * Green: >0.5/min
 * Yellow: 0.1-0.5/min
 * Red: <0.1/min or 0
 */
function getThroughputStatus(perMinute: number): StatusColor {
  if (perMinute < 0.1) return 'red';
  if (perMinute <= 0.5) return 'yellow';
  return 'green';
}

/**
 * Determine error status color
 * Green: 0 errors
 * Yellow: 1-10 errors
 * Red: 10+ errors
 */
function getErrorStatus(errorCount: number): StatusColor {
  if (errorCount >= 10) return 'red';
  if (errorCount > 0) return 'yellow';
  return 'green';
}

/**
 * Format latency for display
 */
function formatLatency(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return '--';
  if (ms < 1) return '< 1ms';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/**
 * Get status icon component based on color
 */
function getStatusIcon(status: StatusColor): React.ReactNode {
  switch (status) {
    case 'green':
      return <CheckCircle className="h-4 w-4 text-green-500" aria-hidden="true" />;
    case 'yellow':
      return <AlertCircle className="h-4 w-4 text-yellow-500" aria-hidden="true" />;
    case 'red':
      return <XCircle className="h-4 w-4 text-red-500" aria-hidden="true" />;
    default:
      return <AlertCircle className="h-4 w-4 text-gray-500" aria-hidden="true" />;
  }
}

/**
 * Get CSS classes for status color
 */
function getStatusClasses(status: StatusColor): string {
  switch (status) {
    case 'green':
      return 'border-green-500/30 hover:border-green-500/50 bg-green-500/5';
    case 'yellow':
      return 'border-yellow-500/30 hover:border-yellow-500/50 bg-yellow-500/5';
    case 'red':
      return 'border-red-500/30 hover:border-red-500/50 bg-red-500/5';
    default:
      return 'border-gray-600/30 hover:border-gray-500/50 bg-gray-700/10';
  }
}

interface IndicatorCardProps {
  testId: string;
  label: string;
  value: string;
  status: StatusColor;
  icon: React.ReactNode;
  tooltipContent: React.ReactNode;
  onClick: () => void;
  ariaLabel: string;
}

/**
 * Individual indicator card component
 */
function IndicatorCard({
  testId,
  label,
  value,
  status,
  icon,
  tooltipContent,
  onClick,
  ariaLabel,
}: IndicatorCardProps) {
  const [showTooltip, setShowTooltip] = useState(false);

  return (
    <div className="relative">
      <button
        type="button"
        data-testid={testId}
        data-status={status}
        onClick={onClick}
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        onFocus={() => setShowTooltip(true)}
        onBlur={() => setShowTooltip(false)}
        aria-label={ariaLabel}
        className={clsx(
          'flex w-full flex-col items-center gap-1 rounded-lg border p-3 transition-all duration-200',
          'focus:outline-none focus:ring-2 focus:ring-[#76B900]/50 cursor-pointer',
          getStatusClasses(status)
        )}
      >
        <div className="flex items-center gap-2">
          {icon}
          <span className="text-xs font-medium text-gray-400">{label}</span>
        </div>
        <div className="flex items-center gap-1.5">
          {getStatusIcon(status)}
          <span className="text-sm font-semibold text-white">{value}</span>
        </div>
      </button>

      {/* Tooltip */}
      {showTooltip && (
        <div
          role="tooltip"
          className={clsx(
            'absolute left-1/2 z-50 -translate-x-1/2 transform',
            'mt-2 rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 shadow-lg',
            'text-xs text-gray-300',
            'w-48'
          )}
          style={{ top: '100%' }}
        >
          {tooltipContent}
          {/* Tooltip arrow */}
          <div
            className="absolute -top-1 left-1/2 h-2 w-2 -translate-x-1/2 rotate-45 transform border-l border-t border-gray-700 bg-gray-800"
            aria-hidden="true"
          />
        </div>
      )}
    </div>
  );
}

/**
 * AIPerformanceSummaryRow - Summary indicators for AI performance
 */
export default function AIPerformanceSummaryRow({
  rtdetr,
  nemotron,
  detectionLatency,
  analysisLatency,
  detectionQueueDepth,
  analysisQueueDepth,
  totalDetections,
  totalEvents,
  totalErrors,
  throughputPerMinute,
  sectionRefs,
  onIndicatorClick,
  className,
}: AIPerformanceSummaryRowProps) {
  // Calculate derived values
  const totalQueueDepth = detectionQueueDepth + analysisQueueDepth;

  // Calculate throughput if not provided (events per minute)
  // Default to a reasonable value based on total events
  const calculatedThroughput = throughputPerMinute ?? (totalEvents > 0 ? Math.max(0.1, totalEvents / 60) : 0);

  // Status colors
  const rtdetrStatus = getRtdetrStatus(rtdetr, detectionLatency);
  const nemotronStatus = getNemotronStatus(nemotron, analysisLatency);
  const queueStatus = getQueueStatus(totalQueueDepth);
  const throughputStatus = getThroughputStatus(calculatedThroughput);
  const errorStatus = getErrorStatus(totalErrors);

  // Handle indicator click with scroll behavior
  const handleIndicatorClick = useCallback(
    (indicator: IndicatorType) => {
      // Call external handler if provided
      onIndicatorClick?.(indicator);

      // Scroll to section if ref is provided
      const ref = sectionRefs?.[indicator];
      if (ref?.current) {
        ref.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    },
    [onIndicatorClick, sectionRefs]
  );

  return (
    <div
      data-testid="ai-summary-row"
      className={clsx(
        'grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5',
        className
      )}
    >
      {/* RT-DETRv2 Indicator */}
      <IndicatorCard
        testId="rtdetr-indicator"
        label="RT-DETRv2"
        value={formatLatency(detectionLatency?.avg_ms)}
        status={rtdetrStatus}
        icon={<AlertTriangle className="h-3.5 w-3.5 text-[#76B900]" aria-hidden="true" />}
        onClick={() => handleIndicatorClick('rtdetr')}
        ariaLabel={`RT-DETRv2: ${rtdetr.status}, average latency ${formatLatency(detectionLatency?.avg_ms)}. Click to scroll to RT-DETRv2 section.`}
        tooltipContent={
          <div className="space-y-1">
            <div className="font-medium text-white">RT-DETRv2 Object Detection</div>
            <div>Status: {rtdetr.status}</div>
            {detectionLatency && (
              <>
                <div>Avg: {formatLatency(detectionLatency.avg_ms)}</div>
                <div>P95: {formatLatency(detectionLatency.p95_ms)}</div>
                <div>P99: {formatLatency(detectionLatency.p99_ms)}</div>
                <div>Samples: {detectionLatency.sample_count?.toLocaleString()}</div>
              </>
            )}
          </div>
        }
      />

      {/* Nemotron Indicator */}
      <IndicatorCard
        testId="nemotron-indicator"
        label="Nemotron"
        value={formatLatency(analysisLatency?.avg_ms)}
        status={nemotronStatus}
        icon={<AlertTriangle className="h-3.5 w-3.5 text-purple-500" aria-hidden="true" />}
        onClick={() => handleIndicatorClick('nemotron')}
        ariaLabel={`Nemotron: ${nemotron.status}, average latency ${formatLatency(analysisLatency?.avg_ms)}. Click to scroll to Nemotron section.`}
        tooltipContent={
          <div className="space-y-1">
            <div className="font-medium text-white">Nemotron Risk Analysis</div>
            <div>Status: {nemotron.status}</div>
            {analysisLatency && (
              <>
                <div>Avg: {formatLatency(analysisLatency.avg_ms)}</div>
                <div>P95: {formatLatency(analysisLatency.p95_ms)}</div>
                <div>P99: {formatLatency(analysisLatency.p99_ms)}</div>
                <div>Samples: {analysisLatency.sample_count?.toLocaleString()}</div>
              </>
            )}
          </div>
        }
      />

      {/* Queues Indicator */}
      <IndicatorCard
        testId="queues-indicator"
        label="Queues"
        value={`${totalQueueDepth} queued`}
        status={queueStatus}
        icon={<Layers className="h-3.5 w-3.5 text-blue-500" aria-hidden="true" />}
        onClick={() => handleIndicatorClick('queues')}
        ariaLabel={`Queues: ${totalQueueDepth} items queued. Click to scroll to queues section.`}
        tooltipContent={
          <div className="space-y-1">
            <div className="font-medium text-white">Queue Depths</div>
            <div>Detection: {detectionQueueDepth}</div>
            <div>Analysis: {analysisQueueDepth}</div>
            <div className="mt-1 text-gray-400">
              {totalQueueDepth <= 10
                ? 'Healthy'
                : totalQueueDepth <= 50
                  ? 'Moderate load'
                  : 'Backlog detected'}
            </div>
          </div>
        }
      />

      {/* Throughput Indicator */}
      <IndicatorCard
        testId="throughput-indicator"
        label="Throughput"
        value={`${calculatedThroughput.toFixed(1)}/min`}
        status={throughputStatus}
        icon={<TrendingUp className="h-3.5 w-3.5 text-cyan-500" aria-hidden="true" />}
        onClick={() => handleIndicatorClick('throughput')}
        ariaLabel={`Throughput: ${calculatedThroughput.toFixed(1)} events per minute. Click to scroll to throughput section.`}
        tooltipContent={
          <div className="space-y-1">
            <div className="font-medium text-white">Pipeline Throughput</div>
            <div>Events/min: {calculatedThroughput.toFixed(2)}</div>
            <div>Total Detections: {totalDetections.toLocaleString()}</div>
            <div>Total Events: {totalEvents.toLocaleString()}</div>
            <div className="mt-1 text-gray-400">
              {calculatedThroughput > 0.5
                ? 'Good throughput'
                : calculatedThroughput >= 0.1
                  ? 'Low throughput'
                  : 'Very low throughput'}
            </div>
          </div>
        }
      />

      {/* Errors Indicator */}
      <IndicatorCard
        testId="errors-indicator"
        label="Errors"
        value={`${totalErrors} error${totalErrors !== 1 ? 's' : ''}`}
        status={errorStatus}
        icon={<AlertTriangle className="h-3.5 w-3.5 text-orange-500" aria-hidden="true" />}
        onClick={() => handleIndicatorClick('errors')}
        ariaLabel={`Errors: ${totalErrors} errors. Click to scroll to errors section.`}
        tooltipContent={
          <div className="space-y-1">
            <div className="font-medium text-white">Pipeline Errors</div>
            <div>Total Errors: {totalErrors}</div>
            <div className="mt-1 text-gray-400">
              {totalErrors === 0
                ? 'No errors detected'
                : totalErrors < 10
                  ? 'Some errors detected'
                  : 'Many errors detected - check logs'}
            </div>
          </div>
        }
      />
    </div>
  );
}
