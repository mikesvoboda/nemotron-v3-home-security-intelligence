/**
 * ZoneActivityHeatmap - Zone activity heatmap visualization (NEM-3186, NEM-3200)
 *
 * Displays a visual heatmap of activity within a zone, showing:
 * - Time-based activity patterns (hourly, daily)
 * - Detection frequency by grid cell
 * - Activity intensity color gradients
 *
 * Part of Phase 5.1: Enhanced Zone Editor Integration.
 *
 * @module components/zones/ZoneActivityHeatmap
 */

import { Card, Title, Text, Select, SelectItem } from '@tremor/react';
import { clsx } from 'clsx';
import {
  Calendar,
  Clock,
  RefreshCw,
} from 'lucide-react';
import { useCallback, useMemo, useState } from 'react';

// ============================================================================
// Types
// ============================================================================

/**
 * Time range options for the heatmap.
 */
export type HeatmapTimeRange = '1h' | '6h' | '24h' | '7d' | '30d';

/**
 * Heatmap data point representing activity at a specific time slot.
 */
export interface HeatmapDataPoint {
  /** Hour of day (0-23) */
  hour: number;
  /** Day of week (0-6, 0 = Sunday) */
  dayOfWeek: number;
  /** Activity count/intensity */
  value: number;
}

/**
 * Hourly activity data for time-of-day analysis.
 */
export interface HourlyActivity {
  hour: number;
  count: number;
}

/**
 * Props for the ZoneActivityHeatmap component.
 */
export interface ZoneActivityHeatmapProps {
  /** Zone ID to display heatmap for */
  zoneId: string;
  /** Zone name for display */
  zoneName?: string;
  /** Initial time range selection */
  initialTimeRange?: HeatmapTimeRange;
  /** Whether to show compact mode */
  compact?: boolean;
  /** Whether to show as an overlay (transparent background) */
  overlay?: boolean;
  /** Grid cell size for overlay mode */
  gridSize?: number;
  /** Additional CSS classes */
  className?: string;
  /** Callback when a cell is clicked */
  onCellClick?: (hour: number, dayOfWeek: number) => void;
}

// ============================================================================
// Constants
// ============================================================================

const TIME_RANGE_OPTIONS: { value: HeatmapTimeRange; label: string }[] = [
  { value: '1h', label: 'Last Hour' },
  { value: '6h', label: 'Last 6 Hours' },
  { value: '24h', label: 'Last 24 Hours' },
  { value: '7d', label: 'Last 7 Days' },
  { value: '30d', label: 'Last 30 Days' },
];

const DAYS_OF_WEEK = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const DAYS_OF_WEEK_FULL = [
  'Sunday',
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
];

const HOURS_OF_DAY = Array.from({ length: 24 }, (_, i) => i);

/**
 * Color gradient for heatmap cells based on intensity.
 * Uses NVIDIA green theme with varying opacities.
 */
function getHeatmapColor(value: number, maxValue: number): string {
  if (maxValue === 0 || value === 0) return 'bg-gray-800/50';

  const intensity = value / maxValue;

  if (intensity < 0.2) return 'bg-[#76B900]/10';
  if (intensity < 0.4) return 'bg-[#76B900]/30';
  if (intensity < 0.6) return 'bg-[#76B900]/50';
  if (intensity < 0.8) return 'bg-[#76B900]/70';
  return 'bg-[#76B900]/90';
}

/**
 * Text color for heatmap cells based on intensity.
 */
function getHeatmapTextColor(value: number, maxValue: number): string {
  if (maxValue === 0 || value === 0) return 'text-gray-500';

  const intensity = value / maxValue;
  return intensity >= 0.6 ? 'text-gray-900' : 'text-gray-200';
}

// ============================================================================
// Mock Data Generator (until API is available)
// ============================================================================

/**
 * Generate mock heatmap data for demonstration.
 * In production, this would be replaced with actual API data.
 */
