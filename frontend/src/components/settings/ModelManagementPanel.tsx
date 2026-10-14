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
import { useModels, useVRAMSummary } from '../../hooks/useModelZoo';

import type { ModelStatus } from '../../services/modelZooApi';

// [r130f] F-125/F-129: this panel's feed used to run through the legacy
// useModelZooStatusQuery -> fetchModelZooStatus -> api.ModelRegistryResponse /
// ModelStatusResponse chain, which models GET /api/system/models as the OLD
// `system.get_models` shape ({ vram_budget_mb, loading_strategy, models with
// display_name/vram_mb/status }). That shape is fiction on the live stack:
// model_management.py registers router prefix "/api/system/models" and is
// mounted (main.py:1648) BEFORE system.py's "/api/system" router (main.py:1663),
// so the FIRST-registered model_management.list_models answers the GET and FastAPI
// strips every field not on its response_model=ModelListResponse ({ models,
// service_status }) with ModelStatus items (name, category, estimated_vram_mb,
// enabled, service, gpu_id, runtime). backend/tests/unit/api/routes/
// test_system_models.py:7-9 records the shadowing; openapi.json still documents
// the shadowed system.get_models schema (a doc-generator artifact of the two
// routes sharing a path). Reading the model off the truth shape
// (config[status] with status undefined) is what threw "Cannot destructure
// property 'icon' of undefined" and blanked the whole tab. This now reuses the
// same live shape and hooks its sibling ModelZooPanel already uses.

/**
 * Props for ModelManagementPanel component
 */
export interface ModelManagementPanelProps {
  /** Additional CSS classes */
  className?: string;
}

/**
 * The states the indicator can draw. [r130f]: not a backend contract — the
 * live ModelStatus carries no status enum (see the note above the imports);
 * this component DERIVES the state from `enabled` + `runtime`.
 *
 * `unknown` is the state the deleted enum could not express: the endpoint sends
 * `runtime: null` when the enrichment service behind a model is down, which the
 * old code could only render as 'unloaded' — a claim about GPU memory the
 * backend never made. The old `loading` and `error` keys are gone: they were
 * unreachable even before this change, because this panel has no load/unload
 * action (that is the sibling ModelZooPanel's) and the endpoint never sent
 * either value. A value this file has never heard of lands on the indicator's
 * fallback instead of a crash.
 */
export type ModelDisplayStatus = 'loaded' | 'unloaded' | 'disabled' | 'unknown';

/**
 * Status indicator component.
 *
 * [r130f] F-125/F-129: `config[status]` used to be indexed and destructured
 * unguarded, so any status value outside the five keys (measured live: the key
 * was `undefined`, because the endpoint sends no status field at all) threw at
 * first render of any model card and the app-level boundary blanked the whole
 * /settings/ai-models tab. Two changes close it: the state is derived from
 * fields that exist, and the lookup has a fallback, so a value the map has
 * never heard of renders a neutral pill instead of taking a settings tab down.
 */
function StatusIndicator({ status }: { status: string }) {
  const FALLBACK = {
    icon: AlertCircle,
    color: 'text-gray-400',
    bgColor: 'bg-gray-500/20',
    label: 'Unknown',
  };
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
    disabled: {
      icon: XCircle,
      color: 'text-yellow-500',
      bgColor: 'bg-yellow-500/20',
      label: 'Disabled',
    },
    unknown: {
      icon: AlertCircle,
      color: 'text-gray-400',
      bgColor: 'bg-gray-500/20',
      label: 'No data',
    },
  };

  const { icon: Icon, color, bgColor, label } = config[status as keyof typeof config] ?? FALLBACK;

  return (
    <div
      data-testid={`status-${status}`}
      aria-label={`Status: ${label}`}
      className={clsx('flex items-center gap-1 rounded-full px-2 py-0.5', bgColor)}
    >
      {/* No spinner state: this panel has no load/unload action, so no model
          can be mid-load here. The spin that used to hang off status ===
          'loading' was unreachable — that value is not derivable and the
          endpoint never sent it. */}
      <Icon className={clsx('h-3 w-3', color)} />
      <span className={clsx('text-xs font-medium', color)}>{label}</span>
    </div>
  );
}

/**
 * Derive the indicator state from the two fields the endpoint actually sends.
 *
 * `enabled` is registry config and `runtime.loaded` is live GPU state, so the
 * pair answers the same question the deleted `status` string claimed to.
 * Precedence: a model disabled in config is 'disabled' whatever the runtime
 * says, since the panel greys it out either way; a missing runtime is 'unknown'
 * rather than 'unloaded', because "not resident" and "we were not told" are
 * different claims; a live runtime answers from `loaded`.
 */
export function modelDisplayStatus(model: ModelStatus): ModelDisplayStatus {
  if (!model.enabled) return 'disabled';
  if (model.runtime === null) return 'unknown';
  return model.runtime.loaded ? 'loaded' : 'unloaded';
}

/**
 * Individual model card component
 */
