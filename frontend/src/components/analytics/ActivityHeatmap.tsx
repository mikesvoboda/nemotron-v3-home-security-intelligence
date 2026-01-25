import { useMemo, useState, useCallback } from 'react';

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
/**
 * Tooltip state for heatmap cell hover.
 */
interface TooltipState {
  visible: boolean;
  x: number;
  y: number;
  day: string;
  hour: string;
  avgCount: number;
  sampleCount: number;
  isPeak: boolean;
  hasData: boolean;
}

export default function ActivityHeatmap({
  entries,
  learningComplete,
  minSamplesRequired,
}: ActivityHeatmapProps) {
  // Tooltip state
  const [tooltip, setTooltip] = useState<TooltipState>({
    visible: false,
    x: 0,
    y: 0,
    day: '',
    hour: '',
    avgCount: 0,
    sampleCount: 0,
    isPeak: false,
    hasData: false,
  });

  // Build a lookup map for quick access
  const entryMap = useMemo(() => {
    const map = new Map<string, ActivityBaselineEntry>();
    entries.forEach((entry) => {
      map.set(`${entry.day_of_week}-${entry.hour}`, entry);
    });
    return map;
  }, [entries]);

  // Handle cell hover
  const handleCellHover = useCallback(
    (
      event: React.MouseEvent<HTMLDivElement>,
      day: string,
      hour: string,
      avgCount: number,
      sampleCount: number,
      isPeak: boolean,
      hasData: boolean
    ) => {
      const rect = event.currentTarget.getBoundingClientRect();
      setTooltip({
        visible: true,
        x: rect.left + rect.width / 2,
        y: rect.top - 8,
        day,
        hour,
        avgCount,
        sampleCount,
        isPeak,
        hasData,
      });
    },
    []
  );

  const handleCellLeave = useCallback(() => {
    setTooltip((prev) => ({ ...prev, visible: false }));
  }, []);

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
                      role="gridcell"
                      tabIndex={hasData ? 0 : -1}
                      className={`m-0.5 h-6 flex-1 rounded-sm transition-colors ${hasData ? getCellColor(avgCount, isPeak) : 'bg-gray-800/50'} ${hasData ? 'cursor-pointer hover:ring-2 hover:ring-white/30 focus:ring-2 focus:ring-[#76B900] focus:outline-none' : ''} `}
                      style={{ minWidth: '24px' }}
                      onMouseEnter={(e) =>
                        handleCellHover(
                          e,
                          day,
                          formatHour(hour),
                          avgCount,
                          sampleCount,
                          isPeak,
                          hasData
                        )
                      }
                      onMouseLeave={handleCellLeave}
                      onFocus={(e) =>
                        hasData &&
                        handleCellHover(
                          e as unknown as React.MouseEvent<HTMLDivElement>,
                          day,
                          formatHour(hour),
                          avgCount,
                          sampleCount,
                          isPeak,
                          hasData
                        )
                      }
                      onBlur={handleCellLeave}
                      data-testid={`heatmap-cell-${dayIndex}-${hour}`}
                      aria-label={
                        hasData
                          ? `${day} ${formatHour(hour)}: ${avgCount.toFixed(1)} average activity, ${sampleCount} samples${isPeak ? ', peak hour' : ''}`
                          : `${day} ${formatHour(hour)}: Insufficient data`
                      }
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

      {/* Tooltip */}
      {tooltip.visible && (
        <div
          role="tooltip"
          className="pointer-events-none fixed z-50 rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm shadow-xl"
          style={{
            left: tooltip.x,
            top: tooltip.y,
            transform: 'translate(-50%, -100%)',
          }}
          data-testid="heatmap-tooltip"
        >
          <div className="space-y-1">
            <div className="font-semibold text-white">
              {tooltip.day} {tooltip.hour}
              {tooltip.isPeak && (
                <span className="ml-2 rounded bg-orange-500/20 px-1.5 py-0.5 text-xs text-orange-400">
                  Peak
                </span>
              )}
            </div>
            {tooltip.hasData ? (
              <div className="space-y-0.5 text-gray-300">
                <div className="flex items-center justify-between gap-4">
                  <span className="text-gray-400">Average:</span>
                  <span className="font-medium text-white">{tooltip.avgCount.toFixed(1)}</span>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <span className="text-gray-400">Samples:</span>
                  <span className="font-medium text-white">{tooltip.sampleCount}</span>
                </div>
              </div>
            ) : (
              <div className="text-gray-400">Insufficient data</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
