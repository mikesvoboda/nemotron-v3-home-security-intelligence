/**
 * ModelCard - Individual AI model card for Model Zoo management
 *
 * Displays model information including:
 * - Model name and category badge
 * - Status indicator (loaded/unloaded/disabled)
 * - VRAM usage (actual when loaded, estimated when not)
 * - Load/Unload buttons with confirmation dialog
 * - Last used timestamp and load count
 *
 * @see NEM-4790 - Frontend Admin Panel
 * @see docs/plans/2025-01-31-model-zoo-management-design.md
 */

import { Badge, Card, Text } from '@tremor/react';
import { clsx } from 'clsx';
import { Loader2, Cpu, Clock, Hash } from 'lucide-react';
import { memo, useState, useCallback } from 'react';

import ConfirmDialog from '../jobs/ConfirmDialog';

import type { ModelStatus } from '../../services/modelZooApi';

/**
 * Props for ModelCard component
 */
export interface ModelCardProps {
  /** Model status data */
  model: ModelStatus;
  /** Callback when load button is clicked */
  onLoad: (modelName: string) => void;
  /** Callback when unload is confirmed */
  onUnload: (modelName: string) => void;
  /** Whether a load/unload operation is in progress */
  isLoading?: boolean;
  /** Which action is currently loading */
  loadingAction?: 'load' | 'unload';
  /** Error message to display */
  error?: string;
}

/**
 * Get category badge color based on model category
 */
function getCategoryColor(
  category: string
): 'blue' | 'emerald' | 'amber' | 'purple' | 'pink' | 'cyan' | 'gray' {
  switch (category.toLowerCase()) {
    case 'detection':
      return 'blue';
    case 'classification':
      return 'emerald';
    case 'embedding':
      return 'purple';
    case 'segmentation':
      return 'pink';
    case 'pose':
      return 'cyan';
    case 'depth':
      return 'amber';
    default:
      return 'gray';
  }
}

/**
 * Format relative time from ISO timestamp
 */
function formatRelativeTime(isoTimestamp: string | null): string {
  if (!isoTimestamp) return 'Never';

  const date = new Date(isoTimestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSeconds < 60) return 'Just now';
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;

  return date.toLocaleDateString();
}

/**
 * ModelCard component displays an individual model with its status and controls
 */
