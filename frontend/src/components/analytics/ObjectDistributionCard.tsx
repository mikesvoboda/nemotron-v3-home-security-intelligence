/**
 * ObjectDistributionCard - Display detection distribution by object type
 *
 * Shows a donut chart of detections grouped by object type (person, car, etc.)
 * with percentage breakdown to help understand what is being detected.
 */

import { Card, Title, Text, DonutChart } from '@tremor/react';
import { AlertCircle, Loader2, PieChart } from 'lucide-react';
import { useMemo } from 'react';

import { useObjectDistributionQuery } from '../../hooks/useObjectDistributionQuery';

// ============================================================================
// Types
// ============================================================================

interface ObjectDistributionCardProps {
  /** Date range for the object distribution query */
  dateRange: {
    startDate: string;
    endDate: string;
  };
}

// ============================================================================
// Constants
// ============================================================================

/**
 * Color palette for object types.
 * Uses a diverse set of colors for visual distinction.
 */
const OBJECT_COLORS: string[] = [
  'emerald',
  'blue',
  'amber',
  'violet',
  'rose',
  'cyan',
  'orange',
  'indigo',
  'lime',
  'pink',
];

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Format a date string for display (e.g., "Jan 10").
 *
 * @param dateStr - ISO date string (YYYY-MM-DD)
 * @returns Formatted date string
 */
function formatDate(dateStr: string): string {
  const date = new Date(dateStr + 'T00:00:00');
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

/**
 * Format a number with thousands separator.
 *
 * @param num - Number to format
 * @returns Formatted number string
 */
function formatNumber(num: number): string {
  return num.toLocaleString();
}

/**
 * Capitalize the first letter of each word.
 *
 * @param str - String to capitalize
 * @returns Capitalized string
 */
function capitalizeWords(str: string): string {
  return str
    .split(/[_\s]+/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
}

// ============================================================================
// Component
// ============================================================================

/**
 * ObjectDistributionCard displays detection counts by object type.
 *
 * Fetches object distribution data for the specified date range and displays
 * a donut chart showing the breakdown of detected object types.
 *
 * @param props - Component props
 * @returns React element
 */
export default function ObjectDistributionCard({ dateRange }: ObjectDistributionCardProps) {
  const { objectTypes, totalDetections, isLoading, error } = useObjectDistributionQuery({
    start_date: dateRange.startDate,
    end_date: dateRange.endDate,
  });

  // Transform data points for Tremor DonutChart
  const chartData = useMemo(() => {
    return objectTypes.map((obj) => ({
      name: capitalizeWords(obj.object_type),
      value: obj.count,
      percentage: obj.percentage,
    }));
  }, [objectTypes]);

  // Get colors for each object type
  const chartColors = useMemo(() => {
    return chartData.map((_, index) => OBJECT_COLORS[index % OBJECT_COLORS.length]);
  }, [chartData]);

  // Format date range for display
  const dateRangeLabel = `${formatDate(dateRange.startDate)} - ${formatDate(dateRange.endDate)}`;

  // Loading state
  if (isLoading) {
    return (
      <Card data-testid="object-distribution-loading">
        <Title>Object Distribution</Title>
        <div className="flex h-48 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      </Card>
    );
  }

  // Error state
  if (error) {
    return (
      <Card data-testid="object-distribution-error">
        <Title>Object Distribution</Title>
        <div className="flex h-48 flex-col items-center justify-center text-red-400">
          <AlertCircle className="mb-2 h-8 w-8" />
          <Text>Failed to load object distribution</Text>
        </div>
      </Card>
    );
  }

  // Empty state
  if (objectTypes.length === 0) {
    return (
      <Card data-testid="object-distribution-empty">
        <Title>Object Distribution</Title>
        <div className="flex h-48 flex-col items-center justify-center text-gray-400">
          <PieChart className="mb-2 h-8 w-8" />
          <Text>No object data available</Text>
        </div>
      </Card>
    );
  }

  return (
    <Card data-testid="object-distribution-card">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <PieChart className="h-5 w-5 text-[#76B900]" />
          <Title>Object Distribution</Title>
        </div>
        <Text className="text-gray-400">{dateRangeLabel}</Text>
      </div>

      <div className="flex items-center gap-6">
        {/* Donut chart */}
        <div className="flex-shrink-0">
          <DonutChart
            className="h-40 w-40"
            data={chartData}
            category="value"
            index="name"
            colors={chartColors}
            showLabel={true}
            label={formatNumber(totalDetections)}
            showAnimation={true}
            data-testid="object-distribution-chart"
          />
        </div>

        {/* Legend with percentages */}
        <div className="flex-1 space-y-2">
          {chartData.slice(0, 5).map((item, index) => (
            <div
              key={item.name}
              className="flex items-center justify-between text-sm"
              data-testid={`object-item-${item.name.toLowerCase().replace(/\s+/g, '-')}`}
            >
              <div className="flex items-center gap-2">
                <div
                  className={`h-3 w-3 rounded-full bg-${chartColors[index]}-500`}
                  style={{
                    backgroundColor: getColorValue(chartColors[index]),
                  }}
                />
                <span className="text-gray-300">{item.name}</span>
              </div>
              <span className="text-gray-400">{item.percentage.toFixed(1)}%</span>
            </div>
          ))}
          {chartData.length > 5 && (
            <div className="text-xs text-gray-500">
              +{chartData.length - 5} more types
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}

/**
 * Get the actual color value for a Tremor color name.
 *
 * @param colorName - Tremor color name (e.g., 'emerald')
 * @returns Hex color value
 */
function getColorValue(colorName: string): string {
  const colorMap: Record<string, string> = {
    emerald: '#10B981',
    blue: '#3B82F6',
    amber: '#F59E0B',
    violet: '#8B5CF6',
    rose: '#F43F5E',
    cyan: '#06B6D4',
    orange: '#F97316',
    indigo: '#6366F1',
    lime: '#84CC16',
    pink: '#EC4899',
  };
  return colorMap[colorName] || '#6B7280';
}
