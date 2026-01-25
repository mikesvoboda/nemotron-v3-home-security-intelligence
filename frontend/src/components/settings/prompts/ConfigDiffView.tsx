/**
 * ConfigDiffView - Display configuration diff for a single model
 *
 * Shows the changes between current and imported configurations
 * with red/green highlighting for removals/additions.
 *
 * @see NEM-2699 - Implement prompt import/export with preview diffs
 */

import { Badge, Card } from '@tremor/react';

import type { PromptDiffEntry } from '../../../types/promptManagement';

// ============================================================================
// Constants
// ============================================================================

/** Model display names for user-friendly labels */
const MODEL_DISPLAY_NAMES: Record<string, string> = {
  nemotron: 'Nemotron',
  florence2: 'Florence-2',
  yolo_world: 'YOLO-World',
  xclip: 'X-CLIP',
  fashion_clip: 'Fashion-CLIP',
};

// ============================================================================
// Types
// ============================================================================

export interface ConfigDiffViewProps {
  /** The diff entry to display */
  diff: PromptDiffEntry;
  /** Whether to show collapsed view (only model name and status) */
  collapsed?: boolean;
  /** Callback when expand/collapse is toggled */
  onToggleCollapse?: () => void;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Format a value for display in the diff
 */
function formatValue(value: unknown): string {
  if (typeof value === 'string') {
    // Truncate long strings
    if (value.length > 100) {
      return `"${value.substring(0, 100)}..."`;
    }
    return `"${value}"`;
  }
  if (Array.isArray(value)) {
    if (value.length > 5) {
      return `[${value
        .slice(0, 5)
        .map((v) => formatValue(v))
        .join(', ')}, ...+${value.length - 5} more]`;
    }
    return `[${value.map((v) => formatValue(v)).join(', ')}]`;
  }
  if (typeof value === 'object' && value !== null) {
    return JSON.stringify(value);
  }
  return String(value);
}

/**
 * Compute detailed diff between two configurations
 */
function computeDetailedDiff(
  current: Record<string, unknown> | undefined,
  imported: Record<string, unknown>
): {
  key: string;
  type: 'added' | 'removed' | 'changed';
  oldValue?: unknown;
  newValue?: unknown;
}[] {
  const diffs: {
    key: string;
    type: 'added' | 'removed' | 'changed';
    oldValue?: unknown;
    newValue?: unknown;
  }[] = [];

  const currentKeys = current ? Object.keys(current) : [];
  const importedKeys = Object.keys(imported);

  // Find removed keys
  for (const key of currentKeys) {
    if (key === 'version') continue; // Skip version field
    if (!importedKeys.includes(key)) {
      diffs.push({ key, type: 'removed', oldValue: current?.[key] });
    }
  }

  // Find added and changed keys
  for (const key of importedKeys) {
    if (key === 'version') continue; // Skip version field
    if (!current || !currentKeys.includes(key)) {
      diffs.push({ key, type: 'added', newValue: imported[key] });
    } else if (JSON.stringify(current[key]) !== JSON.stringify(imported[key])) {
      diffs.push({ key, type: 'changed', oldValue: current[key], newValue: imported[key] });
    }
  }

  return diffs;
}

// ============================================================================
// Component
// ============================================================================

/**
 * Displays configuration diff for a single model with visual highlighting.
 *
 * Shows:
 * - Model name with change status badge
 * - Individual field changes with red (removed) / green (added) highlighting
 *
 * @example
 * ```tsx
 * <ConfigDiffView
 *   diff={{
 *     model: 'nemotron',
 *     has_changes: true,
 *     current_config: { temperature: 0.7 },
 *     imported_config: { temperature: 0.8 },
 *     changes: ['temperature: 0.7 -> 0.8'],
 *   }}
 * />
 * ```
 */
export default function ConfigDiffView({
  diff,
  collapsed = false,
  onToggleCollapse,
}: ConfigDiffViewProps) {
  const modelName = MODEL_DISPLAY_NAMES[diff.model] || diff.model;
  const detailedDiffs = computeDetailedDiff(diff.current_config, diff.imported_config);

  return (
    <Card className="border-gray-700 bg-gray-900/50" data-testid={`config-diff-${diff.model}`}>
      {/* Header with model name and status */}
      <button
        type="button"
        className="flex w-full items-center justify-between text-left"
        onClick={onToggleCollapse}
        aria-expanded={!collapsed}
        aria-label={`Toggle ${modelName} diff details`}
      >
        <div className="flex items-center gap-3">
          <span className="font-medium text-white">{modelName}</span>
          {diff.current_version && (
            <span className="text-sm text-gray-400">v{diff.current_version}</span>
          )}
        </div>
        <Badge color={diff.has_changes ? 'amber' : 'gray'} size="sm">
          {diff.has_changes ? 'WILL CHANGE' : 'NO CHANGE'}
        </Badge>
      </button>

      {/* Diff details (when expanded and has changes) */}
      {!collapsed && diff.has_changes && (
        <div className="mt-4 space-y-2">
          {detailedDiffs.length > 0 ? (
            <div className="rounded-lg border border-gray-700 bg-gray-950 p-3 font-mono text-sm">
              {detailedDiffs.map((d, idx) => (
                <div key={`${d.key}-${idx}`} className="py-1">
                  {d.type === 'removed' && (
                    <div className="text-red-400">
                      - {d.key}: {formatValue(d.oldValue)}
                    </div>
                  )}
                  {d.type === 'added' && (
                    <div className="text-green-400">
                      + {d.key}: {formatValue(d.newValue)}
                    </div>
                  )}
                  {d.type === 'changed' && (
                    <>
                      <div className="text-red-400">
                        - {d.key}: {formatValue(d.oldValue)}
                      </div>
                      <div className="text-green-400">
                        + {d.key}: {formatValue(d.newValue)}
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
          ) : (
            // Fallback to showing the change descriptions from the API
            <div className="rounded-lg border border-gray-700 bg-gray-950 p-3 text-sm">
              {diff.changes.map((change, idx) => (
                <div key={idx} className="py-1 text-gray-300">
                  {change}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* No changes message */}
      {!collapsed && !diff.has_changes && (
        <p className="mt-2 text-sm text-gray-500">
          Configuration is identical to the current version.
        </p>
      )}
    </Card>
  );
}
