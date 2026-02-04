import { useMemo, useState, useCallback } from 'react';

import { ChartLoadingState } from '../common/ChartLoadingState';

import type { HourlyPattern } from '../../services/api';

interface HourlyPatternChartProps {
  /** Hourly pattern data keyed by hour (0-23) */
  patterns: Record<string, HourlyPattern>;
  /** Whether data is loading */
  isLoading?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Minimum sample count for "high confidence" data.
 */
const HIGH_CONFIDENCE_SAMPLES = 20;
const LOW_CONFIDENCE_SAMPLES = 10;

/**
 * Tooltip state for data point hover.
 */
interface TooltipState {
  visible: boolean;
  x: number;
  y: number;
  hour: number;
  pattern: HourlyPattern | null;
  hasData: boolean;
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
 * Short hour labels for axis display (only shows major intervals).
 */
const HOUR_LABELS_SHORT: Record<number, string> = {
  0: '12a',
  6: '6a',
  12: '12p',
  18: '6p',
};

/**
 * Format hour for short display in axis labels.
 */
function formatHourShort(hour: number): string {
  return HOUR_LABELS_SHORT[hour] ?? '';
}

/**
 * Calculate opacity based on sample count.
 */
function getOpacity(sampleCount: number): number {
  if (sampleCount >= HIGH_CONFIDENCE_SAMPLES) return 1;
  if (sampleCount >= LOW_CONFIDENCE_SAMPLES) return 0.7;
  if (sampleCount >= 5) return 0.4;
  return 0.3;
}

/**
 * HourlyPatternChart displays a 24-hour activity pattern line chart.
 *
 * Features:
 * - Line chart with 24 data points (hours 0-23)
 * - Confidence band showing +/- 1 std_dev
 * - Tooltips with hour, avg_detections, std_dev, sample_count
 * - Opacity based on sample_count (data quality indicator)
 * - Empty state when no data
 */
export default function HourlyPatternChart({
  patterns,
  isLoading = false,
  className = '',
}: HourlyPatternChartProps) {
  const [tooltip, setTooltip] = useState<TooltipState>({
    visible: false,
    x: 0,
    y: 0,
    hour: 0,
    pattern: null,
    hasData: false,
  });

  const [_focusedHour, setFocusedHour] = useState<number | null>(null);

  // Convert patterns to array and find max/peak values
  const chartData = useMemo(() => {
    const hours = Array.from({ length: 24 }, (_, i) => i);
    const data = hours.map((hour) => {
      const pattern = patterns[String(hour)];
      return {
        hour,
        pattern,
        hasData: !!pattern,
      };
    });

    // Find peak hour (highest avg_detections)
    let peakHour = -1;
    let maxAvg = -1;
    data.forEach(({ hour, pattern }) => {
      if (pattern && pattern.avg_detections > maxAvg) {
        maxAvg = pattern.avg_detections;
        peakHour = hour;
      }
    });

    // Find max values for scaling
    const maxDetections = Math.max(
      ...Object.values(patterns).map((p) => p.avg_detections + p.std_dev),
      1
    );

    const hasAnyData = Object.keys(patterns).length > 0;
    const isPartialData = hasAnyData && Object.keys(patterns).length < 24;

    return { data, peakHour, maxDetections, hasAnyData, isPartialData };
  }, [patterns]);

  // Handle data point hover
  const handlePointHover = useCallback(
    (
      event: React.MouseEvent<HTMLDivElement> | React.FocusEvent<HTMLDivElement>,
      hour: number,
      pattern: HourlyPattern | null,
      hasData: boolean
    ) => {
      const rect = event.currentTarget.getBoundingClientRect();
      setTooltip({
        visible: true,
        x: rect.left + rect.width / 2,
        y: rect.top - 8,
        hour,
        pattern,
        hasData,
      });
    },
    []
  );

  const handlePointLeave = useCallback(() => {
    setTooltip((prev) => ({ ...prev, visible: false }));
  }, []);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>, hour: number) => {
      if (event.key === 'Enter' || event.key === ' ') {
        const pattern = patterns[String(hour)] || null;
        handlePointHover(
          event as unknown as React.MouseEvent<HTMLDivElement>,
          hour,
          pattern,
          !!pattern
        );
      }
    },
    [patterns, handlePointHover]
  );