function generateMockHeatmapData(): HeatmapDataPoint[] {
  const data: HeatmapDataPoint[] = [];

  for (let day = 0; day < 7; day++) {
    for (let hour = 0; hour < 24; hour++) {
      // Generate realistic patterns:
      // - More activity during daytime (7-22)
      // - More activity on weekdays
      // - Peak hours around 8-9 and 17-19
      let baseValue = 0;

      // Daytime activity
      if (hour >= 7 && hour <= 22) {
        baseValue = Math.floor(Math.random() * 10) + 5;
      } else {
        baseValue = Math.floor(Math.random() * 3);
      }

      // Weekend reduction
      if (day === 0 || day === 6) {
        baseValue = Math.floor(baseValue * 0.6);
      }

      // Peak hours
      if ((hour >= 8 && hour <= 10) || (hour >= 17 && hour <= 19)) {
        baseValue = Math.floor(baseValue * 1.5);
      }

      data.push({
        hour,
        dayOfWeek: day,
        value: baseValue,
      });
    }
  }

  return data;
}

/**
 * Generate mock hourly activity for today.
 */
function generateMockHourlyActivity(): HourlyActivity[] {
  const currentHour = new Date().getHours();
  return HOURS_OF_DAY.map((hour) => ({
    hour,
    count:
      hour <= currentHour
        ? Math.floor(Math.random() * 15) + (hour >= 7 && hour <= 22 ? 5 : 0)
        : 0,
  }));
}

// ============================================================================
// Subcomponents
// ============================================================================

/**
 * Loading skeleton for the heatmap.
 */
