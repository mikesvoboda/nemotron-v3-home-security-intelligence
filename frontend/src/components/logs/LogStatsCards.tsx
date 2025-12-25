import { Card, Title, Text, Badge, Grid } from '@tremor/react';
import { clsx } from 'clsx';
import { AlertCircle, AlertTriangle, FileText, Activity } from 'lucide-react';
import { useEffect, useState } from 'react';

import { fetchLogStats, type LogStats } from '../../services/api';

export interface LogStatsCardsProps {
  className?: string;
}

/**
 * LogStatsCards component displays log statistics in a dashboard card grid
 * - Shows error count (red badge if >0), warnings, total logs today
 * - Displays most active component
 * - Uses NVIDIA dark theme colors (zinc-900 background, green accents)
 * - Matches GpuStats component styling
 */
export default function LogStatsCards({ className }: LogStatsCardsProps) {
  const [stats, setStats] = useState<LogStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadStats = async () => {
      try {
        setLoading(true);
        const data = await fetchLogStats();
        setStats(data);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load log stats');
      } finally {
        setLoading(false);
      }
    };

    void loadStats();
    // Refresh every 30 seconds
    const interval = setInterval(() => {
      void loadStats();
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading && !stats) {
    return (
      <Card className={clsx('bg-[#1A1A1A] border-gray-800 shadow-lg', className)}>
        <Title className="text-white mb-4 flex items-center gap-2">
          <FileText className="h-5 w-5 text-[#76B900]" />
          Log Statistics
        </Title>
        <Text className="text-gray-400">Loading...</Text>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className={clsx('bg-[#1A1A1A] border-gray-800 shadow-lg', className)}>
        <Title className="text-white mb-4 flex items-center gap-2">
          <FileText className="h-5 w-5 text-[#76B900]" />
          Log Statistics
        </Title>
        <Text className="text-red-500">{error}</Text>
      </Card>
    );
  }

  if (!stats) {
    return null;
  }

  return (
    <Card className={clsx('bg-[#1A1A1A] border-gray-800 shadow-lg', className)}>
      <Title className="text-white mb-4 flex items-center gap-2">
        <FileText className="h-5 w-5 text-[#76B900]" />
        Log Statistics
      </Title>

      <Grid numItemsSm={2} numItemsLg={4} className="gap-4">
        {/* Error Count */}
        <Card className="bg-zinc-900 border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <Text className="text-gray-400 text-sm">Errors Today</Text>
              <div className="flex items-center gap-2 mt-1">
                <Text
                  className={clsx(
                    'text-2xl font-semibold',
                    stats.errors_today > 0 ? 'text-red-500' : 'text-gray-300'
                  )}
                >
                  {stats.errors_today}
                </Text>
                {stats.errors_today > 0 && (
                  <Badge color="red" size="sm">
                    Active
                  </Badge>
                )}
              </div>
            </div>
            <AlertCircle
              className={clsx(
                'h-8 w-8',
                stats.errors_today > 0 ? 'text-red-500' : 'text-gray-600'
              )}
            />
          </div>
        </Card>

        {/* Warning Count */}
        <Card className="bg-zinc-900 border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <Text className="text-gray-400 text-sm">Warnings Today</Text>
              <Text
                className={clsx(
                  'text-2xl font-semibold mt-1',
                  stats.warnings_today > 0 ? 'text-yellow-500' : 'text-gray-300'
                )}
              >
                {stats.warnings_today}
              </Text>
            </div>
            <AlertTriangle
              className={clsx(
                'h-8 w-8',
                stats.warnings_today > 0 ? 'text-yellow-500' : 'text-gray-600'
              )}
            />
          </div>
        </Card>

        {/* Total Today */}
        <Card className="bg-zinc-900 border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <Text className="text-gray-400 text-sm">Total Today</Text>
              <Text className="text-2xl font-semibold text-[#76B900] mt-1">
                {stats.total_today}
              </Text>
            </div>
            <FileText className="h-8 w-8 text-[#76B900]" />
          </div>
        </Card>

        {/* Most Active Component */}
        <Card className="bg-zinc-900 border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <Text className="text-gray-400 text-sm">Most Active</Text>
              <Text className="text-lg font-medium text-white mt-1 truncate">
                {stats.top_component || 'N/A'}
              </Text>
              {stats.top_component && stats.by_component[stats.top_component] && (
                <Text className="text-xs text-gray-500 mt-0.5">
                  {stats.by_component[stats.top_component]} logs
                </Text>
              )}
            </div>
            <Activity className="h-8 w-8 text-gray-600" />
          </div>
        </Card>
      </Grid>
    </Card>
  );
}
