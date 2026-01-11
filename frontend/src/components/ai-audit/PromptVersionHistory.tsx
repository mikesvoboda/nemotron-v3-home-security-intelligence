/**
 * PromptVersionHistory Component
 *
 * Displays version history for AI model prompt configurations.
 * Allows users to view past versions, see changes, and restore previous versions.
 *
 * Features:
 * - Model selector dropdown to filter by model
 * - Version history table with date, description, and actions
 * - Restore button to revert to a previous version
 * - Loading and error states
 *
 * @module components/ai-audit/PromptVersionHistory
 */

import {
  Card,
  Table,
  TableHead,
  TableRow,
  TableHeaderCell,
  TableBody,
  TableCell,
  Select,
  SelectItem,
  Badge,
} from '@tremor/react';
import { clsx } from 'clsx';
import {
  AlertCircle,
  CheckCircle,
  Clock,
  History,
  Loader2,
  RefreshCw,
  RotateCcw,
} from 'lucide-react';
import { useCallback, useState } from 'react';

import { useAIAuditPromptHistoryQuery } from '../../hooks/useAIAuditQueries';
import { restorePromptVersion, PromptApiError } from '../../services/promptManagementApi';
import { Skeleton } from '../common';

import type { AIModelEnum, PromptVersionInfo } from '../../types/promptManagement';

// ============================================================================
// Types
// ============================================================================

export interface PromptVersionHistoryProps {
  /** Period in days for filtering (used by parent for consistency) */
  periodDays?: number;
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Constants
// ============================================================================

const MODEL_OPTIONS = [
  { value: '', label: 'All Models' },
  { value: 'nemotron', label: 'Nemotron' },
  { value: 'florence2', label: 'Florence-2' },
  { value: 'yolo_world', label: 'YOLO-World' },
  { value: 'xclip', label: 'X-CLIP' },
  { value: 'fashion_clip', label: 'Fashion-CLIP' },
] as const;

const MODEL_DISPLAY_NAMES: Record<string, string> = {
  nemotron: 'Nemotron',
  florence2: 'Florence-2',
  yolo_world: 'YOLO-World',
  xclip: 'X-CLIP',
  fashion_clip: 'Fashion-CLIP',
};

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Format model name for display
 */
function formatModelName(model: string): string {
  return MODEL_DISPLAY_NAMES[model] || model;
}

/**
 * Format date for display
 */
function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Get relative time string
 */
function getRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return formatDate(dateString);
}

// ============================================================================
// Skeleton Component
// ============================================================================

