import { Card, Title, Text } from '@tremor/react';
import { TrendingUp, Clock, Calendar } from 'lucide-react';
import { useMemo } from 'react';

import type { ActivityBaselineEntry } from '../../services/api';

export interface ActivityHeatmapProps {
  /** Activity baseline entries (up to 168 = 24h x 7 days) */
  entries: ActivityBaselineEntry[];
  /** Hour with highest average activity (0-23), null if no data */
  peakHour: number | null;
  /** Day with highest average activity (0=Monday, 6=Sunday), null if no data */
  peakDay: number | null;
  /** Whether baseline has sufficient samples for reliable anomaly detection */
  learningComplete: boolean;
  /** Optional className for styling */
  className?: string;
}

const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const HOUR_LABELS = Array.from({ length: 24 }, (_, i) => {
  if (i === 0) return '12am';
  if (i === 12) return '12pm';
  if (i < 12) return `${i}am`;
  return `${i - 12}pm`;
});

/**
 * ActivityHeatmap displays a 24x7 heatmap showing activity patterns
 * by hour of day and day of week.
 */
export default function ActivityHeatmap({
  entries,
  peakHour,
  peakDay,
  learningComplete,
  className = '',
}: ActivityHeatmapProps) {
  // Build a 2D grid from entries
  const grid = useMemo(() => {
    const result: (number | null)[][] = Array.from({ length: 7 }, () =>
      Array.from({ length: 24 }, () => null as number | null)
    );

    let maxCount = 0;
    entries.forEach((entry) => {
      if (entry.day_of_week >= 0 && entry.day_of_week < 7 &&
          entry.hour >= 0 && entry.hour < 24) {
        result[entry.day_of_week][entry.hour] = entry.avg_count;
        maxCount = Math.max(maxCount, entry.avg_count);
      }
    });

    return { cells: result, maxCount };
  }, [entries]);

  // Calculate color intensity based on value
  const getCellColor = (value: number | null): string => {
    if (value === null) return 'bg-gray-800';
    if (grid.maxCount === 0) return 'bg-gray-700';

    const intensity = value / grid.maxCount;

    if (intensity < 0.2) return 'bg-gray-700';
    if (intensity < 0.4) return 'bg-green-900/50';
    if (intensity < 0.6) return 'bg-green-700/60';
    if (intensity < 0.8) return 'bg-green-600/70';
    return 'bg-green-500';
  };

  const formatPeakTime = () => {
    if (peakHour === null || peakDay === null) return 'No data';
    return `${DAY_NAMES[peakDay]} at ${HOUR_LABELS[peakHour]}`;
  };

  return (
    <Card className={`bg-[#1A1A1A] border-gray-800 ${className}`}>
      <div className="flex items-center justify-between mb-4">
        <div>
          <Title className="text-white">Activity Heatmap</Title>
          <Text className="text-gray-400">
            Hourly activity patterns by day of week
          </Text>
        </div>
        <div className="flex items-center gap-4">
          {learningComplete ? (
            <div className="flex items-center gap-2 text-green-500">
              <TrendingUp className="h-4 w-4" />
              <Text className="text-green-500">Learning Complete</Text>
            </div>
          ) : (
            <div className="flex items-center gap-2 text-yellow-500">
              <Clock className="h-4 w-4 animate-pulse" />
              <Text className="text-yellow-500">Learning in Progress</Text>
            </div>
          )}
        </div>
      </div>

      {/* Peak time indicator */}
      <div className="flex items-center gap-2 mb-4 text-gray-300">
        <Calendar className="h-4 w-4" />
        <Text className="text-gray-300">
          Peak activity: <span className="text-white font-medium">{formatPeakTime()}</span>
        </Text>
      </div>

      {/* Heatmap grid */}
      <div className="overflow-x-auto">
        <div className="min-w-[800px]">
          {/* Hour labels */}
          <div className="flex ml-12 mb-1">
            {[0, 6, 12, 18].map((hour) => (
              <div key={hour} className="flex-1 text-xs text-gray-500">
                {HOUR_LABELS[hour]}
              </div>
            ))}
            <div className="w-10" />
          </div>

          {/* Grid rows */}
          {DAY_NAMES.map((day, dayIndex) => (
            <div key={day} className="flex items-center mb-1">
              <div className="w-12 text-xs text-gray-500 pr-2 text-right">
                {day}
              </div>
              <div className="flex flex-1 gap-0.5">
                {Array.from({ length: 24 }, (_, hourIndex) => {
                  const value = grid.cells[dayIndex][hourIndex];
                  const isPeak = peakDay === dayIndex && peakHour === hourIndex;
                  return (
                    <div
                      key={hourIndex}
                      className={`
                        flex-1 h-6 rounded-sm transition-colors
                        ${getCellColor(value)}
                        ${isPeak ? 'ring-2 ring-white ring-offset-1 ring-offset-[#1A1A1A]' : ''}
                        hover:opacity-80 cursor-pointer
                      `}
                      title={`${day} ${HOUR_LABELS[hourIndex]}: ${value?.toFixed(1) ?? 'No data'} avg`}
                    />
                  );
                })}
              </div>
            </div>
          ))}

          {/* Legend */}
          <div className="flex items-center justify-end mt-4 gap-2">
            <Text className="text-xs text-gray-500">Low</Text>
            <div className="flex gap-0.5">
              <div className="w-4 h-4 rounded-sm bg-gray-700" />
              <div className="w-4 h-4 rounded-sm bg-green-900/50" />
              <div className="w-4 h-4 rounded-sm bg-green-700/60" />
              <div className="w-4 h-4 rounded-sm bg-green-600/70" />
              <div className="w-4 h-4 rounded-sm bg-green-500" />
            </div>
            <Text className="text-xs text-gray-500">High</Text>
          </div>
        </div>
      </div>
    </Card>
  );
}
