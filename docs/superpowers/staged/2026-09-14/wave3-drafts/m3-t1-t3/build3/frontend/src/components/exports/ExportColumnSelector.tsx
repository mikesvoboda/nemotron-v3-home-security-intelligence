/**
 * ExportColumnSelector Component
 *
 * Allows users to select which columns to include in an export.
 * Supports select all, select none, and individual column toggling.
 *
 * @see NEM-3569
 */

import { Check, Columns, Info } from 'lucide-react';
import { useCallback, useMemo } from 'react';

import { EXPORT_COLUMNS } from '../../types/export';

import type { ExportColumnName } from '../../types/export';

export interface ExportColumnSelectorProps {
  /** Currently selected column names */
  selectedColumns: ExportColumnName[] | null;
  /** Callback when selection changes (null = all columns) */
  onChange: (columns: ExportColumnName[] | null) => void;
  /** Whether the selector is disabled */
  disabled?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Component for selecting export columns.
 */
export default function ExportColumnSelector({
  selectedColumns,
  onChange,
  disabled = false,
  className = '',
}: ExportColumnSelectorProps) {
  // All columns selected means null (include all)
  const allSelected = selectedColumns === null;
  const selectedSet = useMemo(
    () => new Set(selectedColumns ?? EXPORT_COLUMNS.map((c) => c.field)),
    [selectedColumns]
  );

  const handleToggleColumn = useCallback(
    (field: ExportColumnName) => {
      if (disabled) return;

      if (allSelected) {
        // If all selected, clicking one means deselect that one
        const newSelection = EXPORT_COLUMNS.map((c) => c.field).filter((f) => f !== field);
        onChange(newSelection);
      } else {
        const newSet = new Set(selectedSet);
        if (newSet.has(field)) {
          newSet.delete(field);
        } else {
          newSet.add(field);
        }

        // If all columns are now selected, return null
        if (newSet.size === EXPORT_COLUMNS.length) {
          onChange(null);
        } else {
          onChange(Array.from(newSet));
        }
      }
    },
    [allSelected, disabled, onChange, selectedSet]
  );

  const handleSelectAll = useCallback(() => {
    if (disabled) return;
    onChange(null);
  }, [disabled, onChange]);

  const handleSelectNone = useCallback(() => {
    if (disabled) return;
    // Keep at least event_id
    onChange(['event_id']);
  }, [disabled, onChange]);

  const selectedCount = allSelected ? EXPORT_COLUMNS.length : selectedSet.size;

  return (
    <div className={`space-y-3 ${className}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-medium text-gray-300">
          <Columns className="h-4 w-4" />
          <span>Export Columns</span>
          <span className="rounded-full bg-gray-700 px-2 py-0.5 text-xs text-gray-400">
            {selectedCount} of {EXPORT_COLUMNS.length}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleSelectAll}
            disabled={disabled || allSelected}
            className="text-xs text-primary hover:text-primary/80 disabled:cursor-not-allowed disabled:text-gray-500"
          >
            Select All
          </button>
          <span className="text-gray-600">|</span>
          <button
            type="button"
            onClick={handleSelectNone}
            disabled={disabled || selectedCount === 1}
            className="text-xs text-primary hover:text-primary/80 disabled:cursor-not-allowed disabled:text-gray-500"
          >
            Select None
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {EXPORT_COLUMNS.map((column) => {
          const isSelected = allSelected || selectedSet.has(column.field);
          const isRequired = column.field === 'event_id' && selectedCount === 1;

          return (
            <button
              key={column.field}
              type="button"
              onClick={() => handleToggleColumn(column.field)}
              disabled={disabled || isRequired}
              className={`group relative flex items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm transition-all ${
                isSelected
                  ? 'border-primary/50 bg-primary/10 text-white'
                  : 'border-gray-700 bg-gray-800/50 text-gray-400 hover:border-gray-600 hover:bg-gray-800'
              } ${disabled || isRequired ? 'cursor-not-allowed opacity-60' : ''}`}
              title={column.description}
            >
              <div
                className={`flex h-4 w-4 items-center justify-center rounded border ${
                  isSelected
                    ? 'border-primary bg-primary text-gray-900'
                    : 'border-gray-600 bg-gray-700/50'
                }`}
              >
                {isSelected && <Check className="h-3 w-3" strokeWidth={3} />}
              </div>
              <span className="flex-1 truncate">{column.label}</span>
              <Info className="hidden h-3 w-3 text-gray-500 group-hover:block" />
            </button>
          );
        })}
      </div>

      <p className="text-xs text-gray-500">
        Select the fields you want to include in your export. At least one column must be selected.
      </p>
    </div>
  );
}
