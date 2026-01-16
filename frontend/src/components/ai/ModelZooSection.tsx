/**
 * ModelZooSection - Displays Model Zoo status cards and latency chart
 *
 * Shows a dropdown-controlled latency chart and compact status cards for all
 * 18 Model Zoo models. Models are grouped by category in the dropdown with
 * disabled models at the bottom (grayed out).
 */

import {
  Card,
  Title,
  Text,
  AreaChart,
  Select,
  SelectItem,
  Accordion,
  AccordionHeader,
  AccordionBody,
  AccordionList,
} from '@tremor/react';
import { clsx } from 'clsx';
import { TrendingUp, Boxes, Cpu, MemoryStick, Clock } from 'lucide-react';
import { useState, useEffect, useCallback, useMemo } from 'react';

import {
  fetchModelZooCompactStatus,
  fetchModelZooLatencyHistory,
  type ModelZooStatusResponse,
  type ModelLatencyHistoryResponse,
  type ModelZooStatusItem,
} from '../../services/api';

// ============================================================================
// Model Category Configuration
// ============================================================================

/**
 * Model categories for dropdown grouping (order matters for display)
 */
const MODEL_CATEGORIES = [
  'Detection',
  'Classification',
  'Segmentation',
  'Pose',
  'Depth',
  'Embedding',
  'OCR',
  'Action Recognition',
  'Disabled',
] as const;

/**
 * Props for ModelZooSection component
 */
export interface ModelZooSectionProps {
  /** Additional CSS classes */
  className?: string;
  /** Polling interval in ms (default 30000 = 30s) */
  pollingInterval?: number;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Format milliseconds for display
 */
function formatMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return '-';
  if (ms < 1) return '< 1ms';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
}

/**
 * Format time ago for display
 */
function formatTimeAgo(timestamp: string | null): string {
  if (!timestamp) return 'Never';
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
}

/**
 * Get status indicator styles
 */
function getStatusStyles(status: ModelZooStatusItem['status']): {
  dotColor: string;
  bgColor: string;
  label: string;
} {
  switch (status) {
    case 'loaded':
      return {
        dotColor: 'bg-green-500',
        bgColor: 'bg-green-500/10',
        label: 'Loaded',
      };
    case 'loading':
      return {
        dotColor: 'bg-blue-500 animate-pulse',
        bgColor: 'bg-blue-500/10',
        label: 'Loading',
      };
    case 'disabled':
      return {
        dotColor: 'bg-yellow-500',
        bgColor: 'bg-yellow-500/10',
        label: 'Disabled',
      };
    case 'error':
      return {
        dotColor: 'bg-red-500',
        bgColor: 'bg-red-500/10',
        label: 'Error',
      };
    default:
      return {
        dotColor: 'bg-gray-500',
        bgColor: 'bg-gray-500/10',
        label: 'Unloaded',
      };
  }
}

// ============================================================================
// ModelStatusCard Component
// ============================================================================

interface ModelStatusCardProps {
  model: ModelZooStatusItem;
}

function ModelStatusCard({ model }: ModelStatusCardProps) {
  const styles = getStatusStyles(model.status);

  return (
    <div
      className={clsx(
        'rounded-lg border border-gray-700 p-3 transition-colors',
        model.enabled ? 'bg-gray-800/50' : 'bg-gray-900/50 opacity-60'
      )}
      data-testid={`model-card-${model.name}`}
    >
      {/* Header: Name and Status */}
      <div className="mb-2 flex items-center justify-between">
        <Text className="truncate text-sm font-medium text-gray-200" title={model.display_name}>
          {model.display_name}
        </Text>
        <div className="flex items-center gap-1.5">
          <span className={clsx('h-2 w-2 rounded-full', styles.dotColor)} />
          <Text className="text-xs text-gray-400">{styles.label}</Text>
        </div>
      </div>

      {/* Stats Row */}
      <div className="flex items-center justify-between text-xs text-gray-400">
        {/* VRAM */}
        <div className="flex items-center gap-1">
          <MemoryStick className="h-3 w-3" />
          <span>{model.vram_mb}MB</span>
        </div>

        {/* Last Used */}
        <div className="flex items-center gap-1">
          <Clock className="h-3 w-3" />
          <span>{formatTimeAgo(model.last_used_at)}</span>
        </div>
      </div>

      {/* Category Badge */}
      <div className="mt-2">
        <span className="inline-block rounded bg-gray-700/50 px-1.5 py-0.5 text-xs text-gray-400">
          {model.category}
        </span>
      </div>
    </div>
  );
}

