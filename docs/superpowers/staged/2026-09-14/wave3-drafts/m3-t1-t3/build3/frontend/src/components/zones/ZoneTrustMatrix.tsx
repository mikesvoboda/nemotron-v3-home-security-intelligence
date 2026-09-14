/**
 * ZoneTrustMatrix Component
 *
 * Displays a grid/matrix view of trust levels between zones and household members/vehicles.
 * Part of the Zone Intelligence System (NEM-3192).
 *
 * Features:
 * - Grid display with zones as rows and household members/vehicles as columns
 * - Color-coded trust levels: FULL (green), PARTIAL (yellow), MONITOR (orange), NONE (gray)
 * - Hover tooltip showing access schedule details
 * - Click to edit trust level
 * - Filter by zone type or member
 *
 * @module components/zones/ZoneTrustMatrix
 */

import { Car, Check, Clock, Crown, Filter, User, X } from 'lucide-react';
import { useState, useCallback } from 'react';

import useZoneTrustMatrix, {
  fetchZoneHouseholdConfig,
  useUpdateMemberTrust,
  useUpdateVehicleTrust,
  type TrustLevelResult,
  type TrustMatrixCell,
  type TrustMatrixFilters,
  type ZoneHouseholdConfig,
} from '../../hooks/useZoneTrustMatrix';
import Tooltip from '../common/Tooltip';

import type { HouseholdMember, RegisteredVehicle } from '../../hooks/useHouseholdApi';
import type { Zone, ZoneType } from '../../types/generated';

// ============================================================================
// Type Definitions
// ============================================================================

/**
 * View mode for the matrix - either members or vehicles
 */
export type MatrixViewMode = 'members' | 'vehicles';

/**
 * Props for the ZoneTrustMatrix component.
 */
export interface ZoneTrustMatrixProps {
  /** Zones to display as rows */
  zones: Zone[];
  /** Optional class name for styling */
  className?: string;
  /** Initial view mode (default: 'members') */
  initialViewMode?: MatrixViewMode;
  /** Callback when trust level is updated */
  onTrustUpdated?: (zoneId: string, entityId: number, entityType: 'member' | 'vehicle') => void;
  /** Whether the component is in read-only mode */
  readOnly?: boolean;
}

/**
 * Trust level display configuration
 */
interface TrustLevelConfig {
  label: string;
  bgColor: string;
  textColor: string;
  borderColor: string;
  hoverColor: string;
  icon?: React.ReactNode;
}

// ============================================================================
// Constants
// ============================================================================

/**
 * Trust level display configurations with color coding
 */
const TRUST_LEVEL_CONFIGS: Record<TrustLevelResult, TrustLevelConfig> = {
  full: {
    label: 'Full',
    bgColor: 'bg-green-500/20',
    textColor: 'text-green-400',
    borderColor: 'border-green-500/50',
    hoverColor: 'hover:bg-green-500/30',
    icon: <Crown className="h-3 w-3" />,
  },
  partial: {
    label: 'Partial',
    bgColor: 'bg-yellow-500/20',
    textColor: 'text-yellow-400',
    borderColor: 'border-yellow-500/50',
    hoverColor: 'hover:bg-yellow-500/30',
    icon: <Check className="h-3 w-3" />,
  },
  monitor: {
    label: 'Monitor',
    bgColor: 'bg-orange-500/20',
    textColor: 'text-orange-400',
    borderColor: 'border-orange-500/50',
    hoverColor: 'hover:bg-orange-500/30',
    icon: <Clock className="h-3 w-3" />,
  },
  none: {
    label: 'None',
    bgColor: 'bg-gray-500/20',
    textColor: 'text-gray-400',
    borderColor: 'border-gray-500/50',
    hoverColor: 'hover:bg-gray-500/30',
  },
};

/**
 * Available zone types for filtering
 */
const ZONE_TYPES: { value: ZoneType; label: string }[] = [
  { value: 'entry_point', label: 'Entry Point' },
  { value: 'driveway', label: 'Driveway' },
  { value: 'sidewalk', label: 'Sidewalk' },
  { value: 'yard', label: 'Yard' },
  { value: 'other', label: 'Other' },
];

/**
 * Trust level options for editing
 */
const TRUST_LEVELS: TrustLevelResult[] = ['full', 'partial', 'monitor', 'none'];

// ============================================================================
// Sub-components
// ============================================================================

