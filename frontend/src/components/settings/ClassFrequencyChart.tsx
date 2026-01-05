import { Card, Title, Text, BarChart } from '@tremor/react';
import { Package, TrendingUp } from 'lucide-react';
import { useMemo } from 'react';

import type { ClassBaselineEntry } from '../../services/api';

export interface ClassFrequencyChartProps {
  /** Class baseline entries grouped by class and hour */
  entries: ClassBaselineEntry[];
  /** List of unique object classes detected for this camera */
  uniqueClasses: string[];
  /** Total number of samples across all entries */
  totalSamples: number;
  /** Most frequently detected object class, null if no data */
  mostCommonClass: string | null;
  /** Optional className for styling */
  className?: string;
}

interface ClassAggregation {
  name: string;
  totalFrequency: number;
  peakHour: number;
  avgFrequency: number;
}

/**
 * ClassFrequencyChart displays a bar chart showing the frequency
 * distribution of different object classes detected by the camera.
 */
export default function ClassFrequencyChart({
  entries,
  uniqueClasses,
  totalSamples,
  mostCommonClass,
  className = '',
}: ClassFrequencyChartProps) {
  // Aggregate frequencies by class
  const classData = useMemo(() => {
    const aggregation: Record<string, ClassAggregation> = {};

    entries.forEach((entry) => {
      if (!aggregation[entry.object_class]) {
        aggregation[entry.object_class] = {
          name: entry.object_class,
          totalFrequency: 0,
          peakHour: 0,
          avgFrequency: 0,
        };
      }

      const current = aggregation[entry.object_class];
      current.totalFrequency += entry.frequency;

      // Track peak hour
      if (entry.frequency > current.avgFrequency) {
        current.peakHour = entry.hour;
        current.avgFrequency = entry.frequency;
      }
    });

    // Calculate averages and sort by total frequency
    return Object.values(aggregation)
      .map((item) => ({
        ...item,
        avgFrequency: item.totalFrequency / 24, // Average across 24 hours
      }))
      .sort((a, b) => b.totalFrequency - a.totalFrequency);
  }, [entries]);

  // Prepare data for bar chart
  const chartData = classData.map((item) => ({
    name: item.name.charAt(0).toUpperCase() + item.name.slice(1),
    'Total Frequency': Math.round(item.totalFrequency * 10) / 10,
    'Avg per Hour': Math.round(item.avgFrequency * 10) / 10,
  }));

  const formatHour = (hour: number): string => {
    if (hour === 0) return '12am';
    if (hour === 12) return '12pm';
    if (hour < 12) return `${hour}am`;
    return `${hour - 12}pm`;
  };

  return (
    <Card className={`bg-[#1A1A1A] border-gray-800 ${className}`}>
      <div className="flex items-center justify-between mb-4">
        <div>
          <Title className="text-white">Object Class Distribution</Title>
          <Text className="text-gray-400">
            Frequency of different object types detected
          </Text>
        </div>
        <div className="flex items-center gap-2 text-gray-400">
          <Package className="h-4 w-4" />
          <Text>{uniqueClasses.length} classes</Text>
        </div>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-gray-800/50 rounded-lg p-3">
          <Text className="text-gray-400 text-xs uppercase">Most Common</Text>
          <Text className="text-white font-medium text-lg">
            {mostCommonClass ? mostCommonClass.charAt(0).toUpperCase() + mostCommonClass.slice(1) : 'N/A'}
          </Text>
        </div>
        <div className="bg-gray-800/50 rounded-lg p-3">
          <Text className="text-gray-400 text-xs uppercase">Total Samples</Text>
          <Text className="text-white font-medium text-lg">
            {totalSamples.toLocaleString()}
          </Text>
        </div>
        <div className="bg-gray-800/50 rounded-lg p-3">
          <Text className="text-gray-400 text-xs uppercase">Class Count</Text>
          <Text className="text-white font-medium text-lg">
            {uniqueClasses.length}
          </Text>
        </div>
      </div>

      {chartData.length > 0 ? (
        <BarChart
          className="h-64 mt-4"
          data={chartData}
          index="name"
          categories={['Total Frequency', 'Avg per Hour']}
          colors={['emerald', 'gray']}
          valueFormatter={(value) => value.toFixed(1)}
          showLegend
          showGridLines={false}
          showAnimation
        />
      ) : (
        <div className="h-64 flex items-center justify-center text-gray-500">
          <div className="text-center">
            <Package className="h-12 w-12 mx-auto mb-2 opacity-50" />
            <Text>No class data available yet</Text>
          </div>
        </div>
      )}

      {/* Peak hours by class */}
      {classData.length > 0 && (
        <div className="mt-6 pt-4 border-t border-gray-800">
          <Text className="text-gray-400 text-sm mb-3 flex items-center gap-2">
            <TrendingUp className="h-4 w-4" />
            Peak Hours by Class
          </Text>
          <div className="flex flex-wrap gap-2">
            {classData.slice(0, 5).map((item) => (
              <div
                key={item.name}
                className="bg-gray-800/50 rounded-full px-3 py-1 text-sm"
              >
                <span className="text-gray-400">{item.name}:</span>{' '}
                <span className="text-white">{formatHour(item.peakHour)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}