// ============================================================================
// ModelLatencyChart Component
// ============================================================================

interface ModelLatencyChartProps {
  selectedModel: string;
  onModelChange: (model: string) => void;
  models: ModelZooStatusItem[];
}

function ModelLatencyChart({ selectedModel, onModelChange, models }: ModelLatencyChartProps) {
  const [historyData, setHistoryData] = useState<ModelLatencyHistoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHistory = useCallback(async () => {
    if (!selectedModel) return;

    try {
      setLoading(true);
      setError(null);
      const data = await fetchModelZooLatencyHistory(selectedModel, 60, 60);
      setHistoryData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch latency history');
    } finally {
      setLoading(false);
    }
  }, [selectedModel]);

  // Fetch history when model changes or on interval
  useEffect(() => {
    void fetchHistory();
    const interval = setInterval(() => void fetchHistory(), 60000);
    return () => clearInterval(interval);
  }, [fetchHistory]);

  // Create a flat list of models with category prefixes for dropdown
  // Tremor Select doesn't support nested category headers in options
  const sortedModels = useMemo(() => {
    const enabled = models.filter((m) => m.enabled);
    const disabled = models.filter((m) => !m.enabled);

    // Sort enabled by category, then by name
    enabled.sort((a, b) => {
      const catIndexA = MODEL_CATEGORIES.indexOf(a.category as (typeof MODEL_CATEGORIES)[number]);
      const catIndexB = MODEL_CATEGORIES.indexOf(b.category as (typeof MODEL_CATEGORIES)[number]);
      if (catIndexA !== catIndexB) return catIndexA - catIndexB;
      return a.display_name.localeCompare(b.display_name);
    });

    // Disabled models go at the end
    disabled.sort((a, b) => a.display_name.localeCompare(b.display_name));

    return [...enabled, ...disabled];
  }, [models]);

  // Transform data for chart
  const chartData =
    historyData?.snapshots.map((snapshot) => {
      const time = new Date(snapshot.timestamp).toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
      });
      return {
        time,
        'Avg (ms)': snapshot.stats?.avg_ms ?? null,
        'P50 (ms)': snapshot.stats?.p50_ms ?? null,
        'P95 (ms)': snapshot.stats?.p95_ms ?? null,
      };
    }) ?? [];

  const selectedModelData = models.find((m) => m.name === selectedModel);
  const modelDisplayName = selectedModelData?.display_name ?? selectedModel;

  return (
    <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="model-zoo-latency-chart">
      <div className="mb-4 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <Title className="flex items-center gap-2 text-white">
          <TrendingUp className="h-5 w-5 text-[#76B900]" />
          Model Zoo Latency Over Time
        </Title>
        <Select
          value={selectedModel}
          onValueChange={onModelChange}
          className="w-full sm:w-64"
          data-testid="model-select"
        >
          {sortedModels.map((model) => (
            <SelectItem
              key={model.name}
              value={model.name}
              className={clsx(!model.enabled && 'text-gray-500')}
            >
              [{model.category}] {model.display_name}
              {!model.enabled && ' (disabled)'}
            </SelectItem>
          ))}
        </Select>
      </div>

      {loading && !historyData && (
        <div className="flex h-48 items-center justify-center">
          <Text className="text-gray-500">Loading latency history for {modelDisplayName}...</Text>
        </div>
      )}

      {error && (
        <div className="flex h-48 items-center justify-center">
          <Text className="text-red-400">Error: {error}</Text>
        </div>
      )}

      {!loading && !error && !historyData?.has_data && (
        <div className="flex h-48 flex-col items-center justify-center gap-2">
          <Text className="text-gray-400">No data available for {modelDisplayName}</Text>
          <Text className="text-xs text-gray-500">
            This model has not been used recently or is disabled
          </Text>
        </div>
      )}

      {historyData?.has_data && chartData.length > 0 && (
        <AreaChart
          className="h-48"
          data={chartData}
          index="time"
          categories={['Avg (ms)', 'P50 (ms)', 'P95 (ms)']}
          colors={['emerald', 'blue', 'amber']}
          valueFormatter={(value) => (value !== null ? formatMs(value) : '-')}
          showLegend={true}
          showGridLines={true}
          curveType="monotone"
          connectNulls={false}
          data-testid="model-latency-area-chart"
        />
      )}

      {historyData?.timestamp && (
        <Text className="mt-2 text-xs text-gray-500">
          Last updated: {new Date(historyData.timestamp).toLocaleTimeString()}
        </Text>
      )}
    </Card>
  );
}

