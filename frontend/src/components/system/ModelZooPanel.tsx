import { Text, Badge, ProgressBar, Table, TableHead, TableHeaderCell, TableBody, TableRow, TableCell, TextInput } from '@tremor/react';
import { clsx } from 'clsx';
import { Cpu, RefreshCw, AlertCircle, CheckCircle, XCircle, Loader2, MinusCircle, Search, Filter } from 'lucide-react';
import { useState, useMemo } from 'react';

import type { VRAMStats } from '../../hooks/useModelZooStatusQuery';
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
  /** Optional data-testid attribute for testing */
  'data-testid'?: string;
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
 * Get status icon for accessibility (not color-only).
 */
function ModelStatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'loaded':
      return <CheckCircle className="h-4 w-4 text-green-500" aria-hidden="true" data-testid="model-status-icon-loaded" />;
    case 'loading':
      return <Loader2 className="h-4 w-4 animate-spin text-yellow-500" aria-hidden="true" data-testid="model-status-icon-loading" />;
    case 'error':
      return <XCircle className="h-4 w-4 text-red-500" aria-hidden="true" data-testid="model-status-icon-error" />;
    case 'unloaded':
    case 'disabled':
    default:
      return <MinusCircle className="h-4 w-4 text-gray-500" aria-hidden="true" data-testid="model-status-icon-inactive" />;
  }
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
  'data-testid': testId = 'model-zoo-panel',
}: ModelZooPanelProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  // Calculate summary stats
  const loadedCount = models.filter((m) => m.status === 'loaded').length;
  const availableCount = models.length;
  const usedVramMB = vramStats?.usedMb ?? 0;
  const budgetVramMB = vramStats?.budgetMb ?? 0;

  // Filter models based on search query and status filter
  const filteredModels = useMemo(() => {
    return models.filter((model) => {
      // Apply search filter
      const matchesSearch =
        searchQuery === '' ||
        model.display_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        model.name.toLowerCase().includes(searchQuery.toLowerCase());

      // Apply status filter
      const matchesStatus = statusFilter === 'all' || model.status === statusFilter;

      return matchesSearch && matchesStatus;
    });
  }, [models, searchQuery, statusFilter]);

  return (
    <div className={clsx('', className)} data-testid={testId}>
      {/* Header with summary and refresh button */}
      <div className="mb-4 flex items-center justify-between">
        <Text className="text-sm text-gray-400">
          {loadedCount} Loaded | {availableCount} Available | {usedVramMB} MB / {budgetVramMB} MB VRAM
        </Text>
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

      {/* Search and Filter Bar */}
      {!isLoading && !error && models.length > 0 && (
        <div className="mb-4 flex flex-col gap-2 sm:flex-row">
          {/* Search Input */}
          <div className="flex-1">
            <TextInput
              icon={Search}
              placeholder="Search models..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full"
              data-testid="model-zoo-search"
            />
          </div>

          {/* Status Filter */}
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-gray-400" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-md border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-300 transition-colors hover:bg-gray-700 focus:border-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]/50"
              data-testid="model-zoo-filter"
            >
              <option value="all">All Status</option>
              <option value="loaded">Loaded</option>
              <option value="unloaded">Unloaded</option>
              <option value="disabled">Disabled</option>
              <option value="loading">Loading</option>
              <option value="error">Error</option>
            </select>
          </div>
        </div>
      )}

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
                  {vramStats.usedMb}/{vramStats.budgetMb} MB ({Math.round(vramStats.usagePercent)}%)
                </Text>
              </div>
              <ProgressBar
                value={vramStats.usagePercent}
                color={getVramProgressColor(vramStats.usagePercent)}
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
            <>
              {filteredModels.length === 0 ? (
                <div
                  className="flex h-32 items-center justify-center"
                  data-testid="model-zoo-no-results"
                >
                  <div className="text-center">
                    <Search className="mx-auto mb-2 h-8 w-8 text-gray-600" />
                    <Text className="text-gray-500">
                      No models match your search or filter
                    </Text>
                  </div>
                </div>
              ) : (
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
                      {filteredModels.map((model) => (
                    <TableRow
                      key={model.name}
                      className="border-gray-800 hover:bg-gray-800/30"
                    >
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {/* Status icon for accessibility (not color-only) */}
                          <ModelStatusIcon status={model.status} />
                          <div
                            className={clsx(
                              'h-2 w-2 rounded-full',
                              model.status === 'loaded' ? 'bg-green-500' : 'bg-gray-500'
                            )}
                            aria-hidden="true"
                          />
                          <Text className="font-medium text-white">
                            {model.display_name}
                          </Text>
                          <span className="sr-only">Status: {getStatusText(model.status)}</span>
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
        </>
      )}
    </div>
  );
}