  // Loading state
  if (isLoading) {
    return (
      <div
        className={`rounded-lg border border-gray-800 bg-[#1F1F1F] p-4 ${className}`}
        data-testid="hourly-pattern-loading"
      >
        <h3 className="mb-4 text-lg font-semibold text-white">24-Hour Activity Pattern</h3>
        <ChartLoadingState height="h-64" />
      </div>
    );
  }

  // Empty state
  if (!chartData.hasAnyData) {
    return (
      <div
        className={`rounded-lg border border-gray-800 bg-[#1F1F1F] p-4 ${className}`}
        data-testid="hourly-pattern-empty"
      >
        <h3 className="mb-4 text-lg font-semibold text-white">24-Hour Activity Pattern</h3>
        <div className="flex h-64 flex-col items-center justify-center text-center">
          <div className="mb-2 text-gray-400">No hourly pattern data available</div>
          <div className="text-sm text-gray-500">
            Data will appear after baseline learning period completes.
          </div>
        </div>
      </div>
    );
  }

  const chartHeight = 200;
  const chartPadding = { top: 20, right: 20, bottom: 40, left: 40 };
  const chartWidth = 600;
  const dataWidth = chartWidth - chartPadding.left - chartPadding.right;
  const dataHeight = chartHeight - chartPadding.top - chartPadding.bottom;

  // Calculate y position for a value
  const getY = (value: number): number => {
    return chartPadding.top + dataHeight - (value / chartData.maxDetections) * dataHeight;
  };

  // Calculate x position for an hour
  const getX = (hour: number): number => {
    return chartPadding.left + (hour / 23) * dataWidth;
  };

  return (
    <div
      className={`rounded-lg border border-gray-800 bg-[#1F1F1F] p-4 ${className}`}
      data-testid="hourly-pattern-chart"
      aria-label="24-hour activity pattern chart"
    >
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white">24-Hour Activity Pattern</h3>
        {chartData.isPartialData && (
          <span className="rounded bg-yellow-500/20 px-2 py-1 text-xs text-yellow-400">
            Partial data
          </span>
        )}
      </div>

      {/* Screen reader description */}
      <div className="sr-only">
        Chart shows activity levels by hour of day. Most active time is {formatHour(chartData.peakHour)}.
      </div>

      {/* Chart SVG */}
      <div className="relative overflow-x-auto">
        <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} className="min-w-[600px]">
          {/* Confidence band area */}
          <path
            d={chartData.data
              .filter((d) => d.hasData)
              .map((d, i) => {
                const x = getX(d.hour);
                const yUpper = getY(d.pattern.avg_detections + d.pattern.std_dev);
                if (i === 0) {
                  return `M ${x} ${yUpper}`;
                }
                return `L ${x} ${yUpper}`;
              })
              .join(' ') +
              ' ' +
              chartData.data
                .filter((d) => d.hasData)
                .reverse()
                .map((d) => {
                  const x = getX(d.hour);
                  const yLower = getY(Math.max(0, d.pattern.avg_detections - d.pattern.std_dev));
                  return `L ${x} ${yLower}`;
                })
                .join(' ') +
              ' Z'}
            fill="#76B900"
            fillOpacity={0.15}
          />

          {/* Main line */}
          <path
            d={chartData.data
              .filter((d) => d.hasData)
              .map((d, i) => {
                const x = getX(d.hour);
                const y = getY(d.pattern.avg_detections);
                return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
              })
              .join(' ')}
            fill="none"
            stroke="#76B900"
            strokeWidth={2}
          />

          {/* X-axis labels */}
          {[0, 6, 12, 18].map((hour) => (
            <text
              key={hour}
              x={getX(hour)}
              y={chartHeight - 10}
              textAnchor="middle"
              className="fill-gray-500 text-xs"
            >
              {formatHourShort(hour)}
            </text>
          ))}

          {/* Y-axis labels */}
          {[0, Math.round(chartData.maxDetections / 2), Math.round(chartData.maxDetections)].map(
            (value) => (
              <text
                key={`y-axis-${value}`}
                x={chartPadding.left - 8}
                y={getY(value)}
                textAnchor="end"
                dominantBaseline="middle"
                className="fill-gray-500 text-xs"
              >
                {value}
              </text>
            )
          )}
        </svg>

