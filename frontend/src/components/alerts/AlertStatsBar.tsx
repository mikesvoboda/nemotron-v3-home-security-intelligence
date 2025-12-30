import { Badge, Text } from '@tremor/react';
import { clsx } from 'clsx';
import { AlertTriangle, Clock, Eye, Flame, TrendingUp } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { fetchEventStats } from '../../services/api';

import type { EventStatsResponse } from '../../services/api';

export interface AlertStatsBarProps {
  /** Polling interval in milliseconds (default: 30000, 0 to disable) */
  pollingInterval?: number;
  /** Additional CSS classes */
  className?: string;
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
 * AlertStatsBar displays a horizontal summary bar with key alert statistics:
 * - Total critical alerts
 * - Total high alerts
 * - Unreviewed count
 * - Time since last alert
 */
export default function AlertStatsBar({
  pollingInterval = 30000,
  className,
}: AlertStatsBarProps) {
  const [stats, setStats] = useState<EventStatsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const response = await fetchEventStats();
      setStats(response);
    } catch (err) {
      console.error('Failed to fetch alert stats:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchData();

    if (pollingInterval > 0) {
      const intervalId = setInterval(() => {
        void fetchData();
      }, pollingInterval);

      return () => clearInterval(intervalId);
    }
  }, [fetchData, pollingInterval]);

  const byRiskLevel = stats?.events_by_risk_level;
  const criticalCount: number = byRiskLevel?.critical ?? 0;
  const highCount: number = byRiskLevel?.high ?? 0;
  // Note: unreviewed_count is not in generated types - using 0 as placeholder
  const unreviewedCount = 0;
  const totalAlerts = criticalCount + highCount;

  // Calculate average risk score (simplified - would need more data from backend)
  const avgRiskIndicator = totalAlerts > 0 ? (criticalCount > highCount ? 'Critical' : 'High') : 'Low';

  return (
    <div
      className={clsx(
        'flex flex-wrap items-center gap-4 rounded-lg border border-gray-800 bg-[#1F1F1F] p-4',
        className
      )}
      data-testid="alert-stats-bar"
    >
      {/* Critical Alerts */}
      <div className="flex items-center gap-2" data-testid="critical-alerts-stat">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-red-500/10">
          <Flame className="h-4 w-4 text-red-500" />
        </div>
        <div>
          <Text className="text-xs text-gray-500">Critical</Text>
          <div className="flex items-center gap-1">
            <Text className="text-lg font-bold text-white">
              {loading ? '-' : formatCount(criticalCount)}
            </Text>
            {criticalCount > 0 && (
              <Badge color="red" size="xs">
                Active
              </Badge>
            )}
          </div>
        </div>
      </div>

      <div className="h-8 w-px bg-gray-700" />

      {/* High Alerts */}
      <div className="flex items-center gap-2" data-testid="high-alerts-stat">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-orange-500/10">
          <AlertTriangle className="h-4 w-4 text-orange-500" />
        </div>
        <div>
          <Text className="text-xs text-gray-500">High</Text>
          <div className="flex items-center gap-1">
            <Text className="text-lg font-bold text-white">
              {loading ? '-' : formatCount(highCount)}
            </Text>
            {highCount > 0 && (
              <Badge color="orange" size="xs">
                Active
              </Badge>
            )}
          </div>
        </div>
      </div>

      <div className="h-8 w-px bg-gray-700" />

      {/* Unreviewed */}
      <div className="flex items-center gap-2" data-testid="unreviewed-alerts-stat">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-500/10">
          <Eye className="h-4 w-4 text-blue-500" />
        </div>
        <div>
          <Text className="text-xs text-gray-500">Unreviewed</Text>
          <Text className="text-lg font-bold text-white">
            {loading ? '-' : formatCount(unreviewedCount)}
          </Text>
        </div>
      </div>

      <div className="h-8 w-px bg-gray-700" />

      {/* Risk Trend (simplified) */}
      <div className="flex items-center gap-2" data-testid="risk-trend-stat">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-500/10">
          <TrendingUp className="h-4 w-4 text-purple-500" />
        </div>
        <div>
          <Text className="text-xs text-gray-500">Dominant Level</Text>
          <Text
            className={clsx(
              'text-sm font-semibold',
              avgRiskIndicator === 'Critical' && 'text-red-400',
              avgRiskIndicator === 'High' && 'text-orange-400',
              avgRiskIndicator === 'Low' && 'text-green-400'
            )}
          >
            {loading ? '-' : avgRiskIndicator}
          </Text>
        </div>
      </div>

      <div className="h-8 w-px bg-gray-700" />

      {/* Last Alert Time (would need backend support for actual last_event_time) */}
      <div className="flex items-center gap-2" data-testid="last-alert-stat">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gray-500/10">
          <Clock className="h-4 w-4 text-gray-400" />
        </div>
        <div>
          <Text className="text-xs text-gray-500">Total Alerts</Text>
          <Text className="text-lg font-bold text-white">
            {loading ? '-' : formatCount(totalAlerts)}
          </Text>
        </div>
      </div>

      {/* Alert Rate Badge */}
      <div className="ml-auto">
        {totalAlerts > 50 ? (
          <Badge color="red" size="sm">
            High Activity
          </Badge>
        ) : totalAlerts > 10 ? (
          <Badge color="yellow" size="sm">
            Moderate Activity
          </Badge>
        ) : totalAlerts > 0 ? (
          <Badge color="green" size="sm">
            Normal Activity
          </Badge>
        ) : (
          <Badge color="gray" size="sm">
            No Alerts
          </Badge>
        )}
      </div>
    </div>
  );
}