/**
 * Trust level cell in the matrix
 */
interface TrustCellProps {
  cell: TrustMatrixCell;
  onClick?: () => void;
  isEditing: boolean;
  readOnly: boolean;
}

function TrustCell({ cell, onClick, isEditing, readOnly }: TrustCellProps) {
  const config = TRUST_LEVEL_CONFIGS[cell.trustLevel];

  // Build tooltip content
  const tooltipContent = (
    <div className="space-y-1">
      <div className="font-medium">{config.label} Trust</div>
      <div className="text-xs text-gray-400">{cell.reason}</div>
      {cell.isOwner && (
        <div className="flex items-center gap-1 text-xs text-green-400">
          <Crown className="h-3 w-3" />
          Zone Owner
        </div>
      )}
      {cell.accessSchedules.length > 0 && (
        <div className="mt-2 space-y-1">
          <div className="text-xs font-medium text-gray-300">Access Schedules:</div>
          {cell.accessSchedules.map((schedule, idx) => (
            <div key={idx} className="text-xs text-gray-400">
              {schedule.description || schedule.cron_expression}
            </div>
          ))}
        </div>
      )}
      {!readOnly && <div className="mt-2 text-xs text-gray-500">Click to edit</div>}
    </div>
  );

  return (
    <Tooltip content={tooltipContent} position="top">
      <button
        type="button"
        onClick={readOnly ? undefined : onClick}
        disabled={readOnly}
        className={`flex h-10 w-10 items-center justify-center rounded-lg border transition-all ${config.bgColor} ${config.borderColor} ${!readOnly ? config.hoverColor : ''} ${isEditing ? 'ring-2 ring-primary ring-offset-2 ring-offset-gray-900' : ''} ${readOnly ? 'cursor-default' : 'cursor-pointer'} `}
        aria-label={`${cell.entityName} has ${config.label} trust in ${cell.zoneName}`}
      >
        <span className={`text-xs font-medium ${config.textColor}`}>
          {config.icon || config.label.charAt(0)}
        </span>
      </button>
    </Tooltip>
  );
}

/**
 * Trust level editor dropdown
 */
interface TrustEditorProps {
  currentLevel: TrustLevelResult;
  entityType: 'member' | 'vehicle';
  onSelect: (level: TrustLevelResult) => void | Promise<void>;
  onClose: () => void;
  isLoading: boolean;
}