// ============================================================================
// ModelZooSection Main Component
// ============================================================================

/**
 * ModelZooSection - Main component for Model Zoo status and latency visualization
 */
export default function ModelZooSection({
  className,
  pollingInterval = 30000,
}: ModelZooSectionProps) {
  const [statusData, setStatusData] = useState<ModelZooStatusResponse | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>('yolo11-license-plate');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      setError(null);
      const data = await fetchModelZooCompactStatus();
      setStatusData(data);

      // Set default selected model if not set
      if (data.models.length > 0 && !data.models.find((m) => m.name === selectedModel)) {
        const firstEnabled = data.models.find((m) => m.enabled);
        if (firstEnabled) {
          setSelectedModel(firstEnabled.name);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch Model Zoo status');
    } finally {
      setLoading(false);
    }
  }, [selectedModel]);

  // Fetch status on mount and at interval
  useEffect(() => {
    void fetchStatus();
    const interval = setInterval(() => void fetchStatus(), pollingInterval);
    return () => clearInterval(interval);
  }, [fetchStatus, pollingInterval]);

  // Group models by enabled/disabled for cards display
  const enabledModels = statusData?.models.filter((m) => m.enabled) ?? [];
  const disabledModels = statusData?.models.filter((m) => !m.enabled) ?? [];

  return (
    <div className={clsx('space-y-4', className)} data-testid="model-zoo-section">
      {/* Summary Header */}
      <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="model-zoo-summary">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <Boxes className="h-5 w-5 text-[#76B900]" />
            <Title className="text-white">Model Zoo</Title>
          </div>

          {statusData && (
            <div className="flex flex-wrap items-center gap-4 text-sm text-gray-400">
              <div className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-green-500" />
                <span>{statusData.loaded_count} loaded</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-gray-500" />
                <span>
                  {statusData.total_models - statusData.loaded_count - statusData.disabled_count}{' '}
                  unloaded
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-yellow-500" />
                <span>{statusData.disabled_count} disabled</span>
              </div>
              <div className="flex items-center gap-1.5 border-l border-gray-700 pl-4">
                <Cpu className="h-4 w-4" />
                <span>
                  {statusData.vram_used_mb}/{statusData.vram_budget_mb}MB VRAM
                </span>
              </div>
            </div>
          )}
        </div>
      </Card>

      {/* Loading State */}
      {loading && !statusData && (
        <div className="flex h-64 items-center justify-center">
          <Text className="text-gray-500">Loading Model Zoo status...</Text>
        </div>
      )}

      {/* Error State */}
      {error && (
        <Card className="border-red-800 bg-red-900/20">
          <Text className="text-red-400">Error loading Model Zoo status: {error}</Text>
        </Card>
      )}

      {/* Latency Chart with Dropdown */}
      {statusData && statusData.models.length > 0 && (
        <ModelLatencyChart
          selectedModel={selectedModel}
          onModelChange={setSelectedModel}
          models={statusData.models}
        />
      )}

      {/* Status Cards Grid - Collapsible Accordions */}
      {statusData && (
        <div className="space-y-4">
          {/* Enabled Models */}
          {enabledModels.length > 0 && (
            <AccordionList>
              <Accordion defaultOpen={true}>
                <AccordionHeader className="text-white">
                  <Text className="text-sm font-medium text-gray-400">
                    Active Models ({enabledModels.length})
                  </Text>
                </AccordionHeader>
                <AccordionBody>
                  <div
                    className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
                    data-testid="enabled-models-grid"
                  >
                    {enabledModels.map((model) => (
                      <ModelStatusCard key={model.name} model={model} />
                    ))}
                  </div>
                </AccordionBody>
              </Accordion>
            </AccordionList>
          )}

          {/* Disabled Models */}
          {disabledModels.length > 0 && (
            <AccordionList>
              <Accordion defaultOpen={false}>
                <AccordionHeader className="text-white">
                  <Text className="text-sm font-medium text-gray-500">
                    Disabled Models ({disabledModels.length})
                  </Text>
                </AccordionHeader>
                <AccordionBody>
                  <div
                    className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
                    data-testid="disabled-models-grid"
                  >
                    {disabledModels.map((model) => (
                      <ModelStatusCard key={model.name} model={model} />
                    ))}
                  </div>
                </AccordionBody>
              </Accordion>
            </AccordionList>
          )}
        </div>
      )}
    </div>
  );
}
