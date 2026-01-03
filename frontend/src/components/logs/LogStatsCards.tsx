import { Card, Title, Text, Badge, Grid } from '@tremor/react';
import { clsx } from 'clsx';
import { AlertCircle, AlertTriangle, FileText, Activity } from 'lucide-react';
import { useEffect, useState } from 'react';

import { fetchLogStats, type LogStats } from '../../services/api';

import type { LogLevel } from '../../services/logger';

export interface LogStatsCardsProps {
  className?: string;
  /** Callback when a level filter card is clicked */
  onLevelFilter?: (level: LogLevel | undefined) => void;
  /** Currently active level filter (for visual indication) */
  activeLevel?: LogLevel;
}

/**
 * LogStatsCards component displays log statistics in a dashboard card grid
 * - Shows error count (red badge if >0), warnings, total logs today
 * - Displays most active component
 * - Uses NVIDIA dark theme colors (zinc-900 background, green accents)
 * - Matches GpuStats component styling
 */
export default function LogStatsCards({
  className,
  onLevelFilter,
  activeLevel,
}: LogStatsCardsProps) {
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
      <Card className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}>
        <Title className="mb-4 flex items-center gap-2 text-white">
          <FileText className="h-5 w-5 text-[#76B900]" />
          Log Statistics
        </Title>
        <Text className="text-gray-400">Loading...</Text>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}>
        <Title className="mb-4 flex items-center gap-2 text-white">
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

  // Handle click on level filter cards (toggle behavior)
  const handleLevelClick = (level: LogLevel) => {
    if (onLevelFilter) {
      // Toggle: if already active, clear the filter; otherwise set the filter
      onLevelFilter(activeLevel === level ? undefined : level);
    }
  };

  // Check if a level is currently active for styling
  const isErrorActive = activeLevel === 'ERROR';
  const isWarningActive = activeLevel === 'WARNING';

  return (
    <Card className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}>
      <Title className="mb-4 flex items-center gap-2 text-white">
        <FileText className="h-5 w-5 text-[#76B900]" />
        Log Statistics
      </Title>

      <Grid numItemsSm={2} numItemsLg={4} className="gap-4">
        {/* Error Count - Clickable */}
        <Card
          className={clsx(
            'border-gray-700 bg-zinc-900 transition-all duration-200',
            onLevelFilter && 'cursor-pointer hover:border-red-500/50 hover:bg-zinc-800',
            isErrorActive && 'ring-2 ring-red-500 ring-offset-2 ring-offset-zinc-900'
          )}
          onClick={() => handleLevelClick('ERROR')}
          role={onLevelFilter ? 'button' : undefined}
          tabIndex={onLevelFilter ? 0 : undefined}
          onKeyDown={
            onLevelFilter
              ? (e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    handleLevelClick('ERROR');
                  }
                }
              : undefined
          }
          aria-pressed={onLevelFilter ? isErrorActive : undefined}
          aria-label={onLevelFilter ? 'Filter by errors' : undefined}
        >
          <div className="flex items-center justify-between">
            <div>
              <Text className="text-sm text-gray-400">Errors Today</Text>
              <div className="mt-1 flex items-center gap-2">
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
              className={clsx('h-8 w-8', stats.errors_today > 0 ? 'text-red-500' : 'text-gray-600')}
            />
          </div>
        </Card>

        {/* Warning Count - Clickable */}
        <Card
          className={clsx(
            'border-gray-700 bg-zinc-900 transition-all duration-200',
            onLevelFilter && 'cursor-pointer hover:border-yellow-500/50 hover:bg-zinc-800',
            isWarningActive && 'ring-2 ring-yellow-500 ring-offset-2 ring-offset-zinc-900'
          )}
          onClick={() => handleLevelClick('WARNING')}
          role={onLevelFilter ? 'button' : undefined}
          tabIndex={onLevelFilter ? 0 : undefined}
          onKeyDown={
            onLevelFilter
              ? (e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    handleLevelClick('WARNING');
                  }
                }
              : undefined
          }
          aria-pressed={onLevelFilter ? isWarningActive : undefined}
          aria-label={onLevelFilter ? 'Filter by warnings' : undefined}
        >
          <div className="flex items-center justify-between">
            <div>
              <Text className="text-sm text-gray-400">Warnings Today</Text>
              <Text
                className={clsx(
                  'mt-1 text-2xl font-semibold',
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
        <Card className="border-gray-700 bg-zinc-900">
          <div className="flex items-center justify-between">
            <div>
              <Text className="text-sm text-gray-400">Total Today</Text>
              <Text className="mt-1 text-2xl font-semibold text-[#76B900]">
                {stats.total_today}
              </Text>
            </div>
            <FileText className="h-8 w-8 text-[#76B900]" />
          </div>
        </Card>

        {/* Most Active Component */}
        <Card className="border-gray-700 bg-zinc-900">
          <div className="flex items-center justify-between">
            <div>
              <Text className="text-sm text-gray-400">Most Active</Text>
              <Text className="mt-1 truncate text-lg font-medium text-white">
                {stats.top_component || 'N/A'}
              </Text>
              {stats.top_component && stats.by_component[stats.top_component] && (
                <Text className="mt-0.5 text-xs text-gray-500">
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
