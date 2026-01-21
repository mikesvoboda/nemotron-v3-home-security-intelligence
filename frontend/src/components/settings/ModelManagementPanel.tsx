/**
 * ModelManagementPanel - Comprehensive AI model management panel
 *
 * Displays:
 * - VRAM usage overview with progress bar
 * - Model status summary (loaded/unloaded/disabled counts)
 * - Model cards grouped by category
 * - Per-model VRAM usage and load statistics
 *
 * @see NEM-3179 - Add AI model management UI
 */

import { Card, Title, Text, Badge } from '@tremor/react';
import { clsx } from 'clsx';
import {
  Boxes,
  CheckCircle,
  Circle,
  XCircle,
  Loader2,
  AlertCircle,
  MemoryStick,
  RefreshCw,
} from 'lucide-react';
import { useMemo } from 'react';

import VRAMUsageCard from './VRAMUsageCard';
import { useModelZooStatusQuery } from '../../hooks/useModelZooStatusQuery';

import type { ModelStatusResponse } from '../../services/api';


/**
 * Props for ModelManagementPanel component
 */
export interface ModelManagementPanelProps {
  /** Additional CSS classes */
  className?: string;
}

/**
 * Status indicator component
 */
function StatusIndicator({
  status,
}: {
  status: 'loaded' | 'unloaded' | 'loading' | 'error' | 'disabled';
}) {
  const config = {
    loaded: {
      icon: CheckCircle,
      color: 'text-emerald-500',
      bgColor: 'bg-emerald-500/20',
      label: 'Loaded',
    },
    unloaded: {
      icon: Circle,
      color: 'text-gray-400',
      bgColor: 'bg-gray-500/20',
      label: 'Unloaded',
    },
    loading: {
      icon: Loader2,
      color: 'text-blue-400',
      bgColor: 'bg-blue-500/20',
      label: 'Loading',
    },
    error: {
      icon: XCircle,
      color: 'text-red-500',
      bgColor: 'bg-red-500/20',
      label: 'Error',
    },
    disabled: {
      icon: XCircle,
      color: 'text-yellow-500',
      bgColor: 'bg-yellow-500/20',
      label: 'Disabled',
    },
  };

  const { icon: Icon, color, bgColor, label } = config[status];

  return (
    <div
      data-testid={`status-${status}`}
      aria-label={`Status: ${label}`}
      className={clsx('flex items-center gap-1 rounded-full px-2 py-0.5', bgColor)}
    >
      <Icon
        className={clsx('h-3 w-3', color, {
          'animate-spin': status === 'loading',
        })}
      />
      <span className={clsx('text-xs font-medium', color)}>{label}</span>
    </div>
  );
}

/**
 * Individual model card component
 */
