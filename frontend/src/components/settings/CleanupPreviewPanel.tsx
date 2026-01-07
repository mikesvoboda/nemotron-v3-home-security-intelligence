import { Button, Card, Text, Title } from '@tremor/react';
import { AlertCircle, Eye, Trash2, Database, FileImage, HardDrive } from 'lucide-react';
import { useState } from 'react';

import { previewCleanup, triggerCleanup, type CleanupResponse } from '../../services/api';

export interface CleanupPreviewPanelProps {
  className?: string;
}

/**
 * CleanupPreviewPanel provides a preview of what will be deleted by the retention policy
 *
 * Features:
 * - Dry-run capability to preview cleanup impact before running
 * - Breakdown by data type (events, detections, GPU stats, logs, files)
 * - Disk space estimation for reclaimed storage
 * - Manual cleanup trigger with confirmation dialog
 * - Visual indicators for data types using icons
 * - Loading and error states
 */
export default function CleanupPreviewPanel({ className }: CleanupPreviewPanelProps) {
  const [preview, setPreview] = useState<CleanupResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [cleaning, setCleaning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);
  const [cleanupResult, setCleanupResult] = useState<CleanupResponse | null>(null);

  const handlePreview = async () => {
    try {
      setLoading(true);
      setError(null);
      setCleanupResult(null);

      const result = await previewCleanup();
      setPreview(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to preview cleanup');
    } finally {
      setLoading(false);
    }
  };

  const handleCleanup = async () => {
    try {
      setCleaning(true);
      setError(null);
      setShowConfirm(false);

      const result = await triggerCleanup();
      setCleanupResult(result);
      setPreview(null);

      // Clear result after 10 seconds
      setTimeout(() => setCleanupResult(null), 10000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to run cleanup');
    } finally {
      setCleaning(false);
    }
  };

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
  };

  const hasDeletableData =
    preview &&
    (preview.events_deleted > 0 ||
      preview.detections_deleted > 0 ||
      preview.gpu_stats_deleted > 0 ||
      preview.logs_deleted > 0 ||
      preview.thumbnails_deleted > 0 ||
      preview.images_deleted > 0);

  return (
    <Card className={`border-gray-800 bg-[#1A1A1A] shadow-lg ${className || ''}`}>
      <Title className="mb-4 flex items-center gap-2 text-white">
        <Eye className="h-5 w-5 text-[#76B900]" />
        Cleanup Preview
      </Title>

      <Text className="mb-4 text-gray-400">
        Preview what will be deleted by the retention policy before running cleanup. This performs
        a dry-run calculation without actually deleting any data.
      </Text>

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <AlertCircle className="h-5 w-5 flex-shrink-0 text-red-500" />
          <Text className="text-red-500">{error}</Text>
        </div>
      )}

      {cleanupResult && (
        <div className="mb-4 rounded-lg border border-green-500/30 bg-green-500/10 p-4">
          <Text className="mb-3 font-medium text-green-400">Cleanup Complete</Text>
          <div className="space-y-2">
            <div className="flex items-center justify-between border-b border-green-500/20 pb-2">
              <Text className="font-medium text-green-300">Summary</Text>
              <Text className="text-sm text-gray-400">Retention: {cleanupResult.retention_days} days</Text>
            </div>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <Text className="text-gray-400">Events deleted:</Text>
              <Text className="text-white">{cleanupResult.events_deleted.toLocaleString()}</Text>
              <Text className="text-gray-400">Detections deleted:</Text>
              <Text className="text-white">{cleanupResult.detections_deleted.toLocaleString()}</Text>
              <Text className="text-gray-400">GPU stats deleted:</Text>
              <Text className="text-white">{cleanupResult.gpu_stats_deleted.toLocaleString()}</Text>
              <Text className="text-gray-400">Logs deleted:</Text>
              <Text className="text-white">{cleanupResult.logs_deleted.toLocaleString()}</Text>
              <Text className="text-gray-400">Thumbnails deleted:</Text>
              <Text className="text-white">{cleanupResult.thumbnails_deleted.toLocaleString()}</Text>
              <Text className="text-gray-400">Images deleted:</Text>
              <Text className="text-white">{cleanupResult.images_deleted.toLocaleString()}</Text>
              <Text className="text-gray-400">Space reclaimed:</Text>
              <Text className="font-medium text-green-400">{formatBytes(cleanupResult.space_reclaimed)}</Text>
            </div>
          </div>
        </div>
      )}

      {preview && (
        <div className="mb-4 space-y-4">
          <div className="rounded-lg border border-blue-500/30 bg-blue-500/10 p-4">
            <div className="mb-3 flex items-center justify-between border-b border-blue-500/20 pb-2">
              <Text className="font-medium text-blue-300">Preview Results</Text>
              <Text className="text-sm text-gray-400">Retention: {preview.retention_days} days</Text>
            </div>

            {hasDeletableData ? (
              <>
                {/* Database Records */}
                <div className="mb-4">
                  <div className="mb-2 flex items-center gap-2">
                    <Database className="h-4 w-4 text-blue-400" />
                    <Text className="font-medium text-blue-300">Database Records</Text>
                  </div>
                  <div className="grid grid-cols-2 gap-2 pl-6 text-sm">
                    {preview.events_deleted > 0 && (
                      <>
                        <Text className="text-gray-400">Events:</Text>
                        <Text className="text-white">{preview.events_deleted.toLocaleString()}</Text>
                      </>
                    )}
                    {preview.detections_deleted > 0 && (
                      <>
                        <Text className="text-gray-400">Detections:</Text>
                        <Text className="text-white">{preview.detections_deleted.toLocaleString()}</Text>
                      </>
                    )}
                    {preview.gpu_stats_deleted > 0 && (
                      <>
                        <Text className="text-gray-400">GPU Stats:</Text>
                        <Text className="text-white">{preview.gpu_stats_deleted.toLocaleString()}</Text>
                      </>
                    )}
                    {preview.logs_deleted > 0 && (
                      <>
                        <Text className="text-gray-400">Logs:</Text>
                        <Text className="text-white">{preview.logs_deleted.toLocaleString()}</Text>
                      </>
                    )}
                  </div>
                </div>

                {/* Files */}
                {(preview.thumbnails_deleted > 0 || preview.images_deleted > 0) && (
                  <div className="mb-4">
                    <div className="mb-2 flex items-center gap-2">
                      <FileImage className="h-4 w-4 text-blue-400" />
                      <Text className="font-medium text-blue-300">Files</Text>
                    </div>
                    <div className="grid grid-cols-2 gap-2 pl-6 text-sm">
                      {preview.thumbnails_deleted > 0 && (
                        <>
                          <Text className="text-gray-400">Thumbnails:</Text>
                          <Text className="text-white">{preview.thumbnails_deleted.toLocaleString()}</Text>
                        </>
                      )}
                      {preview.images_deleted > 0 && (
                        <>
                          <Text className="text-gray-400">Images:</Text>
                          <Text className="text-white">{preview.images_deleted.toLocaleString()}</Text>
                        </>
                      )}
                    </div>
                  </div>
                )}

                {/* Disk Space */}
                {preview.space_reclaimed > 0 && (
                  <div className="rounded-md border border-blue-500/30 bg-blue-500/5 p-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <HardDrive className="h-4 w-4 text-blue-400" />
                        <Text className="font-medium text-blue-300">Estimated Space to Reclaim</Text>
                      </div>
                      <Text className="text-lg font-semibold text-blue-400">
                        {formatBytes(preview.space_reclaimed)}
                      </Text>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <Text className="text-center text-gray-400">No data to clean up based on current retention settings</Text>
            )}
          </div>

          {hasDeletableData && !showConfirm && (
            <Button
              onClick={() => setShowConfirm(true)}
              className="w-full border-red-500/30 bg-red-500/20 text-red-400 hover:bg-red-500/30"
            >
              <Trash2 className="mr-2 h-4 w-4" />
              Proceed with Cleanup
            </Button>
          )}

          {showConfirm && (
            <div className="rounded-lg border border-red-500/50 bg-red-500/10 p-4">
              <div className="mb-3 flex items-center gap-2">
                <AlertCircle className="h-5 w-5 text-red-400" />
                <Text className="font-medium text-red-400">Confirm Cleanup</Text>
              </div>
              <Text className="mb-4 text-sm text-gray-300">
                This action cannot be undone. The following data will be permanently deleted:
              </Text>
              <div className="mb-4 space-y-1 text-sm">
                {preview.events_deleted > 0 && (
                  <Text className="text-gray-400">• {preview.events_deleted.toLocaleString()} events</Text>
                )}
                {preview.detections_deleted > 0 && (
                  <Text className="text-gray-400">• {preview.detections_deleted.toLocaleString()} detections</Text>
                )}
                {preview.gpu_stats_deleted > 0 && (
                  <Text className="text-gray-400">• {preview.gpu_stats_deleted.toLocaleString()} GPU stats</Text>
                )}
                {preview.logs_deleted > 0 && (
                  <Text className="text-gray-400">• {preview.logs_deleted.toLocaleString()} logs</Text>
                )}
                {preview.thumbnails_deleted > 0 && (
                  <Text className="text-gray-400">• {preview.thumbnails_deleted.toLocaleString()} thumbnail files</Text>
                )}
                {preview.images_deleted > 0 && (
                  <Text className="text-gray-400">• {preview.images_deleted.toLocaleString()} image files</Text>
                )}
              </div>
              <div className="flex gap-3">
                <Button
                  onClick={() => void handleCleanup()}
                  disabled={cleaning}
                  className="flex-1 bg-red-500 text-white hover:bg-red-600 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {cleaning ? 'Deleting...' : 'Yes, Delete Data'}
                </Button>
                <Button
                  onClick={() => setShowConfirm(false)}
                  disabled={cleaning}
                  variant="secondary"
                  className="flex-1 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </div>
      )}

      {!preview && !cleanupResult && (
        <Button
          onClick={() => void handlePreview()}
          disabled={loading}
          className="w-full bg-[#76B900] text-white hover:bg-[#5c8f00] disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Eye className="mr-2 h-4 w-4" />
          {loading ? 'Calculating Preview...' : 'Preview Cleanup'}
        </Button>
      )}

      {preview && !showConfirm && (
        <Button
          onClick={() => setPreview(null)}
          variant="secondary"
          className="w-full"
        >
          Clear Preview
        </Button>
      )}
    </Card>
  );
}