function HeatmapSkeleton({ compact }: { compact?: boolean }) {
  return (
    <div className={clsx('space-y-2', compact && 'space-y-1')}>
      {/* Header skeleton */}
      <div className="flex items-center justify-between">
        <div className="h-4 w-24 animate-pulse rounded bg-gray-700" />
        <div className="h-6 w-32 animate-pulse rounded bg-gray-700" />
      </div>

      {/* Grid skeleton */}
      <div className="grid grid-cols-8 gap-1">
        {/* Header row */}
        <div className="h-4" />
        {DAYS_OF_WEEK.map((day) => (
          <div key={day} className="h-4 animate-pulse rounded bg-gray-700" />
        ))}

        {/* Hour rows */}
        {Array.from({ length: compact ? 8 : 12 }).map((_, hourIdx) => (
          <div key={hourIdx} className="contents">
            <div className="h-6 animate-pulse rounded bg-gray-700" />
            {DAYS_OF_WEEK.map((_, dayIdx) => (
              <div
                key={dayIdx}
                className="h-6 animate-pulse rounded bg-gray-700"
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Hour label formatter.
 */
function formatHour(hour: number): string {
  if (hour === 0) return '12am';
  if (hour === 12) return '12pm';
  if (hour < 12) return `${hour}am`;
  return `${hour - 12}pm`;
}

/**
 * Weekly heatmap grid component.
 */
interface WeeklyHeatmapGridProps {
  data: HeatmapDataPoint[];
  compact?: boolean;
  onCellClick?: (hour: number, dayOfWeek: number) => void;
}

function WeeklyHeatmapGrid({ data, compact, onCellClick }: WeeklyHeatmapGridProps) {
  // Calculate max value for color scaling
  const maxValue = useMemo(() => Math.max(...data.map((d) => d.value), 1), [data]);

  // Group data by hour for row access
  const dataByHourAndDay = useMemo(() => {
    const map = new Map<string, number>();
    data.forEach((d) => {
      map.set(`${d.hour}-${d.dayOfWeek}`, d.value);
    });
    return map;
  }, [data]);

  // Show every 2-3 hours in compact mode
  const displayHours = compact
    ? HOURS_OF_DAY.filter((h) => h % 3 === 0)
    : HOURS_OF_DAY.filter((h) => h % 2 === 0);

  return (
    <div className="overflow-x-auto">
      <div
        className="grid gap-0.5"
        style={{ gridTemplateColumns: `40px repeat(7, minmax(30px, 1fr))` }}
      >
        {/* Header row */}
        <div className="text-xs text-gray-500" />
        {DAYS_OF_WEEK.map((day) => (
          <div
            key={day}
            className="text-center text-xs font-medium text-gray-400"
          >
            {compact ? day.charAt(0) : day}
          </div>
        ))}

        {/* Data rows */}
        {displayHours.map((hour) => (
          <div key={hour} className="contents">
            <div className="flex items-center justify-end pr-1 text-xs text-gray-500">
              {formatHour(hour)}
            </div>
            {DAYS_OF_WEEK.map((_, dayIdx) => {
              const value = dataByHourAndDay.get(`${hour}-${dayIdx}`) ?? 0;
              return (
                <button
                  key={dayIdx}
                  type="button"
                  className={clsx(
                    'relative flex items-center justify-center rounded transition-all',
                    compact ? 'h-5' : 'h-6',
                    getHeatmapColor(value, maxValue),
                    'hover:ring-1 hover:ring-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]'
                  )}
                  onClick={() => onCellClick?.(hour, dayIdx)}
                  title={`${DAYS_OF_WEEK_FULL[dayIdx]} ${formatHour(hour)}: ${value} detections`}
                  data-testid={`heatmap-cell-${hour}-${dayIdx}`}
                >
                  {!compact && value > 0 && (
                    <span
                      className={clsx(
                        'text-xs font-medium',
                        getHeatmapTextColor(value, maxValue)
                      )}
                    >
                      {value}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Hourly bar chart for today's activity.
 */
interface HourlyBarChartProps {
  data: HourlyActivity[];
  compact?: boolean;
}

function HourlyBarChart({ data, compact }: HourlyBarChartProps) {
  const maxCount = useMemo(() => Math.max(...data.map((d) => d.count), 1), [data]);
  const currentHour = new Date().getHours();

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <Text className={clsx('text-gray-400', compact && 'text-xs')}>
          Today&apos;s Activity
        </Text>
        <Text className={clsx('text-gray-500', compact ? 'text-xs' : 'text-sm')}>
          <Clock className="mr-1 inline h-3 w-3" />
          {formatHour(currentHour)}
        </Text>
      </div>

      <div className="flex items-end gap-0.5" style={{ height: compact ? '40px' : '60px' }}>
        {data.map((item) => {
          const height = maxCount > 0 ? (item.count / maxCount) * 100 : 0;
          const isCurrentHour = item.hour === currentHour;

          return (
            <div
              key={item.hour}
              className="group relative flex-1"
              title={`${formatHour(item.hour)}: ${item.count} detections`}
            >
              <div
                className={clsx(
                  'w-full rounded-t transition-all',
                  isCurrentHour ? 'bg-[#76B900]' : 'bg-[#76B900]/60',
                  'hover:bg-[#76B900]'
                )}
                style={{ height: `${Math.max(height, 2)}%` }}
                data-testid={`hourly-bar-${item.hour}`}
              />
              {/* Tooltip on hover */}
              <div className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-1 -translate-x-1/2 whitespace-nowrap rounded bg-gray-900 px-1.5 py-0.5 text-xs text-white opacity-0 shadow transition-opacity group-hover:opacity-100">
                {item.count}
              </div>
            </div>
          );
        })}
      </div>

      {/* Hour labels */}
      <div className="flex gap-0.5 text-center">
        {HOURS_OF_DAY.filter((h) => h % 6 === 0).map((hour) => (
          <div
            key={hour}
            className="text-xs text-gray-500"
            style={{ width: `${(6 / 24) * 100}%` }}
          >
            {formatHour(hour)}
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Color legend for the heatmap.
 */
function HeatmapLegend({ compact }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <Text className={clsx('text-gray-500', compact ? 'text-xs' : 'text-sm')}>
        Low
      </Text>
      <div className="flex gap-0.5">
        {['bg-[#76B900]/10', 'bg-[#76B900]/30', 'bg-[#76B900]/50', 'bg-[#76B900]/70', 'bg-[#76B900]/90'].map(
          (color, idx) => (
            <div
              key={idx}
              className={clsx('rounded', color, compact ? 'h-3 w-3' : 'h-4 w-4')}
            />
          )
        )}
      </div>
      <Text className={clsx('text-gray-500', compact ? 'text-xs' : 'text-sm')}>
        High
      </Text>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * ZoneActivityHeatmap component.
 *
 * Displays activity patterns within a zone using a weekly heatmap
 * and hourly bar chart visualization.
 *
 * @param props - Component props
 * @returns Rendered component
 */
export default function ZoneActivityHeatmap({
  zoneId,
  zoneName,
  initialTimeRange = '7d',
  compact = false,
  overlay = false,
  className,
  onCellClick,
}: ZoneActivityHeatmapProps) {
  const [timeRange, setTimeRange] = useState<HeatmapTimeRange>(initialTimeRange);
  const [isLoading, setIsLoading] = useState(false);

  // Generate mock data (in production, this would use an API hook)
  const weeklyData = useMemo(() => generateMockHeatmapData(), []);
  const hourlyData = useMemo(() => generateMockHourlyActivity(), []);

  // Suppress unused variable warning - zoneId will be used with real API
  void zoneId;
  void timeRange;

  const handleRefresh = useCallback(() => {
    setIsLoading(true);
    // Simulate API refresh
    setTimeout(() => setIsLoading(false), 500);
  }, []);

  // Overlay mode for canvas integration
  if (overlay) {
    return (
      <div
        className={clsx(
          'pointer-events-none absolute inset-0 opacity-50',
          className
        )}
        data-testid="zone-activity-heatmap-overlay"
      >
        {/* Overlay grid would go here - simplified for now */}
        <div className="grid h-full w-full grid-cols-8 grid-rows-6 gap-0.5">
          {Array.from({ length: 48 }).map((_, idx) => {
            const value = Math.random();
            return (
              <div
                key={idx}
                className={clsx(
                  'rounded-sm transition-opacity',
                  value < 0.2
                    ? 'bg-transparent'
                    : value < 0.5
                      ? 'bg-[#76B900]/20'
                      : value < 0.8
                        ? 'bg-[#76B900]/40'
                        : 'bg-[#76B900]/60'
                )}
              />
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="zone-activity-heatmap"
    >
      {/* Header */}
      <div className={clsx('flex items-center justify-between', compact ? 'mb-3' : 'mb-4')}>
        <div className="flex items-center gap-2">
          <Calendar className={clsx('text-[#76B900]', compact ? 'h-4 w-4' : 'h-5 w-5')} />
          <Title className={clsx('text-white', compact && 'text-sm')}>
            {zoneName ? `${zoneName} Activity` : 'Activity Heatmap'}
          </Title>
        </div>

        <div className="flex items-center gap-2">
          <Select
            value={timeRange}
            onValueChange={(v) => setTimeRange(v as HeatmapTimeRange)}
            className="w-32"
            data-testid="time-range-select"
          >
            {TIME_RANGE_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </Select>

          <button
            type="button"
            onClick={handleRefresh}
            disabled={isLoading}
            className="rounded p-1.5 text-gray-400 transition-colors hover:bg-gray-700 hover:text-white disabled:opacity-50"
            title="Refresh data"
            data-testid="refresh-btn"
          >
            <RefreshCw className={clsx('h-4 w-4', isLoading && 'animate-spin')} />
          </button>
        </div>
      </div>

      {isLoading ? (
        <HeatmapSkeleton compact={compact} />
      ) : (
        <div className={clsx('space-y-4', compact && 'space-y-3')}>
          {/* Weekly heatmap */}
          <div>
            <Text className={clsx('mb-2 text-gray-400', compact && 'text-xs')}>
              Weekly Pattern
            </Text>
            <WeeklyHeatmapGrid
              data={weeklyData}
              compact={compact}
              onCellClick={onCellClick}
            />
          </div>

          {/* Hourly bar chart */}
          {!compact && <HourlyBarChart data={hourlyData} compact={compact} />}

          {/* Legend */}
          <div className="flex justify-end">
            <HeatmapLegend compact={compact} />
          </div>
        </div>
      )}
    </Card>
  );
}

// ============================================================================
// Exports
// ============================================================================

// Export subcomponents for testing purposes
// Note: formatHour, getHeatmapColor, getHeatmapTextColor, generateMockHeatmapData,
// and generateMockHourlyActivity are not exported to avoid react-refresh warnings.
// They are tested through component tests.
export { HeatmapSkeleton, WeeklyHeatmapGrid, HourlyBarChart, HeatmapLegend };