function TrustEditor({ currentLevel, entityType, onSelect, onClose, isLoading }: TrustEditorProps) {
  // Vehicles only support partial and none
  const availableLevels =
    entityType === 'vehicle'
      ? TRUST_LEVELS.filter((l) => l === 'partial' || l === 'none')
      : TRUST_LEVELS;

  return (
    <div className="absolute z-50 mt-1 rounded-lg border border-gray-700 bg-gray-800 p-2 shadow-lg">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-medium text-gray-300">Select Trust Level</span>
        <button
          type="button"
          onClick={onClose}
          className="rounded p-1 text-gray-400 hover:bg-gray-700 hover:text-gray-200"
          aria-label="Close editor"
        >
          <X className="h-3 w-3" />
        </button>
      </div>
      <div className="flex flex-col gap-1">
        {availableLevels.map((level) => {
          const config = TRUST_LEVEL_CONFIGS[level];
          const isSelected = level === currentLevel;
          return (
            <button
              key={level}
              type="button"
              onClick={() => void onSelect(level)}
              disabled={isLoading}
              className={`flex items-center gap-2 rounded px-3 py-1.5 text-left text-sm transition-colors ${isSelected ? `${config.bgColor} ${config.textColor}` : 'text-gray-300 hover:bg-gray-700'} ${isLoading ? 'cursor-wait opacity-50' : ''} `}
            >
              {config.icon && <span className={config.textColor}>{config.icon}</span>}
              {config.label}
              {isSelected && <Check className="ml-auto h-3 w-3" />}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Filter panel for the matrix
 */
interface FilterPanelProps {
  filters: TrustMatrixFilters;
  onFiltersChange: (filters: TrustMatrixFilters) => void;
  members: HouseholdMember[];
  vehicles: RegisteredVehicle[];
  viewMode: MatrixViewMode;
}

function FilterPanel({ filters, onFiltersChange, members, vehicles, viewMode }: FilterPanelProps) {
  const [isOpen, setIsOpen] = useState(false);

  const hasFilters =
    filters.zoneType ||
    (filters.memberIds?.length ?? 0) > 0 ||
    (filters.vehicleIds?.length ?? 0) > 0 ||
    filters.trustLevel;

  const clearFilters = () => {
    onFiltersChange({});
  };

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors ${
          hasFilters
            ? 'border-primary bg-primary/10 text-primary'
            : 'border-gray-700 bg-gray-800 text-gray-300 hover:bg-gray-700'
        } `}
      >
        <Filter className="h-4 w-4" />
        Filters
        {hasFilters && (
          <span className="rounded-full bg-primary px-1.5 text-xs text-white">
            {
              [
                filters.zoneType,
                filters.trustLevel,
                ...(filters.memberIds ?? []),
                ...(filters.vehicleIds ?? []),
              ].filter(Boolean).length
            }
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 z-50 mt-2 w-72 rounded-lg border border-gray-700 bg-gray-800 p-4 shadow-lg">
          <div className="mb-4 flex items-center justify-between">
            <span className="font-medium text-gray-200">Filters</span>
            {hasFilters && (
              <button
                type="button"
                onClick={clearFilters}
                className="text-xs text-gray-400 hover:text-gray-200"
              >
                Clear all
              </button>
            )}
          </div>

          {/* Zone Type Filter */}
          <div className="mb-4">
            <label htmlFor="filter-zone-type" className="mb-1 block text-xs text-gray-400">
              Zone Type
            </label>
            <select
              id="filter-zone-type"
              value={filters.zoneType ?? ''}
              onChange={(e) =>
                onFiltersChange({
                  ...filters,
                  zoneType: (e.target.value as ZoneType) || undefined,
                })
              }
              className="w-full rounded border border-gray-600 bg-gray-700 px-2 py-1.5 text-sm text-gray-200"
            >
              <option value="">All Types</option>
              {ZONE_TYPES.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
          </div>

          {/* Trust Level Filter */}
          <div className="mb-4">
            <label htmlFor="filter-trust-level" className="mb-1 block text-xs text-gray-400">
              Trust Level
            </label>
            <select
              id="filter-trust-level"
              value={filters.trustLevel ?? ''}
              onChange={(e) =>
                onFiltersChange({
                  ...filters,
                  trustLevel: (e.target.value as TrustLevelResult) || undefined,
                })
              }
              className="w-full rounded border border-gray-600 bg-gray-700 px-2 py-1.5 text-sm text-gray-200"
            >
              <option value="">All Levels</option>
              {TRUST_LEVELS.map((level) => (
                <option key={level} value={level}>
                  {TRUST_LEVEL_CONFIGS[level].label}
                </option>
              ))}
            </select>
          </div>

          {/* Member/Vehicle Filter */}
          {viewMode === 'members' && members.length > 0 && (
            <div role="group" aria-labelledby="filter-members-label">
              <span id="filter-members-label" className="mb-1 block text-xs text-gray-400">
                Members
              </span>
              <div className="max-h-32 space-y-1 overflow-y-auto">
                {members.map((member) => {
                  const isSelected = filters.memberIds?.includes(member.id);
                  return (
                    <label
                      key={member.id}
                      className="flex cursor-pointer items-center gap-2 text-sm"
                    >
                      <input
                        type="checkbox"
                        checked={isSelected ?? false}
                        onChange={(e) => {
                          const newIds = e.target.checked
                            ? [...(filters.memberIds ?? []), member.id]
                            : (filters.memberIds ?? []).filter((id) => id !== member.id);
                          onFiltersChange({
                            ...filters,
                            memberIds: newIds.length > 0 ? newIds : undefined,
                          });
                        }}
                        className="rounded border-gray-600 bg-gray-700"
                      />
                      <span className="text-gray-300">{member.name}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          )}

          {viewMode === 'vehicles' && vehicles.length > 0 && (
            <div role="group" aria-labelledby="filter-vehicles-label">
              <span id="filter-vehicles-label" className="mb-1 block text-xs text-gray-400">
                Vehicles
              </span>
              <div className="max-h-32 space-y-1 overflow-y-auto">
                {vehicles.map((vehicle) => {
                  const isSelected = filters.vehicleIds?.includes(vehicle.id);
                  return (
                    <label
                      key={vehicle.id}
                      className="flex cursor-pointer items-center gap-2 text-sm"
                    >
                      <input
                        type="checkbox"
                        checked={isSelected ?? false}
                        onChange={(e) => {
                          const newIds = e.target.checked
                            ? [...(filters.vehicleIds ?? []), vehicle.id]
                            : (filters.vehicleIds ?? []).filter((id) => id !== vehicle.id);
                          onFiltersChange({
                            ...filters,
                            vehicleIds: newIds.length > 0 ? newIds : undefined,
                          });
                        }}
                        className="rounded border-gray-600 bg-gray-700"
                      />
                      <span className="text-gray-300">{vehicle.description}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          )}

          <button
            type="button"
            onClick={() => setIsOpen(false)}
            className="mt-4 w-full rounded bg-gray-700 py-1.5 text-sm text-gray-200 hover:bg-gray-600"
          >
            Done
          </button>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * ZoneTrustMatrix displays a grid of trust levels between zones and household members/vehicles.
 */
export default function ZoneTrustMatrix({
  zones,
  className = '',
  initialViewMode = 'members',
  onTrustUpdated,
  readOnly = false,
}: ZoneTrustMatrixProps) {
  const [viewMode, setViewMode] = useState<MatrixViewMode>(initialViewMode);
  const [filters, setFilters] = useState<TrustMatrixFilters>({});
  const [editingCell, setEditingCell] = useState<{ zoneId: string; entityId: number } | null>(null);
  const [zoneConfigs, setZoneConfigs] = useState<Map<string, ZoneHouseholdConfig | null>>(
    new Map()
  );

  // Fetch matrix data
  const {
    zones: filteredZones,
    members,
    vehicles,
    cells,
    isLoading,
    error,
  } = useZoneTrustMatrix(zones, filters);

  // Mutations for updating trust
  const { updateMemberTrust, isLoading: isMemberUpdating } = useUpdateMemberTrust();
  const { updateVehicleTrust, isLoading: isVehicleUpdating } = useUpdateVehicleTrust();
  const isUpdating = isMemberUpdating || isVehicleUpdating;

  // Get current entity columns based on view mode
  const entityColumns = viewMode === 'members' ? members : vehicles;

  // Handle cell click for editing
  const handleCellClick = useCallback(
    (zoneId: string, entityId: number) => {
      if (readOnly) return;
      setEditingCell({ zoneId, entityId });

      // Fetch current config for the zone if not already cached
      if (!zoneConfigs.has(zoneId)) {
        void fetchZoneHouseholdConfig(zoneId).then((config) => {
          setZoneConfigs((prev) => new Map(prev).set(zoneId, config));
        });
      }
    },
    [readOnly, zoneConfigs]
  );

  // Handle trust level selection
  const handleTrustSelect = useCallback(
    async (level: TrustLevelResult) => {
      if (!editingCell) return;

      const { zoneId, entityId } = editingCell;
      const currentConfig = zoneConfigs.get(zoneId) ?? null;

      try {
        if (viewMode === 'members') {
          await updateMemberTrust(zoneId, entityId, level, currentConfig);
        } else {
          await updateVehicleTrust(zoneId, entityId, level, currentConfig);
        }

        // Update cached config
        const newConfig = await fetchZoneHouseholdConfig(zoneId);
        setZoneConfigs((prev) => new Map(prev).set(zoneId, newConfig));

        onTrustUpdated?.(zoneId, entityId, viewMode === 'members' ? 'member' : 'vehicle');
      } catch (err) {
        console.error('Failed to update trust level:', err);
      }

      setEditingCell(null);
    },
    [editingCell, viewMode, zoneConfigs, updateMemberTrust, updateVehicleTrust, onTrustUpdated]
  );

  // Close editor
  const handleCloseEditor = useCallback(() => {
    setEditingCell(null);
  }, []);

  // Loading state
  if (isLoading) {
    return (
      <div className={`rounded-lg border border-gray-700 bg-gray-800/50 p-6 ${className}`}>
        <div className="flex items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-gray-600 border-t-primary" />
          <span className="ml-3 text-gray-400">Loading trust matrix...</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className={`rounded-lg border border-red-500/50 bg-red-500/10 p-6 ${className}`}>
        <div className="text-center text-red-400">Failed to load trust matrix: {error.message}</div>
      </div>
    );
  }

  // Empty state
  if (filteredZones.length === 0) {
    return (
      <div className={`rounded-lg border border-gray-700 bg-gray-800/50 p-6 ${className}`}>
        <div className="text-center text-gray-400">
          {zones.length === 0
            ? 'No zones defined. Create zones to configure trust levels.'
            : 'No zones match the current filters.'}
        </div>
      </div>
    );
  }

  if (entityColumns.length === 0) {
    return (
      <div className={`rounded-lg border border-gray-700 bg-gray-800/50 p-6 ${className}`}>
        <div className="text-center text-gray-400">
          {viewMode === 'members'
            ? 'No household members found. Add members to configure trust levels.'
            : 'No vehicles registered. Add vehicles to configure trust levels.'}
        </div>
      </div>
    );
  }

  return (
    <div className={`rounded-lg border border-gray-700 bg-gray-800/50 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-700 p-4">
        <h3 className="text-lg font-semibold text-gray-200">Zone Trust Matrix</h3>
        <div className="flex items-center gap-3">
          {/* View Mode Toggle */}
          <div className="flex rounded-lg border border-gray-600 p-0.5">
            <button
              type="button"
              onClick={() => setViewMode('members')}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm transition-colors ${
                viewMode === 'members'
                  ? 'bg-primary text-white'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              <User className="h-4 w-4" />
              Members
            </button>
            <button
              type="button"
              onClick={() => setViewMode('vehicles')}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm transition-colors ${
                viewMode === 'vehicles'
                  ? 'bg-primary text-white'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              <Car className="h-4 w-4" />
              Vehicles
            </button>
          </div>

          {/* Filters */}
          <FilterPanel
            filters={filters}
            onFiltersChange={setFilters}
            members={members}
            vehicles={vehicles}
            viewMode={viewMode}
          />
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 border-b border-gray-700 px-4 py-2">
        <span className="text-xs text-gray-400">Legend:</span>
        {TRUST_LEVELS.map((level) => {
          const config = TRUST_LEVEL_CONFIGS[level];
          return (
            <div key={level} className="flex items-center gap-1.5">
              <div className={`h-3 w-3 rounded ${config.bgColor} ${config.borderColor} border`} />
              <span className={`text-xs ${config.textColor}`}>{config.label}</span>
            </div>
          );
        })}
      </div>

      {/* Matrix Grid */}
      <div className="overflow-x-auto p-4">
        <table className="w-full border-separate border-spacing-1">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 bg-gray-800 px-2 py-2 text-left text-sm font-medium text-gray-300">
                Zone
              </th>
              {entityColumns.map((entity) => (
                <th
                  key={'id' in entity ? entity.id : -1}
                  className="min-w-[60px] px-2 py-2 text-center text-xs font-medium text-gray-400"
                >
                  <div className="flex flex-col items-center gap-1">
                    {viewMode === 'members' ? (
                      <User className="h-4 w-4 text-gray-500" />
                    ) : (
                      <Car className="h-4 w-4 text-gray-500" />
                    )}
                    <span className="max-w-[80px] truncate">
                      {'name' in entity ? entity.name : entity.description}
                    </span>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filteredZones.map((zone) => (
              <tr key={zone.id}>
                <td className="sticky left-0 z-10 bg-gray-800 px-2 py-2">
                  <div className="flex items-center gap-2">
                    <div className="h-3 w-3 rounded" style={{ backgroundColor: zone.color }} />
                    <span className="text-sm text-gray-200">{zone.name}</span>
                  </div>
                </td>
                {entityColumns.map((entity) => {
                  const entityId = 'id' in entity ? entity.id : -1;
                  const cellKey = viewMode === 'members' ? entityId : -entityId;
                  const cell = cells.get(zone.id)?.get(cellKey);
                  const isEditing =
                    editingCell?.zoneId === zone.id && editingCell?.entityId === entityId;

                  if (!cell) return <td key={entityId} className="px-2 py-2" />;

                  return (
                    <td key={entityId} className="relative px-2 py-2 text-center">
                      <TrustCell
                        cell={cell}
                        onClick={() => handleCellClick(zone.id, entityId)}
                        isEditing={isEditing}
                        readOnly={readOnly}
                      />
                      {isEditing && (
                        <TrustEditor
                          currentLevel={cell.trustLevel}
                          entityType={cell.entityType}
                          onSelect={handleTrustSelect}
                          onClose={handleCloseEditor}
                          isLoading={isUpdating}
                        />
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
