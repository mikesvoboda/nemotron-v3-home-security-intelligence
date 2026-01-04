import { Card, Text } from '@tremor/react';
import { clsx } from 'clsx';
import {
  CheckCircle,
  AlertTriangle,
  XCircle,
  Cpu,
  Activity,
  Brain,
  Server,
  Monitor,
} from 'lucide-react';
import { useCallback } from 'react';

/**
 * Health status for a summary indicator
 */
export type HealthStatus = 'healthy' | 'degraded' | 'critical' | 'unknown';

/**
 * Individual indicator data
 */
export interface IndicatorData {
  /** Indicator ID for scroll targeting */
  id: string;
  /** Display label */
  label: string;
  /** Current health status */
  status: HealthStatus;
  /** Primary metric value (e.g., "38%", "2/2") */
  primaryValue?: string;
  /** Secondary metric value (e.g., "40C", "0.2/24GB") */
  secondaryValue?: string;
  /** Tertiary metric value (e.g., "0 queue") */
  tertiaryValue?: string;
}

/**
 * Props for SummaryRow component
 */
export interface SummaryRowProps {
  /** Overall system health status */
  overall: IndicatorData;
  /** GPU health status */
  gpu: IndicatorData;
  /** Pipeline health status */
  pipeline: IndicatorData;
  /** AI Models health status */
  aiModels: IndicatorData;
  /** Infrastructure health status */
  infrastructure: IndicatorData;
  /** Callback when an indicator is clicked */
  onIndicatorClick?: (id: string) => void;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Get background color class based on status
 */
function getStatusBackgroundClass(status: HealthStatus): string {
  switch (status) {
    case 'healthy':
      return 'bg-green-500/10 border-green-500/30 hover:bg-green-500/20';
    case 'degraded':
      return 'bg-yellow-500/10 border-yellow-500/30 hover:bg-yellow-500/20';
    case 'critical':
      return 'bg-red-500/10 border-red-500/30 hover:bg-red-500/20';
    default:
      return 'bg-gray-500/10 border-gray-500/30 hover:bg-gray-500/20';
  }
}

/**
 * Get text color class based on status
 */
function getStatusTextClass(status: HealthStatus): string {
  switch (status) {
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
 * Get status icon based on health status
 */
function StatusIcon({ status, className }: { status: HealthStatus; className?: string }) {
  const baseClass = clsx('h-5 w-5', className);

  switch (status) {
    case 'healthy':
      return <CheckCircle className={clsx(baseClass, 'text-green-500')} />;
    case 'degraded':
      return <AlertTriangle className={clsx(baseClass, 'text-yellow-500')} />;
    case 'critical':
      return <XCircle className={clsx(baseClass, 'text-red-500')} />;
    default:
      return <AlertTriangle className={clsx(baseClass, 'text-gray-500')} />;
  }
}

/**
 * Get category icon based on indicator ID
 */
function CategoryIcon({ id, className }: { id: string; className?: string }) {
  const baseClass = clsx('h-5 w-5', className);

  switch (id) {
    case 'overall':
      return <Monitor className={baseClass} />;
    case 'gpu':
      return <Cpu className={baseClass} />;
    case 'pipeline':
      return <Activity className={baseClass} />;
    case 'aiModels':
      return <Brain className={baseClass} />;
    case 'infrastructure':
      return <Server className={baseClass} />;
    default:
      return <Monitor className={baseClass} />;
  }
}

/**
 * Format status text for display
 */
function formatStatusText(status: HealthStatus): string {
  switch (status) {
    case 'healthy':
      return 'Healthy';
    case 'degraded':
      return 'Degraded';
    case 'critical':
      return 'Critical';
    default:
      return 'Unknown';
  }
}

/**
 * Individual indicator card component
 */
interface IndicatorCardProps {
  indicator: IndicatorData;
  onClick?: () => void;
  isOverall?: boolean;
}

function IndicatorCard({ indicator, onClick, isOverall = false }: IndicatorCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={clsx(
        'flex flex-col items-center justify-center rounded-lg border p-3 transition-all duration-200 cursor-pointer',
        getStatusBackgroundClass(indicator.status),
        isOverall && 'md:col-span-1'
      )}
      data-testid={`summary-indicator-${indicator.id}`}
      aria-label={`${indicator.label}: ${formatStatusText(indicator.status)}`}
    >
      {/* Header with icon and label */}
      <div className="mb-1 flex items-center gap-2">
        <CategoryIcon id={indicator.id} className="text-gray-400" />
        <Text className="text-xs font-semibold uppercase tracking-wide text-gray-400">
          {indicator.label}
        </Text>
      </div>

      {/* Status icon */}
      <div className="mb-1">
        <StatusIcon status={indicator.status} className="h-6 w-6" />
      </div>

      {/* Primary value or status text */}
      <Text className={clsx('text-sm font-semibold', getStatusTextClass(indicator.status))}>
        {indicator.primaryValue || formatStatusText(indicator.status)}
      </Text>

      {/* Secondary and tertiary values */}
      {(indicator.secondaryValue || indicator.tertiaryValue) && (
        <div className="mt-0.5 flex flex-col items-center gap-0.5">
          {indicator.secondaryValue && (
            <Text className="text-xs text-gray-500">{indicator.secondaryValue}</Text>
          )}
          {indicator.tertiaryValue && (
            <Text className="text-xs text-gray-500">{indicator.tertiaryValue}</Text>
          )}
        </div>
      )}
    </button>
  );
}

/**
 * SummaryRow - Quick health check indicators for system monitoring
 *
 * Displays 5 clickable health indicators at the top of the System page:
 * - Overall: Aggregate system health
 * - GPU: GPU utilization, temperature, memory
 * - Pipeline: Queue depth and throughput
 * - AI Models: Model status and inference count
 * - Infrastructure: Database, Redis, containers status
 *
 * Features:
 * - Color-coded status (green/yellow/red)
 * - Click to scroll to section
 * - Real-time WebSocket updates
 * - Responsive: 5 columns on desktop, 2x3 grid on mobile
 *
 * @example
 * ```tsx
 * <SummaryRow
 *   overall={{ id: 'overall', label: 'Overall', status: 'healthy' }}
 *   gpu={{ id: 'gpu', label: 'GPU', status: 'healthy', primaryValue: '38%', secondaryValue: '40C' }}
 *   pipeline={{ id: 'pipeline', label: 'Pipeline', status: 'healthy', primaryValue: '0 queue' }}
 *   aiModels={{ id: 'aiModels', label: 'AI Models', status: 'healthy', primaryValue: '2/2' }}
 *   infrastructure={{ id: 'infrastructure', label: 'Infra', status: 'healthy', primaryValue: '4/4' }}
 *   onIndicatorClick={(id) => scrollToSection(id)}
 * />
 * ```
 */
export default function SummaryRow({
  overall,
  gpu,
  pipeline,
  aiModels,
  infrastructure,
  onIndicatorClick,
  className,
}: SummaryRowProps) {
  const handleClick = useCallback(
    (id: string) => {
      onIndicatorClick?.(id);
    },
    [onIndicatorClick]
  );

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] p-4 shadow-lg', className)}
      data-testid="summary-row"
    >
      {/* Desktop: 5 columns in a row */}
      {/* Mobile: Overall on top (full width), then 2x2 grid below */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {/* Overall indicator - spans full width on mobile */}
        <div className="col-span-2 md:col-span-1">
          <IndicatorCard
            indicator={overall}
            onClick={() => handleClick(overall.id)}
            isOverall
          />
        </div>

        {/* Other indicators */}
        <IndicatorCard
          indicator={gpu}
          onClick={() => handleClick(gpu.id)}
        />
        <IndicatorCard
          indicator={pipeline}
          onClick={() => handleClick(pipeline.id)}
        />
        <IndicatorCard
          indicator={aiModels}
          onClick={() => handleClick(aiModels.id)}
        />
        <IndicatorCard
          indicator={infrastructure}
          onClick={() => handleClick(infrastructure.id)}
        />
      </div>
    </Card>
  );
}
