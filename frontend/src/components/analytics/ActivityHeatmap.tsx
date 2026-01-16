import { useMemo } from 'react';

import type { ActivityBaselineEntry } from '../../services/api';

interface ActivityHeatmapProps {
  /** Activity baseline entries to display */
  entries: ActivityBaselineEntry[];
  /** Whether the baseline is still learning */
  learningComplete: boolean;
  /** Minimum samples required per cell */
  minSamplesRequired: number;
}

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const HOURS = Array.from({ length: 24 }, (_, i) => i);

/**
 * ActivityHeatmap displays a 24x7 heatmap showing activity patterns.
 *
 * Each cell represents one hour/day combination, colored by activity level.
 */
export default function ActivityHeatmap({
  entries,
  learningComplete,
  minSamplesRequired,
}: ActivityHeatmapProps) {
  // Build a lookup map for quick access
  const entryMap = useMemo(() => {
    const map = new Map<string, ActivityBaselineEntry>();
    entries.forEach((entry) => {
      map.set(`${entry.day_of_week}-${entry.hour}`, entry);
    });
    return map;
  }, [entries]);

  // Calculate max value for color scaling
  const maxAvgCount = useMemo(() => {
    if (entries.length === 0) return 1;
    return Math.max(...entries.map((e) => e.avg_count), 1);
  }, [entries]);

  // Get color for a cell based on avg_count
  const getCellColor = (avgCount: number, isPeak: boolean): string => {
    if (avgCount === 0) return 'bg-gray-800';

    const intensity = Math.min(avgCount / maxAvgCount, 1);

    if (isPeak) {
      // Peak cells use orange/red scale
      if (intensity > 0.8) return 'bg-orange-500';
      if (intensity > 0.6) return 'bg-orange-600';
      if (intensity > 0.4) return 'bg-orange-700';
      return 'bg-orange-800';
    }

    // Normal cells use green scale
    if (intensity > 0.8) return 'bg-[#76B900]';
    if (intensity > 0.6) return 'bg-[#76B900]/80';
    if (intensity > 0.4) return 'bg-[#76B900]/60';
    if (intensity > 0.2) return 'bg-[#76B900]/40';
    return 'bg-[#76B900]/20';
  };

  // Format hour for display
  const formatHour = (hour: number): string => {
    if (hour === 0) return '12a';
    if (hour === 12) return '12p';
    if (hour < 12) return `${hour}a`;
    return `${hour - 12}p`;
  };

  return (
    <div className="rounded-lg border border-gray-800 bg-[#1F1F1F] p-4">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white">Weekly Activity Pattern</h3>
        {!learningComplete && (
          <span className="rounded bg-yellow-500/20 px-2 py-1 text-xs text-yellow-400">
            Learning ({entries.length} / 168 slots)
          </span>
        )}
      </div>

      {entries.length === 0 ? (
        <div className="flex h-64 items-center justify-center text-gray-400">
          No baseline data available yet. Activity patterns will appear as data is collected.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <div className="min-w-[800px]">
            {/* Hour labels */}
            <div className="mb-1 flex">
              <div className="w-12" /> {/* Spacer for day labels */}
              {HOURS.map((hour) => (
                <div
                  key={hour}
                  className="flex-1 text-center text-xs text-gray-500"
                  style={{ minWidth: '28px' }}
                >
                  {hour % 3 === 0 ? formatHour(hour) : ''}
                </div>
              ))}
            </div>

            {/* Grid */}
            {DAYS.map((day, dayIndex) => (
              <div key={day} className="flex items-center">
                <div className="w-12 text-xs text-gray-400">{day}</div>
                {HOURS.map((hour) => {
                  const entry = entryMap.get(`${dayIndex}-${hour}`);
                  const avgCount = entry?.avg_count ?? 0;
                  const sampleCount = entry?.sample_count ?? 0;
                  const isPeak = entry?.is_peak ?? false;
                  const hasData = sampleCount >= minSamplesRequired;

                  return (
                    <div
                      key={hour}
                      className={`m-0.5 h-6 flex-1 rounded-sm transition-colors ${hasData ? getCellColor(avgCount, isPeak) : 'bg-gray-800/50'} ${hasData ? 'cursor-pointer hover:ring-2 hover:ring-white/30' : ''} `}
                      style={{ minWidth: '24px' }}
                      title={
                        hasData
                          ? `${day} ${formatHour(hour)}: ${avgCount.toFixed(1)} avg (${sampleCount} samples)${isPeak ? ' - PEAK' : ''}`
                          : `${day} ${formatHour(hour)}: Insufficient data`
                      }
                      data-testid={`heatmap-cell-${dayIndex}-${hour}`}
                    />
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="mt-4 flex items-center justify-between text-xs text-gray-400">
        <div className="flex items-center gap-2">
          <span>Low Activity</span>
          <div className="flex gap-0.5">
            <div className="h-3 w-3 rounded-sm bg-[#76B900]/20" />
            <div className="h-3 w-3 rounded-sm bg-[#76B900]/40" />
            <div className="h-3 w-3 rounded-sm bg-[#76B900]/60" />
            <div className="h-3 w-3 rounded-sm bg-[#76B900]/80" />
            <div className="h-3 w-3 rounded-sm bg-[#76B900]" />
          </div>
          <span>High Activity</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-3 w-3 rounded-sm bg-orange-500" />
          <span>Peak Hours</span>
        </div>
      </div>
    </div>
  );
}
