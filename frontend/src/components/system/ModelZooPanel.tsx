import { Card, Title, Text, Badge, ProgressBar, Table, TableHead, TableHeaderCell, TableBody, TableRow, TableCell } from '@tremor/react';
import { clsx } from 'clsx';
import { Cpu, RefreshCw, AlertCircle, Package } from 'lucide-react';

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
 * ModelZooPanel - Displays AI Model Zoo status and VRAM usage.
 *
 * Features:
 * - VRAM budget progress bar showing current consumption
 * - Table of all models with status badges
 * - Load count (inference count) for loaded models
 * - Refresh button for manual updates
 * - Loading, error, and empty states
 *
 * Design matches the task specification:
 * ```
 * +---------------------------------------------------------+
 * | AI Model Zoo                                    [Refresh]|
 * +---------------------------------------------------------+
 * | VRAM Budget: ████████░░░░░░░░░░░ 450/1650 MB (27%)      |
 * +---------------------------------------------------------+
 * | Model                    | Status   | VRAM   | Inferences|
 * |---------------------------------------------------------|
 * | CLIP ViT-L/14           | Loaded   | 400 MB | 1,547     |
 * | YOLO11 Face             | Unloaded | 150 MB | -         |
 * +---------------------------------------------------------+
 * ```
 */
export default function ModelZooPanel({
  models,
  vramStats,
  isLoading,
  error,
  onRefresh,
  className,
}: ModelZooPanelProps) {
  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="model-zoo-panel"
    >
      {/* Header with title and refresh button */}
      <div className="mb-4 flex items-center justify-between">
        <Title className="flex items-center gap-2 text-white">
          <Package className="h-5 w-5 text-[#76B900]" />
          AI Model Zoo
        </Title>
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

          {/* Empty state */}
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

          {/* Model Table */}
          {models.length > 0 && (
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
                  {models.map((model) => (
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
            </div>
          )}
        </>
      )}
    </Card>
  );
}
