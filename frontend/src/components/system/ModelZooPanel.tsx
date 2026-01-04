import { Card, Title, Text, Badge, ProgressBar, Table, TableHead, TableHeaderCell, TableBody, TableRow, TableCell } from '@tremor/react';
import { clsx } from 'clsx';
import { Cpu, RefreshCw, AlertCircle, Package, ChevronDown, ChevronUp } from 'lucide-react';
import { useState, useMemo } from 'react';

import type { VRAMStats } from '../../hooks/useModelZooStatus';
import type { ModelStatusResponse } from '../../services/api';

/**
 * Props for the ModelZooPanel component.
 */
export interface ModelZooPanelProps {
  /** List of models from the Model Zoo registry */
  models: ModelStatusResponse[];
  /** VRAM usage statistics */
  vramStats: VRAMStats | null;
  /** Loading state */
  isLoading: boolean;
  /** Error message if fetch failed */
  error: string | null;
  /** Callback to refresh data */
  onRefresh: () => void;
  /** Whether to show all models by default (default: false - show only active) */
  defaultShowAll?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Get badge color based on model status.
 */
function getStatusColor(status: string): 'green' | 'yellow' | 'red' | 'gray' {
  switch (status) {
    case 'loaded':
      return 'green';
    case 'loading':
      return 'yellow';
    case 'error':
      return 'red';
    case 'unloaded':
      return 'gray';
    case 'disabled':
      return 'gray';
    default:
      return 'gray';
  }
}

/**
 * Get status display text.
 */
function getStatusText(status: string): string {
  switch (status) {
    case 'loaded':
      return 'Loaded';
    case 'unloaded':
      return 'Unloaded';
    case 'disabled':
      return 'Disabled';
    case 'loading':
      return 'Loading';
    case 'error':
      return 'Error';
    default:
      return status.charAt(0).toUpperCase() + status.slice(1);
  }
}

/**
 * Get VRAM progress bar color based on usage percentage.
 */
function getVramProgressColor(usagePercent: number): 'emerald' | 'yellow' | 'orange' | 'red' {
  if (usagePercent < 50) return 'emerald';
  if (usagePercent < 75) return 'yellow';
  if (usagePercent < 90) return 'orange';
  return 'red';
}

/**
 * Check if a model is active (loaded or loading)
 */
function isActiveModel(model: ModelStatusResponse): boolean {
  return model.status === 'loaded' || model.status === 'loading';
}

/**
 * ModelZooPanel - Displays AI Model Zoo status and VRAM usage.
 *
 * Features:
 * - VRAM budget progress bar showing current consumption
 * - Table of models with status badges
 * - Default shows only loaded/loading models
 * - "Show All" toggle to expand full model list
 * - Load count (inference count) for loaded models
 * - Refresh button for manual updates
 * - Loading, error, and empty states
 *
 * Design matches the task specification:
 * ```
 * +---------------------------------------------------------+
 * | AI Model Zoo                     VRAM: 2.0/24GB [Show All]|
 * +---------------------------------------------------------+
 * | Model                    | Status   | VRAM   | Inferences|
 * |---------------------------------------------------------|
 * | RT-DETRv2               | Loaded   | 1.2GB  | 1,847     |
 * | CLIP ViT-L              | Loaded   | 0.8GB  | 1,234     |
 * +---------------------------------------------------------+
 * | 16 models unloaded                         [Show All ->] |
 * +---------------------------------------------------------+
 * ```
 */
export default function ModelZooPanel({
  models,
  vramStats,
  isLoading,
  error,
  onRefresh,
  defaultShowAll = false,
  className,
}: ModelZooPanelProps) {
  const [showAll, setShowAll] = useState(defaultShowAll);

  // Separate active and inactive models
  const { inactiveModels, displayedModels } = useMemo(() => {
    const active = models.filter(isActiveModel);
    const inactive = models.filter((m) => !isActiveModel(m));
    return {
      inactiveModels: inactive,
      displayedModels: showAll ? models : active,
    };
  }, [models, showAll]);
  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="model-zoo-panel"
    >
      {/* Header with title, VRAM summary, and controls */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-3">
          <Title className="flex items-center gap-2 text-white">
            <Package className="h-5 w-5 text-[#76B900]" />
            AI Model Zoo
          </Title>
          {/* Inline VRAM summary */}
          {vramStats && (
            <span className="text-sm text-gray-400" data-testid="vram-inline-summary">
              VRAM: {(vramStats.used_mb / 1024).toFixed(1)}/{(vramStats.budget_mb / 1024).toFixed(0)}GB
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* Show All toggle */}
          <button
            type="button"
            onClick={() => setShowAll(!showAll)}
            className={clsx(
              'flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors',
              showAll
                ? 'bg-[#76B900]/20 text-[#76B900]'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            )}
            data-testid="model-zoo-show-all-toggle"
          >
            {showAll ? (
              <>
                Show Active
                <ChevronUp className="h-3 w-3" />
              </>
            ) : (
              <>
                Show All
                <ChevronDown className="h-3 w-3" />
              </>
            )}
          </button>
          {/* Refresh button */}
          <button
            onClick={onRefresh}
            disabled={isLoading}
            className={clsx(
              'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
              isLoading
                ? 'cursor-not-allowed bg-gray-700 text-gray-500'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600 hover:text-white'
            )}
            data-testid="model-zoo-refresh-btn"
          >
            <RefreshCw
              className={clsx('h-4 w-4', isLoading && 'animate-spin')}
            />
            Refresh
          </button>
        </div>
      </div>

      {/* Loading state */}
      {isLoading && models.length === 0 && (
        <div
          className="flex h-32 items-center justify-center"
          data-testid="model-zoo-loading"
        >
          <div className="flex items-center gap-2 text-gray-400">
            <RefreshCw className="h-5 w-5 animate-spin" />
            <Text>Loading model status...</Text>
          </div>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div
          className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3"
          data-testid="model-zoo-error"
        >
          <AlertCircle className="h-5 w-5 text-red-500" />
          <Text className="text-red-400">{error}</Text>
        </div>
      )}

      {/* Content - only show when not in initial loading and no error */}
      {!isLoading && !error && (
        <>
          {/* VRAM Budget Progress */}
          {vramStats && (
            <div className="mb-4 rounded-lg bg-gray-800/50 p-3">
              <div className="mb-2 flex items-center justify-between text-sm">
                <Text className="text-gray-400">VRAM Budget</Text>
                <Text className="font-medium text-white">
                  {vramStats.used_mb}/{vramStats.budget_mb} MB ({Math.round(vramStats.usage_percent)}%)
                </Text>
              </div>
              <ProgressBar
                value={vramStats.usage_percent}
                color={getVramProgressColor(vramStats.usage_percent)}
                className="bg-gray-700"
                data-testid="vram-progress-bar"
              />
            </div>
          )}

          {/* Empty state - no models at all */}
          {models.length === 0 && (
            <div
              className="flex h-32 items-center justify-center"
              data-testid="model-zoo-empty"
            >
              <div className="text-center">
                <Cpu className="mx-auto mb-2 h-8 w-8 text-gray-600" />
                <Text className="text-gray-500">No models registered</Text>
              </div>
            </div>
          )}

          {/* Empty state - no active models (when not showing all) */}
          {models.length > 0 && displayedModels.length === 0 && !showAll && (
            <div
              className="flex h-24 flex-col items-center justify-center"
              data-testid="model-zoo-no-active"
            >
              <Text className="text-gray-500">No active models</Text>
              <button
                type="button"
                onClick={() => setShowAll(true)}
                className="mt-2 flex items-center gap-1 text-xs text-[#76B900] hover:underline"
                data-testid="show-all-link"
              >
                Show all {inactiveModels.length} models
                <ChevronDown className="h-3 w-3" />
              </button>
            </div>
          )}

          {/* Model Table */}
          {displayedModels.length > 0 && (
            <div className="overflow-hidden rounded-lg border border-gray-800">
              <Table>
                <TableHead className="bg-gray-800/50">
                  <TableRow>
                    <TableHeaderCell className="text-gray-400">Model</TableHeaderCell>
                    <TableHeaderCell className="text-gray-400">Status</TableHeaderCell>
                    <TableHeaderCell className="text-gray-400">VRAM</TableHeaderCell>
                    <TableHeaderCell className="text-gray-400">Inferences</TableHeaderCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {displayedModels.map((model) => (
                    <TableRow
                      key={model.name}
                      className="border-gray-800 hover:bg-gray-800/30"
                    >
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <div
                            className={clsx(
                              'h-2 w-2 rounded-full',
                              model.status === 'loaded' ? 'bg-green-500' : 'bg-gray-500'
                            )}
                          />
                          <Text className="font-medium text-white">
                            {model.display_name}
                          </Text>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge
                          color={getStatusColor(model.status)}
                          size="sm"
                          data-testid={`status-badge-${model.name}`}
                        >
                          {getStatusText(model.status)}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Text className="text-gray-300">{model.vram_mb} MB</Text>
                      </TableCell>
                      <TableCell>
                        <Text className="text-gray-300">
                          {model.status === 'loaded' && (model.load_count ?? 0) > 0
                            ? (model.load_count ?? 0).toLocaleString()
                            : '-'}
                        </Text>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {/* Unloaded models summary - shown when not showing all */}
              {!showAll && inactiveModels.length > 0 && (
                <div
                  className="flex items-center justify-between border-t border-gray-800 bg-gray-800/30 px-4 py-2"
                  data-testid="unloaded-models-summary"
                >
                  <Text className="text-sm text-gray-500">
                    {inactiveModels.length} model{inactiveModels.length !== 1 ? 's' : ''} unloaded
                  </Text>
                  <button
                    type="button"
                    onClick={() => setShowAll(true)}
                    className="flex items-center gap-1 text-xs text-[#76B900] hover:underline"
                    data-testid="show-all-footer-link"
                  >
                    Show All
                    <ChevronDown className="h-3 w-3" />
                  </button>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </Card>
  );
}
