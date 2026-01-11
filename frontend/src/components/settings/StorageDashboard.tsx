import { Card, Text, ProgressBar, Button } from '@tremor/react';
import {
  HardDrive,
  Image,
  FileVideo,
  Database,
  Trash2,
  RefreshCw,
  AlertCircle,
} from 'lucide-react';

import { useStorageStatsQuery, useCleanupPreviewMutation } from '../../hooks/useStorageStatsQuery';

export interface StorageDashboardProps {
  className?: string;
}

/**
 * Format bytes to human-readable string.
 */
function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';

  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const k = 1024;
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${units[i]}`;
}

/**
 * Format number with thousands separator.
 */
function formatNumber(num: number): string {
  return num.toLocaleString();
}

/**
 * StorageDashboard component displays real-time disk usage metrics and storage breakdown.
 *
 * Features:
 * - Overall disk usage with progress bar
 * - Storage breakdown by category (thumbnails, images, clips)
 * - Database record counts
 * - Cleanup preview (dry run)
 * - Automatic polling for real-time updates
 */
export default function StorageDashboard({ className }: StorageDashboardProps) {
  // Use React Query hooks for storage stats and cleanup preview
  const {
    data: stats,
    isLoading,
    isRefetching,
    error: statsError,
    refetch,
  } = useStorageStatsQuery({
    refetchInterval: 60000, // Poll every minute
  });

  const {
    preview: previewCleanup,
    previewData: cleanupPreview,
    isPending: previewLoading,
    error: previewError,
  } = useCleanupPreviewMutation();

  // Combine loading states for UI (use for showing spinner on refresh button)
  const loading = isLoading || isRefetching;

  // Determine progress bar color based on usage percentage
  const getUsageColor = (percent: number): 'emerald' | 'yellow' | 'orange' | 'red' => {
    if (percent < 50) return 'emerald';
    if (percent < 75) return 'yellow';
    if (percent < 90) return 'orange';
    return 'red';
  };

  // Loading state (only show on initial load, not background refetches)
  if (isLoading && !stats) {
    return (
      <div className={`space-y-4 ${className || ''}`}>
        <div className="skeleton h-8 w-32"></div>
        <div className="skeleton h-6 w-full"></div>
        <div className="skeleton h-20 w-full"></div>
      </div>
    );
  }

  // Error state (only show if we have no data to display)
  if (statsError && !stats) {
    return (
      <div className={`flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4 ${className || ''}`}>
        <AlertCircle className="h-5 w-5 flex-shrink-0 text-red-500" />
        <Text className="text-red-500">{statsError.message}</Text>
        <Button
          size="xs"
          variant="secondary"
          onClick={() => void refetch()}
          className="ml-auto"
        >
          <RefreshCw className="mr-1 h-3 w-3" />
          Retry
        </Button>
      </div>
    );
  }

  if (!stats) {
    return null;
  }

  return (
    <div className={`space-y-4 ${className || ''}`}>
      {/* Disk Usage Overview */}
      <div>
        <div className="mb-2 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <HardDrive className="h-4 w-4 text-gray-400" />
            <Text className="font-medium text-gray-300">Disk Usage</Text>
          </div>
          <Button
            size="xs"
            variant="secondary"
            onClick={() => void refetch()}
            disabled={loading}
            className="text-gray-400 hover:text-white"
          >
            <RefreshCw className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>

        <ProgressBar
          value={stats.disk_usage_percent}
          color={getUsageColor(stats.disk_usage_percent)}
          className="mb-1"
        />

        <div className="flex justify-between text-xs text-gray-500">
          <span>{formatBytes(stats.disk_used_bytes)} used</span>
          <span>{stats.disk_usage_percent.toFixed(1)}%</span>
          <span>{formatBytes(stats.disk_total_bytes)} total</span>
        </div>
      </div>

      {/* Storage Breakdown */}
      <div className="grid grid-cols-3 gap-3">
        {/* Thumbnails */}
        <Card
          className="border-gray-800 bg-[#1A1A1A]/50 p-3"
          decoration="top"
          decorationColor="cyan"
        >
          <div className="flex items-center gap-2 mb-2">
            <Image className="h-4 w-4 text-cyan-500" />
            <Text className="text-xs text-gray-400">Thumbnails</Text>
          </div>
          <Text className="font-semibold text-white">
            {formatBytes(stats.thumbnails.size_bytes)}
          </Text>
          <Text className="text-xs text-gray-500">
            {formatNumber(stats.thumbnails.file_count)} files
          </Text>
        </Card>

        {/* Camera Images */}
        <Card
          className="border-gray-800 bg-[#1A1A1A]/50 p-3"
          decoration="top"
          decorationColor="violet"
        >
          <div className="flex items-center gap-2 mb-2">
            <Image className="h-4 w-4 text-violet-500" />
            <Text className="text-xs text-gray-400">Images</Text>
          </div>
          <Text className="font-semibold text-white">
            {formatBytes(stats.images.size_bytes)}
          </Text>
          <Text className="text-xs text-gray-500">
            {formatNumber(stats.images.file_count)} files
          </Text>
        </Card>

        {/* Video Clips */}
        <Card
          className="border-gray-800 bg-[#1A1A1A]/50 p-3"
          decoration="top"
          decorationColor="amber"
        >
          <div className="flex items-center gap-2 mb-2">
            <FileVideo className="h-4 w-4 text-amber-500" />
            <Text className="text-xs text-gray-400">Clips</Text>
          </div>
          <Text className="font-semibold text-white">
            {formatBytes(stats.clips.size_bytes)}
          </Text>
          <Text className="text-xs text-gray-500">
            {formatNumber(stats.clips.file_count)} files
          </Text>
        </Card>
      </div>

      {/* Database Records */}
      <div className="rounded-lg border border-gray-800 bg-[#1A1A1A]/50 p-3">
        <div className="flex items-center gap-2 mb-2">
          <Database className="h-4 w-4 text-gray-400" />
          <Text className="text-xs text-gray-400">Database Records</Text>
        </div>
        <div className="grid grid-cols-4 gap-2 text-center">
          <div>
            <Text className="font-semibold text-white">{formatNumber(stats.events_count)}</Text>
            <Text className="text-xs text-gray-500">Events</Text>
          </div>
          <div>
            <Text className="font-semibold text-white">{formatNumber(stats.detections_count)}</Text>
            <Text className="text-xs text-gray-500">Detections</Text>
          </div>
          <div>
            <Text className="font-semibold text-white">{formatNumber(stats.gpu_stats_count)}</Text>
            <Text className="text-xs text-gray-500">GPU Stats</Text>
          </div>
          <div>
            <Text className="font-semibold text-white">{formatNumber(stats.logs_count)}</Text>
            <Text className="text-xs text-gray-500">Logs</Text>
          </div>
        </div>
      </div>

      {/* Cleanup Preview */}
      <div className="rounded-lg border border-gray-800 bg-[#1A1A1A]/50 p-3">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Trash2 className="h-4 w-4 text-gray-400" />
            <Text className="text-xs text-gray-400">Cleanup Preview</Text>
          </div>
          <Button
            size="xs"
            variant="secondary"
            onClick={() => void previewCleanup()}
            disabled={previewLoading}
            className="text-gray-400 hover:text-white"
          >
            {previewLoading ? 'Checking...' : 'Preview Cleanup'}
          </Button>
        </div>

        {previewError && !cleanupPreview && (
          <div className="mt-3 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-2">
            <AlertCircle className="h-4 w-4 flex-shrink-0 text-red-500" />
            <Text className="text-xs text-red-500">{previewError.message}</Text>
          </div>
        )}

        {cleanupPreview && (
          <div className="mt-3 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3">
            <Text className="mb-2 text-xs font-medium text-amber-400">
              Would be deleted (based on retention period of {cleanupPreview.retention_days} days):
            </Text>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
              <Text className="text-gray-400">Events:</Text>
              <Text className="text-white">{formatNumber(cleanupPreview.events_deleted)}</Text>
              <Text className="text-gray-400">Detections:</Text>
              <Text className="text-white">{formatNumber(cleanupPreview.detections_deleted)}</Text>
              <Text className="text-gray-400">GPU Stats:</Text>
              <Text className="text-white">{formatNumber(cleanupPreview.gpu_stats_deleted)}</Text>
              <Text className="text-gray-400">Logs:</Text>
              <Text className="text-white">{formatNumber(cleanupPreview.logs_deleted)}</Text>
              <Text className="text-gray-400">Thumbnails:</Text>
              <Text className="text-white">{formatNumber(cleanupPreview.thumbnails_deleted)}</Text>
              <Text className="text-gray-400">Space to reclaim:</Text>
              <Text className="font-semibold text-amber-400">
                {formatBytes(cleanupPreview.space_reclaimed)}
              </Text>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
