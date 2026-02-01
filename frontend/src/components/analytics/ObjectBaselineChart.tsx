import { useMemo, useState, useCallback } from 'react';

import type { ObjectBaseline } from '../../services/api';

interface ObjectBaselineChartProps {
  /** Object baseline data keyed by class name */
  baselines: Record<string, ObjectBaseline>;
  /** Whether sorting controls should be shown */
  sortable?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Color palette for object classes.
 */
const CLASS_COLORS: Record<string, string> = {
  person: 'bg-blue-500',
  vehicle: 'bg-green-500',
  car: 'bg-green-600',
  truck: 'bg-green-700',
  animal: 'bg-orange-500',
  dog: 'bg-orange-600',
  cat: 'bg-orange-400',
  bicycle: 'bg-purple-500',
  motorcycle: 'bg-purple-600',
};

const DEFAULT_COLOR = 'bg-gray-500';

/**
 * Sort options for the chart.
 */
type SortOption = 'avg_hourly' | 'total_detections' | 'peak_hour' | 'alphabetical';
const SORT_LABELS: Record<SortOption, string> = {
  avg_hourly: 'Average Hourly',
  total_detections: 'Total Detections',
  peak_hour: 'Peak Hour',
  alphabetical: 'Alphabetical',
};

/**
 * Metric options.
 */
type MetricOption = 'avg_hourly' | 'peak_hour' | 'total_detections';
const METRIC_LABELS: Record<MetricOption, string> = {
  avg_hourly: 'Avg/Hour',
  peak_hour: 'Peak Hour',
  total_detections: 'Total',
};

/**
 * Tooltip state for bar hover.
 */
interface TooltipState {
  visible: boolean;
  x: number;
  y: number;
  objectClass: string;
  baseline: ObjectBaseline;
  metric: MetricOption;
  isMostFrequent: boolean;
}

/**
 * Format hour number to 12-hour time string.
 */
function formatHour(hour: number): string {
  if (hour === 0) return '12:00 AM';
  if (hour === 12) return '12:00 PM';
  if (hour < 12) return `${hour}:00 AM`;
  return `${hour - 12}:00 PM`;
}

/**
 * Format class name for display.
 */
function formatClassName(name: string): string {
  return name
    .split(/[-_]/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

/**
 * Format large numbers with commas.
 */
function formatNumber(num: number): string {
  return num.toLocaleString();
}

/**
 * Get color class for an object class.
 */
function getColorClass(objectClass: string): string {
  return CLASS_COLORS[objectClass.toLowerCase()] ?? DEFAULT_COLOR;
}

/**
 * ObjectBaselineChart displays per-class baseline statistics.
 *
 * Features:
 * - Grouped bars per object class
 * - Metrics: avg_hourly, peak_hour, total_detections
 * - Tooltips with class and values
 * - Color-coded by class
 * - Empty state when no data
 */
export default function ObjectBaselineChart({
  baselines,
  sortable = false,
  className = '',
}: ObjectBaselineChartProps) {
  const [sortBy, setSortBy] = useState<SortOption>('alphabetical');
  const [selectedMetric, setSelectedMetric] = useState<MetricOption>('avg_hourly');
  const [highlightedMetric, setHighlightedMetric] = useState<MetricOption | null>(null);
  const [sortOpen, setSortOpen] = useState(false);
  const [metricOpen, setMetricOpen] = useState(false);

  const [tooltip, setTooltip] = useState<TooltipState | null>(null);

  // Process and sort data
  const chartData = useMemo(() => {
    const entries = Object.entries(baselines);
    const hasAnyData = entries.length > 0;
    const hasSingleClass = entries.length === 1;

    // Find most frequent class (highest avg_hourly)
    let mostFrequentClass = '';
    let maxAvgHourly = 0;
    entries.forEach(([cls, baseline]) => {
      if (baseline.avg_hourly > maxAvgHourly) {
        maxAvgHourly = baseline.avg_hourly;
        mostFrequentClass = cls;
      }
    });

    // Sort entries
    const sortedEntries = [...entries];
    if (sortable || hasSingleClass) {
      switch (sortBy) {
        case 'avg_hourly':
          sortedEntries.sort((a, b) => b[1].avg_hourly - a[1].avg_hourly);
          break;
        case 'total_detections':
          sortedEntries.sort((a, b) => b[1].total_detections - a[1].total_detections);
          break;
        case 'peak_hour':
          sortedEntries.sort((a, b) => a[1].peak_hour - b[1].peak_hour);
          break;
        case 'alphabetical':
        default:
          sortedEntries.sort((a, b) => a[0].localeCompare(b[0]));
          break;
      }
    } else {
      // When not sortable, always use alphabetical
      sortedEntries.sort((a, b) => a[0].localeCompare(b[0]));
    }

    // Find max values for scaling
    const maxAvg = Math.max(...entries.map(([, b]) => b.avg_hourly), 1);
    const maxTotal = Math.max(...entries.map(([, b]) => b.total_detections), 1);

    return {
      entries: sortedEntries,
      hasAnyData,
      hasSingleClass,
      mostFrequentClass,
      maxAvg,
      maxTotal,
    };
  }, [baselines, sortBy, sortable]);

  // Handle bar hover
  const handleBarHover = useCallback(
    (
      event: React.MouseEvent<HTMLElement> | React.FocusEvent<HTMLElement>,
      objectClass: string,
      baseline: ObjectBaseline,
      metric: MetricOption
    ) => {
      const rect = event.currentTarget.getBoundingClientRect();
      setTooltip({
        visible: true,
        x: rect.left + rect.width / 2,
        y: rect.top - 8,
        objectClass,
        baseline,
        metric,
        isMostFrequent: objectClass === chartData.mostFrequentClass,
      });
    },
    [chartData.mostFrequentClass]
  );

  const handleBarLeave = useCallback(() => {
    setTooltip(null);
  }, []);

  // Empty state
  if (!chartData.hasAnyData) {
    return (
      <div
        className={`rounded-lg border border-gray-800 bg-[#1F1F1F] p-4 ${className}`}
        data-testid="object-baseline-empty"
      >
        <h3 className="mb-4 text-lg font-semibold text-white">Detection by Object Type</h3>
        <div className="flex h-64 flex-col items-center justify-center text-center">
          <div className="mb-2 text-gray-400">No object baseline data available</div>
          <div className="text-sm text-gray-500">
            Data will appear after objects are detected and processed.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`flex flex-col lg:flex-row rounded-lg border border-gray-800 bg-[#1F1F1F] p-4 ${className}`}
      data-testid="object-baseline-chart"
      aria-label="Object baseline statistics chart"
    >
      <div className="flex-1">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-lg font-semibold text-white">Detection by Object Type</h3>

          <div className="flex items-center gap-2">
            {/* Metric selector */}
            <div className="relative">
              <button
                className="flex items-center gap-1 rounded bg-gray-700 px-2 py-1 text-xs text-gray-300 hover:bg-gray-600"
                data-testid="metric-selector"
                onClick={() => setMetricOpen(!metricOpen)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    setMetricOpen(!metricOpen);
                  }
                }}
              >
                <span>Metric: {METRIC_LABELS[selectedMetric]}</span>
                <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {metricOpen && (
                <div className="absolute right-0 top-full z-10 mt-1 rounded bg-gray-800 py-1 shadow-lg">
                  {(Object.keys(METRIC_LABELS) as MetricOption[]).map((metric) => (
                    <button
                      key={metric}
                      className="block w-full px-3 py-1 text-left text-xs text-gray-300 hover:bg-gray-700"
                      onClick={() => {
                        setSelectedMetric(metric);
                        setMetricOpen(false);
                      }}
                    >
                      {METRIC_LABELS[metric]}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Sort selector (only show if sortable and multiple classes) */}
            {sortable && !chartData.hasSingleClass && (
              <div className="relative">
                <button
                  className="flex items-center gap-1 rounded bg-gray-700 px-2 py-1 text-xs text-gray-300 hover:bg-gray-600"
                  data-testid="sort-selector"
                  onClick={() => setSortOpen(!sortOpen)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      setSortOpen(!sortOpen);
                    }
                  }}
                >
                  <span>Sort: {SORT_LABELS[sortBy]}</span>
                  <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                {sortOpen && (
                  <div className="absolute right-0 top-full z-10 mt-1 rounded bg-gray-800 py-1 shadow-lg">
                    {(Object.keys(SORT_LABELS) as SortOption[]).map((option) => (
                      <button
                        key={option}
                        className="block w-full px-3 py-1 text-left text-xs text-gray-300 hover:bg-gray-700"
                        onClick={() => {
                          setSortBy(option);
                          setSortOpen(false);
                        }}
                      >
                        {SORT_LABELS[option]}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Screen reader description */}
        <div className="sr-only">
          Chart shows detection statistics by object type. Most frequent type is{' '}
          {formatClassName(chartData.mostFrequentClass)}.
        </div>

        {/* Chart content */}
        <div className="space-y-4">
          {chartData.entries.map(([objectClass, baseline]) => {
            const colorClass = getColorClass(objectClass);
            const avgWidth = (baseline.avg_hourly / chartData.maxAvg) * 100;
            const totalWidth = (baseline.total_detections / chartData.maxTotal) * 100;

            return (
              <div
                key={objectClass}
                className={`group ${colorClass} ${colorClass.replace('bg-', 'border-l-4 border-')}`}
                data-testid={`object-group-${objectClass}`}
                data-class={objectClass}
              >
                {/* Class name */}
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-sm font-medium text-white">
                    {formatClassName(objectClass)}
                  </span>
                </div>

                {/* Metrics bars */}
                <div className="space-y-1 pl-2">
                  {/* Average Hourly */}
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      className={`h-5 rounded transition-all cursor-pointer hover:brightness-110 ${colorClass} ${
                        selectedMetric === 'avg_hourly' || highlightedMetric === 'avg_hourly'
                          ? 'emphasized ring-2 ring-white/30'
                          : 'opacity-70'
                      } ${highlightedMetric === 'avg_hourly' ? 'highlighted' : ''}`}
                      style={{ width: `${avgWidth}%`, minWidth: '20px' }}
                      data-testid={`metric-${objectClass}-avg_hourly`}
                      data-metric="avg_hourly"
                      onMouseEnter={(e) => handleBarHover(e, objectClass, baseline, 'avg_hourly')}
                      onMouseLeave={handleBarLeave}
                      onFocus={(e) => handleBarHover(e, objectClass, baseline, 'avg_hourly')}
                      onBlur={handleBarLeave}
                      aria-label={`${formatClassName(objectClass)} average hourly: ${baseline.avg_hourly.toFixed(1)} per hour`}
                    />
                    <span className="text-xs text-gray-400">{baseline.avg_hourly.toFixed(1)}/hr</span>
                  </div>

                  {/* Peak Hour */}
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      className={`h-5 rounded transition-all cursor-pointer hover:brightness-110 bg-orange-500 ${
                        selectedMetric === 'peak_hour' || highlightedMetric === 'peak_hour'
                          ? 'emphasized ring-2 ring-white/30'
                          : 'opacity-50'
                      } ${highlightedMetric === 'peak_hour' ? 'highlighted' : ''}`}
                      style={{ width: `${(baseline.peak_hour / 23) * 100}%`, minWidth: '20px' }}
                      data-testid={`metric-${objectClass}-peak_hour`}
                      data-metric="peak_hour"
                      onMouseEnter={(e) => handleBarHover(e, objectClass, baseline, 'peak_hour')}
                      onMouseLeave={handleBarLeave}
                      onFocus={(e) => handleBarHover(e, objectClass, baseline, 'peak_hour')}
                      onBlur={handleBarLeave}
                      aria-label={`${formatClassName(objectClass)} peak hour: ${formatHour(baseline.peak_hour)}`}
                    />
                    <span className="text-xs text-gray-400">{formatHour(baseline.peak_hour)}</span>
                  </div>

                  {/* Total Detections */}
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      className={`h-5 rounded transition-all cursor-pointer hover:brightness-110 bg-gray-500 ${
                        selectedMetric === 'total_detections' || highlightedMetric === 'total_detections'
                          ? 'emphasized ring-2 ring-white/30'
                          : 'opacity-50'
                      } ${highlightedMetric === 'total_detections' ? 'highlighted' : ''}`}
                      style={{ width: `${totalWidth}%`, minWidth: '20px' }}
                      data-testid={`metric-${objectClass}-total_detections`}
                      data-metric="total_detections"
                      onMouseEnter={(e) => handleBarHover(e, objectClass, baseline, 'total_detections')}
                      onMouseLeave={handleBarLeave}
                      onFocus={(e) => handleBarHover(e, objectClass, baseline, 'total_detections')}
                      onBlur={handleBarLeave}
                      aria-label={`${formatClassName(objectClass)} total detections: ${formatNumber(baseline.total_detections)}`}
                    />
                    <span className="text-xs text-gray-400">{formatNumber(baseline.total_detections)}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Metric legend */}
        <div
          className="mt-4 flex flex-wrap items-center gap-4 border-t border-gray-800 pt-4 text-xs text-gray-400"
          data-testid="metric-legend"
        >
          <button
            type="button"
            className="flex items-center gap-1 cursor-pointer hover:text-white"
            data-testid="legend-item-avg_hourly"
            onClick={() => setHighlightedMetric(highlightedMetric === 'avg_hourly' ? null : 'avg_hourly')}
          >
            <div className="h-3 w-3 rounded bg-blue-500" />
            <span>Avg/Hour</span>
          </button>
          <button
            type="button"
            className="flex items-center gap-1 cursor-pointer hover:text-white"
            data-testid="legend-item-peak_hour"
            onClick={() => setHighlightedMetric(highlightedMetric === 'peak_hour' ? null : 'peak_hour')}
          >
            <div className="h-3 w-3 rounded bg-orange-500" />
            <span>Peak Hour</span>
          </button>
          <button
            type="button"
            className="flex items-center gap-1 cursor-pointer hover:text-white"
            data-testid="legend-item-total_detections"
            onClick={() => setHighlightedMetric(highlightedMetric === 'total_detections' ? null : 'total_detections')}
          >
            <div className="h-3 w-3 rounded bg-gray-500" />
            <span>Total</span>
          </button>
        </div>

        {/* Color legend for object types */}
        <div
          className="mt-3 flex flex-wrap items-center gap-3 text-xs text-gray-400"
          data-testid="color-legend"
        >
          <span className="font-medium">Object Types:</span>
          {chartData.entries.map(([objectClass]) => (
            <div key={objectClass} className="flex items-center gap-1" title={formatClassName(objectClass)}>
              <div className={`h-2 w-2 rounded-sm ${getColorClass(objectClass)}`} />
              {/* Class name hidden to avoid duplicate text - use title attribute for hover */}
            </div>
          ))}
        </div>
      </div>

      {/* Tooltip */}
      {tooltip && tooltip.visible && (
        <div
          className="pointer-events-none fixed z-50 rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm shadow-xl"
          style={{
            left: tooltip.x,
            top: tooltip.y,
            transform: 'translate(-50%, -100%)',
          }}
          data-testid="object-baseline-tooltip"
        >
          <div className="space-y-1">
            <div className="font-semibold text-white">
              {formatClassName(tooltip.objectClass)}
              {tooltip.isMostFrequent && (
                <span className="ml-2 rounded bg-green-500/20 px-1.5 py-0.5 text-xs text-green-400">
                  Most frequent
                </span>
              )}
            </div>
            <div className="space-y-0.5 text-gray-300">
              {tooltip.metric === 'avg_hourly' && (
                <div className="flex items-center justify-between gap-4">
                  <span className="text-gray-400">Average Hourly: {tooltip.baseline.avg_hourly.toFixed(1)}</span>
                </div>
              )}
              {tooltip.metric === 'peak_hour' && (
                <div className="flex items-center justify-between gap-4">
                  <span className="text-gray-400">Peak Hour: {formatHour(tooltip.baseline.peak_hour)} ({tooltip.baseline.peak_hour})</span>
                </div>
              )}
              {tooltip.metric === 'total_detections' && (
                <div className="flex items-center justify-between gap-4">
                  <span className="text-gray-400">Total Detections: {formatNumber(tooltip.baseline.total_detections)}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
