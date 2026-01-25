/**
 * XClipConfigForm - Form for editing X-CLIP model configuration
 *
 * Provides controls for:
 * - action_classes: Tag input for action recognition classes
 *
 * @see NEM-2697 - Build Prompt Management page
 */

import { Button, TextInput } from '@tremor/react';
import { Plus, X } from 'lucide-react';
import { useCallback, useState } from 'react';

import type { XClipConfig } from '../../../../types/promptManagement';

// ============================================================================
// Types
// ============================================================================

export interface XClipConfigFormProps {
  /** Current configuration values */
  config: XClipConfig;
  /** Callback when configuration changes */
  onChange: (config: XClipConfig) => void;
  /** Whether the form is disabled */
  disabled?: boolean;
}

// ============================================================================
// Component
// ============================================================================

/**
 * Form component for editing X-CLIP AI model configuration.
 *
 * @example
 * ```tsx
 * <XClipConfigForm
 *   config={{ action_classes: ['walking', 'running', 'standing'] }}
 *   onChange={setConfig}
 * />
 * ```
 */
export default function XClipConfigForm({
  config,
  onChange,
  disabled = false,
}: XClipConfigFormProps) {
  const [newAction, setNewAction] = useState('');

  const handleAddAction = useCallback(() => {
    if (newAction.trim() && !config.action_classes.includes(newAction.trim())) {
      onChange({
        ...config,
        action_classes: [...config.action_classes, newAction.trim()],
      });
      setNewAction('');
    }
  }, [config, onChange, newAction]);

  const handleRemoveAction = useCallback(
    (actionToRemove: string) => {
      onChange({
        ...config,
        action_classes: config.action_classes.filter((a) => a !== actionToRemove),
      });
    },
    [config, onChange]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        handleAddAction();
      }
    },
    [handleAddAction]
  );

  return (
    <div className="space-y-6" data-testid="xclip-config-form">
      {/* Action Classes */}
      <div>
        <span id="action-classes-label" className="mb-2 block text-sm font-medium text-gray-200">
          Action Classes
        </span>
        <p className="mb-3 text-xs text-gray-400">
          Define action types for the model to recognize in video frames.
        </p>

        {/* Current actions as tags */}
        <div className="mb-3 flex flex-wrap gap-2">
          {config.action_classes.length === 0 ? (
            <p className="text-sm italic text-gray-500">No action classes defined</p>
          ) : (
            config.action_classes.map((action) => (
              <span
                key={action}
                className="inline-flex items-center gap-1 rounded-full bg-gray-800 px-3 py-1 text-sm text-gray-200"
              >
                {action}
                <button
                  type="button"
                  onClick={() => handleRemoveAction(action)}
                  disabled={disabled}
                  className="ml-1 rounded-full p-0.5 text-gray-400 hover:bg-gray-700 hover:text-red-400 disabled:cursor-not-allowed disabled:opacity-50"
                  aria-label={`Remove action: ${action}`}
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))
          )}
        </div>

        {/* Add new action */}
        <div className="flex gap-2">
          <TextInput
            value={newAction}
            onChange={(e) => setNewAction(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            placeholder="Enter a new action class..."
            className="flex-1 bg-gray-900"
          />
          <Button
            type="button"
            onClick={handleAddAction}
            disabled={disabled || !newAction.trim()}
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
