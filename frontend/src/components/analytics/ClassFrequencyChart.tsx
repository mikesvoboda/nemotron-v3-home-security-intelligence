import { useMemo, useState, useCallback } from 'react';

import type { ClassBaselineEntry } from '../../services/api';

interface ClassFrequencyChartProps {
  /** Class baseline entries to display */
  entries: ClassBaselineEntry[];
  /** Unique classes detected */
  uniqueClasses: string[];
  /** Most common class */
  mostCommonClass: string | null;
}

// Color palette for different object classes
const CLASS_COLORS: Record<string, string> = {
  person: '#76B900',
  vehicle: '#F59E0B',
  car: '#F59E0B',
  truck: '#D97706',
  motorcycle: '#B45309',
  bicycle: '#92400E',
  animal: '#8B5CF6',
  dog: '#7C3AED',
  cat: '#6D28D9',
  bird: '#5B21B6',
};

const DEFAULT_COLOR = '#6B7280';

/**
 * Tooltip state for bar hover.
 */
interface TooltipState {
  visible: boolean;
  x: number;
  y: number;
  objectClass: string;
  frequency: number;
  sampleCount: number;
  percentage: number;
  color: string;
}

/**
 * ClassFrequencyChart displays a bar chart of object class frequencies.
 *
 * Shows the distribution of detected object types for a camera.
 */
export default function ClassFrequencyChart({
  entries,
  uniqueClasses,
  mostCommonClass,
}: ClassFrequencyChartProps) {
  // Tooltip state
  const [tooltip, setTooltip] = useState<TooltipState>({
    visible: false,
    x: 0,
    y: 0,
    objectClass: '',
    frequency: 0,
    sampleCount: 0,
    percentage: 0,
    color: '',
  });
  // Aggregate total frequency per class
  const classStats = useMemo(() => {
    const stats: Record<string, { totalFrequency: number; sampleCount: number }> = {};

    entries.forEach((entry) => {
      if (!stats[entry.object_class]) {
        stats[entry.object_class] = { totalFrequency: 0, sampleCount: 0 };
      }
      stats[entry.object_class].totalFrequency += entry.frequency;
      stats[entry.object_class].sampleCount += entry.sample_count;
    });

    // Convert to sorted array
    return Object.entries(stats)
      .map(([objectClass, data]) => ({
        objectClass,
        ...data,
      }))
      .sort((a, b) => b.totalFrequency - a.totalFrequency);
  }, [entries]);

  // Calculate max frequency for scaling
  const maxFrequency = useMemo(() => {
    if (classStats.length === 0) return 1;
    return Math.max(...classStats.map((s) => s.totalFrequency), 1);
  }, [classStats]);

  // Get color for a class
  const getClassColor = (objectClass: string): string => {
    return CLASS_COLORS[objectClass.toLowerCase()] ?? DEFAULT_COLOR;
  };

  // Format class name for display
  const formatClassName = (name: string): string => {
    return name.charAt(0).toUpperCase() + name.slice(1);
  };

  // Handle bar hover
  const handleBarHover = useCallback(
    (
      event: React.MouseEvent<HTMLDivElement>,
      objectClass: string,
      frequency: number,
      sampleCount: number,
      percentage: number,
      color: string
    ) => {
      const rect = event.currentTarget.getBoundingClientRect();
      setTooltip({
        visible: true,
        x: rect.left + rect.width / 2,
        y: rect.top - 8,
        objectClass,
        frequency,
        sampleCount,
        percentage,
        color,
      });
    },
    []
  );

  const handleBarLeave = useCallback(() => {
    setTooltip((prev) => ({ ...prev, visible: false }));
  }, []);

  return (
    <div className="rounded-lg border border-gray-800 bg-[#1F1F1F] p-4">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white">Object Class Distribution</h3>
        {mostCommonClass && (
          <span className="text-sm text-gray-400">
            Most common:{' '}
            <span className="font-medium text-white">{formatClassName(mostCommonClass)}</span>
          </span>
        )}
      </div>

      {uniqueClasses.length === 0 ? (
        <div className="flex h-48 items-center justify-center text-gray-400">
          No object class data available yet. Detection patterns will appear as objects are
          detected.
        </div>
      ) : (
        <div className="space-y-3">
          {classStats.map((stat) => {
            const percentage = (stat.totalFrequency / maxFrequency) * 100;
            const color = getClassColor(stat.objectClass);

            return (
              <div
                key={stat.objectClass}
                className="group"
                data-testid={`class-bar-${stat.objectClass}`}
              >
                <div className="mb-1 flex items-center justify-between text-sm">
                  <span className="text-gray-300">{formatClassName(stat.objectClass)}</span>
                  <span className="text-gray-500">
                    {stat.totalFrequency.toFixed(1)} freq ({stat.sampleCount} samples)
                  </span>
                </div>
                {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
                <div
                  className="h-6 cursor-pointer overflow-hidden rounded bg-gray-800"
                  onMouseEnter={(e) =>
                    handleBarHover(
                      e,
                      stat.objectClass,
                      stat.totalFrequency,
                      stat.sampleCount,
                      percentage,
                      color
                    )
                  }
                  onMouseLeave={handleBarLeave}
                >
                  <div
                    className="h-full rounded transition-all duration-300 group-hover:brightness-110"
                    style={{
                      width: `${percentage}%`,
                      backgroundColor: color,
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Legend */}
      {uniqueClasses.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-3 border-t border-gray-800 pt-4 text-xs text-gray-400">
          {uniqueClasses.map((className) => (
            <div key={className} className="flex items-center gap-1.5">
              <div
                className="h-2.5 w-2.5 rounded-sm"
                style={{ backgroundColor: getClassColor(className) }}
              />
              <span>{formatClassName(className)}</span>
            </div>
          ))}
        </div>
      )}

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
          data-testid="class-chart-tooltip"
        >
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <span
                className="h-3 w-3 rounded-sm"
                style={{ backgroundColor: tooltip.color }}
              />
              <span className="font-semibold text-white">
                {formatClassName(tooltip.objectClass)}
              </span>
            </div>
            <div className="space-y-0.5 text-gray-300">
              <div className="flex items-center justify-between gap-4">
                <span className="text-gray-400">Frequency:</span>
                <span className="font-medium text-white">{tooltip.frequency.toFixed(1)}</span>
              </div>
              <div className="flex items-center justify-between gap-4">
                <span className="text-gray-400">Samples:</span>
                <span className="font-medium text-white">{tooltip.sampleCount}</span>
              </div>
              <div className="flex items-center justify-between gap-4">
                <span className="text-gray-400">Share:</span>
                <span className="font-medium text-white">{tooltip.percentage.toFixed(1)}%</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