function VersionHistorySkeleton() {
  return (
    <div className="space-y-4" data-testid="version-history-loading">
      {/* Model selector skeleton */}
      <div className="flex items-center gap-4">
        <Skeleton variant="rectangular" width={200} height={40} />
      </div>
      {/* Table skeleton */}
      <div className="space-y-2">
        {[1, 2, 3, 4, 5].map((i) => (
          <Skeleton key={i} variant="rectangular" height={56} />
        ))}
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * PromptVersionHistory - Display and manage prompt version history
 */
export default function PromptVersionHistory({
  className,
}: PromptVersionHistoryProps) {
  // State
  const [selectedModel, setSelectedModel] = useState<AIModelEnum | undefined>(undefined);
  const [restoringVersion, setRestoringVersion] = useState<number | null>(null);
  const [restoreSuccess, setRestoreSuccess] = useState<string | null>(null);
  const [restoreError, setRestoreError] = useState<string | null>(null);

  // Query for version history
  const {
    data: historyData,
    isLoading,
    error,
    refetch,
  } = useAIAuditPromptHistoryQuery({
    model: selectedModel,
    limit: 50,
  });

  // Handle model filter change
  const handleModelChange = (value: string) => {
    setSelectedModel(value === '' ? undefined : (value as AIModelEnum));
    setRestoreSuccess(null);
    setRestoreError(null);
  };

  // Handle restore version
  const handleRestore = useCallback(
    async (version: PromptVersionInfo) => {
      setRestoringVersion(version.id);
      setRestoreSuccess(null);
      setRestoreError(null);

      try {
        const result = await restorePromptVersion(version.id);
        setRestoreSuccess(
          `Restored ${formatModelName(result.model)} to version ${result.restored_version} (new version: ${result.new_version})`
        );
        // Refetch to update the list
        await refetch();
      } catch (err) {
        if (err instanceof PromptApiError) {
          setRestoreError(err.message);
        } else {
          setRestoreError('Failed to restore version');
        }
      } finally {
        setRestoringVersion(null);
      }
    },
    [refetch]
  );

  // Loading state
  if (isLoading) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid="prompt-version-history"
      >
        <VersionHistorySkeleton />
      </Card>
    );
  }

  // Error state
  if (error) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid="prompt-version-history-error"
      >
        <div className="flex flex-col items-center justify-center py-12">
          <AlertCircle className="mb-4 h-12 w-12 text-red-500" />
          <h3 className="mb-2 text-lg font-semibold text-red-500">
            Failed to Load Version History
          </h3>
          <p className="mb-4 text-sm text-gray-400">
            {error instanceof Error ? error.message : 'An error occurred'}
          </p>
          <button
            onClick={() => void refetch()}
            className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700"
            data-testid="retry-button"
          >
            <RefreshCw className="h-4 w-4" />
            Try Again
          </button>
        </div>
      </Card>
    );
  }

  const versions = historyData?.versions ?? [];
  const hasVersions = versions.length > 0;

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="prompt-version-history"
    >
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <History className="h-5 w-5 text-[#76B900]" />
          <h2 className="text-lg font-semibold text-white">Prompt Version History</h2>
        </div>
        <button
          onClick={() => void refetch()}
          className="flex items-center gap-2 rounded-lg bg-gray-800 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-gray-700"
          data-testid="refresh-history-button"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      </div>

      {/* Model Selector */}
      <div className="mb-6">
        <label htmlFor="model-filter" className="mb-2 block text-sm font-medium text-gray-400">
          Filter by Model
        </label>
        <Select
          id="model-filter"
          value={selectedModel ?? ''}
          onValueChange={handleModelChange}
          className="w-48"
          data-testid="model-filter"
        >
          {MODEL_OPTIONS.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </Select>
      </div>

      {/* Success Banner */}
      {restoreSuccess && (
        <div
          className="mb-4 flex items-center gap-2 rounded-lg border border-green-800 bg-green-900/20 p-3"
          data-testid="restore-success-banner"
        >
          <CheckCircle className="h-5 w-5 text-green-400" />
          <span className="text-sm text-green-400">{restoreSuccess}</span>
        </div>
      )}

      {/* Error Banner */}
      {restoreError && (
        <div
          className="mb-4 flex items-center gap-2 rounded-lg border border-red-800 bg-red-900/20 p-3"
          data-testid="restore-error-banner"
        >
          <AlertCircle className="h-5 w-5 text-red-400" />
          <span className="text-sm text-red-400">{restoreError}</span>
        </div>
      )}

      {/* Version History Table */}
      {hasVersions ? (
        <Table data-testid="version-history-table">
          <TableHead>
            <TableRow>
              <TableHeaderCell className="text-gray-400">Version</TableHeaderCell>
              <TableHeaderCell className="text-gray-400">Model</TableHeaderCell>
              <TableHeaderCell className="text-gray-400">Date</TableHeaderCell>
              <TableHeaderCell className="text-gray-400">Changes</TableHeaderCell>
              <TableHeaderCell className="text-gray-400">Status</TableHeaderCell>
              <TableHeaderCell className="text-right text-gray-400">Actions</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {versions.map((version: PromptVersionInfo) => (
              <TableRow key={version.id} data-testid={`version-row-${version.id}`}>
                <TableCell className="font-mono text-[#76B900]">
                  v{version.version}
                </TableCell>
                <TableCell className="font-medium text-white">
                  {formatModelName(version.model)}
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2 text-gray-400">
                    <Clock className="h-4 w-4" />
                    <span title={formatDate(version.created_at)}>
                      {getRelativeTime(version.created_at)}
                    </span>
                  </div>
                </TableCell>
                <TableCell>
                  <span className="text-sm text-gray-300">
                    {version.change_description || 'No description'}
                  </span>
                </TableCell>
                <TableCell>
                  {version.is_active ? (
                    <Badge color="emerald" size="sm">
                      Active
                    </Badge>
                  ) : (
                    <Badge color="gray" size="sm">
                      Previous
                    </Badge>
                  )}
                </TableCell>
                <TableCell className="text-right">
                  {!version.is_active && (
                    <button
                      onClick={() => void handleRestore(version)}
                      disabled={restoringVersion !== null}
                      className="flex items-center gap-1.5 rounded-lg bg-gray-800 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
                      data-testid={`restore-button-${version.id}`}
                    >
                      {restoringVersion === version.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <RotateCcw className="h-4 w-4" />
                      )}
                      Restore
                    </button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : (
        <div
          className="flex flex-col items-center justify-center py-12 text-center"
          data-testid="empty-state"
        >
          <History className="mb-4 h-12 w-12 text-gray-600" />
          <h3 className="mb-2 text-lg font-semibold text-white">No Version History</h3>
          <p className="max-w-md text-sm text-gray-400">
            {selectedModel
              ? `No version history available for ${formatModelName(selectedModel)}.`
              : 'No prompt version history available yet. Version history will be recorded when prompts are updated.'}
          </p>
        </div>
      )}

      {/* Total Count */}
      {hasVersions && historyData && (
        <div className="mt-4 text-center text-xs text-gray-500">
          Showing {versions.length} of {historyData.total_count} versions
        </div>
      )}
    </Card>
  );
}
