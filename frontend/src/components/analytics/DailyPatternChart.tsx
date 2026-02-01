import { useMemo, useState, useCallback } from 'react';

import type { DailyPattern } from '../../services/api';

interface DailyPatternChartProps {
  /** Daily pattern data keyed by day name (monday, tuesday, etc.) */
  patterns: Record<string, DailyPattern>;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Days in order from Monday to Sunday.
 */
const DAYS_ORDER = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
const DAY_LABELS: Record<string, string> = {
  monday: 'Mon',
  tuesday: 'Tue',
  wednesday: 'Wed',
  thursday: 'Thu',
  friday: 'Fri',
  saturday: 'Sat',
  sunday: 'Sun',
};
const DAY_FULL_NAMES: Record<string, string> = {
  monday: 'Monday',
  tuesday: 'Tuesday',
  wednesday: 'Wednesday',
  thursday: 'Thursday',
  friday: 'Friday',
  saturday: 'Saturday',
  sunday: 'Sunday',
};
const WEEKENDS = new Set(['saturday', 'sunday']);

/**
 * Minimum samples for high confidence.
 */
const HIGH_CONFIDENCE_SAMPLES = 100;

/**
 * Tooltip state for bar hover.
 */
interface TooltipState {
  visible: boolean;
  x: number;
  y: number;
  day: string;
  pattern: DailyPattern | null;
  hasData: boolean;
  isBusiest: boolean;
  isQuietest: boolean;
  weeksOfData: number;
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
 * Get color intensity class based on activity level.
 */
function getActivityColorClass(
  avgDetections: number,
  maxDetections: number
): { bg: string; opacity: string } {
  const intensity = avgDetections / maxDetections;
  if (intensity >= 0.8) return { bg: 'bg-blue-600', opacity: 'opacity-100' };
  if (intensity >= 0.6) return { bg: 'bg-blue-500', opacity: 'opacity-80' };
  if (intensity >= 0.4) return { bg: 'bg-blue-400', opacity: 'opacity-60' };
  if (intensity >= 0.2) return { bg: 'bg-blue-300', opacity: 'opacity-40' };
  return { bg: 'bg-blue-200', opacity: 'opacity-30' };
}

/**
 * DailyPatternChart displays a weekly activity pattern bar chart.
 *
 * Features:
 * - Bar chart with 7 bars (Mon-Sun)
 * - Peak hour indicator within each bar
 * - Tooltips with day, avg_detections, peak_hour, total_samples
 * - Color intensity based on activity level
 * - Empty state when no data
 */
export default function DailyPatternChart({
  patterns,
  className = '',
}: DailyPatternChartProps) {
  const [tooltip, setTooltip] = useState<TooltipState>({
    visible: false,
    x: 0,
    y: 0,
    day: '',
    pattern: null,
    hasData: false,
    isBusiest: false,
    isQuietest: false,
    weeksOfData: 0,
  });

  // Process data and find max/busiest/quietest
  const chartData = useMemo(() => {
    const hasAnyData = Object.keys(patterns).length > 0;
    const isPartialWeek = hasAnyData && Object.keys(patterns).length < 7;

    // Find max, busiest, and quietest days
    let maxDetections = 0;
    let busiestDay = '';
    let quietestDay = '';
    let minDetections = Infinity;

    Object.entries(patterns).forEach(([day, pattern]) => {
      if (pattern.avg_detections > maxDetections) {
        maxDetections = pattern.avg_detections;
        busiestDay = day;
      }
      if (pattern.avg_detections < minDetections) {
        minDetections = pattern.avg_detections;
        quietestDay = day;
      }
    });

    // Ensure maxDetections is at least 1 for scaling
    maxDetections = Math.max(maxDetections, 1);

    // Check for low confidence (any day with less than 168 samples = 1 week)
    const hasLowConfidence = Object.values(patterns).some((p) => p.total_samples < HIGH_CONFIDENCE_SAMPLES);

    return {
      hasAnyData,
      isPartialWeek,
      maxDetections,
      busiestDay,
      quietestDay,
      hasLowConfidence,
    };
  }, [patterns]);

  // Handle bar hover
  const handleBarHover = useCallback(
    (
      event: React.MouseEvent<HTMLDivElement> | React.FocusEvent<HTMLDivElement>,
      day: string,
      pattern: DailyPattern | null,
      hasData: boolean
    ) => {
      const rect = event.currentTarget.getBoundingClientRect();
      const weeksOfData = pattern ? Math.round(pattern.total_samples / 24) : 0;
      setTooltip({
        visible: true,
        x: rect.left + rect.width / 2,
        y: rect.top - 8,
        day,
        pattern,
        hasData,
        isBusiest: day === chartData.busiestDay,
        isQuietest: day === chartData.quietestDay,
        weeksOfData,
      });
    },
    [chartData.busiestDay, chartData.quietestDay]
  );

  const handleBarLeave = useCallback(() => {
    setTooltip((prev) => ({ ...prev, visible: false }));
  }, []);

  // Empty state
  if (!chartData.hasAnyData) {
    return (
      <div
        className={`rounded-lg border border-gray-800 bg-[#1F1F1F] p-4 ${className}`}
        data-testid="daily-pattern-empty"
      >
        <h3 className="mb-4 text-lg font-semibold text-white">Weekly Activity Pattern</h3>
        <div className="flex h-64 flex-col items-center justify-center text-center">
          <div className="mb-2 text-gray-400">No daily pattern data available</div>
          <div className="text-sm text-gray-500">
            Data will appear after at least one week of learning completes.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`rounded-lg border border-gray-800 bg-[#1F1F1F] p-4 ${className}`}
      data-testid="daily-pattern-chart"
      aria-label="Weekly activity pattern chart"
    >
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white">Weekly Activity Pattern</h3>
        <div className="flex items-center gap-2">
          {chartData.isPartialWeek && (
            <span className="rounded bg-yellow-500/20 px-2 py-1 text-xs text-yellow-400">
              Partial week
            </span>
          )}
          {chartData.hasLowConfidence && (
            <span className="rounded bg-blue-500/20 px-2 py-1 text-xs text-blue-400">
              Low confidence
            </span>
          )}
        </div>
      </div>

      {/* Screen reader description - text matches accessibility test */}
      <p className="sr-only">
        {'Chart shows activity levels by day of week. Busiest day is '}
        {DAY_FULL_NAMES[chartData.busiestDay]}.
      </p>

      {/* Bar chart */}
      <div className="flex items-end justify-between gap-2 h-48">
        {DAYS_ORDER.map((day) => {
          const pattern = patterns[day];
          const hasData = !!pattern;
          const isWeekend = WEEKENDS.has(day);
          const heightPercent = hasData
            ? (pattern.avg_detections / chartData.maxDetections) * 100
            : 0;
          const colorClass = hasData
            ? getActivityColorClass(pattern.avg_detections, chartData.maxDetections)
            : { bg: '', opacity: '' };

          return (
            <div
              key={day}
              className="flex flex-1 flex-col items-center"
            >
              {/* Bar container */}
              <div
                className={`relative w-full flex flex-col justify-end h-40 rounded-t cursor-pointer transition-transform hover:scale-105 focus:scale-105 focus:outline-none focus:ring-2 focus:ring-[#76B900] ${
                  hasData ? colorClass.opacity : 'no-data'
                } ${isWeekend ? 'weekend' : ''} ${hasData ? colorClass.bg : ''}`}
                data-testid={`daily-bar-${day}`}
                data-day={day}
                tabIndex={0}
                role="button"
                aria-label={
                  hasData
                    ? `${DAY_FULL_NAMES[day]}: ${pattern.avg_detections.toFixed(1)} average detections, peak at ${formatHour(pattern.peak_hour)}`
                    : `${DAY_FULL_NAMES[day]}: No data available`
                }
                onMouseEnter={(e) => handleBarHover(e, day, pattern || null, hasData)}
                onMouseLeave={handleBarLeave}
                onFocus={(e) => handleBarHover(e, day, pattern || null, hasData)}
                onBlur={handleBarLeave}
              >
                {/* Bar fill */}
                <div
                  className={`w-full rounded-t transition-all ${
                    hasData
                      ? `${colorClass.bg} ${isWeekend ? 'bg-opacity-80' : ''}`
                      : 'bg-gray-700/30 border border-dashed border-gray-600'
                  }`}
                  style={{ height: hasData ? `${heightPercent}%` : '10%' }}
                >
                  {/* Peak hour indicator */}
                  {hasData && (
                    <div
                      className="absolute left-1/2 -translate-x-1/2 w-2 h-2 rounded-full bg-orange-500 shadow-lg"
                      data-testid={`peak-indicator-${day}`}
                      data-peak-hour={pattern.peak_hour}
                      style={{
                        top: `${100 - heightPercent + 5}%`,
                      }}
                    />
                  )}
                </div>
              </div>

              {/* Day label */}
              <div className={`mt-2 text-xs ${isWeekend ? 'text-blue-400' : 'text-gray-400'}`}>
                {DAY_LABELS[day]}
              </div>
            </div>
          );
        })}
      </div>

      {/* Legends */}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-4 border-t border-gray-800 pt-4 text-xs text-gray-400">
        {/* Activity level legend */}
        <div className="flex items-center gap-2">
          <span className="font-medium">Activity Level:</span>
          <div className="flex items-center gap-1">
            <span>Low</span>
            <div className="flex gap-0.5">
              <div className="h-3 w-3 rounded-sm bg-blue-200" />
              <div className="h-3 w-3 rounded-sm bg-blue-300" />
              <div className="h-3 w-3 rounded-sm bg-blue-400" />
              <div className="h-3 w-3 rounded-sm bg-blue-500" />
              <div className="h-3 w-3 rounded-sm bg-blue-600" />
            </div>
            <span>High</span>
          </div>
        </div>

        {/* Peak hour marker legend */}
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-orange-500" />
          <span>Peak Hour Marker</span>
        </div>
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
          data-testid="daily-pattern-tooltip"
        >
          <div className="space-y-1">
            <div className="font-semibold text-white">
              {DAY_FULL_NAMES[tooltip.day]}
              {tooltip.isBusiest && (
                <span className="ml-2 rounded bg-green-500/20 px-1.5 py-0.5 text-xs text-green-400">
                  Busiest day
                </span>
              )}
              {tooltip.isQuietest && (
                <span className="ml-2 rounded bg-blue-500/20 px-1.5 py-0.5 text-xs text-blue-400">
                  Quietest day
                </span>
              )}
            </div>
            {tooltip.hasData && tooltip.pattern ? (
              <div className="space-y-0.5 text-gray-300">
                <div className="flex items-center justify-between gap-4">
                  <span className="text-gray-400">Average: {tooltip.pattern.avg_detections.toFixed(1)} detections</span>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <span className="text-gray-400">Peak Hour: {formatHour(tooltip.pattern.peak_hour)}</span>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <span className="text-gray-400">Total Samples: {tooltip.pattern.total_samples}</span>
                </div>
                {tooltip.weeksOfData > 0 && (
                  <div className="mt-1 text-xs text-gray-400">
                    Based on {tooltip.weeksOfData} week{tooltip.weeksOfData !== 1 ? 's' : ''} of data
                  </div>
                )}
              </div>
            ) : (
              <div className="text-gray-400">No data available for this day</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