function ModelCard({ model }: { model: ModelStatus }) {
  const status = modelDisplayStatus(model);
  const actualVram = model.runtime?.actual_vram_mb ?? null;

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
        <Text className="truncate text-sm font-medium text-white" title={model.name}>
          {model.name}
        </Text>
        <StatusIndicator status={status} />
      </div>

      {/* Category Badge */}
      <div className="mb-2">
        <Badge color="gray" size="xs">
          {model.category}
        </Badge>
      </div>

      {/* Stats Row */}
      <div className="flex items-center justify-between text-xs text-gray-400">
        {/* VRAM — actual when resident, estimate otherwise, matching the
            sibling ModelCard the same tab mounts (ModelCard.tsx:181-187). The
            registry only ever has an estimate, so an unloaded model must not
            read as a measured figure. */}
        <div className="flex items-center gap-1">
          <MemoryStick className="h-3 w-3" />
          {actualVram ? (
            <span>
              <span className="text-white">{actualVram} MB</span>
              <span className="text-gray-500"> / {model.estimated_vram_mb} MB</span>
            </span>
          ) : (
            <span>~{model.estimated_vram_mb} MB</span>
          )}
        </div>

        {/* Load Count */}
        {model.runtime && model.runtime.load_count > 0 && (
          <div className="flex items-center gap-1">
            <RefreshCw className="h-3 w-3" />
            <span>{model.runtime.load_count} loads</span>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Category section component
 */
function CategorySection({ category, models }: { category: string; models: ModelStatus[] }) {
  const loadedCount = models.filter((m) => modelDisplayStatus(m) === 'loaded').length;

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
function ModelStatusSummary({ models }: { models: ModelStatus[] }) {
  // [r130f] The loading/error tiles are gone rather than kept at a permanent 0:
  // the derived state above can only ever answer loaded/unloaded/disabled,
  // because nothing on the wire reports an in-flight or failed load (the panel
  // has no load/unload action — that is ModelZooPanel's). Two tiles that could
  // only ever render zero were a second fiction on top of the first.
  const counts = useMemo(() => {
    const loaded = models.filter((m) => modelDisplayStatus(m) === 'loaded').length;
    const unloaded = models.filter((m) => modelDisplayStatus(m) === 'unloaded').length;
    const disabled = models.filter((m) => modelDisplayStatus(m) === 'disabled').length;
    const unknown = models.filter((m) => modelDisplayStatus(m) === 'unknown').length;
    return { loaded, unloaded, disabled, unknown, total: models.length };
  }, [models]);

  return (
    <div
      data-testid="model-status-summary"
      className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-5"
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
      {/* Rendered only when non-zero, unlike the four above: this one counts the
          models whose enrichment service reported no runtime at all, so it is a
          warning rather than a standing column. The four tiles always sum to
          Total — the derived state is exhaustive, which is the property the
          golden spec asserts against the live body. */}
      {counts.unknown > 0 && (
        <div className="rounded-lg border border-gray-700 bg-gray-800/30 p-3 text-center">
          <Text className="text-2xl font-bold text-gray-400">{counts.unknown}</Text>
          <Text className="text-xs text-gray-500">No data</Text>
        </div>
      )}
    </div>
  );
}

/**
 * ModelManagementPanel - Main component for AI model management
 */
export default function ModelManagementPanel({ className }: ModelManagementPanelProps) {
  // Two feeds, both already used by the sibling ModelZooPanel on this same tab:
  // the registry/runtime list, and the per-GPU VRAM summary. The old single
  // feed asked one endpoint for both and the endpoint's response model kept
  // neither of the vram_* fields this card rendered, so the VRAM half silently
  // read undefined — a second drift the same fix has to close.
  const { models, isLoading, isRefetching, error } = useModels({ refetchInterval: 10000 });
  const vram = useVRAMSummary({ refetchInterval: 10000 });
  const totals = vram.data?.totals;
  const usagePercent =
    totals && totals.budget_mb > 0 ? (totals.used_mb / totals.budget_mb) * 100 : 0;

  // Group models by category
  const modelsByCategory = useMemo(() => {
    const grouped: Record<string, ModelStatus[]> = {};
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
    <div className={clsx('space-y-6', className)} data-testid="model-management-panel">
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
        {totals ? (
          <VRAMUsageCard
            budgetMb={totals.budget_mb}
            usedMb={totals.used_mb}
            availableMb={totals.available_mb}
            usagePercent={usagePercent}
            isLoading={vram.isLoading}
          />
        ) : (
          /* [r130f] The section used to render an empty div whenever the VRAM
              feed was missing, which read as "no VRAM to report" rather than
              "this query failed". Its own error is now named. */
          <div data-testid="vram-usage-unavailable" className="flex items-center gap-3 p-4">
            <AlertCircle className="h-5 w-5 text-yellow-400" />
            <Text className="text-sm text-gray-400">
              {vram.error
                ? `VRAM summary unavailable: ${vram.error.message}`
                : 'Loading VRAM summary...'}
            </Text>
          </div>
        )}
      </div>

      {/* Model Status Summary */}
      <ModelStatusSummary models={models} />

      {/* Model Cards Grid by Category */}
      <div data-testid="model-cards-grid" className="space-y-6">
        {modelsByCategory.map(({ category, models: categoryModels }) => (
          <CategorySection key={category} category={category} models={categoryModels} />
        ))}
      </div>
    </div>
  );
}
