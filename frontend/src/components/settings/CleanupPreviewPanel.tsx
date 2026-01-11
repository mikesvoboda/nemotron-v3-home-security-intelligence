import { Button, Card, Text, Title } from '@tremor/react';
import { AlertCircle, Eye, Trash2, Database, FileImage, HardDrive } from 'lucide-react';
import { useState, useEffect } from 'react';

import { useCleanupPreviewMutation, useCleanupMutation } from '../../hooks';

import type { CleanupResponse } from '../../services/api';

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
 *
 * Uses React Query mutations for preview and cleanup operations:
 * - useCleanupPreviewMutation: Performs dry-run cleanup preview
 * - useCleanupMutation: Executes actual cleanup operation
 */
export default function CleanupPreviewPanel({ className }: CleanupPreviewPanelProps) {
  const [showConfirm, setShowConfirm] = useState(false);

  // Use React Query mutations for preview and cleanup
  const {
    preview,
    previewData,
    isPending: previewLoading,
    error: previewError,
    reset: resetPreview,
  } = useCleanupPreviewMutation();

  const {
    cleanup,
    cleanupData,
    isPending: cleanupLoading,
    error: cleanupError,
    reset: resetCleanup,
  } = useCleanupMutation();

  // Clear cleanup result after 10 seconds
  useEffect(() => {
    if (cleanupData) {
      const timer = setTimeout(() => resetCleanup(), 10000);
      return () => clearTimeout(timer);
    }
  }, [cleanupData, resetCleanup]);

  const handlePreview = async () => {
    resetCleanup(); // Clear any previous cleanup result
    await preview();
  };

  const handleCleanup = async () => {
    setShowConfirm(false);
    await cleanup();
    resetPreview(); // Clear preview after successful cleanup
  };

  const handleClearPreview = () => {
    resetPreview();
    setShowConfirm(false);
  };

  const formatBytes = (bytes: number | null | undefined): string => {
    if (bytes === null || bytes === undefined || bytes === 0 || !Number.isFinite(bytes)) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
  };

  // Combine errors from both mutations
  const error = previewError || cleanupError;
  const errorMessage = error?.message || null;

  const hasDeletableData =
    previewData &&
    (previewData.events_deleted > 0 ||
      previewData.detections_deleted > 0 ||
      previewData.gpu_stats_deleted > 0 ||
      previewData.logs_deleted > 0 ||
      previewData.thumbnails_deleted > 0 ||
      previewData.images_deleted > 0);

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

      {errorMessage && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <AlertCircle className="h-5 w-5 flex-shrink-0 text-red-500" />
          <Text className="text-red-500">{errorMessage}</Text>
        </div>
      )}

      {cleanupData && (
        <CleanupCompleteSection cleanupResult={cleanupData} formatBytes={formatBytes} />
      )}

      {previewData && (
        <div className="mb-4 space-y-4">
          <PreviewResultsSection preview={previewData} hasDeletableData={hasDeletableData ?? null} formatBytes={formatBytes} />

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
            <ConfirmCleanupDialog
              preview={previewData}
              cleaning={cleanupLoading}
              onConfirm={() => void handleCleanup()}
              onCancel={() => setShowConfirm(false)}
            />
          )}
        </div>
      )}

      {!previewData && !cleanupData && (
        <Button
          onClick={() => void handlePreview()}
          disabled={previewLoading}
          className="w-full bg-[#76B900] text-white hover:bg-[#5c8f00] disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Eye className="mr-2 h-4 w-4" />
          {previewLoading ? 'Calculating Preview...' : 'Preview Cleanup'}
        </Button>
      )}

      {previewData && !showConfirm && (
        <Button
          onClick={handleClearPreview}
          variant="secondary"
          className="w-full"
        >
          Clear Preview
        </Button>
      )}
    </Card>
  );
}

// Sub-components for better organization

interface CleanupCompleteSectionProps {
  cleanupResult: CleanupResponse;
  formatBytes: (bytes: number) => string;
}

function CleanupCompleteSection({ cleanupResult, formatBytes }: CleanupCompleteSectionProps) {
  return (
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
  );
}

interface PreviewResultsSectionProps {
  preview: CleanupResponse;
  hasDeletableData: boolean | null;
  formatBytes: (bytes: number) => string;
}

function PreviewResultsSection({ preview, hasDeletableData, formatBytes }: PreviewResultsSectionProps) {
  return (
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
  );
}

interface ConfirmCleanupDialogProps {
  preview: CleanupResponse;
  cleaning: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

function ConfirmCleanupDialog({ preview, cleaning, onConfirm, onCancel }: ConfirmCleanupDialogProps) {
  return (
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
          onClick={onConfirm}
          disabled={cleaning}
          className="flex-1 bg-red-700 text-white hover:bg-red-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {cleaning ? 'Deleting...' : 'Yes, Delete Data'}
        </Button>
        <Button
          onClick={onCancel}
          disabled={cleaning}
          variant="secondary"
          className="flex-1 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Cancel
        </Button>
      </div>
    </div>
  );
}