function ModelCard({ model }: { model: ModelStatusResponse }) {
  return (
    <div
      className={clsx(
        'rounded-lg border border-gray-700 bg-gray-800/50 p-3 transition-colors hover:border-gray-600',
        {
          'opacity-60': !model.enabled,
        }
      )}
      data-testid={`model-card-${model.name}`}
    >
      {/* Header: Name and Status */}
      <div className="mb-2 flex items-center justify-between">
        <Text className="truncate text-sm font-medium text-white" title={model.display_name}>
          {model.display_name}
        </Text>
        <StatusIndicator status={model.status} />
      </div>

      {/* Category Badge */}
      <div className="mb-2">
        <Badge color="gray" size="xs">
          {model.category}
        </Badge>
      </div>

      {/* Stats Row */}
      <div className="flex items-center justify-between text-xs text-gray-400">
        {/* VRAM */}
        <div className="flex items-center gap-1">
          <MemoryStick className="h-3 w-3" />
          <span>{model.vram_mb} MB</span>
        </div>

        {/* Load Count */}
        {model.load_count !== undefined && model.load_count > 0 && (
          <div className="flex items-center gap-1">
            <RefreshCw className="h-3 w-3" />
            <span>{model.load_count} loads</span>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Category section component
 */
function CategorySection({
  category,
  models,
}: {
  category: string;
  models: ModelStatusResponse[];
}) {
  const loadedCount = models.filter((m) => m.status === 'loaded').length;

  return (
    <div data-testid={`category-${category.toLowerCase()}`} className="space-y-3">
      <div className="flex items-center justify-between">
        <Text className="text-sm font-medium capitalize text-gray-300">{category}</Text>
        <Badge color="gray" size="xs">
          {models.length} models ({loadedCount} loaded)
        </Badge>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {models.map((model) => (
          <ModelCard key={model.name} model={model} />
        ))}
      </div>
    </div>
  );
}

/**
 * Model status summary component
 */
function ModelStatusSummary({
  models,
}: {
  models: ModelStatusResponse[];
}) {
  const counts = useMemo(() => {
    const loaded = models.filter((m) => m.status === 'loaded').length;
    const unloaded = models.filter((m) => m.status === 'unloaded').length;
    const disabled = models.filter((m) => m.status === 'disabled').length;
    const loading = models.filter((m) => m.status === 'loading').length;
    const error = models.filter((m) => m.status === 'error').length;
    return { loaded, unloaded, disabled, loading, error, total: models.length };
  }, [models]);

  return (
    <div
      data-testid="model-status-summary"
      className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6"
    >
      <div className="rounded-lg border border-gray-700 bg-gray-800/30 p-3 text-center">
        <Text className="text-2xl font-bold text-white">{counts.total}</Text>
        <Text className="text-xs text-gray-400">Total</Text>
      </div>
      <div className="rounded-lg border border-emerald-700/50 bg-emerald-500/10 p-3 text-center">
        <Text className="text-2xl font-bold text-emerald-400">{counts.loaded}</Text>
        <Text className="text-xs text-emerald-400/70">Loaded</Text>
      </div>
      <div className="rounded-lg border border-gray-700 bg-gray-800/30 p-3 text-center">
        <Text className="text-2xl font-bold text-gray-400">{counts.unloaded}</Text>
        <Text className="text-xs text-gray-500">Unloaded</Text>
      </div>
      <div className="rounded-lg border border-yellow-700/50 bg-yellow-500/10 p-3 text-center">
        <Text className="text-2xl font-bold text-yellow-400">{counts.disabled}</Text>
        <Text className="text-xs text-yellow-400/70">Disabled</Text>
      </div>
      {counts.loading > 0 && (
        <div className="rounded-lg border border-blue-700/50 bg-blue-500/10 p-3 text-center">
          <Text className="text-2xl font-bold text-blue-400">{counts.loading}</Text>
          <Text className="text-xs text-blue-400/70">Loading</Text>
        </div>
      )}
      {counts.error > 0 && (
        <div className="rounded-lg border border-red-700/50 bg-red-500/10 p-3 text-center">
          <Text className="text-2xl font-bold text-red-400">{counts.error}</Text>
          <Text className="text-xs text-red-400/70">Errors</Text>
        </div>
      )}
    </div>
  );
}

/**
 * ModelManagementPanel - Main component for AI model management
 */
export default function ModelManagementPanel({ className }: ModelManagementPanelProps) {
  const { models, vramStats, isLoading, isRefetching, error } = useModelZooStatusQuery({
    refetchInterval: 10000,
  });

  // Group models by category
  const modelsByCategory = useMemo(() => {
    const grouped: Record<string, ModelStatusResponse[]> = {};
    for (const model of models) {
      const category = model.category || 'Other';
      if (!grouped[category]) {
        grouped[category] = [];
      }
      grouped[category].push(model);
    }

    // Sort categories and put "Other" at the end
    const sortedCategories = Object.keys(grouped).sort((a, b) => {
      if (a === 'Other') return 1;
      if (b === 'Other') return -1;
      return a.localeCompare(b);
    });

    return sortedCategories.map((category) => ({
      category,
      models: grouped[category],
    }));
  }, [models]);

  // Loading state
  if (isLoading && models.length === 0) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid="model-management-panel"
      >
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-[#76B900]" />
          <Text className="ml-3 text-gray-400">Loading model status...</Text>
        </div>
      </Card>
    );
  }

  // Error state
  if (error) {
    return (
      <Card
        className={clsx('border-red-800 bg-red-900/20 shadow-lg', className)}
        data-testid="model-management-panel"
      >
        <div data-testid="error-message" className="flex items-center gap-3 p-4">
          <AlertCircle className="h-6 w-6 text-red-400" />
          <div>
            <Text className="font-medium text-red-400">Error loading models</Text>
            <Text className="text-sm text-red-300/70">{error.message}</Text>
          </div>
        </div>
      </Card>
    );
  }

  // Empty state
  if (models.length === 0) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid="model-management-panel"
      >
        <div className="flex flex-col items-center justify-center py-12">
          <Boxes className="h-12 w-12 text-gray-600" />
          <Text className="mt-3 text-gray-400">No models available</Text>
        </div>
      </Card>
    );
  }

  return (
    <div
      className={clsx('space-y-6', className)}
      data-testid="model-management-panel"
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Boxes className="h-6 w-6 text-[#76B900]" />
          <Title className="text-white" role="heading">
            Model Management
          </Title>
          {isRefetching && (
            <div data-testid="refetch-indicator">
              <RefreshCw className="h-4 w-4 animate-spin text-gray-400" />
            </div>
          )}
        </div>
      </div>

      {/* VRAM Usage Section */}
      <div data-testid="vram-usage-section">
        {vramStats && (
          <VRAMUsageCard
            budgetMb={vramStats.budgetMb}
            usedMb={vramStats.usedMb}
            availableMb={vramStats.availableMb}
            usagePercent={vramStats.usagePercent}
            isLoading={isLoading}
          />
        )}
      </div>

      {/* Model Status Summary */}
      <ModelStatusSummary models={models} />

      {/* Model Cards Grid by Category */}
      <div data-testid="model-cards-grid" className="space-y-6">
        {modelsByCategory.map(({ category, models: categoryModels }) => (
          <CategorySection
            key={category}
            category={category}
            models={categoryModels}
          />
        ))}
      </div>
    </div>
  );
}
