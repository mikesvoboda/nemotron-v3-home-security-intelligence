/**
 * InsightsCharts - Visualization charts for AI performance insights
 *
 * Displays:
 * - Detection class distribution (DonutChart showing person/vehicle/animal/package counts)
 * - Risk score distribution (clickable bar chart showing events by risk level: low/medium/high/critical)
 *
 * Data sources:
 * - Detection counts from useDetectionStats hook (fetches from /api/detections/stats)
 * - Risk distribution from /api/events/stats endpoint
 *
 * Interactivity:
 * - Clicking on a risk level bar navigates to the Timeline page with that risk level filter applied
 *
 * Mobile Optimization:
 * - Uses ResponsiveChart wrapper for auto-sizing and fullscreen expansion
 * - Uses ChartLegend for collapsible, touch-friendly legend items
 */

import { Card, Text, DonutChart } from '@tremor/react';
import { clsx } from 'clsx';
import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';

import { fetchEventStats } from '../../services/api';
import ResponsiveChart from '../common/ResponsiveChart';

import type { EventStatsResponse } from '../../types/generated';
import type { ChartLegendItem } from '../common/ChartLegend';

/**
 * Detection class counts for the donut chart
 */
export interface DetectionClassData {
  name: string;
  count: number;
}

/**
 * Risk level distribution for the bar chart
 */
export interface RiskDistributionData {
  /** Display name (e.g., "Low", "Medium") */
  name: string;
  /** Event count for this risk level */
  count: number;
  /** Tremor color name for styling */
  color: string;
  /** URL-safe risk level key (e.g., "low", "medium") for navigation */
  riskLevelKey: string;
}