const ModelCard = memo(function ModelCard({
  model,
  onLoad,
  onUnload,
  isLoading = false,
  // loadingAction is part of the public API for future extensibility
  // (e.g., showing different loading indicators based on action type)
  // but is not currently used in the component implementation.
  loadingAction: _loadingAction,
  error,
}: ModelCardProps) {
  const [showUnloadDialog, setShowUnloadDialog] = useState(false);

  const isLoaded = model.runtime?.loaded ?? false;
  const isDisabled = !model.enabled;

  // Status text and class
  const statusText = isDisabled ? 'Disabled' : isLoaded ? 'Loaded' : 'Unloaded';
  const statusClass = isDisabled
    ? 'bg-gray-500/20 text-gray-400 disabled'
    : isLoaded
    ? 'bg-emerald-500/20 text-emerald-400 loaded green active'
    : 'bg-gray-500/20 text-gray-400 unloaded gray inactive';

  const handleLoadClick = useCallback(() => {
    onLoad(model.name);
  }, [model.name, onLoad]);

  const handleUnloadClick = useCallback(() => {
    setShowUnloadDialog(true);
  }, []);

  const handleUnloadConfirm = useCallback(() => {
    setShowUnloadDialog(false);
    onUnload(model.name);
  }, [model.name, onUnload]);

  const handleUnloadCancel = useCallback(() => {
    setShowUnloadDialog(false);
  }, []);

  return (
    <>
      <Card
        data-testid={`model-card-${model.name}`}
        role="article"
        className={clsx(
          'relative border-gray-800 bg-[#1A1A1A] p-4 shadow-lg',
          isDisabled && 'opacity-60'
        )}
      >
        {/* Loading overlay */}
        {isLoading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center rounded-lg bg-black/50">
            <Loader2 data-testid="loading-spinner" className="h-6 w-6 animate-spin text-[#76B900]" />
          </div>
        )}

        {/* Header: Name and Status */}
        <div className="mb-3 flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <Text className="truncate font-semibold text-white">{model.name}</Text>
            <Badge
              color={getCategoryColor(model.category)}
              size="xs"
              className="badge chip tag mt-1"
            >
              {model.category}
            </Badge>
          </div>
          <div
            data-testid="model-status-indicator"
            className={clsx('flex-shrink-0 rounded-full px-2 py-0.5 text-xs font-medium', statusClass)}
          >
            {statusText}
          </div>
        </div>

        {/* Info Grid */}
        <div className="mb-3 grid grid-cols-2 gap-2 text-xs">
          {/* VRAM Usage */}
          <div className="flex items-center gap-1.5 text-gray-400">
            <Cpu className="h-3.5 w-3.5" />
            <span>
              {isLoaded && model.runtime?.actual_vram_mb ? (
                <>
                  <span className="text-white">{model.runtime.actual_vram_mb} MB</span>
                  <span className="text-gray-500"> / {model.estimated_vram_mb} MB</span>
                </>
              ) : (
                <span>~{model.estimated_vram_mb} MB</span>
              )}
            </span>
          </div>

          {/* GPU Assignment */}
          <div className="flex items-center gap-1.5 text-gray-400">
            <span className="text-[#76B900]">GPU {model.gpu_id}</span>
          </div>

          {/* Last Used */}
          <div className="flex items-center gap-1.5 text-gray-400">
            <Clock className="h-3.5 w-3.5" />
            <span>
              Last used:{' '}
              {model.runtime?.last_used ? (
                formatRelativeTime(model.runtime.last_used)
              ) : (
                <span>Never</span>
              )}
            </span>
          </div>

          {/* Load Count */}
          <div className="flex items-center gap-1.5 text-gray-400">
            <Hash className="h-3.5 w-3.5" />
            <span>{model.runtime?.load_count ?? 0} loads</span>
          </div>
        </div>

        {/* Service Name */}
        <div className="mb-3 text-xs text-gray-500">
          Service: <span className="text-gray-400">{model.service}</span>
        </div>

        {/* Error Display */}
        {error && (
          <div className="mb-3 rounded bg-red-500/10 p-2 text-xs text-red-400">{error}</div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleLoadClick}
            disabled={isLoading || isLoaded || isDisabled}
            aria-label="Load"
            className={clsx(
              'flex-1 rounded px-3 py-1.5 text-xs font-medium transition-colors',
              'focus:outline-none focus:ring-2 focus:ring-[#76B900]/50',
              isLoading || isLoaded || isDisabled
                ? 'cursor-not-allowed bg-gray-700 text-gray-500'
                : 'bg-[#76B900] text-white hover:bg-[#6aa800]'
            )}
          >
            Load
          </button>
          <button
            type="button"
            onClick={handleUnloadClick}
            disabled={isLoading || !isLoaded || isDisabled}
            className={clsx(
              'flex-1 rounded px-3 py-1.5 text-xs font-medium transition-colors',
              'focus:outline-none focus:ring-2 focus:ring-gray-500/50',
              isLoading || !isLoaded || isDisabled
                ? 'cursor-not-allowed bg-gray-700 text-gray-500'
                : 'bg-gray-600 text-white hover:bg-gray-500'
            )}
          >
            Unload
          </button>
        </div>
      </Card>

      {/* Unload Confirmation Dialog */}
      <ConfirmDialog
        isOpen={showUnloadDialog}
        title="Unload Model"
        description={`Are you sure you want to unload "${model.name}"? The model will need to reload on next use, which may cause latency.`}
        confirmLabel="Confirm"
        cancelLabel="Cancel"
        variant="warning"
        onConfirm={handleUnloadConfirm}
        onCancel={handleUnloadCancel}
      />
    </>
  );
});

export default ModelCard;