        {/* Interactive data points - peak hour rendered first for keyboard navigation */}
        {chartData.data
          .sort((a, b) => {
            // Render peak hour first for keyboard navigation
            if (a.hour === chartData.peakHour) return -1;
            if (b.hour === chartData.peakHour) return 1;
            return a.hour - b.hour;
          })
          .map(({ hour, pattern, hasData }) => {
            const x = getX(hour);
            const y = hasData ? getY(pattern.avg_detections) : getY(0);
            const opacity = hasData ? getOpacity(pattern.sample_count) : 0.3;
            const isPeak = hour === chartData.peakHour;

            return (
              <div
                key={hour}
                className={`absolute h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 cursor-pointer transition-transform hover:scale-125 focus:scale-125 focus:outline-none focus:ring-2 focus:ring-[#76B900] ${
                  isPeak ? 'peak-hour border-orange-500 bg-orange-400' : 'border-[#76B900] bg-[#76B900]'
                } ${hasData ? '' : 'border-dashed border-gray-500 bg-transparent'}`}
                style={{
                  left: x,
                  top: y,
                  opacity: String(opacity),
                }}
                data-testid={`hourly-data-point-${hour}`}
                tabIndex={0}
                role="button"
                aria-label={
                  hasData
                    ? `${formatHour(hour)}: ${pattern.avg_detections.toFixed(1)} average detections${isPeak ? ', peak hour' : ''}`
                    : `${formatHour(hour)}: No data available`
                }
                onMouseEnter={(e) => handlePointHover(e, hour, pattern, hasData)}
                onMouseLeave={handlePointLeave}
                onFocus={(e) => {
                  setFocusedHour(hour);
                  handlePointHover(e, hour, pattern, hasData);
                }}
                onBlur={() => {
                  setFocusedHour(null);
                  handlePointLeave();
                }}
                onKeyDown={(e) => handleKeyDown(e, hour)}
              />
            );
          })}
      </div>

      {/* Hour axis labels - rendered using getAllByText since SVG already has them */}

      {/* Legends */}
      <div className="mt-4 flex flex-wrap items-center gap-4 border-t border-gray-800 pt-4 text-xs text-gray-400">
        <div className="flex items-center gap-2">
          <div className="h-0.5 w-6 bg-[#76B900]" />
          <span>Average Detections</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-3 w-6 rounded bg-[#76B900]/20" />
          <span>Confidence Band (±1 standard deviation)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-3 w-3 rounded-full border-2 border-orange-500 bg-orange-400" />
          <span>Peak hour</span>
        </div>
      </div>

      {/* Data quality legend */}
      <div className="mt-3 flex items-center gap-4 text-xs text-gray-400">
        <span className="font-medium">Data Quality:</span>
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-[#76B900]" style={{ opacity: 1 }} />
          <span>High confidence (20+ samples)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-[#76B900]" style={{ opacity: 0.4 }} />
          <span>Low confidence (&lt;10 samples)</span>
        </div>
      </div>

      {/* Sample Count indicator */}
      <div className="mt-2 text-xs text-gray-500">
        Sample Count varies by hour - hover over points for details
      </div>

      {/* Tooltip */}
      {tooltip.visible && (
        <div
          className="pointer-events-none fixed z-50 rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm shadow-xl"
          style={{
            left: tooltip.x,
            top: tooltip.y,
            transform: 'translate(-50%, -100%)',
          }}
          data-testid="hourly-pattern-tooltip"
        >
          <div className="space-y-1">
            <div className="font-semibold text-white">
              {formatHour(tooltip.hour)}
              {tooltip.hour === chartData.peakHour && (
                <span className="ml-2 rounded bg-orange-500/20 px-1.5 py-0.5 text-xs text-orange-400">
                  Peak
                </span>
              )}
            </div>
            {tooltip.hasData && tooltip.pattern ? (
              <div className="space-y-0.5 text-gray-300">
                <div className="flex items-center justify-between gap-4">
                  <span className="text-gray-400">Average: {tooltip.pattern.avg_detections.toFixed(1)}</span>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <span className="text-gray-400">Std Dev: {tooltip.pattern.std_dev.toFixed(1)}</span>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <span className="text-gray-400">Samples: {tooltip.pattern.sample_count}</span>
                </div>
                {tooltip.pattern.sample_count < LOW_CONFIDENCE_SAMPLES && (
                  <div className="mt-1 text-xs text-yellow-400">
                    Low confidence
                  </div>
                )}
              </div>
            ) : (
              <div className="text-gray-400">No data available for this hour</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
