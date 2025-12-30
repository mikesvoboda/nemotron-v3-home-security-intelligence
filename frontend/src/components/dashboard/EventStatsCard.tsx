import { Card, Title, Text, BarChart, DonutChart, Legend } from '@tremor/react';
import { clsx } from 'clsx';
import { Activity, AlertTriangle, Camera, RefreshCw, TrendingUp, Eye } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { fetchEventStats, fetchCameras } from '../../services/api';
import { getRiskColor, getRiskLabel } from '../../utils/risk';

import type { EventStatsResponse, Camera as CameraType } from '../../services/api';

export interface EventStatsCardProps {
  /** Polling interval in milliseconds (default: 60000, 0 to disable) */
  pollingInterval?: number;
  /** Show camera breakdown (default: true) */
  showCameraBreakdown?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Risk level chart data
 */
interface RiskChartData {
  name: string;
  value: number;
  color: string;
}

/**
 * Camera chart data
 */
interface CameraChartData {
  camera: string;
  events: number;
}

/**
 * Format large numbers with K/M suffix
 */
function formatCount(count: number): string {
  if (count >= 1000000) return `${(count / 1000000).toFixed(1)}M`;
  if (count >= 1000) return `${(count / 1000).toFixed(1)}K`;
  return count.toString();
}

/**
 * StatTile displays a single statistic
 */
function StatTile({
  icon,
  label,
  value,
  sublabel,
  color = 'text-[#76B900]',
  testId,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  sublabel?: string;
  color?: string;
  testId?: string;
}) {
  return (
    <div
      className="flex items-center gap-3 rounded-lg border border-gray-800 bg-gray-900/50 p-4"
      data-testid={testId}
    >
      <div className={clsx('flex h-10 w-10 items-center justify-center rounded-lg bg-gray-800', color)}>
        {icon}
      </div>
      <div>
        <Text className="text-2xl font-bold text-white">{value}</Text>
        <Text className="text-sm text-gray-400">{label}</Text>
        {sublabel && <Text className="text-xs text-gray-500">{sublabel}</Text>}
      </div>
    </div>
  );
}

/**
 * EventStatsCard displays event statistics including:
 * - Total detection count
 * - Events by risk level distribution
 * - Events by camera (optional)
 * - Total events today
 */
export default function EventStatsCard({
  pollingInterval = 60000,
  showCameraBreakdown = true,
  className,
}: EventStatsCardProps) {
  const [stats, setStats] = useState<EventStatsResponse | null>(null);
  const [cameras, setCameras] = useState<CameraType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [statsResponse, camerasResponse] = await Promise.all([
        fetchEventStats(),
        showCameraBreakdown ? fetchCameras() : Promise.resolve([]),
      ]);
      setStats(statsResponse);
      setCameras(camerasResponse);
      setError(null);
      setLastUpdated(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch event stats');
    } finally {
      setLoading(false);
    }
  }, [showCameraBreakdown]);

  // Initial fetch and polling
  useEffect(() => {
    void fetchData();

    if (pollingInterval > 0) {
      const intervalId = setInterval(() => {
        void fetchData();
      }, pollingInterval);

      return () => clearInterval(intervalId);
    }
  }, [fetchData, pollingInterval]);

  const handleRefresh = () => {
    setLoading(true);
    void fetchData();
  };

  // Calculate chart data with type-safe access
  const byRiskLevel = stats?.events_by_risk_level;
  const riskChartData: RiskChartData[] = byRiskLevel
    ? [
        { name: 'Critical', value: byRiskLevel.critical, color: getRiskColor('critical') },
        { name: 'High', value: byRiskLevel.high, color: getRiskColor('high') },
        { name: 'Medium', value: byRiskLevel.medium, color: getRiskColor('medium') },
        { name: 'Low', value: byRiskLevel.low, color: getRiskColor('low') },
      ].filter((d) => d.value > 0)
    : [];

  const byCamera = stats?.events_by_camera ?? [];
  const cameraChartData: CameraChartData[] = byCamera
    .map((cam) => {
      const camera = cameras.find((c) => c.id === cam.camera_id);
      return {
        camera: camera?.name || cam.camera_name || 'Unknown',
        events: cam.event_count,
      };
    })
    .sort((a, b) => b.events - a.events)
    .slice(0, 5); // Top 5 cameras

  const totalEvents = stats?.total_events ?? 0;
  // Note: unreviewed_count is not in the generated types - using 0 as placeholder
  const unreviewedCount = 0;
  const highAlertCount = (byRiskLevel?.critical ?? 0) + (byRiskLevel?.high ?? 0);

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="event-stats-card"
    >
      <div className="mb-4 flex items-center justify-between">
        <Title className="flex items-center gap-2 text-white">
          <TrendingUp className="h-5 w-5 text-[#76B900]" />
          Event Statistics
        </Title>
        <div className="flex items-center gap-3">
          {lastUpdated && (
            <Text className="text-xs text-gray-500">
              Updated {lastUpdated.toLocaleTimeString()}
            </Text>
          )}
          <button
            onClick={handleRefresh}
            disabled={loading}
            className="flex items-center gap-1 rounded px-2 py-1 text-xs text-gray-400 transition-colors hover:bg-gray-800 hover:text-white disabled:opacity-50"
            aria-label="Refresh statistics"
          >
            <RefreshCw className={clsx('h-3 w-3', loading && 'animate-spin')} />
            Refresh
          </button>
        </div>
      </div>

      {error ? (
        <div
          className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4"
          role="alert"
          data-testid="stats-error"
        >
          <AlertTriangle className="h-5 w-5 text-red-500" />
          <Text className="text-red-400">{error}</Text>
        </div>
      ) : loading && !stats ? (
        <div className="flex h-48 items-center justify-center" data-testid="stats-loading">
          <div className="text-center">
            <div className="mx-auto mb-2 h-8 w-8 animate-spin rounded-full border-2 border-gray-700 border-t-[#76B900]" />
            <Text className="text-gray-500">Loading statistics...</Text>
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Summary Stats Grid */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile
              icon={<Activity className="h-5 w-5" />}
              label="Total Events"
              value={formatCount(totalEvents)}
              sublabel="All time"
              testId="total-events-stat"
            />
            <StatTile
              icon={<AlertTriangle className="h-5 w-5 text-orange-500" />}
              label="High Priority"
              value={formatCount(highAlertCount)}
              sublabel="Critical + High"
              color="text-orange-500"
              testId="high-priority-stat"
            />
            <StatTile
              icon={<Eye className="h-5 w-5 text-blue-500" />}
              label="Unreviewed"
              value={formatCount(unreviewedCount)}
              sublabel="Needs attention"
              color="text-blue-500"
              testId="unreviewed-stat"
            />
            <StatTile
              icon={<Camera className="h-5 w-5 text-purple-500" />}
              label="Active Cameras"
              value={cameras.filter(c => c.status === 'online').length}
              sublabel={`${cameras.length} total`}
              color="text-purple-500"
              testId="cameras-stat"
            />
          </div>

          {/* Charts Row */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Risk Level Distribution */}
            {riskChartData.length > 0 && (
              <div className="rounded-lg border border-gray-800 bg-gray-900/30 p-4">
                <Text className="mb-4 font-medium text-white">Events by Risk Level</Text>
                <div className="flex items-center gap-6">
                  <DonutChart
                    data={riskChartData}
                    category="value"
                    index="name"
                    colors={['red', 'orange', 'yellow', 'green']}
                    className="h-40 w-40"
                    showLabel={false}
                    showAnimation
                    valueFormatter={(v) => formatCount(v)}
                  />
                  <div className="flex-1">
                    <Legend
                      categories={riskChartData.map(d => d.name)}
                      colors={['red', 'orange', 'yellow', 'green']}
                      className="flex-wrap"
                    />
                    <div className="mt-4 space-y-2">
                      {riskChartData.map((item) => (
                        <div key={item.name} className="flex items-center justify-between text-sm">
                          <Text className="text-gray-400">{item.name}</Text>
                          <Text className="font-medium text-white">{formatCount(item.value)}</Text>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Top Cameras by Events */}
            {showCameraBreakdown && cameraChartData.length > 0 && (
              <div className="rounded-lg border border-gray-800 bg-gray-900/30 p-4">
                <Text className="mb-4 font-medium text-white">Top Cameras by Events</Text>
                <BarChart
                  data={cameraChartData}
                  index="camera"
                  categories={['events']}
                  colors={['emerald']}
                  valueFormatter={(v) => formatCount(v)}
                  showLegend={false}
                  showGridLines={false}
                  className="h-48"
                  yAxisWidth={48}
                />
              </div>
            )}
          </div>

          {/* Detailed Risk Level Breakdown */}
          {byRiskLevel && (
            <div className="rounded-lg border border-gray-800 bg-gray-900/30 p-4">
              <Text className="mb-3 font-medium text-white">Risk Level Breakdown</Text>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {(['critical', 'high', 'medium', 'low'] as const).map((level) => {
                  const count = byRiskLevel[level];
                  const color = getRiskColor(level);
                  const label = getRiskLabel(level);
                  const percentage = totalEvents > 0 ? ((count / totalEvents) * 100).toFixed(1) : '0';

                  return (
                    <div
                      key={level}
                      className="rounded-lg border bg-gray-800/50 p-3"
                      style={{ borderColor: `${color}40` }}
                      data-testid={`risk-level-${level}`}
                    >
                      <div className="flex items-center gap-2">
                        <div
                          className="h-3 w-3 rounded-full"
                          style={{ backgroundColor: color }}
                        />
                        <Text className="text-sm font-medium" style={{ color }}>
                          {label}
                        </Text>
                      </div>
                      <Text className="mt-1 text-2xl font-bold text-white">
                        {formatCount(count)}
                      </Text>
                      <Text className="text-xs text-gray-500">
                        {percentage}% of total
                      </Text>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
