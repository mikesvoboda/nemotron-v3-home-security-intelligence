import { clsx } from 'clsx';
import { Edit2, Eye, EyeOff, Trash2 } from 'lucide-react';

import type { Zone, ZoneType } from '../../types/generated';

export interface ZoneListProps {
  /** List of zones to display */
  zones: Zone[];
  /** Currently selected zone ID */
  selectedZoneId?: string | null;
  /** Callback when a zone is selected */
  onSelect?: (zoneId: string) => void;
  /** Callback when edit button is clicked */
  onEdit?: (zone: Zone) => void;
  /** Callback when delete button is clicked */
  onDelete?: (zone: Zone) => void;
  /** Callback when toggle enabled is clicked */
  onToggleEnabled?: (zone: Zone) => void;
  /** Whether zone operations are disabled */
  disabled?: boolean;
}

/** Zone type labels and colors */
const ZONE_TYPE_INFO: Record<ZoneType, { label: string; bgColor: string }> = {
  entry_point: { label: 'Entry Point', bgColor: 'bg-red-500/20 text-red-400' },
  driveway: { label: 'Driveway', bgColor: 'bg-amber-500/20 text-amber-400' },
  sidewalk: { label: 'Sidewalk', bgColor: 'bg-blue-500/20 text-blue-400' },
  yard: { label: 'Yard', bgColor: 'bg-green-500/20 text-green-400' },
  other: { label: 'Other', bgColor: 'bg-gray-500/20 text-gray-400' },
};

/**
 * ZoneList component for displaying and managing zones.
 *
 * Features:
 * - Displays zones in a list with color indicators
 * - Shows zone type badges
 * - Edit and delete buttons
 * - Enable/disable toggle
 * - Selection highlighting
 */
export default function ZoneList({
  zones,
  selectedZoneId,
  onSelect,
  onEdit,
  onDelete,
  onToggleEnabled,
  disabled = false,
}: ZoneListProps) {
  if (zones.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-center">
        <div className="rounded-full bg-gray-800 p-3">
          <svg
            className="h-6 w-6 text-gray-500"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"
            />
          </svg>
        </div>
        <p className="mt-2 text-sm text-text-secondary">No zones defined</p>
        <p className="mt-1 text-xs text-gray-500">Draw a zone on the camera view to get started</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {zones.map((zone) => {
        const isSelected = zone.id === selectedZoneId;
        const typeInfo = ZONE_TYPE_INFO[zone.zone_type] || ZONE_TYPE_INFO.other;

        return (
          <div
            key={zone.id}
            role="button"
            tabIndex={disabled ? -1 : 0}
            aria-pressed={isSelected}
            aria-disabled={disabled}
            className={clsx(
              'flex items-center gap-3 rounded-lg border p-3 transition-all',
              isSelected
                ? 'border-primary bg-primary/10'
                : 'border-gray-700 bg-gray-800/50 hover:border-gray-600',
              !zone.enabled && 'opacity-50',
              !disabled && 'cursor-pointer'
            )}
            onClick={() => !disabled && onSelect?.(zone.id)}
            onKeyDown={(e) => {
              if (!disabled && (e.key === 'Enter' || e.key === ' ')) {
                e.preventDefault();
                onSelect?.(zone.id);
              }
            }}
          >
            {/* Color indicator */}
            <div className="h-8 w-8 shrink-0 rounded" style={{ backgroundColor: zone.color }} />

            {/* Zone info */}
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="truncate font-medium text-text-primary">{zone.name}</span>
                {!zone.enabled && (
                  <span className="rounded bg-gray-700 px-1.5 py-0.5 text-xs text-gray-400">
                    Disabled
                  </span>
                )}
              </div>
              <div className="mt-0.5 flex items-center gap-2">
                <span className={clsx('rounded px-1.5 py-0.5 text-xs', typeInfo.bgColor)}>
                  {typeInfo.label}
                </span>
                <span className="text-xs text-gray-500">Priority: {zone.priority}</span>
              </div>
            </div>

            {/* Action buttons */}
            <div className="flex shrink-0 items-center gap-1">
              {onToggleEnabled && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onToggleEnabled(zone);
                  }}
                  disabled={disabled}
                  className={clsx(
                    'rounded p-1.5 transition-colors focus:outline-none focus:ring-2 focus:ring-primary',
                    zone.enabled
                      ? 'text-primary hover:bg-gray-700'
                      : 'text-gray-500 hover:bg-gray-700 hover:text-gray-300'
                  )}
                  title={zone.enabled ? 'Disable zone' : 'Enable zone'}
                >
                  {zone.enabled ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
                </button>
              )}
              {onEdit && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onEdit(zone);
                  }}
                  disabled={disabled}
                  className="rounded p-1.5 text-gray-400 transition-colors hover:bg-gray-700 hover:text-primary focus:outline-none focus:ring-2 focus:ring-primary"
                  title="Edit zone"
                >
                  <Edit2 className="h-4 w-4" />
                </button>
              )}
              {onDelete && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(zone);
                  }}
                  disabled={disabled}
                  className="rounded p-1.5 text-gray-400 transition-colors hover:bg-gray-700 hover:text-red-500 focus:outline-none focus:ring-2 focus:ring-red-500"
                  title="Delete zone"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
