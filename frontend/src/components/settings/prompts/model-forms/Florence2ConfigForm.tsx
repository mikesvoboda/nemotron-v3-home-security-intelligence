/**
 * Florence2ConfigForm - Form for editing Florence-2 model configuration
 *
 * Provides controls for:
 * - queries: List of scene analysis queries
 *
 * @see NEM-2697 - Build Prompt Management page
 */

import { Button, TextInput } from '@tremor/react';
import { Plus, X } from 'lucide-react';
import { useCallback, useState } from 'react';

import type { Florence2Config } from '../../../../types/promptManagement';

// ============================================================================
// Types
// ============================================================================

export interface Florence2ConfigFormProps {
  /** Current configuration values */
  config: Florence2Config;
  /** Callback when configuration changes */
  onChange: (config: Florence2Config) => void;
  /** Whether the form is disabled */
  disabled?: boolean;
}

// ============================================================================
// Component
// ============================================================================

/**
 * Form component for editing Florence-2 AI model configuration.
 *
 * @example
 * ```tsx
 * <Florence2ConfigForm
 *   config={{ queries: ['What objects are in this scene?'] }}
 *   onChange={setConfig}
 * />
 * ```
 */
export default function Florence2ConfigForm({
  config,
  onChange,
  disabled = false,
}: Florence2ConfigFormProps) {
  const [newQuery, setNewQuery] = useState('');

  const handleAddQuery = useCallback(() => {
    if (newQuery.trim()) {
      onChange({
        ...config,
        queries: [...config.queries, newQuery.trim()],
      });
      setNewQuery('');
    }
  }, [config, onChange, newQuery]);

  const handleRemoveQuery = useCallback(
    (index: number) => {
      onChange({
        ...config,
        queries: config.queries.filter((_, i) => i !== index),
      });
    },
    [config, onChange]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        handleAddQuery();
      }
    },
    [handleAddQuery]
  );

  return (
    <div className="space-y-6" data-testid="florence2-config-form">
      {/* Scene Analysis Queries */}
      <div>
        <span id="scene-queries-label" className="mb-2 block text-sm font-medium text-gray-200">
          Scene Analysis Queries
        </span>
        <p className="mb-3 text-xs text-gray-400">
          Define questions the model will answer about each scene.
        </p>

        {/* Current queries list */}
        <div className="mb-3 space-y-2">
          {config.queries.length === 0 ? (
            <p className="text-sm italic text-gray-500">No queries defined</p>
          ) : (
            config.queries.map((query, index) => (
              <div
                key={index}
                className="flex items-center gap-2 rounded-lg border border-gray-700 bg-gray-900 px-3 py-2"
              >
                <span className="flex-1 text-sm text-gray-200">{query}</span>
                <button
                  type="button"
                  onClick={() => handleRemoveQuery(index)}
                  disabled={disabled}
                  className="rounded p-1 text-gray-400 hover:bg-gray-800 hover:text-red-400 disabled:cursor-not-allowed disabled:opacity-50"
                  aria-label={`Remove query: ${query}`}
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ))
          )}
        </div>

        {/* Add new query */}
        <div className="flex gap-2">
          <TextInput
            value={newQuery}
            onChange={(e) => setNewQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            placeholder="Enter a new scene analysis query..."
            className="flex-1 bg-gray-900"
          />
          <Button
            type="button"
            onClick={handleAddQuery}
            disabled={disabled || !newQuery.trim()}
            variant="secondary"
            icon={Plus}
          >
            Add
          </Button>
        </div>
      </div>
    </div>
  );
}
