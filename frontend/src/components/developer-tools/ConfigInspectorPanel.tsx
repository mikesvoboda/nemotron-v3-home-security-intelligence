/**
 * ConfigInspectorPanel - Displays application configuration key-value pairs
 *
 * This component shows all config values from the debug API in a read-only table.
 * Sensitive values are shown as [REDACTED] in gray italic.
 * Provides copy functionality for individual values and all values as JSON.
 */
import { Copy, CheckCircle, AlertTriangle, Loader2, FileJson } from 'lucide-react';
import { useState, useCallback } from 'react';

import { useDebugConfigQuery, type ConfigEntry } from '../../hooks/useDebugConfigQuery';
import { useToast } from '../../hooks/useToast';

// ============================================================================
// Value Formatting
// ============================================================================

/**
 * Formats a config value for display
 */
function formatValue(value: unknown): string {
  if (value === null) {
    return '\u2014'; // em dash
  }
  if (value === undefined) {
    return '\u2014'; // em dash
  }
  if (typeof value === 'boolean') {
    return value ? 'true' : 'false';
  }
  if (typeof value === 'number') {
    // Add commas for large numbers
    return value.toLocaleString();
  }
  if (typeof value === 'string') {
    return value;
  }
  // For objects/arrays, stringify
  return JSON.stringify(value);
}

/**
 * Gets the display string for copying (raw value)
 */
function getValueForCopy(value: unknown): string {
  if (value === null || value === undefined) {
    return '';
  }
  if (typeof value === 'object') {
    return JSON.stringify(value);
  }
  if (typeof value === 'string') {
    return value;
  }
  // For primitives, use JSON.stringify to avoid [object Object]
  return JSON.stringify(value);
}

// ============================================================================
// Types
// ============================================================================

/** Props for ConfigInspectorPanel (currently none, reserved for future use) */
export interface ConfigInspectorPanelProps {
  /** Optional className for additional styling */
  className?: string;
}

// ============================================================================
// Component
// ============================================================================

export default function ConfigInspectorPanel(_props: ConfigInspectorPanelProps = {}) {
  const { configEntries, data, isLoading, error, refetch } = useDebugConfigQuery();
  const { success, error: toastError } = useToast();
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const handleCopyValue = useCallback(
    async (entry: ConfigEntry) => {
      try {
        await navigator.clipboard.writeText(getValueForCopy(entry.value));
        setCopiedKey(entry.key);
        success('Copied to clipboard');
        setTimeout(() => setCopiedKey(null), 2000);
      } catch {
        toastError('Failed to copy to clipboard');
      }
    },
    [success, toastError]
  );

  const handleCopyAllAsJson = useCallback(async () => {
    if (!data) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(data, null, 2));
      success('Copied all config as JSON');
    } catch {
      toastError('Failed to copy to clipboard');
    }
  }, [data, success, toastError]);

  // Loading state
  if (isLoading) {
    return (
      <div className="rounded-lg border border-gray-800 bg-[#1F1F1F] p-6">
        <h3 className="mb-4 text-lg font-semibold text-white">Configuration Inspector</h3>
        <div className="flex items-center justify-center py-8" data-testid="config-loading">
          <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
          <span className="ml-2 text-gray-400">Loading configuration...</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="rounded-lg border border-gray-800 bg-[#1F1F1F] p-6">
        <h3 className="mb-4 text-lg font-semibold text-white">Configuration Inspector</h3>
        <div
          className="flex items-center gap-2 rounded bg-red-500/10 px-4 py-3 text-red-400"
          data-testid="config-error"
        >
          <AlertTriangle className="h-5 w-5" />
          <span>Failed to load configuration: {error.message}</span>
          <button
            onClick={() => void refetch()}
            className="ml-auto text-sm underline hover:no-underline"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-gray-800 bg-[#1F1F1F] p-6">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white">Configuration Inspector</h3>
      </div>

      {/* Config Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm" role="table">
          <thead>
            <tr className="border-b border-gray-700">
              <th className="pb-2 pr-4 font-medium text-gray-400">Key</th>
              <th className="pb-2 pr-4 font-medium text-gray-400">Value</th>
              <th className="pb-2 font-medium text-gray-400">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {configEntries.map((entry) => (
              <tr key={entry.key} className="hover:bg-gray-800/30">
                <td className="py-2 pr-4">
                  <code className="rounded bg-gray-800 px-1.5 py-0.5 text-xs text-[#76B900]">
                    {entry.key}
                  </code>
                </td>
                <td className="py-2 pr-4">
                  <span
                    data-testid={`value-${entry.key}`}
                    data-sensitive={entry.isSensitive ? 'true' : undefined}
                    className={
                      entry.isSensitive
                        ? 'italic text-gray-500'
                        : entry.value === null
                          ? 'text-gray-500'
                          : typeof entry.value === 'boolean'
                            ? entry.value
                              ? 'text-green-400'
                              : 'text-red-400'
                            : 'text-gray-300'
                    }
                  >
                    {formatValue(entry.value)}
                  </span>
                </td>
                <td className="py-2">
                  <button
                    onClick={() => void handleCopyValue(entry)}
                    className="rounded p-1 text-gray-500 transition-colors hover:bg-gray-700 hover:text-gray-300"
                    data-testid={`copy-${entry.key}`}
                    aria-label={`Copy ${entry.key} value`}
                  >
                    {copiedKey === entry.key ? (
                      <CheckCircle className="h-4 w-4 text-green-500" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Copy All Button */}
      <div className="mt-4 flex justify-end border-t border-gray-800 pt-4">
        <button
          onClick={() => void handleCopyAllAsJson()}
          className="flex items-center gap-2 rounded bg-gray-700 px-3 py-1.5 text-sm font-medium text-gray-200 transition-colors hover:bg-gray-600"
          aria-label="Copy all as JSON"
        >
          <FileJson className="h-4 w-4" />
          Copy All as JSON
        </button>
      </div>
    </div>
  );
}