export interface InsightsChartsProps {
  /** Detection class distribution data - optional, will show placeholder if not provided */
  detectionsByClass?: Record<string, number>;
  /** Total detections count (used when detectionsByClass is not available) */
  totalDetections?: number;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Color mapping for risk levels
 */
const RISK_COLORS: Record<string, string> = {
  low: 'green',
  medium: 'yellow',
  high: 'orange',
  critical: 'red',
};

/**
 * Hex color mapping for risk levels
 */
const RISK_HEX_COLORS: Record<string, string> = {
  low: '#22c55e',
  medium: '#eab308',
  high: '#f97316',
  critical: '#ef4444',
};

/**
 * Display labels for risk levels
 */
const RISK_LABELS: Record<string, string> = {
  low: 'Low',
  medium: 'Medium',
  high: 'High',
  critical: 'Critical',
};

/**
 * Colors for detection class donut chart
 */
const DETECTION_COLORS = ['emerald', 'blue', 'amber', 'violet', 'rose', 'cyan'];

/**
 * Hex colors for detection classes (for legend)
 */
const DETECTION_HEX_COLORS: Record<string, string> = {
  emerald: '#10b981',
  blue: '#3b82f6',
  amber: '#f59e0b',
  violet: '#8b5cf6',
  rose: '#f43f5e',
  cyan: '#06b6d4',
};

/**
 * Transform detection class record to chart data
 */
function transformDetectionData(
  detectionsByClass: Record<string, number> | undefined
): DetectionClassData[] {
  if (!detectionsByClass || Object.keys(detectionsByClass).length === 0) {
    return [];
  }

  return Object.entries(detectionsByClass)
    .map(([name, count]) => ({
      name: name.charAt(0).toUpperCase() + name.slice(1),
      count,
    }))
    .sort((a, b) => b.count - a.count);
}

/**
 * Transform detection data to legend items
 */
function transformToLegendItems(detectionData: DetectionClassData[]): ChartLegendItem[] {
  return detectionData.map((item, index) => ({
    name: item.name,
    value: item.count,
    color: DETECTION_HEX_COLORS[DETECTION_COLORS[index % DETECTION_COLORS.length]] || '#6b7280',
  }));
}

/**
 * Transform event stats to risk distribution chart data
 */
function transformRiskData(eventStats: EventStatsResponse | null): RiskDistributionData[] {
  if (!eventStats?.events_by_risk_level) {
    return [];
  }

  const { events_by_risk_level } = eventStats;
  const riskOrder = ['low', 'medium', 'high', 'critical'];

  return riskOrder.map((level) => ({
    name: RISK_LABELS[level] || level,
    count: events_by_risk_level[level as keyof typeof events_by_risk_level] || 0,
    color: RISK_COLORS[level] || 'gray',
    riskLevelKey: level,
  }));
}

/**
 * Transform risk data to legend items
 */
function transformRiskToLegendItems(riskData: RiskDistributionData[]): ChartLegendItem[] {
  return riskData.map((item) => ({
    name: item.name,
    value: item.count,
    color: RISK_HEX_COLORS[item.riskLevelKey] || '#6b7280',
  }));
}

/**
 * Format large numbers for display
 */
function formatCount(count: number): string {
  if (count >= 1000000) return `${(count / 1000000).toFixed(1)}M`;
  if (count >= 1000) return `${(count / 1000).toFixed(1)}K`;
  return count.toString();
}

/**
 * InsightsCharts - Charts for AI detection and risk analysis insights
 */
export default function InsightsCharts({
  detectionsByClass,
  totalDetections,
  className,
}: InsightsChartsProps) {
  const navigate = useNavigate();
  const [eventStats, setEventStats] = useState<EventStatsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch event stats for risk distribution
  useEffect(() => {
    let mounted = true;

    const loadEventStats = async () => {
      try {
        setIsLoading(true);
        const stats = await fetchEventStats();
        if (mounted) {
          setEventStats(stats);
          setError(null);
        }
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : 'Failed to load event statistics');
          console.error('Failed to fetch event stats:', err);
        }
      } finally {
        if (mounted) {
          setIsLoading(false);
        }
      }
    };

    void loadEventStats();

    return () => {
      mounted = false;
    };
  }, []);

  // Retry loading event stats
  const handleRetryEventStats = useCallback(() => {
    const loadEventStats = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const stats = await fetchEventStats();
        setEventStats(stats);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load event statistics');
        console.error('Failed to fetch event stats:', err);
      } finally {
        setIsLoading(false);
      }
    };
    void loadEventStats();
  }, []);

  // Handle risk level click (navigate to timeline with filter)
  const handleRiskLevelClick = useCallback(
    (item: ChartLegendItem) => {
      const riskLevel = item.name.toLowerCase();
      void navigate(`/timeline?risk_level=${riskLevel}`);
    },
    [navigate]
  );

  // Transform data for charts
  const detectionData = transformDetectionData(detectionsByClass);
  const riskData = transformRiskData(eventStats);

  // Create legend items
  const detectionLegendItems = transformToLegendItems(detectionData);
  const riskLegendItems = transformRiskToLegendItems(riskData);

  // Calculate totals
  const totalDetectionCount =
    detectionData.reduce((sum, item) => sum + item.count, 0) || totalDetections || 0;
  const totalEventCount = riskData.reduce((sum, item) => sum + item.count, 0);

  return (
    <div className={clsx('space-y-4', className)} data-testid="insights-charts">
      {/* Detection Class Distribution */}
      <Card
        className="border-gray-800 bg-[#1A1A1A] shadow-lg"
        data-testid="detection-distribution-card"
      >
        <ResponsiveChart
          title="Detection Class Distribution"
          legendItems={detectionLegendItems}
          legendPosition={detectionData.length > 0 ? 'bottom' : 'none'}
          legendMaxItems={5}
          enableFullscreen
          isEmpty={detectionData.length === 0}
          emptyMessage={
            totalDetectionCount > 0
              ? 'Detection breakdown not available'
              : 'No detections recorded yet'
          }
          dimensionOptions={{
            minHeight: 160,
            maxHeight: 200,
            aspectRatio: 1, // Square for donut chart
          }}
        >
          {() => (
            <div className="flex flex-col items-center gap-4 md:flex-row md:items-center">
              <DonutChart
                className="h-40 w-40"
                data={detectionData}
                category="count"
                index="name"
                colors={DETECTION_COLORS}
                showAnimation
                showTooltip
                valueFormatter={(value) => formatCount(value)}
                data-testid="detection-donut-chart"
              />
              <div className="flex-1 text-center md:text-left">
                <Text className="text-sm text-gray-400">
                  Total Detections:{' '}
                  <span className="font-semibold text-white">{formatCount(totalDetectionCount)}</span>
                </Text>
              </div>
            </div>
          )}
        </ResponsiveChart>
      </Card>

      {/* Risk Score Distribution */}
      <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="risk-distribution-card">
        <ResponsiveChart
          title="Risk Score Distribution"
          legendItems={riskLegendItems}
          legendPosition={riskData.length > 0 && totalEventCount > 0 ? 'bottom' : 'none'}
          legendMaxItems={4}
          onLegendItemClick={handleRiskLevelClick}
          enableFullscreen
          isLoading={isLoading}
          error={error}
          onRetry={handleRetryEventStats}
          isEmpty={riskData.length === 0 || totalEventCount === 0}
          emptyMessage="No events recorded yet. Events will appear here once the AI pipeline processes detections."
          dimensionOptions={{
            minHeight: 180,
            maxHeight: 250,
            aspectRatio: 16 / 9,
          }}
        >
          {() => (
            <div className="space-y-4">
              {/* Custom clickable bar chart */}
              <div
                className="flex h-48 items-end justify-around gap-4 px-4"
                data-testid="risk-bar-chart"
                role="group"
                aria-label="Risk score distribution bar chart"
              >
                {riskData.map((item) => {
                  // Calculate bar height as percentage of max count
                  const maxCount = Math.max(...riskData.map((d) => d.count));
                  const heightPercent = maxCount > 0 ? (item.count / maxCount) * 100 : 0;
                  // Minimum bar height for visibility (10% if count > 0)
                  const minHeight = item.count > 0 ? Math.max(heightPercent, 10) : 0;

                  return (
                    <button
                      key={item.riskLevelKey}
                      onClick={() => {
                        void navigate(`/timeline?risk_level=${item.riskLevelKey}`);
                      }}
                      className={clsx(
                        'group relative flex w-full max-w-[80px] flex-col items-center',
                        'cursor-pointer transition-transform hover:scale-105',
                        'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#1A1A1A]',
                        'rounded-t-md min-h-11' // Touch target
                      )}
                      style={{ height: '100%' }}
                      title={`Click to view ${item.count} ${item.name.toLowerCase()} risk events`}
                      aria-label={`${item.name}: ${item.count} events. Click to view in timeline.`}
                      data-testid={`risk-bar-${item.riskLevelKey}`}
                    >
                      {/* Tooltip on hover */}
                      <div
                        className={clsx(
                          'absolute -top-10 z-10 whitespace-nowrap rounded-md px-2 py-1 text-xs font-medium text-white shadow-lg',
                          'opacity-0 transition-opacity group-hover:opacity-100',
                          'border border-gray-700 bg-gray-900'
                        )}
                      >
                        Click to view {item.count} events
                      </div>
                      {/* Bar container */}
                      <div className="relative flex h-full w-full flex-col justify-end">
                        {/* The bar */}
                        <div
                          className={clsx(
                            'w-full rounded-t-md transition-all duration-200',
                            'group-hover:opacity-80 group-hover:ring-2 group-hover:ring-white/30',
                            item.color === 'green' && 'bg-green-500',
                            item.color === 'yellow' && 'bg-yellow-500',
                            item.color === 'orange' && 'bg-orange-500',
                            item.color === 'red' && 'bg-red-500'
                          )}
                          style={{ height: `${minHeight}%`, minHeight: item.count > 0 ? '8px' : '0' }}
                        />
                      </div>
                      {/* Label below bar */}
                      <div className="mt-2 text-center">
                        <Text className="text-xs text-gray-400 group-hover:text-white">
                          {item.name}
                        </Text>
                      </div>
                    </button>
                  );
                })}
              </div>
              {/* Summary counts below the chart - also clickable */}
              <div className="grid grid-cols-2 gap-4 border-t border-gray-800 pt-4 md:grid-cols-4">
                {riskData.map((item) => (
                  <button
                    key={item.name}
                    onClick={() => {
                      void navigate(`/timeline?risk_level=${item.riskLevelKey}`);
                    }}
                    className={clsx(
                      'cursor-pointer rounded-md p-2 text-center transition-colors min-h-11',
                      'hover:bg-gray-800/50 focus:outline-none focus:ring-2 focus:ring-[#76B900]'
                    )}
                    title={`Click to view ${item.count} ${item.name.toLowerCase()} risk events`}
                    data-testid={`risk-count-${item.riskLevelKey}`}
                  >
                    <Text
                      className={clsx(
                        'text-2xl font-bold',
                        item.color === 'green' && 'text-green-500',
                        item.color === 'yellow' && 'text-yellow-500',
                        item.color === 'orange' && 'text-orange-500',
                        item.color === 'red' && 'text-red-500'
                      )}
                    >
                      {formatCount(item.count)}
                    </Text>
                    <Text className="text-xs text-gray-400">{item.name}</Text>
                  </button>
                ))}
              </div>
              <Text className="text-center text-xs text-gray-500">
                Total Events: {formatCount(totalEventCount)}
              </Text>
            </div>
          )}
        </ResponsiveChart>
      </Card>
    </div>
  );
}
