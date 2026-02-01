/**
 * ComparisonTab - Zone comparison tab content (NEM-4714)
 *
 * Provides a comprehensive comparison view for zones with:
 * - Zone multi-select using checkboxes
 * - Metric selector (crossings, dwell_time, anomalies, occupancy)
 * - Period selector (day, week, month)
 * - ZoneComparisonTable for tabular data
 * - ZoneComparisonChart for visual comparison
 * - Loading and empty states
 *
 * Part of Phase 4B: Frontend Comparison Tab Content.
 *
 * @module components/zones/ComparisonTab
 */

import { clsx } from 'clsx';
import { Check, GitCompare, RefreshCw } from 'lucide-react';
import { memo, useCallback, useState } from 'react';

import ZoneComparisonChart from './ZoneComparisonChart';
import ZoneComparisonTable from './ZoneComparisonTable';
import {
  useZoneComparison,
  type ComparisonMetric,
  type ComparisonPeriod,
} from '../../hooks/useZoneComparison';
import Button from '../common/Button';
import EmptyState from '../common/EmptyState';
import LoadingSpinner from '../common/LoadingSpinner';

import type { Zone } from '../../types/generated';

// ============================================================================
// Types
// ============================================================================

/**
 * Props for the ComparisonTab component.
 */
export interface ComparisonTabProps {
  /** Available zones for comparison */
  zones: Zone[];
  /** Whether zones are loading */
  isLoadingZones?: boolean;
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Constants
// ============================================================================

/**
 * Available metrics for comparison.
 */
const METRIC_OPTIONS: { value: ComparisonMetric; label: string }[] = [
  { value: 'crossings', label: 'Crossings' },
  { value: 'dwell_time', label: 'Dwell Time' },
  { value: 'anomalies', label: 'Anomalies' },
  { value: 'occupancy', label: 'Occupancy' },
];

/**
 * Available periods for comparison.
 */
const PERIOD_OPTIONS: { value: ComparisonPeriod; label: string }[] = [
  { value: 'day', label: 'Today' },
  { value: 'week', label: 'This Week' },
  { value: 'month', label: 'This Month' },
];

// ============================================================================
// Subcomponents
// ============================================================================

/**
 * Zone selection item with checkbox.
 */
interface ZoneSelectItemProps {
  zone: Zone;
  isSelected: boolean;
  onToggle: (zoneId: number) => void;
}

function ZoneSelectItem({ zone, isSelected, onToggle }: ZoneSelectItemProps) {
  return (
    <label
      className={clsx(
        'flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 transition-colors',
        isSelected
          ? 'border-[#76B900] bg-[#76B900]/10'
          : 'border-gray-700 bg-gray-800/50 hover:border-gray-600'
      )}
    >
      <div
        className={clsx(
          'flex h-5 w-5 items-center justify-center rounded border transition-colors',
          isSelected ? 'border-[#76B900] bg-[#76B900]' : 'border-gray-500 bg-transparent'
        )}
      >
        {isSelected && <Check className="h-3 w-3 text-white" />}
      </div>
      <input
        type="checkbox"
        checked={isSelected}
        onChange={() => onToggle(typeof zone.id === 'string' ? parseInt(zone.id, 10) : zone.id)}
        className="sr-only"
        aria-label={`Select ${zone.name}`}
      />
      <div className="flex items-center gap-2 overflow-hidden">
        <div
          className="h-3 w-3 shrink-0 rounded-full"
          style={{ backgroundColor: zone.color }}
          aria-hidden="true"
        />
        <span className="truncate text-sm text-white">{zone.name}</span>
      </div>
    </label>
  );
}

/**
 * Metric selector button group.
 */
interface MetricSelectorProps {
  value: ComparisonMetric;
  onChange: (metric: ComparisonMetric) => void;
}

function MetricSelector({ value, onChange }: MetricSelectorProps) {
  return (
    <div className="flex flex-wrap gap-2">
      {METRIC_OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          className={clsx(
            'rounded-lg px-3 py-1.5 text-sm font-medium transition-colors',
            value === option.value
              ? 'bg-[#76B900] text-white'
              : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-200'
          )}
          data-testid={`metric-${option.value}`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

/**
 * Period selector button group.
 */
interface PeriodSelectorProps {
  value: ComparisonPeriod;
  onChange: (period: ComparisonPeriod) => void;
}

function PeriodSelector({ value, onChange }: PeriodSelectorProps) {
  return (
    <div
      className="flex rounded-lg border border-gray-700 p-0.5"
      role="group"
      aria-label="Time period selection"
    >
      {PERIOD_OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          aria-pressed={value === option.value}
          className={clsx(
            'rounded-md px-3 py-1.5 text-sm font-medium transition-all',
            value === option.value
              ? 'bg-[#76B900] text-white'
              : 'text-gray-400 hover:bg-gray-700 hover:text-gray-200'
          )}
          data-testid={`period-${option.value}`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * ComparisonTab component.
 *
 * Displays zone comparison controls and visualizations.
 *
 * @param props - Component props
 * @returns Rendered component
 */
function ComparisonTabComponent({ zones, isLoadingZones = false, className }: ComparisonTabProps) {
  // Selection state
  const [selectedZoneIds, setSelectedZoneIds] = useState<number[]>([]);
  const [metric, setMetric] = useState<ComparisonMetric>('crossings');
  const [period, setPeriod] = useState<ComparisonPeriod>('day');

  // Fetch comparison data
  const { data, isLoading, error, refetch } = useZoneComparison({
    zoneIds: selectedZoneIds,
    metric,
    period,
    enabled: selectedZoneIds.length > 0,
  });

  // Toggle zone selection
  const handleToggleZone = useCallback((zoneId: number) => {
    setSelectedZoneIds((prev) =>
      prev.includes(zoneId) ? prev.filter((id) => id !== zoneId) : [...prev, zoneId]
    );
  }, []);

  // Select all zones
  const handleSelectAll = useCallback(() => {
    const allIds = zones.map((z) => (typeof z.id === 'string' ? parseInt(z.id, 10) : z.id));
    setSelectedZoneIds(allIds);
  }, [zones]);

  // Clear all selections
  const handleClearAll = useCallback(() => {
    setSelectedZoneIds([]);
  }, []);

  const allSelected = selectedZoneIds.length === zones.length && zones.length > 0;
  const someSelected = selectedZoneIds.length > 0;

  // Loading state for zones
  if (isLoadingZones) {
    return (
      <div
        className={clsx('flex min-h-[400px] items-center justify-center', className)}
        data-testid="comparison-tab-loading-zones"
      >
        <LoadingSpinner />
      </div>
    );
  }

  // Empty state - no zones available
  if (zones.length === 0) {
    return (
      <div className={clsx('space-y-6', className)} data-testid="comparison-tab-no-zones">
        <EmptyState
          icon={GitCompare}
          title="No zones available"
          description="Create zones in the camera settings to enable comparison features."
          variant="muted"
        />
      </div>
    );
  }

  return (
    <div className={clsx('space-y-6', className)} data-testid="comparison-tab">
      {/* Controls Bar */}
      <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          {/* Left: Zone Selection */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium text-gray-300">Select Zones to Compare</h3>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={handleSelectAll}
                  disabled={allSelected}
                  className="text-xs text-[#76B900] hover:underline disabled:opacity-50"
                  data-testid="select-all-btn"
                >
                  Select All
                </button>
                <span className="text-gray-600">|</span>
                <button
                  type="button"
                  onClick={handleClearAll}
                  disabled={!someSelected}
                  className="text-xs text-gray-400 hover:underline disabled:opacity-50"
                  data-testid="clear-all-btn"
                >
                  Clear
                </button>
              </div>
            </div>
            <div className="flex flex-wrap gap-2" data-testid="zone-selection-grid">
              {zones.map((zone) => {
                const zoneIdNum = typeof zone.id === 'string' ? parseInt(zone.id, 10) : zone.id;
                return (
                  <ZoneSelectItem
                    key={zone.id}
                    zone={zone}
                    isSelected={selectedZoneIds.includes(zoneIdNum)}
                    onToggle={handleToggleZone}
                  />
                );
              })}
            </div>
          </div>

          {/* Right: Metric & Period Selectors */}
          <div className="flex flex-col gap-3 lg:items-end">
            <div className="space-y-1">
              <span className="text-xs text-gray-500">Metric</span>
              <MetricSelector value={metric} onChange={setMetric} />
            </div>
            <div className="space-y-1">
              <span className="text-xs text-gray-500">Period</span>
              <PeriodSelector value={period} onChange={setPeriod} />
            </div>
          </div>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div
          className="rounded-lg border border-red-500/30 bg-red-500/10 p-4"
          data-testid="comparison-error"
        >
          <p className="text-sm text-red-400">{error.message}</p>
          <Button
            variant="outline-primary"
            size="sm"
            onClick={() => refetch()}
            leftIcon={<RefreshCw className="h-4 w-4" />}
            className="mt-2"
          >
            Retry
          </Button>
        </div>
      )}

      {/* No Selection State */}
      {selectedZoneIds.length === 0 && !error && (
        <div
          className="flex min-h-[300px] items-center justify-center rounded-lg border border-gray-700 bg-gray-800/50 p-6"
          data-testid="comparison-no-selection"
        >
          <div className="text-center">
            <GitCompare className="mx-auto mb-4 h-12 w-12 text-gray-500" />
            <h3 className="mb-2 text-lg font-medium text-gray-300">Select Zones to Compare</h3>
            <p className="max-w-md text-sm text-gray-400">
              Choose two or more zones from the list above to see a side-by-side comparison of their
              metrics.
            </p>
          </div>
        </div>
      )}

      {/* Comparison Results */}
      {selectedZoneIds.length > 0 && !error && (
        <div className="space-y-6">
          {/* Table View */}
          <ZoneComparisonTable
            zones={data?.zones ?? []}
            metric={metric}
            isLoading={isLoading}
          />

          {/* Chart View */}
          <ZoneComparisonChart
            zones={data?.zones ?? []}
            metric={metric}
            isLoading={isLoading}
          />

          {/* Time Range Info */}
          {data && (
            <div className="text-center text-xs text-gray-500" data-testid="time-range-info">
              Showing data from {new Date(data.start_time).toLocaleDateString()} to{' '}
              {new Date(data.end_time).toLocaleDateString()}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Memoized ComparisonTab for performance.
 */
export const ComparisonTab = memo(ComparisonTabComponent);

export default ComparisonTab;
